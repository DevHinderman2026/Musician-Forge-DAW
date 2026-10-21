"""The project window.

Layout (Tab moves between them; F6 and Shift+F6 go from area to area; Control+1 to 5 jump straight there):
1. Tracks: a list of tracks (instrument tracks and audio tracks). M mutes,
   S solos, [ and ] change volume, Shift+[ and Shift+] change pan,
   Control+Up/Down move the track, F2 renames, Delete deletes, Alt+Enter opens
   track settings, Control+X, C, V and D cut, copy, paste and duplicate tracks.
2. Regions: the selected track's regions (recordings on audio tracks), each
   with where it starts, where it ends and how long it is (Control+5).
   Enter opens one, Control+X, C, V and D cut, copy, paste and duplicate,
   Delete deletes, S splits at the playhead, J joins, M mutes, F2 renames.
3. Musical keyboard: play notes with the letter keys. Right after it, the
   Show keyboard controls button reveals every keyboard setting (Control+4).
4. The Menus group: a button for each menu (File, Edit, Region, Track, Transport, Song, Keyboard, Options and
   Help). Every command is in the menus; since 0.9.5 there are no other button groups (Russell, 21 Oct 2026).
5. Status: a read-only summary you can review line by line.

F6 goes to the next area and Shift+F6 to the previous one, round in a circle, in the order they are
on screen: Tracks, Regions, the Musical keyboard, the Keyboard controls, the Menus group, and Status.
An area that is hidden or empty is skipped, and each jump says where it landed.

The track you are on (the one the Musical keyboard plays) and the region you are on end with
", selected" in their lists. In selection mode the word means "marked with Space" instead.

Selection mode (Shift+F8, or the Select check box): Space then selects or
unselects the track or region you are on, and Cut, Copy, Paste, Duplicate,
Delete, Mute and Solo work on everything selected.

Transport keys work everywhere in the window: Space plays or stops, R records,
Enter goes to the start, comma and period move by bars, Shift with comma or
period moves by beats, Escape silences all sound. In lists you choose from and
in boxes you type in, R and Enter do their usual job instead.

Musician Forge opens on the start screen (start_window.py); Close project
(Control+W) returns there.
"""

import logging
import os
import threading
import time
from contextlib import contextmanager

import wx

from .. import (APP_NAME, __version__, arpeggiator, audio, audioimport, audiotracks, keyboard_map, midiimport, paths,
               projects, theory)
from ..outputwatch import OutputWatch
from ..song import Instrument, SongFileError
from ..session import default_song_file_name
from ..timeline import TimelineError, format_number
from .common import (ask_yes_no, ask_yes_no_cancel, fit_to_screen, list_target, show_error, show_info,
                     show_items, silence_name)
from .dialogs import (AudioSettingsDialog, ChangesDialog, EventListDialog, ExportAudioDialog, GoToBarDialog,
                      InstrumentDialog, MidiImportDialog, NewSongDialog, OpenProjectDialog, PreferencesDialog,
                      QuantizeDialog,
                      RecordingDialog, RecordingsDialog, SaveProjectDialog, SectionsDialog, SectionSettingsDialog,
                      TextInputDialog, TextViewDialog, TrackSettingsDialog)
from .effects_dialogs import EffectsDialog
from .automation_dialogs import AutomationDialog
from .music_dialogs import ChordTrackDialog, NewPlayerDialog, PlayerEditorDialog, RegionSettingsDialog
from .start_window import StartFrame

log = logging.getLogger("musicianforge.ui")

PROJECT_WILDCARD = "Musician Forge projects (*.mforge)|*.mforge"
WAV_WILDCARD = "WAV files (*.wav)|*.wav"
EXPORT_WILDCARDS = {"wav": WAV_WILDCARD, "m4a": "M4A files (*.m4a)|*.m4a"}
ZIP_WILDCARD = "Zip files (*.zip)|*.zip"
MIDI_EXTENSIONS = ("mid", "midi", "rmi", "kar")
MIDI_WILDCARD = "MIDI files (*.mid;*.midi;*.rmi;*.kar)|*.mid;*.midi;*.rmi;*.kar"
IMPORT_TITLE = "Import audio or MIDI file"
RECOVERY_DELAY_MS = 3000   # the crash-recovery copy follows the changes this long after the last one


def import_wildcard():
    """The Import window's list: audio and MIDI files together first, then each kind."""
    everything = ";".join("*." + ext for ext in audioimport.EXTENSIONS + MIDI_EXTENSIONS)
    return "Audio and MIDI files ({})|{}|{}|{}".format(everything, everything, MIDI_WILDCARD, audioimport.wildcard())


def is_midi_file(path):
    """A MIDI file, by its ending or, failing that, by how it starts."""
    if os.path.splitext(path)[1].lower().lstrip(".") in MIDI_EXTENSIONS:
        return True
    try:
        with open(path, "rb") as fh:
            start = fh.read(12)
    except OSError:
        return False
    return start[:4] == b"MThd" or (start[:4] == b"RIFF" and start[8:12] == b"RMID")
MICROPHONE_TEST_MS = 3000
NO_REGIONS = "No regions on this track yet. Record, import or paste to make one."
KEYBOARD_SCALE_CHOICES = ["Follow the song's key"] + list(theory.SCALE_NAMES)
OCTAVE_CHOICES = ["{} (the A key plays C {})".format(o, o) for o in keyboard_map.OCTAVES]
ARP_OCTAVE_CHOICES = ["1 octave"] + ["{} octaves".format(n) for n in range(2, arpeggiator.MAX_OCTAVES + 1)]


def _install_keyboard_accessible(panel):
    """Give the keyboard area a clear name and a description of its current layout."""
    if not hasattr(wx, "Accessible"):
        return

    class KeyboardAccessible(wx.Accessible):
        def GetName(self, childId):
            return (wx.ACC_OK, "Musical typing keyboard")

        def GetDescription(self, childId):
            try:
                return (wx.ACC_OK, panel.session.describe_keyboard())
            except Exception:  # noqa: BLE001
                return (wx.ACC_OK, "")

    try:
        panel.SetAccessible(KeyboardAccessible(panel))
    except Exception:  # noqa: BLE001
        log.exception("Could not attach accessibility information to the keyboard area")


def is_typing_control(control):
    """Controls where letters and Enter belong to the control: choice lists and editable text boxes."""
    if isinstance(control, (wx.Choice, wx.ComboBox)):
        return True
    return isinstance(control, wx.TextCtrl) and control.IsEditable()


class KeyboardPanel(wx.Panel):
    """The musical typing area. Letter keys play notes while it has focus."""

    def __init__(self, parent, frame):
        super().__init__(parent, size=(-1, 90), style=wx.BORDER_SIMPLE | wx.TAB_TRAVERSAL)
        self.frame = frame
        self.session = frame.session
        self.SetLabel("Musical typing keyboard")
        self.SetName("Musical typing keyboard")
        self.SetCanFocus(True)
        self._has_focus = False
        self.Bind(wx.EVT_KEY_DOWN, self.on_key_down)
        self.Bind(wx.EVT_KEY_UP, self.on_key_up)
        self.Bind(wx.EVT_SET_FOCUS, self.on_set_focus)
        self.Bind(wx.EVT_KILL_FOCUS, self.on_kill_focus)
        self.Bind(wx.EVT_PAINT, self.on_paint)
        self.Bind(wx.EVT_LEFT_DOWN, lambda e: self.SetFocus())
        _install_keyboard_accessible(self)

    def AcceptsFocus(self):
        return True

    def AcceptsFocusFromKeyboard(self):
        return True

    @staticmethod
    def char_of(event):
        code = event.GetUnicodeKey()
        if code in (wx.WXK_NONE, 0):
            return None
        try:
            return chr(code).lower()
        except (ValueError, OverflowError):
            return None

    def on_key_down(self, event):
        if event.GetModifiers() not in (wx.MOD_NONE, wx.MOD_SHIFT):
            event.Skip()
            return
        char = self.char_of(event)
        handled = False
        if char:
            try:
                handled = self.session.key_down(char, time.perf_counter())
            except Exception:  # noqa: BLE001 - a key press must never crash the program
                log.exception("Key down failed for %r", char)
        if handled:
            if char in "zxcvb":
                self.frame.refresh_status_text()
                self.frame.refresh_controls()  # the keyboard controls show the new octave, velocity or layout
                self.Refresh()
            return
        event.Skip()

    def on_key_up(self, event):
        char = self.char_of(event)
        if char and self.session.key_up(char, time.perf_counter()):
            return
        event.Skip()

    def on_set_focus(self, event):
        self._has_focus = True
        self.Refresh()
        event.Skip()

    def on_kill_focus(self, event):
        self._has_focus = False
        self.session.release_all_keys()
        self.Refresh()
        event.Skip()

    def on_paint(self, event):
        dc = wx.PaintDC(self)
        dc.SetFont(self.GetFont())
        text = "Musical typing keyboard{}".format(" (active)" if self._has_focus else " - press Control+2 to play")
        dc.DrawText(text, 8, 8)
        try:
            dc.DrawText(self.session.describe_keyboard(), 8, 32)
        except Exception:  # noqa: BLE001
            pass


