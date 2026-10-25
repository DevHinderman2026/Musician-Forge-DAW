"""M4A export: AAC audio in an MPEG-4 file, made by the AAC encoder built into Windows.

Windows Media Foundation (part of Windows 7 and later) does the encoding, so
Musician Forge needs no extra package for it. Windows "N" editions leave Media
Foundation out until the Media Feature Pack is installed; then M4A export
explains that, and WAV export still works.

The Media Foundation calls go through ctypes. The interface method numbers
below follow the Windows SDK headers (mfobjects.idl, mfreadwrite.idl):
IUnknown has 3 methods, IMFAttributes adds 30, and IMFSample and IMFMediaType
come after those.

describe_m4a() reads an .m4a file back (codec, sample rate, channels, length),
for the tests and the self check. It is plain Python and works anywhere.

read_with_media_foundation() (0.9.1) goes the other way for importing: Windows' own
decoders turn M4A, MP4, AAC, Windows Media Audio, MP3 and (on Windows 10 and later)
FLAC and Apple Lossless into floating point sound, through IMFSourceReader. Its
method numbers follow mfreadwrite.idl: IUnknown's 3, then GetStreamSelection (3),
SetStreamSelection (4), GetNativeMediaType (5), GetCurrentMediaType (6),
SetCurrentMediaType (7), SetCurrentPosition (8), ReadSample (9), Flush (10),
GetServiceForStream (11), GetPresentationAttribute (12). IMFSample's
ConvertToContiguousBuffer is method 41 (after IMFAttributes' 33 and eight of its own),
and IMFAttributes' GetUINT32 is method 7.
"""

import ctypes
import os
import struct
import sys

import numpy as np

from .paths import replace_file

KBPS = 192                     # the Windows AAC encoder offers 96, 128, 160 and 192 kbps
SAMPLE_RATES = (44100, 48000)  # what the Windows AAC encoder accepts

# HRESULTs worth explaining
MF_E_BAD_STARTUP_VERSION = 0xC00D36E3
MF_E_INVALIDMEDIATYPE = 0xC00D36B4
MF_E_TOPO_CODEC_NOT_FOUND = 0xC00D5212
MF_E_UNSUPPORTED_BYTESTREAM_TYPE = 0xC00D36C4
MF_E_INVALIDSTREAMNUMBER = 0xC00D36B3
MF_E_UNSUPPORTED_FORMAT = 0xC00D5209
MF_E_INVALIDMEDIATYPE_READ = 0xC00D36B4
MF_E_DRM_UNSUPPORTED = 0xC00D3E8B
NS_E_DRM_LICENSE_NOTACQUIRED = 0xC00D2759
ERROR_FILE_NOT_FOUND_HR = 0x80070002
RPC_E_CHANGED_MODE = 0x80010106


class M4AError(RuntimeError):
    """M4A export (or reading through Media Foundation) cannot work here; the message says why in plain words."""


class MediaFoundationMissing(M4AError):
    """This copy of Windows has no Media Foundation (Windows N editions without the Media Feature Pack)."""


class Cancelled(Exception):
    """Reading was cancelled."""


class TooLongForImport(M4AError):
    """The file is longer than an import may be."""


# ----------------------------------------------------------------------
# Media Foundation through ctypes (Windows only)
# ----------------------------------------------------------------------
class GUID(ctypes.Structure):
    _fields_ = [("Data1", ctypes.c_uint32), ("Data2", ctypes.c_uint16), ("Data3", ctypes.c_uint16),
                ("Data4", ctypes.c_ubyte * 8)]


def _guid(d1, d2, d3, *d4):
    return GUID(d1, d2, d3, (ctypes.c_ubyte * 8)(*d4))


def _media_subtype(code):
    """DEFINE_MEDIATYPE_GUID: a wave format number inside the standard audio GUID."""
    return _guid(code, 0x0000, 0x0010, 0x80, 0x00, 0x00, 0xAA, 0x00, 0x38, 0x9B, 0x71)


