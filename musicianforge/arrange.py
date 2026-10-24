"""Rearranging a song by whole bars and sections.

Everything here works on whole bars, and keeps the song consistent:
- notes and recordings move with their bars (a recording belongs to the bar it starts in),
- regions move with their bars too; inserting bars inside a region splits it,
  and deleting bars shortens or removes the regions there,
- tempo, time signature and key changes move with their bars,
- automation points (volume, pan, effect settings) move with their bars too (23 Oct 2026; until then they stayed
  where they were, so a moved or deleted section left its fades behind),
- the tempo, time signature and key in effect around an edit are restored
  afterwards, so the rest of the song sounds exactly as before.

Callers wrap these functions in Session.edit(), which provides undo.
"""

import copy
from dataclasses import dataclass, field, replace

from . import automation as autolanes
from . import chords as chordtrack
from .song import DEFAULT_SECTION_BARS, Note, NoteRegion, Section
from .timeline import KeyChange, TempoChange, TimeSignatureChange


@dataclass
class Clip:
    """A copy of some bars: their meter, tempo and key changes and their notes."""

    bars: int
    ticks: int
    time_signatures: list   # (bar offset, numerator, denominator); offset 0 always present
    tempos: list            # (bar offset, beat, bpm); offset 0 beat 1 always present
    keys: list              # (bar offset, tonic, scale); offset 0 always present
    notes: dict = field(default_factory=dict)  # track id -> [(tick offset, length, pitch, velocity)]
    regions: dict = field(default_factory=dict)  # track id -> [(tick offset, AudioRegion copy)]
    note_regions: dict = field(default_factory=dict)  # track id -> [NoteRegion copies, ticks from the clip start]
    chords: list = field(default_factory=list)  # [(tick offset, ChordChange copy)]; the chord at the start first
    # track id -> {lane target key: [[tick offset, value, glide], ...]}; a point with a fourth item True was added
    # where the copy cut through the lane (it is left out again where the lane does not need it)
    automation: dict = field(default_factory=dict)


def extract(song, start_bar, end_bar):
    """Copy bars start_bar .. end_bar - 1 (notes that run past the end are shortened)."""
    tl = song.timeline
    t0, t1 = tl.bar_to_tick(start_bar), tl.bar_to_tick(end_bar)
    ts = tl.time_signature_at_bar(start_bar)
    sigs = [(0, ts.numerator, ts.denominator)]
    sigs += [(t.bar - start_bar, t.numerator, t.denominator) for t in tl.time_signatures
             if start_bar < t.bar < end_bar]
    tempos = [(0, 1.0, tl.tempo_at_tick(t0))]
    tempos += [(t.bar - start_bar, t.beat, t.bpm) for t in tl.tempos
               if start_bar <= t.bar < end_bar and not (t.bar == start_bar and t.beat == 1.0)]
    key = tl.key_at_bar(start_bar)
    keys = [(0, key.tonic, key.scale)]
    keys += [(k.bar - start_bar, k.tonic, k.scale) for k in tl.keys if start_bar < k.bar < end_bar]
    notes, regions, spans = {}, {}, {}
    for track in song.tracks:
        notes[track.id] = [(n.tick - t0, min(n.length, t1 - n.tick), n.pitch, n.velocity)
                           for n in track.notes if t0 <= n.tick < t1]
        regions[track.id] = [(r.tick - t0, copy.deepcopy(r)) for r in track.regions if t0 <= r.tick < t1]
        spans[track.id] = [NoteRegion(max(r.start, t0) - t0, min(r.end, t1) - t0, r.name, r.mute,
                                      copy.deepcopy(r.player), r.loops)
                           for r in track.note_regions if r.start < t1 and r.end > t0]
    clip_chords = []
    starting = chordtrack.chord_at(song.chords, t0)
    if starting is not None:
        clip_chords.append((0, copy.deepcopy(starting)))
    clip_chords += [(c.tick - t0, copy.deepcopy(c)) for c in song.chords if t0 < c.tick < t1]
    lanes = {track.id: _extract_lanes(track, t0, t1) for track in song.tracks}
    return Clip(end_bar - start_bar, t1 - t0, sigs, tempos, keys, notes, regions, spans, clip_chords,
                {tid: found for tid, found in lanes.items() if found})


