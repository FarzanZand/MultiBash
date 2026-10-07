using System.Collections.Generic;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.UI;

namespace MultiBash
{
    /// <summary>
    /// In-game HUD in Megabonk's pixel style: XP bar across the top, timer, kills, HP, weapon/tome rows with "LVL n",
    /// boss bar, teammates, "Upgrade Offers" window, announcements, downed overlay, pause and results windows.
    /// Built from code in Awake (styled by UITheme).
    /// </summary>
    public class HUD : MonoBehaviour
    {
        public static HUD Instance { get; private set; }

        UITheme T;
        RectTransform _root;

        // top
        Image _xpFill;
        Text _level, _timer, _elapsed, _kills;
        // boss
        RectTransform _boss;
        Text _bossName, _bossHp;
        Image _bossFill;
        // player
        Image _hpFill;
        Text _hpText;
        readonly List<(Image icon, Text level, RectTransform root)> _weaponSlots = new();
        readonly List<(Image icon, Text level, RectTransform root)> _powerSlots = new();
        RectTransform _feetBar;
        Image _feetFill;
        // teammates
        readonly List<(RectTransform root, Image portrait, Image hp, Text name, Text status)> _mates = new();
        // level-up
        RectTransform _levelUp;
        Text _levelUpTitle;
        readonly List<CardUI> _cards = new();
        float _choiceLock;
        Button _reroll, _skip;
        Text _rerollText;
        // pause: build overview with full tooltips
        RectTransform _build;
        readonly List<(RectTransform root, Image icon, Text title, Text body, Text tag)> _buildRows = new();
        Text _buildFooter;
        // overlays
        Image _damageFlash, _downedVignette;
        Text _downedText, _announce, _countdown, _combo, _frenzy, _mapTitle, _mapSub;
        int _shownCombo;
        float _comboPunch, _frenzyT = 99f;
        float _announceT = 99f;
        // pause / results
        RectTransform _pause, _results;
        Text _resultsTitle, _resultsBody, _resultsFooter;
        readonly List<Text[]> _resultRows = new();
        Button _resultsLobby;
        // world labels for teammates
        readonly Dictionary<PlayerCharacter, (RectTransform rt, Text text, Image bar)> _tags = new();
        RectTransform _tagLayer;

        class CardUI
        {
            public RectTransform root;
            public Image bg, iconBack, icon;
            public Text rarity, title, level, body, key;
            public Button button;
        }

        void Awake()
        {
            Instance = this;
            T = UIKit.T;
            // the menu / lobby leave the camera in "menu" mode (free cursor, no orbit): a run starts in play mode
            CameraRig.MenuOpen = false;
            LocalInput.Blocked = false;
            Build();
        }

        void OnDestroy()
        {
            if (Instance == this) Instance = null;
            CameraRig.MenuOpen = false;
            LocalInput.Blocked = false;
        }

        static Text Outlined(Text t, float px = 3f)
        {
            UIKit.Outline(t, px);
            return t;
        }

        // ================================================================== build

