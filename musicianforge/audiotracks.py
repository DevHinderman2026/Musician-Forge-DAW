"""Audio tracks: where recordings are kept, cutting looped takes, importing WAV files.

Recordings are 24-bit WAV files at 48 kHz. A saved project keeps them in the
Recordings folder inside the project's own folder (see projects.py). Until a
project is saved, recordings wait in Musician Forge's own recordings folder;
saving copies them into the project.
"""

import os
from fractions import Fraction

import numpy as np

from .song import AUDIO_RATE

MIN_TAKE_SECONDS = 0.25          # shorter scraps (for example right after a loop restarts) are dropped
GAIN_MIN_DB, GAIN_MAX_DB = -30.0, 12.0


def audio_folder_for(project_path):
    """A project's recordings live in the Recordings folder beside the project file."""
    return os.path.join(os.path.dirname(os.path.abspath(project_path)), "Recordings")


def unique_path(folder, stem, ext=".wav"):
    """folder/stem.wav, or stem 2.wav, stem 3.wav... if that name is taken."""
    path = os.path.join(folder, stem + ext)
    number = 2
    while os.path.exists(path):
        path = os.path.join(folder, "{} {}{}".format(stem, number, ext))
        number += 1
    return path


def cut_passes(first, audio, loop):
    """Split a recording made over a looping section into one take per pass.

    first: the song sample of the recording's first frame. loop: (start, end) samples
    of the looping section, or None. Returns [(start sample, audio)].
    """
    if loop is None or len(audio) == 0:
        return [(first, audio)]
    loop_start, loop_end = loop
    passes, position, start = [], 0, first
    while position < len(audio):
        room = loop_end - start
        if room <= 0:
            room = loop_end - loop_start
            start = loop_start
        piece = audio[position:position + room]
        passes.append((start, piece))
        position += len(piece)
        start = loop_start
    return passes


def resample(audio, rate, target=AUDIO_RATE):
    """Change a recording's sample rate (for imported files, and WAV export at 44.1 kHz).

    FFT resampling in overlapping pieces of about five seconds (see resample_pieces). Returns float64 shaped
    (frames, channels).
    """
    audio = np.asarray(audio)
    if audio.ndim == 1:
        audio = audio[:, None]
    if int(rate) == int(target) or len(audio) == 0:
        return np.asarray(audio, dtype=np.float64)
    pieces = list(resample_pieces(audio, rate, target))
    return np.concatenate(pieces) if pieces else np.zeros((0, audio.shape[1]))


