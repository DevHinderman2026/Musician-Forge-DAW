"""Songs, tracks and notes, plus saving, loading and undo.

A song file (.mforge) is plain JSON, so it is easy to inspect and hard to lose:
saving writes a temporary file first, keeps the previous version as a .bak
file, and only then replaces the song.
"""

import copy
import json
import math
import os
from dataclasses import dataclass, field

from . import compat, paths, theory
from .compat import NewerVersionError, SongFileError  # noqa: F401 - song.SongFileError, as before
from .timeline import PPQ, Timeline

FILE_FORMAT = "musician-forge-song"
FILE_VERSION = 9   # 2 added song sections, 3 audio tracks, 4 regions on instrument tracks, 5 effects,
                   # 6 the chord track, rhythm players and region looping, 7 automation, 8 rhythm players'
                   # variations, performances and pieces (players.clean_settings reads the older settings
                   # the way 0.9.1 played them), 9 (0.9.8) the drummer's hi-hat pedal piece and the open hi-hat
                   # folded into the hi-hat (player_pieces.clean_pieces reads the older pieces), and every rhythm
                   # player region records the rules it plays by. Older files open: compat.upgrade brings them up
                   # one version at a time (one step per version; add one there with each new version).
FILE_EXTENSION = ".mforge"
# (A development build of 0.9.7 saved "features" in a new project, 23 Oct 2026, to keep its kit-piece loudness and the
# ride and hi-hats taking turns out of older projects; Russell then chose them for every project, 23 Oct 2026, 4:52 AM.
# A file that has it opens as any other; it is not read or saved.)

MAX_TRACKS = 100
# what a command that needs a track says in a project with none yet (a new project starts with no tracks since
# Russell's request of 23 Oct 2026)
NO_TRACK_YET = "There is no track yet. Press Control+T to add one."
AUDIO_RATE = 48000     # recordings are kept at the engine's sample rate
INSTRUMENT_TRACK = "instrument"
AUDIO_TRACK = "audio"


@dataclass
class Note:
    tick: int
    length: int
    pitch: int
    velocity: int

    @property
    def end(self):
        return self.tick + self.length

    def as_list(self):
        return [self.tick, self.length, self.pitch, self.velocity]


DEFAULT_SECTION_BARS = 8


@dataclass
class Section:
    """A song section: a length in whole bars.

    Sections follow each other with no gaps, so a section's first bar is the
    bar after the previous section ends. There is no limit on how many.

    automatic: when on, recording past the end makes the section longer
    (for long takes); when off, recording loops back to the section start.
    An empty name means the section is called by its number ("Section 2"),
    so numbers stay in order when sections are added, moved or deleted.
    """

    length: int = DEFAULT_SECTION_BARS
    automatic: bool = False
    name: str = ""

    def display_name(self, number):
        return self.name.strip() or "Section {}".format(number)


@dataclass
class Instrument:
    bank: int = 0
    program: int = 0
    name: str = "Grand Piano"

    @property
    def is_drum_kit(self):
        return self.bank == 128


@dataclass
class NoteRegion:
    """A stretch of an instrument track, from tick `start` up to (not including) tick `end`."""

    start: int
    end: int
    name: str = ""
    mute: bool = False
    player: dict = field(default=None)   # a rhythm player's settings (see players.py), or None
    loops: int = 1                       # plays this many times in a row; 0 = until the next region

    @property
    def length(self):
        return self.end - self.start

    def contains(self, tick):
        return self.start <= tick < self.end

    def to_list(self):
        return [self.start, self.end, self.name, self.mute, self.player, self.loops]

    @classmethod
    def from_list(cls, raw):
        start, end = int(raw[0]), int(raw[1])
        name = str(raw[2]) if len(raw) > 2 and raw[2] is not None else ""
        mute = bool(raw[3]) if len(raw) > 3 else False
        player = dict(raw[4]) if len(raw) > 4 and isinstance(raw[4], dict) else None
        loops = max(0, min(999, int(raw[5]))) if len(raw) > 5 else 1
        if start < 0 or end <= start:
            raise ValueError("bad region {}".format(raw))
        return cls(start, end, name, mute, player, loops)


@dataclass
class AudioTake:
    """One recording (a WAV file). Saved projects keep the path relative to the project's folder."""

    file: str
    frames: int


