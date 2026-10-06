using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;

namespace MultiBash.EditorTools
{
    /// <summary>
    /// One-click project builder. Menu: MultiBash > Setup.
    ///  - "Build Everything" creates anything that's missing and never overwrites assets you edited.
    ///  - "Rebuild Everything (overwrite)" regenerates all generated assets from code.
    /// Generated content: import settings, materials, ScriptableObjects, prefabs, scenes, build settings.
    /// </summary>
    public static partial class MultiBashSetup
    {
        public const string Root = "Assets/_Game";
        public const string Art = Root + "/Art";
        public const string Models = Art + "/Models";
        public const string Mats = Art + "/Materials";
        public const string Tex = Art + "/Textures";
        public const string Vfx = Art + "/VFX";
        public const string UIDir = Root + "/UI";
        public const string AudioDir = Root + "/Audio";
        public const string Content = Root + "/Content";
        public const string Prefabs = Root + "/Prefabs";
        public const string Scenes = Root + "/Scenes";

        /// <summary>When true, existing generated assets are replaced.</summary>
        static bool Force;

        [MenuItem("MultiBash/Setup/Build Everything", priority = 1)]
        public static void BuildEverything() => Run(false);

        [MenuItem("MultiBash/Setup/Rebuild Everything (overwrite)", priority = 2)]
        public static void RebuildEverything()
        {
            if (Application.isBatchMode || EditorUtility.DisplayDialog("Rebuild everything?",
                    "This regenerates all MultiBash content assets, prefabs and scenes from code and overwrites your edits to them.", "Rebuild", "Cancel"))
                Run(true);
        }

        public static void RunForce() => Run(true);

        [MenuItem("MultiBash/Setup/Reset Content Data To Defaults", priority = 4)]
        public static void ResetContentData()
        {
            Force = false;
            BuildMaterials();
            ConfigureImports();
            Force = true;
            BuildThemeAndAudio();
            BuildContent();
            Force = false;
            BuildPrefabs();          // only creates prefabs that are missing (new enemies / props)
            Force = true;
            LinkContent();
            Force = false;
            RefreshDatabase();
            AssetDatabase.SaveAssets();
            EditorApplication.ExecuteMenuItem("Tools/Fusion/Rebuild Prefab Table");
            Debug.Log("[MultiBash] Content data reset to the defaults in MultiBashSetup.Content.cs.");
        }

        [MenuItem("MultiBash/Setup/Rebuild Scenes Only", priority = 3)]
        public static void RebuildScenes()
        {
            Force = false;
            BuildMaterials();
            Force = true;
            BuildScenes();
            Force = false;
            AssetDatabase.SaveAssets();
            Debug.Log("[MultiBash] Scenes rebuilt.");
        }

        static void Run(bool force)
        {
            Force = force;
            try
            {
                AssetDatabase.StartAssetEditing();
                EnsureFolders();
                ConfigureProject();
            }
            finally
            {
                AssetDatabase.StopAssetEditing();
            }
            AssetDatabase.Refresh();
            ConfigureImports();
            AssetDatabase.Refresh();
            BuildMaterials();
            BuildThemeAndAudio();
            BuildContent();
            BuildPrefabs();
            LinkContent();
            RefreshDatabase();
            BuildScenes();
            AssetDatabase.SaveAssets();
            // make sure Fusion knows about every network prefab we just created
            EditorApplication.ExecuteMenuItem("Tools/Fusion/Rebuild Prefab Table");
            Debug.Log("[MultiBash] Setup complete.");
        }

        // ================================================================== folders & project

        static void EnsureFolders()
        {
            string[] dirs =
            {
                Mats, Tex, Vfx, Art + "/Shaders", UIDir + "/Fonts", UIDir + "/Sprites", UIDir + "/Icons",
                Content + "/Characters", Content + "/Weapons", Content + "/Powerups", Content + "/Enemies", Content + "/Waves", Content + "/Maps",
                Content + "/Pickups", Content + "/Resources", Prefabs + "/Network", Prefabs + "/Environment",
                Prefabs + "/Systems/Resources", Scenes, "Assets/Settings",
            };
            foreach (var d in dirs) Directory.CreateDirectory(d);
        }

