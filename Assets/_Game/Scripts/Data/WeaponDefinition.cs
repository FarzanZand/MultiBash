using System;
using UnityEngine;

namespace MultiBash
{
    /// <summary>How a weapon behaves. Each kind has its own logic in Combat/WeaponLogic.cs.</summary>
    public enum WeaponKind
    {
        MeleeArc,     // sweeping arc in front (Greatsword)
        Projectile,   // auto-aimed piercing projectiles (Longbow)
        Chain,        // lightning that jumps between enemies (Storm Staff)
        Lobbed,       // thrown flask that leaves a damage puddle (Poison Flask)
        Orbit,        // blades circling the player (Orbiting Blades)
        Aura,         // constant damage ring (Holy Aura)
        Boomerang,    // thrown out and back, hits on both passes (Boomerang)
        Meteor,       // meteors fall on enemies and explode (Meteor Staff)
        Nova,         // expanding ring that damages and slows (Frost Nova)
        Homing,       // projectiles that seek enemies (Spirit Daggers)
    }

    public enum Rarity { Common, Rare, Epic }

    [Serializable]
    public class WeaponLevel
    {
        [Tooltip("Shown on the level-up card.")]
        public string upgradeText = "";
        public float damage = 10f;
        [Tooltip("Seconds between attacks (before the player's Cooldown stat).")]
        public float cooldown = 1f;
        [Tooltip("Projectiles / swings / chain jumps / blades / flasks.")]
        public int amount = 1;
        [Tooltip("Radius or reach in meters (scaled by the player's Area stat).")]
        public float area = 3f;
        [Tooltip("How many enemies a projectile passes through.")]
        public int pierce = 1;
        [Tooltip("Lifetime of projectiles / puddles in seconds.")]
        public float duration = 1f;
        [Tooltip("Projectile or rotation speed.")]
        public float speed = 18f;
        public float knockback = 4f;
    }

    [CreateAssetMenu(menuName = "MultiBash/Weapon", fileName = "NewWeapon", order = 1)]
    public class WeaponDefinition : ScriptableObject
    {
        [Header("Identity")]
        public string displayName = "Weapon";
        [TextArea(2, 4)] public string description;
        public Sprite icon;
        public Rarity rarity = Rarity.Common;

        [Header("Behavior")]
        public WeaponKind kind;
        [Tooltip("One entry per level. Level 1 is the first entry. Max level = number of entries.")]
        public WeaponLevel[] levels = { new WeaponLevel() };

        [Header("Visuals & Audio")]
        [Tooltip("Model held in the character's hand (optional).")]
        public GameObject heldModel;
        [Tooltip("Model used for projectiles / blades / thrown flasks (optional).")]
        public GameObject projectileModel;
        public Color fxColor = Color.white;
        public AudioClip fireSound;
        public AudioClip hitSound;

        public int MaxLevel => levels.Length;
        public WeaponLevel GetLevel(int level) => levels[Mathf.Clamp(level - 1, 0, levels.Length - 1)];
    }
}
