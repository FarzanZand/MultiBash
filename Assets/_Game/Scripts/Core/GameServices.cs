using UnityEngine;

namespace MultiBash
{
    /// <summary>
    /// Makes sure the persistent systems (launcher, audio, input) exist no matter which scene you press Play in.
    /// The prefab lives at Prefabs/Systems/Resources/GameServices.prefab.
    /// </summary>
    public static class GameServices
    {
        static bool _created;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
        static void Bootstrap()
        {
            if (_created) return;
            _created = true;
            var prefab = Resources.Load<GameObject>("GameServices");
            if (prefab == null)
            {
                Debug.LogError("[MultiBash] GameServices prefab missing. Run MultiBash > Setup > Build Everything.");
                return;
            }
            var go = Object.Instantiate(prefab);
            go.name = "GameServices";
            Object.DontDestroyOnLoad(go);
        }

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        static void ResetStatics() => _created = false;
    }

    public static class SceneIds
    {
        public const int MainMenu = 0;
        public const int Lobby = 1;
        public const int Game = 2;
    }
}
