using System;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.InputSystem.UI;
using UnityEngine.UI;

namespace MultiBash
{
    public enum UIFont { Body, Header, Number }

    /// <summary>
    /// Tiny helper for building pixel-art uGUI layouts from code, styled by UITheme.
    /// Frames are 9-sliced pixel sprites drawn at 3 screen pixels per texel (reference 1920x1080).
    /// </summary>
    public static class UIKit
    {
        public static UITheme T => UITheme.Instance;

        public static Canvas Canvas(string name, int order, Transform parent = null)
        {
            EnsureEventSystem();
            var go = new GameObject(name, typeof(Canvas), typeof(CanvasScaler), typeof(GraphicRaycaster));
            if (parent != null) go.transform.SetParent(parent, false);
            var c = go.GetComponent<Canvas>();
            c.renderMode = RenderMode.ScreenSpaceOverlay;
            c.sortingOrder = order;
            c.pixelPerfect = true;
            var s = go.GetComponent<CanvasScaler>();
            s.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
            s.referenceResolution = new Vector2(1920, 1080);
            s.matchWidthOrHeight = 0.5f;
            s.referencePixelsPerUnit = 100;
            return c;
        }

        public static void EnsureEventSystem()
        {
            if (EventSystem.current != null) return;
            var es = new GameObject("EventSystem", typeof(EventSystem), typeof(InputSystemUIInputModule));
            UnityEngine.Object.DontDestroyOnLoad(es);
        }

        public static Font FontOf(UIFont f) => f switch
        {
            UIFont.Header => T.headerFont != null ? T.headerFont : T.bodyFont,
            UIFont.Number => T.numberFont != null ? T.numberFont : T.bodyFont,
            _ => T.bodyFont,
        };

        // ------------------------------------------------------------------ layout primitives

        public static RectTransform Rect(Transform parent, string name, Vector2 anchorMin, Vector2 anchorMax, Vector2 offsetMin = default, Vector2 offsetMax = default)
        {
            var go = new GameObject(name, typeof(RectTransform));
            var rt = (RectTransform)go.transform;
            rt.SetParent(parent, false);
            rt.anchorMin = anchorMin;
            rt.anchorMax = anchorMax;
            rt.offsetMin = offsetMin;
            rt.offsetMax = offsetMax;
            return rt;
        }

        /// <summary>Anchored box of a fixed size. pivot/anchor share the same point.</summary>
        public static RectTransform Box(Transform parent, string name, Vector2 anchor, Vector2 pos, Vector2 size)
        {
            var rt = Rect(parent, name, anchor, anchor);
            rt.pivot = anchor;
            rt.anchoredPosition = pos;
            rt.sizeDelta = size;
            return rt;
        }

        public static RectTransform Stretch(Transform parent, string name, float pad = 0f) =>
            Rect(parent, name, Vector2.zero, Vector2.one, new Vector2(pad, pad), new Vector2(-pad, -pad));

        public static Image AddImage(RectTransform rt, Sprite sprite, Color color)
        {
            var img = rt.gameObject.AddComponent<Image>();
            img.sprite = sprite;
            img.color = color;
            img.type = sprite != null && sprite.border.sqrMagnitude > 0 ? UnityEngine.UI.Image.Type.Sliced : UnityEngine.UI.Image.Type.Simple;
            img.raycastTarget = false;
            return img;
        }

        public static Image Image(Transform parent, string name, Sprite sprite, Color color, bool sliced = true)
        {
            var rt = Stretch(parent, name);
            var img = AddImage(rt, sprite, color);
            if (!sliced) img.type = UnityEngine.UI.Image.Type.Simple;
            return img;
        }

        /// <summary>Metal-framed pixel window. With a title, a darker title strip is added at the top.</summary>
        public static RectTransform Panel(Transform parent, string name, Vector2 anchor, Vector2 pos, Vector2 size, string title = null)
        {
            var rt = Box(parent, name, anchor, pos, size);
            AddImage(rt, T.panel, Color.white);
            if (!string.IsNullOrEmpty(title))
            {
                var bar = Box(rt, "TitleBar", new Vector2(0.5f, 1), new Vector2(0, 0), new Vector2(size.x, 66));
                AddImage(bar, T.titleBar, Color.white);
                Label(bar, title, 36, T.text, new Vector2(0, 0.5f), new Vector2(28, -2), new Vector2(size.x - 56, 54), TextAnchor.MiddleLeft, UIFont.Header);
            }
            return rt;
        }

        /// <summary>Recessed dark slot (for icons, inputs).</summary>
        public static Image Slot(RectTransform rt) => AddImage(rt, T.slot, Color.white);

        // ------------------------------------------------------------------ text

        public static Text Text(Transform parent, string name, string text, int size, Color color, TextAnchor align = TextAnchor.MiddleCenter, UIFont font = UIFont.Body, bool shadow = true)
        {
            var rt = Stretch(parent, name);
            return SetupText(rt, text, size, color, align, font, shadow);
        }

        public static Text Label(Transform parent, string text, int size, Color color, Vector2 anchor, Vector2 pos, Vector2 boxSize,
            TextAnchor align = TextAnchor.MiddleCenter, UIFont font = UIFont.Body, bool shadow = true)
        {
            var rt = Box(parent, "Label", anchor, pos, boxSize);
            return SetupText(rt, text, size, color, align, font, shadow);
        }

