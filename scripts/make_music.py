"""Original royalty-free background track: 112 BPM, C-G-Am-F, stereo 44.1 kHz WAV.
Usage: make_music.py OUT.wav [SECONDS]   (default 31 s; use reel length + 1 for longer reels)"""
import sys, wave
import numpy as np

SR, BPM = 44100, 112
DUR = float(sys.argv[2]) if len(sys.argv) > 2 else 31.0
beat = 60 / BPM
n = int(SR * DUR)
t = np.arange(n) / SR
mix_l = np.zeros(n); mix_r = np.zeros(n)
rng = np.random.default_rng(7)

def add(sig, start, pan=0.0, gain=1.0):
    i = int(start * SR)
    if i >= n: return
    sig = sig[: n - i] * gain
    mix_l[i:i + len(sig)] += sig * (1 - pan) / 2 * 2 ** .5
    mix_r[i:i + len(sig)] += sig * (1 + pan) / 2 * 2 ** .5

def env(length, a=0.005, r=0.2):
    m = int(length * SR); e = np.ones(m)
    ai = max(1, int(a * SR)); e[:ai] = np.linspace(0, 1, ai)
    e *= np.exp(-np.arange(m) / SR / r)
    return e

def note(f, length, a=0.005, r=0.3, harm=(1, .5, .25)):
    m = int(length * SR); tt = np.arange(m) / SR
    s = sum(h * np.sin(2 * np.pi * f * (k + 1) * tt) for k, h in enumerate(harm))
    return s * env(length, a, r)

def kick():
    m = int(.35 * SR); tt = np.arange(m) / SR
    f = 50 + 90 * np.exp(-tt * 30)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 9)

def hat():
    m = int(.06 * SR); x = rng.standard_normal(m)
    x = np.diff(np.concatenate([[0], x]))  # crude high-pass
    return x * np.exp(-np.arange(m) / SR * 60) * .5

def clap():
    m = int(.18 * SR); x = rng.standard_normal(m)
    return x * np.exp(-np.arange(m) / SR * 22) * .35

mid = lambda m: 440 * 2 ** ((m - 69) / 12)
chords = [(48, [60, 64, 67]), (43, [59, 62, 67]), (45, [60, 64, 69]), (41, [60, 65, 69])]  # C G Am F
bars = int(DUR / (4 * beat)) + 1
for b in range(bars):
    root, tri = chords[b % 4]
    t0 = b * 4 * beat
    for f in tri:  # soft pad
        add(note(mid(f), 4 * beat, a=.25, r=2.5, harm=(1, .3, .1)), t0, pan=rng.uniform(-.4, .4), gain=.07)
    for k in range(4):
        tb = t0 + k * beat
        if b > 0 or k >= 2:
            add(kick(), tb, gain=.55)
        add(hat(), tb + beat / 2, pan=.3, gain=.35)
        if k in (1, 3) and b > 0:
            add(clap(), tb, pan=-.1, gain=.6)
        add(note(mid(root - 12 if k % 2 else root), beat * .9, r=.25, harm=(1, .4)), tb, gain=.22)  # bass
    for k in range(8):  # pluck arpeggio, 8th notes
        f = mid(tri[k % 3] + (12 if k >= 4 else 0))
        add(note(f, beat / 2, r=.12, harm=(1, .6, .3, .15)), t0 + k * beat / 2, pan=(-.5 if k % 2 else .5), gain=.08)

out = np.stack([mix_l, mix_r], 1)
out /= np.abs(out).max() / 0.85
fade = int(1.5 * SR); out[-fade:] *= np.linspace(1, 0, fade)[:, None]
with wave.open(sys.argv[1], "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((out * 32767).astype("<i2").tobytes())
print("wrote", sys.argv[1])
