"""Install or update everything Musician Forge needs.

Run through "Install or Update Musician Forge.bat". Uses only the Python
standard library. Short progress messages go to the console so a screen reader
can read them; full details go to logs\\install_log.txt.

Steps:
0. If the folders from before the rename (Melody Forge) exist, they are renamed first, so nothing is
   downloaded twice and no song is lost (see musicianforge\\legacy.py).
1. Create Musician Forge's own Python environment in %LOCALAPPDATA%\\MusicianForge\\venv
   (kept separate from your other Python projects).
2. Install the Python packages listed in requirements.txt into it.
3. Download the FluidSynth instrument engine.
4. Download the GeneralUser GS SoundFont (the instrument sounds).
5. and 6. Download the two FreePats distorted electric guitar packs (one step each). Without the
   internet these two steps are skipped and Musician Forge downloads the packs by itself later.
7. Run a self check: load everything, play a test note silently, measure it,
   and speak a message through your screen reader.
"""

import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import time
import urllib.request
import zipfile

PROGRAM_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "MusicianForge")
VENV_DIR = os.path.join(DATA_DIR, "venv")
VENV_PY = os.path.join(VENV_DIR, "Scripts", "python.exe")
FLUID_DIR = os.path.join(DATA_DIR, "fluidsynth")
SF_DIR = os.path.join(DATA_DIR, "soundfonts")
LOG_PATH = os.path.join(PROGRAM_DIR, "logs", "install_log.txt")
# Written when an install starts and removed once everything Musician Forge needs to start is installed; while it is
# there, "Start Musician Forge" will not start (an install that stopped partway left a program that closed at once,
# without a word). An install from before 0.9.7 has no marker at all and starts as before (23 Oct 2026: the first
# version of this check waited for an "install finished" file older installs never had, so Start refused them).
UNFINISHED_MARKER = os.path.join(DATA_DIR, "install_unfinished.json")
# What "Install or Update Musician Forge" and get_python.bat did to find Python (and to install it with winget).
PYTHON_SETUP_LOG = os.path.join(tempfile.gettempdir(), "musicianforge_python_setup.txt")

# GeneralUser GS 2.0.3, pinned to the commit that added it ("Update SoundFont to v2.0.3", 22 Feb 2026), so a newer
# version on main (another size) can never make every install fail its size check
SOUNDFONT_COMMIT = "97049183643d5fc5a9322a69c5b09efb667c6c3a"
SOUNDFONT_URL = "https://github.com/mrbumpy409/GeneralUser-GS/raw/{}/GeneralUser-GS.sf2".format(SOUNDFONT_COMMIT)
SOUNDFONT_LICENSE_URL = "https://github.com/mrbumpy409/GeneralUser-GS/raw/{}/documentation/LICENSE.txt".format(
    SOUNDFONT_COMMIT)
SOUNDFONT_SIZE = 32319396
USER_AGENT = "MusicianForge-installer/1.0"
TOTAL_STEPS = 7

sys.path.insert(0, PROGRAM_DIR)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_python  # noqa: E402
from musicianforge import __version__, fluidbuild, legacy, packs  # noqa: E402  (standard library only)

# FluidSynth 2.5.7, the glib download: every 2.6 Windows download (and the "cpp11" 2.5 ones) crashes as soon
# as tracks have their own outputs (see musicianforge\fluidbuild.py; found 8 Oct 2026).
FLUIDSYNTH_VERSION = fluidbuild.INSTALL_VERSION
FLUIDSYNTH_URL = fluidbuild.INSTALL_URL

_log_file = None
LOGS_DIR = None         # set when the Musician Forge folder cannot be written to (open_log)


def say(message):
    """A short line for the console (read by the screen reader) and the log."""
    print(message, flush=True)
    write_log(message)


def write_log(message):
    stamp = datetime.datetime.now().strftime("%H:%M:%S")
    for line in str(message).splitlines() or [""]:
        _log_file.write("[{}] {}\n".format(stamp, line))
    _log_file.flush()


