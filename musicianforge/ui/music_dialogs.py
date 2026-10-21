"""Windows for version 0.8: the chord track, rhythm players (adding one and its editor), and a
region's trim and loop settings.

The same accessibility rules as everywhere in Musician Forge: each control's label is created just
before it, everything is reached with Tab, buttons have keyboard shortcuts (underlined letters),
and every change is spoken or shown in a text box you can read.
"""

import wx

from .. import chords, player_pieces, players, theory
from .. import player_variations as pv
from ..session_music import FOLLOW_CHOICES, FOLLOW_NAMES, HandMadeSteps
from ..timeline import MAX_NUMERATOR
from .common import (DecimalField, Form, ask_values, choice_ctrl, end_dialog, finish_dialog, fit_to_screen, note_text,
                     set_note_text, show_error, show_items, silence_name, slider_ctrl, spin_ctrl)
from .effects_dialogs import percent_label

# the highest beat a beat box takes: the last beat of the longest bar (32/16 time), with decimals; each bar's own
# number of beats is checked when OK is pressed (before 9 Oct 2026 the boxes stopped at 16.99, so a region or chord
# on beat 17 or later of a 21/16 bar could not be changed at all)
LAST_BEAT = MAX_NUMERATOR + 0.99

STEP_CHOICES = [("bar", "One chord per bar"), ("half", "Up to two chords per bar"), ("beat", "Up to one chord per beat")]


def _note_names(flats):
    return list(theory.SPOKEN_FLAT if flats else theory.SPOKEN_SHARP)


def _bar_and_beat(timeline, tick):
    """(bar, beat) rounded to two decimals the way the beat boxes show them (a moment just before a
    barline becomes beat 1 of the next bar, not beat 5 of a 4-beat bar)."""
    bar, beat = timeline.tick_to_position(tick)
    beat = round(beat, 2)
    if beat >= timeline.time_signature_at_bar(bar).numerator + 1:
        bar, beat = bar + 1, 1.0
    return bar, beat


def _tick_from(timeline, bar, beat, what):
    beats = timeline.time_signature_at_bar(int(bar)).numerator
    if not 1.0 <= float(beat) < beats + 1.0:
        raise ValueError("{}: bar {} has {} beats, so the beat must be from 1 to {}".format(what, bar, beats, beats))
    return timeline.position_to_tick(int(bar), float(beat))


def _button_row(dialog, specs):
    """A wrapping row of buttons; specs are (key, label). Returns ({key: button}, sizer)."""
    row = wx.WrapSizer(wx.HORIZONTAL)
    buttons = {}
    for key, label in specs:
        button = wx.Button(dialog, wx.ID_CANCEL if key == "close" else wx.ID_ANY, label=label)
        buttons[key] = button
        row.Add(button, 0, wx.ALL, 3)
    return buttons, row


