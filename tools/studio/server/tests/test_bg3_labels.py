import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from conftest import put  # noqa: E402
from studio_server import bg3_labels, casting  # noqa: E402
from studio_server.errors import ApiError  # noqa: E402
from test_casting import cfg as _cfg  # noqa: E402,F401  (the fake repo fixture)


def test_schema_has_the_five_required_labels_first():
    assert bg3_labels.REQUIRED == ["gender", "age", "class", "processing", "pitch"]
    assert [d["key"] for d in bg3_labels.SCHEMA[:5]] == bg3_labels.REQUIRED
    assert bg3_labels.BY_KEY["gender"]["options"] == ["male", "female", "neuter"]
    assert bg3_labels.BY_KEY["age"]["options"] == ["child", "youth", "adult", "old"]


def test_setting_a_label_persists_and_clearing_removes_it(_cfg):
    assert bg3_labels.set_label(_cfg, "gortash", "class", "high") == {"class": "high"}
    assert bg3_labels.read_all(_cfg)["gortash"]["class"] == "high"
    assert bg3_labels.set_label(_cfg, "gortash", "class", None) == {}
    assert "gortash" not in bg3_labels.read_all(_cfg)


def test_a_multi_label_keeps_schema_order_and_rejects_unknown_options(_cfg):
    out = bg3_labels.set_label(_cfg, "gortash", "texture", ["smooth", "raspy"])
    assert out["texture"] == ["raspy", "smooth"]
    with pytest.raises(ApiError):
        bg3_labels.set_label(_cfg, "gortash", "texture", ["nope"])
    with pytest.raises(ApiError):
        bg3_labels.set_label(_cfg, "gortash", "pitch", "very high")
    with pytest.raises(ApiError):
        bg3_labels.set_label(_cfg, "gortash", "colour", "red")


def test_automatic_guesses_show_in_the_filters_but_do_not_count_as_labelled(_cfg):
    voices = {v["slug"]: v for v in casting.bg3_voices(_cfg)}
    g = voices["gortash"]                       # fixture voice: male, 120 Hz
    assert g["labels"]["gender"] == "male" and g["labels"]["pitch"] == "middle"
    assert g["mine"] == {} and g["complete"] is False
    for key, val in (("gender", "male"), ("age", "adult"), ("class", "high"), ("processing", "natural"), ("pitch", "middle")):
        bg3_labels.set_label(_cfg, "gortash", key, val)
    assert next(v for v in casting.bg3_voices(_cfg) if v["slug"] == "gortash")["complete"] is True


def test_my_label_wins_over_the_automatic_guess(_cfg):
    bg3_labels.set_label(_cfg, "gortash", "pitch", "low")
    assert next(v for v in casting.bg3_voices(_cfg) if v["slug"] == "gortash")["labels"]["pitch"] == "low"


def test_progress_counts_fully_labelled_voices(_cfg):
    voices = casting.bg3_voices(_cfg)
    for key, val in (("gender", "male"), ("age", "adult"), ("class", "high"), ("processing", "natural")):
        bg3_labels.set_label(_cfg, "gortash", key, val)
    p = bg3_labels.progress(_cfg, voices)
    assert p["complete"] == 0 and p["started"] == 1 and p["total"] == len(voices)
    bg3_labels.set_label(_cfg, "gortash", "pitch", "middle")
    assert bg3_labels.progress(_cfg, voices)["complete"] == 1


def test_a_backup_is_kept_while_labelling(_cfg):
    bg3_labels.set_label(_cfg, "gortash", "class", "low")
    assert list(_cfg.studio.glob("bg3_labels.*.bak.json"))


def test_pool_slots_are_casting_targets_for_the_nameless_speakers(_cfg):
    put(_cfg.studio / "pools.json", {"slots": {"female_human": {"id": "female_human", "name": "Female human", "speaker_key": "pool_female_human",
                                                              "gender": "female", "species": "human", "age": None, "lines": 281}},
                                     "routes": {}})
    page = casting.page(_cfg)
    slot = next(c for c in page["characters"] if c["speaker"] == "pool_female_human")
    assert slot["kind"] == "slot" and slot["rank"] is None and slot["lines"] == 281 and slot["role"].startswith("Nameless speakers")
    assert slot["suggestions"]                                   # offered voices that fit a woman
    casting.assign(_cfg, "pool_female_human", "shadowheart")
    assert next(c for c in casting.page(_cfg)["characters"] if c["speaker"] == "pool_female_human")["assignment"]["name"] == "Shadowheart"
    assert [c["speaker"] for c in page["characters"] if c["kind"] == "character"][0] == "Vladaym Tocara the Liege"      # named characters stay first, by lines


