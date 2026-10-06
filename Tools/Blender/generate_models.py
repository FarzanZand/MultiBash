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


VOLCANO_MODELS = [
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
