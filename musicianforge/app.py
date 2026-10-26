"""Starting Musician Forge.

Start order: logging, settings, instrument engine (FluidSynth, or the simple
built-in synth if FluidSynth is missing), sound engine, session, window,
sound card, then crash recovery. Problems at any step are explained in a
message instead of stopping the program.

Command line:
    python -m musicianforge [song.mforge] [--no-audio] [--test-mode] [--a11y-target NAME]
"""

import argparse
import gc
import logging
import logging.handlers
import os
import platform
import shutil
import sys
import tempfile
import threading

from . import APP_NAME, __version__, legacy, paths, speech
from .audio import SAMPLE_RATE, AudioInput, AudioOutput
from .engine import Engine
from .session import Session
from .settings import Settings
from .simplesynth import SimpleSynth

log = logging.getLogger("musicianforge")

A11Y_TARGETS = ["start", "main", "keyboard_controls", "new_song", "track_settings", "instrument", "tempo", "time",
                "key", "event_list", "quantize", "go_to_bar", "export_audio", "audio", "preferences", "shortcuts",
                "rename", "sections", "section_settings", "save_as", "open_project", "export_midi", "recordings",
                "audio_track_settings", "recording_settings", "import_file", "midi_import", "effects", "add_effect",
                "effect_settings", "audio_effect_settings", "chord_track", "chord", "fill_chords", "new_player",
                "player_editor", "region_settings", "automation", "add_lane", "automation_points", "automation_point",
                "drummer_editor", "piece_settings", "part_settings", "step_pattern", "new_track"]


def setup_logging():
    folder = paths.logs_dir()
    try:
        os.makedirs(folder, exist_ok=True)
        test_file = os.path.join(folder, ".write_test")
        with open(test_file, "w") as fh:
            fh.write("ok")
        os.remove(test_file)
    except OSError:
        folder = paths.ensure_dir(os.path.join(paths.local_data_dir(), "logs"))
    handler = logging.handlers.RotatingFileHandler(os.path.join(folder, "musicianforge.log"),
                                                   maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)

    last_said = [-1e9]

    def excepthook(kind, value, tb):
        log.critical("Unhandled error", exc_info=(kind, value, tb))
        say_it_went_wrong(last_said)

    def thread_excepthook(args):
        log.critical("Unhandled error in thread %s", args.thread, exc_info=(args.exc_type, args.exc_value,
                                                                            args.exc_traceback))
        say_it_went_wrong(last_said)

    sys.excepthook = excepthook
    threading.excepthook = thread_excepthook
    return folder


ERROR_WORDS = "Something went wrong. The details were saved in the logs folder, in musicianforge.log."


def say_it_went_wrong(last_said, speaker=None, now=None, quiet_seconds=3.0):
    """An error nothing else caught (inside a button of a window, say) is spoken as well as logged: wxPython hands
    such an error to sys.excepthook and carries on, so before the review of 9 Oct 2026 pressing the button seemed to
    do nothing at all. Spoken, not shown in a window (a window could bring the same error straight back), and at
    most once every few seconds."""
    import time

    now = time.monotonic() if now is None else now
    if now - last_said[0] < quiet_seconds:
        return False
    last_said[0] = now
    try:
        (speaker or speech.speaker).speak(ERROR_WORDS)
    except Exception:  # noqa: BLE001 - never an error about an error
        return False
    return True


def make_synth(sample_rate, soundfont, pack_folder=None):
    """FluidSynth with GeneralUser GS, Musician Forge's own kits (built the first time), and the two
    guitar packs if they are downloaded (each on its own bank; a stand-in guitar plays until then)."""
    from . import forgekit, packs
    from .fluid import FluidSynth

    synth = FluidSynth(sample_rate=sample_rate)
    try:
        synth.load_soundfont(soundfont)
    except Exception:
        synth.close()
        raise
    try:
        synth.load_soundfont(forgekit.ensure_kit())
    except Exception:  # noqa: BLE001 - every other instrument still works without them
        log.exception("Musician Forge's own instruments could not be loaded")
    for pack in packs.PACKS:
        if packs.is_installed(pack, pack_folder):
            try:
                synth.load_soundfont(packs.installed_path(pack, pack_folder), pack.bank)
            except Exception:  # noqa: BLE001 - the stand-in guitar plays instead
                log.exception("%s could not be loaded", pack.name)
    return synth


