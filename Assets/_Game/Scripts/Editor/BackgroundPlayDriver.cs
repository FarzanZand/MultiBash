using UnityEditor;
using UnityEditorInternal;

namespace MultiBash.EditorTools
{
    /// <summary>
    /// Keeps Play Mode simulating while the Unity Editor window is in the background
    /// (handy when testing multiplayer with a second game window in front).
    /// Toggle: MultiBash > Keep Playing In Background.
    /// </summary>
    [InitializeOnLoad]
    public static class BackgroundPlayDriver
    {
        const string Key = "MultiBash.KeepPlayingInBackground";
        const string MenuPath = "MultiBash/Keep Playing In Background";

        static BackgroundPlayDriver()
        {
            EditorApplication.update += Tick;
        }

        static bool Enabled => EditorPrefs.GetBool(Key, true);

        [MenuItem(MenuPath, priority = 50)]
        static void Toggle() => EditorPrefs.SetBool(Key, !Enabled);

        [MenuItem(MenuPath, true)]
        static bool ToggleValidate()
        {
            Menu.SetChecked(MenuPath, Enabled);
            return true;
        }

        static void Tick()
        {
            if (Enabled && EditorApplication.isPlaying && !EditorApplication.isPaused && !InternalEditorUtility.isApplicationActive)
                EditorApplication.QueuePlayerLoopUpdate();
        }
    }
}
