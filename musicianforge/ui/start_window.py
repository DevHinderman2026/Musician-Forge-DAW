"""The start screen: choose a project.

Musician Forge opens here instead of opening a project straight away. From here
you can start a new project or open one. Enter on a project in the Recent projects
list opens it (Russell, 10 Oct 2026: "when you actually click enter you can actually
open it"; until then Enter only explained that the list was for show), and Browse
projects lists every project, the recent ones first. Close project (Control+W) in
the project window comes back here.
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


def describe_recent(path):
    """'My Song, in Musician Forge Songs' for the recent projects list."""
    return "{}, in {}".format(projects.project_name(path), projects.location_name(path))


class StartFrame(wx.Frame):
    """New project, Browse projects, Recent projects and Quit.

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

        self.new_button.Bind(wx.EVT_BUTTON, lambda e: self.on_new())
        self.open_button.Bind(wx.EVT_BUTTON, lambda e: self.on_open(self.selected_path()))
        self.quit_button.Bind(wx.EVT_BUTTON, lambda e: self.on_quit())
        self.open_recent_button.Bind(wx.EVT_BUTTON, lambda e: self.open_selected())
        self.remove_button.Bind(wx.EVT_BUTTON, lambda e: self.remove_selected())
        self.help_button.Bind(wx.EVT_BUTTON, lambda e: self.on_help and self.on_help(self.help_button))
        self.recent_list.Bind(wx.EVT_KEY_DOWN, self.on_list_key)
        self.recent_list.Bind(wx.EVT_LISTBOX_DCLICK, lambda e: self.open_selected())
        self.Bind(wx.EVT_CLOSE, self.on_close)
        # Enter on the list is taken here, before Windows can treat it as "press the default button" and swallow it
        # (Russell, 10 Oct 2026: Enter on a recent project did not open it)
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
            self.on_recent(path)
        elif self.on_say is not None:
            self.on_say(NO_RECENT_SAID)

    def on_char_hook(self, event):
        key = event.GetKeyCode()
        if (key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER) and event.GetModifiers() == wx.MOD_NONE
                and wx.Window.FindFocus() is self.recent_list):
            self.open_selected()
            return
        event.Skip()

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
        self.on_quit()
