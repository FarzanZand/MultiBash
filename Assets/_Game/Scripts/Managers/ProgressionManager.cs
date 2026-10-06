using UnityEngine;

namespace MultiBash
{
    /// <summary>
    /// The control panel for run progression (levels, XP, enemy scaling, stages, spawning, drops, combo, revives).
    /// Lives in each game scene under "--- Managers ---". Select it to edit the settings; while playing it also shows
    /// the live state and has test buttons (grant levels, skip time...).
    /// Each map can point at its own settings asset (e.g. a harder copy for the volcano). Without a manager in the
    /// scene (menus, lobby), the default asset from the GameDatabase is used.
    /// </summary>
    [DisallowMultipleComponent]
    public class ProgressionManager : MonoBehaviour
    {
        public static ProgressionManager Instance { get; private set; }

        [Tooltip("The settings this map uses. Swap in a copy to tune a map on its own.")]
        public ProgressionSettings settings;

        /// <summary>Settings in effect right now (this scene's manager, else the database default).</summary>
        public static ProgressionSettings Settings =>
            Instance != null && Instance.settings != null ? Instance.settings : GameDatabase.Instance.progression;

        void OnEnable() => Instance = this;

        void OnDisable()
        {
            if (Instance == this) Instance = null;
        }

        // ------------------------------------------------------------------ live readouts (used by the inspector)

        public static float Minute => GameManager.Instance != null ? GameManager.Instance.RunTime / 60f : 0f;
        public static int TeamLevel => GameManager.Instance != null ? GameManager.Instance.TeamLevel : 1;
        public static int Players => Mathf.Max(1, PlayerCharacter.All.Count);

        public static float CurrentEnemyHealthMultiplier(bool fodder = false)
        {
            var gm = GameManager.Instance;
            float diff = gm != null && gm.map != null ? gm.map.difficulty : 1f;
            return Settings.EnemyHealthMultiplier(Minute, TeamLevel, Players, diff, fodder);
        }
    }
}