def empty_clip(song, before_bar, bars):
    """Silent bars that continue the meter, tempo and key of the bar before `before_bar`."""
    tl = song.timeline
    reference = max(1, before_bar - 1)
    ts = tl.time_signature_at_bar(reference)
    tick = max(0, tl.bar_to_tick(before_bar) - 1)
    key = tl.key_at_bar(reference)
    ticks = bars * ts.numerator * tl.ticks_per_beat(reference)
    return Clip(bars, ticks, [(0, ts.numerator, ts.denominator)], [(0, 1.0, tl.tempo_at_tick(tick))],
                [(0, key.tonic, key.scale)], {})


def insert_clip(song, at_bar, clip):
    """Insert the clip's bars at `at_bar`, pushing everything from there on later."""
    tl = song.timeline
    n = clip.bars
    at_tick = tl.bar_to_tick(at_bar)
    ts_after = tl.time_signature_at_bar(at_bar)
    tempo_after = tl.tempo_at_tick(at_tick)
    key_after = tl.key_at_bar(at_bar)

    # Order matters: later entries win when two land on the same bar.
    # 1) what was in effect at the insertion point, restored after the clip
    # 2) the existing changes, shifted
    # 3) the clip's own changes
    sigs = [TimeSignatureChange(at_bar + n, ts_after.numerator, ts_after.denominator)]
    sigs += [TimeSignatureChange(t.bar + n if t.bar >= at_bar else t.bar, t.numerator, t.denominator)
             for t in tl.time_signatures]
    sigs += [TimeSignatureChange(at_bar + off, num, den) for off, num, den in clip.time_signatures]
    tempos = [TempoChange(at_bar + n, 1.0, tempo_after)]
    tempos += [TempoChange(t.bar + n if t.bar >= at_bar else t.bar, t.beat, t.bpm) for t in tl.tempos]
    tempos += [TempoChange(at_bar + off, beat, bpm) for off, beat, bpm in clip.tempos]
    keys = [KeyChange(at_bar + n, key_after.tonic, key_after.scale)]
    keys += [KeyChange(k.bar + n if k.bar >= at_bar else k.bar, k.tonic, k.scale) for k in tl.keys]
    keys += [KeyChange(at_bar + off, tonic, scale) for off, tonic, scale in clip.keys]
    tl.time_signatures, tl.tempos, tl.keys = sigs, tempos, keys
    tl.rebuild()
    _drop_redundant_changes(tl)

    for track in song.tracks:
        for note in track.notes:
            if note.tick >= at_tick:
                note.tick += clip.ticks
        for off, length, pitch, velocity in clip.notes.get(track.id, []):
            track.notes.append(Note(at_tick + off, length, pitch, velocity))
        track.sort_notes()
        for region in track.regions:
            if region.tick >= at_tick:
                region.tick += clip.ticks
        for off, region in clip.regions.get(track.id, []):
            placed = copy.deepcopy(region)
            placed.tick = at_tick + off
            track.regions.append(placed)
        track.sort_regions()
        spans = []
        for r in track.note_regions:
            if r.end <= at_tick:
                spans.append(r)
            elif r.start >= at_tick:
                r.start += clip.ticks
                r.end += clip.ticks
                spans.append(r)
            else:  # the new bars go inside this region: it splits around them
                spans.append(NoteRegion(r.start, at_tick, r.name, r.mute, copy.deepcopy(r.player)))
                spans.append(NoteRegion(at_tick + clip.ticks, r.end + clip.ticks, r.name, r.mute,
                                        copy.deepcopy(r.player)))
        for r in clip.note_regions.get(track.id, []):
            spans.append(NoteRegion(at_tick + r.start, at_tick + r.end, r.name, r.mute, copy.deepcopy(r.player),
                                    r.loops))
        spans.sort(key=lambda r: r.start)
        track.note_regions = spans
        _insert_lanes(track, at_tick, clip)

    # the chord track: what plays after the inserted bars is what played there before
    after = chordtrack.chord_at(song.chords, at_tick)
    moved = []
    for change in song.chords:
        if change.tick >= at_tick:
            change.tick += clip.ticks
        moved.append(change)
    for off, change in clip.chords:
        placed = copy.deepcopy(change)
        placed.tick = at_tick + off
        moved.append(placed)
    moved = chordtrack.sort(moved)
    if after is not None and not any(c.tick == at_tick + clip.ticks for c in moved) \
            and not _same_chord(chordtrack.chord_at(moved, at_tick + clip.ticks), after):
        # (only when the chord there would be another one: until 24 Oct 2026 every added or deleted section left a
        # chord change nobody placed, repeating the chord already playing, in the chord track)
        moved.append(chordtrack.ChordChange(at_tick + clip.ticks, after.root, after.quality, after.bass))
    song.chords = chordtrack.sort(moved)


