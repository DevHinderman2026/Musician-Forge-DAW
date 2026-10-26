"""Looping recordings on audio tracks around section edits and newer recordings (0.9.11).

Russell, 25 Oct 2026 ("Keep going on both sides"): a looping recording works as a looping region on an instrument
track does (arrange.py, regions.continue_loop). Around bars put in or taken out in the middle of its playing it plays
as it did up to them, inserted bars are empty for it, and after them the rest of its playing carries on from the same
point in the recording, in step with the music it played with, and stops where it stopped. A section added at the end
of the song, or the last section made longer: a recording looping until the next region (or the end of the song)
stops where the song ended. Copied bars hold what a looping recording plays in them, and a looping recording copied
with them stays inside them. A newer recording made over its repeats cuts it only there: after the new recording it
carries on.

Until then a looping recording kept its start and its count whatever happened around it: it played straight on
through a new section; the music after new or deleted bars heard it out of step (a bar off when they were not whole
repeats, seconds off where a section of another tempo came before); a set count stopped early or late (a deleted
section's bars came back as empty bars at the end of the song, holding only the loop); a loop that began in a deleted
section lost all its repeats; it looped on into a section added at the end; a copied section held nothing of a loop
begun before it, and a copied looping recording ran on past the copy; a newer recording over its repeats silenced
the rest of it.

A recording plays in seconds and the song in bars, so all of it is worked out in frames of the recording's playing
(its repeats one after another), on the timeline as it was before the edit. What carries a loop on are pieces: copies
of the recording, each with its own start in it (offset), length and loops, so the engine plays them as it plays any
recording, and a project made before plays exactly as it did. A piece starts on a whole tick. After whole repeats
those repeats play on into the next one up to the first whole tick, and the piece carries on from exactly the frame
there, its start in the recording worked out in frames from the exact time, so nothing is skipped and nothing plays
twice (_part_after_repeats; the random-edit tester, 26 Oct 2026: at 40.5 BPM a tick is 74 frames, and the piece with
the last 30 frames of a repeat landed on the tick of the next repeat's piece, which hid it, so those frames were
skipped and the rest played 30 frames early). After the rest of a repeat (a piece that starts partway into one) the
next repeat can be up to half a tick from where it was (a quarter of a millisecond at 120 BPM): a piece plays its
frames in one run, so nothing goes on past a repeat's end there. Every piece fades in and out over a few frames where
it starts and ends, as every repeat of a looping recording always has (engine.FADE_FRAMES).
"""

import copy
import math
from types import SimpleNamespace

from . import arrangement
from .regions import MAX_LOOPS
from .song import AUDIO_RATE

PIECES = "The looping recording is cut into pieces, so it sounds as it did"
PIECES_MANY = "The looping recordings are cut into pieces, so they sound as they did"
TOLERANCE = 2        # frames: a point this close to where a repeat starts or ends is that point (rounding)


def pieces_words(count):
    """What is said when an edit cut `count` looping recordings into pieces ('' for none)."""
    if not count:
        return ""
    return PIECES if count == 1 else PIECES_MANY


def words_after(placed):
    """'. The looping recording is cut into pieces, so it sounds as it did' after an edit that cut one (placed: the
    arrange.LoopsCarriedOn it was given, or None), else ''."""
    count = getattr(placed, "recordings", 0) if placed is not None else 0
    return ". " + pieces_words(count) if count else ""


def _count(placed, recordings):
    """Tell a LoopsCarriedOn which looping recordings an edit cut into pieces (recordings: their _recording()s), so the
    session says how many: each one once, however many steps of the edit cut it (a section moved is taken out and put
    back in, a section copied is copied and then put at the end: until the sixth review of 26 Oct 2026 one recording
    cut in two of them was said as "The looping recordings are cut into pieces")."""
    if placed is not None and recordings:
        placed.cut_recordings = set(getattr(placed, "cut_recordings", ())) | set(recordings)
        placed.recordings = len(placed.cut_recordings)


