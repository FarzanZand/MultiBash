using System.Collections.Generic;
using Fusion;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace MultiBash.EditorTools
{
    /// <summary>Second level: "Molten Caldera". Basalt plains cut by lava rivers, mesas, a smoking volcano on the horizon.</summary>
    public static partial class MultiBashSetup
    {
        const float LavaLevel = 0.35f;

        static readonly Plateau[] VolcanoMesas =
        {
            new() { c = new Vector2(30, 6), r = 9f, h = 4.6f, rampAngle = 180f },
            new() { c = new Vector2(-14, -34), r = 10f, h = 3.8f, rampAngle = 90f },
            new() { c = new Vector2(-40, 40), r = 8f, h = 5.2f, rampAngle = 300f },
            new() { c = new Vector2(42, 42), r = 7f, h = 3.4f, rampAngle = 225f },
            new() { c = new Vector2(-44, -8), r = 6f, h = 3f, rampAngle = 0f },
        };

        static readonly Vector3[] VolcanoShrines =
        {
            new(14, 0, -12), new(-16, 0, 10), new(30, 0, 6), new(-12, 0, -40), new(10, 0, 44),
        };

        static float RiverA(float x) => 24f + Mathf.Sin(x * 0.055f) * 9f + Mathf.Sin(x * 0.13f + 1f) * 3f;   // z of river A at x
        static float RiverB(float z) => -28f + Mathf.Sin(z * 0.06f + 2f) * 8f + Mathf.Sin(z * 0.15f) * 2.5f;  // x of river B at z

        /// <summary>0..1 how much of a lava channel is at x,z (1 = channel floor).</summary>
        static float LavaMask(float x, float z, float half)
        {
            float m = 0f;
            // river A runs east-west, river B north-south (only in the south half so the map stays connected)
            float da = Mathf.Abs(z - RiverA(x));
            float ma = 1f - Mathf.SmoothStep(0f, 1f, (da - 2.4f) / 3.2f);
            foreach (float bx in new[] { -34f, 2f, 38f }) ma *= Mathf.SmoothStep(0f, 1f, (Mathf.Abs(x - bx) - 2.5f) / 2.5f);   // rock bridges
            m = Mathf.Max(m, ma);
            if (z < RiverA(-28f))
            {
                float db = Mathf.Abs(x - RiverB(z));
                float mb = 1f - Mathf.SmoothStep(0f, 1f, (db - 2.2f) / 3.2f);
                foreach (float bz in new[] { -8f, -40f }) mb *= Mathf.SmoothStep(0f, 1f, (Mathf.Abs(z - bz) - 2.5f) / 2.5f);
                m = Mathf.Max(m, mb);
            }
            // lava lakes
            foreach (var (c, r) in new[] { (new Vector2(36, -32), 8.5f), (new Vector2(-46, 22), 6f), (new Vector2(6, -52), 5.5f) })
            {
                float d = Vector2.Distance(new Vector2(x, z), c) - r + (Mathf.PerlinNoise(x * 0.2f, z * 0.2f) - 0.5f) * 3f;
                m = Mathf.Max(m, 1f - Mathf.SmoothStep(0f, 1f, (d + 1.5f) / 3.5f));
            }
            // keep the spawn and the shrines dry
            float center = new Vector2(x, z).magnitude;
            m *= Mathf.SmoothStep(0f, 1f, (center - 10f) / 4f);
            foreach (var s in VolcanoShrines)
                m *= Mathf.SmoothStep(0f, 1f, (Vector2.Distance(new Vector2(x, z), new Vector2(s.x, s.z)) - 4.5f) / 3f);
            // outside the arena the rivers fade into the mountains
            float outside = Mathf.Max(Mathf.Abs(x), Mathf.Abs(z)) - half;
            m *= 1f - Mathf.Clamp01(outside / 3f);
            return Mathf.Clamp01(m);
        }

        static float VolcanoHeight(float x, float z, float half)
        {
            float h = 1.6f + Fbm(x * 0.03f + 40f, z * 0.03f, 3) * 1.8f;
            float center = Mathf.Sqrt(x * x + z * z);
            h = Mathf.Lerp(1.8f, h, Mathf.SmoothStep(0f, 1f, center / 14f));   // flat spawn area

            foreach (var p in VolcanoMesas)
            {
                var d = new Vector2(x, z) - p.c;
                float dist = d.magnitude;
                float ang = Mathf.Atan2(d.y, d.x) * Mathf.Rad2Deg;
                float rampDelta = Mathf.Abs(Mathf.DeltaAngle(ang, p.rampAngle));
                float edge = rampDelta < 22f ? 11f : 1.2f;
                float t = 1f - Mathf.Clamp01((dist - p.r) / edge);
                h = Mathf.Max(h, p.h * t * t * (3 - 2 * t) + 1.4f * t + Fbm(x * 0.25f, z * 0.25f, 1) * 0.4f * t);
            }

            float lava = LavaMask(x, z, half);
            h = Mathf.Lerp(h, LavaLevel - 0.9f, lava);

            float outside = Mathf.Max(Mathf.Abs(x), Mathf.Abs(z)) - (half + 1f);
            if (outside > 0)
                h += Mathf.Min(outside * 2.2f, 12f) + outside * 0.15f + Fbm(x * 0.035f, z * 0.035f, 3) * Mathf.Min(outside, 30f) * 0.6f;
            return h;
        }

        static void VolcanoSplat(TerrainData data, float x, float z, float steep, float h, float[] w)
        {
            float cliff = Mathf.Clamp01((steep - 24f) / 8f);
            float nearLava = Mathf.Clamp01(1f - (h - LavaLevel) / 1.1f);   // scorched crust along the lava
            float cracks = Mathf.Clamp01((Mathf.PerlinNoise(x * 0.09f + 13, z * 0.09f + 7) - 0.7f) * 6f);
            float magma = Mathf.Max(nearLava, cracks * 0.8f) * (1 - cliff);
            float ash = Mathf.Clamp01((Mathf.PerlinNoise(x * 0.05f + 70, z * 0.05f + 20) - 0.5f) * 4f) * (1 - cliff) * (1 - magma);
            float pathR = Mathf.Abs(Mathf.Sqrt(x * x + z * z) - 6f);
            ash = Mathf.Max(ash, Mathf.Clamp01(1f - pathR / 2f) * 0.7f * (1 - cliff) * (1 - magma));
            w[0] = Mathf.Max(0f, 1f - cliff - ash - magma);
            w[1] = cliff;
            w[2] = ash;
            w[3] = magma;
        }

        static VolumeProfile BuildVolcanoProfile()
        {
            string path = "Assets/Settings/MB_PostProcessVolcano.asset";
            var p = Load<VolumeProfile>(path);
            if (p != null && !Force) return p;
            if (p != null) AssetDatabase.DeleteAsset(path);
            p = ScriptableObject.CreateInstance<VolumeProfile>();
            AssetDatabase.CreateAsset(p, path);
            var bloom = p.Add<Bloom>(true);
            bloom.threshold.Override(0.95f);
            bloom.intensity.Override(0.9f);
            bloom.scatter.Override(0.65f);
            bloom.tint.Override(new Color(1f, 0.75f, 0.6f));
            var vig = p.Add<Vignette>(true);
            vig.intensity.Override(0.3f);
            vig.smoothness.Override(0.45f);
            vig.color.Override(new Color(0.08f, 0.01f, 0.02f));
            var ca = p.Add<ColorAdjustments>(true);
            ca.contrast.Override(22f);
            ca.saturation.Override(8f);
            ca.postExposure.Override(0.1f);
            ca.colorFilter.Override(new Color(1.0f, 0.97f, 0.97f));
            var tm = p.Add<Tonemapping>(true);
            tm.mode.Override(TonemappingMode.Neutral);
            foreach (var c in p.components) { c.hideFlags = HideFlags.HideInInspector | HideFlags.HideInHierarchy; AssetDatabase.AddObjectToAsset(c, p); }
            EditorUtility.SetDirty(p);
            AssetDatabase.SaveAssets();
            return p;
        }

        static void BuildVolcanoScene(string path)
        {
            string terrainPath = Scenes + "/VolcanoTerrain.asset";
            if (AssetDatabase.LoadAssetAtPath<TerrainData>(terrainPath) != null) AssetDatabase.DeleteAsset(terrainPath);
            var scene = NewScene();
            var cfg = Load<GameConfig>(Content + "/GameConfig.asset");
            float half = cfg != null ? cfg.arenaHalfSize : 58f;

            // ---- atmosphere: smoky red dusk
            var fogColor = new Color(0.27f, 0.12f, 0.13f);
            RenderSettings.skybox = VolcanoSkyMat;
            RenderSettings.fog = true;
            RenderSettings.fogMode = FogMode.Linear;
            RenderSettings.fogColor = fogColor;
            RenderSettings.fogStartDistance = 20f;
            RenderSettings.fogEndDistance = 175f;
            RenderSettings.ambientMode = AmbientMode.Trilight;
            RenderSettings.ambientSkyColor = new Color(0.46f, 0.42f, 0.58f);     // cool smoky sky light vs. hot lava = contrast
            RenderSettings.ambientEquatorColor = new Color(0.44f, 0.34f, 0.36f);
            RenderSettings.ambientGroundColor = new Color(0.5f, 0.22f, 0.1f);    // lava bounce light from below
            Sun(new Vector3(40, -60, 0), new Color(1f, 0.74f, 0.55f), 1.35f);
            var vol = new GameObject("PostProcess").AddComponent<Volume>();
            vol.isGlobal = true;
            vol.sharedProfile = BuildVolcanoProfile();

            HeightBase = 4f;
            var terrain = BuildTerrain(half, out var data, (x, z) => VolcanoHeight(x, z, half), VolcanoLayers, VolcanoSplat, terrainPath);
            HeightBase = 0f;
            float H(Vector3 p) => terrain.SampleHeight(p) + terrain.transform.position.y;

            // ---- lava surface (one big plane, world-space UVs in the shader)
            var lava = GameObject.CreatePrimitive(PrimitiveType.Plane);
            lava.name = "Lava";
            Object.DestroyImmediate(lava.GetComponent<Collider>());
            lava.transform.position = new Vector3(0, LavaLevel, 0);
            lava.transform.localScale = new Vector3(32f, 1f, 32f);
            var lr = lava.GetComponent<MeshRenderer>();
            lr.sharedMaterial = LavaMat;
            lr.shadowCastingMode = ShadowCastingMode.Off;
            lr.receiveShadows = false;
            var zone = lava.AddComponent<LavaZone>();
            zone.level = LavaLevel;
            zone.damagePerSecond = 15f;

            // glow lights over the lava (no shadows, cheap)
            var glow = new GameObject("LavaGlow").transform;
            void LavaLight(Vector3 p, float range, float intensity)
            {
                var l = new GameObject("Glow").AddComponent<Light>();
                l.transform.SetParent(glow);
                l.transform.position = p + Vector3.up * 2.5f;
                l.type = LightType.Point;
                l.color = new Color(1f, 0.45f, 0.12f);
                l.range = range;
                l.intensity = intensity;
                l.shadows = LightShadows.None;
            }
            for (float x = -half + 6; x < half; x += 18f)
                if (LavaMask(x, RiverA(x), half) > 0.5f) LavaLight(new Vector3(x, LavaLevel, RiverA(x)), 14f, 3f);
            for (float z = -half + 6; z < RiverA(-28f); z += 18f)
                if (LavaMask(RiverB(z), z, half) > 0.5f) LavaLight(new Vector3(RiverB(z), LavaLevel, z), 14f, 3f);
            LavaLight(new Vector3(36, LavaLevel, -32), 18f, 4f);
            LavaLight(new Vector3(-46, LavaLevel, 22), 14f, 3f);
            LavaLight(new Vector3(6, LavaLevel, -52), 14f, 3f);

            // ---- invisible arena walls
            var walls = new GameObject("ArenaWalls").transform;
            int env = LayerMask.NameToLayer("Environment");
            for (int i = 0; i < 4; i++)
            {
                var w = new GameObject("Wall" + i) { layer = env };
                w.transform.SetParent(walls);
                var bc = w.AddComponent<BoxCollider>();
                bool xAxis = i < 2;
                float s = i % 2 == 0 ? 1 : -1;
                w.transform.position = xAxis ? new Vector3(s * (half + 0.5f), 20, 0) : new Vector3(0, 20, s * (half + 0.5f));
                bc.size = xAxis ? new Vector3(1, 60, half * 2 + 2) : new Vector3(half * 2 + 2, 60, 1);
            }

            // ---- props
            var deco = new GameObject("Props").transform;
            var rng = new System.Random(4321);
            float R() => (float)rng.NextDouble();
            var placed = new List<(Vector3 p, float r)>();
            bool Free(Vector3 p, float r, float minCenter = 10f)
            {
                if (new Vector2(p.x, p.z).magnitude < minCenter) return false;
                foreach (var o in placed) if ((new Vector2(o.p.x - p.x, o.p.z - p.z)).magnitude < o.r + r) return false;
                return true;
            }
            float Steep(Vector3 p) => data.GetSteepness((p.x + 160f) / 320f, (p.z + 160f) / 320f);
            bool Dry(Vector3 p, float margin = 0.6f) => H(p) > LavaLevel + margin;
            void Scatter(string prop, int count, float r, float minScale, float maxScale, float maxSteep, float extent, bool block = true, float sink = 0.05f, bool nearLava = false)
            {
                int made = 0, tries = 0;
                while (made < count && tries++ < count * 60)
                {
                    var p = new Vector3((R() * 2 - 1) * extent, 0, (R() * 2 - 1) * extent);
                    float s = Mathf.Lerp(minScale, maxScale, R());
                    if (block && !Free(p, r * s)) continue;
                    if (Steep(p) > maxSteep || !Dry(p)) continue;
                    if (nearLava && LavaMask(p.x + 4, p.z, half) + LavaMask(p.x - 4, p.z, half) + LavaMask(p.x, p.z + 4, half) + LavaMask(p.x, p.z - 4, half) < 0.3f) continue;
                    p.y = H(p) - sink;
                    if (block) placed.Add((p, r * s));
                    Place(prop, p, R() * 360f, s, deco);
                    made++;
                }
            }
            foreach (var p in VolcanoMesas) placed.Add((new Vector3(p.c.x, 0, p.c.y), p.r * 0.8f));
            foreach (var s in VolcanoShrines) placed.Add((s, 4.5f));

            // basalt column ring framing the arena (instead of the castle wall)
            float ringD = half + 3f;
            for (int side = 0; side < 4; side++)
            {
                for (float t = -ringD; t < ringD; t += 5.5f)
                {
                    var p = Quaternion.Euler(0, side * 90f, 0) * new Vector3(t + R() * 2f, 0, ringD + R() * 3f);
                    p.y = H(p) - 0.6f;
                    Place(R() < 0.5f ? "BasaltColumnsA" : "BasaltColumnsB", p, R() * 360f, 1.2f + R() * 0.8f, deco);
                }
            }

            // landmarks: obsidian spires and fire totems on the mesas
            foreach (var m in VolcanoMesas)
            {
                var p = new Vector3(m.c.x + R() * 3f - 1.5f, 0, m.c.y + R() * 3f - 1.5f);
                p.y = H(p) - 0.2f;
                Place(R() < 0.5f ? "ObsidianSpire" : "FireTotem", p, R() * 360f, 1f + R() * 0.4f, deco);
            }
            Scatter("FireTotem", 10, 1.5f, 0.9f, 1.1f, 12f, half - 6);
            Scatter("ObsidianSpire", 12, 1.8f, 0.8f, 1.4f, 18f, half - 4);
            Scatter("BasaltColumnsA", 10, 2.4f, 0.7f, 1.2f, 20f, half - 4);
            Scatter("BasaltColumnsB", 10, 2.4f, 0.7f, 1.2f, 20f, half - 4);
            Scatter("ObsidianSpire", 8, 1.8f, 0.6f, 0.9f, 18f, half - 4);
            Scatter("SulfurVent", 14, 1.5f, 0.8f, 1.3f, 14f, half - 4);
            Scatter("LavaRockA", 22, 1.8f, 0.8f, 1.4f, 30f, half - 3, nearLava: true);
            Scatter("LavaRockB", 10, 2.6f, 0.8f, 1.3f, 30f, half - 3);
            Scatter("LavaRockA", 10, 1.8f, 0.8f, 1.4f, 30f, half - 3);
            Scatter("CharredTreeA", 22, 1.5f, 0.9f, 1.4f, 18f, half - 3);
            Scatter("CharredTreeB", 22, 1.5f, 0.9f, 1.4f, 18f, half - 3);
            Scatter("SkullPile", 18, 1.0f, 0.8f, 1.3f, 20f, half - 4, false);
            Scatter("Brazier", 8, 1.5f, 1f, 1f, 10f, half - 6);
            // trees and spires on the slopes outside the arena
            for (int i = 0; i < 60; i++)
            {
                float a = R() * Mathf.PI * 2f, d = half + 7f + R() * 50f;
                var p = new Vector3(Mathf.Clamp(Mathf.Cos(a) * d, -150, 150), 0, Mathf.Clamp(Mathf.Sin(a) * d, -150, 150));
                p.y = H(p) - 0.3f;
                Place(i % 3 == 0 ? "ObsidianSpire" : (i % 2 == 0 ? "CharredTreeA" : "CharredTreeB"), p, R() * 360f, 1.3f + R() * 1.2f, deco);
            }
            // horizon: ash mountains all around, a big smoking volcano to the north
            for (int i = 0; i < 18; i++)
            {
                float a = i / 18f * 360f + R() * 12f;
                var p = Quaternion.Euler(0, a, 0) * Vector3.forward * (230f * (0.9f + R() * 0.35f));
                p.y = -4f;
                Place(i % 2 == 0 ? "AshMountainB" : "AshMountainA", p, R() * 360f, 0.9f + R() * 0.7f, deco);
            }
            var peak = Place("VolcanoPeak", new Vector3(30, -8, 205), 20f, 1.25f, deco);
            var peak2 = Place("VolcanoPeak", new Vector3(-190, -10, -80), 140f, 0.8f, deco);

            // Fusion needs the scene saved (so it has a GUID) before it can bake scene NetworkObjects
            EditorSceneManager.SaveScene(scene, path);

            var gmGo = new GameObject("GameManager");
            gmGo.AddComponent<NetworkObject>();
            gmGo.AddComponent<GameManager>().map = Load<MapDefinition>(Content + "/Maps/Volcano.asset");

            int si = 0;
            foreach (var s in VolcanoShrines)
            {
                var go = new GameObject("Shrine" + si++);
                var p = s;
                p.y = H(p) - 0.15f;
                go.transform.position = p;
                go.AddComponent<NetworkObject>();
                var shrine = go.AddComponent<Shrine>();
                var baseM = InstantiateModel(Model("Environment", "ShrineBase"), go.transform);
                baseM.name = "Base";
                var crystalHolder = new GameObject("Crystal").transform;
                crystalHolder.SetParent(go.transform, false);
                InstantiateModel(Model("Environment", "ShrineCrystal"), crystalHolder);
                shrine.crystal = crystalHolder;
                var l = new GameObject("Light").AddComponent<Light>();
                l.transform.SetParent(go.transform, false);
                l.transform.localPosition = new Vector3(0, 2.6f, 0);
                l.type = LightType.Point;
                l.color = new Color(0.4f, 0.8f, 1f);
                l.range = 9f;
                l.intensity = 2f;
                l.shadows = LightShadows.None;
            }

            var fx = MakeFx();
            fx.ambientColorA = new Color(1f, 0.55f, 0.15f, 0.95f);
            fx.ambientColorB = new Color(1f, 0.3f, 0.08f, 0.85f);
            fx.ambientRate = 45f;
            fx.ambientRise = 0.25f;

            var rigGo = new GameObject("CameraRig");
            var rig = rigGo.AddComponent<CameraRig>();
            rig.cam = MakeCamera("Camera", rigGo.transform);
            rig.cam.backgroundColor = fogColor;
            rigGo.transform.position = new Vector3(0, 10, -10);

            new GameObject("HUD").AddComponent<HUD>();

            OrganizeScene(scene);
            EditorSceneManager.SaveScene(scene, path);
        }
    }
}
