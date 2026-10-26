"""The automation windows (version 0.9): a track's lanes, one lane's points, and one point.

Same accessibility rules as everywhere: each control's label is created just before it, every
control is reached with Tab, buttons have underlined letters, and every change is spoken.
"""

import wx

from .. import automation as auto
from .common import (TRACK_GONE, DecimalField, Form, ShowAgain, ask_values, choice_ctrl, enable_keeping_focus,
                     end_dialog, finish_dialog, keep_enter_for_lists, note_text, says_after, show_error, show_items,
                     spin_ctrl, undo_in_list_window)


def _buttons(dialog, specs):
    row = wx.WrapSizer(wx.HORIZONTAL)
    buttons = {}
    for key, label in specs:
        button = wx.Button(dialog, wx.ID_CANCEL if key == "close" else wx.ID_ANY, label=label)
        buttons[key] = button
        row.Add(button, 0, wx.ALL, 3)
    return buttons, row


class _ListWindow(wx.Dialog):
    """A list with buttons under it; keys: Enter, Insert, Delete, Space. What a command says comes after the list
    is filled again (says_after)."""

    @says_after
    def _run(self, action):
        try:
            action()
        except ValueError as exc:
            show_error(self, str(exc))
        if not getattr(self, "_closed", False):
            self.list.SetFocus()

    def _bind_keys(self, keys):
        def on_key(event):
            action = keys.get(event.GetKeyCode()) if event.GetModifiers() == wx.MOD_NONE else None
            if action is None:
                event.Skip()
            else:
                self._run(action)
        self.list.Bind(wx.EVT_KEY_DOWN, on_key)
        # Enter reaches the list (common.enter_for_lists); Control+Z and Control+Y undo and redo here
        keep_enter_for_lists(self, (self.list, on_key), undo=self.undo)

    def undo(self, redo=False):
        """Control+Z and Control+Y (common.undo_in_list_window)."""
        undo_in_list_window(self, redo, self.refresh, gone=self._gone)

    def _gone(self):
        """After an undo or redo: the words to close with when it took the track away, or None."""
        return TRACK_GONE if self.session.song.track_by_id(self.track_id) is None else None

    def selected(self, count):
        if not count:
            return None
        index = self.list.GetSelection()
        return 0 if index == wx.NOT_FOUND else index


