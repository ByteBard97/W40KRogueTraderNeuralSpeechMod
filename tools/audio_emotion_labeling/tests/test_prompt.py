import pytest

from prompt import build_prompt, prompt_hash
from vocab import load_vocab


@pytest.fixture
def vocab(tmp_path):
    return load_vocab(tmp_path / "missing.json")  # Original tier only, deterministic


def test_build_prompt_audio_only_lists_vocabulary(vocab):
    text = build_prompt(vocab, "audio", transcript=None)
    assert "angry" in text
    assert "exactly 3" in text.lower() or "3 ranked" in text.lower()
    assert "Transcript" not in text


def test_build_prompt_audio_plus_text_includes_transcript(vocab):
    text = build_prompt(vocab, "audio+text", transcript="Hold the line!")
    assert "Hold the line!" in text


def test_build_prompt_requires_transcript_for_audio_plus_text(vocab):
    with pytest.raises(ValueError):
        build_prompt(vocab, "audio+text", transcript=None)


def test_prompt_hash_stable_across_transcripts(vocab):
    h1 = prompt_hash(vocab, "audio+text")
    text_a = build_prompt(vocab, "audio+text", transcript="Line A")
    text_b = build_prompt(vocab, "audio+text", transcript="Line B")
    assert text_a != text_b  # per-clip prompts do differ
    assert h1 == prompt_hash(vocab, "audio+text")  # but the template hash doesn't


def test_prompt_hash_differs_between_modes(vocab):
    assert prompt_hash(vocab, "audio") != prompt_hash(vocab, "audio+text")
