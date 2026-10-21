"""Preferences that Musician Forge remembers between sessions.

Stored as JSON in %LOCALAPPDATA%\\MusicianForge\\settings.json. Unknown or
damaged values fall back to the defaults, so a bad file can never stop the
program from starting.
"""

import copy
import json
import logging
import math
import os

from . import paths

log = logging.getLogger("musicianforge.settings")

DEFAULTS = {
    "audio": {
        "host_api": "Windows WASAPI",
        "device_name": "",          # empty = the Windows default output
        "block_frames": 256,
        "input_device": "",         # the microphone; empty = the Windows default input
        "raw_microphone": True,     # ask Windows for the raw microphone sound (no noise reduction), 0.9.1
        "low_latency_monitoring": False,  # hear yourself the low-latency way (Windows 10 and later), 0.9.1
    },
    # Measure the recording delay, remembered for each pair of output and microphone (0.9.1):
    # [["host api|output|microphone", milliseconds], ...]
    "microphone_offsets": [],
    "metronome_on": True,
    "metronome_volume": 70,          # percent
    "count_in_bars": 1,
    "record_offset_ms": 0,           # the musical keyboard's timing adjustment
    "microphone_offset_ms": 0,       # recordings from the microphone (Measure the recording delay sets it)
    "keyboard_layout": "piano",      # or "scale" or "chords" (chord strips)
    "keyboard_scale": "",            # empty: the keyboard follows the song's key
    "keyboard_controls_shown": False,
    "arpeggiator": {"on": False, "pattern": "Up", "rate": "Sixteenth notes", "octaves": 1},
    "quantize_grid": "Sixteenth note",
    "quantize_strength": 100,
    "quantize_lengths": False,
    "nudge_step": "quarter",            # how far a region or its edge moves with one key (0.9.4)
    "new_song": {"bpm": 120.0, "numerator": 4, "denominator": 4, "tonic": 0, "scale": "Major"},
    # No remembered export folder: exports always start next to the saved song, or in
    # Musician Forge Songs, so they are easy to find without seeing the screen.
    # format: "wav" or "m4a"; tail: let the sound ring out at the end
    "export": {"format": "wav", "sample_rate": 48000, "bits": 24, "tail": True, "fade": False, "fade_seconds": 10},
    "recent_files": [],
    "speak_with_windows_voice": False,
    "announce_note_names": False,
    "master_volume": 100,
    "soundfont": "",                 # empty = GeneralUser GS
    "play_all_sections": False,      # off: Space loops the current section
    "announce_play_start": False,    # quiet by default so you can hear the metronome
    "announce_record_start": False,
    "announce_recorded_notes": False,
}


class Settings:
    def __init__(self, path=None):
        self.path = path or paths.settings_file()
        self.data = copy.deepcopy(DEFAULTS)

    def load(self):
        try:
            with open(self.path, encoding="utf-8-sig") as fh:     # -sig: a file saved by Notepad starts with a mark
                stored = json.load(fh)
            self.data = _within_limits(_merge(copy.deepcopy(DEFAULTS), stored))
        except FileNotFoundError:
            pass
        except Exception:  # noqa: BLE001
            log.exception("Settings file was damaged; using defaults")
            self.data = copy.deepcopy(DEFAULTS)
        return self

    def save(self):
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self.data, fh, indent=1)
            os.replace(tmp, self.path)
        except Exception:  # noqa: BLE001
            log.exception("Could not save settings")

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value

    def add_recent(self, path, limit=8):
        recent = [p for p in self.data.get("recent_files", []) if os.path.normcase(p) != os.path.normcase(path)]
        recent.insert(0, path)
        self.data["recent_files"] = recent[:limit]

    def recent_projects(self):
        """Recent project files that still exist (deleted or moved ones are dropped from the list)."""
        recent = self.data.get("recent_files", [])
        existing = [p for p in recent if os.path.isfile(p)]
        if existing != recent:
            self.data["recent_files"] = existing
            self.save()
        return existing


