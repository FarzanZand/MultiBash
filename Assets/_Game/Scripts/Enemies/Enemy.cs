using Fusion;
using UnityEngine;

namespace MultiBash
{
    /// <summary>
    /// A networked swarm enemy. The host moves it (simple steering, no physics) and resolves damage;
    /// every peer plays the hit flash, damage numbers and animation from the replicated Health.
    /// All tuning lives on the EnemyDefinition asset.
    /// </summary>
    [RequireComponent(typeof(NetworkTransform))]
    public class Enemy : NetworkBehaviour
    {
        [Networked] public byte DefIndex { get; set; }
        [Networked] public NetworkBool Elite { get; set; }
        [Networked] public float Health { get; set; }
        [Networked] public float MaxHealth { get; set; }
        [Networked] public float ContactDamage { get; set; }
        [Networked] public float ScaleMul { get; set; }
        [Networked] public int AttackTick { get; set; }
        [Networked] public NetworkBool Boss { get; set; }
        [Networked] public int CritCount { get; set; }

        public EnemyDefinition Def { get; private set; }
        public float Radius => (Def != null ? Def.radius : 0.5f) * Mathf.Max(0.1f, ScaleMul);
        public bool IsAlive => Object != null && Object.IsValid && Health > 0f;

        static readonly System.Collections.Generic.List<Enemy> Neighbors = new(32);
        static readonly int EmissionId = Shader.PropertyToID("_EmissionColor");
        static readonly int BaseColorId = Shader.PropertyToID("_BaseColor");

        // host-only simulation state
        float _specialTimer = 1.5f;
        bool _telegraphing;
        float _telegraphLeft;
        float _groundY = -1000f;
        Vector3 _knock;
        float _attackTimer;
        float _hopTimer;
        float _hopT;
        bool _hopping;
        Vector3 _hopDir;
        float _hopSpeed;

        // visuals
        Renderer[] _renderers;
        MaterialPropertyBlock _mpb;
        float _lastHealth;
        float _baseScale = 1f;
        int _lastCrit;
        Transform _crown;
        float _flash;
        int _lastAttackTick;
        ProceduralRig _rig;
        Vector3 _lastPos;

        /// <summary>Called by the spawner inside Runner.Spawn's onBeforeSpawned (host).</summary>
        public void Init(int defIndex, bool elite, float healthMul, float damageMul, bool boss = false)
        {
            var def = GameDatabase.Instance.GetEnemy(defIndex);
            var cfg = GameDatabase.Config;
            DefIndex = (byte)defIndex;
            Elite = elite || boss;
            Boss = boss;
            if (boss)
            {
                MaxHealth = def.maxHealth * healthMul * def.bossHealthMultiplier;
                ContactDamage = def.contactDamage * damageMul * def.bossDamageMultiplier;
                ScaleMul = def.bossScale;
            }
            else
            {
                MaxHealth = def.maxHealth * healthMul * (elite ? cfg.eliteHealthMultiplier : 1f);
                ContactDamage = def.contactDamage * damageMul * (elite ? 1.5f : 1f);
                ScaleMul = elite ? cfg.eliteScale : 1f;
            }
            Health = MaxHealth;
        }

        public string DisplayName => Def == null ? "" : Boss && !string.IsNullOrEmpty(Def.bossName) ? Def.bossName : Def.displayName;

