"""The automation windows (version 0.9): a track's lanes, one lane's points, and one point.

Same accessibility rules as everywhere: each control's label is created just before it, every
control is reached with Tab, buttons have underlined letters, and every change is spoken.
"""

import wx

from .common import DecimalField, Form, ask_values, choice_ctrl, finish_dialog, note_text, show_error, spin_ctrl


def _buttons(dialog, specs):
    row = wx.WrapSizer(wx.HORIZONTAL)
    buttons = {}
    for key, label in specs:
        button = wx.Button(dialog, wx.ID_CANCEL if key == "close" else wx.ID_ANY, label=label)
        buttons[key] = button
        row.Add(button, 0, wx.ALL, 3)
    return buttons, row


class _ListWindow(wx.Dialog):
    """A list with buttons under it; keys: Enter, Insert, Delete, Space."""

    def _run(self, action):
        try:
            action()
        except ValueError as exc:
            show_error(self, str(exc))
        self.list.SetFocus()

    def _bind_keys(self, keys):
        def on_key(event):
            action = keys.get(event.GetKeyCode()) if event.GetModifiers() == wx.MOD_NONE else None
            if action is None:
                event.Skip()
            else:
                self._run(action)
        self.list.Bind(wx.EVT_KEY_DOWN, on_key)

    def selected(self, count):
        if not count:
            return None
        index = self.list.GetSelection()
        return 0 if index == wx.NOT_FOUND else index


class AutomationDialog(_ListWindow):
    """A track's automation lanes: what changes over time on this track."""

    def __init__(self, parent, session, track_id, run_modal=None, confirm=None):
        track = session.song.track_by_id(track_id)
        super().__init__(parent, title="Automation: {}".format(track.name),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.session = session
        self.track_id = track_id
        self.run_modal = run_modal or (lambda dialog: dialog.ShowModal())
        self.confirm = confirm or (lambda message: True)
        body = wx.BoxSizer(wx.VERTICAL)
        body.Add(wx.StaticText(self, label="Automation lanes on {} (what changes over time)".format(track.name)))
        self.list = wx.ListBox(self, size=(540, 180))
        body.Add(self.list, 1, wx.EXPAND | wx.TOP, 4)
        self.buttons, row = _buttons(self, (
            ("add", "&Add lane..."), ("points", "&Points..."), ("toggle", "Turn lane on or &off"),
            ("remove", "&Delete lane"), ("close", "Close")))
        body.Add(row, 0, wx.TOP, 6)
        body.Add(note_text(self, (
            "Enter lists a lane's points, Alt+A adds a lane (Insert too), Space turns one on or off, Delete removes one. "
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
            self.list.Set([self.session.describe_lane(self.track_id, i) for i in range(count)])
            self.list.SetSelection(max(0, min(select, count - 1)))
        else:
            self.list.Set(["No automation yet. Press Alt+A to add a lane, for example Volume."])
            self.list.SetSelection(0)
        for key in ("points", "toggle", "remove"):
            self.buttons[key].Enable(bool(count))

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
                              confirm=self.confirm) as dlg:
            self.run_modal(dlg)
        self.refresh(index)

    def toggle(self):
        index = self.selected(self.count())
        if index is not None:
            self.session.set_lane_on(self.track_id, index)
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

    def __init__(self, parent, session, track_id, lane_index, run_modal=None, confirm=None):
        self.session = session
        self.track_id = track_id
        self.lane_index = lane_index
        self.run_modal = run_modal or (lambda dialog: dialog.ShowModal())
        self.confirm = confirm or (lambda message: True)
        name = session.lane_name(track_id, lane_index)
        track = session.song.track_by_id(track_id)
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
            "Enter edits a point, Alt+A adds one at the playhead (Insert too), Delete removes one, Space plays from it. "
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
            self.list.Set([self.session.describe_point(self.track_id, self.lane_index, i) for i in range(count)])
            self.list.SetSelection(max(0, min(select, count - 1)))
        else:
            self.list.Set(["No points yet. Press Alt+A to add one at the playhead."])
            self.list.SetSelection(0)
        for key in ("edit", "delete", "play"):
            self.buttons[key].Enable(bool(count))

    def add(self):
        tick = self.session.position_tick()
        value = self.session.lane_value_at(self.track_id, self.lane_index, tick)
        with PointDialog(self, self.session, self.track_id, self.lane_index, tick, value, True,
                         title="Add automation point") as dlg:
            values = ask_values(self.run_modal, dlg)
        if values is not None:
            self.refresh(self.session.set_point(self.track_id, self.lane_index, *values))

    def edit(self):
        points = self.points_list()
        index = self.selected(len(points))
        if index is None:
            return self.add()
        tick, value, glide = points[index]
        with PointDialog(self, self.session, self.track_id, self.lane_index, tick, value, glide) as dlg:
            values = ask_values(self.run_modal, dlg)
        if values is not None:
            self.refresh(self.session.set_point(self.track_id, self.lane_index, *values, replacing=index))

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
        return bar, beat, self.value.GetValue(), self.glide.GetValue()
