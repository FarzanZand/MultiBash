"""
MultiBash procedural audio generator (SFX + music), pure numpy.

  python Tools/Audio/generate_audio.py            # everything
  python Tools/Audio/generate_audio.py sfx        # only SFX
  python Tools/Audio/generate_audio.py music      # only music

Writes 16-bit 44.1 kHz WAVs into Assets/_Game/Audio/{SFX/<Category>,Music}/.
Each sound is a small function below; tweak numbers and re-run to iterate on the feel.
"""
import os
import sys
import wave

import numpy as np

SR = 44100
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
AUDIO = os.path.join(ROOT, "Assets", "_Game", "Audio")
rng = np.random.default_rng(1234)


# ----------------------------------------------------------------------------- primitives

def t_(dur):
    return np.arange(int(SR * dur)) / SR


def env(n, a=0.005, d=0.1, s=0.0, r=0.0, total=None):
    """Simple attack/decay(exp) envelope of length n samples."""
    t = np.arange(n) / SR
    e = np.minimum(1.0, t / max(a, 1e-4))
    e *= np.exp(-np.maximum(0, t - a) / max(d, 1e-4)) * (1 - s) + s
    if r > 0:
        rel = int(r * SR)
        e[-rel:] *= np.linspace(1, 0, rel)
    return e


def sine(freq, dur, phase=0.0):
    t = t_(dur)
    if np.isscalar(freq):
        return np.sin(2 * np.pi * freq * t + phase)
    return np.sin(2 * np.pi * np.cumsum(freq) / SR + phase)


def saw(freq, dur):
    t = t_(dur)
    ph = np.cumsum(np.full(len(t), freq) if np.isscalar(freq) else freq) / SR
    return 2 * (ph % 1.0) - 1


def square(freq, dur, duty=0.5):
    t = t_(dur)
    ph = np.cumsum(np.full(len(t), freq) if np.isscalar(freq) else freq) / SR
    return np.where((ph % 1.0) < duty, 1.0, -1.0)


def tri(freq, dur):
    return 2 * np.abs(saw(freq, dur)) - 1


def noise(dur):
    return rng.uniform(-1, 1, int(SR * dur))


def lowpass(x, cutoff):
    """One-pole lowpass; cutoff may be an array (sweeps)."""
    if np.isscalar(cutoff):
        from scipy.signal import lfilter
        a = 1 - np.exp(-2 * np.pi * cutoff / SR)
        return lfilter([a], [1, -(1 - a)], x)
    c = np.broadcast_to(np.asarray(cutoff, dtype=float), x.shape)
    a = 1 - np.exp(-2 * np.pi * c / SR)
    y = np.zeros_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc += a[i] * (x[i] - acc)
        y[i] = acc
    return y


def highpass(x, cutoff):
    return x - lowpass(x, cutoff)


def bandpass(x, lo, hi):
    return lowpass(highpass(x, lo), hi)


def sweep(f0, f1, dur, curve=1.0):
    n = int(SR * dur)
    k = np.linspace(0, 1, n) ** curve
    return f0 * (f1 / f0) ** k


def pad(x, dur):
    n = int(SR * dur)
    return np.pad(x, (0, max(0, n - len(x))))[:n] if len(x) < n else x


def mix(*parts):
    n = max(len(p) for p in parts)
    out = np.zeros(n)
    for p in parts:
        out[: len(p)] += p
    return out


def delay(x, at):
    return np.concatenate([np.zeros(int(at * SR)), x])


def norm(x, peak=0.9):
    m = np.max(np.abs(x))
    return x if m == 0 else x / m * peak


def fade_out(x, dur=0.01):
    n = min(len(x), int(dur * SR))
    x = x.copy()
    x[-n:] *= np.linspace(1, 0, n)
    return x


def pluck(freq, dur, damp=0.996):
    """Karplus-Strong plucked string."""
    n = int(SR * dur)
    p = max(2, int(SR / freq))
    buf = rng.uniform(-1, 1, p)
    out = np.zeros(n)
    for i in range(n):
        out[i] = buf[i % p]
        buf[i % p] = damp * 0.5 * (buf[i % p] + buf[(i + 1) % p])
    return out


