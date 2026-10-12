import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/render_corpus"))

from plan_annotated import annotated_jobs  # noqa: E402

JOB = {"guid": "g1", "speaker": "Vladaym", "speaker_kind": "default_speaker", "src_text": "x", "priority": 1,
       "voice_source": "prompt_bank", "ref": {"wav": "v.wav", "text": "v"}, "annotation": {"emotion": "angry"}}
NARR = {"wav": "n.wav", "text": "n"}


def ref_fn(speaker, emotion):
    if speaker == "Jae":
        return {"wav": "jae.wav", "text": "j", "emotion": emotion}, "prompt_bank"
    return dict(NARR, emotion=None), "fallback"


def entry(*segs):
    return {"segments": [{"speaker": s, "kind": k, "text": t} for s, k, t in segs]}


def test_each_segment_gets_its_own_voice_and_a_distinct_id():
    jobs = annotated_jobs(JOB, entry(("narrator", "narration", "She turns."), ("Jae", "speech", "Fine."), ("Scout", "speech", "Wait!")), NARR, ref_fn)
    assert [j["guid"] for j in jobs] == ["g1~a0", "g1~a1", "g1~a2"]
    assert [j["speaker"] for j in jobs] == ["narrator", "Jae", "Scout"]
    assert [j["voice_source"] for j in jobs] == ["narrator", "prompt_bank", "fallback"]
    assert {j["parent"] for j in jobs} == {"g1"} and jobs[2]["seg_count"] == 3
    assert jobs[0]["seg_kind"] == "narration" and jobs[1]["seg_kind"] == "speech"


def test_cue_level_emotion_only_applies_to_the_cue_speaker():
    jobs = annotated_jobs(JOB, entry(("Vladaym", "speech", "Hmph."), ("Jae", "speech", "Fine.")), NARR, lambda s, e: ({"emotion": e}, "prompt_bank"))
    assert jobs[0]["ref"]["emotion"] == "angry" and jobs[1]["ref"]["emotion"] is None


def test_text_is_cleaned_for_tts():
    jobs = annotated_jobs(JOB, entry(("Jae", "speech", "Hello   there."), ("Scout", "speech", "Hi.")), NARR, ref_fn)
    assert jobs[0]["text"] == "Hello there."


def test_adjacent_segments_of_one_speaker_become_one_job():
    jobs = annotated_jobs(JOB, entry(("Scout", "speech", "Rich!"), ("Lookout", "speech", "Fly."), ("Lookout", "speech", "Fly. You coming?")), NARR, ref_fn)
    assert [j["speaker"] for j in jobs] == ["Scout", "Lookout"]
    assert jobs[1]["text"] == "Fly. Fly. You coming?" and jobs[1]["seg_count"] == 2 and jobs[1]["guid"] == "g1~a1"


def test_jobs_carry_every_field_stitch_mixed_reads():
    jobs = annotated_jobs(JOB, entry(("Jae", "speech", "Fine."), ("narrator", "narration", "She leaves.")), NARR, ref_fn)
    for j in jobs:
        assert {"parent", "seg_index", "seg_kind", "speaker", "text", "src_text"} <= set(j)
    assert next(j["speaker"] for j in jobs if j["seg_kind"] == "speech") == "Jae"
