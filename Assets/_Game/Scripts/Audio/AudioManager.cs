using System.Collections.Generic;
using UnityEngine;

namespace MultiBash
{
    /// <summary>
    /// Pooled one-shot SFX + music. Limits how many copies of the same clip can play at once,
    /// so 200 skeletons dying at once doesn't turn into noise.
    /// </summary>
    public class AudioManager : MonoBehaviour
    {
        public static AudioManager Instance { get; private set; }

        [SerializeField] int voices = 32;
        [SerializeField] int maxSameClip = 4;
        [SerializeField] float sameClipMinInterval = 0.035f;
        [Range(0, 1)] public float sfxVolume = 0.8f;

        readonly List<AudioSource> _pool = new();
        readonly Dictionary<AudioClip, float> _lastPlayed = new();
        AudioSource _music;
        AudioSource _ui;
        int _next;

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
            _music = gameObject.AddComponent<AudioSource>();
            _music.loop = true;
            _music.playOnAwake = false;
            _music.spatialBlend = 0f;
            _ui = gameObject.AddComponent<AudioSource>();
            _ui.playOnAwake = false;
            _ui.spatialBlend = 0f;
            sfxVolume = PlayerPrefs.GetFloat("sfxVolume", sfxVolume);
        }

        public static AudioLibrary Lib => GameDatabase.Instance != null ? GameDatabase.Instance.audio : null;

        public static void PlayUI(AudioClip clip, float volume = 1f, float pitch = 1f)
        {
            if (Instance == null || clip == null) return;
            Instance._ui.pitch = pitch;
            Instance._ui.PlayOneShot(clip, volume * Instance.sfxVolume);
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

        public static void PlayMusic(AudioClip clip)
        {
            if (Instance == null || clip == null) return;
            var m = Instance._music;
            if (m.clip == clip && m.isPlaying) return;
            m.clip = clip;
            m.volume = Lib != null ? Lib.musicVolume * PlayerPrefs.GetFloat("musicVolume", 1f) : 0.4f;
            m.Play();
        }

        public static void SetMusicVolume(float v)
        {
            PlayerPrefs.SetFloat("musicVolume", v);
            if (Instance != null && Lib != null) Instance._music.volume = Lib.musicVolume * v;
        }

        public static void SetSfxVolume(float v)
        {
            PlayerPrefs.SetFloat("sfxVolume", v);
            if (Instance != null) Instance.sfxVolume = v;
        }

        public static void StopMusic()
        {
            if (Instance != null) Instance._music.Stop();
        }
    }
}
