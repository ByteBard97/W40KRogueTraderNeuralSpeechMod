"""Register the automatic BG3 voice assignments (auto_cast.json) into the prompt bank, so the render planner can find them.

Each assigned item (owner picks and automatic) gets its voice's first reference clip copied into prompts/cast/ and an entry in prompts.json
under the item key, built by casting.register_one so it looks exactly like a hand-cast voice. The entry also carries `auto_cast`, `processed`
and `steps`: consumers read entries by name, so extra keys are harmless, and `auto_cast` is how a later run tells its own entries from a real
or hand-cast voice. A speaker that already has an entry which is not ours is never overwritten. Safe to run again: unchanged entries are left
alone. prompts.json is backed up first (prompts.<stamp>.bak.json beside it, at most one per BACKUP_GAP_S) and written atomically.
"""
from __future__ import annotations

import re
import shutil
import time
from datetime import datetime
from pathlib import Path

from . import auto_cast, casting
from .config import Config
from .jsonio import STATE_LOCK, read_json, write_json_atomic

BACKUP_GAP_S = 600
STAMP = "%Y%m%d-%H%M%S"
BACKUP_RE = re.compile(r"^prompts\.(\d{8}-\d{6})\.bak\.json$")


def _plan(cfg: Config) -> tuple[list[dict], list[dict], dict, dict]:
    """(to_do, skipped, prompts, catalog). Every assigned item lands in exactly one of the two lists."""
    p = casting._paths(cfg)
    catalog = {v["slug"]: v for v in casting._need(p["catalog"], "BG3 catalog")}
    prompts = read_json(p["prompts"], {}) or {}
    to_do, skipped, taken = [], [], {}
    for key, it in auto_cast.read(cfg)["items"].items():
        if it.get("status") != "assigned" or not it.get("bg3"):
            continue
        row = {"key": key, "bg3": it["bg3"], "processed": bool(it.get("processed")), "steps": it.get("steps")}
        voice = catalog.get(it["bg3"])
        clip = voice["refs"][0] if voice and voice.get("refs") else None
        if clip is None or not (cfg.root / clip["wav"]).is_file():
            skipped.append({**row, "reason": "the voice has no usable reference clip"})
            continue
        slug = casting._slug(key)
        existing = prompts.get(key)
        ours = bool(existing) and bool(existing[0].get("auto_cast"))
        if existing and not ours:
            skipped.append({**row, "reason": "already has a voice in the prompt bank (real or hand-cast), left alone"})
            continue
        if slug in taken:
            skipped.append({**row, "reason": f"file name clashes with {taken[slug]!r}"})
            continue
        if not ours and (p["cast"] / f"{slug}.wav").exists():
            skipped.append({**row, "reason": "a clip with this file name is already in the cast folder, left alone"})
            continue
        taken[slug] = key
        same = ours and existing[0].get("bg3") == it["bg3"] and (p["cast"] / f"{slug}.wav").is_file()
        action = "unchanged" if same and existing[0].get("processed") == row["processed"] and existing[0].get("steps") == row["steps"] else "update" if ours else "add"
        to_do.append({**row, "voice_name": voice.get("name") or it["bg3"], "clip": clip["wav"], "action": action, "same_clip": same})
    return to_do, skipped, prompts, catalog


def preview(cfg: Config) -> dict:
    """What a register would do, without touching anything."""
    to_do, skipped, _, _ = _plan(cfg)
    items = auto_cast.read(cfg)["items"]
    counts = {"assigned": len(to_do) + len(skipped), "not_assigned": sum(1 for i in items.values() if i.get("status") != "assigned"),
              "add": sum(1 for r in to_do if r["action"] == "add"), "update": sum(1 for r in to_do if r["action"] == "update"),
              "unchanged": sum(1 for r in to_do if r["action"] == "unchanged"), "skipped": len(skipped),
              "processed": sum(1 for r in to_do if r["processed"])}
    return {"counts": counts, "items": to_do, "skipped": skipped}


def _backup(prompts_path: Path, now: float) -> str | None:
    """Copy prompts.json beside itself unless a backup of ours is younger than BACKUP_GAP_S. Returns the new file name."""
    if not prompts_path.is_file():
        return None
    for f in prompts_path.parent.glob("prompts.*.bak.json"):
        m = BACKUP_RE.match(f.name)
        if m and 0 <= now - datetime.strptime(m.group(1), STAMP).timestamp() < BACKUP_GAP_S:
            return None
    dst = prompts_path.with_name(f"prompts.{time.strftime(STAMP, time.localtime(now))}.bak.json")
    shutil.copyfile(prompts_path, dst)
    return dst.name


def register(cfg: Config) -> dict:
    with STATE_LOCK:
        to_do, skipped, prompts, catalog = _plan(cfg)
        work = [r for r in to_do if r["action"] != "unchanged"]
        backup = None
        if work:
            path = casting._paths(cfg)["prompts"]
            backup = _backup(path, time.time())
            for r in work:
                casting.register_one(cfg, prompts, catalog, r["key"], r["bg3"])
                prompts[r["key"]][0].update(auto_cast=True, processed=r["processed"], steps=r["steps"])
            write_json_atomic(path, prompts)
    return {"registered": [r["key"] for r in work], "unchanged": len(to_do) - len(work), "skipped": skipped, "backup": backup}
