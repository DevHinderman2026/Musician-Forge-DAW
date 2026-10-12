"""Effects: EQ, compressor, distortion, delay, reverb, and pitch correction for audio tracks.

Each track has a list of effects that its sound passes through, top to bottom, before its
volume and pan. Every effect has a short list of settings (each with a clear spoken name and
unit), starts from a preset, and every setting can still be changed. In a project file an effect
is a small dictionary:

    {"type": "reverb", "on": true, "preset": "Hall", "params": {"size": 70, "decay": 2.6, ...}}

The sound itself is made by the processor classes at the bottom, which the engine runs a block
at a time (see dsp.py for how numpy keeps them fast enough for real time). Pitch correction is
different: it is worked out ahead of time for each recording (pitchfix.py), so it is not in
the real-time chain at all.
"""

import copy
import math
from dataclasses import dataclass

import numpy as np

from . import dsp

INSTRUMENT, AUDIO = "instrument", "audio"


@dataclass(frozen=True)
class Param:
    """One setting of an effect.

    kind: "number" (a number box: Up and Down arrows step it), "percent" (a slider from 0 to
    100), "choice" (a list) or "switch" (a check box). choices: [(value, spoken name)].
    """

    key: str
    label: str
    kind: str = "number"
    low: float = 0.0
    high: float = 100.0
    step: float = 1.0
    default: object = 0.0
    unit: str = ""
    choices: tuple = ()
    automatable: bool = False
    decimals: int = 0

    def clamp(self, value, fallback=None):
        """The value made valid: kept in range and rounded. Nonsense becomes `fallback`
        (or this setting's default)."""
        fallback = self.default if fallback is None else fallback
        if self.kind == "switch":
            return bool(value)
        if self.kind == "choice":
            values = [v for v, _name in self.choices]
            return value if value in values else fallback
        try:
            number = float(value)
        except (TypeError, ValueError):
            return fallback
        if math.isnan(number):
            return fallback
        number = min(self.high, max(self.low, number))
        if self.decimals == 0:
            return int(round(number))
        return round(number, self.decimals)

    def spoken(self, value):
        """The value as it is said: "minus 3 dB", "4 to 1", "Quarter note", "on"."""
        if self.kind == "switch":
            return "on" if value else "off"
        if self.kind == "choice":
            return dict(self.choices).get(value, str(value))
        if self.kind == "percent":
            return "{} percent".format(format_value(value))
        text = format_value(value)
        if self.unit:
            text = "{} {}".format(text, self.unit)
        return text


def format_value(value):
    """2, 2.5, -3 (no trailing zeros)."""
    if isinstance(value, bool):
        return "on" if value else "off"
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    text = "{:.2f}".format(float(value)).rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


@dataclass(frozen=True)
class EffectType:
    key: str
    name: str
    description: str
    params: tuple
    presets: tuple              # ((name, {key: value}), ...); the first is the default
    kinds: tuple = (INSTRUMENT, AUDIO)

    def param(self, key):
        for p in self.params:
            if p.key == key:
                return p
        raise KeyError(key)

    def defaults(self):
        values = {p.key: p.default for p in self.params}
        values.update(self.presets[0][1])
        return values

    def preset_values(self, name):
        for preset_name, values in self.presets:
            if preset_name == name:
                full = {p.key: p.default for p in self.params}
                full.update(values)
                return full
        raise KeyError(name)

    def preset_names(self):
        return [name for name, _values in self.presets]


DELAY_NOTES = (("whole", "Whole note", 4.0), ("half", "Half note", 2.0), ("dotted_quarter", "Dotted quarter note", 1.5),
               ("quarter", "Quarter note", 1.0), ("dotted_eighth", "Dotted eighth note", 0.75),
               ("eighth", "Eighth note", 0.5), ("eighth_triplet", "Eighth note triplet", 1.0 / 3.0),
               ("sixteenth", "Sixteenth note", 0.25), ("ms", "Milliseconds (the next box)", None))
DELAY_BEATS = {key: beats for key, _name, beats in DELAY_NOTES}

