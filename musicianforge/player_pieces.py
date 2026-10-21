"""The pieces of a rhythm player, each with its own settings (version 0.9.2; Russell, 8 Oct 2026: "drummers of
every style need a way to change individual kit pieces: add, move or remove cymbals, choose whether there are
crashes and which variation of each cymbal plays, and so on", and the same for the other four players).

Anvil's kit is split into ten pieces (kick, snare, clap or rim, closed hi-hat, open hi-hat, toms, crash cymbals,
ride, congas and bongos, other percussion). Bellows, Ember, Spark and Hammer each have one piece, their part.
A piece's settings are stored in the region with the player's other settings ("pieces": only what differs from
the default is kept), so the same settings always give the same notes, and undo, redo and reopening are exact.

Every piece has a Pattern: the rhythm the chosen variation gives it, another variation's, or one of a few common
ones (a drum piece can also be given none). A piece can be turned off, made busier or simpler (complexity), louder
or softer, and some have their own extras: half or double time (kick and snare), ghost notes and a rim click
(snare), how open the hi-hat is, whether the toms play in fills, when a crash comes and which cymbal it is, and
the ride's bell on the beats. The one-row parts of the other players have the chord track on or off, an octave, a
note length, the root only, and passing notes into the next chord.

Hand-made steps: in the Step pattern view a piece's steps are set by hand (one to four bars, repeated through the
region). The view starts from what the piece plays (without fills), so changing one step changes only that step:
a drum step keeps every sound on it (a conga and a bongo together), and a part's step starts as "as the style plays
it", which plays the style's own notes on that step. Hand-made steps stay through Reforge; changing the variation
resets them after a warning (Russell, 11:57 PM), and Control+Z brings them back.

This module holds the data and the words; players.py applies the settings while it plays.
"""

from dataclasses import dataclass

from . import drummap, keyboard_map, player_variations as pv
from .timeline import MAX_NUMERATOR, VALID_DENOMINATORS
from .player_variations import (BONGO_HIGH, BONGO_LOW, CHINA, CLAP, CLAVES, CONGA_LOW, CONGA_MUTE, CONGA_OPEN,
                                COWBELL, CRASH, CRASH2, HAT, KICK, KICK2, MARACAS, OPEN_HAT, PEDAL, RIDE, RIDE_BELL,
                                RIM, SHAKER, SNARE, SNARE2, SPLASH, TAMBOURINE, TOM_FLOOR, TOM_HIGH, TOM_LOW,
                                TOM_MID)

RIDE2 = 59                       # the second ride cymbal (General MIDI "Ride Cymbal 2")
MAX_STEP_BARS = 4
# the sixteenths in the longest bar Musician Forge allows (32 whole notes, 32/1 time: 512). Before the review of
# 9 Oct 2026 this was 64, so in a long bar (32/4 has 128) a hand-made step past the 64th was dropped without a word,
# and so were the style's own hits there once any step was changed
MAX_STEPS_IN_BAR = MAX_NUMERATOR * 16 // min(VALID_DENOMINATORS)


@dataclass(frozen=True)
class Piece:
    key: str
    name: str
    voices: tuple                # the drum notes it plays (empty for a part)
    kind: str = ""               # which extras it has


DRUM_PIECES = (
    Piece("kick", "Kick", (KICK, KICK2), "kick"),
    Piece("snare", "Snare", (SNARE, SNARE2), "snare"),
    Piece("clap", "Clap or rim", (CLAP, RIM)),
    Piece("hat", "Closed hi-hat", (HAT, PEDAL), "hat"),
    Piece("open_hat", "Open hi-hat", (OPEN_HAT,)),
    Piece("toms", "Toms", (TOM_FLOOR, TOM_LOW, TOM_MID, TOM_HIGH), "toms"),
    Piece("crash", "Crash cymbals", (CRASH, CRASH2, SPLASH, CHINA), "crash"),
    Piece("ride", "Ride", (RIDE, RIDE_BELL, RIDE2), "ride"),
    Piece("hand_drums", "Congas and bongos", (CONGA_OPEN, CONGA_MUTE, CONGA_LOW, BONGO_HIGH, BONGO_LOW)),
    Piece("percussion", "Shaker, tambourine, cowbell and claves", (SHAKER, TAMBOURINE, COWBELL, MARACAS, CLAVES)),
)
PART = Piece("part", "Part", (), "part")
PIECE_BY_KEY = {p.key: p for p in DRUM_PIECES + (PART,)}
VOICE_PIECE = {voice: piece.key for piece in DRUM_PIECES for voice in piece.voices}

# names for the notes the drum layout does not name (the Forge kits' own names come from keyboard_map)
NOTE_NAMES = {35: "second kick", 40: "second snare", 59: "second ride", 60: "high bongo", 61: "low bongo",
              62: "muted high conga", 63: "open high conga", 64: "low conga", 70: "maracas", 75: "claves",
              82: "shaker"}

