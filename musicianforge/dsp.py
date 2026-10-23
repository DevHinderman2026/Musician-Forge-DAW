"""Building blocks for Musician Forge's effects, written so numpy does the work.

Python is far too slow to run a filter one sample at a time in real time, so
every filter here is solved a whole block at a time:

- A first-order recursion y[n] = a * y[n-1] + x[n] has a closed form,
  y[n] = a**n * (a * y[-1] + sum over k <= n of a**-k * x[k]), which is a
  cumulative sum. The block is cut into pieces short enough that a**-k never
  overflows; most blocks are one piece.
- A second-order filter (the state-variable filter used for EQ, low cut and
  tone controls) is split into its two "modes", each a first-order recursion
  with a complex coefficient, then solved the same way. Its state is kept in
  the filter's own terms (the two integrators), so changing a setting while
  sound is playing does not click.
- Delays longer than the block read only sound that is already known, so a
  feedback delay is also solved a block at a time (in pieces no longer than
  the delay).

Everything is float64 inside and handles any number of columns (channels, or
the eight lines of the reverb) at once.
"""

import math

import numpy as np

_MAX_EXPONENT = 120.0   # largest power of ten allowed for a**-k inside one piece


_TINY = 1e-9            # coefficients smaller than this are treated as zero (no memory at all)


def _piece_length(smallest, frames):
    """How many samples one closed-form piece may cover, for the smallest coefficient size."""
    if smallest >= 1.0:
        return frames
    return max(1, min(frames, int(_MAX_EXPONENT / -math.log10(smallest))))


class PoleBank:
    """Many first-order recursions y[n] = a * y[n-1] + x[n] side by side (one per column), solved a
    block at a time. The powers of a are worked out once for each block size and kept, so a
    block costs only a cumulative sum and two multiplications."""

    def __init__(self, coefficients):
        a = np.atleast_1d(np.asarray(coefficients))
        self.complex = np.iscomplexobj(a)
        self.dtype = np.complex128 if self.complex else np.float64
        a = a.astype(self.dtype)
        self.zero = np.abs(a) < _TINY
        self.a = np.where(self.zero, 1.0, a).astype(self.dtype)
        self.any_zero = bool(np.any(self.zero))
        sizes = np.abs(self.a[~self.zero])
        self.smallest = float(np.min(sizes)) if sizes.size else 1.0
        self._pieces = {}

    def _plan(self, frames):
        plan = self._pieces.get(frames)
        if plan is None:
            step = _piece_length(self.smallest, frames)
            plan = []
            position = 0
            while position < frames:
                count = min(step, frames - position)
                k = np.arange(count, dtype=np.float64)[:, None]
                plan.append((position, count, self.a ** k, self.a ** -k))
                position += count
            if len(self._pieces) > 8:
                self._pieces.clear()
            self._pieces[frames] = plan
        return plan

    def run(self, x, state):
        """x: (frames, columns). state: y[-1] per column. Returns (y, new state)."""
        frames = x.shape[0]
        prev = np.asarray(state, dtype=self.dtype)
        if frames == 0:
            return np.zeros(x.shape, dtype=self.dtype), prev.copy()
        y = np.empty(x.shape, dtype=self.dtype)
        a = self.a
        for position, count, powers, inverse in self._plan(frames):
            piece = x[position:position + count]
            out = powers * (a * prev + np.cumsum(piece * inverse, axis=0))
            if self.any_zero:
                out[:, self.zero] = piece[:, self.zero]
            y[position:position + count] = out
            prev = out[-1]
        return y, prev.copy()


