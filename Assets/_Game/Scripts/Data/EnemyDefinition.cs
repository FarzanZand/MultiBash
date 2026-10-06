using Fusion;
using UnityEngine;

namespace MultiBash
{
    public enum EnemyMovement
    {
        // (Hopper / Walker enemies can also flee: see EnemyDefinition.flees)
        Walker,   // walks straight at the nearest player
        Hopper,   // waits, then leaps toward the player
        Flyer,    // flies at head height with a weaving swoop, ignores props
        Keeper,   // walks to a preferred distance and holds it (ranged units)
    }

    public enum EnemyAttack
    {
        Contact,  // hurts on touch
        Ranged,   // shoots a dodgeable projectile
        Stomp,    // telegraphed ground slam around itself
        Explode,  // telegraphed self-destruct
    }

    [CreateAssetMenu(menuName = "MultiBash/Enemy", fileName = "NewEnemy", order = 3)]
    public class EnemyDefinition : ScriptableObject
    {
        [Header("Identity")]
        public string displayName = "Enemy";
        [Tooltip("Network prefab (needs NetworkObject + NetworkTransform + Enemy).")]
        public NetworkObject prefab;

        [Header("Stats (minute 0, 1 player)")]
        public float maxHealth = 20f;
        public float moveSpeed = 3f;
        public float contactDamage = 8f;
        [Tooltip("Seconds between hits on the same player.")]
        public float attackInterval = 1f;
        [Tooltip("How close the enemy must be to hit (meters, from center to center minus player radius).")]
        public float attackRange = 0.9f;
        [Tooltip("Body radius used to keep enemies from overlapping.")]
        public float radius = 0.45f;
        [Range(0f, 1f)] public float knockbackResist = 0f;

        [Header("Movement")]
        public EnemyMovement movement = EnemyMovement.Walker;
        [Tooltip("Hopper: seconds resting between hops.")]
        public float hopRest = 0.7f;
        [Tooltip("Hopper: seconds in the air.")]
        public float hopTime = 0.45f;
        [Tooltip("Hopper: hop height in meters.")]
        public float hopHeight = 1.2f;

        [Header("Hordes")]
        [Tooltip("Fodder: never gains HP over time (dies in one hit all run long). Used for the big late-game hordes.")]
        public bool fodder;
        [Tooltip("Size multiplier for this enemy (lets several enemies share one prefab).")]
        public float scale = 1f;
        [Tooltip("Size of the stage gear (helmets) relative to the head/body width.")]
        public float gearSize = 1.4f;
        [Tooltip("Chance a kill drops its XP gem (fodder hordes drop less so levels don't fly by).")]
        [Range(0f, 1f)] public float xpChance = 1f;

        [Header("Treasure (runaway loot enemies)")]
        [Tooltip("Hops AWAY from the players instead of toward them.")]
        public bool flees;
        [Tooltip("Despawns ('got away') after this many seconds. 0 = never.")]
        public float lifetime;
        [Tooltip("Chests dropped on death (also shows the TREASURE marker on the HUD).")]
        public int dropChests;

        [Header("Special attack")]
        public EnemyAttack attack = EnemyAttack.Contact;
        [Tooltip("Ranged: distance it tries to keep. Stomp/Explode: trigger distance.")]
        public float attackDistance = 9f;
        [Tooltip("Seconds between special attacks.")]
        public float specialCooldown = 3f;
        [Tooltip("Warning time before a stomp/explosion lands.")]
        public float telegraphTime = 0.9f;
        [Tooltip("Stomp/Explode radius, or projectile hit radius.")]
        public float specialRadius = 3.5f;
        [Tooltip("Damage multiplier of the special attack vs contact damage.")]
        public float specialDamageMul = 1.6f;
        public float projectileSpeed = 12f;
        public Color specialColor = new(1f, 0.3f, 0.2f);
        public AudioClip specialSound;

        [Header("Rewards")]
        public int xpValue = 1;
        [Range(0f, 1f)] public float healthOrbChance = 0.01f;
        [Range(0f, 1f)] public float magnetChance = 0.002f;

        [Header("On death")]
        [Tooltip("Spawn these when killed (e.g. big slime -> small slimes).")]
        public EnemyDefinition splitInto;
        public int splitCount = 0;

        [Header("Boss version (used by wave bursts marked 'boss')")]
        public string bossName = "";
        public float bossHealthMultiplier = 150f;
        public float bossDamageMultiplier = 2.5f;
        public float bossScale = 3.2f;
        [Tooltip("Extra enemies spawned when the boss dies (uses splitInto).")]
        public int bossSplitCount = 0;

        [Header("Audio")]
        public AudioClip hitSound;
        public AudioClip deathSound;
        public AudioClip moveSound;
        public Color deathColor = Color.white;
    }
}
