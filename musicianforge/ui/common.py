"""Small helpers shared by Musician Forge's windows.

Accessibility rule used everywhere: each input control is created right
after its text label. Windows (and so NVDA, JAWS and Narrator) uses the label
just before a control as that control's name.
"""

import logging

import wx

BORDER = 8

log = logging.getLogger("musicianforge.ui")


def silence_name(window):
    """Give a background container no name at all, so screen readers skip it.

    Without this, wxWidgets reports the panel's internal name ("panel"), which
    a screen reader may announce when focus enters the window.
    """
    if not hasattr(wx, "Accessible"):
        return

    class SilentAccessible(wx.Accessible):
        def GetName(self, childId):
            if childId == 0:
                return (wx.ACC_OK, "")
            return (wx.ACC_NOT_IMPLEMENTED, "")

    try:
        window.SetAccessible(SilentAccessible(window))
    except Exception:  # noqa: BLE001
        log.exception("Could not quiet a background panel's name")


class Form:
    """Builds a two-column form of label + control rows inside a dialog."""

    def __init__(self, parent):
        self.parent = parent
        self.grid = wx.FlexGridSizer(cols=2, vgap=6, hgap=10)
        self.grid.AddGrowableCol(1, 1)

    def add(self, label, control_factory, **kwargs):
        text = wx.StaticText(self.parent, label=label)
        control = control_factory(self.parent, **kwargs)
        if isinstance(control, (NumberField, DecimalField)) and not control.label:
            control.label = label
        self.grid.Add(text, 0, wx.ALIGN_CENTER_VERTICAL)
        self.grid.Add(control, 1, wx.EXPAND)
        return control

    def add_wide(self, window):
        self.grid.Add(window, 0)
        self.grid.Add((0, 0))


NOTE_WIDTH = 460   # about as wide as a window's lists and boxes


def note_text(parent, text, width=NOTE_WIDTH):
    """A paragraph of explanation under a window's controls, wrapped to `width` (in device-independent pixels) so
    the window stays narrow enough for the screen. Unwrapped, the Step pattern window's 440-character note made it
    about 2,600 pixels wide, and its list and Pattern length went off the screen (the accessibility report of
    9 Oct 2026 could not even see them)."""
    label = wx.StaticText(parent, label=text)
    label.Wrap(parent.FromDIP(width))
    return label


def text_ctrl(parent, value="", **kw):
    return wx.TextCtrl(parent, value=value, **kw)


class NumberField(wx.TextCtrl):
    """A plain text box for a whole number.

    Used instead of a Windows spin box, whose separate up/down arrow buttons
    have no name for screen readers. Type a number, or press Up and Down
    arrow (Page Up and Page Down for steps of 10); the new value is spoken.
    GetValue() returns an int and raises ValueError with a friendly message.
    """

    def __init__(self, parent, min_value=0, max_value=100, value=0, label=""):
        super().__init__(parent, value=str(int(value)))
        self.min_value = int(min_value)
        self.max_value = int(max_value)
        self.label = label
        self.Bind(wx.EVT_KEY_DOWN, self._on_key)

    def _problem(self):
        name = self.label or "This box"
        return ValueError("{} needs a whole number from {} to {}".format(name, self.min_value, self.max_value))

    def GetValue(self):
        text = super().GetValue().strip()
        try:
            number = int(text)
        except ValueError:
            raise self._problem() from None
        if not self.min_value <= number <= self.max_value:
            raise self._problem()
        return number

    def SetValue(self, value):
        super().SetValue(str(int(value)))

    def _on_key(self, event):
        step = {wx.WXK_UP: 1, wx.WXK_DOWN: -1, wx.WXK_PAGEUP: 10, wx.WXK_PAGEDOWN: -10,
                wx.WXK_NUMPAD_UP: 1, wx.WXK_NUMPAD_DOWN: -1}.get(event.GetKeyCode())
        if step is None or event.GetModifiers() != wx.MOD_NONE:
            event.Skip()
            return
        try:
            current = int(super().GetValue().strip())
        except ValueError:
            current = self.min_value
        new = max(self.min_value, min(self.max_value, current + step))
        super().SetValue(str(new))
        self.SetInsertionPointEnd()
        try:
            from ..speech import speaker

            speaker.speak(str(new))
        except Exception:  # noqa: BLE001 - speaking is a courtesy here
            pass