def _number(value, whole):
    """A stored number, or None if it is not one (or is NaN or infinity, which JSON files can hold). A setting
    that is a whole number gets a whole number (a slider or a list position cannot take 70.5)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return int(round(value)) if whole else float(value)


def _paths(items):
    return [item for item in items if isinstance(item, str) and item]


def _offset_pairs(items):
    """[["host api|output|microphone", milliseconds], ...], leaving out anything else."""
    pairs = []
    for item in items:
        if isinstance(item, (list, tuple)) and len(item) == 2 and isinstance(item[0], str):
            ms = _number(item[1], whole=True)
            if ms is not None:
                pairs.append([item[0], ms])
    return pairs


LIST_ITEMS = {"recent_files": _paths, "microphone_offsets": _offset_pairs}


class Between:
    """A number setting's allowed range."""

    def __init__(self, low, high):
        self.low, self.high = low, high

    def allows(self, value):
        return self.low <= value <= self.high


class OneOf:
    """The values a setting may hold."""

    def __init__(self, values):
        self.values = tuple(values)

    def allows(self, value):
        return value in self.values


def _limits():
    """{path: Between or OneOf}: what each setting may hold. A value outside (a hand-edited file, or one saved by a
    newer Musician Forge that knows more scales or arpeggiator patterns) gets its default: a new project's tempo of
    500 or an unknown scale stopped Musician Forge before its window opened, and an unknown arpeggiator pattern broke
    the keyboard controls (the review of 9 Oct 2026)."""
    from . import arpeggiator, keyboard_map, quantize, theory
    from .session_nudge import NUDGE_STEPS
    from .timeline import MAX_BPM, MAX_NUMERATOR, MIN_BPM, VALID_DENOMINATORS

    return {
        ("audio", "block_frames"): Between(32, 4096),
        ("metronome_volume",): Between(0, 100), ("master_volume",): Between(0, 150), ("count_in_bars",): Between(0, 2),
        ("record_offset_ms",): Between(-200, 200), ("microphone_offset_ms",): Between(-200, 200),
        ("quantize_strength",): Between(0, 100), ("quantize_grid",): OneOf(quantize.GRID_NAMES),
        ("nudge_step",): OneOf(NUDGE_STEPS),
        ("keyboard_layout",): OneOf(keyboard_map.MODES), ("keyboard_scale",): OneOf(("",) + tuple(theory.SCALE_NAMES)),
        ("arpeggiator", "pattern"): OneOf(arpeggiator.PATTERNS), ("arpeggiator", "rate"): OneOf(arpeggiator.RATE_NAMES),
        ("arpeggiator", "octaves"): Between(1, arpeggiator.MAX_OCTAVES),
        ("new_song", "bpm"): Between(MIN_BPM, MAX_BPM), ("new_song", "numerator"): Between(1, MAX_NUMERATOR),
        ("new_song", "denominator"): OneOf(VALID_DENOMINATORS), ("new_song", "tonic"): Between(0, 11),
        ("new_song", "scale"): OneOf(theory.SCALE_NAMES), ("export", "format"): OneOf(("wav", "m4a")),
        ("export", "sample_rate"): OneOf((44100, 48000)), ("export", "bits"): OneOf((16, 24)),
        ("export", "fade_seconds"): Between(5, 30),
    }


def _within_limits(data):
    for path, limit in _limits().items():
        holder, default = data, DEFAULTS
        for key in path[:-1]:
            holder, default = holder[key], default[key]
        if not limit.allows(holder[path[-1]]):
            holder[path[-1]] = copy.deepcopy(default[path[-1]])
    return data


def _merge(defaults, stored):
    """Take stored values only where their type matches the default's type, and lists only with the items they
    should hold, so a damaged or hand-edited file can never stop the program (found in the review of 9 Oct 2026:
    a recent project that was not text stopped the start screen, and a volume of 70.5 the Preferences window)."""
    if not isinstance(stored, dict):
        return defaults
    for key, default in defaults.items():
        if key not in stored:
            continue
        value = stored[key]
        if isinstance(default, dict):
            defaults[key] = _merge(default, value)
        elif isinstance(default, bool):
            if isinstance(value, bool):
                defaults[key] = value
        elif isinstance(default, (int, float)):
            number = _number(value, whole=isinstance(default, int))
            if number is not None:
                defaults[key] = number
        elif isinstance(default, list):
            if isinstance(value, list):
                defaults[key] = LIST_ITEMS.get(key, list)(value)
        elif isinstance(default, type(value)):
            defaults[key] = value
    return defaults