def one_pole(x, a, state):
    """Solve y[n] = a * y[n-1] + x[n] for a block (a convenience for occasional use; filters keep
    a PoleBank so the powers are not worked out again for every block).

    x: shaped (frames,) or (frames, columns). a: a number, or one per column. state: y[-1].
    Returns (y, new state)."""
    x = np.asarray(x)
    flat = x.ndim == 1
    columns = 1 if flat else x.shape[1]
    coefficients = np.broadcast_to(np.asarray(a), (columns,))
    if np.iscomplexobj(x) or np.iscomplexobj(state):
        coefficients = coefficients.astype(np.complex128)
    bank = PoleBank(coefficients)
    data = x[:, None] if flat else x
    if bank.dtype == np.complex128:
        data = data.astype(np.complex128)
    y, end = bank.run(data, np.broadcast_to(np.asarray(state), (columns,)))
    if flat:
        return y[:, 0], end[0]
    return y, end


# ----------------------------------------------------------------------
# the state-variable filter (Andrew Simper's trapezoidal form)
# ----------------------------------------------------------------------
SHAPES = ("lowpass", "highpass", "bell", "lowshelf", "highshelf")


def svf_section(sample_rate, shape, freq, q=0.7071, gain_db=0.0):
    """One state-variable filter as a little linear system: (A, B, C, D) with
    integrators' = A @ integrators + B * x and y = C @ integrators + D * x."""
    sample_rate = float(sample_rate)
    freq = min(max(float(freq), 5.0), sample_rate * 0.475)
    q = max(0.1, float(q))
    g = math.tan(math.pi * freq / sample_rate)
    k = 1.0 / q
    a = 10.0 ** (float(gain_db) / 40.0)
    if shape == "lowpass":
        m = (0.0, 0.0, 1.0)
    elif shape == "highpass":
        m = (1.0, -k, -1.0)
    elif shape == "bell":
        k = 1.0 / (q * a)
        m = (1.0, k * (a * a - 1.0), 0.0)
    elif shape == "lowshelf":
        g = g / math.sqrt(a)
        m = (1.0, k * (a - 1.0), a * a - 1.0)
    elif shape == "highshelf":
        g = g * math.sqrt(a)
        m = (a * a, k * (1.0 - a) * a, 1.0 - a * a)
    else:
        raise ValueError("unknown filter shape {}".format(shape))
    if abs(k - 2.0) < 1e-3:
        k = 2.002   # exactly critically damped has a repeated mode, which cannot be split; nudge it
    a1 = 1.0 / (1.0 + g * (g + k))
    a2 = g * a1
    a3 = g * a2
    m0, m1, m2 = m
    A = np.array([[2 * a1 - 1, -2 * a2], [2 * a2, 1 - 2 * a3]])
    B = np.array([2 * a2, 2 * a3])
    C = np.array([m1 * a1 + m2 * a2, -m1 * a2 + m2 * (1 - a3)])
    D = m0 + m1 * a2 + m2 * a3
    return A, B, C, D


def cascade(sections):
    """Several filters one after another, as one linear system (A, B, C, D)."""
    A = np.zeros((0, 0))
    B = np.zeros(0)
    C = np.zeros(0)
    D = 1.0
    for a2, b2, c2, d2 in sections:
        n1, n2 = len(B), len(b2)
        new_A = np.zeros((n1 + n2, n1 + n2))
        new_A[:n1, :n1] = A
        new_A[n1:, :n1] = np.outer(b2, C)       # the second filter hears the first one's output
        new_A[n1:, n1:] = a2
        new_B = np.concatenate([B, b2 * D])
        new_C = np.concatenate([d2 * C, c2])
        A, B, C, D = new_A, new_B, new_C, d2 * D
    return A, B, C, D


