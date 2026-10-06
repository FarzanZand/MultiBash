"""
MultiBash heroes v5: low-poly lofted models with planned UVs and hand-designed pixel-art textures.

  blender -b --factory-startup -P Tools/Blender/heroes_pixel.py -- Knight [--preview]

How it works (the way a low-poly pixel artist builds a character):
  * Every part is LOFTED through designed cross-sections (center, radius x/y, per-side bulge) with 8 sides, so
    silhouettes are angular and intentional (flared breastplate, domed pauldrons, tapered limbs, bucket helm).
  * Each part unwraps CYLINDRICALLY into a known rectangle of a 128 px atlas: u = angle around the part
    (front = middle of the rect), v = along the part. Left/right limbs share one rect (mirrored).
  * The texture is DRAWN in numpy into those rectangles: hue-shifted 5-tone ramps, light banded around the part,
    outlines on plate edges, rivets, straps, trims, patterns and faces placed by (u, v) coordinates.
  * Rig and weights come from characters.py (same bone names the game animates).
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


# ----------------------------------------------------------------------------- palette ramps (dark -> light, sRGB 0..1)

def hexc(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)], dtype=np.float32)


RAMPS = {
    "steel":  [hexc(c) for c in ("#1d2230", "#3d4658", "#6c7a8e", "#a7b3c2", "#dfe6ee", "#ffffff")],
    "mail":   [hexc(c) for c in ("#15181f", "#2b313d", "#4a5262", "#6e788a", "#97a2b3", "#c3ccd8")],
    "gold":   [hexc(c) for c in ("#4a2a0c", "#8a5414", "#c98a1e", "#efbd3c", "#ffe27a", "#fff6c8")],
    "cloth":  [hexc(c) for c in ("#5a5468", "#8f8a9c", "#c4c0cc", "#e6e3ea", "#faf8fc", "#ffffff")],
    "red":    [hexc(c) for c in ("#3a0a12", "#6e1420", "#a8222c", "#d63c38", "#f2705a", "#ffb08a")],
    "leather": [hexc(c) for c in ("#26140c", "#462514", "#6e3e1e", "#98602e", "#c08848", "#e2b27a")],
    "black":  [hexc(c) for c in ("#06060a", "#0d0d14", "#16161f", "#22222e", "#30303e", "#40404e")],
}


class Atlas:
    def __init__(self, size=TEX):
        self.size = size
        self.img = np.zeros((size, size, 3), dtype=np.float32)
        self.glow = np.zeros((size, size), dtype=bool)

    def put(self, x, y, ramp, tone):
        if 0 <= x < self.size and 0 <= y < self.size:
            r = RAMPS[ramp]
            self.img[y, x] = r[int(np.clip(tone, 0, len(r) - 1))]


class Rect:
    """A part's area on the atlas: (x, y) top-left in pixels, w x h."""
    def __init__(self, atlas, x, y, w, h):
        self.a, self.x, self.y, self.w, self.h = atlas, x, y, w, h

    def uv(self, u, v):
        """loft (u around 0..1, v along 0..1 top->bottom) -> atlas UV (0..1, v up)."""
        px = self.x + u * self.w
        py = self.y + v * self.h
        return px / self.a.size, 1 - py / self.a.size

    # painting helpers (u: 0..1 around the part, front at 0.5; v: 0 top .. 1 bottom)
    def shade_fill(self, ramp, base=2.0, contrast=2.4, top=0.7, v0=0.0, v1=1.0, dither=True):
        light_a = -0.75   # light from the viewer's upper left (character's right side)
        for py in range(int(self.h * v0), int(math.ceil(self.h * v1))):
            for px in range(self.w):
                u = (px + 0.5) / self.w
                v = (py + 0.5) / self.h
                ang = (u - 0.5) * 2 * math.pi
                lit = 0.45 * math.cos(ang - light_a) + 0.25
                t = base + contrast * lit * 0.5 + top * (0.5 - v)
                tone = int(math.floor(t))
                frac = t - tone
                # dither only in a narrow band around each tone boundary (clean flat bands elsewhere)
                if dither and frac > 0.78 and (px + py) % 2 == 0:
                    tone += 1
                elif frac > 0.9:
                    tone += 1
                self.a.put(self.x + px, self.y + py, ramp, tone)

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

    def dot(self, u, v, ramp, tone, glow=False):
        x, y = self.x + int(u * self.w), self.y + int(v * self.h)
        self.a.put(x, y, ramp, tone)
        if glow and 0 <= x < self.a.size and 0 <= y < self.a.size:
            self.a.glow[y, x] = True

    def box(self, u0, v0, u1, v1, ramp, tone, outline=None):
        for py in range(int(v0 * self.h), int(math.ceil(v1 * self.h))):
            for px in range(int(u0 * self.w), int(math.ceil(u1 * self.w))):
                self.a.put(self.x + px, self.y + py, ramp, tone)
        if outline:
            r, t = outline
            self.hline(v0, r, t, u0, u1); self.hline(v1 - 1 / self.h, r, t, u0, u1)
            self.vline(u0, r, t, v0, v1); self.vline(u1 - 1 / self.w, r, t, v0, v1)

    def line(self, u0, v0, u1, v1, ramp, tone, thick=1):
        n = int(max(abs(u1 - u0) * self.w, abs(v1 - v0) * self.h)) + 1
        for i in range(n + 1):
            t = i / n
            u, v = u0 + (u1 - u0) * t, v0 + (v1 - v0) * t
            for k in range(thick):
                self.a.put(self.x + int(u * self.w) + k, self.y + int(v * self.h), ramp, tone)