def _recording(region):
    """Which recording a looping recording, or a piece of one (a copy of it), is: its takes' files."""
    return tuple(take.file for take in region.takes)


def looping(track, timeline, song_end):
    """(recording, the tick where its playing stops) for each looping recording on an audio track."""
    if not track.is_audio:
        return []
    return [(region, arrangement.audio_region_repeats(track, index, timeline, song_end)[1])
            for index, region in enumerate(track.regions) if region.loops != 1 and region.frames > 0]


def frames_at(timeline, region, tick):
    """How many frames of a recording's playing (its repeats one after another) come before `tick`."""
    return int(round((timeline.tick_to_seconds(tick) - timeline.tick_to_seconds(region.tick)) * AUDIO_RATE))


def pieces(region, first, last, carry_on=True):
    """The pieces that play frames first .. last of a looping recording's playing (counted from its start; `last` is
    where its playing stops), each with the point in the recording it has: [(frames from `first` to where the piece
    starts, offset, length, loops)], offset and length in frames of the recording as AudioRegion has them.

    First comes the rest of the repeat that `first` falls in (none where a repeat starts), then the recording itself,
    looping the repeats left. carry_on True: that keeps the loop's setting (the count left, or 0: until the next
    recording), so whatever stopped it (the next recording, the song's end, its count) still stops it there; it needs
    a whole repeat before `last`, as a recording that starts inside a recording's first play plays over it and does not
    cut it. Otherwise the pieces end exactly at `last`: whole repeats (at most MAX_LOOPS in one piece), then the part of
    one that `last` cuts."""
    length = region.frames
    if length <= 0 or last - first <= TOLERANCE:
        return []
    repeat, into = divmod(max(0, first), length)
    if into <= TOLERANCE:
        into = 0
    elif into >= length - TOLERANCE:
        repeat, into = repeat + 1, 0
    left = None if region.loops == 0 else region.loops - repeat      # repeats still to start, with this one
    if left is not None and left <= 0:
        return []
    span = last - first
    found, at = [], 0
    if into:
        found.append((0, region.offset + into, min(length - into, span), 1))
        at = length - into
        left = None if left is None else left - 1
    if carry_on and span - at >= length and (left is None or left > 0):
        found.append((at, region.offset, region.length, 0 if left is None else left))
        return found
    while (left is None or left > 0) and span - at > TOLERANCE:
        whole = (span - at) // length
        if left is not None:
            whole = min(whole, left)
        if whole <= 0:
            found.append((at, region.offset, span - at, 1))          # the part of a repeat that `last` cuts
            break
        count = min(whole, MAX_LOOPS)
        found.append((at, region.offset, region.length, count))
        at += count * length
        left = None if left is None else left - count
    return found


def _laid_out(timeline, tick, found, region):
    """Where pieces (from pieces()) of `region` go from `tick`: [(tick, offset, length, loops)], each where the frames
    before it end (in seconds on `timeline`, to the nearest tick). A piece that plays once ends no later than where the
    next one starts, or than where its frames end: starting on a whole tick, it would run up to half a tick into what
    comes after it (the bars added after it, or the end of the song). The part of a repeat after whole repeats carries
    on from exactly where they end (_part_after_repeats)."""
    start = timeline.tick_to_seconds(tick)
    ticks = [int(tick) if not frames else int(round(timeline.seconds_to_tick(start + frames / float(AUDIO_RATE))))
             for frames, _offset, _length, _loops in found]
    last = None
    if len(found) > 1 and _whole_repeats(found[-2], region) and _part_of_one(found[-1], region):
        frames, _offset, length, _loops = found[-1]
        last = _part_after_repeats(timeline, region, (ticks[-2],) + tuple(found[-2][1:]),
                                   _on_a_tick(timeline, _sample(timeline, tick) + frames + length))
    available = region.take.frames if region.take is not None else 0
    laid = []
    for number, (frames, offset, length, loops) in enumerate(found):
        if last is not None and number == len(found) - 2:
            whole, part, at = last
            laid.append(whole)
            if part is not None:
                laid.append(part)                 # (the repeats play on up to it: none of them is missing)
            elif whole[3] > 1:
                laid += _rest_of_repeats(timeline, region, whole, at)
            break
        if loops == 1:
            heard = length or max(0, available - offset)               # (length 0: to the end of the recording)
            end = (timeline.tick_to_seconds(ticks[number + 1]) if number + 1 < len(found)
                   else start + (frames + heard) / float(AUDIO_RATE))
            room = int(round((end - timeline.tick_to_seconds(ticks[number])) * AUDIO_RATE))
            if 0 < room < heard:
                length = room
        laid.append((ticks[number], int(offset), int(length), int(loops)))
        if loops > 1 and number + 1 < len(found):          # (where the engine stops the count: _rest_of_repeats)
            laid += _rest_of_repeats(timeline, region, laid[-1], ticks[number + 1])
    return laid


