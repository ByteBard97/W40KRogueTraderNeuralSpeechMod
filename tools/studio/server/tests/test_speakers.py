import pytest

from studio_server import speakers
from studio_server.errors import ApiError
from conftest import put, write_wav


def by_name(cfg):
    return {s["name"]: s for s in speakers.list_speakers(cfg)}


def test_list_marks_origin_counts_and_status(cfg):
    s = by_name(cfg)
    assert s["Pasqal"]["origin"] == "real" and s["Pasqal"]["line_count"] == 2 and s["Pasqal"]["status"] == "source"
    assert s["Muaran"]["origin"] == "designed" and s["Muaran"]["line_count"] == 1
    assert s["Muaran"]["status"] == "needs_voice"
    assert "narrator" not in s


def test_status_follows_pick_and_profile(cfg):
    put(cfg.voice_design / "audit.json", {"Muaran": {"cands": {}, "pick": "c1.wav", "order": ["c1.wav"]}})
    assert by_name(cfg)["Muaran"]["status"] == "source"
    put(cfg.studio / "muaran/profile.json", {"name": "Muaran"})
    assert by_name(cfg)["Muaran"]["status"] == "profile"


def test_slugs_are_unique_and_stable_when_names_collide(cfg):
    put(cfg.voices / "prompts/prompts.json", {"Ulfar": [], "ulfar!": []})
    slugs = [s["slug"] for s in speakers.list_speakers(cfg) if s["name"] in ("Ulfar", "ulfar!")]
    assert len(set(slugs)) == 2
    assert slugs == [s["slug"] for s in speakers.list_speakers(cfg) if s["name"] in ("Ulfar", "ulfar!")]


def test_detail_real_speaker_clips_sorted_curated_first(cfg):
    d = speakers.speaker_detail(cfg, "pasqal")
    assert d["design"] is None and d["profile"] is None
    assert [c["id"] for c in d["clips"]] == ["E1", "E2"]
    assert d["clips"][0]["curated_rank"] == 1 and d["clips"][0]["noise_db"] == -60.0
    assert d["clips"][1]["curated_rank"] is None
    assert d["clips"][0]["wav"] == "data/voices/wav/Pasqal/E1.wav"


def test_detail_designed_speaker_merges_scores_audit_overrides(cfg):
    put(cfg.voice_design / "audit.json", {"Muaran": {"cands": {"c0.wav": {"fit": 4}}, "pick": "c0.wav",
                                                     "order": ["c1.wav", "c0.wav"]}})
    put(cfg.voice_design / "overrides.json", {"Muaran": "A stern woman."})
    d = speakers.speaker_detail(cfg, "muaran")["design"]
    assert d["description"] == "A stern woman." and d["pick"] == "c0.wav"
    assert [c["id"] for c in d["candidates"]] == ["c1.wav", "c0.wav"]      # ranked order first
    c0 = next(c for c in d["candidates"] if c["id"] == "c0.wav")
    assert c0["verdict"] == {"fit": 4} and c0["scores"]["p_us"] == 0.2
    assert c0["file"] == "data/voice_design/clips/muaran/c0.wav"


def test_detail_unknown_slug_is_404(cfg):
    with pytest.raises(ApiError) as e:
        speakers.speaker_detail(cfg, "nobody")
    assert e.value.status == 404


def test_lines_include_bank_clip_and_skip_other_speakers(cfg):
    ls = speakers.speaker_lines(cfg, "Pasqal")
    assert [l["guid"] for l in ls] == ["g1", "g2"]
    assert ls[0]["baseline"] == "data/render/export/wav/g1.wav" and ls[1]["baseline"] is None
    assert ls[0]["emotion"] == "neutral" and ls[0]["instruct"] == "formal"


def test_registered_designed_speaker_stays_designed_and_shows_its_registered_clip(cfg):
    write_wav(cfg.voices / "prompts/designed/muaran.wav")
    put(cfg.voices / "prompts/prompts.json", {"Pasqal": [], "Muaran": [
        {"rank": 1, "event": "designed_muaran", "wav": "prompts/designed/muaran.wav", "text": "t", "duration": 1.0}]})
    s = by_name(cfg)["Muaran"]
    assert s["origin"] == "designed"
    d = speakers.speaker_detail(cfg, "muaran")
    assert d["design"] is not None
    assert [c["id"] for c in d["clips"]] == ["designed_muaran"]
    assert d["clips"][0]["wav"] == "data/voices/prompts/designed/muaran.wav"


def test_prompt_only_speaker_such_as_the_narrator_lists_its_prompt_clips(cfg):
    put(cfg.voices / "prompts/prompts.json", {"narrator_bg3": [
        {"rank": 1, "event": "n1", "wav": "prompts/narrator_bg3/01.wav", "text": "x", "duration": 9.0}]})
    d = speakers.speaker_detail(cfg, "narrator_bg3")
    assert [c["id"] for c in d["clips"]] == ["n1"] and d["design"] is None


def test_speaker_with_no_lines_or_clips_is_empty_not_error(cfg):
    put(cfg.voices / "prompts/prompts.json", {"Pasqal": [], "Ghost": []})
    assert speakers.speaker_lines(cfg, "Ghost") == []
    assert speakers.speaker_detail(cfg, "ghost")["clips"] == []


def test_a_slug_never_moves_to_another_speaker_when_a_colliding_name_appears(cfg):
    put(cfg.voices / "prompts/prompts.json", {"Ulfar!": []})
    first = {s["name"]: s["slug"] for s in speakers.list_speakers(cfg)}["Ulfar!"]
    put(cfg.voices / "prompts/prompts.json", {"Ulfar!": [], "Ulfar": []})     # "Ulfar" sorts before "Ulfar!"
    later = {s["name"]: s["slug"] for s in speakers.list_speakers(cfg)}
    assert later["Ulfar!"] == first and later["Ulfar"] != first
    put(cfg.voices / "prompts/prompts.json", {"Ulfar": []})                    # and a name that went away keeps its slug
    assert {s["name"]: s["slug"] for s in speakers.list_speakers(cfg)}["Ulfar"] == later["Ulfar"]