def exit_text(code):
    """An exit code in the form Windows people look up: 3221226505 is 0xC0000409."""
    return "0x{:08X}".format(code & 0xFFFFFFFF) if code < 0 or code > 255 else str(code)


def child_environment():
    """For the programs the installer runs: Python prints in UTF-8, so a name such as José or a screen reader's
    name with an accent cannot stop the self check (a pipe is cp1252 otherwise, which has no room for many letters)."""
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    env["MUSICIANFORGE_LOGS_DIR"] = LOGS_DIR or os.path.join(PROGRAM_DIR, "logs")   # where selfcheck.py reports
    return env


def run_logged(cmd, timeout=1800):
    """Run a program and write everything it prints to the log. Returns its exit code; what it printed
    stays in run_logged.output."""
    write_log("RUN: " + " ".join('"{}"'.format(c) if " " in c else c for c in cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                          encoding="utf-8", errors="replace", env=child_environment())
    run_logged.output = proc.stdout
    write_log(proc.stdout)
    write_log(proc.stderr)
    write_log("EXIT CODE: {}".format(proc.returncode))
    return proc.returncode


run_logged.output = ""


def download(url, dest, expected_size=None, label="file"):
    """Download with retries; report progress every 25 percent."""
    last_error = None
    for attempt in range(1, 4):
        tmp = dest + ".part"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=60) as resp, open(tmp, "wb") as out:
                total = int(resp.headers.get("Content-Length") or 0) or expected_size or 0
                done, next_report = 0, 25
                while True:
                    chunk = resp.read(1 << 16)
                    if not chunk:
                        break
                    out.write(chunk)
                    done += len(chunk)
                    if total and done * 100 // total >= next_report and next_report < 100:
                        say("  {} download {} percent".format(label, next_report))
                        next_report += 25
            size = os.path.getsize(tmp)
            if expected_size and size != expected_size:
                raise IOError("expected {} bytes but got {}".format(expected_size, size))
            os.replace(tmp, dest)
            write_log("Downloaded {} ({} bytes) to {}".format(url, size, dest))
            return dest
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            write_log("Download attempt {} failed: {!r}".format(attempt, exc))
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError as busy:     # an antivirus program checking the part file: the next try writes
                    write_log("Removing {} failed: {!r}".format(tmp, busy))   # it again from the start
            time.sleep(2 * attempt)
    raise RuntimeError("Could not download {}: {}".format(label, last_error))


def is_store_python(executable=None, prefix=None):
    """True for the Microsoft Store's Python, which redirects new files in AppData to a private folder."""
    return check_python.is_store_python(executable, prefix)


def python_problem():
    """Why this Python cannot be used (check_python.py), or None. Python 3.15 came out on 9 Oct 2026 and the py
    launcher picked it, but wxPython 4.3.1 has no build for it; numpy 2.5.3 needs 3.12 or newer."""
    code, sentence = check_python.problem(store=is_store_python())
    if code == check_python.OK:
        return None
    return "{} {} Then run Install or Update Musician Forge again.".format(sentence, check_python.INSTALL_WORDS)


VERSION_CODE = ("import sys, sysconfig; "
                "print('%d.%d %s' % (sys.version_info[0], sys.version_info[1], sysconfig.get_platform()))")


def environment_problem():
    """Why Musician Forge's own environment must be made again, or None when it can be kept: it is missing or does
    not start, or it was made with another Python than this one (an older install with Python 3.15 kept failing,
    because the environment it had made was kept)."""
    if not os.path.exists(VENV_PY):
        return "there is none yet" if not os.path.isdir(VENV_DIR) else "it is incomplete"
    if run_logged([VENV_PY, "-c", VERSION_CODE]) != 0:
        return "it does not start"
    found = run_logged.output.strip().split()
    if len(found) != 2:
        return "it did not say which Python it is"
    wanted = "%d.%d" % sys.version_info[:2]
    platform_name = sysconfig.get_platform()
    if found[0] != wanted:
        return "it was made with Python {}, and this install uses Python {}".format(found[0], wanted)
    if found[1] != platform_name:
        return "it was made for {}, and this install uses {}".format(found[1], platform_name)
    return None


