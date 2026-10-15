import json
import time

import numpy as np
import pytest

from conftest import make_repo, put, write_wav
from mock_backend import MockBackend
from studio_server import lab, lab_audio, lab_text
from studio_server.errors import ApiError
from studio_server.model import ModelClient

NAME = "Vladaym Tocara the Liege"
LONG = "Naturally, I tried contacting other Rogue Traders. But the terms would have bled Footfall dry — and as for him — I received a transport."


def test_em_dash_pause_cuts_and_sets_gap():
    r = lab_text.prepare(LONG, {"punctuation": {"em_dash": "pause"}, "pause_ms": 300, "split": {"mode": "sentence", "max_chars": 140, "min_chars": 10}})
    texts = [p["text"] for p in r["pieces"]]
    assert "—" not in " ".join(texts)
    dash_gaps = [p["gap_ms"] for p in r["pieces"] if p["kind"] == "dash"]
    assert dash_gaps == [300, 300]
    assert r["pieces"][-1]["gap_ms"] == 0


def test_punctuation_keep_leaves_text_alone():
    out, pauses = lab_text.apply_punctuation("Well — fine... ok; yes", {})
    assert out == "Well — fine... ok; yes" and pauses == []


def test_em_dash_to_comma_and_ellipsis_survives():
    out, _ = lab_text.apply_punctuation("Well — fine... ok", {"em_dash": "comma"})
    assert out == "Well, fine... ok"


@pytest.mark.parametrize("mode,expect", [("whole", 1), ("sentence", 2)])
def test_split_modes(mode, expect):
    assert len(lab_text.split_text("One thing is true. And here is another one, longer.", {"mode": mode, "min_chars": 5})) == expect


def test_max_split_never_exceeds_limit_and_keeps_all_words():
    text = " ".join(f"word{i}" for i in range(60))
    pieces = lab_text.split_text(text, {"mode": "max", "max_chars": 80, "min_chars": 5})
    assert all(len(p) <= 80 for p, _ in pieces)
    assert " ".join(p for p, _ in pieces).split() == text.split()


def test_abbreviation_does_not_split():
    pieces = lab_text.split_text("Dr. Vego spoke. Then he left.", {"mode": "sentence", "min_chars": 5})
    assert [p for p, _ in pieces] == ["Dr. Vego spoke.", "Then he left."]


def test_pronunciation_override_wins_over_lexicon():
    out = lab_text.apply_pronunciation("Juvenna von Valancius smiled.", [{"word": "von Valancius", "mode": "arpabet", "value": "V AA1 N V AH0 L AE1 N S IY0 AH0 S"}])
    assert "{V AA1 N V AH0 L AE1 N S IY0 AH0 S}" in out and "smiled" in out


def test_pronunciation_plain_and_literal():
    assert lab_text.apply_pronunciation("say Foo now", [{"word": "Foo", "mode": "literal", "value": "fuu"}], lexicon=False) == "say fuu now"
    assert lab_text.apply_pronunciation("say Foo now", [{"word": "Foo", "mode": "plain"}], lexicon=False) == "say Foo now"


def test_metrics_flags_squashed_signal():
    rng = np.random.default_rng(0)
    speechlike = rng.laplace(0, 0.03, 48000).astype(np.float32)          # peaky, like speech: crest around 17 dB
    squashed = np.clip(rng.laplace(0, 0.03, 48000) * 40, -0.9, 0.9).astype(np.float32)
    assert lab_audio.metrics(speechlike, 24000)["flag"] is None
    assert lab_audio.metrics(squashed, 24000)["flag"] in ("overdriven", "clipped")


def test_limit_peak_only_scales_down():
    x = np.array([0.0, 1.5, -0.5], dtype=np.float32)
    assert abs(float(np.abs(lab_audio.limit_peak(x, -1.0)).max()) - 10 ** (-1 / 20)) < 1e-6
    q = np.array([0.1, -0.2], dtype=np.float32)
    assert (lab_audio.limit_peak(q, -1.0) == q).all()


def test_join_inserts_silence():
    a = np.ones(2400, dtype=np.float32) * 0.5
    out = lab_audio.join([a, a], [500], 24000)
    assert len(out) == 2400 * 2 + 12000


def test_check_recipe_rejects_bad_values():
    for bad in ({"cfg": 0}, {"seed": "abc"}, {"instruct": "x"}, {"split": {"mode": "bogus"}}, {"punctuation": {"em_dash": "explode"}}):
        with pytest.raises(ApiError):
            lab.check_recipe(bad)
    assert lab.check_recipe({"cfg": 2.0})["timesteps"] == 10


