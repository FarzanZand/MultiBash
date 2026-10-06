using System.Collections.Generic;
using UnityEngine;

namespace MultiBash
{
    /// <summary>
    /// Bounce pad (giant mushroom, steam vent, frost geyser): step on it and get launched high into the air with a
    /// burst of speed. Pure scene data, so every peer predicts the same launch (PlayerCharacter checks <see cref="Find"/>).
    /// </summary>
    public class JumpPad : MonoBehaviour
    {
        public static readonly List<JumpPad> All = new();

        public float radius = 1.4f;
        [Tooltip("Upward launch speed (a normal jump is ~9).")]
        public float launch = 21f;
        [Tooltip("Extra horizontal speed while airborne after the launch (x move speed).")]
        public float boost = 1.6f;
        public Color color = new(1f, 0.6f, 0.9f);
        public AudioClip sound;
        [Tooltip("Optional part that squashes when someone bounces (mushroom cap).")]
        public Transform squash;

        float _squashT = 1f;
        Vector3 _squashBase;

        void OnEnable() { All.Add(this); if (squash) _squashBase = squash.localScale; }
        void OnDisable() => All.Remove(this);

        public static JumpPad Find(Vector3 pos)
        {
            foreach (var p in All)
            {
                var d = pos - p.transform.position;
                if (d.y > -0.6f && d.y < 1.6f && d.x * d.x + d.z * d.z < p.radius * p.radius) return p;
            }
            return null;
        }

        /// <summary>Visual + audio feedback (called from PlayerCharacter.Render when a launch happens).</summary>
        public void Bounced(bool local)
        {
            _squashT = 0f;
            var fx = FxManager.Instance;
            if (fx != null)
            {
                fx.Burst(transform.position + Vector3.up * 0.6f, color, 22, 7f, 0.3f, 0.6f, 4f, true);
                fx.Shockwave(transform.position + Vector3.up * 0.1f, radius * 2.2f, color, false);
                fx.Dust(transform.position, 5);
            }
            if (sound != null) AudioManager.Play(sound, transform.position, local ? 0.9f : 0.5f, Random.Range(0.95f, 1.08f));
        }

        void Update()
        {
            if (squash == null || _squashT >= 1f) return;
            _squashT = Mathf.Min(1f, _squashT + Time.deltaTime * 3f);
            float k = Mathf.Sin(_squashT * Mathf.PI * 3f) * (1f - _squashT) * 0.35f;
            squash.localScale = new Vector3(_squashBase.x * (1f + k), _squashBase.y * (1f - k), _squashBase.z * (1f + k));
        }
    }
}
