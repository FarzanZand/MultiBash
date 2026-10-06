using System.Collections.Generic;
using UnityEngine;

namespace MultiBash
{
    /// <summary>
    /// Pooled one-shot SFX + crossfading music. Limits how many copies of the same clip can play at once,
    /// so 200 skeletons dying at once doesn't turn into noise. UI sounds get their own small pool so a
    /// pitched sound (gem combo) never re-pitches another one that is still playing.
    /// </summary>
    public class AudioManager : MonoBehaviour
    {
        public static AudioManager Instance { get; private set; }

        [SerializeField] int voices = 32;
        [SerializeField] int maxSameClip = 4;
        [SerializeField] float sameClipMinInterval = 0.035f;
        [Range(0, 1)] public float sfxVolume = 0.8f;

        readonly List<AudioSource> _pool = new();
        readonly List<AudioSource> _uiPool = new();
        readonly Dictionary<AudioClip, float> _lastPlayed = new();
        AudioSource _music, _musicB;   // _music = current, _musicB = fading out
        float _fadeTime = 1f, _fadeT = 1f;
        int _next, _nextUi;

        void Awake()
        {
            Instance = this;
            for (int i = 0; i < voices; i++)
            {
                var go = new GameObject("Voice" + i);
                go.transform.SetParent(transform);
                var s = go.AddComponent<AudioSource>();
                s.playOnAwake = false;
                s.spatialBlend = 0.6f;
                s.rolloffMode = AudioRolloffMode.Linear;
                s.minDistance = 8f;
                s.maxDistance = 60f;
                s.dopplerLevel = 0f;
                _pool.Add(s);
            }
            _music = MusicSource();
            _musicB = MusicSource();
            for (int i = 0; i < 6; i++)
            {
                var s = gameObject.AddComponent<AudioSource>();
                s.playOnAwake = false;
                s.spatialBlend = 0f;
                _uiPool.Add(s);
            }
            sfxVolume = PlayerPrefs.GetFloat("sfxVolume", sfxVolume);
        }

        AudioSource MusicSource()
        {
            var m = gameObject.AddComponent<AudioSource>();
            m.loop = true;
            m.playOnAwake = false;
            m.spatialBlend = 0f;
            return m;
        }

        static float MusicTarget => Lib != null ? Lib.musicVolume * PlayerPrefs.GetFloat("musicVolume", 1f) : 0.4f;

        void Update()
        {
            if (_fadeT >= 1f) return;
            _fadeT = Mathf.Min(1f, _fadeT + Time.unscaledDeltaTime / Mathf.Max(0.01f, _fadeTime));
            float target = MusicTarget;
            _music.volume = target * _fadeT;
            _musicB.volume = target * (1f - _fadeT);
            if (_fadeT >= 1f) _musicB.Stop();
        }

        public static AudioLibrary Lib => GameDatabase.Instance != null ? GameDatabase.Instance.audio : null;

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
            src.volume = volume * I.sfxVolume;
            src.Play();
        }

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
            src.volume = volume * sfxVolume;
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
                I._music.volume = MusicTarget;
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

        public static void SetMusicVolume(float v)
        {
            PlayerPrefs.SetFloat("musicVolume", v);
            if (Instance != null && Lib != null && Instance._fadeT >= 1f) Instance._music.volume = Lib.musicVolume * v;
        }

        public static void SetSfxVolume(float v)
        {
            PlayerPrefs.SetFloat("sfxVolume", v);
            if (Instance != null) Instance.sfxVolume = v;
        }

        public static void StopMusic()
        {
            if (Instance != null) { Instance._music.Stop(); Instance._musicB.Stop(); Instance._fadeT = 1f; }
        }
    }
}
