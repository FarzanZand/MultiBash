using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

namespace MultiBash
{
    /// <summary>
    /// Party lobby (Megabonk-style windows): character selection grid, hero details, party list, room code,
    /// ready / start. Party members' heroes stand on pedestals in the 3D scene.
    /// </summary>
    public class LobbyUI : MonoBehaviour
    {
        [Tooltip("Where party members' heroes stand (up to 4).")]
        public Transform[] pedestals;

        Text _code, _hint, _status;
        Button _ready, _start;
        Text _readyLabel;
        Image _detailPortrait, _weaponIcon;
        Text _detailName, _detailDesc, _weaponName, _weaponDesc, _passive;
        Text _mapName, _mapDesc, _mapDiff;
        Image _mapPreview, _mapAccent;
        Button _mapPrev, _mapNext;
        readonly List<SlotView> _slots = new();
        readonly List<(Button button, Image frame)> _tiles = new();
        readonly Dictionary<int, (int character, GameObject model)> _models = new();
        bool _resetDone;

        class SlotView
        {
            public Image portrait, readyIcon;
            public Text name, sub;
        }

        void Start()
        {
            LocalInput.Blocked = false;
            CameraRig.MenuOpen = true;
            Cursor.lockState = CursorLockMode.None;
            Cursor.visible = true;
            AudioManager.PlayMusic(AudioManager.Lib != null ? AudioManager.Lib.menuMusic : null);
            Build();
        }

