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
    /// <summary>
    /// Arena building blocks shared by the three maps: prop scattering with spacing, roads, smashable props,
    /// bounce pads, shrines, walls, and the network/camera/HUD objects every game scene needs.
    /// </summary>
    public static partial class MultiBashSetup
    {
        /// <summary>Places and scatters props on a terrain while keeping them apart (and off roads / the spawn).</summary>
        class Dresser
        {
            public Transform deco;
            public System.Random rng;
            public readonly List<(Vector3 p, float r)> placed = new();
            public System.Func<Vector3, float> H;
            public TerrainData data;
            public System.Func<Vector3, bool> Ok = _ => true;
            public float half;
            public List<(Vector2 a, Vector2 b)> roads = new();

            public float R() => (float)rng.NextDouble();
            public float Steep(Vector3 p) => data.GetSteepness((p.x + 160f) / 320f, (p.z + 160f) / 320f);

            public float RoadDist(Vector3 p)
            {
                float best = 999f;
                var q = new Vector2(p.x, p.z);
                foreach (var (a, b) in roads)
                {
                    var ab = b - a;
                    float t = Mathf.Clamp01(Vector2.Dot(q - a, ab) / Mathf.Max(0.001f, ab.sqrMagnitude));
                    best = Mathf.Min(best, Vector2.Distance(q, a + ab * t));
                }
                return best;
            }

            public bool Free(Vector3 p, float r, float minCenter = 10f)
            {
                if (new Vector2(p.x, p.z).magnitude < minCenter) return false;
                foreach (var o in placed) if (new Vector2(o.p.x - p.x, o.p.z - p.z).magnitude < o.r + r) return false;
                return true;
            }

            public void Block(Vector3 p, float r) => placed.Add((p, r));

            public GameObject At(string prop, Vector3 p, float yaw, float scale = 1f, float sink = 0.05f, float block = 0f)
            {
                p.y = H(p) - sink;
                if (block > 0f) placed.Add((p, block * scale));
                return Place(prop, p, yaw, scale, deco);
            }

            /// <summary>Random props over the square arena (or a circle when center/radius are given).</summary>
            public int Scatter(string prop, int count, float r, float minS, float maxS, float maxSteep, float extent, bool block = true,
                float sink = 0.05f, System.Func<Vector3, bool> where = null, Vector2? center = null, float roadClear = 2.4f)
            {
                int made = 0, tries = 0;
                while (made < count && tries++ < count * 60)
                {
                    Vector3 p;
                    if (center.HasValue)
                    {
                        var c = Random2() * extent;
                        p = new Vector3(center.Value.x + c.x, 0, center.Value.y + c.y);
                    }
                    else p = new Vector3((R() * 2 - 1) * extent, 0, (R() * 2 - 1) * extent);
                    float s = Mathf.Lerp(minS, maxS, R());
                    if (block && !Free(p, r * s)) continue;
                    if (!block && new Vector2(p.x, p.z).magnitude < 6f) continue;
                    if (Steep(p) > maxSteep || !Ok(p)) continue;
                    if (where != null && !where(p)) continue;
                    if (roadClear > 0f && r > 0.3f && RoadDist(p) < roadClear + r * s * 0.5f) continue;
                    p.y = H(p) - sink;
                    if (block) placed.Add((p, r * s));
                    Place(prop, p, R() * 360f, s, deco);
                    made++;
                }
                return made;
            }

            Vector2 Random2()
            {
                float a = R() * Mathf.PI * 2f, d = Mathf.Sqrt(R());
                return new Vector2(Mathf.Cos(a), Mathf.Sin(a)) * d;
            }

            /// <summary>Trees / spires on the slopes outside the arena (frame the view).</summary>
            public void Outskirts(string[] props, int count, float minS, float maxS, float inner = 6f, float depth = 50f)
            {
                for (int i = 0; i < count; i++)
                {
                    float a = R() * Mathf.PI * 2f, d = half + inner + R() * depth;
                    var p = new Vector3(Mathf.Clamp(Mathf.Cos(a) * d, -150, 150), 0, Mathf.Clamp(Mathf.Sin(a) * d, -150, 150));
                    p.y = H(p) - 0.3f;
                    Place(props[i % props.Length], p, R() * 360f, Mathf.Lerp(minS, maxS, R()), deco);
                }
            }
        }

        static float SegDist(Vector2 q, Vector2 a, Vector2 b)
        {
            var ab = b - a;
            float t = Mathf.Clamp01(Vector2.Dot(q - a, ab) / Mathf.Max(0.001f, ab.sqrMagnitude));
            return Vector2.Distance(q, a + ab * t);
        }

        static float RoadMask(float x, float z, (Vector2 a, Vector2 b)[] roads, float width)
        {
            float best = 999f;
            var q = new Vector2(x, z);
            foreach (var (a, b) in roads) best = Mathf.Min(best, SegDist(q, a, b));
            best += (Mathf.PerlinNoise(x * 0.3f, z * 0.3f) - 0.5f) * 0.9f;   // ragged edges
            return 1f - Mathf.SmoothStep(0f, 1f, (best - width) / 1.2f);
        }

        static float PlateauHeight(float x, float z, Plateau p, float lip = 1.3f, float ramp = 11f)
        {
            var d = new Vector2(x, z) - p.c;
            float dist = d.magnitude;
            float ang = Mathf.Atan2(d.y, d.x) * Mathf.Rad2Deg;
            float edge = Mathf.Abs(Mathf.DeltaAngle(ang, p.rampAngle)) < 22f ? ramp : lip;
            float t = 1f - Mathf.Clamp01((dist - p.r) / edge);
            return p.h * t * t * (3 - 2 * t) + Fbm(x * 0.2f, z * 0.2f, 1) * 0.3f * t;
        }

        static void ArenaWalls(float half)
        {
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
        }

        static void MakeShrines(Vector3[] spots, System.Func<Vector3, float> H, Color? color = null)
        {
            int si = 0;
            foreach (var s in spots)
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
                l.color = color ?? new Color(0.4f, 0.8f, 1f);
                l.range = 9f;
                l.intensity = 2f;
                l.shadows = LightShadows.None;
            }
        }

        /// <summary>One scene NetworkObject holding every smashable prop (children in order).</summary>
        static void MakeBreakables(Dresser d, (string model, Color debris, float scale)[] kinds, int count, Vector2[] hotspots, float hotspotShare = 0.6f)
        {
            var root = new GameObject("Breakables");
            root.AddComponent<NetworkObject>();
            var b = root.AddComponent<Breakables>();
            b.breakSound = Clip("SFX_Smash");
            int made = 0, tries = 0;
            while (made < Mathf.Min(count, Breakables.Max) && tries++ < count * 80)
            {
                Vector3 p;
                if (hotspots != null && hotspots.Length > 0 && d.R() < hotspotShare)
                {
                    var c = hotspots[d.rng.Next(hotspots.Length)];
                    float a = d.R() * Mathf.PI * 2f, r = 2.5f + d.R() * 5f;
                    p = new Vector3(c.x + Mathf.Cos(a) * r, 0, c.y + Mathf.Sin(a) * r);
                }
                else p = new Vector3((d.R() * 2 - 1) * (d.half - 4), 0, (d.R() * 2 - 1) * (d.half - 4));
                if (!d.Free(p, 0.8f, 13f) || d.Steep(p) > 22f || !d.Ok(p)) continue;
                var k = kinds[d.rng.Next(kinds.Length)];
                p.y = d.H(p) - 0.03f;
                var m = InstantiateModel(Model("Environment", k.model), root.transform);
                m.name = k.model + made;
                m.transform.position = p;
                m.transform.rotation = Quaternion.Euler(0, d.R() * 360f, 0);
                m.transform.localScale = Vector3.one * k.scale * (0.9f + d.R() * 0.25f);
                b.colors.Add(k.debris);
                d.Block(p, 0.9f);
                made++;
            }
        }

        static Transform _padRoot;

        static void MakePad(Dresser d, string model, Vector3 p, float launch, Color color, float radius = 1.4f, float scale = 1f)
        {
            if (_padRoot == null) _padRoot = new GameObject("JumpPads").transform;
            p.y = d.H(p) - 0.05f;
            var go = new GameObject("JumpPad_" + model);
            go.transform.SetParent(_padRoot);
            go.transform.position = p;
            go.transform.rotation = Quaternion.Euler(0, d.R() * 360f, 0);
            var m = InstantiateModel(Model("Environment", model), go.transform);
            m.transform.localScale = Vector3.one * scale;
            var pad = go.AddComponent<JumpPad>();
            pad.launch = launch;
            pad.color = color;
            pad.radius = radius * scale;
            pad.sound = Clip("SFX_Bounce");
            pad.squash = m.transform;
            var l = new GameObject("Glow").AddComponent<Light>();
            l.transform.SetParent(go.transform, false);
            l.transform.localPosition = Vector3.up * 1.2f;
            l.type = LightType.Point;
            l.color = color;
            l.range = 6f;
            l.intensity = 1.6f;
            l.shadows = LightShadows.None;
            d.Block(p, radius * scale + 1.5f);
        }

        static Light PointLight(Transform parent, Vector3 pos, Color c, float range, float intensity, string name = "Light")
        {
            var l = new GameObject(name).AddComponent<Light>();
            if (parent != null) l.transform.SetParent(parent);
            l.transform.position = pos;
            l.type = LightType.Point;
            l.color = c;
            l.range = range;
            l.intensity = intensity;
            l.shadows = LightShadows.None;
            return l;
        }

        static VolumeProfile MapProfile(string path, float bloomThreshold, float bloomIntensity, Color bloomTint, float vignette, Color vigColor,
            float contrast, float saturation, float exposure, Color filter)
        {
            var p = Load<VolumeProfile>(path);
            if (p != null && !Force) return p;
            if (p != null) AssetDatabase.DeleteAsset(path);
            p = ScriptableObject.CreateInstance<VolumeProfile>();
            AssetDatabase.CreateAsset(p, path);
            var bloom = p.Add<Bloom>(true);
            bloom.threshold.Override(bloomThreshold);
            bloom.intensity.Override(bloomIntensity);
            bloom.scatter.Override(0.62f);
            bloom.tint.Override(bloomTint);
            var vig = p.Add<Vignette>(true);
            vig.intensity.Override(vignette);
            vig.smoothness.Override(0.42f);
            vig.color.Override(vigColor);
            var ca = p.Add<ColorAdjustments>(true);
            ca.contrast.Override(contrast);
            ca.saturation.Override(saturation);
            ca.postExposure.Override(exposure);
            ca.colorFilter.Override(filter);
            var tm = p.Add<Tonemapping>(true);
            tm.mode.Override(TonemappingMode.Neutral);
            foreach (var c in p.components) { c.hideFlags = HideFlags.HideInInspector | HideFlags.HideInHierarchy; AssetDatabase.AddObjectToAsset(c, p); }
            EditorUtility.SetDirty(p);
            AssetDatabase.SaveAssets();
            return p;
        }

        static void Lighting(Material sky, Color fog, float fogStart, float fogEnd, Color ambSky, Color ambEq, Color ambGround)
        {
            RenderSettings.skybox = sky;
            RenderSettings.fog = true;
            RenderSettings.fogMode = FogMode.Linear;
            RenderSettings.fogColor = fog;
            RenderSettings.fogStartDistance = fogStart;
            RenderSettings.fogEndDistance = fogEnd;
            RenderSettings.ambientMode = AmbientMode.Trilight;
            RenderSettings.ambientSkyColor = ambSky;
            RenderSettings.ambientEquatorColor = ambEq;
            RenderSettings.ambientGroundColor = ambGround;
        }

        /// <summary>GameManager, FX, camera rig and HUD (call after the scene has been saved once).</summary>
        static FxManager ArenaSystems(string mapAsset, Color camBackground)
        {
            var gmGo = new GameObject("GameManager");
            gmGo.AddComponent<NetworkObject>();
            gmGo.AddComponent<GameManager>().map = Load<MapDefinition>(Content + "/Maps/" + mapAsset + ".asset");
            var fx = MakeFx();
            var rigGo = new GameObject("CameraRig");
            var rig = rigGo.AddComponent<CameraRig>();
            rig.cam = MakeCamera("Camera", rigGo.transform);
            rig.cam.backgroundColor = camBackground;
            rigGo.transform.position = new Vector3(0, 10, -10);
            new GameObject("HUD").AddComponent<HUD>();
            return fx;
        }

        static StageMood.Mood Mood(Color sun, float sunI, Color fog, float fogEnd, Color amb, Color eq, Color ground, Color top, Color hor, Color clouds,
            Color moon, float stars, float aurora, float motes) => new()
        {
            sun = sun, sunIntensity = sunI, fog = fog, fogEnd = fogEnd, ambientSky = amb, ambientEquator = eq, ambientGround = ground,
            skyTop = top, skyHorizon = hor, clouds = clouds, moon = moon, stars = stars, aurora = aurora, motes = motes,
        };

        static void AddMoods(Light sun, params StageMood.Mood[] moods)
        {
            var m = sun.gameObject.AddComponent<StageMood>();
            m.sun = sun;
            m.moods = moods;
        }

        static float YawToward(Vector3 from, Vector3 to) => Mathf.Atan2(to.x - from.x, to.z - from.z) * Mathf.Rad2Deg;

        // ======================================================================== MENU / LOBBY SET

        /// <summary>Dusk backdrop for the menu and lobby: a meadow with a cobbled road leading to the keep, trees, the
        /// windmill and mountains. The heroes stand around x 0..5, z 0..3 facing the camera (-Z).</summary>
        static Transform FrontEndSet(string terrainName, int seed)
        {
            var fog = new Color(0.47f, 0.47f, 0.6f);
            Lighting(KeepSkyMat, fog, 30f, 230f, new Color(0.58f, 0.62f, 0.88f), new Color(0.66f, 0.6f, 0.62f), new Color(0.38f, 0.36f, 0.34f));
            Sun(new Vector3(28, -55, 0), new Color(1f, 0.84f, 0.66f), 1.5f);
            new GameObject("PostProcess").AddComponent<Volume>().sharedProfile = MapProfile("Assets/Settings/MB_PostProcessKeep.asset",
                1.0f, 0.7f, new Color(1f, 0.85f, 0.75f), 0.22f, new Color(0.06f, 0.04f, 0.12f), 18f, 14f, 0.2f, new Color(1f, 0.98f, 1.0f));
            FindVolume().isGlobal = true;
            var road = new (Vector2 a, Vector2 b)[] { (new(2, -4), new(2.5f, 30)), (new(2.5f, 30), new(4, 70)) };
            float Hf(float x, float z)
            {
                float d = Mathf.Sqrt((x - 2) * (x - 2) + z * z);
                float h = Fbm(x * 0.03f, z * 0.03f, 3) * 3f * Mathf.SmoothStep(0f, 1f, (d - 14f) / 30f);
                h += Mathf.Max(0f, (Mathf.Abs(x - 2) - 30f) * 0.25f) + Mathf.Max(0f, (z - 60f) * 0.2f);
                return h - Mathf.Max(0f, -z - 20f) * 0.1f;
            }
            void Splat(TerrainData d, float x, float z, float steep, float h, float[] w)
            {
                float cliff = Mathf.Clamp01((steep - 24f) / 8f);
                float rm = RoadMask(x, z, road, 1.4f) * (1 - cliff);
                float dirt = Mathf.Clamp01((Mathf.PerlinNoise(x * 0.07f + 5, z * 0.07f + 9) - 0.66f) * 6f) * (1 - cliff) * (1 - rm);
                w[1] = cliff; w[2] = rm; w[3] = 0f; w[4] = dirt; w[0] = Mathf.Max(0f, 1f - cliff - rm - dirt);
            }
            string tp = Scenes + "/" + terrainName + ".asset";
            if (AssetDatabase.LoadAssetAtPath<TerrainData>(tp) != null) AssetDatabase.DeleteAsset(tp);
            HeightBase = 1f;
            var terrain = BuildTerrain(40f, out var data, Hf, KeepLayers, Splat, tp);
            HeightBase = 0f;
            float H(Vector3 p) => terrain.SampleHeight(p) + terrain.transform.position.y;
            var deco = new GameObject("Props").transform;
            var rng = new System.Random(seed);
            float R() => (float)rng.NextDouble();
            void At(string prop, Vector3 p, float yaw, float scale) { p.y = H(p) - 0.05f; Place(prop, p, yaw, scale, deco); }
            At("Keep", new Vector3(3, 0, 62), 180f, 1.1f);
            At("Windmill", new Vector3(-22, 0, 34), 140f, 1.2f);
            At("TowerRuin", new Vector3(26, 0, 30), 70f, 1.1f);
            At("Mausoleum", new Vector3(24, 0, 16), -120f, 1f);
            At("HangingTree", new Vector3(-14, 0, 14), 40f, 1.0f);
            for (int i = 0; i < 6; i++)
            {
                At("Brazier", new Vector3(i % 2 == 0 ? -0.5f : 5.5f, 0, 12 + i * 7), 0, 1.1f);
                At("Banner", new Vector3(i % 2 == 0 ? -1.5f : 6.5f, 0, 14.5f + i * 7), 180, 1.2f);
            }
            for (int i = 0; i < 26; i++)
            {
                var p = new Vector3(-40 + R() * 80, 0, 6 + R() * 60);
                if (Mathf.Abs(p.x - 2.5f) < 6f) continue;
                At(i % 3 == 0 ? "TreePine" : i % 2 == 0 ? "TreeA" : "TreeB", p, R() * 360f, 1f + R() * 0.5f);
            }
            for (int i = 0; i < 12; i++)
            {
                var p = new Vector3(-14 + R() * 32, 0, 4 + R() * 20);
                if (Mathf.Abs(p.x - 2.5f) < 3.5f) continue;
                At(i % 3 == 0 ? "RockA" : i % 2 == 0 ? "Pumpkin" : "Bush", p, R() * 360f, 0.9f + R() * 0.4f);
            }
            for (int i = 0; i < 140; i++)
            {
                var p = new Vector3(-20 + R() * 45, 0, -6 + R() * 34);
                if (Mathf.Abs(p.x - 2.5f) < 2.2f && p.z > 3f) continue;
                At(i % 5 == 0 ? (i % 2 == 0 ? "FlowersA" : "FlowersB") : "GrassTuft", p, R() * 360f, 0.8f + R() * 0.6f);
            }
            Backdrop(deco, 170f, 14, seed);
            return deco;
        }

        // ======================================================================== HAUNTED KEEP

        static readonly Plateau[] KeepHills =
        {
            new() { c = new Vector2(0, 45), r = 13f, h = 3.4f, rampAngle = 270f },     // the keep's hill
            new() { c = new Vector2(43, 43), r = 8f, h = 4.2f, rampAngle = 225f },
            new() { c = new Vector2(-44, -43), r = 8f, h = 3.6f, rampAngle = 45f },
            new() { c = new Vector2(31, -45), r = 7f, h = 2.6f, rampAngle = 150f },    // statue knoll
            new() { c = new Vector2(-46, 24), r = 7f, h = 3.0f, rampAngle = 315f },
        };

        static readonly (Vector2 a, Vector2 b)[] KeepRoads =
        {
            (new(0, 0), new(0, 34)), (new(0, 0), new(18, 6)), (new(18, 6), new(38, 11)),
            (new(0, 0), new(-20, -2)), (new(-20, -2), new(-32, -6)),
            (new(0, 0), new(4, -18)), (new(4, -18), new(5, -36)), (new(5, -36), new(14, -42)),
            (new(-20, -2), new(-25, -20)), (new(-25, -20), new(-26, -40)),
        };

        static readonly Vector3[] KeepShrines = { new(18, 0, 18), new(-17, 0, 15), new(21, 0, -14), new(-12, 0, -14), new(42, 0, -30) };

        static float Brook(float x) => -27f + Mathf.Sin(x * 0.06f + 0.5f) * 5f + Mathf.Sin(x * 0.17f) * 1.5f;

        static float BrookMask(float x, float z)
        {
            float db = Mathf.Abs(z - Brook(x)) + (Mathf.PerlinNoise(x * 0.15f, 3f) - 0.5f) * 0.8f;
            return 1f - Mathf.SmoothStep(0f, 1f, (db - 1.7f) / 2.2f);
        }

        static float KeepHeight(float x, float z, float half)
        {
            float h = Fbm(x * 0.025f, z * 0.025f, 3) * 2.0f;
            float center = Mathf.Sqrt(x * x + z * z);
            h *= Mathf.SmoothStep(0.3f, 1f, center / 14f);
            foreach (var p in KeepHills) h = Mathf.Max(h, PlateauHeight(x, z, p));
            h = Mathf.Lerp(h, -1.0f, BrookMask(x, z));
            float outside = Mathf.Max(Mathf.Abs(x), Mathf.Abs(z)) - (half + 1f);
            if (outside > 0)
                h += Mathf.Min(outside * 1.6f, 9f) + outside * 0.12f + Fbm(x * 0.03f, z * 0.03f, 3) * Mathf.Min(outside, 30f) * 0.5f;
            return h;
        }

        static void KeepSplat(TerrainData data, float x, float z, float steep, float h, float[] w)
        {
            // 0 grass, 1 cliff, 2 cobbled road, 3 dark forest floor, 4 dirt
            float cliff = Mathf.Clamp01((steep - 21f) / 8f);
            float road = RoadMask(x, z, KeepRoads, 1.5f) * (1 - cliff);
            float bank = Mathf.Clamp01(BrookMask(x, z) * 1.6f);
            float forest = Mathf.Clamp01((-x - 22f) / 8f) * Mathf.Clamp01((Mathf.PerlinNoise(x * 0.07f + 3, z * 0.07f) - 0.25f) * 3f);
            float yard = Mathf.Clamp01(1f - Vector2.Distance(new Vector2(x, z), new Vector2(38, 7)) / 16f) * 1.4f;       // graveyard earth
            float dirt = Mathf.Clamp01(Mathf.Max(bank, yard, Mathf.Clamp01((Mathf.PerlinNoise(x * 0.06f + 5, z * 0.06f + 9) - 0.66f) * 6f)));
            dirt *= (1 - cliff) * (1 - road);
            forest *= (1 - cliff) * (1 - road) * (1 - dirt);
            w[1] = cliff;
            w[2] = road;
            w[3] = forest;
            w[4] = dirt;
            w[0] = Mathf.Max(0f, 1f - cliff - road - forest - dirt);
        }

        static void BuildGameScene(string path)
        {
            string terrainPath = Scenes + "/GameTerrain.asset";
            if (AssetDatabase.LoadAssetAtPath<TerrainData>(terrainPath) != null) AssetDatabase.DeleteAsset(terrainPath);
            var scene = NewScene();
            _padRoot = null;
            var cfg = Load<GameConfig>(Content + "/GameConfig.asset");
            float half = cfg != null ? cfg.arenaHalfSize : 58f;

            // ---- golden dusk: low warm sun, violet sky with the moon rising, cool shadows
            var fogColor = new Color(0.47f, 0.47f, 0.6f);
            Lighting(KeepSkyMat, fogColor, 26f, 210f, new Color(0.58f, 0.62f, 0.88f), new Color(0.66f, 0.6f, 0.62f), new Color(0.38f, 0.36f, 0.34f));
            var sun = Sun(new Vector3(34, -65, 0), new Color(1f, 0.84f, 0.66f), 1.55f);
            new GameObject("PostProcess").AddComponent<Volume>().sharedProfile = MapProfile("Assets/Settings/MB_PostProcessKeep.asset",
                1.0f, 0.7f, new Color(1f, 0.85f, 0.75f), 0.22f, new Color(0.06f, 0.04f, 0.12f), 18f, 14f, 0.2f, new Color(1f, 0.98f, 1.0f));
            FindVolume().isGlobal = true;

            HeightBase = 2f;
            var terrain = BuildTerrain(half, out var data, (x, z) => KeepHeight(x, z, half), KeepLayers, KeepSplat, terrainPath);
            HeightBase = 0f;
            float H(Vector3 p) => terrain.SampleHeight(p) + terrain.transform.position.y;

            // ---- the brook (one big water plane: only shows where the terrain dips under it)
            var water = GameObject.CreatePrimitive(PrimitiveType.Plane);
            water.name = "Water";
            Object.DestroyImmediate(water.GetComponent<Collider>());
            water.transform.position = new Vector3(0, -0.4f, 0);
            water.transform.localScale = new Vector3(32f, 1f, 32f);
            var wr = water.GetComponent<MeshRenderer>();
            wr.sharedMaterial = WaterMat;
            wr.shadowCastingMode = ShadowCastingMode.Off;

            ArenaWalls(half);

            var d = new Dresser { deco = new GameObject("Props").transform, rng = new System.Random(1234), H = H, data = data, half = half };
            d.roads.AddRange(KeepRoads);
            d.Ok = p => BrookMask(p.x, p.z) < 0.05f;
            foreach (var p in KeepHills) d.Block(new Vector3(p.c.x, 0, p.c.y), p.r * 0.75f);
            foreach (var s in KeepShrines) d.Block(s, 4.5f);

            // ---- NORTH: the ruined keep on its hill, braziers and banners flanking the climb
            var keepPos = new Vector3(0, 0, 47);
            d.At("Keep", keepPos, 180f, 1f, 0.3f, 8.5f);
            foreach (var x in new[] { -5f, 5f })
            {
                d.At("Brazier", new Vector3(x, 0, 31), 0, 1.1f);
                d.At("Banner", new Vector3(x * 1.5f, 0, 36), 180, 1.3f);
                d.At("PillarBroken", new Vector3(x * 2.4f, 0, 39), d.R() * 360f, 1.1f, 0.05f, 2f);
            }
            d.Scatter("WallRuin", 4, 3.5f, 0.9f, 1.2f, 14f, 12f, center: new Vector2(0, 46));
            d.Scatter("Crates", 3, 1.6f, 0.9f, 1.2f, 12f, 10f, center: new Vector2(0, 40));

            // ---- EAST: graveyard district with the mausoleum and the hanging tree
            var maus = new Vector3(46, 0, 12);
            d.At("Mausoleum", maus, YawToward(maus, Vector3.zero), 1.15f, 0.1f, 5f);
            PointLight(d.deco, new Vector3(maus.x - 4, H(maus) + 2.5f, maus.z), new Color(0.7f, 0.4f, 1f), 12f, 3f, "CryptGlow");
            for (int row = 0; row < 5; row++)
            for (int col = 0; col < 6; col++)
            {
                var p = new Vector3(28f + col * 3.1f + d.R() * 0.8f, 0, -4f + row * 3.6f + d.R() * 0.8f);
                if (d.RoadDist(p) < 2.2f || !d.Free(p, 0.7f) || d.R() < 0.15f) continue;
                d.At(d.R() < 0.35f ? "TombstoneB" : "TombstoneA", p, -90f + d.R() * 24f - 12f, 0.9f + d.R() * 0.3f, 0.05f, 0.7f);
            }
            for (int i = 0; i < 9; i++)   // iron fence along the west edge of the yard
            {
                var p = new Vector3(25f, 0, -6f + i * 2.4f);
                if (d.RoadDist(p) < 2.4f) continue;
                d.At("Fence", p, 90f, 1f);
            }
            var tree = new Vector3(36, 0, -14);
            d.At("HangingTree", tree, d.R() * 360f, 1.1f, 0.2f, 2.5f);
            PointLight(d.deco, tree + Vector3.up * (H(tree) + 4f), new Color(0.6f, 1f, 0.5f), 12f, 2.4f, "TreeGlow");
            d.Scatter("SkullPile", 8, 1f, 0.8f, 1.2f, 20f, 14f, false, center: new Vector2(38, 4));
            d.Scatter("LanternPost", 4, 1.5f, 1f, 1f, 10f, 12f, center: new Vector2(32, 8), roadClear: 0f, where: p => d.RoadDist(p) < 3.2f);

            // ---- WEST: the witch wood (dense trees, a rune circle, bouncy mushrooms)
            var circle = new Vector3(-37, 0, -7);
            for (int i = 0; i < 8; i++)
            {
                float a = i / 8f * Mathf.PI * 2f;
                var p = circle + new Vector3(Mathf.Cos(a), 0, Mathf.Sin(a)) * 6.5f;
                d.At("RuneStone", p, YawToward(p, circle), 1.25f, 0.05f, 1.2f);
            }
            d.Block(circle, 5.5f);
            PointLight(d.deco, circle + Vector3.up * (H(circle) + 3f), new Color(0.5f, 0.85f, 1f), 14f, 3f, "CircleGlow");
            System.Func<Vector3, bool> wood = p => p.x < -24f;
            d.Scatter("TreePine", 26, 2f, 1.0f, 1.6f, 22f, half - 3, where: wood);
            d.Scatter("TreeA", 12, 2.4f, 1.0f, 1.4f, 20f, half - 3, where: wood);
            d.Scatter("DeadTree", 10, 1.5f, 1.0f, 1.4f, 20f, half - 3, where: wood);
            d.Scatter("Mushrooms", 40, 0.5f, 1.0f, 2.0f, 25f, half - 2, false, where: wood);
            d.Scatter("Bush", 30, 1.2f, 0.9f, 1.4f, 25f, half - 2, false, where: wood);

            // ---- SOUTH: the brook, two bridges, windmill, well, the knight statue on its knoll
            foreach (var bx in new[] { 4.5f, -25.5f })
            {
                var bp = new Vector3(bx, 0, Brook(bx));
                float slope = Mathf.Atan((Brook(bx + 1f) - Brook(bx - 1f)) / 2f) * Mathf.Rad2Deg;
                bp.y = Mathf.Max(H(bp + Vector3.forward * 4f), H(bp - Vector3.forward * 4f)) - 0.3f;
                Place("Bridge", bp, -slope, 1.15f, d.deco);
                d.Block(bp, 3f);
            }
            var mill = new Vector3(-30, 0, -46);
            d.At("Windmill", mill, YawToward(mill, new Vector3(-10, 0, -20)), 1.2f, 0.1f, 3.5f);
            d.At("Well", new Vector3(13, 0, -38), d.R() * 360f, 1f, 0.05f, 1.4f);
            var statue = new Vector3(31, 0, -45);
            d.At("KnightStatue", statue, YawToward(statue, Vector3.zero), 1.2f, 0.1f, 3f);
            d.Scatter("Crates", 4, 1.6f, 0.9f, 1.2f, 12f, 8f, center: new Vector2(-24, -44));
            d.Scatter("Fence", 6, 1.2f, 1f, 1f, 12f, 10f, center: new Vector2(-30, -40));
            for (int i = 0; i < 14; i++)   // reeds and rocks along the banks
            {
                float x = -half + 4 + d.R() * (half * 2 - 8);
                var p = new Vector3(x, 0, Brook(x) + (d.R() < 0.5f ? -3.2f : 3.2f));
                if (d.RoadDist(p) < 3f || !d.Free(p, 1f)) continue;
                d.At(d.R() < 0.5f ? "RockA" : "Bush", p, d.R() * 360f, 0.7f + d.R() * 0.4f, 0.1f, 1f);
            }

            // ---- corner ruins on the hills
            d.At("TowerRuin", new Vector3(43, 0, 44), d.R() * 360f, 1.0f, 0.3f, 4f);
            d.At("TowerRuin", new Vector3(-44, 0, -44), d.R() * 360f, 0.9f, 0.3f, 4f);
            d.At("WallRuin", new Vector3(-46, 0, 26), 30f, 1.1f, 0.05f, 3f);

            // ---- general dressing (sparser than before: landmarks carry the look)
            d.Scatter("TreeA", 8, 2.5f, 0.9f, 1.3f, 18f, half - 3, where: p => p.x > -20f);
            d.Scatter("TreeB", 8, 2.5f, 0.9f, 1.3f, 18f, half - 3, where: p => p.x > -20f);
            d.Scatter("RockA", 12, 1.8f, 0.8f, 1.4f, 30f, half - 3);
            d.Scatter("RockB", 6, 2.6f, 0.8f, 1.3f, 30f, half - 3);
            d.Scatter("Log", 6, 1.8f, 0.9f, 1.1f, 10f, half - 4);
            d.Scatter("Brazier", 6, 1.5f, 1f, 1f, 10f, half - 6, roadClear: 0f, where: p => d.RoadDist(p) < 3.5f && d.RoadDist(p) > 2.2f);
            d.Scatter("LanternPost", 8, 1.5f, 1f, 1f, 10f, half - 4, roadClear: 0f, where: p => d.RoadDist(p) < 3.4f && d.RoadDist(p) > 2.2f);
            d.Scatter("FlowersA", 80, 0f, 0.8f, 1.4f, 25f, half, false, 0.02f, where: p => p.x > -22f);
            d.Scatter("FlowersB", 80, 0f, 0.8f, 1.4f, 25f, half, false, 0.02f, where: p => p.x > -22f);
            d.Scatter("Mushrooms", 20, 0.5f, 0.8f, 1.4f, 25f, half - 2, false);
            d.Scatter("Bush", 30, 1.2f, 0.8f, 1.3f, 25f, half - 2, false);
            d.Scatter("GrassTuft", 1000, 0f, 0.7f, 1.5f, 35f, half, false, 0.02f, where: p => d.RoadDist(p) > 1.8f);

            // ---- frame: castle wall ring, trees on the hills, mountains
            float wallD = half + 3.5f;
            for (int side = 0; side < 4; side++)
            {
                for (float t = -wallD + 4f; t < wallD - 2f; t += 8f)
                {
                    if (d.R() < 0.2f) continue;
                    var p = Quaternion.Euler(0, side * 90f, 0) * new Vector3(t, 0, wallD);
                    p.y = H(p) - 0.8f;
                    var w = Place("CastleWall", p, side * 90f + 180f + d.R() * 4f - 2f, 1f, d.deco);
                    if (w != null && d.R() < 0.3f) w.transform.localScale = new Vector3(1f, 0.6f + d.R() * 0.3f, 1f);
                }
                var corner = Quaternion.Euler(0, side * 90f, 0) * new Vector3(wallD, 0, wallD);
                corner.y = H(corner) - 0.8f;
                Place("CastleTower", corner, d.R() * 360f, 1.1f, d.deco);
            }
            d.Outskirts(new[] { "TreePine", "TreeA", "TreeB", "TreePine" }, 80, 1.2f, 2.0f);
            Backdrop(d.deco, 230f, 18, 3);

            EditorSceneManager.SaveScene(scene, path);

            // ---- network objects: shrines, smashables; bounce pads
            MakeShrines(KeepShrines, H);
            MakeBreakables(d, new[] { ("Pumpkin", new Color(1f, 0.55f, 0.15f), 1.3f), ("Urn", new Color(0.8f, 0.45f, 0.25f), 1.1f), ("Barrel", new Color(0.55f, 0.36f, 0.2f), 1.0f) },
                44, new[] { new Vector2(0, 32), new Vector2(34, 6), new Vector2(-34, -6), new Vector2(-26, -42), new Vector2(12, -38), new Vector2(-20, 22), new Vector2(24, -24) }, 0.75f);
            var shroom = new Color(1f, 0.45f, 0.55f);
            foreach (var p in new[] { new Vector3(-30, 0, 12), new Vector3(-44, 0, 8), new Vector3(-11, 0, 37), new Vector3(36, 0, 33), new Vector3(-36, 0, -34), new Vector3(20, 0, -32) })
                MakePad(d, "BounceShroom", p, 20f, shroom, 1.4f, 1.2f);

            // stage 2: night falls; stage 3: the blood moon rises
            AddMoods(sun,
                Mood(new Color(0.72f, 0.76f, 1f), 1.1f, new Color(0.3f, 0.32f, 0.48f), 195f, new Color(0.44f, 0.5f, 0.78f), new Color(0.46f, 0.45f, 0.56f),
                    new Color(0.27f, 0.27f, 0.31f), new Color(0.05f, 0.07f, 0.2f), new Color(0.36f, 0.34f, 0.56f), new Color(0.32f, 0.3f, 0.48f),
                    new Color(1f, 0.97f, 0.88f), 0.95f, 0f, 45f),
                Mood(new Color(1f, 0.56f, 0.5f), 1.15f, new Color(0.36f, 0.18f, 0.24f), 175f, new Color(0.62f, 0.4f, 0.52f), new Color(0.56f, 0.36f, 0.42f),
                    new Color(0.3f, 0.18f, 0.2f), new Color(0.12f, 0.02f, 0.06f), new Color(0.64f, 0.16f, 0.18f), new Color(0.42f, 0.12f, 0.16f),
                    new Color(1f, 0.3f, 0.24f), 0.6f, 0f, 55f));
            var fx = ArenaSystems("Graveyard", fogColor);
            fx.ambientColorA = new Color(0.55f, 1f, 0.75f, 0.85f);    // fireflies and wisps
            fx.ambientColorB = new Color(0.85f, 0.7f, 1f, 0.75f);
            fx.ambientRate = 30f;
            fx.ambientRise = 0.08f;

            OrganizeScene(scene);
            EditorSceneManager.SaveScene(scene, path);
        }

        static Volume FindVolume() => Object.FindFirstObjectByType<Volume>();

        // ======================================================================== FROSTFALL PEAKS

        static readonly Plateau[] FrostHills =
        {
            new() { c = new Vector2(-31, 39), r = 11f, h = 4.2f, rampAngle = 300f },   // the frozen titan
            new() { c = new Vector2(42, 40), r = 9f, h = 2.2f, rampAngle = 225f },    // igloo village
            new() { c = new Vector2(-45, -8), r = 7f, h = 4.6f, rampAngle = 0f },
            new() { c = new Vector2(8, -47), r = 8f, h = 3.4f, rampAngle = 90f },
            new() { c = new Vector2(47, -2), r = 6f, h = 3.0f, rampAngle = 180f },
        };

        static readonly Vector2 LakeC = new(25, -19);
        const float LakeRX = 15f, LakeRZ = 10f;

        static readonly (Vector2 a, Vector2 b)[] FrostRoads =
        {
            (new(0, 0), new(-12, 18)), (new(-12, 18), new(-22, 30)),
            (new(0, 0), new(-20, -12)), (new(-20, -12), new(-32, -22)),
            (new(0, 0), new(20, 18)), (new(20, 18), new(34, 32)),
            (new(0, 0), new(9, -10)),
            (new(0, 0), new(0, -34)),
        };

        static readonly Vector3[] FrostShrines = { new(15, 0, 12), new(-15, 0, 10), new(-13, 0, -21), new(6, 0, -30), new(44, 0, 16) };

        static float LakeMask(float x, float z)
        {
            float u = (x - LakeC.x) / LakeRX, v = (z - LakeC.y) / LakeRZ;
            float r = Mathf.Sqrt(u * u + v * v) + (Mathf.PerlinNoise(x * 0.12f, z * 0.12f) - 0.5f) * 0.18f;
            return 1f - Mathf.SmoothStep(0f, 1f, (r - 0.9f) / 0.22f);
        }

        static float FrostHeight(float x, float z, float half)
        {
            float h = Fbm(x * 0.022f + 90f, z * 0.022f, 3) * 2.6f;
            float center = Mathf.Sqrt(x * x + z * z);
            h *= Mathf.SmoothStep(0.25f, 1f, center / 15f);
            foreach (var p in FrostHills) h = Mathf.Max(h, PlateauHeight(x, z, p, 1.2f));
            h = Mathf.Lerp(h, -0.25f, LakeMask(x, z));
            float outside = Mathf.Max(Mathf.Abs(x), Mathf.Abs(z)) - (half + 1f);
            if (outside > 0)
                h += Mathf.Min(outside * 2.0f, 11f) + outside * 0.18f + Fbm(x * 0.03f, z * 0.03f, 3) * Mathf.Min(outside, 30f) * 0.7f;
            return h;
        }

        static void FrostSplat(TerrainData data, float x, float z, float steep, float h, float[] w)
        {
            // 0 snow, 1 blue rock cliff, 2 packed-snow path, 3 lake ice
            float cliff = Mathf.Clamp01((steep - 23f) / 8f);
            float ice = Mathf.Clamp01(LakeMask(x, z) * 1.4f - 0.2f) * (1 - cliff);
            float path = RoadMask(x, z, FrostRoads, 1.5f) * (1 - cliff) * (1 - ice);
            float drift = Mathf.Clamp01((Mathf.PerlinNoise(x * 0.05f + 20, z * 0.05f) - 0.68f) * 5f) * (1 - cliff) * (1 - ice) * (1 - path) * 0.5f;
            w[1] = cliff;
            w[2] = path + drift;
            w[3] = ice;
            w[0] = Mathf.Max(0f, 1f - w[1] - w[2] - w[3]);
        }

        static void BuildFrostScene(string path)
        {
            string terrainPath = Scenes + "/FrostTerrain.asset";
            if (AssetDatabase.LoadAssetAtPath<TerrainData>(terrainPath) != null) AssetDatabase.DeleteAsset(terrainPath);
            var scene = NewScene();
            _padRoot = null;
            var cfg = Load<GameConfig>(Content + "/GameConfig.asset");
            float half = cfg != null ? cfg.arenaHalfSize : 58f;

            // ---- moonlit night: aurora over the peaks, bright snow, cool blue fog
            var fogColor = new Color(0.5f, 0.62f, 0.8f);
            Lighting(FrostSkyMat, fogColor, 26f, 175f, new Color(0.55f, 0.64f, 0.9f), new Color(0.5f, 0.58f, 0.74f), new Color(0.62f, 0.68f, 0.8f));
            var sun = Sun(new Vector3(42, 150, 0), new Color(0.78f, 0.86f, 1f), 1.15f);
            sun.shadowStrength = 0.55f;
            new GameObject("PostProcess").AddComponent<Volume>().sharedProfile = MapProfile("Assets/Settings/MB_PostProcessFrost.asset",
                1.05f, 0.75f, new Color(0.75f, 0.9f, 1f), 0.26f, new Color(0.02f, 0.05f, 0.14f), 16f, 6f, 0.0f, new Color(0.96f, 0.99f, 1.06f));
            FindVolume().isGlobal = true;

            HeightBase = 2f;
            var terrain = BuildTerrain(half, out var data, (x, z) => FrostHeight(x, z, half), FrostLayers, FrostSplat, terrainPath);
            HeightBase = 0f;
            float H(Vector3 p) => terrain.SampleHeight(p) + terrain.transform.position.y;

            ArenaWalls(half);

            // the frozen lake: slippery for everyone who runs onto it
            var lake = new GameObject("FrozenLake");
            lake.transform.position = new Vector3(LakeC.x, H(new Vector3(LakeC.x, 0, LakeC.y)), LakeC.y);
            var iz = lake.AddComponent<IceZone>();
            iz.radiusX = LakeRX * 0.95f;
            iz.radiusZ = LakeRZ * 0.95f;

            var d = new Dresser { deco = new GameObject("Props").transform, rng = new System.Random(777), H = H, data = data, half = half };
            d.roads.AddRange(FrostRoads);
            d.Ok = p => LakeMask(p.x, p.z) < 0.05f;
            foreach (var p in FrostHills) d.Block(new Vector3(p.c.x, 0, p.c.y), p.r * 0.75f);
            foreach (var s in FrostShrines) d.Block(s, 4.5f);

            // ---- center: a ring of rune monoliths around the spawn
            for (int i = 0; i < 7; i++)
            {
                float a = (i / 7f + 0.05f) * Mathf.PI * 2f;
                var p = new Vector3(Mathf.Cos(a), 0, Mathf.Sin(a)) * 11.5f;
                if (d.RoadDist(p) < 2.5f) continue;
                d.At(i % 2 == 0 ? "RuneMonolithA" : "RuneMonolithB", p, YawToward(p, Vector3.zero), 1.05f, 0.1f, 1.2f);
            }
            PointLight(d.deco, new Vector3(0, H(Vector3.zero) + 4f, 0), new Color(0.4f, 1f, 0.75f), 18f, 1.6f, "CircleGlow");

            // ---- NORTH-WEST: the frozen titan on its hill
            var titan = new Vector3(-32, 0, 41);
            d.At("FrozenTitan", titan, YawToward(titan, Vector3.zero), 1.0f, 0.4f, 6f);
            PointLight(d.deco, titan + new Vector3(4, H(titan) + 5f, -4), new Color(0.5f, 0.85f, 1f), 18f, 3f, "TitanGlow");
            d.Scatter("IceSpireA", 5, 1.6f, 0.9f, 1.4f, 22f, 12f, center: new Vector2(-30, 38));
            d.Scatter("IceSpireB", 4, 1.6f, 0.9f, 1.4f, 22f, 12f, center: new Vector2(-30, 38));

            // ---- SOUTH-WEST: an abandoned viking camp
            var hall = new Vector3(-40, 0, -28);
            d.At("Longhouse", hall, 90f + d.R() * 10f, 1.1f, 0.1f, 5.5f);
            foreach (var t in new[] { new Vector3(-29, 0, -36), new Vector3(-46, 0, -40), new Vector3(-27, 0, -20) })
                d.At("Tent", t, YawToward(t, new Vector3(-34, 0, -30)), 1.1f, 0.05f, 2f);
            var fire = new Vector3(-34, 0, -30);
            d.At("Campfire", fire, 0, 1.2f, 0.02f, 1.6f);
            var fl = PointLight(d.deco, fire + Vector3.up * (H(fire) + 1.2f), new Color(1f, 0.6f, 0.25f), 12f, 4f, "CampfireLight");
            fl.gameObject.AddComponent<FireFlicker>().lightSource = fl;
            d.Scatter("Crates", 4, 1.6f, 0.9f, 1.2f, 12f, 8f, center: new Vector2(-38, -22));
            d.Scatter("Banner", 4, 1.2f, 1.1f, 1.3f, 12f, 10f, center: new Vector2(-34, -30));

            // ---- NORTH-EAST: igloo village
            foreach (var g in new[] { new Vector3(37, 0, 36), new Vector3(46, 0, 44), new Vector3(49, 0, 32) })
                d.At("Igloo", g, YawToward(g, new Vector3(42, 0, 38)), 1.1f, 0.2f, 3f);
            var fire2 = new Vector3(43, 0, 38);
            d.At("Campfire", fire2, 0, 1f, 0.02f, 1.2f);
            var fl2 = PointLight(d.deco, fire2 + Vector3.up * (H(fire2) + 1.2f), new Color(1f, 0.6f, 0.25f), 10f, 3.5f, "IglooFire");
            fl2.gameObject.AddComponent<FireFlicker>().lightSource = fl2;

            // ---- EAST: the frozen lake ringed by ice spires
            for (int i = 0; i < 10; i++)
            {
                float a = i / 10f * Mathf.PI * 2f + d.R() * 0.3f;
                var p = new Vector3(LakeC.x + Mathf.Cos(a) * (LakeRX + 3.2f), 0, LakeC.y + Mathf.Sin(a) * (LakeRZ + 3.2f));
                if (d.RoadDist(p) < 3f || !d.Free(p, 1.4f)) continue;
                d.At(i % 2 == 0 ? "IceSpireA" : "IceSpireB", p, d.R() * 360f, 0.8f + d.R() * 0.6f, 0.1f, 1.4f);
            }

            // ---- edges: frozen waterfalls pouring off the cliffs
            d.At("FrozenWaterfall", new Vector3(8, 0, half + 7f), 180f, 1.3f, 1.5f);
            d.At("FrozenWaterfall", new Vector3(-half - 7f, 0, 6), 90f, 1.1f, 1.5f);
            d.At("FrozenWaterfall", new Vector3(half + 7f, 0, -30), -90f, 1.2f, 1.5f);

            // ---- forests and rocks
            d.Scatter("SnowPineA", 30, 2f, 1.0f, 1.5f, 22f, half - 3, where: p => d.RoadDist(p) > 4f);
            d.Scatter("SnowPineB", 24, 2f, 1.0f, 1.6f, 22f, half - 3, where: p => d.RoadDist(p) > 4f);
            d.Scatter("SnowRockA", 16, 1.6f, 0.8f, 1.4f, 30f, half - 3);
            d.Scatter("SnowRockB", 8, 2.6f, 0.8f, 1.3f, 30f, half - 3);
            d.Scatter("IceSpireA", 8, 1.6f, 0.7f, 1.2f, 25f, half - 3);
            d.Scatter("IceSpireB", 6, 1.6f, 0.7f, 1.2f, 25f, half - 3);
            d.Scatter("DeadTree", 8, 1.5f, 0.9f, 1.3f, 20f, half - 3);
            d.Scatter("Log", 5, 1.8f, 0.9f, 1.1f, 10f, half - 4);
            d.Scatter("SkullPile", 8, 1f, 0.8f, 1.2f, 20f, half - 4, false);
            d.Scatter("LanternPost", 8, 1.5f, 1f, 1f, 10f, half - 4, roadClear: 0f, where: p => d.RoadDist(p) < 3.4f && d.RoadDist(p) > 2.2f);

            // ---- frame
            d.Outskirts(new[] { "SnowPineA", "SnowPineB", "IceSpireA", "SnowPineA" }, 90, 1.3f, 2.2f);
            for (int i = 0; i < 18; i++)
            {
                float a = i / 18f * 360f + d.R() * 12f;
                var p = Quaternion.Euler(0, a, 0) * Vector3.forward * (230f * (0.9f + d.R() * 0.35f));
                p.y = -4f;
                Place(i % 2 == 0 ? "FrostMountainB" : "FrostMountainA", p, d.R() * 360f, 0.9f + d.R() * 0.7f, d.deco);
            }

            EditorSceneManager.SaveScene(scene, path);

            MakeShrines(FrostShrines, H, new Color(0.45f, 1f, 0.8f));
            MakeBreakables(d, new[] { ("IceCrate", new Color(0.6f, 0.9f, 1f), 1.1f), ("FrozenUrn", new Color(0.55f, 0.8f, 1f), 1.1f), ("Barrel", new Color(0.55f, 0.36f, 0.2f), 1.0f) },
                46, new[] { new Vector2(-34, -28), new Vector2(42, 38), new Vector2(-24, 34), new Vector2(8, -36), new Vector2(20, 22), new Vector2(-22, 6), new Vector2(34, 2) }, 0.75f);
            var geyser = new Color(0.45f, 0.95f, 1f);
            foreach (var p in new[] { new Vector3(-22, 0, 26), new Vector3(-38, 0, -6), new Vector3(36, 0, 24), new Vector3(16, 0, -38), new Vector3(42, 0, -6), new Vector3(-8, 0, 30) })
                MakePad(d, "IceGeyser", p, 21f, geyser, 1.4f, 1.15f);

            // stage 2: the aurora storm; stage 3: the blizzard rolls in
            AddMoods(sun,
                Mood(new Color(0.76f, 0.86f, 1f), 1.1f, new Color(0.45f, 0.58f, 0.8f), 160f, new Color(0.55f, 0.66f, 0.95f), new Color(0.5f, 0.6f, 0.78f),
                    new Color(0.62f, 0.7f, 0.84f), new Color(0.03f, 0.06f, 0.18f), new Color(0.3f, 0.46f, 0.68f), new Color(0.4f, 0.5f, 0.7f),
                    new Color(0.9f, 0.95f, 1f), 1f, 1.9f, 220f),
                Mood(new Color(0.8f, 0.86f, 0.98f), 0.95f, new Color(0.62f, 0.7f, 0.82f), 115f, new Color(0.62f, 0.68f, 0.86f), new Color(0.58f, 0.64f, 0.76f),
                    new Color(0.66f, 0.7f, 0.8f), new Color(0.12f, 0.16f, 0.3f), new Color(0.52f, 0.6f, 0.74f), new Color(0.62f, 0.68f, 0.8f),
                    new Color(0.9f, 0.95f, 1f), 0.5f, 1.4f, 420f));
            var fx = ArenaSystems("Frost", fogColor);
            fx.ambientSnow = true;
            fx.ambientColorA = new Color(1f, 1f, 1f, 0.95f);
            fx.ambientColorB = new Color(0.85f, 0.93f, 1f, 0.85f);
            fx.ambientRate = 140f;

            OrganizeScene(scene);
            EditorSceneManager.SaveScene(scene, path);
        }
    }
}
