using Fusion;
using UnityEngine;

namespace MultiBash
{
    /// <summary>
    /// Charge Shrine: stand inside the circle to charge it. When full, everyone inside gets a free upgrade pick.
    /// Recharges after a cooldown. Placed in the Game scene (scene NetworkObject); host simulates.
    /// </summary>
    [RequireComponent(typeof(NetworkObject))]
    public class Shrine : NetworkBehaviour
    {
        public float radius = 3.2f;
        public float chargeSeconds = 4.5f;
        public float cooldownSeconds = 75f;
        public Transform crystal;
        public Color readyColor = new(0.35f, 0.8f, 1f);

        [Networked] public float Progress { get; set; }
        [Networked] public TickTimer Cooldown { get; set; }
        [Networked] public int CompleteTick { get; set; }

        Transform _ring, _fill;
        Renderer _ringR, _fillR;
        MaterialPropertyBlock _mpb;
        int _lastComplete;
        Light _light;
        static readonly int ColorId = Shader.PropertyToID("_Color");

        public bool Ready => Cooldown.ExpiredOrNotRunning(Runner);

        public override void Spawned()
        {
            _lastComplete = CompleteTick;
            _light = GetComponentInChildren<Light>();
        }

        public override void FixedUpdateNetwork()
        {
            if (!HasStateAuthority) return;
            var gm = GameManager.Instance;
            if (gm == null || gm.State != RunState.Playing || !Ready) return;
            float dt = Runner.DeltaTime;
            int inside = 0;
            foreach (var p in PlayerCharacter.All)
                if (p != null && p.IsAlive && Flat(p.transform.position - transform.position) <= radius) inside++;
            // more players = faster charge (co-op bonus)
            Progress = inside > 0 ? Progress + dt / chargeSeconds * (1f + 0.35f * (inside - 1)) : Mathf.Max(0f, Progress - dt / chargeSeconds * 0.6f);
            if (Progress >= 1f)
            {
                Progress = 0f;
                Cooldown = TickTimer.CreateFromSeconds(Runner, cooldownSeconds);
                CompleteTick = Runner.Tick;
                foreach (var p in PlayerCharacter.All)
                    if (p != null && p.IsAlive && Flat(p.transform.position - transform.position) <= radius) p.PendingLevelUps++;
            }
        }

        static float Flat(Vector3 d)
        {
            d.y = 0;
            return d.magnitude;
        }

        public override void Render()
        {
            var fx = FxManager.Instance;
            if (fx == null) return;
            if (_ring == null)
            {
                _mpb = new MaterialPropertyBlock();
                _ring = fx.CreateGroundDecal("ShrineRing", fx.ringTexture, true);
                _fill = fx.CreateGroundDecal("ShrineFill", fx.softTexture, true);
                _ringR = _ring.GetComponent<Renderer>();
                _fillR = _fill.GetComponent<Renderer>();
            }
            var ground = new Vector3(transform.position.x, Ground.Height(transform.position) + 0.08f, transform.position.z);
            _ring.position = ground;
            _fill.position = ground + Vector3.up * 0.02f;
            bool ready = Ready;
            float pulse = 0.8f + 0.2f * Mathf.Sin(Time.time * 3f);
            _ring.localScale = Vector3.one * radius * 2.3f;
            _ring.Rotate(0, 30f * Time.deltaTime, 0, Space.World);
            _fill.localScale = Vector3.one * radius * 2.6f * Mathf.Max(0.05f, Progress);
            var c = ready ? readyColor : new Color(0.4f, 0.4f, 0.45f);
            c.a = (ready ? 0.8f : 0.3f) * pulse;
            _ringR.GetPropertyBlock(_mpb);
            _mpb.SetColor(ColorId, c);
            _ringR.SetPropertyBlock(_mpb);
            var fc = readyColor;
            fc.a = 0.6f;
            _fillR.GetPropertyBlock(_mpb);
            _mpb.SetColor(ColorId, fc);
            _fillR.SetPropertyBlock(_mpb);
            if (crystal != null)
            {
                crystal.localPosition = new Vector3(0, 2.4f + Mathf.Sin(Time.time * 2f) * 0.15f, 0);
                crystal.Rotate(0, (ready ? 60f + Progress * 400f : 10f) * Time.deltaTime, 0);
                crystal.localScale = Vector3.one * (ready ? 1f + Progress * 0.3f : 0.7f);
            }
            if (_light != null) _light.intensity = ready ? 2f + Progress * 4f : 0.3f;

            if (CompleteTick != _lastComplete)
            {
                _lastComplete = CompleteTick;
                fx.LightPillar(transform.position, readyColor, 16f, 1.4f);
                fx.Burst(transform.position + Vector3.up * 2.4f, readyColor, 40, 9f, 0.4f, 0.9f, 2f, true);
                var lib = AudioManager.Lib;
                if (lib != null) AudioManager.Play(lib.levelUp, transform.position, 1f, 0.9f);
            }
        }

        public override void Despawned(NetworkRunner runner, bool hasState)
        {
            if (_ring != null) Destroy(_ring.gameObject);
            if (_fill != null) Destroy(_fill.gameObject);
        }
    }
}
