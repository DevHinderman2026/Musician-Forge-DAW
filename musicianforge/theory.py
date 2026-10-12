"""Music theory helpers: note names, scales, key signatures and chords.

Note names count MIDI note 60 (middle C) as C3, as many music programs do.
Spoken forms use words ("C sharp 3") because screen readers often read the
"#" symbol as "number".
"""

import re
from collections import namedtuple

SHARP_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
FLAT_NAMES = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]
SPOKEN_SHARP = ["C", "C sharp", "D", "D sharp", "E", "F", "F sharp", "G", "G sharp", "A", "A sharp", "B"]
SPOKEN_FLAT = ["C", "D flat", "D", "E flat", "E", "F", "G flat", "G", "A flat", "A", "B flat", "B"]

# Tonic names offered when choosing a key. Where both spellings are common, both are
# given; the key's own name then uses whichever its key signature needs (D flat major,
# but C sharp minor).
TONIC_NAMES = ["C", "C sharp or D flat", "D", "E flat or D sharp", "E", "F", "F sharp or G flat", "G",
               "A flat or G sharp", "A", "B flat", "B"]

MIDDLE_C = 60
OCTAVE_OFFSET = -2  # MIDI 60 // 12 = 5, and 5 - 2 = 3, so middle C is C3


# Scales, in the order they appear in menus: (name, spoken name, intervals).
SCALES = [
    ("Major", "major", (0, 2, 4, 5, 7, 9, 11)),
    ("Natural Minor", "minor", (0, 2, 3, 5, 7, 8, 10)),
    ("Harmonic Minor", "harmonic minor", (0, 2, 3, 5, 7, 8, 11)),
    ("Melodic Minor", "melodic minor", (0, 2, 3, 5, 7, 9, 11)),
    ("Dorian", "Dorian", (0, 2, 3, 5, 7, 9, 10)),
    ("Phrygian", "Phrygian", (0, 1, 3, 5, 7, 8, 10)),
    ("Phrygian Dominant", "Phrygian dominant", (0, 1, 4, 5, 7, 8, 10)),
    ("Lydian", "Lydian", (0, 2, 4, 6, 7, 9, 11)),
    ("Mixolydian", "Mixolydian", (0, 2, 4, 5, 7, 9, 10)),
    ("Locrian", "Locrian", (0, 1, 3, 5, 6, 8, 10)),
    ("Hungarian Minor", "Hungarian minor", (0, 2, 3, 6, 7, 8, 11)),
    ("Minor Pentatonic", "minor pentatonic", (0, 3, 5, 7, 10)),
    ("Major Pentatonic", "major pentatonic", (0, 2, 4, 7, 9)),
    ("Blues", "blues", (0, 3, 5, 6, 7, 10)),
    ("Chromatic", "chromatic", tuple(range(12))),
]
SCALE_NAMES = [s[0] for s in SCALES]
_SCALE_INFO = {s[0]: s for s in SCALES}

# Where each scale sits inside its "parent" major scale, in semitones above the
# parent's tonic. Used to work out the key signature (sharps or flats).
_PARENT_OFFSET = {
    "Major": 0, "Dorian": 2, "Phrygian": 4, "Lydian": 5, "Mixolydian": 7,
    "Natural Minor": 9, "Locrian": 11,
    "Harmonic Minor": 9, "Melodic Minor": 9, "Hungarian Minor": 9,
    "Phrygian Dominant": 4,   # 5th mode of harmonic minor: uses that minor key's signature
    "Major Pentatonic": 0, "Minor Pentatonic": 9, "Blues": 9, "Chromatic": 0,
}
_MINOR_LIKE = {"Natural Minor", "Harmonic Minor", "Melodic Minor", "Dorian", "Phrygian",
               "Phrygian Dominant", "Locrian", "Hungarian Minor", "Minor Pentatonic", "Blues"}
