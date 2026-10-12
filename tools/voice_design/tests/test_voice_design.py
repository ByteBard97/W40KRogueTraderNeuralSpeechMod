import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import wave  # noqa: E402
from audit_server import apply_order, apply_verdict  # noqa: E402
from clone_test import pick_lines, rank  # noqa: E402
from design import slug  # noqa: E402
from register import register  # noqa: E402


def test_slug():
    assert slug("Vladaym Tocara the Liege") == "vladaym_tocara_the_liege"


def test_apply_verdict_pick_toggle():
    a = apply_verdict({}, {"name": "X", "cand": "c1.wav", "accent": "british"})
    a = apply_verdict(a, {"name": "X", "cand": "c1.wav", "fit": "4"})
    a = apply_verdict(a, {"name": "X", "cand": "c1.wav", "pick": True})
    assert a["X"]["cands"]["c1.wav"] == {"accent": "british", "fit": 4} and a["X"]["pick"] == "c1.wav"
    a = apply_verdict(a, {"name": "X", "cand": "c1.wav", "pick": False})
    assert a["X"]["pick"] is None


def test_rank_prefers_low_p_us_then_utmos():
    scores = {"clips/x/c0.wav": {"p_us": 0.9, "utmos": 4}, "clips/x/c1.wav": {"p_us": 0.1, "utmos": 2},
              "clips/x/c2.wav": {"p_us": 0.1, "utmos": 3}}
    assert rank(["c0.wav", "c1.wav", "c2.wav"], "x", scores, 2) == ["c2.wav", "c1.wav"]


def test_pick_lines_filters_length():
    jobs = [{"speaker": "A", "guid": f"g{i}", "text": "x" * n} for i, n in enumerate([10, 90, 120, 150, 500])]
    assert [j["guid"] for j in pick_lines(jobs, "A")] == ["g1", "g3"]


def test_register_writes_prompt_bank(tmp_path):
    clip = tmp_path / "vd/clips/muaran/c2.wav"
    clip.parent.mkdir(parents=True)
    with wave.open(str(clip), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(b"\0\0" * 24000)
    prompts = {}
    done = register({"Muaran": {"pick": "c2.wav"}, "Nobody": {"pick": None}},
                    {"Muaran": {"slug": "muaran", "text": "hello", "description": "d"}},
                    prompts, vd_root=tmp_path / "vd", voices_root=tmp_path / "voices")
    assert done == ["Muaran"]
    assert prompts["Muaran"][0]["wav"] == "prompts/designed/muaran.wav"
    assert (tmp_path / "voices/prompts/designed/muaran.wav").is_file()


def test_save_preset_add_replace_and_clear():
    from audit_server import save_preset
    p = save_preset({}, "Pasqal", {"fx": {"hp": 300}, "speed": 1.123456})
    assert p == {"Pasqal": {"fx": {"hp": 300}, "speed": 1.123}}
    p = save_preset(p, "Pasqal", {"fx": {}, "speed": 1.0})   # nothing set: remove the preset
    assert p == {}


def test_rendered_speakers_samples_and_skips_test_runs(tmp_path):
    import json as _json
    from audit_server import rendered_speakers, sample_lines
    for run, rows in (("linux", [{"guid": f"g{i}", "speaker": "Cassia", "status": "ok", "text": "x" * 100} for i in range(20)]
                                + [{"guid": "bad", "speaker": "Cassia", "status": "failed", "text": "x" * 100}]),
                      ("mac-test", [{"guid": "t", "speaker": "Cassia", "status": "ok", "text": "x" * 100}])):
        d = tmp_path / run / "wav"
        d.mkdir(parents=True)
        (tmp_path / run / "manifest.jsonl").write_text("\n".join(_json.dumps(r) for r in rows))
        for r in rows:
            (d / f"{r['guid']}.wav").write_bytes(b"RIFF")
    out = rendered_speakers(tmp_path, n=5)
    assert list(out) == ["Cassia"] and out["Cassia"]["count"] == 20      # failed + test-run rows excluded
    assert len(out["Cassia"]["samples"]) == 5
    assert out["Cassia"]["samples"][0]["file"].startswith("render/linux/wav/g")
    assert len(sample_lines([], 3)) == 0


def test_save_library_overwrites_by_name_and_validates():
    import pytest as _pt
    from audit_server import save_library
    lib = save_library({}, " Dalek ", {"fx": {"ring": {"hz": 30, "mix": 1}}, "speed": 1})
    assert list(lib) == ["Dalek"]
    lib = save_library(lib, "Dalek", {"fx": {"hp": 300}, "speed": 1.1})
    assert lib["Dalek"] == {"fx": {"hp": 300}, "speed": 1.1}
    with _pt.raises(ValueError):
        save_library(lib, "  ", {"fx": {}})


def test_apply_order_sets_rank_and_pick():
    a = apply_order({}, {"name": "Danrok", "order": ["c3.wav", "c1.wav", "c2.wav"]})
    assert a["Danrok"]["order"] == ["c3.wav", "c1.wav", "c2.wav"]
    assert a["Danrok"]["pick"] == "c3.wav"
    assert apply_order(a, {"name": "Danrok", "order": []})["Danrok"]["pick"] is None


def test_seed_for_is_stable_and_varies():
    from design import seed_for
    assert seed_for("Muaran", 0) == seed_for("Muaran", 0)
    assert len({seed_for("Muaran", i) for i in range(6)}) == 6
    assert seed_for("Muaran", 0) != seed_for("Muaran", 0, "v2")
    assert 0 <= seed_for("Muaran", 0) < 2**31


def test_keep_candidate_appends_and_records(tmp_path):
    from audit_server import keep_candidate
    tmp = tmp_path / "t.wav"
    tmp.write_bytes(b"RIFF")
    man = {"Muaran": {"slug": "muaran", "candidates": ["c0.wav", "c1.wav"]}}
    cand = keep_candidate(man, "Muaran", tmp, {"seed": 7, "cfg": 2.0}, vd=tmp_path)
    assert cand == "c2.wav" and man["Muaran"]["candidates"][-1] == "c2.wav"
    assert (tmp_path / "clips/muaran/c2.wav").read_bytes() == b"RIFF"
    assert man["Muaran"]["gen"]["candidates"]["c2.wav"] == {"seed": 7, "cfg": 2.0, "live": True}
