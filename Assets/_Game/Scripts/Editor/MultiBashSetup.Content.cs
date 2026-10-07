using System.Collections.Generic;
using System.Linq;
using Fusion;
using UnityEditor;
using UnityEngine;

namespace MultiBash.EditorTools
{
    public static partial class MultiBashSetup
    {
        static Color Hex(string h) => ColorUtility.TryParseHtmlString(h, out var c) ? c : Color.white;

        static WeaponLevel L(string text, float dmg, float cd, int amount, float area, int pierce, float duration, float speed, float knock) =>
            new() { upgradeText = text, damage = dmg, cooldown = cd, amount = amount, area = area, pierce = pierce, duration = duration, speed = speed, knockback = knock };

        static void BuildThemeAndAudio()
        {
            Asset<UITheme>(Content + "/Resources/UITheme.asset", t =>
            {
                t.bodyFont = Load<Font>(UIDir + "/Fonts/Silkscreen-Regular.ttf");
                t.headerFont = Load<Font>(UIDir + "/Fonts/Silkscreen-Bold.ttf");
                t.numberFont = Load<Font>(UIDir + "/Fonts/Silkscreen-Regular.ttf");
                t.panel = Sprite(UIDir + "/Sprites/UI_Panel.png");
                t.titleBar = Sprite(UIDir + "/Sprites/UI_TitleBar.png");
                t.roundRect = Sprite(UIDir + "/Sprites/UI_RoundRect.png");
                t.button = Sprite(UIDir + "/Sprites/UI_Button.png");
                t.card = Sprite(UIDir + "/Sprites/UI_Card.png");
                t.slot = Sprite(UIDir + "/Sprites/UI_Slot.png");
                t.outline = Sprite(UIDir + "/Sprites/UI_Outline.png");
                t.circle = Sprite(UIDir + "/Sprites/UI_Circle.png");
                t.glow = Sprite(UIDir + "/Sprites/UI_Glow.png");
                t.gradient = Sprite(UIDir + "/Sprites/UI_Gradient.png");
                t.arrow = Sprite(UIDir + "/Sprites/UI_Arrow.png");
                t.clock = Sprite(UIDir + "/Sprites/UI_Clock.png");
                t.skull = Sprite(UIDir + "/Sprites/UI_Skull.png");
                t.heart = Sprite(UIDir + "/Sprites/UI_Heart.png");
                t.lockIcon = Sprite(UIDir + "/Sprites/UI_Lock.png");
                t.star = Sprite(UIDir + "/Sprites/UI_Star.png");
                t.text = new Color(0.96f, 0.95f, 0.9f);
                t.mutedText = new Color(0.68f, 0.72f, 0.7f);
                t.accent = new Color(1f, 0.82f, 0.25f);
                t.good = new Color(0.45f, 1f, 0.45f);
                t.bad = new Color(1f, 0.3f, 0.25f);
                t.health = new Color(0.9f, 0.1f, 0.1f);
                t.xp = new Color(0.15f, 0.65f, 1f);
                t.buttonBlue = new Color(0.25f, 0.5f, 0.85f);
                t.buttonGrey = new Color(0.45f, 0.5f, 0.5f);
                t.buttonRed = new Color(0.8f, 0.22f, 0.2f);
                t.buttonGreen = new Color(0.25f, 0.65f, 0.3f);
                t.common = new Color(0.2f, 0.55f, 0.28f);
                t.rare = new Color(0.18f, 0.38f, 0.8f);
                t.epic = new Color(0.55f, 0.2f, 0.75f);
            });

            Asset<AudioLibrary>(AudioDir + "/AudioLibrary.asset", a =>
            {
                a.menuMusic = Clip("MUS_Menu");
                a.battleMusic = Clip("MUS_Battle");
                a.bossMusic = Clip("MUS_Boss");
                a.deny = Clip("SFX_UIDeny");
                a.reroll = Clip("SFX_Reroll");
                a.evolution = Clip("SFX_Evolution");
                a.bossWarning = Clip("SFX_BossWarning");
                a.heartbeat = Clip("SFX_Heartbeat");
                a.crit = Clip("SFX_Crit");
                a.footstep = Clip("SFX_Footstep");
                a.land = Clip("SFX_Land");
                a.bounce = Clip("SFX_Bounce");
                a.smash = Clip("SFX_Smash");
                a.treasure = Clip("SFX_Treasure");
                a.click = Clip("SFX_UIClick");
                a.hover = Clip("SFX_UIHover");
                a.ready = Clip("SFX_UIReady");
                a.start = Clip("SFX_UIStart");
                a.victory = Clip("SFX_Victory");
                a.defeat = Clip("SFX_Defeat");
                a.hurt = Clip("SFX_PlayerHurt");
                a.jump = Clip("SFX_PlayerJump");
                a.slide = Clip("SFX_PlayerSlide");
                a.downed = Clip("SFX_PlayerDowned");
                a.revive = Clip("SFX_PlayerRevive");
                a.levelUp = Clip("SFX_LevelUp");
                a.lavaSizzle = Clip("SFX_LavaSizzle");
                a.gem = Clip("SFX_GemPickup");
                a.health = Clip("SFX_HealthPickup");
                a.magnet = Clip("SFX_MagnetPickup");
                a.chest = Clip("SFX_ChestOpen");
            });
        }

