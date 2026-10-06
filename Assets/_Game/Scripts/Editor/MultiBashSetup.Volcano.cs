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
            _padRoot = null;
            var cfg = Load<GameConfig>(Content + "/GameConfig.asset");
            float half = cfg != null ? cfg.arenaHalfSize : 58f;

            // ---- atmosphere: smoky ember dusk (brighter than before so the swarm reads against the rock)
            var fogColor = new Color(0.34f, 0.2f, 0.27f);
            Lighting(VolcanoSkyMat, fogColor, 26f, 185f, new Color(0.58f, 0.56f, 0.76f), new Color(0.5f, 0.44f, 0.54f), new Color(0.56f, 0.3f, 0.2f));
            Sun(new Vector3(42, -60, 0), new Color(1f, 0.8f, 0.62f), 1.5f);
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
            void LavaLight(Vector3 p, float range, float intensity) => PointLight(glow, p + Vector3.up * 2.5f, new Color(1f, 0.45f, 0.12f), range, intensity, "Glow");
            for (float x = -half + 6; x < half; x += 18f)
                if (LavaMask(x, RiverA(x), half) > 0.5f) LavaLight(new Vector3(x, LavaLevel, RiverA(x)), 14f, 3f);
            for (float z = -half + 6; z < RiverA(-28f); z += 18f)
                if (LavaMask(RiverB(z), z, half) > 0.5f) LavaLight(new Vector3(RiverB(z), LavaLevel, z), 14f, 3f);
            LavaLight(new Vector3(36, LavaLevel, -32), 18f, 4f);
            LavaLight(new Vector3(-46, LavaLevel, 22), 14f, 3f);
            LavaLight(new Vector3(6, LavaLevel, -52), 14f, 3f);

            ArenaWalls(half);

            var d = new Dresser { deco = new GameObject("Props").transform, rng = new System.Random(4321), H = H, data = data, half = half };
            d.Ok = p => H(p) > LavaLevel + 0.6f;
            foreach (var p in VolcanoMesas) d.Block(new Vector3(p.c.x, 0, p.c.y), p.r * 0.8f);
            foreach (var s in VolcanoShrines) d.Block(s, 4.5f);
            bool NearLava(Vector3 p) => LavaMask(p.x + 4, p.z, half) + LavaMask(p.x - 4, p.z, half) + LavaMask(p.x, p.z + 4, half) + LavaMask(p.x, p.z - 4, half) > 0.3f;

            // ---- the dragon's bones: a ribcage arching over the middle lava crossing, its skull to the east
            var ribs = new Vector3(2f, 0, RiverA(2f));
            ribs.y = Mathf.Max(H(ribs + Vector3.forward * 7f), H(ribs - Vector3.forward * 7f)) - 0.5f;
            Place("DragonRibcage", ribs, 0f, 1.05f, d.deco);
            d.Block(ribs, 6f);
            var skull = new Vector3(41, 0, -14);
            d.At("DragonSkull", skull, YawToward(skull, Vector3.zero) + 180f, 1.0f, 1.2f, 7f);
            foreach (var c in new[] { new Vector3(30, 0, -22), new Vector3(46, 0, -2), new Vector3(-20, 0, 46) })
                if (d.Free(c, 3f) && H(c) > LavaLevel + 0.6f) d.At("DragonClaw", c, d.R() * 360f, 0.9f + d.R() * 0.3f, 0.6f, 2.6f);

            // ---- the abandoned dwarven forge and a titan's hammer on the high mesas
            var forge = new Vector3(-14, 0, -34);
            d.At("DwarfForge", forge, YawToward(forge, Vector3.zero), 1.1f, 0.1f, 4f);
            d.At("GiantHammer", new Vector3(-40, 0, 40), 25f, 1.1f, 0.3f, 3f);
            d.Scatter("Crates", 3, 1.6f, 0.9f, 1.2f, 12f, 7f, center: new Vector2(-14, -30));

            // ---- landmarks on the other mesas
            d.At("ObsidianSpire", new Vector3(31, 0, 7), 0f, 1.4f, 0.2f, 1.5f);
            d.At("FireTotem", new Vector3(42, 0, 42), 0f, 1.3f, 0.1f, 1.2f);
            d.At("FireTotem", new Vector3(-44, 0, -8), 0f, 1.2f, 0.1f, 1.2f);

            // ---- glowing crystal fields
            d.Scatter("CrystalCluster", 6, 1.4f, 1.2f, 1.9f, 20f, 9f, center: new Vector2(-34, 10));
            d.Scatter("CrystalCluster", 5, 1.4f, 1.2f, 1.9f, 20f, 9f, center: new Vector2(20, 40));
            d.Scatter("CrystalCluster", 6, 1.4f, 1.0f, 1.6f, 20f, half - 6);

            // ---- dressing (sparser: the landmarks carry the look)
            d.Scatter("FireTotem", 6, 1.5f, 0.9f, 1.1f, 12f, half - 6);
            d.Scatter("ObsidianSpire", 10, 1.8f, 0.8f, 1.4f, 18f, half - 4);
            d.Scatter("BasaltColumnsA", 8, 2.4f, 0.7f, 1.2f, 20f, half - 4);
            d.Scatter("BasaltColumnsB", 8, 2.4f, 0.7f, 1.2f, 20f, half - 4);
            d.Scatter("SulfurVent", 10, 1.5f, 0.8f, 1.3f, 14f, half - 4);
            d.Scatter("LavaRockA", 16, 1.8f, 0.8f, 1.4f, 30f, half - 3, where: NearLava);
            d.Scatter("LavaRockB", 8, 2.6f, 0.8f, 1.3f, 30f, half - 3);
            d.Scatter("CharredTreeA", 12, 1.5f, 0.9f, 1.4f, 18f, half - 3);
            d.Scatter("CharredTreeB", 12, 1.5f, 0.9f, 1.4f, 18f, half - 3);
            d.Scatter("SkullPile", 14, 1.0f, 0.8f, 1.3f, 20f, half - 4, false);
            d.Scatter("Brazier", 6, 1.5f, 1f, 1f, 10f, half - 6);

            // ---- frame: basalt ring, lava falls pouring from the caldera walls, ash mountains, the volcano
            float ringD = half + 3f;
            for (int side = 0; side < 4; side++)
            {
                for (float t = -ringD; t < ringD; t += 5.5f)
                {
                    var p = Quaternion.Euler(0, side * 90f, 0) * new Vector3(t + d.R() * 2f, 0, ringD + d.R() * 3f);
                    p.y = H(p) - 0.6f;
                    Place(d.R() < 0.5f ? "BasaltColumnsA" : "BasaltColumnsB", p, d.R() * 360f, 1.2f + d.R() * 0.8f, d.deco);
                }
                for (int k = 0; k < 2; k++)
                {
                    var p = Quaternion.Euler(0, side * 90f, 0) * new Vector3(-22f + k * 44f + d.R() * 8f, 0, half + 9f);
                    p.y = H(p) - 4.5f;
                    Place("LavaFall", p, side * 90f + 180f, 1.8f + d.R() * 0.4f, d.deco);
                }
            }
            d.Outskirts(new[] { "ObsidianSpire", "CharredTreeA", "CharredTreeB" }, 60, 1.3f, 2.5f, 7f);
            for (int i = 0; i < 18; i++)
            {
                float a = i / 18f * 360f + d.R() * 12f;
                var p = Quaternion.Euler(0, a, 0) * Vector3.forward * (230f * (0.9f + d.R() * 0.35f));
                p.y = -4f;
                Place(i % 2 == 0 ? "AshMountainB" : "AshMountainA", p, d.R() * 360f, 0.9f + d.R() * 0.7f, d.deco);
            }
            Place("VolcanoPeak", new Vector3(30, -8, 205), 20f, 1.25f, d.deco);
            Place("VolcanoPeak", new Vector3(-190, -10, -80), 140f, 0.8f, d.deco);

            // Fusion needs the scene saved (so it has a GUID) before it can bake scene NetworkObjects
            EditorSceneManager.SaveScene(scene, path);

            MakeShrines(VolcanoShrines, H);
            MakeBreakables(d, new[] { ("MagmaUrn", new Color(0.35f, 0.3f, 0.3f), 1.1f), ("Urn", new Color(0.8f, 0.45f, 0.25f), 1.1f), ("Barrel", new Color(0.55f, 0.36f, 0.2f), 1.0f) },
                44, new[] { new Vector2(-14, -28), new Vector2(34, -10), new Vector2(-34, 10), new Vector2(20, 40), new Vector2(20, -20), new Vector2(-20, 18) }, 0.75f);
            var steam = new Color(1f, 0.7f, 0.35f);
            foreach (var p in new[] { new Vector3(20, 0, 2), new Vector3(-6, 0, -26), new Vector3(-32, 0, 34), new Vector3(34, 0, 34), new Vector3(-36, 0, -12), new Vector3(16, 0, -40) })
                if (H(p) > LavaLevel + 0.6f) MakePad(d, "SteamVent", p, 21f, steam, 1.4f, 1.1f);

            var fx = ArenaSystems("Volcano", fogColor);
            fx.ambientColorA = new Color(1f, 0.55f, 0.15f, 0.95f);
            fx.ambientColorB = new Color(1f, 0.3f, 0.08f, 0.85f);
            fx.ambientRate = 45f;
            fx.ambientRise = 0.25f;

            OrganizeScene(scene);
            EditorSceneManager.SaveScene(scene, path);
        }
    }
}
