"""Where Musician Forge keeps its files.

- Program files (this code) live in the Musician Forge folder you installed.
- Large downloads (Python environment, instrument engine, SoundFonts) live in
  %LOCALAPPDATA%\\MusicianForge, outside OneDrive, so they never sync or get
  turned into online-only files.
- With the Microsoft Store's Python (0.9.13) they live in MusicianForge in the
  user's own folder instead (C:\\Users\\name\\MusicianForge): the Store's Python
  hides every new file under AppData in a folder only it can see, so settings,
  sounds and the environment itself would be out of reach of everything else
  (Russell, 10 Nov 2026; tools\\check_python.py and tools\\install.py choose the
  same folder when installing).
- Logs live in the program folder's "logs" folder, so they are easy to find.
"""

import os
import sys
import time

from . import legacy

PROGRAM_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_NAME = "MusicianForge"


def on_store_python():
    """True when Musician Forge runs on the Microsoft Store's Python (its own environment made from it too): the
    program's or its base Python's place names the Store's package or its WindowsApps folder."""
    places = " ".join(str(place) for place in (
        sys.executable, sys.prefix, getattr(sys, "base_prefix", ""), getattr(sys, "_base_executable", "")) if place)
    return "WindowsApps" in places or "PythonSoftwareFoundation.Python" in places


def store_data_dir():
    """The data folder of an install made with the Microsoft Store's Python: MusicianForge in the user's own
    folder (the same as tools\\check_python.py's user_folder)."""
    return os.path.join(os.environ.get("USERPROFILE") or os.path.expanduser("~"), DATA_NAME)


def local_data_dir():
    if on_store_python():
        return store_data_dir()
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        base = os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, "MusicianForge")


def venv_dir():
    return os.path.join(local_data_dir(), "venv")


def fluidsynth_dir():
    return os.path.join(local_data_dir(), "fluidsynth")


def soundfont_dir():
    return os.path.join(local_data_dir(), "soundfonts")


def default_soundfont():
    return os.path.join(soundfont_dir(), "GeneralUser-GS.sf2")


def settings_file():
    return os.path.join(local_data_dir(), "settings.json")


def autosave_dir():
    return os.path.join(local_data_dir(), "autosave")


def logs_dir():
    return os.path.join(PROGRAM_DIR, "logs")


def default_songs_dir():
    """Documents\\Musician Forge Songs (created on first save). If the folder from before the rename (Melody
    Forge Songs) is still there because Windows would not rename it, that one is used, so nothing looks lost."""
    docs = legacy.documents_dir()
    new = os.path.join(docs, legacy.NEW_SONGS_NAME)
    old = os.path.join(docs, legacy.OLD_SONGS_NAME)
    if not os.path.isdir(new) and os.path.isdir(old):
        return old
    return new


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)
    return path


def replace_file(source, target, attempts=10, wait=0.1):
    """os.replace, trying again for up to a second while Windows says the file is in use: OneDrive (where
    Documents usually is) or an antivirus program can hold a file for a moment right after it was written, and
    saving would fail with "access denied" (found in the review of 9 Oct 2026)."""
    for attempt in range(attempts):
        try:
            os.replace(source, target)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(wait)
