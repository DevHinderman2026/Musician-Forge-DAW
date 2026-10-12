"""Nudging regions and trimming their edges from the keyboard (0.9.4; Russell, 9 Oct 2026: "how do you actually
trim and nudge your regions?"). Mixed into session.Session; nothing here touches a window.

Until 0.9.4 a region could only be moved by typing a bar and beat (Move region) and trimmed by typing its start and
end (Region settings). Now, in the Regions list, one key moves a region, or one of its edges, by the nudge step:
a bar, a quarter note, an eighth note or a sixteenth note. That is how a rhythm player's region is made longer: its end
moves later and the player fills the new length.

Rules, the same for every kind of region:
- A region never moves or grows over another one: the key says what is in the way and changes nothing (Move region
  and Paste, which replace what is there, are still there for that).
- Nothing moves before the start of the song, and a region keeps at least one tick.
- On an instrument track, the notes move with their region. Trimming an edge inwards removes the notes left
  outside (said in words; Control+Z brings them back). A rhythm player simply fills the new length.
- A recording's edges stop where the recording itself begins and ends.
- A run of presses of the same key on the same track is one undo step.
"""

from .song import AUDIO_RATE
from .timeline import PPQ

NUDGE_STEPS = ("bar", "quarter", "eighth", "sixteenth")
NUDGE_NAMES = {"bar": "1 bar", "quarter": "a quarter note", "eighth": "an eighth note",
               "sixteenth": "a sixteenth note"}
