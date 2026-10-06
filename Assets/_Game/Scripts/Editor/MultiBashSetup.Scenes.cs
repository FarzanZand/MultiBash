using System.Collections.Generic;
using Fusion;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using UnityEngine.SceneManagement;

namespace MultiBash.EditorTools
{
    public static partial class MultiBashSetup
    {
        static VolumeProfile _profile;

        static void BuildScenes()
        {
            _profile = BuildVolumeProfile();
            string menu = Scenes + "/MainMenu.unity", lobby = Scenes + "/Lobby.unity", game = Scenes + "/Game.unity";
            if (Force || !System.IO.File.Exists(menu)) BuildMenuScene(menu);
            if (Force || !System.IO.File.Exists(lobby)) BuildLobbyScene(lobby);
            if (Force || !System.IO.File.Exists(game)) BuildGameScene(game);
            string volcano = Scenes + "/Volcano.unity";
            if (Force || !System.IO.File.Exists(volcano)) BuildVolcanoScene(volcano);
            string frost = Scenes + "/Frost.unity";
            if (Force || !System.IO.File.Exists(frost)) BuildFrostScene(frost);
            EditorBuildSettings.scenes = new[]
            {
                new EditorBuildSettingsScene(menu, true),
                new EditorBuildSettingsScene(lobby, true),
                new EditorBuildSettingsScene(game, true),
                new EditorBuildSettingsScene(volcano, true),
                new EditorBuildSettingsScene(frost, true),
            };
        }

        static VolumeProfile BuildVolumeProfile()
        {
            string path = "Assets/Settings/MB_PostProcess.asset";
            var p = Load<VolumeProfile>(path);
            if (p != null && !Force) return p;
            if (p != null) AssetDatabase.DeleteAsset(path);
            p = ScriptableObject.CreateInstance<VolumeProfile>();
            AssetDatabase.CreateAsset(p, path);
            var bloom = p.Add<Bloom>(true);
            bloom.threshold.Override(1.0f);
            bloom.intensity.Override(0.6f);
            bloom.scatter.Override(0.6f);
            var vig = p.Add<Vignette>(true);
            vig.intensity.Override(0.22f);
            vig.smoothness.Override(0.4f);
            var ca = p.Add<ColorAdjustments>(true);
            ca.contrast.Override(20f);
            ca.saturation.Override(4f);
            ca.postExposure.Override(0.05f);
            ca.colorFilter.Override(new Color(0.93f, 0.97f, 1.05f));
            var tm = p.Add<Tonemapping>(true);
            tm.mode.Override(TonemappingMode.Neutral);
            foreach (var c in p.components) { c.hideFlags = HideFlags.HideInInspector | HideFlags.HideInHierarchy; AssetDatabase.AddObjectToAsset(c, p); }
            EditorUtility.SetDirty(p);
            AssetDatabase.SaveAssets();
            return p;
        }

        // ---------------------------------------------------------------- shared helpers

        static Scene NewScene() => EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

        static readonly Color SkyFog = new(0.36f, 0.6f, 0.72f);

        /// <summary>Megabonk-like blue dusk: pixel sky, teal distance fog, bright cool ambient.</summary>
        static void Atmosphere(float fogStart, float fogEnd)
        {
            RenderSettings.skybox = SkyMat;
            RenderSettings.fog = true;
            RenderSettings.fogMode = FogMode.Linear;
            RenderSettings.fogColor = SkyFog;
            RenderSettings.fogStartDistance = fogStart;
            RenderSettings.fogEndDistance = fogEnd;
            RenderSettings.ambientMode = AmbientMode.Trilight;
            RenderSettings.ambientSkyColor = new Color(0.52f, 0.68f, 0.88f);
            RenderSettings.ambientEquatorColor = new Color(0.5f, 0.6f, 0.62f);
            RenderSettings.ambientGroundColor = new Color(0.3f, 0.34f, 0.28f);
        }

        static Light Sun(Vector3 euler, Color color, float intensity)
        {
            var go = new GameObject("Sun");
            var l = go.AddComponent<Light>();
            l.type = LightType.Directional;
            l.color = color;
            l.intensity = intensity;
            l.shadows = LightShadows.Soft;
            l.shadowStrength = 0.65f;
            go.transform.rotation = Quaternion.Euler(euler);
            RenderSettings.sun = l;
            return l;
        }

