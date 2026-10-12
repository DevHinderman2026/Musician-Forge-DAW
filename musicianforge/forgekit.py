"""Musician Forge's own instruments, made from scratch: three drum kits and the Forge 808 Sub.

Every sound is synthesized here (no recordings from anywhere else), so the kit
carries no outside license. The sounds are written into a small SoundFont that
FluidSynth loads next to GeneralUser GS:

- Forge Dubstep Kit (drum kits, bank 128, program 100, rebuilt in version 3
  for Musician Forge 0.9.2): a deep, punchy kick that gets out of the bass's
  way, a deep 808 kick, a big, heavy snare with a clap layer and a room tail,
  claps, gritty hats, toms, cymbals, an impact and a riser, laid out on the
  usual drum notes so the drum layout keys play it. Its kick, snare, clap and
  hats are driven and crushed for grit (parallel distortion).
- Forge House Kit (bank 128, program 101, version 2): a short, round 909-style
  kick that decays in about a quarter of a second, a noisy snare, a clap of four
  quick bursts and a tail, metallic hats from the six 808 oscillators, a shaker,
  rim, toms and cymbals.
- Forge Trap Kit (bank 128, program 102, version 2): a sharp, short kick that
  leaves room for the 808, a long 808 boom on note 35, a crisp clap layered with a
  snare, thin bright hats for rolls, an open hat and a rim.
- Forge 808 Sub (bank 100, program 38, in the Bass family): a long, deep
  808 bass to play as notes.

The sound design follows the research written up in the development notes
(Beat Kitchen, Sound On Sound, Werner, Abel and Smith's TR-808 cymbal paper).

The SoundFont is built the first time it is needed (about a second) and kept
in the SoundFonts folder. Changing a sound means raising KIT_VERSION.
"""

import logging
import os

import numpy as np

from . import keyboard_map, paths
from .sf2writer import (GEN_EXCLUSIVE_CLASS, GEN_INITIAL_ATTENUATION, GEN_OVERRIDING_ROOT_KEY, GEN_PAN,
                        GEN_RELEASE_VOL_ENV, GEN_SAMPLE_MODES, Instrument, Preset, Sample, Zone, timecents,
                        write_sf2)

log = logging.getLogger("musicianforge.forgekit")

KIT_VERSION = 3
SR = 48000
FORGE_BANK = 100            # Musician Forge's own melodic instruments
DUBSTEP_KIT_PROGRAM = keyboard_map.DUBSTEP_KIT_PROGRAM   # in the drum kits bank (128)
DUBSTEP_KIT_NAME = "Forge Dubstep Kit"
HOUSE_KIT_PROGRAM = 101
HOUSE_KIT_NAME = "Forge House Kit"
TRAP_KIT_PROGRAM = 102
TRAP_KIT_NAME = "Forge Trap Kit"
SUB_808_PROGRAM = 38
SUB_808_NAME = "Forge 808 Sub"

# Notes whose sound in the Forge Dubstep Kit differs from the usual drum name (spoken by the drum layout).
DUBSTEP_DRUM_NAMES = keyboard_map.KIT_DRUM_NAMES[DUBSTEP_KIT_PROGRAM]


def kit_path():
    return os.path.join(paths.soundfont_dir(), "Musician-Forge-Kits-v{}.sf2".format(KIT_VERSION))


