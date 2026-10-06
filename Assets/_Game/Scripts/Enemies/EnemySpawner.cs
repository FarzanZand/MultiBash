using System.Collections.Generic;
using UnityEngine;

namespace MultiBash
{
    /// <summary>Host-side: turns the WaveDefinition timeline into enemies around the players.</summary>
    public class EnemySpawner
    {
        readonly GameManager _gm;
        readonly Dictionary<WaveEntry, float> _accumulators = new();
        readonly HashSet<WaveBurst> _doneBursts = new();
        static readonly List<PlayerCharacter> Alive = new();

        public EnemySpawner(GameManager gm) => _gm = gm;

        public void Tick(float dt)
        {
            var cfg = GameDatabase.Config;
            var waves = _gm.Waves;
            if (waves == null) return;

            Alive.Clear();
            foreach (var p in PlayerCharacter.All) if (p != null && p.IsAlive) Alive.Add(p);
            if (Alive.Count == 0) return;

            float minute = _gm.RunTime / 60f;
            int players = Mathf.Max(1, PlayerCharacter.All.Count);
            float playerMul = 1f + ProgressionManager.Settings.spawnRatePerExtraPlayer * (players - 1);

            foreach (var entry in waves.entries)
            {
                if (entry.enemy == null || minute < entry.startMinute || minute >= entry.endMinute) continue;
                float span = Mathf.Max(0.01f, entry.endMinute - entry.startMinute);
                float t = Mathf.Pow(Mathf.Clamp01((minute - entry.startMinute) / span), Mathf.Max(0.1f, entry.rampCurve));
                float rate = Mathf.Lerp(entry.rateAtStart, entry.rateAtEnd, t) * playerMul * ProgressionManager.Settings.spawnRateMultiplier;
                _accumulators.TryGetValue(entry, out float acc);
                acc += rate * dt;
                while (acc >= 1f)
                {
                    acc -= 1f;
                    if (EnemyRegistry.All.Count >= ProgressionManager.Settings.maxEnemies) { acc = 0f; break; }
                    SpawnGroup(entry.enemy, Mathf.Max(1, entry.groupSize), entry.eliteChance);
                }
                _accumulators[entry] = acc;
            }

            foreach (var b in waves.bursts)
            {
                if (b.enemy == null || _doneBursts.Contains(b) || minute < b.minute) continue;
                _doneBursts.Add(b);
                if (minute - b.minute > 0.25f && !b.boss) continue; // long missed (e.g. time skip): don't dump it all at once
                DoBurst(b);
            }
        }

        void SpawnGroup(EnemyDefinition def, int size, float eliteChance)
        {
            var anchor = Alive[Random.Range(0, Alive.Count)];
            var center = PickSpawnPoint(anchor.transform.position);
            for (int i = 0; i < size; i++)
            {
                if (EnemyRegistry.All.Count >= ProgressionManager.Settings.maxEnemies) return;
                var p = center + new Vector3(Random.Range(-2f, 2f), 0, Random.Range(-2f, 2f));
                _gm.SpawnEnemy(def, ClampArena(p), Random.value < eliteChance);
            }
        }

        void DoBurst(WaveBurst b)
        {
            if (!string.IsNullOrEmpty(b.announcement)) _gm.Announce(b.announcement);
            if (b.boss)
            {
                var anchor0 = Alive[Random.Range(0, Alive.Count)];
                var a = Random.Range(0f, Mathf.PI * 2f);
                var p0 = ClampArena(anchor0.transform.position + new Vector3(Mathf.Cos(a), 0, Mathf.Sin(a)) * 16f);
                _gm.SpawnEnemy(b.enemy, p0, true, true);
                _gm.Rpc_BossSpawned(p0);
                return;
            }
            int elitesLeft = b.elites;
            int total = Mathf.Max(1, Mathf.RoundToInt(b.count * ProgressionManager.Settings.burstSizeMultiplier));
            if (total >= ProgressionManager.Settings.hordeShakeThreshold) _gm.Rpc_Horde(total);
            foreach (var anchor in Alive)
            {
                int count = Mathf.CeilToInt(total / (float)Alive.Count);
                var c = anchor.transform.position;
                for (int i = 0; i < count; i++)
                {
                    if (EnemyRegistry.All.Count >= ProgressionManager.Settings.maxEnemies) return;
                    Vector3 p;
                    if (b.ring)
                    {
                        float a = i / (float)count * Mathf.PI * 2f;
                        float d = Random.Range(14f, 17f);
                        p = c + new Vector3(Mathf.Cos(a), 0, Mathf.Sin(a)) * d;
                    }
                    else p = PickSpawnPoint(c) + new Vector3(Random.Range(-3f, 3f), 0, Random.Range(-3f, 3f));
                    bool elite = elitesLeft > 0 && i == 0;
                    if (elite) elitesLeft--;
                    _gm.SpawnEnemy(b.enemy, ClampArena(p), elite);
                }
            }
        }

        static Vector3 PickSpawnPoint(Vector3 around)
        {
            var cfg = GameDatabase.Config;
            Vector3 best = around;
            float bestScore = -1f;
            for (int tries = 0; tries < 6; tries++)
            {
                float a = Random.Range(0f, Mathf.PI * 2f);
                float d = Random.Range(ProgressionManager.Settings.spawnDistanceMin, ProgressionManager.Settings.spawnDistanceMax);
                var p = ClampArena(around + new Vector3(Mathf.Cos(a), 0, Mathf.Sin(a)) * d);
                // prefer points that stayed far from every player after clamping to the arena
                float minDist = float.MaxValue;
                foreach (var pl in Alive) minDist = Mathf.Min(minDist, (pl.transform.position - p).magnitude);
                if (minDist > bestScore) { bestScore = minDist; best = p; }
                if (minDist >= ProgressionManager.Settings.spawnDistanceMin * 0.8f) break;
            }
            return best;
        }

        static Vector3 ClampArena(Vector3 p)
        {
            float h = GameDatabase.Config.arenaHalfSize - 1f;
            p.x = Mathf.Clamp(p.x, -h, h);
            p.z = Mathf.Clamp(p.z, -h, h);
            p.y = Ground.Height(p);
            return p;
        }
    }
}
