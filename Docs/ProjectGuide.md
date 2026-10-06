# MultiBash project guide

Where things live, and where to go to change how the game plays.

## Tuning the game (start here)

Open a game scene (`Assets/_Game/Scenes/Game.unity` or `Volcano.unity`) and select an object under `--- Managers ---`.

| Object | What it controls | Settings asset |
|---|---|---|
| **ProgressionManager** | Run length, team leveling and XP curve, upgrade offers (rerolls, evolve level, treasure luck, Power Surge), enemy toughness (per minute / team level / party size), elites and bosses, the 3 enemy stages, spawn rate and burst size, drops and gem merging, kill combo / FRENZY, downed and revive | `Content/Settings/ProgressionSettings.asset` |
| **CombatManager** | Hero base stats, global damage / cooldown / area / speed knobs, movement (jump, slide), damage spread, crits, knockback, damage taken and invulnerability, enemy damage, item effects (Thorns, Execution, Phoenix Feather), screen shake, damage numbers, low-HP warning | `Content/Settings/CombatSettings.asset` |
| **GameManager** | Which map this scene is (`map`: waves, music, ambience, intro line, difficulty) | `Content/Maps/*.asset` |

* Every field has a tooltip. Values apply **live while playing**.
* In play mode the managers also show live readouts (run time, level, enemy HP multiplier, alive enemies, your stats) and test buttons: +1 / +5 levels, +3 chests, skip time, next stage, kill all, spawn Treasure Slime / boss, god mode, heal, max weapons, Power Surge, let the bot play.
* **Copy for this map** makes a separate settings asset for that scene, e.g. a harder volcano.
* The formulas themselves (enemy HP, XP per level, stage) are small methods at the bottom of `ProgressionSettings.cs`.

### Multiplayer rules for tuning
* The **host** decides the run: enemy HP and damage, spawns, XP, drops and player damage all come from the hosting machine's settings. Tweak on the machine that hosts.
* **Movement and hero base stats** are also predicted on each player's own machine. After changing *Movement* or *Hero base stats*, make a new build for your friends so everyone matches.
* **Audio** is local: every player has their own volumes.

### Other content you will want to edit
| What | Where |
|---|---|
| What spawns when (enemy timelines, hordes, bosses, announcements) | `Content/Waves/DefaultRun.asset`, `VolcanoRun.asset` |
| Per-weapon numbers (damage, cooldown, count, area per level) and evolutions | `Content/Weapons/**` (evolved forms in `Weapons/Evolved`) |
| Tomes (passives) | `Content/Powerups/*.asset` |
| Enemies (HP, speed, attacks, boss settings, fodder, stage gear size) | `Content/Enemies/**` |
| Heroes (stats, starting weapon, description) | `Content/Characters/**` |
| Maps (scene, waves, music, ambience, intro line, difficulty, preview) | `Content/Maps/*.asset` |
| Shared sounds and music | `Audio/AudioLibrary.asset` |
| UI colors and fonts | `Content/Resources/UITheme.asset` |

The **Content Browser** (`MultiBash > Content Browser`) lists all of it in one window.

> Note: `MultiBash > Setup > Reset Content Data To Defaults` rewrites the content assets (weapons, enemies, waves...) from
> `MultiBashSetup.Content.cs`. It never touches the two settings assets above. Use the inspector's **Reset** on a settings
> asset to go back to the code defaults.

## Maps

| Map | Scene | Builder | Look and hook |
|---|---|---|---|
| Haunted Keep | `Game.unity` | `MultiBashSetup.World.cs` (`BuildGameScene`) | Golden dusk. The ruined keep on its hill (north), graveyard and glowing crypt (east), the witch wood with a rune circle and bounce mushrooms (west), the brook with bridges, windmill and knight statue (south). |
| Molten Caldera | `Volcano.unity` | `MultiBashSetup.Volcano.cs` | Smoky violet dusk over lava rivers. Dragon ribcage arching over the middle lava crossing, dragon skull and claws, dwarven forge, titan's hammer, pink crystal fields, steam-vent bounce pads, lava falls on the caldera walls. Lava burns. |
| Frostfall Peaks | `Frost.unity` | `MultiBashSetup.World.cs` (`BuildFrostScene`) | Moonlit night with aurora and snowfall. Frozen titan, viking camp, igloo village, rune monolith ring at the spawn, frozen waterfalls, and a slippery frozen lake (IceZone). |

`MultiBash > Setup > Rebuild Scenes Only` regenerates all of them (terrain heights and painting, props, lights, network objects).
Shared building blocks (prop scattering with spacing and roads, breakables, pads, shrines, walls, lighting) are in the
`Dresser` class and helpers at the top of `MultiBashSetup.World.cs`. The menu and lobby use `FrontEndSet` (dusk meadow with the keep).

## Interactables

