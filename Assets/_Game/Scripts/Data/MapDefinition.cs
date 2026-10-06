using UnityEngine;

namespace MultiBash
{
    /// <summary>A playable level: which scene to load, its spawn timeline, music and lobby text.</summary>
    [CreateAssetMenu(menuName = "MultiBash/Map", fileName = "NewMap", order = 5)]
    public class MapDefinition : ScriptableObject
    {
        public string displayName = "Map";
        [TextArea(2, 3)] public string description;
        [Tooltip("Announcement when the run starts.")]
        public string intro = "Survive the night!";
        [Tooltip("Scene name (must be in Build Settings).")]
        public string sceneName = "Game";
        public WaveDefinition waves;
        public AudioClip music;
        [Tooltip("Looping ambient bed under the music (wind, lava rumble...). SFX channel.")]
        public AudioClip ambience;
        [Range(0, 1)] public float ambienceVolume = 0.5f;
        public Color accent = Color.white;
        [Tooltip("Shown in the lobby map picker.")]
        public Sprite preview;
        [Tooltip("Enemy HP multiplier for this map (harder maps > 1).")]
        public float difficulty = 1f;
    }
}
