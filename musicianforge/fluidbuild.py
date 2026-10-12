"""Which FluidSynth builds Musician Forge can use on Windows. Standard library only: the installer and
Diagnose use it before (or without) Musician Forge's own Python environment.

Found on 8 October 2026, after the sound engine crashed on Windows from 0.7 on (exit code 0xC0000409):
FluidSynth 2.5.0 and later, when built for Windows without glib, reserves too little memory for the list of
outputs it mixes into. In src/utils/fluidsynth_priv.h the fallback of FLUID_DECLARE_VLA is

    _type *_name = (_type *)alloca(_len * sizeof(_type))

without brackets around _len, so for "buf_count * 2 + fx_buf_count * 2" it reserves
buf_count * 2 + fx_buf_count * 2 * 8 bytes instead of (buf_count * 2 + fx_buf_count * 2) * 8. With one or two
outputs that still fits (Windows rounds up to 16 bytes); with three or more FluidSynth writes past the end the
first time it makes sound, and Windows ends the program. Musician Forge gives every track its own output (128).

Microsoft's C compiler has no variable-length arrays, so every official Windows download takes that fallback:
the "cpp11" downloads of 2.5 and every 2.6 download (2.6 has no glib flavor). The "glib" downloads of 2.5 use
glib's g_newa(_type, (_len)), which has the brackets, and so does every version before 2.5. Checked three ways:
in the source, in the machine code of both Windows DLLs (2.6.1 computes 2 * outputs + 16 * effect buffers;
2.5.7 glib computes 16 * (outputs + effect buffers)), and by building 2.6.1 the way Microsoft's compiler does
(no variable-length arrays, stack protection on), which fails exactly the 13 steps of the sound engine check
that failed on Russell's laptop. 2.5.7 built the same way passes all 21.
"""

import os
import re

# What the installer downloads (tools\\install.py, step 3).
INSTALL_VERSION = "v2.5.7"
INSTALL_URL = ("https://github.com/FluidSynth/fluidsynth/releases/download/v2.5.7/"
               "fluidsynth-v2.5.7-win10-x64-glib.zip")
INSTALL_SIZE = 3412875            # bytes, checked 8 Oct 2026: anything else is a cut-off or wrong download
ENGINE_DLL = "libfluidsynth-3.dll"
GLIB_DLL = "libglib-2.0-0.dll"    # lies next to libfluidsynth-3.dll in the glib downloads

# When FluidSynth releases a version with the brackets put back, write it here (for example (2, 6, 2)) after
# checking its source; Windows builds from that version on are then accepted without glib. None: no fix yet.
FIRST_FIXED_VERSION = None


def parse_version(text):
    """(major, minor, patch) from "2.6.1", "v2.5.7" or "2.5.7-glib", or None."""
    match = re.match(r"v?(\d+)\.(\d+)(?:\.(\d+))?", (text or "").strip())
    if not match:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3) or 0)


def version_in_name(name):
    """The version in a download's folder name, such as "fluidsynth-v2.6.1-win10-x64-cpp11", or None."""
    match = re.search(r"(?<![\d.])v?(\d+\.\d+\.\d+)", name or "")
    return match.group(1) if match else None


def crashes_with_many_outputs(version_text, dll_folder, platform):
    """True for a Windows FluidSynth that ends the program as soon as it has three or more outputs: version
    2.5 or later without glib next to it. Other systems compile the arrays properly, so they are never
    affected. An unknown version counts as safe (nothing to go by)."""
    if platform != "win32":
        return False
    version = parse_version(version_text)
    if version is None or version[:2] < (2, 5):
        return False
    if FIRST_FIXED_VERSION is not None and version >= FIRST_FIXED_VERSION:
        return False
    return not os.path.isfile(os.path.join(dll_folder or "", GLIB_DLL))


def problem_sentence(version_text):
    return ("FluidSynth {} is a Windows build that crashes as soon as tracks have their own sound outputs "
            "(a fault in FluidSynth itself). Close Musician Forge, then run \"Install or Update Musician Forge\" "
            "to replace it with FluidSynth {}.".format(version_text, INSTALL_VERSION.lstrip("v")))


def check_download(zip_path):
    """Problems with a downloaded FluidSynth zip, in words (an empty list when it is good): the right size,
    nothing damaged inside, and the engine with glib next to it."""
    try:
        size = os.path.getsize(zip_path)
    except OSError as exc:
        return ["the download is missing ({})".format(exc)]
    if size != INSTALL_SIZE:
        return ["the download has {} bytes instead of {}".format(size, INSTALL_SIZE)]
    import zipfile

    try:
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
            damaged = zf.testzip()
    except zipfile.BadZipFile as exc:
        return ["the download is not a readable zip file ({})".format(exc)]
    except Exception as exc:  # noqa: BLE001 - damaged compressed data raises zlib.error, EOFError and others
        return ["the download is damaged ({})".format(exc)]
    if damaged is not None:
        return ["{} is damaged in the download".format(damaged)]
    folders = {n.rsplit("/", 1)[0] for n in names if n.rsplit("/", 1)[-1].lower() == ENGINE_DLL}
    if not folders:
        return ["the download does not contain {}".format(ENGINE_DLL)]
    if not any(folder + "/" + GLIB_DLL in names for folder in folders):
        return ["the download does not contain {} next to the engine".format(GLIB_DLL)]
    return []


def read_marker(path):
    """What the installer recorded about the engine it unpacked (fluidsynth\\installed.json): a dictionary,
    empty when there is none or it is damaged."""
    import json

    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def missing_files(folder, installed):
    """The files the installer unpacked that are no longer there (antivirus or a clean-up program can remove
    one, and then the engine cannot start). None when the record has no list of files."""
    files = installed.get("files")
    if not isinstance(files, list) or not files:
        return None
    return [name for name in files if not os.path.exists(os.path.join(folder, *str(name).split("/")))]
