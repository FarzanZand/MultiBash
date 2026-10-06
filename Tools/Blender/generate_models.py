"""
MultiBash low-poly model generator.

Run headless:
  "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" -b -P Tools/Blender/generate_models.py

Every model is built from primitives, UV-mapped onto the shared palette texture
(Tools/palette.json -> Assets/_Game/Art/Textures/T_Palette.png) and exported as FBX
into Assets/_Game/Art/Models/<Category>/<Name>.fbx.

Characters and enemies are split into named parts (Body, ArmL, ArmR, LegL, LegR) with pivots
at the joints so the game can animate them procedurally. The game attaches held weapons to ArmR.

Conventions: 1 unit = 1 meter, Z up, characters face -Y (Blender front view).
"""
import bpy
import json
import math
import os
import random

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "Assets", "_Game", "Art", "Models")
with open(os.path.join(ROOT, "Tools", "palette.json")) as f:
    PALETTE = json.load(f)

GRID = PALETTE["grid"]
COLOR_NAMES = list(PALETTE["colors"].keys())


def uv_for(color):
    i = COLOR_NAMES.index(color)
    cx, cy = i % GRID, i // GRID
    # Row 0 is the TOP of the texture image; UV v=1 is the top.
    return ((cx + 0.5) / GRID, 1.0 - (cy + 0.5) / GRID)


# ----------------------------------------------------------------------------- scene helpers

def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def palette_material():
    mat = bpy.data.materials.get("M_Palette")
    if mat is None:
        mat = bpy.data.materials.new("M_Palette")
    return mat


def _finish(o, size, color):
    o.scale = size
    bpy.context.view_layer.objects.active = o
    o.select_set(True)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    o.select_set(False)
    me = o.data
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    uv = uv_for(color)
    for loop in me.uv_layers.active.data:
        loop.uv = uv
    me.materials.clear()
    me.materials.append(palette_material())
    for p in me.polygons:
        p.use_smooth = False
    return o


