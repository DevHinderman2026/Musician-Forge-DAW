"""Measuring the recording delay with the computer's own speakers and microphone.

Musician Forge already places every recording by when you heard the song (the sound card says
how long its output and input take). Those figures are never quite exact, and Bluetooth or a
laptop's built-in microphone can add a few milliseconds more. The measurement plays a few
short, sharp clicks through the speakers, listens with the microphone, and finds where each
click arrived in the recording, placed exactly the way a real recording would be. Whatever
is left over is the delay the Microphone timing adjustment should remove.

The clicks are spaced unevenly so an echo of one click is never mistaken for the next.
"""

from dataclasses import dataclass, field

import numpy as np

CLICKS = 8
LEAD_SECONDS = 0.4                         # quiet before the first click (the microphone settles)
GAPS = (0.43, 0.51, 0.47, 0.55, 0.45, 0.53, 0.49)   # seconds between clicks (uneven on purpose)
LISTEN_AFTER = 0.6                         # keep listening this long after the last click
SEARCH_BEFORE = 0.08                       # look for each click from 80 ms early...
SEARCH_AFTER = 0.30                        # ...to 300 ms late
MIN_FOUND = 5                              # clicks that must be heard for a trustworthy result
MAX_SPREAD_MS = 4.0                        # and they must agree this closely
LIMIT_MS = 200                             # the timing adjustment goes from -200 to 200 ms


def click_sound(sample_rate, level=0.8):
    """A 4 millisecond click: a sharp start, bright enough to cut through laptop speakers."""
    length = int(0.004 * sample_rate)
    t = np.arange(length) / float(sample_rate)
    tone = np.sin(2 * np.pi * 2500.0 * t) + 0.5 * np.sin(2 * np.pi * 4100.0 * t)
    envelope = np.exp(-t / 0.0012)
    mono = (tone * envelope / 1.5 * level).astype(np.float32)
    return np.stack([mono, mono], axis=1)


def click_times(sample_rate, start=0):
    """Where the clicks start, in samples from `start`."""
    times = [start + int(LEAD_SECONDS * sample_rate)]
    for gap in GAPS[:CLICKS - 1]:
        times.append(times[-1] + int(gap * sample_rate))
    return times


def total_frames(sample_rate):
    return int((LEAD_SECONDS + sum(GAPS[:CLICKS - 1]) + LISTEN_AFTER) * sample_rate)


def _envelope(audio, sample_rate):
    """How strongly each moment of the recording matches the click (a matched filter: noise that
    does not sound like the click mostly cancels out), smoothed over one cycle of the click."""
    mono = np.asarray(audio, dtype=np.float64)
    if mono.ndim > 1:
        mono = mono.mean(axis=1)
    click = click_sound(sample_rate, 1.0)[:, 0].astype(np.float64)
    if len(mono) < len(click):
        return np.zeros(len(mono))
    size = 1 << int(np.ceil(np.log2(len(mono) + len(click))))
    match = np.fft.irfft(np.fft.rfft(mono, size) * np.conj(np.fft.rfft(click, size)), size)[:len(mono)]
    width = max(1, int(sample_rate / 2500.0))
    kernel = np.ones(width) / width
    return np.convolve(np.abs(match), kernel, mode="same")