def write(x, folder, name, peak=0.9):
    x = fade_out(norm(np.asarray(x, dtype=float), peak))
    path = os.path.join(AUDIO, folder, name + ".wav")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = (np.clip(x, -1, 1) * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())
    print("wrote", os.path.relpath(path, ROOT), f"{len(x) / SR:.2f}s")


def write_stereo(l, r, folder, name, peak=0.85):
    m = max(np.max(np.abs(l)), np.max(np.abs(r)))
    l, r = l / m * peak, r / m * peak
    path = os.path.join(AUDIO, folder, name + ".wav")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = np.empty(len(l) * 2, np.int16)
    data[0::2] = (np.clip(l, -1, 1) * 32767).astype(np.int16)
    data[1::2] = (np.clip(r, -1, 1) * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())
    print("wrote", os.path.relpath(path, ROOT), f"{len(l) / SR:.2f}s")


# ----------------------------------------------------------------------------- SFX

def sword_swing():
    d = 0.28
    n = noise(d)
    x = lowpass(n, sweep(600, 4000, d, 0.6)) * env(len(n), a=0.06, d=0.08)
    return x + 0.3 * sine(sweep(320, 140, d), d) * env(len(n), a=0.02, d=0.06)


def bow_shot():
    s = pluck(196, 0.35, 0.990) * env(int(SR * 0.35), a=0.001, d=0.12)
    w = lowpass(noise(0.2), sweep(3000, 800, 0.2)) * env(int(SR * 0.2), a=0.01, d=0.05)
    return mix(s, 0.5 * w)


def lightning_zap():
    d = 0.45
    n = len(t_(d))
    crack = noise(d) * (rng.random(n) > 0.6) * env(n, a=0.001, d=0.12)
    buzz = saw(sweep(1600, 120, d, 0.4), d) * env(n, a=0.001, d=0.10)
    rumble = lowpass(noise(d), 300) * env(n, a=0.01, d=0.2) * 2.5
    return highpass(crack, 900) * 0.8 + 0.5 * buzz + rumble


def flask_throw():
    d = 0.25
    return lowpass(noise(d), sweep(1200, 2500, d)) * env(int(SR * d), a=0.08, d=0.06)


def flask_shatter():
    parts = [highpass(noise(0.08), 3000) * env(int(SR * 0.08), a=0.001, d=0.02)]
    for i in range(7):
        f = rng.uniform(2500, 6000)
        parts.append(delay(sine(f, 0.18) * env(int(SR * 0.18), a=0.001, d=0.04) * 0.4, rng.uniform(0, 0.12)))
    bubble = sine(sweep(300, 900, 0.3), 0.3) * env(int(SR * 0.3), a=0.01, d=0.1) * 0.4
    return mix(*parts, delay(bubble, 0.05))


def blade_hit():
    d = 0.18
    n = int(SR * d)
    return (sine(2400, d) + 0.6 * sine(3700, d) + 0.3 * sine(5200, d)) * env(n, a=0.001, d=0.04) + highpass(noise(d), 4000) * env(n, a=0.001, d=0.01)


def aura_pulse():
    d = 0.6
    n = int(SR * d)
    return (sine(523, d) + sine(784, d) * 0.6 + sine(1046, d) * 0.3) * env(n, a=0.05, d=0.2) * 0.6


def bone_hit():
    d = 0.12
    n = int(SR * d)
    x = bandpass(noise(d), 800, 3500) * env(n, a=0.001, d=0.02)
    return x + sine(sweep(900, 400, d), d) * env(n, a=0.001, d=0.03) * 0.5


def skeleton_death():
    parts = []
    for i in range(6):
        parts.append(delay(bone_hit() * rng.uniform(0.4, 1.0), i * rng.uniform(0.04, 0.07)))
    thud = lowpass(noise(0.25), 200) * env(int(SR * 0.25), a=0.001, d=0.08) * 2
    return mix(*parts, delay(thud, 0.22))