def part(kind, loc, size, color, rot=(0, 0, 0), verts=8, r2=0.0, sub=1):
    r = tuple(math.radians(a) for a in rot)
    if kind == "cube":
        bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=r)
    elif kind == "cyl":
        bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=0.5, depth=1, location=loc, rotation=r)
    elif kind == "cone":
        bpy.ops.mesh.primitive_cone_add(vertices=verts, radius1=0.5, radius2=r2, depth=1, location=loc, rotation=r)
    elif kind == "ico":
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=sub, radius=0.5, location=loc, rotation=r)
    elif kind == "sphere":
        bpy.ops.mesh.primitive_uv_sphere_add(segments=verts, ring_count=max(4, verts // 2), radius=0.5, location=loc, rotation=r)
    elif kind == "torus":
        bpy.ops.mesh.primitive_torus_add(major_segments=verts, minor_segments=4, major_radius=0.5, minor_radius=0.12, location=loc, rotation=r)
    else:
        raise ValueError(kind)
    return _finish(bpy.context.active_object, size, color)


def group(name, parts, pivot):
    """Join parts into one object named `name` with its origin at `pivot`."""
    bpy.ops.object.select_all(action="DESELECT")
    for p in parts:
        p.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    if len(parts) > 1:
        bpy.ops.object.join()
    o = bpy.context.active_object
    o.name = name
    o.data.name = name
    bpy.context.scene.cursor.location = pivot
    bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
    bpy.context.scene.cursor.location = (0, 0, 0)
    o.select_set(False)
    return o


def empty(name, loc):
    o = bpy.data.objects.new(name, None)
    o.location = loc
    bpy.context.scene.collection.objects.link(o)
    return o


def parent(child, par):
    child.parent = par
    child.matrix_parent_inverse = par.matrix_world.inverted()


def export(category, name):
    path = os.path.join(OUT, category, name + ".fbx")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.fbx(
        filepath=path,
        use_selection=True,
        object_types={"MESH", "EMPTY"},
        apply_scale_options="FBX_SCALE_ALL",
        axis_forward="-Z",
        axis_up="Y",
        bake_space_transform=True,
        mesh_smooth_type="FACE",
        add_leaf_bones=False,
        bake_anim=False,
    )
    print("exported", path)


def build(category, name, fn):
    JOINTS.clear()
    reset()
    fn()
    if name in SMOOTH_ENEMIES:
        _smooth_all()
    export(category, name)


def root_with(parts_by_name):
    root = empty("Root", (0, 0, 0))
    for o in parts_by_name:
        parent(o, root)
    return root


# ----------------------------------------------------------------------------- humanoid base (Megabonk-ish proportions, ~1.9m)

HIP_Z = 0.95
SHOULDER_Z = 1.55


# sub-parts (Head, ForeArm*, Shin*) are exported flat under Root (nested FBX transforms break with baked axes);
# ProceduralRig re-parents them in Unity.
JOINTS = []
ELBOW_Z = 1.25
KNEE_Z = 0.52
NECK_Z = 1.62


def humanoid(c, body_extra=(), arm_extra_l=(), arm_extra_r=(), head_extra=(), skirt=None, head=True):
    """c: palette names for torso, chest, arms, legs, boots, belt, skin, hands.
    Hierarchy (for procedural animation): Body > Head, ArmL > ForeArmL, ArmR > ForeArmR, LegL > ShinL, LegR > ShinR."""
    body = [
        part("cube", (0, 0, 0.99), (0.40, 0.26, 0.18), c["legs"]),           # hips
        part("cube", (0, 0, 1.17), (0.38, 0.25, 0.22), c["torso"]),          # waist
        part("cube", (0, 0, 1.40), (0.50, 0.30, 0.30), c.get("chest", c["torso"])),  # chest
        part("cube", (0, 0, 1.08), (0.42, 0.28, 0.07), c["belt"]),           # belt
        part("cube", (0, 0, 1.60), (0.13, 0.13, 0.10), c["skin"]),           # neck
    ]
    if skirt:
        body.append(part("cone", (0, 0, 0.58), (0.62, 0.50, 0.86), skirt, r2=0.42, verts=8))
    body += [f() for f in body_extra]
    Body = group("Body", body, (0, 0, HIP_Z))

    hd = []
    if head:
        hd += [
            part("cube", (0, 0, 1.79), (0.29, 0.29, 0.31), c["skin"]),
            part("cube", (-0.065, -0.147, 1.80), (0.055, 0.02, 0.045), "black"),
            part("cube", (0.065, -0.147, 1.80), (0.055, 0.02, 0.045), "black"),
            part("cube", (0, -0.15, 1.74), (0.05, 0.03, 0.06), c.get("skin_dark", c["skin"])),
        ]
    hd += [f() for f in head_extra]
    if hd:
        JOINTS.append(group("Head", hd, (0, 0, NECK_Z)))

    def arm(side, extra):
        x = 0.32 * side
        upper = group("ArmR" if side < 0 else "ArmL", [part("cube", (x, 0, 1.40), (0.15, 0.16, 0.30), c["arms"])], (x, 0, SHOULDER_Z))
        fore = [
            part("cube", (x, -0.01, 1.11), (0.13, 0.14, 0.30), c.get("forearm", c["arms"])),
            part("cube", (x, -0.01, 0.91), (0.12, 0.13, 0.11), c.get("hands", c["skin"])),
        ]
        fore += [f() for f in extra]
        JOINTS.append(group("ForeArmR" if side < 0 else "ForeArmL", fore, (x, 0, ELBOW_Z)))
        return upper

    def leg(side):
        x = 0.11 * side
        thigh = group("LegR" if side < 0 else "LegL", [part("cube", (x, 0, 0.72), (0.17, 0.19, 0.42), c["legs"])], (x, 0, HIP_Z))
        shin = group("ShinR" if side < 0 else "ShinL", [
            part("cube", (x, 0, 0.32), (0.15, 0.17, 0.42), c.get("shins", c["legs"])),
            part("cube", (x, -0.04, 0.06), (0.17, 0.28, 0.12), c["boots"]),
        ], (x, 0, KNEE_Z))
        JOINTS.append(shin)
        return thigh

    parts = [Body, arm(1, arm_extra_l), arm(-1, arm_extra_r), leg(-1), leg(1)]
    return root_with(parts + JOINTS)

def knight():
    c = dict(torso="steel_dark", chest="steel", arms="steel", forearm="steel_dark", legs="steel_dark", shins="steel",
             boots="dark_iron", belt="leather", skin="steel", hands="steel_dark")
    humanoid(
        c, head=False,
        body_extra=[
            lambda: part("cube", (0, -0.155, 1.33), (0.30, 0.02, 0.44), "cloth_white"),     # surcoat
            lambda: part("cube", (0, -0.168, 1.38), (0.05, 0.01, 0.26), "cloth_red"),       # cross
            lambda: part("cube", (0, -0.168, 1.42), (0.18, 0.01, 0.05), "cloth_red"),
            lambda: part("cube", (0, -0.16, 0.99), (0.26, 0.02, 0.22), "cloth_white"),     # tabard skirt
            lambda: part("ico", (-0.33, 0, 1.56), (0.24, 0.24, 0.16), "steel", sub=1),      # pauldrons
            lambda: part("ico", (0.33, 0, 1.56), (0.24, 0.24, 0.16), "steel", sub=1),
            lambda: part("cube", (0, 0, 1.08), (0.44, 0.30, 0.05), "gold_dark"),            # belt buckle line
        ],
        head_extra=[
            lambda: part("cyl", (0, 0, 1.81), (0.32, 0.32, 0.38), "steel", verts=8),        # bucket helm
            lambda: part("cyl", (0, 0, 2.00), (0.30, 0.30, 0.03), "steel_dark", verts=8),
            lambda: part("cube", (0, -0.155, 1.83), (0.20, 0.02, 0.03), "black"),           # visor slit
            lambda: part("cube", (0, -0.155, 1.76), (0.03, 0.02, 0.10), "black"),
            lambda: part("cube", (0, -0.16, 1.70), (0.10, 0.02, 0.02), "gold"),
        ],
    )


def ranger():
    c = dict(torso="leather", chest="leather", arms="ranger_green", forearm="leather_dark", legs="leather_dark",
             shins="leather_dark", boots="leather_dark", belt="leather_dark", skin="skin", skin_dark="skin_dark", hands="leather")
    humanoid(
        c,
        body_extra=[
            lambda: part("cube", (0, 0.17, 1.12), (0.48, 0.04, 0.85), "ranger_dark"),      # cape
            lambda: part("cyl", (0.10, 0.20, 1.40), (0.13, 0.13, 0.50), "leather", rot=(-12, 0, -18), verts=6),  # quiver
            lambda: part("cube", (0.02, 0.24, 1.70), (0.03, 0.03, 0.14), "cloth_red", rot=(-12, 0, -18)),
            lambda: part("cube", (0.12, 0.24, 1.70), (0.03, 0.03, 0.14), "cloth_red", rot=(-12, 0, -18)),
            lambda: part("cube", (0, -0.155, 1.33), (0.05, 0.02, 0.48), "leather_dark", rot=(0, 32, 0)),
        ],
        head_extra=[
            lambda: part("cube", (0, 0.07, 1.85), (0.37, 0.34, 0.39), "ranger_green"),     # hood (open at the front)
            lambda: part("cube", (0, -0.1, 2.0), (0.37, 0.12, 0.08), "ranger_dark"),       # hood brim
            lambda: part("cone", (0, 0.18, 1.98), (0.22, 0.22, 0.26), "ranger_green", rot=(-60, 0, 0), verts=4),
            lambda: part("cube", (0, 0.05, 1.56), (0.46, 0.34, 0.10), "ranger_green"),     # mantle
        ],
    )


def mage():
    c = dict(torso="mage_purple", chest="mage_purple", arms="mage_purple", forearm="mage_dark", legs="mage_dark",
             boots="black", belt="gold", skin="skin", skin_dark="skin_dark", hands="skin")
    humanoid(
        c, skirt="mage_purple",
        body_extra=[
            lambda: part("cube", (0, -0.155, 1.30), (0.07, 0.02, 0.50), "gold"),
            lambda: part("cone", (0, -0.15, 1.58), (0.22, 0.08, 0.30), "cloth_white", rot=(180, 0, 0), verts=6),  # beard
            lambda: part("cube", (0, 0.05, 1.56), (0.52, 0.34, 0.08), "mage_dark"),        # collar
        ],
        head_extra=[
            lambda: part("cyl", (0, 0, 1.95), (0.62, 0.62, 0.04), "mage_dark", verts=10),   # brim
            lambda: part("cone", (0, 0.04, 2.24), (0.36, 0.36, 0.60), "mage_purple", verts=8, rot=(-14, 0, 0)),
            lambda: part("cube", (0, 0, 1.99), (0.36, 0.36, 0.05), "gold"),
        ],
    )


def alchemist():
    c = dict(torso="cloth_white", chest="cloth_white", arms="alch_orange", forearm="cloth_white", legs="leather_dark",
             boots="black", belt="leather", skin="skin", skin_dark="skin_dark", hands="leather")
    humanoid(
        c,
        body_extra=[
            lambda: part("cube", (0, -0.155, 1.12), (0.34, 0.03, 0.70), "alch_orange"),    # apron
            lambda: part("cube", (0, 0.21, 1.33), (0.34, 0.16, 0.40), "leather"),          # backpack
            lambda: part("cyl", (-0.09, 0.24, 1.60), (0.08, 0.08, 0.16), "poison", verts=6),
            lambda: part("cyl", (0.09, 0.24, 1.60), (0.08, 0.08, 0.16), "gem_blue", verts=6),
            lambda: part("cyl", (-0.21, -0.08, 1.06), (0.09, 0.09, 0.13), "gem_red", verts=6),
        ],
        head_extra=[
            lambda: part("cube", (0, 0.02, 1.97), (0.32, 0.31, 0.08), "leather_dark"),     # hair
            lambda: part("cyl", (-0.07, -0.15, 1.86), (0.10, 0.10, 0.04), "gold", rot=(90, 0, 0), verts=8),  # goggles
            lambda: part("cyl", (0.07, -0.15, 1.86), (0.10, 0.10, 0.04), "gold", rot=(90, 0, 0), verts=8),
            lambda: part("cyl", (-0.07, -0.17, 1.86), (0.07, 0.07, 0.01), "glass", rot=(90, 0, 0), verts=8),
            lambda: part("cyl", (0.07, -0.17, 1.86), (0.07, 0.07, 0.01), "glass", rot=(90, 0, 0), verts=8),
            lambda: part("cube", (0, 0, 1.86), (0.31, 0.30, 0.03), "leather_dark"),
        ],
    )


# ----------------------------------------------------------------------------- enemies

def skeleton():
    body = [
        part("cyl", (0, 0.03, 1.25), (0.06, 0.06, 0.62), "bone_shadow", verts=6),   # spine
        part("cube", (0, 0, 0.97), (0.34, 0.18, 0.09), "bone"),                     # pelvis
        part("cube", (0, 0, 1.53), (0.44, 0.15, 0.05), "bone"),                     # collarbones
    ]
    for i, z in enumerate((1.45, 1.36, 1.27, 1.19)):
        w = 0.40 - i * 0.04
        body.append(part("cube", (0, -0.01, z), (w, 0.22, 0.035), "bone"))         # ribs
    body += [
        part("cube", (0, 0, 1.62), (0.07, 0.07, 0.10), "bone_shadow"),
    ]
    Body = group("Body", body, (0, 0, HIP_Z))
    skull = [
        part("cube", (0, 0, 1.77), (0.26, 0.27, 0.25), "bone"),                     # skull
        part("cube", (0, -0.02, 1.64), (0.20, 0.20, 0.07), "bone_shadow"),          # jaw
        part("cube", (-0.06, -0.137, 1.79), (0.075, 0.02, 0.07), "black"),          # sockets
        part("cube", (0.06, -0.137, 1.79), (0.075, 0.02, 0.07), "black"),
        part("cube", (-0.06, -0.142, 1.79), (0.025, 0.02, 0.025), "eye_red"),
        part("cube", (0.06, -0.142, 1.79), (0.025, 0.02, 0.025), "eye_red"),
        part("cube", (0, -0.137, 1.71), (0.035, 0.02, 0.04), "black"),
        part("cube", (0, -0.12, 1.665), (0.16, 0.02, 0.02), "black"),               # teeth line
    ]
    JOINTS.append(group("Head", skull, (0, 0, NECK_Z)))

    def arm(side):
        x = 0.27 * side
        upper = group("ArmR" if side < 0 else "ArmL", [part("cyl", (x, 0, 1.38), (0.055, 0.055, 0.32), "bone", verts=5)], (x, 0, SHOULDER_Z))
        ps = [
            part("cyl", (x, -0.01, 1.08), (0.045, 0.045, 0.30), "bone_shadow", verts=5),
            part("cube", (x, -0.01, 0.90), (0.08, 0.09, 0.08), "bone"),
        ]
        if side < 0:  # right hand: rusty blade
            ps.append(part("cube", (x, -0.15, 0.91), (0.03, 0.36, 0.05), "dark_iron"))
            ps.append(part("cube", (x, -0.01, 0.91), (0.03, 0.05, 0.12), "leather_dark"))
        JOINTS.append(group("ForeArmR" if side < 0 else "ForeArmL", ps, (x, 0, ELBOW_Z)))
        return upper

    def leg(side):
        x = 0.10 * side
        thigh = group("LegR" if side < 0 else "LegL", [part("cyl", (x, 0, 0.72), (0.06, 0.06, 0.44), "bone", verts=5)], (x, 0, HIP_Z))
        shin = group("ShinR" if side < 0 else "ShinL", [
            part("cyl", (x, 0, 0.30), (0.05, 0.05, 0.42), "bone_shadow", verts=5),
            part("cube", (x, -0.04, 0.04), (0.09, 0.20, 0.06), "bone"),
        ], (x, 0, KNEE_Z))
        JOINTS.append(shin)
        return thigh

    parts = [Body, arm(-1), arm(1), leg(-1), leg(1)]
    root_with(parts + JOINTS)


def slime():
    body = [
        part("ico", (0, 0, 0.42), (1.0, 1.0, 0.80), "slime_green", sub=2),
        part("ico", (0, 0.05, 0.38), (0.60, 0.60, 0.48), "slime_core", sub=1),
        part("cube", (-0.18, -0.46, 0.52), (0.18, 0.04, 0.22), "white"),
        part("cube", (0.18, -0.46, 0.52), (0.18, 0.04, 0.22), "white"),
        part("cube", (-0.18, -0.48, 0.50), (0.09, 0.03, 0.12), "black"),
        part("cube", (0.18, -0.48, 0.50), (0.09, 0.03, 0.12), "black"),
        part("cube", (0, -0.44, 0.32), (0.22, 0.04, 0.05), "slime_dark"),
        part("ico", (0.20, 0.12, 0.86), (0.16, 0.16, 0.12), "slime_core", sub=1),
    ]
    Body = group("Body", body, (0, 0, 0))
    root_with([Body])


# ----------------------------------------------------------------------------- weapons (grip at origin, pointing +Z)

def greatsword():
    ps = [
        part("cube", (0, 0, 0.75), (0.12, 0.035, 1.10), "steel"),
        part("cone", (0, 0, 1.38), (0.12, 0.035, 0.18), "steel", verts=4, rot=(0, 0, 45)),
        part("cube", (0, 0, 0.75), (0.025, 0.045, 1.00), "steel_dark"),
        part("cube", (0, 0, 0.18), (0.44, 0.09, 0.07), "gold"),
        part("cube", (0, 0, 0.0), (0.06, 0.06, 0.30), "leather"),
        part("ico", (0, 0, -0.18), (0.10, 0.10, 0.10), "gold", sub=1),
    ]
    root_with([group("Mesh", ps, (0, 0, 0))])


def longbow():
    ps = []
    segs = 7
    for i in range(segs):
        t0 = -1 + 2 * i / segs
        t1 = -1 + 2 * (i + 1) / segs
        z0, z1 = t0 * 0.75, t1 * 0.75
        y0, y1 = -0.22 * (1 - t0 * t0), -0.22 * (1 - t1 * t1)
        mz, my = (z0 + z1) / 2, (y0 + y1) / 2
        ang = math.degrees(math.atan2(y1 - y0, z1 - z0))
        ps.append(part("cube", (0, my, mz), (0.05, 0.06, abs(z1 - z0) * 1.15), "wood" if i % 3 else "leather", rot=(-ang, 0, 0)))
    ps.append(part("cube", (0, 0, 0), (0.015, 0.015, 1.50), "rope"))
    ps.append(part("cube", (0, -0.22, 0), (0.08, 0.08, 0.20), "leather_dark"))
    root_with([group("Mesh", ps, (0, -0.22, 0))])


def storm_staff():
    ps = [
        part("cyl", (0, 0, 0.55), (0.06, 0.06, 1.50), "wood", verts=6),
        part("cyl", (0, 0, 1.25), (0.10, 0.10, 0.10), "gold", verts=6),
        part("ico", (0, 0, 1.45), (0.20, 0.20, 0.28), "lightning", sub=1),
        part("cone", (0.09, 0, 1.40), (0.05, 0.05, 0.22), "gold", verts=4, rot=(0, -25, 0)),
        part("cone", (-0.09, 0, 1.40), (0.05, 0.05, 0.22), "gold", verts=4, rot=(0, 25, 0)),
    ]
    root_with([group("Mesh", ps, (0, 0, 0))])


def poison_flask():
    ps = [
        part("ico", (0, 0, 0.14), (0.24, 0.24, 0.24), "poison", sub=1),
        part("cyl", (0, 0, 0.31), (0.08, 0.08, 0.14), "glass", verts=6),
        part("cyl", (0, 0, 0.41), (0.10, 0.10, 0.07), "wood", verts=6),
        part("cube", (0, -0.11, 0.16), (0.11, 0.02, 0.07), "cloth_white"),
    ]
    root_with([group("Mesh", ps, (0, 0, 0.1))])


def _flatten(o, rx):
    o.rotation_euler = (math.radians(rx), 0, 0)
    bpy.ops.object.select_all(action="DESELECT")
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.transform_apply(rotation=True)
    return o


def orbit_blade():
    ps = [
        part("cone", (0, 0, 0.25), (0.20, 0.05, 0.50), "steel", verts=4),
        part("cone", (0, 0, -0.10), (0.20, 0.05, 0.20), "steel", verts=4, rot=(180, 0, 0)),
        part("cube", (0, 0, 0), (0.06, 0.07, 0.06), "purple_glow"),
    ]
    root_with([_flatten(group("Mesh", ps, (0, 0, 0)), 90)])


def holy_aura_ring():
    root_with([group("Mesh", [part("torus", (0, 0, 0.05), (1.0, 1.0, 0.25), "gold", verts=24)], (0, 0, 0))])


def arrow():
    ps = [
        part("cyl", (0, 0, 0), (0.03, 0.03, 0.80), "wood", verts=5),
        part("cone", (0, 0, 0.45), (0.09, 0.09, 0.14), "steel", verts=4),
        part("cube", (0, 0, -0.34), (0.12, 0.01, 0.14), "cloth_red"),
        part("cube", (0, 0, -0.34), (0.01, 0.12, 0.14), "cloth_red"),
    ]
    root_with([_flatten(group("Mesh", ps, (0, 0, 0)), 90)])


def lightning_orb():
    root_with([group("Mesh", [part("ico", (0, 0, 0), (0.35, 0.35, 0.35), "lightning", sub=1)], (0, 0, 0))])


# ----------------------------------------------------------------------------- pickups

def crystal(color, light):
    def fn():
        ps = [
            part("cyl", (0, 0, 0.18), (0.22, 0.22, 0.30), color, verts=6),
            part("cone", (0, 0, 0.43), (0.22, 0.22, 0.20), color, verts=6),
            part("cone", (0, 0, -0.07), (0.22, 0.22, 0.20), color, verts=6, rot=(180, 0, 0)),
            part("cube", (0.06, -0.07, 0.22), (0.04, 0.02, 0.22), light),   # shine
        ]
        o = group("Mesh", ps, (0, 0, 0.18))
        o.rotation_euler = (0, math.radians(12), 0)
        root_with([o])
    return fn


def health_orb():
    ps = [
        part("ico", (-0.10, 0, 0.10), (0.24, 0.20, 0.24), "heart_red", sub=1),
        part("ico", (0.10, 0, 0.10), (0.24, 0.20, 0.24), "heart_red", sub=1),
        part("cone", (0, 0, -0.06), (0.38, 0.20, 0.26), "heart_red", verts=4, rot=(180, 0, 45)),
        part("cube", (-0.10, -0.10, 0.15), (0.06, 0.02, 0.06), "white"),
    ]
    root_with([group("Mesh", ps, (0, 0, 0))])


def magnet():
    ps = [
        part("cube", (-0.16, 0, 0.10), (0.12, 0.12, 0.34), "magnet_red"),
        part("cube", (0.16, 0, 0.10), (0.12, 0.12, 0.34), "magnet_red"),
        part("cube", (0, 0, -0.10), (0.44, 0.12, 0.12), "magnet_red"),
        part("cube", (-0.16, 0, 0.31), (0.12, 0.12, 0.10), "magnet_grey"),
        part("cube", (0.16, 0, 0.31), (0.12, 0.12, 0.10), "magnet_grey"),
    ]
    root_with([group("Mesh", ps, (0, 0, 0))])


def chest():
    base = [
        part("cube", (0, 0, 0.25), (0.90, 0.60, 0.50), "wood"),
        part("cube", (0, 0, 0.25), (0.94, 0.64, 0.08), "gold"),
        part("cube", (-0.40, 0, 0.25), (0.08, 0.64, 0.52), "gold"),
        part("cube", (0.40, 0, 0.25), (0.08, 0.64, 0.52), "gold"),
    ]
    lid = [
        part("cyl", (0, 0, 0.50), (0.60, 0.90, 0.90), "wood_dark", rot=(0, 90, 0), verts=8),
        part("cube", (0, -0.31, 0.50), (0.14, 0.04, 0.18), "gold"),
    ]
    root_with([group("Base", base, (0, 0, 0)), group("Lid", lid, (0, 0.30, 0.50))])


# ----------------------------------------------------------------------------- environment

def tombstone_a():
    ps = [
        part("cube", (0, 0, 0.50), (0.70, 0.22, 0.80), "stone"),
        part("cyl", (0, 0, 0.90), (0.70, 0.70, 0.22), "stone", rot=(90, 0, 0), verts=10),
        part("cube", (0, -0.115, 0.70), (0.36, 0.02, 0.06), "stone_dark"),
        part("cube", (0, -0.115, 0.58), (0.26, 0.02, 0.05), "stone_dark"),
        part("cube", (0, 0, 0.05), (0.90, 0.40, 0.12), "dirt"),
        part("cube", (0.22, -0.10, 1.05), (0.20, 0.04, 0.10), "moss"),
    ]
    root_with([group("Mesh", ps, (0, 0, 0))])


def tombstone_b():
    ps = [
        part("cube", (0, 0, 0.75), (0.18, 0.18, 1.40), "stone"),
        part("cube", (0, 0, 1.05), (0.70, 0.18, 0.18), "stone"),
        part("cube", (0, 0, 0.08), (0.50, 0.50, 0.16), "stone_dark"),
    ]
    o = group("Mesh", ps, (0, 0, 0))
    o.rotation_euler = (0, math.radians(8), 0)
    root_with([o])


def dead_tree():
    random.seed(7)
    ps = [
        part("cyl", (0, 0, 1.2), (0.45, 0.45, 2.4), "bark", verts=7),
        part("cone", (0, 0, 0.15), (0.9, 0.9, 0.3), "bark", verts=7, r2=0.25),
    ]
    for i in range(5):
        a = i * 72 + random.uniform(-15, 15)
        z = 1.5 + i * 0.22
        ar = math.radians(a)
        ln = random.uniform(0.9, 1.4)
        ps.append(part("cyl", (math.cos(ar) * ln * 0.45, math.sin(ar) * ln * 0.45, z + ln * 0.3), (0.16, 0.16, ln), "wood_dark", verts=5, rot=(0, 55, a)))
    root_with([group("Mesh", ps, (0, 0, 0))])


def tree_big(seed):
    def fn():
        random.seed(seed)
        h = random.uniform(3.4, 4.2)
        ps = [
            part("cyl", (0, 0, h / 2), (0.5, 0.5, h), "bark", verts=7),
            part("cone", (0, 0, 0.2), (1.1, 1.1, 0.4), "bark", verts=7, r2=0.3),
        ]
        for i in range(3):
            a = math.radians(i * 120 + random.uniform(-20, 20))
            ps.append(part("cyl", (math.cos(a) * 0.5, math.sin(a) * 0.5, h - 0.4), (0.18, 0.18, 1.2), "bark", verts=5, rot=(0, 50, math.degrees(a))))
        # chunky foliage clusters (cube-ish blobs like the reference)
        blobs = [(0, 0, h + 1.0, 2.8)]
        for i in range(4):
            a = math.radians(i * 90 + random.uniform(-25, 25))
            r = random.uniform(1.0, 1.5)
            blobs.append((math.cos(a) * r, math.sin(a) * r, h + random.uniform(0.2, 1.1), random.uniform(1.6, 2.2)))
        for (x, y, z, s) in blobs:
            ps.append(part("ico", (x, y, z), (s, s, s * 0.85), "leaf" if random.random() < 0.6 else "leaf_dark", sub=1,
                           rot=(random.uniform(0, 40), random.uniform(0, 40), random.uniform(0, 90))))
        root_with([group("Mesh", ps, (0, 0, 0))])
    return fn


def tree_pine():
    ps = [part("cyl", (0, 0, 1.0), (0.35, 0.35, 2.0), "bark", verts=6)]
    for i, (z, r) in enumerate(((1.6, 2.6), (2.7, 2.1), (3.7, 1.5), (4.6, 0.9))):
        ps.append(part("cone", (0, 0, z), (r, r, 1.6), "leaf_dark" if i % 2 == 0 else "ivy", verts=7))
    root_with([group("Mesh", ps, (0, 0, 0))])


def bush():
    random.seed(9)
    ps = []
    for i in range(4):
        ps.append(part("ico", (random.uniform(-0.5, 0.5), random.uniform(-0.5, 0.5), 0.45 + random.uniform(0, 0.2)),
                       (1.0, 1.0, 0.8), "leaf" if i % 2 else "leaf_dark", sub=1))
    for i in range(3):
        ps.append(part("ico", (random.uniform(-0.6, 0.6), random.uniform(-0.6, 0.6), 0.8), (0.12, 0.12, 0.12), "fire", sub=1))  # berries
    root_with([group("Mesh", ps, (0, 0, 0))])


def grass_tuft():
    random.seed(4)
    ps = []
    for i in range(7):
        a = random.uniform(0, 360)
        r = random.uniform(0, 0.25)
        ps.append(part("cone", (math.cos(math.radians(a)) * r, math.sin(math.radians(a)) * r, 0.25), (0.10, 0.04, random.uniform(0.4, 0.7)),
                       "grass_light" if i % 2 else "grass", verts=3, rot=(random.uniform(-15, 15), random.uniform(-15, 15), a)))
    root_with([group("Mesh", ps, (0, 0, 0))])


def log():
    ps = [
        part("cyl", (0, 0, 0.3), (0.6, 0.6, 2.2), "bark", rot=(0, 90, 0), verts=8),
        part("cyl", (1.11, 0, 0.3), (0.5, 0.5, 0.02), "wood", rot=(0, 90, 0), verts=8),
        part("cyl", (-1.11, 0, 0.3), (0.5, 0.5, 0.02), "wood", rot=(0, 90, 0), verts=8),
        part("cube", (0.3, 0, 0.62), (0.4, 0.3, 0.06), "moss"),
    ]
    root_with([group("Mesh", ps, (0, 0, 0))])


def rock(seed, scale):
    def fn():
        random.seed(seed)
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=0.5, location=(0, 0, 0.3 * scale[2]))
        o = bpy.context.active_object
        for v in o.data.vertices:
            v.co *= random.uniform(0.75, 1.2)
        _finish(o, scale, "stone")
        top = part("ico", (0.1 * scale[0], 0, 0.62 * scale[2]), (scale[0] * 0.55, scale[1] * 0.5, scale[2] * 0.2), "moss", sub=1)
        root_with([group("Mesh", [o, top], (0, 0, 0))])
    return fn


def tower_ruin():
    random.seed(21)
    R, H = 2.6, 8.0
    ps = [
        part("cyl", (0, 0, H / 2), (R * 2, R * 2, H), "brick", verts=12),
        part("cyl", (0, 0, 0.4), (R * 2 + 0.4, R * 2 + 0.4, 0.8), "brick_dark", verts=12),
        part("cyl", (0, 0, H - 0.6), (R * 2 + 0.3, R * 2 + 0.3, 0.35), "brick_dark", verts=12),
    ]
    # broken crenellations
    for i in range(12):
        if random.random() < 0.3:
            continue
        a = math.radians(i * 30 + 15)
        h = random.uniform(0.6, 1.6)
        ps.append(part("cube", (math.cos(a) * (R - 0.1), math.sin(a) * (R - 0.1), H + h / 2 - 0.1), (0.9, 0.5, h), "brick", rot=(0, 0, math.degrees(a))))
    # ivy patches
    for i in range(10):
        a = math.radians(random.uniform(0, 360))
        z = random.uniform(1.0, H - 1.0)
        ps.append(part("cube", (math.cos(a) * (R + 0.02), math.sin(a) * (R + 0.02), z), (0.1, random.uniform(0.8, 1.6), random.uniform(1.0, 2.8)),
                       "ivy", rot=(0, 0, math.degrees(a))))
    # dark doorway
    ps.append(part("cube", (0, -R, 1.3), (1.0, 0.2, 1.9), "black"))
    root_with([group("Mesh", ps, (0, 0, 0))])


def wall_ruin():
    random.seed(33)
    ps = []
    x = -3.0
    while x < 3.0:
        h = random.uniform(1.4, 3.4)
        w = random.uniform(0.8, 1.4)
        ps.append(part("cube", (x + w / 2, 0, h / 2), (w, 0.8, h), "brick" if random.random() < 0.7 else "brick_dark"))
        if random.random() < 0.5:
            ps.append(part("cube", (x + w / 2, -0.42, h * random.uniform(0.4, 0.8)), (w * 0.8, 0.06, h * 0.5), "ivy"))
        x += w
    ps.append(part("cube", (0, 0, 0.15), (6.4, 1.1, 0.3), "brick_dark"))
    for i in range(4):
        ps.append(part("cube", (random.uniform(-3, 3), random.uniform(-1.2, 1.2), 0.15), (0.5, 0.4, 0.3), "brick", rot=(0, 0, random.uniform(0, 90))))
    root_with([group("Mesh", ps, (0, 0, 0))])


def pillar_broken():
    ps = [
        part("cube", (0, 0, 0.12), (1.1, 1.1, 0.24), "brick_dark"),
        part("cyl", (0, 0, 1.2), (0.70, 0.70, 2.0), "brick", verts=8),
        part("cyl", (0, 0, 2.25), (0.70, 0.70, 0.2), "brick", verts=8, rot=(12, 0, 0)),
        part("cyl", (1.2, 0.4, 0.35), (0.70, 0.70, 1.3), "brick", verts=8, rot=(90, 0, 70)),
        part("cube", (0.3, -0.36, 1.2), (0.3, 0.05, 1.2), "ivy"),
    ]
    root_with([group("Mesh", ps, (0, 0, 0))])


def fence():
    ps = []
    for x in (-1.0, 0.0, 1.0):
        ps.append(part("cube", (x, 0, 0.55), (0.10, 0.10, 1.10), "dark_iron"))
        ps.append(part("cone", (x, 0, 1.17), (0.12, 0.12, 0.16), "dark_iron", verts=4))
    for x in (-0.5, 0.5):
        ps.append(part("cube", (x, 0, 0.50), (0.06, 0.06, 0.90), "dark_iron"))
    ps.append(part("cube", (0, 0, 0.95), (2.1, 0.06, 0.06), "dark_iron"))
    ps.append(part("cube", (0, 0, 0.25), (2.1, 0.06, 0.06), "dark_iron"))
    root_with([group("Mesh", ps, (0, 0, 0))])


def lantern_post():
    ps = [
        part("cyl", (0, 0, 1.2), (0.12, 0.12, 2.4), "dark_iron", verts=6),
        part("cube", (0, 0, 2.45), (0.30, 0.30, 0.34), "dark_iron"),
        part("cube", (0, 0, 2.45), (0.22, 0.32, 0.24), "lantern_glow"),
        part("cube", (0, 0, 2.45), (0.32, 0.22, 0.24), "lantern_glow"),
        part("cone", (0, 0, 2.70), (0.40, 0.40, 0.18), "dark_iron", verts=4, rot=(0, 0, 45)),
        part("cyl", (0, 0, 0.08), (0.40, 0.40, 0.16), "stone_dark", verts=6),
    ]
    root_with([group("Mesh", ps, (0, 0, 0))])


def mountain(seed, w, h):
    def fn():
        random.seed(seed)
        ps = []
        for i in range(5):
            x = random.uniform(-w * 0.35, w * 0.35)
            y = random.uniform(-w * 0.15, w * 0.15)
            ph = h * random.uniform(0.55, 1.0)
            pw = w * random.uniform(0.35, 0.6)
            bpy.ops.mesh.primitive_cone_add(vertices=7, radius1=0.5, radius2=0.04, depth=1, location=(x, y, ph / 2),
                                            rotation=(0, 0, math.radians(random.uniform(0, 60))))
            o = bpy.context.active_object
            for v in o.data.vertices:
                if v.co.z > -0.45:
                    v.co.x += random.uniform(-0.08, 0.08)
                    v.co.y += random.uniform(-0.08, 0.08)
            ps.append(_finish(o, (pw, pw * 0.8, ph), "mountain" if i % 2 else "mountain_dark"))
            # snow cap
            ps.append(part("cone", (x, y, ph * 0.86), (pw * 0.16, pw * 0.13, ph * 0.28), "snow", verts=7, r2=0.02))
        root_with([group("Mesh", ps, (0, 0, 0))])
    return fn


# ----------------------------------------------------------------------------- extra set dressing (Megabonk-like density)

def castle_wall():
    """8m crenellated castle wall with ivy, used to frame the arena."""
    random.seed(41)
    ps = [part("cube", (0, 0, 2.6), (8.0, 1.4, 5.2), "brick"),
          part("cube", (0, 0, 0.3), (8.3, 1.7, 0.6), "brick_dark"),
          part("cube", (0, 0, 5.3), (8.2, 1.6, 0.3), "brick_dark")]
    for i in range(5):
        if random.random() < 0.2:
            continue
        ps.append(part("cube", (-3.4 + i * 1.7, 0, 5.9), (0.9, 1.5, 0.9), "brick"))
    for i in range(3):
        ps.append(part("cube", (random.uniform(-3.4, 3.4), -0.72, random.uniform(0.6, 2.0)), (random.uniform(0.5, 1.1), 0.06, random.uniform(0.8, 1.8)), "ivy"))
    for i in range(3):
        ps.append(part("cube", (random.uniform(-3, 3), -0.72, random.uniform(1.5, 4)), (0.25, 0.04, 0.5), "black"))  # arrow slits
    root_with([group("Mesh", ps, (0, 0, 0))])


def castle_tower():
    random.seed(43)
    R, H = 3.0, 11.0
    ps = [part("cyl", (0, 0, H / 2), (R * 2, R * 2, H), "brick", verts=12),
          part("cyl", (0, 0, 0.5), (R * 2 + 0.5, R * 2 + 0.5, 1.0), "brick_dark", verts=12),
          part("cyl", (0, 0, H + 0.3), (R * 2 + 0.6, R * 2 + 0.6, 0.6), "brick_dark", verts=12),
          part("cone", (0, 0, H + 2.6), (R * 2 + 0.4, R * 2 + 0.4, 4.0), "roof", verts=12),
          part("cyl", (0, 0, H + 5.0), (0.12, 0.12, 1.4), "iron", verts=6),
          part("cube", (0.35, 0, H + 5.4), (0.7, 0.04, 0.45), "banner_red")]
    for i in range(10):
        a = math.radians(random.uniform(0, 360))
        z = random.uniform(1.0, H - 1.5)
        ps.append(part("cube", (math.cos(a) * (R + 0.02), math.sin(a) * (R + 0.02), z), (0.1, random.uniform(1.0, 2.0), random.uniform(1.2, 3.4)), "ivy", rot=(0, 0, math.degrees(a))))
    for i in range(4):
        a = math.radians(i * 90 + 20)
        ps.append(part("cube", (math.cos(a) * (R + 0.01), math.sin(a) * (R + 0.01), H - 2.5 - i * 1.6), (0.12, 0.35, 0.6), "black", rot=(0, 0, math.degrees(a))))
    ps.append(part("cube", (0, -R, 1.5), (1.4, 0.2, 2.6), "black"))
    root_with([group("Mesh", ps, (0, 0, 0))])


def arch():
    ps = [part("cube", (-2.0, 0, 2.0), (1.0, 1.0, 4.0), "brick"),
          part("cube", (2.0, 0, 1.6), (1.0, 1.0, 3.2), "brick"),
          part("cube", (-0.6, 0, 4.3), (3.6, 1.0, 0.9), "brick_dark"),
          part("cube", (-2.0, -0.52, 2.2), (0.8, 0.06, 1.8), "ivy"),
          part("cube", (1.4, 0, 0.3), (0.8, 0.7, 0.6), "brick", rot=(0, 0, 25))]
    root_with([group("Mesh", ps, (0, 0, 0))])


def brazier():
    ps = [part("cyl", (0, 0, 0.6), (0.18, 0.18, 1.2), "iron", verts=6),
          part("cyl", (0, 0, 1.25), (0.9, 0.9, 0.3), "iron", verts=8, ),
          part("cone", (0, 0, 1.05), (0.9, 0.9, 0.3), "iron", verts=8, r2=0.2, rot=(180, 0, 0)),
          part("cyl", (0, 0, 0.05), (0.6, 0.6, 0.1), "stone_dark", verts=6),
          part("cone", (0, 0, 1.65), (0.7, 0.7, 0.8), "fire", verts=5),
          part("cone", (0.12, 0.05, 1.7), (0.4, 0.4, 0.8), "fire_core", verts=5),
          part("cone", (-0.18, -0.1, 1.55), (0.3, 0.3, 0.5), "ember", verts=4)]
    root_with([group("Mesh", ps, (0, 0, 0))])


def banner():
    ps = [part("cyl", (0, 0, 1.6), (0.1, 0.1, 3.2), "wood_dark", verts=6),
          part("cube", (0.0, 0, 3.15), (1.0, 0.08, 0.08), "wood_dark"),
          part("cube", (0.0, 0.02, 2.35), (0.9, 0.04, 1.5), "banner_red"),
          part("cube", (0.0, -0.01, 2.45), (0.3, 0.04, 0.3), "gold"),
          part("cone", (0.0, 0.02, 1.55), (0.9, 0.04, 0.3), "banner_red", verts=4, rot=(0, 0, 45))]
    root_with([group("Mesh", ps, (0, 0, 0))])


def flowers(seed):
    def fn():
        random.seed(seed)
        ps = []
        cols = ["flower_yellow", "flower_pink", "flower_white"]
        for i in range(9):
            x, y = random.uniform(-0.6, 0.6), random.uniform(-0.6, 0.6)
            h = random.uniform(0.18, 0.35)
            ps.append(part("cube", (x, y, h / 2), (0.03, 0.03, h), "grass", ))
            ps.append(part("cube", (x, y, h), (0.12, 0.12, 0.06), random.choice(cols)))
        root_with([group("Mesh", ps, (0, 0, 0))])
    return fn


def mushrooms():
    random.seed(17)
    ps = []
    for i in range(4):
        x, y = random.uniform(-0.4, 0.4), random.uniform(-0.4, 0.4)
        s = random.uniform(0.6, 1.2)
        ps.append(part("cyl", (x, y, 0.12 * s), (0.08 * s, 0.08 * s, 0.24 * s), "mushroom_stem", verts=6))
        ps.append(part("cone", (x, y, 0.28 * s), (0.32 * s, 0.32 * s, 0.14 * s), "mushroom_red", verts=7, r2=0.06))
        ps.append(part("cube", (x + 0.06 * s, y, 0.33 * s), (0.04 * s, 0.04 * s, 0.03 * s), "white"))
    root_with([group("Mesh", ps, (0, 0, 0))])


def crates():
    ps = [part("cube", (0, 0, 0.4), (0.8, 0.8, 0.8), "crate"),
          part("cube", (0, -0.41, 0.4), (0.8, 0.02, 0.1), "wood_dark", rot=(0, 45, 0)),
          part("cube", (0.75, 0.1, 0.3), (0.6, 0.6, 0.6), "crate", rot=(0, 0, 20)),
          part("cube", (0.1, 0.1, 1.05), (0.5, 0.5, 0.5), "crate", rot=(0, 0, -15)),
          part("cyl", (-0.8, 0.2, 0.45), (0.6, 0.6, 0.9), "wood", verts=8)]
    root_with([group("Mesh", ps, (0, 0, 0))])


def skull_pile():
    random.seed(19)
    ps = []
    for i in range(7):
        x, y = random.uniform(-0.5, 0.5), random.uniform(-0.5, 0.5)
        z = 0.12 + (0.2 if i > 4 else 0)
        ps.append(part("cube", (x, y, z), (0.24, 0.26, 0.22), "skull", rot=(0, 0, random.uniform(0, 90))))
        ps.append(part("cube", (x, y - 0.13, z + 0.02), (0.16, 0.02, 0.06), "black", rot=(0, 0, 0)))
    for i in range(5):
        ps.append(part("cyl", (random.uniform(-0.7, 0.7), random.uniform(-0.7, 0.7), 0.05), (0.06, 0.06, 0.6), "bone", verts=5, rot=(90, 0, random.uniform(0, 180))))
    root_with([group("Mesh", ps, (0, 0, 0))])


def crown():
    ps = [part("cyl", (0, 0, 0.08), (0.42, 0.42, 0.16), "crown_gold", verts=8)]
    for i in range(5):
        a = math.radians(i * 72)
        ps.append(part("cone", (math.cos(a) * 0.17, math.sin(a) * 0.17, 0.24), (0.12, 0.12, 0.2), "crown_gold", verts=4))
    ps.append(part("cube", (0, -0.2, 0.08), (0.08, 0.04, 0.08), "gem_red"))
    root_with([group("Mesh", ps, (0, 0, 0))])


def rune_stone():
    ps = [part("cube", (0, 0, 1.0), (0.9, 0.5, 2.0), "stone_dark", rot=(0, 4, 0)),
          part("cube", (0, -0.26, 1.3), (0.12, 0.02, 0.6), "rune_blue"),
          part("cube", (0, -0.26, 1.2), (0.4, 0.02, 0.1), "rune_blue"),
          part("cube", (0, -0.26, 0.8), (0.3, 0.02, 0.1), "rune_blue"),
          part("cube", (0, 0, 0.05), (1.3, 0.9, 0.1), "moss")]
    root_with([group("Mesh", ps, (0, 0, 0))])


# ----------------------------------------------------------------------------- round 2: new enemies, weapons, shrine

def bat():
    body = [
        part("ico", (0, 0, 0.0), (0.42, 0.40, 0.38), "mage_dark", sub=1),
        part("cone", (-0.11, 0.0, 0.24), (0.1, 0.1, 0.18), "mage_dark", verts=4),     # ears
        part("cone", (0.11, 0.0, 0.24), (0.1, 0.1, 0.18), "mage_dark", verts=4),
        part("cube", (-0.08, -0.19, 0.04), (0.07, 0.02, 0.06), "eye_red"),
        part("cube", (0.08, -0.19, 0.04), (0.07, 0.02, 0.06), "eye_red"),
        part("cube", (-0.04, -0.2, -0.08), (0.02, 0.02, 0.06), "white"),               # fangs
        part("cube", (0.04, -0.2, -0.08), (0.02, 0.02, 0.06), "white"),
    ]
    Body = group("Body", body, (0, 0, 0))

    def wing(side):
        x = 0.2 * side
        ps = [
            part("cube", (x + 0.35 * side, 0.02, 0.05), (0.7, 0.04, 0.34), "purple_glow" if False else "mage_purple"),
            part("cone", (x + 0.75 * side, 0.02, -0.06), (0.2, 0.04, 0.3), "mage_purple", verts=3, rot=(0, 90 * side, 0)),
            part("cube", (x + 0.35 * side, 0.0, 0.2), (0.7, 0.05, 0.05), "mage_dark"),
        ]
        return group("WingR" if side < 0 else "WingL", ps, (x, 0, 0.1))
    root_with([Body, wing(-1), wing(1)])


def golem():
    random.seed(77)
    c = dict(torso="stone", chest="stone_dark", arms="stone", forearm="stone_dark", legs="stone_dark", shins="stone",
             boots="stone_dark", belt="moss", skin="stone", hands="stone_dark")
    humanoid(
        c, head=False,
        body_extra=[
            lambda: part("cube", (0, 0, 1.45), (0.78, 0.48, 0.5), "stone"),                 # massive chest
            lambda: part("ico", (-0.42, 0, 1.6), (0.36, 0.36, 0.3), "moss", sub=1),          # mossy shoulders
            lambda: part("ico", (0.42, 0, 1.6), (0.36, 0.36, 0.3), "stone_dark", sub=1),
            lambda: part("cube", (0, -0.25, 1.45), (0.18, 0.02, 0.18), "rune_blue"),         # glowing core rune
            lambda: part("cube", (0.1, 0.2, 1.2), (0.4, 0.06, 0.3), "moss"),
        ],
        arm_extra_l=[lambda: part("cube", (0.32, -0.01, 0.86), (0.26, 0.26, 0.24), "stone_dark")],
        arm_extra_r=[lambda: part("cube", (-0.32, -0.01, 0.86), (0.26, 0.26, 0.24), "stone_dark")],
        head_extra=[
            lambda: part("cube", (0, -0.03, 1.8), (0.34, 0.32, 0.26), "stone"),
            lambda: part("cube", (-0.07, -0.19, 1.82), (0.07, 0.02, 0.04), "rune_blue"),
            lambda: part("cube", (0.07, -0.19, 1.82), (0.07, 0.02, 0.04), "rune_blue"),
        ],
    )


def skeleton_archer():
    skeleton()
    # replace the rusty blade look: add a hood and a bow (bow parts merge into ForeArmL)
    hood = part("cube", (0, 0.03, 1.82), (0.3, 0.3, 0.3), "cloth_red")
    bpy.ops.object.select_all(action="DESELECT")
    head = bpy.data.objects.get("Head")
    hood.select_set(True)
    head.select_set(True)
    bpy.context.view_layer.objects.active = head
    bpy.ops.object.join()
    bow = []
    for i in range(5):
        t0 = -1 + 2 * i / 5
        t1 = -1 + 2 * (i + 1) / 5
        z0, z1 = 0.95 + t0 * 0.5, 0.95 + t1 * 0.5
        y0, y1 = -0.08 - 0.16 * (1 - t0 * t0), -0.08 - 0.16 * (1 - t1 * t1)
        ang = math.degrees(math.atan2(y1 - y0, z1 - z0))
        bow.append(part("cube", (0.27, (y0 + y1) / 2, (z0 + z1) / 2), (0.04, 0.05, abs(z1 - z0) * 1.15), "wood", rot=(-ang, 0, 0)))
    bow.append(part("cube", (0.27, -0.08, 0.95), (0.012, 0.012, 1.0), "rope"))
    fore = bpy.data.objects.get("ForeArmL")
    bpy.ops.object.select_all(action="DESELECT")
    for b in bow:
        b.select_set(True)
    fore.select_set(True)
    bpy.context.view_layer.objects.active = fore
    bpy.ops.object.join()


def bomb_shroom():
    body = [
        part("cyl", (0, 0, 0.32), (0.42, 0.42, 0.62), "mushroom_stem", verts=8),
        part("cone", (0, 0, 0.78), (1.0, 1.0, 0.45), "mushroom_red", verts=9, r2=0.15),
        part("cube", (0.22, -0.3, 0.84), (0.14, 0.14, 0.1), "white"),
        part("cube", (-0.25, 0.1, 0.92), (0.12, 0.12, 0.1), "white"),
        part("cube", (0.05, 0.32, 0.86), (0.1, 0.1, 0.08), "white"),
        part("cube", (-0.09, -0.21, 0.4), (0.08, 0.02, 0.1), "black"),
        part("cube", (0.09, -0.21, 0.4), (0.08, 0.02, 0.1), "black"),
        part("cube", (0, -0.21, 0.26), (0.16, 0.02, 0.04), "black"),
        part("cyl", (0, 0, 1.08), (0.05, 0.05, 0.22), "dark_iron", verts=5),          # fuse
        part("ico", (0, 0, 1.22), (0.12, 0.12, 0.12), "ember", sub=1),
    ]
    root_with([group("Body", body, (0, 0, 0))])


def boomerang():
    ps = [
        part("cube", (0.18, 0, 0), (0.5, 0.06, 0.12), "wood", rot=(0, 0, 35)),
        part("cube", (-0.18, 0, 0), (0.5, 0.06, 0.12), "wood", rot=(0, 0, -35)),
        part("cube", (0, 0, 0), (0.1, 0.07, 0.13), "gold"),
        part("cube", (0.38, 0.0, 0.0), (0.08, 0.07, 0.13), "crystal"),
        part("cube", (-0.38, 0.0, 0.0), (0.08, 0.07, 0.13), "crystal"),
    ]
    o = group("Mesh", ps, (0, 0, 0))
    root_with([_flatten(o, 90)])


def meteor_rock():
    random.seed(9)
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=0.5)
    o = bpy.context.active_object
    for v in o.data.vertices:
        v.co *= random.uniform(0.8, 1.15)
    _finish(o, (0.7, 0.7, 0.7), "dark_iron")
    glow = part("ico", (0, 0, 0), (0.55, 0.55, 0.55), "fire", sub=1, rot=(30, 20, 0))
    core = part("ico", (0.1, -0.1, 0.1), (0.3, 0.3, 0.3), "fire_core", sub=1)
    root_with([group("Mesh", [o, glow, core], (0, 0, 0))])


