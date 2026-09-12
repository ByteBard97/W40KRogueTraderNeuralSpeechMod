# Audio-LLM emotion labeling for the reference-clip catalog

## Problem

`tools/emotion_review/curate.html` is the human-in-the-loop tool for assigning an
emotion-vocabulary label (and an accept/reject usability decision) to each clip in
`data/voices/catalog.json` (5,188 voiced reference clips extracted from the game). Only
Abelard (88 clips, 79 with a non-null `emotion`) has been hand-labeled so far — listening
to and judging every clip by ear does not scale to the full catalog.

The existing automated signal, `tools/score_catalog_emotions.py` (emotion2vec+), only
recognizes 8 coarse SER classes (angry/disgusted/fearful/happy/neutral/sad/surprised/
unknown) and cannot address the project's real vocabulary: the original 12-emotion enum
plus ~70 tiered words in `data/voices/emotion_banks/custom_emotions.json` (e.g. "rueful",
"commanding", "sardonic", "hollow").

Goal: use a local, audio-input LLM to produce richer per-clip emotion labels across the
real vocabulary, validate its accuracy against the existing hand-labeled Abelard clips,
then run it overnight across the full 5,188-clip catalog.

## Scope

**In scope:** picking a model backend via a small accuracy pilot, and a harness that can
label the full catalog with the winning backend.

**Pilot scope note:** the pilot runs all 325 Abelard catalog clips (not just the 79 with
existing human labels) — the 79 give accuracy metrics, the remaining ~246 give realistic
throughput/latency data at meaningful volume and are a useful by-product (a fully labeled
Abelard). Still one speaker; see the single-speaker limitation under Pilot run.

**Out of scope (explicit follow-up, not blocked on by this work):** wiring the resulting
labels into `curate.html`/`serve.py` as a visible signal column, and any adjudication UI
for full-corpus disagreements. The pilot's comparison report stands alone for model
selection; UI integration is a separate bounded task once a backend is chosen.

**Also out of scope:** labeling `data/annotations/annotations.enGB.json` (the 45,114
unvoiced lines) — those already have text-based LLM emotion annotations; this work is
audio-only labeling of the voiced reference-clip catalog.

## Ground truth

`data/voices/emotion_banks/curation.json` → Abelard: 88 entries, 79 with non-null
`emotion`. `decision` (accept/reject, reference-clip usability) and `emotion` (register)
are independent axes — score against `emotion` only, regardless of `decision`. All 82
distinct words appearing across the 12-entry `EMOTION_ORDER` enum and every tier in
`custom_emotions.json` already cover every word actually used in `curation.json` — no
orphan vocabulary to reconcile.

Of the 79 ground-truth events, 68 are distinct base lines and 11 base lines have exactly
one extra Wwise state-variant sibling (`EventName [statevar=value]`, 22 events total
belong to these 11 pairs) — the other 57 events are singletons. Score per-event (each is
a distinct audio recording that still needs its own label), but flag the 11 sibling pairs
in the report for interpretability.

All 79 events are in scope for ground truth regardless of `decision` (only 2 of 88
Abelard clips are `reject`, and `decision` there means reference-clip usability —
length/noise/suitability for TTS conditioning — not audio corruption; it says nothing
about whether the *emotion* label a human already assigned is wrong).

## Model candidates and ranking

| Model | Verdict |
|---|---|
| **Ultravox** (`fixie-ai/ultravox-v0_5-llama-3_1-8b`) | Pilot. Llama-3.1-8B backbone gives strong instruction-following for structured JSON + closed-vocabulary picks. `AutoModel(..., trust_remote_code=True)` or `transformers.pipeline`. `trust_remote_code` executes model-hub code — pin an exact `revision=` commit hash rather than floating on `main`. |
| **Qwen2-Audio-7B-Instruct** (`Qwen/Qwen2-Audio-7B-Instruct`) | Pilot. `Qwen2AudioForConditionalGeneration` + `AutoProcessor`, mature audio understanding, already-installed `transformers` 4.57.3 (in `tools/tts_bakeoff/.venv-qwen`) supports it. |
| Qwen2.5-Omni-7B (4-bit) | Skip. Thinker+talker architecture adds setup/quant risk for no clear gain when only text output is needed. |
| SALMONN | Skip. 13B, not in mainstream `transformers`, weaker (Vicuna-based) instruction-following, worst fit for closed-vocabulary + JSON output. |

