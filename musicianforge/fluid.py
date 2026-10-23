"""A small, direct connection to the FluidSynth instrument engine.

FluidSynth turns MIDI-style note messages into audio using a SoundFont
(.sf2 file). This module talks to FluidSynth's DLL with ctypes, so Musician
Forge does not depend on any other Python binding.

All audio comes back as float32 stereo numpy arrays shaped (frames, 2).
"""

import ctypes
import ctypes.util
import glob
import logging
import os
import sys

import numpy as np

from . import drummap, fluidbuild, packs, paths, sf2keys

log = logging.getLogger("musicianforge.fluid")

FLUID_OK = 0
FLUID_FAILED = -1
CHANNEL_TYPE_MELODIC = 0
CHANNEL_TYPE_DRUM = 1

_LOG_FUNC = ctypes.CFUNCTYPE(None, ctypes.c_int, ctypes.c_char_p, ctypes.c_void_p)


class FluidSynthNotFound(RuntimeError):
    """FluidSynth's DLL could not be found or loaded."""


def candidate_library_paths():
    """Every place Musician Forge looks for the FluidSynth library, best first."""
    found = []
    override = os.environ.get("MUSICIANFORGE_FLUIDSYNTH_DLL")
    if override:
        found.append(override)
    base = paths.fluidsynth_dir()
    if os.path.isdir(base):
        patterns = ["**/libfluidsynth-3.dll", "**/libfluidsynth*.dll", "**/fluidsynth*.dll"]
        for pattern in patterns:
            for match in sorted(glob.glob(os.path.join(base, pattern), recursive=True)):
                if match not in found:
                    found.append(match)
    for name in ("fluidsynth", "libfluidsynth-3", "libfluidsynth", "fluidsynth-3"):
        lib = ctypes.util.find_library(name)
        if lib and lib not in found:
            found.append(lib)
    return found


def loaded_file(lib, path):
    """The file a loaded library really came from. On Windows a name without a folder is looked for in several
    places (the program's folder, System32, added DLL folders), so Windows itself is asked."""
    if sys.platform == "win32":
        try:
            get_name = ctypes.windll.kernel32.GetModuleFileNameW
            get_name.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint32]
            get_name.restype = ctypes.c_uint32
            buf = ctypes.create_unicode_buffer(32768)
            if get_name(lib._handle, buf, len(buf)):
                return buf.value
        except Exception:  # noqa: BLE001 - fall back to the name it was loaded by
            pass
    return os.path.abspath(path)


_lib = None
_lib_path = None
_dll_dir_handles = []
_log_callback = None


def load_library():
    """Load FluidSynth once and return the ctypes library object."""
    global _lib, _lib_path, _log_callback
    if _lib is not None:
        return _lib
    errors, unsafe = [], []
    for path in candidate_library_paths():
        try:
            if sys.platform == "win32" and os.path.isabs(path):
                folder = os.path.dirname(path)
                if hasattr(os, "add_dll_directory"):
                    _dll_dir_handles.append(os.add_dll_directory(folder))
                os.environ["PATH"] = folder + os.pathsep + os.environ.get("PATH", "")
            lib = ctypes.CDLL(path)
            _declare(lib)
            raw = lib.fluid_version_str()
            found_version = raw.decode("ascii", "replace") if raw else "unknown"
            if fluidbuild.crashes_with_many_outputs(found_version, os.path.dirname(loaded_file(lib, path)),
                                                    sys.platform):
                # 8 Oct 2026: loading it is harmless, but the first sound would end the program
                log.error("Not using FluidSynth %s from %s: %s", found_version, path,
                          fluidbuild.problem_sentence(found_version))
                unsafe.append(found_version)
                continue
            _lib, _lib_path = lib, path
            _log_callback = _LOG_FUNC(_on_fluid_log)
            for level in (0, 1, 2):  # panic, error, warning -> our log
                lib.fluid_set_log_function(level, _log_callback, None)
            for level in (3, 4):  # info, debug -> silenced
                lib.fluid_set_log_function(level, ctypes.cast(None, _LOG_FUNC), None)
            log.info("Loaded FluidSynth %s from %s", version(), path)
            return lib
        except (OSError, AttributeError) as exc:
            errors.append("{}: {}".format(path, exc))
    if unsafe:
        raise FluidSynthNotFound(fluidbuild.problem_sentence(unsafe[0]))
    detail = "; ".join(errors) if errors else "no FluidSynth library was found"
    raise FluidSynthNotFound(
        "The FluidSynth instrument engine is not installed ({}). "
        "Run 'Install or Update Musician Forge' to install it.".format(detail))


