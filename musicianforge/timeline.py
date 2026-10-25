"""The song's timeline: tempo changes, time signature changes and key changes.

Positions inside Musician Forge are measured in ticks: 960 ticks per quarter
note (a common resolution in music programs). Bars and beats are counted from 1,
the way musicians count.

- Time signature changes always start at the beginning of a bar.
- Tempo changes sit at a bar and beat. Tempo is in quarter notes per minute,
  as in MIDI files.
- Key changes start at the beginning of a bar.

Changes are stored by bar (and beat), so if an earlier time signature changes,
later tempo and key changes stay on the bar where you put them.
"""

import bisect
import math
from dataclasses import dataclass

import numpy as np

from . import theory

PPQ = 960
MIN_BPM = 20.0
MAX_BPM = 400.0
VALID_DENOMINATORS = (1, 2, 4, 8, 16, 32)
MAX_NUMERATOR = 32


@dataclass
class TempoChange:
    bar: int
    beat: float = 1.0
    bpm: float = 120.0


@dataclass
class TimeSignatureChange:
    bar: int
    numerator: int = 4
    denominator: int = 4

    def label(self):
        return "{}/{}".format(self.numerator, self.denominator)

    def spoken(self):
        return "{} {}".format(self.numerator, self.denominator)


@dataclass
class KeyChange:
    bar: int
    tonic: int = 0
    scale: str = "Major"

    def name(self):
        return theory.key_name(self.tonic, self.scale)


class TimelineError(ValueError):
    """A change that does not make musical sense (bad bar, tempo, signature)."""


def format_number(value):
    """2.0 -> '2', 2.5 -> '2.5', 2.333333 -> '2.333'."""
    text = "{:.3f}".format(value).rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


