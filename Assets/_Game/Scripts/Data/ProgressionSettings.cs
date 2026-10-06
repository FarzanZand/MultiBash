using UnityEngine;

namespace MultiBash
{
    /// <summary>
    /// Everything about how a run PROGRESSES: run length, team leveling and upgrade offers, how enemies scale with
    /// time / team level / party size, the three enemy stages, spawning, drops, combo / Frenzy and revives.
    /// Edit it on the ProgressionManager object in a game scene (or this asset: Content/Settings/ProgressionSettings).
    /// Values are read live, so you can tweak them while playing (the host's values are the ones that count).
    /// </summary>
    [CreateAssetMenu(menuName = "MultiBash/Progression Settings", fileName = "ProgressionSettings", order = 8)]
    public class ProgressionSettings : ScriptableObject
    {
        [Header("Run")]
        [Tooltip("Survive this long to win (seconds).")]
        public float runDurationSeconds = 600f;
        [Tooltip("Seconds on the results screen before everyone returns to the lobby.")]
        public float resultsSeconds = 15f;

        [Header("Team leveling (shared XP)")]
        public int xpFirstLevel = 6;
        [Tooltip("Extra XP needed per level.")]
        public int xpPerLevel = 6;
        [Tooltip("Extra XP needed per level squared (keeps late levels slower).")]
        public float xpQuadratic = 1.1f;
        [Tooltip("XP needed +X per extra player (bigger parties also kill more).")]
        public float xpPerExtraPlayer = 0.35f;
        [Tooltip("Multiplies every XP gem picked up.")]
        public float xpMultiplier = 1f;

        [Header("Upgrade offers")]
        [Range(1, 3)] public int choicesPerLevel = 3;
        [Range(1, 4)] public int maxWeapons = 4;
        [Range(1, 12)] public int maxPowerups = 6;
        [Tooltip("Free rerolls each player starts with.")]
        public int rerollsPerRun = 3;
        [Tooltip("Rerolls everyone gets for each boss kill.")]
        public int rerollsPerBossKill = 1;
        [Tooltip("A weapon can evolve (with its tome) from this level on.")]
        [Range(1, 8)] public int evolveLevel = 5;
        [Tooltip("Extra luck when rolling a chest's Treasure offer.")]
        public float treasureLuckBonus = 2.5f;
        [Range(0f, 1f)] public float healChoicePercent = 0.3f;
        [Tooltip("Skipping an offer heals this share of max HP.")]
        [Range(0f, 1f)] public float skipHealPercent = 0.15f;
        [Tooltip("Power Surge (offered once everything is maxed): damage and max HP per pick.")]
        public float powerSurgeDamage = 0.06f;
        public float powerSurgeHealth = 6f;

        [Header("Enemy toughness")]
        [Tooltip("Enemy HP +X per minute (0.12 = +12%/min).")]
        public float healthPerMinute = 0.12f;
        public float healthPerMinuteSquared = 0f;
        [Tooltip("Enemy HP +X per team level: enemies keep up with how strong the party is.")]
        public float healthPerTeamLevel = 0.03f;
        public float healthPerTeamLevelSquared = 0.0045f;
        [Tooltip("Share of the team-level HP bonus fodder (horde) enemies get. 0 = always one-hit.")]
        [Range(0f, 1f)] public float fodderLevelScaling = 0.35f;
        [Tooltip("Enemy HP +X per extra player.")]
        public float healthPerExtraPlayer = 0.2f;
        [Tooltip("Enemy contact/attack damage +X per minute.")]
        public float damagePerMinute = 0.08f;
        [Tooltip("Enemy move speed +X per minute, capped below.")]
        public float speedPerMinute = 0.05f;
        public float maxSpeedBonus = 0.35f;

        [Header("Elites and bosses")]
        public float eliteHealthMultiplier = 8f;
        public float eliteDamageMultiplier = 1.5f;
        public float eliteScale = 1.8f;
        [Tooltip("Multiplies every boss's HP on top of its own boss multiplier.")]
        public float bossHealthMultiplier = 1f;
        public float bossDamageMultiplier = 1f;