class DecimalField(wx.TextCtrl):
    """A plain text box for a number that may have decimals (such as 2.5 seconds or -3 dB).

    Like NumberField: type a number, or press Up and Down arrow to step it (Page Up and Page Down
    for ten steps); the new value is spoken with its unit. GetValue() returns a float (or an int
    when decimals is 0) and raises ValueError with a friendly message. on_change(value) is called
    after every arrow step and every valid number typed."""

    def __init__(self, parent, min_value=0.0, max_value=100.0, value=0.0, step=1.0, decimals=1, unit="",
                 label="", on_change=None):
        self.min_value = float(min_value)
        self.max_value = float(max_value)
        self.step = float(step)
        self.decimals = int(decimals)
        self.unit = unit
        self.label = label
        self.on_change = on_change
        super().__init__(parent, value=self._text(value))
        self.Bind(wx.EVT_KEY_DOWN, self._on_key)
        self.Bind(wx.EVT_TEXT, self._on_text)

    def _text(self, value):
        value = float(value)
        if self.decimals == 0:
            return str(int(round(value)))
        text = "{:.{}f}".format(value, self.decimals).rstrip("0").rstrip(".")
        return "0" if text in ("-0", "") else text

    def _problem(self):
        name = self.label or "This box"
        return ValueError("{} needs a number from {} to {}".format(name, self._text(self.min_value),
                                                                  self._text(self.max_value)))

    def GetValue(self):
        text = super().GetValue().strip().replace(",", ".")
        try:
            number = float(text)
        except ValueError:
            raise self._problem() from None
        if not self.min_value <= number <= self.max_value:
            raise self._problem()
        number = round(number, self.decimals)
        return int(number) if self.decimals == 0 else number

    def SetValue(self, value):
        self.ChangeValue(self._text(value))

    def _on_text(self, event):
        event.Skip()
        if self.on_change is None:
            return
        try:
            value = self.GetValue()
        except ValueError:
            return   # half typed: wait for a whole number
        self.on_change(value)

    def _on_key(self, event):
        steps = {wx.WXK_UP: 1, wx.WXK_DOWN: -1, wx.WXK_PAGEUP: 10, wx.WXK_PAGEDOWN: -10,
                 wx.WXK_NUMPAD_UP: 1, wx.WXK_NUMPAD_DOWN: -1}.get(event.GetKeyCode())
        if steps is None or event.GetModifiers() != wx.MOD_NONE:
            event.Skip()
            return
        try:
            current = float(super().GetValue().strip().replace(",", "."))
        except ValueError:
            current = self.min_value
        new = max(self.min_value, min(self.max_value, round(current + steps * self.step, 6)))
        self.ChangeValue(self._text(new))
        self.SetInsertionPointEnd()
        spoken = self._text(new) + (" " + self.unit if self.unit else "")
        try:
            from ..speech import speaker

            speaker.speak(spoken)
        except Exception:  # noqa: BLE001 - speaking is a courtesy here
            pass
        if self.on_change is not None:
            self.on_change(self.GetValue())


def spin_ctrl(parent, min_value=0, max_value=100, value=0, label=""):
    """Kept under its old name: every number box in Musician Forge is a NumberField."""
    return NumberField(parent, min_value=min_value, max_value=max_value, value=value, label=label)


def choice_ctrl(parent, choices=(), selection=0):
    ctrl = wx.Choice(parent, choices=list(choices))
    if choices:
        ctrl.SetSelection(max(0, min(selection, len(choices) - 1)))
    return ctrl


def slider_ctrl(parent, value=0, min_value=0, max_value=100):
    # No SL_LABELS: its little number labels would become the slider's name for screen readers.
    slider = wx.Slider(parent, value=value, minValue=min_value, maxValue=max_value, style=wx.SL_HORIZONTAL)
    slider.SetPageSize(10)
    return slider


def finish_dialog(dialog, body_sizer, buttons=wx.OK | wx.CANCEL):
    """Standard layout: the form, then OK and Cancel (Enter and Escape work as usual)."""
    outer = wx.BoxSizer(wx.VERTICAL)
    outer.Add(body_sizer, 1, wx.ALL | wx.EXPAND, BORDER * 2)
    if buttons:
        outer.Add(dialog.CreateStdDialogButtonSizer(buttons), 0, wx.ALL | wx.ALIGN_RIGHT, BORDER)
    dialog.SetSizerAndFit(outer)
    dialog.CentreOnParent()


