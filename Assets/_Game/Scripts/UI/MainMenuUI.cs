using UnityEngine;
using UnityEngine.UI;

namespace MultiBash
{
    /// <summary>Title screen: name, Host / Join by code / Quick Join / Solo / Quit (pixel style).</summary>
    public class MainMenuUI : MonoBehaviour
    {
        Text _status;
        InputField _name;
        InputField _code;
        Button[] _buttons;

        void Start()
        {
            LocalInput.Blocked = false;
            CameraRig.MenuOpen = true;
            Cursor.lockState = CursorLockMode.None;
            Cursor.visible = true;
            AudioManager.PlayMusic(AudioManager.Lib != null ? AudioManager.Lib.menuMusic : null);
            Build();
            if (GameLauncher.Instance != null) GameLauncher.Instance.StatusChanged += OnStatus;
            if (!string.IsNullOrEmpty(GameLauncher.LastError))
            {
                OnStatus(GameLauncher.LastError);
                GameLauncher.LastError = null;
            }
        }

        void OnDestroy()
        {
            if (GameLauncher.Instance != null) GameLauncher.Instance.StatusChanged -= OnStatus;
        }

        void OnStatus(string s)
        {
            if (_status != null) _status.text = s;
        }

        void Build()
        {
            var T = UIKit.T;
            var root = UIKit.Canvas("MainMenuCanvas", 10, transform).transform;

            // title
            var title = UIKit.Label(root, "MultiBash", 144, T.accent, new Vector2(0, 1), new Vector2(90, -40), new Vector2(1000, 170), TextAnchor.UpperLeft, UIFont.Header, false);
            UIKit.Outline(title, 6);
            var sub = UIKit.Label(root, "a co-op horde survival for 1-4 friends", 36, T.text, new Vector2(0, 1), new Vector2(100, -200), new Vector2(1000, 50), TextAnchor.UpperLeft, UIFont.Header, false);
            UIKit.Outline(sub, 3);

            // menu window
            var win = UIKit.Panel(root, "Menu", new Vector2(0, 0.5f), new Vector2(90, -70), new Vector2(600, 640), "Main Menu");
            float y = -96;
            UIKit.Label(win, "Your name", 27, T.mutedText, new Vector2(0, 1), new Vector2(36, y), new Vector2(528, 34), TextAnchor.MiddleLeft, UIFont.Body, false);
            y -= 38;
            _name = UIKit.Input(win, "Enter a name", new Vector2(0, 1), new Vector2(36, y), new Vector2(528, 62));
            _name.characterLimit = 16;
            _name.text = GameLauncher.PlayerName;
            _name.onEndEdit.AddListener(v => GameLauncher.PlayerName = v);
            y -= 86;

            var host = UIKit.Button(win, "Host Party", new Vector2(0, 1), new Vector2(36, y), new Vector2(528, 74), () => Run(() => GameLauncher.Instance.Host()), T.buttonBlue, 45);
            y -= 90;
            _code = UIKit.Input(win, "Room code  (K7QX2-eu)", new Vector2(0, 1), new Vector2(36, y), new Vector2(340, 70));
            _code.characterLimit = 12;
            var join = UIKit.Button(win, "Join", new Vector2(0, 1), new Vector2(392, y), new Vector2(172, 70), () => Run(() => GameLauncher.Instance.Join(_code.text)), T.buttonGreen, 36);
            y -= 86;
            var quick = UIKit.Button(win, "Quick Join", new Vector2(0, 1), new Vector2(36, y), new Vector2(256, 66), () => Run(() => GameLauncher.Instance.QuickJoin()), T.buttonGrey, 36);
            var solo = UIKit.Button(win, "Play Solo", new Vector2(0, 1), new Vector2(308, y), new Vector2(256, 66), () => Run(() => GameLauncher.Instance.Solo()), T.buttonGrey, 36);
            y -= 82;
            UIKit.Button(win, "Quit", new Vector2(0, 1), new Vector2(36, y), new Vector2(528, 60), Quit, T.buttonRed, 36);
            y -= 76;
            _status = UIKit.Label(win, "", 27, T.accent, new Vector2(0, 1), new Vector2(36, y), new Vector2(528, 80), TextAnchor.UpperLeft, UIFont.Body);
            _buttons = new[] { host, join, quick, solo };

            if (!GameLauncher.HasAppId)
            {
                var warn = UIKit.Panel(root, "AppIdWarning", new Vector2(1, 0), new Vector2(-40, 70), new Vector2(640, 200), "Online play");
                UIKit.Label(warn, "Needs a Photon App ID:\nTools > Fusion > Realtime Settings > App Id Fusion.\nSolo play works without it.",
                    27, T.text, new Vector2(0.5f, 0), new Vector2(0, 20), new Vector2(580, 110), TextAnchor.MiddleLeft);
            }

            var help = UIKit.Label(root, "WASD move  |  Mouse camera  |  Space jump  |  Shift slide  |  1/2/3 upgrades  |  Esc menu",
                27, T.text, new Vector2(0.5f, 0), new Vector2(0, 18), new Vector2(1700, 40), TextAnchor.MiddleCenter, UIFont.Body, false);
            UIKit.Outline(help, 2);
            var ver = UIKit.Label(root, "version 0.2", 24, T.text, new Vector2(1, 0), new Vector2(-20, 14), new Vector2(300, 30), TextAnchor.LowerRight, UIFont.Number, false);
            UIKit.Outline(ver, 2);
        }

        async void Run(System.Func<System.Threading.Tasks.Task> action)
        {
            if (GameLauncher.Instance == null || GameLauncher.Instance.IsBusy) return;
            GameLauncher.PlayerName = _name.text;
            foreach (var b in _buttons) b.interactable = false;
            await action();
            if (this != null)
                foreach (var b in _buttons) if (b != null) b.interactable = true;
        }

        void Quit()
        {
#if UNITY_EDITOR
            UnityEditor.EditorApplication.isPlaying = false;
#else
            Application.Quit();
#endif
        }
    }
}
