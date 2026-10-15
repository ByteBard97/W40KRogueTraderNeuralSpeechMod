import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import merge_fx  # noqa: E402


def make_export(root: Path, entries: dict, skip_wav=()):
    (root / "wav").mkdir(parents=True)
    for guid, extra in entries.items():
        if guid not in skip_wav:
            (root / "wav" / f"{guid}.wav").write_bytes(f"{root.name}-{guid}".encode())
    (root / "index.json").write_text(json.dumps({g: {"wav": f"wav/{g}.wav", "speaker": "s", **e} for g, e in entries.items()}))


def tree_hash(root: Path):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob("*")) if p.is_file()}


def setup(tmp_path, fx_skip=()):
    base, fx = tmp_path / "base", tmp_path / "fx"
    make_export(base, {"a": {}, "b": {"loudness": "preset"}, "c": {}})
    make_export(fx, {"a": {"fx": ["x"], "fx_key": "k", "channels": 2}, "b": {"loudness": "preset", "fx": ["y"], "channels": 1},
                     "z": {"fx": ["w"], "channels": 2}}, skip_wav=fx_skip)
    return base, fx, tmp_path / "out"


def test_merge_replaces_keeps_and_carries_fields(tmp_path):
    base, fx, out = setup(tmp_path)
    assert merge_fx.merge(base, fx, out) == (2, 1, 1)
    idx = json.loads((out / "index.json").read_text())
    assert set(idx) == {"a", "b", "c", "z"}
    assert idx["a"]["channels"] == 2 and idx["a"]["fx"] == ["x"] and idx["a"]["fx_key"] == "k"
    assert idx["b"]["loudness"] == "preset" and idx["b"]["channels"] == 1
    assert "fx" not in idx["c"]
    assert (out / "wav/a.wav").read_bytes() == b"fx-a"
    assert (out / "wav/c.wav").read_bytes() == b"base-c"
    assert (out / "wav/z.wav").read_bytes() == b"fx-z"


def test_hard_links_and_inputs_untouched(tmp_path):
    base, fx, out = setup(tmp_path)
    before = (tree_hash(base), tree_hash(fx))
    merge_fx.merge(base, fx, out)
    assert os.path.samefile(out / "wav/a.wav", fx / "wav/a.wav")
    assert os.path.samefile(out / "wav/c.wav", base / "wav/c.wav")
    assert (tree_hash(base), tree_hash(fx)) == before


def test_idempotent_and_swaps_stale_links(tmp_path):
    base, fx, out = setup(tmp_path)
    merge_fx.merge(base, fx, out)
    first = tree_hash(out)
    assert merge_fx.merge(base, fx, out) == (2, 1, 1)
    assert tree_hash(out) == first
    (out / "wav/a.wav").unlink()                   # a stale copy of the raw line from an earlier merge
    os.link(base / "wav/a.wav", out / "wav/a.wav")
    before = tree_hash(base)
    merge_fx.merge(base, fx, out)
    assert (out / "wav/a.wav").read_bytes() == b"fx-a"
    assert tree_hash(base) == before


def test_missing_fx_wav_is_skipped_with_warning(tmp_path, capsys):
    base, fx, out = setup(tmp_path, fx_skip=("a",))
    assert merge_fx.merge(base, fx, out) == (1, 2, 1)
    assert "warning: a" in capsys.readouterr().err
    assert (out / "wav/a.wav").read_bytes() == b"base-a"
    assert "fx" not in json.loads((out / "index.json").read_text())["a"]
