#!/usr/bin/env python3
"""Unattended generate -> score -> select -> retake loop for one character.

Stages run as subprocesses in their own envs (TTS in roguetts, scoring in .venv-scorer) and only
talk through files under data/bon/<speaker>/, so the loop is resumable after a reboot or crash.
Each stage first waits for enough free VRAM (the GPU is shared with games and other servers).

  python3 tools/scorer/loop.py [--speaker Abelard] [--base-takes 6] [--max-takes 12] [--min-pass 2]

Round 0 fills every line up to --base-takes. Later rounds add --retake-step takes only to lines
with fewer than --min-pass passing takes, up to --max-takes. At the end it writes winners.json,
review_queue.json (lines a human should hear) and export/ (winner wavs + index.json).
Runs with plain python3 (stdlib + numpy).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).parent))
from export_winners import export_winners  # noqa: E402
from gpu_guard import wait_for_free  # noqa: E402
from selection import calibration, plan_retakes, review_queue, select_winners  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
GEN_PY = "/home/geoff/anaconda3/envs/roguetts/bin/python3"
SCORE_PY = str(ROOT / "tools/scorer/.venv-scorer/bin/python")
GEN_VRAM_MB = 12000
SCORE_VRAM_MB = 5000


def read_jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def load_state(out: Path, scale: dict) -> tuple[list[dict], dict, dict]:
    manifest = read_jsonl(out / "manifest.jsonl")
    scores = {r["key"]: r["score"] for r in read_jsonl(out / "scores.jsonl")}
    return manifest, scores, select_winners(manifest, scores, scale)


def takes_per_line(manifest: list[dict]) -> dict[str, int]:
    n: dict[str, int] = {}
    for m in manifest:
        n[m["guid"]] = n.get(m["guid"], 0) + 1
    return n


def run_loop(speaker: str, out: Path, scale: dict, *, base_takes: int, max_takes: int, min_pass: int,
             retake_step: int, max_rounds: int, generate: Callable[[int, list[str] | None], None],
             score: Callable[[], None], log: Callable[[str], None] = print) -> dict:
    """Core loop with injected stage runners (unit-tested). Returns final winners."""
    log(f"round 0: fill every line to {base_takes} takes")
    generate(base_takes, None)
    score()
    manifest, scores, winners = load_state(out, scale)
    for rnd in range(1, max_rounds + 1):
        all_guids = sorted(takes_per_line(manifest))
        need = plan_retakes(winners, all_guids, min_pass, max_takes)
        if not need:
            log(f"round {rnd}: nothing left to retake")
            break
        have = takes_per_line(manifest)
        target = min(max_takes, max(have.get(g, 0) for g in need) + retake_step)
        log(f"round {rnd}: {len(need)} lines below {min_pass} passing takes -> up to {target} takes")
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(need, f)
        generate(target, need, Path(f.name))
        score()
        manifest, scores, winners = load_state(out, scale)
    return winners


def finalize(out: Path, winners: dict) -> None:
    (out / "winners.json").write_text(json.dumps(winners, ensure_ascii=False, indent=1), encoding="utf-8")
    queue = review_queue(winners)
    (out / "review_queue.json").write_text(json.dumps(queue, ensure_ascii=False, indent=1), encoding="utf-8")
    n = export_winners(out, winners)
    print(f"finalized: {len(winners)} lines, {n} exported, {len(queue)} in review queue", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--speaker", default="Abelard")
    ap.add_argument("--base-takes", type=int, default=6)
    ap.add_argument("--max-takes", type=int, default=12)
    ap.add_argument("--min-pass", type=int, default=2)
    ap.add_argument("--retake-step", type=int, default=2)
    ap.add_argument("--max-rounds", type=int, default=3)
    ap.add_argument("--cfg", type=float, default=3.0)
    ap.add_argument("--vram-timeout-h", type=float, default=12.0, help="give up waiting for free VRAM after this")
    args = ap.parse_args()

    out = ROOT / "data/bon" / args.speaker
    scale = calibration()

    def stage(cmd: list[str], need_mb: int) -> None:
        if not wait_for_free(need_mb, timeout_s=args.vram_timeout_h * 3600):
            raise SystemExit(f"timed out waiting for {need_mb} MiB free VRAM")
        t0 = time.time()
        subprocess.run(cmd, check=True, cwd=ROOT)
        print(f"stage done in {time.time() - t0:.0f}s: {Path(cmd[1]).name}", flush=True)

    def generate(takes: int, guids: list[str] | None, guids_file: Path | None = None) -> None:
        cmd = [GEN_PY, str(ROOT / "tools/scorer/bon_generate.py"), "--speaker", args.speaker,
               "--takes", str(takes), "--cfg", str(args.cfg)]
        if guids_file:
            cmd += ["--guids-file", str(guids_file)]
        stage(cmd, GEN_VRAM_MB)

    def score() -> None:
        stage([SCORE_PY, str(ROOT / "tools/scorer/bon_score.py"), "--speaker", args.speaker,
               "--asr-device", "cuda"], SCORE_VRAM_MB)

    winners = run_loop(args.speaker, out, scale, base_takes=args.base_takes, max_takes=args.max_takes,
                       min_pass=args.min_pass, retake_step=args.retake_step, max_rounds=args.max_rounds,
                       generate=generate, score=score)
    finalize(out, winners)


if __name__ == "__main__":
    main()