WHEN = (("start_and_fills", "where the region starts and after fills"),
        ("fills", "after fills only"),
        ("sections", "at the start of each section and after fills"),
        ("every_2", "every 2 bars"), ("every_4", "every 4 bars"), ("every_8", "every 8 bars"),
        ("accents", "on the followed track's strongest hits"),
        ("never", "never (only where the pattern has them)"))
WHICH = (("crash1", (CRASH,)), ("crash2", (CRASH2,)), ("alternate", (CRASH, CRASH2)), ("splash", (SPLASH,)),
         ("china", (CHINA,)))
# Intensity is how hard the drummer plays, never how much (Russell, 9 Oct 2026); played softly the snare goes to the
# rim (a cross-stick) and played hard the hi-hat opens, unless these say otherwise.
RIM_AT = 20                      # Intensity at or below this: a rim click instead of the snare ("by intensity")
HALF_OPEN_FROM, OPEN_FROM = 70, 85   # Intensity from these: the hi-hat half open, then open ("by intensity")
OPENNESS = (("intensity", "by intensity (closed, half open from {}, open from {})".format(HALF_OPEN_FROM, OPEN_FROM)),
            ("closed", "closed"), ("half", "half open"), ("open", "open"))
RIM_CHOICES = (("intensity", "by intensity (a rim click at Intensity {} or below)".format(RIM_AT)),
               ("always", "always a rim click (cross-stick)"), ("never", "never (always the snare)"))
RIDE_SOUNDS = (("ride", "the ride", RIDE), ("bell", "the ride bell", RIDE_BELL), ("second", "the second ride", RIDE2))
# Each kit piece plays only its own sounds (Russell, 21 Oct 2026: "with the hi-hat you can change the variation and
# whatnot but you shouldn't change the hi-hat to a cymbal ... it should all be their own respective kit pieces"). Until
# then the hi-hat had "Play this rhythm on" (the ride, its bell or the crash); a project that chose it is read without
# it (clean_pieces leaves out a setting a piece no longer has), so its hi-hat plays on the hi-hat again.
TIME = (("normal", "normal time"), ("half", "half time"), ("double", "double time"))

# the styles a real drummer plays (not the drum machines of dubstep, house and trap, nor the hand percussion styles)
LIVE_DRUMMER_STYLES = ("rock", "hard_rock", "metal", "jazz", "funk", "pop")
# Sixteenth notes on a cymbal only as fast as a drummer's one hand can keep them up (Russell, 21 Oct 2026: "if the tempo
# is over 120 beats a minute then the 16th note patterns shouldn't be an option for the ride cymbal, or whatever you
# decide per kit"). Above the tempo: the Pattern list leaves out patterns with runs of sixteenth notes on that piece,
# and what the piece plays by itself keeps its eighth notes and drops the sixteenths squeezed between them (a lone
# hit on an "e" or "a", a sixteenth away from any other, is not a run and stays; steps you set by hand stay).
# The ride: above 120 in every style. The hi-hat: above 140 in the styles a real drummer plays (two hands can share
# hi-hat sixteenths up to about there); the drum machines keep their fast hi-hats. Kicks (feet), shakers and fills
# are not limited.
# (a drummer's hi-hat was held to eighths above 140 from 0.9.5 until Russell, 21 Oct 2026: "bring the 16th notes to
# the hi-hats back, even if the tempo goes over 140": disco sixteenths on a closed hi-hat are his to choose)
SIXTEENTHS_UP_TO = {"ride": (120, None)}


def sixteenths_up_to(piece_key, style_key):
    """The fastest tempo (quarter notes a minute) at which this piece plays sixteenth notes in this style, or None
    when it has no limit."""
    limit = SIXTEENTHS_UP_TO.get(piece_key)
    if limit is None or (limit[1] is not None and style_key not in limit[1]):
        return None
    return limit[0]


def too_fast_for_sixteenths(piece_key, style_key, tempo):
    limit = sixteenths_up_to(piece_key, style_key)
    return limit is not None and tempo is not None and tempo > limit


def rows_have_sixteenths(rows):
    """Whether rows ({voice: (16 chances, ...)}) can play two hits a sixteenth note apart, one of them between the
    eighth notes (the piece's sounds together, as one hand plays them)."""
    places = set()
    for entry in rows.values():
        places |= {place for place, chance in enumerate(entry[0]) if chance > 0}
    return any((place - 1) % 16 in places or (place + 1) % 16 in places for place in places if place % 2 == 1)


def tempo_words(limit):
    return "eighth notes above {} beats a minute".format(limit)
GHOSTS = (("style", "ghost notes as the style plays them"), ("none", "no ghost notes"), ("more", "more ghost notes"))
LENGTHS = (("short", "short notes"), ("normal", "normal notes"), ("long", "long notes"))

