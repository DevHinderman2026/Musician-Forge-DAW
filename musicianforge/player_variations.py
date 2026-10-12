"""Real variations for every rhythm player style (version 0.9.2; Russell, 8 Oct 2026: "super important").

A style has a set of variations, numbered from 1: each is a recognisably different groove or part (for
drums, where the kick and snare go, the hi-hat or ride rhythm and where the accents fall; for bass, keys,
synth and guitar, the rhythm and the notes' roles). Variation 1 is each style exactly as it was in 0.8, so
older projects sound the same. Reforge never changes the variation: it plays a new performance (fills,
ghost notes, small changes) of the variation chosen.

The grooves are our own, written from how each kind of music is played (the research notes are in the
development notes), not copied from any program.

Drums: a variation lists the voices it changes, each with 16 sixteenth-note steps for one 4/4 bar (1 always
plays: the backbone; a smaller number is a chance that grows with complexity, marked "i" or "c"; since 0.9.4 intensity only changes
how hard), its
loudness, and what scales it ("g" added marks ghost notes). None removes a voice of the style's own table.

Melodic players: a variation is a figure, one character per sixteenth, the way a part could be jotted down:
a letter starts a note (its role picks the pitch from the chord: R root, O octave, F fifth, L low root,
A a note a half step from the root of the chord on the next beat, leading into it, W walking note, G ghost,
C chord, H left hand, S shell voicing, P power chord, U power chord a step up, D strum down, V strum up, Y
arpeggio note, K picked note), "." holds the note before, "-" is a rest. Two rows can be laid on top of each
other with "|" (the left hand under a chord). N plays the chord of the next bar early (an anticipation; when the
chord does not change, it is struck again), B a note of an Alberti bass (low, high, middle, high).
"""

# drum voices (General MIDI numbers, as in players.py)
KICK, KICK2, SNARE, SNARE2, CLAP, RIM = 36, 35, 38, 40, 39, 37
HAT, PEDAL, OPEN_HAT = 42, 44, 46
TOM_HIGH, TOM_MID, TOM_LOW, TOM_FLOOR = 50, 48, 45, 41
CRASH, CRASH2, RIDE, RIDE_BELL, CHINA, SPLASH = 49, 57, 51, 53, 52, 55
TAMBOURINE, COWBELL, SHAKER, MARACAS = 54, 56, 82, 70
CONGA_MUTE, CONGA_OPEN, CONGA_LOW, BONGO_HIGH, BONGO_LOW, CLAVES = 62, 63, 64, 60, 61, 75
FORGE_SHAKER = 54


def steps(*on, value=1.0, also=None):
    """16 steps with `value` on the given steps (and the steps in `also`, a {step: value} dict)."""
    row = [0.0] * 16
    for step in on:
        row[step] = value
    for step, chance in (also or {}).items():
        row[step] = chance
    return row


EIGHTHS = steps(0, 2, 4, 6, 8, 10, 12, 14)
QUARTERS = steps(0, 4, 8, 12)
OFFBEATS = steps(2, 6, 10, 14)
SIXTEENTHS = [1.0] * 16