def delete_bars(song, start_bar, end_bar):
    """Remove bars start_bar .. end_bar - 1 and pull everything after them earlier."""
    if end_bar <= start_bar:
        return
    tl = song.timeline
    n = end_bar - start_bar
    t0, t1 = tl.bar_to_tick(start_bar), tl.bar_to_tick(end_bar)
    span = t1 - t0
    ts_end = tl.time_signature_at_bar(end_bar)
    tempo_end = tl.tempo_at_tick(t1)
    key_end = tl.key_at_bar(end_bar)

    def keep(bar):
        return bar < start_bar or bar >= end_bar

    def moved(bar):
        return bar - n if bar >= end_bar else bar

    sigs = [TimeSignatureChange(start_bar, ts_end.numerator, ts_end.denominator)]
    sigs += [TimeSignatureChange(moved(t.bar), t.numerator, t.denominator) for t in tl.time_signatures if keep(t.bar)]
    tempos = [TempoChange(start_bar, 1.0, tempo_end)]
    tempos += [TempoChange(moved(t.bar), t.beat, t.bpm) for t in tl.tempos if keep(t.bar)]
    keys = [KeyChange(start_bar, key_end.tonic, key_end.scale)]
    keys += [KeyChange(moved(k.bar), k.tonic, k.scale) for k in tl.keys if keep(k.bar)]
    tl.time_signatures, tl.tempos, tl.keys = sigs, tempos, keys
    tl.rebuild()
    _drop_redundant_changes(tl)

    for track in song.tracks:
        kept = []
        for note in track.notes:
            if note.tick < t0:
                if note.tick + note.length > t0:
                    note.length = t0 - note.tick
                kept.append(note)
            elif note.tick >= t1:
                note.tick -= span
                kept.append(note)
        track.notes = kept
        regions = []
        for region in track.regions:
            if region.tick < t0:
                regions.append(region)
            elif region.tick >= t1:
                region.tick -= span
                regions.append(region)
        track.regions = regions
        spans = []
        for r in track.note_regions:
            start = r.start if r.start < t0 else max(t0, r.start - span)
            end = r.end if r.end <= t0 else max(t0, r.end - span)
            if r.start >= t1:
                start, end = r.start - span, r.end - span
            if end > start:
                r.start, r.end = start, end
                spans.append(r)
        track.note_regions = spans
        _delete_lanes(track, t0, t1)

    # the chord track: the chord playing at the end of the deleted bars carries on from where they were
    at_end = chordtrack.chord_at(song.chords, t1)
    kept = [c for c in song.chords if c.tick < t0]
    for change in song.chords:
        if change.tick >= t1:
            change.tick -= span
            kept.append(change)
    if at_end is not None and at_end.tick < t1 and not _same_chord(chordtrack.chord_at(chordtrack.sort(kept), t0), at_end):
        kept.append(chordtrack.ChordChange(t0, at_end.root, at_end.quality, at_end.bass))
    song.chords = chordtrack.sort(kept)


