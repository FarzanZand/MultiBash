using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

namespace MultiBash
{
    /// <summary>
    /// Local-only visual effects: particles, slashes, cosmetic projectiles, lightning, flasks, puddles,
    /// damage numbers. Nothing here affects gameplay, so it's safe to tweak freely.
    /// Lives in the Game scene. Textures/materials are assigned by the setup tool (or by hand).
    /// </summary>
    public class FxManager : MonoBehaviour
    {
        public static FxManager Instance { get; private set; }

        [Header("Materials")]
        public Material additive;
        public Material alpha;

        [Header("Textures")]
        public Texture2D softTexture;
        public Texture2D sparkTexture;
        public Texture2D ringTexture;
        public Texture2D slashTexture;
        public Texture2D puddleTexture;
        public Texture2D lightningTexture;

        [Header("Damage numbers")]
        public Font font;

        [Header("Audio")]
        public AudioClip flaskShatter;

        [Header("Ambient (per level)")]
        public Color ambientColorA = new(1f, 0.85f, 0.5f, 0.8f);
        public Color ambientColorB = new(0.7f, 1f, 0.8f, 0.7f);
        public float ambientRate = 22f;
        [Tooltip("Upward drift of ambient motes (embers rise).")]
        public float ambientRise = 0.05f;

        static readonly int ColorId = Shader.PropertyToID("_Color");

        Mesh _quad;
        MaterialPropertyBlock _mpb;
        Camera _cam;

        readonly Stack<Transform> _additivePool = new();
        readonly Stack<Transform> _alphaPool = new();

        // ---------------------------------------------------------------- timed objects (slashes, decals, lines)
        class Timed
        {
            public Transform t;
            public Renderer r;
            public LineRenderer line;
            public float age, life, fadeIn;
            public Color color;
            public Vector3 baseScale;
            public bool grow, additivePool, isLine, billboardY, holdAlpha;
        }

        readonly List<Timed> _timed = new();
        readonly Stack<LineRenderer> _linePool = new();

        // ---------------------------------------------------------------- cosmetic projectiles
        class Shot
        {
            public Transform t;
            public Vector3 vel;
            public float life, age, turn, spin, outTime;
            public bool returning;
            public int pierceLeft;
            public HashSet<Enemy> hit = new();
            public WeaponDefinition def;
            public Transform returnTo;   // boomerangs fly back to their thrower
            public bool hostile;         // enemy projectile: just flies, no enemy hit checks
        }

        readonly List<Shot> _shots = new();
        readonly Dictionary<GameObject, Stack<Transform>> _modelPools = new();

        class Flight
        {
            public Transform t;
            public Vector3 from, to;
            public float time, duration, radius, puddleLife;
            public WeaponDefinition def;
            public bool meteor;
        }

        readonly List<Flight> _flights = new();

        // ---------------------------------------------------------------- damage numbers
        class Number
        {
            public Text text;
            public Vector3 world;
            public float age;
            public float scale;
        }

        Canvas _canvas;
        readonly List<Number> _numbers = new();
        readonly Stack<Text> _numberPool = new();

        void Awake()
        {
            Instance = this;
            _mpb = new MaterialPropertyBlock();
            _quad = BuildQuad();
            var cgo = new GameObject("DamageNumbers", typeof(Canvas), typeof(CanvasScaler));
            cgo.transform.SetParent(transform, false);
            _canvas = cgo.GetComponent<Canvas>();
            _canvas.renderMode = RenderMode.ScreenSpaceOverlay;
            _canvas.sortingOrder = 5;
            var scaler = cgo.GetComponent<CanvasScaler>();
            scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
            scaler.referenceResolution = new Vector2(1920, 1080);
            scaler.matchWidthOrHeight = 0.5f;
        }

        void OnDestroy()
        {
            if (Instance == this) Instance = null;
        }

        static Mesh BuildQuad()
        {
            var m = new Mesh { name = "FxQuad" };
            m.vertices = new[] { new Vector3(-0.5f, -0.5f), new Vector3(0.5f, -0.5f), new Vector3(-0.5f, 0.5f), new Vector3(0.5f, 0.5f) };
            m.uv = new[] { new Vector2(0, 0), new Vector2(1, 0), new Vector2(0, 1), new Vector2(1, 1) };
            m.triangles = new[] { 0, 2, 1, 2, 3, 1 };
            m.RecalculateNormals();
            m.RecalculateBounds();
            return m;
        }

        Camera Cam
        {
            get
            {
                if (_cam == null) _cam = Camera.main;
                return _cam;
            }
        }

        // ================================================================= public API

        public void DamageNumber(Vector3 world, float amount, bool onPlayer, bool crit = false)
        {
            var C = CombatManager.Settings;
            if (font == null || amount < 0.5f || !C.showDamageNumbers) return;
            if (_numbers.Count >= C.maxDamageNumbers)
            {
                var oldest = _numbers[0];
                _numbers.RemoveAt(0);
                oldest.text.gameObject.SetActive(false);
                _numberPool.Push(oldest.text);
            }
            var text = _numberPool.Count > 0 ? _numberPool.Pop() : CreateNumberText();
            text.gameObject.SetActive(true);
            int v = Mathf.RoundToInt(amount);
            text.text = crit ? $"<size=16>CRIT!</size>\n{v}" : v.ToString();
            text.color = onPlayer ? new Color(1f, 0.25f, 0.2f) : crit ? new Color(1f, 0.86f, 0.15f) : Color.white;
            _numbers.Add(new Number
            {
                text = text,
                world = world + new Vector3(Random.Range(-0.4f, 0.4f), Random.Range(0f, 0.4f), Random.Range(-0.4f, 0.4f)),
                scale = onPlayer ? 1.2f : crit ? 1.35f : 1f,
            });
        }

        Text CreateNumberText()
        {
            var go = new GameObject("Dmg", typeof(RectTransform), typeof(Text), typeof(Outline));
            go.transform.SetParent(_canvas.transform, false);
            var t = go.GetComponent<Text>();
            t.font = font;
            t.fontSize = 24;
            t.alignment = TextAnchor.MiddleCenter;
            t.raycastTarget = false;
            t.supportRichText = true;
            t.lineSpacing = 0.8f;
            t.horizontalOverflow = HorizontalWrapMode.Overflow;
            t.verticalOverflow = VerticalWrapMode.Overflow;
            var o = go.GetComponent<Outline>();
            o.effectColor = Color.black;
            o.effectDistance = new Vector2(3, -3);
            ((RectTransform)go.transform).sizeDelta = new Vector2(120, 40);
            return t;
        }

