"""Opening projects saved by older versions of Musician Forge, and saying plainly when one is from a newer version.

The story of an old project, when it opens in a new Musician Forge:

1. The file is read as it is. Nothing on disk changes until you choose Save; then the file as it was goes to
   the .bak file, so the version you saved before is kept.
2. ``upgrade`` brings the project's data from the version that saved it up to today's FILE_VERSION one step at a
   time (4 to 5, 5 to 6, and so on). A step only adds what a newer version expects, or renames what an older one
   called something else; it never drops anything you made. Every rhythm player region that was saved without a
   rules number gets the one it was made under (rules 1, from before 10 Oct 2026), so it goes on playing the notes it
   played: new rules are for new regions, and for a region you change by hand (session_music sets players.RULES then).
3. Song.from_dict reads the upgraded data. Settings a step did not touch keep their old meaning, because
   players.clean_settings and player_pieces.clean_pieces read older settings the way the version that saved them
   played them.

Adding a version: raise FILE_VERSION in song.py, say in its note what changed, and add one ``_to_<version>`` step
here (even an empty one). A step must be safe to run on data that has already been upgraded (upgrade is run again
on a project's own saved copies), so it adds with setdefault and never overwrites.

A project saved by a newer Musician Forge is refused (NewerVersionError) rather than opened read-only: this version
would not know its new styles, pieces or settings, would quietly play something else in their place, and would lose
them if you saved. The message says what to do: update Musician Forge.
"""


class SongFileError(Exception):
    """A song file could not be read."""


class NewerVersionError(SongFileError):
    """A song file saved by a newer Musician Forge than this one. The file is not changed."""


def saved_version(data):
    """The version of Musician Forge's file format that saved this project (1 when the file has none).
    Raises TypeError or ValueError when it is not a whole number (Song.from_dict reports that as damage)."""
    if isinstance(data.get("version"), bool):
        raise ValueError("the version is not a number")
    version = int(data.get("version", 1))
    return max(1, version)


def upgrade(data):
    """Bring a project's data (a dict read from a .mforge file) up to today's FILE_VERSION, one version at a time.
    The dict is changed in place and returned. Raises NewerVersionError for a file from a newer version."""
    from .song import FILE_VERSION

    version = saved_version(data)
    if version > FILE_VERSION:
        raise NewerVersionError(
            "This project was saved by a newer version of Musician Forge (its file is version {}; this Musician Forge "
            "reads up to version {}). Update Musician Forge with Install or Update Musician Forge.bat, then open it "
            "again. The file has not been changed.".format(version, FILE_VERSION))
    while version < FILE_VERSION:
        STEPS[version](data)
        version += 1
        data["version"] = version
    return data


# -- the steps, each from the version named to the next -------------------------------------------------------------
def _tracks(data):
    """The track dicts of a project, leaving anything damaged to Song.from_dict to report."""
    tracks = data.get("tracks")
    return [td for td in tracks if isinstance(td, dict)] if isinstance(tracks, list) else []


def _player_settings(data):
    """Every rhythm player's settings dict in the project."""
    found = []
    for td in _tracks(data):
        for region in td.get("note_regions") or []:
            if isinstance(region, list) and len(region) > 4 and isinstance(region[4], dict):
                found.append(region[4])
    return found


def _to_2(data):
    """Song sections. An empty list gets one section long enough for every note (Song.fit_last_section)."""
    data.setdefault("sections", [])


def _to_3(data):
    """Audio tracks: every track says what kind it is and has a list of recordings."""
    for td in _tracks(data):
        td.setdefault("kind", "instrument")
        td.setdefault("regions", [])
        td.setdefault("stereo", False)
        td.setdefault("monitor", False)


def _to_4(data):
    """Regions on instrument tracks. Song.from_dict makes one for each section that has notes on the track
    (regions.migrate), since that needs the song's timeline."""
    for td in _tracks(data):
        td.setdefault("note_regions", [])


def _to_5(data):
    """Effects on tracks."""
    for td in _tracks(data):
        td.setdefault("effects", [])


def _to_6(data):
    """The chord track, rhythm players and region looping: a region is [start, end, name, mute, player, loops]."""
    data.setdefault("chords", [])
    for td in _tracks(data):
        for region in td.get("note_regions") or []:
            if isinstance(region, list) and len(region) >= 2:
                for missing in ("", False, None, 1)[len(region) - 2:]:
                    region.append(missing)


def _to_7(data):
    """Automation lanes."""
    for td in _tracks(data):
        td.setdefault("automation", [])


def _to_8(data):
    """Rhythm players' variations, performances and pieces (0.9.2). Before, "variation" was the seed of the
    performance: it becomes the performance, and the variation is 1 (the style as it was), the same notes."""
    for settings in _player_settings(data):
        if "performance" not in settings:
            settings["performance"] = settings.get("variation", 1)
            settings["variation"] = 1


def _to_9(data):
    """0.9.8: the drummer's Closed hi-hat and Open hi-hat become the Hi-hat (the hand) and the Hi-hat pedal (the
    foot), each region's pieces rewritten so it plays the same notes (player_pieces.old_pieces_to_new), and a
    track's kit-piece loudness with them (player_pieces.old_kit_levels_to_new). From here on every rhythm player
    region records the rules it plays by: one saved without a rules number was made before 10 Oct 2026 and keeps
    rules 1, so it plays as it did."""
    from . import player_pieces, players    # (here, not at the top: players imports song)
    for settings in _player_settings(data):
        settings.setdefault("rules", 1)
        if settings.get("player") != "anvil" or not isinstance(settings.get("pieces"), dict):
            continue
        style = settings.get("style") if settings.get("style") in players._DRUM_STYLES else None
        if style is None:
            continue
        rules = settings["rules"] if isinstance(settings["rules"], int) and not isinstance(settings["rules"], bool) else 1
        try:
            variation = max(1, min(players.pv.count("anvil", style), int(settings.get("variation", 1))))
        except (TypeError, ValueError, OverflowError):
            variation = 1
        try:
            settings["pieces"] = player_pieces.old_pieces_to_new(settings["pieces"], style, variation,
                                                                 players._DRUM_STYLES, rules)
        except Exception:                   # damaged pieces: left for clean_pieces to sort out
            pass
    for td in _tracks(data):
        if isinstance(td, dict) and isinstance(td.get("kit_levels"), dict):
            td["kit_levels"] = player_pieces.old_kit_levels_to_new(td["kit_levels"])


STEPS = {1: _to_2, 2: _to_3, 3: _to_4, 4: _to_5, 5: _to_6, 6: _to_7, 7: _to_8, 8: _to_9}