MF_MT_MAJOR_TYPE = _guid(0x48EBA18E, 0xF8C9, 0x4687, 0xBF, 0x11, 0x0A, 0x74, 0xC9, 0xF9, 0x6A, 0x8F)
MF_MT_SUBTYPE = _guid(0xF7E34C9A, 0x42E8, 0x4714, 0xB7, 0x4B, 0xCB, 0x29, 0xD7, 0x2C, 0x35, 0xE5)
MF_MT_AUDIO_NUM_CHANNELS = _guid(0x37E48BF5, 0x645E, 0x4C5B, 0x89, 0xDE, 0xAD, 0xA9, 0xE2, 0x9B, 0x69, 0x6A)
MF_MT_AUDIO_SAMPLES_PER_SECOND = _guid(0x5FAEEAE7, 0x0290, 0x4C31, 0x9E, 0x8A, 0xC5, 0x34, 0xF6, 0x8D, 0x9D, 0xBA)
MF_MT_AUDIO_AVG_BYTES_PER_SECOND = _guid(0x1AAB75C8, 0xCFEF, 0x451C, 0xAB, 0x95, 0xAC, 0x03, 0x4B, 0x8E, 0x17, 0x31)
MF_MT_AUDIO_BLOCK_ALIGNMENT = _guid(0x322DE230, 0x9EEB, 0x43BD, 0xAB, 0x7A, 0xFF, 0x41, 0x22, 0x51, 0x54, 0x1D)
MF_MT_AUDIO_BITS_PER_SAMPLE = _guid(0xF2DEB57F, 0x40FA, 0x4764, 0xAA, 0x33, 0xED, 0x4F, 0x2D, 0x1F, 0xF6, 0x69)
MF_MT_ALL_SAMPLES_INDEPENDENT = _guid(0xC9173739, 0x5E56, 0x461C, 0xB7, 0x13, 0x46, 0xFB, 0x99, 0x5C, 0xB9, 0x5F)
MFMediaType_Audio = _guid(0x73647561, 0x0000, 0x0010, 0x80, 0x00, 0x00, 0xAA, 0x00, 0x38, 0x9B, 0x71)
MFAudioFormat_PCM = _media_subtype(0x0001)        # WAVE_FORMAT_PCM
MFAudioFormat_Float = _media_subtype(0x0003)      # WAVE_FORMAT_IEEE_FLOAT
MFAudioFormat_AAC = _media_subtype(0x1610)        # WAVE_FORMAT_MPEG_HEAAC
MF_PD_DURATION = _guid(0x6C990D33, 0xBB8E, 0x477A, 0x85, 0x98, 0x0D, 0x5D, 0x96, 0xFC, 0xD8, 0x8A)

MF_VERSIONS = (0x00020070, 0x00010070)            # (MF_SDK_VERSION << 16) | MF_API_VERSION, newest first
MFSTARTUP_FULL = 0
COINIT_MULTITHREADED = 0

# vtable slots
RELEASE = 2
ATTR_GET_UINT32, ATTR_SET_UINT32, ATTR_SET_GUID = 7, 21, 24
SAMPLE_SET_TIME, SAMPLE_SET_DURATION, SAMPLE_CONTIGUOUS, SAMPLE_ADD_BUFFER = 36, 38, 41, 42
BUFFER_LOCK, BUFFER_UNLOCK, BUFFER_SET_LENGTH = 3, 4, 6
WRITER_ADD_STREAM, WRITER_SET_INPUT_TYPE, WRITER_BEGIN, WRITER_WRITE_SAMPLE, WRITER_FINALIZE = 3, 4, 5, 6, 11
READER_SET_SELECTION, READER_CURRENT_TYPE, READER_SET_TYPE, READER_READ, READER_ATTRIBUTE = 4, 6, 7, 9, 12
READER_FIRST_AUDIO_STREAM = 0xFFFFFFFD
READER_ALL_STREAMS = 0xFFFFFFFE
READER_MEDIASOURCE = 0xFFFFFFFF
READERF_ERROR, READERF_ENDOFSTREAM, READERF_TYPE_CHANGED = 0x1, 0x2, 0x20


def _hresult(value):
    return value & 0xFFFFFFFF


def _call(obj, slot, *args, argtypes=()):
    """Call method number `slot` of a COM object (a c_void_p); returns the HRESULT as unsigned."""
    vtable = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    prototype = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, *argtypes)
    return _hresult(prototype(vtable[slot])(obj, *args))