def demo_notes(session, folder=None):
    """A few notes, and an audio track with a recording, so every dialog has something to show
    (accessibility checks only)."""
    import numpy as np

    from . import wavfile
    from .song import Note

    piano = session.selected_track_id
    if piano is None:              # (the project behind the start screen has its piano track, but in case)
        piano = session.add_track("Piano").id
    for i, pitch in enumerate([57, 60, 64, 67]):
        session.add_note(piano, Note(i * 480, 480, pitch, 100))
    if folder:
        tone = 0.3 * np.sin(np.arange(48000) / 48000.0 * 2 * np.pi * 220.0)[:, None]
        path = os.path.join(folder, "Demo tone.wav")
        wavfile.write_wav(path, tone, 48000, 16)
        track = session.add_audio_track("Vocals", speak=False)
        session.import_audio(track.id, path, tick=0)
    session.select_track(piano)


def allow_scrolling_dialogs(wx):
    """A window taller or wider than the screen gets scroll bars instead of controls out of sight. Russell's laptop
    (1920 by 1080 at 150 percent) fits every window since 0.9.4, but a smaller screen or 175 percent scaling would
    not fit Audio settings or the Step pattern. wx does this only for a window that does not fit when it opens, so
    on a screen where everything fits nothing changes; it keeps the controls in their order, so screen readers
    name them as before."""
    try:
        wx.Dialog.EnableLayoutAdaptation(True)
        return True
    except Exception:  # noqa: BLE001 - an older wxPython: windows open as before
        log.exception("Scrolling for windows larger than the screen is not available")
        return False


def already_running(wx):
    """The single-instance check: returns the checker to keep while Musician Forge runs, or None when another
    Musician Forge is already running (that is logged)."""
    checker = wx.SingleInstanceChecker("MusicianForge-{}".format(wx.GetUserId()))
    if checker.IsAnotherRunning():
        log.info("Musician Forge is already running; this second start stops here")
        return None
    return checker


def parse_args(argv):
    parser = argparse.ArgumentParser(prog="musicianforge", description=APP_NAME)
    parser.add_argument("song", nargs="?", help="a .mforge song to open")
    parser.add_argument("--no-audio", action="store_true", help="do not open the sound card")
    parser.add_argument("--test-mode", action="store_true", help="use temporary settings (for testing)")
    parser.add_argument("--a11y-target", choices=A11Y_TARGETS, help="open one window for accessibility checks")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    log_folder = setup_logging()
    log.info("%s %s starting; Python %s on %s; logs in %s", APP_NAME, __version__, sys.version.split()[0],
             platform.platform(), log_folder)

    if not (args.test_mode or args.a11y_target):
        try:
            moved, _blocked = legacy.migrate()    # a Melody Forge folder from before the rename (8 Oct 2026)
            for sentence in moved:
                log.info(sentence)
        except Exception:  # noqa: BLE001 - the program starts anyway; the songs folder falls back to the old name
            log.exception("The old folders could not be moved")

    import wx  # imported here so the rest of the program can be tested without it

    from .ui.common import show_error
    from .ui.main_window import MainFrame

    # Only one Musician Forge at a time (test and accessibility runs aside): on 9 Oct 2026 Russell's log showed it
    # started twice, five seconds apart. Two copies share the settings and the crash-recovery copy, so one could
    # overwrite the other's, or offer the other's project as "not closed properly"; both also hold the sound card.
    single = None
    if not (args.test_mode or args.a11y_target):
        single = already_running(wx)
        if single is None:
            app = wx.App(False)
            app.SetAppName(APP_NAME)
            show_error(None, "Musician Forge is already open. Use Alt+Tab to go to it.")
            return 0

    test_dir = tempfile.mkdtemp(prefix="musicianforge-test-") if (args.test_mode or args.a11y_target) else None
    settings = Settings(os.path.join(test_dir, "settings.json") if test_dir else None).load()
    soundfont = settings["soundfont"] or paths.default_soundfont()

    synth_problem = None
    try:
        synth = make_synth(SAMPLE_RATE, soundfont)

        def synth_factory(rate):
            return make_synth(rate, soundfont)
    except Exception as exc:  # noqa: BLE001
        log.exception("Instrument engine failed; using the simple built-in synth")
        synth_problem = str(exc)
        synth = SimpleSynth(SAMPLE_RATE)

        def synth_factory(rate):
            return SimpleSynth(rate)

    engine = Engine(synth, SAMPLE_RATE)
    speaker = speech.speaker
    speaker.allow_sapi = settings["speak_with_windows_voice"]
    autosave_dir = os.path.join(test_dir, "autosave") if test_dir else paths.autosave_dir()
    session = Session(engine, settings, synth_factory, speaker, synth.presets(), autosave_dir)
    microphone = AudioInput(engine)
    microphone.configure(settings["audio"]["host_api"], settings["audio"]["input_device"],
                         settings["audio"]["block_frames"], settings["audio"]["raw_microphone"])
    session.audio_input = microphone  # it opens only while recording an audio track or testing
    if not args.no_audio and not args.a11y_target:
        from . import lowlatency

        if lowlatency.available():   # Windows 10 and later; used only when Audio settings turn it on
            session.low_latency_factory = lowlatency.LowLatencyMonitor

    app = wx.App(False)
    app.SetAppName(APP_NAME)
    allow_scrolling_dialogs(wx)
    speaker.call_on_main = wx.CallAfter
    audio_output = AudioOutput(engine)
    frame = MainFrame(session, audio_output, speaker)  # the project window: hidden until a project is chosen
    speaker.set_window_getter(frame.speech_window)
    log.info("Speech output: %s", speaker.describe())

    if not args.no_audio and not args.a11y_target:
        audio_settings = settings["audio"]
        try:
            audio_output.open(audio_settings["host_api"], audio_settings["device_name"],
                              audio_settings["block_frames"])
            session.audio_is_live = True
        except Exception as exc:  # noqa: BLE001
            log.exception("Could not open audio")
            wx.CallAfter(show_error, None, "Musician Forge could not open your sound card, so you will not "
                                            "hear anything yet.\n\n{}\n\nTry Options, Audio settings.".format(exc))
        frame.output_watch.start()   # headphones plugged in or out: the sound follows Windows (not with --no-audio)
    frame.refresh_status_text()

    if synth_problem:
        wx.CallAfter(show_error, None, "The instrument engine could not start:\n{}\n\nMusician Forge is using "
                                        "simple built-in sounds for now. Run 'Install or Update Musician Forge' "
                                        "to fix this.".format(synth_problem))

    if args.a11y_target:
        demo_notes(session, test_dir)
        session.modified = False
        if args.a11y_target == "start":
            frame.show_start_screen()
        else:
            frame.Show()
            wx.CallLater(700, _open_a11y_target, frame, args.a11y_target)
    else:
        wx.CallAfter(_first_window, frame, session, args.song)
        if not test_dir and not isinstance(synth, SimpleSynth):
            from .pack_downloader import PackDownloader   # downloads a guitar pack the installer could not
            from .ui.common import say_after
            # said two seconds after it arrives, queued: it must not talk over the first window opening (screen
            # reader audit A4, 23 Oct 2026), and kept: words said meanwhile never take its place (26 Oct 2026)
            PackDownloader(engine, lambda text: wx.CallAfter(say_after, session.announce, text, 2000,
                                                              keep=True)).start()

    gc.collect()
    gc.freeze()  # keeps garbage collection pauses away from the audio
    app.MainLoop()
    del single   # held until here: while it exists, a second start is refused
    log.info("%s closed", APP_NAME)
    if test_dir:
        # the temporary folder this test or accessibility run made for itself (settings, a demo recording):
        # before the review of 9 Oct 2026 every run left one behind, about 45 for each Check Accessibility
        shutil.rmtree(test_dir, ignore_errors=True)
    return 0


