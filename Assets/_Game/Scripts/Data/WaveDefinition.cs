using System;
using System.Collections.Generic;
using UnityEngine;

namespace MultiBash
{
    [Serializable]
    public class WaveEntry
    {
        public EnemyDefinition enemy;
        [Tooltip("Run minute this entry starts spawning.")]
        public float startMinute = 0f;
        [Tooltip("Run minute this entry stops spawning.")]
        public float endMinute = 10f;
        [Tooltip("Spawns per second at startMinute.")]
        public float rateAtStart = 0.5f;
        [Tooltip("Spawns per second at endMinute.")]
        public float rateAtEnd = 3f;
        [Tooltip("Ramp shape: 1 = linear, >1 = calm start and steep finish.")]
        public float rampCurve = 1.6f;
        [Tooltip("Enemies spawned together in a clump.")]
        public int groupSize = 1;
        [Range(0f, 1f)] public float eliteChance = 0f;
    }

    [Serializable]
    public class WaveBurst
    {
        [Tooltip("Run minute the burst happens (once).")]
        public float minute = 3f;
        public EnemyDefinition enemy;
        public int count = 30;
        [Tooltip("Spawn as a ring around each player instead of a clump.")]
        public bool ring = true;
        public int elites = 1;
        public string announcement = "A horde approaches!";
        [Tooltip("Spawn ONE boss version of this enemy instead (uses the enemy's boss settings). count/ring/elites are ignored.")]
        public bool boss;
    }

    [CreateAssetMenu(menuName = "MultiBash/Wave Timeline", fileName = "NewWaves", order = 4)]
    public class WaveDefinition : ScriptableObject
    {
        [Tooltip("Continuous spawning rules. Several entries can overlap.")]
        public List<WaveEntry> entries = new();
        [Tooltip("One-off events at specific minutes.")]
        public List<WaveBurst> bursts = new();
    }
}
