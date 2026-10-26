"""Downloading the guitar packs in the background, when the installer could not (no internet then).

At start-up Musician Forge looks for the two packs. If one is missing and the internet is there, it
says so once, downloads and unpacks the pack while you keep working, and has the engine load it
(see Engine.load_soundfont): tracks using the stand-in guitar switch to the real one. If the
internet is not there, nothing is said and nothing breaks; it tries again at the next start.
A pack that comes but is not right (the wrong file or size, damaged, no SoundFont in it) is removed and said in
plain words, and the other pack is still downloaded (Russell, 25 Oct 2026); a lost connection or a full disk
stops the download with one message, as the other pack would fail the same way.
"""

import logging
import threading
import time

from . import packs

log = logging.getLogger("musicianforge.packs")
# seconds between saying a pack's problem and "Now downloading" the other: app.py hands the words to say_after, which
# says them two seconds later, and newer words take the place of words still waiting there (so, at once, the problem
# would never be heard)
PAUSE = 3.0


class PackDownloader(threading.Thread):
    def __init__(self, engine, say, folder=None, is_online=packs.online, install=packs.install_pack, pause=PAUSE):
        super().__init__(name="guitar pack download", daemon=True)
        self.engine = engine
        self.say = say                  # say(text): spoken through the screen reader (called from this thread)
        self.folder = folder
        self.is_online = is_online
        self.install = install
        self.pause = pause              # seconds (PAUSE; the tests make it short)
        self.finished = []              # packs downloaded by this run
        self.failed = []                # (pack, reason)

    def run(self):
        try:
            lacking = packs.missing(self.folder)
            if not lacking:
                return
            if not self.is_online():
                log.info("Guitar packs missing (%s); no internet, so they download another time",
                         ", ".join(p.name for p in lacking))
                return
            if len(lacking) == len(packs.PACKS):
                self.say("Downloading the two guitar packs in the background. Keep working; Musician Forge says when "
                         "each one is ready.")
            else:
                self.say("Downloading {} in the background.".format(lacking[0].name))
            after_problem = False
            for pack in lacking:
                if after_problem:
                    time.sleep(self.pause)              # (PAUSE: the problem is said before these words come)
                    self.say("Now downloading {}.".format(pack.name))
                    after_problem = False
                try:
                    path = self.install(pack, self.folder, say=log.info)
                except packs.PackCheckError as exc:
                    # it came, but it is not right (the wrong file or size, damaged, no SoundFont in it): said in
                    # its own plain words (0.9.11), which say that it was removed and is tried again at the next
                    # start (the exact numbers are in the log only). The other pack is still downloaded now
                    # (Russell, 25 Oct 2026: before, a first pack that came wrong at every start kept the second
                    # away for good)
                    log.warning("Downloading %s: %s", pack.name, exc)
                    self.failed.append((pack, str(exc)))
                    self.say("{}: {}".format(pack.name, exc))
                    after_problem = True
                    continue
                except Exception as exc:  # noqa: BLE001 - it tries again at the next start
                    log.exception("Downloading %s failed", pack.name)
                    self.failed.append((pack, str(exc)))
                    self.say("{} could not be downloaded. Musician Forge tries again the next time it starts."
                             .format(pack.name))
                    break           # the internet probably went away: one message is enough
                self.finished.append(pack)
                self.engine.load_soundfont(path, pack.bank)   # the engine says when it is ready
        except Exception:  # noqa: BLE001 - never take the program down
            log.exception("The guitar pack download stopped")