def _first_window(frame, session, song_path):
    """What opens first: crash recovery if needed, a project given on the command line, or the start screen."""
    from .ui.common import ask_yes_no

    try:
        session.clean_old_recordings()
    except Exception:  # noqa: BLE001 - tidying up must never stop the program
        log.exception("Could not tidy old recordings")
    try:
        if session.recovery_available():
            if ask_yes_no(None, "Musician Forge did not close properly last time. "
                                "Recover the project you were working on?", escape=False):   # (No throws it away)
                with session.pressed("window"):   # "Recovered ..." is said once the project window shows
                    if frame.safe(session.recover):
                        frame.show_project()
                        return
            session.mark_clean_exit()
    except Exception:  # noqa: BLE001 - a window must always open (before the review of 9 Oct 2026, an error
        log.exception("Crash recovery failed")   # here left Musician Forge running with no window at all)
    if song_path:
        if frame.safe(frame.open_song, os.path.abspath(song_path)):
            frame.show_project()
            return
    frame.show_start_screen()


def _open_a11y_target(frame, target):
    """Open one window and leave it open so tools/a11y_check.py can inspect it."""
    if target == "keyboard_controls":
        frame.go_to_keyboard_controls()
        return
    audio_track = next((t for t in frame.session.song.tracks if t.is_audio), None)
    if target in ("recordings", "audio_track_settings", "recording_settings") and audio_track is not None:
        frame.session.select_track(audio_track.id)
    if target == "recording_settings":
        from .ui.dialogs import RecordingDialog

        with RecordingDialog(frame, frame.session, audio_track.id, 0) as dlg:
            frame.show_modal(dlg)
        frame.Close(True)
        return
    if target in ("effects", "add_effect", "effect_settings", "audio_effect_settings"):
        from .ui.effects_dialogs import AddEffectDialog, EffectSettingsDialog

        session = frame.session
        if target == "add_effect":
            dialog = AddEffectDialog(frame, session.effect_types_for(session.selected_track_id))
        elif target == "audio_effect_settings" and audio_track is not None:
            session.add_effect(audio_track.id, "pitch")
            dialog = EffectSettingsDialog(frame, session, audio_track.id, 0)
        elif target == "effect_settings":
            session.add_effect(session.selected_track_id, "delay")   # has every kind of setting
            dialog = EffectSettingsDialog(frame, session, session.selected_track_id, 0)
        else:
            session.add_effect(session.selected_track_id, "reverb", "Hall")
            frame.safe(frame.track_effects)
            session.modified = False
            frame.Close(True)
            return
        with dialog:
            frame.show_modal(dialog)
        session.modified = False
        frame.Close(True)
        return
    if target == "midi_import":
        from .ui.dialogs import MidiImportDialog

        with MidiImportDialog(frame, "Night Drive.mid: 5 tracks with notes, 1234 notes, 3 tempo changes, "
                                     "2 time signatures, 1 key signature, 4 markers.", True) as dlg:
            frame.show_modal(dlg)
        frame.Close(True)
        return
    if target in ("chord", "fill_chords", "player_editor", "region_settings", "drummer_editor", "piece_settings",
                  "part_settings", "step_pattern"):
        from .ui import music_dialogs

        session = frame.session
        session.fill_chords(0, 1, 9)
        if target == "chord":
            dialog = music_dialogs.ChordDialog(frame, session, tick=0)
        elif target == "fill_chords":
            dialog = music_dialogs.FillChordsDialog(frame, 1, 8)
        elif target in ("drummer_editor", "piece_settings", "step_pattern"):
            tid, index = session.add_player_region("anvil", "rock")      # version 0.9.2: the kit pieces
            if target == "drummer_editor":
                dialog = music_dialogs.PlayerEditorDialog(frame, session, tid, index, run_modal=frame.show_modal)
            elif target == "piece_settings":
                dialog = music_dialogs.PieceSettingsDialog(frame, session, tid, index, "crash",
                                                           run_modal=frame.show_modal)
            else:
                dialog = music_dialogs.StepPatternDialog(frame, session, tid, index, "snare")
        else:
            tid, index = session.add_player_region("hammer")
            if target == "player_editor":
                dialog = music_dialogs.PlayerEditorDialog(frame, session, tid, index, run_modal=frame.show_modal)
            elif target == "part_settings":
                dialog = music_dialogs.PieceSettingsDialog(frame, session, tid, index, "part",
                                                           run_modal=frame.show_modal)
            else:
                dialog = music_dialogs.RegionSettingsDialog(frame, session, tid, index)
        with dialog:
            frame.show_modal(dialog)
        session.modified = False
        frame.Close(True)
        return
    if target in ("add_lane", "automation_points", "automation_point"):
        from .ui import automation_dialogs

        session = frame.session
        tid = session.selected_track_id
        session.add_effect(tid, "reverb")
        if target == "add_lane":
            dialog = automation_dialogs.AddLaneDialog(frame, session.automation_targets(tid))
        else:
            lane = session.add_lane(tid, ("volume", None, None))
            session.set_point(tid, lane, 1, 1, 80)
            session.set_point(tid, lane, 3, 1, 40, glide=False)
            if target == "automation_points":
                dialog = automation_dialogs.LanePointsDialog(frame, session, tid, lane, run_modal=frame.show_modal)
            else:
                dialog = automation_dialogs.PointDialog(frame, session, tid, lane, 0, 80, True)
        with dialog:
            frame.show_modal(dialog)
        session.modified = False
        frame.Close(True)
        return
    actions = {
        "main": None,
        "automation": frame.track_automation,
        "chord_track": frame.chord_track,
        "new_player": frame.new_player,
        "new_song": frame.new_song,
        "new_track": frame.new_track,
        "track_settings": frame.track_settings,
        "instrument": frame.change_instrument,
        "tempo": lambda: frame.changes("tempo"),
        "time": lambda: frame.changes("time"),
        "key": lambda: frame.changes("key"),
        "event_list": frame.event_list,
        "quantize": frame.quantize,
        "go_to_bar": frame.go_to_bar,
        "export_audio": frame.export_audio,
        "audio": frame.audio_settings,
        "preferences": frame.preferences,
        "shortcuts": frame.show_shortcuts,
        "rename": frame.rename_track,
        "sections": frame.sections,
        "section_settings": frame.section_settings,
        "recordings": frame.event_list,
        "audio_track_settings": frame.track_settings,
        # Save project as is Musician Forge's own window; Export MIDI and Import are Windows' own
        # windows, checked for the folder they open in
        "save_as": frame.save_as,
        "export_midi": frame.export_midi,
        "import_file": frame.import_file,
        "open_project": frame.choose_project,
    }
    action = actions.get(target)
    if action is None:
        return
    frame.safe(action)
    frame.session.modified = False
    frame.Close(True)


if __name__ == "__main__":
    sys.exit(main())
