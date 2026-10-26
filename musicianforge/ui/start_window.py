"""The start screen: choose a project.

Musician Forge opens here instead of opening a project straight away. From here
you can start a new project or open one. Enter on a project in the Recent projects
list opens it (Russell, 10 Oct 2026: "when you actually click enter you can actually
open it"; until then Enter only explained that the list was for show), and Browse
projects lists every project, the recent ones first. Close project (Control+W) in
the project window comes back here. Escape quits, as the Quit button does (Russell,
25 Oct 2026: "Quit Musician Forge"); a held Escape does nothing more, and a held Enter
or Delete on the Recent projects list acts once (ONCE_KEYS).
"""

import logging

import wx

from .. import __version__, projects
from .common import enable_keeping_focus, note_text, say_after, show_items, silence_name

log = logging.getLogger("musicianforge.ui")

TITLE = "Choose a project - Musician Forge"
NO_RECENT = "No recent projects yet"
RECENT_LABEL = "Recent projects (Enter opens one)"
NO_RECENT_SAID = "There are no recent projects yet. Choose New project or Browse projects."
LIST_HINT = ("Enter opens the project you are on. Delete removes a project from this list (the file itself is kept). "
             "Browse projects lists every project.")
# Enter and Delete on the Recent projects list act once per press, however long they are held: Windows sends a held
# key again about 30 times a second (auto-repeat), so a held Delete removed one project after another from the list,
# and a held Enter on a project whose file is broken opened its message again as soon as it closed (the review, 26 Oct
# 2026). As the project window's NO_REPEAT_KEYS (main_window.is_auto_repeat) and Escape here; arrows and letters
# still repeat.
ONCE_KEYS = (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER, wx.WXK_DELETE, wx.WXK_NUMPAD_DELETE)


def describe_recent(path):
    """'My Song, in Musician Forge Songs' for the recent projects list."""
    return "{}, in {}".format(projects.project_name(path), projects.location_name(path))


def held_down(event):
    """True when Windows sent this key again because it is held down (auto-repeat), as in the project window, where
    a held Space, R, Enter or Escape acts once (main_window.is_auto_repeat). Windows marks every key down after the
    first as a repeat, whichever window gets it, so an Escape still held from the project window is held here too.
    False for a new press, and when wxPython cannot tell (wxKeyEvent.IsAutoRepeat is in wxWidgets 3.1.6 and later)."""
    try:
        return bool(event.IsAutoRepeat())
    except (AttributeError, NotImplementedError):
        return False


def windows_key_down():
    """True while either Windows key is held down. Windows+Escape is Windows' own shortcut (it closes Magnifier,
    which low-vision testers may use), never Musician Forge's, and wxPython may not count a Windows key as a modifier
    (wx.MOD_META), so Windows is asked about both keys (any key can be asked about there). False when they cannot be
    asked about (the stand-in for wxPython has no GetKeyState)."""
    try:
        return bool(wx.GetKeyState(wx.WXK_WINDOWS_LEFT) or wx.GetKeyState(wx.WXK_WINDOWS_RIGHT))
    except Exception:  # noqa: BLE001 - a key that cannot be asked about counts as not held
        return False