# style -> [(description, {voice: (16 steps, loudness, scaled) or None})]; variation 1 changes nothing
DRUMS = {
    "dubstep": [
        ("Kick on one, a huge snare on three, busy hi-hats", {}),
        ("Kick on one and the and of two, hi-hats in eighths", {
            KICK: (steps(0, 6, also={14: .25}), 118, "c"), HAT: (EIGHTHS, 82, ""), FORGE_SHAKER: None}),
        ("A kick on the and of four leads into the next bar; hi-hats in a three-three-two pattern", {
            KICK: (steps(0, 14, also={10: .2}), 118, "c"), HAT: (steps(0, 3, 6, 8, 11, 14), 84, "")}),
        ("Sparse and heavy: kick and snare alone, hi-hats only on the beats", {
            KICK: (steps(0), 120, ""), CLAP: None, HAT: (QUARTERS, 78, ""), OPEN_HAT: None, FORGE_SHAKER: None}),
        ("Busy: a second kick on the and of three, ghost snares around the big snare", {
            KICK: (steps(0, 10, also={11: .4}), 118, "c"),
            SNARE2: (steps(also={6: .45, 7: .35, 10: .3, 15: .4}), 58, "cg")}),
        ("Half-time shuffle: kick on one and the e of three, hi-hats skipping", {
            KICK: (steps(0, 9), 118, "c"), HAT: (steps(0, 2, 3, 5, 6, 8, 10, 11, 13, 14), 80, "i")}),
    ],
    "house": [
        ("Four on the floor, claps on two and four, open hi-hats on the offbeats, a shaker", {}),
        ("Deep: no closed hi-hat, a shaker in every sixteenth, a rim click on the and of four", {
            HAT: None, FORGE_SHAKER: ([.9] * 16, 58, ""), RIM: (steps(14, also={3: .3}), 72, "c")}),
        ("Two-step garage: kick on one and the and of three, claps on two and four", {
            KICK: (steps(0, 10, also={7: .3}), 115, "c"), OPEN_HAT: (steps(also={6: .5, 14: .5}), 85, "i"),
            HAT: (steps(0, 2, 3, 4, 6, 8, 10, 11, 12, 14), 66, "")}),
        ("Driving: open hi-hats on every offbeat, closed hi-hats in sixteenths, a pushed clap", {
            HAT: ([.8] * 16, 62, "i"), CLAP: (steps(4, 12, also={15: .4}), 105, "")}),
        ("Disco house: snare and clap together on two and four, closed hi-hats in eighths", {
            SNARE: (steps(4, 12), 100, ""), HAT: (EIGHTHS, 70, ""), OPEN_HAT: (steps(also={14: .6}), 85, "")}),
    ],
    "trap": [
        ("Kick on one with syncopated pickups, the clap on three, hi-hats in eighths and sixteenths", {}),
        ("Bounce: kicks on one, the a of two and the and of three", {
            KICK: (steps(0, 7, 10, also={13: .3}), 118, "c"), HAT: (EIGHTHS, 84, "")}),
        ("Hi-hats in a three-three-two pattern over a kick on one and the a of three", {
            KICK: (steps(0, 11, also={5: .3}), 118, "c"), HAT: (steps(0, 3, 6, 8, 11, 14), 82, "")}),
        ("Sparse: one kick, the clap, hi-hats on the beats with rolls", {
            KICK: (steps(0, also={13: .4}), 120, "c"), SNARE: None, HAT: (QUARTERS, 84, "")}),
        ("Drill: kicks pushed off the beat, the clap on three and a late snare on the and of four", {
            KICK: (steps(0, 6, 13, also={3: .3}), 118, "c"), SNARE: (steps(14, also={11: .3}), 104, "c"),
            HAT: (steps(0, 2, 3, 5, 6, 8, 10, 11, 13, 14), 82, "")}),
    ],
    "rock": [
        ("Kick on one and three, snare on two and four, eighth-note hi-hats", {}),
        ("Kick on one, the and of two, and three", {KICK: (steps(0, 6, 8, also={10: .2}), 112, "c")}),
        ("The ride cymbal in eighths instead of the hi-hat", {
            HAT: None, OPEN_HAT: None, RIDE: (EIGHTHS, 84, "")}),
        ("Four on the floor, with an open hi-hat on the and of four", {
            KICK: (QUARTERS, 110, ""), OPEN_HAT: (steps(14), 88, "")}),
        ("Half time: the snare on three, kick on one and the and of three", {
            KICK: (steps(0, 10, also={6: .25}), 112, "c"), SNARE: (steps(8), 114, "")}),
        ("Driving sixteenths on the hi-hat, kick on one, three and the and of three", {
            KICK: (steps(0, 8, 10), 112, ""), HAT: (SIXTEENTHS, 78, "")}),
    ],
    "hard_rock": [
        ("Big and driving: pushed kicks, open hi-hats in eighths", {}),
        ("Ride cymbal in eighths, kick on one and three", {
            OPEN_HAT: None, HAT: None, RIDE: (EIGHTHS, 92, ""), KICK: (steps(0, 8, also={6: .4}), 118, "c")}),
        ("Pushed: the and of four ties into the next bar", {
            KICK: (steps(0, 8, 14), 118, ""), OPEN_HAT: (steps(14), 95, ""), HAT: (EIGHTHS, 80, "")}),
        ("Half-time stomp: snare on three, open hi-hats on the beats", {
            KICK: (steps(0, 10, also={3: .5}), 120, "c"), SNARE: (steps(8), 122, ""), OPEN_HAT: (QUARTERS, 92, ""),
            HAT: None}),
        ("Gallop kicks: an eighth and two sixteenths on one and three", {
            KICK: (steps(0, 2, 3, 8, 10, 11), 116, "")}),
    ],
    "metal": [
        ("Double kick in eighths and sixteenths, a solid backbeat", {}),
        ("Gallop: the kick in an eighth and two sixteenths on every beat", {
            KICK: (steps(0, 2, 3, 4, 6, 7, 8, 10, 11, 12, 14, 15), 115, "")}),
        ("Thrash: kick on the beats, snare on every offbeat", {
            KICK: (QUARTERS, 118, ""), SNARE: (OFFBEATS, 118, ""), HAT: None, CHINA: None,
            CRASH: (QUARTERS, 96, "")}),
        ("Half-time breakdown: kicks with the riff, snare on three, china on the beats", {
            KICK: (steps(0, 3, 6, 10, 13), 120, ""), SNARE: (steps(8), 124, ""), HAT: None,
            CHINA: (QUARTERS, 100, "")}),
        ("Blast beat: kick and snare together in eighths, ride on top", {
            KICK: (EIGHTHS, 112, ""), SNARE: (EIGHTHS, 104, ""), HAT: None, RIDE: (EIGHTHS, 90, "")}),
    ],
    "jazz": [
        ("Swinging ride, hi-hat on two and four, feathered kick", {}),
        ("Two feel: the kick on one and three, the ride a little simpler", {
            KICK: (steps(0, 8), 50, ""), RIDE: (steps(0, 4, 8, 12, also={6: .5, 14: .5}), 82, "")}),
        ("Busier comping on the snare", {
            SNARE: (steps(also={2: .4, 5: .3, 6: .5, 10: .45, 13: .3, 14: .5}), 56, "c")}),
        ("Latin jazz: the ride bell in a clave rhythm, a cross-stick on two and four, the kick in a tumbao", {
            RIDE: None, RIDE_BELL: (steps(0, 3, 6, 10, 12), 80, ""), RIM: (steps(4, 12), 64, ""),
            KICK: (steps(0, 6, 8, 14), 52, ""), SNARE: None}),
    ],
    "funk": [
        ("Syncopated sixteenth kicks, ghost notes, tight sixteenth hi-hats", {}),
        ("Linear: kick, snare and hi-hat never play at the same moment", {
            KICK: (steps(0, 7, 10), 112, ""), SNARE: (steps(4, 12, also={9: .5, 15: .4}), 112, "c"),
            HAT: (steps(1, 2, 3, 5, 6, 8, 11, 13, 14), 78, ""), OPEN_HAT: None}),
        ("Disco: four on the floor, open hi-hats on the offbeats", {
            KICK: (QUARTERS, 110, ""), OPEN_HAT: (OFFBEATS, 88, ""), HAT: ([.6] * 16, 70, "i")}),
        ("Half-time funk: the snare on three, kicks around it", {
            KICK: (steps(0, 3, 6, 11, also={14: .4}), 112, "c"), SNARE: (steps(8), 116, "")}),
    ],
    "pop": [
        ("A clean, steady beat with eighth hi-hats and a tambourine when it builds", {}),
        ("Four on the floor pop", {KICK: (QUARTERS, 108, "")}),
        ("Half-time ballad: snare on three, kick on one and the and of three, no tambourine", {
            KICK: (steps(0, 10), 106, ""), SNARE: (steps(8), 108, ""), TAMBOURINE: None}),
        ("Claps with the snare on two and four", {CLAP: (steps(4, 12), 96, "")}),
        ("Toms instead of hi-hats: the floor tom in eighths", {
            HAT: None, TOM_FLOOR: (EIGHTHS, 74, ""), TAMBOURINE: None}),
    ],
    "hand_percussion": [
        ("Congas, bongos and claves (three-two son clave)", {}),
        ("Rumba clave and bongos in eighths", {
            CLAVES: (steps(0, 3, 7, 10, 12), 85, ""), BONGO_HIGH: (EIGHTHS, 72, "")}),
        ("Tumbao: open conga slaps on four and its and", {
            CONGA_OPEN: (steps(12, 14, also={6: .4}), 96, ""), CONGA_MUTE: (QUARTERS, 80, "")}),
        ("A cowbell on every beat drives it", {COWBELL: (QUARTERS, 80, ""), CLAVES: None}),
    ],
    "shakers": [
        ("A shaker in sixteenths and a tambourine on the backbeat", {}),
        ("A shaker in eighths", {SHAKER: (EIGHTHS, 72, ""), MARACAS: None}),
        ("A tambourine in sixteenths instead of the shaker", {
            TAMBOURINE: ([1.0, .6] * 8, 80, ""), SHAKER: None}),
        ("Cowbell on the beats over the shaker", {COWBELL: (QUARTERS, 78, ""), SHAKER: ([.8] * 16, 64, "")}),
    ],
}