        void Build()
        {
            var canvas = UIKit.Canvas("HUDCanvas", 20, transform);
            _root = (RectTransform)canvas.transform;
            _tagLayer = UIKit.Stretch(_root, "WorldTags");

            _damageFlash = UIKit.Image(_root, "DamageFlash", T.gradient, new Color(0.8f, 0.05f, 0.05f, 0f), false);
            _damageFlash.rectTransform.localScale = new Vector3(1, -1, 1); // red from the bottom up
            _downedVignette = UIKit.Image(_root, "Downed", null, new Color(0.25f, 0f, 0f, 0f));

            // ---- XP bar across the very top + level
            var xp = UIKit.Bar(_root, "XPBar", new Vector2(0.5f, 1), Vector2.zero, new Vector2(1920, 22), T.xp);
            xp.bg.rectTransform.anchorMin = new Vector2(0, 1);
            xp.bg.rectTransform.anchorMax = new Vector2(1, 1);
            xp.bg.rectTransform.sizeDelta = new Vector2(0, 22);
            _xpFill = xp.fill;
            _level = Outlined(UIKit.Label(_root, "LVL 1", 48, T.text, new Vector2(1, 1), new Vector2(-30, -30), new Vector2(360, 60), TextAnchor.UpperRight, UIFont.Number, false));

            // ---- timer (time left) + elapsed + kills
            _timer = Outlined(UIKit.Label(_root, "10:00", 64, T.text, new Vector2(0.5f, 1), new Vector2(0, -30), new Vector2(400, 76), TextAnchor.UpperCenter, UIFont.Number, false), 4);
            var clock = UIKit.Box(_root, "ClockIcon", new Vector2(0, 1), new Vector2(26, -36), new Vector2(36, 36));
            UIKit.AddImage(clock, T.clock, Color.white);
            _elapsed = Outlined(UIKit.Label(_root, "0:00", 32, T.text, new Vector2(0, 1), new Vector2(72, -36), new Vector2(150, 40), TextAnchor.MiddleLeft, UIFont.Number, false));
            var skull = UIKit.Box(_root, "SkullIcon", new Vector2(0, 1), new Vector2(230, -36), new Vector2(36, 36));
            UIKit.AddImage(skull, T.skull, Color.white);
            _kills = Outlined(UIKit.Label(_root, "0", 32, T.text, new Vector2(0, 1), new Vector2(276, -36), new Vector2(200, 40), TextAnchor.MiddleLeft, UIFont.Number, false));

            // ---- boss bar (under the timer)
            _boss = UIKit.Box(_root, "BossBar", new Vector2(0.5f, 1), new Vector2(0, -108), new Vector2(1200, 92));
            _bossName = Outlined(UIKit.Label(_boss, "", 45, T.text, new Vector2(0.5f, 1), Vector2.zero, new Vector2(1200, 54), TextAnchor.MiddleCenter, UIFont.Header, false));
            var bb = UIKit.Bar(_boss, "HP", new Vector2(0.5f, 0), Vector2.zero, new Vector2(1200, 32), new Color(0.85f, 0.08f, 0.08f));
            _bossFill = bb.fill;
            _bossHp = UIKit.Label(bb.bg.rectTransform, "", 18, Color.white, new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(400, 30), TextAnchor.MiddleCenter, UIFont.Number);
            _boss.gameObject.SetActive(false);

            // ---- HP bar + weapon / tome rows (top-left)
            var hp = UIKit.Bar(_root, "HP", new Vector2(0, 1), new Vector2(26, -84), new Vector2(330, 34), T.health);
            _hpFill = hp.fill;
            _hpText = UIKit.Label(hp.bg.rectTransform, "100/100", 24, Color.white, new Vector2(0.5f, 0.5f), new Vector2(0, -1), new Vector2(320, 30), TextAnchor.MiddleCenter, UIFont.Number);
            for (int i = 0; i < PlayerCharacter.MaxWeaponSlots; i++)
                _weaponSlots.Add(Slot(new Vector2(26 + i * 82, -132), 66));
            for (int i = 0; i < 6; i++)
                _powerSlots.Add(Slot(new Vector2(26 + i * 64, -236), 52));

            // ---- teammates (right, under the level)
            for (int i = 0; i < 3; i++)
            {
                var rt = UIKit.Box(_root, "Mate" + i, new Vector2(1, 1), new Vector2(-30, -110 - i * 82), new Vector2(340, 72));
                UIKit.Slot(rt);
                var mp = UIKit.Box(rt, "Portrait", new Vector2(0, 0.5f), new Vector2(8, 0), new Vector2(56, 56));
                var mpi = UIKit.AddImage(mp, null, Color.white);
                mpi.preserveAspect = true;
                var mn = UIKit.Label(rt, "", 32, T.text, new Vector2(0, 1), new Vector2(74, -4), new Vector2(250, 36), TextAnchor.UpperLeft, UIFont.Header);
                var mbar = UIKit.Bar(rt, "HP", new Vector2(0, 0), new Vector2(74, 10), new Vector2(252, 18), T.health);
                var ms = UIKit.Label(rt, "", 22, T.bad, new Vector2(1, 1), new Vector2(-10, -8), new Vector2(150, 26), TextAnchor.UpperRight, UIFont.Number);
                _mates.Add((rt, mpi, mbar.fill, mn, ms));
            }

            // ---- HP bar under your own hero (like Megabonk)
            _feetBar = UIKit.Box(_root, "FeetHP", new Vector2(0, 0), Vector2.zero, new Vector2(120, 14));
            _feetBar.pivot = new Vector2(0.5f, 0.5f);
            UIKit.AddImage(_feetBar, T.roundRect, new Color(0, 0, 0, 0.85f));
            var ff = UIKit.Stretch(_feetBar, "Fill", 2);
            _feetFill = UIKit.AddImage(ff, T.roundRect, T.health);
            _feetFill.type = Image.Type.Filled;
            _feetFill.fillMethod = Image.FillMethod.Horizontal;

            BuildUpgradeWindow();

            // ---- center texts
            _announce = Outlined(UIKit.Label(_root, "", 72, T.accent, new Vector2(0.5f, 0.5f), new Vector2(-150, 300), new Vector2(1250, 90), TextAnchor.MiddleCenter, UIFont.Header, false), 4);
            _announce.resizeTextForBestFit = true;
            _announce.resizeTextMinSize = 36;
            _announce.resizeTextMaxSize = 72;
            _announce.horizontalOverflow = HorizontalWrapMode.Wrap;
            _announce.verticalOverflow = VerticalWrapMode.Truncate;
            _countdown = Outlined(UIKit.Label(_root, "", 128, T.text, new Vector2(0.5f, 0.5f), new Vector2(0, 80), new Vector2(400, 190), TextAnchor.MiddleCenter, UIFont.Number, false), 5);
            // map title card while the run counts down
            _mapTitle = Outlined(UIKit.Label(_root, "", 96, T.accent, new Vector2(0.5f, 0.5f), new Vector2(0, 250), new Vector2(1500, 120), TextAnchor.MiddleCenter, UIFont.Header, false), 5);
            _mapSub = Outlined(UIKit.Label(_root, "", 30, T.text, new Vector2(0.5f, 0.5f), new Vector2(0, 185), new Vector2(1400, 50), TextAnchor.MiddleCenter, UIFont.Body, false), 2);
            _combo = Outlined(UIKit.Label(_root, "", 40, T.text, new Vector2(0, 0.5f), new Vector2(30, 120), new Vector2(420, 60), TextAnchor.MiddleLeft, UIFont.Number, false), 3);
            _combo.rectTransform.pivot = new Vector2(0, 0.5f);
            _frenzy = Outlined(UIKit.Label(_root, "", 72, new Color(1f, 0.5f, 0.2f), new Vector2(0, 0.5f), new Vector2(30, 190), new Vector2(700, 90), TextAnchor.MiddleLeft, UIFont.Header, false), 4);
            _frenzy.rectTransform.pivot = new Vector2(0, 0.5f);
            _frenzy.horizontalOverflow = HorizontalWrapMode.Overflow;
            _downedText = Outlined(UIKit.Label(_root, "", 54, T.text, new Vector2(0.5f, 0.5f), new Vector2(0, -60), new Vector2(1400, 140), TextAnchor.MiddleCenter, UIFont.Header, false), 3);

            var help = UIKit.Label(_root, "Mouse look, wheel zoom  |  Space jump  |  Shift slide (+ jump = speed boost)  |  1/2/3 pick  R reroll  X skip  |  Esc build & menu",
                22, new Color(1, 1, 1, 0.7f), new Vector2(0, 0), new Vector2(24, 10), new Vector2(1500, 30), TextAnchor.LowerLeft, UIFont.Body, false);
            help.horizontalOverflow = HorizontalWrapMode.Overflow;
            UIKit.Outline(help, 2);

            BuildPause();
            BuildResults();
        }

        (Image icon, Text level, RectTransform root) Slot(Vector2 pos, float size)
        {
            var rt = UIKit.Box(_root, "Slot", new Vector2(0, 1), pos, new Vector2(size, size));
            UIKit.Slot(rt);
            var iconRt = UIKit.Box(rt, "Icon", new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(size - 10, size - 10));
            var icon = UIKit.AddImage(iconRt, null, Color.white);
            var lvl = Outlined(UIKit.Label(rt, "", size > 60 ? 18 : 16, Color.white, new Vector2(0.5f, 0), new Vector2(0, -26), new Vector2(size + 20, 24), TextAnchor.MiddleCenter, UIFont.Number, false), 2);
            return (icon, lvl, rt);
        }

