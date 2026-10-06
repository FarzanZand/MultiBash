using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Audio;

namespace MultiBash
{
    /// <summary>
    /// All sound for this player, routed through Audio/MultiBashMixer: three groups with their own volume
    /// (exposed mixer parameters "MusicVolume", "SFXVolume", "UIVolume"):
    ///   Music - crossfading background music (map music, boss theme, menu)
    ///   SFX   - pooled 3D world sounds (weapons, enemies, pickups). Limits copies of the same clip so 200 deaths
    ///           at once don't turn into noise.
    ///   UI    - 2D interface and personal cues (clicks, level up, gem combo, heartbeat). Own pool so a pitched
    ///           sound never re-pitches another one still playing.
    ///
    /// Multiplayer: audio is purely local. Every peer plays the sounds the game tells it to (RPCs / replicated
    /// state trigger them), and every player has their own volumes (saved in PlayerPrefs). Nothing here is networked.
    /// Lives on the persistent GameServices prefab.
    /// </summary>
    public class AudioManager : MonoBehaviour
    {
        public static AudioManager Instance { get; private set; }

        public enum Channel { Music, SFX, UI }

        [Header("Mixer (Audio/MultiBashMixer)")]
        public AudioMixer mixer;
        public AudioMixerGroup musicGroup;
        public AudioMixerGroup sfxGroup;
        public AudioMixerGroup uiGroup;

        [Header("Default volumes (0-1, players change them in the pause menu)")]
        [Range(0, 1)] public float defaultMusicVolume = 1f;
        [Range(0, 1)] public float defaultSfxVolume = 0.8f;
        [Range(0, 1)] public float defaultUiVolume = 0.9f;

        [Header("World SFX pool")]
        [SerializeField] int voices = 32;
        [Tooltip("Most copies of one clip playing at once.")]
        [SerializeField] int maxSameClip = 4;
        [SerializeField] float sameClipMinInterval = 0.035f;
        [SerializeField] int uiVoices = 6;

        readonly List<AudioSource> _pool = new();
        readonly List<AudioSource> _uiPool = new();
        readonly Dictionary<AudioClip, float> _lastPlayed = new();
        readonly float[] _volume = new float[3];
        AudioSource _music, _musicB;   // _music = current, _musicB = fading out
        AudioSource _ambience;
        float _ambienceTarget, _ambienceFade = 1.5f;
        float _fadeTime = 1f, _fadeT = 1f;
        int _next, _nextUi;

        static readonly string[] PrefKeys = { "musicVolume", "sfxVolume", "uiVolume" };
        static readonly string[] MixerParams = { "MusicVolume", "SFXVolume", "UIVolume" };

        void Awake()
        {
            Instance = this;
            _volume[0] = PlayerPrefs.GetFloat(PrefKeys[0], defaultMusicVolume);
            _volume[1] = PlayerPrefs.GetFloat(PrefKeys[1], defaultSfxVolume);
            _volume[2] = PlayerPrefs.GetFloat(PrefKeys[2], defaultUiVolume);
            for (int i = 0; i < voices; i++)
            {
                var go = new GameObject("SfxVoice" + i);
                go.transform.SetParent(transform);
                var s = go.AddComponent<AudioSource>();
                s.playOnAwake = false;
                s.spatialBlend = 0.6f;
                s.rolloffMode = AudioRolloffMode.Linear;
                s.minDistance = 8f;
                s.maxDistance = 60f;
                s.dopplerLevel = 0f;
                s.outputAudioMixerGroup = sfxGroup;
                _pool.Add(s);
            }
            _music = MusicSource();
            _musicB = MusicSource();
            _ambience = gameObject.AddComponent<AudioSource>();
            _ambience.loop = true;
            _ambience.playOnAwake = false;
            _ambience.spatialBlend = 0f;
            _ambience.volume = 0f;
            _ambience.outputAudioMixerGroup = sfxGroup;
            for (int i = 0; i < uiVoices; i++)
            {
                var s = gameObject.AddComponent<AudioSource>();
                s.playOnAwake = false;
                s.spatialBlend = 0f;
                s.outputAudioMixerGroup = uiGroup;
                _uiPool.Add(s);
            }
        }

        // exposed mixer parameters can't be set reliably during Awake
        void Start()
        {
            for (int i = 0; i < 3; i++) ApplyVolume((Channel)i);
        }

        AudioSource MusicSource()
        {
            var m = gameObject.AddComponent<AudioSource>();
            m.loop = true;
            m.playOnAwake = false;
            m.spatialBlend = 0f;
            m.outputAudioMixerGroup = musicGroup;
            return m;
        }

        /// <summary>Per-channel gain applied on the source when there is no mixer (fallback).</summary>
        float Gain(Channel c) => mixer != null ? 1f : _volume[(int)c];

        // music mix level (AudioLibrary.musicVolume) x player volume (mixer or fallback)
        float MusicTarget => (Lib != null ? Lib.musicVolume : 0.4f) * Gain(Channel.Music);

