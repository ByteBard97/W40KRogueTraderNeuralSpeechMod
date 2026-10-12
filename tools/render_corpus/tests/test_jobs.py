import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/render_corpus"))
sys.path.insert(0, str(ROOT / "src/TtsSidecar"))

import pytest  # noqa: E402
from jobs import bucket_of, choose_engine, decode_binary, parse_buckets, select_jobs, take_problem  # noqa: E402
from merge import merge  # noqa: E402
from prerendered import load_index, lookup  # noqa: E402


def test_bucket_is_stable_and_in_range():
    assert bucket_of("abc") == bucket_of("abc")
    assert all(0 <= bucket_of(f"g{i}") < 100 for i in range(500))


def test_buckets_cover_without_overlap():
    a, b = parse_buckets("0-69"), parse_buckets("70-99")
    assert not set(a) & set(b) and len(a) + len(b) == 100
    assert list(parse_buckets("5")) == [5]
    with pytest.raises(ValueError):
        parse_buckets("90-120")


def test_engine_split_on_length():
    assert choose_engine("Lord Captain?") == "qwen3_tts"
    assert choose_engine("x" * 80) == "voxcpm2"


def test_take_problem():
    assert take_problem("x" * 100, 0.2) == "too_short"
    assert take_problem("x" * 20, 30.0) == "too_long"
    assert take_problem("x" * 200, 4.0) == "too_fast"
    assert take_problem("x" * 100, 7.0) is None
    assert take_problem("Ah!", 1.3) is None                       # tiny lines legitimately run long per character
    assert take_problem("x" * 247, 198.4) == "too_long"           # the Pasqal runaway


def test_select_jobs_filters_and_orders():
    jobs = [{"guid": "b", "engine": "voxcpm2", "bucket": 5, "priority": 1},
            {"guid": "a", "engine": "voxcpm2", "bucket": 5, "priority": 1},
            {"guid": "c", "engine": "voxcpm2", "bucket": 5, "priority": 0},
            {"guid": "d", "engine": "qwen3_tts", "bucket": 5, "priority": 0},
            {"guid": "e", "engine": "voxcpm2", "bucket": 90, "priority": 0},
            {"guid": "f", "engine": "voxcpm2", "bucket": 5, "priority": 0}]
    got = select_jobs(jobs, "voxcpm2", range(0, 70), {"f"})
    assert [j["guid"] for j in got] == ["c", "a", "b"]


def test_merge_and_guid_match(tmp_path):
    for name, guid in (("linux", "g1"), ("mac", "g2")):
        d = tmp_path / name
        (d / "wav").mkdir(parents=True)
        (d / "wav" / f"{guid}.wav").write_bytes(b"RIFF")
        row = {"guid": guid, "status": "ok", "src_text": '"Hi"', "text": "Hi", "seconds": 1.0, "speaker": "X", "engine": "e",
               "voice_source": "fallback"}
        (d / "manifest.jsonl").write_text(json.dumps(row) + "\n")
    assert merge(tmp_path, ["linux", "mac"]) == 2
    assert merge(tmp_path, ["linux", "mac"]) == 2  # idempotent
    idx = load_index(tmp_path / "bon", tmp_path)
    assert lookup(idx, "g1", "different display text").name == "g1.wav"
    assert lookup(idx, "missing", "x") is None


def test_merge_skips_runaway_takes(tmp_path):
    d = tmp_path / "linux"
    (d / "wav").mkdir(parents=True)
    rows = [{"guid": "good", "status": "ok", "src_text": "x", "text": "x" * 100, "seconds": 7.0, "speaker": "A", "engine": "e", "voice_source": "v"},
            {"guid": "bad", "status": "ok", "src_text": "x", "text": "x" * 247, "seconds": 198.4, "speaker": "A", "engine": "e", "voice_source": "v"}]
    for r in rows:
        (d / "wav" / f"{r['guid']}.wav").write_bytes(b"RIFF")
    (d / "manifest.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
    assert merge(tmp_path, ["linux"]) == 1
    assert list(json.loads((tmp_path / "export/index.json").read_text())) == ["good"]


def test_decode_binary_runs():
    bits = "".join(f"{ord(c):08b}" for c in "Manual Configuration")
    assert decode_binary(f"ERROR. {bits} is required.") == "ERROR. Manual Configuration is required."
    assert decode_binary("code 0110 only") == "code 0110 only"                 # short runs are left alone
    assert decode_binary("x " + "1" * 24 + " y") == "x binary code y"          # not text: say so instead
    assert decode_binary("room 1100110011001100110011 end").count("binary code") == 1   # length not a multiple of 8
