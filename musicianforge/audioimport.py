"""Importing audio files of every common kind (version 0.9.1; Russell, 8 Oct 2026: "import should accept
any kind of audio file, for example M4A and MP3, not only WAV").

Nothing new is downloaded (Russell's "it just works" rule): Musician Forge uses what is already there.
- WAV files Musician Forge can read itself (16-bit and 24-bit) are read directly.
- libsndfile reads WAV of every kind (8-bit, 32-bit float, ADPCM and more), MP3, FLAC, Ogg Vorbis,
  Ogg Opus, AIFF, Apple's CAF (with Apple Lossless inside), Wave 64, RF64 and AU. It comes with the
  FluidSynth download Musician Forge installs (sndfile.dll beside libfluidsynth-3.dll, a build with
  MP3, FLAC, Vorbis and Opus inside; checked 9 Oct 2026).
- Windows Media Foundation (part of Windows, the same route M4A export uses) reads M4A and MP4 audio
  (AAC, and Apple Lossless on Windows 10 and later), raw AAC, 3GP and Windows Media Audio, and MP3 and
  FLAC too if libsndfile cannot. Windows "N" editions leave it out until the Media Feature Pack is
  installed; then every other kind still imports.
Each kind is tried with the decoder that suits it first, then the others, so a file whose name ends
in the wrong extension still imports when anything can read it.

Every decoder returns float32 audio shaped (frames, channels) and its sample rate. The session
resamples it to 48 kHz and keeps its own copy in the project's Recordings folder.
"""

import ctypes
import ctypes.util
import logging
import os
import sys
from collections import namedtuple

import numpy as np

log = logging.getLogger("musicianforge.audioimport")

MAX_SECONDS = 30 * 60          # longer files are refused with words (a recording's copy must stay under 1 GB)
CHUNK_FRAMES = 1 << 16

# (what the open window calls them, file endings), in the order the open window lists them
KINDS = [
    ("WAV", ("wav", "wave")),
    ("MP3", ("mp3",)),
    ("M4A and MP4 audio (AAC or Apple Lossless)", ("m4a", "mp4", "aac", "adts", "3gp")),
    ("FLAC", ("flac",)),
    ("Ogg Vorbis and Opus", ("ogg", "oga", "opus")),
    ("AIFF", ("aif", "aiff", "aifc")),
    ("Windows Media Audio", ("wma", "asf")),
    ("Apple Core Audio (CAF)", ("caf",)),
    ("Wave 64 and RF64", ("w64", "rf64")),
    ("AU", ("au", "snd")),
]
EXTENSIONS = tuple(ext for _name, exts in KINDS for ext in exts)

Decoded = namedtuple("Decoded", "audio rate decoder")    # float32 (frames, channels), sample rate, who read it


MEDIA_FOUNDATION_MISSING = ("this kind of file is read by Windows Media Foundation, which this copy of Windows does "
                            "not have (Windows N editions leave it out): install the Media Feature Pack from "
                            "Microsoft. WAV, MP3, FLAC and Ogg files import without it")
WINDOWS_KINDS = ("m4a", "mp4", "aac", "adts", "3gp", "wma", "asf")   # only Windows' own decoders read these


class AudioImportError(ValueError):
    """The file could not be imported; the message says why in plain words."""


class TooLong(AudioImportError):
    """The file is longer than Musician Forge imports: no other reader is tried."""


class ImportCancelled(Exception):
    """The person cancelled a long import."""


class _Unavailable(Exception):
    """This decoder does not exist on this computer (a quiet reason to try the next one)."""


def wildcard():
    """The open window's list of kinds: all audio files first, then each kind."""
    patterns = ";".join("*." + ext for ext in EXTENSIONS)
    parts = ["All audio files ({})|{}".format(patterns, patterns)]
    for name, exts in KINDS:
        pattern = ";".join("*." + ext for ext in exts)
        parts.append("{} files ({})|{}".format(name, pattern, pattern))
    parts.append("All files (*.*)|*.*")
    return "|".join(parts)