def test_a_voice_in_between_can_carry_several_values_of_a_category_label(_cfg):
    out = bg3_labels.set_label(_cfg, "gortash", "age", ["adult", "youth"])
    assert out["age"] == ["youth", "adult"]                              # schema order, not click order
    assert bg3_labels.set_label(_cfg, "gortash", "age", ["old"]) == {"age": "old"}      # one value is a plain string again
    with pytest.raises(ApiError):
        bg3_labels.set_label(_cfg, "gortash", "rating", ["1", "2"])          # a rating is one number
    with pytest.raises(ApiError):
        bg3_labels.set_label(_cfg, "gortash", "reserve", ["free", "do not use"])


def test_a_several_valued_required_label_counts_as_set(_cfg):
    for key, val in (("gender", ["male", "female"]), ("age", ["youth", "adult"]), ("class", "low"), ("processing", "natural"), ("pitch", "low-middle")):
        bg3_labels.set_label(_cfg, "gortash", key, val)
    assert next(v for v in casting.bg3_voices(_cfg) if v["slug"] == "gortash")["complete"] is True


def test_class_and_pitch_have_five_steps_both_running_low_to_high(_cfg):
    steps = ["low", "low-middle", "middle", "middle-high", "high"]
    assert bg3_labels.BY_KEY["class"]["options"] == steps
    assert bg3_labels.BY_KEY["pitch"]["options"] == steps
    assert bg3_labels.set_label(_cfg, "gortash", "class", "low-middle") == {"class": "low-middle"}
    with pytest.raises(ApiError):
        bg3_labels.set_label(_cfg, "gortash", "pitch", ["low", "middle"])          # in-between is its own button now


def test_two_neighbouring_picks_become_the_in_between_step():
    f = bg3_labels.between_value
    assert f("class", ["low", "middle"]) == "low-middle"
    assert f("class", ["middle", "high"]) == "middle-high"
    assert f("pitch", ["middle", "low"]) == "low-middle"              # click order does not matter
    assert f("pitch", ["high", "middle"]) == "middle-high"
    assert f("pitch", ["low", "high"]) is None                       # not neighbours: left for the owner to decide
    assert f("class", "middle") is None and f("age", ["youth", "adult"]) is None


def test_migration_converts_saved_labels_and_backs_up_first(_cfg):
    bg3_labels.path(_cfg).parent.mkdir(parents=True, exist_ok=True)
    bg3_labels.path(_cfg).write_text(json.dumps({
        "a": {"class": ["low", "middle"], "pitch": ["high", "middle"], "gender": "male"},
        "b": {"class": "high", "pitch": ["middle", "low"]},
        "c": {"pitch": ["low", "high"]},
    }))
    report = bg3_labels.migrate_between_values(_cfg)
    got = bg3_labels.read_all(_cfg)
    assert got["a"] == {"class": "low-middle", "pitch": "middle-high", "gender": "male"}
    assert got["b"] == {"class": "high", "pitch": "low-middle"}
    assert got["c"] == {"pitch": ["low", "high"]}
    assert report == {"converted": 3, "left": ["c: pitch"], "backup": report["backup"]} and report["backup"]
    assert bg3_labels.migrate_between_values(_cfg)["converted"] == 0           # safe to run twice


def test_do_not_use_counts_as_fully_labelled(_cfg):
    assert bg3_labels.is_complete({"reserve": "do not use"}) is True
    assert bg3_labels.is_complete({"reserve": "free"}) is False
    bg3_labels.set_label(_cfg, "gortash", "reserve", "do not use")
    assert next(v for v in casting.bg3_voices(_cfg) if v["slug"] == "gortash")["complete"] is True
    assert bg3_labels.progress(_cfg, [{"slug": "gortash"}, {"slug": "other"}])["complete"] == 1
