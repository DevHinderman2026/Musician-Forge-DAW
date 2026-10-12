"""A very small built-in synthesizer.

Used when the FluidSynth engine is missing (so Musician Forge still makes sound
and can tell you what is wrong), and in automated tests, where its clean
tones make timing easy to measure. Same interface as fluid.FluidSynth.
"""

import math

import numpy as np

from .fluid import Preset


class _Voice:
    __slots__ = ("freq", "phase", "amp", "level", "releasing", "drum", "noise_left")

    def __init__(self, freq, amp, drum):
        self.freq, self.amp, self.drum = freq, amp, drum
        self.phase = math.pi / 2  # start at a peak so the first sample is never silent
        self.level = 0.0
        self.releasing = False
        self.noise_left = 2400 if drum else 0


class SimpleSynth:
    ATTACK_SECONDS = 0.002
    RELEASE_SECONDS = 0.05

    def __init__(self, sample_rate=48000, channels=128, **_ignored):
        self.sample_rate = int(sample_rate)
        self.channels = channels
        self.voices = {}
        self.volume = [100] * channels
        self.pan = [64] * channels
        self.drum = [False] * channels
        self.instruments = {}
        self.soundfont_path = None
        self.events = []  # (kind, channel, key, velocity) - handy for tests
        self._rng = np.random.default_rng(1)

    def load_soundfont(self, path):
        self.soundfont_path = path
        return 1

    def presets(self):
        names = ["Sine Piano", "Sine Organ"]
        result = [Preset(0, i, n) for i, n in enumerate(names)]
        result.append(Preset(128, 0, "Noise Drums"))
        return result

    def set_instrument(self, channel, bank, program, drum=False):
        self.drum[channel] = bool(drum)
        self.instruments[channel] = (bank, program)
        return True

    def noteon(self, channel, key, velocity):
        self.events.append(("on", channel, key, velocity))
        if velocity <= 0:
            self.noteoff(channel, key)
            return
        freq = 440.0 * 2 ** ((key - 69) / 12.0)
        self.voices[(channel, key)] = _Voice(freq, 0.25 * velocity / 127.0, self.drum[channel])

    def noteoff(self, channel, key):
        self.events.append(("off", channel, key, 0))
        voice = self.voices.get((channel, key))
        if voice is not None:
            voice.releasing = True

    def cc(self, channel, controller, value):
        if controller == 7:
            self.volume[channel] = value
        elif controller == 10:
            self.pan[channel] = value

    def pitch_bend(self, channel, value):
        pass

    def all_notes_off(self, channel=-1):
        for (ch, _key), voice in self.voices.items():
            if channel < 0 or ch == channel:
                voice.releasing = True

    def all_sounds_off(self, channel=-1):
        for key in [k for k in self.voices if channel < 0 or k[0] == channel]:
            del self.voices[key]

    def set_gain(self, gain):
        pass

    def render_channels(self, frames, planar, offset, fx=None):
        """Add each channel's sound to its own two rows of `planar` (see fluid.FluidSynth)."""
        if frames <= 0 or not self.voices:
            return
        sr = self.sample_rate
        attack_step = 1.0 / max(1, int(self.ATTACK_SECONDS * sr))
        release_step = 1.0 / max(1, int(self.RELEASE_SECONDS * sr))
        n = np.arange(frames)
        finished = []
        end = offset + frames
        for (channel, key), v in self.voices.items():
            if v.releasing:
                env = np.maximum(0.0, v.level - release_step * (n + 1))
                v.level = float(env[-1])
                if v.level <= 0.0:
                    finished.append((channel, key))
            else:
                env = np.minimum(1.0, v.level + attack_step * (n + 1))
                env[0] = max(env[0], attack_step)
                v.level = float(env[-1])
            if v.drum:
                tone = self._rng.uniform(-1, 1, frames)
                decay = np.clip((v.noise_left - n) / 2400.0, 0, 1)
                v.noise_left = max(0, v.noise_left - frames)
                tone *= decay
                if v.noise_left == 0:
                    v.releasing = True
            else:
                tone = np.cos(v.phase - math.pi / 2 + 2 * math.pi * v.freq * n / sr)
                v.phase = (v.phase + 2 * math.pi * v.freq * frames / sr) % (2 * math.pi)
            gain = v.amp * (self.volume[channel] / 127.0)
            pan = max(-1.0, min(1.0, (self.pan[channel] - 64) / 63.0))   # CC 0 is a little past -1
            left = gain * math.sqrt(0.5 * (1 - pan))
            right = gain * math.sqrt(0.5 * (1 + pan))
            signal = tone * env
            planar[2 * channel, offset:end] += (signal * left).astype(np.float32)
            planar[2 * channel + 1, offset:end] += (signal * right).astype(np.float32)
        for key in finished:
            del self.voices[key]

    def render(self, frames, out=None):
        if out is None:
            out = np.zeros((frames, 2), dtype=np.float32)
        else:
            out.fill(0.0)
        if frames <= 0 or not self.voices:
            return out
        planar = np.zeros((2 * self.channels, frames), dtype=np.float32)
        self.render_channels(frames, planar, 0)
        out[:, 0] = planar[0::2].sum(axis=0)
        out[:, 1] = planar[1::2].sum(axis=0)
        return out

    def close(self):
        self.voices.clear()
