using System.IO;
using Fusion;
using UnityEditor;
using UnityEngine;

namespace MultiBash.EditorTools
{
    public static partial class MultiBashSetup
    {
        static GameObject SavePrefab(GameObject go, string path)
        {
            Directory.CreateDirectory(Path.GetDirectoryName(path));
            var prefab = PrefabUtility.SaveAsPrefabAsset(go, path);
            Object.DestroyImmediate(go);
            return prefab;
        }

        static bool NeedPrefab(string path) => Force || Load<GameObject>(path) == null;

        static GameObject InstantiateModel(GameObject model, Transform parent)
        {
            var go = (GameObject)PrefabUtility.InstantiatePrefab(model);
            go.transform.SetParent(parent, false);
            go.name = "Model";
            foreach (var r in go.GetComponentsInChildren<Renderer>())
                if (r.sharedMaterial == null || !r.sharedMaterial.name.StartsWith("M_Char_")) r.sharedMaterial = PaletteMat;
            return go;
        }

        static void BuildPrefabs()
        {
            int envLayer = LayerMask.NameToLayer("Environment");
            int playerLayer = LayerMask.NameToLayer("Player");

            // ---------------------------------------------------------------- PlayerData
            string pd = Prefabs + "/Network/PlayerData.prefab";
            if (NeedPrefab(pd))
            {
                var go = new GameObject("PlayerData");
                go.AddComponent<NetworkObject>();
                go.AddComponent<PlayerData>();
                SavePrefab(go, pd);
            }

            // ---------------------------------------------------------------- PlayerCharacter
            string pc = Prefabs + "/Network/PlayerCharacter.prefab";
            if (NeedPrefab(pc))
            {
                var go = new GameObject("PlayerCharacter") { layer = playerLayer };
                go.AddComponent<NetworkObject>();
                var cc = go.AddComponent<CharacterController>();
                cc.height = 1.8f;
                cc.radius = 0.4f;
                cc.center = new Vector3(0, 0.92f, 0);
                cc.stepOffset = 0.45f;
                cc.slopeLimit = 50f;
                cc.skinWidth = 0.05f;
                var ncc = go.AddComponent<NetworkCharacterController>();
                ncc.gravity = -24f;
                ncc.jumpImpulse = 8.5f;
                ncc.maxSpeed = 7f;
                ncc.acceleration = 70f;
                ncc.braking = 16f;
                ncc.rotationSpeed = 18f;
                var visual = new GameObject("Visual");
                visual.transform.SetParent(go.transform, false);
                visual.AddComponent<ProceduralRig>();
                var p = go.AddComponent<PlayerCharacter>();
                var so = new SerializedObject(p);
                so.FindProperty("visualRoot").objectReferenceValue = visual.transform;
                so.ApplyModifiedPropertiesWithoutUndo();
                SavePrefab(go, pc);
            }

            // ---------------------------------------------------------------- enemies
            string E = Content + "/Enemies";
            BuildEnemyPrefab($"{E}/Skeleton/Skeleton.prefab", Model("Enemies", "Skeleton"), 1f, false);
            BuildEnemyPrefab($"{E}/Slime/Slime.prefab", Model("Enemies", "Slime"), 1.15f, true);
            BuildEnemyPrefab($"{E}/Slime/SlimeSmall.prefab", Model("Enemies", "Slime"), 0.6f, true);
            BuildEnemyPrefab($"{E}/Bat/Bat.prefab", Model("Enemies", "Bat"), 1.1f, false);
            BuildEnemyPrefab($"{E}/SkeletonArcher/SkeletonArcher.prefab", Model("Enemies", "SkeletonArcher"), 1f, false);
            BuildEnemyPrefab($"{E}/BombShroom/BombShroom.prefab", Model("Enemies", "BombShroom"), 1f, true);
            BuildEnemyPrefab($"{E}/Golem/Golem.prefab", Model("Enemies", "Golem"), 1.6f, false);
            BuildEnemyPrefab($"{E}/MagmaSlime/MagmaSlime.prefab", Model("Enemies", "MagmaSlime"), 1.15f, true);
            BuildEnemyPrefab($"{E}/MagmaSlime/MagmaSlimeSmall.prefab", Model("Enemies", "MagmaSlime"), 0.6f, true);
            BuildEnemyPrefab($"{E}/FireImp/FireImp.prefab", Model("Enemies", "FireImp"), 1.1f, false);

            // ---------------------------------------------------------------- pickups
            string Pk = Content + "/Pickups";
            BuildPickup($"{Pk}/XPGem.prefab", 0.9f, ("Tier0", Model("Pickups", "GemGreen")), ("Tier1", Model("Pickups", "GemBlue")), ("Tier2", Model("Pickups", "GemRed")));
            BuildPickup($"{Pk}/HealthOrb.prefab", 1.4f, ("Heart", Model("Pickups", "HealthOrb")));
            BuildPickup($"{Pk}/Magnet.prefab", 1.6f, ("Magnet", Model("Pickups", "Magnet")));
            BuildPickup($"{Pk}/Chest.prefab", 1.3f, ("Chest", Model("Pickups", "Chest")));

            // ---------------------------------------------------------------- environment props
            Prop("TombstoneA", 0.55f, PropCollider.Box);
            Prop("TombstoneB", 0.45f, PropCollider.Box);
            Prop("DeadTree", 0.6f, PropCollider.Capsule);
            Prop("TreeA", 0.7f, PropCollider.Capsule);
            Prop("TreeB", 0.7f, PropCollider.Capsule);
            Prop("TreePine", 0.5f, PropCollider.Capsule);
            Prop("Bush", 0f, PropCollider.None);
            Prop("GrassTuft", 0f, PropCollider.None, shadows: false);
            Prop("Log", 0.9f, PropCollider.Box);
            Prop("RockA", 1.0f, PropCollider.Box);
            Prop("RockB", 1.5f, PropCollider.Box);
            Prop("TowerRuin", 2.9f, PropCollider.Mesh);
            Prop("WallRuin", 0f, PropCollider.Box, obstacleLine: 3);
            Prop("PillarBroken", 0.85f, PropCollider.Mesh);
            Prop("Fence", 0f, PropCollider.Box);
            Prop("LanternPost", 0.3f, PropCollider.Capsule, withLight: true);
            Prop("CastleWall", 0f, PropCollider.Box, obstacleLine: 4, lineHalf: 3.2f);
            Prop("CastleTower", 3.3f, PropCollider.Mesh);
            Prop("Arch", 0f, PropCollider.Mesh, obstacleLine: 2, lineHalf: 2.0f);
            Prop("Brazier", 0.6f, PropCollider.Capsule, withLight: true, lightHeight: 1.8f, lightColor: new Color(1f, 0.6f, 0.25f), lightRange: 10f, lightIntensity: 4f);
            Prop("Banner", 0f, PropCollider.None);
            Prop("FlowersA", 0f, PropCollider.None, shadows: false);
            Prop("FlowersB", 0f, PropCollider.None, shadows: false);
            Prop("Mushrooms", 0f, PropCollider.None, shadows: false);
            Prop("Crates", 1.0f, PropCollider.Box);
            Prop("SkullPile", 0f, PropCollider.None, shadows: false);
            Prop("RuneStone", 0.6f, PropCollider.Box);
            Prop("MountainA", 0f, PropCollider.None);
            Prop("MountainB", 0f, PropCollider.None);
            // volcano
            Prop("BasaltColumnsA", 1.3f, PropCollider.Mesh);
            Prop("BasaltColumnsB", 1.3f, PropCollider.Mesh);
            Prop("ObsidianSpire", 0.9f, PropCollider.Capsule);
            Prop("LavaRockA", 1.0f, PropCollider.Box);
            Prop("LavaRockB", 1.5f, PropCollider.Box);
            Prop("CharredTreeA", 0.6f, PropCollider.Capsule);
            Prop("CharredTreeB", 0.6f, PropCollider.Capsule);
            Prop("SulfurVent", 0.9f, PropCollider.Box, withLight: true, lightHeight: 1.2f, lightColor: new Color(1f, 0.55f, 0.15f), lightRange: 7f, lightIntensity: 2.5f);
            Prop("FireTotem", 0.6f, PropCollider.Box, withLight: true, lightHeight: 2.8f, lightColor: new Color(1f, 0.5f, 0.2f), lightRange: 10f, lightIntensity: 4f);
            Prop("AshMountainA", 0f, PropCollider.None);
            Prop("AshMountainB", 0f, PropCollider.None);
            Prop("VolcanoPeak", 0f, PropCollider.None);

            // ---------------------------------------------------------------- persistent services
            string gs = Prefabs + "/Systems/Resources/GameServices.prefab";
            if (NeedPrefab(gs))
            {
                var go = new GameObject("GameServices");
                go.AddComponent<GameLauncher>();
                go.AddComponent<AudioManager>();
                go.AddComponent<LocalInput>();
                go.AddComponent<AutoPilot>();
                SavePrefab(go, gs);
            }
            AssetDatabase.SaveAssets();
        }