# Sharps (+) or flats (-) in each major key, by tonic pitch class.
_MAJOR_ACCIDENTALS = {0: 0, 7: 1, 2: 2, 9: 3, 4: 4, 11: 5, 6: 6, 1: -5, 8: -4, 3: -3, 10: -2, 5: -1}


def scale_intervals(scale):
    try:
        return _SCALE_INFO[scale][2]
    except KeyError:
        raise ValueError("Unknown scale: {}".format(scale)) from None


def scale_spoken_name(scale):
    return _SCALE_INFO[scale][1]


def key_accidentals(tonic, scale):
    """Key signature as a count: positive = sharps, negative = flats."""
    parent = (int(tonic) - _PARENT_OFFSET[scale]) % 12
    count = _MAJOR_ACCIDENTALS[parent]
    if count == 6 and key_is_minor(scale):
        count = -6  # E flat minor (6 flats) is written far more often than D sharp minor (6 sharps)
    return count


def key_is_minor(scale):
    return scale in _MINOR_LIKE


def key_prefers_flats(tonic, scale):
    return key_accidentals(tonic, scale) < 0


def tonic_name(tonic, scale):
    """The key's root, spelled to match its key signature: 'D flat' in D flat major, 'C sharp' in C sharp minor."""
    names = SPOKEN_FLAT if key_prefers_flats(tonic, scale) else SPOKEN_SHARP
    return names[int(tonic) % 12]


def key_name(tonic, scale):
    """Spoken key name, such as 'A minor' or 'E Phrygian'."""
    return "{} {}".format(tonic_name(tonic, scale), scale_spoken_name(scale))


def describe_accidentals(count):
    if count == 0:
        return "no sharps or flats"
    word = "sharp" if count > 0 else "flat"
    n = abs(count)
    return "{} {}{}".format(n, word, "" if n == 1 else "s")


def scale_pitch_classes(tonic, scale):
    return {(int(tonic) + i) % 12 for i in scale_intervals(scale)}


def note_octave(midi):
    return midi // 12 + OCTAVE_OFFSET


def note_name(midi, flats=False):
    """Short name such as 'C#3' (for files and compact displays)."""
    names = FLAT_NAMES if flats else SHARP_NAMES
    return "{}{}".format(names[midi % 12], note_octave(midi))


def spoken_note_name(midi, flats=False):
    """Screen-reader-friendly name such as 'C sharp 3'."""
    names = SPOKEN_FLAT if flats else SPOKEN_SHARP
    return "{} {}".format(names[midi % 12], note_octave(midi))


