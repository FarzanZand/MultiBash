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

        public static Vector3 Snap(Vector3 p, float offset = 0f)
        {
            p.y = Height(p) + offset;
            return p;
        }
    }
}
