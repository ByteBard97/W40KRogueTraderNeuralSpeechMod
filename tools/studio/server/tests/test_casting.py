import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from conftest import put, write_wav  # noqa: E402
from studio_server import casting  # noqa: E402
from studio_server.config import Config  # noqa: E402
from studio_server.errors import ApiError  # noqa: E402


def bg3(slug, name, lines, gender="male", hint=False, refs=True):
    return {"slug": slug, "name": name, "lines": lines, "seconds": lines * 4.0, "gender": gender, "median_f0_hz": 120.0, "non_human_hint": hint,
            "refs": [{"wav": f"data/bg3_voices/{slug}/ref_1.wav", "text": "A reference line.", "seconds": 10.0}] if refs else []}


@pytest.fixture
def cfg(tmp_path):
    d = tmp_path / "data"
    put(d / "npc_profile/describe/casting_needs.json", [
        {"speaker": "Vladaym Tocara the Liege", "lines": 194, "chars": 9000, "approx_minutes": 43, "status": "designed", "gender": "male", "species": "human"},
        {"speaker": "Seberian", "lines": 120, "chars": 5000, "approx_minutes": 20, "status": "voiceless", "gender": "male", "species": "human"},
        {"speaker": "Zacchary Weisz", "lines": 30, "chars": 1000, "approx_minutes": 5, "status": "voiceless", "gender": "male", "species": "human"},
        {"speaker": "Octaviana", "lines": 10, "chars": 400, "approx_minutes": 2, "status": "voiceless", "gender": "female", "species": "human"}])
    put(d / "npc_profile/describe/in/batch_0.json", [{"speaker": "Vladaym Tocara the Liege", "sample_lines": [{"conv": "c", "text": "I am impressed by your prudence. Your decision to arrive on Footfall incognito was quite wise."}]}])
    put(d / "bg3_voices/catalog.json", [bg3("gortash", "Gortash", 616), bg3("astarion", "Astarion", 10000), bg3("rat", "Rat", 40, hint=True),
                                         bg3("shadowheart", "Shadowheart", 9000, "female"), bg3("noclip", "Silent", 500, refs=False), bg3("zevlor", "Zevlor", 615)])
    for n in ("Vladaim", "Seberian"):
        (d / "portraits/half").mkdir(parents=True, exist_ok=True)
        (d / f"portraits/half/{n}.png").write_bytes(b"png")
    for slug in ("gortash", "astarion", "zevlor"):
        write_wav(d / f"bg3_voices/{slug}/ref_1.wav")
    put(d / "voices/prompts/prompts.json", {"Seberian": [{"rank": 1, "event": "old", "wav": "prompts/designed/seberian.wav", "text": "x", "duration": 1, "source": "old"}]})
    return Config(root=tmp_path)


def test_portrait_guess_handles_spelling_and_tokens():
    names = ["Vladaim", "Seberian", "ZaccharyWeisz", "VistencaVjatt"]
    assert casting.guess_portrait("Vladaym Tocara the Liege", names) == "Vladaim"
    assert casting.guess_portrait("Seberian", names) == "Seberian"
    assert casting.guess_portrait("Zacchary Weisz", names) == "ZaccharyWeisz"
    assert casting.guess_portrait("Nobody Special", names) is None


def test_eligible_filters_gender_creatures_and_missing_clips(cfg):
    cat = json.loads((cfg.data / "bg3_voices/catalog.json").read_text())
    male = [v["slug"] for v in casting.eligible(cat, "human", "male")]
    assert male == ["astarion", "gortash", "zevlor"]               # no rat (creature), no shadowheart (female), no voice without a clip; biggest first
    assert "shadowheart" in [v["slug"] for v in casting.eligible(cat, "human", "female")]
    assert "rat" in [v["slug"] for v in casting.eligible(cat, "machine", None)]               # a creature voice is allowed for a non-human character


def test_suggest_pairs_big_with_big_and_prefers_unused():
    pool = [{"slug": f"v{i}", "name": f"v{i}", "lines": 1000 - i, "gender": "male"} for i in range(20)]
    assert casting.suggest(0.0, pool, {})[0]["slug"] == "v0"
    assert casting.suggest(1.0, pool, {})[0]["slug"] == "v19"
    assert casting.suggest(0.0, pool, {"v0": ["someone"]})[0]["slug"] == "v1"        # v0 is taken, the next biggest wins


def test_page_is_sorted_by_screen_time_with_portraits_and_suggestions(cfg):
    pg = casting.page(cfg)
    assert [c["speaker"] for c in pg["characters"]][0] == "Vladaym Tocara the Liege"
    first = pg["characters"][0]
    assert first["portrait"] == "data/portraits/half/Vladaim.png" and first["suggestions"] and first["samples"]
    assert pg["total"] == 4 and pg["assigned"] == 0


def test_assign_persists_and_marks_the_voice_used(cfg):
    casting.assign(cfg, "Vladaym Tocara the Liege", "gortash")
    assert casting.page(cfg)["characters"][0]["assignment"]["name"] == "Gortash"
    assert next(v for v in casting.bg3_voices(cfg) if v["slug"] == "gortash")["used_by"] == ["Vladaym Tocara the Liege"]
    casting.assign(cfg, "Vladaym Tocara the Liege", None)
    assert casting.page(cfg)["assigned"] == 0
    with pytest.raises(ApiError):
        casting.assign(cfg, "Nobody", "gortash")
    with pytest.raises(ApiError):
        casting.assign(cfg, "Seberian", "no_such_voice")


