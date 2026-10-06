using System.Collections.Generic;
using UnityEngine;

namespace MultiBash
{
    /// <summary>
    /// Host-side weapon logic for one player. Reads the networked loadout, fires weapons on cooldown,
    /// applies damage, and tells every peer to play the matching visual via RPC.
    /// To add a new weapon behavior: add a WeaponKind and a case in Fire()/TickContinuous().
    /// </summary>
    public class WeaponSystem
    {
        class Slot
        {
            public int weaponIndex;
            public int level;
            public float cooldown;
            public WeaponDefinition def;
            public int fires;          // volleys fired (evolution extras trigger every few)
            public float extraTimer;   // continuous weapons: timer for their evolution extra
            public readonly Dictionary<Enemy, float> hitTimers = new();
        }

        readonly PlayerCharacter _owner;
        readonly List<Slot> _slots = new();
        int _version = -1;
        static readonly List<Enemy> Hits = new(64);
        static readonly HashSet<Enemy> Chained = new();
        static readonly List<Enemy> TempList = new(32);
        static readonly List<Enemy> DeadKeys = new(16);

        public WeaponSystem(PlayerCharacter owner) => _owner = owner;

        void Sync()
        {
            if (_version == _owner.LoadoutVersion) return;
            _version = _owner.LoadoutVersion;
            var db = GameDatabase.Instance;
            var keep = new List<Slot>();
            for (int i = 0; i < PlayerCharacter.MaxWeaponSlots; i++)
            {
                int id = _owner.WeaponIds.Get(i) - 1;
                if (id < 0) continue;
                var existing = _slots.Find(s => s.weaponIndex == id);
                if (existing == null)
                    existing = new Slot { weaponIndex = id, def = db.GetWeapon(id), cooldown = 0.3f + 0.15f * keep.Count };
                existing.level = _owner.WeaponLevels.Get(i);
                keep.Add(existing);
            }
            _slots.Clear();
            _slots.AddRange(keep);
        }

        public void Tick(float dt)
        {
            Sync();
            EnemyRegistry.EnsureGrid(_owner.Runner.Tick);
            var stats = _owner.Stats;
            foreach (var s in _slots)
            {
                if (s.def == null) continue;
                var lvl = s.def.GetLevel(s.level);
                if (s.def.kind == WeaponKind.Orbit)
                {
                    TickOrbit(s, lvl, stats, dt);
                    continue;
                }
                s.cooldown -= dt;
                if (s.cooldown <= 0f)
                {
                    bool fired = Fire(s, lvl, stats);
                    s.cooldown = fired ? lvl.cooldown * stats.Cooldown : 0.15f;
                    if (fired) s.fires++;
                }
            }
        }

        /// <summary>Set by the last damage roll; Enemy.TakeDamage consumes it to show "CRIT!" on every client.</summary>
        public static bool PendingCrit;

        /// <summary>Damage roll: ±10% spread and a 10% (+luck) chance to crit for double damage.</summary>
        float Dmg(WeaponLevel lvl, PlayerStats stats)
        {
            var C = CombatManager.Settings;
            float d = lvl.damage * stats.Damage * Random.Range(1f - C.damageSpread, 1f + C.damageSpread);
            PendingCrit = Random.value < stats.CritChance + stats.Luck * C.critChancePerLuck;
            if (PendingCrit) d *= stats.CritDamage;
            return d;
        }

        Vector3 Origin => _owner.transform.position + Vector3.up * 0.9f;

        bool Fire(Slot s, WeaponLevel lvl, PlayerStats stats)
        {
            switch (s.def.kind)
            {
                case WeaponKind.MeleeArc: return FireMelee(s, lvl, stats);
                case WeaponKind.Projectile: return FireProjectile(s, lvl, stats);
                case WeaponKind.Chain: return FireChain(s, lvl, stats);
                case WeaponKind.Lobbed: return FireLobbed(s, lvl, stats);
                case WeaponKind.Aura: return FireAura(s, lvl, stats);
                case WeaponKind.Boomerang: return FireBoomerang(s, lvl, stats);
                case WeaponKind.Meteor: return FireMeteor(s, lvl, stats);
                case WeaponKind.Nova: return FireNova(s, lvl, stats);
                case WeaponKind.Homing: return FireHoming(s, lvl, stats);
            }
            return false;
        }

        // ------------------------------------------------------------------ Boomerang: out and back, hits twice

