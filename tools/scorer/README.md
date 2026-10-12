# Automated TTS clip scoring and best-of-N selection

Replaces hand-listening with local metrics. Runs in its own venv (`tools/scorer/.venv-scorer`,
torch 2.11+cu128); model downloads live in `/media/geoff/Elements/hf_cache_scorer` (external
NTFS drive holds files only, venvs stay on the main drive). TTS generation runs separately in
the `roguetts` conda env; the two sides only talk through files.

## Pieces

| File | Env | What it does |
|---|---|---|
| `scorer.py` | scorer | `ClipScorer` (models loaded once) and `Character` (per-character calibration: centroid of real clips, emotion-family probe trained on the character's ear-verified clips). `Character.score(gen, ref, text, target_label)` returns voice, artifact and emotion-family metrics. |
| `bon_generate.py` | roguetts | Resumable best-of-N take generator for a character's unvoiced lines, in rounds (round r = take r for every line). Output `data/bon/<speaker>/manifest.jsonl` + `wav/`. |
| `bon_score.py` | scorer | Scores new takes as they appear (`--watch`), gates, and writes `winners.json`. `--asr-device cpu` keeps Whisper off a GPU shared with generation. |
| `rank_takes.py`, `gen_best_of_n.py`, `review_server.py`, `analyze_answers.py` | mixed | The blind A/B check of the scorer against a listener (port 8906). |
| `probe_*.py` | scorer | Throwaway evidence-gathering scripts. Kept because their numbers are cited below. |

Typical run (two terminals):

    /home/geoff/anaconda3/envs/roguetts/bin/python3 tools/scorer/bon_generate.py --takes 6
    tools/scorer/.venv-scorer/bin/python tools/scorer/bon_score.py --watch --asr-device cpu

Both are resumable; stop and restart freely. Do not run `pkill` and a relaunch in one Bash call.

## Unattended loop

`loop.py` runs generate -> score -> select -> retake for one character, waiting for free VRAM
before each stage (`gpu_guard.py`). Round 0 fills every line to `--base-takes`; later rounds add
takes only to lines with fewer than `--min-pass` passing takes, up to `--max-takes`. It ends by
writing `winners.json`, `review_queue.json` (no passing take, low emotion probability, few or
indistinguishable candidates: the lines worth a human listen) and `export/` (winner wavs plus
`index.json`, see `export_winners.py`). Plain `python3 tools/scorer/loop.py --speaker Abelard`.
Gates, selection and retake planning live in `selection.py` (numpy only). Tests:
`python3 -m pytest tools/scorer/tests`.

## What the evidence says (2026-09-24, Abelard, 228 hand-rated sweep clips)

- **Voice match / artifacts:** ECAPA and WavLM cosine (to the cloning reference and to the
  centroid of all real clips) plus UTMOSv2 each correlate about 0.4 with the user's voice rating.
  Picking the top take per line with the 5-metric composite scored +0.59 rating points above the
  line mean (95% CI +0.36 to +0.83, leave-one-line-out, 19 lines; oracle +0.96).
- **Learned weights** (`probe_learned_weights.py`, ridge, leave-one-line-out): on the 5 voice features they do worse than equal
  weights (+0.38 to +0.48 vs +0.59). Adding wer/trail/lead/rms/speech-rate gives +0.75 at one alpha, but the paired gain over
  equal weights is +0.16 (95% CI -0.07..+0.39, 19 lines, alpha picked from 6 configs), so equal weights stay.
- **Failure tags:** gravelly and whisper occurred almost only at cfg 1.5-2.0, so tag detection is
  confounded with cfg and the counts are too small to trust; rhotic-R (8) and rushed (4) untestable.
- **Emotion:** raw arousal/dominance/valence distances and embedding similarity to the reference
  do not track the emotion ratings (all |rho| < 0.2). A logistic probe on the audEERING embedding,
  trained on the ear-labelled real clips, reaches 46% leave-one-out on 8 families (majority 23.5%,
  shuffled 12-21%) and ranks takes within a line in the user's direction (per-line tau +0.35, 9
  lines only). Qwen2.5-Omni-7B forced-choice got 37-41% but says "stern" for most clips.
- **Not used for ranking yet:** the emotion probe. It only flags `low_emotion_prob` until the
  blind A/B check confirms it agrees with listeners.
- Untested: whether any of this holds for other characters; every step needs that character's
  labelled reference clips.

## Known limits

- `wavlm-base-plus-sv` cosines are compressed (0.93-0.98). The WavLM-large SV checkpoint
  (UniSpeech `wavlm_large_finetune.pth`, CC BY-SA 3.0, vendored loader in `vendor/unispeech/`,
  `probe_wavlm_large.py`) has a wider range but tracked the 228 ratings no better (leave-one-line-out
  gain +0.54 swapped in, +0.59 added, vs +0.59 for the current composite), so it is not used.
- No speaker-embedding metric rises with cfg past 2.0-2.5 the way the user's voice rating does, so
  something the ratings reward at high cfg (less gravel/whisper) is only partly captured.
- The em-dash normalisation bug (`"a — b"` -> `"a , b"`) in `tools/build_test_set.py` `speech_only()`
  was fixed on 2026-09-24; `data/bon/Abelard_emdash_bug_run/` holds a few minutes of output from
  before the fix and can be ignored.
- One real Abelard clip (`PRL_AbelardRecruit_18.wav`) gives a non-finite WavLM embedding and is
  skipped.
- Whisper WER uses a crude proper-noun mask; it is only a gate against dropped or garbled words.