# ----------------------------------------------------------------------------- lofted geometry with planned UVs

class Builder:
    def __init__(self):
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.new("UVMap")
        self.bones = self.bm.verts.layers.int.new("bone")      # -1 = auto weights
        self.bone_names = []

    def _bone(self, name):
        if name is None:
            return -1
        if name not in self.bone_names:
            self.bone_names.append(name)
        return self.bone_names.index(name)

    def loft(self, rect, sections, sides=8, cap_top=True, cap_bot=True, bone=None, mirror=False):
        """sections: list of (cx, cy, z, rx, ry[, bulge list per side]); top -> bottom. front = -Y."""
        bi = self._bone(bone)
        rings = []
        for s in sections:
            cx, cy, z, rx, ry = s[:5]
            bulge = s[5] if len(s) > 5 else None
            ring = []
            for i in range(sides):
                a = math.pi + 2 * math.pi * i / sides      # i = 0 at the back, sides/2 at the front
                m = bulge[i] if bulge else 1.0
                x = cx + math.sin(a) * rx * m
                y = cy - math.cos(a) * ry * m
                if mirror:
                    x = -x
                v = self.bm.verts.new((x, y, z))
                v[self.bones] = bi
                ring.append(v)
            rings.append(ring)
        # cumulative length for v
        zs = [s[2] for s in sections]
        total = sum(abs(zs[i] - zs[i + 1]) for i in range(len(zs) - 1)) or 1
        vs = [0.0]
        for i in range(len(zs) - 1):
            vs.append(vs[-1] + abs(zs[i] - zs[i + 1]) / total)
        cap_v = 0.04
        vs = [cap_v + v * (1 - 2 * cap_v) for v in vs]
        for r in range(len(rings) - 1):
            for i in range(sides):
                j = (i + 1) % sides
                quad = [rings[r][i], rings[r][j], rings[r + 1][j], rings[r + 1][i]]
                if mirror:
                    quad.reverse()
                f = self.bm.faces.new(quad)
                uvs = [(i / sides, vs[r]), ((i + 1) / sides, vs[r]), ((i + 1) / sides, vs[r + 1]), (i / sides, vs[r + 1])]
                if mirror:
                    uvs.reverse()
                for loop, (u, vv) in zip(f.loops, uvs):
                    loop[self.uv].uv = rect.uv(u, vv)
        for ring, vcap, top in ((rings[0], 0.01, True), (rings[-1], 0.99, False)):
            if (top and not cap_top) or (not top and not cap_bot):
                continue
            c = sum((v.co for v in ring), ring[0].co * 0) / len(ring)
            cv = self.bm.verts.new(c)
            cv[self.bones] = bi
            for i in range(sides):
                j = (i + 1) % sides
                tri = [cv, ring[j], ring[i]] if top else [cv, ring[i], ring[j]]
                if mirror:
                    tri.reverse()
                f = self.bm.faces.new(tri)
                for loop in f.loops:
                    u = (i + 0.5) / sides
                    loop[self.uv].uv = rect.uv(u, vcap)

    def box(self, rect, center, size, bone=None, taper_top=1.0, mirror=False):
        """Tapered box (feet, hands, buckles) mapped onto one rect."""
        bi = self._bone(bone)
        cx, cy, cz = center
        if mirror:
            cx = -cx
        sx, sy, sz = (s / 2 for s in size)
        corners = []
        for z, k in ((-sz, 1.0), (sz, taper_top)):
            for x, y in ((-sx, -sy), (sx, -sy), (sx, sy), (-sx, sy)):
                v = self.bm.verts.new((cx + x * k, cy + y * k, cz + z))
                v[self.bones] = bi
                corners.append(v)
        b, t = corners[:4], corners[4:]
        faces = [[b[0], b[1], t[1], t[0]], [b[1], b[2], t[2], t[1]], [b[2], b[3], t[3], t[2]], [b[3], b[0], t[0], t[3]],
                 [t[0], t[1], t[2], t[3]], [b[3], b[2], b[1], b[0]]]
        for fv in faces:
            f = self.bm.faces.new(fv)
            for loop, (u, v) in zip(f.loops, ((0.1, 0.9), (0.9, 0.9), (0.9, 0.1), (0.1, 0.1))):
                loop[self.uv].uv = rect.uv(u, v)

    def finish(self, name):
        me = bpy.data.meshes.new("Skin_" + name)
        self.bm.normal_update()
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces)
        self.bm.to_mesh(me)
        o = bpy.data.objects.new("Skin", me)
        bpy.context.scene.collection.objects.link(o)
        for p in me.polygons:
            p.use_smooth = True
        # weights: tagged parts are rigid on their bone, the rest blends by distance (characters.py rules)
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
                bname = self.bone_names[t]
                for g in o.vertex_groups:
                    g.remove([i])
                o.vertex_groups[bname].add([i], 1.0, "REPLACE")
        return o