        static void ConfigureProject()
        {
            // layers
            var tagManager = new SerializedObject(AssetDatabase.LoadAllAssetsAtPath("ProjectSettings/TagManager.asset")[0]);
            var layers = tagManager.FindProperty("layers");
            SetLayer(layers, 8, "Environment");
            SetLayer(layers, 9, "Player");
            SetLayer(layers, 10, "Enemy");
            SetLayer(layers, 11, "Pickup");
            tagManager.ApplyModifiedProperties();
            Physics.IgnoreLayerCollision(9, 9, true);   // players pass through each other
            Physics.IgnoreLayerCollision(9, 10, true);
            Physics.IgnoreLayerCollision(9, 11, true);

            PlayerSettings.productName = "MultiBash";
            PlayerSettings.companyName = "MultiBash";
            PlayerSettings.runInBackground = true;      // keep simulating when alt-tabbed (needed for co-op)
            PlayerSettings.visibleInBackground = true;
            PlayerSettings.fullScreenMode = FullScreenMode.Windowed;
            PlayerSettings.defaultScreenWidth = 1600;
            PlayerSettings.defaultScreenHeight = 900;
            PlayerSettings.resizableWindow = true;
            PlayerSettings.forceSingleInstance = false;  // allow two copies for local testing
        }

        static void SetLayer(SerializedProperty layers, int index, string name)
        {
            var p = layers.GetArrayElementAtIndex(index);
            if (string.IsNullOrEmpty(p.stringValue) || p.stringValue == name) p.stringValue = name;
        }

        // ================================================================== import settings

