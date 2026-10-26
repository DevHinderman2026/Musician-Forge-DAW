"""Musical typing: playing notes with the laptop keyboard.

Piano layout:
    A S D F G H J K L ; '   white keys, starting at C
    W E   T Y U   O P       black keys
    Z / X                   octave down / up
    C / V                   velocity down / up

Scale layout: the home row plays the song's current scale, starting on the
key's root note: A is the root, S the 2nd note of the scale, and so on. The
top row (W E T Y U O P) carries on upward where the apostrophe leaves off.
The scale follows key changes in the song, unless a scale is chosen in the
keyboard controls (it then starts on the song key's root note).

Chord strips layout: A S D F G H J K play
eight chords, the key's seven chords and then a borrowed one, each with its
root in the bass. Number keys 1 to 8 play just the bass note of each chord.

Drum layout (used automatically when the track's instrument is a drum kit):
each key plays a named drum. See DRUM_KEYS.
"""

from collections import namedtuple

from . import chords as chord_types, theory

# a chord strip you chose yourself (the Chord strips window): its quality and bass come along
CustomStrip = namedtuple("CustomStrip", "root intervals flats bass quality")

PIANO_KEYS = {
    "a": 0, "w": 1, "s": 2, "e": 3, "d": 4, "f": 5, "t": 6, "g": 7, "y": 8, "h": 9,
    "u": 10, "j": 11, "k": 12, "o": 13, "l": 14, "p": 15, ";": 16, "'": 17,
}
SCALE_KEYS = ["a", "s", "d", "f", "g", "h", "j", "k", "l", ";", "'",
              "w", "e", "t", "y", "u", "o", "p"]

# key: (General MIDI drum note, spoken name)
DRUM_KEYS = {
    "a": (36, "kick"),
    "s": (38, "snare"),
    "d": (42, "closed hi-hat"),
    "f": (46, "open hi-hat"),
    "g": (44, "hi-hat pedal"),
    "h": (45, "low tom"),
    "j": (48, "middle tom"),
    "k": (50, "high tom"),
    "l": (49, "crash cymbal"),
    ";": (51, "ride cymbal"),
    "'": (53, "ride bell"),
    "w": (37, "side stick"),
    "e": (40, "second snare"),
    "t": (41, "floor tom"),
    "y": (57, "second crash cymbal"),
    "u": (52, "china cymbal"),
    "o": (55, "splash cymbal"),
    "p": (39, "hand clap"),
    "q": (56, "cowbell"),
    "i": (54, "tambourine"),
}
DRUM_NAMES = {note: name for note, name in DRUM_KEYS.values()}

VELOCITY_STEPS = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 127]
DEFAULT_VELOCITY = 100
DEFAULT_BASE = theory.MIDDLE_C          # the A key plays middle C (C3)
LOWEST_BASE = 0                         # C-2
HIGHEST_BASE = 108                      # C7: keeps the top keys at or below 127

MODE_PIANO = "piano"
MODE_SCALE = "scale"
MODE_CHORDS = "chords"
MODES = [MODE_PIANO, MODE_SCALE, MODE_CHORDS]   # the order B cycles through
MODE_NAMES = {MODE_PIANO: "Piano", MODE_SCALE: "Scale", MODE_CHORDS: "Chord strips"}

CHORD_KEYS = ["a", "s", "d", "f", "g", "h", "j", "k"]   # chord strips 1 to 8
BASS_KEYS = ["1", "2", "3", "4", "5", "6", "7", "8"]    # the bass note of each strip

OCTAVES = list(range(theory.note_octave(LOWEST_BASE), theory.note_octave(HIGHEST_BASE) + 1))  # -2 to 7
DRUM_OCTAVE_WORDS = "The Drum layout does not use the octave"   # A is always the kick (Control+J, Z and X)