def spirit_dagger():
    ps = [
        part("cone", (0, 0, 0.2), (0.1, 0.03, 0.42), "purple_glow", verts=4),
        part("cube", (0, 0, -0.04), (0.2, 0.05, 0.04), "gold"),
        part("cube", (0, 0, -0.12), (0.04, 0.04, 0.14), "mage_dark"),
    ]
    root_with([_flatten(group("Mesh", ps, (0, 0, 0)), 90)])


def frost_shard():
    ps = [part("cone", (0, 0, 0.2), (0.18, 0.18, 0.5), "crystal", verts=6),
          part("cone", (0, 0, -0.05), (0.18, 0.18, 0.15), "crystal_light", verts=6, rot=(180, 0, 0))]
    root_with([group("Mesh", ps, (0, 0, 0))])


def shrine_base():
    ps = [
        part("cyl", (0, 0, 0.15), (3.2, 3.2, 0.3), "stone_dark", verts=10),
        part("cyl", (0, 0, 0.4), (2.2, 2.2, 0.25), "brick", verts=10),
    ]
    for i in range(4):
        a = math.radians(i * 90 + 45)
        ps.append(part("cube", (math.cos(a) * 1.25, math.sin(a) * 1.25, 1.1), (0.35, 0.35, 1.6), "stone", rot=(0, 0, i * 90 + 45)))
        ps.append(part("cube", (math.cos(a) * 1.25, math.sin(a) * 1.25, 1.95), (0.18, 0.18, 0.12), "rune_blue", rot=(0, 0, i * 90 + 45)))
    root_with([group("Mesh", ps, (0, 0, 0))])


def shrine_crystal():
    ps = [part("cone", (0, 0, 0.35), (0.6, 0.6, 0.7), "rune_blue", verts=6),
          part("cone", (0, 0, -0.2), (0.6, 0.6, 0.4), "rune_blue", verts=6, rot=(180, 0, 0)),
          part("cube", (0.12, -0.2, 0.3), (0.08, 0.04, 0.3), "crystal_light")]
    root_with([group("Mesh", ps, (0, 0, 0))])



# ----------------------------------------------------------------------------- volcano level

def magma_slime():
    random.seed(31)
    body = [
        part("ico", (0, 0, 0.42), (1.0, 1.0, 0.80), "magma_skin", sub=2),
        part("ico", (0, -0.12, 0.36), (0.7, 0.62, 0.5), "magma", sub=1),
    ]
    # cooled basalt crust plates riding on the molten blob
    for i in range(7):
        a = math.radians(i * 51 + random.uniform(-12, 12))
        z = random.uniform(0.45, 0.78)
        r = 0.42 * math.sqrt(max(0.05, 1 - ((z - 0.42) / 0.42) ** 2)) + 0.04
        body.append(part("cube", (math.cos(a) * r, math.sin(a) * r, z), (0.26, 0.26, 0.12), "basalt_dark" if i % 2 else "lava_crust",
                         rot=(random.uniform(-30, 30), random.uniform(-30, 30), math.degrees(a))))
    body.append(part("cube", (0, 0, 0.82), (0.34, 0.3, 0.1), "basalt", rot=(0, 0, 20)))
    body += [
        part("cube", (-0.18, -0.46, 0.5), (0.18, 0.04, 0.16), "black"),
        part("cube", (0.18, -0.46, 0.5), (0.18, 0.04, 0.16), "black"),
        part("cube", (-0.18, -0.48, 0.5), (0.08, 0.03, 0.08), "magma_core"),
        part("cube", (0.18, -0.48, 0.5), (0.08, 0.03, 0.08), "magma_core"),
        part("cube", (0, -0.45, 0.3), (0.26, 0.04, 0.06), "basalt_dark"),
    ]
    root_with([group("Body", body, (0, 0, 0))])


def fire_imp():
    body = [
        part("ico", (0, 0, 0.0), (0.42, 0.36, 0.5), "imp_red", sub=1),             # torso
        part("ico", (0, -0.02, 0.36), (0.36, 0.34, 0.32), "imp_red", sub=1),       # head
        part("cone", (-0.12, 0.0, 0.56), (0.08, 0.08, 0.22), "basalt_dark", verts=4, rot=(0, -25, 0)),   # horns
        part("cone", (0.12, 0.0, 0.56), (0.08, 0.08, 0.22), "basalt_dark", verts=4, rot=(0, 25, 0)),
        part("cube", (-0.08, -0.17, 0.38), (0.08, 0.02, 0.05), "magma_core"),       # eyes
        part("cube", (0.08, -0.17, 0.38), (0.08, 0.02, 0.05), "magma_core"),
        part("cube", (0, -0.17, 0.28), (0.12, 0.02, 0.03), "black"),                # grin
        part("cube", (0, -0.17, 0.0), (0.16, 0.04, 0.16), "imp_dark"),             # belly
        part("cube", (-0.13, -0.05, -0.28), (0.08, 0.08, 0.16), "imp_dark"),       # dangling legs
        part("cube", (0.13, -0.05, -0.28), (0.08, 0.08, 0.16), "imp_dark"),
        part("cyl", (0, 0.22, -0.18), (0.05, 0.05, 0.4), "imp_dark", verts=4, rot=(50, 0, 0)),   # tail
        part("cone", (0, 0.38, -0.32), (0.12, 0.05, 0.14), "imp_dark", verts=3, rot=(140, 0, 0)),
        part("ico", (0.24, -0.12, 0.05), (0.18, 0.18, 0.18), "magma", sub=1),     # fireball in claw
        part("ico", (0.24, -0.12, 0.05), (0.1, 0.1, 0.1), "magma_core", sub=1),
    ]
    Body = group("Body", body, (0, 0, 0))

    def wing(side):
        x = 0.18 * side
        ps = [
            part("cube", (x + 0.3 * side, 0.08, 0.12), (0.6, 0.04, 0.3), "imp_dark"),
            part("cone", (x + 0.62 * side, 0.08, 0.0), (0.18, 0.04, 0.3), "imp_dark", verts=3, rot=(0, 90 * side, 0)),
            part("cube", (x + 0.3 * side, 0.06, 0.27), (0.62, 0.05, 0.05), "basalt_dark"),
        ]
        return group("WingR" if side < 0 else "WingL", ps, (x, 0.08, 0.15))
    root_with([Body, wing(-1), wing(1)])


def basalt_columns(seed):
    def fn():
        random.seed(seed)
        ps = []
        for i in range(7):
            a = random.uniform(0, math.pi * 2)
            r = random.uniform(0, 1.1) if i else 0
            h = random.uniform(1.2, 3.6) if i else 3.9
            ps.append(part("cyl", (math.cos(a) * r, math.sin(a) * r, h / 2), (0.8, 0.8, h), "basalt" if i % 2 else "basalt_dark", verts=6))
            ps.append(part("cyl", (math.cos(a) * r, math.sin(a) * r, h + 0.02), (0.7, 0.7, 0.05), "ash", verts=6))
        root_with([group("Mesh", ps, (0, 0, 0))])
    return fn


def obsidian_spire():
    random.seed(17)
    ps = [part("cone", (0, 0, 1.6), (1.1, 0.9, 3.2), "obsidian", verts=5, rot=(0, 6, 0))]
    for i in range(4):
        a = math.radians(i * 90 + random.uniform(-20, 20))
        h = random.uniform(1.0, 2.0)
        ps.append(part("cone", (math.cos(a) * 0.55, math.sin(a) * 0.55, h / 2), (0.55, 0.45, h), "obsidian", verts=4,
                       rot=(random.uniform(-15, 15), random.uniform(10, 25), math.degrees(a))))
    ps.append(part("cone", (0.12, -0.2, 1.4), (0.2, 0.1, 1.2), "purple_glow", verts=4))   # glassy glint
    ps.append(part("cyl", (0, 0, 0.08), (1.6, 1.4, 0.16), "basalt_dark", verts=7))
    root_with([group("Mesh", ps, (0, 0, 0))])


def lava_rock(seed, scale):
    def fn():
        random.seed(seed)
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=0.5, location=(0, 0, 0.3 * scale[2]))
        o = bpy.context.active_object
        for v in o.data.vertices:
            v.co *= random.uniform(0.75, 1.2)
        _finish(o, scale, "volcano_rock")
        ps = [o]
        for i in range(3):   # glowing cracks
            a = random.uniform(0, 360)
            ps.append(part("cube", (math.cos(math.radians(a)) * scale[0] * 0.42, math.sin(math.radians(a)) * scale[1] * 0.42, 0.35 * scale[2]),
                           (0.06, scale[1] * 0.3, scale[2] * 0.4), "magma", rot=(random.uniform(-20, 20), 0, a)))
        ps.append(part("ico", (0.1 * scale[0], 0, 0.6 * scale[2]), (scale[0] * 0.5, scale[1] * 0.45, scale[2] * 0.18), "ash", sub=1))
        root_with([group("Mesh", ps, (0, 0, 0))])
    return fn


def charred_tree(seed):
    def fn():
        random.seed(seed)
        h = random.uniform(2.6, 3.4)
        ps = [
            part("cyl", (0, 0, h / 2), (0.42, 0.42, h), "charcoal", verts=6, rot=(random.uniform(-5, 5), random.uniform(-5, 5), 0)),
            part("cone", (0, 0, 0.18), (1.0, 1.0, 0.36), "charcoal", verts=6, r2=0.25),
        ]
        for i in range(5):
            a = i * 72 + random.uniform(-15, 15)
            z = h * 0.55 + i * 0.25
            ar = math.radians(a)
            ln = random.uniform(0.8, 1.4)
            ps.append(part("cyl", (math.cos(ar) * ln * 0.45, math.sin(ar) * ln * 0.45, z + ln * 0.3), (0.14, 0.14, ln), "basalt_dark", verts=5, rot=(0, 55, a)))
            ps.append(part("ico", (math.cos(ar) * ln * 0.9, math.sin(ar) * ln * 0.9, z + ln * 0.62), (0.12, 0.12, 0.12), "ember", sub=1))
        ps.append(part("cube", (0.0, -0.2, h * 0.35), (0.06, 0.05, 0.5), "magma"))   # smouldering crack
        root_with([group("Mesh", ps, (0, 0, 0))])
    return fn


