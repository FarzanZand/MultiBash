"""
MultiBash music v2: longer, sectioned loops (intro / verse / chorus / breakdown / bridge) so a 10-minute run
doesn't hear the same 25 seconds 24 times, plus a boss theme.

  python Tools/Audio/music_v2.py [battle|volcano|boss|menu|all]

Everything is pure numpy/scipy: a few small synth voices, a stereo bus with a send reverb, and a tiny
"arranger" that renders sections from chord progressions, drum patterns and motif-based melodies.
Every track folds its tail back onto the start, so the loop point is seamless.
"""
import os
import sys

import numpy as np
from scipy.signal import fftconvolve, lfilter

sys.path.insert(0, os.path.dirname(__file__))
import generate_audio as ga  # noqa: E402

SR = ga.SR
midi, sine, saw, square, tri, noise, env = ga.midi, ga.sine, ga.saw, ga.square, ga.tri, ga.noise, ga.env
rng = np.random.default_rng(77)


def lp(x, c):
    a = 1 - np.exp(-2 * np.pi * c / SR)
    return lfilter([a], [1, -(1 - a)], x)


def hp(x, c):
    return x - lp(x, c)


def bp(x, lo, hi):
    return lp(hp(x, lo), hi)


def adsr(n, a=0.01, d=0.2, s=0.6, r=0.1):
    t = np.arange(n) / SR
    e = np.where(t < a, t / max(a, 1e-4), s + (1 - s) * np.exp(-(t - a) / max(d, 1e-4)))
    rel = min(n, int(r * SR))
    if rel > 0:
        e[-rel:] *= np.linspace(1, 0, rel)
    return e


# ----------------------------------------------------------------------------- voices

def supersaw(f, dur, voices=5, spread=0.012):
    out = np.zeros(int(SR * dur))
    for i in range(voices):
        det = 1 + spread * (i - (voices - 1) / 2) / max(1, voices - 1) * 2
        ph = rng.random()
        t = np.arange(len(out)) / SR
        out += 2 * ((f * det * t + ph) % 1.0) - 1
    return out / voices


def pluck_v(f, dur, bright=3000):
    n = int(SR * dur)
    x = (saw(f, dur) * 0.6 + square(f * 1.002, dur, 0.3) * 0.4)
    return lp(x, bright) * env(n, a=0.002, d=0.14)


def bell(f, dur):
    n = int(SR * dur)
    return (sine(f, dur) + 0.35 * sine(f * 2.76, dur) + 0.15 * sine(f * 5.4, dur)) * env(n, a=0.002, d=dur * 0.35)


def lead_v(f, dur, kind="saw", vib=True):
    n = int(SR * dur)
    t = np.arange(n) / SR
    fv = f * (1 + (0.006 * np.sin(2 * np.pi * 5.5 * t) * np.clip((t - 0.15) * 4, 0, 1) if vib else 0))
    if kind == "saw":
        x = saw(fv, dur) * 0.55 + square(fv * 1.004, dur, 0.5) * 0.45
        x = lp(x, 2800)
    elif kind == "brass":
        x = np.tanh(saw(fv, dur) * 2.2) * 0.6 + saw(fv * 0.5, dur) * 0.4
        cut = 600 + 2600 * np.exp(-t * 6)
        x = ga.lowpass(x, cut) if n < SR * 0.6 else lp(x, 2200)
    elif kind == "flute":
        x = tri(fv, dur) * 0.8 + 0.2 * sine(fv * 2, dur) + 0.04 * noise(dur)
        x = lp(x, 3200)
    else:
        x = np.tanh((saw(fv, dur) + saw(fv * 1.005, dur)) * 1.6)
        x = lp(x, 2400)
    return x * adsr(n, a=0.015, d=0.3, s=0.55, r=min(0.08, dur * 0.3))


def choir(f, dur):
    """'Aah' pad: detuned saws through two formant bands."""
    x = supersaw(f, dur, voices=4, spread=0.008)
    y = bp(x, 550, 900) * 1.4 + bp(x, 1000, 1400) * 0.7
    return y * adsr(int(SR * dur), a=0.4, d=1.0, s=0.8, r=0.4)


def pad_v(f, dur, bright=1300):
    x = supersaw(f, dur, voices=5, spread=0.01)
    return lp(x, bright) * adsr(int(SR * dur), a=0.35, d=1.5, s=0.7, r=0.4)


