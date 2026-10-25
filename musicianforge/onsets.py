"""Finding the hits in a recording, so a rhythm player can follow a real guitar, piano, voice or
tapping recorded through the microphone (or an imported WAV file).

The recording is cut into short windows (256 samples apart, about 5 ms). In each window the
loudness is measured in quarter-octave bands on a log scale, each band's own background noise
taken into account, and the "flux" is how much louder the bands got than just before, added up
(a standard onset measure, close to the "SuperFlux" of Böck and Widmer, 2013: a new hit makes many
bands jump at once, while noise and a wobbling held note do not). Peaks of the flux that stand out from their surroundings by more than the sensitivity
allows are hits. Each hit keeps its time (refined to the sample where the sound starts rising),
its loudness, and how low it is (the share of its energy below about 200 Hz), so a heavy, low
hit counts for more. Only the list of hits is kept, never a copy of the audio.

Clear, separate hits (picked or chugged guitar, piano, drums, tapping) are found reliably;
pads, slow strings and sustained chords have few clear starts.
"""

from dataclasses import dataclass

import numpy as np

HOP = 256
WINDOW = 1024
MIN_GAP_SECONDS = 0.05          # two hits closer than this count as one
QUIET_LEVEL = 10 ** (-50 / 20)  # windows quieter than -50 dB are never hits
FLOOR = 2.0                     # the least strength a hit needs (a steady tone stays well under it)
RISE = 1.4                      # a hit is at least 3 dB louder than the moment before it


@dataclass
class AudioHit:
    sample: int                 # where the hit starts, in the recording
    loudness: float             # 0 to 1
    low: float                  # 0 (bright) to 1 (deep)


def _band_matrix(sample_rate):
    """Quarter-octave bands from 40 Hz up to 16 kHz, as rows of 0 and 1 over the FFT bins."""
    freqs = np.fft.rfftfreq(WINDOW, 1.0 / sample_rate)
    edges = [40.0]
    while edges[-1] * 2 ** 0.25 < min(sample_rate / 2.0, 16000.0):
        edges.append(edges[-1] * 2 ** 0.25)
    rows = []
    for low, high in zip(edges[:-1], edges[1:]):
        row = (freqs >= low) & (freqs < high)
        if not row.any():                       # narrower than one bin: use the nearest bin
            row = np.zeros_like(freqs, dtype=bool)
            row[int(np.argmin(np.abs(freqs - (low + high) / 2.0)))] = True
        rows.append(row)
    return np.array(rows, dtype=np.float64)


def find_hits(audio, sample_rate, sensitivity=50):
    """The hits in a recording. sensitivity 0 (only the clearest hits) to 100 (every little one)."""
    audio = np.asarray(audio, dtype=np.float64)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    if len(audio) < WINDOW:
        return []
    # A steady offset (a microphone or interface that sits off centre) is taken out first: it counted as loudness,
    # so the rise a hit makes looked small beside it and hits went unfound (the review of 25 Oct 2026). A tiny
    # offset is left: the lopsided sum of ordinary notes, which changes nothing.
    offset = float(np.mean(audio))
    if abs(offset) > 0.02 * float(np.max(np.abs(audio))):
        audio = audio - offset
    # silence in front, so a hit right at the very start of a recording is found too
    hits = _find_hits(np.concatenate([np.zeros(WINDOW), audio]), sample_rate, sensitivity)
    for hit in hits:
        hit.sample = max(0, hit.sample - WINDOW)
    if hits and hits[0].sample < 2 * HOP:
        # ...but only a real one: background noise that is there from the start is not a hit
        blocks = len(audio) // HOP
        envelope = np.sqrt(np.mean(audio[:blocks * HOP].reshape(blocks, HOP) ** 2, axis=1))
        opening = envelope[:max(1, int(0.04 * sample_rate / HOP))].max()
        if opening < 3.0 * np.median(envelope):
            hits = hits[1:]
    return hits


