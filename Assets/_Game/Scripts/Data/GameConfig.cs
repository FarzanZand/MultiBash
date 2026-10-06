using System.Collections.Generic;
using Fusion;
using UnityEngine;

namespace MultiBash
{
    /// <summary>Global tuning knobs for a run. One asset: Content/GameConfig.</summary>
    [CreateAssetMenu(menuName = "MultiBash/Game Config", fileName = "GameConfig", order = 10)]
    public class GameConfig : ScriptableObject
    {
        [Header("Run")]
        [Tooltip("Survive this long to win.")]
        public float runDurationSeconds = 600f;
        public WaveDefinition waves;
        [Tooltip("Seconds before the host returns everyone to the lobby after a run ends.")]
        public float resultsSeconds = 15f;

        [Header("Player base stats (before character + powerups)")]
        public List<StatModifier> baseStats = new()
        {
            new(StatType.MaxHealth, 100f),
            new(StatType.MoveSpeed, 7f),
            new(StatType.Damage, 1f),
            new(StatType.Area, 1f),
            new(StatType.Cooldown, 1f),
            new(StatType.ProjectileSpeed, 1f),
            new(StatType.Duration, 1f),
            new(StatType.PickupRadius, 3f),
            new(StatType.XPGain, 1f),
        };
        public float jumpImpulse = 8.5f;
        public float slideSpeedMultiplier = 1.9f;
        public float slideDuration = 0.45f;
        public float slideCooldown = 0.8f;

        [Header("Leveling (team XP)")]
        public int xpFirstLevel = 6;
        [Tooltip("Extra XP needed per level.")]
        public int xpPerLevel = 5;
        [Tooltip("Extra XP needed per level squared (keeps late levels slower).")]
        public float xpQuadratic = 0.35f;
        [Tooltip("XP multiplier per extra player so bigger parties still level at a fun pace.")]
        public float xpPerExtraPlayer = 0.35f;
        public int choicesPerLevel = 3;
        public int maxWeapons = 4;
        public int maxPowerups = 6;
        [Range(0f, 1f)] public float healChoicePercent = 0.3f;

        [Header("Enemy scaling")]
        [Tooltip("Enemy HP +X per minute (0.15 = +15%/min).")]
        public float healthPerMinute = 0.25f;
        [Tooltip("Enemy HP +X per minute squared (makes the late game ramp up).")]
        public float healthPerMinuteSquared = 0.06f;
        [Tooltip("Enemy move speed +X per minute (capped at +35%).")]
        public float speedPerMinute = 0.035f;
        [Tooltip("Enemy HP +X per extra player.")]
        public float healthPerExtraPlayer = 0.5f;
        [Tooltip("Spawn rate +X per extra player.")]
        public float spawnRatePerExtraPlayer = 0.6f;
        public float damagePerMinute = 0.08f;
        public int maxEnemies = 220;
        public float spawnDistanceMin = 22f;
        public float spawnDistanceMax = 30f;
        [Tooltip("Elites: HP multiplier and size.")]
        public float eliteHealthMultiplier = 8f;
        public float eliteScale = 1.8f;
        [Tooltip("Floating crown shown over elites and bosses.")]
        public GameObject eliteCrown;

        [Header("Arena")]
        public float arenaHalfSize = 58f;

        [Header("Downed / Revive")]
        public float downedSeconds = 30f;
        public float reviveSeconds = 2.5f;
        public float reviveRadius = 2.5f;
        [Range(0f, 1f)] public float reviveHealthPercent = 0.5f;

        [Header("Pickups")]
        public NetworkObject xpGemPrefab;
        public NetworkObject healthOrbPrefab;
        public NetworkObject magnetPrefab;
        public NetworkObject chestPrefab;
        [Range(0f, 1f)] public float healthOrbHeal = 0.25f;
        public int maxGems = 220;

        public int XPForLevel(int level, int playerCount)
        {
            float baseXp = xpFirstLevel + xpPerLevel * (level - 1) + xpQuadratic * (level - 1) * (level - 1);
            return Mathf.CeilToInt(baseXp * (1f + xpPerExtraPlayer * Mathf.Max(0, playerCount - 1)));
        }
    }
}