def _count_stops(timeline, region):
    """The tick where the engine stops a recording's count of repeats, with no recording after it."""
    return arrangement.audio_region_repeats(SimpleNamespace(regions=[region]), 0, timeline, 0)[1]


def _sample(timeline, tick):
    """The song sample where a recording placed at `tick` starts, as the engine places it (PlaybackData)."""
    return timeline.tick_to_sample(tick, AUDIO_RATE)


def _tick_from(timeline, sample):
    """The first whole tick at song sample `sample` or after it."""
    tick = max(0, int(math.floor(timeline.seconds_to_tick(sample / float(AUDIO_RATE)))))
    while _sample(timeline, tick) < sample:
        tick += 1
    while tick > 0 and _sample(timeline, tick - 1) >= sample:
        tick -= 1
    return tick


def _on_a_tick(timeline, sample):
    """`sample`, or the sample of a whole tick within TOLERANCE frames of it: where a looping recording's playing stops
    is a tick (bars going in, a recording starting, the end of the song), and counted in frames from its start it can
    come out a frame off (each is rounded on its own)."""
    exact = _sample(timeline, int(round(timeline.seconds_to_tick(sample / float(AUDIO_RATE)))))
    return exact if abs(exact - sample) <= TOLERANCE else sample


def _whole_repeats(entry, region):
    """Whether a piece from pieces() (frames, offset, length, loops) plays whole repeats of `region`."""
    return entry[1] == region.offset and entry[2] == region.length and entry[3] >= 1


def _part_of_one(entry, region):
    """Whether a piece from pieces() plays the start of one repeat of `region`, not all of it (the part of one that the
    end of its playing cuts)."""
    return entry[1] == region.offset and entry[3] == 1 and 0 < entry[2] < region.frames


def _part_after_repeats(timeline, region, entry, end):
    """Whole repeats of a looping recording, entry (tick, offset, length, loops), each beginning exactly where the one
    before it ends, then the part of the next repeat that plays up to song sample `end`. That part cannot begin exactly
    where they end as a piece of its own, which starts on a whole tick: so the repeats play one more, which goes on into
    that next repeat up to the first whole tick, and the part (a piece) plays the rest of it from that tick, trimmed in
    frames from the exact time. The piece starts after their first play, so it stops them there (a recording that
    starts there would), and nothing is skipped or played twice where they meet. Returns (the entry with one more
    repeat, the piece (tick, offset, length, 1), its tick); (the entry, None, that tick) when less than TOLERANCE
    frames of the part would be left after that tick (left out: the repeats end where they end); None where they end on
    a whole tick (the part starts there, as it always did) or cannot play one more (a count of MAX_LOOPS, one the engine
    would stop before that tick, or a first play that ends after it)."""
    tick, offset, length, loops = (int(value) for value in entry)
    repeats = copy.copy(region)
    repeats.tick, repeats.offset, repeats.length, repeats.loops = tick, offset, length, loops + 1
    each = repeats.frames
    if each <= 0:
        return None
    boundary = _sample(timeline, tick) + loops * each           # where the whole repeats end and the next begins
    at = _tick_from(timeline, boundary)
    into = _sample(timeline, at) - boundary                     # frames of the next repeat before that tick
    if into == 0:
        return None
    rest = min(end - _sample(timeline, at), each - into)
    if rest <= TOLERANCE:
        return (tick, offset, length, loops), None, at
    if repeats.loops > MAX_LOOPS or repeats.end_tick(timeline) > at or _count_stops(timeline, repeats) < at:
        return None
    return (tick, offset, length, repeats.loops), (at, offset + into, rest, 1), at


