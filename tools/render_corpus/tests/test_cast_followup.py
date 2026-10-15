import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cast_followup as cf  # noqa: E402


def put_lines(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def piece(guid, parent="c1", text="The servitor stood in the doorway for a long while."):
    return {"guid": guid, "parent": parent, "speaker": "Seberian", "text": text, "seg_index": 0, "engine": "voxcpm2", "priority": 1}


def render(root, guid, wer=0.0, flags=(), status="ok", seconds=3.4, error=None, text="The servitor stood in the doorway for a long while."):
    run = root / "data/render/cast"
    row = {"guid": guid, "status": status, "seconds": seconds, "text": text, "flags": []}
    if error:
        row["error"] = error
    with open(run / "manifest.jsonl", "a") as f:
        f.write(json.dumps(row) + "\n")
    if status == "ok":
        (run / "wav").mkdir(parents=True, exist_ok=True)
        (run / "wav" / f"{guid}.wav").write_bytes(b"x")
        with open(run / "asr.jsonl", "a") as f:
            f.write(json.dumps({"guid": guid, "wer": wer, "flags": list(flags), "heard": "heard text"}) + "\n")


def repo(tmp_path, *piece_guids):
    put_lines(tmp_path / "data/render/cast_jobs/cast-1.jsonl", [piece(g) for g in piece_guids])
    (tmp_path / "data/render/cast").mkdir(parents=True, exist_ok=True)
    return tmp_path


def test_a_clean_piece_is_usable_and_a_truncated_one_is_to_redo(tmp_path):
    root = repo(tmp_path, "a", "b")
    render(root, "a")
    render(root, "b", wer=0.5, flags=["asr_bad", "asr_truncated"])
    c = cf.classify(root)
    assert c["usable"] == ["a"] and c["redo"] == ["b"]


def test_a_plain_asr_bad_is_lenient_and_does_not_need_a_redo(tmp_path):
    root = repo(tmp_path, "a")
    render(root, "a", wer=0.3, flags=["asr_bad"])
    assert cf.classify(root)["usable"] == ["a"]


def test_queue_redo_writes_the_next_take_for_each_piece_that_needs_one(tmp_path):
    root = repo(tmp_path, "a", "b")
    render(root, "a")
    render(root, "b", flags=["asr_truncated"])
    state = {}
    assert cf.queue_redo(root, state) == 1
    rows = [json.loads(x) for x in (root / "data/render/cast_jobs/redo-01.jsonl").read_text().splitlines()]
    assert rows[0]["guid"] == "b@r1" and rows[0]["redo_of"] == "b" and rows[0]["parent"] == "c1" and "whisper" in rows[0]["redo_reason"]
    assert cf.queue_redo(root, state) == 1 and (root / "data/render/cast_jobs/redo-01.jsonl").is_file()        # not rendered yet: it would be asked again by the next idle pass


def test_a_clean_redo_take_makes_the_piece_usable(tmp_path):
    root = repo(tmp_path, "b")
    render(root, "b", flags=["asr_truncated"])
    render(root, "b@r1")
    assert cf.classify(root)["usable"] == ["b"]


def test_a_failed_render_is_redone_and_a_second_redo_follows_a_second_failure(tmp_path):
    root = repo(tmp_path, "d")
    render(root, "d", status="failed", error="CUDA out of memory")
    render(root, "d", status="failed", error="CUDA out of memory")
    state = {}
    cf.queue_redo(root, state)
    assert state["reasons"]["d"].startswith("render failed: CUDA out of memory")
    render(root, "d@r1", status="failed", error="CUDA out of memory")
    cf.queue_redo(root, state)
    assert any(json.loads(x)["guid"] == "d@r2" for x in (root / "data/render/cast_jobs/redo-02.jsonl").read_text().splitlines())


def test_out_of_attempts_accepts_the_best_flagged_take_and_lists_the_unrenderable(tmp_path):
    root = repo(tmp_path, "s", "u")
    for g, w in (("s", 0.9), ("s@r1", 0.4), ("s@r2", 0.7)):
        render(root, g, wer=w, flags=["asr_truncated"])
    for g in ("u", "u@r1", "u@r2"):
        render(root, g, status="failed", error="boom")
    assert cf.classify(root)["exhausted"] == ["s", "u"]
    out = cf.settle(root)
    assert list(out["accepted"]) == ["s@r1"] and out["accepted"]["s@r1"]["wer"] == 0.4
    assert [u["piece"] for u in out["unrenderable"]] == ["u"]
    assert cf.classify(root)["usable"] == ["s"]                       # the accepted take now passes the stitcher's check
    assert json.loads((root / "data/render/cast_accept.json").read_text()).keys() == {"s@r1"}