def read(path, progress=None, cancelled=None):
    """Read an audio file. Returns Decoded; raises AudioImportError with words, or ImportCancelled.

    progress(fraction 0 to 1) is called now and then; cancelled() returning True stops the reading."""
    if not os.path.isfile(path):
        raise AudioImportError("{} is not there any more. It may have been moved or deleted.".format(
            os.path.basename(path)))
    if os.path.getsize(path) == 0:
        raise AudioImportError("{} is empty: the file holds no sound at all.".format(os.path.basename(path)))
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    if ext in ("wav", "wave"):
        order = [_read_simple_wav, _read_sndfile, _read_media_foundation]
    elif ext in WINDOWS_KINDS:
        order = [_read_media_foundation, _read_sndfile]
    else:
        order = [_read_sndfile, _read_media_foundation, _read_simple_wav]
    problems = []
    for decoder in order:
        try:
            decoded = decoder(path, progress, cancelled)
        except _Unavailable as exc:
            log.info("Import of %s: %s", path, exc)
            continue
        except TooLong:
            raise
        except AudioImportError as exc:
            log.info("Import of %s: %s", path, exc)
            problems.append(str(exc))
            continue
        audio = np.asarray(decoded.audio, dtype=np.float32)
        if audio.ndim == 1:
            audio = audio[:, None]
        if not len(audio):
            problems.append("it holds no sound")
            continue
        if not np.all(np.isfinite(audio)):
            audio = np.nan_to_num(audio, nan=0.0, posinf=1.0, neginf=-1.0)
        if audio.shape[1] > 2:          # surround sound: everything mixed into one channel, so nothing is lost
            audio = audio.mean(axis=1, keepdims=True)
        log.info("Imported %s with %s: %d frames, %d Hz, %d channel(s)", path, decoded.decoder, len(audio),
                 decoded.rate, audio.shape[1])
        return Decoded(audio, int(decoded.rate), decoded.decoder)
    name = os.path.basename(path)
    if problems:
        # for the kinds only Windows reads, Windows' answer says the most (the Media Feature Pack, for one)
        detail = problems[0] if ext in WINDOWS_KINDS else problems[-1]
        if detail == MEDIA_FOUNDATION_MISSING:
            raise AudioImportError("{} could not be imported: {}.".format(name, detail))
        raise AudioImportError("{} could not be imported: {}. If the file plays elsewhere, it may be copy-protected "
                               "or damaged; saving it again as WAV or MP3 in another program usually helps."
                               .format(name, detail.rstrip(".")))
    raise AudioImportError("{} could not be imported: no audio reader on this computer knows this kind of file. "
                           "WAV, MP3, M4A, FLAC, Ogg, AIFF and Windows Media Audio files work.".format(name))


