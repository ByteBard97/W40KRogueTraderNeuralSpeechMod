import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import plan_recipe  # noqa: E402
import recipe_render as R  # noqa: E402
import recipe_text as T  # noqa: E402

SR = 24000
RECIPE = {"name": "t", "cfg": 2.5, "timesteps": 15, "normalize": False, "instruct": "annotation", "lexicon": False, "pronunciation": [],
          "punctuation": {"em_dash": "period"}, "pause_ms": 250, "gaps_ms": {}, "split": {"mode": "sentence", "max_chars": 220, "min_chars": 0},
          "level_match": True, "trim_silence": True, "onset_soften_db": 0.0, "peak_limit_db": -1.0, "seed": ""}


def job(text="Have no doubt — and as for him. I received a transport.", recipe=None):
    return {"guid": "g~q0", "speaker": "S", "text": text, "src_text": text, "voice_source": "prompt_bank", "annotation": {"instruct": "calm"},
            "recipe": recipe or RECIPE}


def speechlike(n, scale=0.03, seed=0):
    return np.random.default_rng(seed).laplace(0, scale, n).astype(np.float32)


def test_em_dash_becomes_a_sentence_with_a_capital():
    pieces = T.prepare("Have no doubt — and as for him. Done.", RECIPE)["pieces"]
    assert [p["text"] for p in pieces] == ["Have no doubt.", "And as for him.", "Done."]


def test_render_passes_text_instruct_cfg_and_seed_and_joins():
    calls = []

    def raw(text, ref, instruct, cfg, steps, normalize, seed):
        calls.append((text, instruct, cfg, steps, normalize, seed))
        return speechlike(SR * 2), SR

    row, wav, sr = R.render_recipe(raw, job(), "ref.wav")
    assert [c[0] for c in calls] == ["Have no doubt.", "And as for him.", "I received a transport."]
    assert all(c[1] == "calm" and c[2] == 2.5 and c[3] == 15 and c[4] is False for c in calls)
    assert len({c[5] for c in calls}) == 3                     # each piece its own seed
    assert row["status"] == "ok" and row["pieces"] == 3 and row["recipe"] == "t" and row["flags"] == []
    assert len(wav) / sr > 3 * 2 * 0.9 + 2 * 0.3                # three pieces plus two 350 ms gaps (minus trimmed silence)


def test_seed_is_stable_for_a_guid():
    assert R.stable_seed("a") == R.stable_seed("a") != R.stable_seed("b")


def test_overdriven_piece_is_retried_with_new_seed_then_lower_cfg():
    seen = []

    def raw(text, ref, instruct, cfg, steps, normalize, seed):
        seen.append((cfg, seed))
        squashed = np.clip(speechlike(SR * 2, 0.5, seed) , -0.3, 0.3)       # flat-topped: crest well under 11 dB
        return (squashed if len(seen) < 3 else speechlike(SR * 2, 0.03, seed)), SR

    row, wav, _ = R.render_recipe(raw, job("One short sentence here."), "r.wav")
    assert row["attempts"] == [3] and row["flags"] == []
    assert seen[0][0] == seen[1][0] == 2.5 and seen[2][0] == 2.0       # attempt 2 only changes the seed, attempt 3 lowers cfg by 0.5
    assert seen[0][1] != seen[1][1]


def test_still_overdriven_after_the_ladder_is_flagged_and_best_kept():
    def raw(text, ref, instruct, cfg, steps, normalize, seed):
        return np.clip(speechlike(SR * 2, 0.5, seed), -0.3, 0.3), SR

    row, wav, _ = R.render_recipe(raw, job("One short sentence here."), "r.wav")
    assert row["attempts"] == [4] and "piece_overdriven" in row["flags"] and len(wav)


def test_cfg_ladder_never_goes_below_the_floor():
    qc = {**R.QC_DEFAULT, "attempts": 9}
    assert R.piece_cfg(2.5, 0, qc) == 2.5 and R.piece_cfg(2.5, 1, qc) == 2.5 and R.piece_cfg(2.5, 2, qc) == 2.0
    assert R.piece_cfg(2.5, 8, qc) == 1.5


def test_engine_error_is_a_failed_row():
    def raw(*a, **k):
        raise RuntimeError("cuda out of memory")

    row, wav, sr = R.render_recipe_job(raw, job(), "r.wav")
    assert row["status"] == "failed" and "cuda" in row["error"] and wav is None


def test_plan_keeps_speech_pieces_of_the_speaker_and_skips_corrected_cues(tmp_path):
    rows = [{"guid": "c1~q0", "parent": "c1", "speaker": "V", "seg_kind": "speech", "text": "a"},
            {"guid": "c1~q1", "parent": "c1", "speaker": "narrator", "seg_kind": "speech", "text": "b"},
            {"guid": "c2~q0", "parent": "c2", "speaker": "V", "seg_kind": "speech", "text": "c"},
            {"guid": "c3~q0", "parent": "c3", "speaker": "W", "seg_kind": "speech", "text": "d"}]
    p = tmp_path / "jobs.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    out = plan_recipe.plan(p, "V", {"name": "x"}, skip={"c2"})
    assert [o["guid"] for o in out] == ["c1~q0"] and out[0]["recipe"] == {"name": "x"} and out[0]["respell"] is False