        static Camera MakeCamera(string name, Transform parent = null)
        {
            var go = new GameObject(name) { tag = "MainCamera" };
            if (parent != null) go.transform.SetParent(parent, false);
            var cam = go.AddComponent<Camera>();
            cam.clearFlags = CameraClearFlags.Skybox;
            cam.backgroundColor = SkyFog;
            cam.fieldOfView = 60f;
            cam.nearClipPlane = 0.2f;
            cam.farClipPlane = 450f;
            go.AddComponent<AudioListener>();
            var data = go.AddComponent<UniversalAdditionalCameraData>();
            data.renderPostProcessing = true;
            data.antialiasing = AntialiasingMode.None; // crisp pixels
            return cam;
        }

        static void PostVolume()
        {
            var go = new GameObject("PostProcess");
            var v = go.AddComponent<Volume>();
            v.isGlobal = true;
            v.sharedProfile = _profile;
        }

        static GameObject GrassPlane(float size)
        {
            var g = GameObject.CreatePrimitive(PrimitiveType.Plane);
            g.name = "Ground";
            g.transform.localScale = new Vector3(size / 10f, 1, size / 10f);
            var m = new Material(GrassMat);
            g.GetComponent<Renderer>().sharedMaterial = GrassMat;
            g.layer = LayerMask.NameToLayer("Environment");
            g.isStatic = true;
            return g;
        }

        static GameObject Place(string prop, Vector3 pos, float yRot, float scale = 1f, Transform parent = null)
        {
            var prefab = Load<GameObject>($"{Prefabs}/Environment/{prop}.prefab");
            if (prefab == null) return null;
            var go = (GameObject)PrefabUtility.InstantiatePrefab(prefab);
            if (parent != null) go.transform.SetParent(parent, false);
            go.transform.position = pos;
            go.transform.rotation = Quaternion.Euler(0, yRot, 0);
            go.transform.localScale = Vector3.one * scale;
            return go;
        }

        /// <summary>Places a model inside a rotated holder; returns the model (put a ProceduralRig on it safely).</summary>
        static GameObject PlaceModel(GameObject model, Vector3 pos, float yRot, float scale = 1f)
        {
            var holder = new GameObject(model.name).transform;
            holder.position = pos;
            holder.rotation = Quaternion.Euler(0, yRot, 0);
            holder.localScale = Vector3.one * scale;
            var go = InstantiateModel(model, holder);
            go.transform.localPosition = Vector3.zero;
            go.transform.localRotation = Quaternion.identity;
            return go;
        }

        static FxManager MakeFx()
        {
            var go = new GameObject("FxManager");
            var fx = go.AddComponent<FxManager>();
            fx.additive = FxAdd;
            fx.alpha = FxAlpha;
            fx.softTexture = Load<Texture2D>(Vfx + "/T_SoftParticle.png");
            fx.sparkTexture = Load<Texture2D>(Vfx + "/T_Spark.png");
            fx.ringTexture = Load<Texture2D>(Vfx + "/T_Ring.png");
            fx.slashTexture = Load<Texture2D>(Vfx + "/T_Slash.png");
            fx.puddleTexture = Load<Texture2D>(Vfx + "/T_Puddle.png");
            fx.lightningTexture = Load<Texture2D>(Vfx + "/T_Lightning.png");
            fx.font = Load<Font>(UIDir + "/Fonts/Silkscreen-Bold.ttf");
            fx.flaskShatter = Clip("SFX_FlaskShatter");
            return fx;
        }

        static void Backdrop(Transform parent, float radius, int count, int seed)
        {
            var rng = new System.Random(seed);
            for (int i = 0; i < count; i++)
            {
                float a = i / (float)count * 360f + (float)rng.NextDouble() * 12f;
                float r = radius * (0.9f + (float)rng.NextDouble() * 0.35f);
                var p = Quaternion.Euler(0, a, 0) * Vector3.forward * r;
                p.y = -4f;
                Place(i % 2 == 0 ? "MountainB" : "MountainA", p, (float)rng.NextDouble() * 360f, 0.9f + (float)rng.NextDouble() * 0.7f, parent);
            }
        }

