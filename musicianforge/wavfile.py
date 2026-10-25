"""Writing (and reading back) WAV files.

Supports 16-bit and 24-bit PCM stereo. 16-bit files get a tiny amount of
"dither" noise (TPDF), the standard way to avoid harsh distortion on quiet
fades when reducing to 16 bits.
"""

import os
import wave

import numpy as np

from .paths import replace_file

MAX_WAV_BYTES = 1_000_000_000  # Russell's rule: no WAV of a gigabyte or more


def wav_size_bytes(frames, channels=2, bits=24):
    return 44 + frames * channels * (bits // 8)


def to_pcm_bytes(audio, bits=24, rng=None):
    """float32 audio shaped (frames, channels) in -1..1 -> little-endian PCM bytes."""
    audio = np.asarray(audio, dtype=np.float64)
    if bits == 16:
        rng = rng or np.random.default_rng(0)
        lsb = 1.0 / 32768.0
        dither = (rng.random(audio.shape) - rng.random(audio.shape)) * lsb
        scaled = np.clip((audio + dither) * 32768.0, -32768, 32767)
        return np.round(scaled).astype("<i2").tobytes()
    if bits == 24:
        scaled = np.clip(np.round(audio * 8388608.0), -8388608, 8388607).astype("<i4")
        raw = scaled.reshape(-1).view(np.uint8).reshape(-1, 4)[:, :3]
        return np.ascontiguousarray(raw).tobytes()
    raise ValueError("Only 16-bit and 24-bit WAV files are supported")


class WavWriter:
    """Write a WAV file in pieces (so long songs never sit in memory twice)."""

    def __init__(self, path, sample_rate=48000, bits=24, channels=2):
        if bits not in (16, 24):
            raise ValueError("Only 16-bit and 24-bit WAV files are supported")
        self.path = path
        self.tmp_path = path + ".tmp"
        self.bits = bits
        self.channels = channels
        self.frames = 0
        self._rng = np.random.default_rng(12345)
        self._wav = wave.open(self.tmp_path, "wb")
        self._wav.setnchannels(channels)
        self._wav.setsampwidth(bits // 8)
        self._wav.setframerate(int(sample_rate))

    def write(self, audio):
        audio = np.asarray(audio)
        if audio.ndim != 2 or audio.shape[1] != self.channels:
            raise ValueError("audio must be shaped (frames, {})".format(self.channels))
        if wav_size_bytes(self.frames + len(audio), self.channels, self.bits) >= MAX_WAV_BYTES:
            raise ValueError("This export would reach 1 gigabyte. Export a shorter range or use 16-bit.")
        self._wav.writeframes(to_pcm_bytes(audio, self.bits, self._rng))
        self.frames += len(audio)

    def close(self):
        """Finish the file and move it into place. If that fails (a full disk, or the old file held open by another
        program), the old file stays as it was and the temporary one is removed (the review of 25 Oct 2026)."""
        try:
            self._wav.close()
            replace_file(self.tmp_path, self.path)
        except BaseException:
            try:
                self.abort()
            except OSError:
                pass
            raise

    def abort(self):
        try:
            self._wav.close()
        finally:
            if os.path.exists(self.tmp_path):
                os.remove(self.tmp_path)


def write_wav(path, audio, sample_rate=48000, bits=24):
    writer = WavWriter(path, sample_rate, bits, channels=np.asarray(audio).shape[1])
    try:
        writer.write(audio)
    except Exception:
        writer.abort()
        raise
    writer.close()


class ReadCancelled(Exception):
    """read_wav was asked to stop (a long import cancelled)."""


# the sample rates a WAV file can sensibly have: a damaged header saying 0 Hz divided by zero, and one saying 1 Hz
# made converting it to the song's rate ask for tens of thousands of times its size in memory (the review of
# 25 Oct 2026)
LOWEST_RATE, HIGHEST_RATE = 1000, 384000


class BadSampleRate(ValueError):
    """The file's header gives a sample rate no real recording has."""


def check_rate(rate, what="This WAV file"):
    if not LOWEST_RATE <= rate <= HIGHEST_RATE:
        raise BadSampleRate("{} says its sample rate is {} Hz, which cannot be right".format(what, rate))


READ_CHUNK = 1 << 18          # frames converted at a time, so a long file never sits in memory more than once


def read_wav(path, dtype=np.float64, check=None, progress=None, cancelled=None):
    """Returns (audio shaped (frames, channels) as `dtype`, sample_rate, bits) for a 16-bit or 24-bit WAV.

    check(frames, rate) is called before anything is read (it may raise, to refuse a file that is too long);
    progress(0 to 1) is called as it reads; cancelled() returning True raises ReadCancelled. The file is read
    and converted a piece at a time."""
    with wave.open(path, "rb") as wav:
        channels, width, rate, frames = wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getnframes()
        if width not in (2, 3):
            raise ValueError("Unsupported sample width {}".format(width))
        check_rate(rate)
        # a header can promise more than the file holds (a recorder that stopped before finishing it, or a cut-off
        # copy): never more than the file's size allows (the review of 9 Oct 2026)
        frames = min(frames, os.path.getsize(path) // max(1, width * channels))
        if check is not None:
            check(frames, rate)
        audio = np.empty((frames, channels), dtype=dtype)
        done = 0
        while done < frames:
            if cancelled is not None and cancelled():
                raise ReadCancelled()
            raw = wav.readframes(min(READ_CHUNK, frames - done))
            got = len(raw) // (width * channels)
            if got <= 0:
                break
            audio[done:done + got] = _pcm_to_float(raw[:got * width * channels], width, dtype).reshape(-1, channels)
            done += got
            if progress is not None:
                progress(done / float(frames))
    return audio[:done], rate, width * 8


def _pcm_to_float(raw, width, dtype):
    if width == 2:
        return np.frombuffer(raw, dtype="<i2").astype(dtype) / dtype(32768.0)
    b = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3).astype(np.int32)
    ints = b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)
    ints = np.where(ints >= 1 << 23, ints - (1 << 24), ints)
    return ints.astype(dtype) / dtype(8388608.0)
