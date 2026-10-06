using UnityEngine;

namespace MultiBash
{
    /// <summary>Glowing ring under a player who owns an Aura weapon. Pulses when the host deals aura damage.</summary>
    public class AuraVisual : MonoBehaviour
    {
        public PlayerCharacter Owner;
        Transform _ring;
        Renderer _renderer;
        MaterialPropertyBlock _mpb;
        float _pulse;
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
                return;
            }
            if (_ring == null)
            {
                _ring = FxManager.Instance != null ? FxManager.Instance.CreateGroundDecal("AuraRing", FxManager.Instance.ringTexture, true) : null;
                if (_ring == null) return;
                _renderer = _ring.GetComponent<Renderer>();
                _mpb = new MaterialPropertyBlock();
            }
            _ring.gameObject.SetActive(true);
            float radius = def.GetLevel(level).area * Owner.Stats.Area;
            _pulse = Mathf.MoveTowards(_pulse, 0f, Time.deltaTime * 3f);
            _ring.position = Owner.transform.position + Vector3.up * 0.06f;
            _ring.localScale = Vector3.one * radius * 2f * (1f + _pulse * 0.08f);
            _ring.Rotate(0, 40f * Time.deltaTime, 0, Space.World);
            var c = def.fxColor;
            c.a = 0.45f + _pulse * 0.5f;
            _mpb.SetColor(ColorId, c);
            _renderer.SetPropertyBlock(_mpb);
        }

        void OnDestroy()
        {
            if (_ring != null) Destroy(_ring.gameObject);
        }
    }
}