        bool FireBoomerang(Slot s, WeaponLevel lvl, PlayerStats stats)
        {
            float speed = lvl.speed * stats.ProjectileSpeed;
            float life = lvl.duration * stats.Duration;
            var target = EnemyRegistry.Nearest(_owner.transform.position, speed * life * 0.5f + 2f);
            if (target == null) return false;
            var dir = target.transform.position - _owner.transform.position;
            dir.y = 0;
            dir.Normalize();
            int count = Mathf.Max(1, lvl.amount + stats.ProjectileCount);
            float spread = Mathf.Min(25f * (count - 1), 120f);
            if (s.def.isEvolution) spread = 360f * (count - 1) / count;   // Twin Moons: a full circle of glaives
            for (int i = 0; i < count; i++)
            {
                float a = count == 1 ? 0f : -spread * 0.5f + spread * i / (count - 1);
                CombatWorld.SpawnProjectile(new CombatWorld.Projectile
                {
                    owner = _owner, weapon = s.weaponIndex, pos = Origin, vel = Quaternion.Euler(0, a, 0) * dir * speed,
                    life = 30f, outTime = life * 0.5f, pierce = 999, damage = Dmg(lvl, stats), crit = PendingCrit,
                    knockback = lvl.knockback, radius = 0.7f * lvl.area * Mathf.Sqrt(stats.Area),
                });
                PendingCrit = false;
            }
            _owner.Rpc_Boomerang(Origin, dir, (byte)count, spread, speed, life, (byte)s.weaponIndex);
            return true;
        }

        // ------------------------------------------------------------------ Meteor Staff: delayed explosions on crowds

        bool FireMeteor(Slot s, WeaponLevel lvl, PlayerStats stats)
        {
            EnemyRegistry.NearestN(_owner.transform.position, 20f, 24, TempList);
            if (TempList.Count == 0) return false;
            int count = Mathf.Max(1, lvl.amount + stats.ProjectileCount);
            float radius = lvl.area * stats.Area;
            for (int i = 0; i < count; i++)
            {
                // pick the densest spot among a few samples
                Enemy best = null;
                int bestN = -1;
                for (int k = 0; k < 5; k++)
                {
                    var c = TempList[Random.Range(0, TempList.Count)];
                    EnemyRegistry.Query(c.transform.position, radius, Hits);
                    if (Hits.Count > bestN) { bestN = Hits.Count; best = c; }
                }
                var p = best.transform.position + new Vector3(Random.Range(-1f, 1f), 0, Random.Range(-1f, 1f));
                p.y = Ground.Height(p);
                float delay = 0.75f;
                CombatWorld.SpawnBlast(new CombatWorld.Blast
                {
                    owner = _owner, pos = p, delay = delay, radius = radius, damage = Dmg(lvl, stats), crit = PendingCrit, knockback = lvl.knockback,
                });
                PendingCrit = false;
                _owner.Rpc_Meteor(p, delay, radius, (byte)s.weaponIndex);
                if (s.def.isEvolution)
                {
                    // Armageddon: every impact leaves a burning crater
                    float burn = 3.5f * stats.Duration;
                    CombatWorld.SpawnPuddle(new CombatWorld.Puddle
                    {
                        owner = _owner, weapon = s.weaponIndex, pos = p, radius = radius * 0.75f, delay = delay, life = burn,
                        damagePerTick = lvl.damage * stats.Damage * 0.12f, tickInterval = 0.4f, knockback = 0f,
                    });
                    _owner.Rpc_Flask(p + Vector3.up * 0.2f, p, delay, radius * 0.75f, burn, (byte)s.weaponIndex);
                }
            }
            return true;
        }

        // ------------------------------------------------------------------ Frost Nova: ring that damages and slows

