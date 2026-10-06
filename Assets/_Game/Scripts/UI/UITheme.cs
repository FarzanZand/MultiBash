using UnityEngine;

namespace MultiBash
{
    /// <summary>Fonts, pixel sprites and colors for every menu and the HUD. Edit Content/Resources/UITheme.asset to restyle.</summary>
    [CreateAssetMenu(menuName = "MultiBash/UI Theme", fileName = "UITheme", order = 13)]
    public class UITheme : ScriptableObject
    {
        [Header("Fonts (pixel fonts look best at multiples of their design size)")]
        [Tooltip("Gothic pixel font for titles and most text (Jacquarda Bastarda 9: use sizes 18, 27, 36, 45, 54, 72...).")]
        public Font headerFont;
        public Font bodyFont;
        [Tooltip("Chunky pixel font for numbers (Silkscreen: sizes 16, 24, 32, 40, 48...).")]
        public Font numberFont;

        [Header("Sprites (pixel art, 9-sliced)")]
        public Sprite panel;
        public Sprite titleBar;
        public Sprite roundRect;
        public Sprite button;
        public Sprite card;
        public Sprite slot;
        public Sprite outline;
        public Sprite circle;
        public Sprite glow;
        public Sprite gradient;
        public Sprite arrow;
        public Sprite clock;
        public Sprite skull;
        public Sprite heart;
        public Sprite lockIcon;
        public Sprite star;

        [Header("Colors")]
        public Color text = new(0.96f, 0.95f, 0.9f);
        public Color mutedText = new(0.68f, 0.72f, 0.7f);
        public Color accent = new(1f, 0.82f, 0.25f);
        public Color good = new(0.45f, 1f, 0.45f);
        public Color bad = new(1f, 0.3f, 0.25f);
        public Color health = new(0.9f, 0.1f, 0.1f);
        public Color xp = new(0.15f, 0.65f, 1f);
        public Color buttonBlue = new(0.25f, 0.5f, 0.85f);
        public Color buttonGrey = new(0.45f, 0.5f, 0.5f);
        public Color buttonRed = new(0.8f, 0.22f, 0.2f);
        public Color buttonGreen = new(0.25f, 0.65f, 0.3f);
        public Color common = new(0.2f, 0.55f, 0.28f);
        public Color rare = new(0.18f, 0.38f, 0.8f);
        public Color epic = new(0.55f, 0.2f, 0.75f);

        static UITheme _instance;
        public static UITheme Instance
        {
            get
            {
                if (_instance == null) _instance = Resources.Load<UITheme>("UITheme");
                return _instance;
            }
        }

        public Color RarityColor(Rarity r) => r switch
        {
            Rarity.Rare => rare,
            Rarity.Epic => epic,
            Rarity.Legendary => new Color(0.85f, 0.5f, 0.08f),
            _ => common,
        };

        public static string RarityName(Rarity r) => r switch
        {
            Rarity.Rare => "Rare",
            Rarity.Epic => "Epic",
            Rarity.Legendary => "Legendary",
            _ => "Common",
        };
    }
}