def _same_chord(a, b):
    """Whether two chord changes are the same chord (either None: no)."""
    return a is not None and b is not None and \
        (a.root % 12, a.quality, a.bass) == (b.root % 12, b.quality, b.bass)


# ----------------------------------------------------------------------
# automation points (23 Oct 2026)
# ----------------------------------------------------------------------
# Points move with their bars, the way notes do. Where an edit cuts through a lane, a point is added so the lane
# keeps the value it had there: at the start of copied bars, where deleted bars were, and after inserted bars (the
# rest of the song sounds as before). Such an added point is left out again when the lane sounds the same without
# it, so the Automation window does not fill up with points nobody placed.
def _glide_at(points, tick):
    """Whether the lane glides (True) or holds (False) at `tick`: the flag of the point at or before it."""
    before = [p for p in points if p[0] <= tick]
    return bool(before[-1][2]) if before else True


def _value_at(points, tick):
    value = autolanes.value_at(points, tick)
    return None if value is None else round(float(value), 6)


def _value_before(points, tick):
    """The value a lane comes to just before `tick` (a point exactly at `tick` may jump away from it)."""
    before = [p for p in points if p[0] < tick]
    if not before:
        return _value_at(points, tick)
    last = before[-1]
    following = points[len(before)] if len(before) < len(points) else None
    if not last[2] or following is None:
        return last[1]
    span = float(following[0] - last[0])
    return round(last[1] + (following[1] - last[1]) * (tick - last[0]) / span, 6) if span > 0 else following[1]


def _cut_point(points, tick):
    """A point at `tick` that keeps a lane exactly as it was there: [tick, value, glide]."""
    return [int(tick), _value_at(points, tick), _glide_at(points, tick)]


def _needed(points, i):
    """Whether the lane would sound different without points[i]."""
    tick, value, glide = points[i][0], points[i][1], bool(points[i][2])
    if len(points) == 1:
        return True
    if i == 0:
        return points[1][1] != value
    prev = points[i - 1]
    nxt = points[i + 1] if i + 1 < len(points) else None
    if not prev[2]:                       # the point before holds its value up to here
        return value != prev[1] or (glide and nxt is not None and nxt[1] != value)
    if nxt is None:                       # the point before glides to this one, which then holds to the end
        return value != prev[1]
    if not glide:
        return True
    # three points with glides: this one is needed unless it lies on the straight line between its neighbours
    span = float(nxt[0] - prev[0])
    on_line = prev[1] + (nxt[1] - prev[1]) * (tick - prev[0]) / span if span > 0 else nxt[1]
    return abs(on_line - value) > 1e-6


def _tidy(entries):
    """entries: [(point, added)] in any order; a later entry at the same tick wins, so the caller lists an
    added point before a real one at the same place. Returns the lane's points, in time order, without added
    points it does not need."""
    by_tick = {}
    for point, added in entries:
        if point[1] is None:
            continue
        by_tick[int(point[0])] = ([int(point[0]), point[1], bool(point[2])], added)
    ordered = [by_tick[t] for t in sorted(by_tick) if t >= 0]
    changed = True
    while changed:
        changed = False
        points = [p for p, _added in ordered]
        for i in range(len(ordered) - 1, -1, -1):
            if ordered[i][1] and not _needed(points, i):
                del ordered[i]
                changed = True
                break
    return autolanes.sort_points([p for p, _added in ordered])


