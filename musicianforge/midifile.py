"""Standard MIDI Files: export songs for other music programs (and read them back to check).

Export writes a type 1 MIDI file at 960 ticks per quarter note:
- Track 1 (the "conductor") holds the song title, every tempo change, every
  time signature change, every key signature change, and a marker at the
  start of each song section: only what other programs put on their own
  tempo, signature and marker tracks, so they make no track of it.
- Then one track per Musician Forge track, with its name, instrument (program
  change), volume, pan and notes. Drum kit tracks use MIDI channel 10, the
  General MIDI drum channel; other tracks use the remaining channels.
- Instruments are written as their General MIDI numbers and names, so other
  programs choose the right kind of sound: the guitar packs (program 0 on
  banks 40 and 41 here) are a Distortion Guitar, acoustic drum kits the
  Standard kit, electronic kits the Electronic or Analog (808) kit. A text
  event keeps the exact instrument, for Musician Forge's own import.
- Drum tracks: the splash and the china are written as the crash, and the
  second ride as the ride, since other programs' kits often lack them.
- The chord track, if the song has one, is a silent track of its own (Russell,
  10 Oct 2026): each chord held as notes and named in a lyric event.
- No note sounds after the music ends: the chord track stops with the last
  note (or recording). Sections, tempos and keys all come across.

MIDI key signatures can only say "major" or "minor" plus a number of sharps
or flats, so modes such as Phrygian are written with their correct sharps or
flats and marked minor or major by their character.
"""

import os
import struct

from . import drummap, midiimport, theory
from .paths import replace_file
from .timeline import PPQ

DRUM_CHANNEL = 9
MELODIC_CHANNELS = [c for c in range(16) if c != DRUM_CHANNEL]

GM_NAMES = (
    "Acoustic Grand Piano", "Bright Acoustic Piano", "Electric Grand Piano", "Honky-tonk Piano", "Electric Piano 1",
    "Electric Piano 2", "Harpsichord", "Clavi", "Celesta", "Glockenspiel", "Music Box", "Vibraphone", "Marimba",
    "Xylophone", "Tubular Bells", "Dulcimer", "Drawbar Organ", "Percussive Organ", "Rock Organ", "Church Organ",
    "Reed Organ", "Accordion", "Harmonica", "Tango Accordion", "Acoustic Guitar (nylon)", "Acoustic Guitar (steel)",
    "Electric Guitar (jazz)", "Electric Guitar (clean)", "Electric Guitar (muted)", "Overdriven Guitar",
    "Distortion Guitar", "Guitar Harmonics", "Acoustic Bass", "Electric Bass (finger)", "Electric Bass (pick)",
    "Fretless Bass", "Slap Bass 1", "Slap Bass 2", "Synth Bass 1", "Synth Bass 2", "Violin", "Viola", "Cello",
    "Contrabass", "Tremolo Strings", "Pizzicato Strings", "Orchestral Harp", "Timpani", "String Ensemble 1",
    "String Ensemble 2", "SynthStrings 1", "SynthStrings 2", "Choir Aahs", "Voice Oohs", "Synth Voice",
    "Orchestra Hit", "Trumpet", "Trombone", "Tuba", "Muted Trumpet", "French Horn", "Brass Section", "SynthBrass 1",
    "SynthBrass 2", "Soprano Sax", "Alto Sax", "Tenor Sax", "Baritone Sax", "Oboe", "English Horn", "Bassoon",
    "Clarinet", "Piccolo", "Flute", "Recorder", "Pan Flute", "Blown Bottle", "Shakuhachi", "Whistle", "Ocarina",
    "Lead 1 (square)", "Lead 2 (sawtooth)", "Lead 3 (calliope)", "Lead 4 (chiff)", "Lead 5 (charang)",
    "Lead 6 (voice)", "Lead 7 (fifths)", "Lead 8 (bass + lead)", "Pad 1 (new age)", "Pad 2 (warm)",
    "Pad 3 (polysynth)", "Pad 4 (choir)", "Pad 5 (bowed)", "Pad 6 (metallic)", "Pad 7 (halo)", "Pad 8 (sweep)",
    "FX 1 (rain)", "FX 2 (soundtrack)", "FX 3 (crystal)", "FX 4 (atmosphere)", "FX 5 (brightness)",
    "FX 6 (goblins)", "FX 7 (echoes)", "FX 8 (sci-fi)", "Sitar", "Banjo", "Shamisen", "Koto", "Kalimba", "Bag pipe",
    "Fiddle", "Shanai", "Tinkle Bell", "Agogo", "Steel Drums", "Woodblock", "Taiko Drum", "Melodic Tom",
    "Synth Drum", "Reverse Cymbal", "Guitar Fret Noise", "Breath Noise", "Seashore", "Bird Tweet",
    "Telephone Ring", "Helicopter", "Applause", "Gunshot",
)
DRUM_BANKS = (128, 120)          # GeneralUser GS's kits, and its copies of them on bank 120 (instruments.py)
GUITAR_PACK_BANKS = (40, 41)     # the FreePats distorted guitar packs (packs.py): program 0 on their own banks
DISTORTION_GUITAR = 30
# General MIDI 2 drum kit numbers. Acoustic kits are written as the Standard kit, the one every program knows as
# acoustic (Russell, 10 Oct 2026: another program played the Power kit, number 16, as an electronic kit).
STANDARD_KIT, ELECTRONIC_KIT, ANALOG_KIT, ORCHESTRA_KIT, SFX_KIT = 0, 24, 25, 48, 56
KIT_NAMES = {STANDARD_KIT: "Standard Kit", ELECTRONIC_KIT: "Electronic Kit", ANALOG_KIT: "Analog Kit (808)",
             ORCHESTRA_KIT: "Orchestra Kit", SFX_KIT: "SFX Kit"}