_LETTERS = {"c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "b": 11}
_NOTE_RE = re.compile(
    r"^\s*([a-g])\s*(#|♯|b|♭|sharp|flat)?\s*(-?\d+)\s*$", re.IGNORECASE)


def parse_note_name(text):
    """Turn 'C#3', 'Db 3', 'c sharp 3' or 'B flat -1' into a MIDI note number.

    Raises ValueError for anything that is not a valid note from 0 to 127.
    """
    match = _NOTE_RE.match(text or "")
    if not match:
        raise ValueError("'{}' is not a note name. Try something like C3, F sharp 2 or B flat 4.".format(text))
    letter, accidental, octave = match.groups()
    pitch_class = _LETTERS[letter.lower()]
    if accidental:
        acc = accidental.lower()
        if acc in ("#", "♯", "sharp"):
            pitch_class += 1
        else:
            pitch_class -= 1
    midi = (int(octave) - OCTAVE_OFFSET) * 12 + pitch_class
    if not 0 <= midi <= 127:
        raise ValueError("{} is outside the playable range (C-2 to G8).".format(text.strip()))
    return midi


def nearest_scale_note(midi, tonic, scale):
    """The closest note in the scale (ties go down)."""
    pcs = scale_pitch_classes(tonic, scale)
    for distance in range(0, 7):
        for candidate in (midi - distance, midi + distance):
            if 0 <= candidate <= 127 and candidate % 12 in pcs:
                return candidate
    return midi


# ----------------------------------------------------------------------
# chords (chord strips now, the chord track and rhythm players later)
# ----------------------------------------------------------------------
# root: pitch class 0-11. intervals: semitones above the root, starting with 0.
# flats: spell the root with a flat (B flat) rather than a sharp (A sharp).
Chord = namedtuple("Chord", "root intervals flats")

MAJOR_TRIAD = (0, 4, 7)
MINOR_TRIAD = (0, 3, 7)

# intervals: (short symbol, spoken quality)
_CHORD_QUALITIES = {
    (0, 4, 7): ("", "major"),
    (0, 3, 7): ("m", "minor"),
    (0, 3, 6): ("dim", "diminished"),
    (0, 4, 8): ("aug", "augmented"),
    (0, 4, 6): ("(b5)", "major flat five"),
    (0, 2, 7): ("sus2", "suspended second"),
    (0, 5, 7): ("sus4", "suspended fourth"),
}


def chord_scale(scale):
    """The 7-note scale a key builds its chords from.

    Pentatonic, blues and chromatic scales have no 7 chords of their own, so
    they borrow them from major or natural minor.
    """
    if len(scale_intervals(scale)) == 7:
        return scale
    return "Natural Minor" if key_is_minor(scale) else "Major"


def diatonic_chords(tonic, scale):
    """The 7 chords of a key: a triad on each scale note, from every other note of the scale."""
    tonic = int(tonic) % 12
    flats = key_prefers_flats(tonic, scale)
    steps = scale_intervals(chord_scale(scale))
    chords = []
    for degree in range(7):
        root = steps[degree]
        third = steps[(degree + 2) % 7] + (12 if degree + 2 >= 7 else 0)
        fifth = steps[(degree + 4) % 7] + (12 if degree + 4 >= 7 else 0)
        chords.append(Chord((tonic + root) % 12, (0, third - root, fifth - root), flats))
    return chords


def chord_strip_chords(tonic, scale):
    """The 8 chord strips: the key's 7 chords, then one common borrowed chord.

    Major-type keys add the major chord on the lowered 7th (B flat in C major).
    Minor-type keys add the major chord on the 5th (E major in A minor). If the
    key already has that chord, the next most common one is used instead.
    """
    tonic = int(tonic) % 12
    chords = diatonic_chords(tonic, scale)
    flats = key_prefers_flats(tonic, scale)
    if key_is_minor(scale):
        candidates = [Chord((tonic + 7) % 12, MAJOR_TRIAD, flats),    # major V: E in A minor
                      Chord((tonic + 5) % 12, MAJOR_TRIAD, flats),    # major IV: D in A minor
                      Chord((tonic + 10) % 12, MAJOR_TRIAD, True)]    # flat VII: G in A minor
    else:
        candidates = [Chord((tonic + 10) % 12, MAJOR_TRIAD, True),    # flat VII: B flat in C major
                      Chord((tonic + 5) % 12, MINOR_TRIAD, flats),    # minor iv: F minor in C major
                      Chord((tonic + 3) % 12, MAJOR_TRIAD, True)]     # flat III: E flat in C major
    have = {(c.root, c.intervals) for c in chords}
    for candidate in candidates:
        if (candidate.root, candidate.intervals) not in have:
            return chords + [candidate]
    return chords + [chords[0]]


def chord_name(chord, short=False):
    """'B flat major', 'F sharp diminished' (short: 'Bb', 'F#dim')."""
    if short:
        root = (FLAT_NAMES if chord.flats else SHARP_NAMES)[chord.root]
    else:
        root = (SPOKEN_FLAT if chord.flats else SPOKEN_SHARP)[chord.root]
    quality = _CHORD_QUALITIES.get(tuple(chord.intervals))
    if quality is None:  # an unusual chord from an exotic scale: name its notes
        names = SPOKEN_FLAT if chord.flats else SPOKEN_SHARP
        notes = [names[(chord.root + i) % 12] for i in chord.intervals]
        return "{} chord, {}".format(root, ", ".join(notes))
    return root + quality[0] if short else "{} {}".format(root, quality[1])