        public override void Spawned()
        {
            Def = GameDatabase.Instance.GetEnemy(DefIndex);
            if (ScaleMul <= 0f) ScaleMul = 1f;
            _baseScale = Mathf.Max(0.1f, transform.localScale.x);
            transform.localScale = Vector3.one * ScaleMul * _baseScale;
            EnemyRegistry.Register(this);

            _renderers = GetComponentsInChildren<Renderer>();
            // only the torso casts a shadow: big swarms stay cheap to render
            foreach (var r in _renderers)
                if (r.name != "Body") r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            _mpb = new MaterialPropertyBlock();
            _rig = GetComponentInChildren<ProceduralRig>();
            _lastHealth = Health;
            _lastAttackTick = AttackTick;
            _lastCrit = CritCount;
            _lastPos = transform.position;
            _hopTimer = Random.Range(0f, Def != null ? Def.hopRest : 0.5f);
            ApplyTint(0f);

            var crownPrefab = GameDatabase.Config.eliteCrown;
            if (Elite && crownPrefab != null)
            {
                float top = 0f;
                foreach (var r in _renderers) top = Mathf.Max(top, r.bounds.max.y - transform.position.y);
                _crown = Instantiate(crownPrefab, transform).transform;
                _crown.localPosition = Vector3.up * (top / Mathf.Max(0.01f, transform.lossyScale.y) + 0.35f);
                _crown.localScale = Vector3.one * (Boss ? 0.9f : 0.75f) / Mathf.Max(0.5f, ScaleMul) * 1.6f;
            }
        }

        public override void Despawned(NetworkRunner runner, bool hasState)
        {
            EnemyRegistry.Unregister(this);
        }

        // ------------------------------------------------------------------ host simulation

        public override void FixedUpdateNetwork()
        {
            PerfStats.EnemySim.Start();
            try { Simulate(); }
            finally { PerfStats.EnemySim.Stop(); }
        }