def _check(hr, what):
    if hr & 0x80000000:
        raise M4AError("{} failed (Windows error 0x{:08X})".format(what, hr))


def _release(obj):
    if obj:
        _call(obj, RELEASE)


class _MediaFoundation:
    """The Media Foundation functions Musician Forge uses, loaded on first use."""

    def __init__(self):
        if sys.platform != "win32":
            raise M4AError("M4A export works on Windows only")
        try:
            self.plat = ctypes.WinDLL("mfplat")
            self.readwrite = ctypes.WinDLL("mfreadwrite")
            self.ole32 = ctypes.WinDLL("ole32")
        except OSError:
            raise MediaFoundationMissing("M4A export needs Windows Media Foundation, which this copy of Windows "
                                         "does not have. On Windows N editions, install the Media Feature Pack "
                                         "from Microsoft. WAV export still works.") from None
        for name, args in (("MFStartup", (ctypes.c_ulong, ctypes.c_ulong)), ("MFShutdown", ()),
                           ("MFCreateMediaType", (ctypes.c_void_p,)), ("MFCreateSample", (ctypes.c_void_p,)),
                           ("MFCreateMemoryBuffer", (ctypes.c_ulong, ctypes.c_void_p))):
            fn = getattr(self.plat, name)
            fn.argtypes, fn.restype = args, ctypes.c_long
        fn = self.readwrite.MFCreateSinkWriterFromURL
        fn.argtypes = (ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
        fn.restype = ctypes.c_long
        fn = self.readwrite.MFCreateSourceReaderFromURL
        fn.argtypes = (ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_void_p)
        fn.restype = ctypes.c_long
        self.ole32.CoInitializeEx.argtypes = (ctypes.c_void_p, ctypes.c_ulong)
        self.ole32.CoInitializeEx.restype = ctypes.c_long
        self.ole32.CoUninitialize.argtypes = ()
        self.ole32.CoUninitialize.restype = None


def _media_type(mf, values):
    """A new IMFMediaType with the given (GUID key, GUID or int value) attributes."""
    media_type = ctypes.c_void_p()
    _check(_hresult(mf.plat.MFCreateMediaType(ctypes.byref(media_type))), "Creating a media type")
    try:
        for key, value in values:
            if isinstance(value, GUID):
                hr = _call(media_type, ATTR_SET_GUID, ctypes.byref(key), ctypes.byref(value),
                           argtypes=(ctypes.POINTER(GUID), ctypes.POINTER(GUID)))
            else:
                hr = _call(media_type, ATTR_SET_UINT32, ctypes.byref(key), int(value),
                           argtypes=(ctypes.POINTER(GUID), ctypes.c_uint32))
            _check(hr, "Describing the audio")
    except Exception:
        _release(media_type)
        raise
    return media_type


def to_pcm16(block):
    """Float audio (-1 to 1) as 16-bit samples, interleaved, ready for the encoder."""
    data = np.clip(np.asarray(block, dtype=np.float32), -1.0, 1.0)
    return np.round(data * 32767.0).astype("<i2").tobytes()


class M4AWriter:
    """Writes stereo float blocks into an .m4a file (AAC, 192 kbps), the way WavWriter writes WAV.

    The file is written under a temporary name and moved into place by close(), so a
    cancelled or failed export never leaves half a file behind."""

    def __init__(self, path, sample_rate=48000, channels=2, kbps=KBPS):
        if int(sample_rate) not in SAMPLE_RATES:
            raise M4AError("M4A export works at 44.1 or 48 kHz")
        self.path = path
        self.sample_rate = int(sample_rate)
        self.channels = int(channels)
        self.frames = 0
        self.tmp_path = None
        self._mf = _MediaFoundation()
        self._com = False
        self._started = False
        self._writer = ctypes.c_void_p()
        self._stream = ctypes.c_ulong(0)
        try:
            self._open(kbps)
        except Exception:
            self._shutdown()
            self._remove_tmp()
            raise

    def _open(self, kbps):
        mf = self._mf
        hr = _hresult(mf.ole32.CoInitializeEx(None, COINIT_MULTITHREADED))
        self._com = not hr & 0x80000000          # S_OK or S_FALSE must be balanced; RPC_E_CHANGED_MODE is fine
        for version in MF_VERSIONS:
            hr = _hresult(mf.plat.MFStartup(version, MFSTARTUP_FULL))
            if hr != MF_E_BAD_STARTUP_VERSION:
                break
        _check(hr, "Starting Windows Media Foundation")
        self._started = True
        folder = os.path.dirname(os.path.abspath(self.path))
        os.makedirs(folder, exist_ok=True)
        base = os.path.splitext(os.path.abspath(self.path))[0]
        last = 0
        for ext in (".m4a", ".mp4"):  # .mp4 is the same container, in case .m4a is not recognized
            tmp = base + ".partial" + ext
            if os.path.exists(tmp):
                os.remove(tmp)
            last = _hresult(mf.readwrite.MFCreateSinkWriterFromURL(tmp, None, None, ctypes.byref(self._writer)))
            if not last & 0x80000000:
                self.tmp_path = tmp
                break
            self._writer = ctypes.c_void_p()
        _check(last, "Creating the M4A file")
        avg_bytes = int(kbps) * 1000 // 8
        out_type = _media_type(mf, [(MF_MT_MAJOR_TYPE, MFMediaType_Audio), (MF_MT_SUBTYPE, MFAudioFormat_AAC),
                                    (MF_MT_AUDIO_BITS_PER_SAMPLE, 16),
                                    (MF_MT_AUDIO_SAMPLES_PER_SECOND, self.sample_rate),
                                    (MF_MT_AUDIO_NUM_CHANNELS, self.channels),
                                    (MF_MT_AUDIO_AVG_BYTES_PER_SECOND, avg_bytes)])
        try:
            hr = _call(self._writer, WRITER_ADD_STREAM, out_type, ctypes.byref(self._stream),
                       argtypes=(ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)))
        finally:
            _release(out_type)
        _check(hr, "Choosing the AAC encoder")
        block_align = 2 * self.channels
        in_type = _media_type(mf, [(MF_MT_MAJOR_TYPE, MFMediaType_Audio), (MF_MT_SUBTYPE, MFAudioFormat_PCM),
                                   (MF_MT_AUDIO_BITS_PER_SAMPLE, 16),
                                   (MF_MT_AUDIO_SAMPLES_PER_SECOND, self.sample_rate),
                                   (MF_MT_AUDIO_NUM_CHANNELS, self.channels),
                                   (MF_MT_AUDIO_BLOCK_ALIGNMENT, block_align),
                                   (MF_MT_AUDIO_AVG_BYTES_PER_SECOND, block_align * self.sample_rate),
                                   (MF_MT_ALL_SAMPLES_INDEPENDENT, 1)])
        try:
            hr = _call(self._writer, WRITER_SET_INPUT_TYPE, self._stream.value, in_type, None,
                       argtypes=(ctypes.c_ulong, ctypes.c_void_p, ctypes.c_void_p))
        finally:
            _release(in_type)
        if hr in (MF_E_INVALIDMEDIATYPE, MF_E_TOPO_CODEC_NOT_FOUND):
            raise M4AError("Windows could not find its AAC encoder (Windows error 0x{:08X}). "
                           "WAV export still works.".format(hr))
        _check(hr, "Setting up the AAC encoder")
        _check(_call(self._writer, WRITER_BEGIN), "Starting the M4A file")

    def write(self, block):
        """Add float audio shaped (frames, channels)."""
        block = np.asarray(block)
        if block.ndim == 1:
            block = block[:, None]
        if block.shape[1] != self.channels:
            block = np.repeat(block[:, :1], self.channels, axis=1) if block.shape[1] == 1 else block[:, :self.channels]
        frames = len(block)
        if not frames:
            return
        data = to_pcm16(block)
        mf = self._mf
        buffer, sample = ctypes.c_void_p(), ctypes.c_void_p()
        try:
            _check(_hresult(mf.plat.MFCreateMemoryBuffer(len(data), ctypes.byref(buffer))), "Making a buffer")
            where = ctypes.c_void_p()
            _check(_call(buffer, BUFFER_LOCK, ctypes.byref(where), None, None,
                         argtypes=(ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p, ctypes.c_void_p)),
                   "Filling a buffer")
            ctypes.memmove(where, data, len(data))
            _call(buffer, BUFFER_UNLOCK)
            _check(_call(buffer, BUFFER_SET_LENGTH, len(data), argtypes=(ctypes.c_ulong,)), "Filling a buffer")
            _check(_hresult(mf.plat.MFCreateSample(ctypes.byref(sample))), "Making a sample")
            _check(_call(sample, SAMPLE_ADD_BUFFER, buffer, argtypes=(ctypes.c_void_p,)), "Making a sample")
            start = self.frames * 10_000_000 // self.sample_rate          # 100-nanosecond units
            end = (self.frames + frames) * 10_000_000 // self.sample_rate
            _check(_call(sample, SAMPLE_SET_TIME, start, argtypes=(ctypes.c_longlong,)), "Timing a sample")
            _check(_call(sample, SAMPLE_SET_DURATION, end - start, argtypes=(ctypes.c_longlong,)), "Timing a sample")
            _check(_call(self._writer, WRITER_WRITE_SAMPLE, self._stream.value, sample,
                         argtypes=(ctypes.c_ulong, ctypes.c_void_p)), "Encoding audio")
        finally:
            _release(sample)
            _release(buffer)
        self.frames += frames

    def close(self):
        """Finish the file and move it into place."""
        try:
            _check(_call(self._writer, WRITER_FINALIZE), "Finishing the M4A file")
        except Exception:
            self.abort()
            raise
        self._shutdown()
        try:
            replace_file(self.tmp_path, self.path)
        except BaseException:
            self._remove_tmp()       # the old file held open by another program: no finished copy left beside it
            raise

    def abort(self):
        self._shutdown()
        self._remove_tmp()

    def _shutdown(self):
        if self._writer:
            _release(self._writer)
            self._writer = ctypes.c_void_p()
        if self._started:
            self._mf.plat.MFShutdown()
            self._started = False
        if self._com:
            self._mf.ole32.CoUninitialize()
            self._com = False

    def _remove_tmp(self):
        if self.tmp_path and os.path.exists(self.tmp_path):
            try:
                os.remove(self.tmp_path)
            except OSError:
                pass