        void BuildUpgradeWindow()
        {
            _levelUp = UIKit.Panel(_root, "UpgradeOffers", new Vector2(1, 0.5f), new Vector2(-30, -90), new Vector2(660, 706), "Upgrade Offers");
            _levelUpTitle = _levelUp.Find("TitleBar").GetComponentInChildren<Text>();
            for (int i = 0; i < 3; i++)
            {
                int slot = i;
                var c = new CardUI();
                c.root = UIKit.Box(_levelUp, "Card" + i, new Vector2(0.5f, 1), new Vector2(0, -88 - i * 172), new Vector2(600, 160));
                c.bg = c.root.gameObject.AddComponent<Image>();
                c.bg.sprite = T.card;
                c.bg.type = Image.Type.Sliced;
                c.button = c.root.gameObject.AddComponent<Button>();
                c.button.targetGraphic = c.bg;
                c.button.onClick.AddListener(() => Choose(slot));
                c.root.gameObject.AddComponent<HoverSound>();
                c.rarity = UIKit.Label(c.root, "", 16, Color.white, new Vector2(0, 1), new Vector2(18, -8), new Vector2(200, 24), TextAnchor.UpperLeft, UIFont.Number);
                var ib = UIKit.Box(c.root, "IconBack", new Vector2(0, 0.5f), new Vector2(18, -10), new Vector2(104, 104));
                ib.pivot = new Vector2(0, 0.5f);
                c.iconBack = UIKit.AddImage(ib, T.slot, Color.white);
                c.icon = UIKit.AddImage(UIKit.Box(ib, "Icon", new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(88, 88)), null, Color.white);
                c.title = UIKit.Label(c.root, "", 36, Color.white, new Vector2(0, 1), new Vector2(140, -28), new Vector2(300, 44), TextAnchor.UpperLeft, UIFont.Header);
                c.title.horizontalOverflow = HorizontalWrapMode.Overflow;
                c.title.resizeTextForBestFit = true;
                c.title.resizeTextMinSize = 16;
                c.title.resizeTextMaxSize = c.title.fontSize;
                c.title.verticalOverflow = VerticalWrapMode.Truncate;
                c.title.horizontalOverflow = HorizontalWrapMode.Wrap;
                c.level = UIKit.Label(c.root, "", 24, T.accent, new Vector2(1, 1), new Vector2(-20, -28), new Vector2(170, 34), TextAnchor.UpperRight, UIFont.Number);
                c.body = UIKit.Label(c.root, "", 22, T.text, new Vector2(0, 1), new Vector2(140, -80), new Vector2(400, 70), TextAnchor.UpperLeft, UIFont.Body);
                var kb = UIKit.Box(c.root, "Key", new Vector2(1, 0), new Vector2(-14, 12), new Vector2(40, 40));
                UIKit.AddImage(kb, T.slot, Color.white);
                c.key = UIKit.Label(kb, (i + 1).ToString(), 24, T.accent, new Vector2(0.5f, 0.5f), new Vector2(1, 0), new Vector2(40, 40), TextAnchor.MiddleCenter, UIFont.Number, false);
                _cards.Add(c);
            }
            _reroll = UIKit.Button(_levelUp, "Reroll", new Vector2(0.5f, 0), new Vector2(-150, 22), new Vector2(280, 58), Reroll, T.buttonBlue, 27);
            _rerollText = _reroll.GetComponentInChildren<Text>();
            _skip = UIKit.Button(_levelUp, "Skip (X)  +HP", new Vector2(0.5f, 0), new Vector2(150, 22), new Vector2(280, 58), Skip, T.buttonGrey, 27);
        }

        void Reroll()
        {
            var me = PlayerCharacter.Local;
            var lib = AudioManager.Lib;
            if (me == null || me.PendingLevelUps <= 0 || Time.unscaledTime < _choiceLock) return;
            if (me.Rerolls == 0)
            {
                if (lib != null) AudioManager.PlayUI(lib.deny, 0.7f);
                return;
            }
            _choiceLock = Time.unscaledTime + 0.35f;
            me.Rpc_Reroll();
            if (lib != null) AudioManager.PlayUI(lib.reroll, 0.8f);
            foreach (var c in _cards) c.root.localScale = new Vector3(1f, 0.6f, 1f);
        }

        void Skip()
        {
            var me = PlayerCharacter.Local;
            if (me == null || me.PendingLevelUps <= 0 || Time.unscaledTime < _choiceLock) return;
            _choiceLock = Time.unscaledTime + 0.35f;
            me.Rpc_Skip();
            var lib = AudioManager.Lib;
            if (lib != null) AudioManager.PlayUI(lib.click, 0.8f, 0.8f);
        }

        void BuildPause()
        {
            _pause = UIKit.Stretch(_root, "Pause");
            UIKit.AddImage(_pause, null, new Color(0, 0, 0, 0.55f)).raycastTarget = true;
            var p = UIKit.Panel(_pause, "Panel", new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(560, 720), "Paused");
            p.pivot = new Vector2(0.5f, 0.5f);
            p.anchoredPosition = new Vector2(-400, 0);
            BuildBuildPanel();
            UIKit.Label(p, "(the game keeps running for your friends)", 22, T.mutedText, new Vector2(0.5f, 1), new Vector2(0, -78), new Vector2(500, 30));
            UIKit.Button(p, "Resume", new Vector2(0.5f, 1), new Vector2(0, -120), new Vector2(440, 72), () => SetPause(false), T.buttonBlue, 45);
            UIKit.Label(p, "Mouse sensitivity", 27, T.text, new Vector2(0.5f, 1), new Vector2(0, -212), new Vector2(440, 32), TextAnchor.MiddleLeft);
            BuildSlider(p, new Vector2(0, -250), CameraRig.Sensitivity, 0.2f, 3f, v => CameraRig.Sensitivity = v);
            // three mixer channels, each player sets their own (saved locally)
            UIKit.Label(p, "Music volume", 27, T.text, new Vector2(0.5f, 1), new Vector2(0, -296), new Vector2(440, 32), TextAnchor.MiddleLeft);
            BuildSlider(p, new Vector2(0, -334), AudioManager.GetVolume(AudioManager.Channel.Music), 0f, 1f, v => AudioManager.SetVolume(AudioManager.Channel.Music, v));
            UIKit.Label(p, "Effects volume", 27, T.text, new Vector2(0.5f, 1), new Vector2(0, -380), new Vector2(440, 32), TextAnchor.MiddleLeft);
            BuildSlider(p, new Vector2(0, -418), AudioManager.GetVolume(AudioManager.Channel.SFX), 0f, 1f, v => AudioManager.SetVolume(AudioManager.Channel.SFX, v));
            UIKit.Label(p, "Interface volume", 27, T.text, new Vector2(0.5f, 1), new Vector2(0, -464), new Vector2(440, 32), TextAnchor.MiddleLeft);
            BuildSlider(p, new Vector2(0, -502), AudioManager.GetVolume(AudioManager.Channel.UI), 0f, 1f, v => AudioManager.SetVolume(AudioManager.Channel.UI, v));
            UIKit.Button(p, "Leave Party", new Vector2(0.5f, 1), new Vector2(0, -584), new Vector2(440, 64), () => GameLauncher.Instance?.Leave(), T.buttonRed, 36);
            _pause.gameObject.SetActive(false);
        }

