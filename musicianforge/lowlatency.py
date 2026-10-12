"""Hearing yourself sooner while recording: a low-latency path on Windows 10 and later (0.9.1).

Russell hears a little delay when he sings into the microphone with Hear the microphone while recording on
(8 Oct 2026). The usual way runs the microphone through PortAudio into Musician Forge's engine and back out
through PortAudio: Windows' shared mode, PortAudio's buffers on both sides and the engine's own block all add
up (others measured about 51 ms for the round trip with 256-sample buffers in shared mode).

Windows 10 added IAudioClient3, which lets a program ask for a shared-mode stream with a shorter period than
the usual 10 ms, when the sound driver allows it (often 128 samples, 2.7 ms, at 48 kHz). It stays shared mode,
so NVDA keeps talking (exclusive mode is never used: it would silence the screen reader). PortAudio cannot ask
for it (its issue 385, open since 2020), so this module talks to Windows directly through ctypes, the way M4A
export already does: one small microphone stream and one small output stream, both at the shortest period
the driver offers, and a thread that hands each piece of microphone sound straight to the output.

What you hear this way is the microphone itself, with the track's volume and pan but without its effects
(reverb, pitch correction and the rest play back once recorded). The song still plays through the engine as
before, and the recording itself is made exactly as before; only hearing yourself takes the short way. When
Windows or the driver cannot give a short stream, Musician Forge says why in words and you hear yourself the
usual way.

The interface method numbers follow the Windows SDK headers (audioclient.idl, mmdeviceapi.idl; checked
against mingw-w64's copies on 9 Oct 2026): IUnknown has 3 methods; IAudioClient adds 12 (Initialize is 3,
GetBufferSize 4, GetStreamLatency 5, GetCurrentPadding 6, IsFormatSupported 7, GetMixFormat 8,
GetDevicePeriod 9, Start 10, Stop 11, Reset 12, SetEventHandle 13, GetService 14), IAudioClient2 three more
(IsOffloadCapable 15, SetClientProperties 16, GetBufferSizeLimits 17) and IAudioClient3 three more
(GetSharedModeEnginePeriod 18, GetCurrentSharedModeEnginePeriod 19, InitializeSharedAudioStream 20).

engine_periods() only reads (for Diagnose and the Audio settings check). Standard library only, apart from
the monitor itself, which needs numpy.
"""

import ctypes
import logging
import sys
import threading

log = logging.getLogger("musicianforge.lowlatency")

COINIT_MULTITHREADED = 0
CLSCTX_ALL = 0x17
STGM_READ = 0
E_RENDER, E_CAPTURE = 0, 1
E_CONSOLE = 0
DEVICE_STATE_ACTIVE = 1
VT_LPWSTR = 31
AUDCLNT_STREAMFLAGS_EVENTCALLBACK = 0x00040000
AUDCLNT_STREAMOPTIONS_RAW = 0x1
AUDCLNT_BUFFERFLAGS_SILENT = 0x2
AUDCLNT_S_BUFFER_EMPTY = 0x08890001
WAIT_OBJECT_0, WAIT_TIMEOUT, WAIT_FAILED = 0, 0x102, 0xFFFFFFFF
RPC_E_CHANGED_MODE = 0x80010106
WAVE_FORMAT_IEEE_FLOAT, WAVE_FORMAT_EXTENSIBLE = 0x0003, 0xFFFE

# vtable slots
RELEASE = 2
ENUM_ENDPOINTS, ENUM_DEFAULT = 3, 4
COLLECTION_COUNT, COLLECTION_ITEM = 3, 4
DEVICE_ACTIVATE, DEVICE_PROPERTIES = 3, 4
STORE_GET_VALUE = 5
CLIENT_BUFFER_SIZE, CLIENT_PADDING, CLIENT_MIX_FORMAT = 4, 6, 8
CLIENT_START, CLIENT_STOP, CLIENT_SET_EVENT, CLIENT_SERVICE = 10, 11, 13, 14
CLIENT_SET_PROPERTIES = 16
CLIENT_ENGINE_PERIOD, CLIENT_CURRENT_PERIOD, CLIENT_INIT_SHARED = 18, 19, 20
RENDER_GET_BUFFER, RENDER_RELEASE_BUFFER = 3, 4
CAPTURE_GET_BUFFER, CAPTURE_RELEASE_BUFFER, CAPTURE_NEXT_PACKET = 3, 4, 5

# Windows' errors worth saying in words (AUDCLNT_ERR(n) is 0x88890000 + n)
AUDCLNT_E_DEVICE_INVALIDATED = 0x88890004
AUDCLNT_E_UNSUPPORTED_FORMAT = 0x88890008
AUDCLNT_E_DEVICE_IN_USE = 0x8889000A
AUDCLNT_E_SERVICE_NOT_RUNNING = 0x88890010
AUDCLNT_E_RAW_MODE_UNSUPPORTED = 0x88890027
AUDCLNT_E_ENGINE_PERIODICITY_LOCKED = 0x88890028
AUDCLNT_E_ENGINE_FORMAT_LOCKED = 0x88890029
E_NOINTERFACE = 0x80004002
E_NOTFOUND = 0x80070490

