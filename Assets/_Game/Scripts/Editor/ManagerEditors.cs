using System.Linq;
using UnityEditor;
using UnityEngine;

namespace MultiBash.EditorTools
{
    /// <summary>Shared look for the two manager inspectors: the settings asset drawn inline + a play-mode panel.</summary>
    abstract class ManagerEditorBase<TManager, TSettings> : Editor where TManager : MonoBehaviour where TSettings : ScriptableObject
    {
        Editor _inner;
        protected abstract string Intro { get; }
        protected abstract TSettings GetSettings(TManager m);
        protected abstract void SetSettings(TManager m, TSettings s);
        protected abstract void LivePanel(TManager m);

        protected static bool IsHost =>
            Application.isPlaying && GameManager.Instance != null && GameManager.Instance.Object != null && GameManager.Instance.Object.IsValid
            && GameManager.Instance.Object.HasStateAuthority;

        public override bool RequiresConstantRepaint() => Application.isPlaying;

        public override void OnInspectorGUI()
        {
            var m = (TManager)target;
            EditorGUILayout.HelpBox(Intro, MessageType.None);

            serializedObject.Update();
            EditorGUILayout.PropertyField(serializedObject.FindProperty("settings"));
            serializedObject.ApplyModifiedProperties();
            var s = GetSettings(m);
            if (s == null)
            {
                EditorGUILayout.HelpBox("No settings asset assigned: the game uses the default one from the GameDatabase.", MessageType.Info);
                return;
            }

            using (new EditorGUILayout.HorizontalScope())
            {
                EditorGUILayout.LabelField(AssetDatabase.GetAssetPath(s), EditorStyles.miniLabel);
                if (GUILayout.Button(new GUIContent("Copy for this map", "Make a separate copy of these settings for just this scene/map."), GUILayout.Width(120)))
                {
                    string src = AssetDatabase.GetAssetPath(s);
                    string dst = AssetDatabase.GenerateUniqueAssetPath(src.Replace(".asset", "_" + m.gameObject.scene.name + ".asset"));
                    AssetDatabase.CopyAsset(src, dst);
                    Undo.RecordObject(m, "Use map settings");
                    SetSettings(m, AssetDatabase.LoadAssetAtPath<TSettings>(dst));
                    EditorUtility.SetDirty(m);
                }
                if (GUILayout.Button("Select", GUILayout.Width(55))) Selection.activeObject = s;
            }

            if (Application.isPlaying)
            {
                EditorGUILayout.Space(4);
                using (new EditorGUILayout.VerticalScope(EditorStyles.helpBox))
                {
                    EditorGUILayout.LabelField("Live (play mode)", EditorStyles.boldLabel);
                    if (!IsHost) EditorGUILayout.HelpBox("Start or host a run to use the test tools (they act on the host).", MessageType.Info);
                    else LivePanel(m);
                }
            }

            EditorGUILayout.Space(6);
            CreateCachedEditor(s, null, ref _inner);
            _inner.OnInspectorGUI();
        }

        protected static void Row(string label, string value) => EditorGUILayout.LabelField(label, value);
    }

    [CustomEditor(typeof(ProgressionManager))]
    class ProgressionManagerEditor : ManagerEditorBase<ProgressionManager, ProgressionSettings>
    {
        protected override string Intro =>
            "Run progression: leveling, upgrade offers, enemy scaling, stages, spawning, drops, combo and revives.\n" +
            "Edits apply live. The host's values decide the run (enemy HP, XP, spawns), so tune on the hosting machine. " +
            "Wave timelines (what spawns when) are the WaveDefinition assets in Content/Waves.";

        protected override ProgressionSettings GetSettings(ProgressionManager m) => m.settings;
        protected override void SetSettings(ProgressionManager m, ProgressionSettings s) => m.settings = s;