class Timeline:
    def __init__(self, tempos=None, time_signatures=None, keys=None):
        self.tempos = list(tempos) if tempos else [TempoChange(1, 1.0, 120.0)]
        self.time_signatures = list(time_signatures) if time_signatures else [TimeSignatureChange(1, 4, 4)]
        self.keys = list(keys) if keys else [KeyChange(1, 0, "Major")]
        self.rebuild()

    # ------------------------------------------------------------------
    # validation and caches
    # ------------------------------------------------------------------
    def rebuild(self):
        """Check every change, sort them, and recompute lookup tables."""
        for ts in self.time_signatures:
            ts.bar, ts.numerator, ts.denominator = int(ts.bar), int(ts.numerator), int(ts.denominator)
            if ts.bar < 1:
                raise TimelineError("Time signature changes must be at bar 1 or later")
            if not 1 <= ts.numerator <= MAX_NUMERATOR:
                raise TimelineError("The top number of a time signature must be 1 to {}".format(MAX_NUMERATOR))
            if ts.denominator not in VALID_DENOMINATORS:
                raise TimelineError("The bottom number of a time signature must be 1, 2, 4, 8, 16 or 32")
        self.time_signatures = _dedupe(sorted(self.time_signatures, key=lambda t: t.bar), key=lambda t: t.bar)
        if self.time_signatures[0].bar != 1:
            self.time_signatures.insert(0, TimeSignatureChange(1, 4, 4))

        self._ts_bars = [t.bar for t in self.time_signatures]
        self._ts_tpb = [_ticks_per_bar(t) for t in self.time_signatures]
        self._ts_start = [0]
        for i in range(1, len(self.time_signatures)):
            span = self._ts_bars[i] - self._ts_bars[i - 1]
            self._ts_start.append(self._ts_start[-1] + span * self._ts_tpb[i - 1])

        for k in self.keys:
            k.bar, k.tonic = int(k.bar), int(k.tonic) % 12
            if k.bar < 1:
                raise TimelineError("Key changes must be at bar 1 or later")
            theory.scale_intervals(k.scale)  # raises ValueError for unknown scales
        self.keys = _dedupe(sorted(self.keys, key=lambda k: k.bar), key=lambda k: k.bar)
        if self.keys[0].bar != 1:
            self.keys.insert(0, KeyChange(1, 0, "Major"))
        self._key_bars = [k.bar for k in self.keys]

        for t in self.tempos:
            t.bar, t.beat, t.bpm = int(t.bar), float(t.beat), float(t.bpm)
            if t.bar < 1:
                raise TimelineError("Tempo changes must be at bar 1 or later")
            if not MIN_BPM <= t.bpm <= MAX_BPM:
                raise TimelineError("Tempo must be between {} and {} beats per minute".format(
                    int(MIN_BPM), int(MAX_BPM)))
            beats = self.time_signature_at_bar(t.bar).numerator
            if not 1.0 <= t.beat < beats + 1.0:
                raise TimelineError("Bar {} has {} beats, so a tempo change there must be on beat 1 to {}".format(
                    t.bar, beats, beats))
        keyed = sorted(self.tempos, key=lambda t: self.position_to_tick(t.bar, t.beat))
        self.tempos = _dedupe(keyed, key=lambda t: self.position_to_tick(t.bar, t.beat))
        if self.position_to_tick(self.tempos[0].bar, self.tempos[0].beat) != 0:
            self.tempos.insert(0, TempoChange(1, 1.0, self.tempos[0].bpm))

        self._tempo_ticks = np.array([self.position_to_tick(t.bar, t.beat) for t in self.tempos], dtype=np.float64)
        self._tempo_spt = np.array([60.0 / (t.bpm * PPQ) for t in self.tempos], dtype=np.float64)  # seconds per tick
        secs = [0.0]
        for i in range(1, len(self.tempos)):
            secs.append(secs[-1] + (self._tempo_ticks[i] - self._tempo_ticks[i - 1]) * self._tempo_spt[i - 1])
        self._tempo_secs = np.array(secs, dtype=np.float64)

    # ------------------------------------------------------------------
    # bars and beats
    # ------------------------------------------------------------------
    def _ts_index_for_bar(self, bar):
        return max(0, bisect.bisect_right(self._ts_bars, bar) - 1)

    def time_signature_at_bar(self, bar):
        return self.time_signatures[self._ts_index_for_bar(bar)]

    def ticks_per_bar(self, bar):
        return self._ts_tpb[self._ts_index_for_bar(bar)]

    def ticks_per_beat(self, bar):
        return PPQ * 4 // self.time_signature_at_bar(bar).denominator

    def bar_to_tick(self, bar):
        """Tick where `bar` starts. Bars before 1 (a count-in) are allowed."""
        bar = int(bar)
        i = self._ts_index_for_bar(bar)
        return self._ts_start[i] + (bar - self._ts_bars[i]) * self._ts_tpb[i]

    def position_to_tick(self, bar, beat=1.0):
        """Tick for a bar and beat; beat 1.5 is halfway through the first beat."""
        return int(round(self.bar_to_tick(bar) + (float(beat) - 1.0) * self.ticks_per_beat(bar)))

    def tick_to_bar(self, tick):
        i = max(0, bisect.bisect_right(self._ts_start, tick) - 1)
        return self._ts_bars[i] + (int(tick) - self._ts_start[i]) // self._ts_tpb[i]

    def tick_to_position(self, tick):
        """(bar, beat) for a tick; beat is a float counted from 1."""
        tick = int(round(tick))        # a playhead between ticks: its nearest tick, never "beat 5" of a 4/4 bar
        bar = self.tick_to_bar(tick)
        offset = tick - self.bar_to_tick(bar)
        return bar, 1.0 + offset / self.ticks_per_beat(bar)

    def describe_position(self, tick):
        bar, beat = self.tick_to_position(tick)
        return "Bar {}, beat {}".format(bar, format_number(beat))

    def short_position(self, tick):
        """Compact form for lists, such as '5.2' or '5.2.5'."""
        bar, beat = self.tick_to_position(tick)
        return "{}.{}".format(bar, format_number(beat))

    def spoken_bar_position(self, tick):
        """'bar 9' on a bar line, otherwise 'bar 5 beat 2.5' (beats rounded to hundredths)."""
        bar, beat = self.tick_to_position(tick)
        beat = round(beat, 2)
        if beat >= self.time_signature_at_bar(bar).numerator + 1:    # a hair before the next bar line
            bar, beat = bar + 1, 1.0
        if beat == 1.0:
            return "bar {}".format(bar)
        return "bar {} beat {}".format(bar, format_number(beat))

    def _said_position(self, tick):
        """(bar, beat) for a tick, where a hair before a bar line counts as that bar line, as spoken_bar_position
        says it (its beat then a hair under 1)."""
        bar, beat = self.tick_to_position(tick)
        beats = self.time_signature_at_bar(bar).numerator
        if round(beat, 2) >= beats + 1:
            return bar + 1, beat - beats
        return bar, beat

    def bars_and_beats(self, start_tick, end_tick):
        """How long a stretch is in whole bars plus beats: (bars, beats). (Until the fifth review of 25 Oct 2026 an end
        a hair before a bar line, said as that bar line, made it a bar shorter and a bar's beats longer: "ends at bar
        9, 7 bars and 4 beats long".)"""
        b0, beat0 = self._said_position(start_tick)
        b1, beat1 = self._said_position(end_tick)
        bars, beats = b1 - b0, round(beat1 - beat0, 2)
        if beats < 0:
            bars -= 1
            beats = round(beats + self.time_signature_at_bar(max(1, b1 - 1)).numerator, 2)
        return max(0, bars), max(0.0, beats)

    def describe_span(self, start_tick, end_tick):
        """'starts at bar 1, ends at bar 9, 8 bars long', or with beats where it is not on a bar line:
        'starts at bar 5, ends at bar 9 beat 3, 4 bars and 2 beats long'."""
        bars, beats = self.bars_and_beats(start_tick, end_tick)
        parts = []
        if bars:
            parts.append("{} bar{}".format(bars, "" if bars == 1 else "s"))
        if beats or not bars:
            parts.append("{} beat{}".format(format_number(beats), "" if beats == 1 else "s"))
        return "starts at {}, ends at {}, {} long".format(self.spoken_bar_position(start_tick),
                                                          self.spoken_bar_position(end_tick), " and ".join(parts))

    # ------------------------------------------------------------------
    # time
    # ------------------------------------------------------------------
    def _tempo_index(self, tick):
        return max(0, int(np.searchsorted(self._tempo_ticks, tick, side="right")) - 1)

    def tempo_at_tick(self, tick):
        return self.tempos[self._tempo_index(tick)].bpm

    def tick_to_seconds(self, tick):
        i = self._tempo_index(tick)
        return float(self._tempo_secs[i] + (tick - self._tempo_ticks[i]) * self._tempo_spt[i])

    def ticks_to_seconds_array(self, ticks):
        ticks = np.asarray(ticks, dtype=np.float64)
        idx = np.clip(np.searchsorted(self._tempo_ticks, ticks, side="right") - 1, 0, None)
        return self._tempo_secs[idx] + (ticks - self._tempo_ticks[idx]) * self._tempo_spt[idx]

    def seconds_to_tick(self, seconds):
        """Float tick at a time in seconds (negative times use the first tempo)."""
        i = max(0, int(np.searchsorted(self._tempo_secs, seconds, side="right")) - 1)
        return float(self._tempo_ticks[i] + (seconds - self._tempo_secs[i]) / self._tempo_spt[i])

    def tick_to_sample(self, tick, sample_rate):
        return int(round(self.tick_to_seconds(tick) * sample_rate))

    def sample_to_tick(self, sample, sample_rate):
        return self.seconds_to_tick(sample / float(sample_rate))

    # ------------------------------------------------------------------
    # keys
    # ------------------------------------------------------------------
    def key_at_bar(self, bar):
        i = max(0, bisect.bisect_right(self._key_bars, bar) - 1)
        return self.keys[i]

    def key_at_tick(self, tick):
        return self.key_at_bar(self.tick_to_bar(tick))

    # ------------------------------------------------------------------
    # beats for the metronome
    # ------------------------------------------------------------------
    def beats_between(self, start_tick, end_tick):
        """Every beat with start_tick <= tick < end_tick.

        Returns a list of (tick, bar, beat_number, is_downbeat).
        """
        result = []
        if end_tick <= start_tick:
            return result
        bar = self.tick_to_bar(start_tick)
        while True:
            bar_tick = self.bar_to_tick(bar)
            if bar_tick >= end_tick:
                break
            ts = self.time_signature_at_bar(bar)
            tpb = self.ticks_per_beat(bar)
            for n in range(ts.numerator):
                t = bar_tick + n * tpb
                if t >= end_tick:
                    break
                if t >= start_tick:
                    result.append((t, bar, n + 1, n == 0))
            bar += 1
        return result

    # ------------------------------------------------------------------
    # editing helpers (callers keep undo history)
    # ------------------------------------------------------------------
    def _change(self, tempos, time_signatures, keys):
        """Put in new lists of changes, or, if they do not make sense together, leave the timeline exactly as it was
        and raise TimelineError (before the review of 9 Oct 2026 a refused change stayed half made: removing a 7/8
        bar that a tempo change sat in, say)."""
        before = (self.tempos, self.time_signatures, self.keys)
        self.tempos, self.time_signatures, self.keys = list(tempos), list(time_signatures), list(keys)
        try:
            self.rebuild()
        except Exception:
            self.tempos, self.time_signatures, self.keys = before
            self.rebuild()
            raise

    def set_tempo(self, bar, beat, bpm):
        tempos = [t for t in self.tempos if not (t.bar == bar and abs(t.beat - beat) < 1e-9)]
        self._change(tempos + [TempoChange(bar, beat, bpm)], self.time_signatures, self.keys)

    def set_time_signature(self, bar, numerator, denominator):
        signatures = [t for t in self.time_signatures if t.bar != bar]
        self._change(self.tempos, signatures + [TimeSignatureChange(bar, numerator, denominator)], self.keys)

    def set_key(self, bar, tonic, scale):
        keys = [k for k in self.keys if k.bar != bar]
        self._change(self.tempos, self.time_signatures, keys + [KeyChange(bar, tonic, scale)])

    def remove_tempo(self, index):
        if index == 0:
            raise TimelineError("The first tempo cannot be removed; change it instead")
        self._change(self.tempos[:index] + self.tempos[index + 1:], self.time_signatures, self.keys)

    def remove_time_signature(self, index):
        if index == 0:
            raise TimelineError("The first time signature cannot be removed; change it instead")
        self._change(self.tempos, self.time_signatures[:index] + self.time_signatures[index + 1:], self.keys)

    def remove_key(self, index):
        if index == 0:
            raise TimelineError("The first key cannot be removed; change it instead")
        self._change(self.tempos, self.time_signatures, self.keys[:index] + self.keys[index + 1:])

    # ------------------------------------------------------------------
    # saving
    # ------------------------------------------------------------------
    def to_dict(self):
        return {
            "tempos": [[t.bar, t.beat, t.bpm] for t in self.tempos],
            "time_signatures": [[t.bar, t.numerator, t.denominator] for t in self.time_signatures],
            "keys": [[k.bar, k.tonic, k.scale] for k in self.keys],
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            tempos=[TempoChange(int(b), float(beat), float(bpm)) for b, beat, bpm in data.get("tempos", [])],
            time_signatures=[TimeSignatureChange(int(b), int(n), int(d)) for b, n, d in data.get("time_signatures", [])],
            keys=[KeyChange(int(b), int(t), str(s)) for b, t, s in data.get("keys", [])],
        )

    def copy(self):
        return Timeline.from_dict(self.to_dict())