GM_KITS = {
    24: ELECTRONIC_KIT,          # Electronic
    25: ANALOG_KIT,              # 808/909
    26: ELECTRONIC_KIT,          # Dance (909)
    48: ORCHESTRA_KIT,           # Orchestral
    56: SFX_KIT,                 # SFX
    100: ELECTRONIC_KIT,         # Forge Dubstep Kit (forgekit.py)
    101: ELECTRONIC_KIT,         # Forge House Kit (909-style)
    102: ANALOG_KIT,             # Forge Trap Kit (808-style)
}                                # every other kit (Standard 1 to 3, Room, Power, Jazz, Brush, CM-64): Standard
INSTRUMENT_TEXT_PREFIX = midiimport.INSTRUMENT_TEXT_PREFIX


def is_kit(instrument):
    return instrument.bank in DRUM_BANKS


def general_midi(instrument):
    """(program, name) of the General MIDI instrument another program should use for this one."""
    if is_kit(instrument):
        kit = GM_KITS.get(instrument.program, STANDARD_KIT)
        return kit, KIT_NAMES[kit]
    program = DISTORTION_GUITAR if instrument.bank in GUITAR_PACK_BANKS else instrument.program & 0x7F
    return program, GM_NAMES[program]


class MidiFileError(Exception):
    pass


# ----------------------------------------------------------------------
# low-level helpers
# ----------------------------------------------------------------------
def encode_varlen(value):
    if value < 0:
        raise ValueError("delta times cannot be negative")
    out = bytearray([value & 0x7F])
    value >>= 7
    while value:
        out.insert(0, 0x80 | (value & 0x7F))
        value >>= 7
    return bytes(out)


def decode_varlen(data, pos):
    value = 0
    for _ in range(4):
        byte = data[pos]
        pos += 1
        value = (value << 7) | (byte & 0x7F)
        if not byte & 0x80:
            return value, pos
    raise MidiFileError("variable-length number is too long")


def _meta(kind, payload):
    return bytes([0xFF, kind]) + encode_varlen(len(payload)) + payload


def _chunk(kind, payload):
    return kind + struct.pack(">I", len(payload)) + payload


def _track_bytes(events, end_tick=None):
    """events: list of (tick, order, raw_bytes). Sorted, delta-encoded, ended (at end_tick, if later)."""
    events = sorted(events, key=lambda e: (e[0], e[1]))
    out = bytearray()
    last = 0
    for tick, _order, raw in events:
        out += encode_varlen(tick - last) + raw
        last = tick
    out += encode_varlen(max(0, (end_tick or 0) - last)) + _meta(0x2F, b"")
    return bytes(out)