        void BuildBuildPanel()
        {
            _build = UIKit.Panel(_pause, "Build", new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(900, 880), "Your Build");
            _build.pivot = new Vector2(0.5f, 0.5f);
            _build.anchoredPosition = new Vector2(370, -50);
            for (int i = 0; i < PlayerCharacter.MaxWeaponSlots + 6; i++)
            {
                var row = UIKit.Box(_build, "Row" + i, new Vector2(0.5f, 1), new Vector2(0, -78 - i * 70), new Vector2(850, 68));
                var ib = UIKit.Box(row, "Icon", new Vector2(0, 0.5f), new Vector2(36, 0), new Vector2(62, 62));
                UIKit.AddImage(ib, T.slot, Color.white);
                var icon = UIKit.AddImage(UIKit.Box(ib, "I", new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(48, 48)), null, Color.white);
                var title = UIKit.Label(row, "", 27, T.text, new Vector2(0, 1), new Vector2(84, -2), new Vector2(460, 32), TextAnchor.UpperLeft, UIFont.Header);
                title.horizontalOverflow = HorizontalWrapMode.Overflow;
                var tag = UIKit.Label(row, "", 16, T.accent, new Vector2(1, 1), new Vector2(-6, -52), new Vector2(460, 20), TextAnchor.UpperRight, UIFont.Body);
                var body = UIKit.Label(row, "", 16, T.mutedText, new Vector2(0, 1), new Vector2(84, -34), new Vector2(760, 40), TextAnchor.UpperLeft, UIFont.Body);
                body.horizontalOverflow = HorizontalWrapMode.Overflow;
                body.verticalOverflow = VerticalWrapMode.Truncate;
                _buildRows.Add((row, icon, title, body, tag));
            }
            _buildFooter = UIKit.Label(_build, "", 22, T.accent, new Vector2(0.5f, 0), new Vector2(0, 18), new Vector2(770, 30), TextAnchor.MiddleCenter, UIFont.Body);
        }

        void RefreshBuild()
        {
            var me = PlayerCharacter.Local;
            var db = GameDatabase.Instance;
            int r = 0;
            void Row(Sprite icon, string title, string body, string tag = "")
            {
                if (r >= _buildRows.Count) return;
                var row = _buildRows[r++];
                row.root.gameObject.SetActive(true);
                row.icon.sprite = icon;
                row.title.text = title;
                row.body.text = body;
                row.tag.text = tag;
            }
            if (me != null)
            {
                for (int i = 0; i < PlayerCharacter.MaxWeaponSlots; i++)
                {
                    int idx = me.WeaponIds.Get(i) - 1;
                    var w = db.GetWeapon(idx);
                    if (w == null) continue;
                    int lvl = me.WeaponLevels.Get(i);
                    var L = w.GetLevel(lvl);
                    string lv = w.isEvolution ? "<color=#ffb347>EVOLVED</color>" : lvl >= w.MaxLevel ? "<color=#f2c447>MAX</color>" : $"LVL {lvl}/{w.MaxLevel}";
                    string evo = "";
                    if (!w.isEvolution && w.evolveWith != null && w.evolvesInto != null)
                        evo = UpgradeSystem.CanEvolve(me, idx) ? "<color=#ffb347>Evolves on your next level-up!</color>"
                            : $"<color=#d9b8ff>LVL {w.EvolveAt} + {w.evolveWith.displayName} = {w.evolvesInto.displayName}</color>";
                    Row(w.icon, $"{w.displayName}  <size=22>{lv}</size>",
                        $"{w.description}\n<color=#f2c447>{L.damage * me.Stats.Damage:0} damage   every {L.cooldown * me.Stats.Cooldown:0.##}s</color>", evo);
                }
                for (int i = 0; i < db.powerups.Count; i++)
                {
                    int lvl = me.PowerupLevels.Get(i);
                    if (lvl <= 0) continue;
                    var p = db.powerups[i];
                    var parts = new List<string>();
                    foreach (var m in p.perLevel) parts.Add(StatInfo.Describe(m.stat, m.value * lvl));
                    string ptag = "";
                    foreach (var w in db.weapons)
                        if (w.evolveWith == p && w.evolvesInto != null && me.WeaponLevelOf(db.IndexOf(w)) > 0) { ptag = $"<color=#d9b8ff>Evolves {w.displayName}</color>"; break; }
                    Row(p.icon, $"{p.displayName}  <size=22>LVL {lvl}/{p.maxLevel}</size>", $"{p.description}\n<color=#9fe39f>Total: {string.Join(", ", parts)}</color>", ptag);
                }
                var st = me.Stats;
                _buildFooter.text = $"Rerolls {me.Rerolls}   |   Damage {st.Damage * 100f:0}%   |   Crit {st.CritChance * 100f:0}%   |   Armor {st.Armor:0}   |   Speed {st.MoveSpeed:0.#}";
            }
            for (int i = r; i < _buildRows.Count; i++) _buildRows[i].root.gameObject.SetActive(false);
        }