# style -> [(description, figure or None for the 0.8 rules)]
MELODIC = {
    "bellows": {
        "eighths": [("Steady eighth notes on the root", None),
                    ("Root and octave in turn", "R.O.R.O.R.O.R.O."),
                    ("Dotted eighths", "R..R..R.R..R..R."),
                    ("Three eighths and a held note, twice a bar", "R.R.R...R.R.R...")],
        "roots": [("Long notes on the root", None),
                  ("Root and fifth", "R.......F......."),
                  ("A long root with a pickup into the next chord", "R...........A..."),
                  ("A whole note on the root", "R...............")],
        "funk": [("Syncopated sixteenths, octave pops and ghost notes", None),
                 ("Octave pops on the and of two and the and of four", "R.....O.R.....O."),
                 ("Tight sixteenth syncopation", "R-RR--R-R-RR--R-"),
                 ("Big notes with space between them", "R.--O---R.--O-A-")],
        "walking": [("A walking line in quarter notes", None),
                    ("Two feel: half notes", "R.......W......."),
                    ("Walking with eighth-note pickups", "R...W...W..AW..A"),
                    ("A chromatic approach into every beat", "R..AW..AW..AW..A")],
        "dubstep": [("Deep sub in half time, with drops to the low octave", None),
                    ("One long sub note held all bar", "L..............."),
                    ("Wobble eighths on the sub", "L.L.L.L.L.L.L.L."),
                    ("Syncopated sub: one, the a of two, the and of three", "L......L..L....."),
                    ],
        "house": [("Short offbeat notes against the four-on-the-floor kick", None),
                  ("Offbeat octaves", "--O---O---O---O-"),
                  ("Rolling sixteenths", "RRORRRORRROR-RRA"),
                  ("A sustained root with a pickup", "R.............A.")],
        "trap": [("Long 808 notes on syncopated hits", None),
                 ("One long 808 per bar", "R..............."),
                 ("Bouncing 808: one, the a of two, the and of three", "R......R..R....."),
                 ("808 locked with the kick: one, the and of two, four", "R.....R.....R...")],
        "metal": [("Low gallops and sixteenth chugs", None),
                  ("Straight sixteenths on the low root", "LLLLLLLLLLLLLLLL"),
                  ("Eighth chugs", "L.L.L.L.L.L.L.L."),
                  ("Reverse gallop: two sixteenths and an eighth", "LLL.LLL.LLL.LLL.")],
    },
    "ember": {
        "block": [("Full chords on the downbeats, the root in the left hand", None),
                  ("Chords on every beat", "C...C...C...C...|H.......H......."),
                  ("Charleston: one and the and of two", "C.....C.........|H..............."),
                  ("Anticipated: the next chord arrives on the and of four", "C.............N.|H...............")],
        "pulse": [("Chords pulsing in eighth notes", None),
                  ("Quarter-note pulse", "C...C...C...C..."),
                  ("Sixteenth pulse, accented on the beats", "CCCCCCCCCCCCCCCC"),
                  ("Syncopated pulse: three-three-two", "C..C..C.C..C..C.")],
        "arpeggio": [("Broken chords flowing up and down", None),
                     ("Slow arpeggio in quarter notes", "Y...Y...Y...Y...|H..............."),
                     ("Sixteenth-note arpeggio", "YYYYYYYYYYYYYYYY|H..............."),
                     ("Alberti bass: low, high, middle, high", "B.B.B.B.B.B.B.B.")],
        "comping": [("Short, syncopated chords with sevenths and ninths", None),
                    ("Charleston comping", "S.....S........."),
                    ("Comping on two and four", "----S.------S.--"),
                    ("Anticipations: the and of every beat", "--S---S---S---S-")],
        "stabs": [("Short offbeat chord stabs", None),
                  ("Stabs on two and four", "----C-------C---"),
                  ("Sixteenth stabs before the beat", "---C---C---C---C"),
                  ("House piano: one, the a of two, the and of three", "C......C..C.....")],
    },
    "spark": {
        "pad": [("Sustained chords that change smoothly", None),
                ("Two pad chords a bar", "C.......C......."),
                ("A swelling pad on every beat", "C...C...C...C..."),
                ("A held pad with the next chord pushed in early", "C.............N.")],
        "arp_up": [("Chord notes climbing in sixteenths", None),
                   ("Climbing in eighths", "Y.Y.Y.Y.Y.Y.Y.Y."),
                   ("Climbing in a three-three-two rhythm", "Y..Y..Y.Y..Y..Y."),
                   ("Sixteenths with a rest on each beat", "-YYY-YYY-YYY-YYY")],
        "arp_updown": [("Chord notes climbing and falling", None),
                       ("Up and down in eighths", "Y.Y.Y.Y.Y.Y.Y.Y."),
                       ("Up and down in a three-three-two rhythm", "Y..Y..Y.Y..Y..Y."),
                       ("Sixteenths with a rest at the end of each beat", "YYY-YYY-YYY-YYY-")],
        "pluck": [("A rhythmic pluck pattern on the chord notes", None),
                  ("Plucks in a three-three-two rhythm", "Y..Y..Y.Y..Y..Y."),
                  ("Offbeat plucks", "--Y---Y---Y---Y-"),
                  ("Busy plucks", "Y-YY-YY-Y-YY-YY-")],
        "gate": [("The chord chopped into a sixteenth-note rhythm", None),
                 ("Chopped in eighths", "C-C-C-C-C-C-C-C-"),
                 ("The classic trance gate: on, off, on, on", "C-CC-CC-C-CC-CC-"),
                 ("Stutter gate", "CCC-CC-CCCC-CC-C")],
        "stabs": [("Hard, syncopated chord stabs", None),
                  ("Stabs on one and the a of two", "C......C........"),
                  ("Stabs in a three-three-two rhythm", "C..C..C.C..C..C."),
                  ("Answering stabs on four", "C-----------C-C-")],
    },
    "hammer": {
        "chugs": [("Tight, muted power chords in sixteenths", None),
                  ("Muted eighths", "P.P.P.P.P.P.P.P."),
                  ("Chugs with a rest on every beat's e", "P-PPP-PPP-PPP-PP"),
                  ("Sixteenths with an accent push on the and of four", "PPPPPPPPPPPPPPU.")],
        "gallop": [("An eighth and two sixteenths on every beat", None),
                   ("Reverse gallop: two sixteenths and an eighth", "PPP.PPP.PPP.PPP."),
                   ("Gallop on one and three, eighths between", "P.PPP.P.P.PPP.P."),
                   ("A syncopated gallop", "P..PP.P..PP.P.PP")],
        "hard_rock": [("Power chords in eighths, ringing on the big beats", None),
                      ("Big chords on one and three", "P.......P......."),
                      ("Pushed riff: chords on one, the and of two and four", "P.....P.....P..."),
                      ("Eighths with a step-up chord at the end", "P.P.P.P.P.P.U.U.")],
        "palm_eighths": [("Steady muted eighth notes on the root power chord", None),
                         ("Muted quarter notes", "P...P...P...P..."),
                         ("Muted eighths, skipping the and of two", "P.P.P...P.P.P.P."),
                         ("Muted sixteenths on the beats", "PP..PP..PP..PP..")],
        "strum": [("Full chords strummed down and up", None),
                  ("Down strums on every beat", "D...D...D...D..."),
                  ("Island strum: down, down-up, up-down-up", "D...D.V...V.D.V."),
                  ("Eighth-note strums down and up", "D.V.D.V.D.V.D.V.")],
        "arpeggio": [("Chord notes picked one at a time", None),
                     ("Picked in quarter notes", "K...K...K...K..."),
                     ("Picked in sixteenths", "KKKKKKKKKKKKKKKK"),
                     ("Picked with a ringing bass on one", "K...K.K.K.K.K.K.")],
    },
}