@dataclass
class AudioRegion:
    """A recording placed on an audio track. Recording over a looped section adds takes;
    the newest plays, and any take can be chosen later.

    layer: where recordings overlap on a track, the newer one (higher layer) is heard,
    like recording over part of an older take; the older one plays again where the
    newer one ends.
    """

    tick: int
    takes: list = field(default_factory=list)
    active: int = 0
    gain_db: float = 0.0
    layer: int = 0
    mute: bool = False
    offset: int = 0          # frames trimmed off the start of the recording
    length: int = 0          # frames that play (0: to the end of the recording)
    loops: int = 1           # plays this many times in a row; 0 = until the next recording

    @property
    def take(self):
        return self.takes[self.active] if self.takes else None

    @property
    def frames(self):
        """How many frames of the recording play once (after trimming)."""
        if not self.takes:
            return 0
        available = max(0, self.take.frames - self.offset)
        return min(available, self.length) if self.length else available

    def end_tick(self, timeline):
        seconds = timeline.tick_to_seconds(self.tick) + self.frames / float(AUDIO_RATE)
        return int(round(timeline.seconds_to_tick(seconds)))

    def to_list(self):
        return [self.tick, [[t.file, t.frames] for t in self.takes], self.active, self.gain_db, self.layer,
                self.mute, self.offset, self.length, self.loops]


@dataclass
class Track:
    id: int
    name: str
    instrument: Instrument = field(default_factory=Instrument)
    volume: int = 80          # percent, 0 to 100
    pan: int = 0              # -100 (left) to 100 (right)
    mute: bool = False
    solo: bool = False
    notes: list = field(default_factory=list)
    kind: str = INSTRUMENT_TRACK
    regions: list = field(default_factory=list)   # audio tracks: AudioRegion list
    stereo: bool = False                           # audio tracks: record two channels
    monitor: bool = False                          # audio tracks: hear the input while recording
    note_regions: list = field(default_factory=list)  # instrument tracks: NoteRegion list (see regions.py)
    effects: list = field(default_factory=list)       # the track's effects, in order (see effects.py)
    automation: list = field(default_factory=list)    # lanes: volume, pan, effect settings over time (automation.py)
    # the drummer's kit-piece loudness on this track ({piece key: 0 to 100}, only those not at 50; 0.9.7, every
    # project): every Anvil region on the track plays each piece this loud. An older project's tracks have none, so
    # they play as they did.
    kit_levels: dict = field(default_factory=dict)

    @property
    def is_audio(self):
        return self.kind == AUDIO_TRACK

    def sort_notes(self):
        self.notes.sort(key=lambda n: (n.tick, n.pitch))

    def sort_regions(self):
        self.regions.sort(key=lambda r: r.tick)

    def top_layer(self):
        """The layer for a new recording: above every recording already on the track."""
        return max((r.layer for r in self.regions), default=-1) + 1

    def pan_description(self):
        if self.pan == 0:
            return "center"
        return "{} percent {}".format(abs(self.pan), "left" if self.pan < 0 else "right")

    def describe(self, number=None):
        """One line for the track list, read by screen readers."""
        parts = []
        if number is not None:
            parts.append("{}.".format(number))
        parts.append(self.name + ",")
        if self.is_audio:
            parts.append("audio track,")
            count = len(self.regions)
            parts.append("{} recording{},".format(count, "" if count == 1 else "s"))
        else:
            parts.append(self.instrument.name + ",")
            players = sum(1 for r in self.note_regions if r.player)
            if players:
                parts.append("{} rhythm player region{},".format(players, "" if players == 1 else "s"))
            if self.notes or not players:
                parts.append("{} notes,".format(len(self.notes)) if len(self.notes) != 1 else "1 note,")
        parts.append("volume {},".format(self.volume))
        parts.append("pan {}".format(self.pan_description()))
        active = sum(1 for e in self.effects if e.get("on", True))
        if self.effects:
            parts.append(", {} effect{}".format(len(self.effects), "" if len(self.effects) == 1 else "s"))
            if active < len(self.effects):
                parts.append(", {} off".format(len(self.effects) - active))
        kinds = []
        for lane in self.automation:
            word = lane["target"] if lane["target"] in ("volume", "pan") else "effects"
            if lane["points"] and lane.get("on", True) and word not in kinds:
                kinds.append(word)
        if kinds:
            parts.append(", automation: {}".format(", ".join(kinds)))
        if self.mute:
            parts.append(", muted")
        if self.solo:
            parts.append(", solo")
        return " ".join(parts).replace(" ,", ",")


