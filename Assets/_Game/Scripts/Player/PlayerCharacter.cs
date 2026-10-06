using System.Collections.Generic;
using Fusion;
using UnityEngine;

namespace MultiBash
{
    /// <summary>
    /// The in-game hero. Movement is client-predicted (NetworkCharacterController); health, weapons,
    /// downed/revive and level-up choices are decided by the host.
    /// </summary>
    [RequireComponent(typeof(NetworkCharacterController))]
    public class PlayerCharacter : NetworkBehaviour
    {
        public static readonly List<PlayerCharacter> All = new();
        /// <summary>Dev/testing only: players take no damage.</summary>
        public static bool DevGodMode;

        public const int MaxWeaponSlots = 4;
        public const int MaxPowerupSlots = 32;

        [Networked] public byte CharacterIndex { get; set; }
        [Networked] public float Health { get; set; }
        [Networked] public NetworkBool Downed { get; set; }
        [Networked] public NetworkBool Dead { get; set; }
        [Networked] public TickTimer DownedTimer { get; set; }
        [Networked] public float ReviveProgress { get; set; }

        /// <summary>weapon index + 1 (0 = empty slot)</summary>
        [Networked, Capacity(MaxWeaponSlots)] public NetworkArray<byte> WeaponIds => default;
        [Networked, Capacity(MaxWeaponSlots)] public NetworkArray<byte> WeaponLevels => default;
        [Networked, Capacity(MaxPowerupSlots)] public NetworkArray<byte> PowerupLevels => default;
        [Networked] public int LoadoutVersion { get; set; }

        [Networked] public int PendingLevelUps { get; set; }
        /// <summary>Upgrade codes (see UpgradeSystem). 0 = empty.</summary>
        [Networked, Capacity(3)] public NetworkArray<short> Choices => default;

        [Networked] TickTimer SlideTimer { get; set; }
        [Networked] TickTimer SlideCooldown { get; set; }
        [Networked] TickTimer HurtInvuln { get; set; }
        [Networked] Vector3 SlideDir { get; set; }
        [Networked] NetworkBool Momentum { get; set; }
        [Networked] NetworkButtons PrevButtons { get; set; }
        [Networked] public int JumpTick { get; set; }
        [Networked] public int SlideTick { get; set; }
        [Networked] public int ReviveTick { get; set; }
        [Networked] int AirJumps { get; set; }
        [Networked] public int AirJumpTick { get; set; }

        [SerializeField] Transform visualRoot;

        public PlayerData Data { get; private set; }
        public CharacterDefinition Def { get; private set; }
        public bool IsAlive => Object != null && Object.IsValid && !Downed && !Dead;
        public bool IsLocal => Object != null && Object.HasInputAuthority;
        public bool IsSliding => !SlideTimer.ExpiredOrNotRunning(Runner);
        public float MaxHealth => Stats.MaxHealth;
        public string DisplayName => Data != null ? Data.DisplayName : "Player";
        public Vector3 Velocity => _cc != null ? _cc.Velocity : Vector3.zero;

        NetworkCharacterController _cc;
        readonly PlayerStats _stats = new();
        int _statsVersion = -1;
        WeaponSystem _weapons;
        ProceduralRig _rig;
        Transform _hand;
        GameObject _heldModel;
        int _heldWeapon = -1;

        // visual change tracking
        float _lastHealth, _sizzleTimer;
        /// <summary>Telemetry (host): damage taken by source.</summary>
        public static float DamageFromHits, DamageFromLava;
        int _lastJump, _lastSlide, _lastRevive;
        bool _lastDowned;
        float _stepTimer;
        int _visualLoadout = -1;
        OrbitVisual _orbit;
        AuraVisual _aura;

        public PlayerStats Stats
        {
            get
            {
                if (_statsVersion != LoadoutVersion || Def == null) RecalcStats();
                return _stats;
            }
        }

        // ------------------------------------------------------------------ setup

        /// <summary>Host: called from Runner.Spawn's onBeforeSpawned.</summary>
        public void Init(int characterIndex)
        {
            var db = GameDatabase.Instance;
            CharacterIndex = (byte)characterIndex;
            Def = db.GetCharacter(characterIndex);
            for (int i = 0; i < MaxWeaponSlots; i++) { WeaponIds.Set(i, 0); WeaponLevels.Set(i, 0); }
            int start = db.IndexOf(Def.startingWeapon);
            if (start >= 0) { WeaponIds.Set(0, (byte)(start + 1)); WeaponLevels.Set(0, 1); }
            LoadoutVersion++;
            RecalcStats();
            Health = _stats.MaxHealth;
        }