Both pilot candidates quantize to 4-bit via `bitsandbytes` (already installed), but
`bitsandbytes` 4-bit kernels on Blackwell (sm_120, this machine's torch 2.11.0+cu128) are
unverified — no confirmation bnb's CUDA kernels have been validated on this architecture.
**First implementation step, before any labeling**: smoke-load each model at 4-bit and
generate on one clip. If bnb 4-bit fails or misbehaves on sm_120, fall back to bf16 with
`device_map="auto"` (an 8B model at bf16 is ~16GB, tight but plausible with the 4-bit
KV-cache/activations headroom freed by closing Solasta 2) or CPU-offload the fraction that
doesn't fit — not blocked either way.

## Architecture

New directory `tools/audio_emotion_labeling/`, following the existing
`tools/tts_bakeoff/` convention of one venv per backend (incompatible dependency stacks):

- `.venv-qwen2audio/` — cloned from `tools/tts_bakeoff/.venv-qwen`'s torch 2.11.0+cu128
  baseline (already proven working on this machine's RTX 5080/Blackwell), plus
  `bitsandbytes` for 4-bit loading.
- `.venv-ultravox/` — separate venv, `transformers` + `trust_remote_code`, same torch
  baseline, `bitsandbytes` for 4-bit.
- `label.py` — backend-pluggable, resumable batch runner. Same code path for the pilot
  subset and the eventual full-catalog overnight run.
- `score_pilot.py` — the accuracy report described below.

No per-model subdirectories or plugin framework beyond the two venvs and one adapter
interface (`load_model(backend) -> generate(wav_path, prompt) -> raw_text`) in `label.py`.

## Prompt and label format

System prompt lists all 82 vocabulary words grouped by their existing energy tiers
(`custom_emotions.json`), instructs the model to return JSON:

```json
{"labels": [{"word": "rueful", "confidence": 0.8}, {"word": "regretful", "confidence": 0.5}],
 "notes": ""}
```

Exactly 3 ranked picks required (not "1-3") so Recall@k is comparable across backends —
a backend that returns fewer labels must not get an easier recall score than one that
returns more. `notes` is an optional free-text field the model can use to propose a
better word if nothing in the list fits well — mirroring how the vocabulary is already
extended by hand via `serve.py`'s `/add_emotion`. The pilot report tallies how often
`notes` is used and lists the most common proposed words; it does **not** auto-add
anything to `custom_emotions.json` — a proposal rate high enough to matter (e.g. >20% of
clips) is itself a finding about a vocabulary gap, for a human to act on.

Two prompt modes:
- `audio` — audio only, a blind listening pass comparable to a human doing `curate.html`
  by ear, and an independent check against the existing text-based LLM annotation.
- `audio+text` — audio plus the clip's transcript (already present in `catalog.json`'s
  `texts[].text`, no extra join needed).

Generation is greedy/deterministic (`temperature=0` or equivalent, fixed `max_new_tokens`)
so pilot numbers are reproducible and a re-run doesn't disagree with itself; both are
recorded alongside `model_id`/`quant`/`prompt_hash`.

**Audio preprocessing contract**: source WAVs are 48kHz mono 16-bit (confirmed by
sampling the catalog). Both Ultravox and Qwen2-Audio expect 16kHz mono input —
`label.py` resamples explicitly (e.g. via `librosa.load(path, sr=16000, mono=True)`)
rather than relying on either model's loader to do it silently.

## Data flow

```
label.py --backend {qwen2audio,ultravox} --mode {audio,audio+text} [--pilot]
```

`--pilot` restricts the run to all 325 Abelard catalog clips (accuracy is scored on the
79 with ground truth; see Scope). Output:
`data/voices/emotion_banks/audio_llm_labels.json`, keyed
`event -> backend -> mode -> prompt_hash -> {labels, raw_response, model_id, quant,
temperature, max_new_tokens, timestamp}` — `prompt_hash` is part of the key path, not just
a stored field, so a prompt edit adds a new entry instead of silently overwriting the
previous generation at the same `event/backend/mode`. Resumable: skip any
`(event, backend, mode, prompt_hash)` already present, same pattern as
`score_catalog_emotions.py`. Both the parsed labels and the raw model output are stored
under that key — so a malformed-JSON response can be re-parsed offline without re-running
inference.

## Scoring (`score_pilot.py`)

Several numbers per backend/mode, not one — the ground truth itself is soft (many Abelard
clips had several plausible labels, or none that fit well):

1. **Top-1 exact match** against the human label.
2. **Recall@1/@2/@3** — human label appears within the model's first *k* ranked picks,
   reported separately for k=1,2,3 (every backend returns exactly 3 ranked labels — see
   Prompt format — so this is a fair comparison rather than rewarding a backend for
   simply returning more guesses than another).
3. **Graded similarity**, using the tier structure already built in
   `custom_emotions.json` rather than raw word-embedding cosine (bare adjectives like
   "dry" or "grim" embed poorly in isolation as vectors, whereas the tiers are the
   project's own human-authored model of emotional-energy distance — a better prior than
   a generic embedding here): same word = 1.0, same tier = 0.7, adjacent tier = 0.4,
   otherwise 0. Computed **best-of-set**: the max score over the model's 3 returned
   labels against the human label, not top-1 only.
4. **Confidence calibration** — mean reported `confidence` on clips where top-1 agrees
   with the human label vs. clips where it disagrees. If confidence doesn't separate the
   two groups, it isn't usable as an auto-accept gate later — a real finding either way,
   directly answering whether model confidence can drive that gate.
5. **Disagreement list** — every event where top-1 differs from the human label, printed
   with the transcript and (where the GUID matches) the existing text-only LLM emotion
   guess from `annotations.enGB.json` at zero extra inference cost. This list is for
   manual eyeballing, not an automated metric — it is where a model can be "right where
   the human was unsure," which a pure agreement rate would penalize.
6. **`notes` usage** — how often the model used the free-text escape hatch instead of the
   vocabulary, and the most common proposed words (see Prompt format above).

## Pilot run

325 Abelard clips × 2 backends × 2 modes = 1,300 generate calls (accuracy scored on the
79 with ground truth, the rest for volume/throughput). Per-clip latency is recorded during
the pilot (not yet measured) to project full-corpus (5,188-clip) wall-clock before
deciding whether the overnight run uses both modes or just the pilot's winning mode:
back-of-envelope *estimate pending pilot data*, both modes across the full catalog is
~10,400 calls, which at a guessed 3-6s/clip is 8-17 hours — likely too close to an
overnight budget to run both modes on everything. Default plan: full run uses whichever
single mode wins the pilot, unless the pilot shows both modes fit comfortably.

Run the pilot (and the eventual full run) with Solasta 2 closed — it currently holds 5GB
of the RTX 5080's 16GB, which would otherwise contaminate the pilot's memory-fit and
latency numbers.

**Single-speaker limitation.** All 79 ground-truth labels are Abelard — one voice actor
with a narrow, measured/dutiful register. A backend that wins on Abelard is not
guaranteed to generalize to a very different register (Argenta's zealous high-energy
lines, Cassia's fragile/breathy delivery, Idira's own register). Rather than hand-labeling
another speaker (out of scope here), the winning backend runs once more on ~20 unlabeled
clips each from 2-3 other speakers before committing to the full overnight run, and the
label *distribution* is eyeballed for mode collapse (e.g. every Argenta clip coming back
"dutiful" or every Cassia clip "neutral" would mean the pilot's numbers don't transfer).
State this limitation plainly when reporting pilot results — the accuracy numbers are
Abelard-only.

## Testing

- Pilot run itself is the validation: metrics + disagreement list per backend/mode,
  reviewed by hand before picking a winner.
- Sanity-check `label.py`'s JSON parsing against a few deliberately malformed model
  outputs (truncated JSON, prose wrapping the JSON block) since 7B models will produce
  non-conforming output on some fraction of real clips.
