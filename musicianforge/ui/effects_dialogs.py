"""The effects windows: a track's list of effects, adding one, and one effect's settings.

Everything here follows the same accessibility rules as the rest of Musician Forge: each control's
label is created right before it, every control is reached with Tab, and changes are spoken.
"""

import wx

from .. import effects
from .common import (TRACK_GONE, DecimalField, Form, ask_values, choice_ctrl, enable_keeping_focus, finish_dialog,
                     keep_enter_for_lists, note_text, says_after, show_error, show_items, slider_ctrl,
                     undo_in_list_window)

OWN_SETTINGS = "Your own settings"


class EffectsDialog(wx.Dialog):
    """A track's effects, top to bottom: the order its sound goes through them."""

    def __init__(self, parent, session, track_id, run_modal=None, confirm=None):
        track = session.song.track_by_id(track_id)
        super().__init__(parent, title="Effects: {}".format(track.name), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.session = session
        self.track_id = track_id
        self.run_modal = run_modal or (lambda dialog: dialog.ShowModal())
        self.confirm = confirm or (lambda message: True)
        body = wx.BoxSizer(wx.VERTICAL)
        body.Add(wx.StaticText(self, label="Effects on {}, in the order the sound goes through them".format(
            track.name)))
        self.list = wx.ListBox(self, size=(520, 200))
        body.Add(self.list, 1, wx.EXPAND | wx.TOP, 4)
        row = wx.WrapSizer(wx.HORIZONTAL)
        self.buttons = {}
        for key, label in (("add", "&Add effect..."), ("settings", "&Settings..."), ("toggle", "Turn on or &off"),
                           ("up", "Move &up"), ("down", "Move &down"), ("remove", "&Remove"), ("close", "Close")):
            button = wx.Button(self, wx.ID_CANCEL if key == "close" else wx.ID_ANY, label=label)
            self.buttons[key] = button
            row.Add(button, 0, wx.ALL, 3)
        body.Add(row, 0, wx.TOP, 6)
        body.Add(note_text(self, (
            "Enter opens the selected effect's settings. Alt+A adds an effect, Delete removes one, Space turns it "
            "on or off, Control+Up and Control+Down move it. Effects work on the track's sound before its volume "
            "and pan.")), 0, wx.TOP, 8)
        finish_dialog(self, body, buttons=0)
        self.SetEscapeId(wx.ID_CANCEL)
        actions = {"add": self.add, "settings": self.settings, "toggle": self.toggle, "up": lambda: self.move(-1),
                   "down": lambda: self.move(1), "remove": self.remove}
        for key, action in actions.items():
            self.buttons[key].Bind(wx.EVT_BUTTON, lambda e, a=action: self._run(a))
        self.list.Bind(wx.EVT_KEY_DOWN, self.on_key)
        # Enter reaches the list (common.enter_for_lists); Control+Z and Control+Y undo and redo here
        keep_enter_for_lists(self, (self.list, self.on_key), undo=self.undo)
        self.list.Bind(wx.EVT_LISTBOX_DCLICK, lambda e: self._run(self.settings))
        self.refresh(0)
        self.list.SetFocus()

    @property
    def effects(self):
        return self.session.effects_of(self.track_id)

    @says_after
    def _run(self, action):
        try:
            action()
        except ValueError as exc:
            show_error(self, str(exc))
        self.list.SetFocus()

    def undo(self, redo=False):
        """Control+Z and Control+Y (common.undo_in_list_window); an undo that takes the track away closes the window."""
        undo_in_list_window(self, redo, self.refresh,
                            gone=lambda: TRACK_GONE if self.session.song.track_by_id(self.track_id) is None else None)

    def refresh(self, select=0):
        items = self.effects
        if items:
            show_items(self.list, [self.session.describe_effect(self.track_id, i) for i in range(len(items))],
                       max(0, min(select, len(items) - 1)))
        else:
            show_items(self.list, ["No effects yet. Press Alt+A, or the Add effect button, to add one."], 0)
        # a button dimmed while it has the focus would send the focus on by itself (screen reader audit B3)
        for key in ("settings", "toggle", "up", "down", "remove"):
            enable_keeping_focus(self.buttons[key], bool(items), self.list)
        enable_keeping_focus(self.buttons["add"], len(items) < effects.MAX_EFFECTS, self.list)

    def selected(self):
        if not self.effects:
            return None
        index = self.list.GetSelection()
        return 0 if index == wx.NOT_FOUND else index

    def add(self):
        types = self.session.effect_types_for(self.track_id)
        with AddEffectDialog(self, types) as dlg:
            if self.run_modal(dlg) != wx.ID_OK:
                return
            type_key, preset = dlg.get_values()
        index = self.session.add_effect(self.track_id, type_key, preset)
        self.refresh(index)

    def settings(self):
        index = self.selected()
        if index is None:
            return
        with EffectSettingsDialog(self, self.session, self.track_id, index) as dlg:
            # a mistyped number brings the same window back with every change still in it (it used to open a new
            # one with the saved settings, while the changes went on being heard)
            values = ask_values(self.run_modal, dlg)
        if values is None:
            self.session.end_effect_preview()
        else:
            on, preset, params = values
            self.session.update_effect(self.track_id, index, params=params, preset=preset, on=on)
        self.refresh(index)

    def toggle(self):
        index = self.selected()
        if index is not None:
            # the list reads the effect's line again with "on" or "off": not said twice (audit B2). From the Turn on or
            # off button (or Alt+O) too, since _run gives the list the focus and the screen reader reads it there with
            # its new line; the button said the effect's words again after it (the keyboard monkey, 26 Oct 2026)
            self.session.set_effect_on(self.track_id, index, speak=False)
            self.refresh(index)

    def move(self, delta):
        index = self.selected()
        if index is not None:
            self.refresh(self.session.move_effect(self.track_id, index, delta))

    def remove(self):
        index = self.selected()
        if index is None:
            return
        name = effects.TYPE_BY_KEY[self.effects[index]["type"]].name
        if self.confirm("Remove {} from this track? You can undo this with Control+Z.".format(name)):
            self.session.remove_effect(self.track_id, index)
            self.refresh(index)

    def on_key(self, event):
        key = event.GetKeyCode()
        mods = event.GetModifiers()
        action = None
        if mods == wx.MOD_NONE:
            action = {wx.WXK_RETURN: self.settings, wx.WXK_NUMPAD_ENTER: self.settings,
                      wx.WXK_INSERT: self.add, wx.WXK_NUMPAD_INSERT: self.add,
                      wx.WXK_DELETE: self.remove, wx.WXK_NUMPAD_DELETE: self.remove,
                      wx.WXK_SPACE: self.toggle}.get(key)
        elif mods == wx.MOD_CONTROL:
            action = {wx.WXK_UP: lambda: self.move(-1), wx.WXK_DOWN: lambda: self.move(1)}.get(key)
        if action is None:
            event.Skip()
        else:
            self._run(action)


def percent_label(label):
    """'Mix (how much reverb)' becomes 'Mix in percent (how much reverb)'."""
    if " (" in label:
        head, tail = label.split(" (", 1)
        return "{} in percent ({}".format(head, tail)
    return label + " in percent"


class AddEffectDialog(wx.Dialog):
    """Choose an effect and the preset it starts from (every setting can be changed afterwards)."""

    SUMMARIES = {"eq": "shapes the tone: bass, middle and treble", "compressor": "evens out the volume",
                 "distortion": "overdrive, crunch, fuzz or bit crushing", "delay": "echoes in time with the song",
                 "reverb": "the sound of a room or hall", "pitch": "pulls a recording onto the song's key"}

    def __init__(self, parent, types):
        super().__init__(parent, title="Add effect")
        self.types = list(types)
        form = Form(self)
        self.kind = form.add("Effect", choice_ctrl,
                             choices=["{}: {}".format(t.name, self.SUMMARIES.get(t.key, "")) for t in self.types],
                             selection=0)
        self.preset = form.add("Starting preset (every setting can be changed afterwards)", choice_ctrl, choices=[])
        self.about = form.add("About this effect", wx.TextCtrl, value="",
                              style=wx.TE_READONLY | wx.TE_MULTILINE, size=(-1, 70))
        finish_dialog(self, form.grid)
        self.kind.Bind(wx.EVT_CHOICE, lambda e: self.on_kind())
        self.on_kind()
        self.kind.SetFocus()

    def chosen(self):
        return self.types[max(0, self.kind.GetSelection())]

    def on_kind(self):
        kind = self.chosen()
        self.preset.Set(kind.preset_names())
        self.preset.SetSelection(0)
        self.about.SetValue(kind.description)

    def get_values(self):
        kind = self.chosen()
        return kind.key, kind.preset_names()[max(0, self.preset.GetSelection())]


class EffectSettingsDialog(wx.Dialog):
    """One effect: on or off, a preset to start from, and every setting. Changes are heard at once
    (play the song with the Play or stop button); OK keeps them, Cancel puts back what was there."""

    def __init__(self, parent, session, track_id, index):
        track = session.song.track_by_id(track_id)
        effect = track.effects[index]
        self.kind = effects.TYPE_BY_KEY[effect["type"]]
        super().__init__(parent, title="{} settings: {}".format(self.kind.name, track.name))
        self.session = session
        self.track_id = track_id
        self.index = index
        self._filling = False
        self.controls = {}
        form = Form(self)
        names = self.kind.preset_names()
        preset = effects.matching_preset(effect)
        self.preset_names = names + [OWN_SETTINGS]
        self.preset = form.add("Preset", choice_ctrl, choices=self.preset_names,
                               selection=names.index(preset) if preset in names else len(names))
        self.on = wx.CheckBox(self, label="Effect on")
        self.on.SetValue(bool(effect.get("on", True)))
        form.add_wide(self.on)
        for p in self.kind.params:
            value = effect["params"][p.key]
            if p.kind == "switch":
                control = wx.CheckBox(self, label=p.label)
                control.SetValue(bool(value))
                form.add_wide(control)
                control.Bind(wx.EVT_CHECKBOX, lambda e: self.changed())
            elif p.kind == "choice":
                values = [v for v, _name in p.choices]
                control = form.add(p.label, choice_ctrl, choices=[name for _v, name in p.choices],
                                   selection=values.index(value) if value in values else 0)
                control.Bind(wx.EVT_CHOICE, lambda e: self.changed())
            elif p.kind == "percent":
                control = form.add(percent_label(p.label), slider_ctrl, value=int(value), min_value=0, max_value=100)
                control.Bind(wx.EVT_SLIDER, lambda e: self.changed())
            else:
                control = form.add(p.label, DecimalField, min_value=p.low, max_value=p.high, value=value,
                                   step=p.step, decimals=p.decimals, unit=p.unit,
                                   on_change=lambda v: self.changed())
            self.controls[p.key] = control
        self.play_button = wx.Button(self, label="&Play or stop the song (to hear the changes)")
        form.add_wide(self.play_button)
        note = ("Pitch correction is worked out for each recording when you press OK, then you hear it."
                if self.kind.key == "pitch" else "Changes are heard straight away. OK keeps them; Cancel puts "
                                                 "back what was there.")
        form.add_wide(wx.StaticText(self, label=note))
        finish_dialog(self, form.grid)
        self.preset.Bind(wx.EVT_CHOICE, lambda e: self.on_preset())
        self.on.Bind(wx.EVT_CHECKBOX, lambda e: self.preview())
        self.play_button.Bind(wx.EVT_BUTTON, lambda e: self.play())
        self.preset.SetFocus()

    def play(self):
        try:
            self.session.toggle_play()
        except ValueError as exc:
            show_error(self, str(exc))

    def read(self, strict=False):
        """The settings as they are now in the window. strict: raise ValueError for a bad number;
        otherwise a bad number keeps the effect's current value."""
        current = self.session.effects_of(self.track_id)[self.index]["params"]
        params = {}
        for p in self.kind.params:
            control = self.controls[p.key]
            if p.kind == "switch":
                params[p.key] = bool(control.GetValue())
            elif p.kind == "choice":
                params[p.key] = p.choices[max(0, control.GetSelection())][0]
            elif p.kind == "percent":
                params[p.key] = int(control.GetValue())
            else:
                try:
                    params[p.key] = p.clamp(control.GetValue())
                except ValueError:
                    if strict:
                        raise
                    params[p.key] = current[p.key]
        return params

    def fill(self, values):
        self._filling = True
        try:
            for p in self.kind.params:
                control = self.controls[p.key]
                value = values[p.key]
                if p.kind == "switch":
                    control.SetValue(bool(value))
                elif p.kind == "choice":
                    keys = [v for v, _name in p.choices]
                    control.SetSelection(keys.index(value) if value in keys else 0)
                elif p.kind == "percent":
                    control.SetValue(int(value))
                else:
                    control.SetValue(value)
        finally:
            self._filling = False

    def on_preset(self):
        index = self.preset.GetSelection()
        if index == wx.NOT_FOUND or self.preset_names[index] == OWN_SETTINGS:
            return
        self.fill(self.kind.preset_values(self.preset_names[index]))
        self.preview()

    def changed(self):
        if self._filling:
            return
        params = self.read()
        matching = None
        for name in self.kind.preset_names():
            values = self.kind.preset_values(name)
            if all(values[p.key] == params[p.key] for p in self.kind.params):
                matching = name
                break
        target = self.preset_names.index(matching) if matching else len(self.preset_names) - 1
        if self.preset.GetSelection() != target:
            self.preset.SetSelection(target)
        self.preview()

    def preview(self):
        try:
            self.session.preview_effect(self.track_id, self.index, params=self.read(), on=self.on.GetValue())
        except ValueError:
            pass

    def get_values(self):
        """(on, preset name, settings); raises ValueError with a friendly message for a bad number."""
        params = self.read(strict=True)
        index = self.preset.GetSelection()
        name = self.preset_names[index] if index != wx.NOT_FOUND else OWN_SETTINGS
        if name == OWN_SETTINGS:
            name = self.session.effects_of(self.track_id)[self.index].get("preset")
        return self.on.GetValue(), name, params