def step_environment():
    say("Step 1 of 7: setting up Musician Forge's own Python environment.")
    problem = python_problem()
    if problem:
        raise RuntimeError(problem)
    os.makedirs(DATA_DIR, exist_ok=True)
    why = environment_problem()
    if why:
        write_log("The Python environment is made new: {}.".format(why))
        if os.path.isdir(VENV_DIR):
            say("  Making Musician Forge's Python environment again: {}.".format(why))
            shutil.rmtree(VENV_DIR, ignore_errors=True)
            if os.path.isdir(VENV_DIR):
                raise RuntimeError("The old Python environment could not be removed; Musician Forge may still be "
                                   "open. Close it, then run Install or Update Musician Forge again")
        if run_logged([sys.executable, "-m", "venv", VENV_DIR]) != 0:
            raise RuntimeError("Could not create the Python environment")
    say("  Environment ready.")


def step_packages():
    say("Step 2 of 7: installing Python packages. This is the longest step, about 1 to 3 minutes.")
    run_logged([VENV_PY, "-m", "pip", "install", "--upgrade", "pip"])
    req = os.path.join(PROGRAM_DIR, "requirements.txt")
    code = run_logged([VENV_PY, "-m", "pip", "install", "--upgrade", "--only-binary=:all:", "-r", req])
    if code != 0:
        raise RuntimeError("Installing packages failed; see install_log.txt")
    say("  Packages installed.")


ENGINE_IN_USE = ("The old instrument engine is in use, so it could not be replaced. Close Musician Forge, and any "
                 "File Explorer window showing its folder, then run Install or Update Musician Forge again")


read_marker = fluidbuild.read_marker
RENAME_TRIES = 10       # Windows antivirus often holds files it has just seen open for a moment:
RENAME_WAIT = 0.5       # a refused rename is tried again for up to five seconds


def engine_files_present(folder, installed):
    """True when every file the last install unpacked is still there."""
    missing = fluidbuild.missing_files(folder, installed)
    return missing is not None and not missing


def rename(src, dst):
    for attempt in range(RENAME_TRIES):
        try:
            os.rename(src, dst)
            return
        except OSError as exc:
            write_log("Renaming {} to {} failed (attempt {}): {!r}".format(src, dst, attempt + 1, exc))
            if attempt == RENAME_TRIES - 1:
                raise
            time.sleep(RENAME_WAIT)


def unused_name(path):
    """path itself, emptied first if an earlier run left it behind, or path with a number when that is not
    possible (a file in it may still be in use)."""
    if os.path.exists(path):
        shutil.rmtree(path, ignore_errors=True)
    number = 1
    candidate = path
    while os.path.exists(candidate):
        candidate = "{}-{}".format(path, number)
        number += 1
    return candidate


def remove_leftovers():
    """Folders an earlier replacement left behind (fluidsynth-old..., fluidsynth-new...). Only called while
    a complete engine is in place."""
    parent, base = os.path.split(FLUID_DIR)
    if not os.path.isdir(parent):
        return
    for name in os.listdir(parent):
        if name.startswith(base + "-old") or name.startswith(base + "-new"):
            shutil.rmtree(os.path.join(parent, name), ignore_errors=True)


def swap_in(new_dir):
    """Put the unpacked engine in place with two renames. If Windows refuses the first one, nothing changes;
    if it refuses the second, the old engine is put back."""
    old_dir = None
    if os.path.exists(FLUID_DIR):
        old_dir = unused_name(FLUID_DIR + "-old")
        try:
            rename(FLUID_DIR, old_dir)
        except OSError:
            shutil.rmtree(new_dir, ignore_errors=True)
            raise RuntimeError(ENGINE_IN_USE)
    try:
        rename(new_dir, FLUID_DIR)
    except OSError:
        if old_dir is not None:
            try:
                rename(old_dir, FLUID_DIR)
            except OSError as back:
                write_log("Putting the old engine back failed: {!r}".format(back))
        shutil.rmtree(new_dir, ignore_errors=True)
        raise RuntimeError("The new instrument engine could not be put in place. Run Install or Update Musician "
                           "Forge again")