def bass_v(f, dur, kind="saw", cut=900):
    n = int(SR * dur)
    if kind == "dist":
        x = np.tanh(lp(saw(f, dur) + saw(f * 1.5, dur) * 0.45, 1100) * 3.2)
        return x * env(n, a=0.002, d=0.07)
    if kind == "sub":
        return (sine(f, dur) * 0.8 + 0.25 * lp(saw(f, dur), 400)) * adsr(n, a=0.005, d=0.2, s=0.7, r=0.03)
    return lp(saw(f, dur) + 0.5 * square(f * 0.5, dur), cut) * env(n, a=0.003, d=0.13)


# drums
def kick(punch=1.0):
    d = 0.35
    n = int(SR * d)
    return (sine(ga.sweep(160, 44, d, 0.3), d) * env(n, a=0.001, d=0.13) * 1.15
            + hp(noise(d), 2000) * env(n, a=0.0005, d=0.006) * 0.25 * punch)


def snare(tone=190):
    d = 0.25
    n = int(SR * d)
    return (hp(noise(d), 1400) * env(n, a=0.001, d=0.07) * 0.75
            + sine(tone, d) * env(n, a=0.001, d=0.045) * 0.55)


def clap():
    d = 0.25
    n = int(SR * d)
    x = np.zeros(n)
    for k in range(3):
        i = int(k * 0.011 * SR)
        seg = bp(noise(d), 900, 3000)[: n - i] * env(n - i, a=0.0005, d=0.03 if k < 2 else 0.09)
        x[i:] += seg
    return x * 0.6


def hat(open_=False):
    d = 0.22 if open_ else 0.05
    n = int(SR * d)
    return hp(noise(d), 7500) * env(n, a=0.001, d=0.07 if open_ else 0.013) * 0.33


def crash():
    d = 1.6
    n = int(SR * d)
    return hp(noise(d), 4000) * env(n, a=0.002, d=0.55) * 0.32


def tom(f):
    d = 0.3
    n = int(SR * d)
    return sine(ga.sweep(f, f * 0.55, d, 0.4), d) * env(n, a=0.001, d=0.13) * 0.9


def riser(dur):
    n = int(SR * dur)
    t = np.arange(n) / SR
    x = noise(dur)
    out = np.zeros(n)
    # stepped band sweep (cheap): 8 bands
    steps = 8
    for k in range(steps):
        a, b = int(n * k / steps), int(n * (k + 1) / steps)
        f = 400 * (12 ** (k / steps))
        out[a:b] = bp(x[a:b], f, f * 2)
    return out * (t / dur) ** 2 * 0.5


def impact():
    d = 1.4
    n = int(SR * d)
    return sine(ga.sweep(90, 30, d, 0.5), d) * env(n, a=0.001, d=0.5) * 1.1 + lp(noise(d), 1200) * env(n, a=0.001, d=0.2) * 0.4


# ----------------------------------------------------------------------------- arranger

class Song:
    def __init__(self, bpm, bars_total):
        self.bpm = bpm
        self.beat = 60.0 / bpm
        self.dur = bars_total * 4 * self.beat
        n = int(SR * self.dur) + SR * 4
        self.L = np.zeros(n); self.R = np.zeros(n)
        self.sL = np.zeros(n); self.sR = np.zeros(n)        # reverb send
        self.duckL = np.ones(n)                              # sidechain pump from kicks

    def put(self, x, at, gain=1.0, pan=0.0, send=0.0, haas=0.0):
        i = int(at * SR)
        if i >= len(self.L):
            return
        x = x[: len(self.L) - i]
        gl, gr = gain * min(1.0, 1 - pan), gain * min(1.0, 1 + pan)
        j = min(len(self.L), i + int(haas * SR))
        self.L[i:i + len(x)] += x * gl
        self.R[j:j + len(x)] += x[: len(self.R) - j] * gr
        if send > 0:
            self.sL[i:i + len(x)] += x * gl * send
            self.sR[i:i + len(x)] += x * gr * send

    def duck(self, at, depth=0.35, time=0.18):
        i = int(at * SR)
        n = int(time * SR)
        seg = 1 - depth * np.exp(-np.arange(n) / (n / 4))
        e = min(len(self.duckL), i + n)
        self.duckL[i:e] = np.minimum(self.duckL[i:e], seg[: e - i])

    def render(self, reverb_time=1.6, reverb_mix=0.28):
        n = int(SR * self.dur)
        ir_n = int(SR * reverb_time)
        t = np.arange(ir_n) / SR
        irl = rng.uniform(-1, 1, ir_n) * np.exp(-t / (reverb_time / 5))
        irr = rng.uniform(-1, 1, ir_n) * np.exp(-t / (reverb_time / 5))
        irl[: int(0.02 * SR)] = 0; irr[: int(0.023 * SR)] = 0
        wl = fftconvolve(lp(self.sL, 5000), irl)[: len(self.L)]
        wr = fftconvolve(lp(self.sR, 5000), irr)[: len(self.R)]
        wl /= max(1e-9, np.sqrt(np.sum(irl ** 2))); wr /= max(1e-9, np.sqrt(np.sum(irr ** 2)))
        L = self.L * self.duckL + wl * reverb_mix
        R = self.R * self.duckL + wr * reverb_mix
        # fold the tail (reverb + ringing notes) onto the start: seamless loop
        tl, tr = L[n:], R[n:]
        L, R = L[:n].copy(), R[:n].copy()
        L[: len(tl)] += tl[: n]
        R[: len(tr)] += tr[: n]
        # gentle bus glue
        L, R = np.tanh(L * 1.1) / 1.1, np.tanh(R * 1.1) / 1.1
        return L, R


