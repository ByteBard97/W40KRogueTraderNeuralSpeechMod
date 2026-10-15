import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from conftest import put, write_wav  # noqa: E402
from studio_server import auto_cast_register as R  # noqa: E402
from studio_server.config import Config  # noqa: E402
from studio_server.router import Router  # noqa: E402
from studio_server.routes import build_router  # noqa: E402


def bg3(slug, refs=True):
    return {"slug": slug, "name": slug.title(), "lines": 300, "seconds": 1200.0, "gender": "male",
            "refs": [{"wav": f"data/bg3_voices/{slug}/ref_1.wav", "text": f"Ref of {slug}.", "seconds": 10.0}] if refs else []}


@pytest.fixture
def cfg(tmp_path):
    d = tmp_path / "data"
    put(d / "bg3_voices/catalog.json", [bg3("bruno"), bg3("carl"), bg3("silent", refs=False), bg3("ghosted")])
    write_wav(d / "bg3_voices/bruno/ref_1.wav")
    write_wav(d / "bg3_voices/carl/ref_1.wav")                                  # ghosted: listed ref, file missing
    put(d / "studio/auto_cast.json", {"items": {
        "Guard Hobb": {"status": "assigned", "bg3": "bruno", "processed": False, "steps": 15},
        "group:Scene_A|sailor": {"status": "assigned", "bg3": "carl", "processed": True, "steps": 20, "owner": True},
        "Mute": {"status": "assigned", "bg3": "silent", "processed": False, "steps": 15},
        "Lost": {"status": "assigned", "bg3": "ghosted", "processed": False, "steps": 15},
        "Real Voice": {"status": "assigned", "bg3": "bruno", "processed": False, "steps": 15},
        "Ghost": {"status": "needs_info", "missing": ["gender"]}}})
    put(d / "voices/prompts/prompts.json", {"Real Voice": [{"rank": 1, "event": "e", "wav": "prompts/designed/real.wav", "text": "x", "duration": 1, "source": "designed"}],
                                            "Abelard": [{"rank": 1, "wav": "prompts/Abelard/01.wav", "text": "y"}]})
    return Config(root=tmp_path)


def prompts(cfg):
    return json.loads((cfg.voices / "prompts/prompts.json").read_text())


def test_preview_lists_what_would_happen_and_touches_nothing(cfg):
    before = (cfg.voices / "prompts/prompts.json").read_bytes()
    out = R.preview(cfg)
    c = out["counts"]
    assert (c["assigned"], c["add"], c["skipped"], c["not_assigned"], c["processed"]) == (5, 2, 3, 1, 1)
    sailor = next(r for r in out["items"] if r["key"].startswith("group:"))
    assert sailor["bg3"] == "carl" and sailor["clip"] == "data/bg3_voices/carl/ref_1.wav" and sailor["steps"] == 20
    reasons = {s["key"]: s["reason"] for s in out["skipped"]}
    assert "no usable reference" in reasons["Mute"] and "no usable reference" in reasons["Lost"] and "left alone" in reasons["Real Voice"]
    assert (cfg.voices / "prompts/prompts.json").read_bytes() == before
    assert not (cfg.voices / "prompts/cast").exists()


def test_register_copies_clips_adds_entries_and_keeps_real_voices(cfg):
    out = R.register(cfg)
    assert sorted(out["registered"]) == ["Guard Hobb", "group:Scene_A|sailor"] and out["unchanged"] == 0 and len(out["skipped"]) == 3
    p = prompts(cfg)
    e = p["group:Scene_A|sailor"][0]
    assert e["wav"] == "prompts/cast/group_scene_a_sailor.wav" and e["text"] == "Ref of carl." and e["bg3"] == "carl"
    assert e["processed"] is True and e["steps"] == 20 and e["auto_cast"] is True
    assert (cfg.voices / e["wav"]).is_file() and (cfg.voices / "prompts/cast/guard_hobb.wav").is_file()
    assert p["Real Voice"][0]["source"] == "designed" and "Abelard" in p and "Mute" not in p
    assert out["backup"] and R.BACKUP_RE.match(out["backup"])
    assert "Guard Hobb" not in json.loads((cfg.voices / "prompts" / out["backup"]).read_text())            # the backup is the state before


def test_register_twice_changes_nothing_and_makes_no_second_backup(cfg):
    R.register(cfg)
    first = (cfg.voices / "prompts/prompts.json").read_bytes()
    again = R.register(cfg)
    assert again["registered"] == [] and again["unchanged"] == 2 and again["backup"] is None
    assert (cfg.voices / "prompts/prompts.json").read_bytes() == first
    assert len(list((cfg.voices / "prompts").glob("prompts.*.bak.json"))) == 1


def test_a_changed_pick_updates_our_entry(cfg):
    R.register(cfg)
    put(cfg.studio / "auto_cast.json", {"items": {"Guard Hobb": {"status": "assigned", "bg3": "carl", "processed": False, "steps": 15}}})
    assert R.preview(cfg)["counts"]["update"] == 1
    out = R.register(cfg)
    assert out["registered"] == ["Guard Hobb"] and prompts(cfg)["Guard Hobb"][0]["bg3"] == "carl"
    assert out["backup"] is None                                                   # inside the ten minute window


def test_backup_gap_expires(cfg):
    path = cfg.voices / "prompts/prompts.json"
    (path.parent / "prompts.20200101-000000.bak.json").write_text("{}")
    assert R.register(cfg)["backup"] is not None                                    # an old backup does not count


def test_a_cast_file_that_is_not_ours_is_not_overwritten(cfg):
    write_wav(cfg.voices / "prompts/cast/guard_hobb.wav", seconds=0.5)
    size = (cfg.voices / "prompts/cast/guard_hobb.wav").stat().st_size
    out = R.register(cfg)
    assert "Guard Hobb" in [s["key"] for s in out["skipped"]]
    assert (cfg.voices / "prompts/cast/guard_hobb.wav").stat().st_size == size


def test_routes(cfg):
    r: Router = build_router()
    code, body = r.dispatch("GET", "/api/assignments/register-preview", {}, {}, cfg, None)
    assert code == 200 and body["counts"]["add"] == 2
    code, body = r.dispatch("POST", "/api/assignments/register", {}, {}, cfg, None)
    assert code == 200 and len(body["registered"]) == 2
