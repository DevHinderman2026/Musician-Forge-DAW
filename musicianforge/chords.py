"""The chord track: which chord is playing at every point of the song.

Rhythm players (Bellows, Ember, Spark and Hammer) take their notes from it. A chord change
starts at a tick and lasts until the next one. Each change is a root (pitch class 0 to 11), a
quality ("major", "minor7" and so on) and, optionally, a different bass note ("C major with E in
the bass").

The chord track can be filled three ways: one change at a time, from a progression (pop, ballad,
blues and so on, built from the song's key at each bar), or from a track's notes (Musician Forge
works out the chord in each bar, half bar or beat from the notes played there: handy after
recording with the chord strips).
"""

from dataclasses import dataclass

from . import theory

# (key, spoken quality, short symbol, intervals above the root)
QUALITIES = [
    ("major", "major", "", (0, 4, 7)),
    ("minor", "minor", "m", (0, 3, 7)),
    ("7", "seven", "7", (0, 4, 7, 10)),
    ("maj7", "major seven", "maj7", (0, 4, 7, 11)),
    ("m7", "minor seven", "m7", (0, 3, 7, 10)),
    ("sus2", "suspended second", "sus2", (0, 2, 7)),
    ("sus4", "suspended fourth", "sus4", (0, 5, 7)),
    ("dim", "diminished", "dim", (0, 3, 6)),
    ("m7b5", "half diminished", "m7b5", (0, 3, 6, 10)),
    ("dim7", "diminished seven", "dim7", (0, 3, 6, 9)),
    ("aug", "augmented", "aug", (0, 4, 8)),
    ("6", "six", "6", (0, 4, 7, 9)),
    ("m6", "minor six", "m6", (0, 3, 7, 9)),
    ("add9", "add nine", "add9", (0, 4, 7, 14)),
    ("5", "power chord (root and fifth)", "5", (0, 7)),
]
QUALITY_KEYS = [q[0] for q in QUALITIES]
_BY_KEY = {q[0]: q for q in QUALITIES}
_BY_INTERVALS = {q[3]: q[0] for q in QUALITIES}


@dataclass
class ChordChange:
    tick: int
    root: int               # pitch class, 0 = C
    quality: str = "major"
    bass: int = None        # pitch class of a different bass note, or None

    def intervals(self):
        return _BY_KEY.get(self.quality, _BY_KEY["major"])[3]

    def pitch_classes(self):
        classes = {(self.root + i) % 12 for i in self.intervals()}
        if self.bass is not None:
            classes.add(self.bass % 12)
        return classes

    def bass_class(self):
        return self.root if self.bass is None else self.bass % 12

    def to_list(self):
        return [self.tick, self.root, self.quality, self.bass]

    @classmethod
    def from_list(cls, raw):
        tick, root = int(raw[0]), int(raw[1]) % 12
        quality = str(raw[2]) if len(raw) > 2 and str(raw[2]) in _BY_KEY else "major"
        bass = int(raw[3]) % 12 if len(raw) > 3 and raw[3] is not None else None
        if tick < 0:
            raise ValueError("a chord change cannot start before the song")
        return cls(tick, root, quality, bass)


def quality_of(intervals):
    return _BY_INTERVALS.get(tuple(intervals), "major")


def spoken_quality(quality):
    return _BY_KEY.get(quality, _BY_KEY["major"])[1]


def name(change, flats=False):
    """'A minor', 'C major with E in the bass', 'B flat seven'."""
    names = theory.SPOKEN_FLAT if flats else theory.SPOKEN_SHARP
    text = "{} {}".format(names[change.root], spoken_quality(change.quality))
    if change.bass is not None and change.bass % 12 != change.root:
        text += " with {} in the bass".format(names[change.bass % 12])
    return text


def short_name(change, flats=False):
    names = theory.FLAT_NAMES if flats else theory.SHARP_NAMES
    text = names[change.root] + _BY_KEY.get(change.quality, _BY_KEY["major"])[2]
    if change.bass is not None and change.bass % 12 != change.root:
        text += "/" + names[change.bass % 12]
    return text


def sort(changes):
    """In time order, one change per tick (a later entry for the same tick wins)."""
    by_tick = {}
    for change in changes:
        by_tick[int(change.tick)] = change
    return [by_tick[t] for t in sorted(by_tick)]


def chord_at(changes, tick):
    """The chord change in effect at `tick`, or None before the first one."""
    found = None
    for change in changes:
        if change.tick <= tick:
            found = change
        else:
            break
    return found


def spans(changes, start, end, timeline=None):
    """[(from tick, to tick, change)] covering start..end. Before the first change (or with no chord
    track at all) the key's own chord (I or i) of that bar is used, so players always have a chord."""
    result = []
    current = chord_at(changes, start)
    position = start
    upcoming = [c for c in changes if start < c.tick < end]
    for change in upcoming + [None]:
        stop = change.tick if change is not None else end
        if stop > position:
            if current is None and timeline is not None:
                result.extend(_key_chords(timeline, position, stop))
            elif current is not None:
                result.append((position, stop, current))
        if change is not None:
            current = change
            position = change.tick
    return result


def _key_chords(timeline, start, end):
    """The tonic chord of the key in each bar (used where the chord track is empty)."""
    result = []
    position = start
    while position < end:
        bar = timeline.tick_to_bar(position)
        stop = min(end, timeline.bar_to_tick(bar + 1))
        key = timeline.key_at_bar(bar)
        tonic = theory.diatonic_chords(key.tonic, key.scale)[0]
        result.append((position, stop, ChordChange(position, tonic.root, quality_of(tonic.intervals))))
        position = stop
    return result