        public override void Spawned()
        {
            if (!All.Contains(this)) All.Add(this);
            _cc = GetComponent<NetworkCharacterController>();
            Def = GameDatabase.Instance.GetCharacter(CharacterIndex);
            Data = PlayerData.Get(Object.InputAuthority);
            if (Data != null) Data.Character = this;

            if (HasStateAuthority && _statsVersion != LoadoutVersion) RecalcStats();
            _weapons = new WeaponSystem(this);

            BuildVisual();
            _lastHealth = Health;
            _lastJump = JumpTick;
            _lastSlide = SlideTick;
            _lastRevive = ReviveTick;

            if (HasInputAuthority && CameraRig.Instance != null) CameraRig.Instance.SetTarget(this);
        }

        public override void Despawned(NetworkRunner runner, bool hasState)
        {
            All.Remove(this);
            if (Data != null && Data.Character == this) Data.Character = null;
        }

        void BuildVisual()
        {
            if (visualRoot == null)
            {
                visualRoot = new GameObject("Visual").transform;
                visualRoot.SetParent(transform, false);
            }
            if (Def != null && Def.model != null)
            {
                var model = Instantiate(Def.model, visualRoot);
                model.name = "Model";
                model.transform.localPosition = Vector3.zero;
                model.transform.localRotation = Quaternion.identity;
            }
            _rig = visualRoot.GetComponent<ProceduralRig>();
            if (_rig == null) _rig = visualRoot.gameObject.AddComponent<ProceduralRig>();
            _rig.Rebind(); // the model was just instantiated under the rig
            _hand = _rig.FindPart("Hand_R");
            if (_hand == null)
            {
                // hand anchor sits at the end of the forearm (falls back to the whole arm on older models)
                var fore = _rig.FindPart("ForeArmR");
                var arm = fore != null ? fore : _rig.FindPart("ArmR");
                if (arm != null)
                {
                    _hand = new GameObject("Hand_R").transform;
                    _hand.SetParent(arm, false);
                    _hand.localPosition = fore != null ? new Vector3(0f, -0.34f, -0.02f) : new Vector3(0f, -0.64f, -0.02f);
                }
            }
            _orbit = gameObject.AddComponent<OrbitVisual>();
            _orbit.Owner = this;
            _aura = gameObject.AddComponent<AuraVisual>();
            _aura.Owner = this;
        }

        void RecalcStats()
        {
            var db = GameDatabase.Instance;
            if (Def == null) Def = db.GetCharacter(CharacterIndex);
            _stats.Clear();
            _stats.Add(db.config.baseStats);
            if (Def != null) _stats.Add(Def.statBonuses);
            for (int i = 0; i < db.powerups.Count && i < MaxPowerupSlots; i++)
            {
                int lvl = PowerupLevels.Get(i);
                if (lvl > 0) _stats.Add(db.powerups[i].perLevel, lvl);
            }
            _statsVersion = LoadoutVersion;
        }

        // ------------------------------------------------------------------ loadout helpers

        public int WeaponLevelOf(int weaponIndex)
        {
            for (int i = 0; i < MaxWeaponSlots; i++)
                if (WeaponIds.Get(i) == weaponIndex + 1) return WeaponLevels.Get(i);
            return 0;
        }

        public int WeaponCount
        {
            get
            {
                int c = 0;
                for (int i = 0; i < MaxWeaponSlots; i++) if (WeaponIds.Get(i) != 0) c++;
                return c;
            }
        }

        public int PowerupCount
        {
            get
            {
                int c = 0;
                for (int i = 0; i < MaxPowerupSlots; i++) if (PowerupLevels.Get(i) != 0) c++;
                return c;
            }
        }

        /// <summary>Host only.</summary>
        public void AddOrLevelWeapon(int weaponIndex)
        {
            for (int i = 0; i < MaxWeaponSlots; i++)
            {
                if (WeaponIds.Get(i) == weaponIndex + 1)
                {
                    WeaponLevels.Set(i, (byte)(WeaponLevels.Get(i) + 1));
                    LoadoutVersion++;
                    return;
                }
            }
            for (int i = 0; i < MaxWeaponSlots; i++)
            {
                if (WeaponIds.Get(i) == 0)
                {
                    WeaponIds.Set(i, (byte)(weaponIndex + 1));
                    WeaponLevels.Set(i, 1);
                    LoadoutVersion++;
                    return;
                }
            }
        }

