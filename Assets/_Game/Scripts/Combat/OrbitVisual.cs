using System.Collections.Generic;
using UnityEngine;

namespace MultiBash
{
    /// <summary>Draws orbiting blades around a player on every peer (host does the damage in WeaponSystem).</summary>
    public class OrbitVisual : MonoBehaviour
    {
        public PlayerCharacter Owner;
        readonly List<Transform> _blades = new();
        int _weaponIndex = -2;

        public static float AngleAt(float time, float degreesPerSecond) => time * degreesPerSecond % 360f;

        void LateUpdate()
        {
            if (Owner == null || Owner.Object == null || !Owner.Object.IsValid) return;
            var db = GameDatabase.Instance;
            int level = 0;
            WeaponDefinition def = null;
            for (int i = 0; i < db.weapons.Count; i++)
            {
                if (db.weapons[i].kind != WeaponKind.Orbit) continue;
                level = Owner.WeaponLevelOf(i);
                if (level > 0) { def = db.weapons[i]; break; }
            }

            var stats = Owner.Stats;
            int count = def == null || Owner.Dead ? 0 : Mathf.Max(1, def.GetLevel(level).amount + stats.ProjectileCount);
            while (_blades.Count < count) _blades.Add(CreateBlade(def));
            for (int i = 0; i < _blades.Count; i++) _blades[i].gameObject.SetActive(i < count);
            if (count == 0) return;

            var lvl = def.GetLevel(level);
            float radius = lvl.area * stats.Area;
            float time = Owner.Runner != null ? Owner.Runner.LocalRenderTime : Time.time;
            float a0 = AngleAt(time, lvl.speed * stats.ProjectileSpeed);
            var c = Owner.transform.position + Vector3.up * 0.9f;
            float scale = Mathf.Sqrt(stats.Area) * 1.6f;
            for (int i = 0; i < count; i++)
            {
                float a = (a0 + i * 360f / count) * Mathf.Deg2Rad;
                var dir = new Vector3(Mathf.Cos(a), 0, Mathf.Sin(a));
                var t = _blades[i];
                t.position = c + dir * radius;
                // blade points along its travel direction and spins
                var tangent = new Vector3(-dir.z, 0, dir.x);
                t.rotation = Quaternion.LookRotation(tangent) * Quaternion.Euler(0, Time.time * 720f % 360f, 0);
                t.localScale = Vector3.one * scale;
            }
        }

        Transform CreateBlade(WeaponDefinition def)
        {
            GameObject go;
            if (def != null && def.projectileModel != null) go = Instantiate(def.projectileModel);
            else
            {
                go = GameObject.CreatePrimitive(PrimitiveType.Cube);
                Destroy(go.GetComponent<Collider>());
                go.transform.localScale = new Vector3(0.1f, 0.05f, 0.5f);
            }
            go.name = "OrbitBlade";
            go.transform.SetParent(transform, true);
            FxManager.Instance?.AttachTrail(go.transform, def != null ? def.fxColor : Color.white, 0.18f);
            return go.transform;
        }

        void OnDestroy()
        {
            foreach (var b in _blades) if (b != null) Destroy(b.gameObject);
        }
    }
}
