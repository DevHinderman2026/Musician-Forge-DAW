"""Musician Forge's dialogs. Every one is keyboard-only friendly: Tab moves
between controls, Enter is OK, Escape is Cancel, and every control has a
label that screen readers read."""

import logging
import os

import wx

from .. import audiotracks, instruments, player_pieces, projects, theory
from ..exportcheck import FADE_SECONDS_DEFAULT, FADE_SECONDS_RANGE
from ..quantize import DEFAULT_GRID, GRID_NAMES, grid_ticks
from ..song import Note
from ..timeline import MAX_BPM, MAX_NUMERATOR, MIN_BPM, NOTE_LENGTHS, PPQ, describe_length, format_number
from .common import (BORDER, TRACK_GONE, DecimalField, Form, ShowAgain, ask_values, choice_ctrl,
                     enable_keeping_focus, end_dialog, finish_dialog, keep_enter_for_lists, note_text, say_after,
                     says_after, show_error, show_items, slider_ctrl, spin_ctrl, text_ctrl, undo_in_list_window)

log = logging.getLogger("musicianforge.ui")

DENOMINATOR_CHOICES = [2, 4, 8, 16]
SCALE_LABELS = [theory.scale_spoken_name(name) for name in theory.SCALE_NAMES]


class TextInputDialog(wx.Dialog):
    """One labeled text box (used for names and titles)."""

    def __init__(self, parent, title, label, value=""):
        super().__init__(parent, title=title)
        form = Form(self)
        self.text = form.add(label, text_ctrl, value=value)
        finish_dialog(self, form.grid)
        self.text.SetFocus()
        self.text.SelectAll()

    def get_value(self):
        return self.text.GetValue().strip()


class GoToBarDialog(wx.Dialog):
    def __init__(self, parent, bar=1, beat=1, title="Go to bar"):
        super().__init__(parent, title=title)
        form = Form(self)
        self.bar = form.add("Bar", spin_ctrl, min_value=1, max_value=9999, value=bar)
        self.beat = form.add("Beat", spin_ctrl, min_value=1, max_value=MAX_NUMERATOR, value=beat)
        finish_dialog(self, form.grid)
        self.bar.SetFocus()

    def get_values(self):
        return self.bar.GetValue(), self.beat.GetValue()


# ----------------------------------------------------------------------
# instruments and tracks
# ----------------------------------------------------------------------
class InstrumentDialog(wx.Dialog):
    """Pick a family, then an instrument. Each instrument plays as you arrow to it."""

    def __init__(self, parent, session, current=None):
        super().__init__(parent, title="Choose instrument", style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.session = session
        self.groups = instruments.group_presets(session.presets)
        self.families = list(self.groups)
        body = wx.BoxSizer(wx.HORIZONTAL)
        left = wx.BoxSizer(wx.VERTICAL)
        left.Add(wx.StaticText(self, label="Instrument family"))
        self.family_list = wx.ListBox(self, choices=self.families, size=(220, 320))
        left.Add(self.family_list, 1, wx.EXPAND | wx.TOP, 4)
        right = wx.BoxSizer(wx.VERTICAL)
        right.Add(wx.StaticText(self, label="Instrument (plays when selected)"))
        self.instrument_list = wx.ListBox(self, size=(300, 320))
        right.Add(self.instrument_list, 1, wx.EXPAND | wx.TOP, 4)
        self.preview = wx.CheckBox(self, label="Play each instrument when selected")
        self.preview.SetValue(True)
        right.Add(self.preview, 0, wx.TOP, 6)
        body.Add(left, 1, wx.EXPAND | wx.RIGHT, BORDER)
        body.Add(right, 2, wx.EXPAND)
        finish_dialog(self, body)
        self.family_list.Bind(wx.EVT_LISTBOX, self.on_family)
        self.instrument_list.Bind(wx.EVT_LISTBOX, self.on_instrument)
        self.instrument_list.Bind(wx.EVT_LISTBOX_DCLICK, lambda e: end_dialog(self, wx.ID_OK))
        self._select_current(current)

    def _select_current(self, current):
        family_index = 0
        preset_index = 0
        if current is not None:
            for i, family in enumerate(self.families):
                for j, preset in enumerate(self.groups[family]):
                    if preset.bank == current.bank and preset.program == current.program:
                        family_index, preset_index = i, j
        if self.families:
            self.family_list.SetSelection(family_index)
            self._fill(family_index)
            if self.instrument_list.GetCount():
                self.instrument_list.SetSelection(preset_index)
        self.instrument_list.SetFocus()

    def _fill(self, family_index):
        presets = self.groups[self.families[family_index]]
        self.instrument_list.Set([instruments.describe_preset(p) for p in presets])

    def on_family(self, event):
        index = self.family_list.GetSelection()
        if index != wx.NOT_FOUND:
            self._fill(index)
            if self.instrument_list.GetCount():
                self.instrument_list.SetSelection(0)

    def on_instrument(self, event):
        preset = self.get_preset()
        if preset is not None and self.preview.GetValue():
            self.session.preview_instrument(preset)

    def get_preset(self):
        f = self.family_list.GetSelection()
        i = self.instrument_list.GetSelection()
        if f == wx.NOT_FOUND or i == wx.NOT_FOUND:
            return None
        return self.groups[self.families[f]][i]


# The New track list (Russell, 23 Oct 2026: "when the user presses new track, the user can choose between a list of
# items ... instrument audio recording import file and then rhythm"): (what it is, its words in the list).
# Russell, 23 Oct 2026, 1:10 PM: Recording left the list ("that's not needed"); Import file is the one place to
# import from (it left the File menu).
TRACK_KINDS = (
    ("instrument", "Instrument: play or write notes with an instrument sound"),
    ("audio", "Audio: an empty audio track, for recording sound or adding audio files"),
    ("import", "Import file: an audio file on a new track, or a MIDI file as new tracks"),
    ("player", "Rhythm player: a player and its style, on a new track"),
)


class NewTrackDialog(wx.Dialog):
    """New track (Control+T, the New track button, and at once in a new project): a list of the kinds of track.
    Enter or a double-click on one chooses it, as does the Choose button; Escape and Cancel add nothing. Then that
    kind's own window opens (the instrument list, the rhythm player and its style, Windows' Open window).

    Enter is handled in the window's EVT_CHAR_HOOK: on Windows, a dialog's own navigation takes Enter before a
    list's EVT_KEY_DOWN sees it."""

    def __init__(self, parent):
        super().__init__(parent, title="New track")
        body = wx.BoxSizer(wx.VERTICAL)
        body.Add(wx.StaticText(self, label="Kind of track"))
        self.list = wx.ListBox(self, choices=[words for _kind, words in TRACK_KINDS], style=wx.LB_SINGLE,
                               size=(520, 120))
        body.Add(self.list, 1, wx.EXPAND | wx.TOP, 4)
        row = wx.BoxSizer(wx.HORIZONTAL)
        self.choose_button = wx.Button(self, wx.ID_OK, label="&Choose")
        self.cancel_button = wx.Button(self, wx.ID_CANCEL, label="Cancel")
        for button in (self.choose_button, self.cancel_button):
            row.Add(button, 0, wx.ALL, 3)
        body.Add(row, 0, wx.TOP, 6)
        body.Add(wx.StaticText(self, label="Enter chooses the selected kind. Escape adds nothing."), 0, wx.TOP, 6)
        finish_dialog(self, body, buttons=0)
        self.SetEscapeId(wx.ID_CANCEL)
        self.choose_button.SetDefault()
        self.list.SetSelection(0)
        self.choose_button.Bind(wx.EVT_BUTTON, lambda e: self.choose())
        self.cancel_button.Bind(wx.EVT_BUTTON, lambda e: end_dialog(self, wx.ID_CANCEL))
        self.list.Bind(wx.EVT_LISTBOX_DCLICK, lambda e: self.choose())
        self.Bind(wx.EVT_CHAR_HOOK, self.on_char_hook)
        self.list.SetFocus()

    def on_char_hook(self, event):
        key = event.GetKeyCode()
        if event.GetModifiers() == wx.MOD_NONE:
            on_list = event.GetEventObject() is self.list or wx.Window.FindFocus() is self.list
            if key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER) and on_list:
                self.choose()
                return
            if key == wx.WXK_ESCAPE:
                end_dialog(self, wx.ID_CANCEL)
                return
        event.Skip()

    def choose(self):
        if self.get_kind() is not None:
            end_dialog(self, wx.ID_OK)

    def get_kind(self):
        """"instrument", "audio", "import" or "player" (None when nothing is selected)."""
        index = self.list.GetSelection()
        return TRACK_KINDS[index][0] if 0 <= index < len(TRACK_KINDS) else None

    def choose_kind(self, kind):
        """Select a kind in the list (as arrowing to it does)."""
        self.list.SetSelection([k for k, _words in TRACK_KINDS].index(kind))


class TrackSettingsDialog(wx.Dialog):
    def __init__(self, parent, session, track):
        super().__init__(parent, title="Track settings: {}".format(track.name))
        self.session = session
        self.is_audio = track.is_audio
        self.preset = None if track.is_audio else instruments.find_preset(session.presets, track.instrument.bank,
                                                                          track.instrument.program)
        form = Form(self)
        self.name = form.add("Track name", text_ctrl, value=track.name)
        self.instrument_button = self.stereo = self.monitor = None
        if track.is_audio:
            self.stereo = wx.CheckBox(self, label="Record in stereo (two channels; off records one channel)")
            self.stereo.SetValue(track.stereo)
            form.add_wide(self.stereo)
            self.monitor = wx.CheckBox(self, label="Hear the microphone while recording (use headphones, "
                                                   "or the speakers will feed back)")
            self.monitor.SetValue(track.monitor)
            form.add_wide(self.monitor)
        else:
            self.instrument_button = wx.Button(self, label="Instrument: {}".format(track.instrument.name))
            form.add_wide(self.instrument_button)
        self.volume = form.add("Volume (percent)", slider_ctrl, value=track.volume, min_value=0, max_value=100)
        self.pan = form.add("Pan (left -100 to right 100)", slider_ctrl, value=track.pan,
                            min_value=-100, max_value=100)
        self.mute = wx.CheckBox(self, label="Mute")
        self.mute.SetValue(track.mute)
        form.add_wide(self.mute)
        self.solo = wx.CheckBox(self, label="Solo")
        self.solo.SetValue(track.solo)
        form.add_wide(self.solo)
        # Kit piece loudness (0.9.7; Russell, 23 Oct 2026: "adjusting the loudness of the ride, the hi-hat, that will
        # all move to the track settings for that rhythm player specific track"): the drummer's own mix on this track,
        # one slider per kit piece, on any track with a drummer, in every project (Russell, 23 Oct 2026, 4:52 AM: "for
        # new and old projects"). It is how loud each piece plays, not how hard the drummer plays (Intensity).
        self.kit_levels = {}
        if not track.is_audio and session.track_has_drummer(track.id):
            form.add_wide(wx.StaticText(self, label="Kit piece loudness (the drummer's mix on this track)"))
            levels = player_pieces.clean_kit_levels(track.kit_levels)
            for piece in player_pieces.DRUM_PIECES:
                self.kit_levels[piece.key] = form.add(
                    player_pieces.kit_level_label(piece), slider_ctrl,
                    value=levels.get(piece.key, player_pieces.LEVEL_DEFAULT), min_value=0, max_value=100)
        finish_dialog(self, form.grid)
        if self.instrument_button is not None:
            self.instrument_button.Bind(wx.EVT_BUTTON, self.on_instrument)
        self.name.SetFocus()

    def on_instrument(self, event):
        with InstrumentDialog(self, self.session, self.preset) as dlg:
            if dlg.ShowModal() == wx.ID_OK and dlg.get_preset() is not None:
                self.preset = dlg.get_preset()
                self.instrument_button.SetLabel("Instrument: {}".format(self.preset.name))

    def get_values(self):
        if not self.name.GetValue().strip():
            raise ValueError("A track needs a name")
        values = {"name": self.name.GetValue().strip(), "preset": self.preset,
                  "volume": self.volume.GetValue(), "pan": self.pan.GetValue(),
                  "mute": self.mute.GetValue(), "solo": self.solo.GetValue()}
        if self.is_audio:
            values.update(stereo=self.stereo.GetValue(), monitor=self.monitor.GetValue())
        if self.kit_levels:
            values["kit_levels"] = {key: slider.GetValue() for key, slider in self.kit_levels.items()}
        return values


