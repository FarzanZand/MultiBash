using UnityEngine;

namespace MultiBash
{
    /// <summary>
    /// Lighting that follows the run's three stages (see ProgressionSettings.StageAt): stage 1 uses the scene as built,
    /// stages 2 and 3 blend to the moods set here over a few seconds (night falls, the volcano erupts, the blizzard
    /// rolls in). Purely visual and local: every peer derives the stage from the replicated run time.
    /// </summary>
    public class StageMood : MonoBehaviour
    {
        [System.Serializable]
        public struct Mood
        {
            public Color sun;
            public float sunIntensity;
            public Color fog;
            public float fogEnd;
            public Color ambientSky, ambientEquator, ambientGround;
            public Color skyTop, skyHorizon, clouds, moon;
            public float aurora, stars;
            [Tooltip("Ambient motes per second (embers, fireflies, snow).")]
            public float motes;
        }

        public Light sun;
        [Tooltip("Mood for stage 2 and stage 3.")]
        public Mood[] moods = new Mood[2];
        public float blendSeconds = 6f;

        Material _sky;
        Mood _base, _from, _to;
        int _stage;
        float _t = 1f;

        static readonly int Top = Shader.PropertyToID("_TopColor"), Hor = Shader.PropertyToID("_HorizonColor"), Cloud = Shader.PropertyToID("_CloudColor"),
            Moon = Shader.PropertyToID("_MoonColor"), Aur = Shader.PropertyToID("_Aurora"), Stars = Shader.PropertyToID("_StarDensity");

        void Start()
        {
            if (RenderSettings.skybox != null)
            {
                _sky = new Material(RenderSettings.skybox);   // never edit the shared asset at runtime
                RenderSettings.skybox = _sky;
            }
            _base = Capture();
            _from = _to = _base;
        }

        void OnDestroy()
        {
            if (_sky != null) Destroy(_sky);
        }

        Mood Capture()
        {
            var m = new Mood
            {
                sun = sun != null ? sun.color : Color.white, sunIntensity = sun != null ? sun.intensity : 1f,
                fog = RenderSettings.fogColor, fogEnd = RenderSettings.fogEndDistance,
                ambientSky = RenderSettings.ambientSkyColor, ambientEquator = RenderSettings.ambientEquatorColor, ambientGround = RenderSettings.ambientGroundColor,
                motes = FxManager.Instance != null ? FxManager.Instance.ambientRate : 20f,
            };
            if (_sky != null)
            {
                m.skyTop = _sky.GetColor(Top); m.skyHorizon = _sky.GetColor(Hor); m.clouds = _sky.GetColor(Cloud);
                m.moon = _sky.HasProperty(Moon) ? _sky.GetColor(Moon) : Color.white;
                m.aurora = _sky.HasProperty(Aur) ? _sky.GetFloat(Aur) : 0f;
                m.stars = _sky.HasProperty(Stars) ? _sky.GetFloat(Stars) : 0f;
            }
            return m;
        }

        void Update()
        {
            var gm = GameManager.Instance;
            int stage = gm != null && gm.Object != null && gm.Object.IsValid ? ProgressionManager.Settings.StageAt(gm.RunTime) : 0;
            if (stage != _stage)
            {
                _stage = stage;
                _from = Lerp(_from, _to, Smooth(_t));
                _to = stage == 0 || moods == null || moods.Length < stage ? _base : moods[stage - 1];
                _t = 0f;
            }
            if (_t >= 1f) return;
            _t = Mathf.Min(1f, _t + Time.deltaTime / Mathf.Max(0.1f, blendSeconds));
            Apply(Lerp(_from, _to, Smooth(_t)));
        }

        static float Smooth(float t) => t * t * (3f - 2f * t);

        static Mood Lerp(Mood a, Mood b, float t) => new()
        {
            sun = Color.Lerp(a.sun, b.sun, t), sunIntensity = Mathf.Lerp(a.sunIntensity, b.sunIntensity, t),
            fog = Color.Lerp(a.fog, b.fog, t), fogEnd = Mathf.Lerp(a.fogEnd, b.fogEnd, t),
            ambientSky = Color.Lerp(a.ambientSky, b.ambientSky, t), ambientEquator = Color.Lerp(a.ambientEquator, b.ambientEquator, t),
            ambientGround = Color.Lerp(a.ambientGround, b.ambientGround, t),
            skyTop = Color.Lerp(a.skyTop, b.skyTop, t), skyHorizon = Color.Lerp(a.skyHorizon, b.skyHorizon, t), clouds = Color.Lerp(a.clouds, b.clouds, t),
            moon = Color.Lerp(a.moon, b.moon, t), aurora = Mathf.Lerp(a.aurora, b.aurora, t), stars = Mathf.Lerp(a.stars, b.stars, t),
            motes = Mathf.Lerp(a.motes, b.motes, t),
        };

        void Apply(Mood m)
        {
            if (sun != null) { sun.color = m.sun; sun.intensity = m.sunIntensity; }
            RenderSettings.fogColor = m.fog;
            RenderSettings.fogEndDistance = m.fogEnd;
            RenderSettings.ambientSkyColor = m.ambientSky;
            RenderSettings.ambientEquatorColor = m.ambientEquator;
            RenderSettings.ambientGroundColor = m.ambientGround;
            var cam = Camera.main;
            if (cam != null) cam.backgroundColor = m.fog;
            if (_sky != null)
            {
                _sky.SetColor(Top, m.skyTop); _sky.SetColor(Hor, m.skyHorizon); _sky.SetColor(Cloud, m.clouds);
                if (_sky.HasProperty(Moon)) _sky.SetColor(Moon, m.moon);
                if (_sky.HasProperty(Aur)) _sky.SetFloat(Aur, m.aurora);
                if (_sky.HasProperty(Stars)) _sky.SetFloat(Stars, m.stars);
            }
            FxManager.Instance?.SetAmbientRate(m.motes);
        }
    }
}
