# MultiBash — Game Design Document

> 1–4 player online co-op horde survivor, inspired by *Megabonk*.
> Third-person 3D, auto-attacking weapons, XP gems, level-up drafts, ever-growing swarms.
> Engine: Unity 6 (URP) · Networking: Photon Fusion 2 (Host mode).

---

## 1. The pitch

You and up to three friends drop into an arena. Weapons fire **automatically**; your job is to
**move**: dodge, kite, jump, slide, and grab XP. Every level-up you pick 1 of 3 upgrades and your
build snowballs from "one sword" into "a screen full of lightning and poison". The swarm grows every
minute until a timer runs out (you win) or the whole party goes down (you lose).

**Core fantasy:** *start weak, end as a walking apocalypse, together.*

---

## 2. What makes it fun (design pillars)

| Pillar | How we deliver it |
|---|---|
| **Power curve you can feel** | Small numbers at minute 1, absurd numbers at minute 10. Every upgrade is visible: bigger arcs, more projectiles, more chains, bigger puddles. |
| **Movement is the skill** | Weapons aim themselves, so the player's skill is positioning. Fast run, jump, and a **slide** that keeps momentum. Slide-jumping is faster than running, which rewards skilled players like Megabonk's bhop/slide tech. |
| **Juice** | Hit flash, knockback, damage numbers, enemy squash on death, screen shake on big hits, XP gems that vacuum toward you, a "ding" pitch ladder when you collect gems quickly. |
| **Co-op that matters** | Shared team XP (everyone levels together, nobody falls behind), revive downed friends, and build synergy between characters (Mage chains through enemies the Alchemist poisons, etc.). |
| **No downtime** | Level-ups **don't pause** the game (it's multiplayer). Choices queue up and you pick with `1/2/3` while still running. Gems you don't need are never wasted. |

---

## 3. Game flow

```
Main Menu ─► Host Party ─┐
           └► Join (code)─┴─► Lobby (pick character, Ready) ─► Host presses START
                                                                     │
         ┌──────────────────────── Run (default 10 minutes) ◄────────┘
         │   kill swarm → XP gems → team level-up → choose upgrades
         │   enemies scale every minute, elite waves at 3/6/9 min
         ▼
   Victory (timer reached) / Defeat (all players down) ─► Results ─► back to Lobby
```

### Menus
- **Main Menu:** Name field, *Host*, *Join by Code*, *Quick Join* (any open party), *Quit*.
- **Lobby:** party list (up to 4) showing each player's name, character, ready state.
  Character select (4 cards with stats + starting weapon). Host sees a **room code** to share
  with friends and a *Start Run* button that unlocks when everyone is ready.
- **In-game HUD:** HP bar, team XP bar + level, run timer, kill counter, weapon/upgrade icons,
  teammate HP list, pending-level-up prompt.
- **Results:** victory/defeat, time survived, kills per player, damage per weapon.

---

## 4. Player

### Controls (keyboard/mouse + gamepad via Input System)
| Action | KB/M | Gamepad |
|---|---|---|
| Move | WASD | Left stick |
| Camera | Mouse | Right stick |
| Jump | Space | A |
| Slide | Left Ctrl / Shift | B |
| Pick upgrade | 1 / 2 / 3 | D-pad |
| Scoreboard | Tab | Select |

### Base stats (every stat is a designer-editable number on the Character asset)
Max HP, HP regen, armor, move speed, jump height, pickup radius, damage %, area %,
cooldown %, projectile count bonus, projectile speed %, duration %, XP gain %, luck.

### Downed & revive
- At 0 HP you're **downed** (can't move or attack) for 30s.
- A teammate standing in your revive circle for 3s brings you back at 50% HP.
- If the timer runs out you die for the rest of the run (spectate teammates).
- **Everyone downed at once = Defeat.**

---

## 5. Characters & starting weapons (4)

Each character starts with one signature weapon and a small passive bonus.
Any character can later find any weapon.

| Character | Starting weapon | Weapon behavior | Passive | Playstyle |
|---|---|---|---|---|
| **Knight** | **Greatsword** | Wide melee arc in front of you; upgrades widen the arc and add a back-swing. | +20% Max HP, +2 armor | Front-liner; wades into the swarm. |
| **Ranger** | **Longbow** | Auto-targets the nearest enemy and fires piercing arrows; upgrades add arrows and pierce. | +15% move speed | Kiter; fast, fragile. |
| **Mage** | **Storm Staff** | Lightning bolt that **chains** between nearby enemies; upgrades add chains and jump range. | +15% cooldown reduction | Crowd-clearer; best against big packs. |
| **Alchemist** | **Poison Flask** | Lobs flasks that leave a **damage-over-time puddle**; upgrades make puddles bigger and longer. | +20% area | Zone control; protects teammates. |

### Weapon levels
Each weapon has **5 levels**. Each level is a row in the weapon asset (damage, cooldown,
amount, area, pierce, duration, chains...), so designers can rebalance without code.