def test_register_copies_the_clip_backs_up_prompts_and_replaces_the_entry(cfg):
    casting.assign(cfg, "Seberian", "zevlor")
    out = casting.register(cfg)
    assert out["registered"] == ["Seberian"]
    prompts = json.loads((cfg.voices / "prompts/prompts.json").read_text())
    assert prompts["Seberian"][0]["wav"] == "prompts/cast/seberian.wav" and prompts["Seberian"][0]["source"] == "BG3 voice: Zevlor"
    assert (cfg.voices / "prompts/cast/seberian.wav").is_file()
    assert list(cfg.voices.glob("prompts/prompts.json.pre-casting-*"))        # the old bank is kept


def test_audition_clones_the_reference_onto_a_real_line(cfg):
    class FakeModel:
        def call(self, path, body):
            assert path == "/generate" and body["reference_wav"] == "data/bg3_voices/gortash/ref_1.wav" and "prudence" in body["text"]
            write_wav(cfg.voice_design / "live_tmp/x.wav")
            return {"file": "live_tmp/x.wav", "seconds": 0.1}

    out = casting.audition(cfg, FakeModel(), "Vladaym Tocara the Liege", "gortash")
    assert out["file"].startswith("data/studio/casting/auditions/") and (cfg.root / out["file"]).is_file()


def test_designed_voices_get_their_details_and_sample_lines_from_the_manifest_and_job_list(cfg):
    put(cfg.voice_design / "design_manifest.json", {"Seberian": {"gender": "Male", "role": "dynasty patriarch", "description": "A man in his seventies."}})
    long = "He spoke slowly, and every word of it was meant to be heard by the whole room."
    jobs = [{"guid": "g1", "speaker": "Seberian", "speaker_kind": "unit", "text": long}, {"guid": "g2", "speaker": "Seberian", "speaker_kind": "unit", "text": "Short."}]
    (cfg.render).mkdir(parents=True, exist_ok=True)
    (cfg.render / "jobs.jsonl").write_text("".join(json.dumps(j) + "\n" for j in jobs), encoding="utf-8")
    sev = next(c for c in casting.page(cfg)["characters"] if c["speaker"] == "Seberian")
    assert sev["role"] == "dynasty patriarch" and sev["voice_description"] == "A man in his seventies." and sev["samples"] == [long]


def test_an_unnamed_catalog_voice_is_shown_by_its_technical_name(cfg):
    cat = json.loads((cfg.data / "bg3_voices/catalog.json").read_text())
    cat.append({**bg3("mystery", None, 100), "tech_name": "S_Mystery"})
    put(cfg.data / "bg3_voices/catalog.json", cat)
    assert next(v for v in casting.bg3_voices(cfg) if v["slug"] == "mystery")["name"] == "S_Mystery"


def test_a_voice_known_by_another_name_lists_it(cfg):
    cat = json.loads((cfg.data / "bg3_voices/catalog.json").read_text())
    cat.append(bg3("nightsong", "Nightsong", 601, "female"))
    put(cfg.data / "bg3_voices/catalog.json", cat)
    assert "Dame Aylin" in next(v for v in casting.bg3_voices(cfg) if v["slug"] == "nightsong")["aliases"]


def test_a_voice_cast_as_several_characters_lists_all_of_them_biggest_first(cfg):
    casting.assign(cfg, "Zacchary Weisz", "gortash")
    casting.assign(cfg, "Vladaym Tocara the Liege", "gortash")
    casting.assign(cfg, "Seberian", "gortash")
    assert next(v for v in casting.bg3_voices(cfg) if v["slug"] == "gortash")["used_by"] == ["Vladaym Tocara the Liege", "Seberian", "Zacchary Weisz"]
    page = casting.page(cfg)
    seb = next(c for c in page["characters"] if c["speaker"] == "Seberian")
    assert next(x for x in seb["suggestions"] if x["slug"] == "gortash")["used_by"] == ["Vladaym Tocara the Liege", "Seberian", "Zacchary Weisz"]


def test_the_name_in_a_technical_name_is_searchable(cfg):
    cat = json.loads((cfg.data / "bg3_voices/catalog.json").read_text())
    cat += [{**bg3("weary", "Weary Traveller", 232), "tech_name": "S_GLO_Elminster"},
            {**bg3("dv", "Dream Visitor", 1000), "tech_name": "S_GLO_DreamVisitor_Female"},
            {**bg3("gale", "Gale", 9000), "tech_name": "S_Player_Gale"}]
    put(cfg.data / "bg3_voices/catalog.json", cat)
    got = {v["slug"]: v["aliases"] for v in casting.bg3_voices(cfg)}
    assert got["weary"] == ["Elminster"]
    assert got["gale"] == [] and "Female" not in got["dv"]               # the shown name already says it; a gender word is not a name


def test_voices_whose_best_reference_is_poor_are_not_suggested_but_are_still_listed(cfg):
    cat = json.loads((cfg.data / "bg3_voices/catalog.json").read_text())
    cat.append({**bg3("thin", "Thin Ref", 5000), "refs_quality": "poor"})
    put(cfg.data / "bg3_voices/catalog.json", cat)
    assert "thin" not in [v["slug"] for v in casting.eligible(cat, "human", "male")]
    listed = next(v for v in casting.bg3_voices(cfg) if v["slug"] == "thin")
    assert listed["quality"] == "poor"