def _rest_of_repeats(timeline, region, entry, upto):
    """A piece of `region` playing a count of its repeats (entry: (tick, offset, length, loops)), with more of the loop
    from tick `upto`, where those repeats end: [a piece playing what the engine leaves out of them before it], or [].
    The engine counts the repeats in the first play rounded to a whole tick (arrangement.audio_region_repeats), so a
    recording a little longer than its ticks stops its count early, by that much for each repeat: there was a dropout
    before `upto` (a millisecond or more; after 999 repeats of a short one, up to a quarter of a second at 120 BPM; the
    sixth review of 26 Oct 2026)."""
    piece = copy.copy(region)
    piece.tick, piece.offset, piece.length, piece.loops = entry
    stops, each = _count_stops(timeline, piece), piece.frames
    into = frames_at(timeline, piece, stops) - (piece.loops - 1) * each          # where in its last repeat it stops
    room = frames_at(timeline, piece, upto) - frames_at(timeline, piece, stops)
    if stops >= upto or not 0 <= into < each - TOLERANCE or room <= TOLERANCE:
        return []
    return [(stops, piece.offset + into, min(each - into, room), 1)]


def place(track, timeline, region, found, tick):
    """Put pieces (from pieces()) of a recording on its track from `tick` (_laid_out). Each is a copy of the recording
    (`region`, as it was) with its own start in it, length and loops. Returns them."""
    return _put(track, region, _laid_out(timeline, tick, found, region))


def _put(track, region, laid):
    """Put pieces of a recording (`region`, as it was) on its track: laid, [(tick, offset, length, loops)]. Returns
    them."""
    placed = []
    for at, offset, length, loops in laid:
        piece = copy.deepcopy(region).to_todays_rules()      # (a new recording: today's rules, song.RECORDING_RULES)
        piece.tick, piece.offset, piece.length, piece.loops = at, offset, length, loops
        track.regions.append(piece)
        placed.append(piece)
    if placed:
        track.sort_regions()
    return placed


def stop_at(track, timeline, region, played, ends_there=False, cut_there=False):
    """Make a looping recording on the track stop after `played` frames of its playing, keeping everything before as
    it was: its whole repeats, then a piece with the part of the next one (inside its first play it is trimmed there
    and plays once). cut_there: a recording starts there, after its first play, and cuts it as one always did: Loops 0
    (until the next region) stays, and a count comes down to the repeats heard. ends_there: the song ends there, where
    Loops 0 stops it too. Returns the pieces added."""
    length = region.frames
    if length <= 0 or played <= TOLERANCE or region.loops == 1:
        return []
    if region.loops > 1 and played >= region.loops * length - TOLERANCE:
        return []                                                     # it had stopped by then
    was = copy.deepcopy(region)
    if played >= length - TOLERANCE and (cut_there or (ends_there and region.loops == 0)):
        if region.loops > 1:
            region.loops = max(1, min(region.loops, int(math.ceil((played - TOLERANCE) / float(length)))))
            if 1 < region.loops < was.loops:          # (the engine may stop that count before the cut: below)
                return _from_its_stop(track, timeline, region, was, played, played) or []
        return []
    found = pieces(was, 0, played, carry_on=False)
    if not found:
        return []
    _at, region.offset, region.length, region.loops = found[0]        # the recording itself: what it plays first
    if len(found) == 2 and _whole_repeats(found[0], was) and _part_of_one(found[1], was):
        # its whole repeats, then part of the next one: it plays on into that one up to a whole tick, where a piece
        # carries on from exactly the right frame (_part_after_repeats)
        last = _part_after_repeats(timeline, was, (region.tick,) + tuple(found[0][1:]),
                                   _on_a_tick(timeline, _sample(timeline, region.tick) + played))
        if last is not None:
            whole, part, _tick = last
            if part is not None:
                region.loops = whole[3]
                return _put(track, was, [part])
            played, found = region.loops * length, found[:1]        # (less than a tick of it: left out)
    if region.loops > 1:
        made = _from_its_stop(track, timeline, region, was, region.loops * length, played)
        if made is not None:
            return made
    return place(track, timeline, was, found[1:], region.tick)