        void Build()
        {
            var T = UIKit.T;
            var db = GameDatabase.Instance;
            var root = UIKit.Canvas("LobbyCanvas", 10, transform).transform;

            // ---- character selection grid (top-left)
            var sel = UIKit.Panel(root, "CharacterSelection", new Vector2(0, 1), new Vector2(40, -20), new Vector2(500, 560), "Character Selection");
            for (int i = 0; i < db.characters.Count; i++)
            {
                int index = i;
                var c = db.characters[i];
                var tile = UIKit.Box(sel, "Tile_" + c.displayName, new Vector2(0, 1), new Vector2(34 + (i % 2) * 222, -92 - (i / 2) * 228), new Vector2(210, 216));
                var bg = tile.gameObject.AddComponent<Image>();
                bg.sprite = T.slot;
                bg.type = Image.Type.Sliced;
                var btn = tile.gameObject.AddComponent<Button>();
                btn.targetGraphic = bg;
                btn.onClick.AddListener(() => PickCharacter(index));
                tile.gameObject.AddComponent<HoverSound>();
                var pr = UIKit.Box(tile, "Portrait", new Vector2(0.5f, 1), new Vector2(0, -12), new Vector2(144, 144));
                var pimg = UIKit.AddImage(pr, c.portrait, Color.white);
                pimg.preserveAspect = true;
                UIKit.Label(tile, c.displayName, 36, T.text, new Vector2(0.5f, 0), new Vector2(0, 8), new Vector2(200, 46), TextAnchor.MiddleCenter, UIFont.Header);
                var frame = UIKit.Image(tile, "Frame", T.outline, T.accent);
                _tiles.Add((btn, frame));
            }

            // ---- hero details (right)
            var det = UIKit.Panel(root, "Details", new Vector2(1, 1), new Vector2(-40, -150), new Vector2(620, 700));
            var dp = UIKit.Box(det, "Portrait", new Vector2(0, 1), new Vector2(30, -30), new Vector2(150, 150));
            UIKit.Slot(dp);
            var dpi = UIKit.Box(dp, "Img", new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(138, 138));
            _detailPortrait = UIKit.AddImage(dpi, null, Color.white);
            _detailPortrait.preserveAspect = true;
            _detailName = UIKit.Label(det, "", 54, T.text, new Vector2(0, 1), new Vector2(200, -36), new Vector2(390, 64), TextAnchor.UpperLeft, UIFont.Header);
            _detailDesc = UIKit.Label(det, "", 27, T.text, new Vector2(0, 1), new Vector2(200, -104), new Vector2(390, 120), TextAnchor.UpperLeft);
            var wi = UIKit.Box(det, "WeaponIcon", new Vector2(0, 1), new Vector2(30, -236), new Vector2(84, 84));
            UIKit.Slot(wi);
            _weaponIcon = UIKit.AddImage(UIKit.Box(wi, "Img", new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(66, 66)), null, Color.white);
            _weaponName = UIKit.Label(det, "", 36, T.accent, new Vector2(0, 1), new Vector2(132, -236), new Vector2(460, 44), TextAnchor.UpperLeft, UIFont.Header);
            _weaponDesc = UIKit.Label(det, "", 22, T.text, new Vector2(0, 1), new Vector2(132, -278), new Vector2(460, 80), TextAnchor.UpperLeft);
            var si = UIKit.Box(det, "PassiveIcon", new Vector2(0, 1), new Vector2(30, -372), new Vector2(84, 84));
            UIKit.Slot(si);
            UIKit.AddImage(UIKit.Box(si, "Img", new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(48, 48)), T.star, T.accent);
            UIKit.Label(det, "Passive", 36, T.accent, new Vector2(0, 1), new Vector2(132, -372), new Vector2(460, 44), TextAnchor.UpperLeft, UIFont.Header);
            _passive = UIKit.Label(det, "", 22, T.good, new Vector2(0, 1), new Vector2(132, -414), new Vector2(460, 60), TextAnchor.UpperLeft);
            _ready = UIKit.Button(det, "Ready", new Vector2(0.5f, 0), new Vector2(0, 34), new Vector2(330, 80), ToggleReady, T.buttonBlue, 45);
            _readyLabel = _ready.GetComponentInChildren<Text>();
            _start = UIKit.Button(det, "Start Run", new Vector2(0.5f, 0), new Vector2(0, 34), new Vector2(330, 80), StartRun, T.buttonBlue, 45);
            _hint = UIKit.Label(det, "", 27, T.mutedText, new Vector2(0.5f, 0), new Vector2(0, 124), new Vector2(560, 60), TextAnchor.MiddleCenter);

            // ---- room code (top-right)
            var codeBox = UIKit.Panel(root, "Code", new Vector2(1, 1), new Vector2(-40, -20), new Vector2(620, 116));
            UIKit.Label(codeBox, "Room Code", 27, T.mutedText, new Vector2(0, 1), new Vector2(26, -14), new Vector2(300, 30), TextAnchor.UpperLeft);
            _code = UIKit.Label(codeBox, "-----", 40, T.text, new Vector2(0, 0), new Vector2(26, 16), new Vector2(380, 54), TextAnchor.LowerLeft, UIFont.Number);
            UIKit.Button(codeBox, "Copy", new Vector2(1, 0.5f), new Vector2(-22, 0), new Vector2(150, 62), () =>
            {
                GUIUtility.systemCopyBuffer = GameLauncher.Instance != null ? GameLauncher.Instance.RoomCode : "";
                _status.text = "Room code copied!";
            }, T.buttonGrey, 36);
            _status = UIKit.Label(root, "", 27, T.accent, new Vector2(1, 1), new Vector2(-50, -140), new Vector2(500, 30), TextAnchor.UpperRight);

            // ---- party (bottom-left)
            var party = UIKit.Panel(root, "Party", new Vector2(0, 0), new Vector2(40, 20), new Vector2(500, 470), "Party");
            for (int i = 0; i < 4; i++)
            {
                var s = new SlotView();
                var row = UIKit.Box(party, "Slot" + i, new Vector2(0, 1), new Vector2(26, -84 - i * 74), new Vector2(448, 68));
                UIKit.Slot(row);
                var pr = UIKit.Box(row, "Portrait", new Vector2(0, 0.5f), new Vector2(8, 0), new Vector2(56, 56));
                s.portrait = UIKit.AddImage(pr, null, Color.white);
                s.portrait.preserveAspect = true;
                s.name = UIKit.Label(row, "", 32, T.text, new Vector2(0, 0.5f), new Vector2(76, 10), new Vector2(280, 34), TextAnchor.MiddleLeft, UIFont.Header);
                s.sub = UIKit.Label(row, "", 22, T.mutedText, new Vector2(0, 0.5f), new Vector2(78, -18), new Vector2(280, 26), TextAnchor.MiddleLeft);
                var ri = UIKit.Box(row, "Ready", new Vector2(1, 0.5f), new Vector2(-14, 0), new Vector2(36, 36));
                s.readyIcon = UIKit.AddImage(ri, T.star, T.good);
                _slots.Add(s);
            }
            UIKit.Button(party, "Leave", new Vector2(1, 0), new Vector2(-26, 20), new Vector2(160, 52), () => GameLauncher.Instance?.Leave(), T.buttonRed, 32);

            // ---- map picker (bottom-center; host chooses, everyone sees it)
            var map = UIKit.Panel(root, "Map", new Vector2(0.5f, 0), new Vector2(-30, 20), new Vector2(600, 290), "Map");
            var prevBox = UIKit.Box(map, "Preview", new Vector2(0, 0), new Vector2(26, 22), new Vector2(200, 150));
            UIKit.Slot(prevBox);
            _mapPreview = UIKit.AddImage(UIKit.Box(prevBox, "Img", new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(188, 138)), null, Color.white);
            _mapPreview.preserveAspect = false;
            _mapAccent = UIKit.AddImage(UIKit.Box(map, "Accent", new Vector2(0, 0), new Vector2(240, 166), new Vector2(330, 6)), null, Color.white);
            _mapName = UIKit.Label(map, "", 40, T.text, new Vector2(0, 0), new Vector2(240, 174), new Vector2(340, 46), TextAnchor.LowerLeft, UIFont.Header);
            _mapName.resizeTextForBestFit = true;
            _mapName.resizeTextMinSize = 16;
            _mapName.resizeTextMaxSize = _mapName.fontSize;
            _mapName.horizontalOverflow = HorizontalWrapMode.Wrap;
            _mapName.verticalOverflow = VerticalWrapMode.Truncate;
            _mapDesc = UIKit.Label(map, "", 22, T.text, new Vector2(0, 0), new Vector2(240, 64), new Vector2(340, 96), TextAnchor.UpperLeft);
            _mapDiff = UIKit.Label(map, "", 22, T.accent, new Vector2(0, 0), new Vector2(240, 18), new Vector2(240, 30), TextAnchor.LowerLeft);
            _mapPrev = UIKit.Button(map, "<", new Vector2(1, 0), new Vector2(-104, 16), new Vector2(64, 52), () => CycleMap(-1), T.buttonGrey, 36);
            _mapNext = UIKit.Button(map, ">", new Vector2(1, 0), new Vector2(-28, 16), new Vector2(64, 52), () => CycleMap(1), T.buttonGrey, 36);
        }