def slime_hit():
    d = 0.2
    n = int(SR * d)
    return sine(sweep(420, 160, d), d) * env(n, a=0.002, d=0.06) + lowpass(noise(d), 900) * env(n, a=0.002, d=0.03) * 0.6


def slime_death():
    d = 0.45
    n = int(SR * d)
    splat = lowpass(noise(d), sweep(2000, 200, d)) * env(n, a=0.001, d=0.1)
    gloop = sine(sweep(260, 70, d, 0.5), d) * env(n, a=0.005, d=0.15)
    drips = [delay(sine(sweep(700, 1200, 0.06), 0.06) * env(int(SR * 0.06), a=0.002, d=0.02) * 0.3, 0.15 + i * 0.07) for i in range(3)]
    return mix(splat, gloop, *drips)


def slime_hop():
    d = 0.22
    n = int(SR * d)
    return sine(sweep(180, 520, d, 0.7), d) * env(n, a=0.005, d=0.08)


def player_hurt():
    d = 0.3
    n = int(SR * d)
    return lowpass(noise(d), 500) * env(n, a=0.001, d=0.06) * 1.5 + square(sweep(220, 90, d), d, 0.3) * env(n, a=0.001, d=0.08) * 0.4


def player_jump():
    d = 0.18
    n = int(SR * d)
    return square(sweep(260, 620, d), d, 0.25) * env(n, a=0.002, d=0.06) * 0.5 + lowpass(noise(d), 1500) * env(n, a=0.002, d=0.03) * 0.3


def player_slide():
    d = 0.4
    n = int(SR * d)
    return bandpass(noise(d), 300, 2500) * env(n, a=0.03, d=0.2)


def player_downed():
    d = 0.9
    n = int(SR * d)
    return (tri(sweep(440, 110, d), d) + 0.5 * tri(sweep(330, 82, d), d)) * env(n, a=0.01, d=0.4)


def player_revive():
    notes = [523, 659, 784, 1046]
    return mix(*[delay(sine(f, 0.25) * env(int(SR * 0.25), a=0.005, d=0.1), i * 0.07) for i, f in enumerate(notes)])


def level_up():
    notes = [523, 659, 784, 1046, 1318]
    parts = [delay((sine(f, 0.4) + 0.4 * tri(f * 2, 0.4)) * env(int(SR * 0.4), a=0.005, d=0.15), i * 0.06) for i, f in enumerate(notes)]
    shimmer = highpass(noise(0.6), 6000) * env(int(SR * 0.6), a=0.05, d=0.2) * 0.15
    return mix(*parts, delay(shimmer, 0.2))


def gem_pickup():
    d = 0.12
    n = int(SR * d)
    return (sine(1568, d) + 0.5 * sine(2349, d)) * env(n, a=0.001, d=0.04)


def health_pickup():
    return mix(*[delay(sine(f, 0.3) * env(int(SR * 0.3), a=0.01, d=0.12), i * 0.09) for i, f in enumerate([392, 523, 659])])


def magnet_pickup():
    d = 0.7
    n = int(SR * d)
    return sine(sweep(200, 1600, d, 2.0), d) * env(n, a=0.3, d=0.2) + 0.3 * square(sweep(100, 800, d, 2), d) * env(n, a=0.3, d=0.2)


def chest_open():
    creak = bandpass(saw(sweep(90, 140, 0.3), 0.3), 200, 1200) * env(int(SR * 0.3), a=0.05, d=0.2) * 0.5
    fan = mix(*[delay((sine(f, 0.5) + 0.3 * square(f, 0.5)) * env(int(SR * 0.5), a=0.005, d=0.2), 0.25 + i * 0.1)
                for i, f in enumerate([523, 659, 784, 1046])])
    return mix(creak, fan)


def ui_click():
    d = 0.06
    n = int(SR * d)
    return sine(sweep(1200, 700, d), d) * env(n, a=0.001, d=0.015)