def _find_hits(audio, sample_rate, sensitivity):
    frames = len(audio)
    count = 1 + (frames - WINDOW) // HOP
    window = np.hanning(WINDOW)
    starts = np.arange(count) * HOP
    spectra = np.empty((count, WINDOW // 2 + 1))
    levels = np.empty(count)
    for first in range(0, count, 512):
        idx = starts[first:first + 512, None] + np.arange(WINDOW)[None, :]
        spectra[first:first + 512] = np.abs(np.fft.rfft(audio[idx] * window, axis=1))
        levels[first:first + 512] = np.max(np.abs(audio[idx]), axis=1)    # peak: a hit at a window's end counts
    # Loudness in quarter-octave bands, on a log scale. Each band's own quiet level (room noise, hum)
    # is added in first, so changes far below it hardly count and noise cannot pass for hits.
    bands = _band_matrix(sample_rate)
    power = (spectra ** 2) @ bands.T / bands.sum(axis=1)[None, :]
    floor = np.percentile(power, 20, axis=0)
    logs = np.log10(power + floor[None, :] + 1e-10 * power.max() + 1e-20)
    # how much louder each band got than in the window before (or the one before that, whichever was
    # louder, so a wobbling held note does not count), summed over the bands
    earlier = np.maximum(logs[:-1], logs[np.maximum(0, np.arange(count - 1) - 1)])
    flux = np.zeros(count)
    flux[1:] = np.maximum(0.0, logs[1:] - earlier).sum(axis=1)
    flux[levels < QUIET_LEVEL] = 0.0
    # A hit that falls between two windows shows up in both: each window's strength counts the next
    # one too, so a hit counts in full wherever it falls.
    flux = flux + np.concatenate([flux[1:], [0.0]])
    # A hit must rise clearly above the flux around it: the background's typical level plus several times
    # its spread (lower sensitivity asks for more), and never below a floor that a steady tone stays under.
    span = int(0.2 * sample_rate / HOP)
    padded = np.pad(flux, span, mode="symmetric")          # works for recordings shorter than the span too
    windows = np.lib.stride_tricks.sliding_window_view(padded, 2 * span + 1)[:count]
    local = np.median(windows, axis=1)
    spread = 1.4826 * np.median(np.abs(windows - local[:, None]), axis=1)   # robust: hits don't raise it
    strictness = 3.0 + 9.0 * (1.0 - float(sensitivity) / 100.0)
    threshold = local + np.maximum(FLOOR, strictness * spread)
    gap = int(MIN_GAP_SECONDS * sample_rate / HOP)
    blocks = frames // HOP
    envelope = np.sqrt(np.mean(audio[:blocks * HOP].reshape(blocks, HOP) ** 2, axis=1))
    span_blocks = max(2, int(0.04 * sample_rate / HOP))
    freqs = np.fft.rfftfreq(WINDOW, 1.0 / sample_rate)
    low_bins = freqs < 200.0
    loudest = float(np.max(levels))
    hits, strengths = [], []
    for i in range(1, count - 1):
        value = flux[i]
        if value <= 0 or value < flux[i - 1] or value < flux[i + 1] or value < threshold[i]:
            continue
        sample = _refine(audio, int(starts[i]), sample_rate)
        replace = False
        if hits and sample - hits[-1].sample < gap * HOP:
            if value <= strengths[-1]:
                continue
            replace = True                     # two candidates close together: the stronger one is the hit
        # a real hit makes the sound louder than just before it (a sound that stops suddenly, or is
        # cut off, also changes the spectrum, but it gets quieter)
        first = sample // HOP
        before = envelope[max(0, first - span_blocks):max(0, first - 1)]
        after = envelope[first:first + span_blocks]
        if not len(after) or (len(before) and after.max() < RISE * before.max()):
            continue
        following = levels[i:min(count, i + 6)]
        loudness = float(np.max(following) / loudest) if loudest > 0 else 0.0
        energy = spectra[min(count - 1, i + int(np.argmax(following)))] ** 2
        low = float(energy[low_bins].sum() / energy.sum()) if energy.sum() > 0 else 0.0
        hit = AudioHit(int(sample), min(1.0, loudness), min(1.0, low * 2.0))
        if replace:
            hits[-1], strengths[-1] = hit, value
        else:
            hits.append(hit)
            strengths.append(value)
    return hits


def _refine(audio, window_start, sample_rate):
    """The sample where the hit starts, near the window that found it: the moment the short-term
    energy jumps most above the energy just before it, backed up to where the rise begins."""
    lo = max(0, window_start - WINDOW // 2)
    hi = min(len(audio), window_start + WINDOW + WINDOW // 2)
    piece = audio[lo:hi]
    width = max(1, int(0.001 * sample_rate))           # energy over 1 millisecond
    energy = np.convolve(piece ** 2, np.ones(width) / width, mode="same")
    back = max(1, int(0.005 * sample_rate))            # compared with the 5 milliseconds before
    if len(energy) <= back:
        return window_start
    total = np.concatenate([[0.0], np.cumsum(energy)])
    index = np.arange(len(energy))
    begin = np.maximum(0, index - back)
    before = (total[index] - total[begin]) / np.maximum(1, index - begin)
    ratio = energy / (before + 1e-12 + 1e-6 * energy.max())
    best = int(np.argmax(ratio[back:])) + back
    k = best
    while k > back and energy[k - 1] > before[best] * 2:
        k -= 1
    return lo + k


def describe_count(hits):
    count = len(hits)
    return "{} hit{} found".format(count, "" if count == 1 else "s")