        Slider BuildSlider(Transform parent, Vector2 pos, float value, float min, float max, System.Action<float> onChange)
        {
            var rt = UIKit.Box(parent, "Slider", new Vector2(0.5f, 1), pos, new Vector2(440, 26));
            var bgImg = UIKit.AddImage(rt, T.slot, Color.white);
            bgImg.raycastTarget = true;
            var fillArea = UIKit.Stretch(rt, "FillArea", 5);
            var fill = UIKit.Stretch(fillArea, "Fill");
            UIKit.AddImage(fill, T.roundRect, T.xp);
            var handleArea = UIKit.Stretch(rt, "HandleArea", 0);
            var handle = UIKit.Box(handleArea, "Handle", new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(24, 40));
            var himg = UIKit.AddImage(handle, T.button, Color.white);
            himg.raycastTarget = true;
            var s = rt.gameObject.AddComponent<Slider>();
            s.fillRect = fill;
            s.handleRect = handle;
            s.targetGraphic = himg;
            s.minValue = min;
            s.maxValue = max;
            s.value = value;
            s.onValueChanged.AddListener(v => onChange(v));
            return s;
        }

        void BuildResults()
        {
            _results = UIKit.Stretch(_root, "Results");
            UIKit.AddImage(_results, null, new Color(0, 0, 0, 0.6f)).raycastTarget = true;
            var p = UIKit.Panel(_results, "Panel", new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(1040, 680), "Run Summary");
            p.pivot = new Vector2(0.5f, 0.5f);
            p.anchoredPosition = Vector2.zero;
            _resultsTitle = Outlined(UIKit.Label(p, "Victory", 108, T.accent, new Vector2(0.5f, 1), new Vector2(0, -78), new Vector2(940, 120), TextAnchor.MiddleCenter, UIFont.Header, false), 4);
            _resultsBody = UIKit.Label(p, "", 32, T.text, new Vector2(0.5f, 1), new Vector2(0, -204), new Vector2(940, 44), TextAnchor.UpperCenter);
            string[] headers = { "Player", "Hero", "Kills", "Damage", "Best Combo" };
            float[] colX = { 50, 330, 470, 650, 820 };
            for (int c = 0; c < 5; c++)
                UIKit.Label(p, headers[c], 27, T.mutedText, new Vector2(0, 1), new Vector2(colX[c], -262), new Vector2(c >= 2 ? 170 : 200, 34), c >= 2 ? TextAnchor.MiddleRight : TextAnchor.MiddleLeft, UIFont.Header, false);
            for (int r = 0; r < 4; r++)
            {
                var row = new Text[5];
                for (int c = 0; c < 5; c++)
                    row[c] = UIKit.Label(p, "", c >= 2 ? 27 : 36, T.text, new Vector2(0, 1), new Vector2(colX[c], -304 - r * 52), new Vector2(c == 0 ? 280 : c == 1 ? 200 : 170, 46),
                        c >= 2 ? TextAnchor.MiddleRight : TextAnchor.MiddleLeft, c >= 2 ? UIFont.Number : UIFont.Header);
                _resultRows.Add(row);
            }
            _resultsFooter = UIKit.Label(p, "", 27, T.mutedText, new Vector2(0.5f, 0), new Vector2(0, 116), new Vector2(940, 34));
            _resultsLobby = UIKit.Button(p, "Back to Lobby", new Vector2(0.5f, 0), new Vector2(-190, 30), new Vector2(340, 74), () => GameManager.Instance?.ReturnToLobbyNow(), T.buttonBlue, 30);
            UIKit.Button(p, "Leave Party", new Vector2(0.5f, 0), new Vector2(190, 30), new Vector2(340, 74), () => GameLauncher.Instance?.Leave(), T.buttonRed, 40);
            _results.gameObject.SetActive(false);
        }

        // ================================================================== runtime

        public void FlashDamage() => _damageFlash.color = new Color(0.8f, 0.05f, 0.05f, 0.45f);

        public void Frenzy(int combo)
        {
            _frenzy.text = $"FRENZY x{combo}!  <size=27>heal + gem vacuum</size>";
            _frenzyT = 0f;
        }

        void UpdateCombo(PlayerCharacter me)
        {
            int c = me != null ? me.Combo : 0;
            if (c > _shownCombo) _comboPunch = 1f;
            _shownCombo = c;
            _comboPunch = Mathf.MoveTowards(_comboPunch, 0f, Time.deltaTime * 5f);
            if (c >= 5)
            {
                var col = c >= 150 ? new Color(1f, 0.25f, 0.2f) : c >= 75 ? new Color(1f, 0.55f, 0.15f) : c >= 25 ? T.accent : T.text;
                _combo.text = $"{c} <size=24>KILL COMBO</size>";
                _combo.color = col;
                _combo.rectTransform.localScale = Vector3.one * (1f + _comboPunch * 0.18f);
            }
            else _combo.text = "";
            _frenzyT += Time.deltaTime;
            var fc = _frenzy.color;
            fc.a = _frenzyT < 1.8f ? 1f : Mathf.Clamp01(1f - (_frenzyT - 1.8f) * 2f);
            _frenzy.color = fc;
            _frenzy.rectTransform.localScale = Vector3.one * (1f + Mathf.Max(0f, 0.25f - _frenzyT) * 2f);
        }

        public void ShowAnnouncement(string text)
        {
            _announce.text = text;
            _announceT = 0f;
        }

        void SetPause(bool on)
        {
            if (on) RefreshBuild();
            _pause.gameObject.SetActive(on);
            CameraRig.MenuOpen = on || _results.gameObject.activeSelf;
            LocalInput.Blocked = on;
        }

        void Choose(int slot)
        {
            var me = PlayerCharacter.Local;
            if (me == null || me.PendingLevelUps <= 0 || Time.unscaledTime < _choiceLock) return;
            if (me.Choices.Get(slot) == 0) return;
            _choiceLock = Time.unscaledTime + 0.35f;
            me.Rpc_Choose(slot);
            var lib = AudioManager.Lib;
            if (lib != null) AudioManager.PlayUI(lib.click, 0.9f, 1.2f);
            _cards[slot].root.localScale = Vector3.one * 1.06f;
        }

        void Update()
        {
            PerfStats.Hud.Start();
            try { Tick(); }
            finally { PerfStats.Hud.Stop(); }
        }