PROBLEMS = {
    AUDCLNT_E_DEVICE_INVALIDATED: "the device was unplugged or switched off",
    AUDCLNT_E_UNSUPPORTED_FORMAT: "the device does not accept Windows' own sound format",
    AUDCLNT_E_DEVICE_IN_USE: "another program is using the device on its own (exclusive mode)",
    AUDCLNT_E_SERVICE_NOT_RUNNING: "the Windows Audio service is not running",
    AUDCLNT_E_RAW_MODE_UNSUPPORTED: "the device cannot give raw sound",
    AUDCLNT_E_ENGINE_PERIODICITY_LOCKED: "another program has fixed how often Windows mixes sound on this device",
    AUDCLNT_E_ENGINE_FORMAT_LOCKED: "another program has fixed the device's sound format",
    E_NOINTERFACE: "this version of Windows has no low-latency shared streams (they came with Windows 10)",
    E_NOTFOUND: "the device was not found",
}


class Unavailable(RuntimeError):
    """The low-latency path cannot be used here; the message says why in words."""


class DeviceLost(RuntimeError):
    """A stream stopped working while running (unplugged, or Windows reset the device)."""


def problem_words(hr):
    hr &= 0xFFFFFFFF
    words = PROBLEMS.get(hr)
    return "{} (Windows error 0x{:08X})".format(words, hr) if words else "Windows error 0x{:08X}".format(hr)


# ----------------------------------------------------------------------
# COM through ctypes (Windows only)
# ----------------------------------------------------------------------
class GUID(ctypes.Structure):
    _fields_ = [("Data1", ctypes.c_uint32), ("Data2", ctypes.c_uint16), ("Data3", ctypes.c_uint16),
                ("Data4", ctypes.c_ubyte * 8)]


def _guid(text):
    """A GUID from its usual written form, '1cb9ad4c-dbfa-4c32-b178-c2f568a703b2'."""
    parts = text.split("-")
    tail = bytes.fromhex(parts[3] + parts[4])
    return GUID(int(parts[0], 16), int(parts[1], 16), int(parts[2], 16), (ctypes.c_ubyte * 8)(*tail))


CLSID_MMDeviceEnumerator = _guid("bcde0395-e52f-467c-8e3d-c4579291692e")
IID_IMMDeviceEnumerator = _guid("a95664d2-9614-4f35-a746-de8db63617e6")
IID_IAudioClient3 = _guid("7ed4ee07-8e67-4cd4-8c1a-2b7a5987ad42")
IID_IAudioRenderClient = _guid("f294acfc-3146-4483-a7bf-addca7c260e2")
IID_IAudioCaptureClient = _guid("c8adbd64-e71e-48a0-a4de-185c395cd317")
KSDATAFORMAT_SUBTYPE_IEEE_FLOAT = _guid("00000003-0000-0010-8000-00aa00389b71")


class PROPERTYKEY(ctypes.Structure):
    _fields_ = [("fmtid", GUID), ("pid", ctypes.c_uint32)]


PKEY_Device_FriendlyName = PROPERTYKEY(_guid("a45c254e-df1c-4efd-8020-67d146a850e0"), 14)


class PROPVARIANT(ctypes.Structure):
    """Enough of a PROPVARIANT for a string (VT_LPWSTR): 24 bytes, as on 64-bit Windows."""
    _fields_ = [("vt", ctypes.c_ushort), ("reserved1", ctypes.c_ushort), ("reserved2", ctypes.c_ushort),
                ("reserved3", ctypes.c_ushort), ("pointer", ctypes.c_void_p), ("extra", ctypes.c_void_p)]


class WAVEFORMATEX(ctypes.Structure):
    """18 bytes: Windows packs it with no padding (mmreg.h uses #pragma pack(1)); without _pack_ ctypes would pad
    it to 20 and read everything after it from the wrong place."""
    _pack_ = 1
    _fields_ = [("wFormatTag", ctypes.c_uint16), ("nChannels", ctypes.c_uint16), ("nSamplesPerSec", ctypes.c_uint32),
                ("nAvgBytesPerSec", ctypes.c_uint32), ("nBlockAlign", ctypes.c_uint16),
                ("wBitsPerSample", ctypes.c_uint16), ("cbSize", ctypes.c_uint16)]


class WAVEFORMATEXTENSIBLE(ctypes.Structure):
    """40 bytes, packed the same way: the sample kind (SubFormat) starts at byte 24."""
    _pack_ = 1
    _fields_ = [("Format", WAVEFORMATEX), ("wValidBitsPerSample", ctypes.c_uint16), ("dwChannelMask", ctypes.c_uint32),
                ("SubFormat", GUID)]


class AudioClientProperties(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint32), ("bIsOffload", ctypes.c_int32), ("eCategory", ctypes.c_int32),
                ("Options", ctypes.c_int32)]


def _failed(hr):
    return bool(hr & 0x80000000)


def _method(obj, slot, *argtypes):
    """Method number `slot` of a COM object, bound once (the monitor calls some of them hundreds of times a
    second). Calling it returns the HRESULT as an unsigned number."""
    vtable = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    function = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, *argtypes)(vtable[slot])

    def call(*args):
        return function(obj, *args) & 0xFFFFFFFF
    return call


def _release(obj):
    if obj is not None and obj.value:
        _method(obj, RELEASE)()
        obj.value = None


