# Recipe render jobs

A job with a `recipe` field is rendered by `tools/render_corpus/recipe_render.py` instead of the plain path. The recipe is the Render Lab's
(`data/studio/lab/recipes.json`); the planner copies it into every job, so a lexicon or recipe edit never changes a render that is already queued.

Fields read from `job["recipe"]`: `cfg`, `timesteps`, `normalize` (never inside `{PHONEME}` guides), `instruct` (`annotation` | `none` | `custom` +
`instruct_text`), `lexicon`, `pronunciation` (overrides run before the lexicon), `punctuation` (per mark: keep, comma, period, ellipsis, space, pause),
`pause_ms`, `split` (`whole` | `sentence` | `clause` | `max`, `max_chars`, `min_chars`), `gaps_ms`, `level_match`, `trim_silence`, `onset_soften_db/ms`,
`peak_limit_db`, `seed` (text salt), `qc`. `period` makes the mark a sentence end and capitalises the next word.

Precedence: the job's own `recipe` wins over every default in `render.py`; `respell: false` is set so the lexicon pass is the recipe's, not the old one.
Seeds are derived from guid, recipe seed and piece index, so a render is repeatable; each QC attempt adds a fixed stride.

Quality control, per piece: crest factor under 11 dB (overdriven) or a run of clipped samples triggers up to `qc.attempts` takes (default 4): a new
seed first, then `cfg` lowered by `cfg_step` (0.5) down to `min_cfg` (1.5). The best take is kept; anything still flagged gets `piece_overdriven`.
Pieces under 1 s are not judged. The joined take is measured again and its flags go in the manifest row with `crest_db`, `model_peak`, `attempts`, `cfg_used`.
Recipe jobs are written as 32-bit float wavs: a model peak past full scale is measured and scaled at the join, never clipped by a 16-bit write.

Second pass: `recipe_followup.py` re-plans flagged or Whisper-rejected pieces as `<guid>@fix` jobs (same recipe, new seed salt, 6 attempts); `takes.pick`
tries `@fix` first. Stitch with `--runs <recipe run> cast`, then overlay `cast-r2b-stitched` last (`night_build.py`).
