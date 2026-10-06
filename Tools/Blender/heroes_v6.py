"""
MultiBash heroes v6: faceted, sculpted low-poly armor with geometry-driven pixel shading.

  blender -b --factory-startup -P Tools/Blender/heroes_v6.py -- Knight [--preview] [--cam=x,y,z,tx,ty,tz[,lens]] [--out=path]

What changed from v5 (round lofted tubes):
  * Parts are lofted through SHAPED cross-sections with real corners (keel ridge on breastplate, helm and greaves,
    flat side planes, narrow back), so plates read as sculpted armor, not cylinders. Creases stay sharp
    (smooth-by-angle), curved areas stay smooth.
  * Shading comes from the GEOMETRY: world normals and AO are baked into the planned 128 px atlas, then painted as
    pixel art: a tone band per plane, dark/light crease lines where planes meet, specular hot spots on the curves.
    Designed details (straps, emblems, slots, rivets, trims) are drawn on top at known (u, v) coordinates.
"""
import bpy
import bmesh
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import generate_models as gm  # noqa: E402
import characters as ch  # noqa: E402

TEX = 128
OUT_TEX = ch.OUT_TEX


def hexc(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)], dtype=np.float32)


RAMP_LIST = [
    ("steel",   ("#161a24", "#323a4c", "#5d6a80", "#97a4b6", "#d3dbe6", "#ffffff")),
    ("mail",    ("#12151c", "#262c38", "#444c5c", "#6a7486", "#949fb0", "#c0c9d6")),
    ("gold",    ("#3e2208", "#7a4812", "#b97c1c", "#e6b23a", "#ffdc78", "#fff4c4")),
    ("cloth",   ("#4e4a5c", "#857f94", "#bcb7c6", "#e2dfe8", "#f8f6fb", "#ffffff")),
    ("red",     ("#360a12", "#681420", "#a2222c", "#d23c38", "#ee6e58", "#ffac88")),
    ("leather", ("#22120a", "#3e2112", "#62381c", "#8c5a2c", "#b88446", "#deae78")),
    ("black",   ("#05050a", "#0b0b12", "#14141c", "#1e1e28", "#2a2a36", "#383846")),
    ("skin",    ("#3b1a14", "#78392a", "#b46a4c", "#dc9a74", "#f4c49e", "#ffe8d0")),
    ("hairk",   ("#030304", "#09090c", "#121117", "#1c1a23", "#2c2934", "#45404e")),
    ("hairb",   ("#1c0e06", "#3a200e", "#5c381a", "#835428", "#a87640", "#d0a266")),
    ("blonde",  ("#3c2008", "#6e4612", "#a8761e", "#d4a238", "#ecc458", "#f8e08c")),
    ("green",   ("#0a1e0e", "#163a18", "#256024", "#3f8c34", "#6cba4a", "#acea80")),
    ("wine",    ("#16030a", "#360812", "#5a1020", "#841c2a", "#ac3032", "#d0584a")),
    ("orange",  ("#3a1204", "#762a08", "#bc5612", "#ea8a26", "#ffb852", "#ffe29c")),
    ("glass",   ("#0e2c3c", "#1c566c", "#3888a2", "#6cc2d6", "#b2ecf2", "#ffffff")),
    ("poison",  ("#0a2804", "#1c560a", "#389812", "#66d222", "#a6f45a", "#eaffb4")),
    ("gem",     ("#081a40", "#123a80", "#2266c8", "#44a0f0", "#8cd4ff", "#e6f8ff")),
    ("tan",     ("#24160e", "#46301e", "#6c4c34", "#94704e", "#bc9a74", "#e0c6a2")),
    ("pants",   ("#0e0e14", "#1e1d28", "#33313f", "#4b4858", "#686476", "#8c889a")),
]
RAMPS = {k: np.array([hexc(c) for c in v], dtype=np.float32) for k, v in RAMP_LIST}
RAMP_ID = {k: i for i, (k, _) in enumerate(RAMP_LIST)}
RAMP_NAME = [k for k, _ in RAMP_LIST]


# ----------------------------------------------------------------------------- atlas (material per texel + painted overrides)

class Atlas:
    def __init__(self, size=TEX):
        self.size = size
        self.ramp = np.full((size, size), -1, dtype=np.int32)    # material ramp per texel (-1 = unused)
        self.bias = np.zeros((size, size), dtype=np.float32)     # tone offset of that material area
        self.tone = np.full((size, size), -1, dtype=np.int32)    # painted tone override (-1 = from lighting)
        self.oramp = np.full((size, size), -1, dtype=np.int32)   # painted ramp override
        self.glow = np.zeros((size, size), dtype=bool)

    def put(self, x, y, ramp, tone):
        if 0 <= x < self.size and 0 <= y < self.size:
            self.oramp[y, x] = RAMP_ID[ramp]
            self.tone[y, x] = int(np.clip(tone, 0, 5))


class Rect:
    def __init__(self, atlas, x, y, w, h):
        self.a, self.x, self.y, self.w, self.h = atlas, x, y, w, h

    def uv(self, u, v):
        return (self.x + u * self.w) / self.a.size, 1 - (self.y + v * self.h) / self.a.size

    def fill(self, ramp, bias=0.0, v0=0.0, v1=1.0, u0=0.0, u1=1.0):
        """Material for an area; its tones come from the baked geometry (bias shifts it darker/lighter)."""
        ys = slice(self.y + int(v0 * self.h), self.y + int(math.ceil(v1 * self.h)))
        xs = slice(self.x + int(u0 * self.w), self.x + int(math.ceil(u1 * self.w)))
        self.a.ramp[ys, xs] = RAMP_ID[ramp]
        self.a.bias[ys, xs] = bias

    def hline(self, v, ramp, tone, u0=0.0, u1=1.0, thick=1):
        py = int(v * self.h)
        for t in range(thick):
            for px in range(int(u0 * self.w), int(math.ceil(u1 * self.w))):
                self.a.put(self.x + px, self.y + py + t, ramp, tone)

    def vline(self, u, ramp, tone, v0=0.0, v1=1.0, thick=1):
        px = int(u * self.w)
        for t in range(thick):
            for py in range(int(v0 * self.h), int(math.ceil(v1 * self.h))):
                self.a.put(self.x + px + t, self.y + py, ramp, tone)

    def dot(self, u, v, ramp, tone):
        self.a.put(self.x + int(u * self.w), self.y + int(v * self.h), ramp, tone)

    def box(self, u0, v0, u1, v1, ramp, tone):
        for py in range(int(v0 * self.h), int(math.ceil(v1 * self.h))):
            for px in range(int(u0 * self.w), int(math.ceil(u1 * self.w))):
                self.a.put(self.x + px, self.y + py, ramp, tone)

    def glow(self, u0, v0, u1, v1):
        for py in range(int(v0 * self.h), int(math.ceil(v1 * self.h))):
            for px in range(int(u0 * self.w), int(math.ceil(u1 * self.w))):
                if 0 <= self.y + py < self.a.size and 0 <= self.x + px < self.a.size:
                    self.a.glow[self.y + py, self.x + px] = True

    def px(self, x, y, ramp, tone):
        """Pixel-exact draw in the rect's own pixel grid."""
        self.a.put(self.x + x, self.y + y, ramp, tone)


# ----------------------------------------------------------------------------- cross-section profiles (back -> -x -> front -> +x)

def ell(rx, ry, n=8, bulge=None):
    pts = []
    for i in range(n):
        a = math.pi + 2 * math.pi * i / n
        m = bulge[i] if bulge else 1.0
        pts.append((math.sin(a) * rx * m, -math.cos(a) * ry * m))
    return pts


def keel(w, yb, yf, sharp=1.0):
    """10-point armor section: flat-ish back, angled side planes, ridge (keel) at the front."""
    k = 0.82 + 0.1 * (1 - sharp)
    return [(0, yb), (-0.55 * w, yb * 0.97), (-w, yb * 0.4), (-w * 0.97, yf * 0.3), (-0.55 * w, yf * k), (0, yf),
            (0.55 * w, yf * k), (w * 0.97, yf * 0.3), (w, yb * 0.4), (0.55 * w, yb * 0.97)]