        // ---------------------------------------------------------------- Main menu

        static void BuildMenuScene(string path)
        {
            var scene = NewScene();
            Atmosphere(25f, 220f);
            Sun(new Vector3(35, -40, 0), new Color(1f, 0.95f, 0.85f), 1.35f);
            GrassPlane(300);
            PostVolume();
            var deco = new GameObject("Props").transform;

            var pivot = new GameObject("Pivot").transform;
            pivot.position = new Vector3(0.4f, 0, 0);
            var cam = MakeCamera("MenuCamera");
            var bd = cam.gameObject.AddComponent<MenuBackdrop>();
            bd.pivot = pivot;
            bd.distance = 7f;
            bd.height = 1.9f;
            bd.sway = 12f;
            cam.transform.position = new Vector3(2.2f, 2.2f, -8);

            string[] heroes = { "Knight", "Ranger", "Mage", "Alchemist" };
            for (int i = 0; i < heroes.Length; i++)
            {
                var h = PlaceModel(Model("Characters", heroes[i]), new Vector3(i * 1.4f, 0, 0), 180f + (i - 1.5f) * -8f, 1.05f);
                h.AddComponent<ProceduralRig>();
            }
            var rng = new System.Random(3);
            for (int i = 0; i < 16; i++)
            {
                float x = -8f + (float)rng.NextDouble() * 20f, z = 6f + (float)rng.NextDouble() * 10f;
                var model = i % 3 == 0 ? Model("Enemies", "Slime") : Model("Enemies", "Skeleton");
                var e = PlaceModel(model, new Vector3(x, 0, z), 180f + (float)rng.NextDouble() * 40f - 20f, i % 3 == 0 ? 1.1f : 1f);
                e.AddComponent<ProceduralRig>();
            }
            Place("TowerRuin", new Vector3(-12, 0, 18), 20, 1.2f, deco);
            Place("TowerRuin", new Vector3(22, 0, 26), 70, 1f, deco);
            Place("WallRuin", new Vector3(6, 0, 20), 5, 1f, deco);
            Place("TreeA", new Vector3(-7, 0, 9), 30, 1.1f, deco);
            Place("TreeB", new Vector3(12, 0, 11), 120, 1f, deco);
            Place("TreePine", new Vector3(-16, 0, 30), 0, 1.3f, deco);
            Place("TreePine", new Vector3(30, 0, 40), 0, 1.5f, deco);
            Place("Bush", new Vector3(-3.5f, 0, 2.5f), 10, 1f, deco);
            Place("Log", new Vector3(8, 0, 3), 60, 1f, deco);
            Place("RockB", new Vector3(15, 0, 6), 40, 1f, deco);
            Place("LanternPost", new Vector3(-2.5f, 0, -1.5f), 0, 1f, deco);
            for (int i = 0; i < 60; i++)
                Place("GrassTuft", new Vector3(-20 + (float)rng.NextDouble() * 45, 0, -6 + (float)rng.NextDouble() * 30), (float)rng.NextDouble() * 360, 0.8f + (float)rng.NextDouble() * 0.6f, deco);
            Backdrop(deco, 170f, 14, 5);

            new GameObject("MainMenuUI").AddComponent<MainMenuUI>();
            MakeFx();
            OrganizeScene(scene);
            EditorSceneManager.SaveScene(scene, path);
        }

        // ---------------------------------------------------------------- Lobby

