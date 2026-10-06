"""
Renders character portraits for the UI (Assets/_Game/UI/Icons/Characters/Portrait_<Name>.png)
and, with --sheet, a preview contact sheet of every model (written to Tools/Blender/preview.png).

  blender -b -P Tools/Blender/render_previews.py
  blender -b -P Tools/Blender/render_previews.py -- --sheet
"""
import bpy
import math
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import generate_models as gm  # noqa: E402

ROOT = gm.ROOT
PALETTE_PNG = os.path.join(ROOT, "Assets", "_Game", "Art", "Textures", "T_Palette.png")


def setup_material():
    mat = gm.palette_material()
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(PALETTE_PNG, check_existing=True)
    tex.interpolation = "Closest"
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.8


def setup_render(res_x, res_y, transparent=True):
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE" if "BLENDER_EEVEE" in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items] else "BLENDER_EEVEE_NEXT"
    sc.render.resolution_x = res_x
    sc.render.resolution_y = res_y
    sc.render.film_transparent = transparent
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    world = bpy.data.worlds.new("W")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.35, 0.38, 0.45, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.8
    sc.world = world
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
    sun.data.energy = 4
    sun.rotation_euler = (math.radians(50), math.radians(10), math.radians(-30))
    sc.collection.objects.link(sun)


def camera(loc, look_at, ortho=None, lens=50):
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    bpy.context.scene.collection.objects.link(cam)
    cam.location = loc
    d = [look_at[i] - loc[i] for i in range(3)]
    import mathutils
    cam.rotation_euler = mathutils.Vector(d).to_track_quat("-Z", "Y").to_euler()
    if ortho:
        cam.data.type = "ORTHO"
        cam.data.ortho_scale = ortho
    cam.data.lens = lens
    bpy.context.scene.camera = cam
    return cam


def portraits():
    out_dir = os.path.join(ROOT, "Assets", "_Game", "UI", "Icons", "Characters")
    os.makedirs(out_dir, exist_ok=True)
    for name, fn in (("Knight", gm.knight), ("Ranger", gm.ranger), ("Mage", gm.mage), ("Alchemist", gm.alchemist)):
        gm.reset()
        fn()
        setup_material()
        setup_render(256, 256)
        camera((0.55, -1.9, 2.05), (0, 0, 1.72), lens=60)
        bpy.context.scene.render.filepath = os.path.join(out_dir, f"Portrait_{name}.png")
        bpy.ops.render.render(write_still=True)
        print("portrait", name)


def sheet():
    gm.reset()
    x = 0.0
    for cat, name, fn in gm.MODELS:
        before = set(bpy.data.objects)
        fn()
        new = [o for o in bpy.data.objects if o not in before]
        roots = [o for o in new if o.parent is None]
        for r in roots:
            r.location.x += x
        x += 3.2 if cat == "Environment" else 1.8
    setup_material()
    setup_render(2400, 500, transparent=False)
    camera((x / 2, -40, 9), (x / 2, 0, 1.0), ortho=x + 2)
    bpy.context.scene.render.filepath = os.path.join(ROOT, "Tools", "Blender", "preview.png")
    bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if "--sheet" in args:
        sheet()
    else:
        portraits()