@pytest.fixture
def stack(tmp_path):
    cfg = make_repo(tmp_path)
    write_wav(cfg.data / "voices/prompts/cast/vladaym.wav", 1.0)
    jobs = [{"guid": f"c1~q{i}", "parent": "c1", "seg_index": i, "seg_kind": "speech", "speaker": NAME, "speaker_kind": "unit", "text": t,
             "src_text": t, "ref": {"wav": "data/voices/prompts/cast/vladaym.wav", "text": "ref"}, "annotation": {"instruct": "formal"}}
            for i, t in enumerate(["A short line.", "Another line — with a dash. And a second sentence."])]
    jobs.append({"guid": "n~q0", "parent": "n", "seg_index": 0, "seg_kind": "speech", "speaker": "narrator", "text": "You see.", "ref": {"wav": "x"}})
    (cfg.render).mkdir(parents=True, exist_ok=True)
    (cfg.render / lab.CAST_JOBS).write_text("".join(json.dumps(j) + "\n" for j in jobs), encoding="utf-8")
    write_wav(cfg.render / "cast/wav/c1~q0.wav", 1.0)
    lab._CACHE.update(mtime=None, by_speaker={})
    be = MockBackend(cfg.voice_design)
    yield cfg, ModelClient(be.url, root=cfg.root, live_dir=cfg.voice_design), be
    be.close()


def test_lines_exclude_narrator_and_carry_metrics(stack):
    cfg, _, _ = stack
    out = lab.lines(cfg, "vladaym_tocara_the_liege")
    assert [x["guid"] for x in out["lines"]] == ["c1~q0", "c1~q1"]
    assert out["lines"][0]["current"]["seconds"] == 1.0 and out["lines"][1]["current"] is None
    assert out["lines"][0]["instruct"] == "formal"
    assert lab.canon(cfg, "Vladaym%20Tocara%20the%20Liege") == NAME


def test_render_batch_makes_takes_with_pieces_and_gaps(stack):
    cfg, model, be = stack
    rec = {"punctuation": {"em_dash": "pause"}, "split": {"mode": "sentence", "min_chars": 5, "max_chars": 140}, "pause_ms": 400}
    job = lab.start_render(cfg, model, {"speaker": NAME, "items": [{"guid": "c1~q1", "label": "t"}], "recipe": rec, "seeds": [5, 6]})
    for _ in range(100):
        j = lab.get_job(job["id"])
        if j["state"] not in ("queued", "running"):
            break
        time.sleep(0.05)
    assert j["state"] == "done" and j["done"] == 2 and len(j["take_ids"]) == 2
    t = lab.takes(cfg, NAME, "c1~q1")
    assert len(t) == 2 and {x["seed"] for x in t} == {5, 6}
    assert len(t[0]["pieces"]) == 3                      # cut at the dash, then two sentences
    assert (cfg.root / t[0]["wav"]).is_file()
    assert be.calls[0]["instruct"] == "formal" and be.calls[0]["cfg"] == 3.0 and "—" not in be.calls[0]["text"]
    # 3 pieces of 0.1 s with a 400 ms gap after the first and 350 ms after the second
    assert t[0]["metrics"]["seconds"] > 0.3 + 0.7 - 0.05


def test_instruct_none_and_custom(stack):
    cfg, model, be = stack
    for mode, text, expect in (("none", "", None), ("custom", "angry", "angry")):
        be.calls.clear()
        job = lab.start_render(cfg, model, {"speaker": NAME, "items": [{"guid": "c1~q0"}], "recipe": {"instruct": mode, "instruct_text": text}, "seeds": [1]})
        while lab.get_job(job["id"])["state"] in ("queued", "running"):
            time.sleep(0.05)
        assert be.calls[0].get("instruct") == expect


def test_backend_error_is_reported_on_the_job(stack):
    cfg, model, be = stack
    be.fail = True
    job = lab.start_render(cfg, model, {"speaker": NAME, "items": [{"guid": "c1~q0"}], "recipe": {}, "seeds": [1]})
    while lab.get_job(job["id"])["state"] in ("queued", "running"):
        time.sleep(0.05)
    j = lab.get_job(job["id"])
    assert j["state"] == "error" and "boom" in j["error"]


def test_rate_hide_and_recipes(stack):
    cfg, model, _ = stack
    job = lab.start_render(cfg, model, {"speaker": NAME, "items": [{"guid": "c1~q0"}], "recipe": {}, "seeds": [1]})
    while lab.get_job(job["id"])["state"] in ("queued", "running"):
        time.sleep(0.05)
    tid = lab.get_job(job["id"])["take_ids"][0]
    assert lab.update_take(cfg, NAME, tid, {"rating": 4, "note": "good"})["rating"] == 4
    with pytest.raises(ApiError):
        lab.update_take(cfg, NAME, tid, {"rating": 9})
    lab.update_take(cfg, NAME, tid, {"hidden": True})
    assert lab.takes(cfg, NAME) == []
    names = [r["name"] for r in lab.save_recipe(cfg, {"name": "mine", "recipe": {"cfg": 2.0}})]
    assert names[0].startswith("production") and "mine" in names


