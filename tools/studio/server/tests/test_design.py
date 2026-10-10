import pytest

from studio_server import design
from studio_server.errors import ApiError
from studio_server.jsonio import read_json
from conftest import write_wav


def test_verdict_pick_and_toggle(cfg):
    design.post_verdict(cfg, "muaran", {"cand": "c0.wav", "accent": "british", "fit": 4})
    design.post_verdict(cfg, "muaran", {"cand": "c0.wav", "pick": True})
    a = read_json(cfg.voice_design / "audit.json", {})["Muaran"]
    assert a["cands"]["c0.wav"] == {"accent": "british", "fit": 4} and a["pick"] == "c0.wav"
    design.post_verdict(cfg, "muaran", {"cand": "c0.wav", "pick": False})
    assert read_json(cfg.voice_design / "audit.json", {})["Muaran"]["pick"] is None


def test_order_with_follow_rank_sets_rank_one_as_pick(cfg):
    design.post_order(cfg, "muaran", ["c1.wav", "c0.wav"], follow_rank=True)
    a = read_json(cfg.voice_design / "audit.json", {})["Muaran"]
    assert a["order"] == ["c1.wav", "c0.wav"] and a["pick"] == "c1.wav"


def test_order_rejects_unknown_candidate(cfg):
    with pytest.raises(ApiError) as e:
        design.post_order(cfg, "muaran", ["c9.wav"])
    assert e.value.status == 400


def test_description_saved_as_override(cfg):
    design.post_description(cfg, "muaran", "A stern woman.")
    assert read_json(cfg.voice_design / "overrides.json", {}) == {"Muaran": "A stern woman."}


def test_register_copies_the_pick_into_the_prompt_bank_and_leaves_others(cfg):
    design.post_verdict(cfg, "muaran", {"cand": "c0.wav", "pick": True})
    assert design.register_pick(cfg, "muaran") == {"registered": ["Muaran"]}
    assert (cfg.voices / "prompts/designed/muaran.wav").is_file()
    prompts = read_json(cfg.voices / "prompts/prompts.json", {})
    assert prompts["Muaran"][0]["event"] == "designed_muaran" and "Pasqal" in prompts


def test_register_without_a_pick_is_400_and_changes_nothing(cfg):
    before = (cfg.voices / "prompts/prompts.json").read_text(encoding="utf-8")
    with pytest.raises(ApiError) as e:
        design.register_pick(cfg, "muaran")
    assert e.value.status == 400
    assert (cfg.voices / "prompts/prompts.json").read_text(encoding="utf-8") == before


def test_keep_copies_take_to_next_candidate_and_records_gen(cfg):
    write_wav(cfg.voice_design / "live_tmp/t1.wav")
    r = design.keep(cfg, "muaran", {"file": "live_tmp/t1.wav", "seed": 7, "cfg": 2.0, "timesteps": 10,
                                    "description": "A calm woman.", "text": "The augurs…"})
    assert r == {"cand": "c2.wav"}
    assert (cfg.voice_design / "clips/muaran/c2.wav").is_file()
    m = read_json(cfg.voice_design / "design_manifest.json", {})["Muaran"]
    assert m["candidates"][-1] == "c2.wav" and m["gen"]["candidates"]["c2.wav"]["seed"] == 7


def test_keep_backfills_description_and_text_so_every_kept_candidate_is_regenerable(cfg):
    write_wav(cfg.voice_design / "live_tmp/t2.wav")
    design.keep(cfg, "muaran", {"file": "live_tmp/t2.wav", "seed": 9, "cfg": 2.0, "timesteps": 10})
    rec = read_json(cfg.voice_design / "design_manifest.json", {})["Muaran"]["gen"]["candidates"]["c2.wav"]
    assert rec["description"] == "A calm woman." and rec["text"] == "The augurs report nothing unusual."


def test_keep_rejects_a_take_with_no_seed(cfg):
    write_wav(cfg.voice_design / "live_tmp/t3.wav")
    with pytest.raises(ApiError) as e:
        design.keep(cfg, "muaran", {"file": "live_tmp/t3.wav"})
    assert e.value.status == 400


@pytest.mark.parametrize("bad", ["live_tmp/missing.wav", "../audit.json", "clips/muaran/c0.wav", "/etc/passwd"])
def test_keep_rejects_files_outside_live_tmp_or_missing(cfg, bad):
    with pytest.raises(ApiError) as e:
        design.keep(cfg, "muaran", {"file": bad, "seed": 1, "cfg": 2.0, "timesteps": 10})
    assert e.value.status == 400


def test_real_speaker_has_no_design(cfg):
    with pytest.raises(ApiError) as e:
        design.post_verdict(cfg, "pasqal", {"cand": "c0.wav"})
    assert e.value.status == 404


@pytest.mark.parametrize("cand", ["../../../voices/catalog.json", "c9.wav", "", "/etc/passwd"])
def test_verdict_rejects_a_candidate_that_is_not_in_the_manifest(cfg, cand):
    with pytest.raises(ApiError) as e:
        design.post_verdict(cfg, "muaran", {"cand": cand, "pick": True})
    assert e.value.status == 400
    assert read_json(cfg.voice_design / "audit.json", {}) == {}