class FilterCascade:
    """Any number of state-variable filters in a row (an EQ is several), solved a block at a time.

    The whole row is one linear system; it is split into its modes, and every mode of every
    channel runs side by side in one PoleBank. The state is kept as the filters' own integrators,
    so settings can change while sound plays without a click.
    """

    def __init__(self, sample_rate, channels=2, sections=()):
        self.sample_rate = float(sample_rate)
        self.channels = int(channels)
        self.order = 0
        self.state = np.zeros((0, self.channels))
        self._key = None
        self.set_sections(sections)

    def set_sections(self, sections):
        """sections: a list of (shape, frequency, Q, gain in dB)."""
        key = tuple((s[0], float(s[1]), float(s[2]), float(s[3])) for s in sections)
        if key == self._key:
            return
        old_key = self._key or ()
        self._key = key
        parts = [svf_section(self.sample_rate, *s) for s in key]
        A, B, C, D = cascade(parts)
        order = len(B)
        if order != self.order:
            # A filter was added or taken away (an EQ band turned on or off while playing). The others keep
            # their state: starting them all from silence clicked (23 Oct 2026). The state is each filter's own
            # integrators, one after another, so each kept filter's rows move to where it now is.
            state = np.zeros((order, self.channels))
            old_sizes = [len(svf_section(self.sample_rate, *s)[1]) for s in old_key]
            old_starts = np.concatenate([[0], np.cumsum(old_sizes)]).astype(int) if old_sizes else [0]
            used = set()
            at = 0
            for section, part in zip(key, parts):
                size = len(part[1])
                for i, old in enumerate(old_key):
                    if i not in used and old[0] == section[0] and old_sizes[i] == size \
                            and old_starts[i] + size <= len(self.state):
                        used.add(i)
                        state[at:at + size] = self.state[old_starts[i]:old_starts[i] + size]
                        break
                at += size
            self.state = state
            self.order = order
        self.A, self.B, self.C, self.D = A, B, C, D
        self._bank = None
        if order == 0:
            return
        values, vectors = np.linalg.eig(A)
        vectors = vectors.astype(np.complex128)
        if np.linalg.cond(vectors) > 1e9:
            # two identical filters in a row cannot be split into modes: nudge one a tiny bit
            nudged = [(s[0], s[1] * (1.0 + 1e-3 * i), s[2], s[3]) for i, s in enumerate(key)]
            A, B, C, D = cascade([svf_section(self.sample_rate, *s) for s in nudged])
            self.A, self.B, self.C, self.D = A, B, C, D
            values, vectors = np.linalg.eig(A)
            vectors = vectors.astype(np.complex128)
        inverse = np.linalg.inv(vectors)
        # A real filter's modes come in mirror-image pairs; only one of each pair is computed and
        # its real part doubled, which halves the work.
        keep, factor = [], []
        for i, value in enumerate(values):
            if abs(value.imag) < 1e-12:
                keep.append(i)
                factor.append(1.0)
            elif value.imag > 0:
                keep.append(i)
                factor.append(2.0)
        keep = np.array(keep)
        factor = np.array(factor)
        c = self.channels
        k = len(keep)
        feed = (inverse @ B.astype(np.complex128))[keep]
        out = (C.astype(np.complex128) @ vectors)[keep] * factor
        eye = np.eye(c)
        self._feed = np.kron(feed[None, :], eye)              # (channels, modes * channels)
        self._out = np.kron(out[:, None], eye)                # (modes * channels, channels)
        self._to_modes = inverse[keep]                        # integrators -> kept modes
        self._to_state = vectors[:, keep] * factor            # kept modes -> integrators (real part)
        self._kept = k
        self._bank = PoleBank(np.repeat(values[keep].astype(np.complex128), c))

    def reset(self):
        self.state[:] = 0.0

    def process(self, x):
        """Filter a block shaped (frames, channels); returns a new float64 array."""
        x = np.asarray(x, dtype=np.float64)
        frames = x.shape[0]
        if self._bank is None:
            return x * self.D
        if frames == 0:
            return x.copy()
        c, k = self.channels, self._kept
        start = (self._to_modes @ self.state.astype(np.complex128)).reshape(-1)   # (modes * channels)
        modes, end = self._bank.run(x @ self._feed, start)
        before = np.empty_like(modes)       # the output uses the modes as they were before each sample
        before[0] = start
        before[1:] = modes[:-1]
        y = self.D * x + np.real(before @ self._out)
        self.state = np.real(self._to_state @ end.reshape(k, c))
        return y