        static void BuildContent()
        {
            string W = Content + "/Weapons";
            string icons = UIDir + "/Icons";

            // ------------------------------------------------------------------ weapons
            var sword = Asset<WeaponDefinition>($"{W}/Greatsword/Greatsword.asset", w =>
            {
                w.displayName = "Greatsword";
                w.description = "Cleaves everything in a wide arc in front of you.";
                w.kind = WeaponKind.MeleeArc;
                w.rarity = Rarity.Common;
                w.icon = Sprite($"{icons}/Weapons/Icon_Greatsword.png");
                w.heldModel = Model("Weapons", "Greatsword");
                w.fxColor = Hex("#9fc4ff");
                w.fireSound = Clip("SFX_SwordSwing");
                w.hitSound = Clip("SFX_BladeHit");
                w.levels = new[]
                {
                    L("", 15, 0.95f, 1, 3.6f, 0, 0, 0, 7),
                    L("+30% damage", 20, 0.95f, 1, 3.6f, 0, 0, 0, 7),
                    L("Much bigger swing", 22, 1.0f, 1, 4.3f, 0, 0, 0, 8),
                    L("Also swings behind you", 26, 1.0f, 2, 4.3f, 0, 0, 0, 8),
                    L("MAX: huge damage, faster swings", 36, 0.8f, 2, 4.8f, 0, 0, 0, 10),
                };
            });
            var bow = Asset<WeaponDefinition>($"{W}/Longbow/Longbow.asset", w =>
            {
                w.displayName = "Longbow";
                w.description = "Fires piercing arrows at the nearest enemy.";
                w.kind = WeaponKind.Projectile;
                w.rarity = Rarity.Common;
                w.icon = Sprite($"{icons}/Weapons/Icon_Longbow.png");
                w.heldModel = Model("Weapons", "Longbow");
                w.projectileModel = Model("Weapons", "Arrow");
                w.fxColor = Hex("#c8ff9a");
                w.fireSound = Clip("SFX_BowShot");
                w.hitSound = Clip("SFX_BoneHit");
                w.levels = new[]
                {
                    L("", 11, 0.85f, 1, 1, 2, 0.95f, 28, 3),
                    L("+1 arrow", 11, 0.85f, 2, 1, 2, 0.95f, 28, 3),
                    L("Arrows pierce 2 more enemies", 14, 0.8f, 2, 1, 4, 1.0f, 30, 3),
                    L("+1 arrow, faster", 14, 0.65f, 3, 1, 4, 1.0f, 30, 3),
                    L("MAX: +1 arrow, +40% damage, pierce 7", 20, 0.6f, 4, 1, 7, 1.1f, 34, 4),
                };
            });
            var staff = Asset<WeaponDefinition>($"{W}/StormStaff/StormStaff.asset", w =>
            {
                w.displayName = "Storm Staff";
                w.description = "Lightning that leaps between nearby enemies.";
                w.kind = WeaponKind.Chain;
                w.rarity = Rarity.Common;
                w.icon = Sprite($"{icons}/Weapons/Icon_StormStaff.png");
                w.heldModel = Model("Weapons", "StormStaff");
                w.fxColor = Hex("#9fd8ff");
                w.fireSound = Clip("SFX_LightningZap");
                w.levels = new[]
                {
                    // amount = bolts, pierce = jumps, area = jump range
                    L("", 17, 1.5f, 1, 5.5f, 3, 0, 0, 2),
                    L("+2 jumps", 19, 1.5f, 1, 5.5f, 5, 0, 0, 2),
                    L("+1 bolt", 21, 1.4f, 2, 6f, 5, 0, 0, 2),
                    L("Longer jumps, faster casting", 24, 1.15f, 2, 7.5f, 6, 0, 0, 2),
                    L("MAX: +1 bolt, +30% damage", 32, 1.1f, 3, 8f, 7, 0, 0, 3),
                };
            });
            var flask = Asset<WeaponDefinition>($"{W}/PoisonFlask/PoisonFlask.asset", w =>
            {
                w.displayName = "Poison Flask";
                w.description = "Throws flasks that leave a toxic puddle. Damage every 0.5s.";
                w.kind = WeaponKind.Lobbed;
                w.rarity = Rarity.Common;
                w.icon = Sprite($"{icons}/Weapons/Icon_PoisonFlask.png");
                w.heldModel = Model("Weapons", "PoisonFlask");
                w.projectileModel = Model("Weapons", "PoisonFlask");
                w.fxColor = Hex("#9cff3a");
                w.fireSound = Clip("SFX_FlaskThrow");
                w.hitSound = Clip("SFX_FlaskShatter");
                w.levels = new[]
                {
                    L("", 7, 2.2f, 1, 2.4f, 0, 3f, 0, 0.5f),
                    L("Bigger puddles", 7, 2.2f, 1, 3.0f, 0, 3f, 0, 0.5f),
                    L("+1 flask", 8, 2.1f, 2, 3.0f, 0, 3.5f, 0, 0.5f),
                    L("+40% damage, lasts longer", 11, 2.0f, 2, 3.0f, 0, 4.5f, 0, 0.5f),
                    L("MAX: +1 flask, bigger puddles", 14, 1.8f, 3, 3.3f, 0, 5f, 0, 0.5f),
                };
            });
            var blades = Asset<WeaponDefinition>($"{W}/OrbitingBlades/OrbitingBlades.asset", w =>
            {
                w.displayName = "Orbiting Blades";
                w.description = "Blades circle around you, shredding anything they touch.";
                w.kind = WeaponKind.Orbit;
                w.rarity = Rarity.Rare;
                w.icon = Sprite($"{icons}/Weapons/Icon_OrbitingBlades.png");
                w.projectileModel = Model("Weapons", "OrbitBlade");
                w.fxColor = Hex("#d0a8ff");
                w.hitSound = Clip("SFX_BladeHit");
                w.levels = new[]
                {
                    // cooldown = time before the same enemy can be hit again, speed = degrees / second
                    L("", 10, 0.55f, 2, 2.6f, 0, 0, 210, 6),
                    L("+1 blade", 10, 0.55f, 3, 2.6f, 0, 0, 210, 6),
                    L("+40% damage, wider orbit", 14, 0.5f, 3, 3.1f, 0, 0, 230, 7),
                    L("+1 blade, spins faster", 14, 0.45f, 4, 3.1f, 0, 0, 280, 7),
                    L("MAX: +1 blade, +40% damage", 20, 0.4f, 5, 3.4f, 0, 0, 300, 8),
                };
            });
            var aura = Asset<WeaponDefinition>($"{W}/HolyAura/HolyAura.asset", w =>
            {
                w.displayName = "Holy Aura";
                w.description = "A ring of holy light constantly burns nearby enemies.";
                w.kind = WeaponKind.Aura;
                w.rarity = Rarity.Rare;
                w.icon = Sprite($"{icons}/Weapons/Icon_HolyAura.png");
                w.fxColor = Hex("#ffe28a");
                w.fireSound = Clip("SFX_AuraPulse");
                w.levels = new[]
                {
                    L("", 5, 0.5f, 1, 2.8f, 0, 0, 0, 1.5f),
                    L("Bigger aura", 5, 0.5f, 1, 3.4f, 0, 0, 0, 1.5f),
                    L("+60% damage", 8, 0.5f, 1, 3.4f, 0, 0, 0, 2f),
                    L("Bigger and pulses faster", 8, 0.4f, 1, 4.1f, 0, 0, 0, 2f),
                    L("MAX: +50% damage, huge radius", 12, 0.4f, 1, 4.8f, 0, 0, 0, 2.5f),
                };
            });
            var boomerang = Asset<WeaponDefinition>($"{W}/Boomerang/Boomerang.asset", w =>
            {
                w.displayName = "Boomerang";
                w.description = "Thrown at the nearest foe, then flies back. Hits on the way out and back.";
                w.kind = WeaponKind.Boomerang;
                w.rarity = Rarity.Common;
                w.icon = Sprite($"{icons}/Weapons/Icon_Boomerang.png");
                w.projectileModel = Model("Weapons", "Boomerang");
                w.fxColor = Hex("#ffd27a");
                w.fireSound = Clip("SFX_BoomerangWhoosh");
                w.hitSound = Clip("SFX_BladeHit");
                w.levels = new[]
                {
                    L("", 16, 1.4f, 1, 1.0f, 0, 1.3f, 18, 4),
                    L("+1 boomerang", 16, 1.4f, 2, 1.0f, 0, 1.3f, 18, 4),
                    L("+40% damage, bigger", 22, 1.3f, 2, 1.3f, 0, 1.4f, 19, 5),
                    L("+1 boomerang, faster", 22, 1.1f, 3, 1.3f, 0, 1.4f, 22, 5),
                    L("MAX: +1 boomerang, huge damage", 32, 1.0f, 4, 1.5f, 0, 1.5f, 24, 6),
                };
            });
            var meteor = Asset<WeaponDefinition>($"{W}/MeteorStaff/MeteorStaff.asset", w =>
            {
                w.displayName = "Meteor Staff";
                w.description = "Calls meteors down on the thickest crowd. Huge explosions.";
                w.kind = WeaponKind.Meteor;
                w.rarity = Rarity.Epic;
                w.icon = Sprite($"{icons}/Weapons/Icon_MeteorStaff.png");
                w.projectileModel = Model("Weapons", "MeteorRock");
                w.fxColor = Hex("#ff8a2e");
                w.fireSound = Clip("SFX_MeteorCast");
                w.hitSound = Clip("SFX_Explosion");
                w.levels = new[]
                {
                    L("", 32, 2.6f, 1, 2.6f, 0, 0, 0, 9),
                    L("+1 meteor", 32, 2.6f, 2, 2.6f, 0, 0, 0, 9),
                    L("Bigger explosions", 38, 2.5f, 2, 3.3f, 0, 0, 0, 10),
                    L("+40% damage, faster", 50, 2.1f, 2, 3.3f, 0, 0, 0, 10),
                    L("MAX: +1 meteor, enormous blasts", 64, 1.9f, 3, 4.0f, 0, 0, 0, 12),
                };
            });
            var nova = Asset<WeaponDefinition>($"{W}/FrostNova/FrostNova.asset", w =>
            {
                w.displayName = "Frost Nova";
                w.description = "An icy blast around you that damages and slows everything it touches.";
                w.kind = WeaponKind.Nova;
                w.rarity = Rarity.Rare;
                w.icon = Sprite($"{icons}/Weapons/Icon_FrostNova.png");
                w.projectileModel = Model("Weapons", "FrostShard");
                w.fxColor = Hex("#9fe6ff");
                w.fireSound = Clip("SFX_FrostNova");
                w.levels = new[]
                {
                    // duration = seconds of slow
                    L("", 10, 2.4f, 1, 4.0f, 0, 2.0f, 0, 6),
                    L("Bigger blast", 10, 2.4f, 1, 4.8f, 0, 2.0f, 0, 6),
                    L("+60% damage", 16, 2.3f, 1, 4.8f, 0, 2.2f, 0, 7),
                    L("Longer slow, more often", 16, 1.9f, 1, 5.3f, 0, 3.0f, 0, 7),
                    L("MAX: huge blast, +50% damage", 24, 1.7f, 1, 6.3f, 0, 3.2f, 0, 9),
                };
            });
            var daggers = Asset<WeaponDefinition>($"{W}/SpiritDaggers/SpiritDaggers.asset", w =>
            {
                w.displayName = "Spirit Daggers";
                w.description = "Ghostly blades that hunt down enemies on their own.";
                w.kind = WeaponKind.Homing;
                w.rarity = Rarity.Rare;
                w.icon = Sprite($"{icons}/Weapons/Icon_SpiritDaggers.png");
                w.projectileModel = Model("Weapons", "SpiritDagger");
                w.fxColor = Hex("#c08aff");
                w.fireSound = Clip("SFX_DaggerCast");
                w.hitSound = Clip("SFX_BladeHit");
                w.levels = new[]
                {
                    L("", 9, 1.3f, 2, 1, 1, 1.6f, 16, 2),
                    L("+1 dagger", 9, 1.3f, 3, 1, 1, 1.6f, 16, 2),
                    L("Pierce 1 more, +30% damage", 12, 1.25f, 3, 1, 2, 1.8f, 17, 2),
                    L("+1 dagger, faster", 12, 1.0f, 4, 1, 2, 1.8f, 19, 3),
                    L("MAX: +2 daggers, +40% damage", 17, 0.95f, 6, 1, 3, 2.0f, 20, 3),
                };
            });

            // levels 6-8: every weapon keeps growing - more projectiles, swings, rings, blades and bolts on screen
            void Grow(WeaponDefinition w, string unit)
            {
                if (w.levels.Length != 5) return;
                var last = w.levels[4];
                var list = new List<WeaponLevel>(w.levels);
                for (int k = 1; k <= 3; k++)
                {
                    float mul = 1f + (k == 3 ? 0.25f : 0.08f * k);
                    list.Add(L(k == 3 ? $"OVERDRIVE: +1 {unit}, +25% damage" : $"+1 {unit}, +{8 * k}% damage",
                        last.damage * mul, last.cooldown * (k == 3 ? 0.9f : 1f), last.amount + k, last.area, last.pierce + k, last.duration, last.speed, last.knockback));
                }
                w.levels = list.ToArray();
                EditorUtility.SetDirty(w);
            }
            Grow(sword, "swing"); Grow(bow, "arrow"); Grow(staff, "bolt"); Grow(flask, "flask"); Grow(blades, "blade");
            Grow(aura, "ring"); Grow(boomerang, "boomerang"); Grow(meteor, "meteor"); Grow(nova, "ring"); Grow(daggers, "dagger");

            // ------------------------------------------------------------------ powerups
            string P = Content + "/Powerups";
            PowerupDefinition Pow(string name, string desc, Rarity r, int max, StatType stat, float v, string iconName = null)
            {
                return Asset<PowerupDefinition>($"{P}/{name}.asset", p =>
                {
                    p.displayName = name;
                    p.description = desc;
                    p.rarity = r;
                    p.maxLevel = max;
                    p.icon = Sprite($"{icons}/Powerups/Icon_{iconName ?? name}.png");
                    p.perLevel = new List<StatModifier> { new(stat, v) };
                });
            }
            var might = Pow("Might", "Hit harder with every weapon.", Rarity.Common, 5, StatType.Damage, 0.12f);
            var swift = Pow("Swiftness", "Run faster.", Rarity.Common, 5, StatType.MoveSpeed, 0.6f);
            Pow("Vitality", "More max health (and heals that much).", Rarity.Common, 5, StatType.MaxHealth, 20f);
            var haste = Pow("Haste", "Weapons attack more often.", Rarity.Rare, 5, StatType.Cooldown, -0.07f);
            var expanse = Pow("Expanse", "Bigger swings, auras, puddles and orbits.", Rarity.Common, 5, StatType.Area, 0.12f);
            Pow("Multishot", "+1 arrow, flask, blade, swing, ring and lightning jump.", Rarity.Epic, 4, StatType.ProjectileCount, 1f);
            var wisdom = Pow("Wisdom", "Gain more XP for the whole team.", Rarity.Rare, 5, StatType.XPGain, 0.1f);
            var regen = Pow("Regeneration", "Slowly recover health.", Rarity.Rare, 5, StatType.HealthRegen, 0.6f);
            var armor = Pow("Armor", "Take less damage from every hit.", Rarity.Common, 5, StatType.Armor, 1f);
            var precision = Pow("Precision", "More critical hits.", Rarity.Common, 5, StatType.CritChance, 0.06f);
            Pow("Vampirism", "Heal for a share of the damage you deal.", Rarity.Epic, 4, StatType.Lifesteal, 0.012f);
            Pow("Feather", "Jump again in mid-air. Great for escaping the horde.", Rarity.Rare, 2, StatType.ExtraJumps, 1f);
            var persistence = Pow("Persistence", "Projectiles, puddles and slows last longer.", Rarity.Common, 5, StatType.Duration, 0.12f);
            var clover = Pow("Clover", "Luckier upgrade offers and more crits.", Rarity.Rare, 5, StatType.Luck, 0.15f);
            Pow("Phoenix Feather", "When you would go down, rise at 60% HP and blast foes away. 1 per level.", Rarity.Epic, 2,
                StatType.Revives, 1f, "Phoenix");

            // ------------------------------------------------------------------ evolutions (max weapon + its tome)
            WeaponDefinition Evo(WeaponDefinition from, PowerupDefinition with, string folder, string name, string desc, string fx, WeaponLevel lvl)
            {
                var evo = Asset<WeaponDefinition>($"{W}/Evolved/{folder}.asset", w =>
                {
                    w.displayName = name;
                    w.description = desc;
                    w.kind = from.kind;
                    w.rarity = Rarity.Legendary;
                    w.isEvolution = true;
                    var evoIcon = Sprite($"{icons}/Weapons/Icon_Evo_{folder}.png");
                    w.icon = evoIcon != null ? evoIcon : from.icon;
                    w.heldModel = from.heldModel;
                    w.projectileModel = from.projectileModel;
                    w.fxColor = Hex(fx);
                    w.fireSound = from.fireSound;
                    w.hitSound = from.hitSound;
                    var l2 = L("+1, +15% damage", lvl.damage * 1.15f, lvl.cooldown, lvl.amount + 1, lvl.area, lvl.pierce + 1, lvl.duration, lvl.speed, lvl.knockback);
                    var l3 = L("MAX: +1, +30% damage", lvl.damage * 1.3f, lvl.cooldown * 0.9f, lvl.amount + 2, lvl.area * 1.1f, lvl.pierce + 2, lvl.duration, lvl.speed, lvl.knockback);
                    w.levels = new[] { lvl, l2, l3 };
                });
                if (Force || from.evolvesInto == null)
                {
                    from.evolvesInto = evo;
                    from.evolveWith = with;
                    EditorUtility.SetDirty(from);
                }
                return evo;
            }
            Evo(sword, might, "TitansCleaver", "Titan's Cleaver", "A colossal blade. Every swing cleaves a full circle around you.", "#ffd27a",
                L("", 58, 0.75f, 4, 5.8f, 0, 0, 0, 12));
            Evo(bow, haste, "HailOfArrows", "Hail of Arrows", "A volley of eight arrows that pierce through whole hordes.", "#eaffb0",
                L("", 24, 0.45f, 8, 1, 14, 1.2f, 36, 4));
            Evo(staff, precision, "ThunderGod", "Thunder God's Rod", "Five bolts at once, each leaping through ten enemies.", "#e8f6ff",
                L("", 40, 0.95f, 5, 9f, 10, 0, 0, 3));
            Evo(flask, persistence, "PlagueCauldron", "Plague Cauldron", "Hurls five flasks that leave huge, lasting plague pools.", "#c8ff3a",
                L("", 18, 1.6f, 5, 4.6f, 0, 7f, 0, 0.6f));
            Evo(blades, expanse, "BladeTornado", "Blade Tornado", "Eight blades spin in a wide, fast storm around you.", "#f0c8ff",
                L("", 26, 0.32f, 8, 4.4f, 0, 0, 380, 9));
            Evo(aura, regen, "Sanctuary", "Sanctuary", "A blazing holy circle that scorches everything around you.", "#fff2a8",
                L("", 18, 0.33f, 1, 6.5f, 0, 0, 0, 3f));
            Evo(boomerang, swift, "TwinMoons", "Twin Moons", "Six glaives fly out and back, shredding both ways.", "#ffe9a0",
                L("", 44, 0.9f, 6, 1.8f, 0, 1.6f, 26, 7));
            Evo(meteor, clover, "Armageddon", "Armageddon", "A rain of six meteors with enormous blasts.", "#ff6a1a",
                L("", 95, 1.6f, 6, 5.2f, 0, 0, 0, 14));
            Evo(nova, armor, "AbsoluteZero", "Absolute Zero", "A vast frozen blast that nearly stops everything it touches.", "#dff8ff",
                L("", 36, 1.3f, 1, 9f, 0, 5f, 0, 10));
            Evo(daggers, wisdom, "PhantomLegion", "Phantom Legion", "Ten spectral blades hunt down every enemy nearby.", "#e2b8ff",
                L("", 24, 0.75f, 10, 1, 4, 2.4f, 22, 3));

            // ------------------------------------------------------------------ characters
            string C = Content + "/Characters";
            void Hero(string name, string display, string desc, string color, WeaponDefinition weapon, params StatModifier[] bonuses)
            {
                Asset<CharacterDefinition>($"{C}/{name}/{name}.asset", c =>
                {
                    c.displayName = display;
                    c.description = desc;
                    c.color = Hex(color);
                    c.portrait = Sprite($"{icons}/Characters/Portrait_{name}.png");
                    c.model = Model("Characters", name);
                    c.startingWeapon = weapon;
                    c.statBonuses = bonuses.ToList();
                });
            }
            Hero("Knight", "Knight", "A walking fortress. Wades into the horde and cleaves everything in reach.", "#4f86f0", sword,
                new StatModifier(StatType.MaxHealth, 30), new StatModifier(StatType.Armor, 2));
            Hero("Ranger", "Ranger", "Fast and precise. Keep moving and let the arrows do the work.", "#5fc04a", bow,
                new StatModifier(StatType.MoveSpeed, 1.2f), new StatModifier(StatType.PickupRadius, 1f));
            Hero("Mage", "Farzan", "A bearded storm sage. Calls lightning that leaps through packs of enemies.", "#e0473b", staff,
                new StatModifier(StatType.Cooldown, -0.1f), new StatModifier(StatType.XPGain, 0.1f));
            Hero("Alchemist", "Fredrik", "A bespectacled alchemist. Hurls toxic flasks that turn the ground into a death zone.", "#f0973a", flask,
                new StatModifier(StatType.Area, 0.2f), new StatModifier(StatType.Duration, 0.2f));

            // ------------------------------------------------------------------ enemies (prefab linked later)
            string E = Content + "/Enemies";
            var smallSlime = Asset<EnemyDefinition>($"{E}/Slime/SlimeSmall.asset", e =>
            {
                e.displayName = "Small Slime";
                e.maxHealth = 7; e.moveSpeed = 4.0f; e.contactDamage = 4; e.attackInterval = 0.9f; e.radius = 0.33f;
                e.movement = EnemyMovement.Hopper; e.hopRest = 0.35f; e.hopTime = 0.35f; e.hopHeight = 0.7f;
                e.xpValue = 1; e.healthOrbChance = 0.004f;
                e.hitSound = Clip("SFX_SlimeHit"); e.deathSound = Clip("SFX_SlimeDeath");
                e.deathColor = Hex("#7ee04a");
            });
            Asset<EnemyDefinition>($"{E}/Slime/Slime.asset", e =>
            {
                e.displayName = "Slime";
                e.maxHealth = 24; e.moveSpeed = 3.3f; e.contactDamage = 7; e.attackInterval = 1f; e.radius = 0.6f;
                e.movement = EnemyMovement.Hopper; e.hopRest = 0.6f; e.hopTime = 0.5f; e.hopHeight = 1.3f;
                e.xpValue = 2; e.healthOrbChance = 0.02f; e.magnetChance = 0.003f;
                e.splitInto = smallSlime; e.splitCount = 2;
                e.knockbackResist = 0.3f;
                e.bossName = "Slime Mother"; e.bossHealthMultiplier = 260f; e.bossDamageMultiplier = 2f; e.bossScale = 3.6f; e.bossSplitCount = 8;
                e.hitSound = Clip("SFX_SlimeHit"); e.deathSound = Clip("SFX_SlimeDeath"); e.moveSound = Clip("SFX_SlimeHop");
                e.deathColor = Hex("#7ee04a");
            });
            Asset<EnemyDefinition>($"{E}/Skeleton/Skeleton.asset", e =>
            {
                e.displayName = "Skeleton";
                e.maxHealth = 14; e.moveSpeed = 3.6f; e.contactDamage = 6; e.attackInterval = 1.1f; e.radius = 0.42f;
                e.movement = EnemyMovement.Walker;
                e.bossName = "Bone King"; e.bossHealthMultiplier = 480f; e.bossDamageMultiplier = 3f; e.bossScale = 3.3f;
                e.xpValue = 1; e.healthOrbChance = 0.015f; e.magnetChance = 0.002f;
                e.hitSound = Clip("SFX_BoneHit"); e.deathSound = Clip("SFX_SkeletonDeath");
                e.deathColor = Hex("#efe6cf");
            });
            Asset<EnemyDefinition>($"{E}/Bat/Bat.asset", e =>
            {
                e.displayName = "Bat";
                e.maxHealth = 6; e.moveSpeed = 6.0f; e.contactDamage = 4; e.attackInterval = 0.8f; e.radius = 0.35f;
                e.movement = EnemyMovement.Flyer;
                e.xpValue = 1; e.healthOrbChance = 0.006f;
                e.hitSound = Clip("SFX_BatScreech"); e.deathSound = Clip("SFX_BatDeath");
                e.deathColor = Hex("#6a3aa8");
            });
            Asset<EnemyDefinition>($"{E}/SkeletonArcher/SkeletonArcher.asset", e =>
            {
                e.displayName = "Skeleton Archer";
                e.maxHealth = 12; e.moveSpeed = 3.2f; e.contactDamage = 5; e.attackInterval = 1.2f; e.radius = 0.42f;
                e.movement = EnemyMovement.Keeper;
                e.attack = EnemyAttack.Ranged; e.attackDistance = 10f; e.specialCooldown = 2.6f; e.projectileSpeed = 13f;
                e.specialDamageMul = 1.4f; e.specialRadius = 0.35f; e.specialColor = Hex("#ff6a4a"); e.specialSound = Clip("SFX_EnemyArrow");
                e.xpValue = 2; e.healthOrbChance = 0.015f;
                e.hitSound = Clip("SFX_BoneHit"); e.deathSound = Clip("SFX_SkeletonDeath");
                e.deathColor = Hex("#efe6cf");
            });
            Asset<EnemyDefinition>($"{E}/BombShroom/BombShroom.asset", e =>
            {
                e.displayName = "Bomb Shroom";
                e.maxHealth = 16; e.moveSpeed = 4.6f; e.contactDamage = 6; e.attackInterval = 1f; e.radius = 0.5f;
                e.movement = EnemyMovement.Walker;
                e.attack = EnemyAttack.Explode; e.attackDistance = 2.6f; e.specialCooldown = 99f; e.telegraphTime = 0.95f;
                e.specialRadius = 3.0f; e.specialDamageMul = 2.3f; e.specialColor = Hex("#ff7a2a"); e.specialSound = Clip("SFX_Explosion");
                e.xpValue = 2; e.healthOrbChance = 0.02f;
                e.hitSound = Clip("SFX_SlimeHit"); e.deathSound = Clip("SFX_SlimeDeath");
                e.deathColor = Hex("#d8302a");
            });
            Asset<EnemyDefinition>($"{E}/Golem/Golem.asset", e =>
            {
                e.displayName = "Golem";
                e.maxHealth = 120; e.moveSpeed = 2.5f; e.contactDamage = 14; e.attackInterval = 1.5f; e.radius = 1.0f;
                e.movement = EnemyMovement.Walker;
                e.attack = EnemyAttack.Stomp; e.attackDistance = 4f; e.specialCooldown = 4f; e.telegraphTime = 1.05f;
                e.specialRadius = 4.5f; e.specialDamageMul = 1.5f; e.specialColor = Hex("#5ad8ff"); e.specialSound = Clip("SFX_GolemStomp");
                e.knockbackResist = 0.85f;
                e.bossName = "Ancient Golem"; e.bossHealthMultiplier = 95f; e.bossDamageMultiplier = 2f; e.bossScale = 2.4f;
                e.xpValue = 8; e.healthOrbChance = 0.15f; e.magnetChance = 0.02f;
                e.hitSound = Clip("SFX_RockHit"); e.deathSound = Clip("SFX_GolemStomp");
                e.deathColor = Hex("#8e939c");
            });

            // stage 2 / 3 newcomers
            Asset<EnemyDefinition>($"{E}/Ghoul/Ghoul.asset", e =>
            {
                e.displayName = "Ghoul";
                e.maxHealth = 30; e.moveSpeed = 4.5f; e.contactDamage = 7; e.attackInterval = 0.9f; e.radius = 0.45f;
                e.movement = EnemyMovement.Walker; e.gearSize = 1.3f;
                e.xpValue = 3; e.healthOrbChance = 0.02f; e.magnetChance = 0.003f;
                e.hitSound = Clip("SFX_SlimeHit"); e.deathSound = Clip("SFX_SkeletonDeath");
                e.deathColor = Hex("#7aa04a");
            });
            Asset<EnemyDefinition>($"{E}/Wraith/Wraith.asset", e =>
            {
                e.displayName = "Wraith";
                e.maxHealth = 26; e.moveSpeed = 5.4f; e.contactDamage = 10; e.attackInterval = 1f; e.radius = 0.45f;
                e.movement = EnemyMovement.Flyer; e.gearSize = 1.1f;
                e.attack = EnemyAttack.Ranged; e.attackDistance = 9f; e.specialCooldown = 3.2f; e.projectileSpeed = 11f;
                e.specialDamageMul = 1.2f; e.specialRadius = 0.45f; e.specialColor = Hex("#c070ff"); e.specialSound = Clip("SFX_DaggerCast");
                e.xpValue = 3; e.healthOrbChance = 0.02f;
                e.hitSound = Clip("SFX_BatScreech"); e.deathSound = Clip("SFX_BatDeath");
                e.deathColor = Hex("#9a5aff");
            });
            Asset<EnemyDefinition>($"{E}/ObsidianBrute/ObsidianBrute.asset", e =>
            {
                e.displayName = "Obsidian Brute";
                e.maxHealth = 160; e.moveSpeed = 3.0f; e.contactDamage = 18; e.attackInterval = 1.4f; e.radius = 0.85f;
                e.movement = EnemyMovement.Walker; e.gearSize = 1.0f;
                e.attack = EnemyAttack.Stomp; e.attackDistance = 3.4f; e.specialCooldown = 3.5f; e.telegraphTime = 0.9f;
                e.specialRadius = 3.4f; e.specialDamageMul = 1.4f; e.specialColor = Hex("#ff6a1a"); e.specialSound = Clip("SFX_GolemStomp");
                e.knockbackResist = 0.8f;
                e.xpValue = 10; e.healthOrbChance = 0.12f; e.magnetChance = 0.015f;
                e.hitSound = Clip("SFX_RockHit"); e.deathSound = Clip("SFX_GolemStomp");
                e.deathColor = Hex("#3a3040");
            });

            // fodder: weak horde enemies that never scale up (one hit all run long, so late game = slaying fast)
            Asset<EnemyDefinition>($"{E}/Fodder/BoneRabble.asset", e =>
            {
                e.displayName = "Bone Rabble";
                e.fodder = true; e.scale = 0.72f; e.xpChance = 0.25f;
                e.maxHealth = 4; e.moveSpeed = 4.4f; e.contactDamage = 4; e.attackInterval = 1f; e.radius = 0.32f;
                e.movement = EnemyMovement.Walker;
                e.xpValue = 1; e.healthOrbChance = 0.002f;
                e.hitSound = Clip("SFX_BoneHit"); e.deathSound = Clip("SFX_SkeletonDeath");
                e.deathColor = Hex("#efe6cf");
            });
            Asset<EnemyDefinition>($"{E}/Fodder/Slimeling.asset", e =>
            {
                e.displayName = "Slimeling";
                e.fodder = true; e.scale = 0.85f; e.xpChance = 0.25f;
                e.maxHealth = 3; e.moveSpeed = 4.6f; e.contactDamage = 3; e.attackInterval = 0.9f; e.radius = 0.3f;
                e.movement = EnemyMovement.Hopper; e.hopRest = 0.25f; e.hopTime = 0.35f; e.hopHeight = 0.7f;
                e.xpValue = 1; e.healthOrbChance = 0.002f;
                e.hitSound = Clip("SFX_SlimeHit"); e.deathSound = Clip("SFX_SlimeDeath");
                e.deathColor = Hex("#7ee04a");
            });
            Asset<EnemyDefinition>($"{E}/Fodder/Cinderling.asset", e =>
            {
                e.displayName = "Cinderling";
                e.fodder = true; e.scale = 0.85f; e.xpChance = 0.25f;
                e.maxHealth = 4; e.moveSpeed = 4.8f; e.contactDamage = 4; e.attackInterval = 0.9f; e.radius = 0.3f;
                e.movement = EnemyMovement.Hopper; e.hopRest = 0.22f; e.hopTime = 0.35f; e.hopHeight = 0.8f;
                e.xpValue = 1; e.healthOrbChance = 0.002f;
                e.hitSound = Clip("SFX_MagmaHit"); e.deathSound = Clip("SFX_MagmaDeath");
                e.deathColor = Hex("#ff7a1a");
            });

            // ------------------------------------------------------------------ Frostfall Peaks
            var frostSlimeling = Asset<EnemyDefinition>($"{E}/Frost/FrostSlimeling.asset", e =>
            {
                e.displayName = "Frost Slimeling";
                e.fodder = true; e.scale = 0.85f; e.xpChance = 0.25f;
                e.maxHealth = 3; e.moveSpeed = 4.6f; e.contactDamage = 3; e.attackInterval = 0.9f; e.radius = 0.3f;
                e.movement = EnemyMovement.Hopper; e.hopRest = 0.25f; e.hopTime = 0.35f; e.hopHeight = 0.7f;
                e.xpValue = 1; e.healthOrbChance = 0.002f;
                e.hitSound = Clip("SFX_SnowCrunch"); e.deathSound = Clip("SFX_SlimeDeath");
                e.deathColor = Hex("#9ff4ff");
            });
            Asset<EnemyDefinition>($"{E}/Frost/FrostSlime.asset", e =>
            {
                e.displayName = "Frost Slime";
                e.maxHealth = 26; e.moveSpeed = 3.2f; e.contactDamage = 7; e.attackInterval = 1f; e.radius = 0.6f;
                e.movement = EnemyMovement.Hopper; e.hopRest = 0.6f; e.hopTime = 0.5f; e.hopHeight = 1.3f;
                e.xpValue = 2; e.healthOrbChance = 0.02f; e.magnetChance = 0.003f;
                e.splitInto = frostSlimeling; e.splitCount = 2;
                e.knockbackResist = 0.3f;
                e.bossName = "Glacier Mother"; e.bossHealthMultiplier = 270f; e.bossDamageMultiplier = 2f; e.bossScale = 3.7f; e.bossSplitCount = 10;
                e.hitSound = Clip("SFX_SlimeHit"); e.deathSound = Clip("SFX_IceShatter"); e.moveSound = Clip("SFX_SlimeHop");
                e.deathColor = Hex("#9ff4ff");
            });
            Asset<EnemyDefinition>($"{E}/Frost/FrostSkeleton.asset", e =>
            {
                e.displayName = "Frost Skeleton";
                e.tint = new Color(0.72f, 0.9f, 1.3f);
                e.maxHealth = 15; e.moveSpeed = 3.6f; e.contactDamage = 6; e.attackInterval = 1.1f; e.radius = 0.42f;
                e.movement = EnemyMovement.Walker;
                e.bossName = "The Frost Lich King"; e.bossHealthMultiplier = 500f; e.bossDamageMultiplier = 3f; e.bossScale = 3.3f;
                e.xpValue = 1; e.healthOrbChance = 0.015f; e.magnetChance = 0.002f;
                e.hitSound = Clip("SFX_BoneHit"); e.deathSound = Clip("SFX_SkeletonDeath");
                e.deathColor = Hex("#c8f0ff");
            });
            Asset<EnemyDefinition>($"{E}/Frost/FrostBat.asset", e =>
            {
                e.displayName = "Frost Bat";
                e.maxHealth = 6; e.moveSpeed = 6.2f; e.contactDamage = 4; e.attackInterval = 0.8f; e.radius = 0.35f;
                e.movement = EnemyMovement.Flyer;
                e.xpValue = 1; e.healthOrbChance = 0.006f;
                e.hitSound = Clip("SFX_BatScreech"); e.deathSound = Clip("SFX_BatDeath");
                e.deathColor = Hex("#9ff4ff");
            });
            Asset<EnemyDefinition>($"{E}/IceWolf/IceWolf.asset", e =>
            {
                e.displayName = "Ice Wolf";
                e.maxHealth = 13; e.moveSpeed = 6.4f; e.contactDamage = 6; e.attackInterval = 0.8f; e.radius = 0.5f;
                e.movement = EnemyMovement.Walker; e.gearSize = 1.1f;
                e.xpValue = 2; e.healthOrbChance = 0.012f; e.magnetChance = 0.002f;
                e.hitSound = Clip("SFX_WolfBite"); e.deathSound = Clip("SFX_WolfDeath");
                e.deathColor = Hex("#c8d4e0");
            });
            Asset<EnemyDefinition>($"{E}/Yeti/Yeti.asset", e =>
            {
                e.displayName = "Yeti";
                e.maxHealth = 110; e.moveSpeed = 2.9f; e.contactDamage = 13; e.attackInterval = 1.4f; e.radius = 0.95f;
                e.movement = EnemyMovement.Walker; e.gearSize = 1.2f;
                e.attack = EnemyAttack.Stomp; e.attackDistance = 4f; e.specialCooldown = 4.2f; e.telegraphTime = 1.0f;
                e.specialRadius = 4.4f; e.specialDamageMul = 1.5f; e.specialColor = Hex("#9ff4ff"); e.specialSound = Clip("SFX_GolemStomp");
                e.knockbackResist = 0.8f;
                e.bossName = "Yeti King"; e.bossHealthMultiplier = 95f; e.bossDamageMultiplier = 2.1f; e.bossScale = 2.5f;
                e.xpValue = 8; e.healthOrbChance = 0.15f; e.magnetChance = 0.02f;
                e.hitSound = Clip("SFX_YetiHit"); e.deathSound = Clip("SFX_YetiRoar");
                e.deathColor = Hex("#e8eef2");
            });
            Asset<EnemyDefinition>($"{E}/Snowman/Snowman.asset", e =>
            {
                e.displayName = "Grumpy Snowman";
                e.maxHealth = 16; e.moveSpeed = 4.4f; e.contactDamage = 6; e.attackInterval = 1f; e.radius = 0.5f;
                e.movement = EnemyMovement.Walker;
                e.attack = EnemyAttack.Explode; e.attackDistance = 2.6f; e.specialCooldown = 99f; e.telegraphTime = 0.95f;
                e.specialRadius = 3.0f; e.specialDamageMul = 2.2f; e.specialColor = Hex("#9ff4ff"); e.specialSound = Clip("SFX_IceShatter");
                e.xpValue = 2; e.healthOrbChance = 0.02f;
                e.hitSound = Clip("SFX_SnowCrunch"); e.deathSound = Clip("SFX_SnowCrunch");
                e.deathColor = Hex("#f4f8ff");
            });

            Asset<EnemyDefinition>($"{E}/TreasureSlime/TreasureSlime.asset", e =>
            {
                e.displayName = "Treasure Slime";
                e.maxHealth = 70; e.moveSpeed = 6.2f; e.contactDamage = 0; e.attackInterval = 1f; e.radius = 0.55f;
                e.movement = EnemyMovement.Hopper; e.hopRest = 0.18f; e.hopTime = 0.42f; e.hopHeight = 1.1f;
                e.flees = true; e.lifetime = 28f; e.dropChests = 2;
                e.knockbackResist = 0.6f;
                e.xpValue = 0; e.healthOrbChance = 0f;
                e.hitSound = Clip("SFX_GemPickup"); e.deathSound = Clip("SFX_Treasure"); e.moveSound = Clip("SFX_SlimeHop");
                e.deathColor = Hex("#ffd24a");
            });

            // volcano
            var smallMagma = Asset<EnemyDefinition>($"{E}/MagmaSlime/MagmaSlimeSmall.asset", e =>
            {
                e.displayName = "Small Magma Slime";
                e.maxHealth = 9; e.moveSpeed = 4.3f; e.contactDamage = 5; e.attackInterval = 0.9f; e.radius = 0.33f;
                e.movement = EnemyMovement.Hopper; e.hopRest = 0.3f; e.hopTime = 0.35f; e.hopHeight = 0.8f;
                e.xpValue = 1; e.healthOrbChance = 0.004f;
                e.hitSound = Clip("SFX_MagmaHit"); e.deathSound = Clip("SFX_MagmaDeath");
                e.deathColor = Hex("#ff7a1a");
            });
            Asset<EnemyDefinition>($"{E}/MagmaSlime/MagmaSlime.asset", e =>
            {
                e.displayName = "Magma Slime";
                e.maxHealth = 28; e.moveSpeed = 3.3f; e.contactDamage = 7; e.attackInterval = 1f; e.radius = 0.6f;
                e.movement = EnemyMovement.Hopper; e.hopRest = 0.55f; e.hopTime = 0.5f; e.hopHeight = 1.4f;
                e.xpValue = 2; e.healthOrbChance = 0.02f; e.magnetChance = 0.003f;
                e.splitInto = smallMagma; e.splitCount = 2;
                e.knockbackResist = 0.35f;
                e.bossName = "Magma Queen"; e.bossHealthMultiplier = 300f; e.bossDamageMultiplier = 1.7f; e.bossScale = 3.8f; e.bossSplitCount = 10;
                e.hitSound = Clip("SFX_MagmaHit"); e.deathSound = Clip("SFX_MagmaDeath"); e.moveSound = Clip("SFX_SlimeHop");
                e.deathColor = Hex("#ff7a1a");
            });
            Asset<EnemyDefinition>($"{E}/FireImp/FireImp.asset", e =>
            {
                e.displayName = "Fire Imp";
                e.maxHealth = 10; e.moveSpeed = 5.2f; e.contactDamage = 5; e.attackInterval = 0.9f; e.radius = 0.38f;
                e.movement = EnemyMovement.Flyer;
                e.attack = EnemyAttack.Ranged; e.attackDistance = 9f; e.specialCooldown = 3.6f; e.projectileSpeed = 10f;
                e.specialDamageMul = 1.0f; e.specialRadius = 0.5f; e.specialColor = Hex("#ff8a1a"); e.specialSound = Clip("SFX_Fireball");
                e.xpValue = 2; e.healthOrbChance = 0.012f;
                e.hitSound = Clip("SFX_ImpCackle"); e.deathSound = Clip("SFX_ImpDeath");
                e.deathColor = Hex("#ff5a1a");
            });
        }