def test_register_refuses_a_stale_pick_and_a_missing_clip_and_never_overwrites(cfg):
    from conftest import put
    put(cfg.voice_design / "audit.json", {"Muaran": {"pick": "../../../voices/catalog.json", "cands": {}}})
    write_wav(cfg.voices / "prompts/designed/muaran.wav")
    before = (cfg.voices / "prompts/designed/muaran.wav").read_bytes()
    with pytest.raises(ApiError) as e:
        design.register_pick(cfg, "muaran")
    assert e.value.status == 400 and (cfg.voices / "prompts/designed/muaran.wav").read_bytes() == before
    put(cfg.voice_design / "audit.json", {"Muaran": {"pick": "c1.wav", "cands": {}}})
    (cfg.voice_design / "clips/muaran/c1.wav").rename(cfg.voice_design / "clips/muaran/gone.wav")
    with pytest.raises(ApiError) as e2:
        design.register_pick(cfg, "muaran")
    assert e2.value.status == 409


def test_empty_description_is_rejected_and_nothing_written(cfg):
    with pytest.raises(ApiError) as e:
        design.post_description(cfg, "muaran", "   ")
    assert e.value.status == 400 and not (cfg.voice_design / "overrides.json").exists()


def test_register_refuses_a_rejected_candidate(cfg):
    design.post_verdict(cfg, "muaran", {"cand": "c0.wav", "reject": True})
    design.post_verdict(cfg, "muaran", {"cand": "c0.wav", "pick": True})
    with pytest.raises(ApiError) as e:
        design.register_pick(cfg, "muaran")
    assert e.value.status == 409 and not (cfg.voices / "prompts/designed/muaran.wav").exists()


def test_keep_twice_with_the_same_take_does_not_make_a_duplicate(cfg):
    write_wav(cfg.voice_design / "live_tmp/t9.wav")
    body = {"file": "live_tmp/t9.wav", "seed": 5, "cfg": 2.0, "timesteps": 10}
    first = design.keep(cfg, "muaran", body)
    again = design.keep(cfg, "muaran", body)
    assert first == again
    assert read_json(cfg.voice_design / "design_manifest.json", {})["Muaran"]["candidates"].count(first["cand"]) == 1


def _clone_fixture(cfg):
    from conftest import put
    put(cfg.voice_design / "clone_manifest.json", {
        "muaran/c0_L0.wav": {"name": "Muaran", "candidate": "c0.wav", "text": "Real line one."},
        "muaran/c1_L0.wav": {"name": "Muaran", "candidate": "c1.wav", "text": "Real line two."},
        "other/c0_L0.wav": {"name": "Someone Else", "candidate": "c0.wav", "text": "Not ours."}})
    write_wav(cfg.voice_design / "clones/muaran/c0_L0.wav")
    put(cfg.voice_design / "scores.json", {"clones/muaran/c0_L0.wav": {"p_us": 0.8, "top": "england", "p_top": 0.5}})


def test_design_payload_lists_this_speakers_clone_tests_with_scores(cfg):
    from studio_server import speakers
    _clone_fixture(cfg)
    d = speakers.speaker_detail(cfg, "muaran")["design"]
    assert [c["candidate"] for c in d["clones"]] == ["c0.wav", "c1.wav"]
    first = d["clones"][0]
    assert first["file"] == "data/voice_design/clones/muaran/c0_L0.wav" and first["text"] == "Real line one."
    assert first["scores"]["p_us"] == 0.8 and d["clones"][1]["scores"] is None


def test_design_payload_has_empty_clones_without_a_manifest(cfg):
    from studio_server import speakers
    assert speakers.speaker_detail(cfg, "muaran")["design"]["clones"] == []


def test_list_flags_speakers_that_have_a_pick(cfg):
    from studio_server import speakers
    by = lambda: {s["name"]: s for s in speakers.list_speakers(cfg)}
    assert by()["Muaran"]["has_pick"] is False and by()["Pasqal"]["has_pick"] is False
    design.post_verdict(cfg, "muaran", {"cand": "c0.wav", "pick": True})
    assert by()["Muaran"]["has_pick"] is True


def test_register_all_registers_picks_and_reports_skips(cfg):
    from conftest import put
    design.post_verdict(cfg, "muaran", {"cand": "c0.wav", "pick": True})
    r = design.register_all(cfg)
    assert r["registered"] == [{"name": "Muaran", "cand": "c0.wav"}]
    assert r["skipped"] == [{"name": "Pasqal", "reason": "real", "detail": "real voice, nothing to register"}]
    assert (cfg.voices / "prompts/designed/muaran.wav").is_file()
    put(cfg.voice_design / "audit.json", {"Muaran": {"pick": "c0.wav", "cands": {"c0.wav": {"reject": True}}}})
    r2 = design.register_all(cfg)
    err = next(x for x in r2["skipped"] if x["name"] == "Muaran")
    assert r2["registered"] == [] and err["reason"] == "error" and "rejected" in err["detail"]


def test_register_all_with_no_picks_skips_everyone_by_category(cfg):
    r = design.register_all(cfg)
    assert r["registered"] == []
    assert {(x["name"], x["reason"]) for x in r["skipped"]} == {("Muaran", "no_pick"), ("Pasqal", "real")}
