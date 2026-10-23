"""The connection to the sound card through sounddevice: the output, and the microphone.

Tries Windows WASAPI first (lowest delay), then DirectSound, then MME, so
there is always sound if any output works. Every attempt is logged.

The microphone (AudioInput) opens only while recording or testing the level,
so Windows does not show Musician Forge using the microphone the rest of the time.

Raw microphone sound (0.9.1): Windows, and many laptops' sound drivers, process the
microphone before any program hears it: noise suppression, echo cancelling, automatic
gain. That removes background sound, and held notes and instruments with it (Russell,
8 Oct 2026: "the background sound disappears"). Windows 8.1 and later can hand a
program the raw sound instead (AUDCLNT_STREAMOPTIONS_RAW). PortAudio, under
sounddevice, asks for it when its WASAPI settings say eStreamOptionRaw, and
sounddevice's WASAPI settings carry that field, so Musician Forge sets it. A device
that cannot give raw sound records as before (PortAudio only logs it, and should a
device refuse to open with it, it is opened again without it), and processing built
into the device's own hardware stays on whatever is asked.
"""

import logging
import time

import numpy as np

from .startfade import StartFade

log = logging.getLogger("musicianforge.audio")

SAMPLE_RATE = 48000
HOST_API_ORDER = ["Windows WASAPI", "Windows DirectSound", "MME"]
STREAM_OPTION_RAW = 1         # PortAudio's eStreamOptionRaw (pa_win_wasapi.h): no Windows sound processing
BLUETOOTH_WORDS = ("bluetooth", "hands-free", "handsfree", "airpods", " buds", "bt ")


def looks_like_bluetooth(name):
    """A guess from the device's name: Bluetooth adds a fifth of a second or more of delay."""
    text = " {} ".format(str(name or "").lower())
    return any(word in text for word in BLUETOOTH_WORDS)


def wasapi_settings(sd, auto_convert=False, raw=False):
    """WASAPI settings for a stream: always shared mode (exclusive mode would silence NVDA), and the raw
    microphone sound when asked. Returns (settings, whether raw sound was asked for)."""
    extra = sd.WasapiSettings(exclusive=False, auto_convert=auto_convert)
    asked = False
    if raw:
        try:
            extra._streaminfo.streamOption = STREAM_OPTION_RAW
            asked = True
        except (AttributeError, TypeError):   # an older sounddevice without the field: record as before
            log.info("This sounddevice cannot ask Windows for raw microphone sound")
    return extra, asked


def close_quietly(stream):
    """Close a stream that opened but could not start (a device that is busy, say), so it does not keep the
    device. Nothing to do for None."""
    if stream is None:
        return
    try:
        stream.close()
    except Exception:  # noqa: BLE001 - it is being given up on anyway
        log.debug("A stream that did not start could not be closed either", exc_info=True)


def _sd():
    import sounddevice  # imported lazily so the rest of Musician Forge works without it

    return sounddevice


def list_outputs():
    """[(host_api_name, [device names])] for every host API with outputs."""
    sd = _sd()
    result = []
    for api_index, api in enumerate(sd.query_hostapis()):
        names = [d["name"] for d in sd.query_devices()
                 if d["hostapi"] == api_index and d["max_output_channels"] >= 2]
        if names:
            result.append((api["name"], names))
    return result


def find_device(host_api_name, device_name):
    """Device index for a host API and device name ('' = that API's default)."""
    sd = _sd()
    for api_index, api in enumerate(sd.query_hostapis()):
        if api["name"] != host_api_name:
            continue
        if not device_name:
            index = api.get("default_output_device", -1)
            return index if index is not None and index >= 0 else None
        for index, dev in enumerate(sd.query_devices()):
            if dev["hostapi"] == api_index and dev["name"] == device_name and dev["max_output_channels"] >= 2:
                return index
    return None


