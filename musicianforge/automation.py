"""Automation: a track's volume, pan and effect settings changing over time.

A track can have one lane for each thing that changes: its volume, its pan, or one setting of one
of its effects (for example the reverb's mix). A lane is a list of points; each point has a place
in the song (in ticks), a value, and whether the value glides to the next point (a straight line)
or holds until it (a step). Once a lane has points it sets that value for the whole song: before
its first point the first point's value, after its last point the last point's value. A lane can
be turned off, and then the track's own setting is used again.

Lanes are stored on the track (Track.automation) as plain lists so they save in the project:
    {"target": "volume" | "pan" | "effect", "effect": effect id or None, "param": setting key or None,
     "on": True, "points": [[tick, value, glide], ...]}
Effects are named by their id (effects keep an id that never changes, see effects.ensure_ids), so a
lane keeps its effect when effects are moved up or down the list.

Player is built for the engine from a song (see engine.PlaybackData): it answers "what is this
track's volume and pan at this moment" and puts automated effect settings into the track's effect
chain, a block at a time.
"""

import bisect

from . import effects as fx

VOLUME, PAN, EFFECT = "volume", "pan", "effect"
MAX_POINTS = 5000            # per lane


# ----------------------------------------------------------------------
# what a lane changes
# ----------------------------------------------------------------------
def target_key(lane):
    return (lane["target"], lane.get("effect"), lane.get("param"))


def new_lane(target, effect_id=None, param=None):
    return {"target": target, "effect": effect_id if target == EFFECT else None,
            "param": param if target == EFFECT else None, "on": True, "points": []}


def _effect_by_id(track, effect_id):
    for index, effect in enumerate(track.effects):
        if effect.get("id") == effect_id:
            return index, effect
    return None, None


def param_of(track, lane):
    """The effects.Param an effect lane changes, or None (a volume or pan lane, or a lost effect)."""
    if lane["target"] != EFFECT:
        return None
    _index, effect = _effect_by_id(track, lane.get("effect"))
    if effect is None:
        return None
    for p in fx.TYPE_BY_KEY[effect["type"]].params:
        if p.key == lane.get("param"):
            return p
    return None


def value_range(track, lane):
    """(lowest, highest, decimals, unit word) of a lane's values."""
    if lane["target"] == VOLUME:
        return 0, 100, 0, "percent"
    if lane["target"] == PAN:
        return -100, 100, 0, ""
    p = param_of(track, lane)
    if p is None:
        return 0, 100, 0, ""
    if p.kind == "percent":
        return 0, 100, 0, "percent"
    return p.low, p.high, p.decimals, p.unit


def clamp_value(track, lane, value):
    low, high, decimals, _unit = value_range(track, lane)
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise ValueError("The value must be a number") from None
    value = min(high, max(low, value))
    return int(round(value)) if decimals == 0 else round(value, decimals)


def lane_name(track, lane):
    """'Volume', 'Pan', or 'Reverb 2: Mix (how much reverb)'."""
    if lane["target"] == VOLUME:
        return "Volume"
    if lane["target"] == PAN:
        return "Pan"
    index, effect = _effect_by_id(track, lane.get("effect"))
    p = param_of(track, lane)
    if effect is None or p is None:
        return "An effect that was removed"
    return "{} {}: {}".format(fx.TYPE_BY_KEY[effect["type"]].name, index + 1, p.label)


def spoken_value(track, lane, value):
    if lane["target"] == VOLUME:
        return "volume {}".format(fx.format_value(value))
    if lane["target"] == PAN:
        value = int(round(value))
        return "pan center" if value == 0 else "pan {} percent {}".format(abs(value), "left" if value < 0 else "right")
    p = param_of(track, lane)
    return p.spoken(value) if p is not None else fx.format_value(value)


def automatable_targets(track):
    """Everything on a track that can have a lane: [(target key, name)]."""
    found = [((VOLUME, None, None), "Volume"), ((PAN, None, None), "Pan")]
    for index, effect in enumerate(track.effects):
        kind = fx.TYPE_BY_KEY[effect["type"]]
        if effect["type"] not in fx.PROCESSORS:
            continue          # pitch correction is worked out for whole recordings, so it cannot change over time
        for p in kind.params:
            if p.automatable:
                found.append(((EFFECT, effect.get("id"), p.key), "{} {}: {}".format(kind.name, index + 1, p.label)))
    return found


# ----------------------------------------------------------------------
# reading a lane
# ----------------------------------------------------------------------
def value_at(points, tick):
    """A lane's value at `tick` (points sorted by tick; None if there are none)."""
    if not points:
        return None
    ticks = [p[0] for p in points]
    i = bisect.bisect_right(ticks, tick) - 1
    if i < 0:
        return points[0][1]
    t0, v0, glide = points[i][0], points[i][1], points[i][2] if len(points[i]) > 2 else True
    if i + 1 >= len(points) or not glide:
        return v0
    t1, v1 = points[i + 1][0], points[i + 1][1]
    if t1 <= t0:
        return v1
    return v0 + (v1 - v0) * (tick - t0) / float(t1 - t0)


def describe_point(track, lane, index, timeline):
    """'Bar 5, beat 1: volume 80, glides to 60 by bar 7, beat 1.'"""
    points = lane["points"]
    tick, value, glide = points[index][0], points[index][1], points[index][2]
    text = "{}: {}".format(timeline.describe_position(tick), spoken_value(track, lane, value))
    if index + 1 >= len(points):
        return text + ", stays there to the end"
    following = points[index + 1]
    if glide and following[1] != value:
        return text + ", glides to {} by {}".format(spoken_value(track, lane, following[1]),
                                                     timeline.describe_position(following[0]).lower())
    return text + ", holds until the next point"