        public void Burst(Vector3 pos, Color color, int count, float speed, float size, float life, float gravity = 9f, bool additiveBlend = true)
        {
            for (int i = 0; i < count; i++)
            {
                var dir = Random.onUnitSphere;
                dir.y = Mathf.Abs(dir.y) * 0.8f + 0.2f;
                SpawnParticle(pos, dir * speed * Random.Range(0.5f, 1.1f), color, size * Random.Range(0.7f, 1.3f),
                    life * Random.Range(0.7f, 1.2f), gravity, 1.5f, additiveBlend, sparkTexture);
            }
        }

        // big hordes die by the hundred: past this budget, deaths get a lighter burst so the screen stays readable
        float _deathBudget = 40f, _deathBudgetTime;

        public void DeathBurst(Vector3 pos, Color color, float scale)
        {
            float s = Mathf.Sqrt(scale);
            float now = Time.unscaledTime;
            _deathBudget = Mathf.Min(40f, _deathBudget + (now - _deathBudgetTime) * CombatManager.Settings.deathEffectsPerSecond);
            _deathBudgetTime = now;
            bool full = _deathBudget >= 1f || scale > 1.2f;
            _deathBudget -= 1f;
            if (!full)
            {
                for (int i = 0; i < 3; i++)
                {
                    var v = new Vector3(Random.Range(-1f, 1f), Random.Range(0.6f, 1.4f), Random.Range(-1f, 1f)) * 5f;
                    var c = color; c.a = 1f;
                    SpawnParticle(pos + Vector3.up * 0.8f, v, c, Random.Range(0.12f, 0.2f), 0.8f, 16f, 0.6f, false, null);
                }
                return;
            }
            // tumbling cube debris
            int n = Mathf.RoundToInt(9 * s);
            for (int i = 0; i < n; i++)
            {
                var v = new Vector3(Random.Range(-1f, 1f), Random.Range(0.6f, 1.4f), Random.Range(-1f, 1f)) * 5.5f * s;
                var c = Color.Lerp(color, color * 0.7f, Random.value);
                c.a = 1f;
                SpawnParticle(pos + Vector3.up * 0.8f * scale + Random.insideUnitSphere * 0.3f * scale, v, c, Random.Range(0.12f, 0.24f) * s, Random.Range(0.9f, 1.4f), 16f, 0.6f, false, null);
            }
            // white pop + dust poof (lighter when lots die at once)
            Burst(pos + Vector3.up * 0.8f * scale, Color.white, 1, 4f, 0.2f * s, 0.12f, 0f, true);
            int poofs = _deathBudget > 20f ? 3 : 1;
            for (int i = 0; i < poofs; i++)
                SpawnParticle(pos + Vector3.up * 0.3f, new Vector3(Random.Range(-1.5f, 1.5f), Random.Range(0.3f, 1f), Random.Range(-1.5f, 1.5f)),
                    new Color(0.8f, 0.8f, 0.76f, 0.4f), Random.Range(0.5f, 0.85f) * s, 0.5f, -0.5f, 2f, false, softTexture);
        }

        /// <summary>Small white impact spark on every hit (bigger + golden on crits).</summary>
        public void HitSpark(Vector3 pos, bool crit)
        {
            int n = crit ? 6 : 3;
            var c = crit ? new Color(1f, 0.85f, 0.3f) : Color.white;
            for (int i = 0; i < n; i++)
                SpawnParticle(pos + Random.insideUnitSphere * 0.2f, Random.onUnitSphere * (crit ? 7f : 4.5f), c, crit ? 0.32f : 0.22f, 0.18f, 0f, 4f, true, sparkTexture);
        }

        /// <summary>Vertical beam of light (level ups, chests, revives).</summary>
        public void LightPillar(Vector3 pos, Color color, float height = 9f, float life = 0.9f)
        {
            for (int k = 0; k < 2; k++)
            {
                var t = GetQuad(true, softTexture);
                t.position = pos + Vector3.up * height * 0.5f;
                t.rotation = Quaternion.Euler(0, k * 90f, 0);
                var c = color;
                c.a = 0.8f;
                var timed = new Timed { t = t, r = t.GetComponent<Renderer>(), life = life, color = c, baseScale = new Vector3(1.4f, height, 1f), additivePool = true, billboardY = true };
                t.localScale = timed.baseScale;
                _timed.Add(timed);
            }
        }

        public void Dust(Vector3 pos, int count)
        {
            for (int i = 0; i < count; i++)
            {
                var v = new Vector3(Random.Range(-2f, 2f), Random.Range(0.5f, 1.5f), Random.Range(-2f, 2f));
                SpawnParticle(pos + Vector3.up * 0.1f, v, new Color(0.75f, 0.72f, 0.65f, 0.6f), Random.Range(0.3f, 0.6f), 0.5f, -0.5f, 2f, false, softTexture);
            }
        }

        public void UpgradeBurst(Vector3 pos, Color color)
        {
            LightPillar(pos, color);
            var ring = CreateGroundDecal("UpgradeRing", ringTexture, true);
            ring.position = pos + Vector3.up * 0.08f;
            AddTimed(ring, 0.6f, color, Vector3.one * 5f, true, true);
            for (int i = 0; i < 18; i++)
            {
                var p = pos + new Vector3(Random.Range(-0.8f, 0.8f), Random.Range(0f, 0.5f), Random.Range(-0.8f, 0.8f));
                SpawnParticle(p, new Vector3(0, Random.Range(2f, 6f), 0), color, Random.Range(0.2f, 0.4f), Random.Range(0.6f, 1.1f), -1f, 0.5f, true, sparkTexture);
            }
        }

        public void Slash(Vector3 origin, Vector3 dir, float radius, float arc, Color color)
        {
            dir.y = 0;
            if (dir.sqrMagnitude < 0.0001f) dir = Vector3.forward;
            dir.Normalize();
            var t = GetQuad(true, slashTexture);
            // texture: circle centred at the bottom middle with radius 0.41 of the width
            float k = radius / 0.41f;
            t.rotation = Quaternion.LookRotation(Vector3.down, dir); // lie flat, texture "up" = dir
            t.position = origin + Vector3.down * 0.4f + dir * (k * 0.5f);
            AddTimed(t, 0.22f, color, new Vector3(k, k, 1f), false, true);
            // a second, brighter thinner layer for punch
            var t2 = GetQuad(true, slashTexture);
            t2.rotation = t.rotation;
            t2.position = t.position + Vector3.up * 0.05f;
            AddTimed(t2, 0.12f, Color.white, new Vector3(k * 0.95f, k * 0.95f, 1f), false, true);
        }

