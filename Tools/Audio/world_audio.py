"""
World pass audio: movement feedback (footsteps, landing, bounce pads), smashing props, Frostfall Peaks enemies,
looping map ambiences and the Frostfall music.

  python Tools/Audio/world_audio.py          (everything)
  python Tools/Audio/world_audio.py sfx|amb|music
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_audio as ga  # noqa: E402
from generate_audio import SR, env, sine, noise, lowpass, highpass, bandpass, sweep, mix, delay, tri, square  # noqa: E402

rng = np.random.default_rng(77)


def n_(d):
    return int(SR * d)


# ----------------------------------------------------------------------------- movement

def footstep():
    d = 0.09
    x = lowpass(noise(d), 900) * env(n_(d), a=0.002, d=0.05) + sine(sweep(140, 70, d), d) * env(n_(d), a=0.001, d=0.04) * 0.6
    return x


def land():
    d = 0.35
    thump = sine(sweep(120, 45, d, 0.5), d) * env(n_(d), a=0.001, d=0.18)
    dust = lowpass(noise(d), 1400) * env(n_(d), a=0.002, d=0.12) * 0.6
    return mix(thump, dust)


def bounce():
    """Cartoon boing: rising pitch with a wobble + a springy pluck."""
    d = 0.55
    t = np.arange(n_(d)) / SR
    f = 180 + 520 * (1 - np.exp(-t * 9)) + 40 * np.sin(t * 2 * np.pi * 18) * np.exp(-t * 4)
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = (np.sin(ph) + 0.35 * np.sin(2 * ph)) * env(n_(d), a=0.004, d=0.42)
    whoosh = bandpass(noise(d), 800, 4000) * env(n_(d), a=0.06, d=0.3) * 0.25
    return mix(body, whoosh)


def smash():
    """Clay pot / pumpkin smash: crack, crunchy debris and a few clinks."""
    d = 0.6
    crack = highpass(noise(0.05), 1500) * env(n_(0.05), a=0.0005, d=0.03)
    crunch = bandpass(noise(d), 300, 3000) * env(n_(d), a=0.001, d=0.16)
    out = mix(ga.pad(crack, d) * 1.2, crunch * 0.8, sine(sweep(220, 80, d, 0.4), d) * env(n_(d), a=0.001, d=0.08) * 0.5)
    for k in range(5):
        f = rng.uniform(1800, 4200)
        c = sine(f, 0.12) * env(n_(0.12), a=0.001, d=0.05) * 0.25
        out = mix(out, ga.pad(delay(c, rng.uniform(0.05, 0.35)), d))
    return out


# ----------------------------------------------------------------------------- frost enemies

def wolf_howl():
    d = 1.2
    t = np.arange(n_(d)) / SR
    f = 380 + 260 * np.sin(np.clip(t / d, 0, 1) * np.pi) ** 0.7 + 6 * np.sin(t * 2 * np.pi * 6)
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = (np.sin(ph) + 0.4 * np.sin(2 * ph) + 0.15 * np.sin(3 * ph)) * env(n_(d), a=0.15, d=0.3, s=0.7, r=0.4, total=n_(d))
    breath = bandpass(noise(d), 800, 2500) * 0.15 * env(n_(d), a=0.2, d=0.5)
    return mix(x, breath)


def wolf_bite():
    d = 0.22
    snap = highpass(noise(0.04), 2000) * env(n_(0.04), a=0.0005, d=0.02)
    growl = lowpass(square(95, d) * (0.6 + 0.4 * np.sin(np.arange(n_(d)) / SR * 2 * np.pi * 30)), 900) * env(n_(d), a=0.01, d=0.15) * 0.6
    return mix(ga.pad(snap, d), growl)


def wolf_death():
    d = 0.45
    t = np.arange(n_(d)) / SR
    f = 900 * np.exp(-t * 3.5) + 250
    ph = 2 * np.pi * np.cumsum(f) / SR
    return (np.sin(ph) + 0.3 * np.sin(2 * ph)) * env(n_(d), a=0.005, d=0.35) + bandpass(noise(d), 1000, 3000) * env(n_(d), a=0.001, d=0.1) * 0.3


def yeti_roar():
    d = 1.1
    t = np.arange(n_(d)) / SR
    f = 85 + 30 * np.sin(np.clip(t / d, 0, 1) * np.pi)
    ph = 2 * np.pi * np.cumsum(f) / SR
    buzz = lowpass(np.sign(np.sin(ph)) * 0.6 + np.sin(ph * 2) * 0.4, 1200)
    gr = bandpass(noise(d), 200, 1600) * 0.8
    x = (buzz + gr) * env(n_(d), a=0.08, d=0.2, s=0.8, r=0.5, total=n_(d))
    return np.tanh(x * 2.0)


def yeti_hit():
    d = 0.18
    return mix(lowpass(noise(d), 700) * env(n_(d), a=0.001, d=0.1), sine(sweep(110, 60, d), d) * env(n_(d), a=0.001, d=0.12) * 0.8)


def snow_crunch():
    d = 0.16
    x = noise(d)
    grains = (rng.random(n_(d)) < 0.08) * rng.uniform(-1, 1, n_(d))
    return mix(bandpass(x, 1200, 6000) * env(n_(d), a=0.002, d=0.1) * 0.6, highpass(grains, 2000) * env(n_(d), a=0.001, d=0.12))


def ice_shatter():
    """Snowman pop: icy burst with shimmering shards."""
    d = 1.0
    boom = sine(sweep(160, 40, 0.5, 0.5), 0.5) * env(n_(0.5), a=0.001, d=0.25)
    hiss = highpass(noise(d), 3000) * env(n_(d), a=0.001, d=0.35) * 0.5
    out = mix(ga.pad(boom, d), hiss)
    for k in range(12):
        f = rng.uniform(2200, 6500)
        c = (sine(f, 0.4) + 0.4 * sine(f * 1.51, 0.4)) * env(n_(0.4), a=0.001, d=0.2) * 0.18
        out = mix(out, ga.pad(delay(c, rng.uniform(0.0, 0.5)), d))
    return out


# ----------------------------------------------------------------------------- ambiences (stereo, seamless ~24 s loops)

def loopify(x, fade=2.0):
    """Crossfade the tail into the head so the loop has no seam."""
    f = n_(fade)
    head, tail = x[:f].copy(), x[-f:]
    w = np.linspace(0, 1, f)
    x = x[:-f].copy()
    x[:f] = head * w + tail * (1 - w)
    return x


def wind(d, base=400, gust=0.6, seed=1):
    r = np.random.default_rng(seed)
    t = np.arange(n_(d)) / SR
    lfo = 0.5 + 0.5 * np.sin(2 * np.pi * (t / 7.0 + r.random())) * np.sin(2 * np.pi * (t / 3.1 + r.random()))
    w = lowpass(r.uniform(-1, 1, n_(d)), base) * (0.35 + gust * lfo)
    whistle = bandpass(r.uniform(-1, 1, n_(d)), base * 2.2, base * 2.6) * (lfo ** 3) * 0.6
    return w + whistle


def amb_keep():
    d = 26.0
    L = wind(d, 350, 0.5, 1) * 0.5
    R = wind(d, 360, 0.5, 2) * 0.5
    # crickets: chirp trains
    for k in range(70):
        at = rng.uniform(0, d - 0.5)
        f = rng.uniform(3800, 4600)
        ch = sine(f, 0.25) * (np.sin(np.arange(n_(0.25)) / SR * 2 * np.pi * 28) > 0.2) * env(n_(0.25), a=0.01, d=0.2) * 0.05
        tgt = L if k % 2 else R
        i = n_(at)
        tgt[i:i + len(ch)] += ch[: len(tgt) - i]
    # distant owl hoots
    for at in (5.0, 6.0, 17.5, 18.3):
        h = (sine(sweep(420, 380, 0.45), 0.45) + 0.2 * sine(840, 0.45)) * env(n_(0.45), a=0.06, d=0.3) * 0.12
        h = lowpass(h, 1200)
        i = n_(at)
        L[i:i + len(h)] += h * 0.6
        R[i:i + len(h)] += h
    return loopify(L), loopify(R)


def amb_volcano():
    d = 26.0
    r = np.random.default_rng(5)
    t = np.arange(n_(d)) / SR
    rumble = lowpass(r.uniform(-1, 1, n_(d)), 90) * (0.8 + 0.3 * np.sin(2 * np.pi * t / 9.0))
    L, R = rumble.copy(), rumble.copy() * 0.95
    L += lowpass(r.uniform(-1, 1, n_(d)), 600) * 0.15
    R += lowpass(r.uniform(-1, 1, n_(d)), 600) * 0.15
    # crackles and lava bubbles
    for k in range(260):
        at = r.uniform(0, d - 0.2)
        if k % 4 == 0:
            bub = sine(sweep(r.uniform(120, 220), r.uniform(300, 500), 0.12), 0.12) * env(n_(0.12), a=0.01, d=0.08) * 0.25
        else:
            bub = highpass(r.uniform(-1, 1, n_(0.02)), 2500) * env(n_(0.02), a=0.0005, d=0.01) * r.uniform(0.1, 0.35)
        tgt = L if r.random() < 0.5 else R
        i = n_(at)
        tgt[i:i + len(bub)] += bub[: len(tgt) - i]
    return loopify(L), loopify(R)


def amb_frost():
    d = 26.0
    L = wind(d, 520, 1.0, 11) * 0.7
    R = wind(d, 540, 1.0, 12) * 0.7
    # ice creaks and tinkles
    r = np.random.default_rng(9)
    for k in range(24):
        at = r.uniform(0, d - 1.0)
        if k % 3 == 0:
            cr = lowpass(square(r.uniform(60, 110), 0.5) * (np.sin(np.arange(n_(0.5)) / SR * 2 * np.pi * r.uniform(15, 30)) > 0), 600) \
                * env(n_(0.5), a=0.1, d=0.35) * 0.05
        else:
            f = r.uniform(2500, 5000)
            cr = (sine(f, 0.6) + 0.3 * sine(f * 2.7, 0.6)) * env(n_(0.6), a=0.001, d=0.4) * 0.03
        tgt = L if r.random() < 0.5 else R
        i = n_(at)
        tgt[i:i + len(cr)] += cr[: len(tgt) - i]
    return loopify(L), loopify(R)


SFX = {
    "Player": [("SFX_Footstep", footstep), ("SFX_Land", land), ("SFX_Bounce", bounce)],
    "Pickups": [("SFX_Smash", smash)],
    "Enemies": [("SFX_WolfHowl", wolf_howl), ("SFX_WolfBite", wolf_bite), ("SFX_WolfDeath", wolf_death),
                ("SFX_YetiRoar", yeti_roar), ("SFX_YetiHit", yeti_hit), ("SFX_SnowCrunch", snow_crunch), ("SFX_IceShatter", ice_shatter)],
}

AMB = [("AMB_Keep", amb_keep, 0.7), ("AMB_Volcano", amb_volcano, 0.75), ("AMB_Frost", amb_frost, 0.75)]

if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    if what in ("all", "sfx"):
        ga.MIX_DB.update({"SFX_Footstep": -8, "SFX_Land": -4, "SFX_SnowCrunch": -4, "SFX_WolfHowl": -3})
        for cat, items in SFX.items():
            for name, fn in items:
                ga.write(fn(), os.path.join("SFX", cat), name)
    if what in ("all", "amb"):
        for name, fn, peak in AMB:
            l, r = fn()
            ga.write_stereo(l, r, "Ambience", name, peak=peak)
    if what in ("all", "music"):
        import music_v2
        l, r = music_v2.frost_theme()
        ga.write_stereo(l, r, "Music", "MUS_Frost", peak=0.85)
