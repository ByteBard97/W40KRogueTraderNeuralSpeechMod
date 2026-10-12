#!/usr/bin/env python3
"""Join data/bakeoff_abelard_cfg_sweep/ratings.json (1-5 score per clip, two dimensions:
emotion delivery and voice/timbre match - 1 bad, 5 good) back to manifest.json's
cfg_value/repeat/guid, and report whether any pattern emerges - e.g. does a higher cfg_value
raise the voice-match score, at the cost of emotion delivery, or vice versa. Also joins in
reference-clip length (seconds + spoken word count) and output-clip length (seconds + target
word count), to check whether clip length predicts a "good on both dimensions" result
(GOOD_THRESHOLD, default score >= 4 on both).

Only counts clips that have been rated on a given dimension (unrated clips are silently
excluded from that dimension's stats). The "good on both" analysis only uses cells rated on
BOTH dimensions (a cell rated on just one can't be scored as good-on-both or not).

Run: python3 tools/tts_bakeoff/analyze_cfg_sweep_ratings.py
"""
from __future__ import annotations

import json
import re
import wave
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
SWEEP_ROOT = ROOT / "data/bakeoff_abelard_cfg_sweep"
MANIFEST_PATH = SWEEP_ROOT / "manifest.json"
RATINGS_PATH = SWEEP_ROOT / "ratings.json"
TAGS_PATH = SWEEP_ROOT / "tags.json"

GOOD_THRESHOLD = 4  # score >= this on a dimension counts as "good" for that dimension

_QUOTED = re.compile(r'"([^"]*)"')


def _spoken_only(ref_text: str) -> str:
    # Same extraction as tools/tts_engines/qwen3_tts.py's _spoken_only - reference transcripts
    # in this project's catalog interleave narration (never vocalized) with quoted dialogue
    # (what's actually in the audio). Word-counting the raw transcript would overcount for any
    # reference clip that has narration description attached.
    quotes = _QUOTED.findall(ref_text)
    return " ".join(q.strip() for q in quotes if q.strip()) or ref_text


def _wav_duration_seconds(path: Path) -> float | None:
    try:
        with wave.open(str(path), "rb") as f:
            return f.getnframes() / f.getframerate()
    except (FileNotFoundError, wave.Error):
        return None


def _word_count(text: str) -> int:
    return len(text.split())


def _tag_report(manifest: dict, ratings: dict) -> None:
    # Failure-tag rates by cfg_value. Tagging was added after the first lines were rated, so
    # clips with no tag are ambiguous (clean vs. rated before tagging). Restrict the
    # denominator to lines where at least one clip carries a tag, i.e. lines rated with tags on.
    if not TAGS_PATH.exists():
        return
    tags = json.loads(TAGS_PATH.read_text(encoding="utf-8"))
    if not tags:
        return
    tagged_lines = {manifest[c]["guid"] for c in tags if c in manifest}
    cells = [c for c, e in manifest.items() if e["guid"] in tagged_lines and c in ratings]
    print(f"\n=== Failure tags by cfg_value ({len(cells)} rated clips in {len(tagged_lines)} tagged line(s)) ===")
    cfgs = sorted({manifest[c]["cfg_value"] for c in cells})
    names = sorted({t for ts in tags.values() for t in ts})
    print("  tag        " + "".join(f"cfg {cfg:<5}" for cfg in cfgs))
    for name in names:
        row = []
        for cfg in cfgs:
            in_cfg = [c for c in cells if manifest[c]["cfg_value"] == cfg]
            hit = sum(1 for c in in_cfg if name in tags.get(c, []))
            row.append(f"{hit}/{len(in_cfg):<7}")
        print(f"  {name:<10} " + "".join(row))
    print("\n  mean emotion/voice score, tagged vs. untagged clips:")
    for label, sel in (("tagged", [c for c in cells if c in tags]),
                       ("untagged", [c for c in cells if c not in tags])):
        for dim in ("emotion", "voice"):
            v = [ratings[c][dim] for c in sel if dim in ratings[c]]
            print(f"    {label:<9} {dim:<8} " + (f"{sum(v)/len(v):.2f} (n={len(v)})" if v else "--"))
    if any("rushed" in ts for ts in tags.values()):
        wps = lambda c: _word_count(manifest[c]["text"]) / manifest[c]["audio_seconds"]
        r = [wps(c) for c in cells if "rushed" in tags.get(c, [])]
        o = [wps(c) for c in cells if "rushed" not in tags.get(c, [])]
        print(f"\n  words/sec: rushed-tagged {sum(r)/len(r):.2f} (n={len(r)}) vs. rest {sum(o)/len(o):.2f} (n={len(o)})")