def _from_its_stop(track, timeline, region, was, repeats, played):
    """stop_at, for a count of a looping recording's repeats that should play `repeats` frames of its playing: where
    the engine stops that count before (_rest_of_repeats), the rest of its playing up to `played`, in pieces from
    there; else None (nothing is missing)."""
    stops = _count_stops(timeline, region)
    heard = frames_at(timeline, region, stops)
    if heard >= repeats - TOLERANCE:
        return None
    return place(track, timeline, was, pieces(was, heard, played, carry_on=False), stops)


def _starts_at(track, tick, region, sources=None):
    """Whether a recording starts at `tick` (and so cuts `region` there). sources (keep_uncut's): a piece another loop
    got in this edit does not count; it starts where nothing did before."""
    key = sources.get(id(region), id(region)) if sources else None
    return any(r.tick == tick for r in track.regions
               if r is not region and not (sources and id(r) in sources and sources[id(r)] != key))


def _cut_exactly_at(track, region, until, tick):
    """Whether the next recording cuts a looping recording exactly at `tick`, where bars go in or are taken out. It then
    stops there, so it does not wake up when that recording moves away with its bars: a section added there starts
    empty for it, and a section taken out that starts with that recording leaves the bars after it as they were (as
    arrange._cut_at does for looping regions)."""
    return region.tick < tick == until and _starts_at(track, tick, region)


def keep_uncut(track, timeline, sources, song_end, caps=None):
    """After pieces went on an audio track: none of them cuts another looping recording. A recording that starts after
    a looping recording's first play cuts it, whatever its layer, and a piece starts where nothing did before, so a
    looping recording that a piece of another loop would cut carries on from there in pieces of its own, over or under
    it as before (two looping recordings on one track, one played over the other). sources: {id(piece): the loop it
    carries on}, for every piece the edit placed (the pieces this adds join it). caps: {id(recording): the tick it
    must stop by} (a copied section's own loops stay inside it). Returns the pieces added."""
    caps = {} if caps is None else caps
    added = []
    for _round in range(64):
        hit = _cut_by_another_loop(track, timeline, sources, song_end, caps)
        if hit is None:
            break
        region, cut, until, key = hit
        was = copy.deepcopy(region)
        found = pieces(was, frames_at(timeline, region, cut), frames_at(timeline, region, until), carry_on=False)
        new = place(track, timeline, was, found, cut)
        new += stop_at(track, timeline, region, frames_at(timeline, region, cut), cut_there=True)
        for piece in new:
            sources[id(piece)] = key
            if id(region) in caps:
                caps[id(piece)] = caps[id(region)]
        added += new
    return added


