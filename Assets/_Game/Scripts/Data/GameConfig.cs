using Fusion;
using UnityEngine;

namespace MultiBash
{
    /// <summary>
    /// Shared CONTENT references for every run (default waves, pickup prefabs, gear models, arena size).
    /// All tuning numbers live in ProgressionSettings and CombatSettings (edit them on the ProgressionManager /
    /// CombatManager objects in a game scene). One asset: Content/GameConfig.
    /// </summary>
    [CreateAssetMenu(menuName = "MultiBash/Game Config", fileName = "GameConfig", order = 10)]
    public class GameConfig : ScriptableObject
    {
        [Header("Run")]
        [Tooltip("Fallback wave timeline (maps normally bring their own).")]
        public WaveDefinition waves;

        [Header("Arena")]
        public float arenaHalfSize = 58f;

        [Header("Enemy visuals")]
        [Tooltip("Floating crown shown over elites and bosses.")]
        public GameObject eliteCrown;
        [Tooltip("Gear worn by stage 2 (index 0) and stage 3 (index 1) enemies.")]
        public GameObject[] stageGear;

        [Header("Pickups")]
        public NetworkObject xpGemPrefab;
        public NetworkObject healthOrbPrefab;
        public NetworkObject magnetPrefab;
        public NetworkObject chestPrefab;
        [Tooltip("Plain chest model for the opening animation, and the loot it sprays out.")]
        public GameObject chestModel;
        public GameObject[] chestLoot;
    }
}