        /// <summary>Host only.</summary>
        public void AddPowerup(int powerupIndex)
        {
            float oldMax = Stats.MaxHealth;
            PowerupLevels.Set(powerupIndex, (byte)(PowerupLevels.Get(powerupIndex) + 1));
            LoadoutVersion++;
            float newMax = Stats.MaxHealth;
            if (newMax > oldMax) Health += newMax - oldMax;
        }

        public void Heal(float amount)
        {
            if (!HasStateAuthority || !IsAlive) return;
            Health = Mathf.Min(Stats.MaxHealth, Health + amount);
        }

        // ------------------------------------------------------------------ simulation

        public override void FixedUpdateNetwork()
        {
            var gm = GameManager.Instance;
            var cfg = GameDatabase.Config;
            bool playing = gm != null && gm.State == RunState.Playing;
            bool canAct = playing && !Downed && !Dead;

            if (GetInput(out NetworkInputData input))
            {
                var pressed = input.Buttons.GetPressed(PrevButtons);
                PrevButtons = input.Buttons;

                var dir = canAct ? new Vector3(input.Move.x, 0f, input.Move.y) : Vector3.zero;
                if (dir.sqrMagnitude > 1f) dir.Normalize();
                float speed = Stats.MoveSpeed;
                bool sliding = IsSliding;

                if (canAct && pressed.IsSet(InputButton.Slide) && SlideCooldown.ExpiredOrNotRunning(Runner) && _cc.Grounded)
                {
                    var sd = dir.sqrMagnitude > 0.01f ? dir.normalized : transform.forward;
                    SlideDir = sd;
                    SlideTimer = TickTimer.CreateFromSeconds(Runner, cfg.slideDuration);
                    SlideCooldown = TickTimer.CreateFromSeconds(Runner, cfg.slideCooldown);
                    sliding = true;
                    SlideTick = Runner.Tick;
                    var v = _cc.Velocity;
                    var hv = sd * speed * cfg.slideSpeedMultiplier;
                    _cc.Velocity = new Vector3(hv.x, v.y, hv.z);
                }

                if (_cc.Grounded) AirJumps = 0;
                if (canAct && pressed.IsSet(InputButton.Jump))
                {
                    if (_cc.Grounded)
                    {
                        if (sliding) Momentum = true;
                        _cc.Jump(false, cfg.jumpImpulse);
                        JumpTick = Runner.Tick;
                    }
                    else if (AirJumps < Stats.ExtraJumps)
                    {
                        // mid-air jump (Feather): reset vertical speed so it always feels the same
                        AirJumps++;
                        var v = _cc.Velocity;
                        _cc.Velocity = new Vector3(v.x, 0f, v.z);
                        _cc.Jump(true, cfg.jumpImpulse * 0.95f);
                        JumpTick = Runner.Tick;
                        AirJumpTick = Runner.Tick;
                    }
                }

                float max = speed;
                if (sliding)
                {
                    max = speed * cfg.slideSpeedMultiplier;
                    dir = SlideDir;
                }
                else if (Momentum)
                {
                    max = speed * 1.45f;
                }

                _cc.maxSpeed = max;
                _cc.acceleration = sliding ? 400f : 70f;
                _cc.braking = 16f;
                _cc.Move(dir);

                if (_cc.Grounded && !sliding && Momentum && Runner.Tick - JumpTick > 4) Momentum = false;

                if (transform.position.y < Ground.Height(transform.position) - 6f) _cc.Teleport(Ground.Snap(transform.position, 1f));
            }

            if (!HasStateAuthority || !playing || Dead) return;
            float dt = Runner.DeltaTime;

            if (Downed)
            {
                bool helped = false;
                foreach (var p in All)
                {
                    if (p == this || !p.IsAlive) continue;
                    if ((p.transform.position - transform.position).sqrMagnitude <= cfg.reviveRadius * cfg.reviveRadius)
                    {
                        helped = true;
                        break;
                    }
                }
                ReviveProgress = helped
                    ? ReviveProgress + dt / cfg.reviveSeconds
                    : Mathf.Max(0f, ReviveProgress - dt / cfg.reviveSeconds * 0.5f);

                if (ReviveProgress >= 1f)
                {
                    Downed = false;
                    ReviveProgress = 0f;
                    Health = Stats.MaxHealth * cfg.reviveHealthPercent;
                    HurtInvuln = TickTimer.CreateFromSeconds(Runner, 2f);
                    ReviveTick = Runner.Tick;
                }
                else if (DownedTimer.Expired(Runner))
                {
                    Dead = true;
                    gm.CheckDefeat();
                }
                return;
            }

            if (LavaZone.InLava(transform.position) && !DevGodMode)
            {
                // lava burns through armor and invulnerability
                Health -= LavaZone.DamagePerSecond * dt;
                DamageFromLava += LavaZone.DamagePerSecond * dt;
                if (Health <= 0f)
                {
                    Health = 0f;
                    Downed = true;
                    ReviveProgress = 0f;
                    DownedTimer = TickTimer.CreateFromSeconds(Runner, GameDatabase.Config.downedSeconds);
                    gm.CheckDefeat();
                    return;
                }
            }

            if (Stats.HealthRegen > 0f) Health = Mathf.Min(Stats.MaxHealth, Health + Stats.HealthRegen * dt);
            if (Health > Stats.MaxHealth) Health = Stats.MaxHealth;

            PerfStats.Weapons.Start();
            _weapons.Tick(dt);
            PerfStats.Weapons.Stop();

            if (PendingLevelUps > 0 && Choices.Get(0) == 0)
                UpgradeSystem.Roll(this);
        }

