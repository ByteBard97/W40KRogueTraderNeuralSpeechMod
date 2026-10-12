import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server  # noqa: E402


def test_safe_name_strips_path_tricks():
    assert server.safe_name("../../etc/passwd") == "etc_passwd"
    assert server.safe_name("   ") == "unnamed"


def test_make_profile_fills_defaults_and_drops_unknown():
    p = server.make_profile({"name": "a", "reference": {"wav": "x", "text": "t"}, "options": {"cfg": 3.0, "bogus": 1}})
    assert p["options"]["cfg"] == 3.0 and p["options"]["timesteps"] == 10 and "bogus" not in p["options"]


def test_in_roots_rejects_outside_and_missing(tmp_path):
    inside = tmp_path / "a.wav"
    inside.write_bytes(b"x")
    assert server.in_roots(inside, [tmp_path])
    assert not server.in_roots(tmp_path / "missing.wav", [tmp_path])
    assert not server.in_roots(inside, [tmp_path / "other"])


def test_sources_and_lines_load():
    src, ln = server.sources(), server.lines()
    assert len(src) == 45 and sum(1 for s in src if s["curated_rank"]) == 12
    assert len(ln) == 844 and all(l["baseline"] for l in ln)
