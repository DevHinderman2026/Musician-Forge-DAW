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

UI CONTRACT (0.9.8)
What the windows use from here (Russell, 24 Oct 2026: one hi-hat piece for the hand, a separate pedal piece for the
foot, and the ride and the hi-hat taking turns as two plain toggles):
- DRUM_PIECES, in the Kit pieces list's order, key and display name (PIECE_BY_KEY[key].name): kick "Kick",
  snare "Snare", clap "Clap or rim", hat "Hi-hat" (the hand on the hi-hat: both its closed and open sounds, HAT and
  OPEN_HAT; kind "hat", with the settings "openness" (How open the hi-hat is) and "open_offbeats"), pedal "Hi-hat
  pedal" (the foot, PEDAL only; kind "pedal", only the common settings: on, pattern, busy, level, steps), toms "Toms",
  crash "Crash cymbals", ride "Ride", hand_drums "Congas and bongos", percussion "Shaker, tambourine, cowbell and
  claves". There is no "open_hat" piece any more, and no "foot only" state: a piece is on or off. The settings in
  TURN_KEYS ("off_for", "open_level", "open_busy", "old_off", "old_steps") are the model's own and get no control in
  the piece window.
- A toggle: the window calls session.update_piece(track_id, index, piece_key, speak=False, on=True or False), or
  session.toggle_piece(track_id, index, piece_key). Both apply TAKES_TURNS in the same undo step and return the
  piece's Kit pieces line (describe_piece). Right after, session.turn_words is None or one of TURN_PHRASES ("Ride on,
  hi-hat off", "Hi-hat on, ride off", "Ride off, hi-hat on", "Hi-hat off, ride on"), or "Ride on with the hi-hat's
  rhythm, hi-hat off" when a ride with nothing of its own to play took over the hi-hat's rhythm. The window then
  re-reads the other piece (session.piece_settings(track_id, index, other)["on"]) and sets its check box to that.
  session.pieces_turned_off(track_id, index, piece_key) says beforehand which other piece turning this one on would
  turn off: ["hat"], ["ride"] or [] (nothing is changed).
- session.piece_settings(track_id, index, piece_key)["on"] is a piece's toggle as it stands (piece_on).
- The pedal's default (pedal_default_on; PEDAL_STYLES): on by itself where the groove has the foot (jazz), and in
  regions made or changed from 0.9.8 (rules 4) also in funk and pop, the foot on two and four; off in rock, hard rock,
  metal and the drum machines (house, trap, dubstep) until turned on. Nothing but its own toggle, Pattern or steps
  turns it on or off: the ride and the hi-hat never touch it (TAKES_TURNS has no entry for it).
- Lines in the Kit pieces list: "Hi-hat: off, the ride keeps time" and "Ride: off, the hi-hat keeps time" for a piece
  the other one turned off (it comes back when that one is turned off); "Hi-hat pedal: off" for
  the pedal off by itself and "Hi-hat pedal: on, the foot on two and four" where it plays by itself. TURN_NAMES has
  the spoken names ("ride", "hi-hat", "hi-hat pedal").
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
    Piece("hat", "Hi-hat", (HAT, OPEN_HAT), "hat"),            # the hand: closed and open (0.9.8)
    Piece("pedal", "Hi-hat pedal", (PEDAL,), "pedal"),           # the foot (0.9.8)
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
                 "off_for": "", "open_level": -1, "open_busy": -1, "old_off": "", "old_steps": "", "old_bars": None,
                 "auto": False, "steps": None}
PART_DEFAULTS = {"pattern": "style", "chords": True, "octave": 0, "length": "normal", "root_only": False,
                 "passing": False, "busy": BUSY_DEFAULT, "level": LEVEL_DEFAULT, "steps": None}
RANGES = {"busy": (0, 100), "level": (0, 100), "ghost_level": (0, 100), "octave": (-2, 2)}
CHOICES = {"time": TIME, "ghosts": GHOSTS, "openness": OPENNESS, "when": WHEN,
           "which": tuple((key, key) for key, _notes in WHICH), "length": LENGTHS, "rim": RIM_CHOICES,
           "ride_sound": tuple((key, words) for key, words, _note in RIDE_SOUNDS)}
EXTRAS = {"kick": ("time",), "snare": ("time", "ghosts", "ghost_level", "rim"),
          "hat": ("openness", "open_offbeats", "off_for", "open_level", "open_busy", "old_off", "old_steps",
                  "old_bars"),
          "toms": ("in_fills",),
          "crash": ("when", "which", "off_for"), "ride": ("ride_sound", "bell", "off_for")}