        static Text SetupText(RectTransform rt, string text, int size, Color color, TextAnchor align, UIFont font, bool shadow)
        {
            var t = rt.gameObject.AddComponent<Text>();
            t.font = FontOf(font);
            t.text = text;
            // the body pixel font is wide: shrink it and snap to its 8px design grid so it stays crisp
            if (font != UIFont.Number) size = Mathf.Max(16, Mathf.RoundToInt(size * 0.75f / 8f) * 8);
            t.fontSize = size;
            t.color = color;
            t.alignment = align;
            t.supportRichText = true;
            t.horizontalOverflow = HorizontalWrapMode.Wrap;
            t.verticalOverflow = VerticalWrapMode.Overflow;
            t.raycastTarget = false;
            t.lineSpacing = 0.9f;
            if (shadow)
            {
                var s = rt.gameObject.AddComponent<Shadow>();
                s.effectColor = new Color(0, 0, 0, 0.9f);
                s.effectDistance = new Vector2(3, -3);
            }
            return t;
        }

        /// <summary>Adds a hard black pixel outline (for text over the 3D world).</summary>
        public static void Outline(Graphic g, float px = 3f)
        {
            var o = g.gameObject.AddComponent<Outline>();
            o.effectColor = Color.black;
            o.effectDistance = new Vector2(px, -px);
        }

        // ------------------------------------------------------------------ controls

        public static Button Button(Transform parent, string label, Vector2 anchor, Vector2 pos, Vector2 size, Action onClick, Color? color = null, int fontSize = 36)
        {
            var rt = Box(parent, "Btn_" + label, anchor, pos, size);
            var img = rt.gameObject.AddComponent<Image>();
            img.sprite = T.button;
            img.type = UnityEngine.UI.Image.Type.Sliced;
            img.color = color ?? T.buttonGrey;
            var b = rt.gameObject.AddComponent<Button>();
            b.targetGraphic = img;
            var colors = b.colors;
            colors.normalColor = Color.white;
            colors.highlightedColor = new Color(1.25f, 1.25f, 1.25f);
            colors.selectedColor = Color.white;
            colors.pressedColor = new Color(0.75f, 0.75f, 0.75f);
            colors.disabledColor = new Color(0.4f, 0.4f, 0.4f, 0.75f);
            colors.colorMultiplier = 1.3f;
            colors.fadeDuration = 0.05f;
            b.colors = colors;
            var t = Text(rt, "Text", label, fontSize, Color.white, TextAnchor.MiddleCenter, UIFont.Header);
            t.rectTransform.offsetMin = new Vector2(6, 6);
            t.rectTransform.offsetMax = new Vector2(-6, 0);
            b.onClick.AddListener(() =>
            {
                var lib = AudioManager.Lib;
                if (lib != null) AudioManager.PlayUI(lib.click, 0.7f);
                onClick?.Invoke();
            });
            rt.gameObject.AddComponent<HoverSound>();
            return b;
        }

        public static InputField Input(Transform parent, string placeholder, Vector2 anchor, Vector2 pos, Vector2 size, int fontSize = 32)
        {
            var rt = Box(parent, "Input", anchor, pos, size);
            var img = rt.gameObject.AddComponent<Image>();
            img.sprite = T.slot;
            img.type = UnityEngine.UI.Image.Type.Sliced;
            img.color = Color.white;
            var field = rt.gameObject.AddComponent<InputField>();
            var textRt = Stretch(rt, "Text", 0);
            textRt.offsetMin = new Vector2(18, 4);
            textRt.offsetMax = new Vector2(-18, -4);
            var text = textRt.gameObject.AddComponent<Text>();
            text.font = FontOf(UIFont.Number);
            text.fontSize = fontSize;
            text.color = T.text;
            text.alignment = TextAnchor.MiddleLeft;
            text.supportRichText = false;
            var phRt = Stretch(rt, "Placeholder", 0);
            phRt.offsetMin = new Vector2(18, 4);
            phRt.offsetMax = new Vector2(-18, -4);
            var ph = phRt.gameObject.AddComponent<Text>();
            ph.font = FontOf(UIFont.Body);
            ph.fontSize = 27;
            ph.color = new Color(1, 1, 1, 0.35f);
            ph.text = placeholder;
            ph.alignment = TextAnchor.MiddleLeft;
            field.textComponent = text;
            field.placeholder = ph;
            field.targetGraphic = img;
            field.caretWidth = 3;
            field.customCaretColor = true;
            field.caretColor = T.accent;
            return field;
        }

        /// <summary>Hard-edged pixel bar: black frame, flat fill.</summary>
        public static (Image bg, Image fill) Bar(Transform parent, string name, Vector2 anchor, Vector2 pos, Vector2 size, Color fillColor)
        {
            var rt = Box(parent, name, anchor, pos, size);
            var bg = AddImage(rt, T.roundRect, new Color(0.02f, 0.02f, 0.03f, 0.92f));
            var fillRt = Stretch(rt, "Fill", 3);
            var fill = fillRt.gameObject.AddComponent<Image>();
            fill.sprite = T.roundRect;
            fill.color = fillColor;
            fill.type = UnityEngine.UI.Image.Type.Filled;
            fill.fillMethod = UnityEngine.UI.Image.FillMethod.Horizontal;
            fill.fillOrigin = 0;
            fill.fillAmount = 1f;
            fill.raycastTarget = false;
            return (bg, fill);
        }

        public static string FormatTime(float seconds)
        {
            int s = Mathf.Max(0, Mathf.FloorToInt(seconds));
            return $"{s / 60}:{s % 60:00}";
        }

        public static string Hex(Color c) => ColorUtility.ToHtmlStringRGB(c);
    }
}
