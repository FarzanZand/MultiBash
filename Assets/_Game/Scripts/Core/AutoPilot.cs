using System.Text;
using UnityEngine;
using UnityEngine.InputSystem;

namespace MultiBash
{
    /// <summary>
    /// Developer playtest bot + telemetry. Press F8 in game (or start with -autopilot) to let the bot play:
    /// it kites away from the swarm, grabs XP, revives friends and picks upgrades.
    /// Every 15 seconds a telemetry line is logged so balance can be checked over a whole run.
    /// </summary>
    public class AutoPilot : MonoBehaviour
    {
        public static bool Enabled;
        public static readonly StringBuilder Telemetry = new();

        float _choiceDelay, _nextLog, _wander;
        Vector3 _wanderDir = Vector3.forward;
        static float _jumpCooldown;

        void Awake()
        {
            foreach (var a in System.Environment.GetCommandLineArgs())
                if (a == "-autopilot") Enabled = true;
        }

        void Update()
        {
            PerfStats.Frames++;
            var kb = Keyboard.current;
            bool dev = Application.isEditor || Debug.isDebugBuild;
            if (dev && kb != null && kb.f8Key.wasPressedThisFrame) Enabled = !Enabled;
            if (dev && kb != null && kb.f9Key.wasPressedThisFrame) SkipTime(60f);

            var gm = GameManager.Instance;
            if (gm != null && gm.Object != null && gm.Object.IsValid && Time.time >= _nextLog)
            {
                _nextLog = Time.time + 15f;
                LogTelemetry(gm);
            }

            if (!Enabled) return;
            var me = PlayerCharacter.Local;
            if (me == null || me.Object == null || !me.Object.IsValid) return;
            if (me.PendingLevelUps > 0 && me.Choices.Get(0) != 0)
            {
                _choiceDelay += Time.deltaTime;
                if (_choiceDelay > 0.6f)
                {
                    _choiceDelay = 0f;
                    me.Rpc_Choose(PickChoice(me));
                }
            }
        }

        /// <summary>Bot upgrade pick like a sensible player: evolve > new weapon > weapon level > anything.</summary>
        static int PickChoice(PlayerCharacter me)
        {
            int best = Random.Range(0, 3), score = -1;
            for (int i = 0; i < me.Choices.Length; i++)
            {
                short c = me.Choices.Get(i);
                if (c == 0) continue;
                int sc = UpgradeSystem.IsEvolution(c) ? 4
                    : UpgradeSystem.IsWeapon(c) && me.WeaponLevelOf(UpgradeSystem.WeaponIndex(c)) == 0 ? 3
                    : UpgradeSystem.IsWeapon(c) ? 2 : 1;
                sc = sc * 10 + Random.Range(0, 5);
                if (sc > score) { score = sc; best = i; }
            }
            return best;
        }

        /// <summary>Dev cheat (host only, F9): jump the run timer forward to test later waves and bosses.</summary>
        public static void SkipTime(float seconds)
        {
            var gm = GameManager.Instance;
            if (gm == null || gm.Object == null || !gm.Object.HasStateAuthority || gm.State != RunState.Playing) return;
            gm.RunTime = Mathf.Min(gm.RunTime + seconds, ProgressionManager.Settings.runDurationSeconds - 1f);
        }

        void LogTelemetry(GameManager gm)
        {
            var me = PlayerCharacter.Local;
            string line = $"t={gm.RunTime:0} state={gm.State} lvl={gm.TeamLevel} xp={gm.TeamXP}/{gm.XPToNext} enemies={EnemyRegistry.All.Count} gems={Pickup.All.Count} kills={gm.TotalKills} fps={1f / Mathf.Max(0.0001f, Time.smoothDeltaTime):0}";
            if (me != null && me.Object != null && me.Object.IsValid)
                line += $" hp={me.Health:0}/{me.MaxHealth:0} downed={me.Downed} weapons={me.WeaponCount} powerups={me.PowerupCount} dmgHits={PlayerCharacter.DamageFromHits:0} dmgLava={PlayerCharacter.DamageFromLava:0} hitsPerKill={(Enemy.RegularKills > 0 ? Enemy.RegularHits / (float)Enemy.RegularKills : 0):0.00}";
                Enemy.RegularHits = 0; Enemy.RegularKills = 0;
            line += " | " + PerfStats.Report();
            Telemetry.AppendLine(line);
            Debug.Log("[Telemetry] " + line);
        }