NOTE_TICKS = {"quarter": PPQ, "eighth": PPQ // 2, "sixteenth": PPQ // 4}
DEFAULT_NUDGE_STEP = "quarter"


class NudgeMixin:
    # ------------------------------------------------------------------
    # the step
    # ------------------------------------------------------------------
    @property
    def nudge_step(self):
        step = self.settings["nudge_step"] if self.settings is not None else getattr(self, "_nudge_step", None)
        return step if step in NUDGE_STEPS else DEFAULT_NUDGE_STEP

    def set_nudge_step(self, step):
        if step not in NUDGE_STEPS:
            raise ValueError("The nudge step can be {}".format(", ".join(NUDGE_NAMES[s] for s in NUDGE_STEPS)))
        if self.settings is not None:
            self.settings["nudge_step"] = step
            self.settings.save()
        else:
            self._nudge_step = step

    def cycle_nudge_step(self, direction=1):
        """N in the Regions list: the next step (Shift+N the one before), said in words."""
        steps = NUDGE_STEPS
        step = steps[(steps.index(self.nudge_step) + (1 if direction >= 0 else -1)) % len(steps)]
        self.set_nudge_step(step)
        self.announce("Nudge step: {}".format(NUDGE_NAMES[step]))
        return step

    def nudged_tick(self, tick, direction, step=None):
        """Where `tick` lands one nudge step later (direction 1) or earlier (-1). A bar keeps the place in the bar
        (bars can differ in length). The note values are the same length everywhere, whatever the time signature,
        so a nudge later and a nudge earlier always cancel out."""
        tl = self.song.timeline
        step = step or self.nudge_step
        tick = int(tick)
        if step == "bar":
            bar = tl.tick_to_bar(tick)
            offset = tick - tl.bar_to_tick(bar)
            target = bar + (1 if direction > 0 else -1)
            return tl.bar_to_tick(target) + min(offset, tl.ticks_per_bar(target) - 1)
        return tick + (NOTE_TICKS[step] if direction > 0 else -NOTE_TICKS[step])

    # ------------------------------------------------------------------
    # moving
    # ------------------------------------------------------------------
    def nudge_regions(self, track_id, indices, direction):
        """Move regions one nudge step later or earlier, keeping their spacing. Returns the new index of the first."""
        self._need_regions(track_id, indices)
        indices = sorted(set(indices))
        spans = [self.region_span(track_id, i) for i in indices]
        first = min(start for start, _end in spans)
        delta = self.nudged_tick(first, direction) - first
        if first + delta < 0:
            raise ValueError("The region is at the start of the song")
        self._check_room(track_id, indices, [(s + delta, e + delta) for s, e in spans])
        key = (track_id, "move")
        with self.edit("nudge regions" if len(indices) > 1 else "nudge region", merge=True, merge_key=key):
            target = self.song.track_by_id(track_id)
            chosen = [self.regions_of(track_id)[i] for i in indices]   # the same regions, in the edited song
            if target.is_audio:
                for region in chosen:
                    region.tick += delta
                target.sort_regions()
            else:
                owned = [n for n in target.notes if any(r.start <= n.tick < r.end for r in chosen)]
                for note in owned:
                    note.tick += delta
                for region in chosen:
                    region.start += delta
                    region.end += delta
                target.sort_notes()
                target.note_regions.sort(key=lambda r: r.start)
            new_first = self.regions_of(track_id).index(chosen[0])
        # the selection stays: nothing passes another region, so every region keeps its place in the list
        self.announce("{}{}".format("" if len(indices) == 1 else "{} regions: ".format(len(indices)),
                                    self.song.timeline.spoken_bar_position(first + delta).capitalize()))
        return new_first

    # ------------------------------------------------------------------
    # trimming an edge
    # ------------------------------------------------------------------
    def nudge_region_edge(self, track_id, index, edge, direction):
        """Move a region's start or end ("start" or "end") one nudge step later or earlier. Moving the end later
        makes it longer: the way to lengthen a rhythm player's region. Returns the region's new index."""
        track = self._need_regions(track_id, [index])
        start, end = self.region_span(track_id, index)
        tl = self.song.timeline
        if edge == "start":
            start = self.nudged_tick(start, direction)
            if start < 0:
                raise ValueError("The region starts at the start of the song")
        elif edge == "end":
            end = self.nudged_tick(end, direction)
        else:
            raise ValueError("A region has a start and an end")
        if end <= start:
            raise ValueError("The region is as short as the nudge step allows. Choose a smaller step with N.")
        self._check_room(track_id, [index], [(start, end)])
        removed = 0
        if track.is_audio:
            region = track.regions[index]
            begins = tl.seconds_to_tick(tl.tick_to_seconds(region.tick) - region.offset / float(AUDIO_RATE))
            ends = tl.seconds_to_tick(tl.tick_to_seconds(region.tick) +
                                      (region.take.frames - region.offset) / float(AUDIO_RATE))
            if start < int(round(begins)) - 1:
                raise ValueError("The recording begins at {}".format(tl.spoken_bar_position(int(round(begins)))))
            if end > int(round(ends)) + 1:
                raise ValueError("The recording ends at {}".format(tl.spoken_bar_position(int(round(ends)))))
        else:
            old_start, old_end = track.note_regions[index].start, track.note_regions[index].end
            if not track.note_regions[index].player:
                removed = sum(1 for n in track.notes if old_start <= n.tick < old_end and not start <= n.tick < end)
        new_index = self.trim_region(track_id, index, start, end, speak=False, merge_key=(track_id, edge))
        new_start, new_end = self.region_span(track_id, new_index)
        bars, beats = tl.bars_and_beats(new_start, new_end)
        length = []
        if bars:
            length.append("{} bar{}".format(bars, "" if bars == 1 else "s"))
        if beats or not bars:
            length.append("{:g} beat{}".format(beats, "" if beats == 1 else "s"))
        place = tl.spoken_bar_position(new_start if edge == "start" else new_end)
        text = "{} at {}, {} long".format("Starts" if edge == "start" else "Ends", place, " and ".join(length))
        if removed:
            text += ". {} note{} outside it removed; Control+Z brings {} back".format(
                removed, "" if removed == 1 else "s", "it" if removed == 1 else "them")
        self.announce(text)
        return new_index

    # ------------------------------------------------------------------
    def _check_room(self, track_id, indices, new_spans):
        """ValueError, in words, when a region would move or grow over another one or before the song starts."""
        if any(start < 0 for start, _end in new_spans):
            raise ValueError("The region is at the start of the song")
        others = [i for i in range(len(self.regions_of(track_id))) if i not in indices]
        for i in others:
            o_start, o_end = self.region_span(track_id, i)
            for start, end in new_spans:
                if start < o_end and end > o_start:
                    raise ValueError("{} is in the way ({}). Move or shorten it first.".format(
                        self.region_name(track_id, i),
                        self.song.timeline.describe_span(o_start, o_end)))
