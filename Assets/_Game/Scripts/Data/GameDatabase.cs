using System.Collections.Generic;
using Fusion;
using UnityEngine;

namespace MultiBash
{
    /// <summary>
    /// The single index of all content. The network sends list indices, so every peer must have the same database.
    /// Lives in Content/Resources/GameDatabase.asset. Use the menu "MultiBash/Refresh Database" (or the Content Browser)
    /// after adding new characters, weapons, powerups or enemies — it finds them automatically.
    /// </summary>
    [CreateAssetMenu(menuName = "MultiBash/Game Database", fileName = "GameDatabase", order = 11)]
    public class GameDatabase : ScriptableObject
    {
        public GameConfig config;
        [Tooltip("Default progression tuning (a scene's ProgressionManager can point at its own copy).")]
        public ProgressionSettings progression;
        [Tooltip("Default combat tuning (a scene's CombatManager can point at its own copy).")]
        public CombatSettings combat;
        public AudioLibrary audio;

        [Header("Content (auto-filled by MultiBash/Refresh Database)")]
        public List<CharacterDefinition> characters = new();
        public List<WeaponDefinition> weapons = new();
        public List<PowerupDefinition> powerups = new();
        public List<EnemyDefinition> enemies = new();
        public List<MapDefinition> maps = new();

        [Header("Network prefabs")]
        public NetworkObject playerDataPrefab;
        public NetworkObject playerCharacterPrefab;

        [Header("Misc")]
        public Sprite healIcon;
        public Sprite xpIcon;

        static GameDatabase _instance;

        public static GameDatabase Instance
        {
            get
            {
                if (_instance == null) _instance = Resources.Load<GameDatabase>("GameDatabase");
                return _instance;
            }
        }

        public static GameConfig Config => Instance.config;

        public CharacterDefinition GetCharacter(int i) => characters[Mathf.Clamp(i, 0, characters.Count - 1)];
        public WeaponDefinition GetWeapon(int i) => i >= 0 && i < weapons.Count ? weapons[i] : null;
        public PowerupDefinition GetPowerup(int i) => i >= 0 && i < powerups.Count ? powerups[i] : null;
        public EnemyDefinition GetEnemy(int i) => i >= 0 && i < enemies.Count ? enemies[i] : null;
        public MapDefinition GetMap(int i) => maps.Count == 0 ? null : maps[Mathf.Clamp(i, 0, maps.Count - 1)];
        public int IndexOf(WeaponDefinition w) => weapons.IndexOf(w);
        public int IndexOf(EnemyDefinition e) => enemies.IndexOf(e);
    }
}
