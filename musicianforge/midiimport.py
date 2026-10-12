"""Importing standard MIDI files (version 0.9.1; Russell, 8 Oct 2026: "importing also covers MIDI files").

Reads type 0 and type 1 MIDI files (and RIFF RMID files, which wrap one), at any timing resolution, into:
- tracks: one for each MIDI track that has notes, split by channel when a track holds several; channel 10
  becomes a drum track; the program change (and bank select) in force when its first note starts chooses the
  instrument, wherever the file sets it (a type 1 file often does so in a track of its own); the volume and
  pan in force then become the track's own, and later volume and pan changes become automation that holds;
- the song's timeline: every tempo change, time signature and key signature, and the markers as sections
  (the way Musician Forge's MIDI export writes them, so a song survives the round trip).

Real files have oddities, all legal: running status (a status byte left out because it repeats), note-ons
with velocity 0 that end notes, notes struck again before they end, notes never ended, events after the
end-of-track marker, chunks Musician Forge does not know, and more. A damaged or cut-off file gives a
plain-words message and imports nothing. Standard library only.

Time signature and key changes in Musician Forge start on a bar line, so one that a file puts partway
through a bar moves to the next bar line, and the import says so. Keys come as a number of sharps or flats
plus major or minor; Musician Forge's own export also writes the exact key (a mode such as Dorian) in a
text event beside it, which the import reads back.
"""

import os
import struct
from dataclasses import dataclass, field

from .song import Note
from .timeline import MAX_BPM, MIN_BPM, PPQ, VALID_DENOMINATORS, MAX_NUMERATOR

DRUM_CHANNEL = 9
KEY_TEXT_PREFIX = "Musician Forge key: "     # written by midifile.py next to each key signature
CHORD_TRACK_NAME = "Chord track"             # midifile.py writes the chord track as a MIDI track of this name
CHORD_TEXT_PREFIX = "Musician Forge chord: " # ... with this text event at each chord
INSTRUMENT_TEXT_PREFIX = "Musician Forge instrument: "   # midifile.py: the exact instrument of a track
MIN_NOTE_TICKS = 30
MAX_FILE_BYTES = 64 * 1024 * 1024


class MidiImportError(ValueError):
    """The file cannot be imported; the message says why in plain words."""


@dataclass
class ImportedTrack:
    name: str
    channel: int
    bank: int = 0
    program: int = 0
    notes: list = field(default_factory=list)          # song.Note, at 960 ticks per quarter note
    volume: int = None                                 # percent, from the first volume (controller 7)
    pan: int = None                                    # -100 to 100, from the first pan (controller 10)
    volume_points: list = field(default_factory=list)  # [(tick, percent)] later volume changes
    pan_points: list = field(default_factory=list)
    exact: tuple = None                                # (bank, program) Musician Forge wrote for its own import

    @property
    def drums(self):
        return self.channel == DRUM_CHANNEL


@dataclass
class MidiContents:
    format: int
    division: int
    tracks: list                 # ImportedTrack with notes
    tempos: list                 # [(tick, bpm)]
    time_signatures: list        # [(tick, numerator, denominator)]
    keys: list                   # [(tick, tonic, scale)]
    markers: list                # [(tick, text)]
    title: str = ""
    end_tick: int = 0
    warnings: list = field(default_factory=list)
    chords: list = field(default_factory=list)   # Musician Forge's own chord track: [ChordChange]

    @property
    def note_count(self):
        return sum(len(t.notes) for t in self.tracks)


# ----------------------------------------------------------------------
# reading the bytes
# ----------------------------------------------------------------------
class _Reader:
    def __init__(self, data):
        self.data, self.pos = data, 0

    def byte(self):
        if self.pos >= len(self.data):
            raise MidiImportError("the file is cut short in the middle of a track")
        value = self.data[self.pos]
        self.pos += 1
        return value

    def take(self, count):
        if count < 0 or self.pos + count > len(self.data):
            raise MidiImportError("the file is cut short in the middle of a track")
        piece = self.data[self.pos:self.pos + count]
        self.pos += count
        return piece

    def varlen(self):
        value = 0
        for _ in range(4):
            byte = self.byte()
            value = (value << 7) | (byte & 0x7F)
            if not byte & 0x80:
                return value
        raise MidiImportError("the file has a number that is too long, so it is damaged")


