"""Moving the folders the program used before it was renamed (8 Oct 2026: Melody Forge became Musician Forge).

Two folders carried the old name:
- the data folder, %LOCALAPPDATA%\\MelodyForge (Python environment, instrument engine, sounds, settings),
- the songs folder, Documents\\Melody Forge Songs (every project, its recordings and exports).

Both are moved, not copied, with one rename each, so nothing is duplicated and nothing is lost. Projects keep
working: a saved project finds its recordings next to itself. The only absolute paths stored anywhere are in
settings.json (the recent projects) and the autosave folder, and those are rewritten to the new folder.

Standard library only: the installer uses this before Musician Forge's own environment exists.
"""

import json
import os
import sys

OLD_DATA_NAME = "MelodyForge"
NEW_DATA_NAME = "MusicianForge"
OLD_SONGS_NAME = "Melody Forge Songs"
NEW_SONGS_NAME = "Musician Forge Songs"
OLD_KIT_PREFIX = "Melody-Forge-Kits"


def documents_dir():
    """The Documents folder (the real one even when OneDrive has moved it)."""
    docs = None
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
            CSIDL_PERSONAL = 5
            if ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_PERSONAL, None, 0, buf) == 0:
                docs = buf.value
        except Exception:  # noqa: BLE001
            docs = None
    return docs or os.path.join(os.path.expanduser("~"), "Documents")


def local_base():
    return os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), ".local", "share")


def _has_files(folder):
    for _root, _dirs, files in os.walk(folder):
        if files:
            return True
    return False


def _remove_empty_tree(folder):
    """Remove a folder that holds no files at all (only empty folders). Never removes a file."""
    for root, dirs, _files in os.walk(folder, topdown=False):
        for name in dirs:
            try:
                os.rmdir(os.path.join(root, name))
            except OSError:
                pass
    os.rmdir(folder)


def _move(old, new, what):
    """Move one folder. Returns (state, sentence): state is "none" (nothing to do), "moved", "both" (the
    new one already has files, so nothing moved) or "blocked" (Windows would not rename it)."""
    if not os.path.isdir(old):
        return "none", ""
    if os.path.isdir(new):
        if _has_files(new):
            return "both", ("Both {} and {} exist, so nothing was moved. Musician Forge uses {}; the old "
                            "folder is untouched.".format(old, new, new))
        try:
            _remove_empty_tree(new)
        except OSError:
            return "both", "{} exists and could not be replaced, so {} was not moved.".format(new, old)
    try:
        os.rename(old, new)
    except OSError as exc:
        return "blocked", ("The {} {} could not be renamed to {} ({}). Close everything that may be using it, "
                           "such as File Explorer windows, then try again.".format(what, old, new, exc))
    return "moved", "The {} was renamed from {} to {}.".format(what, old, new)


def _rewrite_strings(value, mapping):
    """Replace the start of every string that begins with an old folder by its new folder (case-insensitive,
    as Windows paths are). Returns (new value, whether anything changed)."""
    if isinstance(value, str):
        folded = value.lower()
        for old, new in mapping:
            rest = value[len(old):]
            # the folder itself or something inside it, not "Melody Forge Songs Backup"
            if folded.startswith(old.lower()) and (not rest or rest[0] in "\\/"):
                return new + rest, True
        return value, False
    if isinstance(value, list):
        changed = False
        out = []
        for item in value:
            new_item, did = _rewrite_strings(item, mapping)
            out.append(new_item)
            changed = changed or did
        return out, changed
    if isinstance(value, dict):
        changed = False
        out = {}
        for key, item in value.items():
            new_item, did = _rewrite_strings(item, mapping)
            out[key] = new_item
            changed = changed or did
        return out, changed
    return value, False


def _rewrite_file(path, mapping):
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return False
    data, changed = _rewrite_strings(data, mapping)
    if changed:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=1)
        os.replace(tmp, path)
    return changed


def migrate(base=None, docs=None):
    """Move the old folders to their new names. Returns (sentences, blocked): what happened in words (empty
    when there was nothing to move) and whether the data folder could not be moved. Safe to run every time."""
    base = base or local_base()
    docs = docs or documents_dir()
    old_data, new_data = os.path.join(base, OLD_DATA_NAME), os.path.join(base, NEW_DATA_NAME)
    old_songs, new_songs = os.path.join(docs, OLD_SONGS_NAME), os.path.join(docs, NEW_SONGS_NAME)
    sentences, mapping, blocked = [], [], False
    state, text = _move(old_data, new_data, "data folder")
    if text:
        sentences.append(text)
    blocked = state == "blocked"
    if state == "moved":
        mapping.append((old_data, new_data))
        soundfonts = os.path.join(new_data, "soundfonts")
        if os.path.isdir(soundfonts):
            for name in os.listdir(soundfonts):       # the kit file is built again under its new name
                if name.startswith(OLD_KIT_PREFIX) and name.endswith(".sf2"):
                    try:
                        os.remove(os.path.join(soundfonts, name))
                    except OSError:
                        pass
    state, text = _move(old_songs, new_songs, "songs folder")
    if text:
        sentences.append(text)
    if state == "moved":
        mapping.append((old_songs, new_songs))
    if mapping:
        settings = os.path.join(new_data, "settings.json")
        if os.path.isfile(settings):
            _rewrite_file(settings, mapping)
        autosave = os.path.join(new_data, "autosave")
        if os.path.isdir(autosave):
            for name in os.listdir(autosave):
                _rewrite_file(os.path.join(autosave, name), mapping)
    return sentences, blocked