        static void ConfigureImports()
        {
            foreach (var path in Find("t:Model", Models))
            {
                var mi = (ModelImporter)AssetImporter.GetAtPath(path);
                bool dirty = false;
                // heroes are skinned meshes with an armature (Tools/Blender/characters.py): generic rig, no avatar, axis baked
                bool skinned = path.Contains("/Characters/");
                var anim = skinned ? ModelImporterAnimationType.Generic : ModelImporterAnimationType.None;
                if (mi.animationType != anim) { mi.animationType = anim; dirty = true; }
                if (skinned && mi.avatarSetup != ModelImporterAvatarSetup.NoAvatar) { mi.avatarSetup = ModelImporterAvatarSetup.NoAvatar; dirty = true; }
                if (mi.bakeAxisConversion != skinned) { mi.bakeAxisConversion = skinned; dirty = true; }
                if (mi.importAnimation) { mi.importAnimation = false; dirty = true; }
                if (mi.importCameras || mi.importLights) { mi.importCameras = false; mi.importLights = false; dirty = true; }
                if (mi.materialImportMode != ModelImporterMaterialImportMode.ImportStandard) { mi.materialImportMode = ModelImporterMaterialImportMode.ImportStandard; dirty = true; }
                if (mi.importBlendShapes) { mi.importBlendShapes = false; dirty = true; }
                if (dirty) mi.SaveAndReimport();
            }

            // pixel-art look: everything point filtered, uncompressed, no mipmaps on small textures
            Texture(Tex + "/T_Palette.png", t =>
            {
                t.filterMode = FilterMode.Point;
                t.mipmapEnabled = false;
                t.textureCompression = TextureImporterCompression.Uncompressed;
                t.wrapMode = TextureWrapMode.Clamp;
                t.sRGBTexture = true;
                t.alphaIsTransparency = false;
            });
            Texture(Tex + "/T_DetailAtlas.png", t =>
            {
                t.filterMode = FilterMode.Point;
                t.mipmapEnabled = false;
                t.textureCompression = TextureImporterCompression.Uncompressed;
                t.wrapMode = TextureWrapMode.Repeat;
                t.sRGBTexture = false;
            });
            foreach (var p in Find("t:Texture2D", Tex + "/Characters"))
                Texture(p, t =>
                {
                    t.filterMode = FilterMode.Point;
                    t.mipmapEnabled = true;
                    t.textureCompression = TextureImporterCompression.Uncompressed;
                    t.wrapMode = TextureWrapMode.Clamp;
                    t.sRGBTexture = true;
                    t.alphaIsTransparency = false;
                });
            foreach (var n in new[] { "T_TerrainGrass", "T_TerrainDirt", "T_TerrainCliff", "T_TerrainMoss",
                         "T_TerrainBasalt", "T_TerrainAsh", "T_TerrainMagma", "T_TerrainVolcCliff", "T_Lava" })
                Texture($"{Tex}/{n}.png", t =>
                {
                    t.filterMode = FilterMode.Point;
                    t.mipmapEnabled = true;
                    t.textureCompression = TextureImporterCompression.Uncompressed;
                    t.wrapMode = TextureWrapMode.Repeat;
                });
            Texture(Tex + "/T_Ground.png", t => { t.wrapMode = TextureWrapMode.Repeat; t.anisoLevel = 4; });
            Texture(Tex + "/T_Stone.png", t => t.wrapMode = TextureWrapMode.Repeat);
            foreach (var p in Find("t:Texture2D", Vfx))
                Texture(p, t =>
                {
                    t.alphaIsTransparency = true;
                    t.wrapMode = TextureWrapMode.Clamp;
                    t.textureCompression = TextureImporterCompression.Uncompressed;
                    t.filterMode = FilterMode.Point;
                    t.mipmapEnabled = false;
                });

            // 9-slice borders in texels (sprites are drawn at 3 screen pixels per texel: PPU 33.33 vs canvas 100)
            var borders = new System.Collections.Generic.Dictionary<string, Vector4>
            {
                { "UI_Panel", new Vector4(6, 6, 6, 6) },
                { "UI_TitleBar", new Vector4(6, 6, 6, 6) },
                { "UI_RoundRect", new Vector4(1, 1, 1, 1) },
                { "UI_Button", new Vector4(3, 4, 3, 4) },
                { "UI_Card", new Vector4(4, 4, 4, 4) },
                { "UI_Slot", new Vector4(2, 2, 2, 2) },
                { "UI_Outline", new Vector4(3, 3, 3, 3) },
            };
            foreach (var p in Find("t:Texture2D", UIDir))
            {
                Texture(p, t =>
                {
                    t.textureType = TextureImporterType.Sprite;
                    t.spriteImportMode = SpriteImportMode.Single;
                    t.alphaIsTransparency = true;
                    t.mipmapEnabled = false;
                    t.filterMode = FilterMode.Point;
                    t.textureCompression = TextureImporterCompression.Uncompressed;
                    var name = Path.GetFileNameWithoutExtension(p);
                    bool frame = borders.ContainsKey(name);
                    t.spritePixelsPerUnit = frame ? 33.333f : 100f;
                    if (borders.TryGetValue(name, out var b)) t.spriteBorder = b;
                });
            }

            // pixel fonts: crisp rasterization
            foreach (var p in Find("t:Font", UIDir + "/Fonts"))
            {
                var fi = AssetImporter.GetAtPath(p) as TrueTypeFontImporter;
                if (fi == null || fi.fontRenderingMode == FontRenderingMode.HintedRaster) continue;
                fi.fontRenderingMode = FontRenderingMode.HintedRaster;
                fi.SaveAndReimport();
            }

            foreach (var p in Find("t:AudioClip", AudioDir + "/SFX"))
            {
                var ai = (AudioImporter)AssetImporter.GetAtPath(p);
                var s = ai.defaultSampleSettings;
                if (s.loadType != AudioClipLoadType.DecompressOnLoad || !ai.forceToMono)
                {
                    s.loadType = AudioClipLoadType.DecompressOnLoad;
                    ai.defaultSampleSettings = s;
                    ai.forceToMono = true;
                    ai.SaveAndReimport();
                }
            }
            foreach (var p in Find("t:AudioClip", AudioDir + "/Music"))
            {
                var ai = (AudioImporter)AssetImporter.GetAtPath(p);
                var s = ai.defaultSampleSettings;
                if (s.loadType != AudioClipLoadType.Streaming)
                {
                    s.loadType = AudioClipLoadType.Streaming;
                    s.compressionFormat = AudioCompressionFormat.Vorbis;
                    s.quality = 0.7f;
                    ai.defaultSampleSettings = s;
                    ai.SaveAndReimport();
                }
            }

            // fonts (copied from the Fusion package's OFL fonts so they're included in builds)
            CopyIfMissing("Assets/Photon/Fusion/Editor/EditorResources/Fonts/Oswald-Header.ttf", UIDir + "/Fonts/Oswald.ttf");
            CopyIfMissing("Assets/Photon/Fusion/Runtime/RuntimeAssets/Roboto-Regular.ttf", UIDir + "/Fonts/Roboto.ttf");
            CopyIfMissing("Assets/Photon/Fusion/Editor/EditorResources/Fonts/OFL.txt", UIDir + "/Fonts/OFL.txt");
        }

