using UnityEngine;

namespace MultiBash
{
    /// <summary>Spins a child part (windmill blades) around the object's forward axis.</summary>
    public class Spinner : MonoBehaviour
    {
        public string partName = "Blades";
        public float degreesPerSecond = 40f;
        Transform _part;
        Vector3 _axis;

        void Start()
        {
            foreach (var t in GetComponentsInChildren<Transform>())
                if (t.name == partName) { _part = t; break; }
            if (_part == null) return;
            // spin around the line from the building's centre out through the hub
            _axis = _part.position - transform.position;
            _axis.y = 0f;
            _axis = _axis.sqrMagnitude > 0.01f ? _axis.normalized : transform.forward;
        }

        void Update()
        {
            if (_part == null) return;
            _part.RotateAround(_part.position, _axis, degreesPerSecond * Time.deltaTime);
        }
    }
}