def _cut_by_another_loop(track, timeline, sources, song_end, caps):
    """(a looping recording, where a piece of another loop cuts it, where it would stop without them, its loop) for
    the first such recording on the track, or None."""
    for index, region in enumerate(track.regions):
        if region.loops == 1 or region.frames <= 0:
            continue
        key = sources.get(id(region), id(region))

        def foreign(r):
            return id(r) in sources and sources[id(r)] != key

        until = arrangement.audio_region_repeats(track, index, timeline, song_end)[1]
        if not any(r.tick == until and foreign(r) for r in track.regions):
            continue
        shadow = copy.copy(track)
        shadow.regions = [r for r in track.regions if not foreign(r)]
        mine = next(i for i, r in enumerate(shadow.regions) if r is region)
        meant = min(arrangement.audio_region_repeats(shadow, mine, timeline, song_end)[1],
                    caps.get(id(region), song_end))
        if meant > until:
            return region, until, meant, key
    return None


def _loops_in(added):
    """The looping recordings that pieces carry on (each piece is a copy of its recording), for _count."""
    return {_recording(piece) for piece in added}


def _from(sources, made, key):
    """Note that the pieces in `made` carry on the loop `key` (for keep_uncut); returns them."""
    for piece in made:
        sources[id(piece)] = key
    return made


# ----------------------------------------------------------------------
# bars inserted, deleted and copied (arrange.insert_clip, delete_bars, extract, _loops_stop_at_the_end)
# ----------------------------------------------------------------------
def across_insert(song, at_tick):
    """Before bars go in at at_tick, while nothing has moved: the looping recordings playing there, as ({track id:
    [(recording, a copy of it, frames of its playing before at_tick, frames it plays in all)]}, the song's end)."""
    timeline, end = song.timeline, song.song_end_tick()
    found = {}
    for track in song.tracks:
        rows = [(region, copy.deepcopy(region), frames_at(timeline, region, at_tick),
                 frames_at(timeline, region, until))
                for region, until in looping(track, timeline, end)
                if region.tick < at_tick < until or _cut_exactly_at(track, region, until, at_tick)]
        if rows:
            found[track.id] = rows
    return found, end


def after_insert(song, at_tick, ticks, across, placed=None):
    """After `ticks` of bars went in at at_tick (across: across_insert's): a looping recording that was playing there
    plays as it did up to them, they are empty for it, and the rest of its playing carries on after them from the same
    point in the recording. A looping recording that came in with them (a copied section's) stays inside them, as a
    looping region does. placed: a LoopsCarriedOn, told how many recordings were cut into pieces (or None)."""
    rows, old_end = across
    timeline = song.timeline
    after = at_tick + ticks
    song_end = max(old_end, at_tick) + ticks
    cut = set()
    for track in song.tracks:
        if not track.is_audio:
            continue
        sources, caps = {}, {}
        for region in [r for r in track.regions if at_tick <= r.tick < after]:
            caps[id(region)] = after                                  # (it came in with the bars: it stays in them)
            if hasattr(region, "loop_source"):                       # (a copy's piece: copy_playing_in)
                sources[id(region)] = region.loop_source
                del region.loop_source
        for region, was, played, total in rows.get(track.id, []):
            made = place(track, timeline, was, pieces(was, played, total), after) if total > played else []
            _from(sources, made, id(region))
            made += stop_at(track, timeline, region, played, cut_there=_starts_at(track, at_tick, region, sources))
            cut |= _loops_in(_from(sources, made, id(region)))
        for region in [r for r in track.regions if at_tick <= r.tick < after and r.loops != 1]:
            index = next(i for i, r in enumerate(track.regions) if r is region)
            if arrangement.audio_region_repeats(track, index, timeline, song_end)[1] > after:
                key = sources.get(id(region), id(region))
                made = stop_at(track, timeline, region, frames_at(timeline, region, after),
                               ends_there=after >= song_end, cut_there=_starts_at(track, after, region, sources))
                for piece in _from(sources, made, key):
                    caps[id(piece)] = after
                cut |= _loops_in(made)
        cut |= _loops_in(keep_uncut(track, timeline, sources, song_end, caps))
    _count(placed, cut)


