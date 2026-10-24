"""What a track actually plays: its notes, with looped regions repeated and rhythm player
regions performed. Used for playback, WAV and M4A export, MIDI export, and for what another
rhythm player follows.

A region plays `loops` times in a row (1 means once). Loops set to 0 means "until the next
region": it repeats until the next region on the track starts, or the song ends. A repeat never
runs into the next region: whatever would land there is left out.

A looping rhythm player region (0.9.8; Russell, 24 Oct 2026) leads back into its own first chord
at the end of every repeat but the last, which leads into the chord where its playing stops:
performance_for(track, region, lead_into=tick) gives those two versions (the same notes, for a
player that does not lead into chords).
"""

import math

from .song import Note


def note_region_repeats(track, index, song_end):
    """How many times a region on an instrument track plays, and the tick where its playing stops."""
    region = track.note_regions[index]
    following = [r.start for r in track.note_regions if r.start >= region.end]
    limit = min(following) if following else None
    length = max(1, region.length)
    if region.loops == 0:
        until = limit if limit is not None else max(song_end, region.end)
        return max(1, int(math.ceil((until - region.start) / float(length)))), until
    stop = region.start + max(1, region.loops) * length
    return max(1, region.loops), (min(stop, limit) if limit is not None else stop)


def audio_region_repeats(track, index, timeline, song_end):
    """How many times a recording plays, and the tick where its playing stops."""
    region = track.regions[index]
    once_end = region.end_tick(timeline)
    following = [r.tick for r in track.regions if r.tick >= once_end and r is not region]
    limit = min(following) if following else None
    start_seconds = timeline.tick_to_seconds(region.tick)
    seconds = max(1e-6, timeline.tick_to_seconds(once_end) - start_seconds)
    if region.loops == 0:
        until = limit if limit is not None else max(song_end, once_end)
        count = max(1, int(math.ceil((timeline.tick_to_seconds(until) - start_seconds) / seconds - 1e-9)))
        return count, until
    count = max(1, region.loops)
    stop = int(round(timeline.seconds_to_tick(start_seconds + count * seconds)))
    return count, (min(stop, limit) if limit is not None else stop)


def sounding_notes(song, track, performance_for):
    """Every note an instrument track plays, in order.

    performance_for(track, region) returns a rhythm player region's notes. Muted regions are left
    out; looped regions are repeated."""
    if track.is_audio:
        return []
    song_end = song.song_end_tick()
    notes = []
    for index, region in enumerate(track.note_regions):
        if region.mute:
            continue
        own = [n for n in track.notes if region.start <= n.tick < region.end]
        inside = own
        count, stop = note_region_repeats(track, index, song_end)
        looping = None
        if region.player:
            inside = sorted(own + list(performance_for(track, region) if count == 1 else
                                       performance_for(track, region, lead_into=stop)),
                            key=lambda n: (n.tick, n.pitch))
            if count > 1:
                looping = sorted(own + list(performance_for(track, region, lead_into=region.start)),
                                 key=lambda n: (n.tick, n.pitch))
        for k in range(count):
            shift = k * region.length
            for note in (looping if looping is not None and k < count - 1 else inside):
                tick = note.tick + shift
                if tick >= stop:
                    break
                if k == 0:
                    notes.append(note)
                else:
                    notes.append(Note(tick, note.length, note.pitch, note.velocity))
    covered = [(r.start, r.end) for r in track.note_regions]
    notes += [n for n in track.notes if not any(a <= n.tick < b for a, b in covered)]
    notes.sort(key=lambda n: (n.tick, n.pitch))
    return notes


def loop_text(count, stop, timeline, loops_setting):
    """'loops 4 times, to bar 33', 'loops until the next region, to bar 25', or ''."""
    if loops_setting == 1:
        return ""
    bar = timeline.tick_to_bar(max(0, stop - 1)) + 1
    if loops_setting == 0:
        return "loops until the next region, {} time{}, to bar {}".format(count, "" if count == 1 else "s", bar)
    return "loops {} time{}, to bar {}".format(count, "" if count == 1 else "s", bar)
