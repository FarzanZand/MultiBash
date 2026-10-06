using System.Collections.Generic;
using Fusion;
using UnityEngine;

namespace MultiBash
{
    public enum RunState : byte
    {
        Starting,
        Playing,
        Victory,
        Defeat,
    }

    /// <summary>
    /// Owns a run: spawns heroes, the timer, team XP / levels, enemy spawning, drops and win/lose.
    /// Scene object in the Game scene. The host simulates; everyone reads the networked state.
    /// </summary>
    public class GameManager : NetworkBehaviour
    {
        public static GameManager Instance { get; private set; }

        [Networked] public RunState State { get; set; }
        [Networked] public float RunTime { get; set; }
        [Networked] public int TeamLevel { get; set; }
        [Networked] public int TeamXP { get; set; }
        [Networked] public int XPToNext { get; set; }
        [Networked] public int TotalKills { get; set; }
        [Networked] public TickTimer StateTimer { get; set; }
        [Networked] public NetworkString<_64> Announcement { get; set; }
        [Networked] public int AnnouncementTick { get; set; }

        [Tooltip("Which map this scene is (waves, music, difficulty). Set by the setup tool.")]
        public MapDefinition map;

        public WaveDefinition Waves => map != null && map.waves != null ? map.waves : GameDatabase.Config.waves;

        public float EnemySpeedMul => 1f + Mathf.Min(RunTime / 60f * GameDatabase.Config.speedPerMinute, 0.35f);
        public float TimeLeft => Mathf.Max(0f, GameDatabase.Config.runDurationSeconds - RunTime);
        public int AlivePlayerCount { get; private set; }

        EnemySpawner _spawner;
        float _xpRemainder;
        readonly HashSet<PlayerRef> _spawnedFor = new();

        // visuals
        int _lastLevel;
        RunState _lastState;
        int _lastAnnouncement;

        public override void Spawned()
        {
            Instance = this;
            _spawner = new EnemySpawner(this);
            CombatWorld.Clear();
            if (HasStateAuthority)
            {
                State = RunState.Starting;
                StateTimer = TickTimer.CreateFromSeconds(Runner, 3f);
                TeamLevel = 1;
                TeamXP = 0;
                XPToNext = GameDatabase.Config.XPForLevel(1, Mathf.Max(1, PlayerData.All.Count));
                foreach (var p in PlayerData.All) p.ResetRunStats();
                Announce("Survive the night!");
            }
            _lastLevel = TeamLevel;
            _lastState = State;
            _lastAnnouncement = AnnouncementTick;
            AudioManager.PlayMusic(map != null && map.music != null ? map.music : AudioManager.Lib != null ? AudioManager.Lib.battleMusic : null);
        }

        public override void Despawned(NetworkRunner runner, bool hasState)
        {
            if (Instance == this) Instance = null;
            CombatWorld.Clear();
        }

        public void Announce(string text)
        {
            if (!HasStateAuthority) return;
            Announcement = text;
            AnnouncementTick = Runner.Tick;
        }

        // ------------------------------------------------------------------ host simulation

        public override void FixedUpdateNetwork()
        {
            if (!HasStateAuthority) return;
            float dt = Runner.DeltaTime;
            var cfg = GameDatabase.Config;

            SpawnMissingCharacters();

            int alive = 0;
            foreach (var p in PlayerCharacter.All) if (p != null && p.IsAlive) alive++;
            AlivePlayerCount = alive;

            switch (State)
            {
                case RunState.Starting:
                    if (StateTimer.Expired(Runner))
                    {
                        State = RunState.Playing;
                        Announce("Here they come!");
                    }
                    break;

                case RunState.Playing:
                    RunTime += dt;
                    _spawner.Tick(dt);
                    CombatWorld.Tick(Runner.Tick, dt);
                    CheckDefeat();
                    if (RunTime >= cfg.runDurationSeconds) EndRun(true);
                    break;

                case RunState.Victory:
                case RunState.Defeat:
                    if (StateTimer.Expired(Runner))
                    {
                        StateTimer = TickTimer.None;
                        ReturnToLobbyNow();
                    }
                    break;
            }
        }