def sulfur_vent():
    ps = [
        part("cone", (0, 0, 0.35), (1.8, 1.8, 0.7), "volcano_rock", verts=8, r2=0.55),
        part("cyl", (0, 0, 0.69), (0.62, 0.62, 0.04), "magma", verts=8),
        part("cyl", (0, 0, 0.71), (0.32, 0.32, 0.04), "magma_core", verts=8),
    ]
    for i in range(6):
        a = math.radians(i * 60 + 15)
        ps.append(part("ico", (math.cos(a) * 0.75, math.sin(a) * 0.75, 0.55), (0.22, 0.22, 0.12), "sulfur", sub=1))
    root_with([group("Mesh", ps, (0, 0, 0))])


def ash_mountain(seed, w, h, crater=False):
    def fn():
        random.seed(seed)
        ps = []
        n = 1 if crater else 5
        for i in range(n):
            x = 0 if crater else random.uniform(-w * 0.35, w * 0.35)
            y = 0 if crater else random.uniform(-w * 0.15, w * 0.15)
            ph = h if crater else h * random.uniform(0.55, 1.0)
            pw = w if crater else w * random.uniform(0.35, 0.6)
            bpy.ops.mesh.primitive_cone_add(vertices=9 if crater else 7, radius1=0.5, radius2=0.14 if crater else 0.04, depth=1,
                                            location=(x, y, ph / 2), rotation=(0, 0, math.radians(random.uniform(0, 60))))
            o = bpy.context.active_object
            for v in o.data.vertices:
                if v.co.z > -0.45:
                    v.co.x += random.uniform(-0.06, 0.06)
                    v.co.y += random.uniform(-0.06, 0.06)
            ps.append(_finish(o, (pw, pw * 0.85, ph), "basalt" if i % 2 else "volcano_rock"))
            # dark ash band near the top
            ps.append(part("cone", (x, y, ph * 0.8), (pw * 0.3, pw * 0.26, ph * 0.42), "basalt_dark", verts=7, r2=0.4 if crater else 0.05))
        if crater:
            ps.append(part("cyl", (0, 0, h * 0.995), (w * 0.12, w * 0.11, h * 0.02), "magma_core", verts=9))
            ps.append(part("cyl", (0, 0, h * 0.99), (w * 0.15, w * 0.14, h * 0.02), "magma", verts=9))
            slope = math.degrees(math.atan2(w * 0.36, h))
            for i in range(5):   # lava flows down the flank
                a = random.uniform(0, 360) if i else 200
                ln = h * random.uniform(0.4, 0.7)
                mid = h - ln * 0.5
                r = (1 - mid / h) * w * 0.43 + w * 0.06
                ar = math.radians(a)
                ps.append(part("cube", (math.cos(ar) * r, math.sin(ar) * r, mid), (w * 0.03, w * 0.03, ln * 1.05),
                               "magma", rot=(0, slope, a)))
        root_with([group("Mesh", ps, (0, 0, 0))])
    return fn


def fire_totem():
    ps = [
        part("cube", (0, 0, 0.9), (0.7, 0.7, 1.8), "basalt"),
        part("cube", (0, 0, 1.95), (0.85, 0.85, 0.3), "basalt_dark"),
        part("cube", (0, -0.36, 1.25), (0.42, 0.04, 0.12), "magma"),
        part("cube", (-0.14, -0.36, 1.45), (0.1, 0.04, 0.1), "magma_core"),
        part("cube", (0.14, -0.36, 1.45), (0.1, 0.04, 0.1), "magma_core"),
        part("cone", (0, 0, 2.45), (0.6, 0.6, 0.8), "magma", verts=5),
        part("cone", (0.05, 0.05, 2.5), (0.32, 0.32, 0.7), "magma_core", verts=5),
        part("cube", (0, 0, 0.08), (1.1, 1.1, 0.16), "volcano_rock"),
    ]
    root_with([group("Mesh", ps, (0, 0, 0))])


def treasure_slime():
    """Golden slime stuffed with coins and gems, a tiny crown and nervous eyes (it runs away!)."""
    random.seed(77)
    body = [
        soft("ico", (0, 0, 0.4), (1.0, 0.95, 0.78), "gold", sub=3),
        soft("ico", (0, 0, 0.12), (1.1, 1.05, 0.26), "gold_dark", sub=2),
        soft("ico", (-0.22, -0.2, 0.66), (0.2, 0.12, 0.12), "white", sub=2, rot=(0, -30, 0)),
        soft("ico", (-0.33, -0.24, 0.52), (0.07, 0.05, 0.07), "white", sub=1),
    ]
    for i in range(7):                                                                            # coins and gems inside
        a = random.uniform(0, 6.28)
        r = random.uniform(0.1, 0.3)
        c = ("gem_red", "gem_blue", "gem_green", "crown_gold")[i % 4]
        body.append(soft("cyl" if i % 4 == 3 else "ico", (math.cos(a) * r, math.sin(a) * r + 0.05, random.uniform(0.25, 0.55)),
                         (0.12, 0.12, 0.03) if i % 4 == 3 else (0.07, 0.07, 0.08), c, verts=8, rot=(random.uniform(0, 90), 0, 0)))
    body += eye(-0.17, -0.42, 0.5, 0.075, look=(0.6, 0.3)) + eye(0.17, -0.42, 0.5, 0.075, look=(0.6, 0.3))
    body.append(soft("ico", (0, -0.45, 0.3), (0.1, 0.04, 0.08), "gold_dark", sub=1))             # little "o" mouth
    for i in range(5):                                                                            # crown
        a = math.radians(i * 72)
        body.append(soft("cone", (math.cos(a) * 0.12, math.sin(a) * 0.12, 0.92), (0.07, 0.07, 0.14), "crown_gold", verts=4))
    body.append(soft("cyl", (0, 0, 0.84), (0.3, 0.3, 0.07), "crown_gold", verts=10))
    body.append(soft("ico", (0, -0.15, 0.86), (0.05, 0.03, 0.05), "gem_red", sub=1))
    body.append(soft("ico", (0.3, 0.45, 0.25), (0.28, 0.24, 0.26), "leather", sub=2))            # loot sack on its back
    body.append(soft("cone", (0.3, 0.45, 0.5), (0.1, 0.1, 0.1), "rope", verts=6))
    root_with([group("Body", body, (0, 0, 0))])


def gear_helmet():
    """Stage 2 enemy gear: dented iron kettle helmet with a rim and rivets (unit size, sits on top of any enemy)."""
    ps = [soft("ico", (0, 0, 0.18), (0.62, 0.62, 0.42), "iron", sub=2),
          soft("cyl", (0, 0, 0.06), (0.9, 0.9, 0.06), "dark_iron", verts=14),
          soft("cube", (0, -0.31, 0.2), (0.08, 0.04, 0.3), "steel_light")]
    for i in range(6):
        a = math.radians(i * 60)
        ps.append(soft("ico", (math.cos(a) * 0.3, math.sin(a) * 0.3, 0.1), (0.05, 0.05, 0.05), "gold_trim", sub=1))
    root_with([group("Mesh", ps, (0, 0, 0))])


def gear_warhelm():
    """Stage 3 enemy gear: blackened spiked helm with two red horns and a glowing visor slit."""
    ps = [soft("ico", (0, 0, 0.2), (0.64, 0.64, 0.46), "obsidian", sub=2),
          soft("cyl", (0, 0, 0.06), (0.86, 0.86, 0.07), "dark_iron", verts=14),
          soft("cube", (0, -0.3, 0.17), (0.34, 0.04, 0.05), "fire_core")]
    for x in (-1, 1):
        ps.append(soft("cone", (0.3 * x, 0, 0.32), (0.16, 0.16, 0.5), "cloth_red", verts=6, rot=(0, 35 * x, 0)))
        ps.append(soft("cone", (0.48 * x, 0, 0.6), (0.07, 0.07, 0.2), "bone", verts=6, rot=(0, 55 * x, 0)))
    for i in range(5):
        a = math.radians(i * 72 + 90)
        ps.append(soft("cone", (math.cos(a) * 0.18, math.sin(a) * 0.18 + 0.05, 0.42), (0.07, 0.07, 0.18), "iron", verts=4))
    root_with([group("Mesh", ps, (0, 0, 0))])


VOLCANO_MODELS = [
    ("Enemies", "GearHelmet", gear_helmet),
    ("Enemies", "GearWarHelm", gear_warhelm),
    ("Enemies", "TreasureSlime", treasure_slime),
    ("Enemies", "MagmaSlime", magma_slime),
    ("Enemies", "FireImp", fire_imp),
    ("Environment", "BasaltColumnsA", basalt_columns(3)),
    ("Environment", "BasaltColumnsB", basalt_columns(8)),
    ("Environment", "ObsidianSpire", obsidian_spire),
    ("Environment", "LavaRockA", lava_rock(11, (1.6, 1.3, 1.1))),
    ("Environment", "LavaRockB", lava_rock(12, (2.6, 2.0, 1.6))),
    ("Environment", "CharredTreeA", charred_tree(5)),
    ("Environment", "CharredTreeB", charred_tree(6)),
    ("Environment", "SulfurVent", sulfur_vent),
    ("Environment", "FireTotem", fire_totem),
    ("Environment", "AshMountainA", ash_mountain(4, 80, 45)),
    ("Environment", "AshMountainB", ash_mountain(5, 110, 60)),
    ("Environment", "VolcanoPeak", ash_mountain(6, 150, 95, crater=True)),
]



# ----------------------------------------------------------------------------- heroes v2 (Megabonk-like: chunky faceted low-poly, tapered limbs, big round heads)

HEAD_Z = 1.84


def hero(c, body_extra=(), arm_extra_l=(), arm_extra_r=(), head_extra=(), skirt=None, face=True, hair=None, shoulder=None):
    """Same joints/pivots as humanoid() (ProceduralRig compatible) but sculpted from tapered, faceted shapes."""
    body = [
        part("cyl", (0, 0, 0.99), (0.40, 0.28, 0.20), c["legs"], verts=8),                       # hips
        part("cone", (0, 0, 1.20), (0.36, 0.26, 0.30), c["torso"], verts=8, r2=0.62),            # waist, flares up
        part("ico", (0, 0.0, 1.42), (0.54, 0.36, 0.36), c.get("chest", c["torso"]), sub=1),       # chest
        part("cyl", (0, 0, 1.08), (0.43, 0.31, 0.07), c["belt"], verts=8),                        # belt
        part("cube", (0, -0.155, 1.08), (0.08, 0.02, 0.07), "gold"),                               # buckle
        part("cyl", (0, 0, 1.61), (0.14, 0.14, 0.12), c["skin"], verts=6),                       # neck
    ]
    if skirt:
        body.append(part("cone", (0, 0, 0.62), (0.66, 0.52, 0.80), skirt, r2=0.36, verts=9))
    if shoulder:
        for s in (-1, 1):
            body.append(part("ico", (0.32 * s, 0, 1.55), (0.26, 0.26, 0.2), shoulder, sub=1))
    body += [f() for f in body_extra]
    Body = group("Body", body, (0, 0, HIP_Z))

    hd = []
    if face:
        skin, dark = c["skin"], c.get("skin_dark", c["skin"])
        hd += [
            part("ico", (0, 0, HEAD_Z), (0.40, 0.38, 0.40), skin, sub=2),                         # round head
            part("cube", (0, -0.08, 1.72), (0.26, 0.2, 0.08), skin),                               # jaw
            part("cube", (-0.075, -0.188, 1.85), (0.05, 0.02, 0.085), "black"),                    # eyes (tall pills)
            part("cube", (0.075, -0.188, 1.85), (0.05, 0.02, 0.085), "black"),
            part("cube", (-0.065, -0.196, 1.875), (0.018, 0.01, 0.025), "white"),                 # eye glints
            part("cube", (0.085, -0.196, 1.875), (0.018, 0.01, 0.025), "white"),
            part("cone", (0, -0.2, 1.8), (0.06, 0.07, 0.07), dark, verts=4, rot=(-80, 0, 0)),      # nose
            part("cube", (-0.075, -0.19, 1.91), (0.07, 0.015, 0.018), dark),                       # brows
            part("cube", (0.075, -0.19, 1.91), (0.07, 0.015, 0.018), dark),
            part("ico", (-0.2, 0, 1.83), (0.06, 0.08, 0.1), skin, sub=1),                          # ears
            part("ico", (0.2, 0, 1.83), (0.06, 0.08, 0.1), skin, sub=1),
        ]
    if hair:
        hd += [
            part("ico", (0, 0.04, 1.93), (0.43, 0.42, 0.3), hair, sub=1),                          # hair cap
            part("cube", (0, 0.12, 1.8), (0.38, 0.18, 0.26), hair),                                 # back of the head
            part("cone", (-0.1, -0.15, 1.97), (0.14, 0.1, 0.14), hair, verts=4, rot=(-120, 0, 20)),  # fringe tufts
            part("cone", (0.06, -0.16, 1.98), (0.14, 0.1, 0.12), hair, verts=4, rot=(-120, 0, -15)),
        ]
    hd += [f() for f in head_extra]
    if hd:
        JOINTS.append(group("Head", hd, (0, 0, NECK_Z)))

    def arm(side, extra):
        x = 0.32 * side
        upper = group("ArmR" if side < 0 else "ArmL", [
            part("ico", (x, 0, 1.52), (0.17, 0.17, 0.17), c["arms"], sub=1),                      # shoulder ball
            part("cone", (x, 0, 1.39), (0.15, 0.16, 0.30), c["arms"], verts=6, r2=0.38, rot=(180, 0, 0)),  # tapered upper arm
        ], (x, 0, SHOULDER_Z))
        fore = [
            part("cone", (x, -0.01, 1.12), (0.15, 0.15, 0.28), c.get("forearm", c["arms"]), verts=6, r2=0.36, rot=(180, 0, 0)),
            part("cyl", (x, -0.01, 1.0), (0.15, 0.15, 0.06), c.get("cuff", c.get("forearm", c["arms"])), verts=6),  # cuff
            part("ico", (x, -0.01, 0.91), (0.13, 0.14, 0.13), c.get("hands", c["skin"]), sub=1),  # fist
            part("ico", (x - 0.04 * side, -0.06, 0.94), (0.05, 0.05, 0.06), c.get("hands", c["skin"]), sub=1),  # thumb
        ]
        fore += [f() for f in extra]
        JOINTS.append(group("ForeArmR" if side < 0 else "ForeArmL", fore, (x, 0, ELBOW_Z)))
        return upper

    def leg(side):
        x = 0.11 * side
        thigh = group("LegR" if side < 0 else "LegL", [
            part("cone", (x, 0, 0.73), (0.19, 0.21, 0.42), c["legs"], verts=6, r2=0.62),           # thigh, wide at hip
        ], (x, 0, HIP_Z))
        shin = group("ShinR" if side < 0 else "ShinL", [
            part("cone", (x, 0, 0.33), (0.15, 0.17, 0.40), c.get("shins", c["legs"]), verts=6, r2=0.62),
            part("cyl", (x, 0, 0.17), (0.18, 0.19, 0.12), c["boots"], verts=6),                    # boot cuff
            part("ico", (x, -0.05, 0.07), (0.17, 0.28, 0.14), c["boots"], sub=1),                  # rounded boot
            part("cube", (x, -0.03, 0.015), (0.17, 0.28, 0.03), "black"),                          # sole
        ], (x, 0, KNEE_Z))
        JOINTS.append(shin)
        return thigh

    parts = [Body, arm(1, arm_extra_l), arm(-1, arm_extra_r), leg(-1), leg(1)]
    return root_with(parts + JOINTS)


def knight():
    c = dict(torso="steel_dark", chest="steel", arms="steel", forearm="steel_dark", cuff="gold_dark", legs="steel_dark",
             shins="steel", boots="dark_iron", belt="leather", skin="steel", hands="steel_dark")
    hero(
        c, face=False, shoulder="steel",
        body_extra=[
            lambda: part("cone", (0, -0.1, 1.33), (0.4, 0.12, 0.5), "cloth_white", verts=4, r2=0.62, rot=(0, 0, 45)),   # surcoat
            lambda: part("cube", (0, -0.17, 1.37), (0.06, 0.02, 0.28), "cloth_red"),                # cross
            lambda: part("cube", (0, -0.17, 1.42), (0.2, 0.02, 0.06), "cloth_red"),
            lambda: part("cone", (0, -0.13, 0.92), (0.3, 0.06, 0.3), "cloth_white", verts=4, rot=(180, 0, 45)),  # tabard tail
            lambda: part("ico", (-0.36, 0, 1.6), (0.3, 0.3, 0.2), "steel", sub=1),                 # big pauldrons
            lambda: part("ico", (0.36, 0, 1.6), (0.3, 0.3, 0.2), "steel", sub=1),
            lambda: part("cube", (-0.36, 0, 1.6), (0.32, 0.06, 0.04), "gold_dark"),
            lambda: part("cube", (0.36, 0, 1.6), (0.32, 0.06, 0.04), "gold_dark"),
            lambda: part("cone", (0, 0.2, 1.15), (0.5, 0.08, 0.85), "cloth_red", verts=4, r2=0.3, rot=(8, 0, 45)),   # cape
        ],
        head_extra=[
            lambda: part("ico", (0, 0, HEAD_Z), (0.42, 0.4, 0.44), "steel", sub=2),                 # rounded great helm
            lambda: part("cyl", (0, 0, 1.73), (0.36, 0.34, 0.08), "steel_dark", verts=8),          # gorget
            lambda: part("cube", (0, -0.2, 1.86), (0.24, 0.03, 0.035), "black"),                   # visor slit
            lambda: part("cube", (0, -0.2, 1.8), (0.035, 0.03, 0.09), "black"),
            lambda: part("cube", (0, -0.17, 1.95), (0.05, 0.08, 0.15), "gold"),                    # brow ridge
            lambda: part("cone", (0, 0.05, 2.12), (0.1, 0.22, 0.3), "cloth_red", verts=4, rot=(-30, 0, 0)),   # plume
            lambda: part("cone", (0, 0.16, 2.02), (0.08, 0.2, 0.26), "cloth_red", verts=4, rot=(-75, 0, 0)),
        ],
        arm_extra_l=[lambda: part("cube", (0.42, -0.02, 1.06), (0.06, 0.44, 0.52), "knight_blue"),             # shield
                     lambda: part("cube", (0.455, -0.02, 1.06), (0.02, 0.1, 0.34), "gold"),
                     lambda: part("cube", (0.455, -0.02, 1.1), (0.02, 0.3, 0.08), "gold")],
    )


def ranger():
    c = dict(torso="leather", chest="ranger_green", arms="ranger_green", forearm="leather_dark", cuff="leather",
             legs="leather_dark", shins="leather_dark", boots="leather_dark", belt="leather_dark", skin="skin",
             skin_dark="skin_dark", hands="leather")
    hero(
        c, hair="wood",
        body_extra=[
            lambda: part("cone", (0, 0.18, 1.1), (0.52, 0.08, 0.95), "ranger_dark", verts=4, r2=0.3, rot=(8, 0, 45)),   # cloak
            lambda: part("cyl", (0.12, 0.22, 1.42), (0.14, 0.14, 0.52), "leather", rot=(-12, 0, -18), verts=6),  # quiver
            lambda: part("cone", (0.04, 0.27, 1.73), (0.05, 0.03, 0.14), "white", rot=(-12, 0, -18), verts=3),   # fletchings
            lambda: part("cone", (0.13, 0.27, 1.75), (0.05, 0.03, 0.14), "cloth_red", rot=(-12, 0, -18), verts=3),
            lambda: part("cube", (0, -0.17, 1.33), (0.06, 0.03, 0.52), "leather_dark", rot=(0, 32, 0)),        # strap
            lambda: part("cone", (0, 0.03, 1.58), (0.56, 0.42, 0.16), "ranger_green", verts=8, r2=0.3),      # mantle
        ],
        head_extra=[
            lambda: part("cone", (0, 0.08, 1.96), (0.48, 0.48, 0.42), "ranger_green", verts=7, r2=0.06, rot=(-25, 0, 0)),  # hood
            lambda: part("cone", (0, 0.28, 1.95), (0.16, 0.16, 0.3), "ranger_green", verts=4, rot=(-110, 0, 0)),  # hood tip
        ],
    )