        bool FireNova(Slot s, WeaponLevel lvl, PlayerStats stats)
        {
            float radius = lvl.area * stats.Area;
            var pos = _owner.transform.position;
            Breakables.HitSphere(pos, radius);
            EnemyRegistry.Query(pos, radius, Hits);
            if (Hits.Count == 0) return false;
            float slow = lvl.duration * stats.Duration;
            foreach (var e in Hits)
            {
                e.TakeDamage(Dmg(lvl, stats), pos, lvl.knockback, _owner);
                e.ApplySlow(slow);
            }
            // extra rings (levels + Multishot): each one bigger, a beat later
            int rings = Mathf.Max(1, lvl.amount + stats.ProjectileCount);
            for (int k = 1; k < rings; k++)
            {
                CombatWorld.SpawnBlast(new CombatWorld.Blast
                {
                    owner = _owner, pos = pos, delay = 0.2f * k, radius = radius * (1f + 0.4f * k), damage = Dmg(lvl, stats) * 0.75f,
                    crit = PendingCrit, knockback = lvl.knockback * 0.7f, slow = slow,
                });
                PendingCrit = false;
            }
            _owner.Rpc_Nova(radius, (byte)rings, (byte)s.weaponIndex);
            if (s.def.isEvolution)
            {
                // Absolute Zero: a spray of homing frost shards
                int n = 8 + stats.ProjectileCount * 2;
                for (int i = 0; i < n; i++)
                {
                    var d = Quaternion.Euler(-10f, i * 360f / n, 0) * Vector3.forward;
                    CombatWorld.SpawnProjectile(new CombatWorld.Projectile
                    {
                        owner = _owner, weapon = s.weaponIndex, pos = Origin + Vector3.up * 0.3f, vel = d * 16f, life = 1.6f, pierce = 2,
                        damage = Dmg(lvl, stats) * 0.5f, crit = PendingCrit, knockback = 2f, radius = 0.45f, turn = 300f, slow = slow,
                    });
                    PendingCrit = false;
                }
                _owner.Rpc_Homing(Origin + Vector3.up * 0.3f, Vector3.forward, (byte)n, 16f, 1.6f, 2, (byte)s.weaponIndex);
            }
            return true;
        }

        // ------------------------------------------------------------------ Spirit Daggers: homing blades

        bool FireHoming(Slot s, WeaponLevel lvl, PlayerStats stats)
        {
            if (EnemyRegistry.Nearest(_owner.transform.position, 18f) == null) return false;
            int count = Mathf.Max(1, lvl.amount + stats.ProjectileCount);
            float speed = lvl.speed * stats.ProjectileSpeed;
            float life = lvl.duration * stats.Duration;
            var fwd = _owner.transform.forward;
            for (int i = 0; i < count; i++)
            {
                var d = Quaternion.Euler(-15f, -60f + 120f * (count == 1 ? 0.5f : i / (float)(count - 1)), 0) * fwd;
                CombatWorld.SpawnProjectile(new CombatWorld.Projectile
                {
                    owner = _owner, weapon = s.weaponIndex, pos = Origin + Vector3.up * 0.4f, vel = d * speed, life = life,
                    pierce = Mathf.Max(1, lvl.pierce), damage = Dmg(lvl, stats), crit = PendingCrit, knockback = lvl.knockback,
                    radius = 0.45f, turn = 360f,
                });
                PendingCrit = false;
            }
            _owner.Rpc_Homing(Origin, fwd, (byte)count, speed, life, (byte)Mathf.Clamp(lvl.pierce, 1, 255), (byte)s.weaponIndex);
            if (s.def.isEvolution && s.fires % 2 == 1)
            {
                // Phantom Legion: every other volley a ring of spirit blades bursts out around you
                int n = 10;
                for (int i = 0; i < n; i++)
                {
                    var d = Quaternion.Euler(-5f, i * 36f, 0) * Vector3.forward;
                    CombatWorld.SpawnProjectile(new CombatWorld.Projectile
                    {
                        owner = _owner, weapon = s.weaponIndex, pos = Origin + Vector3.up * 0.4f, vel = d * speed, life = life,
                        pierce = Mathf.Max(1, lvl.pierce), damage = Dmg(lvl, stats), crit = PendingCrit, knockback = lvl.knockback, radius = 0.45f, turn = 360f,
                    });
                    PendingCrit = false;
                }
                _owner.Rpc_Homing(Origin + Vector3.up * 0.4f, Vector3.forward, (byte)n, speed, life, (byte)Mathf.Clamp(lvl.pierce, 1, 255), (byte)s.weaponIndex);
            }
            return true;
        }

        // ------------------------------------------------------------------ Greatsword: arc sweep