        protected override void LivePanel(ProgressionManager m)
        {
            var gm = GameManager.Instance;
            var P = ProgressionManager.Settings;
            Row("Run time", $"{UIKit.FormatTime(gm.RunTime)} / {UIKit.FormatTime(P.runDurationSeconds)}   ({gm.State})");
            Row("Team level", $"{gm.TeamLevel}   XP {gm.TeamXP}/{gm.XPToNext}");
            Row("Stage", $"{P.StageAt(gm.RunTime) + 1} of 3");
            Row("Enemies alive", $"{EnemyRegistry.All.Count} / {P.maxEnemies}   (kills {gm.TotalKills})");
            Row("Enemy HP x (normal / fodder)", $"{ProgressionManager.CurrentEnemyHealthMultiplier():0.00}  /  {ProgressionManager.CurrentEnemyHealthMultiplier(true):0.00}");
            Row("Enemy damage x / speed x", $"{P.EnemyDamageMultiplier(gm.RunTime / 60f):0.00}  /  {P.EnemySpeedMultiplier(gm.RunTime / 60f):0.00}");

            using (new EditorGUILayout.HorizontalScope())
            {
                if (GUILayout.Button("+1 level")) GiveLevels(1);
                if (GUILayout.Button("+5 levels")) GiveLevels(5);
                if (GUILayout.Button("+3 chests")) foreach (var p in PlayerCharacter.All) { p.PendingLevelUps += 3; p.TreasurePicks += 3; }
            }
            using (new EditorGUILayout.HorizontalScope())
            {
                if (GUILayout.Button("Skip 30 s")) AutoPilot.SkipTime(30f);
                if (GUILayout.Button("Skip 1 min")) AutoPilot.SkipTime(60f);
                if (GUILayout.Button("Next stage"))
                {
                    float f = P.StageAt(gm.RunTime) == 0 ? P.stage2At : P.stage3At;
                    gm.RunTime = Mathf.Max(gm.RunTime, f * P.runDurationSeconds + 1f);
                }
            }
            using (new EditorGUILayout.HorizontalScope())
            {
                if (GUILayout.Button("Kill all enemies"))
                    foreach (var e in EnemyRegistry.All.ToArray()) if (e != null && e.IsAlive) e.TakeDamage(e.Health + 1f, e.transform.position, 0f, PlayerCharacter.Local);
                if (GUILayout.Button("Treasure Slime")) SpawnNear(GameDatabase.Instance.enemies.Find(e => e.dropChests > 0), false);
                if (GUILayout.Button("Spawn boss"))
                {
                    var b = gm.Waves != null ? gm.Waves.bursts.FirstOrDefault(x => x.boss && x.minute * 60f > gm.RunTime) ?? gm.Waves.bursts.FirstOrDefault(x => x.boss) : null;
                    if (b != null) { SpawnNear(b.enemy, true); gm.Announce($"{b.enemy.bossName} (test)"); }
                }
            }
        }

        static void GiveLevels(int n)
        {
            var gm = GameManager.Instance;
            for (int i = 0; i < n; i++) gm.AddXP((gm.XPToNext - gm.TeamXP + 1) / ProgressionManager.Settings.xpMultiplier);
        }

        static void SpawnNear(EnemyDefinition def, bool boss)
        {
            var me = PlayerCharacter.Local;
            if (def == null || me == null) return;
            var p = Ground.Snap(me.transform.position + me.transform.forward * (boss ? 14f : 8f));
            GameManager.Instance.SpawnEnemy(def, p, boss, boss);
            if (boss) GameManager.Instance.Rpc_BossSpawned(p);
        }
    }

    [CustomEditor(typeof(CombatManager))]
    class CombatManagerEditor : ManagerEditorBase<CombatManager, CombatSettings>
    {
        protected override string Intro =>
            "Combat feel: hero base stats and movement, global damage / cooldown / area knobs, crits, knockback, damage taken, " +
            "item effects and screen feel. Damage and enemy values are decided by the host and apply live.\n" +
            "Multiplayer note: movement and base stats are also predicted on each player's machine, so friends need a build " +
            "with the same values (rebuild after changing Movement or Hero base stats). Per-weapon numbers live on the weapon assets in Content/Weapons.";

        protected override CombatSettings GetSettings(CombatManager m) => m.settings;
        protected override void SetSettings(CombatManager m, CombatSettings s) => m.settings = s;

        protected override void LivePanel(CombatManager m)
        {
            var me = PlayerCharacter.Local;
            if (me != null)
            {
                var st = me.Stats;
                Row("Your hero", $"{me.Def?.displayName}  HP {me.Health:0}/{me.MaxHealth:0}  armor {st.Armor:0}");
                Row("Damage / cooldown / area", $"{st.Damage * 100f:0}%  /  {st.Cooldown * 100f:0}%  /  {st.Area * 100f:0}%");
                Row("Crit / crit dmg / speed", $"{st.CritChance * 100f:0}%  /  x{st.CritDamage:0.0}  /  {st.MoveSpeed:0.0} m/s");
            }
            using (new EditorGUILayout.HorizontalScope())
            {
                PlayerCharacter.DevGodMode = GUILayout.Toggle(PlayerCharacter.DevGodMode, "God mode (all heroes)", "Button");
                if (GUILayout.Button("Heal team")) foreach (var p in PlayerCharacter.All) if (p != null) p.Heal(p.MaxHealth);
                if (GUILayout.Button("Refresh stats")) CombatManager.RefreshHeroStats();
            }
            using (new EditorGUILayout.HorizontalScope())
            {
                if (GUILayout.Button("Max my weapons") && me != null)
                {
                    var db = GameDatabase.Instance;
                    for (int i = 0; i < PlayerCharacter.MaxWeaponSlots; i++)
                    {
                        var w = db.GetWeapon(me.WeaponIds.Get(i) - 1);
                        if (w != null) me.WeaponLevels.Set(i, (byte)w.MaxLevel);
                    }
                    me.LoadoutVersion++;
                }
                if (GUILayout.Button("+1 Power Surge") && me != null) { me.PowerSurges++; me.LoadoutVersion++; }
                AutoPilot.Enabled = GUILayout.Toggle(AutoPilot.Enabled, "Bot plays me", "Button");
            }
        }
    }
}
