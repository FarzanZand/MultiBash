using UnityEngine;
using UnityEngine.InputSystem;

namespace MultiBash
{
    /// <summary>
    /// Third-person orbit camera. Mouse / right stick rotates around the local hero, scroll zooms.
    /// Spectates teammates when your hero is dead. The movement input is relative to this camera's yaw.
    /// </summary>
    public class CameraRig : MonoBehaviour
    {
        public static CameraRig Instance { get; private set; }

        public Camera cam;
        public float distance = 8.5f;
        public float minDistance = 4f;
        public float maxDistance = 18f;
        public float pitch = 20f;
        public float minPitch = -15f;
        public float maxPitch = 75f;
        public float followSharpness = 14f;
        public Vector3 lookOffset = new(0, 1.9f, 0);

        public float Yaw { get; private set; }
        public static float Sensitivity
        {
            get => PlayerPrefs.GetFloat("mouseSensitivity", 1f);
            set => PlayerPrefs.SetFloat("mouseSensitivity", value);
        }

        PlayerCharacter _target;
        Vector3 _focus;
        float _shake;
        int _spectateIndex;

        void Awake()
        {
            Instance = this;
            if (cam == null) cam = GetComponentInChildren<Camera>();
            Yaw = transform.eulerAngles.y;
        }

        void OnDestroy()
        {
            if (Instance == this) Instance = null;
            Cursor.lockState = CursorLockMode.None;
            Cursor.visible = true;
        }

        public void SetTarget(PlayerCharacter pc)
        {
            _target = pc;
            if (pc != null) _focus = pc.transform.position;
        }

        public void Shake(float amount) => _shake = Mathf.Max(_shake, amount);

        public static bool MenuOpen;

        void LateUpdate()
        {
            bool playing = !MenuOpen;
            Cursor.lockState = playing ? CursorLockMode.Locked : CursorLockMode.None;
            Cursor.visible = !playing;

            var follow = _target;
            if (follow == null || follow.Object == null || !follow.Object.IsValid)
            {
                follow = PlayerCharacter.Local;
                if (follow != null) _target = follow;
            }
            if (follow != null && follow.Dead)
            {
                // spectate a living teammate
                var all = PlayerCharacter.All;
                if (all.Count > 0)
                {
                    if (Keyboard.current != null && Keyboard.current.spaceKey.wasPressedThisFrame) _spectateIndex++;
                    for (int i = 0; i < all.Count; i++)
                    {
                        var p = all[(i + _spectateIndex) % all.Count];
                        if (p != null && !p.Dead) { follow = p; break; }
                    }
                }
            }

            if (playing)
            {
                var mouse = Mouse.current;
                float sens = Sensitivity;
                if (mouse != null)
                {
                    var d = mouse.delta.ReadValue();
                    Yaw += d.x * 0.12f * sens;
                    pitch = Mathf.Clamp(pitch - d.y * 0.1f * sens, minPitch, maxPitch);
                    float scroll = mouse.scroll.ReadValue().y;
                    if (Mathf.Abs(scroll) > 0.01f) distance = Mathf.Clamp(distance - Mathf.Sign(scroll) * 1.2f, minDistance, maxDistance);
                }
                var pad = Gamepad.current;
                if (pad != null)
                {
                    var r = pad.rightStick.ReadValue();
                    Yaw += r.x * 160f * sens * Time.deltaTime;
                    pitch = Mathf.Clamp(pitch - r.y * 90f * sens * Time.deltaTime, minPitch, maxPitch);
                }
            }

            if (follow != null)
                _focus = Vector3.Lerp(_focus, follow.transform.position, 1f - Mathf.Exp(-followSharpness * Time.deltaTime));

            var rot = Quaternion.Euler(pitch, Yaw, 0);
            var look = _focus + lookOffset;
            var camPos = look - rot * Vector3.forward * distance;
            // keep the camera above hills: if the ground pokes up between, pull in / lift
            float minY = Ground.Height(camPos) + 0.6f;
            // a ridge between the hero and the camera: lift the camera until the line of sight clears it
            for (float t = 0.2f; t < 1f; t += 0.1f)
            {
                var p = Vector3.Lerp(look, camPos, t);
                float h = Ground.TerrainHeight(p) + 0.45f;
                if (p.y < h) minY = Mathf.Max(minY, look.y + (h - look.y) / t);
            }
            _lift = Mathf.Max(minY - camPos.y, Mathf.Lerp(_lift, minY - camPos.y, 1f - Mathf.Exp(-4f * Time.deltaTime)));
            if (_lift > 0f)
            {
                camPos.y += _lift;
                rot = Quaternion.LookRotation(look - camPos);
            }
            transform.position = camPos;
            transform.rotation = rot;

            if (_shake > 0f)
            {
                transform.position += Random.insideUnitSphere * _shake * 0.4f;
                _shake = Mathf.MoveTowards(_shake, 0f, Time.deltaTime * 2.5f);
            }

            HideOccluders(look);
        }

        // ------------------------------------------------------------------ props between camera and hero become invisible (shadows stay)

        float _lift;
        readonly System.Collections.Generic.List<Renderer> _hidden = new();
        readonly System.Collections.Generic.HashSet<Renderer> _hitNow = new();
        readonly RaycastHit[] _hits = new RaycastHit[16];
        int _envMask;

        void HideOccluders(Vector3 look)
        {
            if (_envMask == 0) _envMask = LayerMask.GetMask("Environment");
            _hitNow.Clear();
            var from = transform.position;
            var to = look - Vector3.up * 0.4f;
            var dir = to - from;
            int n = Physics.SphereCastNonAlloc(from, 0.6f, dir.normalized, _hits, dir.magnitude - 1f, _envMask, QueryTriggerInteraction.Ignore);
            for (int i = 0; i < n; i++)
            {
                var col = _hits[i].collider;
                if (col == null || col.name == "Ground") continue;
                // climb to the prop's root (the child of the "Props" container)
                var root = col.transform;
                while (root.parent != null && root.parent.name != "Props") root = root.parent;
                if (root.name.StartsWith("Platform")) continue; // never hide what you're standing on
                foreach (var r in root.GetComponentsInChildren<Renderer>()) _hitNow.Add(r);
            }
            for (int i = _hidden.Count - 1; i >= 0; i--)
            {
                var r = _hidden[i];
                if (r == null) { _hidden.RemoveAt(i); continue; }
                if (!_hitNow.Contains(r))
                {
                    r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.On;
                    _hidden.RemoveAt(i);
                }
            }
            foreach (var r in _hitNow)
            {
                if (r.shadowCastingMode == UnityEngine.Rendering.ShadowCastingMode.ShadowsOnly) continue;
                r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.ShadowsOnly;
                _hidden.Add(r);
            }
        }
    }
}
