#!/usr/bin/env bash
# Waits for the main bon_generate.py run to finish, then sweeps cfg above the 3.0 baseline on a
# fixed 40-line subset (3 takes each), scores everything, and prints the paired comparison.
set -u
cd "$(dirname "$0")/../.."
while pgrep -f "bon_generate.py --takes 6" >/dev/null; do sleep 30; done
for cfg in 3.5 4.0 4.5; do
  /home/geoff/anaconda3/envs/roguetts/bin/python3 tools/scorer/bon_generate.py --takes 3 --limit-lines 40 --cfg "$cfg" --out-name "Abelard_cfg$cfg"
done
for cfg in 3.5 4.0 4.5; do
  tools/scorer/.venv-scorer/bin/python tools/scorer/bon_score.py --out-name "Abelard_cfg$cfg"
done
tools/scorer/.venv-scorer/bin/python tools/scorer/compare_settings.py Abelard Abelard_cfg3.5 Abelard_cfg4.0 Abelard_cfg4.5
