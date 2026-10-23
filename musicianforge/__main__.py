import sys

MISSING_PART = ("Musician Forge cannot start: a part it needs is missing ({}). The last Install or Update probably "
                "stopped before it finished. Please run \"Install or Update Musician Forge\" again, in the Musician "
                "Forge folder.")


def missing_part(exc):
    """A package Musician Forge needs could not be loaded (an install that stopped partway): say so in a Windows
    message box. "Start Musician Forge" runs it without a console window, so before, nothing at all happened."""
    text = MISSING_PART.format(getattr(exc, "name", None) or exc)
    print(text, file=sys.stderr)       # (nowhere without a console; then the message box says it)
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, text, "Musician Forge", 0x10)     # MB_ICONERROR
    except Exception:  # noqa: BLE001 - not on Windows
        pass
    return 1


def run():
    try:
        from .app import main
    except ImportError as exc:      # numpy, say, before logging could start
        return missing_part(exc)
    try:
        return main()
    except ImportError as exc:      # wxPython is imported once logging has started
        import logging

        logging.getLogger("musicianforge").exception("A part Musician Forge needs is missing")
        return missing_part(exc)


if __name__ == "__main__":
    sys.exit(run())