        void Simulate()
        {
            if (!HasStateAuthority || !IsAlive || Def == null) return;
            var gm = GameManager.Instance;
            if (gm == null || gm.State != RunState.Playing) return;

            float dt = Runner.DeltaTime;
            EnemyRegistry.EnsureGrid(Runner.Tick);

            var pos = transform.position;
            var target = PlayerCharacter.NearestAlive(pos);
            Vector3 toTarget = Vector3.zero;
            float dist = float.MaxValue;
            if (target != null)
            {
                toTarget = target.transform.position - pos;
                toTarget.y = 0;
                dist = toTarget.magnitude;
            }
            Vector3 dir = dist > 0.01f && dist < float.MaxValue ? toTarget / dist : transform.forward;

            // separation so the swarm spreads into a crowd instead of a single stack
            Vector3 sep = Vector3.zero;
            EnemyRegistry.Query(pos, Radius * 1.6f, Neighbors, 7);
            foreach (var n in Neighbors)
            {
                if (n == this) continue;
                var d = pos - n.transform.position;
                d.y = 0;
                float m = d.magnitude;
                float want = Radius + n.Radius;
                if (m < 0.001f) { d = new Vector3(Random.Range(-1f, 1f), 0, Random.Range(-1f, 1f)); m = 0.01f; }
                if (m < want) sep += d / m * (want - m) / want;
            }

            float speed = Def.moveSpeed * gm.EnemySpeedMul * (Boss ? 0.8f : Elite ? 0.85f : 1f) * (IsSlowed ? 0.4f : 1f);
            Vector3 vel;
            float y = 0f;

            // telegraphed special (stomp / explode): stand still and wind up, then release
            if (_telegraphing)
            {
                _telegraphLeft -= dt;
                vel = sep * 2f;
                if (_telegraphLeft <= 0f)
                {
                    _telegraphing = false;
                    ReleaseSpecial(pos);
                    if (!IsAlive || Object == null || !Object.IsValid) return;
                }
            }
            else if (Def.movement == EnemyMovement.Flyer)
            {
                // weave left/right while closing in, hover at head height
                var side = new Vector3(-dir.z, 0, dir.x);
                float weave = Mathf.Sin((float)Runner.SimulationTime * 3.2f + Object.Id.Raw * 1.7f);
                vel = (dir + side * weave * 0.7f).normalized * speed + sep * 2.5f;
                // ranged flyers (imps) circle at casting distance instead of diving in
                if (Def.attack == EnemyAttack.Ranged && dist < Def.attackDistance * 0.85f)
                {
                    float spin = (Object.Id.Raw & 1) == 0 ? 1f : -1f;
                    vel = (side * spin * 0.8f - dir * (dist < Def.attackDistance * 0.5f ? 0.6f : 0f)).normalized * speed * 0.7f + sep * 2.5f;
                }
                y = 1.4f + Mathf.Sin((float)Runner.SimulationTime * 5f + Object.Id.Raw) * 0.35f;
            }
            else if (Def.movement == EnemyMovement.Keeper)
            {
                // hold a firing distance: approach, back off, or strafe
                var side = new Vector3(-dir.z, 0, dir.x) * ((Object.Id.Raw & 1) == 0 ? 1f : -1f);
                if (dist > Def.attackDistance * 1.1f) vel = dir * speed;
                else if (dist < Def.attackDistance * 0.65f) vel = -dir * speed * 0.8f;
                else vel = side * speed * 0.45f;
                vel += sep * 4f;
            }
            else if (Def.movement == EnemyMovement.Hopper)
            {
                if (!_hopping)
                {
                    _hopTimer -= dt;
                    vel = sep * 3f;
                    if (_hopTimer <= 0f && target != null)
                    {
                        _hopping = true;
                        _hopT = 0f;
                        _hopDir = dir;
                        // average speed over a full hop cycle equals moveSpeed
                        _hopSpeed = speed * (Def.hopRest + Def.hopTime) / Mathf.Max(0.05f, Def.hopTime);
                        _hopSpeed = Mathf.Min(_hopSpeed, Mathf.Max(dist, 1f) / Def.hopTime * 1.2f);
                    }
                }
                else
                {
                    _hopT += dt / Mathf.Max(0.05f, Def.hopTime);
                    vel = _hopDir * _hopSpeed + sep * 3f;
                    y = Mathf.Sin(Mathf.Clamp01(_hopT) * Mathf.PI) * Def.hopHeight * Mathf.Sqrt(ScaleMul);
                    if (_hopT >= 1f)
                    {
                        _hopping = false;
                        _hopTimer = Def.hopRest * Random.Range(0.8f, 1.2f);
                        y = 0f;
                    }
                }
            }
            else
            {
                vel = dir * speed + sep * 4f;
                // stop pushing into the player when already in reach
                if (dist < Radius + 0.6f) vel = sep * 4f;
            }

            pos += (vel + _knock) * dt;
            _knock = Vector3.MoveTowards(_knock, Vector3.zero, 30f * dt);

            // walk around props (flyers just go over them)
            if (Def.movement != EnemyMovement.Flyer)
            foreach (var o in Obstacle.Near(pos))
            {
                var d = pos - o.transform.position;
                d.y = 0;
                float r = o.WorldRadius + Radius;
                float sq = d.sqrMagnitude;
                if (sq < r * r && sq > 0.0001f)
                {
                    float m = Mathf.Sqrt(sq);
                    pos += d / m * (r - m);
                }
            }

            float half = GameDatabase.Config.arenaHalfSize;
            pos.x = Mathf.Clamp(pos.x, -half, half);
            pos.z = Mathf.Clamp(pos.z, -half, half);

            // follow the terrain: walk down fast, scramble up cliffs at a limited speed (no plateau is a safe spot)
            float ground = Ground.Height(pos);
            if (_groundY < -999f) _groundY = ground;
            _groundY = ground > _groundY ? Mathf.MoveTowards(_groundY, ground, 6f * dt) : Mathf.MoveTowards(_groundY, ground, 20f * dt);
            pos.y = _groundY + y;
            transform.position = pos;

            var face = _hopping ? _hopDir : dir;
            if (face.sqrMagnitude > 0.01f)
                transform.rotation = Quaternion.Slerp(transform.rotation, Quaternion.LookRotation(face), 10f * dt);

            // contact attack
            _attackTimer -= dt;
            if (target != null && _attackTimer <= 0f && dist <= Radius + 0.45f + Def.attackRange
                && Mathf.Abs(target.transform.position.y - pos.y) < 1.7f + y)
            {
                _attackTimer = Def.attackInterval;
                AttackTick = Runner.Tick;
                target.TakeDamage(ContactDamage);
            }

            // special attacks
            _specialTimer -= dt;
            if (target == null || _telegraphing || _specialTimer > 0f || Def.attack == EnemyAttack.Contact) return;
            switch (Def.attack)
            {
                case EnemyAttack.Ranged:
                    if (dist <= Def.attackDistance * 1.35f)
                    {
                        _specialTimer = Def.specialCooldown * Random.Range(0.85f, 1.15f);
                        // lead the target a little so strafing still matters
                        var tp = target.transform.position + Vector3.up * 1.1f + target.Velocity * Mathf.Clamp(dist / Def.projectileSpeed, 0f, 1f) * 0.6f;
                        var origin = pos + Vector3.up * (1.3f * ScaleMul);
                        var v = (tp - origin).normalized * Def.projectileSpeed;
                        CombatWorld.SpawnEnemyShot(new CombatWorld.EnemyShot
                        {
                            pos = origin, vel = v, life = Def.attackDistance * 2.2f / Def.projectileSpeed,
                            damage = ContactDamage * Def.specialDamageMul, radius = Def.specialRadius,
                        });
                        AttackTick = Runner.Tick;
                        gm.Rpc_EnemyShot(origin, v, DefIndex);
                    }
                    break;
                case EnemyAttack.Stomp:
                case EnemyAttack.Explode:
                    if (dist <= Def.attackDistance)
                    {
                        _specialTimer = Def.specialCooldown;
                        _telegraphing = true;
                        _telegraphLeft = Def.telegraphTime;
                        TelegraphTick = Runner.Tick;
                        float r = Def.specialRadius * Mathf.Sqrt(ScaleMul);
                        gm.Rpc_Telegraph(new Vector3(pos.x, _groundY, pos.z), r, Def.telegraphTime, DefIndex);
                    }
                    break;
            }
        }