def _check_length(frames, rate, name):
    if rate > 0 and frames / float(rate) > MAX_SECONDS:
        raise TooLong("{} is longer than {} minutes, which is more than Musician Forge imports in one go"
                               .format(name, MAX_SECONDS // 60))


# ----------------------------------------------------------------------
# WAV files Musician Forge reads itself
# ----------------------------------------------------------------------
def _read_simple_wav(path, progress=None, cancelled=None):
    from . import wavfile

    name = os.path.basename(path)
    try:
        audio, rate, _bits = wavfile.read_wav(path, np.float32, check=lambda frames, rate: _check_length(
            frames, rate, name), progress=progress, cancelled=cancelled)
    except TooLong:
        raise
    except wavfile.ReadCancelled:
        raise ImportCancelled() from None
    except Exception as exc:  # noqa: BLE001 - another decoder may manage
        raise AudioImportError("it is not a 16-bit or 24-bit WAV file ({})".format(exc)) from None
    if progress:
        progress(1.0)
    return Decoded(audio, rate, "Musician Forge's own WAV reader")


# ----------------------------------------------------------------------
# libsndfile
# ----------------------------------------------------------------------
SFM_READ = 0x10
SF_ERR_NO_ERROR = 0


class SF_INFO(ctypes.Structure):  # noqa: N801 - libsndfile's own name
    _fields_ = [("frames", ctypes.c_int64), ("samplerate", ctypes.c_int), ("channels", ctypes.c_int),
                ("format", ctypes.c_int), ("sections", ctypes.c_int), ("seekable", ctypes.c_int)]


_sndfile = None


def sndfile_candidates():
    """Where libsndfile may be: beside the FluidSynth engine Musician Forge installs, then the system's."""
    found = []
    override = os.environ.get("MUSICIANFORGE_SNDFILE_DLL")
    if override:
        found.append(override)
    try:
        from . import fluid

        for engine in fluid.candidate_library_paths():
            folder = os.path.dirname(engine)
            if not folder:
                continue
            for name in ("sndfile.dll", "libsndfile-1.dll", "libsndfile.dll"):
                path = os.path.join(folder, name)
                if os.path.isfile(path) and path not in found:
                    found.append(path)
    except Exception:  # noqa: BLE001 - no engine folder: the system's libsndfile may still be there
        pass
    for name in ("sndfile", "libsndfile-1", "libsndfile"):
        lib = ctypes.util.find_library(name)
        if lib and lib not in found:
            found.append(lib)
    return found


def load_sndfile():
    """libsndfile, loaded once; raises _Unavailable if it is nowhere to be found."""
    global _sndfile
    if _sndfile is not None:
        return _sndfile
    errors = []
    for path in sndfile_candidates():
        try:
            if sys.platform == "win32" and os.path.isabs(path) and hasattr(os, "add_dll_directory"):
                os.add_dll_directory(os.path.dirname(path))
            lib = ctypes.CDLL(path)
            lib.sf_open.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.POINTER(SF_INFO)]
            lib.sf_open.restype = ctypes.c_void_p
            if hasattr(lib, "sf_wchar_open"):
                lib.sf_wchar_open.argtypes = [ctypes.c_wchar_p, ctypes.c_int, ctypes.POINTER(SF_INFO)]
                lib.sf_wchar_open.restype = ctypes.c_void_p
            lib.sf_readf_float.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_float), ctypes.c_int64]
            lib.sf_readf_float.restype = ctypes.c_int64
            lib.sf_close.argtypes = [ctypes.c_void_p]
            lib.sf_close.restype = ctypes.c_int
            lib.sf_strerror.argtypes = [ctypes.c_void_p]
            lib.sf_strerror.restype = ctypes.c_char_p
            lib.sf_error.argtypes = [ctypes.c_void_p]
            lib.sf_error.restype = ctypes.c_int
            lib.sf_version_string.argtypes = []
            lib.sf_version_string.restype = ctypes.c_char_p
            log.info("Loaded %s from %s", lib.sf_version_string().decode("ascii", "replace"), path)
            _sndfile = lib
            return lib
        except (OSError, AttributeError) as exc:
            errors.append("{}: {}".format(path, exc))
    raise _Unavailable("libsndfile is not here ({})".format("; ".join(errors) or "not found"))


def sndfile_version():
    try:
        return load_sndfile().sf_version_string().decode("ascii", "replace")
    except _Unavailable:
        return None


