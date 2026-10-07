using System.Collections.Generic;
using UnityEngine;

namespace MultiBash
{
    /// <summary>
    /// Rolls and applies level-up choices. Choices are sent over the network as short codes:
    ///   1..999      weapon index + 1
    ///   1000..1999  powerup index + 1000
    ///   2000        heal (fallback when everything is maxed)
    ///   3000..3999  evolve into weapon index + 3000 (a max-level weapon + its tome)
    /// </summary>
    public static class UpgradeSystem
    {
        public const short Heal = 2000;
        /// <summary>Fallback when everything is maxed: a small permanent boost that can be taken forever.</summary>
        public const short PowerSurge = 2001;
        const short EvolveBase = 3000;

        public static bool IsWeapon(short code) => code > 0 && code < 1000;
        public static bool IsPowerup(short code) => code >= 1000 && code < 2000;
        public static bool IsEvolution(short code) => code >= EvolveBase && code < EvolveBase + 1000;
        public static int WeaponIndex(short code) => IsEvolution(code) ? code - EvolveBase : code - 1;
        public static int PowerupIndex(short code) => code - 1000;

        /// <summary>The weapon (index into db.weapons) this player evolves into evoIndex, or -1.</summary>
        public static int EvolutionSource(PlayerCharacter pc, int evoIndex)
        {
            var db = GameDatabase.Instance;
            var evo = db.GetWeapon(evoIndex);
            if (evo == null) return -1;
            for (int i = 0; i < db.weapons.Count; i++)
                if (db.weapons[i].evolvesInto == evo && CanEvolve(pc, i)) return i;
            return -1;
        }

        /// <summary>True when this weapon is maxed and its evolution tome is owned.</summary>
        public static bool CanEvolve(PlayerCharacter pc, int weaponIndex)
        {
            var db = GameDatabase.Instance;
            var w = db.GetWeapon(weaponIndex);
            if (w == null || w.evolvesInto == null || w.evolveWith == null) return false;
            if (pc.WeaponLevelOf(weaponIndex) < w.EvolveAt) return false;
            int tome = db.powerups.IndexOf(w.evolveWith);
            return tome >= 0 && pc.PowerupLevels.Get(tome) > 0 && db.IndexOf(w.evolvesInto) >= 0;
        }

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
            bool treasure = pc.TreasurePicks > 0;
            pc.OfferIsTreasure = treasure;
            float luck = pc.Stats.Luck + (treasure ? ProgressionManager.Settings.treasureLuckBonus : 0f);
            Candidates.Clear();

            // an available evolution is always offered first
            int firstSlot = 0;
            for (int i = 0; i < db.weapons.Count && firstSlot == 0; i++)
            {
                if (!CanEvolve(pc, i)) continue;
                pc.Choices.Set(0, (short)(EvolveBase + db.IndexOf(db.weapons[i].evolvesInto)));
                firstSlot = 1;
            }

            int weaponCount = pc.WeaponCount;
            for (int i = 0; i < db.weapons.Count; i++)
            {
                var w = db.weapons[i];
                int lvl = pc.WeaponLevelOf(i);
                if (w.isEvolution && lvl == 0) continue;   // evolutions come from evolving, but level up like any weapon
                if (lvl > 0 && lvl < w.MaxLevel)
                    Candidates.Add(new Candidate { code = (short)(i + 1), weight = RarityWeight(w.rarity, luck) * (treasure ? 3f : 1.6f) });
                else if (lvl == 0 && weaponCount < ProgressionManager.Settings.maxWeapons)
                    Candidates.Add(new Candidate { code = (short)(i + 1), weight = RarityWeight(w.rarity, luck) });
            }

            int powerCount = pc.PowerupCount;
            for (int i = 0; i < db.powerups.Count && i < PlayerCharacter.MaxPowerupSlots; i++)
            {
                var p = db.powerups[i];
                int lvl = pc.PowerupLevels.Get(i);
                if (lvl > 0 && lvl < p.maxLevel)
                    Candidates.Add(new Candidate { code = (short)(1000 + i), weight = RarityWeight(p.rarity, luck) * 1.2f });
                else if (lvl == 0 && powerCount < ProgressionManager.Settings.maxPowerups)
                    Candidates.Add(new Candidate { code = (short)(1000 + i), weight = RarityWeight(p.rarity, luck) });
            }