# Loudness ("level", 10 Oct 2026; Russell: "instead of zero to 40 ... zero to 100, 100 being the loudest"): a percent
# of how hard the style plays the piece. 50 is the style's own, 100 twice as hard (as loud as a note goes), 0 silent.
# Before 0.9.4 it was "loudness", -40 to 40 added to each hit; clean_pieces turns that into the nearest level.
LEVEL_DEFAULT = 50
# Complexity of one piece or part ("busy", 10 Oct 2026; Russell: "set the complexity from zero to 100 ... it should
# get busier up until 100% but not so crazy where it looks like it's inhuman"): 50 plays it as the style does at the
# region's Complexity, higher adds notes (in-between eighths, then some sixteenths), lower thins it to the beats.
# Before this it was "complexity", -50 to 50 added to the region's Complexity, which changed only the steps a style
# plays sometimes, so most pieces did not change; clean_pieces turns it into the same "busy" (50 + half of it).
BUSY_DEFAULT = 50
DRUM_DEFAULTS = {"on": True, "pattern": "style", "busy": BUSY_DEFAULT, "level": LEVEL_DEFAULT, "time": "normal",
                 "ghosts": "style", "ghost_level": LEVEL_DEFAULT,
                 "rim": "intensity", "openness": "intensity", "open_offbeats": False, "in_fills": True,
                 "when": "start_and_fills", "which": "crash1", "bell": False, "ride_sound": "ride",
                 "steps": None}
PART_DEFAULTS = {"pattern": "style", "chords": True, "octave": 0, "length": "normal", "root_only": False,
                 "passing": False, "busy": BUSY_DEFAULT, "level": LEVEL_DEFAULT, "steps": None}
RANGES = {"busy": (0, 100), "level": (0, 100), "ghost_level": (0, 100), "octave": (-2, 2)}
CHOICES = {"time": TIME, "ghosts": GHOSTS, "openness": OPENNESS, "when": WHEN,
           "which": tuple((key, key) for key, _notes in WHICH), "length": LENGTHS, "rim": RIM_CHOICES,
           "ride_sound": tuple((key, words) for key, words, _note in RIDE_SOUNDS)}
EXTRAS = {"kick": ("time",), "snare": ("time", "ghosts", "ghost_level", "rim"), "hat": ("openness", "open_offbeats"),
          "toms": ("in_fills",), "crash": ("when", "which"), "ride": ("ride_sound", "bell")}
COMMON = ("on", "pattern", "busy", "level", "steps")
PART_KEYS = ("pattern", "chords", "octave", "length", "root_only", "passing", "busy", "level", "steps")


def level_velocity(velocity, level):
    """A hit's loudness at a piece's level (50: as it is; 100: twice as hard, at most 127; 0: None, not played)."""
    if level == LEVEL_DEFAULT:
        return velocity
    if level <= 0:
        return None
    return max(1, min(127, int(round(velocity * level / float(LEVEL_DEFAULT)))))


def old_loudness_to_level(value):
    """Before 0.9.4: -40 to 40 added to each hit (most hits are near 90): the nearest level."""
    try:
        return max(0, min(100, int(round(LEVEL_DEFAULT * (90 + float(value)) / 90.0))))
    except (TypeError, ValueError, OverflowError):
        return LEVEL_DEFAULT

# what a step of a part can play ("style": the style's own notes on that step, at the step's loudness)
PART_SOUNDS = {"bellows": ("root", "third", "fifth", "octave", "style"),
               "ember": ("chord", "root", "third", "fifth", "octave", "style"),
               "spark": ("chord", "root", "third", "fifth", "octave", "style"),
               "hammer": ("power", "strum", "root", "third", "fifth", "octave", "style")}
SOUND_NAMES = {"chord": "the chord", "power": "a power chord", "strum": "a strummed chord", "root": "the root",
               "third": "the third", "fifth": "the fifth", "octave": "the octave", "style": "as the style plays it"}


def pieces_for(player_key):
    return DRUM_PIECES if player_key == "anvil" else (PART,)


def busy_complexity(region_complexity, busy):
    """The Complexity a piece or part plays at: the region's, moved by its own (50: the region's; 100: the busiest;
    0: the simplest)."""
    return max(0, min(100, int(region_complexity) + 2 * (int(busy) - BUSY_DEFAULT)))


def allowed_keys(piece):
    if piece.kind == "part":
        return PART_KEYS
    return COMMON + EXTRAS.get(piece.kind, ())


def defaults_for(piece):
    return dict(PART_DEFAULTS if piece.kind == "part" else DRUM_DEFAULTS)