        static void BuildEnemyPrefab(string path, GameObject model, float scale, bool blob)
        {
            if (!NeedPrefab(path)) return;
            var go = new GameObject(Path.GetFileNameWithoutExtension(path));
            go.layer = LayerMask.NameToLayer("Enemy");
            go.AddComponent<NetworkObject>();
            go.AddComponent<NetworkTransform>();
            go.AddComponent<Enemy>();
            var visual = new GameObject("Visual");
            visual.transform.SetParent(go.transform, false);
            visual.transform.localScale = Vector3.one * scale;
            var rig = visual.AddComponent<ProceduralRig>();
            rig.blob = blob;
            InstantiateModel(model, visual.transform);
            SavePrefab(go, path);
        }

        static void BuildPickup(string path, float scale, params (string name, GameObject model)[] models)
        {
            if (!NeedPrefab(path)) return;
            var go = new GameObject(Path.GetFileNameWithoutExtension(path));
            go.layer = LayerMask.NameToLayer("Pickup");
            go.AddComponent<NetworkObject>();
            go.AddComponent<NetworkTransform>();
            var p = go.AddComponent<Pickup>();
            var visual = new GameObject("Visual");
            visual.transform.SetParent(go.transform, false);
            foreach (var (name, model) in models)
            {
                var holder = new GameObject(name);
                holder.transform.SetParent(visual.transform, false);
                holder.transform.localScale = Vector3.one * scale;
                var m = InstantiateModel(model, holder.transform);
                foreach (var r in m.GetComponentsInChildren<Renderer>()) r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                if (models.Length > 1 && name != "Tier0") holder.SetActive(false);
            }
            p.visual = visual.transform;
            SavePrefab(go, path);
        }

