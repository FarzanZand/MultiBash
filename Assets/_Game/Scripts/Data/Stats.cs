using System;
using System.Collections.Generic;
using UnityEngine;

namespace MultiBash
{
    /// <summary>
    /// Every number that describes how strong a player is.
    /// Multiplier stats (Damage, Area, Cooldown, ...) use 1 = 100%.
    /// </summary>
    public enum StatType
    {
        MaxHealth,
        HealthRegen,      // HP per second
        Armor,            // flat damage reduction per hit
        MoveSpeed,        // meters per second
        Damage,           // multiplier
        Area,             // multiplier
        Cooldown,         // multiplier (lower = faster). 0.9 = 10% faster
        ProjectileCount,  // bonus projectiles / chains / blades
        ProjectileSpeed,  // multiplier
        Duration,         // multiplier
        PickupRadius,     // meters
        XPGain,           // multiplier
        Luck,             // 0 = normal, 1 = rares twice as likely
        CritChance,       // 0.1 = 10%
        CritDamage,       // multiplier on crit (2 = double)
        Lifesteal,        // fraction of damage dealt returned as HP (0.02 = 2%)
        ExtraJumps,       // mid-air jumps
        Thorns,           // enemies that hit you take this multiple of their hit back
        Execute,          // non-boss enemies below this fraction of their HP die instantly (0.05 = 5%)
        Revives,          // self-revives per run (Phoenix Feather)
    }

    [Serializable]
    public struct StatModifier
    {
        public StatType stat;
        [Tooltip("Added to the stat. For multipliers 0.1 = +10%. For Cooldown use negative numbers to make weapons faster.")]
        public float value;

        public StatModifier(StatType stat, float value)
        {
            this.stat = stat;
            this.value = value;
        }

        public override string ToString() => StatInfo.Describe(stat, value);
    }

    public static class StatInfo
    {
        public static readonly int Count = Enum.GetValues(typeof(StatType)).Length;

        public static bool IsMultiplier(StatType s) =>
            s is StatType.Damage or StatType.Area or StatType.Cooldown or StatType.ProjectileSpeed
                or StatType.Duration or StatType.XPGain or StatType.Luck or StatType.CritChance
                or StatType.CritDamage or StatType.Lifesteal or StatType.Thorns or StatType.Execute;

        public static string Describe(StatType s, float v)
        {
            string sign = v >= 0 ? "+" : "";
            return s switch
            {
                StatType.Cooldown => $"{(v <= 0 ? "-" : "+")}{Mathf.Abs(v) * 100f:0}% cooldown",
                StatType.MaxHealth => $"{sign}{v:0} max HP",
                StatType.HealthRegen => $"{sign}{v:0.#} HP/sec",
                StatType.Armor => $"{sign}{v:0} armor",
                StatType.MoveSpeed => $"{sign}{v:0.#} move speed",
                StatType.ProjectileCount => $"{sign}{v:0} projectile",
                StatType.PickupRadius => $"{sign}{v:0.#}m pickup radius",
                StatType.ExtraJumps => $"{sign}{v:0} mid-air jump",
                StatType.Lifesteal => $"{sign}{v * 100f:0.#}% lifesteal",
                StatType.Thorns => $"{sign}{v * 100f:0}% damage reflected",
                StatType.Execute => $"execute below {v * 100f:0}% HP",
                StatType.Revives => $"{sign}{v:0} self-revive",
                _ => $"{sign}{v * 100f:0}% {Nice(s)}",
            };
        }

        static string Nice(StatType s) => s switch
        {
            StatType.ProjectileSpeed => "projectile speed",
            StatType.XPGain => "XP gain",
            StatType.CritChance => "crit chance",
            StatType.CritDamage => "crit damage",
            _ => s.ToString().ToLowerInvariant(),
        };
    }

    /// <summary>Final computed stats for a player. Plain array, cheap to rebuild.</summary>
    public class PlayerStats
    {
        readonly float[] _v = new float[StatInfo.Count];

        public float this[StatType s] => _v[(int)s];

        public float MaxHealth => _v[(int)StatType.MaxHealth];
        public float HealthRegen => _v[(int)StatType.HealthRegen];
        public float Armor => _v[(int)StatType.Armor];
        public float MoveSpeed => _v[(int)StatType.MoveSpeed];
        public float Damage => _v[(int)StatType.Damage];
        public float Area => _v[(int)StatType.Area];
        public float Cooldown => Mathf.Max(0.25f, _v[(int)StatType.Cooldown]);
        public int ProjectileCount => Mathf.RoundToInt(_v[(int)StatType.ProjectileCount]);
        public float ProjectileSpeed => _v[(int)StatType.ProjectileSpeed];
        public float Duration => _v[(int)StatType.Duration];
        public float PickupRadius => _v[(int)StatType.PickupRadius];
        public float XPGain => _v[(int)StatType.XPGain];
        public float Luck => _v[(int)StatType.Luck];
        public float CritChance => _v[(int)StatType.CritChance];
        public float CritDamage => Mathf.Max(1.5f, _v[(int)StatType.CritDamage]);
        public float Lifesteal => _v[(int)StatType.Lifesteal];
        public int ExtraJumps => Mathf.RoundToInt(_v[(int)StatType.ExtraJumps]);
        public float Thorns => _v[(int)StatType.Thorns];
        public float Execute => Mathf.Min(0.3f, _v[(int)StatType.Execute]);
        public int Revives => Mathf.RoundToInt(_v[(int)StatType.Revives]);

        public void Clear() => Array.Clear(_v, 0, _v.Length);

        public void Add(StatModifier m, float times = 1f) => _v[(int)m.stat] += m.value * times;

        public void Add(IEnumerable<StatModifier> mods, float times = 1f)
        {
            if (mods == null) return;
            foreach (var m in mods) Add(m, times);
        }
    }
}