        static void BuildLobbyScene(string path)
        {
            var scene = NewScene();
            Atmosphere(25f, 220f);
            Sun(new Vector3(35, -25, 0), new Color(1f, 0.95f, 0.85f), 1.35f);
            GrassPlane(300);
            PostVolume();
            var deco = new GameObject("Props").transform;

            var cam = MakeCamera("LobbyCamera");
            cam.transform.position = new Vector3(1.6f, 2.4f, -6.5f);
            cam.transform.rotation = Quaternion.Euler(6, 0, 0);

            var pedestals = new List<Transform>();
            for (int i = 0; i < 4; i++)
            {
                float x = (i - 1.5f) * 1.9f + 2.6f;
                var ped = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
                ped.name = "Pedestal" + i;
                ped.transform.position = new Vector3(x, 0.12f, 2.6f);
                ped.transform.localScale = new Vector3(1.3f, 0.12f, 1.3f);
                ped.GetComponent<Renderer>().sharedMaterial = StoneMat;
                Object.DestroyImmediate(ped.GetComponent<Collider>());
                var spot = new GameObject("Spot" + i).transform;
                spot.position = new Vector3(x, 0.24f, 2.6f);
                spot.rotation = Quaternion.Euler(0, 180, 0);
                pedestals.Add(spot);
            }
            Place("TowerRuin", new Vector3(-9, 0, 16), 30, 1.1f, deco);
            Place("WallRuin", new Vector3(9, 0, 13), -10, 1f, deco);
            Place("TreeA", new Vector3(-4, 0, 9), 40, 1f, deco);
            Place("TreeB", new Vector3(14, 0, 9), 140, 1.1f, deco);
            Place("TreePine", new Vector3(20, 0, 24), 0, 1.4f, deco);
            Place("LanternPost", new Vector3(-1.2f, 0, 3.4f), 0, 1f, deco);
            Place("LanternPost", new Vector3(6.6f, 0, 3.4f), 0, 1f, deco);
            Place("Bush", new Vector3(8, 0, 5), 0, 1f, deco);
            var rng = new System.Random(8);
            for (int i = 0; i < 50; i++)
                Place("GrassTuft", new Vector3(-12 + (float)rng.NextDouble() * 30, 0, -2 + (float)rng.NextDouble() * 20), (float)rng.NextDouble() * 360, 0.8f + (float)rng.NextDouble() * 0.6f, deco);
            Backdrop(deco, 160f, 14, 9);

            var ui = new GameObject("LobbyUI").AddComponent<LobbyUI>();
            ui.pedestals = pedestals.ToArray();
            MakeFx();
            OrganizeScene(scene);
            EditorSceneManager.SaveScene(scene, path);
        }

        // ---------------------------------------------------------------- Game arena (terrain with plateaus, cliffs, ramps)

        struct Plateau
        {
            public Vector2 c;
            public float r, h, rampAngle;
        }

        static readonly Plateau[] Plateaus =
        {
            new() { c = new Vector2(26, -24), r = 10f, h = 3.2f, rampAngle = 200f },
            new() { c = new Vector2(-30, 20), r = 12f, h = 4.0f, rampAngle = 20f },
            new() { c = new Vector2(34, 30), r = 8f, h = 2.6f, rampAngle = 250f },
            new() { c = new Vector2(-24, -34), r = 9f, h = 3.0f, rampAngle = 60f },
            new() { c = new Vector2(2, 40), r = 7f, h = 4.8f, rampAngle = 270f },
            new() { c = new Vector2(-44, -6), r = 6f, h = 2.2f, rampAngle = 0f },
        };

        static float Fbm(float x, float z, int oct)
        {
            float s = 0, a = 0.5f, f = 1f;
            for (int i = 0; i < oct; i++) { s += Mathf.PerlinNoise(x * f + 31.7f, z * f + 11.3f) * a; f *= 2.03f; a *= 0.5f; }
            return s;
        }

        /// <summary>World height (meters) of the arena at x,z.</summary>
        static float ArenaHeight(float x, float z, float half)
        {
            float h = Fbm(x * 0.025f, z * 0.025f, 3) * 2.2f;                       // gentle rolling ground
            float center = Mathf.Sqrt(x * x + z * z);
            h *= Mathf.SmoothStep(0.3f, 1f, center / 14f);                         // flat spawn area

            foreach (var p in Plateaus)
            {
                var d = new Vector2(x, z) - p.c;
                float dist = d.magnitude;
                float ang = Mathf.Atan2(d.y, d.x) * Mathf.Rad2Deg;
                float rampDelta = Mathf.Abs(Mathf.DeltaAngle(ang, p.rampAngle));
                float edge = rampDelta < 22f ? 11f : 1.4f;                         // ramp sector = gentle slope
                float t = 1f - Mathf.Clamp01((dist - p.r) / edge);
                h = Mathf.Max(h, p.h * t * t * (3 - 2 * t) + Fbm(x * 0.2f, z * 0.2f, 1) * 0.3f * t);
            }

            // hills rising outside the arena (natural walls + horizon)
            float outside = Mathf.Max(Mathf.Abs(x), Mathf.Abs(z)) - (half + 1f);
            if (outside > 0)
                h += Mathf.Min(outside * 1.6f, 9f) + outside * 0.12f + Fbm(x * 0.03f, z * 0.03f, 3) * Mathf.Min(outside, 30f) * 0.5f;
            return h;
        }

