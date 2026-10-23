"""Where an export distorts, by how much, and which tracks are loudest there (Russell, 21 Oct 2026: the warning has
to be specific, so a musician who mixes by ear knows where to listen and what to turn down).

An export distorts where its sound reaches full scale (CLIP_LEVEL): a WAV or M4A file cannot hold anything louder,
so those moments are cut flat. ClipFinder watches the blocks as they are written and keeps the stretches where that
happens (with the loudest moment of each). The words name the bars and sections, how many decibels too loud the
loudest moment was, and the tracks that are loudest there, with the volume each would need.
"""

import math

import numpy as np

FADE_SECONDS_RANGE = (5, 30)     # the export's fade-out (Russell, 21 Oct 2026: 5 to 30 seconds, 10 to start)
FADE_SECONDS_DEFAULT = 10
CLIP_LEVEL = 0.999               # full scale: the file cannot hold more (0.9.4's warning used the same)
JOIN_SECONDS = 0.5               # moments closer than this are one stretch
MOST_PLACES = 3                  # the places named; the rest are counted
MOST_TRACKS = 3                  # the tracks named
NAMED_WITHIN_DB = 6.0            # a track is named when it is within this of the loudest one there


class ClipFinder:
    def __init__(self, sample_rate):
        self.rate = sample_rate
        self.spans = []          # [first frame, last frame, loudest level]

    def add(self, levels, start_frame):
        """levels: how loud each frame was before full scale cut it off (render_offline's on_levels), or a block of
        (frames, channels); start_frame: where it starts in the file."""
        if not len(levels):
            return
        level = np.max(np.abs(levels), axis=1) if levels.ndim > 1 else np.abs(levels)
        over = np.nonzero(level >= CLIP_LEVEL)[0]
        if not len(over):
            return
        join = int(JOIN_SECONDS * self.rate)
        # stretches inside the block: wherever two loud frames are further apart than JOIN_SECONDS a new one starts
        breaks = np.nonzero(np.diff(over) > join)[0]
        starts = np.concatenate(([0], breaks + 1))
        ends = np.concatenate((breaks, [len(over) - 1]))
        for a, b in zip(starts, ends):
            first, last = start_frame + int(over[a]), start_frame + int(over[b])
            loud = float(np.max(level[over[a]:over[b] + 1]))
            if self.spans and first - self.spans[-1][1] <= join:
                self.spans[-1][1] = last
                self.spans[-1][2] = max(self.spans[-1][2], loud)
            else:
                self.spans.append([first, last, loud])

    def windows(self):
        """[(start seconds, end seconds, loudest level)]."""
        return [(a / float(self.rate), (b + 1) / float(self.rate), loud) for a, b, loud in self.spans]


def decibels_over(level):
    """How many decibels over full scale (at least a tenth: a sound held right at the top is over too)."""
    return max(0.1, 20.0 * math.log10(max(level, 1e-9)))


def bar_ranges(windows, timeline):
    """[(first bar, last bar)] the windows fall in, joined where they touch or follow each other."""
    ranges = []
    for start, end, _loud in windows:
        first = timeline.tick_to_bar(int(timeline.seconds_to_tick(start)))
        last = timeline.tick_to_bar(int(timeline.seconds_to_tick(max(start, end - 1e-6))))
        if ranges and first <= ranges[-1][1] + 1:
            ranges[-1] = (ranges[-1][0], max(ranges[-1][1], last))
        else:
            ranges.append((first, last))
    return ranges


def place_words(first, last, song):
    """'bar 61 (Section 5)' or 'bars 33 to 36 (Section 3)' or 'bars 15 to 18 (Sections 2 and 3)'."""
    sections = []
    for bar in range(first, last + 1):
        name = song.section_name(song.section_index_at_bar(bar))
        if name not in sections:
            sections.append(name)
    if len(sections) > 2:
        where = "{} to {}".format(sections[0], sections[-1])
    else:
        where = " and ".join(sections)
    if first == last:
        return "bar {} ({})".format(first, where)
    return "bars {} to {} ({})".format(first, last, where)


def places_words(windows, song):
    ranges = bar_ranges(windows, song.timeline)
    named = [place_words(first, last, song) for first, last in ranges[:MOST_PLACES]]
    more = len(ranges) - len(named)
    if more:
        named.append("{} more place{}".format(more, "" if more == 1 else "s"))
    if len(named) == 1:
        return named[0]
    return ", ".join(named[:-1]) + " and " + named[-1]


def turned_down(volume, db):
    """A track's volume (0 to 100; its loudness goes with the square) turned down by `db` decibels."""
    return max(0, int(math.floor(volume * 10 ** (-db / 40.0))))


def whole_db(db):
    return max(1, int(math.ceil(db - 1e-9)))


def song_words(windows, song, loud_tracks=None):
    """The warning for a song mixed into one file: where, how much, and the loudest tracks there.
    loud_tracks: [(track, level there)], loudest first, or None when they were not measured."""
    over = whole_db(decibels_over(max(loud for _s, _e, loud in windows)))
    words = " It distorts at {}: up to about {} dB too loud there, so listen there.".format(
        places_words(windows, song), over)
    named = _named(loud_tracks)
    if named:
        changes = ", ".join("{} from volume {} to {}".format(track_label(t, song), t.volume,
                                                             turned_down(t.volume, over)) for t in named)
        words += " The loudest track{} there {} {}. Turning {} down about {} dB ({}) should fix it; export again to " \
                 "check.".format("s" if len(named) > 1 else "", "are" if len(named) > 1 else "is",
                                 _list_words([track_label(t, song) for t in named]),
                                 "them" if len(named) > 1 else "it", over,
                                 changes)
    else:
        words += " Turning the loudest tracks down about {} dB should fix it; export again to check.".format(over)
    return words


def tracks_words(found, song):
    """The warning for tracks exported on their own: found [(track, windows)] of the files that distort."""
    parts = []
    for track, windows in found[:MOST_TRACKS]:
        over = whole_db(decibels_over(max(loud for _s, _e, loud in windows)))
        parts.append("{} at {}, up to about {} dB too loud (volume {} to {} fixes it)".format(
            track_label(track, song), places_words(windows, song), over, track.volume,
            turned_down(track.volume, over)))
    more = len(found) - len(parts)
    if more:
        parts.append("{} more track{}".format(more, "" if more == 1 else "s"))
    return " Distortion: {}. Export again to check.".format("; ".join(parts))


def track_label(track, song):
    """A track's name, with its number when another track has the same name ("track 2, Piano"): after Control+D
    every copy is called the same, and "Piano, Piano and Piano" could not be told apart (23 Oct 2026)."""
    tracks = list(getattr(song, "tracks", []) or [])
    name = track.name
    key = str(name).strip().lower()
    if sum(1 for t in tracks if str(t.name).strip().lower() == key) < 2:
        return name
    for number, t in enumerate(tracks, 1):
        if t is track or t.id == getattr(track, "id", None):
            return "track {}, {}".format(number, name)
    return name


def _named(loud_tracks):
    if not loud_tracks:
        return []
    top = loud_tracks[0][1]
    if top <= 0:
        return []
    floor = top * 10 ** (-NAMED_WITHIN_DB / 20.0)
    return [track for track, level in loud_tracks[:MOST_TRACKS] if level >= floor]


def _list_words(names):
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " and " + names[-1]