# Musician Forge's own kits put different sounds on a few notes (see forgekit.py).
DUBSTEP_KIT_PROGRAM = 100
HOUSE_KIT_PROGRAM = 101
TRAP_KIT_PROGRAM = 102
# The notes each of Musician Forge's own kits has (forgekit.build_kit lays them out; any other note is silent in
# it). Other kits (GeneralUser GS) have every drum note.
KIT_NOTES = {
    DUBSTEP_KIT_PROGRAM: frozenset((35, 36, 37, 38, 39, 40, 41, 42, 44, 45, 46, 48, 49, 50, 51, 52, 53, 54, 55, 56,
                                    57)),
    HOUSE_KIT_PROGRAM: frozenset((35, 36, 37, 38, 39, 40, 41, 42, 44, 45, 46, 48, 49, 50, 51, 53, 54, 56, 57)),
    TRAP_KIT_PROGRAM: frozenset((35, 36, 37, 38, 39, 40, 41, 42, 44, 45, 46, 48, 49, 50, 51, 54, 56, 57)),
}
KIT_DRUM_NAMES = {
    DUBSTEP_KIT_PROGRAM: {
        35: "deep 808 kick", 37: "rim snap", 40: "clap snare", 52: "impact", 54: "shaker",
        55: "riser", 56: "808 cowbell", 57: "reverse cymbal",
    },
    HOUSE_KIT_PROGRAM: {35: "soft kick", 54: "shaker", 56: "808 cowbell"},
    TRAP_KIT_PROGRAM: {35: "808 bass", 54: "shaker", 56: "808 cowbell", 57: "reverse cymbal"},
}


def drum_name(note, kit_program=None):
    """Spoken name of a drum note; kit_program picks a kit's own names where they differ."""
    special = KIT_DRUM_NAMES.get(kit_program, {})
    return special.get(note) or DRUM_NAMES.get(note) or "drum note {}".format(theory.note_name(note))