def fit_to_screen(window):
    """Make a window no larger than the screen it is on (without the taskbar), and keep it on that screen. The
    project window asks for 960 by 900 pixels, which is taller than a laptop screen once Windows' scaling is 125
    or 150 percent (found in the review of 9 Oct 2026)."""
    try:
        index = wx.Display.GetFromWindow(window)
        area = wx.Display(index if index != wx.NOT_FOUND else 0).GetClientArea()
        width, height = window.GetSize()
        fitted = (min(width, area.width), min(height, area.height))
        if fitted != (width, height):
            window.SetSize(fitted)
            window.CentreOnScreen()
    except Exception:  # noqa: BLE001 - a window opens whatever its size
        log.exception("Could not fit a window to the screen")


def end_dialog(dialog, code):
    """Close a dialog with this result. wx allows EndModal only while the dialog is shown with ShowModal (it
    raises an assertion otherwise), so a dialog that is not (as in the window tests) just records the result
    and hides. Found on Windows on 9 Oct 2026: the rhythm player editor called EndModal unconditionally."""
    if dialog.IsModal():
        dialog.EndModal(code)
    else:
        dialog.SetReturnCode(code)
        dialog.Hide()


def show_error(parent, message, title="Musician Forge"):
    wx.MessageBox(message, title, wx.OK | wx.ICON_ERROR, parent)


def ask_values(run_modal, dialog, get_values=None):
    """Show a dialog (with run_modal) until what was typed in it makes sense: get_values() (the dialog's own by
    default) raises ValueError in words, and the dialog comes back with everything still in it. Returns the values,
    or None if it was cancelled. (Before the review of 9 Oct 2026 a mistyped number closed the window.)"""
    get_values = get_values or dialog.get_values
    while run_modal(dialog) == wx.ID_OK:
        try:
            return get_values()
        except ValueError as exc:
            show_error(dialog, str(exc))
    return None


def show_info(parent, message, title="Musician Forge"):
    wx.MessageBox(message, title, wx.OK | wx.ICON_INFORMATION, parent)


def ask_yes_no(parent, message, title="Musician Forge"):
    with wx.MessageDialog(parent, message, title, wx.YES_NO | wx.ICON_QUESTION) as dlg:
        return dlg.ShowModal() == wx.ID_YES


def ask_yes_no_cancel(parent, message, title="Musician Forge"):
    """Returns 'yes', 'no' or 'cancel'."""
    with wx.MessageDialog(parent, message, title, wx.YES_NO | wx.CANCEL | wx.ICON_QUESTION) as dlg:
        result = dlg.ShowModal()
    return {wx.ID_YES: "yes", wx.ID_NO: "no"}.get(result, "cancel")


NAVIGATION_KEYS = {wx.WXK_UP: -1, wx.WXK_DOWN: 1, wx.WXK_NUMPAD_UP: -1, wx.WXK_NUMPAD_DOWN: 1,
                   wx.WXK_PAGEUP: -10, wx.WXK_PAGEDOWN: 10, wx.WXK_NUMPAD_PAGEUP: -10, wx.WXK_NUMPAD_PAGEDOWN: 10,
                   wx.WXK_HOME: "first", wx.WXK_END: "last", wx.WXK_NUMPAD_HOME: "first", wx.WXK_NUMPAD_END: "last"}


def list_target(ctrl, key):
    """Where Up, Down, Page Up, Page Down, Home or End move in a list, or None for any other key."""
    move = NAVIGATION_KEYS.get(key)
    count = ctrl.GetCount()
    if move is None or not count:
        return None
    if move == "first":
        return 0
    if move == "last":
        return count - 1
    return max(0, min(count - 1, max(0, ctrl.GetSelection()) + move))


def show_items(ctrl, items, index):
    """Put `items` in a list and move it to `index` so that a screen reader reads the item it lands on once,
    with its new words (", selected"): the items the list is not on change first, then the list moves, then the
    item it left changes. Changing the words of the item a list is on makes Windows select it again, which a
    screen reader announces a second time (found in the review of 9 Oct 2026)."""
    if ctrl.GetCount() != len(items):
        ctrl.Set(items)
        if index is not None and 0 <= index < len(items):
            ctrl.SetSelection(index)
        return
    current = ctrl.GetSelection()
    for i, text in enumerate(items):
        if i != current and ctrl.GetString(i) != text:
            ctrl.SetString(i, text)
    if index is not None and 0 <= index < len(items) and current != index:
        ctrl.SetSelection(index)
    if 0 <= current < len(items) and ctrl.GetString(current) != items[current]:
        ctrl.SetString(current, items[current])