        public void Projectiles(Vector3 origin, Vector3 dir, int count, float spread, float speed, float life, int pierce, WeaponDefinition def)
        {
            for (int i = 0; i < count; i++)
            {
                float a = count == 1 ? 0f : -spread * 0.5f + spread * i / (count - 1);
                var d = Quaternion.Euler(0, a, 0) * dir;
                var t = GetModel(def != null ? def.projectileModel : null);
                t.position = origin;
                t.rotation = Quaternion.LookRotation(d);
                t.localScale = Vector3.one * 1.3f;
                var shot = new Shot { t = t, vel = d * speed, life = life, pierceLeft = Mathf.Max(1, pierce), def = def };
                _shots.Add(shot);
            }
        }

        // ---------------------------------------------------------------- new weapon visuals

        public void Boomerangs(Transform owner, Vector3 origin, Vector3 dir, int count, float spread, float speed, float life, WeaponDefinition def)
        {
            for (int i = 0; i < count; i++)
            {
                float a = count == 1 ? 0f : -spread * 0.5f + spread * i / (count - 1);
                var d = Quaternion.Euler(0, a, 0) * dir;
                var t = GetModel(def != null ? def.projectileModel : null);
                t.position = origin;
                t.localScale = Vector3.one * 1.6f;
                _shots.Add(new Shot { t = t, vel = d * speed, life = 30f, outTime = life * 0.5f, pierceLeft = 9999, def = def, returnTo = owner, spin = 900f });
            }
        }

        public void HomingShots(Vector3 origin, Vector3 dir, int count, float speed, float life, int pierce, float turn, WeaponDefinition def)
        {
            for (int i = 0; i < count; i++)
            {
                var d = Quaternion.Euler(Random.Range(-25f, -5f), -60f + 120f * (count == 1 ? 0.5f : i / (float)(count - 1)), 0) * dir;
                var t = GetModel(def != null ? def.projectileModel : null);
                t.position = origin + Vector3.up * 0.4f;
                t.rotation = Quaternion.LookRotation(d);
                t.localScale = Vector3.one * 1.4f;
                _shots.Add(new Shot { t = t, vel = d * speed, life = life, pierceLeft = Mathf.Max(1, pierce), def = def, turn = turn });
            }
        }

        public void EnemyProjectile(Vector3 origin, Vector3 vel, float life, Color color)
        {
            var t = GetQuad(true, sparkTexture);
            t.position = origin;
            t.localScale = Vector3.one * 0.7f;
            var r = t.GetComponent<Renderer>();
            r.GetPropertyBlock(_mpb);
            _mpb.SetColor(ColorId, color * 1.5f);
            r.SetPropertyBlock(_mpb);
            _shots.Add(new Shot { t = t, vel = vel, life = life, pierceLeft = 1, hostile = true });
            Burst(origin, color, 3, 2f, 0.3f, 0.2f, 0f, true);
        }

        public void Meteor(Vector3 target, float delay, float radius, WeaponDefinition def)
        {
            var col = def != null ? def.fxColor : new Color(1f, 0.5f, 0.2f);
            Telegraph(target, radius, delay, new Color(1f, 0.5f, 0.15f));
            var t = GetModel(def != null ? def.projectileModel : null);
            var start = target + new Vector3(Random.Range(-6f, 6f), 18f, Random.Range(-6f, 6f));
            t.position = start;
            t.localScale = Vector3.one * (1.2f + radius * 0.35f);
            _flights.Add(new Flight { t = t, from = start, to = target, duration = delay, radius = radius, def = def, meteor = true });
        }

        // ------------------------------------------------------------------ chest opening (local visual only)

        class Loot
        {
            public Transform t;
            public Vector3 vel, spin;
            public float age, life;
            public bool landed;
        }

        readonly List<Loot> _loot = new();

        /// <summary>A chest that wobbles, flings its lid open in a burst of light and sprays loot everywhere.</summary>
        public void ChestOpen(Vector3 pos, Vector3 facing)
        {
            var cfg = GameDatabase.Config;
            if (cfg.chestModel == null)
            {
                UpgradeBurst(pos, new Color(1f, 0.85f, 0.3f));
                return;
            }
            StartCoroutine(ChestRoutine(pos, facing));
        }