def _text(payload):
    for encoding in ("utf-8", "cp1252", "latin-1"):
        try:
            return payload.decode(encoding).strip().strip("\0").strip()
        except UnicodeDecodeError:
            continue
    return ""


def _chunks(data):
    """The file's chunks: (kind, body)."""
    if data[:4] == b"RIFF" and data[8:12] == b"RMID":          # a RIFF MIDI file wraps a standard one
        pos = 12
        while pos + 8 <= len(data):
            kind, size = data[pos:pos + 4], struct.unpack("<I", data[pos + 4:pos + 8])[0]
            if kind == b"data":
                data = data[pos + 8:pos + 8 + size]
                break
            pos += 8 + size + (size & 1)
    if data[:4] != b"MThd":
        raise MidiImportError("it is not a MIDI file (it does not start the way MIDI files do)")
    pos, chunks = 0, []
    while pos + 8 <= len(data):
        kind = data[pos:pos + 4]
        size = struct.unpack(">I", data[pos + 4:pos + 8])[0]
        body = data[pos + 8:pos + 8 + size]
        if len(body) < size:
            if kind == b"MTrk" and body:
                chunks.append((kind, body, True))              # the last track is cut short: read what is there
            break
        chunks.append((kind, body, False))
        pos += 8 + size
    return chunks


def _events(body, cut_short):
    """(tick, kind, channel, data) for one track; kind is "meta" (with (type, payload)), or a channel event."""
    reader = _Reader(body)
    tick, status, events = 0, None, []
    try:
        while reader.pos < len(body):
            tick += reader.varlen()
            byte = reader.byte()
            if byte == 0xFF:
                kind = reader.byte()
                payload = reader.take(reader.varlen())
                events.append((tick, "meta", None, (kind, payload)))
                if kind == 0x2F:
                    break                                       # end of track: anything after it is ignored
                continue
            if byte in (0xF0, 0xF7):
                reader.take(reader.varlen())                    # system exclusive: skipped
                continue
            if byte & 0x80:
                if byte >= 0xF0:
                    continue                                    # a stray system message: skipped
                status = byte
            else:
                if status is None:
                    raise MidiImportError("a track has data without saying what it is, so the file is damaged")
                reader.pos -= 1                                 # running status: the byte is data
            high, channel = status & 0xF0, status & 0x0F
            count = 1 if high in (0xC0, 0xD0) else 2
            values = tuple(reader.byte() & 0x7F for _ in range(count))
            events.append((tick, high, channel, values))
    except MidiImportError:
        if not cut_short:
            raise
    return events