class MusicalTyping:
    """Turns key presses into notes and remembers which keys are held."""

    def __init__(self):
        self.mode = MODE_PIANO
        self.base = DEFAULT_BASE
        self.velocity = DEFAULT_VELOCITY
        self.scale = ""  # empty: follow the song's key; otherwise a scale name on the key's root note
        self._held = {}  # key character -> MIDI note that key started
        self.custom_strips = None   # a function giving the song's own chord strips (or None: the key's)

    # -- settings -------------------------------------------------------
    @property
    def octave(self):
        return theory.note_octave(self.base)

    def octave_down(self):
        if self.base - 12 >= LOWEST_BASE:
            self.base -= 12
            return True
        return False

    def octave_up(self):
        if self.base + 12 <= HIGHEST_BASE:
            self.base += 12
            return True
        return False

    def velocity_down(self):
        lower = [v for v in VELOCITY_STEPS if v < self.velocity]
        if lower:
            self.velocity = lower[-1]
            return True
        return False

    def velocity_up(self):
        higher = [v for v in VELOCITY_STEPS if v > self.velocity]
        if higher:
            self.velocity = higher[0]
            return True
        return False

    def set_octave(self, octave):
        """Octave of the A key (C3 is octave 3). Returns False if out of range."""
        base = (int(octave) - theory.OCTAVE_OFFSET) * 12
        if not LOWEST_BASE <= base <= HIGHEST_BASE:
            return False
        self.base = base
        return True

    def set_velocity(self, velocity):
        self.velocity = max(1, min(127, int(velocity)))

    def toggle_mode(self):
        """B key: piano, then scale, then chord strips, then piano again."""
        self.mode = MODES[(MODES.index(self.mode) + 1) % len(MODES)] if self.mode in MODES else MODE_PIANO
        return self.mode

    def describe_octave(self, drums=False):
        """'Octave 3, the A key plays C 3'. Only the Piano layout's A key plays C: in the Scale layout it plays the
        scale's root note, and in the Chord strips layout a chord with its bass an octave lower (the fifth review of
        25 Oct 2026: in G major the A key plays G 3, and the words said C 3). In the lowest octave a bass note would be
        below the lowest note, so the number keys play each chord's lowest note (Russell, 25 Oct 2026: "Play the
        chord's lowest note"). `drums`: the Drum layout, where the octave changes nothing
        (A is always the kick), and the words said "the A key plays C 3" (Russell, 25 Oct 2026: "Words for the
        layout"). The Octave choice and the Keyboard menu's Octave submenu say the same (octave_choices)."""
        if drums:
            return "Octave {}. {}".format(self.octave, DRUM_OCTAVE_WORDS)
        if self.mode == MODE_SCALE:
            return "Octave {}, the A key plays the scale's root note".format(self.octave)
        if self.mode == MODE_CHORDS:
            if self.octave <= OCTAVES[0]:
                return ("Octave {}, the chords play in octave {}, and the number keys play each chord's "
                        "lowest note".format(self.octave, self.octave))
            return "Octave {}, the chords play in octave {} with their bass notes in octave {}".format(
                self.octave, self.octave, self.octave - 1)
        return "Octave {}, the A key plays {}".format(self.octave, theory.spoken_note_name(self.base))

    # -- scales and chords ---------------------------------------------
    def scale_for(self, key):
        """The scale the keyboard plays: the chosen one, or the song key's own."""
        return self.scale if self.scale in theory.SCALE_NAMES else key.scale

    def chords_for(self, key):
        """The 8 chord strips: the ones you chose (the Chord strips window), or the song key's at the playhead."""
        own = self.custom_strips() if callable(self.custom_strips) else None
        if own:
            flats = theory.key_prefers_flats(key.tonic, key.scale) if key is not None else False
            return [CustomStrip(root, chord_types.ChordChange(0, root, quality).intervals(), flats, bass, quality)
                    for root, quality, bass in own]
        return theory.chord_strip_chords(key.tonic, self.scale_for(key))

    def chord_voicing(self, chord):
        """A chord's notes: its root in the bass, then the chord inside the keyboard's octave.

        Keeping every chord in the same octave makes moving between them smooth,
        the way chord strips sound.
        """
        low = getattr(chord, "bass", None)
        bass = self.base - 12 + (chord.root if low is None else low) % 12
        upper = sorted(self.base + (chord.root + i) % 12 for i in chord.intervals)
        return [n for n in [bass] + upper if 0 <= n <= 127]

    # -- notes ------------------------------------------------------------
    def notes_for_key(self, char, key=None, drums=False):
        """Every MIDI note a key plays (a chord strip plays several), or () if it plays none.

        `key` is the song's KeyChange at the playhead (needed for scale and chord strips).
        """
        char = (char or "").lower()
        if drums:
            entry = DRUM_KEYS.get(char)
            return (entry[0],) if entry else ()
        if self.mode == MODE_CHORDS and key is not None:
            if char in CHORD_KEYS:
                return tuple(self.chord_voicing(self.chords_for(key)[CHORD_KEYS.index(char)]))
            if char in BASS_KEYS:
                bass = self.chord_voicing(self.chords_for(key)[BASS_KEYS.index(char)])[:1]
                return tuple(bass)
            return ()
        if self.mode == MODE_SCALE and key is not None:
            if char not in SCALE_KEYS:
                return ()
            degree = SCALE_KEYS.index(char)
            intervals = theory.scale_intervals(self.scale_for(key))
            root = self.base + key.tonic
            note = root + 12 * (degree // len(intervals)) + intervals[degree % len(intervals)]
        else:
            if char not in PIANO_KEYS:
                return ()
            note = self.base + PIANO_KEYS[char]
        return (note,) if 0 <= note <= 127 else ()

    def chord_for_key(self, char, key):
        """The chord a chord-strip key or number key plays, or None."""
        char = (char or "").lower()
        if self.mode != MODE_CHORDS or key is None:
            return None
        for keys in (CHORD_KEYS, BASS_KEYS):
            if char in keys:
                return self.chords_for(key)[keys.index(char)]
        return None

    def note_for_key(self, char, key=None, drums=False):
        """The first note a key plays, or None (kept for single-note layouts)."""
        notes = self.notes_for_key(char, key, drums)
        return notes[0] if notes else None

    def press(self, char, key=None, drums=False):
        """A key went down. Returns the note to start, or None.

        Holding a key down (keyboard auto-repeat) does not restart the note.
        """
        char = (char or "").lower()
        if char in self._held:
            return None
        note = self.note_for_key(char, key, drums)
        if note is None:
            return None
        self._held[char] = note
        return note

    def release(self, char):
        """A key came up. Returns the note to stop, or None."""
        return self._held.pop((char or "").lower(), None)

    def release_all(self):
        """Forget every held key (for example when the window loses focus)."""
        notes = list(self._held.values())
        self._held.clear()
        return notes

    def held_notes(self):
        return list(self._held.values())


def octave_choices(mode=MODE_PIANO, drums=False):
    """The Octave choice's items (and the Keyboard menu's Octave submenu's), one for each of OCTAVES in order:
    what the octave means in this layout, in the words of describe_octave (Control+J and the Status box), made short.
    Until 25 Oct 2026 every layout said "3 (the A key plays C 3)", true only in the Piano layout (Russell: "Words
    for the layout")."""
    words = []
    for octave in OCTAVES:
        if drums:
            meaning = "the Drum layout does not use the octave"
        elif mode == MODE_SCALE:
            meaning = "the A key plays the scale's root note"
        elif mode == MODE_CHORDS:
            meaning = ("chords in octave {}, number keys play the lowest note".format(octave) if octave <= OCTAVES[0]
                       else "chords in octave {}, bass notes in octave {}".format(octave, octave - 1))
        else:
            meaning = "the A key plays C {}".format(octave)
        words.append("{} ({})".format(octave, meaning))
    return words


def is_note_key(char, drums=False, mode=MODE_PIANO):
    char = (char or "").lower()
    if drums:
        return char in DRUM_KEYS
    if mode == MODE_SCALE:
        return char in SCALE_KEYS
    if mode == MODE_CHORDS:
        return char in CHORD_KEYS or char in BASS_KEYS
    return char in PIANO_KEYS


def strip_name(chord):
    """'C major', 'A minor with E in the bass', 'G suspended fourth'."""
    if isinstance(chord, CustomStrip):
        return chord_types.name(chord_types.ChordChange(0, chord.root, chord.quality, chord.bass), chord.flats)
    return theory.chord_name(chord)


def describe_chord_strips(chords, lowest=False):
    """'A: C major. S: D minor. ...' for the 8 strips, then their bass keys. lowest: the lowest octave, where the
    number keys play each chord's lowest note instead of a bass note below it (it said "the bass notes" there too, which
    went against the words just before it; the review of the guide, 26 Oct 2026)."""
    parts = ["{}: {}".format(char.upper(), strip_name(chord)) for char, chord in zip(CHORD_KEYS, chords)]
    if lowest:
        return ". ".join(parts) + ". Number keys 1 to 8 play each chord's lowest note."
    return ". ".join(parts) + ". Number keys 1 to 8 play the bass notes of these chords."


def layout_help(drums=False, mode=MODE_PIANO):
    """Text describing the current layout, for the Help menu."""
    if drums:
        lines = ["Drum layout. Each key plays one drum:"]
        order = ["a", "s", "d", "f", "g", "h", "j", "k", "l", ";", "'", "q", "w", "e", "t", "y", "u", "i", "o", "p"]
        names = {";": "semicolon", "'": "apostrophe"}
        for char in order:
            note, name = DRUM_KEYS[char]
            lines.append("{}: {}".format(names.get(char, char.upper()), name))
        for title, program in (("Forge Dubstep Kit", DUBSTEP_KIT_PROGRAM), ("Forge House Kit", HOUSE_KIT_PROGRAM),
                               ("Forge Trap Kit", TRAP_KIT_PROGRAM)):
            special = KIT_DRUM_NAMES[program]
            changed = [(char, special[DRUM_KEYS[char][0]]) for char in order if DRUM_KEYS[char][0] in special]
            if changed:
                lines.append("")
                lines.append("{}, one of Musician Forge's own kits, plays different sounds on these keys:".format(title))
                lines += ["{}: {}".format(names.get(char, char.upper()), name) for char, name in changed]
        return "\n".join(lines)
    if mode == MODE_SCALE:
        return ("Scale layout. The home row plays the song's scale from its root note: "
                "A is the root, S is the second note, D the third, and so on through apostrophe. "
                "The top row W E T Y U O P continues upward from there. "
                "The scale follows key changes in the song, unless you choose a scale in the keyboard controls. "
                "Z and X change octave.")
    if mode == MODE_CHORDS:
        return ("Chord strips layout. A S D F G H J and K play eight chords: the seven chords of the song's key, "
                "then one borrowed chord (B flat in C major, E major in A minor). Each chord has its root in the bass. "
                "Number keys 1 to 8 play just the bass note of each chord. The chords follow key changes. "
                "Z and X change octave. C and V change velocity. Control+J says which chord is on each key.")
    return ("Piano layout. A S D F G H J K L semicolon and apostrophe are white keys starting at C. "
            "W E T Y U O and P are the black keys above them. "
            "Z and X change octave. C and V change velocity.")