class _Windows:
    """The few Windows functions this module needs, loaded on first use."""

    _loaded = None

    @classmethod
    def get(cls):
        if cls._loaded is None:
            cls._loaded = cls()
        return cls._loaded

    def __init__(self):
        if sys.platform != "win32":
            raise Unavailable("low-latency hearing yourself works on Windows only")
        self.ole32 = ctypes.WinDLL("ole32")
        self.kernel32 = ctypes.WinDLL("kernel32")
        try:
            self.avrt = ctypes.WinDLL("avrt")
        except OSError:
            self.avrt = None
        self.ole32.CoInitializeEx.argtypes = (ctypes.c_void_p, ctypes.c_ulong)
        self.ole32.CoInitializeEx.restype = ctypes.c_long
        self.ole32.CoUninitialize.argtypes = ()
        self.ole32.CoUninitialize.restype = None
        self.ole32.CoCreateInstance.argtypes = (ctypes.POINTER(GUID), ctypes.c_void_p, ctypes.c_ulong,
                                                ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p))
        self.ole32.CoCreateInstance.restype = ctypes.c_long
        self.ole32.CoTaskMemFree.argtypes = (ctypes.c_void_p,)
        self.ole32.CoTaskMemFree.restype = None
        self.ole32.PropVariantClear.argtypes = (ctypes.POINTER(PROPVARIANT),)
        self.ole32.PropVariantClear.restype = ctypes.c_long
        k = self.kernel32
        k.CreateEventW.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_wchar_p)
        k.CreateEventW.restype = ctypes.c_void_p
        k.SetEvent.argtypes = (ctypes.c_void_p,)
        k.SetEvent.restype = ctypes.c_int
        k.CloseHandle.argtypes = (ctypes.c_void_p,)
        k.CloseHandle.restype = ctypes.c_int
        k.WaitForMultipleObjects.argtypes = (ctypes.c_ulong, ctypes.POINTER(ctypes.c_void_p), ctypes.c_int,
                                             ctypes.c_ulong)
        k.WaitForMultipleObjects.restype = ctypes.c_ulong
        if self.avrt is not None:
            self.avrt.AvSetMmThreadCharacteristicsW.argtypes = (ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_ulong))
            self.avrt.AvSetMmThreadCharacteristicsW.restype = ctypes.c_void_p
            self.avrt.AvRevertMmThreadCharacteristics.argtypes = (ctypes.c_void_p,)
            self.avrt.AvRevertMmThreadCharacteristics.restype = ctypes.c_int


class _Com:
    """COM switched on for the thread that uses it (and off again afterwards, when this switched it on)."""

    def __init__(self):
        self.win = _Windows.get()
        hr = self.win.ole32.CoInitializeEx(None, COINIT_MULTITHREADED) & 0xFFFFFFFF
        self.started = not _failed(hr)            # RPC_E_CHANGED_MODE: the thread already has COM (a window)
        if _failed(hr) and hr != RPC_E_CHANGED_MODE:
            raise Unavailable("Windows' sound system could not be started ({})".format(problem_words(hr)))

    def close(self):
        if self.started:
            self.win.ole32.CoUninitialize()
            self.started = False


def _enumerator(win):
    enum = ctypes.c_void_p()
    hr = win.ole32.CoCreateInstance(ctypes.byref(CLSID_MMDeviceEnumerator), None, CLSCTX_ALL,
                                    ctypes.byref(IID_IMMDeviceEnumerator), ctypes.byref(enum)) & 0xFFFFFFFF
    if _failed(hr):
        raise Unavailable("Windows' list of sound devices could not be read ({})".format(problem_words(hr)))
    return enum


def _friendly_name(win, device):
    store = ctypes.c_void_p()
    if _failed(_method(device, DEVICE_PROPERTIES, ctypes.c_ulong, ctypes.POINTER(ctypes.c_void_p))(
            STGM_READ, ctypes.byref(store))):
        return ""
    value = PROPVARIANT()
    try:
        hr = _method(store, STORE_GET_VALUE, ctypes.POINTER(PROPERTYKEY), ctypes.POINTER(PROPVARIANT))(
            ctypes.byref(PKEY_Device_FriendlyName), ctypes.byref(value))
        if _failed(hr) or value.vt != VT_LPWSTR or not value.pointer:
            return ""
        return ctypes.wstring_at(value.pointer)
    finally:
        win.ole32.PropVariantClear(ctypes.byref(value))
        _release(store)


def name_matches(wanted, friendly):
    """Whether a device chosen in Audio settings (PortAudio's name for it) is this Windows endpoint. WASAPI names
    are the endpoint's own; MME cuts names to 31 characters."""
    wanted, friendly = (wanted or "").strip().lower(), (friendly or "").strip().lower()
    if not wanted or not friendly:
        return False
    return wanted == friendly or (len(wanted) >= 31 and friendly.startswith(wanted))


def _find_device(win, enum, flow, wanted):
    """(IMMDevice, its name): the endpoint chosen in Audio settings, or Windows' default when none is chosen or it is
    not found (that is said in the log)."""
    if wanted:
        collection = ctypes.c_void_p()
        hr = _method(enum, ENUM_ENDPOINTS, ctypes.c_int, ctypes.c_ulong, ctypes.POINTER(ctypes.c_void_p))(
            flow, DEVICE_STATE_ACTIVE, ctypes.byref(collection))
        if not _failed(hr):
            try:
                count = ctypes.c_uint()
                _method(collection, COLLECTION_COUNT, ctypes.POINTER(ctypes.c_uint))(ctypes.byref(count))
                for index in range(count.value):
                    device = ctypes.c_void_p()
                    if _failed(_method(collection, COLLECTION_ITEM, ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p))(
                            index, ctypes.byref(device))):
                        continue
                    name = _friendly_name(win, device)
                    if name_matches(wanted, name):
                        return device, name
                    _release(device)
            finally:
                _release(collection)
        log.info("Low latency: %s was not found among Windows' %s devices; using the default", wanted,
                 "output" if flow == E_RENDER else "microphone")
    device = ctypes.c_void_p()
    hr = _method(enum, ENUM_DEFAULT, ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p))(
        flow, E_CONSOLE, ctypes.byref(device))
    if _failed(hr):
        raise Unavailable("Windows has no {} ({})".format("output device" if flow == E_RENDER else "microphone",
                                                        problem_words(hr)))
    return device, _friendly_name(win, device)