class Builder:
    def __init__(self):
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.new("UVMap")
        self.bones = self.bm.verts.layers.int.new("bone")
        self.bone_names = []

    def _bone(self, name):
        if name is None:
            return -1
        if name not in self.bone_names:
            self.bone_names.append(name)
        return self.bone_names.index(name)

    def loft(self, rect, sections, cap_top=True, cap_bot=True, bone=None, mirror=False, tilt=None):
        """sections: list of (cx, cy, z, profile_points) top -> bottom, profiles with equal point counts."""
        bi = self._bone(bone)
        n = len(sections[0][3])
        rings = []
        for cx, cy, z, prof in sections:
            ring = []
            for pt in prof:
                x, y, zz = cx + pt[0], cy + pt[1], z + (pt[2] if len(pt) > 2 else 0.0)
                if tilt:
                    ang, pvx, pvz = math.radians(tilt[0]), tilt[1], tilt[2]
                    dx, dz = x - pvx, zz - pvz
                    x = pvx + dx * math.cos(ang) + dz * math.sin(ang)
                    zz = pvz - dx * math.sin(ang) + dz * math.cos(ang)
                if mirror:
                    x = -x
                v = self.bm.verts.new((x, y, zz))
                v[self.bones] = bi
                ring.append(v)
            rings.append(ring)
        zs = [s[2] for s in sections]
        total = sum(abs(zs[i] - zs[i + 1]) for i in range(len(zs) - 1)) or 1
        vs = [0.0]
        for i in range(len(zs) - 1):
            vs.append(vs[-1] + abs(zs[i] - zs[i + 1]) / total)
        cap_v = 0.04
        vs = [cap_v + v * (1 - 2 * cap_v) for v in vs]
        for r in range(len(rings) - 1):
            for i in range(n):
                j = (i + 1) % n
                quad = [rings[r][i], rings[r][j], rings[r + 1][j], rings[r + 1][i]]
                uvs = [(i / n, vs[r]), ((i + 1) / n, vs[r]), ((i + 1) / n, vs[r + 1]), (i / n, vs[r + 1])]
                if mirror:
                    quad.reverse(); uvs.reverse()
                f = self.bm.faces.new(quad)
                for loop, (u, vv) in zip(f.loops, uvs):
                    loop[self.uv].uv = rect.uv(u, vv)
        for ring, vcap, top in ((rings[0], 0.01, True), (rings[-1], 0.99, False)):
            if (top and not cap_top) or (not top and not cap_bot):
                continue
            c = sum((v.co for v in ring), ring[0].co * 0) / len(ring)
            cv = self.bm.verts.new(c)
            cv[self.bones] = bi
            for i in range(n):
                j = (i + 1) % n
                tri = [cv, ring[j], ring[i]] if top else [cv, ring[i], ring[j]]
                if mirror:
                    tri.reverse()
                f = self.bm.faces.new(tri)
                for loop in f.loops:
                    loop[self.uv].uv = rect.uv((i + 0.5) / n, vcap)

    def plate(self, rect, outline, y, thick=0.02, bone=None, tilt_x=0.0):
        """Flat plate in the XZ plane (outline of (x, z) points, CCW seen from the front) at depth y."""
        bi = self._bone(bone)
        xs = [p[0] for p in outline]; zs = [p[1] for p in outline]
        x0, x1, z0, z1 = min(xs), max(xs), min(zs), max(zs)
        front, back = [], []
        for (x, z) in outline:
            yy = y + (z - z1) * math.tan(math.radians(tilt_x))
            for lst, dy in ((front, 0.0), (back, thick)):
                v = self.bm.verts.new((x, yy + dy, z))
                v[self.bones] = bi
                lst.append(v)
        f = self.bm.faces.new(front)
        for loop, (x, z) in zip(f.loops, outline):
            loop[self.uv].uv = rect.uv(0.04 + 0.92 * (x - x0) / (x1 - x0), 0.04 + 0.92 * (z1 - z) / (z1 - z0))
        others = [list(reversed(back))]
        m = len(outline)
        for i in range(m):
            j = (i + 1) % m
            others.append([front[j], front[i], back[i], back[j]])
        for fv in others:
            f = self.bm.faces.new(fv)
            for loop in f.loops:
                loop[self.uv].uv = rect.uv(0.01, 0.99)      # rim/back: one dark corner texel

    def finish(self, name):
        me = bpy.data.meshes.new("Skin_" + name)
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces)
        self.bm.to_mesh(me)
        o = bpy.data.objects.new("Skin", me)
        bpy.context.scene.collection.objects.link(o)
        bpy.ops.object.select_all(action="DESELECT")
        o.select_set(True)
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.shade_smooth_by_angle(angle=math.radians(52))   # creases sharp, curves smooth
        tags = [0] * len(me.vertices)
        bm = bmesh.new(); bm.from_mesh(me)
        lay = bm.verts.layers.int.get("bone")
        for v in bm.verts:
            tags[v.index] = v[lay]
        bm.free()
        for b in ch.BONES:
            if b != "Root":
                o.vertex_groups.new(name=b)
        ch.weigh(o)
        for i, t in enumerate(tags):
            if t >= 0:
                for g in o.vertex_groups:
                    g.remove([i])
                o.vertex_groups[self.bone_names[t]].add([i], 1.0, "REPLACE")
        return o


def side(name, s):
    return name + ("L" if s > 0 else "R")


# ----------------------------------------------------------------------------- Knight

TORSO = [(1.62, 0.09, 0.075, -0.08), (1.56, 0.2, 0.115, -0.12), (1.46, 0.245, 0.14, -0.18), (1.32, 0.225, 0.135, -0.17),
         (1.18, 0.158, 0.105, -0.125), (1.08, 0.17, 0.11, -0.12), (0.98, 0.175, 0.115, -0.115)]


def knight():
    A = Atlas()
    R = {
        "torso": Rect(A, 0, 0, 60, 40), "helm": Rect(A, 60, 0, 40, 30), "fauld": Rect(A, 60, 30, 40, 12),
        "tasset": Rect(A, 100, 0, 28, 30), "pauld": Rect(A, 0, 40, 32, 22), "lame": Rect(A, 32, 40, 32, 8),
        "lame2": Rect(A, 32, 48, 32, 8), "upper": Rect(A, 64, 42, 24, 16), "fore": Rect(A, 88, 42, 24, 22),
        "hand": Rect(A, 112, 30, 16, 16), "thumb": Rect(A, 112, 46, 8, 10), "finger": Rect(A, 120, 46, 8, 10),
        "thigh": Rect(A, 0, 62, 24, 22), "greave": Rect(A, 24, 62, 24, 30), "knee": Rect(A, 48, 62, 16, 12),
        "couter": Rect(A, 48, 74, 16, 12), "foot": Rect(A, 64, 64, 32, 16), "belt": Rect(A, 96, 64, 32, 8),
        "cuff": Rect(A, 96, 72, 24, 8),
    }
    B = Builder()
    B.loft(R["torso"], [(0, 0, z, keel(w, yb, yf)) for z, w, yb, yf in TORSO])
    B.loft(R["belt"], [(0, 0, 1.11, keel(0.168, 0.112, -0.128)), (0, 0, 1.055, keel(0.178, 0.118, -0.128))],
           cap_top=False, cap_bot=False, bone="Body")
    B.loft(R["helm"], [(0, 0, 1.985, keel(0.085, 0.09, -0.095)), (0, 0, 1.955, keel(0.125, 0.13, -0.15)),
                       (0, 0, 1.84, keel(0.15, 0.15, -0.178)), (0, 0, 1.72, keel(0.145, 0.145, -0.168)),
                       (0, 0, 1.645, keel(0.115, 0.125, -0.13)), (0, 0, 1.6, keel(0.1, 0.1, -0.105))], bone="Head")
    B.loft(R["fauld"], [(0, 0, 1.07, keel(0.182, 0.13, -0.14, 0.5)), (0, 0, 0.94, keel(0.228, 0.165, -0.175, 0.5)),
                        (0, 0, 0.86, keel(0.24, 0.175, -0.182, 0.5))], cap_top=False, cap_bot=False, bone="Body")
    B.plate(R["tasset"], [(-0.11, 1.04), (0.11, 1.04), (0.125, 0.86), (0.0, 0.72), (-0.125, 0.86)], y=-0.2, thick=0.02,
            bone="Body", tilt_x=-8)
    for s in (1, -1):
        mir = s < 0
        arm, fore, leg, shin = side("Arm", s), side("ForeArm", s), side("Leg", s), side("Shin", s)
        outer = [1.0, 0.95, 0.82, 0.95, 1.0, 1.08, 1.16, 1.08]
        tilt = (24, 0.24, 1.52)
        B.loft(R["pauld"], [(0.245, 0, 1.655, ell(0.05, 0.05)), (0.252, 0, 1.63, ell(0.12, 0.108, bulge=outer)),
                            (0.262, 0, 1.585, ell(0.165, 0.142, bulge=outer)), (0.275, 0, 1.52, ell(0.18, 0.152, bulge=outer)),
                            (0.282, 0, 1.47, ell(0.176, 0.15, bulge=outer))], cap_bot=False, bone=arm, mirror=mir, tilt=tilt)
        B.loft(R["lame"], [(0.285, 0, 1.485, ell(0.186, 0.158, bulge=outer)), (0.292, 0, 1.42, ell(0.18, 0.154, bulge=outer))],
               cap_top=False, cap_bot=False, bone=arm, mirror=mir, tilt=tilt)
        B.loft(R["lame2"], [(0.294, 0, 1.43, ell(0.182, 0.156, bulge=outer)), (0.3, 0, 1.365, ell(0.172, 0.148, bulge=outer))],
               cap_top=False, cap_bot=False, bone=arm, mirror=mir, tilt=tilt)
        B.loft(R["upper"], [(0.26, 0, 1.5, ell(0.07, 0.07)), (0.29, 0, 1.33, ell(0.072, 0.07)), (0.31, 0.005, 1.14, ell(0.058, 0.058))],
               mirror=mir)
        B.loft(R["couter"], [(0.31, 0.045, 1.225, ell(0.02, 0.012)), (0.31, 0.055, 1.195, ell(0.06, 0.035)),
                             (0.31, 0.06, 1.15, ell(0.066, 0.04)), (0.31, 0.055, 1.105, ell(0.05, 0.03)),
                             (0.31, 0.045, 1.085, ell(0.018, 0.012))], bone=fore, mirror=mir)
        B.loft(R["fore"], [(0.31, 0.01, 1.2, ell(0.066, 0.066)), (0.32, -0.005, 1.08, ell(0.07, 0.07)),
                           (0.328, -0.01, 0.95, ell(0.055, 0.053))], mirror=mir)
        B.loft(R["cuff"], [(0.331, -0.011, 0.965, ell(0.07, 0.068)), (0.332, -0.012, 0.93, ell(0.082, 0.078)),
                           (0.332, -0.015, 0.865, ell(0.064, 0.062))], cap_top=False, bone=fore, mirror=mir)
        B.loft(R["hand"], [(0.332, -0.012, 0.885, ell(0.044, 0.05)), (0.333, -0.014, 0.845, ell(0.047, 0.068)),
                           (0.334, -0.02, 0.795, ell(0.045, 0.07)), (0.332, -0.022, 0.778, ell(0.04, 0.064))], bone=fore, mirror=mir)
        for fy, ln in ((-0.068, 1.0), (-0.035, 1.08), (-0.004, 1.0), (0.024, 0.85)):
            B.loft(R["finger"], [(0.335, fy, 0.79, ell(0.017, 0.015, 6)), (0.332, fy - 0.004, 0.79 - 0.04 * ln, ell(0.016, 0.0145, 6)),
                                 (0.322, fy - 0.008, 0.79 - 0.068 * ln, ell(0.013, 0.012, 6))], bone=fore, mirror=mir)
        B.loft(R["thumb"], [(0.312, -0.05, 0.855, ell(0.022, 0.022, 6)), (0.308, -0.072, 0.82, ell(0.02, 0.02, 6)),
                            (0.306, -0.08, 0.79, ell(0.015, 0.015, 6))], bone=fore, mirror=mir)
        B.loft(R["thigh"], [(0.1, 0, 0.97, keel(0.085, 0.085, -0.095)), (0.105, -0.01, 0.78, keel(0.1, 0.095, -0.115)),
                            (0.105, -0.01, 0.58, keel(0.078, 0.075, -0.09))], mirror=mir)
        B.loft(R["knee"], [(0.105, -0.08, 0.6, ell(0.02, 0.012)), (0.105, -0.085, 0.575, ell(0.062, 0.035)),
                           (0.105, -0.09, 0.53, ell(0.07, 0.042)), (0.105, -0.085, 0.49, ell(0.056, 0.032)),
                           (0.105, -0.078, 0.465, ell(0.02, 0.012))], bone=shin, mirror=mir)
        B.loft(R["greave"], [(0.105, -0.01, 0.6, keel(0.08, 0.08, -0.095)), (0.105, -0.01, 0.5, keel(0.085, 0.085, -0.108)),
                             (0.105, 0.005, 0.36, keel(0.088, 0.088, -0.112)), (0.105, 0, 0.16, keel(0.068, 0.07, -0.085)),
                             (0.105, 0, 0.11, keel(0.072, 0.075, -0.085))], mirror=mir)
        toe = [1.0, 1.0, 1.0, 1.08, 1.25, 1.45, 1.25, 1.08, 1.0, 1.0]
        B.loft(R["foot"], [(0.105, -0.01, 0.125, ell(0.066, 0.07, 10)), (0.105, -0.045, 0.085, ell(0.072, 0.115, 10, toe)),
                           (0.105, -0.055, 0.035, ell(0.07, 0.125, 10, toe)), (0.105, -0.055, 0.005, ell(0.066, 0.12, 10, toe))],
               bone=shin, mirror=mir)

    # ---------------- materials (tones come from the geometry) and drawn details
    for k in ("torso", "helm", "fauld", "pauld", "lame", "lame2", "fore", "hand", "thumb", "finger", "thigh", "greave",
              "knee", "couter", "foot", "cuff"):
        R[k].fill("steel")
    R["upper"].fill("mail")
    R["belt"].fill("leather", -0.3)
    R["tasset"].fill("steel", 0.2)
    A.ramp[R["tasset"].y + R["tasset"].h - 1, R["tasset"].x] = RAMP_ID["steel"]

    # keel ridges catch the light: bright line on the ridge, darker pixel line on the shadow side
    for key, v0, v1 in (("torso", 0.12, 0.8), ("helm", 0.08, 0.92), ("greave", 0.05, 0.82), ("thigh", 0.05, 0.95)):
        r_ = R[key]
        r_.vline(0.5, "steel", 5, v0, v1); r_.vline(0.5 + 1 / r_.w, "steel", 3, v0, v1)
    t = R["torso"]
    t.hline(0.0, "steel", 1); t.hline(0.985, "steel", 0)
    # crossed gold straps, straight in 3D: shoulder (x .15, z 1.53) -> opposite hip (x -.13, z 1.12)
    zs = [r_[0] for r_ in TORSO]; ws = [r_[1] for r_ in TORSO]
    def w_at(z):
        for k in range(len(zs) - 1):
            if zs[k] >= z >= zs[k + 1]:
                f = (zs[k] - z) / (zs[k] - zs[k + 1])
                return ws[k] + (ws[k + 1] - ws[k]) * f
        return ws[-1]
    def u_for(x, z):
        """x on the keel profile front -> u (front keel at u .5; front corners at .4/.6; side corners at .3/.7)."""
        w = w_at(z); a = abs(x) / w
        if a <= 0.55:
            du = 0.1 * a / 0.55
        else:
            du = 0.1 + 0.1 * (a - 0.55) / 0.42
        return 0.5 + (du if x > 0 else -du)
    for sgn in (1, -1):
        for py in range(t.h):
            v = (py + 0.5) / t.h
            z = zs[0] - (v - 0.04) / 0.92 * (zs[0] - zs[-1])
            if not (1.12 <= z <= 1.53):
                continue
            f = (1.53 - z) / 0.41
            x = sgn * (0.15 - 0.28 * f)
            px = int(u_for(x, z) * t.w)
            t.px(px, py, "gold", 4); t.px(px + 1, py, "gold", 2)
    vx = 0.04 + 0.92 * (zs[0] - 1.315) / (zs[0] - zs[-1])
    t.box(0.48, vx - 0.03, 0.53, vx + 0.035, "gold", 3); t.dot(0.49, vx - 0.02, "gold", 5)
    for u in (0.06, 0.94):
        for v in (0.2, 0.45):
            t.dot(u, v, "steel", 5)                                      # back rivets

    be = R["belt"]
    be.box(0.46, 0.1, 0.54, 0.9, "gold", 3); be.box(0.48, 0.3, 0.52, 0.7, "black", 1)   # buckle
    for u in (0.2, 0.8):
        be.box(u, 0.15, u + 0.04, 0.85, "leather", 4)                    # strap keepers

    h = R["helm"]
    for (u0, u1) in ((0.385, 0.475), (0.525, 0.615)):                   # eye slots either side of the keel
        h.box(u0, 0.34, u1, 0.42, "black", 0)
        h.hline(0.42, "steel", 4, u0, u1)
    for u in (0.56, 0.6):
        for v in (0.6, 0.66, 0.72):
            h.dot(u, v, "black", 0)                                      # breaths on one cheek (asymmetric)
    h.hline(0.05, "steel", 0); h.hline(0.97, "steel", 0)
    for u in (0.22, 0.78):
        h.dot(u, 0.5, "steel", 5); h.dot(u, 0.53, "steel", 1)

    ts = R["tasset"]
    ts.box(0.44, 0.22, 0.56, 0.7, "black", 1)                          # cross emblem
    ts.box(0.3, 0.34, 0.7, 0.44, "black", 1)
    ts.box(0.46, 0.24, 0.54, 0.68, "red", 3)
    ts.box(0.32, 0.36, 0.68, 0.42, "red", 3)
    ts.hline(0.05, "gold", 3)

    fd = R["fauld"]
    fd.hline(0.0, "steel", 4); fd.hline(0.5, "steel", 0); fd.hline(0.55, "steel", 4); fd.hline(0.95, "gold", 3)
    for k in ("lame", "lame2"):
        R[k].hline(0.05, "steel", 5); R[k].hline(0.92, "steel", 0)
    R["lame2"].hline(0.8, "gold", 3)
    R["pauld"].hline(0.96, "steel", 0)
    for u in (0.62, 0.75, 0.88):
        R["pauld"].dot(u, 0.55, "gold", 4)                               # rivet row on the outer face
    R["cuff"].hline(0.15, "gold", 3, thick=1); R["cuff"].hline(0.95, "steel", 0)
    R["fore"].hline(0.02, "steel", 0)
    gr = R["greave"]
    gr.hline(0.03, "steel", 0); gr.hline(0.84, "steel", 0); gr.hline(0.87, "steel", 4)
    R["thigh"].hline(0.5, "steel", 0); R["thigh"].hline(0.53, "steel", 4); R["thigh"].hline(0.97, "steel", 0)
    R["knee"].dot(0.5, 0.45, "gold", 4)
    R["foot"].hline(0.35, "steel", 0); R["foot"].hline(0.4, "steel", 4); R["foot"].hline(0.97, "black", 1)
    hd = R["hand"]
    hd.hline(0.9, "steel", 4); hd.hline(0.96, "steel", 0); hd.dot(0.75, 0.4, "gold", 4)
    R["finger"].hline(0.45, "steel", 1); R["finger"].hline(0.5, "steel", 4)
    return B, A