        static void CopyIfMissing(string from, string to)
        {
            if (File.Exists(to) || !File.Exists(from)) return;
            AssetDatabase.CopyAsset(from, to);
        }

        static void Texture(string path, System.Action<TextureImporter> edit)
        {
            var ti = AssetImporter.GetAtPath(path) as TextureImporter;
            if (ti == null) return;
            var before = EditorJsonUtility.ToJson(ti);
            edit(ti);
            if (EditorJsonUtility.ToJson(ti) != before) ti.SaveAndReimport();
        }

        public static string[] Find(string filter, string folder) =>
            AssetDatabase.FindAssets(filter, new[] { folder }).Select(AssetDatabase.GUIDToAssetPath).Distinct().ToArray();

        // ================================================================== materials

        public static Material PaletteMat, GroundMat, FxAdd, FxAlpha, StoneMat, SkyMat, GrassMat, TerrainMat, VolcanoSkyMat, LavaMat;
        public static TerrainLayer[] TerrainLayers, VolcanoLayers;

        static TerrainLayer Layer(string name, string tex, float tile)
        {
            string path = $"{Mats}/{name}.terrainlayer";
            var l = Load<TerrainLayer>(path);
            if (l == null)
            {
                l = new TerrainLayer();
                AssetDatabase.CreateAsset(l, path);
            }
            l.diffuseTexture = Load<Texture2D>($"{Tex}/{tex}.png");
            l.tileSize = new Vector2(tile, tile);
            l.smoothness = 0f;
            l.metallic = 0f;
            EditorUtility.SetDirty(l);
            return l;
        }