def _text(value):
    """Words for a name or text event. Windows' own letters (cp1252) first, so a curly apostrophe or a dash survives
    (23 Oct 2026: "Don’t Stop" came back as "Don?t Stop"); a letter it lacks goes as Latin-1, or as "?"."""
    out = bytearray()
    for char in str(value):
        for encoding in ("cp1252", "latin-1"):
            try:
                out += char.encode(encoding)
                break
            except UnicodeEncodeError:
                continue
        else:
            out += b"?"
    return bytes(out[:127])


# ----------------------------------------------------------------------
# export
# ----------------------------------------------------------------------
def tempo_microseconds(bpm):
    return int(round(60_000_000 / float(bpm)))


def midi_places(song, notes_by_track=None):
    """{track id: (MIDI port, channel)} for each instrument track that plays notes: drums on channel 10, the others
    on the other 15 channels. Since 23 Oct 2026 a track without notes takes no channel (it used to, so an empty
    track could take a channel another track then shared), and from the 16th instrument track on the tracks go on
    a second MIDI port (a third from the 31st, and so on), so no two share a channel on one port. A program that
    ignores ports plays them on the channels of the first 15 (see ports_used). A second drum track goes on channel 10
    of the second port, a third on the third, and so on (the review of 25 Oct 2026: they all shared channel 10 of the
    first port, so the last one's kit, volume and pan, and either one's automation, went for all of them); General
    MIDI has only the one drum channel, so a program that ignores ports still plays them all on channel 10."""
    places = {}
    melodic_index = 0
    drum_index = 0
    for track in song.tracks:
        if getattr(track, "is_audio", False):
            continue  # recordings cannot go into a MIDI file
        if not (notes_by_track or {}).get(track.id, track.notes):
            continue
        if is_kit(track.instrument):
            places[track.id] = (drum_index, DRUM_CHANNEL)
            drum_index += 1
        else:
            places[track.id] = (melodic_index // len(MELODIC_CHANNELS),
                                MELODIC_CHANNELS[melodic_index % len(MELODIC_CHANNELS)])
            melodic_index += 1
    return places


def channel_for_tracks(song, notes_by_track=None):
    """MIDI channel for each track id that plays notes (see midi_places)."""
    return {tid: channel for tid, (_port, channel) in midi_places(song, notes_by_track).items()}


def ports_used(song, notes_by_track=None):
    """How many MIDI ports an export of the song uses (more than 1: more than 15 instrument tracks play notes)."""
    return 1 + max((port for port, _channel in midi_places(song, notes_by_track).values()), default=0)


