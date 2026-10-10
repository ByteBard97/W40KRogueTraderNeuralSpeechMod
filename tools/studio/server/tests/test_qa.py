import json
import os

import pytest

from conftest import make_repo, put, write_wav
from studio_server import qa
from studio_server.errors import ApiError
from studio_server.jsonio import read_json

SR = 1000     # tiny sample rate: long durations without big files


def clip(cfg, guid, seconds, text, speaker="Pasqal", engine="voxcpm2"):
    write_wav(cfg.render / f"export/wav/{guid}.wav", seconds, SR)
    return {"wav": f"wav/{guid}.wav", "text": text, "speaker": speaker, "engine": engine, "voice_source": "prompt_bank", "flags": []}


@pytest.fixture
def qcfg(tmp_path):
    cfg = make_repo(tmp_path)
    index = {
        "q1": clip(cfg, "q1", 2.0, "A perfectly ordinary line of text."),        # 34 chars / 2 s = 17 ch/s
        "q2": clip(cfg, "q2", 28.0, "Runaway generation at the cap length x"),    # cap_hit
        "q3": clip(cfg, "q3", 0.5, "Hi"),                                          # short; too few chars to rate speed
        "q4": clip(cfg, "q4", 5.0, "twenty chars of text", speaker="Ravor"),       # 4 ch/s: slow
        "q5": clip(cfg, "q5", 1.0, "thirty characters of speech ok", engine="qwen3_tts"),   # 30 ch/s: fast
        "q6": clip(cfg, "q6", 41.0, "A very long clip indeed with some words."),  # very_long (and slow)
    }
    index["q1"]["flags"] = ["render_flag"]
    put(cfg.render / "export/index.json", index)
    with open(cfg.render / "jobs.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps({"guid": "q1", "speaker": "Pasqal", "text": "A perfectly ordinary line of text.", "annotation": {"emotion": "calm", "instruct": "formal"},
                            "ref": {"wav": "data/voices/wav/Pasqal/E1.wav", "text": "Hello."}}) + "\n")
    # one render run
    run = cfg.render / "runA"
    write_wav(run / "wav/r1.wav", 2.0, SR)
    write_wav(run / "wav/r2.wav", 3.0, SR)
    (run / "manifest.jsonl").write_text("\n".join(json.dumps(r) for r in [
        {"guid": "r1", "status": "ok", "speaker": "Pasqal", "engine": "voxcpm2", "text": "Run line one is okay.", "voice_source": "prompt_bank", "flags": []},
        {"guid": "r2", "status": "ok", "speaker": "Pasqal", "engine": "voxcpm2", "text": "Run line two {n}here{/n}.", "voice_source": "prompt_bank", "flags": []},
        {"guid": "r3", "status": "error", "speaker": "Pasqal", "engine": "voxcpm2", "text": "failed", "flags": []},
    ]) + "\n", encoding="utf-8")
    (run / "asr.jsonl").write_text(json.dumps({"guid": "r2", "flags": ["asr_dropped"], "heard": "Run line", "wer": 0.4}) + "\n", encoding="utf-8")
    put(run / "real.json", {"r2": [{"wav": "real/r2_1.wav", "speaker": "Pasqal", "event": "Ev_1", "text": "Said by Pasqal.", "located": True},
                                   {"wav": "real/r2_2.wav", "speaker": "_unattributed", "event": "Ev_2", "text": "Narrated.", "located": False}]})
    write_wav(run / "real/r2_1.wav", 1.0, SR)
    write_wav(cfg.render / "export/wav/r1.wav", 2.0, SR)       # an earlier render of r1
    return cfg


@pytest.mark.parametrize("dur,chars,flags", [
    (2.0, 30, []), (27.0, 400, ["cap_hit"]), (30.2, 450, ["cap_hit"]), (26.9, 400, []), (30.3, 450, []),
    (4.0, 20, ["slow"]), (2.0, 14, []), (2.0, 13, ["slow"]), (1.0, 27, ["fast"]), (1.0, 26, []), (0.5, 2, ["short"]),
    (0.7, 20, ["fast"]), (41.0, 600, ["very_long"]), (41.0, 40, ["slow", "very_long"]), (28.0, 30, ["cap_hit", "slow"]),
])
def test_auto_flags_thresholds(dur, chars, flags):
    assert sorted(qa.auto_flags(dur, chars, [])) == sorted(flags)


