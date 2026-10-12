"""Regions on instrument tracks: named stretches of a track that own the notes starting in them.

A track's notes stay in one list (that is what plays and what the event list
shows); regions mark out stretches of it, like boxes laid along the timeline:

- Recording makes a region that covers exactly what was recorded: the
  looping section, or from the bar where recording started to the bar after it
  stopped (across sections when All sections is on). Regions it overlaps get
  shorter, or are split around it.
- Pasting or moving a region replaces whatever was in that spot.
- Regions never overlap, and every note is inside one: tidy() makes sure, so a
  note added in the event list gets a region of its own bar if it needs one.
- Projects from before regions existed get one region for each section that
  has notes.

Recordings on audio tracks are regions too (song.AudioRegion); this module is
about instrument tracks.
"""

import bisect
import copy
from dataclasses import dataclass

from .song import Note, NoteRegion


def notes_in(track, start, end):
    """The track's notes that start in [start, end), as (index in track.notes, note)."""
    return [(i, n) for i, n in enumerate(track.notes) if start <= n.tick < end]


def region_at(track, tick):
    """The index of the region that holds `tick`, or None."""
    starts = [r.start for r in track.note_regions]
    i = bisect.bisect_right(starts, tick) - 1
    if i >= 0 and track.note_regions[i].contains(tick):
        return i
    return None


def claim(track, start, end, name="", mute=False, player=None, loops=1):
    """Make [start, end) a region of its own: regions it overlaps get shorter, are split around it,
    or disappear if it covers them. Returns the new region (notes are not touched)."""
    kept = []
    for r in track.note_regions:
        if r.end <= start or r.start >= end:
            kept.append(r)
            continue
        if r.start < start:
            kept.append(NoteRegion(r.start, start, r.name, r.mute, copy.deepcopy(r.player), r.loops))
        if r.end > end:
            kept.append(NoteRegion(end, r.end, r.name, r.mute, copy.deepcopy(r.player)))
    region = NoteRegion(int(start), int(end), name, mute, player, loops)
    kept.append(region)
    kept.sort(key=lambda r: r.start)
    track.note_regions = kept
    return region


def clear_span(track, start, end):
    """Remove the notes that start in [start, end) (what pasting over a spot replaces)."""
    track.notes = [n for n in track.notes if not start <= n.tick < end]


def tidy(song):
    """Keep every instrument track's regions in order: sorted, not overlapping, and holding every note."""
    tl = song.timeline
    for track in song.tracks:
        if track.is_audio:
            track.note_regions = []
            continue
        regions = sorted((r for r in track.note_regions if r.end > max(0, r.start)), key=lambda r: r.start)
        cleaned = []
        for r in regions:
            r.start = max(0, r.start)
            if cleaned and cleaned[-1].end > r.start:
                cleaned[-1].end = r.start          # an earlier region gives way to a later one
                if cleaned[-1].end <= cleaned[-1].start:
                    cleaned.pop()
            cleaned.append(r)
        track.note_regions = cleaned
        made = []
        for note in sorted(track.notes, key=lambda n: n.tick):
            if region_at(track, note.tick) is not None:
                continue
            bar = tl.tick_to_bar(note.tick)
            start, end = tl.bar_to_tick(bar), tl.bar_to_tick(bar + 1)
            before = [r for r in track.note_regions if r.start <= note.tick]
            after = [r for r in track.note_regions if r.start > note.tick]
            if before:
                start = max(start, before[-1].end)
            if after:
                end = min(end, after[0].start)
            if made and made[-1].end == start:
                made[-1].end = end                 # notes in the next bar join the region just made
                continue
            region = NoteRegion(start, end)
            track.note_regions.append(region)
            track.note_regions.sort(key=lambda r: r.start)
            made.append(region)


def migrate(song):
    """Projects saved before regions existed: one region for each section that has notes on a track."""
    tl = song.timeline
    for track in song.tracks:
        if track.is_audio or track.note_regions or not track.notes:
            continue
        for index in range(len(song.sections)):
            start_bar, end_bar = song.section_bounds(index)
            start, end = tl.bar_to_tick(start_bar), tl.bar_to_tick(end_bar)
            if any(start <= n.tick < end for n in track.notes):
                track.note_regions.append(NoteRegion(start, end))
    tidy(song)


def bar_span(timeline, start_tick, stop_tick):
    """From the bar line at or before start_tick to the bar line at or after stop_tick."""
    first = timeline.bar_to_tick(timeline.tick_to_bar(start_tick))
    last_bar = timeline.tick_to_bar(max(start_tick, stop_tick - 1)) + 1
    return first, max(first + 1, timeline.bar_to_tick(last_bar))


# ----------------------------------------------------------------------
# copying and pasting
# ----------------------------------------------------------------------
@dataclass
class RegionCopy:
    """A copied region: its length, name and notes (ticks counted from the region's start)."""

    offset: int          # from the start of the first copied region
    length: int
    name: str
    mute: bool
    player: dict
    notes: list          # [(tick from the region start, length, pitch, velocity)]
    loops: int = 1


def copy_regions(track, indices):
    """RegionCopy for each chosen region, in time order."""
    chosen = sorted((track.note_regions[i] for i in indices), key=lambda r: r.start)
    if not chosen:
        return []
    first = chosen[0].start
    return [RegionCopy(r.start - first, r.length, r.name, r.mute, copy.deepcopy(r.player),
                       [(n.tick - r.start, n.length, n.pitch, n.velocity) for _i, n in notes_in(track, r.start, r.end)],
                       r.loops)
            for r in chosen]


def paste_regions(track, copies, at_tick):
    """Put copied regions on a track from `at_tick`, replacing whatever was there.
    Returns the new regions."""
    placed = []
    for c in copies:
        start = at_tick + c.offset
        end = start + c.length
        clear_span(track, start, end)
        region = claim(track, start, end, c.name, c.mute, copy.deepcopy(c.player), c.loops)
        for tick, length, pitch, velocity in c.notes:
            track.notes.append(Note(start + tick, length, pitch, velocity))
        placed.append(region)
    track.sort_notes()
    return placed


def delete_regions(track, indices):
    """Remove the chosen regions and their notes."""
    chosen = [track.note_regions[i] for i in indices]
    for r in chosen:
        clear_span(track, r.start, r.end)
    track.note_regions = [r for r in track.note_regions if all(r is not c for c in chosen)]


def split_region(track, index, tick):
    """Split a region in two at `tick` (inside it). Returns the index of the second part."""
    r = track.note_regions[index]
    if not r.start < tick < r.end:
        raise ValueError("Move the playhead inside the region to split it there")
    second = NoteRegion(tick, r.end, r.name, r.mute, copy.deepcopy(r.player))
    r.end = tick
    r.loops = 1          # each part plays once (a loop of the whole would not make sense in two halves)
    track.note_regions.insert(index + 1, second)
    return index + 1


def join_regions(track, indices):
    """Join the chosen regions (and anything between them) into one. Returns its index."""
    chosen = sorted(indices)
    if len(chosen) < 2:
        raise ValueError("Select two or more regions to join")
    first, last = track.note_regions[chosen[0]], track.note_regions[chosen[-1]]
    joined = NoteRegion(first.start, last.end, first.name, first.mute, copy.deepcopy(first.player))
    track.note_regions = [r for r in track.note_regions if r.end <= joined.start or r.start >= joined.end]
    track.note_regions.append(joined)
    track.note_regions.sort(key=lambda r: r.start)
    return next(i for i, r in enumerate(track.note_regions) if r is joined)