# ----------------------------------------------------------------------------- shared organic parts (heads, hair, hands)

def pack(A, spec):
    """Shelf-pack named rects [(name, w, h)] into the atlas (tallest first)."""
    out, x, y, row = {}, 0, 0, 0
    for name, w, h in sorted(spec, key=lambda t: -t[2]):
        if x + w > A.size:
            x, y, row = 0, y + row, 0
        out[name] = Rect(A, x, y, w, h)
        x += w
        row = max(row, h)
    assert y + row <= A.size, f"atlas overflow ({y + row} > {A.size})"
    return out


# skull: (z, rx, back depth, front depth, bulge per ring point) - 16 points, front = index 8
HEAD = [(1.985, 0.045, 0.05, 0.045, {}), (1.96, 0.1, 0.11, 0.095, {}), (1.91, 0.127, 0.135, 0.12, {}),
        (1.85, 0.134, 0.14, 0.13, {}), (1.815, 0.134, 0.138, 0.136, {}),
        (1.785, 0.131, 0.132, 0.13, {7: 0.93, 9: 0.93}),                     # eye sockets
        (1.745, 0.127, 0.122, 0.136, {6: 1.04, 10: 1.04}),                    # cheekbones
        (1.70, 0.117, 0.11, 0.132, {}), (1.66, 0.1, 0.095, 0.128, {}),
        (1.63, 0.074, 0.07, 0.116, {}), (1.61, 0.04, 0.045, 0.085, {})]
HZ0, HZ1 = HEAD[0][0], HEAD[-1][0]


def egg(rx, yb, yf, n=16, bulge=None, grow=1.0):
    pts = []
    for i in range(n):
        a = math.pi + 2 * math.pi * i / n
        c = -math.cos(a)
        m = (bulge or {}).get(i, 1.0) * grow
        pts.append((math.sin(a) * rx * m, c * (yb if c > 0 else yf) * m))
    return pts


def head_at(z):
    z = min(HZ0, max(HZ1, z))
    for k in range(len(HEAD) - 1):
        if HEAD[k][0] >= z >= HEAD[k + 1][0]:
            f = (HEAD[k][0] - z) / (HEAD[k][0] - HEAD[k + 1][0])
            return tuple(HEAD[k][j] + (HEAD[k + 1][j] - HEAD[k][j]) * f for j in (1, 2, 3))
    return HEAD[-1][1:4]


def hv(z):
    """v coordinate of height z on the head rect."""
    return 0.04 + 0.92 * (HZ0 - z) / (HZ0 - HZ1)


def shell_ring(z, n=16, grow=1.1, add=0.004, dz=lambda a, c, s: 0.0, gfn=None):
    """Ring hugging the skull (hair, bands). dz(angle, cos-back, sin-x) lowers individual points."""
    pts = []
    for i in range(n):
        a = math.pi + 2 * math.pi * i / n
        c, s_ = -math.cos(a), math.sin(a)
        d = dz(i, c, s_)
        rx, yb, yf = head_at(z + d)
        g = gfn(c, s_) if gfn else grow
        pts.append((s_ * (rx * g + add), c * ((yb if c > 0 else yf) * g + add), d))
    return pts


def head(B, R, skin="skin", ears=True):
    B.loft(R["head"], [(0, 0, z, egg(rx, yb, yf, 16, bl)) for z, rx, yb, yf, bl in HEAD], bone="Head")
    B.loft(R["neck"], [(0, 0.012, 1.69, ell(0.06, 0.062)), (0, 0.012, 1.6, ell(0.064, 0.064)), (0, 0.01, 1.52, ell(0.075, 0.07))],
           cap_top=False, cap_bot=False)
    B.loft(R["nose"], [(0, -0.126, 1.775, ell(0.008, 0.006, 6)), (0, -0.142, 1.737, ell(0.015, 0.014, 6)),
                       (0, -0.138, 1.72, ell(0.016, 0.012, 6)), (0, -0.126, 1.714, ell(0.009, 0.007, 6))], bone="Head")
    if ears:
        for s in (1, -1):
            B.loft(R["ear"], [(0.124, 0.015, 1.8, ell(0.01, 0.02, 6)), (0.132, 0.02, 1.765, ell(0.018, 0.032, 6)),
                              (0.126, 0.012, 1.725, ell(0.012, 0.018, 6))], bone="Head", mirror=s < 0)
    R["head"].fill(skin); R["neck"].fill(skin, -0.4); R["nose"].fill(skin, -0.1); R["ear"].fill(skin, -0.2)