# ----------------------------------------------------------------------
# cleaning what a project file holds
# ----------------------------------------------------------------------
def clean_value(piece, key, value, player_key=None):
    """A valid value for one setting, or raise ValueError."""
    if key not in allowed_keys(piece):
        raise ValueError("{} has no setting called {}".format(piece.name, key))
    if key == "rim" and isinstance(value, bool):      # before 0.9.4 the rim click was on or off
        value = "always" if value else "intensity"
    if key in ("on", "open_offbeats", "in_fills", "bell", "chords", "root_only", "passing"):
        return bool(value)
    if key in RANGES:
        low, high = RANGES[key]
        try:
            return int(max(low, min(high, int(value))))
        except (TypeError, ValueError, OverflowError):
            raise ValueError("{} needs a whole number".format(key)) from None
    if key in CHOICES:
        if not isinstance(value, str) or value not in [c[0] for c in CHOICES[key]]:
            raise ValueError("Unknown choice for {}".format(key))
        return value
    if key == "pattern":
        if not isinstance(value, str) or not value or len(value) > 40:
            raise ValueError("Unknown pattern")
        return value
    if key == "steps":
        return clean_steps(piece, value, player_key)
    raise ValueError("Unknown setting {}".format(key))


def clean_steps(piece, raw, player_key=None):
    """Hand-made steps: {"bars": [[[step, velocity, sound], ...], ...]}, 1 to 4 bars; None for none. A drum piece's
    step can hold several sounds (each listed once); a part's step holds one."""
    if raw is None:
        return None
    bars = raw.get("bars") if isinstance(raw, dict) else None
    if not isinstance(bars, list) or not 1 <= len(bars) <= MAX_STEP_BARS:
        raise ValueError("Hand-made steps need 1 to {} bars".format(MAX_STEP_BARS))
    part = piece.kind == "part"
    sounds = PART_SOUNDS.get(player_key, PART_SOUNDS["ember"]) if part else piece.voices
    clean = []
    for bar in bars:
        found = {}
        for item in bar if isinstance(bar, list) else ():
            try:
                step, velocity, sound = int(item[0]), int(item[1]), item[2]
            except (TypeError, ValueError, LookupError, OverflowError):
                continue
            if isinstance(sound, bool) or not isinstance(sound, (str, int, float)):
                continue
            if not part and isinstance(sound, float) and sound.is_integer():
                sound = int(sound)
            if not 0 <= step < MAX_STEPS_IN_BAR or sound not in sounds:
                continue
            found[step if part else (step, sound)] = [step, max(1, min(127, velocity)), sound]
        clean.append([found[k] for k in sorted(found)])
    return {"bars": clean}


def clean_pieces(player_key, raw):
    """Valid piece settings from a project file: {piece key: {setting: value}}, only what differs from the default
    (anything damaged is left out, so it plays as the style does)."""
    if not isinstance(raw, dict):
        return {}
    cleaned = {}
    for piece in pieces_for(player_key):
        stored = raw.get(piece.key)
        if not isinstance(stored, dict):
            continue
        if "loudness" in stored:                       # saved before 0.9.4
            stored = dict(stored)
            old = stored.pop("loudness")
            stored.setdefault("level", old_loudness_to_level(old))
        if "complexity" in stored:                     # an offset, -50 to 50, before 10 Oct 2026
            stored = dict(stored)
            old = stored.pop("complexity")
            try:
                stored.setdefault("busy", BUSY_DEFAULT + int(round(max(-50, min(50, int(old))) / 2.0)))
            except (TypeError, ValueError, OverflowError):
                pass
        defaults = defaults_for(piece)
        kept = {}
        for key, value in stored.items():
            try:
                value = clean_value(piece, key, value, player_key)
            except (ValueError, TypeError, LookupError, OverflowError):
                continue
            if value != defaults.get(key) or key == "on":     # on or off as chosen (see piece_on)
                kept[key] = value
        if kept:
            cleaned[piece.key] = kept
    return cleaned


def piece_settings(settings, piece_key):
    """Every setting of one piece (the defaults with what the region changed)."""
    piece = PIECE_BY_KEY[piece_key]
    full = defaults_for(piece)
    full.update((settings.get("pieces") or {}).get(piece_key, {}))
    return full


def piece_on(settings, piece_key, has_groove=True):
    """Whether a kit piece plays its groove (Russell, 21 Oct 2026: "if a kit piece is not in the groove ... those kit
    pieces are off"). As chosen when it was turned on or off by hand; otherwise on when it has something of its own
    to play: the variation's groove has it (has_groove), another pattern was chosen for it, it has hand-made steps,
    or more ghost notes were asked of it. Off only takes a piece out of the groove: fills use the whole kit, and the crashes where a section starts
    and after fills follow the crash's When setting (from rules 2; see players._KitPieces). The part is always on."""
    piece = PIECE_BY_KEY[piece_key]
    if piece.kind == "part":
        return True
    stored = (settings.get("pieces") or {}).get(piece_key) or {}
    if "on" in stored:
        return bool(stored["on"])
    return bool(has_groove or stored.get("pattern", "style") not in ("style", "none") or stored.get("steps")
                or stored.get("ghosts") == "more")      # more ghost notes: the snare plays them, groove or not


