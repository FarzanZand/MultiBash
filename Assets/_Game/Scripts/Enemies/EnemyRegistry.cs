using System.Collections.Generic;
using UnityEngine;

namespace MultiBash
{
    /// <summary>
    /// All live enemies + a uniform grid for fast "who is near this point" queries (host side).
    /// Weapons and enemy separation use this instead of physics colliders.
    /// </summary>
    public static class EnemyRegistry
    {
        public static readonly List<Enemy> All = new();

        const float CellSize = 2f;
        static readonly Dictionary<long, List<Enemy>> Grid = new();
        static readonly Stack<List<Enemy>> ListPool = new();
        static int _builtFrame = -1;
        static int _builtTick = -1;

        public static void Register(Enemy e) { if (!All.Contains(e)) All.Add(e); }
        public static void Unregister(Enemy e) => All.Remove(e);

        static long Key(int x, int z) => ((long)x << 32) ^ (uint)z;

        /// <summary>Rebuild the grid once per simulation tick.</summary>
        public static void EnsureGrid(int tick)
        {
            if (tick == _builtTick && Time.frameCount == _builtFrame) return;
            _builtTick = tick;
            _builtFrame = Time.frameCount;
            foreach (var kv in Grid) { kv.Value.Clear(); ListPool.Push(kv.Value); }
            Grid.Clear();
            foreach (var e in All)
            {
                if (e == null || !e.IsAlive) continue;
                var p = e.transform.position;
                long k = Key(Mathf.FloorToInt(p.x / CellSize), Mathf.FloorToInt(p.z / CellSize));
                if (!Grid.TryGetValue(k, out var list))
                {
                    list = ListPool.Count > 0 ? ListPool.Pop() : new List<Enemy>(8);
                    Grid[k] = list;
                }
                list.Add(e);
            }
        }

        /// <summary>Enemies whose center is within radius (+ their own radius) of pos, on the XZ plane.</summary>
        public static void Query(Vector3 pos, float radius, List<Enemy> results) => Query(pos, radius, results, int.MaxValue);

        /// <summary>Same as Query but stops after maxResults (used for crowd separation so dense blobs stay cheap).</summary>
        public static void Query(Vector3 pos, float radius, List<Enemy> results, int maxResults)
        {
            results.Clear();
            int r = Mathf.CeilToInt((radius + 1f) / CellSize);
            int cx = Mathf.FloorToInt(pos.x / CellSize), cz = Mathf.FloorToInt(pos.z / CellSize);
            for (int x = cx - r; x <= cx + r; x++)
            for (int z = cz - r; z <= cz + r; z++)
            {
                if (!Grid.TryGetValue(Key(x, z), out var list)) continue;
                foreach (var e in list)
                {
                    if (e == null || !e.IsAlive) continue;
                    var d = e.transform.position - pos;
                    d.y = 0;
                    float rr = radius + e.Radius;
                    if (d.sqrMagnitude <= rr * rr)
                    {
                        results.Add(e);
                        if (results.Count >= maxResults) return;
                    }
                }
            }
        }

        public static Enemy Nearest(Vector3 pos, float maxRange, HashSet<Enemy> exclude = null)
        {
            Enemy best = null;
            float bestD = maxRange * maxRange;
            // Small ranges: use the grid. Large: scan all (still cheap with ~200 enemies).
            foreach (var e in All)
            {
                if (e == null || !e.IsAlive) continue;
                if (exclude != null && exclude.Contains(e)) continue;
                var d = e.transform.position - pos;
                d.y = 0;
                float sq = d.sqrMagnitude;
                if (sq < bestD) { bestD = sq; best = e; }
            }
            return best;
        }

        public static void NearestN(Vector3 pos, float maxRange, int n, List<Enemy> results)
        {
            results.Clear();
            float max = maxRange * maxRange;
            foreach (var e in All)
            {
                if (e == null || !e.IsAlive) continue;
                var d = e.transform.position - pos;
                d.y = 0;
                if (d.sqrMagnitude <= max) results.Add(e);
            }
            results.Sort((a, b) =>
            {
                var da = a.transform.position - pos;
                var dbb = b.transform.position - pos;
                return da.sqrMagnitude.CompareTo(dbb.sqrMagnitude);
            });
            if (results.Count > n) results.RemoveRange(n, results.Count - n);
        }
    }
}