            int n = Mathf.Min(ProgressionManager.Settings.choicesPerLevel, pc.Choices.Length);
            for (int slot = firstSlot; slot < n; slot++)
            {
                if (Candidates.Count == 0)
                {
                    // everything maxed: Power Surge (+ a heal when it would actually heal)
                    bool hurt = pc.Health < pc.MaxHealth - 0.5f;
                    short fill = slot == firstSlot ? PowerSurge : slot == firstSlot + 1 && hurt ? Heal : (short)0;
                    pc.Choices.Set(slot, fill);
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
            if (IsEvolution(code))
            {
                int evo = WeaponIndex(code);
                int src = EvolutionSource(pc, evo);
                if (src >= 0) pc.EvolveWeapon(src, evo);
            }
            else if (IsWeapon(code)) pc.AddOrLevelWeapon(WeaponIndex(code));
            else if (IsPowerup(code)) pc.AddPowerup(PowerupIndex(code));
            else if (code == Heal) pc.Heal(pc.Stats.MaxHealth * ProgressionManager.Settings.healChoicePercent);
            else if (code == PowerSurge) { pc.PowerSurges++; pc.LoadoutVersion++; }
        }

        // ------------------------------------------------------------------ UI helpers

        public static string NameOf(short code)
        {
            var db = GameDatabase.Instance;
            if (IsWeapon(code) || IsEvolution(code)) return db.GetWeapon(WeaponIndex(code))?.displayName ?? "?";
            if (IsPowerup(code)) return db.GetPowerup(PowerupIndex(code))?.displayName ?? "?";
            return code == PowerSurge ? "Power Surge" : "Second Wind";
        }

        public static Sprite IconOf(short code)
        {
            var db = GameDatabase.Instance;
            if (IsWeapon(code) || IsEvolution(code)) return db.GetWeapon(WeaponIndex(code))?.icon;
            if (IsPowerup(code)) return db.GetPowerup(PowerupIndex(code))?.icon;
            if (code == PowerSurge)
            {
                var might = db.powerups.Find(p => p.name == "Might");
                if (might != null) return might.icon;
            }
            return db.healIcon;
        }

        public static Rarity RarityOf(short code)
        {
            var db = GameDatabase.Instance;
            if (IsEvolution(code)) return Rarity.Legendary;
            if (IsWeapon(code)) return db.GetWeapon(WeaponIndex(code))?.rarity ?? Rarity.Common;
            if (IsPowerup(code)) return db.GetPowerup(PowerupIndex(code))?.rarity ?? Rarity.Common;
            return code == PowerSurge ? Rarity.Epic : Rarity.Common;
        }

        public static Color ColorOf(short code) => RarityOf(code) switch
        {
            Rarity.Legendary => new Color(1f, 0.6f, 0.15f),
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
                if (lines >= 3) return;
                if (lines > 0) sb.Append('\n');
                sb.Append(s);
                lines++;
            }

            if (IsEvolution(code))
            {
                var evo = db.GetWeapon(WeaponIndex(code));
                var from = db.GetWeapon(EvolutionSource(pc, WeaponIndex(code)));
                Add($"<color=#ffb347>{from?.displayName} evolves!</color>");
                Add($"<color={Gold}>{evo.description}</color>");
                return sb.ToString();
            }
            if (IsWeapon(code))
            {
                var w = db.GetWeapon(WeaponIndex(code));
                int lvl = pc.WeaponLevelOf(WeaponIndex(code));
                if (lvl == 0)
                {
                    Add($"<color={Gold}>{w.description}</color>");
                    if (w.evolveWith != null && w.evolvesInto != null) Add($"<color=#e2c8ff>Evolves with {w.evolveWith.displayName}</color>");
                    return sb.ToString();
                }
                var a = w.GetLevel(lvl);
                var b = w.GetLevel(lvl + 1);
                if (!Mathf.Approximately(a.damage, b.damage)) Add(Delta("Damage", $"{a.damage:0.#}", $"{b.damage:0.#}"));
                if (a.amount != b.amount) Add(Delta(w.kind == WeaponKind.Orbit ? "Blades" : w.kind == WeaponKind.MeleeArc ? "Swings" : w.kind == WeaponKind.Chain ? "Bolts"
                    : w.kind is WeaponKind.Aura or WeaponKind.Nova ? "Rings" : w.kind == WeaponKind.Lobbed ? "Flasks" : "Projectiles", $"{a.amount}", $"{b.amount}"));
                if (!Mathf.Approximately(a.area, b.area)) Add(Delta("Size", $"{a.area:0.#}m", $"{b.area:0.#}m"));
                bool usesPierce = w.kind is WeaponKind.Projectile or WeaponKind.Homing or WeaponKind.Chain;
                if (a.pierce != b.pierce && usesPierce) Add(Delta(w.kind == WeaponKind.Chain ? "Chain Jumps" : "Pierce", $"{a.pierce}", $"{b.pierce}"));
                if (!Mathf.Approximately(a.cooldown, b.cooldown)) Add(Delta("Cooldown", $"{a.cooldown:0.##}s", $"{b.cooldown:0.##}s"));
                if (!Mathf.Approximately(a.duration, b.duration)) Add(Delta("Duration", $"{a.duration:0.#}s", $"{b.duration:0.#}s"));
                if (!Mathf.Approximately(a.speed, b.speed)) Add(Delta("Speed", $"{a.speed:0}", $"{b.speed:0}"));
                if (lvl + 1 >= w.EvolveAt && w.evolveWith != null && w.evolvesInto != null)
                {
                    lines = Mathf.Min(lines, 2);
                    Add($"<color=#e2c8ff>LVL {w.EvolveAt} + {w.evolveWith.displayName} = {w.evolvesInto.displayName}</color>");
                }
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
                        StatType.Thorns => "Thorns",
                        StatType.Execute => "Execute",
                        StatType.Revives => "Self-Revives",
                        _ => m.stat.ToString(),
                    };
                    if (m.stat == StatType.Cooldown) Add(Delta(name, Pct(1f / Mathf.Max(0.25f, cur)), Pct(1f / Mathf.Max(0.25f, next))));
                    else if (StatInfo.IsMultiplier(m.stat)) Add(Delta(name, Pct(cur), Pct(next)));
                    else Add(Delta(name, $"{cur:0.#}", $"{next:0.#}"));
                }
                // tell players which of their weapons this tome evolves
                foreach (var w in db.weapons)
                    if (w.evolveWith == p && w.evolvesInto != null && pc.WeaponLevelOf(db.IndexOf(w)) > 0)
                    {
                        int lv = pc.WeaponLevelOf(db.IndexOf(w));
                        Add(lv >= w.EvolveAt
                            ? $"<color=#e2c8ff>Unlocks {w.evolvesInto.displayName}!</color>"
                            : $"<color=#e2c8ff>Key to {w.evolvesInto.displayName} ({w.displayName} LVL {w.EvolveAt})</color>");
                        break;
                    }
                return sb.ToString();
            }
            if (code == PowerSurge)
            {
                var st = pc.Stats;
                Add("<color=#f2c447>Everything is maxed! Take as many as you like.</color>");
                Add(Delta("Damage", Pct(st.Damage), Pct(st.Damage + PlayerCharacter.SurgeDamage)));
                Add(Delta("Max HP", $"{st.MaxHealth:0}", $"{st.MaxHealth + PlayerCharacter.SurgeHealth:0}"));
                return sb.ToString();
            }
            return Delta("Health", $"{pc.Health:0}", $"{Mathf.Min(pc.MaxHealth, pc.Health + pc.MaxHealth * ProgressionManager.Settings.healChoicePercent):0}");
        }

        /// <summary>"NEW!" or "Lv 2 → 3" plus what it does.</summary>
        public static string Describe(PlayerCharacter pc, short code, out string levelText)
        {
            var db = GameDatabase.Instance;
            if (IsEvolution(code))
            {
                levelText = "EVOLUTION";
                return db.GetWeapon(WeaponIndex(code))?.description ?? "";
            }
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
            if (code == PowerSurge) return "Permanent damage and health boost.";
            return $"Heal {ProgressionManager.Settings.healChoicePercent * 100f:0}% of your max HP.";
        }
    }
}