class Format:
    """The sound format Windows mixes a device in (its mix format)."""

    def __init__(self, rate, channels, bits, is_float):
        self.rate, self.channels, self.bits, self.is_float = int(rate), int(channels), int(bits), bool(is_float)

    @classmethod
    def read(cls, pointer):
        base = ctypes.cast(pointer, ctypes.POINTER(WAVEFORMATEX)).contents
        is_float = base.wFormatTag == WAVE_FORMAT_IEEE_FLOAT
        if base.wFormatTag == WAVE_FORMAT_EXTENSIBLE and base.cbSize >= 22:
            sub = ctypes.cast(pointer, ctypes.POINTER(WAVEFORMATEXTENSIBLE)).contents.SubFormat
            is_float = bytes(sub) == bytes(KSDATAFORMAT_SUBTYPE_IEEE_FLOAT)
        return cls(base.nSamplesPerSec, base.nChannels, base.wBitsPerSample, is_float)

    def describe(self):
        return "{:g} kHz, {} channel{}, {}-bit{}".format(self.rate / 1000.0, self.channels,
                                                         "" if self.channels == 1 else "s", self.bits,
                                                         " floating point" if self.is_float else "")


class Periods:
    """How often Windows mixes a device in shared mode, in samples: its usual period, the smallest step, and the
    shortest and longest a low-latency stream may ask for."""

    def __init__(self, default, fundamental, minimum, maximum, rate):
        self.default, self.fundamental, self.minimum, self.maximum = (int(default), int(fundamental), int(minimum),
                                                                      int(maximum))
        self.rate = int(rate)

    def ms(self, frames):
        return 1000.0 * frames / float(self.rate or 48000)

    @property
    def low_latency(self):
        return 0 < self.minimum < self.default

    def describe(self):
        if self.low_latency:
            return ("low-latency streams from {} samples ({:.1f} ms) up to {} ({:.1f} ms); the usual is {} samples "
                    "({:.1f} ms)").format(self.minimum, self.ms(self.minimum), self.maximum, self.ms(self.maximum),
                                          self.default, self.ms(self.default))
        return ("only the usual {} samples ({:.1f} ms): the sound driver offers no shorter period, so hearing yourself "
                "gains less (a newer driver, or Windows' own High Definition Audio driver, may offer more)").format(
                    self.default, self.ms(self.default))


def _activate(device):
    client = ctypes.c_void_p()
    hr = _method(device, DEVICE_ACTIVATE, ctypes.POINTER(GUID), ctypes.c_ulong, ctypes.c_void_p,
                 ctypes.POINTER(ctypes.c_void_p))(ctypes.byref(IID_IAudioClient3), CLSCTX_ALL, None,
                                                  ctypes.byref(client))
    if _failed(hr):
        raise Unavailable(problem_words(hr))
    return client


def _mix_format(win, client):
    pointer = ctypes.c_void_p()
    hr = _method(client, CLIENT_MIX_FORMAT, ctypes.POINTER(ctypes.c_void_p))(ctypes.byref(pointer))
    if _failed(hr):
        raise Unavailable("the device's sound format could not be read ({})".format(problem_words(hr)))
    return pointer


def _periods(client, pointer, rate):
    values = [ctypes.c_uint32() for _ in range(4)]
    hr = _method(client, CLIENT_ENGINE_PERIOD, ctypes.c_void_p, *([ctypes.POINTER(ctypes.c_uint32)] * 4))(
        pointer, *[ctypes.byref(v) for v in values])
    if _failed(hr):
        raise Unavailable(problem_words(hr))
    return Periods(*[v.value for v in values], rate=rate)


def engine_periods(output_name="", input_name=""):
    """What Windows offers for the output and the microphone, read only:
    [{"kind": "output" or "microphone", "name": ..., "format": Format or None, "periods": Periods or None,
      "problem": words or ""}]. An empty list when this is not Windows."""
    if sys.platform != "win32":
        return []
    found = []
    try:
        com = _Com()
    except (Unavailable, OSError) as exc:
        return [{"kind": "output", "name": "", "format": None, "periods": None, "problem": str(exc)}]
    try:
        win = com.win
        enum = _enumerator(win)
        try:
            for kind, flow, wanted in (("output", E_RENDER, output_name), ("microphone", E_CAPTURE, input_name)):
                entry = {"kind": kind, "name": wanted or "", "format": None, "periods": None, "problem": ""}
                device = client = pointer = None
                try:
                    device, entry["name"] = _find_device(win, enum, flow, wanted)
                    client = _activate(device)
                    pointer = _mix_format(win, client)
                    entry["format"] = Format.read(pointer)
                    entry["periods"] = _periods(client, pointer, entry["format"].rate)
                except Unavailable as exc:
                    entry["problem"] = str(exc)
                finally:
                    if pointer is not None and pointer.value:
                        win.ole32.CoTaskMemFree(pointer)
                    _release(client)
                    _release(device)
                found.append(entry)
        finally:
            _release(enum)
    except Unavailable as exc:
        found.append({"kind": "output", "name": "", "format": None, "periods": None, "problem": str(exc)})
    finally:
        com.close()
    return found