def motif_melody(chord_tones, rhythm, seed, octave=12, rest_p=0.1):
    """Melody for one bar from chord tones + passing notes. rhythm: list of (beat_offset, length_beats)."""
    r = np.random.default_rng(seed)
    out = []
    prev = None
    for off, ln in rhythm:
        if r.random() < rest_p and off > 0:
            continue
        pool = [c + octave for c in chord_tones] + [c + octave + 12 for c in chord_tones[:1]]
        if prev is not None:
            pool.sort(key=lambda n: abs(n - prev) + r.random() * 4)
            n = pool[0] if r.random() < 0.7 else pool[min(1, len(pool) - 1)]
        else:
            n = pool[r.integers(len(pool))]
        prev = n
        out.append((off, ln, n))
    return out


def drums(S, t0, style, bar_i, fill=False, density=1.0, open_hats=False):
    b = S.beat
    k, s, cl, hc, ho = kick(), snare(), clap(), hat(), hat(True)
    if style == "none":
        return
    if style in ("full", "half", "four", "boss"):
        kicks = {"full": [0, 1.5, 2, 3.5] if bar_i % 2 else [0, 2, 2.75], "half": [0, 2.5], "four": [0, 1, 2, 3],
                 "boss": [0, 0.75, 1.5, 2, 2.75, 3.5]}[style]
        for kb in kicks:
            S.put(k, t0 + kb * b, 0.72)
            S.duck(t0 + kb * b, 0.3 if style != "half" else 0.2)
        snb = [1, 3] if style != "half" else [2]
        for sb in snb:
            S.put(s, t0 + sb * b, 0.75, send=0.15)
            if style in ("full", "boss"):
                S.put(cl, t0 + sb * b + 0.005, 0.35, pan=0.2, send=0.2)
        sub = 4 if style == "boss" else 2
        for h in range(4 * sub):
            if density < 1 and h % 2:
                continue
            hh = ho if (open_hats and h % sub == sub // 2) else hc
            S.put(hh, t0 + h * b / sub, 0.32 + 0.2 * (h % 2 == 0), pan=0.35)
    if style == "toms":
        for i in range(8):
            S.put(tom([150, 150, 130, 130, 110, 110, 95, 85][i]), t0 + i * b / 2, 0.7, pan=-0.4 + i * 0.1, send=0.2)
    if fill:
        for i in range(6):
            S.put(tom([240, 200, 170, 140, 115, 95][i]), t0 + 3 * b + i * b / 6, 0.75, pan=0.5 - i * 0.2, send=0.2)
        S.put(s, t0 + 3.833 * b, 0.6)


# ----------------------------------------------------------------------------- tracks

def battle_theme():
    """Haunted Keep: A minor, 132 bpm, ~87 s: intro, verse, chorus, breakdown, bridge, chorus 2, turnaround."""
    S = Song(132, 48)
    b = S.beat
    I = {"Am": [57, 60, 64], "F": [53, 57, 60], "C": [48, 52, 55], "G": [55, 59, 62], "Em": [52, 55, 59],
         "Dm": [50, 53, 57], "E": [52, 56, 59]}
    verse = ["Am", "F", "C", "G"]
    bridge = ["F", "G", "Em", "Am", "Dm", "Em", "F", "E"]
    plan = ([("intro", c) for c in verse] + [("verse", c) for c in verse * 2] + [("chorus", c) for c in verse * 2]
            + [("break", c) for c in ["Am", "F", "Dm", "E"]] + [("bridge", c) for c in bridge]
            + [("chorus2", c) for c in verse * 2] + [("verse", c) for c in verse] + [("turn", c) for c in ["Dm", "F", "G", "E"]])
    hook = [(0, 1, 76), (1, 0.5, 74), (1.5, 0.5, 72), (2, 1, 74), (3, 1, 76),
            (0, 1.5, 79), (1.5, 0.5, 76), (2, 1, 72), (3, 1, 74),
            (0, 1, 72), (1, 1, 69), (2, 1, 72), (3, 1, 74),
            (0, 2, 76), (2, 1, 74), (3, 1, 71)]
    for bi, (sec, ch) in enumerate(plan):
        t0 = bi * 4 * b
        tones = I[ch]
        root = tones[0] if tones[0] < 56 else tones[0] - 12
        new_sec = bi == 0 or plan[bi - 1][0] != sec
        if new_sec and sec in ("chorus", "chorus2", "verse"):
            S.put(crash(), t0, 0.7, send=0.3)
        last_of_section = bi + 1 >= len(plan) or plan[bi + 1][0] != sec
        style = {"intro": "half", "verse": "full", "chorus": "full", "chorus2": "full", "break": "none", "bridge": "half",
                 "turn": "full"}[sec]
        drums(S, t0, style, bi, fill=last_of_section and sec not in ("break",), open_hats=sec in ("chorus", "chorus2"))
        if sec == "break" and bi % 4 == 3:
            S.put(riser(4 * b), t0, 0.5)
            drums(S, t0 + 2 * b, "toms", bi)
        # bass
        if sec != "break":
            for e in range(8):
                f = midi(root - 12 + (12 if e % 4 == 3 else 0))
                S.put(bass_v(f, b / 2), t0 + e * b / 2, 0.36)
        else:
            S.put(bass_v(midi(root - 12), 4 * b, "sub"), t0, 0.3)
        # pad
        for n in tones:
            S.put(pad_v(midi(n), 4 * b + 0.3, 1400 if sec in ("intro", "break") else 2000), t0, 0.1, pan=-0.2, send=0.5, haas=0.014)
        if sec in ("break", "bridge"):
            for n in tones:
                S.put(choir(midi(n + 12), 4 * b + 0.3), t0, 0.08, send=0.6)
        # arpeggio
        if sec not in ("break",):
            pat = [0, 1, 2, 1, 0, 2, 1, 2] if sec != "bridge" else [0, 2, 1, 2, 0, 1, 2, 1]
            for e in range(16):
                n = tones[pat[e % 8]] + 12 + (12 if e % 8 == 7 else 0)
                g = 0.13 if sec in ("chorus", "chorus2") else 0.1
                S.put(pluck_v(midi(n), b / 4 + 0.05), t0 + e * b / 4, g, pan=0.45, send=0.25)
                S.put(pluck_v(midi(n), b / 4 + 0.05), t0 + e * b / 4 + 0.75 * b, g * 0.5, pan=-0.5, send=0.25)
        # lead
        if sec in ("chorus", "chorus2"):
            part = hook[(bi % 4) * 4:(bi % 4) * 4 + 4] if False else [h for h in hook[(bi % 4) * 4:(bi % 4 + 1) * 4]]
            for off, ln, n in part:
                n2 = n + (12 if sec == "chorus2" and (bi % 8) >= 4 else 0)
                S.put(lead_v(midi(n2), ln * b, "saw"), t0 + off * b, 0.26, send=0.35, haas=0.006)
                if sec == "chorus2":
                    S.put(lead_v(midi(n2 - 12), ln * b, "brass"), t0 + off * b, 0.07, pan=-0.3, send=0.3)
        if sec == "bridge":
            for off, ln, n in motif_melody(tones, [(0, 1.5), (1.5, 0.5), (2, 2)], seed=bi, octave=12):
                S.put(lead_v(midi(n), ln * b, "flute"), t0 + off * b, 0.22, pan=0.2, send=0.5)
        if sec == "verse" and bi % 8 >= 4:
            for off, ln, n in motif_melody(tones, [(0, 0.5), (0.5, 0.5), (1, 1), (2.5, 0.5), (3, 1)], seed=bi + 100, octave=24, rest_p=0.25):
                S.put(bell(midi(n), 0.8), t0 + off * b, 0.07, pan=-0.3, send=0.4)
    return S.render(1.8, 0.3)


def volcano_theme():
    """Molten Caldera: D phrygian, 138 bpm, ~98 s, chugging distorted bass, toms, choir, brass hook."""
    S = Song(138, 52)
    b = S.beat
    I = {"Dm": [50, 53, 57], "Eb": [51, 55, 58], "C": [48, 52, 55], "Bb": [46, 50, 53], "Gm": [55, 58, 62], "A": [57, 61, 64]}
    riff = ["Dm", "Eb", "Dm", "C"]
    plan = ([("intro", c) for c in riff] + [("verse", c) for c in riff * 2] + [("chorus", c) for c in ["Dm", "Bb", "C", "A"] * 2]
            + [("break", c) for c in ["Gm", "Eb", "Gm", "A"]] + [("verse2", c) for c in riff * 2]
            + [("chorus", c) for c in ["Dm", "Bb", "C", "A"] * 2] + [("bridge", c) for c in ["Bb", "C", "Dm", "Dm", "Gm", "A", "Dm", "A"]]
            + [("turn", c) for c in riff])
    hook = [(0, 1.5, 74), (1.5, 0.5, 75), (2, 2, 74), (0, 1, 72), (1, 1, 70), (2, 2, 69),
            (0, 1.5, 72), (1.5, 0.5, 74), (2, 2, 76), (0, 1, 73), (1, 1, 76), (2, 2, 79)]
    for bi, (sec, ch) in enumerate(plan):
        t0 = bi * 4 * b
        tones = I[ch]
        root = tones[0] if tones[0] < 54 else tones[0] - 12
        new_sec = bi == 0 or plan[bi - 1][0] != sec
        last = bi + 1 >= len(plan) or plan[bi + 1][0] != sec
        if new_sec and sec != "break":
            S.put(impact() if sec == "chorus" else crash(), t0, 0.6, send=0.3)
        style = {"intro": "toms", "verse": "full", "verse2": "four", "chorus": "full", "break": "half", "bridge": "toms", "turn": "full"}[sec]
        drums(S, t0, style, bi, fill=last or bi % 4 == 3, open_hats=sec == "chorus")
        if sec in ("verse", "verse2", "chorus", "turn"):
            for e in range(16):
                if e % 8 in (3, 6):
                    continue
                S.put(bass_v(midi(root - 12), b / 4, "dist"), t0 + e * b / 4, 0.17, pan=-0.25, haas=0.008)
        S.put(bass_v(midi(root - 24), 4 * b, "sub"), t0, 0.18)
        for n in tones:
            S.put(choir(midi(n + 12), 4 * b + 0.3), t0, 0.12, send=0.55, haas=0.012)
        if sec == "chorus":
            k = (bi % 2) * 3
            seg = hook[k:k + 3] if (bi // 2) % 2 == 0 else hook[6 + k:9 + k]
            for off, ln, n in seg:
                S.put(lead_v(midi(n), ln * b, "brass"), t0 + off * b, 0.24, send=0.3, haas=0.005)
                S.put(lead_v(midi(n - 12), ln * b, "dist"), t0 + off * b, 0.07, pan=0.3, send=0.2)
        if sec == "verse2":
            for off, ln, n in motif_melody(tones, [(0, 1), (1, 0.5), (1.5, 0.5), (2, 1.5), (3.5, 0.5)], seed=bi + 7, octave=12, rest_p=0.2):
                S.put(lead_v(midi(n), ln * b, "dist"), t0 + off * b, 0.1, pan=0.25, send=0.3)
        if sec == "bridge":
            for e in range(8):
                n = tones[[0, 1, 2, 1, 0, 2, 1, 0][e]] + 24
                S.put(bell(midi(n), 0.7), t0 + e * b / 2, 0.06, pan=0.4 * (1 if e % 2 else -1), send=0.6)
        if sec == "break" and bi % 4 == 3:
            S.put(riser(4 * b), t0, 0.45)
    return S.render(2.2, 0.32)


def boss_theme():
    """Boss fights: E harmonic minor, 152 bpm, ~50 s, double-time drums, brass stabs, urgent arps."""
    S = Song(152, 32)
    b = S.beat
    I = {"Em": [52, 55, 59], "C": [48, 52, 55], "Am": [57, 60, 64], "B": [59, 63, 66], "D": [50, 54, 57], "F#dim": [54, 57, 60]}
    prog = ["Em", "C", "Am", "B"] * 4 + ["Em", "D", "C", "B"] * 2 + ["Am", "F#dim", "B", "B"] * 2
    for bi, ch in enumerate(prog):
        t0 = bi * 4 * b
        tones = I[ch]
        root = tones[0] if tones[0] < 56 else tones[0] - 12
        part = 0 if bi < 8 else 1 if bi < 16 else 2 if bi < 24 else 3
        if bi % 8 == 0:
            S.put(impact(), t0, 0.7, send=0.3)
            S.put(crash(), t0, 0.7, send=0.3)
        drums(S, t0, "boss" if part != 2 else "full", bi, fill=bi % 4 == 3, open_hats=True)
        for e in range(16):
            n = root - 12 + (12 if e % 4 == 2 else 0) + (7 if e % 8 == 7 else 0)
            S.put(bass_v(midi(n), b / 4, "dist"), t0 + e * b / 4, 0.17, pan=-0.2, haas=0.007)
        stabs = [0, 0.75, 1.5] if part % 2 == 0 else [0, 1.5, 2.5, 3]
        for st in stabs:
            for n in tones:
                S.put(lead_v(midi(n + 12), 0.28, "brass"), t0 + st * b, 0.09, pan=0.2, send=0.25, haas=0.006)
        for e in range(16):
            n = tones[[0, 1, 2, 1][e % 4]] + 24 + (12 if e % 16 == 15 else 0)
            S.put(pluck_v(midi(n), b / 4 + 0.03, 3600), t0 + e * b / 4, 0.09, pan=0.5 * (1 if e % 2 else -1), send=0.2)
        if part >= 1:
            for off, ln, n in motif_melody(tones, [(0, 1.5), (1.5, 0.5), (2, 1), (3, 1)], seed=bi + 50, octave=24 if part == 3 else 12, rest_p=0.1):
                S.put(lead_v(midi(n), ln * b, "saw"), t0 + off * b, 0.22, send=0.3, haas=0.005)
        for n in tones:
            S.put(choir(midi(n), 4 * b + 0.2), t0, 0.09, send=0.5, haas=0.012)
    return S.render(1.5, 0.25)


def menu_theme():
    """Lobby: A minor, 84 bpm, ~46 s, music box + pad, flute melody in the second half."""
    S = Song(84, 16)
    b = S.beat
    prog = [[57, 60, 64, 67], [53, 57, 60, 64], [50, 53, 57, 60], [52, 56, 59, 64]]
    for bi in range(16):
        ch = prog[bi % 4]
        t0 = bi * 4 * b
        for n in ch:
            S.put(pad_v(midi(n), 4 * b + 0.5, 1300), t0, 0.06, send=0.5, haas=0.015)
        S.put(bass_v(midi(ch[0] - 12), 4 * b, "sub"), t0, 0.18)
        for e in range(8):
            n = ch[[0, 2, 1, 3, 2, 1, 3, 2][e]] + 12
            S.put(bell(midi(n), 1.2), t0 + e * b / 2, 0.09, pan=0.4 if e % 2 else -0.4, send=0.5)
        if bi >= 8:
            for off, ln, n in motif_melody(ch[:3], [(0, 1.5), (1.5, 0.5), (2, 2)], seed=bi + 3, octave=12, rest_p=0.0):
                S.put(lead_v(midi(n), ln * b, "flute"), t0 + off * b, 0.16, send=0.6)
        if bi >= 4:
            for kb in (0, 2.5):
                S.put(kick(0.3) * 0.5, t0 + kb * b, 0.6)
            for h in range(8):
                S.put(hat(), t0 + h * b / 2, 0.25, pan=0.3)
    return S.render(2.4, 0.4)


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    jobs = {"battle": ("MUS_Battle", battle_theme), "volcano": ("MUS_Volcano", volcano_theme),
            "boss": ("MUS_Boss", boss_theme), "menu": ("MUS_Menu", menu_theme)}
    for k, (name, fn) in jobs.items():
        if what in ("all", k):
            l, r = fn()
            ga.write_stereo(l, r, "Music", name, peak=0.85)