class PROPVARIANT(ctypes.Structure):
    """Just enough of a PROPVARIANT for a duration (VT_UI8); 24 bytes, as on 64-bit Windows."""
    _fields_ = [("vt", ctypes.c_ushort), ("reserved1", ctypes.c_ushort), ("reserved2", ctypes.c_ushort),
                ("reserved3", ctypes.c_ushort), ("value", ctypes.c_ulonglong), ("extra", ctypes.c_ulonglong)]


VT_UI8 = 21


def _read_problem(hr, name):
    """Plain words for why Windows could not read a file."""
    if hr in (MF_E_UNSUPPORTED_BYTESTREAM_TYPE, MF_E_UNSUPPORTED_FORMAT, MF_E_TOPO_CODEC_NOT_FOUND):
        return "Windows does not know how to read this kind of file (Windows error 0x{:08X})".format(hr)
    if hr in (MF_E_DRM_UNSUPPORTED, NS_E_DRM_LICENSE_NOTACQUIRED):
        return "it is copy-protected, so no program may read its sound"
    if hr == MF_E_INVALIDSTREAMNUMBER:
        return "it has no sound in it"
    if hr == ERROR_FILE_NOT_FOUND_HR:
        return "Windows could not find {}".format(name)
    return "Windows could not read it (Windows error 0x{:08X})".format(hr)


