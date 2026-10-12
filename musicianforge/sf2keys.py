"""Which notes each instrument of a SoundFont has a sound for, read from the file's instrument directory (only
that part of the file is read: no sample data). Used to play a drum sound a kit lacks on one it has
(drummap.py)."""

import os
import struct

_cache = {}        # path -> (size, modified time, {(bank, program): frozenset of notes})

GEN_KEY_RANGE, GEN_INSTRUMENT, GEN_SAMPLE = 43, 41, 53


def preset_keys(path):
    """{(bank, program): frozenset(notes)} as the file numbers them (a bank offset is not added). Empty if the
    file cannot be read."""
    try:
        stat = os.stat(path)
    except OSError:
        return {}
    cached = _cache.get(path)
    if cached and cached[0] == stat.st_size and cached[1] == stat.st_mtime:
        return cached[2]
    try:
        result = _read(path)
    except (OSError, ValueError, struct.error):
        result = {}
    _cache[path] = (stat.st_size, stat.st_mtime, result)
    return result


def _read(path):
    with open(path, "rb") as fh:
        head = fh.read(12)
        if len(head) < 12 or head[:4] != b"RIFF" or head[8:12] != b"sfbk":
            raise ValueError("not a SoundFont")
        end = struct.unpack("<I", head[4:8])[0] + 8
        pdta = None
        pos = 12
        while pos + 8 <= end:
            fh.seek(pos)
            header = fh.read(12)
            if len(header) < 8:
                break
            kind, size = header[:4], struct.unpack("<I", header[4:8])[0]
            if kind == b"LIST" and header[8:12] == b"pdta":
                fh.seek(pos + 12)
                pdta = fh.read(size - 4)
                break
            pos += 8 + size + (size & 1)
    if pdta is None:
        raise ValueError("no instrument directory")
    parts = {}
    pos = 0
    while pos + 8 <= len(pdta):
        kind, size = pdta[pos:pos + 4], struct.unpack("<I", pdta[pos + 4:pos + 8])[0]
        parts[kind] = pdta[pos + 8:pos + 8 + size]
        pos += 8 + size + (size & 1)

    def records(kind, fmt):
        data, step = parts.get(kind, b""), struct.calcsize(fmt)
        return [struct.unpack(fmt, data[i:i + step]) for i in range(0, len(data) - step + 1, step)]

    phdr, pbag, pgen = records(b"phdr", "<20sHHHIII"), records(b"pbag", "<HH"), records(b"pgen", "<HH")
    inst, ibag, igen = records(b"inst", "<20sH"), records(b"ibag", "<HH"), records(b"igen", "<HH")

    def zones(bags, gens, first, last):
        found = []
        for z in range(first, min(last, len(bags) - 1)):
            found.append(dict(gens[bags[z][0]:bags[z + 1][0]]))
        return found

    def key_range(zone):
        value = zone.get(GEN_KEY_RANGE)
        return (0, 127) if value is None else (value & 0xFF, value >> 8)

    result = {}
    for i in range(len(phdr) - 1):          # the last record only marks the end
        _name, program, bank, first_bag = phdr[i][:4]
        notes = set()
        for preset_zone in zones(pbag, pgen, first_bag, phdr[i + 1][3]):
            index = preset_zone.get(GEN_INSTRUMENT)
            if index is None or index + 1 >= len(inst):
                continue
            low, high = key_range(preset_zone)
            for zone in zones(ibag, igen, inst[index][1], inst[index + 1][1]):
                if GEN_SAMPLE not in zone:
                    continue
                zone_low, zone_high = key_range(zone)
                notes.update(range(max(low, zone_low), min(high, zone_high) + 1))
        result[(bank, program)] = frozenset(notes)
    return result
