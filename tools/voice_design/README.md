# Designed voices for side NPCs

NPCs with no voiced clips get a voice made from a text description, then every one of their lines is cloned
from that saved clip (so the voice stays the same). Audition page: `python3 tools/voice_design/audit_server.py`
then http://127.0.0.1:8907 (local only; it serves audio made from game files).

Pipeline (all resumable):

1. `npcs.json` holds the NPC list, descriptions and the fixed design sentence. `data/voice_design/overrides.json`
   (written by the page's "Save description for redo") wins over it.
2. `design.py --engine vox` (VoxCPM2 env) renders 6 candidates per NPC to `data/voice_design/clips/<slug>/`.
   Run it on the Mac: `~/rt-tts/.venv-vox/bin/python tools/voice_design/design.py`.
3. `score_candidates.py` (scorer venv) adds the accent hint (`p_us`, CommonAccent XLSR) to `scores.json`.
   `--utmos` also adds UTMOS but needs the scorer's model cache (it lives on the external drive).
4. `clone_test.py` (VoxCPM2 env) clones the top 3 candidates onto 2 of the NPC's real lines.
5. Audit page: accent / fit / reject / pick. "Register picks" runs `register.py`, which copies the clip to
   `data/voices/prompts/designed/<slug>.wav` and adds the NPC to `prompts.json`. Re-run
   `tools/render_corpus/plan.py` afterwards and those lines leave the `fallback` voice.

## What the accent check can and can't tell you

- Qwen3-TTS VoiceDesign ignored every accent request (12 of 12 test clips came back American, whatever the
  phrasing), so VoxCPM2's `(description)text` design mode is the default. Its best phrasing puts the accent last:
  `..., British English accent.` (`probe_accent_phrasing.py`).
- 58 of 72 first-round VoxCPM2 candidates scored `p_us < 0.5`. Of 66 clone-test clips made from low-`p_us`
  candidates, 57 stayed below 0.5, so the accent mostly survives cloning.
- The classifier is noisy: real game actors Seberian (0.99), Solomorne (0.86) and Ulfar (0.67) score as
  American. Treat `p_us` as a hint and judge by ear. Calibration is in `accent_calibration.json`.
- Fine labels are unreliable (real British clips came back as wales / new zealand / australia).