def _ticks_per_bar(ts):
    return ts.numerator * PPQ * 4 // ts.denominator


def _dedupe(items, key):
    """Keep the last item for each key value, preserving sorted order."""
    result = []
    for item in items:
        if result and key(result[-1]) == key(item):
            result[-1] = item
        else:
            result.append(item)
    return result


# Musical lengths, longest first, for describing note lengths in words.
NOTE_LENGTHS = [
    (3840, "whole note"), (2880, "dotted half note"), (1920, "half note"),
    (1440, "dotted quarter note"), (1280, "half note triplet"), (960, "quarter note"),
    (720, "dotted eighth note"), (640, "quarter note triplet"), (480, "eighth note"),
    (360, "dotted sixteenth note"), (320, "eighth note triplet"), (240, "sixteenth note"),
    (160, "sixteenth note triplet"), (120, "thirty-second note"), (60, "sixty-fourth note"),
]
_LENGTH_NAMES = dict(NOTE_LENGTHS)


def describe_length(ticks):
    """Words for a note length: 'quarter note', '2 quarter notes', '1.37 quarter notes'."""
    ticks = int(ticks)
    if ticks in _LENGTH_NAMES:
        return _LENGTH_NAMES[ticks]
    quarters = ticks / PPQ
    if ticks % PPQ == 0:
        return "{} quarter notes".format(ticks // PPQ)
    return "{} quarter notes".format(format_number(quarters))


def bars_to_ms(timeline, tick_a, tick_b):
    return 1000.0 * (timeline.tick_to_seconds(tick_b) - timeline.tick_to_seconds(tick_a))


def is_close(a, b, tol=1e-6):
    return math.isclose(a, b, rel_tol=0, abs_tol=tol)
