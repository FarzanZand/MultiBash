using Fusion;
using UnityEngine;

namespace MultiBash
{
    public enum InputButton
    {
        Jump = 0,
        Slide = 1,
    }

    /// <summary>What each client sends to the host every tick.</summary>
    public struct NetworkInputData : INetworkInput
    {
        /// <summary>World-space move direction on the XZ plane (already rotated by the camera).</summary>
        public Vector2 Move;
        public NetworkButtons Buttons;
    }
}