def main() -> None:
    if not MANIFEST_PATH.exists():
        raise SystemExit(f"no sweep manifest at {MANIFEST_PATH}")
    manifest = {e["cell_id"]: e for e in json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))}
    ratings = {}
    if RATINGS_PATH.exists():
        ratings = json.loads(RATINGS_PATH.read_text(encoding="utf-8"))

    if not ratings:
        print("No ratings recorded yet - rate some clips at http://127.0.0.1:8902/sweep first.")
        return

    # dim -> cfg_value -> list of 1-5 scores
    by_cfg: dict[str, dict[float, list[int]]] = {
        "emotion": defaultdict(list), "voice": defaultdict(list),
    }
    # dim -> guid -> list of 1-5 scores (per-line breakdown, to catch line-specific effects)
    by_line: dict[str, dict[str, list[int]]] = {
        "emotion": defaultdict(list), "voice": defaultdict(list),
    }
    n_missing_manifest = 0

    for cell_id, dims in ratings.items():
        entry = manifest.get(cell_id)
        if entry is None:
            n_missing_manifest += 1
            continue
        cfg = entry["cfg_value"]
        guid = entry["guid"]
        for dim, val in dims.items():
            if dim not in by_cfg or not isinstance(val, int) or not 1 <= val <= 5:
                continue
            by_cfg[dim][cfg].append(val)
            by_line[dim][guid].append(val)

    if n_missing_manifest:
        print(f"warning: {n_missing_manifest} rated cell_ids not found in current sweep manifest "
              f"(stale ratings from a re-rendered/renamed cell)\n")

    print(f"=== By cfg_value (mean score, 1-5; 'good%' = share scoring >= {GOOD_THRESHOLD}) ===")
    for dim in ("emotion", "voice"):
        print(f"\n-- {dim} --")
        cfgs = sorted(by_cfg[dim])
        if not cfgs:
            print("  no ratings on this dimension yet")
            continue
        for cfg in cfgs:
            scores = by_cfg[dim][cfg]
            n = len(scores)
            mean = sum(scores) / n
            good_pct = 100 * sum(1 for s in scores if s >= GOOD_THRESHOLD) / n
            bar = "#" * round(mean / 5 * 20)
            print(f"  cfg {cfg:>4}: mean={mean:.2f}  good%={good_pct:5.1f}  n={n:<3} {bar}")

    print(f"\n=== By line (mean score per dim, n in parens) ===")
    all_guids = sorted(set(by_line["emotion"]) | set(by_line["voice"]))
    if not all_guids:
        print("  no ratings yet")
    for guid in all_guids:
        parts = []
        for dim in ("emotion", "voice"):
            scores = by_line[dim][guid]
            if scores:
                parts.append(f"{dim}={sum(scores)/len(scores):.1f}(n={len(scores)})")
            else:
                parts.append(f"{dim}=--")
        print(f"  {guid[:8]}: {'  '.join(parts)}")

    total_rated_cells = len(ratings)
    total_cells = len(manifest)
    print(f"\n{total_rated_cells}/{total_cells} clips have at least one rating.")

    _length_pattern_report(manifest, ratings)
    _tag_report(manifest, ratings)


