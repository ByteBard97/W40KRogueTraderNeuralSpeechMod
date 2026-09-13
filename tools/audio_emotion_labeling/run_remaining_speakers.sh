#!/usr/bin/env bash
# Runs Ultravox audio-emotion labeling (both modes) for every named catalog speaker except
# _unattributed (no character identity - not useful for a per-speaker vocabulary) and Abelard
# (already fully labeled - see data/voices/emotion_banks/audio_llm_labels.json).
#
# Wraps each (speaker, mode) invocation in a restart loop: this machine's GPU is shared across
# concurrent Claude Code sessions on other projects (see memory: shared-gpu-contention-risk), so
# a transient CUDA OOM from another session grabbing VRAM shouldn't strand the rest of an
# unattended overnight run. label.py is resumable at 25-clip granularity (already-labeled
# event/backend/mode combos are skipped), so re-invoking it after a crash just continues.
#
# Run gpt-oss (or anything else GPU-resident) stopped first - `ollama stop <model>` - Ultravox
# needs ~6-8GB free at 4-bit and won't share a 16GB card with a 13GB-resident Ollama model.
set -uo pipefail
cd "$(dirname "$0")"

SPEAKERS=(Solomorne Kibellah Heinrix Marazhai Jae Ulfar Cassia Idira Yrliet Argenta \
          Manipulus Pasqal Eogunn Edelthrad "Trazyn, Lord of Histories" Theodora \
          "Theobald Orsellio" Stranger Overseer "Trazyn the Infinite" Seberian \
          "Kunrad Voigtvir" Mort "Vox-Skull" "Master Helmsman Ravor")
MODES=(audio "audio+text")
MAX_ATTEMPTS=40
RETRY_DELAY_S=120

for speaker in "${SPEAKERS[@]}"; do
  for mode in "${MODES[@]}"; do
    echo "=== $(date -Is) : ${speaker} / ${mode} ==="
    ok=0
    for attempt in $(seq 1 "$MAX_ATTEMPTS"); do
      .venv-ultravox/bin/python label.py --backend ultravox --mode "$mode" --speaker "$speaker" && { ok=1; break; }
      echo "  attempt ${attempt}/${MAX_ATTEMPTS} failed, retrying in ${RETRY_DELAY_S}s"
      sleep "$RETRY_DELAY_S"
    done
    if [ "$ok" -ne 1 ]; then
      echo "  GAVE UP on ${speaker}/${mode} after ${MAX_ATTEMPTS} attempts - moving on"
    fi
  done
done
echo "=== $(date -Is) : all speakers done ==="