        /// <summary>Host only.</summary>
        public void TakeDamage(float amount)
        {
            if (!HasStateAuthority || !IsAlive || DevGodMode) return;
            if (!HurtInvuln.ExpiredOrNotRunning(Runner)) return;
            float dmg = Mathf.Max(1f, amount - Stats.Armor);
            Health -= dmg;
            DamageFromHits += dmg;
            HurtInvuln = TickTimer.CreateFromSeconds(Runner, 0.33f);
            if (Health <= 0f)
            {
                Health = 0f;
                Downed = true;
                ReviveProgress = 0f;
                DownedTimer = TickTimer.CreateFromSeconds(Runner, GameDatabase.Config.downedSeconds);
                GameManager.Instance?.CheckDefeat();
            }
        }

        /// <summary>Host: instantly bring back (used when a run ends in victory).</summary>
        public void ForceRevive()
        {
            if (!HasStateAuthority) return;
            Downed = false;
            Dead = false;
            Health = Stats.MaxHealth;
        }

        public static PlayerCharacter NearestAlive(Vector3 pos)
        {
            PlayerCharacter best = null;
            float bestD = float.MaxValue;
            foreach (var p in All)
            {
                if (p == null || !p.IsAlive) continue;
                float d = (p.transform.position - pos).sqrMagnitude;
                if (d < bestD) { bestD = d; best = p; }
            }
            return best;
        }

        public static PlayerCharacter Local
        {
            get
            {
                foreach (var p in All) if (p != null && p.IsLocal) return p;
                return null;
            }
        }

        // ------------------------------------------------------------------ level-up choice (client -> host)

        [Rpc(RpcSources.InputAuthority, RpcTargets.StateAuthority)]
        public void Rpc_Choose(int slot)
        {
            if (PendingLevelUps <= 0 || slot < 0 || slot >= Choices.Length) return;
            short code = Choices.Get(slot);
            if (code == 0) return;
            UpgradeSystem.Apply(this, code);
            PendingLevelUps--;
            for (int i = 0; i < Choices.Length; i++) Choices.Set(i, 0);
            Rpc_UpgradeChosen(code);
        }

        [Rpc(RpcSources.StateAuthority, RpcTargets.All)]
        void Rpc_UpgradeChosen(short code)
        {
            FxManager.Instance?.UpgradeBurst(transform.position, UpgradeSystem.ColorOf(code));
        }

        // ------------------------------------------------------------------ weapon FX RPCs (host -> everyone)

        [Rpc(RpcSources.StateAuthority, RpcTargets.All, Channel = RpcChannel.Unreliable)]
        public void Rpc_Slash(Vector3 dir, float radius, float arcDegrees, byte weapon)
        {
            _rig?.Attack();
            var def = GameDatabase.Instance.GetWeapon(weapon);
            FxManager.Instance?.Slash(transform.position + Vector3.up * 0.9f, dir, radius, arcDegrees, def != null ? def.fxColor : Color.white);
            if (def != null) AudioManager.Play(def.fireSound, transform.position, 0.6f);
        }