        [Header("Enemy stages (new looks, gear and enemy types)")]
        [Tooltip("Run fraction where enemies switch to their stage 2 look (helmets, steel tint).")]
        [Range(0f, 1f)] public float stage2At = 0.36f;
        [Tooltip("Run fraction where enemies switch to their stage 3 look (horned helms, crimson tint).")]
        [Range(0f, 1f)] public float stage3At = 0.63f;
        [Tooltip("HP and damage +X per stage.")]
        public float stageBonus = 0.1f;
        [Tooltip("Size of stage 3 enemies.")]
        public float stage3Scale = 1.1f;

        [Header("Spawning")]
        [Tooltip("Multiplies every spawn rate in the wave timelines.")]
        public float spawnRateMultiplier = 1f;
        [Tooltip("Multiplies the size of every burst / horde.")]
        public float burstSizeMultiplier = 1f;
        [Tooltip("Spawn rate +X per extra player.")]
        public float spawnRatePerExtraPlayer = 0.3f;
        [Tooltip("Most enemies alive at once (network limit is around 450).")]
        public int maxEnemies = 420;
        public float spawnDistanceMin = 22f;
        public float spawnDistanceMax = 30f;
        [Tooltip("Bursts at least this big shake the camera.")]
        public int hordeShakeThreshold = 40;

        [Header("Drops")]
        [Range(0f, 1f)] public float healthOrbHeal = 0.25f;
        [Tooltip("XP gems on the map before new ones merge into old ones.")]
        public int maxGems = 220;
        [Tooltip("New gems merge into an idle gem this close.")]
        public float gemMergeRadius = 1.4f;

        [Header("Kill combo / FRENZY")]
        [Tooltip("Seconds between kills before the combo breaks.")]
        public float comboWindow = 2.5f;
        [Tooltip("First FRENZY at this many chained kills; each next one needs this many more on top.")]
        public int frenzyFirst = 50;
        public int frenzyGapGrowth = 50;
        [Range(0f, 1f)] public float frenzyHeal = 0.1f;
        public float frenzyVacuumRadius = 30f;

        [Header("Downed and revive")]
        public float downedSeconds = 30f;
        public float reviveSeconds = 2.5f;
        public float reviveRadius = 2.5f;
        [Range(0f, 1f)] public float reviveHealthPercent = 0.5f;

        // ------------------------------------------------------------------ formulas (one place to read and change them)

        public int XPForLevel(int level, int playerCount)
        {
            float baseXp = xpFirstLevel + xpPerLevel * (level - 1) + xpQuadratic * (level - 1) * (level - 1);
            return Mathf.CeilToInt(baseXp * (1f + xpPerExtraPlayer * Mathf.Max(0, playerCount - 1)));
        }

        /// <summary>Enemy HP multiplier for something spawning now (before elite / boss / stage bonuses).</summary>
        public float EnemyHealthMultiplier(float minute, int teamLevel, int players, float mapDifficulty, bool fodder)
        {
            float L = Mathf.Max(0, teamLevel - 1);
            float levelMul = 1f + healthPerTeamLevel * L + healthPerTeamLevelSquared * L * L;
            if (fodder) levelMul = 1f + (levelMul - 1f) * fodderLevelScaling;
            float timeMul = fodder ? 1f : 1f + healthPerMinute * minute + healthPerMinuteSquared * minute * minute;
            return timeMul * levelMul * (1f + healthPerExtraPlayer * (players - 1)) * mapDifficulty;
        }

        public float EnemyDamageMultiplier(float minute) => 1f + damagePerMinute * minute;

        public float EnemySpeedMultiplier(float minute) => 1f + Mathf.Min(minute * speedPerMinute, maxSpeedBonus);

        /// <summary>0, 1 or 2 for the given run time.</summary>
        public int StageAt(float runTime)
        {
            float f = runTime / Mathf.Max(1f, runDurationSeconds);
            return f >= stage3At ? 2 : f >= stage2At ? 1 : 0;
        }
    }
}