def _read_sndfile(path, progress=None, cancelled=None):
    lib = load_sndfile()
    info = SF_INFO()
    if sys.platform == "win32" and hasattr(lib, "sf_wchar_open"):
        handle = lib.sf_wchar_open(os.path.abspath(path), SFM_READ, ctypes.byref(info))
    else:
        handle = lib.sf_open(os.fsencode(os.path.abspath(path)), SFM_READ, ctypes.byref(info))
    if not handle:
        reason = (lib.sf_strerror(None) or b"").decode("utf-8", "replace").strip()
        raise AudioImportError("the audio reader did not recognise it ({})".format(reason or "unknown reason"))
    name = os.path.basename(path)
    try:
        channels, rate = int(info.channels), int(info.samplerate)
        if channels < 1 or rate < 1:
            raise AudioImportError("it says it has {} channels at {} Hz".format(channels, rate))
        expected = int(info.frames) if 0 < info.frames < (1 << 40) else 0
        _check_length(expected, rate, name)
        pieces, total = [], 0
        while True:
            if cancelled is not None and cancelled():
                raise ImportCancelled()
            block = np.empty((CHUNK_FRAMES, channels), dtype=np.float32)
            got = int(lib.sf_readf_float(handle, block.ctypes.data_as(ctypes.POINTER(ctypes.c_float)), CHUNK_FRAMES))
            if got <= 0:
                break
            pieces.append(block[:got])
            total += got
            _check_length(total, rate, name)
            if progress is not None and expected:
                progress(min(1.0, total / float(expected)))
        error = lib.sf_error(handle)
        if error != SF_ERR_NO_ERROR and not total:
            reason = (lib.sf_strerror(handle) or b"").decode("utf-8", "replace").strip()
            raise AudioImportError("reading it failed ({})".format(reason))
        if not total:
            raise AudioImportError("it holds no sound")
        audio = np.concatenate(pieces) if len(pieces) > 1 else pieces[0]
        return Decoded(audio, rate, "libsndfile")
    finally:
        lib.sf_close(handle)


# ----------------------------------------------------------------------
# Windows Media Foundation (see m4a.py)
# ----------------------------------------------------------------------
def _read_media_foundation(path, progress=None, cancelled=None):
    if sys.platform != "win32":
        raise _Unavailable("Windows Media Foundation is part of Windows only")
    from . import m4a

    try:
        audio, rate = m4a.read_with_media_foundation(path, progress, cancelled, max_seconds=MAX_SECONDS)
    except m4a.Cancelled:
        raise ImportCancelled() from None
    except m4a.TooLongForImport:
        raise TooLong("{} is longer than {} minutes, which is more than Musician Forge imports in one go".format(
            os.path.basename(path), MAX_SECONDS // 60)) from None
    except m4a.MediaFoundationMissing:
        raise AudioImportError(MEDIA_FOUNDATION_MISSING) from None
    except m4a.M4AError as exc:
        raise AudioImportError(str(exc)) from None
    except OSError as exc:      # ctypes turns a fault inside Windows into OSError: explained, never a crash
        log.exception("Windows Media Foundation failed on %s", path)
        raise AudioImportError("Windows could not read it ({})".format(exc)) from None
    return Decoded(audio, rate, "Windows Media Foundation")


def write_test_file(path, audio, rate, major, subtype):
    """Write a file with libsndfile (tests make MP3, FLAC, Ogg and other files to import). major and
    subtype are libsndfile format numbers. Raises _Unavailable if this libsndfile cannot write it."""
    lib = load_sndfile()
    audio = np.ascontiguousarray(np.asarray(audio, dtype=np.float32))
    if audio.ndim == 1:
        audio = audio[:, None]
    info = SF_INFO(0, int(rate), int(audio.shape[1]), int(major | subtype), 0, 0)
    lib.sf_format_check.argtypes = [ctypes.POINTER(SF_INFO)]
    lib.sf_format_check.restype = ctypes.c_int
    if not lib.sf_format_check(ctypes.byref(info)):
        raise _Unavailable("this libsndfile cannot write format 0x{:X}".format(major | subtype))
    lib.sf_writef_float.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_float), ctypes.c_int64]
    lib.sf_writef_float.restype = ctypes.c_int64
    handle = lib.sf_open(os.fsencode(path), 0x20, ctypes.byref(info))          # SFM_WRITE
    if not handle:
        raise _Unavailable("this libsndfile cannot write {}: {}".format(
            path, (lib.sf_strerror(None) or b"").decode("utf-8", "replace")))
    try:
        lib.sf_writef_float(handle, audio.ctypes.data_as(ctypes.POINTER(ctypes.c_float)), len(audio))
    finally:
        lib.sf_close(handle)