        void Tick()
        {
            var gm = GameManager.Instance;
            var me = PlayerCharacter.Local;
            var kb = Keyboard.current;

            if (kb != null && kb.escapeKey.wasPressedThisFrame && !_results.gameObject.activeSelf) SetPause(!_pause.gameObject.activeSelf);

            var df = _damageFlash.color;
            var meNow = PlayerCharacter.Local;
            float floor = 0f;
            if (meNow != null && meNow.IsAlive && meNow.Health < meNow.MaxHealth * CombatManager.Settings.lowHealthWarning)
                floor = 0.07f + 0.05f * Mathf.Sin(Time.time * 7f);   // low HP: pulsing red edge
            df.a = Mathf.Max(floor, Mathf.MoveTowards(df.a, 0f, Time.deltaTime * 1.6f));
            _damageFlash.color = df;

            _announceT += Time.deltaTime;
            var ac = _announce.color;
            ac.a = _announceT < 2.5f ? Mathf.Clamp01(_announceT * 6f) : Mathf.Clamp01(1f - (_announceT - 2.5f));
            _announce.color = ac;
            _announce.rectTransform.localScale = Vector3.one * (1f + Mathf.Max(0f, 0.2f - _announceT) * 1.5f);

            if (gm == null || gm.Object == null || !gm.Object.IsValid) return;
            var db = GameDatabase.Instance;

            // top
            _xpFill.fillAmount = gm.XPToNext > 0 ? Mathf.Clamp01(gm.TeamXP / (float)gm.XPToNext) : 0f;
            _level.text = "LVL " + gm.TeamLevel;
            _timer.text = UIKit.FormatTime(gm.TimeLeft);
            _timer.color = gm.TimeLeft < 30f ? Color.Lerp(T.text, T.bad, Mathf.PingPong(Time.time * 2f, 1f)) : T.text;
            _elapsed.text = UIKit.FormatTime(gm.RunTime);
            _kills.text = gm.TotalKills.ToString("N0");

            // boss
            Enemy boss = null;
            foreach (var e in EnemyRegistry.All) if (e != null && e.IsAlive && e.Boss) { boss = e; break; }
            _boss.gameObject.SetActive(boss != null);
            if (boss != null)
            {
                _bossName.text = boss.DisplayName;
                _bossFill.fillAmount = Mathf.Lerp(_bossFill.fillAmount, boss.MaxHealth > 0 ? boss.Health / boss.MaxHealth : 0f, Time.deltaTime * 8f);
                _bossHp.text = $"{Mathf.CeilToInt(boss.Health):N0} / {Mathf.CeilToInt(boss.MaxHealth):N0}";
            }

            _countdown.text = gm.State == RunState.Starting ? Mathf.CeilToInt(gm.StateTimer.RemainingTime(gm.Runner) ?? 0f).ToString() : "";
            {
                // title card: in during the countdown, out over the first seconds of the run
                float a = gm.State == RunState.Starting ? 1f : gm.State == RunState.Playing ? Mathf.Clamp01(1f - (gm.RunTime - 1.2f) / 0.8f) : 0f;
                var m = gm.map;
                if (a > 0f && m != null)
                {
                    _mapTitle.text = m.displayName.ToUpperInvariant();
                    var c = m.accent; c.a = a;
                    _mapTitle.color = c;
                    _mapTitle.rectTransform.localScale = Vector3.one * (1f + (1f - a) * 0.15f);
                    _mapSub.text = m.description;
                    var sc = T.text; sc.a = a * 0.9f;
                    _mapSub.color = sc;
                }
                _mapTitle.gameObject.SetActive(a > 0f && m != null);
                _mapSub.gameObject.SetActive(a > 0f && m != null);
            }

            if (me != null)
            {
                float max = me.MaxHealth;
                float frac = max > 0 ? Mathf.Clamp01(me.Health / max) : 0;
                _hpFill.fillAmount = frac;
                _hpText.text = $"{Mathf.CeilToInt(me.Health)}/{Mathf.CeilToInt(max)}";

                for (int i = 0; i < _weaponSlots.Count; i++)
                {
                    var s = _weaponSlots[i];
                    var w = db.GetWeapon(me.WeaponIds.Get(i) - 1);
                    s.icon.enabled = w != null;
                    s.icon.sprite = w != null ? w.icon : null;
                    int lvl = me.WeaponLevels.Get(i);
                    s.level.text = w != null ? (lvl >= w.MaxLevel ? "MAX" : "LVL " + lvl) : "";
                }
                int ps = 0;
                for (int i = 0; i < db.powerups.Count && ps < _powerSlots.Count; i++)
                {
                    int lvl = me.PowerupLevels.Get(i);
                    if (lvl <= 0) continue;
                    var s = _powerSlots[ps++];
                    s.icon.enabled = true;
                    s.icon.sprite = db.powerups[i].icon;
                    s.level.text = "LVL " + lvl;
                }
                for (; ps < _powerSlots.Count; ps++)
                {
                    _powerSlots[ps].icon.enabled = false;
                    _powerSlots[ps].level.text = "";
                }

                // HP bar under your own feet
                var cam = Camera.main;
                if (cam != null && !me.Dead)
                {
                    var sp = cam.WorldToScreenPoint(me.transform.position - Vector3.up * 0.15f);
                    _feetBar.gameObject.SetActive(sp.z > 0);
                    _feetBar.position = sp;
                    _feetFill.fillAmount = frac;
                }
                else _feetBar.gameObject.SetActive(false);

                if (me.Downed)
                {
                    float left = me.DownedTimer.RemainingTime(me.Runner) ?? 0f;
                    _downedText.text = $"You are down!\n<size=36>A teammate can revive you by standing close  {Mathf.CeilToInt(left)}s" +
                                       (me.ReviveProgress > 0 ? $"   <color=#{UIKit.Hex(T.good)}>reviving {me.ReviveProgress * 100f:0}%</color>" : "") + "</size>";
                    _downedVignette.color = new Color(0.25f, 0f, 0f, 0.45f);
                }
                else if (me.Dead && gm.State == RunState.Playing)
                {
                    _downedText.text = "You died\n<size=36>Spectating (Space to switch). Survive, team!</size>";
                    _downedVignette.color = new Color(0f, 0f, 0f, 0.35f);
                }
                else
                {
                    _downedText.text = "";
                    _downedVignette.color = Color.clear;
                }

                UpdateLevelUp(me, kb);
            }
            else
            {
                _levelUp.gameObject.SetActive(false);
                _feetBar.gameObject.SetActive(false);
            }

            UpdateMates(me);
            UpdateTags();
            UpdateCombo(me);
            UpdateObjective(gm);

            bool ended = gm.State == RunState.Victory || gm.State == RunState.Defeat;
            if (ended != _results.gameObject.activeSelf)
            {
                _results.gameObject.SetActive(ended);
                if (ended) _pause.gameObject.SetActive(false);
                CameraRig.MenuOpen = ended;
                LocalInput.Blocked = ended;
            }
            if (ended)
            {
                UpdateResults(gm);
                _downedText.text = "";
                _downedVignette.color = Color.clear;
                _levelUp.gameObject.SetActive(false);
                _feetBar.gameObject.SetActive(false);
            }
        }