ROLES = {"R": "root", "O": "octave", "F": "fifth", "L": "low", "A": "lead", "W": "walk", "G": "ghost",
         "C": "chord", "N": "next", "H": "left", "S": "shell", "P": "power", "U": "power_up", "D": "strum_down",
         "V": "strum_up", "Y": "arp", "B": "alberti", "K": "pick"}


def count(player_key, style_key):
    """How many variations a style has (at least 4)."""
    if player_key == "anvil":
        return len(DRUMS.get(style_key, [None]))
    return len(MELODIC.get(player_key, {}).get(style_key, [None]))


def description(player_key, style_key, variation):
    """'Kick on one and the and of two, hi-hats in eighths'."""
    table = DRUMS.get(style_key) if player_key == "anvil" else MELODIC.get(player_key, {}).get(style_key)
    if not table:
        return "the style's own rhythm"
    return table[max(0, min(len(table), int(variation)) - 1)][0]


def drum_overrides(style_key, variation):
    table = DRUMS.get(style_key)
    if not table or variation <= 1:
        return {}
    return table[min(len(table), int(variation)) - 1][1]


def figure(player_key, style_key, variation):
    """The figure for a melodic variation, or None (variation 1: the style's own rules)."""
    table = MELODIC.get(player_key, {}).get(style_key)
    if not table or variation <= 1:
        return None
    return table[min(len(table), int(variation)) - 1][1]