        void ReleaseSpecial(Vector3 pos)
        {
            var gm = GameManager.Instance;
            float r = Def.specialRadius * Mathf.Sqrt(ScaleMul);
            float dmg = ContactDamage * Def.specialDamageMul;
            foreach (var p in PlayerCharacter.All)
            {
                if (p == null || !p.IsAlive) continue;
                var d = p.transform.position - pos;
                if (Mathf.Abs(d.y) > 2.5f) continue; // jumped over the shockwave!
                d.y = 0;
                if (d.magnitude <= r) p.TakeDamage(dmg);
            }
            gm?.Rpc_Blast(new Vector3(pos.x, _groundY, pos.z), r, DefIndex, Def.attack == EnemyAttack.Explode);
            AttackTick = Runner.Tick;
            if (Def.attack == EnemyAttack.Explode)
            {
                // self-destruct: no loot, just a boom
                Health = 0f;
                Runner.Despawn(Object);
            }
        }

        // ------------------------------------------------------------------ status effects (host)

        [Networked] public TickTimer SlowTimer { get; set; }
        [Networked] public int TelegraphTick { get; set; }
        public bool IsSlowed => SlowTimer.IsRunning && !SlowTimer.Expired(Runner);

        public void ApplySlow(float seconds)
        {
            if (!HasStateAuthority || Boss) return;
            SlowTimer = TickTimer.CreateFromSeconds(Runner, seconds);
        }

        /// <summary>Host only.</summary>
        public void TakeDamage(float amount, Vector3 from, float knockback, PlayerCharacter source)
        {
            if (!HasStateAuthority || !IsAlive) return;
            if (WeaponSystem.PendingCrit) CritCount++;
            WeaponSystem.PendingCrit = false;
            Health -= amount;
            if (source != null && source.Data != null) source.Data.DamageDealt += amount;
            if (source != null)
            {
                float ls = source.Stats.Lifesteal;
                if (ls > 0f) source.Heal(Mathf.Min(amount, Mathf.Max(0f, Health + amount)) * ls);
            }

            var d = transform.position - from;
            d.y = 0;
            if (d.sqrMagnitude > 0.0001f)
            {
                float k = knockback * (1f - Def.knockbackResist) * (Boss ? 0f : Elite ? 0.25f : 1f);
                _knock += d.normalized * k;
                if (_knock.magnitude > 14f) _knock = _knock.normalized * 14f;
            }

            if (Health <= 0f)
            {
                Health = 0f;
                GameManager.Instance?.OnEnemyKilled(this, source);
                Runner.Despawn(Object);
            }
        }