EQ = EffectType(
    "eq", "EQ",
    "Shapes the tone: cuts the lowest rumble, and turns the bass, middle and treble up or down.",
    (
        Param("low_cut", "Low cut in hertz (0 turns it off)", low=0, high=500, step=10, default=0, unit="hertz",
              automatable=True),
        Param("low_gain", "Bass in dB", low=-15, high=15, step=0.5, default=0.0, unit="dB", automatable=True,
              decimals=1),
        Param("low_freq", "Bass frequency in hertz", low=40, high=500, step=10, default=120, unit="hertz"),
        Param("mid_gain", "Middle in dB", low=-15, high=15, step=0.5, default=0.0, unit="dB", automatable=True,
              decimals=1),
        Param("mid_freq", "Middle frequency in hertz", low=200, high=8000, step=50, default=1000, unit="hertz",
              automatable=True),
        Param("mid_width", "Middle width", kind="choice", default="medium",
              choices=(("narrow", "Narrow"), ("medium", "Medium"), ("wide", "Wide"))),
        Param("high_gain", "Treble in dB", low=-15, high=15, step=0.5, default=0.0, unit="dB", automatable=True,
              decimals=1),
        Param("high_freq", "Treble frequency in hertz", low=1500, high=16000, step=250, default=8000, unit="hertz"),
        Param("high_cut", "High cut in hertz (20000 turns it off)", low=1000, high=20000, step=250, default=20000,
              unit="hertz", automatable=True),
        Param("output", "Output level in dB", low=-12, high=12, step=0.5, default=0.0, unit="dB", automatable=True,
              decimals=1),
    ),
    (
        ("Flat", {}),
        ("Warm", {"low_gain": 3.0, "low_freq": 150, "high_gain": -2.0, "high_freq": 7000}),
        ("Bright", {"low_cut": 40, "high_gain": 4.0, "high_freq": 8000}),
        ("Cut the mud", {"low_cut": 60, "mid_gain": -4.0, "mid_freq": 300, "mid_width": "wide"}),
        ("Vocal presence", {"low_cut": 90, "mid_gain": 3.0, "mid_freq": 3000, "high_gain": 2.0, "high_freq": 10000}),
        ("Bass boost", {"low_gain": 6.0, "low_freq": 80}),
        ("Telephone", {"low_cut": 400, "high_cut": 3500, "mid_gain": 4.0, "mid_freq": 1500, "output": 2.0}),
    ),
)

COMPRESSOR = EffectType(
    "compressor", "Compressor",
    "Evens out the volume: loud moments are turned down, so the part sounds steadier and fuller.",
    (
        Param("threshold", "Threshold in dB (sounds louder than this are turned down)", low=-60, high=0, step=1,
              default=-18, unit="dB", automatable=True),
        Param("ratio", "Ratio (how strongly, 4 means 4 to 1)", low=1, high=20, step=0.5, default=4.0, unit="to 1",
              decimals=1),
        Param("attack", "Attack in milliseconds", low=0.5, high=100, step=0.5, default=10.0, unit="milliseconds",
              decimals=1),
        Param("release", "Release in milliseconds", low=20, high=1000, step=10, default=150, unit="milliseconds"),
        Param("makeup", "Make-up gain in dB", low=0, high=24, step=0.5, default=4.0, unit="dB", automatable=True,
              decimals=1),
        Param("mix", "Mix (100 is fully compressed)", kind="percent", default=100, automatable=True),
    ),
    (
        ("Gentle", {"threshold": -18, "ratio": 2.0, "attack": 20.0, "release": 200, "makeup": 2.0}),
        ("Vocal", {"threshold": -20, "ratio": 4.0, "attack": 5.0, "release": 120, "makeup": 5.0}),
        ("Drum punch", {"threshold": -15, "ratio": 4.0, "attack": 25.0, "release": 100, "makeup": 4.0}),
        ("Even bass", {"threshold": -22, "ratio": 5.0, "attack": 10.0, "release": 150, "makeup": 6.0}),
        ("Heavy squash", {"threshold": -30, "ratio": 12.0, "attack": 1.0, "release": 80, "makeup": 10.0}),
        ("Parallel", {"threshold": -30, "ratio": 8.0, "attack": 2.0, "release": 100, "makeup": 8.0, "mix": 40}),
    ),
)