def read_with_media_foundation(path, progress=None, cancelled=None, max_seconds=None):
    """Decode any audio file Windows can read into float32 audio shaped (frames, channels).
    Returns (audio, sample rate). Raises M4AError with words, Cancelled, or TooLongForImport."""
    mf = _MediaFoundation()
    name = os.path.basename(path)
    hr = _hresult(mf.ole32.CoInitializeEx(None, COINIT_MULTITHREADED))
    com = not hr & 0x80000000
    started = False
    reader = ctypes.c_void_p()
    try:
        for version in MF_VERSIONS:
            hr = _hresult(mf.plat.MFStartup(version, MFSTARTUP_FULL))
            if hr != MF_E_BAD_STARTUP_VERSION:
                break
        _check(hr, "Starting Windows Media Foundation")
        started = True
        hr = _hresult(mf.readwrite.MFCreateSourceReaderFromURL(os.path.abspath(path), None, ctypes.byref(reader)))
        if hr & 0x80000000:
            raise M4AError(_read_problem(hr, name))
        _call(reader, READER_SET_SELECTION, READER_ALL_STREAMS, 0, argtypes=(ctypes.c_ulong, ctypes.c_int))
        hr = _call(reader, READER_SET_SELECTION, READER_FIRST_AUDIO_STREAM, 1, argtypes=(ctypes.c_ulong, ctypes.c_int))
        if hr & 0x80000000:
            raise M4AError(_read_problem(hr, name))
        wanted = _media_type(mf, [(MF_MT_MAJOR_TYPE, MFMediaType_Audio), (MF_MT_SUBTYPE, MFAudioFormat_Float)])
        try:
            hr = _call(reader, READER_SET_TYPE, READER_FIRST_AUDIO_STREAM, None, wanted,
                       argtypes=(ctypes.c_ulong, ctypes.c_void_p, ctypes.c_void_p))
        finally:
            _release(wanted)
        if hr & 0x80000000:
            raise M4AError(_read_problem(hr, name))
        _call(reader, READER_SET_SELECTION, READER_FIRST_AUDIO_STREAM, 1, argtypes=(ctypes.c_ulong, ctypes.c_int))
        channels, rate, bits = _current_format(reader)
        if bits != 32 or channels < 1 or rate < 1:
            raise M4AError("Windows gave its sound in a form Musician Forge does not expect ({} channels, {} Hz, "
                           "{} bits)".format(channels, rate, bits))
        duration = _duration(mf, reader)
        pieces, frames = [], 0
        while True:
            if cancelled is not None and cancelled():
                raise Cancelled()
            index, flags, stamp, sample = ctypes.c_ulong(), ctypes.c_ulong(), ctypes.c_longlong(), ctypes.c_void_p()
            hr = _call(reader, READER_READ, READER_FIRST_AUDIO_STREAM, 0, ctypes.byref(index), ctypes.byref(flags),
                       ctypes.byref(stamp), ctypes.byref(sample),
                       argtypes=(ctypes.c_ulong, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong),
                                 ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_longlong),
                                 ctypes.POINTER(ctypes.c_void_p)))
            try:
                if hr & 0x80000000:
                    raise M4AError(_read_problem(hr, name))
                if flags.value & READERF_ERROR:
                    raise M4AError("Windows stopped reading it partway (the file may be damaged)")
                if flags.value & READERF_TYPE_CHANGED and _current_format(reader)[:2] != (channels, rate):
                    raise M4AError("its sound changes format partway through, which Musician Forge cannot import")
                if sample:
                    data = _sample_bytes(sample)
                    if data:
                        block = np.frombuffer(data, dtype="<f4")
                        block = block[:len(block) - len(block) % channels].reshape(-1, channels)
                        pieces.append(block.copy())
                        frames += len(block)
                        if max_seconds and frames > max_seconds * rate:
                            raise TooLongForImport("too long")
                        if progress is not None and duration:
                            progress(min(1.0, stamp.value / float(duration)))
                if flags.value & READERF_ENDOFSTREAM:
                    break
            finally:
                _release(sample)
        if not frames:
            raise M4AError("it has no sound in it")
        return np.concatenate(pieces), rate
    finally:
        _release(reader)
        if started:
            mf.plat.MFShutdown()
        if com:
            mf.ole32.CoUninitialize()