def step_fluidsynth():
    say("Step 3 of 7: installing the FluidSynth instrument engine.")
    installed = read_marker(os.path.join(FLUID_DIR, "installed.json"))
    # The address says both the version and the kind of build (glib or cpp11), so a change of either
    # replaces the engine; so does a missing file.
    if installed.get("url") == FLUIDSYNTH_URL and engine_files_present(FLUID_DIR, installed):
        remove_leftovers()
        say("  FluidSynth {} is already installed.".format(FLUIDSYNTH_VERSION))
        return
    old_version = installed.get("version")
    if installed.get("url") == FLUIDSYNTH_URL:
        say("  Some of FluidSynth's files are missing, so it is installed again.")
    elif old_version:
        why = ""
        if "cpp11" in str(installed.get("url")) and (fluidbuild.parse_version(str(old_version)) or (0, 0))[:2] >= (2, 5):
            why = ": the Windows build of {} crashes as soon as tracks have their own sound outputs".format(old_version)
        say("  Replacing FluidSynth {} with FluidSynth {}{}.".format(old_version, FLUIDSYNTH_VERSION, why))
    # Everything is downloaded, checked and unpacked beside the old engine first; the old one is only touched
    # by the final swap (a cut-off download or a full disk leaves it as it was).
    tmp_zip = os.path.join(tempfile.gettempdir(), "musicianforge_fluidsynth.zip")
    new_dir = None
    try:
        download(FLUIDSYNTH_URL, tmp_zip, expected_size=fluidbuild.INSTALL_SIZE, label="FluidSynth")
        problems = fluidbuild.check_download(tmp_zip)
        if problems:
            write_log("FluidSynth download problems: " + "; ".join(problems))
            raise RuntimeError("The FluidSynth download is not usable ({}), so nothing was changed. Run Install or "
                               "Update Musician Forge again".format(problems[0]))
        new_dir = unused_name(FLUID_DIR + "-new")
        try:
            with zipfile.ZipFile(tmp_zip) as zf:
                zf.extractall(new_dir)
                names = zf.namelist()
            write_log("FluidSynth files: " + ", ".join(names))
            with open(os.path.join(new_dir, "installed.json"), "w", encoding="utf-8") as fh:
                json.dump({"version": FLUIDSYNTH_VERSION, "url": FLUIDSYNTH_URL, "files": names}, fh, indent=1)
        except Exception as exc:  # noqa: BLE001 - a full disk, for example
            write_log("Unpacking FluidSynth failed: {!r}".format(exc))
            raise RuntimeError("FluidSynth could not be unpacked, so nothing was changed. Check that the disk has "
                               "free space, then run Install or Update Musician Forge again")
    except Exception:
        if new_dir is not None:
            shutil.rmtree(new_dir, ignore_errors=True)
        raise
    finally:
        remove_quietly(tmp_zip)
    swap_in(new_dir)
    remove_leftovers()
    say("  FluidSynth {} installed.".format(FLUIDSYNTH_VERSION))


def remove_quietly(path):
    """Remove a downloaded file that is no longer needed. Windows (an antivirus program checking it) can refuse for
    a moment; that is written in the log and the install goes on, instead of stopping with an error."""
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError as exc:
        write_log("Removing {} failed: {!r}".format(path, exc))


def soundfont_ok(path):
    if not os.path.exists(path) or os.path.getsize(path) != SOUNDFONT_SIZE:
        return False
    with open(path, "rb") as fh:
        head = fh.read(12)
    return head[:4] == b"RIFF" and head[8:12] == b"sfbk"