def hand_made(settings):
    """The pieces with hand-made steps, in order: [Piece]."""
    stored = settings.get("pieces") or {}
    return [p for p in pieces_for(settings["player"]) if (stored.get(p.key) or {}).get("steps")]


# ----------------------------------------------------------------------
# patterns
# ----------------------------------------------------------------------
def _row(text):
    """'x...x...' -> 16 chances: x always, a digit 1 to 9 a chance of a tenth to nine tenths, . never."""
    out = []
    for ch in text:
        out.append(1.0 if ch == "x" else (int(ch) / 10.0 if ch.isdigit() else 0.0))
    return out


# a few common patterns for each piece: (key, words, {voice: (16 chances, loudness, scaled)})
GENERIC = {
    "kick": [("four", "four on the floor (every beat)", {KICK: (_row("x...x...x...x..."), 112, "")}),
             ("one_three", "one and three", {KICK: (_row("x.......x......."), 112, "")}),
             ("one", "one only", {KICK: (_row("x..............."), 115, "")}),
             ("half", "one and the and of three (half time)", {KICK: (_row("x.........x....."), 115, "")}),
             ("push", "one, the and of two, and three", {KICK: (_row("x.....x.x......."), 112, "")}),
             ("eighths", "eighth notes (double kick)", {KICK: (_row("x.x.x.x.x.x.x.x."), 110, "")}),
             ("sixteenths", "sixteenth notes (double kick)", {KICK: (_row("xxxxxxxxxxxxxxxx"), 104, "")})],
    "snare": [("backbeat", "two and four", {SNARE: (_row("....x.......x..."), 112, "")}),
              ("three", "three only (half time)", {SNARE: (_row("........x......."), 118, "")}),
              ("every_beat", "every beat", {SNARE: (_row("x...x...x...x..."), 106, "")}),
              ("offbeats", "the and of every beat", {SNARE: (_row("..x...x...x...x."), 108, "")})],
    "clap": [("backbeat", "a clap on two and four", {CLAP: (_row("....x.......x..."), 105, "")}),
             ("three", "a clap on three", {CLAP: (_row("........x......."), 110, "")}),
             ("offbeats", "a clap on the and of every beat", {CLAP: (_row("..x...x...x...x."), 100, "")}),
             ("rim", "a rim click on two and four", {RIM: (_row("....x.......x..."), 82, "")})],
    "hat": [("eighths", "eighth notes", {HAT: (_row("x.x.x.x.x.x.x.x."), 85, "")}),
            ("sixteenths", "sixteenth notes", {HAT: (_row("xxxxxxxxxxxxxxxx"), 76, "")}),
            ("quarters", "every beat", {HAT: (_row("x...x...x...x..."), 85, "")}),
            ("offbeats", "the and of every beat", {HAT: (_row("..x...x...x...x."), 85, "")}),
            ("332", "a three-three-two pattern", {HAT: (_row("x..x..x.x..x..x."), 84, "")}),
            ("pedal", "the foot pedal on two and four", {PEDAL: (_row("....x.......x..."), 78, "")}),
            ("disco", "disco sixteenths (open on the and of each beat)", {HAT: (_row("xxxxxxxxxxxxxxxx"), 74, "")})],
    "open_hat": [("offbeats", "the and of every beat", {OPEN_HAT: (_row("..x...x...x...x."), 88, "")}),
                 ("and_of_four", "the and of four", {OPEN_HAT: (_row("..............x."), 88, "")}),
                 ("quarters", "every beat", {OPEN_HAT: (_row("x...x...x...x..."), 90, "")})],
    "toms": [("floor_eighths", "the floor tom in eighth notes", {TOM_FLOOR: (_row("x.x.x.x.x.x.x.x."), 80, "")}),
             ("floor_beats", "the floor tom on every beat", {TOM_FLOOR: (_row("x...x...x...x..."), 90, "")}),
             ("around", "a groove around the toms", {TOM_FLOOR: (_row("x.....x........."), 100, ""),
                                                     TOM_LOW: (_row("...x......x....."), 95, ""),
                                                     TOM_MID: (_row("........x....x.."), 90, "")})],
    "crash": [("beats", "a crash on every beat", {CRASH: (_row("x...x...x...x..."), 96, "")}),
              ("eighths", "a crash in eighth notes (a wash)", {CRASH: (_row("x.x.x.x.x.x.x.x."), 88, "")}),
              ("one", "a crash on one of every bar", {CRASH: (_row("x..............."), 100, "")})],
    "ride": [("eighths", "eighth notes", {RIDE: (_row("x.x.x.x.x.x.x.x."), 84, "")}),
             ("beats", "every beat", {RIDE: (_row("x...x...x...x..."), 86, "")}),
             ("sixteenths", "sixteenth notes", {RIDE: (_row("xxxxxxxxxxxxxxxx"), 76, "")}),
             ("swing", "the swing pattern", {RIDE: (_row("x...x.x.x...x.x."), 82, "")}),
             ("bell", "the bell on every beat", {RIDE_BELL: (_row("x...x...x...x..."), 85, "")})],
    "hand_drums": [("tumbao", "a conga tumbao", {CONGA_MUTE: (_row("x...x...x...x..."), 80, ""),
                                                 CONGA_OPEN: (_row("......xx......xx"), 95, "")}),
                   ("bongos", "bongos in eighth notes", {BONGO_HIGH: (_row("x.x.x.x.x.x.x.x."), 72, ""),
                                                         BONGO_LOW: (_row("...x.......x...."), 75, "")})],
    "percussion": [("shaker", "a shaker in sixteenths", {SHAKER: (_row("xxxxxxxxxxxxxxxx"), 66, "")}),
                   ("shaker8", "a shaker in eighth notes", {SHAKER: (_row("x.x.x.x.x.x.x.x."), 70, "")}),
                   ("tambourine", "a tambourine on two and four", {TAMBOURINE: (_row("....x.......x..."), 90, "")}),
                   ("cowbell", "a cowbell on every beat", {COWBELL: (_row("x...x...x...x..."), 80, "")}),
                   ("clave", "son clave", {CLAVES: (_row("x..x..x...x.x..."), 85, "")})],
}


