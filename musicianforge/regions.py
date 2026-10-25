"""Regions on instrument tracks: named stretches of a track that own the notes starting in them.

A track's notes stay in one list (that is what plays and what the event list
shows); regions mark out stretches of it, like boxes laid along the timeline:

- Recording makes a region that covers exactly what was recorded: the
  looping section, or from the bar where recording started to the bar after it
  stopped (across sections when All sections is on). Regions it overlaps get
  shorter, or are split around it; a looping region it lands on carries on
  after it as it would have played (0.9.11, continue_loop below).
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


# ----------------------------------------------------------------------
# a looping region's playing, carried on somewhere else (0.9.11)
# ----------------------------------------------------------------------
# Russell, 25 Oct 2026: a take recorded over a looping region's repeats replaces only the bars it recorded, and the
# repeats carry on after it exactly as they would have played; bars inserted in the middle of a loop leave it playing
# on both sides of them (and bars deleted from it, or a section moved, keep each side's music). Until then the take
# (being the next region) cut the loop where it started, so the repeats after it went silent, and inserted bars either
# split the region into two halves that played once or let its repeats run on into the new bars. These work out the
# regions that do it: session._place_take_region and arrange (insert_clip, delete_bars, extract) use them.
MAX_LOOPS = 999       # the most a region plays (Session.set_region_loops; NoteRegion.from_list keeps a saved one to it)


def loop_pieces(region, notes, p, until, carry_on=True, song_end=None):
    """The regions that play what a looping `region` plays from tick p on, with the phase it has there, up to tick
    `until` (where its playing stops: arrangement.note_region_repeats). Returns [(start, end, loops, notes)] with
    ticks counted from p; notes [(tick from the piece's start, length, pitch, velocity)] are the region's own notes
    (`notes`: those that start in it, as they were) as each piece plays them.

    The first piece is the rest of the repeat that p falls in (none where a repeat starts). Then comes the region
    itself, looping the repeats left. carry_on True: it keeps the loop's setting (the count left, or 0: until the next
    region), so the loop goes on as before and the next region, or the song end, still cuts it where it did.
    carry_on False: the pieces end exactly at `until` (whole repeats, then the part of one that `until` cuts), for a
    loop that has to stop there with no region after it to cut it. A piece that would reach past `until` is cut there
    and plays once. The pieces of a rhythm player region are rhythm player regions with the same settings; one shorter
    than the region (the rest of a repeat, or the part of one) starts its pattern afresh, as any shorter region does,
    so it plays the pattern's first bars, not the bars of the repeat it stands for.
    song_end: where the song ends (counted as `until` is): a note that would ring past it ends there, as it is heard,
    or the song would grow a bar to hold it (the fourth review of 25 Oct 2026: a riff's held note in the last repeat,
    cut by the song's end, made the song longer once it was carried on as a region)."""
    length = region.length
    if length <= 0 or not region.start <= p < until:
        return []
    repeat, offset = divmod(p - region.start, length)
    left = None if region.loops == 0 else region.loops - repeat      # repeats still to start (with the current one)
    if left is not None and left <= 0:
        return []                                     # it had played all its repeats by p
    own = sorted(((n.tick - region.start, n.length, n.pitch, n.velocity) for n in notes
                  if region.start <= n.tick < region.end), key=lambda n: (n[0], n[2]))
    span = until - p
    pieces = []
    at = 0
    if offset:
        pieces.append((0, length - offset, 1,
                       [(tick - offset, ln, pitch, velocity) for tick, ln, pitch, velocity in own if tick >= offset]))
        at = length - offset
        left = None if left is None else left - 1
    if carry_on:
        if left is None or left > 0:
            pieces.append((at, at + length, 0 if left is None else left, own))
    else:
        whole = max(0, (span - at) // length)
        if left is not None:
            whole = min(whole, left)
        while whole > 0:                              # (a count over MAX_LOOPS goes on in another copy)
            count = min(whole, MAX_LOOPS)
            pieces.append((at, at + length, count, own))
            at += count * length
            whole -= count
            left = None if left is None else left - count
        if at < span and (left is None or left > 0):
            pieces.append((at, at + length, 1, own))      # the part of a repeat that `until` cuts (just below)
    found = []
    for start, end, loops, piece_notes in pieces:
        if start >= span:
            break
        if end > span:
            end, loops = span, 1
            piece_notes = [n for n in piece_notes if n[0] < end - start]
        if song_end is not None:
            last = song_end - p - start
            piece_notes = [(tick, min(ln, last - tick), pitch, velocity) for tick, ln, pitch, velocity in piece_notes]
        found.append((start, end, loops, piece_notes))
    return found


def place_pieces(track, region, pieces, at):
    """Put loop_pieces of `region` on a track from tick `at`. Each piece takes the region's name, mute and rhythm player
    settings, and replaces whatever was in its stretch (the callers place them where only the region's own music was).
    Returns the new regions."""
    placed = []
    for start, end, loops, piece_notes in pieces:
        first, last = at + start, at + end
        clear_span(track, first, last)
        placed.append(claim(track, first, last, region.name, region.mute, copy.deepcopy(region.player), loops))
        track.notes.extend(Note(first + tick, length, pitch, velocity) for tick, length, pitch, velocity in piece_notes)
    track.sort_notes()
    return placed


def continue_loop(track, region, notes, p, q, until, song_end=None):
    """Carry a looping region's playing on from tick q with the phase it had at tick p, up to where its playing
    stopped (`until`, which moves with q): after a take recorded over it (p == q: the take's end), after bars inserted
    in the middle of it (q = p + their length), or where bars deleted from it were (q < p).
    region: the region as it was (a copy: the edit may have changed or removed it); notes: its own notes as they were.
    song_end: where the song ended (counted as p is; loop_pieces). Returns the new regions."""
    return place_pieces(track, region, loop_pieces(region, notes, p, until, song_end=song_end), q)


def write_loop_out(track, start, end, notes, name="", mute=False):
    """Make ticks start .. end one ordinary region holding `notes` (Note objects at song ticks) in place of the regions
    that carried a loop on there: what a rhythm player copy that would not sound like the loop becomes
    (Session._match_loops; Russell, 25 Oct 2026, "Match the loop"). Returns the region."""
    clear_span(track, start, end)
    region = claim(track, start, end, name, mute)
    track.notes.extend(notes)
    track.sort_notes()
    return region


def count_is_heard(region):
    """Whether a looping region sounds the same when its count comes down to the repeats heard before the region that
    cuts it: every region but a rhythm player region of rules older than 7, whose count picks the repeat that leads
    into what follows (arrangement.sounding_notes counts the repeats heard from rules 7 on). Those keep their count, so
    they play the same notes as before; their line in the Regions list says where the loop stops."""
    return not region.player or region.player.get("rules", 1) >= 7


def stop_loop_at(track, region, tick, notes=None, ends_there=False, first_end=None):
    """Make a looping region on the track stop playing at `tick`, keeping everything before it as it was.

    Inside its first play it ends there and plays once (first_end: where that ended before the edit shortened the
    region to `tick`; default: where it ends now). Further on it plays its repeats up to there. When a region
    starts at `tick`, it cuts the repeat it lands in, as it always did: the count comes down to the repeats heard
    (count_is_heard), and Loops 0 (until the next region) stays. Loops 0 also stays when the song ends at `tick`
    (ends_there). Otherwise (bars were inserted or deleted there, with no region after them) the region plays its whole
    repeats up to `tick`, and a region of its own plays the part of the next repeat before it.
    notes: the region's own notes as they were (default: those on the track now). Returns the regions added."""
    length = region.length
    if length <= 0 or tick <= region.start:
        return []
    if tick < (region.end if first_end is None else first_end):
        region.end, region.loops = min(region.end, tick), 1
        return []
    repeats, offset = divmod(tick - region.start, length)
    if region.loops >= 1 and region.loops * length <= tick - region.start:
        return []                                     # it had stopped by then
    if region.loops == 0 and ends_there:
        return []
    if any(r.start == tick for r in track.note_regions if r is not region):
        if region.loops >= 1 and count_is_heard(region):
            region.loops = min(region.loops, repeats + (1 if offset else 0))
        return []
    was = copy.deepcopy(region)
    if notes is None:
        notes = [n for n in track.notes if region.start <= n.tick < region.end]
    pieces = loop_pieces(was, notes, region.start, tick, carry_on=False, song_end=tick if ends_there else None)
    if not pieces:
        return []
    region.loops = pieces[0][2]                       # the region itself: its whole repeats up to `tick`
    return place_pieces(track, was, pieces[1:], region.start)
