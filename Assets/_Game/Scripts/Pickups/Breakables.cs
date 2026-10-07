using System.Collections.Generic;
using Fusion;
using UnityEngine;

namespace MultiBash
{
    /// <summary>
    /// Smashable pots, crates, barrels and ice crates scattered over a map (one scene NetworkObject holds them all).
    /// Children are the visual props, in order. Walk / slide into one or hit it with any attack to smash it: it bursts
    /// into debris and drops loot (gems, sometimes a health orb, a magnet or even a chest). Smashed props grow back later.
    /// The host decides what breaks and what drops; every peer plays the FX from the replicated break ticks.
    /// </summary>
    [RequireComponent(typeof(NetworkObject))]
    public class Breakables : NetworkBehaviour
    {
        public const int Max = 96;
        public static Breakables Instance { get; private set; }

        [Tooltip("Debris colour per child (same order as the children).")]
        public List<Color> colors = new();
        [Tooltip("Seconds until a smashed prop grows back.")]
        public float respawnSeconds = 80f;
        [Tooltip("Touch radius: walking into a prop smashes it (sliding reaches a bit further).")]
        public float touchRadius = 1.15f;
        public AudioClip breakSound;

        [Header("Loot (host)")]
        public int gemsMin = 2, gemsMax = 4;
        public int gemValue = 2;
        [Range(0f, 1f)] public float healthChance = 0.14f;
        [Range(0f, 1f)] public float magnetChance = 0.04f;
        [Range(0f, 1f)] public float chestChance = 0.025f;

        /// <summary>Tick the prop was smashed (0 = intact).</summary>
        [Networked, Capacity(Max)] NetworkArray<int> BrokeTick => default;

        readonly List<Transform> _props = new();
        Vector3[] _pos;
        int[] _seen;
        float[] _grow, _baseScale;

        void Awake()
        {
            _props.Clear();
            foreach (Transform c in transform)
            {
                if (_props.Count >= Max) break;
                _props.Add(c);
            }
            _pos = new Vector3[_props.Count];
            _seen = new int[_props.Count];
            _grow = new float[_props.Count];
            _baseScale = new float[_props.Count];
            for (int i = 0; i < _props.Count; i++) { _pos[i] = _props[i].position; _grow[i] = 1f; _baseScale[i] = Mathf.Max(0.05f, _props[i].localScale.x); }
        }

        public override void Spawned()
        {
            Instance = this;
            for (int i = 0; i < _props.Count; i++)
            {
                _seen[i] = BrokeTick[i];
                _props[i].gameObject.SetActive(_seen[i] == 0);
            }
        }

        public override void Despawned(NetworkRunner runner, bool hasState)
        {
            if (Instance == this) Instance = null;
        }

        /// <summary>Host: smash every intact prop overlapping this sphere (attacks call this).</summary>
        public static void HitSphere(Vector3 center, float radius)
        {
            var b = Instance;
            if (b == null || b.Object == null || !b.HasStateAuthority) return;
            float r2 = (radius + 0.45f) * (radius + 0.45f);
            for (int i = 0; i < b._props.Count; i++)
            {
                if (b.BrokeTick[i] != 0) continue;
                var d = b._pos[i] - center;
                d.y *= 0.5f;
                if (d.sqrMagnitude <= r2) b.Smash(i);
            }
        }

        public override void FixedUpdateNetwork()
        {
            if (!HasStateAuthority) return;
            var gm = GameManager.Instance;
            if (gm == null || gm.State != RunState.Playing) return;
            int respawnTicks = Mathf.RoundToInt(respawnSeconds / Runner.DeltaTime);
            for (int i = 0; i < _props.Count; i++)
            {
                int t = BrokeTick[i];
                if (t != 0)
                {
                    if (Runner.Tick - t > respawnTicks && !PlayerNear(_pos[i], 6f)) BrokeTick.Set(i, 0);
                    continue;
                }
                foreach (var p in PlayerCharacter.All)
                {
                    if (p == null || !p.IsAlive) continue;
                    var d = p.transform.position - _pos[i];
                    float r = p.IsSliding ? touchRadius * 1.7f : touchRadius;
                    if (Mathf.Abs(d.y) < 2.2f && d.x * d.x + d.z * d.z < r * r) { Smash(i); break; }
                }
            }
        }

        static bool PlayerNear(Vector3 pos, float r)
        {
            foreach (var p in PlayerCharacter.All)
                if (p != null && p.IsAlive && (p.transform.position - pos).sqrMagnitude < r * r) return true;
            return false;
        }

        void Smash(int i)
        {
            BrokeTick.Set(i, Mathf.Max(1, Runner.Tick));
            var cfg = GameDatabase.Config;
            var pos = _pos[i];
            Vector3 Off() { var o = Random.insideUnitSphere * 1.1f; o.y = 0; return o; }
            int gems = Random.Range(gemsMin, gemsMax + 1);
            int value = Mathf.Max(1, Mathf.RoundToInt(gemValue * (1f + GameManager.Instance.RunTime / 150f)));
            for (int k = 0; k < gems; k++) Pickup.SpawnXP(Runner, pos + Off(), value);
            float roll = Random.value;
            if (roll < chestChance) Pickup.Spawn(Runner, cfg.chestPrefab, pos + Off(), PickupKind.Chest, 0);
            else if (roll < chestChance + magnetChance) Pickup.Spawn(Runner, cfg.magnetPrefab, pos + Off(), PickupKind.Magnet, 0);
            else if (roll < chestChance + magnetChance + healthChance) Pickup.Spawn(Runner, cfg.healthOrbPrefab, pos + Off(), PickupKind.Health, 0);
        }

        public override void Render()
        {
            var fx = FxManager.Instance;
            for (int i = 0; i < _props.Count; i++)
            {
                int t = BrokeTick[i];
                var prop = _props[i];
                if (t != _seen[i])
                {
                    bool broke = t != 0;
                    _seen[i] = t;
                    if (broke)
                    {
                        prop.gameObject.SetActive(false);
                        var c = i < colors.Count ? colors[i] : new Color(0.75f, 0.45f, 0.25f);
                        if (fx != null)
                        {
                            fx.DeathBurst(_pos[i], c, 1.3f);
                            fx.Burst(_pos[i] + Vector3.up * 0.6f, new Color(1f, 0.9f, 0.5f), 8, 5f, 0.25f, 0.35f, 6f, true);
                        }
                        if (breakSound != null) AudioManager.Play(breakSound, _pos[i], 0.85f, Random.Range(0.9f, 1.15f));
                    }
                    else
                    {
                        prop.gameObject.SetActive(true);
                        _grow[i] = 0f;
                    }
                }
                if (_grow[i] < 1f && prop.gameObject.activeSelf)
                {
                    _grow[i] = Mathf.Min(1f, _grow[i] + Time.deltaTime * 2.5f);
                    float g = _grow[i];
                    float s = g < 0.7f ? Mathf.SmoothStep(0f, 1.15f, g / 0.7f) : Mathf.Lerp(1.15f, 1f, (g - 0.7f) / 0.3f);
                    prop.localScale = Vector3.one * Mathf.Max(0.01f, s) * PropScale(i);
                }
            }
        }

        float PropScale(int i) => _baseScale[i];
    }
}
