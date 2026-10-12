"""Generate N takes per line at fixed settings for the best-of-N scorer test.
Run: /home/geoff/anaconda3/envs/roguetts/bin/python3 tools/scorer/gen_best_of_n.py
Resumable; output data/scorer_probe/best_of_n/{manifest.json,wav/}."""
import json, sys, time
from pathlib import Path
import soundfile as sf

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/tts_bakeoff"))
import sweep_voxcpm2_cfg as sw  # noqa: E402

OUT = ROOT / "data/scorer_probe/best_of_n"
CFG, TS, N = 3.0, 10, 8
lines = {}
for m in json.load(open(sw.SWEEP_MANIFEST_PATH)):
    lines.setdefault(m["guid"], m)
(OUT / "wav").mkdir(parents=True, exist_ok=True)
mp = OUT / "manifest.json"
entries = json.load(open(mp)) if mp.exists() else []
done = {e["cell_id"] for e in entries}
model = sw.eng.load()
t0 = time.time()
for take in range(N):
    for guid, m in sorted(lines.items()):
        cid = f"{guid}_bon{take}"
        if cid in done:
            continue
        wav, sr = sw.synth_with_cfg(model, m["text"], m["reference"]["wav"], m["instruct"], CFG, TS)
        p = OUT / "wav" / f"{cid}.wav"
        sf.write(str(p), wav, sr)
        entries.append({"cell_id": cid, "guid": guid, "take": take, "text": m["text"], "instruct": m["instruct"],
                        "emotion": m["emotion"], "cfg_value": CFG, "wav_path": str(p.relative_to(ROOT)),
                        "reference": m["reference"], "audio_seconds": round(len(wav) / sr, 2)})
        json.dump(entries, open(mp, "w"), indent=1)
        print(f"[{len(entries)}/{N*len(lines)}] {cid} {time.time()-t0:.0f}s", flush=True)
print("done")