# ----------------------------------------------------------------------
# tempo, time signature and key changes
# ----------------------------------------------------------------------
class TempoDialog(wx.Dialog):
    def __init__(self, parent, bar=1, beat=1, bpm=120.0, title="Tempo change"):
        super().__init__(parent, title=title)
        form = Form(self)
        self.bar = form.add("Bar", spin_ctrl, min_value=1, max_value=9999, value=bar)
        # decimals as the list shows them: a MIDI file's tempo changes can fall between beats (bar 2, beat 2.5), and a
        # whole-number box showed beat 2, so changing only the tempo moved the change there (the fifth review of
        # 25 Oct 2026). A beat left as shown keeps its exact place.
        self.beat = form.add("Beat", DecimalField, min_value=1, max_value=MAX_NUMERATOR + 0.999, value=beat, step=1,
                             decimals=3)
        self.exact_beat = float(beat)
        self.bpm = form.add("Tempo in beats per minute", text_ctrl, value=format_number(bpm))
        finish_dialog(self, form.grid)
        self.bpm.SetFocus()
        self.bpm.SelectAll()

    def get_values(self):
        """(bar, beat, bpm); raises ValueError with a friendly message."""
        try:
            bpm = float(self.bpm.GetValue().strip().replace(",", "."))
        except ValueError:
            raise ValueError("Type the tempo as a number, such as 120 or 92.5") from None
        if not MIN_BPM <= bpm <= MAX_BPM:
            raise ValueError("Tempo must be between {} and {}".format(int(MIN_BPM), int(MAX_BPM)))
        bar, beat = self.bar.GetValue(), self.beat.GetValue()
        if abs(beat - round(self.exact_beat, 3)) < 1e-9:
            beat = self.exact_beat
        return bar, beat, bpm


class TimeSignatureDialog(wx.Dialog):
    def __init__(self, parent, bar=1, numerator=4, denominator=4, title="Time signature change"):
        super().__init__(parent, title=title)
        form = Form(self)
        self.bar = form.add("Starting at bar", spin_ctrl, min_value=1, max_value=9999, value=bar)
        self.numerator = form.add("Beats per bar (top number)", spin_ctrl, min_value=1,
                                  max_value=MAX_NUMERATOR, value=numerator)
        selection = DENOMINATOR_CHOICES.index(denominator) if denominator in DENOMINATOR_CHOICES else 1
        self.denominator = form.add("Beat unit (bottom number)", choice_ctrl,
                                    choices=["2 (half note)", "4 (quarter note)", "8 (eighth note)",
                                             "16 (sixteenth note)"], selection=selection)
        finish_dialog(self, form.grid)
        self.numerator.SetFocus()

    def get_values(self):
        return (self.bar.GetValue(), self.numerator.GetValue(),
                DENOMINATOR_CHOICES[self.denominator.GetSelection()])


class KeyDialog(wx.Dialog):
    def __init__(self, parent, bar=1, tonic=0, scale="Major", title="Key change"):
        super().__init__(parent, title=title)
        form = Form(self)
        self.bar = form.add("Starting at bar", spin_ctrl, min_value=1, max_value=9999, value=bar)
        self.tonic = form.add("Root note", choice_ctrl, choices=theory.TONIC_NAMES, selection=tonic)
        self.scale = form.add("Scale", choice_ctrl, choices=SCALE_LABELS,
                              selection=theory.SCALE_NAMES.index(scale) if scale in theory.SCALE_NAMES else 0)
        finish_dialog(self, form.grid)
        self.tonic.SetFocus()

    def get_values(self):
        return self.bar.GetValue(), self.tonic.GetSelection(), theory.SCALE_NAMES[self.scale.GetSelection()]


