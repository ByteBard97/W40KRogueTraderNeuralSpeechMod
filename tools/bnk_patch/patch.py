"""Write patched AIVO banks with our rendered audio swapped in.

  python3 patch.py --bank OLD.bnk --export data/render/export --out-dir DIR [--speaker X] [--limit N] [--dry-run]

Converted clips are cached as PCM .wem files under --cache so reruns are quick.
"""
import argparse, json, os, sys
from concurrent.futures import ProcessPoolExecutor
sys.path.insert(0, os.path.dirname(__file__))
from bank import PLUGIN_OPUS_WEM, PLUGIN_PCM, Bank
from wem import LOUDNESS_VERSION, linear_gain_db, measure_levels, pcm_wem
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "loudness"))
from targets import target_for


def convert(job):
    src, dst, target, trim, codec = job
    if not os.path.exists(dst):
        tmp = dst + ".part"
        with open(tmp, "wb") as f:
            if codec == "opus":   # same linear gain as the PCM path, applied before encoding
                from opus_wem import opus_wem
                lufs, peak = measure_levels(src)
                f.write(opus_wem(src, gain_db=linear_gain_db(lufs, peak, target, trim)))
            else:
                f.write(pcm_wem(src, target, trim))
        os.replace(tmp, dst)
    return dst


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bank", required=True)
    ap.add_argument("--export", required=True)
    ap.add_argument("--out-dir")
    ap.add_argument("--cache", default="data/render/wem_cache")
    ap.add_argument("--speaker")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--codec", choices=["pcm", "opus"], default="pcm", help="opus is about 16x smaller but must be proven in game first (tone_test3.py)")
    ap.add_argument("--trim", type=float, default=0.0, help="dB added to every loudness target (in-game balance knob)")
    a = ap.parse_args()
    bank = Bank(a.bank)
    idx = json.load(open(os.path.join(a.export, "index.json")))
    todo, missing = {}, 0
    for guid, e in idx.items():
        if a.speaker and e.get("speaker") != a.speaker:
            continue
        hit = bank.media_for_guid(guid)
        if hit is None:
            missing += 1
            continue
        todo[hit[1]] = (os.path.join(a.export, e["wav"]), None if e.get("loudness") == "preset" else target_for(e.get("speaker")))
    items = list(todo.items())[: a.limit]
    print(f"bank clips {len(bank.didx)}, replacing {len(items)}, no event/unsupported {missing}", flush=True)
    if a.dry_run:
        return
    os.makedirs(a.cache, exist_ok=True)
    os.makedirs(a.out_dir, exist_ok=True)
    # cache key: source wav (re-rendered lines are repacked), loudness version, target and trim (a new level repacks)
    jobs = [(p, os.path.join(a.cache, "%d_%d_%d_L%d_%s_%+.1f_%s.wem" % (m, os.stat(p).st_mtime, os.stat(p).st_size,
                                                                        LOUDNESS_VERSION, "preset" if tgt is None else "%+.1f" % tgt, a.trim, a.codec)), tgt, a.trim, a.codec)
            for m, (p, tgt) in items]
    with ProcessPoolExecutor(a.jobs) as ex:
        for i, _ in enumerate(ex.map(convert, jobs, chunksize=16)):
            if i % 1000 == 0:
                print("converted", i, flush=True)
    rep = {m: j[1] for (m, _), j in zip(items, jobs)}
    for path, size in bank.write_split(a.out_dir, os.path.splitext(os.path.basename(a.bank))[0], rep,
                                          plugin=PLUGIN_OPUS_WEM if a.codec == "opus" else PLUGIN_PCM):
        print(f"wrote {path}: DATA {size/1e9:.2f} GB")


if __name__ == "__main__":
    main()
