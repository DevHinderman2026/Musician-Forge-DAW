"""The two FreePats distorted electric guitar packs: downloading, unpacking and checking them.

Both are by FreePats and published under CC0 (public domain): free to use and to share, no
attribution needed (Credits.md thanks FreePats anyway). They are big (about 430 and 390
megabytes once unpacked), so they are not in the program folder or in Git: the installer
downloads them into %LOCALAPPDATA%\\MusicianForge\\soundfonts, and if the computer is offline then,
Musician Forge downloads them by itself the next time it starts with the internet available.
Nobody ever has to download a sound pack by hand.

Each download is checked by its exact size, unpacked with sevenzip.py (standard library only), and
the unpacked SoundFont is checked against the CRC stored in the archive and its exact size.
This module uses only the standard library, so the installer can use it before Musician Forge's own
Python environment exists.
"""

import logging
import os
import time
import urllib.request
from dataclasses import dataclass

from . import paths, sevenzip

log = logging.getLogger("musicianforge.packs")
USER_AGENT = "MusicianForge (guitar pack download)"


@dataclass(frozen=True)
class Pack:
    key: str
    name: str                 # what Musician Forge calls it (and the patch name)
    url: str
    archive_size: int         # bytes, to check the download
    sf2_size: int             # bytes of the unpacked SoundFont
    sf2_crc: int              # the CRC stored in the archive
    bank: int                 # the bank its instrument appears on (it is bank 0 inside the file)
    filename: str             # the unpacked SoundFont's name in the soundfonts folder
    page: str = "https://freepats.zenvoid.org/ElectricGuitar/distorted-electric-guitar.html"


PACKS = (
    Pack("dist1", "FSBS Electric Guitar Distorted 1",
         "https://github.com/freepats/electric-guitar-FSBS-dist1/releases/download/2022-09-11/"
         "EGuitarFSBS-dist1-SF2-20220911.7z", 332579821, 438272296, 0x06C359E7, 40,
         "FSBS-Electric-Guitar-Distorted-1.sf2"),
    Pack("dist2", "FSBS Electric Guitar Distorted 2",
         "https://github.com/freepats/electric-guitar-FSBS-dist2/releases/download/2022-09-11/"
         "EGuitarFSBS-dist2-SF2-20220911.7z", 127358936, 392689320, 0xBBAFC94B, 41,
         "FSBS-Electric-Guitar-Distorted-2.sf2"),
)
PACK_BY_BANK = {p.bank: p for p in PACKS}
STAND_IN = (0, 30, "Distortion Guitar")     # what plays until a pack is downloaded


class PackError(Exception):
    """A download or an unpack went wrong (the message says what, in plain words)."""


def soundfont_folder():
    return paths.soundfont_dir()


def installed_path(pack, folder=None):
    return os.path.join(folder or soundfont_folder(), pack.filename)


def is_installed(pack, folder=None):
    """True if the pack's SoundFont is there, complete (exact size) and really a SoundFont."""
    path = installed_path(pack, folder)
    try:
        if os.path.getsize(path) != pack.sf2_size:
            return False
        with open(path, "rb") as fh:
            head = fh.read(12)
        return head[:4] == b"RIFF" and head[8:12] == b"sfbk"
    except OSError:
        return False


def missing(folder=None):
    return [p for p in PACKS if not is_installed(p, folder)]


def describe_state(folder=None):
    """'Both guitar packs are installed.' or which one is still to come."""
    lacking = missing(folder)
    if not lacking:
        return "Both guitar packs are installed."
    if len(lacking) == len(PACKS):
        return ("The two guitar packs are not downloaded yet. Musician Forge downloads them by itself the next time "
                "it starts with the internet available. Until then a stand-in guitar plays.")
    return "{} is not downloaded yet; it downloads by itself the next time Musician Forge starts online.".format(
        lacking[0].name)


