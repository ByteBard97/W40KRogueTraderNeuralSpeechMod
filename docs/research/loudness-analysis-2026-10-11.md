# Loudness analysis of game VO, old AIVO pack and our renders (2026-10-11)

Tool: `tools/loudness/analyze.py` (EBU R128 through ffmpeg `ebur128=peak=true`, plus RMS and sample peak). Raw rows are in
`data/loudness/stats.jsonl` (real, old, ours) and `data/loudness/shipped.jsonl` (our clips read back out of the installed
banks). Samples: 2,126 real game VO clips (150 per speaker), 1,200 guids paired between the old AIVO bank and our renders
(635 narrator, 565 named), plus about 2,100 renders at random.

## Results (integrated LUFS p10 / median / p90, median LRA, true peak, crest = peak minus RMS)

| Set | n | LUFS p10 / med / p90 | LRA | True peak med / p95 | Crest |
|---|---|---|---|---|---|
| Real game VO | 2126 | -24.1 / -22.3 / -20.0 | 2.7 | -6.3 / -4.4 dBTP | 16.8 dB |
| Old AIVO pack (paired) | 1200 | -21.0 / -18.8 / -16.6 | 2.9 | -0.3 / +0.1 dBTP | 19.1 dB |
| Ours as shipped, narrator | 635 | -19.0 / -19.0 / -18.9 | 2.3 | +0.4 / +0.8 dBTP | 18.7 dB |
| Ours as shipped, named | 565 | -19.0 / -18.9 / -18.9 | 2.3 | -3.3 / -0.3 dBTP | 15.7 dB |
| Ours raw (before the wem step), narrator | 635 | -21.9 / -21.9 / -20.4 | 2.3 | -0.9 | 20.4 dB |

Per real speaker the medians sit between -19.9 and -24.4 LUFS (Abelard -22.6, Argenta -22.6, Jae -22.3, Idira -22.1,
Pasqal -20.1, Ulfar -19.9, Heinrix -23.2, Marazhai -23.2).

## What this says

1. **We match the old AIVO pack on median loudness (about -19 LUFS), but the old pack is itself 3.5 LU louder than the
   game's real voice-over (-22.3).** Both AI voices sit hot against the real VO, and ours is as hot as theirs.
2. **Our clips have no spread.** Every shipped clip lands at -19.0 (p10 to p90 is 0.1 LU) because `wem.py` normalises each
   clip to the same target. The old pack varies by about 4.4 LU (p10 to p90) and real VO by 4.1 LU. A flat level makes the
   narrator read as constantly loud next to lines that breathe.
3. **The narrator clips clip.** 499 of 635 shipped narrator clips have true peaks above 0 dBTP (median +0.4), because the
   normaliser lifts them about 3 LU (raw median -21.9 to -19.0) and the limiter only guards sample peaks at 0.89, not
   inter-sample peaks. The old pack also touches 0 dBTP (median -0.3) but the real VO peaks near -6.
4. Named-speaker clips are less hot at the peaks (median -3.3 dBTP) because their takes are less dynamic (crest 15.7 dB).

## Proposed metric and target

- Target integrated loudness per clip: the real-VO distribution rather than the old pack. Use -22.3 LUFS median, with each
  named speaker's own real-VO median as its target where we have one (table above), narrator at the overall median.
- Keep a little natural spread instead of a flat level: draw each clip's target as speaker median plus its raw
  deviation scaled by 0.5, or simply clamp to the real-VO p10 to p90 band (-24.1 to -20.0).
- True peak ceiling -1.5 dBTP (real VO p95 is -4.4, p50 -6.3, so -1.5 is generous). Use a true-peak limiter, not a
  sample-peak one.
- Keep LRA as rendered (2.3 vs real 2.7 is close enough).
- One global trim knob (default -3.5 LU relative to the old pack) so the user can set the in-game balance by ear: the bus
  gain applied to AIVO events in game is unknown, so these numbers are relative to the game's own VO, and the final
  offset has to be checked in game.

## Not done yet

`tools/bnk_patch/wem.py` still normalises to a flat -20 LUFS with the sample-peak limiter. Changing it needs a rebuild of the
12,475 clips (about 12 minutes) and a bank install. Waiting on a go-ahead for the target values above.