        void CycleMap(int dir)
        {
            var host = PlayerData.Host;
            var db = GameDatabase.Instance;
            if (!IsHost || host == null || db.maps.Count == 0) return;
            int n = db.maps.Count;
            host.MapIndex = ((host.MapIndex + dir) % n + n) % n;
            PlayerPrefs.SetInt("map", host.MapIndex);
        }

        void UpdateMap()
        {
            var db = GameDatabase.Instance;
            var host = PlayerData.Host;
            var m = db.GetMap(host != null ? host.MapIndex : 0);
            bool any = m != null;
            _mapName.text = any ? m.displayName : "Graveyard";
            _mapDesc.text = any ? m.description : "";
            _mapDiff.text = any ? (m.difficulty > 1.01f ? $"Danger x{m.difficulty:0.0#}" : "Danger: normal") : "";
            _mapAccent.color = any ? m.accent : UIKit.T.accent;
            _mapName.color = any ? Color.Lerp(m.accent, Color.white, 0.35f) : UIKit.T.text;
            _mapPreview.sprite = any ? m.preview : null;
            _mapPreview.color = any && m.preview != null ? Color.white : (any ? m.accent * 0.6f : Color.grey);
            bool canPick = IsHost && db.maps.Count > 1;
            _mapPrev.gameObject.SetActive(canPick);
            _mapNext.gameObject.SetActive(canPick);
        }

        void PickCharacter(int index)
        {
            PlayerPrefs.SetInt("character", index);
            var me = PlayerData.Local;
            if (me != null)
            {
                me.Rpc_SetCharacter(index);
                if (me.Ready) me.Rpc_SetReady(false);
            }
        }

        void ToggleReady()
        {
            var me = PlayerData.Local;
            if (me == null) return;
            me.Rpc_SetReady(!me.Ready);
            var lib = AudioManager.Lib;
            if (lib != null && !me.Ready) AudioManager.PlayUI(lib.ready, 0.8f);
        }

        void StartRun()
        {
            if (!CanStart()) return;
            var lib = AudioManager.Lib;
            if (lib != null) AudioManager.PlayUI(lib.start, 0.9f);
            GameLauncher.Instance.LoadGameScene();
        }

        bool IsHost => GameLauncher.Instance != null && GameLauncher.Instance.Runner != null && GameLauncher.Instance.Runner.IsServer;

        bool CanStart()
        {
            if (!IsHost) return false;
            foreach (var p in PlayerData.All)
                if (p != null && !p.IsHost && !p.Ready) return false;
            return true;
        }

