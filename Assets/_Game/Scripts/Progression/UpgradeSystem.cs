using System.Collections.Generic;
using UnityEngine;

namespace MultiBash
{
    /// <summary>
    /// Rolls and applies level-up choices. Choices are sent over the network as short codes:
    ///   1..999      weapon index + 1
    ///   1000..1999  powerup index + 1000
    ///   2000        heal (fallback when everything is maxed)
    /// </summary>
    public static class UpgradeSystem
    {
        public const short Heal = 2000;

        public static bool IsWeapon(short code) => code > 0 && code < 1000;
        public static bool IsPowerup(short code) => code >= 1000 && code < 2000;
        public static int WeaponIndex(short code) => code - 1;
        public static int PowerupIndex(short code) => code - 1000;

        struct Candidate
        {
            public short code;
            public float weight;
        }

        static readonly List<Candidate> Candidates = new();

        static float RarityWeight(Rarity r, float luck) => r switch
        {
            Rarity.Common => 10f,
            Rarity.Rare => 5f * (1f + luck),
            Rarity.Epic => 2f * (1f + luck * 1.5f),
            _ => 5f,
        };

        /// <summary>Host only: fills pc.Choices with up to 3 random valid upgrades.</summary>
        public static void Roll(PlayerCharacter pc)
        {
            var db = GameDatabase.Instance;
            var cfg = db.config;
            float luck = pc.Stats.Luck;
            Candidates.Clear();

            int weaponCount = pc.WeaponCount;
            for (int i = 0; i < db.weapons.Count; i++)
            {
                var w = db.weapons[i];
                int lvl = pc.WeaponLevelOf(i);
                if (lvl > 0 && lvl < w.MaxLevel)
                    Candidates.Add(new Candidate { code = (short)(i + 1), weight = RarityWeight(w.rarity, luck) * 1.6f });
                else if (lvl == 0 && weaponCount < cfg.maxWeapons)
                    Candidates.Add(new Candidate { code = (short)(i + 1), weight = RarityWeight(w.rarity, luck) });
            }

            int powerCount = pc.PowerupCount;
            for (int i = 0; i < db.powerups.Count && i < PlayerCharacter.MaxPowerupSlots; i++)
            {
                var p = db.powerups[i];
                int lvl = pc.PowerupLevels.Get(i);
                if (lvl > 0 && lvl < p.maxLevel)
                    Candidates.Add(new Candidate { code = (short)(1000 + i), weight = RarityWeight(p.rarity, luck) * 1.2f });
                else if (lvl == 0 && powerCount < cfg.maxPowerups)
                    Candidates.Add(new Candidate { code = (short)(1000 + i), weight = RarityWeight(p.rarity, luck) });
            }

            int n = Mathf.Min(cfg.choicesPerLevel, pc.Choices.Length);
            for (int slot = 0; slot < n; slot++)
            {
                if (Candidates.Count == 0)
                {
                    pc.Choices.Set(slot, slot == 0 ? Heal : (short)0);
                    continue;
                }
                float total = 0f;
                foreach (var c in Candidates) total += c.weight;
                float r = Random.value * total;
                int pick = 0;
                for (int i = 0; i < Candidates.Count; i++)
                {
                    r -= Candidates[i].weight;
                    if (r <= 0f) { pick = i; break; }
                }
                pc.Choices.Set(slot, Candidates[pick].code);
                Candidates.RemoveAt(pick);
            }
        }

        /// <summary>Host only.</summary>
        public static void Apply(PlayerCharacter pc, short code)
        {
            if (IsWeapon(code)) pc.AddOrLevelWeapon(WeaponIndex(code));
            else if (IsPowerup(code)) pc.AddPowerup(PowerupIndex(code));
            else if (code == Heal) pc.Heal(pc.Stats.MaxHealth * GameDatabase.Config.healChoicePercent);
        }

        // ------------------------------------------------------------------ UI helpers

        public static string NameOf(short code)
        {
            var db = GameDatabase.Instance;
            if (IsWeapon(code)) return db.GetWeapon(WeaponIndex(code))?.displayName ?? "?";
            if (IsPowerup(code)) return db.GetPowerup(PowerupIndex(code))?.displayName ?? "?";
            return "Second Wind";
        }

        public static Sprite IconOf(short code)
        {
            var db = GameDatabase.Instance;
            if (IsWeapon(code)) return db.GetWeapon(WeaponIndex(code))?.icon;
            if (IsPowerup(code)) return db.GetPowerup(PowerupIndex(code))?.icon;
            return db.healIcon;
        }

        public static Rarity RarityOf(short code)
        {
            var db = GameDatabase.Instance;
            if (IsWeapon(code)) return db.GetWeapon(WeaponIndex(code))?.rarity ?? Rarity.Common;
            if (IsPowerup(code)) return db.GetPowerup(PowerupIndex(code))?.rarity ?? Rarity.Common;
            return Rarity.Common;
        }

        public static Color ColorOf(short code) => RarityOf(code) switch
        {
            Rarity.Rare => new Color(0.35f, 0.65f, 1f),
            Rarity.Epic => new Color(0.8f, 0.45f, 1f),
            _ => new Color(1f, 0.85f, 0.4f),
        };

