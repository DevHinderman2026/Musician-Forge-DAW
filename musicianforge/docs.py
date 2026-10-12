"""The help pages Musician Forge can show: the quick start guide, what's new, and credits.

They are the Read Me, Changelog and Credits files in the Musician Forge folder.
Markdown is turned into plain text so screen readers do not read out symbols
such as # and |.
"""

import os
import re

from . import paths

DOCS = {
    "quick_start": ("Quick start guide", "Read Me.txt"),
    "whats_new": ("What's new", "Changelog.md"),
    "credits": ("Credits", "Credits.md"),
}

_LINK = re.compile(r"<(https?://[^>]+)>")
_MARKUP = re.compile(r"\*\*|`")


def markdown_to_text(text):
    """Plain, screen-reader-friendly text from simple Markdown (headings, bold, lists, tables)."""
    lines = []
    headers = None
    for raw in text.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if stripped.startswith("|"):
            cells = [_clean(c) for c in stripped.strip("|").split("|")]
            if all(set(c) <= set("-: ") for c in cells):
                continue  # the line under a table's header row
            if headers is None:
                headers = cells
                continue
            parts = [cells[0]] + ["{}: {}".format(h, c) for h, c in zip(headers[1:], cells[1:])]
            lines.append(". ".join(parts) + ".")
            continue
        headers = None
        if stripped.startswith("#"):
            if lines and lines[-1]:
                lines.append("")
            lines.append(_clean(stripped.lstrip("#").strip()))
            continue
        if stripped.startswith(("- ", "* ")):
            # only the item's own mark goes: before 9 Oct 2026 the first "* " inside the item went too, so an item
            # starting in bold ("**Kit pieces** in Anvil's editor") read "Kit pieces*in Anvil's editor", and an
            # item inside another kept its dash
            lines.append(_clean(stripped[2:]))
            continue
        lines.append(_clean(line))
    result = "\n".join(lines).strip()
    return re.sub(r"\n{3,}", "\n\n", result) + "\n"


def _clean(text):
    return _MARKUP.sub("", _LINK.sub(r"\1", text)).strip()


def read_doc(key):
    """(title, text) of a help page. Missing files give a friendly note instead of an error."""
    title, filename = DOCS[key]
    path = os.path.join(paths.PROGRAM_DIR, filename)
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return title, "{} was not found in the Musician Forge folder. Running Install or Update Musician Forge " \
                      "puts it back.\n".format(filename)
    if filename.endswith(".md"):
        text = markdown_to_text(text)
    return title, text
