#!/usr/bin/env python3
"""Build a merged export directory: the base export with the FX-processed lines winning over the raw ones.

  python3 tools/render_corpus/merge_fx.py --base data/render/export --fx data/render/export_fx --out data/render/export_merged

Every guid in the FX index replaces the base entry and wav, and keeps the FX entry's extra fields (fx, fx_key, channels, and
`"loudness": "preset"` if the base had it). Guids only in the base are kept as they are. wavs are hard-linked (copied when
linking fails), the base and FX directories are never touched, and a re-run swaps stale links atomically.
Feed the result to tools/bnk_patch/patch.py as --export: stereo FX wavs become stereo wems there.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from overlay_export import link  # noqa: E402


def merge(base: Path, fx: Path, out: Path) -> tuple[int, int, int]:
    """(replaced, kept, fx_only). FX entries whose wav is missing are skipped with a warning and the base line stays."""
    if out.resolve() in (base.resolve(), fx.resolve()):
        raise SystemExit("--out must be a different directory from --base and --fx")
    base_idx = json.loads((base / "index.json").read_text(encoding="utf-8"))
    fx_idx = json.loads((fx / "index.json").read_text(encoding="utf-8"))
    (out / "wav").mkdir(parents=True, exist_ok=True)
    merged, replaced, fx_only = {}, 0, 0
    use_fx = {}
    for guid, e in fx_idx.items():
        if not (fx / e["wav"]).is_file():
            print(f"warning: {guid}: FX wav {e['wav']} is missing, skipped", file=sys.stderr)
            continue
        use_fx[guid] = e
    for guid, e in base_idx.items():
        if guid in use_fx:
            continue
        link(base / e["wav"], out / "wav" / f"{guid}.wav")
        merged[guid] = {**e, "wav": f"wav/{guid}.wav"}
    for guid, e in use_fx.items():
        link(fx / e["wav"], out / "wav" / f"{guid}.wav")
        merged[guid] = {**e, "wav": f"wav/{guid}.wav"}
        if guid in base_idx:
            replaced += 1
        else:
            fx_only += 1
    kept = len(merged) - replaced - fx_only
    tmp = out / "index.json.new"
    tmp.write_text(json.dumps(merged, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(out / "index.json")
    return replaced, kept, fx_only


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, help="raw export dir (index.json + wav/)")
    ap.add_argument("--fx", required=True, help="FX export dir written by tools/fx_lab/batch.py")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    replaced, kept, fx_only = merge(Path(a.base), Path(a.fx), Path(a.out))
    print(f"{a.out}: {replaced} replaced by FX, {kept} kept from base, {fx_only} FX-only")


if __name__ == "__main__":
    main()