        // run after prefabs exist
        static void LinkContent()
        {
            string E = Content + "/Enemies";
            void LinkEnemy(string defPath, string prefabPath)
            {
                var def = Load<EnemyDefinition>(defPath);
                var prefab = Load<GameObject>(prefabPath);
                if (def != null && prefab != null && (def.prefab == null || Force))
                {
                    def.prefab = prefab.GetComponent<NetworkObject>();
                    EditorUtility.SetDirty(def);
                }
            }
            LinkEnemy($"{E}/Skeleton/Skeleton.asset", $"{E}/Skeleton/Skeleton.prefab");
            LinkEnemy($"{E}/Slime/Slime.asset", $"{E}/Slime/Slime.prefab");
            LinkEnemy($"{E}/Slime/SlimeSmall.asset", $"{E}/Slime/SlimeSmall.prefab");
            LinkEnemy($"{E}/Bat/Bat.asset", $"{E}/Bat/Bat.prefab");
            LinkEnemy($"{E}/SkeletonArcher/SkeletonArcher.asset", $"{E}/SkeletonArcher/SkeletonArcher.prefab");
            LinkEnemy($"{E}/BombShroom/BombShroom.asset", $"{E}/BombShroom/BombShroom.prefab");
            LinkEnemy($"{E}/Golem/Golem.asset", $"{E}/Golem/Golem.prefab");
            LinkEnemy($"{E}/MagmaSlime/MagmaSlime.asset", $"{E}/MagmaSlime/MagmaSlime.prefab");
            LinkEnemy($"{E}/MagmaSlime/MagmaSlimeSmall.asset", $"{E}/MagmaSlime/MagmaSlimeSmall.prefab");
            LinkEnemy($"{E}/FireImp/FireImp.asset", $"{E}/FireImp/FireImp.prefab");
            LinkEnemy($"{E}/TreasureSlime/TreasureSlime.asset", $"{E}/TreasureSlime/TreasureSlime.prefab");
            var treasure = Load<EnemyDefinition>($"{E}/TreasureSlime/TreasureSlime.asset");
            LinkEnemy($"{E}/Ghoul/Ghoul.asset", $"{E}/Ghoul/Ghoul.prefab");
            LinkEnemy($"{E}/Wraith/Wraith.asset", $"{E}/Wraith/Wraith.prefab");
            LinkEnemy($"{E}/ObsidianBrute/ObsidianBrute.asset", $"{E}/ObsidianBrute/ObsidianBrute.prefab");
            var ghoul = Load<EnemyDefinition>($"{E}/Ghoul/Ghoul.asset");
            var wraith = Load<EnemyDefinition>($"{E}/Wraith/Wraith.asset");
            var brute = Load<EnemyDefinition>($"{E}/ObsidianBrute/ObsidianBrute.asset");
            LinkEnemy($"{E}/Fodder/BoneRabble.asset", $"{E}/Skeleton/Skeleton.prefab");
            LinkEnemy($"{E}/Fodder/Slimeling.asset", $"{E}/Slime/SlimeSmall.prefab");
            LinkEnemy($"{E}/Fodder/Cinderling.asset", $"{E}/MagmaSlime/MagmaSlimeSmall.prefab");
            LinkEnemy($"{E}/Frost/FrostSlimeling.asset", $"{E}/Frost/FrostSlimeSmall.prefab");
            LinkEnemy($"{E}/Frost/FrostSlime.asset", $"{E}/Frost/FrostSlime.prefab");
            LinkEnemy($"{E}/Frost/FrostSkeleton.asset", $"{E}/Skeleton/Skeleton.prefab");
            LinkEnemy($"{E}/Frost/FrostBat.asset", $"{E}/Frost/FrostBat.prefab");
            LinkEnemy($"{E}/IceWolf/IceWolf.asset", $"{E}/IceWolf/IceWolf.prefab");
            LinkEnemy($"{E}/Yeti/Yeti.asset", $"{E}/Yeti/Yeti.prefab");
            LinkEnemy($"{E}/Snowman/Snowman.asset", $"{E}/Snowman/Snowman.prefab");
            var rabble = Load<EnemyDefinition>($"{E}/Fodder/BoneRabble.asset");
            var slimeling = Load<EnemyDefinition>($"{E}/Fodder/Slimeling.asset");
            var cinder = Load<EnemyDefinition>($"{E}/Fodder/Cinderling.asset");
            // escalating hordes: every minute from 4 on, a bigger ring of fodder
            List<WaveBurst> Hordes(EnemyDefinition a, EnemyDefinition b, params string[] lines)
            {
                var list = new List<WaveBurst>();
                for (int m = 4; m <= 9; m++)
                    list.Add(new() { minute = m + 0.6f, enemy = m % 2 == 0 ? a : b, count = 50 + 38 * (m - 4), ring = true, elites = 0, announcement = lines[(m - 4) % lines.Length] });
                return list;
            }

            var skel = Load<EnemyDefinition>($"{E}/Skeleton/Skeleton.asset");
            var slime = Load<EnemyDefinition>($"{E}/Slime/Slime.asset");
            var bat = Load<EnemyDefinition>($"{E}/Bat/Bat.asset");
            var archer = Load<EnemyDefinition>($"{E}/SkeletonArcher/SkeletonArcher.asset");
            var shroom = Load<EnemyDefinition>($"{E}/BombShroom/BombShroom.asset");
            var golem = Load<EnemyDefinition>($"{E}/Golem/Golem.asset");
            var waves = Asset<WaveDefinition>(Content + "/Waves/DefaultRun.asset", w =>
            {
                w.entries = new List<WaveEntry>
                {
                    new() { enemy = skel, startMinute = 0f, endMinute = 10f, rateAtStart = 0.45f, rateAtEnd = 8f, groupSize = 2, eliteChance = 0.008f },
                    new() { enemy = slime, startMinute = 1f, endMinute = 10f, rateAtStart = 0.2f, rateAtEnd = 4.5f, groupSize = 1, eliteChance = 0.012f },
                    new() { enemy = skel, startMinute = 2.5f, endMinute = 10f, rateAtStart = 0.1f, rateAtEnd = 1.0f, groupSize = 8, eliteChance = 0f },
                    new() { enemy = slime, startMinute = 4f, endMinute = 10f, rateAtStart = 0.06f, rateAtEnd = 0.6f, groupSize = 6, eliteChance = 0f },
                    new() { enemy = rabble, startMinute = 2.5f, endMinute = 10f, rateAtStart = 0.12f, rateAtEnd = 2.8f, groupSize = 6, rampCurve = 1.3f, eliteChance = 0f },
                    new() { enemy = slimeling, startMinute = 4f, endMinute = 10f, rateAtStart = 0.15f, rateAtEnd = 2.2f, groupSize = 8, rampCurve = 1.3f, eliteChance = 0f },
                    new() { enemy = ghoul, startMinute = 3.6f, endMinute = 10f, rateAtStart = 0.2f, rateAtEnd = 2.0f, groupSize = 3, eliteChance = 0.01f },
                    new() { enemy = wraith, startMinute = 6.2f, endMinute = 10f, rateAtStart = 0.25f, rateAtEnd = 1.4f, groupSize = 3, eliteChance = 0.01f },
                    new() { enemy = brute, startMinute = 6.5f, endMinute = 10f, rateAtStart = 0.06f, rateAtEnd = 0.35f, groupSize = 1, eliteChance = 0.04f },
                    new() { enemy = bat, startMinute = 1.25f, endMinute = 10f, rateAtStart = 0.12f, rateAtEnd = 2.2f, groupSize = 6, eliteChance = 0f },
                    new() { enemy = archer, startMinute = 2.25f, endMinute = 10f, rateAtStart = 0.08f, rateAtEnd = 0.9f, groupSize = 2, eliteChance = 0.01f },
                    new() { enemy = shroom, startMinute = 3.5f, endMinute = 10f, rateAtStart = 0.06f, rateAtEnd = 0.8f, groupSize = 1, eliteChance = 0f },
                    new() { enemy = golem, startMinute = 4f, endMinute = 10f, rateAtStart = 0.03f, rateAtEnd = 0.22f, groupSize = 1, eliteChance = 0.05f },
                };
                w.bursts = new List<WaveBurst>
                {
                    new() { minute = 1.5f, enemy = skel, count = 24, ring = true, elites = 1, announcement = "A ring of bones closes in!" },
                    new() { minute = 2.0f, enemy = treasure, count = 1, ring = true, elites = 0, announcement = "A Treasure Slime! Catch it before it escapes!" },
                    new() { minute = 5.0f, enemy = treasure, count = 1, ring = true, elites = 0, announcement = "A Treasure Slime! Catch it before it escapes!" },
                    new() { minute = 8.0f, enemy = treasure, count = 1, ring = true, elites = 0, announcement = "A Treasure Slime! Catch it before it escapes!" },
                    new() { minute = 2.25f, enemy = bat, count = 28, ring = false, elites = 0, announcement = "A swarm of bats!" },
                    new() { minute = 3f, enemy = slime, count = 15, ring = false, elites = 1, announcement = "Slime tide!" },
                    new() { minute = 3.9f, enemy = shroom, count = 8, ring = true, elites = 0, announcement = "Something is ticking..." },
                    new() { minute = 6.25f, enemy = archer, count = 24, ring = true, elites = 2, announcement = "Archers on the ridge!" },
                    new() { minute = 7.5f, enemy = golem, boss = true, announcement = "THE ANCIENT GOLEM STIRS!" },
                    new() { minute = 4.5f, enemy = skel, count = 60, ring = true, elites = 2, announcement = "The dead march!" },
                    new() { minute = 5.5f, enemy = slime, boss = true, announcement = "THE SLIME MOTHER AWAKENS!" },
                    new() { minute = 7f, enemy = slime, count = 50, ring = true, elites = 2, announcement = "The swamp awakens!" },
                    new() { minute = 8.5f, enemy = skel, count = 90, ring = true, elites = 3, announcement = "Hold the line!" },
                    new() { minute = 9f, enemy = skel, boss = true, announcement = "THE BONE KING RISES!" },
                    new() { minute = 9.5f, enemy = slime, count = 70, ring = false, elites = 3, announcement = "FINAL SURGE!" },
                };
                w.bursts.Add(new() { minute = 3.6f, enemy = ghoul, count = 10, ring = true, elites = 1, announcement = "Ghouls claw their way out of the graves!" });
                w.bursts.Add(new() { minute = 6.25f, enemy = wraith, count = 14, ring = true, elites = 1, announcement = "Wraiths descend!" });
                w.bursts.Add(new() { minute = 6.9f, enemy = brute, count = 4, ring = true, elites = 1, announcement = "Obsidian Brutes stomp in!" });
                w.bursts.AddRange(Hordes(rabble, slimeling, "The rabble swarms!", "A flood of slimelings!", "They keep coming!", "An endless horde!", "THE DEAD WON'T STOP!", "EVERYTHING AT ONCE!"));
            });

            var magma = Load<EnemyDefinition>($"{E}/MagmaSlime/MagmaSlime.asset");
            var imp = Load<EnemyDefinition>($"{E}/FireImp/FireImp.asset");
            var volcanoWaves = Asset<WaveDefinition>(Content + "/Waves/VolcanoRun.asset", w =>
            {
                w.entries = new List<WaveEntry>
                {
                    new() { enemy = skel, startMinute = 0f, endMinute = 10f, rateAtStart = 0.5f, rateAtEnd = 7.5f, groupSize = 2, eliteChance = 0.008f },
                    new() { enemy = magma, startMinute = 0.75f, endMinute = 10f, rateAtStart = 0.12f, rateAtEnd = 4.5f, groupSize = 1, eliteChance = 0.012f },
                    new() { enemy = cinder, startMinute = 2.5f, endMinute = 10f, rateAtStart = 0.2f, rateAtEnd = 3.2f, groupSize = 7, rampCurve = 1.3f, eliteChance = 0f },
                    new() { enemy = ghoul, startMinute = 3.6f, endMinute = 10f, rateAtStart = 0.2f, rateAtEnd = 1.8f, groupSize = 3, eliteChance = 0.01f },
                    new() { enemy = brute, startMinute = 5.8f, endMinute = 10f, rateAtStart = 0.08f, rateAtEnd = 0.45f, groupSize = 1, eliteChance = 0.04f },
                    new() { enemy = wraith, startMinute = 6.2f, endMinute = 10f, rateAtStart = 0.2f, rateAtEnd = 1.2f, groupSize = 3, eliteChance = 0.01f },
                    new() { enemy = rabble, startMinute = 4f, endMinute = 10f, rateAtStart = 0.15f, rateAtEnd = 2.2f, groupSize = 7, rampCurve = 1.3f, eliteChance = 0f },
                    new() { enemy = imp, startMinute = 1.75f, endMinute = 10f, rateAtStart = 0.05f, rateAtEnd = 1.0f, groupSize = 2, eliteChance = 0.01f },
                    new() { enemy = bat, startMinute = 2f, endMinute = 10f, rateAtStart = 0.1f, rateAtEnd = 1.2f, groupSize = 5, eliteChance = 0f },
                    new() { enemy = magma, startMinute = 3f, endMinute = 10f, rateAtStart = 0.06f, rateAtEnd = 0.6f, groupSize = 6, eliteChance = 0f },
                    new() { enemy = shroom, startMinute = 2.75f, endMinute = 10f, rateAtStart = 0.1f, rateAtEnd = 0.9f, groupSize = 1, eliteChance = 0f },
                    new() { enemy = archer, startMinute = 4f, endMinute = 10f, rateAtStart = 0.05f, rateAtEnd = 0.6f, groupSize = 2, eliteChance = 0.01f },
                    new() { enemy = golem, startMinute = 3.5f, endMinute = 10f, rateAtStart = 0.04f, rateAtEnd = 0.25f, groupSize = 1, eliteChance = 0.05f },
                };
                w.bursts = new List<WaveBurst>
                {
                    new() { minute = 1.5f, enemy = magma, count = 10, ring = true, elites = 1, announcement = "The ground boils!" },
                    new() { minute = 2.25f, enemy = treasure, count = 1, ring = true, elites = 0, announcement = "A Treasure Slime! Catch it before it escapes!" },
                    new() { minute = 5.0f, enemy = treasure, count = 1, ring = true, elites = 0, announcement = "A Treasure Slime! Catch it before it escapes!" },
                    new() { minute = 7.75f, enemy = treasure, count = 1, ring = true, elites = 0, announcement = "A Treasure Slime! Catch it before it escapes!" },
                    new() { minute = 2.5f, enemy = imp, count = 8, ring = false, elites = 1, announcement = "Imps rain fire from above!" },
                    new() { minute = 3.25f, enemy = shroom, count = 14, ring = true, elites = 0, announcement = "Something is ticking..." },
                    new() { minute = 4.25f, enemy = skel, count = 60, ring = true, elites = 2, announcement = "The ashen dead march!" },
                    new() { minute = 5.5f, enemy = magma, boss = true, announcement = "THE MAGMA QUEEN ERUPTS!" },
                    new() { minute = 6.5f, enemy = imp, count = 30, ring = true, elites = 2, announcement = "The sky burns!" },
                    new() { minute = 7.5f, enemy = golem, boss = true, announcement = "AN ANCIENT GOLEM AWAKENS!" },
                    new() { minute = 8.25f, enemy = magma, count = 60, ring = true, elites = 3, announcement = "Lava tide!" },
                    new() { minute = 9f, enemy = skel, boss = true, announcement = "THE BONE KING RISES FROM THE ASH!" },
                    new() { minute = 9.5f, enemy = imp, count = 50, ring = false, elites = 3, announcement = "FINAL ERUPTION!" },
                };
                w.bursts.Add(new() { minute = 3.6f, enemy = ghoul, count = 10, ring = true, elites = 1, announcement = "Ash ghouls crawl out of the cinders!" });
                w.bursts.Add(new() { minute = 6.0f, enemy = brute, count = 5, ring = true, elites = 1, announcement = "Obsidian Brutes rise from the lava!" });
                w.bursts.Add(new() { minute = 6.6f, enemy = wraith, count = 12, ring = true, elites = 1, announcement = "Wraiths ride the smoke!" });
                w.bursts.AddRange(Hordes(cinder, rabble, "Cinderlings pour from the cracks!", "The ashen rabble swarms!", "The caldera overflows!", "An endless horde!", "THE MOUNTAIN SPITS FIRE!", "EVERYTHING AT ONCE!"));
            });

            var fSkel = Load<EnemyDefinition>($"{E}/Frost/FrostSkeleton.asset");
            var fSlime = Load<EnemyDefinition>($"{E}/Frost/FrostSlime.asset");
            var fSlimeling = Load<EnemyDefinition>($"{E}/Frost/FrostSlimeling.asset");
            var fBat = Load<EnemyDefinition>($"{E}/Frost/FrostBat.asset");
            var wolf = Load<EnemyDefinition>($"{E}/IceWolf/IceWolf.asset");
            var yeti = Load<EnemyDefinition>($"{E}/Yeti/Yeti.asset");
            var snowman = Load<EnemyDefinition>($"{E}/Snowman/Snowman.asset");
            var frostWaves = Asset<WaveDefinition>(Content + "/Waves/FrostRun.asset", w =>
            {
                w.entries = new List<WaveEntry>
                {
                    new() { enemy = fSkel, startMinute = 0f, endMinute = 10f, rateAtStart = 0.45f, rateAtEnd = 7f, groupSize = 2, eliteChance = 0.008f },
                    new() { enemy = wolf, startMinute = 0.75f, endMinute = 10f, rateAtStart = 0.12f, rateAtEnd = 2.6f, groupSize = 3, eliteChance = 0.01f },
                    new() { enemy = fSlime, startMinute = 1.25f, endMinute = 10f, rateAtStart = 0.15f, rateAtEnd = 3.6f, groupSize = 1, eliteChance = 0.012f },
                    new() { enemy = fBat, startMinute = 1.75f, endMinute = 10f, rateAtStart = 0.1f, rateAtEnd = 1.8f, groupSize = 6, eliteChance = 0f },
                    new() { enemy = snowman, startMinute = 2.5f, endMinute = 10f, rateAtStart = 0.08f, rateAtEnd = 1.0f, groupSize = 2, eliteChance = 0f },
                    new() { enemy = fSlimeling, startMinute = 2.5f, endMinute = 10f, rateAtStart = 0.15f, rateAtEnd = 3.0f, groupSize = 8, rampCurve = 1.3f, eliteChance = 0f },
                    new() { enemy = ghoul, startMinute = 3.6f, endMinute = 10f, rateAtStart = 0.18f, rateAtEnd = 1.6f, groupSize = 3, eliteChance = 0.01f },
                    new() { enemy = yeti, startMinute = 3.75f, endMinute = 10f, rateAtStart = 0.04f, rateAtEnd = 0.3f, groupSize = 1, eliteChance = 0.05f },
                    new() { enemy = rabble, startMinute = 4f, endMinute = 10f, rateAtStart = 0.15f, rateAtEnd = 2.2f, groupSize = 7, rampCurve = 1.3f, eliteChance = 0f },
                    new() { enemy = wraith, startMinute = 6.2f, endMinute = 10f, rateAtStart = 0.2f, rateAtEnd = 1.2f, groupSize = 3, eliteChance = 0.01f },
                    new() { enemy = archer, startMinute = 4.5f, endMinute = 10f, rateAtStart = 0.05f, rateAtEnd = 0.6f, groupSize = 2, eliteChance = 0.01f },
                    new() { enemy = brute, startMinute = 6.5f, endMinute = 10f, rateAtStart = 0.06f, rateAtEnd = 0.35f, groupSize = 1, eliteChance = 0.04f },
                };
                w.bursts = new List<WaveBurst>
                {
                    new() { minute = 1.0f, enemy = wolf, count = 8, ring = true, elites = 1, announcement = "Wolves! The pack has your scent!" },
                    new() { minute = 2.0f, enemy = treasure, count = 1, ring = true, elites = 0, announcement = "A Treasure Slime! Catch it before it escapes!" },
                    new() { minute = 5.0f, enemy = treasure, count = 1, ring = true, elites = 0, announcement = "A Treasure Slime! Catch it before it escapes!" },
                    new() { minute = 8.0f, enemy = treasure, count = 1, ring = true, elites = 0, announcement = "A Treasure Slime! Catch it before it escapes!" },
                    new() { minute = 2.6f, enemy = fBat, count = 26, ring = false, elites = 0, announcement = "A blizzard of bats!" },
                    new() { minute = 3.2f, enemy = snowman, count = 12, ring = true, elites = 0, announcement = "The snowmen look... grumpy." },
                    new() { minute = 3.9f, enemy = wolf, count = 18, ring = true, elites = 2, announcement = "The whole pack howls!" },
                    new() { minute = 4.5f, enemy = fSkel, count = 60, ring = true, elites = 2, announcement = "The frozen dead march!" },
                    new() { minute = 5.5f, enemy = fSlime, boss = true, announcement = "THE GLACIER MOTHER CRACKS FREE!" },
                    new() { minute = 6.25f, enemy = wraith, count = 14, ring = true, elites = 1, announcement = "Wraiths ride the blizzard!" },
                    new() { minute = 7.5f, enemy = yeti, boss = true, announcement = "THE YETI KING ROARS!" },
                    new() { minute = 8.25f, enemy = wolf, count = 40, ring = true, elites = 3, announcement = "Wolves from every ridge!" },
                    new() { minute = 9f, enemy = fSkel, boss = true, announcement = "THE FROST LICH KING RISES!" },
                    new() { minute = 9.5f, enemy = snowman, count = 40, ring = true, elites = 2, announcement = "FINAL AVALANCHE!" },
                };
                w.bursts.Add(new() { minute = 6.9f, enemy = yeti, count = 4, ring = true, elites = 1, announcement = "Yetis stomp down the slopes!" });
                w.bursts.AddRange(Hordes(fSlimeling, rabble, "Frost slimelings pour over the snow!", "The frozen rabble swarms!", "The peaks overflow!", "An endless horde!", "THE MOUNTAIN WAKES!", "EVERYTHING AT ONCE!"));
            });

            string Mp = Content + "/Maps";
            Asset<MapDefinition>($"{Mp}/Graveyard.asset", m =>
            {
                m.displayName = "The Keep";
                m.description = "Ruined castle grounds full of bones, slimes and old magic. A good first run.";
                m.sceneName = "Game";
                m.waves = waves;
                m.music = Clip("MUS_Battle");
                m.accent = Hex("#5ad8ff");
                m.preview = Sprite(UIDir + "/Sprites/Map_Graveyard.png");
                m.difficulty = 1f;
                m.intro = "Survive until dawn!";
                m.ambience = Clip("AMB_Keep");
                m.ambienceVolume = 0.32f;
            });
            Asset<MapDefinition>($"{Mp}/Volcano.asset", m =>
            {
                m.displayName = "Molten Caldera";
                m.description = "Basalt ridges over rivers of lava. Imps, magma slimes, and lava that burns. Harder.";
                m.sceneName = "Volcano";
                m.waves = volcanoWaves;
                m.music = Clip("MUS_Volcano");
                m.accent = Hex("#ff7a2a");
                m.preview = Sprite(UIDir + "/Sprites/Map_Volcano.png");
                m.difficulty = 1.05f;
                m.intro = "The caldera wakes. Don't touch the lava!";
                m.ambience = Clip("AMB_Volcano");
                m.ambienceVolume = 0.38f;
            });
            Asset<MapDefinition>($"{Mp}/Frost.asset", m =>
            {
                m.displayName = "Frostfall Peaks";
                m.description = "Snowy peaks under the aurora. Wolf packs, yetis, grumpy snowmen and a frozen lake you can glide across. Hardest.";
                m.sceneName = "Frost";
                m.waves = frostWaves;
                m.music = Clip("MUS_Frost");
                m.accent = Hex("#9ff4ff");
                m.preview = Sprite(UIDir + "/Sprites/Map_Frost.png");
                m.difficulty = 1.18f;
                m.intro = "The pack is hunting. Stay together!";
                m.ambience = Clip("AMB_Frost");
                m.ambienceVolume = 0.36f;
            });

            string Pk = Content + "/Pickups";
            Asset<GameConfig>(Content + "/GameConfig.asset", c =>
            {
                c.waves = waves;
                c.eliteCrown = Model("Enemies", "Crown");
                c.stageGear = new[] { Model("Enemies", "GearHelmet"), Model("Enemies", "GearWarHelm") };
                c.xpGemPrefab = Load<GameObject>($"{Pk}/XPGem.prefab")?.GetComponent<NetworkObject>();
                c.healthOrbPrefab = Load<GameObject>($"{Pk}/HealthOrb.prefab")?.GetComponent<NetworkObject>();
                c.magnetPrefab = Load<GameObject>($"{Pk}/Magnet.prefab")?.GetComponent<NetworkObject>();
                c.chestPrefab = Load<GameObject>($"{Pk}/Chest.prefab")?.GetComponent<NetworkObject>();
                c.chestModel = Model("Pickups", "Chest");
                c.chestLoot = new[] { Model("Pickups", "GemGreen"), Model("Pickups", "GemBlue"), Model("Pickups", "GemRed"), Model("Pickups", "HealthOrb"),
                    Model("Weapons", "PoisonFlask"), Model("Enemies", "Crown") };
            });
        }

