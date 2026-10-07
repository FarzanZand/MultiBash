using System.Collections.Generic;
using UnityEngine;

namespace MultiBash
{
    /// <summary>
    /// Everything about how COMBAT feels: hero base stats and movement, global damage / cooldown / area knobs,
    /// crits and knockback, how hard enemies hit, item effects (Phoenix Feather...) and screen feel.
    /// Edit it on the CombatManager object in a game scene (or this asset: Content/Settings/CombatSettings).
    /// Values are read live; the host's values are the ones that count for damage.
    /// </summary>
    [CreateAssetMenu(menuName = "MultiBash/Combat Settings", fileName = "CombatSettings", order = 9)]
    public class CombatSettings : ScriptableObject
    {
        [Header("Hero base stats (before character bonuses and tomes)")]
        public List<StatModifier> baseStats = new()
        {
            new(StatType.MaxHealth, 100f), new(StatType.HealthRegen, 0.3f), new(StatType.MoveSpeed, 7f),
            new(StatType.Damage, 1f), new(StatType.Area, 1f), new(StatType.Cooldown, 1f), new(StatType.ProjectileSpeed, 1f),
            new(StatType.Duration, 1f), new(StatType.PickupRadius, 3.2f), new(StatType.XPGain, 1f),
            new(StatType.CritChance, 0.08f), new(StatType.CritDamage, 2f),
        };

        [Header("Global hero power knobs (multiply final stats)")]
        [Tooltip("All hero damage.")]
        public float damageMultiplier = 1f;
        [Tooltip("All weapon cooldowns (lower = faster attacks).")]
        public float cooldownMultiplier = 1f;
        [Tooltip("Size of swings, auras, puddles, orbits and blasts.")]
        public float areaMultiplier = 1f;
        public float moveSpeedMultiplier = 1f;
        [Tooltip("Fastest a weapon may get (cooldown stat floor).")]
        public float minCooldown = 0.25f;

        [Header("Movement")]
        public float jumpImpulse = 8.5f;
        public float slideSpeedMultiplier = 1.9f;
        public float slideDuration = 0.45f;
        public float slideCooldown = 0.8f;
        [Tooltip("Speed bonus from a slide-jump until you land.")]
        public float momentumSpeed = 1.45f;

        [Header("Damage dealt")]
        [Tooltip("Random spread on every hit (0.1 = ±10%).")]
        [Range(0f, 0.5f)] public float damageSpread = 0.1f;
        [Tooltip("Crit chance gained per point of Luck.")]
        public float critChancePerLuck = 0.05f;
        [Tooltip("Smallest crit multiplier, whatever the stats say.")]
        public float minCritMultiplier = 1.5f;
        [Tooltip("Multiplies all knockback.")]
        public float knockbackMultiplier = 1f;
        public float maxKnockback = 14f;

        [Header("Damage taken")]
        [Tooltip("Multiplies every enemy hit on heroes.")]
        public float damageTakenMultiplier = 1f;
        [Tooltip("Smallest hit after armor.")]
        public float minDamageTaken = 1f;
        [Tooltip("Invulnerability after taking a hit (seconds).")]
        public float hurtInvulnerability = 0.33f;
        [Tooltip("Multiplies enemy contact and attack damage (applied when they spawn).")]
        public float enemyDamageMultiplier = 1f;

        [Header("Items")]
        [Tooltip("Phoenix Feather: HP you rise with, blast radius and damage (+ share of your max HP).")]
        [Range(0f, 1f)] public float phoenixHealPercent = 0.6f;
        public float phoenixBlastRadius = 6f;
        public float phoenixBlastDamage = 40f;
        public float phoenixBlastPerMaxHealth = 0.4f;

        [Header("Feel")]
        [Tooltip("Multiplies every camera shake.")]
        [Range(0f, 3f)] public float screenShake = 1f;
        public bool showDamageNumbers = true;
        [Range(5, 120)] public int maxDamageNumbers = 40;
        [Tooltip("Full death effects per second before deaths get a lighter burst.")]
        public float deathEffectsPerSecond = 50f;
        [Tooltip("Below this share of HP: heartbeat and red screen edge.")]
        [Range(0f, 1f)] public float lowHealthWarning = 0.3f;
    }
}