def library_path():
    return _lib_path


def _on_fluid_log(level, message, _data):
    try:
        text = message.decode("utf-8", "replace").strip() if message else ""
        if level <= 1:
            log.error("FluidSynth: %s", text)
        else:
            log.warning("FluidSynth: %s", text)
    except Exception:  # noqa: BLE001 - never raise into C code
        pass


def _declare(lib):
    vp, ci, cd, cf, cs = ctypes.c_void_p, ctypes.c_int, ctypes.c_double, ctypes.c_float, ctypes.c_char_p
    sigs = {
        "new_fluid_settings": (vp, []),
        "delete_fluid_settings": (None, [vp]),
        "fluid_settings_setstr": (ci, [vp, cs, cs]),
        "fluid_settings_setnum": (ci, [vp, cs, cd]),
        "fluid_settings_setint": (ci, [vp, cs, ci]),
        "new_fluid_synth": (vp, [vp]),
        "delete_fluid_synth": (None, [vp]),
        "fluid_synth_sfload": (ci, [vp, cs, ci]),
        "fluid_synth_program_select": (ci, [vp, ci, ci, ci, ci]),
        "fluid_synth_noteon": (ci, [vp, ci, ci, ci]),
        "fluid_synth_noteoff": (ci, [vp, ci, ci]),
        "fluid_synth_cc": (ci, [vp, ci, ci, ci]),
        "fluid_synth_pitch_bend": (ci, [vp, ci, ci]),
        "fluid_synth_all_notes_off": (ci, [vp, ci]),
        "fluid_synth_all_sounds_off": (ci, [vp, ci]),
        "fluid_synth_system_reset": (ci, [vp]),
        "fluid_synth_set_channel_type": (ci, [vp, ci, ci]),
        "fluid_synth_write_float": (ci, [vp, ci, vp, ci, ci, vp, ci, ci]),
        "fluid_synth_process": (ci, [vp, ci, ci, vp, ci, vp]),
        "fluid_synth_set_gain": (None, [vp, cf]),
        "fluid_synth_get_sfont_by_id": (vp, [vp, ci]),
        "fluid_sfont_iteration_start": (None, [vp]),
        "fluid_sfont_iteration_next": (vp, [vp]),
        "fluid_preset_get_name": (cs, [vp]),
        "fluid_preset_get_banknum": (ci, [vp]),
        "fluid_preset_get_num": (ci, [vp]),
        "fluid_version_str": (cs, []),
        "fluid_set_log_function": (vp, [ci, _LOG_FUNC, vp]),
        "fluid_synth_set_bank_offset": (ci, [vp, ci, ci]),
        "fluid_synth_set_gen": (ci, [vp, ci, ci, cf]),
    }
    for name, (restype, argtypes) in sigs.items():
        func = getattr(lib, name)
        func.restype = restype
        func.argtypes = argtypes
    # Each channel's own reverb and chorus (FluidSynth 2.2 and later; see FluidSynth.effects_on). An older
    # FluidSynth lacks them and keeps one reverb and chorus for every channel, as before.
    optional = {
        "fluid_synth_count_effects_groups": (ci, [vp]),
        "fluid_synth_reverb_on": (ci, [vp, ci, ci]),
        "fluid_synth_chorus_on": (ci, [vp, ci, ci]),
    }
    for name, (restype, argtypes) in optional.items():
        func = getattr(lib, name, None)
        if func is not None:
            func.restype = restype
            func.argtypes = argtypes