        /// <summary>Terrain heights can't go below 0, so the terrain is lowered by this much (lets lava channels dip below ground level 0).</summary>
        static float HeightBase;

        static Terrain BuildTerrain(float half, out TerrainData data) =>
            BuildTerrain(half, out data, (x, z) => ArenaHeight(x, z, half), TerrainLayers, GraveyardSplat, Scenes + "/GameTerrain.asset");

        static void GraveyardSplat(TerrainData data, float x, float z, float steep, float h, float[] w)
        {
            float cliff = Mathf.Clamp01((steep - 21f) / 8f);
            float dirt = Mathf.Clamp01((Mathf.PerlinNoise(x * 0.06f + 5, z * 0.06f + 9) - 0.62f) * 6f) * (1 - cliff);
            float pathR = Mathf.Abs(Mathf.Sqrt(x * x + z * z) - 6f);
            dirt = Mathf.Max(dirt, Mathf.Clamp01(1f - pathR / 2.2f) * 0.8f * (1 - cliff));
            float moss = Mathf.Clamp01((Mathf.PerlinNoise(x * 0.04f + 50, z * 0.04f) - 0.6f) * 5f) * (1 - cliff) * (1 - dirt);
            w[0] = Mathf.Max(0f, 1f - cliff - dirt - moss);
            w[1] = cliff;
            w[2] = dirt;
            w[3] = moss;
        }

        static Terrain BuildTerrain(float half, out TerrainData data, System.Func<float, float, float> heightFn, TerrainLayer[] layers,
            System.Action<TerrainData, float, float, float, float, float[]> splat, string assetPath)
        {
            const float size = 320f, maxH = 45f;
            const int res = 257;
            data = new TerrainData { heightmapResolution = res, alphamapResolution = 256, baseMapResolution = 256 };
            data.size = new Vector3(size, maxH, size);
            // save the asset first: alphamaps written before CreateAsset are lost (splat textures become sub-assets)
            AssetDatabase.CreateAsset(data, assetPath);
            var heights = new float[res, res];
            for (int iz = 0; iz < res; iz++)
            for (int ix = 0; ix < res; ix++)
            {
                float x = ix / (float)(res - 1) * size - size / 2f;
                float z = iz / (float)(res - 1) * size - size / 2f;
                heights[iz, ix] = Mathf.Clamp01((heightFn(x, z) + HeightBase) / maxH);
            }
            data.SetHeights(0, 0, heights);
            data.terrainLayers = layers;

            int ar = data.alphamapResolution;
            int nl = layers.Length;
            var maps = new float[ar, ar, nl];
            var w = new float[nl];
            for (int iz = 0; iz < ar; iz++)
            for (int ix = 0; ix < ar; ix++)
            {
                float nx = ix / (float)(ar - 1), nz = iz / (float)(ar - 1);
                float steep = data.GetSteepness(nx, nz);
                float x = nx * size - size / 2f, z = nz * size - size / 2f;
                splat(data, x, z, steep, data.GetInterpolatedHeight(nx, nz) - HeightBase, w);
                for (int k = 0; k < nl; k++) maps[iz, ix, k] = w[k];
            }
            data.SetAlphamaps(0, 0, maps);
            EditorUtility.SetDirty(data);
            AssetDatabase.SaveAssets();

            var go = Terrain.CreateTerrainGameObject(data);
            go.name = "Terrain";
            go.layer = LayerMask.NameToLayer("Environment");
            go.isStatic = true;
            go.transform.position = new Vector3(-size / 2f, -HeightBase, -size / 2f);
            var t = go.GetComponent<Terrain>();
            t.materialTemplate = TerrainMat;
            t.basemapDistance = 400f;
            t.heightmapPixelError = 4f;
            t.drawInstanced = true;
            return t;
        }
    }
}