class AutomationDialog(_ListWindow):
    """A track's automation lanes: what changes over time on this track."""

    def __init__(self, parent, session, track_id, run_modal=None, confirm=None, confirm_replace=None):
        """confirm(words) asks Yes or No; confirm_replace(words) is the question before Add takes the place of a point
        already at that moment, in a lane's Points window (confirm when not given)."""
        track = session.song.track_by_id(track_id)
        super().__init__(parent, title="Automation: {}".format(track.name),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.session = session
        self.track_id = track_id
        self.run_modal = run_modal or (lambda dialog: dialog.ShowModal())
        self.confirm = confirm or (lambda message: True)
        self.confirm_replace = confirm_replace or self.confirm
        body = wx.BoxSizer(wx.VERTICAL)
        body.Add(wx.StaticText(self, label="Automation lanes on {} (what changes over time)".format(track.name)))
        self.list = wx.ListBox(self, size=(540, 180))
        body.Add(self.list, 1, wx.EXPAND | wx.TOP, 4)
        self.buttons, row = _buttons(self, (
            ("add", "&Add lane..."), ("points", "&Points..."), ("toggle", "Turn lane on or &off"),
            ("remove", "&Delete lane"), ("close", "Close")))
        body.Add(row, 0, wx.TOP, 6)
        body.Add(note_text(self, (
            "Enter lists a lane's points, Alt+A adds a lane, Space turns one on or off, Delete removes one. "
            "Once a lane has points it sets that value for the whole song; turned off, the track's own "
            "setting is used. Write automation (Control+Shift+W) records lanes as you change settings while "
            "the song plays."), width=540), 0, wx.TOP, 8)
        finish_dialog(self, body, buttons=0)
        self.SetEscapeId(wx.ID_CANCEL)
        actions = {"add": self.add, "points": self.points, "toggle": self.toggle, "remove": self.remove}
        for key, action in actions.items():
            self.buttons[key].Bind(wx.EVT_BUTTON, lambda e, a=action: self._run(a))
        self.list.Bind(wx.EVT_LISTBOX_DCLICK, lambda e: self._run(self.points))
        self._bind_keys({wx.WXK_RETURN: self.points, wx.WXK_NUMPAD_ENTER: self.points, wx.WXK_INSERT: self.add,
                         wx.WXK_NUMPAD_INSERT: self.add, wx.WXK_DELETE: self.remove,
                         wx.WXK_NUMPAD_DELETE: self.remove, wx.WXK_SPACE: self.toggle})
        self.refresh(0)
        self.list.SetFocus()

    def count(self):
        return len(self.session.lanes_of(self.track_id))

    def refresh(self, select=0):
        count = self.count()
        if count:
            show_items(self.list, [self.session.describe_lane(self.track_id, i) for i in range(count)],
                       max(0, min(select, count - 1)))
        else:
            show_items(self.list, ["No automation yet. Press Alt+A to add a lane, for example Volume."], 0)
        for key in ("points", "toggle", "remove"):
            enable_keeping_focus(self.buttons[key], bool(count), self.list)

    def add(self):
        targets = self.session.automation_targets(self.track_id)
        with AddLaneDialog(self, targets) as dlg:
            if self.run_modal(dlg) != wx.ID_OK:
                return
            target = dlg.get_target()
        index = self.session.add_lane(self.track_id, target)
        self.refresh(index)
        self.points()

    def points(self):
        index = self.selected(self.count())
        if index is None:
            return self.add()
        with LanePointsDialog(self, self.session, self.track_id, index, run_modal=self.run_modal,
                              confirm=self.confirm, confirm_replace=self.confirm_replace) as dlg:
            self.run_modal(dlg)
        if self._gone():             # an undo in there took the track away, and said so as that window closed
            self._closed = True
            end_dialog(self, wx.ID_CANCEL)
            return
        self.refresh(index)

    def toggle(self):
        index = self.selected(self.count())
        if index is not None:
            # the list, where the focus ends (from the button too), reads the lane's new line with "on" or "off", and
            # that line is all the session would say: not said twice (as the Effects window's Space; the keyboard
            # monkey, 26 Oct 2026)
            self.session.set_lane_on(self.track_id, index, speak=False)
            self.refresh(index)

    def remove(self):
        index = self.selected(self.count())
        if index is None:
            return
        if self.confirm("Delete the {} lane and its points? You can undo this with Control+Z.".format(
                self.session.lane_name(self.track_id, index))):
            self.session.remove_lane(self.track_id, index)
            self.refresh(index)


class AddLaneDialog(wx.Dialog):
    """Choose what the new lane changes: volume, pan, or one setting of one of the track's effects."""

    def __init__(self, parent, targets):
        super().__init__(parent, title="Add automation lane")
        self.targets = list(targets)
        form = Form(self)
        names = ["{}{}".format(name, " (already has a lane)" if have else "") for _key, name, have in self.targets]
        first_free = next((i for i, t in enumerate(self.targets) if not t[2]), 0)
        self.choice = form.add("What changes over time", choice_ctrl, choices=names, selection=first_free)
        form.add_wide(note_text(self, (
            "Effect settings are listed for each effect on this track. Add an effect first (Control+F) to "
            "automate it.")))
        finish_dialog(self, form.grid)
        self.choice.SetFocus()

    def get_target(self):
        return self.targets[max(0, self.choice.GetSelection())][0]


class LanePointsDialog(_ListWindow):
    """One lane's points, in song order."""

    def __init__(self, parent, session, track_id, lane_index, run_modal=None, confirm=None, confirm_replace=None):
        self.session = session
        self.track_id = track_id
        self.lane_index = lane_index
        self.run_modal = run_modal or (lambda dialog: dialog.ShowModal())
        self.confirm = confirm or (lambda message: True)
        self.confirm_replace = confirm_replace or self.confirm
        name = session.lane_name(track_id, lane_index)
        track = session.song.track_by_id(track_id)
        self.target = auto.target_key(session.lanes_of(track_id)[lane_index])   # (found again by it after an undo)
        super().__init__(parent, title="{} automation: {}".format(name, track.name),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        body = wx.BoxSizer(wx.VERTICAL)
        body.Add(wx.StaticText(self, label="Points of the {} lane, in song order".format(name)))
        self.list = wx.ListBox(self, size=(560, 220))
        body.Add(self.list, 1, wx.EXPAND | wx.TOP, 4)
        self.buttons, row = _buttons(self, (
            ("add", "&Add point..."), ("edit", "&Edit..."), ("delete", "&Delete"),
            ("play", "&Play from this point"), ("clear", "C&lear bars..."), ("close", "Close")))
        body.Add(row, 0, wx.TOP, 6)
        body.Add(note_text(self, (
            "Enter edits a point, Alt+A adds one at the playhead, Delete removes one, Space plays from it. "
            "Each point either glides to the next one or holds its value until the next one."), width=560),
                 0, wx.TOP, 8)
        finish_dialog(self, body, buttons=0)
        self.SetEscapeId(wx.ID_CANCEL)
        actions = {"add": self.add, "edit": self.edit, "delete": self.delete, "play": self.play,
                   "clear": self.clear}
        for key, action in actions.items():
            self.buttons[key].Bind(wx.EVT_BUTTON, lambda e, a=action: self._run(a))
        self.list.Bind(wx.EVT_LISTBOX_DCLICK, lambda e: self._run(self.edit))
        self._bind_keys({wx.WXK_RETURN: self.edit, wx.WXK_NUMPAD_ENTER: self.edit, wx.WXK_INSERT: self.add,
                         wx.WXK_NUMPAD_INSERT: self.add, wx.WXK_DELETE: self.delete,
                         wx.WXK_NUMPAD_DELETE: self.delete, wx.WXK_SPACE: self.play})
        self.refresh(self._index_at_playhead())
        self.list.SetFocus()

    def points_list(self):
        return self.session.lanes_of(self.track_id)[self.lane_index]["points"]

    def _gone(self):
        """After an undo or redo: None while this lane is still on the track (found again by what it changes, in case
        the undo moved it in the list of lanes), or the words to close with."""
        if self.session.song.track_by_id(self.track_id) is None:
            return TRACK_GONE
        lanes = self.session.lanes_of(self.track_id)
        index = next((i for i, lane in enumerate(lanes) if auto.target_key(lane) == self.target), None)
        if index is None:
            return "This automation lane is no longer on the track, so the window closed"
        self.lane_index = index
        return None

    def _index_at_playhead(self):
        tick = self.session.position_tick()
        index = 0
        for i, point in enumerate(self.points_list()):
            if point[0] <= tick:
                index = i
        return index

    def refresh(self, select=0):
        count = len(self.points_list())
        if count:
            show_items(self.list, [self.session.describe_point(self.track_id, self.lane_index, i)
                                   for i in range(count)], max(0, min(select, count - 1)))
        else:
            show_items(self.list, ["No points yet. Press Alt+A to add one at the playhead."], 0)
        for key in ("edit", "delete", "play"):
            enable_keeping_focus(self.buttons[key], bool(count), self.list)

    def add(self):
        tick = self.session.adding_tick()      # the playhead, or at the end of the song the last bar's start
        value = self.session.lane_value_at(self.track_id, self.lane_index, tick)
        with PointDialog(self, self.session, self.track_id, self.lane_index, tick, value, True,
                         title="Add automation point") as dlg:
            index = ask_values(self.run_modal, dlg, lambda: self._set_point(dlg))
        if index is not None:
            self.refresh(index)

    def _set_point(self, dlg, replacing=None):
        """Make the point from what is typed in its window; inside ask_values, so a point the song refuses (moved onto
        another point, or one past the lane's limit) brings the same window back with everything typed still in it,
        instead of its error coming after the window has closed (the review of 25 Oct 2026). A new point at the
        moment of one already there asks first (_ask_before_replacing). The list then lands on the point, and the
        screen reader reads its line, so the session leaves those words out (speak=False; said as well, NVDA said the
        line twice: the keyboard monkey, 26 Oct 2026) and says only what the line does not."""
        values = dlg.get_values()
        asked = replacing is None and self._ask_before_replacing(dlg, values)
        return self.session.set_point(self.track_id, self.lane_index, *values, replacing=replacing,
                                      tick=dlg.kept_tick, asked=bool(asked), speak=False)

    def _ask_before_replacing(self, dlg, values):
        """Add at the exact moment of a point already there would take its place (a lane keeps one point per
        moment): asked first, Yes or No (Russell, 25 Oct 2026; until then the song replaced it and said so after).
        No, or Escape, raises ShowAgain: the Add window comes back as it was. Yes replaces it, as one undo step, and
        returns True (it was asked, so the song does not say "Replaced the point that was there" after it). Writing
        automation while the song plays still replaces points without asking: that is what it is for."""
        tl = self.session.song.timeline
        tick = dlg.kept_tick if dlg.kept_tick is not None else tl.position_to_tick(int(values[0]), float(values[1]))
        tick = max(0, int(tick))
        there = next((p for p in self.points_list() if p[0] == tick), None)
        if there is None:
            return
        track = self.session.song.track_by_id(self.track_id)
        lane = self.session.lanes_of(self.track_id)[self.lane_index]
        where = tl.describe_position(tick)
        if not self.confirm_replace("There is already a point at {}{} ({}). Replace it?".format(
                where[:1].lower(), where[1:], auto.spoken_value(track, lane, there[1]))):
            raise ShowAgain()
        return True

    def edit(self):
        points = self.points_list()
        index = self.selected(len(points))
        if index is None:
            return self.add()
        tick, value, glide = points[index]
        with PointDialog(self, self.session, self.track_id, self.lane_index, tick, value, glide) as dlg:
            new_index = ask_values(self.run_modal, dlg, lambda: self._set_point(dlg, replacing=index))
        if new_index is not None:
            self.refresh(new_index)

    def delete(self):
        index = self.selected(len(self.points_list()))
        if index is not None:
            self.session.remove_point(self.track_id, self.lane_index, index)
            self.refresh(index)

    def play(self):
        index = self.selected(len(self.points_list()))
        if index is not None:
            self.session.play_from_point(self.track_id, self.lane_index, index)

    def clear(self):
        from .music_dialogs import BarRangeDialog

        song = self.session.song
        start, end = song.section_bounds(self.session.current_section_index())
        with BarRangeDialog(self, "Clear automation points", start, end - 1) as dlg:
            values = ask_values(self.run_modal, dlg)
        if values is None:
            return
        first, last = values
        self.session.clear_points(self.track_id, self.lane_index, first, last + 1)
        self.refresh(0)


class PointDialog(wx.Dialog):
    """One point: where it is, its value, and whether it glides to the next point."""

    def __init__(self, parent, session, track_id, lane_index, tick, value, glide, title="Edit automation point"):
        super().__init__(parent, title=title)
        self.session = session
        from .music_dialogs import LAST_BEAT, _bar_and_beat

        bar, beat = _bar_and_beat(session.song.timeline, tick)
        # the place as shown and the exact moment behind it: a place left as shown keeps the exact moment (the
        # shown beat is rounded, so a change of value alone could move the point onto its neighbour; the review of
        # 25 Oct 2026)
        self.tick, self.shown = tick, (bar, beat)
        self.kept_tick = None
        low, high, decimals, unit = session.value_range(track_id, lane_index)
        name = session.lane_name(track_id, lane_index)
        form = Form(self)
        self.bar = form.add("Bar", spin_ctrl, min_value=1, max_value=9999, value=bar)
        self.beat = form.add("Beat", DecimalField, min_value=1, max_value=LAST_BEAT, value=beat, step=1,
                             decimals=2)
        label = name
        if session.lanes_of(track_id)[lane_index]["target"] == "pan":
            label = "Pan (minus is left, plus is right, 0 is the middle)"
        elif unit == "percent" and "percent" not in label:
            label = "{} in percent".format(label)
        step = 1 if decimals == 0 else 10 ** -decimals
        self.value = form.add(label, DecimalField, min_value=low, max_value=high, value=value,
                              step=max(step, (high - low) / 100.0 if decimals == 0 and high - low > 200 else step),
                              decimals=decimals, unit="" if unit == "percent" else unit)
        self.glide = wx.CheckBox(self, label="Glide to the next point (off: hold this value until the next point)")
        self.glide.SetValue(bool(glide))
        form.add_wide(self.glide)
        finish_dialog(self, form.grid)
        self.value.SetFocus()

    def get_values(self):
        """(bar, beat, value, glide); raises ValueError with a friendly message (a beat the bar does not have too,
        so the window stays open to put it right)."""
        from .music_dialogs import _tick_from

        bar, beat = self.bar.GetValue(), self.beat.GetValue()
        _tick_from(self.session.song.timeline, bar, beat, "Beat")
        unchanged = int(bar) == self.shown[0] and round(float(beat), 2) == round(self.shown[1], 2)
        self.kept_tick = self.tick if unchanged else None
        return bar, beat, self.value.GetValue(), self.glide.GetValue()
