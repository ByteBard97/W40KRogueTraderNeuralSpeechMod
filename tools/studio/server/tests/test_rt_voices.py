import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from conftest import make_repo, put  # noqa: E402
from studio_server import rt_voices  # noqa: E402
from studio_server.errors import ApiError  # noqa: E402


def clip(speaker, n, seconds, text):
    return {"event": f"{speaker}{n}", "speaker": speaker, "wav": f"wav/{speaker}/{n}.wav", "duration": seconds, "texts": [{"guid": f"g{speaker}{n}", "text": text}]}


@pytest.fixture
def cfg(tmp_path):
    cfg = make_repo(tmp_path)
    clips = {f"A{i}": clip("Abelard", i, 3.0 + i, f"Line {i}.") for i in range(6)}
    clips["P0"] = clip("Pasqal", 0, 5.0, "Praise the Omnissiah.")
    clips["U0"] = clip("_unattributed", 0, 4.0, "Who said this?")
    put(cfg.data / "voices/catalog.json", clips)
    return cfg


def test_the_speakers_with_game_audio_are_listed_without_the_unattributed_clips(cfg):
    page = rt_voices.page(cfg)
    assert [v["slug"] for v in page["voices"]] == ["Abelard", "Pasqal"]
    a = page["voices"][0]
    assert a["lines"] == 6 and a["minutes"] == round((3 + 4 + 5 + 6 + 7 + 8) / 60, 1)
    assert 1 <= len(a["refs"]) <= rt_voices.SAMPLE_CLIPS and a["refs"][0]["wav"].startswith("data/voices/wav/Abelard/")
    assert a["complete"] is False and a["mine"] == {}


def test_the_label_set_has_the_bg3_vocabulary_plus_effects_and_clip_quality(cfg):
    keys = [d["key"] for d in rt_voices.page(cfg)["schema"]]
    assert keys[:5] == ["gender", "age", "class", "processing", "pitch"]
    assert {"accent", "species", "texture", "energy", "pace", "effects", "clip_quality", "note"} <= set(keys)
    assert rt_voices.LABELS.by_key["class"]["options"] == ["low", "low-middle", "middle", "middle-high", "high"]


def test_labels_are_saved_per_speaker_and_count_toward_progress(cfg):
    for k, v in (("gender", "male"), ("age", "adult"), ("class", "high"), ("processing", "processed"), ("pitch", "low-middle")):
        rt_voices.set_label(cfg, "Pasqal", k, v)
    rt_voices.set_label(cfg, "Pasqal", "effects", ["machine / vox-caster", "echo / reverb"])
    page = rt_voices.page(cfg)
    assert page["progress"] == {"total": 2, "complete": 1, "started": 1}
    assert next(v for v in page["voices"] if v["slug"] == "Pasqal")["mine"]["effects"] == ["machine / vox-caster", "echo / reverb"]
    assert json.loads((cfg.studio / "rt_labels.json").read_text())["Pasqal"]["processing"] == "processed"
    with pytest.raises(ApiError):
        rt_voices.set_label(cfg, "Pasqal", "processing", "shiny")
    with pytest.raises(ApiError):
        rt_voices.set_label(cfg, "Nobody", "gender", "male")                     # not a speaker with audio


def test_clips_the_extractor_left_unattributed_count_for_the_speaker_they_were_assigned_to(cfg):
    put(cfg.data / "voices/catalog.json", {**json.loads((cfg.data / "voices/catalog.json").read_text()),
        "X1": {**clip("_unattributed", 1, 6.0, "Hello."), "event": "Companions_Techpriest_1"}})
    put(cfg.data / "voices/attribution.json", {"X1": {"speaker": "Pasqal", "basis": "conversation name"}})
    pasqal = next(v for v in rt_voices.page(cfg)["voices"] if v["slug"] == "Pasqal")
    assert pasqal["lines"] == 2                                              # his own clip plus the re-attributed one
