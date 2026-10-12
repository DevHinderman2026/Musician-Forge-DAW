"""Where a project's files go: every project has its own folder.

    Musician Forge Songs
        My Song
            My Song.mforge     the project
            Recordings         sound recorded or imported into it
            Exports            WAV and MIDI files made from it

Saving a project somewhere else works the same way: Musician Forge makes the
project's folder wherever you choose. Projects saved by older versions (a
.mforge file on its own) keep working where they are; their recordings and
exports go into Recordings and Exports folders beside them.
"""

import datetime
import os

from . import paths
from .song import FILE_EXTENSION

RECORDINGS = "Recordings"
EXPORTS = "Exports"

_BAD_CHARACTERS = '<>:"/\\|?*'
_RESERVED = ({"CON", "PRN", "AUX", "NUL"} | {"COM{}".format(i) for i in range(1, 10)}
             | {"LPT{}".format(i) for i in range(1, 10)})
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]


def safe_name(name):
    """A project name Windows accepts as a file and folder name ("AC/DC" becomes "AC-DC")."""
    text = "".join("-" if ch in _BAD_CHARACTERS or ord(ch) < 32 else ch for ch in str(name or ""))
    text = text.strip().rstrip(". ")[:100].rstrip(". ")    # Windows drops a name's last dots and spaces
    if not text:
        text = "Untitled"
    base = text.split(".")[0]
    if base.strip().upper() in _RESERVED:      # "CON" and "CON.txt" both name a device: "CON song.txt"
        text = base + " song" + text[len(base):]
    return text


def project_path(parent_folder, name):
    """Where a project called `name` is saved inside `parent_folder`: in a folder of its own."""
    name = safe_name(name)
    return os.path.join(parent_folder, name, name + FILE_EXTENSION)


def project_name(path):
    return os.path.splitext(os.path.basename(path))[0]


def has_own_folder(path):
    """True if the project file is inside a folder named after it (My Song\\My Song.mforge)."""
    folder = os.path.basename(os.path.dirname(os.path.abspath(path)))
    return os.path.normcase(folder) == os.path.normcase(project_name(path))


def location_name(path):
    """Where a project is, the way it is spoken: the folder that holds the project's own folder."""
    folder = os.path.dirname(os.path.abspath(path))
    if has_own_folder(path):
        folder = os.path.dirname(folder)
    return os.path.basename(folder.rstrip("\\/")) or folder


def recordings_folder(project_file):
    return os.path.join(os.path.dirname(os.path.abspath(project_file)), RECORDINGS)


def exports_folder(project_file=None):
    """A saved project's Exports folder; before a project is saved, Musician Forge Songs\\Exports."""
    if project_file:
        return os.path.join(os.path.dirname(os.path.abspath(project_file)), EXPORTS)
    return os.path.join(paths.default_songs_dir(), EXPORTS)


def describe_file_location(path):
    """Where an exported file went, the way it is spoken: "the Exports folder of My Song"."""
    folder = os.path.dirname(os.path.abspath(path))
    name = os.path.basename(folder.rstrip("\\/")) or folder
    if os.path.normcase(name) == os.path.normcase(EXPORTS):
        owner = os.path.basename(os.path.dirname(folder).rstrip("\\/"))
        return "the Exports folder of {}".format(owner) if owner else "the Exports folder"
    return name


def find_projects(folder=None):
    """Every project in Musician Forge Songs (in its own folder, or a file on its own), newest first.

    Returns [(path, name, modified time)]."""
    folder = folder or paths.default_songs_dir()
    found = {}
    try:
        entries = list(os.scandir(folder))
    except OSError:
        return []
    for entry in entries:
        try:
            if entry.is_file() and entry.name.lower().endswith(FILE_EXTENSION):
                found[os.path.normcase(entry.path)] = entry.path
            elif entry.is_dir() and entry.name not in (EXPORTS, RECORDINGS):
                for inner in sorted(os.listdir(entry.path)):
                    if inner.lower().endswith(FILE_EXTENSION):
                        path = os.path.join(entry.path, inner)
                        found[os.path.normcase(path)] = path
        except OSError:
            continue
    projects = []
    for path in found.values():
        try:
            projects.append((path, project_name(path), os.path.getmtime(path)))
        except OSError:
            continue
    projects.sort(key=lambda item: (-item[2], item[1].lower()))
    return projects


def describe_time(timestamp, now=None):
    """'today at 8:15 PM', 'yesterday at 7:02 AM', 'October 3 at 9:30 PM', 'March 5, 2025'."""
    when = datetime.datetime.fromtimestamp(timestamp)
    now = now or datetime.datetime.now()
    clock = "{}:{:02d} {}".format(when.hour % 12 or 12, when.minute, "AM" if when.hour < 12 else "PM")
    days = (now.date() - when.date()).days
    if days == 0:
        return "today at " + clock
    if days == 1:
        return "yesterday at " + clock
    if when.year == now.year:
        return "{} {} at {}".format(MONTHS[when.month - 1], when.day, clock)
    return "{} {}, {}".format(MONTHS[when.month - 1], when.day, when.year)


def describe_project(path, modified, now=None):
    """One line of the Open project list: 'My Song, saved today at 8:15 PM'."""
    return "{}, saved {}".format(project_name(path), describe_time(modified, now))