        System.Collections.IEnumerator ChestRoutine(Vector3 pos, Vector3 facing)
        {
            var cfg = GameDatabase.Config;
            var lib = AudioManager.Lib;
            var gold = new Color(1f, 0.82f, 0.3f);
            pos.y = Ground.Height(pos);
            var chest = Instantiate(cfg.chestModel);
            chest.name = "OpeningChest";
            var look = facing - pos;
            look.y = 0;
            chest.transform.SetPositionAndRotation(pos, look.sqrMagnitude > 0.01f ? Quaternion.LookRotation(look) : Quaternion.identity);
            Transform lid = null;
            foreach (var t in chest.GetComponentsInChildren<Transform>()) if (t.name == "Lid") lid = t;
            var lidRest = lid != null ? lid.localRotation : Quaternion.identity;
            var glow = AttachGlow(chest.transform, gold, 2.5f);
            if (lib != null) AudioManager.Play(lib.chest, pos, 0.9f);

            // 1) wobble and build up
            float t0 = 0f;
            while (t0 < 0.45f)
            {
                t0 += Time.deltaTime;
                float k = t0 / 0.45f;
                chest.transform.localScale = Vector3.one * 1.3f * (1f + Mathf.Sin(t0 * 40f) * 0.06f * k);
                chest.transform.rotation = Quaternion.LookRotation(look.sqrMagnitude > 0.01f ? look : Vector3.forward) * Quaternion.Euler(0, 0, Mathf.Sin(t0 * 35f) * 6f * k);
                if (Random.value < 0.4f) Burst(pos + Vector3.up * 0.6f, gold, 1, 2f, 0.12f, 0.4f, -1f, true);
                yield return null;
            }
            // 2) BANG: lid flies open, light, ring and loot
            chest.transform.localScale = Vector3.one * 1.3f;
            if (lib != null) AudioManager.Play(lib.treasure, pos, 1f);
            CameraRig.Instance?.Shake(0.2f);
            LightPillar(pos, gold, 14f, 1.2f);
            Shockwave(pos, 3f, gold, false);
            Burst(pos + Vector3.up * 0.9f, gold, 40, 10f, 0.25f, 0.9f, 5f, true);
            Burst(pos + Vector3.up * 0.9f, Color.white, 12, 6f, 0.35f, 0.3f, 0f, true);
            int n = 16;
            for (int i = 0; i < n && cfg.chestLoot != null && cfg.chestLoot.Length > 0; i++)
            {
                var model = cfg.chestLoot[i % 3 == 0 ? Random.Range(0, cfg.chestLoot.Length) : Random.Range(0, Mathf.Min(3, cfg.chestLoot.Length))];
                if (model == null) continue;
                var go = Instantiate(model);
                foreach (var r in go.GetComponentsInChildren<Renderer>()) r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                go.transform.position = pos + Vector3.up * 0.8f;
                go.transform.localScale = Vector3.one * Random.Range(0.55f, 0.85f);
                float a = Random.Range(0f, Mathf.PI * 2f);
                var v = new Vector3(Mathf.Cos(a), 0, Mathf.Sin(a)) * Random.Range(2.5f, 6f) + Vector3.up * Random.Range(7f, 11f);
                _loot.Add(new Loot { t = go.transform, vel = v, spin = Random.insideUnitSphere * 720f, life = Random.Range(1.6f, 2.4f) });
            }
            float t1 = 0f;
            while (t1 < 0.3f)
            {
                t1 += Time.deltaTime;
                if (lid != null) lid.localRotation = lidRest * Quaternion.Euler(-115f * Mathf.Clamp01(t1 / 0.18f) + Mathf.Sin(t1 * 30f) * 8f * (1f - t1 / 0.3f), 0, 0);
                yield return null;
            }
            // 3) glow a while, then sink away
            yield return new WaitForSeconds(2.4f);
            float t2 = 0f;
            while (t2 < 0.5f)
            {
                t2 += Time.deltaTime;
                chest.transform.localScale = Vector3.one * 1.3f * (1f - t2 / 0.5f);
                yield return null;
            }
            if (glow != null) Destroy(glow.gameObject);
            Destroy(chest);
        }

        void UpdateLoot(float dt)
        {
            var lib = AudioManager.Lib;
            for (int i = _loot.Count - 1; i >= 0; i--)
            {
                var l = _loot[i];
                if (l.t == null) { _loot.RemoveAt(i); continue; }
                l.age += dt;
                l.vel += Vector3.down * 22f * dt;
                var p = l.t.position + l.vel * dt;
                float g = Ground.Height(p) + 0.15f;
                if (p.y < g)
                {
                    p.y = g;
                    if (l.vel.y < -2f && lib != null && !l.landed) AudioManager.Play(lib.gem, p, 0.25f, Random.Range(1.1f, 1.6f), 0.05f);
                    l.landed = true;
                    l.vel = new Vector3(l.vel.x * 0.55f, -l.vel.y * 0.4f, l.vel.z * 0.55f);   // bounce
                    l.spin *= 0.6f;
                }
                l.t.position = p;
                l.t.Rotate(l.spin * dt, Space.World);
                if (l.age > l.life)
                {
                    float k = (l.age - l.life) / 0.3f;
                    l.t.localScale *= Mathf.Max(0f, 1f - k * 0.5f);
                    if (k >= 1f)
                    {
                        SpawnParticle(p + Vector3.up * 0.2f, Vector3.up, new Color(1f, 0.85f, 0.4f), 0.3f, 0.3f, 0f, 1f, true, sparkTexture);
                        Destroy(l.t.gameObject);
                        _loot.RemoveAt(i);
                    }
                }
            }
        }

        /// <summary>Frost Nova with extra rings: each one wider, a beat later (matches the host's delayed blasts).</summary>
        public void NovaRings(Vector3 center, float radius, int rings, Color color)
        {
            Nova(center, radius, color);
            if (rings > 1) StartCoroutine(NovaLater(center, radius, rings, color));
        }

        System.Collections.IEnumerator NovaLater(Vector3 center, float radius, int rings, Color color)
        {
            for (int k = 1; k < rings; k++)
            {
                yield return new WaitForSeconds(0.2f);
                Nova(center, radius * (1f + 0.4f * k), Color.Lerp(color, Color.white, 0.25f * k));
            }
        }

        /// <summary>Critical hit flair: a golden star burst (bigger with Brutality's big crits).</summary>
        float _critBudget = 20f, _critTime;

        public void CritBurst(Vector3 pos, float power)
        {
            float now = Time.unscaledTime;
            _critBudget = Mathf.Min(20f, _critBudget + (now - _critTime) * 25f);
            _critTime = now;
            if (_critBudget < 1f) return;
            _critBudget -= 1f;
            Burst(pos, new Color(1f, 0.85f, 0.25f), Mathf.RoundToInt(4 + 3 * power), 6f + 2f * power, 0.14f, 0.28f, 0f, true);
        }

        /// <summary>Execution: a red skull flash where an enemy was finished off.</summary>
        public void ExecuteBurst(Vector3 pos)
        {
            LightPillar(pos, new Color(1f, 0.2f, 0.15f), 4f, 0.4f);
            Burst(pos + Vector3.up * 1f, new Color(1f, 0.25f, 0.2f), 14, 6f, 0.2f, 0.45f, 2f, true);
        }

        public void Nova(Vector3 center, float radius, Color color)
        {
            var ring = CreateGroundDecal("Nova", ringTexture, true);
            ring.position = new Vector3(center.x, Ground.Height(center) + 0.1f, center.z);
            AddTimed(ring, 0.45f, color, Vector3.one * radius * 2.3f, true, true);
            var ring2 = CreateGroundDecal("Nova2", ringTexture, true);
            ring2.position = ring.position + Vector3.up * 0.05f;
            AddTimed(ring2, 0.3f, Color.white, Vector3.one * radius * 1.6f, true, true);
            for (int i = 0; i < 22; i++)
            {
                float a = i / 22f * Mathf.PI * 2f;
                var d = new Vector3(Mathf.Cos(a), 0.15f, Mathf.Sin(a));
                SpawnParticle(center + Vector3.up * 0.6f, d * radius * 2.2f, color, Random.Range(0.25f, 0.45f), 0.45f, 0f, 2.5f, true, sparkTexture);
            }
        }

