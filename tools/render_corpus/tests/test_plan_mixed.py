import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/render_corpus"))

from plan_mixed import SEP, segment_jobs  # noqa: E402

NARR = {"wav": "n.wav", "text": "narrator ref"}
JOB = {"guid": "abc", "speaker": "Argenta", "speaker_kind": "companion", "priority": 1, "voice_source": "prompt_bank",
       "ref": {"wav": "a.wav", "text": "argenta ref"}, "annotation": {"emotion": "stern"},
       "src_text": '{n}Argenta glares.{/n} "The warp takes everything."'}


def test_mixed_cue_becomes_ordered_segment_jobs():
    jobs = segment_jobs(JOB, NARR)
    assert [j["guid"] for j in jobs] == [f"abc{SEP}0", f"abc{SEP}1"]
    narration, speech = jobs
    assert narration["speaker"] == "narrator" and narration["ref"]["wav"] == "n.wav" and narration["annotation"] is None
    assert speech["speaker"] == "Argenta" and speech["ref"]["wav"] == "a.wav" and speech["annotation"] == {"emotion": "stern"}
    assert all(j["parent"] == "abc" and j["seg_count"] == 2 for j in jobs)


def test_pure_speech_cue_is_not_planned():
    assert segment_jobs({**JOB, "src_text": '"Only speech here, friend."'}, NARR) == []
