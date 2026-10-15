import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from split_long import chunks, split_job  # noqa: E402


def test_chunks_keep_sentences_whole_and_lose_no_text():
    text = " ".join(f"Sentence number {i} goes here." for i in range(60))
    parts = chunks(text, 200)
    assert all(len(p) <= 200 for p in parts) and len(parts) > 1
    assert " ".join(parts) == text
    assert all(p.endswith(".") for p in parts)


def test_oversized_sentence_is_cut_at_a_space():
    parts = chunks("word " * 300, 100)
    assert all(len(p) <= 100 for p in parts)
    assert " ".join(parts).split() == ("word " * 300).split()


def test_split_job_names_and_orders_segments():
    job = {"guid": "g", "speaker": "narrator", "text": "A. " * 400, "src_text": "x", "voice_source": "narrator",
           "ref": {"wav": "r.wav", "text": "t", "emotion": None}, "annotation": None}
    segs = split_job(job, 100)
    assert [s["guid"] for s in segs] == [f"g~{k}" for k in range(len(segs))]
    assert all(s["parent"] == "g" and s["seg_count"] == len(segs) and s["seg_kind"] == "speech" for s in segs)
