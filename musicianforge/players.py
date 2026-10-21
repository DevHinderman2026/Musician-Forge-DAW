"""Rhythm players: Anvil (drums), Bellows (bass), Ember (keys), Spark (synth) and Hammer (guitar).

A rhythm player region holds no notes of its own. Its notes are worked out from its settings by
one function, perform(), whose inputs are the style, its variation, intensity, complexity, fills,
swing, the pieces' own settings, the chords it plays (from the chord track), the hits of the track
it follows, the region's length and a performance number. The same inputs always give exactly the
same notes: every random choice comes from a generator seeded with those settings (and the bar
number), never from the clock. So undo and redo are exact, and a reopened project plays the same
performance.

Each style is a set of rules: where the kick, snare and hi-hat go in a dubstep bar, how a
walking bass approaches the next chord, how a metal guitarist gallops. Since 0.9.2 (Russell,
8 Oct 2026: "super important") a style has real variations (player_variations.py): each is a
recognisably different groove or part, chosen by number. Reforge never changes the variation: it
moves to another performance number, which changes the fills and the small details (ghost notes,
which extra hits come, the voicings), so a reforged dubstep bar keeps its groove. Variation 1 is
each style exactly as it was in 0.8, and an older project's old "variation" number becomes its
performance number, so older projects sound exactly the same.

Pieces (0.9.2, player_pieces.py): Anvil's kit pieces and the other players' parts each have their
own settings (on or off, pattern, extras, hand-made steps); with every piece at its default the
notes are exactly what the style plays.

Follow: a player can lock its rhythm to another track's hits (note starts, or the hits found
in a recording). Pitches always come from the chord track.
"""

import hashlib
import json
import random
from dataclasses import dataclass, field

from . import chords as chordtrack
from . import player_pieces as pp
from . import player_variations as pv
from .song import Note
from .timeline import PPQ

STEP = PPQ // 4                  # a sixteenth note
GROUP_ELECTRONIC, GROUP_ACOUSTIC, GROUP_PERCUSSION = "Electronic", "Acoustic", "Percussion"

# ----------------------------------------------------------------------
# players and styles
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class Style:
    key: str
    name: str
    description: str
    patch: tuple                 # default (bank, program, name)
    group: str = ""              # drums only: Electronic, Acoustic or Percussion
    swing: int = 0               # the style's own swing (0 to 100)
    follow: str = "chords"       # the default Follow setting


@dataclass(frozen=True)
class Player:
    key: str
    name: str
    role: str                    # "drums", "bass", "keys", "synth" or "guitar"
    styles: tuple

    def style(self, key):
        for style in self.styles:
            if style.key == key:
                return style
        return self.styles[0]

    @property
    def title(self):
        return "{}, {}".format(self.name, self.role)


FORGE_DUBSTEP_KIT = (128, 100, "Forge Dubstep Kit")
FORGE_HOUSE_KIT = (128, 101, "Forge House Kit")
FORGE_TRAP_KIT = (128, 102, "Forge Trap Kit")
FORGE_808 = (100, 38, "Forge 808 Sub")
GUITAR_PACK_1 = (40, 0, "FSBS Electric Guitar Distorted 1")
GUITAR_PACK_2 = (41, 0, "FSBS Electric Guitar Distorted 2")
STAND_IN_GUITAR = (0, 30, "Distortion Guitar")

ANVIL = Player("anvil", "Anvil", "drums", (
    Style("dubstep", "Dubstep", "Half time at full weight: the kick on one, a huge snare on three, busy hats.",
          FORGE_DUBSTEP_KIT, GROUP_ELECTRONIC, 0, "none"),
    Style("house", "House", "Four on the floor, claps on two and four, open hats on the offbeats, a shaker.",
          FORGE_HOUSE_KIT, GROUP_ELECTRONIC, 30, "none"),
    Style("trap", "Trap", "Half time with syncopated kicks, crisp claps and hi-hat rolls in 32nds and triplets.",
          FORGE_TRAP_KIT, GROUP_ELECTRONIC, 0, "none"),
    Style("rock", "Rock", "A straight rock beat: kick on one and three, snare on two and four, eighth hats.",
          (128, 8, "Room"), GROUP_ACOUSTIC, 0, "none"),
    Style("hard_rock", "Hard rock", "Big and driving: pushed kicks, open hats and crashes on the downbeats.",
          (128, 16, "Power"), GROUP_ACOUSTIC, 0, "none"),
    Style("metal", "Metal", "Double kick in eighths and sixteenths, a solid backbeat, china and crash accents.",
          (128, 16, "Power"), GROUP_ACOUSTIC, 0, "none"),
    Style("jazz", "Jazz", "Swinging ride cymbal, hi-hat on two and four, feathered kick and comping snare.",
          (128, 32, "Jazz"), GROUP_ACOUSTIC, 60, "none"),
    Style("funk", "Funk", "Syncopated sixteenth-note kicks, ghost notes on the snare, tight sixteenth hats.",
          (128, 2, "Standard 3"), GROUP_ACOUSTIC, 15, "none"),
    Style("pop", "Pop", "A clean, steady pop beat with eighth hats and a tambourine when it builds.",
          (128, 0, "Standard 1"), GROUP_ACOUSTIC, 0, "none"),
    Style("hand_percussion", "Hand percussion", "Congas, bongos and claves in a Latin-flavoured groove.",
          (128, 0, "Standard 1"), GROUP_PERCUSSION, 10, "none"),
    Style("shakers", "Shakers and tambourine", "A shaker in sixteenths and a tambourine on the backbeat.",
          (128, 0, "Standard 1"), GROUP_PERCUSSION, 10, "none"),
))

BELLOWS = Player("bellows", "Bellows", "bass", (
    Style("eighths", "Driving eighths", "Steady eighth notes on the chord's root, with octave jumps as it gets "
          "more complex.", (0, 34, "Pick Bass")),
    Style("roots", "Root notes", "Long notes on the chord's root: simple and solid.", (0, 33, "Finger Bass")),
    Style("funk", "Funk", "Syncopated sixteenths, octave pops and ghost notes.", (0, 36, "Slap Bass 1"), swing=15),
    Style("walking", "Walking", "A jazz walking line in quarter notes that leads into each new chord.",
          (0, 32, "Acoustic Bass"), swing=60),
    Style("dubstep", "Dubstep sub", "Deep sub-bass in half time, with drops to the low octave.", FORGE_808),
    Style("house", "House offbeat", "Short offbeat notes that bounce against a four-on-the-floor kick.",
          (0, 38, "Synth Bass 1"), swing=30),
    Style("trap", "Trap 808", "Long 808 notes on syncopated hits, following the chords.", FORGE_808),
    Style("metal", "Metal gallop", "Low root notes in gallops and sixteenth chugs, locked with the guitar.",
          (0, 34, "Pick Bass")),
))

EMBER = Player("ember", "Ember", "keys", (
    Style("block", "Block chords", "Full chords on the downbeats, with the root in the left hand.",
          (0, 0, "Grand Piano")),
    Style("pulse", "Pop pulse", "Chords pulsing in eighth notes.", (0, 0, "Grand Piano")),
    Style("arpeggio", "Ballad arpeggio", "Broken chords flowing up and down.", (0, 0, "Grand Piano")),
    Style("comping", "Jazz comping", "Short, syncopated chords with sevenths and ninths.", (0, 4, "Electric Piano 1"),
          swing=60),
    Style("stabs", "Funk and house stabs", "Short offbeat chord stabs.", (0, 4, "Electric Piano 1"), swing=20),
))

SPARK = Player("spark", "Spark", "synth", (
    Style("pad", "Pad", "Sustained chords that change smoothly.", (0, 89, "Warm Pad")),
    Style("arp_up", "Arpeggio up", "Chord notes climbing in sixteenths.", (0, 81, "Saw Lead")),
    Style("arp_updown", "Arpeggio up and down", "Chord notes climbing and falling.", (0, 80, "Square Lead")),
    Style("pluck", "Pluck sequence", "A rhythmic pluck pattern on the chord notes.", (0, 81, "Saw Lead")),
    Style("gate", "Trance gate", "The chord chopped into a sixteenth-note rhythm.", (0, 90, "Polysynth")),
    Style("stabs", "Dubstep stabs", "Hard, syncopated chord stabs.", (0, 81, "Saw Lead")),
))

HAMMER = Player("hammer", "Hammer", "guitar", (
    Style("chugs", "Power chord chugs", "Tight, muted power chords in sixteenths, accented on the beat.",
          GUITAR_PACK_1),
    Style("gallop", "Metal gallop", "An eighth and two sixteenths on every beat.", GUITAR_PACK_1),
    Style("hard_rock", "Hard rock riff", "Power chords in eighths, ringing on the big beats, with pickups.",
          GUITAR_PACK_2),
    Style("palm_eighths", "Muted eighths", "Steady muted eighth notes on the root power chord.", GUITAR_PACK_2),
    Style("strum", "Rock strum", "Full chords strummed down and up.", GUITAR_PACK_2),
    Style("arpeggio", "Picked chords", "Chord notes picked one at a time.", GUITAR_PACK_2),
))

PLAYERS = {p.key: p for p in (ANVIL, BELLOWS, EMBER, SPARK, HAMMER)}
PLAYER_ORDER = ["anvil", "bellows", "ember", "spark", "hammer"]

DEFAULTS = {"intensity": 60, "complexity": 40, "fills": 40, "fill_complexity": 50, "follow_amount": 70, "sensitivity": 50,
            "variation": 1, "performance": 1, "play_after_reforge": True}
SETTING_RANGES = {"intensity": (0, 100), "complexity": (0, 100), "fills": (0, 100), "fill_complexity": (0, 100),
                  "swing": (0, 100),
                  "follow_amount": (0, 100), "sensitivity": (0, 100)}
# Reforge picks a performance at random from this many (Russell, 21 Oct 2026: "9999 possibilities ... there should be
# way more than that ... picked at random and it should be pretty much infinite"). 2**53 - 1 is the largest whole
# number every JSON reader keeps exactly; a project saved before keeps its own number (1 to 9999 are in here too).
MAX_PERFORMANCE = 2 ** 53 - 1
# Rules a region plays by (Russell, 10 Oct 2026: "make this project the exception of all these changes unless I
# manually change something"). 1: as before 10 Oct 2026, 3 PM (louder drums, fills only at phrase ends, no piece
# Complexity of its own, fewer fill shapes, no hi-hat builds or per-performance habits); 2: today's. A region saved
# before has no "rules", so it keeps 1 until it is changed in the editor (session_music.py); new regions get 2.
RULES = 2


def new_rules(settings):
    return settings.get("rules", 1) >= 2


_CHANCE = random.SystemRandom()          # Reforge's own random numbers: never the same sequence twice


def random_performance(current=None):
    """A performance number picked at random, never the one playing now: which fills come where, their shapes, the
    ghost notes, accents and voicings all follow from it, so each Reforge is a new draw from about nine quadrillion."""
    while True:
        number = _CHANCE.randint(1, MAX_PERFORMANCE)
        if number != current:
            return number


def style_label(player, style):
    return "{}: {}".format(style.group, style.name) if style.group else style.name


def new_settings(player_key, style_key=None):
    """A rhythm player region's settings, starting from a style's defaults."""
    player = PLAYERS[player_key]
    style = player.style(style_key) if style_key else player.styles[0]
    settings = {"player": player.key, "style": style.key, "swing": style.swing,
                "swing_note": natural_swing_note(player.key, style.key), "follow": style.follow,
                "follow_track": None}
    settings.update(DEFAULTS)
    settings["rules"] = RULES
    settings["pieces"] = {}
    return settings


def _whole(value, low, high, default):
    try:
        return int(max(low, min(high, int(value))))
    except (TypeError, ValueError, OverflowError):
        return default


def clean_settings(raw):
    """Valid settings from a project file (anything damaged gets its default).

    Settings saved before 0.9.2 have no "performance": their "variation" was the seed of the performance, so it
    becomes the performance, and the variation is 1 (the style as it was), which plays exactly the same notes."""
    if not isinstance(raw, dict) or not isinstance(raw.get("player"), str) or raw["player"] not in PLAYERS:
        return None
    player = PLAYERS[raw["player"]]
    settings = new_settings(player.key, raw.get("style") if raw.get("style") in [s.key for s in player.styles]
                            else None)
    for key, (low, high) in SETTING_RANGES.items():
        if key in raw:
            settings[key] = _whole(raw[key], low, high, settings[key])
    if "performance" in raw:
        settings["performance"] = _whole(raw["performance"], 1, MAX_PERFORMANCE, 1)
        settings["variation"] = _whole(raw.get("variation", 1), 1, variation_count(settings), 1)
    else:
        settings["performance"] = _whole(raw.get("variation", 1), 1, MAX_PERFORMANCE, 1)
        settings["variation"] = 1
    if raw.get("swing_note") in SWING_NOTES:      # older projects have none: the style's own, as they played
        settings["swing_note"] = raw["swing_note"]
    if raw.get("follow") in ("chords", "track", "none"):
        settings["follow"] = raw["follow"]
    if isinstance(raw.get("follow_track"), int):
        settings["follow_track"] = raw["follow_track"]
    settings["play_after_reforge"] = bool(raw.get("play_after_reforge", True))
    settings["rules"] = raw.get("rules") if raw.get("rules") in (1, RULES) else 1
    settings["pieces"] = pp.clean_pieces(player.key, raw.get("pieces"))
    return settings


def variation_count(settings):
    return pv.count(settings["player"], settings["style"])


def describe_variation(settings, number=None):
    """'Variation 2 of 6: kick on one and the and of two, hi-hats in eighths'."""
    number = settings["variation"] if number is None else number
    return "Variation {} of {}: {}".format(number, variation_count(settings),
                                         pv.description(settings["player"], settings["style"], number))


def describe_settings(settings):
    player = PLAYERS[settings["player"]]
    style = player.style(settings["style"])
    return "{}, {}".format(player.title, style.name)


# ----------------------------------------------------------------------
# the inputs
# ----------------------------------------------------------------------
@dataclass
class Hit:
    """One hit of the followed part: when, how strong (0 to 1) and how low (0 high to 1 deep)."""

    tick: int
    weight: float
    low: float = 0.0


@dataclass
class Performance:
    notes: list
    fill_bars: list = field(default_factory=list)       # song bar numbers that have fills
    accents: int = 0                                      # accents in the followed part
    matched: int = 0                                      # accents the player locked to
    hits: int = 0                                         # hits found in the followed part


