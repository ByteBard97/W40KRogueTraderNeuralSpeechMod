# Audio-LLM Emotion Labeling Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a harness that uses a local audio-input LLM to assign emotion-vocabulary
labels to Rogue Trader's voiced reference-clip catalog, validated on Abelard (the one
hand-labeled character) before running overnight across the full 5,188-clip catalog.

**Architecture:** Two interchangeable backend adapters (Ultravox, Qwen2-Audio-7B), each in
its own venv, driven by a shared resumable batch runner (`label.py`) that writes a JSON
signal file keyed by event/backend/mode/prompt-hash. A separate scorer (`score_pilot.py`)
compares that signal against the 79 Abelard clips already hand-labeled in `curation.json`,
using soft (tier-distance) metrics rather than exact match, since the human ground truth
itself was frequently uncertain between several plausible labels.

**Tech Stack:** Python 3.12, `transformers` 4.57.3, `torch` 2.11.0+cu128, `bitsandbytes`,
`librosa`/`soundfile` for audio resampling, `pytest` for the pure-logic modules.

**Spec:** `docs/superpowers/specs/2026-09-11-audio-llm-emotion-labeling-design.md`

## Global Constraints

- Model candidates, pinned: Ultravox `fixie-ai/ultravox-v0_5-llama-3_1-8b` at revision
  `94aa77f70ca548e669ea61f737e159b2fddbb7f7`; Qwen2-Audio `Qwen/Qwen2-Audio-7B-Instruct`
  at revision `0a095220c30b7b31434169c3086508ef3ea5bf0a`. Both revisions were resolved
  directly from the HF Hub API on 2026-09-11 — use them as-is, don't re-resolve.
- 4-bit via `bitsandbytes` is the default load path, but unverified on this machine's
  Blackwell (sm_120) GPU — every backend's smoke-load step must confirm it works or fall
  back to bf16 (`device_map="auto"`, no quantization) before anything else proceeds.
- Source WAVs are 48kHz mono 16-bit; every backend adapter resamples to 16kHz mono via
  `librosa.load(path, sr=16000, mono=True)` before inference — never rely on a model's
  own loader to do this silently.
- Generation is deterministic: `do_sample=False` (greedy), `max_new_tokens=192`.
- Every generation call requests exactly 3 ranked labels (never "1-3") so Recall@k is
  comparable across backends.
- Output signal file: `data/voices/emotion_banks/audio_llm_labels.json`, keyed
  `event -> backend -> mode -> prompt_hash -> entry`. `prompt_hash` is part of the key
  path, not just a stored field.
- Pilot scope: all 325 Abelard catalog clips (`data/voices/catalog.json`, `speaker ==
  "Abelard"`). Accuracy is scored only against the 79 with non-null `emotion` in
  `data/voices/emotion_banks/curation.json`.
- Run any GPU step (smoke tests, pilot, full run) with Solasta 2 closed — it currently
  holds ~5GB of the RTX 5080's 16GB.
- Model `notes` proposals (off-vocabulary words) are tallied and reported, never
  auto-added to `data/voices/emotion_banks/custom_emotions.json`.

---

## File Structure

```
tools/audio_emotion_labeling/
  vocab.py                  # combined emotion vocabulary + tier lookup
  prompt.py                 # prompt text builder + template hash
  parsing.py                # robust JSON extraction from raw model text
  scoring.py                # pure metric functions (tier similarity, recall@k)
  label.py                  # resumable batch runner (CLI) + iter_labels() core
  score_pilot.py             # pilot accuracy report (CLI)
  backends/
    __init__.py
    qwen2audio.py            # load_model() / generate() for Qwen2-Audio-7B
    ultravox.py               # load_model() / generate() for Ultravox
  tests/
    test_vocab.py
    test_prompt.py
    test_parsing.py
    test_scoring.py
    test_label_resume.py     # iter_labels() against a fake generate_fn
  .venv-qwen2audio/          # created by Task 1, not committed
  .venv-ultravox/            # created by Task 2, not committed
```

`vocab.py`, `prompt.py`, `parsing.py`, `scoring.py`, and `iter_labels()` in `label.py`
have zero heavy dependencies (stdlib only) and run under plain `python3` — they're fully
unit-tested without a GPU or either venv. Only the two `backends/*.py` modules and
`label.py`'s CLI wrapper need `torch`/`transformers`, and each is run from its own venv
(`.venv-qwen2audio/bin/python label.py --backend qwen2audio ...` or the ultravox
equivalent) — `label.py` lazily imports only the backend module its `--backend` flag
selects, so it never needs both venvs' packages at once.

---

### Task 1: Qwen2-Audio backend — venv, adapter, smoke-load

**Files:**
- Create: `tools/audio_emotion_labeling/.venv-qwen2audio/` (venv)
- Create: `tools/audio_emotion_labeling/backends/__init__.py`
- Create: `tools/audio_emotion_labeling/backends/qwen2audio.py`

**Interfaces:**
- Produces: `load_model() -> tuple[model, processor, dict]` where the returned dict is
  `{"model_id": str, "quant": str, "temperature": 0.0, "max_new_tokens": 192}` (`quant` is
  `"4bit-bnb"` or `"bf16"` depending on which path actually succeeded; `temperature`/
  `max_new_tokens` are fixed constants recorded here so `label.py` can store them on every
  entry without needing to know backend internals).
- Produces: `generate(model, processor, wav_path: str, prompt_text: str) -> str` — raw
  decoded text from the model.

- [ ] **Step 1: Create the venv and install pinned dependencies**

```bash
cd /home/geoff/projects/W40KRogueTraderNeuralSpeechMod/tools/audio_emotion_labeling
python3 -m venv .venv-qwen2audio
.venv-qwen2audio/bin/pip install --upgrade pip
.venv-qwen2audio/bin/pip install torch==2.11.0 --index-url https://download.pytorch.org/whl/cu128
.venv-qwen2audio/bin/pip install transformers==4.57.3 accelerate==1.12.0 bitsandbytes librosa soundfile
```

Run: `.venv-qwen2audio/bin/python3 -c "import torch; print(torch.__version__, torch.cuda.is_available())"`
Expected: prints a version containing `+cu128` and `True`. If the exact `torch==2.11.0`
build is no longer resolvable, install the latest available `cu128` build instead and
record whatever version this prints — that's fine as long as it's a `cu128` build and
`cuda.is_available()` is `True`.

- [ ] **Step 2: Write the backend adapter**