def refresh_device_list():
    """Start PortAudio again so its list of devices is Windows' list now. Every open stream is closed by it.
    sounddevice has no public call for this; its _terminate and _initialize are what its own documentation
    suggests for it (and when they are missing, the list just stays as it was)."""
    sd = _sd()
    terminate, initialize = getattr(sd, "_terminate", None), getattr(sd, "_initialize", None)
    if terminate is None or initialize is None:
        log.info("This sounddevice cannot read the list of devices again")
        return False
    try:
        terminate()
    finally:
        initialize()
    return True


class AudioOutput:
    """Runs the engine's process() inside the sound card's callback."""

    def __init__(self, engine):
        self.engine = engine
        self.stream = None
        self.description = "no audio output"
        self.underflows = 0
        self.callbacks = 0
        self.latency = 0.0

    def open(self, host_api="Windows WASAPI", device_name="", block_frames=256):
        """Open the best available output. Returns a description, or raises RuntimeError."""
        self.close()
        sd = _sd()
        attempts = [(host_api, device_name)]
        for api in HOST_API_ORDER:
            if (api, "") not in attempts:
                attempts.append((api, ""))
        errors = []
        for api, name in attempts:
            index = find_device(api, name)
            if index is None:
                errors.append("{}: no device".format(api))
                continue
            for auto_convert in (False, True):
                extra = None
                if "WASAPI" in api:
                    extra = sd.WasapiSettings(exclusive=False, auto_convert=auto_convert)
                elif auto_convert:
                    break
                stream = None
                try:
                    stream = sd.OutputStream(samplerate=SAMPLE_RATE, channels=2, dtype="float32",
                                             blocksize=int(block_frames), device=index, latency="low",
                                             callback=self._callback, extra_settings=extra)
                    stream.start()
                except Exception as exc:  # noqa: BLE001
                    close_quietly(stream)      # opened but would not start: it would hold the device (23 Oct 2026)
                    errors.append("{} / {}{}: {}".format(api, sd.query_devices(index)["name"],
                                                          " (auto convert)" if auto_convert else "", exc))
                    continue
                self.stream = stream
                self.latency = float(stream.latency)
                dev_name = sd.query_devices(index)["name"]
                self.description = "{} on {}, {} ms".format(dev_name, api, int(round(self.latency * 1000)))
                log.info("Audio output opened: %s (block %s frames)", self.description, block_frames)
                if errors:
                    log.info("Earlier attempts: %s", "; ".join(errors))
                return self.description
        log.error("No audio output could be opened: %s", "; ".join(errors))
        raise RuntimeError("No audio output could be opened. " + "; ".join(errors[-3:]))

    def reopen(self, host_api="Windows WASAPI", device_name="", block_frames=256):
        """Open the sound again after Windows' outputs changed (headphones plugged in or unplugged; see
        outputwatch.py). PortAudio lists the devices once, when it starts, so it is started again first: an output
        that appeared afterwards is not in its list otherwise. Starting it again closes every stream, so the
        caller makes sure the microphone is closed. Returns a description, or raises RuntimeError.

        Any failure becomes a RuntimeError (the final review, 10 Oct 2026): PortAudio's own errors are not
        RuntimeErrors, and the project window, which catches RuntimeError, would otherwise have left the sound closed
        without a word while still counting it as playing."""
        self.close()
        try:
            refresh_device_list()
        except Exception:  # noqa: BLE001 - the old list may still hold the new output: try it
            log.exception("Could not read Windows' list of outputs again")
        try:
            return self.open(host_api, device_name, block_frames)
        except RuntimeError:
            raise
        except Exception as exc:  # noqa: BLE001
            log.exception("Opening the sound again failed")
            raise RuntimeError("No audio output could be opened. {}".format(exc)) from exc

    def _callback(self, outdata, frames, time_info, status):
        now = time.perf_counter()
        if status.output_underflow:
            self.underflows += 1
        try:
            dac_delay = float(time_info.outputBufferDacTime - time_info.currentTime)
            if not 0.0 <= dac_delay <= 1.0:
                dac_delay = self.latency
        except Exception:  # noqa: BLE001
            dac_delay = self.latency
        outdata[:] = self.engine.process(frames, now=now, dac_delay=dac_delay)
        self.callbacks += 1

    def close(self):
        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:  # noqa: BLE001
                log.exception("Closing the audio output failed")
            self.stream = None
            self.description = "no audio output"

    @property
    def is_open(self):
        return self.stream is not None and self.stream.active


