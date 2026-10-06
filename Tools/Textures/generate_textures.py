"""
MultiBash procedural texture + icon generator.

  python Tools/Textures/generate_textures.py

Outputs:
  Assets/_Game/Art/Textures/   T_Palette.png, T_Ground.png, T_Stone.png
  Assets/_Game/Art/VFX/        soft particle, spark, ring, slash, puddle, lightning textures
  Assets/_Game/UI/Sprites/     panel / button / bar / circle sprites (9-slice friendly)
  Assets/_Game/UI/Icons/       Weapons/, Powerups/ icons (128x128)

Icons are drawn from simple vector shapes so they stay readable at small sizes.
To restyle: tweak the colors/shapes below and re-run; Unity reimports automatically.
"""
import json
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
GAME = os.path.join(ROOT, "Assets", "_Game")
with open(os.path.join(ROOT, "Tools", "palette.json")) as f:
    PAL = json.load(f)


def hexrgb(h, a=255):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


def save(img, *parts):
    path = os.path.join(GAME, *parts)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path)
    print("wrote", os.path.relpath(path, ROOT))


# ----------------------------------------------------------------------------- palette

PATTERN_ALPHA = {"noise": 255, "brick": 191, "leaves": 128, "grain": 64, "glow": 32, "flat": 0}


def pal_color(name):
    """'#rrggbb|pattern' -> (r,g,b,255)"""
    return hexrgb(PAL["colors"][name].split("|")[0])


def palette():
    g, c = PAL["grid"], PAL["cellPixels"]
    img = Image.new("RGBA", (g * c, g * c), (255, 0, 255, 255))
    d = ImageDraw.Draw(img)
    for i, (name, value) in enumerate(PAL["colors"].items()):
        hx, _, pattern = value.partition("|")
        x, y = i % g, i // g
        d.rectangle([x * c, y * c, x * c + c - 1, y * c + c - 1], fill=hexrgb(hx, PATTERN_ALPHA.get(pattern or "noise", 255)))
    save(img, "Art", "Textures", "T_Palette.png")


# ----------------------------------------------------------------------------- pixel detail atlas (PixelLit shader)