        [Rpc(RpcSources.StateAuthority, RpcTargets.All, Channel = RpcChannel.Unreliable)]
        public void Rpc_Projectiles(Vector3 origin, Vector3 dir, byte count, float spread, float speed, float life, byte pierce, byte weapon)
        {
            _rig?.Cast();
            var def = GameDatabase.Instance.GetWeapon(weapon);
            FxManager.Instance?.Projectiles(origin, dir, count, spread, speed, life, pierce, def);
            if (def != null) AudioManager.Play(def.fireSound, transform.position, 0.5f);
        }

        [Rpc(RpcSources.StateAuthority, RpcTargets.All, Channel = RpcChannel.Unreliable)]
        public void Rpc_Lightning(Vector3 a, Vector3 b, byte weapon, NetworkBool first)
        {
            var def = GameDatabase.Instance.GetWeapon(weapon);
            var col = def != null ? def.fxColor : Color.cyan;
            if (first)
            {
                _rig?.Cast();
                if (def != null) AudioManager.Play(def.fireSound, b, 0.55f);
                FxManager.Instance?.SkyStrike(b, col);
            }
            else FxManager.Instance?.Lightning(a, b, col);
        }

        [Rpc(RpcSources.StateAuthority, RpcTargets.All, Channel = RpcChannel.Unreliable)]
        public void Rpc_Flask(Vector3 from, Vector3 to, float flightTime, float radius, float duration, byte weapon)
        {
            _rig?.Cast();
            var def = GameDatabase.Instance.GetWeapon(weapon);
            FxManager.Instance?.Flask(from, to, flightTime, radius, duration, def);
        }

        [Rpc(RpcSources.StateAuthority, RpcTargets.All, Channel = RpcChannel.Unreliable)]
        public void Rpc_Boomerang(Vector3 origin, Vector3 dir, byte count, float spread, float speed, float life, byte weapon)
        {
            _rig?.Attack();
            var def = GameDatabase.Instance.GetWeapon(weapon);
            FxManager.Instance?.Boomerangs(transform, origin, dir, count, spread, speed, life, def);
            if (def != null) AudioManager.Play(def.fireSound, transform.position, 0.5f);
        }

        [Rpc(RpcSources.StateAuthority, RpcTargets.All, Channel = RpcChannel.Unreliable)]
        public void Rpc_Meteor(Vector3 target, float delay, float radius, byte weapon)
        {
            _rig?.Cast();
            var def = GameDatabase.Instance.GetWeapon(weapon);
            FxManager.Instance?.Meteor(target, delay, radius, def);
            if (def != null) AudioManager.Play(def.fireSound, transform.position, 0.45f);
        }

        [Rpc(RpcSources.StateAuthority, RpcTargets.All, Channel = RpcChannel.Unreliable)]
        public void Rpc_Nova(float radius, byte weapon)
        {
            var def = GameDatabase.Instance.GetWeapon(weapon);
            FxManager.Instance?.Nova(transform.position, radius, def != null ? def.fxColor : Color.cyan);
            if (def != null) AudioManager.Play(def.fireSound, transform.position, 0.6f);
        }

        [Rpc(RpcSources.StateAuthority, RpcTargets.All, Channel = RpcChannel.Unreliable)]
        public void Rpc_Homing(Vector3 origin, Vector3 fwd, byte count, float speed, float life, byte pierce, byte weapon)
        {
            _rig?.Cast();
            var def = GameDatabase.Instance.GetWeapon(weapon);
            FxManager.Instance?.HomingShots(origin, fwd, count, speed, life, pierce, 360f, def);
            if (def != null) AudioManager.Play(def.fireSound, transform.position, 0.45f);
        }

        [Rpc(RpcSources.StateAuthority, RpcTargets.All, Channel = RpcChannel.Unreliable)]
        public void Rpc_AuraPulse(float radius, byte weapon)
        {
            var def = GameDatabase.Instance.GetWeapon(weapon);
            _aura?.Pulse();
            if (def != null) AudioManager.Play(def.fireSound, transform.position, 0.25f);
        }

        [Rpc(RpcSources.StateAuthority, RpcTargets.All, Channel = RpcChannel.Unreliable)]
        public void Rpc_HitSound(byte weapon, Vector3 pos)
        {
            var def = GameDatabase.Instance.GetWeapon(weapon);
            if (def != null) AudioManager.Play(def.hitSound, pos, 0.4f);
        }

        // ------------------------------------------------------------------ visuals