        void SpawnMissingCharacters()
        {
            var db = GameDatabase.Instance;
            int i = 0;
            foreach (var data in PlayerData.All)
            {
                i++;
                if (data == null || data.Object == null) continue;
                var player = data.Object.InputAuthority;
                if (data.Character != null || _spawnedFor.Contains(player)) continue;
                _spawnedFor.Add(player);
                float a = i * Mathf.PI * 0.5f;
                var pos = Ground.Snap(new Vector3(Mathf.Cos(a) * 2.5f, 0f, Mathf.Sin(a) * 2.5f), 0.3f);
                int charIndex = data.CharacterIndex;
                int catchUp = Mathf.Max(0, TeamLevel - 1);
                var face = -new Vector3(pos.x, 0f, pos.z).normalized;
                Runner.Spawn(db.playerCharacterPrefab, pos, Quaternion.LookRotation(face), player,
                    (r, o) =>
                    {
                        var pc = o.GetComponent<PlayerCharacter>();
                        pc.Init(charIndex);
                        pc.PendingLevelUps = catchUp; // late joiners catch up with the team
                    });
            }
        }

        public void CheckDefeat()
        {
            if (!HasStateAuthority || State != RunState.Playing) return;
            if (PlayerCharacter.All.Count == 0) return;
            foreach (var p in PlayerCharacter.All) if (p != null && p.IsAlive) return;
            EndRun(false);
        }

        void EndRun(bool victory)
        {
            State = victory ? RunState.Victory : RunState.Defeat;
            StateTimer = TickTimer.CreateFromSeconds(Runner, GameDatabase.Config.resultsSeconds);
            Announce(victory ? "VICTORY!" : "The party has fallen...");
            if (victory)
            {
                foreach (var e in EnemyRegistry.All.ToArray())
                    if (e != null && e.IsAlive) Rpc_EnemyDied(e.transform.position, e.DefIndex, e.Elite);
                foreach (var e in EnemyRegistry.All.ToArray())
                    if (e != null && e.Object != null) Runner.Despawn(e.Object);
                foreach (var p in PlayerCharacter.All) p.ForceRevive();
            }
        }

        /// <summary>Host: let the host skip the results screen.</summary>
        public void ReturnToLobbyNow()
        {
            if (!HasStateAuthority) return;
            // despawn everything spawned during the run before the scene changes
            foreach (var e in EnemyRegistry.All.ToArray()) if (e != null && e.Object != null && e.Object.IsValid) Runner.Despawn(e.Object);
            foreach (var p in Pickup.All.ToArray()) if (p != null && p.Object != null && p.Object.IsValid) Runner.Despawn(p.Object);
            foreach (var c in PlayerCharacter.All.ToArray()) if (c != null && c.Object != null && c.Object.IsValid) Runner.Despawn(c.Object);
            CombatWorld.Clear();
            GameLauncher.Instance?.LoadLobbyScene();
        }

        // ------------------------------------------------------------------ XP

        public void AddXP(float amount)
        {
            if (!HasStateAuthority || State != RunState.Playing) return;
            _xpRemainder += amount;
            int whole = Mathf.FloorToInt(_xpRemainder);
            _xpRemainder -= whole;
            TeamXP += whole;
            var cfg = GameDatabase.Config;
            while (TeamXP >= XPToNext)
            {
                TeamXP -= XPToNext;
                TeamLevel++;
                XPToNext = cfg.XPForLevel(TeamLevel, Mathf.Max(1, PlayerCharacter.All.Count));
                foreach (var p in PlayerCharacter.All)
                    if (p != null && !p.Dead) p.PendingLevelUps++;
            }
        }

        // ------------------------------------------------------------------ enemies

        public void SpawnEnemy(EnemyDefinition def, Vector3 pos, bool elite, bool boss = false)
        {
            if (def == null || def.prefab == null) return;
            var db = GameDatabase.Instance;
            var cfg = db.config;
            int idx = db.IndexOf(def);
            if (idx < 0) return;
            float minute = RunTime / 60f;
            int players = Mathf.Max(1, PlayerCharacter.All.Count);
            float hpMul = (1f + cfg.healthPerMinute * minute + cfg.healthPerMinuteSquared * minute * minute) * (1f + cfg.healthPerExtraPlayer * (players - 1))
                          * (map != null ? map.difficulty : 1f);
            float dmgMul = 1f + cfg.damagePerMinute * minute;
            var rot = Quaternion.Euler(0, Random.Range(0f, 360f), 0);
            Runner.Spawn(def.prefab, pos, rot, null, (r, o) => o.GetComponent<Enemy>().Init(idx, elite, hpMul, dmgMul, boss));
        }