@dataclass
class Measurement:
    delays_ms: list = field(default_factory=list)    # one per click that was heard
    clicks: int = CLICKS
    loudest: float = 0.0                             # loudest sound the microphone heard (0 to 1)

    @property
    def found(self):
        return len(self.delays_ms)

    @property
    def delay_ms(self):
        return float(np.median(self.delays_ms)) if self.delays_ms else 0.0

    @property
    def spread_ms(self):
        if len(self.delays_ms) < 2:
            return 0.0
        q1, q3 = np.percentile(self.delays_ms, [25, 75])
        return float(q3 - q1)

    @property
    def reliable(self):
        return self.found >= MIN_FOUND and self.spread_ms <= MAX_SPREAD_MS

    @property
    def adjustment_ms(self):
        """The Microphone timing adjustment that removes the delay (whole milliseconds)."""
        return int(max(-LIMIT_MS, min(LIMIT_MS, round(self.delay_ms))))

    def describe(self):
        if self.loudest < 0.002:
            return ("The microphone heard nothing. Check that the microphone is on and allowed in Windows "
                    "privacy settings, and that the speakers are turned up. Nothing was changed.")
        if not self.reliable:
            if self.found < MIN_FOUND:
                return ("Only {} of {} clicks were heard clearly, so the measurement is not trustworthy and "
                        "nothing was changed. Turn the speakers up, make the room quiet, and try again. "
                        "With headphones on, the microphone cannot hear the clicks: take them off for the "
                        "measurement.".format(self.found, self.clicks))
            return ("The clicks arrived at uneven times (they varied by {} milliseconds), so nothing was changed. "
                    "Make the room quiet and try again.".format(int(round(self.spread_ms))))
        direction = "late" if self.delay_ms >= 0 else "early"
        return ("Measured: recordings arrive {} milliseconds {}, steady over {} of {} clicks. "
                "Microphone timing adjustment set to {} milliseconds. Press OK to keep it.".format(
                    int(round(abs(self.delay_ms))), direction, self.found, self.clicks, self.adjustment_ms))


def measure(first, audio, clicks, sample_rate):
    """Find each click in a recording.

    first: the sample (on the same clock as `clicks`) where the recording's first frame belongs,
    placed by when it was heard, as for a real recording. audio: the recording, (frames,) or
    (frames, channels). clicks: where the clicks were played. Returns a Measurement."""
    audio = np.asarray(audio, dtype=np.float64)
    result = Measurement(clicks=len(clicks))
    if audio.size == 0:
        return result
    result.loudest = float(np.max(np.abs(audio)))
    env = _envelope(audio, sample_rate)
    before = int(SEARCH_BEFORE * sample_rate)
    after = int(SEARCH_AFTER * sample_rate)
    for click in clicks:
        lo = click - before - first
        hi = click + after - first
        if lo < 0 or hi > len(env):
            continue
        window = env[lo:hi]
        peak_index = int(np.argmax(window))
        peak = float(window[peak_index])
        noise_part = window[:max(1, before // 2)]
        noise = float(np.median(noise_part)) if len(noise_part) else 0.0
        if peak < 1e-4 or peak < 5.0 * max(noise, 1e-9):
            continue
        delay = (lo + peak_index + first) - click     # where the recording lines up best with the click
        result.delays_ms.append(delay * 1000.0 / sample_rate)
    return result


def simulate(sample_rate, delay_ms, noise=0.002, level=0.3, brightness=0.5, seed=1):
    """A pretend recording of the click train, as if the sound took delay_ms longer than reported.
    Used by the tests."""
    rng = np.random.default_rng(seed)
    frames = total_frames(sample_rate)
    out = rng.standard_normal(frames) * noise
    click = click_sound(sample_rate, level)[:, 0].astype(np.float64)
    # laptop speakers and microphones are not flat: soften the click a little
    soft = np.convolve(click, np.ones(max(1, int(brightness * 6))) / max(1, int(brightness * 6)))[:len(click)]
    shift = int(round(delay_ms / 1000.0 * sample_rate))
    for start in click_times(sample_rate):
        at = start + shift
        if 0 <= at < frames:
            piece = soft[:frames - at]
            out[at:at + len(piece)] += piece
            echo = at + int(0.012 * sample_rate)       # a wall's reflection, quieter
            if echo < frames:
                piece = soft[:frames - echo] * 0.3
                out[echo:echo + len(piece)] += piece
    return out.astype(np.float32)[:, None]


def describe_ms(value):
    value = int(round(value))
    return "{} millisecond{}".format(value, "" if abs(value) == 1 else "s")