        void Update()
        {
            var launcher = GameLauncher.Instance;
            var runner = launcher != null ? launcher.Runner : null;
            if (runner == null || !runner.IsRunning) return;

            if (!_resetDone && runner.IsServer)
            {
                _resetDone = true;
                foreach (var p in PlayerData.All) p.ResetForLobby();
            }

            var db = GameDatabase.Instance;
            var T = UIKit.T;
            _code.text = launcher.RoomCode;

            var players = new List<PlayerData>(PlayerData.All);
            players.RemoveAll(p => p == null || p.Object == null || !p.Object.IsValid);
            players.Sort((a, b) => a.JoinOrder.CompareTo(b.JoinOrder));

            for (int i = 0; i < _slots.Count; i++)
            {
                var s = _slots[i];
                if (i < players.Count)
                {
                    var p = players[i];
                    var c = db.GetCharacter(p.CharacterIndex);
                    s.portrait.enabled = true;
                    s.portrait.sprite = c.portrait;
                    s.name.text = p.DisplayName;
                    s.sub.text = $"<color=#{UIKit.Hex(c.color)}>{c.displayName}</color>" + (p.IsHost ? $"   <color=#{UIKit.Hex(T.accent)}>Host</color>" : "") + (p.IsLocal ? "   <color=#ffffff>You</color>" : "");
                    bool ready = p.Ready || p.IsHost;
                    s.readyIcon.color = ready ? T.good : new Color(1, 1, 1, 0.12f);
                }
                else
                {
                    s.portrait.enabled = false;
                    s.name.text = "<color=#5a6664>Empty slot</color>";
                    s.sub.text = "";
                    s.readyIcon.color = new Color(1, 1, 1, 0.05f);
                }
            }

            var me = PlayerData.Local;
            int sel = me != null ? me.CharacterIndex : PlayerPrefs.GetInt("character", 0);
            for (int i = 0; i < _tiles.Count; i++) _tiles[i].frame.enabled = i == sel;
            var def = db.GetCharacter(sel);
            _detailPortrait.sprite = def.portrait;
            _detailName.text = def.displayName;
            _detailDesc.text = def.description;
            _passive.text = def.PassiveText;
            if (def.startingWeapon != null)
            {
                _weaponIcon.sprite = def.startingWeapon.icon;
                _weaponName.text = def.startingWeapon.displayName;
                var sw = def.startingWeapon;
                _weaponDesc.text = sw.description + (sw.evolveWith != null && sw.evolvesInto != null
                    ? $"\n<size=18><color=#e2c8ff>Evolves: LVL {sw.EvolveAt} + {sw.evolveWith.displayName} = {sw.evolvesInto.displayName}</color></size>" : "");
            }

            bool host = IsHost;
            _start.gameObject.SetActive(host);
            _start.interactable = CanStart();
            _ready.gameObject.SetActive(!host);
            if (me != null)
            {
                _readyLabel.text = me.Ready ? "Not Ready" : "Ready";
                _ready.image.color = me.Ready ? T.buttonGrey : T.buttonBlue;
            }

            int notReady = 0;
            foreach (var p in players) if (!p.IsHost && !p.Ready) notReady++;
            _hint.text = host
                ? (notReady > 0 ? $"Waiting for {notReady} player(s) to ready up..." : players.Count == 1 ? "Start alone, or share the room code with friends." : "Everyone is ready!")
                : (me != null && me.Ready ? "Waiting for the host to start..." : "Pick a hero, then press Ready.");

            UpdateMap();
            UpdateModels(players);
        }

        void UpdateModels(List<PlayerData> players)
        {
            if (pedestals == null) return;
            var db = GameDatabase.Instance;
            for (int i = 0; i < pedestals.Length; i++)
            {
                int ch = i < players.Count ? players[i].CharacterIndex : -1;
                _models.TryGetValue(i, out var current);
                if (current.model != null && current.character == ch) continue;
                if (current.model != null) Destroy(current.model);
                _models.Remove(i);
                if (ch < 0 || pedestals[i] == null) continue;
                var def = db.GetCharacter(ch);
                if (def.model == null) continue;
                var m = Instantiate(def.model, pedestals[i]);
                m.transform.localPosition = Vector3.zero;
                m.transform.localRotation = Quaternion.identity;
                m.transform.localScale = Vector3.one;
                m.AddComponent<ProceduralRig>();
                FxManager.Instance?.UpgradeBurst(pedestals[i].position, def.color);
                _models[i] = (ch, m);
            }
            for (int i = 0; i < pedestals.Length; i++)
                if (pedestals[i] != null)
                    pedestals[i].localRotation = Quaternion.Euler(0, 180f + Mathf.Sin(Time.time * 0.8f + i) * 25f, 0);
        }
    }
}