def _current_format(reader):
    """(channels, sample rate, bits) of what the reader hands back."""
    media_type = ctypes.c_void_p()
    _check(_call(reader, READER_CURRENT_TYPE, READER_FIRST_AUDIO_STREAM, ctypes.byref(media_type),
                 argtypes=(ctypes.c_ulong, ctypes.POINTER(ctypes.c_void_p))), "Reading the sound's format")
    try:
        values = []
        for key in (MF_MT_AUDIO_NUM_CHANNELS, MF_MT_AUDIO_SAMPLES_PER_SECOND, MF_MT_AUDIO_BITS_PER_SAMPLE):
            value = ctypes.c_uint32()
            hr = _call(media_type, ATTR_GET_UINT32, ctypes.byref(key), ctypes.byref(value),
                       argtypes=(ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_uint32)))
            values.append(value.value if not hr & 0x80000000 else 0)
        return tuple(values)
    finally:
        _release(media_type)


def _duration(mf, reader):
    """The file's length in 100-nanosecond units, or 0 if Windows does not say (only used for progress)."""
    value = PROPVARIANT()
    try:
        hr = _call(reader, READER_ATTRIBUTE, READER_MEDIASOURCE, ctypes.byref(MF_PD_DURATION), ctypes.byref(value),
                   argtypes=(ctypes.c_ulong, ctypes.POINTER(GUID), ctypes.POINTER(PROPVARIANT)))
        if hr & 0x80000000 or value.vt != VT_UI8:
            return 0
        return int(value.value)
    except OSError:
        return 0


