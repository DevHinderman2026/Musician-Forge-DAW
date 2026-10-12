"""Grouping SoundFont instruments into the General MIDI families.

Makes the instrument chooser easy to browse with a screen reader: first pick
a family (Piano, Guitar, Bass, Drum kits...), then an instrument in it.
"""

FAMILIES = [
    "Piano", "Chromatic Percussion", "Organ", "Guitar", "Bass", "Strings", "Ensemble", "Brass",
    "Reed", "Pipe", "Synth Lead", "Synth Pad", "Synth Effects", "Ethnic", "Percussive",
    "Sound Effects",
]
DRUM_FAMILY = "Drum Kits"
GUITAR_PACK_BANKS = (40, 41)   # the FreePats guitar packs (packs.py): program 0 on their own banks
# GeneralUser GS keeps a second copy of its 13 drum kits on bank 120 ("Standard 1 Kit", "808/909 Kit"...), for
# playing a kit on an ordinary channel. Grouped by program number they were scattered through Piano, Organ, Guitar,
# Bass, Strings and the rest (Russell, 10 Oct 2026: "the drum kits are scattered in the guitar instrument family").
# They belong with the drum kits, and a copy whose real kit (bank 128, the same program) is there is not listed at
# all: the real one plays as a drum kit (the drum layout, the drummer); a song that chose a copy still plays it.
DRUM_COPY_BANKS = (120,)


def family_of(preset):
    if preset.bank == 128 or preset.bank in DRUM_COPY_BANKS:
        return DRUM_FAMILY
    if preset.bank in GUITAR_PACK_BANKS:
        return "Guitar"
    return FAMILIES[max(0, min(127, preset.program)) // 8]


def group_presets(presets):
    """{family: [presets]} in General MIDI order, drum kits last; empty families left out."""
    groups = {}
    kits = {p.program for p in presets if p.bank == 128}
    for preset in presets:
        if preset.bank in DRUM_COPY_BANKS and preset.program in kits:
            continue                       # the same kit is listed from the drum kits bank
        groups.setdefault(family_of(preset), []).append(preset)
    ordered = {}
    for family in FAMILIES + [DRUM_FAMILY]:
        if family in groups:
            ordered[family] = sorted(groups[family], key=lambda p: (p.program, p.bank))
    return ordered


def find_preset(presets, bank, program):
    for preset in presets:
        if preset.bank == bank and preset.program == program:
            return preset
    return None


FORGE_BANK = 100  # Musician Forge's own instruments (forgekit.py)


def describe_preset(preset):
    """Name for lists; variations in other banks get their bank number."""
    if preset.bank in (0, 128, FORGE_BANK) + GUITAR_PACK_BANKS:
        return preset.name
    return "{} (variation {})".format(preset.name, preset.bank)
