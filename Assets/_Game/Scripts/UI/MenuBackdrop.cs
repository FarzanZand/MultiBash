using UnityEngine;

namespace MultiBash
{
    /// <summary>Slowly orbits the menu camera around a point so the title screen feels alive.</summary>
    public class MenuBackdrop : MonoBehaviour
    {
        public Transform pivot;
        public float speed = 4f;
        public float distance = 9f;
        public float height = 3.2f;
        public Vector3 lookOffset = new(0, 1.2f, 0);
        public float sway = 25f;

        float _t;

        void LateUpdate()
        {
            _t += Time.deltaTime;
            var center = pivot != null ? pivot.position : Vector3.zero;
            float a = Mathf.Sin(_t * speed * 0.02f) * sway + 180f;
            var dir = Quaternion.Euler(0, a, 0) * Vector3.forward;
            transform.position = center + dir * distance + Vector3.up * height;
            transform.LookAt(center + lookOffset);
        }
    }
}
