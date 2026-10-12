"""Musician Forge self check.

Runs inside Musician Forge's Python environment after installation. Checks the
packages, the audio output, the FluidSynth engine with the SoundFont (it
renders test notes silently and measures their pitch), and screen reader
speech. Writes logs\\selfcheck_log.txt with PASS, WARN and FAIL lines.
"""

import os
import sys
import time
import traceback

PROGRAM_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROGRAM_DIR)

REPORT = os.path.join(PROGRAM_DIR, "logs", "selfcheck_log.txt")
TRACE = os.path.join(PROGRAM_DIR, "logs", "selfcheck_trace.txt")   # every call into FluidSynth, written first
results = []


def record(status, message):
    line = "{} {}".format(status, message)
    results.append(line)
    print(line, flush=True)


def check(name, func):
    try:
        func()
    except Exception as exc:  # noqa: BLE001
        record("FAIL", "{}: {}".format(name, exc))
        results.append(traceback.format_exc())


def check_packages():
    import numpy
    import wx
    record("PASS", "wxPython {} and numpy {}".format(wx.version(), numpy.__version__))


def check_audio_output():
    import sounddevice as sd

    record("PASS", "sounddevice {} (PortAudio {})".format(sd.__version__, sd.get_portaudio_version()[1]))
    apis = [api["name"] for api in sd.query_hostapis()]
    results.append("Host APIs: " + ", ".join(apis))
    for index, dev in enumerate(sd.query_devices()):
        if dev["max_output_channels"] > 0:
            results.append("  output device {}: {} [{}] {} Hz".format(
                index, dev["name"], sd.query_hostapis(dev["hostapi"])["name"],
                int(dev["default_samplerate"])))
    wasapi = next((i for i, api in enumerate(sd.query_hostapis()) if "WASAPI" in api["name"]), None)
    if wasapi is None:
        record("WARN", "Windows WASAPI audio is not available; Musician Forge will use a slower driver")
        device = None
    else:
        device = sd.query_hostapis(wasapi)["default_output_device"]
        if device is None or device < 0:
            record("WARN", "WASAPI has no default output device; using the system default")
            device, wasapi = None, None
        else:
            record("PASS", "Default WASAPI output: {}".format(sd.query_devices(device)["name"]))
    frames_done = [0]

    def callback(outdata, frames, time_info, status):
        outdata.fill(0)  # silence: this only proves the device opens and runs
        frames_done[0] += frames

    extra = sd.WasapiSettings(exclusive=False) if wasapi is not None else None
    try:
        stream = sd.OutputStream(samplerate=48000, channels=2, dtype="float32", blocksize=256,
                                 device=device, callback=callback, latency="low", extra_settings=extra)
    except Exception:  # noqa: BLE001 - some devices need sample-rate conversion
        extra = sd.WasapiSettings(exclusive=False, auto_convert=True) if wasapi is not None else None
        stream = sd.OutputStream(samplerate=48000, channels=2, dtype="float32", blocksize=256,
                                 device=device, callback=callback, latency="low", extra_settings=extra)
        record("WARN", "Audio device needed automatic sample-rate conversion")
    with stream:
        time.sleep(0.5)
        latency = stream.latency
    if frames_done[0] > 0:
        record("PASS", "Audio output ran silently for half a second; latency {:.0f} ms".format(latency * 1000))
    else:
        record("FAIL", "Audio output opened but never asked for sound")
    # Microphones are only listed here, never opened: Windows would show Musician Forge using the microphone.
    inputs = [(index, dev) for index, dev in enumerate(sd.query_devices()) if dev["max_input_channels"] > 0]
    for index, dev in inputs:
        results.append("  input device {}: {} [{}] {} channel(s)".format(
            index, dev["name"], sd.query_hostapis(dev["hostapi"])["name"], dev["max_input_channels"]))
    if inputs:
        record("PASS", "Microphones found: {} (Options, Audio settings has a microphone test)".format(len(inputs)))
    else:
        record("WARN", "No microphone found; audio tracks need one to record (importing WAV files still works)")


def dominant_frequency(signal, sample_rate):
    import numpy as np

    window = signal * np.hanning(len(signal))
    spectrum = np.abs(np.fft.rfft(window))
    freqs = np.fft.rfftfreq(len(window), 1.0 / sample_rate)
    spectrum[freqs < 40] = 0
    return float(freqs[int(np.argmax(spectrum))])