        enum PropCollider { Box, Capsule, Mesh, None }

        static void Prop(string name, float obstacleRadius, PropCollider col, bool withLight = false, bool shadows = true, int obstacleLine = 0,
            float lineHalf = 2.2f, float lightHeight = 2.45f, Color? lightColor = null, float lightRange = 9f, float lightIntensity = 3f)
        {
            string path = $"{Prefabs}/Environment/{name}.prefab";
            if (!NeedPrefab(path)) return;
            var model = Model("Environment", name);
            if (model == null) { Debug.LogWarning("[MultiBash] missing model " + name); return; }
            var go = new GameObject(name) { layer = LayerMask.NameToLayer("Environment"), isStatic = true };
            var m = InstantiateModel(model, go.transform);
            foreach (var t in m.GetComponentsInChildren<Transform>()) { t.gameObject.layer = go.layer; t.gameObject.isStatic = true; }
            if (!shadows)
                foreach (var r in m.GetComponentsInChildren<Renderer>()) r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            // long props (walls): several obstacle circles along the local X axis
            for (int i = 0; i < obstacleLine; i++)
            {
                var o = new GameObject("Obstacle" + i);
                o.transform.SetParent(go.transform, false);
                o.transform.localPosition = new Vector3(-lineHalf + 2f * lineHalf * i / Mathf.Max(1, obstacleLine - 1), 0, 0);
                o.AddComponent<Obstacle>().radius = Mathf.Max(1.0f, lineHalf / Mathf.Max(1, obstacleLine - 1) + 0.3f);
            }
            var bounds = new Bounds(go.transform.position, Vector3.zero);
            foreach (var r in m.GetComponentsInChildren<Renderer>()) bounds.Encapsulate(r.bounds);
            switch (col)
            {
                case PropCollider.Box:
                    var b = go.AddComponent<BoxCollider>();
                    b.center = bounds.center;
                    b.size = bounds.size;
                    break;
                case PropCollider.Capsule:
                    var c = go.AddComponent<CapsuleCollider>();
                    c.center = new Vector3(0, bounds.size.y / 2f, 0);
                    c.height = bounds.size.y;
                    c.radius = Mathf.Max(0.25f, obstacleRadius * 0.8f);
                    break;
                case PropCollider.Mesh:
                    foreach (var mf in m.GetComponentsInChildren<MeshFilter>())
                    {
                        var mc = mf.gameObject.AddComponent<MeshCollider>();
                        mc.sharedMesh = mf.sharedMesh;
                    }
                    break;
            }
            if (obstacleRadius > 0f) go.AddComponent<Obstacle>().radius = obstacleRadius;
            if (withLight)
            {
                var l = new GameObject("Light").AddComponent<Light>();
                l.transform.SetParent(go.transform, false);
                l.transform.localPosition = new Vector3(0, lightHeight, 0);
                l.type = LightType.Point;
                l.color = lightColor ?? new Color(1f, 0.78f, 0.45f);
                l.range = lightRange;
                l.intensity = lightIntensity;
                l.shadows = LightShadows.None;
                go.AddComponent<FireFlicker>().lightSource = l;
            }
            SavePrefab(go, path);
        }
    }
}
