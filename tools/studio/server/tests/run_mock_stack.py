#!/usr/bin/env python3
"""Serve the studio against a throwaway fake repo and a mock model backend. No GPU, no real data.

  python3 tests/run_mock_stack.py <dir> [--port 8931]
"""
import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from conftest import make_repo  # noqa: E402
from mock_backend import MockBackend  # noqa: E402
from studio_server.app import make_server  # noqa: E402
from studio_server.model import ModelClient  # noqa: E402

REAL_REPO = Path(__file__).resolve().parents[4]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--port", type=int, default=8931)
    ap.add_argument("--backend", help="use this real model backend (remote mode) instead of the mock; data stays in <dir>")
    ap.add_argument("--ref-wav", help="copy this real clip over the fake Pasqal clips so a real model has something to clone")
    a = ap.parse_args()
    root = Path(a.dir)
    marker = root / ".mock_stack"
    if root.exists() and any(root.iterdir()) and not marker.exists():
        raise SystemExit(f"refusing to write fixtures into {root}: it is not empty and was not made by this script")
    root.mkdir(parents=True, exist_ok=True)
    marker.write_text("throwaway fake repo made by run_mock_stack.py\n", encoding="utf-8")
    cfg = make_repo(root)
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
    make_server(cfg, model, a.port).serve_forever()


if __name__ == "__main__":
    main()