```python
# tools/audio_emotion_labeling/backends/qwen2audio.py
"""Qwen2-Audio-7B-Instruct backend adapter: load once, generate per clip."""
from __future__ import annotations

import librosa
import torch
from transformers import AutoProcessor, BitsAndBytesConfig, Qwen2AudioForConditionalGeneration

MODEL_ID = "Qwen/Qwen2-Audio-7B-Instruct"
REVISION = "0a095220c30b7b31434169c3086508ef3ea5bf0a"


def load_model():
    processor = AutoProcessor.from_pretrained(MODEL_ID, revision=REVISION)
    try:
        bnb_config = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16)
        model = Qwen2AudioForConditionalGeneration.from_pretrained(
            MODEL_ID, revision=REVISION, quantization_config=bnb_config, device_map="auto")
        quant = "4bit-bnb"
    except Exception as e:  # noqa: BLE001 - bnb kernel support on this GPU is unverified
        print(f"4-bit load failed ({e}); falling back to bf16")
        model = Qwen2AudioForConditionalGeneration.from_pretrained(
            MODEL_ID, revision=REVISION, torch_dtype=torch.bfloat16, device_map="auto")
        quant = "bf16"
    return model, processor, {"model_id": MODEL_ID, "quant": quant,
                               "temperature": 0.0, "max_new_tokens": 192}


def generate(model, processor, wav_path: str, prompt_text: str) -> str:
    audio, _ = librosa.load(wav_path, sr=16000, mono=True)
    conversation = [{"role": "user", "content": [
        {"type": "audio", "audio_url": wav_path},
        {"type": "text", "text": prompt_text},
    ]}]
    chat_prompt = processor.apply_chat_template(conversation, add_generation_prompt=True, tokenize=False)
    inputs = processor(text=chat_prompt, audios=[audio], sampling_rate=16000, return_tensors="pt")
    inputs = {k: v.to(model.device) for k, v in inputs.items()}
    generated = model.generate(**inputs, max_new_tokens=192, do_sample=False)
    generated = generated[:, inputs["input_ids"].shape[1]:]
    return processor.batch_decode(generated, skip_special_tokens=True)[0]
```

```python
# tools/audio_emotion_labeling/backends/__init__.py
```

- [ ] **Step 3: Smoke-load against one real clip**

```bash
.venv-qwen2audio/bin/python3 -c "
from backends.qwen2audio import load_model, generate
model, processor, meta = load_model()
print('loaded:', meta)
text = generate(model, processor,
    '/home/geoff/projects/W40KRogueTraderNeuralSpeechMod/data/voices/wav/Abelard/BNTRS_AreaPeaceful_Abelard_14.wav',
    'Describe in one sentence how the speaker sounds emotionally.')
print('OUTPUT:', text)
"
```

Run from `tools/audio_emotion_labeling/`. Expected: `meta['quant']` prints either
`4bit-bnb` or `bf16` (either is acceptable — this is the exact check the Global
Constraints section requires before any labeling), and `OUTPUT` is a non-empty sentence
that plausibly describes vocal delivery. If it crashes with an OOM or a `bitsandbytes`
CUDA-kernel error even on the bf16 fallback path, stop and report — that's a real
blocker, not something to paper over.

- [ ] **Step 4: Commit**

```bash
git add tools/audio_emotion_labeling/backends/__init__.py tools/audio_emotion_labeling/backends/qwen2audio.py
git commit -m "Add Qwen2-Audio backend adapter for emotion labeling harness"
```

(`.venv-qwen2audio/` is a virtualenv — confirm `.venv-*` is git-ignored before committing;
if not, add `tools/audio_emotion_labeling/.venv-*` to `.gitignore` in this same commit.)

---

### Task 2: Ultravox backend — venv, adapter, smoke-load

**Files:**
- Create: `tools/audio_emotion_labeling/.venv-ultravox/` (venv)
- Create: `tools/audio_emotion_labeling/backends/ultravox.py`

**Interfaces:**
- Produces: same `load_model()` / `generate()` shape as Task 1's `qwen2audio.py`, so
  `label.py` can treat both backends identically.

- [ ] **Step 1: Create the venv and install pinned dependencies**

```bash
cd /home/geoff/projects/W40KRogueTraderNeuralSpeechMod/tools/audio_emotion_labeling
python3 -m venv .venv-ultravox
.venv-ultravox/bin/pip install --upgrade pip
.venv-ultravox/bin/pip install torch==2.11.0 --index-url https://download.pytorch.org/whl/cu128
.venv-ultravox/bin/pip install transformers==4.57.3 accelerate==1.12.0 bitsandbytes librosa soundfile
```

Run: `.venv-ultravox/bin/python3 -c "import torch; print(torch.__version__, torch.cuda.is_available())"`
Expected: same as Task 1 Step 1.

- [ ] **Step 2: Write the backend adapter**

```python
# tools/audio_emotion_labeling/backends/ultravox.py
"""Ultravox (Llama-3.1-8B + Whisper adapter) backend adapter."""
from __future__ import annotations

import librosa
import torch
from transformers import AutoModel, AutoProcessor, BitsAndBytesConfig

MODEL_ID = "fixie-ai/ultravox-v0_5-llama-3_1-8b"
REVISION = "94aa77f70ca548e669ea61f737e159b2fddbb7f7"


def load_model():
    processor = AutoProcessor.from_pretrained(
        MODEL_ID, revision=REVISION, trust_remote_code=True)
    try:
        bnb_config = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16)
        model = AutoModel.from_pretrained(
            MODEL_ID, revision=REVISION, trust_remote_code=True,
            quantization_config=bnb_config, device_map="auto")
        quant = "4bit-bnb"
    except Exception as e:  # noqa: BLE001 - bnb kernel support on this GPU is unverified
        print(f"4-bit load failed ({e}); falling back to bf16")
        model = AutoModel.from_pretrained(
            MODEL_ID, revision=REVISION, trust_remote_code=True,
            torch_dtype=torch.bfloat16, device_map="auto")
        quant = "bf16"
    return model, processor, {"model_id": MODEL_ID, "quant": quant,
                               "temperature": 0.0, "max_new_tokens": 192}


def generate(model, processor, wav_path: str, prompt_text: str) -> str:
    audio, _ = librosa.load(wav_path, sr=16000, mono=True)
    turns = [{"role": "system", "content": "You are an expert at judging vocal emotion."},
             {"role": "user", "content": prompt_text}]
    inputs = processor(audio=audio, sampling_rate=16000, turns=turns, return_tensors="pt")
    inputs = {k: v.to(model.device) if hasattr(v, "to") else v for k, v in inputs.items()}
    generated = model.generate(**inputs, max_new_tokens=192, do_sample=False)
    generated = generated[:, inputs["input_ids"].shape[1]:]
    return processor.tokenizer.batch_decode(generated, skip_special_tokens=True)[0]
```

- [ ] **Step 3: Smoke-load against one real clip**

```bash
.venv-ultravox/bin/python3 -c "
from backends.ultravox import load_model, generate
model, processor, meta = load_model()
print('loaded:', meta)
text = generate(model, processor,
    '/home/geoff/projects/W40KRogueTraderNeuralSpeechMod/data/voices/wav/Abelard/BNTRS_AreaPeaceful_Abelard_14.wav',
    'Describe in one sentence how the speaker sounds emotionally.')
print('OUTPUT:', text)
"
```

Run from `tools/audio_emotion_labeling/`. Expected: same shape as Task 1 Step 3. Ultravox
ships its `AutoModel`/`AutoProcessor` glue as remote code
(`ultravox_model.py`/`ultravox_processing.py`/`ultravox_pipeline.py`, already visible in
the HF cache from the background download) — if the processor call signature above
doesn't match what that remote code actually expects, read the cached
`ultravox_processing.py` under `~/.cache/huggingface/hub/models--fixie-ai--ultravox-v0_5-llama-3_1-8b/snapshots/<revision>/` to correct the argument names; the two functions'
external contract (`load_model()` / `generate(model, processor, wav_path, prompt_text)`)
stays the same either way.

