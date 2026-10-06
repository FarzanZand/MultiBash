using System.Collections.Generic;
using UnityEngine;

namespace MultiBash
{
    /// <summary>A passive upgrade ("tome") that adds stats every level.</summary>
    [CreateAssetMenu(menuName = "MultiBash/Powerup", fileName = "NewPowerup", order = 2)]
    public class PowerupDefinition : ScriptableObject
    {
        public string displayName = "Powerup";
        [TextArea(2, 3)] public string description;
        public Sprite icon;
        public Rarity rarity = Rarity.Common;
        [Range(1, 10)] public int maxLevel = 5;

        [Tooltip("Applied once per level owned.")]
        public List<StatModifier> perLevel = new();

        public string EffectText
        {
            get
            {
                var parts = new List<string>();
                foreach (var m in perLevel) parts.Add(m.ToString());
                return string.Join(", ", parts);
            }
        }
    }
}
