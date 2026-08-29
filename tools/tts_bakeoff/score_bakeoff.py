#!/usr/bin/env python3
"""Score bake-off outputs: speaker similarity to the real actor + intelligibility (WER).

- Similarity: ECAPA-TDNN (speechbrain spkrec-ecapa-voxceleb) cosine between each synthesized
  clip and the centroid of the speaker's real prompt-bank clips. Narrator has no reference,
  so similarity is skipped there.
- WER: faster-whisper (small.en) transcript vs the test-set text, both normalized.

Output: data/bakeoff/scores.json + scores.md (per engine x speaker table).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
BAKE = ROOT / "data/bakeoff"


def norm_text(t: str) -> list[str]:
    t = re.sub(r"[^a-z0-9' ]+", " ", t.lower())
    return t.split()


def wer(ref: list[str], hyp: list[str]) -> float:
    d = np.zeros((len(ref) + 1, len(hyp) + 1), dtype=np.int32)
    d[:, 0] = np.arange(len(ref) + 1)
    d[0, :] = np.arange(len(hyp) + 1)
    for i in range(1, len(ref) + 1):
        for j in range(1, len(hyp) + 1):
            d[i, j] = min(d[i-1, j] + 1, d[i, j-1] + 1, d[i-1, j-1] + (ref[i-1] != hyp[j-1]))
    return float(d[-1, -1]) / max(1, len(ref))


def main() -> None:
    import torch
    import torchaudio
    from speechbrain.inference.speaker import EncoderClassifier
    from faster_whisper import WhisperModel

    device = "cuda" if torch.cuda.is_available() else "cpu"
    enc = EncoderClassifier.from_hparams(source="speechbrain/spkrec-ecapa-voxceleb",
                                         run_opts={"device": device})
    whisper = WhisperModel("small.en", device=device, compute_type="float16" if device == "cuda" else "int8")

    def embed(path: Path):
        import soundfile as sf
        data, sr = sf.read(str(path), dtype="float32", always_2d=True)
        sig = torch.from_numpy(data.T)
        if sig.shape[0] > 1:
            sig = sig.mean(dim=0, keepdim=True)
        if sr != 16000:
            sig = torchaudio.functional.resample(sig, sr, 16000)
        with torch.no_grad():
            return enc.encode_batch(sig.to(device)).squeeze().cpu().numpy()

    def transcribe(path: Path) -> str:
        segs, _ = whisper.transcribe(str(path), language="en", beam_size=3)
        return " ".join(s.text for s in segs)

    test = {t["id"]: t for t in json.load(open(ROOT / "data/tts_test_set.json", encoding="utf-8"))}
    prompts = json.load(open(ROOT / "data/voices/prompts/prompts.json", encoding="utf-8"))

    # reference centroids from real clips
    centroids = {}
    for sp, bank in prompts.items():
        embs = []
        for p in bank[:8]:
            try:
                embs.append(embed(ROOT / "data/voices" / p["wav"]))
            except Exception:
                pass
        if embs:
            c = np.mean(embs, axis=0)
            centroids[sp] = c / np.linalg.norm(c)

    engines = sys.argv[1:] or [d.name for d in BAKE.iterdir() if d.is_dir()]
    scores = {}
    for engine in engines:
        edir = BAKE / engine
        rows = []
        for wav in sorted(edir.glob("t*.wav")):
            tid, _, sp = wav.stem.partition("_")
            item = test.get(tid)
            if not item:
                continue
            row = {"id": tid, "speaker": sp}
            if sp in centroids:
                e = embed(wav)
                row["similarity"] = round(float(np.dot(e / np.linalg.norm(e), centroids[sp])), 4)
            hyp = transcribe(wav)
            row["wer"] = round(wer(norm_text(item["text"]), norm_text(hyp)), 3)
            rows.append(row)
        scores[engine] = rows
        sims = [r["similarity"] for r in rows if "similarity" in r]
        wers = [r["wer"] for r in rows]
        print(f"{engine}: n={len(rows)} sim={np.mean(sims):.3f} wer={np.mean(wers):.3f}" if rows else f"{engine}: no output")

    (BAKE / "scores.json").write_text(json.dumps(scores, indent=1), encoding="utf-8")

    # per-speaker markdown table
    speakers = sorted({r["speaker"] for rows in scores.values() for r in rows})
    lines = ["# Bake-off scores", "", "similarity = ECAPA cosine vs real-voice centroid (higher better); wer = word error rate (lower better)", ""]
    header = "| speaker | " + " | ".join(f"{e} sim / wer" for e in scores) + " |"
    lines += [header, "|" + "---|" * (len(scores) + 1)]
    for sp in speakers:
        cells = []
        for e in scores:
            rs = [r for r in scores[e] if r["speaker"] == sp]
            sims = [r["similarity"] for r in rs if "similarity" in r]
            wers = [r["wer"] for r in rs]
            cells.append(f"{np.mean(sims):.3f} / {np.mean(wers):.2f}" if sims else (f"- / {np.mean(wers):.2f}" if wers else "-"))
        lines.append(f"| {sp} | " + " | ".join(cells) + " |")
    (BAKE / "scores.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("wrote", BAKE / "scores.md")


if __name__ == "__main__":
    main()