DISTORTION = EffectType(
    "distortion", "Distortion",
    "Drives the sound until it breaks up: warm overdrive, crunch, fuzz, or gritty digital bit crushing. "
    "Good for guitars, bass and dubstep growls.",
    (
        Param("character", "Character", kind="choice", default="soft",
              choices=(("soft", "Soft (warm overdrive)"), ("hard", "Hard (crunchy)"), ("fuzz", "Fuzz (lopsided)"),
                       ("crush", "Bit crusher (gritty digital)"))),
        Param("drive", "Drive in dB", low=0, high=48, step=1, default=18, unit="dB", automatable=True),
        Param("tone", "Tone in hertz (lower is darker)", low=500, high=16000, step=250, default=6000, unit="hertz",
              automatable=True),
        Param("output", "Output level in dB", low=-24, high=6, step=0.5, default=-6.0, unit="dB", automatable=True,
              decimals=1),
        Param("mix", "Mix (100 is fully distorted)", kind="percent", default=100, automatable=True),
    ),
    (
        ("Warm overdrive", {"character": "soft", "drive": 12, "tone": 7000, "output": -4.0}),
        ("Crunch", {"character": "hard", "drive": 20, "tone": 5000, "output": -8.0}),
        ("Heavy", {"character": "hard", "drive": 36, "tone": 4500, "output": -12.0}),
        ("Fuzz", {"character": "fuzz", "drive": 30, "tone": 3500, "output": -10.0}),
        ("Dubstep growl", {"character": "fuzz", "drive": 40, "tone": 9000, "output": -12.0}),
        ("Lo-fi", {"character": "crush", "drive": 16, "tone": 8000, "output": -2.0}),
    ),
)

DELAY = EffectType(
    "delay", "Delay",
    "Echoes: repeats the sound in time with the song (or every so many milliseconds).",
    (
        Param("time", "Echo time", kind="choice", default="quarter",
              choices=tuple((key, name) for key, name, _beats in DELAY_NOTES)),
        Param("time_ms", "Echo time in milliseconds (when Echo time is Milliseconds)", low=10, high=2000, step=10,
              default=300, unit="milliseconds"),
        Param("feedback", "Feedback (how many echoes)", kind="percent", default=35, automatable=True),
        Param("tone", "Echo tone in hertz (lower makes darker echoes)", low=500, high=16000, step=250,
              default=5000, unit="hertz", automatable=True),
        Param("ping_pong", "Ping-pong: echoes bounce between left and right", kind="switch", default=False),
        Param("mix", "Mix (how loud the echoes are)", kind="percent", default=25, automatable=True),
    ),
    (
        ("Quarter note echo", {"time": "quarter", "feedback": 35, "mix": 25}),
        ("Slapback", {"time": "ms", "time_ms": 110, "feedback": 10, "tone": 6000, "mix": 25}),
        ("Dotted eighth", {"time": "dotted_eighth", "feedback": 35, "mix": 22}),
        ("Ping-pong eighths", {"time": "eighth", "feedback": 40, "ping_pong": True, "mix": 25}),
        ("Long ambient", {"time": "half", "feedback": 60, "tone": 2500, "mix": 30}),
        ("Dub echo", {"time": "dotted_quarter", "feedback": 70, "tone": 1800, "mix": 35}),
    ),
)

REVERB = EffectType(
    "reverb", "Reverb",
    "The sound of a space: from a small room to a cathedral.",
    (
        Param("size", "Room size", kind="percent", default=50),
        Param("decay", "Decay time in seconds", low=0.2, high=12, step=0.1, default=2.0, unit="seconds",
              automatable=True, decimals=1),
        Param("brightness", "Brightness (lower sounds darker and warmer)", kind="percent", default=60,
              automatable=True),
        Param("predelay", "Pre-delay in milliseconds", low=0, high=250, step=5, default=15, unit="milliseconds"),
        Param("width", "Stereo width", kind="percent", default=100),
        Param("mix", "Mix (how much reverb)", kind="percent", default=25, automatable=True),
    ),
    (
        ("Medium room", {"size": 45, "decay": 1.2, "brightness": 55, "predelay": 10, "mix": 22}),
        ("Small room", {"size": 25, "decay": 0.6, "brightness": 55, "predelay": 5, "mix": 20}),
        ("Vocal booth", {"size": 12, "decay": 0.4, "brightness": 60, "predelay": 0, "mix": 15}),
        ("Hall", {"size": 70, "decay": 2.6, "brightness": 50, "predelay": 25, "mix": 25}),
        ("Cathedral", {"size": 100, "decay": 6.5, "brightness": 40, "predelay": 40, "mix": 30}),
        ("Plate", {"size": 40, "decay": 1.8, "brightness": 80, "predelay": 0, "mix": 25}),
        ("Big space", {"size": 85, "decay": 4.0, "brightness": 45, "predelay": 30, "mix": 20}),
    ),
)