def face(R, hair, eye="black", brows=0.0, mouth=True, smile=False, thick=False):
    """Pixel face drawn at the skull's ring points (eyes at points 7/9 -> u .4375/.5625)."""
    h = R["head"]
    W = h.w
    ev = hv(1.79)
    for cx in (7, 9):
        u = cx / 16
        x0 = int(round(u * W)) - 1
        y0 = int(ev * h.h)
        for dx in (0, 1):
            h.px(x0 + dx, y0, eye, 0); h.px(x0 + dx, y0 + 1, eye, 1)
        inner = x0 + (1 if cx == 7 else 0)
        h.px(inner, y0, "cloth", 5)                                       # catch-light
        by = int(hv(1.818 + 0.004 * brows) * h.h)
        outer_lo = 1 if brows < 0 else 0
        for dx in range(-1, 3):
            tilt = (dx if cx == 7 else 1 - dx) * brows * 0.4
            h.px(x0 + dx, by + int(round(tilt)), hair, 1)
            if thick:
                h.px(x0 + dx, by + int(round(tilt)) - 1, hair, 2)
        h.px(x0 + (2 if cx == 7 else -1), y0 + 2, "skin", 2)              # under-eye shadow
    if mouth:
        my = int(hv(1.672) * h.h)
        c = int(0.5 * W)
        for dx in range(-2, 2):
            h.px(c + dx, my, "skin", 1)
        if smile:
            h.px(c - 3, my - 1, "skin", 1); h.px(c + 2, my - 1, "skin", 1)
        h.px(c - 1, my + 1, "skin", 4); h.px(c, my + 1, "skin", 4)        # lower lip light


def hand(B, R, s, glove=None):
    mir = s < 0
    fore = side("ForeArm", s)
    B.loft(R["hand"], [(0.332, -0.012, 0.885, ell(0.04, 0.046)), (0.333, -0.014, 0.845, ell(0.043, 0.064)),
                       (0.334, -0.02, 0.795, ell(0.042, 0.066)), (0.332, -0.022, 0.778, ell(0.037, 0.06))], bone=fore, mirror=mir)
    for fy, ln in ((-0.064, 1.0), (-0.033, 1.08), (-0.004, 1.0), (0.022, 0.85)):
        B.loft(R["finger"], [(0.335, fy, 0.79, ell(0.0155, 0.014, 6)), (0.332, fy - 0.004, 0.79 - 0.04 * ln, ell(0.015, 0.0135, 6)),
                             (0.322, fy - 0.008, 0.79 - 0.066 * ln, ell(0.012, 0.011, 6))], bone=fore, mirror=mir)
    B.loft(R["thumb"], [(0.312, -0.048, 0.855, ell(0.02, 0.02, 6)), (0.308, -0.07, 0.82, ell(0.018, 0.018, 6)),
                        (0.306, -0.078, 0.792, ell(0.014, 0.014, 6))], bone=fore, mirror=mir)


def lock(B, rect, root, mid, tip, w=0.03, d=0.018, bone="Head"):
    """Tapered hair lock / spike: root -> mid -> tip (each (x, y, z)), flattened front-to-back."""
    B.loft(rect, [(root[0], root[1], root[2], ell(w, d, 6)), (mid[0], mid[1], mid[2], ell(w * 0.75, d * 0.75, 6)),
                  (tip[0], tip[1], tip[2], ell(0.003, 0.003, 6))], bone=bone)


def hands_paint(R, ramp, bias=0.0):
    for k in ("hand", "finger", "thumb"):
        R[k].fill(ramp, bias)
    R["finger"].hline(0.45, ramp, 1)


# cloth torso: rounded back, side planes, pecs either side of a soft sternum dip (12 points, sides at u .25/.75)
def chest(w, yb, yf, pec=1.0):
    return [(0, yb), (-0.5 * w, 0.95 * yb), (-0.88 * w, 0.6 * yb), (-w, 0.0), (-0.9 * w, 0.55 * yf), (-0.48 * w, yf * pec),
            (0, yf * (0.92 + 0.08 * (1 - pec))), (0.48 * w, yf * pec), (0.9 * w, 0.55 * yf), (w, 0.0), (0.88 * w, 0.6 * yb), (0.5 * w, 0.95 * yb)]


CLOTH_TORSO = [(1.6, 0.085, 0.075, -0.08), (1.555, 0.19, 0.108, -0.112), (1.46, 0.218, 0.122, -0.152),
               (1.33, 0.196, 0.116, -0.148), (1.2, 0.152, 0.1, -0.118), (1.1, 0.158, 0.104, -0.112), (0.98, 0.17, 0.11, -0.112)]


def torso(B, R, key="torso", rows=CLOTH_TORSO, z_min=0.0, grow=1.0):
    B.loft(R[key], [(0, 0, z, chest(w * grow, yb * grow, yf * grow, 1.0 if z > 1.25 else 0.6)) for z, w, yb, yf in rows if z >= z_min])


def ring_at(z, grow=1.0, rows=CLOTH_TORSO):
    zs = [r_[0] for r_ in rows]
    for k in range(len(rows) - 1):
        if zs[k] >= z >= zs[k + 1]:
            f = (zs[k] - z) / (zs[k] - zs[k + 1])
            w, yb, yf = (rows[k][j] + (rows[k + 1][j] - rows[k][j]) * f for j in (1, 2, 3))
            return chest(w * grow, yb * grow, yf * grow, 0.6)
    w, yb, yf = rows[-1][1:4]
    return chest(w * grow, yb * grow, yf * grow, 0.6)


def arm_upper(B, rect, s, r0=0.072, r1=0.06, grow=1.0, z1=1.14):
    B.loft(rect, [(0.235, 0, 1.53, ell(0.07 * grow, 0.072 * grow, 10)), (0.27, 0, 1.43, ell(r0 * 1.05 * grow, r0 * grow, 10)),
                  (0.29, 0, 1.33, ell(r0 * grow, r0 * 0.96 * grow, 10)), (0.31, 0.005, z1, ell(r1 * grow, r1 * grow, 10))],
           mirror=s < 0)


def arm_fore(B, rect, s, r0=0.062, r1=0.046, z0=1.2, z1=0.88, bone=None, cap=True):
    B.loft(rect, [(0.31, 0.008, z0, ell(r0, r0 * 0.98, 10)), (0.318, -0.002, 1.08, ell(r0 * 1.04, r0, 10)),
                  (0.33, -0.012, z1, ell(r1, r1 * 0.96, 10))], bone=bone, mirror=s < 0, cap_top=cap, cap_bot=cap)


def leg(B, R, s, thigh="thigh", shin="shin", r=1.0):
    mir = s < 0
    mus = [1.0, 0.98, 0.96, 1.02, 1.08, 1.1, 1.08, 1.02, 0.96, 0.98]
    B.loft(R[thigh], [(0.1, 0, 0.97, ell(0.088 * r, 0.09 * r, 10)), (0.105, -0.01, 0.8, ell(0.094 * r, 0.096 * r, 10, mus)),
                      (0.105, -0.01, 0.56, ell(0.072 * r, 0.074 * r, 10))], mirror=mir)
    calf = [1.04, 1.02, 0.98, 0.96, 0.98, 1.0, 0.98, 0.96, 0.98, 1.02]
    B.loft(R[shin], [(0.105, -0.008, 0.58, ell(0.071 * r, 0.072 * r, 10)), (0.105, 0.006, 0.42, ell(0.074 * r, 0.078 * r, 10, calf)),
                     (0.105, 0.0, 0.16, ell(0.052 * r, 0.054 * r, 10))], mirror=mir)


def boot(B, R, s, key="boot", top=0.44, cuff=None, toe_len=1.0):
    mir = s < 0
    B.loft(R[key], [(0.105, 0.004, top, ell(0.078, 0.082, 10)), (0.105, 0.004, top - 0.12, ell(0.074, 0.078, 10)),
                    (0.105, 0, 0.16, ell(0.062, 0.066, 10)), (0.105, 0, 0.11, ell(0.066, 0.07, 10))], cap_top=False, mirror=mir)
    toe = [1.0, 1.0, 1.0, 1.06, 1.22 * toe_len, 1.42 * toe_len, 1.22 * toe_len, 1.06, 1.0, 1.0]
    B.loft(R["foot"], [(0.105, -0.012, 0.13, ell(0.068, 0.072, 10)), (0.105, -0.045, 0.085, ell(0.072, 0.112, 10, toe)),
                       (0.105, -0.055, 0.03, ell(0.07, 0.122, 10, toe)), (0.105, -0.055, 0.0, ell(0.066, 0.118, 10, toe))],
           bone=side("Shin", s), mirror=mir)
    if cuff:
        B.loft(R[cuff], [(0.105, 0.006, top + 0.03, ell(0.082, 0.086, 10)), (0.105, 0.008, top - 0.01, ell(0.098, 0.1, 10)),
                         (0.105, 0.008, top - 0.065, ell(0.09, 0.094, 10))], bone=side("Shin", s), mirror=mir)


def skirt(B, rect, z0, z1, w0, w1, yb0, yb1, yf0, yf1, n=16, jag=0.0, jag_every=2, wrap=False, rings=4):
    """Flared skirt / robe / apron. jag: hem zig-zag depth. wrap: back half hidden inside the body (apron)."""
    secs = []
    for k in range(rings):
        t = k / (rings - 1)
        e = t ** 1.3
        z = z0 + (z1 - z0) * t
        w, yb, yf = w0 + (w1 - w0) * e, yb0 + (yb1 - yb0) * e, yf0 + (yf1 - yf0) * e
        pts = []
        for i in range(n):
            a = math.pi + 2 * math.pi * i / n
            c = -math.cos(a)
            x, y = math.sin(a) * w, c * (yb if c > 0 else yf)
            if wrap and c > -0.2:
                x *= 0.8; y = min(y, 0.0) * 0.4 + (yb0 * 0.2 if c > 0 else 0)
            d = 0.0
            if k == rings - 1 and jag:
                d = jag if (i % jag_every == 0) else 0.0
            pts.append((x, y, d))
        secs.append((0, 0, z, pts))
    B.loft(rect, secs, cap_top=False, cap_bot=False)