        static void BuildMaterials()
        {
            var lit = Shader.Find("Universal Render Pipeline/Lit");
            var pixelLit = Shader.Find("MultiBash/PixelLit");
            PaletteMat = Mat(Mats + "/M_Palette.mat", pixelLit, m =>
            {
                m.SetTexture("_BaseMap", Load<Texture2D>(Tex + "/T_Palette.png"));
                m.SetTexture("_DetailAtlas", Load<Texture2D>(Tex + "/T_DetailAtlas.png"));
                m.SetColor("_BaseColor", Color.white);
                m.SetFloat("_DetailTile", 1.6f);
                m.SetFloat("_DetailStrength", 0.8f);
                m.SetColor("_EmissionColor", Color.black);
                m.SetFloat("_Wrap", 0.35f);
                m.SetColor("_ShadowTint", new Color(0.45f, 0.58f, 0.8f));
                m.enableInstancing = true;
            });
            // the palette material must use PixelLit even when not forcing (older projects had URP/Lit)
            if (PaletteMat.shader != pixelLit && pixelLit != null)
            {
                PaletteMat.shader = pixelLit;
                PaletteMat.SetTexture("_BaseMap", Load<Texture2D>(Tex + "/T_Palette.png"));
                PaletteMat.SetTexture("_DetailAtlas", Load<Texture2D>(Tex + "/T_DetailAtlas.png"));
                PaletteMat.SetFloat("_DetailTile", 1.6f);
                PaletteMat.SetFloat("_DetailStrength", 0.8f);
                PaletteMat.SetFloat("_Wrap", 0.35f);
                PaletteMat.SetColor("_ShadowTint", new Color(0.45f, 0.58f, 0.8f));
                EditorUtility.SetDirty(PaletteMat);
            }
            SkyMat = Mat(Mats + "/M_Sky.mat", Shader.Find("MultiBash/PixelSky"), m => { });
            GrassMat = Mat(Mats + "/M_Grass.mat", lit, m =>
            {
                m.SetTexture("_BaseMap", Load<Texture2D>(Tex + "/T_TerrainGrass.png"));
                m.SetTextureScale("_BaseMap", new Vector2(20, 20));
                m.SetFloat("_Smoothness", 0.0f);
            });
            TerrainMat = Mat(Mats + "/M_Terrain.mat", Shader.Find("Universal Render Pipeline/Terrain/Lit"), m => { });
            TerrainLayers = new[]
            {
                Layer("TL_Grass", "T_TerrainGrass", 4.5f),
                Layer("TL_Cliff", "T_TerrainCliff", 5f),
                Layer("TL_Dirt", "T_TerrainDirt", 4f),
                Layer("TL_Moss", "T_TerrainMoss", 4.5f),
            };
            VolcanoLayers = new[]
            {
                Layer("TL_Basalt", "T_TerrainBasalt", 4.5f),
                Layer("TL_VolcCliff", "T_TerrainVolcCliff", 5f),
                Layer("TL_Ash", "T_TerrainAsh", 4f),
                Layer("TL_Magma", "T_TerrainMagma", 4.5f),
            };
            VolcanoSkyMat = Mat(Mats + "/M_SkyVolcano.mat", Shader.Find("MultiBash/PixelSky"), m =>
            {
                m.SetColor("_TopColor", new Color(0.16f, 0.05f, 0.07f));
                m.SetColor("_HorizonColor", new Color(0.78f, 0.3f, 0.12f));
                m.SetColor("_BottomColor", new Color(0.3f, 0.1f, 0.06f));
                m.SetColor("_CloudColor", new Color(0.36f, 0.17f, 0.15f));
                m.SetFloat("_CloudCover", 0.62f);
                m.SetFloat("_CloudScale", 2.4f);
                m.SetFloat("_Speed", 0.007f);
            });
            LavaMat = Mat(Mats + "/M_Lava.mat", Shader.Find("MultiBash/PixelLava"), m =>
            {
                m.SetTexture("_MainTex", Load<Texture2D>(Tex + "/T_Lava.png"));
                m.SetColor("_Tint", Color.white);
                m.SetFloat("_Glow", 2.4f);
                m.SetFloat("_Tile", 7f);
            });
            GroundMat = Mat(Mats + "/M_Ground.mat", lit, m =>
            {
                m.SetTexture("_BaseMap", Load<Texture2D>(Tex + "/T_Ground.png"));
                m.SetTextureScale("_BaseMap", new Vector2(14, 14));
                m.SetColor("_BaseColor", new Color(0.85f, 0.9f, 0.85f));
                m.SetFloat("_Smoothness", 0.05f);
            });
            StoneMat = Mat(Mats + "/M_Stone.mat", lit, m =>
            {
                m.SetTexture("_BaseMap", Load<Texture2D>(Tex + "/T_Stone.png"));
                m.SetFloat("_Smoothness", 0.1f);
            });
            FxAdd = Mat(Mats + "/M_FxAdditive.mat", Shader.Find("MultiBash/FxAdditive"), m =>
            {
                m.SetTexture("_MainTex", Load<Texture2D>(Vfx + "/T_SoftParticle.png"));
                m.enableInstancing = true;
            });
            FxAlpha = Mat(Mats + "/M_FxAlpha.mat", Shader.Find("MultiBash/FxAlpha"), m =>
            {
                m.SetTexture("_MainTex", Load<Texture2D>(Vfx + "/T_SoftParticle.png"));
                m.enableInstancing = true;
            });

            // per-hero materials with their baked painted textures (names match the FBX materials "M_Char_<Name>")
            foreach (var texPath in Find("t:Texture2D", Tex + "/Characters"))
            {
                string hero = Path.GetFileNameWithoutExtension(texPath).Replace("T_Char_", "");
                Mat($"{Mats}/M_Char_{hero}.mat", pixelLit, m =>
                {
                    m.SetTexture("_BaseMap", Load<Texture2D>(texPath));
                    m.SetTexture("_DetailAtlas", Load<Texture2D>(Tex + "/T_DetailAtlas.png"));
                    m.SetColor("_BaseColor", Color.white);
                    m.SetFloat("_DetailTile", 1.6f);
                    m.SetFloat("_DetailStrength", 0.4f);
                    m.SetColor("_EmissionColor", Color.black);
                    m.SetFloat("_Wrap", 0.35f);
                    m.SetColor("_ShadowTint", new Color(0.45f, 0.58f, 0.8f));
                    m.enableInstancing = true;
                });
            }

            // make every model use the shared palette material (remap by name "M_Palette")
            foreach (var path in Find("t:Model", Models))
            {
                var mi = (ModelImporter)AssetImporter.GetAtPath(path);
                var map = mi.GetExternalObjectMap();
                bool ok = map.Any(kv => kv.Value == PaletteMat);
                if (ok && !Force) continue;
                mi.SearchAndRemapMaterials(ModelImporterMaterialName.BasedOnMaterialName, ModelImporterMaterialSearch.Everywhere);
                mi.SaveAndReimport();
            }
        }