def version():
    lib = load_library()
    raw = lib.fluid_version_str()
    return raw.decode("ascii", "replace") if raw else "unknown"


TRACE_ENV = "MUSICIANFORGE_TRACE"   # a file name: every call into FluidSynth is written to it first (see FluidSynth._t)
KEEPER_CHANNELS = {40: 125, 41: 126}  # spare channels (tracks use 0 to 99, 127 previews instruments)
GEN_RELEASE = 38                 # the SoundFont volume envelope's release generator
GUITAR_PACK_RELEASE = -2000.0    # timecents: release times 2 ** (-2000 / 1200), about a third
GEN_ATTENUATION = 48             # the SoundFont initial attenuation generator
GUITAR_PACK_ATTENUATION = 60.0   # centibels: 6 dB quieter (measured: a power chord's level drops 6.0 dB)


class Preset:
    """One instrument. missing is True for a guitar pack that is not downloaded yet (a stand-in plays)."""
    __slots__ = ("bank", "program", "name", "missing")

    def __init__(self, bank, program, name, missing=False):
        self.bank, self.program, self.name, self.missing = bank, program, name, missing

    @property
    def is_drum_kit(self):
        return self.bank == 128

    def __repr__(self):
        return "Preset({}, {}, {!r})".format(self.bank, self.program, self.name)