def describe_entry(entry):
    """'Output, Speakers (Realtek(R) Audio): 48 kHz, 2 channels, 32-bit floating point; low-latency streams
    from 128 samples (2.7 ms) ...'."""
    title = "{}, {}".format("Output" if entry["kind"] == "output" else "Microphone", entry["name"] or "unknown")
    if entry["problem"]:
        return "{}: low latency is not available: {}".format(title, entry["problem"])
    return "{}: {}; {}".format(title, entry["format"].describe(), entry["periods"].describe())


def describe_support(output_name="", input_name=""):
    """In words, for the Audio settings check and Diagnose: what each device offers and what that means."""
    entries = in_own_thread(lambda: engine_periods(output_name, input_name))
    if not entries:
        return "Low-latency hearing yourself needs Windows 10 or later."
    lines = [describe_entry(e) for e in entries]
    good = [e for e in entries if not e["problem"]]
    odd = [e for e in good if not e["format"].is_float]
    if odd:
        lines.append("Windows mixes the {} in a format the low-latency way does not handle ({}), so you hear "
                     "yourself the usual way.".format(odd[0]["kind"], odd[0]["format"].describe()))
    elif len(good) == 2 and good[0]["format"].rate != good[1]["format"].rate:
        lines.append("The output and the microphone run at different sample rates ({:g} and {:g} kHz), so the "
                     "low-latency way cannot join them; set both to the same rate in Windows' Sound settings."
                     .format(good[0]["format"].rate / 1000.0, good[1]["format"].rate / 1000.0))
    elif len(good) == 2:
        estimate = sum(e["periods"].ms(e["periods"].minimum if e["periods"].low_latency else e["periods"].default)
                       for e in good) * 2.5
        lines.append("Hearing yourself the low-latency way could take about {:.0f} ms plus the devices' own delay "
                     "(wired headphones; Bluetooth adds a fifth of a second or more).".format(estimate))
    return " ".join(lines)


def in_own_thread(work, timeout=10.0):
    """Run `work` in a thread of its own (with COM of its own), so a window's thread is never involved."""
    result = {}

    def run():
        try:
            result["value"] = work()
        except Exception as exc:  # noqa: BLE001 - said in words by the caller
            result["error"] = exc

    thread = threading.Thread(target=run, name="Musician Forge low-latency check", daemon=True)
    thread.start()
    thread.join(timeout)
    if thread.is_alive():
        raise Unavailable("Windows did not answer within {:g} seconds".format(timeout))
    if "error" in result:
        raise result["error"]
    return result.get("value", [])


# ----------------------------------------------------------------------
# the sound in between: what the microphone gave, waiting to be heard
# ----------------------------------------------------------------------
class MonitorBuffer:
    """Microphone sound on its way to the output (pure numpy, so it is tested anywhere).

    The output stream keeps `target` samples queued in Windows' buffer: enough to ride over the moments the
    microphone's pieces arrive late, no more. When the queue would run dry before the microphone catches up,
    silence fills the gap and the target grows by one period (up to `most`), the way the usual way's buffer
    does. When sound piles up (the microphone's clock runs a little fast), the oldest is skipped with a short
    crossfade, so hearing yourself never drifts later."""

    FADE = 32

    def __init__(self, period, capture_period=None, start_periods=2, most_ms=20.0, rate=48000):
        import numpy as np  # noqa: PLC0415 - only the monitor needs numpy

        self.np = np
        self.rate = int(rate)
        self.period = max(1, int(period))
        self.capture_period = max(1, int(capture_period or period))
        self.target = self.period * max(1, int(start_periods))
        self.most = max(self.target, int(round(most_ms * rate / 1000.0)))
        self.waiting = np.zeros((0, 2), dtype=np.float32)
        self.in_gap = False
        from .startfade import StartFade  # noqa: PLC0415 - with numpy, only here

        self.start_fade = StartFade(self.rate)     # its own microphone opens with it: no pop as it starts
        self.stats = {"pieces": 0, "frames_in": 0, "frames_out": 0, "gaps": 0, "silence": 0, "skips": 0,
                      "skipped": 0, "most_queued": 0, "queued_sum": 0, "tops": 0}

    def push(self, block):
        """A piece of microphone sound, already shaped to (frames, 2)."""
        np = self.np
        self.stats["pieces"] += 1
        self.stats["frames_in"] += len(block)
        block = self.start_fade.apply(block)
        self.waiting = block if not len(self.waiting) else np.concatenate([self.waiting, block])
        limit = self.capture_period + self.period          # one piece, and a period of slack
        extra = len(self.waiting) - limit
        if extra > self.FADE:
            fade = self.FADE
            ramp = ((np.arange(fade, dtype=np.float32) + 0.5) / fade)[:, None]
            kept = self.waiting[extra:].copy()
            kept[:fade] = self.waiting[:fade] * (1.0 - ramp) + kept[:fade] * ramp
            self.waiting = kept
            self.stats["skips"] += 1
            self.stats["skipped"] += extra

    def pull(self, padding, space):
        """What to give the output now, when `padding` samples are still queued in Windows and `space` more fit:
        (sound to write or None, silence samples to write after it)."""
        np = self.np
        want = min(self.target - padding, space)
        if want <= 0:
            return None, 0
        take = min(want, len(self.waiting))
        sound = self.waiting[:take] if take else None
        if take:
            self.waiting = self.waiting[take:]
        silence = 0
        if padding + take < self.period:
            # the microphone is late: fill one period so Windows never runs dry, and (once for each time it is
            # late) keep one period more queued from now on
            silence = min(space - take, self.period - (padding + take))
            self.stats["silence"] += silence
            if not self.in_gap:
                self.in_gap = True
                self.stats["gaps"] += 1
                self.target = min(self.most, self.target + self.period)
        else:
            self.in_gap = False
        queued = padding + take + silence
        self.stats["frames_out"] += take
        self.stats["tops"] += 1
        self.stats["queued_sum"] += queued
        self.stats["most_queued"] = max(self.stats["most_queued"], queued)
        return (np.ascontiguousarray(sound) if sound is not None else None), silence


