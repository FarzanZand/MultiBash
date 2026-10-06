using System.Collections.Generic;
using UnityEngine;

namespace MultiBash
{
    /// <summary>
    /// Static props register a circle so enemies walk around them (enemies don't use physics).
    /// Obstacles are static, so they're bucketed into a grid once; enemies only check nearby cells.
    /// </summary>
    public class Obstacle : MonoBehaviour
    {
        public static readonly List<Obstacle> All = new();
        public float radius = 1f;

        const float Cell = 4f;
        static readonly Dictionary<long, List<Obstacle>> Grid = new();
        static bool _dirty = true;
        static readonly List<Obstacle> Empty = new();

        public float WorldRadius => radius * transform.lossyScale.x;

        void OnEnable() { All.Add(this); _dirty = true; }
        void OnDisable() { All.Remove(this); _dirty = true; }

        static long Key(int x, int z) => ((long)x << 32) ^ (uint)z;

        static void Rebuild()
        {
            _dirty = false;
            Grid.Clear();
            foreach (var o in All)
            {
                if (o == null) continue;
                var p = o.transform.position;
                float r = o.WorldRadius + 2f; // margin for the enemy's own radius
                int x0 = Mathf.FloorToInt((p.x - r) / Cell), x1 = Mathf.FloorToInt((p.x + r) / Cell);
                int z0 = Mathf.FloorToInt((p.z - r) / Cell), z1 = Mathf.FloorToInt((p.z + r) / Cell);
                for (int x = x0; x <= x1; x++)
                for (int z = z0; z <= z1; z++)
                {
                    long k = Key(x, z);
                    if (!Grid.TryGetValue(k, out var list)) Grid[k] = list = new List<Obstacle>(4);
                    list.Add(o);
                }
            }
        }

        /// <summary>Obstacles whose circle may overlap this point's cell.</summary>
        public static List<Obstacle> Near(Vector3 p)
        {
            if (_dirty) Rebuild();
            return Grid.TryGetValue(Key(Mathf.FloorToInt(p.x / Cell), Mathf.FloorToInt(p.z / Cell)), out var list) ? list : Empty;
        }

        void OnDrawGizmosSelected()
        {
            Gizmos.color = Color.yellow;
            Gizmos.DrawWireSphere(transform.position, WorldRadius);
        }
    }
}
