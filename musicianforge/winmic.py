"""What Windows does to the microphone before Musician Forge hears it (0.9.1): read only.

Windows keeps each sound device's settings in the registry, under MMDevices. For every working
microphone this reads its name and whether Windows' audio enhancements (noise suppression, echo
cancelling and the like, provided by the sound driver) are turned off. Nothing is ever changed:
Russell's rule is that Musician Forge only reads Windows settings and says in words how to change
them. Musician Forge asks for the raw microphone sound anyway (see audio.py), which skips these
enhancements on devices that support it.

Standard library only, so Diagnose can use it before anything is installed.
"""

CAPTURE_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\Capture"
DEVICE_DESCRIPTION = "{a45c254e-df1c-4efd-8020-67d146a850e0},2"   # "Microphone"
ADAPTER_NAME = "{b3f8fa53-0004-438e-9003-51a46e139bfc},6"         # "Realtek(R) Audio"
DISABLE_SYSFX = "{1da5d803-d492-4edd-8c23-e0c0ffee7f0e},5"        # 1: audio enhancements are off
DEVICE_STATE_ACTIVE = 1


def _value(winreg, key, name):
    try:
        value, _kind = winreg.QueryValueEx(key, name)
        return value
    except OSError:
        return None


def _subkeys(winreg, key):
    index = 0
    while True:
        try:
            yield winreg.EnumKey(key, index)
        except OSError:
            return
        index += 1


def _as_number(value):
    """Registry values come as numbers, or as bytes for some property types."""
    if isinstance(value, int):
        return value
    if isinstance(value, (bytes, bytearray)) and value:
        return int.from_bytes(bytes(value[:4]).ljust(4, b"\0"), "little")
    return None


def microphones(winreg=None):
    """[{"name": ..., "enhancements": "off" | "on" | "the driver's default"}] for every working microphone.
    An empty list when this is not Windows or nothing can be read."""
    if winreg is None:
        try:
            import winreg  # noqa: PLC0415 - only on Windows
        except ImportError:
            return []
    found = []
    try:
        root = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, CAPTURE_KEY)
    except OSError:
        return []
    with root:
        for guid in list(_subkeys(winreg, root)):
            try:
                device = winreg.OpenKey(root, guid)
            except OSError:
                continue
            with device:
                if _as_number(_value(winreg, device, "DeviceState")) != DEVICE_STATE_ACTIVE:
                    continue
                name, setting = guid, None
                try:
                    with winreg.OpenKey(device, "Properties") as props:
                        description = _value(winreg, props, DEVICE_DESCRIPTION)
                        adapter = _value(winreg, props, ADAPTER_NAME)
                        if isinstance(description, str) and description:
                            name = description + (" ({})".format(adapter) if isinstance(adapter, str) and adapter
                                                  else "")
                except OSError:
                    pass
                try:
                    with winreg.OpenKey(device, "FxProperties") as fx:
                        setting = _as_number(_value(winreg, fx, DISABLE_SYSFX))
                except OSError:
                    setting = None
                if setting is None:
                    state = "the driver's default"
                else:
                    state = "off" if setting else "on"
                found.append({"name": name, "enhancements": state})
    found.sort(key=lambda m: m["name"].lower())
    return found


HOW_TO_TURN_OFF = ("To turn them off: Windows Settings, System, Sound, choose the microphone under Input, then set "
                   "Audio enhancements to Off. On Windows 10: the Sound Control Panel, Recording, the microphone's "
                   "Properties, the Advanced or Enhancements tab, then Disable all enhancements.")


def describe(mic):
    """One sentence about one microphone."""
    if mic["enhancements"] == "off":
        return "{}: Windows audio enhancements are off.".format(mic["name"])
    if mic["enhancements"] == "on":
        return ("{}: Windows audio enhancements are on (noise reduction can remove background sound and held "
                "notes).".format(mic["name"]))
    return ("{}: Windows audio enhancements are as the sound driver sets them (often on: noise reduction can "
            "remove background sound and held notes).".format(mic["name"]))