        bool FireMelee(Slot s, WeaponLevel lvl, PlayerStats stats)
        {
            float radius = lvl.area * stats.Area;
            var target = EnemyRegistry.Nearest(_owner.transform.position, radius + 1.5f);
            if (target == null) return false;
            var dir = target.transform.position - _owner.transform.position;
            dir.y = 0;
            dir = dir.sqrMagnitude > 0.001f ? dir.normalized : _owner.transform.forward;

            const float arc = 150f;
            int swings = Mathf.Max(1, lvl.amount + stats.ProjectileCount);
            for (int i = 0; i < swings; i++)
            {
                // extra swings alternate: front, back, sides
                var sd = Quaternion.Euler(0, i * (360f / swings), 0) * dir;
                ArcDamage(s, lvl, stats, sd, radius, arc);
                _owner.Rpc_Slash(sd, radius, arc, (byte)s.weaponIndex);
                if (s.def.isEvolution)
                {
                    // Titan's Cleaver: each swing slams a shockwave where the blade lands
                    var at = _owner.transform.position + sd * radius * 0.85f;
                    at.y = Ground.Height(at);
                    CombatWorld.SpawnBlast(new CombatWorld.Blast { owner = _owner, pos = at, delay = 0.12f, radius = 3f * Mathf.Sqrt(stats.Area), damage = Dmg(lvl, stats) * 0.6f, crit = PendingCrit, knockback = 8f });
                    PendingCrit = false;
                    _owner.Rpc_Shock(at, 3f * Mathf.Sqrt(stats.Area), (byte)s.weaponIndex);
                }
            }
            return true;
        }

        void ArcDamage(Slot s, WeaponLevel lvl, PlayerStats stats, Vector3 dir, float radius, float arc)
        {
            var pos = _owner.transform.position;
            Breakables.HitSphere(pos + dir * radius * 0.55f, radius * 0.55f);
            EnemyRegistry.Query(pos, radius, Hits);
            float cos = Mathf.Cos(arc * 0.5f * Mathf.Deg2Rad);
            bool any = false;
            foreach (var e in Hits)
            {
                var d = e.transform.position - pos;
                d.y = 0;
                if (d.sqrMagnitude > 0.25f && Vector3.Dot(d.normalized, dir) < cos) continue;
                e.TakeDamage(Dmg(lvl, stats), pos, lvl.knockback, _owner);
                any = true;
            }
            if (any) _owner.Rpc_HitSound((byte)s.weaponIndex, pos + dir * radius * 0.5f);
        }

        // ------------------------------------------------------------------ Longbow: piercing arrows

        bool FireProjectile(Slot s, WeaponLevel lvl, PlayerStats stats)
        {
            float range = lvl.speed * stats.ProjectileSpeed * lvl.duration * stats.Duration;
            var target = EnemyRegistry.Nearest(_owner.transform.position, range);
            if (target == null) return false;
            var dir = target.transform.position + Vector3.up * 0.6f - Origin;
            dir.y = 0;
            dir.Normalize();
            int count = Mathf.Max(1, lvl.amount + stats.ProjectileCount);
            float spread = Mathf.Min(10f * (count - 1), 70f);
            float speed = lvl.speed * stats.ProjectileSpeed;
            float life = lvl.duration * stats.Duration;
            for (int i = 0; i < count; i++)
            {
                float a = count == 1 ? 0f : -spread * 0.5f + spread * i / (count - 1);
                var d = Quaternion.Euler(0, a, 0) * dir;
                CombatWorld.SpawnProjectile(new CombatWorld.Projectile
                {
                    owner = _owner,
                    weapon = s.weaponIndex,
                    pos = Origin,
                    vel = d * speed,
                    life = life,
                    pierce = lvl.pierce,
                    damage = Dmg(lvl, stats),
                    crit = PendingCrit,
                    knockback = lvl.knockback,
                    radius = 0.45f * Mathf.Sqrt(stats.Area),
                });
                PendingCrit = false;
            }
            _owner.Rpc_Projectiles(Origin, dir, (byte)count, spread, speed, life, (byte)Mathf.Clamp(lvl.pierce, 1, 255), (byte)s.weaponIndex);
            if (s.def.isEvolution && s.fires % 3 == 2)
            {
                // Hail of Arrows: every third volley also looses a full ring of arrows
                int n = 16;
                float ring = 360f * (n - 1) / n;
                for (int i = 0; i < n; i++)
                {
                    var d = Quaternion.Euler(0, -ring * 0.5f + ring * i / (n - 1), 0) * dir;
                    CombatWorld.SpawnProjectile(new CombatWorld.Projectile
                    {
                        owner = _owner, weapon = s.weaponIndex, pos = Origin, vel = d * speed, life = life, pierce = lvl.pierce,
                        damage = Dmg(lvl, stats), crit = PendingCrit, knockback = lvl.knockback, radius = 0.45f * Mathf.Sqrt(stats.Area),
                    });
                    PendingCrit = false;
                }
                _owner.Rpc_Projectiles(Origin, dir, (byte)n, ring, speed, life, (byte)Mathf.Clamp(lvl.pierce, 1, 255), (byte)s.weaponIndex);
            }
            return true;
        }

