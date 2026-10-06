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
            for (px_, py_) in prof:
                x, y, zz = cx + px_, cy + py_, z
                if tilt:
                    ang, pvx, pvz = math.radians(tilt[0]), tilt[1], tilt[2]
                    dx, dz = x - pvx, z - pvz
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


HEROES = {"Knight": knight}

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
    tone = np.where(spec > 0.55, np.maximum(tone, 5), tone)
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


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    names = [a for a in args if a in HEROES] or list(HEROES)
    if "--preview" in args:
        preview(names)
    else:
        for n in names:
            build(n)
            ch.export(n)