class ChangesDialog(wx.Dialog):
    """A list of tempo, time signature or key changes with Add, Edit and Delete.

    kind is "tempo", "time" or "key".
    """

    TITLES = {"tempo": "Tempo changes", "time": "Time signature changes", "key": "Key changes"}

    def __init__(self, parent, session, kind, confirm_replace=None):
        """confirm_replace(words): the Yes or No question before Add takes the place of a change already at that
        bar (and beat); True replaces it (the project window asks for real, common.ask_replace)."""
        super().__init__(parent, title=self.TITLES[kind], style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.session = session
        self.kind = kind
        self.confirm_replace = confirm_replace or (lambda message: True)
        body = wx.BoxSizer(wx.VERTICAL)
        body.Add(wx.StaticText(self, label=self.TITLES[kind]))
        self.list = wx.ListBox(self, size=(420, 220))
        body.Add(self.list, 1, wx.EXPAND | wx.TOP, 4)
        buttons = wx.BoxSizer(wx.HORIZONTAL)
        self.add_button = wx.Button(self, label="&Add...")
        self.edit_button = wx.Button(self, label="&Edit...")
        self.delete_button = wx.Button(self, label="&Delete")
        close = wx.Button(self, wx.ID_CANCEL, label="Close")
        for b in (self.add_button, self.edit_button, self.delete_button, close):
            buttons.Add(b, 0, wx.RIGHT, 6)
        body.Add(buttons, 0, wx.TOP, 8)
        hint = note_text(self, "Enter edits the selected change. Delete removes it. "
                          "The first change cannot be deleted, only edited.")
        body.Add(hint, 0, wx.TOP, 8)
        finish_dialog(self, body, buttons=0)
        self.SetEscapeId(wx.ID_CANCEL)
        self.add_button.Bind(wx.EVT_BUTTON, lambda e: self.add())
        self.edit_button.Bind(wx.EVT_BUTTON, lambda e: self.edit())
        self.delete_button.Bind(wx.EVT_BUTTON, lambda e: self.delete())
        self.list.Bind(wx.EVT_LISTBOX_DCLICK, lambda e: self.edit())
        self.list.Bind(wx.EVT_KEY_DOWN, self.on_key)
        # Enter reaches the list (common.enter_for_lists); Control+Z and Control+Y undo and redo here
        keep_enter_for_lists(self, (self.list, self.on_key), undo=self.undo)
        self.refresh(0)
        self.list.SetFocus()

    def undo(self, redo=False):
        """Control+Z and Control+Y (common.undo_in_list_window)."""
        undo_in_list_window(self, redo, self.refresh)

    # what the dialogs edit ---------------------------------------------------
    def _items(self):
        tl = self.session.song.timeline
        if self.kind == "tempo":
            return tl.tempos
        if self.kind == "time":
            return tl.time_signatures
        return tl.keys

    def _describe(self, item):
        if self.kind == "tempo":
            return "Bar {}, beat {}: {} BPM".format(item.bar, format_number(item.beat), format_number(item.bpm))
        if self.kind == "time":
            return "From bar {}: {} {} time".format(item.bar, item.numerator, item.denominator)
        return "From bar {}: {}, {}".format(item.bar, item.name(),
                                           theory.describe_accidentals(theory.key_accidentals(item.tonic, item.scale)))

    def refresh(self, select=None):
        items = self._items()
        index = max(0, min(select if select is not None else 0, len(items) - 1)) if items else None
        show_items(self.list, [self._describe(i) for i in items], index)   # read once (screen reader audit B1)

    def _current_bar(self):
        """Where Add starts: the playhead's bar, or at the end of the song the last bar (Session.adding_tick)."""
        tl = self.session.song.timeline
        return tl.tick_to_bar(self.session.adding_tick())

    def _open_editor(self, item=None):
        tl = self.session.song.timeline
        if self.kind == "tempo":
            if item is None:
                bar = self._current_bar()
                return TempoDialog(self, bar, 1, tl.tempo_at_tick(tl.bar_to_tick(bar)), title="Add tempo change")
            return TempoDialog(self, item.bar, item.beat, item.bpm, title="Edit tempo change")
        if self.kind == "time":
            if item is None:
                bar = self._current_bar()
                ts = tl.time_signature_at_bar(bar)
                return TimeSignatureDialog(self, bar, ts.numerator, ts.denominator, title="Add time signature change")
            return TimeSignatureDialog(self, item.bar, item.numerator, item.denominator,
                                       title="Edit time signature change")
        if item is None:
            bar = self._current_bar()
            key = tl.key_at_bar(bar)
            return KeyDialog(self, bar, key.tonic, key.scale, title="Add key change")
        return KeyDialog(self, item.bar, item.tonic, item.scale, title="Edit key change")

    def _apply(self, values, replacing=None):
        s = self.session
        if replacing is not None:
            s.edit_change(self.kind, replacing, values)   # also when it moves: one step, all or nothing
        elif self.kind == "tempo":
            s.set_tempo(*values)
        elif self.kind == "time":
            s.set_time_signature(*values)
        else:
            s.set_key(*values)

    def _run_editor(self, item=None, index=None):
        # one window, shown again after a mistake with everything typed still in it (the review, 23 Oct 2026: a new
        # window came back with the old values, so a tempo typed as "12o" at bar 3 had to be typed again)
        def apply():
            values = dlg.get_values()
            if index == 0 and values[0] != 1:
                raise ValueError("The first change must stay at bar 1")
            self._refuse_moving_onto_another(values, index)
            if index is None:
                self._ask_before_replacing(values)         # No: this window comes back as it is (ShowAgain)
            self._apply(values, replacing=index)           # (TimelineError is a ValueError)
            return values

        with self._open_editor(item) as dlg:
            values = ask_values(lambda d: d.ShowModal(), dlg, apply, on_error=lambda words: show_error(self, words))
        if values is not None:
            self.refresh(self._find(values))

    def _refuse_moving_onto_another(self, values, index):
        """A change edited and moved onto another change's bar (and beat, for a tempo) would quietly take that
        one's place (session.edit_change puts it there, and the timeline keeps one change per place): refuse it in
        words instead, so nothing is lost without being asked (the review of 25 Oct 2026, as for automation points)."""
        if index is None:
            return
        found = self._find(values, missing=None)
        if found is not None and found != index:
            where = "bar {}".format(values[0])
            if self.kind == "tempo":
                where += ", beat {}".format(format_number(values[1]))
            what = {"tempo": "tempo change", "time": "time signature change", "key": "key change"}[self.kind]
            raise ValueError("Another {} is already at {}, so this one was not moved. Choose another {}, or edit "
                             "that one instead".format(what, where, "beat" if self.kind == "tempo" else "bar"))

    def _ask_before_replacing(self, values):
        """Add at a bar (and beat, for a tempo) that already has a change of this kind would take its place (the
        timeline keeps one per place): asked first, Yes or No (Russell, 25 Oct 2026; until then it was replaced
        without a word). No, or Escape, raises ShowAgain: the Add window comes back with everything typed still in
        it, so the place can be changed. Yes replaces it, as one undo step."""
        found = self._find(values, missing=None)
        if found is not None and not self.confirm_replace(self.replace_question(self._items()[found])):
            raise ShowAgain()

    def replace_question(self, item):
        """'There is already a tempo change at bar 5, beat 1 (90 BPM). Replace it?'"""
        if self.kind == "tempo":
            what = "a tempo change at bar {}, beat {} ({} BPM)".format(item.bar, format_number(item.beat),
                                                                       format_number(item.bpm))
        elif self.kind == "time":
            what = "a time signature change at bar {} ({} time)".format(item.bar, item.spoken())
        else:
            what = "a key change at bar {} ({})".format(item.bar, item.name())
        return "There is already {}. Replace it?".format(what)

    def _find(self, values, missing=0):
        for i, item in enumerate(self._items()):
            if item.bar == values[0] and (self.kind != "tempo" or abs(item.beat - values[1]) < 1e-9):
                return i
        return missing

    @says_after
    def add(self):
        self._run_editor(None, None)
        self.list.SetFocus()

    @says_after
    def edit(self):
        index = self.list.GetSelection()
        if index == wx.NOT_FOUND:
            return
        self._run_editor(self._items()[index], index)
        self.list.SetFocus()

    @says_after
    def delete(self):
        index = self.list.GetSelection()
        if index == wx.NOT_FOUND:
            return
        if index == 0:
            show_error(self, "The first change cannot be deleted. Use Edit to change it.")
            return
        remove = {"tempo": self.session.remove_tempo, "time": self.session.remove_time_signature,
                  "key": self.session.remove_key}[self.kind]
        remove(index)
        self.refresh(index)          # the next change, as in every other list (the last one when the last went)
        self.list.SetFocus()

    def on_key(self, event):
        key = event.GetKeyCode()
        if event.GetModifiers() != wx.MOD_NONE:
            event.Skip()            # Alt+Enter, Control+Delete and the like are not Enter or Delete (0.9.7)
        elif key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self.edit()
        elif key in (wx.WXK_DELETE, wx.WXK_NUMPAD_DELETE):
            self.delete()
        elif key in (wx.WXK_INSERT, wx.WXK_NUMPAD_INSERT):
            self.add()
        else:
            event.Skip()


# ----------------------------------------------------------------------
# notes
# ----------------------------------------------------------------------
LENGTH_CHOICES = [name for _ticks, name in NOTE_LENGTHS]
LENGTH_TICKS = [ticks for ticks, _name in NOTE_LENGTHS]


class NoteDialog(wx.Dialog):
    def __init__(self, parent, session, track_id, note=None, title="Edit note", at_tick=None):
        super().__init__(parent, title=title)
        self.session = session
        self.track_id = track_id
        tl = session.song.timeline
        if note is None:
            # at the playhead, or at the end of the song the last bar's start (Session.adding_tick)
            tick = session.adding_tick() if at_tick is None else at_tick
            note = Note(tick, PPQ, 60, session.typing.velocity)
        bar, beat = tl.tick_to_position(note.tick)
        key = tl.key_at_tick(note.tick)
        flats = theory.key_prefers_flats(key.tonic, key.scale)
        form = Form(self)
        self.bar = form.add("Bar", spin_ctrl, min_value=1, max_value=9999, value=bar)
        self.beat = form.add("Beat (decimals allowed, such as 2.5)", text_ctrl, value=format_number(beat))
        self.pitch = form.add("Note (such as C3, F sharp 2 or B flat 4)", text_ctrl,
                              value=theory.spoken_note_name(note.pitch, flats))
        self.velocity = form.add("Velocity (1 to 127)", spin_ctrl, min_value=1, max_value=127,
                                 value=note.velocity)
        if note.length in LENGTH_TICKS:
            selection = LENGTH_TICKS.index(note.length)
        else:
            selection = len(LENGTH_CHOICES)
        self.length = form.add("Length", choice_ctrl, choices=LENGTH_CHOICES + ["Other, in ticks"],
                               selection=selection)
        self.ticks = form.add("Length in ticks (960 = quarter note)", spin_ctrl, min_value=1,
                              max_value=960 * 64, value=note.length)
        finish_dialog(self, form.grid)
        self.length.Bind(wx.EVT_CHOICE, self.on_length)
        self.on_length(None)
        self.pitch.SetFocus()
        self.pitch.SelectAll()

    def on_length(self, event):
        index = self.length.GetSelection()
        if index < len(LENGTH_TICKS):
            self.ticks.SetValue(LENGTH_TICKS[index])
        # the ticks count only with "Other, in ticks": dimmed otherwise, so what is typed there is not ignored
        # without a word (the review, 23 Oct 2026)
        self.ticks.Enable(index >= len(LENGTH_TICKS))

    def get_note(self):
        """The edited note; raises ValueError with a friendly message."""
        tl = self.session.song.timeline
        bar = self.bar.GetValue()
        try:
            beat = float(self.beat.GetValue().strip().replace(",", "."))
        except ValueError:
            raise ValueError("Type the beat as a number, such as 1, 2.5 or 3.75") from None
        beats = tl.time_signature_at_bar(bar).numerator
        if not 1.0 <= beat < beats + 1.0:
            raise ValueError("Bar {} has {} beats, so the beat must be from 1 to {}".format(bar, beats, beats))
        pitch = theory.parse_note_name(self.pitch.GetValue())
        index = self.length.GetSelection()
        length = LENGTH_TICKS[index] if index < len(LENGTH_TICKS) else self.ticks.GetValue()
        return Note(tl.position_to_tick(bar, beat), int(length), pitch, self.velocity.GetValue())


class QuantizeDialog(wx.Dialog):
    def __init__(self, parent, settings, allow_selection=False, region_name=None):
        """region_name: the region you are on, offered as "The region" (Russell, 10 Oct 2026: quantize the region,
        the track or all tracks)."""
        super().__init__(parent, title="Quantize")
        self.settings = settings
        form = Form(self)
        grid_name = settings["quantize_grid"] if settings["quantize_grid"] in GRID_NAMES else DEFAULT_GRID
        self.grid = form.add("Grid", choice_ctrl, choices=GRID_NAMES, selection=GRID_NAMES.index(grid_name))
        self.strength = form.add("Strength in percent (100 snaps fully)", spin_ctrl, min_value=1,
                                 max_value=100, value=settings["quantize_strength"])
        self.lengths = wx.CheckBox(self, label="Also snap note lengths to the grid")
        self.lengths.SetValue(settings["quantize_lengths"])
        form.add_wide(self.lengths)
        if allow_selection:
            scopes = ["Selected notes", "Whole track", "All tracks"]
        elif region_name:
            scopes = ["The region you are on: {}".format(region_name), "Selected track", "All tracks"]
        else:
            scopes = ["Selected track", "All tracks"]
        self.scope_names = scopes
        self.scope_keys = (["notes", "track", "all"] if allow_selection else
                           (["region", "track", "all"] if region_name else ["track", "all"]))
        self.scope = wx.RadioBox(self, label="Quantize", choices=scopes, majorDimension=1,
                                 style=wx.RA_SPECIFY_COLS)
        form.add_wide(self.scope)
        finish_dialog(self, form.grid)
        self.grid.SetFocus()

    def get_values(self):
        strength = self.strength.GetValue()            # first: a number out of range changes nothing
        name = GRID_NAMES[self.grid.GetSelection()]
        self.settings["quantize_grid"] = name
        self.settings["quantize_strength"] = strength
        self.settings["quantize_lengths"] = self.lengths.GetValue()
        self.settings.save()
        return {"grid": grid_ticks(name), "grid_name": name, "strength": strength / 100.0,
                "lengths": self.lengths.GetValue(), "scope": self.scope.GetStringSelection(),
                "what": self.scope_keys[max(0, self.scope.GetSelection())]}


class EventListDialog(wx.Dialog):
    """Every note on a track, or in one region of it, one per line."""

    def __init__(self, parent, session, track_id, span=None, span_name=""):
        """span: (start tick, end tick) to list only the notes of one region."""
        track = session.song.track_by_id(track_id)
        where = "{}, {}".format(track.name, span_name) if span else track.name
        super().__init__(parent, title="Event list: {}".format(where),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.session = session
        self.track_id = track_id
        self.span = span
        body = wx.BoxSizer(wx.VERTICAL)
        body.Add(wx.StaticText(self, label="Notes in {}".format(span_name) if span else "Notes on {}".format(track.name)))
        # Space selects the note you are on (Russell, 10 Oct 2026), the way selection mode works in the project
        # window: the list itself chooses one note at a time, and the selected ones end with ", selected"
        self.list = wx.ListBox(self, size=(560, 320), style=wx.LB_SINGLE)
        self.marked = set()          # the selected notes, by their place on the whole track
        body.Add(self.list, 1, wx.EXPAND | wx.TOP, 4)
        self.play_on_move = wx.CheckBox(self, label="Play each note when selected")
        self.play_on_move.SetValue(True)
        body.Add(self.play_on_move, 0, wx.TOP, 6)
        self.buttons = {}
        # Every key of the list is a button too (Russell, 10 Oct 2026: every feature reachable with Tab; the keys are
        # extra). Rows of a few buttons each keep the window narrow enough for a laptop screen at 150 percent.
        for specs in ((("select", "&Select or unselect (Space)"), ("select_all", "Select a&ll (Control+A)"),
                       ("play", "&Play (P)")),
                      (("semitone_up", "&Up a semitone (Control+Up)"),
                       ("semitone_down", "Do&wn a semitone (Control+Down)")),
                      (("octave_up", "Up an &octave (Control+Shift+Up)"),
                       ("octave_down", "Down an octa&ve (Control+Shift+Down)")),
                      (("add", "&Add note..."), ("edit", "&Edit..."), ("delete", "&Delete"),
                       ("quantize", "&Quantize..."), ("close", "Close"))):
            row = wx.BoxSizer(wx.HORIZONTAL)
            for key, label in specs:
                button = wx.Button(self, wx.ID_CANCEL if key == "close" else wx.ID_ANY, label=label)
                self.buttons[key] = button
                row.Add(button, 0, wx.RIGHT, 6)
            body.Add(row, 0, wx.TOP, 6)
        help_text = ("Keys (each has a button too): Space selects or unselects the note you are on, Control+A selects "
                     "every note. Delete, Control plus Up or Down arrow (a semitone; add Shift for an octave), "
                     "Quantize and P (play) work on the selected notes, or on the note you are on when none is "
                     "selected. Enter edits the note you are on, and Alt+A adds one.")
        body.Add(note_text(self, help_text, width=560), 0, wx.TOP, 8)
        finish_dialog(self, body, buttons=0)
        self.SetEscapeId(wx.ID_CANCEL)
        self.buttons["add"].Bind(wx.EVT_BUTTON, lambda e: self.add())
        self.buttons["edit"].Bind(wx.EVT_BUTTON, lambda e: self.edit())
        self.buttons["delete"].Bind(wx.EVT_BUTTON, lambda e: self.delete())
        self.buttons["quantize"].Bind(wx.EVT_BUTTON, lambda e: self.quantize())
        for key, action in (("select", self.toggle_mark), ("select_all", self.mark_all), ("play", self.play_selected),
                            ("semitone_up", lambda: self.transpose(1)), ("semitone_down", lambda: self.transpose(-1)),
                            ("octave_up", lambda: self.transpose(12)), ("octave_down", lambda: self.transpose(-12))):
            self.buttons[key].Bind(wx.EVT_BUTTON, lambda e, a=action: self.on_note_button(a))
        self.list.Bind(wx.EVT_KEY_DOWN, self.on_key)
        # Enter reaches the list (common.enter_for_lists); Control+Z and Control+Y undo and redo here
        keep_enter_for_lists(self, (self.list, self.on_key), undo=self.undo)
        self.list.Bind(wx.EVT_LISTBOX, self.on_select)
        self.list.Bind(wx.EVT_LISTBOX_DCLICK, lambda e: self.edit())
        self.refresh([0])
        self.list.SetFocus()

    def undo(self, redo=False):
        """Control+Z and Control+Y (common.undo_in_list_window). The selected notes are kept as places on the track,
        so when the undo changed the notes those places may hold other notes: the selection is cleared then (as
        Delete would otherwise remove notes never selected; the final review of 10 Oct 2026)."""
        before = self._note_values()

        def refresh(here):
            if self._note_values() != before:
                self.marked.clear()
            count = len(self.notes)
            self.refresh([min(here, count - 1)] if count else [])
        undo_in_list_window(self, redo, refresh,
                            gone=lambda: TRACK_GONE if self.session.song.track_by_id(self.track_id) is None else None)

    def _note_values(self):
        track = self.session.song.track_by_id(self.track_id)
        return [(n.tick, n.length, n.pitch, n.velocity) for n in track.notes] if track is not None else None

    @property
    def track_notes(self):
        return self.session.song.track_by_id(self.track_id).notes

    def real_indices(self):
        """For each line of the list, the note's place on the whole track."""
        notes = self.track_notes
        if self.span is None:
            return list(range(len(notes)))
        start, end = self.span
        return [i for i, n in enumerate(notes) if start <= n.tick < end]

    @property
    def notes(self):
        notes = self.track_notes
        return [notes[i] for i in self.real_indices()]

    def _to_real(self, positions):
        mapping = self.real_indices()
        return [mapping[p] for p in positions if 0 <= p < len(mapping)]

    def _to_positions(self, real):
        mapping = self.real_indices()
        return [mapping.index(r) for r in real if r in mapping]

    def refresh(self, select=()):
        notes = self.notes
        mapping = self.real_indices()
        self.marked &= set(mapping)
        if notes:
            items = [self.session.describe_note(n, self.track_id) + (", selected" if mapping[i] in self.marked
                                                                     else "") for i, n in enumerate(notes)]
        else:
            items = ["No notes yet. Press Alt+A to add one, or record with the musical keyboard."]
        valid = [i for i in select if 0 <= i < len(notes)]
        here = valid[0] if valid else (0 if notes else wx.NOT_FOUND)
        # only what changed, and the list moves once: Space or Control+A used to fill the whole list again, and the
        # screen reader read it over what was said (screen reader audit B1, B2)
        show_items(self.list, items, here if here != wx.NOT_FOUND else 0)
        if notes and here != wx.NOT_FOUND:
            self.list.EnsureVisible(here)

    def current(self):
        """The note you are on (its line), or None."""
        here = self.list.GetSelection()
        return here if self.notes and 0 <= here < len(self.notes) else None

    def selected(self):
        """The lines of the selected notes (Space), or the note you are on when none is selected."""
        if not self.notes:
            return []
        if self.marked:
            return self._to_positions(sorted(self.marked))
        here = self.current()
        return [] if here is None else [here]

    def toggle_mark(self):
        here = self.current()
        if here is None:
            return
        real = self._to_real([here])[0]
        if real in self.marked:
            self.marked.discard(real)
            word = "unselected"
        else:
            self.marked.add(real)
            word = "selected"
        in_list = wx.Window.FindFocus() is self.list
        self.refresh([here])
        count = len(self.marked)
        words = "{} note{} selected".format(count, "" if count == 1 else "s")
        # Space in the list: the list reads the note again with or without ", selected", so only the count is
        # added, after it (screen reader audit B2); from the Select button the list is not read
        say_after(self.session.announce, words if in_list else "{}. {}".format(word.capitalize(), words))

    def mark_all(self):
        self.marked = set(self.real_indices())
        here = self.current()
        self.refresh([here] if here is not None else [])
        count = len(self.marked)
        say_after(self.session.announce, "{} note{} selected".format(count, "" if count == 1 else "s"))

    def on_note_button(self, action):
        """One of the buttons for the list's keys: the same as the key, on the note the list is on (or the selected
        notes). The focus stays on the button, so it can be pressed again (Up a semitone twice, say); what changed
        is said."""
        if not self.notes:
            self.session.announce("There are no notes yet. Press Alt+A to add one.")
            return
        action()

    def on_select(self, event):
        here = self.current()
        if here is not None and self.play_on_move.GetValue():
            self.session.audition_note(self.track_id, self.notes[here])

    def play_selected(self):
        notes = self.notes
        for i in self.selected()[:12]:
            self.session.audition_note(self.track_id, notes[i])

    def _marked_notes(self):
        """The selected notes themselves. They are kept as places on the track, and adding a note or giving one a
        new time sorts the notes again, which moves those places: the final review (10 Oct 2026) found the
        selection then on other notes, so Delete removed notes that were never selected. After such a change the
        selection is found again from the notes themselves (_mark_notes)."""
        notes = self.track_notes
        return [notes[i] for i in sorted(self.marked) if 0 <= i < len(notes)]

    def _mark_notes(self, chosen):
        wanted = {id(note) for note in chosen}
        self.marked = {i for i, note in enumerate(self.track_notes) if id(note) in wanted}

    @says_after
    def add(self):
        def add_it():
            chosen = self._marked_notes()
            return chosen, self.session.add_note(self.track_id, dlg.get_note())

        # one window, shown again after a mistake with everything typed still in it (the review, 23 Oct 2026)
        with NoteDialog(self, self.session, self.track_id, title="Add note",
                        at_tick=self.span[0] if self.span else None) as dlg:
            done = ask_values(lambda d: d.ShowModal(), dlg, add_it, on_error=lambda words: show_error(self, words))
        if done is not None:
            chosen, index = done
            self._mark_notes(chosen)
            self.refresh(self._to_positions([index]))
        self.list.SetFocus()

    @says_after
    def edit(self):
        here = self.current()                      # Enter edits the note you are on
        if here is None:
            return
        index = self._to_real([here])[0]

        def change_it():
            chosen = [note for note in self._marked_notes() if note is not self.track_notes[index]]
            was_marked = index in self.marked
            return chosen, was_marked, self.session.update_note(self.track_id, index, dlg.get_note())

        # one window, shown again after a mistake with everything typed still in it (the review, 23 Oct 2026)
        with NoteDialog(self, self.session, self.track_id, self.track_notes[index]) as dlg:
            done = ask_values(lambda d: d.ShowModal(), dlg, change_it,
                              on_error=lambda words: show_error(self, words))
        if done is not None:
            chosen, was_marked, new_index = done
            self._mark_notes(chosen)
            if was_marked:                        # the edited note stays selected, at its new place
                self.marked.add(new_index)
            self.refresh(self._to_positions([new_index]))
        self.list.SetFocus()

    @says_after
    def delete(self):
        chosen = self.selected()
        if not chosen:
            return
        self.session.delete_notes(self.track_id, self._to_real(chosen))
        self.marked.clear()
        self.refresh([min(chosen)])
        self.list.SetFocus()

    def transpose(self, semitones):
        chosen = self.selected()
        if chosen:
            notes = self.track_notes
            fits = all(0 <= notes[i].pitch + semitones <= 127 for i in self._to_real(chosen))
            moved_real = self.session.transpose_notes(self.track_id, self._to_real(chosen), semitones)
            if self.marked:
                self.marked = set(moved_real)
            moved = self._to_positions(moved_real)
            in_list = wx.Window.FindFocus() is self.list
            self.refresh(moved[:1])
            if len(moved) == 1 and fits:
                note = self.notes[moved[0]]
                if not in_list:      # in the list, the screen reader reads the note's new line itself (audit B2)
                    say_after(self.session.announce, self.session.describe_note(note, self.track_id))
                self.session.audition_note(self.track_id, note)
            elif len(moved) > 1 and fits:
                # several notes: said in words, since from a button the list is not read (the final review)
                say_after(self.session.announce, "{} notes {} {}".format(
                    len(moved), "up" if semitones > 0 else "down", "an octave" if abs(semitones) == 12 else "a semitone"))

    @says_after
    def quantize(self):
        with QuantizeDialog(self, self.session.settings, allow_selection=True) as dlg:
            while True:
                if dlg.ShowModal() != wx.ID_OK:
                    self.list.SetFocus()
                    return
                try:
                    values = dlg.get_values()
                    break
                except ValueError as exc:      # a strength out of range: said, and the window stays
                    show_error(dlg, str(exc))
        chosen = self.selected()
        if values["scope"] == "Selected notes":
            if not chosen:
                show_error(self, "Select the notes to quantize first.")
                return
            self.session.quantize([self.track_id], values["grid"], values["strength"], values["lengths"],
                                  note_indices=self._to_real(chosen))
            self.marked.clear()                     # the notes moved (their places on the track changed)
        elif values["scope"] == "Whole track":
            self.session.quantize([self.track_id], values["grid"], values["strength"], values["lengths"])
            self.marked.clear()                     # every note moved, so the places of the selected ones changed
        else:
            self.session.quantize([t.id for t in self.session.song.tracks], values["grid"],
                                  values["strength"], values["lengths"])
            self.marked.clear()
        self.refresh(chosen)
        self.list.SetFocus()

    def on_key(self, event):
        # each key with exactly the modifiers it is listed with: Alt+Enter is not Enter, Alt+Space is Windows'
        # own window menu, Control+Alt+Up is not Control+Up (0.9.7)
        key = event.GetKeyCode()
        mods = event.GetModifiers()
        plain = mods == wx.MOD_NONE
        ctrl = mods in (wx.MOD_CONTROL, wx.MOD_CONTROL | wx.MOD_SHIFT)
        shift = mods & wx.MOD_SHIFT
        if plain and key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self.edit()
        elif plain and key in (wx.WXK_DELETE, wx.WXK_NUMPAD_DELETE):
            self.delete()
        elif plain and key in (wx.WXK_INSERT, wx.WXK_NUMPAD_INSERT):
            self.add()
        elif plain and key == wx.WXK_SPACE:
            self.toggle_mark()                     # Space selects (Russell, 10 Oct 2026); P plays
        elif plain and key == ord("P"):
            self.play_selected()
        elif mods == wx.MOD_CONTROL and key == ord("A"):
            self.mark_all()
        elif ctrl and key == wx.WXK_UP:
            self.transpose(12 if shift else 1)
        elif ctrl and key == wx.WXK_DOWN:
            self.transpose(-12 if shift else -1)
        else:
            event.Skip()


# ----------------------------------------------------------------------
# audio tracks: the recordings on a track
# ----------------------------------------------------------------------
class RecordingDialog(wx.Dialog):
    """One recording: where it starts, which take plays, and its gain."""

    def __init__(self, parent, session, track_id, index):
        super().__init__(parent, title="Recording settings")
        self.session = session
        region = session.song.track_by_id(track_id).regions[index]
        tl = session.song.timeline
        bar, beat = tl.tick_to_position(region.tick)
        form = Form(self)
        self.bar = form.add("Starts at bar", spin_ctrl, min_value=1, max_value=9999, value=bar)
        self.beat = form.add("Beat (decimals allowed, such as 2.5)", text_ctrl, value=format_number(beat))
        takes = ["Take {}, {}".format(i + 1, audiotracks.describe_seconds(t.frames))
                 for i, t in enumerate(region.takes)]
        self.take = form.add("Take that plays", choice_ctrl, choices=takes, selection=region.active)
        self.take.Enable(len(takes) > 1)
        self.gain = form.add("Gain in dB ({:g} to {:g}, 0 leaves it as recorded)".format(
            audiotracks.GAIN_MIN_DB, audiotracks.GAIN_MAX_DB), spin_ctrl,
            min_value=int(audiotracks.GAIN_MIN_DB), max_value=int(audiotracks.GAIN_MAX_DB),
            value=int(round(region.gain_db)))
        finish_dialog(self, form.grid)
        self.bar.SetFocus()
        self.bar.SelectAll()

    def get_values(self):
        """{"tick", "take", "gain_db"}; raises ValueError with a friendly message."""
        tl = self.session.song.timeline
        bar = self.bar.GetValue()
        try:
            beat = float(self.beat.GetValue().strip().replace(",", "."))
        except ValueError:
            raise ValueError("Type the beat as a number, such as 1, 2.5 or 3.75") from None
        beats = tl.time_signature_at_bar(bar).numerator
        if not 1.0 <= beat < beats + 1.0:
            raise ValueError("Bar {} has {} beats, so the beat must be from 1 to {}".format(bar, beats, beats))
        return {"tick": tl.position_to_tick(bar, beat), "take": max(0, self.take.GetSelection()),
                "gain_db": float(self.gain.GetValue())}


class RecordingsDialog(wx.Dialog):
    """Every recording on an audio track, one per line (an audio track's list of what is on it)."""

    def __init__(self, parent, session, track_id, run_modal=None, confirm=None, import_file=None):
        """import_file(owner window, track id): asks for an audio file, imports it onto this track and returns
        the new recording's place in the list, or None."""
        track = session.song.track_by_id(track_id)
        super().__init__(parent, title="Recordings: {}".format(track.name),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.session = session
        self.track_id = track_id
        self.run_modal = run_modal or (lambda dialog: dialog.ShowModal())
        self.confirm = confirm or (lambda message: True)
        self.import_file = import_file
        body = wx.BoxSizer(wx.VERTICAL)
        body.Add(wx.StaticText(self, label="Recordings on {}".format(track.name)))
        self.list = wx.ListBox(self, size=(560, 260))
        body.Add(self.list, 1, wx.EXPAND | wx.TOP, 4)
        row = wx.WrapSizer(wx.HORIZONTAL)
        self.buttons = {}
        for key, label in (("play", "&Play or stop"), ("edit", "&Edit..."), ("import", "&Import audio file..."),
                           ("delete", "&Delete"), ("close", "Close")):
            button = wx.Button(self, wx.ID_CANCEL if key == "close" else wx.ID_ANY, label=label)
            self.buttons[key] = button
            row.Add(button, 0, wx.ALL, 3)
        body.Add(row, 0, wx.TOP, 6)
        body.Add(note_text(self, (
            "Enter edits the selected recording: where it starts, which take plays, and its gain. "
            "Space plays from it, or stops. Alt+I imports an audio file (WAV, MP3, M4A and more) at the playhead. "
            "Delete removes the recording."), width=520), 0, wx.TOP, 8)
        finish_dialog(self, body, buttons=0)
        self.SetEscapeId(wx.ID_CANCEL)
        actions = {"play": self.play, "edit": self.edit, "import": self.import_audio, "delete": self.delete}
        for key, action in actions.items():
            # Play or stop leaves the focus on its button, to be pressed again, as the Event list's buttons do
            # (Russell, 25 Oct 2026; it went back to the list, which the screen reader then read out); the others
            # end in the list, whose lines they change
            self.buttons[key].Bind(wx.EVT_BUTTON, lambda e, a=action, k=key: self._run(a, keep_focus=k == "play"))
        self.buttons["import"].Enable(import_file is not None)
        self.list.Bind(wx.EVT_KEY_DOWN, self.on_key)
        # Enter reaches the list (common.enter_for_lists); Control+Z and Control+Y undo and redo here
        keep_enter_for_lists(self, (self.list, self.on_key), undo=self.undo)
        self.list.Bind(wx.EVT_LISTBOX_DCLICK, lambda e: self._run(self.edit))
        self.refresh(0)
        self.list.SetFocus()

    def undo(self, redo=False):
        """Control+Z and Control+Y (common.undo_in_list_window); an undo that takes the track away closes the window."""
        undo_in_list_window(self, redo, self.refresh,
                            gone=lambda: TRACK_GONE if self.session.song.track_by_id(self.track_id) is None else None)

    @property
    def regions(self):
        return self.session.song.track_by_id(self.track_id).regions

    @says_after
    def _run(self, action, keep_focus=False):
        """A command of the list (its keys and buttons); the focus goes back to the list afterwards, unless
        keep_focus (the Play or stop button, like the Event list's buttons)."""
        try:
            action()
        except ValueError as exc:
            show_error(self, str(exc))
        except Exception as exc:  # noqa: BLE001 - said in words, never lost in the log alone
            log.exception("Recordings list action failed")
            show_error(self, "Something went wrong: {}\n\nThe details were saved in the logs folder "
                             "(musicianforge.log).".format(exc))
        if not keep_focus:
            self.list.SetFocus()

    def refresh(self, select=0):
        regions = self.regions
        if regions:
            show_items(self.list, [self.session.describe_region(self.track_id, i) for i in range(len(regions))],
                       max(0, min(select, len(regions) - 1)))
        else:
            show_items(self.list, ["No recordings yet. Press R in the main window to record from the microphone, "
                                   "or Alt+I to import an audio file."], 0)
        for key in ("play", "edit", "delete"):
            enable_keeping_focus(self.buttons[key], bool(regions), self.list)

    def selected(self):
        """The selected recording's place in the list, or None if there are none."""
        if not self.regions:
            return None
        index = self.list.GetSelection()
        return 0 if index == wx.NOT_FOUND else index

    def play(self):
        index = self.selected()
        if index is not None:
            self.session.play_region(self.track_id, index)

    def edit(self):
        index = self.selected()
        if index is None:
            return
        # one window, shown again after a mistake with everything typed still in it (the review, 23 Oct 2026)
        with RecordingDialog(self, self.session, self.track_id, index) as dlg:
            new_index = ask_values(self.run_modal, dlg,
                                   lambda: self.session.update_region(self.track_id, index, speak=False,
                                                                     **dlg.get_values()),
                                   on_error=lambda words: show_error(self, words))
        if new_index is not None:
            self.refresh(new_index)

    def import_audio(self):
        if self.import_file is None:
            return
        index = self.import_file(self, self.track_id)
        if index is not None:
            self.refresh(index)

    def delete(self):
        index = self.selected()
        if index is None:
            return
        if self.confirm("Delete the recording at {}? You can undo this with Control+Z.".format(
                self.session.describe_position(self.regions[index].tick))):
            self.session.delete_region(self.track_id, index)
            self.refresh(index)

    def on_key(self, event):
        key = event.GetKeyCode()
        action = None
        if event.GetModifiers() != wx.MOD_NONE:
            pass                                   # Alt+Enter and the like are not Enter (0.9.7)
        elif key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            action = self.edit
        elif key in (wx.WXK_INSERT, wx.WXK_NUMPAD_INSERT):
            action = self.import_audio
        elif key in (wx.WXK_DELETE, wx.WXK_NUMPAD_DELETE):
            action = self.delete
        elif key == wx.WXK_SPACE:
            action = self.play
        if action is None:
            event.Skip()
        else:
            self._run(action)


# ----------------------------------------------------------------------
# songs, export and settings
# ----------------------------------------------------------------------
class MidiImportDialog(wx.Dialog):
    """Import MIDI file: what the file holds, and whether its tempo, time signatures, keys and markers replace
    the project's own (on for a project with nothing in it yet)."""

    def __init__(self, parent, summary, use_timeline):
        super().__init__(parent, title="Import MIDI file")
        form = Form(self)
        self.summary = form.add("What the file holds", text_ctrl, value=summary,
                                style=wx.TE_READONLY | wx.TE_MULTILINE, size=(420, 70))
        self.timeline = wx.CheckBox(self, label="Use the file's tempo changes, time signatures, keys and markers "
                                                "(they replace the project's own; markers become sections)")
        self.timeline.SetValue(bool(use_timeline))
        form.add_wide(self.timeline)
        form.add_wide(note_text(self, ("Each MIDI track with notes becomes a new track, with its own "
                                  "instrument; channel 10 becomes drums. Control+Z takes the "
                                  "whole import back.")))
        finish_dialog(self, form.grid)
        # it opens on what the file holds, so the screen reader reads that first; Tab goes on to the check box
        # (screen reader audit D4, 23 Oct 2026)
        self.summary.SetFocus()

    def get_values(self):
        return {"use_timeline": self.timeline.GetValue()}


class NewSongDialog(wx.Dialog):
    """New project: the song's title, tempo, time signature and key."""

    def __init__(self, parent, settings):
        super().__init__(parent, title="New project")
        self.settings = settings
        d = settings["new_song"]
        form = Form(self)
        self.title_ctrl = form.add("Song title", text_ctrl, value="Untitled")
        self.bpm = form.add("Tempo in beats per minute", text_ctrl, value=format_number(d["bpm"]))
        self.numerator = form.add("Beats per bar (top number)", spin_ctrl, min_value=1,
                                  max_value=MAX_NUMERATOR, value=d["numerator"])
        den = d["denominator"] if d["denominator"] in DENOMINATOR_CHOICES else 4
        self.denominator = form.add("Beat unit (bottom number)", choice_ctrl,
                                    choices=["2 (half note)", "4 (quarter note)", "8 (eighth note)",
                                             "16 (sixteenth note)"], selection=DENOMINATOR_CHOICES.index(den))
        self.tonic = form.add("Key root note", choice_ctrl, choices=theory.TONIC_NAMES, selection=d["tonic"])
        scale = d["scale"] if d["scale"] in theory.SCALE_NAMES else "Major"
        self.scale = form.add("Key scale", choice_ctrl, choices=SCALE_LABELS,
                              selection=theory.SCALE_NAMES.index(scale))
        self.remember = wx.CheckBox(self, label="Use these settings for every new project")
        form.add_wide(self.remember)
        finish_dialog(self, form.grid)
        self.title_ctrl.SetFocus()
        self.title_ctrl.SelectAll()

    def get_values(self):
        try:
            bpm = float(self.bpm.GetValue().strip().replace(",", "."))
        except ValueError:
            raise ValueError("Type the tempo as a number, such as 120") from None
        if not MIN_BPM <= bpm <= MAX_BPM:
            raise ValueError("Tempo must be between {} and {}".format(int(MIN_BPM), int(MAX_BPM)))
        values = {"title": self.title_ctrl.GetValue().strip() or "Untitled", "bpm": bpm,
                  "numerator": self.numerator.GetValue(),
                  "denominator": DENOMINATOR_CHOICES[self.denominator.GetSelection()],
                  "tonic": self.tonic.GetSelection(), "scale": theory.SCALE_NAMES[self.scale.GetSelection()]}
        if self.remember.GetValue():
            self.settings["new_song"] = {k: values[k] for k in ("bpm", "numerator", "denominator", "tonic", "scale")}
            self.settings.save()
        return values


class SaveProjectDialog(wx.Dialog):
    """Save project as: the project's name, and the folder its own folder goes in."""

    def __init__(self, parent, name, folder, choose_folder=None):
        """choose_folder(current folder, owner window) asks for another folder and returns it, or None."""
        super().__init__(parent, title="Save project as")
        self.folder = folder
        self.choose_folder = choose_folder
        form = Form(self)
        self.name = form.add("Project name", text_ctrl, value=name)
        self.where = form.add("Saved in", text_ctrl, value=folder, style=wx.TE_READONLY)
        self.folder_button = wx.Button(self, label="Choose another &folder...")
        form.add_wide(self.folder_button)
        form.add_wide(note_text(self, ("Musician Forge makes a folder named after the project, "
                                  "with its Recordings and Exports folders inside.")))
        finish_dialog(self, form.grid)
        self.folder_button.Bind(wx.EVT_BUTTON, lambda e: self.on_choose_folder())
        self.folder_button.Enable(choose_folder is not None)
        self.name.SetFocus()
        self.name.SelectAll()

    def on_choose_folder(self):
        chosen = self.choose_folder(self.folder, self) if self.choose_folder else None
        if chosen:
            self.folder = chosen
            self.where.SetValue(chosen)
        self.name.SetFocus()
        if chosen:      # the Saved in box is not where the focus goes, so its new folder is said (audit, small note)
            from ..speech import speaker

            say_after(speaker.speak, "Saved in {}".format(chosen))

    def get_path(self):
        """Where the project file goes; raises ValueError if the name is empty."""
        name = self.name.GetValue().strip()
        if not name:
            raise ValueError("Type a name for the project")
        return projects.project_path(self.folder, name)


class OpenProjectDialog(wx.Dialog):
    """Open project: the projects you opened recently first, then every other project in Musician Forge Songs,
    newest first, or browse for one in another folder. Choosing Open project is the deliberate step, so Enter
    here opens the selected project (on the start screen the Recent projects list only shows them)."""

    def __init__(self, parent, found, browse=None, now=None, recent=(), preselect=None):
        """found: [(path, name, modified time)] from projects.find_projects().
        browse(owner window): asks for a project file anywhere and returns its path, or None.
        recent: the recent projects (paths, newest first); they come first, marked as recent.
        preselect: the path to have chosen already (the one the start screen's list was on)."""
        super().__init__(parent, title="Open project", style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.browse = browse
        self.chosen = None
        self.paths, items, seen = [], [], set()
        for path in recent:
            key = os.path.normcase(os.path.abspath(path))
            if key in seen:
                continue
            seen.add(key)
            self.paths.append(path)
            items.append("Recent: {}, in {}".format(projects.project_name(path), projects.location_name(path))
                         + ("" if os.path.isfile(path) else " (it is not there any more)"))
        for path, _name, modified in found:
            key = os.path.normcase(os.path.abspath(path))
            if key in seen:
                continue         # already listed as a recent project
            seen.add(key)
            self.paths.append(path)
            items.append(projects.describe_project(path, modified, now))
        body = wx.BoxSizer(wx.VERTICAL)
        heading = ("Projects: the ones you opened recently first, then the rest of Musician Forge Songs, newest first"
                   if recent else "Projects in Musician Forge Songs, newest first")
        body.Add(wx.StaticText(self, label=heading))
        self.list = wx.ListBox(self, size=(480, 260))
        body.Add(self.list, 1, wx.EXPAND | wx.TOP, 4)
        row = wx.BoxSizer(wx.HORIZONTAL)
        self.open_button = wx.Button(self, wx.ID_OK, label="&Open")
        self.browse_button = wx.Button(self, label="&Browse for a project in another folder...")
        cancel = wx.Button(self, wx.ID_CANCEL, label="Cancel")
        for button in (self.open_button, self.browse_button, cancel):
            row.Add(button, 0, wx.ALL, 3)
        body.Add(row, 0, wx.TOP, 6)
        body.Add(wx.StaticText(self, label="Enter opens the selected project."), 0, wx.TOP, 6)
        finish_dialog(self, body, buttons=0)
        self.SetEscapeId(wx.ID_CANCEL)
        self.list.Set(items or ["No projects in Musician Forge Songs yet. Browse opens a project from another folder."])
        start = 0
        if preselect:
            wanted = os.path.normcase(os.path.abspath(preselect))
            start = next((i for i, p in enumerate(self.paths) if os.path.normcase(os.path.abspath(p)) == wanted), 0)
        self.list.SetSelection(start)
        self.open_button.Enable(bool(self.paths))
        self.browse_button.Enable(browse is not None)
        if self.paths:
            self.open_button.SetDefault()
        self.open_button.Bind(wx.EVT_BUTTON, lambda e: self.open_selected())
        self.browse_button.Bind(wx.EVT_BUTTON, lambda e: self.browse_for_project())
        self.list.Bind(wx.EVT_LISTBOX_DCLICK, lambda e: self.open_selected())
        self.list.Bind(wx.EVT_KEY_DOWN, self.on_key)
        keep_enter_for_lists(self, (self.list, self.on_key))   # Enter reaches the list (common.enter_for_lists)
        (self.list if self.paths else self.browse_button).SetFocus()

    def selected_path(self):
        index = self.list.GetSelection()
        return self.paths[index] if 0 <= index < len(self.paths) else None

    def open_selected(self):
        path = self.selected_path()
        if path:
            self.chosen = path
            self._done()

    def browse_for_project(self):
        path = self.browse(self) if self.browse else None
        if path:
            self.chosen = path
            self._done()

    def _done(self):
        end_dialog(self, wx.ID_OK)

    def get_path(self):
        return self.chosen or self.selected_path()

    def on_key(self, event):
        if event.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER) and event.GetModifiers() == wx.MOD_NONE:
            self.open_selected()
        else:
            event.Skip()


class ExportAudioDialog(wx.Dialog):
    """Export audio: WAV (full quality) or M4A (smaller, for sharing and Apple devices); with WAV, the whole song
    or tracks on their own: every track, or only the tracks you choose, such as the vocals (Russell, 10 Oct 2026)."""

    FORMATS = ["wav", "m4a"]
    FORMAT_NAMES = ["WAV (full quality)", "M4A (smaller, for sharing and for Apple devices)"]
    RATES = [44100, 48000]
    BITS = [16, 24]
    WHAT = ["song", "every", "chosen"]
    WHAT_NAMES = ["The whole song, mixed into one file",
                  "Every track you can hear, each as its own WAV file",
                  "Only the tracks you choose, each as its own WAV file"]

    def __init__(self, parent, session):
        super().__init__(parent, title="Export audio")
        self.session = session
        settings = session.settings["export"]
        form = Form(self)
        fmt = settings.get("format", "wav") if settings.get("format", "wav") in self.FORMATS else "wav"
        rate = settings["sample_rate"] if settings["sample_rate"] in self.RATES else 48000
        bits = settings["bits"] if settings["bits"] in self.BITS else 24
        self.format = form.add("Format", choice_ctrl, choices=self.FORMAT_NAMES, selection=self.FORMATS.index(fmt))
        self.rate = form.add("Sample rate", choice_ctrl, choices=["44.1 kHz", "48 kHz"],
                             selection=self.RATES.index(rate))
        self.bits = form.add("Bit depth (WAV only)", choice_ctrl, choices=["16-bit", "24-bit"],
                             selection=self.BITS.index(bits))
        self.tail = wx.CheckBox(self, label="Let the sound ring out after the end (it stops once the sound "
                                            "has faded, up to 10 seconds)")
        self.tail.SetValue(bool(settings.get("tail", True)))
        form.add_wide(self.tail)
        # a fade-out at the end (Russell, 21 Oct 2026: 5 to 30 seconds, 10 to start); it ends where the song ends, so
        # the ring-out is dimmed while it is on
        self.fade = wx.CheckBox(self, label="&Fade out at the end of the song")
        self.fade.SetValue(bool(settings.get("fade", False)))
        form.add_wide(self.fade)
        low, high = FADE_SECONDS_RANGE
        seconds = settings.get("fade_seconds", FADE_SECONDS_DEFAULT)
        seconds = seconds if isinstance(seconds, int) and low <= seconds <= high else FADE_SECONDS_DEFAULT
        self.fade_length = form.add("Fade-out length in seconds ({} to {})".format(low, high), slider_ctrl,
                                    value=seconds, min_value=low, max_value=high)
        self.what = form.add("What to export (tracks on their own need WAV)", choice_ctrl,
                             choices=self.WHAT_NAMES, selection=0)
        # every track with something to play, in the order of the Tracks list
        notes = session.all_sounding_notes()
        self.track_ids = [t.id for t in session.song.tracks if (t.regions if t.is_audio else notes.get(t.id))]
        self.chosen = set()
        self.tracks = form.add("Tracks to export (Space selects a track, Control+A selects all)", wx.ListBox,
                               choices=[self.track_words(tid) for tid in self.track_ids], style=wx.LB_SINGLE)
        if self.track_ids:
            self.tracks.SetSelection(0)
        # the list's two keys as buttons too (Russell, 10 Oct 2026: every feature reachable with Tab)
        track_row = wx.BoxSizer(wx.HORIZONTAL)
        self.select_button = wx.Button(self, label="&Select or unselect the track (Space)")
        self.all_button = wx.Button(self, label="Select &all tracks (Control+A)")
        track_row.Add(self.select_button, 0, wx.RIGHT, 6)
        track_row.Add(self.all_button, 0)
        form.add_wide(track_row)
        # a read-only box Tab reaches, not words on the window that changed where no screen reader went (screen
        # reader audit, 23 Oct 2026)
        self.size_box = form.add("Estimated size", text_ctrl, value="", style=wx.TE_READONLY)
        finish_dialog(self, form.grid)
        for control in (self.format, self.rate, self.bits, self.what):
            control.Bind(wx.EVT_CHOICE, self.update_size)
        self.tail.Bind(wx.EVT_CHECKBOX, self.update_size)
        self.fade.Bind(wx.EVT_CHECKBOX, self.update_size)
        self.tracks.Bind(wx.EVT_KEY_DOWN, self.on_track_key)
        self.select_button.Bind(wx.EVT_BUTTON, lambda e: self.toggle_track())
        self.all_button.Bind(wx.EVT_BUTTON, lambda e: self.choose_all())
        self.update_size(None)
        self.format.SetFocus()

    def track_words(self, track_id):
        """"Vocals, audio track, selected": the track's name, its kind, muted, and whether it is chosen."""
        track = self.session.song.track_by_id(track_id)
        parts = [track.name]
        if track.is_audio:
            parts.append("audio track")
        if track.mute:
            parts.append("muted")
        if track_id in self.chosen:
            parts.append("selected")
        return ", ".join(parts)

    def refresh_tracks(self):
        # show_items: the item you are on changes its words last, once, so it is not read twice (the review,
        # 23 Oct 2026: every item's words were set again, the one you were on too)
        here = self.tracks.GetSelection()
        show_items(self.tracks, [self.track_words(tid) for tid in self.track_ids],
                   here if here != wx.NOT_FOUND else None)

    def on_track_key(self, event):
        key = event.GetKeyCode()
        if key == wx.WXK_SPACE and event.GetModifiers() == wx.MOD_NONE:
            self.toggle_track()
        elif key in (ord("A"), ord("a")) and event.GetModifiers() == wx.MOD_CONTROL:
            self.choose_all()
        else:
            event.Skip()

    def toggle_track(self):
        here = self.tracks.GetSelection()
        if here == wx.NOT_FOUND or not self.track_ids:
            return
        tid = self.track_ids[here]
        if tid in self.chosen:
            self.chosen.discard(tid)
            word = "not selected"
        else:
            self.chosen.add(tid)
            word = "selected"
        in_list = wx.Window.FindFocus() is self.tracks
        self.refresh_tracks()
        self.update_size(None)
        count = len(self.chosen)
        words = "{} track{} selected".format(count, "" if count == 1 else "s")
        # Space in the list: the list reads the track again with or without ", selected", so only the count is
        # added, after it, as in the event list (screen reader audit B2); from the button the list is not read, so
        # the track and its new state are said too. Said at once, the words and the list's reading cut each other
        # off (the review of 24 Oct 2026).
        say_after(self.session.announce, words if in_list else "{} {}. {}".format(
            self.session.song.track_by_id(tid).name, word, words))

    def choose_all(self):
        self.chosen = set(self.track_ids)
        self.refresh_tracks()
        self.update_size(None)
        count = len(self.chosen)
        say_after(self.session.announce, "{} track{} selected".format(count, "" if count == 1 else "s"))

    def chosen_format(self):
        return self.FORMATS[max(0, self.format.GetSelection())]

    def what_to_export(self):
        """"song" (one mixed file), "every" (every track you can hear) or "chosen" (the tracks you chose)."""
        if self.chosen_format() != "wav":
            return "song"
        return self.WHAT[max(0, self.what.GetSelection())]

    def tracks_to_export(self):
        """The track ids for a track-by-track export, in the Tracks list's order."""
        what = self.what_to_export()
        if what == "every":
            heard = {t.id for t in self.session.song.audible_tracks()}
            return [tid for tid in self.track_ids if tid in heard]
        if what == "chosen":
            return [tid for tid in self.track_ids if tid in self.chosen]
        return []

    # kept for older callers: True when tracks go out on their own
    def each_track(self):
        return self.what_to_export() != "song"

    def get_values(self):
        """(format, sample rate, bit depth, ring-out on or off); remembered for the next export. A track-by-track
        export with no track chosen says so and the window stays."""
        if self.what_to_export() == "chosen" and not self.chosen:
            raise ValueError("Choose the tracks to export first: in Tracks to export, press Space on each one "
                             "(or use the Select or unselect the track button).")
        if self.what_to_export() == "every" and not self.tracks_to_export():
            raise ValueError("No track you can hear has anything to export.")
        fmt = self.chosen_format()
        rate = self.RATES[self.rate.GetSelection()]
        bits = self.BITS[self.bits.GetSelection()]
        tail = self.tail.GetValue()
        self.session.settings["export"].update(format=fmt, sample_rate=rate, bits=bits, tail=tail,
                                               fade=self.fade.GetValue(), fade_seconds=self.fade_length.GetValue())
        self.session.settings.save()
        return fmt, rate, bits, tail

    def fade_seconds(self):
        """The fade-out's length in seconds, or 0 when it is off."""
        return int(self.fade_length.GetValue()) if self.fade.GetValue() else 0

    def update_size(self, event):
        fmt = self.chosen_format()
        self.bits.Enable(fmt == "wav")
        self.what.Enable(fmt == "wav")
        what = self.what_to_export()
        choosing = what == "chosen" and bool(self.track_ids)
        for control in (self.tracks, self.select_button, self.all_button):
            control.Enable(choosing)
        fading = self.fade.GetValue()
        self.fade_length.Enable(fading)
        self.tail.Enable(not fading)            # the fade ends where the song ends: nothing is left to ring out
        rate = self.RATES[self.rate.GetSelection()]
        bits = self.BITS[self.bits.GetSelection()]
        megabytes = self.session.estimate_export_bytes(fmt, rate, bits, self.tail.GetValue() and not fading) / 1e6
        if what == "song":
            self.size_box.ChangeValue("Estimated file size: {:.1f} megabytes".format(megabytes))
        else:
            count = len(self.tracks_to_export())
            if count == 1:
                kind = "1 track, one WAV file"
            else:
                kind = "{} tracks, one zip file".format(count)
            self.size_box.ChangeValue("Estimated size: {:.1f} megabytes ({})".format(megabytes * max(1, count), kind))
        self.Layout()


ExportWavDialog = ExportAudioDialog  # its name before M4A arrived


def device_pair_key(host_api, output, microphone):
    """How a measured recording delay is remembered: for this output and this microphone together."""
    return "{}|{}|{}".format(host_api, output or "default", microphone or "default")


def remembered_offset(settings, key):
    for stored_key, ms in settings["microphone_offsets"]:
        if stored_key == key:
            return int(ms)
    return None


def remember_offset(settings, key, ms):
    pairs = [[k, v] for k, v in settings["microphone_offsets"] if k != key]
    settings["microphone_offsets"] = [[key, int(ms)]] + pairs[:19]


class AudioSettingsDialog(wx.Dialog):
    BLOCKS = [128, 256, 512, 1024]

    def __init__(self, parent, settings, outputs, inputs=None, test_microphone=None, measure_delay=None,
                 check_low_latency=None):
        """outputs and inputs: [(host_api_name, [device names])] from audio.list_outputs() and list_inputs().
        test_microphone(host_api, device_name, done): listens for a moment, then calls done(message).
        measure_delay(host_api, device_name, done): plays clicks and listens, then calls
        done(latency.Measurement).
        check_low_latency(output name, microphone name): what Windows offers for low-latency hearing yourself,
        in words (0.9.1; only reads).

        The Raw microphone sound check box takes effect at once (so the test and the measurement use it);
        the project window puts it back if the window is cancelled."""
        super().__init__(parent, title="Audio settings")
        self.settings = settings
        self.outputs = outputs or [("Windows WASAPI", [])]
        self.inputs = inputs or []
        self.test_microphone = test_microphone
        self.measure_delay = measure_delay
        self.check_low_latency = check_low_latency
        audio = settings["audio"]
        form = Form(self)
        apis = [api for api, _ in self.outputs]
        api_index = apis.index(audio["host_api"]) if audio["host_api"] in apis else 0
        self.api = form.add("Audio driver (WASAPI has the shortest delay)", choice_ctrl,
                            choices=apis, selection=api_index)
        self.device = form.add("Output device", choice_ctrl, choices=[])
        self.microphone = form.add("Microphone (for audio tracks)", choice_ctrl, choices=[])
        self.raw_check = wx.CheckBox(self, label="Raw microphone sound: Windows noise reduction and other microphone "
                                                 "processing off (best for music; WASAPI only)")
        self.raw_check.SetValue(bool(audio.get("raw_microphone", True)))
        form.add_wide(self.raw_check)
        self.test_button = wx.Button(self, label="&Test the microphone")
        form.add_wide(self.test_button)
        self.test_result = form.add("Microphone test result", text_ctrl,
                                    value="Not tested yet. The test listens for 3 seconds.",
                                    style=wx.TE_READONLY | wx.TE_MULTILINE, size=(-1, 60))
        block = audio["block_frames"] if audio["block_frames"] in self.BLOCKS else 256
        self.block = form.add("Buffer size (smaller is quicker, larger is safer)", choice_ctrl,
                              choices=["{} samples ({:.1f} milliseconds)".format(b, b * 1000.0 / 48000)
                                       for b in self.BLOCKS],
                              selection=self.BLOCKS.index(block))
        self.offset = form.add("Musical keyboard timing adjustment in milliseconds (positive moves notes earlier)",
                               spin_ctrl, min_value=-200, max_value=200, value=settings["record_offset_ms"])
        self.mic_offset = form.add("Microphone timing adjustment in milliseconds (positive moves recordings "
                                   "earlier)", spin_ctrl, min_value=-200, max_value=200,
                                   value=settings["microphone_offset_ms"])
        self.measure_button = wx.Button(self, label="&Measure the recording delay (plays clicks; take headphones off)")
        form.add_wide(self.measure_button)
        self.measure_result = form.add("Measurement result", text_ctrl,
                                       value="Not measured yet. It takes about five seconds in a quiet room.",
                                       style=wx.TE_READONLY | wx.TE_MULTILINE, size=(-1, 60))
        self.low_latency = wx.CheckBox(self, label="Low-latency hearing yourself (Windows 10 and later): hear the "
                                                   "microphone sooner while recording, without the track's effects")
        self.low_latency.SetValue(bool(audio.get("low_latency_monitoring", False)))
        form.add_wide(self.low_latency)
        self.low_latency_button = wx.Button(self, label="Check &low-latency support")
        form.add_wide(self.low_latency_button)
        self.low_latency_result = form.add("Low-latency check result", text_ctrl,
                                           value="Not checked yet. The check only reads what Windows offers.",
                                           style=wx.TE_READONLY | wx.TE_MULTILINE, size=(-1, 60))
        finish_dialog(self, form.grid)
        self.api.Bind(wx.EVT_CHOICE, lambda e: self._fill_devices("", ""))
        self.device.Bind(wx.EVT_CHOICE, lambda e: self._devices_changed())
        self.microphone.Bind(wx.EVT_CHOICE, lambda e: self._devices_changed())
        self.raw_check.Bind(wx.EVT_CHECKBOX, lambda e: self._raw_changed())
        self.test_button.Bind(wx.EVT_BUTTON, lambda e: self.run_test())
        self.measure_button.Bind(wx.EVT_BUTTON, lambda e: self.run_measurement())
        self.low_latency_button.Bind(wx.EVT_BUTTON, lambda e: self.run_low_latency_check())
        self._saved_pair = device_pair_key(audio["host_api"], audio["device_name"], audio["input_device"])
        # What the Microphone timing adjustment shows, and where it came from: "remembered" for this pair,
        # "measured" here, or None (carried over from another pair, or never measured). Only a remembered,
        # measured or typed value is remembered for the pair on OK (the review of 9 Oct 2026: every OK
        # remembered whatever the box held, so a pair never measured said "Measured before").
        self._shown_offset = settings["microphone_offset_ms"]
        self._offset_source = None
        self._measured = {}           # pair -> what was measured for it in this window (kept on OK)
        self._fill_devices(audio["device_name"], audio["input_device"])
        self.test_button.Enable(test_microphone is not None)
        self.measure_button.Enable(measure_delay is not None)
        self.low_latency_button.Enable(check_low_latency is not None)
        self.api.SetFocus()

    def _fill_devices(self, wanted, wanted_microphone):
        api = self.api.GetStringSelection()
        names = dict(self.outputs).get(api, [])
        self.device.Set(["Windows default"] + names)
        self.device.SetSelection(names.index(wanted) + 1 if wanted in names else 0)
        microphones = dict(self.inputs).get(api, [])
        self.microphone.Set(["Windows default"] + microphones)
        self.microphone.SetSelection(microphones.index(wanted_microphone) + 1
                                     if wanted_microphone in microphones else 0)
        self._devices_changed()

    def chosen_microphone(self):
        return "" if self.microphone.GetSelection() <= 0 else self.microphone.GetStringSelection()

    def chosen_output(self):
        return "" if self.device.GetSelection() <= 0 else self.device.GetStringSelection()

    def pair_key(self):
        return device_pair_key(self.api.GetStringSelection(), self.chosen_output(), self.chosen_microphone())

    def _devices_changed(self):
        """Another output or microphone: use the delay measured for that pair, or say to measure it."""
        from .. import audio as audio_module

        notes = []
        key = self.pair_key()
        known = remembered_offset(self.settings, key)
        if known is not None:
            self._show_offset(known, "remembered")
            notes.append("Measured before for this output and microphone: the timing adjustment is {} "
                         "milliseconds.".format(known))
        else:
            try:
                self._shown_offset = self.mic_offset.GetValue()
            except ValueError:
                self._shown_offset = None
            self._offset_source = None
            if key != self._saved_pair:
                notes.append("Not measured yet for this output and microphone. Measure the recording delay "
                             "(take headphones off) so recordings land on the beat.")
        if any(audio_module.looks_like_bluetooth(name) for name in (self.chosen_output(), self.chosen_microphone())):
            notes.append("This looks like a Bluetooth device. Bluetooth adds a fifth of a second or more of delay; "
                         "wired headphones are best for recording.")
        if notes:
            self.measure_result.SetValue(" ".join(notes))

    def _show_offset(self, value, source):
        try:
            showing = self.mic_offset.GetValue()
        except ValueError:
            showing = None
        if showing != value:
            self.mic_offset.SetValue(value)
        self._shown_offset, self._offset_source = value, source

    def _raw_changed(self):
        self.settings["audio"]["raw_microphone"] = self.raw_check.GetValue()
        self.measure_result.SetValue("Raw microphone sound is {}. Test the microphone, and measure the recording "
                                     "delay again: Windows' processing takes time of its own.".format(
                                         "on" if self.raw_check.GetValue() else "off"))

    def run_test(self):
        if self.test_microphone is None:
            return
        # the words first, then the focus on them (the screen reader reads them), then the button is dimmed: dimmed
        # while it had the focus, Windows sent the focus on to whatever came next (screen reader audit D1)
        self.test_result.SetValue("Listening for 3 seconds. Speak, sing or play something.")
        self.test_result.SetFocus()
        self.test_button.Enable(False)
        try:
            self.test_microphone(self.api.GetStringSelection(), self.chosen_microphone(), self.show_test_result)
        except (ValueError, RuntimeError) as exc:
            self.show_test_result(str(exc))
            self._say(str(exc))   # the box has the focus, but its new words are not read by themselves

    @staticmethod
    def _say(words):
        """A test or measurement that could not start (no microphone, say): said, after the result box's reading."""
        from ..speech import speaker

        say_after(speaker.speak, words)

    def show_test_result(self, message):
        try:
            self.test_result.SetValue(message)
            self.test_button.Enable(True)
        except RuntimeError:  # the dialog closed while the test was listening
            pass

    def focus_measurement(self):
        """Options, Measure the recording delay: this window opens on the button (it is far down the window). Without
        a microphone the button is dimmed, and a screen reader's Tab skips it, so the result box says why."""
        if self.measure_button.IsEnabled():
            self.measure_button.SetFocus()
        else:
            self.measure_result.SetValue("The measurement needs a microphone, and none is set up. Choose one above.")
            self.measure_result.SetFocus()

    def run_measurement(self):
        if self.measure_delay is None:
            return
        self.measure_result.SetValue("Measuring: eight clicks, about five seconds. Keep the room quiet.")
        self.measure_result.SetFocus()                 # as for the microphone test (audit D1)
        self.measure_button.Enable(False)
        try:
            self.measure_delay(self.api.GetStringSelection(), self.chosen_microphone(), self.show_measurement)
        except (ValueError, RuntimeError) as exc:
            self.measure_result.SetValue(str(exc))
            self.measure_button.Enable(True)
            self._say(str(exc))

    def show_measurement(self, result):
        """The measurement finished: show what was found, and fill in the adjustment if it is trustworthy."""
        try:
            self.measure_result.SetValue(result.describe())
            if result.reliable:
                self._show_offset(result.adjustment_ms, "measured")
                self._measured[self.pair_key()] = result.adjustment_ms
            self.measure_button.Enable(True)
        except RuntimeError:  # the window closed while measuring
            pass

    def run_low_latency_check(self):
        """What Windows offers for the chosen output and microphone, in words (only reads)."""
        if self.check_low_latency is None:
            return
        self.low_latency_result.SetValue("Checking...")
        try:
            words = self.check_low_latency(self.chosen_output(), self.chosen_microphone())
        except Exception as exc:  # noqa: BLE001 - said in words; nothing was changed
            words = "The check could not finish: {}".format(exc)
        self.low_latency_result.SetValue(words)
        self.low_latency_result.SetFocus()

    def get_values(self):
        record_offset = self.offset.GetValue()         # first: a number out of range changes nothing at all
        offset = self.mic_offset.GetValue()
        audio = self.settings["audio"]
        audio["host_api"] = self.api.GetStringSelection()
        audio["device_name"] = self.chosen_output()
        audio["input_device"] = self.chosen_microphone()
        audio["block_frames"] = self.BLOCKS[self.block.GetSelection()]
        audio["raw_microphone"] = self.raw_check.GetValue()
        audio["low_latency_monitoring"] = self.low_latency.GetValue()
        self.settings["record_offset_ms"] = record_offset
        self.settings["microphone_offset_ms"] = offset
        for key, measured in self._measured.items():       # every pair measured here, the chosen one last
            if key != self.pair_key():
                remember_offset(self.settings, key, measured)
        if self._offset_source in ("remembered", "measured") or offset != self._shown_offset:
            remember_offset(self.settings, self.pair_key(), offset)          # measured, or typed in by hand
        self.settings.save()
        return audio


class PreferencesDialog(wx.Dialog):
    def __init__(self, parent, settings):
        super().__init__(parent, title="Preferences")
        self.settings = settings
        form = Form(self)
        self.metronome_volume = form.add("Metronome volume (percent)", slider_ctrl,
                                         value=settings["metronome_volume"], min_value=0, max_value=100)
        self.count_in = form.add("Count-in before recording", choice_ctrl,
                                 choices=["Off", "1 bar", "2 bars"], selection=settings["count_in_bars"])
        self.master = form.add("Master volume (percent)", slider_ctrl, value=settings["master_volume"],
                               min_value=0, max_value=150)
        self.note_names = wx.CheckBox(self, label="Speak note names while playing the musical keyboard")
        self.note_names.SetValue(settings["announce_note_names"])
        form.add_wide(self.note_names)
        self.sapi = wx.CheckBox(self, label="Speak with the Windows voice when no screen reader is running")
        self.sapi.SetValue(settings["speak_with_windows_voice"])
        form.add_wide(self.sapi)
        self.say_play = wx.CheckBox(self, label="Announce when playback starts")
        self.say_play.SetValue(settings["announce_play_start"])
        form.add_wide(self.say_play)
        self.say_record = wx.CheckBox(self, label="Announce when recording starts")
        self.say_record.SetValue(settings["announce_record_start"])
        form.add_wide(self.say_record)
        self.say_count = wx.CheckBox(self, label="Announce how many notes were recorded")
        self.say_count.SetValue(settings["announce_recorded_notes"])
        form.add_wide(self.say_count)
        finish_dialog(self, form.grid)
        self.metronome_volume.SetFocus()

    def get_values(self):
        s = self.settings
        s["metronome_volume"] = self.metronome_volume.GetValue()
        s["count_in_bars"] = self.count_in.GetSelection()
        s["master_volume"] = self.master.GetValue()
        s["announce_note_names"] = self.note_names.GetValue()
        s["speak_with_windows_voice"] = self.sapi.GetValue()
        s["announce_play_start"] = self.say_play.GetValue()
        s["announce_record_start"] = self.say_record.GetValue()
        s["announce_recorded_notes"] = self.say_count.GetValue()
        s.save()
        return s


class TextViewDialog(wx.Dialog):
    """Read-only text for help pages: arrow keys read it line by line."""

    def __init__(self, parent, title, text):
        super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        body = wx.BoxSizer(wx.VERTICAL)
        body.Add(wx.StaticText(self, label=title))
        self.text = wx.TextCtrl(self, value=text, size=(620, 420),
                                style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        body.Add(self.text, 1, wx.EXPAND | wx.TOP, 4)
        finish_dialog(self, body, buttons=wx.OK)
        self.text.SetFocus()
        self.text.SetInsertionPoint(0)


def describe_note_length(ticks):
    return describe_length(ticks)


# ----------------------------------------------------------------------
# song sections
# ----------------------------------------------------------------------
class SectionSettingsDialog(wx.Dialog):
    """Name, length in bars and the Automatic switch."""

    def __init__(self, parent, session, index):
        section = session.song.sections[index]
        super().__init__(parent, title="Section settings: {}".format(session.song.section_name(index)))
        self.session = session
        self.index = index
        form = Form(self)
        self.name = form.add("Name (leave empty to use its number)", text_ctrl, value=section.name)
        self.length = form.add("Length in bars", spin_ctrl, min_value=1, max_value=9999, value=section.length)
        self.automatic = wx.CheckBox(self, label="Automatic: grow when I record past the end")
        self.automatic.SetValue(section.automatic)
        form.add_wide(self.automatic)
        finish_dialog(self, form.grid)
        self.length.SetFocus()
        self.length.SelectAll()

    def get_values(self):
        return {"name": self.name.GetValue().strip(), "length": self.length.GetValue(),
                "automatic": self.automatic.GetValue()}


class SectionsDialog(wx.Dialog):
    """Every section of the song, with buttons to arrange them."""

    def __init__(self, parent, session, confirm=None, run_modal=None):
        super().__init__(parent, title="Sections", style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.session = session
        self.confirm = confirm or (lambda message: True)
        self.run_modal = run_modal or (lambda dialog: dialog.ShowModal())
        self.went_to = None
        body = wx.BoxSizer(wx.VERTICAL)
        body.Add(wx.StaticText(self, label="Sections"))
        self.list = wx.ListBox(self, size=(460, 240))
        body.Add(self.list, 1, wx.EXPAND | wx.TOP, 4)
        row = wx.WrapSizer(wx.HORIZONTAL)
        self.buttons = {}
        for key, label in (("go", "&Go to section"), ("add", "&Add section"), ("duplicate", "D&uplicate"),
                           ("earlier", "Move &earlier"), ("later", "Move &later"),
                           ("settings", "Section &settings..."), ("delete", "&Delete"), ("close", "Close")):
            button = wx.Button(self, wx.ID_CANCEL if key == "close" else wx.ID_ANY, label=label)
            self.buttons[key] = button
            row.Add(button, 0, wx.ALL, 3)
        body.Add(row, 0, wx.TOP, 6)
        body.Add(note_text(self, (
            "Enter goes to the selected section. Alt+A adds a section after it, Control+D copies it to the end of the song, "
            "Control+Up and Control+Down move it, F2 opens its settings, Delete removes it and its music. "
            "Sections have no limit.")), 0, wx.TOP, 8)
        finish_dialog(self, body, buttons=0)
        self.SetEscapeId(wx.ID_CANCEL)
        actions = {"go": self.go_to, "add": self.add, "duplicate": self.duplicate, "earlier": lambda: self.move(-1),
                   "later": lambda: self.move(1), "settings": self.settings, "delete": self.delete}
        for key, action in actions.items():
            self.buttons[key].Bind(wx.EVT_BUTTON, lambda e, a=action: self._run(a))
        self.list.Bind(wx.EVT_KEY_DOWN, self.on_key)
        # Enter reaches the list (common.enter_for_lists); Control+Z and Control+Y undo and redo here
        keep_enter_for_lists(self, (self.list, self.on_key), undo=self.undo)
        self.list.Bind(wx.EVT_LISTBOX_DCLICK, lambda e: self._run(self.go_to))
        self.refresh(session.current_section_index())
        self.list.SetFocus()

    def undo(self, redo=False):
        """Control+Z and Control+Y (common.undo_in_list_window)."""
        undo_in_list_window(self, redo, self.refresh)

    @says_after
    def _run(self, action):
        try:
            action()
        except ValueError as exc:
            show_error(self, str(exc))
        self.list.SetFocus()

    def refresh(self, select=0):
        song = self.session.song
        show_items(self.list, ["{}. {}".format(i + 1, song.describe_section(i)) for i in range(len(song.sections))],
                   max(0, min(select, len(song.sections) - 1)))

    def selected(self):
        index = self.list.GetSelection()
        return 0 if index == wx.NOT_FOUND else index

    def go_to(self):
        index = self.selected()
        self.went_to = index
        with self.session.pressed("window"):     # "Section 2, bar 9" once this window has closed (audit B4)
            self.session.go_to_section(index)
        end_dialog(self, wx.ID_OK)

    def add(self):
        self.refresh(self.session.add_section(after_index=self.selected()))

    def duplicate(self):
        self.refresh(self.session.duplicate_section(self.selected()))

    def move(self, delta):
        self.refresh(self.session.move_section(self.selected(), delta))

    def settings(self):
        index = self.selected()
        # one window, shown again after a mistake with everything typed still in it (the review, 23 Oct 2026)
        with SectionSettingsDialog(self, self.session, index) as dlg:
            values = ask_values(self.run_modal, dlg, on_error=lambda words: show_error(self, words))
        if values is None:
            return
        lost = self.session.notes_lost_if_shortened(index, values["length"])
        if lost and not self.confirm("Shortening this section removes {} note{} in its last bars. "
                                     "You can undo this with Control+Z. Continue?".format(
                                         lost, "" if lost == 1 else "s")):
            return
        self.session.update_section(index, **values)
        self.refresh(index)

    def delete(self):
        index = self.selected()
        song = self.session.song
        start, end = song.section_bounds(index)
        from ..arrange import notes_in_bars

        count = notes_in_bars(song, start, end)
        if self.confirm("Delete {} and the {} note{} in it? You can undo this with Control+Z.".format(
                song.section_name(index), count, "" if count == 1 else "s")):
            self.refresh(self.session.delete_section(index))

    def on_key(self, event):
        key = event.GetKeyCode()
        mods = event.GetModifiers()
        plain = mods == wx.MOD_NONE           # each key with exactly its own modifiers: Alt+Enter is not Enter (0.9.7)
        ctrl = mods == wx.MOD_CONTROL
        action = None
        if plain and key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            action = self.go_to
        elif plain and key in (wx.WXK_INSERT, wx.WXK_NUMPAD_INSERT):
            action = self.add
        elif plain and key in (wx.WXK_DELETE, wx.WXK_NUMPAD_DELETE):
            action = self.delete
        elif plain and key == wx.WXK_F2:
            action = self.settings
        elif ctrl and key == ord("D"):
            action = self.duplicate
        elif ctrl and key == wx.WXK_UP:
            action = lambda: self.move(-1)  # noqa: E731
        elif ctrl and key == wx.WXK_DOWN:
            action = lambda: self.move(1)  # noqa: E731
        if action is None:
            event.Skip()
        else:
            self._run(action)