def ui_hover():
    d = 0.04
    n = int(SR * d)
    return sine(1800, d) * env(n, a=0.001, d=0.01) * 0.5


def ui_ready():
    return mix(sine(660, 0.15) * env(int(SR * 0.15), a=0.002, d=0.05), delay(sine(990, 0.2) * env(int(SR * 0.2), a=0.002, d=0.07), 0.08))


def ui_start():
    whoosh = lowpass(noise(0.8), sweep(300, 6000, 0.8, 2)) * env(int(SR * 0.8), a=0.6, d=0.1)
    chord = mix(*[(saw(f, 1.0) * 0.3 + sine(f, 1.0)) * env(int(SR * 1.0), a=0.01, d=0.4) for f in (220, 277, 330, 440)])
    return mix(whoosh, delay(lowpass(chord, 3000), 0.7))


def victory():
    seq = [(523, 0.15), (659, 0.15), (784, 0.15), (1046, 0.5), (784, 0.15), (1046, 0.9)]
    parts, t = [], 0.0
    for f, d in seq:
        parts.append(delay((sine(f, d + 0.3) + 0.4 * square(f, d + 0.3, 0.25)) * env(int(SR * (d + 0.3)), a=0.005, d=d), t))
        t += d
    return mix(*parts)


def defeat():
    seq = [(392, 0.35), (370, 0.35), (349, 0.35), (262, 1.2)]
    parts, t = [], 0.0
    for f, d in seq:
        parts.append(delay((tri(f, d + 0.3) + 0.3 * saw(f / 2, d + 0.3)) * env(int(SR * (d + 0.3)), a=0.01, d=d), t))
        t += d
    return lowpass(mix(*parts), 2500)


def bat_screech():
    d = 0.22
    n = int(SR * d)
    return (square(sweep(2600, 1800, d), d, 0.3) * 0.4 + sine(sweep(3200, 2400, d), d)) * env(n, a=0.005, d=0.06) * 0.6


def bat_death():
    d = 0.35
    n = int(SR * d)
    return sine(sweep(2400, 600, d), d) * env(n, a=0.002, d=0.12) * 0.6 + highpass(noise(d), 2000) * env(n, a=0.001, d=0.04) * 0.4


def golem_stomp():
    d = 0.9
    n = int(SR * d)
    boom = sine(sweep(90, 32, d, 0.5), d) * env(n, a=0.002, d=0.35) * 1.5
    crack = lowpass(noise(d), sweep(3000, 200, d)) * env(n, a=0.001, d=0.12)
    rubble = [delay(bandpass(noise(0.08), 400, 2000) * env(int(SR * 0.08), a=0.001, d=0.02) * 0.5, 0.1 + i * 0.06) for i in range(6)]
    return mix(boom, crack, *rubble)


def rock_hit():
    d = 0.14
    n = int(SR * d)
    return bandpass(noise(d), 300, 1800) * env(n, a=0.001, d=0.03) + sine(sweep(220, 120, d), d) * env(n, a=0.001, d=0.04) * 0.6


def explosion():
    d = 1.1
    n = int(SR * d)
    body = lowpass(noise(d), sweep(5000, 120, d, 0.4)) * env(n, a=0.002, d=0.35) * 1.4
    thump = sine(sweep(120, 35, d, 0.4), d) * env(n, a=0.002, d=0.3) * 1.4
    crackle = noise(d) * (rng.random(n) > 0.97) * env(n, a=0.05, d=0.4) * 0.5
    return mix(body, thump, crackle)


def fuse_hiss():
    d = 0.8
    n = int(SR * d)
    return highpass(noise(d), 4000) * env(n, a=0.05, d=0.6, s=0.6) * 0.4 * (1 + 0.5 * np.sin(np.arange(n) / SR * 60))


def enemy_arrow():
    d = 0.3
    n = int(SR * d)
    return pluck(330, d, 0.985) * env(n, a=0.001, d=0.08) * 0.6 + lowpass(noise(d), sweep(2500, 600, d)) * env(n, a=0.01, d=0.05) * 0.4