# set by the ride and the hi-hat taking turns (TAKES_TURNS), not in the piece window: "off_for" is the piece that
# turned this one off ("ride" or "hat"), so turning that one off brings this one back; "" for off by hand.
# "open_level" is only for regions saved before 0.9.8, whose Open hi-hat had a loudness of its own: it is applied to
# the hi-hat's open notes so they play as they did (-1: the hi-hat's own level; nothing in the windows sets it).
# "open_busy" is the same for the Open hi-hat's Complexity of its own, read only under the old rules
# (players._KitPieces._old_hat_pieces; the review of 24 Oct 2026: without it those open notes came out at the
# region's Complexity, and the fills' random choices moved with them) and dropped when the region moves to today's
# rules, where the one Hi-hat has one Complexity.
# "old_steps" says which of those regions' two pieces had hand-made steps ("hat", "open" or "both"; the Hi-hat
# holds both pieces' steps now), so that under the old rules each old piece's steps replace only that piece's
# sounds, as they did; it goes with "old_off" when the region moves to today's rules.
# "old_off" is for those regions too: "closed" when their Closed hi-hat was turned off by hand while the Open
# hi-hat played ("closed_groove" when it was off for having nothing in the groove: the hi-hat still built into a
# louder region then), "open" the other way round (one Hi-hat cannot be half off, so the drummer leaves those notes
# out under the old rules, and the setting goes when the region moves to today's rules: players.to_todays_rules).
# "old_bars" is for those regions too: [the Closed hi-hat's bars, the Open hi-hat's bars] when their hand-made steps
# were of different lengths, so each repeats on its own under the old rules, as it did (the review of 25 Oct 2026:
# 3 bars and 2 bars drifted apart in bar 4); it goes when the region moves to today's rules.
# "auto" marks a pattern a piece was given because it was turned on with nothing of its own to play (Russell, 25 Oct
# 2026: a piece that is on always plays): when the style or variation changes and the new groove has the piece, it
# plays the groove again; choosing a pattern yourself makes it yours (the review of 25 Oct 2026: the given eighth
# notes stayed after a change to a variation with sixteenths).
TURN_KEYS = ("off_for", "open_level", "open_busy", "old_off", "old_steps", "old_bars", "auto")
COMMON = ("on", "pattern", "busy", "level", "steps", "auto")
PART_KEYS = ("pattern", "chords", "octave", "length", "root_only", "passing", "busy", "level", "steps")


def level_velocity(velocity, level):
    """A hit's loudness at a piece's level (50: as it is; 100: twice as hard, at most 127; 0: None, not played)."""
    if level == LEVEL_DEFAULT:
        return velocity
    if level <= 0:
        return None
    return max(1, min(127, int(round(velocity * level / float(LEVEL_DEFAULT)))))


# The kit's own mix (0.9.7; Russell, 23 Oct 2026: "for the kit piece's loudness, so for example, adjusting the
# loudness of the ride, the hi-hat, that will all move to the track settings for that rhythm player specific track ...
# the loudness of the kit pieces ... Not the actual intensity"; for every project, old and new, 23 Oct 2026, 4:52 AM).
# Each kit piece's loudness is a setting of the drummer's track (Track settings), the same
# percent as a piece's Loudness was (level_velocity: 50 as the drummer plays it, 100 twice as hard, 0 silent), for
# every hit of that piece in every drummer region on the track: the groove, fills, crashes and hand-made steps. A
# sound a piece's own settings turn into another (the hi-hat opened by How open the hi-hat is, the rim click the
# snare plays softly, the ride's bell) stays that piece's. Intensity, how hard the drummer plays, is not changed.
def kit_level_label(piece):
    """The Track settings slider's label: 'Ride loudness in percent (50 is as the drummer plays it, ...)'. A long
    name ("Shaker, tambourine, cowbell and claves") puts what the numbers mean on a line of its own, so the window
    stays narrow enough for the screen (a screen reader reads the two lines as one)."""
    words = "{} loudness in percent".format(piece.name)
    return words + ("\n" if len(piece.name) > 20 else " ") + "(50 is as the drummer plays it, 100 the loudest, 0 silent)"


# A kit piece's window shows its own Loudness only when this region has one from an older version (not 50): it plays
# on top of the track's kit loudness, and can be put back to 50 there.
REGION_LEVEL_LABEL = ("This region's own loudness for this piece, from an older version, in percent\n"
                      "(50 is none; the kit's loudness is in Track settings)")


# a track's kit-piece loudness saved before 0.9.8 whose Open hi-hat differed from its Closed hi-hat (old_kit_levels_to_new)
OLD_OPEN_HAT = "old_open_hat"