def _number(text):
    """The number in a pattern's name ("v3" gives 3), or None."""
    return int(text) if text.isdecimal() and len(text) <= 4 else None


def kit_voices(piece, kit_notes=None):
    """The voices of a drum piece the kit has (kit_notes None: a kit with every drum note)."""
    return tuple(v for v in piece.voices if kit_notes is None or v in kit_notes)


def which_choices(kit_notes=None):
    """The Which cymbal choices whose cymbals the kit has: [(key, notes)]."""
    return [(key, notes) for key, notes in WHICH if kit_notes is None or all(n in kit_notes for n in notes)]


def style_table(style_key, variation, base_tables):
    """The drum table of a style's variation: {voice: (16 chances, loudness, scaled)} (variation 1 is the style's
    own table, untouched)."""
    table = dict(base_tables[style_key])
    for voice, entry in pv.drum_overrides(style_key, variation).items():
        if entry is None:
            table.pop(voice, None)
        else:
            table[voice] = entry
    return table


def piece_rows(table, piece):
    return {voice: entry for voice, entry in table.items() if VOICE_PIECE.get(voice) == piece.key}


def _rows_key(rows):
    return tuple(sorted((voice, tuple(entry[0]), entry[1]) for voice, entry in rows.items()))


def drum_pattern_options(style_key, variation, piece_key, base_tables, kit_program=None, kit_notes=None, tempo=None,
                         chosen=None):
    """[(key, words)] for a drum piece's Pattern list: the chosen variation's own first, then what the style's other
    variations play on this piece, then none, then common patterns (only those the kit has the sounds for). Each
    rhythm is listed once, named with the kit's own names for its sounds.
    tempo: the region's fastest tempo; above the piece's limit (SIXTEENTHS_UP_TO) patterns with sixteenth notes are
    left out, except `chosen` (the pattern the piece has), which stays and says it plays eighth notes there."""
    piece = PIECE_BY_KEY[piece_key]
    own = piece_rows(style_table(style_key, variation, base_tables), piece)
    fast = too_fast_for_sixteenths(piece_key, style_key, tempo)
    limit = sixteenths_up_to(piece_key, style_key)

    def playable(rows, key=None):
        if fast and rows_have_sixteenths(rows) and key != chosen:
            return False
        return kit_notes is None or all(voice in kit_notes for voice in rows)

    def words_at_tempo(words, rows):
        return words + (" ({})".format(tempo_words(limit)) if fast and rows_have_sixteenths(rows) else "")

    options = [("style", words_at_tempo("As variation {} plays it: {}".format(
        variation, rows_words(own, kit_program) if own else "none in the groove"), own))]
    seen = {_rows_key(own)}
    for number in range(1, pv.count("anvil", style_key) + 1):
        if number == variation:
            continue
        rows = piece_rows(style_table(style_key, number, base_tables), piece)
        if rows and _rows_key(rows) not in seen and playable(rows, "v{}".format(number)):
            seen.add(_rows_key(rows))
            options.append(("v{}".format(number), words_at_tempo("Variation {}'s: {}".format(
                number, rows_words(rows, kit_program)), rows)))
    if own:
        options.append(("none", "None in the groove" + (" (fills only)" if piece.kind == "toms" else "")))
    for key, words, rows in GENERIC.get(piece_key, ()):
        if _rows_key(rows) not in seen and playable(rows, "g:" + key):
            seen.add(_rows_key(rows))
            options.append(("g:" + key, words_at_tempo(words[0].upper() + words[1:], rows)))
    return options


