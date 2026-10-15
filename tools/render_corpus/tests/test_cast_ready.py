import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))

import cast_ready  # noqa: E402


def put(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")


def repo(tmp_path, quality):
    put(tmp_path / "data/studio/casting.json", {"assignments": {"Seberian": {"bg3": "zevlor"}, "Octaviana": {"bg3": "mizora"}, "Nobody": {"bg3": "gone"}}})
    (tmp_path / "data/bg3_voices/zevlor").mkdir(parents=True)
    (tmp_path / "data/bg3_voices/zevlor/ref_v2_1.wav").write_bytes(b"w")
    put(tmp_path / "data/bg3_voices/catalog.json", [
        {"slug": "zevlor", "refs_quality": quality, "refs": [{"wav": "data/bg3_voices/zevlor/ref_v2_1.wav"}]},
        {"slug": "mizora", "refs_quality": "poor", "refs": [{"wav": "data/bg3_voices/mizora/ref_v2_1.wav"}]}])
    return tmp_path


def test_a_character_is_ready_only_when_its_voice_has_a_rebuilt_good_reference(tmp_path):
    ok, waiting = cast_ready.ready(repo(tmp_path, "good"))
    assert ok == [("Seberian", "zevlor")]
    assert "poor" in waiting["Octaviana"] and "catalog" in waiting["Nobody"]


def test_a_voice_with_an_unchecked_reference_waits(tmp_path):
    ok, waiting = cast_ready.ready(repo(tmp_path, None))
    assert ok == [] and "not checked" in waiting["Seberian"]


def test_a_missing_reference_file_waits(tmp_path):
    root = repo(tmp_path, "ok")
    (root / "data/bg3_voices/zevlor/ref_v2_1.wav").unlink()
    assert cast_ready.ready(root)[1]["Seberian"] == "reference file missing"


def test_the_free_gpu_check_runs_at_most_every_thirty_minutes(tmp_path):
    (tmp_path / "data/render").mkdir(parents=True)
    assert cast_ready.check_due(tmp_path, now=100000.0) is True            # first check is due at once
    assert cast_ready.check_due(tmp_path, now=100000.0 + 1799) is False
    assert cast_ready.check_due(tmp_path, now=100000.0 + 1800) is True


def test_the_5080_is_gated_by_the_pause_file_the_game_and_the_wait_for_free_file(tmp_path, monkeypatch):
    (tmp_path / "data/render").mkdir(parents=True)
    monkeypatch.setattr(cast_ready, "game_running", lambda: False)
    monkeypatch.setattr(cast_ready, "gpu_free", lambda: (True, "13000 MiB free"))
    assert cast_ready.local_gate(tmp_path) == (True, "")                      # nothing set: start
    (tmp_path / cast_ready.NO_LOCAL_FILE).write_text("")
    assert cast_ready.local_gate(tmp_path)[0] is False                        # paused
    (tmp_path / cast_ready.NO_LOCAL_FILE).unlink()
    monkeypatch.setattr(cast_ready, "game_running", lambda: True)
    assert cast_ready.local_gate(tmp_path) == (False, "the game is running")
    monkeypatch.setattr(cast_ready, "game_running", lambda: False)
    (tmp_path / cast_ready.WHEN_FREE_FILE).write_text("")
    assert cast_ready.local_gate(tmp_path)[0] is True                         # waiting for free, and it is free
    assert cast_ready.local_gate(tmp_path)[0] is False                        # the same half hour: not checked again
    monkeypatch.setattr(cast_ready, "check_due", lambda root: True)
    monkeypatch.setattr(cast_ready, "gpu_free", lambda: (False, "4000 MiB free of 16303, utilisation 90%"))
    go, note = cast_ready.local_gate(tmp_path)
    assert go is False and "still busy" in note


def test_the_marker_can_delay_the_first_check_and_set_a_shorter_interval(tmp_path):
    import time as _t
    (tmp_path / "data/render").mkdir(parents=True)
    start = _t.mktime(_t.strptime("2026-10-12T22:55:00", "%Y-%m-%dT%H:%M:%S"))
    (tmp_path / cast_ready.WHEN_FREE_FILE).write_text(json.dumps({"not_before": "2026-10-12T22:55:00", "every_s": 600}))
    assert cast_ready.check_due(tmp_path, now=start - 60) is False           # before the start time: never
    assert cast_ready.check_due(tmp_path, now=start) is True                 # then at once
    assert cast_ready.check_due(tmp_path, now=start + 599) is False
    assert cast_ready.check_due(tmp_path, now=start + 600) is True           # and every ten minutes