- [ ] **Step 4: Commit**

```bash
git add tools/audio_emotion_labeling/backends/ultravox.py
git commit -m "Add Ultravox backend adapter for emotion labeling harness"
```

---

### Task 3: Vocabulary module

**Files:**
- Create: `tools/audio_emotion_labeling/vocab.py`
- Test: `tools/audio_emotion_labeling/tests/test_vocab.py`

**Interfaces:**
- Produces: `load_vocab(custom_emotions_path: Path) -> dict` returning
  `{"tiers": [{"tier": str, "words": list[str]}], "word_to_tier": dict[str, str],
  "all_words": list[str]}`.
- Produces: `ENERGY_LADDER: list[str]` — the 5 tier names in energy order, used by
  Task 6's `scoring.py` for tier-adjacency.

- [ ] **Step 1: Write the failing test**

```python
# tools/audio_emotion_labeling/tests/test_vocab.py
import json
from pathlib import Path

from vocab import load_vocab, ENERGY_LADDER


def test_load_vocab_merges_original_and_custom_tiers(tmp_path):
    custom_path = tmp_path / "custom_emotions.json"
    custom_path.write_text(json.dumps({"tiers": [
        {"tier": "Low energy", "words": ["somber", "resigned"]},
        {"tier": "High energy", "words": ["ecstatic"]},
    ]}))

    vocab = load_vocab(custom_path)

    assert vocab["tiers"][0]["tier"] == "Original"
    assert "angry" in vocab["tiers"][0]["words"]
    assert vocab["word_to_tier"]["angry"] == "Original"
    assert vocab["word_to_tier"]["somber"] == "Low energy"
    assert "somber" in vocab["all_words"]
    assert len(vocab["all_words"]) == 12 + 2 + 1


def test_load_vocab_missing_file_returns_original_only(tmp_path):
    vocab = load_vocab(tmp_path / "does_not_exist.json")
    assert vocab["tiers"] == [{"tier": "Original", "words": vocab["tiers"][0]["words"]}]
    assert len(vocab["all_words"]) == 12


def test_energy_ladder_is_five_tiers_in_order():
    assert ENERGY_LADDER == ["Low energy", "Low-mid energy", "Mid energy",
                              "Mid-high energy", "High energy"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd tools/audio_emotion_labeling && python3 -m pytest tests/test_vocab.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'vocab'`

- [ ] **Step 3: Write the implementation**

```python
# tools/audio_emotion_labeling/vocab.py
"""Combined emotion vocabulary: the original 12-emotion enum plus the tiered custom
vocabulary in data/voices/emotion_banks/custom_emotions.json."""
from __future__ import annotations

import json
from pathlib import Path

EMOTION_ORDER = ["angry", "commanding", "fear", "surprised", "pleading", "sad", "whisper",
                  "sarcastic", "dramatic", "happy", "amused", "neutral"]

ENERGY_LADDER = ["Low energy", "Low-mid energy", "Mid energy", "Mid-high energy", "High energy"]


def load_vocab(custom_emotions_path: Path) -> dict:
    tiers = [{"tier": "Original", "words": list(EMOTION_ORDER)}]
    if custom_emotions_path.exists():
        tiers += json.loads(custom_emotions_path.read_text(encoding="utf-8")).get("tiers", [])
    word_to_tier = {w: t["tier"] for t in tiers for w in t["words"]}
    all_words = [w for t in tiers for w in t["words"]]
    return {"tiers": tiers, "word_to_tier": word_to_tier, "all_words": all_words}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd tools/audio_emotion_labeling && python3 -m pytest tests/test_vocab.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add tools/audio_emotion_labeling/vocab.py tools/audio_emotion_labeling/tests/test_vocab.py
git commit -m "Add combined emotion vocabulary loader"
```

---

### Task 4: Prompt builder

**Files:**
- Create: `tools/audio_emotion_labeling/prompt.py`
- Test: `tools/audio_emotion_labeling/tests/test_prompt.py`

