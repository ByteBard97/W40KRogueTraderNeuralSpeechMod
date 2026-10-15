import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from conftest import put, write_wav  # noqa: E402
from studio_server import auto_cast, bg3_labels  # noqa: E402
from studio_server.config import Config  # noqa: E402
from studio_server.errors import ApiError  # noqa: E402

FULL = {"age": "adult", "class": "middle", "processing": "natural", "pitch": "middle", "species": "human", "accent": "received (RP)"}


def bg3(slug, name, gender="male"):
    return {"slug": slug, "name": name, "lines": 300, "seconds": 1200.0, "gender": gender, "median_f0_hz": 120.0, "non_human_hint": False,
            "refs": [{"wav": f"data/bg3_voices/{slug}/ref_1.wav", "text": "A reference.", "seconds": 10.0}]}


@pytest.fixture
def cfg(tmp_path):
    d = tmp_path / "data"
    put(d / "npc_profile/describe/casting_needs.json", [
        {"speaker": "Guard Hobb", "lines": 50, "chars": 2000, "approx_minutes": 3, "status": "voiceless", "gender": "male", "species": "human", "role": "soldier"},
        {"speaker": "Handmaid", "lines": 30, "chars": 1000, "approx_minutes": 2, "status": "voiceless", "gender": "female", "species": "human", "role": "servant"},
        {"speaker": "Already Cast", "lines": 99, "chars": 1000, "approx_minutes": 2, "status": "voiceless", "gender": "male", "species": "human", "role": "soldier"}])
    put(d / "bg3_voices/catalog.json", [bg3("bruno", "Bruno"), bg3("brenda", "Brenda", "female"), bg3("banned", "Banned"), bg3("carl", "Carl")])
    put(d / "studio/bg3_labels.json", {"bruno": {**FULL, "gender": "male"}, "brenda": {**FULL, "gender": "female"}, "carl": {**FULL, "gender": "male"},
                                        "banned": {**FULL, "gender": "male", "reserve": "do not use"}})
    put(d / "studio/casting.json", {"assignments": {"Already Cast": {"bg3": "carl", "at": "x"}}, "portraits": {}})
    put(d / "npc_profile/roster_35b_all.json", [{"conversation": "Scene_A", "roster": [
        {"id": "sailor", "label": "Sailor", "gender": "male", "species": "human", "role": "deckhand", "baseline_voice": "A gruff voice.", "evidence": ["he spat"], "fx": []},
        {"id": "ghost", "label": "Ghost", "gender": "unknown", "species": "unknown", "role": "", "baseline_voice": "", "evidence": [], "fx": []}]}])
    put(d / "studio/pools.json", {"slots": {}, "routes": {
        "g1": {"to": "slot", "entry": "Scene_A|sailor", "attr": {}, "slot": "male_human"}, "g2": {"to": "slot", "entry": " Scene_A|sailor", "attr": {}, "slot": "male_human"},
        "g3": {"to": "slot", "entry": "Scene_A|ghost", "attr": {}, "slot": "other"}, "g4": {"to": "speaker", "speaker": "Abelard"}}})
    for slug in ("bruno", "brenda", "carl", "banned"):
        write_wav(d / f"bg3_voices/{slug}/ref_1.wav")
    return Config(root=tmp_path)


def test_run_assigns_the_uncast_and_the_groups_and_leaves_hand_casting_alone(cfg):
    out = auto_cast.run(cfg)
    items = auto_cast.read(cfg)["items"]
    assert out == {"total": 4, "assigned": 3, "needs_info": 1}
    assert "Already Cast" not in items                                     # cast by hand: not a target
    assert items["Handmaid"]["bg3"] == "brenda" and items["Guard Hobb"]["bg3"] in ("bruno", "carl")
    sailor = items["group:Scene_A|sailor"]
    assert sailor["lines"] == 2 and sailor["status"] == "assigned" and sailor["bg3"] != "banned"       # both spellings of the entry are one group
    assert items["group:Scene_A|ghost"]["missing"] == ["gender", "species", "role or description"]
    assert json.loads((cfg.studio / "casting.json").read_text())["assignments"] == {"Already Cast": {"bg3": "carl", "at": "x"}}


def test_an_override_survives_a_rerun_and_can_be_handed_back(cfg):
    auto_cast.run(cfg)
    got = auto_cast.override(cfg, "Guard Hobb", "carl")
    assert got["owner"] is True and got["reasons"] == ["picked by you"]
    auto_cast.run(cfg)
    assert auto_cast.read(cfg)["items"]["Guard Hobb"]["bg3"] == "carl"
    auto_cast.override(cfg, "Guard Hobb", None)
    assert "owner" not in auto_cast.read(cfg)["items"]["Guard Hobb"]
    with pytest.raises(ApiError):
        auto_cast.override(cfg, "Guard Hobb", "banned")                    # ruled out by the owner
    with pytest.raises(ApiError):
        auto_cast.override(cfg, "nobody", "carl")


def test_the_page_names_the_voice_and_shows_a_few_lines(cfg):
    auto_cast.run(cfg)
    pg = auto_cast.page(cfg)
    assert pg["summary"]["assigned"] == 3
    hobb = next(r for r in pg["items"] if r["key"] == "Guard Hobb")
    assert hobb["voice_name"] in ("Bruno", "Carl")
