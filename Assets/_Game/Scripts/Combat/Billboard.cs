using UnityEngine;

namespace MultiBash
{
    /// <summary>Keeps a quad facing the camera (used for pickup glows).</summary>
    public class Billboard : MonoBehaviour
    {
        static Camera _cam;

        void LateUpdate()
        {
            if (_cam == null) _cam = Camera.main;
            if (_cam != null) transform.rotation = _cam.transform.rotation;
        }
    }
}