def across_delete(song, t0, t1):
    """Before ticks t0 .. t1 are deleted: the looping recordings whose playing reaches into them and out of them, as
    {track id: [(recording, a copy of it, frames of its playing before t0, before t1, and in all)]}."""
    timeline, end = song.timeline, song.song_end_tick()
    found = {}
    for track in song.tracks:
        rows = [(region, copy.deepcopy(region), frames_at(timeline, region, t0), frames_at(timeline, region, t1),
                 frames_at(timeline, region, until))
                for region, until in looping(track, timeline, end)
                if region.tick < t1 and until > t0 and (region.tick < t0 or until > t1)
                or _cut_exactly_at(track, region, until, t0)]
        if rows:
            found[track.id] = rows
    return found, end


def after_delete(song, t0, t1, across, at_the_end, placed=None):
    """After ticks t0 .. t1 were deleted (across: across_delete's): a looping recording plays as it did up to t0, and
    the rest of its playing after t1 carries on from t0 from the same point in the recording (a loop that began in the
    deleted bars too). Where the deleted bars were whole repeats of it, it simply loops on: its count comes down by
    them. at_the_end: the deleted bars ended the song. placed: as for after_insert."""
    rows, old_end = across
    timeline = song.timeline
    song_end = t0 if at_the_end else old_end - (t1 - t0)
    cut = set()
    for track in song.tracks:
        if track.id not in rows:
            continue
        sources = {}
        for region, was, before, after, total in rows[track.id]:
            length = was.frames
            gone = (after - before) % length
            if was.tick < t0 and before >= length - TOLERANCE and total > after and \
                    (gone <= TOLERANCE or gone >= length - TOLERANCE):
                # its own repeats after t0 are what played after t1: the same recording goes on looping (not when t0
                # is inside its first play: the recording that stopped it after them would land in that first play,
                # where a recording does not stop a loop, so it would play on through it; the sixth review, 26 Oct)
                if region.loops > 1:
                    region.loops -= int(round((after - before) / float(length)))
                continue
            made = place(track, timeline, was, pieces(was, after, total), t0) if total > after else []
            _from(sources, made, id(region))
            if was.tick < t0:
                made += stop_at(track, timeline, region, before, ends_there=at_the_end,
                                cut_there=_starts_at(track, t0, region, sources))
            cut |= _loops_in(_from(sources, made, id(region)))
        cut |= _loops_in(keep_uncut(track, timeline, sources, song_end))
    _count(placed, cut)


def stop_at_the_end(song, placed=None):
    """Before bars go in after the end of the song: a recording looping until the next region (or the end of the song)
    that the song's end stopped keeps playing exactly what it played, its whole repeats and then, in a piece of its
    own, the part of the next one the end cut (as arrange._loops_stop_at_the_end does for looping regions). placed: as
    for after_insert."""
    timeline, end = song.timeline, song.song_end_tick()
    cut = set()
    for track in song.tracks:
        sources = {}
        for region, until in looping(track, timeline, end):
            if region.loops == 0 and until == end and region.tick < end:
                made = stop_at(track, timeline, region, frames_at(timeline, region, end))
                cut |= _loops_in(_from(sources, made, id(region)))
        if sources:
            cut |= _loops_in(keep_uncut(track, timeline, sources, end))
    _count(placed, cut)


def split_at(song, ticks, placed=None):
    """arrange.move_section, before anything moves: each looping recording whose playing goes on across one of `ticks`
    is cut there into pieces (as after_insert cuts one where bars go in), so the bars between them move as they are.
    (Until the sixth review of 26 Oct 2026 the moved section's bars were taken out and put back in front of the other
    one with only the loops of each step cut: a looping recording that the first step made play once, and whose first
    play still went on across where they went back in, played straight on through them, and its music there was gone
    from where those bars went.) placed: as for after_insert."""
    timeline, end = song.timeline, song.song_end_tick()
    cut = set()
    for track in song.tracks:
        sources = {}
        for region, until in looping(track, timeline, end):
            inside = sorted({int(t) for t in ticks if region.tick < t < until})
            if not inside:
                continue
            was, total = copy.deepcopy(region), frames_at(timeline, region, until)
            made = []
            for number, at in enumerate(inside):
                last = frames_at(timeline, was, inside[number + 1]) if number + 1 < len(inside) else total
                # (after the last of `ticks` its playing stays where it is and keeps the loop's setting, pieces();
                # pieces that move end exactly where it stopped, as a copy's do: copy_playing_in)
                made += place(track, timeline, was, pieces(was, frames_at(timeline, was, at), last,
                                                           carry_on=at == max(ticks)), at)
            _from(sources, made, id(region))
            made += stop_at(track, timeline, region, frames_at(timeline, region, inside[0]),
                            cut_there=_starts_at(track, inside[0], region, sources))
            cut |= _loops_in(_from(sources, made, id(region)))
        if sources:
            cut |= _loops_in(keep_uncut(track, timeline, sources, end))
    _count(placed, cut)


