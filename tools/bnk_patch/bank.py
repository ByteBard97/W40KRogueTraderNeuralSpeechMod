"""Minimal Wwise soundbank reader/writer for swapping embedded media (bank version 145).

Only the pieces needed to replace the audio of existing sounds: BKHD/DIDX/DATA/HIRC chunks.
HIRC is kept byte-identical except, per replaced Sound object, the codec plugin id and the
in-memory media size.
"""
import struct

PLUGIN_VORBIS = 0x00040001
PLUGIN_PCM = 0x00010001
PLUGIN_OPUS_WEM = 0x00140001   # AKCODECID_AKOPUS_WEM (codec 20); unproven in game, see tone_test3.py
OBJ_SOUND, OBJ_ACTION, OBJ_EVENT = 2, 3, 4


def fnv32(name):
    h = 2166136261
    for c in name.lower().encode():
        h = ((h * 16777619) & 0xFFFFFFFF) ^ c
    return h


class Bank:
    def __init__(self, path):
        self.path = path
        self.f = open(path, "rb")
        self.chunks = []  # (tag, offset, size) in file order
        self.f.seek(0, 2)
        end = self.f.tell()
        self.f.seek(0)
        while self.f.tell() < end:
            tag, size = struct.unpack("<4sI", self.f.read(8))
            self.chunks.append((tag, self.f.tell(), size))
            self.f.seek(size, 1)
        c = {t: (o, s) for t, o, s in self.chunks}
        self.bkhd = self._read(*c[b"BKHD"])
        o, s = c[b"DIDX"]
        raw = self._read(o, s)
        self.didx = [struct.unpack_from("<III", raw, i * 12) for i in range(s // 12)]
        self.data_off = c[b"DATA"][0]
        self.hirc = bytearray(self._read(*c[b"HIRC"])) if b"HIRC" in c else bytearray(struct.pack("<I", 0))
        self.media_size = {m: sz for m, _, sz in self.didx}
        self._parse_hirc()

    def _read(self, off, size):
        self.f.seek(off)
        return self.f.read(size)

    def read_media(self, media_id):
        m = {m: (o, s) for m, o, s in self.didx} if not hasattr(self, "_mm") else self._mm
        self._mm = m
        o, s = m[media_id]
        return self._read(self.data_off + o, s)

    def _parse_hirc(self):
        n = struct.unpack_from("<I", self.hirc, 0)[0]
        pos = 4
        self.sounds, actions, events = {}, {}, {}
        self.objs = []
        for _ in range(n):
            t, sz = struct.unpack_from("<BI", self.hirc, pos)
            body = pos + 5
            oid = struct.unpack_from("<I", self.hirc, body)[0]
            if t == OBJ_SOUND:
                self.sounds[oid] = body
            elif t == OBJ_ACTION:
                actions[oid] = struct.unpack_from("<I", self.hirc, body + 6)[0]
            elif t == OBJ_EVENT and self.hirc[body + 4] == 1:
                events[oid] = struct.unpack_from("<I", self.hirc, body + 5)[0]
            pos = body + sz
        assert pos == len(self.hirc), "HIRC parse did not consume the chunk"
        self.event_sound = {}
        for ev, act in events.items():
            snd = actions.get(act)
            if snd in self.sounds:
                self.event_sound[ev] = snd

    def sound_media(self, sound_id):
        b = self.sounds[sound_id]
        plugin = struct.unpack_from("<I", self.hirc, b + 4)[0]
        stream = self.hirc[b + 8]
        src_id, size = struct.unpack_from("<II", self.hirc, b + 9)
        return plugin, stream, src_id, size

    def media_for_guid(self, guid):
        snd = self.event_sound.get(fnv32("ev_" + guid))
        if snd is None:
            return None
        plugin, stream, src, size = self.sound_media(snd)
        if stream != 0 or src not in self.media_size or size != self.media_size[src]:
            return None
        return snd, src

    def write_split(self, out_dir, name, replacements, max_bank=3_400_000_000, align=16, plugin=PLUGIN_PCM):
        """replacements: {media_id: path to PCM wem file}.

        Writes <name>.bnk (original objects with patched Sound entries, replaced media removed) and
        <name>_pcmN.bnk media-only banks (BKHD + DIDX + DATA, no HIRC) holding the new audio. Wwise
        resolves media ids across every loaded bank, so the events in the main bank find the media
        in the side banks. Returns the list of (file, DATA bytes).
        """
        import os
        hirc = bytearray(self.hirc)
        for b in self.sounds.values():
            src = struct.unpack_from("<I", hirc, b + 9)[0]
            if src in replacements:
                struct.pack_into("<I", hirc, b + 4, plugin)
                struct.pack_into("<I", hirc, b + 13, os.path.getsize(replacements[src]))
        out = []

        def emit(path, items, with_hirc, bank_id):
            # items: list of (media_id, size, reader)
            entries, pos = [], 0
            for m, size, _ in items:
                pos = (pos + align - 1) // align * align
                entries.append((m, pos, size))
                pos += size
            if pos >= 2**32:
                raise ValueError("DATA chunk %d bytes, over the u32 limit" % pos)
            didx = b"".join(struct.pack("<III", *e) for e in entries)
            bkhd = bytearray(self.bkhd)
            struct.pack_into("<I", bkhd, 4, bank_id)
            with open(path, "wb") as o:
                o.write(struct.pack("<4sI", b"BKHD", len(bkhd)) + bytes(bkhd))
                o.write(struct.pack("<4sI", b"DIDX", len(didx)) + didx)
                o.write(struct.pack("<4sI", b"DATA", pos))
                cur = 0
                for (m, p, s), (_, _, rd) in zip(entries, items):
                    o.write(b"\0" * (p - cur))
                    o.write(rd())
                    cur = p + s
                if with_hirc:
                    o.write(struct.pack("<4sI", b"HIRC", len(hirc)) + bytes(hirc))
            out.append((path, pos))

        keep = [(m, s, (lambda m=m: self.read_media(m))) for m, _, s in self.didx if m not in replacements]
        emit(os.path.join(out_dir, name + ".bnk"), keep, True, struct.unpack_from("<I", self.bkhd, 4)[0])
        group, used, n = [], 0, 1
        order = [m for m, _, _ in self.didx if m in replacements]
        for m in order:
            size = os.path.getsize(replacements[m])
            if group and used + size + align > max_bank:
                emit(os.path.join(out_dir, "%s_pcm%d.bnk" % (name, n)), group, False, fnv32("%s_pcm%d" % (name, n)))
                group, used, n = [], 0, n + 1
            p = replacements[m]
            group.append((m, size, (lambda p=p: open(p, "rb").read())))
            used += size + align
        if group:
            emit(os.path.join(out_dir, "%s_pcm%d.bnk" % (name, n)), group, False, fnv32("%s_pcm%d" % (name, n)))
        return out