class FluidSynth:
    """One FluidSynth synthesizer with its SoundFonts and channels.

    The first SoundFont loaded is the main one (GeneralUser GS). Others, such as
    Musician Forge's own kits, add instruments on bank and program numbers the
    main one does not use; each instrument is played from the SoundFont it is in.

    Every MIDI channel has its own stereo output (FluidSynth's "audio groups"), so each
    track's sound can go through its own effects, volume and pan (see render_channels).
    FluidSynth's built-in reverb and chorus come out separately. Since 23 Oct 2026 every channel also has its own
    reverb and chorus (FluidSynth's "effects groups"), so they can follow the track's volume, pan and effects
    (see effects_on and engine.Engine._mix_channels).

    Not thread-safe by design: Musician Forge calls it only from the audio
    thread (or from one thread during an export).
    """

    def __init__(self, sample_rate=48000, channels=128, polyphony=256, gain=0.6,
                 reverb=True, chorus=True, dynamic_samples=True, outputs=None):
        self._lib = load_library()
        self._trace = None
        trace_file = os.environ.get(TRACE_ENV)
        if trace_file:
            self._trace = open(trace_file, "a", encoding="utf-8")
        self.sample_rate = int(sample_rate)
        self.channels = int(channels)
        self.outputs = int(outputs or channels)    # stereo outputs: normally one per channel
        self._t("new settings: {} channels, {} outputs".format(self.channels, self.outputs))
        self._settings = self._lib.new_fluid_settings()
        if not self._settings:
            raise RuntimeError("FluidSynth could not create its settings")
        self._set_num("synth.sample-rate", float(self.sample_rate))
        self._set_num("synth.gain", float(gain))
        self._set_int("synth.midi-channels", self.channels)
        self._set_int("synth.polyphony", int(polyphony))
        self._set_int("synth.reverb.active", 1 if reverb else 0)
        self._set_int("synth.chorus.active", 1 if chorus else 0)
        self._set_int("synth.cpu-cores", 1)
        self._set_int("synth.audio-channels", self.outputs)    # one stereo output per MIDI channel
        self._set_int("synth.audio-groups", self.outputs)
        # One reverb and chorus per channel (23 Oct 2026). Before, one reverb and chorus took every channel's
        # sound at full level, so a track at volume 0 still played its reverb, a fade left the reverb behind,
        # pan did not move it, and the track's effects did not touch it. FluidSynth's reverb and chorus are
        # linear, so one unit per channel added together sounds exactly like the single shared one. A unit
        # costs time even when silent, so only the channels that need one have it on (effects_on).
        lib = self._lib
        self._own_effects = (hasattr(lib, "fluid_synth_count_effects_groups")
                             and hasattr(lib, "fluid_synth_reverb_on") and hasattr(lib, "fluid_synth_chorus_on"))
        if self._own_effects and (reverb or chorus):
            self._set_int("synth.effects-groups", min(128, self.channels))
        # load an instrument's samples only when a track uses it: the guitar packs are large
        self._set_int("synth.dynamic-sample-loading", 1 if dynamic_samples else 0)
        self._t("new_fluid_synth")
        self._synth = self._lib.new_fluid_synth(self._settings)
        if not self._synth:
            self._lib.delete_fluid_settings(self._settings)
            raise RuntimeError("FluidSynth could not start")
        self.sfont_id = None          # the main SoundFont
        self.soundfont_path = None
        self.fonts = []               # (id, path) of every loaded SoundFont, in loading order
        self.bank_offsets = {}        # SoundFont id -> number added to its bank numbers
        self._preset_fonts = None     # (bank, program) -> id of the SoundFont that has it
        self._kept = set()            # guitar pack instruments whose samples stay loaded (see _keep_loaded)
        self._key_maps = {}           # channel -> {drum note its kit lacks: the note played instead} (drummap.py)
        self._kit_keys = {}           # SoundFont id -> {(bank, program): notes it has a sound for} (sf2keys.py)
        self._buffer = np.zeros((0, 2), dtype=np.float32)
        self._targets = {}            # id of a planar buffer -> (its rows' addresses, its fx rows' addresses)
        self._scratch = None          # planar buffers for render()
        self.fx_groups = 1            # reverb and chorus units: channel c uses unit c % fx_groups
        if self._own_effects:
            self.fx_groups = max(1, int(self._lib.fluid_synth_count_effects_groups(self._synth)))
        self._reverb, self._chorus = bool(reverb), bool(chorus)
        self._fx_on = set(range(self.fx_groups))     # units that are on (FluidSynth starts with all of them on)
        self._fx_wanted = set(self._fx_on)            # units the engine wants (see effects_on)
        self._asleep = set()                          # of those, units resting while silent (see sleep_effects)
        self.effects_version = 0                      # counts changes of the units running (Engine._live_effects)
        self._fx_null = None          # a unit that is off leaves its unprocessed send in its rows: they are skipped
        self._fx_wide = None          # rows for every unit, for a caller that passes fewer (see render_channels)

    # -- settings ---------------------------------------------------------
    def _t(self, text):
        """Write what is about to happen to the trail file (only when MUSICIANFORGE_TRACE is set). Windows can
        end the program at once when FluidSynth does something wrong, and Python's crash report cannot see that;
        the last line of the trail then names the call that did it."""
        if self._trace is not None:
            self._trace.write(text + "\n")
            self._trace.flush()

    def _set_num(self, name, value):
        if self._lib.fluid_settings_setnum(self._settings, name.encode(), value) != FLUID_OK:
            log.warning("FluidSynth setting %s=%s was not accepted", name, value)

    def _set_int(self, name, value):
        if self._lib.fluid_settings_setint(self._settings, name.encode(), value) != FLUID_OK:
            log.warning("FluidSynth setting %s=%s was not accepted", name, value)

    # -- soundfonts -------------------------------------------------------
    def load_soundfont(self, path, bank_offset=0):
        """Load a SoundFont. bank_offset moves all its instruments up that many banks, so a SoundFont
        whose instruments are on bank 0 (like the guitar packs) does not clash with GeneralUser GS."""
        if not os.path.isfile(path):
            raise FileNotFoundError("SoundFont not found: {}".format(path))
        # Only the first SoundFont resets the channels' instruments: resetting after a later one would
        # pick that one's bank 0 instruments for every channel (and, for a guitar pack, load all of its
        # samples) before its bank offset is set.
        reset = 1 if self.sfont_id is None else 0
        self._t("sfload {} reset={}".format(os.path.basename(path), reset))
        sfid = self._lib.fluid_synth_sfload(self._synth, os.fsencode(path), reset)
        if sfid == FLUID_FAILED:
            raise RuntimeError("FluidSynth could not load the SoundFont {}".format(path))
        if bank_offset:
            self._t("set_bank_offset {}".format(bank_offset))
            self._lib.fluid_synth_set_bank_offset(self._synth, sfid, int(bank_offset))
            self.bank_offsets[sfid] = int(bank_offset)
        if self.sfont_id is None:
            self.sfont_id = sfid
            self.soundfont_path = path
        self.fonts.append((sfid, path))
        # which notes each kit has a sound for, read now (23 Oct 2026): picking a drum kit reads it on the audio
        # thread, where reading the file the first time would hold up the sound
        self._kit_keys[sfid] = sf2keys.preset_keys(path)
        self._preset_fonts = None
        return sfid

    def presets(self):
        """All instruments in every loaded SoundFont, sorted by bank then program.

        If two SoundFonts have the same bank and program, the one loaded first wins.
        """
        result, owners = [], {}
        for sfid, _path in self.fonts:
            sfont = self._lib.fluid_synth_get_sfont_by_id(self._synth, sfid)
            if not sfont:
                continue
            self._lib.fluid_sfont_iteration_start(sfont)
            while True:
                preset = self._lib.fluid_sfont_iteration_next(sfont)
                if not preset:
                    break
                bank = self._lib.fluid_preset_get_banknum(preset) + self.bank_offsets.get(sfid, 0)
                program = self._lib.fluid_preset_get_num(preset)
                if (bank, program) in owners:
                    continue
                owners[(bank, program)] = sfid
                raw = self._lib.fluid_preset_get_name(preset) or b""
                name = raw.decode("latin-1").strip()
                if bank in packs.PACK_BY_BANK and self.bank_offsets.get(sfid):
                    name = packs.PACK_BY_BANK[bank].name      # its own name is shortened to 20 letters
                result.append(Preset(bank, program, name))
        self._preset_fonts = owners
        for pack in packs.PACKS:     # a guitar pack still to be downloaded is listed, and a stand-in plays it
            if (pack.bank, 0) not in owners:
                result.append(Preset(pack.bank, 0, pack.name + " (not downloaded yet; a stand-in guitar plays)",
                                     missing=True))
        result.sort(key=lambda p: (p.bank, p.program))
        return result

    # -- channel setup ----------------------------------------------------
    def set_instrument(self, channel, bank, program, drum=False):
        if self.sfont_id is None:
            raise RuntimeError("No SoundFont is loaded")
        kind = CHANNEL_TYPE_DRUM if drum else CHANNEL_TYPE_MELODIC
        self._t("set_channel_type channel={} kind={}".format(channel, kind))
        self._lib.fluid_synth_set_channel_type(self._synth, channel, kind)
        if self._preset_fonts is None:
            self.presets()
        pack = packs.PACK_BY_BANK.get(bank)
        if pack is not None and (bank, program) not in self._preset_fonts:
            bank, program = packs.STAND_IN[:2]          # the pack is not downloaded yet
        elif pack is not None:
            self._keep_loaded(bank, program)
        sfid = self._preset_fonts.get((bank, program), self.sfont_id)
        self._t("program_select channel={} bank={} program={}".format(channel, bank, program))
        result = self._lib.fluid_synth_program_select(self._synth, channel, sfid, bank, program)
        if result != FLUID_OK:
            log.warning("Instrument bank %s program %s is not in the SoundFont", bank, program)
        self._key_maps.pop(channel, None)
        if drum and result == FLUID_OK:
            # a drum sound this kit lacks (a splash on the Forge House Kit, say) plays on the nearest one it has
            missing = drummap.substitutes(self.kit_notes(sfid, bank, program))
            if missing:
                self._key_maps[channel] = missing
        # The guitar packs ring for half a second after a key is let go, which blurs fast chugs and muted
        # notes (the packs have no palm-muted samples): their release is made about three times shorter.
        pack_channel = bank in packs.PACK_BY_BANK
        self._t("set_gen release channel={}".format(channel))
        self._lib.fluid_synth_set_gen(self._synth, channel, GEN_RELEASE, GUITAR_PACK_RELEASE if pack_channel else 0.0)
        # The packs are recorded hot, about 9 dB louder than the other instruments: 6 dB quieter
        # puts a power chord level with a strong General MIDI guitar, so a band does not clip.
        self._t("set_gen attenuation channel={}".format(channel))
        self._lib.fluid_synth_set_gen(self._synth, channel, GEN_ATTENUATION,
                                      GUITAR_PACK_ATTENUATION if pack_channel else 0.0)
        return result == FLUID_OK

    def kit_notes(self, sfid, bank, program):
        """The notes a kit has a sound for, read from its SoundFont (everything, if that cannot be read)."""
        kit_keys = self.__dict__.setdefault("_kit_keys", {})
        keys = kit_keys.get(sfid)
        if keys is None:          # (a SoundFont load_soundfont did not read: read now, once)
            path = dict(self.fonts).get(sfid)
            keys = kit_keys[sfid] = sf2keys.preset_keys(path) if path else {}
        notes = keys.get((bank - self.bank_offsets.get(sfid, 0), program))
        return notes if notes else frozenset(range(128))

    def _keep_loaded(self, bank, program):
        """A guitar pack's samples load (about 400 megabytes, most of a second) the first time a channel
        picks it, and would be unloaded whenever no channel uses it. A spare channel that never plays
        keeps each pack picked once loaded, so changing instruments back and forth stays instant."""
        if (bank, program) in self._kept:
            return
        channel = KEEPER_CHANNELS.get(bank)
        if channel is None or channel >= self.channels:
            return
        sfid = self._preset_fonts.get((bank, program))
        if sfid is not None and self._lib.fluid_synth_program_select(
                self._synth, channel, sfid, bank, program) == FLUID_OK:
            self._kept.add((bank, program))

    def would_load_samples(self, bank, program=0):
        """True if picking this instrument now would load a guitar pack's samples (most of a second)."""
        if bank not in packs.PACK_BY_BANK or (bank, program) in self._kept:
            return False
        if self._preset_fonts is None:
            self.presets()
        return (bank, program) in self._preset_fonts

    def is_kept_loaded(self, bank, program=0):
        return (bank, program) in self._kept

    # -- performance messages ---------------------------------------------
    def noteon(self, channel, key, velocity):
        key = self._key_maps.get(channel, {}).get(key, key)
        if self._trace is not None:
            self._t("noteon channel={} key={} velocity={}".format(channel, key, velocity))
        if velocity <= 0:
            self._lib.fluid_synth_noteoff(self._synth, channel, key)
        else:
            if getattr(self, "_asleep", None):
                self._wake(channel)          # its reverb and chorus run again before the note sounds
            self._lib.fluid_synth_noteon(self._synth, channel, key, min(127, int(velocity)))

    def noteoff(self, channel, key):
        key = self._key_maps.get(channel, {}).get(key, key)
        if self._trace is not None:
            self._t("noteoff channel={} key={}".format(channel, key))
        self._lib.fluid_synth_noteoff(self._synth, channel, key)

    def cc(self, channel, controller, value):
        self._lib.fluid_synth_cc(self._synth, channel, controller, max(0, min(127, int(value))))

    def pitch_bend(self, channel, value):
        self._lib.fluid_synth_pitch_bend(self._synth, channel, max(0, min(16383, int(value))))

    def all_notes_off(self, channel=-1):
        """Release notes (they fade naturally). channel -1 means every channel."""
        channels = range(self.channels) if channel < 0 else [channel]
        for chan in channels:
            self._lib.fluid_synth_all_notes_off(self._synth, chan)

    def all_sounds_off(self, channel=-1):
        """Silence immediately. channel -1 means every channel."""
        channels = range(self.channels) if channel < 0 else [channel]
        for chan in channels:
            self._lib.fluid_synth_all_sounds_off(self._synth, chan)

    def set_gain(self, gain):
        self._lib.fluid_synth_set_gain(self._synth, float(gain))

    # -- each channel's own reverb and chorus (23 Oct 2026) --------------
    @property
    def fx_rows(self):
        """Rows render_channels fills when `fx` has a row for every unit: 4 per unit (reverb left, right,
        chorus left, right), unit u in rows 4u to 4u + 3."""
        return 4 * self.fx_groups

    def effects_on(self, channels):
        """Turn the reverb and chorus on for these channels' units and off for every other unit (only units
        that can make a sound need to run). A unit turned off keeps what it held; turned on again, that plays
        out (the engine only ever adds units while it runs, see Engine._update_effect_units)."""
        if self.fx_groups <= 1:
            return
        self._fx_wanted = {int(c) % self.fx_groups for c in channels}
        self._asleep &= self._fx_wanted
        self._run_units(self._fx_wanted - self._asleep)

    def sleep_effects(self, channels):
        """Rest the reverb and chorus of these channels: they have been silent long enough that nothing is left in
        them (Engine._rest_quiet_effects). A unit costs as much silent as busy, so a song with many tracks would
        otherwise spend most of its time on reverbs of tracks not playing. The next note on the channel wakes it
        (noteon), before that note sounds."""
        if self.fx_groups <= 1:
            return
        units = {int(c) % self.fx_groups for c in channels} & self._fx_wanted
        if units - self._asleep:
            self._asleep |= units
            self._run_units(self._fx_wanted - self._asleep)

    def _wake(self, channel):
        unit = int(channel) % self.fx_groups
        if unit in self._asleep:
            self._asleep.discard(unit)
            self._run_units(self._fx_wanted - self._asleep)

    def _run_units(self, running):
        if running == self._fx_on:
            return
        for unit in range(self.fx_groups):
            on = unit in running
            if on != (unit in self._fx_on):
                self._t("effects unit {} {}".format(unit, "on" if on else "off"))
                if self._reverb:
                    self._lib.fluid_synth_reverb_on(self._synth, unit, 1 if on else 0)
                if self._chorus:
                    self._lib.fluid_synth_chorus_on(self._synth, unit, 1 if on else 0)
        self._fx_on = set(running)
        self.effects_version += 1
        off = [r for u in range(self.fx_groups) if u not in running for r in range(4 * u, 4 * u + 4)]
        self._fx_null = np.array(off, dtype=np.int64) if off else None

    def effects_units_on(self):
        """The units whose reverb and chorus are running now."""
        return set(self._fx_on)

    # -- audio ------------------------------------------------------------
    def render_channels(self, frames, planar, offset, fx):
        """Mix `frames` frames of every channel into its own rows of `planar`, from column `offset`.

        planar: C-contiguous float32 shaped (2 * channels, length): rows 2c and 2c + 1 are
        channel c's left and right. fx: float32 for the built-in reverb and chorus, either shaped
        (fx_rows, length), each unit in its own four rows (reverb left, right, chorus left, right; the rows of
        a unit that is off are left alone), or (4, length) for every unit added together.
        The sound is added to what is already there."""
        frames = int(frames)
        if frames <= 0:
            return
        if 0 < fx.shape[0] < self.fx_rows and self._fx_null is not None:
            # every unit added together into fewer rows: a unit that is off must not add its unprocessed send
            if self._fx_wide is None or self._fx_wide.shape[1] < frames:
                self._fx_wide = np.zeros((self.fx_rows, max(frames, 1024)), dtype=np.float32)
            wide = self._fx_wide
            wide[:, :frames] = 0.0
            self.render_channels(frames, planar, offset, wide)
            n = fx.shape[0]
            for r in range(n):
                fx[r, offset:offset + frames] += wide[r::n, :frames].sum(axis=0)
            return
        key = (planar.ctypes.data, fx.ctypes.data, planar.shape, fx.shape)
        target = self._targets.get(key)
        if target is None:
            if planar.dtype != np.float32 or not planar.flags.c_contiguous or planar.shape[0] != 2 * self.outputs:
                raise ValueError("render_channels() needs a contiguous float32 array with two rows per channel")
            rows = np.array([planar[i].ctypes.data for i in range(planar.shape[0])], dtype=np.uint64)
            fx_rows = np.array([fx[i].ctypes.data for i in range(fx.shape[0])], dtype=np.uint64)
            target = (rows, fx_rows, planar, fx)    # the arrays are kept so their memory stays valid
            if len(self._targets) > 4:
                self._targets.clear()
            self._targets[key] = target
        rows, fx_rows = target[0], target[1]
        shift = np.uint64(int(offset) * 4)
        out_ptrs = rows + shift
        fx_ptrs = fx_rows + shift
        if self._fx_null is not None and len(fx_ptrs) == self.fx_rows:
            fx_ptrs[self._fx_null] = 0      # no pointer: FluidSynth skips the rows of units that are off
        if self._trace is not None:
            self._t("process frames={} nfx={} nout={}".format(frames, len(fx_ptrs), len(out_ptrs)))
        result = self._lib.fluid_synth_process(self._synth, frames, len(fx_ptrs), fx_ptrs.ctypes.data,
                                               len(out_ptrs), out_ptrs.ctypes.data)
        if result != FLUID_OK:
            log.warning("FluidSynth could not render a block")

    def render(self, frames, out=None):
        """Render `frames` frames of stereo float32 audio (every channel mixed together).

        If `out` is given it must be a C-contiguous float32 array shaped
        (frames, 2); it is filled in place and returned.
        """
        frames = int(frames)
        if out is None:
            out = np.empty((frames, 2), dtype=np.float32)
        if frames <= 0:
            return out
        if out.dtype != np.float32 or out.shape != (frames, 2):
            raise ValueError("render() needs a float32 array shaped (frames, 2)")
        if self._scratch is None or self._scratch[0].shape[1] < frames:
            size = max(frames, 4096)
            self._scratch = (np.zeros((2 * self.outputs, size), np.float32), np.zeros((4, size), np.float32))
        planar, fx = self._scratch
        planar[:, :frames] = 0.0
        fx[:, :frames] = 0.0
        self.render_channels(frames, planar, 0, fx)
        out[:, 0] = planar[0::2, :frames].sum(axis=0) + fx[0, :frames] + fx[2, :frames]
        out[:, 1] = planar[1::2, :frames].sum(axis=0) + fx[1, :frames] + fx[3, :frames]
        return out

    def close(self):
        if getattr(self, "_synth", None):
            self._t("delete_fluid_synth")
            self._lib.delete_fluid_synth(self._synth)
            self._synth = None
        if getattr(self, "_settings", None):
            self._t("delete_fluid_settings")
            self._lib.delete_fluid_settings(self._settings)
            self._settings = None
        if getattr(self, "_trace", None) is not None:
            self._trace.close()
            self._trace = None

    def __del__(self):
        try:
            self.close()
        except Exception:  # noqa: BLE001
            pass