# ----------------------------------------------------------------------------- Ranger

def ranger():
    A = Atlas()
    R = pack(A, [("head", 56, 34), ("hair", 40, 24), ("torso", 56, 34), ("skirt", 48, 18), ("upper", 24, 18),
                 ("fore", 24, 16), ("thigh", 24, 22), ("shin", 24, 20), ("boot", 24, 20), ("foot", 24, 12), ("cuff", 24, 8),
                 ("pauld", 24, 14), ("lame", 24, 6), ("cowl", 40, 12), ("belt", 32, 6), ("quiver", 20, 30), ("pony", 12, 20),
                 ("band", 32, 6), ("lock", 8, 12), ("hand", 16, 12), ("finger", 8, 8), ("thumb", 8, 8), ("neck", 16, 8),
                 ("nose", 8, 8), ("ear", 8, 8), ("arrow", 6, 16), ("fletch", 8, 8), ("bracer", 24, 10), ("strap", 16, 6)])
    B = Builder()
    head(B, R)
    # swept-back hair: hairline at the brow, above the ears, down to the nape; spiky fringe up front
    hl = lambda i, c, s_: -0.17 * ((c + 1) / 2) ** 0.9 + (-0.022 if (c < -0.6 and i % 2) else 0.0)
    B.loft(R["hair"], [(0, 0, 2.005, shell_ring(1.985, grow=0.55)), (0, 0, 1.975, shell_ring(1.975, grow=1.12)),
                       (0, 0, 1.93, shell_ring(1.93, grow=1.13)),
                       (0, 0, 1.875, shell_ring(1.875, grow=1.12, dz=lambda i, c, s_: 0.5 * hl(i, c, s_))),
                       (0, 0, 1.86, shell_ring(1.86, grow=1.07, add=0.002, dz=hl))], cap_bot=False, bone="Head")
    B.loft(R["pony"], [(0, 0.12, 1.86, ell(0.045, 0.04, 8)), (0, 0.17, 1.8, ell(0.05, 0.045, 8)),
                       (0, 0.2, 1.7, ell(0.042, 0.036, 8)), (0, 0.205, 1.6, ell(0.012, 0.012, 8))], bone="Head")
    B.loft(R["band"], [(0, 0, 1.905, shell_ring(1.905, grow=1.14, add=0.008)), (0, 0, 1.875, shell_ring(1.875, grow=1.14, add=0.008))],
           cap_top=False, cap_bot=False, bone="Head")
    for k, x in enumerate((-0.085, -0.045, -0.005, 0.035, 0.075)):            # fringe swept to the left, over the band
        lock(B, R["lock"], (x, -0.1, 1.95), (x + 0.03, -0.142, 1.9), (x + 0.065, -0.15, 1.84 - 0.012 * (k % 2)), w=0.03, d=0.016)
    for s_ in (1, -1):                                                         # side locks in front of the ears
        lock(B, R["lock"], (0.125 * s_, -0.05, 1.89), (0.142 * s_, -0.06, 1.81), (0.13 * s_, -0.07, 1.75), w=0.022, d=0.02)
    for k, (x, y) in enumerate(((-0.07, 0.12), (0.07, 0.12), (-0.11, 0.06), (0.11, 0.06))):   # spikes at the back
        lock(B, R["lock"], (x * 0.7, y * 0.8, 1.93), (x * 1.1, y * 1.25, 1.88), (x * 1.35, y * 1.5, 1.8), w=0.03, d=0.025)
    torso(B, R)
    B.loft(R["cowl"], [(0, 0.005, 1.68, ell(0.085, 0.085, 12)), (0, 0.005, 1.62, ell(0.13, 0.12, 12)),
                       (0, 0.01, 1.555, ell(0.2, 0.135, 12)), (0, 0.015, 1.51, ell(0.205, 0.142, 12))], cap_top=False, cap_bot=False)
    B.loft(R["belt"], [(0, 0, 1.13, ring_at(1.13, 1.06)), (0, 0, 1.075, ring_at(1.075, 1.07))], cap_top=False, cap_bot=False, bone="Body")
    skirt(B, R["skirt"], 1.09, 0.7, 0.185, 0.25, 0.118, 0.165, 0.122, 0.17, n=16, jag=0.07, jag_every=4)
    # quiver across the back (leans to the right shoulder), arrows sticking out
    qt = (-22, 0.0, 1.3)
    B.loft(R["quiver"], [(0.0, 0.2, 1.66, ell(0.06, 0.05, 8)), (0.0, 0.2, 1.62, ell(0.068, 0.056, 8)),
                         (0.0, 0.2, 1.1, ell(0.058, 0.048, 8)), (0.0, 0.2, 1.06, ell(0.05, 0.04, 8))], bone="Body", tilt=qt)
    for k, (ax, ay) in enumerate(((-0.025, 0.19), (0.0, 0.215), (0.025, 0.195), (0.012, 0.175))):
        B.loft(R["arrow"], [(ax, ay, 1.84 + 0.02 * (k % 2), ell(0.006, 0.006, 4)), (ax, ay, 1.6, ell(0.006, 0.006, 4))],
               bone="Body", tilt=qt)
        B.plate(R["fletch"], [(ax - 0.022, 1.82 + 0.02 * (k % 2)), (ax, 1.85 + 0.02 * (k % 2)), (ax + 0.022, 1.82 + 0.02 * (k % 2)),
                              (ax + 0.016, 1.75 + 0.02 * (k % 2)), (ax - 0.016, 1.75 + 0.02 * (k % 2))], y=ay, thick=0.004, bone="Body")
    for s in (1, -1):
        mir = s < 0
        arm_upper(B, R["upper"], s, grow=1.06)
        arm_fore(B, R["fore"], s, z0=1.2, z1=0.9, bone=None)
        B.loft(R["bracer"], [(0.316, -0.003, 1.08, ell(0.064, 0.062, 10)), (0.322, -0.008, 1.0, ell(0.06, 0.058, 10)),
                             (0.33, -0.012, 0.9, ell(0.054, 0.052, 10))], cap_top=False, cap_bot=False, bone=side("ForeArm", s), mirror=mir)
        hand(B, R, s)
        leg(B, R, s)
        boot(B, R, s, top=0.47, cuff="cuff")
    # single leather pauldron on the bow shoulder (left), two lames below
    tilt = (22, 0.24, 1.52)
    outer = [1.0, 0.95, 0.85, 0.95, 1.0, 1.06, 1.12, 1.06]
    B.loft(R["pauld"], [(0.262, 0, 1.6, keel(0.03, 0.03, -0.03)), (0.266, 0, 1.588, keel(0.085, 0.08, -0.085)),
                        (0.274, 0, 1.54, keel(0.105, 0.098, -0.104)), (0.28, 0, 1.5, keel(0.104, 0.097, -0.103))],
           cap_bot=False, bone="ArmL", tilt=tilt)
    B.loft(R["lame"], [(0.284, 0, 1.51, keel(0.108, 0.1, -0.107)), (0.29, 0, 1.455, keel(0.1, 0.094, -0.1))],
           cap_top=False, cap_bot=False, bone="ArmL", tilt=tilt)

    # ---- paint
    R["hair"].fill("blonde", -0.7); R["pony"].fill("blonde", -0.4); R["band"].fill("red", -0.5); R["lock"].fill("blonde", -0.3)
    R["torso"].fill("green"); R["skirt"].fill("green", -0.2); R["cowl"].fill("green", -0.9)
    R["upper"].fill("green", -0.2); R["fore"].fill("skin"); R["bracer"].fill("leather")
    R["belt"].fill("leather", -0.4); R["quiver"].fill("leather"); R["arrow"].fill("tan", 0.4); R["fletch"].fill("red", 0.3)
    R["thigh"].fill("tan", -0.3); R["shin"].fill("tan", -0.3); R["boot"].fill("leather", -0.6); R["foot"].fill("leather", -0.6)
    R["cuff"].fill("leather", 0.2); R["pauld"].fill("leather", 0.1); R["lame"].fill("leather", -0.2)
    hands_paint(R, "leather", -0.5)
    face(R, "blonde", brows=0.7, smile=True)
    hr = R["hair"]
    for u in (0.1, 0.22, 0.34, 0.66, 0.78, 0.9):                       # combed strands
        hr.vline(u, "blonde", 1, 0.25, 0.9)
    hr.vline(0.5, "blonde", 5, 0.1, 0.55)
    R["pony"].hline(0.12, "red", 2, thick=2)                            # hair tie
    t = R["torso"]
    for py in range(t.h):                                               # quiver strap: right shoulder -> left hip (front)
        v = (py + 0.5) / t.h
        if 0.12 < v < 0.86:
            u = 0.43 + (v - 0.12) / 0.74 * 0.2
            t.px(int(u * t.w), py, "leather", 2); t.px(int(u * t.w) + 1, py, "leather", 3); t.px(int(u * t.w) + 2, py, "leather", 1)
    for py in range(int(0.3 * t.h)):                                   # open V neck with criss-cross lacing
        half = max(0, int((0.3 * t.h - py) * 0.22))
        for dx in range(-half, half + 1):
            t.px(t.w // 2 + dx, py, "skin", 3 if dx < 0 else 2)
        t.px(t.w // 2 - half - 1, py, "green", 1); t.px(t.w // 2 + half + 1, py, "green", 1)
        if py % 2 and half > 0:
            t.px(t.w // 2 + (1 if py % 4 == 1 else -1), py, "tan", 4)
    t.hline(0.98, "green", 1)
    be = R["belt"]
    be.box(0.44, 0.0, 0.56, 1.0, "gold", 3); be.box(0.47, 0.3, 0.53, 0.7, "leather", 0)
    be.box(0.7, 0.0, 0.76, 1.0, "tan", 4)                               # pouch flap
    sk = R["skirt"]
    sk.hline(0.85, "gold", 3); sk.hline(0.9, "green", 1)
    R["cowl"].hline(0.9, "green", 1)
    for k in ("upper",):
        R[k].hline(0.92, "gold", 3); R[k].hline(0.97, "green", 0)
    br = R["bracer"]
    br.hline(0.1, "leather", 5); br.hline(0.85, "leather", 1)
    for v in (0.35, 0.6):
        br.hline(v, "tan", 4, 0.4, 0.6)                                  # laces
    R["cuff"].hline(0.1, "leather", 5); R["boot"].hline(0.6, "leather", 2); R["foot"].hline(0.97, "black", 1)
    q = R["quiver"]
    q.hline(0.12, "gold", 3); q.hline(0.85, "gold", 3); q.vline(0.5, "leather", 1, 0.2, 0.8)
    R["pauld"].hline(0.95, "leather", 0)
    for u in (0.62, 0.74, 0.86):
        R["pauld"].dot(u, 0.6, "gold", 4)
    R["lame"].hline(0.1, "leather", 5)
    R["thigh"].hline(0.98, "tan", 1)
    return B, A


# ----------------------------------------------------------------------------- Farzan (the red mage)

def mage():
    A = Atlas()
    R = pack(A, [("head", 56, 34), ("hair", 48, 26), ("curtain", 32, 26), ("beard", 32, 28), ("torso", 56, 30),
                 ("robe", 64, 34), ("sleeve", 32, 24), ("fore", 16, 8), ("sash", 40, 8), ("lock", 12, 20),
                 ("circlet", 40, 4), ("gem", 8, 8), ("hand", 16, 12), ("finger", 8, 8), ("thumb", 8, 8), ("neck", 16, 8),
                 ("nose", 8, 8), ("ear", 8, 8), ("foot", 24, 12), ("book", 16, 16), ("mous", 16, 8), ("collar", 40, 8)])
    B = Builder()
    head(B, R, ears=False)
    # long black hair: hairline at the brow, falls past the ears to the jaw at the sides and back
    def hl(i, c, s_):
        side_amt = min(1.0, max(0.0, (c + 0.55) / 0.4))
        return -0.2 * side_amt + (0.012 if (abs(s_) < 0.2 and c < 0) else 0.0)
    B.loft(R["hair"], [(0, 0, 2.008, shell_ring(1.985, grow=0.55)), (0, 0, 1.978, shell_ring(1.978, grow=1.13)),
                       (0, 0, 1.93, shell_ring(1.93, grow=1.15)),
                       (0, 0, 1.88, shell_ring(1.88, grow=1.15, dz=lambda i, c, s_: 0.4 * hl(i, c, s_))),
                       (0, 0, 1.87, shell_ring(1.87, grow=1.1, add=0.006, dz=hl))], cap_bot=False, bone="Head")
    # hair down the back (over the robe)
    jag = [0, -0.05, 0, -0.04, 0, -0.06, 0, -0.03]
    B.loft(R["curtain"], [(0, 0.06, 1.76, ell(0.13, 0.08, 8)), (0, 0.12, 1.64, ell(0.15, 0.06, 8)),
                          (0, 0.175, 1.5, ell(0.17, 0.05, 8)), (0, 0.18, 1.36, ell(0.16, 0.045, 8)),
                          (0, 0.17, 1.24, [(x, y, jag[i]) for i, (x, y) in enumerate(ell(0.13, 0.03, 8))])], cap_top=False)
    for s in (1, -1):                                                  # locks over the shoulders, framing the beard
        B.loft(R["lock"], [(0.115, -0.02, 1.76, ell(0.03, 0.035, 6)), (0.13, -0.07, 1.6, ell(0.04, 0.03, 6)),
                           (0.14, -0.13, 1.45, ell(0.035, 0.022, 6)), (0.14, -0.15, 1.36, ell(0.01, 0.008, 6))], mirror=s < 0)
    # long beard from the jaw to the chest, moustache over the mouth
    def jaw(z, grow, back=0.02):
        rx, yb, yf = head_at(z)
        return [(x, min(y, back), 0.0) for x, y in egg(rx * grow, yb, yf * grow, 12)]
    B.loft(R["beard"], [(0, 0, 1.735, jaw(1.735, 1.06, -0.04)), (0, 0, 1.69, jaw(1.69, 1.1)), (0, -0.02, 1.62, jaw(1.65, 1.12)),
                        (0, -0.1, 1.5, [(x * 0.7, y * 0.55, 0) for x, y in egg(0.1, 0.06, 0.07, 12)]),
                        (0, -0.155, 1.38, [(x, y, 0) for x, y in egg(0.06, 0.035, 0.045, 12)]),
                        (0, -0.18, 1.28, [(x, y, 0) for x, y in egg(0.015, 0.01, 0.012, 12)])], cap_top=False)
    B.loft(R["mous"], [(0, -0.142, 1.715, ell(0.03, 0.012, 8)), (0, -0.146, 1.7, ell(0.06, 0.02, 8)),
                       (0, -0.138, 1.675, ell(0.07, 0.016, 8))], bone="Head")
    B.loft(R["circlet"], [(0, 0, 1.865, shell_ring(1.865, gfn=lambda c, s_: 1.02 if c < -0.6 else 1.125, add=0.004)),
                          (0, 0, 1.845, shell_ring(1.845, gfn=lambda c, s_: 1.02 if c < -0.6 else 1.125, add=0.004))],
           cap_top=False, cap_bot=False, bone="Head")
    B.loft(R["gem"], [(0, -0.142, 1.875, ell(0.006, 0.004, 6)), (0, -0.148, 1.855, ell(0.022, 0.012, 6)),
                      (0, -0.146, 1.835, ell(0.006, 0.004, 6))], bone="Head")
    torso(B, R, grow=1.04)
    B.loft(R["collar"], [(0, 0.01, 1.66, ell(0.095, 0.09, 12)), (0, 0.01, 1.6, ell(0.12, 0.11, 12)),
                         (0, 0.01, 1.55, ell(0.17, 0.13, 12))], cap_top=False, cap_bot=False)
    B.loft(R["sash"], [(0, 0, 1.14, ring_at(1.14, 1.1)), (0, 0, 1.06, ring_at(1.06, 1.12))], cap_top=False, cap_bot=False, bone="Body")
    skirt(B, R["robe"], 1.1, 0.055, 0.175, 0.31, 0.12, 0.27, 0.125, 0.29, n=16, jag=0.05, jag_every=2, rings=5)
    B.loft(R["book"], [(0.19, -0.06, 1.06, keel(0.04, 0.05, -0.05, 0.2)), (0.205, -0.065, 0.9, keel(0.042, 0.052, -0.052, 0.2))],
           bone="Body")
    for s in (1, -1):
        mir = s < 0
        # bell sleeve: fitted at the shoulder, opening wide over the wrist
        B.loft(R["sleeve"], [(0.235, 0, 1.53, ell(0.074, 0.076, 10)), (0.275, 0, 1.4, ell(0.08, 0.078, 10)),
                             (0.305, 0.004, 1.2, ell(0.078, 0.076, 10)), (0.32, -0.006, 1.02, ell(0.1, 0.098, 10)),
                             (0.33, -0.01, 0.9, [(x, y, (-0.03 if i in (4, 5, 6) else 0.0)) for i, (x, y) in enumerate(ell(0.118, 0.112, 10))])],
               cap_bot=True, mirror=mir)
        arm_fore(B, R["fore"], s, r0=0.05, r1=0.044, z0=1.0, z1=0.88, bone=side("ForeArm", s))
        hand(B, R, s)
        B.loft(R["foot"], [(0.105, -0.03, 0.09, ell(0.06, 0.08, 10)), (0.105, -0.075, 0.05, ell(0.065, 0.11, 10)),
                           (0.105, -0.085, 0.0, ell(0.06, 0.11, 10))], bone=side("Shin", s), mirror=mir)

    # ---- paint
    R["hair"].fill("hairk", -0.6); R["curtain"].fill("hairk", -0.5); R["lock"].fill("hairk", -0.5); R["beard"].fill("hairk", -0.5)
    R["mous"].fill("hairk", -0.4); R["circlet"].fill("gold"); R["gem"].fill("gem", 0.6); R["gem"].glow(0, 0, 1, 1)
    R["torso"].fill("red", -0.7); R["robe"].fill("red", -0.8); R["sleeve"].fill("red", -0.6); R["collar"].fill("wine")
    R["sash"].fill("wine", -0.3); R["fore"].fill("skin", -0.3); R["foot"].fill("leather", -0.7); R["book"].fill("leather")
    hands_paint(R, "skin")
    face(R, "hairk", brows=1.0, mouth=False, thick=True)
    for k, n_ in (("hair", 9), ("curtain", 7), ("beard", 6), ("lock", 3)):  # strands: alternating light/dark streaks
        r_ = R[k]
        for j in range(n_):
            u = (j + 0.5) / n_
            r_.vline(u, "hairk", 3 if j % 2 else 0, 0.15, 0.95)
    R["hair"].vline(0.5, "hairk", 0, 0.05, 0.9)                          # centre parting
    R["mous"].hline(0.45, "hairk", 4, 0.2, 0.8)
    t = R["torso"]
    t.box(0.455, 0.0, 0.545, 1.0, "wine", 2)                            # front panel with gold edges
    t.vline(0.45, "gold", 3); t.vline(0.545, "gold", 4)
    for v in (0.3, 0.55, 0.8):
        t.dot(0.49, v, "gold", 4)
    t.hline(0.0, "gold", 3)
    rb = R["robe"]
    rb.box(0.455, 0.0, 0.545, 1.0, "wine", 2)
    rb.vline(0.45, "gold", 3); rb.vline(0.545, "gold", 4)
    rb.hline(0.86, "gold", 3, thick=2); rb.hline(0.93, "wine", 1, thick=2)
    for u in (0.08, 0.2, 0.32, 0.68, 0.8, 0.92):                        # long folds
        rb.vline(u, "red", 1, 0.25, 0.84)
        rb.vline(u + 0.02, "red", 4, 0.35, 0.82)
    for v in (0.2, 0.45, 0.7):                                          # small glowing runes down the panel
        rb.dot(0.49, v, "gem", 4); rb.dot(0.5, v + 0.03, "gem", 3)
        rb.glow(0.48, v, 0.52, v + 0.04)
    sl = R["sleeve"]
    sl.hline(0.84, "gold", 3, thick=2); sl.hline(0.995, "wine", 0)
    sl.vline(0.25, "red", 1, 0.3, 0.8); sl.vline(0.75, "red", 1, 0.3, 0.8)
    R["sash"].hline(0.2, "gold", 3); R["sash"].hline(0.8, "gold", 3)
    R["sash"].box(0.47, 0.0, 0.53, 1.0, "gold", 4)
    R["collar"].hline(0.05, "gold", 4); R["collar"].hline(0.5, "wine", 1)
    R["circlet"].hline(0.5, "gold", 5, 0.4, 0.6)
    bk = R["book"]
    bk.hline(0.1, "gold", 3); bk.hline(0.9, "gold", 3); bk.box(0.45, 0.4, 0.55, 0.6, "gem", 4); bk.glow(0.45, 0.4, 0.55, 0.6)
    return B, A


# ----------------------------------------------------------------------------- Fredrik (the alchemist)

def alchemist():
    A = Atlas()
    R = pack(A, [("head", 56, 34), ("hair", 44, 22), ("torso", 56, 32), ("apron", 48, 26), ("upper", 24, 18),
                 ("roll", 24, 6), ("fore", 16, 10), ("glove", 24, 14), ("thigh", 24, 22), ("shin", 24, 18), ("boot", 24, 16),
                 ("foot", 24, 12), ("cuff", 24, 8), ("belt", 40, 6), ("pack", 32, 22), ("flask", 12, 14), ("liquid", 8, 8),
                 ("cork", 8, 6), ("lens", 10, 10), ("bridge", 8, 4), ("hand", 16, 12), ("finger", 8, 8), ("thumb", 8, 8),
                 ("neck", 16, 8), ("nose", 8, 8), ("ear", 8, 8), ("collar", 32, 8), ("vial", 8, 10), ("tuft", 8, 8),
                 ("scarf", 32, 8)])
    B = Builder()
    head(B, R)
    hl = lambda i, c, s_: -0.13 * ((c + 1) / 2) ** 1.2 + (-0.028 if (c < -0.3 and i % 2 == 0) else 0.0)
    B.loft(R["hair"], [(0, 0, 2.0, shell_ring(1.985, grow=0.6)), (0, 0, 1.972, shell_ring(1.972, grow=1.13)),
                       (0, 0, 1.925, shell_ring(1.925, grow=1.12)),
                       (0, 0, 1.89, shell_ring(1.89, grow=1.1, dz=lambda i, c, s_: 0.5 * hl(i, c, s_))),
                       (0, 0, 1.875, shell_ring(1.875, grow=1.06, add=0.002, dz=hl))], cap_bot=False, bone="Head")
    for k, x in enumerate((-0.08, -0.04, 0.0, 0.04, 0.08)):                   # messy fringe
        lock(B, R["tuft"], (x, -0.09, 1.96), (x - 0.01 + 0.02 * (k % 2), -0.14, 1.92), (x + 0.02 * (k % 2), -0.15, 1.865 - 0.015 * (k % 2)),
             w=0.03, d=0.018)
    for x, y, tx in ((0.02, 0.0, 0.05), (-0.03, 0.04, -0.06), (0.06, 0.06, 0.1)):  # cowlicks on top
        lock(B, R["tuft"], (x, y, 1.98), (x + tx * 0.4, y + 0.01, 2.02), (x + tx, y + 0.03, 2.035), w=0.025, d=0.025)
    # round spectacles: two lenses + bridge (temples are painted on the head sides)
    for s in (1, -1):
        pts = [(0.052 * s + math.cos(a) * 0.037, 1.788 + math.sin(a) * 0.036) for a in (2 * math.pi * k / 10 for k in range(10))]
        if s < 0:
            pts.reverse()
        B.plate(R["lens"], pts, y=-0.158, thick=0.006, bone="Head")
    B.plate(R["bridge"], [(-0.017, 1.8), (0.017, 1.8), (0.017, 1.792), (-0.017, 1.792)], y=-0.168, thick=0.006, bone="Head")
    torso(B, R)
    B.loft(R["collar"], [(0, 0.01, 1.655, ell(0.08, 0.078, 12)), (0, 0.01, 1.6, ell(0.095, 0.09, 12)),
                         (0, 0.01, 1.565, ell(0.13, 0.11, 12))], cap_top=False, cap_bot=False)
    B.loft(R["scarf"], [(0, 0.01, 1.63, ell(0.088, 0.086, 12)), (0, 0.012, 1.585, ell(0.115, 0.105, 12)),
                        (0, 0.015, 1.55, ell(0.15, 0.118, 12))], cap_top=False, cap_bot=False)
    B.loft(R["belt"], [(0, 0, 1.12, ring_at(1.12, 1.07)), (0, 0, 1.065, ring_at(1.065, 1.08))], cap_top=False, cap_bot=False, bone="Body")
    skirt(B, R["apron"], 1.4, 0.56, 0.165, 0.2, 0.08, 0.1, 0.165, 0.17, n=16, wrap=True, rings=5)
    # backpack with two bubbling flasks
    B.loft(R["pack"], [(0, 0.2, 1.52, keel(0.14, -0.06, 0.07, 0.3)), (0, 0.21, 1.46, keel(0.16, -0.07, 0.085, 0.3)),
                       (0, 0.21, 1.2, keel(0.16, -0.07, 0.085, 0.3)), (0, 0.2, 1.16, keel(0.14, -0.06, 0.07, 0.3))], bone="Body")
    for fx_, ramp in ((-0.08, "poison"), (0.075, "orange")):
        B.loft(R["flask"], [(fx_, 0.21, 1.66, ell(0.016, 0.016, 8)), (fx_, 0.21, 1.62, ell(0.018, 0.018, 8)),
                            (fx_, 0.21, 1.585, ell(0.05, 0.05, 8)), (fx_, 0.21, 1.53, ell(0.052, 0.052, 8)),
                            (fx_, 0.21, 1.5, ell(0.04, 0.04, 8))], bone="Body")
        B.loft(R["cork"], [(fx_, 0.21, 1.685, ell(0.02, 0.02, 6)), (fx_, 0.21, 1.655, ell(0.018, 0.018, 6))], bone="Body")
    # vials on the belt
    for vx, vy in ((0.12, -0.115), (-0.1, -0.12), (-0.155, -0.06)):
        B.loft(R["vial"], [(vx, vy, 1.12, ell(0.012, 0.012, 6)), (vx, vy, 1.08, ell(0.02, 0.02, 6)), (vx, vy, 1.0, ell(0.022, 0.022, 6))],
               bone="Body")
    for s in (1, -1):
        mir = s < 0
        arm_upper(B, R["upper"], s, r0=0.078, r1=0.066, grow=1.04, z1=1.16)
        B.loft(R["roll"], [(0.31, 0.004, 1.19, ell(0.072, 0.072, 10)), (0.312, 0.003, 1.16, ell(0.078, 0.078, 10)),
                           (0.314, 0.002, 1.13, ell(0.07, 0.07, 10))], cap_top=False, cap_bot=False, bone=side("ForeArm", s), mirror=mir)
        arm_fore(B, R["fore"], s, z0=1.16, z1=1.0, bone=None, cap=False)
        B.loft(R["glove"], [(0.322, -0.006, 1.06, ell(0.074, 0.072, 10)), (0.326, -0.008, 1.0, ell(0.066, 0.064, 10)),
                            (0.33, -0.012, 0.9, ell(0.05, 0.048, 10))], cap_top=True, bone=side("ForeArm", s), mirror=mir)
        hand(B, R, s)
        leg(B, R, s, r=1.04)
        boot(B, R, s, top=0.36, cuff="cuff", toe_len=1.05)

    # ---- paint
    R["hair"].fill("hairb", -0.3); R["tuft"].fill("hairb", -0.1)
    R["torso"].fill("orange", -0.4); R["collar"].fill("cloth", -0.4); R["scarf"].fill("green", -0.6)
    R["upper"].fill("cloth", -0.4); R["roll"].fill("cloth", -0.1); R["fore"].fill("skin")
    R["glove"].fill("leather", -0.5); R["belt"].fill("leather", -0.8); R["apron"].fill("leather", -0.1)
    R["thigh"].fill("pants"); R["shin"].fill("pants"); R["boot"].fill("leather", -0.7); R["foot"].fill("leather", -0.7)
    R["cuff"].fill("leather", -0.2); R["pack"].fill("leather", -0.3); R["flask"].fill("glass", 0.6); R["cork"].fill("tan", 0.3)
    R["lens"].fill("glass", 0.8); R["bridge"].fill("gold", 0.5); R["vial"].fill("glass", 0.6)
    hands_paint(R, "leather", -0.5)
    face(R, "hairb", brows=0.8, smile=True)
    h = R["head"]
    ev = hv(1.792)
    for u0, u1 in ((0.66, 0.79), (0.21, 0.34)):                        # spectacle temples over the ears
        h.hline(ev, "gold", 2, u0, u1)
    hr = R["hair"]
    for u in (0.08, 0.2, 0.3, 0.7, 0.8, 0.92):
        hr.vline(u, "hairb", 1, 0.3, 0.92)
    hr.vline(0.56, "hairb", 4, 0.15, 0.7)
    ln = R["lens"]
    for px_ in range(ln.w):                                             # gold rim, glass, glint, pupil showing through
        for py in range(ln.h):
            dx, dy = (px_ + 0.5) / ln.w - 0.5, (py + 0.5) / ln.h - 0.5
            r = math.hypot(dx, dy)
            if r > 0.36:
                ln.px(px_, py, "gold", 3 if dy < 0 else 2)
            elif r > 0.3:
                ln.px(px_, py, "gold", 1)
    ln.box(0.3, 0.25, 0.42, 0.37, "glass", 5)
    ln.box(0.48, 0.45, 0.6, 0.62, "black", 0)
    t = R["torso"]
    t.box(0.475, 0.0, 0.525, 1.0, "cloth", 2)                          # shirt showing between the vest panels
    t.vline(0.465, "orange", 0); t.vline(0.53, "orange", 1)
    for v in (0.25, 0.4, 0.55, 0.7):
        t.dot(0.445, v, "gold", 4)                                      # buttons
    for u in (0.37, 0.61):                                              # backpack straps over the shoulders
        t.vline(u, "leather", 2, 0.0, 0.3); t.vline(u + 0.018, "leather", 3, 0.0, 0.3)
    for u in (0.1, 0.88):
        t.vline(u, "leather", 2, 0.0, 0.6)
    t.hline(0.97, "orange", 1)
    ap = R["apron"]
    ap.hline(0.03, "leather", 1)
    ap.box(0.36, 0.5, 0.48, 0.66, "leather", 2); ap.hline(0.5, "leather", 4, 0.36, 0.48)          # pockets
    ap.box(0.52, 0.5, 0.64, 0.66, "leather", 2); ap.hline(0.5, "leather", 4, 0.52, 0.64)
    for u, v in ((0.42, 0.75), (0.58, 0.3), (0.45, 0.88)):                                         # stains
        ap.dot(u, v, "poison", 2); ap.dot(u + 0.02, v, "poison", 3)
    ap.hline(0.97, "leather", 0)
    be = R["belt"]
    be.box(0.46, 0.0, 0.54, 1.0, "gold", 3); be.box(0.48, 0.3, 0.52, 0.7, "leather", 0)
    R["roll"].hline(0.5, "cloth", 5); R["upper"].vline(0.5, "cloth", 2, 0.2, 0.9)
    gl = R["glove"]
    gl.hline(0.08, "leather", 4); gl.hline(0.2, "leather", 1); gl.hline(0.5, "orange", 3, 0.4, 0.6)
    R["cuff"].hline(0.1, "leather", 4); R["foot"].hline(0.97, "black", 1)
    R["thigh"].hline(0.6, "pants", 4, 0.1, 0.2)                            # patch
    pk = R["pack"]
    pk.hline(0.1, "leather", 1); pk.vline(0.25, "leather", 1, 0.2, 0.9); pk.vline(0.75, "leather", 1, 0.2, 0.9)
    pk.box(0.2, 0.3, 0.3, 0.4, "gold", 4); pk.box(0.7, 0.3, 0.8, 0.4, "gold", 4)
    fl = R["flask"]
    fl.box(0.0, 0.5, 1.0, 1.0, "poison", 4); fl.glow(0.0, 0.5, 1.0, 1.0)
    fl.dot(0.3, 0.6, "poison", 5); fl.dot(0.6, 0.75, "poison", 5)
    fl.hline(0.3, "glass", 5, 0.2, 0.4)
    vi = R["vial"]
    vi.box(0.0, 0.4, 1.0, 1.0, "orange", 4); vi.glow(0.0, 0.4, 1.0, 1.0)
    R["scarf"].hline(0.5, "green", 4, 0.0, 1.0)
    return B, A


HEROES = {"Knight": knight, "Ranger": ranger, "Mage": mage, "Alchemist": alchemist}

# ----------------------------------------------------------------------------- geometry bake + pixel compose

L = np.array([-0.12, -0.28, 0.95]); L /= np.linalg.norm(L)
V = np.array([0.0, -0.8, 0.6]); V /= np.linalg.norm(V)
H = (L + V) / np.linalg.norm(L + V)
BAYER2 = np.array([[0, 2], [3, 1]], dtype=np.float32) / 4.0


def bake_maps(obj, size):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 64
    sc.render.bake.margin = 1
    imgs = {k: bpy.data.images.new(f"{k}_bake", size, size, alpha=True, float_buffer=True) for k in ("N", "AO")}
    for im in imgs.values():
        im.colorspace_settings.name = "Non-Color"
    mat = bpy.data.materials.new("BAKE")
    mat.use_nodes = True
    nt = mat.node_tree
    for n_ in list(nt.nodes):
        nt.nodes.remove(n_)
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    vm = nt.nodes.new("ShaderNodeVectorMath"); vm.operation = "MULTIPLY_ADD"
    vm.inputs[1].default_value = (0.5, 0.5, 0.5); vm.inputs[2].default_value = (0.5, 0.5, 0.5)
    nt.links.new(geo.outputs["Normal"], vm.inputs[0])
    ao = nt.nodes.new("ShaderNodeAmbientOcclusion"); ao.samples = 64; ao.inputs["Distance"].default_value = 0.08
    em = nt.nodes.new("ShaderNodeEmission")
    out = nt.nodes.new("ShaderNodeOutputMaterial"); nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    tgt = nt.nodes.new("ShaderNodeTexImage")
    obj.data.materials.clear(); obj.data.materials.append(mat)
    bpy.ops.object.select_all(action="DESELECT"); obj.select_set(True); bpy.context.view_layer.objects.active = obj
    res = {}
    for key, sock in (("N", vm.outputs["Vector"]), ("AO", ao.outputs["Color"])):
        for l in list(nt.links):
            if l.to_node == em:
                nt.links.remove(l)
        nt.links.new(sock, em.inputs["Color"])
        tgt.image = imgs[key]; nt.nodes.active = tgt
        bpy.ops.object.bake(type="EMIT")
        res[key] = np.array(imgs[key].pixels[:], dtype=np.float32).reshape(size, size, 4)[::-1]   # rows top-down
    return res


def compose(A, maps):
    S = A.size
    nrm = maps["N"][..., :3] * 2 - 1
    covered = maps["N"][..., 3] > 0.5
    nlen = np.linalg.norm(nrm, axis=-1, keepdims=True)
    nrm = np.where(nlen > 1e-3, nrm / np.maximum(nlen, 1e-3), np.array([0, -1, 0]))
    ao = maps["AO"][..., 0]
    acc = np.zeros_like(ao); cnt = np.zeros_like(ao)                    # denoise AO inside covered texels
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            acc += np.roll(np.roll(ao * covered, dy, 0), dx, 1)
            cnt += np.roll(np.roll(covered.astype(np.float32), dy, 0), dx, 1)
    ao = np.where(cnt > 0, acc / np.maximum(cnt, 1), ao)
    ndl = (nrm * L).sum(-1)
    spec = np.clip((nrm * H).sum(-1), 0, 1) ** 24
    lit = 0.5 + 0.5 * ndl
    t = 0.25 + 4.4 * lit * (0.55 + 0.45 * ao) + A.bias
    yy, xx = np.mgrid[0:S, 0:S]
    rng = np.random.default_rng(7)
    grain = (rng.random((S, S)) < 0.025).astype(np.float32) * np.where(rng.random((S, S)) < 0.5, -0.6, 0.6)
    tone = np.floor(t + 0.5 + grain).astype(np.int32)                 # clean bands, sparse painterly grain
    metal = np.isin(A.ramp, [RAMP_ID[k] for k in ("steel", "gold", "glass", "gem", "mail")])
    tone = np.where((spec > 0.55) & metal, np.maximum(tone, 5), tone)
    tone = np.where((spec > 0.8) & ~metal, np.maximum(tone, 4), tone)          # soft sheen on cloth/hair/skin
    tone = np.clip(tone, 0, 5)
    # crease lines: where neighbouring texels of the same material face very different ways
    edge_dark = np.zeros((S, S), dtype=bool); edge_lite = np.zeros((S, S), dtype=bool)
    for dy, dx in ((0, 1), (1, 0), (0, -1), (-1, 0)):
        nn = np.roll(np.roll(nrm, dy, 0), dx, 1)
        nr = np.roll(np.roll(A.ramp, dy, 0), dx, 1)
        nc = np.roll(np.roll(covered, dy, 0), dx, 1)
        same = (nr == A.ramp) & nc & covered
        crease = same & ((nrm * nn).sum(-1) < 0.62)
        nl = (nn * L).sum(-1)
        edge_dark |= crease & (ndl < nl)
        edge_lite |= crease & (ndl >= nl)
    tone = np.where(edge_dark, np.maximum(tone - 2, 0), tone)
    tone = np.where(edge_lite, np.minimum(tone + 1, 5), tone)
    ramp = np.where(A.oramp >= 0, A.oramp, A.ramp)
    tone = np.where(A.tone >= 0, A.tone, tone)
    rgb = np.zeros((S, S, 3), dtype=np.float32)
    for name, rid in RAMP_ID.items():
        m = ramp == rid
        rgb[m] = RAMPS[name][tone[m]]
    rgb[A.ramp < 0] = RAMPS["steel"][1]
    alpha = np.where(A.glow, 32 / 255, 0.0)
    return np.concatenate([rgb, alpha[..., None]], -1)


def write_texture(rgba, name):
    os.makedirs(OUT_TEX, exist_ok=True)
    img = bpy.data.images.new("T_Char_" + name, TEX, TEX, alpha=True)
    img.colorspace_settings.name = "Non-Color"
    img.pixels[:] = rgba[::-1].astype(np.float32).ravel()
    img.filepath_raw = os.path.join(OUT_TEX, f"T_Char_{name}.png")
    img.file_format = "PNG"
    img.save()
    print("painted", img.filepath_raw)
    return img


def build(name, preview=False, reset=True):
    if reset:
        gm.reset()
    B, A = HEROES[name]()
    mesh = B.finish(name)
    maps = bake_maps(mesh, TEX)
    img = write_texture(compose(A, maps), name)
    mesh.data.materials.clear()
    mat = bpy.data.materials.new("M_Char_" + name)
    if preview:
        mat.use_nodes = True
        tn = mat.node_tree.nodes.new("ShaderNodeTexImage")
        tn.image = img
        img.colorspace_settings.name = "sRGB"
        img.alpha_mode = "NONE"
        tn.interpolation = "Closest"
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        bsdf.inputs["Roughness"].default_value = 0.9
        mat.node_tree.links.new(tn.outputs["Color"], bsdf.inputs["Base Color"])
    mesh.data.materials.append(mat)
    rig = ch.armature()
    mesh.parent = rig
    mod = mesh.modifiers.new("Armature", "ARMATURE")
    mod.object = rig
    return mesh, rig


def preview(names):
    import render_previews as rp
    gm.reset()
    for i, n in enumerate(names):
        mesh, rig = build(n, preview=True, reset=False)
        rig.location.x += i * 1.3
    bpy.context.scene.render.engine = "BLENDER_EEVEE" if "BLENDER_EEVEE" in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items] else "BLENDER_EEVEE_NEXT"
    rp.setup_render(1200, 1200, transparent=False)
    rp.camera((0.9, -3.6, 1.6), (0, 0, 1.05), lens=50)
    for a in sys.argv:
        if a.startswith("--cam="):
            v = [float(x) for x in a[6:].split(",")]
            rp.camera(tuple(v[0:3]), tuple(v[3:6]), lens=v[6] if len(v) > 6 else 50)
    out = next((a[6:] for a in sys.argv if a.startswith("--out=")), None)
    bpy.context.scene.render.filepath = out or os.path.join(gm.ROOT, "Tools", "Blender", "hero_v6.png")
    bpy.ops.render.render(write_still=True)


def portrait(name):
    """Head-and-shoulders portrait for the UI (Assets/_Game/UI/Icons/Characters/Portrait_<name>.png, pixelated later)."""
    import render_previews as rp
    gm.reset()
    build(name, preview=True, reset=False)
    bpy.context.scene.render.engine = "BLENDER_EEVEE" if "BLENDER_EEVEE" in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items] else "BLENDER_EEVEE_NEXT"
    rp.setup_render(256, 256, transparent=True)
    rp.camera((0.3, -1.2, 1.84), (0, 0, 1.75), lens=58)
    out = os.path.join(gm.ROOT, "Assets", "_Game", "UI", "Icons", "Characters", f"Portrait_{name}.png")
    bpy.context.scene.render.filepath = out
    bpy.ops.render.render(write_still=True)
    print("portrait", out)


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    names = [a for a in args if a in HEROES] or list(HEROES)
    if "--portrait" in args:
        for n in names:
            portrait(n)
    elif "--preview" in args:
        preview(names)
    else:
        for n in names:
            build(n)
            ch.export(n)