def song_to_midi_bytes(song, notes_by_track=None, include_chords=True):
    """notes_by_track: {track id: notes} a track really plays (loops and rhythm players included)."""
    tl = song.timeline
    conductor = [(0, 0, _meta(0x03, _text(song.title or "Musician Forge song")))]
    for ts in tl.time_signatures:
        tick = tl.bar_to_tick(ts.bar)
        dd = ts.denominator.bit_length() - 1
        clocks = 24 * 4 // ts.denominator
        conductor.append((tick, 1, _meta(0x58, bytes([ts.numerator, dd, max(1, clocks), 8]))))
    key_texts = []
    exact_keys = []
    for key in tl.keys:
        tick = tl.bar_to_tick(key.bar)
        sf = theory.key_accidentals(key.tonic, key.scale)
        mi = 1 if theory.key_is_minor(key.scale) else 0
        conductor.append((tick, 2, _meta(0x59, struct.pack(">bB", sf, mi))))
        # the exact key too (a key signature cannot say "Dorian"), for Musician Forge's own import. It goes in a
        # track of music, not here: this track holds only what other programs put on their tempo, signature and
        # marker tracks (Russell, 10 Oct 2026: a text here gave another program an extra, empty track at the top)
        key_texts.append((tick, 2, _meta(0x01, _text(midiimport.key_text(key.tonic, key.scale)))))
        exact_keys.append((tick, key.tonic, key.scale))
    for tempo in tl.tempos:
        tick = tl.position_to_tick(tempo.bar, tempo.beat)
        conductor.append((tick, 3, _meta(0x51, tempo_microseconds(tempo.bpm).to_bytes(3, "big"))))
    for index in range(len(getattr(song, "sections", []))):
        start_bar, _end = song.section_bounds(index)
        conductor.append((tl.bar_to_tick(start_bar), 4, _meta(0x06, _text(song.section_name(index)))))
    # the conductor track ends where the song ends, so the last section keeps its length when imported again
    end = song.song_end_tick() if hasattr(song, "song_end_tick") else None
    chunks = [_track_bytes(conductor, end)]

    places = midi_places(song, notes_by_track)
    channels = {tid: channel for tid, (_port, channel) in places.items()}
    several_ports = any(port for port, _channel in places.values())
    played = {t.id: (notes_by_track or {}).get(t.id, t.notes) for t in song.tracks if t.id in channels}
    # the exact keys ride along in the track that plays longest, so they never make a track longer than its music
    host = max((tid for tid in played if played[tid]), key=lambda tid: max(n.tick + n.length for n in played[tid]),
               default=None)
    if host is None:
        conductor.extend(key_texts)
        chunks[0] = _track_bytes(conductor, end)
    for track in song.tracks:
        if getattr(track, "is_audio", False):
            continue  # audio tracks
        events = [(0, 0, _meta(0x03, _text(track.name)))]
        inst = track.instrument
        program, gm_name = general_midi(inst)
        events.append((0, 0, _meta(0x04, _text(gm_name))))
        events.append((0, 0, _meta(0x01, _text(instrument_text(inst.bank, inst.program)))))
        if track.id not in channels:
            # no notes: its name and instrument only. It takes no channel, so it cannot change the instrument,
            # volume or pan of a track that plays (23 Oct 2026)
            chunks.append(_track_bytes(events))
            continue
        port, ch = places[track.id]
        if several_ports:
            events.append((0, 0, _meta(0x21, bytes([port]))))            # MIDI port: 16 channels per port
        if not is_kit(inst):
            events.append((0, 1, bytes([0xB0 | ch, 0, 0])))            # General MIDI's own bank
            events.append((0, 2, bytes([0xB0 | ch, 32, 0])))
        events.append((0, 3, bytes([0xC0 | ch, program])))
        events.append((0, 4, bytes([0xB0 | ch, 7, volume_to_cc(track.volume)])))
        events.append((0, 5, bytes([0xB0 | ch, 10, pan_to_cc(track.pan)])))
        for lane in getattr(track, "automation", []):        # volume and pan automation as controller changes
            if lane.get("on", True) and lane["points"] and lane["target"] in ("volume", "pan"):
                controller, convert, order = ((7, volume_to_cc, 4) if lane["target"] == "volume"
                                              else (10, pan_to_cc, 5))
                for tick, value in automation_steps(lane["points"]):
                    events.append((tick, order, bytes([0xB0 | ch, controller, convert(value)])))
        track_end = 0
        notes = (notes_by_track or {}).get(track.id, track.notes)
        if is_kit(inst):
            # the cymbals other programs' kits most often lack go out as the crash and the ride, so they sound
            # in every program (Russell, 10 Oct 2026: a splash was silent in another program) (drummap.py)
            notes = [type(n)(n.tick, n.length, drummap.for_export(n.pitch), n.velocity) for n in notes]
        for note in end_at_restrike(notes):
            # note-offs (order 6) sort before note-ons (order 7) on the same tick
            events.append((note.tick + note.length, 6, bytes([0x80 | ch, note.pitch, 64])))
            events.append((note.tick, 7, bytes([0x90 | ch, note.pitch, note.velocity])))
            track_end = max(track_end, note.tick + note.length)
        if track.id == host:
            for (tick, order, raw), (_t, tonic, scale) in zip(key_texts, exact_keys):
                if tick < track_end or tick == 0:
                    events.append((tick, order, raw))
                else:
                    # a key change after the last note (23 Oct 2026: its mode was lost): written before the music
                    # ends, so the track is no longer than its music, saying which key signature it belongs to
                    events.append((max(0, track_end - 1), order,
                                   _meta(0x01, _text(midiimport.key_text(tonic, scale, at=tick)))))
        if any(e[0] < 0 for e in events):
            raise MidiFileError("Track '{}' has notes before the start of the song".format(track.name))
        chunks.append(_track_bytes(events))

    if include_chords and getattr(song, "chords", None):
        # no note after the music ends (Russell, 10 Oct 2026: a chord where the song ended played on its own)
        port_zero = {ch for port, ch in places.values() if port == 0}
        chunks.append(chord_track_events(song, port_zero, music_end(song, notes_by_track) or end,
                                         port=0 if several_ports else None))
    header = struct.pack(">HHH", 1, len(chunks), PPQ)
    return _chunk(b"MThd", header) + b"".join(_chunk(b"MTrk", c) for c in chunks)


