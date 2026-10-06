using UnityEngine;

namespace MultiBash
{
    /// <summary>
    /// Lava surface for a level: anything (player) standing below Level + margin burns.
    /// Put one in a scene with a lava plane at the same height. Enemies are immune (they live here).
    /// </summary>
    public class LavaZone : MonoBehaviour
    {
        public static float Level = float.NaN;
        public static float DamagePerSecond = 22f;

        [Tooltip("World height of the lava surface.")]
        public float level = 0.5f;
        public float damagePerSecond = 22f;
        [Tooltip("UV scroll speed of the lava texture.")]
        public Vector2 flow = new(0.02f, 0.012f);

        Renderer _renderer;

        void Awake()
        {
            Level = level;
            DamagePerSecond = damagePerSecond;
            _renderer = GetComponent<Renderer>();
        }

        void OnDestroy()
        {
            if (Mathf.Approximately(Level, level)) Level = float.NaN;
        }

        /// <summary>True if a point (feet position) is standing in lava.</summary>
        public static bool InLava(Vector3 feet) => !float.IsNaN(Level) && feet.y < Level + 0.3f;

        void Update()
        {
            if (_renderer != null) _renderer.sharedMaterial.SetVector("_Flow", flow);
        }
    }
}