        public void OnEnemyKilled(Enemy e, PlayerCharacter killer)
        {
            if (!HasStateAuthority) return;
            TotalKills++;
            if (killer != null && killer.Data != null) killer.Data.Kills++;
            var def = e.Def;
            var cfg = GameDatabase.Config;
            var pos = e.transform.position;

            Rpc_EnemyDied(pos, e.DefIndex, e.Elite);

            if (e.Boss)
            {
                // boss loot: a chest for everyone, a magnet, a heal and a big pile of XP
                Announce($"{e.DisplayName} has fallen!");
                Rpc_BossDefeated(pos);
                int chests = Mathf.Max(1, PlayerCharacter.All.Count);
                for (int i = 0; i < chests; i++) Pickup.Spawn(Runner, cfg.chestPrefab, pos + RandomOffset() * 3f, PickupKind.Chest, 0);
                Pickup.Spawn(Runner, cfg.magnetPrefab, pos + RandomOffset() * 2f, PickupKind.Magnet, 0);
                Pickup.Spawn(Runner, cfg.healthOrbPrefab, pos + RandomOffset() * 2f, PickupKind.Health, 0);
                for (int i = 0; i < 6; i++) Pickup.SpawnXP(Runner, pos + RandomOffset() * 3f, 30);
                if (def.splitInto != null && def.bossSplitCount > 0 && State == RunState.Playing)
                    for (int i = 0; i < def.bossSplitCount; i++)
                        SpawnEnemy(def.splitInto, pos + RandomOffset() * 3f, i % 3 == 0);
                return;
            }

            int xp = def.xpValue * (e.Elite ? 10 : 1);
            Pickup.SpawnXP(Runner, pos, xp);
            if (Random.value < def.healthOrbChance) Pickup.Spawn(Runner, cfg.healthOrbPrefab, pos + RandomOffset(), PickupKind.Health, 0);
            if (Random.value < def.magnetChance) Pickup.Spawn(Runner, cfg.magnetPrefab, pos + RandomOffset(), PickupKind.Magnet, 0);
            if (e.Elite) Pickup.Spawn(Runner, cfg.chestPrefab, pos + RandomOffset(), PickupKind.Chest, 0);

            if (def.splitInto != null && def.splitCount > 0 && State == RunState.Playing)
            {
                for (int i = 0; i < def.splitCount; i++)
                    SpawnEnemy(def.splitInto, pos + RandomOffset() * 0.8f, false);
            }
        }

        static Vector3 RandomOffset() => new Vector3(Random.Range(-1f, 1f), 0, Random.Range(-1f, 1f));

        // ------------------------------------------------------------------ RPCs for visuals

        [Rpc(RpcSources.StateAuthority, RpcTargets.All, Channel = RpcChannel.Unreliable)]
        public void Rpc_EnemyDied(Vector3 pos, byte defIndex, NetworkBool elite)
        {
            var def = GameDatabase.Instance.GetEnemy(defIndex);
            if (def == null) return;
            float scale = elite ? GameDatabase.Config.eliteScale : 1f;
            FxManager.Instance?.DeathBurst(pos, def.deathColor, scale);
            AudioManager.Play(def.deathSound, pos, elite ? 1f : 0.55f);
            if (elite) CameraRig.Instance?.Shake(0.35f);
        }

        [Rpc(RpcSources.StateAuthority, RpcTargets.All, Channel = RpcChannel.Unreliable)]
        public void Rpc_EnemyShot(Vector3 origin, Vector3 vel, byte defIndex)
        {
            var def = GameDatabase.Instance.GetEnemy(defIndex);
            if (def == null) return;
            FxManager.Instance?.EnemyProjectile(origin, vel, def.attackDistance * 2.2f / Mathf.Max(1f, def.projectileSpeed), def.specialColor);
            AudioManager.Play(def.specialSound, origin, 0.45f);
        }

        [Rpc(RpcSources.StateAuthority, RpcTargets.All)]
        public void Rpc_Telegraph(Vector3 pos, float radius, float time, byte defIndex)
        {
            var def = GameDatabase.Instance.GetEnemy(defIndex);
            FxManager.Instance?.Telegraph(pos, radius, time, def != null ? def.specialColor : Color.red);
        }

