using System.Collections.Generic;
using UnityEngine;

namespace MultiBash
{
    /// <summary>
    /// Host-only simulation of short-lived attacks (projectiles, poison puddles).
    /// These are NOT network objects: the host resolves hits, and clients draw matching visuals from RPCs.
    /// Ticked by GameManager.
    /// </summary>
    public static class CombatWorld
    {
        public struct Projectile
        {
            public PlayerCharacter owner;
            public int weapon;
            public Vector3 pos, vel;
            public float life, damage, knockback, radius;
            public int pierce;
            public bool crit;
            public HashSet<Enemy> hit;
            public float turn;          // homing turn rate (deg/s), 0 = straight
            public float outTime;       // boomerang: seconds before it flies back (0 = not a boomerang)
            public float age;
            public bool returning;
            public float slow;          // seconds of slow applied on hit
        }

        /// <summary>Delayed area hit (meteor impact).</summary>
        public struct Blast
        {
            public PlayerCharacter owner;
            public Vector3 pos;
            public float delay, radius, damage, knockback, slow;
            public bool crit;
        }

        static readonly List<Blast> Blasts = new();

        public static void SpawnBlast(Blast b) => Blasts.Add(b);

        public struct Puddle
        {
            public PlayerCharacter owner;
            public int weapon;
            public Vector3 pos;
            public float radius, delay, life, damagePerTick, tickInterval, knockback, tickTimer, slow;
            public bool crit;
        }

        /// <summary>Enemy projectile (e.g. skeleton arrows): hurts players, dodgeable.</summary>
        public struct EnemyShot
        {
            public Vector3 pos, vel;
            public float life, damage, radius;
        }

        static readonly List<EnemyShot> EnemyShots = new();

        public static void SpawnEnemyShot(EnemyShot s) => EnemyShots.Add(s);

        static readonly List<Projectile> Projectiles = new();
        static readonly List<Puddle> Puddles = new();
        static readonly List<Enemy> Hits = new(64);
        static readonly Stack<HashSet<Enemy>> SetPool = new();

        public static void SpawnProjectile(Projectile p)
        {
            p.hit = SetPool.Count > 0 ? SetPool.Pop() : new HashSet<Enemy>();
            p.hit.Clear();
            Projectiles.Add(p);
        }

        public static void SpawnPuddle(Puddle p) => Puddles.Add(p);

        public static void Clear()
        {
            Projectiles.Clear();
            Puddles.Clear();
            EnemyShots.Clear();
            Blasts.Clear();
        }

        public static void Tick(int tick, float dt)
        {
            EnemyRegistry.EnsureGrid(tick);

            for (int i = EnemyShots.Count - 1; i >= 0; i--)
            {
                var s = EnemyShots[i];
                s.life -= dt;
                s.pos += s.vel * dt;
                bool remove = s.life <= 0f || s.pos.y < Ground.Height(s.pos) - 0.2f;
                if (!remove)
                {
                    foreach (var p in PlayerCharacter.All)
                    {
                        if (p == null || !p.IsAlive) continue;
                        var d = p.transform.position + Vector3.up * 1f - s.pos;
                        if (Mathf.Abs(d.y) < 1.2f && d.x * d.x + d.z * d.z < (s.radius + 0.4f) * (s.radius + 0.4f))
                        {
                            p.TakeDamage(s.damage);
                            remove = true;
                            break;
                        }
                    }
                }
                if (remove) EnemyShots.RemoveAt(i);
                else EnemyShots[i] = s;
            }

            for (int i = Projectiles.Count - 1; i >= 0; i--)
            {
                var p = Projectiles[i];
                p.life -= dt;
                p.age += dt;
                if (p.outTime > 0f && p.owner != null && p.age >= p.outTime)
                {
                    // boomerang flies back to its thrower and can hit everything again on the way
                    if (!p.returning) { p.returning = true; p.hit.Clear(); p.pierce = 999; }
                    var back = p.owner.transform.position + Vector3.up - p.pos;
                    p.vel = back.normalized * p.vel.magnitude * 1.15f;
                    p.life = back.sqrMagnitude < 1.2f || p.age > p.outTime * 4f ? 0f : 1f;
                }
                else if (p.turn > 0f)
                {
                    var target = EnemyRegistry.Nearest(p.pos, 18f, p.hit);
                    if (target != null)
                    {
                        var want = (target.transform.position + Vector3.up * 0.8f * target.ScaleMul - p.pos).normalized * p.vel.magnitude;
                        p.vel = Vector3.RotateTowards(p.vel, want, p.turn * Mathf.Deg2Rad * dt, 0f);
                    }
                }
                p.pos += p.vel * dt;
                bool remove = p.life <= 0f || p.owner == null;
                if (!remove)
                {
                    Breakables.HitSphere(p.pos, p.radius);
                    EnemyRegistry.Query(p.pos, p.radius, Hits);
                    foreach (var e in Hits)
                    {
                        if (p.hit.Contains(e)) continue;
                        p.hit.Add(e);
                        WeaponSystem.PendingCrit = p.crit;
                        e.TakeDamage(p.damage, p.pos - p.vel.normalized, p.knockback, p.owner);
                        if (p.slow > 0f) e.ApplySlow(p.slow);
                        p.pierce--;
                        if (p.pierce <= 0) { remove = true; break; }
                    }
                }
                if (remove)
                {
                    SetPool.Push(p.hit);
                    Projectiles.RemoveAt(i);
                }
                else Projectiles[i] = p;
            }

            for (int i = Blasts.Count - 1; i >= 0; i--)
            {
                var b = Blasts[i];
                b.delay -= dt;
                if (b.delay > 0f) { Blasts[i] = b; continue; }
                Blasts.RemoveAt(i);
                if (b.owner == null) continue;
                Breakables.HitSphere(b.pos, b.radius);
                EnemyRegistry.Query(b.pos, b.radius, Hits);
                foreach (var e in Hits)
                {
                    WeaponSystem.PendingCrit = b.crit;
                    e.TakeDamage(b.damage, b.pos, b.knockback, b.owner);
                    if (b.slow > 0f) e.ApplySlow(b.slow);
                }
            }

            for (int i = Puddles.Count - 1; i >= 0; i--)
            {
                var p = Puddles[i];
                if (p.delay > 0f)
                {
                    p.delay -= dt;
                    Puddles[i] = p;
                    continue;
                }
                p.life -= dt;
                p.tickTimer -= dt;
                if (p.tickTimer <= 0f && p.owner != null)
                {
                    p.tickTimer = p.tickInterval;
                    EnemyRegistry.Query(p.pos, p.radius, Hits);
                    foreach (var e in Hits)
                    {
                        WeaponSystem.PendingCrit = p.crit;
                        e.TakeDamage(p.damagePerTick, p.pos, p.knockback, p.owner);
                        if (p.slow > 0f && e.IsAlive) e.ApplySlow(p.slow);
                    }
                }
                if (p.life <= 0f) Puddles.RemoveAt(i);
                else Puddles[i] = p;
            }
        }
    }
}
