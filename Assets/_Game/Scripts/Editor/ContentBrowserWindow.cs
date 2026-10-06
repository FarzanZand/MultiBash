using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEngine;

namespace MultiBash.EditorTools
{
    /// <summary>
    /// MultiBash > Content Browser: every character, weapon, powerup, enemy and wave in one window,
    /// with an inline inspector and buttons to create new content.
    /// </summary>
    public class ContentBrowserWindow : EditorWindow
    {
        static readonly string[] Tabs = { "Characters", "Weapons", "Powerups", "Enemies", "Waves & Config" };
        int _tab;
        Vector2 _listScroll, _inspectorScroll;
        Object _selected;
        Editor _editor;

        [MenuItem("MultiBash/Content Browser", priority = 0)]
        public static void Open() => GetWindow<ContentBrowserWindow>("MultiBash Content").minSize = new Vector2(760, 420);

        void OnGUI()
        {
            EditorGUILayout.Space(4);
            int tab = GUILayout.Toolbar(_tab, Tabs, GUILayout.Height(26));
            if (tab != _tab) { _tab = tab; Select(null); }
            EditorGUILayout.Space(4);

            EditorGUILayout.BeginHorizontal();
            DrawList();
            DrawInspector();
            EditorGUILayout.EndHorizontal();
        }

        void DrawList()
        {
            EditorGUILayout.BeginVertical(GUILayout.Width(260));
            var items = Items().ToList();
            _listScroll = EditorGUILayout.BeginScrollView(_listScroll, "box");
            foreach (var item in items)
            {
                var icon = Icon(item);
                var style = new GUIStyle(EditorStyles.toolbarButton) { alignment = TextAnchor.MiddleLeft, fixedHeight = 40, fontSize = 12 };
                var content = new GUIContent("  " + Label(item), icon != null ? icon.texture : null);
                bool on = _selected == item;
                if (GUILayout.Toggle(on, content, style, GUILayout.Height(40)) && !on) Select(item);
            }
            EditorGUILayout.EndScrollView();

            if (_tab < 4 && GUILayout.Button("+ Create new " + Tabs[_tab].TrimEnd('s'), GUILayout.Height(28))) CreateNew();
            if (GUILayout.Button("Refresh Database", GUILayout.Height(22))) MultiBashSetup.RefreshDatabase();
            EditorGUILayout.EndVertical();
        }

        void DrawInspector()
        {
            EditorGUILayout.BeginVertical();
            _inspectorScroll = EditorGUILayout.BeginScrollView(_inspectorScroll, "box");
            if (_selected == null)
            {
                EditorGUILayout.HelpBox(
                    "Pick something on the left to edit it.\n\n" +
                    "• Every number here is live data: change it, press Play, feel the difference.\n" +
                    "• New content is picked up automatically (Refresh Database).\n" +
                    "• Enemies need a prefab: duplicate an existing enemy folder and swap the model.",
                    MessageType.Info);
            }
            else
            {
                EditorGUILayout.BeginHorizontal();
                EditorGUILayout.LabelField(_selected.name, EditorStyles.boldLabel);
                if (GUILayout.Button("Ping", GUILayout.Width(60))) EditorGUIUtility.PingObject(_selected);
                EditorGUILayout.EndHorizontal();
                if (_editor == null || _editor.target != _selected) Editor.CreateCachedEditor(_selected, null, ref _editor);
                _editor.OnInspectorGUI();
            }
            EditorGUILayout.EndScrollView();
            EditorGUILayout.EndVertical();
        }

        void Select(Object o)
        {
            _selected = o;
            if (o != null) Selection.activeObject = o;
        }

        IEnumerable<Object> Items()
        {
            switch (_tab)
            {
                case 0: return FindAll<CharacterDefinition>();
                case 1: return FindAll<WeaponDefinition>();
                case 2: return FindAll<PowerupDefinition>();
                case 3: return FindAll<EnemyDefinition>();
                default: return FindAll<WaveDefinition>().Concat(FindAll<GameConfig>()).Concat(FindAll<UITheme>()).Concat(FindAll<AudioLibrary>());
            }
        }

        static IEnumerable<Object> FindAll<T>() where T : Object =>
            AssetDatabase.FindAssets("t:" + typeof(T).Name, new[] { "Assets/_Game" })
                .Select(g => AssetDatabase.LoadAssetAtPath<T>(AssetDatabase.GUIDToAssetPath(g)))
                .Where(x => x != null).OrderBy(x => x.name);

        static Sprite Icon(Object o) => o switch
        {
            CharacterDefinition c => c.portrait,
            WeaponDefinition w => w.icon,
            PowerupDefinition p => p.icon,
            _ => null,
        };

        static string Label(Object o) => o switch
        {
            CharacterDefinition c => c.displayName,
            WeaponDefinition w => $"{w.displayName}  ({w.kind})",
            PowerupDefinition p => $"{p.displayName}  ({p.rarity})",
            EnemyDefinition e => $"{e.displayName}  ({e.maxHealth} HP)",
            _ => o.name,
        };

        void CreateNew()
        {
            string folder = MultiBashSetup.Content + "/" + Tabs[_tab];
            string name = "New" + Tabs[_tab].TrimEnd('s');
            string path = AssetDatabase.GenerateUniqueAssetPath($"{folder}/{name}.asset");
            ScriptableObject so = _tab switch
            {
                0 => CreateInstance<CharacterDefinition>(),
                1 => CreateInstance<WeaponDefinition>(),
                2 => CreateInstance<PowerupDefinition>(),
                _ => CreateInstance<EnemyDefinition>(),
            };
            AssetDatabase.CreateAsset(so, path);
            AssetDatabase.SaveAssets();
            MultiBashSetup.RefreshDatabase();
            Select(so);
        }
    }
}
