"""Unpacking .7z archives with nothing but Python's own standard library.

The FreePats guitar packs are published as .7z files. Windows has no 7-Zip built in that a
program can rely on, and Musician Forge's installer uses only the standard library, so this module
reads the 7z format itself: it understands the archive's table of contents (including a
compressed one) and archives packed with LZMA or LZMA2, which is what the guitar packs use.
Python's lzma module does the actual decompression. Every file is checked against the CRC the
archive stores, so a damaged download is always caught.

Format reference: 7zFormat.txt from the 7-Zip source (Igor Pavlov, public domain).
"""

import lzma
import os
import struct
import zlib

SIGNATURE = b"7z\xbc\xaf\x27\x1c"
K_END, K_HEADER, K_ARCHIVE_PROPERTIES, K_ADDITIONAL_STREAMS = 0x00, 0x01, 0x02, 0x03
K_MAIN_STREAMS, K_FILES, K_PACK_INFO, K_UNPACK_INFO, K_SUBSTREAMS = 0x04, 0x05, 0x06, 0x07, 0x08
K_SIZE, K_CRC, K_FOLDER, K_CODERS_UNPACK_SIZE, K_NUM_UNPACK_STREAM = 0x09, 0x0A, 0x0B, 0x0C, 0x0D
K_EMPTY_STREAM, K_EMPTY_FILE, K_NAME, K_ENCODED_HEADER, K_DUMMY = 0x0E, 0x0F, 0x11, 0x17, 0x19
LZMA2_ID, LZMA_ID, COPY_ID = b"\x21", b"\x03\x01\x01", b"\x00"
CHUNK = 1 << 20


class ArchiveError(Exception):
    """The archive is damaged, or packed in a way this reader does not handle."""


class _Reader:
    def __init__(self, data):
        self.data = data
        self.pos = 0

    def byte(self):
        if self.pos >= len(self.data):
            raise ArchiveError("the archive's table of contents ends too early")
        value = self.data[self.pos]
        self.pos += 1
        return value

    def bytes(self, count):
        if self.pos + count > len(self.data):
            raise ArchiveError("the archive's table of contents ends too early")
        value = self.data[self.pos:self.pos + count]
        self.pos += count
        return value

    def number(self):
        first = self.byte()
        mask = 0x80
        value = 0
        for i in range(8):
            if first & mask == 0:
                return value | ((first & (mask - 1)) << (8 * i))
            value |= self.byte() << (8 * i)
            mask >>= 1
        return value

    def uint32(self):
        return struct.unpack("<I", self.bytes(4))[0]

    def bits(self, count):
        result, mask, current = [], 0, 0
        for _ in range(count):
            if mask == 0:
                current = self.byte()
                mask = 0x80
            result.append(bool(current & mask))
            mask >>= 1
        return result

    def defined_bits(self, count):
        """'All defined' byte, then (if not all) a bit for each item."""
        all_defined = self.byte()
        return [True] * count if all_defined else self.bits(count)


class _Coder:
    def __init__(self, method, props, in_streams, out_streams):
        self.method, self.props = method, props
        self.in_streams, self.out_streams = in_streams, out_streams


class _Folder:
    def __init__(self):
        self.coders = []
        self.bind_pairs = []
        self.packed = []
        self.unpack_sizes = []
        self.crc = None

    def unpack_size(self):
        bound = {out for _in, out in self.bind_pairs}
        for i, size in enumerate(self.unpack_sizes):
            if i not in bound:
                return size
        return self.unpack_sizes[-1]


class _Streams:
    def __init__(self):
        self.pack_pos = 0
        self.pack_sizes = []
        self.folders = []
        self.substream_counts = []
        self.substream_sizes = []
        self.substream_crcs = []


def _read_pack_info(r, streams):
    streams.pack_pos = r.number()
    count = r.number()
    while True:
        kind = r.number()
        if kind == K_END:
            break
        if kind == K_SIZE:
            streams.pack_sizes = [r.number() for _ in range(count)]
        elif kind == K_CRC:
            defined = r.defined_bits(count)
            for flag in defined:
                if flag:
                    r.uint32()
        else:
            raise ArchiveError("unexpected item {} in the pack information".format(kind))