def figure_events(text, steps, beat, arp_shape="up", step_map=None, beats=None):
    """[(step, length in steps, accent, role)] for one bar from a figure (repeated or cut to the bar). step_map and
    beats: the bar's meter (players._Bar.map and .beats), so a 16-step figure fits 3/4, 6/8 or 7/8 beat by beat."""
    events = []
    rows = text.split("|")
    for row_number, row in enumerate(rows):
        if row and step_map is not None and len(row) == 16 and len(step_map) == steps:
            cells = "".join(row[step_map[s]] if step_map[s] > step_map[s - 1] or s == 0 or row[step_map[s]] == "."
                            else "." for s in range(steps))          # a cell met again in a dotted beat holds on
        else:
            cells = (row * (steps // len(row) + 1))[:steps] if row else ""
        k = 0
        for step, cell in enumerate(cells):
            if cell in ROLES:
                length = 1
                while step + length < steps and cells[step + length] == ".":
                    length += 1
                role = ROLES[cell]
                if role in ("arp", "alberti"):
                    role = "{}:{}".format(arp_shape if role == "arp" else "alberti", k)
                    k += 1
                elif role == "pick":
                    role = "pick:{}:0".format(k)
                    k += 1
                accent = 1.0 if (step in beats if beats is not None else step % beat == 0) else 0.75
                events.append((step, length, accent if row_number == 0 else 0.85, role))
    return events
