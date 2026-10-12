"""Everything Musician Forge does, without any windows.

The Session holds the open song, the undo history, the sound engine and the
musical typing state. The user interface only calls Session methods and
shows or speaks what they report, which keeps the program's behavior fully
testable without a screen.
"""

import copy
import json
import logging
import os
import shutil
import tempfile
import time
from collections import namedtuple
from contextlib import contextmanager

import numpy as np

from . import (arpeggiator, arrange, audioimport, audiotracks, effects, latency, m4a, meterchange, midifile, packs,
               pitchfix,
               projects, regions, theory, wavfile)
from . import chords as chords_module
from . import keyboard_map as km
from .engine import PlaybackData, render_offline
from .quantize import quantize_notes
from .session_automation import AutomationMixin
from .session_music import MusicMixin
from .session_nudge import NudgeMixin
from .song import (AUDIO_RATE, AUDIO_TRACK, FILE_EXTENSION, MAX_TRACKS, AudioRegion, AudioTake, Instrument, Note,
                   Song, SongFileError, UndoHistory, new_song)
from .timeline import PPQ, format_number
from .paths import replace_file
from .wavfile import WavWriter, wav_size_bytes

log = logging.getLogger("musicianforge.session")

MAX_TAIL_SECONDS = 10.0   # an export's ring-out stops at silence, or after this long
PREVIEW_CHANNEL = 127
PREVIEW_PITCH = 60


# An audio file read and copied, ready to go on a track (Session.prepare_import): the original's path, Musician
# Forge's copy, its sound at 48 kHz (float32, (frames, channels)), the original's sample rate and channels, and the
# decoder that read it.
PreparedImport = namedtuple("PreparedImport", "path file audio rate channels decoder")