def hits_from_notes(notes, start, end, timeline):
    """The hits of a part played with notes: each note start, weighted by loudness, lowness and
    whether it falls on a beat. Notes starting together count as one hit."""
    by_tick = {}
    for note in notes:
        if start <= note.tick < end:
            by_tick.setdefault(note.tick, []).append(note)
    hits = []
    for tick in sorted(by_tick):
        group = by_tick[tick]
        loud = max(n.velocity for n in group) / 127.0
        low = max(0.0, min(1.0, (72 - min(n.pitch for n in group)) / 36.0))
        bar = timeline.tick_to_bar(tick)
        beat_ticks = timeline.ticks_per_beat(bar)
        on_beat = 1.0 if (tick - timeline.bar_to_tick(bar)) % beat_ticks == 0 else 0.0
        weight = min(1.0, 0.55 * loud + 0.25 * low + 0.2 * on_beat + 0.05 * (len(group) - 1))
        hits.append(Hit(tick, weight, low))
    return hits


def accents(hits):
    """The hits that stand out: the stronger half (and every hit above 0.75)."""
    if not hits:
        return []
    weights = sorted(h.weight for h in hits)
    middle = weights[len(weights) // 2]
    return [h for h in hits if h.weight >= min(middle, 0.75)]


# ----------------------------------------------------------------------
# seeded choices
# ----------------------------------------------------------------------
def _seed(settings, salt):
    """The performance's random choices for one bar (salt). Variation 1 is seeded exactly as every performance was
    before 0.9.2 (the performance number in the place of the old variation number), so older projects play the
    same notes; another variation adds its number."""
    # Intensity is left out (0.9.4): it changes only how hard the notes are played, so moving it never changes which
    # notes there are
    keys = ("player", "style", "complexity", "fills", "swing")
    values = [settings.get(k) for k in keys] + [settings.get("performance", 1)]
    if settings.get("variation", 1) > 1:
        values += ["variation", settings["variation"]]
    text = json.dumps(values + [salt], sort_keys=True)
    return int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")


def _piece_seed(settings, piece_key, salt):
    """Random choices that belong to one piece's own settings, kept apart from the performance's, so changing a
    piece never changes what the other pieces play."""
    return _seed(settings, ["piece", piece_key, salt])


# ----------------------------------------------------------------------
# the meter: every time signature, not only 4/4 (Russell, 10 Oct 2026: "If I switch the time signature the drummer
# should play in 3/4 time. Same with all the other session players")
# ----------------------------------------------------------------------
def pulse_lengths(numerator, denominator, steps):
    """The beats a player feels in one bar, as lengths in sixteenths: quarter notes in 3/4, 5/4 or 7/4 (and in 2/2,
    counted in quarters); dotted quarters in 6/8, 9/8 and 12/8; eighths grouped in twos with a three at the end in
    5/8 and 7/8 (7/8 is 2+2+3); sixteenths grouped in fours in x/16."""
    lengths = []
    if denominator <= 4:
        lengths = [4] * (steps // 4)
    elif denominator == 8:
        if numerator % 3 == 0:
            lengths = [6] * (numerator // 3)
        elif numerator == 1:
            lengths = [2]
        else:
            lengths = [4] * ((numerator - 3) // 2) + [6] if numerator % 2 else [4] * (numerator // 2)
    elif denominator == 16:
        lengths = [4] * (numerator // 4)
        rest = numerator % 4
        if rest == 1 and lengths:
            lengths[-1] += 1
        elif rest:
            lengths.append(rest)
    if not lengths or sum(lengths) != steps:
        lengths = [steps]
    return lengths


def pulse_roles(count):
    """Which beat of a 4/4 groove each beat of the bar plays: the first is one (the downbeat), the last is four (it
    leads into the next bar), and those between take two (the backbeat) and three in turn. 4/4 is 1 2 3 4; 3/4 and
    9/8 are 1 2 4; 6/8 is 1 2 (the snare on its second big beat); 5/4 is 1 2 3 2 4."""
    if count == 1:
        return [1]
    if count == 2:
        return [1, 2]
    if count == 3:
        return [1, 2, 4]
    return [1] + [2 if i % 2 == 0 else 3 for i in range(count - 2)] + [4]


def _inside(t, length):
    """Where sixteenth `t` of a beat `length` sixteenths long falls in a 4/4 beat (0 on the beat, 1 the e, 2 the and,
    3 the a): a dotted-quarter beat's three eighths are on the beat, and, and; its sixteenths between are e and a."""
    if length == 4:
        return t
    if length == 2:
        return (0, 2)[t]
    if length % 2 == 0:
        return 0 if t == 0 else (2 if t % 2 == 0 else (1 if t < length / 2.0 else 3))
    return min(3, int(round(t * 4.0 / length)))


class _Bar:
    """What a generator needs to know about one bar."""

    def __init__(self, number, start, end, steps, beat_steps, index, phrase_position, last_in_region, meter=(4, 4)):
        self.number = number            # the song's bar number
        self.start, self.end = start, end
        self.steps = steps              # sixteenths in the bar
        self.index = index              # 0 for the region's first bar
        self.phrase_position = phrase_position
        self.last_in_region = last_in_region
        self.tempo = None               # the fastest tempo in the bar (_bars sets it)
        lengths = pulse_lengths(meter[0], meter[1], steps)
        starts = [sum(lengths[:i]) for i in range(len(lengths))]
        self.pulses = list(zip(starts, lengths))             # (first sixteenth, length) of each beat
        self.beats = frozenset(starts)
        roles = pulse_roles(len(lengths))
        # each sixteenth's place in the style's 4/4 groove (0 to 15): 4/4 is itself, so it plays exactly as it did
        self.map = [0] * steps
        for (first, length), role in zip(self.pulses, roles):
            for t in range(length):
                if first + t < steps:
                    self.map[first + t] = (role - 1) * 4 + _inside(t, length)
        self.beat_steps = lengths[0] if len(set(lengths)) == 1 else beat_steps   # sixteenths in a beat
        if len(starts) > 1:            # the beat nearest the middle of the bar (the later one when two are as near)
            self.half = min(starts[1:], key=lambda st: (abs(st - steps / 2.0), -st))
        else:
            self.half = max(1, steps // 2)

    def pulse_at(self, step):
        """(first sixteenth, length) of the beat `step` falls in."""
        found = self.pulses[0]
        for pulse in self.pulses:
            if pulse[0] <= step:
                found = pulse
        return found

    def next_beat(self, step):
        """The first sixteenth of the beat after `step` (or the end of the bar)."""
        for first, _length in self.pulses:
            if first > step:
                return first
        return self.steps


def fastest_tempo(timeline, start, end):
    """The fastest tempo (quarter notes a minute) anywhere in [start, end)."""
    fastest = timeline.tempo_at_tick(start)
    for change in timeline.tempos:
        tick = timeline.position_to_tick(change.bar, change.beat)
        if start < tick < end:
            fastest = max(fastest, change.bpm)
    return fastest


def _bars(timeline, start, end):
    bars = []
    first = timeline.tick_to_bar(start)
    number = first
    index = 0
    while True:
        bar_start = max(start, timeline.bar_to_tick(number))
        bar_end = min(end, timeline.bar_to_tick(number + 1))
        if bar_start >= end:
            break
        full = timeline.ticks_per_bar(number)
        steps = max(1, full // STEP)
        beat_steps = max(1, timeline.ticks_per_beat(number) // STEP)
        signature = timeline.time_signature_at_bar(number)
        bars.append(_Bar(number, timeline.bar_to_tick(number), bar_end, steps, beat_steps, index, 0, False,
                         (signature.numerator, signature.denominator)))
        bars[-1].tempo = fastest_tempo(timeline, bar_start, bar_end)
        number += 1
        index += 1
    if bars:
        bars[-1].last_in_region = True
    for bar in bars:
        bar.phrase_position = bar.index % 4
    return bars


# Styles built on eighth notes swing their eighths; the others swing their sixteenths.
EIGHTH_SWING = {("anvil", "rock"), ("anvil", "hard_rock"), ("anvil", "jazz"), ("anvil", "pop"),
                ("bellows", "eighths"), ("bellows", "roots"), ("bellows", "walking"),
                ("ember", "block"), ("ember", "pulse"), ("ember", "arpeggio"), ("ember", "comping"),
                ("spark", "pad"), ("hammer", "hard_rock"), ("hammer", "palm_eighths"), ("hammer", "arpeggio")}


# Swing feel (Russell, 9 Oct 2026: a toggle between eighth-note and sixteenth-note swing). Each style starts on its
# own feel (EIGHTH_SWING), so a region made before the setting existed plays exactly as it did.
SWING_NOTES = ("eighth", "sixteenth")
SWING_NOTE_NAMES = {"eighth": "Eighth notes", "sixteenth": "Sixteenth notes"}


def natural_swing_note(player_key, style_key):
    return "eighth" if (player_key, style_key) in EIGHTH_SWING else "sixteenth"


def swing_grid(settings):
    """2 (sixteenths are swung, in pairs of steps) or 4 (eighths are swung): the region's Swing feel, or else its
    style's own."""
    note = settings.get("swing_note")
    if note not in SWING_NOTES:
        note = natural_swing_note(settings["player"], settings["style"])
    return 4 if note == "eighth" else 2


TRIPLET_LOCK_FROM = 30       # eighth swing from here: sixteenths are played as triplets (Russell, 10 Oct 2026)


def _swing_tick(bar, step, swing, grid):
    """Where an event on sixteenth `step` is heard. Eighth swing is left out of a dotted beat (6/8, 9/8, 12/8 and the
    long beat of 7/8 are already in threes); sixteenth swing pairs sixteenths in every beat."""
    tick = bar.start + int(round(step * STEP))
    if step != int(step) or swing <= 0:
        return tick                         # rolls in 32nds and triplets are not swung
    if grid == 4 and bar.pulse_at(int(step))[1] != 4:
        return tick
    return _swung(tick, bar.start, swing, grid)


def _triplet_lock(items, bar, swing, grid, voice, stays=None):
    """Eighth swing at TRIPLET_LOCK_FROM and more: in each beat of four sixteenths a note on the "a" joins the swung
    "and" (or is left out when the same sound already plays there), so a beat holds three notes in a triplet feel
    (one, the e at a third, the and at the swing) instead of a lopsided gallop (Russell, 10 Oct 2026: with eighth
    swing "the fills are a little rough"). items: (step, ...) tuples; voice(item): what counts as the same sound.
    stays(item): True for an item that keeps its place: the silent pedal note that closes a half-open hi-hat, whose
    own swung place on the "a" is already just after the swung "and" (moved onto the "and", it closed the next
    hi-hat the moment it was struck, so that one rang wide open: the final review, 10 Oct 2026)."""
    if grid != 4 or swing < TRIPLET_LOCK_FROM:
        return items
    taken = {(int(it[0]), voice(it)) for it in items if it[0] == int(it[0])}
    kept = []
    for item in items:
        step = item[0]
        if step == int(step) and 0 <= int(step) < bar.steps and not (stays is not None and stays(item)):
            first, length = bar.pulse_at(int(step))
            if length == 4 and int(step) - first == 3:
                target = first + 2
                if (target, voice(item)) in taken:
                    continue
                taken.add((target, voice(item)))
                item = (target,) + tuple(item[1:])
        kept.append(item)
    return kept


def _swung(tick, bar_start, swing, grid=2):
    """Swing: in each pair (two sixteenths when grid is 2 steps, two eighths when it is 4) the second
    one comes later. Swing 0 is straight; about 65 is a triplet feel; 100 puts it three quarters of the
    way through the pair. Notes in between (a sixteenth inside swung eighths) move in proportion, so a
    fill never lands on top of the swung note."""
    if swing <= 0:
        return tick
    span = grid * STEP
    position = tick - bar_start
    start = position - position % span
    inside = position - start
    half = span / 2.0
    late = half + span * 0.25 * swing / 100.0           # where the second note of the pair goes
    if inside < half:
        moved = inside * late / half
    else:
        moved = late + (inside - half) * (span - late) / half
    return bar_start + start + int(round(moved))


def _velocity(base, intensity, rng, spread=8):
    """How hard a note is played: Intensity's whole job (half as hard at 0, a quarter harder at 100)."""
    scale = 0.5 + 0.75 * intensity / 100.0
    return max(1, min(127, int(round(base * scale + rng.uniform(-spread, spread)))))


# ----------------------------------------------------------------------
# drums
# ----------------------------------------------------------------------
KICK, KICK2, SNARE, SNARE2, CLAP, RIM = 36, 35, 38, 40, 39, 37
HAT, PEDAL, OPEN_HAT = 42, 44, 46
TOM_HIGH, TOM_MID, TOM_LOW, TOM_FLOOR = 50, 48, 45, 41
CRASH, CRASH2, RIDE, RIDE_BELL, CHINA, SPLASH = 49, 57, 51, 53, 52, 55
TAMBOURINE, COWBELL, SHAKER, MARACAS = 54, 56, 82, 70
CONGA_MUTE, CONGA_OPEN, CONGA_LOW, BONGO_HIGH, BONGO_LOW, CLAVES = 62, 63, 64, 60, 61, 75
FORGE_SHAKER, FORGE_IMPACT, FORGE_RISER = 54, 52, 55

# For each style: voice -> (16 probabilities for one 4/4 bar at medium intensity, velocity).
# A probability of 1 is always played (the style's backbone); "i" scales a voice's other hits with
# complexity (an "i", from before 0.9.4, now does the same: intensity only changes how hard), "c" with complexity;
# a "g" marks a row of ghost notes (a variation's own), which the snare's
# Ghost notes setting turns off with the rest.
_DRUM_STYLES = {
    "dubstep": {
        KICK: ([1, 0, 0, 0, 0, 0, 0, 0, 0, 0, .25, 0, 0, 0, .15, 0], 118, "c"),
        SNARE: ([0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0], 120, ""),
        CLAP: ([0, 0, 0, 0, 0, 0, 0, 0, .6, 0, 0, 0, 0, 0, 0, 0], 100, "i"),
        HAT: ([1, .5, 1, .5, 1, .5, 1, .5, 1, .5, 1, .5, 1, .5, 1, .5], 80, "i"),
        OPEN_HAT: ([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, .35, 0], 85, "i"),
        FORGE_SHAKER: ([.4, .4, .4, .4, .4, .4, .4, .4, .4, .4, .4, .4, .4, .4, .4, .4], 60, "c"),
    },
    "house": {
        KICK: ([1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, .2], 115, ""),
        CLAP: ([0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0], 105, ""),
        OPEN_HAT: ([0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0], 90, ""),
        HAT: ([.7, .5, 0, .5, .7, .5, 0, .5, .7, .5, 0, .5, .7, .5, 0, .5], 65, "i"),
        FORGE_SHAKER: ([.6, .6, .6, .6, .6, .6, .6, .6, .6, .6, .6, .6, .6, .6, .6, .6], 55, "c"),
        RIM: ([0, 0, 0, .3, 0, 0, 0, 0, 0, .3, 0, 0, 0, 0, 0, .2], 70, "c"),
    },
    "trap": {
        KICK: ([1, 0, 0, .25, 0, 0, .3, .45, 0, 0, .4, 0, 0, .2, 0, 0], 118, "c"),
        CLAP: ([0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0], 112, ""),
        SNARE: ([0, 0, 0, 0, 0, 0, 0, 0, .7, 0, 0, 0, 0, 0, 0, .15], 100, "c"),
        HAT: ([1, .55, 1, .55, 1, .55, 1, .55, 1, .55, 1, .55, 1, .55, 1, .55], 82, "i"),
        OPEN_HAT: ([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, .25, 0], 80, "i"),
    },
    "rock": {
        KICK: ([1, 0, 0, 0, 0, 0, .2, 0, 1, 0, .3, 0, 0, 0, 0, 0], 112, "c"),
        SNARE: ([0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0], 112, ""),
        HAT: ([1, .2, 1, .2, 1, .2, 1, .2, 1, .2, 1, .2, 1, .2, 1, .2], 85, "i"),
        OPEN_HAT: ([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, .2, 0], 90, "i"),
    },
    "hard_rock": {
        KICK: ([1, 0, 0, 0, 0, 0, .5, 0, 1, 0, .6, 0, 0, 0, .2, 0], 118, "c"),
        SNARE: ([0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0], 120, ""),
        OPEN_HAT: ([.9, 0, .9, 0, .9, 0, .9, 0, .9, 0, .9, 0, .9, 0, .9, 0], 92, ""),
        HAT: ([0, .3, 0, .3, 0, .3, 0, .3, 0, .3, 0, .3, 0, .3, 0, .3], 70, "i"),
    },
    "metal": {
        KICK: ([1, .5, 1, .5, 1, .5, 1, .5, 1, .5, 1, .5, 1, .5, 1, .5], 115, "i"),
        SNARE: ([0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0], 122, ""),
        HAT: ([1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0], 88, ""),
        CHINA: ([0, 0, 0, 0, .2, 0, 0, 0, 0, 0, 0, 0, .2, 0, 0, 0], 100, "c"),
    },
    "jazz": {
        RIDE: ([1, 0, 0, 0, 1, 0, .9, 0, 1, 0, 0, 0, 1, 0, .9, 0], 82, ""),
        PEDAL: ([0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0], 70, ""),
        KICK: ([.45, 0, 0, 0, .45, 0, 0, 0, .45, 0, 0, 0, .45, 0, 0, .15], 45, "c"),
        SNARE: ([0, 0, .1, 0, 0, 0, .2, 0, 0, 0, .15, 0, 0, 0, .2, 0], 52, "c"),
    },
    "funk": {
        KICK: ([1, 0, 0, .35, 0, 0, .4, .3, 0, 0, .75, 0, 0, .25, 0, 0], 112, "c"),
        SNARE: ([0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0], 115, ""),
        HAT: ([1, .8, 1, .8, 1, .8, 1, .8, 1, .8, 1, .8, 1, .8, 1, .8], 78, "i"),
        OPEN_HAT: ([0, 0, 0, 0, 0, 0, 0, .3, 0, 0, 0, 0, 0, 0, 0, .3], 85, "c"),
    },
    "pop": {
        KICK: ([1, 0, 0, 0, 0, 0, .3, 0, 1, 0, .25, 0, 0, 0, 0, 0], 108, "c"),
        SNARE: ([0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0], 108, ""),
        HAT: ([1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0], 80, ""),
        TAMBOURINE: ([0, .4, 0, .4, .8, .4, 0, .4, 0, .4, 0, .4, .8, .4, 0, .4], 70, "i"),
    },
    "hand_percussion": {
        CONGA_MUTE: ([.8, 0, 0, 0, .8, 0, 0, 0, .8, 0, 0, 0, .8, 0, 0, 0], 80, ""),
        CONGA_OPEN: ([0, 0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 1, 1], 95, ""),
        CONGA_LOW: ([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, .5, 0, 0, 0, 0], 95, "c"),
        BONGO_HIGH: ([.9, .5, .9, .5, .9, .5, .9, .5, .9, .5, .9, .5, .9, .5, .9, .5], 70, "i"),
        BONGO_LOW: ([0, 0, 0, .4, 0, 0, 0, .4, 0, 0, 0, .4, 0, 0, 0, .4], 75, "c"),
        CLAVES: ([1, 0, 0, 1, 0, 0, 1, 0, 0, 0, 1, 0, 1, 0, 0, 0], 85, ""),
    },
    "shakers": {
        SHAKER: ([.9, .7, 1, .7, .9, .7, 1, .7, .9, .7, 1, .7, .9, .7, 1, .7], 70, ""),
        TAMBOURINE: ([0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0], 95, ""),
        MARACAS: ([0, .5, 0, .5, 0, .5, 0, .5, 0, .5, 0, .5, 0, .5, 0, .5], 60, "i"),
        COWBELL: ([.3, 0, 0, 0, 0, 0, 0, 0, .3, 0, 0, 0, 0, 0, 0, 0], 70, "c"),
    },
}
_FORGE_STYLES = {"dubstep", "house", "trap"}
_ACCENT_STEPS = {0: 1.0, 8: 0.9, 4: 0.85, 12: 0.85}


# where a hit came from, so the pieces' settings know what to change (ROW_GHOST: a ghost-note row of a
# variation's own table, which the table plays like the rest of its rows)
GROOVE, GHOST, ROW_GHOST, ROLL, BLAST, FILL, ACCENT, CHORD_KICK, FOLLOWED, HAND = (
    "groove", "ghost", "row ghost", "roll", "blast", "fill", "accent", "chord", "follow", "hand")


def _table_hits(bar, table, settings, rng, complexity=None):
    """The hits a drum table plays in one bar: [(step, note, velocity, GROOVE or ROW_GHOST)]."""
    complexity = settings["complexity"] / 100.0 if complexity is None else complexity
    hits = []
    for note, (pattern, velocity, scaled) in table.items():
        origin = ROW_GHOST if "g" in scaled else GROOVE
        scaled = scaled.replace("g", "")
        for step in range(bar.steps):
            place = bar.map[step]            # its place in the style's 4/4 groove (in 4/4, the step itself)
            p = pattern[place]
            if p <= 0:
                continue
            if p >= 1.0:
                pass                    # the backbone of the style: always played
            elif scaled == "i":         # once grew with intensity; now with complexity, as gently as it did
                p = p * (0.35 + 1.1 * complexity)
            elif scaled == "c":
                p = p * (0.25 + 1.3 * complexity)
            if p < 1.0 and rng.random() >= p:
                continue
            accent = _ACCENT_STEPS.get(place, 0.82 if place % 2 == 0 else 0.7)
            hits.append((step, note, _velocity(velocity * accent, settings["intensity"], rng), origin))
    return hits


def _piece_density(bar, hits, rows, busy, rng, intensity, kick=False):
    """One piece's own Complexity, 0 to 100 (Russell, 10 Oct 2026), on the hits its rows play in a bar. 50 leaves
    them; lower leaves out the sixteenths first, then the in-between eighths, down to the beats; higher adds notes
    where the piece rests, the in-between eighths first, then some sixteenths, never all of them (a kick adds fewer),
    so even at 100 a drummer could play it."""
    amount = (busy - 50) / 50.0
    if amount == 0 or not rows:
        return hits

    def place_of(step):
        return bar.map[step] if 0 <= step < len(bar.map) else step

    if amount < 0:
        kept = []
        for hit in hits:
            step = hit[0]
            if step != int(step):
                continue                                   # a flam or roll note between steps goes first
            place = place_of(int(step))
            if place % 4 == 0:
                drop = 0.0                                 # the beats stay
            elif place % 2 == 1:
                drop = min(1.0, -amount * 1.6)             # sixteenths
            else:
                drop = max(0.0, -amount * 1.6 - 0.6)       # the in-between eighths, only near 0
            if drop <= 0 or rng.random() >= drop:
                kept.append(hit)
        return kept
    note, (pattern, velocity, _scaled) = max(rows.items(), key=lambda item: sum(item[1][0]))
    if max(pattern) <= 0:
        return hits
    taken = {int(h[0]) for h in hits}
    added = []
    for step in range(bar.steps):
        if step in taken:
            continue
        place = place_of(step)
        if place % 2 == 0:
            chance = amount * (0.6 if kick else 0.9)
        else:
            chance = max(0.0, amount - (0.5 if kick else 0.35)) * (0.4 if kick else 0.7)
        if chance > 0 and rng.random() < chance:
            accent = 0.82 if place % 2 == 0 else 0.7
            added.append((step, note, _velocity(velocity * accent, intensity, rng), GROOVE))
    return hits + added


def _drum_bar(bar, style_key, table, settings, rng):
    """One bar of the style's groove (table: the chosen variation's), with the style's own touches."""
    complexity = settings["complexity"] / 100.0
    hits = _table_hits(bar, table, settings, rng)
    # ghost notes on the snare grow with complexity (not in electronic styles)
    if style_key in ("funk", "rock", "pop", "hard_rock", "jazz"):
        for step in range(bar.steps):
            if bar.map[step] % 4 in (1, 3) and rng.random() < 0.18 * complexity:
                hits.append((step, SNARE, _velocity(34, settings["intensity"] if new_rules(settings) else 50, rng, 6),
                             GHOST))
    # hi-hat rolls in trap: 32nd notes or triplets just before the clap and at the bar's end
    if style_key == "trap" and rng.random() < 0.25 + 0.6 * complexity:
        where = rng.choice([6, 14]) if bar.steps >= 16 else max(0, bar.steps - 2)
        kind = rng.choice(["32nds", "triplets"])
        hits = [h for h in hits if not (h[1] == HAT and where <= h[0] < where + 2)]
        count = 4 if kind == "32nds" else 3
        for k in range(count):
            hits.append((where + k * 2.0 / count, HAT, _velocity(70 + 6 * k, settings["intensity"], rng), ROLL))
    # metal: a blast of eighth-note snares at the very top of the complexity range (it was intensity before 0.9.4)
    if style_key == "metal" and complexity > 0.85:
        hits = [h for h in hits if h[1] != SNARE] + [(s, SNARE, _velocity(100, settings["intensity"], rng), BLAST)
                                                     for s in range(0, bar.steps, 2)]
    return hits


HAT_BUILD_STYLES = ("rock", "hard_rock", "metal", "funk", "pop", "house", "trap", "dubstep")
# Russell (10 Oct 2026): the hi-hat builds only into a louder region (Intensity 50 going to 100, say), opening
# gradually over the last two bars; never in ordinary fills, and never at Intensity 100 (nothing to build to)
BUILD_RISE = 20             # the next region at least this much louder (Intensity) makes the hi-hat build into it
BUILD_BARS = 2              # how many bars that build takes
BUILD_HALF_FROM = 0.4       # how far through a build the hi-hat starts to open (half open: the foot closes it again)
BUILD_OPEN_FROM = 0.8       # and is played wide open, into the crash


def _build_hits(places, intensity, rng):
    """A hi-hat build: places is [(step, how far through the build from 0 to 1, steps to the next hit)]. Harder and
    harder; closed, then half open (played open a little softer, the foot closing it again halfway to the next hit),
    then wide open on the last hits."""
    out = []
    for step, through, gap in places:
        velocity = _velocity(45 + 80 * through, intensity, rng, 4)
        if through < BUILD_HALF_FROM:
            out.append((step, HAT, velocity, FILL))
        elif through < BUILD_OPEN_FROM:
            out.append((step, OPEN_HAT, max(1, int(velocity * 0.85)), FILL))
            closes = step + gap / 2.0
            out.append((int(closes) if closes == int(closes) else closes, PEDAL, 1, CHOKE))
        else:
            out.append((step, OPEN_HAT, velocity, FILL))
    return out
# how this performance accents its hi-hat: a loudness for each place in the beat (beat, sixteenth, eighth, sixteenth)
HAT_ACCENTS = ((1.0, 1.0, 1.0, 1.0), (1.0, 0.8, 0.9, 0.8), (0.85, 0.8, 1.0, 0.8), (1.0, 0.75, 0.75, 0.75),
               (0.9, 0.85, 0.95, 0.85))


def drum_intensity(intensity):
    """The Intensity the drums' notes are played at (Russell, 10 Oct 2026: "intensity 40 is what I feel like is at
    100%"): 100 now plays as hard as 40 did, and lower is softer (at 0 a little softer than before). What Intensity
    decides besides loudness (the rim click below 20, the hi-hat opening from 70) still uses the number set."""
    return (0.4 * intensity - 10.0) / 0.75


def fill_chance(bar, amount):
    """How likely a fill is in a bar at a Fill amount (0 to 1): 1 is a fill in every bar."""
    if amount <= 0:
        return 0.0
    if bar.phrase_position == 3 or bar.last_in_region:
        if bar.index % 8 == 7 or bar.last_in_region:
            return min(1.0, amount * 1.4)
        return min(1.0, amount * 0.9 + max(0.0, amount - 0.75) * 0.4)
    if bar.index % 2 == 1:
        return max(0.0, (amount - 0.5) * 2)
    return max(0.0, (amount - 0.75) * 4)


def _fill_start(bar, size, rng):
    """Where a fill starts, by Fill complexity (0 to 1): a beat's pickup when small, half the bar in the middle (as
    fills always were), up to the whole bar when big."""
    first, second = rng.random(), rng.random()
    if size < 0.25:
        start = bar.steps - (bar.pulses[-1][1] if bar.pulses else 4)
    elif size <= 0.6:
        start = bar.steps // 2 + (bar.steps // 4 if second < 0.4 else 0)
    else:
        start = 0 if first < (size - 0.6) / 0.4 else bar.steps // 2
    return max(0, min(bar.steps - 2, start))


NO_FILL_STYLES = {("spark", "pad")}     # a simple held pad has no runs into the next bar


def has_fills(settings):
    """True if this player and style play fills (every one but a simple pad)."""
    return (settings.get("player"), settings.get("style")) not in NO_FILL_STYLES


def _melodic_fill_chance(bar, amount):
    """Fill amount for bass, keys, synth and guitar: a run into the next bar at phrase ends first, then every second
    bar, then every bar at 100."""
    if amount <= 0:
        return 0.0
    if bar.phrase_position == 3 or bar.last_in_region:
        return min(1.0, amount * 0.8 + max(0.0, amount - 0.75) * 0.8)
    if bar.index % 2 == 1:
        return max(0.0, (amount - 0.5) * 2)
    return max(0.0, (amount - 0.75) * 4)


def _performance_touches(bar, hits, accents, pickups, rng, intensity):
    """A performance's own small habits (each Reforge picks new ones): how it accents the hi-hat, and an extra kick
    just before a beat now and then."""
    out = []
    taken = {(int(h[0]), h[1]) for h in hits}
    for h in hits:
        if h[1] == HAT and h[3] == GROOVE and h[0] == int(h[0]):
            place = bar.map[int(h[0])] if int(h[0]) < len(bar.map) else int(h[0])
            loud = accents[place % 4]
            out.append((h[0], h[1], max(1, int(round(h[2] * loud))), h[3]))
        else:
            out.append(h)
    if pickups:
        for step in range(1, bar.steps):
            place = bar.map[step] if step < len(bar.map) else step
            if place % 4 == 3 and (step, KICK) not in taken and rng.random() < pickups:
                out.append((step, KICK, _velocity(78, intensity, rng), GROOVE))
    return out


def _drum_fill(bar, style_key, settings, rng, start_step):
    """A fill from `start_step` to the end of the bar. Fill complexity (0 to 1) makes it fuller; each performance
    picks one of many shapes (more since 10 Oct 2026, Russell: "near infinite for regenerations")."""
    steps = list(range(start_step, bar.steps))
    intensity = settings["intensity"]
    size = settings.get("fill_complexity", 50) / 100.0
    hits = []
    if style_key in ("dubstep", "trap", "house"):
        kind = rng.choice(["snare roll", "snare roll", "triplet roll", "stutter", "clap roll"])
    elif style_key in ("hand_percussion", "shakers"):
        kind = "congas"
    elif style_key == "jazz":
        kind = rng.choice(["snare comp", "toms", "snare comp"])
    else:
        kind = rng.choice(["toms", "snare and toms", "snare roll", "toms up", "flams", "kick and snare", "alternating"])
    toms = [TOM_HIGH, TOM_MID, TOM_LOW, TOM_FLOOR]
    if kind in ("snare roll", "clap roll"):
        sound = CLAP if (style_key == "house" or kind == "clap roll") else SNARE
        doubles = 4 if size <= 0.6 else 8
        for i, step in enumerate(steps):
            hits.append((step, sound, _velocity(60 + 50 * i / max(1, len(steps)), intensity, rng)))
            if len(steps) - i <= doubles and rng.random() < size:
                hits.append((step + 0.5, sound, _velocity(70 + 40 * i / max(1, len(steps)), intensity, rng)))
    elif kind == "triplet roll":
        count = len(steps) * 3 // 4 or 1
        for i in range(count * 2):
            hits.append((start_step + i * len(steps) / float(count * 2), SNARE, _velocity(65 + 40 * i / (2 * count),
                                                                                         intensity, rng)))
    elif kind == "stutter":                  # eighths, then sixteenths, then thirty-seconds, rising
        third = max(1, len(steps) // 3)
        for i, step in enumerate(steps):
            rise = i / float(max(1, len(steps)))
            if i < third and i % 2:
                continue
            hits.append((step, SNARE, _velocity(60 + 55 * rise, intensity, rng)))
            if i >= 2 * third and rng.random() < 0.5 + size / 2:
                hits.append((step + 0.5, SNARE, _velocity(65 + 55 * rise, intensity, rng)))
    elif kind == "congas":
        drums = [CONGA_OPEN, CONGA_MUTE, CONGA_LOW, BONGO_HIGH, BONGO_LOW]
        for step in steps:
            if rng.random() < 0.6 + 0.4 * size or step == steps[-1]:
                hits.append((step, rng.choice(drums), _velocity(90, intensity, rng)))
    elif kind == "snare comp":
        for step in steps:
            if rng.random() < size:
                hits.append((step, SNARE, _velocity(70, intensity, rng)))
    elif kind == "flams":                    # a soft grace note just before each hit
        for i, step in enumerate(steps):
            if i % 2 and rng.random() > size:
                continue
            note = SNARE if i < len(steps) // 2 else toms[min(3, int(i * 4 / max(1, len(steps))))]
            hits.append((step - 0.25 if step > 0 else step, note, _velocity(50, intensity, rng)))
            hits.append((step, note, _velocity(100, intensity, rng)))
    elif kind == "kick and snare":           # unison hits that climb
        for i, step in enumerate(steps):
            if i % 2 and rng.random() > size:
                continue
            loud = 75 + 45 * i / max(1, len(steps))
            hits.append((step, SNARE, _velocity(loud, intensity, rng)))
            hits.append((step, KICK, _velocity(loud, intensity, rng)))
    elif kind == "alternating":              # snare and a tom in turn, the tom moving down
        for i, step in enumerate(steps):
            if rng.random() > 0.55 + 0.6 * size and step != steps[-1]:
                continue
            note = SNARE if i % 2 == 0 else toms[min(3, int(i * 4 / max(1, len(steps))))]
            hits.append((step, note, _velocity(90, intensity, rng)))
    else:
        order = list(reversed(toms)) if kind == "toms up" else toms
        for i, step in enumerate(steps):
            if kind == "snare and toms" and i < len(steps) // 2:
                note = SNARE
            else:
                note = order[min(len(order) - 1, int(i * len(order) / max(1, len(steps))))]
            if rng.random() < 0.55 + 0.6 * size or step == steps[-1]:
                hits.append((step, note, _velocity(95, intensity, rng)))
    if kind not in ("congas", "snare comp", "kick and snare") and style_key in ("rock", "hard_rock", "metal") \
            and steps:
        hits.append((steps[-1], KICK, _velocity(110, intensity, rng)))
    return hits


def _drum_fill_rules_1(bar, style_key, settings, rng, start_step):
    """A fill from `start_step` to the end of the bar, as regions with rules 1 play it (before 10 Oct 2026)."""
    steps = list(range(start_step, bar.steps))
    intensity = settings["intensity"]
    hits = []
    if style_key in ("dubstep", "trap", "house"):
        kind = rng.choice(["snare roll", "snare roll", "triplet roll"])
    elif style_key in ("hand_percussion", "shakers"):
        kind = "congas"
    elif style_key == "jazz":
        kind = rng.choice(["snare comp", "toms"])
    else:
        kind = rng.choice(["toms", "snare and toms", "snare roll"])
    if kind == "snare roll":
        for i, step in enumerate(steps):
            hits.append((step, SNARE if style_key != "house" else CLAP,
                         _velocity(60 + 50 * i / max(1, len(steps)), intensity, rng)))
            if len(steps) - i <= 4 and rng.random() < 0.5:
                hits.append((step + 0.5, SNARE, _velocity(70 + 40 * i / max(1, len(steps)), intensity, rng)))
    elif kind == "triplet roll":
        count = len(steps) * 3 // 4 or 1
        for i in range(count * 2):
            hits.append((start_step + i * len(steps) / float(count * 2), SNARE, _velocity(65 + 40 * i / (2 * count),
                                                                                         intensity, rng)))
    elif kind == "congas":
        drums = [CONGA_OPEN, CONGA_MUTE, CONGA_LOW, BONGO_HIGH, BONGO_LOW]
        for step in steps:
            hits.append((step, rng.choice(drums), _velocity(90, intensity, rng)))
    elif kind == "snare comp":
        for step in steps:
            if rng.random() < 0.5:
                hits.append((step, SNARE, _velocity(70, intensity, rng)))
    else:
        toms = [TOM_HIGH, TOM_MID, TOM_LOW, TOM_FLOOR]
        for i, step in enumerate(steps):
            if kind == "snare and toms" and i < len(steps) // 2:
                note = SNARE
            else:
                note = toms[min(len(toms) - 1, int(i * len(toms) / max(1, len(steps))))]
            if rng.random() < 0.85 or step == steps[-1]:
                hits.append((step, note, _velocity(95, intensity, rng)))
        if style_key in ("rock", "hard_rock", "metal") and steps:
            hits.append((steps[-1], KICK, _velocity(110, intensity, rng)))
    return hits


class _KitPieces:
    """Anvil's kit pieces with settings of their own (player_pieces.py), applied around the style's performance:
    groove() right after the bar's groove is made (another pattern, ghost notes, half or double time) and finish()
    once the fills, crashes and Follow are in (hi-hat openness, the ride's bell, toms in fills, when and which crash,
    on or off, hand-made steps, loudness, the rim click). Their own random choices come from generators of their
    own, so the performance's fills and details stay as they were; with every piece at its default nothing changes."""

    def __init__(self, settings, style_key, table, hits_in, follow, section_starts, for_steps=False):
        self.settings = settings
        self.for_steps = for_steps   # for the Step pattern view: each piece keeps its own sounds
        self.full = {p.key: pp.piece_settings(settings, p.key) for p in pp.DRUM_PIECES}
        intensity = settings["intensity"]
        self.openness = self._openness(self.full["hat"]["openness"], intensity)
        rim = self.full["snare"]["rim"]
        self.rim = rim == "always" or (rim == "intensity" and (intensity <= pp.RIM_AT if new_rules(settings)
                                                               else intensity < RIM_BELOW_RULES_1))
        # with every piece at its default, soft playing still goes to the rim and hard playing still opens the hi-hat
        self.active = (any(self.full[key] != pp.DRUM_DEFAULTS for key in self.full) or self.rim
                       or self.openness != "closed")
        self.voices = {p.key: set(p.voices) for p in pp.DRUM_PIECES}
        self.custom = {}             # piece -> (rows it plays instead, whether it is another pattern)
        for piece in pp.DRUM_PIECES:
            full = self.full[piece.key]
            rows = pp.drum_pattern_rows(style_key, settings["variation"], piece.key, full["pattern"], _DRUM_STYLES)
            if rows is not None:
                self.custom[piece.key] = (rows, True)
            elif full["busy"] != pp.BUSY_DEFAULT:
                self.custom[piece.key] = (pp.piece_rows(table, piece), False)
        self.section_starts = list(section_starts or ())
        self.follow = follow
        self.accent_ticks = [h.tick for h in accents(hits_in) if h.weight >= 0.75] if follow else []
        self.crash_turn = 0

    def _rng(self, name, bar):
        return random.Random(_piece_seed(self.settings, name, bar.index))

    def ghost_loudness(self, hits):
        """The snare's ghost notes at their own loudness (Russell, 10 Oct 2026: "an intensity slider for those ghost
        notes to make them sound bigger"): 50 as the style plays them, 100 more than half again as hard, 0 a
        whisper."""
        snare = self.full["snare"]
        level = snare.get("ghost_level", pp.LEVEL_DEFAULT)
        if level == pp.LEVEL_DEFAULT or snare["ghosts"] == "none":
            return hits
        factor = 0.4 + 1.2 * level / 100.0
        return [(h[0], h[1], max(1, min(127, int(round(h[2] * factor)))), h[3])
                if h[1] in (SNARE, SNARE2) and h[3] in (GHOST, ROW_GHOST) else h for h in hits]

    def rng_named(self, name, bar):
        """Random choices of their own for one bar, apart from the performance's (so adding them changes nothing
        else), still new with each Reforge."""
        return self._rng(name, bar)

    def groove(self, bar, hits):
        if not self.active:
            return hits
        for piece_key, (rows, other_pattern) in self.custom.items():
            voices = self.voices[piece_key]
            dropped = (GROOVE, ROW_GHOST, ROLL, BLAST) if other_pattern else (GROOVE, ROW_GHOST)
            hits = [h for h in hits if not (h[1] in voices and h[3] in dropped)]
            busy = self.full[piece_key]["busy"]
            complexity = pp.busy_complexity(self.settings["complexity"], busy) / 100.0
            rng = self._rng(piece_key, bar)
            mine = _table_hits(bar, rows, self.settings, rng, complexity)
            if busy != pp.BUSY_DEFAULT and new_rules(self.settings):
                mine = _piece_density(bar, mine, rows, busy, rng, self.settings["intensity"],
                                      kick=pp.PIECE_BY_KEY[piece_key].kind == "kick")
            hits += mine
        snare = self.full["snare"]
        if snare["ghosts"] == "none":
            hits = [h for h in hits if h[3] not in (GHOST, ROW_GHOST)]
        elif snare["ghosts"] == "more":
            rng = self._rng("ghosts", bar)
            taken = {h[0] for h in hits if h[1] in (SNARE, SNARE2)}
            chance = 0.3 + 0.4 * self.settings["complexity"] / 100.0
            for step in range(bar.steps):
                if bar.map[step] % 4 in (1, 3) and step not in taken and rng.random() < chance:
                    hits.append((step, SNARE, _velocity(36, self.settings["intensity"] if new_rules(self.settings)
                                                        else 50, rng, 6), GHOST))
        for piece_key in ("kick", "snare"):
            if self.full[piece_key]["time"] != "normal":
                hits = self._retime(bar, hits, self.voices[piece_key], self.full[piece_key]["time"])
        return hits

    @staticmethod
    def _retime(bar, hits, voices, mode):
        """Half time: each half of the bar's pattern stretched over a whole bar (two bars make one pattern).
        Double time: the pattern twice in one bar. Ghost notes and rolls stay where they are."""
        steps = bar.steps
        moving = [h for h in hits if h[1] in voices and h[3] in (GROOVE, BLAST) and h[0] == int(h[0])]
        kept = [h for h in hits if h not in moving]
        moved = []
        half = max(1, steps // 2)
        if mode == "half":
            first = 0 if bar.index % 2 == 0 else half
            moved = [((h[0] - first) * 2, h[1], h[2], h[3]) for h in moving if first <= h[0] < first + half]
        else:
            for h in moving:
                if int(h[0]) % 2 == 0:
                    moved.append((int(h[0]) // 2, h[1], h[2], h[3]))
                    if int(h[0]) // 2 + half < steps:
                        moved.append((int(h[0]) // 2 + half, h[1], h[2], h[3]))
        return kept + [h for h in moved if h[0] < steps]

    def finish(self, bar, hits, fill_start, fill_bars, thinned=()):
        """thinned: the (step, note) places of the hi-hats and shakers the bar's fill or hi-hat build left out
        (hand-made steps there are left out too, as the style's own were)."""
        if not self.active:
            return [h for h in hits if h[3] not in OVERLAYS] if self.for_steps else hits
        full = self.full
        if not full["toms"]["in_fills"]:
            hits = [(h[0], SNARE, h[2], h[3]) if h[1] in self.voices["toms"] and h[3] == FILL else h for h in hits]
        crash = full["crash"]
        if crash["when"] != "start_and_fills":
            hits = self._crash_when(bar, hits, crash["when"], fill_bars)
        for piece in pp.DRUM_PIECES:
            settings, voices = full[piece.key], self.voices[piece.key]
            if not settings["on"]:
                hits = [h for h in hits if h[1] not in voices]
                continue
            if settings["steps"]:
                hits = self._hand_made(bar, hits, voices, settings["steps"], fill_start, thinned)
            if settings["level"] != pp.LEVEL_DEFAULT:
                scaled = []
                for h in hits:
                    if h[1] in voices and h[3] != HAND:
                        velocity = pp.level_velocity(h[2], settings["level"])
                        if velocity is None:
                            continue                     # loudness 0: silent
                        h = (h[0], h[1], velocity, h[3])
                    scaled.append(h)
                hits = scaled
        # last, so these keep belonging to their own piece and apply to hand-made steps too: the ride's bell, the
        # hi-hat's openness and the snare's rim click. The Step pattern view leaves them out (it shows each piece's
        # own sounds) and leaves out what comes on top of a piece's steps by itself (crashes where the region starts
        # and after fills, kicks on chord changes and on the followed track's hits).
        if self.for_steps:
            return [h for h in hits if h[3] not in OVERLAYS]
        if crash["which"] != "crash1":
            hits = self._crash_which(hits, crash["which"])
        hat = full["hat"]
        sound = full["ride"]["ride_sound"]
        if sound != "ride":          # Which ride: every ride note on that cymbal
            target = dict((k, n) for k, _w, n in pp.RIDE_SOUNDS)[sound]
            hits = [(h[0], target, h[2], h[3]) if h[1] == RIDE else h for h in hits]
        if full["ride"]["bell"]:
            hits = [(h[0], RIDE_BELL, h[2], h[3]) if h[1] in (RIDE, pp.RIDE2) and h[0] == int(h[0])
                    and int(h[0]) in bar.beats else h for h in hits]
        offbeats = hat["open_offbeats"] or hat["pattern"] == "g:disco"     # disco sixteenths open their offbeats
        if hat["on"] and (self.openness != "closed" or offbeats):
            # half open by intensity keeps the full loudness: playing harder never makes a hit softer
            hits = self._open_hats(bar, hits, dict(hat, openness=self.openness, open_offbeats=offbeats,
                                                   soften=hat["openness"] != "intensity"))
        if self.rim:          # the backbeat goes to the rim; ghost notes and soft snares stay on the snare
            level = full["snare"]["level"]          # (judged by the style's own loudness, before the piece's level)
            # a main hit, not a ghost note: measured against how hard the drums play at this Intensity, since the
            # drums play softer since 10 Oct 2026 (a hand-made step's loudness is its own, so Loudness leaves it)
            scale = max(0.05, 0.5 + 0.75 * self.settings["intensity"] / 100.0) if new_rules(self.settings) else 1.0
            hits = [(h[0], RIM, h[2], h[3]) if h[1] == SNARE and h[3] in (GROOVE, BLAST, HAND)
                    and (h[2] / scale if h[3] == HAND else h[2] / scale * pp.LEVEL_DEFAULT / float(max(1, level)))
                    >= GHOST_LOUDNESS
                    else h for h in hits]
        return hits

    @staticmethod
    def _openness(chosen, intensity):
        """How open the hi-hat is: as chosen, or by intensity (closed, then half open, then open)."""
        if chosen != "intensity":
            return chosen
        return "open" if intensity >= pp.OPEN_FROM else ("half" if intensity >= pp.HALF_OPEN_FROM else "closed")

    @staticmethod
    def _open_hats(bar, hits, hat):
        """Open: every closed hi-hat is played open. Half open: played open a little softer, with the foot closing
        it again a sixteenth later (a silent pedal note, which cuts the open hi-hat off). Open on the offbeats: the
        hi-hats on the and of each beat are played open."""
        taken = {h[0] for h in hits if h[1] in (HAT, PEDAL, OPEN_HAT)}
        already_open = {h[0] for h in hits if h[1] == OPEN_HAT}     # opening a hi-hat there would hit it twice
        changed = []
        for h in hits:
            if h[1] != HAT or h[3] not in (GROOVE, ROLL, HAND):
                changed.append(h)
                continue
            offbeat = h[0] == int(h[0]) and int(h[0]) < bar.steps and bar.map[int(h[0])] % 4 == 2
            if hat["openness"] in ("open", "half") or (hat["open_offbeats"] and offbeat):
                if h[0] in already_open:
                    continue
            if hat["openness"] == "open" or (hat["open_offbeats"] and offbeat):
                changed.append((h[0], OPEN_HAT, h[2], h[3]))
            elif hat["openness"] == "half":
                changed.append((h[0], OPEN_HAT, max(1, int(h[2] * (0.8 if hat.get("soften", True) else 1.0))),
                                h[3]))
                after = h[0] + (1 if h[0] == int(h[0]) else 0.5)
                if after not in taken and after < bar.steps:
                    changed.append((after, PEDAL, 1, CHOKE))
            else:
                changed.append(h)
        return changed

    def _crash_when(self, bar, hits, when, fill_bars):
        cymbals = (CRASH, CRASH2)
        others = [h for h in hits if not (h[3] == ACCENT and h[1] in cymbals)]
        if when == "never":
            return [h for h in others if not (h[3] == ACCENT and h[1] in (FORGE_IMPACT, FORGE_RISER))]
        if when == "accents" and not self.follow:
            return hits                  # nothing is followed: as the style plays them
        steps = []
        after_fill = bar.index > 0 and (bar.number - 1) in fill_bars
        if when in ("fills", "sections") and after_fill:
            steps.append(0)
        if when == "sections":
            steps += [(t - bar.start) // STEP for t in self.section_starts
                      if bar.start <= t < bar.end and (t - bar.start) % STEP == 0]
        elif when.startswith("every_"):
            if bar.index % int(when.split("_")[1]) == 0:
                steps.append(0)
        elif when == "accents":
            steps += [int(round((t - bar.start) / float(STEP))) for t in self.accent_ticks if bar.start <= t < bar.end]
        rng = self._rng("crash", bar)
        for step in sorted(set(st for st in steps if 0 <= st < bar.steps)):
            others.append((step, CRASH, _velocity(106, self.settings["intensity"], rng), ACCENT))
        return others

    def _crash_which(self, hits, which):
        notes = dict(pp.WHICH).get(which, (CRASH,))
        out = []
        for h in hits:
            if h[1] in (CRASH, CRASH2) and h[3] in (GROOVE, ACCENT, HAND):
                out.append((h[0], notes[self.crash_turn % len(notes)], h[2], h[3]))
                self.crash_turn += 1
            else:
                out.append(h)
        return out

    @staticmethod
    def _hand_made(bar, hits, voices, steps, fill_start, thinned=()):
        """The piece's own steps instead of what the style plays. What comes on top by itself stays: fills, rolls,
        crashes where the region starts and after fills, kicks on chord changes and on the followed track's hits. In a
        bar with a fill, the fill takes over from where it starts, except the sounds the style keeps playing through
        a fill (the kick, the hi-hats, the ride and the shaker); a trap hi-hat roll takes over the two steps it
        fills."""
        kept = [h for h in hits if h[1] not in voices or h[3] in (FILL, ROLL, CHOKE) + OVERLAYS]
        rolls = [h[0] for h in hits if h[1] in voices and h[3] == ROLL]
        rolled = (min(rolls), min(rolls) + 2) if rolls else (0, 0)
        pattern = steps["bars"][bar.index % len(steps["bars"])]
        kept += [(step, sound, velocity, HAND) for step, velocity, sound in pattern
                 if (fill_start is None or step < fill_start or sound in FILL_KEEPS) and (step, sound) not in thinned
                 and not rolled[0] <= step < rolled[1]]
        return kept


CHOKE = "choke"                  # the silent pedal note that closes a half-open hi-hat
RIM_BELOW_RULES_1 = 35           # rules 1: Intensity below this went to the rim
GHOST_LOUDNESS = 50              # a snare softer than this stays on the snare when the rim click is on (a ghost note)
OVERLAYS = (ACCENT, CHORD_KICK, FOLLOWED)    # what comes on top of a piece's steps by itself
FILL_KEEPS = (KICK, HAT, OPEN_HAT, RIDE, PEDAL, SHAKER, FORGE_SHAKER)   # what keeps playing through a fill


# A drummer has two hands (Russell, 10 Oct 2026: "a drummer doesn't play a hi-hat and a crash cymbal at the same time
# when hitting the snare drum"). In the styles a real drummer plays (not the drum machines of dubstep, house and trap,
# nor the hand percussion styles), at most two hand sounds start together, and a crash takes the place of the hi-hat
# or ride the same hand was keeping time on. The feet (kick, hi-hat pedal) are free. Hand-made steps are kept as set.
LIVE_DRUMMER_STYLES = pp.LIVE_DRUMMER_STYLES
_CRASHES = (CRASH, CRASH2, SPLASH, CHINA)
_TIMEKEEPING = (HAT, OPEN_HAT, RIDE, RIDE_BELL, pp.RIDE2)
_HAND_ORDER = [(_CRASHES, 0), ((SNARE, SNARE2, RIM), 1), ((TOM_HIGH, TOM_MID, TOM_LOW, TOM_FLOOR), 2),
               ((RIDE, RIDE_BELL, pp.RIDE2), 3), ((HAT, OPEN_HAT), 4), ((COWBELL, TAMBOURINE, CLAVES), 5)]
_HAND_RANK = {note: rank for notes, rank in _HAND_ORDER for note in notes}


def _two_hands(hits):
    by_time = {}
    for hit in hits:
        by_time.setdefault(round(float(hit[0]), 6), []).append(hit)
    kept = []
    for together in by_time.values():
        hands = [h for h in together if h[1] in _HAND_RANK]
        if len(hands) < 2 and not any(h[1] in _CRASHES for h in hands):
            kept += together
            continue
        dropped = set()
        crashes = [h for h in hands if h[1] in _CRASHES]
        if crashes:           # the timekeeping hand moves to the crash (kept only when you set both there yourself)
            yours = all(h[3] == HAND for h in crashes)
            dropped |= {id(h) for h in hands if h[1] in _TIMEKEEPING and not (h[3] == HAND and yours)}
        left = [h for h in hands if id(h) not in dropped]
        left.sort(key=lambda h: (h[3] != HAND, _HAND_RANK[h[1]], -h[2]))
        room = max(2, sum(1 for h in left if h[3] == HAND))
        dropped |= {id(h) for h in left[room:] if h[3] != HAND}
        kept += [h for h in together if id(h) not in dropped]
    return kept


# the hand-played sounds of the pieces with a tempo limit for sixteenth notes (the hi-hat pedal is a foot)
_SIXTEENTH_VOICES = {"ride": (RIDE, RIDE_BELL, pp.RIDE2), "hat": (HAT, OPEN_HAT)}


def _eighths_when_fast(bar, hits, style_key):
    """Above a piece's tempo limit (player_pieces.SIXTEENTHS_UP_TO; Russell, 21 Oct 2026: no sixteenth notes on the
    ride over 120 beats a minute), the ride and hi-hat keep their eighth notes and leave out the sixteenths squeezed
    between them, whatever made them (the style, a pattern, Complexity, a fill). A hit between the eighths with no
    other hit of the piece a sixteenth away is not a run, and stays. Steps set by hand stay as set."""
    for key, voices in _SIXTEENTH_VOICES.items():
        if not pp.too_fast_for_sixteenths(key, style_key, bar.tempo):
            continue
        places = [float(h[0]) for h in hits if h[1] in voices and h[3] != CHOKE]

        def in_a_run(step):
            whole = int(step)
            between = step != whole or not 0 <= whole < bar.steps or bar.map[whole] % 2 == 1
            return between and sum(1 for other in places if abs(other - step) < 1.01) > 1

        hits = [h for h in hits if not (h[1] in voices and h[3] not in (HAND, CHOKE) and in_a_run(float(h[0])))]
    return hits


def _perform_drums(settings, bars, chord_spans, hits_in, follow, rng_for, section_starts=(), for_steps=False,
                   next_intensity=None):
    """for_steps: for the Step pattern view, the performance as heard but with no fills (each bar's random choices
    are made exactly as they are heard, so everything else stays the same), no swing, and each piece's own sounds.
    next_intensity: the Intensity of the drummer region straight after this one on the track (None: there is none);
    a louder one makes the hi-hat build into it."""
    style_key = settings["style"]
    fills_amount = settings["fills"] / 100.0
    fill_size = settings.get("fill_complexity", 50) / 100.0
    feel = random.Random(_seed(settings, "feel"))          # this performance's own touches (Reforge changes them)
    hat_accents = feel.choice(HAT_ACCENTS)
    pickups = feel.choice((0.0, 0.1, 0.2)) * min(1.0, settings["complexity"] / 50.0)   # an extra kick before a beat
    swing = 0 if for_steps else settings["swing"]
    grid = swing_grid(settings)
    table = pp.style_table(style_key, settings["variation"], _DRUM_STYLES)
    kit = _KitPieces(settings, style_key, table, hits_in, follow, section_starts, for_steps)
    rules_now = new_rules(settings)
    chosen_intensity = settings["intensity"]
    builds_at_all = rules_now and style_key in HAT_BUILD_STYLES and chosen_intensity < 100 and not for_steps
    # no hi-hat playing (turned off): nothing to build (Russell)
    builds_at_all = builds_at_all and kit.full["hat"]["on"]
    builds_up = (builds_at_all and next_intensity is not None and next_intensity - chosen_intensity >= BUILD_RISE)
    if rules_now:
        settings = dict(settings, intensity=drum_intensity(settings["intensity"]))   # how hard the notes are played
    kit.settings = settings
    notes = []
    fill_bars = []
    followed = accents(hits_in) if follow else []
    matched = set()
    for bar in bars:
        rng = rng_for(bar.index)
        hits = kit.groove(bar, _drum_bar(bar, style_key, table, settings, rng))
        if rules_now and style_key in LIVE_DRUMMER_STYLES:
            # only on pieces still playing the style's own pattern: a pattern chosen or steps made by hand stay as set
            own = lambda key: kit.full[key]["pattern"] == "style" and not kit.full[key]["steps"]  # noqa: E731
            hits = _performance_touches(bar, hits, hat_accents if own("hat") else HAT_ACCENTS[0],
                                        pickups if own("kick") and kit.full["kick"]["busy"] >= pp.BUSY_DEFAULT
                                        else 0.0, kit.rng_named("touches", bar), settings["intensity"])
        fill_start = None
        thinned = set()
        # Fill amount (Russell, 10 Oct 2026): 0 no fills, 100 a fill in every bar; between, the ends of phrases first
        # (every 4 bars, more likely at 8 and at the region's end), then every second bar, then every bar
        if rules_now:
            chance = fill_chance(bar, fills_amount)
        else:                                       # rules 1: the ends of phrases only
            phrase_end = bar.phrase_position == 3 or bar.last_in_region
            chance = (fills_amount * (1.4 if (bar.index % 8 == 7 or bar.last_in_region) else 0.9)
                      if phrase_end else 0.0)
        if chance > 0 and rng.random() < chance:
            if rules_now:
                start = _fill_start(bar, fill_size, rng)
            else:
                start = bar.steps // 2 if (rng.random() < 0.6 or fills_amount < 0.6) else 0
                start = max(0, min(bar.steps - 2, start + (bar.steps // 4 if rng.random() < 0.4 else 0)))
            filled = [h for h in hits if h[0] < start or h[1] in FILL_KEEPS]
            kept_through = [h for h in filled if not (h[0] >= start and h[1] in (HAT, OPEN_HAT, SHAKER, FORGE_SHAKER)
                                                      and rng.random() < 0.5)]
            thinned = {(h[0], h[1]) for h in filled if h not in kept_through}
            filled = kept_through
            fill = _drum_fill if rules_now else _drum_fill_rules_1
            filled += [(step, note, velocity, FILL) for step, note, velocity in
                       fill(bar, style_key, settings, rng, start)]
            fill_bars.append(bar.number)
            if not for_steps:
                hits = filled
                fill_start = start
        # the last two bars before a louder region: the hi-hat builds into it, opening gradually (Russell)
        from_end = len(bars) - 1 - bar.index
        if builds_up and from_end < BUILD_BARS:
            length = min(BUILD_BARS, len(bars))
            which = length - 1 - from_end                  # 0: the build's first bar
            hits = [h for h in hits if h[1] not in (HAT, OPEN_HAT, PEDAL)]
            thinned = set(thinned) | {(st, sound) for st in range(bar.steps) for sound in (HAT, OPEN_HAT, PEDAL)}
            places = list(range(0, bar.steps, 2))
            hits += _build_hits([(step, (which + (k + 1) / float(len(places))) / length, 2)
                                 for k, step in enumerate(places)], settings["intensity"],
                                kit.rng_named("region build", bar))
        # a crash on the region's first beat, and after a fill
        if style_key not in ("hand_percussion", "shakers", "jazz"):
            if bar.index == 0:
                hits.append((0, CRASH, _velocity(105, settings["intensity"], rng), ACCENT))
            elif bar.index > 0 and (bar.number - 1) in fill_bars:
                hits.append((0, CRASH if rng.random() < 0.7 else CRASH2, _velocity(108, settings["intensity"], rng),
                             ACCENT))
                if style_key == "dubstep" and fills_amount > 0.5:
                    hits.append((0, FORGE_IMPACT, _velocity(100, settings["intensity"], rng), ACCENT))
        if style_key == "dubstep" and bar.last_in_region and fills_amount > 0.6 and bar.steps >= 16:
            hits.append((0, FORGE_RISER, _velocity(90, settings["intensity"], rng), ACCENT))
        # the chord track: a kick on every chord change (when following the chord track)
        if settings["follow"] == "chords":
            for start, _end, _change in chord_spans:
                if bar.start <= start < bar.end and (start - bar.start) % STEP == 0:
                    step = (start - bar.start) // STEP
                    if not any(h[0] == step and h[1] in (KICK, KICK2) for h in hits):
                        hits.append((step, KICK, _velocity(105, settings["intensity"], rng), CHORD_KICK))
        # Follow: the kick locks to the followed part's accents
        if follow:
            amount = settings["follow_amount"] / 100.0
            in_bar = [h for h in followed if bar.start <= h.tick < bar.end]
            kicks = [h for h in hits if h[1] in (KICK, KICK2)]
            others = [h for h in hits if h[1] not in (KICK, KICK2)]
            kept_kicks = []
            for kick in kicks:
                tick = bar.start + kick[0] * STEP
                near = any(abs(h.tick - tick) <= STEP // 2 for h in in_bar)
                if near or rng.random() >= amount:
                    kept_kicks.append(kick)
            placed = []
            for accent in in_bar:
                if rng.random() < amount:
                    step = (accent.tick - bar.start) / float(STEP)
                    if abs(step - round(step)) * STEP <= 30:
                        step = float(round(step))
                    kept_kicks = [k for k in kept_kicks if abs(k[0] - step) > 0.5]
                    placed.append((step, KICK, _velocity(80 + 40 * accent.weight, settings["intensity"], rng),
                                   FOLLOWED))
                    matched.add(accent.tick)
            # fills and toms step aside where the followed part hits
            others = [h for h in others if not (bar.number in fill_bars and h[1] in (SNARE, TOM_HIGH, TOM_MID, TOM_LOW,
                                                                                    TOM_FLOOR)
                                                and any(abs(bar.start + h[0] * STEP - a.tick) < STEP // 2
                                                        for a in in_bar))]
            hits = others + kept_kicks + placed
        hits = kit.finish(bar, hits, fill_start, fill_bars, thinned if not for_steps else ())
        hits = kit.ghost_loudness(hits)
        if rules_now:                           # (older regions play as they did until they are changed)
            hits = _eighths_when_fast(bar, hits, style_key)
        # eighth swing's triplet feel, the Step pattern view too (it shows where the notes are heard), before the two
        # hands, so a note that joins the "and" still finds only two hands there
        hits = _triplet_lock(hits, bar, settings["swing"], grid, lambda h: h[1], stays=lambda h: h[3] == CHOKE)
        if grid == 4 and settings["swing"] >= TRIPLET_LOCK_FROM:   # a fill's doubled 32nds have no place in triplets
            hits = [h for h in hits if not (h[3] == FILL and h[0] != int(h[0]))]
        if style_key in LIVE_DRUMMER_STYLES:        # the Step pattern view too: it shows what is heard
            hits = _two_hands(hits)
        for step, note, velocity, origin in hits:
            tick = _swing_tick(bar, step, swing, grid)
            if tick >= bar.end:
                continue
            length = 480 if note in (CRASH, CRASH2, RIDE, CHINA, OPEN_HAT, FORGE_IMPACT, FORGE_RISER) else STEP
            if origin == CHOKE:
                length = 30
            notes.append(Note(tick, length, note, velocity))
    return _tidy(notes), fill_bars, len(followed), len(matched)


# ----------------------------------------------------------------------
# pitches: chords to notes
# ----------------------------------------------------------------------
def _in_range(pc, low, high):
    """The lowest note with pitch class `pc` at or above `low` (wrapping down if it passes `high`)."""
    note = low + ((pc - low) % 12)
    while note > high:
        note -= 12
    return note


def _chord_at(chord_spans, tick):
    for start, end, change in chord_spans:
        if start <= tick < end:
            return change
    return chord_spans[-1][2] if chord_spans else chordtrack.ChordChange(0, 0)


def _next_chord(chord_spans, tick):
    for start, _end, change in chord_spans:
        if start > tick:
            return change
    return None


def _voicing(change, low, high, extensions, previous=None, rng=None):
    """Chord tones from low to high, as a hand would play them: the inversion nearest the previous voicing
    (now and then the next nearest, which is what makes a reforged part voice its chords differently)."""
    intervals = list(change.intervals())
    if extensions >= 0.6 and len(intervals) == 3 and change.quality in ("major", "minor"):
        intervals.append(14)       # add a ninth
    if extensions >= 0.8 and change.quality == "major" and 11 not in intervals:
        intervals.append(11 if change.root % 12 in (0, 5) else 10)
    candidates = []
    for base in range(low, low + 12):
        if base % 12 != change.root % 12:
            continue
        for inversion in range(len(intervals)):
            notes = sorted((base + iv + (12 if k < inversion else 0)) for k, iv in enumerate(intervals))
            notes = [n for n in notes if n <= high]
            if len(notes) >= min(3, len(intervals)):
                candidates.append(notes)
    if not candidates:
        root = _in_range(change.root, low, high)
        return [root + iv for iv in intervals if root + iv <= high + 12]
    centre = sum(previous) / float(len(previous)) if previous else (low + high) / 2.0
    ranked = sorted(candidates, key=lambda v: abs(sum(v) / float(len(v)) - centre))
    if rng is not None and len(ranked) > 1 and rng.random() < 0.3:
        return ranked[1]
    return ranked[0]


def _power_chord(change, low=40, high=52):
    root = _in_range(change.root, low, high)
    return [root, root + 7, root + 12]


def _guitar_chord(change, low=40):
    """Up to six strings: root, fifth, octave, third, fifth, root (an open-position shape)."""
    root = _in_range(change.root, low, low + 11)
    intervals = change.intervals()
    third = intervals[1] if len(intervals) > 1 else 4
    fifth = 7 if 7 in intervals else (intervals[2] if len(intervals) > 2 else 7)
    shape = [0, fifth, 12, 12 + third, 12 + fifth, 24]
    return [root + i for i in shape if root + i <= 79]


# ----------------------------------------------------------------------
# melodic players
# ----------------------------------------------------------------------
def _style_rhythm(player, style, bar, settings, rng):
    """[(step, length in steps, accent 0 to 1, role)] for one bar. role picks the pitch:
    "root", "fifth", "octave", "approach", "chord", "arp" or "ghost"."""
    steps = bar.steps
    half = bar.half                          # the beat nearest the middle (8 in 4/4)
    place = bar.map                          # each sixteenth's place in a 4/4 groove (0 to 15)
    on_beat = bar.beats.__contains__         # in every meter, not only every fourth sixteenth
    # Complexity alone decides how many notes there are; intensity only how hard they are played (Russell,
    # 9 Oct 2026: "the intensity is just supposed to change the velocity"). Where intensity used to choose (half
    # notes or whole notes, eighths or sixteenths), complexity now does, at a point that keeps the default settings
    # playing the same rhythm.
    c = settings["complexity"] / 100.0
    events = []
    if player == "bellows":
        if style == "roots":
            events.append((0, steps if c < 0.35 else half, 1.0, "root"))
            if c >= 0.35:
                events.append((half, steps - half, 0.85, "fifth" if rng.random() < c else "root"))
        elif style == "eighths":
            for s in range(0, steps, 2):
                role = "root"
                if place[s] % 4 == 2 and rng.random() < 0.6 * c:
                    role = "octave"
                if s == steps - 2 and rng.random() < c:
                    role = "approach"
                events.append((s, 2, 1.0 if on_beat(s) else 0.8, role))
        elif style == "funk":
            pattern = [1, 0, 0, .5, 0, 0, .6, .4, 0, .3, .8, 0, 0, .5, 0, .4]
            for s in range(steps):
                p = pattern[place[s]] * (0.6 + 0.8 * c) if pattern[place[s]] < 1 else 1.0
                if rng.random() < p:
                    role = rng.choice(["root", "root", "octave", "fifth"]) if s else "root"
                    events.append((s, 1 if s % 2 else 2, 1.0 if on_beat(s) else 0.7, role))
                elif rng.random() < 0.15 * c:
                    events.append((s, 1, 0.3, "ghost"))
        elif style == "walking":
            for b, length in bar.pulses:          # one note a beat: three in 3/4, two in 6/8
                role = "root" if b == 0 else ("approach" if b + length >= steps else "walk")
                events.append((b, length, 0.9 if b == 0 else 0.75, role))
                if rng.random() < 0.15 * c and b + length < steps:
                    events.append((b + length - 1, 1, 0.5, "approach"))
        elif style == "dubstep":
            events.append((0, half, 1.0, "root"))
            if rng.random() < 0.4 + 0.5 * c:
                events.append((half + (2 if rng.random() < c else 0), max(1, steps - half - 2), 0.9,
                               rng.choice(["root", "low", "fifth"])))
            if c > 0.7:
                for s in range(half, steps, 1):
                    if rng.random() < 0.25 * c:
                        events.append((s, 1, 0.8, "root"))
        elif style == "house":
            for b, length in bar.pulses:          # the offbeat of every beat
                s = b + max(2, length // 4 * 2) if length >= 4 else b + length // 2
                if s < steps:
                    events.append((s, 1, 0.9, "octave" if rng.random() < 0.4 * c else "root"))
            if rng.random() < 0.5 * c:
                events.append((steps - 1, 1, 0.7, "approach"))
        elif style == "trap":
            spots = [0] + [s for s in range(1, steps) if place[s] in (3, 6, 7, 10, 11, 14)
                           and rng.random() < 0.25 + 0.35 * c]
            spots = sorted(set(spots))
            for k, s in enumerate(spots):
                end = spots[k + 1] if k + 1 < len(spots) else steps
                events.append((s, end - s, 1.0 if s == 0 else 0.85,
                               rng.choice(["root", "root", "octave", "fifth"]) if s else "root"))
        elif style == "metal":
            figures = {"gallop": [(0, 2), (2, 1), (3, 1)], "reverse": [(0, 1), (1, 1), (2, 2)],
                       "sixteenths": [(0, 1), (1, 1), (2, 1), (3, 1)], "eighths": [(0, 2), (2, 2)]}
            weights = ["gallop", "gallop", "reverse"] + (["sixteenths"] * 2 if c > 0.6 else ["eighths"])
            for b, size in bar.pulses:
                figure = (figures[rng.choice(weights)] if size == 4 else
                          [(o, min(2, size - o)) for o in range(0, size, 2)])     # a dotted beat: three eighths
                for offset, length in figure:
                    if b + offset < steps:
                        events.append((b + offset, length, 1.0 if offset == 0 else 0.75,
                                       "octave" if offset and rng.random() < 0.1 * c else "low"))
    elif player == "ember":
        if style == "block":
            events.append((0, half if c >= 0.35 else steps, 1.0, "chord"))
            if c >= 0.35:
                second = half - (2 if rng.random() < 0.35 * c else 0)         # sometimes pushed early
                events.append((second, steps - second, 0.85, "chord"))
            events.append((0, steps if c < 0.35 else half, 0.9, "left"))
            if rng.random() < 0.3 * c:
                events.append((steps - 2, 2, 0.7, "chord"))
        elif style == "pulse":
            skip = rng.choice([None, 6, 10, 14]) if c > 0.2 else None
            for s in range(0, steps, 2):
                if place[s] == skip:
                    continue
                events.append((s, 2, 1.0 if on_beat(s) else (0.85 if rng.random() < 0.3 else 0.72), "chord"))
            if c > 0.5:
                events.append((0, half, 0.8, "left"))
        elif style == "arpeggio":
            rate = 1 if c > 0.6 else 2
            shape = rng.choice(["up", "updown", "skip", "wave"])
            for k, s in enumerate(range(0, steps, rate)):
                events.append((s, rate * 2, 1.0 if on_beat(s) else 0.7, "{}:{}".format(shape, k)))
            events.append((0, steps, 0.8, "left"))
        elif style == "comping":
            spots = [s for s in range(steps) if place[s] in (0, 3, 6, 8, 10, 14)
                     and rng.random() < (0.35 + 0.5 * c if s else 0.6)]
            for s in spots:
                events.append((s, rng.choice([1, 2, 3]), 0.8, "shell"))
        elif style == "stabs":
            for s in range(steps):
                if place[s] % 4 == 2 or (place[s] % 4 == 3 and rng.random() < 0.3 * c):
                    if rng.random() < 0.7 + 0.3 * c:
                        events.append((s, 1, 0.9, "chord"))
    elif player == "spark":
        if style == "pad":
            events.append((0, steps, 0.8, "chord"))
        elif style in ("arp_up", "arp_updown"):
            rate = 1 if c >= 0.4 else 2
            if style == "arp_up":
                shape = rng.choice(["up", "up", "skip", "up3"])
            else:
                shape = rng.choice(["updown", "updown", "wave"])
            start = rng.randrange(3)
            for k, s in enumerate(range(0, steps, rate)):
                events.append((s, rate, 1.0 if on_beat(s) else 0.75, "{}:{}".format(shape, k + start)))
        elif style == "pluck":
            pattern = [1, 0, .7, 1, 0, .7, 1, 0, 1, 0, .7, 1, 0, .7, 1, .5]
            k = 0
            for s in range(steps):
                if rng.random() < pattern[place[s]] * (0.6 + 0.6 * c):
                    events.append((s, 1, 1.0 if on_beat(s) else 0.75, "pluck:{}".format(rng.randrange(8))))
                    k += 1
        elif style == "gate":
            gate = [1, 0, 1, 1, 0, 1, 1, 0, 1, 0, 1, 1, 0, 1, 1, 0]
            for s in range(steps):
                if gate[place[s]] or rng.random() < 0.2 * c:
                    events.append((s, 1, 1.0 if on_beat(s) else 0.7, "chord"))
        elif style == "stabs":
            for s in [st for st in range(steps) if place[st] in (0, 3, 6, 10, 11, 14)]:
                if s == 0 or rng.random() < 0.4 + 0.4 * c:
                    events.append((s, 1 if s % 2 else 2, 1.0, "chord"))
    elif player == "hammer":
        if style == "chugs":
            rate = 1 if c >= 0.35 else 2
            for s in range(0, steps, rate):
                if not on_beat(s) and rng.random() < 0.2 * c:
                    continue      # a rest makes the riff
                events.append((s, rate, 1.0 if on_beat(s) else 0.7, "power"))
        elif style == "gallop":
            figures = [[(0, 2), (2, 1), (3, 1)], [(0, 2), (2, 1), (3, 1)], [(0, 1), (1, 1), (2, 2)],
                       [(0, 2), (2, 2)]]
            for b, size in bar.pulses:
                figure = rng.choice(figures) if (b and rng.random() < 0.3 + 0.5 * c) else figures[0]
                if size != 4:                         # a dotted beat: an eighth, two sixteenths and an eighth
                    figure = [(0, 2), (2, 1), (3, 1), (4, 2)][:3 if size < 6 else 4]
                for offset, length in figure:
                    if b + offset < steps:
                        events.append((b + offset, length, 1.0 if offset == 0 else 0.8,
                                       "power_up" if offset and rng.random() < 0.08 * c else "power"))
        elif style == "hard_rock":
            for s in range(0, steps, 2):
                ring = s in (0, half)
                events.append((s, 4 if ring else 2, 1.0 if ring else 0.75, "power"))
            if rng.random() < c:
                events.append((steps - 1, 1, 0.8, "power_up"))
        elif style == "palm_eighths":
            for s in range(0, steps, 2):
                events.append((s, 1, 0.95 if on_beat(s) else 0.75, "power"))
        elif style == "strum":
            pattern = dict([(0, "down"), (4, "down"), (6, "up"), (10, "up"), (12, "down"), (14, "up")])
            for s, direction in [(st, pattern[place[st]]) for st in range(steps) if place[st] in pattern]:
                if s == 0 or rng.random() < 0.6 + 0.4 * c:
                    events.append((s, 2 if direction == "up" else 4, 1.0 if direction == "down" else 0.7,
                                   "strum_" + direction))
        elif style == "arpeggio":
            order = rng.randrange(len(_PICK_ORDERS))
            for k, s in enumerate(range(0, steps, 2)):
                events.append((s, 4, 0.9 if on_beat(s) else 0.7, "pick:{}:{}".format(k, order)))
    return events


_PICK_ORDERS = ([0, 2, 3, 4, 3, 2, 1, 2], [0, 3, 2, 4, 1, 3, 2, 4], [0, 1, 2, 3, 4, 3, 2, 1], [0, 2, 4, 3, 1, 2, 3, 4])


def _arp_note(shape, k, tones):
    """The k-th note of an arpeggio shape over `tones` (low to high)."""
    n = len(tones)
    if shape in ("up", "arp", "pluck"):
        return tones[k % n]
    if shape == "up3":
        return tones[(k * 2) % n]
    if shape == "skip":
        order = [0, 2, 1, 3, 2, 4, 3, 5]
        return tones[order[k % len(order)] % n]
    if shape == "wave":
        order = [0, 1, 2, 1, 2, 3, 2, 1]
        return tones[order[k % len(order)] % n]
    if shape == "alberti":
        order = [0, 2, 1, 2]              # low, high, middle, high
        return tones[order[k % len(order)] % n]
    cycle = tones + tones[-2:0:-1]        # up and down
    return cycle[k % len(cycle)]


PART_REGISTERS = {"ember": (55, 76), "spark": (60, 79), "hammer": (40, 52)}


def _fifth(intervals):
    """The chord's fifth: the perfect fifth, or the chord's own (the flat fifth of a diminished or half-diminished
    chord, the sharp fifth of an augmented one)."""
    return 7 if 7 in intervals else (intervals[2] if len(intervals) > 2 else 7)


def _chord_tone(change, sound, low):
    """The root, third, fifth or octave of a chord, from its root at or above `low`."""
    intervals = change.intervals()
    root = _in_range(change.root, low, low + 11)
    offset = {"root": 0, "third": intervals[1] if len(intervals) > 1 else 4,
              "fifth": _fifth(intervals), "octave": 12}[sound]
    return root + offset


def _step_pitches(player, sound, change, state, rng, settings):
    """The notes for a hand-made step of a part (player_pieces.PART_SOUNDS)."""
    if player == "bellows":
        if sound == "fifth":
            low, high = (24, 40) if settings["style"] in ("dubstep", "trap") else (28, 43)
            return [_in_range((change.root + _fifth(change.intervals())) % 12, low, high + 5)]
        return _pitches(player, sound, change, None, state, rng, settings)
    if sound == "chord":
        return _pitches(player, "chord", change, None, state, rng, settings)
    if sound == "power":
        return _power_chord(change)
    if sound == "strum":
        return _guitar_chord(change)
    return [_chord_tone(change, sound, PART_REGISTERS[player][0])]


def _pitches(player, role, change, next_change, state, rng, settings, ahead=None):
    """The notes for one event, from the chord playing there. next_change: the next chord change, however far
    off (the 0.8 rules' approach notes lead into it); ahead: the chords on the next beat ("beat") and at the start of
    the next bar ("bar"), for the variations' figures."""
    c = settings["complexity"] / 100.0
    ahead = ahead or {}
    if role.startswith("step:"):
        return _step_pitches(player, role[5:], change, state, rng, settings)
    if role == "next":                     # the next bar's chord, pushed in early (struck again if it is the same)
        change, role = ahead.get("bar") or change, "chord"
    if role == "passing":                  # a passing note into the chord change a sixteenth later
        role = "approach"
    if role == "lead":                     # a half step from the note on the next beat, leading into it
        target_chord = ahead.get("beat") or change
        if player == "bellows":
            low, high = (24, 40) if settings["style"] in ("dubstep", "trap") else (28, 43)
            target = _in_range(target_chord.bass_class(), low, high)       # a root (or the next bar's first note)
            if ahead.get("role") == "walk":    # the walking note that follows: chosen now, and played there
                previous = state.get("bass", target)
                options = [_in_range((target_chord.root + iv) % 12, low, high + 7) for iv in target_chord.intervals()]
                options += [o + 12 for o in options if o + 12 <= high + 7]
                options = [o for o in options if o != previous] or [target]
                target = min(options, key=lambda n: abs(n - previous))
                state["walk_target"] = target
            return [target + rng.choice([-1, 1])]
        low, high = PART_REGISTERS[player]
        return [_in_range(target_chord.root, low, high) + rng.choice([-1, 1])]
    if role == "approach" and player != "bellows":
        low, high = PART_REGISTERS[player]
        return [_in_range((next_change or change).root, low, high) + rng.choice([-1, 1])]
    if player == "bellows":
        low, high = (24, 40) if settings["style"] in ("dubstep", "trap") else (28, 43)
        root = _in_range(change.bass_class(), low, high)
        walk_target = state.pop("walk_target", None)       # set by an approach note just before (the figures)
        if role == "low":
            return [_in_range(change.root, 28, 39)]
        if role == "octave":
            return [root + 12 if root + 12 <= high + 12 else root]
        if role == "fifth":
            fifth = 7 if 7 in change.intervals() else change.intervals()[-1]
            note = _in_range((change.root + fifth) % 12, low, high + 5)
            return [note]
        if role == "third":
            intervals = change.intervals()
            return [_in_range((change.root + (intervals[1] if len(intervals) > 1 else 4)) % 12, low, high + 5)]
        if role == "approach" and next_change is not None:
            target = _in_range(next_change.bass_class(), low, high)
            return [target + rng.choice([-1, 1, -2])]
        if role == "walk":
            if walk_target is not None:
                state["bass"] = walk_target
                return [walk_target]
            tones = [(change.root + iv) % 12 for iv in change.intervals()]
            previous = state.get("bass", root)
            options = [_in_range(pc, low, high + 7) for pc in tones]
            options += [o + 12 for o in options if o + 12 <= high + 7]
            options = [o for o in options if o != previous] or [root]
            note = min(options, key=lambda n: abs(n - previous) + rng.random() * 3)
            state["bass"] = note
            return [note]
        if role == "ghost":
            return [root]
        state["bass"] = root
        return [root]
    if player in ("ember", "spark"):
        low, high = (55, 76) if player == "ember" else (60, 79)
        if role == "left":
            return [_in_range(change.bass_class(), 36, 47)]
        voicing = _voicing(change, low, high, c, state.get("voicing"), rng)
        state["voicing"] = voicing
        if role == "shell":
            intervals = change.intervals()
            root = _in_range(change.root, 48, 59)
            third = root + (intervals[1] if len(intervals) > 1 else 4)
            seventh = root + (10 if change.quality in ("m7", "7", "minor", "m7b5") else 11)
            return [third, seventh] + ([seventh + 4] if c > 0.6 else [])
        if ":" in role:
            shape, k = role.split(":")[0], int(role.split(":")[1])
            tones = voicing + [n + 12 for n in voicing]
            return [_arp_note(shape, k, tones)]
        return voicing
    if player == "hammer":
        if role in ("power", "power_up"):
            chord = _power_chord(change)
            return [n + 2 for n in chord] if role == "power_up" else chord
        if role.startswith("strum"):
            shape = _guitar_chord(change)
            return shape if role.endswith("down") else list(reversed(shape[:4]))
        if role.startswith("pick:"):
            shape = _guitar_chord(change)
            _name, k, which = role.split(":")
            order = _PICK_ORDERS[int(which) % len(_PICK_ORDERS)]
            return [shape[order[int(k) % len(order)] % len(shape)]]
    return []


def _passing_notes(bar, events, chord_spans):
    """A short note into each chord change, a sixteenth before it (where nothing else starts)."""
    taken = {e[0] for e in events}
    added = []
    for start, _end, _change in chord_spans:
        if bar.start < start <= bar.end and (start - bar.start) % STEP == 0:
            step = (start - bar.start) // STEP - 1
            if 0 <= step < bar.steps and step not in taken:
                added.append((step, 1, 0.7, "passing"))
    return events + added


MAIN_SOUND = {"bellows": "root", "ember": "chord", "spark": "chord", "hammer": "power"}


def _perform_melodic(settings, bars, chord_spans, hits_in, follow, rng_for, for_steps=False):
    """for_steps: for the Step pattern view, the part as heard but with no fill runs (each bar's random choices are
    made exactly as they are heard), no swing and no passing notes."""
    player, style = settings["player"], settings["style"]
    part = pp.piece_settings(settings, "part")
    if part["busy"] != pp.BUSY_DEFAULT:
        # the part's own Complexity, 0 to 100 (50: the player's Complexity) (Russell, 10 Oct 2026); the performance's
        # random choices stay seeded from the region's settings, so only how busy it is changes
        settings = dict(settings, complexity=pp.busy_complexity(settings["complexity"], part["busy"]))
    feel = random.Random(_seed(settings, "feel"))          # this performance's own habits (Reforge changes them)
    rules_now = new_rules(settings)
    accents_here = feel.choice(HAT_ACCENTS) if rules_now else HAT_ACCENTS[0]
    octave_pops = feel.choice((0.0, 0.06, 0.12)) if player == "bellows" and rules_now else 0.0
    run_every = (feel.choice((1, 2)) if settings["complexity"] >= 50 else 2) if player in ("ember", "spark") \
        and rules_now else (1 if player in ("bellows", "hammer") else 2)
    rhythm_style, rhythm_variation = pp.part_pattern(player, style, settings["variation"], part["pattern"])
    figure = pv.figure(player, rhythm_style, rhythm_variation)
    arp_shape = "updown" if (player, rhythm_style) == ("spark", "arp_updown") else "up"
    swing = 0 if for_steps else settings["swing"]
    grid = swing_grid(settings)
    fills = settings["fills"] / 100.0
    fill_size = settings.get("fill_complexity", 50) / 100.0
    hand_made = part["steps"] if not for_steps else None
    notes = []
    state = {}
    step_state = {}                       # the hand-made steps' own voice leading
    fill_bars = []
    followed = accents(hits_in) if follow else []
    matched = set()

    def event_notes(bar, event, rng, own_state, next_role="root"):
        """The notes of one event (step, length in steps, accent, role[, loudness set by hand]); next_role: the role
        of the event after it (an approach note aims at a walking note that follows it)."""
        step, length, accent, role = event[:4]
        tick = _swing_tick(bar, step, swing, grid)
        if tick >= bar.end:
            return []
        change = _chord_at(chord_spans, tick)
        next_change = _next_chord(chord_spans, tick)
        beat_end = bar.start + bar.next_beat(int(step)) * STEP
        ahead = {"beat": _chord_at(chord_spans, min(beat_end, bar.end)), "bar": _chord_at(chord_spans, bar.end),
                 "role": next_role}
        pitches = _pitches(player, role, change, next_change, own_state, rng, settings, ahead)
        if part["root_only"] and pitches:
            lowest = min(pitches)
            root = change.bass_class() if player == "bellows" else change.root
            pitches = [lowest - ((lowest - root) % 12)]
        if part["octave"]:
            pitches = [n + 12 * part["octave"] for n in pitches]
        ticks = max(30, int(length * STEP))
        if player == "hammer" and settings["style"] in ("chugs", "gallop", "palm_eighths"):
            ticks = max(40, int(ticks * 0.55))       # muted: short and tight
        elif player in ("ember", "spark") and settings["style"] in ("stabs", "gate", "pluck"):
            ticks = max(40, int(ticks * 0.6))
        if part["length"] == "short":
            ticks = max(30, ticks // 2)
        elif part["length"] == "long":
            ticks = int(ticks * 1.6)
        ticks = min(ticks, bar.end + 4 * STEP - tick)
        if len(event) > 4:
            velocity = event[4]                      # a hand-made step: its own loudness
        else:
            base = 96 if role != "ghost" else 40
            if step == int(step) and int(step) < len(bar.map):
                base *= accents_here[bar.map[int(step)] % 4]      # this performance's accents
            velocity = _velocity(base * accent, settings["intensity"], rng)
            if octave_pops and role == "root" and pitches and touch.random() < octave_pops:
                pitches = [n + 12 for n in pitches if n + 12 <= 127] or pitches   # a bass octave pop now and then
            if part["level"] != pp.LEVEL_DEFAULT:
                velocity = pp.level_velocity(velocity, part["level"])
                if velocity is None:
                    return []                         # loudness 0: silent
        spread = 0
        if role.startswith("strum") or role == "step:strum":
            spread = 14 if (role.endswith("down") or role == "step:strum") else 10
        return [Note(tick + k * spread, ticks, pitch, max(1, velocity - (k * 3 if spread else 0)))
                for k, pitch in enumerate(pitches) if 0 <= pitch <= 127]

    touch = None
    for bar in bars:
        rng = rng_for(bar.index)
        touch = random.Random(_seed(settings, ["touch", bar.index]))
        if figure:
            events = pv.figure_events(figure, bar.steps, bar.beat_steps, arp_shape, bar.map, bar.beats)
        else:
            events = _style_rhythm(player, rhythm_style, bar, settings, rng)
        run_start = None
        # a little fill at phrase ends: an extra run or pickup into the next bar
        if rules_now:
            chance = _melodic_fill_chance(bar, fills) if has_fills(settings) else 0.0
        else:                                       # rules 1: a run at the ends of phrases only
            chance = fills * 0.8 if (bar.phrase_position == 3 or bar.last_in_region) else 0.0
        if chance > 0 and rng.random() < chance:
            # Fill complexity (Russell, 10 Oct 2026): a two-step pickup when small, the last beat in the middle (as runs
            # always were), up to half the bar when big
            pick, pulse = rng.random(), bar.pulses[-1][1]
            if not rules_now:
                start = bar.steps - (pulse if pick < 0.6 else 2)
            elif fill_size < 0.25:
                start = bar.steps - 2
            elif fill_size <= 0.6:
                start = bar.steps - (pulse if pick < 0.6 else 2)
            else:
                start = bar.steps // 2 if pick < (fill_size - 0.6) / 0.4 else bar.steps - pulse
            start = max(0, min(bar.steps - 1, start))
            fill_bars.append(bar.number)
            if not for_steps:
                run_start = start
                events = [e for e in events if e[0] < run_start]
                for s in range(run_start, bar.steps, run_every):
                    role = "approach" if player == "bellows" else ("power" if player == "hammer" else "arp:{}".format(s))
                    events.append((s, 1, 0.8, role))
        if follow:
            amount = settings["follow_amount"] / 100.0
            in_bar = [h for h in hits_in if bar.start <= h.tick < bar.end]
            rhythm_hits = followed and [h for h in in_bar if h in followed] or in_bar
            kept = []
            for event in events:
                tick = bar.start + event[0] * STEP
                near = any(abs(h.tick - tick) <= STEP // 2 for h in in_bar)
                if near or rng.random() >= amount:
                    kept.append(event)
            events = kept
            role = {"bellows": "root", "ember": "chord", "spark": "chord", "hammer": "power"}[player]
            for k, hit in enumerate(rhythm_hits):
                if rng.random() < amount:
                    step = (hit.tick - bar.start) / float(STEP)
                    following = rhythm_hits[k + 1].tick if k + 1 < len(rhythm_hits) else bar.end
                    length = max(1.0, min((following - hit.tick) / float(STEP), 8.0))
                    events = [e for e in events if abs(e[0] - step) > 0.5]
                    events.append((step, length, 0.6 + 0.4 * hit.weight, role))
                    matched.add(hit.tick)
        if part["passing"]:
            events = _passing_notes(bar, events, chord_spans)
        events = _triplet_lock(events, bar, settings["swing"], grid, lambda e: None)   # the Step view too
        events.sort(key=lambda e: e[0])
        # every event's notes, exactly as the style plays the bar (hand-made steps then choose from them)
        made = [(event, event_notes(bar, event, rng, state, events[k + 1][3] if k + 1 < len(events) else "root"))
                for k, event in enumerate(events)]
        if hand_made:
            made = _part_steps(bar, made, hand_made, run_start, chord_spans, part, player, settings,
                               lambda event, step_rng: event_notes(bar, event, step_rng, step_state))
        for event, event_list in made:
            if for_steps and event[3] == "passing":
                continue                          # passing notes come back by themselves on hand-made steps
            notes.extend(event_list)
    return _tidy(notes), fill_bars, len(followed), len(matched)


def _part_steps(bar, made, steps, run_start, chord_spans, part, player, settings, notes_of):
    """A part's hand-made steps in one bar. made: [(event, notes)], the bar as the style plays it. A step "as the
    style plays it" plays the style's own notes on that step, at the step's loudness (or, where the style plays
    nothing on it in this bar, the player's main sound); any other sound is worked out from the chord and lasts until
    the next step. A fill still takes over where its run starts, and with passing notes on, a short note still leads
    into each chord change where no step starts. Returns [(event, notes)]."""
    pattern = steps["bars"][bar.index % len(steps["bars"])]
    limit = bar.steps if run_start is None else run_start
    on = [(step, velocity, sound) for step, velocity, sound in pattern if step < limit]
    step_rng = random.Random(_piece_seed(settings, "part", bar.index))
    style_notes, passing = {}, {}
    for event, event_list in made:
        if run_start is not None and event[0] >= run_start:
            continue
        where = passing if event[3] == "passing" else style_notes
        where.setdefault(int(round(event[0])), []).extend(event_list)
    out = [(event, event_list) for event, event_list in made if run_start is not None and event[0] >= run_start]
    for k, (step, velocity, sound) in enumerate(on):
        following = on[k + 1][0] if k + 1 < len(on) else limit
        if sound == "style" and style_notes.get(step):
            found = style_notes[step]
            top = max(n.velocity for n in found)
            out.append(((step, 1, 1.0, "step:style", velocity),
                        [Note(n.tick, n.length, n.pitch, max(1, min(127, int(round(velocity * n.velocity / float(top))))))
                         for n in found]))
            continue
        sound = MAIN_SOUND[player] if sound == "style" else sound
        event = (step, max(1, following - step), 1.0, "step:" + sound, velocity)
        out.append((event, notes_of(event, step_rng)))
    if part["passing"]:
        taken = [event for event, _notes in out]
        added = _passing_notes(bar, taken, chord_spans)[len(taken):]
        # eighth swing's triplet feel, as on the style's own passing notes (a passing note on an "a" joins the "and",
        # or is left out where something already starts there)
        locked = _triplet_lock(added + [(e[0], None) for e in taken], bar, settings["swing"], swing_grid(settings),
                               lambda e: None)
        added = [e for e in locked if len(e) > 2]
        for event in added:
            step = event[0]
            if run_start is not None and step >= run_start:
                continue
            out.append((event, passing.get(step) or notes_of(event, step_rng)))
    return out


def _tidy(notes):
    """Sorted, no two notes of the same pitch starting together."""
    seen = {}
    for note in notes:
        key = (note.tick, note.pitch)
        if key not in seen or note.velocity > seen[key].velocity:
            seen[key] = note
    return sorted(seen.values(), key=lambda n: (n.tick, n.pitch))


# ----------------------------------------------------------------------
# the one function
# ----------------------------------------------------------------------
def perform(settings, start, end, timeline, chord_changes, follow_hits=None, section_starts=(), for_steps=False,
            next_intensity=None):
    """The notes a rhythm player plays in [start, end).

    settings: the region's player settings. chord_changes: the song's chord track (an empty one
    plays the key's own chord). follow_hits: [Hit] of the followed track, or None. section_starts:
    the ticks where the song's sections start (for a crash at the start of each section).
    next_intensity: drums only: the Intensity of the drummer region straight after this one (a louder one gets a
    hi-hat build in this one's last two bars).
    for_steps: what the Step pattern view starts from: the performance as heard, but without fills, swing or
    passing notes (they still come on top of hand-made steps), each drum piece with its own sounds (before the
    hi-hat's openness and the rim click change them).
    Same inputs, same notes."""
    settings = clean_settings(settings) or new_settings("anvil")
    bars = _bars(timeline, start, end)
    if settings["player"] != "anvil" and not pp.piece_settings(settings, "part")["chords"]:
        chord_changes = []                 # the part plays the key's own chord, not the chord track
    chord_spans = chordtrack.spans(chord_changes, start, end, timeline)
    follow = settings["follow"] == "track" and follow_hits is not None

    def rng_for(index):
        return random.Random(_seed(settings, index))

    hits_in = [h for h in (follow_hits or []) if start <= h.tick < end]
    if settings["player"] == "anvil":
        notes, fill_bars, accent_count, matched = _perform_drums(settings, bars, chord_spans, hits_in, follow, rng_for,
                                                                 section_starts, for_steps, next_intensity)
    else:
        notes, fill_bars, accent_count, matched = _perform_melodic(settings, bars, chord_spans, hits_in, follow,
                                                                   rng_for, for_steps)
    notes = [n for n in notes if start <= n.tick < end]
    return Performance(notes, fill_bars, accent_count, matched, len(hits_in))


def summary(settings, performance, bars, follow_text=""):
    """'Anvil, dubstep, variation 2 of 6, 8 bars, 31 notes. Fills in bars 4 and 8.' plus how Follow went, and the
    pieces that are not as the style plays them."""
    player = PLAYERS[settings["player"]]
    style = player.style(settings["style"])
    text = "{}, {}, variation {} of {}, {} bar{}, {} note{}.".format(
        player.name, style.name.lower(), settings["variation"], variation_count(settings), bars,
        "" if bars == 1 else "s", len(performance.notes), "" if len(performance.notes) == 1 else "s")
    if performance.fill_bars:
        numbers = [str(b) for b in performance.fill_bars]
        joined = numbers[0] if len(numbers) == 1 else ", ".join(numbers[:-1]) + " and " + numbers[-1]
        text += " Fill{} in bar{} {}.".format("s" if len(numbers) > 1 else "", "s" if len(numbers) > 1 else "",
                                             joined)
    if follow_text:
        text += " " + follow_text
    pieces = pieces_words(settings)
    if pieces:
        text += " " + pieces
    return text


def pieces_words(settings):
    """'Pieces off: Ride. Hand-made: Snare. Changed: Closed hi-hat.' (empty when every piece is as the style plays
    it)."""
    stored = settings.get("pieces") or {}
    if not stored:
        return ""
    off, hand, changed = [], [], []
    for piece in pp.pieces_for(settings["player"]):
        own = stored.get(piece.key)
        if not own:
            continue
        name = piece.name if piece.kind != "part" else "the part"
        if own.get("on") is False:
            off.append(name)
        elif own.get("steps"):
            hand.append(name)
        else:
            changed.append(name)
    parts = []
    if off:
        parts.append("Off: {}.".format(pp.join_words(off)))
    if hand:
        parts.append("Hand-made: {}.".format(pp.join_words(hand)))
    if changed:
        parts.append("Changed: {}.".format(pp.join_words(changed)))
    return " ".join(parts)
