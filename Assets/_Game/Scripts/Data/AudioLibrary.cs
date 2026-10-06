using UnityEngine;

namespace MultiBash
{
    /// <summary>Shared sounds that don't belong to a specific weapon or enemy.</summary>
    [CreateAssetMenu(menuName = "MultiBash/Audio Library", fileName = "AudioLibrary", order = 12)]
    public class AudioLibrary : ScriptableObject
    {
        [Header("Music")]
        public AudioClip menuMusic;
        public AudioClip battleMusic;
        [Range(0, 1)] public float musicVolume = 0.45f;

        [Header("UI")]
        public AudioClip click;
        public AudioClip hover;
        public AudioClip ready;
        public AudioClip start;
        public AudioClip victory;
        public AudioClip defeat;

        [Header("Player")]
        public AudioClip hurt;
        public AudioClip jump;
        public AudioClip slide;
        public AudioClip downed;
        public AudioClip revive;
        public AudioClip levelUp;
        public AudioClip lavaSizzle;

        [Header("Pickups")]
        public AudioClip gem;
        public AudioClip health;
        public AudioClip magnet;
        public AudioClip chest;
    }
}