def mage():
    c = dict(torso="mage_red", chest="mage_red", arms="mage_red", forearm="mage_red_dark", cuff="gold", legs="mage_red_dark",
             boots="black", belt="gold", skin="skin", skin_dark="skin_dark", hands="skin")
    hero(
        c, skirt="mage_red",
        body_extra=[
            lambda: part("cube", (0, -0.17, 1.3), (0.08, 0.02, 0.5), "gold"),
            lambda: part("cone", (0, -0.17, 1.55), (0.3, 0.12, 0.42), "cloth_white", rot=(180, 0, 0), verts=6),  # big beard
            lambda: part("cone", (0, 0.04, 1.58), (0.6, 0.44, 0.14), "mage_red_dark", verts=8, r2=0.32),      # collar
            lambda: part("cone", (0, 0.2, 1.1), (0.5, 0.08, 0.9), "mage_red_dark", verts=4, r2=0.3, rot=(6, 0, 45)),  # cape
        ],
        head_extra=[
            lambda: part("cone", (0, -0.17, 1.71), (0.24, 0.1, 0.16), "cloth_white", rot=(180, 0, 0), verts=6),   # moustache
            lambda: part("cyl", (0, 0, 1.97), (0.7, 0.7, 0.05), "mage_red_dark", verts=10),       # brim
            lambda: part("cone", (0, 0.06, 2.28), (0.42, 0.42, 0.66), "mage_red", verts=8, rot=(-16, 0, 0)),
            lambda: part("cone", (0, 0.2, 2.56), (0.16, 0.16, 0.24), "mage_red", verts=6, rot=(-55, 0, 0)),    # bent tip
            lambda: part("cyl", (0, 0, 2.02), (0.44, 0.44, 0.06), "gold", verts=8),                 # band
            lambda: part("ico", (0, -0.2, 2.03), (0.07, 0.04, 0.07), "lightning", sub=1),           # gem
        ],
    )


def alchemist():
    c = dict(torso="cloth_white", chest="cloth_white", arms="alch_orange", forearm="cloth_white", cuff="leather",
             legs="leather_dark", boots="black", belt="leather", skin="skin", skin_dark="skin_dark", hands="leather")
    hero(
        c, hair="leather_dark",
        body_extra=[
            lambda: part("cone", (0, -0.13, 1.12), (0.42, 0.1, 0.72), "alch_orange", verts=4, r2=0.35, rot=(0, 0, 45)),  # apron
            lambda: part("cube", (0, 0.22, 1.33), (0.38, 0.18, 0.42), "leather"),                   # backpack
            lambda: part("cube", (0, 0.32, 1.2), (0.3, 0.04, 0.12), "leather_dark"),
            lambda: part("cyl", (-0.1, 0.25, 1.62), (0.09, 0.09, 0.18), "poison", verts=6),
            lambda: part("cyl", (0.1, 0.25, 1.62), (0.09, 0.09, 0.18), "gem_blue", verts=6),
            lambda: part("cyl", (-0.22, -0.08, 1.04), (0.1, 0.1, 0.14), "gem_red", verts=6),         # belt vials
            lambda: part("cyl", (0.22, -0.08, 1.04), (0.1, 0.1, 0.14), "poison", verts=6),
        ],
        head_extra=[
            lambda: part("cyl", (0, 0, 1.9), (0.43, 0.42, 0.04), "leather_dark", verts=10),          # goggle strap
            lambda: part("cyl", (-0.08, -0.19, 1.9), (0.12, 0.12, 0.05), "gold", rot=(90, 0, 0), verts=8),  # goggles on forehead
            lambda: part("cyl", (0.08, -0.19, 1.9), (0.12, 0.12, 0.05), "gold", rot=(90, 0, 0), verts=8),
            lambda: part("cyl", (-0.08, -0.215, 1.9), (0.08, 0.08, 0.01), "glass", rot=(90, 0, 0), verts=8),
            lambda: part("cyl", (0.08, -0.215, 1.9), (0.08, 0.08, 0.01), "glass", rot=(90, 0, 0), verts=8),
        ],
    )



# ----------------------------------------------------------------------------- heroes v3: PS2-era low-poly anatomy
# Continuous, smooth-shaded limbs grown from joint chains with Blender's Skin modifier (+1 subdivision), heroic
# proportions (~6 heads tall, broad shoulders, narrow waist, tapered muscles). Same joint names/pivots as humanoid().

def skin(points, color, subdiv=1, smooth=True, edges=None):
    """points: [((x,y,z), (rx,ry)), ...] -> organic tube through them (chain unless edges given)."""
    me = bpy.data.meshes.new("skin")
    verts = [p for p, _ in points]
    if edges is None:
        edges = [(i, i + 1) for i in range(len(points) - 1)]
    me.from_pydata(verts, edges, [])
    o = bpy.data.objects.new("skin", me)
    bpy.context.scene.collection.objects.link(o)
    bpy.ops.object.select_all(action="DESELECT")
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    m = o.modifiers.new("Skin", "SKIN")
    m.use_smooth_shade = smooth
    for i, (_, r) in enumerate(points):
        sv = me.skin_vertices[0].data[i]
        sv.radius = r if isinstance(r, tuple) else (r, r)
        sv.use_root = i == 0
    if subdiv:
        s = o.modifiers.new("Sub", "SUBSURF")
        s.levels = subdiv
        s.render_levels = subdiv
    for mod in list(o.modifiers):
        bpy.ops.object.modifier_apply(modifier=mod.name)
    _finish(o, (1, 1, 1), color)
    for p in o.data.polygons:
        p.use_smooth = smooth
    return o


def soft(kind, loc, size, color, **kw):
    """A primitive part, smooth shaded (rounded, painted-look instead of faceted)."""
    o = part(kind, loc, size, color, **kw)
    for p in o.data.polygons:
        p.use_smooth = True
    return o


HEAD_C = 1.77


def extras(fns, side):
    out = []
    for f in fns:
        r = f(side)
        out += r if isinstance(r, list) else [r]
    return out


def plate(kind, loc, size, color, edge="steel_edge", grow=1.12, **kw):
    """Armor plate with a dark rim: a slightly larger dark copy behind the main piece reads as a painted outline."""
    big = tuple(v * grow for v in size)
    return [soft(kind, loc, big, edge, **kw), soft(kind, loc, size, color, **kw)]


def body3(c, body_extra=(), arm_extra_l=(), arm_extra_r=(), head_extra=(), head=True, face="human", bare_arms=False,
          upper_extra=(), leg_extra=(), shin_extra=()):
    """upper_extra / leg_extra / shin_extra: functions f(side) -> part or list, attached to that limb (they animate with it)."""
    """c: palette names: torso, chest, arms, forearm, hands, legs, shins, boots, belt, skin, skin_dark."""
    body = [
        skin([((0, 0, 0.94), (0.17, 0.11)), ((0, 0, 1.12), (0.135, 0.095)), ((0, -0.01, 1.34), (0.215, 0.135)),
              ((0, 0, 1.47), (0.245, 0.13)), ((0, 0, 1.55), (0.1, 0.08))], c.get("chest", c["torso"])),
        skin([((0, 0, 1.52), (0.06, 0.06)), ((0, 0.005, 1.66), (0.055, 0.055))], c["skin"]),          # neck
        skin([((0, 0, 0.9), (0.165, 0.115)), ((0, 0, 1.1), (0.14, 0.1))], c["torso"]),               # hips / waist cloth
        soft("cyl", (0, 0, 1.06), (0.3, 0.22, 0.07), c["belt"], verts=10),                            # belt
        part("cube", (0, -0.112, 1.06), (0.07, 0.02, 0.06), "gold"),                                   # buckle
    ]
    for s in (-1, 1):   # shoulder caps (deltoids) live on the body so the silhouette stays broad
        body.append(soft("ico", (0.235 * s, 0, 1.49), (0.15, 0.15, 0.13), c.get("shoulder", c["arms"]), sub=2))
    for f in body_extra:
        r = f()
        body += r if isinstance(r, list) else [r]
    Body = group("Body", body, (0, 0, HIP_Z))

    hd = []
    if head:
        skin_c, dark = c["skin"], c.get("skin_dark", c["skin"])
        hd += [
            soft("ico", (0, 0, HEAD_C), (0.24, 0.265, 0.29), skin_c, sub=2),                            # skull
            soft("ico", (0, -0.055, 1.69), (0.17, 0.16, 0.13), skin_c, sub=2),                         # jaw / chin
        ]
        if face == "human":
            hd += [
                soft("ico", (-0.05, -0.122, 1.792), (0.03, 0.02, 0.036), "black", sub=1),            # eyes
                soft("ico", (0.05, -0.122, 1.792), (0.03, 0.02, 0.036), "black", sub=1),
                part("cube", (-0.055, -0.13, 1.818), (0.06, 0.02, 0.014), dark),                       # brows
                part("cube", (0.055, -0.13, 1.818), (0.06, 0.02, 0.014), dark),
                soft("cone", (0, -0.14, 1.755), (0.035, 0.05, 0.06), dark, verts=4, rot=(-75, 0, 0)), # nose
                part("cube", (0, -0.132, 1.705), (0.06, 0.012, 0.012), dark),                          # mouth
                soft("ico", (-0.122, 0, 1.775), (0.035, 0.05, 0.07), skin_c, sub=1),                   # ears
                soft("ico", (0.122, 0, 1.775), (0.035, 0.05, 0.07), skin_c, sub=1),
            ]
    for f in head_extra:
        r = f()
        hd += r if isinstance(r, list) else [r]
    if hd:
        JOINTS.append(group("Head", hd, (0, 0, NECK_Z)))

    def arm(side, extra):
        x = side
        upper = skin([((0.24 * x, 0, 1.53), (0.08, 0.08)), ((0.275 * x, 0, 1.38), (0.085, 0.08)),
                      ((0.3 * x, 0.005, 1.25), (0.062, 0.062)), ((0.302 * x, 0.0, 1.19), (0.055, 0.055))],
                     c["skin"] if bare_arms else c["arms"])
        ups = [upper]
        for f in upper_extra:
            r = f(side)
            ups += r if isinstance(r, list) else [r]
        Upper = group("ArmR" if side < 0 else "ArmL", ups, (0.26 * x, 0, SHOULDER_Z))
        fore = [
            skin([((0.298 * x, 0, 1.31), (0.06, 0.06)), ((0.3 * x, 0, 1.25), (0.064, 0.064)), ((0.312 * x, -0.01, 1.14), (0.072, 0.066)),
                  ((0.32 * x, -0.012, 0.99), (0.045, 0.045)), ((0.32 * x, -0.013, 0.95), (0.042, 0.045))], c.get("forearm", c["arms"])),
            skin([((0.32 * x, -0.014, 1.0), (0.04, 0.05)), ((0.322 * x, -0.02, 0.91), (0.042, 0.062)),
                  ((0.322 * x, -0.025, 0.84), (0.036, 0.05))], c.get("hands", c["skin"])),             # hand
            soft("ico", (0.3 * x, -0.055, 0.92), (0.035, 0.035, 0.06), c.get("hands", c["skin"]), sub=1),  # thumb
        ]
        for f in extra:
            r = f()
            fore += r if isinstance(r, list) else [r]
        JOINTS.append(group("ForeArmR" if side < 0 else "ForeArmL", fore, (0.3 * x, 0, ELBOW_Z)))
        return Upper

    def leg(side):
        x = 0.105 * side
        thigh = group("LegR" if side < 0 else "LegL", [
            skin([((x, 0, 1.0), (0.11, 0.11)), ((x, 0, 0.96), (0.118, 0.118)), ((x * 1.05, -0.01, 0.75), (0.1, 0.1)),
                  ((x, -0.01, 0.53), (0.072, 0.075)), ((x, -0.01, 0.47), (0.066, 0.07))], c["legs"]),
        ] + extras(leg_extra, side), (x, 0, HIP_Z))
        shin = group("ShinR" if side < 0 else "ShinL", [
            skin([((x, -0.01, 0.6), (0.066, 0.07)), ((x, -0.01, 0.53), (0.072, 0.075)), ((x, 0.014, 0.38), (0.082, 0.082)),
                  ((x, 0, 0.14), (0.052, 0.056)), ((x, 0, 0.09), (0.05, 0.054))], c.get("shins", c["legs"])),
            skin([((x, 0.01, 0.16), (0.06, 0.064)), ((x, -0.03, 0.06), (0.066, 0.05)), ((x, -0.15, 0.04), (0.056, 0.034))],
                 c["boots"]),                                                                          # foot / boot
        ] + extras(shin_extra, side), (x, 0, KNEE_Z))
        JOINTS.append(shin)
        return thigh

    parts = [Body, arm(1, arm_extra_l), arm(-1, arm_extra_r), leg(-1), leg(1)]
    return root_with(parts + JOINTS)


def jagged_hem(z_top, z_bottom, r_top, r_bottom, color, points=9, depth=0.16, y_scale=0.8):
    """Long coat skirt flaring out, with zig-zag points along the hem (Megabonk mage coat)."""
    ps = [soft("cone", (0, 0.01, (z_top + z_bottom) / 2 + depth / 2), (r_bottom * 2, r_bottom * 2 * y_scale, z_top - z_bottom - depth),
               color, verts=points * 2, r2=0.5 * r_top / r_bottom)]
    zc = z_bottom + depth / 2
    for i in range(points):
        a = math.radians(i / points * 360 + 180 / points)
        ps.append(soft("cone", (math.cos(a) * r_bottom * 0.93, math.sin(a) * r_bottom * 0.93 * y_scale + 0.01, zc),
                       (0.2 * r_bottom * 3.2 / points * 2.2, 0.06, depth), color, verts=3, rot=(180, 0, math.degrees(a) + 90)))
    return ps


def knight():
    c = dict(torso="steel_dark", chest="steel", arms="steel", shoulder="steel", forearm="steel_dark", hands="dark_iron",
             legs="steel_dark", shins="steel", boots="dark_iron", belt="leather", skin="steel", skin_dark="steel_dark")
    body3(
        c, face="none",
        body_extra=[
            lambda: soft("cone", (0, -0.03, 1.27), (0.42, 0.28, 0.5), "cloth_white", verts=10, r2=0.62),   # surcoat
            lambda: part("cube", (0, -0.14, 1.32), (0.05, 0.02, 0.26), "cloth_red"),
            lambda: part("cube", (0, -0.14, 1.37), (0.18, 0.02, 0.05), "cloth_red"),
            lambda: soft("cone", (0, -0.0, 0.88), (0.4, 0.3, 0.3), "steel_dark", verts=10, r2=0.4),       # tassets
            lambda: soft("ico", (-0.27, 0, 1.53), (0.24, 0.24, 0.17), "steel", sub=2),                     # pauldrons
            lambda: soft("ico", (0.27, 0, 1.53), (0.24, 0.24, 0.17), "steel", sub=2),
            lambda: soft("cyl", (-0.27, 0, 1.5), (0.25, 0.25, 0.03), "gold_dark", verts=10),
            lambda: soft("cyl", (0.27, 0, 1.5), (0.25, 0.25, 0.03), "gold_dark", verts=10),
            lambda: soft("cone", (0, 0.16, 1.05), (0.46, 0.06, 0.95), "cloth_red", verts=4, r2=0.36, rot=(6, 0, 45)),  # cape
        ],
        head_extra=[
            lambda: soft("ico", (0, 0, 1.78), (0.27, 0.29, 0.31), "steel", sub=2),                       # helm
            lambda: soft("cyl", (0, 0.0, 1.66), (0.2, 0.2, 0.06), "steel_dark", verts=10),               # gorget
            lambda: part("cube", (0, -0.14, 1.79), (0.17, 0.03, 0.025), "black"),                        # visor slit
            lambda: part("cube", (0, -0.14, 1.74), (0.025, 0.03, 0.07), "black"),
            lambda: soft("cube", (0, -0.12, 1.86), (0.04, 0.06, 0.12), "gold"),                          # crest ridge
            lambda: soft("cone", (0, 0.06, 2.0), (0.06, 0.2, 0.22), "cloth_red", verts=6, rot=(-35, 0, 0)),   # plume
        ],
        arm_extra_l=[lambda: soft("cube", (0.37, -0.03, 1.05), (0.05, 0.36, 0.44), "knight_blue"),        # shield
                     lambda: part("cube", (0.397, -0.03, 1.05), (0.02, 0.07, 0.3), "gold"),
                     lambda: part("cube", (0.397, -0.03, 1.1), (0.02, 0.24, 0.06), "gold")],
    )


def ranger():
    c = dict(torso="ranger_green", chest="ranger_green", arms="cloth_white", forearm="leather", hands="skin",
             legs="cloth_white", shins="cloth_white", boots="leather_dark", belt="leather_dark", skin="skin", skin_dark="skin_dark")
    body3(
        c,
        body_extra=[
            lambda: soft("cone", (0, 0, 0.86), (0.42, 0.32, 0.28), "ranger_green", verts=10, r2=0.36),     # tunic skirt
            lambda: soft("ico", (-0.24, 0, 1.49), (0.17, 0.17, 0.15), "ranger_green", sub=2),              # short sleeves
            lambda: soft("ico", (0.24, 0, 1.49), (0.17, 0.17, 0.15), "ranger_green", sub=2),
            lambda: soft("cyl", (0.1, 0.15, 1.38), (0.11, 0.11, 0.48), "leather", rot=(-12, 0, -22), verts=8),  # quiver
            lambda: soft("cone", (0.04, 0.19, 1.67), (0.05, 0.03, 0.14), "cloth_red", rot=(-12, 0, -22), verts=3),
            lambda: soft("cone", (0.12, 0.2, 1.68), (0.05, 0.03, 0.14), "cloth_red", rot=(-12, 0, -22), verts=3),
            lambda: part("cube", (0, -0.125, 1.32), (0.04, 0.02, 0.44), "leather_dark", rot=(0, 35, 0)),   # strap
        ],
        head_extra=[
            lambda: soft("ico", (0, 0.03, 1.81), (0.26, 0.27, 0.27), "flower_yellow", sub=2),             # blonde hair
            lambda: soft("cube", (0, 0.07, 1.7), (0.22, 0.14, 0.16), "flower_yellow"),
            lambda: soft("cone", (0, 0.02, 1.9), (0.27, 0.3, 0.2), "ranger_green", verts=10, r2=0.18, rot=(-10, 0, 0)),  # cap
            lambda: soft("cone", (0, 0.14, 1.98), (0.1, 0.1, 0.22), "ranger_green", verts=6, rot=(-75, 0, 0)),          # cap tip
            lambda: soft("cone", (0.1, 0.06, 1.98), (0.03, 0.02, 0.2), "cloth_red", verts=3, rot=(-40, 25, 0)),         # feather
        ],
    )


def mage():
    """Red mage after the Megabonk reference: shadowed face with glowing eyes, wide-brim hat, high collar,
    long red coat with a jagged hem, black belt with gold buckle, dark gloves, glowing hands."""
    c = dict(torso="mage_red", chest="mage_red", arms="mage_red", shoulder="mage_red", forearm="dark_iron", hands="dark_iron",
             legs="mage_red_dark", shins="mage_red_dark", boots="black", belt="black", skin="black", skin_dark="black")
    body3(
        c, face="none",
        body_extra=[
            lambda: jagged_hem(1.12, 0.1, 0.16, 0.25, "mage_red", points=7, depth=0.24, y_scale=0.75),  # long coat
            lambda: soft("cone", (0, 0.13, 0.95), (0.48, 0.07, 1.05), "mage_red_dark", verts=4, r2=0.3, rot=(4, 0, 45)),  # back cape
            lambda: soft("cone", (0, 0.0, 1.6), (0.36, 0.32, 0.24), "mage_red", verts=10, r2=0.62),     # high collar
            lambda: soft("cone", (-0.23, 0, 1.49), (0.24, 0.24, 0.16), "mage_red", verts=8, r2=0.2),    # shoulder capes
            lambda: soft("cone", (0.23, 0, 1.49), (0.24, 0.24, 0.16), "mage_red", verts=8, r2=0.2),
            lambda: part("cube", (0, -0.125, 1.06), (0.09, 0.02, 0.07), "gold"),
        ],
        head_extra=[
            lambda: part("cube", (-0.05, -0.128, 1.79), (0.045, 0.02, 0.022), "lantern_glow"),         # glowing eyes in shadow
            lambda: part("cube", (0.05, -0.128, 1.79), (0.045, 0.02, 0.022), "lantern_glow"),
            lambda: soft("cone", (0, 0, 1.915), (0.62, 0.62, 0.05), "mage_red", verts=14, r2=0.42),   # wide brim
            lambda: soft("cone", (0, 0.03, 2.13), (0.36, 0.36, 0.4), "mage_red", verts=12, r2=0.17, rot=(-8, 0, 0)),   # hat crown
            lambda: soft("cone", (0, 0.1, 2.38), (0.13, 0.13, 0.22), "mage_red", verts=8, rot=(-32, 0, 0)),          # bent tip
            lambda: soft("cyl", (0, 0, 1.96), (0.33, 0.33, 0.06), "dark_iron", verts=12),               # hat band
        ],
        arm_extra_l=[lambda: soft("ico", (0.33, -0.06, 0.86), (0.12, 0.12, 0.12), "lantern_glow", sub=2)],   # magic orb
        arm_extra_r=[lambda: soft("ico", (-0.33, -0.06, 0.86), (0.12, 0.12, 0.12), "lantern_glow", sub=2)],
    )


