#!/usr/bin/env python3
"""Import in-game flags (flags.jsonl from the Dialogue Flag mod) into Render QA verdicts.

Verdicts are guid -> {verdict, tags, note}, the same file Voice Studio's /qa page reads and writes.
Dry run by default; --write backs the verdicts file up to .bak first. The flag's own text is only a
hint (it comes from the dialog cue showing at play time); the guid is the key.
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PREFIX = Path("/mnt/games/SteamLibrary/steamapps/compatdata/2186680/pfx/drive_c/users/steamuser/AppData/LocalLow"
              "/Owlcat Games/Warhammer 40000 Rogue Trader/UnityModManager/DialogueFlag")
IN_GAME_TAG = "in-game"
MAX_NEARBY = 8
CONFIDENT_AGO_S = 8.0


def load_flags(path: Path) -> list[dict]:
    flags = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            flags.append(json.loads(line))
        except json.JSONDecodeError:
            print(f"skipping unreadable line {n} in {path.name}", file=sys.stderr)
    return flags


def latest_per_guid(flags: list[dict]) -> dict[str, dict]:
    latest: dict[str, dict] = {}
    for f in sorted(flags, key=lambda f: f.get("ts", "")):
        if f.get("guid") and f.get("verdict") in ("good", "bad"):
            latest[f["guid"]] = f
    return latest


def is_confident(f: dict) -> bool:
    """The picked line was still playing, or started a few seconds before the key press."""
    return bool(f.get("still_playing")) or (f.get("heard_s_ago") or 0) <= CONFIDENT_AGO_S


def nearby(f: dict) -> list[dict]:
    """Other lines played in the window before the key press, nearest first, excluding the picked one."""
    cands = [c for c in (f.get("candidates") or []) if c.get("event") != f.get("event")]
    return sorted(cands, key=lambda c: c.get("ago_s", 0))[:MAX_NEARBY]


def note_for(f: dict) -> str:
    parts = [f"in-game {f['ts']}, heard {f.get('heard_s_ago')}s before the key press"]
    if f.get("still_playing"):
        parts.append("still playing")
    if f.get("text"):
        parts.append(f"cue then: {f['text'][:120]}")
    if not is_confident(f):
        parts.append("NOT SURE this is the line, see ingame_candidates.json")
    return "; ".join(parts)


def clip_info(guid: str, index: dict) -> dict:
    row = index.get(guid, {})
    return {"guid": guid, "text": row.get("text"), "speaker": row.get("speaker"), "wav": row.get("wav")}


def build_review(unsure: list[dict], index: dict) -> list[dict]:
    """One entry per late key press: the picked line and the others played just before, to audition by ear."""
    out = []
    for f in unsure:
        out.append({
            "ts": f["ts"], "verdict": f["verdict"],
            "picked": {**clip_info(f["guid"], index), "ago_s": f.get("heard_s_ago")},
            "nearby": [{**clip_info(c["event"].removeprefix("ev_"), index), "ago_s": c.get("ago_s")}
                       for c in nearby(f)],
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--flags", type=Path, default=PREFIX / "flags.jsonl")
    ap.add_argument("--run", default="export", help="'export' (default) or a run name under data/render/audit")
    ap.add_argument("--write", action="store_true", help="write the verdicts file (default is a dry run)")
    a = ap.parse_args()

    audit = ROOT / "data/render/audit"
    vpath = audit / ("verdicts.json" if a.run == "export" else f"verdicts_{a.run}.json")
    # the installed banks hold export_all_new (narrator + p01 + redos), so resolve guids against it as well as the old export
    index = {}
    for name in ("export", "export_all_new"):
        path = ROOT / "data/render" / name / "index.json"
        if path.exists():
            index.update(json.loads(path.read_text()))
    known = set(index) if a.run == "export" else None

    flags = load_flags(a.flags)
    sure = [f for f in flags if is_confident(f)]
    unsure = [f for f in flags if not is_confident(f) and f.get("verdict") in ("good", "bad")]
    latest = latest_per_guid(sure)
    verdicts = json.loads(vpath.read_text()) if vpath.exists() else {}
    added, unknown = {}, []
    for guid, f in latest.items():
        if known is not None and guid not in known:
            unknown.append(f)
            continue
        tags = sorted(set(verdicts.get(guid, {}).get("tags", [])) | {IN_GAME_TAG})
        added[guid] = {"verdict": f["verdict"], "tags": tags, "note": note_for(f)}

    bad = sum(v["verdict"] == "bad" for v in added.values())
    print(f"{len(latest)} flagged lines: {len(added)} importable ({bad} bad, {len(added) - bad} good) into {vpath.name}")
    for f in unknown:
        print(f"  not in the {a.run} render, left out: {f['guid']} {f.get('verdict')} {(f.get('text') or '')[:70]!r}")
    for guid, v in added.items():
        print(f"  {v['verdict']:4} {guid} {'(overwrites ' + verdicts[guid]['verdict'] + ')' if guid in verdicts else ''}")
    review = build_review(unsure, index)
    print(f"{len(unsure)} flags where the picked line was not playing (key pressed late): "
          f"{len(review)} to listen to, not given verdicts")
    for r in review:
        print(f"  {r['verdict']:4} {r['ts']} picked {r['picked']['guid']} + {len(r['nearby'])} nearby")
    if not a.write:
        print("dry run, nothing written (add --write)")
        return 0
    if review:
        rpath = audit / "ingame_candidates.json"
        rpath.write_text(json.dumps(review, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"wrote {rpath}")
    if vpath.exists():
        shutil.copy2(vpath, vpath.with_suffix(".json.bak"))
    verdicts.update(added)
    tmp = vpath.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(verdicts, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(vpath)
    print(f"wrote {vpath}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
