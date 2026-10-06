using UnityEngine;

namespace MultiBash
{
    /// <summary>Fast ground height queries. Uses the scene's Terrain when there is one, otherwise y = 0.</summary>
    public static class Ground
    {
        static Terrain _terrain;
        static int _frame = -1;

        static Terrain T
        {
            get
            {
                if (_frame != Time.frameCount && (_terrain == null || !_terrain.isActiveAndEnabled))
                {
                    _frame = Time.frameCount;
                    _terrain = Terrain.activeTerrain;
                }
                return _terrain;
            }
        }

        /// <summary>Walkable height for enemies, pickups and spawns: terrain, or the lava surface where the terrain dips below it.</summary>
        public static float Height(Vector3 p)
        {
            float h = TerrainHeight(p);
            return float.IsNaN(LavaZone.Level) ? h : Mathf.Max(h, LavaZone.Level);
        }

        /// <summary>Raw terrain height (ignores lava).</summary>
        public static float TerrainHeight(Vector3 p)
        {
            var t = T;
            return t != null ? t.SampleHeight(p) + t.transform.position.y : 0f;
        }

        /// <summary>Height for a flat ground decal of this radius: the highest ground under it (+ a hair), so slopes
        /// don't swallow half of the circle.</summary>
        public static float Cover(Vector3 p, float radius)
        {
            float h = Height(p);
            for (int i = 0; i < 8; i++)
            {
                float a = i * Mathf.PI * 0.25f;
                var d = new Vector3(Mathf.Cos(a), 0f, Mathf.Sin(a));
                h = Mathf.Max(h, Height(p + d * radius * 0.5f), Height(p + d * radius * 0.95f));
            }
            return h + 0.08f;
        }

        public static Vector3 Snap(Vector3 p, float offset = 0f)
        {
            p.y = Height(p) + offset;
            return p;
        }
    }
}