PITCH = EffectType(
    "pitch", "Pitch correction",
    "Pulls a recorded voice or instrument onto the notes of the song's key. Audio tracks only. "
    "It is worked out for each recording, so it is not heard while you record.",
    (
        Param("speed", "Speed in milliseconds (0 snaps at once, larger sounds more natural)", low=0, high=400,
              step=10, default=60, unit="milliseconds"),
        Param("strength", "Strength (100 is fully on the note)", kind="percent", default=100),
        Param("scale", "Notes to use", kind="choice", default="key",
              choices=(("key", "The song's key (follows key changes)"), ("chromatic", "Every note (chromatic)"))),
    ),
    (
        ("Natural", {"speed": 120, "strength": 80}),
        ("Tight", {"speed": 40, "strength": 100}),
        ("Robotic", {"speed": 0, "strength": 100}),
        ("Gentle", {"speed": 220, "strength": 60}),
    ),
    kinds=(AUDIO,),
)

TYPES = (EQ, COMPRESSOR, DISTORTION, DELAY, REVERB, PITCH)
TYPE_BY_KEY = {t.key: t for t in TYPES}
MAX_EFFECTS = 8


def types_for(track_kind):
    """The effects that can go on a track: every one on an audio track; pitch correction is
    for recordings, so instrument tracks don't offer it."""
    return [t for t in TYPES if track_kind in t.kinds]


def new_effect(type_key, preset=None):
    """A new effect, starting from its first preset (or the one named)."""
    kind = TYPE_BY_KEY[type_key]
    name = preset or kind.presets[0][0]
    return {"type": type_key, "on": True, "preset": name, "params": kind.preset_values(name)}


def clean_effect(raw):
    """A valid effect from a project file (unknown or damaged values become defaults), or None."""
    if not isinstance(raw, dict) or raw.get("type") not in TYPE_BY_KEY:
        return None
    kind = TYPE_BY_KEY[raw["type"]]
    params = kind.defaults()
    stored = raw.get("params") if isinstance(raw.get("params"), dict) else {}
    for p in kind.params:
        if p.key in stored:
            params[p.key] = p.clamp(stored[p.key], params[p.key])
    preset = str(raw.get("preset", "")) or kind.presets[0][0]
    effect = {"type": kind.key, "on": bool(raw.get("on", True)), "preset": preset, "params": params}
    if isinstance(raw.get("id"), int) and not isinstance(raw.get("id"), bool):
        effect["id"] = raw["id"]
    return effect


def ensure_ids(effects):
    """Give every effect on a track an id of its own that never changes (automation lanes name
    their effect by it). Effects from before version 0.9 get one; duplicates get new ones."""
    used = set()
    for effect in effects:
        if isinstance(effect.get("id"), int) and effect["id"] not in used:
            used.add(effect["id"])
        else:
            effect.pop("id", None)
    following = max(used, default=0) + 1
    for effect in effects:
        if "id" not in effect:
            effect["id"] = following
            used.add(following)
            following += 1
    return effects


def clean_effects(raw_list, track_kind):
    effects = []
    for raw in raw_list or []:
        effect = clean_effect(raw)
        if effect is not None and track_kind in TYPE_BY_KEY[effect["type"]].kinds:
            effects.append(effect)
    return ensure_ids(effects[:MAX_EFFECTS])


def matching_preset(effect):
    """The preset whose settings are exactly the effect's, or None (changed settings)."""
    kind = TYPE_BY_KEY[effect["type"]]
    names = [effect.get("preset")] + kind.preset_names()
    for name in names:
        try:
            values = kind.preset_values(name)
        except KeyError:
            continue
        if all(values[p.key] == effect["params"].get(p.key) for p in kind.params):
            return name
    return None


def describe_effect(effect, number=None):
    """'1. Reverb, Hall, on' or '2. EQ, your own settings (from Warm), off'."""
    kind = TYPE_BY_KEY[effect["type"]]
    preset = matching_preset(effect)
    setting = preset if preset else "your own settings (from {})".format(effect.get("preset") or "scratch")
    text = "{}, {}, {}".format(kind.name, setting, "on" if effect.get("on", True) else "off")
    return "{}. {}".format(number, text) if number is not None else text


def describe_settings(effect):
    """Every setting in words: 'Room size 70 percent, Decay time 2.6 seconds, ...'."""
    kind = TYPE_BY_KEY[effect["type"]]
    parts = []
    for p in kind.params:
        label = p.label.split(" (")[0]
        for unit_words in (" in dB", " in hertz", " in milliseconds", " in seconds"):
            label = label.replace(unit_words, "")
        parts.append("{} {}".format(label, p.spoken(effect["params"][p.key])))
    return ", ".join(parts)


def automatable_params(effect):
    return [p for p in TYPE_BY_KEY[effect["type"]].params if p.automatable]