        // ------------------------------------------------------------------ visuals (every peer)

        public override void Render()
        {
            PerfStats.EnemyRender.Start();
            try { RenderVisuals(); }
            finally { PerfStats.EnemyRender.Stop(); }
        }

        void RenderVisuals()
        {
            if (Def == null) return;
            float h = Health;
            if (h < _lastHealth - 0.01f)
            {
                float dmg = _lastHealth - h;
                _flash = 0.12f;
                bool crit = CritCount != _lastCrit;
                _lastCrit = CritCount;
                FxManager.Instance?.DamageNumber(transform.position + Vector3.up * (1.9f * ScaleMul), dmg, false, crit);
                FxManager.Instance?.HitSpark(transform.position + Vector3.up * (0.9f * ScaleMul), crit);
                if (Def.hitSound != null) AudioManager.Play(Def.hitSound, transform.position, 0.45f);
                _rig?.Hit();
            }
            _lastHealth = h;

            if (AttackTick != _lastAttackTick)
            {
                _lastAttackTick = AttackTick;
                _rig?.Attack();
            }

            if (_crown != null) _crown.localRotation = Quaternion.Euler(0, Time.time * 90f, 0);
            if (_flash > 0f) _flash -= Time.deltaTime;
            // windup pulse for stomps / explosions (faster as it gets close to going off)
            float windup = 0f;
            if (Def.attack is EnemyAttack.Stomp or EnemyAttack.Explode && TelegraphTick > 0)
            {
                float since = (Runner.Tick - TelegraphTick) * Runner.DeltaTime;
                if (since < Def.telegraphTime)
                {
                    float k = since / Def.telegraphTime;
                    windup = (0.5f + 0.5f * Mathf.Sin(since * (10f + 30f * k))) * (0.4f + 0.6f * k);
                    if (_rig != null) transform.localScale = Vector3.one * ScaleMul * _baseScale * (1f + k * 0.15f);
                }
                else if (transform.localScale.x != ScaleMul * _baseScale) transform.localScale = Vector3.one * ScaleMul * _baseScale;
            }
            ApplyTint(Mathf.Clamp01(_flash / 0.12f), windup, IsSlowed);

            if (_rig != null)
            {
                var p = transform.position;
                var v = (p - _lastPos) / Mathf.Max(Time.deltaTime, 0.0001f);
                v.y = 0;
                _rig.SetMotion(v.magnitude, Def.movement == EnemyMovement.Hopper && (p.y - _lastPos.y) > 0.001f);
                _lastPos = p;
            }
        }

        bool _tinted;

        void ApplyTint(float flash, float windup = 0f, bool slowed = false)
        {
            if (_renderers == null) return;
            if (flash <= 0f && !Elite && windup <= 0f && !slowed)
            {
                // no override needed: drop the property block so the SRP batcher can batch this enemy
                if (_tinted)
                {
                    foreach (var r in _renderers) if (r != null) r.SetPropertyBlock(null);
                    _tinted = false;
                }
                return;
            }
            _tinted = true;
            var baseColor = Elite ? new Color(1f, 0.9f, 0.72f) : Color.white;
            if (slowed) baseColor *= new Color(0.6f, 0.85f, 1.3f);
            var emission = Color.white * (flash * 2.5f) + (Elite ? new Color(0.14f, 0.09f, 0.02f) : Color.black)
                           + new Color(1f, 0.15f, 0.05f) * windup * 1.6f + (slowed ? new Color(0.05f, 0.15f, 0.3f) : Color.black);
            foreach (var r in _renderers)
            {
                if (r == null) continue;
                r.GetPropertyBlock(_mpb);
                _mpb.SetColor(BaseColorId, baseColor);
                _mpb.SetColor(EmissionId, emission);
                r.SetPropertyBlock(_mpb);
            }
        }
    }
}
