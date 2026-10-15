#!/usr/bin/env python3
"""Stitch, overlay, patch and verify the overnight renders into a new bank set. Never installs and never deletes.

  python3 tools/render_corpus/night_build.py stitch      # stitched mixed / routed / designed cues -> data/render/*-stitched
  python3 tools/render_corpus/night_build.py export      # export_all_night = export_all_new + everything finished (later wins)
  python3 tools/render_corpus/night_build.py patch       # banks -> /home/geoff/rt-mods/all-banks-night
  python3 tools/render_corpus/night_build.py verify      # structure sweep of the built banks (PCM extensible header, sizes)
Each step skips runs whose manifest is missing. The export step also writes *-whole dirs (manifest rows without a "~" in the guid,
hard-linked wavs) because segment wavs must not be indexed as cues.
"""
from __future__ import annotations

import json
import os
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
R = ROOT / "data/render"
EXPORT = os.environ.get("RT_EXPORT", "export_all_night")
CACHE = Path(os.environ.get("RT_WEM_CACHE", str(R / "wem_cache_lufs")))
CODEC = os.environ.get("RT_CODEC", "opus")                 # "pcm" for the old uncompressed banks (about 12x larger)
OPUS_BITRATE = os.environ.get("RT_OPUS_BITRATE", "24k")   # chosen by ear in the Render Lab, 2026-10-13
PY = "/home/geoff/anaconda3/envs/roguetts/bin/python3"
OUT_BANKS = Path(os.environ.get("RT_OUT_BANKS", "/home/geoff/rt-mods/all-banks-night"))   # set RT_OUT_BANKS to build on another disk
PRISTINE = ("/mnt/games/SteamLibrary/steamapps/compatdata/2186680/pfx/drive_c/users/steamuser/AppData/LocalLow/Owlcat Games/"
            "Warhammer 40000 Rogue Trader/UnityModManager/W40KRT_AIVOMod/soundbanks_disabled/w40krt_avio_charvogen.bnk.pre-narr-real-2026-10-11")


def run(*args):
    print("+", " ".join(map(str, args)), flush=True)
    subprocess.run([PY, *map(str, args)], check=True, cwd=ROOT)


def has(run_name):
    return (R / run_name / "manifest.jsonl").is_file()


def stitch():
    sets = [("mixed-stitched", "jobs_mixed.jsonl", ["resat-r2", "night-redo", "mixed-seg-redo", "mixed-seg"]),
            ("routed-stitched", "jobs_routed_seg.jsonl", ["resat-r2", "night-redo", "routed"]),
            ("designed-stitched", "jobs_designed_seg.jsonl", ["resat-r2", "night-redo", "designed"]),
            ("split-long-stitched", "jobs_split.jsonl", ["split-long"]),
            ("q21-stitched", "jobs_q21.jsonl", ["q21"]),
            ("cast-stitched", "jobs_cast_all.jsonl", ["resat-r2", "cast"]),
            ("cast-fix-stitched", "jobs_cast_fix.jsonl", ["resat-r2", "cast"]),
            ("cast-r2b-stitched", "jobs_cast_r2_cues.jsonl", ["cast-r2", "resat-r2", "cast"])]     # recipe re-render (plan_recipe.py): cast-r2 takes win     # cues whose cast speaker contradicted ground truth (plan_cast_fix.py)       # characters cast with BG3 voices (cast_ready.py)
    for out, jobs, runs in sets:
        runs = [r for r in runs if has(r)]
        if runs and (R / jobs).is_file():
            run("tools/render_corpus/stitch_mixed.py", "--jobs", R / jobs, "--runs", *runs, "--out", out)


def whole(run_name):
    """data/render/<run>-whole: manifest rows without '~' and their wavs, hard-linked. A '<guid>@fix' take (recipe_followup.py) replaces its '<guid>' take."""
    out = R / f"{run_name}-whole"
    (out / "wav").mkdir(parents=True, exist_ok=True)
    best = {}
    for ln in (R / run_name / "manifest.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(ln)
        if "~" in r["guid"] or r.get("status") != "ok":
            continue
        base = r["guid"].removesuffix("@fix")
        if base not in best or r["guid"].endswith("@fix"):
            best[base] = r
    rows = []
    for base, r in best.items():
        src, dst = R / run_name / "wav" / f"{r['guid']}.wav", out / "wav" / f"{base}.wav"
        if src.is_file():
            if dst.exists() and dst.stat().st_ino != src.stat().st_ino:
                raise SystemExit(f"{dst} is linked to an older take; move {out} aside (gio trash after approval) and rebuild")
            if not dst.exists():
                os.link(src, dst)
            rows.append({**r, "guid": base})
    (out / "manifest.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    return out.name


def export():
    overlays = []
    for name in ("extra",):                       # codex/item strings; only with WITH_EXTRA=1 (adds ~3.5 GB of PCM to the bank set)
        if has(name) and os.environ.get("WITH_EXTRA") == "1":
            overlays.append(whole(name))
            if has("split-long-stitched"):
                overlays.append("split-long-stitched")
            if has("extra-r2"):
                overlays.append(whole("extra-r2"))         # narrator re-render with the real BG3 reference; wins over the Gale takes
    for name in ("mixed-stitched",):
        if has(name):
            overlays.append(name)
    for name in ("routed", "designed"):
        if has(name):
            overlays.append(whole(name))
    for name in ("routed-stitched", "designed-stitched", "q21-stitched", "cast-stitched", "cast-fix-stitched", "cast-r2b-stitched"):   # cast last: later overlays win
        if has(name):
            overlays.append(name)
    if has("resat-r2"):
        overlays.append(whole("resat-r2"))         # saturated whole-cue clips re-rendered with the recipe (stitched cues come in through stitch())
    run("tools/render_corpus/overlay_export.py", "--base", "export_all_new", "--overlay", *overlays, "--out", EXPORT)


def patch():
    base = OUT_BANKS.parent / "pristine-bank"
    base.mkdir(exist_ok=True)
    link = base / "w40krt_avio_charvogen.bnk"
    if not link.exists():
        os.symlink(PRISTINE, link)
    OUT_BANKS.mkdir(exist_ok=True)
    run("tools/bnk_patch/patch.py", "--bank", link, "--export", R / EXPORT, "--cache", CACHE,
        "--codec", CODEC, "--bitrate", OPUS_BITRATE,
        "--out-dir", OUT_BANKS)


def verify():
    sys.path.insert(0, str(ROOT / "tools/bnk_patch"))
    from bank import Bank
    bad = total = 0
    for p in sorted(OUT_BANKS.glob("*.bnk")):
        b = Bank(str(p))
        for mid, _, size in b.didx:
            data = b.read_media(mid)
            total += 1
            ok = data[:4] == b"RIFF" and data[8:12] == b"WAVE"
            if ok:
                tag = struct.unpack_from("<H", data, 20)[0]
                ok = tag in (0xFFFE, 0x3041, 0x0000) or (tag == 0xFFFF)   # extensible PCM (ours) or untouched Vorbis wems (0xFFFF)
            bad += not ok
        print(p.name, len(b.didx), "media", flush=True)
    print(f"verify: {total} media, {bad} bad header")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    for step in sys.argv[1:] or ["stitch", "export", "patch", "verify"]:
        globals()[step]()