def side(name, s):
    return name + ("L" if s > 0 else "R")


# ----------------------------------------------------------------------------- Knight

def knight():
    A = Atlas()
    R = {
        "torso": Rect(A, 0, 0, 64, 40), "fauld": Rect(A, 64, 0, 64, 22), "helm": Rect(A, 64, 22, 48, 30),
        "pauld": Rect(A, 0, 40, 40, 24), "upper": Rect(A, 40, 40, 24, 18), "fore": Rect(A, 0, 64, 32, 34),
        "thigh": Rect(A, 32, 64, 32, 24), "shin": Rect(A, 64, 56, 32, 36), "foot": Rect(A, 96, 56, 16, 16),
        "neck": Rect(A, 112, 22, 16, 12), "hand": Rect(A, 96, 72, 24, 24), "thumb": Rect(A, 120, 72, 8, 12), "finger": Rect(A, 120, 84, 8, 12), "toe": Rect(A, 112, 56, 16, 16), "couter": Rect(A, 96, 96, 16, 16),
    }
    B = Builder()
    chest_bulge = [0.95, 0.95, 1.0, 1.08, 1.14, 1.08, 1.0, 0.95]
    TORSO = [(0, 0.005, 1.6, 0.1, 0.085), (0, 0, 1.53, 0.21, 0.13), (0, 0, 1.43, 0.25, 0.155, chest_bulge),
             (0, -0.01, 1.27, 0.205, 0.145, chest_bulge), (0, 0, 1.12, 0.145, 0.108), (0, 0, 0.98, 0.17, 0.12)]
    B.loft(R["torso"], TORSO)
    B.loft(R["fauld"], [(0, 0, 1.06, 0.185, 0.135), (0, 0, 0.92, 0.215, 0.16), (0, 0, 0.78, 0.235, 0.175)],
           cap_top=False, cap_bot=False, bone="Body")
    ridge = [1, 1, 1, 1.03, 1.12, 1.03, 1, 1]
    B.loft(R["helm"], [(0, 0, 1.95, 0.13, 0.14), (0, 0, 1.93, 0.15, 0.16, ridge), (0, -0.005, 1.79, 0.155, 0.165, ridge),
                       (0, 0, 1.66, 0.15, 0.16, ridge), (0, 0, 1.62, 0.12, 0.125)], bone="Head")
    for s in (1, -1):
        mir = s < 0
        B.loft(R["pauld"], [(0.27, 0, 1.635, 0.03, 0.03), (0.275, 0, 1.6, 0.12, 0.11), (0.285, 0, 1.53, 0.165, 0.15),
                            (0.3, 0, 1.44, 0.17, 0.155), (0.305, 0, 1.4, 0.16, 0.15)], cap_bot=False,
               bone=side("Arm", s), mirror=mir)
        B.loft(R["upper"], [(0.26, 0, 1.5, 0.07, 0.07), (0.29, 0, 1.33, 0.072, 0.07), (0.31, 0.005, 1.14, 0.058, 0.058)],
               mirror=mir)
        B.loft(R["fore"], [(0.31, 0.01, 1.2, 0.068, 0.068), (0.32, -0.005, 1.08, 0.072, 0.072), (0.328, -0.01, 0.95, 0.056, 0.054),
                           (0.332, -0.012, 0.93, 0.082, 0.078), (0.332, -0.015, 0.865, 0.064, 0.062)], mirror=mir)
        # gauntlet hand: palm faces the body (thin along x), fingers curl in, thumb on the inner front edge
        fore = side("ForeArm", s)
        # hand: one tapered loft, palm toward the thigh (thin in x), fingers curling forward + in; separate thumb
        B.loft(R["hand"], [(0.332, -0.012, 0.885, 0.044, 0.05), (0.333, -0.014, 0.845, 0.047, 0.068),
                           (0.334, -0.02, 0.795, 0.045, 0.07), (0.332, -0.022, 0.778, 0.04, 0.064)], bone=fore, mirror=mir)
        for fy, ln in ((-0.068, 1.0), (-0.035, 1.08), (-0.004, 1.0), (0.024, 0.85)):          # index, middle, ring, little
            B.loft(R["finger"], [(0.335, fy, 0.790, 0.017, 0.015), (0.332, fy - 0.004, 0.790 - 0.04 * ln, 0.016, 0.0145),
                                 (0.322, fy - 0.008, 0.790 - 0.068 * ln, 0.013, 0.012)], sides=6, bone=fore, mirror=mir)
        B.loft(R["thumb"], [(0.312, -0.05, 0.855, 0.022, 0.022), (0.308, -0.072, 0.82, 0.02, 0.02),
                            (0.306, -0.08, 0.79, 0.015, 0.015)], sides=6, bone=fore, mirror=mir)
        B.loft(R["thigh"], [(0.1, 0, 0.98, 0.11, 0.11), (0.105, -0.01, 0.78, 0.1, 0.1), (0.105, -0.01, 0.58, 0.078, 0.08)],
               mirror=mir)
        knee = [1, 1, 1, 1.12, 1.28, 1.12, 1, 1]
        B.loft(R["shin"], [(0.105, -0.01, 0.6, 0.08, 0.085, knee), (0.105, -0.01, 0.5, 0.085, 0.09, knee),
                           (0.105, 0.005, 0.36, 0.088, 0.088), (0.105, 0, 0.16, 0.068, 0.07), (0.105, 0, 0.1, 0.07, 0.075)],
               mirror=mir)
        B.box(R["foot"], (0.105, -0.02, 0.055), (0.125, 0.2, 0.11), bone=side("Shin", s), taper_top=0.85, mirror=mir)
        B.box(R["toe"], (0.105, -0.155, 0.035), (0.1, 0.1, 0.07), bone=side("Shin", s), taper_top=0.55, mirror=mir)
        B.box(R["couter"], (0.312, 0.062, 1.145), (0.075, 0.05, 0.1), bone=side("ForeArm", s), taper_top=0.6, mirror=mir)

    # ---------------- paint
    t = R["torso"]
    t.shade_fill("steel")
    t.hline(0.0, "steel", 1); t.hline(0.97, "steel", 0)
    t.vline(0.5, "steel", 5, 0.2, 0.75)                            # breastplate ridge highlight
    t.vline(0.5 + 1 / 64, "steel", 1, 0.2, 0.75)
    # crossed gold straps, straight in 3D: shoulder (x .16, z 1.52) to opposite hip (x -.13, z 1.08)
    zs = [sec[2] for sec in TORSO]; rxs = [sec[3] for sec in TORSO]
    def rx_at(z):
        for k in range(len(zs) - 1):
            if zs[k] >= z >= zs[k + 1]:
                f = (zs[k] - z) / (zs[k] - zs[k + 1])
                return rxs[k] + (rxs[k + 1] - rxs[k]) * f
        return rxs[-1]
    for sgn in (1, -1):
        for py in range(t.h):
            v = (py + 0.5) / t.h
            z = zs[0] - (v - 0.04) / 0.92 * (zs[0] - zs[-1])
            if not (1.08 <= z <= 1.52):
                continue
            f = (1.52 - z) / 0.44
            x = sgn * (0.16 - 0.29 * f)
            u = 0.5 + math.asin(max(-1, min(1, x / rx_at(z)))) / (2 * math.pi)
            px = int(u * t.w)
            for k, tone in ((0, 4), (1, 2)):
                A.put(t.x + px + k, t.y + py, "gold", tone)
    # gold boss exactly where the straps cross (x = 0 -> z ~ 1.278)
    vx = 0.04 + 0.92 * (zs[0] - 1.278) / (zs[0] - zs[-1])
    t.box(0.47, vx - 0.045, 0.53 + 1 / 64, vx + 0.045, "gold", 3)       # solid stud
    t.box(0.48, vx - 0.03, 0.5, vx, "gold", 5)                          # lit corner
    t.hline(vx + 0.045, "gold", 1, 0.47, 0.53 + 1 / 64)                  # shadow under it
    # back plate: spine ridge, rivets, shoulder-blade plate line
    t.vline(0.0, "steel", 4, 0.15, 0.8); t.vline(1 - 1 / 64, "steel", 1, 0.15, 0.8)
    t.hline(0.35, "steel", 1, 0.0, 0.2); t.hline(0.35, "steel", 1, 0.8, 1.0)
    for u in (0.06, 0.94):
        for v in (0.2, 0.45):
            t.dot(u, v, "steel", 5)
    t.hline(0.72, "steel", 0); t.hline(0.73, "steel", 4)            # plate seam under the chest
    t.hline(0.86, "gold", 3, thick=3); t.hline(0.86, "gold", 4, 0.45, 0.55, thick=3)   # belt + buckle
    for u in (0.1, 0.2, 0.8, 0.9):
        t.dot(u, 0.12, "steel", 5); t.dot(u, 0.62, "steel", 5)      # rivets
    f = R["fauld"]
    f.shade_fill("steel", base=1.8)
    for v in (0.0, 0.34, 0.67):
        f.hline(v, "steel", 0); f.hline(v + 1 / 22, "steel", 4)     # overlapping lames
    f.hline(0.95, "gold", 3, thick=1)
    f.box(0.4, 0.05, 0.6, 1.0, "cloth", 3, outline=("black", 1))     # tabard
    f.box(0.485, 0.2, 0.515 + 1 / 64, 0.85, "black", 1)              # black cross
    f.box(0.44, 0.38, 0.56, 0.5, "black", 1)
    h = R["helm"]
    h.shade_fill("steel", base=2.2)
    h.hline(0.03, "steel", 0); h.hline(0.12, "steel", 1); h.hline(0.94, "steel", 0)
    h.box(0.38, 0.33, 0.62, 0.42, "black", 0)                         # eye slit
    h.box(0.495, 0.33, 0.505 + 1 / 48, 0.42, "steel", 4)              # nose bar between the eyes
    h.vline(0.5, "steel", 5, 0.12, 0.92); h.vline(0.5 + 1 / 48, "steel", 2, 0.12, 0.92)
    for u in (0.42, 0.45, 0.55, 0.58):
        for v in (0.56, 0.62, 0.68, 0.74):
            h.dot(u, v, "black", 0)                                   # grid of breathing holes either side of the ridge
    for u in (0.3, 0.7, 0.15, 0.85):
        h.dot(u, 0.2, "gold", 4)
    h.hline(0.13, "gold", 3, 0.35, 0.65)                              # gold brow band
    p = R["pauld"]
    p.shade_fill("steel", base=2.2, top=1.4)
    for v in (0.45, 0.65, 0.85):
        p.hline(v, "steel", 0); p.hline(v + 1 / 24, "steel", 4)
    p.hline(0.95, "gold", 3, thick=2)
    for u in (0.25, 0.5, 0.75):
        p.dot(u, 0.3, "steel", 5)
    up = R["upper"]
    up.shade_fill("mail", base=2.0)
    for py in range(up.h):
        for px in range(up.w):
            if (px + (py // 2) * 1) % 3 == 0 and py % 2 == 0:
                A.put(up.x + px, up.y + py, "mail", 1)                # chainmail rings
    fo = R["fore"]
    fo.shade_fill("steel", base=2.0)
    fo.hline(0.0, "steel", 1)
    fo.hline(0.32, "steel", 0); fo.hline(0.33, "steel", 4)
    fo.hline(0.47, "gold", 3, thick=2)                                # gauntlet cuff trim
    fo.hline(0.97, "steel", 0)
    hd = R["hand"]                                                   # plated back of hand (front = u .5, outer = u .75)
    hd.shade_fill("steel", base=2.0, contrast=2.2, top=0.4)
    hd.hline(0.04, "steel", 0)
    hd.box(0.6, 0.15, 0.9, 0.7, "steel", 3, outline=("steel", 0))
    hd.hline(0.16, "steel", 4, 0.62, 0.88)
    hd.dot(0.75, 0.4, "gold", 4)
    hd.hline(0.9, "steel", 4); hd.hline(0.96, "steel", 0)           # knuckle ridge
    fg = R["finger"]
    fg.shade_fill("steel", base=2.0, contrast=2.0, top=0.6, dither=False)
    fg.hline(0.45, "steel", 1); fg.hline(0.5, "steel", 4)           # knuckle joint plate
    fg.hline(0.95, "steel", 1)
    tb = R["thumb"]
    tb.shade_fill("steel", base=2.0, contrast=2.0, top=0.4)
    tb.hline(0.5, "steel", 1); tb.hline(0.95, "steel", 0)
    th = R["thigh"]
    th.shade_fill("steel", base=1.9)
    th.hline(0.5, "steel", 0); th.hline(0.5 + 1 / 24, "steel", 4)
    sh = R["shin"]
    sh.shade_fill("steel", base=2.1)
    sh.box(0.38, 0.0, 0.62, 0.28, "steel", 3, outline=("steel", 0))  # knee cop: shaded plate with a lit top edge
    sh.hline(0.03, "steel", 5, 0.4, 0.6); sh.box(0.38, 0.2, 0.62, 0.26, "steel", 2)
    sh.dot(0.5, 0.12, "gold", 4)
    sh.hline(0.3, "steel", 0)
    sh.vline(0.5, "steel", 5, 0.32, 0.85)
    sh.hline(0.88, "steel", 0)
    for key in ("toe", "couter"):
        r_ = R[key]
        r_.shade_fill("steel", base=2.1, contrast=1.6, dither=False)
        r_.box(0.0, 0.0, 1.0, 1.0, "steel", 3, outline=("steel", 0))
        r_.hline(0.5, "steel", 1, 0.1, 0.9); r_.hline(0.56, "steel", 4, 0.1, 0.9)
    fb = R["foot"]
    fb.shade_fill("steel", base=1.9, contrast=1.6, dither=False)
    fb.box(0.0, 0.0, 1.0, 1.0, "steel", 2, outline=("steel", 0))
    for v in (0.3, 0.55):
        fb.hline(v, "steel", 0, 0.08, 0.92); fb.hline(v + 1 / 16, "steel", 4, 0.08, 0.92)   # sabaton lames
    R["neck"].shade_fill("mail")
    return B, A


def write_texture(A, name):
    os.makedirs(OUT_TEX, exist_ok=True)
    img = bpy.data.images.new("T_Char_" + name, TEX, TEX, alpha=True)
    img.colorspace_settings.name = "Non-Color"
    rgba = np.concatenate([A.img[::-1], np.where(A.glow[::-1], 32 / 255, 0.0)[..., None]], -1)   # rows bottom-up
    img.pixels[:] = rgba.astype(np.float32).ravel()
    img.filepath_raw = os.path.join(OUT_TEX, f"T_Char_{name}.png")
    img.file_format = "PNG"
    img.save()
    print("painted", img.filepath_raw)
    return img


HEROES = {"Knight": knight}


def build(name, preview=False, reset=True):
    if reset:
        gm.reset()
    B, A = HEROES[name]()
    mesh = B.finish(name)
    img = write_texture(A, name)
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
    rp.setup_render(1200, 1200, transparent=False)
    rp.camera((0.9, -3.6, 1.6), (0, 0, 1.05), lens=50)
    if "--hands" in sys.argv:
        rp.camera((0.75, -1.15, 1.15), (0.25, 0, 0.95), lens=50)
    if "--hands-side" in sys.argv:
        rp.camera((1.25, -0.25, 1.0), (0.3, -0.02, 0.92), lens=50)
    for a in sys.argv:
        if a.startswith("--cam="):
            v = [float(x) for x in a[6:].split(",")]
            rp.camera(tuple(v[0:3]), tuple(v[3:6]), lens=v[6] if len(v) > 6 else 50)
    out = next((a[6:] for a in sys.argv if a.startswith("--out=")), None)
    bpy.context.scene.render.filepath = out or os.path.join(gm.ROOT, "Tools", "Blender", "hero_v5.png")
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
