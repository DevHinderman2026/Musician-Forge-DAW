"""Session features from version 0.8: the chord track, rhythm players (with Follow and Reforge),
and trimming and looping regions. Mixed into session.Session; like the rest of the Session,
nothing here touches a window, so it is all tested headless."""

import copy
import json
import logging
import os

from . import arrangement, chords, keyboard_map, onsets, player_pieces, players, regions, theory
from .song import AUDIO_RATE, Instrument

log = logging.getLogger("musicianforge.session")

FOLLOW_CHOICES = ("chords", "track", "none")
FOLLOW_NAMES = {"chords": "Chord track", "track": "Another track", "none": "Nothing (the style alone)"}
COALESCE = ("intensity", "complexity", "fills", "fill_complexity", "swing", "follow_amount", "sensitivity")
SETTING_WORDS = {"style": "style", "intensity": "intensity", "complexity": "complexity", "fills": "fill amount",
                 "fill_complexity": "fill complexity",
                 "swing": "swing", "swing_note": "swing feel", "follow": "follow", "follow_track": "track to follow",
                 "follow_amount": "follow amount", "sensitivity": "hit sensitivity",
                 "play_after_reforge": "play after Reforge"}
PIECE_COALESCE = ("busy", "level", "ghost_level", "octave")       # sliders and number boxes: one undo step per run


def for_each_selected_region(method):
    """While the rhythm player editor is open on several selected regions (Russell, 10 Oct 2026: "if multiple
    regions are selected the Open region button ... edits all the regions"), a change to the region the editor
    is on is made to every one of them too, as one undo step. A change one of the others cannot take (a variation
    its style does not have, say) leaves that one as it was."""
    def wrapped(self, track_id, index, *args, **kwargs):
        group = getattr(self, "player_group", None)
        if not group or getattr(self, "_in_player_group", False) or group[0] != track_id:
            return method(self, track_id, index, *args, **kwargs)
        track = self.song.track_by_id(track_id)
        here = track.note_regions[index].start if track is not None and 0 <= index < len(track.note_regions) else None
        others = [start for start in group[1] if start != here]
        if here not in group[1] or not others:
            return method(self, track_id, index, *args, **kwargs)
        key = (method.__name__, track_id, tuple(sorted(group[1])), args[:1], tuple(sorted(kwargs)))
        reforging = method.__name__ == "reforge"
        self._in_player_group = True
        try:
            with self.edit_group("{} in {} regions".format(method.__name__.replace("_", " "), len(group[1])),
                                 merge=method.__name__ in ("update_player", "update_piece"), merge_key=key):
                # a Reforge plays its region once every region has its new performance (below)
                result = method(self, track_id, index, *args, **(dict(kwargs, play=False) if reforging else kwargs))
                said = getattr(self, "last_announcement", None)
                # the others say nothing, and a Reforge plays only the region in the editor (the final review,
                # 10 Oct 2026: each one took the playing over in turn, so the last region of the selection played)
                quiet = dict(kwargs, speak=False)
                if reforging:
                    quiet["play"] = False
                stayed = 0
                for start in others:
                    other = next((i for i, r in enumerate(self.song.track_by_id(track_id).note_regions)
                                  if r.start == start and r.player), None)
                    if other is None:
                        continue
                    try:
                        method(self, track_id, other, *args, **quiet)
                    except ValueError:
                        stayed += 1              # a variation its style does not have, hand-made steps...
                if reforging and said:
                    self.announce("{}, in {} regions".format(said, len(group[1])))
                if stayed:                       # said, so a change that missed some regions is never a surprise
                    self.announce("{} of the {} regions could not take that and stayed as {} {}".format(
                        stayed, len(group[1]), "it" if stayed == 1 else "they", "was" if stayed == 1 else "were"))
        finally:
            self._in_player_group = False
        if reforging and kwargs.get("play", True):
            settings = players.clean_settings(self.song.track_by_id(track_id).note_regions[index].player)
            if settings and settings.get("play_after_reforge", True):
                self.play_note_region(track_id, index)
        return result
    wrapped.__name__ = method.__name__
    wrapped.__doc__ = method.__doc__
    return wrapped


class HandMadeSteps(ValueError):
    """Changing the variation would reset hand-made steps: the message says which, for the warning."""