class Session(MusicMixin, AutomationMixin, NudgeMixin):
    def __init__(self, engine, settings, synth_factory=None, speaker=None, presets=None,
                 autosave_dir=None, recordings_dir=None):
        self.engine = engine
        self.settings = settings
        self.synth_factory = synth_factory
        self.speaker = speaker
        self.presets = presets or []
        self.autosave_dir = autosave_dir
        self._recordings_dir = recordings_dir  # recordings of projects not saved yet (see recordings_dir)
        self.audio_input = None      # the microphone (audio.AudioInput), set by the program at start
        # Low-latency hearing yourself (0.9.1): lowlatency.LowLatencyMonitor on Windows 10 and later, set by the
        # program; it is used when Audio settings turn it on (see _start_monitoring)
        self.low_latency_factory = None
        self._low_latency = None     # the running low-latency monitor, while recording
        self._low_latency_said = False
        self._audio_cache = {}       # recording's full path -> its audio
        self._missing_audio = set()
        self._scratch = set()        # recordings made before the project was ever saved
        self._gathered = {}          # recording -> its copy in a project's audio folder
        self._chunks_at_start = 0
        self._corrected = {}         # pitch-corrected recordings: (file, settings, keys) -> audio
        self._effect_preview = {}    # track id -> effects being tried out in the effect settings window
        self._measure_done = None    # called with the result of Measure the recording delay
        self.last_measurement = None
        self.history = UndoHistory()
        self.typing = km.MusicalTyping()
        self.typing.custom_strips = lambda: self.song.strips if getattr(self, "song", None) is not None else None
        self.arp = {"on": False, "pattern": arpeggiator.DEFAULT_PATTERN, "rate": arpeggiator.DEFAULT_RATE,
                    "octaves": 1}
        if settings is not None:
            if settings["keyboard_layout"] in km.MODES:
                self.typing.mode = settings["keyboard_layout"]
            if settings["keyboard_scale"] in theory.SCALE_NAMES:
                self.typing.scale = settings["keyboard_scale"]
            self.arp.update({k: v for k, v in settings["arpeggiator"].items() if k in self.arp})
        self.listeners = []
        self._merge_label = None     # the last edit that can absorb the next one (moving a slider)
        self.automation_write = False  # Write automation: moving a setting while playing writes it
        self._write_pass = {}          # (track, lane) -> the last tick written in this play-through
        self.last_announcement = ""
        self.song = None
        self.path = None
        self._saved_content = None     # the song as its file has it (or as it was made), to find changes by
        self._autosaved_content = None  # the song as the crash-recovery copy has it
        self.modified = False
        self.selected_track_id = None
        self._playhead = 0
        self._play_start = 0
        self._held = {}
        self._take = None
        self._stale_take = False       # a take the engine still hands back belongs to a project now closed
        self.selecting = False         # selection mode (Shift+F8): Space picks tracks and regions
        self.selected_tracks = set()   # track ids
        self.selected_regions = set()  # indices into the current track's regions
        self.player_group = None       # (track id, {region starts}) the rhythm player editor changes together
        self.clipboard = None          # copied tracks or regions
        self.all_sections = bool(self._pref("play_all_sections")) if settings is not None else False
        self.audio_is_live = False  # set by the window once the sound card is running
        self._apply_engine_settings()
        self.new_song()

    @property
    def modified(self):
        """True when the project has changes its file does not have yet (or, before it is first saved, any change).

        Every change made through edit() sets this. As a safety net, the song is also compared with what was last
        saved or opened, so a change that somehow did not go through edit() still counts: Close project, New, Open
        and Exit then always offer to save it (Russell, 9 Oct 2026: changes were missing after closing)."""
        if self._modified:
            return True
        return (self.song is not None and self._saved_content is not None
                and self.song.to_dict() != self._saved_content)

    @modified.setter
    def modified(self, value):
        self._modified = bool(value)
        if not value:
            self._saved_content = self.song.to_dict() if self.song is not None else None

    @property
    def selected_track_id(self):
        return self._selected_track_id

    @selected_track_id.setter
    def selected_track_id(self, track_id):
        if track_id != getattr(self, "_selected_track_id", None) and hasattr(self, "selected_regions"):
            self.selected_regions.clear()  # region choices belong to one track
        self._selected_track_id = track_id

    # ------------------------------------------------------------------
    # notifications and speech
    # ------------------------------------------------------------------
    def notify(self, what):
        for listener in list(self.listeners):
            try:
                listener(what)
            except Exception:  # noqa: BLE001
                log.exception("A listener failed for %s", what)

    def announce(self, text, interrupt=True):
        self.last_announcement = text
        log.debug("Announce: %s", text)
        if self.speaker is not None:
            self.speaker.speak(text, interrupt)
        self.notify("announcement")

    # ------------------------------------------------------------------
    # song files
    # ------------------------------------------------------------------
    def new_song(self):
        defaults = self.settings["new_song"] if self.settings is not None else {}
        self._stop_engine_quietly()
        self.song = new_song(bpm=defaults.get("bpm", 120.0), numerator=defaults.get("numerator", 4),
                             denominator=defaults.get("denominator", 4), tonic=defaults.get("tonic", 0),
                             scale=defaults.get("scale", "Major"))
        self._after_load(None)

    def new_song_with(self, title="Untitled", bpm=120.0, numerator=4, denominator=4, tonic=0, scale="Major"):
        """New song from the New Song dialog's choices."""
        self._stop_engine_quietly()
        self.song = new_song(title=title, bpm=bpm, numerator=numerator, denominator=denominator,
                             tonic=tonic, scale=scale)
        self._after_load(None)

    def open(self, path, backup=False):
        """Open a project. backup: open path's backup (the save before the last one) because path itself is
        damaged; the project keeps its own name and place (Recent projects lists it, not the backup), and
        counts as changed, so saving puts the project right."""
        source = path + ".bak" if backup else path
        song = Song.load(source)  # raises SongFileError with a clear message
        self._absolute_audio(song, os.path.dirname(os.path.abspath(path)))
        self._stop_engine_quietly()
        self.song = song
        self._after_load(path)
        self.modified = bool(backup)
        if self.settings is not None:
            self.settings.add_recent(path)
            self.settings.save()
        log.info("Opened song: %s", source)
        missing = self.missing_recordings()
        text = "Opened {}{}, {} tracks".format("the backup of " if backup else "", self.song.title,
                                              len(self.song.tracks))
        if self._playhead:                # back where it was saved: say where
            text += ". {}, {}".format(self.song.section_name(self.current_section_index()), self.describe_position())
        if missing:
            text += ". {} recording{} could not be found".format(missing, "" if missing == 1 else "s")
            log.warning("%d recordings are missing in %s", missing, path)
        self.announce(text)

    def _after_load(self, path):
        self.path = path
        self._autosaved_content = None
        self.history.clear()
        self.selected_tracks.clear()
        self.selected_regions.clear()
        self._discard_scratch()  # the previous project's never-saved recordings
        self._missing_audio.clear()
        keep = {os.path.normcase(self.audio_path(t.file)) for t in self._takes()}
        self._audio_cache = {p: d for p, d in self._audio_cache.items() if os.path.normcase(p) in keep}
        self.selected_track_id = self.song.tracks[0].id if self.song.tracks else None
        self._playhead = 0
        place = self.song.place      # where you were when it was saved (Russell, 10 Oct 2026)
        if place:
            if self.song.track_by_id(place.get("track")) is not None:
                self.selected_track_id = place["track"]
            self._playhead = max(0, min(int(place["playhead"]), self.song.song_end_tick() - 1))
        self._sync_engine()
        self.engine.locate(self._playhead)
        self.modified = False   # last, so anything tidied while loading is not counted as a change
        self.notify("song")

    def save(self, path=None):
        path = path or self.path
        if not path:
            raise ValueError("No file name yet; use Save As")
        if not path.lower().endswith(FILE_EXTENSION):
            path += FILE_EXTENSION
        if not self.song.title or self.song.title == "Untitled":
            self.song.title = os.path.splitext(os.path.basename(path))[0]
        self._gather_audio(path)
        written = self._song_for_file(path)
        written.place = {"playhead": int(self.position_tick()), "track": self.selected_track_id}
        written.save(path)
        self._check_saved(path, written)
        self.path = path
        self.modified = False
        self.mark_clean_exit()   # the file is now newer than the crash-recovery copy, which must not be offered
        if self.settings is not None:
            self.settings.add_recent(path)
            self.settings.save()
        log.info("Saved song: %s", path)
        self.notify("title")
        self.announce("Saved {} in {}".format(projects.project_name(path), projects.location_name(path)))
        return path

    @staticmethod
    def _check_saved(path, written):
        """Read a project straight back after saving it: what is in the file must be exactly what was meant to be
        saved, or Save says so instead of seeming to have worked."""
        meant = json.loads(json.dumps(written.to_dict()))   # as JSON has it (lists, not tuples)
        try:
            with open(path, encoding="utf-8") as fh:
                matches = json.load(fh) == meant
            Song.load(path)                                   # and it opens
        except (OSError, ValueError, SongFileError):
            matches = False
        if not matches:
            log.error("A saved project did not read back the same: %s", path)
            raise SongFileError("{} was saved, but reading it back did not give the same project. Try Save project "
                                "as, in another folder.".format(os.path.basename(path)))

    def title_text(self):
        """The window's title: the project's name. It no longer says "(unsaved changes)": screen readers read the
        title every time a window closes, and the changes are kept for crash recovery all the time anyway
        (Russell, 9 Oct 2026). Without ".mforge" (10 Oct 2026). (For a while that night it was only "Musician Forge";
        Russell asked for the project's name back.)"""
        return "{} - Musician Forge".format(self.project_name())

    def project_name(self):
        """The project's name: its file's name without .mforge, or the song's title before it is saved."""
        return os.path.splitext(os.path.basename(self.path))[0] if self.path else self.song.title

    # -- autosave and recovery --------------------------------------------
    def _autosave_paths(self):
        folder = self.autosave_dir
        return (os.path.join(folder, "autosave" + FILE_EXTENSION), os.path.join(folder, "session.json"))

    def autosave(self):
        """Keep the crash-recovery copy up to date (in Musician Forge's own folder, never the project's). Writes
        only when the song has changes its file does not have and the copy does not have them yet. True if it
        wrote."""
        if not self.autosave_dir or not self.modified:
            return False
        content = self.song.to_dict()
        if content == self._autosaved_content:
            return False
        song_path, info_path = self._autosave_paths()
        os.makedirs(self.autosave_dir, exist_ok=True)
        recovery = Song.from_dict(copy.deepcopy(content))
        recovery.place = {"playhead": int(self.position_tick()), "track": self.selected_track_id}   # where you were
        for track in recovery.tracks:  # the copy lives elsewhere, so recordings are found by full path
            for region in track.regions:
                for take in region.takes:
                    take.file = self.audio_path(take.file)
        recovery.save(song_path)
        with open(info_path, "w", encoding="utf-8") as fh:
            json.dump({"clean_exit": False, "song_path": self.path, "saved_at": time.time()}, fh)
        self._autosaved_content = content
        return True

    def mark_clean_exit(self):
        if not self.autosave_dir:
            return
        _song_path, info_path = self._autosave_paths()
        self._autosaved_content = None
        if os.path.exists(info_path):
            with open(info_path, "w", encoding="utf-8") as fh:
                json.dump({"clean_exit": True}, fh)

    def recovery_available(self):
        """Path of an autosaved song from a session that did not close properly, or None."""
        if not self.autosave_dir:
            return None
        song_path, info_path = self._autosave_paths()
        try:
            with open(info_path, encoding="utf-8") as fh:
                info = json.load(fh)
        except (OSError, ValueError):
            return None
        if not isinstance(info, dict) or info.get("clean_exit", True) or not os.path.exists(song_path):
            return None
        return song_path

    def recover(self):
        song_path = self.recovery_available()
        if not song_path:
            return False
        _p, info_path = self._autosave_paths()
        with open(info_path, encoding="utf-8") as fh:
            original = json.load(fh).get("song_path")
        if not isinstance(original, str):
            original = None
        self.song = Song.load(song_path)
        self._after_load(original)
        scratch = os.path.normcase(os.path.abspath(self.recordings_dir))
        self._scratch |= {self.audio_path(t.file) for t in self._takes()
                          if os.path.normcase(os.path.dirname(self.audio_path(t.file))) == scratch}
        self.modified = True
        log.info("Recovered the autosaved project (it was %s)", original or "never saved")
        self.notify("title")
        self.announce("Recovered your unsaved project")
        return True

    # ------------------------------------------------------------------
    # editing with undo
    # ------------------------------------------------------------------
    @contextmanager
    def edit(self, label, record_undo=True, merge=False, merge_key=None):
        """Wrap every change: undo snapshot, safe rollback on errors, engine refresh.

        merge: this change may join the previous one if that had the same label and could be
        merged too (moving one slider several times in a row is one undo step). merge_key: what else
        must be the same (for example the region), so the same slider in two regions is two steps."""
        if getattr(self, "_group_depth", 0):
            # inside edit_group: the group's own edit keeps the undo step and puts things back if anything fails
            yield self.song
            self.song.fit_last_section()
            self.song.tidy_regions()
            self.modified = True
            return
        snapshot = self.song.to_dict()
        try:
            yield self.song
            self.song.fit_last_section()
            self.song.tidy_regions()
        except Exception:
            self.song = Song.from_dict(snapshot)
            self._sync_engine()
            raise
        joined = merge and self._merge_label == (label, merge_key) and self.history.undo_label() == label
        if record_undo and not joined:
            self.history.push(label, snapshot)
        self._merge_label = (label, merge_key) if merge else None
        self.modified = True
        self._sync_engine()
        self.notify("song")

    @contextmanager
    def edit_group(self, label, merge=False, merge_key=None):
        """Several changes as one undo step (the same change to several selected regions, say)."""
        with self.edit(label, merge=merge, merge_key=merge_key):
            self._group_depth = getattr(self, "_group_depth", 0) + 1
            try:
                yield self.song
            finally:
                self._group_depth -= 1

    def undo(self):
        self._merge_label = None
        result = self.history.undo(self.song)
        if result is None:
            self.announce("Nothing to undo")
            return
        label, song = result
        self._replace_song(song)
        self._close_take_undo()
        self.announce("Undo {}".format(label))

    def redo(self):
        self._merge_label = None
        result = self.history.redo(self.song)
        if result is None:
            self.announce("Nothing to redo")
            return
        label, song = result
        self._replace_song(song)
        self._close_take_undo()
        self.announce("Redo {}".format(label))

    def _close_take_undo(self):
        """Undo or redo while a looping take is still being recorded: the passes still to come make an undo step
        of their own, instead of joining one that is no longer at the top (then Control+Z would take back the
        change made before the take as well)."""
        if self._take is not None:
            self._take["undo_open"] = False
            self._take["count"] = 0      # notes said as recorded are only the ones still in the song

    def _replace_song(self, song):
        selected = self.selected_track_id
        self.song = song
        self.selected_regions.clear()
        self.selected_tracks = {t for t in self.selected_tracks if song.track_by_id(t) is not None}
        if self.song.track_by_id(selected) is None:
            self.selected_track_id = self.song.tracks[0].id if self.song.tracks else None
        self.modified = True
        self._sync_engine()
        self.notify("song")

    def _sync_engine(self):
        self.engine.set_data(PlaybackData(self.song, self.engine.sample_rate, self.load_audio,
                                          take_loader=self._take_audio, effects_override=self._effect_preview,
                                          notes_by_track=self.all_sounding_notes()))
        self._refresh_region()

    def _apply_engine_settings(self):
        self.engine.set_arpeggiator(self._arp_settings())
        if self.settings is None:
            return
        s = self.settings
        self.engine.metronome_on = bool(s["metronome_on"])
        self.engine.metronome_volume = s["metronome_volume"] / 100.0
        self.engine.count_in_bars = int(s["count_in_bars"])
        self.engine.record_offset_seconds = s["record_offset_ms"] / 1000.0
        self.engine.audio_offset_seconds = s["microphone_offset_ms"] / 1000.0
        self.engine.master_gain = s["master_volume"] / 100.0

    def _arp_settings(self):
        if not self.arp["on"]:
            return None
        return arpeggiator.make_settings(self.arp["pattern"], self.arp["rate"], self.arp["octaves"])

    def _save_setting(self, key, value):
        if self.settings is not None:
            self.settings[key] = value
            self.settings.save()

    # ------------------------------------------------------------------
    # tracks
    # ------------------------------------------------------------------
    @property
    def selected_track(self):
        return self.song.track_by_id(self.selected_track_id)

    def channel_of(self, track_id):
        index = self.song.index_of(track_id)
        return index if index >= 0 else 0

    def select_track(self, track_id, speak=False):
        if self.song.track_by_id(track_id) is None:
            return
        self._release_held_keys()
        self.selected_track_id = track_id
        if speak:
            self.announce(self.describe_track(track_id))
        self.notify("selection")

    def describe_track(self, track_id):
        index = self.song.index_of(track_id)
        return self.song.tracks[index].describe(index + 1)

    def add_track(self, name=None, instrument=None):
        if instrument is None and self.presets:
            first = self.presets[0]
            instrument = Instrument(first.bank, first.program, first.name)
        with self.edit("add track"):
            index = self.song.index_of(self.selected_track_id) + 1 if self.selected_track_id else None
            track = self.song.add_track(name, instrument, index=index)
        self.selected_track_id = track.id
        self.notify("selection")
        self.announce("Added {}".format(self.describe_track(track.id)))
        return track

    def delete_track(self, track_id):
        track = self.song.track_by_id(track_id)
        if track is None:
            return
        if self.engine.recording:
            self.announce("Stop recording before deleting a track")
            return
        index = self.song.index_of(track_id)
        with self.edit("delete track {}".format(track.name)):
            self.song.remove_track(track_id)
        self.selected_tracks.discard(track_id)      # a new track could get its number and look selected
        if self.song.tracks:
            self.selected_track_id = self.song.tracks[min(index, len(self.song.tracks) - 1)].id
        else:
            self.selected_track_id = None
        self.notify("selection")
        self.announce("Deleted {}".format(track.name))

    def rename_track(self, track_id, name):
        name = (name or "").strip()
        if not name:
            raise ValueError("A track needs a name")
        with self.edit("rename track"):
            self.song.track_by_id(track_id).name = name
        self.announce("Renamed to {}".format(name))

    def update_track(self, track_id, name=None, preset=None, volume=None, pan=None, mute=None, solo=None,
                     stereo=None, monitor=None):
        """Apply everything from the Track Settings dialog as one undo step (while Write automation is
        on and the song plays, a changed volume or pan is written into the automation instead)."""
        name = (name or "").strip() if name is not None else None
        if name == "":
            raise ValueError("A track needs a name")
        if self._writing():
            current = self.song.track_by_id(track_id)
            if volume is not None and int(volume) != self._heard_setting(current, "volume"):
                self.write_automation(track_id, ("volume", None, None), volume, speak=False)
            if pan is not None and int(pan) != self._heard_setting(current, "pan"):
                self.write_automation(track_id, ("pan", None, None), pan, speak=False)
            volume = pan = None
            others = {"name": (name, current.name), "stereo": (stereo, current.stereo),
                      "monitor": (monitor, current.monitor), "mute": (mute, current.mute),
                      "solo": (solo, current.solo)}
            unchanged = all(new is None or new == old for new, old in others.values())
            if unchanged and (preset is None or current.is_audio or (preset.bank, preset.program) ==
                              (current.instrument.bank, current.instrument.program)):
                self.announce("Written into the automation")    # the play-through stays one undo step
                return
        if preset is not None:
            preset = self._real_preset(preset)
        with self.edit("track settings"):
            track = self.song.track_by_id(track_id)
            if name is not None:
                track.name = name
            if preset is not None and not track.is_audio:
                track.instrument = Instrument(preset.bank, preset.program, preset.name)
            if stereo is not None:
                track.stereo = bool(stereo)
            if monitor is not None:
                track.monitor = bool(monitor)
            if volume is not None:
                track.volume = max(0, min(100, int(volume)))
            if pan is not None:
                track.pan = max(-100, min(100, int(pan)))
            if mute is not None:
                track.mute = bool(mute)
            if solo is not None:
                track.solo = bool(solo)
        self.announce("Track settings saved")

    @staticmethod
    def _real_preset(preset):
        """A guitar pack chosen before it is downloaded is stored under its own name, so the track is
        right once the pack arrives (the stand-in only plays meanwhile)."""
        if getattr(preset, "missing", False) and preset.bank in packs.PACK_BY_BANK:
            return type(preset)(preset.bank, preset.program, packs.PACK_BY_BANK[preset.bank].name)
        return preset

    def set_instrument(self, track_id, preset):
        track = self.song.track_by_id(track_id)
        if track is not None and track.is_audio:
            raise ValueError("An audio track plays recordings, so it has no instrument")
        preset = self._real_preset(preset)
        with self.edit("change instrument"):
            self.song.track_by_id(track_id).instrument = Instrument(preset.bank, preset.program, preset.name)
        self.announce("Instrument {}".format(preset.name))

    def set_volume(self, track_id, volume, speak=True):
        volume = max(0, min(100, int(volume)))
        if self._writing():
            self.write_automation(track_id, ("volume", None, None), volume, speak)
            return
        with self.edit("change volume"):
            self.song.track_by_id(track_id).volume = volume
        if speak:
            self.announce("Volume {}".format(volume))

    def change_volume(self, track_id, delta):
        track = self.song.track_by_id(track_id)
        if track is None:
            return
        if self._writing():
            self.set_volume(track_id, self._heard_setting(track, "volume") + delta)
            return
        self.set_volume(track_id, track.volume + delta, speak=False)
        self.announce("Volume {}{}".format(self.song.track_by_id(track_id).volume, self._lane_note(track, "volume")))

    def set_pan(self, track_id, pan, speak=True):
        pan = max(-100, min(100, int(pan)))
        if self._writing():
            self.write_automation(track_id, ("pan", None, None), pan, speak)
            return
        with self.edit("change pan"):
            self.song.track_by_id(track_id).pan = pan
        if speak:
            self.announce("Pan {}".format(self.song.track_by_id(track_id).pan_description()))

    def change_pan(self, track_id, delta):
        track = self.song.track_by_id(track_id)
        if track is None:
            return
        if self._writing():
            self.set_pan(track_id, self._heard_setting(track, "pan") + delta)
            return
        self.set_pan(track_id, track.pan + delta, speak=False)
        changed = self.song.track_by_id(track_id)
        self.announce("Pan {}{}".format(changed.pan_description(), self._lane_note(changed, "pan")))

    def _lane_note(self, track, target):
        """Said after a volume or pan change that a lane overrides."""
        if any(lane["target"] == target and lane.get("on", True) and lane["points"] for lane in track.automation):
            return (". The {} automation lane is on, so you hear the lane; turn it off in Automation "
                    "(Control+Shift+U) to hear this".format(target))
        return ""

    def _heard_setting(self, track, target):
        """A track's volume or pan as heard now: its automation lane's value at the playhead, or its own
        setting (so [ and ] step from what you hear)."""
        for lane in track.automation:
            if lane["target"] == target and lane.get("on", True) and lane["points"]:
                from . import automation

                return int(round(automation.value_at(lane["points"], self.position_tick())))
        return track.volume if target == "volume" else track.pan

    def toggle_mute(self, track_id):
        track = self.song.track_by_id(track_id)
        with self.edit("mute"):
            track.mute = not track.mute
        self.announce("Muted" if track.mute else "Unmuted")

    def toggle_solo(self, track_id):
        track = self.song.track_by_id(track_id)
        with self.edit("solo"):
            track.solo = not track.solo
        self.announce("Solo on" if track.solo else "Solo off")

    def move_track(self, track_id, delta):
        index = self.song.index_of(track_id)
        target = index + delta
        if not 0 <= target < len(self.song.tracks):
            self.announce("Already at the {}".format("top" if delta < 0 else "bottom"))
            return
        with self.edit("move track"):
            self.song.move_track(track_id, target)
        self.announce("Moved to position {}".format(target + 1))

    def preview_instrument(self, preset, pitch=None):
        drum = preset.bank == 128
        if pitch is None:
            pitch = 38 if drum else PREVIEW_PITCH
        self.engine.set_channel_instrument(PREVIEW_CHANNEL, preset.bank, preset.program, drum)
        self.engine.audition(PREVIEW_CHANNEL, pitch, 100, seconds=0.6)

    # ------------------------------------------------------------------
    # transport (Space loops the current section unless
    # "All sections" is on; recording in a fixed section loops and layers
    # takes; an Automatic section grows when you record past its end)
    # ------------------------------------------------------------------
    def position_tick(self):
        if self.engine.playing:
            return max(0, int(round(self.engine.position_tick())))
        return self._playhead

    def _pref(self, key, default=False):
        if self.settings is None:
            return default
        try:
            return self.settings[key]
        except KeyError:
            return default

    def current_section_index(self, tick=None):
        tick = self.position_tick() if tick is None else tick
        return self.song.section_index_at_bar(self.song.timeline.tick_to_bar(tick))

    def section_ticks(self, index):
        start, end = self.song.section_bounds(index)
        tl = self.song.timeline
        return tl.bar_to_tick(start), tl.bar_to_tick(end)

    def describe_position(self, tick=None):
        tick = self.position_tick() if tick is None else tick
        return self.song.timeline.describe_position(tick)

    def describe_status(self):
        tl = self.song.timeline
        tick = self.position_tick()
        bar = tl.tick_to_bar(tick)
        index = self.current_section_index(tick)
        state = "Recording" if self.engine.recording else ("Playing" if self.engine.playing else "Stopped")
        return "{}. {}. {}, {} of {}. {} BPM, {} time, {}.".format(
            state, self.describe_position(tick), self.song.section_name(index), index + 1,
            len(self.song.sections), format_number(tl.tempo_at_tick(tick)),
            tl.time_signature_at_bar(bar).spoken(), tl.key_at_bar(bar).name())

    def describe_play_mode(self):
        return "All sections play" if self.all_sections else "The current section loops"

    def _clamped_playhead(self):
        """The playhead, pulled back inside the song if it is past the end."""
        song_end = self.song.song_end_tick()
        if self._playhead >= song_end:
            start, _end = self.section_ticks(len(self.song.sections) - 1)
            self._playhead = start
        return self._playhead

    def _plan_region(self, tick, recording):
        """Where the engine loops, stops or goes quiet, for playing or recording from `tick`."""
        index = self.current_section_index(tick)
        section = self.song.sections[index]
        start, end = self.section_ticks(index)
        if recording and section.automatic:
            later_sections = index < len(self.song.sections) - 1
            return None, None, (end if later_sections else None)
        if self.all_sections:
            return None, self.song.song_end_tick(), None
        return (start, end), None, None

    def _refresh_region(self):
        """After an edit or a move while playing (not while recording a take)."""
        if self.engine.playing and not self.engine.recording:
            self.engine.set_region(*self._plan_region(self.position_tick(), recording=False))

    def toggle_play(self):
        if self.engine.playing:
            self.stop()
            return
        tick = self._clamped_playhead()
        self._play_start = tick
        self.new_write_pass()
        self.engine.set_region(*self._plan_region(tick, recording=False))
        self.engine.play(tick)
        if self._pref("announce_play_start"):
            self.announce("Play")
        self.notify("transport")

    def stop(self, speak=True):
        if not self.engine.playing:
            return
        tick = self.position_tick()
        self.engine.stop()
        self._playhead = min(tick, max(0, self.song.song_end_tick() - 1))
        self._wait_for_engine()
        if speak:
            self.announce("Stopped, {}".format(self.describe_position(self._playhead)))
        self.notify("transport")

    def stop_button(self):
        """Stop; if already stopped, go back to the start of the current section."""
        if self.engine.playing:
            self.stop()
        else:
            index = self.current_section_index()
            self.locate(self.section_ticks(index)[0], speak=False)
            self.announce(self.describe_bar(self.song.section_bounds(index)[0]))

    def toggle_record(self):
        track = self.selected_track
        if track is None:
            self.announce("Add a track before recording")
            return
        if self.engine.recording:
            self.stop()
            return
        kind = "notes"
        if track.is_audio:
            if not self._prepare_microphone(track):
                return
            kind = "audio"
        speak = self._pref("announce_record_start")
        if self.engine.playing:
            tick = self.position_tick()
            self._take = self._new_take(track.id, tick)
            plan = self._plan_region(tick, recording=True)
            self._take["loop"] = plan[0]
            self.engine.set_region(*plan)
            self.engine.punch_in(track.id, kind)
            if speak:
                self.announce("Recording on {}".format(track.name))
        else:
            tick = self._clamped_playhead()
            self._play_start = tick
            self.new_write_pass()
            self._take = self._new_take(track.id, tick)
            plan = self._plan_region(tick, recording=True)
            self._take["loop"] = plan[0]
            self.engine.set_region(*plan)
            self.engine.record(track.id, tick, kind)
            if speak:
                bars = self.engine.count_in_bars
                count = ", {} bar count-in".format(bars) if bars else ""
                self.announce("Record on {}{}".format(track.name, count))
        self.notify("transport")

    def _new_take(self, track_id, tick):
        index = self.current_section_index(tick)
        return {"track_id": track_id, "section": index, "automatic": self.song.sections[index].automatic,
                "undo_open": False, "count": 0, "start": int(tick), "loop": None, "end": 0}

    def locate(self, tick, speak=True):
        if self.engine.recording:
            self.announce("Stop recording before moving the playhead")
            return False
        tick = max(0, min(int(tick), self.song.song_end_tick() - 1))
        self._playhead = tick
        self.engine.locate(tick)
        if self.engine.playing:
            self.engine.set_region(*self._plan_region(tick, recording=False))
        if speak:
            self.announce(self.describe_position(tick))
        self.notify("transport")
        return True

    def describe_bar(self, bar):
        """'Bar 9, start of Section 2' - says when a bar is the first or last of its section."""
        index = self.song.section_index_at_bar(bar)
        start, end = self.song.section_bounds(index)
        name = self.song.section_name(index)
        first, last = bar == start, bar == end - 1
        if first and last:
            return "Bar {}, start and end of {}".format(bar, name)
        if first:
            return "Bar {}, start of {}".format(bar, name)
        if last:
            return "Bar {}, end of {}".format(bar, name)
        return "Bar {}".format(bar)

    def _floor_tick(self):
        """Where Go to start and rewinding stop: the current section's start, or with All sections on, the song's
        (Russell, 10 Oct 2026: rewinding before the section is only for All sections)."""
        if self.all_sections:
            return 0
        return self.section_ticks(self.current_section_index())[0]

    def go_to_start(self):
        """Enter: the start of the current section (with All sections on, of the song)."""
        tick = self._floor_tick()
        if self.locate(tick, speak=False):
            self.announce(self.describe_bar(self.song.timeline.tick_to_bar(tick)))

    def go_to_bar(self, bar, beat=1.0):
        bar = max(1, min(int(bar), self.song.end_bar() - 1))
        beats = self.song.timeline.time_signature_at_bar(bar).numerator
        beat = max(1.0, min(float(beat), beats + 0.999))
        if self.locate(self.song.timeline.position_to_tick(bar, beat), speak=False):
            self.announce(self.describe_bar(bar) if beat == 1.0 else self.describe_position())

    def move_bars(self, count):
        """Rewind and Forward: one bar at a time, saying when you reach a section's start or end."""
        if self.engine.recording:
            return  # nothing is spoken while recording; the playhead stays put
        tl = self.song.timeline
        tick = self.position_tick()
        bar = tl.tick_to_bar(tick)
        last_bar = self.song.end_bar() - 1
        floor = self._floor_tick()
        first_bar = tl.tick_to_bar(floor)
        target = bar + count
        if target < first_bar:
            if bar == first_bar and tick == floor:
                self.announce("Start of song" if floor == 0 else
                              "Start of {}".format(self.song.section_name(self.current_section_index(tick))))
                return
            target = first_bar
        if target > last_bar:
            if bar >= last_bar:
                self.announce("End of song")
                return
            target = last_bar
        if self.locate(tl.bar_to_tick(target), speak=False):
            self.announce(self.describe_bar(target))

    def move_beats(self, count):
        if self.engine.recording:
            return
        tl = self.song.timeline
        tick = self.position_tick()
        bar, beat = tl.tick_to_position(tick)
        target = tl.position_to_tick(bar, int(beat)) + count * tl.ticks_per_beat(bar)
        floor = self._floor_tick()
        if count < 0 and target < floor:
            if tick <= floor:
                self.announce("Start of song" if floor == 0 else
                              "Start of {}".format(self.song.section_name(self.current_section_index(tick))))
                return
            target = floor
        self.locate(max(0, target))

    def next_section(self):
        if self.engine.recording:
            return
        index = self.current_section_index()
        if index + 1 >= len(self.song.sections):
            self.announce("Last section")
            return
        self._go_to_section(index + 1)

    def previous_section(self):
        if self.engine.recording:
            return
        tick = self.position_tick()
        index = self.current_section_index(tick)
        start_tick = self.section_ticks(index)[0]
        if tick - start_tick > PPQ // 2:  # already into this section: back to its start
            self._go_to_section(index)
        elif index > 0:
            self._go_to_section(index - 1)
        else:
            self.announce("First section")

    def go_to_section(self, index):
        self._go_to_section(index)

    def _go_to_section(self, index):
        start_bar, _end = self.song.section_bounds(index)
        if self.locate(self.section_ticks(index)[0], speak=False):
            self.announce("{}, bar {}".format(self.song.section_name(index), start_bar))

    def toggle_all_sections(self):
        self.all_sections = not self.all_sections
        if self.settings is not None:
            self.settings["play_all_sections"] = self.all_sections
            self.settings.save()
        self._refresh_region()
        self.announce("All sections play" if self.all_sections else "Current section loops")
        self.notify("transport")

    def toggle_metronome(self):
        on = not self.engine.metronome_on
        self.engine.metronome_on = on
        if self.settings is not None:
            self.settings["metronome_on"] = on
            self.settings.save()
        self.announce("Metronome on" if on else "Metronome off")
        self.notify("transport")

    def cycle_count_in(self):
        bars = (self.engine.count_in_bars + 1) % 3
        self.engine.count_in_bars = bars
        if self.settings is not None:
            self.settings["count_in_bars"] = bars
            self.settings.save()
        self.announce("Count-in off" if bars == 0 else "Count-in {} bar{}".format(bars, "s" if bars > 1 else ""))

    def poll(self):
        """Handle messages from the engine. Call this regularly (the window does, 10 times a second)."""
        handled = 0
        if self._low_latency is not None:
            self._check_low_latency()
        while not self.engine.messages.empty():
            message = self.engine.messages.get()
            handled += 1
            kind = message[0]
            if kind in ("recorded", "audio_recorded") and self._stale_take:
                self._drop_stale_take(message)
            elif kind == "recorded":
                partial = message[3] if len(message) > 3 else False
                self._finish_recording(message[1], message[2], partial)
            elif kind == "audio_recorded":
                self._finish_audio_recording(*message[1:])
            elif kind == "stopped":
                self._playhead = max(0, min(int(round(self.engine.position_tick())),
                                            self.song.song_end_tick() - 1))
                self.announce("End of song, stopped")
                self.notify("transport")
            elif kind == "delay_measured":
                self._finish_measurement(*message[1:])
            elif kind == "soundfont_loaded":
                self._soundfont_loaded(message[1], message[2])
            elif kind == "soundfont_failed":
                log.warning("SoundFont %s could not be loaded: %s", message[1], message[2])
                self.announce("{} could not be loaded: {}".format(os.path.basename(message[1]), message[2]))
            elif kind == "error":
                self.announce(message[1])
        return handled

    def _soundfont_loaded(self, path, presets):
        """A guitar pack finished downloading and is loaded: tracks that used the stand-in now play it."""
        self.presets = presets
        name = os.path.basename(path)
        for pack in packs.PACKS:
            if os.path.basename(pack.filename) == name:
                name = pack.name
        self.announce("{} is ready. Tracks that use it play it now.".format(name))
        self.notify("presets")

    def _finish_recording(self, track_id, notes, partial=False):
        """Notes from a take (or from one pass of a looped take) go into the song.

        All passes of one take share a single undo step.
        """
        track = self.song.track_by_id(track_id)
        take = self._take if self._take and self._take["track_id"] == track_id else None
        if take is None:
            take = self._new_take(track_id, notes[0].tick if notes else 0)
        if notes:
            take["end"] = max(take["end"], max(n.end for n in notes))
        if track is not None and (notes or (not partial and take["count"])):
            with self.edit("recording on {}".format(track.name), record_undo=not take["undo_open"]):
                section = take["section"]
                if (not partial and take["automatic"] and section < len(self.song.sections)
                        and self.song.sections[section].automatic):   # Control+Z during the take can change that
                    arrange.grow_section_for_recording(self.song, section, notes)
                track.notes.extend(notes)
                track.sort_notes()
                if not partial and not track.is_audio:
                    self._place_take_region(track, take)
                    self.selected_regions.clear()
            take["undo_open"] = True
            take["count"] += len(notes)
        if partial:
            self._take = take
            return
        self._take = None
        if self._pref("announce_recorded_notes") and track is not None:
            count = take["count"]
            if count:
                self.announce("Recorded {} note{} on {}".format(count, "" if count == 1 else "s", track.name),
                              interrupt=False)
            else:
                self.announce("Nothing was recorded", interrupt=False)

    def _place_take_region(self, track, take):
        """A finished take gets a region of its own: the looping section it was recorded in, or from
        the bar where recording started to the bar after it stopped (across sections if need be)."""
        tl = self.song.timeline
        if take["loop"] is not None:
            start, end = take["loop"]
        else:
            stop = max(take["end"], int(round(self.engine.position_tick())), take["start"] + 1)
            start, end = regions.bar_span(tl, take["start"], stop)
        regions.claim(track, start, end)

    def _wait_for_engine(self, timeout=0.5):
        """After stop: give the audio thread a moment to hand back the recording."""
        if not self.audio_is_live:
            self.poll()
            return
        deadline = time.monotonic() + timeout
        while self.engine.messages.empty() and time.monotonic() < deadline:
            if not self.engine.commands.empty() or self.engine.playing:
                time.sleep(0.005)
            else:
                break
        self.poll()

    def _stop_engine_quietly(self):
        """Stop before the song is replaced (New, Open). The window stops first, so a take being recorded goes
        into the project it belongs to and is asked about; whatever the engine still hands back after this
        belongs to the project being replaced, and is dropped instead of landing in the next one (on a track
        that happens to have the same number)."""
        if self.engine.recording:
            self._stale_take = True
        self.engine.stop()
        self.engine.panic()
        self._held.clear()
        self.typing.release_all()
        self._take = None

    def _drop_stale_take(self, message):
        if message[0] == "audio_recorded":
            self._release_microphone()
            final = True
        else:
            final = not (len(message) > 3 and message[3])   # a looping pass is followed by the take's end
        if final:
            self._stale_take = False
        log.warning("A take from the project that was closed arrived afterwards and was not kept (%s)", message[0])

    # ------------------------------------------------------------------
    # sections
    # ------------------------------------------------------------------
    def describe_section(self, index):
        return self.song.describe_section(index)

    def add_section(self, after_index=None, length=8):
        if self.engine.recording:
            raise ValueError("Stop recording before changing sections")
        after = self.current_section_index() if after_index is None else after_index
        with self.edit("add section"):
            index = arrange.add_section_after(self.song, after, length)
        self.announce("Added {}".format(self.describe_section(index)))
        return index

    def duplicate_section(self, index):
        if self.engine.recording:
            raise ValueError("Stop recording before changing sections")
        with self.edit("duplicate section"):
            new = arrange.duplicate_section(self.song, index)
        self.announce("Copied to {}".format(self.describe_section(new)))
        return new

    def delete_section(self, index):
        if self.engine.recording:
            raise ValueError("Stop recording before changing sections")
        name = self.song.section_name(index)
        with self.edit("delete section"):
            arrange.delete_section(self.song, index)
        self._playhead = max(0, min(self._playhead, self.song.song_end_tick() - 1))
        self.announce("Deleted {}".format(name))
        return min(index, len(self.song.sections) - 1)

    def move_section(self, index, delta):
        if self.engine.recording:
            raise ValueError("Stop recording before changing sections")
        name = self.song.section_name(index)
        with self.edit("move section"):
            new = arrange.move_section(self.song, index, delta)
        self.announce("{} is now section {}".format(name, new + 1))
        return new

    def update_section(self, index, name=None, length=None, automatic=None):
        """Section settings: name (empty = its number), length in bars, Automatic switch."""
        if self.engine.recording:
            raise ValueError("Stop recording before changing sections")
        with self.edit("section settings"):
            section = self.song.sections[index]
            if name is not None:
                section.name = name.strip()
            if automatic is not None:
                section.automatic = bool(automatic)
            if length is not None and int(length) != section.length:
                arrange.set_section_length(self.song, index, int(length))
        self._playhead = max(0, min(self._playhead, self.song.song_end_tick() - 1))
        self.announce("Section settings saved. {}".format(self.describe_section(index)))

    def notes_lost_if_shortened(self, index, new_length):
        start, end = self.song.section_bounds(index)
        if new_length >= end - start:
            return 0
        return arrange.notes_in_bars(self.song, start + new_length, end)

    # ------------------------------------------------------------------
    # audio tracks: recordings from the microphone, and imported WAV files
    #
    # While a project is open, every recording is known by its full path.
    # Saving copies recordings into the project's own folder (the Recordings
    # folder next to "My Song.mforge") and writes them into the project file
    # relative to it, so a project and its Recordings folder move together.
    # Recordings made before a project is first saved wait in Musician Forge's
    # recordings folder; if the project is never saved, they are deleted.
    # ------------------------------------------------------------------
    @property
    def recordings_dir(self):
        if self._recordings_dir is None:
            if self.autosave_dir:
                self._recordings_dir = os.path.join(os.path.dirname(os.path.abspath(self.autosave_dir)),
                                                    "recordings")
            else:
                self._recordings_dir = tempfile.mkdtemp(prefix="musicianforge-recordings-")
        return self._recordings_dir

    def audio_path(self, file):
        """A recording's full path (a relative name belongs to the project's folder)."""
        if os.path.isabs(file):
            return os.path.normpath(file)
        base = os.path.dirname(os.path.abspath(self.path)) if self.path else self.recordings_dir
        return os.path.normpath(os.path.join(base, file))

    def load_audio(self, file):
        """A recording's audio, float32 shaped (frames, channels), or None if the file is missing."""
        path = self.audio_path(file)
        data = self._audio_cache.get(path)
        if data is None:
            try:
                raw, rate, _bits = wavfile.read_wav(path, np.float32)
            except Exception:  # noqa: BLE001 - a missing or damaged recording plays as silence
                if path not in self._missing_audio:
                    self._missing_audio.add(path)
                    log.warning("Recording not found or unreadable: %s", path)
                return None
            data = raw if rate == AUDIO_RATE else audiotracks.resample(raw, rate).astype(np.float32)
            self._audio_cache[path] = data
        return data

    def _takes(self, song=None):
        return [take for track in (song or self.song).tracks for region in track.regions for take in region.takes]

    def missing_recordings(self):
        return sum(1 for take in self._takes() if not os.path.isfile(self.audio_path(take.file)))

    @staticmethod
    def _absolute_audio(song, base_dir):
        """After opening: recordings named relative to the project get their full path."""
        for track in song.tracks:
            for region in track.regions:
                for take in region.takes:
                    if not os.path.isabs(take.file):
                        take.file = os.path.normpath(os.path.join(base_dir, take.file))

    def _song_for_file(self, project_path):
        """A copy of the song for the project file, with recordings named relative to the project."""
        copy = self.song.clone()
        base = os.path.dirname(os.path.abspath(project_path))
        for take in self._takes(copy):
            try:
                take.file = os.path.relpath(self.audio_path(take.file), base).replace(os.sep, "/")
            except ValueError:
                pass  # on another drive: keep the full path
        return copy

    def _gather_audio(self, project_path):
        """Before saving: copy recordings into the project's own audio folder, and use them from there."""
        folder = os.path.normcase(audiotracks.audio_folder_for(project_path))
        for take in self._takes():
            source = self.audio_path(take.file)
            take.file = source
            if os.path.normcase(os.path.dirname(source)) == folder or not os.path.isfile(source):
                continue  # already in place, or missing (it keeps pointing where it was)
            target = self._gathered.get(source)
            if target is None or not os.path.isfile(target) or os.path.normcase(os.path.dirname(target)) != folder:
                os.makedirs(audiotracks.audio_folder_for(project_path), exist_ok=True)
                stem = os.path.splitext(os.path.basename(source))[0]
                target = audiotracks.unique_path(audiotracks.audio_folder_for(project_path), stem)
                shutil.copy2(source, target)
                self._gathered[source] = target
                if source in self._audio_cache:
                    self._audio_cache[target] = self._audio_cache[source]
                log.info("Copied recording into the project: %s", target)
            take.file = target

    def _discard_scratch(self):
        """Delete recordings of a project that was never saved, now that it is gone."""
        keep = {os.path.normcase(self.audio_path(t.file)) for t in self._takes()} if self.song else set()
        for path in list(self._scratch):
            if os.path.normcase(path) in keep:
                continue
            try:
                os.remove(path)
                log.info("Deleted an unsaved recording: %s", path)
            except OSError:
                pass
            self._audio_cache.pop(path, None)
        self._scratch = {p for p in self._scratch if os.path.normcase(p) in keep}

    def clean_old_recordings(self, days=7):
        """At start: delete leftover recordings of unsaved projects (after a crash) older than `days`,
        unless the project waiting to be recovered still uses them."""
        folder = self.recordings_dir
        if not os.path.isdir(folder):
            return 0
        keep = {os.path.normcase(self.audio_path(t.file)) for t in self._takes()}
        pending = self.recovery_available()
        if pending:
            try:
                keep |= {os.path.normcase(os.path.normpath(t.file)) for t in self._takes(Song.load(pending))}
            except Exception:  # noqa: BLE001
                return 0  # unsure what the recovery needs: delete nothing
        cutoff = time.time() - days * 86400
        removed = 0
        for name in os.listdir(folder):
            path = os.path.join(folder, name)
            if not name.lower().endswith(".wav") or os.path.normcase(path) in keep:
                continue
            try:
                if os.path.getmtime(path) < cutoff:
                    os.remove(path)
                    removed += 1
            except OSError:
                pass
        if removed:
            log.info("Deleted %d old recordings of unsaved projects", removed)
        return removed

    def shutdown(self, keep_recordings=False):
        """When Musician Forge closes (after the offer to save): the microphone off, and recordings of a
        project that was never saved are deleted. A saved project uses its own copies. keep_recordings: closed
        by Windows with unsaved changes, so the crash-recovery copy still needs them."""
        self._release_microphone()
        if keep_recordings:
            return
        song, self.song = self.song, None
        try:
            self._discard_scratch()
        finally:
            self.song = song

    def add_audio_track(self, name=None, speak=True):
        """A new track for recording sound (a microphone) or for WAV files."""
        if self.engine.recording:
            raise ValueError("Stop recording before adding a track")
        with self.edit("add audio track"):
            index = self.song.index_of(self.selected_track_id) + 1 if self.selected_track_id else None
            track = self.song.add_track(name, Instrument(0, 0, "Audio"), index=index)
            track.kind = AUDIO_TRACK
            if not name:
                track.name = "Audio {}".format(sum(1 for t in self.song.tracks if t.is_audio))
        self.selected_track_id = track.id
        self.notify("selection")
        if speak:
            self.announce("Added {}. Press R to record from the microphone.".format(self.describe_track(track.id)))
        return track

    def describe_microphone(self):
        if self.audio_input is None:
            return "none"
        return self.audio_input.description

    def _prepare_microphone(self, track):
        if self.audio_input is None:
            self.announce("Recording sound needs a microphone. Choose one in Options, Audio settings.")
            return False
        try:
            self.audio_input.ensure_open(channels=2 if track.stereo else 1)
        except Exception as exc:  # noqa: BLE001
            log.exception("Could not open the microphone")
            self.announce("The microphone could not be opened. {}".format(exc))
            return False
        self._chunks_at_start = self.audio_input.chunks
        self._start_monitoring(track)
        return True

    def _start_monitoring(self, track):
        """Hear the microphone while recording, when the track asks for it: the low-latency way when Audio
        settings turn it on and Windows allows it (0.9.1), otherwise through the engine (with the track's effects).
        A low-latency way that cannot start says why, once each time Musician Forge runs, and the usual way is
        used."""
        self._stop_low_latency()
        if not track.monitor:
            self.engine.set_monitoring(False)
            return
        audio = self.settings["audio"] if self.settings is not None else {}
        if audio.get("low_latency_monitoring") and self.low_latency_factory is not None:
            from . import lowlatency
            from .engine import track_gains

            left, right = (0.0, 0.0) if track.mute else track_gains("audio", track.volume, track.pan)
            master = self.engine.master_gain
            try:
                monitor = self.low_latency_factory(output_name=audio.get("device_name", ""),
                                                   input_name=audio.get("input_device", ""),
                                                   raw=audio.get("raw_microphone", True), stereo=track.stereo,
                                                   gains=(left * master, right * master))
                description = monitor.start()
            except (lowlatency.Unavailable, OSError) as exc:
                log.info("Low-latency hearing yourself is not available: %s", exc)
                if not self._low_latency_said:
                    self._low_latency_said = True
                    self.announce("Low-latency hearing yourself is not available: {}. You hear yourself the usual "
                                  "way.".format(exc), interrupt=False)
            else:
                self._low_latency = monitor
                self.engine.set_monitoring(False)
                log.info("Hearing yourself the low-latency way: %s", description)
                return
        self.engine.set_monitoring(True)

    def _stop_low_latency(self):
        monitor, self._low_latency = self._low_latency, None
        if monitor is None:
            return
        try:
            monitor.stop()
        except Exception:  # noqa: BLE001
            log.exception("Stopping low-latency hearing yourself failed")
        report = monitor.report()
        if report:
            log.info("Hearing yourself while recording: %s", report)

    def _check_low_latency(self):
        """A low-latency monitor that stopped by itself (a headset unplugged) hands over to the usual way."""
        monitor = self._low_latency
        if monitor is not None and not monitor.running:
            self._stop_low_latency()
            self.engine.set_monitoring(True)       # the microphone is still open: the take goes on
            log.info("Low-latency hearing yourself stopped by itself; hearing yourself the usual way")

    def _release_microphone(self):
        self._stop_low_latency()
        self.engine.set_monitoring(False)
        report = self.engine.monitor_report()
        if report:
            log.info("Hearing yourself while recording: %s", report)
        if self.audio_input is not None:
            try:
                self.audio_input.release()
            except Exception:  # noqa: BLE001
                log.exception("Closing the microphone failed")

    def _finish_audio_recording(self, track_id, first, audio, loop):
        """A take from the microphone: saved as WAV files (one per loop pass) and placed on the track.

        Passes over a looping section become takes of one recording; the newest complete pass plays.
        A last pass cut short by Stop (recording ran past the end of the section and wrapped round) is
        kept as a take too, but never hides the complete pass before it (8 Oct 2026: Russell recorded bar
        1 to bar 9 in an 8-bar section, the 1.5-second spill-over became the take that played, and the
        whole take seemed lost). A recording is never deleted on its own. The whole take is one undo step.
        """
        heard_nothing = (self.audio_input is not None and self.audio_input.chunks == self._chunks_at_start)
        self._release_microphone()
        track = self.song.track_by_id(track_id)
        take = self._take if self._take and self._take["track_id"] == track_id else self._new_take(track_id, 0)
        self._take = None
        pieces = audiotracks.cut_passes(first, audio, loop)
        if loop is not None and len(pieces) > 1 and pieces[0][0] > loop[0]:
            # punched in partway through a looping section: the first pass becomes a whole-section
            # take (silent until the punch-in), so every pass is a take of the same recording
            start, data = pieces[0]
            pad = np.zeros((start - loop[0], data.shape[1]), dtype=data.dtype)
            pieces[0] = (loop[0], np.concatenate([pad, data]))
        pieces = [(start, data) for start, data in pieces if len(data) >= audiotracks.MIN_TAKE_SECONDS * AUDIO_RATE]
        if track is None or not pieces:
            if heard_nothing:
                self.announce("Nothing was recorded: no sound came from the microphone. "
                              "Options, Audio settings has a microphone test.")
            elif self._pref("announce_recorded_notes"):
                self.announce("Nothing was recorded", interrupt=False)
            return
        whole = loop[1] - loop[0] if loop is not None else None
        complete = [whole is None or len(data) >= whole - 2 for _start, data in pieces]
        files = [self._save_recording(data) for _start, data in pieces]
        tl = self.song.timeline
        short_passes = []   # (region, its take index) of last passes cut short: kept, not played
        layered = {}        # region recorded over again -> how many takes it had before
        with self.edit("recording on {}".format(track.name)):
            last_end = 0
            ours = set()    # regions this recording made or added a take to
            for (start, data), file, whole_pass in zip(pieces, files, complete):
                tick = max(0, int(round(tl.seconds_to_tick(start / float(AUDIO_RATE)))))
                new_take = AudioTake(file, len(data))
                region = next((r for r in track.regions if abs(r.tick - tick) <= 2), None)
                if region is None:
                    region = AudioRegion(tick, [new_take], 0, layer=track.top_layer())
                    track.regions.append(region)
                elif whole_pass or id(region) not in ours:
                    if id(region) not in ours:
                        layered[id(region)] = (region, len(region.takes))
                    region.takes.append(new_take)
                    # the same spot again: another take, and the newest plays, from its first frame and all
                    # the way (an earlier take's trim would cut the new one short or move it)
                    region.active = len(region.takes) - 1
                    region.offset, region.length = 0, 0
                    region.layer = track.top_layer()
                else:
                    region.takes.append(new_take)      # cut short by Stop: kept, but the complete pass plays
                    short_passes.append((region, len(region.takes) - 1))
                ours.add(id(region))
                last_end = max(last_end, region.end_tick(tl))
            track.sort_regions()
            if take["automatic"]:
                arrange.grow_section_to(self.song, take["section"], last_end)
        warning = audiotracks.recording_warning(audio)
        if warning:
            self.announce(warning, interrupt=False)  # always said: something needs attention
        elif self._pref("announce_recorded_notes"):
            self.announce("Recorded {} take{} on {}".format(len(pieces), "" if len(pieces) == 1 else "s",
                                                           track.name), interrupt=False)
        # always said, so a take never seems lost: where the earlier takes went, and why a pass does not play
        for region, before in layered.values():
            if before:
                self.announce("Take {} plays at {}; the earlier take{} {} kept. Control+L lists the recordings, and "
                              "Enter there chooses the take that plays.".format(
                                  region.active + 1, tl.spoken_bar_position(region.tick),
                                  "" if before == 1 else "s", "is" if before == 1 else "are"), interrupt=False)
        for region, index in short_passes:
            self.announce("The last pass was cut short when you stopped, so it is kept as take {} and take {} still "
                          "plays.".format(index + 1, region.active + 1), interrupt=False)

    def _new_recording_path(self, stem=None):
        """Where a new recording (or an imported file's copy) goes: the project's Recordings folder, or
        Musician Forge's own recordings folder until the project is saved."""
        folder = audiotracks.audio_folder_for(self.path) if self.path else self.recordings_dir
        os.makedirs(folder, exist_ok=True)
        return audiotracks.unique_path(folder, stem or "Recording {}".format(time.strftime("%Y-%m-%d %H-%M-%S")))

    def _save_recording(self, data, stem=None):
        """Write a recording (24-bit WAV, 48 kHz) and return its full path."""
        path = self._new_recording_path(stem)
        wavfile.write_wav(path, data, AUDIO_RATE, 24)
        self._audio_cache[os.path.normpath(path)] = np.asarray(data, dtype=np.float32)
        if not self.path:
            self._scratch.add(os.path.normpath(path))
        log.info("Saved recording: %s (%.1f seconds)", path, len(data) / float(AUDIO_RATE))
        return os.path.normpath(path)

    def prepare_import(self, path, progress=None, cancelled=None, decoded=None):
        """The slow part of importing an audio file: read it, convert it to 48 kHz and write Musician Forge's
        copy (24-bit WAV) in the project's Recordings folder. It changes nothing in the project, so the window
        runs it in a worker thread while it shows progress; import_audio() then puts it on a track at once.

        A piece at a time, so a long file is held in memory only as read and as converted (a 5-minute stereo
        file took about 690 MB more and froze the window for 10 seconds before; 9 Oct 2026). Raises
        AudioImportError (a ValueError) with words, or audioimport.ImportCancelled (then no copy is left)."""
        def part(low, high):
            if progress is None:
                return None
            return lambda fraction: progress(low + (high - low) * max(0.0, min(1.0, fraction)))

        name = os.path.basename(path)
        if decoded is None:
            decoded = audioimport.read(path, progress=part(0.0, 0.6), cancelled=cancelled)
        raw, rate, decoder = decoded.audio, int(decoded.rate), decoded.decoder
        channels = raw.shape[1]
        total = len(raw) if rate == AUDIO_RATE else int(round(len(raw) * AUDIO_RATE / float(rate)))
        if not total:
            raise ValueError("{} holds no sound".format(name))
        converting = part(0.6, 0.85)
        audio = np.empty((total, channels), dtype=np.float32)
        done, peak = 0, 0.0
        for piece in audiotracks.resample_pieces(raw, rate):
            if cancelled is not None and cancelled():
                raise audioimport.ImportCancelled()
            n = min(len(piece), total - done)
            if n <= 0:
                break
            audio[done:done + n] = piece[:n]
            peak = max(peak, float(np.max(np.abs(audio[done:done + n]))))
            done += n
            if converting:
                converting(done / float(total))
        audio = audio[:done]
        del raw, decoded
        if peak > 1.0:
            audio /= peak               # a decoder's overshoot: the whole file a little quieter, never clipped
        saving = part(0.85, 1.0)
        file = self._new_recording_path(os.path.splitext(name)[0])
        try:
            writer = wavfile.WavWriter(file, AUDIO_RATE, 24, channels)
            try:
                for start in range(0, len(audio), wavfile.READ_CHUNK):
                    if cancelled is not None and cancelled():
                        raise audioimport.ImportCancelled()
                    writer.write(audio[start:start + wavfile.READ_CHUNK])
                    if saving:
                        saving(min(1.0, (start + wavfile.READ_CHUNK) / float(len(audio))))
            except BaseException:
                writer.abort()
                raise
            writer.close()
        except OSError as exc:
            raise ValueError("Musician Forge could not save its copy of {} in {} ({}). Check that the disk has "
                             "room.".format(name, os.path.dirname(file), exc.strerror or exc)) from None
        log.info("Imported audio: %s (%d Hz, %d channel(s), read by %s) as %s", path, rate, channels, decoder, file)
        return PreparedImport(path, os.path.normpath(file), audio, rate, channels, decoder)

    def check_import_target(self, track_id=None):
        """Raise ValueError (in words) before the slow part of an import when it could not be placed: while
        recording, on a track that is not an audio track, or when a new track is needed and there is no room."""
        if self.engine.recording:
            raise ValueError("Stop recording before importing")
        if track_id is not None:
            track = self.song.track_by_id(track_id)
            if track is None or not track.is_audio:
                raise ValueError("Choose an audio track first. Control+U adds one.")
            return
        track = self.selected_track
        if (track is None or not track.is_audio) and len(self.song.tracks) >= MAX_TRACKS:
            raise ValueError("A song can have up to {} tracks, so there is no room for the audio track this file "
                             "needs. Choose an audio track first.".format(MAX_TRACKS))

    def discard_prepared(self, prepared):
        """A prepared import that was cancelled after all: its copy is removed."""
        try:
            os.remove(prepared.file)
        except OSError:
            pass

    def import_audio(self, track_id, path, tick=None, decoded=None, prepared=None):
        """Bring an audio file into an audio track at the playhead: WAV, MP3, M4A, FLAC, Ogg, AIFF, Windows
        Media Audio and more (see audioimport.py), at any sample rate.

        prepared: the file already read and copied (prepare_import, which the window runs while showing
        progress); otherwise that is done here. Musician Forge keeps its own copy (24-bit WAV at 48 kHz) in the
        project's Recordings folder, so the original file is never changed."""
        track = self.song.track_by_id(track_id)
        if track is None or not track.is_audio:
            raise ValueError("Choose an audio track first. Control+U adds one.")
        if self.engine.recording:
            raise ValueError("Stop recording before importing")
        if prepared is None:
            prepared = self.prepare_import(path, decoded=decoded)
        file, audio = prepared.file, prepared.audio
        self._audio_cache[file] = audio
        if not self.path:
            self._scratch.add(file)
        tick = self.position_tick() if tick is None else int(tick)
        with self.edit("import audio"):
            region = AudioRegion(tick, [AudioTake(file, len(audio))], 0, layer=track.top_layer())
            track.regions.append(region)
            track.sort_regions()
            index = next(i for i, r in enumerate(track.regions) if r is region)
        where = ("the project's Recordings folder" if self.path else
                 "Musician Forge's own recordings folder until the project is saved")
        self.announce("Imported {}, {}, {}, {}, at {}. Musician Forge's copy is in {}.".format(
            os.path.basename(path), audiotracks.describe_seconds(len(audio)), describe_rate(prepared.rate),
            "stereo" if prepared.channels > 1 else "mono", self.describe_position(tick), where))
        return index

    def import_audio_file(self, path, decoded=None, prepared=None):
        """Import an audio file: onto the selected audio track, or onto a new audio track named after it."""
        track = self.selected_track
        if track is None or not track.is_audio:
            if prepared is None:
                prepared = self.prepare_import(path, decoded=decoded)   # first, so a bad file adds no track
            track = self.add_audio_track(os.path.splitext(os.path.basename(path))[0], speak=False)
        return self.import_audio(track.id, path, decoded=decoded, prepared=prepared)

    # -- MIDI files (0.9.1) ---------------------------------------------------
    def project_is_empty(self):
        """Nothing made yet: no notes, recordings or rhythm players (a new project's empty Piano track), no chords,
        and no song set up beyond what a new project starts with (one section, and no tempo, time signature or key
        changes), so a MIDI file's timeline can replace it without losing anything."""
        song = self.song
        tl = song.timeline
        return (not song.has_content() and not song.chords and len(song.sections) == 1 and not song.sections[0].name
                and len(tl.tempos) == 1 and len(tl.time_signatures) == 1 and len(tl.keys) == 1)

    def _exact_preset(self, exact):
        """The instrument a Musician Forge MIDI file names exactly ((bank, program)), if it is here, or None."""
        if not exact:
            return None
        for preset in self.presets:
            if (preset.bank, preset.program) == tuple(exact) and not getattr(preset, "missing", False):
                return Instrument(preset.bank, preset.program, preset.name)
        return None

    def _preset_named(self, bank, program, drums):
        """The instrument (bank, program, name) for a MIDI program change, falling back to the first bank's.
        General MIDI's Distortion Guitar becomes the FSBS distorted guitar pack, the real guitar Musician Forge
        exports as Distortion Guitar (the same rule in reverse, Russell, 10 Oct 2026)."""
        if not drums and bank == 0 and program == midifile.DISTORTION_GUITAR:
            for preset in self.presets:
                if (preset.bank, preset.program) == IMPORTED_DISTORTION_GUITAR:
                    # a pack not downloaded yet is kept by name, and the stand-in plays until it arrives
                    return Instrument(preset.bank, preset.program, packs.PACK_BY_BANK[preset.bank].name)
        wanted = [(128, program), (128, 0)] if drums else [(bank, program), (0, program)]
        for want in wanted:
            for preset in self.presets:
                if (preset.bank, preset.program) == want and not getattr(preset, "missing", False):
                    return Instrument(preset.bank, preset.program, preset.name)
        if drums:
            return Instrument(128, 0, "Standard drum kit")
        return Instrument(0, program, "Program {}".format(program + 1))

    def import_midi(self, path, contents=None, use_timeline=None):
        """Bring a MIDI file in: a track for each MIDI track (or channel) with notes, and, when use_timeline
        is on (the default for a project with nothing in it yet), the file's tempo changes, time signatures,
        keys and markers as sections. One undo step. Returns the words that were said."""
        from . import automation, midiimport

        if self.engine.recording:
            raise ValueError("Stop recording before importing")
        if contents is None:
            try:
                contents = midiimport.read_file(path)
            except midiimport.MidiImportError as exc:
                raise ValueError("{} could not be imported: {}.".format(os.path.basename(path), exc)) from None
        if not contents.tracks and not contents.chords:
            raise ValueError("{} has no notes to import.".format(os.path.basename(path)))
        empty = self.project_is_empty()
        if use_timeline is None:
            use_timeline = empty
        self._stop_engine_quietly()
        notes_said = list(contents.warnings)
        made = []
        with self.edit("import MIDI file"):
            song = self.song
            if empty and len(song.tracks) == 1 and not song.tracks[0].effects and not song.tracks[0].automation:
                song.tracks = []          # a new project's empty Piano track makes way
            if use_timeline:
                timeline, markers, moved = midiimport.build_timeline(contents)
                song.timeline = timeline
                end_bar = timeline.tick_to_bar(max(0, contents.end_tick - 1)) + 1
                song.sections = midiimport.sections_from_markers(markers, end_bar)
                notes_said += moved
                if contents.title and (not song.title or song.title == "Untitled"):
                    song.title = contents.title[:80]
            if contents.chords and (use_timeline or not song.chords):
                song.chords = list(contents.chords)      # Musician Forge's own chord track, back as the chord track
            room = MAX_TRACKS - len(song.tracks)
            if len(contents.tracks) > room:
                notes_said.append("{} of its tracks did not fit (a project has up to {} tracks)".format(
                    len(contents.tracks) - room, MAX_TRACKS))
            for item in contents.tracks[:max(0, room)]:
                instrument = (self._exact_preset(item.exact)
                              or self._preset_named(item.bank, item.program, item.drums))
                track = song.add_track(item.name or "MIDI track", instrument)
                track.notes = [Note(n.tick, n.length, n.pitch, n.velocity) for n in item.notes]
                track.sort_notes()
                if item.volume is not None:
                    track.volume = item.volume
                if item.pan is not None:
                    track.pan = item.pan
                for target, start, points in (("volume", item.volume, item.volume_points),
                                              ("pan", item.pan, item.pan_points)):
                    if points:
                        lane = automation.new_lane(target)
                        first = start if start is not None else (80 if target == "volume" else 0)
                        lane["points"] = [[0, first, False]] + [[int(t), v, False] for t, v in points if t > 0]
                        track.automation.append(lane)
                start, end = regions.bar_span(song.timeline, track.notes[0].tick, max(n.end for n in track.notes))
                regions.claim(track, start, end)
                made.append(track)
        self.selected_track_id = made[0].id if made else self.selected_track_id
        self._playhead = 0
        self.engine.locate(0)
        self.notify("selection")
        words = "Imported {}: {}, {} note{}".format(
            os.path.basename(path), self._count_words(len(made), "track"), sum(len(t.notes) for t in made),
            "" if sum(len(t.notes) for t in made) == 1 else "s")
        if use_timeline:
            tl = self.song.timeline
            words += ", {}, {}, {}, {}".format(
                self._count_words(len(tl.tempos), "tempo"), self._count_words(len(tl.time_signatures),
                                                                              "time signature"),
                self._count_words(len(tl.keys), "key"), self._count_words(len(self.song.sections), "section"))
        else:
            words += "; the project kept its own tempo, time signatures, keys and sections"
        words += "."
        if notes_said:
            words += " Note: " + "; ".join(notes_said) + "."
        log.info("Imported MIDI file %s: %s", path, words)
        self.announce(words)
        return words

    def _region(self, track_id, index):
        track = self.song.track_by_id(track_id)
        if track is None or not 0 <= index < len(track.regions):
            raise ValueError("That recording is not there any more")
        return track, track.regions[index]

    def describe_sections_between(self, start_tick, end_tick):
        """'Section 1', or 'Sections 1 to 3' (by name when sections have names: 'Verse to Chorus')."""
        tl = self.song.timeline
        first = self.song.section_index_at_bar(tl.tick_to_bar(start_tick))
        last = self.song.section_index_at_bar(tl.tick_to_bar(max(start_tick, end_tick - 1)))
        if first == last:
            return self.song.section_name(first)
        a, b = self.song.section_name(first), self.song.section_name(last)
        if a == "Section {}".format(first + 1) and b == "Section {}".format(last + 1):
            return "Sections {} to {}".format(first + 1, last + 1)
        return "{} to {}".format(a, b)

    def describe_region(self, track_id, index):
        """'Recording 1, Section 1: starts at bar 5, ends at bar 9 beat 3, 4 bars and 2 beats long,
        8.5 seconds, take 2 of 3, gain 0 dB'."""
        _track, region = self._region(track_id, index)
        tl = self.song.timeline
        end = region.end_tick(tl)
        text = "Recording {}, {}: {}, {}".format(index + 1, self.describe_sections_between(region.tick, end),
                                                 tl.describe_span(region.tick, end),
                                                 audiotracks.describe_seconds(region.frames))
        if len(region.takes) > 1:
            text += ", take {} of {}".format(region.active + 1, len(region.takes))
        text += ", " + audiotracks.describe_gain(region.gain_db)
        if region.take is not None and not os.path.isfile(self.audio_path(region.take.file)):
            text += ", file missing"
        return text

    def delete_region(self, track_id, index):
        if self.engine.recording:
            raise ValueError("Stop recording before deleting a recording")
        with self.edit("delete recording"):
            track, _region = self._region(track_id, index)
            del track.regions[index]
        self.announce("Recording deleted")

    def update_region(self, track_id, index, tick=None, take=None, gain_db=None):
        """Where a recording starts, which take plays, and its gain, as one undo step.
        Returns the recording's place in the track's list afterwards."""
        if self.engine.recording:
            raise ValueError("Stop recording before changing a recording")
        if gain_db is not None:
            gain_db = float(gain_db)
            if not audiotracks.GAIN_MIN_DB <= gain_db <= audiotracks.GAIN_MAX_DB:
                raise ValueError("Gain can go from {:g} to {:g} dB".format(audiotracks.GAIN_MIN_DB,
                                                                            audiotracks.GAIN_MAX_DB))
        if tick is not None and int(tick) < 0:
            raise ValueError("A recording cannot start before the beginning of the song")
        _track, region = self._region(track_id, index)
        if take is not None and not 0 <= int(take) < len(region.takes):
            raise ValueError("There is no take {}".format(int(take) + 1))
        with self.edit("recording settings"):
            track, region = self._region(track_id, index)
            if take is not None:
                region.active = int(take)
            if gain_db is not None:
                region.gain_db = gain_db
            if tick is not None:
                region.tick = int(tick)
                track.sort_regions()
            new_index = next(i for i, r in enumerate(track.regions) if r is region)
        self.announce(self.describe_region(track_id, new_index))
        return new_index

    def move_region(self, track_id, index, bar, beat=1.0):
        return self.update_region(track_id, index, tick=self.song.timeline.position_to_tick(int(bar), float(beat)))

    def set_region_gain(self, track_id, index, gain_db):
        return self.update_region(track_id, index, gain_db=gain_db)

    def choose_take(self, track_id, index, take_index):
        return self.update_region(track_id, index, take=take_index)

    def play_region(self, track_id, index):
        """Play from the start of a recording (or stop, if playing)."""
        if self.engine.recording:
            raise ValueError("Stop recording first")
        if self.engine.playing:
            self.stop(speak=False)
            return
        _track, region = self._region(track_id, index)
        if self.locate(region.tick, speak=False):
            self.toggle_play()

    # ------------------------------------------------------------------
    # regions: the stretches of a track (recordings on audio tracks), for
    # arranging with cut, copy, paste, duplicate, delete, split and join
    # ------------------------------------------------------------------
    def regions_of(self, track_id):
        track = self.song.track_by_id(track_id)
        if track is None:
            return []
        return track.regions if track.is_audio else track.note_regions

    def region_span(self, track_id, index):
        """(start tick, end tick) of a region or recording."""
        track = self.song.track_by_id(track_id)
        region = self.regions_of(track_id)[index]
        if track.is_audio:
            return region.tick, region.end_tick(self.song.timeline)
        return region.start, region.end

    def region_name(self, track_id, index):
        track = self.song.track_by_id(track_id)
        if track.is_audio:
            return "Recording"
        region = track.note_regions[index]
        if region.name:
            return region.name
        if region.player:
            from . import players

            settings = players.clean_settings(region.player)
            return "Rhythm player region: {}".format(players.describe_settings(settings)) if settings else \
                "Rhythm player region"
        return "{} region".format(track.name)

    def describe_region_item(self, track_id, index, number=True, current=None):
        """One line of the Regions list: '1. Piano region, Section 1: starts at bar 1, ends at bar 9,
        8 bars long, 24 notes' (recordings add their seconds, take and gain).

        current: the region you are on in the Regions list; it ends with ", selected". In selection mode
        the word belongs to the regions marked with Space instead."""
        track = self.song.track_by_id(track_id)
        tl = self.song.timeline
        start, end = self.region_span(track_id, index)
        text = "{}{}, {}: {}".format("{}. ".format(index + 1) if number else "", self.region_name(track_id, index),
                                     self.describe_sections_between(start, end), tl.describe_span(start, end))
        region = self.regions_of(track_id)[index]
        if track.is_audio:
            text += ", " + audiotracks.describe_seconds(region.frames)
            if len(region.takes) > 1:
                text += ", take {} of {}".format(region.active + 1, len(region.takes))
            text += ", " + audiotracks.describe_gain(region.gain_db)
            if region.take is not None and not os.path.isfile(self.audio_path(region.take.file)):
                text += ", file missing"
        elif region.player:
            from . import player_pieces, players

            settings = players.clean_settings(region.player)
            if settings:
                text += ", variation {} of {}".format(settings["variation"], players.variation_count(settings))
                if player_pieces.hand_made(settings):
                    text += ", hand-made steps"
        else:
            count = len(regions.notes_in(track, start, end))
            text += ", {} note{}".format(count, "" if count == 1 else "s")
        if region.loops != 1:
            from . import arrangement

            if track.is_audio:
                count, stop = arrangement.audio_region_repeats(track, index, tl, self.song.song_end_tick())
            else:
                count, stop = arrangement.note_region_repeats(track, index, self.song.song_end_tick())
            text += ", " + arrangement.loop_text(count, stop, tl, region.loops)
        if region.mute:
            text += ", muted"
        if self.is_selected_region(track_id, index, current):
            text += ", selected"
        return text

    def is_selected_track(self, track_id):
        """Whether a track's line ends with ", selected": the track you are on, or in selection mode every
        track marked with Space (so the word never means two things at once)."""
        if self.selecting:
            return track_id in self.selected_tracks
        return track_id is not None and track_id == self.selected_track_id

    def is_selected_region(self, track_id, index, current=None):
        """Whether a region's line ends with ", selected": the region you are on (current), or in selection
        mode every region marked with Space."""
        if self.selecting:
            return track_id == self.selected_track_id and index in self.selected_regions
        return current is not None and index == current

    def region_at_playhead(self, track_id):
        """The region the playhead is in on a track, or None."""
        tick = self.position_tick()
        for i in range(len(self.regions_of(track_id))):
            start, end = self.region_span(track_id, i)
            if start <= tick < end:
                return i
        return None

    # -- selection: Shift+F8 turns it on; then Space picks tracks or regions ---
    def toggle_selecting(self):
        self.selecting = not self.selecting
        self.selected_tracks.clear()
        self.selected_regions.clear()
        if self.selecting:
            self.announce("Selection on. Space selects or unselects the track or region you are on. "
                          "Cut, copy, paste, duplicate and delete then work on everything you selected. "
                          "Shift+F8 turns selection off.")
        else:
            self.announce("Selection off")
        self.notify("selection")

    def toggle_track_selected(self, track_id):
        track = self.song.track_by_id(track_id)
        if track is None:
            return
        if track_id in self.selected_tracks:
            self.selected_tracks.discard(track_id)
            state = "not selected"
        else:
            self.selected_tracks.add(track_id)
            state = "selected"
        count = len(self.selected_tracks)
        self.announce("{} {}. {} track{} selected".format(track.name, state, count, "" if count == 1 else "s"))
        self.notify("selection")

    def toggle_region_selected(self, index):
        if not 0 <= index < len(self.regions_of(self.selected_track_id)):
            return
        if index in self.selected_regions:
            self.selected_regions.discard(index)
            state = "not selected"
        else:
            self.selected_regions.add(index)
            state = "selected"
        count = len(self.selected_regions)
        self.announce("Region {} {}. {} region{} selected".format(index + 1, state, count,
                                                                  "" if count == 1 else "s"))
        self.notify("selection")

    def select_all(self, what):
        if what == "tracks":
            self.selected_tracks = {t.id for t in self.song.tracks}
            count, noun = len(self.selected_tracks), "track"
        else:
            self.selected_regions = set(range(len(self.regions_of(self.selected_track_id))))
            count, noun = len(self.selected_regions), "region"
        self.announce("{} {}{} selected".format(count, noun, "" if count == 1 else "s"))
        self.notify("selection")

    def tracks_for_action(self):
        """The selected tracks (in selection mode), or the current track."""
        if self.selecting and self.selected_tracks:
            return [t.id for t in self.song.tracks if t.id in self.selected_tracks]
        return [self.selected_track_id] if self.selected_track_id is not None else []

    def regions_for_action(self, current=None):
        """The selected regions (in selection mode), or the region you are on."""
        if self.selecting and self.selected_regions:
            return sorted(self.selected_regions)
        if current is None:
            current = self.region_at_playhead(self.selected_track_id)
        return [] if current is None else [current]

    def _after_region_change(self):
        self.selected_regions.clear()

    # -- whole tracks ------------------------------------------------------
    def copy_tracks(self, track_ids, speak=True):
        if not track_ids:
            raise ValueError("Choose a track first")
        self.clipboard = {"kind": "tracks", "tracks": [copy.deepcopy(self.song.track_by_id(t)) for t in track_ids]}
        if speak:
            self.announce("Copied {}".format(self._count_words(len(track_ids), "track")))

    def cut_tracks(self, track_ids):
        if len(track_ids) >= len(self.song.tracks):
            raise ValueError("A project keeps at least one track, so you can't cut them all. Copy them instead.")
        self.copy_tracks(track_ids, speak=False)
        self._delete_tracks(track_ids, "cut")
        self.announce("Cut {}".format(self._count_words(len(track_ids), "track")))

    def paste_tracks(self):
        if not self.clipboard or self.clipboard["kind"] != "tracks":
            raise ValueError("There are no copied tracks to paste")
        if self.engine.recording:
            raise ValueError("Stop recording before pasting")
        with self.edit("paste tracks"):
            index = self.song.index_of(self.selected_track_id) + 1 if self.selected_track_id else len(self.song.tracks)
            added = self._insert_track_copies(self.clipboard["tracks"], index)
        self.selected_track_id = added[0].id
        self.notify("selection")
        self.announce("Pasted {}".format(self._count_words(len(added), "track")))
        return added

    def duplicate_tracks(self, track_ids):
        if not track_ids:
            raise ValueError("Choose a track first")
        with self.edit("duplicate tracks"):
            originals = [copy.deepcopy(self.song.track_by_id(t)) for t in track_ids]
            index = max(self.song.index_of(t) for t in track_ids) + 1
            added = self._insert_track_copies(originals, index)
        self.selected_track_id = added[0].id
        self.notify("selection")
        self.announce("Duplicated {}".format(self._count_words(len(added), "track")))
        return added

    def delete_tracks(self, track_ids):
        if len(track_ids) == 1:
            self.delete_track(track_ids[0])
            return
        self._delete_tracks(track_ids, "delete")
        self.announce("Deleted {}".format(self._count_words(len(track_ids), "track")))

    def _delete_tracks(self, track_ids, label):
        if self.engine.recording:
            raise ValueError("Stop recording before removing tracks")
        index = min(self.song.index_of(t) for t in track_ids)
        with self.edit("{} tracks".format(label)):
            for track_id in track_ids:
                self.song.remove_track(track_id)
        self.selected_tracks.clear()
        self.selected_track_id = self.song.tracks[min(index, len(self.song.tracks) - 1)].id if self.song.tracks else None
        self.notify("selection")

    def _insert_track_copies(self, tracks, index):
        if len(self.song.tracks) + len(tracks) > MAX_TRACKS:
            raise ValueError("A project can have up to {} tracks".format(MAX_TRACKS))
        added = []
        for offset, original in enumerate(tracks):
            track = copy.deepcopy(original)
            track.id = self.song.next_track_id()
            track.solo = False
            self.song.tracks.insert(index + offset, track)
            added.append(track)
        return added

    def set_tracks_mute(self, track_ids):
        """Mute every chosen track, or unmute them all if the first is already muted."""
        tracks = [self.song.track_by_id(t) for t in track_ids]
        value = not tracks[0].mute
        with self.edit("mute"):
            for track in tracks:
                track.mute = value
        self.announce("{} {}".format("Muted" if value else "Unmuted", self._count_words(len(tracks), "track")))

    def set_tracks_solo(self, track_ids):
        tracks = [self.song.track_by_id(t) for t in track_ids]
        value = not tracks[0].solo
        with self.edit("solo"):
            for track in tracks:
                track.solo = value
        self.announce("Solo {} for {}".format("on" if value else "off", self._count_words(len(tracks), "track")))

    @staticmethod
    def _count_words(count, noun):
        return "{} {}{}".format(count, noun, "" if count == 1 else "s")

    # -- regions -------------------------------------------------------------
    def _need_regions(self, track_id, indices):
        if not indices:
            raise ValueError("There is no region here. Move to a region in the Regions list first.")
        if self.engine.recording:
            raise ValueError("Stop recording before changing regions")
        return self.song.track_by_id(track_id)

    def copy_regions(self, track_id, indices, speak=True):
        track = self._need_regions(track_id, indices)
        if track.is_audio:
            chosen = sorted((track.regions[i] for i in indices), key=lambda r: r.tick)
            first = chosen[0].tick
            self.clipboard = {"kind": "audio", "regions": [(r.tick - first, copy.deepcopy(r)) for r in chosen],
                              "end": max(r.end_tick(self.song.timeline) for r in chosen) - first}
        else:
            copies = regions.copy_regions(track, indices)
            self.clipboard = {"kind": "notes", "copies": copies,
                              "end": max(c.offset + c.length for c in copies)}
        if speak:
            self.announce("Copied {}".format(self._count_words(len(indices), "region")))

    def cut_regions(self, track_id, indices):
        self.copy_regions(track_id, indices, speak=False)
        with self.edit("cut regions"):
            self._remove_regions(self.song.track_by_id(track_id), indices)
        self._after_region_change()
        self.announce("Cut {}".format(self._count_words(len(indices), "region")))

    def delete_regions(self, track_id, indices):
        self._need_regions(track_id, indices)
        with self.edit("delete regions"):
            self._remove_regions(self.song.track_by_id(track_id), indices)
        self._after_region_change()
        self.announce("Deleted {}".format(self._count_words(len(indices), "region")))

    def _remove_regions(self, track, indices):
        if track.is_audio:
            chosen = [track.regions[i] for i in indices]
            track.regions = [r for r in track.regions if all(r is not c for c in chosen)]
        else:
            regions.delete_regions(track, indices)

    def paste_regions(self, track_id, tick=None):
        """Paste copied regions on a track at the playhead, replacing what was there.
        Returns the index of the first pasted region."""
        track = self.song.track_by_id(track_id)
        clip = self.clipboard
        if not clip or clip["kind"] not in ("notes", "audio"):
            raise ValueError("There are no copied regions to paste")
        if track is None:
            raise ValueError("Choose a track first")
        if clip["kind"] == "notes" and track.is_audio:
            raise ValueError("Regions with notes go on instrument tracks, and this is an audio track")
        if clip["kind"] == "audio" and not track.is_audio:
            raise ValueError("Recordings go on audio tracks, and this is an instrument track")
        if self.engine.recording:
            raise ValueError("Stop recording before pasting")
        tick = self.position_tick() if tick is None else int(tick)
        first = self._place_clipboard(track, clip, tick, "paste regions")
        self.announce("Pasted {} at {}".format(self._count_words(self._clip_count(clip), "region"),
                                              self.describe_position(tick)))
        return first

    def duplicate_regions(self, track_id, indices):
        """Copies of the regions right after the last one."""
        track = self._need_regions(track_id, indices)
        saved = self.clipboard
        try:
            self.copy_regions(track_id, indices, speak=False)
            clip = self.clipboard
            starts = [self.region_span(track_id, i)[0] for i in indices]
            ends = [self.region_span(track_id, i)[1] for i in indices]
            at = min(starts) + (max(ends) - min(starts))
            first = self._place_clipboard(track, clip, at, "duplicate regions")
        finally:
            self.clipboard = saved
        self.announce("Duplicated {}, starting at {}".format(self._count_words(len(indices), "region"),
                                                             self.describe_position(at)))
        return first

    def move_regions(self, track_id, indices, bar, beat=1.0):
        """Move regions so the first starts at bar and beat (what was there is replaced)."""
        track = self._need_regions(track_id, indices)
        tick = self.song.timeline.position_to_tick(int(bar), float(beat))
        saved = self.clipboard
        try:
            self.copy_regions(track_id, indices, speak=False)
            clip = self.clipboard
            with self.edit("move regions"):
                self._remove_regions(track, indices)
                first = self._paste_into(self.song.track_by_id(track_id), clip, tick)
        finally:
            self.clipboard = saved
        self._after_region_change()
        self.announce("Moved {} to {}".format(self._count_words(len(indices), "region"), self.describe_position(tick)))
        return first

    def _place_clipboard(self, track, clip, tick, label):
        with self.edit(label):
            first = self._paste_into(self.song.track_by_id(track.id), clip, tick)
        self._after_region_change()
        return first

    def _paste_into(self, track, clip, tick):
        if clip["kind"] == "notes":
            placed = regions.paste_regions(track, clip["copies"], tick)
            self.song.tidy_regions()
            return next(i for i, r in enumerate(track.note_regions) if r is placed[0])
        placed = []
        for offset, region in clip["regions"]:
            new = copy.deepcopy(region)
            new.tick = tick + offset
            new.layer = track.top_layer()
            track.regions.append(new)
            placed.append(new)
        track.sort_regions()
        return next(i for i, r in enumerate(track.regions) if r is placed[0])

    @staticmethod
    def _clip_count(clip):
        return len(clip["copies"]) if clip["kind"] == "notes" else len(clip["regions"])

    def toggle_regions_mute(self, track_id, indices):
        self._need_regions(track_id, indices)
        items = self.regions_of(track_id)
        value = not items[indices[0]].mute
        with self.edit("mute regions"):
            items = self.regions_of(track_id)
            for i in indices:
                items[i].mute = value
        self.announce("{} {}".format("Muted" if value else "Unmuted", self._count_words(len(indices), "region")))

    def split_region(self, track_id, index, tick=None):
        """Split a region in two at the playhead. Returns the second part's index."""
        track = self._need_regions(track_id, [index] if index is not None else [])
        if track.is_audio:
            raise ValueError("Splitting recordings comes in a later version. You can split regions on "
                             "instrument tracks.")
        tick = self.position_tick() if tick is None else int(tick)
        with self.edit("split region"):
            second = regions.split_region(self.song.track_by_id(track_id), index, tick)
        self._after_region_change()
        self.announce("Split at {}. {}".format(self.describe_position(tick),
                                               self.describe_region_item(track_id, second)))
        return second

    def join_regions(self, track_id, indices):
        track = self._need_regions(track_id, indices)
        if track.is_audio:
            raise ValueError("Joining recordings comes in a later version. You can join regions on "
                             "instrument tracks.")
        with self.edit("join regions"):
            joined = regions.join_regions(self.song.track_by_id(track_id), indices)
        self._after_region_change()
        self.announce("Joined. {}".format(self.describe_region_item(track_id, joined)))
        return joined

    def rename_region(self, track_id, index, name):
        track = self._need_regions(track_id, [index])
        if track.is_audio:
            raise ValueError("Recordings are named by where they start. You can rename regions on "
                             "instrument tracks.")
        with self.edit("rename region"):
            self.song.track_by_id(track_id).note_regions[index].name = name.strip()
        self.announce("Renamed to {}".format(self.region_name(track_id, index)))

    # ------------------------------------------------------------------
    # effects: each track's list, top to bottom, before its volume and pan
    # ------------------------------------------------------------------
    def effects_of(self, track_id):
        track = self.song.track_by_id(track_id)
        return track.effects if track is not None else []

    def _effect_track(self, track_id, index=None):
        track = self.song.track_by_id(track_id)
        if track is None:
            raise ValueError("Choose a track first")
        if index is not None and not 0 <= index < len(track.effects):
            raise ValueError("That effect is not there any more")
        return track

    def effect_types_for(self, track_id):
        track = self._effect_track(track_id)
        return effects.types_for(effects.AUDIO if track.is_audio else effects.INSTRUMENT)

    def describe_effect(self, track_id, index, number=True):
        effect = self._effect_track(track_id, index).effects[index]
        return effects.describe_effect(effect, index + 1 if number else None)

    def add_effect(self, track_id, type_key, preset=None):
        """Add an effect at the end of the track's list (pitch correction always goes first).
        Returns its place in the list."""
        track = self._effect_track(track_id)
        kind = effects.TYPE_BY_KEY.get(type_key)
        if kind is None:
            raise ValueError("Unknown effect")
        if (effects.AUDIO if track.is_audio else effects.INSTRUMENT) not in kind.kinds:
            raise ValueError("{} is for recordings, so it goes on audio tracks.".format(kind.name))
        if len(track.effects) >= effects.MAX_EFFECTS:
            raise ValueError("A track can have up to {} effects".format(effects.MAX_EFFECTS))
        if type_key == "pitch" and any(e["type"] == "pitch" for e in track.effects):
            raise ValueError("This track already has pitch correction. Open it to change its settings.")
        effect = effects.new_effect(type_key, preset)
        with self.edit("add {}".format(kind.name)):
            track = self.song.track_by_id(track_id)
            if type_key == "pitch":
                track.effects.insert(0, effect)
                index = 0
            else:
                track.effects.append(effect)
                index = len(track.effects) - 1
            effects.ensure_ids(track.effects)
        text = "Added {} to {}".format(effects.describe_effect(effect), track.name)
        if type_key == "pitch":
            text += ". " + self._pitch_report(track_id)
        self.announce(text)
        return index

    def remove_effect(self, track_id, index):
        track = self._effect_track(track_id, index)
        name = effects.TYPE_BY_KEY[track.effects[index]["type"]].name
        with self.edit("remove {}".format(name)):
            target = self.song.track_by_id(track_id)
            removed = target.effects.pop(index)
            self._drop_lanes_for_effect(target, removed.get("id"))       # its automation goes with it
        self.announce("Removed {}. {}".format(name, self._count_words(len(self.effects_of(track_id)), "effect")))

    def move_effect(self, track_id, index, delta):
        """Move an effect up or down the list. Returns its new place."""
        track = self._effect_track(track_id, index)
        target = index + delta
        if not 0 <= target < len(track.effects):
            self.announce("Already {}".format("first" if delta < 0 else "last"))
            return index
        if "pitch" in (track.effects[index]["type"], track.effects[target]["type"]):
            self.announce("Pitch correction always comes first")
            return index
        with self.edit("move effect"):
            items = self.song.track_by_id(track_id).effects
            items.insert(target, items.pop(index))
        self.announce("{}, now {} of {}".format(self.describe_effect(track_id, target, number=False), target + 1,
                                                len(self.effects_of(track_id))))
        return target

    def set_effect_on(self, track_id, index, on=None):
        """Turn an effect on or off (None switches it). Off keeps its settings."""
        track = self._effect_track(track_id, index)
        value = (not track.effects[index].get("on", True)) if on is None else bool(on)
        with self.edit("turn effect {}".format("on" if value else "off")):
            self.song.track_by_id(track_id).effects[index]["on"] = value
        self.announce(self.describe_effect(track_id, index, number=False))

    def update_effect(self, track_id, index, params=None, preset=None, on=None):
        """The effect settings window's OK: every change as one undo step."""
        track = self._effect_track(track_id, index)
        kind = effects.TYPE_BY_KEY[track.effects[index]["type"]]
        if preset is not None and preset not in kind.preset_names():
            raise ValueError("Unknown preset")
        cleaned = None
        if params is not None:
            cleaned = dict(track.effects[index]["params"])
            for p in kind.params:
                if p.key in params:
                    cleaned[p.key] = p.clamp(params[p.key])
        self._effect_preview.pop(track_id, None)
        if self._writing() and cleaned is not None:
            # moved while writing: those settings went into the automation, the effect's own stay
            current = track.effects[index]["params"]
            for p in kind.params:
                if p.automatable:
                    cleaned[p.key] = current[p.key]
            if cleaned == current and (on is None or bool(on) == track.effects[index].get("on", True)):
                self._sync_engine()
                self.announce("{} changes were written into the automation".format(kind.name))
                return
        with self.edit("{} settings".format(kind.name)):
            effect = self.song.track_by_id(track_id).effects[index]
            if preset is not None:
                effect["preset"] = preset
            if cleaned is not None:
                effect["params"] = cleaned
            if on is not None:
                effect["on"] = bool(on)
        text = "{} settings saved. {}".format(kind.name, self.describe_effect(track_id, index, number=False))
        if kind.key == "pitch":
            text += ". " + self._pitch_report(track_id)
        self.announce(text)

    def preview_effect(self, track_id, index, params=None, on=None):
        """Hear changed settings straight away while the settings window is open (no undo step yet).
        Pitch correction is worked out for whole recordings, so it is heard after OK."""
        track = self._effect_track(track_id, index)
        if track.effects[index]["type"] == "pitch":
            return
        trial = effects.copy_effects(track.effects)
        kind = effects.TYPE_BY_KEY[trial[index]["type"]]
        if params is not None:
            for p in kind.params:
                if p.key in params:
                    trial[index]["params"][p.key] = p.clamp(params[p.key])
        if on is not None:
            trial[index]["on"] = bool(on)
        if self._writing() and params is not None:
            # Write automation: a setting moved while the song plays is written at the moment heard
            before = self._effect_preview.get(track_id, track.effects)[index]["params"]
            for p in kind.params:
                if p.automatable and p.key in params and trial[index]["params"][p.key] != before.get(p.key):
                    self.write_automation(track_id, ("effect", track.effects[index].get("id"), p.key),
                                          trial[index]["params"][p.key], speak=False)
        self._effect_preview[track_id] = trial
        self._sync_engine()

    def end_effect_preview(self):
        """Cancel in the settings window: back to the saved settings."""
        if self._effect_preview:
            self._effect_preview.clear()
            self._sync_engine()

    # -- pitch correction (worked out for each recording, then cached) --------
    def _pitch_effect(self, track):
        for effect in getattr(track, "effects", []):
            if effect["type"] == "pitch" and effect.get("on", True):
                return effect
        return None

    def _key_spans(self, region, frames):
        """The song's keys during a recording: [(first sample, allowed pitch classes)]."""
        tl = self.song.timeline
        start_seconds = tl.tick_to_seconds(region.tick)
        spans = []
        for change in tl.keys:
            offset = int(round((tl.tick_to_seconds(tl.bar_to_tick(change.bar)) - start_seconds) * AUDIO_RATE))
            if offset >= frames:
                break
            classes = frozenset(theory.scale_pitch_classes(change.tonic, change.scale))
            if offset <= 0 or not spans:
                spans = [(0, classes)]      # the key in force when the recording starts
            else:
                spans.append((offset, classes))
        if not spans:
            key = tl.key_at_tick(region.tick)
            spans = [(0, frozenset(theory.scale_pitch_classes(key.tonic, key.scale)))]
        return tuple(spans)

    def _take_audio(self, track, region):
        """A recording as it should play: pitch-corrected when the track has pitch correction on."""
        take = region.take
        data = self.load_audio(take.file) if take is not None else None
        if data is None or not len(data):
            return data
        effect = self._pitch_effect(track)
        if effect is None:
            return data
        spans = self._key_spans(region, len(data))
        params = effect["params"]
        key = (os.path.normcase(self.audio_path(take.file)), tuple(sorted(params.items())), spans)
        corrected = self._corrected.get(key)
        if corrected is None:
            starts = [start for start, _classes in spans]

            def allowed_at(sample):
                i = max(0, np.searchsorted(starts, sample, side="right") - 1)
                return spans[i][1]

            started = time.perf_counter()
            try:
                corrected = pitchfix.correct(data, AUDIO_RATE, params, allowed_at)
            except Exception:  # noqa: BLE001 - a recording that cannot be corrected plays as recorded; an error
                log.exception("Pitch correction failed for %s; it plays as recorded", take.file)   # here used to
                corrected = data                     # stop every change to the project from reaching the sound
            log.info("Pitch corrected %s in %.1f seconds", take.file, time.perf_counter() - started)
            if len(self._corrected) > 64:
                self._corrected.clear()
            self._corrected[key] = corrected
        return corrected

    def _pitch_report(self, track_id):
        """'Pitch correction found a clear pitch in 2 of 3 recordings.' (said after it is applied)."""
        track = self.song.track_by_id(track_id)
        if track is None or not track.is_audio:
            return ""
        effect = self._pitch_effect(track)
        if effect is None:
            return "Pitch correction is off"
        recordings = [r for r in track.regions if r.take is not None]
        if not recordings:
            return "It will correct the recordings you make on this track"
        clear = 0
        for region in recordings:
            data = self.load_audio(region.take.file)
            if data is None:
                continue
            voiced, total = pitchfix.summary(data, AUDIO_RATE)
            if total and voiced >= 0.1 * total:
                clear += 1
        return "Pitch correction found a clear pitch in {} of {} recording{}".format(
            clear, len(recordings), "" if len(recordings) == 1 else "s")

    # ------------------------------------------------------------------
    # measuring the recording delay (Options, Audio settings)
    # ------------------------------------------------------------------
    def measure_recording_delay(self, done):
        """Play clicks through the speakers and listen with the microphone (see latency.py).
        done(Measurement) is called when it has finished (from poll())."""
        if self.engine.playing or self.engine.recording:
            raise ValueError("Stop playing before measuring the recording delay")
        if self.audio_input is None:
            raise ValueError("Measuring the recording delay needs a microphone. Choose one in Audio settings.")
        if not self.audio_is_live:
            raise ValueError("Measuring the recording delay needs the sound card to be working. "
                             "Check the output device in Audio settings.")
        try:
            self.audio_input.ensure_open(1)
        except Exception as exc:  # noqa: BLE001
            raise ValueError("The microphone could not be opened. {}".format(exc)) from None
        self._measure_done = done
        self.engine.set_monitoring(False)
        self.engine.measure_delay()
        log.info("Measuring the recording delay")

    def _finish_measurement(self, first, audio, clicks):
        done, self._measure_done = self._measure_done, None
        if self.audio_input is not None and not self.engine.recording:
            try:
                self.audio_input.release()
            except Exception:  # noqa: BLE001
                log.exception("Closing the microphone failed")
        result = latency.measure(first, audio, clicks, self.engine.sample_rate)
        self.last_measurement = result
        log.info("Recording delay measured: %s (clicks heard %d of %d, delays %s ms)", result.describe(),
                 result.found, result.clicks, ", ".join("{:.1f}".format(d) for d in result.delays_ms))
        if done is not None:
            done(result)
        else:
            self.announce(result.describe())

    # ------------------------------------------------------------------
    # musical typing
    # ------------------------------------------------------------------
    def current_key(self):
        return self.song.timeline.key_at_tick(self.position_tick())

    def is_drum_track(self):
        track = self.selected_track
        return bool(track and track.instrument.is_drum_kit)

    def key_down(self, char, timestamp=None):
        """A key went down in the musical typing area. Returns True if it was used."""
        char = (char or "").lower()
        if not char:
            return False
        track = self.selected_track
        drums = self.is_drum_track()
        if char in self._held:
            return True  # keyboard auto-repeat
        if track is not None and track.is_audio and km.is_note_key(char, mode=self.typing.mode):
            message = "{} is an audio track. Press R to record from the microphone.".format(track.name)
            if self.last_announcement != message:
                self.announce(message)
            return True
        notes = ()
        if track is not None:
            notes = self.typing.notes_for_key(char, self.current_key(), drums)
        if notes:
            channel = self.channel_of(track.id)
            stamp = timestamp if timestamp is not None else time.perf_counter()
            via_arp = self.arp["on"]
            self._held[char] = (channel, notes, via_arp)
            if via_arp:
                self._send_arp_hold(channel, stamp)
            else:
                for note in notes:
                    self.engine.note_on(channel, note, self.typing.velocity, stamp)
            if self.settings is not None and self.settings["announce_note_names"]:
                self.announce(self._name_of_key(char, notes, drums))
            return True
        if char == "z":
            if self.typing.octave_down():
                self.announce("Octave {}".format(self.typing.octave))
            else:
                self.announce("Lowest octave")
            return True
        if char == "x":
            if self.typing.octave_up():
                self.announce("Octave {}".format(self.typing.octave))
            else:
                self.announce("Highest octave")
            return True
        if char == "c":
            self.typing.velocity_down()
            self.announce("Velocity {}".format(self.typing.velocity))
            return True
        if char == "v":
            self.typing.velocity_up()
            self.announce("Velocity {}".format(self.typing.velocity))
            return True
        if char == "b":
            self.toggle_layout()
            return True
        return False

    def key_up(self, char, timestamp=None):
        char = (char or "").lower()
        held = self._held.pop(char, None)
        if held is None:
            return False
        channel, notes, via_arp = held
        stamp = timestamp if timestamp is not None else time.perf_counter()
        if via_arp:
            self._send_arp_hold(channel, stamp)
        else:
            # a note another key still holds keeps sounding: chord strips share notes (C major and A minor both
            # have C and E), and letting go of the old chord after the new one went down cut them (the review of
            # 9 Oct 2026), live and in the recording
            still_held = {n for ch, held_notes, arp in self._held.values() if ch == channel and not arp
                          for n in held_notes}
            for note in notes:
                if note not in still_held:
                    self.engine.note_off(channel, note, stamp)
        return True

    def _send_arp_hold(self, channel, stamp):
        """Tell the arpeggiator every note held now, in the order the keys went down."""
        notes = []
        for held_channel, held_notes, via_arp in self._held.values():
            if via_arp and held_channel == channel:
                notes.extend(n for n in held_notes if n not in notes)
        self.engine.arp_hold(channel, notes, self.typing.velocity, stamp)

    def _name_of_key(self, char, notes, drums):
        if drums:
            return km.drum_name(notes[0], self.selected_track.instrument.program)
        chord = self.typing.chord_for_key(char, self.current_key())
        if chord is not None:
            if char in km.BASS_KEYS:
                return "{} bass".format(theory.spoken_note_name(notes[0], chord.flats))
            return theory.chord_name(chord)
        return theory.spoken_note_name(notes[0], self._flats())

    def _release_held_keys(self):
        now = time.perf_counter()
        arp_channels = set()
        for channel, notes, via_arp in self._held.values():
            if via_arp:
                arp_channels.add(channel)
            else:
                for note in notes:
                    self.engine.note_off(channel, note, now)
        self._held.clear()
        for channel in arp_channels:
            self.engine.arp_hold(channel, (), self.typing.velocity, now)

    def release_all_keys(self):
        """Call when the keyboard area loses focus, so no note hangs."""
        self._release_held_keys()

    # -- keyboard controls (also reachable with Tab in the main window) -------
    def toggle_layout(self):
        """B key: piano, scale, chord strips, then piano again."""
        if self.is_drum_track():
            self.announce("Drum layout. Drum kits always use the drum layout.")
            return
        modes = km.MODES
        mode = modes[(modes.index(self.typing.mode) + 1) % len(modes)] if self.typing.mode in modes else km.MODE_PIANO
        self.set_layout(mode)

    def set_layout(self, mode, speak=True):
        """Piano, scale or chord strips. Drum kits always use the drum layout."""
        if mode not in km.MODES:
            raise ValueError("Unknown keyboard layout")
        if self.is_drum_track():
            if speak:
                self.announce("Drum layout. Drum kits always use the drum layout.")
            return False
        self._release_held_keys()
        self.typing.mode = mode
        self._save_setting("keyboard_layout", mode)
        if speak:
            self.announce(self.describe_layout())
        self.notify("keyboard")
        return True

    def set_keyboard_scale(self, scale, speak=False):
        """The scale for the Scale and Chord strips layouts. Empty: follow the song's key."""
        scale = scale if scale in theory.SCALE_NAMES else ""
        self._release_held_keys()
        self.typing.scale = scale
        self._save_setting("keyboard_scale", scale)
        if speak:
            self.announce(self.describe_keyboard_scale())
        self.notify("keyboard")

    def set_octave(self, octave, speak=False):
        if not self.typing.set_octave(octave):
            raise ValueError("The octave can go from {} to {}".format(km.OCTAVES[0], km.OCTAVES[-1]))
        if speak:
            self.announce("Octave {}".format(self.typing.octave))
        self.notify("keyboard")

    def set_velocity(self, velocity, speak=False):
        self.typing.set_velocity(velocity)
        if speak:
            self.announce("Velocity {}".format(self.typing.velocity))
        self.notify("keyboard")

    def set_arpeggiator(self, on=None, pattern=None, rate=None, octaves=None, speak=False):
        """Turn the arpeggiator on or off, or change its pattern, speed or octave range."""
        if pattern is not None and pattern not in arpeggiator.PATTERNS:
            raise ValueError("Unknown arpeggiator pattern")
        if rate is not None and rate not in arpeggiator.RATE_NAMES:
            raise ValueError("Unknown arpeggiator speed")
        if octaves is not None and not 1 <= int(octaves) <= arpeggiator.MAX_OCTAVES:
            raise ValueError("The arpeggiator can span 1 to {} octaves".format(arpeggiator.MAX_OCTAVES))
        self._release_held_keys()  # held keys were started the old way; let them go cleanly
        for key, value in (("on", on), ("pattern", pattern), ("rate", rate), ("octaves", octaves)):
            if value is not None:
                self.arp[key] = bool(value) if key == "on" else (int(value) if key == "octaves" else value)
        self._save_setting("arpeggiator", dict(self.arp))
        self.engine.set_arpeggiator(self._arp_settings())
        if speak:
            self.announce(self.describe_arpeggiator())
        self.notify("keyboard")

    def toggle_arpeggiator(self):
        self.set_arpeggiator(on=not self.arp["on"], speak=True)

    def describe_arpeggiator(self):
        if not self.arp["on"]:
            return "Arpeggiator off"
        return "Arpeggiator on, {}".format(arpeggiator.describe(self.arp["pattern"], self.arp["rate"],
                                                                 self.arp["octaves"]))

    def describe_keyboard_scale(self):
        key = self.current_key()
        if not self.typing.scale:
            return "Scale follows the song's key, {}".format(key.name())
        return "Scale {}".format(theory.key_name(key.tonic, self.typing.scale))

    def describe_layout(self):
        if self.is_drum_track():
            return "Drum layout"
        key = self.current_key()
        scale = self.typing.scale_for(key)
        if self.typing.mode == km.MODE_SCALE:
            return "Scale layout, {}".format(theory.key_name(key.tonic, scale))
        if self.typing.mode == km.MODE_CHORDS:
            return "Chord strips, {}".format(theory.key_name(key.tonic, scale))
        return "Piano layout"

    def describe_chord_strips(self):
        """Which chord each key plays right now (the key's chords follow key changes; your own stay as you set them)."""
        key = self.current_key()
        if self.song.strips:
            return "Your own chord strips. {}".format(km.describe_chord_strips(self.typing.chords_for(key)))
        return "Chord strips in {}. {}".format(theory.key_name(key.tonic, self.typing.scale_for(key)),
                                              km.describe_chord_strips(self.typing.chords_for(key)))

    # -- your own chord strips (Russell, 10 Oct 2026) ----------------------
    def chord_strip_entries(self):
        """The 8 strips as [root, chord type, bass or None]: yours, or the key's at the playhead."""
        if self.song.strips:
            return [list(e) for e in self.song.strips]
        found = []
        for chord in self.typing.chords_for(self.current_key()):
            found.append([chord.root % 12, chords_module.quality_of(chord.intervals), None])
        return found

    def chord_strip_words(self, index):
        """'A: C major' for strip `index` (0 to 7)."""
        chord = self.typing.chords_for(self.current_key())[index]
        return "{}: {}".format(km.CHORD_KEYS[index].upper(), km.strip_name(chord))

    def set_chord_strip(self, index, root, quality, bass=None):
        """Your own chord on strip `index` (0 to 7, the keys A to K). The first one you set starts the other seven
        from the key's chords, so they keep playing what they did. One undo step."""
        if not 0 <= index < 8:
            raise ValueError("There are 8 chord strips")
        if quality not in chords_module.QUALITY_KEYS:
            raise ValueError("Unknown chord type")
        entries = self.chord_strip_entries()
        entries[index] = [int(root) % 12, quality, None if bass is None or int(bass) % 12 == int(root) % 12
                          else int(bass) % 12]
        with self.edit("chord strip"):
            self.song.strips = entries
        text = self.chord_strip_words(index)
        self.announce(text)
        return text

    def reset_chord_strips(self):
        """Back to the key's own chords (they follow key changes again). One undo step."""
        if not self.song.strips:
            self.announce("The chord strips already follow the song's key")
            return
        with self.edit("chord strips"):
            self.song.strips = None
        self.announce("The chord strips follow the song's key again")

    def preview_chord_strip(self, index):
        """Play strip `index` on the selected track's instrument."""
        chord = self.typing.chords_for(self.current_key())[index]
        track = self.selected_track
        bank, program = (track.instrument.bank, track.instrument.program) if track is not None and \
            not track.is_audio and not track.instrument.is_drum_kit else (0, 0)
        self.engine.set_channel_instrument(PREVIEW_CHANNEL, bank, program, False)
        for pitch in self.typing.chord_voicing(chord):
            self.engine.audition(PREVIEW_CHANNEL, pitch, 96, seconds=0.9)

    def describe_keyboard(self):
        text = "{}. {}. Velocity {}.".format(self.describe_layout(), self.typing.describe_octave(),
                                             self.typing.velocity)
        if self.arp["on"]:
            text += " {}.".format(self.describe_arpeggiator())
        return text

    def _flats(self):
        key = self.current_key()
        return theory.key_prefers_flats(key.tonic, key.scale)

    # ------------------------------------------------------------------
    # tempo, time signature and key changes
    # ------------------------------------------------------------------
    def set_tempo(self, bar, beat, bpm):
        with self.edit("tempo change"):
            self.song.timeline.set_tempo(bar, beat, bpm)
        self.announce("Tempo {} at bar {}".format(format_number(bpm), bar))

    # kind: (the timeline's list, its remove method, its set method, the undo label)
    _CHANGE_KINDS = {"tempo": ("tempos", "remove_tempo", "set_tempo", "tempo change"),
                     "time": ("time_signatures", "remove_time_signature", "set_time_signature",
                              "time signature change"),
                     "key": ("keys", "remove_key", "set_key", "key change")}

    def edit_change(self, kind, index, values):
        """Change the tempo, time signature or key change at index (kind "tempo", "time" or "key") to values, which
        may move it to another bar (or beat): one undo step, and a change that is refused leaves the old one where
        it was. (Before 9 Oct 2026 the old one was removed first, as a step of its own, and stayed removed when its
        new place was refused; trying again then removed the next one.)"""
        attr, remove, put, label = self._CHANGE_KINDS[kind]
        old = getattr(self.song.timeline, attr)[index]
        moved = (values[0], values[1]) != (old.bar, old.beat) if kind == "tempo" else values[0] != old.bar
        lost = 0
        with self.edit(label):
            timeline = self.song.timeline
            before = copy.deepcopy(timeline)
            if moved and index > 0:
                getattr(timeline, remove)(index)
            getattr(timeline, put)(*values)
            if kind == "time":
                lost = meterchange.keep_bars(self.song, before)      # every section keeps its bars
        if kind == "tempo":
            self.announce("Tempo {} at bar {}".format(format_number(values[2]), values[0]))
        elif kind == "time":
            self.announce("{} {} time from bar {}{}".format(values[1], values[2], values[0], self._lost_words(lost)))
        else:
            self.announce("{} from bar {}".format(theory.key_name(values[1], values[2]), values[0]))

    def remove_tempo(self, index):
        with self.edit("remove tempo change"):
            self.song.timeline.remove_tempo(index)
        self.announce("Tempo change removed")

    def set_time_signature(self, bar, numerator, denominator):
        """A time signature from `bar`: every section keeps its number of bars, and everything in them keeps its bar
        and its place in the bar (meterchange.py; Russell, 10 Oct 2026)."""
        with self.edit("time signature change"):
            before = copy.deepcopy(self.song.timeline)
            self.song.timeline.set_time_signature(bar, numerator, denominator)
            lost = meterchange.keep_bars(self.song, before)
        self.announce("{} {} time from bar {}{}".format(numerator, denominator, bar, self._lost_words(lost)))

    def remove_time_signature(self, index):
        with self.edit("remove time signature change"):
            before = copy.deepcopy(self.song.timeline)
            self.song.timeline.remove_time_signature(index)
            lost = meterchange.keep_bars(self.song, before)
        self.announce("Time signature change removed" + self._lost_words(lost))

    @staticmethod
    def _lost_words(lost):
        if not lost:
            return ""
        return ". {} note{} on beats the shorter bars do not have {} left out; Control+Z brings {} back".format(
            lost, "" if lost == 1 else "s", "was" if lost == 1 else "were", "it" if lost == 1 else "them")

    def set_key(self, bar, tonic, scale):
        with self.edit("key change"):
            self.song.timeline.set_key(bar, tonic, scale)
        self.announce("{} from bar {}".format(theory.key_name(tonic, scale), bar))

    def remove_key(self, index):
        with self.edit("remove key change"):
            self.song.timeline.remove_key(index)
        self.announce("Key change removed")

    def rename_song(self, title):
        title = (title or "").strip() or "Untitled"
        with self.edit("rename song"):
            self.song.title = title
        self.notify("title")

    # ------------------------------------------------------------------
    # notes (event list)
    # ------------------------------------------------------------------
    def describe_note(self, note, track_id=None):
        tl = self.song.timeline
        track = self.song.track_by_id(track_id if track_id is not None else self.selected_track_id)
        if track is not None and track.instrument.is_drum_kit:
            name = km.drum_name(note.pitch, track.instrument.program)
        else:
            key = tl.key_at_tick(note.tick)
            name = theory.spoken_note_name(note.pitch, theory.key_prefers_flats(key.tonic, key.scale))
        from .timeline import describe_length

        return "{}: {}, velocity {}, {}".format(tl.describe_position(note.tick), name, note.velocity,
                                                describe_length(note.length))

    def add_note(self, track_id, note):
        _validate_note(note)
        with self.edit("add note"):
            track = self.song.track_by_id(track_id)
            track.notes.append(note)
            track.sort_notes()
        return self.song.track_by_id(track_id).notes.index(note)

    def update_note(self, track_id, index, new_note):
        _validate_note(new_note)
        with self.edit("edit note"):
            track = self.song.track_by_id(track_id)
            track.notes[index] = new_note
            track.sort_notes()
        return self.song.track_by_id(track_id).notes.index(new_note)

    def delete_notes(self, track_id, indices):
        indices = sorted(set(indices))
        if not indices:
            return
        with self.edit("delete {} note{}".format(len(indices), "" if len(indices) == 1 else "s")):
            track = self.song.track_by_id(track_id)
            for i in reversed(indices):
                del track.notes[i]
        self.announce("Deleted {} note{}".format(len(indices), "" if len(indices) == 1 else "s"))

    def transpose_notes(self, track_id, indices, semitones):
        """Move notes up or down. Returns their new positions in the sorted list."""
        track = self.song.track_by_id(track_id)
        chosen = [track.notes[i] for i in sorted(set(indices))]
        if not chosen:
            return []
        if any(not 0 <= n.pitch + semitones <= 127 for n in chosen):
            self.announce("That would go outside the playable range")
            return sorted(set(indices))
        with self.edit("transpose"):
            track = self.song.track_by_id(track_id)
            moved = [track.notes[i] for i in sorted(set(indices))]
            for note in moved:
                note.pitch += semitones
            track.sort_notes()
        track = self.song.track_by_id(track_id)
        ids = {id(n) for n in moved}
        return [i for i, n in enumerate(track.notes) if id(n) in ids]

    def quantize(self, track_ids, grid_ticks, strength=1.0, lengths=False, note_indices=None):
        """Quantize whole tracks, or only `note_indices` of a single track."""
        count = 0
        with self.edit("quantize"):
            for track_id in track_ids:
                track = self.song.track_by_id(track_id)
                if note_indices is None:
                    track.notes = quantize_notes(track.notes, grid_ticks, self.song.timeline, strength, lengths)
                    count += len(track.notes)
                else:
                    chosen = set(note_indices)
                    picked = [n for i, n in enumerate(track.notes) if i in chosen]
                    rest = [n for i, n in enumerate(track.notes) if i not in chosen]
                    done = quantize_notes(picked, grid_ticks, self.song.timeline, strength, lengths)
                    track.notes = rest + done
                    track.sort_notes()
                    count += len(done)
        self.announce("Quantized {} note{}".format(count, "" if count == 1 else "s"))
        return count

    def audition_note(self, track_id, note):
        self.engine.audition(self.channel_of(track_id), note.pitch, note.velocity,
                             seconds=min(1.0, max(0.15, self.song.timeline.tick_to_seconds(note.end)
                                                  - self.song.timeline.tick_to_seconds(note.tick))))

    # ------------------------------------------------------------------
    # export
    # ------------------------------------------------------------------
    def export_midi(self, path):
        """The whole song as one MIDI file (Russell, 10 Oct 2026: one file, not a zip, so each track can be
        changed in the other program): every track with notes, rhythm players included, and the chord track."""
        if not path.lower().endswith((".mid", ".midi")):
            path += ".mid"
        size = midifile.export_midi(self.song, path, self.all_sounding_notes())
        log.info("Exported MIDI: %s (%d bytes)", path, size)
        self.announce(self.midi_export_words(path))
        return path, size

    def midi_export_words(self, path):
        """What to say when a MIDI export is done: "Export finished. Song.mid in ...: 4 tracks and the chord
        track." """
        notes = self.all_sounding_notes()
        count = sum(1 for t in self.song.tracks if not t.is_audio and notes.get(t.id))
        words = "Export finished. {} in {}: {} track{}{}.".format(
            os.path.basename(path), projects.describe_file_location(path), count, "" if count == 1 else "s",
            " and the chord track" if self.song.chords else "")
        if any(t.is_audio and t.regions for t in self.song.tracks):
            words += " Audio tracks are not in it, since a MIDI file holds notes only."
        return words

    def export_tracks(self, path, sample_rate=48000, bits=24, progress=None, cancelled=None, tail=True,
                      track_ids=None):
        """Tracks on their own, as WAV files (Russell, 10 Oct 2026): track_ids, or every track you can hear.
        A .wav path with one track is that one file (the vocals alone, say); otherwise the files go into one zip
        file. Every file has the same length, from the start of the song, so they line up side by side in another
        program. Safe to run on a background thread."""
        import zipfile
        if not self.song.has_content():
            raise ValueError("The song has nothing to export yet")
        notes = self.all_sounding_notes()
        if track_ids is None:
            tracks = [t for t in self.song.audible_tracks() if (t.regions if t.is_audio else notes.get(t.id))]
        else:
            wanted = set(track_ids)
            tracks = [t for t in self.song.tracks if t.id in wanted]
        if not tracks:
            raise ValueError("No track has anything to export yet")
        if len(tracks) == 1 and path.lower().endswith(".wav"):
            result = self.export_audio(path, "wav", sample_rate, bits, progress, cancelled, tail,
                                       only_track=tracks[0].id)
            result["files"] = 0 if result["cancelled"] else 1
            result["tracks"] = [tracks[0].name]
            return result
        if not path.lower().endswith(".zip"):
            path += ".zip"
        folder = tempfile.mkdtemp(prefix="musicianforge-tracks-")
        made = []
        peak = 0.0
        seconds = 0.0
        try:
            for number, track in enumerate(tracks):
                def part(fraction, number=number):
                    if progress:
                        progress((number + fraction) / float(len(tracks)))
                name = "{:02d} {}.wav".format(number + 1, projects.safe_name(track.name) or "Track")
                result = self.export_audio(os.path.join(folder, name), "wav", sample_rate, bits, part, cancelled,
                                           tail, only_track=track.id)
                if result["cancelled"]:
                    log.info("Track export cancelled: %s", path)
                    return {"path": path, "cancelled": True, "seconds": 0.0, "peak": peak, "files": 0,
                            "tracks": []}
                peak = max(peak, result["peak"])
                seconds = max(seconds, result["seconds"])
                made.append(result["path"])
            tmp = path + ".tmp"
            try:
                with zipfile.ZipFile(tmp, "w", zipfile.ZIP_STORED, allowZip64=True) as zf:
                    for file in made:
                        zf.write(file, os.path.basename(file))
                replace_file(tmp, path)
            except BaseException:
                # a full disk, say: no half-made zip is left next to the user's songs (the final review, 10 Oct 2026)
                try:
                    os.remove(tmp)
                except OSError:
                    pass
                raise
        finally:
            shutil.rmtree(folder, ignore_errors=True)
        log.info("Exported tracks: %s (%d WAV files, %.1f seconds)", path, len(made), seconds)
        return {"path": path, "cancelled": False, "seconds": seconds, "peak": peak, "files": len(made),
                "tracks": [t.name for t in tracks]}

    @staticmethod
    def describe_track_export(result):
        """What to say when tracks have gone out on their own: the file, where, what is in it, how long."""
        minutes, seconds = divmod(int(round(result["seconds"])), 60)
        length = "{} minute{} {} second{}".format(minutes, "" if minutes == 1 else "s", seconds,
                                                 "" if seconds == 1 else "s")
        where = "{} in {}".format(os.path.basename(result["path"]), projects.describe_file_location(result["path"]))
        if result["files"] == 1 and result["path"].lower().endswith(".wav"):
            message = "Export finished. {}: {} on its own, {} long.".format(where, result["tracks"][0], length)
        else:
            message = "Export finished. {}: {} WAV files, one for each track, {} long.".format(
                where, result["files"], length)
        if result["peak"] >= 0.999:
            message += DISTORTION_WORDS.format("track" if result["files"] == 1 else "tracks")
        return message

    def estimate_wav_bytes(self, sample_rate, bits, tail=True):
        """About how big a WAV export will be (a ring-out usually lasts a second or two)."""
        return wav_size_bytes(int(self._export_seconds(tail) * sample_rate), 2, bits)

    def estimate_export_bytes(self, fmt, sample_rate, bits, tail=True):
        if fmt == "m4a":
            return m4a.m4a_size_bytes(self._export_seconds(tail))
        return self.estimate_wav_bytes(sample_rate, bits, tail)

    def _export_seconds(self, tail):
        end = max(self.song.end_tick(), self.song.song_end_tick())
        return self.song.timeline.tick_to_seconds(end) + (2.0 if tail else 0.0)

    def export_wav(self, path, sample_rate=48000, bits=24, progress=None, cancelled=None, tail=True):
        return self.export_audio(path, "wav", sample_rate, bits, progress, cancelled, tail)

    def export_audio(self, path, fmt="wav", sample_rate=48000, bits=24, progress=None, cancelled=None, tail=True,
                     only_track=None):
        """Render the song to a WAV or M4A file. Safe to run on a background thread.

        tail: True lets the sound ring out after the end until it has faded to silence
        (up to 10 seconds); False ends the file exactly at the end of the song.
        Returns a dict with the path, seconds, peak and whether it was cancelled.
        """
        if not self.song.has_content():
            raise ValueError("The song has nothing to export yet")
        fmt = "m4a" if fmt == "m4a" else "wav"
        if not path.lower().endswith("." + fmt):
            path += "." + fmt
        song = self.song.clone()  # the user can keep working while this runs
        if only_track is not None:       # one track on its own: the same length as the others, so no early stop
            for t in song.tracks:
                t.solo = t.id == only_track
                t.mute = t.id != only_track
        notes_by_track = {tid: [Note(n.tick, n.length, n.pitch, n.velocity) for n in notes]
                          for tid, notes in self.all_sounding_notes().items()}
        try:
            writer = m4a.M4AWriter(path, sample_rate) if fmt == "m4a" else WavWriter(path, sample_rate, bits)
        except m4a.M4AError as exc:
            log.error("M4A export is not available: %s", exc)
            raise ValueError(str(exc)) from None
        try:
            synth = self.synth_factory(sample_rate)
        except Exception:
            writer.abort()          # no half-made file left in the Exports folder
            raise
        peak = 0.0
        stopped = False
        try:
            for block in render_offline(song, synth, sample_rate, progress=progress, cancelled=cancelled,
                                        audio_loader=self.load_audio, tail_seconds=MAX_TAIL_SECONDS if tail else 0.0,
                                        until_silent=tail and only_track is None, take_loader=self._take_audio,
                                        notes_by_track=notes_by_track):
                peak = max(peak, float(abs(block).max()))
                writer.write(block)
            stopped = bool(cancelled and cancelled())
        except m4a.M4AError as exc:
            writer.abort()
            log.error("M4A export failed: %s", exc)
            raise ValueError(str(exc)) from None
        except Exception:
            writer.abort()
            raise
        finally:
            try:
                synth.close()
            except Exception:  # noqa: BLE001
                pass
        if stopped:
            writer.abort()
            log.info("%s export cancelled: %s", fmt.upper(), path)
            return {"path": path, "cancelled": True, "seconds": 0.0, "peak": peak}
        try:
            writer.close()
        except m4a.M4AError as exc:
            log.error("M4A export failed: %s", exc)
            raise ValueError(str(exc)) from None
        seconds = writer.frames / float(sample_rate)
        if fmt == "m4a":
            log.info("Exported M4A: %s (%.1f seconds, %d Hz, %d kbps AAC, peak %.2f)", path, seconds, sample_rate,
                     m4a.KBPS, peak)
        else:
            log.info("Exported WAV: %s (%.1f seconds, %d Hz, %d-bit, peak %.2f)", path, seconds, sample_rate, bits,
                     peak)
        return {"path": path, "cancelled": False, "seconds": seconds, "peak": peak}

    @staticmethod
    def describe_export(result):
        """What to say when an export finishes: the file, where it went and its length."""
        minutes, seconds = divmod(int(round(result["seconds"])), 60)
        message = "Exported {} in {}, {} minute{} {} second{}.".format(
            os.path.basename(result["path"]), projects.describe_file_location(result["path"]),
            minutes, "" if minutes == 1 else "s", seconds, "" if seconds == 1 else "s")
        if result["peak"] >= 0.999:
            # (Russell, 10 Oct 2026: only track volumes; the master volume in Preferences is not used by exports)
            message += DISTORTION_WORDS.format("song")
        return message

    describe_wav_export = describe_export