def step_soundfont():
    say("Step 4 of 7: installing the GeneralUser GS instrument sounds, 32 megabytes.")
    os.makedirs(SF_DIR, exist_ok=True)
    dest = os.path.join(SF_DIR, "GeneralUser-GS.sf2")
    if soundfont_ok(dest):
        say("  Instrument sounds are already installed.")
    else:
        download(SOUNDFONT_URL, dest, expected_size=SOUNDFONT_SIZE, label="Instrument sounds")
        if not soundfont_ok(dest):
            raise RuntimeError("The SoundFont download is not a valid SoundFont file")
        say("  Instrument sounds installed.")
    license_path = os.path.join(SF_DIR, "GeneralUser-GS-License.txt")
    if not os.path.exists(license_path):
        try:
            download(SOUNDFONT_LICENSE_URL, license_path, label="SoundFont license")
        except Exception as exc:  # noqa: BLE001 - the license copy is a courtesy
            write_log("License download skipped: {!r}".format(exc))


def guitar_pack_step(number, pack):
    def step():
        megabytes = pack.archive_size // 1_000_000
        say("Step {} of {}: installing the guitar pack {}, a {} megabyte download.".format(
            number, TOTAL_STEPS, pack.name, megabytes))
        if packs.is_installed(pack, SF_DIR):
            say("  {} is already installed.".format(pack.name))
            return
        reported = [0]

        def progress(fraction):
            percent = int(fraction * 100)
            if percent >= reported[0] + 25 and reported[0] < 75:
                reported[0] = percent // 25 * 25
                say("  {} {} percent".format(pack.name, reported[0]))
        try:
            packs.install_pack(pack, SF_DIR, progress=progress, say=lambda text: say("  " + text))
        except Exception as exc:  # noqa: BLE001 - no internet must never stop the install
            write_log("Guitar pack skipped: {!r}".format(exc))
            say("  Skipped: {} could not be downloaded right now. Musician Forge downloads it by itself "
                "the next time it starts with the internet available. A stand-in guitar plays until then."
                .format(pack.name))
    step.__name__ = "step_guitar_pack_{}".format(number - 4)
    return step