        /// <summary>Warning circle on the ground that fills up until the attack lands.</summary>
        public void Telegraph(Vector3 pos, float radius, float time, Color color)
        {
            var outer = CreateGroundDecal("Telegraph", ringTexture, true);
            outer.position = new Vector3(pos.x, Ground.Height(pos) + 0.07f, pos.z);
            var c = color;
            c.a = 0.9f;
            _timed.Add(new Timed { t = outer, r = outer.GetComponent<Renderer>(), life = time, color = c, baseScale = Vector3.one * radius * 2.3f, fadeIn = 0.1f, holdAlpha = true });
            outer.localScale = Vector3.one * radius * 2.3f;
            var fill = CreateGroundDecal("TelegraphFill", softTexture, false);
            fill.position = outer.position + Vector3.up * 0.01f;
            var fc = color;
            fc.a = 0.35f;
            _timed.Add(new Timed { t = fill, r = fill.GetComponent<Renderer>(), life = time, color = fc, baseScale = Vector3.one * radius * 2.6f, grow = true, holdAlpha = true });
        }

        public void Shockwave(Vector3 pos, float radius, Color color, bool explosion)
        {
            var ring = CreateGroundDecal("Shockwave", ringTexture, true);
            ring.position = new Vector3(pos.x, Ground.Height(pos) + 0.1f, pos.z);
            AddTimed(ring, 0.4f, color, Vector3.one * radius * 2.4f, true, true);
            Burst(pos + Vector3.up * 0.5f, explosion ? new Color(1f, 0.6f, 0.2f) : color, explosion ? 26 : 14, explosion ? 11f : 7f, 0.5f, 0.5f, 6f, true);
            Burst(pos + Vector3.up * 0.3f, Color.white, explosion ? 6 : 3, 4f, 0.9f, 0.18f, 0f, true);
            for (int i = 0; i < (explosion ? 10 : 6); i++)
            {
                var v = new Vector3(Random.Range(-1f, 1f), Random.Range(0.8f, 1.6f), Random.Range(-1f, 1f)) * radius * 1.6f;
                SpawnParticle(pos + Vector3.up * 0.3f, v, explosion ? new Color(0.35f, 0.3f, 0.28f) : new Color(0.5f, 0.42f, 0.32f), Random.Range(0.18f, 0.32f), 1.2f, 16f, 0.6f, false, null);
            }
            for (int i = 0; i < 6; i++)
                SpawnParticle(pos + Vector3.up * 0.4f, new Vector3(Random.Range(-3f, 3f), Random.Range(0.5f, 2f), Random.Range(-3f, 3f)),
                    new Color(0.8f, 0.78f, 0.72f, 0.6f), Random.Range(1f, 1.8f), 0.8f, -0.5f, 2f, false, softTexture);
        }

        public void Lightning(Vector3 a, Vector3 b, Color color)
        {
            // jagged path shared by a wide colored glow and a thin white core
            const int segs = 9;
            var pts = new Vector3[segs + 1];
            var dir = (b - a);
            var side = Vector3.Cross(dir.sqrMagnitude > 0.0001f ? dir.normalized : Vector3.forward, Vector3.up);
            if (side.sqrMagnitude < 0.01f) side = Vector3.right;
            for (int i = 0; i <= segs; i++)
            {
                float f = i / (float)segs;
                var p = Vector3.Lerp(a, b, f);
                if (i > 0 && i < segs)
                    p += side * Random.Range(-0.5f, 0.5f) + Vector3.up * Random.Range(-0.4f, 0.4f);
                pts[i] = p;
            }
            AddBolt(pts, color, 0.55f, 0.22f);
            AddBolt(pts, Color.white, 0.16f, 0.16f);
            Burst(b, color, 6, 6f, 0.35f, 0.3f, 4f, true);
            Burst(b, Color.white, 3, 3f, 0.6f, 0.12f, 0f, true);
        }

        /// <summary>Bolt from the sky onto a point (first hit of a lightning cast).</summary>
        public void SkyStrike(Vector3 pos, Color color)
        {
            Lightning(pos + new Vector3(Random.Range(-1f, 1f), 14f, Random.Range(-1f, 1f)), pos, color);
            var ring = CreateGroundDecal("StrikeRing", ringTexture, true);
            ring.position = new Vector3(pos.x, Ground.Height(pos) + 0.08f, pos.z);
            AddTimed(ring, 0.35f, color, Vector3.one * 3f, true, true);
        }

        void AddBolt(Vector3[] pts, Color color, float width, float life)
        {
            var lr = _linePool.Count > 0 ? _linePool.Pop() : CreateLine();
            lr.gameObject.SetActive(true);
            lr.positionCount = pts.Length;
            lr.SetPositions(pts);
            lr.widthMultiplier = width;
            _timed.Add(new Timed { t = lr.transform, line = lr, life = life, color = color, isLine = true, baseScale = Vector3.one * width });
        }

        public void Flask(Vector3 from, Vector3 to, float flightTime, float radius, float duration, WeaponDefinition def)
        {
            var t = GetModel(def != null ? def.projectileModel : null);
            t.position = from;
            t.localScale = Vector3.one * 1.4f;
            _flights.Add(new Flight { t = t, from = from, to = to, duration = flightTime, radius = radius, puddleLife = duration, def = def });
        }

        public void AttachTrail(Transform target, Color color, float width)
        {
            var tr = target.gameObject.AddComponent<TrailRenderer>();
            tr.material = additive;
            tr.time = 0.18f;
            tr.minVertexDistance = 0.1f;
            tr.widthMultiplier = width;
            tr.startColor = color;
            tr.endColor = new Color(color.r, color.g, color.b, 0f);
            tr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
        }

        /// <summary>Soft additive glow that follows `parent` and faces the camera. Returns its renderer.</summary>
        public Renderer AttachGlow(Transform parent, Color color, float size)
        {
            var go = new GameObject("Glow", typeof(MeshFilter), typeof(MeshRenderer), typeof(Billboard));
            go.transform.SetParent(parent, false);
            go.transform.localScale = Vector3.one * size;
            go.GetComponent<MeshFilter>().sharedMesh = _quad;
            var r = go.GetComponent<MeshRenderer>();
            r.sharedMaterial = additive;
            r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            r.receiveShadows = false;
            SetColor(r, color);
            return r;
        }