def _read_folder(r):
    folder = _Folder()
    total_in = total_out = 0
    for _ in range(r.number()):
        flags = r.byte()
        method = r.bytes(flags & 0x0F)
        if flags & 0x10:
            in_streams, out_streams = r.number(), r.number()
        else:
            in_streams = out_streams = 1
        props = r.bytes(r.number()) if flags & 0x20 else b""
        if flags & 0x80:
            raise ArchiveError("this archive uses alternative coder methods, which are not supported")
        folder.coders.append(_Coder(method, props, in_streams, out_streams))
        total_in += in_streams
        total_out += out_streams
    for _ in range(total_out - 1):
        folder.bind_pairs.append((r.number(), r.number()))
    packed_count = total_in - (total_out - 1)
    if packed_count == 1:
        bound_in = {i for i, _o in folder.bind_pairs}
        folder.packed = [next(i for i in range(total_in) if i not in bound_in)]
    else:
        folder.packed = [r.number() for _ in range(packed_count)]
    folder.total_out = total_out
    return folder


def _read_unpack_info(r, streams):
    if r.number() != K_FOLDER:
        raise ArchiveError("the folder list is missing")
    count = r.number()
    if r.byte() != 0:
        raise ArchiveError("folders stored elsewhere in the archive are not supported")
    streams.folders = [_read_folder(r) for _ in range(count)]
    if r.number() != K_CODERS_UNPACK_SIZE:
        raise ArchiveError("the unpacked sizes are missing")
    for folder in streams.folders:
        folder.unpack_sizes = [r.number() for _ in range(folder.total_out)]
    while True:
        kind = r.number()
        if kind == K_END:
            break
        if kind == K_CRC:
            defined = r.defined_bits(count)
            for folder, flag in zip(streams.folders, defined):
                if flag:
                    folder.crc = r.uint32()
        else:
            raise ArchiveError("unexpected item {} in the folder information".format(kind))


def _read_substreams(r, streams):
    counts = [1] * len(streams.folders)
    kind = r.number()
    if kind == K_NUM_UNPACK_STREAM:
        counts = [r.number() for _ in streams.folders]
        kind = r.number()
    sizes = []
    if kind == K_SIZE:
        for folder, count in zip(streams.folders, counts):
            if count == 0:
                continue
            these = [r.number() for _ in range(count - 1)]
            these.append(folder.unpack_size() - sum(these))
            sizes.extend(these)
        kind = r.number()
    else:
        for folder, count in zip(streams.folders, counts):
            if count == 1:
                sizes.append(folder.unpack_size())
    crcs = []
    unknown = sum(c for f, c in zip(streams.folders, counts) if not (c == 1 and f.crc is not None))
    while kind != K_END:
        if kind == K_CRC:
            defined = r.defined_bits(unknown)
            digests = iter([r.uint32() if flag else None for flag in defined])
            for folder, count in zip(streams.folders, counts):
                if count == 1 and folder.crc is not None:
                    crcs.append(folder.crc)
                else:
                    crcs.extend(next(digests) for _ in range(count))
        else:
            raise ArchiveError("unexpected item {} in the file sizes".format(kind))
        kind = r.number()
    if not crcs:
        for folder, count in zip(streams.folders, counts):
            crcs.extend([folder.crc] if count == 1 else [None] * count)
    streams.substream_counts = counts
    streams.substream_sizes = sizes
    streams.substream_crcs = crcs


def _read_streams_info(r):
    streams = _Streams()
    while True:
        kind = r.number()
        if kind == K_END:
            break
        if kind == K_PACK_INFO:
            _read_pack_info(r, streams)
        elif kind == K_UNPACK_INFO:
            _read_unpack_info(r, streams)
        elif kind == K_SUBSTREAMS:
            _read_substreams(r, streams)
        else:
            raise ArchiveError("unexpected item {} in the streams information".format(kind))
    if not streams.substream_counts:
        streams.substream_counts = [1] * len(streams.folders)
        streams.substream_sizes = [f.unpack_size() for f in streams.folders]
        streams.substream_crcs = [f.crc for f in streams.folders]
    return streams


