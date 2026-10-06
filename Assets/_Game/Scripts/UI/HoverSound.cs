using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

namespace MultiBash
{
    /// <summary>Plays the UI hover tick when the pointer enters an interactable control.</summary>
    public class HoverSound : MonoBehaviour, IPointerEnterHandler
    {
        public void OnPointerEnter(PointerEventData eventData)
        {
            var b = GetComponent<Selectable>();
            if (b != null && !b.interactable) return;
            var lib = AudioManager.Lib;
            if (lib != null) AudioManager.PlayUI(lib.hover, 0.35f);
        }
    }
}