        public void SetColor(Renderer r, Color c)
        {
            r.GetPropertyBlock(_mpb);
            _mpb.SetTexture("_MainTex", softTexture);
            _mpb.SetColor(ColorId, c);
            r.SetPropertyBlock(_mpb);
        }

        /// <summary>A flat quad lying on the ground (for rings and puddles). Caller owns it.</summary>
        public Transform CreateGroundDecal(string name, Texture tex, bool additiveBlend)
        {
            var go = new GameObject(name, typeof(MeshFilter), typeof(MeshRenderer));
            go.GetComponent<MeshFilter>().sharedMesh = _quad;
            var r = go.GetComponent<MeshRenderer>();
            r.sharedMaterial = additiveBlend ? additive : alpha;
            r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            r.receiveShadows = false;
            var mpb = new MaterialPropertyBlock();
            if (tex != null) mpb.SetTexture("_MainTex", tex);
            mpb.SetColor(ColorId, Color.white);
            r.SetPropertyBlock(mpb);
            go.transform.rotation = Quaternion.Euler(90f, 0f, 0f);
            return go.transform;
        }

        // ================================================================= internals

        Transform GetQuad(bool additiveBlend, Texture tex)
        {
            var pool = additiveBlend ? _additivePool : _alphaPool;
            Transform t;
            if (pool.Count > 0) t = pool.Pop();
            else
            {
                var go = new GameObject("Fx", typeof(MeshFilter), typeof(MeshRenderer));
                go.transform.SetParent(transform, false);
                go.GetComponent<MeshFilter>().sharedMesh = _quad;
                var r = go.GetComponent<MeshRenderer>();
                r.sharedMaterial = additiveBlend ? additive : alpha;
                r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                r.receiveShadows = false;
                t = go.transform;
            }
            t.gameObject.SetActive(true);
            var rr = t.GetComponent<Renderer>();
            rr.GetPropertyBlock(_mpb);
            if (tex != null) _mpb.SetTexture("_MainTex", tex);
            rr.SetPropertyBlock(_mpb);
            return t;
        }

        void ReleaseQuad(Transform t, bool additiveBlend)
        {
            t.gameObject.SetActive(false);
            (additiveBlend ? _additivePool : _alphaPool).Push(t);
        }

        // Particles go through three pooled ParticleSystems (one draw call each, simulated natively):
        //  sparks = additive glows, chunks = falling debris, dust = floating puffs.
        ParticleSystem _sparks, _chunks, _dust;

        ParticleSystem MakeSystem(string name, Material baseMat, Texture tex, float gravity, float drag)
        {
            var go = new GameObject(name);
            go.transform.SetParent(transform, false);
            var ps = go.AddComponent<ParticleSystem>();
            ps.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            var main = ps.main;
            main.playOnAwake = false;
            main.loop = true;
            main.maxParticles = 3000;
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            main.gravityModifier = gravity / 9.81f;
            var emission = ps.emission;
            emission.enabled = false;
            var shape = ps.shape;
            shape.enabled = false;
            var col = ps.colorOverLifetime;
            col.enabled = true;
            var g = new Gradient();
            g.SetKeys(new[] { new GradientColorKey(Color.white, 0f), new GradientColorKey(Color.white, 1f) },
                new[] { new GradientAlphaKey(1f, 0f), new GradientAlphaKey(1f, 0.5f), new GradientAlphaKey(0f, 1f) });
            col.color = g;
            var size = ps.sizeOverLifetime;
            size.enabled = true;
            size.size = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.Linear(0f, 1f, 1f, 0.3f));
            var limit = ps.limitVelocityOverLifetime;
            limit.enabled = true;
            limit.drag = drag;
            limit.limit = 100f;
            var r = go.GetComponent<ParticleSystemRenderer>();
            r.renderMode = ParticleSystemRenderMode.Billboard;
            r.sharedMaterial = new Material(baseMat) { mainTexture = tex };
            r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            r.receiveShadows = false;
            ps.Play();
            return ps;
        }

