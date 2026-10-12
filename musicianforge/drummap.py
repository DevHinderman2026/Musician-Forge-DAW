"""Drum sounds a kit does not have (Russell, 10 Oct 2026: "where there was supposed to be a splash cymbal the
patch did not support it ... it might have to route through the crash").

General MIDI numbers each drum sound (36 a kick, 49 a crash, 55 a splash...), but not every kit has every one:
Musician Forge's Forge House and Forge Trap kits have no splash or china, and other programs' kits often lack
them too. A sound a kit does not have is played on the nearest one it does have, cymbals first on the crash
(or the ride, for ride sounds), so a fill never ends in silence.

- `substitutes(available)` is used by the synthesizer for Musician Forge's own sound: it knows exactly which
  notes the chosen kit has (sf2keys.py reads them from the SoundFont).
- `EXPORT_ROUTES` is used by the MIDI export, which cannot know the other program's kit: the cymbals kits
  most often lack are written as the crash and the ride, which every kit has.
Percussion with no sensible stand-in (tambourine, cowbell, congas...) is left as it is.
"""

KICK2, KICK = 35, 36
SIDE_STICK, SNARE, CLAP, SNARE2 = 37, 38, 39, 40
CLOSED_HAT, PEDAL_HAT, OPEN_HAT = 42, 44, 46
TOM_LOW_FLOOR, TOM_HIGH_FLOOR, TOM_LOW, TOM_LOW_MID, TOM_HIGH_MID, TOM_HIGH = 41, 43, 45, 47, 48, 50
CRASH, RIDE, CHINA, RIDE_BELL, SPLASH, CRASH2, RIDE2 = 49, 51, 52, 53, 55, 57, 59

# for each sound: the stand-ins to try, nearest first
FALLBACKS = {
    SPLASH: (CRASH, CRASH2, CHINA),
    CHINA: (CRASH, CRASH2, SPLASH),
    CRASH2: (CRASH, SPLASH, CHINA),
    CRASH: (CRASH2, SPLASH, CHINA),
    RIDE2: (RIDE, RIDE_BELL),
    RIDE: (RIDE2, RIDE_BELL),
    RIDE_BELL: (RIDE, RIDE2),
    PEDAL_HAT: (CLOSED_HAT,),
    OPEN_HAT: (CLOSED_HAT,),
    CLOSED_HAT: (PEDAL_HAT,),
    KICK2: (KICK,),
    KICK: (KICK2,),
    SNARE2: (SNARE,),
    SNARE: (SNARE2,),
    SIDE_STICK: (SNARE2, SNARE),
    TOM_HIGH: (TOM_HIGH_MID, TOM_LOW_MID),
    TOM_HIGH_MID: (TOM_HIGH, TOM_LOW_MID),
    TOM_LOW_MID: (TOM_HIGH_MID, TOM_LOW),
    TOM_LOW: (TOM_LOW_MID, TOM_HIGH_FLOOR),
    TOM_HIGH_FLOOR: (TOM_LOW, TOM_LOW_FLOOR),
    TOM_LOW_FLOOR: (TOM_HIGH_FLOOR, TOM_LOW),
}

# what the MIDI export writes instead: the cymbals other programs' kits most often lack
EXPORT_ROUTES = {SPLASH: CRASH, CHINA: CRASH, RIDE2: RIDE}


def substitutes(available):
    """{note the kit lacks: the note to play instead} for a kit whose sounding notes are `available`."""
    found = {}
    for note, choices in FALLBACKS.items():
        if note in available:
            continue
        for choice in choices:
            if choice in available:
                found[note] = choice
                break
    return found


def for_export(pitch):
    """The note the MIDI export writes for a drum note (the same note, unless kits often lack it)."""
    return EXPORT_ROUTES.get(pitch, pitch)