def drum_pattern_rows(style_key, variation, piece_key, pattern, base_tables):
    """The rows a drum piece plays for a Pattern choice, or None for the variation's own."""
    piece = PIECE_BY_KEY[piece_key]
    if pattern == "style":
        return None
    if pattern == "none":
        return {}
    if pattern.startswith("v") and _number(pattern[1:]) is not None:
        number = max(1, min(pv.count("anvil", style_key), _number(pattern[1:])))
        return piece_rows(style_table(style_key, number, base_tables), piece)
    if pattern.startswith("g:"):
        for key, _words, rows in GENERIC.get(piece_key, ()):
            if key == pattern[2:]:
                return dict(rows)
    return None                     # an unknown pattern (from a newer version, say) plays the variation's own


def part_pattern_options(player, style_key, variation):
    """[(key, words)] for a part's Pattern list: the variation's own, the style's other variations, then the
    player's other styles' variations."""
    options = [("style", "As variation {} plays it: {}".format(variation,
                                                               pv.description(player.key, style_key, variation)))]
    for number in range(1, pv.count(player.key, style_key) + 1):
        if number != variation:
            options.append(("v{}".format(number), "Variation {}: {}".format(
                number, pv.description(player.key, style_key, number))))
    for style in player.styles:
        if style.key == style_key:
            continue
        for number in range(1, pv.count(player.key, style.key) + 1):
            options.append(("s:{}:{}".format(style.key, number), "{}, variation {}: {}".format(
                style.name, number, pv.description(player.key, style.key, number))))
    return options


def part_pattern(player_key, style_key, variation, pattern):
    """(style, variation) whose rhythm a part plays for a Pattern choice."""
    if pattern.startswith("v") and _number(pattern[1:]) is not None:
        return style_key, max(1, min(pv.count(player_key, style_key), _number(pattern[1:])))
    if pattern.startswith("s:"):
        parts = pattern.split(":")
        if len(parts) == 3 and _number(parts[2]) is not None and parts[1] in pv.MELODIC.get(player_key, {}):
            return parts[1], max(1, min(pv.count(player_key, parts[1]), _number(parts[2])))
    return style_key, variation


# ----------------------------------------------------------------------
# words
# ----------------------------------------------------------------------
BEAT_WORDS = ("one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
              "thirteen", "fourteen", "fifteen", "sixteen")


def step_words(step, beat_steps=4):
    """'one', 'the e of two', 'the and of two', 'the a of two' (sixteenths in a beat of four steps)."""
    beat, inside = divmod(int(step), beat_steps)
    name = BEAT_WORDS[beat] if beat < len(BEAT_WORDS) else str(beat + 1)
    if inside == 0:
        return name
    if beat_steps == 4:
        return "the {} of {}".format(("e", "and", "a")[inside - 1], name)
    return "step {} of beat {}".format(inside + 1, name)


def join_words(items):
    items = list(items)
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def positions_words(row):
    """Where a 16-step row plays: 'on every eighth note', 'on one and three, sometimes on the and of three', 'now and
    then on every sixteenth note'."""
    sure = [s for s, v in enumerate(row) if v >= 1.0]
    maybe = [s for s, v in enumerate(row) if 0.0 < v < 1.0]
    named = {tuple(range(16)): "every sixteenth note", tuple(range(0, 16, 2)): "every eighth note",
             tuple(range(0, 16, 4)): "every beat", tuple(range(2, 16, 4)): "the and of every beat"}

    def where(steps, others=False):
        if tuple(steps) in named:
            return named[tuple(steps)]
        if len(steps) > 6:
            return "{} {}sixteenth notes".format(len(steps), "other " if others else "")
        return join_words(step_words(s) for s in steps)
    if sure and maybe:
        return "on {}, sometimes on {}".format(where(sure), where(maybe, True))
    if sure:
        return "on " + where(sure)
    if maybe:
        return "now and then on " + where(maybe)
    return "nowhere"


def note_name(note, kit_program=None):
    special = keyboard_map.KIT_DRUM_NAMES.get(kit_program, {})
    return special.get(note) or NOTE_NAMES.get(note) or keyboard_map.drum_name(note)


def missing_words(notes, kit_notes=None, kit_program=None):
    """What a choice of sound says when the kit lacks it: '' when the kit has every one of `notes` (one note or
    several); else " (not in this kit, so the crash cymbal plays it)", the stand-in Musician Forge plays instead
    (drummap.py, since 10 Oct 2026), or " (not in this kit, so silent)" when there is none. (Until the final
    review that evening every such choice was said to be silent, which had stopped being true.)"""
    notes = (notes,) if isinstance(notes, int) else tuple(notes)
    lacking = [n for n in notes if kit_notes is not None and n not in kit_notes]
    if not lacking:
        return ""
    stand_ins = drummap.substitutes(kit_notes)
    if any(n not in stand_ins for n in lacking):
        return " (not in this kit, so silent)"
    names = []
    for n in lacking:
        name = note_name(stand_ins[n], kit_program)
        if name not in names:
            names.append(name)
    return " (not in this kit, so the {} plays it)".format(" and the ".join(names))