def boomerang_whoosh():
    d = 0.5
    n = int(SR * d)
    wob = 0.6 + 0.4 * np.sin(np.arange(n) / SR * 2 * np.pi * 14)
    return bandpass(noise(d), 500, sweep(1500, 3500, d)) * env(n, a=0.08, d=0.25) * wob


def meteor_cast():
    d = 0.7
    n = int(SR * d)
    return lowpass(noise(d), sweep(400, 3000, d, 2)) * env(n, a=0.4, d=0.15) + sine(sweep(200, 700, d, 2), d) * env(n, a=0.4, d=0.1) * 0.3


def frost_nova():
    d = 0.8
    n = int(SR * d)
    chimes = mix(*[delay(sine(f, 0.5) * env(int(SR * 0.5), a=0.002, d=0.15) * 0.4, k * 0.03) for k, f in enumerate([1568, 2093, 2637, 3136])])
    crack = highpass(noise(d), 3000) * env(n, a=0.001, d=0.08)
    whoosh = lowpass(noise(d), sweep(6000, 1500, d)) * env(n, a=0.01, d=0.25) * 0.5
    return mix(chimes, crack, whoosh)


def dagger_cast():
    d = 0.35
    n = int(SR * d)
    return (sine(sweep(800, 1600, d), d) + 0.5 * sine(sweep(1200, 2400, d), d)) * env(n, a=0.01, d=0.12) * 0.6 + highpass(noise(d), 5000) * env(n, a=0.01, d=0.08) * 0.2


def shrine_charge():
    d = 1.2
    n = int(SR * d)
    return mix(*[delay((sine(f, 0.9) + 0.3 * sine(f * 2, 0.9)) * env(int(SR * 0.9), a=0.01, d=0.4) * 0.5, k * 0.09) for k, f in enumerate([392, 523, 659, 784, 1046, 1318])])


# ----------------------------------------------------------------------------- volcano level

def imp_cackle():
    d = 0.4
    n = int(SR * d)
    trem = 0.5 + 0.5 * np.sign(np.sin(np.arange(n) / SR * 2 * np.pi * 14))
    v = square(sweep(700, 950, d), d, 0.3) * 0.5 + saw(sweep(1400, 1800, d), d) * 0.25
    return bandpass(v, 500, 3500) * trem * env(n, a=0.01, d=0.18) * 0.7


def imp_death():
    d = 0.45
    n = int(SR * d)
    squeal = square(sweep(1200, 300, d), d, 0.3) * env(n, a=0.002, d=0.15) * 0.5
    poof = lowpass(noise(d), sweep(4000, 300, d)) * env(n, a=0.002, d=0.12) * 0.6
    return mix(squeal, poof)


def fireball_cast():
    d = 0.5
    n = int(SR * d)
    whoosh = bandpass(noise(d), 300, 3000) * env(n, a=0.04, d=0.2) * 0.7
    roar = lowpass(saw(sweep(110, 70, d), d), 600) * env(n, a=0.02, d=0.2) * 0.4
    crackle = noise(d) * (rng.random(n) > 0.985) * env(n, a=0.02, d=0.3) * 0.5
    return mix(whoosh, roar, crackle)


def magma_hit():
    d = 0.2
    n = int(SR * d)
    return lowpass(noise(d), 1800) * env(n, a=0.001, d=0.05) * 0.8 + sine(sweep(180, 80, d), d) * env(n, a=0.001, d=0.06) * 0.6


def magma_death():
    d = 0.7
    n = int(SR * d)
    splat = lowpass(noise(d), sweep(2500, 200, d)) * env(n, a=0.002, d=0.15) * 0.9
    sizzle = highpass(noise(d), 3500) * env(n, a=0.05, d=0.4) * 0.35
    bloop = sine(sweep(260, 70, d, 0.5), d) * env(n, a=0.002, d=0.2) * 0.7
    return mix(splat, sizzle, bloop)


def lava_sizzle():
    d = 0.5
    n = int(SR * d)
    pops = noise(d) * (rng.random(n) > 0.96) * 0.8
    return mix(highpass(noise(d), 2500) * 0.4, pops) * env(n, a=0.02, d=0.25)