def check_instruments():
    import numpy as np
    from musicianforge import fluid, paths

    synth = fluid.FluidSynth(sample_rate=48000)
    record("PASS", "FluidSynth {} loaded from {}".format(fluid.version(), fluid.library_path()))
    synth.load_soundfont(paths.default_soundfont())
    presets = synth.presets()
    drums = [p for p in presets if p.is_drum_kit]
    record("PASS", "SoundFont loaded: {} instruments including {} drum kits".format(len(presets), len(drums)))
    results.append("First instruments: " + "; ".join(
        "{}:{} {}".format(p.bank, p.program, p.name) for p in presets[:12]))

    # Flute playing A4 (440 Hz): nearly a pure tone, so the pitch is easy to measure.
    synth.set_instrument(0, 0, 73)
    synth.noteon(0, 69, 100)
    audio = synth.render(48000)
    synth.noteoff(0, 69)
    synth.render(24000)
    freq = dominant_frequency(audio[12000:36000, 0].astype(np.float64), 48000)
    peak = float(np.max(np.abs(audio)))
    if abs(freq - 440.0) < 440.0 * 0.02 and peak > 0.01:
        record("PASS", "Test note A4 measured at {:.1f} Hz (expected 440), peak level {:.2f}".format(freq, peak))
    else:
        record("FAIL", "Test note A4 measured at {:.1f} Hz with peak {:.3f}".format(freq, peak))

    # Piano and a drum kit just need to make sound.
    synth.set_instrument(1, 0, 0)
    synth.noteon(1, 60, 100)
    piano = synth.render(24000)
    synth.noteoff(1, 60)
    synth.set_instrument(9, 128, 0, drum=True)
    synth.noteon(9, 36, 110)
    kick = synth.render(24000)
    synth.noteoff(9, 36)
    for label, sound in (("Piano", piano), ("Drum kit kick", kick)):
        level = float(np.max(np.abs(sound)))
        record("PASS" if level > 0.01 else "FAIL", "{} test sound peak level {:.2f}".format(label, level))

    # Musician Forge's own instruments: built here (if missing), then loaded next to GeneralUser GS.
    from musicianforge import forgekit

    kit = forgekit.ensure_kit()
    synth.load_soundfont(kit)
    synth.set_instrument(8, 128, forgekit.DUBSTEP_KIT_PROGRAM, drum=True)
    synth.noteon(8, 36, 120)
    forge_kick = synth.render(24000)
    synth.noteoff(8, 36)
    level = float(np.max(np.abs(forge_kick)))
    record("PASS" if level > 0.01 else "FAIL",
           "Forge Dubstep Kit kick peak level {:.2f} ({})".format(level, os.path.basename(kit)))
    synth.close()


def check_m4a():
    """Encode half a second of a tone to M4A with Windows' own AAC encoder, then read it back."""
    import tempfile

    import numpy as np
    from musicianforge import m4a

    folder = tempfile.mkdtemp(prefix="musicianforge-m4a-")
    path = os.path.join(folder, "check.m4a")
    tone = 0.3 * np.sin(np.arange(24000) / 48000.0 * 2 * np.pi * 440.0)
    try:
        writer = m4a.M4AWriter(path, 48000)
        writer.write(np.stack([tone, tone], axis=1))
        writer.close()
        info = m4a.describe_m4a(path)
    except m4a.M4AError as exc:
        record("WARN", "M4A export is not available: {} (WAV export still works)".format(exc))
        return
    finally:
        for name in os.listdir(folder):
            os.remove(os.path.join(folder, name))
        os.rmdir(folder)
    if info.get("codec") == "mp4a" and abs(info.get("seconds", 0) - 0.5) < 0.1:
        record("PASS", "M4A export works (AAC, {} Hz, {:.2f} seconds)".format(info["sample_rate"], info["seconds"]))
    else:
        record("FAIL", "M4A export made an unexpected file: {}".format(info))


def check_speech():
    from musicianforge import speech

    output = speech.speaker.describe()
    if output.startswith("none"):
        record("WARN", "No screen reader detected for announcements")
    else:
        speech.speaker.speak("Musician Forge self check finished.")
        record("PASS", "Announcements will use {}".format(output))


def main():
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    os.environ["MUSICIANFORGE_TRACE"] = TRACE
    open(TRACE, "w").close()
    check("Packages", check_packages)
    check("Audio output", check_audio_output)
    check("Instruments", check_instruments)
    check("M4A export", check_m4a)
    check("Speech", check_speech)
    failed = any(r.startswith("FAIL") for r in results)
    with open(REPORT, "w", encoding="utf-8") as fh:
        fh.write("Musician Forge self check, Python {}\n".format(sys.version))
        fh.write("\n".join(results) + "\n")
        fh.write("RESULT: {}\n".format("PROBLEMS FOUND" if failed else "ALL GOOD"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