        public override void Render()
        {
            var lib = AudioManager.Lib;

            bool burning = LavaZone.InLava(transform.position) && !Dead && !Downed;
            _sizzleTimer -= Time.deltaTime;
            if (burning && _sizzleTimer <= 0f && AudioManager.Lib != null)
            {
                _sizzleTimer = 0.4f;
                AudioManager.Play(AudioManager.Lib.lavaSizzle, transform.position, IsLocal ? 0.7f : 0.35f);
            }
            if (burning && Random.value < 0.5f)
                FxManager.Instance?.Burst(transform.position + Vector3.up * 0.2f, new Color(1f, 0.5f, 0.15f), 1, 3f, 0.3f, 0.4f, -3f, true);
            if (Health < _lastHealth - 0.01f && burning && _lastHealth - Health < 2f)
            {
                // small lava ticks: no damage numbers spam, just a pulse
                if (IsLocal && Random.value < 0.08f) HUD.Instance?.FlashDamage();
                _lastHealth = Health;
            }
            if (Health < _lastHealth - 0.01f)
            {
                _rig?.Hit();
                if (IsLocal)
                {
                    CameraRig.Instance?.Shake(0.25f);
                    HUD.Instance?.FlashDamage();
                    if (lib != null) AudioManager.PlayUI(lib.hurt, 0.7f);
                }
                else if (lib != null) AudioManager.Play(lib.hurt, transform.position, 0.4f);
                FxManager.Instance?.DamageNumber(transform.position + Vector3.up * 2.1f, _lastHealth - Health, true);
            }
            _lastHealth = Health;

            if (JumpTick != _lastJump)
            {
                _lastJump = JumpTick;
                bool air = AirJumpTick == JumpTick;
                if (lib != null) AudioManager.Play(lib.jump, transform.position, IsLocal ? 0.5f : 0.3f, air ? 1.35f : 1f);
                if (air) FxManager.Instance?.Burst(transform.position + Vector3.up * 0.3f, new Color(0.85f, 0.95f, 1f), 12, 4f, 0.3f, 0.35f, 0f, true); // feather puff
                else FxManager.Instance?.Dust(transform.position, 3);
            }
            if (SlideTick != _lastSlide)
            {
                _lastSlide = SlideTick;
                if (lib != null) AudioManager.Play(lib.slide, transform.position, IsLocal ? 0.6f : 0.35f);
                FxManager.Instance?.Dust(transform.position, 6);
            }
            if (ReviveTick != _lastRevive)
            {
                _lastRevive = ReviveTick;
                if (lib != null) AudioManager.Play(lib.revive, transform.position, 0.9f);
                FxManager.Instance?.UpgradeBurst(transform.position, new Color(0.4f, 1f, 0.6f));
            }
            bool down = Downed || Dead;
            if (down != _lastDowned)
            {
                _lastDowned = down;
                if (down && Downed && lib != null) AudioManager.Play(lib.downed, transform.position, 0.9f);
            }

            if (_rig != null)
            {
                var v = Velocity;
                v.y = 0;
                // footstep dust puffs while running
                _stepTimer -= Time.deltaTime;
                if (_stepTimer <= 0f && v.magnitude > 3f && _cc != null && _cc.Grounded && !down)
                {
                    _stepTimer = IsSliding ? 0.05f : 0.28f;
                    FxManager.Instance?.Dust(transform.position, IsSliding ? 2 : 1);
                }
                _rig.SetMotion(v.magnitude, _cc != null && !_cc.Grounded, Velocity.y);
                _rig.SetSliding(IsSliding);
                _rig.SetDowned(down);
                _rig.gameObject.SetActive(!Dead);
            }

            if (_visualLoadout != LoadoutVersion)
            {
                _visualLoadout = LoadoutVersion;
                UpdateHeldWeapon();
            }
        }

        void UpdateHeldWeapon()
        {
            int first = WeaponIds.Get(0) - 1;
            if (first == _heldWeapon || _hand == null) return;
            _heldWeapon = first;
            if (_heldModel != null) Destroy(_heldModel);
            var def = GameDatabase.Instance.GetWeapon(first);
            if (def == null || def.heldModel == null) return;
            _heldModel = Instantiate(def.heldModel, _hand);
            _heldModel.transform.localPosition = Vector3.zero;
            _heldModel.transform.localRotation = Quaternion.Euler(90f, 0f, 0f);
            _heldModel.transform.localScale = Vector3.one;
        }
    }
}
