"""Keeping every bar where it is when a time signature changes (Russell, 10 Oct 2026: "if you're in 4/4 and the
section is eight bars, go to 3/4, the section changes to eleven bars. We don't want that").

Notes, regions, recordings, chord changes and automation points are stored in ticks, so a bar of 4/4 turned into 3/4
used to leave its last beat spilling into the next bar, and the song (and its last section) grew to hold everything.
Now each thing stays in its bar, at the same place inside the bar: bar 5 stays bar 5. When bars get shorter, what
was past their new end has no place: a note or a chord change there is left out (Control+Z brings it back), a region
or recording that started there starts at the end of the bar instead. Bars before the change are untouched (their
ticks do not move at all)."""


def _place(tick, old, new):
    """(new tick, whether it still fits its bar) for a tick of the old timeline."""
    bar = old.tick_to_bar(tick)
    inside = tick - old.bar_to_tick(bar)
    length = new.ticks_per_bar(bar)
    return new.bar_to_tick(bar) + min(inside, length), inside < length or inside == 0


def keep_bars(song, old):
    """Move everything in `song` (whose timeline has just changed from `old`) so it keeps its bar and its place in
    the bar. Returns how many notes had no place and were left out."""
    from . import players

    new = song.timeline
    lost = 0

    def place(tick):
        return _place(tick, old, new)

    for track in song.tracks:
        kept = []
        for note in track.notes:
            start, fits = place(note.tick)
            if not fits:
                lost += 1
                continue
            end, _ = place(note.tick + note.length)
            note.tick, note.length = start, max(1, end - start)
            kept.append(note)
        track.notes = kept
        regions = []
        for region in track.note_regions:
            start, _ = place(region.start)
            end, _ = place(region.end)
            if end > start:
                if region.player and start != region.start:      # (it keeps its feel: players.keep_feel)
                    region.player = players.keep_feel(region.player, region.start, start)
                region.start, region.end = start, end
                regions.append(region)
        track.note_regions = regions
        for region in track.regions:                     # recordings: where they start
            region.tick = place(region.tick)[0]
        for lane in track.automation or []:
            points = []
            for point in lane.get("points", []):
                tick, fits = place(point[0])
                if fits:
                    points.append([tick] + list(point[1:]))
            lane["points"] = points
    chords = []
    for change in song.chords:
        tick, fits = place(change.tick)
        if fits:
            change.tick = tick
            chords.append(change)
    song.chords = chords
    _loops_stop_at_the_end(song)
    return lost


def _loops_stop_at_the_end(song):
    """A looping region's repeats are counted in its own length, so in bars made shorter they can run past the song's
    end, and the song grew a bar to hold them (the fifth review of 25 Oct 2026: a 2-bar riff of 4/4 looped twice, with
    3/4 from bar 3, made a 4-bar section 5 bars long). Such a loop stops where the song ends instead, as a loop does at
    the end of the song (regions.stop_loop_at), so every section keeps its bars."""
    from . import arrangement, regions

    end = song.song_end_tick()
    for track in song.tracks:
        for region in [r for r in track.note_regions if r.loops > 1]:
            index = next(i for i, r in enumerate(track.note_regions) if r is region)
            if arrangement.note_region_repeats(track, index, end)[1] > end:
                regions.stop_loop_at(track, region, end, ends_there=True)