def parse(data):
    """MidiContents from the bytes of a MIDI file; raises MidiImportError with words."""
    if len(data) > MAX_FILE_BYTES:
        raise MidiImportError("it is larger than any song file should be ({} megabytes)".format(len(data) // 1000000))
    chunks = _chunks(bytes(data))
    if not chunks or chunks[0][0] != b"MThd" or len(chunks[0][1]) < 6:
        raise MidiImportError("its header is damaged")
    fmt, count, division = struct.unpack(">HHH", chunks[0][1][:6])
    if fmt not in (0, 1, 2):
        raise MidiImportError("it says it is MIDI file type {}, which does not exist".format(fmt))
    if division & 0x8000:
        raise MidiImportError("it counts time in film frames (SMPTE), not in beats; save it again with beats "
                              "(ticks per quarter note) in the program that made it")
    if division == 0:
        raise MidiImportError("its header says a beat lasts no time at all, so it is damaged")
    tracks = [(body, short) for kind, body, short in chunks[1:] if kind == b"MTrk"]
    contents = MidiContents(fmt, division, [], [], [], [], [])
    if not tracks:
        raise MidiImportError("it has no tracks in it")
    if any(short for _body, short in tracks):
        contents.warnings.append("the file is cut short at the end, so its last notes may be missing")
    if fmt == 2:
        contents.warnings.append("it is a type 2 MIDI file (separate patterns), so its tracks are laid one after "
                                 "another's start, all at bar 1")
    scale = PPQ / float(division)

    def at(raw_tick):
        return int(round(raw_tick * scale))

    key_texts = {}
    padded_end = 0
    own_file = False                                    # written by Musician Forge (its own text events)
    track_events = [_events(body, short) for body, short in tracks]
    # Each channel's instrument, bank, volume and pan, from every track in time order: a type 1 file often sets
    # them up in a track of their own, apart from the notes (the review of 9 Oct 2026).
    settings = {}
    for events in track_events:
        for tick, kind, channel, values in events:
            if kind == 0xC0:
                settings.setdefault(channel, {}).setdefault("program", []).append((at(tick), values[0]))
            elif kind == 0xB0 and values[0] in (0, 7, 10):
                what = {0: "bank", 7: "volume", 10: "pan"}[values[0]]
                settings.setdefault(channel, {}).setdefault(what, []).append((at(tick), values[1]))
    for changes in settings.values():
        for key in changes:
            changes[key].sort(key=lambda change: change[0])          # stable: at the same moment, the later track
    for number, events in enumerate(track_events):
        names = [_text(e[3][1]) for e in events if e[1] == "meta" and e[3][0] == 0x03 and e[0] == 0]
        own_chords = [(e[0], _text(e[3][1])[len(CHORD_TEXT_PREFIX):]) for e in events if e[1] == "meta"
                      and e[3][0] == 0x01 and _text(e[3][1]).startswith(CHORD_TEXT_PREFIX)]
        if own_chords and names and names[0] == CHORD_TRACK_NAME:
            # Musician Forge's own chord track: it becomes the chord track again, not a track of notes
            own_file = True
            from .chords import ChordChange
            for raw_tick, raw in own_chords:
                parts = raw.split(" ")              # tick root quality bass (the tick is the event's own)
                try:
                    bass = int(parts[3]) if len(parts) > 3 and parts[3] else None
                    contents.chords.append(ChordChange.from_list([at(raw_tick), int(parts[1]), parts[2], bass]))
                except (ValueError, IndexError):
                    continue
            continue
        instrument_names = [_text(e[3][1]) for e in events if e[1] == "meta" and e[3][0] == 0x04]
        exact = None
        for e in events:
            if e[1] == "meta" and e[3][0] == 0x01 and _text(e[3][1]).startswith(INSTRUMENT_TEXT_PREFIX):
                exact = instrument_from_text(_text(e[3][1])[len(INSTRUMENT_TEXT_PREFIX):])
                own_file = True
        by_channel = {}
        for tick, kind, channel, values in events:
            t = at(tick)
            if kind == "meta" and values[0] == 0x2F:
                padded_end = max(padded_end, t)        # where a track says it ends: often empty time after the music
            elif kind == "meta":
                contents.end_tick = max(contents.end_tick, t)
            if kind == "meta":
                meta, payload = values
                if meta == 0x51 and len(payload) >= 3:
                    micros = int.from_bytes(payload[:3], "big")
                    if micros > 0:
                        contents.tempos.append((t, simplest_bpm(micros)))
                elif meta == 0x58 and len(payload) >= 2:
                    contents.time_signatures.append((t, payload[0], 2 ** payload[1] if payload[1] < 8 else 0))
                elif meta == 0x59 and len(payload) >= 2:
                    sharps = struct.unpack("b", payload[:1])[0]
                    minor = payload[1] == 1
                    contents.keys.append((t, sharps, minor))
                elif meta == 0x06:
                    contents.markers.append((t, _text(payload)))
                elif meta == 0x01 and _text(payload).startswith(KEY_TEXT_PREFIX):
                    key_texts[t] = _text(payload)[len(KEY_TEXT_PREFIX):]
                elif meta == 0x03 and number == 0 and t == 0 and not contents.title:
                    contents.title = _text(payload)
                continue
            if kind not in (0x80, 0x90):
                continue
            state = by_channel.setdefault(channel, {"open": {}, "notes": [], "first_note": None})
            pitch, velocity = values
            if kind == 0x90 and velocity > 0:
                if state["first_note"] is None:
                    state["first_note"] = t
                struck = state["open"].pop(pitch, None)
                if struck is not None and t > struck[0]:
                    # struck again before it ended: the first one ends here, as a synthesizer plays it (and a
                    # single note-off then ends the new one, instead of leaving it sounding to the end)
                    state["notes"].append(Note(struck[0], max(MIN_NOTE_TICKS, t - struck[0]), pitch, struck[1]))
                state["open"][pitch] = (t, max(1, velocity))
            else:
                struck = state["open"].pop(pitch, None)
                if struck is not None:
                    state["notes"].append(Note(struck[0], max(MIN_NOTE_TICKS, t - struck[0]), pitch, struck[1]))
        last = at(events[-1][0]) if events else 0
        for channel in sorted(by_channel):
            state = by_channel[channel]
            for pitch, (start, velocity) in state["open"].items():    # notes never ended: they end with the track
                state["notes"].append(Note(start, max(MIN_NOTE_TICKS, last - start), pitch, velocity))
            state["open"] = {}
        if names and names[0].strip().lower() == CHORD_TRACK_NAME.lower():
            # A chord track that came back from another program without Musician Forge's chord texts: its held
            # chords become the chord track again (the same rule in reverse, Russell, 10 Oct 2026)
            held = [n for state in by_channel.values() for n in state["notes"]]
            contents.chords.extend(chords_from_held_notes(held))
            for n in held:
                contents.end_tick = max(contents.end_tick, n.end)
            continue
        for channel in sorted(by_channel):
            state = by_channel[channel]
            if not state["notes"]:
                continue
            state["notes"].sort(key=lambda n: (n.tick, n.pitch))
            name = names[0] if names else (instrument_names[0] if instrument_names else "")
            if len([c for c in by_channel if by_channel[c]["notes"]]) > 1 or not name:
                label = "drums" if channel == DRUM_CHANNEL else "channel {}".format(channel + 1)
                name = "{}, {}".format(name, label) if name else "MIDI track {}, {}".format(number + 1, label)
            changes = settings.get(channel, {})
            first = state["first_note"]
            program = _at_first_note(changes.get("program"), first)
            if program is None and changes.get("program"):
                program = changes["program"][0][1]             # set only after the first note: still the one meant
            bank = _at_first_note(changes.get("bank"), first)
            track = ImportedTrack(name[:60], channel, bank or 0, program or 0, state["notes"])
            track.exact = exact
            track.volume, track.volume_points = _first_and_rest(changes.get("volume"), _volume_percent, first)
            track.pan, track.pan_points = _first_and_rest(changes.get("pan"), _pan_value, first)
            contents.tracks.append(track)
    # one of each per moment (a file may repeat them, in several tracks): the last one counts
    contents.tempos = _last_at_each_tick(contents.tempos)
    contents.time_signatures = _last_at_each_tick(contents.time_signatures)
    contents.keys = _last_at_each_tick(contents.keys)
    # Musician Forge's own export writes the exact key (a mode, say) in a text event beside each key signature
    contents.keys = [(tick, sharps, minor, key_texts.get(tick)) for tick, sharps, minor in contents.keys]
    for note_track in contents.tracks:
        contents.end_tick = max([contents.end_tick] + [n.end for n in note_track.notes])
    # Musician Forge ends its file where the song ends (empty sections at the end included), so that end counts;
    # another program often pads its tracks with empty time, which would become empty bars after the music
    if own_file or key_texts:
        contents.end_tick = max(contents.end_tick, padded_end)
    return contents


def chords_from_held_notes(notes):
    """Chord changes from a track of held chords: one where new notes start, worked out from what sounds."""
    from .chords import detect

    starts = sorted({n.tick for n in notes})
    changes = []
    for k, start in enumerate(starts):
        stop = starts[k + 1] if k + 1 < len(starts) else max(n.end for n in notes if n.tick == start)
        found = detect([n for n in notes if n.tick <= start < n.end or n.tick == start], start, max(stop, start + 1))
        if found is not None:
            changes.append(found)
    return changes


def _last_at_each_tick(items):
    """Items (tick first) in time order, keeping only the last one given for each tick."""
    found = {}
    for item in items:
        found[item[0]] = item
    return [found[tick] for tick in sorted(found)]


def _at_first_note(changes, first_note):
    """The raw value in force when the first note starts: the last change at or before it, or None."""
    value = None
    for tick, raw in changes or ():
        if tick > first_note:
            break
        value = raw
    return value


def simplest_bpm(micros):
    """The tempo for microseconds per quarter note, with as few decimals as give back the same number
    (a file's 428571 is 140 beats per minute, not 140.00005)."""
    exact = 60_000_000.0 / micros
    for decimals in range(5):
        candidate = round(exact, decimals)
        if candidate > 0 and int(round(60_000_000.0 / candidate)) == micros:
            return candidate
    return round(exact, 4)


def _volume_percent(value):
    return max(0, min(100, int(round(value * 100 / 127.0))))


def _pan_value(value):
    return max(-100, min(100, int(round((value - 64) * 100 / 63.0))))


def _first_and_rest(changes, convert, first_note=0):
    """(the track's own value, [(tick, value)] for the changes after it), for a channel's volume or pan changes.

    The track's own value is the one set at the very start (a file sets its mix there, and Musician Forge's own
    export writes the track's setting there); without one, the one in force when the first note starts; without
    that either, None (the track keeps its own, and every change becomes a point). Of several changes at the same
    moment the last one counts (the review of 9 Oct 2026: the first one won); repeats are left out."""
    if not changes:
        return None, []
    changes = _last_at_each_tick(changes)
    if changes[0][0] == 0:
        start = 0
    else:
        before = [c for c in changes if c[0] <= first_note]
        start = before[-1][0] if before else None
    first = None
    points = []
    for tick, raw in changes:
        value = convert(raw)
        if start is not None and tick <= start:
            first = value
            continue
        if points and points[-1][1] == value or (not points and first is not None and value == first):
            continue
        points.append((tick, value))
    return first, points


def read_file(path):
    """MidiContents from a MIDI file on disk, or MidiImportError with words."""
    try:
        with open(path, "rb") as fh:
            data = fh.read(MAX_FILE_BYTES + 1)
    except OSError as exc:
        raise MidiImportError("it could not be opened ({})".format(exc.strerror or exc)) from None
    if not data:
        raise MidiImportError("it is empty")
    return parse(data)


# ----------------------------------------------------------------------
# the song's timeline, from the file's tempos, meters, keys and markers
# ----------------------------------------------------------------------
def key_from_signature(sharps, minor):
    """(tonic 0 to 11, scale) for a key signature: -7 to 7 sharps (flats negative), major or minor."""
    major_tonic = (7 * int(sharps)) % 12
    if minor:
        return (major_tonic + 9) % 12, "Natural Minor"
    return major_tonic, "Major"


def key_text(tonic, scale):
    """The text event Musician Forge's export writes beside a key signature: the exact key, mode and all."""
    return "{}tonic={} scale={}".format(KEY_TEXT_PREFIX, int(tonic) % 12, scale)


def instrument_from_text(text):
    """(bank, program) from the words after INSTRUMENT_TEXT_PREFIX ("bank=41 program=0"), or None."""
    try:
        bank_part, program_part = text.strip().split(" ", 1)
        bank = int(bank_part.split("=", 1)[1])
        program = int(program_part.split("=", 1)[1])
    except (ValueError, IndexError):
        return None
    if not (0 <= bank <= 16383 and 0 <= program <= 127):
        return None
    return bank, program


def key_from_text(text):
    """(tonic, scale) from the words after KEY_TEXT_PREFIX ("tonic=2 scale=Dorian"), or None."""
    from . import theory

    try:
        tonic_part, scale_part = text.strip().split(" ", 1)
        tonic = int(tonic_part.split("=", 1)[1])
        scale = scale_part.split("=", 1)[1].strip()
    except (ValueError, IndexError):
        return None
    if scale not in theory.SCALE_NAMES or not 0 <= tonic <= 11:
        return None
    return tonic, scale


def build_timeline(contents):
    """(Timeline, [(start bar, name)] for the sections, [notes about changes that moved]) for a file."""
    from .timeline import KeyChange, TempoChange, Timeline, TimeSignatureChange, format_number

    notes = []
    meters = [TimeSignatureChange(1, 4, 4)]
    timeline = Timeline(time_signatures=meters)
    for tick, numerator, denominator in sorted(contents.time_signatures, key=lambda m: m[0]):
        if not 1 <= numerator <= MAX_NUMERATOR or denominator not in VALID_DENOMINATORS:
            notes.append("a time signature of {} over {} was left out (Musician Forge allows 1 to {} beats "
                         "of 1, 2, 4, 8, 16 or 32)".format(numerator, denominator, MAX_NUMERATOR))
            continue
        bar = timeline.tick_to_bar(tick)
        if timeline.bar_to_tick(bar) != tick:
            bar += 1
            notes.append("the {}/{} time signature moved to the start of bar {}".format(numerator, denominator, bar))
        meters = [m for m in meters if m.bar != bar] + [TimeSignatureChange(bar, numerator, denominator)]
        timeline = Timeline(time_signatures=meters)
    tempos = []
    file_tempos = sorted(contents.tempos, key=lambda t: t[0])
    if file_tempos and file_tempos[0][0] > 0:
        tempos.append(TempoChange(1, 1.0, 120.0))     # a MIDI file plays at 120 until its first tempo says otherwise
    for tick, bpm in file_tempos:
        if not MIN_BPM <= bpm <= MAX_BPM:
            clamped = max(MIN_BPM, min(MAX_BPM, bpm))
            notes.append("a tempo of {} beats per minute became {}".format(format_number(round(bpm, 2)),
                                                                            format_number(clamped)))
            bpm = clamped
        bar, beat = timeline.tick_to_position(tick)
        tempos.append(TempoChange(bar, round(beat, 6), round(bpm, 4)))
    keys = []
    for item in sorted(contents.keys, key=lambda k: k[0]):
        tick, sharps, minor, exact = item
        known = key_from_text(exact) if exact else None
        tonic, scale = known if known else key_from_signature(sharps, minor)
        bar = timeline.tick_to_bar(tick)
        if timeline.bar_to_tick(bar) != tick:
            bar += 1
            notes.append("a key change moved to the start of bar {}".format(bar))
        keys = [k for k in keys if k.bar != bar] + [KeyChange(bar, tonic, scale)]
    result = Timeline(tempos=tempos or None, time_signatures=meters, keys=keys or None)
    sections = []
    for tick, text in sorted(contents.markers, key=lambda m: m[0]):
        bar = result.tick_to_bar(tick)
        if result.bar_to_tick(bar) != tick:
            bar += 1
        if sections and sections[-1][0] == bar:
            sections[-1] = (bar, text)
        else:
            sections.append((bar, text))
    return result, sections, notes


def sections_from_markers(markers, end_bar):
    """Song sections from [(start bar, name)]: the first starts at bar 1; the last runs to end_bar (the bar
    after the music ends). A name like "Section 3" that is just its number is left empty, so it keeps
    counting with the others."""
    from .song import Section

    starts = [(bar, name) for bar, name in markers if bar >= 1]
    if not starts or starts[0][0] != 1:
        starts.insert(0, (1, ""))
    sections = []
    for i, (bar, name) in enumerate(starts):
        nxt = starts[i + 1][0] if i + 1 < len(starts) else max(end_bar, bar + 1)
        if nxt <= bar:
            continue
        plain = name.strip()
        if plain.lower() == "section {}".format(len(sections) + 1):
            plain = ""
        sections.append(Section(nxt - bar, False, plain[:60]))
    return sections


def describe(contents, path=None):
    """'Night Drive.mid: 5 tracks with notes, 1234 notes, 3 tempo changes, 2 time signatures, 1 key, 4 markers.'"""
    def count(n, noun, plural=None):
        return "{} {}".format(n, noun if n == 1 else (plural or noun + "s"))

    parts = [count(len(contents.tracks), "track with notes", "tracks with notes"), count(contents.note_count, "note"),
             count(len(contents.tempos), "tempo change"), count(len(contents.time_signatures), "time signature"),
             count(len(contents.keys), "key signature"), count(len(contents.markers), "marker")]
    head = "{}: ".format(os.path.basename(path)) if path else ""
    return head + ", ".join(parts) + "."