        void EnsureSystems()
        {
            if (_sparks != null) return;
            _sparks = MakeSystem("Sparks", additive, sparkTexture, 3f, 1.5f);
            _chunks = MakeSystem("Chunks", alpha, null, 16f, 0.6f);
            _dust = MakeSystem("Dust", alpha, softTexture, -0.5f, 2f);
            // chunks are tumbling little cubes (pixel debris like the reference)
            var r = _chunks.GetComponent<ParticleSystemRenderer>();
            var cube = GameObject.CreatePrimitive(PrimitiveType.Cube);
            r.renderMode = ParticleSystemRenderMode.Mesh;
            r.mesh = cube.GetComponent<MeshFilter>().sharedMesh;
            Destroy(cube);
            r.sharedMaterial = new Material(alpha) { mainTexture = Texture2D.whiteTexture };
            var main = _chunks.main;
            main.startRotation3D = true;
            var rot = _chunks.rotationOverLifetime;
            rot.enabled = true;
            rot.separateAxes = true;
            rot.x = new ParticleSystem.MinMaxCurve(-8f, 8f);
            rot.y = new ParticleSystem.MinMaxCurve(-8f, 8f);
            rot.z = new ParticleSystem.MinMaxCurve(-8f, 8f);
            var size = _chunks.sizeOverLifetime;
            size.size = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.Linear(0f, 1f, 1f, 0.6f));
            var col = _chunks.colorOverLifetime;
            var g = new Gradient();
            g.SetKeys(new[] { new GradientColorKey(Color.white, 0f), new GradientColorKey(Color.white, 1f) },
                new[] { new GradientAlphaKey(1f, 0f), new GradientAlphaKey(1f, 0.75f), new GradientAlphaKey(0f, 1f) });
            col.color = g;
            // collide with the ground so debris bounces and settles
            var c = _chunks.collision;
            c.enabled = true;
            c.type = ParticleSystemCollisionType.World;
            c.mode = ParticleSystemCollisionMode.Collision3D;
            c.quality = ParticleSystemCollisionQuality.Low;
            c.collidesWith = LayerMask.GetMask("Environment");
            c.bounce = 0.35f;
            c.dampen = 0.4f;
            c.lifetimeLoss = 0f;
            BuildAmbient();
        }

        // ---------------------------------------------------------------- ambient motes drifting around the camera
        ParticleSystem _ambient;

        void BuildAmbient()
        {
            _ambient = MakeSystem("AmbientMotes", additive, softTexture, -ambientRise, 0.2f);
            var main = _ambient.main;
            main.maxParticles = 300;
            main.startLifetime = new ParticleSystem.MinMaxCurve(5f, 9f);
            main.startSize = new ParticleSystem.MinMaxCurve(0.08f, 0.18f);
            main.startSpeed = new ParticleSystem.MinMaxCurve(0.1f, 0.5f);
            main.startColor = new ParticleSystem.MinMaxGradient(ambientColorA, ambientColorB);
            var em = _ambient.emission;
            em.enabled = true;
            em.rateOverTime = ambientRate;
            var shape = _ambient.shape;
            shape.enabled = true;
            shape.shapeType = ParticleSystemShapeType.Box;
            shape.scale = new Vector3(50f, 8f, 50f);
            var noise = _ambient.noise;
            noise.enabled = true;
            noise.strength = 0.4f;
            noise.frequency = 0.3f;
            var col = _ambient.colorOverLifetime;
            var g = new Gradient();
            g.SetKeys(new[] { new GradientColorKey(Color.white, 0f), new GradientColorKey(Color.white, 1f) },
                new[] { new GradientAlphaKey(0f, 0f), new GradientAlphaKey(1f, 0.3f), new GradientAlphaKey(1f, 0.7f), new GradientAlphaKey(0f, 1f) });
            col.color = g;
            var size = _ambient.sizeOverLifetime;
            size.enabled = false;
            _ambient.Play();
        }

        void SpawnParticle(Vector3 pos, Vector3 vel, Color color, float size, float life, float gravity, float drag, bool additiveBlend, Texture tex)
        {
            EnsureSystems();
            var ps = additiveBlend ? _sparks : gravity > 0f ? _chunks : _dust;
            var ep = new ParticleSystem.EmitParams
            {
                position = pos,
                velocity = vel,
                startColor = color,
                startSize = size,
                startLifetime = life,
                applyShapeToPosition = false,
            };
            ps.Emit(ep, 1);
        }

        void AddTimed(Transform t, float life, Color color, Vector3 scale, bool grow, bool additiveBlend)
        {
            t.localScale = scale;
            _timed.Add(new Timed
            {
                t = t, r = t.GetComponent<Renderer>(), life = life, color = color, baseScale = scale, grow = grow,
                additivePool = additiveBlend,
            });
        }

        LineRenderer CreateLine()
        {
            var go = new GameObject("Bolt");
            go.transform.SetParent(transform, false);
            var lr = go.AddComponent<LineRenderer>();
            lr.material = additive;
            lr.textureMode = LineTextureMode.Stretch;
            lr.numCapVertices = 2;
            lr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            lr.receiveShadows = false;
            return lr;
        }

        Transform GetModel(GameObject prefab)
        {
            if (prefab == null)
            {
                var q = GetQuad(true, sparkTexture);
                q.localScale = Vector3.one * 0.6f;
                return q;
            }
            if (!_modelPools.TryGetValue(prefab, out var pool)) _modelPools[prefab] = pool = new Stack<Transform>();
            Transform t;
            if (pool.Count > 0) t = pool.Pop();
            else
            {
                t = Instantiate(prefab, transform).transform;
                t.gameObject.AddComponent<PooledModel>().prefab = prefab;
                foreach (var r in t.GetComponentsInChildren<Renderer>()) r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                AttachTrail(t, new Color(1f, 1f, 1f, 0.7f), 0.14f);
            }
            t.gameObject.SetActive(true);
            var trail = t.GetComponent<TrailRenderer>();
            if (trail != null) trail.Clear();
            return t;
        }

        void ReleaseModel(Transform t)
        {
            var pm = t.GetComponent<PooledModel>();
            if (pm == null)
            {
                ReleaseQuad(t, true);
                return;
            }
            t.gameObject.SetActive(false);
            _modelPools[pm.prefab].Push(t);
        }

        class PooledModel : MonoBehaviour
        {
            public GameObject prefab;
        }

        void LateUpdate()
        {
            if (_loot.Count > 0) UpdateLoot(Time.deltaTime);
            PerfStats.Fx.Start();
            try { Tick(); }
            finally { PerfStats.Fx.Stop(); }
        }

        void Start() => EnsureSystems();

        void Tick()
        {
            float dt = Time.deltaTime;
            var cam = Cam;
            if (_ambient != null && cam != null)
                _ambient.transform.position = cam.transform.position + cam.transform.forward * 14f + Vector3.up * 1f;
            var camRot = cam != null ? cam.transform.rotation : Quaternion.identity;

            // slashes, rings, decals, bolts
            for (int i = _timed.Count - 1; i >= 0; i--)
            {
                var t = _timed[i];
                t.age += dt;
                float f = Mathf.Clamp01(t.age / t.life);
                if (f >= 1f)
                {
                    if (t.isLine)
                    {
                        t.line.gameObject.SetActive(false);
                        _linePool.Push(t.line);
                    }
                    else if (t.t.parent == transform) ReleaseQuad(t.t, t.additivePool);
                    else Destroy(t.t.gameObject);
                    _timed.RemoveAt(i);
                    continue;
                }
                var c = t.color;
                float fadeIn = t.fadeIn > 0f ? Mathf.Clamp01(t.age / t.fadeIn) : 1f;
                c.a *= (t.holdAlpha ? (f < 0.85f ? 1f : (1f - f) / 0.15f) * (0.75f + 0.25f * Mathf.Sin(t.age * 25f)) : 1f - f * f) * fadeIn;
                if (t.isLine)
                {
                    t.line.startColor = c;
                    t.line.endColor = c;
                    t.line.widthMultiplier = t.baseScale.x * (1f - f * 0.6f);
                }
                else
                {
                    if (t.grow) t.t.localScale = t.baseScale * (0.2f + f);
                    if (t.billboardY && cam != null)
                    {
                        var fwd = cam.transform.forward;
                        fwd.y = 0;
                        if (fwd.sqrMagnitude > 0.001f) t.t.rotation = Quaternion.LookRotation(fwd);
                        t.t.localScale = new Vector3(t.baseScale.x * (1f - f * 0.7f), t.baseScale.y, 1f);
                    }
                    t.r.GetPropertyBlock(_mpb);
                    _mpb.SetColor(ColorId, c);
                    t.r.SetPropertyBlock(_mpb);
                }
            }

            // cosmetic projectiles
            for (int i = _shots.Count - 1; i >= 0; i--)
            {
                var s = _shots[i];
                s.life -= dt;
                s.age += dt;
                if (s.returnTo != null && s.age >= s.outTime)
                {
                    // boomerang: after the out-flight it homes back to the thrower (and can hit everything again)
                    if (!s.returning) { s.returning = true; s.hit.Clear(); }
                    var back = s.returnTo.position + Vector3.up * 1f - s.t.position;
                    s.vel = back.normalized * s.vel.magnitude * 1.15f;
                    if (back.sqrMagnitude < 1.2f || s.age > s.outTime * 4f) s.life = 0f;
                }
                else if (s.turn > 0f)
                {
                    // homing: steer toward the nearest enemy
                    var target = EnemyRegistry.Nearest(s.t.position, 18f, s.hit);
                    if (target != null)
                    {
                        var want = (target.transform.position + Vector3.up * 0.8f * target.ScaleMul - s.t.position).normalized * s.vel.magnitude;
                        s.vel = Vector3.RotateTowards(s.vel, want, s.turn * Mathf.Deg2Rad * dt, 0f);
                    }
                }
                s.t.position += s.vel * dt;
                if (s.spin > 0f) s.t.Rotate(0f, s.spin * dt, 0f, Space.World);
                else if (s.vel.sqrMagnitude > 0.01f && !s.hostile) s.t.rotation = Quaternion.LookRotation(s.vel);
                if (s.hostile && cam != null) s.t.rotation = cam.transform.rotation;
                bool done = s.life <= 0f;
                if (!done && !s.hostile)
                {
                    foreach (var e in EnemyRegistry.All)
                    {
                        if (e == null || !e.IsAlive || s.hit.Contains(e)) continue;
                        var d = e.transform.position + Vector3.up * 0.8f * e.ScaleMul - s.t.position;
                        float r = e.Radius + 0.4f;
                        if (d.x * d.x + d.z * d.z < r * r && Mathf.Abs(d.y) < 1.5f * e.ScaleMul)
                        {
                            s.hit.Add(e);
                            s.pierceLeft--;
                            if (s.def != null) Burst(s.t.position, s.def.fxColor, 3, 3f, 0.25f, 0.2f, 0f, true);
                            if (s.pierceLeft <= 0) { done = true; break; }
                        }
                    }
                }
                if (done)
                {
                    ReleaseModel(s.t);
                    _shots.RemoveAt(i);
                }
            }

            // thrown flasks
            for (int i = _flights.Count - 1; i >= 0; i--)
            {
                var fl = _flights[i];
                fl.time += dt;
                float f = Mathf.Clamp01(fl.time / fl.duration);
                var p = Vector3.Lerp(fl.from, fl.to, fl.meteor ? f * f : f);
                if (!fl.meteor) p.y += Mathf.Sin(f * Mathf.PI) * 3f;
                fl.t.position = p;
                fl.t.Rotate(400f * dt, 250f * dt, 0f);
                if (fl.meteor && Random.value < 0.6f)
                    SpawnParticle(p, Random.insideUnitSphere * 1.5f, new Color(1f, 0.55f, 0.2f), Random.Range(0.4f, 0.7f), 0.35f, -1f, 1f, true, softTexture);
                if (f >= 1f && fl.meteor)
                {
                    ReleaseModel(fl.t);
                    _flights.RemoveAt(i);
                    Shockwave(fl.to, fl.radius, new Color(1f, 0.55f, 0.2f), true);
                    AudioManager.Play(fl.def != null ? fl.def.hitSound : null, fl.to, 0.9f);
                    var me = PlayerCharacter.Local;
                    if (me != null && (me.transform.position - fl.to).sqrMagnitude < 400f) CameraRig.Instance?.Shake(0.22f);
                    continue;
                }
                if (f >= 1f)
                {
                    ReleaseModel(fl.t);
                    _flights.RemoveAt(i);
                    var col = fl.def != null ? fl.def.fxColor : Color.green;
                    Burst(fl.to, col, 12, 6f, 0.3f, 0.5f, 12f, false);
                    var puddle = CreateGroundDecal("Puddle", puddleTexture, false);
                    puddle.position = fl.to + Vector3.up * 0.03f;
                    puddle.Rotate(0, 0, Random.Range(0f, 360f), Space.Self);
                    var timed = new Timed
                    {
                        t = puddle, r = puddle.GetComponent<Renderer>(), life = fl.puddleLife, fadeIn = 0.15f,
                        color = new Color(col.r * 0.55f, col.g * 0.7f, col.b * 0.45f, 0.32f), baseScale = Vector3.one * fl.radius * 2.2f,
                    };
                    puddle.localScale = timed.baseScale;
                    _timed.Add(timed);
                    AudioManager.Play(fl.def != null && fl.def.hitSound != null ? fl.def.hitSound : flaskShatter, fl.to, 0.6f);
                }
            }

            // damage numbers
            if (cam != null)
            {
                for (int i = _numbers.Count - 1; i >= 0; i--)
                {
                    var n = _numbers[i];
                    n.age += dt;
                    const float life = 0.75f;
                    if (n.age >= life)
                    {
                        n.text.gameObject.SetActive(false);
                        _numberPool.Push(n.text);
                        _numbers.RemoveAt(i);
                        continue;
                    }
                    var w = n.world + Vector3.up * (n.age * 1.6f);
                    var sp = cam.WorldToScreenPoint(w);
                    if (sp.z < 0f) { n.text.enabled = false; continue; }
                    n.text.enabled = true;
                    n.text.rectTransform.position = sp;
                    float pop = n.age < 0.1f ? Mathf.Lerp(1.6f, 1f, n.age / 0.1f) : 1f;
                    n.text.rectTransform.localScale = Vector3.one * n.scale * pop;
                    var c = n.text.color;
                    c.a = 1f - Mathf.Clamp01((n.age - life * 0.6f) / (life * 0.4f));
                    n.text.color = c;
                }
            }
        }
    }
}
