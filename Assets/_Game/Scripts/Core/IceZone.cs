using System.Collections.Generic;
using UnityEngine;

namespace MultiBash
{
    /// <summary>Slippery ice (frozen lakes): low grip, long glides. Circles in the scene, checked by PlayerCharacter on every peer.</summary>
    public class IceZone : MonoBehaviour
    {
        public static readonly List<IceZone> All = new();
        public float radiusX = 10f, radiusZ = 8f;

        void OnEnable() => All.Add(this);
        void OnDisable() => All.Remove(this);

        public static bool On(Vector3 pos)
        {
            foreach (var z in All)
            {
                var d = z.transform.InverseTransformPoint(pos);
                float x = d.x / z.radiusX, y = d.z / z.radiusZ;
                if (x * x + y * y < 1f && Mathf.Abs(d.y) < 1.5f) return true;
            }
            return false;
        }
    }
}
