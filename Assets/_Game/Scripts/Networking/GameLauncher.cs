using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using Fusion;
using Fusion.Photon.Realtime;
using Fusion.Sockets;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace MultiBash
{
    /// <summary>
    /// Starts / joins / leaves Fusion sessions and spawns a PlayerData for each player that joins.
    /// Lives on the persistent GameServices object.
    ///
    /// Room codes look like "K7QX2-eu": 5 letters + the Photon region the host is in, so friends in other
    /// countries always land in the same region.
    /// </summary>
    public class GameLauncher : MonoBehaviour, INetworkRunnerCallbacks
    {
        public static GameLauncher Instance { get; private set; }

        public NetworkRunner Runner { get; private set; }
        public string RoomCode { get; private set; } = "";
        public bool IsBusy { get; private set; }
        public static string LastError;

        public event Action<string> StatusChanged;

        const string CodeChars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";

        void Awake()
        {
            Instance = this;
        }

        void Start()
        {
            // Command line (handy for testing two copies on one PC):
            //   -name Bob  -character 2  -map 1  -host  -join K7QX2-eu  -autopilot
            var args = System.Environment.GetCommandLineArgs();
            string join = null;
            bool host = false;
            for (int i = 0; i < args.Length; i++)
            {
                string next = i + 1 < args.Length ? args[i + 1] : null;
                switch (args[i])
                {
                    case "-name" when next != null: PlayerName = next; break;
                    case "-character" when next != null && int.TryParse(next, out int c): PlayerPrefs.SetInt("character", c); break;
                    case "-map" when next != null && int.TryParse(next, out int m): PlayerPrefs.SetInt("map", m); break;
                    case "-join" when next != null: join = next; break;
                    case "-host": host = true; break;
                }
            }
            if (join != null) { _ = Join(join); return; }
            if (host) { _ = Host(); return; }

            // Pressing Play directly in the Lobby or Game scene: start an offline single-player session so you can iterate fast.
            int scene = SceneManager.GetActiveScene().buildIndex;
            if (scene >= SceneIds.Lobby)
                _ = StartSession(GameMode.Single, null, null, scene);
        }

        public static string PlayerName
        {
            get => PlayerPrefs.GetString("playerName", "Player" + UnityEngine.Random.Range(100, 999));
            set => PlayerPrefs.SetString("playerName", string.IsNullOrWhiteSpace(value) ? "Player" : value.Trim());
        }

        public static bool HasAppId
        {
            get
            {
                var s = PhotonAppSettings.Global;
                return s != null && !string.IsNullOrWhiteSpace(s.AppSettings.AppIdFusion);
            }
        }

        // ------------------------------------------------------------------ public API (called by menus)

        public Task Host() => StartSession(GameMode.Host, GenerateCode(), null, SceneIds.Lobby);

        public Task Join(string code)
        {
            code = (code ?? "").Trim();
            string region = null;
            int dash = code.LastIndexOf('-');
            if (dash > 0)
            {
                region = code.Substring(dash + 1).ToLowerInvariant();
                code = code.Substring(0, dash);
            }
            code = code.ToUpperInvariant();
            if (code.Length == 0)
            {
                SetStatus("Enter a room code first.");
                return Task.CompletedTask;
            }
            return StartSession(GameMode.Client, code, region, SceneIds.Lobby);
        }

        public Task QuickJoin() => StartSession(GameMode.AutoHostOrClient, null, null, SceneIds.Lobby);

        public Task Solo() => StartSession(GameMode.Single, null, null, SceneIds.Lobby);

        public async void Leave()
        {
            if (Runner != null)
                await Runner.Shutdown();
            else
                ReturnToMenu();
        }

        // ------------------------------------------------------------------ session start

        async Task StartSession(GameMode mode, string code, string region, int sceneIndex)
        {
            if (IsBusy) return;
            if (mode != GameMode.Single && !HasAppId)
            {
                SetStatus("No Photon App ID set. In Unity: Tools > Fusion > Realtime Settings, paste your Fusion App ID.");
                return;
            }

            IsBusy = true;
            LastError = null;
            SetStatus(mode switch
            {
                GameMode.Host => "Creating party...",
                GameMode.Client => $"Joining {code}...",
                GameMode.Single => "Starting solo run...",
                _ => "Looking for a party...",
            });

            var go = new GameObject("NetworkRunner");
            DontDestroyOnLoad(go);
            Runner = go.AddComponent<NetworkRunner>();
            Runner.ProvideInput = true;
            Runner.AddCallbacks(this);
            var sceneManager = go.AddComponent<NetworkSceneManagerDefault>();

            var appSettings = PhotonAppSettings.Global.AppSettings.GetCopy();
            if (!string.IsNullOrEmpty(region)) appSettings.FixedRegion = region;

            var args = new StartGameArgs
            {
                GameMode = mode,
                SessionName = code,
                PlayerCount = 4,
                SceneManager = sceneManager,
                Scene = SceneRef.FromIndex(sceneIndex),
                CustomPhotonAppSettings = appSettings,
                IsOpen = true,
                IsVisible = true,
            };

            StartGameResult result;
            try
            {
                result = await Runner.StartGame(args);
            }
            catch (Exception e)
            {
                result = null;
                Debug.LogException(e);
            }

            IsBusy = false;
            if (result == null || !result.Ok)
            {
                string reason = result != null ? $"{result.ShutdownReason}" : "unknown error";
                LastError = reason switch
                {
                    "GameNotFound" => $"No party found with code {code}.",
                    "GameIsFull" => "That party is full (4/4).",
                    "GameClosed" => "That party is closed.",
                    "InvalidAuthentication" or "CustomAuthenticationFailed" => "Photon rejected the App ID. Check Tools > Fusion > Realtime Settings.",
                    _ => $"Could not connect ({reason}).",
                };
                SetStatus(LastError);
                if (Runner != null) Destroy(Runner.gameObject);
                Runner = null;
                return;
            }

            if (mode == GameMode.Single)
                RoomCode = "SOLO";
            else
            {
                string reg = Runner.SessionInfo.Region;
                RoomCode = string.IsNullOrEmpty(reg) ? Runner.SessionInfo.Name : $"{Runner.SessionInfo.Name}-{reg}";
            }
            Debug.Log($"[MultiBash] Session started: mode={mode} code={RoomCode}");
            SetStatus("");
        }

        static string GenerateCode()
        {
            var c = new char[5];
            for (int i = 0; i < c.Length; i++) c[i] = CodeChars[UnityEngine.Random.Range(0, CodeChars.Length)];
            return new string(c);
        }

        void SetStatus(string s) => StatusChanged?.Invoke(s);

        void ReturnToMenu()
        {
            Runner = null;
            RoomCode = "";
            PlayerData.All.Clear();
            Cursor.lockState = CursorLockMode.None;
            Cursor.visible = true;
            if (SceneManager.GetActiveScene().buildIndex != SceneIds.MainMenu)
                SceneManager.LoadScene(SceneIds.MainMenu);
        }

        // ------------------------------------------------------------------ host-side scene helpers

        public void LoadGameScene()
        {
            if (Runner == null || !Runner.IsSceneAuthority) return;
            var host = PlayerData.Host;
            var map = GameDatabase.Instance.GetMap(host != null ? host.MapIndex : 0);
            int index = SceneIds.Game;
            if (map != null)
            {
                int found = SceneUtility.GetBuildIndexByScenePath($"Assets/_Game/Scenes/{map.sceneName}.unity");
                if (found >= 0) index = found;
            }
            Runner.LoadScene(SceneRef.FromIndex(index));
        }

        public void LoadLobbyScene()
        {
            if (Runner != null && Runner.IsSceneAuthority)
                Runner.LoadScene(SceneRef.FromIndex(SceneIds.Lobby));
        }

        // ------------------------------------------------------------------ Fusion callbacks

        public void OnPlayerJoined(NetworkRunner runner, PlayerRef player)
        {
            if (!runner.IsServer) return;
            var db = GameDatabase.Instance;
            var obj = runner.Spawn(db.playerDataPrefab, Vector3.zero, Quaternion.identity, player);
            runner.SetPlayerObject(player, obj);
        }

        public void OnPlayerLeft(NetworkRunner runner, PlayerRef player)
        {
            if (!runner.IsServer) return;
            if (runner.TryGetPlayerObject(player, out var obj) && obj != null)
            {
                var data = obj.GetComponent<PlayerData>();
                if (data != null && data.Character != null) runner.Despawn(data.Character.Object);
                runner.Despawn(obj);
            }
        }

        public void OnInput(NetworkRunner runner, NetworkInput input)
        {
            if (LocalInput.Instance != null) input.Set(LocalInput.Instance.Collect());
        }

        public void OnShutdown(NetworkRunner runner, ShutdownReason shutdownReason)
        {
            if (shutdownReason != ShutdownReason.Ok)
            {
                LastError = shutdownReason switch
                {
                    ShutdownReason.DisconnectedByPluginLogic or ShutdownReason.ServerInRoom => "The host left the party.",
                    ShutdownReason.PhotonCloudTimeout or ShutdownReason.ConnectionTimeout => "Connection timed out.",
                    _ => $"Disconnected ({shutdownReason}).",
                };
            }
            if (runner != null && runner.gameObject != null) Destroy(runner.gameObject);
            ReturnToMenu();
        }

        public void OnDisconnectedFromServer(NetworkRunner runner, NetDisconnectReason reason)
        {
            LastError = "Lost connection to the host.";
        }

        public void OnConnectedToServer(NetworkRunner runner) { }
        public void OnConnectRequest(NetworkRunner runner, NetworkRunnerCallbackArgs.ConnectRequest request, byte[] token) { }
        public void OnConnectFailed(NetworkRunner runner, NetAddress remoteAddress, NetConnectFailedReason reason) { }
        public void OnUserSimulationMessage(NetworkRunner runner, SimulationMessagePtr message) { }
        public void OnSessionListUpdated(NetworkRunner runner, List<SessionInfo> sessionList) { }
        public void OnCustomAuthenticationResponse(NetworkRunner runner, Dictionary<string, object> data) { }
        public void OnHostMigration(NetworkRunner runner, HostMigrationToken hostMigrationToken) { }
        public void OnReliableDataReceived(NetworkRunner runner, PlayerRef player, ReliableKey key, ReadOnlySpan<byte> data) { }
        public void OnReliableDataProgress(NetworkRunner runner, PlayerRef player, ReliableKey key, float progress) { }
        public void OnInputMissing(NetworkRunner runner, PlayerRef player, NetworkInput input) { }
        public void OnObjectExitAOI(NetworkRunner runner, NetworkObject obj, PlayerRef player) { }
        public void OnObjectEnterAOI(NetworkRunner runner, NetworkObject obj, PlayerRef player) { }
        public void OnSceneLoadDone(NetworkRunner runner) { }
        public void OnSceneLoadStart(NetworkRunner runner) { }
    }
}