def _extract_lanes(track, t0, t1):
    """{lane target key: points of ticks t0 .. t1 - 1, from tick 0}, for lanes with points."""
    found = {}
    for lane in track.automation or []:
        points = lane.get("points") or []
        if not points:
            continue
        inside = [[p[0] - t0, p[1], bool(p[2])] for p in points if t0 <= p[0] < t1]
        start = _cut_point(points, t0) + [True]            # a fourth item True: a point added here, not placed
        start[0] = 0
        clip_points = ([start] if not inside or inside[0][0] > 0 else []) + inside
        last = clip_points[-1]
        if last[2] and t1 - 1 - t0 > last[0]:
            # the lane glides on past the end of the copied bars: keep where it has got to by their last tick
            clip_points.append([t1 - 1 - t0, _value_at(points, t1 - 1), True, True])
        found[autolanes.target_key(lane)] = clip_points
    return found


def _lane_for(track, key):
    for lane in track.automation:
        if autolanes.target_key(lane) == key:
            return lane
    lane = autolanes.new_lane(key[0], key[1], key[2])
    track.automation.append(lane)
    return lane


def _insert_lanes(track, at_tick, clip):
    """Push points from at_tick on later by the clip's length and put the clip's points in the gap. Bars inserted
    without points of their own (new silent bars) keep the value the lane had at at_tick."""
    ticks = clip.ticks
    own = clip.automation.get(track.id, {})
    for key in own:
        _lane_for(track, key)
    for lane in track.automation or []:
        points = lane.get("points") or []
        clip_points = own.get(autolanes.target_key(lane))
        if not points and not clip_points:
            continue          # a lane without points changes nothing; giving it one would
        entries = [(list(p), False) for p in points if p[0] < at_tick]
        if points:
            if clip_points is None:
                # new bars hold the value the lane had just before them (they belong to the section they follow)
                entries.append(([at_tick, _value_before(points, at_tick), False], True))
            elif at_tick > 0 and _glide_at(points, at_tick - 1):
                entries.append((_cut_point(points, at_tick - 1), True))        # a glide reaches the clip as before
        for p in clip_points or []:
            entries.append(([at_tick + p[0], p[1], bool(p[2])], len(p) > 3 and bool(p[3])))
        if points:
            after = _cut_point(points, at_tick)          # after the new bars the lane goes on as it did from at_tick
            after[0] = at_tick + ticks
            entries.append((after, True))
        entries += [([p[0] + ticks, p[1], bool(p[2])], False) for p in points if p[0] >= at_tick]
        lane["points"] = _tidy(entries)


def _delete_lanes(track, t0, t1):
    """Take out the points of ticks t0 .. t1 - 1 and pull later ones earlier. From t0 on, the lane goes on as it
    went on from t1."""
    span = t1 - t0
    for lane in track.automation or []:
        points = lane.get("points") or []
        if not points:
            continue
        entries = [(list(p), False) for p in points if p[0] < t0]
        if t0 > 0 and _glide_at(points, t0 - 1):
            entries.append((_cut_point(points, t0 - 1), True))        # a glide into the deleted bars ends as it did
        joined = _cut_point(points, t1)
        joined[0] = t0
        entries.append((joined, True))
        entries += [([p[0] - span, p[1], bool(p[2])], False) for p in points if p[0] >= t1]
        lane["points"] = _tidy(entries)


def _drop_redundant_changes(tl):
    """Remove changes that repeat what is already in effect (keeps the lists tidy)."""
    sigs = [tl.time_signatures[0]]
    for t in tl.time_signatures[1:]:
        if (t.numerator, t.denominator) != (sigs[-1].numerator, sigs[-1].denominator):
            sigs.append(t)
    keys = [tl.keys[0]]
    for k in tl.keys[1:]:
        if (k.tonic, k.scale) != (keys[-1].tonic, keys[-1].scale):
            keys.append(k)
    tempos = [tl.tempos[0]]
    for t in tl.tempos[1:]:
        if abs(t.bpm - tempos[-1].bpm) > 1e-9:
            tempos.append(t)
    if (len(sigs), len(keys), len(tempos)) != (len(tl.time_signatures), len(tl.keys), len(tl.tempos)):
        tl.time_signatures, tl.keys, tl.tempos = sigs, keys, tempos
        tl.rebuild()