def alchemist():
    c = dict(torso="leather_dark", chest="cloth_white", arms="cloth_white", forearm="leather", hands="leather",
             legs="leather_dark", shins="leather_dark", boots="black", belt="leather", skin="skin", skin_dark="skin_dark")
    body3(
        c,
        body_extra=[
            lambda: soft("cone", (0, 0.0, 1.43), (0.56, 0.46, 0.32), "alch_orange", verts=10, r2=0.3),  # poncho / mantle
            lambda: soft("cone", (0, -0.1, 1.0), (0.3, 0.06, 0.52), "alch_orange", verts=4, r2=0.36, rot=(0, 0, 45)),  # apron
            lambda: soft("cube", (0, 0.16, 1.28), (0.3, 0.14, 0.34), "leather"),                        # backpack
            lambda: soft("cyl", (-0.08, 0.17, 1.52), (0.07, 0.07, 0.15), "poison", verts=8),
            lambda: soft("cyl", (0.08, 0.17, 1.52), (0.07, 0.07, 0.15), "gem_blue", verts=8),
            lambda: soft("cyl", (-0.17, -0.07, 1.0), (0.08, 0.08, 0.12), "gem_red", verts=8),            # belt vials
            lambda: soft("cyl", (0.17, -0.07, 1.0), (0.08, 0.08, 0.12), "poison", verts=8),
            lambda: soft("cube", (0.19, 0.0, 0.98), (0.08, 0.14, 0.12), "leather"),                      # pouch
        ],
        head_extra=[
            lambda: soft("ico", (0, 0.03, 1.82), (0.27, 0.28, 0.26), "leather_dark", sub=2),             # hair
            lambda: soft("cone", (-0.05, -0.1, 1.9), (0.1, 0.06, 0.1), "leather_dark", verts=4, rot=(-120, 0, 20)),
            lambda: soft("cyl", (0, 0, 1.86), (0.27, 0.29, 0.03), "leather", verts=12),                  # goggle strap
            lambda: soft("cyl", (-0.055, -0.13, 1.86), (0.085, 0.085, 0.04), "gold", rot=(90, 0, 0), verts=10),
            lambda: soft("cyl", (0.055, -0.13, 1.86), (0.085, 0.085, 0.04), "gold", rot=(90, 0, 0), verts=10),
            lambda: soft("cyl", (-0.055, -0.152, 1.86), (0.06, 0.06, 0.01), "glass", rot=(90, 0, 0), verts=10),
            lambda: soft("cyl", (0.055, -0.152, 1.86), (0.06, 0.06, 0.01), "glass", rot=(90, 0, 0), verts=10),
        ],
    )



def plate(kind, loc, size, color, edge="steel_edge", grow=(1.14, 0.6, 1.14), back=(0, 0.012, 0), flat=True, **kw):
    """Front-facing armor plate with a dark painted-style rim (a dark copy, bigger in the plate plane, just behind it)."""
    mk = part if flat else soft
    big = tuple(size[i] * grow[i] for i in range(3))
    bl = tuple(loc[i] + back[i] for i in range(3))
    return [mk(kind, bl, big, edge, **kw), mk(kind, loc, size, color, **kw)]


def knight():
    """Megabonk-style knight: flat-top bucket helm with eye holes, layered angular plates (flat-shaded = metal sheen),
    dark plate rims, gold straps crossing the chest, tabard with a black cross, faulds, couters, knee cops."""
    c = dict(torso="steel_edge", chest="steel", arms="steel_edge", shoulder="steel", forearm="steel", hands="steel_edge",
             legs="steel", shins="steel", boots="steel_edge", belt="gold_trim", skin="steel", skin_dark="steel_edge")

    def pauldron(s):
        ps = [part("ico", (0.26 * s, 0, 1.55), (0.25, 0.25, 0.2), "steel", sub=1)]                  # dome
        for k in range(3):                                                                           # lames
            z = 1.5 - k * 0.065
            ps.append(part("cone", (0.285 * s, 0, z), (0.27 - k * 0.02, 0.25 - k * 0.02, 0.07), "steel_edge", verts=8, r2=0.42))
            ps.append(part("cone", (0.285 * s, 0, z + 0.012), (0.255 - k * 0.02, 0.235 - k * 0.02, 0.06),
                           "steel_light" if k == 0 else "steel", verts=8, r2=0.42))
        ps.append(part("cyl", (0.285 * s, 0, 1.385), (0.2, 0.19, 0.02), "gold_trim", verts=8))
        return ps

    def couter(s):
        return [part("ico", (0.3 * s, 0.035, 1.25), (0.12, 0.1, 0.12), "steel_light", sub=1),
                part("cone", (0.3 * s, 0.075, 1.25), (0.09, 0.04, 0.09), "steel", verts=4, rot=(-90, 0, 0)),
                part("cone", (0.32 * s, -0.012, 1.0), (0.14, 0.14, 0.13), "steel", verts=8, r2=0.33, rot=(180, 0, 0)),   # gauntlet cuff
                part("cyl", (0.32 * s, -0.012, 1.065), (0.145, 0.145, 0.02), "gold_trim", verts=8)]

    body3(
        c, head=False,
        upper_extra=[pauldron],
        leg_extra=[lambda s: plate("cube", (0.105 * s, -0.08, 0.76), (0.16, 0.05, 0.28), "steel_light")],       # cuisses
        shin_extra=[
            lambda s: [part("ico", (0.105 * s, -0.07, 0.53), (0.13, 0.09, 0.13), "steel_light", sub=1),        # knee cops
                       part("cone", (0.105 * s, -0.1, 0.53), (0.1, 0.05, 0.1), "steel", verts=4, rot=(90, 0, 0))],
            lambda s: plate("cube", (0.105 * s, -0.065, 0.32), (0.12, 0.04, 0.3), "steel_light"),                # greaves
            lambda s: part("cone", (0.105 * s, -0.12, 0.06), (0.12, 0.16, 0.08), "steel", verts=4, rot=(-90, 0, 45)),  # sabaton
        ],
        body_extra=[
            lambda: plate("ico", (0, -0.055, 1.37), (0.44, 0.24, 0.38), "steel_light", sub=1, grow=(1.08, 0.9, 1.08)),  # breastplate
            lambda: part("cube", (0, -0.17, 1.37), (0.025, 0.03, 0.3), "steel"),                     # center ridge
            lambda: part("cube", (0.0, -0.165, 1.37), (0.026, 0.03, 0.4), "gold_trim", rot=(0, 34, 0)),   # crossed straps
            lambda: part("cube", (0.0, -0.165, 1.37), (0.026, 0.03, 0.4), "gold_trim", rot=(0, -34, 0)),
            lambda: part("cyl", (0, 0, 1.6), (0.26, 0.22, 0.07), "steel_edge", verts=8),             # gorget
            lambda: part("cyl", (0, 0, 1.63), (0.22, 0.19, 0.04), "steel", verts=8),
            lambda: part("cone", (0, 0, 0.97), (0.42, 0.31, 0.09), "steel_edge", verts=10, r2=0.44),  # fauld tiers
            lambda: part("cone", (0, 0, 0.98), (0.4, 0.29, 0.08), "steel", verts=10, r2=0.44),
            lambda: part("cone", (0, 0, 0.9), (0.45, 0.33, 0.09), "steel_edge", verts=10, r2=0.44),
            lambda: part("cone", (0, 0, 0.91), (0.43, 0.31, 0.08), "steel_light", verts=10, r2=0.44),
            lambda: plate("cube", (0, -0.15, 0.8), (0.2, 0.02, 0.32), "cloth_white", edge="steel_edge", grow=(1.12, 1, 1.05)),  # tabard
            lambda: part("cube", (0, -0.163, 0.83), (0.035, 0.012, 0.18), "black"),                  # cross
            lambda: part("cube", (0, -0.163, 0.86), (0.12, 0.012, 0.035), "black"),
        ],
        head_extra=[
            lambda: part("cyl", (0, 0, 1.8), (0.29, 0.31, 0.36), "steel", verts=8),                 # bucket helm
            lambda: part("cyl", (0, 0, 1.99), (0.27, 0.29, 0.03), "steel_light", verts=8),          # flat top
            lambda: part("cyl", (0, 0, 1.64), (0.31, 0.33, 0.04), "steel_edge", verts=8),           # rim
            lambda: part("cyl", (0, 0, 1.9), (0.3, 0.32, 0.02), "steel_edge", verts=8),
            lambda: part("cube", (0, -0.155, 1.79), (0.03, 0.03, 0.32), "steel_light"),              # face ridge
            lambda: part("cube", (-0.058, -0.152, 1.84), (0.07, 0.02, 0.04), "black"),               # eye holes
            lambda: part("cube", (0.058, -0.152, 1.84), (0.07, 0.02, 0.04), "black"),
            lambda: part("cube", (-0.05, -0.152, 1.72), (0.015, 0.02, 0.015), "black"),              # breaths
            lambda: part("cube", (0.05, -0.152, 1.72), (0.015, 0.02, 0.015), "black"),
            lambda: part("cube", (-0.05, -0.152, 1.69), (0.015, 0.02, 0.015), "black"),
            lambda: part("cube", (0.05, -0.152, 1.69), (0.015, 0.02, 0.015), "black"),
        ],
        arm_extra_l=[lambda: couter(1)],
        arm_extra_r=[lambda: couter(-1)],
    )


def ranger():
    """Green archer after the reference: green tunic with dark trim and split skirt, short sleeves, leather bracers,
    white leggings, tall folded boots, gold-buckled belt, pointed cap with a feather, blonde hair, quiver."""
    c = dict(torso="ranger_green", chest="ranger_green", arms="skin", shoulder="ranger_green", forearm="leather", hands="skin",
             legs="cloth_white", shins="cloth_white", boots="leather", belt="leather_dark", skin="skin", skin_dark="skin_dark")
    body3(
        c,
        upper_extra=[lambda s: [soft("cone", (0.262 * s, 0, 1.43), (0.2, 0.19, 0.18), "ranger_green", verts=10, r2=0.34),   # sleeve
                                soft("cyl", (0.268 * s, 0, 1.345), (0.19, 0.18, 0.02), "green_dark", verts=10)]],
        arm_extra_l=[lambda: [soft("cyl", (0.31, -0.01, 1.08), (0.15, 0.14, 0.18), "leather", verts=8),       # bracer
                              soft("cyl", (0.31, -0.01, 1.13), (0.155, 0.145, 0.015), "leather_dark", verts=8),
                              soft("cyl", (0.31, -0.01, 1.03), (0.155, 0.145, 0.015), "leather_dark", verts=8)]],
        arm_extra_r=[lambda: [soft("cyl", (-0.31, -0.01, 1.08), (0.15, 0.14, 0.18), "leather", verts=8),
                              soft("cyl", (-0.31, -0.01, 1.13), (0.155, 0.145, 0.015), "leather_dark", verts=8),
                              soft("cyl", (-0.31, -0.01, 1.03), (0.155, 0.145, 0.015), "leather_dark", verts=8)]],
        shin_extra=[lambda s: [soft("cone", (0.105 * s, 0, 0.37), (0.17, 0.18, 0.06), "leather_light", verts=10, r2=0.42),  # boot fold
                               soft("cyl", (0.105 * s, 0.005, 0.23), (0.15, 0.16, 0.26), "leather", verts=10)]],          # tall boot
        body_extra=[
            lambda: soft("cone", (0, -0.01, 0.86), (0.42, 0.32, 0.3), "ranger_green", verts=12, r2=0.36),   # tunic skirt
            lambda: soft("cone", (0, -0.01, 0.725), (0.44, 0.34, 0.03), "green_dark", verts=12, r2=0.48),   # hem trim
            lambda: part("cube", (0, -0.16, 0.82), (0.03, 0.03, 0.22), "green_dark"),                       # skirt split
            lambda: soft("cone", (0, -0.1, 1.5), (0.16, 0.06, 0.12), "green_dark", verts=3, rot=(180, 0, 0)),   # V collar
            lambda: part("cube", (0, -0.12, 1.06), (0.08, 0.02, 0.07), "gold_trim"),
            lambda: soft("cyl", (0.1, 0.15, 1.38), (0.11, 0.11, 0.5), "leather", rot=(-12, 0, -22), verts=8),   # quiver
            lambda: soft("cyl", (0.03, 0.2, 1.62), (0.12, 0.12, 0.02), "leather_dark", rot=(-12, 0, -22), verts=8),
            lambda: soft("cone", (0.04, 0.19, 1.69), (0.05, 0.03, 0.15), "cloth_red", rot=(-12, 0, -22), verts=3),
            lambda: soft("cone", (0.1, 0.2, 1.7), (0.05, 0.03, 0.15), "cloth_red", rot=(-12, 0, -22), verts=3),
            lambda: soft("cone", (0.16, 0.21, 1.66), (0.05, 0.03, 0.15), "white", rot=(-12, 0, -22), verts=3),
            lambda: part("cube", (0, -0.13, 1.32), (0.035, 0.02, 0.46), "leather_dark", rot=(0, 35, 0)),   # strap
        ],
        head_extra=[
            lambda: soft("ico", (0, 0.03, 1.81), (0.265, 0.275, 0.27), "hair_blonde", sub=2),           # blonde hair
            lambda: soft("cone", (0, 0.07, 1.66), (0.26, 0.16, 0.24), "hair_blonde", verts=8, r2=0.3, rot=(180, 0, 0)),  # hair to shoulders
            lambda: soft("cone", (-0.07, -0.11, 1.86), (0.1, 0.05, 0.1), "hair_blonde", verts=4, rot=(-120, 0, 25)),   # bangs
            lambda: soft("cone", (0.05, -0.115, 1.865), (0.1, 0.05, 0.09), "hair_blonde", verts=4, rot=(-120, 0, -20)),
            lambda: soft("cone", (0, 0.02, 1.9), (0.28, 0.3, 0.2), "ranger_green", verts=10, r2=0.18, rot=(-10, 0, 0)),  # cap
            lambda: soft("cyl", (0, 0.0, 1.84), (0.285, 0.305, 0.02), "green_dark", verts=10),
            lambda: soft("cone", (0, 0.15, 1.98), (0.1, 0.1, 0.24), "ranger_green", verts=6, rot=(-75, 0, 0)),          # cap tip
            lambda: soft("cone", (0.11, 0.06, 1.99), (0.03, 0.02, 0.22), "cloth_red", verts=3, rot=(-40, 25, 0)),       # feather
        ],
    )


def mage():
    """Red mage after the Megabonk reference: shadowed face with glowing eyes, wide-brim hat, high collar,
    long red coat with a jagged hem and dark trim, black belt with gold buckle, dark gloves, glowing hands."""
    c = dict(torso="mage_red", chest="mage_red", arms="mage_red", shoulder="mage_red", forearm="steel_edge", hands="steel_edge",
             legs="mage_red_dark", shins="mage_red_dark", boots="black", belt="black", skin="black", skin_dark="black")
    body3(
        c, face="none",
        upper_extra=[lambda s: soft("cone", (0.27 * s, 0, 1.4), (0.2, 0.19, 0.3), "mage_red", verts=10, r2=0.32)],   # sleeves
        arm_extra_l=[lambda: [soft("cone", (0.31, -0.01, 1.2), (0.17, 0.17, 0.14), "mage_red_dark", verts=10, r2=0.34, rot=(180, 0, 0)),  # cuff
                              soft("ico", (0.34, -0.07, 0.86), (0.13, 0.13, 0.13), "lantern_glow", sub=2)]],      # magic orb
        arm_extra_r=[lambda: [soft("cone", (-0.31, -0.01, 1.2), (0.17, 0.17, 0.14), "mage_red_dark", verts=10, r2=0.34, rot=(180, 0, 0)),
                              soft("ico", (-0.34, -0.07, 0.86), (0.13, 0.13, 0.13), "lantern_glow", sub=2)]],
        body_extra=[
            lambda: jagged_hem(1.12, 0.1, 0.16, 0.25, "mage_red", points=7, depth=0.24, y_scale=0.75),  # long coat
            lambda: part("cube", (0, -0.13, 0.62), (0.02, 0.02, 0.9), "mage_red_dark"),                  # coat opening
            lambda: soft("cone", (0, 0.13, 0.95), (0.48, 0.07, 1.05), "mage_red_dark", verts=4, r2=0.3, rot=(4, 0, 45)),  # back cape
            lambda: soft("cone", (0, 0.0, 1.6), (0.36, 0.32, 0.24), "mage_red", verts=10, r2=0.62),     # high collar
            lambda: soft("cone", (0, 0.0, 1.715), (0.45, 0.4, 0.02), "mage_red_dark", verts=10, r2=0.5),
            lambda: soft("cone", (-0.23, 0, 1.49), (0.26, 0.26, 0.16), "mage_red", verts=8, r2=0.2),    # shoulder capes
            lambda: soft("cone", (0.23, 0, 1.49), (0.26, 0.26, 0.16), "mage_red", verts=8, r2=0.2),
            lambda: soft("cyl", (0, 0, 1.06), (0.31, 0.23, 0.08), "black", verts=10),
            lambda: plate("cube", (0, -0.125, 1.06), (0.09, 0.02, 0.07), "black", edge="gold_trim", grow=(1.5, 0.5, 1.6)),  # buckle
        ],
        head_extra=[
            lambda: part("cube", (-0.05, -0.128, 1.79), (0.045, 0.02, 0.022), "lantern_glow"),          # glowing eyes in shadow
            lambda: part("cube", (0.05, -0.128, 1.79), (0.045, 0.02, 0.022), "lantern_glow"),
            lambda: soft("cone", (0, 0, 1.915), (0.62, 0.62, 0.05), "mage_red", verts=14, r2=0.42),   # wide brim
            lambda: soft("cone", (0, 0.03, 2.13), (0.36, 0.36, 0.4), "mage_red", verts=12, r2=0.17, rot=(-8, 0, 0)),
            lambda: soft("cone", (0, 0.1, 2.38), (0.13, 0.13, 0.22), "mage_red", verts=8, rot=(-32, 0, 0)),
            lambda: soft("cyl", (0, 0, 1.97), (0.34, 0.34, 0.06), "steel_edge", verts=12),             # hat band
        ],
    )


def alchemist():
    """Wandering alchemist: layered orange mantle with a dark trim, satchel, pouch belt, gloves, tall boots, goggles."""
    c = dict(torso="leather_dark", chest="cloth_white", arms="cloth_white", forearm="leather", hands="leather_dark",
             legs="leather_dark", shins="leather_dark", boots="leather", belt="leather", skin="skin", skin_dark="skin_dark")
    body3(
        c,
        upper_extra=[lambda s: soft("cone", (0.27 * s, 0, 1.4), (0.18, 0.17, 0.26), "cloth_white", verts=10, r2=0.36)],
        arm_extra_l=[lambda: soft("cone", (0.31, -0.01, 1.05), (0.15, 0.15, 0.16), "leather", verts=8, r2=0.36, rot=(180, 0, 0))],   # gloves
        arm_extra_r=[lambda: soft("cone", (-0.31, -0.01, 1.05), (0.15, 0.15, 0.16), "leather", verts=8, r2=0.36, rot=(180, 0, 0))],
        shin_extra=[lambda s: [soft("cyl", (0.105 * s, 0.005, 0.24), (0.16, 0.17, 0.28), "leather", verts=10),
                               soft("cone", (0.105 * s, 0, 0.39), (0.18, 0.19, 0.05), "leather_light", verts=10, r2=0.44)]],
        body_extra=[
            lambda: soft("cone", (0, 0.0, 1.4), (0.62, 0.52, 0.36), "alch_orange", verts=12, r2=0.3),      # poncho
            lambda: soft("cone", (0, 0.0, 1.225), (0.63, 0.53, 0.03), "alch_dark", verts=12, r2=0.49),     # poncho trim
            lambda: soft("cone", (0, 0.0, 1.62), (0.3, 0.26, 0.1), "alch_dark", verts=10, r2=0.4),        # hood rolled down
            lambda: soft("cone", (0, -0.1, 0.92), (0.3, 0.06, 0.36), "alch_orange", verts=4, r2=0.36, rot=(0, 0, 45)),   # apron
            lambda: soft("cube", (0, 0.18, 1.28), (0.3, 0.14, 0.34), "leather"),                         # backpack
            lambda: soft("cube", (0, 0.26, 1.18), (0.28, 0.04, 0.1), "leather_dark"),
            lambda: soft("cyl", (-0.08, 0.19, 1.52), (0.07, 0.07, 0.15), "poison", verts=8),
            lambda: soft("cyl", (0.08, 0.19, 1.52), (0.07, 0.07, 0.15), "gem_blue", verts=8),
            lambda: soft("cyl", (-0.17, -0.07, 1.0), (0.08, 0.08, 0.12), "gem_red", verts=8),            # belt vials
            lambda: soft("cyl", (0.17, -0.07, 1.0), (0.08, 0.08, 0.12), "poison", verts=8),
            lambda: soft("cube", (0.2, 0.02, 0.97), (0.08, 0.14, 0.12), "leather"),                       # pouches
            lambda: soft("cube", (-0.2, 0.04, 0.97), (0.07, 0.12, 0.1), "leather_light"),
            lambda: plate("cube", (0, -0.12, 1.06), (0.07, 0.02, 0.06), "leather_dark", edge="gold_trim", grow=(1.5, 0.5, 1.6)),
        ],
        head_extra=[
            lambda: soft("ico", (0, 0.03, 1.82), (0.27, 0.28, 0.26), "leather_dark", sub=2),             # hair
            lambda: soft("cone", (-0.06, -0.105, 1.89), (0.11, 0.06, 0.11), "leather_dark", verts=4, rot=(-120, 0, 25)),
            lambda: soft("cone", (0.06, -0.11, 1.9), (0.1, 0.06, 0.1), "leather_dark", verts=4, rot=(-120, 0, -25)),
            lambda: soft("cyl", (0, 0, 1.86), (0.27, 0.29, 0.03), "leather", verts=12),                  # goggle strap
            lambda: soft("cyl", (-0.055, -0.13, 1.87), (0.085, 0.085, 0.04), "gold", rot=(90, 0, 0), verts=10),
            lambda: soft("cyl", (0.055, -0.13, 1.87), (0.085, 0.085, 0.04), "gold", rot=(90, 0, 0), verts=10),
            lambda: soft("cyl", (-0.055, -0.152, 1.87), (0.06, 0.06, 0.01), "glass", rot=(90, 0, 0), verts=10),
            lambda: soft("cyl", (0.055, -0.152, 1.87), (0.06, 0.06, 0.01), "glass", rot=(90, 0, 0), verts=10),
            lambda: soft("cone", (0, -0.12, 1.66), (0.2, 0.08, 0.06), "alch_dark", verts=8, r2=0.4),      # scarf
        ],
    )