| What | Script | Notes |
|---|---|---|
| Smashable props (crates, sacks, urns, barrels, ice crates) | `Pickups/Breakables.cs` | One scene NetworkObject holds every prop (children). Walk / slide into one or hit it with any attack: debris, a sound, gems and sometimes a heart, magnet or chest. Grows back after `respawnSeconds`. Host decides, everyone sees. |
| Bounce pads (mushrooms, steam vents, frost geysers) | `Core/JumpPad.cs` | Scene data: each peer predicts the launch in `PlayerCharacter` (`PadTick` replicates the FX). Tune `launch` / `radius` on the pad. |
| Slippery ice | `Core/IceZone.cs` | Ellipse; low grip + long glides while grounded on it. |
| Windmill blades | `Core/Spinner.cs` | Purely visual. |

## Art pipelines (Blender, headless)

| Script | Makes |
|---|---|
| `Tools/Blender/heroes_v6.py` | The four heroes (sculpted lofts, baked pixel shading, skinned). |
| `Tools/Blender/creatures_v6.py` | **Every enemy** in the same style: per-creature skeleton (bones named like the heroes so `ProceduralRig` animates them), lofted bodies and tubes, painted pixel textures. Output `Art/Models/Creatures/<Name>.fbx` + `Textures/Characters/T_Char_<Name>.png`. `-- Yeti --preview` renders a preview. Never build creatures from mashed primitives. |
| `Tools/Blender/world_models.py` | Landmarks and props for the three maps (keep, crypt, windmill, dragon bones, forge, frozen titan, igloos...). |
| `Tools/Blender/generate_models.py` | Older props, weapons, pickups and helpers. |
| `Tools/Textures/generate_textures.py` | Palette, terrain layers (`terrain`, `volcano`, `frost`, `keep`), VFX (rings, runic aura ring), UI and icons. |
| `Tools/Audio/world_audio.py` | Footsteps, landing, bounce, smash, frost enemy sounds, map ambiences (`Audio/Ambience`), Frostfall music. |

Enemy prefabs are rebuilt automatically when their model or scale changes in `MultiBashSetup.Prefabs.cs` (`BuildEnemyPrefab`).

## Audio

`AudioManager` (on the persistent `Prefabs/Systems/Resources/GameServices` prefab) routes everything through
`Audio/MultiBashMixer.mixer`:

| Mixer group | Used for | Exposed volume |
|---|---|---|
| Music | map music, boss theme, menu music (crossfades) | `MusicVolume` |
| SFX | 3D world sounds: weapons, enemies, pickups | `SFXVolume` |
| UI | interface and personal cues: clicks, level up, gem combo, heartbeat | `UIVolume` |

Each map also has a looping **ambience** bed (wind and crickets, lava rumble, howling wind) on the SFX channel, set on the map asset.

* In code, use `AudioManager.PlayMusic` / `Play` (world, SFX) / `PlayUI`.
* Players set the three volumes in the pause menu; they're saved per machine.
* Open the mixer to add effects or rebalance the groups.

## Scene layout

Every scene uses the same groups (rebuilds keep them; re-run `MultiBash > Organize Scene Hierarchy` after adding objects by hand):

```
--- Managers ---     GameManager, ProgressionManager, CombatManager, FxManager
--- Gameplay ---     shrines, lava, breakables, jump pads, frozen lake
--- Camera & UI ---  CameraRig (+ camera), HUD / LobbyUI / MainMenuUI
--- Showcase ---     menu / lobby display models and pedestals
--- Environment ---  Sun, PostProcess, Terrain, ArenaWalls, Props
```

Scenes are generated by `Scripts/Editor/MultiBashSetup.Scenes.cs` (Haunted Keep) and `MultiBashSetup.Volcano.cs`. Hand edits
are lost if you run *Rebuild Scenes*.

## Folders

```
Assets/_Game/
  Art/        Models (FBX from Tools/Blender), Materials, Textures, Shaders, VFX
  Audio/      Music, SFX, AudioLibrary.asset, MultiBashMixer.mixer
  Content/    Settings (Progression / Combat), Characters, Weapons, Powerups, Enemies, Waves, Maps, Pickups, GameConfig, Resources
  Prefabs/    Network (player prefabs), Environment (props), Systems (GameServices)
  Scenes/     MainMenu, Lobby, Game (Haunted Keep), Volcano (Molten Caldera), Frost (Frostfall Peaks)
  Scripts/
    Managers/     ProgressionManager, CombatManager (tuning control panels)
    Progression/  GameManager (run state, XP, spawning calls), UpgradeSystem (offers, evolutions)
    Combat/       WeaponSystem (weapon logic), CombatWorld (projectiles / puddles / blasts), FxManager (visual effects)
    Enemies/      Enemy, EnemySpawner (wave timelines), EnemyRegistry (spatial lookups)
    Player/       PlayerCharacter, CameraRig
    Pickups/      gems, orbs, chests, shrines, lava
    Data/         ScriptableObject types (settings, definitions, stats)
    Audio/        AudioManager
    Networking/   Photon Fusion launcher, lobby data, input
    UI/           HUD, lobby, menus, UI kit
    Core/         procedural animation rig, ground queries, bot autopilot
    Editor/       setup tools, manager inspectors, content browser
Tools/        Blender model / hero scripts, texture + icon generator, audio + music generator
Docs/         design doc, this guide, art reference
```