def volcano_theme():
    """Heavier battle loop: D phrygian, chugging distorted bass, toms, ominous choir pad."""
    bpm = 138
    beat = 60 / bpm
    bars = 16
    dur = bars * 4 * beat
    L = np.zeros(int(SR * dur) + SR)
    R = np.zeros_like(L)
    prog = [(50, [50, 53, 57]), (51, [51, 55, 58]), (50, [50, 53, 57]), (48, [48, 52, 55])]   # Dm  Eb  Dm  C
    k, s, hc = kick(), snare(), hat()

    def tom(f):
        dd = 0.3
        nn = int(SR * dd)
        return sine(sweep(f, f * 0.55, dd, 0.4), dd) * env(nn, a=0.001, d=0.12) * 0.9

    lead = [74, 75, 74, 72, 70, 69, 70, 72, 74, 77, 75, 74, 72, 70, 69, 70]
    for bar in range(bars):
        root, chord = prog[bar % 4]
        t0 = bar * 4 * beat
        hype = bar >= 8
        for b in range(4):
            place(L, k, t0 + b * beat); place(R, k, t0 + b * beat)
            if b in (1, 3):
                place(L, s, t0 + b * beat); place(R, s, t0 + b * beat)
            for h in range(2):
                place(L, hc * 0.6, t0 + (b + h * 0.5) * beat); place(R, hc * 0.8, t0 + (b + h * 0.5) * beat)
        if bar % 4 == 3:   # tom fill
            for i, f in enumerate([220, 180, 150, 120, 100, 85]):
                place(L, tom(f) * (0.9 if i % 2 else 0.6), t0 + 3 * beat + i * beat / 6)
                place(R, tom(f) * (0.6 if i % 2 else 0.9), t0 + 3 * beat + i * beat / 6)
        # palm-muted 16th chug (distorted saw, clipped)
        for e in range(16):
            if e % 8 in (3, 6):
                continue
            nd = beat / 4
            f = midi(root - 12)
            note = np.tanh(lowpass(saw(f, nd) + saw(f * 1.5, nd) * 0.5, 1100) * 3) * env(int(SR * nd), a=0.002, d=0.05)
            place(L, note * 0.22, t0 + e * nd); place(R, note * 0.22, t0 + e * nd + 0.004)
        # choir-ish pad
        padn = sum(lowpass(tri(midi(n)) if False else tri(midi(n), 4 * beat) + tri(midi(n) * 1.006, 4 * beat), 1200) for n in chord)
        padn *= env(len(padn), a=0.5, d=3.0, s=0.5) * 0.09
        place(L, padn, t0); place(R, padn * 0.95, t0 + 0.012)
        if hype:
            for e in range(4):
                n = lead[(bar % 4) * 4 + e]
                nd = beat
                ld = np.tanh((saw(midi(n), nd) + saw(midi(n) * 1.004, nd)) * 1.5)
                ld = lowpass(ld, 2400) * env(int(SR * nd), a=0.01, d=0.4, s=0.35) * 0.12
                place(L, ld, t0 + e * nd); place(R, ld, t0 + e * nd + 0.01)
    n = int(SR * dur)
    return L[:n], R[:n]


