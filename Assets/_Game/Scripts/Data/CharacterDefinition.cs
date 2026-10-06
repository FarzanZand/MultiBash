using System.Collections.Generic;
using UnityEngine;

namespace MultiBash
{
    [CreateAssetMenu(menuName = "MultiBash/Character", fileName = "NewCharacter", order = 0)]
    public class CharacterDefinition : ScriptableObject
    {
        [Header("Identity")]
        public string displayName = "Hero";
        [TextArea(2, 4)] public string description;
        public Sprite portrait;
        public Color color = Color.white;

        [Header("Visuals")]
        [Tooltip("Model shown in game (the FBX or a prefab). Needs child parts named Body/ArmL/ArmR/LegL/LegR for animation and Hand_R for the weapon.")]
        public GameObject model;

        [Header("Gameplay")]
        public WeaponDefinition startingWeapon;
        [Tooltip("Bonuses on top of GameConfig base stats.")]
        public List<StatModifier> statBonuses = new();

        public string PassiveText
        {
            get
            {
                var parts = new List<string>();
                foreach (var m in statBonuses) parts.Add(m.ToString());
                return string.Join(", ", parts);
            }
        }
    }
}