**Interfaces:**
- Consumes: `vocab: dict` (Task 3's `load_vocab()` return shape).
- Produces: `build_prompt(vocab: dict, mode: str, transcript: str | None) -> str`.
  `mode` is `"audio"` or `"audio+text"`; `transcript` is required (non-`None`) when
  `mode == "audio+text"`, ignored/must be `None` for `"audio"`.
- Produces: `prompt_hash(vocab: dict, mode: str) -> str` — 12-hex-char sha256 prefix of
  the prompt *template* (transcript replaced with a fixed placeholder), stable across
  clips within the same (vocab, mode).

- [ ] **Step 1: Write the failing test**

```python
# tools/audio_emotion_labeling/tests/test_prompt.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd tools/audio_emotion_labeling && python3 -m pytest tests/test_prompt.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'prompt'`

- [ ] **Step 3: Write the implementation**

```python
# tools/audio_emotion_labeling/prompt.py
"""Builds the emotion-labeling prompt sent to an audio-input LLM, and a stable hash of
the prompt template (independent of any per-clip transcript) used to key cached output."""
from __future__ import annotations

import hashlib

_TRANSCRIPT_PLACEHOLDER = "{TRANSCRIPT}"

_INSTRUCTIONS = """You are labeling the emotional delivery of a short voiced game line.

Listen to the audio and pick exactly 3 words that best describe how the speaker sounds,
ranked best-fit first, preferably from this vocabulary (grouped by energy level):

{vocab_block}

Respond with ONLY this JSON object, no other text:
{{"labels": [{{"word": "...", "confidence": 0.0}}, {{"word": "...", "confidence": 0.0}}, {{"word": "...", "confidence": 0.0}}], "notes": ""}}

confidence is your certainty in that pick, from 0.0 to 1.0. If none of the 3 vocabulary
words you'd normally pick fit well, use "notes" to propose a better word instead — still
return exactly 3 labels."""


def _vocab_block(vocab: dict) -> str:
    lines = []
    for tier in vocab["tiers"]:
        lines.append(f"{tier['tier']}: {', '.join(tier['words'])}")
    return "\n".join(lines)


def build_prompt(vocab: dict, mode: str, transcript: str | None) -> str:
    if mode not in ("audio", "audio+text"):
        raise ValueError(f"unknown mode: {mode!r}")
    if mode == "audio+text" and transcript is None:
        raise ValueError("audio+text mode requires a transcript")
    text = _INSTRUCTIONS.format(vocab_block=_vocab_block(vocab))
    if mode == "audio+text":
        text += f'\n\nTranscript of the line: "{transcript}"'
    return text


def prompt_hash(vocab: dict, mode: str) -> str:
    transcript = _TRANSCRIPT_PLACEHOLDER if mode == "audio+text" else None
    template = build_prompt(vocab, mode, transcript)
    return hashlib.sha256(template.encode("utf-8")).hexdigest()[:12]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd tools/audio_emotion_labeling && python3 -m pytest tests/test_prompt.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add tools/audio_emotion_labeling/prompt.py tools/audio_emotion_labeling/tests/test_prompt.py
git commit -m "Add emotion-labeling prompt builder and template hash"
```

---

### Task 5: Response parser

**Files:**
- Create: `tools/audio_emotion_labeling/parsing.py`
- Test: `tools/audio_emotion_labeling/tests/test_parsing.py`

**Interfaces:**
- Produces: `parse_model_response(raw_text: str) -> dict | None` returning
  `{"labels": [{"word": str, "confidence": float}, ...], "notes": str}` (labels list may
  have fewer than 3 entries if some were malformed but at least one parsed) or `None` if
  no usable JSON object could be recovered at all.

- [ ] **Step 1: Write the failing test**

```python
# tools/audio_emotion_labeling/tests/test_parsing.py
from parsing import parse_model_response


def test_parses_clean_json():
    raw = '{"labels": [{"word": "rueful", "confidence": 0.8}, {"word": "sad", "confidence": 0.4}, {"word": "grim", "confidence": 0.2}], "notes": ""}'
    result = parse_model_response(raw)
    assert result["labels"][0] == {"word": "rueful", "confidence": 0.8}
    assert len(result["labels"]) == 3
    assert result["notes"] == ""


def test_recovers_json_wrapped_in_prose():
    raw = ('Sure, here is my analysis:\n'
           '{"labels": [{"word": "commanding", "confidence": 0.9}], "notes": "firm"}\n'
           'Let me know if you need anything else!')
    result = parse_model_response(raw)
    assert result["labels"] == [{"word": "commanding", "confidence": 0.9}]
    assert result["notes"] == "firm"


def test_truncated_json_returns_none():
    raw = '{"labels": [{"word": "angry", "confidence": 0.7}, {"word": "stern"'
    assert parse_model_response(raw) is None


def test_missing_labels_key_returns_none():
    raw = '{"notes": "the speaker sounds tired"}'
    assert parse_model_response(raw) is None


def test_drops_malformed_label_entries_but_keeps_valid_ones():
    raw = '{"labels": [{"word": "angry", "confidence": 0.7}, {"word": 123}, "not a dict"], "notes": ""}'
    result = parse_model_response(raw)
    assert result["labels"] == [{"word": "angry", "confidence": 0.7}]


def test_clamps_out_of_range_confidence():
    raw = '{"labels": [{"word": "angry", "confidence": 1.7}], "notes": ""}'
    result = parse_model_response(raw)
    assert result["labels"][0]["confidence"] == 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd tools/audio_emotion_labeling && python3 -m pytest tests/test_parsing.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'parsing'`

- [ ] **Step 3: Write the implementation**

```python
# tools/audio_emotion_labeling/parsing.py
"""Robust extraction of the {"labels": [...], "notes": ...} JSON object a 7B model was
asked to emit, tolerating prose wrapping and dropping individually malformed entries."""
from __future__ import annotations

import json
import re


def _extract_json_object(raw_text: str) -> dict | None:
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def parse_model_response(raw_text: str) -> dict | None:
    obj = _extract_json_object(raw_text)
    if not isinstance(obj, dict) or "labels" not in obj or not isinstance(obj["labels"], list):
        return None

    labels = []
    for item in obj["labels"]:
        if not isinstance(item, dict):
            continue
        word = item.get("word")
        confidence = item.get("confidence")
        if not isinstance(word, str) or not isinstance(confidence, (int, float)):
            continue
        labels.append({"word": word, "confidence": max(0.0, min(1.0, float(confidence)))})
    if not labels:
        return None

    notes = obj.get("notes", "")
    return {"labels": labels, "notes": notes if isinstance(notes, str) else ""}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd tools/audio_emotion_labeling && python3 -m pytest tests/test_parsing.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add tools/audio_emotion_labeling/parsing.py tools/audio_emotion_labeling/tests/test_parsing.py
git commit -m "Add tolerant JSON parser for model label responses"
```

---

### Task 6: Scoring functions

**Files:**
- Create: `tools/audio_emotion_labeling/scoring.py`
- Test: `tools/audio_emotion_labeling/tests/test_scoring.py`

**Interfaces:**
- Consumes: `word_to_tier: dict[str, str]` and `ENERGY_LADDER` (Task 3's `vocab.py`).
- Produces: `tier_similarity(word_a: str, word_b: str, word_to_tier: dict) -> float`,
  `recall_at_k(human_word: str, model_words: list[str], k: int) -> bool`,
  `best_of_set_similarity(human_word: str, model_words: list[str], word_to_tier: dict) -> float`.

- [ ] **Step 1: Write the failing test**

```python
# tools/audio_emotion_labeling/tests/test_scoring.py
from scoring import tier_similarity, recall_at_k, best_of_set_similarity

WORD_TO_TIER = {
    "rueful": "Low-mid energy", "somber": "Low energy", "grim": "Mid energy",
    "ecstatic": "High energy", "angry": "Original", "commanding": "Original",
}


def test_tier_similarity_exact_word_is_one():
    assert tier_similarity("rueful", "rueful", WORD_TO_TIER) == 1.0


def test_tier_similarity_same_tier_is_point_seven():
    assert tier_similarity("angry", "commanding", WORD_TO_TIER) == 0.7


def test_tier_similarity_adjacent_energy_tier_is_point_four():
    assert tier_similarity("somber", "rueful", WORD_TO_TIER) == 0.4  # Low <-> Low-mid


def test_tier_similarity_distant_energy_tier_is_zero():
    assert tier_similarity("somber", "ecstatic", WORD_TO_TIER) == 0.0  # Low <-> High


def test_tier_similarity_unknown_word_is_zero():
    assert tier_similarity("somber", "made_up_word", WORD_TO_TIER) == 0.0


def test_recall_at_k_hit_within_k():
    assert recall_at_k("rueful", ["angry", "rueful", "grim"], k=2) is True


def test_recall_at_k_miss_outside_k():
    assert recall_at_k("rueful", ["angry", "grim", "rueful"], k=2) is False


def test_best_of_set_similarity_takes_max():
    result = best_of_set_similarity("rueful", ["angry", "somber", "ecstatic"], WORD_TO_TIER)
    assert result == 0.4  # somber is adjacent-tier to rueful; angry/ecstatic score lower


def test_best_of_set_similarity_empty_set_is_zero():
    assert best_of_set_similarity("rueful", [], WORD_TO_TIER) == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd tools/audio_emotion_labeling && python3 -m pytest tests/test_scoring.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scoring'`

- [ ] **Step 3: Write the implementation**

```python
# tools/audio_emotion_labeling/scoring.py
"""Pure scoring functions comparing a model's predicted labels against a human label.
Ground truth here is soft (the human was often unsure between several plausible words),
so similarity is graded via the project's own energy tiers rather than exact match only."""
from __future__ import annotations

from vocab import ENERGY_LADDER


def tier_similarity(word_a: str, word_b: str, word_to_tier: dict[str, str]) -> float:
    if word_a == word_b:
        return 1.0
    tier_a, tier_b = word_to_tier.get(word_a), word_to_tier.get(word_b)
    if tier_a is None or tier_b is None:
        return 0.0
    if tier_a == tier_b:
        return 0.7
    if tier_a in ENERGY_LADDER and tier_b in ENERGY_LADDER:
        if abs(ENERGY_LADDER.index(tier_a) - ENERGY_LADDER.index(tier_b)) == 1:
            return 0.4
    return 0.0


def recall_at_k(human_word: str, model_words: list[str], k: int) -> bool:
    return human_word in model_words[:k]


def best_of_set_similarity(human_word: str, model_words: list[str], word_to_tier: dict[str, str]) -> float:
    if not model_words:
        return 0.0
    return max(tier_similarity(human_word, w, word_to_tier) for w in model_words)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd tools/audio_emotion_labeling && python3 -m pytest tests/test_scoring.py -v`
Expected: PASS (9 tests)

- [ ] **Step 5: Commit**

```bash
git add tools/audio_emotion_labeling/scoring.py tools/audio_emotion_labeling/tests/test_scoring.py
git commit -m "Add tier-based scoring functions for pilot accuracy report"
```

---

### Task 7: Resumable batch runner (`label.py`)

**Files:**
- Create: `tools/audio_emotion_labeling/label.py`
- Test: `tools/audio_emotion_labeling/tests/test_label_resume.py`

**Interfaces:**
- Consumes: `build_prompt`/`prompt_hash` (Task 4), `parse_model_response` (Task 5),
  `load_vocab` (Task 3), and (for the CLI only) `backends.qwen2audio` / `backends.ultravox`
  (Tasks 1-2), each exposing `load_model()` and `generate(model, processor, wav_path, prompt_text)`.
- Produces: `iter_labels(catalog, existing, backend_name, mode, prompt_hash_value,
  generate_fn, vocab, backend_meta, speaker_filter=None) -> Iterator[tuple[str, dict]]`
  — pure, no file I/O, used directly by tests and by the CLI wrapper below.
  `generate_fn(wav_path: str, prompt_text: str) -> str`.
- Produces: a CLI (`label.py --backend {qwen2audio,ultravox} --mode {audio,audio+text}
  [--pilot] [--limit N]`) that loads/saves `data/voices/emotion_banks/audio_llm_labels.json`
  around `iter_labels()`.

- [ ] **Step 1: Write the failing test**

```python
# tools/audio_emotion_labeling/tests/test_label_resume.py
from pathlib import Path

from label import iter_labels
from prompt import prompt_hash
from vocab import load_vocab

VOCAB = load_vocab(Path("/nonexistent"))  # Original tier only, deterministic
CATALOG = {
    "EVT_1": {"speaker": "Abelard", "wav": "wav/Abelard/EVT_1.wav",
              "texts": [{"text": "Hold the line!"}]},
    "EVT_2": {"speaker": "Abelard", "wav": "wav/Abelard/EVT_2.wav",
              "texts": [{"text": "As you wish."}]},
    "EVT_3": {"speaker": "Argenta", "wav": "wav/Argenta/EVT_3.wav",
              "texts": [{"text": "For the Emperor!"}]},
}
BACKEND_META = {"model_id": "fake/model", "quant": "bf16", "temperature": 0.0, "max_new_tokens": 192}


def fake_generate(wav_path: str, prompt_text: str) -> str:
    return '{"labels": [{"word": "angry", "confidence": 0.9}], "notes": ""}'


def test_yields_one_entry_per_unlabeled_event():
    ph = prompt_hash(VOCAB, "audio")
    results = list(iter_labels(CATALOG, {}, "qwen2audio", "audio", ph,
                                fake_generate, VOCAB, BACKEND_META))
    assert {event for event, _ in results} == {"EVT_1", "EVT_2", "EVT_3"}


def test_skips_events_already_labeled_at_same_key():
    ph = prompt_hash(VOCAB, "audio")
    existing = {"EVT_1": {"qwen2audio": {"audio": {ph: {"labels": []}}}}}
    results = list(iter_labels(CATALOG, existing, "qwen2audio", "audio", ph,
                                fake_generate, VOCAB, BACKEND_META))
    assert {event for event, _ in results} == {"EVT_2", "EVT_3"}


def test_different_prompt_hash_is_not_skipped():
    old_ph = "aaaaaaaaaaaa"
    new_ph = prompt_hash(VOCAB, "audio")
    existing = {"EVT_1": {"qwen2audio": {"audio": {old_ph: {"labels": []}}}}}
    results = list(iter_labels(CATALOG, existing, "qwen2audio", "audio", new_ph,
                                fake_generate, VOCAB, BACKEND_META))
    assert "EVT_1" in {event for event, _ in results}


def test_speaker_filter_restricts_to_one_speaker():
    ph = prompt_hash(VOCAB, "audio")
    results = list(iter_labels(CATALOG, {}, "qwen2audio", "audio", ph,
                                fake_generate, VOCAB, BACKEND_META, speaker_filter="Abelard"))
    assert {event for event, _ in results} == {"EVT_1", "EVT_2"}


def test_entry_shape_includes_parsed_labels_meta_and_latency():
    ph = prompt_hash(VOCAB, "audio")
    _, entry = next(iter_labels(CATALOG, {}, "qwen2audio", "audio", ph,
                                 fake_generate, VOCAB, BACKEND_META, speaker_filter="Abelard"))
    assert entry["labels"] == [{"word": "angry", "confidence": 0.9}]
    assert entry["parse_ok"] is True
    assert entry["model_id"] == "fake/model"
    assert entry["quant"] == "bf16"
    assert entry["temperature"] == 0.0
    assert entry["max_new_tokens"] == 192
    assert "latency_s" in entry and entry["latency_s"] >= 0
    assert "timestamp" in entry


def test_unparseable_response_still_yields_entry_with_parse_ok_false():
    ph = prompt_hash(VOCAB, "audio")
    _, entry = next(iter_labels(CATALOG, {}, "qwen2audio", "audio", ph,
                                 lambda wav, p: "not json at all",
                                 VOCAB, BACKEND_META, speaker_filter="Abelard"))
    assert entry["parse_ok"] is False
    assert entry["labels"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd tools/audio_emotion_labeling && python3 -m pytest tests/test_label_resume.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'label'`

- [ ] **Step 3: Write the implementation**

```python
# tools/audio_emotion_labeling/label.py
"""Resumable batch runner: labels catalog clips with a chosen audio-LLM backend.

Usage (run from inside the matching venv):
  .venv-qwen2audio/bin/python label.py --backend qwen2audio --mode audio --pilot
  .venv-ultravox/bin/python label.py --backend ultravox --mode audio+text --pilot --limit 5

Writes data/voices/emotion_banks/audio_llm_labels.json, keyed
event -> backend -> mode -> prompt_hash -> entry. Safe to interrupt and re-run: already
labeled (event, backend, mode, prompt_hash) combinations are skipped.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterator

from parsing import parse_model_response
from prompt import build_prompt

ROOT = Path(__file__).resolve().parent.parent.parent
VOICES = ROOT / "data/voices"
OUT_PATH = VOICES / "emotion_banks/audio_llm_labels.json"


def iter_labels(catalog: dict, existing: dict, backend_name: str, mode: str,
                 prompt_hash_value: str, generate_fn: Callable[[str, str], str],
                 vocab: dict, backend_meta: dict,
                 speaker_filter: str | None = None) -> Iterator[tuple[str, dict]]:
    for event, clip in catalog.items():
        if speaker_filter and clip.get("speaker") != speaker_filter:
            continue
        already = (existing.get(event, {}).get(backend_name, {})
                   .get(mode, {}).get(prompt_hash_value))
        if already:
            continue

        transcript = clip["texts"][0]["text"] if mode == "audio+text" else None
        prompt_text = build_prompt(vocab, mode, transcript)

        t0 = time.monotonic()
        raw = generate_fn(clip["wav"], prompt_text)
        latency = time.monotonic() - t0

        parsed = parse_model_response(raw)
        entry = {
            "labels": parsed["labels"] if parsed else [],
            "notes": parsed["notes"] if parsed else "",
            "parse_ok": parsed is not None,
            "raw_response": raw,
            **backend_meta,
            "latency_s": round(latency, 3),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        yield event, entry


def _atomic_write(path: Path, data: dict) -> None:
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", required=True, choices=["qwen2audio", "ultravox"])
    ap.add_argument("--mode", required=True, choices=["audio", "audio+text"])
    ap.add_argument("--pilot", action="store_true", help="restrict to all Abelard catalog clips")
    ap.add_argument("--limit", type=int, default=0, help="cap number of clips processed (debugging)")
    args = ap.parse_args()

    from vocab import load_vocab
    vocab = load_vocab(VOICES / "emotion_banks/custom_emotions.json")
    from prompt import prompt_hash
    ph = prompt_hash(vocab, args.mode)

    if args.backend == "qwen2audio":
        from backends.qwen2audio import generate as backend_generate
        from backends.qwen2audio import load_model
    else:
        from backends.ultravox import generate as backend_generate
        from backends.ultravox import load_model

    model, processor, backend_meta = load_model()
    print(f"loaded {args.backend}: {backend_meta}")

    def generate_fn(wav_path: str, prompt_text: str) -> str:
        return backend_generate(model, processor, str(VOICES / wav_path), prompt_text)

    catalog = json.loads((VOICES / "catalog.json").read_text(encoding="utf-8"))
    existing = json.loads(OUT_PATH.read_text(encoding="utf-8")) if OUT_PATH.exists() else {}
    speaker_filter = "Abelard" if args.pilot else None

    count = 0
    for event, entry in iter_labels(catalog, existing, args.backend, args.mode, ph,
                                     generate_fn, vocab, backend_meta, speaker_filter):
        existing.setdefault(event, {}).setdefault(args.backend, {}).setdefault(args.mode, {})[ph] = entry
        _atomic_write(OUT_PATH, existing)
        count += 1
        print(f"[{count}] {event}: {entry['labels']} (parse_ok={entry['parse_ok']}, "
              f"{entry['latency_s']}s)")
        if args.limit and count >= args.limit:
            break

    print(f"done: {count} clips labeled")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd tools/audio_emotion_labeling && python3 -m pytest tests/test_label_resume.py -v`
Expected: PASS (6 tests) — this runs under plain `python3`, no venv/GPU needed, since the
test only exercises `iter_labels()` with a fake `generate_fn`.

- [ ] **Step 5: Real end-to-end smoke test with each backend**

```bash
cd tools/audio_emotion_labeling
.venv-qwen2audio/bin/python label.py --backend qwen2audio --mode audio --pilot --limit 2
.venv-ultravox/bin/python label.py --backend ultravox --mode audio --pilot --limit 2
```

Expected: each prints `loaded ...` with a `quant` value, then 2 lines showing an event
name, a labels list (ideally 3 entries with real vocabulary words), `parse_ok=True`, and
a latency in seconds. Inspect `data/voices/emotion_banks/audio_llm_labels.json` afterward
— it should contain exactly those 2 events with the expected key nesting. Re-run the same
command once more and confirm the log shows `done: 0 clips labeled` (everything already
labeled at that prompt hash) before proceeding to Task 9's full pilot.

- [ ] **Step 6: Commit**

```bash
git add tools/audio_emotion_labeling/label.py tools/audio_emotion_labeling/tests/test_label_resume.py
git add data/voices/emotion_banks/audio_llm_labels.json
git commit -m "Add resumable batch labeling runner"
```

---

### Task 8: Pilot accuracy report (`score_pilot.py`)

**Files:**
- Create: `tools/audio_emotion_labeling/score_pilot.py`
- Test: `tools/audio_emotion_labeling/tests/test_score_pilot.py`

**Interfaces:**
- Consumes: `tier_similarity`, `recall_at_k`, `best_of_set_similarity` (Task 6).
- Produces: `build_report(ground_truth: dict[str, str], labels: dict, word_to_tier: dict,
  backend: str, mode: str, prompt_hash_value: str, event_context: dict | None = None) ->
  dict` — a pure function (no file I/O) so it's independently testable; `labels` is the
  full `audio_llm_labels.json` structure. `event_context`, when given, is
  `{event: {"transcript": str, "text_llm_emotion": str | None}}` — attached to each
  disagreement entry so a human reviewing the report doesn't have to cross-reference
  `catalog.json`/`annotations.enGB.json` by hand.
- Produces: `duplicate_base_lines(ground_truth: dict[str, str]) -> dict[str, list[str]]`
  — base line name -> list of its Wwise state-variant sibling event names, for any base
  line with more than one ground-truth event (see spec: 11 such pairs in the Abelard set).
- Produces: a CLI that loads the real files, calls `build_report` per (backend, mode,
  prompt_hash) combination present in the data, and writes
  `data/voices/emotion_banks/pilot_report.md`.

- [ ] **Step 1: Write the failing test**

```python
# tools/audio_emotion_labeling/tests/test_score_pilot.py
from score_pilot import build_report, duplicate_base_lines

WORD_TO_TIER = {"angry": "Original", "commanding": "Original", "rueful": "Low-mid energy",
                 "somber": "Low energy"}

GROUND_TRUTH = {"EVT_1": "rueful", "EVT_2": "commanding"}

LABELS = {
    "EVT_1": {"qwen2audio": {"audio": {"ph1": {
        "labels": [{"word": "somber", "confidence": 0.8}, {"word": "rueful", "confidence": 0.3}],
        "notes": "", "parse_ok": True}}}},
    "EVT_2": {"qwen2audio": {"audio": {"ph1": {
        "labels": [{"word": "angry", "confidence": 0.9}],
        "notes": "", "parse_ok": True}}}},
}


def test_report_computes_top1_and_recall():
    report = build_report(GROUND_TRUTH, LABELS, WORD_TO_TIER, "qwen2audio", "audio", "ph1")
    assert report["n_scored"] == 2
    assert report["top1_exact"] == 0.0  # neither top-1 pick was the exact human word
    assert report["recall_at_2"] == 0.5  # EVT_1's rueful is recall@2, EVT_2's commanding never appears


def test_report_computes_best_of_set_similarity_mean():
    report = build_report(GROUND_TRUTH, LABELS, WORD_TO_TIER, "qwen2audio", "audio", "ph1")
    # EVT_1: max(sim(rueful,somber)=0.4, sim(rueful,rueful)=1.0) = 1.0
    # EVT_2: max(sim(commanding,angry)=0.7) = 0.7
    assert report["graded_similarity_mean"] == (1.0 + 0.7) / 2


def test_report_disagreement_list_only_has_top1_mismatches():
    report = build_report(GROUND_TRUTH, LABELS, WORD_TO_TIER, "qwen2audio", "audio", "ph1")
    assert {d["event"] for d in report["disagreements"]} == {"EVT_1", "EVT_2"}


def test_report_skips_events_with_no_ground_truth():
    labels = dict(LABELS)
    labels["EVT_3"] = {"qwen2audio": {"audio": {"ph1": {
        "labels": [{"word": "angry", "confidence": 0.5}], "notes": "", "parse_ok": True}}}}
    report = build_report(GROUND_TRUTH, labels, WORD_TO_TIER, "qwen2audio", "audio", "ph1")
    assert report["n_scored"] == 2


def test_report_disagreements_carry_event_context_when_given():
    event_context = {
        "EVT_1": {"transcript": "Dreaming of feasting...", "text_llm_emotion": "sad"},
        "EVT_2": {"transcript": "Typical.", "text_llm_emotion": None},
    }
    report = build_report(GROUND_TRUTH, LABELS, WORD_TO_TIER, "qwen2audio", "audio", "ph1",
                           event_context=event_context)
    by_event = {d["event"]: d for d in report["disagreements"]}
    assert by_event["EVT_1"]["transcript"] == "Dreaming of feasting..."
    assert by_event["EVT_1"]["text_llm_emotion"] == "sad"
    assert by_event["EVT_2"]["text_llm_emotion"] is None


def test_report_disagreements_omit_context_fields_when_not_given():
    report = build_report(GROUND_TRUTH, LABELS, WORD_TO_TIER, "qwen2audio", "audio", "ph1")
    assert "transcript" not in report["disagreements"][0]


def test_duplicate_base_lines_groups_state_variant_siblings():
    ground_truth = {
        "PRL_Foo_04 [statevar=1]": "sad", "PRL_Foo_04 [statevar=2]": "sad",
        "PRL_Bar_01": "angry",
    }
    dupes = duplicate_base_lines(ground_truth)
    assert dupes == {"PRL_Foo_04": ["PRL_Foo_04 [statevar=1]", "PRL_Foo_04 [statevar=2]"]}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd tools/audio_emotion_labeling && python3 -m pytest tests/test_score_pilot.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'score_pilot'`

- [ ] **Step 3: Write the implementation**

```python
# tools/audio_emotion_labeling/score_pilot.py
"""Pilot accuracy report: compares audio_llm_labels.json against the hand-labeled Abelard
ground truth in curation.json, per (backend, mode, prompt_hash)."""
from __future__ import annotations

import json
import re
from pathlib import Path

from scoring import best_of_set_similarity, recall_at_k, tier_similarity
from vocab import load_vocab

ROOT = Path(__file__).resolve().parent.parent.parent
VOICES = ROOT / "data/voices"

_VARIANT_SUFFIX = re.compile(r" \[.*\]$")


def build_report(ground_truth: dict[str, str], labels: dict, word_to_tier: dict,
                  backend: str, mode: str, prompt_hash_value: str,
                  event_context: dict | None = None) -> dict:
    n_scored = 0
    top1_hits = 0
    recall_hits = {1: 0, 2: 0, 3: 0}
    similarities = []
    agree_confidences = []
    disagree_confidences = []
    disagreements = []
    notes_used = 0

    for event, human_word in ground_truth.items():
        entry = labels.get(event, {}).get(backend, {}).get(mode, {}).get(prompt_hash_value)
        if entry is None:
            continue
        n_scored += 1
        model_words = [l["word"] for l in entry["labels"]]
        top1 = model_words[0] if model_words else None
        top1_confidence = entry["labels"][0]["confidence"] if entry["labels"] else None

        if top1 == human_word:
            top1_hits += 1
            if top1_confidence is not None:
                agree_confidences.append(top1_confidence)
        else:
            disagreement = {"event": event, "human": human_word, "model": model_words,
                             "notes": entry.get("notes", "")}
            if event_context is not None:
                ctx = event_context.get(event, {})
                disagreement["transcript"] = ctx.get("transcript")
                disagreement["text_llm_emotion"] = ctx.get("text_llm_emotion")
            disagreements.append(disagreement)
            if top1_confidence is not None:
                disagree_confidences.append(top1_confidence)

        for k in (1, 2, 3):
            if recall_at_k(human_word, model_words, k):
                recall_hits[k] += 1

        similarities.append(best_of_set_similarity(human_word, model_words, word_to_tier))
        if entry.get("notes"):
            notes_used += 1

    def _mean(xs: list[float]) -> float | None:
        return sum(xs) / len(xs) if xs else None

    return {
        "backend": backend, "mode": mode, "n_scored": n_scored,
        "top1_exact": top1_hits / n_scored if n_scored else 0.0,
        "recall_at_1": recall_hits[1] / n_scored if n_scored else 0.0,
        "recall_at_2": recall_hits[2] / n_scored if n_scored else 0.0,
        "recall_at_3": recall_hits[3] / n_scored if n_scored else 0.0,
        "graded_similarity_mean": _mean(similarities) or 0.0,
        "mean_confidence_on_agreement": _mean(agree_confidences),
        "mean_confidence_on_disagreement": _mean(disagree_confidences),
        "notes_used_fraction": notes_used / n_scored if n_scored else 0.0,
        "disagreements": disagreements,
    }


def duplicate_base_lines(ground_truth: dict[str, str]) -> dict[str, list[str]]:
    """Base line name -> its Wwise state-variant sibling events, for base lines with more
    than one ground-truth event (see spec: 11 such pairs in the Abelard set)."""
    groups: dict[str, list[str]] = {}
    for event in ground_truth:
        base = _VARIANT_SUFFIX.sub("", event)
        groups.setdefault(base, []).append(event)
    return {base: events for base, events in groups.items() if len(events) > 1}


def _ground_truth() -> dict[str, str]:
    curation = json.loads((VOICES / "emotion_banks/curation.json").read_text(encoding="utf-8"))
    return {event: rec["emotion"] for speaker_clips in curation.values()
            for event, rec in speaker_clips.items() if rec.get("emotion")}


def _event_context() -> dict[str, dict]:
    """event -> {"transcript": str, "text_llm_emotion": str | None}, joining catalog.json's
    transcript to annotations.enGB.json's existing text-based LLM emotion guess via the
    shared localization GUID, at zero extra inference cost."""
    catalog = json.loads((VOICES / "catalog.json").read_text(encoding="utf-8"))
    annotations_path = ROOT / "data/annotations/annotations.enGB.json"
    annotations = json.loads(annotations_path.read_text(encoding="utf-8")) if annotations_path.exists() else {}
    context = {}
    for event, clip in catalog.items():
        texts = clip.get("texts") or []
        transcript = texts[0]["text"] if texts else None
        guid = texts[0]["guid"] if texts else None
        text_llm_emotion = annotations.get(guid, {}).get("emotion") if guid else None
        context[event] = {"transcript": transcript, "text_llm_emotion": text_llm_emotion}
    return context


def main() -> None:
    ground_truth = _ground_truth()
    labels = json.loads((VOICES / "emotion_banks/audio_llm_labels.json").read_text(encoding="utf-8"))
    vocab = load_vocab(VOICES / "emotion_banks/custom_emotions.json")
    event_context = _event_context()
    dupes = duplicate_base_lines(ground_truth)

    combos = {(b, m, ph) for evt in labels.values() for b, modes in evt.items()
              for m, phs in modes.items() for ph in phs}

    lines = ["# Pilot accuracy report\n",
             f"Duplicate base-line siblings among ground truth ({len(dupes)} base lines): "
             f"{dupes}\n"]
    for backend, mode, ph in sorted(combos):
        report = build_report(ground_truth, labels, vocab["word_to_tier"], backend, mode, ph,
                               event_context=event_context)
        lines.append(f"## {backend} / {mode} (prompt_hash={ph})\n")
        for key in ("n_scored", "top1_exact", "recall_at_1", "recall_at_2", "recall_at_3",
                    "graded_similarity_mean", "mean_confidence_on_agreement",
                    "mean_confidence_on_disagreement", "notes_used_fraction"):
            lines.append(f"- {key}: {report[key]}")
        lines.append(f"\n### Disagreements ({len(report['disagreements'])})\n")
        for d in report["disagreements"]:
            lines.append(f"- `{d['event']}`: human=`{d['human']}` model={d['model']} "
                          f"text_llm=`{d.get('text_llm_emotion')}` notes={d['notes']!r}\n"
                          f"  transcript: {d.get('transcript')!r}")
        lines.append("")

    out_path = VOICES / "emotion_banks/pilot_report.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd tools/audio_emotion_labeling && python3 -m pytest tests/test_score_pilot.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add tools/audio_emotion_labeling/score_pilot.py tools/audio_emotion_labeling/tests/test_score_pilot.py
git commit -m "Add pilot accuracy report scoring Abelard ground truth"
```

---

### Task 9: Run the full Abelard pilot and pick a backend

This is an operational task, not a coding task — it runs the software built in Tasks 1-8.

**Files:** none created; produces `data/voices/emotion_banks/audio_llm_labels.json` (full)
and `data/voices/emotion_banks/pilot_report.md`.

- [ ] **Step 1: Confirm Solasta 2 is closed**

Run: `nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv`
Expected: no `Brimstone-Win64-Shipping.exe` row (or any other large GPU consumer).

- [ ] **Step 2: Run all 4 combinations across all 325 Abelard clips**

```bash
cd tools/audio_emotion_labeling
.venv-qwen2audio/bin/python label.py --backend qwen2audio --mode audio --pilot
.venv-qwen2audio/bin/python label.py --backend qwen2audio --mode audio+text --pilot
.venv-ultravox/bin/python label.py --backend ultravox --mode audio --pilot
.venv-ultravox/bin/python label.py --backend ultravox --mode audio+text --pilot
```

Note the wall-clock time of each run (e.g. prefix each with `time`) — this is the actual
per-clip latency data the spec's throughput projection depends on. Each run is
independently resumable if interrupted; re-running any of these four commands skips
whatever it already finished.

- [ ] **Step 3: Generate the report**

```bash
python3 score_pilot.py
cat ../../data/voices/emotion_banks/pilot_report.md
```

- [ ] **Step 4: Review and decide**

Read the report's `top1_exact`, `recall_at_1/2/3`, `graded_similarity_mean`, and the two
confidence-calibration numbers for all 4 backend/mode combinations. Read through the
`disagreements` list for the winning candidates — per the spec, a model can legitimately
be "right where the human was unsure," so don't mechanically penalize every disagreement.
Using the recorded wall-clock times from Step 2, compute the full-corpus (5,188-clip)
projection for the winning backend in both modes; if both modes fit comfortably inside an
overnight window, keep both, otherwise commit to the single winning mode per the spec's
default plan.

Record the decision (winning backend + mode, and why) as the first paragraph of
`data/voices/emotion_banks/pilot_report.md` by hand before moving on — this becomes the
input to Task 10 and to the eventual full-corpus run.

- [ ] **Step 5: Commit**

```bash
git add data/voices/emotion_banks/audio_llm_labels.json data/voices/emotion_banks/pilot_report.md
git commit -m "Run Abelard pilot across both backends and modes, pick winner"
```

---

### Task 10: Single-speaker generalization guard

**Files:** none created; extends `data/voices/emotion_banks/audio_llm_labels.json`.

- [ ] **Step 1: Label ~20 unlabeled clips each from 2-3 other speakers**

Using the winning backend/mode from Task 9 (example assumes `qwen2audio`/`audio`):

```bash
cd tools/audio_emotion_labeling
.venv-qwen2audio/bin/python3 -c "
import json
cat = json.load(open('../../data/voices/catalog.json'))
for speaker in ('Argenta', 'Cassia', 'Idira'):
    events = [e for e,c in cat.items() if c.get('speaker')==speaker][:20]
    print(speaker, len(events))
"
```

Then run `label.py` filtered to each of those speakers. `label.py` doesn't currently
expose a `--speaker` flag (only `--pilot` for Abelard) — add one:

```python
# tools/audio_emotion_labeling/label.py — in main(), replace:
    speaker_filter = "Abelard" if args.pilot else None
# with:
    speaker_filter = "Abelard" if args.pilot else args.speaker
```

```python
# and add to the argparse setup:
    ap.add_argument("--speaker", default=None, help="restrict to one speaker's catalog clips")
```

```bash
.venv-qwen2audio/bin/python label.py --backend qwen2audio --mode audio --speaker Argenta --limit 20
.venv-qwen2audio/bin/python label.py --backend qwen2audio --mode audio --speaker Cassia --limit 20
.venv-qwen2audio/bin/python label.py --backend qwen2audio --mode audio --speaker Idira --limit 20
```

- [ ] **Step 2: Read the label distribution by hand**

```bash
python3 -c "
import json, collections
labels = json.load(open('../../data/voices/emotion_banks/audio_llm_labels.json'))
from prompt import prompt_hash
from vocab import load_vocab
vocab = load_vocab(__import__('pathlib').Path('../../data/voices/emotion_banks/custom_emotions.json'))
ph = prompt_hash(vocab, 'audio')
for speaker in ('Argenta', 'Cassia', 'Idira'):
    cat = json.load(open('../../data/voices/catalog.json'))
    events = [e for e,c in cat.items() if c.get('speaker')==speaker]
    top1s = [labels[e]['qwen2audio']['audio'][ph]['labels'][0]['word']
             for e in events if e in labels and labels[e].get('qwen2audio',{}).get('audio',{}).get(ph,{}).get('labels')]
    print(speaker, collections.Counter(top1s))
"
```

Expected: each speaker's top-1 label distribution shows meaningfully different words
across speakers and reasonable variety within a speaker's own 20 clips. A red flag is
one word dominating almost every clip for a speaker whose lines are known to vary in
register (e.g. Argenta being uniformly labeled "neutral" would indicate mode collapse and
mean the winning backend needs re-evaluation before the full overnight run).

- [ ] **Step 3: Commit**

```bash
git add tools/audio_emotion_labeling/label.py data/voices/emotion_banks/audio_llm_labels.json
git commit -m "Add speaker filter to labeling CLI, spot-check generalization beyond Abelard"
```

At this point the harness is validated and ready for the full 5,188-clip overnight run
using the winning backend/mode — that run itself, and wiring the resulting labels into
`curate.html`/`serve.py`, are the explicit follow-ups noted as out of scope in the spec.