def download_file(url, dest, expected_size, progress=None, attempts=3, timeout=60):
    """Download url to dest (through dest + '.part'), checking the size. progress(fraction)."""
    last_error = None
    for attempt in range(1, attempts + 1):
        temp = dest + ".part"
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=timeout) as response, open(temp, "wb") as out:
                total = int(response.headers.get("Content-Length") or 0) or expected_size
                done = 0
                while True:
                    chunk = response.read(1 << 16)
                    if not chunk:
                        break
                    out.write(chunk)
                    done += len(chunk)
                    if progress is not None and total:
                        progress(min(1.0, done / float(total)))
            size = os.path.getsize(temp)
            if expected_size and size != expected_size:
                raise PackError("the download was {} bytes instead of {}".format(size, expected_size))
            os.replace(temp, dest)
            return dest
        except Exception as exc:  # noqa: BLE001 - every kind of network trouble gets another try
            last_error = exc
            if os.path.exists(temp):
                try:
                    os.remove(temp)
                except OSError:
                    pass
            if attempt < attempts:
                time.sleep(min(10, 2 * attempt))
    raise PackError("could not download it ({})".format(last_error))


def install_pack(pack, folder=None, progress=None, say=None, url=None, work_dir=None):
    """Download one pack, unpack its SoundFont into the soundfonts folder and check it.

    url and work_dir are for tests (a local server, a temporary folder). say(text) reports each
    stage in words. Returns the SoundFont's path. The downloaded archive is always deleted."""
    folder = folder or soundfont_folder()
    os.makedirs(folder, exist_ok=True)
    # The download waits in a folder of its own, emptied first: a download cut off by closing
    # Musician Forge or by losing the internet never leaves hundreds of megabytes behind.
    work = work_dir or os.path.join(folder, "downloading")
    os.makedirs(work, exist_ok=True)
    if work_dir is None:
        for name in os.listdir(work):
            try:
                os.remove(os.path.join(work, name))
            except OSError:
                pass
    archive = os.path.join(work, pack.key + ".7z")
    if os.path.exists(installed_path(pack, folder) + ".part"):     # an unpack that was cut off
        os.remove(installed_path(pack, folder) + ".part")
    say = say or (lambda text: None)
    try:
        say("Downloading {} ({} megabytes).".format(pack.name, pack.archive_size // 1_000_000))
        download_file(url or pack.url, archive, pack.archive_size,
                      progress=(lambda f: progress(0.7 * f)) if progress else None)
        say("Unpacking {}.".format(pack.name))
        try:
            entries = sevenzip.list_files(archive)
        except sevenzip.ArchiveError as exc:
            raise PackError(str(exc)) from None
        sf2 = [e for e in entries if e.name.lower().endswith(".sf2")]
        if not sf2:
            raise PackError("the download has no SoundFont in it")
        entry = max(sf2, key=lambda e: e.size)
        # the SoundFont must be the one the pack promises, by its exact size and the CRC the archive stores for it
        # (the review of 24 Oct 2026: sf2_crc was carried but never compared, so a download of the right size
        # holding another file of the right size would have been installed as the pack), before 400 megabytes
        # are unpacked for nothing
        if entry.size != pack.sf2_size:
            raise PackError("the download holds a SoundFont of {} bytes instead of {}".format(entry.size, pack.sf2_size))
        if pack.sf2_crc and entry.crc is not None and (entry.crc & 0xFFFFFFFF) != (pack.sf2_crc & 0xFFFFFFFF):
            raise PackError("the download is not the expected SoundFont (its check sum differs)")
        target = installed_path(pack, folder)
        try:
            sevenzip.extract_file(archive, entry, target,
                                  progress=(lambda f: progress(0.7 + 0.3 * f)) if progress else None)
        except sevenzip.ArchiveError as exc:
            raise PackError(str(exc)) from None
        if not is_installed(pack, folder):
            if os.path.exists(target):
                os.remove(target)
            raise PackError("the unpacked SoundFont is not the expected size")
        say("{} is ready.".format(pack.name))
        return target
    finally:
        try:
            if os.path.exists(archive):
                os.remove(archive)
        except OSError as exc:   # an antivirus program checking it: the pack is ready anyway (or the real error shows)
            log.warning("The downloaded %s could not be removed: %r", archive, exc)
        if work_dir is None:
            try:
                os.rmdir(work)
            except OSError:
                pass


def online(url="https://github.com", timeout=6):
    """A quick check that the internet is there (so nothing is attempted, or said, while offline)."""
    try:
        request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=timeout):
            return True
    except Exception:  # noqa: BLE001
        return False