### Extra weapons (unlockable mid-run through level-up)
- **Orbiting Blades:** blades circle you; great passive defense.
- **Holy Aura:** constant damage ring around you; scales with Area.

> Six weapons total at launch. Adding a 7th = one ScriptableObject + (optionally) one behavior script.

---

## 6. Powerups (passive "tomes")

Picked at level-up, stack up to 5 times each. All are data-only assets.

| Powerup | Per level |
|---|---|
| Might | +10% damage |
| Swiftness | +8% move speed |
| Vitality | +20 max HP |
| Haste | -8% weapon cooldown |
| Expanse | +12% area |
| Multishot | +1 projectile (max 3 levels) |
| Magnet | +30% pickup radius |
| Wisdom | +10% XP gain |
| Regeneration | +0.5 HP/s |
| Armor | +1 flat damage reduction |

### Level-up draft rules
- 3 random choices, weighted by rarity (Common / Rare / Epic tints).
- Never offers a maxed item. Max **4 weapons** and **6 powerups** per player.
- Once a player has 4 weapons, only owned weapons can be offered.
- If everything is maxed, offer *+Gold* / *Heal 30%*.

---

## 7. Enemies

| Enemy | Behavior | Why it's fun |
|---|---|---|
| **Skeleton** | Walks straight at the nearest player, melee swipe. Comes in big rattling crowds. | The "swarm" baseline: satisfying to mow down with arcs. |
| **Slime** | Hops in bursts (pause, leap). Big slimes **split into 2 small slimes** on death. | Hopping rhythm forces dodging; splitting rewards AoE. |
| **Bat** | Fast flyer that weaves side to side over props. Arrives in swarms. | Forces you to turn and deal with fast flankers. |
| **Skeleton Archer** | Keeps its distance and shoots arrows that lead your movement. | Punishes standing still; makes you dive into the crowd. |
| **Bomb Shroom** | Runs at you, stops, flashes red and **explodes** (jump to dodge). | Telegraphed threat: read the red ring and get out. |
| **Golem** | Slow stone bruiser, telegraphed ground **stomp** (jump to dodge). | A wall that reshapes the fight. |
| **Magma Slime** *(volcano)* | Hotter, tougher slime that splits into small magma slimes. | Same rhythm as slimes, more pressure. |
| **Fire Imp** *(volcano)* | Flyer that circles at range and throws fireballs. | Ranged pressure from above that you have to chase down. |

**Elites:** any enemy can spawn as an *Elite* (1.8x size, 8x HP, floating gold crown, drops a chest).

**Bosses:** *Slime Mother* / *Magma Queen* (5:30, bursts into slimes), *Ancient Golem* (7:30) and
*Bone King* (9:00). Huge HP with a boss bar; they drop a chest per player, a magnet, a heal and a pile of XP.

### Spawning & difficulty
- The **Wave asset** is a timeline of entries: `minute → which enemy, spawn rate, group size, elite chance, ramp curve`,
  plus one-off horde bursts and boss events.
- Spawn rates ease in (calm first minutes) and ramp steeply toward the end.
- Enemies spawn 22–30 m away around a random living player.
- HP scales with run time (+25%/min plus a quadratic term) and +25% per extra player (spawn rate +40%); speed +5%/min (max +35%).
- Max alive cap (default 260) keeps the network and CPU healthy.

---

## 8. Pickups & economy

- **XP crystals:** blue (1+), green (5+), purple (25+). Vacuum to you inside pickup radius. All XP goes to the **team**.
- **Chests:** dropped by elites and bosses. Walk into one for a free upgrade pick.
- **Crits:** every hit has a 10% (+Luck) chance to deal double damage and shows a yellow `CRIT!` number.
- **Health orbs:** rare drop, heal 20%.
- **Magnet orb:** pulls every gem on the map to you.

---

## 9. Maps

The host picks the map in the lobby (`<` `>` under **Map**); everyone sees the choice. Each map is a
`MapDefinition` asset (`Content/Maps/`): scene, wave timeline, music, difficulty, lobby preview.

### Haunted Keep (`Game` scene)
- ~120 x 120 m arena on generated **terrain**: rolling ground, six raised plateaus with steep cliffs and a
  ramp each (enemies scramble up cliffs, so nothing is a safe spot), hills rising outside the arena.
- A ring of castle walls and towers frames the arena; ruined towers, walls, arches, rune stones,
  braziers, banners, a graveyard, trees, bushes, flowers, mushrooms and grass fill it.
- Mountains and a pixel cloud sky on the horizon; teal distance fog. Five charge shrines.

### Molten Caldera (`Volcano` scene, danger x1.15)
- Dark basalt plains cut by two **lava rivers** with rock bridges, three lava lakes, and basalt mesas with ramps.
- **Lava burns players** (about 15 HP/s, ignores armor) but enemies walk right over it, so a river is
  a shortcut for them and a hazard for you. Jump (or double jump) across.
- Charred trees, obsidian spires, fire totems, sulfur vents, glowing lava rocks; a ring of basalt columns
  frames the arena; smoking volcanoes and ash mountains on a red horizon; rising embers.