# ----------------------------------------------------------------------
# the chord track
# ----------------------------------------------------------------------
class ChordTrackDialog(wx.Dialog):
    """Every chord change in the song, in order. Rhythm players play these chords."""

    def __init__(self, parent, session, run_modal=None, confirm=None):
        super().__init__(parent, title="Chord track", style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.session = session
        self.run_modal = run_modal or (lambda dialog: dialog.ShowModal())
        self.confirm = confirm or (lambda message: True)
        body = wx.BoxSizer(wx.VERTICAL)
        body.Add(wx.StaticText(self, label="Chord changes, in song order (each lasts until the next one)"))
        self.list = wx.ListBox(self, size=(520, 220))
        body.Add(self.list, 1, wx.EXPAND | wx.TOP, 4)
        self.buttons, row = _button_row(self, (
            ("add", "&Add chord change..."), ("edit", "&Edit..."), ("delete", "&Delete"),
            ("fill", "&Fill from a progression..."), ("from_track", "&Work out from a track..."),
            ("clear", "C&lear bars..."), ("close", "Close")))
        body.Add(row, 0, wx.TOP, 6)
        body.Add(note_text(self, (
            "Enter edits the selected chord change, Alt+A adds one (Insert too), Delete removes one. Rhythm players for bass, "
            "keys, synth and guitar play these chords. Where the chord track is empty they play the key's own "
            "chord."), width=520), 0, wx.TOP, 8)
        finish_dialog(self, body, buttons=0)
        self.SetEscapeId(wx.ID_CANCEL)
        actions = {"add": self.add, "edit": self.edit, "delete": self.delete, "fill": self.fill,
                   "from_track": self.from_track, "clear": self.clear}
        for key, action in actions.items():
            self.buttons[key].Bind(wx.EVT_BUTTON, lambda e, a=action: self._run(a))
        self.list.Bind(wx.EVT_KEY_DOWN, self.on_key)
        self.list.Bind(wx.EVT_LISTBOX_DCLICK, lambda e: self._run(self.edit))
        self.refresh(self._index_at_playhead())
        self.list.SetFocus()

    def _index_at_playhead(self):
        tick = self.session.position_tick()
        index = 0
        for i, change in enumerate(self.session.song.chords):
            if change.tick <= tick:
                index = i
        return index

    def _run(self, action):
        try:
            action()
        except ValueError as exc:
            show_error(self, str(exc))
        self.list.SetFocus()

    def refresh(self, select=0):
        count = len(self.session.song.chords)
        if count:
            self.list.Set([self.session.describe_chord(i) for i in range(count)])
            self.list.SetSelection(max(0, min(select, count - 1)))
        else:
            self.list.Set(["No chord changes yet. Press Alt+A to add one, or Fill from a progression."])
            self.list.SetSelection(0)
        for key in ("edit", "delete"):
            self.buttons[key].Enable(bool(count))

    def selected(self):
        if not self.session.song.chords:
            return None
        index = self.list.GetSelection()
        return 0 if index == wx.NOT_FOUND else index

    def add(self):
        with ChordDialog(self, self.session, tick=self.session.position_tick()) as dlg:
            values = ask_values(self.run_modal, dlg)
        if values is not None:
            self.refresh(self.session.set_chord(*values))

    def edit(self):
        index = self.selected()
        if index is None:
            return self.add()
        change = self.session.song.chords[index]
        with ChordDialog(self, self.session, change=change, title="Edit chord change") as dlg:
            values = ask_values(self.run_modal, dlg)
        if values is not None:
            self.refresh(self.session.set_chord(*values, replacing=index))

    def delete(self):
        index = self.selected()
        if index is not None:
            self.session.remove_chord(index)
            self.refresh(index)

    def _span_defaults(self):
        start, end = self.session.song.section_bounds(self.session.current_section_index())
        return start, end - 1

    def fill(self):
        start, last = self._span_defaults()
        with FillChordsDialog(self, start, last) as dlg:
            values = ask_values(self.run_modal, dlg)
        if values is None:
            return
        progression, first, final, per_chord, sevenths = values
        if self._chords_between(first, final) and not self.confirm(
                "Bars {} to {} already have chord changes. Replace them? You can undo this with Control+Z.".format(
                    first, final)):
            return
        self.session.fill_chords(progression, first, final + 1, per_chord, sevenths)
        self.refresh(self._first_index_from(first))

    def from_track(self):
        candidates = [t for t in self.session.song.tracks if not t.is_audio and not t.instrument.is_drum_kit]
        if not candidates:
            raise ValueError("There is no instrument track to work chords out from")
        start, last = self._span_defaults()
        selected = self.session.selected_track_id
        with ChordsFromTrackDialog(self, candidates, selected, start, last) as dlg:
            values = ask_values(self.run_modal, dlg)
        if values is None:
            return
        track_id, first, final, step = values
        self.session.chords_from_track(track_id, first, final + 1, step)
        self.refresh(self._first_index_from(first))

    def clear(self):
        start, last = self._span_defaults()
        with BarRangeDialog(self, "Clear chord changes", start, last) as dlg:
            values = ask_values(self.run_modal, dlg)
        if values is None:
            return
        first, final = values
        self.session.clear_chords(first, final + 1)
        self.refresh(self._first_index_from(first))

    def _chords_between(self, first, final):
        tl = self.session.song.timeline
        t0, t1 = tl.bar_to_tick(first), tl.bar_to_tick(final + 1)
        return [c for c in self.session.song.chords if t0 <= c.tick < t1]

    def _first_index_from(self, bar):
        tick = self.session.song.timeline.bar_to_tick(bar)
        for i, change in enumerate(self.session.song.chords):
            if change.tick >= tick:
                return i
        return max(0, len(self.session.song.chords) - 1)

    def on_key(self, event):
        key = event.GetKeyCode()
        action = None
        if event.GetModifiers() == wx.MOD_NONE:
            action = {wx.WXK_RETURN: self.edit, wx.WXK_NUMPAD_ENTER: self.edit, wx.WXK_INSERT: self.add,
                      wx.WXK_NUMPAD_INSERT: self.add, wx.WXK_DELETE: self.delete,
                      wx.WXK_NUMPAD_DELETE: self.delete}.get(key)
        if action is None:
            event.Skip()
        else:
            self._run(action)


class ChordDialog(wx.Dialog):
    """One chord change: where it starts, its root, its type, and (if different) its bass note."""

    def __init__(self, parent, session, change=None, tick=0, title="Add chord change"):
        super().__init__(parent, title=title)
        self.session = session
        tl = session.song.timeline
        tick = change.tick if change is not None else tick
        bar, beat = _bar_and_beat(tl, tick)
        key = tl.key_at_tick(tick)
        flats = theory.key_prefers_flats(key.tonic, key.scale)
        self.flats = flats
        names = _note_names(flats)
        root = change.root if change is not None else key.tonic % 12
        tonic_chord = theory.diatonic_chords(key.tonic, key.scale)[0]
        quality = change.quality if change is not None else chords.quality_of(tonic_chord.intervals)
        bass = change.bass if change is not None else None
        form = Form(self)
        self.bar = form.add("Starts at bar", spin_ctrl, min_value=1, max_value=9999, value=bar)
        self.beat = form.add("Beat", DecimalField, min_value=1, max_value=LAST_BEAT, value=beat, step=1, decimals=2)
        self.root = form.add("Root note", choice_ctrl, choices=names, selection=root)
        self.quality = form.add("Chord type", choice_ctrl,
                                choices=["{}, written {}".format(q[1], q[2]) if q[2] else q[1]
                                         for q in chords.QUALITIES],
                                selection=chords.QUALITY_KEYS.index(quality))
        self.bass = form.add("Bass note", choice_ctrl, choices=["Same as the root"] + names,
                             selection=0 if bass is None else bass + 1)
        self.preview = form.add("Chord", wx.TextCtrl, value="", style=wx.TE_READONLY)
        finish_dialog(self, form.grid)
        for control in (self.root, self.quality, self.bass):
            control.Bind(wx.EVT_CHOICE, lambda e: self.update_preview())
        self.update_preview()
        self.root.SetFocus()

    def update_preview(self):
        try:
            _bar, _beat, root, quality, bass = self.get_values(check=False)
        except ValueError:
            return
        change = chords.ChordChange(0, root, quality, bass)
        notes = sorted(change.pitch_classes(), key=lambda pc: (pc - change.bass_class()) % 12)
        names = _note_names(self.flats)
        self.preview.SetValue("{}: {}".format(chords.name(change, self.flats), ", ".join(names[n] for n in notes)))

    def get_values(self, check=True):
        """(bar, beat, root, quality, bass or None); raises ValueError for a bad bar or beat."""
        bar = self.bar.GetValue() if check else 1
        beat = self.beat.GetValue() if check else 1
        if check:
            _tick_from(self.session.song.timeline, bar, beat, "Starts at")
        bass = self.bass.GetSelection() - 1
        return (bar, beat, self.root.GetSelection(), chords.QUALITY_KEYS[max(0, self.quality.GetSelection())],
                None if bass < 0 or bass == self.root.GetSelection() else bass)


class ChordStripsDialog(wx.Dialog):
    """Your own chord strips (Russell, 10 Oct 2026: make the chord strips customizable): the eight chords the keys
    A to K play in the Chord strips layout. Enter changes one, Space plays it, and Use the key's chords goes back to
    the song key's own chords. Every change is one undo step and is saved with the project."""

    def __init__(self, parent, session, run_modal=None):
        super().__init__(parent, title="Chord strips", style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.session = session
        self.run_modal = run_modal or (lambda dialog: dialog.ShowModal())
        body = wx.BoxSizer(wx.VERTICAL)
        body.Add(wx.StaticText(self, label="Chord strips (Enter changes one, Space plays it)"))
        self.list = wx.ListBox(self, size=(460, 170))
        body.Add(self.list, 1, wx.EXPAND | wx.TOP, 4)
        self.buttons, row = _button_row(self, (
            ("edit", "&Change chord..."), ("play", "&Play"), ("reset", "&Use the key's chords"), ("close", "Close")))
        body.Add(row, 0, wx.TOP, 6)
        self.note = note_text(self, "", width=460)
        body.Add(self.note, 0, wx.TOP, 8)
        finish_dialog(self, body, buttons=0)
        self.SetEscapeId(wx.ID_CANCEL)
        for key, action in (("edit", self.edit), ("play", self.play), ("reset", self.reset)):
            self.buttons[key].Bind(wx.EVT_BUTTON, lambda e, a=action: self._run(a))
        self.list.Bind(wx.EVT_KEY_DOWN, self.on_key)
        self.list.Bind(wx.EVT_LISTBOX_DCLICK, lambda e: self._run(self.edit))
        self.Bind(wx.EVT_CHAR_HOOK, self.on_char_hook)
        self.refresh(0)
        self.list.SetFocus()

    def refresh(self, select=None):
        here = self.list.GetSelection() if select is None else select
        items = [self.session.chord_strip_words(i) for i in range(8)]
        if [self.list.GetString(i) for i in range(self.list.GetCount())] != items:
            self.list.Set(items)
        self.list.SetSelection(max(0, min(7, here if here != wx.NOT_FOUND else 0)))
        own = bool(self.session.song.strips)
        self.buttons["reset"].Enable(own)
        set_note_text(self.note, "These are your own chords; they stay as they are when the key changes. Number keys 1 "
                                 "to 8 play their bass notes." if own else
                                 "These are the song key's chords; they follow key changes. Change one to make them "
                                 "your own. Number keys 1 to 8 play their bass notes.", width=460)

    def _run(self, action):
        try:
            action()
        except ValueError as exc:
            show_error(self, str(exc))
        self.refresh()
        self.list.SetFocus()

    def selected(self):
        index = self.list.GetSelection()
        return 0 if index == wx.NOT_FOUND else index

    def edit(self):
        index = self.selected()
        root, quality, bass = self.session.chord_strip_entries()[index]
        with ChordStripDialog(self, self.session, index, root, quality, bass) as dlg:
            values = ask_values(self.run_modal, dlg)
        if values is not None:
            self.session.set_chord_strip(index, *values)

    def play(self):
        self.session.preview_chord_strip(self.selected())

    def reset(self):
        self.session.reset_chord_strips()

    def on_key(self, event):
        key = event.GetKeyCode()
        if event.GetModifiers() == wx.MOD_NONE and key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._run(self.edit)
        elif event.GetModifiers() == wx.MOD_NONE and key == wx.WXK_SPACE:
            self._run(self.play)
        else:
            event.Skip()

    def on_char_hook(self, event):
        """Enter in the list, taken before Windows can treat it as the default button; Control+Z and Control+Y."""
        key, mods = event.GetKeyCode(), event.GetModifiers()
        if mods == wx.MOD_NONE and key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER) and wx.Window.FindFocus() is self.list:
            self._run(self.edit)
            return
        if mods == wx.MOD_CONTROL and key in (ord("Z"), ord("Y")):
            if key == ord("Z"):
                self.session.undo()
            else:
                self.session.redo()
            self.refresh()
            return
        event.Skip()


class ChordStripDialog(wx.Dialog):
    """One chord strip: its root, its chord type and (if different) its bass note."""

    def __init__(self, parent, session, index, root, quality, bass):
        from ..keyboard_map import CHORD_KEYS

        super().__init__(parent, title="Chord strip {}, the {} key".format(index + 1, CHORD_KEYS[index].upper()))
        key = session.current_key()
        self.flats = theory.key_prefers_flats(key.tonic, key.scale)
        names = _note_names(self.flats)
        form = Form(self)
        self.root = form.add("Root note", choice_ctrl, choices=names, selection=root % 12)
        self.quality = form.add("Chord type", choice_ctrl,
                                choices=["{}, written {}".format(q[1], q[2]) if q[2] else q[1]
                                         for q in chords.QUALITIES],
                                selection=chords.QUALITY_KEYS.index(quality) if quality in chords.QUALITY_KEYS else 0)
        self.bass = form.add("Bass note", choice_ctrl, choices=["Same as the root"] + names,
                             selection=0 if bass is None else bass % 12 + 1)
        self.preview = form.add("Chord", wx.TextCtrl, value="", style=wx.TE_READONLY)
        finish_dialog(self, form.grid)
        for control in (self.root, self.quality, self.bass):
            control.Bind(wx.EVT_CHOICE, lambda e: self.update_preview())
        self.update_preview()
        self.root.SetFocus()

    def update_preview(self):
        root, quality, bass = self.get_values()
        change = chords.ChordChange(0, root, quality, bass)
        notes = sorted(change.pitch_classes(), key=lambda pc: (pc - change.bass_class()) % 12)
        names = _note_names(self.flats)
        self.preview.SetValue("{}: {}".format(chords.name(change, self.flats), ", ".join(names[n] for n in notes)))

    def get_values(self):
        """(root, chord type, bass or None)."""
        bass = self.bass.GetSelection() - 1
        root = max(0, self.root.GetSelection())
        return root, chords.QUALITY_KEYS[max(0, self.quality.GetSelection())], None if bass < 0 or bass == root else bass


class BarRangeDialog(wx.Dialog):
    def __init__(self, parent, title, first=1, last=4, extra=None):
        super().__init__(parent, title=title)
        form = Form(self)
        if extra:
            extra(form)
        self.first = form.add("From bar", spin_ctrl, min_value=1, max_value=9999, value=first)
        self.last = form.add("To bar (included)", spin_ctrl, min_value=1, max_value=9999, value=last)
        self.after_range(form)
        finish_dialog(self, form.grid)
        self.focus_first()

    def after_range(self, form):
        pass

    def focus_first(self):
        self.first.SetFocus()

    def bar_range(self):
        first, last = self.first.GetValue(), self.last.GetValue()
        if last < first:
            raise ValueError("The last bar must be the same as the first bar or later")
        return first, last

    def get_values(self):
        return self.bar_range()


class FillChordsDialog(BarRangeDialog):
    """Fill bars with a common progression, built from the song's key in each bar."""

    def __init__(self, parent, first=1, last=4):
        def extra(form):
            self.progression = form.add("Progression", choice_ctrl, choices=[p[0] for p in chords.PROGRESSIONS],
                                        selection=0)
        super().__init__(parent, "Fill the chord track from a progression", first, last, extra)

    def after_range(self, form):
        self.per_chord = form.add("Bars for each chord", choice_ctrl,
                                  choices=["1 bar", "2 bars", "4 bars"], selection=0)
        self.sevenths = wx.CheckBox(self, label="Use seventh chords")
        form.add_wide(self.sevenths)

    def focus_first(self):
        self.progression.SetFocus()

    def get_values(self):
        first, last = self.bar_range()
        per = (1, 2, 4)[max(0, self.per_chord.GetSelection())]
        return self.progression.GetSelection(), first, last, per, self.sevenths.GetValue()


class ChordsFromTrackDialog(BarRangeDialog):
    """Work the chord track out from a track's notes (for example chord strips you played)."""

    def __init__(self, parent, tracks, selected_id, first=1, last=4):
        self.tracks = list(tracks)
        ids = [t.id for t in self.tracks]

        def extra(form):
            self.track = form.add("Track to listen to", choice_ctrl,
                                  choices=["{}, {}".format(t.name, t.instrument.name) for t in self.tracks],
                                  selection=ids.index(selected_id) if selected_id in ids else 0)
        super().__init__(parent, "Work out chords from a track", first, last, extra)

    def after_range(self, form):
        self.step = form.add("How often the chord can change", choice_ctrl, choices=[s[1] for s in STEP_CHOICES],
                             selection=0)

    def focus_first(self):
        self.track.SetFocus()

    def get_values(self):
        first, last = self.bar_range()
        return (self.tracks[max(0, self.track.GetSelection())].id, first, last,
                STEP_CHOICES[max(0, self.step.GetSelection())][0])


# ----------------------------------------------------------------------
# rhythm players
# ----------------------------------------------------------------------
class NewPlayerDialog(wx.Dialog):
    """Choose a rhythm player, its style, where it goes and how long it plays."""

    def __init__(self, parent, session):
        super().__init__(parent, title="New rhythm player")
        self.session = session
        self.order = [players.PLAYERS[k] for k in players.PLAYER_ORDER]
        form = Form(self)
        self.player = form.add("Player", choice_ctrl, choices=[p.title for p in self.order], selection=0)
        self.style = form.add("Style", choice_ctrl, choices=[])
        self.about = form.add("About this style", wx.TextCtrl, value="", style=wx.TE_READONLY | wx.TE_MULTILINE,
                              size=(-1, 60))
        track = session.song.track_by_id(session.selected_track_id)
        self.track_id = track.id if track is not None and not track.is_audio else None
        places = ["On a new track"]
        if self.track_id is not None:
            places.append("On the selected track, {} (replaces what is there)".format(track.name))
        self.place = form.add("Where", choice_ctrl, choices=places, selection=0)
        index = session.current_section_index()
        start, end = session.song.section_bounds(index)
        self.section_span = (start, end - 1)
        self.song_span = (1, session.song.end_bar() - 1)
        self.span = form.add("How long", choice_ctrl, choices=[
            "The section the playhead is in: {}, bars {} to {}".format(session.song.section_name(index), start,
                                                                       end - 1),
            "The whole song, bars 1 to {}".format(self.song_span[1]), "Bars I choose"], selection=0)
        self.first = form.add("From bar", spin_ctrl, min_value=1, max_value=9999, value=start)
        self.last = form.add("To bar (included)", spin_ctrl, min_value=1, max_value=9999, value=end - 1)
        finish_dialog(self, form.grid)
        self.player.Bind(wx.EVT_CHOICE, lambda e: self.on_player())
        self.style.Bind(wx.EVT_CHOICE, lambda e: self.on_style())
        self.span.Bind(wx.EVT_CHOICE, lambda e: self.on_span())
        self.on_player()
        self.on_span()
        self.player.SetFocus()

    def chosen_player(self):
        return self.order[max(0, self.player.GetSelection())]

    def on_player(self):
        player = self.chosen_player()
        self.style.Set([players.style_label(player, s) for s in player.styles])
        self.style.SetSelection(0)
        self.on_style()

    def on_style(self):
        player = self.chosen_player()
        style = player.styles[max(0, self.style.GetSelection())]
        patch = self.session.player_patch(player.key, style.key)
        self.about.SetValue("{} Patch: {}.".format(style.description, patch[2]))

    def on_span(self):
        choice = self.span.GetSelection()
        custom = choice == 2
        self.first.Enable(custom)
        self.last.Enable(custom)
        if not custom:
            first, last = self.section_span if choice == 0 else self.song_span
            self.first.SetValue(first)
            self.last.SetValue(last)

    def get_values(self):
        """{player, style, track_id (None for a new track), start_tick, end_tick}."""
        player = self.chosen_player()
        first, last = self.first.GetValue(), self.last.GetValue()
        if last < first:
            raise ValueError("The last bar must be the same as the first bar or later")
        tl = self.session.song.timeline
        return {"player": player.key, "style": player.styles[max(0, self.style.GetSelection())].key,
                "track_id": self.track_id if self.place.GetSelection() == 1 else None,
                "start_tick": tl.bar_to_tick(first), "end_tick": tl.bar_to_tick(last + 1)}


SLIDERS = (("intensity", "Intensity (how hard it plays: softer or heavier, never more notes)"),
           ("complexity", "Complexity (how busy: how many notes, extra notes and variations)"),
           ("fills", "Fill amount (0 none, from 1 every 8th bar, 40 every 4th, 70 every 2nd, 100 every bar)"),
           ("fill_complexity", "Fill complexity (how big each fill is: from a short pickup up to a whole bar)"),
           ("swing", "Swing (0 is straight; more delays every second eighth or sixteenth)"))


def _player_region_index(session, track_id, start):
    """Where the rhythm player region that starts at `start` is now in its track's list (an undo can move it), or
    None if it is gone."""
    track = session.song.track_by_id(track_id)
    if track is None or track.is_audio:
        return None
    for index, region in enumerate(track.note_regions):
        if region.player and region.start == start:
            return index
    return None


def ask_change_variation(parent, message):
    """The warning before hand-made steps are reset (Russell, 8 Oct 2026, 11:57 PM): Change or Cancel. Cancel is the
    default button, and Escape cancels."""
    dlg = wx.MessageDialog(parent, message, "Change the variation?",
                           wx.OK | wx.CANCEL | wx.CANCEL_DEFAULT | wx.ICON_WARNING)
    try:
        dlg.SetOKCancelLabels("&Change", "Cancel")
        return dlg.ShowModal() == wx.ID_OK
    finally:
        dlg.Destroy()


class PlayerEditorDialog(wx.Dialog):
    """A rhythm player region: every setting changes the performance at once (Control+Z undoes it).

    Variation chooses the groove or part itself (Previous and Next variation step through them); Reforge
    (Control+R) plays a new performance of the same variation: new fills and details. The Kit pieces list (for
    bass, keys, synth and guitar, the part) opens each piece's own settings and its step pattern."""

    def __init__(self, parent, session, track_id, index, run_modal=None, confirm=None, warn=None, together=1):
        self.session = session
        self.track_id = track_id
        self.index = index
        self.run_modal = run_modal or (lambda dialog: dialog.ShowModal())
        self.confirm = confirm or (lambda message: True)
        self.warn = warn or (lambda message: ask_change_variation(self, message))
        settings = session.player_settings(track_id, index)
        self.player = players.PLAYERS[settings["player"]]
        track = session.song.track_by_id(track_id)
        self.region_start = track.note_regions[index].start
        title = "{} on {}".format(self.player.title, track.name)
        if together > 1:
            title += ", {} regions together".format(together)     # every change goes to all of them
        super().__init__(parent, title=title)
        self._filling = False
        self.piece_keys = []
        drums = self.player.key == "anvil"
        # The settings scroll, and the buttons stay below them, always in sight: the drummer's editor was
        # 1,077 pixels tall, taller than Russell's screen, so its note was out of sight (Check Accessibility,
        # 9 Oct 2026); at 125 or 150 percent scaling more of it would be. Every label and its control share the
        # scrolling panel, created in order, so screen readers name them as before; the focused control scrolls
        # into sight by itself.
        body = wx.ScrolledWindow(self, style=wx.VSCROLL | wx.TAB_TRAVERSAL)
        body.SetScrollRate(0, 20)
        silence_name(body)
        self.body = body
        form = Form(body)
        self.summary = form.add("Summary", wx.TextCtrl, value="", style=wx.TE_READONLY | wx.TE_MULTILINE,
                                size=(460, 60))
        self.style = form.add("Style", choice_ctrl,
                              choices=[players.style_label(self.player, s) for s in self.player.styles])
        self.variation = form.add("Variation (the groove itself; Reforge keeps it)", choice_ctrl, choices=[])
        self.previous_variation = wx.Button(body, label="Pre&vious variation")
        form.add_wide(self.previous_variation)
        self.next_variation = wx.Button(body, label="Ne&xt variation")
        form.add_wide(self.next_variation)
        self.patch = wx.Button(body, label="&Patch...")
        form.add_wide(self.patch)
        self.sliders = {}
        for key, label in SLIDERS:
            self.sliders[key] = form.add(percent_label(label), slider_ctrl, value=settings.get(key, 50))
        self.swing_note = form.add("Swing feel (which notes swing)", choice_ctrl,
                                   choices=[players.SWING_NOTE_NAMES[n] for n in players.SWING_NOTES])
        self.follow = form.add("Follow", choice_ctrl, choices=[FOLLOW_NAMES[c] for c in FOLLOW_CHOICES])
        self.follow_track = form.add("Track to follow", choice_ctrl, choices=[])
        self.sliders["follow_amount"] = form.add(percent_label(
            "Follow amount (how closely it locks to the followed track)"), slider_ctrl, value=settings["follow_amount"])
        self.sliders["sensitivity"] = form.add(percent_label(
            "Hit sensitivity (for a recording: more finds quieter hits)"), slider_ctrl, value=settings["sensitivity"])
        self.pieces = form.add("Kit pieces (Space turns one on or off; Enter opens its settings)" if drums else
                               "The part (Enter opens its settings and its step pattern)", wx.ListBox, choices=[],
                               size=(460, 120 if drums else 40))
        self.piece_button = wx.Button(body, label="P&iece settings...")
        form.add_wide(self.piece_button)
        self.play_after = wx.CheckBox(body, label="Play the region after Reforge")
        form.add_wide(self.play_after)
        form.add_wide(note_text(body, (
            "Every change is heard straight away and is one undo step: Control+Z and Control+Y work here. "
            "Reforge plays a new performance of the same variation: new fills and small details.")))
        inner = wx.BoxSizer(wx.VERTICAL)
        inner.Add(form.grid, 0, wx.EXPAND | wx.RIGHT, 16)   # room for the scroll bar
        body.SetSizer(inner)
        self.buttons, row = _button_row(self, (
            ("reforge", "&Reforge (Control+R)"), ("say", "&Say the summary"), ("play", "Play the re&gion"),
            ("notes", "&Turn into notes..."), ("close", "Close")))
        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(body, 1, wx.EXPAND)
        outer.Add(row, 0, wx.TOP, 6)
        content = inner.GetMinSize()
        body.SetMinSize(content)                 # first as tall as all its settings ...
        finish_dialog(self, outer, buttons=0)
        # ... then allowed to be shorter, scrolling. Its minimum height is set, not left to wx: left unset, wx takes
        # the settings' full height as the minimum, and its scrolling for windows larger than the screen
        # (app.allow_scrolling_dialogs) would put this already scrolling window inside another one.
        body.SetMinSize((content.width, self.FromDIP(200)))
        self.SetLayoutAdaptationMode(wx.DIALOG_ADAPTATION_MODE_DISABLED)   # it scrolls by itself
        self.SetMinSize(wx.DefaultSize)
        fit_to_screen(self)                      # when the screen is not tall enough
        self.Layout()
        body.FitInside()
        self.SetEscapeId(wx.ID_CANCEL)
        self.style.Bind(wx.EVT_CHOICE, lambda e: self.on_style())
        # the Variation list is read by the screen reader as it changes, so nothing more is said (Russell, 10 Oct 2026)
        self.variation.Bind(wx.EVT_CHOICE, lambda e: self._run(lambda: self.go_to_variation(
            self.variation.GetSelection() + 1, speak=False)))
        self.previous_variation.Bind(wx.EVT_BUTTON, lambda e: self._run(lambda: self.step_variation(-1)))
        self.next_variation.Bind(wx.EVT_BUTTON, lambda e: self._run(lambda: self.step_variation(1)))
        self.patch.Bind(wx.EVT_BUTTON, lambda e: self._run(self.choose_patch))
        for key, slider in self.sliders.items():
            slider.Bind(wx.EVT_SLIDER, lambda e, k=key: self.change(**{k: self.sliders[k].GetValue()}))
        self.swing_note.Bind(wx.EVT_CHOICE, lambda e: self.change(
            swing_note=players.SWING_NOTES[max(0, self.swing_note.GetSelection())]))
        self.follow.Bind(wx.EVT_CHOICE, lambda e: self._run(self.on_follow))
        self.follow_track.Bind(wx.EVT_CHOICE, lambda e: self._run(self.on_follow_track))
        self.play_after.Bind(wx.EVT_CHECKBOX, lambda e: self.change(play_after_reforge=self.play_after.GetValue()))
        self.pieces.Bind(wx.EVT_KEY_DOWN, self.on_pieces_key)
        self.pieces.Bind(wx.EVT_LISTBOX_DCLICK, lambda e: self._run(self.open_piece))
        self.piece_button.Bind(wx.EVT_BUTTON, lambda e: self._run(self.open_piece))
        actions = {"reforge": self.reforge, "say": self.say, "play": self.play, "notes": self.turn_into_notes}
        for key, action in actions.items():
            self.buttons[key].Bind(wx.EVT_BUTTON, lambda e, a=action: self._run(a))
        self.Bind(wx.EVT_CHAR_HOOK, self.on_char_hook)
        self._closed = False
        self.fill()
        self.style.SetFocus()

    # -- reading the region back --------------------------------------------
    def settings(self):
        return self.session.player_settings(self.track_id, self.index)

    def fill(self):
        """Show the region's settings (after opening, undo, redo or a style change)."""
        settings = self.settings()
        self._filling = True
        try:
            keys = [s.key for s in self.player.styles]
            self.style.SetSelection(keys.index(settings["style"]) if settings["style"] in keys else 0)
            names = ["{}: {}".format(n, pv.description(settings["player"], settings["style"], n))
                     for n in range(1, players.variation_count(settings) + 1)]
            if [self.variation.GetString(i) for i in range(self.variation.GetCount())] != names:
                self.variation.Set(names)
            self.variation.SetSelection(settings["variation"] - 1)
            for key, slider in self.sliders.items():
                if slider.GetValue() != settings[key]:
                    slider.SetValue(settings[key])
            self.swing_note.SetSelection(players.SWING_NOTES.index(settings["swing_note"]))
            self.follow.SetSelection(FOLLOW_CHOICES.index(settings["follow"]))
            self.candidates = self.session.follow_candidates(self.track_id, self.index)
            if self.candidates:
                self.follow_track.Set([label for _id, label in self.candidates])
                ids = [c[0] for c in self.candidates]
                self.follow_track.SetSelection(ids.index(settings["follow_track"])
                                               if settings["follow_track"] in ids else 0)
            else:
                self.follow_track.Set(["No other track has notes or a recording in this region"])
                self.follow_track.SetSelection(0)
            following = settings["follow"] == "track"
            self.follow_track.Enable(following and bool(self.candidates))
            self.sliders["follow_amount"].Enable(following)
            fills_here = players.has_fills(settings)          # a simple pad has none (Russell, 10 Oct 2026)
            self.sliders["fills"].Enable(fills_here)
            self.sliders["fill_complexity"].Enable(fills_here)
            followed = self.session.song.track_by_id(settings.get("follow_track"))
            self.sliders["sensitivity"].Enable(following and followed is not None and followed.is_audio)
            lines = self.session.describe_pieces(self.track_id, self.index)
            self.piece_keys = [key for key, _words in lines]
            here = max(0, self.pieces.GetSelection())
            show_items(self.pieces, [words for _key, words in lines], min(here, len(lines) - 1))
            self.play_after.SetValue(settings.get("play_after_reforge", True))
            track = self.session.song.track_by_id(self.track_id)
            self.patch.SetLabel("&Patch: {}...".format(track.instrument.name))
            self.summary.SetValue(self.session.player_summary(self.track_id, self.index))
        finally:
            self._filling = False

    def _still_there(self):
        """True if this editor's region is still a rhythm player region (found again by where it
        starts, in case an undo moved it in the list)."""
        index = _player_region_index(self.session, self.track_id, self.region_start)
        if index is None:
            return False
        self.index = index
        return True

    def _run(self, action):
        try:
            action()
        except ValueError as exc:
            show_error(self, str(exc))
        if self._closed:
            return
        if self._still_there():
            self.fill()
        else:          # an undo in a window opened from here took the region away
            self._close("This region is no longer a rhythm player, so the editor closed")

    def _close(self, words=None, code=wx.ID_CANCEL):
        self._closed = True
        if words:
            self.session.announce(words)
        end_dialog(self, code)

    # -- changes ---------------------------------------------------------------
    def change(self, **changes):
        if self._filling:
            return
        try:
            self.session.update_player(self.track_id, self.index, speak=False, **changes)
        except ValueError as exc:
            show_error(self, str(exc))
        self.fill()

    def on_style(self):
        """A new style; if it has fewer variations than the one chosen, it starts again at variation 1, and says so."""
        if self._filling:
            return
        before = self.settings()["variation"]
        self.change(style=self.player.styles[self.style.GetSelection()].key)
        settings = self.settings()
        if settings["variation"] != before:
            self.session.announce("This style has {} variations, so it is on variation 1".format(
                players.variation_count(settings)))

    def go_to_variation(self, number, speak=True):
        """Another variation; with hand-made steps, the warning first (Cancel keeps everything as it was). Previous
        and Next variation say "Variation 3 of 6"; the Variation list says nothing more than its own item."""
        if self._filling or number == self.settings()["variation"]:
            return
        try:
            self.session.set_variation(self.track_id, self.index, number, speak=speak)
        except HandMadeSteps as warning:
            if self.warn(str(warning)):
                self.session.set_variation(self.track_id, self.index, number, reset_steps=True, speak=speak)
            else:
                self.session.announce("Cancelled. Still {}".format(self.session.variation_words(self.settings())))

    def step_variation(self, step):
        settings = self.settings()
        target = settings["variation"] + step
        if not 1 <= target <= players.variation_count(settings):
            self.session.next_variation(self.track_id, self.index, step)    # says it is the first or the last
            return
        self.go_to_variation(target)

    def choose_patch(self):
        from .dialogs import InstrumentDialog

        track = self.session.song.track_by_id(self.track_id)
        with InstrumentDialog(self, self.session, track.instrument) as dlg:
            if self.run_modal(dlg) != wx.ID_OK:
                return
            preset = dlg.get_preset()
        if preset is not None:
            self.session.set_player_patch(self.track_id, preset)

    def on_follow(self):
        if self._filling:
            return
        choice = FOLLOW_CHOICES[max(0, self.follow.GetSelection())]
        if choice == "track":
            candidates = self.session.follow_candidates(self.track_id, self.index)
            if not candidates:
                raise ValueError("No other track has notes or a recording in this region yet, so there is nothing "
                                 "to follow. Record or add one first.")
            current = self.settings().get("follow_track")
            target = current if current in [c[0] for c in candidates] else candidates[0][0]
            self.session.update_player(self.track_id, self.index, speak=False, follow="track", follow_track=target)
        else:
            # the Follow list is read by the screen reader; the whole summary on top was too much (10 Oct 2026)
            self.session.update_player(self.track_id, self.index, speak=False, follow=choice)

    def on_follow_track(self):
        if self._filling or not self.candidates:
            return
        target = self.candidates[max(0, self.follow_track.GetSelection())][0]
        self.session.update_player(self.track_id, self.index, speak=False, follow="track", follow_track=target)

    # -- the pieces ------------------------------------------------------------
    def selected_piece(self):
        here = self.pieces.GetSelection()
        return self.piece_keys[here] if 0 <= here < len(self.piece_keys) else None

    def on_pieces_key(self, event):
        key = event.GetKeyCode()
        if event.GetModifiers() == wx.MOD_NONE and key == wx.WXK_SPACE:
            self._run(self.toggle_piece)
            return
        if event.GetModifiers() == wx.MOD_NONE and key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._run(self.open_piece)
            return
        event.Skip()

    def toggle_piece(self):
        piece = self.selected_piece()
        if piece is None:
            return
        if piece == "part":
            self.session.announce("The part cannot be turned off; mute the region instead (M in the Regions list)")
            return
        on = not self.session.piece_settings(self.track_id, self.index, piece)["on"]
        self.session.update_piece(self.track_id, self.index, piece, speak=False, on=on)
        self.fill()
        name = player_pieces.PIECE_BY_KEY[piece].name
        self.session.announce("{} {}".format(name, "on" if on else "off"))      # short (Russell, 10 Oct 2026)

    def open_piece(self):
        piece = self.selected_piece()
        if piece is None:
            return
        with PieceSettingsDialog(self, self.session, self.track_id, self.index, piece, run_modal=self.run_modal) as dlg:
            self.run_modal(dlg)
        self.pieces.SetFocus()

    # -- Reforge and the rest -------------------------------------------------
    def reforge(self):
        self.session.reforge(self.track_id, self.index)

    def say(self):
        self.session.announce(self.session.player_summary(self.track_id, self.index))

    def play(self):
        self.session.play_note_region(self.track_id, self.index)

    def turn_into_notes(self):
        if not self.confirm("Turn this rhythm player region into ordinary notes you can edit? Its settings and "
                            "Reforge go away; Control+Z brings them back."):
            return
        self.session.turn_into_notes(self.track_id, self.index)
        self._close(code=wx.ID_OK)

    def undo(self, redo=False):
        (self.session.redo if redo else self.session.undo)()
        if self._still_there():
            self.fill()
        else:
            self._close("This region is no longer a rhythm player, so the editor closed")

    def on_char_hook(self, event):
        key = event.GetKeyCode()
        if event.GetModifiers() == wx.MOD_CONTROL:
            if key == ord("R"):
                self._run(self.reforge)
                return
            if key in (ord("Z"), ord("Y")):
                self.undo(redo=key == ord("Y"))
                return
        event.Skip()


OCTAVE_CHOICES = [(-2, "Two octaves down"), (-1, "One octave down"), (0, "As the style plays it"),
                  (1, "One octave up"), (2, "Two octaves up")]


class _RegionWindow:
    """For the windows opened from the rhythm player editor: they find their region again after an undo or redo
    (by where it starts, as the editor does), and close, saying so, if it is gone."""

    def _still_there(self):
        index = _player_region_index(self.session, self.track_id, self.region_start)
        if index is None:
            return False
        self.index = index
        return True

    def _close_if_gone(self):
        """True (after closing the window) when the region is no longer a rhythm player region."""
        if self._closed:
            return True
        if self._still_there():
            return False
        self._closed = True
        self.session.announce("This region is no longer a rhythm player, so the window closed")
        end_dialog(self, wx.ID_CANCEL)
        return True

    def _run(self, action):
        if self._close_if_gone():
            return
        try:
            action()
        except ValueError as exc:
            show_error(self, str(exc))
        if not self._close_if_gone():
            self.after_change()

    def undo(self, redo=False):
        (self.session.redo if redo else self.session.undo)()
        if not self._close_if_gone():
            self.after_change()

    def on_char_hook(self, event):
        key = event.GetKeyCode()
        if event.GetModifiers() == wx.MOD_CONTROL and key in (ord("Z"), ord("Y")):
            self.undo(redo=key == ord("Y"))
            return
        event.Skip()


class PieceSettingsDialog(wx.Dialog, _RegionWindow):
    """One piece of a rhythm player (a kit piece of Anvil's, or the part of Bellows, Ember, Spark or Hammer): its
    pattern, its own extras, loudness, and its step pattern. Every change is heard at once and is one undo step;
    Control+Z and Control+Y work here."""

    def __init__(self, parent, session, track_id, index, piece_key, run_modal=None):
        self.session, self.track_id, self.index = session, track_id, index
        self.run_modal = run_modal or (lambda dialog: dialog.ShowModal())
        self.piece = player_pieces.PIECE_BY_KEY[piece_key]
        settings = session.player_settings(track_id, index)
        self.player = players.PLAYERS[settings["player"]]
        self.part = self.piece.kind == "part"
        track = session.song.track_by_id(track_id)
        self.region_start = track.note_regions[index].start
        self.kit, self.kit_notes = session.kit_program(track_id), session.kit_notes(track_id)
        name = "The part" if self.part else self.piece.name
        super().__init__(parent, title="{}: {} on {}".format(name, self.player.name, track.name))
        self._filling = False
        self._closed = False
        self.choices = {}               # setting -> (Choice, [keys])
        self.checks = {}
        self.numbers = {}
        full = self.full()
        form = Form(self)
        self.about = form.add("This piece now", wx.TextCtrl, value="", style=wx.TE_READONLY | wx.TE_MULTILINE,
                              size=(460, 50))
        if not self.part:
            self._check(form, "on", "Play this piece")
        self.pattern = form.add("Pattern", choice_ctrl, choices=[])
        self.numbers["busy"] = form.add(
            "Complexity of this {} in percent (50 as the style plays it; more is busier)".format(
                "part" if self.part else "piece"), slider_ctrl, value=player_pieces.BUSY_DEFAULT)
        kind = self.piece.kind
        if kind in ("kick", "snare"):
            self._choice(form, "time", "Time", player_pieces.TIME)
        if kind == "snare":
            self._choice(form, "ghosts", "Ghost notes", player_pieces.GHOSTS)
            self.numbers["ghost_level"] = form.add(
                "Ghost note loudness in percent (50 as the style plays them; more is bigger)", slider_ctrl,
                value=player_pieces.LEVEL_DEFAULT)
            self._choice(form, "rim", "Rim click (cross-stick) instead of the snare", player_pieces.RIM_CHOICES)
        if kind == "hat":
            self._choice(form, "openness", "How open the hi-hat is", player_pieces.OPENNESS)
            self._check(form, "open_offbeats", "Open the hi-hat on the and of each beat")
        if kind == "toms":
            self._check(form, "in_fills", "Play the toms in fills (off: the fills use the snare)")
        if kind == "crash":
            self._choice(form, "when", "When a crash comes", player_pieces.WHEN)
            which = [(key, player_pieces.which_words(key, self.kit))
                     for key, _notes in player_pieces.which_choices(self.kit_notes)]
            if full["which"] not in [key for key, _words in which]:      # chosen with another kit
                which.append((full["which"], player_pieces.which_words(full["which"], self.kit) +
                              player_pieces.missing_words(dict(player_pieces.WHICH).get(full["which"], ()),
                                                          self.kit_notes, self.kit)))
            self._choice(form, "which", "Which cymbal", which)
        if kind == "ride":
            self._choice(form, "ride_sound", "Which ride", self._in_kit(player_pieces.RIDE_SOUNDS, full["ride_sound"]))
        if kind == "ride" and (self.kit_notes is None or player_pieces.RIDE_BELL in self.kit_notes or full["bell"]):
            self._check(form, "bell", "Play the bell on the beats")
        if self.part:
            self._check(form, "chords", "Follow the chord track (off: the key's own chord)")
            self._choice(form, "octave", "Octave", OCTAVE_CHOICES)
            self._choice(form, "length", "Note length", player_pieces.LENGTHS)
            self._check(form, "root_only", "Play the root only")
            self._check(form, "passing", "Add passing notes into each chord change")
        self.numbers["level"] = form.add(
            "Loudness of this piece in percent (50 is as the style plays it, 100 the loudest, 0 silent)", slider_ctrl,
            value=player_pieces.LEVEL_DEFAULT)
        self.steps_button = wx.Button(self, label="&Step pattern...")
        form.add_wide(self.steps_button)
        self.clear_button = wx.Button(self, label="&Back to the pattern (the hand-made steps go)")
        form.add_wide(self.clear_button)
        self.close_button = wx.Button(self, wx.ID_CANCEL, label="Close")
        form.add_wide(self.close_button)
        finish_dialog(self, form.grid, buttons=0)
        self.SetEscapeId(wx.ID_CANCEL)
        self.pattern.Bind(wx.EVT_CHOICE, lambda e: self._pattern_chosen())
        for key, ctrl in self.numbers.items():          # sliders (Russell, 10 Oct 2026: "sliders are better")
            ctrl.Bind(wx.EVT_SLIDER, lambda e, k=key: self.change(**{k: self.numbers[k].GetValue()}))
        for key, (ctrl, values) in self.choices.items():
            ctrl.Bind(wx.EVT_CHOICE, lambda e, k=key: self._choice_chosen(k))
        for key, ctrl in self.checks.items():
            ctrl.Bind(wx.EVT_CHECKBOX, lambda e, k=key: self.change(**{k: self.checks[k].GetValue()}))
        self.steps_button.Bind(wx.EVT_BUTTON, lambda e: self._run(self.open_steps))
        self.clear_button.Bind(wx.EVT_BUTTON, lambda e: self._run(self.back_to_pattern))
        self.Bind(wx.EVT_CHAR_HOOK, self.on_char_hook)
        self.fill()
        (self.checks.get("on") or self.pattern).SetFocus()

    def _in_kit(self, options, chosen):
        """[(key, words)] of the cymbal choices the kit has, and the one chosen (it says which cymbal plays it
        instead if the kit lacks it)."""
        pairs = []
        for key, words, note in options:
            if self.kit_notes is None or note in self.kit_notes:
                pairs.append((key, words))
            elif key == chosen:
                pairs.append((key, words + player_pieces.missing_words(note, self.kit_notes, self.kit)))
        return pairs

    def _check(self, form, key, label):
        self.checks[key] = wx.CheckBox(self, label=label)
        form.add_wide(self.checks[key])

    def _choice(self, form, key, label, pairs):
        ctrl = form.add(label, choice_ctrl, choices=[words[0].upper() + words[1:] for _value, words in pairs])
        self.choices[key] = (ctrl, [value for value, _words in pairs])

    def full(self):
        return self.session.piece_settings(self.track_id, self.index, self.piece.key)

    @staticmethod
    def short_name(words):
        """A Pattern list item without what it plays: "Variation 3's: ride on every beat" is "Variation 3's"."""
        return words.split(": ", 1)[0]

    def has_sounds(self):
        """False for a kit piece the kit has none of (the Forge kits have no congas, for example)."""
        return self.part or bool(player_pieces.kit_voices(self.piece, self.kit_notes))

    def pattern_options(self):
        settings = self.session.player_settings(self.track_id, self.index)
        if self.part:
            return player_pieces.part_pattern_options(self.player, settings["style"], settings["variation"])
        # the region's fastest tempo: above it, no sixteenth-note patterns on the ride or hi-hat (21 Oct 2026)
        region = self.session.song.track_by_id(self.track_id).note_regions[self.index]
        tempo = players.fastest_tempo(self.session.song.timeline, region.start, region.end)
        return player_pieces.drum_pattern_options(settings["style"], settings["variation"], self.piece.key,
                                                  players._DRUM_STYLES, self.kit, self.kit_notes, tempo=tempo,
                                                  chosen=self.full()["pattern"])

    # what a hand-made drum piece's steps decide instead (dimmed while it is hand-made)
    STEPS_DECIDE = ("pattern", "busy", "time", "ghosts", "ghost_level")

    def fill(self):
        full = self.full()
        self._filling = True
        try:
            about = self.session.describe_piece(self.track_id, self.index, self.piece.key)
            if full["steps"]:
                about += (". Your steps set its rhythm and each step's loudness{}; Loudness now changes only what comes "
                          "by itself (fills, and crashes where the region starts and after fills)".format(
                              "" if self.part else ", so Pattern, Complexity, Time and Ghost notes are dimmed until "
                                                   "Back to the pattern"))
            self.options = self.pattern_options()
            keys = [key for key, _words in self.options]
            if full["pattern"] not in keys:            # chosen from a list that has changed since (a new variation)
                self.options.insert(1, (full["pattern"], "The pattern chosen before"))
                keys.insert(1, full["pattern"])
            # The list says only which pattern ("Variation 3's", "None in the groove", "Eighth notes"); what it plays is
            # in "This piece now" (Russell, 10 Oct 2026: changing a pattern read everything out).
            names = [self.short_name(words) for _key, words in self.options]
            chosen = self.options[keys.index(full["pattern"])][1]
            if self.short_name(chosen) != chosen and not chosen.endswith("none in the groove"):
                about += ". Pattern: " + chosen
            self.about.SetValue(about)
            if [self.pattern.GetString(i) for i in range(self.pattern.GetCount())] != names:
                self.pattern.Set(names)                 # only when it changed, so the screen reader is not disturbed
            self.pattern.SetSelection(keys.index(full["pattern"]))
            for key, (ctrl, values) in self.choices.items():
                ctrl.SetSelection(values.index(full[key]) if full[key] in values else 0)
            for key, ctrl in self.checks.items():
                ctrl.SetValue(bool(full[key]))
            for key, ctrl in self.numbers.items():
                try:
                    shown = ctrl.GetValue()
                except ValueError:
                    shown = None
                if shown != full[key]:
                    ctrl.SetValue(full[key])
            decided = self.STEPS_DECIDE if full["steps"] and not self.part else ()
            controls = {"pattern": self.pattern}
            controls.update(self.numbers)
            controls.update((key, ctrl) for key, (ctrl, _values) in self.choices.items())
            if any(controls[key].HasFocus() for key in decided if key in controls):
                self.steps_button.SetFocus()            # about to be dimmed: keep the focus somewhere useful
            for key, ctrl in controls.items():
                ctrl.Enable(key not in decided and not (key == "ghost_level" and full.get("ghosts") == "none"))
            self.steps_button.Enable(self.has_sounds())
            if not full["steps"] and self.clear_button.HasFocus():
                self.steps_button.SetFocus()            # it is about to be dimmed: keep the focus somewhere useful
            self.clear_button.Enable(bool(full["steps"]))
        finally:
            self._filling = False

    after_change = fill

    def change(self, **changes):
        if self._filling or self._close_if_gone():
            return
        try:
            self.session.update_piece(self.track_id, self.index, self.piece.key, speak=False, **changes)
        except ValueError as exc:
            show_error(self, str(exc))
            return
        self.fill()
        # nothing more is said: the pattern list, choices, check boxes and number boxes are read by the screen reader
        # as they change, and the piece's whole line on top of that was too much (Russell, 10 Oct 2026)

    def _pattern_chosen(self):
        here = self.pattern.GetSelection()
        if 0 <= here < len(self.options):
            self.change(pattern=self.options[here][0])

    def _choice_chosen(self, key):
        ctrl, values = self.choices[key]
        here = ctrl.GetSelection()
        if 0 <= here < len(values):
            self.change(**{key: values[here]})

    def open_steps(self):
        if not self.has_sounds():
            raise ValueError("This kit has no {} sounds, so there are no steps to set.".format(self.piece.name.lower()))
        with StepPatternDialog(self, self.session, self.track_id, self.index, self.piece.key) as dlg:
            self.run_modal(dlg)
        self.steps_button.SetFocus()

    def back_to_pattern(self):
        self.steps_button.SetFocus()                    # Back to the pattern is dimmed once the steps are gone
        words = self.session.update_piece(self.track_id, self.index, self.piece.key, speak=False, steps=None)
        self.fill()
        self.session.announce(words)


STEP_LENGTHS = [1, 2, 3, 4]


class StepPatternDialog(wx.Dialog, _RegionWindow):
    """A piece's steps one by one, our own accessible step sequencer. Each step is read with where it is in the bar,
    whether it plays, its sounds and their loudness. Space turns a step on or off, Left and Right choose its sound,
    Page Up and Page Down its loudness. Every change is heard at once and is one undo step (Control+Z and Control+Y
    work here); it makes the piece hand-made, which Reforge keeps and a change of variation resets after a warning.
    Until something is changed, the steps shown are what the piece plays now (without fills), so changing one step
    changes only that step: a drum step keeps every sound on it, and a part's steps play "as the style plays it"."""

    def __init__(self, parent, session, track_id, index, piece_key):
        self.session, self.track_id, self.index = session, track_id, index
        self.piece = player_pieces.PIECE_BY_KEY[piece_key]
        self.part = self.piece.kind == "part"
        settings = session.player_settings(track_id, index)
        self.player_key = settings["player"]
        self.kit, self.kit_notes = session.kit_program(track_id), session.kit_notes(track_id)
        self.sounds = player_pieces.sound_names(self.piece, self.player_key, self.kit, self.kit_notes)
        region = session.song.track_by_id(track_id).note_regions[index]
        self.region_start = region.start
        layout = players._bars(session.song.timeline, region.start, region.end)
        self.region_bars = len(layout)
        self.bar_steps, self.beat_steps = layout[0].steps, layout[0].beat_steps
        name = "the part" if self.part else self.piece.name
        super().__init__(parent, title="Step pattern: {}".format(name[0].upper() + name[1:]))
        self._closed = False
        self.load()
        self.last_velocity = 100
        self.last_sound = None
        self.turned_off = {}             # (bar, step) -> its sounds, so Space brings back exactly what it turned off
        form = Form(self)
        self.length = form.add("Pattern length", choice_ctrl,
                               choices=["{} bar{}".format(n, "" if n == 1 else "s") for n in STEP_LENGTHS])
        self.list = form.add("Steps (Space: on or off; Left and Right: the sound; Page Up and Page Down: loudness)",
                             wx.ListBox, choices=[], size=(460, 280))
        # the list's keys as buttons too, for the step the list is on (Russell, 10 Oct 2026: every feature reachable
        # with Tab); two short rows keep the window narrow
        self.step_buttons, step_row = _button_row(self, (
            ("toggle", "&Turn the step on or off (Space)"), ("previous", "Pre&vious sound (Left)"),
            ("next", "&Next sound (Right)")))
        more, loud_row = _button_row(self, (("louder", "Lo&uder (Page Up)"), ("softer", "So&fter (Page Down)")))
        self.step_buttons.update(more)
        self.buttons, row = _button_row(self, (
            ("copy", "&Copy steps"), ("paste", "&Paste steps"), ("clear", "C&lear every step"),
            ("pattern", "&Back to the pattern"), ("play", "Play the re&gion"), ("close", "Close")))
        form.add_wide(note_text(self, (
            "Up and Down move one step; the buttons under the list do what its keys do. Until you change a step, this "
            "shows what the piece plays now. Changing a step makes the piece hand-made: Reforge keeps it, and the "
            "pattern repeats through the whole region. Crashes where the region starts and after fills still come by "
            "themselves. At the end of a phrase a fill still takes over the snare, claps and toms (the kick, hi-hats, "
            "ride and shaker keep your steps): set Fills to 0 to hear only your steps.")))
        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(form.grid, 0, wx.EXPAND)
        outer.Add(step_row, 0, wx.TOP, 6)
        outer.Add(loud_row, 0)
        outer.Add(row, 0, wx.TOP, 6)
        finish_dialog(self, outer, buttons=0)
        self.SetEscapeId(wx.ID_CANCEL)
        self.length.Bind(wx.EVT_CHOICE, lambda e: self._run(self.set_length))
        self.list.Bind(wx.EVT_KEY_DOWN, self.on_key)
        actions = {"copy": self.copy, "paste": self.paste, "clear": self.clear, "pattern": self.back_to_pattern,
                   "play": lambda: self.session.play_note_region(self.track_id, self.index)}
        for key, action in actions.items():
            self.buttons[key].Bind(wx.EVT_BUTTON, lambda e, a=action: self._run(a))
        for key, button in self.step_buttons.items():
            button.Bind(wx.EVT_BUTTON, lambda e, k=key: self.step_action(k, self.list.GetSelection()))
        self.Bind(wx.EVT_CHAR_HOOK, self.on_char_hook)
        self.refresh(0)
        self.list.SetFocus()

    # -- the steps --------------------------------------------------------------
    def load(self, bars=None):
        """The steps: the hand-made ones, or else what the piece plays in the region's first bars (up to four, or
        `bars`), so changing one step changes only that step in those bars."""
        self.hand_made = bool(self.session.piece_settings(self.track_id, self.index, self.piece.key)["steps"])
        if self.hand_made:
            self.steps = self.session.piece_steps(self.track_id, self.index, self.piece.key)
        else:
            bars = bars or min(player_pieces.MAX_STEP_BARS, self.region_bars)
            self.steps = self.session.piece_steps(self.track_id, self.index, self.piece.key, bars=bars)

    def after_change(self):
        self.load(None if self.hand_made else len(self.steps["bars"]))
        self.refresh()

    def positions(self):
        return [(bar, step) for bar in range(len(self.steps["bars"])) for step in range(self.bar_steps)]

    def items_at(self, bar, step):
        """The step's sounds: [[step, loudness, sound], ...] (none when it is off; a drum step can have several)."""
        return [item for item in self.steps["bars"][bar] if item[0] == step]

    def sound_words(self, sound):
        words = dict(self.sounds).get(sound)
        if words is None:            # a sound the style plays that this kit does not have
            words = (player_pieces.note_name(sound, self.kit) +
                     player_pieces.missing_words(sound, self.kit_notes, self.kit) if isinstance(sound, int) else
                     player_pieces.SOUND_NAMES.get(sound, str(sound)))
        return words

    def describe(self, bar, step):
        """'Bar 1, step 3, the and of one: on, kick, loudness 90'."""
        where = "Bar {}, step {}, {}".format(bar + 1, step + 1, player_pieces.step_words(step, self.beat_steps))
        items = self.items_at(bar, step)
        if not items:
            return where + ": off"
        if len(items) > 1:
            return "{}: on, {}".format(where, player_pieces.join_words(
                "{} at {}".format(self.sound_words(item[2]), item[1]) for item in items))
        item = items[0]
        if len(self.sounds) > 1 or self.part:
            return "{}: on, {}, loudness {}".format(where, self.sound_words(item[2]), item[1])
        return "{}: on, loudness {}".format(where, item[1])

    def refresh(self, here=None):
        here = self.list.GetSelection() if here is None else here
        items = [self.describe(bar, step) for bar, step in self.positions()]
        show_items(self.list, items, max(0, min(here, len(items) - 1)))
        self.length.SetSelection(STEP_LENGTHS.index(len(self.steps["bars"])) if len(self.steps["bars"]) in STEP_LENGTHS
                                 else 0)
        if not self.hand_made and self.buttons["pattern"].HasFocus():
            self.list.SetFocus()                        # it is about to be dimmed: keep the focus on the steps
        self.buttons["pattern"].Enable(self.hand_made)

    def _sorted(self, items):
        return sorted(items, key=lambda i: (i[0], 0 if self.part else i[2]))

    def commit(self, speak_index=None):
        """Store the steps as the piece's hand-made steps (one undo step), then say the step that changed (and, the
        first time, that the pattern now repeats through the region)."""
        first_time = not self.hand_made
        self.session.set_piece_steps(self.track_id, self.index, self.piece.key, self.steps, speak=False)
        self.hand_made = True
        self.steps = self.session.piece_steps(self.track_id, self.index, self.piece.key)
        here = self.list.GetSelection()
        self.refresh(here)
        if speak_index is not None:
            bar, step = self.positions()[speak_index]
            words = self.describe(bar, step)
            if first_time:
                words += ". {} is hand-made now".format("The part" if self.part else self.piece.name)
                if self.region_bars > len(self.steps["bars"]):
                    words += "; its {} bar{} repeat{} through the region's {} bars".format(
                        len(self.steps["bars"]), "" if len(self.steps["bars"]) == 1 else "s",
                        "s" if len(self.steps["bars"]) == 1 else "", self.region_bars)
            self.session.announce(words)

    def on_key(self, event):
        key, mods = event.GetKeyCode(), event.GetModifiers()
        if mods == wx.MOD_CONTROL and key in (ord("C"), ord("V")):
            self._run(self.copy if key == ord("C") else self.paste)
            return
        here = self.list.GetSelection()
        if mods != wx.MOD_NONE or not 0 <= here < len(self.positions()):
            event.Skip()
            return
        what = {wx.WXK_SPACE: "toggle", wx.WXK_LEFT: "previous", wx.WXK_RIGHT: "next", wx.WXK_PAGEUP: "louder",
                wx.WXK_PAGEDOWN: "softer"}.get(key)
        if what is None:
            event.Skip()
            return
        self.step_action(what, here)

    def step_action(self, what, here):
        """What the list's keys and the buttons under it do to the step at line `here`: "toggle" (Space),
        "previous" and "next" sound (Left and Right), "louder" and "softer" (Page Up and Page Down)."""
        if not 0 <= here < len(self.positions()):
            self.session.announce("Choose a step in the list first")
            return
        action = {"toggle": lambda: self.toggle_step(here),
                  "previous": lambda: self.next_sound(here, -1), "next": lambda: self.next_sound(here, 1),
                  "louder": lambda: self.louder(here, 10), "softer": lambda: self.louder(here, -10)}[what]
        self._run(action)

    def toggle_step(self, here):
        bar, step = self.positions()[here]
        items = self.items_at(bar, step)
        row = self.steps["bars"][bar]
        if items:
            self.turned_off[(bar, step)] = [list(item) for item in items]
            for item in items:
                row.remove(item)
        else:
            back = self.turned_off.pop((bar, step), None)
            if back is None:
                sound = self.last_sound if self.last_sound in dict(self.sounds) else self.sounds[0][0]
                back = [[step, self.last_velocity, sound]]
            row.extend(back)
            self.steps["bars"][bar] = self._sorted(row)
        self.commit(here)

    def next_sound(self, here, direction):
        bar, step = self.positions()[here]
        items = self.items_at(bar, step)
        if not items:
            self.session.announce("This step is off. Space, or Turn the step on or off, turns it on.")
            return
        values = [value for value, _words in self.sounds]
        if len(values) == 1 and len(items) == 1:
            self.session.announce("{} has one sound".format(self.piece.name))
            return
        at = values.index(items[0][2]) if items[0][2] in values else 0
        sound = values[(at + direction) % len(values)] if len(items) == 1 else values[at]
        loudness = max(item[1] for item in items)
        row = [item for item in self.steps["bars"][bar] if item[0] != step] + [[step, loudness, sound]]
        self.steps["bars"][bar] = self._sorted(row)
        self.last_sound = sound
        self.commit(here)

    def louder(self, here, change):
        bar, step = self.positions()[here]
        items = self.items_at(bar, step)
        if not items:
            self.session.announce("This step is off. Space, or Turn the step on or off, turns it on.")
            return
        for item in items:
            item[1] = max(1, min(127, item[1] + change))
        self.last_velocity = max(item[1] for item in items)
        self.commit(here)

    def set_length(self):
        """Another pattern length: hand-made bars are repeated or cut; until then, the region's own bars are shown
        (nothing becomes hand-made until a step is changed)."""
        bars = STEP_LENGTHS[max(0, self.length.GetSelection())]
        current = self.steps["bars"]
        if bars == len(current):
            return
        if not self.hand_made:
            self.load(bars)
            self.refresh()
            self.session.announce("Showing {} bar{} of what the piece plays".format(bars, "" if bars == 1 else "s"))
            return
        self.steps = {"bars": [[list(item) for item in current[k % len(current)]] for k in range(bars)]}
        self.commit()
        self.session.announce("The pattern is {} bar{} long".format(bars, "" if bars == 1 else "s"))

    def copy(self):
        self.session.steps_clipboard = {"piece": self.piece.key, "player": self.player_key,
                                        "bars": [[list(item) for item in bar] for bar in self.steps["bars"]]}
        self.session.announce("Copied the steps of {} bar{}".format(len(self.steps["bars"]),
                                                                  "" if len(self.steps["bars"]) == 1 else "s"))

    def paste(self):
        clip = getattr(self.session, "steps_clipboard", None)
        if not clip:
            raise ValueError("Copy some steps first (Copy steps, or Control+C in a step pattern)")
        values = [value for value, _words in self.sounds]
        bars = []
        for bar in clip["bars"][:player_pieces.MAX_STEP_BARS]:
            found = {}
            for item in bar:
                if item[0] >= self.bar_steps:
                    continue
                sound = item[2] if item[2] in values else values[0]       # another piece's sound: this one's first
                key = item[0] if self.part else (item[0], sound)
                if key not in found or item[1] > found[key][1]:
                    found[key] = [item[0], item[1], sound]
            bars.append(self._sorted(found.values()))
        self.steps = {"bars": bars or [[]]}
        self.commit()
        self.session.announce("Pasted {} bar{} of steps".format(len(self.steps["bars"]),
                                                              "" if len(self.steps["bars"]) == 1 else "s"))

    def clear(self):
        self.steps = {"bars": [[] for _bar in self.steps["bars"]]}
        self.commit()
        self.session.announce("Every step is off")

    def back_to_pattern(self):
        self.list.SetFocus()                            # Back to the pattern is dimmed once the steps are gone
        self.session.clear_piece_steps(self.track_id, self.index, self.piece.key)
        self.load()
        self.refresh()


# ----------------------------------------------------------------------
# a region's trim and loop settings
# ----------------------------------------------------------------------
class RegionSettingsDialog(wx.Dialog):
    """Where a region starts and ends (trim), and how many times it plays in a row (loop)."""

    def __init__(self, parent, session, track_id, index):
        super().__init__(parent, title="Region settings: {}".format(session.region_name(track_id, index)))
        self.session = session
        tl = session.song.timeline
        start, end = session.region_span(track_id, index)
        loops = session.region_loops(track_id, index)
        audio = session.song.track_by_id(track_id).is_audio
        form = Form(self)
        start_bar, start_beat = _bar_and_beat(tl, start)
        end_bar, end_beat = _bar_and_beat(tl, end)
        self.start_bar = form.add("Starts at bar", spin_ctrl, min_value=1, max_value=9999, value=start_bar)
        self.start_beat = form.add("Starts at beat", DecimalField, min_value=1, max_value=LAST_BEAT, value=start_beat,
                                   step=1, decimals=2)
        self.end_bar = form.add("Ends at bar (where the next part begins)", spin_ctrl, min_value=1, max_value=9999,
                                value=end_bar)
        self.end_beat = form.add("Ends at beat", DecimalField, min_value=1, max_value=LAST_BEAT, value=end_beat, step=1,
                                 decimals=2)
        self.shown_span = (_tick_from(tl, start_bar, start_beat, "Starts at"),
                           _tick_from(tl, end_bar, end_beat, "Ends at"))
        self.times = form.add("Plays this many times in a row", spin_ctrl, min_value=1, max_value=999,
                              value=max(1, loops))
        self.until_next = wx.CheckBox(self, label="Loop until the next region (or the end of the song)")
        self.until_next.SetValue(loops == 0)
        form.add_wide(self.until_next)
        note = ("Trimming a recording changes which part of it plays; nothing is cut from the file, so you can "
                "lengthen it again." if audio else
                "Notes outside the new start and end are removed (Control+Z brings them back). A rhythm player fills "
                "whatever length it has.")
        form.add_wide(note_text(self, note))
        finish_dialog(self, form.grid)
        self.until_next.Bind(wx.EVT_CHECKBOX, lambda e: self.times.Enable(not self.until_next.GetValue()))
        self.times.Enable(loops != 0)
        self.start_bar.SetFocus()

    def get_values(self):
        """(start tick, end tick, loops: 0 means until the next region); start and end are None when
        they were left as shown (so a recording is never trimmed by rounding)."""
        tl = self.session.song.timeline
        start = _tick_from(tl, self.start_bar.GetValue(), self.start_beat.GetValue(), "Starts at")
        end = _tick_from(tl, self.end_bar.GetValue(), self.end_beat.GetValue(), "Ends at")
        if end <= start:
            raise ValueError("The region must end after it starts")
        loops = 0 if self.until_next.GetValue() else self.times.GetValue()
        if (start, end) == self.shown_span:
            return None, None, loops
        return start, end, loops
