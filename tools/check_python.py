"""Can Musician Forge use this Python?

Run by find_base_python.bat with each Python it finds (python.org's folders first, then the py launcher, then
"python"): it prints one plain sentence and ends with 0 when this Python can be used, or with another number when it
cannot, the sentence saying why and which Python to install. install.py and diagnose.py ask the same question
through problem().

Musician Forge needs a 64-bit Python (x64, also called AMD64), version 3.12, 3.13 or 3.14:
- numpy 2.5.3 (requirements.txt) needs Python 3.12 or newer;
- wxPython 4.3.1 has no build for Python 3.15 yet (3.15 came out on 9 October 2026, and python.org offers it first);
- the packages have no builds for ARM64 or 32-bit Python.

The Microsoft Store's Python (0.9.13; Russell, 10 Nov 2026: "if it detects Python from the Microsoft store, it will
reroute those packages to a user folder on that computer ... it won't write it in the hidden data folder"). The
Store's Python quietly moves every new file under AppData into a hidden folder of its own
(AppData\\Local\\Packages\\PythonSoftwareFoundation.Python...\\LocalCache), where only it can see it: an environment
made in %LOCALAPPDATA%\\MusicianForge could not run ("failed to locate pyvenv.cfg"), so until 0.9.13 the Store's
Python was refused and python.org's asked for. Outside AppData it moves nothing, so with the Store's Python Musician
Forge now keeps everything it sets up (its Python environment and packages, the instrument engine, the sounds, its
settings) in MusicianForge in the user's own folder, C:\\Users\\name\\MusicianForge (user_folder, data_folder).
python.org's Python is still used first when a computer has both, and keeps %LOCALAPPDATA%\\MusicianForge.

Standard library only, and old syntax only, so that even an old Python can say what is wrong. The sentences have no
brackets: a batch file prints them inside its blocks, where a bracket ends the block.
"""

import os
import sys
import sysconfig

MINIMUM = (3, 12)
NEWEST = (3, 14)
WANTED = "3.14"          # the Python to install (get_python.bat installs this one with winget)

OK, TOO_OLD, TOO_NEW, STORE, ARM64, BITS32 = 0, 2, 3, 4, 5, 6      # (STORE: until 0.9.13, the Store's Python refused)
DATA_NAME = "MusicianForge"
# In the user folder of an install made with the Store's Python: what the folder is (written once, so Remove
# Musician Forge knows the folder is Musician Forge's), and that it is the install in use (written by an install with
# the Store's Python, taken away by one with another Python; Start Musician Forge reads it).
ABOUT_FILE = "about_this_folder.txt"
IN_USE_FILE = "installed_with_store_python.txt"

INSTALL_WORDS = ("Please install Python {} from python.org: choose Install Now, which does not need administrator "
                 "rights.".format(WANTED))


def is_store_python(executable=None, prefix=None, base_executable=None):
    """True for the Microsoft Store's Python, which redirects new files in AppData to a private folder."""
    places = " ".join([executable or sys.executable, prefix or sys.prefix,
                       base_executable if base_executable is not None else getattr(sys, "_base_executable", "")])
    return "WindowsApps" in places or "PythonSoftwareFoundation.Python" in places


def user_folder(environ=None):
    """Where Musician Forge keeps its files when its Python is the Microsoft Store's: MusicianForge in the user's own
    folder (C:\\Users\\name\\MusicianForge). The Store's Python hides new files only under AppData."""
    environ = os.environ if environ is None else environ
    return os.path.join(environ.get("USERPROFILE") or os.path.expanduser("~"), DATA_NAME)


def data_folder(store=None, environ=None):
    """Musician Forge's data folder for an install with this Python: %LOCALAPPDATA%\\MusicianForge, or with the
    Microsoft Store's Python the user folder (user_folder)."""
    environ = os.environ if environ is None else environ
    if is_store_python() if store is None else store:
        return user_folder(environ)
    return os.path.join(environ.get("LOCALAPPDATA") or os.path.expanduser("~"), DATA_NAME)


def problem(version=None, platform_name=None, bits=None, store=None):
    """(code, sentence): OK and a short description when this Python can be used, or the reason it cannot."""
    version = tuple(version or sys.version_info[:3])
    platform_name = platform_name or sysconfig.get_platform()
    bits = bits or (64 if sys.maxsize > 2 ** 32 else 32)
    store = is_store_python() if store is None else store
    name = "{}.{}.{}".format(*version[:3]) if len(version) > 2 else "{}.{}".format(*version[:2])
    if version[:2] > NEWEST:
        return TOO_NEW, ("This computer's Python is {}, which is too new: some of the parts Musician Forge needs are "
                         "not made for it yet. Musician Forge needs Python {} from python.org, or 3.12 or 3.13, "
                         "which can be installed beside it.".format(name, WANTED))
    if version[:2] < MINIMUM:
        return TOO_OLD, ("This computer's Python is {}, which is too old. Musician Forge needs Python {} from "
                         "python.org, or 3.12 or 3.13.".format(name, WANTED))
    if "arm64" in platform_name.lower() or "aarch64" in platform_name.lower():
        return ARM64, ("This computer's Python {} is the ARM64 version, and the parts Musician Forge needs are not made "
                       "for it. Musician Forge needs the x64 version of Python {} from python.org, also called "
                       "AMD64; it runs on this computer too.".format(name, WANTED))
    if bits < 64:
        return BITS32, ("This computer's Python {} is the 32-bit version. Musician Forge needs the 64-bit version of "
                        "Python {} from python.org.".format(name, WANTED))
    if store:
        # (0.9.13: used, with Musician Forge's files in the user folder; see the top of this file)
        return OK, ("Python {}, 64-bit, from the Microsoft Store. Musician Forge keeps its files in the MusicianForge "
                    "folder of your user folder, where the Store version does not hide them.".format(name))
    return OK, "Python {}, 64-bit, from {}".format(name, sys.executable)


def main():
    code, sentence = problem()
    print(sentence)
    return code


if __name__ == "__main__":
    sys.exit(main())