SFX = {
    "Weapons": [("SFX_SwordSwing", sword_swing), ("SFX_BowShot", bow_shot), ("SFX_LightningZap", lightning_zap),
                ("SFX_FlaskThrow", flask_throw), ("SFX_FlaskShatter", flask_shatter), ("SFX_BladeHit", blade_hit),
                ("SFX_AuraPulse", aura_pulse),
                ("SFX_BoomerangWhoosh", boomerang_whoosh), ("SFX_MeteorCast", meteor_cast), ("SFX_Explosion", explosion),
                ("SFX_FrostNova", frost_nova), ("SFX_DaggerCast", dagger_cast)],
    "Enemies": [("SFX_BoneHit", bone_hit), ("SFX_SkeletonDeath", skeleton_death), ("SFX_SlimeHit", slime_hit),
                ("SFX_SlimeDeath", slime_death), ("SFX_SlimeHop", slime_hop),
                ("SFX_BatScreech", bat_screech), ("SFX_BatDeath", bat_death), ("SFX_GolemStomp", golem_stomp), ("SFX_RockHit", rock_hit),
                ("SFX_FuseHiss", fuse_hiss), ("SFX_EnemyArrow", enemy_arrow),
                ("SFX_ImpCackle", imp_cackle), ("SFX_ImpDeath", imp_death), ("SFX_Fireball", fireball_cast),
                ("SFX_MagmaHit", magma_hit), ("SFX_MagmaDeath", magma_death), ("SFX_LavaSizzle", lava_sizzle)],
    "Player": [("SFX_PlayerHurt", player_hurt), ("SFX_PlayerJump", player_jump), ("SFX_PlayerSlide", player_slide),
               ("SFX_PlayerDowned", player_downed), ("SFX_PlayerRevive", player_revive), ("SFX_LevelUp", level_up)],
    "Pickups": [("SFX_GemPickup", gem_pickup), ("SFX_HealthPickup", health_pickup), ("SFX_MagnetPickup", magnet_pickup),
                ("SFX_ChestOpen", chest_open), ("SFX_ShrineCharge", shrine_charge)],
    "UI": [("SFX_UIClick", ui_click), ("SFX_UIHover", ui_hover), ("SFX_UIReady", ui_ready), ("SFX_UIStart", ui_start),
           ("SFX_Victory", victory), ("SFX_Defeat", defeat)],
}


# ----------------------------------------------------------------------------- music

def midi(n):
    return 440.0 * 2 ** ((n - 69) / 12)


def place(buf, x, at):
    i = int(at * SR)
    end = min(len(buf), i + len(x))
    buf[i:end] += x[: end - i]


def kick():
    d = 0.35
    n = int(SR * d)
    return sine(sweep(150, 45, d, 0.3), d) * env(n, a=0.001, d=0.12) * 1.2


def snare():
    d = 0.22
    n = int(SR * d)
    return highpass(noise(d), 1500) * env(n, a=0.001, d=0.06) * 0.7 + sine(190, d) * env(n, a=0.001, d=0.04) * 0.5


def hat(open_=False):
    d = 0.18 if open_ else 0.05
    n = int(SR * d)
    return highpass(noise(d), 7000) * env(n, a=0.001, d=0.05 if open_ else 0.012) * 0.35


def battle_theme():
    bpm = 132
    beat = 60 / bpm
    bars = 16
    dur = bars * 4 * beat
    L = np.zeros(int(SR * dur) + SR)
    R = np.zeros_like(L)
    # A minor: Am - F - C - G (x4), last 8 bars go up an energy notch
    prog = [(57, [57, 60, 64]), (53, [53, 57, 60]), (48, [55, 60, 64]), (55, [55, 59, 62])]
    k, s, hc, ho = kick(), snare(), hat(), hat(True)
    lead_motif = [76, 74, 72, 74, 76, 79, 76, 72, 74, 72, 69, 72, 74, 76, 74, 71]
    for bar in range(bars):
        root, chord = prog[bar % 4]
        t0 = bar * 4 * beat
        hype = bar >= 8
        for b in range(4):
            place(L, k, t0 + b * beat); place(R, k, t0 + b * beat)
            if b in (1, 3):
                place(L, s, t0 + b * beat); place(R, s, t0 + b * beat)
            for h in range(2):
                hh = ho if (h == 1 and hype) else hc
                place(L, hh * 0.8, t0 + (b + h * 0.5) * beat)
                place(R, hh, t0 + (b + h * 0.5) * beat)
        # driving 8th-note bass
        for e in range(8):
            f = midi(root - 12 + (12 if e % 4 == 3 else 0))
            nd = beat / 2
            note = lowpass(saw(f, nd) * env(int(SR * nd), a=0.003, d=0.12), 900)
            place(L, note * 0.55, t0 + e * nd); place(R, note * 0.55, t0 + e * nd)
        # pad
        padn = sum(lowpass(saw(midi(n), 4 * beat) + saw(midi(n) * 1.005, 4 * beat), 1400) for n in chord)
        padn *= env(len(padn), a=0.3, d=3.0, s=0.4) * 0.08
        place(L, padn, t0); place(R, padn * 0.9, t0)
        # arpeggio (16ths) on the right, delayed copy on left
        for e in range(16):
            n = chord[e % 3] + 12 + (12 if e % 8 == 7 else 0)
            nd = beat / 4
            a = square(midi(n), nd, 0.25) * env(int(SR * nd), a=0.002, d=0.05) * (0.10 if hype else 0.07)
            place(R, a, t0 + e * nd)
            place(L, a * 0.6, t0 + e * nd + beat * 0.75)
        if hype:
            for e in range(4):
                n = lead_motif[(bar % 4) * 4 + e]
                nd = beat
                ld = (saw(midi(n), nd) * 0.5 + square(midi(n) * 1.003, nd, 0.5) * 0.5)
                ld = lowpass(ld, 2600) * env(int(SR * nd), a=0.01, d=0.35, s=0.3) * 0.16
                place(L, ld, t0 + e * nd); place(R, ld, t0 + e * nd)
    n = int(SR * dur)
    return L[:n], R[:n]


