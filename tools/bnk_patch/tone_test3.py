"""Round 3 (compression): Wwise Opus wems in the four Footfall test lines, plus a PCM control. Stage only, do not install
over a working set before the user has heard it.

  A  OPUS_WEM tag 0x3041, codec plugin 0x00140001 (AKCODECID_AKOPUS_WEM), real narrator audio
  B  same wem, plugin 0x00130001 (AKCODECID_AKOPUS)
  C  same wem with cbSize 16 in the fmt chunk, plugin 0x00140001
  D  control: extensible PCM (the proven format) at the new loudness target

  python3 tone_test3.py --bank PRISTINE.bnk --export data/render/export_all_new --out-dir DIR
"""
import argparse, json, os, struct, sys
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "loudness"))
from bank import Bank
from opus_wem import opus_wem
from targets import target_for
from tone_test import write_bank, MAIN_NAME
from wem import linear_gain_db, measure_levels, pcm_wem

LINES = {"A": "2d5e736b-9e34-40ba-80a6-fafbdb639a80", "B": "cb3f1b83-c684-48ea-aba1-3310527b2dc8",
         "C": "a4e47895-75d8-4ecb-8624-ea262dcf00f8", "D": "d976ffbc-4346-4667-94e9-8207f0d6e4ee"}
PLUGIN_OPUS_WEM, PLUGIN_OPUS = 0x00140001, 0x00130001


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bank", required=True)
    ap.add_argument("--export", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--only-new", action="store_true",
                    help="keep only the four test clips in the bank (small file, for the in-game format tester mod)")
    a = ap.parse_args()
    bank = Bank(a.bank)
    idx = json.load(open(os.path.join(a.export, "index.json")))
    wavs = {k: os.path.join(a.export, idx[g]["wav"]) for k, g in LINES.items()}
    target = target_for("narrator")
    variants = {}
    for k, cb in (("A", None), ("B", None), ("C", 16)):
        lufs, tp = measure_levels(wavs[k])
        variants[k] = (opus_wem(wavs[k], gain_db=linear_gain_db(lufs, tp, target), cb_size=cb),
                       PLUGIN_OPUS if k == "B" else PLUGIN_OPUS_WEM)
    variants["D"] = (pcm_wem(wavs["D"], target), 0x00010001)
    hirc = bytearray(bank.hirc)
    new = {}
    for k, guid in LINES.items():
        snd, med = bank.media_for_guid(guid)
        data, plugin = variants[k]
        b = bank.sounds[snd]
        struct.pack_into("<I", hirc, b + 4, plugin)
        struct.pack_into("<I", hirc, b + 13, len(data))
        new[med] = data
        print(k, guid[:8], hex(plugin), len(data), "bytes")
    keep = [] if a.only_new else [(m, s, (lambda m=m: bank.read_media(m))) for m, _, s in bank.didx if m not in new]
    keep += [(m, len(d), (lambda d=d: d)) for m, d in new.items()]
    os.makedirs(a.out_dir, exist_ok=True)
    write_bank(os.path.join(a.out_dir, MAIN_NAME), bank.bkhd, struct.unpack_from("<I", bank.bkhd, 4)[0], keep, hirc)
    print("wrote", a.out_dir)
    if a.only_new:
        write_tester_files(a.out_dir, bank, wavs, target)


def write_tester_files(out_dir, bank, wavs, target):
    """Files for tools/format_tester: tests.json plus a PCM wem (line A's audio) to push into line D's media with SetMedia."""
    snd_d, med_d = bank.media_for_guid(LINES["D"])
    wem = pcm_wem(wavs["A"], target)
    open(os.path.join(out_dir, "setmedia_override.wem"), "wb").write(wem)
    tests = {"bank": MAIN_NAME, "lines": {k: "ev_" + g for k, g in LINES.items()},
             "setmedia": {"event": "ev_" + LINES["D"], "sourceId": med_d, "wem": "setmedia_override.wem"}}
    json.dump(tests, open(os.path.join(out_dir, "tests.json"), "w"), indent=2)
    print("wrote tests.json, setmedia_override.wem (source", med_d, ")")


if __name__ == "__main__":
    main()