        void UpdateLevelUp(PlayerCharacter me, Keyboard kb)
        {
            // hidden while the pause / build screen is up (it would show through it); picks wait until you resume
            bool show = me.PendingLevelUps > 0 && me.Choices.Get(0) != 0 && !me.Dead && !_pause.gameObject.activeSelf;
            _levelUp.gameObject.SetActive(show);
            if (!show) return;
            string title = me.OfferIsTreasure ? "<color=#ffd24a>Treasure!</color>" : "Upgrade Offers";
            _levelUpTitle.text = me.PendingLevelUps > 1 ? $"{title}  <size=27>(+{me.PendingLevelUps - 1} more)</size>" : title;
            _rerollText.text = $"Reroll (R)  x{me.Rerolls}";
            _reroll.image.color = me.Rerolls > 0 ? T.buttonBlue : T.buttonGrey;

            for (int i = 0; i < _cards.Count; i++)
            {
                var c = _cards[i];
                short code = me.Choices.Get(i);
                c.root.gameObject.SetActive(code != 0);
                if (code == 0) continue;
                var rarity = UpgradeSystem.RarityOf(code);
                var col = T.RarityColor(rarity);
                c.bg.color = col;
                c.rarity.text = UITheme.RarityName(rarity);
                c.rarity.color = Color.Lerp(col, Color.white, 0.6f);
                c.icon.sprite = UpgradeSystem.IconOf(code);
                c.title.text = UpgradeSystem.NameOf(code);
                UpgradeSystem.Describe(me, code, out string lvl);
                c.level.text = lvl.StartsWith("Lv") ? "LVL " + lvl.Substring(lvl.LastIndexOf(' ') + 1) : lvl == "EVOLUTION" ? "<color=#ffd24a>EVOLVE!</color>" : (lvl.Length > 0 ? "New!" : "");
                if (rarity == Rarity.Legendary) c.root.localScale = Vector3.one * (1f + 0.025f * Mathf.Sin(Time.unscaledTime * 6f));
                c.body.text = UpgradeSystem.StatLines(me, code);
                c.root.localScale = Vector3.Lerp(c.root.localScale, Vector3.one, Time.deltaTime * 12f);
            }

            if (LocalInput.Blocked) return;
            var pad = Gamepad.current;
            if ((kb != null && (kb.digit1Key.wasPressedThisFrame || kb.numpad1Key.wasPressedThisFrame)) || (pad != null && pad.dpad.left.wasPressedThisFrame)) Choose(0);
            if ((kb != null && (kb.digit2Key.wasPressedThisFrame || kb.numpad2Key.wasPressedThisFrame)) || (pad != null && pad.dpad.up.wasPressedThisFrame)) Choose(1);
            if ((kb != null && (kb.digit3Key.wasPressedThisFrame || kb.numpad3Key.wasPressedThisFrame)) || (pad != null && pad.dpad.right.wasPressedThisFrame)) Choose(2);
            if ((kb != null && kb.rKey.wasPressedThisFrame) || (pad != null && pad.buttonNorth.wasPressedThisFrame)) Reroll();
            if ((kb != null && kb.xKey.wasPressedThisFrame) || (pad != null && pad.dpad.down.wasPressedThisFrame)) Skip();
        }

        void UpdateMates(PlayerCharacter me)
        {
            int m = 0;
            foreach (var p in PlayerCharacter.All)
            {
                if (p == null || p == me || m >= _mates.Count) continue;
                var v = _mates[m++];
                v.root.gameObject.SetActive(true);
                v.portrait.sprite = p.Def != null ? p.Def.portrait : null;
                v.name.text = p.DisplayName;
                v.hp.fillAmount = p.MaxHealth > 0 ? Mathf.Clamp01(p.Health / p.MaxHealth) : 0;
                v.status.text = p.Dead ? "DEAD" : p.Downed ? $"DOWN {Mathf.CeilToInt(p.DownedTimer.RemainingTime(p.Runner) ?? 0)}" : "";
            }
            for (; m < _mates.Count; m++) _mates[m].root.gameObject.SetActive(false);
        }

        void UpdateTags()
        {
            var cam = Camera.main;
            if (cam == null) return;
            var stale = new List<PlayerCharacter>();
            foreach (var kv in _tags) if (kv.Key == null || kv.Key.Object == null) stale.Add(kv.Key);
            foreach (var s in stale) { if (_tags[s].rt != null) Destroy(_tags[s].rt.gameObject); _tags.Remove(s); }

            foreach (var p in PlayerCharacter.All)
            {
                if (p == null || p.IsLocal) continue;
                if (!_tags.TryGetValue(p, out var tag))
                {
                    var rt = UIKit.Box(_tagLayer, "Tag", new Vector2(0, 0), Vector2.zero, new Vector2(260, 70));
                    rt.pivot = new Vector2(0.5f, 0f);
                    var text = Outlined(UIKit.Label(rt, "", 32, Color.white, new Vector2(0.5f, 1), new Vector2(0, 0), new Vector2(260, 36), TextAnchor.MiddleCenter, UIFont.Header, false), 2);
                    text.rectTransform.pivot = new Vector2(0.5f, 1);
                    var bar = UIKit.Bar(rt, "Revive", new Vector2(0.5f, 0), new Vector2(0, 4), new Vector2(140, 14), T.good);
                    bar.bg.rectTransform.pivot = new Vector2(0.5f, 0);
                    bar.bg.rectTransform.anchoredPosition = new Vector2(0, 4);
                    var arrowRt = UIKit.Box(rt, "Arrow", new Vector2(0.5f, 0.5f), new Vector2(0, -26), new Vector2(36, 36));
                    arrowRt.pivot = new Vector2(0.5f, 0.5f);
                    UIKit.AddImage(arrowRt, T.arrow, Color.white);
                    tag = (rt, text, bar.fill);
                    _tags[p] = tag;
                }
                var c = p.Def != null ? p.Def.color : Color.white;
                var arrow = (RectTransform)tag.rt.Find("Arrow");
                bool show = !p.Dead;
                tag.rt.gameObject.SetActive(show);
                if (!show) continue;

                var sp = cam.WorldToScreenPoint(p.transform.position + Vector3.up * 2.4f);
                if (sp.z < 0) sp = new Vector3(Screen.width - sp.x, -100f, 0);
                float margin = 80f;
                bool off = sp.x < margin || sp.x > Screen.width - margin || sp.y < margin || sp.y > Screen.height - margin;
                var center = new Vector3(Screen.width / 2f, Screen.height / 2f, 0);
                if (off)
                {
                    var d = (Vector3)(Vector2)(sp - center);
                    float sx = (Screen.width / 2f - margin) / Mathf.Max(1f, Mathf.Abs(d.x));
                    float sy = (Screen.height / 2f - margin) / Mathf.Max(1f, Mathf.Abs(d.y));
                    sp = center + d * Mathf.Min(sx, sy);
                    arrow.gameObject.SetActive(true);
                    arrow.localRotation = Quaternion.Euler(0, 0, Mathf.Atan2(d.y, d.x) * Mathf.Rad2Deg - 90f);
                    arrow.GetComponent<Image>().color = p.Downed ? T.bad : c;
                }
                else arrow.gameObject.SetActive(false);
                tag.rt.position = new Vector3(sp.x, sp.y, 0);
                tag.text.text = p.Downed ? $"<color=#{UIKit.Hex(T.bad)}>{p.DisplayName} - Help!</color>" : $"<color=#{UIKit.Hex(c)}>{p.DisplayName}</color>";
                tag.bar.transform.parent.gameObject.SetActive(p.Downed);
                tag.bar.fillAmount = p.ReviveProgress;
            }
        }