def list_inputs():
    """[(host_api_name, [device names])] for every host API with inputs (microphones)."""
    sd = _sd()
    result = []
    for api_index, api in enumerate(sd.query_hostapis()):
        names = [d["name"] for d in sd.query_devices()
                 if d["hostapi"] == api_index and d["max_input_channels"] >= 1]
        if names:
            result.append((api["name"], names))
    return result


def find_input(host_api_name, device_name):
    """Input device index for a host API and device name ('' = that API's default input)."""
    sd = _sd()
    for api_index, api in enumerate(sd.query_hostapis()):
        if api["name"] != host_api_name:
            continue
        if not device_name:
            index = api.get("default_input_device", -1)
            return index if index is not None and index >= 0 else None
        for index, dev in enumerate(sd.query_devices()):
            if dev["hostapi"] == api_index and dev["name"] == device_name and dev["max_input_channels"] >= 1:
                return index
    return None


class AudioInput:
    """The microphone: hands what it hears to the engine (stamped with when it was heard),
    and remembers the loudest level for the microphone test."""

    def __init__(self, engine):
        self.engine = engine
        self.stream = None
        self.host_api = "Windows WASAPI"
        self.device_name = ""
        self.block_frames = 256
        self.raw = True            # ask Windows for the raw microphone sound (Audio settings can turn it off)
        self.raw_asked = False     # whether the open stream asked for it
        self.channels = 1          # what the engine gets: 1 (mono) or 2 (stereo)
        self.description = "the Windows default microphone (not in use)"
        self.latency = 0.0
        self.chunks = 0            # pieces received since Musician Forge started
        self.overflows = 0         # times Windows had to drop some microphone sound
        self.peak = 0.0            # loudest level since the last reset_peak()
        self.frames_heard = 0
        self.levels = []           # during the microphone test: each piece's level (root mean square)
        self.testing = False
        self.start_fade = None     # the soft start after the microphone opens (startfade.py)

    def configure(self, host_api, device_name, block_frames=256, raw=None):
        """Use another microphone from now on (it opens the next time it is needed)."""
        self.close()
        self.host_api, self.device_name, self.block_frames = host_api, device_name, int(block_frames)
        if raw is not None:
            self.raw = bool(raw)
        name = device_name or "the Windows default microphone"
        self.description = "{} (not in use)".format(name)

    def ensure_open(self, channels=1):
        """Open the microphone if it is not open yet. channels: 1 for mono tracks, 2 for stereo."""
        self.channels = 2 if channels >= 2 else 1
        if self.stream is not None:
            return self.description
        sd = _sd()
        attempts = [(self.host_api, self.device_name)]
        for api in HOST_API_ORDER:
            if (api, "") not in attempts:
                attempts.append((api, ""))
        errors = []
        for api, name in attempts:
            index = find_input(api, name)
            if index is None:
                errors.append("{}: no microphone".format(api))
                continue
            device_channels = max(1, min(2, int(sd.query_devices(index)["max_input_channels"])))
            options = [(False, self.raw), (True, self.raw)]
            if self.raw and "WASAPI" in api:
                # a device that refuses raw sound is opened without it, before any other device is tried
                options += [(False, False), (True, False)]
            for auto_convert, want_raw in options:
                extra, raw = None, False
                if "WASAPI" in api:
                    extra, raw = wasapi_settings(sd, auto_convert, want_raw)
                elif auto_convert:
                    break
                stream = None
                try:
                    stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=device_channels, dtype="float32",
                                            blocksize=self.block_frames, device=index, latency="low",
                                            callback=self._callback, extra_settings=extra)
                    stream.start()
                except Exception as exc:  # noqa: BLE001
                    close_quietly(stream)      # opened but would not start: it would hold the microphone
                    errors.append("{} / {}{}{}: {}".format(api, sd.query_devices(index)["name"],
                                                            " (auto convert)" if auto_convert else "",
                                                            " (raw)" if raw else "", exc))
                    continue
                self.stream = stream
                self.start_fade = StartFade(SAMPLE_RATE)       # no pop as it starts (Russell, 10 Oct 2026)
                self.latency = float(stream.latency)
                self.raw_asked = raw
                self.description = "{} on {}{}".format(sd.query_devices(index)["name"], api,
                                                       ", raw sound" if raw else "")
                log.info("Microphone opened: %s, %d channel(s), %d ms%s", self.description, device_channels,
                         int(round(self.latency * 1000)),
                         "" if not looks_like_bluetooth(self.description) else " (looks like Bluetooth)")
                if errors:
                    log.info("Earlier microphone attempts: %s", "; ".join(errors))
                return self.description
        log.error("No microphone could be opened: %s", "; ".join(errors))
        raise RuntimeError("No microphone could be opened. " + "; ".join(errors[-3:]))

    def _callback(self, indata, frames, time_info, status):
        now = time.perf_counter()
        if status.input_overflow:
            self.overflows += 1
        try:
            delay = float(time_info.currentTime - time_info.inputBufferAdcTime)
            if not 0.0 <= delay <= 1.0:
                delay = self.latency
        except Exception:  # noqa: BLE001
            delay = self.latency
        self.deliver(now - delay, indata)

    def deliver(self, capture_time, indata):
        """Shape one piece of microphone sound for the engine (mono or stereo) and keep the level."""
        data = np.array(indata, dtype=np.float32, copy=True)
        if data.ndim == 1:
            data = data[:, None]
        if self.channels == 1 and data.shape[1] > 1:
            data = data.mean(axis=1, keepdims=True)
        elif self.channels == 2 and data.shape[1] == 1:
            data = np.repeat(data, 2, axis=1)
        if self.start_fade is not None:
            data = self.start_fade.apply(data)
        if len(data):
            self.peak = max(self.peak, float(np.max(np.abs(data))))
            self.frames_heard += len(data)
            if self.testing:
                self.levels.append(float(np.sqrt(np.mean(np.square(data, dtype=np.float64)))))
        self.chunks += 1
        if not self.testing:
            self.engine.input_chunk(capture_time, data)

    def reset_peak(self):
        self.peak = 0.0
        self.frames_heard = 0
        self.levels = []

    def quiet_level(self):
        """The level between sounds during the microphone test: the quietest tenth of its pieces (0 to 1),
        or None if too little was heard."""
        if len(self.levels) < 10:
            return None
        return float(np.percentile(self.levels, 10))

    def start_test(self):
        """The microphone test: open the microphone and start listening for the loudest sound."""
        self.ensure_open(1)
        self.testing = True
        self.reset_peak()

    def finish_test(self):
        """End the test. Returns (loudest level 0 to 1, frames heard)."""
        result = (self.peak, self.frames_heard)
        self.testing = False
        if not self.engine.recording:
            self.release()
        return result

    def release(self):
        """Close the microphone when nothing needs it (recording or the test)."""
        if not self.testing:
            self.close()

    def close(self):
        # Closing ends a microphone test that is still listening (Audio settings closed within its three seconds).
        # Before the review of 9 Oct 2026 the test went on "listening" after it, so a recording started in those
        # seconds lost its first part: the microphone's sound went to the test instead of the take.
        self.testing = False
        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:  # noqa: BLE001
                log.exception("Closing the microphone failed")
            self.stream = None
            log.info("Microphone closed (%d dropouts)", self.overflows)
        name = self.device_name or "the Windows default microphone"
        self.description = "{} (not in use)".format(name)

    @property
    def is_open(self):
        return self.stream is not None
