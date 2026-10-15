import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import plan_auto_cast as P  # noqa: E402
import queue_server  # noqa: E402


def put(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj) if not isinstance(obj, str) else obj, encoding="utf-8")


def job(guid, speaker, text, kind="unit"):
    return {"guid": guid, "speaker": speaker, "speaker_kind": kind, "text": text, "src_text": text, "annotation": {"emotion": "neutral"},
            "engine": "qwen3_tts", "bucket": 1, "priority": 3, "voice_source": "fallback", "ref": {"wav": "data/narrator.wav", "text": "n"}}


def entry(name, **extra):
    return [{"rank": 1, "event": "e", "wav": f"prompts/cast/{name}.wav", "text": f"ref {name}", "duration": 1, "source": "BG3", "bg3": "x", "auto_cast": True, **extra}]


@pytest.fixture
def root(tmp_path):
    d = tmp_path / "data"
    put(d / "studio/auto_cast.json", {"items": {
        "Guard Hobb": {"status": "assigned", "bg3": "bruno", "processed": False, "steps": 15},
        "group:Scene_A|sailor": {"status": "assigned", "bg3": "carl", "processed": True, "steps": 20},
        "Unregistered": {"status": "assigned", "bg3": "bruno"},
        "Ghost": {"status": "needs_info"}}})
    put(d / "voices/prompts/prompts.json", {"Guard Hobb": entry("guard_hobb"), "group:Scene_A|sailor": entry("group_scene_a_sailor"),
                                            "Ghost": entry("ghost"), "Abelard": [{"wav": "prompts/Abelard/01.wav", "text": "y"}]})
    for n in ("guard_hobb", "group_scene_a_sailor", "ghost"):
        (d / f"voices/prompts/cast").mkdir(parents=True, exist_ok=True)
        (d / f"voices/prompts/cast/{n}.wav").write_bytes(b"RIFF")
    put(d / "studio/pools.json", {"routes": {"g1": {"to": "slot", "entry": "Scene_A|sailor", "slot": "male_human"},
                                             "g2": {"to": "slot", "entry": " Scene_A|sailor", "slot": "male_human"},
                                             "g3": {"to": "speaker", "speaker": "Guard Hobb"}, "g9": {"to": "slot", "entry": "Other|x", "slot": "s"}}})
    put(d / "studio/lab/recipes.json", [{"name": "resat-r2", "cfg": 3.0, "timesteps": 15}])
    lines = [job("a1", "Guard Hobb", "Halt."), job("g1", "default_speaker", "Aye aye.", "default_speaker"), job("g2", "default_speaker", "Yes.", "default_speaker"),
             job("g3", "default_speaker", "Move along.", "default_speaker"), job("g9", "default_speaker", "No.", "default_speaker"),
             job("u1", "Unregistered", "Hm."), job("a1", "Guard Hobb", "dup")]
    put(d / "render/jobs.jsonl", "".join(json.dumps(j) + "\n" for j in lines))
    return tmp_path


def run(root, *args):
    out = root / "data/render/jobs_auto_cast.jsonl"
    P.main(["--out", str(out), *args], root=root)
    return [json.loads(x) for x in out.read_text().splitlines()]


def test_plans_character_group_and_routed_lines(root, capsys):
    rows = run(root)
    by = {r["guid"]: r for r in rows}
    assert sorted(by) == ["a1", "g1", "g2", "g3"]                               # not g9 (another group), not the unregistered one; a1 once
    assert by["a1"]["speaker"] == "Guard Hobb" and by["g1"]["speaker"] == "group:Scene_A|sailor" and by["g3"]["speaker"] == "Guard Hobb"
    r = by["g1"]
    assert r["ref"] == {"wav": "data/voices/prompts/cast/group_scene_a_sailor.wav", "text": "ref group_scene_a_sailor", "emotion": None}
    assert r["voice_source"] == "auto_cast_bg3" and r["recipe"]["name"] == "resat-r2" and r["recipe"]["timesteps"] == 15
    assert r["engine"] == "voxcpm2" and r["annotation"] == {"emotion": "neutral"} and r["text"] == "Aye aye."
    assert "4 lines" in capsys.readouterr().out


def test_queue_raises_processed_to_twenty_and_leaves_natural_at_fifteen(root):
    run(root)
    jobs = {j["guid"]: j for j in queue_server.load_jobs(root / "data/render/jobs_auto_cast.jsonl", root)}
    assert jobs["g1"]["recipe"]["timesteps"] == 20 and jobs["g1"]["recipe"]["name"] == "resat-r2+p20" and jobs["g1"]["processed"] is True
    assert jobs["a1"]["recipe"]["timesteps"] == 15 and jobs["a1"]["recipe"]["name"] == "resat-r2"


def test_only_and_skip_done(root, capsys):
    assert {r["guid"] for r in run(root, "--only", "Guard Hobb")} == {"a1", "g3"}
    manifest = root / "m.jsonl"
    manifest.write_text(json.dumps({"guid": "a1", "status": "ok"}) + "\n" + json.dumps({"guid": "g3", "status": "failed"}) + "\n")
    capsys.readouterr()
    rows = run(root, "--only", "Guard Hobb", "--skip-done", str(manifest), "--force")
    assert [r["guid"] for r in rows] == ["g3"]                                  # a failed one is retried
    assert "skipped as already rendered: 1" in capsys.readouterr().out


def test_refuses_to_overwrite_without_force(root):
    run(root)
    with pytest.raises(SystemExit):
        run(root)
    assert run(root, "--force")


def test_unknown_recipe_and_nothing_to_plan_stop(root):
    with pytest.raises(SystemExit):
        run(root, "--recipe", "nope")
    with pytest.raises(SystemExit):
        run(root, "--only", "Nobody")


def test_a_registered_item_with_a_missing_clip_is_not_planned(root):
    (root / "data/voices/prompts/cast/guard_hobb.wav").rename(root / "gone.wav")      # the clip goes missing
    assert {r["speaker"] for r in run(root)} == {"group:Scene_A|sailor"}