        RectTransform _objective;
        Text _objectiveText;

        /// <summary>Points at a fleeing Treasure Slime (screen-edge arrow when it is off screen).</summary>
        void UpdateObjective(GameManager gm)
        {
            var cam = Camera.main;
            Enemy target = null;
            if (gm.State == RunState.Playing)
                foreach (var e in EnemyRegistry.All) if (e != null && e.IsAlive && e.Def != null && e.Def.dropChests > 0) { target = e; break; }
            if (_objective == null)
            {
                _objective = UIKit.Box(_tagLayer, "Objective", Vector2.zero, Vector2.zero, new Vector2(260, 80));
                _objective.pivot = new Vector2(0.5f, 0f);
                _objectiveText = Outlined(UIKit.Label(_objective, "", 27, new Color(1f, 0.85f, 0.3f), new Vector2(0.5f, 1), Vector2.zero, new Vector2(260, 34), TextAnchor.MiddleCenter, UIFont.Header, false), 2);
                var a = UIKit.Box(_objective, "Arrow", new Vector2(0.5f, 0.5f), new Vector2(0, -26), new Vector2(40, 40));
                UIKit.AddImage(a, T.arrow, new Color(1f, 0.82f, 0.25f));
            }
            _objective.gameObject.SetActive(target != null && cam != null);
            if (target == null || cam == null) return;
            var arrow = (RectTransform)_objective.Find("Arrow");
            var sp = cam.WorldToScreenPoint(target.transform.position + Vector3.up * 2.2f);
            if (sp.z < 0) sp = new Vector3(Screen.width - sp.x, -100f, 0);
            float margin = 90f;
            bool off = sp.x < margin || sp.x > Screen.width - margin || sp.y < margin || sp.y > Screen.height - margin;
            var center = new Vector3(Screen.width / 2f, Screen.height / 2f, 0);
            if (off)
            {
                var d = (Vector3)(Vector2)(sp - center);
                float sx = (Screen.width / 2f - margin) / Mathf.Max(1f, Mathf.Abs(d.x));
                float sy = (Screen.height / 2f - margin) / Mathf.Max(1f, Mathf.Abs(d.y));
                sp = center + d * Mathf.Min(sx, sy);
                arrow.gameObject.SetActive(true);
                arrow.localRotation = Quaternion.Euler(0, 0, Mathf.Atan2(d.y, d.x) * Mathf.Rad2Deg - 90f);
            }
            else arrow.gameObject.SetActive(false);
            _objective.position = new Vector3(sp.x, sp.y, 0);
            float left = target.Def.lifetime > 0 ? Mathf.Max(0f, target.Def.lifetime - target.Age) : 0f;
            _objectiveText.text = left > 0 ? $"TREASURE  {Mathf.CeilToInt(left)}s" : "TREASURE";
            _objective.localScale = Vector3.one * (1f + 0.06f * Mathf.Sin(Time.time * 8f));
        }

        void UpdateResults(GameManager gm)
        {
            bool win = gm.State == RunState.Victory;
            _resultsTitle.text = win ? "Victory" : "Defeat";
            _resultsTitle.color = win ? T.accent : T.bad;
            _resultsBody.text = $"Survived {UIKit.FormatTime(gm.RunTime)}   |   Level {gm.TeamLevel}   |   {gm.TotalKills:N0} kills";
            var players = new List<PlayerData>(PlayerData.All);
            players.RemoveAll(x => x == null || x.Object == null || !x.Object.IsValid);
            players.Sort((a, b) => b.DamageDealt.CompareTo(a.DamageDealt));
            var db = GameDatabase.Instance;
            for (int r = 0; r < _resultRows.Count; r++)
            {
                var row = _resultRows[r];
                if (r >= players.Count)
                {
                    foreach (var t in row) t.text = "";
                    continue;
                }
                var p = players[r];
                var c = db.GetCharacter(p.CharacterIndex);
                row[0].text = p.DisplayName + (r == 0 && players.Count > 1 ? "  <size=27><color=#f2c447>MVP</color></size>" : "");
                row[1].text = $"<color=#{UIKit.Hex(c.color)}>{c.displayName}</color>";
                row[2].text = p.Kills.ToString("N0");
                row[3].text = Mathf.RoundToInt(p.DamageDealt).ToString("N0");
                row[4].text = p.BestCombo.ToString("N0");
            }
            float left = gm.StateTimer.RemainingTime(gm.Runner) ?? 0f;
            bool host = gm.Runner.IsServer;
            _resultsFooter.text = host ? $"Returning to the lobby in {Mathf.CeilToInt(left)}s" : $"The host will bring you back to the lobby in {Mathf.CeilToInt(left)}s";
            _resultsLobby.gameObject.SetActive(host);
        }
    }
}