def step_selfcheck():
    say("Step 7 of 7: checking that everything works.")
    logs = LOGS_DIR or os.path.join(PROGRAM_DIR, "logs")
    report = os.path.join(logs, "selfcheck_log.txt")
    trace = os.path.join(logs, "selfcheck_trace.txt")
    for stale in (report, trace):       # 8 Oct: an old report was shown as if it were this run's result
        if os.path.exists(stale):
            os.remove(stale)
    code = run_logged([VENV_PY, os.path.join(PROGRAM_DIR, "tools", "selfcheck.py")], timeout=300)
    if os.path.exists(report):
        with open(report, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if line.startswith(("PASS", "FAIL", "WARN")):
                    say("  " + line.strip())
    if code == 0:
        return
    if os.path.exists(report):
        raise RuntimeError("The self check found a problem")
    # No report: the self check did not finish. A large exit code means Windows ended it at once.
    for line in run_logged.output.splitlines():
        if line.startswith("PASS"):
            say("  " + line.strip())
    say("  The self check stopped suddenly (exit code {}). Everything above worked; the program was ended at "
        "the next check. Windows does that when the sound engine does something it must not.".format(
            exit_text(code)))
    tail = trace_tail(trace)
    if tail:
        say("  The last call into the sound engine was: {}.".format(tail[-1]))
    tools_dir = os.path.dirname(os.path.abspath(__file__))
    if tools_dir not in sys.path:
        sys.path.insert(0, tools_dir)
    try:
        import engine_probe
    except ImportError:
        # main, the branch users download, has no sound engine check (it is a development tool): what is known is in
        # the install log, and the development branch's Run Tests finds the rest
        raise RuntimeError("Everything is installed, but the sound engine crashed in the self check. The details are "
                           "in logs, install_log.txt") from None
    say("  Running the sound engine check to find out which calls crash and which do not. About a minute.")
    summary, _failed = engine_probe.run_all(say=lambda text: None, logs_dir=logs, python=VENV_PY)
    for line in probe_lines(os.path.join(logs, "engine_probe.txt")):
        say("  " + line)
    say("  " + summary)
    raise RuntimeError("Everything is installed, but the sound engine crashed in the self check. "
                       "The details are in logs, engine_probe.txt and install_log.txt")


def probe_lines(path):
    """The sound engine check's report in short form: one line for each step, and for a step that crashed
    also the last call it made into the sound engine."""
    lines, last_call = [], None
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read().splitlines()
    except OSError:
        return lines
    for line in text:
        if re.match(r"\s*\d+\. (PASS|PROBLEM) ", line):
            if last_call:
                lines.append("    last call before the stop: " + last_call)
                last_call = None
            lines.append(line.strip())
        elif line.startswith("        > "):
            last_call = line.strip()[2:]
    if last_call:
        lines.append("    last call before the stop: " + last_call)
    return lines


def trace_tail(path, count=3):
    """The last lines of a trail file (see musicianforge.fluid), or an empty list."""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return [line.strip() for line in fh if line.strip()][-count:]
    except OSError:
        return []


def open_log():
    """The install log, in the Musician Forge folder's logs folder; when that folder cannot be written to (a
    read-only folder, or one Windows protects), in %LOCALAPPDATA%\MusicianForge\logs, as Musician Forge's own log."""
    global LOG_PATH, LOGS_DIR
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        return open(LOG_PATH, "w", encoding="utf-8"), False
    except OSError:
        LOGS_DIR = os.path.join(DATA_DIR, "logs")
        LOG_PATH = os.path.join(LOGS_DIR, "install_log.txt")
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        return open(LOG_PATH, "w", encoding="utf-8"), True


def copy_python_setup_log():
    """What the batch files did to find (and perhaps install) Python, into this log."""
    try:
        with open(PYTHON_SETUP_LOG, encoding="utf-8", errors="replace") as fh:
            text = fh.read().strip()
    except OSError:
        return
    if text:
        write_log("Finding Python:\n" + text)


def mark_finished(done):
    """done False: an install is under way, so Start waits for it (the marker is written); True: everything Musician
    Forge needs to start is in place (the marker goes)."""
    try:
        if not done:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(UNFINISHED_MARKER, "w", encoding="utf-8") as fh:
                json.dump({"version": __version__, "python": sys.version.split()[0],
                           "started": datetime.datetime.now().isoformat(timespec="seconds")}, fh)
        elif os.path.exists(UNFINISHED_MARKER):
            os.remove(UNFINISHED_MARKER)
    except OSError as exc:
        write_log("The install marker {} could not be {}: {!r}".format(
            UNFINISHED_MARKER, "removed" if done else "written", exc))


def main():
    global _log_file
    _log_file, moved_log = open_log()
    write_log("Musician Forge installer, Python {}".format(sys.version))
    write_log("Program folder: {}".format(PROGRAM_DIR))
    write_log("Data folder: {}".format(DATA_DIR))
    if moved_log:
        say("The Musician Forge folder cannot be written to, so the install log is in {}.".format(LOG_PATH))
    copy_python_setup_log()
    try:
        moved, blocked = legacy.migrate()       # Melody Forge's folders get Musician Forge's name (8 Oct 2026)
    except Exception as exc:  # noqa: BLE001
        moved, blocked = ["The old folders could not be moved: {}".format(exc)], True
    for sentence in moved:
        say(sentence)
    if blocked:
        say("Problem: the old data folder could not be renamed, so the install stopped before downloading "
            "everything again. Close every Musician Forge or Melody Forge window and run this again.")
        return 1
    mark_finished(False)
    steps = [step_environment, step_packages, step_fluidsynth, step_soundfont,
             guitar_pack_step(5, packs.PACKS[0]), guitar_pack_step(6, packs.PACKS[1]), step_selfcheck]
    for step in steps:
        try:
            step()
            if step is step_soundfont:
                # Everything Musician Forge needs to start is in place (the guitar packs come by themselves later,
                # and the self check only reports), so Start can start it
                mark_finished(True)
        except Exception as exc:  # noqa: BLE001
            say("Problem: {}".format(exc))
            import traceback
            write_log(traceback.format_exc())
            return 1
    say("All steps finished.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
