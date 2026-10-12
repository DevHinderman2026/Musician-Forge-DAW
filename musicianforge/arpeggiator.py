"""The arpeggiator: plays the notes you hold one at a time, in time with the song.

This module only decides which notes to play and how fast. The sound engine
does the timing (engine.py), so the notes land exactly on the beat, and while
recording, every note the arpeggiator plays is recorded into the track.
"""

from collections import namedtuple

from .timeline import PPQ

PATTERNS = ["Up", "Down", "Up and down", "Down and up", "As played", "Random"]

# (name shown in the keyboard controls, ticks between notes)
RATES = [
    ("Quarter notes", PPQ),
    ("Eighth notes", PPQ // 2),
    ("Eighth-note triplets", PPQ // 3),
    ("Sixteenth notes", PPQ // 4),
    ("Sixteenth-note triplets", PPQ // 6),
    ("Thirty-second notes", PPQ // 8),
]
RATE_NAMES = [name for name, _ticks in RATES]
MAX_OCTAVES = 4
GATE = 0.8  # each note lasts 80 percent of the step, so the rhythm stays clear

DEFAULT_PATTERN = "Up"
DEFAULT_RATE = "Sixteenth notes"

# What the engine needs: pattern name, ticks per step, octave range, gate (0-1).
ArpSettings = namedtuple("ArpSettings", "pattern step_ticks octaves gate")


def make_settings(pattern=DEFAULT_PATTERN, rate=DEFAULT_RATE, octaves=1):
    """Settings for the engine, with anything unknown replaced by the defaults."""
    if pattern not in PATTERNS:
        pattern = DEFAULT_PATTERN
    ticks = dict(RATES).get(rate, dict(RATES)[DEFAULT_RATE])
    octaves = max(1, min(MAX_OCTAVES, int(octaves)))
    return ArpSettings(pattern, ticks, octaves, GATE)


def sequence(held, pattern, octaves=1):
    """One full cycle of the arpeggio, from the notes held (in the order they were pressed).

    Random returns the notes it chooses from; the engine picks among them.
    """
    if not held:
        return []
    if pattern == "As played":
        base = list(dict.fromkeys(held))  # keep the playing order, drop repeats
    else:
        base = sorted(set(held))
    notes = [n + 12 * octave for octave in range(max(1, int(octaves))) for n in base if 0 <= n + 12 * octave <= 127]
    if pattern == "Down":
        return notes[::-1]
    if pattern == "Up and down":
        return notes + notes[-2:0:-1]  # the top and bottom notes are not repeated
    if pattern == "Down and up":
        down = notes[::-1]
        return down + down[-2:0:-1]
    return notes  # Up, As played and Random


def describe(pattern, rate, octaves):
    """Spoken summary, such as 'up, sixteenth notes, 2 octaves'."""
    octaves = int(octaves)
    return "{}, {}, {} octave{}".format(pattern.lower(), rate.lower(), octaves, "" if octaves == 1 else "s")