class StateVariableFilter(FilterCascade):
    """One filter: low pass, high pass, bell, low shelf or high shelf."""

    SHAPES = SHAPES

    def __init__(self, sample_rate, channels=2, shape="lowpass", freq=1000.0, q=0.7071, gain_db=0.0):
        super().__init__(sample_rate, channels, [(shape, freq, q, gain_db)])

    def set(self, shape, freq, q=0.7071, gain_db=0.0):
        self.set_sections([(shape, freq, q, gain_db)])


class OnePoleLowpass:
    """A gentle 6 dB per octave low pass (for tone controls and reverb damping)."""

    def __init__(self, sample_rate, channels=2, freq=8000.0):
        self.sample_rate = float(sample_rate)
        self.state = np.zeros(channels)
        self.set(freq)

    def set(self, freq):
        freq = min(max(float(freq), 5.0), self.sample_rate * 0.49)
        a = math.exp(-2.0 * math.pi * freq / self.sample_rate)
        if getattr(self, "a", None) != a:
            self.a = a
            self._bank = PoleBank(np.full(len(self.state), a))

    def process(self, x):
        y, self.state = self._bank.run((1.0 - self.a) * np.asarray(x, dtype=np.float64), self.state)
        return y


class DCBlocker:
    """Removes any steady offset (a very low high pass), used after lopsided distortion."""

    def __init__(self, sample_rate, channels=2, freq=15.0):
        self.a = math.exp(-2.0 * math.pi * freq / float(sample_rate))
        self.last_in = np.zeros(channels)
        self.state = np.zeros(channels)
        self._bank = PoleBank(np.full(channels, self.a))

    def process(self, x):
        x = np.asarray(x, dtype=np.float64)
        if not len(x):
            return x.copy()
        diff = np.empty_like(x)
        diff[0] = x[0] - self.last_in
        diff[1:] = x[1:] - x[:-1]
        self.last_in = x[-1].copy()
        y, self.state = self._bank.run(diff, self.state)
        return y


# ----------------------------------------------------------------------
# delay lines
# ----------------------------------------------------------------------
class DelayLine:
    """A ring buffer holding the last `length` frames of several columns."""

    def __init__(self, length, columns=2):
        self.length = max(1, int(length))
        self.buffer = np.zeros((self.length, columns))
        self.position = 0          # where the next frame is written

    def read(self, delay, count):
        """`count` frames as they were `delay` frames before the next write position.
        delay must be at least `count` (the frames being read already exist)."""
        start = (self.position - int(delay)) % self.length
        return self._take(start, count)

    def read_columns(self, delays, count):
        """Like read, with a different delay for each column. Returns (count, columns)."""
        out = np.empty((count, self.buffer.shape[1]))
        for column, delay in enumerate(delays):
            start = (self.position - int(delay)) % self.length
            idx = (start + np.arange(count)) % self.length
            out[:, column] = self.buffer[idx, column]
        return out

    def _take(self, start, count):
        end = start + count
        if end <= self.length:
            return self.buffer[start:end].copy()
        first = self.length - start
        return np.concatenate([self.buffer[start:], self.buffer[:count - first]])

    def write(self, frames):
        frames = np.asarray(frames, dtype=np.float64)
        count = len(frames)
        if count >= self.length:
            self.buffer[:] = frames[-self.length:]
            self.position = 0
            return
        end = self.position + count
        if end <= self.length:
            self.buffer[self.position:end] = frames
        else:
            first = self.length - self.position
            self.buffer[self.position:] = frames[:first]
            self.buffer[:count - first] = frames[first:]
        self.position = end % self.length

    def clear(self):
        self.buffer[:] = 0.0


def db_to_gain(db):
    return 10.0 ** (float(db) / 20.0)


def gain_to_db(gain):
    return 20.0 * math.log10(max(float(gain), 1e-12))


def ramp(start, end, frames):
    """A straight line from start to end over a block, shaped (frames, 1), for click-free changes.
    When nothing changes it is just the number (multiplying by a number is quicker)."""
    if start == end:
        return float(end)
    if frames <= 0:
        return np.zeros((0, 1))
    step = (float(end) - float(start)) / frames
    return (float(start) + step * np.arange(1, frames + 1))[:, None]