class MainFrame(wx.Frame):
    def __init__(self, session, audio_output=None, speaker=None, test_mode=False):
        super().__init__(None, title=APP_NAME, size=(960, 900))
        fit_to_screen(self)
        self.session = session
        self.audio_output = audio_output
        self.speaker = speaker
        self.test_mode = test_mode
        self.start_frame = None
        self._quitting = False
        self._last_status_bar = ""
        self._last_status_text = ""
        self.buttons = {}
        self.groups = []            # the button groups (since 0.9.5 only Menus): (title, group box, [its buttons])
        self.last_list = "tracks"   # where Cut, Copy, Paste, Duplicate and Delete act: "tracks" or "regions"
        self._menu_handlers = {}    # menu bar item id -> what it does (the Menus group's buttons copy the menus)
        self._build_menus()
        self._build_body()
        self.CreateStatusBar()
        self.SetStatusText("Ready")
        self.Bind(wx.EVT_CHAR_HOOK, self.on_char_hook)
        self.Bind(wx.EVT_CLOSE, self.on_close)
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_timer, self.timer)
        self.autosave_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_autosave, self.autosave_timer)
        # the crash-recovery copy is also brought up to date a few seconds after every change (Russell, 9 Oct 2026:
        # "it should always save"), not only every two minutes
        self.recovery_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_recovery_timer, self.recovery_timer)
        # headphones plugged in or unplugged: follow Windows' default output (outputwatch.py)
        self.output_watch = OutputWatch()
        self._output_wait_logged = None
        if not test_mode:
            self.timer.Start(100)
            self.autosave_timer.Start(120000)   # (the output watch is started by app.py once the sound is open)
        session.listeners.append(self.on_session_change)
        self.refresh_all()
        self.track_list.SetFocus()

    # ------------------------------------------------------------------
    # building the window
    # ------------------------------------------------------------------
    def _build_body(self):
        # The controls scroll up and down when the window is smaller than they are (they need about 1,130 pixels:
        # more than the 900 the window asks for, and more than a laptop screen with Windows' scaling at 125 or
        # 150 percent). wx scrolls the control that gets the keyboard focus into sight by itself.
        panel = wx.ScrolledWindow(self, style=wx.VSCROLL | wx.TAB_TRAVERSAL)
        panel.SetScrollRate(0, 20)
        silence_name(panel)  # otherwise screen readers announce a meaningless "panel"
        self.body = panel
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.body_sizer = sizer
        sizer.Add(wx.StaticText(panel, label="Tracks"), 0, wx.LEFT | wx.TOP, 8)
        self.track_list = wx.ListBox(panel, style=wx.LB_SINGLE, size=(-1, 150))
        sizer.Add(self.track_list, 1, wx.ALL | wx.EXPAND, 8)
        sizer.Add(wx.StaticText(panel, label="Regions"), 0, wx.LEFT, 8)
        self.region_list = wx.ListBox(panel, style=wx.LB_SINGLE, size=(-1, 110))
        sizer.Add(self.region_list, 0, wx.ALL | wx.EXPAND, 8)
        sizer.Add(wx.StaticText(panel, label="Musical keyboard"), 0, wx.LEFT, 8)
        self.keyboard = KeyboardPanel(panel, self)
        sizer.Add(self.keyboard, 0, wx.ALL | wx.EXPAND, 8)
        self._build_keyboard_controls(panel, sizer)
        self._build_buttons(panel, sizer)
        sizer.Add(wx.StaticText(panel, label="Status"), 0, wx.LEFT, 8)
        self.status_text = wx.TextCtrl(panel, size=(-1, 130),
                                       style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_DONTWRAP)
        sizer.Add(self.status_text, 0, wx.ALL | wx.EXPAND, 8)
        panel.SetSizer(sizer)
        self.track_list.Bind(wx.EVT_LISTBOX, self.on_track_selected)
        self.track_list.Bind(wx.EVT_LISTBOX_DCLICK, lambda e: self.safe(self.track_settings))
        self.track_list.Bind(wx.EVT_KEY_DOWN, self.on_track_key)
        self.track_list.Bind(wx.EVT_SET_FOCUS, lambda e: self._list_focused(e, "tracks"))
        self.region_list.Bind(wx.EVT_KEY_DOWN, self.on_region_key)
        self.region_list.Bind(wx.EVT_LISTBOX, lambda e: self.refresh_regions())   # ", selected" moves along
        self.region_list.Bind(wx.EVT_LISTBOX_DCLICK, lambda e: self.safe(self.open_region))
        self.region_list.Bind(wx.EVT_SET_FOCUS, lambda e: self._list_focused(e, "regions"))

    def _build_keyboard_controls(self, panel, sizer):
        """The Show keyboard controls button, then the controls it reveals. Every one is reachable with Tab,
        and each also has a key on the musical keyboard or a shortcut."""
        self.controls_button = wx.Button(panel, label="Show keyboard controls")
        self.controls_button.Bind(wx.EVT_BUTTON, lambda e: self._after(self.safe(self.toggle_keyboard_controls)))
        sizer.Add(self.controls_button, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        box = wx.StaticBox(panel, label="Keyboard controls")
        self.controls_sizer = wx.StaticBoxSizer(box, wx.VERTICAL)
        grid = wx.FlexGridSizer(cols=2, vgap=4, hgap=10)

        def add(label, choices):
            # The label must be created before its control: Windows names a control after the text
            # created just before it, and that name is what NVDA, JAWS and Narrator read.
            grid.Add(wx.StaticText(box, label=label), 0, wx.ALIGN_CENTER_VERTICAL)
            control = wx.Choice(box, choices=list(choices))
            grid.Add(control, 0)
            return control

        self.layout_choice = add("Layout", [])
        self.scale_choice = add("Scale (for the Scale and Chord strips layouts)", KEYBOARD_SCALE_CHOICES)
        self.octave_choice = add("Octave", OCTAVE_CHOICES)
        self.velocity_choice = add("Velocity", [str(v) for v in keyboard_map.VELOCITY_STEPS])
        self.arp_check = wx.CheckBox(box, label="Arpeggiator")
        grid.Add(self.arp_check, 0)
        grid.Add((0, 0))
        self.arp_pattern_choice = add("Arpeggiator pattern", arpeggiator.PATTERNS)
        self.arp_rate_choice = add("Arpeggiator speed", arpeggiator.RATE_NAMES)
        self.arp_octaves_choice = add("Arpeggiator octave range", ARP_OCTAVE_CHOICES)
        # your own chords on the chord strips (Russell, 10 Oct 2026); also Keyboard menu and Control+Shift+J
        self.strips_button = wx.Button(box, label="Customize chord strips...")
        grid.Add(self.strips_button, 0)
        grid.Add((0, 0))
        self.strips_button.Bind(wx.EVT_BUTTON, lambda e: self._after(self.safe(self.chord_strips)))
        self.controls_sizer.Add(grid, 0, wx.ALL, 4)
        sizer.Add(self.controls_sizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)

        s = self.session
        handlers = {
            self.layout_choice: lambda i: s.set_layout(keyboard_map.MODES[i], speak=False)
            if not s.is_drum_track() else None,
            self.scale_choice: lambda i: s.set_keyboard_scale("" if i == 0 else theory.SCALE_NAMES[i - 1]),
            self.octave_choice: lambda i: s.set_octave(keyboard_map.OCTAVES[i]),
            self.velocity_choice: lambda i: s.set_velocity(keyboard_map.VELOCITY_STEPS[i]),
            self.arp_pattern_choice: lambda i: s.set_arpeggiator(pattern=arpeggiator.PATTERNS[i]),
            self.arp_rate_choice: lambda i: s.set_arpeggiator(rate=arpeggiator.RATE_NAMES[i]),
            self.arp_octaves_choice: lambda i: s.set_arpeggiator(octaves=i + 1),
        }
        for choice, handler in handlers.items():
            choice.Bind(wx.EVT_CHOICE, lambda e, c=choice, h=handler: self._on_keyboard_choice(c, h))
        self.arp_check.Bind(wx.EVT_CHECKBOX,
                            lambda e: self._after(self.safe(lambda: s.set_arpeggiator(on=self.arp_check.GetValue()))))
        shown = bool(s.settings["keyboard_controls_shown"]) if s.settings is not None else False
        self._show_keyboard_controls(shown)

    def _on_keyboard_choice(self, choice, handler):
        index = choice.GetSelection()
        if index != wx.NOT_FOUND:
            self.safe(handler, index)
        self._after(None)

    def _show_keyboard_controls(self, shown):
        self.body_sizer.Show(self.controls_sizer, shown, recursive=True)
        self.controls_button.SetLabel("Hide keyboard controls" if shown else "Show keyboard controls")
        self.body.FitInside()          # the scrolling area grows or shrinks with the keyboard controls
        self.body.Layout()

    def keyboard_controls_shown(self):
        return self.layout_choice.IsShown()

    def toggle_keyboard_controls(self):
        shown = not self.keyboard_controls_shown()
        self._show_keyboard_controls(shown)
        if self.session.settings is not None:
            self.session.settings["keyboard_controls_shown"] = shown
            self.session.settings.save()
        self.session.announce("Keyboard controls shown. Tab to reach them." if shown else "Keyboard controls hidden")

    def go_to_keyboard_controls(self):
        """Control+4: show the keyboard controls if needed and move to the first one."""
        if not self.keyboard_controls_shown():
            self._show_keyboard_controls(True)
            if self.session.settings is not None:
                self.session.settings["keyboard_controls_shown"] = True
                self.session.settings.save()
        self.refresh_controls()
        self.layout_choice.SetFocus()

    def _sync_keyboard_controls(self):
        """Keep the keyboard controls in step with the keys (Z, X, C, V, B) and the selected track."""
        s = self.session
        drums = s.is_drum_track()
        items = ["Drums (this track is a drum kit)"] if drums else [keyboard_map.MODE_NAMES[m]
                                                                   for m in keyboard_map.MODES]
        if self.layout_choice.GetItems() != items:
            self.layout_choice.Set(items)
        found = self.keyboard_setting_indexes()           # the same as the Keyboard menu's check marks
        arp = s.arp
        for choice, key in ((self.layout_choice, "layout"), (self.scale_choice, "scale"),
                            (self.octave_choice, "octave"), (self.velocity_choice, "velocity"),
                            (self.arp_pattern_choice, "arp_pattern"), (self.arp_rate_choice, "arp_rate"),
                            (self.arp_octaves_choice, "arp_octaves")):
            index = found[key] if found[key] is not None else 0
            if choice.GetSelection() != index:
                choice.SetSelection(index)
        if self.arp_check.GetValue() != bool(arp["on"]):
            self.arp_check.SetValue(bool(arp["on"]))

    def _build_buttons(self, panel, sizer):
        """The Menus group: a button for each menu of the menu bar, so Tab reaches every command.

        Until 0.9.5 the window also had a group of buttons for each menu (Transport, Track, Edit, Region, Song, File
        and Settings), each doing what an item of its menu does. Russell, 21 Oct 2026: "move all of the song controls,
        file controls, whatever into their respective menus to reduce clutter", so the menus hold every command, the
        same way everywhere, and this group's buttons open them (Russell's rule, 10 Oct 2026: every feature can be
        reached with Tab, a key is extra; Alt opens the menu bar too)."""
        box, row = self._group(panel, sizer, "Menus")
        for title in self.MENU_BUTTONS:
            label = "{} menu".format(title)
            self._button(box, row, label, lambda t=title, k=label: self.show_bar_menu(t, self.buttons[k]))
        help_button = self._button(box, row, "Help menu", lambda: self.show_help_menu(help_button))

    # -- help ----------------------------------------------------------------
    def help_items(self):
        """What the Help menu button offers (the Help menu in the menu bar has the same pages)."""
        return [("Keyboard shortcuts (F1)", self.show_shortcuts),
                ("Musical keyboard layouts (Shift+F1)", self.show_layouts),
                ("Quick start guide", lambda: self.show_doc("quick_start")),
                ("What's new", lambda: self.show_doc("whats_new")),
                ("Credits", lambda: self.show_doc("credits")),
                ("About Musician Forge", self.about)]

    def show_help_menu(self, button):
        """Open the help menu under a button. Up and Down arrows choose, Enter opens, Escape closes."""
        menu = wx.Menu()
        actions = {}
        for label, handler in self.help_items():
            actions[menu.Append(wx.ID_ANY, label).GetId()] = handler
        chosen = self.popup_menu(menu, button, actions)
        menu.Destroy()
        if chosen is not None:
            self.safe(actions[chosen])

    MENU_BUTTONS = ("File", "Edit", "Region", "Track", "Transport", "Song", "Keyboard", "Options")

    def show_bar_menu(self, title, button):
        """A button in the Menus group: that menu bar menu, opened under the button, with the same items, shortcuts,
        check marks and dimmed items, and each item does what it does in the menu bar (Russell, 10 Oct 2026: the
        menu bar is reached with Alt, never with Tab, so every menu is a button too)."""
        self.refresh_menus()
        bar = self.GetMenuBar()
        titles = [bar.GetMenuLabelText(i).replace("&", "") for i in range(bar.GetMenuCount())]
        actions = {}
        menu = self._copy_menu(bar.GetMenu(titles.index(title)), actions)
        chosen = self.popup_menu(menu, button, actions)
        menu.Destroy()
        if chosen is not None:
            self.safe(actions[chosen])

    def _copy_menu(self, source, actions):
        menu = wx.Menu()
        for item in source.GetMenuItems():
            if item.IsSeparator():
                menu.AppendSeparator()
                continue
            submenu = item.GetSubMenu()
            if submenu is not None:
                menu.AppendSubMenu(self._copy_menu(submenu, actions), item.GetItemLabel())
                continue
            handler = self._menu_handlers.get(item.GetId())
            kind = wx.ITEM_CHECK if item.IsCheckable() else wx.ITEM_NORMAL
            copy = menu.Append(wx.ID_ANY, item.GetItemLabel(), "", kind)
            if kind == wx.ITEM_CHECK:
                copy.Check(item.IsChecked())
            copy.Enable(item.IsEnabled() and handler is not None)
            if handler is not None:
                actions[copy.GetId()] = handler
        return menu

    def popup_menu(self, menu, button, actions):
        """Show a menu under a button; returns the chosen item's id, or None (tests replace this)."""
        chosen = button.GetPopupMenuSelectionFromUser(menu, (0, button.GetSize().height))
        return chosen if chosen in actions else None

    def show_doc(self, key):
        from ..docs import read_doc

        title, text = read_doc(key)
        with TextViewDialog(self.visible_parent(), title, text) as dlg:
            self.show_modal(dlg)

    def visible_parent(self):
        """The window to own a dialog: this one, or the start screen while this one is hidden."""
        if not self.IsShown() and self.start_frame is not None and self.start_frame.IsShown():
            return self.start_frame
        return self

    def _group(self, panel, sizer, title):
        box = wx.StaticBox(panel, label=title)
        box_sizer = wx.StaticBoxSizer(box, wx.VERTICAL)
        row = wx.WrapSizer(wx.HORIZONTAL)
        box_sizer.Add(row, 0, wx.ALL | wx.EXPAND, 2)
        sizer.Add(box_sizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)
        self.groups.append((title, box, []))
        return box, row

    def _group_controls(self, box):
        for _title, group_box, controls in self.groups:
            if group_box is box:
                return controls
        return []

    def _button(self, box, row, label, handler):
        # buttons live inside their group box, so screen readers report the group
        button = wx.Button(box, label=label)
        button.Bind(wx.EVT_BUTTON, lambda e, h=handler: self._after(self.safe(h)))
        row.Add(button, 0, wx.ALL, 3)
        self.buttons[label] = button
        self._group_controls(box).append(button)
        return button

    # -- F6 and Shift+F6: from area to area ------------------------------------
    def jump_areas(self):
        """Every area F6 goes through, in the order they are on screen:
        [(name, the control focus lands on or None when the area is hidden or empty, the words said,
          the controls that belong to the area)]."""
        s = self.session
        tid = s.selected_track_id
        areas = []
        tracks = len(s.song.tracks)
        areas.append(("Tracks", self.track_list if tracks else None,
                      "Tracks, {}".format(s._count_words(tracks, "track")), [self.track_list]))
        regions = len(s.regions_of(tid)) if tid is not None else 0
        track = s.song.track_by_id(tid) if tid is not None else None
        noun = "recording" if track is not None and track.is_audio else "region"
        areas.append(("Regions", self.region_list if regions else None,
                      "Regions of {}, {}".format(track.name if track else "no track", s._count_words(regions, noun)),
                      [self.region_list]))
        areas.append(("Musical keyboard", self.keyboard, "Musical keyboard: the letter keys play notes",
                      [self.keyboard]))
        settings = [self.layout_choice, self.scale_choice, self.octave_choice, self.velocity_choice, self.arp_check,
                    self.arp_pattern_choice, self.arp_rate_choice, self.arp_octaves_choice]
        if self.keyboard_controls_shown():
            areas.append(("Keyboard controls", self.layout_choice,
                          "Keyboard controls, {} settings".format(len(settings)),
                          [self.controls_button] + settings))
        else:
            areas.append(("Keyboard controls", self.controls_button,
                          "Keyboard controls are hidden. Space shows them.", [self.controls_button] + settings))
        for title, _box, controls in self.groups:
            usable = [c for c in controls if c.IsShown() and c.IsEnabled()]
            buttons = sum(1 for c in usable if not isinstance(c, wx.CheckBox))
            checks = len(usable) - buttons
            words = "{} group, {}".format(title, self.session._count_words(buttons, "button"))
            if checks:
                words += ", {} check box{}".format(checks, "" if checks == 1 else "es")
            areas.append((title + " group", usable[0] if usable else None, words, controls))
        lines = len(self.status_lines())
        areas.append(("Status", self.status_text, "Status, {} lines".format(lines), [self.status_text]))
        return areas

    def jump(self, delta):
        """F6 (delta 1) and Shift+F6 (delta -1): the next or previous area that is shown and not empty,
        round in a circle. Says where it landed (quietly while recording, like other speech)."""
        areas = self.jump_areas()
        focused = self._focused_control()
        here = None
        for index, (_name, _target, _words, members) in enumerate(areas):
            if focused is not None and any(focused is m for m in members):
                here = index
                break
        count = len(areas)
        start = here if here is not None else (-1 if delta > 0 else count)
        for step in range(1, count + 1):
            index = (start + delta * step) % count
            name, target, words, _members = areas[index]
            if target is None:
                continue          # hidden or empty: skipped
            target.SetFocus()
            if target is self.track_list:
                self.last_list = "tracks"
            elif target is self.region_list:
                self.last_list = "regions"
            self.say_area(words)
            return name
        return None

    def say_area(self, words):
        """What F6 says. It waits a moment and joins the queue, so the screen reader first says the control
        that got the focus; nothing is said while recording."""
        if self.session.engine.recording:
            return
        if self.test_mode:
            self.session.announce(words, interrupt=False)
        else:
            wx.CallLater(200, self.session.announce, words, False)

    def _after(self, _result):
        self.refresh_controls()
        self.refresh_status_text()

    def play_button(self):
        if not self.session.engine.playing:
            self.session.toggle_play()

    def _focused_control(self):
        return wx.Window.FindFocus()

    def _item(self, menu, label, handler, accel=None, help_text="", check=False):
        text = label + ("\t" + accel if accel else "")
        kind = wx.ITEM_CHECK if check else wx.ITEM_NORMAL
        item = menu.Append(wx.ID_ANY, text, help_text, kind)
        self.Bind(wx.EVT_MENU, lambda e, h=handler: self.safe(h), item)
        self._menu_handlers[item.GetId()] = handler
        return item

    def _build_menus(self):
        bar = wx.MenuBar()

        m = wx.Menu()
        self._item(m, "&New project...", self.new_song, "Ctrl+N")
        self._item(m, "&Open project...", self.open_song, "Ctrl+O")
        self.recent_menu = wx.Menu()
        m.AppendSubMenu(self.recent_menu, "Open &recent")
        self._item(m, "&Save project", self.save, "Ctrl+S")
        self._item(m, "Save project &as...", self.save_as, "Ctrl+Shift+S")
        self._item(m, "&Close project", self.close_project, "Ctrl+W")
        m.AppendSeparator()
        self._item(m, "&Export audio (WAV or M4A)...", self.export_audio, "Ctrl+E")
        self._item(m, "Export &MIDI file...", self.export_midi, "Ctrl+Shift+E")
        self._item(m, "&Import audio or MIDI file (WAV, MP3, M4A, FLAC, MIDI and more)...", self.import_file,
                   "Ctrl+Shift+I")
        self._item(m, "Import MI&DI file...", self.import_midi_file)
        m.AppendSeparator()
        self._item(m, "Song &title...", self.song_title)
        m.AppendSeparator()
        self._item(m, "E&xit", self.Close, "Alt+F4")
        bar.Append(m, "&File")

        m = wx.Menu()
        self.undo_item = self._item(m, "&Undo", self.session.undo, "Ctrl+Z")
        self.redo_item = self._item(m, "&Redo", self.session.redo, "Ctrl+Y")
        m.AppendSeparator()
        self.select_item = self._item(m, "&Select: Space picks tracks and regions", self.toggle_selecting,
                                      "Shift+F8", check=True)
        self._item(m, "Cu&t (Control+X in the Tracks or Regions list)", lambda: self.edit_action("cut"))
        self._item(m, "&Copy (Control+C in the Tracks or Regions list)", lambda: self.edit_action("copy"))
        self._item(m, "&Paste (Control+V in the Tracks or Regions list)", lambda: self.edit_action("paste"))
        self._item(m, "Dup&licate (Control+D in the Tracks or Regions list)", lambda: self.edit_action("duplicate"))
        self._item(m, "&Delete (Delete in the Tracks or Regions list)", lambda: self.edit_action("delete"))
        m.AppendSeparator()
        self._item(m, "&Event list (every note or recording on the track)...", self.event_list, "Ctrl+L")
        self._item(m, "&Quantize...", self.quantize, "Ctrl+Q")
        bar.Append(m, "&Edit")

        m = wx.Menu()
        self._item(m, "&Open region: its notes, or a rhythm player's editor (Enter in the Regions list)",
                   self.open_region)
        self._item(m, "Region se&ttings: trim and loop... (Alt+Enter in the Regions list)", self.region_settings)
        self._item(m, "Re&forge: a new performance of a rhythm player region (R in the Regions list)",
                   self.reforge_region)
        self._item(m, "&New rhythm player region at the playhead (P in the Regions list)", self.new_player_region)
        self._item(m, "&Move region to a bar...", self.move_region)
        self._item(m, "Nudge region &later (Alt+Right in the Regions list)", lambda: self.nudge_region(1))
        self._item(m, "Nudge region &earlier (Alt+Left in the Regions list)", lambda: self.nudge_region(-1))
        self._item(m, "Region st&art earlier (left bracket in the Regions list)",
                   lambda: self.nudge_region_edge("start", -1))
        self._item(m, "Reg&ion start later (right bracket in the Regions list)",
                   lambda: self.nudge_region_edge("start", 1))
        self._item(m, "Region en&d earlier, shorter (Shift+left bracket in the Regions list)",
                   lambda: self.nudge_region_edge("end", -1))
        self._item(m, "Region end later, lon&ger (Shift+right bracket in the Regions list)",
                   lambda: self.nudge_region_edge("end", 1))
        self._item(m, "C&hange the nudge step: bar, quarter, eighth or sixteenth note (N in the Regions list)",
                   lambda: self.session.cycle_nudge_step(1))
        self._item(m, "&Split region at the playhead (S in the Regions list)", self.split_region)
        self._item(m, "&Join selected regions (J in the Regions list)", self.join_regions)
        self._item(m, "M&ute or unmute region (M in the Regions list)", self.mute_regions)
        self._item(m, "&Rename region... (F2 in the Regions list)", self.rename_region)
        bar.Append(m, "&Region")

        m = wx.Menu()
        self._item(m, "&New track...", self.new_track, "Ctrl+T")
        self._item(m, "New &audio track (record a microphone)", self.new_audio_track, "Ctrl+U")
        self._item(m, "New r&hythm player: drums, bass, keys, synth or guitar...", self.new_player, "Ctrl+Shift+R")
        self._item(m, "Track &settings (region settings in the Regions list)...", self.settings_for_focus,
                   "Alt+Enter")
        self._item(m, "Change &instrument...", self.change_instrument, "Ctrl+I")
        self._item(m, "&Effects (reverb, EQ, compressor and more)...", self.track_effects, "Ctrl+F")
        self._item(m, "Au&tomation: volume, pan and effects changing over time...", self.track_automation,
                   "Ctrl+Shift+U")
        self.write_item = self._item(m, "Write automation while the song &plays", self.session.toggle_automation_write,
                                     "Ctrl+Shift+W", check=True)
        self._item(m, "&Rename track...", self.rename_track, "F2")
        self._item(m, "&Mute or unmute (M in the track list)", self.toggle_mute)
        self._item(m, "S&olo on or off (S in the track list)", self.toggle_solo)
        self._item(m, "Move track &up", lambda: self.move_track(-1), "Ctrl+Shift+Up")
        self._item(m, "Move track do&wn", lambda: self.move_track(1), "Ctrl+Shift+Down")
        self._item(m, "&Delete track (Delete in the track list)", self.delete_track)
        bar.Append(m, "&Track")

        m = wx.Menu()
        self._item(m, "&Play or stop (Space)", self.session.toggle_play)
        self._item(m, "&Record or stop (R)", self.session.toggle_record)
        self._item(m, "Go to &start (Enter)", self.session.go_to_start)
        self._item(m, "Previous bar (comma)", lambda: self.session.move_bars(-1))
        self._item(m, "Next bar (period)", lambda: self.session.move_bars(1))
        self._item(m, "Previous beat (Shift+comma)", lambda: self.session.move_beats(-1))
        self._item(m, "Next beat (Shift+period)", lambda: self.session.move_beats(1))
        self._item(m, "Previous section (Control+comma)", self.session.previous_section)
        self._item(m, "Next section (Control+period)", self.session.next_section)
        self.all_sections_item = self._item(m, "&All sections (off: the current section loops)",
                                            self.session.toggle_all_sections, "Ctrl+Shift+L", check=True)
        self._item(m, "&Go to bar...", self.go_to_bar, "Ctrl+G")
        m.AppendSeparator()
        self.metronome_item = self._item(m, "&Metronome", self.toggle_metronome, "Ctrl+K", check=True)
        self._item(m, "&Count-in: off, 1 bar or 2 bars", self.cycle_count_in, "Ctrl+Shift+C")
        m.AppendSeparator()
        self._item(m, "Spea&k position and song details", self.speak_position, "Ctrl+P")
        self._item(m, "Stop all sound (Escape)", self.stop_all_sound)
        bar.Append(m, "Tra&nsport")

        m = wx.Menu()
        self._item(m, "&Tempo changes...", lambda: self.changes("tempo"), "Ctrl+Shift+T")
        self._item(m, "Time &signature changes...", lambda: self.changes("time"), "Ctrl+Shift+M")
        self._item(m, "&Key changes...", lambda: self.changes("key"), "Ctrl+Shift+K")
        m.AppendSeparator()
        self._item(m, "C&hord track...", self.chord_track, "Ctrl+Shift+H")
        m.AppendSeparator()
        self._item(m, "S&ections...", self.sections, "Ctrl+Shift+A")
        self._item(m, "&Add a section after this one", lambda: self.session.add_section(), "Ctrl+Shift+N")
        self._item(m, "Section setti&ngs...", self.section_settings)
        bar.Append(m, "&Song")

        m = wx.Menu()
        self._item(m, "Go to the musical &keyboard", lambda: self.keyboard.SetFocus(), "Ctrl+2")
        self._item(m, "Go to the keyboard &controls", self.go_to_keyboard_controls, "Ctrl+4")
        self._item(m, "Go to the &tracks", lambda: self.track_list.SetFocus(), "Ctrl+1")
        self._item(m, "Go to the &regions", lambda: self.region_list.SetFocus(), "Ctrl+5")
        self._item(m, "Go to the &status", lambda: self.status_text.SetFocus(), "Ctrl+3")
        self._item(m, "Go to the ne&xt area: tracks, regions, keyboard, the Menus group, status (F6)",
                   lambda: self.jump(1))
        self._item(m, "Go to the pre&vious area (Shift+F6)", lambda: self.jump(-1))
        m.AppendSeparator()
        self._item(m, "Switch &layout: piano, scale or chord strips (B)", self.session.toggle_layout)
        self._item(m, "&Arpeggiator on or off", self.session.toggle_arpeggiator, "Ctrl+Shift+P")
        self._item(m, "Octave down (Z)", lambda: self.session.key_down("z"))
        self._item(m, "Octave up (X)", lambda: self.session.key_down("x"))
        self._item(m, "Velocity down (C)", lambda: self.session.key_down("c"))
        self._item(m, "Velocity up (V)", lambda: self.session.key_down("v"))
        self._item(m, "Speak keyboard settings and c&hords", self.speak_keyboard, "Ctrl+J")
        self._item(m, "Customize chord stri&ps...", self.chord_strips, "Ctrl+Shift+J")
        m.AppendSeparator()
        self._build_keyboard_submenus(m)
        bar.Append(m, "&Keyboard")

        m = wx.Menu()
        self._item(m, "&Audio settings...", self.audio_settings, "Ctrl+Shift+O")
        # straight to the measurement (Russell, 10 Oct 2026: "I can't find the button where you can actually measure
        # the latency"; it is far down Audio settings). Tab reaches both through the Options menu button.
        self._item(m, "&Measure the recording delay...", lambda: self.audio_settings(focus="measure"), "Ctrl+Shift+D")
        self._item(m, "&Preferences...", self.preferences)
        bar.Append(m, "&Options")

        m = wx.Menu()
        self._item(m, "&Keyboard shortcuts", self.show_shortcuts, "F1")
        self._item(m, "Musical keyboard &layouts", self.show_layouts, "Shift+F1")
        self._item(m, "&Quick start guide", lambda: self.show_doc("quick_start"))
        self._item(m, "&What's new", lambda: self.show_doc("whats_new"))
        self._item(m, "&Credits", lambda: self.show_doc("credits"))
        self._item(m, "&About Musician Forge", self.about)
        bar.Append(m, "&Help")

        self.SetMenuBar(bar)

    # the keyboard controls' settings, one submenu each, the current one checked (Russell, 21 Oct 2026: every command in
    # its menu; he chose to keep the Keyboard controls area too, for trying settings quickly while playing)
    KEYBOARD_SUBMENUS = ("layout", "scale", "octave", "velocity", "arp_pattern", "arp_rate", "arp_octaves")

    def _build_keyboard_submenus(self, m):
        s = self.session
        names = {"layout": [keyboard_map.MODE_NAMES[mode] for mode in keyboard_map.MODES],
                 "scale": KEYBOARD_SCALE_CHOICES, "octave": OCTAVE_CHOICES,
                 "velocity": ["Velocity {}".format(v) for v in keyboard_map.VELOCITY_STEPS],
                 "arp_pattern": arpeggiator.PATTERNS,
                 "arp_rate": arpeggiator.RATE_NAMES, "arp_octaves": ARP_OCTAVE_CHOICES}
        titles = {"layout": "Layo&ut", "scale": "Scal&e (for the Scale and Chord strips layouts)",
                  "octave": "&Octave", "velocity": "Veloc&ity", "arp_pattern": "Arpeggiator patter&n",
                  "arp_rate": "Arpeggiator spee&d", "arp_octaves": "Arpeggiator octave ran&ge"}
        self.keyboard_menu_items = {}
        for key in self.KEYBOARD_SUBMENUS:
            sub = wx.Menu()
            items = []
            for index, name in enumerate(names[key]):
                items.append(self._item(sub, name, lambda k=key, i=index: self.choose_keyboard_setting(k, i),
                                        check=True))
            m.AppendSubMenu(sub, titles[key])
            self.keyboard_menu_items[key] = items

    def choose_keyboard_setting(self, key, index):
        """A Keyboard menu submenu item: the same as choosing it in the keyboard controls, and it is said (a menu
        closes without reading the new value)."""
        s = self.session
        if key == "layout":
            s.set_layout(keyboard_map.MODES[index])          # on a drum kit it says the drum layout stays
        elif key == "scale":
            s.set_keyboard_scale("" if index == 0 else theory.SCALE_NAMES[index - 1], speak=True)
        elif key == "octave":
            s.set_octave(keyboard_map.OCTAVES[index], speak=True)
        elif key == "velocity":
            s.set_velocity(keyboard_map.VELOCITY_STEPS[index], speak=True)
        else:                       # the arpeggiator: says the new setting, and when it is off, how to turn it on
            what, value, words = {"arp_pattern": ("pattern", arpeggiator.PATTERNS[index], "pattern"),
                                  "arp_rate": ("rate", arpeggiator.RATE_NAMES[index], "speed"),
                                  "arp_octaves": ("octaves", index + 1, "octave range")}[key]
            s.set_arpeggiator(**{what: value})
            name = ARP_OCTAVE_CHOICES[index] if key == "arp_octaves" else value
            s.announce("Arpeggiator {}: {}{}".format(words, name, "" if s.arp["on"] else
                                                     ". The arpeggiator is off; Control+Shift+P turns it on"))
        self.refresh_controls()

    def keyboard_setting_indexes(self):
        """{setting: the index of its current choice} (None for the layout on a drum kit, which has only drums)."""
        s = self.session
        steps = keyboard_map.VELOCITY_STEPS
        arp = s.arp
        return {"layout": None if s.is_drum_track() else
                (keyboard_map.MODES.index(s.typing.mode) if s.typing.mode in keyboard_map.MODES else 0),
                "scale": KEYBOARD_SCALE_CHOICES.index(s.typing.scale) if s.typing.scale in theory.SCALE_NAMES else 0,
                "octave": keyboard_map.OCTAVES.index(s.typing.octave) if s.typing.octave in keyboard_map.OCTAVES else 0,
                "velocity": min(range(len(steps)), key=lambda i: abs(steps[i] - s.typing.velocity)),
                "arp_pattern": arpeggiator.PATTERNS.index(arp["pattern"]),
                "arp_rate": arpeggiator.RATE_NAMES.index(arp["rate"]),
                "arp_octaves": int(arp["octaves"]) - 1}

    # ------------------------------------------------------------------
    # safety net: no action can crash the program
    # ------------------------------------------------------------------
    def safe(self, func, *args):
        parent = self if self.IsShown() else None  # a message owned by a hidden window could go unseen
        try:
            result = func(*args)
            self.refresh_menus()
            return result if result is not None else True
        except (ValueError, TimelineError, SongFileError) as exc:
            self.session.announce(str(exc))
            show_error(parent, str(exc))
        except Exception as exc:  # noqa: BLE001
            log.exception("Action failed: %s", getattr(func, "__name__", func))
            show_error(parent, "Something went wrong: {}\n\nThe details were saved in the logs folder "
                               "(musicianforge.log).".format(exc))
        return False

    def show_modal(self, dialog):
        """All dialogs open through here (tests replace this)."""
        return dialog.ShowModal()

    def ask_values(self, dialog, get_values):
        """Show a dialog until what was typed in it makes sense: get_values() raises ValueError in words, and the
        dialog comes back with everything still in it (before the review of 9 Oct 2026, some closed and everything
        had to be typed again). Returns the values, or None if it was cancelled."""
        while self.show_modal(dialog) == wx.ID_OK:
            try:
                return get_values()
            except ValueError as exc:
                show_error(dialog, str(exc))
        return None

    # ------------------------------------------------------------------
    # keys
    # ------------------------------------------------------------------
    def on_char_hook(self, event):
        key = event.GetKeyCode()
        mods = event.GetModifiers()
        s = self.session
        action = None
        focused = self._focused_control()
        if key == wx.WXK_F6 and mods in (wx.MOD_NONE, wx.MOD_SHIFT):
            self.safe(self.jump, -1 if mods == wx.MOD_SHIFT else 1)   # F6 and Shift+F6: the next or previous area
            return
        if key in (wx.WXK_SPACE, wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER) and isinstance(
                focused, (wx.Button, wx.CheckBox, wx.ToggleButton)):
            event.Skip()  # Space and Enter press the focused button, as everywhere in Windows
            return
        if mods == wx.MOD_NONE and key in (ord("R"), wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER) and is_typing_control(focused):
            event.Skip()  # in a list you choose from (R jumps to "Random") or a box you type in
            return
        if mods == wx.MOD_NONE and key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER) and focused is self.region_list:
            event.Skip()  # Enter opens the region
            return
        if mods == wx.MOD_NONE and key == ord("R") and focused is self.region_list and self._on_player_region():
            self.safe(self.reforge_region)  # R on a rhythm player region reforges it (elsewhere R records)
            self.refresh_controls()
            return
        if mods == wx.MOD_NONE and key == wx.WXK_SPACE and s.selecting and focused in (self.track_list,
                                                                                       self.region_list):
            self.safe(self.toggle_item_selected, focused)  # selection mode: Space picks the item
            self.refresh_controls()
            return
        if mods == wx.MOD_NONE:
            action = {
                wx.WXK_SPACE: s.toggle_play,
                ord("R"): s.toggle_record,
                wx.WXK_RETURN: s.go_to_start,
                wx.WXK_NUMPAD_ENTER: s.go_to_start,
                ord(","): lambda: s.move_bars(-1),
                ord("."): lambda: s.move_bars(1),
                wx.WXK_ESCAPE: self.stop_all_sound,
            }.get(key)
        elif mods == wx.MOD_SHIFT:
            action = {ord(","): lambda: s.move_beats(-1), ord("."): lambda: s.move_beats(1),
                      ord("<"): lambda: s.move_beats(-1), ord(">"): lambda: s.move_beats(1)}.get(key)
        elif mods == wx.MOD_CONTROL:
            action = {ord(","): s.previous_section, ord("."): s.next_section}.get(key)
        if action is None:
            event.Skip()
            return
        self.safe(action)
        self.refresh_controls()
        self.refresh_status_text()

    def on_track_key(self, event):
        key = event.GetKeyCode()
        mods = event.GetModifiers()
        tid = self.session.selected_track_id
        s = self.session
        target = list_target(self.track_list, key) if mods in (wx.MOD_NONE, wx.MOD_SHIFT) else None
        if target is not None:
            # Musician Forge moves the list itself, so ", selected" is on the track before the screen reader
            # reads it (and it is read once)
            if 0 <= target < len(s.song.tracks) and target != self.track_list.GetSelection():
                s.select_track(s.song.tracks[target].id)
            return
        action = None
        if tid is not None:
            if mods == wx.MOD_NONE:
                action = {ord("M"): self.toggle_mute, ord("S"): self.toggle_solo,
                          ord("["): lambda: s.change_volume(tid, -5), ord("]"): lambda: s.change_volume(tid, 5),
                          wx.WXK_DELETE: self.delete_track, wx.WXK_NUMPAD_DELETE: self.delete_track}.get(key)
            elif mods == wx.MOD_SHIFT:
                action = {ord("["): lambda: s.change_pan(tid, -10), ord("]"): lambda: s.change_pan(tid, 10),
                          ord("{"): lambda: s.change_pan(tid, -10), ord("}"): lambda: s.change_pan(tid, 10)}.get(key)
            elif mods == wx.MOD_CONTROL:
                action = {wx.WXK_UP: lambda: self.move_track(-1), wx.WXK_DOWN: lambda: self.move_track(1),
                          ord("X"): lambda: self.track_action("cut"), ord("C"): lambda: self.track_action("copy"),
                          ord("V"): lambda: self.track_action("paste"),
                          ord("D"): lambda: self.track_action("duplicate"),
                          ord("A"): lambda: self.select_all("tracks")}.get(key)
        if action is None:
            event.Skip()
            return
        self.safe(action)
        self.refresh_controls()

    def on_region_key(self, event):
        key = event.GetKeyCode()
        mods = event.GetModifiers()
        target = list_target(self.region_list, key) if mods in (wx.MOD_NONE, wx.MOD_SHIFT) else None
        if target is not None:
            if target != self.region_list.GetSelection():         # as in the Tracks list: read once, with its words
                self.refresh_regions(select=target)
            return
        action = self.nudge_key_action(key, mods)
        if action is not None:
            pass
        elif mods == wx.MOD_NONE:
            action = {wx.WXK_RETURN: self.open_region, wx.WXK_NUMPAD_ENTER: self.open_region,
                      ord("P"): self.new_player_region,     # not Insert: NVDA keeps Insert for itself (10 Oct 2026)
                      wx.WXK_DELETE: lambda: self.region_action("delete"),
                      wx.WXK_NUMPAD_DELETE: lambda: self.region_action("delete"),
                      ord("S"): self.split_region, ord("J"): self.join_regions, ord("M"): self.mute_regions,
                      wx.WXK_F2: self.rename_region}.get(key)
        elif mods == wx.MOD_CONTROL:
            action = {ord("X"): lambda: self.region_action("cut"), ord("C"): lambda: self.region_action("copy"),
                      ord("V"): lambda: self.region_action("paste"),
                      ord("D"): lambda: self.region_action("duplicate"),
                      ord("A"): lambda: self.select_all("regions"), ord("R"): self.reforge_region}.get(key)
        elif mods == wx.MOD_ALT:
            action = {wx.WXK_RETURN: self.region_settings, wx.WXK_NUMPAD_ENTER: self.region_settings}.get(key)
        if action is None:
            event.Skip()
            return
        self.safe(action)
        self.refresh_controls()

    def nudge_key_action(self, key, mods):
        """The Regions list's nudge keys (0.9.4), or None: Alt+Left and Alt+Right move the region by the nudge step;
        [ and ] move its start; Shift+[ and Shift+] (and Alt+Shift+Left and Alt+Shift+Right) move its end, which is
        how a rhythm player's region gets longer; N and Shift+N change the nudge step."""
        left, right = (wx.WXK_LEFT, wx.WXK_NUMPAD_LEFT), (wx.WXK_RIGHT, wx.WXK_NUMPAD_RIGHT)
        if mods == wx.MOD_ALT and key in left + right:
            return lambda: self.nudge_region(1 if key in right else -1)
        if mods == wx.MOD_ALT | wx.MOD_SHIFT and key in left + right:
            return lambda: self.nudge_region_edge("end", 1 if key in right else -1)
        if mods == wx.MOD_NONE and key in (ord("["), ord("]")):
            return lambda: self.nudge_region_edge("start", 1 if key == ord("]") else -1)
        if mods == wx.MOD_SHIFT and key in (ord("["), ord("]"), ord("{"), ord("}")):
            return lambda: self.nudge_region_edge("end", 1 if key in (ord("]"), ord("}")) else -1)
        if key == ord("N") and mods in (wx.MOD_NONE, wx.MOD_SHIFT):
            return lambda: self.session.cycle_nudge_step(-1 if mods == wx.MOD_SHIFT else 1)
        return None

    def nudge_region(self, direction):
        """Move the region you are on (or the selected regions) one nudge step later or earlier."""
        s = self.session
        with self._spoken_refusal():
            tid, index = self._need_region()
            self.select_region_in_list(s.nudge_regions(tid, s.regions_for_action(current=index), direction))

    def nudge_region_edge(self, edge, direction):
        """Move the start or the end of the region you are on one nudge step."""
        with self._spoken_refusal():
            tid, index = self._need_region()
            self.select_region_in_list(self.session.nudge_region_edge(tid, index, edge, direction))

    @contextmanager
    def _spoken_refusal(self):
        """A nudge key that cannot do anything (something in the way, the start of the song) says why and lets you
        press the next key at once: a message box to close after every key would be too much."""
        try:
            yield
        except (ValueError, TimelineError) as exc:
            self.session.announce(str(exc))

    def _list_focused(self, event, which):
        self.last_list = which
        event.Skip()

    def on_track_selected(self, event):
        index = self.track_list.GetSelection()
        if 0 <= index < len(self.session.song.tracks):
            self.session.select_track(self.session.song.tracks[index].id)

    # ------------------------------------------------------------------
    # keeping the window up to date
    # ------------------------------------------------------------------
    def on_session_change(self, what):
        if what == "song":
            self.recovery_copy_soon()
        if what in ("song", "selection", "presets"):
            self.refresh_tracks()
            self.refresh_regions()
            self.refresh_title()
            self.refresh_status_text()
        elif what == "title":
            self.refresh_title()
        elif what in ("transport", "keyboard"):
            self.refresh_status_text()
        self.refresh_menus()
        self.refresh_controls()

    def refresh_all(self):
        self.refresh_tracks()
        self.refresh_regions()
        self.refresh_title()
        self.refresh_status_text()
        self.refresh_menus()
        self.refresh_recent()
        self.refresh_controls()

    def refresh_controls(self):
        """Keep the keyboard controls in step with the song (they can change from the keyboard too); the menus' check
        marks follow in refresh_menus."""
        self._sync_keyboard_controls()

    def refresh_title(self):
        title = self.session.title_text()
        if self.GetTitle() != title:
            self.SetTitle(title)

    def refresh_tracks(self):
        """The Tracks list. The track you are on ends with ", selected" (in selection mode, every track marked
        with Space does instead), on screen and for screen readers alike."""
        s = self.session
        tracks = s.song.tracks
        items = [t.describe(i + 1) + (", selected" if s.is_selected_track(t.id) else "") for i, t in enumerate(tracks)]
        index = self.session.song.index_of(self.session.selected_track_id)
        show_items(self.track_list, items, index if index >= 0 else None)

    def refresh_regions(self, select=None):
        """The selected track's regions, keeping your place in the list (or moving to `select`). The region you
        are on ends with ", selected" (in selection mode, every region marked with Space does instead)."""
        s = self.session
        tid = s.selected_track_id
        count = len(s.regions_of(tid)) if tid is not None else 0
        here = self.region_list.GetSelection() if select is None else select
        here = min(max(here, 0), count - 1) if count else None
        items = [s.describe_region_item(tid, i, current=here) for i in range(count)] or [NO_REGIONS]
        show_items(self.region_list, items, here if here is not None else 0)

    def current_region(self):
        """The region you are on in the Regions list, or None."""
        tid = self.session.selected_track_id
        index = self.region_list.GetSelection()
        if tid is None or not 0 <= index < len(self.session.regions_of(tid)):
            return None
        return index

    def select_region_in_list(self, index):
        self.refresh_regions(select=index)

    def refresh_menus(self):
        h = self.session.history
        self.undo_item.SetItemLabel("&Undo {}\tCtrl+Z".format(h.undo_label()) if h.can_undo() else "&Undo\tCtrl+Z")
        self.redo_item.SetItemLabel("&Redo {}\tCtrl+Y".format(h.redo_label()) if h.can_redo() else "&Redo\tCtrl+Y")
        self.undo_item.Enable(h.can_undo())
        self.redo_item.Enable(h.can_redo())
        self.metronome_item.Check(self.session.engine.metronome_on)
        self.all_sections_item.Check(self.session.all_sections)
        self.select_item.Check(self.session.selecting)
        self.write_item.Check(self.session.automation_write)
        indexes = self.keyboard_setting_indexes()
        for key, items in self.keyboard_menu_items.items():
            for index, item in enumerate(items):
                item.Check(index == indexes[key])
                if key == "layout":
                    item.Enable(indexes[key] is not None)     # a drum kit always uses the drum layout

    def status_lines(self):
        s = self.session
        track = s.selected_track
        bars = s.engine.count_in_bars
        index = s.current_section_index()
        lines = [
            s.describe_status(),
            "Section {} of {}: {}. {}.".format(index + 1, len(s.song.sections), s.describe_section(index),
                                             s.describe_play_mode()),
            "Selected track: {}".format(s.describe_track(track.id) if track else "none"),
            "Chord: {}".format(s.chord_at_playhead()),
            self.describe_selection(),
            "Musical keyboard: {}".format(s.describe_keyboard()),
            "Write automation {}.".format("on: changes while playing are written" if s.automation_write else "off"),
            "Metronome {}. Count-in {}.".format("on" if s.engine.metronome_on else "off",
                                                "off" if bars == 0 else "{} bar{}".format(bars, "s" if bars > 1 else "")),
            "Audio: {}.".format(self.audio_output.description if self.audio_output else "off"),
            "Microphone: {}.".format(s.describe_microphone()),
            "Announcements: {}.".format(self.speaker.describe() if self.speaker else "off"),
        ]
        return lines

    def refresh_status_text(self):
        text = "\n".join(self.status_lines())
        if text != self._last_status_text:
            self._last_status_text = text
            self.status_text.SetValue(text)
        self.keyboard.Refresh()

    def on_timer(self, event):
        try:
            self.follow_output()
        except Exception:  # noqa: BLE001
            log.exception("Following Windows' output failed")
        try:
            self.session.poll()
            s = self.session
            tl = s.song.timeline
            tick = s.position_tick()
            bar = tl.tick_to_bar(tick)
            state = "Recording" if s.engine.recording else ("Playing" if s.engine.playing else "Stopped")
            if s.engine.in_count_in():
                state = "Count-in"
            line = "{} | {} | {} BPM | {} | {}".format(
                state, s.describe_position(tick), format_number(tl.tempo_at_tick(tick)),
                tl.time_signature_at_bar(bar).label(), tl.key_at_bar(bar).name())
            if line != self._last_status_bar:
                self._last_status_bar = line
                self.SetStatusText(line)
        except Exception:  # noqa: BLE001
            log.exception("Timer update failed")

    def follow_output(self):
        """Headphones plugged in or unplugged (Russell, 9 Oct 2026): when Windows' default output has changed and
        Audio settings say "Windows default", the sound moves to the new default. An output chosen by name stays
        chosen. While recording (or while the microphone is open) it waits, quietly, until that is over."""
        new = self.output_watch.changed()
        if new is None or self.audio_output is None:
            return
        settings = self.session.settings["audio"] if self.session.settings is not None else {}
        if settings.get("device_name"):
            self.output_watch.acknowledge(new)
            log.info("Windows' output changed to %s; Musician Forge stays on %s, chosen in Audio settings",
                     new, settings["device_name"])
            return
        mic = self.session.audio_input
        if self.session.engine.recording or (mic is not None and mic.is_open):
            if self._output_wait_logged != new:         # speech stays quiet while recording
                self._output_wait_logged = new
                log.info("Windows' output changed to %s; the sound moves there when the microphone is closed", new)
            return
        self._output_wait_logged = None
        self.output_watch.acknowledge(new)
        try:
            description = self.audio_output.reopen(settings.get("host_api", "Windows WASAPI"), "",
                                                   settings.get("block_frames", 256))
        except RuntimeError as exc:
            self.session.audio_is_live = False
            log.error("Windows' output changed to %s, and no output could be opened: %s", new, exc)
            self.session.announce("Windows' sound output changed to {}, but Musician Forge could not play there. "
                                  "Try Options, Audio settings.".format(new))
            return
        self.session.audio_is_live = True
        log.info("Windows' output changed to %s; the sound now plays there (%s)", new, description)
        self.session.announce("Sound now on {}".format(new))
        self.refresh_status_text()

    def on_autosave(self, event):
        """Every two minutes: keep the crash-recovery copy up to date, even while the song plays."""
        self.keep_recovery_copy()

    def recovery_copy_soon(self):
        """After a change: keep the crash-recovery copy up to date a few seconds later (once the changes stop)."""
        if not self.test_mode:
            self.recovery_timer.Start(RECOVERY_DELAY_MS, wx.TIMER_ONE_SHOT)

    def on_recovery_timer(self, event):
        if self.session.engine.playing:
            # not while the song plays or records (writing the copy takes the program's attention for a moment);
            # once it stops, or at the latest at the two-minute save
            self.recovery_copy_soon()
            return
        self.keep_recovery_copy()

    def keep_recovery_copy(self):
        try:
            if self.session.autosave():
                log.info("Autosaved for crash recovery")
        except Exception:  # noqa: BLE001
            log.exception("Autosave failed")

    # ------------------------------------------------------------------
    # file actions
    # ------------------------------------------------------------------
    def confirm_discard(self):
        """True if it is OK to replace or close the current project (saving it first if asked). A take being
        recorded stops first: it goes into the project and counts as a change, so it can be saved."""
        if self.session.engine.recording:
            self.session.stop(speak=False)
        if not self.session.modified:
            return True
        answer = ask_yes_no_cancel(self, "Save changes to {} first?".format(self.session.song.title))
        log.info("Asked to save changes to %s first: %s", self.session.song.title, answer)
        if answer == "cancel":
            return False
        if answer == "yes":
            saved = self.save()   # a project never saved asks for its name first; Cancel there keeps it open
            if not saved:
                self.session.announce("Not saved, so the project stays open")
            return saved
        return True

    def new_song(self, parent=None):
        """New project: asks for the title, tempo, time signature and key. Returns True if one was made."""
        if parent is None and not self.confirm_discard():
            return False
        with NewSongDialog(parent or self, self.session.settings) as dlg:
            while True:
                if self.show_modal(dlg) != wx.ID_OK:
                    return False
                try:
                    values = dlg.get_values()
                    break
                except ValueError as exc:
                    show_error(dlg, str(exc))
        self.session.new_song_with(**values)
        self.session.announce("New project {}, {} BPM".format(values["title"], format_number(values["bpm"])))
        return True

    def open_song(self, path=None, parent=None, preselect=None):
        """Open project: from a path, or from the Open project list (preselect: the project to have chosen
        there already). Returns True if one opened."""
        if parent is None and not self.confirm_discard():
            return False
        if path is None:
            path = self.choose_project(parent, preselect)
            if not path:
                return False
        if not os.path.isfile(path):
            self.refresh_recent()
            raise ValueError("{} is no longer there. It may have been moved or deleted.".format(
                os.path.basename(path)))
        try:
            self.session.open(path)
        except SongFileError as exc:
            backup = path + ".bak"
            if os.path.exists(backup) and ask_yes_no(
                    parent or self, "{}\n\nA backup of the previous save exists. Open the backup instead?".format(exc)):
                self.session.open(path, backup=True)
                self.refresh_title()
            else:
                raise
        self.refresh_recent()
        return True

    def choose_project(self, parent=None, preselect=None):
        """The Open project window: the recent projects first, then every other project in Musician Forge
        Songs, newest first, or Browse. Returns the chosen project's path, or None.

        preselect: the project to have chosen already. From the project window, the most recent project that
        is not the one already open."""
        found = projects.find_projects(paths.ensure_dir(paths.default_songs_dir()))
        recent = self.session.settings.recent_projects() if self.session.settings is not None else []
        if preselect is None and parent is None and self.session.path:
            current = os.path.normcase(os.path.abspath(self.session.path))
            preselect = next((p for p in recent if os.path.normcase(os.path.abspath(p)) != current), None)
        with OpenProjectDialog(parent or self, found, browse=self.browse_for_project, recent=recent,
                               preselect=preselect) as dlg:
            if self.show_modal(dlg) != wx.ID_OK:
                return None
            return dlg.get_path()

    def browse_for_project(self, parent=None):
        """Windows' Open window, for a project in any folder."""
        with wx.FileDialog(parent or self, "Open project file", defaultDir=paths.default_songs_dir(),
                           wildcard=PROJECT_WILDCARD, style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as dlg:
            if self.show_modal(dlg) != wx.ID_OK:
                return None
            return dlg.GetPath()

    # -- the start screen and Close project --------------------------------
    def show_start_screen(self):
        """Hide the project window and show the start screen (New project, Browse projects, Recent projects)."""
        if self.start_frame is None:
            self.start_frame = StartFrame(
                self.session.settings,
                on_new=lambda: self._from_start(self.new_song),
                on_open=lambda chosen=None: self._from_start(self.open_song, preselect=chosen),
                on_recent=lambda path: self._from_start(self.open_song, path),
                on_quit=self.quit_app,
                on_help=lambda button: self.show_help_menu(button),
                on_say=self.session.announce)
        self.Hide()
        if self.test_mode:
            self.start_frame.refresh()  # automated tests never put windows on the screen
        else:
            self.start_frame.present()

    def _from_start(self, action, *args, **options):
        """Run New, Open or a recent project from the start screen; show the project if it worked."""
        parent = self.start_frame
        try:
            done = action(*args, parent=parent, **options)
        except (ValueError, SongFileError) as exc:
            show_error(parent, str(exc))
            parent.refresh()
            return False
        except Exception as exc:  # noqa: BLE001
            log.exception("Could not start the project")
            show_error(parent, "Something went wrong: {}\n\nThe details were saved in the logs folder "
                               "(musicianforge.log).".format(exc))
            return False
        if done:
            self.show_project()
        return bool(done)

    def show_project(self):
        """Show the project window (after a project was made or opened, or recovered)."""
        if self.start_frame is not None:
            self.start_frame.Hide()
        self.refresh_all()
        if not self.test_mode:
            self.Show()
            self.Raise()
            self.body.FitInside()      # the button rows wrap at the window's real width only once it is shown
        self.track_list.SetFocus()

    def close_project(self):
        """Close project (Control+W): offer to save, then go back to the start screen."""
        self.session.stop(speak=False)  # first, so a take being recorded is kept and counts as a change
        if not self.confirm_discard():
            return False
        self.session.new_song()  # an empty project waits behind the start screen
        self.session.mark_clean_exit()
        log.info("Closed the project")
        self.show_start_screen()
        return True

    def quit_app(self):
        """Quit from the start screen (or Exit): close both windows."""
        if self._quitting:
            return
        if self.IsShown() and not self.confirm_discard():
            return
        self._quitting = True
        self.session.modified = False
        self.Close(True)

    def speech_window(self):
        """The window that is showing (the start screen or the project), for screen reader notifications."""
        if self.start_frame is not None and self.start_frame.IsShown():
            return self.start_frame.GetHandle()
        return self.GetHandle()

    def save(self):
        if self.session.path:
            self.session.save()
            self.refresh_recent()
            return True
        return self.save_as()

    # Files always start somewhere predictable, never "wherever a file went last time", so nothing is
    # ever saved somewhere unexpected without anyone seeing the screen.
    def project_parent_folder(self):
        """Where Save As offers to put the project's folder: next to the project's own folder,
        or Musician Forge Songs."""
        path = self.session.path
        if path and os.path.isdir(os.path.dirname(path)):
            folder = os.path.dirname(os.path.abspath(path))
            return os.path.dirname(folder) if projects.has_own_folder(path) else folder
        return paths.ensure_dir(paths.default_songs_dir())

    def export_folder(self):
        """The project's Exports folder (Musician Forge Songs, Exports before the project is saved)."""
        return paths.ensure_dir(projects.exports_folder(self.session.path))

    def import_folder(self):
        if self.session.path and os.path.isdir(os.path.dirname(self.session.path)):
            return os.path.dirname(os.path.abspath(self.session.path))
        return paths.ensure_dir(paths.default_songs_dir())

    def choose_folder(self, current, owner=None):
        """Windows' folder window, for Save As (tests replace show_modal)."""
        with wx.DirDialog(owner or self, "Choose the folder for the project", defaultPath=current) as dlg:
            if self.show_modal(dlg) != wx.ID_OK:
                return None
            return dlg.GetPath()

    def save_as(self):
        """Save project as: a name, and a folder of its own (in Musician Forge Songs unless you choose)."""
        if self.session.path:
            name = projects.project_name(self.session.path)
        else:
            name = projects.safe_name(self.session.song.title)
        with SaveProjectDialog(self, name, self.project_parent_folder(), choose_folder=self.choose_folder) as dlg:
            while True:
                if self.show_modal(dlg) != wx.ID_OK:
                    return False
                try:
                    path = dlg.get_path()
                except ValueError as exc:
                    show_error(dlg, str(exc))
                    continue
                same = self.session.path and os.path.normcase(os.path.abspath(path)) == os.path.normcase(
                    os.path.abspath(self.session.path))
                if os.path.exists(path) and not same and not ask_yes_no(
                        dlg, "There is already a project called {} in {}. Replace it?".format(
                            projects.project_name(path), projects.location_name(path))):
                    continue
                break
        self.session.save(path)
        self.refresh_recent()
        return True

    def refresh_recent(self):
        for item in list(self.recent_menu.GetMenuItems()):
            self.recent_menu.Delete(item)
        recent = self.session.settings.recent_projects() if self.session.settings is not None else []
        if not recent:
            item = self.recent_menu.Append(wx.ID_ANY, "No recent projects")
            item.Enable(False)
            return
        for i, path in enumerate(recent, 1):
            label = "&{} {}".format(i, os.path.basename(path)) if i < 10 else os.path.basename(path)
            item = self.recent_menu.Append(wx.ID_ANY, label, path)
            self.Bind(wx.EVT_MENU, lambda e, p=path: self.safe(self.open_song, p), item)
            self._menu_handlers[item.GetId()] = lambda p=path: self.open_song(p)

    def song_title(self):
        with TextInputDialog(self, "Song title", "Song title", self.session.song.title) as dlg:
            if self.show_modal(dlg) == wx.ID_OK:
                self.session.rename_song(dlg.get_value())

    def export_midi(self):
        if not any(self.session.all_sounding_notes().values()):   # played notes and rhythm players
            raise ValueError("The song has no notes to export yet. MIDI files hold notes; "
                             "recordings on audio tracks go into WAV exports.")
        # One MIDI file for the whole song (Russell, 10 Oct 2026), and it says when it is done.
        name = os.path.splitext(default_song_file_name(self.session.song))[0] + ".mid"
        with wx.FileDialog(self, "Export MIDI file", defaultDir=self.export_folder(), defaultFile=name,
                           wildcard="MIDI files (*.mid)|*.mid", style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as dlg:
            if self.show_modal(dlg) != wx.ID_OK:
                return
            path = dlg.GetPath()
        path, _size = self.session.export_midi(path)
        show_info(self, self.session.midi_export_words(path), "Export finished")

    def export_audio(self):
        """Control+E: the whole song as a WAV or M4A file, or (WAV) every track as its own file in a zip."""
        if not self.session.song.has_content():
            raise ValueError("The song has nothing to export yet")
        with ExportAudioDialog(self, self.session) as dlg:
            values = self.ask_values(dlg, dlg.get_values)   # choosing tracks but none: said, and the window stays
            if values is None:
                return
            fmt, rate, bits, tail = values
            what = dlg.what_to_export()
            track_ids = dlg.tracks_to_export()
        if what != "song":
            self.export_each_track(rate, bits, tail, track_ids)
            return
        name = os.path.splitext(default_song_file_name(self.session.song))[0] + "." + fmt
        with wx.FileDialog(self, "Export {} file".format(fmt.upper()), defaultDir=self.export_folder(),
                           defaultFile=name, wildcard=EXPORT_WILDCARDS[fmt],
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as fd:
            if self.show_modal(fd) != wx.ID_OK:
                return
            path = fd.GetPath()
        result = self.run_export(path, rate, bits, tail, fmt)
        if result is None:
            return
        if result["cancelled"]:
            self.session.announce("Export cancelled")
            return
        message = self.session.describe_export(result)
        self.session.announce(message)
        show_info(self, message, "Export finished")

    export_wav = export_audio  # its name before M4A arrived

    def export_each_track(self, rate, bits, tail, track_ids):
        """Tracks on their own (Russell, 10 Oct 2026): one chosen track is one WAV file (the vocals alone, say);
        several are WAV files in one zip file. Every file has the song's length, so they line up."""
        song = self.session.song
        base = os.path.splitext(default_song_file_name(song))[0]
        if len(track_ids) == 1:
            track_name = projects.safe_name(song.track_by_id(track_ids[0]).name) or "Track"
            name, wildcard, title = base + " - " + track_name + ".wav", WAV_WILDCARD, "Export the track"
        else:
            name, wildcard, title = base + " tracks.zip", ZIP_WILDCARD, "Export the tracks (a zip file)"
        with wx.FileDialog(self, title, defaultDir=self.export_folder(), defaultFile=name, wildcard=wildcard,
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as fd:
            if self.show_modal(fd) != wx.ID_OK:
                return
            path = fd.GetPath()
        ending = ".wav" if len(track_ids) == 1 else ".zip"
        if not path.lower().endswith(ending):
            path += ending
        result = self.run_export(path, rate, bits, tail, "tracks", track_ids)
        if result is None:
            return
        if result["cancelled"]:
            self.session.announce("Export cancelled")
            return
        message = self.session.describe_track_export(result)
        self.session.announce(message)
        show_info(self, message, "Export finished")

    def make_progress(self, path):
        """The progress window for an audio export (tests replace this)."""
        return wx.ProgressDialog("Exporting audio", "Rendering {}".format(os.path.basename(path)), maximum=100,
                                 parent=self, style=wx.PD_APP_MODAL | wx.PD_CAN_ABORT | wx.PD_ELAPSED_TIME)

    def run_export(self, path, rate, bits, tail=True, fmt="wav", track_ids=None):
        state = {"fraction": 0.0, "cancel": False, "result": None, "error": None}

        def work():
            try:
                if fmt == "tracks":
                    state["result"] = self.session.export_tracks(
                        path, rate, bits, progress=lambda f: state.__setitem__("fraction", f),
                        cancelled=lambda: state["cancel"], tail=tail, track_ids=track_ids)
                else:
                    state["result"] = self.session.export_audio(
                        path, fmt, rate, bits, progress=lambda f: state.__setitem__("fraction", f),
                        cancelled=lambda: state["cancel"], tail=tail)
            except ValueError as exc:  # explained to the user, no need for a traceback
                state["error"] = exc
            except Exception as exc:  # noqa: BLE001
                log.exception("Audio export failed")
                state["error"] = exc

        worker = threading.Thread(target=work, name="wav-export", daemon=True)
        progress = self.make_progress(path)
        worker.start()
        try:
            while worker.is_alive():
                keep_going, _skip = progress.Update(min(99, int(state["fraction"] * 100)))
                if not keep_going:
                    state["cancel"] = True
                wx.MilliSleep(100)
        finally:
            progress.Destroy()
        if state["error"] is not None:
            raise state["error"]
        return state["result"]

    # ------------------------------------------------------------------
    # tracks
    # ------------------------------------------------------------------
    def _need_track(self):
        track = self.session.selected_track
        if track is None:
            raise ValueError("There is no track selected. Press Control+T to add one.")
        return track

    def new_track(self):
        with InstrumentDialog(self, self.session) as dlg:
            if self.show_modal(dlg) != wx.ID_OK or dlg.get_preset() is None:
                return
            preset = dlg.get_preset()
        preset = self.session._real_preset(preset)
        self.session.add_track(preset.name, Instrument(preset.bank, preset.program, preset.name))
        self.track_list.SetFocus()

    def new_audio_track(self):
        self.session.add_audio_track()
        self.track_list.SetFocus()

    def choose_import_file(self, owner=None, kind="any"):
        """The Import window (Windows' own Open window): kind "any" lists audio and MIDI files, "audio" only
        audio, "midi" only MIDI. Returns the path or None (tests replace show_modal)."""
        title, wildcard = {"any": (IMPORT_TITLE, import_wildcard()),
                           "audio": ("Import audio file", audioimport.wildcard()),
                           "midi": ("Import MIDI file", MIDI_WILDCARD + "|All files (*.*)|*.*")}[kind]
        with wx.FileDialog(owner or self, title, defaultDir=self.import_folder(), wildcard=wildcard,
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as dlg:
            if self.show_modal(dlg) != wx.ID_OK:
                return None
            return dlg.GetPath()

    def import_file(self):
        """Control+Shift+I: an audio file onto the selected audio track (or a new one named after it), or a MIDI
        file as new tracks."""
        path = self.choose_import_file()
        if not path:
            return
        if is_midi_file(path):
            self.import_midi_file(path)
        else:
            self.import_audio_path(path)
            self.track_list.SetFocus()

    import_wav = import_file  # its name before 0.9.1

    def import_audio_path(self, path, track_id=None, owner=None):
        """Read an audio file and make Musician Forge's copy (showing progress for long ones), then put it on the
        track. Returns the new recording's place, or None if it was cancelled."""
        self.session.check_import_target(track_id)         # before the slow part, not after
        prepared = self.prepare_import_with_progress(path, owner)
        if prepared is None:
            self.session.announce("Import cancelled")
            return None
        try:
            if track_id is None:
                return self.session.import_audio_file(path, prepared=prepared)
            return self.session.import_audio(track_id, path, prepared=prepared)
        except BaseException:
            self.session.discard_prepared(prepared)          # not placed after all: no copy is left behind
            raise

    def import_into_track(self, owner, track_id):
        """The Recordings list's Import: an audio file onto that track."""
        path = self.choose_import_file(owner, kind="audio")
        if not path:
            return None
        try:
            return self.import_audio_path(path, track_id, owner)
        except ValueError as exc:
            show_error(owner, str(exc))
            return None

    def make_import_progress(self, path, owner=None):
        """The progress window while a long file is read (tests replace this)."""
        return wx.ProgressDialog("Importing audio", "Reading {}".format(os.path.basename(path)), maximum=100,
                                 parent=owner or self, style=wx.PD_APP_MODAL | wx.PD_CAN_ABORT | wx.PD_ELAPSED_TIME)

    def prepare_import_with_progress(self, path, owner=None):
        """session.prepare_import (reading, converting to 48 kHz, saving the copy) in the background while a
        progress window shows how far it is and can cancel. Returns the prepared import, or None if cancelled
        (then no copy is left); problems are raised in words."""
        state = {"fraction": 0.0, "cancel": False, "result": None, "error": None}
        self.session.announce("Importing {}".format(os.path.basename(path)))

        def work():
            try:
                state["result"] = self.session.prepare_import(
                    path, progress=lambda f: state.__setitem__("fraction", f), cancelled=lambda: state["cancel"])
            except audioimport.ImportCancelled:
                state["result"] = None
            except ValueError as exc:        # said in words, no need for a traceback
                state["error"] = exc
            except Exception as exc:  # noqa: BLE001
                log.exception("Importing %s failed", path)
                state["error"] = exc

        worker = threading.Thread(target=work, name="audio-import", daemon=True)
        progress = self.make_import_progress(path, owner)
        worker.start()
        try:
            while worker.is_alive():
                keep_going, _skip = progress.Update(min(99, int(state["fraction"] * 100)))
                if not keep_going:
                    state["cancel"] = True
                wx.MilliSleep(50)
        finally:
            progress.Destroy()
        if state["cancel"]:
            if state["result"] is not None:          # it finished just as Cancel was pressed
                self.session.discard_prepared(state["result"])
            return None
        if state["error"] is not None:
            error = state["error"]
            if isinstance(error, ValueError):
                raise error
            raise ValueError("{} could not be imported: {}".format(os.path.basename(path), error)) from error
        return state["result"]

    def import_midi_file(self, path=None):
        """Import MIDI file: its tracks become new tracks; its tempo, time signatures, keys and markers replace the
        project's own when chosen (the default for a project with nothing in it yet)."""
        path = path or self.choose_import_file(kind="midi")
        if not path:
            return
        try:
            contents = midiimport.read_file(path)
        except midiimport.MidiImportError as exc:
            raise ValueError("{} could not be imported: {}.".format(os.path.basename(path), exc)) from None
        if not contents.tracks:
            raise ValueError("{} has no notes to import.".format(os.path.basename(path)))
        summary = midiimport.describe(contents, path)
        if contents.warnings:
            summary += " Note: " + "; ".join(contents.warnings) + "."
        with MidiImportDialog(self, summary, self.session.project_is_empty()) as dlg:
            if self.show_modal(dlg) != wx.ID_OK:
                return
            values = dlg.get_values()
        self.session.import_midi(path, contents, use_timeline=values["use_timeline"])
        self.track_list.SetFocus()

    def track_settings(self):
        track = self._need_track()
        with TrackSettingsDialog(self, self.session, track) as dlg:
            values = self.ask_values(dlg, dlg.get_values)
        if values is None:
            return
        self.session.update_track(track.id, **values)

    def track_effects(self):
        """Control+F: the selected track's effects."""
        track = self._need_track()
        with EffectsDialog(self, self.session, track.id, run_modal=self.show_modal,
                           confirm=lambda m: ask_yes_no(self, m)) as dlg:
            self.show_modal(dlg)
        self.session.end_effect_preview()
        self.refresh_tracks()

    def track_automation(self):
        """Control+Shift+U: the selected track's automation lanes."""
        track = self._need_track()
        with AutomationDialog(self, self.session, track.id, run_modal=self.show_modal,
                              confirm=lambda m: ask_yes_no(self, m)) as dlg:
            self.show_modal(dlg)
        self.refresh_tracks()

    def change_instrument(self):
        track = self._need_track()
        if track.is_audio:
            raise ValueError("{} is an audio track: it plays recordings, so it has no instrument.".format(track.name))
        with InstrumentDialog(self, self.session, track.instrument) as dlg:
            if self.show_modal(dlg) != wx.ID_OK or dlg.get_preset() is None:
                return
            self.session.set_instrument(track.id, dlg.get_preset())

    def rename_track(self):
        track = self._need_track()
        with TextInputDialog(self, "Rename track", "Track name", track.name) as dlg:
            if self.show_modal(dlg) == wx.ID_OK:
                self.session.rename_track(track.id, dlg.get_value())

    def toggle_mute(self):
        """Mute or unmute the current track, or every selected track in selection mode."""
        self._need_track()
        ids = self.session.tracks_for_action()
        if len(ids) == 1:
            self.session.toggle_mute(ids[0])
        else:
            self.session.set_tracks_mute(ids)

    def toggle_solo(self):
        self._need_track()
        ids = self.session.tracks_for_action()
        if len(ids) == 1:
            self.session.toggle_solo(ids[0])
        else:
            self.session.set_tracks_solo(ids)

    def move_track(self, delta):
        self.session.move_track(self._need_track().id, delta)

    def delete_track(self):
        """Delete in the Tracks list, the Delete track button and menu item, and the Edit group's Delete: the tracks
        selected in selection mode, or else the track you are on, after asking. (Until 9 Oct 2026 the Delete key,
        the button and the menu item deleted only the track you were on and ignored the selection.)"""
        s = self.session
        self._need_track()
        ids = s.tracks_for_action()
        if len(ids) > 1:
            if ask_yes_no(self, "Delete {} tracks and everything on them? You can undo this with Control+Z.".format(
                    len(ids))):
                s.delete_tracks(ids)
            return
        track = s.song.track_by_id(ids[0])
        count, what = (len(track.regions), "recording") if track.is_audio else (len(track.notes), "note")
        if ask_yes_no(self, "Delete the track {} and its {} {}{}? You can undo this with Control+Z.".format(
                track.name, count, what, "" if count == 1 else "s")):
            s.delete_tracks([track.id])

    # ------------------------------------------------------------------
    # selection, and cut, copy, paste, duplicate and delete
    # ------------------------------------------------------------------
    def describe_selection(self):
        s = self.session
        if not s.selecting:
            return "Selection off (Shift+F8 turns it on)."
        return "Selection on: {} and {} selected.".format(s._count_words(len(s.selected_tracks), "track"),
                                                          s._count_words(len(s.selected_regions), "region"))

    def toggle_selecting(self):
        self.session.toggle_selecting()
        self.refresh_tracks()
        self.refresh_regions()

    def toggle_item_selected(self, focused):
        s = self.session
        if focused is self.track_list:
            if s.selected_track_id is not None:
                s.toggle_track_selected(s.selected_track_id)
        else:
            index = self.current_region()
            if index is None:
                raise ValueError("This track has no regions yet")
            s.toggle_region_selected(index)
            self.select_region_in_list(index)

    def select_all(self, what):
        if not self.session.selecting:
            self.session.toggle_selecting()
        self.session.select_all(what)
        self.refresh_regions()

    def edit_action(self, what):
        """The Edit buttons and menu: act on the tracks or regions, whichever list you were in last."""
        if self.last_list == "regions":
            self.region_action(what)
        else:
            self.track_action(what)

    def track_action(self, what):
        s = self.session
        ids = s.tracks_for_action()
        if what == "copy":
            s.copy_tracks(ids)
        elif what == "cut":
            s.cut_tracks(ids)
        elif what == "paste":
            s.paste_tracks()
        elif what == "duplicate":
            s.duplicate_tracks(ids)
        elif what == "delete":
            self.delete_track()
        self.track_list.SetFocus()

    def _need_region_track(self):
        tid = self.session.selected_track_id
        if tid is None:
            raise ValueError("There is no track selected. Press Control+T to add one.")
        return tid

    def region_action(self, what):
        s = self.session
        tid = self._need_region_track()
        indices = s.regions_for_action(current=self.current_region())
        index = None
        if what == "copy":
            s.copy_regions(tid, indices)
            index = self.current_region()
        elif what == "cut":
            s.cut_regions(tid, indices)
        elif what == "paste":
            index = s.paste_regions(tid)
        elif what == "duplicate":
            index = s.duplicate_regions(tid, indices)
        elif what == "delete":
            if not self.confirm_delete_regions(tid, indices):
                self.region_list.SetFocus()
                return
            s.delete_regions(tid, indices)
        self.select_region_in_list(index)
        self.region_list.SetFocus()

    def confirm_delete_regions(self, tid, indices):
        """Ask before deleting regions, every time (Russell, 9 Oct 2026: "Always ask"): one region by its name,
        several by how many. Nothing to delete, or recording, says why instead of asking."""
        s = self.session
        s._need_regions(tid, indices)
        if len(indices) == 1:
            index = indices[0]          # as the Regions list reads it: "2. Piano region"
            message = "Delete region {}, {}? You can undo this with Control+Z.".format(index + 1,
                                                                                     s.region_name(tid, index))
        else:
            message = "Delete {} regions? You can undo this with Control+Z.".format(len(indices))
        return ask_yes_no(self, message)

    def _need_region(self):
        tid = self._need_region_track()
        if self.session.engine.recording:
            # A take adds notes and regions under an open window, which then changes the wrong one (review of
            # 9 Oct 2026; Russell chose to say so and open nothing).
            raise ValueError("Stop recording before opening or changing a region")
        index = self.current_region()
        if index is None:
            raise ValueError("There is no region here. Choose one in the Regions list (Control+5) first.")
        return tid, index

    def open_region(self):
        """Enter in the Regions list: a region's notes (the event list), or a recording's settings."""
        s = self.session
        tid, index = self._need_region()
        track = s.song.track_by_id(tid)
        if s.is_player_region(tid, index):
            self.edit_player(tid, index)
        elif track.is_audio:
            with RecordingDialog(self, s, tid, index) as dlg:
                values = self.ask_values(dlg, dlg.get_values)
            if values is None:
                return
            self.select_region_in_list(s.update_region(tid, index, **values))
        else:
            start, end = s.region_span(tid, index)
            with EventListDialog(self, s, tid, span=(start, end), span_name=s.region_name(tid, index)) as dlg:
                self.show_modal(dlg)
            self.select_region_in_list(index)
        self.region_list.SetFocus()

    def edit_player(self, tid, index):
        """The rhythm player editor for a region (Enter on it in the Regions list). With several rhythm player regions
        selected, every change in it is made to all of them (Russell, 10 Oct 2026)."""
        s = self.session
        track = s.song.track_by_id(tid)
        chosen = [i for i in s.regions_for_action(index) if s.is_player_region(tid, i)] if s.selecting else []
        starts = {track.note_regions[i].start for i in chosen} | {track.note_regions[index].start}
        if len(starts) > 1:
            s.player_group = (tid, starts)
            s.announce("Editing {} rhythm player regions together".format(len(starts)))
        try:
            with PlayerEditorDialog(self, s, tid, index, run_modal=self.show_modal,
                                    confirm=lambda m: ask_yes_no(self, m), together=len(starts)) as dlg:
                self.show_modal(dlg)
        finally:
            s.player_group = None
        self.refresh_tracks()
        self.select_region_in_list(index)

    def new_player(self):
        """Control+Shift+R: a rhythm player region on a new track or the selected one."""
        s = self.session
        with NewPlayerDialog(self, s) as dlg:
            values = self.ask_values(dlg, dlg.get_values)
        if values is None:
            return
        tid, index = s.add_player_region(values["player"], values["style"], values["start_tick"],
                                         values["end_tick"], values["track_id"])
        self.refresh_tracks()
        self.select_region_in_list(index)
        self.region_list.SetFocus()

    def _on_player_region(self):
        s = self.session
        index = self.current_region()
        return (index is not None and not s.engine.recording
                and s.is_player_region(s.selected_track_id, index))

    def new_player_region(self):
        """P in the Regions list, the New rhythm player region button and Region menu item: a rhythm player
        region at the playhead, in the empty stretch of its section: the track's player and style, from its
        defaults."""
        _tid, index = self.session.add_player_region_here()
        self.select_region_in_list(index)
        self.region_list.SetFocus()

    def reforge_region(self):
        """Control+R in the Regions list: a different performance, with every setting kept."""
        s = self.session
        tid, index = self._need_region()
        if not s.is_player_region(tid, index):
            raise ValueError("Reforge works on rhythm player regions. This region holds ordinary notes; add a "
                             "rhythm player with Control+Shift+R.")
        s.reforge(tid, index)
        self.select_region_in_list(index)

    def region_settings(self):
        """Alt+Enter in the Regions list: trim a region's start and end, and loop it."""
        s = self.session
        tid, index = self._need_region()
        with RegionSettingsDialog(self, s, tid, index) as dlg:
            values = self.ask_values(dlg, dlg.get_values)
        if values is None:
            return
        start, end, loops = values
        if start is not None:
            index = s.trim_region(tid, index, start, end)
        if loops != s.region_loops(tid, index):
            s.set_region_loops(tid, index, loops)
        self.select_region_in_list(index)
        self.region_list.SetFocus()

    def settings_for_focus(self):
        """Alt+Enter: region settings in the Regions list, track settings everywhere else."""
        if self._focused_control() is self.region_list and self.current_region() is not None:
            self.region_settings()
        else:
            self.track_settings()

    def chord_track(self):
        """Control+Shift+H: the chord changes rhythm players play."""
        with ChordTrackDialog(self, self.session, run_modal=self.show_modal,
                              confirm=lambda m: ask_yes_no(self, m)) as dlg:
            self.show_modal(dlg)
        self.refresh_status_text()

    def move_region(self):
        s = self.session
        tid, index = self._need_region()
        indices = s.regions_for_action(current=index)
        bar, beat = s.song.timeline.tick_to_position(s.region_span(tid, indices[0])[0])
        with GoToBarDialog(self, bar, int(beat), title="Move region") as dlg:
            values = self.ask_values(dlg, dlg.get_values)
        if values is None:
            return
        to_bar, to_beat = values
        if s.song.track_by_id(tid).is_audio and len(indices) == 1:
            new = s.move_region(tid, indices[0], to_bar, to_beat)
        else:
            new = s.move_regions(tid, indices, to_bar, to_beat)
        self.select_region_in_list(new)
        self.region_list.SetFocus()

    def split_region(self):
        tid, index = self._need_region()
        self.select_region_in_list(self.session.split_region(tid, index))

    def join_regions(self):
        s = self.session
        tid = self._need_region_track()
        indices = s.regions_for_action(current=self.current_region())
        self.select_region_in_list(s.join_regions(tid, indices))

    def mute_regions(self):
        s = self.session
        tid = self._need_region_track()
        s.toggle_regions_mute(tid, s.regions_for_action(current=self.current_region()))
        self.refresh_regions()

    def rename_region(self):
        s = self.session
        tid, index = self._need_region()
        if s.song.track_by_id(tid).is_audio:
            raise ValueError("Recordings are named by where they start. You can rename regions on "
                             "instrument tracks.")
        with TextInputDialog(self, "Rename region", "Region name (empty uses the track's name)",
                             s.song.track_by_id(tid).note_regions[index].name) as dlg:
            if self.show_modal(dlg) == wx.ID_OK:
                s.rename_region(tid, index, dlg.get_value())
        self.select_region_in_list(index)

    # ------------------------------------------------------------------
    # editing, transport and song changes
    # ------------------------------------------------------------------
    def event_list(self):
        """Control+L: every note on an instrument track, or every recording on an audio track."""
        track = self._need_track()
        if self.session.engine.recording:     # a take adds notes under the open list (see _need_region)
            raise ValueError("Stop recording before opening the {}".format(
                "list of recordings" if track.is_audio else "event list"))
        if track.is_audio:
            with RecordingsDialog(self, self.session, track.id, run_modal=self.show_modal,
                                  confirm=lambda m: ask_yes_no(self, m), import_file=self.import_into_track) as dlg:
                self.show_modal(dlg)
        else:
            with EventListDialog(self, self.session, track.id) as dlg:
                self.show_modal(dlg)
        self.refresh_tracks()

    def quantize(self):
        """Control+Q: the region you are on (in the Regions list, or else at the playhead), the selected track, or
        all tracks (Russell, 10 Oct 2026)."""
        s = self.session
        track = self._need_track()
        region = None
        if not track.is_audio:
            index = self.current_region()
            if index is None:
                index = s.region_at_playhead(track.id)
            if index is not None and not s.is_player_region(track.id, index):
                region = index                 # a rhythm player region plays its own notes: nothing to quantize
        name = "region {}, {}".format(region + 1, s.region_name(track.id, region)) if region is not None else None
        with QuantizeDialog(self, s.settings, region_name=name) as dlg:
            values = self.ask_values(dlg, dlg.get_values)
        if values is None:
            return
        if values["what"] == "region":
            start, end = s.region_span(track.id, region)
            half = values["grid"] / 2.0
            # A note played a little early still belongs to the region it snaps into.
            chosen = [i for i, n in enumerate(track.notes) if start - half <= n.tick < end - half]
            if not chosen:
                raise ValueError("This region has no notes to quantize")
            s.quantize([track.id], values["grid"], values["strength"], values["lengths"], note_indices=chosen)
            return
        ids = [track.id] if values["what"] == "track" else [t.id for t in s.song.tracks]
        s.quantize(ids, values["grid"], values["strength"], values["lengths"])

    def changes(self, kind):
        with ChangesDialog(self, self.session, kind) as dlg:
            self.show_modal(dlg)
        self.refresh_status_text()

    def sections(self):
        with SectionsDialog(self, self.session, confirm=lambda m: ask_yes_no(self, m),
                            run_modal=self.show_modal) as dlg:
            self.show_modal(dlg)
        self.refresh_status_text()

    def section_settings(self):
        index = self.session.current_section_index()
        with SectionSettingsDialog(self, self.session, index) as dlg:
            values = self.ask_values(dlg, dlg.get_values)
        if values is None:
            return
        lost = self.session.notes_lost_if_shortened(index, values["length"])
        if lost and not ask_yes_no(self, "Shortening this section removes {} note{} in its last bars. "
                                         "You can undo this with Control+Z. Continue?".format(
                                             lost, "" if lost == 1 else "s")):
            return
        self.session.update_section(index, **values)

    def go_to_bar(self):
        tl = self.session.song.timeline
        bar = tl.tick_to_bar(self.session.position_tick())
        with GoToBarDialog(self, bar, 1) as dlg:
            values = self.ask_values(dlg, dlg.get_values)
        if values is not None:
            self.session.go_to_bar(*values)

    def toggle_metronome(self):
        self.session.toggle_metronome()
        self.refresh_status_text()

    def cycle_count_in(self):
        self.session.cycle_count_in()
        self.refresh_status_text()

    def speak_position(self):
        self.session.announce(self.session.describe_status())

    def chord_strips(self):
        """Customize chord strips (Control+Shift+J): the chords the keys A to K play in the Chord strips layout."""
        from .music_dialogs import ChordStripsDialog

        with ChordStripsDialog(self, self.session, run_modal=self.show_modal) as dlg:
            self.show_modal(dlg)
        self.refresh_controls()

    def speak_keyboard(self):
        """Control+J: the keyboard settings, plus the chord on every key when chord strips are on."""
        s = self.session
        text = s.describe_keyboard()
        if s.typing.mode == keyboard_map.MODE_CHORDS and not s.is_drum_track():
            text += " " + s.describe_chord_strips()
        s.announce(text)

    def stop_all_sound(self):
        if self.session.engine.recording or self.session.engine.playing:
            self.session.stop()
        self.session.engine.panic()
        self.session.announce("All sound stopped")

    # ------------------------------------------------------------------
    # options and help
    # ------------------------------------------------------------------
    def audio_settings(self, focus=None):
        """Options, Audio settings. focus "measure": opens it on the Measure the recording delay button."""
        outputs, inputs = [], []
        try:
            outputs = audio.list_outputs()
            inputs = audio.list_inputs()
        except Exception:  # noqa: BLE001
            log.exception("Could not list audio devices")
        test = self.test_microphone if self.session.audio_input is not None else None
        measure = self.measure_delay if self.session.audio_input is not None else None
        raw_before = self.session.settings["audio"]["raw_microphone"]
        from .. import lowlatency

        with AudioSettingsDialog(self, self.session.settings, outputs, inputs, test, measure,
                                 lowlatency.describe_support) as dlg:
            if focus == "measure":
                dlg.focus_measurement()
            values = self.ask_values(dlg, dlg.get_values)
        accepted = values is not None
        if not accepted:
            self.session.settings["audio"]["raw_microphone"] = raw_before   # Cancel puts it back
        self._configure_microphone()  # the chosen one, or back to the saved one after a test
        if not accepted:
            return
        self.session._apply_engine_settings()
        if self.audio_output is not None:
            try:
                description = self.audio_output.open(values["host_api"], values["device_name"],
                                                     values["block_frames"])
                self.session.audio_is_live = True
                self.session.announce("Audio: {}".format(description))
            except RuntimeError as exc:
                self.session.audio_is_live = False
                show_error(self, str(exc))
        self.refresh_status_text()

    def _configure_microphone(self):
        mic = self.session.audio_input
        if mic is not None and self.session.settings is not None and not self.session.engine.recording:
            settings = self.session.settings["audio"]
            mic.configure(settings["host_api"], settings["input_device"], settings["block_frames"],
                          settings["raw_microphone"])

    def test_microphone(self, host_api, device_name, done):
        """The microphone test in Audio settings: listen for 3 seconds, then say how loud it was."""
        mic = self.session.audio_input
        if mic is None:
            raise ValueError("Musician Forge has no microphone support here")
        if self.session.engine.recording:
            raise ValueError("Stop recording before testing the microphone")
        audio_settings = self.session.settings["audio"]
        mic.configure(host_api, device_name, audio_settings["block_frames"], audio_settings["raw_microphone"])
        mic.start_test()  # RuntimeError if no microphone opens
        self.session.announce("Listening for 3 seconds. Speak, sing or play something.")

        def finish():
            quiet = mic.quiet_level() if hasattr(mic, "quiet_level") else None
            peak, frames = mic.finish_test()
            message = audiotracks.describe_level(peak, frames, quiet=quiet)
            log.info("Microphone test: peak %.4f over %d frames, between sounds %s, %s", peak, frames,
                     "unknown" if quiet is None else "{:.1f} dB".format(audiotracks.peak_db(quiet)),
                     getattr(mic, "description", ""))
            self.session.announce(message)
            done(message)

        if self.test_mode:
            finish()
        else:
            wx.CallLater(MICROPHONE_TEST_MS, finish)

    def measure_delay(self, host_api, device_name, done):
        """Measure the recording delay (Audio settings): clicks through the speakers, heard by the
        microphone. done(measurement) is called when it has finished, about five seconds later."""
        mic = self.session.audio_input
        if mic is None:
            raise ValueError("Musician Forge has no microphone support here")
        audio_settings = self.session.settings["audio"]
        mic.configure(host_api, device_name, audio_settings["block_frames"], audio_settings["raw_microphone"])
        self.session.measure_recording_delay(done)
        self.session.announce("Measuring. Keep the room quiet; the clicks take about five seconds.")

    def preferences(self):
        with PreferencesDialog(self, self.session.settings) as dlg:
            if self.show_modal(dlg) != wx.ID_OK:
                return
            dlg.get_values()
        self.session._apply_engine_settings()
        if self.speaker is not None:
            self.speaker.allow_sapi = self.session.settings["speak_with_windows_voice"]
        self.refresh_status_text()

    def show_shortcuts(self):
        with TextViewDialog(self.visible_parent(), "Keyboard shortcuts", SHORTCUTS_TEXT) as dlg:
            self.show_modal(dlg)

    def show_layouts(self):
        text = "\n\n".join([keyboard_map.layout_help(), keyboard_map.layout_help(mode=keyboard_map.MODE_SCALE),
                            keyboard_map.layout_help(mode=keyboard_map.MODE_CHORDS),
                            "Right now: " + self.session.describe_chord_strips(),
                            keyboard_map.layout_help(drums=True)])
        with TextViewDialog(self.visible_parent(), "Musical keyboard layouts", text) as dlg:
            self.show_modal(dlg)

    def about(self):
        from .. import fluid

        engine_name = "FluidSynth {}".format(fluid.version()) if fluid.library_path() else "built-in simple synth"
        text = ("{} version {}\n\nAn accessible digital audio workstation for Windows.\n\n"
                "Instrument engine: {}\nInstruments: {}\nAudio: {}\nAnnouncements: {}\n\n"
                "FluidSynth is free software (GNU LGPL 2.1). GeneralUser GS is by S. Christian Collins "
                "and is free to use for your own music, private or commercial.\n\n"
                "Full credits are in Credits.md, and every version's changes in Changelog.md, "
                "both in the Musician Forge folder.").format(
            APP_NAME, __version__, engine_name,
            os.path.basename(getattr(self.session.engine.synth, "soundfont_path", "") or "none"),
            self.audio_output.description if self.audio_output else "off",
            self.speaker.describe() if self.speaker else "off")
        with TextViewDialog(self.visible_parent(), "About Musician Forge", text) as dlg:
            self.show_modal(dlg)

    # ------------------------------------------------------------------
    # closing
    # ------------------------------------------------------------------
    def on_close(self, event):
        if event.CanVeto():
            # stop first, as Close project does: a take being recorded goes into the song and counts as a
            # change, so closing asks to save it instead of losing it
            try:
                self.session.stop(speak=False)
            except Exception:  # noqa: BLE001
                log.exception("Could not stop before closing")
            try:
                keep_open = self.session.modified and not self.confirm_discard()
            except (ValueError, SongFileError) as exc:   # the save failed: say so, and stay open with the changes
                show_error(self, str(exc))
                keep_open = True
            except Exception as exc:  # noqa: BLE001
                log.exception("Saving before closing failed")
                show_error(self, "Something went wrong while saving: {}\n\nThe details were saved in the logs "
                                 "folder (musicianforge.log).".format(exc))
                keep_open = True
            if keep_open:
                event.Veto()
                return
        # Closed without the chance to ask (Windows shutting down or signing out): unsaved changes stay in the
        # crash-recovery copy, which the next start offers, and the recordings it needs are kept
        forced = not event.CanVeto() and not self._quitting and self.session.modified
        if forced:
            self.session.stop(speak=False)
            self.keep_recovery_copy()
            log.info("Closed by Windows with unsaved changes; the next start offers to recover them")
        if self.start_frame is not None:
            self.start_frame.Destroy()
            self.start_frame = None
        self.timer.Stop()
        self.autosave_timer.Stop()
        self.recovery_timer.Stop()
        self.output_watch.stop()
        if self.audio_output is not None:
            log.info("Audio health: %s blocks, %s underruns (dropouts), %s engine errors",
                     self.audio_output.callbacks, self.audio_output.underflows, self.session.engine.errors)
        try:
            self.session.stop(speak=False)
            self.session.engine.panic()
            self.session.shutdown(keep_recordings=forced)
            if self.audio_output is not None:
                self.audio_output.close()
            if not forced:
                self.session.mark_clean_exit()
            if self.session.settings is not None:
                self.session.settings.save()
        except Exception:  # noqa: BLE001
            log.exception("Problem while closing")
        self.Destroy()


SHORTCUTS_TEXT = """Musician Forge keyboard shortcuts

Starting
Musician Forge opens on the start screen: New project, Browse projects, and the Recent projects list.
Enter on a recent project opens it. Browse projects (Control+O in a project) lists your recent projects
first, then every other project in Musician Forge Songs, newest first; there Enter opens the selected
project, and Browse finds one in another folder. Delete in the Recent projects list removes a project
from the list (the file itself is kept). Control+W closes the project you are in, asks to save any
changes, and goes back to the start screen.

Moving around the project window
F6: go to the next area. Shift+F6: go to the previous area. They go round in a circle, in the order
the areas are on screen: Tracks, Regions, the Musical keyboard, the Keyboard controls, the Menus group
and Status. An area that is hidden or empty is skipped, and Musician Forge says where you landed, for
example "Menus group, 9 buttons".
Tab and Shift+Tab: move from control to control.
Space or Enter presses the button you are on.
Every command is in the menus. Alt opens the menu bar; the Menus group has a button for each menu (File,
Edit, Region, Track, Transport, Song, Keyboard, Options and Help), which opens the same menu with Tab.
Control+1: Tracks. Control+5: Regions. Control+2: Musical keyboard. Control+3: Status.
Control+4: Keyboard controls.
The track you are on and the region you are on end with "selected" in their lists. In selection mode
(Shift+F8), "selected" means the tracks and regions you marked with Space.

Sections
A new project is one 8-bar section. Add as many sections as you like.
Space plays and loops the section you are in. Turn on All sections (Control+Shift+L) to play the whole song.
Recording in a section loops back to its start, and each pass adds notes that you hear on the next pass.
Turn on Automatic in Section settings and the section grows when you record past its end, for long takes.
Control+comma and Control+period: previous and next section.
Control+Shift+A: the Sections list. Control+Shift+N: add a section after this one.
In the Sections list, Control+D (or Duplicate) copies the section to the end of the song: with sections
1, 2 and 3, duplicating any of them makes section 4.

Transport (anywhere in the main window)
Space: play or stop.
R: record, or stop recording. Pressing R while playing starts recording right away.
Recording starts quietly so you can hear the count-in and metronome.
Enter: go to the start of the section you are in (with All sections on, of the song). Rewinding stops there too.
Comma and period: back or forward one bar (Transport menu, Previous bar and Next bar).
Musician Forge says when you reach the start or end of a section.
Shift+comma and Shift+period: back or forward one beat.
Control+G: go to a bar.
Control+Shift+J: customize the chord strips (your own chord on each of the keys A to K).
Control+Shift+O: Audio settings. Control+Shift+D: measure the recording delay (both in the Options menu).
Control+K: metronome on or off.
Control+Shift+C: count-in off, 1 bar or 2 bars.
Control+P: speak the position, section, tempo, time signature and key.
Escape: stop all sound.

Musical keyboard (when it has focus)
Piano layout: A S D F G H J K L semicolon and apostrophe are white keys from C.
W E T Y U O P are the black keys.
Z and X: octave down and up. C and V: velocity down and up.
B: switch layout: piano, scale, then chord strips.
Scale layout: the home row plays the song's current scale from its root note, and follows key changes.
Chord strips: A S D F G H J K play the key's seven chords and a borrowed chord, each with its root
in the bass. Number keys 1 to 8 play the bass note of each chord. The chords follow key changes.
Drum kits use the drum layout automatically. Shift+F1 lists every layout and drum key.
Control+J: speak the keyboard settings, and in chord strips, the chord on every key.
Control+Shift+P: arpeggiator on or off. While it is on, held notes and chords play one note at a time,
in time with the song, and every note it plays is recorded.

Keyboard controls (the button right after the musical keyboard, or Control+4)
Layout, Scale, Octave, Velocity, Arpeggiator, Arpeggiator pattern, Arpeggiator speed and
Arpeggiator octave range. Up and Down arrows change a setting. The keys above change the same settings, and the
Keyboard menu has each setting as a submenu, with the current choice checked.

Regions list (the selected track's regions; recordings on audio tracks)
Each region says its name, its sections, where it starts and ends, how long it is, and how many notes.
Recording makes a region that covers what you recorded: the looping section, or from the bar where you
started to the bar after you stopped, across sections when All sections is on.
Enter: open the region (its notes, a recording's settings, or a rhythm player's editor). Delete: delete it (asks).
P, or Region menu, New rhythm player region: on a rhythm player track, a new region at the playhead, the same player
and style starting from its defaults (it fills the empty part of the section, for example a section you just added).
Alt+Enter: region settings: trim where it starts and ends, and loop it (play it several times in a row,
or until the next region). R or Control+R on a rhythm player region: Reforge (on any other
region, R records as everywhere else).
Control+X, Control+C, Control+V and Control+D: cut, copy, paste and duplicate. Paste puts regions at
the playhead and replaces what was there (Control+Z brings it back).
S: split the region at the playhead. J: join the selected regions. M: mute or unmute. F2: rename.
Region menu, Move region to a bar, moves a region to another bar.
Nudging (the nudge step is 1 bar, a quarter note, an eighth note or a sixteenth note; N changes it, Shift+N
goes back):
Alt+Left and Alt+Right: move the region (or the selected regions) earlier or later by the nudge step.
Left bracket and right bracket: move the region's start earlier or later.
Shift+left bracket and Shift+right bracket (or Alt+Shift+Left and Alt+Shift+Right): move its end earlier
or later. That is how a rhythm player's region gets longer: its end moves later and the player fills it.
A region never moves over another one: Musician Forge says what is in the way. Each key says where the region
now starts or ends and how long it is. Presses of the same key in a row are one undo step (Control+Z).

Selection (Shift+F8, or Edit menu, Select)
Selection on: Space selects or unselects the track or region you are on, and Musician Forge says how many
are selected. Cut, Copy, Paste, Duplicate, Delete, Mute and Solo then work on everything selected.
Control+A selects every track or region in the list. Shift+F8 again turns selection off.

Tracks list
Up and Down arrows: choose a track. Musical typing plays and records on the chosen track.
Control+X, Control+C, Control+V and Control+D: cut, copy, paste and duplicate tracks.
M: mute. S: solo. Left bracket and right bracket: volume down and up.
Shift+left bracket and Shift+right bracket: pan left and right.
Control+Up and Control+Down: move the track (also Track menu, Move track up and Move track down).
F2: rename. Delete: delete the track, or the selected tracks (asks first).
Alt+Enter: track settings. Control+I: change instrument. Control+T: new track. Control+U: new audio track.
Control+Shift+R: new rhythm player.
Control+F: the track's effects. Control+Shift+U: the track's automation.
Control+Shift+W: Write automation on or off.

Effects (Control+F, or Track menu, Effects)
Every track has a list of effects its sound goes through, top to bottom, before its volume and pan:
EQ, compressor, distortion, delay and reverb, and pitch correction on audio tracks.
In the list: Alt+A adds an effect, Enter opens its settings, Space turns it on or off,
Control+Up and Control+Down move it, Delete removes it.
Each effect starts from a preset, and every setting can be changed. In the settings window,
Up and Down arrows change a number (Page Up and Page Down by ten steps), and the change is heard
at once; the Play or stop button plays the song so you can listen. OK keeps the changes, Cancel puts
back what was there. Everything undoes with Control+Z. Exports include the effects.

Automation (Control+Shift+U, or Track menu, Automation)
A track's volume, pan and effect settings can change over time. Each thing that changes has a lane;
a lane has points (where, the value, and whether it glides to the next point or holds until it).
In the lanes list: Alt+A adds a lane, Enter lists its points, Space turns it on or off, Delete removes it.
In the points list: Alt+A adds a point at the playhead, Enter edits one, Delete removes one,
Space plays from it. Once a lane has points it sets that value for the whole song; turned off,
the track's own setting is used again.
Write automation (Control+Shift+W, or Track menu, Write automation): while the song plays,
changing volume ([ and ]), pan (Shift+[ and Shift+]), Track settings, or an effect's settings
writes points at the moment you hear. A whole play-through undoes with one Control+Z.
Written values hold until the next change. Effect settings moved while writing stay in the
automation even if you press Cancel; Control+Z takes them back.
Exports include automation; MIDI files get volume and pan changes as controller messages.

Audio tracks (record a microphone, or bring in audio files)
Control+U: new audio track. Then R records from the microphone, with the same count-in,
metronome and section looping as instrument tracks. Each pass over a looping section becomes a take,
and the newest take plays. Use wired headphones, so the metronome and other tracks stay out of the
recording. Wired, not Bluetooth: Bluetooth adds a delay you can hear (a fifth of a second or more).
Control+L on an audio track lists its recordings: Enter changes where one starts, which take plays,
and its gain. Space plays from it. Alt+I imports an audio file. Delete removes it.
Control+Shift+I: import an audio file (WAV, MP3, M4A, AAC, FLAC, Ogg, Opus, AIFF, Windows Media Audio
and more) onto the selected audio track, or onto a new one named after it; or a MIDI file (see below).
The Import window lists audio and MIDI files together first, then each kind. A long file shows how far
it has got (Escape cancels). Musician Forge keeps its own copy in the project's Recordings folder and says
the file's length, sample rate, and whether it is mono or stereo.
Options, Audio settings: choose the microphone, and test its level.
Measure the recording delay (in Audio settings): take headphones off, turn the speakers up and keep
the room quiet; Musician Forge plays eight clicks, listens with the microphone, and sets the microphone
timing adjustment so recordings land exactly on the beat.
Track settings for an audio track: record in stereo, and hear the microphone while recording.
Hearing yourself through a computer always takes a moment. Options, Audio settings has Low-latency
hearing yourself (Windows 10 and later, off at first): a shorter way, without the track's effects;
Check low-latency support says what your sound card allows. For no delay at all, use a USB microphone
or audio interface with its own headphone socket (direct monitoring), and wired headphones.
Recordings are kept in the project's own folder, in Recordings (My Song, Recordings).

Editing (also in the Edit menu: Undo, Redo, Event list and Quantize)
Control+Z: undo. Control+Y: redo. A whole recorded take, all its loop passes, undoes in one step.
Control+L: event list, every note on the selected track (or every recording on an audio track).
In the event list: Space selects a note, Control+A selects all, P plays, Enter edits, Alt+A adds, Delete removes,
Control+Up and Down move notes a semitone, add Shift for an octave. Each of these keys has a button too.
Control+Q: quantize the region you are on, the selected track or all tracks.

Song
Control+Shift+T: tempo changes. Control+Shift+M: time signature changes. Control+Shift+K: key changes.
Control+Shift+H: the chord track.

Chord track (Control+Shift+H, or Song menu, Chord track)
The chords of the song, in order; each lasts until the next. Rhythm players play these chords.
Enter edits a chord change, Alt+A adds one, Delete removes one. Fill from a progression puts a common
progression (such as one, five, six, four) into bars you choose, in the song's key. Work out from a track
listens to a track's notes, such as chord strips you played, and writes the chords it hears.
The Status (Control+3) says the chord at the playhead.

Rhythm players (Control+Shift+R, or Track menu, New rhythm player)
Anvil plays drums, Bellows bass, Ember keys, Spark synth, and Hammer guitar. Choose a player, a style,
where it goes (a new track or the selected one) and how long it plays. It makes a rhythm player region.
Enter on that region opens its editor: Style; Variation (each style has its own grooves or parts, numbered
and described; Previous and Next variation step through them); Patch (the instrument or kit); Intensity
(how hard it plays, never how many notes), Complexity (how busy), Fill amount, Fill complexity, Swing, Swing feel (eighth or
sixteenth notes); Follow (the chord track, another track, or nothing), the track to follow, Follow
amount, Hit sensitivity (for a recording); and the Kit pieces (the part, for bass, keys, synth and guitar).
Every change is heard at once. With several rhythm player regions selected, Enter edits them all together.
Control+R or the editor's Reforge button: a new performance of the same variation, picked at random, with new fills and
small details, and Musician Forge says "Regenerated performance"; the variation never changes, and Control+Z
goes back to the one before. Alt+S says
the summary. Turn into notes makes ordinary notes you can edit. Control+Z and Control+Y work inside the editor.
Kit pieces: Space turns a piece on or off; Enter opens its settings: Pattern (the variation's own, another
variation's, or a common one), Complexity and Loudness sliders for that piece alone, and its own extras: half or double
time (kick and snare), ghost notes, their loudness and a rim click (snare), how open the hi-hat is, toms in fills, when and
which crash comes, which ride and its bell. Each piece plays only its own sounds. Above 120 beats a minute the ride
plays no runs of sixteenth notes (its eighth notes stay), and above 140 neither does the hi-hat of a drummer (rock,
hard rock, metal, jazz, funk, pop); those patterns leave the Pattern list there. A part has the chord track on or off, an octave, a note length, the root
only, and passing notes into each chord change.
Step pattern (in a piece's settings): every step of one to four bars, read one by one, starting from what the
piece plays in the region's first bars, so changing one step changes only that step. A drum step can hold
several sounds; a part's steps start as "as the style plays it". Space turns a step on or off, Left and Right
choose its sound, Page Up and Page Down its loudness (each of these keys has a button under the list too),
Control+C and Control+V copy and paste steps. Changing a step makes the piece hand-made: its pattern repeats
through the region, Reforge keeps it, and crashes where the region starts and after fills still come by
themselves; changing the variation resets it after a warning, and Control+Z brings it back.
Hammer plays the two FreePats distorted guitar packs. Until they are downloaded, a stand-in guitar plays.

Projects and files
Control+N: new project. Control+O: open a project. Control+S: save. Control+Shift+S: save as.
Control+W: close the project and go back to the start screen.
Control+E: export audio, as WAV (full quality) or M4A (smaller, for sharing and Apple devices).
With WAV, What to export can also be every track, or only the tracks you choose (Space, or the button
Select or unselect the track, selects), each as its own WAV file: one track makes a WAV file, several a zip file.
Control+Shift+E: export the whole song as one MIDI file, with the chord track (silent) and the song's
tempos, time signatures, keys and section markers.
Control+Shift+I, or File menu, Import: import an audio file or a MIDI file.
File menu, Import MIDI file, lists only MIDI files.
Files go into Musician Forge Songs unless you choose another folder, and Musician Forge says where each went.
Musician Forge keeps a copy of your changes for crash recovery a few seconds after each one; Save puts them into the project.
Headphones: plug them in or out at any time. When Windows switches between the speakers and the headphones,
the sound follows (with Audio settings on Windows default).

Importing a MIDI file
Each MIDI track with notes becomes a new track (split by channel when a track holds several), with the
instrument its program change chooses; channel 10 becomes a drum track. The first volume and pan become the
track's own, and later volume and pan changes become automation. A window says what the file holds and
offers to use its tempo changes, time signatures, keys and markers (markers become sections); this is on
for a project with nothing in it yet, and then the empty Piano track makes way. Changes that a file puts
partway through a bar move to the next bar line, and Musician Forge says so. Control+Z takes the whole
import back. Musician Forge's own MIDI export writes the exact key (a mode such as Dorian) too, so a song
comes back the same.

Quiet recording
Starting playback, starting a recording, and the number of notes recorded are not announced,
so you can focus on the metronome. Options, Preferences can turn each announcement back on.

NVDA tip: if NVDA speaks each letter while you play, press NVDA+2 until it says
typed characters only in edit controls. Musician Forge's keyboard area is not an edit control.
"""
