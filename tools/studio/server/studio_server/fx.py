from __future__ import annotations

import subprocess
from pathlib import Path

from .config import Config
from .errors import ApiError
from .jsonio import read_json
from .speakers import studio_dir
from .store import read_takes, update_take

FX_TIMEOUT_S = 120


def list_presets(cfg: Config) -> list[str]:
    names = [s["name"] for s in read_json(cfg.root / "tools/fx_lab/scenarios.json", {"scenarios": []})["scenarios"]]
    names += [n for n in read_json(cfg.data / "fx_lab/presets.json", {}) if n not in names]
    return names


def apply_to_take(cfg: Config, slug: str, take_id: str, presets: list[str]) -> dict:
    take = read_takes(cfg, slug).get(take_id)
    if take is None:
        raise ApiError(404, f"no take '{take_id}'")
    if not presets:
        return update_take(cfg, slug, take_id, fx=None)
    py = cfg.root / "tools/fx_lab/.venv-fx/bin/python"
    if not py.is_file():
        raise ApiError(500, "tools/fx_lab/.venv-fx is missing")
    out = studio_dir(cfg, slug) / "fx" / f"{take_id}.wav"
    out.parent.mkdir(parents=True, exist_ok=True)
    script = Path(__file__).with_name("fx_apply.py")
    try:
        r = subprocess.run([str(py), str(script), "--in", str(cfg.root / take["raw"]), "--out", str(out)]
                           + [a for n in presets for a in ("--preset", n)], capture_output=True, text=True,
                           timeout=FX_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        raise ApiError(500, f"FX took longer than {FX_TIMEOUT_S}s and was stopped")
    if r.returncode != 0:
        raise ApiError(500, ((r.stderr or r.stdout).strip().splitlines() or ["fx failed"])[-1][:300])
    return update_take(cfg, slug, take_id, fx={"presets": presets, "wav": f"data/studio/{slug}/fx/{take_id}.wav",
                                               "v": out.stat().st_mtime_ns})
