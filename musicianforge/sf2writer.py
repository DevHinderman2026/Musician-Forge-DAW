"""Writing SoundFont 2 (.sf2) files, for Musician Forge's own instruments.

Only what Musician Forge needs: 16-bit mono samples, instruments made of zones
(a key range, a velocity range, a sample and a few settings), and presets that
each play one instrument. FluidSynth loads the result like any SoundFont.

Layout and numbers follow the SoundFont 2.04 specification.
"""

import struct
from dataclasses import dataclass, field

import numpy as np

# Generator numbers (SoundFont 2.04, section 8.1.2)
GEN_PAN = 17                    # -500 (left) to 500 (right), tenths of a percent
GEN_ATTACK_VOL_ENV = 34         # timecents
GEN_HOLD_VOL_ENV = 35
GEN_DECAY_VOL_ENV = 36
GEN_SUSTAIN_VOL_ENV = 37        # centibels of attenuation
GEN_RELEASE_VOL_ENV = 38
GEN_INSTRUMENT = 41
GEN_KEY_RANGE = 43
GEN_VEL_RANGE = 44
GEN_INITIAL_ATTENUATION = 48    # centibels
GEN_COARSE_TUNE = 51
GEN_FINE_TUNE = 52
GEN_SAMPLE_ID = 53
GEN_SAMPLE_MODES = 54           # 0: play once, 1: loop
GEN_SCALE_TUNING = 56           # cents per key: 100 normally, 0 for one pitch on every key
GEN_EXCLUSIVE_CLASS = 57        # sounds in the same class cut each other off (hi-hats)
GEN_OVERRIDING_ROOT_KEY = 58

MONO_SAMPLE = 1
SAMPLE_PADDING = 46             # zero points the specification requires after every sample


def timecents(seconds):
    """Envelope times are stored as timecents: 1200 times log2 of the seconds."""
    return int(round(1200.0 * np.log2(max(0.001, float(seconds)))))


@dataclass
class Sample:
    name: str
    data: np.ndarray            # mono float audio, -1 to 1
    sample_rate: int = 48000
    root_key: int = 60


@dataclass
class Zone:
    sample: int                 # index into the sample list
    key_range: tuple = (0, 127)
    vel_range: tuple = (0, 127)
    generators: dict = field(default_factory=dict)  # generator number -> amount


@dataclass
class Instrument:
    name: str
    zones: list


@dataclass
class Preset:
    name: str
    bank: int
    program: int
    instrument: int             # index into the instrument list


def _name(text):
    return text.encode("latin-1", "replace")[:19].ljust(20, b"\0")


def _chunk(tag, data):
    pad = b"\0" if len(data) % 2 else b""
    return tag + struct.pack("<I", len(data)) + data + pad


def _list(kind, chunks):
    body = kind + b"".join(chunks)
    return b"LIST" + struct.pack("<I", len(body)) + body


def _zstr(text):
    data = text.encode("latin-1", "replace") + b"\0"
    return data + (b"\0" if len(data) % 2 else b"")


def _gen(oper, amount):
    if oper in (GEN_KEY_RANGE, GEN_VEL_RANGE):
        lo, hi = amount
        return struct.pack("<HBB", oper, int(lo), int(hi))
    return struct.pack("<Hh", oper, int(amount))


def build_sf2(bank_name, samples, instruments, presets, copyright_text="", comment=""):
    """The bytes of a complete .sf2 file."""
    # sample data: 16-bit, each sample followed by zero padding
    pcm, headers, position = [], [], 0
    for sample in samples:
        data = np.clip(np.asarray(sample.data, dtype=np.float64), -1.0, 1.0)
        ints = np.round(data * 32767.0).astype("<i2")
        start, end = position, position + len(ints)
        headers.append(struct.pack("<20sIIIIIBbHH", _name(sample.name), start, end, start, end,
                                   int(sample.sample_rate), int(sample.root_key), 0, 0, MONO_SAMPLE))
        pcm.append(ints.tobytes() + b"\0\0" * SAMPLE_PADDING)
        position = end + SAMPLE_PADDING
    headers.append(struct.pack("<20sIIIIIBbHH", _name("EOS"), 0, 0, 0, 0, 0, 0, 0, 0, 0))

    inst_records, ibag, igen = [], [], []
    for inst in instruments:
        inst_records.append(struct.pack("<20sH", _name(inst.name), len(ibag)))
        for zone in inst.zones:
            ibag.append(struct.pack("<HH", len(igen), 0))
            igen.append(_gen(GEN_KEY_RANGE, zone.key_range))   # the key range must come first
            igen.append(_gen(GEN_VEL_RANGE, zone.vel_range))   # then the velocity range
            for oper in sorted(zone.generators):
                igen.append(_gen(oper, zone.generators[oper]))
            igen.append(_gen(GEN_SAMPLE_ID, zone.sample))      # and the sample last
    inst_records.append(struct.pack("<20sH", _name("EOI"), len(ibag)))
    ibag.append(struct.pack("<HH", len(igen), 0))
    igen.append(struct.pack("<HH", 0, 0))

    preset_records, pbag, pgen = [], [], []
    for preset in sorted(presets, key=lambda p: (p.bank, p.program)):
        preset_records.append(struct.pack("<20sHHHIII", _name(preset.name), int(preset.program),
                                          int(preset.bank), len(pbag), 0, 0, 0))
        pbag.append(struct.pack("<HH", len(pgen), 0))
        pgen.append(_gen(GEN_INSTRUMENT, preset.instrument))   # the instrument comes last (and only)
    preset_records.append(struct.pack("<20sHHHIII", _name("EOP"), 0, 0, len(pbag), 0, 0, 0))
    pbag.append(struct.pack("<HH", len(pgen), 0))
    pgen.append(struct.pack("<HH", 0, 0))
    empty_mod = struct.pack("<HHhHH", 0, 0, 0, 0, 0)

    info = [_chunk(b"ifil", struct.pack("<HH", 2, 1)), _chunk(b"isng", _zstr("EMU8000")),
            _chunk(b"INAM", _zstr(bank_name)), _chunk(b"ISFT", _zstr("Musician Forge"))]
    if copyright_text:
        info.append(_chunk(b"ICOP", _zstr(copyright_text)))
    if comment:
        info.append(_chunk(b"ICMT", _zstr(comment)))
    sdta = [_chunk(b"smpl", b"".join(pcm))]
    pdta = [_chunk(b"phdr", b"".join(preset_records)), _chunk(b"pbag", b"".join(pbag)),
            _chunk(b"pmod", empty_mod), _chunk(b"pgen", b"".join(pgen)),
            _chunk(b"inst", b"".join(inst_records)), _chunk(b"ibag", b"".join(ibag)),
            _chunk(b"imod", empty_mod), _chunk(b"igen", b"".join(igen)),
            _chunk(b"shdr", b"".join(headers))]
    body = b"sfbk" + _list(b"INFO", info) + _list(b"sdta", sdta) + _list(b"pdta", pdta)
    return b"RIFF" + struct.pack("<I", len(body)) + body


def write_sf2(path, *args, **kwargs):
    """Write the file safely: to a temporary name first, then swap it into place."""
    import os

    data = build_sf2(*args, **kwargs)
    tmp = path + ".tmp"
    with open(tmp, "wb") as fh:
        fh.write(data)
    os.replace(tmp, path)
    return len(data)