def menu_theme():
    bpm = 84
    beat = 60 / bpm
    bars = 8
    dur = bars * 4 * beat
    L = np.zeros(int(SR * dur) + SR * 3)
    R = np.zeros_like(L)
    prog = [[57, 60, 64, 67], [53, 57, 60, 64], [50, 53, 57, 60], [52, 56, 59, 64]]  # Am7 Fmaj7 Dm7 E
    for bar in range(bars):
        chord = prog[bar % 4]
        t0 = bar * 4 * beat
        padn = sum(lowpass(saw(midi(n), 4 * beat + 1) + tri(midi(n) * 1.004, 4 * beat + 1), 900) for n in chord)
        padn *= env(len(padn), a=0.8, d=4.0, s=0.5) * 0.06
        place(L, padn, t0); place(R, padn, t0 + 0.01)
        bass = lowpass(tri(midi(chord[0] - 12), 4 * beat), 500) * env(int(SR * 4 * beat), a=0.05, d=2.0) * 0.4
        place(L, bass, t0); place(R, bass, t0)
        # music-box arpeggio
        for e in range(8):
            n = chord[[0, 2, 1, 3, 2, 1, 3, 2][e]] + 12
            nd = beat / 2
            bell = (sine(midi(n), 1.2) + 0.3 * sine(midi(n) * 3, 1.2)) * env(int(SR * 1.2), a=0.002, d=0.4) * 0.12
            place(L if e % 2 else R, bell, t0 + e * nd)
            place(R if e % 2 else L, bell * 0.4, t0 + e * nd + beat * 0.5)
    n = int(SR * dur)
    # fold the tail back to the start so the loop is seamless
    tail_l, tail_r = L[n:], R[n:]
    L, R = L[:n].copy(), R[:n].copy()
    L[: len(tail_l)] += tail_l
    R[: len(tail_r)] += tail_r
    return L, R


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    if what in ("all", "sfx", "volcano"):
        for cat, items in SFX.items():
            for name, fn in items:
                if what == "volcano" and name not in ("SFX_ImpCackle", "SFX_ImpDeath", "SFX_Fireball", "SFX_MagmaHit", "SFX_MagmaDeath", "SFX_LavaSizzle"):
                    continue
                write(fn(), os.path.join("SFX", cat), name)
    if what in ("all", "music"):
        l, r = menu_theme()
        write_stereo(l, r, "Music", "MUS_Menu")
        l, r = battle_theme()
        write_stereo(l, r, "Music", "MUS_Battle")
    if what in ("all", "music", "volcano"):
        l, r = volcano_theme()
        write_stereo(l, r, "Music", "MUS_Volcano")