# ----------------------------------------------------------------------
# whole sections
# ----------------------------------------------------------------------
def add_section_after(song, index, length=DEFAULT_SECTION_BARS):
    """A new empty section right after section `index`. Returns its index."""
    _start, end = song.section_bounds(index)
    insert_clip(song, end, empty_clip(song, end, length))
    song.sections.insert(index + 1, Section(length))
    return index + 1


def duplicate_section(song, index):
    """Copy a section (with its notes, recordings, chords and changes) to the end of the song, so it becomes the
    last section: with sections 1, 2 and 3, duplicating any of them makes section 4 (Russell, 9 Oct 2026; until
    then the copy went right after the section it came from). Returns the copy's index."""
    start, end = song.section_bounds(index)
    song_end = song.section_bounds(len(song.sections) - 1)[1]
    insert_clip(song, song_end, extract(song, start, end))
    song.sections.append(replace(song.sections[index]))
    return len(song.sections) - 1


def delete_section(song, index):
    """Remove a section and everything in it. The song always keeps at least one section."""
    if len(song.sections) <= 1:
        raise ValueError("A song needs at least one section. Change its length instead.")
    start, end = song.section_bounds(index)
    delete_bars(song, start, end)
    del song.sections[index]


def move_section(song, index, delta):
    """Swap a section with its neighbour (delta -1 = earlier, +1 = later). Returns its new index."""
    other = index + delta
    if not 0 <= other < len(song.sections) or delta not in (-1, 1):
        raise ValueError("That section cannot move further")
    first, second = (other, index) if delta < 0 else (index, other)
    # move `second` in front of `first`
    s2, e2 = song.section_bounds(second)
    s1, _e1 = song.section_bounds(first)
    clip = extract(song, s2, e2)
    delete_bars(song, s2, e2)
    insert_clip(song, s1, clip)
    song.sections[first], song.sections[second] = song.sections[second], song.sections[first]
    return other


def set_section_length(song, index, length):
    """Make a section longer (silent bars at its end) or shorter (removes bars from its end)."""
    length = int(length)
    if length < 1:
        raise ValueError("A section must be at least 1 bar long")
    start, end = song.section_bounds(index)
    current = end - start
    if length > current:
        insert_clip(song, end, empty_clip(song, end, length - current))
    elif length < current:
        delete_bars(song, start + length, end)
    song.sections[index].length = length


def notes_in_bars(song, start_bar, end_bar):
    """How many notes start in bars start_bar .. end_bar - 1."""
    tl = song.timeline
    t0, t1 = tl.bar_to_tick(start_bar), tl.bar_to_tick(end_bar)
    return sum(1 for t in song.tracks for n in t.notes if t0 <= n.tick < t1)


def regions_in_bars(song, start_bar, end_bar):
    """How many recordings start in bars start_bar .. end_bar - 1."""
    tl = song.timeline
    t0, t1 = tl.bar_to_tick(start_bar), tl.bar_to_tick(end_bar)
    return sum(1 for t in song.tracks for r in t.regions if t0 <= r.tick < t1)


def grow_section_for_recording(song, index, new_notes):
    """After a take in an Automatic section: grow it to hold notes recorded past its end.

    Material after the section (later sections) moves later to make room; the
    new notes stay exactly where they were played. Returns the bars added.
    """
    if not new_notes:
        return 0
    return grow_section_to(song, index, max(n.tick + n.length for n in new_notes))


def grow_section_to(song, index, last_end):
    """Grow an Automatic section so it reaches `last_end` (a tick). Returns the bars added."""
    tl = song.timeline
    start, end = song.section_bounds(index)
    if last_end <= 0:
        return 0
    needed_end = tl.tick_to_bar(last_end - 1) + 1
    growth = max(0, needed_end - end)
    if growth == 0:
        return 0
    if index < len(song.sections) - 1:
        # make room: push the following sections later, but not the new notes
        insert_clip(song, end, empty_clip(song, end, growth))
    song.sections[index].length += growth
    return growth
