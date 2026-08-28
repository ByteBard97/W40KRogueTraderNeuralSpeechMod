#!/usr/bin/env python3
"""Unpack Audiokinetic Wwise .pck (AKPK) file packages.

AKPK layout (little-endian):
  char[4] 'AKPK'
  u32 header_size (bytes after this field up to data)
  u32 version (1)
  u32 language_map_size
  u32 banks_table_size
  u32 streams_table_size
  u32 externals_table_size   (present in v1 packages written by modern Wwise)
  -- language map: u32 count, then count * (u32 offset, u32 id); at offsets, utf-16le names
  -- banks table:   u32 count, then count * (u32 id, u32 block_size, u32 size, u32 offset, u32 lang_id)
  -- streams table: same record layout
  -- externals:     u64 id, u32 block_size, u32 size, u32 offset, u32 lang_id

Files are written as <out>/<lang>/<id>.<ext> where ext is .bnk for banks, .wem for streams.
"""
from __future__ import annotations

import argparse
import struct
from pathlib import Path


def read_pck(path: Path):
    data = path.read_bytes()
    assert data[:4] == b"AKPK", f"{path} is not an AKPK package"
    header_size = struct.unpack_from("<I", data, 4)[0]
    version, lang_size, banks_size, streams_size, extern_size = struct.unpack_from("<5I", data, 8)
    pos = 28

    # language map
    lang_end = pos + lang_size
    count = struct.unpack_from("<I", data, pos)[0]
    langs = {}
    entries = [struct.unpack_from("<2I", data, pos + 4 + i * 8) for i in range(count)]
    for off, lang_id in entries:
        raw = data[pos + off: data.index(b"\x00\x00\x00", pos + off) + 2]
        # utf-16le, terminated by u16 0
        name = raw.decode("utf-16le", errors="ignore").rstrip("\x00")
        langs[lang_id] = name or f"lang{lang_id}"
    pos = lang_end

    def table(size, record="<5I", id_bytes=4):
        nonlocal pos
        end = pos + size
        if size < 4:
            pos = end
            return []
        n = struct.unpack_from("<I", data, pos)[0]
        rec_size = struct.calcsize(record)
        out = []
        p = pos + 4
        for _ in range(n):
            out.append(struct.unpack_from(record, data, p))
            p += rec_size
        pos = end
        return out

    banks = table(banks_size)
    streams = table(streams_size)
    externals = table(extern_size, record="<Q4I") if extern_size else []
    return data, langs, banks, streams, externals


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("pck", nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--list", action="store_true", help="only print the table summary")
    ap.add_argument("--banks-only", action="store_true")
    args = ap.parse_args()

    for pck in args.pck:
        path = Path(pck)
        data, langs, banks, streams, externals = read_pck(path)
        print(f"{path.name}: langs={list(langs.values())} banks={len(banks)} streams={len(streams)} externals={len(externals)}")
        if args.list:
            continue
        out_root = Path(args.out) / path.stem
        for kind, rows, ext in (("bank", banks, ".bnk"), ("stream", streams, ".wem")):
            if args.banks_only and kind != "bank":
                continue
            for row in rows:
                fid, block, size, offset, lang_id = row[-5:] if len(row) == 5 else (row[0], *row[1:])
                lang = langs.get(lang_id, str(lang_id))
                d = out_root / lang
                d.mkdir(parents=True, exist_ok=True)
                (d / f"{fid}{ext}").write_bytes(data[offset: offset + size])
        for row in externals:
            fid, block, size, offset, lang_id = row
            lang = langs.get(lang_id, str(lang_id))
            d = out_root / lang / "external"
            d.mkdir(parents=True, exist_ok=True)
            (d / f"{fid}.wem").write_bytes(data[offset: offset + size])


if __name__ == "__main__":
    main()
