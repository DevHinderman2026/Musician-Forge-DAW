"""A soft start for microphone sound (Russell, 10 Oct 2026: "a harsh pop when it activates").

A microphone's first moments after it opens can hold a jolt: the converter and Windows' processing settle, and a
laptop's microphone array is known for it (the delay measurement already waits 0.4 seconds "while the microphone
settles"). StartFade keeps the first `quiet` seconds silent and then fades in over `fade` seconds, so neither
hearing yourself nor the take starts with a click. Pieces keep their length, so timing is untouched."""

import numpy as np

# Russell, 21 Oct 2026: "there is still a slight popping ... increase that slightly ... it's barely noticeable" (with
# audio recording). From 60 ms silent and a 15 ms straight fade to 80 ms and a 25 ms rounded (raised-cosine) fade,
# which starts and ends without a corner, so it adds no click of its own.
QUIET_SECONDS = 0.08         # the microphone's first 80 ms: silent
FADE_SECONDS = 0.025         # then 25 ms to full level


class StartFade:
    def __init__(self, rate, quiet=QUIET_SECONDS, fade=FADE_SECONDS):
        self.quiet = max(0, int(round(quiet * rate)))
        self.fade = max(1, int(round(fade * rate)))
        self.done = 0                       # frames already through

    @property
    def finished(self):
        return self.done >= self.quiet + self.fade

    def apply(self, data):
        """data: (frames, channels) float32. Returns it softened where it falls in the start (a copy when changed;
        the caller's array is never changed)."""
        frames = len(data)
        if self.finished or not frames:
            self.done += frames
            return data
        positions = np.arange(self.done, self.done + frames, dtype=np.float32)
        ramp = np.clip((positions - self.quiet + 0.5) / self.fade, 0.0, 1.0)
        gain = (0.5 - 0.5 * np.cos(np.pi * ramp))[:, None]          # rounded at both ends
        self.done += frames
        return (data * gain).astype(np.float32, copy=False)