        // ------------------------------------------------------------------ Storm Staff: chain lightning

        bool FireChain(Slot s, WeaponLevel lvl, PlayerStats stats)
        {
            const float range = 16f;
            int bolts = Mathf.Max(1, lvl.amount);
            int jumps = lvl.pierce + stats.ProjectileCount;
            float jumpRange = lvl.area * stats.Area;
            Chained.Clear();
            bool fired = false;
            for (int b = 0; b < bolts; b++)
            {
                EnemyRegistry.NearestN(_owner.transform.position, range, bolts + 3, TempList);
                Enemy first = null;
                foreach (var e in TempList) if (!Chained.Contains(e)) { first = e; break; }
                if (first == null) break;
                fired = true;
                Vector3 from = Origin + Vector3.up * 0.8f;
                var current = first;
                if (s.def.isEvolution)
                {
                    // Thunder God's Rod: the first strike of every bolt explodes
                    var at = first.transform.position;
                    CombatWorld.SpawnBlast(new CombatWorld.Blast { owner = _owner, pos = at, delay = 0.05f, radius = 2.6f * Mathf.Sqrt(stats.Area), damage = Dmg(lvl, stats) * 0.8f, crit = PendingCrit, knockback = 5f });
                    PendingCrit = false;
                    _owner.Rpc_Shock(at, 2.6f * Mathf.Sqrt(stats.Area), (byte)s.weaponIndex);
                }
                for (int j = 0; j <= jumps && current != null; j++)
                {
                    Chained.Add(current);
                    var to = current.transform.position + Vector3.up * 0.8f * current.ScaleMul;
                    _owner.Rpc_Lightning(from, to, (byte)s.weaponIndex, j == 0 && b == 0);
                    current.TakeDamage(Dmg(lvl, stats) * (j == 0 ? 1f : 0.85f), from, lvl.knockback, _owner);
                    from = to;
                    current = EnemyRegistry.Nearest(to, jumpRange, Chained);
                }
            }
            return fired;
        }

        // ------------------------------------------------------------------ Poison Flask: lobbed puddles

        bool FireLobbed(Slot s, WeaponLevel lvl, PlayerStats stats)
        {
            const float range = 14f;
            int count = Mathf.Max(1, lvl.amount + stats.ProjectileCount);
            EnemyRegistry.NearestN(_owner.transform.position, range, count * 3, TempList);
            if (TempList.Count == 0) return false;
            float radius = lvl.area * stats.Area;
            float duration = lvl.duration * stats.Duration;
            for (int i = 0; i < count; i++)
            {
                var t = TempList[Random.Range(0, TempList.Count)];
                var to = t.transform.position;
                to += new Vector3(Random.Range(-1f, 1f), 0, Random.Range(-1f, 1f)) * (i == 0 ? 0.5f : 2.5f);
                to.y = Ground.Height(to) + 0.05f;
                float flight = 0.55f;
                CombatWorld.SpawnPuddle(new CombatWorld.Puddle
                {
                    owner = _owner,
                    weapon = s.weaponIndex,
                    pos = to,
                    radius = radius,
                    delay = flight,
                    life = duration,
                    damagePerTick = Dmg(lvl, stats),
                    crit = PendingCrit,
                    tickInterval = 0.5f,
                    knockback = lvl.knockback,
                    slow = s.def.isEvolution ? 0.6f : 0f,   // Plague Cauldron: the plague pools also slow
                });
                PendingCrit = false;
                _owner.Rpc_Flask(Origin + Vector3.up * 0.5f, to, flight, radius, duration, (byte)s.weaponIndex);
            }
            return true;
        }

        // ------------------------------------------------------------------ Holy Aura: damage ring

