using UnityEngine;

namespace MultiBash
{
    /// <summary>Makes a point light flicker like a fire and bobs an optional flame mesh.</summary>
    public class FireFlicker : MonoBehaviour
    {
        public Light lightSource;
        public float baseIntensity = 3f;
        public float amount = 0.35f;
        public float speed = 9f;
        float _seed;

        void Awake()
        {
            _seed = Random.value * 100f;
            if (lightSource == null) lightSource = GetComponentInChildren<Light>();
            if (lightSource != null) baseIntensity = lightSource.intensity;
        }

        void Update()
        {
            if (lightSource == null) return;
            float n = Mathf.PerlinNoise(_seed, Time.time * speed) - 0.5f;
            lightSource.intensity = baseIntensity * (1f + n * amount * 2f);
        }
    }
}
