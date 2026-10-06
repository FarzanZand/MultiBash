using UnityEngine;

namespace MultiBash
{
    /// <summary>
    /// The control panel for combat (hero base stats, movement, global damage / cooldown / area knobs, crits,
    /// knockback, damage taken, item effects and screen feel). Lives in each game scene under "--- Managers ---".
    /// Select it to edit; while playing it has test buttons (god mode, heal, max weapons...).
    /// Without a manager in the scene, the default asset from the GameDatabase is used.
    /// </summary>
    [DisallowMultipleComponent]
    public class CombatManager : MonoBehaviour
    {
        public static CombatManager Instance { get; private set; }

        [Tooltip("The settings this map uses. Swap in a copy to tune a map on its own.")]
        public CombatSettings settings;

        /// <summary>Settings in effect right now (this scene's manager, else the database default).</summary>
        public static CombatSettings Settings =>
            Instance != null && Instance.settings != null ? Instance.settings : GameDatabase.Instance.combat;

        void OnEnable() => Instance = this;

        void OnDisable()
        {
            if (Instance == this) Instance = null;
        }

        /// <summary>Recompute every hero's stats (after editing base stats or the global knobs while playing).</summary>
        public static void RefreshHeroStats()
        {
            foreach (var p in PlayerCharacter.All)
                if (p != null && p.Object != null && p.Object.IsValid && p.Object.HasStateAuthority) p.LoadoutVersion++;
        }

        void OnValidate()
        {
            if (Application.isPlaying) RefreshHeroStats();
        }
    }
}