def test_real_clips_match_text_and_skip_unattributed(tmp_path):
    cfg = make_repo(tmp_path)
    put(cfg.data / "voices/catalog.json", {
        "a": {"speaker": "Heinrix", "wav": "wav/Heinrix/a.wav", "duration": 9.0, "texts": [{"guid": "1", "text": "The von Valancius dynasty."}]},
        "b": {"speaker": "Idira", "wav": "wav/Idira/b.wav", "duration": 4.0, "texts": [{"guid": "2", "text": "Von Valancius, hello."}]},
        "c": {"speaker": "_unattributed", "wav": "wav/u/c.wav", "duration": 1.0, "texts": [{"guid": "3", "text": "von Valancius"}]}})
    lab._REAL.clear()
    out = lab.real_clips(cfg, "valancius")
    assert [o["speaker"] for o in out] == ["Idira", "Heinrix"] and out[0]["wav"] == "data/voices/wav/Idira/b.wav"
    assert lab.real_clips(cfg, "va") == []


def test_match_levels_brings_pieces_together():
    sr = 24000
    rng = np.random.default_rng(1)
    quiet, loud = rng.laplace(0, 0.01, sr), rng.laplace(0, 0.04, sr)
    a, b = lab_audio.match_levels([quiet, loud], sr)
    assert abs(lab_audio.speech_level_db(a, sr) - lab_audio.speech_level_db(b, sr)) < 0.2
    assert lab_audio.match_levels([quiet], sr)[0] is quiet


def test_trim_silence_keeps_margin():
    sr = 24000
    x = np.concatenate([np.zeros(sr), np.ones(sr // 2) * 0.5, np.zeros(sr)]).astype(np.float32)
    y = lab_audio.trim_silence(x, sr, keep_ms=40)
    assert abs(len(y) - (sr // 2 + 2 * int(sr * 0.04))) <= 2


def test_soften_onset_ramps_up_and_leaves_the_rest():
    sr = 24000
    x = np.ones(sr, dtype=np.float32)
    y = lab_audio.soften_onset(x, sr, -6.0, 100)
    assert abs(y[0] - 10 ** (-6 / 20)) < 0.01 and y[int(sr * 0.1) + 5] == 1.0 and (y >= 10 ** (-6 / 20) - 1e-6).all()
    assert (lab_audio.soften_onset(x, sr, 0.0, 100) == x).all()


def test_render_applies_level_trim_and_soften(stack):
    cfg, model, be = stack
    rec = {"split": {"mode": "sentence", "min_chars": 5, "max_chars": 140}, "level_match": True, "trim_silence": True, "onset_soften_db": -4.0}
    job = lab.start_render(cfg, model, {"speaker": NAME, "items": [{"guid": "c1~q1"}], "recipe": rec, "seeds": [1]})
    while lab.get_job(job["id"])["state"] in ("queued", "running"):
        time.sleep(0.05)
    assert lab.get_job(job["id"])["state"] == "done"
    with pytest.raises(ApiError):
        lab.check_recipe({"onset_soften_db": 5})


def test_opus_preview_encodes_decodes_and_reports_size(tmp_path):
    import shutil
    from studio_server import lab_opus
    if not shutil.which("ffmpeg") and not (lab_opus.Path(lab_opus._BNK) / "wem.py").is_file():
        pytest.skip("no ffmpeg")
    cfg = make_repo(tmp_path)
    write_wav(cfg.data / "render/x.wav", 2.0, sr=24000)
    try:
        out = lab_opus.preview(cfg, "data/render/x.wav", 24)
    except Exception as e:                       # libopus missing on this machine
        pytest.skip(str(e))
    assert out["kbps"] == 24 and out["opus_bytes"] < out["source_bytes"] and (cfg.root / out["wav"]).is_file() and out["ratio"] > 3
    with pytest.raises(ApiError):
        lab_opus.preview(cfg, "data/render/x.wav", 7)
    with pytest.raises(ApiError):
        lab_opus.preview(cfg, "../etc/passwd", 24)


def test_a_processed_speaker_renders_with_twenty_steps_in_the_lab_too(stack):
    cfg, model, be = stack
    put(cfg.studio / "npc_processing.json", {NAME: True})
    job = lab.start_render(cfg, model, {"speaker": NAME, "items": [{"guid": "c1~q1", "label": "t"}], "recipe": {"timesteps": 15}, "seeds": [5]})
    for _ in range(100):
        if lab.get_job(job["id"])["state"] not in ("queued", "running"):
            break
        time.sleep(0.05)
    assert be.calls[0]["timesteps"] == 20
