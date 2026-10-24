"""Session features from version 0.9: automation (volume, pan and effect settings changing over
time). Mixed into session.Session; nothing here touches a window, so it is all tested headless.

Two ways to make automation:
- the automation lists (a track's lanes, each lane's points), where every point is placed and
  changed by number;
- Write automation (Control+Shift+W): while it is on and the song plays, moving a track's volume
  or pan, or an effect setting, writes points at the moment you hear. Everything written in one
  play-through is one undo step, and it replaces what the lane had between the first and the last
  point written.
"""

import logging

from . import automation as auto
from . import effects as fx

log = logging.getLogger("musicianforge.session")


class AutomationMixin:
    # ------------------------------------------------------------------
    # lanes
    # ------------------------------------------------------------------
    def _automation_track(self, track_id):
        track = self.song.track_by_id(track_id)
        if track is None:
            raise ValueError("Choose a track first")
        return track

    def lanes_of(self, track_id):
        track = self.song.track_by_id(track_id)
        return track.automation if track is not None else []

    def _lane(self, track_id, index):
        track = self._automation_track(track_id)
        if not 0 <= index < len(track.automation):
            raise ValueError("That automation lane is not there any more")
        return track, track.automation[index]

    def automation_targets(self, track_id):
        """[(target key, name, already has a lane)] for the Add lane window."""
        track = self._automation_track(track_id)
        have = {auto.target_key(lane) for lane in track.automation}
        return [(key, name, key in have) for key, name in auto.automatable_targets(track)]

    def describe_lane(self, track_id, index):
        track, lane = self._lane(track_id, index)
        return auto.describe_lane(track, lane)

    def lane_name(self, track_id, index):
        track, lane = self._lane(track_id, index)
        return auto.lane_name(track, lane)

    def add_lane(self, track_id, target):
        """A lane for target (volume, pan, or (effect, effect id, setting)). Returns its place; a lane
        that is already there is simply found."""
        track = self._automation_track(track_id)
        target = tuple(target)
        for index, lane in enumerate(track.automation):
            if auto.target_key(lane) == target:
                self.announce("{} already has a lane".format(auto.lane_name(track, lane)))
                return index
        if target not in [key for key, _name in auto.automatable_targets(track)]:
            raise ValueError("That cannot be automated")
        lane = auto.new_lane(*target)
        with self.edit("add automation lane"):
            self.song.track_by_id(track_id).automation.append(lane)
        index = len(self.lanes_of(track_id)) - 1
        # no "Enter lists its points" hint: the Points window opens straight away and the hint was lost under it
        # (screen reader audit B4, 23 Oct 2026)
        self.announce("Added a {} lane".format(self.lane_name(track_id, index)))
        return index

    def remove_lane(self, track_id, index):
        track, lane = self._lane(track_id, index)
        name = auto.lane_name(track, lane)
        with self.edit("remove automation lane"):
            del self.song.track_by_id(track_id).automation[index]
        self.announce("Removed the {} lane. The track's own setting is used again.".format(name))

    def set_lane_on(self, track_id, index, on=None):
        """Turn a lane on or off (None switches it); off uses the track's own setting, and keeps the points."""
        track, lane = self._lane(track_id, index)
        value = (not lane.get("on", True)) if on is None else bool(on)
        with self.edit("turn automation {}".format("on" if value else "off")):
            self.song.track_by_id(track_id).automation[index]["on"] = value
        self.announce(self.describe_lane(track_id, index))

    def _drop_lanes_for_effect(self, track, effect_id):
        track.automation = [lane for lane in track.automation
                            if not (lane["target"] == auto.EFFECT and lane.get("effect") == effect_id)]

    # ------------------------------------------------------------------
    # points
    # ------------------------------------------------------------------
    def describe_point(self, track_id, lane_index, point_index):
        track, lane = self._lane(track_id, lane_index)
        return auto.describe_point(track, lane, point_index, self.song.timeline)

    def lane_value_at(self, track_id, lane_index, tick):
        """The lane's value at a moment (its track's own setting when the lane has no points)."""
        track, lane = self._lane(track_id, lane_index)
        value = auto.value_at(lane["points"], tick)
        if value is None:
            value = self._own_value(track, lane)
        return auto.clamp_value(track, lane, value)

    def _own_value(self, track, lane):
        if lane["target"] == auto.VOLUME:
            return track.volume
        if lane["target"] == auto.PAN:
            return track.pan
        _index, effect = auto._effect_by_id(track, lane.get("effect"))
        return effect["params"].get(lane.get("param"), 0) if effect else 0

    def value_range(self, track_id, lane_index):
        track, lane = self._lane(track_id, lane_index)
        return auto.value_range(track, lane)

    def set_point(self, track_id, lane_index, bar, beat, value, glide=True, replacing=None):
        """Add a point (or change the one at `replacing`). Returns its place in the lane."""
        track, lane = self._lane(track_id, lane_index)
        tl = self.song.timeline
        if int(bar) < 1:
            # (a point before bar 1 was saved and then silently dropped when the project was opened again; the
            # review, 24 Oct 2026)
            raise ValueError("A point must be at bar 1 or later")
        beats = tl.time_signature_at_bar(int(bar)).numerator
        if not 1.0 <= float(beat) < beats + 1.0:
            raise ValueError("Bar {} has {} beats, so the beat must be from 1 to {}".format(bar, beats, beats))
        tick = tl.position_to_tick(int(bar), float(beat))
        low, high, _decimals, _unit = auto.value_range(track, lane)
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise ValueError("The value must be a number") from None
        if not low <= number <= high:
            raise ValueError("The value must be from {} to {}".format(fx.format_value(low), fx.format_value(high)))
        value = auto.clamp_value(track, lane, number)
        if replacing is None and len(lane["points"]) >= auto.MAX_POINTS:
            raise ValueError("A lane can have up to {} points".format(auto.MAX_POINTS))
        with self.edit("automation point"):
            target = self.song.track_by_id(track_id).automation[lane_index]
            points = [p for i, p in enumerate(target["points"]) if i != replacing]
            target["points"] = auto.sort_points(points + [[tick, value, bool(glide)]])
        index = next(i for i, p in enumerate(self.lanes_of(track_id)[lane_index]["points"]) if p[0] == tick)
        self.announce(self.describe_point(track_id, lane_index, index))
        return index

    def remove_point(self, track_id, lane_index, point_index):
        track, lane = self._lane(track_id, lane_index)
        if not 0 <= point_index < len(lane["points"]):
            raise ValueError("That point is not there any more")
        with self.edit("remove automation point"):
            del self.song.track_by_id(track_id).automation[lane_index]["points"][point_index]
        left = len(self.lanes_of(track_id)[lane_index]["points"])
        self.announce("Point removed. {} left".format(self._count_words(left, "point")))

    def clear_points(self, track_id, lane_index, start_bar, end_bar):
        """Remove the points in bars start_bar .. end_bar - 1. Returns how many."""
        track, lane = self._lane(track_id, lane_index)
        tl = self.song.timeline
        t0, t1 = tl.bar_to_tick(max(1, int(start_bar))), tl.bar_to_tick(max(int(start_bar) + 1, int(end_bar)))
        removed = sum(1 for p in lane["points"] if t0 <= p[0] < t1)
        with self.edit("clear automation"):
            target = self.song.track_by_id(track_id).automation[lane_index]
            target["points"] = [p for p in target["points"] if not t0 <= p[0] < t1]
        self.announce("Removed {}".format(self._count_words(removed, "point")))
        return removed

    def play_from_point(self, track_id, lane_index, point_index):
        _track, lane = self._lane(track_id, lane_index)
        if not 0 <= point_index < len(lane["points"]):
            raise ValueError("That point is not there any more")
        tick = lane["points"][point_index][0]
        if self.engine.playing:
            self.stop(speak=False)
        self.locate(tick, speak=False)
        self.toggle_play()

    # ------------------------------------------------------------------
    # writing automation by moving a setting while the song plays
    # ------------------------------------------------------------------
    def toggle_automation_write(self):
        self.automation_write = not getattr(self, "automation_write", False)
        if self.automation_write:
            self.announce_state("Write automation on", "While the song plays, changing a track's volume or pan, or "
                                "an effect setting, writes it into that track's automation.")
        else:
            self.announce_state("Write automation off")
        self.notify("transport")
        return self.automation_write

    def _writing(self):
        return bool(getattr(self, "automation_write", False)) and self.engine.playing

    def new_write_pass(self):
        """Called when playing or recording starts: a new play-through is a new undo step."""
        self._write_pass = {}
        self._merge_label = None

    def _continues_pass(self, last, tick):
        """True if the song has played straight on from the last point written (no jump with the
        period key, no section loop back to its start): only then is what lies between replaced."""
        if last is None:
            return False
        last_tick, last_clock = last
        tl = self.song.timeline
        elapsed = (self.engine._clock - last_clock) / float(self.engine.sample_rate)   # the audio's own clock
        expected = tl.seconds_to_tick(tl.tick_to_seconds(last_tick) + elapsed)
        return last_tick < tick and abs(tick - expected) <= tl.ticks_per_beat(tl.tick_to_bar(tick))

    def write_automation(self, track_id, target, value, speak=True):
        """Write one value into a lane at the moment being heard (creating the lane if needed).
        The value holds until the next point, exactly as it was heard while writing."""
        track = self._automation_track(track_id)
        target = tuple(target)
        tick = int(round(self.position_tick()))
        lane_index = next((i for i, lane in enumerate(track.automation) if auto.target_key(lane) == target), None)
        if lane_index is not None and len(track.automation[lane_index]["points"]) >= auto.MAX_POINTS:
            self.announce("This lane already has {} points, the most it can hold".format(auto.MAX_POINTS))
            return value
        lanes_pass = self.__dict__.setdefault("_write_pass", {})
        key = (track_id,) + target
        last = lanes_pass.get(key)
        continuing = self._continues_pass(last, tick)
        with self.edit("write automation", merge=True):
            target_track = self.song.track_by_id(track_id)
            if lane_index is None:
                target_track.automation.append(auto.new_lane(*target))
                lane = target_track.automation[-1]
            else:
                lane = target_track.automation[lane_index]
            lane["on"] = True
            value = auto.clamp_value(target_track, lane, value)
            points = lane["points"]
            if continuing:
                # replace what was there since the last point written in this play-through
                points = [p for p in points if not last[0] < p[0] <= tick]
            else:
                points = [p for p in points if p[0] != tick]
            lane["points"] = auto.sort_points(points + [[tick, value, False]])
        lanes_pass[key] = (tick, self.engine._clock)
        if speak:
            self.announce(auto.spoken_value(self.song.track_by_id(track_id), lane, value).capitalize())
        return value