def _filters(coder):
    if coder.method == LZMA2_ID:
        prop = coder.props[0] if coder.props else 24
        dict_size = 0xFFFFFFFF if prop >= 40 else (2 | (prop & 1)) << (prop // 2 + 11)
        return [{"id": lzma.FILTER_LZMA2, "dict_size": min(dict_size, 1 << 30)}]
    if coder.method == LZMA_ID:
        props = coder.props
        if len(props) < 5:
            raise ArchiveError("LZMA settings are missing")
        d = props[0]
        lc, rest = d % 9, d // 9
        lp, pb = rest % 5, rest // 5
        dict_size = struct.unpack("<I", props[1:5])[0]
        return [{"id": lzma.FILTER_LZMA1, "lc": lc, "lp": lp, "pb": pb, "dict_size": max(dict_size, 4096)}]
    raise ArchiveError("this archive is packed with a method Musician Forge cannot unpack ({})".format(
        coder.method.hex()))


def _folder_chunks(fh, start, folder, pack_size):
    """Yield the unpacked bytes of one folder, a piece at a time."""
    if len(folder.coders) != 1 or len(folder.packed) != 1:
        raise ArchiveError("archives with several coders in a row (filters) are not supported")
    coder = folder.coders[0]
    fh.seek(start)
    remaining = pack_size
    if coder.method == COPY_ID:
        while remaining > 0:
            piece = fh.read(min(CHUNK, remaining))
            if not piece:
                raise ArchiveError("the archive ends too early")
            remaining -= len(piece)
            yield piece
        return
    decompressor = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=_filters(coder))
    wanted = folder.unpack_size()
    produced = 0
    while produced < wanted:
        if decompressor.needs_input:
            if remaining <= 0:
                raise ArchiveError("the archive ends too early")
            piece = fh.read(min(CHUNK, remaining))
            if not piece:
                raise ArchiveError("the archive ends too early")
            remaining -= len(piece)
        else:
            piece = b""
        out = decompressor.decompress(piece, max_length=CHUNK)
        if not out and (decompressor.eof or (remaining <= 0 and decompressor.needs_input)):
            break
        if out:
            out = out[:wanted - produced]   # 7z streams have no end marker: anything past the size is not data
            produced += len(out)
            yield out
    if produced != wanted:
        raise ArchiveError("the archive's data is shorter than its table of contents says")


def _read_header(fh):
    fh.seek(0)
    start = fh.read(32)
    if len(start) < 32 or start[:6] != SIGNATURE:
        raise ArchiveError("this is not a 7z archive")
    next_offset, next_size, next_crc = struct.unpack("<QQI", start[12:32])
    if zlib.crc32(start[12:32]) & 0xFFFFFFFF != struct.unpack("<I", start[8:12])[0]:
        raise ArchiveError("the archive's start is damaged")
    fh.seek(32 + next_offset)
    header = fh.read(next_size)
    if len(header) != next_size or zlib.crc32(header) & 0xFFFFFFFF != next_crc:
        raise ArchiveError("the archive's table of contents is damaged (it may not have downloaded completely)")
    r = _Reader(header)
    kind = r.number()
    while kind == K_ENCODED_HEADER:
        streams = _read_streams_info(r)
        position = 32 + streams.pack_pos
        data = b"".join(_folder_chunks(fh, position, streams.folders[0], streams.pack_sizes[0]))
        if streams.folders[0].crc is not None and zlib.crc32(data) & 0xFFFFFFFF != streams.folders[0].crc:
            raise ArchiveError("the archive's table of contents is damaged")
        r = _Reader(data)
        kind = r.number()
    if kind != K_HEADER:
        raise ArchiveError("the archive's table of contents is not recognised")
    return r