# ----------------------------------------------------------------------
# processors: the real-time sound of each effect
# ----------------------------------------------------------------------
SILENCE = 1e-7          # quieter than this (about -140 dB) counts as silence


class Context:
    """What the effects need to know about the song right now."""

    __slots__ = ("bpm",)

    def __init__(self, bpm=120.0):
        self.bpm = float(bpm)


def _wet_dry(mix_percent):
    """Mix 0 to 100 as (dry gain, wet gain): the dry sound stays full until halfway."""
    mix = min(1.0, max(0.0, float(mix_percent) / 100.0))
    return min(1.0, 2.0 * (1.0 - mix)), min(1.0, 2.0 * mix)


class Processor:
    tail_seconds = 0.0

    def __init__(self, sample_rate, params):
        self.sample_rate = float(sample_rate)
        self.params = dict(params)

    def update(self, params):
        self.params = dict(params)

    def process(self, block, context):
        return block


class EqProcessor(Processor):
    WIDTH_Q = {"narrow": 2.5, "medium": 1.0, "wide": 0.5}

    def __init__(self, sample_rate, params):
        super().__init__(sample_rate, params)
        self.filters = dsp.FilterCascade(sample_rate, 2)
        self._gain = dsp.db_to_gain(params["output"])
        self.update(params)

    def sections(self, params):
        sections = []
        if params["low_cut"] > 0:
            sections.append(("highpass", max(10.0, params["low_cut"]), 0.7071, 0.0))
        if params["low_gain"] != 0:
            sections.append(("lowshelf", params["low_freq"], 0.7071, params["low_gain"]))
        if params["mid_gain"] != 0:
            sections.append(("bell", params["mid_freq"], self.WIDTH_Q.get(params["mid_width"], 1.0),
                             params["mid_gain"]))
        if params["high_gain"] != 0:
            sections.append(("highshelf", params["high_freq"], 0.7071, params["high_gain"]))
        if params["high_cut"] < 20000:
            sections.append(("lowpass", params["high_cut"], 0.7071, 0.0))
        return sections

    def update(self, params):
        self.params = dict(params)
        self.filters.set_sections(self.sections(self.params))

    def process(self, block, context):
        y = self.filters.process(block)
        target = dsp.db_to_gain(self.params["output"])
        y *= dsp.ramp(self._gain, target, len(y))
        self._gain = target
        return y