        void Update()
        {
            if (_ambience != null && _ambience.clip != null)
            {
                float want = _ambienceTarget * Gain(Channel.SFX);
                _ambience.volume = Mathf.MoveTowards(_ambience.volume, want, Time.unscaledDeltaTime / Mathf.Max(0.1f, _ambienceFade));
                if (_ambience.volume <= 0.001f && _ambienceTarget <= 0f && _ambience.isPlaying) _ambience.Stop();
            }
            if (_fadeT >= 1f) return;
            _fadeT = Mathf.Min(1f, _fadeT + Time.unscaledDeltaTime / Mathf.Max(0.01f, _fadeTime));
            float target = MusicTarget;
            _music.volume = target * _fadeT;
            _musicB.volume = target * (1f - _fadeT);
            if (_fadeT >= 1f) _musicB.Stop();
        }

        public static AudioLibrary Lib => GameDatabase.Instance != null ? GameDatabase.Instance.audio : null;

        // ------------------------------------------------------------------ playback

        /// <summary>2D interface / personal sound on the UI channel.</summary>
        public static void PlayUI(AudioClip clip, float volume = 1f, float pitch = 1f)
        {
            if (Instance == null || clip == null) return;
            var I = Instance;
            AudioSource src = null;
            for (int i = 0; i < I._uiPool.Count; i++)
            {
                var s = I._uiPool[(I._nextUi + i) % I._uiPool.Count];
                if (!s.isPlaying) { src = s; break; }
            }
            if (src == null) src = I._uiPool[I._nextUi];
            I._nextUi = (I._nextUi + 1) % I._uiPool.Count;
            src.clip = clip;
            src.pitch = pitch;
            src.volume = volume * I.Gain(Channel.UI);
            src.Play();
        }

        /// <summary>3D world sound on the SFX channel.</summary>
        public static void Play(AudioClip clip, Vector3 position, float volume = 1f, float pitch = 1f, float pitchJitter = 0.08f)
        {
            if (Instance == null || clip == null) return;
            Instance.PlayInternal(clip, position, volume, pitch + Random.Range(-pitchJitter, pitchJitter));
        }

        void PlayInternal(AudioClip clip, Vector3 pos, float volume, float pitch)
        {
            float now = Time.unscaledTime;
            if (_lastPlayed.TryGetValue(clip, out float last) && now - last < sameClipMinInterval) return;

            int playing = 0;
            foreach (var s in _pool)
                if (s.isPlaying && s.clip == clip) playing++;
            if (playing >= maxSameClip) return;

            _lastPlayed[clip] = now;
            AudioSource src = null;
            for (int i = 0; i < _pool.Count; i++)
            {
                var s = _pool[(_next + i) % _pool.Count];
                if (!s.isPlaying) { src = s; _next = (_next + i + 1) % _pool.Count; break; }
            }
            if (src == null) { src = _pool[_next]; _next = (_next + 1) % _pool.Count; }

            src.transform.position = pos;
            src.clip = clip;
            src.volume = volume * Gain(Channel.SFX);
            src.pitch = pitch;
            src.Play();
        }

        /// <summary>Switch music. fade > 0 crossfades from the current track.</summary>
        public static void PlayMusic(AudioClip clip, float fade = 0f)
        {
            if (Instance == null || clip == null) return;
            var I = Instance;
            if (I._music.clip == clip && I._music.isPlaying) return;
            if (fade <= 0f || !I._music.isPlaying)
            {
                I._musicB.Stop();
                I._music.clip = clip;
                I._music.volume = I.MusicTarget;
                I._music.Play();
                I._fadeT = 1f;
                return;
            }
            (I._music, I._musicB) = (I._musicB, I._music);
            I._music.clip = clip;
            I._music.volume = 0f;
            I._music.Play();
            I._fadeTime = fade;
            I._fadeT = 0f;
        }

        /// <summary>Looping ambient bed (wind, lava rumble) on the SFX channel; null fades it out.</summary>
        public static void PlayAmbience(AudioClip clip, float volume = 0.5f)
        {
            if (Instance == null) return;
            var a = Instance._ambience;
            if (clip == null) { Instance._ambienceTarget = 0f; return; }
            if (a.clip != clip) { a.clip = clip; a.volume = 0f; a.Play(); }
            else if (!a.isPlaying) a.Play();
            Instance._ambienceTarget = volume;
        }

        public static void StopMusic()
        {
            if (Instance != null) { Instance._music.Stop(); Instance._musicB.Stop(); Instance._fadeT = 1f; }
        }

        // ------------------------------------------------------------------ volumes (per player, saved)

        public static float GetVolume(Channel c) => Instance != null ? Instance._volume[(int)c] : PlayerPrefs.GetFloat(PrefKeys[(int)c], 1f);

        public static void SetVolume(Channel c, float v)
        {
            v = Mathf.Clamp01(v);
            PlayerPrefs.SetFloat(PrefKeys[(int)c], v);
            if (Instance == null) return;
            Instance._volume[(int)c] = v;
            Instance.ApplyVolume(c);
        }

        void ApplyVolume(Channel c)
        {
            float v = _volume[(int)c];
            if (mixer != null) mixer.SetFloat(MixerParams[(int)c], v <= 0.0001f ? -80f : Mathf.Log10(v) * 20f);
            else if (c == Channel.Music && _fadeT >= 1f) _music.volume = MusicTarget;
        }

        // kept for existing callers
        public static void SetMusicVolume(float v) => SetVolume(Channel.Music, v);
        public static void SetSfxVolume(float v) => SetVolume(Channel.SFX, v);
        public static void SetUiVolume(float v) => SetVolume(Channel.UI, v);
    }
}