def ensure_kit(path=None):
    """The kit's SoundFont, built first if it is missing. Returns its path."""
    path = path or kit_path()
    if not os.path.isfile(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        size = build_kit(path)
        log.info("Built Musician Forge's own instruments: %s (%d bytes)", path, size)
    return path


# ----------------------------------------------------------------------
# sound-making helpers
# ----------------------------------------------------------------------
def _t(seconds):
    return np.arange(int(round(seconds * SR))) / float(SR)


def _noise(n, seed):
    return np.random.default_rng(seed).uniform(-1.0, 1.0, n)


def _band(x, lo=None, hi=None):
    """Keep frequencies between lo and hi (soft edges), using the FFT."""
    spectrum = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(len(x), 1.0 / SR)
    gain = np.ones_like(freqs)
    if lo:
        gain *= np.clip((freqs - lo * 0.8) / (lo * 0.4), 0.0, 1.0)
    if hi:
        gain *= np.clip((hi * 1.2 - freqs) / (hi * 0.4), 0.0, 1.0)
    return np.fft.irfft(spectrum * gain, len(x))


def _sine(freq):
    """A sine whose frequency follows the array `freq` (Hz, one value per sample)."""
    return np.sin(2.0 * np.pi * np.cumsum(freq) / SR)


def _square(freq, t):
    return np.sign(np.sin(2.0 * np.pi * freq * t))


def _decay(t, tau):
    return np.exp(-t / tau)


def _attack(t, seconds):
    return np.clip(t / seconds, 0.0, 1.0)


def _saturate(x, drive):
    """Soft clipping: louder, thicker, harder-hitting."""
    return np.tanh(drive * x) / np.tanh(drive)


def _finish(x, peak=0.92, fade=0.004):
    """Fade the very end to silence and set the loudest point to `peak`."""
    x = np.asarray(x, dtype=np.float64)
    n = min(len(x), int(fade * SR))
    if n:
        x[-n:] *= np.linspace(1.0, 0.0, n)
    top = np.max(np.abs(x))
    return x * (peak / top) if top > 0 else x


def _metal(t, freqs):
    return sum(_square(f, t) for f in freqs) / float(len(freqs))


HAT_FREQS = (205.3, 304.4, 369.6, 522.7, 540.0, 800.0)          # the classic 808 hat oscillators
CYMBAL_FREQS = (263.0, 400.0, 421.0, 474.0, 587.0, 845.0, 1074.0, 1387.0)


# ----------------------------------------------------------------------
# the Forge Dubstep Kit's kick, snare, clap and hats (kit version 3, Musician Forge 0.9.2)
# ----------------------------------------------------------------------
# Rebuilt from the research in the development notes ("A more dubstep Forge Dubstep Kit"): a deeper,
# punchier kick, a bigger and heavier snare, and grit throughout. Each one takes clean=True to leave out its
# distortion, so the tests can measure how much of the sound is grit.
def _crush(x, bits):
    """Fewer loudness steps, like a bit crusher: a gritty, digital edge."""
    steps = float(2 ** (bits - 1))
    return np.round(x * steps) / steps


def _grit(x, drive, lo, hi, bits=None):
    """Parallel distortion: a copy of the sound driven hard (and crushed), kept between lo and hi. Mixed in
    beside the sound, it adds grit without muddying the low end."""
    top = float(np.max(np.abs(x)))
    y = _saturate(x / top if top > 0 else x, drive)
    if bits:
        y = _crush(y, bits)
    return _band(y, lo, hi)


def _held(t, hold, tau):
    """Full loudness for `hold` seconds, then a decay."""
    return np.where(t < hold, 1.0, np.exp(-np.clip(t - hold, 0.0, None) / tau))


def _clap_layer(t, seed, spacing=(0.0, 0.0095, 0.019, 0.0285), tail=0.18, lo=900.0, hi=7000.0):
    """Hand claps: noise in quick bursts, then a tail."""
    noise = _band(_noise(len(t), seed), lo, hi)
    env = np.zeros_like(t)
    for start in spacing:
        env += (t >= start) * np.exp(-np.clip(t - start, 0.0, None) / 0.0065)
    last = spacing[-1]
    env += (t >= last) * 0.65 * np.exp(-np.clip(t - last, 0.0, None) / tail)
    return noise * env


def kick(hard=True, clean=False):
    """A deep, punchy kick. A sine drops from about 235 Hz to 45 Hz (65 Hz after 50 ms, 51 Hz after 100 ms),
    is driven hard while it holds for 60 ms (thick, with overtones small speakers carry), then falls away
    quickly to leave room for the bass. A knock near 95 Hz, a click near 4 kHz, and grit beside it."""
    t = _t(0.65)
    tone = _sine(45.0 + 160.0 * _decay(t, 0.016) + 30.0 * _decay(t, 0.06))
    body = (tone if clean else _saturate(tone, 4.0 if hard else 2.4)) * _held(t, 0.06, 0.12) * _attack(t, 0.0008)
    knock = _sine(95.0 + 80.0 * _decay(t, 0.012)) * _decay(t, 0.04) * 0.8
    click = _band(_noise(len(t), 41), 2500, 10000) * _decay(t, 0.0035) * 2.0
    click += np.sin(2 * np.pi * 4200.0 * t) * _decay(t, 0.0025) * 1.2
    dry = body + knock + click
    if clean:
        return _finish(dry)
    grit = _grit(dry, 10.0, 150.0, 5000.0) * (0.25 if hard else 0.1)
    return _finish(_saturate(dry + grit, 1.8 if hard else 1.2))


def deep_kick(clean=False):
    """The deep 808 kick (note 35): a long boom that drops to 36 Hz, driven before its envelope so that its
    overtones carry on laptop speakers and earbuds."""
    t = _t(1.4)
    tone = _sine(36.0 + 120.0 * _decay(t, 0.025) + 22.0 * _decay(t, 0.12))
    body = (tone if clean else _saturate(tone, 3.5)) * _held(t, 0.05, 0.6) * _attack(t, 0.001)
    knock = _sine(100.0 + 60.0 * _decay(t, 0.015)) * _decay(t, 0.04) * 0.7
    click = _band(_noise(len(t), 42), 2000, 8000) * _decay(t, 0.004) * 1.2
    dry = body + knock + click
    if clean:
        return _finish(dry)
    return _finish(_saturate(dry + _grit(dry, 6.0, 90.0, 1500.0) * 0.2, 1.6))


def snare(hard=True, clean=False):
    """A big, heavy snare: a thick body near 190 Hz (held for 20 ms, then decaying over about 120 ms), a
    bright snap of noise, a short crack from 2 to 5 kHz, a clap layer from 500 Hz up, and a room that rings for
    about a second, with grit beside it."""
    t = _t(1.0)
    tone = _sine(190.0 + 80.0 * _decay(t, 0.015))
    body = (tone if clean else _saturate(tone, 1.6 if hard else 1.3)) * _held(t, 0.02, 0.12) * _attack(t, 0.0005)
    body += _sine(308.0 + 50.0 * _decay(t, 0.015)) * _decay(t, 0.07) * 0.45
    snap = _band(_noise(len(t), 51), 1800, 11000) * _decay(t, 0.16)
    crack = _band(_noise(len(t), 52), 2000, 5000) * _decay(t, 0.012) * 2.0
    clap = _clap_layer(t, 53, lo=500.0) * 0.5
    late = np.clip(t - 0.012, 0.0, None)
    room = _band(_noise(len(t), 54), 500, 7000) * _decay(late, 0.35) * (t >= 0.012) * 0.3
    dry = body * (0.85 if hard else 0.6) + snap * 0.85 + crack + clap + room
    if clean:
        return _finish(dry)
    grit = _grit(dry, 7.0, 400.0, 9000.0, bits=6) * (0.35 if hard else 0.15)
    return _finish(_saturate(dry + grit, 2.6 if hard else 1.6))


def clap(clean=False):
    """Four claps 11 ms apart from 500 Hz up, a longer tail, and crushed grit beside it."""
    t = _t(0.75)
    dry = _clap_layer(t, 61, spacing=(0.0, 0.011, 0.022, 0.034), tail=0.21, lo=500.0)
    if clean:
        return _finish(dry)
    return _finish(_saturate(dry + _grit(dry, 6.0, 800.0, 8000.0, bits=6) * 0.3, 1.8))


def clap_snare(clean=False):
    s, c = snare(True, clean), clap(clean)
    n = max(len(s), len(c))
    mix = np.zeros(n)
    mix[:len(s)] += s * 0.8
    mix[:len(c)] += c * 0.75
    return _finish(mix if clean else _saturate(mix, 1.6))


def hat(length, tau, lo=6500.0, seed=7, clean=False):
    """808-style metal and noise above lo, with a driven, crushed copy mixed in for grit."""
    t = _t(length)
    tone = _metal(t, HAT_FREQS) * 0.6 + _noise(len(t), seed) * 0.5
    if not clean:
        tone = tone + _grit(tone, 6.0, lo * 0.7, 15000.0, bits=4) * 0.9
    return _finish(_band(tone, lo, 16000) * _decay(t, tau) * _attack(t, 0.0006), peak=0.85)


# ----------------------------------------------------------------------
# the rest of the Forge Dubstep Kit
# ----------------------------------------------------------------------
def cymbal(length=2.8, tau=0.9, seed=8):
    t = _t(length)
    tone = _metal(t, CYMBAL_FREQS) * 0.5 + _noise(len(t), seed) * 0.6
    return _finish(_band(tone, 3000, 16000) * _decay(t, tau) * _attack(t, 0.001), peak=0.85)


def ride():
    t = _t(1.8)
    tone = _metal(t, (430.0, 640.0, 960.0, 1290.0)) * 0.6 + _noise(len(t), 9) * 0.15
    return _finish(_band(tone, 2500, 12000) * _decay(t, 0.6), peak=0.8)


def ride_bell():
    t = _t(1.4)
    tone = sum(np.sin(2 * np.pi * f * t) * a for f, a in ((720, 1.0), (1080, 0.6), (1612, 0.5), (2410, 0.3)))
    tone = tone + _metal(t, (720.0, 1612.0)) * 0.2
    return _finish(_band(tone, 500, 12000) * _decay(t, 0.5), peak=0.8)


def reverse_cymbal():
    x = cymbal(2.2, 0.8, seed=10)[::-1].copy()
    return _finish(x * np.linspace(0.2, 1.0, len(x)), fade=0.01)


def tom(pitch):
    t = _t(0.55)
    body = _sine(pitch * (1.0 + 0.6 * _decay(t, 0.03))) * _decay(t, 0.28) * _attack(t, 0.001)
    overtone = _sine(pitch * 2.4 * (1.0 + 0.3 * _decay(t, 0.03))) * _decay(t, 0.09) * 0.35
    click = _band(_noise(len(t), 11), 1000, 6000) * _decay(t, 0.006) * 0.9
    return _finish(_saturate(body + overtone + click, 1.8))


def rim():
    t = _t(0.09)
    x = np.sin(2 * np.pi * 1700 * t) * _decay(t, 0.008) + np.sin(2 * np.pi * 480 * t) * _decay(t, 0.012) * 0.6
    x += _band(_noise(len(t), 12), 2000, 9000) * _decay(t, 0.002) * 0.5
    return _finish(x)


def cowbell():
    t = _t(0.5)
    tone = (_square(540.0, t) + _square(800.0, t)) * 0.5
    env = _decay(t, 0.09) + 0.3 * _decay(t, 0.35)
    return _finish(_band(tone, 500, 4000) * env)


def shaker():
    t = _t(0.25)
    env = _attack(t, 0.015) * _decay(t, 0.06)
    return _finish(_band(_noise(len(t), 13), 4000, 14000) * env, peak=0.8)


def impact():
    t = _t(3.0)
    boom = _sine(28.0 + 30.0 * _decay(t, 0.25)) * _decay(t, 0.9) * _attack(t, 0.002)
    burst = _band(_noise(len(t), 14), 80, 5000) * _decay(t, 0.08) * 2.2
    tail = _band(_noise(len(t), 15), 150, 6000) * _decay(t, 0.7) * 0.8
    return _finish(_saturate(boom + burst + tail, 2.4))


def riser(length=3.0):
    """White noise swept from low to high, getting louder: the build before a drop."""
    n = int(length * SR)
    noise = _noise(n, 16)
    frame, hop = 2048, 512
    window = np.hanning(frame)
    out = np.zeros(n + frame)
    freqs = np.fft.rfftfreq(frame, 1.0 / SR)
    for start in range(0, n, hop):
        chunk = np.zeros(frame)
        piece = noise[start:start + frame]
        chunk[:len(piece)] = piece
        progress = start / float(n)
        centre = 250.0 * (40.0 ** progress)  # 250 Hz up to 10 kHz
        gain = np.exp(-0.5 * (np.log2(np.maximum(freqs, 1.0) / centre) / 0.6) ** 2)
        out[start:start + frame] += np.fft.irfft(np.fft.rfft(chunk * window) * gain, frame) * window
    out = out[:n]
    t = np.arange(n) / float(SR)
    out *= (t / length) ** 2
    out += np.sin(2 * np.pi * np.cumsum(200.0 * (10.0 ** (t / length))) / SR) * (t / length) ** 3 * 0.15
    return _finish(out, fade=0.03)


def sub_808():
    """The 808 bass: a deep sine with a little punch at the start and a long decay (root C1, note 36)."""
    t = _t(3.5)
    freq = 65.406 * (1.0 + 0.08 * _decay(t, 0.03))
    body = _sine(freq) * _attack(t, 0.003) * _decay(t, 1.4)
    # driven hard enough to add the overtones that let laptop speakers and earbuds carry it
    return _finish(_saturate(body, 3.0), peak=0.9, fade=0.05)


# ----------------------------------------------------------------------
# the house kit (909 style) and the trap kit
# ----------------------------------------------------------------------
def _bandpass(x, centre, width):
    return _band(x, centre - width / 2.0, centre + width / 2.0)


def house_kick():
    """A round kick: a sine falling from about 150 Hz to 52 Hz in 30 ms, gone in about a quarter second,
    with a 10 ms click so it is heard on small speakers."""
    t = _t(0.42)
    freq = 52.0 + 98.0 * _decay(t, 0.03)
    body = _sine(freq) * _decay(t, 0.11) * _attack(t, 0.001)
    click = _band(_noise(len(t), 21), 1500, 8000) * _decay(t, 0.004) * 0.6
    return _finish(_saturate(body + click, 1.8))


def house_snare():
    """The 909 recipe: partials at 180 and 330 Hz with their own decays, and noise in two bands."""
    t = _t(0.35)
    tone = np.sin(2 * np.pi * 180.0 * t) * _decay(t, 0.05) + 0.6 * np.sin(2 * np.pi * 330.0 * t) * _decay(t, 0.035)
    noise = _noise(len(t), 22)
    bright = _band(noise, 4000, 14000) * _decay(t, 0.08)
    body = _band(noise, 800, 6000) * _decay(t, 0.05) * 0.6
    return _finish(_saturate(tone * 0.7 + bright + body, 1.5))


def house_clap():
    """Noise around 1 to 3 kHz in four bursts 10 ms apart, then a 150 ms tail."""
    t = _t(0.45)
    noise = _band(_noise(len(t), 23), 900, 3500)
    env = np.zeros_like(t)
    for start in (0.0, 0.010, 0.020, 0.031):
        env += (t >= start) * np.exp(-np.clip(t - start, 0.0, None) / 0.006)
    env += (t >= 0.031) * 0.55 * np.exp(-np.clip(t - 0.031, 0.0, None) / 0.13)
    return _finish(noise * env)


def metal_hat(length, tau, seed, lo=6000.0, bands=((3440.0, 1600.0), (7100.0, 4000.0))):
    """The 808's six square-wave oscillators through its two band passes (3440 and 7100 Hz), plus a little noise."""
    t = _t(length)
    metal = _metal(t, HAT_FREQS)
    tone = sum(_bandpass(metal, centre, width) for centre, width in bands) + 0.25 * _noise(len(t), seed)
    return _finish(_band(tone, lo, 17000) * _decay(t, tau) * _attack(t, 0.0005), peak=0.85)


def house_open_hat():
    return metal_hat(0.7, 0.18, 24, lo=5500.0)


def trap_kick():
    """Sharp and short (a pitch snap of an octave and more in 20 ms, decaying in about 120 ms), so the 808 has room."""
    t = _t(0.3)
    freq = 55.0 + 180.0 * _decay(t, 0.02)
    body = _sine(freq) * _decay(t, 0.07) * _attack(t, 0.0008)
    click = _band(_noise(len(t), 25), 2500, 10000) * _decay(t, 0.003) * 0.9
    return _finish(_saturate(body + click, 2.6))


def trap_808():
    """The 808 boom: a long sine at 49 Hz (G1) with a quick drop at the start, saturated for small speakers."""
    t = _t(2.4)
    freq = 49.0 * (1.0 + 0.5 * _decay(t, 0.015))
    body = _sine(freq) * _decay(t, 0.9) * _attack(t, 0.002)
    return _finish(_saturate(body, 2.2), fade=0.05)


def trap_clap():
    """A crisp digital clap layered with a short bright snare."""
    t = _t(0.3)
    noise = _band(_noise(len(t), 26), 1200, 7000)
    env = np.zeros_like(t)
    for start in (0.0, 0.007, 0.015):
        env += (t >= start) * np.exp(-np.clip(t - start, 0.0, None) / 0.005)
    env += (t >= 0.015) * 0.4 * np.exp(-np.clip(t - 0.015, 0.0, None) / 0.07)
    snap = _band(_noise(len(t), 27), 3000, 12000) * _decay(t, 0.04) * 0.5
    snap += np.sin(2 * np.pi * 220 * t) * _decay(t, 0.03) * 0.3
    return _finish(_saturate(noise * env + snap, 1.3))


def trap_snare():
    t = _t(0.25)
    tone = _sine(240.0 + 80.0 * _decay(t, 0.01)) * _decay(t, 0.04)
    crack = _band(_noise(len(t), 28), 2500, 12000) * _decay(t, 0.06)
    return _finish(_saturate(tone * 0.6 + crack, 1.8))


def trap_rim():
    t = _t(0.06)
    x = np.sin(2 * np.pi * 1900 * t) * _decay(t, 0.006) + 0.5 * np.sin(2 * np.pi * 520 * t) * _decay(t, 0.01)
    return _finish(x + _band(_noise(len(t), 29), 3000, 10000) * _decay(t, 0.0015) * 0.4)


def soft_tom(pitch, seed):
    """An electronic tom: a sine with a small pitch drop."""
    t = _t(0.45)
    body = _sine(pitch * (1.0 + 0.35 * _decay(t, 0.04))) * _decay(t, 0.2) * _attack(t, 0.001)
    click = _band(_noise(len(t), seed), 1000, 5000) * _decay(t, 0.004) * 0.5
    return _finish(_saturate(body + click, 1.4))


# ----------------------------------------------------------------------
# the SoundFont
# ----------------------------------------------------------------------
def build_kit(path):
    """Synthesize every sound and write the SoundFont. Returns its size in bytes."""
    samples = []

    def add(name, data, root=60):
        samples.append(Sample(name, data, SR, root))
        return len(samples) - 1

    drum_release = timecents(4.0)   # a released key lets the hit ring out
    zones = []

    def drum(note, data, name, attenuation=0, pan=0, choke=None, vel=(0, 127)):
        index = add(name, data, note)
        gens = {GEN_OVERRIDING_ROOT_KEY: note, GEN_RELEASE_VOL_ENV: drum_release, GEN_SAMPLE_MODES: 0}
        if attenuation:
            gens[GEN_INITIAL_ATTENUATION] = attenuation
        if pan:
            gens[GEN_PAN] = pan
        if choke:
            gens[GEN_EXCLUSIVE_CLASS] = choke
        zones.append(Zone(index, (note, note), vel, gens))

    drum(36, kick(False), "Kick soft", attenuation=40, vel=(0, 89))
    drum(36, kick(True), "Kick hard", attenuation=20, vel=(90, 127))
    drum(35, deep_kick(), "Deep 808 kick", attenuation=30)
    drum(38, snare(False), "Snare soft", attenuation=50, vel=(0, 89))
    drum(38, snare(True), "Snare hard", attenuation=30, vel=(90, 127))
    drum(40, clap_snare(), "Clap snare", attenuation=30)
    drum(39, clap(), "Clap", attenuation=50)
    drum(37, rim(), "Rim snap", attenuation=50)
    drum(42, hat(0.12, 0.018), "Closed hat", attenuation=80, pan=150, choke=1)
    drum(44, hat(0.18, 0.03, lo=5000.0, seed=17), "Pedal hat", attenuation=85, pan=150, choke=1)
    drum(46, hat(0.8, 0.16, seed=18), "Open hat", attenuation=80, pan=150, choke=1)
    for note, pitch, pan in ((41, 72.0, -250), (45, 96.0, -100), (48, 128.0, 100), (50, 160.0, 250)):
        drum(note, tom(pitch), "Tom {}".format(note), attenuation=30, pan=pan)
    drum(49, cymbal(), "Crash", attenuation=80, pan=-200)
    drum(57, reverse_cymbal(), "Reverse cymbal", attenuation=60)
    drum(51, ride(), "Ride", attenuation=80, pan=200)
    drum(53, ride_bell(), "Ride bell", attenuation=80, pan=200)
    drum(52, impact(), "Impact", attenuation=60)
    drum(55, riser(), "Riser", attenuation=50)
    drum(54, shaker(), "Shaker", attenuation=90, pan=150)
    drum(56, cowbell(), "808 cowbell", attenuation=70, pan=-100)
    kit = Instrument(DUBSTEP_KIT_NAME, zones)

    zones = []
    drum(36, house_kick(), "House kick", attenuation=20)
    drum(35, house_kick(), "House kick 2", attenuation=40)
    drum(38, house_snare(), "House snare", attenuation=40)
    drum(40, house_snare(), "House snare 2", attenuation=50)
    drum(39, house_clap(), "House clap", attenuation=30)
    drum(37, rim(), "House rim", attenuation=60)
    drum(42, metal_hat(0.1, 0.022, 30), "House closed hat", attenuation=90, pan=120, choke=1)
    drum(44, metal_hat(0.12, 0.03, 31, lo=5000.0), "House pedal hat", attenuation=95, pan=120, choke=1)
    drum(46, house_open_hat(), "House open hat", attenuation=85, pan=120, choke=1)
    for note, pitch, pan in ((41, 80.0, -250), (45, 104.0, -100), (48, 136.0, 100), (50, 170.0, 250)):
        drum(note, soft_tom(pitch, 32 + note), "House tom {}".format(note), attenuation=40, pan=pan)
    drum(49, cymbal(2.4, 0.8, seed=33), "House crash", attenuation=90, pan=-200)
    drum(57, cymbal(2.0, 0.7, seed=34), "House crash 2", attenuation=90, pan=200)
    drum(51, ride(), "House ride", attenuation=85, pan=200)
    drum(53, ride_bell(), "House ride bell", attenuation=85, pan=200)
    drum(54, shaker(), "House shaker", attenuation=95, pan=-150)
    drum(56, cowbell(), "House cowbell", attenuation=75, pan=-100)
    house_kit = Instrument(HOUSE_KIT_NAME, zones)

    zones = []
    drum(36, trap_kick(), "Trap kick", attenuation=20)
    drum(35, trap_808(), "Trap 808", attenuation=30)
    drum(38, trap_snare(), "Trap snare", attenuation=40)
    drum(40, trap_snare(), "Trap snare 2", attenuation=50)
    drum(39, trap_clap(), "Trap clap", attenuation=30)
    drum(37, trap_rim(), "Trap rim", attenuation=50)
    drum(42, metal_hat(0.06, 0.012, 40, lo=7000.0), "Trap closed hat", attenuation=90, pan=100, choke=1)
    drum(44, metal_hat(0.08, 0.02, 41, lo=6000.0), "Trap pedal hat", attenuation=95, pan=100, choke=1)
    drum(46, metal_hat(0.5, 0.12, 42, lo=6000.0), "Trap open hat", attenuation=88, pan=100, choke=1)
    for note, pitch, pan in ((41, 70.0, -250), (45, 95.0, -100), (48, 125.0, 100), (50, 160.0, 250)):
        drum(note, soft_tom(pitch, 43 + note), "Trap tom {}".format(note), attenuation=40, pan=pan)
    drum(49, cymbal(2.2, 0.7, seed=44), "Trap crash", attenuation=90, pan=-200)
    drum(57, reverse_cymbal(), "Trap reverse cymbal", attenuation=70)
    drum(51, ride(), "Trap ride", attenuation=85, pan=200)
    drum(54, shaker(), "Trap shaker", attenuation=95, pan=-150)
    drum(56, cowbell(), "Trap cowbell", attenuation=75, pan=-100)
    trap_kit = Instrument(TRAP_KIT_NAME, zones)

    sub = add("808 sub C1", sub_808(), 36)
    sub_zone = Zone(sub, (0, 127), (0, 127), {GEN_RELEASE_VOL_ENV: timecents(0.15), GEN_SAMPLE_MODES: 0,
                                              GEN_INITIAL_ATTENUATION: 40})
    sub_inst = Instrument(SUB_808_NAME, [sub_zone])

    presets = [Preset(DUBSTEP_KIT_NAME, 128, DUBSTEP_KIT_PROGRAM, 0),
               Preset(SUB_808_NAME, FORGE_BANK, SUB_808_PROGRAM, 1),
               Preset(HOUSE_KIT_NAME, 128, HOUSE_KIT_PROGRAM, 2),
               Preset(TRAP_KIT_NAME, 128, TRAP_KIT_PROGRAM, 3)]
    return write_sf2(path, "Musician Forge Kits {}".format(KIT_VERSION), samples,
                     [kit, sub_inst, house_kit, trap_kit], presets,
                     copyright_text="Musician Forge. Synthesized sounds, free to use in any music.",
                     comment="Made by Musician Forge from scratch: no outside samples.")
