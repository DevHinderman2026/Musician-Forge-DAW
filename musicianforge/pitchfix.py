"""Pitch correction for recordings on audio tracks.

Worked out ahead of time for each recording (it needs to look at the whole note), then played
like any recording. Three steps:

1. Find the pitch every 5 milliseconds with the YIN method (de Cheveigne and Kawahara, 2002):
   compare the sound with itself shifted by every possible period and pick the best match.
2. Decide the target: the nearest note of the song's key at that moment (or any note, for
   chromatic), then glide towards it at the chosen speed. Strength scales how far it goes.
3. Move the pitch with PSOLA (pitch-synchronous overlap-add): the recording is cut into
   two-period slices centred on each wave cycle, and the slices are laid down again closer
   together (higher) or further apart (lower). The length and timing stay exactly the same,
   and the sound keeps its own character.

Works best on one voice or one instrument at a time (a singer, a solo line). Chords and
noisy sounds are left as they are where no clear pitch is found.

Clearer sound (0.9.1; Russell, 8 Oct 2026: "pitch correction muddies the sound"). Measured on
a sung "ah" (a harmonic voice through vowel resonances), the old version changed the sound even
where it had nothing to correct: every stretch went through the slicing and re-laying, which
moved the slices' phase, blurred breath and background noise (the brightness of a slightly
noisy voice fell by 18 percent) and lost up to 1.8 dB between 2 and 6 kHz. Now:
- only what is really moved is processed: where the pitch is not clear, or the correction is
  smaller than a hundredth of a semitone, the recording plays exactly as recorded, with 10 ms
  crossfades where processing starts and stops;
- tiny wobbles are left alone: a note less than 8 cents from the target is not touched, and
  the correction grows smoothly to full by 16 cents (so in-tune singing is not processed);
- octave mistakes in the pitch reading (a frame read an octave up or down) are put right
  before they can pull a note the wrong way, and a reading far from its neighbours is ignored;
- each slice is lined up with the one before it by matching the waveform, not by the highest
  peak, so the cycles are cut at the same point every time;
- slices are one cycle long with short crossfades, instead of two cycles crossfaded all the way:
  long crossfades mix two slices a little out of step, which cancels high frequencies like a
  comb filter (6.5 dB lost between 4 and 8 kHz on a sung "ah" with background noise; now 0.4).
"""

import math

import numpy as np

HOP = 256                 # pitch is measured every 256 samples (5.3 ms at 48 kHz)
WINDOW = 2048
MIN_FREQ, MAX_FREQ = 70.0, 1000.0
YIN_THRESHOLD = 0.15
VOICED_LIMIT = 0.3        # a frame whose best match is worse than this has no clear pitch
QUIET_DB = -45.0          # frames quieter than this are left alone
UNVOICED_STEP = 480       # slice spacing where there is no pitch (10 ms)
DEAD_ZONE = (0.08, 0.16)  # semitones: nothing under 8 cents off is corrected; full correction from 16 cents
MOVED = 0.01              # semitones: a correction smaller than this leaves the recording as it was
CROSSFADE = 0.010         # seconds of crossfade where processing starts and stops
OCTAVE_WINDOW = 7         # frames on each side that a pitch reading is checked against
TAPER = 0.2               # the crossfade between slices, as a share of a cycle