def bone(a, b, r, color="bone"):
    """Long bone: thin shaft with knobbed ends (epiphyses)."""
    mid = tuple((a[i] + b[i]) / 2 for i in range(3))
    return skin([(a, (r * 1.7, r * 1.5)), (mid, (r, r)), (b, (r * 1.7, r * 1.5))], color)


def skeleton():
    """Megabonk-style skeleton: big cranium with deep sockets and a toothy jaw, curved ribs, vertebrae, winged pelvis,
    knobbed limb bones. Smooth bone surfaces, dark cavities."""
    body = [skin([((0, 0.05, 0.98), (0.035, 0.035)), ((0, 0.06, 1.2), (0.03, 0.03)), ((0, 0.04, 1.45), (0.032, 0.032)),
                  ((0, 0.02, 1.62), (0.028, 0.028))], "bone_shadow")]                                      # spine
    for i in range(9):                                                                                      # vertebrae
        z = 1.0 + i * 0.07
        body.append(soft("ico", (0, 0.07, z), (0.07, 0.06, 0.04), "bone", sub=1))
    for i, (z, w) in enumerate(((1.47, 0.38), (1.39, 0.4), (1.31, 0.38), (1.23, 0.33))):                    # ribs
        body.append(soft("torus", (0, 0.0, z), (w, 0.27, 0.22), "bone", verts=14))
    body += [
        soft("cube", (0, -0.13, 1.35), (0.05, 0.03, 0.26), "bone"),                                         # sternum
        bone((-0.22, 0.0, 1.53), (0.22, 0.0, 1.53), 0.028),                                                  # collarbones
        soft("ico", (-0.13, 0.02, 0.98), (0.2, 0.1, 0.15), "bone", sub=2, rot=(0, 0, 20)),                 # pelvis wings
        soft("ico", (0.13, 0.02, 0.98), (0.2, 0.1, 0.15), "bone", sub=2, rot=(0, 0, -20)),
        soft("ico", (0, 0.06, 0.94), (0.1, 0.08, 0.12), "bone_shadow", sub=1),                              # sacrum
    ]
    Body = group("Body", body, (0, 0, HIP_Z))

    skull = [
        soft("ico", (0, 0.02, 1.8), (0.3, 0.32, 0.29), "bone", sub=2),                                      # cranium
        soft("ico", (0, -0.07, 1.72), (0.24, 0.18, 0.16), "bone", sub=2),                                   # face / cheekbones
        soft("ico", (-0.06, -0.135, 1.775), (0.085, 0.05, 0.085), "black", sub=2),                          # sockets
        soft("ico", (0.06, -0.135, 1.775), (0.085, 0.05, 0.085), "black", sub=2),
        soft("ico", (-0.06, -0.152, 1.775), (0.022, 0.02, 0.022), "eye_red", sub=1),                        # ember pupils
        soft("ico", (0.06, -0.152, 1.775), (0.022, 0.02, 0.022), "eye_red", sub=1),
        soft("cone", (0, -0.15, 1.715), (0.045, 0.03, 0.05), "black", verts=3, rot=(-90, 0, 180)),         # nasal cavity
        soft("ico", (0, -0.06, 1.635), (0.2, 0.16, 0.07), "bone_shadow", sub=2),                            # jaw
        part("cube", (0, -0.14, 1.67), (0.15, 0.02, 0.012), "black"),                                       # mouth gap
    ]
    for i in range(6):                                                                                      # teeth
        x = -0.055 + i * 0.022
        skull.append(part("cube", (x, -0.145, 1.682), (0.016, 0.015, 0.022), "bone"))
        skull.append(part("cube", (x, -0.14, 1.655), (0.016, 0.015, 0.02), "bone"))
    JOINTS.append(group("Head", skull, (0, 0, NECK_Z)))

    def arm(side):
        x = side
        upper = group("ArmR" if side < 0 else "ArmL", [
            soft("ico", (0.24 * x, 0, 1.52), (0.08, 0.08, 0.08), "bone", sub=1),
            bone((0.25 * x, 0, 1.5), (0.29 * x, 0, 1.25), 0.026)], (0.25 * x, 0, SHOULDER_Z))
        ps = [
            bone((0.29 * x, 0, 1.25), (0.31 * x, -0.02, 0.98), 0.022),
            bone((0.3 * x, 0.015, 1.24), (0.32 * x, 0.0, 0.99), 0.016, "bone_shadow"),                        # radius + ulna
            soft("ico", (0.315 * x, -0.02, 0.93), (0.07, 0.04, 0.07), "bone", sub=1),                          # hand
        ]
        for k in range(3):                                                                                   # fingers
            ps.append(bone((0.3 * x + 0.02 * k * x, -0.03, 0.9), (0.3 * x + 0.02 * k * x, -0.04, 0.84), 0.008))
        if side < 0:  # right hand: rusty blade
            ps.append(part("cube", (0.315 * x, -0.17, 0.91), (0.03, 0.36, 0.06), "dark_iron"))
            ps.append(part("cube", (0.315 * x, -0.17, 0.93), (0.012, 0.36, 0.02), "steel"))
            ps.append(part("cube", (0.315 * x, -0.02, 0.91), (0.03, 0.05, 0.12), "leather_dark"))
        JOINTS.append(group("ForeArmR" if side < 0 else "ForeArmL", ps, (0.29 * x, 0, ELBOW_Z)))
        return upper

    def leg(side):
        x = 0.1 * side
        thigh = group("LegR" if side < 0 else "LegL", [bone((x, 0, 0.94), (x, -0.01, 0.53), 0.032)], (x, 0, HIP_Z))
        shin = group("ShinR" if side < 0 else "ShinL", [
            soft("ico", (x, -0.04, 0.53), (0.07, 0.05, 0.07), "bone", sub=1),                                # kneecap
            bone((x, -0.01, 0.53), (x, 0, 0.1), 0.026),
            bone((x + 0.03 * side, 0.01, 0.5), (x + 0.02 * side, 0.01, 0.12), 0.014, "bone_shadow"),          # fibula
            soft("ico", (x, -0.06, 0.05), (0.1, 0.22, 0.06), "bone", sub=1),                                  # foot
        ], (x, 0, KNEE_Z))
        JOINTS.append(shin)
        return thigh

    parts = [Body, arm(-1), arm(1), leg(-1), leg(1)]
    root_with(parts + JOINTS)


SMOOTH_ENEMIES = {"Slime", "MagmaSlime", "Bat", "FireImp", "BombShroom", "TreasureSlime", "Wraith"}


def _smooth_all():
    for o in bpy.data.objects:
        if o.type == "MESH":
            for p in o.data.polygons:
                p.use_smooth = True


def eye(x, y, z, r, pupil="black", white="white", look=(0, 0)):
    """Cartoon eye: white ball, pupil, glint (faces -Y)."""
    return [soft("ico", (x, y, z), (r * 2.2, r * 1.2, r * 2.5), white, sub=2),
            soft("ico", (x + look[0] * r * 0.3, y - r * 0.55, z + look[1] * r * 0.3), (r * 0.95, r * 0.6, r * 1.15), pupil, sub=2),
            soft("ico", (x + r * 0.25, y - r * 0.85, z + r * 0.45), (r * 0.4, r * 0.2, r * 0.4), white, sub=1)]


def slime():
    body = [
        soft("ico", (0, 0, 0.4), (1.0, 0.95, 0.78), "slime_green", sub=3),                     # jelly dome
        soft("ico", (0, 0, 0.12), (1.1, 1.05, 0.26), "slime_green", sub=2),                    # squashed base
        soft("ico", (0.05, 0.12, 0.42), (0.42, 0.42, 0.36), "slime_core", sub=2),              # core
        soft("ico", (-0.22, -0.2, 0.66), (0.2, 0.12, 0.12), "white", sub=2, rot=(0, -30, 0)),  # shine
        soft("ico", (-0.33, -0.24, 0.52), (0.07, 0.05, 0.07), "white", sub=1),
        soft("cone", (0, -0.45, 0.3), (0.2, 0.05, 0.08), "slime_dark", verts=8, rot=(90, 0, 0)),   # smile
    ]
    body += eye(-0.17, -0.42, 0.48, 0.07) + eye(0.17, -0.42, 0.48, 0.07)
    for x, z in ((0.35, 0.78), (-0.1, 0.83)):                                                    # bubbles
        body.append(soft("ico", (x, -0.05, z), (0.08, 0.08, 0.08), "slime_core", sub=1))
    root_with([group("Body", body, (0, 0, 0))])


def magma_slime():
    random.seed(31)
    body = [
        soft("ico", (0, 0, 0.4), (1.0, 0.95, 0.78), "magma_skin", sub=3),
        soft("ico", (0, 0, 0.12), (1.1, 1.05, 0.26), "magma_skin", sub=2),
        soft("ico", (-0.22, -0.2, 0.66), (0.18, 0.1, 0.1), "magma_core", sub=2, rot=(0, -30, 0)),
    ]
    for i in range(6):                                                                           # glowing fissures
        a = math.radians(i * 60 + random.uniform(-15, 15))
        body.append(soft("cube", (math.cos(a) * 0.43, math.sin(a) * 0.41, 0.42), (0.035, 0.3, 0.05), "magma",
                         rot=(random.uniform(-40, 40), 0, math.degrees(a))))
    for i in range(5):                                                                           # cooled crust plates
        a = math.radians(i * 72 + 20)
        body.append(soft("ico", (math.cos(a) * 0.3, math.sin(a) * 0.3, 0.7), (0.24, 0.24, 0.1), "basalt_dark", sub=1,
                         rot=(random.uniform(-25, 25), random.uniform(-25, 25), 0)))
    body += eye(-0.17, -0.42, 0.46, 0.07, pupil="magma") + eye(0.17, -0.42, 0.46, 0.07, pupil="magma")
    body += [soft("cone", (0, -0.45, 0.28), (0.24, 0.05, 0.1), "basalt_dark", verts=8, rot=(90, 0, 0)),
             soft("cone", (0, 0.0, 0.88), (0.12, 0.12, 0.2), "magma", verts=6)]                 # little eruption
    root_with([group("Body", body, (0, 0, 0))])


def bat_wing(side, membrane, bone_c):
    """Membrane wing: three bone fingers with scalloped skin panels between them."""
    x0 = 0.15 * side
    ps = [bone((x0, 0.03, 0.08), (x0 + 0.32 * side, 0.03, 0.2), 0.022, bone_c)]                 # arm
    tip = (x0 + 0.32 * side, 0.03, 0.2)
    ends = [(x0 + 0.78 * side, 0.03, 0.18), (x0 + 0.7 * side, 0.03, -0.12), (x0 + 0.42 * side, 0.03, -0.24)]
    prev = (x0 + 0.05 * side, 0.03, -0.12)
    for e in ends:
        ps.append(bone(tip, e, 0.012, bone_c))
    pts = [tip] + ends
    # panels between consecutive fingers (and the body)
    for a, b in zip(pts[1:], pts[2:] + [prev]):
        cx = (tip[0] + a[0] + b[0]) / 3
        cz = (tip[2] + a[2] + b[2]) / 3
        w = math.dist((a[0], a[2]), (b[0], b[2]))
        h = math.dist((tip[0], tip[2]), ((a[0] + b[0]) / 2, (a[2] + b[2]) / 2))
        ang = math.degrees(math.atan2((a[0] + b[0]) / 2 - tip[0], (a[2] + b[2]) / 2 - tip[2]))
        ps.append(soft("cone", (cx, 0.03, cz), (w * 1.05, 0.02, h * 1.1), membrane, verts=3, rot=(0, ang + 180, 0)))
    return group("WingR" if side < 0 else "WingL", ps, (x0, 0.03, 0.1))


def bat():
    body = [
        soft("ico", (0, 0, 0.0), (0.4, 0.36, 0.38), "mage_dark", sub=2),                       # furry body
        soft("ico", (0, -0.04, 0.17), (0.32, 0.3, 0.27), "mage_dark", sub=2),                  # head
        soft("cone", (-0.1, 0.0, 0.36), (0.13, 0.08, 0.22), "mage_dark", verts=6, rot=(0, -15, 0)),   # big ears
        soft("cone", (0.1, 0.0, 0.36), (0.13, 0.08, 0.22), "mage_dark", verts=6, rot=(0, 15, 0)),
        soft("cone", (-0.1, -0.02, 0.35), (0.07, 0.04, 0.15), "heart_red", verts=6, rot=(0, -15, 0)),
        soft("cone", (0.1, -0.02, 0.35), (0.07, 0.04, 0.15), "heart_red", verts=6, rot=(0, 15, 0)),
        soft("ico", (0, -0.17, 0.12), (0.08, 0.05, 0.06), "mage_purple", sub=1),               # snout
        soft("cone", (-0.03, -0.17, 0.06), (0.02, 0.02, 0.06), "white", verts=4, rot=(180, 0, 0)),   # fangs
        soft("cone", (0.03, -0.17, 0.06), (0.02, 0.02, 0.06), "white", verts=4, rot=(180, 0, 0)),
        soft("ico", (-0.06, 0, -0.2), (0.06, 0.06, 0.08), "mage_purple", sub=1),               # feet
        soft("ico", (0.06, 0, -0.2), (0.06, 0.06, 0.08), "mage_purple", sub=1),
    ]
    body += eye(-0.065, -0.15, 0.2, 0.04, pupil="eye_red") + eye(0.065, -0.15, 0.2, 0.04, pupil="eye_red")
    root_with([group("Body", body, (0, 0, 0)), bat_wing(-1, "mage_purple", "mage_dark"), bat_wing(1, "mage_purple", "mage_dark")])


def fire_imp():
    body = [
        soft("ico", (0, 0, 0.0), (0.4, 0.34, 0.44), "imp_red", sub=2),                         # pot belly
        soft("ico", (0, -0.08, -0.02), (0.24, 0.12, 0.26), "imp_dark", sub=2),                 # belly
        soft("ico", (0, -0.03, 0.34), (0.36, 0.33, 0.32), "imp_red", sub=2),                   # head
        soft("cone", (-0.1, 0.0, 0.53), (0.09, 0.09, 0.24), "basalt_dark", verts=6, rot=(0, -28, 0)),   # horns
        soft("cone", (0.1, 0.0, 0.53), (0.09, 0.09, 0.24), "basalt_dark", verts=6, rot=(0, 28, 0)),
        soft("cone", (-0.19, 0.0, 0.37), (0.06, 0.12, 0.14), "imp_red", verts=4, rot=(0, -75, 0)),     # pointed ears
        soft("cone", (0.19, 0.0, 0.37), (0.06, 0.12, 0.14), "imp_red", verts=4, rot=(0, 75, 0)),
        soft("cone", (0, -0.16, 0.25), (0.14, 0.04, 0.05), "black", verts=8, rot=(90, 0, 0)),          # grin
        soft("cone", (-0.04, -0.17, 0.235), (0.02, 0.015, 0.035), "white", verts=4, rot=(180, 0, 0)),
        soft("cone", (0.04, -0.17, 0.235), (0.02, 0.015, 0.035), "white", verts=4, rot=(180, 0, 0)),
        bone((-0.15, 0, 0.08), (-0.22, -0.08, -0.1), 0.03, "imp_red"),                                   # arms
        bone((0.15, 0, 0.08), (0.24, -0.1, -0.02), 0.03, "imp_red"),
        bone((-0.1, 0, -0.18), (-0.12, -0.03, -0.36), 0.035, "imp_dark"),                               # legs
        bone((0.1, 0, -0.18), (0.12, -0.03, -0.36), 0.035, "imp_dark"),
        skin([((0, 0.18, -0.12), (0.035, 0.035)), ((0, 0.32, -0.22), (0.025, 0.025)), ((0, 0.38, -0.08), (0.015, 0.015))], "imp_dark"),  # tail
        soft("cone", (0, 0.4, -0.02), (0.1, 0.03, 0.12), "imp_dark", verts=3),
        soft("ico", (0.27, -0.13, 0.0), (0.2, 0.2, 0.2), "magma", sub=2),                       # fireball in claw
        soft("ico", (0.27, -0.13, 0.0), (0.11, 0.11, 0.11), "magma_core", sub=2),
    ]
    body += eye(-0.075, -0.15, 0.37, 0.042, pupil="black", white="magma_core") + eye(0.075, -0.15, 0.37, 0.042, pupil="black", white="magma_core")
    root_with([group("Body", body, (0, 0, 0)), bat_wing(-1, "imp_dark", "basalt_dark"), bat_wing(1, "imp_dark", "basalt_dark")])


def bomb_shroom():
    body = [
        soft("cyl", (0, 0, 0.3), (0.44, 0.42, 0.58), "mushroom_stem", verts=12),                # stem
        soft("ico", (0, 0, 0.08), (0.52, 0.5, 0.18), "mushroom_stem", sub=2),
        soft("ico", (0, 0, 0.78), (1.05, 1.05, 0.62), "mushroom_red", sub=3),                   # dome cap
        soft("cone", (0, 0, 0.6), (1.0, 1.0, 0.1), "mushroom_stem", verts=16, r2=0.3),          # gills
    ]
    for (x, y, z, r) in ((0.25, -0.32, 0.9, 0.12), (-0.28, -0.25, 0.95, 0.1), (0.05, 0.36, 1.0, 0.11),
                         (-0.05, -0.1, 1.08, 0.09), (0.38, 0.12, 0.92, 0.08), (-0.36, 0.2, 0.88, 0.09)):
        body.append(soft("ico", (x, y, z), (r * 2, r * 2, r), "white", sub=1))                # spots
    body += eye(-0.09, -0.2, 0.42, 0.045) + eye(0.09, -0.2, 0.42, 0.045)
    body += [
        soft("cube", (-0.09, -0.235, 0.5), (0.09, 0.02, 0.02), "black", rot=(0, -20, 0)),       # angry brows
        soft("cube", (0.09, -0.235, 0.5), (0.09, 0.02, 0.02), "black", rot=(0, 20, 0)),
        soft("cone", (0, -0.22, 0.3), (0.12, 0.04, 0.05), "black", verts=8, rot=(-90, 0, 0)),   # frown
        skin([((0, 0, 1.05), (0.03, 0.03)), ((0.04, 0, 1.2), (0.025, 0.025)), ((0.0, 0, 1.3), (0.02, 0.02))], "dark_iron"),  # fuse
        soft("ico", (0, 0, 1.33), (0.1, 0.1, 0.1), "ember", sub=2),
    ]
    root_with([group("Body", body, (0, 0, 0))])


def rock_chunk(loc, size, color, seed, sub=1):
    """Faceted boulder (flat shaded so it reads as cut stone)."""
    random.seed(seed)
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=sub, radius=0.5, location=loc)
    o = bpy.context.active_object
    for v in o.data.vertices:
        v.co *= random.uniform(0.82, 1.12)
    return _finish(o, size, color)


def golem():
    """Stone golem: boulder torso and limbs, mossy shoulders, glowing rune core and eyes, huge fists."""
    body = [
        rock_chunk((0, 0, 1.38), (0.86, 0.58, 0.62), "stone", 1),                                   # chest boulder
        rock_chunk((0, 0.02, 1.02), (0.56, 0.42, 0.36), "stone_dark", 2),                          # belly
        rock_chunk((0, 0, 0.88), (0.5, 0.38, 0.26), "stone", 3),                                   # hips
        soft("ico", (-0.4, 0.02, 1.62), (0.42, 0.42, 0.24), "moss", sub=2),                        # mossy shoulders
        soft("ico", (0.36, 0.05, 1.6), (0.3, 0.3, 0.16), "moss", sub=2),
        rock_chunk((0, -0.28, 1.4), (0.22, 0.06, 0.22), "rune_blue", 4),                           # rune core
        part("cube", (0, -0.31, 1.4), (0.06, 0.02, 0.16), "crystal_light"),
        rock_chunk((0.12, 0.25, 1.25), (0.3, 0.12, 0.26), "moss", 5),
    ]
    Body = group("Body", body, (0, 0, HIP_Z))
    head = [rock_chunk((0, -0.04, 1.8), (0.36, 0.34, 0.3), "stone", 6),
            part("cube", (0, -0.2, 1.88), (0.3, 0.06, 0.06), "stone_dark"),                         # brow ridge
            soft("ico", (-0.075, -0.2, 1.81), (0.07, 0.03, 0.05), "rune_blue", sub=1),               # glowing eyes
            soft("ico", (0.075, -0.2, 1.81), (0.07, 0.03, 0.05), "rune_blue", sub=1)]
    JOINTS.append(group("Head", head, (0, 0, NECK_Z)))

    def arm(side):
        x = 0.46 * side
        upper = group("ArmR" if side < 0 else "ArmL", [rock_chunk((x, 0, 1.4), (0.3, 0.3, 0.38), "stone_dark", 10 + side)],
                      (x, 0, SHOULDER_Z))
        fore = [rock_chunk((x * 1.04, -0.01, 1.08), (0.3, 0.3, 0.36), "stone", 20 + side),
                rock_chunk((x * 1.06, -0.03, 0.82), (0.36, 0.34, 0.3), "stone_dark", 30 + side),        # huge fist
                soft("ico", (x * 1.04, 0.1, 1.12), (0.16, 0.12, 0.1), "moss", sub=1)]
        JOINTS.append(group("ForeArmR" if side < 0 else "ForeArmL", fore, (x, 0, ELBOW_Z)))
        return upper

    def leg(side):
        x = 0.17 * side
        thigh = group("LegR" if side < 0 else "LegL", [rock_chunk((x, 0, 0.72), (0.28, 0.3, 0.42), "stone_dark", 40 + side)], (x, 0, HIP_Z))
        shin = group("ShinR" if side < 0 else "ShinL", [
            rock_chunk((x, 0, 0.32), (0.26, 0.28, 0.42), "stone", 50 + side),
            rock_chunk((x, -0.06, 0.07), (0.32, 0.4, 0.16), "stone_dark", 60 + side)], (x, 0, KNEE_Z))
        JOINTS.append(shin)
        return thigh

    parts = [Body, arm(-1), arm(1), leg(-1), leg(1)]
    root_with(parts + JOINTS)