def resample_pieces(audio, rate, target=AUDIO_RATE, segment_frames=1 << 18):
    """resample() a piece at a time (0.9.1): each piece is worked out from its own stretch of the recording plus
    a margin on both sides, so the pieces join seamlessly and only a few seconds are ever copied at once. Joined
    together the pieces are exactly what resample() returns. At the same rate the recording's own pieces come
    back unchanged."""
    audio = np.asarray(audio)
    if audio.ndim == 1:
        audio = audio[:, None]
    rate, target = int(rate), int(target)
    frames, channels = len(audio), audio.shape[1]
    if rate == target or frames == 0:
        for start in range(0, frames, segment_frames):
            yield audio[start:start + segment_frames]
        return
    ratio = Fraction(target, rate)
    p, q = ratio.numerator, ratio.denominator      # every q input frames become p output frames
    out_frames = int(round(frames * target / float(rate)))
    segment = max(1, segment_frames // q) * q
    margin = (8192 // q + 1) * q                    # extra on both sides, so the pieces join seamlessly
    padded_frames = -(-frames // q) * q
    margin_out = margin * p // q
    produced = 0
    for start in range(0, padded_frames, segment):
        stop = min(start + segment, padded_frames)
        low, high = start - margin, stop + margin   # the stretch this piece is worked out from
        piece = np.zeros((high - low, channels))
        a, b = max(low, 0), min(high, frames)
        if b > a:
            piece[a - low:b - low] = audio[a:b]
        result = _fft_resample(piece, len(piece) * p // q)
        length = (stop - start) * p // q
        keep = min(length, out_frames - produced)
        if keep <= 0:
            return
        yield result[margin_out:margin_out + keep]
        produced += keep


def _fft_resample(audio, new_frames):
    frames = len(audio)
    spectrum = np.fft.rfft(audio, axis=0)
    bins = new_frames // 2 + 1
    resized = np.zeros((bins, audio.shape[1]), dtype=complex)
    keep = min(bins, spectrum.shape[0])
    resized[:keep] = spectrum[:keep]
    return np.fft.irfft(resized, new_frames, axis=0) * (new_frames / float(frames))


def peak_db(peak):
    """A level from 0 to 1 in decibels below full scale (full volume is 0 dB)."""
    return 20.0 * np.log10(max(float(peak), 1e-9))


NOISE_GATE_DB = -80.0         # quieter than this between sounds: the background has been taken away


def describe_level(peak, frames_heard, sample_rate=AUDIO_RATE, quiet=None):
    """What the microphone test says, from the loudest level it heard (0 to 1) and, when known, the level
    between sounds (quiet, 0 to 1): near silence there means Windows or the sound card removes background
    noise, which also eats held notes and instruments."""
    if frames_heard <= 0:
        return ("No sound arrived from the microphone. Check that it is connected, "
                "and chosen in Audio settings.")
    if peak <= 0.0:
        return ("The microphone sent complete silence. Windows may be blocking it: in Windows Settings, "
                "Privacy and security, Microphone, turn on microphone access, and Let desktop apps "
                "access your microphone.")
    level = "{:.0f} dB".format(peak_db(peak)).replace("-0 dB", "0 dB")
    if peak >= 0.99:
        text = ("Too loud: it reached full volume ({}) and will sound distorted. "
                "Move back, or turn the microphone level down in Windows sound settings.".format(level))
    elif peak < 0.003:
        text = ("Very quiet: the loudest sound was {}. Move closer, or turn the microphone level up "
                "in Windows sound settings.".format(level))
    elif peak < 0.03:
        text = "Quiet: the loudest sound was {}. Recording works, but a bit louder would be better.".format(level)
    else:
        text = "Good level: the loudest sound was {}.".format(level)
    if quiet is not None and peak >= 0.03 and peak_db(quiet) < NOISE_GATE_DB:
        text += (" Between sounds the microphone went almost completely silent ({:.0f} dB), so Windows or the "
                 "sound card seems to be removing background noise, which can also cut held notes. To turn it "
                 "off: Windows Settings, System, Sound, choose the microphone under Input, then set Audio "
                 "enhancements to Off (on Windows 10: Sound Control Panel, Recording, the microphone's "
                 "Properties, Advanced or Enhancements, then Disable all enhancements). Keep Raw microphone "
                 "sound on in Audio settings.".format(peak_db(quiet)))
    return text


def recording_warning(audio):
    """Something to say about a finished recording that sounds wrong, or "" if it sounds fine."""
    if not len(audio):
        return ""
    peak = float(np.max(np.abs(audio)))
    if peak <= 0.0:
        return ("The recording is silent. Windows may be blocking the microphone; "
                "Options, Audio settings has a microphone test.")
    if peak < 0.003:
        return "The recording is very quiet. Options, Audio settings has a microphone test."
    if peak >= 0.999:
        return "The recording reached full volume in places and may sound distorted."
    return ""


def describe_seconds(frames, rate=AUDIO_RATE):
    """'8.5 seconds', '1 minute 2 seconds'."""
    seconds = frames / float(rate)
    if seconds < 60:
        value = round(seconds, 1)
        text = ("{:.1f}".format(value)).rstrip("0").rstrip(".")
        return "{} second{}".format(text, "" if text == "1" else "s")
    minutes, rest = divmod(int(round(seconds)), 60)
    return "{} minute{} {} second{}".format(minutes, "" if minutes == 1 else "s", rest, "" if rest == 1 else "s")


def describe_gain(gain_db):
    if abs(gain_db) < 0.05:
        return "gain 0 dB"
    return "gain {:+.1f} dB".format(gain_db).replace(".0 dB", " dB")