class StartFrame(wx.Frame):
    """New project, Browse projects, Recent projects and Quit (Escape quits too).

    The actions are callbacks so this window does not depend on the project window:
    on_new(), on_open(path the Recent projects list is on, or None), on_recent(path), on_quit(),
    on_help(button) and on_say(words) (speaks through the screen reader).
    """

    def __init__(self, settings, on_new, on_open, on_recent, on_quit, on_help=None, on_say=None):
        super().__init__(None, title=TITLE, size=(620, 500))
        self.settings = settings
        self.on_new, self.on_open, self.on_recent, self.on_quit = on_new, on_open, on_recent, on_quit
        self.on_help = on_help
        self.on_say = on_say
        self.paths = []
        self._windows_open = 0       # New project, Browse projects, Open, the Help menu or Quit's question is open
        panel = wx.Panel(self)
        silence_name(panel)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(wx.StaticText(panel, label="Musician Forge {}".format(__version__)), 0, wx.ALL, 8)
        sizer.Add(wx.StaticText(panel, label="Start a new project, open one, or choose a recent project."),
                  0, wx.LEFT | wx.RIGHT, 8)
        row = wx.BoxSizer(wx.HORIZONTAL)
        self.new_button = wx.Button(panel, label="New project")
        self.open_button = wx.Button(panel, label="Browse projects")
        row.Add(self.new_button, 0, wx.ALL, 4)
        row.Add(self.open_button, 0, wx.ALL, 4)
        sizer.Add(row, 0, wx.ALL, 4)
        sizer.Add(wx.StaticText(panel, label=RECENT_LABEL), 0, wx.LEFT | wx.TOP, 8)
        self.recent_list = wx.ListBox(panel, style=wx.LB_SINGLE, size=(-1, 220))
        sizer.Add(self.recent_list, 1, wx.ALL | wx.EXPAND, 8)
        # Enter and Delete on the list, as buttons too (the review, 23 Oct 2026); dimmed while the list is empty
        list_row = wx.BoxSizer(wx.HORIZONTAL)
        self.open_recent_button = wx.Button(panel, label="Open")
        self.remove_button = wx.Button(panel, label="Remove from list")
        list_row.Add(self.open_recent_button, 0, wx.ALL, 4)
        list_row.Add(self.remove_button, 0, wx.ALL, 4)
        sizer.Add(list_row, 0, wx.LEFT | wx.RIGHT, 4)
        sizer.Add(note_text(panel, LIST_HINT, width=580), 0, wx.LEFT | wx.RIGHT, 8)   # the window is 620 wide
        last_row = wx.BoxSizer(wx.HORIZONTAL)
        self.help_button = wx.Button(panel, label="Help menu")
        self.quit_button = wx.Button(panel, label="Quit")
        last_row.Add(self.help_button, 0, wx.ALL, 4)
        last_row.Add(self.quit_button, 0, wx.ALL, 4)
        sizer.Add(last_row, 0, wx.ALL, 4)
        panel.SetSizer(sizer)

        self.new_button.Bind(wx.EVT_BUTTON, lambda e: self.from_here(self.on_new))
        self.open_button.Bind(wx.EVT_BUTTON, lambda e: self.from_here(self.on_open, self.selected_path()))
        self.quit_button.Bind(wx.EVT_BUTTON, lambda e: self.quit())
        self.open_recent_button.Bind(wx.EVT_BUTTON, lambda e: self.open_selected())
        self.remove_button.Bind(wx.EVT_BUTTON, lambda e: self.remove_selected())
        self.help_button.Bind(wx.EVT_BUTTON, lambda e: self.on_help and self.from_here(self.on_help, self.help_button))
        self.recent_list.Bind(wx.EVT_KEY_DOWN, self.on_list_key)
        self.recent_list.Bind(wx.EVT_LISTBOX_DCLICK, lambda e: self.open_selected())
        self.Bind(wx.EVT_CLOSE, self.on_close)
        # Enter on the list is taken here, before Windows can treat it as "press the default button" and swallow it
        # (Russell, 10 Oct 2026: Enter on a recent project did not open it), and so is Escape, which quits
        self.Bind(wx.EVT_CHAR_HOOK, self.on_char_hook)
        self.refresh()

    # ------------------------------------------------------------------
    def refresh(self, select=0):
        """Fill the Recent projects list again, on item `select` (None: stay where it is). show_items moves the
        list only once, so a screen reader reads one item, not the first and then the right one (screen reader
        audit A5, 23 Oct 2026)."""
        if select is None:
            select = max(0, self.recent_list.GetSelection())
        self.paths = self.settings.recent_projects() if self.settings is not None else []
        items = [describe_recent(p) for p in self.paths] or [NO_RECENT]
        show_items(self.recent_list, items, min(select, len(items) - 1))
        # dimmed while one has the focus (Open on a project whose file has gone: the list drops it), Windows would
        # move the focus on by itself, unannounced: it goes to New project first, as after Remove from list
        for button in (self.open_recent_button, self.remove_button):
            enable_keeping_focus(button, bool(self.paths), self.new_button)

    def present(self):
        """Show the start screen and put the keyboard focus somewhere useful."""
        self.refresh()
        self.Show()
        self.Raise()
        if self.paths:
            self.recent_list.SetFocus()
        else:
            self.new_button.SetFocus()

    def selected_path(self):
        index = self.recent_list.GetSelection()
        if 0 <= index < len(self.paths):
            return self.paths[index]
        return None

    def open_selected(self):
        """Enter or a double-click on the Recent projects list: open the project it is on (with none, say so). It
        says "Opening" at once: a project with pitch-corrected recordings takes a moment to open."""
        path = self.selected_path()
        log.info("Start screen: open the recent project %s", path)
        if path is not None:
            if self.on_say is not None:
                self.on_say("Opening {}".format(projects.project_name(path)))
            self.from_here(self.on_recent, path)
        elif self.on_say is not None:
            self.on_say(NO_RECENT_SAID)

    def on_char_hook(self, event):
        key = event.GetKeyCode()
        if (key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER) and event.GetModifiers() == wx.MOD_NONE
                and wx.Window.FindFocus() is self.recent_list):
            if not held_down(event):        # a held Enter opens the project once (ONCE_KEYS); taken all the same
                self.open_selected()
            return
        if (key == wx.WXK_ESCAPE and event.GetModifiers() == wx.MOD_NONE and not windows_key_down()
                and not self._windows_open and self.focus_is_here()):
            # Escape on its own quits, as Quit does (Russell, 25 Oct 2026): not with Shift, Control, Alt or a Windows
            # key (wx.MOD_META, or either Windows key held: Windows+Escape closes Magnifier). And only a new press:
            # a held Escape, or one still held down from the project window (where it stops all sound), comes again
            # as auto-repeat: nothing
            if not held_down(event):
                log.info("Start screen: Escape, so Musician Forge quits")
                self.quit()
            return
        event.Skip()

    def focus_is_here(self):
        """True when the keyboard focus is on this window, not in a window opened from it. (While Windows' own
        message box or Open window has the focus, wxPython sees it nowhere.)"""
        focus = wx.Window.FindFocus()
        try:
            return focus is not None and focus.GetTopLevelParent() is self
        except RuntimeError:  # a window being closed
            return False

    def from_here(self, action, *args):
        """Run New project, Browse projects, Open, the Help menu or Quit. Until the window it opens closes (a dialog,
        a message box, the Help menu, Quit's question about unsaved changes), Escape is that window's: it closes it,
        never Musician Forge. (The Help menu leaves the focus on its button, so the focus alone cannot tell.)"""
        self._windows_open += 1
        try:
            return action(*args)
        finally:
            self._windows_open -= 1

    def quit(self):
        """The Quit button, Escape and Alt+F4: Musician Forge closes (with a project open too, after its usual
        question about unsaved changes)."""
        self.from_here(self.on_quit)

    def remove_selected(self):
        """Delete on the Recent projects list, or the Remove from list button: the project leaves the list (its file
        is kept)."""
        path = self.selected_path()
        if path is None or self.settings is None:
            return
        index = self.recent_list.GetSelection()
        self.settings["recent_files"] = [p for p in self.settings["recent_files"] if p != path]
        self.settings.save()
        if not self.settings.recent_projects() and wx.Window.FindFocus() is self.remove_button:
            self.new_button.SetFocus()     # the button is about to be dimmed: the focus goes somewhere useful first
        self.refresh(select=index)                 # the next project takes its place, read once
        if self.on_say is not None:                # after the list's own reading, not over it
            say_after(self.on_say, "Removed {} from the list".format(projects.project_name(path)))

    def on_list_key(self, event):
        key = event.GetKeyCode()
        if event.GetModifiers() != wx.MOD_NONE:
            event.Skip()            # Alt+Enter, Shift+Delete and the like are not Enter or Delete (0.9.7)
        elif key in ONCE_KEYS and held_down(event):
            return                  # a held Enter or Delete acts once; taken, so it goes no further
        elif key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self.open_selected()
        elif key in (wx.WXK_DELETE, wx.WXK_NUMPAD_DELETE):
            self.remove_selected()
        else:
            event.Skip()

    def on_close(self, event):
        # Alt+F4 here quits Musician Forge, like the Quit button (the project window then closes both)
        if event.CanVeto():
            event.Veto()
        self.quit()
