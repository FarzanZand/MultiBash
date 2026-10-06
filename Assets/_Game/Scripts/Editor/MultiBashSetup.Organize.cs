using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace MultiBash.EditorTools
{
    /// <summary>
    /// Keeps every scene's hierarchy tidy and the same everywhere:
    ///   --- Managers ---     GameManager, ProgressionManager, CombatManager, FxManager
    ///   --- Gameplay ---     shrines, lava and other things the run interacts with
    ///   --- Environment ---  sun, post-processing, terrain, walls, props
    ///   --- Camera & UI ---  camera rig, HUD / menu UI
    ///   --- Showcase ---     menu/lobby display models
    /// Run it from "MultiBash/Organize Scene Hierarchy"; the scene builders call it too, so rebuilds stay organized.
    /// Grouping objects are plain empties at the origin (scene NetworkObjects are fine under them).
    /// </summary>
    public static partial class MultiBashSetup
    {
        static readonly string[] GameScenes = { "Game", "Volcano" };
        static readonly string[] AllScenes = { "MainMenu", "Lobby", "Game", "Volcano" };

        const string GManagers = "--- Managers ---", GGameplay = "--- Gameplay ---", GEnv = "--- Environment ---",
            GCamUI = "--- Camera & UI ---", GShow = "--- Showcase ---";

        [MenuItem("MultiBash/Organize Scene Hierarchy", priority = 21)]
        public static void OrganizeAllScenes()
        {
            if (EditorApplication.isPlaying) { Debug.LogWarning("[MultiBash] Stop play mode first."); return; }
            if (!EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo()) return;
            var active = SceneManager.GetActiveScene().path;
            foreach (var name in AllScenes)
            {
                string path = $"{Scenes}/{name}.unity";
                if (!System.IO.File.Exists(path)) continue;
                var scene = EditorSceneManager.OpenScene(path, OpenSceneMode.Single);
                OrganizeScene(scene);
                EditorSceneManager.SaveScene(scene);
            }
            if (!string.IsNullOrEmpty(active)) EditorSceneManager.OpenScene(active, OpenSceneMode.Single);
            Debug.Log("[MultiBash] Scene hierarchies organized.");
        }

        /// <summary>Group the root objects of a scene (and make sure game scenes have their managers).</summary>
        public static void OrganizeScene(Scene scene)
        {
            bool game = GameScenes.Contains(scene.name) || scene.GetRootGameObjects().Any(r => r.GetComponentInChildren<GameManager>(true) != null);
            if (game) EnsureManagers(scene);

            var groups = new Dictionary<string, Transform>();
            Transform Group(string n, int order)
            {
                if (groups.TryGetValue(n, out var t)) return t;
                var existing = scene.GetRootGameObjects().FirstOrDefault(r => r.name == n);
                t = existing != null ? existing.transform : new GameObject(n).transform;
                if (existing == null) SceneManager.MoveGameObjectToScene(t.gameObject, scene);
                t.SetPositionAndRotation(Vector3.zero, Quaternion.identity);
                t.localScale = Vector3.one;
                t.SetSiblingIndex(order);
                groups[n] = t;
                return t;
            }

            foreach (var root in scene.GetRootGameObjects())
            {
                if (root.name.StartsWith("---")) continue;
                string g = Classify(root);
                if (g == null) continue;
                int order = g == GManagers ? 0 : g == GGameplay ? 1 : g == GCamUI ? 2 : g == GShow ? 3 : 4;
                root.transform.SetParent(Group(g, order), true);
            }
            // fixed order of the groups
            string[] ordered = { GManagers, GGameplay, GCamUI, GShow, GEnv };
            int idx = 0;
            foreach (var n in ordered) if (groups.TryGetValue(n, out var t)) t.SetSiblingIndex(idx++);
            EditorSceneManager.MarkSceneDirty(scene);
        }

        static string Classify(GameObject go)
        {
            if (go.GetComponent<GameManager>() || go.GetComponent<ProgressionManager>() || go.GetComponent<CombatManager>() || go.GetComponent<FxManager>())
                return GManagers;
            if (go.GetComponent<Shrine>() || go.GetComponent<LavaZone>() || go.GetComponent<Breakables>() || go.GetComponent<IceZone>() || go.name == "JumpPads")
                return GGameplay;
            if (go.GetComponent<CameraRig>() || go.GetComponent<Camera>() || go.GetComponent<HUD>() || go.GetComponent<LobbyUI>() || go.GetComponent<MainMenuUI>()
                || go.GetComponent<UnityEngine.EventSystems.EventSystem>())
                return GCamUI;
            string n = go.name;
            if (n.StartsWith("Pedestal") || n.StartsWith("Spot") || n == "Pivot") return GShow;
            if (go.GetComponent<Light>() || go.GetComponent<UnityEngine.Rendering.Volume>() || go.GetComponent<Terrain>() || n == "Props" || n == "ArenaWalls"
                || n == "Ground" || n == "LavaGlow" || n == "Water")
                return GEnv;
            // menu showcase heroes / enemies (model holders)
            if (go.GetComponentInChildren<Renderer>() != null) return GShow;
            return GEnv;
        }

        /// <summary>Game scenes get a ProgressionManager and a CombatManager pointing at the default settings.</summary>
        static void EnsureManagers(Scene scene)
        {
            var roots = scene.GetRootGameObjects();
            var prog = Load<ProgressionSettings>(Content + "/Settings/ProgressionSettings.asset");
            var comb = Load<CombatSettings>(Content + "/Settings/CombatSettings.asset");
            if (!roots.Any(r => r.GetComponentInChildren<ProgressionManager>(true) != null))
            {
                var go = new GameObject("ProgressionManager");
                SceneManager.MoveGameObjectToScene(go, scene);
                go.AddComponent<ProgressionManager>().settings = prog;
            }
            if (!roots.Any(r => r.GetComponentInChildren<CombatManager>(true) != null))
            {
                var go = new GameObject("CombatManager");
                SceneManager.MoveGameObjectToScene(go, scene);
                go.AddComponent<CombatManager>().settings = comb;
            }
            foreach (var r in scene.GetRootGameObjects())
            {
                foreach (var pm in r.GetComponentsInChildren<ProgressionManager>(true)) if (pm.settings == null) pm.settings = prog;
                foreach (var cm in r.GetComponentsInChildren<CombatManager>(true)) if (cm.settings == null) cm.settings = comb;
            }
        }

        /// <summary>Route the AudioManager on the GameServices prefab through the mixer's Music / SFX / UI groups.</summary>
        [MenuItem("MultiBash/Setup/Wire Audio Mixer", priority = 6)]
        public static void WireAudioMixer()
        {
            var mixer = BuildMixer();
            string gs = Prefabs + "/Systems/Resources/GameServices.prefab";
            var root = PrefabUtility.LoadPrefabContents(gs);
            var am = root.GetComponent<AudioManager>();
            if (am != null)
            {
                am.mixer = mixer;
                am.musicGroup = MixerGroup(mixer, "Music");
                am.sfxGroup = MixerGroup(mixer, "SFX");
                am.uiGroup = MixerGroup(mixer, "UI");
                PrefabUtility.SaveAsPrefabAsset(root, gs);
            }
            PrefabUtility.UnloadPrefabContents(root);
            Debug.Log($"[MultiBash] AudioManager routed through {MixerPath} (music={am?.musicGroup != null}, sfx={am?.sfxGroup != null}, ui={am?.uiGroup != null}).");
        }
    }
}
