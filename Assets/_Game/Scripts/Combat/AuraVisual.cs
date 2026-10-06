using UnityEngine;

namespace MultiBash
{
    /// <summary>Glowing ring under a player who owns an Aura weapon. Pulses when the host deals aura damage.</summary>
    public class AuraVisual : MonoBehaviour
    {
        public PlayerCharacter Owner;
        Transform _ring;
        Renderer _renderer;
        readonly System.Collections.Generic.List<(Transform t, Renderer r)> _extra = new();
        MaterialPropertyBlock _mpb;
        float _pulse, _groundY, _nextGround;
        static readonly int ColorId = Shader.PropertyToID("_Color");

        public void Pulse() => _pulse = 1f;

        void LateUpdate()
        {
            if (Owner == null || Owner.Object == null || !Owner.Object.IsValid) return;
            var db = GameDatabase.Instance;
            WeaponDefinition def = null;
            int level = 0;
            for (int i = 0; i < db.weapons.Count; i++)
            {
                if (db.weapons[i].kind != WeaponKind.Aura) continue;
                level = Owner.WeaponLevelOf(i);
                if (level > 0) { def = db.weapons[i]; break; }
            }

            bool show = def != null && Owner.IsAlive;
            if (!show)
            {
                if (_ring != null) _ring.gameObject.SetActive(false);
                foreach (var e in _extra) e.t.gameObject.SetActive(false);
                return;
            }
            if (_ring == null)
            {
                _ring = FxManager.Instance != null ? FxManager.Instance.CreateGroundDecal("AuraRing", FxManager.Instance.auraTexture != null ? FxManager.Instance.auraTexture : FxManager.Instance.ringTexture, true) : null;
                if (_ring == null) return;
                _renderer = _ring.GetComponent<Renderer>();
                _mpb = new MaterialPropertyBlock();
            }
            _ring.gameObject.SetActive(true);
            float radius = def.GetLevel(level).area * Owner.Stats.Area;
            _pulse = Mathf.MoveTowards(_pulse, 0f, Time.deltaTime * 3f);
            var op = Owner.transform.position;
            // sit on the highest ground under the circle (re-sampled a few times a second): slopes don't eat it
            if (Time.time >= _nextGround) { _nextGround = Time.time + 0.15f; _groundY = Ground.Cover(op, radius); }
            _ring.position = new Vector3(op.x, _groundY, op.z);
            _ring.localScale = Vector3.one * radius * 2f * (1f + _pulse * 0.08f);
            _ring.Rotate(0, 40f * Time.deltaTime, 0, Space.World);
            var c = def.fxColor;
            c.a = 0.55f + _pulse * 0.4f;
            _renderer.GetPropertyBlock(_mpb);   // keep the decal's texture: SetPropertyBlock replaces the whole block
            _mpb.SetColor(ColorId, c);
            _renderer.SetPropertyBlock(_mpb);

            // extra halos for extra rings (weapon levels + Multishot), counter-rotating, a bit fainter
            int rings = Mathf.Max(1, def.GetLevel(level).amount + Owner.Stats.ProjectileCount);
            while (_extra.Count < rings - 1)
            {
                var fx = FxManager.Instance;
                var t = fx.CreateGroundDecal("AuraRingX", fx.thinRingTexture != null ? fx.thinRingTexture : fx.ringTexture, true);
                _extra.Add((t, t.GetComponent<Renderer>()));
            }
            for (int k = 0; k < _extra.Count; k++)
            {
                var (t, r) = _extra[k];
                bool on = k < rings - 1;
                t.gameObject.SetActive(on);
                if (!on) continue;
                float rr = radius * (1f + 0.45f * (k + 1));
                t.position = new Vector3(op.x, _groundY + 0.01f * (k + 1), op.z);
                t.localScale = Vector3.one * rr * 2f * (1f + _pulse * 0.06f);
                t.Rotate(0, (k % 2 == 0 ? -55f : 35f) * Time.deltaTime, 0, Space.World);
                var ce = Color.Lerp(def.fxColor, Color.white, 0.2f);
                ce.a = 0.4f + _pulse * 0.3f;
                r.GetPropertyBlock(_mpb);
                _mpb.SetColor(ColorId, ce);
                r.SetPropertyBlock(_mpb);
            }
        }

        void OnDestroy()
        {
            if (_ring != null) Destroy(_ring.gameObject);
            foreach (var e in _extra) if (e.t != null) Destroy(e.t.gameObject);
        }
    }
}
