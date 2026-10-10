from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from .config import Config
from .errors import ApiError
from .jsonio import read_json
from .speakers import studio_dir, wav_dur
from .store import read_takes, update_take

FX_TIMEOUT_S = 120
PREVIEW_CACHE_MAX = 32
PREVIEW_SEP = "|"
_PREVIEW: dict[tuple, bytes] = {}


def list_presets(cfg: Config) -> list[str]:
    names = [s["name"] for s in read_json(cfg.root / "tools/fx_lab/scenarios.json", {"scenarios": []})["scenarios"]]
    names += [n for n in read_json(cfg.data / "fx_lab/presets.json", {}) if n not in names]
    return names


def _run_fx(cfg: Config, src: Path, out: Path, presets: list[str], missing_status: int = 500) -> None:
    py = cfg.root / "tools/fx_lab/.venv-fx/bin/python"
    if not py.is_file():
        raise ApiError(missing_status, "tools/fx_lab/.venv-fx is missing: the FX chain needs that environment (soundfile, DawDreamer)")
    out.parent.mkdir(parents=True, exist_ok=True)
    script = Path(__file__).with_name("fx_apply.py")
    try:
        r = subprocess.run([str(py), str(script), "--in", str(src), "--out", str(out)]
                           + [a for n in presets for a in ("--preset", n)], capture_output=True, text=True,
                           timeout=FX_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        raise ApiError(500, f"FX took longer than {FX_TIMEOUT_S}s and was stopped")
    if r.returncode != 0:
        raise ApiError(500, ((r.stderr or r.stdout).strip().splitlines() or ["fx failed"])[-1][:300])


def default_sample(cfg: Config) -> Path | None:
    """A Pasqal clip (the FX Lab's own test voice): the first prompt-bank clip, else the first catalogue clip."""
    for p in (read_json(cfg.voices / "prompts/prompts.json", {}).get("Pasqal") or []):
        f = cfg.voices / p.get("wav", "")
        if p.get("wav") and f.is_file():
            return f
    for c in read_json(cfg.voices / "catalog.json", {}).values():
        f = cfg.voices / c.get("wav", "")
        if c.get("speaker") == "Pasqal" and c.get("wav") and f.is_file():
            return f
    return None


def render_preview(cfg: Config, presets: list[str], path: str = "") -> bytes:
    """A wav with the preset chain applied, for auditioning a preset in the library. `path` is a repo wav under a served
    root; blank means the default Pasqal sample. Cached on (file, mtime, chain). 501 if the FX environment is missing."""
    known = list_presets(cfg)
    if not presets or any(n not in known for n in presets):
        raise ApiError(400, "presets must be a non-empty list of library preset names")
    src = cfg.resolve_file(path) if path else default_sample(cfg)
    if src is None or src.suffix != ".wav":
        raise ApiError(404, "no such wav" if path else "no default Pasqal sample clip found")
    key = (str(src), src.stat().st_mtime_ns, tuple(presets))
    hit = _PREVIEW.get(key)
    if hit is not None:
        return hit
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "fx.wav"
        _run_fx(cfg, src, out, presets, missing_status=501)
        data = out.read_bytes()
    if len(_PREVIEW) >= PREVIEW_CACHE_MAX:
        _PREVIEW.clear()
    _PREVIEW[key] = data
    return data


def apply_to_take(cfg: Config, slug: str, take_id: str, presets: list[str]) -> dict:
    take = read_takes(cfg, slug).get(take_id)
    if take is None:
        raise ApiError(404, f"no take '{take_id}'")
    if not presets:
        return update_take(cfg, slug, take_id, fx=None)
    out = studio_dir(cfg, slug) / "fx" / f"{take_id}.wav"
    _run_fx(cfg, cfg.root / take["raw"], out, presets)
    return update_take(cfg, slug, take_id, fx={"presets": presets, "wav": f"data/studio/{slug}/fx/{take_id}.wav",
                                               "v": out.stat().st_mtime_ns,
                                               "dur": wav_dur(out)})