def _validate_note(note):
    if not isinstance(note, Note):
        raise TypeError("expected a Note")
    if note.tick < 0:
        raise ValueError("A note cannot start before the beginning of the song")
    if note.length <= 0:
        raise ValueError("A note must have a length")
    if not 0 <= note.pitch <= 127:
        raise ValueError("That note is outside the playable range")
    if not 1 <= note.velocity <= 127:
        raise ValueError("Velocity must be from 1 to 127")


def describe_rate(rate):
    """'44.1 kHz', '48 kHz'."""
    return "{} kHz".format(format_number(rate / 1000.0))


DISTORTION_WORDS = " There may be distortion in certain parts of the {}. Reducing track volumes will help with this."
IMPORTED_DISTORTION_GUITAR = (41, 0)    # FSBS Electric Guitar Distorted 2 (packs.py), as most Hammer styles use


def default_song_file_name(song):
    return projects.safe_name(song.title) + FILE_EXTENSION


def folder_name(path):
    """The name of the folder a file is in, the way it is spoken: "Musician Forge Songs"."""
    folder = os.path.dirname(os.path.abspath(path))
    return os.path.basename(folder.rstrip("\\/")) or folder


__all__ = ["Session", "SongFileError", "PREVIEW_CHANNEL", "PPQ", "default_song_file_name", "folder_name"]