        [Rpc(RpcSources.StateAuthority, RpcTargets.All)]
        public void Rpc_Blast(Vector3 pos, float radius, byte defIndex, NetworkBool explosion)
        {
            var def = GameDatabase.Instance.GetEnemy(defIndex);
            var col = def != null ? def.specialColor : Color.red;
            FxManager.Instance?.Shockwave(pos, radius, col, explosion);
            if (def != null) AudioManager.Play(def.specialSound, pos, 1f);
            var me = PlayerCharacter.Local;
            if (me != null && (me.transform.position - pos).sqrMagnitude < (radius + 8f) * (radius + 8f)) CameraRig.Instance?.Shake(explosion ? 0.45f : 0.35f);
        }

        [Rpc(RpcSources.StateAuthority, RpcTargets.All)]
        void Rpc_BossDefeated(Vector3 pos)
        {
            CameraRig.Instance?.Shake(1f);
            FxManager.Instance?.UpgradeBurst(pos, new Color(1f, 0.8f, 0.3f));
            FxManager.Instance?.Burst(pos + Vector3.up * 2f, new Color(1f, 0.85f, 0.4f), 60, 14f, 0.6f, 1.2f, 6f, true);
            var lib = AudioManager.Lib;
            if (lib != null) AudioManager.PlayUI(lib.victory, 0.7f, 1.2f);
        }

        [Rpc(RpcSources.StateAuthority, RpcTargets.All)]
        public void Rpc_BossSpawned(Vector3 pos)
        {
            CameraRig.Instance?.Shake(0.8f);
            FxManager.Instance?.UpgradeBurst(pos, new Color(1f, 0.3f, 0.3f));
            var lib = AudioManager.Lib;
            if (lib != null) AudioManager.PlayUI(lib.defeat, 0.6f, 1.4f);
        }

        [Rpc(RpcSources.StateAuthority, RpcTargets.All, Channel = RpcChannel.Unreliable)]
        public void Rpc_PickupFx(byte kind, Vector3 pos, PlayerRef collector)
        {
            var lib = AudioManager.Lib;
            if (lib == null) return;
            bool mine = Runner.LocalPlayer == collector;
            switch ((PickupKind)kind)
            {
                case PickupKind.XP:
                    if (mine) GemCombo.Play(lib.gem);
                    break;
                case PickupKind.Health:
                    AudioManager.Play(lib.health, pos, 0.8f);
                    FxManager.Instance?.UpgradeBurst(pos, new Color(1f, 0.4f, 0.5f));
                    break;
                case PickupKind.Magnet:
                    AudioManager.PlayUI(lib.magnet, 0.8f);
                    break;
                case PickupKind.Chest:
                    AudioManager.Play(lib.chest, pos, 1f);
                    FxManager.Instance?.UpgradeBurst(pos, new Color(1f, 0.85f, 0.3f));
                    break;
            }
        }

        public override void Render()
        {
            var lib = AudioManager.Lib;
            if (TeamLevel != _lastLevel)
            {
                if (TeamLevel > _lastLevel && _lastLevel > 0)
                {
                    if (lib != null) AudioManager.PlayUI(lib.levelUp, 0.8f);
                    foreach (var p in PlayerCharacter.All)
                        if (p != null && !p.Dead) FxManager.Instance?.UpgradeBurst(p.transform.position, new Color(0.5f, 0.9f, 1f));
                }
                _lastLevel = TeamLevel;
            }
            if (State != _lastState)
            {
                _lastState = State;
                if (State == RunState.Victory && lib != null) { AudioManager.StopMusic(); AudioManager.PlayUI(lib.victory); }
                if (State == RunState.Defeat && lib != null) { AudioManager.StopMusic(); AudioManager.PlayUI(lib.defeat); }
            }
            if (AnnouncementTick != _lastAnnouncement)
            {
                _lastAnnouncement = AnnouncementTick;
                HUD.Instance?.ShowAnnouncement(Announcement.Value);
            }
        }
    }

    /// <summary>Gem pickup sound that rises in pitch when you collect gems quickly (very satisfying).</summary>
    public static class GemCombo
    {
        static float _last;
        static int _combo;

        public static void Play(AudioClip clip)
        {
            float now = Time.time;
            _combo = now - _last < 0.35f ? Mathf.Min(_combo + 1, 14) : 0;
            _last = now;
            AudioManager.PlayUI(clip, 0.45f, 1f + _combo * 0.06f);
        }
    }
}