def rows_words(rows, kit_program=None):
    """'kick on one and three, sometimes on the and of three'."""
    return "; ".join("{} {}".format(note_name(voice, kit_program), positions_words(entry[0]))
                     for voice, entry in rows.items())


def which_words(which, kit_program=None):
    notes = dict(WHICH).get(which, (CRASH,))
    return " and ".join(note_name(n, kit_program) for n in notes) + (" in turn" if len(notes) > 1 else "")


def choice_words(key, value):
    return dict(CHOICES[key]).get(value, value)


def describe_piece(settings, piece_key, has_groove=True, kit_program=None, kit_notes=None):
    """The line in the Kit pieces list: 'Crash cymbals: on, where the region starts and after fills, crash'.
    kit_notes: the notes the kit has (None: every drum note), so a piece or sound the kit lacks is said."""
    piece = PIECE_BY_KEY[piece_key]
    full = piece_settings(settings, piece_key)
    words = []
    if piece.kind != "part":
        words.append("on" if piece_on(settings, piece_key, has_groove) else "off")
        if not kit_voices(piece, kit_notes):
            words.append("not in this kit")
    if full["pattern"] != "style":
        words.append("pattern changed")
    elif piece.kind not in ("part", "crash") and not has_groove and not full["steps"] and kit_voices(piece, kit_notes):
        words.append("in fills only" if piece.kind == "toms" else "not in this groove")
    if piece.kind == "crash":
        when = choice_words("when", full["when"])
        if full["when"] == "accents" and settings.get("follow") != "track":
            when += " (nothing is followed, so where the style plays them)"
        words.append(when)
        cymbals = dict(WHICH).get(full["which"], (CRASH,))
        words.append(which_words(full["which"], kit_program) + missing_words(cymbals, kit_notes, kit_program))
    for key in EXTRAS.get(piece.kind, ()):
        # (the ghost notes' loudness is said further down, with the other loudness; until the final review of
        # 10 Oct 2026 it fell through to here, and any value but 50 raised an error that broke the Kit pieces list)
        if key in ("when", "which", "ghost_level") or full[key] == DRUM_DEFAULTS[key]:
            continue
        if key == "ride_sound":
            words.append("played on " + choice_words(key, full[key]))
            note = dict((k, n) for k, _w, n in RIDE_SOUNDS).get(full[key])
            if note is not None:
                words[-1] += missing_words(note, kit_notes, kit_program)
        elif key in CHOICES:
            words.append(choice_words(key, full[key]))
        else:
            words.append({"open_offbeats": "open on the offbeats",
                          "in_fills": "not in fills", "bell": "the bell on the beats"}[key])
            if key == "bell":
                words[-1] += missing_words(RIDE_BELL, kit_notes, kit_program)
    if piece.kind == "part":
        if not full["chords"]:
            words.append("the key's own chord, not the chord track")
        if full["octave"]:
            words.append("{} octave{} {}".format(abs(full["octave"]), "" if abs(full["octave"]) == 1 else "s",
                                                 "up" if full["octave"] > 0 else "down"))
        if full["length"] != "normal":
            words.append(choice_words("length", full["length"]))
        if full["root_only"]:
            words.append("the root only")
        if full["passing"]:
            words.append("passing notes")
    if full.get("busy", BUSY_DEFAULT) != BUSY_DEFAULT:
        words.append("complexity {} ({})".format(full["busy"], "busier" if full["busy"] > BUSY_DEFAULT else "simpler"))
    if full.get("ghost_level", LEVEL_DEFAULT) != LEVEL_DEFAULT and full.get("ghosts") != "none":
        words.append("ghost notes at {} percent".format(full["ghost_level"]))
    if full["level"] != LEVEL_DEFAULT:
        words.append("loudness {} percent".format(full["level"]))
    if full["steps"]:
        count = len(full["steps"]["bars"])
        words.append("hand-made, {} bar{}".format(count, "" if count == 1 else "s"))
    return "{}: {}".format(piece.name if piece.kind != "part" else "The part", ", ".join(words) or "as the style "
                                                                                                  "plays it")


def sound_names(piece, player_key, kit_program=None, kit_notes=None):
    """[(sound, words)] a step of this piece can play (for a drum piece, the sounds the kit has)."""
    if piece.kind == "part":
        return [(s, SOUND_NAMES[s]) for s in PART_SOUNDS.get(player_key, PART_SOUNDS["ember"])]
    return [(v, note_name(v, kit_program)) for v in kit_voices(piece, kit_notes)]