- Own wave timeline (`VolcanoRun`): magma slimes and fire imps join the usual horde, and the Magma Queen
  replaces the Slime Mother. Own music track (heavier, D phrygian).

Enemies walk around props using a static obstacle grid (no NavMesh needed).

---

## 10. Art & audio direction

- **Style:** Megabonk-like: low-poly models with chunky, point-filtered pixel textures (bricks, leaves, wood
  grain, noise) projected by the `PixelLit` shader; glowing crystals/runes/fire with bloom; blue dusk sky.
  Models are generated with Blender scripts (`Tools/Blender`) and exported as FBX.
- **VFX:** pixel slashes, sky-strike lightning, tumbling cube debris on death, hit sparks, light pillars on
  level-up, floating motes, footstep dust, arrow trails.
- **Palette:** cold blue-grey ground, warm player colors (Knight blue, Ranger green, Mage purple,
  Alchemist orange), bone-white skeletons, acid-green slimes.
- **UI:** pixel-art windows with metal frames and rivets, Silkscreen pixel font, rarity-colored upgrade cards
  (Common green / Rare blue / Epic purple) showing stat changes, pixel item icons with outlines.
- **Audio:** synthesized SFX (swings, bow twangs, zaps, glass shatter, bone crunch, slime squelch,
  gem pings with rising pitch, level-up chime, UI clicks) + a looping synth music track for the
  menu and one for the run. Generated with `Tools/Audio` scripts so variants are easy to remake.

---

## 11. Technical architecture

### Networking (Photon Fusion 2, Host mode)
- **Host = authority.** The host simulates enemies, damage, XP and spawning. Clients predict
  their own movement for responsive controls.
- Enemies and pickups are lightweight NetworkObjects. Weapon hits are resolved on the host;
  weapon **visuals** are played on every client via RPC, so projectiles aren't networked objects
  (cheap bandwidth, hundreds of effects).
- Each player has a persistent **PlayerData** object (name, character, ready state, stats) that
  survives the Lobby → Game scene change.
- Sessions are found by a short **room code** (session name) or by Quick Join.

### Data-driven content (designer workflow)
Everything a designer tunes is a **ScriptableObject** in `Assets/_Game/Content`:

```
CharacterDefinition  – stats, starting weapon, model prefab, color, icon
WeaponDefinition     – behavior type, 5 level rows, VFX/SFX, icon, rarity
PowerupDefinition    – stat modifier per level, max level, icon, rarity
EnemyDefinition      – HP, speed, damage, XP drop, behavior settings, prefab, SFX
WaveDefinition       – spawn timeline
GameConfig           – run length, scaling, caps, revive time, XP curve
```

A single **GameDatabase** asset auto-collects every definition (menu: *MultiBash ▸ Refresh Database*),
so **adding content = right-click ▸ Create ▸ MultiBash ▸ ...** with no code and no manual list editing.
The **MultiBash ▸ Content Browser** window shows every enemy/weapon/powerup/character in one place.

### Folder layout
```
Assets/_Game/
  Content/            ← designers live here (ScriptableObjects + gameplay prefabs, one folder per thing)
    Characters/  Knight/ Ranger/ Mage/ Alchemist/
    Weapons/     Greatsword/ Longbow/ StormStaff/ PoisonFlask/ OrbitingBlades/ HolyAura/
    Powerups/    Might.asset, Swiftness.asset, ...
    Enemies/     Skeleton/ Slime/
    Waves/       DefaultRun.asset
    Pickups/
    GameConfig.asset, GameDatabase.asset
  Art/
    Models/      Characters/ Enemies/ Weapons/ Environment/ Pickups/
    Materials/   Textures/   VFX/
  UI/
    Icons/       Weapons/ Powerups/ Characters/
    Sprites/     Prefabs/
  Audio/
    Music/       SFX/ Weapons/ Enemies/ Player/ Pickups/ UI/
  Prefabs/       Network/ Systems/ Environment/
  Scenes/        MainMenu, Lobby, Game
  Scripts/       Core/ Networking/ Player/ Combat/ Enemies/ Pickups/ Progression/ UI/ Audio/ Data/ Editor/
Tools/
  Blender/       model generator scripts (.py)
  Audio/         SFX/music synth scripts (.py)
  Textures/      icon/texture generator scripts (.py)
```

### Testing on one computer
- **Multiplayer Play Mode** (Unity package) is installed: *Window ▸ Multiplayer ▸ Multiplayer Play Mode*,
  enable Player 2–4, press Play, and each virtual player gets its own window.
- Or make a build (*File ▸ Build Profiles*), run the build and host there, then join from the Editor.

---

## 12. Roadmap after this first playable

1. Boss at minute 10 (Skeleton King).
2. More enemies: Bat (fast flier), Golem (tank), Necromancer (summons skeletons).
3. Weapon evolutions (max weapon + matching powerup = evolved weapon).
4. Meta progression: unlock characters, permanent upgrades with gold.
5. Multiple maps and difficulty tiers.
6. Gamepad UI navigation, settings menu (volume, sensitivity, graphics).
