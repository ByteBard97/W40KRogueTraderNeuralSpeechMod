#!/usr/bin/env python3
"""Audit a built export: flag the longest p percent of renders and the rate outliers, then check each flagged file.

  python3 tools/render_corpus/audit_renders.py [--export export_all_night] [--top-pct 5] [--out data/render/audit/render_audit.json]

Pass 1 (cheap, every clip): file size vs the size its frame count implies, sample rate, channels, seconds per spoken character.
Pass 2 (flagged clips only): silence, clipping, a cut-off ending, long gaps in the middle, plus any Whisper flags from the
runs' asr.jsonl. Flagged = the longest --top-pct percent by duration, seconds-per-character outliers (robust z-score), and
anything failing pass 1. Writes a ranked JSON list with a verdict per clip ("listen" ones are the ones to open first).
Read only: never edits an export.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[2]
RENDER = ROOT / "data/render"
TAGS = re.compile(r"\{/?[a-z]+\}|\{[^}]*\}|<[^>]+>")
OUTLIER_Z = 4.0           # robust z-score of seconds per character
GAP_S = 1.5               # silence inside a clip longer than this is suspicious
SILENCE_DB = -50.0
TAIL_S = 0.08
TAIL_REL_DB = -15.0       # last 80 ms within 15 dB of the whole clip's level = speech still going = probably cut off
SR = 48000                # the export is resampled to 48 kHz mono
BAD_ASR = {"asr_bad", "asr_truncated", "asr_extra_words"}   # asr_warn / asr_spelled are only hints
INTRO_QUIET_DB = 6.0      # the first second this much quieter than the rest of the clip: the line starts too softly
CLIP_FRAC = 0.001         # >0.1% of samples at full scale


def spoken(text: str) -> str:
    return TAGS.sub("", text).replace("\n", " ").strip()


def load_asr() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for p in RENDER.glob("*/asr.jsonl"):
        for line in p.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            out.setdefault(r["guid"], r)
    return out


def db(x: float) -> float:
    return 20 * np.log10(max(x, 1e-9))


def deep_check(path: Path) -> tuple[list[str], dict]:
    x, sr = sf.read(str(path), dtype="float32")
    if x.ndim > 1:
        x = x.mean(axis=1)
    notes, stats = [], {}
    peak = float(np.max(np.abs(x))) if len(x) else 0.0
    stats["peak_db"] = round(db(peak), 1)
    if len(x) and float(np.mean(np.abs(x) > 0.999)) > CLIP_FRAC:
        notes.append("clipping")
    win = int(0.02 * sr)
    n = len(x) // win
    if n < 2:
        return notes + ["almost_empty"], stats
    env = np.sqrt(np.mean(x[: n * win].reshape(n, win) ** 2, axis=1))
    quiet = env < 10 ** (SILENCE_DB / 20)
    stats["silence_frac"] = round(float(quiet.mean()), 2)
    if quiet.mean() > 0.5:
        notes.append("mostly_silent")
    run = best = 0
    for q in quiet[int(0.3 / 0.02): -int(0.3 / 0.02) or None]:    # ignore the natural lead-in and tail
        run = run + 1 if q else 0
        best = max(best, run)
    stats["longest_gap_s"] = round(best * 0.02, 2)
    if best * 0.02 > GAP_S:
        notes.append("long_gap")
    body, intro = env[int(1.0 / 0.02):], env[: int(1.0 / 0.02)]
    if len(body) > 25 and len(intro) > 10 and db(float(np.sqrt(np.mean(body ** 2)))) - db(float(np.sqrt(np.mean(intro ** 2)))) > INTRO_QUIET_DB:
        notes.append("quiet_intro")
    tail = x[-int(TAIL_S * sr):]
    if len(tail) and db(float(np.sqrt(np.mean(tail ** 2)))) - db(float(np.sqrt(np.mean(x ** 2)))) > TAIL_REL_DB:
        notes.append("abrupt_end")
    return notes, stats


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--export", default="export_all_night")
    ap.add_argument("--top-pct", type=float, default=5.0)
    ap.add_argument("--out", default=str(RENDER / "audit/render_audit.json"))
    a = ap.parse_args()
    root = RENDER / a.export
    if (root / "index.json").is_file():
        index = json.loads((root / "index.json").read_text(encoding="utf-8"))
    else:          # a stitched run has a manifest, not an index: audit its clips the same way
        index = {r["guid"]: {"wav": f"wav/{r['guid']}.wav", "text": r.get("text", ""), "speaker": r.get("speaker")}
                 for r in map(json.loads, (root / "manifest.jsonl").read_text(encoding="utf-8").splitlines()) if r.get("status") == "ok"}
    rows = []
    for guid, e in index.items():
        path = root / e["wav"]
        row = {"guid": guid, "speaker": e.get("speaker"), "text": spoken(e.get("text", "")), "wav": str(path), "problems": []}
        try:
            info = sf.info(str(path))
        except Exception as ex:  # unreadable file is itself a finding
            row.update(seconds=0.0, problems=[f"unreadable: {ex}"])
            rows.append(row)
            continue
        row["seconds"] = round(info.duration, 2)
        row["bytes"] = path.stat().st_size
        implied = info.frames * info.channels * 2 + 44          # 16-bit PCM wav
        if info.subtype == "PCM_16" and abs(row["bytes"] - implied) > 1024:
            row["problems"].append(f"size_mismatch {row['bytes']} vs {implied}")
        if info.samplerate != SR or info.channels != 1:
            row["problems"].append(f"format {info.samplerate}Hz x{info.channels}")
        row["chars"] = len(row["text"])
        row["sec_per_char"] = round(info.duration / max(1, row["chars"]), 4)
        rows.append(row)
    secs = np.array([r["seconds"] for r in rows])
    cut = float(np.percentile(secs, 100 - a.top_pct))
    rate = np.array([r["sec_per_char"] for r in rows if r.get("chars", 0) > 20])
    med = float(np.median(rate))
    mad = float(np.median(np.abs(rate - med))) or 1e-6
    asr = load_asr()
    flagged = []
    for r in rows:
        why = []
        if r["seconds"] >= cut:
            why.append(f"top_{a.top_pct:g}pct_length")
        if r.get("chars", 0) > 20:
            z = 0.6745 * (r["sec_per_char"] - med) / mad
            r["rate_z"] = round(float(z), 1)
            if abs(z) > OUTLIER_Z:
                why.append("rate_outlier_slow" if z > 0 else "rate_outlier_fast")
        if r["problems"]:
            why.append("file_problem")
        a_row = asr.get(r["guid"])
        if a_row and set(a_row.get("flags", [])) & BAD_ASR:
            r["asr_flags"], r["heard"] = a_row["flags"], a_row.get("heard", "")
            why.append("asr_" + "_".join(f.replace("asr_", "") for f in a_row["flags"] if f in BAD_ASR))
        if why:
            r["why"] = why
            flagged.append(r)
    for i, r in enumerate(flagged):
        if i and i % 200 == 0:
            print(f"  deep-checking {i}/{len(flagged)}", file=sys.stderr)
        if Path(r["wav"]).is_file() and r["seconds"] > 0:
            notes, stats = deep_check(Path(r["wav"]))
            r["problems"] += notes
            r.update(stats)
    for r in flagged:
        hard = [p for p in r["problems"] if not p.startswith("format")]
        r["verdict"] = "listen" if hard or any(w.startswith(("rate_outlier", "asr_")) for w in r["why"]) else "probably_fine"
    flagged.sort(key=lambda r: (r["verdict"] != "listen", -len(r["problems"]), -r["seconds"]))
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps({"export": a.export, "clips": len(rows), "length_cutoff_s": round(cut, 1),
                                       "median_sec_per_char": round(med, 4), "flagged": flagged}, indent=1, ensure_ascii=False), encoding="utf-8")
    listen = [r for r in flagged if r["verdict"] == "listen"]
    print(f"{len(rows)} clips; top {a.top_pct:g}% = {cut:.1f}s and longer; flagged {len(flagged)}; listen first: {len(listen)}")
    from collections import Counter
    print("reasons:", dict(Counter(w for r in flagged for w in r["why"])))
    print("problems:", dict(Counter(p.split()[0] for r in flagged for p in r["problems"])))
    print("wrote", a.out)


if __name__ == "__main__":
    main()