CHORD_TRACK_NAME = midiimport.CHORD_TRACK_NAME
CHORD_TEXT_PREFIX = midiimport.CHORD_TEXT_PREFIX


def chord_track_events(song, used_channels, end=None, port=None):
    """The chord track as a MIDI track of its own (Russell, 10 Oct 2026). MIDI has no chord events, so each
    chord is held as notes (the bass note low, the chord above middle C) and named in a lyric event, which
    other programs show beside the notes; a text event beside it lets Musician Forge's own import bring
    the chord track back exactly. It is on a channel no other track uses (none free: names only), with its
    volume all the way down, since a chord track guides and does not play (Russell chose "Silent"). No chord
    sounds after the music ends: a chord there is left out, and the last one stops with the music."""
    from . import chords

    free = [c for c in MELODIC_CHANNELS if c not in used_channels]
    ch = free[-1] if free else None
    flats = False
    events = [(0, 0, _meta(0x03, _text(CHORD_TRACK_NAME)))]
    if port is not None:
        events.append((0, 0, _meta(0x21, bytes([port]))))           # the export uses several MIDI ports
    if ch is not None:
        events.append((0, 0, _meta(0x04, _text(GM_NAMES[0]))))
        events.append((0, 3, bytes([0xC0 | ch, 0])))                  # a piano, if someone turns it up
        events.append((0, 4, bytes([0xB0 | ch, 7, 0])))               # silent, like Musician Forge's chord track
    changes = chords.sort(song.chords)
    stop_at = end if end else max([c.tick for c in changes] + [0]) + 4 * PPQ
    for k, change in enumerate(changes):
        start = change.tick
        if start >= stop_at:
            break                                     # a chord where the music has ended is not played
        stop = min(changes[k + 1].tick, stop_at) if k + 1 < len(changes) else stop_at
        if stop <= start:
            continue
        events.append((start, 1, _meta(0x05, _text(chords.short_name(change, flats)))))
        events.append((start, 2, _meta(0x01, _text(CHORD_TEXT_PREFIX + " ".join(
            "" if v is None else str(v) for v in change.to_list())))))
        if ch is None:
            continue
        pitches = sorted({36 + change.bass_class()} | {60 + change.root + i for i in change.intervals() if i < 24})
        for pitch in pitches:
            pitch = max(0, min(127, pitch))
            events.append((stop, 6, bytes([0x80 | ch, pitch, 64])))
            events.append((start, 7, bytes([0x90 | ch, pitch, 70])))
    return _track_bytes(events, end)


def music_end(song, notes_by_track=None):
    """Where the music ends: the end of the last note any track plays, or of the last recording (0 if none)."""
    from . import arrangement

    notes = notes_by_track if notes_by_track is not None else {t.id: t.notes for t in song.tracks}
    end = max((n.tick + n.length for track_notes in notes.values() for n in track_notes), default=0)
    for track in song.tracks:
        if not getattr(track, "is_audio", False):
            continue
        for i, region in enumerate(track.regions):
            end = max(end, region.end_tick(song.timeline))
            if region.loops > 1:
                end = max(end, arrangement.audio_region_repeats(track, i, song.timeline, 0)[1])
    return end


def instrument_text(bank, program):
    """The text event that keeps a track's exact instrument, for Musician Forge's own import."""
    return "{}bank={} program={}".format(INSTRUMENT_TEXT_PREFIX, int(bank), int(program))


def end_at_restrike(notes):
    """The notes as Musician Forge plays them: one that is still sounding when the same pitch is struck again ends
    there (of two starting together, the longer one plays), so another program plays the file the same way."""
    from .song import Note

    ordered = sorted(notes, key=lambda n: (n.pitch, n.tick, n.length))
    result = []
    for k, note in enumerate(ordered):
        nxt = ordered[k + 1] if k + 1 < len(ordered) else None
        if nxt is not None and nxt.pitch == note.pitch and note.end > nxt.tick:
            if nxt.tick == note.tick:
                continue                                     # the same note twice: the longer one plays
            note = Note(note.tick, nxt.tick - note.tick, note.pitch, note.velocity)
        result.append(note)
    result.sort(key=lambda n: (n.tick, n.pitch))
    return result