class CompressorProcessor(Processor):
    STEP = 32           # the gain is worked out every 32 samples (two thirds of a millisecond)
    KNEE_DB = 6.0
    tail_seconds = 1.0

    def __init__(self, sample_rate, params):
        super().__init__(sample_rate, params)
        self.envelope = -120.0          # detected level in dB
        self.gain_db = 0.0              # gain applied at the end of the last block
        self.reduction = 0.0            # latest gain reduction in dB (for "how much is it working")
        self._dry, self._wet = _wet_dry(params["mix"])

    def _reduction(self, level):
        p = self.params
        over = level - p["threshold"]
        slope = 1.0 / max(1.0, p["ratio"]) - 1.0
        half = self.KNEE_DB / 2.0
        if over <= -half:
            return 0.0
        if over < half:
            return slope * (over + half) ** 2 / (2.0 * self.KNEE_DB)
        return slope * over

    def process(self, block, context):
        p = self.params
        frames = len(block)
        if frames == 0:
            return block
        step = self.STEP
        attack = math.exp(-step / (max(0.05, p["attack"]) / 1000.0 * self.sample_rate))
        release = math.exp(-step / (max(1.0, p["release"]) / 1000.0 * self.sample_rate))
        level = np.abs(block).max(axis=1)
        count = -(-frames // step)
        padded = np.zeros(count * step)
        padded[:frames] = level
        peaks = padded.reshape(count, step).max(axis=1)
        peaks_db = 20.0 * np.log10(np.maximum(peaks, 1e-6))
        gains = np.empty(count + 1)
        gains[0] = self.gain_db
        env = self.envelope
        makeup = p["makeup"]
        for i in range(count):
            target = peaks_db[i]
            coef = attack if target > env else release
            env = coef * env + (1.0 - coef) * target
            gains[i + 1] = self._reduction(env) + makeup
        self.envelope = env
        self.reduction = -(gains[-1] - makeup)
        self.gain_db = gains[-1]
        # a smooth line through the gains, one point every STEP samples
        positions = (np.arange(frames) + 1.0) / step
        curve = np.interp(positions, np.arange(count + 1), gains)
        wet = block * (10.0 ** (curve / 20.0))[:, None]
        dry_gain, wet_gain = _wet_dry(p["mix"])
        if dry_gain == 0.0 and self._dry == 0.0:
            out = wet * wet_gain
        else:
            out = block * dsp.ramp(self._dry, dry_gain, frames) + wet * dsp.ramp(self._wet, wet_gain, frames)
        self._dry, self._wet = dry_gain, wet_gain
        return out


class DistortionProcessor(Processor):
    FUZZ_BIAS = 0.35

    def __init__(self, sample_rate, params):
        super().__init__(sample_rate, params)
        self.tone = dsp.StateVariableFilter(sample_rate, 2, "lowpass", params["tone"])
        self.dc = dsp.DCBlocker(sample_rate, 2)
        self._drive = dsp.db_to_gain(params["drive"])
        self._out = dsp.db_to_gain(params["output"])
        self._dry, self._wet = _wet_dry(params["mix"])
        self._hold = np.zeros(2)        # bit crusher: the value being held
        self._hold_left = 0             # bit crusher: samples until the next new value

    def update(self, params):
        self.params = dict(params)
        self.tone.set("lowpass", params["tone"])

    def _crush(self, x):
        depth = self.params["drive"] / 48.0              # 0 to 1
        bits = 12.0 - 9.0 * depth                         # 12 bits down to 3
        factor = max(1, int(round(1 + 15 * depth)))     # keep every sample, down to every 16th
        frames = len(x)
        held = np.empty_like(x)
        position = 0
        if self._hold_left > 0:
            take = min(self._hold_left, frames)
            held[:take] = self._hold
            self._hold_left -= take
            position = take
        if position < frames:
            picks = np.arange(position, frames, factor)
            values = x[picks]
            index = np.repeat(np.arange(len(picks)), factor)[:frames - position]
            held[position:] = values[index]
            self._hold = values[-1].copy()
            used = len(index)
            self._hold_left = len(picks) * factor - used
        levels = 2.0 ** (bits - 1.0)
        return np.round(held * levels) / levels

    def process(self, block, context):
        p = self.params
        frames = len(block)
        character = p["character"]
        if character == "crush":
            shaped = self._crush(block)
        else:
            target = dsp.db_to_gain(p["drive"])
            driven = block * dsp.ramp(self._drive, target, frames)
            self._drive = target
            if character == "hard":
                shaped = np.clip(driven, -1.0, 1.0)
                shaped = 1.5 * shaped - 0.5 * shaped ** 3          # rounds the corners a little
            elif character == "fuzz":
                shaped = self.dc.process(np.tanh(driven + self.FUZZ_BIAS) - math.tanh(self.FUZZ_BIAS))
            else:
                shaped = np.tanh(driven)
        shaped = self.tone.process(shaped)
        out_gain = dsp.db_to_gain(p["output"])
        shaped *= dsp.ramp(self._out, out_gain, frames)
        self._out = out_gain
        dry_gain, wet_gain = _wet_dry(p["mix"])
        out = block * dsp.ramp(self._dry, dry_gain, frames) + shaped * dsp.ramp(self._wet, wet_gain, frames)
        self._dry, self._wet = dry_gain, wet_gain
        return out


class DelayProcessor(Processor):
    MAX_SECONDS = 4.0

    def __init__(self, sample_rate, params):
        super().__init__(sample_rate, params)
        self.line = dsp.DelayLine(int(self.MAX_SECONDS * self.sample_rate) + 4096, 2)
        self.tone = dsp.OnePoleLowpass(sample_rate, 2, params["tone"])
        self._delay = None
        self._dry, self._wet = _wet_dry(params["mix"])
        self._feedback = params["feedback"] / 100.0

    @property
    def tail_seconds(self):
        feedback = min(0.9, self.params["feedback"] / 100.0)
        repeats = 1 if feedback <= 0.001 else math.log(1e-4) / math.log(feedback)
        seconds = (self._delay or self.sample_rate) / self.sample_rate
        return min(60.0, seconds * (repeats + 1))

    def delay_frames(self, context):
        p = self.params
        beats = DELAY_BEATS.get(p["time"])
        seconds = p["time_ms"] / 1000.0 if beats is None else beats * 60.0 / max(1.0, context.bpm)
        return int(min(self.MAX_SECONDS, max(0.001, seconds)) * self.sample_rate)

    def update(self, params):
        self.params = dict(params)
        self.tone.set(params["tone"])

    def process(self, block, context):
        p = self.params
        frames = len(block)
        target = self.delay_frames(context)
        old = self._delay if self._delay is not None else target
        self._delay = target
        feedback = min(0.95, p["feedback"] / 100.0)
        fb_ramp = dsp.ramp(self._feedback, feedback, frames)
        if isinstance(fb_ramp, float):
            fb_ramp = np.full((frames, 1), fb_ramp)
        self._feedback = feedback
        wet = np.empty((frames, 2))
        position = 0
        while position < frames:
            count = min(frames - position, target, old)
            taps = self.line.read(target, count)
            if old != target:  # the echo time changed: fade from the old echo to the new one
                fade = np.linspace(0.0, 1.0, count, endpoint=False)[:, None]
                taps = taps * fade + self.line.read(old, count) * (1.0 - fade)
                old = target
            echoes = self.tone.process(taps)
            fb = echoes * fb_ramp[position:position + count]
            source = block[position:position + count]
            if p["ping_pong"]:
                mono = source.mean(axis=1)
                written = np.stack([mono + fb[:, 1], fb[:, 0]], axis=1)
            else:
                written = source + fb
            self.line.write(written)
            wet[position:position + count] = echoes
            position += count
        dry_gain, wet_gain = _wet_dry(p["mix"])
        out = block * dsp.ramp(self._dry, dry_gain, frames) + wet * dsp.ramp(self._wet, wet_gain, frames)
        self._dry, self._wet = dry_gain, wet_gain
        return out


class ReverbProcessor(Processor):
    """A feedback delay network: eight delay lines that feed back into each other through a
    mixing matrix, each slightly darkened every time round, after two diffusers that smear
    the input. All eight lines run side by side as columns."""

    LINES_MS = (29.7, 37.1, 41.1, 43.7, 53.3, 61.9, 71.3, 79.7)
    DIFFUSERS_MS = (7.1, 9.3)
    DIFFUSER_GAIN = 0.6

    def __init__(self, sample_rate, params):
        super().__init__(sample_rate, params)
        sr = self.sample_rate
        size = 8
        h = np.array([[1.0]])
        while h.shape[0] < size:
            h = np.block([[h, h], [h, -h]])
        self.matrix = h / math.sqrt(size)
        rng = np.random.default_rng(7)
        self.in_gains = rng.choice([-1.0, 1.0], size) * 0.35
        self.out_left = rng.choice([-1.0, 1.0], size) / math.sqrt(size)
        self.out_right = rng.choice([-1.0, 1.0], size) / math.sqrt(size)
        self._outputs = np.stack([self.out_left, self.out_right], axis=1)
        self.predelay = dsp.DelayLine(int(0.3 * sr) + 4096, 1)
        self.diffusers = [(dsp.DelayLine(int(ms / 1000.0 * sr) + 1, 1), int(ms / 1000.0 * sr))
                          for ms in self.DIFFUSERS_MS]
        self._size = None
        self._dry, self._wet = _wet_dry(params["mix"])
        self.update(params)

    @property
    def tail_seconds(self):
        return self.params["decay"] * 1.5 + self.params["predelay"] / 1000.0 + 0.2

    def update(self, params):
        self.params = dict(params)
        sr = self.sample_rate
        if params["size"] != self._size:
            self._size = params["size"]
            factor = 0.35 + 1.3 * params["size"] / 100.0
            lengths = []
            for ms in self.LINES_MS:
                n = max(64, int(ms * factor / 1000.0 * sr))
                while n in lengths:
                    n += 1
                lengths.append(n)
            self.lengths = np.array(lengths)
            # the eight lines share one ring buffer, kept twice over (a mirror), so every read is one
            # straight run of memory however the ring wraps
            self.capacity = int(self.lengths.max()) + 4096
            self.ring = np.zeros((2 * self.capacity, len(lengths)))
            self.ring_position = 0
            self.damping_state = np.zeros(len(lengths))
            self._columns = np.arange(len(lengths))
        decay = max(0.1, params["decay"])
        self.gains = 10.0 ** (-3.0 * self.lengths / (decay * sr))
        brightness = params["brightness"] / 100.0
        cutoff = 1200.0 + brightness ** 2 * 16000.0
        a = math.exp(-2.0 * math.pi * cutoff / sr)
        self.damping = dsp.PoleBank(np.full(len(self.lengths), a))
        self.damping_a = a

    def _ring_write(self, rows):
        count = len(rows)
        cap = self.capacity
        start = self.ring_position
        first = min(count, cap - start)
        self.ring[start:start + first] = rows[:first]
        self.ring[start + cap:start + cap + first] = rows[:first]
        if first < count:
            rest = count - first
            self.ring[:rest] = rows[first:]
            self.ring[cap:cap + rest] = rows[first:]
        self.ring_position = (start + count) % cap

    def _diffuse(self, x):
        for line, delay in self.diffusers:
            out = np.empty_like(x)
            position = 0
            g = self.DIFFUSER_GAIN
            while position < len(x):
                count = min(delay, len(x) - position)
                past = line.read(delay, count)[:, 0]
                v = x[position:position + count] + g * past
                line.write(v[:, None])
                out[position:position + count] = past - g * v
                position += count
            x = out
        return x

    def process(self, block, context):
        p = self.params
        frames = len(block)
        mono = block.mean(axis=1)
        delay = int(p["predelay"] / 1000.0 * self.sample_rate)
        if delay > 0:
            self.predelay.write(mono[:, None])
            mono = self.predelay.read(delay + frames, frames)[:, 0] if delay + frames <= self.predelay.length \
                else mono
        mono = self._diffuse(mono)
        wet = np.empty((frames, 2))
        shortest = int(self.lengths.min())
        position = 0
        width_lines = len(self.lengths)
        flat = self.ring.reshape(-1)
        while position < frames:
            count = min(shortest, frames - position)
            starts = self.ring_position + self.capacity - self.lengths       # each line's read start
            index = (starts * width_lines + self._columns)[None, :] + (np.arange(count) * width_lines)[:, None]
            taps = flat[index]
            damped, self.damping_state = self.damping.run((1.0 - self.damping_a) * taps, self.damping_state)
            feedback = (damped * self.gains) @ self.matrix
            self._ring_write(mono[position:position + count, None] * self.in_gains + feedback)
            wet[position:position + count] = taps @ self._outputs
            position += count
        width = p["width"] / 100.0
        if width < 1.0:
            mid = wet.mean(axis=1, keepdims=True)
            wet = mid + (wet - mid) * width
        dry_gain, wet_gain = _wet_dry(p["mix"])
        out = block * dsp.ramp(self._dry, dry_gain, frames) + wet * dsp.ramp(self._wet, wet_gain, frames)
        self._dry, self._wet = dry_gain, wet_gain
        return out


PROCESSORS = {"eq": EqProcessor, "compressor": CompressorProcessor, "distortion": DistortionProcessor,
              "delay": DelayProcessor, "reverb": ReverbProcessor}


class Chain:
    """One track's effects, in order. Built and run on the audio thread.

    configure() takes the track's effect list (only the ones that are on and that run in real
    time); processors whose type is unchanged keep their sound (a reverb tail carries on while
    you change its mix)."""

    def __init__(self, sample_rate):
        self.sample_rate = float(sample_rate)
        self.processors = []          # (type key, processor)
        self.quiet_frames = 0

    def configure(self, effects):
        wanted = [e for e in effects if e.get("on", True) and e["type"] in PROCESSORS]
        new = []
        for i, effect in enumerate(wanted):
            kind = effect["type"]
            if i < len(self.processors) and self.processors[i][0] == kind:
                processor = self.processors[i][1]
                if processor.params != effect["params"]:
                    processor.update(effect["params"])
            else:
                processor = PROCESSORS[kind](self.sample_rate, effect["params"])
            new.append((kind, processor))
        self.processors = new

    @property
    def active(self):
        return bool(self.processors)

    def tail_seconds(self):
        return sum(p.tail_seconds for _k, p in self.processors)

    def set_param(self, index, key, value):
        """Automation: change one setting of the effect at `index` (in the chain's own order)."""
        if 0 <= index < len(self.processors):
            processor = self.processors[index][1]
            if processor.params.get(key) != value:
                params = dict(processor.params)
                params[key] = value
                processor.update(params)

    def has_param(self, index, key, value):
        """True if the effect at `index` has setting `key` at `value` already (automation's check that the
        chain was not rebuilt with the saved settings since it last changed it)."""
        return 0 <= index < len(self.processors) and self.processors[index][1].params.get(key) == value

    def process(self, block, context):
        """block: float (frames, 2). Returns the processed block (float64)."""
        if not self.processors:
            return block
        silent = not np.any(np.abs(block) > SILENCE)
        if silent:
            self.quiet_frames += len(block)
            if self.quiet_frames > self.tail_seconds() * self.sample_rate + len(block):
                return np.zeros(block.shape)      # the tails have died away: nothing to work out
        else:
            self.quiet_frames = 0
        y = np.asarray(block, dtype=np.float64)
        for _kind, processor in self.processors:
            y = processor.process(y, context)
        return y


def copy_effects(effects):
    return copy.deepcopy(effects)