def _read_files(r, count):
    names = [""] * count
    empty = [False] * count
    while True:
        kind = r.number()
        if kind == K_END:
            break
        size = r.number()
        end = r.pos + size
        if kind == K_NAME:
            if r.byte() != 0:
                raise ArchiveError("file names stored elsewhere are not supported")
            raw = r.bytes(end - r.pos).decode("utf-16-le")
            names = raw.split("\x00")[:count]
        elif kind == K_EMPTY_STREAM:
            empty = r.bits(count)
        r.pos = end
    return names, empty


class Entry:
    def __init__(self, name, size, crc, folder, offset):
        self.name, self.size, self.crc = name, size, crc
        self.folder, self.offset = folder, offset    # which folder, and where in its unpacked data


def list_files(path):
    """[Entry] for every file with data in the archive (folders and empty files are left out)."""
    try:
        return _list_files(path)
    except (lzma.LZMAError, zlib.error, EOFError, struct.error, IndexError, StopIteration) as exc:
        raise ArchiveError("the archive is damaged ({})".format(exc)) from None


def _list_files(path):
    with open(path, "rb") as fh:
        r = _read_header(fh)
        streams = _Streams()
        names, empty = [], []
        while True:
            kind = r.number()
            if kind == K_END:
                break
            if kind == K_ARCHIVE_PROPERTIES:
                while r.number() != K_END:
                    r.bytes(r.number())
            elif kind == K_ADDITIONAL_STREAMS:
                _read_streams_info(r)
            elif kind == K_MAIN_STREAMS:
                streams = _read_streams_info(r)
            elif kind == K_FILES:
                count = r.number()
                names, empty = _read_files(r, count)
            else:
                raise ArchiveError("unexpected item {} in the table of contents".format(kind))
    entries = []
    sizes = iter(streams.substream_sizes)
    crcs = iter(streams.substream_crcs)
    data_names = iter([n for n, e in zip(names, empty) if not e])
    for folder_index, count in enumerate(streams.substream_counts):
        offset = 0
        for _ in range(count):
            size = next(sizes)
            entries.append(Entry(next(data_names, "file"), size, next(crcs, None), folder_index, offset))
            offset += size
    entries_streams = streams
    for entry in entries:
        entry.streams = entries_streams
    return entries


def extract_file(path, entry, target, progress=None):
    """Unpack one file from the archive to `target`, checking its CRC. Written to target + '.part' first,
    so an interrupted unpack never leaves a broken file. progress(fraction) is called now and then."""
    streams = entry.streams
    folder = streams.folders[entry.folder]
    pack_start = 32 + streams.pack_pos + sum(streams.pack_sizes[:entry.folder])
    temp = target + ".part"
    crc = 0
    written = 0
    position = 0
    end = entry.offset + entry.size
    try:
        with open(path, "rb") as fh, open(temp, "wb") as out:
            for piece in _folder_chunks(fh, pack_start, folder, streams.pack_sizes[entry.folder]):
                piece_end = position + len(piece)
                if piece_end > entry.offset and position < end:
                    part = piece[max(0, entry.offset - position):min(len(piece), end - position)]
                    out.write(part)
                    crc = zlib.crc32(part, crc)
                    written += len(part)
                    if progress is not None and entry.size:
                        progress(written / float(entry.size))
                position = piece_end
                if position >= end:
                    break
        if written != entry.size:
            raise ArchiveError("{} came out {} bytes long instead of {}".format(entry.name, written, entry.size))
        if entry.crc is not None and crc & 0xFFFFFFFF != entry.crc:
            raise ArchiveError("{} is damaged (its check sum does not match)".format(entry.name))
        os.replace(temp, target)
    except (lzma.LZMAError, zlib.error, EOFError, struct.error) as exc:
        if os.path.exists(temp):
            os.remove(temp)
        raise ArchiveError("{} is damaged and cannot be unpacked ({})".format(entry.name, exc)) from None
    except BaseException:
        if os.path.exists(temp):
            os.remove(temp)
        raise
    return target