def test_auto_flags_keeps_the_renders_own_flags_first():
    assert qa.auto_flags(2.0, 30, ["render_flag"]) == ["render_flag"]
    assert qa.auto_flags(28.0, 420, ["x"]) == ["x", "cap_hit"]


def test_spoken_text_strips_braced_markup():
    assert qa.spoken_text("{n}Hello{/n} there {mf|a|b}") == "Hello there"


def test_runs_lists_the_export_and_each_run_with_a_manifest(qcfg):
    runs = {r["id"]: r for r in qa.runs(qcfg)}
    assert runs["export"]["clips"] == 6 and runs["runA"]["clips"] == 3 and runs["export"]["label"]


def test_export_clips_have_paths_flags_and_the_clone_reference(qcfg):
    by = {c["guid"]: c for c in qa.clips(qcfg, "export")}
    assert len(by) == 6
    assert by["q1"]["wav"] == "data/render/export/wav/q1.wav" and by["q1"]["ref_path"] == "data/voices/wav/Pasqal/E1.wav" and by["q1"]["ref"] == "E1"
    assert by["q1"]["emotion"] == "calm" and by["q1"]["instruct"] == "formal"
    assert by["q2"]["flags"] == ["cap_hit", "slow"] and by["q4"]["flags"] == ["slow"] and by["q5"]["flags"] == ["fast"] and by["q3"]["flags"] == ["short"]
    assert "very_long" in by["q6"]["flags"] and by["q1"]["flags"] == ["render_flag"] and by["q1"]["dur"] == 2.0


def test_run_clips_skip_failures_and_carry_asr_real_and_the_old_render(qcfg):
    by = {c["guid"]: c for c in qa.clips(qcfg, "runA")}
    assert set(by) == {"r1", "r2"}
    assert by["r1"]["wav"] == "data/render/runA/wav/r1.wav" and by["r1"]["old"] == "data/render/export/wav/r1.wav" and by["r2"]["old"] is None
    assert "asr_dropped" in by["r2"]["flags"] and by["r2"]["heard"] == "Run line" and by["r2"]["wer"] == 0.4
    assert by["r2"]["real"] == [
        {"label": "Real: Pasqal", "path": "data/render/runA/real/r2_1.wav", "text": "Said by Pasqal.", "full_line": False},
        {"label": "Real: _unattributed", "path": "data/render/runA/real/r2_2.wav", "text": "Narrated.", "full_line": True}]
    assert qcfg.resolve_file(by["r2"]["real"][0]["path"]) is not None and by["r1"]["real"] == []
    assert by["r2"]["text"] == "Run line two {n}here{/n}."


@pytest.mark.parametrize("run", ["nope", "../etc", "runA/../x", ""])
def test_unknown_or_unsafe_run_is_a_404(qcfg, run):
    with pytest.raises(ApiError) as e:
        qa.clips(qcfg, run or "no-such-run")
    assert e.value.status == 404


def test_unreadable_wavs_are_skipped(qcfg):
    (qcfg.render / "export/wav/q3.wav").write_bytes(b"not a wav")
    assert "q3" not in {c["guid"] for c in qa.clips(qcfg, "export")}


def test_facets(qcfg):
    f = qa.facets(qcfg, "export")
    assert f["speakers"] == ["Pasqal", "Ravor"] and f["engines"] == ["qwen3_tts", "voxcpm2"] and f["refs"] == ["E1"]
    assert {"cap_hit", "slow", "fast", "short", "very_long", "render_flag"} <= set(f["flags"])


def test_page_filters(qcfg):
    ids = lambda **kw: [i["guid"] for i in qa.page(qcfg, "export", sort="longest", **kw)["items"]]
    assert ids(speaker="Ravor") == ["q4"] and ids(engine="qwen3_tts") == ["q5"] and ids(ref="E1") == ["q1"]
    assert ids(flag="cap_hit") == ["q2"] and ids(flag="no flag") == []
    assert set(ids(flag="any flag")) == {"q1", "q2", "q3", "q4", "q5", "q6"}
    assert ids(q="runaway") == ["q2"] and ids(q="RUNAWAY") == ["q2"]