        /// <summary>
        /// The two tuning assets behind the ProgressionManager / CombatManager. Created once with the defaults written
        /// in ProgressionSettings.cs / CombatSettings.cs and then never overwritten by the setup tools (they are yours
        /// to tweak; use the inspector's "Reset" to go back to the defaults).
        /// </summary>
        static void BuildSettings()
        {
            string dir = Content + "/Settings";
            System.IO.Directory.CreateDirectory(dir);
            if (Load<ProgressionSettings>(dir + "/ProgressionSettings.asset") == null)
                AssetDatabase.CreateAsset(ScriptableObject.CreateInstance<ProgressionSettings>(), dir + "/ProgressionSettings.asset");
            if (Load<CombatSettings>(dir + "/CombatSettings.asset") == null)
                AssetDatabase.CreateAsset(ScriptableObject.CreateInstance<CombatSettings>(), dir + "/CombatSettings.asset");
        }

        [MenuItem("MultiBash/Refresh Database", priority = 20)]
        public static void RefreshDatabase()
        {
            var db = Asset<GameDatabase>(Content + "/Resources/GameDatabase.asset", d => { });
            db.config = Load<GameConfig>(Content + "/GameConfig.asset");
            BuildSettings();
            db.progression = Load<ProgressionSettings>(Content + "/Settings/ProgressionSettings.asset");
            db.combat = Load<CombatSettings>(Content + "/Settings/CombatSettings.asset");
            db.audio = Load<AudioLibrary>(AudioDir + "/AudioLibrary.asset");
            db.playerDataPrefab = Load<GameObject>(Prefabs + "/Network/PlayerData.prefab")?.GetComponent<NetworkObject>();
            db.playerCharacterPrefab = Load<GameObject>(Prefabs + "/Network/PlayerCharacter.prefab")?.GetComponent<NetworkObject>();
            db.healIcon = Sprite(UIDir + "/Icons/Powerups/Icon_Heal.png");

            // keep existing order (network ids!) and append anything new
            Merge(db.characters, PreferredOrder<CharacterDefinition>("Knight", "Ranger", "Mage", "Alchemist"));
            Merge(db.weapons, PreferredOrder<WeaponDefinition>("Greatsword", "Longbow", "StormStaff", "PoisonFlask", "OrbitingBlades", "HolyAura",
                "Boomerang", "MeteorStaff", "FrostNova", "SpiritDaggers", "TitansCleaver", "HailOfArrows", "ThunderGod", "PlagueCauldron",
                "BladeTornado", "Sanctuary", "TwinMoons", "Armageddon", "AbsoluteZero", "PhantomLegion"));
            Merge(db.powerups, PreferredOrder<PowerupDefinition>());
            Merge(db.enemies, PreferredOrder<EnemyDefinition>("Skeleton", "Slime", "SlimeSmall"));
            Merge(db.maps, PreferredOrder<MapDefinition>("Graveyard", "Volcano", "Frost"));
            EditorUtility.SetDirty(db);
            AssetDatabase.SaveAssets();
            Debug.Log($"[MultiBash] Database: {db.characters.Count} characters, {db.weapons.Count} weapons, {db.powerups.Count} powerups, {db.enemies.Count} enemies, {db.maps.Count} maps.");
        }

        static List<T> PreferredOrder<T>(params string[] first) where T : Object
        {
            var all = Find("t:" + typeof(T).Name, Content).Select(Load<T>).Where(x => x != null).ToList();
            all.Sort((a, b) =>
            {
                int ia = System.Array.IndexOf(first, a.name), ib = System.Array.IndexOf(first, b.name);
                if (ia < 0) ia = 999;
                if (ib < 0) ib = 999;
                return ia != ib ? ia.CompareTo(ib) : string.CompareOrdinal(a.name, b.name);
            });
            return all;
        }

        static void Merge<T>(List<T> list, List<T> found) where T : Object
        {
            list.RemoveAll(x => x == null || !found.Contains(x));
            foreach (var f in found) if (!list.Contains(f)) list.Add(f);
        }
    }
}
