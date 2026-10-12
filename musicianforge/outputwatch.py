"""Following Windows when headphones are plugged in or unplugged (Russell, 9 Oct 2026: "the program needs to be
smart enough to switch between speaker and headphones").

On many laptops the headphone jack is an output of its own (on Russell's, "Realtek HD Audio 2nd output" beside
"Speakers"), and Windows makes it the default output while headphones are plugged in. Until 0.9.3 Musician Forge
kept playing on the output it opened at start, so plugging in headphones changed nothing, and unplugging them
left it playing into an output that was gone.

A background thread asks Windows which output is the default, twice a second (read only: Windows' own
IMMDeviceEnumerator::GetDefaultAudioEndpoint, through the same COM code as lowlatency.py). The project window's
timer asks `OutputWatch.changed()`; when the default has changed and stayed changed, it reopens the sound on the
new default (audio.AudioOutput.reopen, which also refreshes PortAudio's list of devices: an output plugged in
after start is not in the list PortAudio made at start). It does that only when Audio settings say "Windows
default"; an output chosen by name stays chosen. While recording, or while the microphone is open, the switch
waits until it is closed, since starting the sound system again closes the microphone too.

Nothing here changes any Windows setting.
"""

import logging
import sys
import threading

log = logging.getLogger("musicianforge.outputwatch")

POLL_SECONDS = 0.5
STEADY_READINGS = 2     # the same new default twice in a row (a second at most): a jack's contacts can bounce


def default_output_name():
    """The friendly name of Windows' default output now ("Speakers (Realtek(R) Audio)"), or None if it cannot be
    read (not Windows, or Windows did not answer). Must run on a thread with COM (see OutputWatch)."""
    from . import lowlatency as ll

    win = ll._Windows.get()
    enum = ll._enumerator(win)
    try:
        device = ll.ctypes.c_void_p()
        hr = ll._method(enum, ll.ENUM_DEFAULT, ll.ctypes.c_int, ll.ctypes.c_int,
                        ll.ctypes.POINTER(ll.ctypes.c_void_p))(ll.E_RENDER, ll.E_CONSOLE, ll.ctypes.byref(device))
        if ll._failed(hr):
            return None       # no output at all just now (every output unplugged or switched off)
        try:
            return ll._friendly_name(win, device) or None
        finally:
            ll._release(device)
    finally:
        ll._release(enum)


class OutputWatch:
    """Remembers Windows' default output as it was when the sound was opened (`acknowledge`), and reports a new one
    once it has held for STEADY_READINGS readings (`changed`). `read` is called on the watch's own thread (tests
    pass their own and call `reading` directly instead of starting the thread)."""

    def __init__(self, read=default_output_name, interval=POLL_SECONDS):
        self.read = read
        self.interval = interval
        self.acknowledged = None     # the default output the sound is on (as Windows names it)
        self._candidate = None
        self._count = 0
        self._steady = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None

    # -- the thread ------------------------------------------------------------
    def start(self):
        if sys.platform != "win32" or self._thread is not None:
            return False
        self._thread = threading.Thread(target=self._run, name="Musician Forge output watch", daemon=True)
        self._thread.start()
        return True

    def stop(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(2.0)
            self._thread = None

    def _run(self):
        from . import lowlatency as ll

        try:
            com = ll._Com()
        except Exception:  # noqa: BLE001 - without it, Musician Forge simply does not follow
            log.exception("Could not start watching the default output")
            return
        failures = 0
        try:
            while not self._stop.wait(self.interval):
                try:
                    self.reading(self.read())
                    failures = 0
                except Exception:  # noqa: BLE001
                    failures += 1
                    if failures == 1:       # once, not twice a second
                        log.exception("Could not read Windows' default output")
        finally:
            com.close()

    # -- the readings ----------------------------------------------------------
    def reading(self, name):
        """One reading of the default output's name (None: none could be read)."""
        if not name:
            return
        with self._lock:
            if self.acknowledged is None:
                self.acknowledged = name          # the first reading: where the sound opened
                return
            if name == self._candidate:
                self._count += 1
            else:
                self._candidate, self._count = name, 1
            self._steady = name if self._count >= STEADY_READINGS else self._steady
            if name == self.acknowledged:
                self._steady = None               # it went back before anything was done

    def changed(self):
        """The new default output's name, when it differs from the one acknowledged and has held; else None."""
        with self._lock:
            if self._steady is not None and self._steady != self.acknowledged:
                return self._steady
            return None

    def acknowledge(self, name):
        """The sound is now on `name` (or was left where it is, deliberately)."""
        with self._lock:
            self.acknowledged = name
            self._steady = None