def skeleton_archer():
    skeleton()
    head = bpy.data.objects.get("Head")
    hood = [soft("ico", (0, 0.03, 1.82), (0.36, 0.38, 0.36), "cloth_red", sub=2),                   # cloth hood over the skull
            soft("cone", (0, 0.14, 1.66), (0.34, 0.24, 0.3), "cloth_red", verts=8, r2=0.3, rot=(180, 0, 0)),
            soft("cone", (0, 0.06, 2.0), (0.1, 0.1, 0.16), "cloth_red", verts=6, rot=(-60, 0, 0))]
    bpy.ops.object.select_all(action="DESELECT")
    for h in hood:
        h.select_set(True)
    head.select_set(True)
    bpy.context.view_layer.objects.active = head
    bpy.ops.object.join()
    # the hood swallows the front of the skull: cut the face back in front of it
    bow = []
    for i in range(6):
        t0 = -1 + 2 * i / 6
        t1 = -1 + 2 * (i + 1) / 6
        z0, z1 = 0.95 + t0 * 0.5, 0.95 + t1 * 0.5
        y0, y1 = -0.08 - 0.16 * (1 - t0 * t0), -0.08 - 0.16 * (1 - t1 * t1)
        ang = math.degrees(math.atan2(y1 - y0, z1 - z0))
        bow.append(soft("cube", (0.31, (y0 + y1) / 2, (z0 + z1) / 2), (0.035, 0.045, abs(z1 - z0) * 1.15), "wood", rot=(-ang, 0, 0)))
    bow.append(part("cube", (0.31, -0.08, 0.95), (0.01, 0.01, 1.0), "rope"))
    fore = bpy.data.objects.get("ForeArmL")
    bpy.ops.object.select_all(action="DESELECT")
    for b in bow:
        b.select_set(True)
    fore.select_set(True)
    bpy.context.view_layer.objects.active = fore
    bpy.ops.object.join()


def mage():
    """Red-robed sage: deep hood up over a visible old face with a long white beard, gold-trimmed robe with a
    straight hem, layered bell sleeves, a sash and a stole with rune patches, glowing rune pendant."""
    c = dict(torso="mage_red", chest="mage_red", arms="mage_red", shoulder="mage_red", forearm="mage_red", hands="skin",
             legs="mage_red_dark", shins="mage_red_dark", boots="leather_dark", belt="gold_trim", skin="skin", skin_dark="skin_dark")
    body3(
        c,
        upper_extra=[lambda s: soft("cone", (0.27 * s, 0, 1.4), (0.19, 0.18, 0.3), "mage_red", verts=10, r2=0.34)],
        arm_extra_l=[lambda: [soft("cone", (0.315, -0.01, 1.1), (0.2, 0.2, 0.24), "mage_red", verts=12, r2=0.26, rot=(180, 0, 0)),  # bell sleeve
                              soft("cone", (0.315, -0.01, 0.98), (0.21, 0.21, 0.03), "gold_trim", verts=12, r2=0.48)]],
        arm_extra_r=[lambda: [soft("cone", (-0.315, -0.01, 1.1), (0.2, 0.2, 0.24), "mage_red", verts=12, r2=0.26, rot=(180, 0, 0)),
                              soft("cone", (-0.315, -0.01, 0.98), (0.21, 0.21, 0.03), "gold_trim", verts=12, r2=0.48)]],
        body_extra=[
            lambda: soft("cone", (0, 0.0, 0.6), (0.56, 0.46, 1.04), "mage_red", verts=14, r2=0.27),         # robe, straight hem
            lambda: soft("cone", (0, 0.0, 0.095), (0.57, 0.47, 0.05), "gold_trim", verts=14, r2=0.49),     # hem trim
            lambda: part("cube", (0, -0.2, 0.55), (0.12, 0.02, 0.9), "mage_red_dark"),                    # front panel
            lambda: part("cube", (-0.065, -0.205, 0.55), (0.012, 0.012, 0.9), "gold_trim"),
            lambda: part("cube", (0.065, -0.205, 0.55), (0.012, 0.012, 0.9), "gold_trim"),
            lambda: soft("cyl", (0, 0, 1.07), (0.32, 0.24, 0.09), "gold_trim", verts=12),                 # sash
            lambda: soft("cone", (0.1, -0.12, 0.92), (0.07, 0.03, 0.28), "gold_trim", verts=4, rot=(0, 10, 0)),   # sash tail
            lambda: soft("cone", (0, 0.0, 1.5), (0.52, 0.4, 0.16), "mage_red_dark", verts=12, r2=0.38),    # shoulder mantle
            lambda: soft("cone", (0, 0.0, 1.43), (0.53, 0.41, 0.02), "gold_trim", verts=12, r2=0.49),
            lambda: part("cube", (-0.09, -0.13, 1.25), (0.07, 0.02, 0.4), "cloth_white"),                  # stole
            lambda: part("cube", (0.09, -0.13, 1.25), (0.07, 0.02, 0.4), "cloth_white"),
            lambda: part("cube", (-0.09, -0.142, 1.15), (0.04, 0.01, 0.04), "rune_blue"),
            lambda: part("cube", (0.09, -0.142, 1.15), (0.04, 0.01, 0.04), "rune_blue"),
            lambda: soft("ico", (0, -0.14, 1.38), (0.06, 0.03, 0.08), "lightning", sub=1),                 # rune pendant
            lambda: soft("cone", (0, -0.235, 1.36), (0.2, 0.1, 0.46), "cloth_white", verts=8, rot=(170, 0, 0)),   # long beard
        ],
        head_extra=[
            lambda: soft("cone", (0, -0.1, 1.67), (0.2, 0.09, 0.14), "cloth_white", verts=8, rot=(180, 0, 0)),   # moustache / beard top
            lambda: soft("cube", (-0.055, -0.128, 1.822), (0.065, 0.02, 0.02), "cloth_white"),            # bushy brows
            lambda: soft("cube", (0.055, -0.128, 1.822), (0.065, 0.02, 0.02), "cloth_white"),
            lambda: soft("ico", (0, 0.075, 1.83), (0.34, 0.32, 0.36), "mage_red", sub=2),                  # hood (face stays visible)
            lambda: soft("torus", (0, -0.075, 1.8), (0.3, 0.32, 0.4), "mage_red_dark", verts=14, rot=(90, 0, 0)),   # hood opening rim
            lambda: soft("cone", (0, 0.17, 1.88), (0.14, 0.14, 0.3), "mage_red", verts=6, rot=(-100, 0, 0)),   # hood point down the back
            lambda: soft("cyl", (0, -0.12, 1.96), (0.2, 0.03, 0.02), "gold_trim", verts=8),
        ],
    )

ROUND2_MODELS = [
    ("Enemies", "Bat", bat),
    ("Enemies", "Golem", golem),
    ("Enemies", "SkeletonArcher", skeleton_archer),
    ("Enemies", "BombShroom", bomb_shroom),
    ("Weapons", "Boomerang", boomerang),
    ("Weapons", "MeteorRock", meteor_rock),
    ("Weapons", "SpiritDagger", spirit_dagger),
    ("Weapons", "FrostShard", frost_shard),
    ("Environment", "ShrineBase", shrine_base),
    ("Environment", "ShrineCrystal", shrine_crystal),
]

EXTRA_MODELS = [
    ("Environment", "CastleWall", castle_wall),
    ("Environment", "CastleTower", castle_tower),
    ("Environment", "Arch", arch),
    ("Environment", "Brazier", brazier),
    ("Environment", "Banner", banner),
    ("Environment", "FlowersA", flowers(1)),
    ("Environment", "FlowersB", flowers(2)),
    ("Environment", "Mushrooms", mushrooms),
    ("Environment", "Crates", crates),
    ("Environment", "SkullPile", skull_pile),
    ("Environment", "RuneStone", rune_stone),
    ("Enemies", "Crown", crown),
]

MODELS = [
    ("Characters", "Knight", knight),
    ("Characters", "Ranger", ranger),
    ("Characters", "Mage", mage),
    ("Characters", "Alchemist", alchemist),
    ("Enemies", "Skeleton", skeleton),
    ("Enemies", "Slime", slime),
    ("Weapons", "Greatsword", greatsword),
    ("Weapons", "Longbow", longbow),
    ("Weapons", "StormStaff", storm_staff),
    ("Weapons", "PoisonFlask", poison_flask),
    ("Weapons", "OrbitBlade", orbit_blade),
    ("Weapons", "HolyAuraRing", holy_aura_ring),
    ("Weapons", "Arrow", arrow),
    ("Weapons", "LightningOrb", lightning_orb),
    ("Pickups", "GemGreen", crystal("crystal", "crystal_light")),   # tier 0: blue XP crystal (Megabonk style)
    ("Pickups", "GemBlue", crystal("gem_green", "white")),          # tier 1: green
    ("Pickups", "GemRed", crystal("gem_purple", "white")),          # tier 2: purple
    ("Pickups", "HealthOrb", health_orb),
    ("Pickups", "Magnet", magnet),
    ("Pickups", "Chest", chest),
    ("Environment", "TombstoneA", tombstone_a),
    ("Environment", "TombstoneB", tombstone_b),
    ("Environment", "DeadTree", dead_tree),
    ("Environment", "TreeA", tree_big(1)),
    ("Environment", "TreeB", tree_big(2)),
    ("Environment", "TreePine", tree_pine),
    ("Environment", "Bush", bush),
    ("Environment", "GrassTuft", grass_tuft),
    ("Environment", "Log", log),
    ("Environment", "RockA", rock(3, (1.6, 1.3, 1.1))),
    ("Environment", "RockB", rock(5, (2.6, 2.0, 1.6))),
    ("Environment", "TowerRuin", tower_ruin),
    ("Environment", "WallRuin", wall_ruin),
    ("Environment", "PillarBroken", pillar_broken),
    ("Environment", "Fence", fence),
    ("Environment", "LanternPost", lantern_post),
    ("Environment", "MountainA", mountain(1, 80, 45)),
    ("Environment", "MountainB", mountain(2, 110, 60)),
] + EXTRA_MODELS + ROUND2_MODELS + VOLCANO_MODELS

# lists above were built while older builders were still bound: use the latest definition of every builder
def ghoul():
    """Stage 2 undead: hunched grey-green ghoul, long clawed arms, ragged loincloth, glowing yellow eyes."""
    flesh, dark = "moss", "slime_dark"
    body = [
        skin([((0, 0.06, 0.95), (0.17, 0.13)), ((0, -0.02, 1.2), (0.2, 0.15)), ((0, -0.1, 1.42), (0.23, 0.17))], flesh),   # hunched spine
        soft("ico", (0, 0.06, 1.33), (0.34, 0.22, 0.2), dark, sub=2),                                                     # back hump
        soft("cone", (0, -0.02, 0.88), (0.36, 0.3, 0.26), "leather_dark", verts=7, r2=0.4, rot=(180, 0, 0)),                # ragged loincloth
        soft("cyl", (0, 0, 0.98), (0.36, 0.28, 0.06), "rope", verts=8),
    ]
    for i in range(4):                                                                                                     # ribs showing
        body.append(soft("cube", (0, -0.17 + 0.01 * i, 1.12 + 0.07 * i), (0.26 - 0.02 * i, 0.03, 0.025), "bone"))
    Body = group("Body", body, (0, 0, HIP_Z))
    head = [soft("ico", (0, -0.2, 1.52), (0.27, 0.3, 0.25), flesh, sub=2),
            soft("ico", (0, -0.31, 1.45), (0.2, 0.14, 0.12), dark, sub=2),                                                 # jaw
            soft("ico", (-0.07, -0.33, 1.56), (0.06, 0.03, 0.04), "lantern_glow", sub=1),
            soft("ico", (0.07, -0.33, 1.56), (0.06, 0.03, 0.04), "lantern_glow", sub=1)]
    for x in (-0.05, -0.015, 0.02, 0.055):
        head.append(soft("cone", (x, -0.38, 1.44), (0.025, 0.02, 0.05), "bone", verts=4, rot=(180, 0, 0)))                 # fangs
    for x in (-1, 1):
        head.append(soft("cone", (0.13 * x, -0.15, 1.6), (0.05, 0.03, 0.14), flesh, verts=4, rot=(0, 60 * x, 0)))          # pointed ears
    JOINTS.append(group("Head", head, (0, -0.1, 1.42)))

    def arm(side):
        x = 0.24 * side
        upper = group("ArmR" if side < 0 else "ArmL", [skin([((x, -0.08, 1.4), (0.07, 0.07)), ((x * 1.15, -0.12, 1.15), (0.055, 0.055))], flesh)],
                      (x, -0.08, 1.42))
        fore = [skin([((x * 1.15, -0.12, 1.15), (0.05, 0.05)), ((x * 1.2, -0.22, 0.88), (0.045, 0.045))], flesh),
                soft("ico", (x * 1.2, -0.24, 0.84), (0.1, 0.08, 0.08), dark, sub=1)]
        for k in range(3):                                                                                                 # long claws
            fore.append(soft("cone", (x * 1.2 + 0.03 * (k - 1), -0.3, 0.76), (0.025, 0.025, 0.13), "bone", verts=4, rot=(200, 0, 0)))
        JOINTS.append(group("ForeArmR" if side < 0 else "ForeArmL", fore, (x * 1.15, -0.12, 1.15)))
        return upper

    def leg(side):
        x = 0.1 * side
        thigh = group("LegR" if side < 0 else "LegL", [skin([((x, 0.04, 0.92), (0.075, 0.075)), ((x * 1.2, -0.06, 0.55), (0.06, 0.06))], flesh)],
                      (x, 0.04, HIP_Z))
        shin = group("ShinR" if side < 0 else "ShinL", [
            skin([((x * 1.2, -0.06, 0.55), (0.055, 0.055)), ((x * 1.2, 0.05, 0.12), (0.045, 0.045))], flesh),
            soft("ico", (x * 1.2, -0.05, 0.05), (0.1, 0.2, 0.06), dark, sub=1)], (x * 1.2, -0.06, KNEE_Z))
        JOINTS.append(shin)
        return thigh

    root_with([Body, arm(-1), arm(1), leg(-1), leg(1)] + JOINTS)


def wraith():
    """Stage 3 spectre: floating hooded shroud with tattered tail, skeletal hands, two burning eyes (a flyer)."""
    body = [
        soft("cone", (0, 0, 0.55), (0.62, 0.55, 1.0), "mage_dark", verts=10, r2=0.42),                                    # shroud
        soft("cone", (0, 0, 1.06), (0.66, 0.58, 0.12), "purple_glow", verts=10, r2=0.5),                                   # glowing trim
        soft("ico", (0, 0.02, 1.25), (0.44, 0.42, 0.42), "mage_dark", sub=2),                                              # hood
        soft("ico", (0, -0.14, 1.22), (0.3, 0.2, 0.3), "black", sub=2),                                                    # dark face hole
        soft("ico", (-0.07, -0.24, 1.25), (0.07, 0.03, 0.05), "fire_core", sub=1),
        soft("ico", (0.07, -0.24, 1.25), (0.07, 0.03, 0.05), "fire_core", sub=1),
        soft("cone", (0, 0.12, 1.5), (0.14, 0.14, 0.22), "mage_dark", verts=6, rot=(-40, 0, 0)),                           # hood tip
    ]
    for i in range(6):                                                                                                     # tattered hem strands
        a = math.radians(i * 60 + 15)
        body.append(soft("cone", (math.cos(a) * 0.24, math.sin(a) * 0.22, 0.06), (0.1, 0.06, 0.32), "mage_dark", verts=4, rot=(180, 0, 0)))
    Body = group("Body", body, (0, 0, 0.6))
    arms = []
    for side in (-1, 1):
        x = 0.3 * side
        a = [soft("cone", (x, -0.05, 1.02), (0.16, 0.16, 0.36), "mage_dark", verts=8, r2=0.3, rot=(150, 0, 20 * side)),
             soft("ico", (x * 1.2, -0.18, 0.86), (0.08, 0.06, 0.08), "bone", sub=1)]
        for k in range(3):
            a.append(bone((x * 1.2 + 0.025 * (k - 1), -0.2, 0.84), (x * 1.25 + 0.03 * (k - 1), -0.3, 0.74), 0.008))
        arms.append(group("ArmR" if side < 0 else "ArmL", a, (x, -0.05, 1.15)))
    root_with([Body] + arms)


def obsidian_brute():
    """Stage 3 heavy: hulking obsidian brute, magma veins, shoulder spikes, huge glowing fists."""
    body = [
        rock_chunk((0, 0, 1.3), (0.9, 0.62, 0.66), "obsidian", 71),
        rock_chunk((0, 0.02, 0.98), (0.6, 0.44, 0.36), "basalt_dark", 72),
        rock_chunk((0, 0, 0.86), (0.52, 0.4, 0.24), "obsidian", 73),
        part("cube", (0, -0.31, 1.3), (0.08, 0.02, 0.4), "magma"),                                                           # magma veins
        part("cube", (0.15, -0.3, 1.18), (0.22, 0.02, 0.05), "magma", rot=(0, 30, 0)),
        part("cube", (-0.14, -0.3, 1.4), (0.2, 0.02, 0.05), "magma", rot=(0, -25, 0)),
    ]
    for x in (-1, 1):
        for k in range(3):
            body.append(soft("cone", (0.36 * x + 0.06 * k * x, 0.05 * k, 1.62 + 0.03 * k), (0.08, 0.08, 0.26 - 0.04 * k), "obsidian", verts=4,
                             rot=(0, 25 * x, 0)))
    Body = group("Body", body, (0, 0, HIP_Z))
    head = [rock_chunk((0, -0.08, 1.7), (0.3, 0.28, 0.24), "obsidian", 74),
            part("cube", (0, -0.22, 1.72), (0.22, 0.03, 0.04), "magma_core"),
            soft("cone", (-0.1, -0.05, 1.86), (0.06, 0.06, 0.16), "basalt", verts=4, rot=(0, -20, 0)),
            soft("cone", (0.1, -0.05, 1.86), (0.06, 0.06, 0.16), "basalt", verts=4, rot=(0, 20, 0))]
    JOINTS.append(group("Head", head, (0, 0, NECK_Z - 0.05)))

    def arm(side):
        x = 0.5 * side
        upper = group("ArmR" if side < 0 else "ArmL", [rock_chunk((x, 0, 1.36), (0.32, 0.3, 0.4), "basalt_dark", 80 + side)], (x, 0, SHOULDER_Z))
        fore = [rock_chunk((x * 1.04, -0.02, 1.04), (0.3, 0.3, 0.36), "obsidian", 82 + side),
                rock_chunk((x * 1.06, -0.04, 0.76), (0.4, 0.38, 0.34), "basalt_dark", 84 + side),
                part("cube", (x * 1.06, -0.24, 0.76), (0.2, 0.02, 0.05), "magma")]
        JOINTS.append(group("ForeArmR" if side < 0 else "ForeArmL", fore, (x, 0, ELBOW_Z)))
        return upper

    def leg(side):
        x = 0.18 * side
        thigh = group("LegR" if side < 0 else "LegL", [rock_chunk((x, 0, 0.7), (0.3, 0.32, 0.42), "basalt_dark", 90 + side)], (x, 0, HIP_Z))
        shin = group("ShinR" if side < 0 else "ShinL", [rock_chunk((x, 0, 0.3), (0.28, 0.3, 0.42), "obsidian", 92 + side),
                                                         rock_chunk((x, -0.06, 0.07), (0.34, 0.42, 0.16), "basalt_dark", 94 + side)], (x, 0, KNEE_Z))
        JOINTS.append(shin)
        return thigh

    root_with([Body, arm(-1), arm(1), leg(-1), leg(1)] + JOINTS)


MODELS += [("Enemies", "Ghoul", ghoul), ("Enemies", "Wraith", wraith), ("Enemies", "ObsidianBrute", obsidian_brute)]
MODELS = [(c, n, globals().get(f.__name__, f) if f.__name__ != "fn" else f) for c, n, f in MODELS]

if __name__ == "__main__":
    import sys
    only = None
    if "--" in sys.argv:
        only = set(sys.argv[sys.argv.index("--") + 1:])
    for cat, name, fn in MODELS:
        if only and name not in only:
            continue
        build(cat, name, fn)
    print("DONE", len(MODELS))