def _valid_place(raw):
    """{"playhead": tick, "track": id or None} from a file, or None (anything damaged is left out, never an error)."""
    if not isinstance(raw, dict):
        return None
    try:
        playhead = max(0, int(raw.get("playhead", 0)))
    except (TypeError, ValueError, OverflowError):
        return None
    track = raw.get("track")
    return {"playhead": playhead, "track": track if isinstance(track, int) and not isinstance(track, bool) else None}


def valid_strips(raw):
    """8 chord strips [root 0-11, chord type, bass 0-11 or None] from a file, or None (anything damaged: the key's)."""
    from .chords import QUALITY_KEYS

    if not isinstance(raw, list) or len(raw) != 8:
        return None
    strips = []
    for item in raw:
        try:
            root, quality, bass = item
            root = int(root) % 12
            bass = None if bass is None else int(bass) % 12
        except (TypeError, ValueError, OverflowError):
            return None
        if quality not in QUALITY_KEYS or isinstance(item[0], bool):
            return None
        strips.append([root, quality, bass])
    return strips


# SongFileError ("a song file could not be read") and NewerVersionError (saved by a newer Musician Forge) live in
# compat.py, with the steps that open older files; they are imported above so song.SongFileError stays where it was.


class Song:
    def __init__(self, title="Untitled", timeline=None):
        self.title = title
        self.timeline = timeline or Timeline()
        self.tracks = []
        self.sections = [Section()]
        self.chords = []        # the chord track: chords.ChordChange list, in time order
        self._next_id = 1
        # Where you were when it was saved: {"playhead": tick, "track": track id} (Russell, 10 Oct 2026: saved in
        # section 3, opened in section 1). Written only when saving, so moving the playhead is never an unsaved change;
        # an older Musician Forge ignores it.
        self.place = None
        # Your own chord strips (Russell, 10 Oct 2026): 8 [root, chord type, bass or None] for the keys A to K, or None
        # to follow the song's key. Saved with the project; an older Musician Forge ignores them.
        self.strips = None

    # -- tracks -------------------------------------------------------------
    def add_track(self, name=None, instrument=None, index=None):
        if len(self.tracks) >= MAX_TRACKS:
            raise ValueError("A song can have up to {} tracks".format(MAX_TRACKS))
        track = Track(id=self._next_id, name=name or "Track {}".format(self._next_id),
                      instrument=instrument or Instrument())
        self._next_id += 1
        if index is None:
            self.tracks.append(track)
        else:
            self.tracks.insert(index, track)
        return track

    def next_track_id(self):
        """A new, unused track number (for tracks made by copying)."""
        number = self._next_id
        self._next_id += 1
        return number

    def remove_track(self, track_id):
        self.tracks = [t for t in self.tracks if t.id != track_id]

    def track_by_id(self, track_id):
        for track in self.tracks:
            if track.id == track_id:
                return track
        return None

    def index_of(self, track_id):
        for i, track in enumerate(self.tracks):
            if track.id == track_id:
                return i
        return -1

    def move_track(self, track_id, new_index):
        i = self.index_of(track_id)
        if i < 0:
            return
        track = self.tracks.pop(i)
        new_index = max(0, min(len(self.tracks), new_index))
        self.tracks.insert(new_index, track)

    def audible_tracks(self):
        """Tracks that should sound, honoring mute and solo."""
        soloed = [t for t in self.tracks if t.solo]
        if soloed:
            return [t for t in soloed if not t.mute]
        return [t for t in self.tracks if not t.mute]

    # -- sections -------------------------------------------------------------
    def section_start(self, index):
        """First bar of a section."""
        return 1 + sum(sec.length for sec in self.sections[:index])

    def section_bounds(self, index):
        """(first bar, bar after the last bar) of a section."""
        start = self.section_start(index)
        return start, start + self.sections[index].length

    def end_bar(self):
        """The bar just after the song ends."""
        return 1 + sum(sec.length for sec in self.sections)

    def song_end_tick(self):
        return self.timeline.bar_to_tick(self.end_bar())

    def section_index_at_bar(self, bar):
        """Index of the section containing `bar` (bars past the end count as the last section)."""
        position = 1
        for i, section in enumerate(self.sections):
            position += section.length
            if bar < position:
                return i
        return len(self.sections) - 1

    def section_name(self, index):
        return self.sections[index].display_name(index + 1)

    def describe_section(self, index):
        start, end = self.section_bounds(index)
        section = self.sections[index]
        bars = "bar {}".format(start) if section.length == 1 else "bars {} to {}".format(start, end - 1)
        text = "{}: {}, {} bar{}".format(self.section_name(index), bars, section.length,
                                        "" if section.length == 1 else "s")
        if section.automatic:
            text += ", automatic"
        return text

    def last_music_bar(self):
        """The last bar that has a note sounding in it (0 if there are no notes)."""
        end = self.end_tick()
        return self.timeline.tick_to_bar(end - 1) if end > 0 else 0

    def tidy_regions(self):
        """Regions in order, not overlapping, and holding every note (see regions.py)."""
        from . import regions

        regions.tidy(self)

    def fit_last_section(self):
        """Make the last section long enough to hold every note (nothing is ever cut off)."""
        if not self.sections:
            self.sections = [Section()]
        needed = self.last_music_bar() + 1
        shortfall = needed - self.end_bar()
        if shortfall > 0:
            self.sections[-1].length += shortfall
            return True
        return False

    # -- notes --------------------------------------------------------------
    def end_tick(self):
        """Where the last note, region, recording or loop ends (0 for an empty song)."""
        from . import arrangement

        notes = max((n.end for t in self.tracks for n in t.notes), default=0)
        audio = max((r.end_tick(self.timeline) for t in self.tracks for r in t.regions), default=0)
        spans = max((r.end for t in self.tracks for r in t.note_regions), default=0)
        loops = 0
        for track in self.tracks:   # a region set to play several times makes the song longer
            for i, region in enumerate(track.note_regions):
                if region.loops > 1:
                    loops = max(loops, arrangement.note_region_repeats(track, i, 0)[1])
            for i, region in enumerate(track.regions):
                if region.loops > 1:
                    loops = max(loops, arrangement.audio_region_repeats(track, i, self.timeline, 0)[1])
        return max(notes, audio, spans, loops)

    def length_in_bars(self):
        end = self.end_tick()
        if end <= 0:
            return 0
        return self.timeline.tick_to_bar(end - 1)

    def note_count(self):
        return sum(len(t.notes) for t in self.tracks)

    def region_count(self):
        return sum(len(t.regions) for t in self.tracks)

    def has_content(self):
        """True if there is anything to play or export: notes, rhythm players or recordings. (Before 0.9.2 a song
        made only of rhythm players counted as empty, so it could not be exported.)"""
        return (self.note_count() > 0 or self.region_count() > 0
                or any(r.player for t in self.tracks for r in t.note_regions))

    # -- saving and loading -------------------------------------------------
    def to_dict(self):
        return {
            "format": FILE_FORMAT,
            "version": FILE_VERSION,
            "ppq": PPQ,
            "title": self.title,
            "next_track_id": self._next_id,
            "timeline": self.timeline.to_dict(),
            "sections": [[sec.length, sec.automatic, sec.name] for sec in self.sections],
            "chords": [c.to_list() for c in self.chords],
            **({"place": dict(self.place)} if self.place else {}),
            **({"strips": [list(s) for s in self.strips]} if self.strips else {}),
            "tracks": [
                {
                    "id": t.id, "name": t.name,
                    "instrument": {"bank": t.instrument.bank, "program": t.instrument.program,
                                   "name": t.instrument.name},
                    "volume": t.volume, "pan": t.pan, "mute": t.mute, "solo": t.solo,
                    "notes": [n.as_list() for n in t.notes],
                    "kind": t.kind, "regions": [r.to_list() for r in t.regions],
                    "stereo": t.stereo, "monitor": t.monitor,
                    "note_regions": [r.to_list() for r in t.note_regions],
                    "effects": copy.deepcopy(t.effects),
                    "automation": copy.deepcopy(t.automation),
                    **({"kit_levels": dict(t.kit_levels)} if t.kit_levels else {}),
                }
                for t in self.tracks
            ],
        }

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict) or data.get("format") != FILE_FORMAT:
            raise SongFileError("This is not a Musician Forge song file")
        try:
            saved = compat.saved_version(data)       # (a newer version's file: compat.upgrade refuses it plainly)
            data = compat.upgrade(copy.deepcopy(data))   # older files: up to date, one version at a time
            if int(data.get("ppq", PPQ)) != PPQ:
                raise SongFileError("This song uses an unsupported timing resolution")
            song = cls(title=str(data.get("title", "Untitled")),
                       timeline=Timeline.from_dict(data.get("timeline", {})))
            for td in data.get("tracks", []):
                inst = td.get("instrument", {})
                track = Track(
                    id=int(td["id"]), name=str(td.get("name", "Track")),
                    instrument=Instrument(int(inst.get("bank", 0)), int(inst.get("program", 0)),
                                          str(inst.get("name", "Instrument"))),
                    volume=_clamp(int(td.get("volume", 80)), 0, 100),
                    pan=_clamp(int(td.get("pan", 0)), -100, 100),
                    mute=bool(td.get("mute", False)), solo=bool(td.get("solo", False)),
                    notes=[_valid_note(n) for n in td.get("notes", [])],
                    kind=AUDIO_TRACK if td.get("kind") == AUDIO_TRACK else INSTRUMENT_TRACK,
                    regions=[_valid_region(r) for r in td.get("regions", [])],
                    stereo=bool(td.get("stereo", False)), monitor=bool(td.get("monitor", False)),
                    note_regions=[NoteRegion.from_list(r) for r in td.get("note_regions", [])],
                )
                from . import effects

                from . import automation, players

                for region in track.note_regions:
                    if region.player and players.clean_settings(region.player) is None:
                        region.player = None    # damaged rhythm player settings: an ordinary region (it used to
                                                # stop the whole song playing; the review of 9 Oct 2026)
                track.effects = effects.clean_effects(td.get("effects", []), track.kind)
                track.automation = automation.clean_lanes(td.get("automation", []), track)
                from . import player_pieces

                track.kit_levels = player_pieces.clean_kit_levels(td.get("kit_levels"))
                track.sort_notes()
                track.sort_regions()
                song.tracks.append(track)
            sections = []
            for length, automatic, name in data.get("sections", []):
                if int(length) < 1:
                    raise ValueError("a section must be at least 1 bar long")
                sections.append(Section(int(length), bool(automatic), str(name)))
            song.sections = sections or [Section()]
            from . import chords

            song.chords = chords.sort(chords.ChordChange.from_list(raw) for raw in data.get("chords", []))
            song.fit_last_section()  # older songs: one section long enough for all their notes
            from . import regions

            if saved < 4:
                regions.migrate(song)  # older songs: a region for each section that has notes
            regions.tidy(song)
            ids = [t.id for t in song.tracks]
            if len(ids) != len(set(ids)):
                raise SongFileError("The song file has two tracks with the same number")
            song._next_id = max([int(data.get("next_track_id", 1))] + [i + 1 for i in ids])
            song.place = _valid_place(data.get("place"))
            song.strips = valid_strips(data.get("strips"))
        except SongFileError:
            raise
        except (KeyError, TypeError, ValueError, IndexError, AttributeError, OverflowError) as exc:
            # OverflowError: a number too big to be one (Infinity, or 1e999) where a whole number belongs; until
            # 23 Oct 2026 it got past this, so opening offered no backup
            raise SongFileError("The song file is damaged: {}".format(exc)) from exc
        return song

    def save(self, path):
        """Save safely: temp file, keep a .bak of the previous version, then replace."""
        data = json.dumps(self.to_dict(), indent=1, ensure_ascii=False)
        folder = os.path.dirname(os.path.abspath(path))
        os.makedirs(folder, exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        if os.path.exists(path) and (not os.path.exists(path + ".bak") or Song.is_worth_keeping(path)):
            paths.replace_file(path, path + ".bak")       # a damaged file never takes a good backup's place
        paths.replace_file(tmp, path)

    @staticmethod
    def is_readable(path):
        """True if path opens as a song."""
        try:
            Song.load(path)
            return True
        except Exception:  # noqa: BLE001 - damaged in any way
            return False

    @staticmethod
    def is_worth_keeping(path):
        """True if path opens as a song, or was saved by a newer Musician Forge (a whole project this version cannot
        read, not damage: when its backup is opened instead and saved, it goes to the .bak file rather than being
        written over and lost; the review of 24 Oct 2026)."""
        try:
            Song.load(path)
            return True
        except NewerVersionError:
            return True
        except Exception:  # noqa: BLE001 - damaged in any way
            return False

    @classmethod
    def load(cls, path):
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except json.JSONDecodeError as exc:
            raise SongFileError("The song file is damaged (not valid JSON): {}".format(exc)) from exc
        except UnicodeDecodeError as exc:
            raise SongFileError("This is not a Musician Forge song file") from exc
        song = cls.from_dict(data)
        return song

    def clone(self):
        return Song.from_dict(copy.deepcopy(self.to_dict()))


def _clamp(value, low, high):
    return max(low, min(high, value))


def _valid_region(raw):
    tick, takes, active, gain_db = raw[:4]
    layer = int(raw[4]) if len(raw) > 4 else 0
    mute = bool(raw[5]) if len(raw) > 5 else False
    offset = max(0, int(raw[6])) if len(raw) > 6 else 0
    length = max(0, int(raw[7])) if len(raw) > 7 else 0
    loops = max(0, min(999, int(raw[8]))) if len(raw) > 8 else 1
    takes = [AudioTake(str(f), int(n)) for f, n in takes]
    if int(tick) < 0 or not takes or any(t.frames <= 0 for t in takes) or not math.isfinite(float(gain_db)):
        raise ValueError("bad recording {}".format(raw))
    return AudioRegion(int(tick), takes, max(0, min(len(takes) - 1, int(active))), float(gain_db), layer, mute,
                       offset, length, loops)


def _valid_note(raw):
    tick, length, pitch, velocity = (int(v) for v in raw)
    if tick < 0 or length <= 0 or not 0 <= pitch <= 127 or not 1 <= velocity <= 127:
        raise ValueError("bad note {}".format(raw))
    return Note(tick, length, pitch, velocity)


class UndoHistory:
    """Undo and redo by keeping snapshots of the whole song.

    Songs are small (a few thousand notes at most), so snapshots are simple,
    reliable and fast.
    """

    def __init__(self, limit=100):
        self.limit = limit
        self._undo = []   # list of (label, snapshot)
        self._redo = []

    def record(self, label, song):
        """Call BEFORE changing the song."""
        self.push(label, song.to_dict())

    def push(self, label, snapshot):
        """Store a snapshot taken before a change (see Session.edit)."""
        self._undo.append((label, snapshot))
        if len(self._undo) > self.limit:
            self._undo.pop(0)
        self._redo.clear()

    def can_undo(self):
        return bool(self._undo)

    def can_redo(self):
        return bool(self._redo)

    def undo_label(self):
        return self._undo[-1][0] if self._undo else None

    def redo_label(self):
        return self._redo[-1][0] if self._redo else None

    def undo(self, current_song):
        """Returns (label, restored_song) or None."""
        if not self._undo:
            return None
        label, snapshot = self._undo.pop()
        self._redo.append((label, current_song.to_dict()))
        return label, Song.from_dict(snapshot)

    def redo(self, current_song):
        if not self._redo:
            return None
        label, snapshot = self._redo.pop()
        self._undo.append((label, current_song.to_dict()))
        return label, Song.from_dict(snapshot)

    def clear(self):
        self._undo.clear()
        self._redo.clear()


def new_song(title="Untitled", bpm=120.0, numerator=4, denominator=4, tonic=0, scale="Major"):
    """A new song with one piano track, ready to play."""
    from .timeline import KeyChange, TempoChange, TimeSignatureChange

    timeline = Timeline(tempos=[TempoChange(1, 1, bpm)],
                        time_signatures=[TimeSignatureChange(1, numerator, denominator)],
                        keys=[KeyChange(1, tonic, scale)])
    song = Song(title=title, timeline=timeline)
    song.add_track("Piano", Instrument(0, 0, "Grand Piano"))
    return song


def describe_note(note, timeline, flats=False):
    """Spoken description of a note for the event list."""
    return "{}, {}, velocity {}, {}".format(
        timeline.describe_position(note.tick), theory.spoken_note_name(note.pitch, flats),
        note.velocity, _length_words(note.length))


def _length_words(length):
    from .timeline import describe_length

    return describe_length(length)