        /// <summary>Called by LocalInput: returns a world-space move direction for the bot.</summary>
        public static Vector2 Steer(out bool jump, out bool slide)
        {
            jump = slide = false;
            var me = PlayerCharacter.Local;
            if (me == null || me.Object == null || !me.Object.IsValid) return Vector2.zero;
            var pos = me.transform.position;
            Vector3 flee = Vector3.zero;
            float closest = 99f;
            Enemy nearest = null;
            int crowd = 0;
            foreach (var e in EnemyRegistry.All)
            {
                if (e == null || !e.IsAlive) continue;
                var d = pos - e.transform.position;
                d.y = 0;
                float m = d.magnitude;
                if (m < closest) { closest = m; nearest = e; }
                if (m < 3f) crowd++;
                if (m < 6f) flee += d.normalized / Mathf.Max(0.5f, m * m) * (e.Elite ? 3f : 1f);
            }
            // a real player engages at their weapon's range and only kites when it gets crowded or health is low
            bool melee = me.Def != null && me.Def.startingWeapon != null && me.Def.startingWeapon.kind == WeaponKind.MeleeArc;
            float engage = melee ? 2.2f : 7f;
            bool danger = crowd >= (melee ? 4 : 2) || me.Health < me.MaxHealth * 0.5f;
            if (!danger) flee *= 0.15f;
            Vector3 attack = Vector3.zero;
            if (!danger && nearest != null && closest > engage)
                attack = (nearest.transform.position - pos).normalized;

            Vector3 want = Vector3.zero;
            // revive downed friends (a good teammate takes some risk for this)
            foreach (var p in PlayerCharacter.All)
                if (p != null && p != me && p.Downed)
                {
                    want += (p.transform.position - pos).normalized * 3f;
                    flee *= 0.3f;
                }

            // grab gems when it's safe enough
            Pickup best = null;
            float bestD = 14f;
            foreach (var g in Pickup.All)
            {
                if (g == null || g.Target.IsValid) continue;
                float d = (g.transform.position - pos).magnitude;
                if (d < bestD) { bestD = d; best = g; }
            }
            if (best != null) want += (best.transform.position - pos).normalized * (closest > 3f ? 1.2f : 0.4f);

            // stay away from walls
            float half = GameDatabase.Config.arenaHalfSize - 8f;
            if (Mathf.Abs(pos.x) > half || Mathf.Abs(pos.z) > half) want += -pos.normalized * 1.5f;

            var dir = flee * 6f + want + attack;
            if (dir.sqrMagnitude < 0.05f)
            {
                // circle-strafe when idle
                dir = Quaternion.Euler(0, Time.time * 20f, 0) * Vector3.forward;
            }
            // orbit around the swarm instead of running straight (feels like a real kiting player)
            dir += Vector3.Cross(Vector3.up, flee.normalized) * 0.35f;
            dir.y = 0;
            dir.Normalize();

            // don't walk into lava: pick the closest safe heading (and hop out if already burning)
            if (!float.IsNaN(LavaZone.Level))
            {
                bool Hot(Vector3 p) => Ground.TerrainHeight(p) < LavaZone.Level + 0.25f;
                bool burning = LavaZone.InLava(pos);
                if (burning || Hot(pos + dir * 2f) || Hot(pos + dir * 4f))
                {
                    Vector3 bestDir = dir;
                    float bestScore = float.MinValue;
                    for (int i = 0; i < 16; i++)
                    {
                        var d = Quaternion.Euler(0, i * 22.5f, 0) * Vector3.forward;
                        int dry = 0;
                        for (int k = 1; k <= 3; k++) if (!Hot(pos + d * (k * 1.6f))) dry++;
                        float score = dry * 2f + Vector3.Dot(d, dir) - (burning ? 0f : (dry < 3 ? 10f : 0f));
                        if (score > bestScore) { bestScore = score; bestDir = d; }
                    }
                    dir = bestDir;
                    if (burning && _jumpCooldown <= 0f) { jump = true; _jumpCooldown = 0.6f; }
                }
            }

            _jumpCooldown -= Time.deltaTime;
            if (closest < 1.6f && _jumpCooldown <= 0f)
            {
                slide = true;
                jump = Random.value < 0.5f;
                _jumpCooldown = 1f;
            }
            return new Vector2(dir.x, dir.z);
        }
    }
}
