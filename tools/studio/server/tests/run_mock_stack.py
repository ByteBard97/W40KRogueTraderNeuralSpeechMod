#!/usr/bin/env python3
"""Serve the studio against a throwaway fake repo and a mock model backend. No GPU, no real data.

  python3 tests/run_mock_stack.py <dir> [--port 8931]
"""
import argparse
import json
import math
import random
import shutil
import struct
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from conftest import make_repo  # noqa: E402
from mock_backend import MockBackend  # noqa: E402
from studio_server.app import make_server  # noqa: E402
from studio_server.model import ModelClient  # noqa: E402

REAL_REPO = Path(__file__).resolve().parents[4]
# What the pedalboard page reads from the repo (read-only inputs, copied so a Save in a test can only write into the fake root).
PEDALBOARD_COPIES = ("tools/fx_lab/faust/blocks.lib", "tools/fx_lab/faust/catalog.json")
PEDALBOARD_SPEAKER = "Tester"        # one name for the Render Lab speaker and the game-voice reference, so choosing it loads both
FIXTURE_SR = 24000
FIXTURE_SECONDS = 3.0


def _speechish(n: int, sr: int, seed: int, phase: float) -> list[float]:
    """Voiced-looking noise: a 120 Hz buzz with harmonics and breath noise under a syllable-rate envelope. `phase` decorrelates L from R."""
    rng = random.Random(seed)
    out = []
    for i in range(n):
        t = i / sr
        env = max(0.0, math.sin(2 * math.pi * 3.0 * t)) ** 2
        buzz = sum(math.sin(2 * math.pi * 120 * k * t + phase * k) / k for k in range(1, 12))
        out.append(0.25 * env * (0.6 * buzz + 0.4 * (rng.random() * 2 - 1)))
    return out


def write_pcm16(path: Path, channels: list[list[float]], sr: int = FIXTURE_SR) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = b"".join(struct.pack("<" + "h" * len(channels), *(int(max(-1.0, min(1.0, c[i])) * 32767) for c in channels))
                      for i in range(len(channels[0])))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(len(channels)); w.setsampwidth(2); w.setframerate(sr); w.writeframes(frames)


def add_pedalboard_fixtures(root: Path) -> None:
    """Make the pedalboard page usable on the fake root: block library, starters, one Render Lab speaker with one wav line and
    one stereo game-voice reference. The vendored FaustWasm is served from the real repo by the app (read-only), and graphs/presets
    start empty under <root>/data/fx_lab and <root>/tools/fx_lab/faust/presets."""
    for rel in PEDALBOARD_COPIES:
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REAL_REPO / rel, root / rel)
    shutil.copytree(REAL_REPO / "tools/fx_lab/starters", root / "tools/fx_lab/starters", dirs_exist_ok=True)
    n = int(FIXTURE_SR * FIXTURE_SECONDS)
    line = {"guid": "e2e-line-1", "parent": "e2e-cue", "text": "The machine spirit is displeased.", "ref": {"wav": "prompts/Tester/01.wav"},
            "speaker": PEDALBOARD_SPEAKER, "annotation": {}, "speaker_kind": "unit"}
    (root / "data/render").mkdir(parents=True, exist_ok=True)
    (root / "data/render/jobs_cast_all.jsonl").write_text(json.dumps(line) + "\n", encoding="utf-8")
    write_pcm16(root / "data/render/cast/wav/e2e-line-1.wav", [_speechish(n, FIXTURE_SR, 1, 0.0)])
    ref_dir = root / "data/voices/wav/Tester"
    for k in (1, 2):
        write_pcm16(ref_dir / f"R{k}.wav", [_speechish(n, FIXTURE_SR, 10 + k, 0.0), _speechish(n, FIXTURE_SR, 20 + k, 1.3)])
    cat_path = root / "data/voices/catalog.json"
    cat = json.loads(cat_path.read_text(encoding="utf-8"))
    for k in (1, 2):
        cat[f"R{k}"] = {"event": f"R{k}", "speaker": PEDALBOARD_SPEAKER, "wav": f"wav/Tester/R{k}.wav", "duration": FIXTURE_SECONDS, "texts": []}
    cat_path.write_text(json.dumps(cat), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--port", type=int, default=8931)
    ap.add_argument("--backend", help="use this real model backend (remote mode) instead of the mock; data stays in <dir>")
    ap.add_argument("--ref-wav", help="copy this real clip over the fake Pasqal clips so a real model has something to clone")
    ap.add_argument("--pedalboard", action="store_true", help="also add what the pedalboard page needs (see add_pedalboard_fixtures)")
    ap.add_argument("--dist", help="serve this web build instead of tools/studio/web/dist (lets a test build leave the real dist alone)")
    a = ap.parse_args()
    root = Path(a.dir)
    marker = root / ".mock_stack"
    if root.exists() and any(root.iterdir()) and not marker.exists():
        raise SystemExit(f"refusing to write fixtures into {root}: it is not empty and was not made by this script")
    root.mkdir(parents=True, exist_ok=True)
    marker.write_text("throwaway fake repo made by run_mock_stack.py\n", encoding="utf-8")
    cfg = make_repo(root)
    if a.pedalboard:
        add_pedalboard_fixtures(root)
    real_venv, link = REAL_REPO / "tools/fx_lab/.venv-fx", root / "tools/fx_lab/.venv-fx"
    if real_venv.is_dir() and not link.exists():
        link.symlink_to(real_venv)          # lets "apply FX" run for real (CPU only) on the fake data
    if a.ref_wav:
        for n in ("E1", "E2"):
            shutil.copyfile(a.ref_wav, cfg.voices / f"wav/Pasqal/{n}.wav")
    if a.backend:
        model, what = ModelClient(a.backend, root=cfg.root, live_dir=cfg.voice_design, remote=True), f"real model at {a.backend}"
    else:
        model, what = ModelClient(MockBackend(cfg.voice_design).url), "mock model"
    print(f"Voice Studio ({what}, fake data in {root}) on http://127.0.0.1:{a.port}", flush=True)
    make_server(cfg, model, a.port, Path(a.dist) if a.dist else None).serve_forever()


if __name__ == "__main__":
    main()