        bool FireAura(Slot s, WeaponLevel lvl, PlayerStats stats)
        {
            float radius = lvl.area * stats.Area;
            var pos = _owner.transform.position;
            Breakables.HitSphere(pos, radius);
            EnemyRegistry.Query(pos, radius, Hits);
            foreach (var e in Hits) e.TakeDamage(Dmg(lvl, stats), pos, lvl.knockback, _owner);
            // extra rings (levels + Multishot): wider halos that burn the outer crowd
            int rings = Mathf.Max(1, lvl.amount + stats.ProjectileCount);
            for (int k = 1; k < rings; k++)
            {
                float inner = radius * (1f + 0.45f * (k - 1)), outer = radius * (1f + 0.45f * k);
                EnemyRegistry.Query(pos, outer, Hits);
                foreach (var e in Hits)
                {
                    var d = e.transform.position - pos;
                    d.y = 0;
                    if (d.sqrMagnitude >= inner * inner) e.TakeDamage(Dmg(lvl, stats) * 0.7f, pos, lvl.knockback, _owner);
                }
            }
            if (s.def.isEvolution)
            {
                // Sanctuary: the holy light also mends you and allies standing in it
                foreach (var p in PlayerCharacter.All)
                    if (p != null && p.IsAlive && (p.transform.position - pos).sqrMagnitude <= radius * radius) p.Heal(p.MaxHealth * 0.006f);
            }
            _owner.Rpc_AuraPulse(radius, (byte)s.weaponIndex);
            return true; // always pulses (also fine when no enemies are near)
        }

        // ------------------------------------------------------------------ Orbiting Blades: continuous

        void TickOrbit(Slot s, WeaponLevel lvl, PlayerStats stats, float dt)
        {
            int blades = Mathf.Max(1, lvl.amount + stats.ProjectileCount);
            float radius = lvl.area * stats.Area;
            float hitRadius = 0.7f * Mathf.Sqrt(stats.Area);
            float time = (float)(_owner.Runner.Tick * _owner.Runner.DeltaTime);
            float angle0 = OrbitVisual.AngleAt(time, lvl.speed * stats.ProjectileSpeed);
            var center = _owner.transform.position;

            // forget old hit timers
            DeadKeys.Clear();
            foreach (var kv in s.hitTimers) if (kv.Key == null || !kv.Key.IsAlive || time >= kv.Value) DeadKeys.Add(kv.Key);
            foreach (var k in DeadKeys) s.hitTimers.Remove(k);

            float rehit = lvl.cooldown * stats.Cooldown;
            if (s.def.isEvolution)
            {
                // Blade Tornado: the blades fling copies of themselves outward
                s.extraTimer -= _owner.Runner.DeltaTime;
                if (s.extraTimer <= 0f && EnemyRegistry.Nearest(center, radius + 12f) != null)
                {
                    s.extraTimer = 1.4f * stats.Cooldown;
                    float a0 = angle0 * Mathf.Deg2Rad;
                    var d0 = new Vector3(Mathf.Cos(a0), 0, Mathf.Sin(a0));
                    float ring = 360f * (blades - 1) / Mathf.Max(1, blades);
                    for (int i = 0; i < blades; i++)
                    {
                        var d = Quaternion.Euler(0, -ring * 0.5f + (blades == 1 ? 0 : ring * i / (blades - 1)), 0) * d0;
                        CombatWorld.SpawnProjectile(new CombatWorld.Projectile
                        {
                            owner = _owner, weapon = s.weaponIndex, pos = center + Vector3.up * 0.9f + d * radius, vel = d * 20f, life = 0.8f, pierce = 4,
                            damage = Dmg(lvl, stats) * 0.8f, crit = PendingCrit, knockback = lvl.knockback, radius = 0.6f,
                        });
                        PendingCrit = false;
                    }
                    _owner.Rpc_Projectiles(center + Vector3.up * 0.9f, d0, (byte)blades, ring, 20f, 0.8f, 4, (byte)s.weaponIndex);
                }
            }
            for (int i = 0; i < blades; i++)
            {
                float a = (angle0 + i * 360f / blades) * Mathf.Deg2Rad;
                var p = center + new Vector3(Mathf.Cos(a), 0, Mathf.Sin(a)) * radius;
                Breakables.HitSphere(p, hitRadius);
                EnemyRegistry.Query(p, hitRadius, Hits);
                foreach (var e in Hits)
                {
                    if (s.hitTimers.ContainsKey(e)) continue;
                    s.hitTimers[e] = time + rehit;
                    e.TakeDamage(Dmg(lvl, stats), center, lvl.knockback, _owner);
                    _owner.Rpc_HitSound((byte)s.weaponIndex, p);
                }
            }
        }
    }
}