def detail_atlas():
    """2x2 atlas of 32x32 grayscale patterns: [noise | brick] (top row), [leaves | grain] (bottom row)."""
    rng = np.random.default_rng(42)
    S = 32

    # noise: chunky 2x2 blotches + speckles
    n = rng.random((S // 2, S // 2))
    n = np.kron(n, np.ones((2, 2)))
    n = 0.5 + (n - 0.5) * 0.6 + (rng.random((S, S)) > 0.93) * -0.25
    noise_p = np.clip(n, 0, 1)

    # bricks: 4 rows of bricks, offset every other row, mortar lines, per-brick tone
    b = np.zeros((S, S))
    rows, bw = 4, 16
    for r in range(rows):
        y0 = r * (S // rows)
        off = (bw // 2) * (r % 2)
        for x0 in range(-bw, S, bw):
            tone = 0.55 + rng.random() * 0.3
            for yy in range(y0, y0 + S // rows):
                for xx in range(x0 + off, x0 + off + bw):
                    b[yy % S, xx % S] = tone + (rng.random() - 0.5) * 0.12
        b[y0, :] = 0.18          # horizontal mortar
        for x0 in range(0, S, bw):
            b[y0:y0 + S // rows, (x0 + off) % S] = 0.18
    b[b > 0.2] += np.clip((np.roll(b, 1, axis=0) < 0.2) * 0.15, 0, 1)[b > 0.2]  # highlight under mortar
    brick_p = np.clip(b, 0, 1)

    # leaves / grass: clusters of light leaves over dark
    l = np.full((S, S), 0.35)
    for _ in range(70):
        cx, cy = rng.integers(0, S, 2)
        tone = 0.5 + rng.random() * 0.45
        for dx, dy in ((0, 0), (1, 0), (0, 1), (-1, 0), (1, 1)):
            if rng.random() < 0.85:
                l[(cy + dy) % S, (cx + dx) % S] = tone
    l += (rng.random((S, S)) > 0.9) * -0.15
    leaves_p = np.clip(l, 0, 1)

    # wood grain: vertical streaks with knots
    gx = np.tile(np.sin(np.arange(S) * 0.9 + rng.random(S).cumsum() * 0.3), (S, 1))
    g2 = 0.55 + gx * 0.12 + (rng.random((S, S)) - 0.5) * 0.08
    for _ in range(3):
        kx, ky = rng.integers(2, S - 2, 2)
        g2[ky - 1:ky + 2, kx - 1:kx + 2] = 0.3
    grain_p = np.clip(g2, 0, 1)

    atlas = np.zeros((S * 2, S * 2))
    atlas[:S, :S] = noise_p    # image top-left  -> uv (0, 0.5..1)
    atlas[:S, S:] = brick_p    # image top-right -> uv (0.5..1, 0.5..1)
    atlas[S:, :S] = leaves_p   # bottom-left     -> uv (0..0.5, 0..0.5)
    atlas[S:, S:] = grain_p    # bottom-right
    img = Image.fromarray((atlas * 255).astype(np.uint8), "L").convert("RGB")
    save(img, "Art", "Textures", "T_DetailAtlas.png")


# ----------------------------------------------------------------------------- pixel terrain textures

def pixel_tex(size, base, variants, seed, speck=0.0):
    """Chunky pixel texture: base color + random 2px clusters from a list of (color, chance)."""
    rng = np.random.default_rng(seed)
    img = np.zeros((size, size, 3))
    img[:] = base
    lowres = rng.random((size // 2, size // 2))
    acc = 0.0
    for col, chance in variants:
        mask = (lowres >= acc) & (lowres < acc + chance)
        img[np.kron(mask, np.ones((2, 2), bool))] = col
        acc += chance
    if speck:
        m = rng.random((size, size)) < speck
        img[m] = img[m] * 1.25
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB")


def terrain_textures():
    grass = pixel_tex(64, (58, 92, 50), [((52, 84, 46), 0.25), ((66, 102, 54), 0.2), ((76, 112, 58), 0.05), ((48, 76, 44), 0.06)], 1)
    # a few blade strokes
    d = ImageDraw.Draw(grass)
    rng = np.random.default_rng(3)
    for _ in range(40):
        x, y = rng.integers(0, 64, 2)
        d.line([(x, y), (x, y - 2)], fill=(88, 130, 62))
    save(grass, "Art", "Textures", "T_TerrainGrass.png")

    dirt = pixel_tex(64, (104, 80, 56), [((88, 66, 46), 0.25), ((120, 94, 66), 0.2), ((74, 56, 40), 0.08), ((136, 110, 80), 0.04)], 2)
    save(dirt, "Art", "Textures", "T_TerrainDirt.png")

    cliff = pixel_tex(64, (112, 88, 62), [((96, 74, 52), 0.3), ((128, 102, 72), 0.15), ((80, 62, 44), 0.1)], 4)
    d = ImageDraw.Draw(cliff)
    for y in (12, 27, 41, 55):   # horizontal strata
        d.line([(0, y), (63, y)], fill=(78, 60, 42))
        d.line([(0, y + 1), (63, y + 1)], fill=(140, 112, 80))
    for _ in range(14):           # embedded stones
        x, y = rng.integers(0, 60, 2)
        d.rectangle([x, y, x + 3, y + 2], fill=(130, 130, 128))
        d.line([(x, y + 2), (x + 3, y + 2)], fill=(90, 90, 90))
    save(cliff, "Art", "Textures", "T_TerrainCliff.png")

    moss = pixel_tex(64, (54, 84, 46), [((48, 76, 42), 0.3), ((62, 94, 50), 0.2), ((84, 74, 56), 0.08)], 5)
    save(moss, "Art", "Textures", "T_TerrainMoss.png")



def volcano_textures():
    """Volcano level: basalt ground, ash, magma crust, dark cliff and the animated lava surface."""
    rng = np.random.default_rng(21)
    basalt = pixel_tex(64, (46, 43, 46), [((38, 35, 38), 0.28), ((56, 52, 54), 0.18), ((30, 28, 31), 0.08), ((70, 64, 62), 0.04)], 21)
    d = ImageDraw.Draw(basalt)
    for _ in range(10):   # hex-ish crack lines
        x, y = rng.integers(0, 60, 2)
        d.line([(x, y), (x + rng.integers(2, 6), y + rng.integers(-2, 3))], fill=(30, 26, 28))
    save(basalt, "Art", "Textures", "T_TerrainBasalt.png")

    ash = pixel_tex(64, (96, 90, 86), [((84, 78, 76), 0.28), ((110, 104, 98), 0.18), ((70, 64, 62), 0.08), ((124, 116, 106), 0.04)], 22)
    save(ash, "Art", "Textures", "T_TerrainAsh.png")

    crust = pixel_tex(64, (52, 36, 32), [((40, 28, 26), 0.3), ((66, 42, 34), 0.15)], 23)
    d = ImageDraw.Draw(crust)
    for _ in range(18):   # glowing seams in the cooled crust
        x, y = rng.integers(0, 62, 2)
        pts = [(x, y)]
        for _ in range(3):
            x = (x + rng.integers(-3, 4)) % 64
            y = (y + rng.integers(1, 4)) % 64
            pts.append((x, y))
        d.line(pts, fill=(236, 104, 34))
    save(crust, "Art", "Textures", "T_TerrainMagma.png")

    cliff = pixel_tex(64, (52, 44, 44), [((42, 36, 36), 0.3), ((64, 54, 52), 0.15), ((34, 28, 30), 0.1)], 24)
    d = ImageDraw.Draw(cliff)
    for x in (8, 21, 33, 47, 58):   # vertical basalt columns
        d.line([(x, 0), (x, 63)], fill=(30, 26, 28))
        d.line([(x + 1, 0), (x + 1, 63)], fill=(78, 68, 66))
    for y in (16, 40):
        d.line([(0, y), (63, y)], fill=(34, 28, 30))
    save(cliff, "Art", "Textures", "T_TerrainVolcCliff.png")

    # lava: tileable noise -> hot palette, quantized for pixel look
    n = tile_noise(64, 4, 25)
    n = (n - n.min()) / (n.max() - n.min())
    n = np.floor(n * 7) / 7
    lava = colorize(n, [(0.0, (90, 16, 6)), (0.3, (190, 44, 10)), (0.55, (255, 104, 20)), (0.8, (255, 180, 50)), (1.0, (255, 236, 140))])
    img = Image.fromarray(np.clip(lava, 0, 255).astype(np.uint8), "RGB")
    save(img, "Art", "Textures", "T_Lava.png")


# ----------------------------------------------------------------------------- tileable noise

def tile_noise(size, octaves, seed):
    rng = np.random.default_rng(seed)
    out = np.zeros((size, size))
    amp, total = 1.0, 0.0
    for o in range(octaves):
        cells = 4 * (2 ** o)
        grid = rng.random((cells, cells))
        # bilinear upsample with wraparound -> tileable
        xs = np.linspace(0, cells, size, endpoint=False)
        x0 = np.floor(xs).astype(int)
        t = xs - x0
        t = t * t * (3 - 2 * t)
        x1 = (x0 + 1) % cells
        a = grid[x0][:, x0]
        b = grid[x0][:, x1]
        c = grid[x1][:, x0]
        d = grid[x1][:, x1]
        tx = t[None, :]
        ty = t[:, None]
        layer = (a * (1 - tx) + b * tx) * (1 - ty) + (c * (1 - tx) + d * tx) * ty
        out += layer * amp
        total += amp
        amp *= 0.5
    return out / total


def colorize(n, stops):
    """stops: list of (t, rgb)."""
    h, w = n.shape
    out = np.zeros((h, w, 3))
    for i in range(len(stops) - 1):
        t0, c0 = stops[i]
        t1, c1 = stops[i + 1]
        m = (n >= t0) & (n <= t1)
        f = ((n - t0) / max(1e-6, t1 - t0))[..., None]
        out[m] = (np.array(c0) * (1 - f) + np.array(c1) * f)[m]
    return out


def ground():
    n = tile_noise(512, 6, 1)
    n2 = tile_noise(512, 3, 2)
    n = np.clip((n - 0.25) / 0.5, 0, 1)
    col = colorize(n, [(0, (38, 52, 44)), (0.45, (52, 70, 56)), (0.6, (66, 84, 60)), (0.8, (78, 70, 56)), (1, (92, 82, 66))])
    col *= (0.85 + 0.3 * n2)[..., None]
    rng = np.random.default_rng(5)
    speck = rng.random((512, 512)) > 0.996
    col[speck] = (110, 112, 118)
    img = Image.fromarray(np.clip(col, 0, 255).astype(np.uint8), "RGB")
    save(img, "Art", "Textures", "T_Ground.png")


def stone():
    n = tile_noise(256, 5, 9)
    col = colorize(n, [(0, (80, 84, 92)), (0.5, (120, 124, 132)), (1, (150, 152, 160))])
    save(Image.fromarray(col.astype(np.uint8), "RGB"), "Art", "Textures", "T_Stone.png")


# ----------------------------------------------------------------------------- VFX (pixel style: low-res, hard alpha steps, point filtered)

def quant(a, levels=4):
    """Quantize alpha into a few hard steps -> crisp pixel look."""
    return np.round(np.clip(a, 0, 1) * (levels - 1)) / (levels - 1)


def radial(size, fn, levels=4):
    y, x = np.mgrid[0:size, 0:size]
    c = (size - 1) / 2
    rr = np.sqrt((x - c) ** 2 + (y - c) ** 2) / c
    r = np.clip(rr, 0, 1)
    a = quant(np.clip(fn(r), 0, 1), levels)
    a[rr >= 1] = 0
    img = np.zeros((size, size, 4), np.uint8)
    img[..., :3] = 255
    img[..., 3] = (a * 255).astype(np.uint8)
    return Image.fromarray(img, "RGBA")


def vfx():
    save(radial(16, lambda r: (1 - r) ** 1.5), "Art", "VFX", "T_SoftParticle.png")
    save(radial(48, lambda r: ((r > 0.86) & (r < 0.97)).astype(float) + ((r > 0.8) & (r <= 0.86)) * 0.5, 3), "Art", "VFX", "T_Ring.png")
    spark = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    d = ImageDraw.Draw(spark)
    d.rectangle([2, 2, 5, 5], fill=(255, 255, 255, 255))
    d.point([(3, 1), (4, 1), (3, 6), (4, 6), (1, 3), (1, 4), (6, 3), (6, 4)], fill=(255, 255, 255, 170))
    save(spark, "Art", "VFX", "T_Spark.png")

    # slash: crisp pixel crescent (circle centred at the bottom middle, radius 0.41 of the width)
    s = 64
    y, x = np.mgrid[0:s, 0:s]
    cx, cy = s / 2, s
    r = np.sqrt((x - cx) ** 2 + (y - cy) ** 2) / (s / 2)
    ang = np.arctan2(cy - y, x - cx)
    fade = np.clip(np.sin(ang), 0, 1)
    thick = 0.05 + 0.13 * fade
    band = (np.abs(r - 0.78) < thick).astype(float)
    edge = (np.abs(r - (0.78 + thick)) < 0.035).astype(float)
    a = np.clip(band * (0.55 + 0.45 * (fade > 0.5)) + edge, 0, 1) * (fade > 0.05)
    img = np.zeros((s, s, 4), np.uint8)
    img[..., :3] = 255
    img[..., 3] = (quant(a, 3) * 255).astype(np.uint8)
    save(Image.fromarray(img, "RGBA"), "Art", "VFX", "T_Slash.png")

    # poison puddle: blotchy pixel disc
    n = tile_noise(32, 3, 21)
    y, x = np.mgrid[0:32, 0:32]
    r = np.sqrt((x - 15.5) ** 2 + (y - 15.5) ** 2) / 15.5
    a = np.clip((1 - r) * 2.4 + (n - 0.5) * 1.4, 0, 1)
    a = np.where(a > 0.3, np.where(a > 0.7, 0.9, 0.6), 0)
    img = np.zeros((32, 32, 4), np.uint8)
    img[..., 0] = np.where(n > 0.55, 200, 150).astype(np.uint8)
    img[..., 1] = 255
    img[..., 2] = np.where(n > 0.55, 90, 50).astype(np.uint8)
    img[..., 3] = (a * 255).astype(np.uint8)
    save(Image.fromarray(img, "RGBA"), "Art", "VFX", "T_Puddle.png")

    # lightning strip
    img = Image.new("RGBA", (64, 8), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 2, 63, 5], fill=(160, 210, 255, 150))
    d.rectangle([0, 3, 63, 4], fill=(240, 250, 255, 255))
    save(img, "Art", "VFX", "T_Lightning.png")


# ----------------------------------------------------------------------------- UI sprites (pixel art, 9-slice, point filtered)

SLATE = (38, 50, 48, 245)
SLATE_DARK = (26, 35, 34, 250)
METAL = (150, 160, 158, 255)
METAL_HI = (205, 212, 210, 255)
METAL_LO = (88, 96, 95, 255)
INK = (10, 12, 12, 255)


def frame(size, fill, studs=True, inner_line=True):
    """Megabonk-like metal frame: black outline, 2px bevelled metal border, rivets in the corners."""
    w, h = size
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w - 1, h - 1], fill=INK)
    d.rectangle([1, 1, w - 2, h - 2], fill=METAL)
    d.line([(1, 1), (w - 2, 1)], fill=METAL_HI)
    d.line([(1, 1), (1, h - 2)], fill=METAL_HI)
    d.line([(1, h - 2), (w - 2, h - 2)], fill=METAL_LO)
    d.line([(w - 2, 1), (w - 2, h - 2)], fill=METAL_LO)
    d.rectangle([3, 3, w - 4, h - 4], fill=INK)
    d.rectangle([4, 4, w - 5, h - 5], fill=fill)
    if inner_line:
        d.line([(4, 4), (w - 5, 4)], fill=tuple(min(255, c + 14) for c in fill[:3]) + (fill[3],))
    if studs:
        for (x, y) in ((0, 0), (w - 4, 0), (0, h - 4), (w - 4, h - 4)):
            d.rectangle([x, y, x + 3, y + 3], fill=INK)
            d.rectangle([x + 1, y + 1, x + 2, y + 2], fill=METAL_HI)
    return img


def ui_sprites():
    # plain fill (bars, backgrounds) – crisp square
    save(Image.new("RGBA", (8, 8), (255, 255, 255, 255)), "UI", "Sprites", "UI_RoundRect.png")
    save(frame((24, 24), SLATE), "UI", "Sprites", "UI_Panel.png")
    save(frame((24, 24), SLATE_DARK, studs=False), "UI", "Sprites", "UI_TitleBar.png")

    # selection outline: 2px white with corner brackets
    o = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(o)
    d.rectangle([0, 0, 15, 15], outline=(255, 255, 255, 255), width=2)
    save(o, "UI", "Sprites", "UI_Outline.png")

    # rarity card: grey fill + light border; tinted by rarity color in code
    c = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(c)
    d.rectangle([0, 0, 15, 15], fill=INK)
    d.rectangle([1, 1, 14, 14], fill=(235, 235, 235, 255))
    d.rectangle([2, 2, 13, 13], fill=INK)
    d.rectangle([3, 3, 12, 12], fill=(118, 118, 118, 255))
    d.line([(3, 3), (12, 3)], fill=(140, 140, 140, 255))
    save(c, "UI", "Sprites", "UI_Card.png")

    # button: bevelled, tinted in code
    b = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(b)
    d.rectangle([0, 0, 15, 15], fill=INK)
    d.rectangle([1, 1, 14, 14], fill=(200, 200, 200, 255))
    d.line([(1, 1), (14, 1)], fill=(255, 255, 255, 255))
    d.line([(1, 2), (14, 2)], fill=(235, 235, 235, 255))
    d.rectangle([1, 12, 14, 14], fill=(120, 120, 120, 255))
    save(b, "UI", "Sprites", "UI_Button.png")

    # inventory slot: dark inset
    sl = Image.new("RGBA", (12, 12), (0, 0, 0, 0))
    d = ImageDraw.Draw(sl)
    d.rectangle([0, 0, 11, 11], fill=(10, 14, 14, 220))
    d.rectangle([1, 1, 10, 10], fill=(22, 30, 29, 220))
    d.line([(1, 10), (10, 10)], fill=(60, 72, 70, 220))
    save(sl, "UI", "Sprites", "UI_Slot.png")

    save(radial(16, lambda r: (r < 0.95).astype(float), 2), "UI", "Sprites", "UI_Circle.png")
    save(radial(32, lambda r: (1 - r) ** 1.5, 4), "UI", "Sprites", "UI_Glow.png")
    g = np.zeros((64, 4, 4), np.uint8)
    g[..., :3] = 255
    g[..., 3] = (quant(np.linspace(1, 0, 64), 6) * 255)[:, None].astype(np.uint8)
    save(Image.fromarray(g, "RGBA"), "UI", "Sprites", "UI_Gradient.png")

    arrow = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    ImageDraw.Draw(arrow).polygon([(8, 1), (15, 14), (8, 10), (1, 14)], fill=(255, 255, 255, 255))
    save(arrow, "UI", "Sprites", "UI_Arrow.png")

    # tiny pixel glyphs drawn from text grids
    glyphs = {
        "UI_Clock": ["..XXXX..", ".X....X.", "X...X..X", "X...X..X", "X...XX.X", "X......X", ".X....X.", "..XXXX.."],
        "UI_Skull": ["..XXXX..", ".XXXXXX.", "XXXXXXXX", "X..XX..X", "X..XX..X", "XXX..XXX", ".XXXXXX.", ".X.X.X.."],
        "UI_Heart": [".XX..XX.", "XXXXXXXX", "XXXXXXXX", "XXXXXXXX", ".XXXXXX.", "..XXXX..", "...XX...", "........"],
        "UI_Lock": ["..XXXX..", ".X....X.", ".X....X.", "XXXXXXXX", "XXX..XXX", "XXX..XXX", "XXXXXXXX", "XXXXXXXX"],
        "UI_Star": ["...XX...", "...XX...", "XXXXXXXX", ".XXXXXX.", "..XXXX..", ".XXXXXX.", ".XX..XX.", "X......X"],
    }
    for name, rows in glyphs.items():
        im = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
        px = im.load()
        for yy, row in enumerate(rows):
            for xx, ch in enumerate(row):
                if ch == "X":
                    px[xx + 1, yy + 1] = (255, 255, 255, 255)
        # 1px dark outline
        base = im.copy()
        bp = base.load()
        for yy in range(10):
            for xx in range(10):
                if bp[xx, yy][3] == 0 and any(0 <= xx + dx < 10 and 0 <= yy + dy < 10 and bp[xx + dx, yy + dy][3] > 0
                                              for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                    px[xx, yy] = (0, 0, 0, 255)
        save(im, "UI", "Sprites", name + ".png")


def pixelate_icon(img, size=32):
    """Shrink a 128px vector icon to crisp pixel art: hard alpha + 1px black outline."""
    small = img.resize((size, size), Image.BOX)
    arr = np.array(small)
    alpha = arr[..., 3] >= 110
    arr[..., 3] = np.where(alpha, 255, 0)
    out = arr.copy()
    for yy in range(size):
        for xx in range(size):
            if not alpha[yy, xx] and any(0 <= xx + dx < size and 0 <= yy + dy < size and alpha[yy + dy, xx + dx]
                                         for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                out[yy, xx] = (8, 8, 10, 255)
    return Image.fromarray(out, "RGBA")


# ----------------------------------------------------------------------------- icons

ICON = 128


def icon_base(c1, c2):
    img = Image.new("RGBA", (ICON, ICON), (0, 0, 0, 0))
    # radial gradient disc
    y, x = np.mgrid[0:ICON, 0:ICON]
    r = np.sqrt((x - 63.5) ** 2 + (y - 50) ** 2) / 90
    r = np.clip(r, 0, 1)[..., None]
    col = np.array(c1[:3]) * (1 - r) + np.array(c2[:3]) * r
    arr = np.zeros((ICON, ICON, 4), np.uint8)
    arr[..., :3] = col.astype(np.uint8)
    arr[..., 3] = 255
    bg = Image.fromarray(arr, "RGBA")
    mask = Image.new("L", (ICON, ICON), 0)
    ImageDraw.Draw(mask).rounded_rectangle([4, 4, ICON - 5, ICON - 5], radius=22, fill=255)
    img.paste(bg, (0, 0), mask)
    ImageDraw.Draw(img).rounded_rectangle([4, 4, ICON - 5, ICON - 5], radius=22, outline=(255, 255, 255, 90), width=3)
    return img


def glyph_layer():
    return Image.new("RGBA", (ICON, ICON), (0, 0, 0, 0))


def finish(base, glyph):
    shadow = glyph.split()[3].point(lambda a: int(a * 0.6))
    sh = Image.new("RGBA", (ICON, ICON), (0, 0, 0, 255))
    sh.putalpha(shadow)
    sh = sh.filter(ImageFilter.GaussianBlur(3))
    out = base.copy()
    out.alpha_composite(sh, (3, 4))
    out.alpha_composite(glyph)
    return out


def rot(points, deg, cx=64, cy=64):
    a = math.radians(deg)
    ca, sa = math.cos(a), math.sin(a)
    return [(cx + (x - cx) * ca - (y - cy) * sa, cy + (x - cx) * sa + (y - cy) * ca) for x, y in points]


W = (250, 250, 250, 255)
GOLD = hexrgb("#f2c447")
DARK = (30, 30, 40, 255)


def g_sword(d):
    blade = rot([(60, 18), (68, 18), (70, 82), (64, 92), (58, 82)], 45)
    d.polygon(blade, fill=(225, 232, 240, 255), outline=DARK)
    d.polygon(rot([(44, 82), (84, 82), (84, 90), (44, 90)], 45), fill=GOLD, outline=DARK)
    d.polygon(rot([(60, 90), (68, 90), (68, 108), (60, 108)], 45), fill=hexrgb("#8a5a34"), outline=DARK)


def g_bow(d):
    d.arc([22, 18, 86, 110], 300, 60, fill=hexrgb("#8a5a34"), width=9)
    d.line([(70, 23), (70, 105)], fill=W, width=2)
    d.line([(30, 64), (104, 64)], fill=(225, 225, 225, 255), width=5)
    d.polygon([(104, 56), (118, 64), (104, 72)], fill=(200, 210, 220, 255), outline=DARK)
    d.polygon([(30, 58), (40, 64), (30, 70), (22, 64)], fill=hexrgb("#b8323a"))


def g_bolt(d, col=(255, 240, 120, 255)):
    d.polygon([(72, 12), (36, 70), (60, 70), (48, 116), (94, 52), (68, 52), (84, 12)], fill=col, outline=DARK)


def g_flask(d, col=hexrgb("#9cff3a")):
    d.ellipse([28, 50, 100, 116], fill=col, outline=DARK, width=3)
    d.rectangle([54, 22, 74, 56], fill=(180, 230, 255, 255), outline=DARK, width=3)
    d.rectangle([50, 14, 78, 26], fill=hexrgb("#6b4a2e"), outline=DARK, width=2)
    d.ellipse([44, 66, 58, 80], fill=(255, 255, 255, 160))


def g_blades(d):
    for a in (0, 120, 240):
        blade = rot([(64, 14), (74, 40), (64, 50), (54, 40)], a)
        d.polygon(blade, fill=(225, 232, 240, 255), outline=DARK)
    d.ellipse([52, 52, 76, 76], fill=hexrgb("#c08aff"), outline=DARK, width=3)


def g_aura(d):
    d.ellipse([16, 16, 112, 112], outline=GOLD, width=8)
    d.ellipse([36, 36, 92, 92], outline=(255, 245, 190, 255), width=5)
    d.ellipse([56, 56, 72, 72], fill=W)


def g_up(d):
    d.polygon([(64, 14), (104, 60), (80, 60), (80, 112), (48, 112), (48, 60), (24, 60)], fill=hexrgb("#ff6a4a"), outline=DARK)


def g_wing(d):
    for i, ox in enumerate((0, 22, 44)):
        d.polygon([(22 + ox, 30), (52 + ox, 64), (22 + ox, 98), (34 + ox, 64)], fill=(160 + i * 30, 255, 200, 255), outline=DARK)


def g_heart(d, col=hexrgb("#e8303e")):
    d.ellipse([18, 26, 66, 74], fill=col)
    d.ellipse([62, 26, 110, 74], fill=col)
    d.polygon([(20, 58), (108, 58), (64, 110)], fill=col)
    d.ellipse([34, 38, 48, 52], fill=(255, 255, 255, 180))


def g_hourglass(d):
    d.polygon([(32, 18), (96, 18), (64, 64)], fill=(255, 220, 140, 255), outline=DARK)
    d.polygon([(64, 64), (96, 110), (32, 110)], fill=(255, 220, 140, 255), outline=DARK)
    d.rectangle([26, 12, 102, 20], fill=hexrgb("#6b4a2e"))
    d.rectangle([26, 108, 102, 116], fill=hexrgb("#6b4a2e"))


def g_expanse(d):
    for r, a in ((50, 120), (36, 190), (22, 255)):
        d.ellipse([64 - r, 64 - r, 64 + r, 64 + r], outline=(140, 210, 255, a), width=7)


def g_multishot(d):
    for a in (-25, 0, 25):
        shaft = rot([(62, 30), (66, 30), (66, 104), (62, 104)], a, 64, 104)
        head = rot([(54, 34), (64, 12), (74, 34)], a, 64, 104)
        d.polygon(shaft, fill=hexrgb("#d8c28a"), outline=DARK)
        d.polygon(head, fill=(220, 230, 240, 255), outline=DARK)


def g_magnet(d):
    d.arc([24, 20, 104, 100], 180, 360, fill=hexrgb("#d83a3a"), width=20)
    d.rectangle([24, 58, 44, 100], fill=hexrgb("#d83a3a"))
    d.rectangle([84, 58, 104, 100], fill=hexrgb("#d83a3a"))
    d.rectangle([24, 92, 44, 112], fill=(220, 225, 230, 255))
    d.rectangle([84, 92, 104, 112], fill=(220, 225, 230, 255))


def g_star(d):
    pts = []
    for i in range(10):
        r = 50 if i % 2 == 0 else 22
        a = math.radians(-90 + i * 36)
        pts.append((64 + math.cos(a) * r, 66 + math.sin(a) * r))
    d.polygon(pts, fill=(170, 230, 255, 255), outline=DARK)


def g_plus(d):
    d.rounded_rectangle([50, 18, 78, 110], radius=6, fill=hexrgb("#4aff8a"), outline=DARK, width=3)
    d.rounded_rectangle([18, 50, 110, 78], radius=6, fill=hexrgb("#4aff8a"), outline=DARK, width=3)


def g_shield(d):
    d.polygon([(64, 14), (104, 28), (100, 72), (64, 114), (28, 72), (24, 28)], fill=(190, 200, 215, 255), outline=DARK)
    d.polygon([(64, 26), (92, 36), (89, 70), (64, 100)], fill=(150, 162, 180, 255))


def g_coin(d):
    d.ellipse([22, 22, 106, 106], fill=GOLD, outline=DARK, width=3)
    d.ellipse([36, 36, 92, 92], outline=hexrgb("#b98a1e"), width=5)


def g_boomerang(d):
    d.polygon([(20, 40), (40, 24), (70, 70), (64, 80)], fill=hexrgb("#c8823a"), outline=DARK)
    d.polygon([(64, 80), (70, 70), (110, 60), (108, 80)], fill=hexrgb("#a86a2c"), outline=DARK)
    d.rectangle([60, 66, 74, 80], fill=GOLD, outline=DARK)


def g_meteor(d):
    for k, a in enumerate((0, 14, 28)):
        d.line([(20 + a, 20), (64 + a // 2, 64)], fill=(255, 160 - k * 30, 60, 255), width=10 - k * 2)
    d.ellipse([52, 52, 106, 106], fill=hexrgb("#5a4a44"), outline=DARK, width=3)
    d.ellipse([60, 60, 90, 90], fill=hexrgb("#ff8a2e"))
    d.ellipse([68, 66, 82, 80], fill=hexrgb("#fff2b0"))


def g_snowflake(d):
    c = (200, 240, 255, 255)
    for a in (0, 60, 120):
        p = rot([(60, 14), (68, 14), (68, 114), (60, 114)], a)
        d.polygon(p, fill=c, outline=DARK)
    for a in range(0, 360, 60):
        p = rot([(52, 24), (64, 34), (76, 24), (64, 40)], a)
        d.polygon(p, fill=(255, 255, 255, 255))


def g_dagger(d):
    blade = rot([(60, 10), (68, 10), (72, 80), (64, 92), (56, 80)], 35)
    d.polygon(blade, fill=hexrgb("#c08aff"), outline=DARK)
    d.polygon(rot([(46, 84), (82, 84), (82, 92), (46, 92)], 35), fill=GOLD, outline=DARK)
    d.polygon(rot([(60, 92), (68, 92), (68, 112), (60, 112)], 35), fill=hexrgb("#4e2a86"), outline=DARK)


def g_crosshair(d):
    d.ellipse([22, 22, 106, 106], outline=hexrgb("#ff4a4a"), width=8)
    d.ellipse([46, 46, 82, 82], outline=hexrgb("#ff4a4a"), width=6)
    d.rectangle([60, 10, 68, 40], fill=W)
    d.rectangle([60, 88, 68, 118], fill=W)
    d.rectangle([10, 60, 40, 68], fill=W)
    d.rectangle([88, 60, 118, 68], fill=W)


def g_burst(d):
    pts = []
    for i in range(16):
        r = 54 if i % 2 == 0 else 24
        a = math.radians(i * 22.5)
        pts.append((64 + math.cos(a) * r, 64 + math.sin(a) * r))
    d.polygon(pts, fill=hexrgb("#ff5a3a"), outline=DARK)
    d.ellipse([48, 48, 80, 80], fill=hexrgb("#ffd23a"))


def g_drop(d):
    d.polygon([(64, 12), (100, 70), (28, 70)], fill=hexrgb("#c8102e"), outline=DARK)
    d.ellipse([28, 44, 100, 112], fill=hexrgb("#c8102e"), outline=DARK, width=3)
    d.ellipse([44, 60, 58, 74], fill=(255, 255, 255, 170))


def g_feather(d):
    d.polygon([(30, 104), (96, 20), (104, 30), (40, 110)], fill=(240, 245, 255, 255), outline=DARK)
    for k in range(6):
        y = 30 + k * 12
        d.line([(100 - k * 10, y - 6), (72 - k * 10, y + 8)], fill=(170, 200, 240, 255), width=3)
    d.line([(26, 110), (100, 22)], fill=DARK, width=3)


def g_infinity(d):
    d.ellipse([14, 40, 66, 88], outline=hexrgb("#7ad8ff"), width=10)
    d.ellipse([62, 40, 114, 88], outline=hexrgb("#7ad8ff"), width=10)


def g_clover(d):
    g = hexrgb("#3ad86a")
    for (x, y) in ((40, 22), (68, 22), (40, 50), (68, 50)):
        d.ellipse([x - 4, y + 4, x + 28, y + 36], fill=g, outline=DARK, width=3)
    d.line([(64, 80), (80, 114)], fill=hexrgb("#2a8a4a"), width=7)

ICONS = {
    ("Weapons", "Icon_Greatsword"): (("#5a8cf0", "#1d2c5c"), g_sword),
    ("Weapons", "Icon_Longbow"): (("#6cc050", "#1f3c18"), g_bow),
    ("Weapons", "Icon_StormStaff"): (("#a070f0", "#2a1650"), g_bolt),
    ("Weapons", "Icon_PoisonFlask"): (("#f0a050", "#4c2810"), g_flask),
    ("Weapons", "Icon_OrbitingBlades"): (("#8890a8", "#262a38"), g_blades),
    ("Weapons", "Icon_HolyAura"): (("#f0d070", "#4c3a10"), g_aura),
    ("Weapons", "Icon_Boomerang"): (("#f0d070", "#4c3a10"), g_boomerang),
    ("Weapons", "Icon_MeteorStaff"): (("#f0d070", "#4c3a10"), g_meteor),
    ("Weapons", "Icon_FrostNova"): (("#f0d070", "#4c3a10"), g_snowflake),
    ("Weapons", "Icon_SpiritDaggers"): (("#f0d070", "#4c3a10"), g_dagger),
    ("Powerups", "Icon_Precision"): (("#f0d070", "#4c3a10"), g_crosshair),
    ("Powerups", "Icon_Brutality"): (("#f0d070", "#4c3a10"), g_burst),
    ("Powerups", "Icon_Vampirism"): (("#f0d070", "#4c3a10"), g_drop),
    ("Powerups", "Icon_Feather"): (("#f0d070", "#4c3a10"), g_feather),
    ("Powerups", "Icon_Persistence"): (("#f0d070", "#4c3a10"), g_infinity),
    ("Powerups", "Icon_Clover"): (("#f0d070", "#4c3a10"), g_clover),
    ("Powerups", "Icon_Might"): (("#f07050", "#4c1a10"), g_up),
    ("Powerups", "Icon_Swiftness"): (("#50e0b0", "#104c3a"), g_wing),
    ("Powerups", "Icon_Vitality"): (("#f05070", "#4c1020"), g_heart),
    ("Powerups", "Icon_Haste"): (("#f0c050", "#4c3810"), g_hourglass),
    ("Powerups", "Icon_Expanse"): (("#50a0f0", "#10284c"), g_expanse),
    ("Powerups", "Icon_Multishot"): (("#c0a070", "#3c2c14"), g_multishot),
    ("Powerups", "Icon_Magnet"): (("#e06060", "#3c1414"), g_magnet),
    ("Powerups", "Icon_Wisdom"): (("#70c0f0", "#14304c"), g_star),
    ("Powerups", "Icon_Regeneration"): (("#50f080", "#104c20"), g_plus),
    ("Powerups", "Icon_Armor"): (("#a0a8b8", "#2a2e38"), g_shield),
    ("Powerups", "Icon_Gold"): (("#f0d050", "#4c3c10"), g_coin),
    ("Powerups", "Icon_Heal"): (("#f07080", "#4c1020"), lambda d: g_heart(d, hexrgb("#ff8a9a"))),
}


def icons():
    # Megabonk-style item icons: just the item, pixelated with a dark outline (the UI supplies the colored backing)
    for (folder, name), ((c1, c2), fn) in ICONS.items():
        gl = glyph_layer()
        fn(ImageDraw.Draw(gl))
        save(pixelate_icon(gl, 32), "UI", "Icons", folder, name + ".png")


def pixelate_portraits():
    """Character portraits (rendered by Blender) -> 48px pixel art."""
    d = os.path.join(GAME, "UI", "Icons", "Characters")
    if not os.path.isdir(d):
        return
    for f in os.listdir(d):
        if f.startswith("Portrait_") and f.endswith(".png"):
            p = os.path.join(d, f)
            img = Image.open(p).convert("RGBA")
            if img.width <= 64:
                continue
            small = img.resize((48, 48), Image.BOX)
            arr = np.array(small)
            arr[..., 3] = np.where(arr[..., 3] > 100, 255, 0)
            Image.fromarray(arr, "RGBA").save(p)
            print("pixelated", f)


if __name__ == "__main__":
    import sys
    only = sys.argv[1:] or ["palette", "detail", "terrain", "vfx", "ui", "icons", "portraits", "volcano"]
    if "palette" in only: palette()
    if "detail" in only: detail_atlas()
    if "terrain" in only: terrain_textures()
    if "vfx" in only: vfx()
    if "ui" in only: ui_sprites()
    if "icons" in only: icons()
    if "portraits" in only: pixelate_portraits()
    if "volcano" in only: volcano_textures()