# ----------------------------------------------------------------------
# progressions, built from the key at each bar
# ----------------------------------------------------------------------
# (name, degrees: 1 to 7 of the key, or "b7" style borrowed chords as (semitones, quality))
PROGRESSIONS = [
    ("Pop: one, five, six, four (I V vi IV)", [1, 5, 6, 4]),
    ("Ballad: six, four, one, five (vi IV I V)", [6, 4, 1, 5]),
    ("Fifties: one, six, four, five (I vi IV V)", [1, 6, 4, 5]),
    ("Rock: one, four, five, four (I IV V IV)", [1, 4, 5, 4]),
    ("Minor epic: one, six, three, seven (i VI III VII)", [1, 6, 3, 7]),
    ("Dark minor: one, six, seven, one (i VI VII i)", [1, 6, 7, 1]),
    ("Twelve-bar blues (I I I I IV IV I I V IV I V)", [1, 1, 1, 1, 4, 4, 1, 1, 5, 4, 1, 5]),
    ("Jazz two, five, one (ii V I I)", [2, 5, 1, 1]),
    ("One chord: the key's own chord", [1]),
]


def progression_chords(timeline, start_bar, end_bar, degrees, bars_per_chord=1, sevenths=False):
    """Chord changes for bars start_bar .. end_bar - 1 following a progression of scale degrees."""
    changes = []
    index = 0
    bar = start_bar
    while bar < end_bar:
        key = timeline.key_at_bar(bar)
        chord = theory.diatonic_chords(key.tonic, key.scale)[(degrees[index % len(degrees)] - 1) % 7]
        quality = quality_of(chord.intervals)
        if sevenths and quality in ("major", "minor", "dim"):
            third = chord.intervals[1]
            scale_pcs = theory.scale_pitch_classes(key.tonic, theory.chord_scale(key.scale))
            seventh_major = (chord.root + 11) % 12 in scale_pcs
            if quality == "major":
                quality = "maj7" if seventh_major else "7"
            elif quality == "minor":
                quality = "m7"
            elif third == 3:
                quality = "m7b5"
        changes.append(ChordChange(timeline.bar_to_tick(bar), chord.root, quality))
        bar += bars_per_chord
        index += 1
    return changes


# ----------------------------------------------------------------------
# working out chords from notes
# ----------------------------------------------------------------------
_TEMPLATES = [(q[0], q[3]) for q in QUALITIES if q[0] in ("major", "minor", "7", "maj7", "m7", "dim", "sus4",
                                                          "sus2", "aug", "5", "m7b5")]


def detect(notes, start, end, flats_key=None):
    """The chord that best explains the notes sounding between start and end, or None.

    Each note counts by how long it sounds there (and a little by how hard it was played);
    the lowest note counts extra as the likely root or bass."""
    weights = [0.0] * 12
    lowest = None
    for note in notes:
        overlap = min(end, note.tick + note.length) - max(start, note.tick)
        if overlap <= 0:
            continue
        weight = overlap * (0.6 + note.velocity / 254.0)
        weights[note.pitch % 12] += weight
        if lowest is None or note.pitch < lowest[0]:
            lowest = (note.pitch, weight)
    total = sum(weights)
    if total <= 0:
        return None
    best = None
    for root in range(12):
        for quality, intervals in _TEMPLATES:
            members = {(root + i) % 12 for i in intervals}
            inside = sum(weights[pc] for pc in members)
            outside = total - inside
            missing = sum(1 for pc in members if weights[pc] <= 0)
            score = inside - 1.2 * outside - 0.25 * missing * (total / max(1, len(members)))
            if lowest is not None and lowest[0] % 12 == root:
                score += 0.15 * total
            score -= 0.01 * total * len(intervals)        # simpler chords win ties
            if best is None or score > best[0]:
                best = (score, root, quality)
    _score, root, quality = best
    bass = lowest[0] % 12 if lowest is not None and lowest[0] % 12 != root else None
    if bass is not None and bass not in {(root + i) % 12 for i in _BY_KEY[quality][3]}:
        bass = None    # a passing low note, not a chord's bass
    return ChordChange(start, root, quality, bass)


def chords_from_notes(notes, timeline, start, end, step="bar"):
    """Chord changes worked out from notes, one per bar ("bar"), half bar ("half") or beat ("beat").
    Repeats of the same chord are merged."""
    changes = []
    position = start
    while position < end:
        bar = timeline.tick_to_bar(position)
        bar_end = timeline.bar_to_tick(bar + 1)
        if step == "beat":
            length = timeline.ticks_per_beat(bar)
        elif step == "half":
            length = max(timeline.ticks_per_beat(bar), (bar_end - timeline.bar_to_tick(bar)) // 2)
        else:
            length = bar_end - position
        stop = min(end, bar_end, position + length)
        found = detect(notes, position, stop)
        if found is not None and not (changes and (changes[-1].root, changes[-1].quality, changes[-1].bass)
                                      == (found.root, found.quality, found.bass)):
            changes.append(found)
        position = stop
    return changes


def describe_change(change, timeline, flats=False):
    return "{}: {}".format(timeline.describe_position(change.tick), name(change, flats))