class MusicMixin:
    # ------------------------------------------------------------------
    # the chord track
    # ------------------------------------------------------------------
    def _flats_at(self, tick):
        key = self.song.timeline.key_at_tick(tick)
        return theory.key_prefers_flats(key.tonic, key.scale)

    def describe_chord(self, index):
        change = self.song.chords[index]
        return chords.describe_change(change, self.song.timeline, self._flats_at(change.tick))

    def chord_at_playhead(self):
        """Control+Shift+H in a list, or the status: the chord playing now."""
        tick = self.position_tick()
        change = chords.chord_at(self.song.chords, tick)
        if change is None:
            return "No chord yet. The chord track is empty here, so rhythm players use the key's own chord."
        return "{}: {}".format(self.describe_position(tick), chords.name(change, self._flats_at(change.tick)))

    def set_chord(self, bar, beat, root, quality, bass=None, replacing=None):
        """Add a chord change (or replace the one at `replacing`). Returns its place in the chord track."""
        tl = self.song.timeline
        beats = tl.time_signature_at_bar(int(bar)).numerator
        if not 1.0 <= float(beat) < beats + 1.0:
            raise ValueError("Bar {} has {} beats, so the beat must be from 1 to {}".format(bar, beats, beats))
        if quality not in chords.QUALITY_KEYS:
            raise ValueError("Unknown chord type")
        tick = tl.position_to_tick(int(bar), float(beat))
        change = chords.ChordChange(tick, int(root) % 12, quality, None if bass is None else int(bass) % 12)
        with self.edit("chord change"):
            items = [c for i, c in enumerate(self.song.chords) if i != replacing]
            items = [c for c in items if c.tick != tick] + [change]
            self.song.chords = chords.sort(items)
        index = next(i for i, c in enumerate(self.song.chords) if c.tick == tick)
        self.announce(self.describe_chord(index))
        return index

    def remove_chord(self, index):
        if not 0 <= index < len(self.song.chords):
            raise ValueError("That chord change is not there any more")
        with self.edit("remove chord change"):
            del self.song.chords[index]
        self.announce("Chord change removed. {} left".format(self._count_words(len(self.song.chords), "chord change")))

    def _span_ticks(self, start_bar, end_bar):
        tl = self.song.timeline
        start_bar = max(1, int(start_bar))
        end_bar = max(start_bar + 1, int(end_bar))
        return start_bar, end_bar, tl.bar_to_tick(start_bar), tl.bar_to_tick(end_bar)

    def fill_chords(self, progression, start_bar, end_bar, bars_per_chord=1, sevenths=False):
        """Fill bars start_bar .. end_bar - 1 with a progression (an index into chords.PROGRESSIONS),
        built from the song's key in each bar. Replaces the chord changes there. Returns how many."""
        name, degrees = chords.PROGRESSIONS[int(progression)]
        start_bar, end_bar, t0, t1 = self._span_ticks(start_bar, end_bar)
        made = chords.progression_chords(self.song.timeline, start_bar, end_bar, degrees, max(1, int(bars_per_chord)),
                                         sevenths)
        self._replace_chords(t0, t1, made, "fill chords")
        self.announce("Chord track filled from bar {} to bar {} with {}: {}".format(
            start_bar, end_bar - 1, name.split(":")[0].split(" (")[0], self._chord_list_words(made)))
        return len(made)

    def chords_from_track(self, track_id, start_bar, end_bar, step="bar"):
        """Work out the chord track from what a track plays (for example, chord strips you recorded)."""
        track = self.song.track_by_id(track_id)
        if track is None or track.is_audio:
            raise ValueError("Choose an instrument track that has notes")
        start_bar, end_bar, t0, t1 = self._span_ticks(start_bar, end_bar)
        notes = self.sounding_notes(track)
        if track.instrument.is_drum_kit or not any(t0 <= n.tick < t1 for n in notes):
            raise ValueError("{} has no notes to work chords out from between bars {} and {}".format(
                track.name, start_bar, end_bar - 1))
        made = chords.chords_from_notes(notes, self.song.timeline, t0, t1, step)
        self._replace_chords(t0, t1, made, "chords from track")
        self.announce("Worked out {} from {}: {}".format(self._count_words(len(made), "chord change"), track.name,
                                                         self._chord_list_words(made)))
        return len(made)

    def clear_chords(self, start_bar, end_bar):
        start_bar, end_bar, t0, t1 = self._span_ticks(start_bar, end_bar)
        removed = sum(1 for c in self.song.chords if t0 <= c.tick < t1)
        self._replace_chords(t0, t1, [], "clear chords")
        self.announce("Removed {}".format(self._count_words(removed, "chord change")))
        return removed

    def _replace_chords(self, t0, t1, made, label):
        with self.edit(label):
            kept = [c for c in self.song.chords if not t0 <= c.tick < t1]
            self.song.chords = chords.sort(kept + list(made))

    def _chord_list_words(self, made, limit=8):
        names = [chords.short_name(c, self._flats_at(c.tick)) for c in made[:limit]]
        text = ", ".join(names)
        if len(made) > limit:
            text += ", and {} more".format(len(made) - limit)
        return text or "none"

    # ------------------------------------------------------------------
    # rhythm players
    # ------------------------------------------------------------------
    def _player_region(self, track_id, index):
        track = self.song.track_by_id(track_id)
        if track is None or track.is_audio or not 0 <= index < len(track.note_regions):
            raise ValueError("That region is not there any more")
        region = track.note_regions[index]
        if not region.player:
            raise ValueError("This is not a rhythm player region. Add one with New rhythm player (Control+Shift+R).")
        return track, region

    def is_player_region(self, track_id, index):
        track = self.song.track_by_id(track_id)
        return bool(track is not None and not track.is_audio and 0 <= index < len(track.note_regions)
                    and track.note_regions[index].player)

    def player_patch(self, player_key, style_key):
        """The patch a style starts with (an instrument the sound set lacks falls back to its bank 0 version)."""
        style = players.PLAYERS[player_key].style(style_key)
        bank, program, name = style.patch
        if player_key == "hammer":
            return style.patch      # a guitar pack not downloaded yet: the synthesizer plays a stand-in until it is
        if not self._preset_available(bank, program):
            fallback = (128, 0) if bank == 128 else (0, program)     # a kit falls back to the standard kit
            for preset in self.presets:
                if (preset.bank, preset.program) == fallback:
                    return (preset.bank, preset.program, preset.name)
        for preset in self.presets:
            if (preset.bank, preset.program) == (bank, program):
                return (bank, program, preset.name)
        return style.patch

    def _preset_available(self, bank, program):
        if not self.presets:
            return True
        return any(p.bank == bank and p.program == program and not getattr(p, "missing", False) for p in self.presets)

    def add_player_region(self, player_key, style_key=None, start_tick=None, end_tick=None, track_id=None):
        """A rhythm player region: on a new track (track_id None) or on an instrument track, from start_tick
        to end_tick (default: the section the playhead is in). Whatever was there is replaced.
        Returns (track id, region index)."""
        if self.engine.recording:
            raise ValueError("Stop recording before adding a rhythm player")
        if player_key not in players.PLAYERS:
            raise ValueError("Unknown rhythm player")
        player = players.PLAYERS[player_key]
        settings = players.new_settings(player_key, style_key)
        if start_tick is None or end_tick is None:
            index = self.current_section_index()
            start_tick, end_tick = self.section_ticks(index)
        start_tick, end_tick = int(start_tick), int(end_tick)
        if end_tick <= start_tick:
            raise ValueError("A rhythm player region needs at least one beat")
        bank, program, patch_name = self.player_patch(player_key, settings["style"])
        if track_id is not None:
            existing = self.song.track_by_id(track_id)
            if existing is None or existing.is_audio:
                raise ValueError("Rhythm players go on instrument tracks")
        with self.edit("add {}".format(player.name)):
            if track_id is None:
                position = self.song.index_of(self.selected_track_id) + 1 if self.selected_track_id else None
                track = self.song.add_track(player.title.replace(", ", " (", 1) + ")",
                                            Instrument(bank, program, patch_name), index=position)
            else:
                track = self.song.track_by_id(track_id)
            regions.clear_span(track, start_tick, end_tick)
            region = regions.claim(track, start_tick, end_tick, player=settings)
            track_id = track.id
        track = self.song.track_by_id(track_id)
        index = next(i for i, r in enumerate(track.note_regions) if r.start == region.start)
        self.selected_track_id = track_id
        self.notify("selection")
        self.announce("Added a rhythm player region on {}. {}".format(track.name, self.player_summary(track_id, index)))
        return track_id, index

    def add_player_region_here(self, track_id=None):
        """New rhythm player region (Russell, 10 Oct 2026: a new section has no region, and there was no way to give
        a rhythm player track one there): on a track that already has a rhythm player, a region at the playhead that
        fills the empty stretch of the section the playhead is in. It is the same player and style as the nearest
        player region (the one before the playhead, or else the one after), starting fresh from that style's
        defaults and its first variation, not the other region's settings (Russell: "you don't want it to use the
        previous settings of the previous region"). Returns (track id, region index)."""
        if self.engine.recording:
            raise ValueError("Stop recording before adding a region")
        track_id = self.selected_track_id if track_id is None else track_id
        track = self.song.track_by_id(track_id)
        if track is None:
            raise ValueError("There is no track selected. Press Control+T to add one.")
        players_here = [r for r in track.note_regions if r.player] if not track.is_audio else []
        if not players_here:
            raise ValueError("{} has no rhythm player yet, so New player region has nothing to play on. Press "
                             "Control+Shift+R for a new rhythm player.".format(track.name))
        tick = self.position_tick()
        song_end = self.song.song_end_tick()
        sounding = []                                    # (start, end heard, region), loops included
        for i, region in enumerate(track.note_regions):
            _count, stop = arrangement.note_region_repeats(track, i, song_end)
            sounding.append((region.start, max(region.end, stop), region))
        for i, (first, stop, region) in enumerate(sounding):
            if first <= tick < stop:
                raise ValueError("There is already a region here: {}. Move the playhead to an empty stretch, for "
                                 "example into the new section.".format(self.region_name(track_id, i)))
        section_start, section_end = self.section_ticks(self.current_section_index(tick))
        start = max([section_start] + [stop for _first, stop, _r in sounding if stop <= tick])
        end = min([section_end] + [first for first, _stop, _r in sounding if first > tick])
        before = [r for first, _stop, r in sounding if r.player and first <= tick]
        source = before[-1] if before else next(r for first, _stop, r in sounding if r.player)
        nearest = players.clean_settings(source.player)
        if nearest is None:
            raise ValueError("The rhythm player on {} could not be read".format(track.name))
        settings = players.new_settings(nearest["player"], nearest["style"])     # the style's defaults, variation 1
        player = players.PLAYERS[settings["player"]]
        with self.edit("add {} region".format(player.name)):
            region = regions.claim(self.song.track_by_id(track_id), start, end, player=copy.deepcopy(settings))
        track = self.song.track_by_id(track_id)
        index = next(i for i, r in enumerate(track.note_regions) if r.start == region.start)
        self.notify("selection")
        tl = self.song.timeline
        first_bar, last_bar = tl.tick_to_bar(start), tl.tick_to_bar(end - 1)
        where = "bar {}".format(first_bar) if first_bar == last_bar else "bars {} to {}".format(first_bar, last_bar)
        self.announce("Added a rhythm player region on {}, {}: {}, variation 1 of {}".format(
            track.name, where, players.describe_settings(settings), players.variation_count(settings)))
        return track_id, index

    def player_settings(self, track_id, index):
        _track, region = self._player_region(track_id, index)
        return players.clean_settings(region.player)

    @for_each_selected_region
    def update_player(self, track_id, index, speak=True, **changes):
        """Change a rhythm player's settings (each change is one undo step; moving one slider several
        times in a row is a single step). Returns the summary. The variation is changed with set_variation,
        and the performance only by Reforge."""
        track, region = self._player_region(track_id, index)
        settings = players.clean_settings(region.player)
        before = copy.deepcopy(settings)
        old_style = settings["style"]
        reset_note = ""
        for key, value in changes.items():
            if key == "style":
                if value not in [s.key for s in players.PLAYERS[settings["player"]].styles]:
                    raise ValueError("Unknown style")
                settings["style"] = value
                # a style with fewer variations starts again at its first
                if settings["variation"] > players.variation_count(settings):
                    settings["variation"] = 1
                    reset_note = " This style has {} variations, so it is on variation 1.".format(
                        players.variation_count(settings))
            elif key == "follow":
                if value not in FOLLOW_CHOICES:
                    raise ValueError("Unknown Follow choice")
                settings["follow"] = value
            elif key == "follow_track":
                settings["follow_track"] = None if value is None else int(value)
            elif key == "play_after_reforge":
                settings["play_after_reforge"] = bool(value)
            elif key == "swing_note":
                if value not in players.SWING_NOTES:
                    raise ValueError("Swing feel is eighth notes or sixteenth notes")
                settings["swing_note"] = value
            elif key in players.SETTING_RANGES:
                low, high = players.SETTING_RANGES[key]
                settings[key] = int(max(low, min(high, int(value))))
            else:
                raise ValueError("Unknown setting {}".format(key))
        if settings["follow"] == "track":
            problem = self._follow_problem(track, settings.get("follow_track"))
            if problem:
                raise ValueError(problem)
        patch_note = ""
        new_patch = None
        if settings["style"] != old_style:
            player_key = settings["player"]
            old_patch = self.player_patch(player_key, old_style)
            if (track.instrument.bank, track.instrument.program) == old_patch[:2]:
                new_patch = self.player_patch(player_key, settings["style"])
                if new_patch[:2] != old_patch[:2]:
                    patch_note = " Patch {}.".format(new_patch[2])
            settings["swing"] = players.PLAYERS[player_key].style(settings["style"]).swing
            if "swing_note" not in changes:          # a new style starts on its own swing feel, as its own swing
                settings["swing_note"] = players.natural_swing_note(player_key, settings["style"])
        merge = len(changes) == 1 and next(iter(changes)) in COALESCE
        what = SETTING_WORDS.get(next(iter(changes)), "settings") if len(changes) == 1 else "settings"
        label = "{} {}".format(players.PLAYERS[settings["player"]].name, what)
        if settings != before or new_patch is not None:        # nothing changed: no undo step
            with self.edit(label, merge=merge, merge_key=(track_id, region.start)):
                target = self.song.track_by_id(track_id)
                settings["rules"] = players.RULES          # changed by hand: it plays by today's rules
                target.note_regions[index].player = settings
                if new_patch is not None:
                    target.instrument = Instrument(*new_patch)
        text = self.player_summary(track_id, index) + patch_note + reset_note
        if speak:
            self.announce(text)
        return text

    def set_player_patch(self, track_id, preset):
        """The patch (instrument or kit) a rhythm player plays: the track's instrument."""
        self.set_instrument(track_id, preset)

    @for_each_selected_region
    def reforge(self, track_id, index, speak=True, play=True):
        """A new performance of the same region: the fills and the small details change, the variation (the groove
        or part itself) and every setting stay (Russell, 8 Oct 2026). Control+Z goes back to the one before.
        speak and play False: the other regions of several edited together (for_each_selected_region), which
        neither say anything nor take over the playing from the region in the editor."""
        track, region = self._player_region(track_id, index)
        settings = players.clean_settings(region.player)
        settings["performance"] = settings["performance"] % players.MAX_PERFORMANCE + 1
        with self.edit("reforge"):
            settings["rules"] = players.RULES               # changed by hand: it plays by today's rules
            self.song.track_by_id(track_id).note_regions[index].player = settings
        text = "New performance of variation {} of {}".format(settings["variation"],      # short (10 Oct 2026)
                                                              players.variation_count(settings))
        if speak:
            self.announce(text)
        if play and settings.get("play_after_reforge", True):
            self.play_note_region(track_id, index)
        return text

    def variation_warning(self, track_id, index, variation):
        """The warning to show before going to `variation`, or "" when nothing hand-made would be reset."""
        settings = self.player_settings(track_id, index)
        made = player_pieces.hand_made(settings)
        if not made or int(variation) == settings["variation"]:
            return ""
        names = [p.name if p.kind != "part" else "the part" for p in made]
        return ("Changing to variation {} resets your hand-made steps on {}. Change the variation?".format(
            int(variation), player_pieces.join_words(names)))

    @staticmethod
    def variation_words(settings):
        """'Variation 3 of 6': all that is said when the variation changes (Russell, 10 Oct 2026: it read out the
        whole summary; the Variation list and the summary box still describe it)."""
        return "Variation {} of {}".format(settings["variation"], players.variation_count(settings))

    @for_each_selected_region
    def set_variation(self, track_id, index, variation, reset_steps=False, speak=True):
        """Go to another variation of the style (its own groove or part). Hand-made steps are reset with it, so
        unless reset_steps is True (after the warning), HandMadeSteps is raised with the warning's words first.
        One undo step brings the old variation and the hand-made steps back together. speak False: say nothing
        (the Variation list, which the screen reader reads, made the change)."""
        track, region = self._player_region(track_id, index)
        settings = players.clean_settings(region.player)
        count = players.variation_count(settings)
        variation = int(variation)
        if not 1 <= variation <= count:
            raise ValueError("This style has variations 1 to {}".format(count))
        if variation == settings["variation"]:                  # already there: nothing is reset
            text = self.variation_words(settings)
            if speak:
                self.announce(text)
            return text
        warning = self.variation_warning(track_id, index, variation)
        if warning and not reset_steps:
            raise HandMadeSteps(warning)
        settings["variation"] = variation
        for stored in settings["pieces"].values():
            stored.pop("steps", None)
        settings["pieces"] = {key: value for key, value in settings["pieces"].items() if value}
        with self.edit("variation"):
            settings["rules"] = players.RULES               # changed by hand: it plays by today's rules
            self.song.track_by_id(track_id).note_regions[index].player = settings
        text = self.variation_words(settings)
        if speak:
            self.announce(text)
        return text

    def next_variation(self, track_id, index, step=1, reset_steps=False):
        """The next (or with step -1, the previous) variation; at either end it says so."""
        settings = self.player_settings(track_id, index)
        target = settings["variation"] + step
        if not 1 <= target <= players.variation_count(settings):
            text = "{} is the {} variation".format(self.variation_words(settings), "last" if step > 0 else "first")
            self.announce(text)
            return text
        return self.set_variation(track_id, index, target, reset_steps)

    def previous_variation(self, track_id, index, reset_steps=False):
        return self.next_variation(track_id, index, -1, reset_steps)

    # -- the pieces of a rhythm player (0.9.2) ------------------------------
    def kit_program(self, track_id):
        """The drum kit's program number when the track plays a drum kit (for the Forge kits' own sound names)."""
        track = self.song.track_by_id(track_id)
        return track.instrument.program if track is not None and track.instrument.bank == 128 else None

    def kit_notes(self, track_id):
        """The drum notes the track's kit has, or None when it has every one (a GeneralUser GS kit)."""
        return keyboard_map.KIT_NOTES.get(self.kit_program(track_id))

    def piece_settings(self, track_id, index, piece_key):
        return player_pieces.piece_settings(self.player_settings(track_id, index), piece_key)

    def describe_pieces(self, track_id, index):
        """The Kit pieces list (or the part's line): [(piece key, words)]."""
        settings = self.player_settings(track_id, index)
        table = None
        if settings["player"] == "anvil":
            table = player_pieces.style_table(settings["style"], settings["variation"], players._DRUM_STYLES)
        kit, notes = self.kit_program(track_id), self.kit_notes(track_id)
        found = []
        for piece in player_pieces.pieces_for(settings["player"]):
            groove = True if table is None else bool(player_pieces.piece_rows(table, piece))
            found.append((piece.key, player_pieces.describe_piece(settings, piece.key, groove, kit, notes)))
        return found

    def describe_piece(self, track_id, index, piece_key):
        return dict(self.describe_pieces(track_id, index))[piece_key]

    @for_each_selected_region
    def update_piece(self, track_id, index, piece_key, speak=True, **changes):
        """Change one piece's settings (one undo step; moving one slider several times in a row is one step).
        Returns the piece's line, which is also said."""
        track, region = self._player_region(track_id, index)
        settings = players.clean_settings(region.player)
        piece = player_pieces.PIECE_BY_KEY.get(piece_key)
        if piece is None or piece not in player_pieces.pieces_for(settings["player"]):
            raise ValueError("{} has no such piece".format(players.PLAYERS[settings["player"]].name))
        before = dict(settings["pieces"].get(piece_key, {}))
        stored = dict(before)
        defaults = player_pieces.defaults_for(piece)
        for key, value in changes.items():
            value = player_pieces.clean_value(piece, key, value, settings["player"])
            if value == defaults.get(key):
                stored.pop(key, None)
            else:
                stored[key] = value
        if stored:
            settings["pieces"][piece_key] = stored
        else:
            settings["pieces"].pop(piece_key, None)
        merge = len(changes) == 1 and next(iter(changes)) in PIECE_COALESCE
        label = "{} {}".format(piece.name if piece.kind != "part" else "part", next(iter(changes)) if len(changes) == 1
                               else "settings")
        if stored != before:                                    # nothing changed: no undo step
            # The change is made inside edit(), which then hands the new notes to the sound engine. (From 10 Oct
            # 2026, 3:50 PM until the final review that evening it was made just after, so a piece's change, the
            # kick turned off say, was not heard until some other change came along.)
            with self.edit(label, merge=merge, merge_key=(track_id, region.start, piece_key)):
                settings["rules"] = players.RULES               # changed by hand: it plays by today's rules
                self.song.track_by_id(track_id).note_regions[index].player = settings
        text = self.describe_piece(track_id, index, piece_key)
        if speak:
            self.announce(text)
        return text

    def toggle_piece(self, track_id, index, piece_key):
        """Space in the Kit pieces list: a piece on or off."""
        on = self.piece_settings(track_id, index, piece_key)["on"]
        return self.update_piece(track_id, index, piece_key, on=not on)

    def piece_steps(self, track_id, index, piece_key, bars=None):
        """A piece's steps for the Step pattern view: {"bars": [[[step, velocity, sound], ...], ...]}. Hand-made
        steps when there are some; otherwise exactly what the piece plays in the region's first bars now, without
        fills, swing or passing notes (players.perform with for_steps; the same random choices as what is heard), so
        changing one step changes only that step: a drum step lists every sound on it, and a part's steps start as
        "as the style plays it". A piece that is off shows what it plays when it is on. bars: how many bars (1 to 4)
        when starting afresh."""
        track, region = self._player_region(track_id, index)
        settings = players.clean_settings(region.player)
        own = player_pieces.piece_settings(settings, piece_key)["steps"]
        if own and bars is None:
            return own
        bars = max(1, min(player_pieces.MAX_STEP_BARS, int(bars or 1)))
        viewed = copy.deepcopy(settings)
        mine = viewed["pieces"].setdefault(piece_key, {})
        mine.pop("steps", None)
        mine.pop("on", None)
        tl = self.song.timeline
        result = players.perform(viewed, region.start, region.end, tl, self.song.chords,
                                 self._follow_hits(track, region, settings), self._section_starts(region),
                                 for_steps=True)
        piece = player_pieces.PIECE_BY_KEY[piece_key]
        out = []
        for bar in players._bars(tl, region.start, region.end)[:bars]:
            found = {}
            for note in result.notes:
                if not bar.start <= note.tick < bar.end:
                    continue
                step = int(round((note.tick - bar.start) / float(players.STEP)))
                if not 0 <= step < bar.steps:
                    continue
                if piece.kind == "part":
                    key, sound = step, "style"
                elif note.pitch in piece.voices and note.velocity > 1 and (note.tick - bar.start) % players.STEP == 0:
                    key, sound = (step, note.pitch), note.pitch         # (a roll's notes between the steps stay a roll)
                else:
                    continue
                if key not in found or note.velocity > found[key][1]:
                    found[key] = [step, note.velocity, sound]
            out.append([found[k] for k in sorted(found)])
        while len(out) < bars:
            out.append([])
        return {"bars": out}

    def set_piece_steps(self, track_id, index, piece_key, steps, speak=True):
        """Hand-made steps for one piece (one undo step); they stay through Reforge. Every step off is a hand-made
        silence: the piece then plays nothing but its fills."""
        return self.update_piece(track_id, index, piece_key, speak=speak, steps=steps)

    def clear_piece_steps(self, track_id, index, piece_key):
        """Back to the pattern: the hand-made steps go (Control+Z brings them back)."""
        return self.update_piece(track_id, index, piece_key, steps=None)

    def play_note_region(self, track_id, index):
        """Play one region through once from its start (after a Reforge, so it can be judged at once)."""
        if self.engine.recording:
            return
        start, end = self.region_span(track_id, index)
        if self.engine.playing:
            self.stop(speak=False)
        self._playhead = start
        self._play_start = start
        self.new_write_pass()
        self.engine.locate(start)
        self.engine.set_region(None, end, None)
        self.engine.play(start)
        self.notify("transport")

    def turn_into_notes(self, track_id, index):
        """Make a rhythm player region's performance into ordinary notes you can edit."""
        track, region = self._player_region(track_id, index)
        notes = list(self.performance(track, region).notes)
        with self.edit("turn into notes"):
            target = self.song.track_by_id(track_id)
            spot = target.note_regions[index]
            target.notes.extend(copy.deepcopy(notes))
            target.sort_notes()
            spot.player = None
        self.announce("Turned into {}. The region is now ordinary notes; Enter lists them.".format(
            self._count_words(len(notes), "note")))
        return len(notes)

    def player_summary(self, track_id, index):
        """'Anvil, dubstep, 8 bars, 31 notes. Fills in bars 4 and 8.' and what Follow did."""
        track, region = self._player_region(track_id, index)
        settings = players.clean_settings(region.player)
        result = self.performance(track, region)
        tl = self.song.timeline
        bars = tl.tick_to_bar(region.end - 1) - tl.tick_to_bar(region.start) + 1
        return players.summary(settings, result, bars, self._follow_words(track, region, settings, result))

    def _follow_words(self, track, region, settings, result):
        player = players.PLAYERS[settings["player"]]
        if settings["follow"] == "none":
            return ""
        own = player_pieces.piece_settings(settings, "kick" if player.key == "anvil" else "part")
        if player.key == "anvil" and not own["on"]:
            return "The kick is off, so Follow has nothing to move."
        if player.key != "anvil" and own["steps"] and settings["follow"] == "track":
            return "The part is hand-made, so Follow does not move its steps."
        if settings["follow"] == "chords":
            if player.key == "anvil":
                return "Kicks land on the chord changes."
            if not own["chords"]:
                return "It plays the key's own chord: the part does not follow the chord track."
            return "Plays the chord track." if self.song.chords else ("The chord track is empty, so it plays the "
                                                                       "key's own chord.")
        followed = self.song.track_by_id(settings.get("follow_track"))
        if followed is None:
            return "The followed track is gone, so it follows the chord track."
        name = self._track_label(followed)
        if result.hits == 0:
            return "{} follows {}, but it has no hits here, so it plays its own style.".format(player.name, name)
        what = "Kicks land on" if player.key == "anvil" else "It plays along with"
        if followed.is_audio:
            text = "{} follows {}. {} hit{} found. {} {} of them.".format(
                player.name, name, result.hits, "" if result.hits == 1 else "s", what, result.matched)
            tl = self.song.timeline
            bars = tl.tick_to_bar(region.end - 1) - tl.tick_to_bar(region.start) + 1
            if result.hits < bars:
                text += " Few clear hits found; try raising the sensitivity, or follow the chord track."
            return text
        return "{} follows {}. {} {} of its {} accents.".format(player.name, name, what, result.matched,
                                                              result.accents)

    def _track_label(self, track):
        number = self.song.index_of(track.id) + 1
        if track.is_audio:
            return "Track {}, recorded audio".format(number)
        return "Track {}, {}".format(number, track.instrument.name)

    def follow_candidates(self, track_id, index):
        """Tracks a rhythm player region can follow: [(track id, label)] of tracks with notes or a recording
        in the region's span (never the player's own track)."""
        track, region = self._player_region(track_id, index)
        found = []
        for other in self.song.tracks:
            if other.id == track.id:
                continue
            if other.is_audio:
                busy = any(r.tick < region.end and r.end_tick(self.song.timeline) > region.start for r in other.regions)
            else:
                busy = any(region.start <= n.tick < region.end for n in other.notes) or any(
                    r.player and r.start < region.end and r.end > region.start for r in other.note_regions)
            if busy:
                found.append((other.id, self._track_label(other)))
        return found

    def _follow_problem(self, track, follow_id):
        """Why a track cannot be followed, or '' if it can."""
        if follow_id is None:
            return "Choose the track to follow"
        if follow_id == track.id:
            return "A rhythm player cannot follow its own track"
        other = self.song.track_by_id(follow_id)
        if other is None:
            return "That track is not there any more"
        for region in other.note_regions:
            settings = players.clean_settings(region.player) if region.player else None
            if settings and settings["follow"] == "track" and settings.get("follow_track") == track.id:
                return ("{} already follows this track, and two players cannot follow each other. Change that "
                        "one first.".format(other.name))
        return ""

    # -- performances (cached) ----------------------------------------------
    def _section_starts(self, region):
        """Where the song's sections start inside a region (a crash can come at each)."""
        tl = self.song.timeline
        starts = [tl.bar_to_tick(self.song.section_bounds(i)[0]) for i in range(len(self.song.sections))]
        return [tick for tick in starts if region.start <= tick < region.end]

    @staticmethod
    def _next_intensity(track, region):
        """The Intensity of the drummer region that starts where this one ends on the same track (None: none
        there, or it is muted, or not a drummer). A louder one gets a hi-hat build in this region's last bars."""
        for other in track.note_regions:
            if other is region or other.start != region.end or other.mute or not other.player:
                continue
            found = players.clean_settings(other.player)
            if found and found["player"] == "anvil":
                return found["intensity"]
        return None

    def performance(self, track, region):
        """A rhythm player region's notes (worked out once for each set of inputs)."""
        settings = players.clean_settings(region.player)
        span_chords = [c.to_list() for c in self.song.chords if c.tick < region.end]
        hits = self._follow_hits(track, region, settings)
        sections = self._section_starts(region)
        coming = self._next_intensity(track, region) if settings["player"] == "anvil" else None
        key = json.dumps([settings, region.start, region.end, span_chords, self._timeline_key(), sections, coming,
                          None if hits is None else [(h.tick, round(h.weight, 3)) for h in hits]], sort_keys=True,
                         default=str)
        cache = self.__dict__.setdefault("_performances", {})
        found = cache.get(key)
        if found is None:
            if hits is None and settings["follow"] == "track":
                settings = dict(settings, follow="chords")     # the followed track is gone: follow the chords
            found = players.perform(settings, region.start, region.end, self.song.timeline, self.song.chords, hits,
                                    sections, next_intensity=coming)
            if len(cache) > 256:
                cache.clear()
            cache[key] = found
        return found

    def _timeline_key(self):
        tl = self.song.timeline
        return json.dumps(tl.to_dict(), sort_keys=True)

    def _follow_hits(self, track, region, settings):
        """The followed track's hits in the region (None when not following a track)."""
        if settings["follow"] != "track":
            return None
        other = self.song.track_by_id(settings.get("follow_track"))
        if other is None or other.id == track.id:
            return None
        tl = self.song.timeline
        if other.is_audio:
            hits = []
            for recording in other.regions:
                if recording.mute or recording.take is None:
                    continue
                for hit in self._recording_hits(recording, settings["sensitivity"]):
                    seconds = tl.tick_to_seconds(recording.tick) + hit.sample / float(AUDIO_RATE)
                    tick = int(round(tl.seconds_to_tick(seconds)))
                    if region.start <= tick < region.end:
                        hits.append(players.Hit(tick, 0.5 * hit.loudness + 0.3 * hit.low + 0.2, hit.low))
            hits.sort(key=lambda h: h.tick)
            return hits
        notes = self.sounding_notes(other, avoid=track.id)
        return players.hits_from_notes(notes, region.start, region.end, tl)

    def _recording_hits(self, recording, sensitivity):
        """Hits found in a recording (the take that plays), cached by file and sensitivity."""
        path = os.path.normcase(self.audio_path(recording.take.file))
        key = (path, recording.offset, recording.length, int(sensitivity))
        cache = self.__dict__.setdefault("_onsets", {})
        found = cache.get(key)
        if found is None:
            data = self.load_audio(recording.take.file)
            if data is None:
                return []
            data = data[recording.offset:]
            if recording.length:
                data = data[:recording.length]
            try:
                found = onsets.find_hits(data, AUDIO_RATE, sensitivity)
            except Exception:  # noqa: BLE001 - a recording that cannot be read for hits is simply not followed
                log.exception("Finding hits failed in %s", recording.take.file)
                found = []
            if len(cache) > 128:
                cache.clear()
            cache[key] = found
        return found

    def sounding_notes(self, track, avoid=None):
        """What an instrument track really plays (loops repeated, rhythm players performed).
        avoid: a track id whose players must not be followed back (stops a loop of followers)."""
        def perform_for(t, region):
            settings = players.clean_settings(region.player)
            if settings and settings["follow"] == "track" and settings.get("follow_track") == avoid:
                settings = dict(settings, follow="chords")
                return players.perform(settings, region.start, region.end, self.song.timeline, self.song.chords,
                                       None, self._section_starts(region),
                                       next_intensity=self._next_intensity(t, region)).notes
            return self.performance(t, region).notes

        return arrangement.sounding_notes(self.song, track, perform_for)

    def all_sounding_notes(self):
        """{track id: notes} for every instrument track of the song (for playback and export)."""
        return {t.id: self.sounding_notes(t) for t in self.song.tracks if not t.is_audio}

    # ------------------------------------------------------------------
    # trimming and looping regions (every kind)
    # ------------------------------------------------------------------
    def region_loops(self, track_id, index):
        return self.regions_of(track_id)[index].loops

    def set_region_loops(self, track_id, index, loops):
        """How many times a region plays in a row (1 = once); 0 loops it until the next region."""
        loops = int(loops)
        if not 0 <= loops <= 999:
            raise ValueError("A region can play from 1 to 999 times (0 loops it until the next region)")
        self._need_regions(track_id, [index])
        with self.edit("loop region"):
            self.regions_of(track_id)[index].loops = loops
        self.announce(self.describe_region_item(track_id, index, number=False))

    def trim_region(self, track_id, index, start_tick, end_tick, speak=True, merge_key=None):
        """Change where a region starts and ends; its music stays where it is in the song.

        On an instrument track, notes outside the new span are removed (Control+Z brings them back); a
        rhythm player fills whatever length it has. A recording is trimmed: its start moves into the
        recording (or back out, up to where it really begins), and its end shortens or lengthens it.
        merge_key: presses of one nudge key in a row (session_nudge.py) are one undo step."""
        track = self._need_regions(track_id, [index])
        start_tick, end_tick = int(start_tick), int(end_tick)
        if end_tick <= start_tick:
            raise ValueError("A region must end after it starts")
        if start_tick < 0:
            raise ValueError("A region cannot start before the beginning of the song")
        tl = self.song.timeline
        if track.is_audio:
            region = track.regions[index]
            start_frame = int(round((tl.tick_to_seconds(start_tick) - tl.tick_to_seconds(region.tick)) * AUDIO_RATE))
            new_offset = region.offset + start_frame
            if new_offset < 0:
                raise ValueError("The recording begins at {}; a region cannot start before its recording".format(
                    self.describe_position(int(round(tl.seconds_to_tick(
                        tl.tick_to_seconds(region.tick) - region.offset / float(AUDIO_RATE)))))))
            frames = int(round((tl.tick_to_seconds(end_tick) - tl.tick_to_seconds(start_tick)) * AUDIO_RATE))
            available = region.take.frames - new_offset
            if available <= 0:
                raise ValueError("That would trim away the whole recording")
            with self.edit("trim recording", merge=merge_key is not None, merge_key=merge_key):
                target = self.song.track_by_id(track_id).regions[index]
                target.offset = new_offset
                target.length = 0 if frames >= available else max(1, frames)
                target.tick = start_tick
                self.song.track_by_id(track_id).sort_regions()
                new_index = next(i for i, r in enumerate(self.song.track_by_id(track_id).regions) if r is target)
        else:
            others = [r for i, r in enumerate(track.note_regions) if i != index]
            if any(r.start < end_tick and r.end > start_tick for r in others):
                raise ValueError("That would overlap the next or previous region. Shorten that one first, or move "
                                 "this one.")
            with self.edit("trim region", merge=merge_key is not None, merge_key=merge_key):
                target_track = self.song.track_by_id(track_id)
                region = target_track.note_regions[index]
                old_start, old_end = region.start, region.end
                if not region.player:
                    target_track.notes = [n for n in target_track.notes
                                          if not (old_start <= n.tick < old_end and not start_tick <= n.tick < end_tick)]
                region.start, region.end = start_tick, end_tick
                target_track.note_regions.sort(key=lambda r: r.start)
                new_index = next(i for i, r in enumerate(target_track.note_regions) if r is region)
        if speak:
            self.announce("Trimmed. {}".format(self.describe_region_item(track_id, new_index, number=False)))
        return new_index