def test_page_sorts(qcfg):
    first = lambda sort: [i["guid"] for i in qa.page(qcfg, "export", sort=sort)["items"]]
    assert first("longest") == ["q6", "q2", "q4", "q1", "q5", "q3"]
    assert first("shortest") == ["q3", "q5", "q1", "q4", "q2", "q6"]
    assert first("slowest")[:2] == ["q6", "q2"] and first("fastest")[:2] == ["q5", "q1"]
    # most flags first, then furthest from the typical 15 chars/s, then by guid
    assert first("suspicious") == ["q6", "q2", "q5", "q3", "q4", "q1"]


def test_random_sort_is_stable_for_a_seed_and_differs_between_seeds(qcfg):
    a = [i["guid"] for i in qa.page(qcfg, "export", sort="random", seed=1)["items"]]
    assert a == [i["guid"] for i in qa.page(qcfg, "export", sort="random", seed=1)["items"]]
    assert set(a) == {"q1", "q2", "q3", "q4", "q5", "q6"}
    assert any(a != [i["guid"] for i in qa.page(qcfg, "export", sort="random", seed=s)["items"]] for s in range(2, 8))


def test_paging_and_the_limit_cap(qcfg):
    p = qa.page(qcfg, "export", sort="longest", offset=2, limit=2)
    assert p["total"] == 6 and [i["guid"] for i in p["items"]] == ["q4", "q1"]
    assert qa.page(qcfg, "export", limit=10_000)["limit"] == qa.MAX_PAGE
    assert qa.page(qcfg, "export", offset=99)["items"] == []


def test_verdicts_set_clear_and_per_run_files(qcfg):
    qa.set_verdict(qcfg, "export", {"guid": "q1", "verdict": "good", "tags": [], "note": "nice"})
    qa.set_verdict(qcfg, "runA", {"guid": "r1", "verdict": "bad", "tags": ["garbled"], "note": ""})
    assert read_json(qcfg.render / "audit/verdicts.json", {}) == {"q1": {"verdict": "good", "tags": [], "note": "nice"}}
    assert read_json(qcfg.render / "audit/verdicts_runA.json", {})["r1"]["tags"] == ["garbled"]
    p = qa.page(qcfg, "export", verdict="good")
    assert [i["guid"] for i in p["items"]] == ["q1"] and p["items"][0]["verdict"]["note"] == "nice"
    assert qa.page(qcfg, "export", verdict="unjudged")["total"] == 5
    assert {k: p["stats"][k] for k in ("good", "bad", "unjudged")} == {"good": 1, "bad": 0, "unjudged": 5}
    qa.set_verdict(qcfg, "export", {"guid": "q1", "verdict": None})
    assert read_json(qcfg.render / "audit/verdicts.json", {}) == {} and qa.page(qcfg, "export")["stats"]["good"] == 0


@pytest.mark.parametrize("body,status", [
    ({"guid": "q1", "verdict": "maybe"}, 400), ({"verdict": "good"}, 400), ({"guid": "q1", "verdict": "good", "tags": "x"}, 400),
    ({"guid": "nope", "verdict": "good"}, 404),
])
def test_bad_verdicts_are_rejected_and_write_nothing(qcfg, body, status):
    with pytest.raises(ApiError) as e:
        qa.set_verdict(qcfg, "export", body)
    assert e.value.status == status and not (qcfg.render / "audit/verdicts.json").exists()


def test_the_clip_cache_follows_the_index(qcfg):
    assert len(qa.clips(qcfg, "export")) == 6
    index = read_json(qcfg.render / "export/index.json", {})
    del index["q6"]
    put(qcfg.render / "export/index.json", index)
    os.utime(qcfg.render / "export/index.json", (1, 1_900_000_000))
    assert len(qa.clips(qcfg, "export")) == 5


def test_compressed_audio_is_cached_and_validates_the_preset(qcfg):
    pytest.importorskip("scipy")
    write_wav(qcfg.render / "export/wav/fx.wav", 0.3)               # the compressor's filters need a real sample rate
    p = qcfg.render / "export/wav/fx.wav"
    a = qa.compressed(p, "mild")
    assert a[:4] == b"RIFF" and qa.compressed(p, "mild") is a
    with pytest.raises(ApiError) as e:
        qa.compressed(p, "nuclear")
    assert e.value.status == 400


