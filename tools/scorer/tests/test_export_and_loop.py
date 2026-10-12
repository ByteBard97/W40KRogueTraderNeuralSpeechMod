import json

from export_winners import export_winners
from loop import run_loop
from selection import VOICE_FEATURES, take_key

SCALE = {f: 1.0 for f in VOICE_FEATURES}


def score_row(v, wer=0.0):
    r = {f: v for f in VOICE_FEATURES}
    r.update(wer=wer, clipped=False, trail_silence=0.1, p_target_family=0.5, target_family="stern")
    return r


def test_export_copies_only_ok_and_existing(tmp_path):
    (tmp_path / "a.wav").write_bytes(b"RIFF")
    winners = {"a": {"status": "ok", "wav": "a.wav", "text": "t", "emotion": "e", "voice_score": 1.0, "flags": []},
               "b": {"status": "no_passing_take", "flags": []},
               "c": {"status": "ok", "wav": "missing.wav", "text": "t", "emotion": "e", "voice_score": 1.0, "flags": []}}
    out = tmp_path / "out"
    assert export_winners(out, winners, root=tmp_path) == 1
    assert (out / "export/wav/a.wav").read_bytes() == b"RIFF"
    assert list(json.loads((out / "export/index.json").read_text())) == ["a"]


def test_loop_retakes_only_weak_lines_until_done(tmp_path):
    """Line 'hard' only passes on takes >= 4; 'easy' passes always. Fake stages append to files."""
    out = tmp_path
    (out / "manifest.jsonl").write_text("")
    (out / "scores.jsonl").write_text("")
    calls = []

    def generate(takes, guids, guids_file=None):
        calls.append((takes, guids))
        have = {(m["guid"], m["take"]) for m in map(json.loads, (out / "manifest.jsonl").read_text().splitlines())}
        with open(out / "manifest.jsonl", "a") as f:
            for g in guids or ["easy", "hard"]:
                for t in range(takes):
                    if (g, t) not in have:
                        f.write(json.dumps({"guid": g, "take": t, "text": "x", "emotion": "e", "wav": f"{g}{t}"}) + "\n")

    def score():
        done = {json.loads(l)["key"] for l in (out / "scores.jsonl").read_text().splitlines()}
        with open(out / "scores.jsonl", "a") as f:
            for m in map(json.loads, (out / "manifest.jsonl").read_text().splitlines()):
                k = take_key(m["guid"], m["take"])
                if k not in done:
                    bad = m["guid"] == "hard" and m["take"] < 4
                    f.write(json.dumps({"key": k, "score": score_row(1.0, wer=0.9 if bad else 0.0)}) + "\n")

    winners = run_loop("x", out, SCALE, base_takes=3, max_takes=8, min_pass=2, retake_step=2, max_rounds=5,
                       generate=generate, score=score, log=lambda s: None)
    assert calls[0] == (3, None)
    assert all(g == ["hard"] for _, g in calls[1:])          # easy line never retaken
    assert winners["easy"]["n_takes"] == 3
    assert winners["hard"]["n_pass"] >= 2                      # retakes reached passing takes
    assert winners["hard"]["n_takes"] <= 8


def test_loop_stops_at_max_takes(tmp_path):
    out = tmp_path
    (out / "manifest.jsonl").write_text("")
    (out / "scores.jsonl").write_text("")
    def generate(takes, guids, guids_file=None):
        have = {(m["guid"], m["take"]) for m in map(json.loads, (out / "manifest.jsonl").read_text().splitlines())}
        with open(out / "manifest.jsonl", "a") as f:
            for t in range(takes):
                if ("h", t) not in have:
                    f.write(json.dumps({"guid": "h", "take": t, "text": "x", "emotion": "e", "wav": "w"}) + "\n")
    def score():
        done = {json.loads(l)["key"] for l in (out / "scores.jsonl").read_text().splitlines()}
        with open(out / "scores.jsonl", "a") as f:
            for m in map(json.loads, (out / "manifest.jsonl").read_text().splitlines()):
                k = take_key(m["guid"], m["take"])
                if k not in done:
                    f.write(json.dumps({"key": k, "score": score_row(1.0, wer=0.9)}) + "\n")
    w = run_loop("x", out, SCALE, base_takes=2, max_takes=6, min_pass=1, retake_step=2, max_rounds=10,
                 generate=generate, score=score, log=lambda s: None)
    assert w["h"]["n_takes"] == 6 and w["h"]["status"] == "no_passing_take"
