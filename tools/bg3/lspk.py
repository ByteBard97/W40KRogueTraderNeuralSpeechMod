"""Minimal reader for Larian LSPK v18 packages (BG3): list files and extract entries."""
import struct, zlib
import lz4.block, lz4.frame

DATA = "/mnt/games/SteamLibrary/steamapps/common/Baldurs Gate 3/Data/"


class Entry:
    __slots__ = ("name", "offset", "part", "flags", "size", "usize")


class Pak:
    def __init__(self, path):
        self.f = open(path, "rb")
        assert self.f.read(4) == b"LSPK"
        ver, = struct.unpack("<I", self.f.read(4))
        assert ver == 18, ver
        off, size, flags, prio = struct.unpack("<QIBB", self.f.read(14))
        self.f.read(16)
        nparts, = struct.unpack("<H", self.f.read(2))
        assert nparts == 1, "multi-part package"
        self.f.seek(off)
        n, csize = struct.unpack("<II", self.f.read(8))
        raw = lz4.block.decompress(self.f.read(csize), uncompressed_size=n * 272)
        self.entries = {}
        for i in range(n):
            nm, o1, o2, part, fl, sz, us = struct.unpack_from("<256sIHBBII", raw, i * 272)
            e = Entry()
            e.name = nm.split(b"\0")[0].decode()
            e.offset = o1 | (o2 << 32)
            e.part, e.flags, e.size, e.usize = part, fl, sz, us
            self.entries[e.name] = e

    def read(self, name):
        e = self.entries[name]
        self.f.seek(e.offset)
        d = self.f.read(e.size)
        m = e.flags & 0xF
        if m == 0:
            return d
        if m == 1:
            return zlib.decompress(d)
        if m == 2:
            try:
                return lz4.block.decompress(d, uncompressed_size=e.usize)
            except Exception:
                return lz4.frame.decompress(d)
        raise NotImplementedError("compression %d" % m)


def parse_loca(data):
    """LOCA -> {handle: text}. Handles look like h<uuid with 'g' for '-'>."""
    assert data[:4] == b"LOCA"
    n, toff = struct.unpack_from("<II", data, 4)
    out, pos, tp = {}, 12, toff
    for _ in range(n):
        key, ver, ln = struct.unpack_from("<64sHI", data, pos)
        pos += 70
        out[key.split(b"\0")[0].decode()] = data[tp:tp + ln - 1].decode("utf8", "replace")
        tp += ln
    return out