        const string Gold = "#f2c447", Green = "#7dff6a";

        static string Delta(string label, string from, string to) =>
            $"<color={Gold}>{label}: {from} > </color><color={Green}>{to}</color>";

        static string Pct(float v) => $"{Mathf.RoundToInt(v * 100f)}%";

        /// <summary>Megabonk-style stat lines: "Damage: 15 > 20" (new value in green). Up to 3 lines.</summary>
        public static string StatLines(PlayerCharacter pc, short code)
        {
            var db = GameDatabase.Instance;
            var sb = new System.Text.StringBuilder();
            int lines = 0;
            void Add(string s)
            {
                if (lines >= 2) return;
                if (lines > 0) sb.Append('\n');
                sb.Append(s);
                lines++;
            }

            if (IsWeapon(code))
            {
                var w = db.GetWeapon(WeaponIndex(code));
                int lvl = pc.WeaponLevelOf(WeaponIndex(code));
                if (lvl == 0)
                {
                    Add($"<color={Gold}>{w.description}</color>");
                    return sb.ToString();
                }
                var a = w.GetLevel(lvl);
                var b = w.GetLevel(lvl + 1);
                if (!Mathf.Approximately(a.damage, b.damage)) Add(Delta("Damage", $"{a.damage:0.#}", $"{b.damage:0.#}"));
                if (a.amount != b.amount) Add(Delta(w.kind == WeaponKind.Orbit ? "Blades" : w.kind == WeaponKind.MeleeArc ? "Swings" : w.kind == WeaponKind.Chain ? "Bolts" : "Projectiles", $"{a.amount}", $"{b.amount}"));
                if (!Mathf.Approximately(a.area, b.area)) Add(Delta("Size", $"{a.area:0.#}m", $"{b.area:0.#}m"));
                if (a.pierce != b.pierce) Add(Delta(w.kind == WeaponKind.Chain ? "Chain Jumps" : "Pierce", $"{a.pierce}", $"{b.pierce}"));
                if (!Mathf.Approximately(a.cooldown, b.cooldown)) Add(Delta("Cooldown", $"{a.cooldown:0.##}s", $"{b.cooldown:0.##}s"));
                if (!Mathf.Approximately(a.duration, b.duration)) Add(Delta("Duration", $"{a.duration:0.#}s", $"{b.duration:0.#}s"));
                if (!Mathf.Approximately(a.speed, b.speed)) Add(Delta("Speed", $"{a.speed:0}", $"{b.speed:0}"));
                return sb.ToString();
            }
            if (IsPowerup(code))
            {
                var p = db.GetPowerup(PowerupIndex(code));
                var stats = pc.Stats;
                foreach (var m in p.perLevel)
                {
                    float cur = stats[m.stat], next = cur + m.value;
                    string name = m.stat switch
                    {
                        StatType.MaxHealth => "Max HP",
                        StatType.HealthRegen => "HP Regen",
                        StatType.MoveSpeed => "Move Speed",
                        StatType.ProjectileCount => "Projectile Count",
                        StatType.PickupRadius => "Pickup Range",
                        StatType.XPGain => "XP Gain",
                        StatType.Cooldown => "Attack Speed",
                        StatType.CritChance => "Crit Chance",
                        StatType.CritDamage => "Crit Damage",
                        StatType.ExtraJumps => "Air Jumps",
                        _ => m.stat.ToString(),
                    };
                    if (m.stat == StatType.Cooldown) Add(Delta(name, Pct(1f / Mathf.Max(0.25f, cur)), Pct(1f / Mathf.Max(0.25f, next))));
                    else if (StatInfo.IsMultiplier(m.stat)) Add(Delta(name, Pct(cur), Pct(next)));
                    else Add(Delta(name, $"{cur:0.#}", $"{next:0.#}"));
                }
                return sb.ToString();
            }
            return Delta("Health", $"{pc.Health:0}", $"{Mathf.Min(pc.MaxHealth, pc.Health + pc.MaxHealth * GameDatabase.Config.healChoicePercent):0}");
        }

        /// <summary>"NEW!" or "Lv 2 → 3" plus what it does.</summary>
        public static string Describe(PlayerCharacter pc, short code, out string levelText)
        {
            var db = GameDatabase.Instance;
            if (IsWeapon(code))
            {
                int i = WeaponIndex(code);
                var w = db.GetWeapon(i);
                int lvl = pc.WeaponLevelOf(i);
                if (lvl == 0)
                {
                    levelText = "NEW WEAPON";
                    return w.description;
                }
                levelText = $"Lv {lvl} > {lvl + 1}";
                var next = w.GetLevel(lvl + 1);
                return string.IsNullOrEmpty(next.upgradeText) ? w.description : next.upgradeText;
            }
            if (IsPowerup(code))
            {
                int i = PowerupIndex(code);
                var p = db.GetPowerup(i);
                int lvl = pc.PowerupLevels.Get(i);
                levelText = lvl == 0 ? "NEW" : $"Lv {lvl} > {lvl + 1}";
                return $"{p.description}\n<color=#9fe39f>{p.EffectText}</color>";
            }
            levelText = "";
            return $"Heal {GameDatabase.Config.healChoicePercent * 100f:0}% of your max HP.";
        }
    }
}