        static Material Mat(string path, Shader shader, System.Action<Material> setup)
        {
            var m = AssetDatabase.LoadAssetAtPath<Material>(path);
            bool created = m == null;
            if (created)
            {
                m = new Material(shader);
                AssetDatabase.CreateAsset(m, path);
            }
            if (created || Force)
            {
                m.shader = shader;
                setup(m);
                EditorUtility.SetDirty(m);
            }
            return m;
        }

        public static T Load<T>(string path) where T : Object => AssetDatabase.LoadAssetAtPath<T>(path);

        public static Sprite Sprite(string path) => AssetDatabase.LoadAssetAtPath<Sprite>(path);

        public static AudioClip Clip(string name)
        {
            var guid = AssetDatabase.FindAssets(name + " t:AudioClip", new[] { AudioDir }).FirstOrDefault(g => Path.GetFileNameWithoutExtension(AssetDatabase.GUIDToAssetPath(g)) == name);
            return guid == null ? null : AssetDatabase.LoadAssetAtPath<AudioClip>(AssetDatabase.GUIDToAssetPath(guid));
        }

        public static GameObject Model(string category, string name) => Load<GameObject>($"{Models}/{category}/{name}.fbx");

        /// <summary>Load or create a ScriptableObject. `fill` runs only for new assets (or when forcing).</summary>
        public static T Asset<T>(string path, System.Action<T> fill) where T : ScriptableObject
        {
            var a = AssetDatabase.LoadAssetAtPath<T>(path);
            bool created = a == null;
            if (created)
            {
                Directory.CreateDirectory(Path.GetDirectoryName(path));
                a = ScriptableObject.CreateInstance<T>();
                AssetDatabase.CreateAsset(a, path);
            }
            if (created || Force)
            {
                fill(a);
                EditorUtility.SetDirty(a);
            }
            return a;
        }
    }
}
