"""Quantize: move notes onto the beat grid.

The grid is measured from the start of each note's bar, so quantizing works
correctly in any time signature, including odd ones like 7/8 or 5/4.
"""

from .song import Note
from .timeline import PPQ

# (name, grid size in ticks)
GRIDS = [
    ("Quarter note", PPQ),
    ("Eighth note", PPQ // 2),
    ("Sixteenth note", PPQ // 4),
    ("Thirty-second note", PPQ // 8),
    ("Half note", PPQ * 2),
    ("Whole note", PPQ * 4),
    ("Quarter note triplet", PPQ * 2 // 3),
    ("Eighth note triplet", PPQ // 3),
    ("Sixteenth note triplet", PPQ // 6),
]
GRID_NAMES = [g[0] for g in GRIDS]
DEFAULT_GRID = "Sixteenth note"


def grid_ticks(name):
    for grid_name, ticks in GRIDS:
        if grid_name == name:
            return ticks
    raise ValueError("Unknown quantize grid: {}".format(name))


def quantize_tick(tick, grid, timeline, strength=1.0):
    """Move one position toward the nearest grid line of its bar."""
    bar = timeline.tick_to_bar(tick)
    bar_start, bar_end = timeline.bar_to_tick(bar), timeline.bar_to_tick(bar + 1)
    offset = tick - bar_start
    # the grid line at or before the note and the one after it; in a bar the grid does not divide (a quarter note
    # in 7/8, a half note in 7/8), the line after the last one is the next bar's first beat, and the nearer of the
    # two wins (before the review of 23 Oct 2026 a note just before that beat was rounded back to the last line)
    last = bar_start + (offset // grid) * grid
    following = min(last + grid, bar_end)
    target = last if tick - last <= following - tick else following
    return int(round(tick + (target - tick) * float(strength)))


def notes_in_region(notes, start, end, grid, timeline):
    """The indexes of the notes Quantize takes for "the region you are on": every note in the region, and a note played
    a little early, just before it, that snaps into it. (Until 23 Oct 2026 a note in the region's last half grid line
    was left out, so in 7/8 a note near the end of the bar did not move: a tester's run of the 0.9.7 features.)"""
    half = grid / 2.0
    return [i for i, n in enumerate(notes)
            if start <= n.tick < end or (start - half <= n.tick < start and quantize_tick(n.tick, grid, timeline) >= start)]


def quantize_notes(notes, grid, timeline, strength=1.0, quantize_lengths=False):
    """Return new, sorted notes moved onto the grid.

    - strength 1.0 snaps fully; 0.5 moves halfway.
    - quantize_lengths also snaps each note's length to the grid (at least one grid step).
    - Notes never start before tick 0.
    """
    result = []
    for note in notes:
        start = max(0, quantize_tick(note.tick, grid, timeline, strength))
        length = note.length
        if quantize_lengths:
            steps = max(1, int(round(length / float(grid))))
            length = int(round(length + (steps * grid - length) * float(strength)))
        result.append(Note(start, max(1, length), note.pitch, note.velocity))
    result.sort(key=lambda n: (n.tick, n.pitch))
    return _remove_duplicates(result)


def _remove_duplicates(notes):
    """Two identical notes on the same tick after quantizing: keep the louder, longer one."""
    best = {}
    order = []
    for note in notes:
        key = (note.tick, note.pitch)
        if key not in best:
            best[key] = note
            order.append(key)
        else:
            current = best[key]
            if (note.velocity, note.length) > (current.velocity, current.length):
                best[key] = note
    return [best[k] for k in order]
