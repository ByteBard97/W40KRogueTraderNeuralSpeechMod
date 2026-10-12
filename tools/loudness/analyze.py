"""Loudness statistics (EBU R128 via ffmpeg) for three sets of dialogue, to calibrate our renders.

  real   original game voice-over (data/voices/wav/<speaker>/*.wav)
  old    the old AIVO pack (Vorbis wems read out of the pristine bank and decoded with vgmstream), paired by guid
  ours   our renders (data/render/export_all_new/wav/<guid>.wav, as rendered, before the bank's -20 LUFS wem step)

Writes one JSON line per clip: set, id, group, I (LUFS), LRA, true peak (dBTP), RMS (dBFS), peak (dBFS), duration.
  python3 analyze.py --out data/loudness/stats.jsonl [--paired 1200] [--real-per-speaker 120]
"""
import argparse, json, os, random, re, subprocess, sys, tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/bnk_patch"))
FFMPEG = "/home/geoff/anaconda3/bin/ffmpeg"
VGM = ROOT / "tools/bin/vgmstream-cli"
PRISTINE = ("/mnt/games/SteamLibrary/steamapps/compatdata/2186680/pfx/drive_c/users/steamuser/AppData/LocalLow/"
            "Owlcat Games/Warhammer 40000 Rogue Trader/UnityModManager/W40KRT_AIVOMod/soundbanks_disabled/"
            "w40krt_avio_charvogen.bnk.chatterbox-original")


def measure(job):
    set_name, ident, group, path = job
    try:
        err = subprocess.run([FFMPEG, "-nostdin", "-hide_banner", "-nostats", "-i", path, "-af",
                              "ebur128=peak=true", "-f", "null", "-"], capture_output=True).stderr.decode()
        tail = err[err.rfind("Summary:"):]
        g = lambda pat: float(re.search(pat, tail).group(1))
        pcm = np.frombuffer(subprocess.run([FFMPEG, "-nostdin", "-hide_banner", "-i", path, "-ac", "1", "-ar", "24000",
                                            "-f", "s16le", "-"], capture_output=True).stdout, dtype="<i2").astype(float) / 32768
        if pcm.size == 0:
            return None
        rms = float(np.sqrt(np.mean(pcm ** 2)))
        peak = float(np.abs(pcm).max())
        return {"set": set_name, "id": ident, "group": group, "I": g(r"I:\s+(-?[\d.]+) LUFS"), "LRA": g(r"LRA:\s+([\d.]+) LU"),
                "tp": g(r"Peak:\s+(-?[\d.]+) dBFS"), "rms": 20 * np.log10(max(rms, 1e-9)),
                "peak": 20 * np.log10(max(peak, 1e-9)), "dur": pcm.size / 24000}
    except Exception as e:  # silent or undecodable clips
        print("skip", ident, e, file=sys.stderr)
        return None


def old_aivo_clips(guids, work):
    from bank import Bank, fnv32
    bank = Bank(PRISTINE)
    jobs = []
    os.makedirs(work, exist_ok=True)
    for guid, group in guids:
        hit = bank.media_for_guid(guid)
        if hit is None:
            continue
        wem, wav = os.path.join(work, guid + ".wem"), os.path.join(work, guid + ".wav")
        with open(wem, "wb") as f:
            f.write(bank.read_media(hit[1]))
        r = subprocess.run([str(VGM), "-o", wav, wem], capture_output=True)
        if r.returncode == 0 and os.path.exists(wav):
            jobs.append(("old", guid, group, wav))
    return jobs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--paired", type=int, default=1200)
    ap.add_argument("--real-per-speaker", type=int, default=120)
    ap.add_argument("--work", default=tempfile.mkdtemp(prefix="loud_"))
    ap.add_argument("--jobs", type=int, default=8)
    a = ap.parse_args()
    rnd = random.Random(7)
    idx = json.load(open(ROOT / "data/render/export_all_new/index.json"))

    jobs = []
    for sp in sorted((ROOT / "data/voices/wav").iterdir()):
        wavs = sorted(sp.glob("*.wav"))
        rnd.shuffle(wavs)
        jobs += [("real", w.stem, sp.name, str(w)) for w in wavs[: a.real_per_speaker]]

    guids = list(idx)
    rnd.shuffle(guids)
    paired = [(g, "narrator" if idx[g]["speaker"] == "narrator" else "named") for g in guids]
    old = old_aivo_clips(paired[: int(a.paired * 1.3)], a.work)[: a.paired]
    print("old clips decoded", len(old), flush=True)
    jobs += old
    jobs += [("ours", g, grp, str(ROOT / "data/render/export_all_new" / idx[g]["wav"])) for _, g, grp, _ in old]
    jobs += [("ours_all", g, "narrator" if e["speaker"] == "narrator" else "named", str(ROOT / "data/render/export_all_new" / e["wav"]))
             for g, e in list(idx.items())[::6]]

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    n = 0
    with ProcessPoolExecutor(a.jobs) as ex, open(a.out, "w") as f:
        for r in ex.map(measure, jobs, chunksize=8):
            if r:
                f.write(json.dumps(r) + "\n")
                n += 1
            if n % 500 == 0 and n:
                print("measured", n, flush=True)
    print("wrote", n, "to", a.out)


if __name__ == "__main__":
    main()