def shape(block, stereo, left, right):
    """A piece from the microphone, (frames, channels) as float32, as the track hears it: (frames, 2) with the
    track's volume and pan. A mono track hears the channels mixed; a stereo track the first two."""
    import numpy as np  # noqa: PLC0415

    block = np.asarray(block, dtype=np.float32)
    if block.ndim == 1:
        block = block[:, None]
    if stereo and block.shape[1] >= 2:
        pair = block[:, :2]
    else:
        mono = block.mean(axis=1) if block.shape[1] > 1 else block[:, 0]
        pair = np.stack([mono, mono], axis=1)
    out = np.empty((len(pair), 2), dtype=np.float32)
    out[:, 0] = pair[:, 0] * left
    out[:, 1] = pair[:, 1] * right
    return out


# ----------------------------------------------------------------------
# the streams (Windows) and the monitor
# ----------------------------------------------------------------------
class _Stream:
    """One low-latency shared-mode stream: the microphone (capture) or the output (render)."""

    def __init__(self, win, device, name, capture, raw=False):
        self.win, self.name, self.capture = win, name, capture
        self.client = self.service = None
        self.event = None
        self.raw = False
        self.note = ""
        try:
            self._open(device, raw)
        except BaseException:
            self.close()
            raise

    def _open(self, device, raw):
        win, capture = self.win, self.capture
        pointer = None
        try:
            self.client = _activate(device)
            pointer = _mix_format(win, self.client)
            self.format = Format.read(pointer)
            self.periods = _periods(self.client, pointer, self.format.rate)
            if raw:
                self.raw = self._ask_raw()
            self.period = self._initialize(device, pointer)
        finally:
            if pointer is not None and pointer.value:
                win.ole32.CoTaskMemFree(pointer)
        self.event = win.kernel32.CreateEventW(None, 0, 0, None)
        hr = _method(self.client, CLIENT_SET_EVENT, ctypes.c_void_p)(self.event)
        if _failed(hr):
            raise Unavailable(problem_words(hr))
        size = ctypes.c_uint32()
        hr = _method(self.client, CLIENT_BUFFER_SIZE, ctypes.POINTER(ctypes.c_uint32))(ctypes.byref(size))
        if _failed(hr):
            raise Unavailable(problem_words(hr))
        self.buffer_frames = size.value
        self.service = ctypes.c_void_p()
        iid = IID_IAudioCaptureClient if capture else IID_IAudioRenderClient
        hr = _method(self.client, CLIENT_SERVICE, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p))(
            ctypes.byref(iid), ctypes.byref(self.service))
        if _failed(hr):
            raise Unavailable(problem_words(hr))
        self._start = _method(self.client, CLIENT_START)
        self._stop = _method(self.client, CLIENT_STOP)
        self._pointer = ctypes.c_void_p()
        self._frames = ctypes.c_uint32()
        self._flags = ctypes.c_ulong()
        if capture:
            self._next = _method(self.service, CAPTURE_NEXT_PACKET, ctypes.POINTER(ctypes.c_uint32))
            self._get = _method(self.service, CAPTURE_GET_BUFFER, ctypes.POINTER(ctypes.c_void_p),
                                ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_ulong), ctypes.c_void_p,
                                ctypes.c_void_p)
            self._put = _method(self.service, CAPTURE_RELEASE_BUFFER, ctypes.c_uint32)
        else:
            self._padding = _method(self.client, CLIENT_PADDING, ctypes.POINTER(ctypes.c_uint32))
            self._get = _method(self.service, RENDER_GET_BUFFER, ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p))
            self._put = _method(self.service, RENDER_RELEASE_BUFFER, ctypes.c_uint32, ctypes.c_ulong)

    def _ask_raw(self):
        properties = AudioClientProperties(ctypes.sizeof(AudioClientProperties), 0, 0, AUDCLNT_STREAMOPTIONS_RAW)
        hr = _method(self.client, CLIENT_SET_PROPERTIES, ctypes.POINTER(AudioClientProperties))(
            ctypes.byref(properties))
        if _failed(hr):
            self.note = "raw sound not available ({})".format(problem_words(hr))
            return False
        return True

    def _initialize(self, device, pointer):
        """Ask for the shortest period; if another program has fixed the period, take the one in use; if the
        device cannot give raw sound, start again without it."""
        init = _method(self.client, CLIENT_INIT_SHARED, ctypes.c_ulong, ctypes.c_uint32, ctypes.c_void_p,
                       ctypes.c_void_p)
        period = self.periods.minimum or self.periods.default
        hr = init(AUDCLNT_STREAMFLAGS_EVENTCALLBACK, period, pointer, None)
        if hr == AUDCLNT_E_RAW_MODE_UNSUPPORTED and self.raw:
            _release(self.client)
            self.client = _activate(device)
            self.raw = False
            self.note = "raw sound not available on this device"
            init = _method(self.client, CLIENT_INIT_SHARED, ctypes.c_ulong, ctypes.c_uint32, ctypes.c_void_p,
                           ctypes.c_void_p)
            hr = init(AUDCLNT_STREAMFLAGS_EVENTCALLBACK, period, pointer, None)
        if hr == AUDCLNT_E_ENGINE_PERIODICITY_LOCKED:
            current = ctypes.c_uint32()
            used = ctypes.c_void_p()
            if not _failed(_method(self.client, CLIENT_CURRENT_PERIOD, ctypes.POINTER(ctypes.c_void_p),
                                   ctypes.POINTER(ctypes.c_uint32))(ctypes.byref(used), ctypes.byref(current))):
                if used.value:
                    self.win.ole32.CoTaskMemFree(used)
                if current.value:
                    period = current.value
                    hr = init(AUDCLNT_STREAMFLAGS_EVENTCALLBACK, period, pointer, None)
        if _failed(hr):
            raise Unavailable("{} could not start a low-latency stream: {}".format(self.name or "The device",
                                                                                   problem_words(hr)))
        return period

    def start(self, prefill=0):
        """Start the stream; an output first gets `prefill` samples of silence queued, so it does not run dry
        before the microphone's first piece arrives."""
        if not self.capture and prefill:
            self.write_silence(min(prefill, self.buffer_frames))
        hr = self._start()
        if _failed(hr):
            raise Unavailable(problem_words(hr))

    def read(self):
        """Every piece the microphone has ready: [(frames, channels) float32]."""
        import numpy as np  # noqa: PLC0415

        pieces = []
        channels = self.format.channels
        count = ctypes.c_uint32()
        while True:
            hr = self._next(ctypes.byref(count))
            if _failed(hr):
                raise DeviceLost(problem_words(hr))
            if not count.value:
                return pieces
            hr = self._get(ctypes.byref(self._pointer), ctypes.byref(self._frames), ctypes.byref(self._flags),
                           None, None)
            if hr == AUDCLNT_S_BUFFER_EMPTY:
                return pieces
            if _failed(hr):
                raise DeviceLost(problem_words(hr))
            frames = self._frames.value
            if self._flags.value & AUDCLNT_BUFFERFLAGS_SILENT or not self._pointer.value:
                piece = np.zeros((frames, channels), dtype=np.float32)
            else:
                raw = np.ctypeslib.as_array(ctypes.cast(self._pointer, ctypes.POINTER(ctypes.c_float)),
                                            shape=(frames * channels,))
                piece = raw.reshape(frames, channels).copy()
            self._put(frames)
            pieces.append(piece)

    def padding(self):
        count = ctypes.c_uint32()
        hr = self._padding(ctypes.byref(count))
        if _failed(hr):
            raise DeviceLost(problem_words(hr))
        return count.value

    def write(self, pair):
        """(frames, 2) float32 into the output's buffer (more channels get silence, one channel gets both)."""
        import numpy as np  # noqa: PLC0415

        frames = len(pair)
        hr = self._get(frames, ctypes.byref(self._pointer))
        if _failed(hr):
            raise DeviceLost(problem_words(hr))
        channels = self.format.channels
        out = np.ctypeslib.as_array(ctypes.cast(self._pointer, ctypes.POINTER(ctypes.c_float)),
                                    shape=(frames * channels,)).reshape(frames, channels)
        if channels == 1:
            out[:, 0] = (pair[:, 0] + pair[:, 1]) * 0.5
        else:
            out[:, :2] = pair
            if channels > 2:
                out[:, 2:] = 0.0
        self._put(frames, 0)

    def write_silence(self, frames):
        if frames <= 0:
            return
        hr = self._get(frames, ctypes.byref(self._pointer))
        if _failed(hr):
            raise DeviceLost(problem_words(hr))
        self._put(frames, AUDCLNT_BUFFERFLAGS_SILENT)

    def close(self):
        if self.client is not None and self.client.value:
            try:
                _method(self.client, CLIENT_STOP)()
            except OSError:
                pass
        _release(self.service)
        _release(self.client)
        if self.event:
            self.win.kernel32.CloseHandle(self.event)
            self.event = None

    def describe(self):
        text = "{}: {} samples ({:.1f} ms) a period, {} samples of buffer".format(
            self.name or "default", self.period, self.periods.ms(self.period), self.buffer_frames)
        if self.capture:
            text += ", raw sound" if self.raw else ""
        return text + ("; " + self.note if self.note else "")


