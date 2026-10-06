using System.Collections.Generic;
using Fusion;
using UnityEngine;

namespace MultiBash
{
    public enum PickupKind : byte
    {
        XP,
        Health,
        Magnet,
        Chest,
    }

    /// <summary>
    /// XP gems, health orbs, magnets and chests. They sit still until a living player gets within their
    /// pickup radius, then fly to that player (host moves them, NetworkTransform syncs).
    /// XP gems show a different model per value tier: children named Tier0 / Tier1 / Tier2.
    /// </summary>
    [RequireComponent(typeof(NetworkTransform))]
    public class Pickup : NetworkBehaviour
    {
        public static readonly List<Pickup> All = new();

        [Networked] public PickupKind Kind { get; set; }
        [Networked] public int Value { get; set; }
        [Networked] public NetworkId Target { get; set; }

        [Tooltip("Value needed to show Tier1 / Tier2 models.")]
        public int tier1Value = 5;
        public int tier2Value = 25;
        public Transform visual;

        float _speed;
        int _shownTier = -1;
        float _bobSeed;

        public static void SpawnXP(NetworkRunner runner, Vector3 pos, int value)
        {
            var cfg = GameDatabase.Config;
            int gems = 0;
            foreach (var p in All) if (p.Kind == PickupKind.XP) gems++;
            if (gems >= cfg.maxGems)
            {
                // too many gems on the map: merge into the oldest idle one
                foreach (var p in All)
                {
                    if (p.Kind != PickupKind.XP || p.Target.IsValid) continue;
                    p.Value += value;
                    return;
                }
            }
            Spawn(runner, cfg.xpGemPrefab, pos, PickupKind.XP, value);
        }

        public static void Spawn(NetworkRunner runner, NetworkObject prefab, Vector3 pos, PickupKind kind, int value)
        {
            if (prefab == null) return;
            pos.y += 0.4f;
            runner.Spawn(prefab, pos, Quaternion.Euler(0, Random.Range(0, 360f), 0), null, (r, o) =>
            {
                var p = o.GetComponent<Pickup>();
                p.Kind = kind;
                p.Value = value;
            });
        }

        public override void Spawned()
        {
            All.Add(this);
            _bobSeed = Random.value * 10f;
            if (visual == null && transform.childCount > 0) visual = transform.GetChild(0);
            if (FxManager.Instance != null && visual != null)
                _glow = FxManager.Instance.AttachGlow(visual, GlowColor(0), Kind == PickupKind.Chest ? 2.6f : Kind == PickupKind.XP ? 0.85f : 1.6f);
        }

        Renderer _glow;

        Color GlowColor(int tier) => Kind switch
        {
            PickupKind.Health => new Color(1f, 0.3f, 0.4f, 0.8f),
            PickupKind.Magnet => new Color(1f, 0.4f, 0.4f, 0.8f),
            PickupKind.Chest => new Color(1f, 0.8f, 0.3f, 0.9f),
            _ => tier switch
            {
                2 => new Color(0.8f, 0.35f, 1f, 0.45f),
                1 => new Color(0.35f, 1f, 0.5f, 0.35f),
                _ => new Color(0.3f, 0.75f, 1f, 0.32f),
            },
        };

        public override void Despawned(NetworkRunner runner, bool hasState) => All.Remove(this);

        PlayerCharacter TargetCharacter
        {
            get
            {
                if (!Target.IsValid) return null;
                var obj = Runner.FindObject(Target);
                return obj != null ? obj.GetComponent<PlayerCharacter>() : null;
            }
        }

        public override void FixedUpdateNetwork()
        {
            if (!HasStateAuthority) return;
            var gm = GameManager.Instance;
            if (gm == null || gm.State != RunState.Playing) return;
            float dt = Runner.DeltaTime;

            var target = TargetCharacter;
            if (target != null && !target.IsAlive)
            {
                Target = default;
                target = null;
            }

            if (target == null)
            {
                float best = float.MaxValue;
                foreach (var p in PlayerCharacter.All)
                {
                    if (p == null || !p.IsAlive) continue;
                    float radius = Kind == PickupKind.Chest ? 1.8f : Kind == PickupKind.XP ? p.Stats.PickupRadius : 2.2f;
                    float d = (p.transform.position - transform.position).sqrMagnitude;
                    if (d <= radius * radius && d < best)
                    {
                        best = d;
                        target = p;
                    }
                }
                if (target == null) return;
                Target = target.Object.Id;
                _speed = -4f; // small hop away first, like a vacuum pop
            }

            var to = target.transform.position + Vector3.up * 0.8f - transform.position;
            float dist = to.magnitude;
            _speed = Mathf.Min(_speed + 45f * dt, 35f);
            if (dist < 0.8f || (_speed > 0f && _speed * dt >= dist))
            {
                Collect(target);
                return;
            }
            transform.position += to / dist * _speed * dt;
        }

        void Collect(PlayerCharacter p)
        {
            var gm = GameManager.Instance;
            var cfg = GameDatabase.Config;
            switch (Kind)
            {
                case PickupKind.XP:
                    gm.AddXP(Value * p.Stats.XPGain);
                    break;
                case PickupKind.Health:
                    p.Heal(p.Stats.MaxHealth * cfg.healthOrbHeal);
                    break;
                case PickupKind.Magnet:
                    foreach (var g in All)
                        if (g.Kind == PickupKind.XP && !g.Target.IsValid) g.Target = p.Object.Id;
                    break;
                case PickupKind.Chest:
                    p.PendingLevelUps++;
                    break;
            }
            gm.Rpc_PickupFx((byte)Kind, transform.position, p.Object.InputAuthority);
            Runner.Despawn(Object);
        }

        public override void Render()
        {
            if (visual == null) return;
            if (Kind == PickupKind.XP)
            {
                int tier = Value >= tier2Value ? 2 : Value >= tier1Value ? 1 : 0;
                if (tier != _shownTier)
                {
                    _shownTier = tier;
                    if (_glow != null) FxManager.Instance?.SetColor(_glow, GlowColor(tier));
                    for (int i = 0; i < visual.childCount; i++)
                    {
                        var c = visual.GetChild(i);
                        if (c.name.StartsWith("Tier")) c.gameObject.SetActive(c.name == "Tier" + tier);
                    }
                }
            }
            float t = Time.time + _bobSeed;
            bool flying = Target.IsValid;
            visual.localPosition = flying ? Vector3.zero : Vector3.up * (Mathf.Sin(t * 3f) * 0.12f);
            float spin = Kind == PickupKind.Chest ? 0f : 90f;
            visual.localRotation = Quaternion.Euler(0, t * spin, 0);
        }
    }
}