def copy_playing_in(song, t0, t1, regions, placed=None):
    """arrange.extract: what each looping recording that began before ticks t0 .. t1 plays in them, as pieces in the
    copy (regions: the copy's, {track id: [(tick from t0, recording)]}), from the same point in the recording, so the
    copy sounds like the bars it copies (until then it held nothing of such a loop). placed: as for after_insert."""
    timeline, end = song.timeline, song.song_end_tick()
    cut = set()
    for track in song.tracks:
        for region, until in looping(track, timeline, end):
            if not region.tick < t0 < until:
                continue
            found = pieces(region, frames_at(timeline, region, t0), frames_at(timeline, region, min(until, t1)),
                           carry_on=False)
            for tick, offset, length, loops in _laid_out(timeline, t0, found, region):
                piece = copy.deepcopy(region).to_todays_rules()     # (a new recording: today's rules)
                piece.offset, piece.length, piece.loops = offset, length, loops
                piece.loop_source = id(region)             # (for keep_uncut where the copy goes: after_insert)
                regions.setdefault(track.id, []).append((tick - t0, piece))
            if found:
                regions[track.id].sort(key=lambda item: item[0])
                cut.add(_recording(region))
    _count(placed, cut)


# ----------------------------------------------------------------------
# a newer recording over a looping recording's repeats (Session._finish_audio_recording)
# ----------------------------------------------------------------------
def before_new_recordings(track, timeline, song_end):
    """Before a take is placed on an audio track: its looping recordings, with where their playing stops, and the
    recordings it has (for after_new_recordings)."""
    return ([(region, copy.deepcopy(region), until) for region, until in looping(track, timeline, song_end)],
            {id(r) for r in track.regions}, song_end)


def after_new_recordings(track, timeline, before):
    """A take landed on a looping recording's repeats (after its first play, where it cuts the loop as the next
    recording): the loop plays as it did up to the take, and after the take carries on from the same point in the
    recording, up to where its playing stopped (0.9.11, as a looping region does: Session._place_take_region; until
    then the bars after the take went silent). A take inside a loop's first play plays over it, as it always did.
    Returns how many looping recordings this cut into pieces."""
    loops, known, song_end = before
    new = sorted((r for r in track.regions if id(r) not in known), key=lambda r: r.tick)
    cut = set()
    sources = {}
    for region, was, until in loops:
        first_end = was.end_tick(timeline)
        landing = [r for r in new if first_end <= r.tick < until]
        if not landing:
            continue
        made = []
        for number, take in enumerate(landing):
            begin = take.end_tick(timeline)
            stop = landing[number + 1].tick if number + 1 < len(landing) else until
            if stop > begin:
                made += place(track, timeline, was, pieces(was, frames_at(timeline, was, begin),
                                                           frames_at(timeline, was, stop), carry_on=stop == until),
                              begin)
        made += stop_at(track, timeline, region, frames_at(timeline, region, landing[0].tick), cut_there=True)
        cut |= _loops_in(_from(sources, made, id(region)))
    if sources:
        cut |= _loops_in(keep_uncut(track, timeline, sources, song_end))
    return len(cut)