class LowLatencyMonitor:
    """Hear the microphone through the output the short way, while recording.

    start() returns a description once both streams run, or raises Unavailable with the reason in words (then
    nothing is left running). stop() ends it; report() says in words how close to live it stayed."""

    WAIT_MS = 200

    def __init__(self, output_name="", input_name="", raw=True, stereo=False, gains=(1.0, 1.0), switch_interval=0.001):
        self.output_name, self.input_name = output_name or "", input_name or ""
        self.raw, self.stereo = bool(raw), bool(stereo)
        self.left, self.right = float(gains[0]), float(gains[1])
        self.switch_interval = switch_interval
        self.description = ""
        self.buffer = None
        self.problem = ""             # why it stopped by itself, if it did
        self._thread = None
        self._ready = threading.Event()
        self._error = None
        self._stop_event = None
        self._win = None
        self._old_interval = None

    # -- the caller's side -------------------------------------------------------------
    def start(self, timeout=3.0):
        self._win = _Windows.get()
        self._stop_event = self._win.kernel32.CreateEventW(None, 1, 0, None)
        self._thread = threading.Thread(target=self._run, name="Musician Forge hearing yourself", daemon=True)
        self._old_interval = sys.getswitchinterval()
        if self.switch_interval:
            sys.setswitchinterval(self.switch_interval)      # the thread gets its turn within a period
        self._thread.start()
        if not self._ready.wait(timeout):
            self.stop()
            raise Unavailable("the low-latency streams did not start in time")
        if self._error is not None:
            error = self._error
            self.stop()
            raise error if isinstance(error, Unavailable) else Unavailable(str(error))
        return self.description

    def stop(self):
        if self._stop_event is not None:
            self._win.kernel32.SetEvent(self._stop_event)
        finished = True
        if self._thread is not None:
            self._thread.join(2.0)
            finished = not self._thread.is_alive()
            if not finished:
                # held up inside Windows: it ends by itself once Windows lets go (the event stays set for it)
                log.warning("Low-latency hearing yourself is taking long to stop")
            self._thread = None
        if self._stop_event is not None:
            if finished:
                self._win.kernel32.CloseHandle(self._stop_event)
            self._stop_event = None
        if self._old_interval is not None:
            sys.setswitchinterval(self._old_interval)
            self._old_interval = None

    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive()

    def report(self):
        """'... the output kept 5.3 ms queued on average (at most 8.0 ms); 2 gaps ...' for the log."""
        if self.buffer is None:
            return ""
        return report_words(self.buffer, self.description, self.problem)

    # -- the thread ----------------------------------------------------------------------
    def _run(self):
        try:
            com = _Com()
        except Unavailable as exc:
            self._error = exc
            self._ready.set()
            return
        win = self._win
        capture = render = enum = None
        task = None
        try:
            try:
                enum = _enumerator(win)
                mic, mic_name = _find_device(win, enum, E_CAPTURE, self.input_name)
                try:
                    capture = _Stream(win, mic, mic_name, True, self.raw)
                finally:
                    _release(mic)
                out, out_name = _find_device(win, enum, E_RENDER, self.output_name)
                try:
                    render = _Stream(win, out, out_name, False)
                finally:
                    _release(out)
                if capture.format.rate != render.format.rate:
                    raise Unavailable("the microphone runs at {:g} kHz and the output at {:g} kHz; set both to the "
                                      "same rate in Windows' Sound settings".format(capture.format.rate / 1000.0,
                                                                                   render.format.rate / 1000.0))
                if not (capture.format.is_float and render.format.is_float):
                    raise Unavailable("Windows mixes this device in a format the low-latency way does not handle "
                                      "({})".format((capture if not capture.format.is_float else render).format
                                                    .describe()))
                self.buffer = MonitorBuffer(render.period, capture.period, rate=render.format.rate)
                if win.avrt is not None:
                    index = ctypes.c_ulong(0)
                    task = win.avrt.AvSetMmThreadCharacteristicsW("Pro Audio", ctypes.byref(index))
                capture.start()
                render.start(prefill=self.buffer.target)
                self.description = "microphone {}; output {}".format(capture.describe(), render.describe())
            except (Unavailable, DeviceLost, OSError) as exc:
                self._error = exc if isinstance(exc, Unavailable) else Unavailable(str(exc))
                return
            finally:
                self._ready.set()
            self._loop(capture, render)
        except DeviceLost as exc:
            self.problem = "it stopped: {}".format(exc)
            log.warning("Low-latency hearing yourself stopped: %s", exc)
        except Exception as exc:  # noqa: BLE001 - never take the program down; the usual way still records
            self.problem = "it stopped after an error: {}".format(exc)
            log.exception("Low-latency hearing yourself failed")
        finally:
            for stream in (capture, render):
                if stream is not None:
                    stream.close()
            _release(enum)
            if task:
                win.avrt.AvRevertMmThreadCharacteristics(task)
            com.close()

    def _loop(self, capture, render):
        handles = (ctypes.c_void_p * 3)(capture.event, render.event, self._stop_event)
        wait = self._win.kernel32.WaitForMultipleObjects
        buffer = self.buffer
        while True:
            result = wait(3, handles, 0, self.WAIT_MS)
            if result == WAIT_OBJECT_0 + 2:
                return
            if result == WAIT_FAILED:
                raise DeviceLost("waiting for the sound devices failed")
            pump(capture, render, buffer, self.stereo, self.left, self.right)