def test_the_export_cache_follows_the_jobs_files(qcfg):
    assert qa.clips(qcfg, "export")[0]["text"] == "A perfectly ordinary line of text."
    jobs = qcfg.render / "jobs.jsonl"
    jobs.write_text(jobs.read_text(encoding="utf-8").replace("ordinary", "changed"), encoding="utf-8")
    os.utime(jobs, (1, 1_900_000_000))
    assert "changed" in next(c for c in qa.clips(qcfg, "export") if c["guid"] == "q1")["text"]


def test_stats_tally_verdicts_per_reference(qcfg):
    qa.set_verdict(qcfg, "export", {"guid": "q1", "verdict": "bad", "tags": [], "note": ""})
    by_ref = qa.page(qcfg, "export")["stats"]["by_ref"]
    assert by_ref["E1"] == {"good": 0, "bad": 1, "total": sum(1 for c in qa.clips(qcfg, "export") if c["ref"] == "E1")}
    assert all(set(v) == {"good", "bad", "total"} for v in by_ref.values()) and "" not in by_ref


def test_exclude_is_applied_before_slicing_and_random_order_survives_judging(qcfg):
    every = [c["guid"] for c in qa.page(qcfg, "export", sort="random", seed=3, limit=200)["items"]]
    rest = qa.page(qcfg, "export", sort="random", seed=3, exclude=",".join(every[:2]), limit=2)
    assert [i["guid"] for i in rest["items"]] == every[2:4] and rest["total"] == len(every) - 2
    qa.set_verdict(qcfg, "export", {"guid": every[2], "verdict": "bad", "tags": [], "note": ""})
    unjudged = [i["guid"] for i in qa.page(qcfg, "export", sort="random", seed=3, verdict="unjudged", limit=200)["items"]]
    assert unjudged == [g for g in every if g != every[2]]
    assert qa.page(qcfg, "export", exclude=",".join(every))["items"] == []


def test_view_stats_follow_the_filters_but_not_exclude_or_paging(qcfg):
    qa.set_verdict(qcfg, "export", {"guid": "q1", "verdict": "good", "tags": [], "note": ""})
    qa.set_verdict(qcfg, "export", {"guid": "q4", "verdict": "bad", "tags": [], "note": ""})
    p = qa.page(qcfg, "export")
    assert p["view"] == {"good": 1, "bad": 1, "unjudged": 4, "total": 6} and p["stats"]["total"] == 6 and p["stats"]["judged"] == 2
    v = qa.page(qcfg, "export", speaker="Pasqal")["view"]
    assert v == {"good": 1, "bad": 0, "unjudged": 4, "total": 5}
    assert qa.page(qcfg, "export", speaker="Pasqal")["stats"]["bad"] == 1       # run-wide stats ignore the filter
    assert qa.page(qcfg, "export", verdict="unjudged")["view"] == {"good": 0, "bad": 0, "unjudged": 4, "total": 4}
    paged = qa.page(qcfg, "export", speaker="Pasqal", limit=1, exclude="q1,q2")
    assert paged["view"] == v and paged["total"] == 3
    assert qa.page(qcfg, "export", q="nothing matches this")["view"] == {"good": 0, "bad": 0, "unjudged": 0, "total": 0}


def test_flag_info_explains_every_automatic_flag(qcfg):
    info = qa.facets(qcfg, "export")["flag_info"]
    assert set(info) >= {"cap_hit", "slow", "fast", "short", "very_long"} and "5" not in info["slow"] and "7" in info["slow"]
    assert set(qa.facets(qcfg, "export")["flags"]) - {"render_flag"} <= set(info)


def test_export_picks_up_an_asr_file_when_one_is_merged_in(qcfg):
    c = next(c for c in qa.clips(qcfg, "export") if c["guid"] == "q1")
    assert c["heard"] == "" and c["wer"] is None
    (qcfg.render / "export/asr.jsonl").write_text(json.dumps({"guid": "q1", "heard": "ordinary line", "wer": 0.3, "flags": ["asr_warn"]}) + "\n", encoding="utf-8")
    os.utime(qcfg.render / "export/asr.jsonl", (1, 1_900_000_001))
    c = next(c for c in qa.clips(qcfg, "export") if c["guid"] == "q1")
    assert c["heard"] == "ordinary line" and c["wer"] == 0.3 and "asr_warn" in c["flags"]