def describe_lane(track, lane):
    """'Volume: 4 points, on' (the lane list)."""
    count = len(lane["points"])
    text = "{}: {} point{}".format(lane_name(track, lane), count, "" if count == 1 else "s")
    if not count:
        text += " (no effect until it has a point)"
    return text + (", on" if lane.get("on", True) else ", off (the track's own setting is used)")


def clean_lanes(raw, track):
    """Valid lanes from a project file: unknown targets, lost effects and bad points are dropped."""
    lanes, seen = [], set()
    for item in raw or []:
        if not isinstance(item, dict) or item.get("target") not in (VOLUME, PAN, EFFECT):
            continue
        lane = new_lane(item["target"], item.get("effect"), item.get("param"))
        lane["on"] = bool(item.get("on", True))
        if lane["target"] == EFFECT and param_of(track, lane) is None:
            continue
        key = target_key(lane)
        if key in seen:
            continue
        points = []
        for p in item.get("points", [])[:MAX_POINTS]:
            try:
                tick = int(p[0])
                value = clamp_value(track, lane, p[1])
            except (TypeError, ValueError, IndexError):
                continue
            if tick >= 0:
                points.append([tick, value, bool(p[2]) if len(p) > 2 else True])
        lane["points"] = sort_points(points)
        seen.add(key)
        lanes.append(lane)
    return lanes


def sort_points(points):
    """In time order, one point per tick (a later entry for the same tick wins)."""
    by_tick = {}
    for p in points:
        by_tick[int(p[0])] = [int(p[0]), p[1], bool(p[2])]
    return [by_tick[t] for t in sorted(by_tick)]


# ----------------------------------------------------------------------
# the engine's side
# ----------------------------------------------------------------------
# An effect whose setting glides is updated at most this often (some effects, such as the EQ, take
# most of a millisecond to change; every 40 ticks is about 20 ms at 120 beats a minute).
MIN_UPDATE_TICKS = 40


class _Lane:
    __slots__ = ("ticks", "values", "glides", "decimals", "key", "applied_tick", "applied_value")

    def __init__(self, points, decimals=0, key=None):
        self.ticks = [p[0] for p in points]
        self.values = [float(p[1]) for p in points]
        self.glides = [bool(p[2]) for p in points]
        self.decimals = decimals
        self.key = key
        self.applied_tick = None      # the audio thread's own bookkeeping (see Player.apply_effects)
        self.applied_value = None

    def at(self, tick):
        i = bisect.bisect_right(self.ticks, tick) - 1
        if i < 0:
            return self.values[0]
        if i + 1 >= len(self.ticks) or not self.glides[i]:
            return self.values[i]
        t0, t1 = self.ticks[i], self.ticks[i + 1]
        if t1 <= t0:
            return self.values[i + 1]
        return self.values[i] + (self.values[i + 1] - self.values[i]) * (tick - t0) / float(t1 - t0)


class Player:
    """What automation does while the song plays. Read-only once built (the engine swaps in a new
    one with each new PlaybackData)."""

    def __init__(self, song, effects_by_track=None):
        self.mix = {}                # track id -> (volume lane or None, pan lane or None)
        self.effect_lanes = {}       # track id -> [(chain index, _Lane)]
        for track in song.tracks:
            lanes = [lane for lane in getattr(track, "automation", []) if lane.get("on", True) and lane["points"]]
            if not lanes:
                continue
            volume = pan = None
            chain_effects = (effects_by_track or {}).get(track.id, track.effects)
            running = [e for e in chain_effects if e.get("on", True) and e["type"] in fx.PROCESSORS]
            positions = {e.get("id"): i for i, e in enumerate(running)}
            for lane in lanes:
                if lane["target"] == VOLUME:
                    volume = _Lane(lane["points"])
                elif lane["target"] == PAN:
                    pan = _Lane(lane["points"])
                else:
                    p = param_of(track, lane)
                    index = positions.get(lane.get("effect"))
                    if p is None or index is None:
                        continue      # the effect is off (or gone): its own settings apply
                    decimals = 0 if p.kind == "percent" else p.decimals
                    self.effect_lanes.setdefault(track.id, []).append((index, _Lane(lane["points"], decimals, p.key)))
            if volume is not None or pan is not None:
                self.mix[track.id] = (volume, pan)

    @property
    def empty(self):
        return not self.mix and not self.effect_lanes

    def mix_at(self, track_id, tick, volume, pan):
        """The track's volume and pan at `tick` (its own settings where it has no lane)."""
        lanes = self.mix.get(track_id)
        if lanes is None:
            return volume, pan
        if lanes[0] is not None:
            volume = lanes[0].at(tick)
        if lanes[1] is not None:
            pan = lanes[1].at(tick)
        return volume, pan

    def apply_effects(self, track_id, chain, tick):
        """Put the automated settings at `tick` into the track's effect chain (rounded to each
        setting's own precision, so a glide changes an effect only as often as it can be heard)."""
        for index, lane in self.effect_lanes.get(track_id, ()):
            value = lane.at(tick)
            value = int(round(value)) if lane.decimals == 0 else round(value, lane.decimals)
            if value == lane.applied_value:
                continue
            last = lane.applied_tick
            gliding = last is not None and 0 <= tick - last < MIN_UPDATE_TICKS and value not in lane.values
            if gliding and chain.has_param(index, lane.key, lane.applied_value):
                continue              # along a glide: the next small step comes a moment later
            chain.set_param(index, lane.key, value)
            lane.applied_tick, lane.applied_value = tick, value


def has_automation(song):
    return any(lane["points"] for track in song.tracks for lane in getattr(track, "automation", []))