def pump(capture, render, buffer, stereo, left, right):
    """One turn: everything the microphone has ready goes into the buffer, then the output is topped up."""
    for piece in capture.read():
        buffer.push(shape(piece, stereo, left, right))
    padding = render.padding()
    sound, silence = buffer.pull(padding, render.buffer_frames - padding)
    if sound is not None and len(sound):
        render.write(sound)
    if silence:
        render.write_silence(silence)


def report_words(buffer, description="", problem=""):
    stats = buffer.stats
    ms = 1000.0 / float(buffer.rate or 48000)
    average = stats["queued_sum"] / float(stats["tops"]) if stats["tops"] else 0.0
    text = ("low latency ({}): the output kept {:.1f} ms queued on average (at most {:.1f} ms, aiming for {:.1f} ms); "
            "{} gap{} filled with {:.1f} ms of silence; {} catch-up{} skipped {:.1f} ms").format(
        description or "streams", average * ms, stats["most_queued"] * ms, buffer.target * ms, stats["gaps"],
        "" if stats["gaps"] == 1 else "s", stats["silence"] * ms, stats["skips"], "" if stats["skips"] == 1 else "s",
        stats["skipped"] * ms)
    if problem:
        text += "; " + problem
    return text


def available():
    """Whether this computer could try the low-latency way at all (Windows 10 or later)."""
    if sys.platform != "win32":
        return False
    try:
        return sys.getwindowsversion().major >= 10
    except AttributeError:
        return False

