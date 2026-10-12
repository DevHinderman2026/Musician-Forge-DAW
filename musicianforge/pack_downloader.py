"""Downloading the guitar packs in the background, when the installer could not (no internet then).

At start-up Musician Forge looks for the two packs. If one is missing and the internet is there, it
says so once, downloads and unpacks the pack while you keep working, and has the engine load it
(see Engine.load_soundfont): tracks using the stand-in guitar switch to the real one. If the
internet is not there, nothing is said and nothing breaks; it tries again at the next start.
"""

import logging
import threading

from . import packs

log = logging.getLogger("musicianforge.packs")


class PackDownloader(threading.Thread):
    def __init__(self, engine, say, folder=None, is_online=packs.online, install=packs.install_pack):
        super().__init__(name="guitar pack download", daemon=True)
        self.engine = engine
        self.say = say                  # say(text): spoken through the screen reader (called from this thread)
        self.folder = folder
        self.is_online = is_online
        self.install = install
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
            for pack in lacking:
                try:
                    path = self.install(pack, self.folder, say=log.info)
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
