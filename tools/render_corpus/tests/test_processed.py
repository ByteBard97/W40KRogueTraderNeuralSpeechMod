import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import processed as P  # noqa: E402
import queue_server  # noqa: E402


def put(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")


def repo(tmp_path: Path) -> Path:
    d = tmp_path / "data/studio"
    put(d / "bg3_labels.json", {"robot": {"processing": "processed"}, "plain": {"processing": "natural"}, "both": {"processing": ["natural", "processed"]}})
    put(d / "casting.json", {"assignments": {"Tech Adept": {"bg3": "robot"}, "Farmer": {"bg3": "plain"}, "Mixed": {"bg3": "both"}}, "portraits": {}})
    put(d / "auto_cast.json", {"items": {"Servitor": {"processed": True, "bg3": "robot"}, "Clerk": {"processed": False, "bg3": "plain"}}})
    put(d / "pools.json", {"slots": {"male_machine": {"speaker_key": "pool_male_machine", "species": "machine"}, "male_human": {"speaker_key": "pool_male_human", "species": "human"}}})
    return tmp_path


def test_processed_speakers_come_from_casting_auto_cast_and_machine_pools(tmp_path):
    got = P.load(repo(tmp_path))
    assert got == {"Tech Adept", "Servitor", "pool_male_machine", "Mixed"}                      # a voice labelled both natural and processed counts
    assert {"Farmer", "Clerk", "pool_male_human"}.isdisjoint(got)


def test_an_explicit_label_beats_the_derived_answer(tmp_path):
    root = repo(tmp_path)
    put(root / "data/studio/npc_processing.json", {"Pasqal": True, "Tech Adept": False})
    got = P.load(root)
    assert "Pasqal" in got and "Tech Adept" not in got


def test_apply_raises_steps_to_twenty_renames_the_recipe_and_leaves_others_alone():
    shared = {"name": "resat-r2", "cfg": 3.0, "timesteps": 15}
    jobs = [{"guid": "a", "speaker": "Pasqal", "recipe": shared}, {"guid": "b", "speaker": "Farmer", "recipe": shared},
            {"guid": "c", "speaker": "Pasqal"}, {"guid": "d", "speaker": "Pasqal", "recipe": {"name": "x", "timesteps": 25}}]
    out = P.apply(jobs, {"Pasqal"})
    assert out[0]["recipe"] == {"name": "resat-r2+p20", "cfg": 3.0, "timesteps": 20} and out[0]["processed"] is True
    assert out[1]["recipe"] is shared and shared["timesteps"] == 15 and "processed" not in out[1]       # the shared recipe is not changed
    assert "recipe" not in out[2] and out[2]["processed"] is True                                    # a legacy job is only marked
    assert out[3]["recipe"]["timesteps"] == 25 and out[3]["recipe"]["name"] == "x+p25"               # never lowered


def test_apply_is_safe_to_run_twice():
    once = P.apply([{"guid": "a", "speaker": "P", "recipe": {"name": "r", "timesteps": 15}}], {"P"})
    twice = P.apply(once, {"P"})
    assert twice[0]["recipe"] == {"name": "r+p20", "timesteps": 20}


def test_the_queue_loads_jobs_with_the_step_count_already_raised(tmp_path):
    root = repo(tmp_path)
    put(root / "data/studio/npc_processing.json", {"Pasqal": True})
    jobs = root / "jobs.jsonl"
    jobs.write_text("\n".join(json.dumps(j) for j in [{"guid": "a", "speaker": "Pasqal", "recipe": {"name": "r", "timesteps": 15}},
                                                     {"guid": "b", "speaker": "Farmer", "recipe": {"name": "r", "timesteps": 15}}]), encoding="utf-8")
    got = queue_server.load_jobs(jobs, root=root)
    assert [j["recipe"]["timesteps"] for j in got] == [20, 15]


def test_a_label_on_a_voiced_rt_speaker_counts_and_the_override_file_still_wins(tmp_path):
    root = repo(tmp_path)
    put(root / "data/studio/rt_labels.json", {"Pasqal": {"processing": "processed"}, "Tech Adept": {"processing": "natural"},
                                               "Abelard": {"processing": "natural"}, "Ulfar": {"gender": "male"}, "Manipulus": {"processing": ["natural", "processed"]}})
    got = P.load(root)
    assert "Pasqal" in got and "Manipulus" in got                      # processed, or both
    assert "Tech Adept" not in got                                      # the label says natural, over the derived answer
    assert {"Abelard", "Ulfar"}.isdisjoint(got)
    put(root / "data/studio/npc_processing.json", {"Pasqal": False, "Abelard": True})
    got = P.load(root)
    assert "Pasqal" not in got and "Abelard" in got
