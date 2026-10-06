using UnityEngine;
using UnityEngine.InputSystem;

namespace MultiBash
{
    /// <summary>
    /// Reads keyboard / mouse / gamepad every frame and hands Fusion a snapshot each tick.
    /// Button presses are latched so a quick tap between ticks is never lost.
    /// </summary>
    public class LocalInput : MonoBehaviour
    {
        public static LocalInput Instance { get; private set; }

        /// <summary>Set by UI when a text field has focus or a menu is open.</summary>
        public static bool Blocked;

        bool _jumpLatched, _slideLatched;

        void Awake() => Instance = this;

        void Update()
        {
            if (Blocked) return;
            var kb = Keyboard.current;
            var pad = Gamepad.current;
            if ((kb != null && kb.spaceKey.wasPressedThisFrame) || (pad != null && pad.buttonSouth.wasPressedThisFrame)) _jumpLatched = true;
            if ((kb != null && (kb.leftCtrlKey.wasPressedThisFrame || kb.leftShiftKey.wasPressedThisFrame || kb.cKey.wasPressedThisFrame))
                || (pad != null && pad.buttonEast.wasPressedThisFrame)) _slideLatched = true;
        }

        public static Vector2 ReadMoveRaw()
        {
            if (Blocked) return Vector2.zero;
            Vector2 v = Vector2.zero;
            var kb = Keyboard.current;
            if (kb != null)
            {
                if (kb.wKey.isPressed || kb.upArrowKey.isPressed) v.y += 1;
                if (kb.sKey.isPressed || kb.downArrowKey.isPressed) v.y -= 1;
                if (kb.dKey.isPressed || kb.rightArrowKey.isPressed) v.x += 1;
                if (kb.aKey.isPressed || kb.leftArrowKey.isPressed) v.x -= 1;
            }
            var pad = Gamepad.current;
            if (pad != null)
            {
                var s = pad.leftStick.ReadValue();
                if (s.sqrMagnitude > 0.04f) v += s;
            }
            return Vector2.ClampMagnitude(v, 1f);
        }

        public NetworkInputData Collect()
        {
            var data = new NetworkInputData();
            if (AutoPilot.Enabled)
            {
                data.Move = AutoPilot.Steer(out bool j, out bool s);
                data.Buttons.Set(InputButton.Jump, j || _jumpLatched);
                data.Buttons.Set(InputButton.Slide, s || _slideLatched);
                _jumpLatched = _slideLatched = false;
                return data;
            }
            var raw = ReadMoveRaw();
            float yaw = CameraRig.Instance != null ? CameraRig.Instance.Yaw : 0f;
            var world = Quaternion.Euler(0, yaw, 0) * new Vector3(raw.x, 0, raw.y);
            data.Move = new Vector2(world.x, world.z);
            data.Buttons.Set(InputButton.Jump, _jumpLatched);
            data.Buttons.Set(InputButton.Slide, _slideLatched);
            _jumpLatched = false;
            _slideLatched = false;
            return data;
        }
    }
}