def _length_pattern_report(manifest: dict, ratings: dict) -> None:
    # Ref-clip duration is cached per guid (same reference clip reused across cfg/repeat for a
    # given line) - reading 19 wav headers instead of up to 228.
    ref_duration_cache: dict[str, float | None] = {}
    ref_words_cache: dict[str, int] = {}

    rows = []  # one row per cell rated on BOTH dims
    for cell_id, dims in ratings.items():
        entry = manifest.get(cell_id)
        if entry is None or "emotion" not in dims or "voice" not in dims:
            continue
        e_score, v_score = dims["emotion"], dims["voice"]
        if not isinstance(e_score, int) or not isinstance(v_score, int):
            continue
        if not (1 <= e_score <= 5 and 1 <= v_score <= 5):
            continue
        guid = entry["guid"]
        ref = entry["reference"]
        if guid not in ref_duration_cache:
            ref_duration_cache[guid] = _wav_duration_seconds(ROOT / ref["wav"])
            ref_words_cache[guid] = _word_count(_spoken_only(ref["text"]))
        rows.append({
            "cell_id": cell_id,
            "guid": guid,
            "cfg_value": entry["cfg_value"],
            "ref_duration_s": ref_duration_cache[guid],
            "ref_words": ref_words_cache[guid],
            "output_duration_s": entry["audio_seconds"],
            "output_words": _word_count(entry["text"]),
            "emotion_score": e_score,
            "voice_score": v_score,
            "combined_score": (e_score + v_score) / 2,
            "good_on_both": e_score >= GOOD_THRESHOLD and v_score >= GOOD_THRESHOLD,
        })

    print(f"\n=== Good-on-both (score >= {GOOD_THRESHOLD} on both dims) vs. clip length "
          f"(cells rated on BOTH dimensions only) ===")
    if not rows:
        print("  no cells rated on both dimensions yet - need both emotion and voice rated "
              "on the same clip.")
        return
    n_good = sum(r["good_on_both"] for r in rows)
    print(f"  {len(rows)} cells rated on both dims, {n_good} good-on-both "
          f"({100 * n_good / len(rows):.1f}%)")

    features = [
        ("reference clip duration (s)", "ref_duration_s"),
        ("reference spoken word count", "ref_words"),
        ("output clip duration (s)", "output_duration_s"),
        ("output target word count", "output_words"),
    ]
    for label, key in features:
        vals = np.array([r[key] for r in rows if r[key] is not None], dtype=float)
        good = np.array([r["good_on_both"] for r in rows if r[key] is not None], dtype=float)
        combined = np.array([r["combined_score"] for r in rows if r[key] is not None], dtype=float)
        print(f"\n-- {label} --")
        if len(vals) < 6 or np.std(vals) == 0:
            print(f"  n={len(vals)}, not enough spread yet to bucket")
            continue
        # Two correlations: against the binary good-on-both flag, and against the raw
        # combined (emotion+voice)/2 score - the raw-score version uses the full 1-5
        # resolution instead of collapsing to a threshold, so it's the more sensitive signal
        # at small n even though both are crude linear reads, not proof of causation.
        corr_good = float(np.corrcoef(vals, good)[0, 1])
        corr_score = float(np.corrcoef(vals, combined)[0, 1])
        terciles = np.quantile(vals, [1 / 3, 2 / 3])
        bucket_names = ["low", "mid", "high"]
        bucket_idx = np.digitize(vals, terciles)
        print(f"  correlation with good-on-both: {corr_good:+.2f}  |  "
              f"with combined score: {corr_score:+.2f}  (n={len(vals)})")
        for b in range(3):
            mask = bucket_idx == b
            n = int(mask.sum())
            if n == 0:
                continue
            good_rate = 100 * good[mask].mean()
            mean_score = combined[mask].mean()
            vrange = f"{vals[mask].min():.1f}-{vals[mask].max():.1f}"
            print(f"  {bucket_names[b]:>4} ({vrange}): {good_rate:5.1f}% good-on-both, "
                  f"mean score {mean_score:.2f}  (n={n})")

    print("\n(Small-n caveat: with < ~30-50 double-rated clips these patterns are suggestive, "
          "not conclusive - re-run this after more ratings accumulate.)")


if __name__ == "__main__":
    main()