def clean_kit_levels(raw):
    """A track's kit-piece loudness from a project file: {piece key: 0 to 100}, only the kit's pieces and only those
    not at 50 (anything damaged is left out, so that piece plays as the drummer plays it)."""
    if not isinstance(raw, dict):
        return {}
    cleaned = {}
    for piece in DRUM_PIECES:
        value = raw.get(piece.key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        try:
            value = int(max(0, min(100, int(value))))
        except (TypeError, ValueError, OverflowError):
            continue
        if value != LEVEL_DEFAULT:
            cleaned[piece.key] = value
    value = raw.get(OLD_OPEN_HAT)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            cleaned[OLD_OPEN_HAT] = int(max(0, min(100, int(value))))   # (kept at 50 too: it differs from the Hi-hat's)
        except (TypeError, ValueError, OverflowError):
            pass
    return cleaned


def visible_kit_levels(levels):
    """The kit-piece loudness Track settings shows (OLD_OPEN_HAT left out)."""
    return {key: value for key, value in (levels or {}).items() if key != OLD_OPEN_HAT}


# One hand keeps time on one cymbal (0.9.7; Russell, 23 Oct 2026: "if the hi-hat turns on and if somebody turns on
# the ride, the hi-hat should turn off because it's a cymbal being used"; he chose both ways, and every project, old
# and new). From 0.9.8 (Russell, 24 Oct 2026: "the actual toggle needs to be set to off. Same the other way around")
# the ride and the hi-hat are two plain toggles that take turns, on a drummer that plays like a real one
# (LIVE_DRUMMER_STYLES; the drum machines and the hand percussion are not affected): when the ride starts playing
# (Space, Play this piece, a Pattern or steps) the Hi-hat is turned off, marked off for the ride; when the hi-hat
# starts playing the Ride is turned off, marked off for the hi-hat. Turning the one that took over off by hand
# brings the other back (so something keeps time); a piece turned off by hand stays off. A ride with nothing of its
# own to play takes over the hand's hi-hat rhythm (its Pattern becomes "The hi-hat's rhythm", HAT_RHYTHM), as a
# drummer moves the riding hand. The Hi-hat pedal (the foot) is never touched: it has no entry here.
# Each is one undo step. Nothing changes until a piece is turned on or off, so an older region with the ride and the
# hi-hat both on keeps playing them both.
TAKES_TURNS = {"ride": ("hat",), "hat": ("ride",)}
TURN_NAMES = {"ride": "ride", "hat": "hi-hat", "pedal": "hi-hat pedal", "crash": "crash"}
# Russell, 25 Oct 2026: where the crash keeps time (metal's grooves with no hi-hat and no ride), turning the Hi-hat on
# takes the crash's turn too: the crash's groove goes off, marked off for the hi-hat ("off_for"), and comes back when
# the Hi-hat is turned off again (the crash where a section starts and after fills keeps its When setting)
CRASH_GIVES_WAY_TO = ("hat",)
TURN_PHRASES = ("Ride on, hi-hat off", "Hi-hat on, ride off", "Ride off, hi-hat on", "Hi-hat off, ride on")
HAT_RHYTHM = "h:"           # the ride's Pattern "The hi-hat's rhythm": "h:" and the Hi-hat's own pattern
# The Hi-hat pedal plays by itself where the groove has the foot in it (jazz), and from rules 4 (0.9.8, Russell,
# 24 Oct 2026) also in funk and pop, a quiet foot on two and four under the ride; off in rock, hard rock, metal
# ("metal, hard rock, whatever drummers don't use the foot pedal") and the drum machines until turned on.
PEDAL_STYLES = ("jazz", "funk", "pop")


def takes_turns(style_key, piece_key):
    """The pieces turning this one on turns off on a drummer of this style (only those a real drummer plays)."""
    return TAKES_TURNS.get(piece_key, ()) if style_key in LIVE_DRUMMER_STYLES else ()


def pedal_default_on(style_key, variation, base_tables, rules=None):
    """Whether the Hi-hat pedal plays with nothing chosen for it: the groove has the foot (jazz), or, from rules 4,
    the style is one whose drummer keeps a foot on two and four under the ride (PEDAL_STYLES)."""
    if PEDAL in style_table(style_key, variation, base_tables):
        return True
    return style_key in PEDAL_STYLES and (rules is None or rules >= 4)


def pedal_rows(settings, base_tables):
    """The rows the Hi-hat pedal plays when its Pattern is the style's: the groove's own foot, else the foot on two
    and four (where the pedal plays by itself, pedal_default_on, and wherever it was turned on by hand), else
    none."""
    table = style_table(settings["style"], settings["variation"], base_tables)
    rows = piece_rows(table, PIECE_BY_KEY["pedal"])
    if rows:
        return rows
    stored = (settings.get("pieces") or {}).get("pedal") or {}
    if stored.get("on") or pedal_default_on(settings["style"], settings["variation"], base_tables,
                                            settings.get("rules", 1)):
        return dict(GENERIC["pedal"][0][2])
    return {}


def turn_state(settings, piece_key, has_groove=True):
    """'on' or 'off' (TAKES_TURNS; before 0.9.8 the Closed hi-hat could be at 'foot only')."""
    return "on" if piece_on(settings, piece_key, has_groove) else "off"


def others_words(piece_key, before, after):
    """What a change to this piece did to the other's turn (TAKES_TURNS), or '': 'hi-hat off', 'ride on'.
    before and after: {piece key: turn_state}."""
    keys = TAKES_TURNS.get(piece_key, ()) + (("crash",) if piece_key in CRASH_GIVES_WAY_TO else ())
    return ", ".join("{} {}".format(TURN_NAMES[key], after[key]) for key in keys
                     if key in before and before.get(key) != after.get(key))


def turns_words(piece_key, before, after, rhythm=None):
    """What the windows say when a piece's turn changes the other's (TAKES_TURNS), or None when it changes nothing
    (nor gives the ride a rhythm): 'Ride on, hi-hat off', 'Ride on with the hi-hat's rhythm, hi-hat off',
    'Ride off, hi-hat on', 'Hi-hat on, ride off', 'Hi-hat off, ride on'; only the other when the piece itself stayed
    on or off (a Pattern chosen: 'Ride off'). rhythm: what a ride with nothing of its own to play was given ("the
    hi-hat's rhythm", "the hi-hat's steps" or "eighth notes")."""
    others = others_words(piece_key, before, after)
    if not others and not rhythm:
        return None
    if before.get(piece_key) == after.get(piece_key) and not rhythm:
        return others[0].upper() + others[1:]
    main = "{} {}".format(PIECE_BY_KEY[piece_key].name, after[piece_key]) + (" with " + rhythm if rhythm else "")
    return ", ".join(w for w in (main, others) if w)


def hand_hat_row(style_key, variation, hat_pattern, base_tables):
    """What the hand plays on the hi-hat, as one row (16 chances, loudness, scaled), or None when it plays none:
    the closed and the open hi-hat of the Hi-hat's pattern (in hard rock the hand keeps time on the open hi-hat),
    each step as likely as the likelier of the two; the loudness is that of the one that plays more."""
    rows = None
    if not hat_pattern.startswith(HAT_RHYTHM):
        rows = drum_pattern_rows(style_key, variation, "hat", hat_pattern, base_tables)
    table = style_table(style_key, variation, base_tables)
    if rows is None:
        rows = piece_rows(table, PIECE_BY_KEY["hat"])
    found = [entry for entry in (rows.get(HAT), rows.get(OPEN_HAT)) if entry is not None]
    if not found:
        return None
    chances = [max(entry[0][place] for entry in found) for place in range(len(found[0][0]))]
    busiest = max(found, key=lambda entry: sum(entry[0]))
    return (chances,) + tuple(busiest[1:])


def hat_rhythm_rows(style_key, variation, hat_pattern, base_tables):
    """The ride's rows for "The hi-hat's rhythm" (HAT_RHYTHM): the hand's hi-hat rhythm (hand_hat_row) played on
    the ride; eighth notes when the hand plays no hi-hat."""
    row = hand_hat_row(style_key, variation, hat_pattern, base_tables)
    return dict(GENERIC["ride"][0][2]) if row is None else {RIDE: row}


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
    if key in ("on", "open_offbeats", "in_fills", "bell", "chords", "root_only", "passing", "auto"):
        return bool(value)
    if key == "off_for":
        return value if value in ("ride", "hat") else ""
    if key == "old_off":
        return value if value in ("closed", "closed_groove", "open") else ""
    if key == "old_steps":
        return value if value in ("hat", "open", "both") else ""
    if key == "old_bars":
        try:
            bars = [int(value[0]), int(value[1])]
        except (TypeError, ValueError, LookupError, OverflowError):
            return None
        return bars if len(value) == 2 and all(1 <= b <= MAX_STEP_BARS for b in bars) else None
    if key in ("open_level", "open_busy"):
        try:
            return int(max(-1, min(100, int(value))))
        except (TypeError, ValueError, OverflowError):
            return -1
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


# ----------------------------------------------------------------------
# pieces saved before 0.9.8 (compat._to_9 calls this once, when an older project file is read)
# ----------------------------------------------------------------------
OLD_HAT_FOOTLESS_STYLES = ("hard_rock", "metal")     # 0.9.7's "foot only" played no foot on these


def _old_on(stored, groove, rules):
    """0.9.7's piece_on for a piece from its stored settings: rules 1, on unless turned off by hand."""
    if "on" in stored:
        return bool(stored["on"])
    return True if rules < 2 else bool(groove or stored.get("pattern", "style") not in ("style", "none")
                                       or stored.get("steps"))


def _merge_steps(*step_sets):
    """Hand-made steps of several old pieces as one piece's: {"bars": [...]} or None; a shorter set repeats."""
    found = [steps for steps in step_sets if steps and steps.get("bars")]
    if not found:
        return None
    length = max(len(steps["bars"]) for steps in found)
    bars = []
    for number in range(length):
        bar = []
        for steps in found:
            bar.extend(list(hit) for hit in steps["bars"][number % len(steps["bars"])])
        bars.append(bar)
    return {"bars": bars}


def first_bars(steps, count):
    """The first count bars of hand-made steps (all of them for None), or None for no steps."""
    if not steps or not count:
        return steps
    return {"bars": steps["bars"][:count]}


def _silent_steps(*step_sets):
    """Hand-made steps with every step off, as many bars as the longest of these."""
    return {"bars": [[] for _ in range(max(len(steps["bars"]) for steps in step_sets if steps))]}


def _steps_of(steps, sounds):
    """The hits of these sounds from hand-made steps, or None when there are none."""
    if not steps or not steps.get("bars"):
        return None
    bars = [[list(hit) for hit in bar if len(hit) > 2 and hit[2] in sounds] for bar in steps["bars"]]
    return {"bars": bars} if any(bars) else None


def _old_hand_tokens(hat_pattern, generic_hat):
    """What 0.9.7's Closed hi-hat pattern gave the hand and the foot: (the hand's tokens of the Hi-hat's pattern,
    the Hi-hat pedal's pattern or None for no foot)."""
    hand, foot_pattern = [], None
    if hat_pattern in ("style", "none") or hat_pattern.startswith("v") and _number(hat_pattern[1:]) is not None:
        if hat_pattern != "none":
            hand.append("c:" + hat_pattern)
        foot_pattern = hat_pattern
    elif hat_pattern == "g:pedal":
        foot_pattern = "g:pedal"
    elif hat_pattern.startswith("g:") and hat_pattern[2:] in generic_hat:
        hand.append(hat_pattern)              # a hand pattern: the groove's foot does not play under it
    else:                                     # unknown: played as the variation's own
        hand.append("c:style")
        foot_pattern = "style"
    return hand, foot_pattern


def old_pieces_to_new(raw, style_key, variation, base_tables, rules=1):
    """The pieces of a drummer region saved before 0.9.8, as 0.9.8 keeps them, playing the same notes: the Closed
    hi-hat (closed hi-hat and foot pedal) and the Open hi-hat become the Hi-hat (the hand: closed and open) and the
    Hi-hat pedal (the foot). Each old piece's rhythm goes to the new piece that plays its sounds: the closed hi-hat's
    hand part and the open hi-hat's pattern join as one Hi-hat pattern ("g:eighths+o:style", "c:style" or
    "g:open_quarters"; drum_pattern_rows), its pedal part becomes the Hi-hat pedal's pattern, hand-made steps are
    split by sound, and a loudness the Open hi-hat had of its own is kept as the Hi-hat's open_level. 0.9.7's "foot
    only" (the hand on the ride) becomes Hi-hat off for the ride and the pedal on; a ride "for the hi-hats" becomes
    Ride off for the hi-hat. A dict already in the new form (a "pedal" entry, or no "open_hat", "foot_only" or
    "for_hats") is returned as it is."""
    if not isinstance(raw, dict):
        return raw
    hat = raw.get("hat") if isinstance(raw.get("hat"), dict) else {}
    open_hat = raw.get("open_hat") if isinstance(raw.get("open_hat"), dict) else {}
    ride = raw.get("ride") if isinstance(raw.get("ride"), dict) else {}
    old = "open_hat" in raw or "foot_only" in hat or "for_hats" in ride
    pattern = hat.get("pattern") if isinstance(hat.get("pattern"), str) else ""
    ride_pattern = ride.get("pattern") if isinstance(ride.get("pattern"), str) else ""
    new = ("pedal" in raw or any(key in hat for key in TURN_KEYS) or "+" in pattern
           or pattern[:2] in ("c:", "o:") or pattern.startswith("g:open_")
           or ride_pattern.startswith(HAT_RHYTHM) and (ride_pattern[2:4] in ("c:", "o:") or "+" in ride_pattern))
    if new or not old and not hat and not ride_pattern.startswith(HAT_RHYTHM):
        return raw
    out = {key: value for key, value in raw.items() if key not in ("hat", "open_hat")}
    table = style_table(style_key, variation, base_tables)
    groove_hand, groove_open, groove_foot = HAT in table, OPEN_HAT in table, PEDAL in table
    foot_only = bool(hat.get("foot_only"))
    hat_on = _old_on(hat, groove_hand or groove_foot, rules)
    open_on = _old_on(open_hat, groove_open, rules) and not foot_only
    hat_pattern = hat.get("pattern", "style") if isinstance(hat.get("pattern"), str) else "style"
    open_pattern = open_hat.get("pattern", "style") if isinstance(open_hat.get("pattern"), str) else "style"
    generic_hat = {key for key, _w, _r in GENERIC["hat"]}
    generic_open = {key for key, _w, _r in GENERIC["hat"] if key.startswith("open_")}

    # The hand's rhythm tokens, and what the foot plays (None: nothing). Kept even for a piece that was off: 0.9.7
    # still worked out an off piece's chosen pattern before leaving its notes out, and a fill's random choices
    # went by how many hi-hat notes there were, so the fills only come out the same with the rhythm still there
    # (old_off says what was off).
    hand, foot_pattern = _old_hand_tokens(hat_pattern, generic_hat)
    if foot_only:                             # 0.9.7: the foot's own rows, else two and four (not on metal, hard rock)
        # (a pattern of None had no rows, so no foot of its own: the foot went on two and four; the review of
        # 25 Oct 2026)
        has_foot = foot_pattern == "style" and groove_foot or foot_pattern == "g:pedal" or (
            foot_pattern or "").startswith("v") and PEDAL in style_table(
                style_key, max(1, min(pv.count("anvil", style_key), _number(foot_pattern[1:]) or 1)), base_tables)
        if hat.get("steps") and _steps_of(hat["steps"], (PEDAL,)):
            has_foot = True
        if not has_foot:
            foot_pattern = "g:pedal" if style_key not in OLD_HAT_FOOTLESS_STYLES else None
    if not hat_on:
        foot_pattern = None                   # the Closed hi-hat off: its foot was off with it (at foot only too:
        #                                       the review of 24 Oct 2026; the foot came on by itself before)
    opened = []
    if True:
        if open_pattern in ("style",) or open_pattern.startswith("v") and _number(open_pattern[1:]) is not None:
            opened.append("o:" + open_pattern)
        elif open_pattern.startswith("g:") and "open_" + open_pattern[2:] in generic_open:
            opened.append("g:open_" + open_pattern[2:])
        elif open_pattern == "none":
            opened.append("o:none")           # (an Open hi-hat at None worked that out as a pattern of its own)
        else:
            opened.append("o:style")

    new_hat = {key: value for key, value in hat.items()
               if key not in ("on", "pattern", "steps", "foot_only", "for_hats", "level", "busy")}
    tokens = hand + opened
    if tokens:
        # only the two pieces' own patterns are the Hi-hat's own: another with the same rows (a variation's that
        # happens to be the same) was worked out as a pattern of its own, with random choices of its own and
        # without the performance's hi-hat accents (the review of 24 Oct 2026; it was taken for the style's)
        pattern = "+".join(tokens)
        if tokens == ["c:style", "o:style"]:
            pattern = "style"
        elif tokens == ["o:none"]:
            pattern = "none"
        if pattern != "style":
            new_hat["pattern"] = pattern
        if "on" in hat and hat["on"] and pattern == "style":
            new_hat["on"] = True
    level = hat.get("level", LEVEL_DEFAULT) if hat_on or foot_only else open_hat.get("level", LEVEL_DEFAULT)
    if level != LEVEL_DEFAULT:
        new_hat["level"] = level
    if open_on and open_hat.get("level", LEVEL_DEFAULT) != level:
        new_hat["open_level"] = open_hat.get("level", LEVEL_DEFAULT)
    busy = hat.get("busy", BUSY_DEFAULT) if hand else open_hat.get("busy", BUSY_DEFAULT)
    if busy != BUSY_DEFAULT:
        new_hat["busy"] = busy
    if opened and open_hat.get("busy", BUSY_DEFAULT) != BUSY_DEFAULT:
        new_hat["open_busy"] = open_hat.get("busy", BUSY_DEFAULT)   # (its own, under the old rules)
    hat_steps = hat.get("steps") if isinstance(hat.get("steps"), dict) and hat["steps"].get("bars") else None
    open_steps = (open_hat.get("steps") if isinstance(open_hat.get("steps"), dict) and open_hat["steps"].get("bars")
                  else None)
    # (a Closed hi-hat that was off played none of its steps: the review of 25 Oct 2026, they came in under an
    # Open hi-hat that played)
    closed_steps, opened_steps = _steps_of(hat_steps if hat_on else None, (HAT,)), _steps_of(open_steps, (OPEN_HAT,))
    steps = _merge_steps(closed_steps, opened_steps)
    if closed_steps and opened_steps and len(closed_steps["bars"]) != len(opened_steps["bars"]):
        new_hat["old_bars"] = [len(closed_steps["bars"]), len(opened_steps["bars"])]
    if steps is None and (hat_steps and hat_on or open_steps):
        steps = _silent_steps(hat_steps, open_steps)    # every step off: a hand-made silence, kept silent
    if steps:
        new_hat["steps"] = steps
    # (at foot only, 0.9.7 kept only the foot's steps of the Closed hi-hat's, and none when it had none)
    had = [name for name, found in (("hat", hat_steps and (not foot_only or _steps_of(hat_steps, (PEDAL,)))),
                                    ("open", open_steps)) if found]
    if had:
        # which old piece the steps were made for, so under the old rules each is applied to that piece's sounds
        # (players._KitPieces.finish; the review of 24 Oct 2026: the Open hi-hat's steps took the closed hi-hat's
        # groove out too, and the Closed hi-hat's steps left the groove's foot playing)
        new_hat["old_steps"] = "both" if len(had) == 2 else had[0]
    if foot_only:
        new_hat["on"] = False
        new_hat["off_for"] = "ride"
    elif not (hat_on or open_on):
        new_hat["on"] = False
    elif hat_on != open_on and (hand if not hat_on else opened):
        new_hat["old_off"] = ("closed" if hat.get("on") is False else "closed_groove") if not hat_on else "open"
        if "on" in hat or "on" in open_hat:
            new_hat["on"] = True
    if new_hat:
        out["hat"] = new_hat

    foot_steps = _steps_of(hat_steps, (PEDAL,)) if hat_on else None
    if foot_steps is None and hat_steps and hat_on and foot_pattern is not None and not foot_only:
        foot_steps = _silent_steps(hat_steps)         # (the Closed hi-hat's steps had no foot: the foot was silent)
    pedal = {}
    if foot_pattern is None and not foot_steps:
        pedal["on"] = False
    else:
        if foot_pattern not in (None, "style"):
            pedal["pattern"] = foot_pattern
        if "on" in hat and hat["on"] and foot_pattern == "style" and groove_foot:
            pedal["on"] = True                # (turned on by hand with a foot in the groove: it stays turned on)
        if foot_only:
            pedal["on"] = True                # (the foot's steps, or its pattern, played under the ride)
        for key in ("level", "busy"):
            default = LEVEL_DEFAULT if key == "level" else BUSY_DEFAULT
            if hat.get(key, default) != default:
                pedal[key] = hat[key]
    if foot_steps:
        pedal["steps"] = foot_steps
        if not foot_only:
            pedal.pop("on", None)
    if pedal:
        out["pedal"] = pedal

    if "for_hats" in ride or (ride.get("pattern") or "").startswith(HAT_RHYTHM):
        new_ride = {key: value for key, value in ride.items() if key != "for_hats"}
        if (ride.get("pattern") or "").startswith(HAT_RHYTHM):
            # "The hi-hat's rhythm" named the old Closed hi-hat's pattern, played with the groove's open hi-hat
            # (0.9.7's hand_hat_row): the same as the Hi-hat's pattern made of those two
            tokens = _old_hand_tokens(ride["pattern"][len(HAT_RHYTHM):], generic_hat)[0] + ["o:style"]
            new_ride["pattern"] = HAT_RHYTHM + ("style" if tokens == ["c:style", "o:style"] else "+".join(tokens))
        if ride.get("for_hats") and not _old_on(ride, bool(piece_rows(table, PIECE_BY_KEY["ride"])), rules):
            new_ride["on"] = False            # ("for the hi-hats" only marked a ride that was off)
            new_ride["off_for"] = "hat"
        if new_ride:
            out["ride"] = new_ride
        else:
            out.pop("ride", None)
    return out


def old_kit_levels_to_new(raw):
    """A track's kit-piece loudness saved before 0.9.8: the Hi-hat pedal gets the Closed hi-hat's (it played the
    foot), and where the Open hi-hat's differed from the Closed hi-hat's (50 when it was not saved), it is kept as
    OLD_OPEN_HAT, so the open hi-hat notes of an older project keep their loudness (the review of 25 Oct 2026: it
    was dropped, so they played at the Hi-hat's). It goes when the kit's loudness is changed in Track settings."""
    if not isinstance(raw, dict) or "open_hat" not in raw and "pedal" in raw:
        return raw
    out = {key: value for key, value in raw.items() if key not in ("open_hat", OLD_OPEN_HAT)}
    if "hat" in raw and "pedal" not in raw:
        out["pedal"] = raw["hat"]
    closed, opened = raw.get("hat", LEVEL_DEFAULT), raw.get("open_hat", LEVEL_DEFAULT)
    if opened != closed:
        out[OLD_OPEN_HAT] = opened
    return out


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
    or more ghost notes were asked of it. The Hi-hat pedal also plays by itself where its drummer keeps a foot going
    (pedal_default_on). Off only takes a piece out of the groove: fills use the whole kit, and the crashes where a
    section starts and after fills follow the crash's When setting (from rules 2; see players._KitPieces). The part
    is always on."""
    piece = PIECE_BY_KEY[piece_key]
    if piece.kind == "part":
        return True
    stored = (settings.get("pieces") or {}).get(piece_key) or {}
    if "on" in stored:
        return bool(stored["on"])
    if piece_key == "pedal" and not has_groove and stored.get("pattern", "style") == "style" and not stored.get(
            "steps") and settings.get("style") in PEDAL_STYLES and settings.get("rules", 1) >= 4:
        return True                                     # a quiet foot on two and four (PEDAL_STYLES)
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
            ("disco", "disco sixteenths (open on the and of each beat)", {HAT: (_row("xxxxxxxxxxxxxxxx"), 74, "")}),
            ("open_offbeats", "open on the and of every beat", {OPEN_HAT: (_row("..x...x...x...x."), 88, "")}),
            ("open_and_of_four", "open on the and of four", {OPEN_HAT: (_row("..............x."), 88, "")}),
            ("open_quarters", "open on every beat", {OPEN_HAT: (_row("x...x...x...x..."), 90, "")})],
    # the foot (0.9.8): its first pattern is what the pedal plays by itself where the groove has no foot (pedal_rows)
    "pedal": [("pedal", "the foot pedal on two and four", {PEDAL: (_row("....x.......x..."), 78, "")}),
              ("beats", "the foot pedal on every beat", {PEDAL: (_row("x...x...x...x..."), 72, "")}),
              ("one_three", "the foot pedal on one and three", {PEDAL: (_row("x.......x......."), 76, "")})],
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

    # (a variation with none of this piece: "off"; Russell, 25 Oct 2026, the only time something is not in the
    # groove is if it's off, so choosing it turns the piece off, session_music._apply_piece_change)
    options = [("style", words_at_tempo("As variation {} plays it: {}".format(
        variation, rows_words(own, kit_program) if own else "off"), own))]
    seen = {_rows_key(own)}
    for number in range(1, pv.count("anvil", style_key) + 1):
        if number == variation:
            continue
        rows = piece_rows(style_table(style_key, number, base_tables), piece)
        if rows and _rows_key(rows) not in seen and playable(rows, "v{}".format(number)):
            seen.add(_rows_key(rows))
            options.append(("v{}".format(number), words_at_tempo("Variation {}'s: {}".format(
                number, rows_words(rows, kit_program)), rows)))
    if piece_key == "hat" and chosen and chosen not in [key for key, _words in options] and (
            "+" in chosen or chosen[:2] in ("c:", "o:")):
        # the pattern a region saved before 0.9.8 keeps from its two hi-hat pieces (old_pieces_to_new), named for
        # what it plays (the review of 24 Oct 2026: the window said "The pattern chosen before" and no more); it is
        # listed while it is the choice, and Control+Z brings it back once another is chosen
        rows = drum_pattern_rows(style_key, variation, piece_key, chosen, base_tables)
        if rows is not None:
            seen.add(_rows_key(rows))
            words = "As the closed and open hi-hat pieces played it before: {}".format(
                rows_words(rows, kit_program) if rows else "none in the groove")
            options.insert(1, (chosen, words_at_tempo(words, rows)))
    if piece_key == "ride":
        # the hi-hat's rhythm on the ride (TAKES_TURNS): the variation's own when its hi-hat has one, and the one
        # chosen when it is another
        hat_hand = hand_hat_row(style_key, variation, "style", base_tables) is not None
        keys = [HAT_RHYTHM + "style"] if hat_hand or chosen == HAT_RHYTHM + "style" else []
        if (chosen or "").startswith(HAT_RHYTHM) and chosen not in keys:
            keys.append(chosen)
        for key in keys:
            rows = hat_rhythm_rows(style_key, variation, key[len(HAT_RHYTHM):], base_tables)
            if key == chosen or (_rows_key(rows) not in seen and playable(rows, key)):
                seen.add(_rows_key(rows))
                options.append((key, words_at_tempo("The hi-hat's {}rhythm: {}".format(
                    "" if key == HAT_RHYTHM + "style" else "chosen ", rows_words(rows, kit_program)), rows)))
    if own and chosen == "none":
        # (only while it is the choice, in a region saved before 0.9.9: to take a piece out of the groove now, turn
        # it off; Russell, 25 Oct 2026)
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
    if pattern.startswith(HAT_RHYTHM) and piece_key == "ride":
        # (before the "+" below: the hi-hat's pattern after "h:" can be one of two parts)
        return hat_rhythm_rows(style_key, variation, pattern[len(HAT_RHYTHM):], base_tables)
    if "+" in pattern and piece_key == "hat":
        # two rhythms at once (only from a region saved before 0.9.8, whose Closed hi-hat and Open hi-hat each had a
        # pattern of their own, now one Hi-hat): the union of both
        rows = {}
        for part in pattern.split("+"):
            found = drum_pattern_rows(style_key, variation, piece_key, part, base_tables)
            if found is None:
                found = piece_rows(style_table(style_key, variation, base_tables), piece)
            rows.update(found)
        return rows
    if piece_key == "hat" and pattern[:2] in ("c:", "o:"):
        # the closed (c:) or the open (o:) hi-hat alone of the groove ("c:style") or a variation ("o:v2"); only from
        # a region saved before 0.9.8, where the two were separate pieces
        voice = HAT if pattern[0] == "c" else OPEN_HAT
        rows = drum_pattern_rows(style_key, variation, piece_key, pattern[2:], base_tables)
        if rows is None:
            rows = piece_rows(style_table(style_key, variation, base_tables), piece)
        return {k: v for k, v in rows.items() if k == voice}
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


# the styles that crash after their fills (not jazz and the hand percussion)
CRASH_AFTER_FILLS = ("dubstep", "house", "trap", "rock", "hard_rock", "metal", "funk", "pop")


def describe_piece(settings, piece_key, has_groove=True, kit_program=None, kit_notes=None):
    """The line in the Kit pieces list: 'Crash cymbals: on, where the region starts and after fills, crash'.
    kit_notes: the notes the kit has (None: every drum note), so a piece or sound the kit lacks is said."""
    piece = PIECE_BY_KEY[piece_key]
    full = piece_settings(settings, piece_key)
    words = []
    if piece.kind != "part":
        state = turn_state(settings, piece_key, has_groove)
        words.append(state)
        if state == "off" and (piece_key in TAKES_TURNS or piece_key == "crash") and full["off_for"]:
            words.append("the {} keeps time".format(TURN_NAMES[full["off_for"]]))   # the other took its turn
        if not kit_voices(piece, kit_notes):
            words.append("not in this kit")
    # a piece's pattern is said only while it plays (Russell, 24 Oct 2026: "Ride: off, the hi-hat keeps time", not
    # "..., the hi-hat's rhythm"); a piece that is off says why, not what it would play
    off = piece.kind != "part" and state == "off"
    if full["pattern"].startswith(HAT_RHYTHM) and piece_key == "ride":
        if not off:
            words.append("the hi-hat's rhythm")
    elif full["pattern"] != "style":
        if not off:
            words.append("pattern changed")
    elif piece.kind not in ("part", "crash") and not has_groove and not full["steps"] and kit_voices(piece, kit_notes):
        if piece_key == "pedal" and state == "on":
            words.append("the foot on two and four")      # by itself (PEDAL_STYLES)
        else:
            if piece.kind == "toms":
                words.append("in fills only")
            # (no "not in this groove": Russell, 25 Oct 2026, "the only time something is not in the groove is if
            # it's off"; a piece turned on plays a pattern of its own, and one that is off just says off)
    if piece.kind == "crash":
        when = choice_words("when", full["when"])
        if full["when"] == "accents" and settings.get("follow") != "track":
            when += " (nothing is followed, so where the style plays them)"
        words.append(when)
        cymbals = dict(WHICH).get(full["which"], (CRASH,))
        words.append(which_words(full["which"], kit_program) + missing_words(cymbals, kit_notes, kit_program))
        if (full["which"] == "crash1" and settings.get("rules", 1) < 3 and settings.get("style") in CRASH_AFTER_FILLS
                and full["when"] == "start_and_fills"):
            # a region from before 0.9.7 plays as it did: 3 crashes after a fill in 10 on the second crash (the musical
            # review, 23 Oct 2026; changed in the editor, it plays crash 1 only)
            words[-1] += " (after a fill now and then the {})".format(note_name(CRASH2, kit_program))
    for key in EXTRAS.get(piece.kind, ()):
        # (the ghost notes' loudness is said further down, with the other loudness; until the final review of
        # 10 Oct 2026 it fell through to here, and any value but 50 raised an error that broke the Kit pieces list)
        if key in ("when", "which", "ghost_level") + TURN_KEYS or full[key] == DRUM_DEFAULTS[key]:
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