def _sample_bytes(sample):
    """The bytes of one IMFSample, copied out."""
    buffer = ctypes.c_void_p()
    _check(_call(sample, SAMPLE_CONTIGUOUS, ctypes.byref(buffer), argtypes=(ctypes.POINTER(ctypes.c_void_p),)),
           "Reading the sound")
    try:
        where, length = ctypes.c_void_p(), ctypes.c_ulong()
        _check(_call(buffer, BUFFER_LOCK, ctypes.byref(where), None, ctypes.byref(length),
                     argtypes=(ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong))),
               "Reading the sound")
        try:
            return ctypes.string_at(where, length.value) if length.value and where.value else b""
        finally:
            _call(buffer, BUFFER_UNLOCK)
    finally:
        _release(buffer)


def m4a_size_bytes(seconds, kbps=KBPS):
    """About how big an M4A export will be."""
    return int(seconds * kbps * 1000 / 8) + 4096


# ----------------------------------------------------------------------
# reading an .m4a file back (any computer)
# ----------------------------------------------------------------------
CONTAINERS = {b"moov", b"trak", b"mdia", b"minf", b"stbl", b"udta", b"edts"}


def _boxes(data, start=0, end=None):
    """(type, body start, body end) for each box between start and end."""
    end = len(data) if end is None else end
    pos = start
    while pos + 8 <= end:
        size, kind = struct.unpack(">I4s", data[pos:pos + 8])
        header = 8
        if size == 1:
            size = struct.unpack(">Q", data[pos + 8:pos + 16])[0]
            header = 16
        elif size == 0:
            size = end - pos
        if size < header or pos + size > end:
            break
        yield kind, pos + header, pos + size
        pos += size


def describe_m4a(path):
    """{'brand', 'codec', 'sample_rate', 'channels', 'seconds'} for an MPEG-4 audio file.
    Raises ValueError if it is not one."""
    with open(path, "rb") as fh:
        data = fh.read()
    top = {kind: (a, b) for kind, a, b in _boxes(data)}
    if b"ftyp" not in top or b"moov" not in top:
        raise ValueError("not an MPEG-4 file")
    info = {"brand": data[top[b"ftyp"][0]:top[b"ftyp"][0] + 4].decode("latin-1"), "has_media": b"mdat" in top}

    def walk(a, b):
        for kind, start, stop in _boxes(data, a, b):
            if kind in CONTAINERS:
                walk(start, stop)
            elif kind == b"mdhd":
                version = data[start]
                if version == 1:
                    scale, duration = struct.unpack(">IQ", data[start + 20:start + 32])
                else:
                    scale, duration = struct.unpack(">II", data[start + 12:start + 20])
                info["seconds"] = duration / float(scale) if scale else 0.0
            elif kind == b"stsd":
                entries = list(_boxes(data, start + 8, stop))
                if entries:
                    codec, entry_start, _entry_end = entries[0]
                    info["codec"] = codec.decode("latin-1")
                    # audio sample entry: 6 reserved, 2 index, 8 reserved, channels, sample size, 4, rate 16.16
                    channels, = struct.unpack(">H", data[entry_start + 16:entry_start + 18])
                    rate, = struct.unpack(">I", data[entry_start + 24:entry_start + 28])
                    info["channels"] = channels
                    info["sample_rate"] = rate >> 16
    walk(*top[b"moov"])
    return info