def detect_pitch(mono, sample_rate):
    """Pitch in hertz for each frame (0 where there is no clear pitch), and the frame centres."""
    mono = np.asarray(mono, dtype=np.float64)
    frames = len(mono)
    min_lag = int(sample_rate / MAX_FREQ)
    max_lag = min(int(sample_rate / MIN_FREQ), WINDOW // 2)
    centres = np.arange(0, frames, HOP)
    if frames == 0:
        return np.zeros(0), centres
    padded = np.concatenate([np.zeros(WINDOW // 2), mono, np.zeros(WINDOW + HOP)])
    pitches = np.zeros(len(centres))
    size = 1 << int(math.ceil(math.log2(2 * WINDOW)))
    half = WINDOW // 2
    for start in range(0, len(centres), 256):
        group = centres[start:start + 256]
        idx = group[:, None] + np.arange(WINDOW)[None, :]
        chunk = padded[idx]                                         # (frames, WINDOW)
        energy = np.sum(chunk[:, :half] ** 2, axis=1)
        loud = 10.0 * np.log10(np.maximum(energy / half, 1e-12)) > QUIET_DB
        spectrum = np.fft.rfft(chunk, size, axis=1)
        first = np.fft.rfft(chunk[:, :half], size, axis=1)
        cross = np.fft.irfft(np.conj(first) * spectrum, size, axis=1)[:, :max_lag + 2]
        squares = np.cumsum(chunk ** 2, axis=1)
        lags = np.arange(max_lag + 2)
        # energy of chunk[tau : tau + half] for every lag
        shifted = squares[:, lags + half - 1] - np.concatenate(
            [np.zeros((len(group), 1)), squares[:, lags[1:] - 1]], axis=1)
        diff = energy[:, None] + shifted - 2.0 * cross
        diff[:, 0] = 0.0
        running = np.cumsum(diff[:, 1:], axis=1) / np.arange(1, max_lag + 2)[None, :]
        cmnd = np.ones_like(diff)
        cmnd[:, 1:] = diff[:, 1:] / np.maximum(running, 1e-12)
        for row in range(len(group)):
            if not loud[row]:
                continue
            curve = cmnd[row]
            below = np.flatnonzero(curve[min_lag:max_lag] < YIN_THRESHOLD)
            if len(below):
                tau = min_lag + int(below[0])
                while tau + 1 < max_lag and curve[tau + 1] < curve[tau]:
                    tau += 1
            else:
                tau = min_lag + int(np.argmin(curve[min_lag:max_lag]))
                if curve[tau] > VOICED_LIMIT:
                    continue
            if 1 <= tau < len(curve) - 1:   # refine between samples
                a, b, c = curve[tau - 1], curve[tau], curve[tau + 1]
                bend = a - 2 * b + c
                offset = 0.5 * (a - c) / bend if abs(bend) > 1e-12 else 0.0
            else:
                offset = 0.0
            pitches[start + row] = sample_rate / (tau + max(-0.5, min(0.5, offset)))
    return pitches, centres


def repair_octaves(pitches):
    """Octave mistakes put right: a reading about twice or half its neighbours' is folded back, and one still
    more than 7 semitones from them is dropped (no correction there)."""
    pitches = np.asarray(pitches, dtype=np.float64).copy()
    voiced = np.flatnonzero(pitches > 0)
    if len(voiced) < 3:
        return pitches
    values = pitches[voiced]
    for n, i in enumerate(voiced):
        lo, hi = max(0, n - OCTAVE_WINDOW), min(len(voiced), n + OCTAVE_WINDOW + 1)
        near = [values[k] for k in range(lo, hi) if k != n and abs(int(voiced[k]) - int(i)) <= 2 * OCTAVE_WINDOW]
        if len(near) < 2:
            continue
        median = float(np.median(near))
        ratio = pitches[i] / median
        if abs(ratio - 2.0) < 0.06 * 2.0:
            pitches[i] /= 2.0
        elif abs(ratio - 0.5) < 0.06 * 0.5:
            pitches[i] *= 2.0
        if abs(12.0 * math.log2(pitches[i] / median)) > 7.0:
            pitches[i] = 0.0
    return pitches


def dead_zone(deviation):
    """How much of a deviation (semitones) to correct: none under 8 cents, all of it from 16 cents."""
    size = abs(deviation)
    low, high = DEAD_ZONE
    if size <= low:
        return 0.0
    if size >= high:
        return deviation
    x = (size - low) / (high - low)
    return deviation * x * x * (3.0 - 2.0 * x)


def hz_to_midi(hz):
    return 69.0 + 12.0 * np.log2(np.asarray(hz, dtype=np.float64) / 440.0)


def nearest_allowed(midi, pitch_classes):
    """The nearest note (a whole MIDI number) whose pitch class is allowed."""
    base = int(math.floor(midi))
    best, best_distance = base, 99.0
    for candidate in range(base - 6, base + 8):
        if candidate % 12 in pitch_classes:
            distance = abs(candidate - midi)
            if distance < best_distance:
                best, best_distance = candidate, distance
    return best


def corrections(pitches, centres, sample_rate, speed_ms, strength, allowed_at):
    """How many semitones to move each frame. allowed_at(sample) gives the allowed pitch classes."""
    count = len(pitches)
    result = np.zeros(count)
    alpha = 0.0 if speed_ms <= 0 else math.exp(-HOP / (speed_ms / 1000.0 * sample_rate))
    current = 0.0
    voiced_before = False
    for i in range(count):
        if pitches[i] <= 0:
            current = 0.0 if not voiced_before else current * 0.5
            voiced_before = False
            result[i] = 0.0
            continue
        midi = float(hz_to_midi(pitches[i]))
        target = dead_zone(nearest_allowed(midi, allowed_at(int(centres[i]))) - midi)
        if not voiced_before:
            current = target if alpha == 0.0 else target * (1.0 - alpha) + 0.0 * alpha
        else:
            current = alpha * current + (1.0 - alpha) * target
        voiced_before = True
        result[i] = current * strength
    return result


def psola(audio, sample_rate, pitches, centres, shifts):
    """Move the pitch of `audio` (frames, channels) by `shifts` semitones per frame, keeping its length."""
    audio = np.asarray(audio, dtype=np.float64)
    if audio.ndim == 1:
        audio = audio[:, None]
    frames = len(audio)
    if frames == 0 or not np.any(np.abs(shifts) > 1e-3):
        return audio.copy()
    mono = audio.mean(axis=1)
    sample_points = np.arange(frames)
    voiced = pitches > 0
    periods = np.where(voiced, sample_rate / np.maximum(pitches, 1.0), UNVOICED_STEP)
    period_at = np.interp(sample_points, centres, periods)
    voiced_at = np.interp(sample_points, centres, voiced.astype(float)) > 0.5
    ratio_at = 2.0 ** (np.interp(sample_points, centres, shifts) / 12.0)

    marks = analysis_marks(mono, period_at, voiced_at)
    if len(marks) < 2:
        return audio.copy()

    out = np.zeros_like(audio)
    weight = np.zeros(frames)
    synthesis = float(marks[0])
    while synthesis < frames:
        at = int(round(synthesis))
        nearest = int(np.argmin(np.abs(marks - at)))
        source = marks[nearest]
        spacing = float(period_at[source])
        ratio = ratio_at[min(at, frames - 1)] if voiced_at[source] else 1.0
        step = max(1.0, spacing) / max(0.25, ratio)
        # Each slice is one cycle (as long as the step to the next slice) plus a short crossfade on each side.
        # Long crossfades (the usual two-cycle Hann slices) mix two slices that are a little out of step
        # with each other, which cancels high frequencies like a comb: measured on a sung "ah" with
        # background noise, 6.5 dB lost between 4 and 8 kHz. Crossfades a fifth of a cycle long lose 0.4 dB.
        taper = max(16, int(TAPER * spacing))
        half = int(round(step / 2.0 + taper / 2.0))
        window = np.ones(2 * half + 1)
        ramp = 0.5 - 0.5 * np.cos(np.pi * (np.arange(taper) + 0.5) / taper)
        window[:taper] = ramp
        window[-taper:] = ramp[::-1]
        lo, hi = max(0, source - half), min(frames, source + half + 1)
        window = window[lo - source + half:hi - source + half]
        start = at - (source - lo)
        a, b = max(0, start), min(frames, start + (hi - lo))
        if b > a:
            piece = audio[lo + (a - start):lo + (b - start)] * window[a - start:b - start, None]
            out[a:b] += piece
            weight[a:b] += window[a - start:b - start]
        synthesis += step
    safe = np.maximum(weight, 1e-3)
    out /= safe[:, None]
    out[weight < 1e-3] = audio[weight < 1e-3]
    return out


def analysis_marks(mono, period_at, voiced_at):
    """One mark per wave cycle. A voiced stretch starts at its cycle's highest peak; each next mark is where
    the next cycle looks most like the one before (the same point of every cycle, steadier than peaks, which
    wander on low or breathy voices), found to a fraction of a sample so the marks never drift through the
    cycle. Where there is no pitch, marks are evenly spaced."""
    frames = len(mono)
    marks = []
    position = 0.0
    previous = None       # where the last voiced mark really is (a fraction of a sample)
    windows = np.lib.stride_tricks.sliding_window_view
    while position < frames:
        mark = int(position)
        here = min(mark, frames - 1)
        period = float(period_at[here])
        exact = float(mark)
        if voiced_at[here]:
            reach = max(1, int(period / 4))
            size = max(8, int(round(period)))
            half = size // 2
            anchor = int(round(previous)) if previous is not None else None
            guess = int(round(previous + period)) if previous is not None else mark
            lo, hi = max(0, guess - reach), min(frames, guess + reach + 1)
            if anchor is not None and anchor - half >= 0 and anchor - half + size <= frames \
                    and lo - half >= 0 and hi - 1 - half + size <= frames and hi - lo >= 3:
                reference = mono[anchor - half:anchor - half + size]
                candidates = windows(mono[lo - half:hi - 1 - half + size], size)
                norms = np.sqrt(np.einsum("ij,ij->i", candidates, candidates)) * (np.sqrt(reference @ reference) + 1e-12)
                scores = (candidates @ reference) / np.maximum(norms, 1e-12)
                best = int(np.argmax(scores))
                offset = 0.0
                if 0 < best < len(scores) - 1:
                    a, b, c = scores[best - 1], scores[best], scores[best + 1]
                    bend = a - 2.0 * b + c
                    offset = 0.5 * (a - c) / bend if abs(bend) > 1e-12 else 0.0
                exact = lo + best + max(-0.5, min(0.5, offset)) + (previous - anchor)
                mark = int(round(exact))
            else:
                lo, hi = max(0, mark - reach), min(frames, mark + reach + 1)
                if hi > lo:
                    mark = lo + int(np.argmax(mono[lo:hi]))   # the first cycle: its highest peak
                exact = float(mark)
            previous = exact
        else:
            previous = None
        if marks and mark <= marks[-1]:
            mark = marks[-1] + max(1, int(period / 2))
            exact = float(mark)
            if previous is not None:
                previous = exact
        if mark >= frames:
            break
        marks.append(mark)
        position = (exact if previous is not None else mark) + period
    return np.array(marks, dtype=np.int64)


def processing_mix(shifts, pitches, centres, frames, sample_rate):
    """For each sample, how much of the processed sound to use (0: the recording exactly as it was). A whole
    voiced stretch (a note or a phrase) is processed if any of it is really moved, and left exactly as recorded
    if none of it is, so the sound never switches back and forth inside a note; crossfades are CROSSFADE long."""
    voiced = pitches > 0
    active = np.zeros(len(pitches))
    start = None
    for i in range(len(pitches) + 1):
        on = i < len(pitches) and voiced[i]
        if on and start is None:
            start = i
        elif not on and start is not None:
            if np.any(np.abs(shifts[start:i]) > MOVED):
                active[start:i] = 1.0
            start = None
    if not np.any(active):
        return np.zeros(frames)
    per_sample = (np.interp(np.arange(frames), centres, active) > 0.5).astype(np.float64)
    # never longer than the recording: np.convolve's "same" gives the longer of the two lengths, so a recording
    # shorter than the crossfade (under 10 ms, with a clear pitch) used to stop pitch correction with an error
    fade = max(1, min(int(CROSSFADE * sample_rate), frames))
    ramp = np.convolve(per_sample, np.ones(fade) / fade, mode="same")
    reach = np.convolve(per_sample, np.ones(fade), mode="same") > 0
    return np.clip(np.where(reach, np.maximum(ramp, per_sample), 0.0), 0.0, 1.0)


def correct(audio, sample_rate, params, allowed_at):
    """Pitch-corrected copy of a recording.

    params: the effect's settings (speed, strength, scale). allowed_at(sample) returns the allowed
    pitch classes for that point of the recording (the song's key there)."""
    audio = np.asarray(audio, dtype=np.float64)
    if audio.ndim == 1:
        audio = audio[:, None]
    if params.get("scale") == "chromatic":
        allowed = set(range(12))

        def allowed_at(_sample, _allowed=allowed):  # noqa: F811 - every note is allowed
            return _allowed

    pitches, centres = detect_pitch(audio.mean(axis=1), sample_rate)
    pitches = repair_octaves(pitches)
    shifts = corrections(pitches, centres, sample_rate, float(params.get("speed", 60)),
                         float(params.get("strength", 100)) / 100.0, allowed_at)
    mix = processing_mix(shifts, pitches, centres, len(audio), sample_rate)
    if not np.any(mix > 0):
        return audio.astype(np.float32)                 # nothing to move: exactly as recorded
    moved = psola(audio, sample_rate, pitches, centres, shifts)
    return (audio * (1.0 - mix[:, None]) + moved * mix[:, None]).astype(np.float32)


def summary(audio, sample_rate):
    """(frames with a clear pitch, all frames): to tell whether correction can do anything."""
    pitches, _centres = detect_pitch(np.asarray(audio, dtype=np.float64).mean(axis=1)
                                     if np.ndim(audio) > 1 else audio, sample_rate)
    return int(np.count_nonzero(pitches)), len(pitches)