def export_midi(song, path, notes_by_track=None):
    data = song_to_midi_bytes(song, notes_by_track)
    tmp = path + ".tmp"
    try:
        with open(tmp, "wb") as fh:
            fh.write(data)
        replace_file(tmp, path)
    except BaseException:
        # a full disk, or the old file held open by another program: the old file stays as it was, and no half-made
        # file is left beside it (the review of 25 Oct 2026: Song.mid.tmp was left behind)
        _remove_quietly(tmp)
        raise
    return len(data)


def _remove_quietly(path):
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def automation_steps(points, step=PPQ // 4):
    """(tick, value) for a lane: each point, and every sixteenth note along a glide."""
    from . import automation

    result = [(0, points[0][1])]
    for i, (tick, value, glide) in enumerate(points):
        result.append((tick, value))
        if glide and i + 1 < len(points):
            for t in range(tick + step, points[i + 1][0], step):
                result.append((t, automation.value_at(points, t)))
    cleaned, last = [], None
    for tick, value in sorted(result, key=lambda item: item[0]):
        key = round(value, 3)
        if key != last:
            cleaned.append((tick, value))
            last = key
    return cleaned


def volume_to_cc(percent):
    return max(0, min(127, int(round(percent * 127 / 100.0))))


def pan_to_cc(pan):
    return max(0, min(127, int(round(64 + pan * 63 / 100.0))))


# ----------------------------------------------------------------------
# reading (used to verify exports, and for importing later)
# ----------------------------------------------------------------------
class MidiEvent:
    __slots__ = ("tick", "kind", "channel", "data")

    def __init__(self, tick, kind, channel, data):
        self.tick, self.kind, self.channel, self.data = tick, kind, channel, data

    def __repr__(self):
        return "MidiEvent({}, {!r}, {}, {!r})".format(self.tick, self.kind, self.channel, self.data)


def read_midi_bytes(data):
    """Parse a MIDI file. Returns (format, division, [list of MidiEvent per track])."""
    if data[:4] != b"MThd":
        raise MidiFileError("Not a MIDI file")
    length = struct.unpack(">I", data[4:8])[0]
    fmt, ntracks, division = struct.unpack(">HHH", data[8:14])
    pos = 8 + length
    tracks = []
    while pos < len(data) and len(tracks) < ntracks:
        kind = data[pos:pos + 4]
        size = struct.unpack(">I", data[pos + 4:pos + 8])[0]
        body = data[pos + 8:pos + 8 + size]
        pos += 8 + size
        if kind == b"MTrk":
            tracks.append(_parse_track(body))
    return fmt, division, tracks


def _parse_track(body):
    events = []
    pos, tick, status = 0, 0, None
    while pos < len(body):
        delta, pos = decode_varlen(body, pos)
        tick += delta
        byte = body[pos]
        if byte == 0xFF:
            kind = body[pos + 1]
            size, pos = decode_varlen(body, pos + 2)
            payload = body[pos:pos + size]
            pos += size
            events.append(MidiEvent(tick, ("meta", kind), None, payload))
            if kind == 0x2F:
                break
            continue
        if byte in (0xF0, 0xF7):
            size, pos = decode_varlen(body, pos + 1)
            pos += size
            continue
        if byte & 0x80:
            status = byte
            pos += 1
        elif status is None:
            raise MidiFileError("running status without a status byte")
        high, ch = status & 0xF0, status & 0x0F
        nbytes = 1 if high in (0xC0, 0xD0) else 2
        args = tuple(body[pos:pos + nbytes])
        pos += nbytes
        names = {0x80: "note_off", 0x90: "note_on", 0xA0: "aftertouch", 0xB0: "cc",
                 0xC0: "program", 0xD0: "pressure", 0xE0: "pitch_bend"}
        kind = names[high]
        if kind == "note_on" and args[1] == 0:
            kind = "note_off"
        events.append(MidiEvent(tick, kind, ch, args))
    return events


def notes_from_events(events):
    """Pair note-on and note-off events into (tick, length, pitch, velocity, channel)."""
    open_notes = {}
    result = []
    for ev in events:
        if ev.kind == "note_on":
            open_notes.setdefault((ev.channel, ev.data[0]), []).append((ev.tick, ev.data[1]))
        elif ev.kind == "note_off":
            stack = open_notes.get((ev.channel, ev.data[0]))
            if stack:
                start, vel = stack.pop(0)
                result.append((start, ev.tick - start, ev.data[0], vel, ev.channel))
    result.sort()
    return result
