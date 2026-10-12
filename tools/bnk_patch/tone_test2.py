"""Round 2 of the silent-audio diagnosis: four PCM wem header variants, all in the MAIN bank.

  1 EXT_MONO     WAVE_FORMAT_EXTENSIBLE, mono, channel mask 0x4 (what Wwise Authoring writes), 600 Hz tone
  2 EXT_STEREO   WAVE_FORMAT_EXTENSIBLE, stereo, mask 0x3, 800 Hz tone
  3 PLAIN_18     plain PCM fmt chunk with cbSize (18 bytes), 1000 Hz tone
  4 REAL_EXT     the real narrator render as WAVE_FORMAT_EXTENSIBLE mono

  python3 tone_test2.py --bank PRISTINE.bnk --export data/render/export_all_new --out-dir DIR
"""
import argparse, json, math, os, struct, subprocess, sys
sys.path.insert(0, os.path.dirname(__file__))
from bank import Bank, PLUGIN_PCM
from tone_test import write_bank, MAIN_NAME, RATE, TONE_SECONDS, TONE_AMP
from wem import FFMPEG, measure_lufs, TARGET_LUFS

LINES = {
    "EXT_MONO": "2d5e736b-9e34-40ba-80a6-fafbdb639a80",
    "EXT_STEREO": "cb3f1b83-c684-48ea-aba1-3310527b2dc8",
    "PLAIN_18": "a4e47895-75d8-4ecb-8624-ea262dcf00f8",
    "REAL_EXT": "d976ffbc-4346-4667-94e9-8207f0d6e4ee",
}
PCM_SUBFORMAT = bytes.fromhex("0100000000001000800000aa00389b71")
MASK_MONO, MASK_STEREO = 0x4, 0x3


def riff(fmt, pcm):
    body = b"WAVE" + b"fmt " + struct.pack("<I", len(fmt)) + fmt + b"data" + struct.pack("<I", len(pcm)) + pcm
    return b"RIFF" + struct.pack("<I", len(body)) + body


def fmt_ext(channels, mask, rate=RATE):
    block = 2 * channels
    return struct.pack("<HHIIHHHHI", 0xFFFE, channels, rate, rate * block, block, 16, 22, 16, mask) + PCM_SUBFORMAT


def fmt_plain18(rate=RATE):
    return struct.pack("<HHIIHHH", 1, 1, rate, rate * 2, 2, 16, 0)


def tone(hz, channels=1):
    n = RATE * TONE_SECONDS
    fade = RATE // 20
    out = []
    for i in range(n):
        v = int(32767 * TONE_AMP * min(1.0, i / fade, (n - i) / fade) * math.sin(2 * math.pi * hz * i / RATE))
        out += [v] * channels
    return struct.pack("<%dh" % len(out), *out)


def real_pcm(path):
    lufs = measure_lufs(path)
    gain = 0.0 if lufs is None else max(-12.0, min(12.0, TARGET_LUFS - lufs))
    af = "volume=%.2fdB,alimiter=limit=0.89" % gain
    return subprocess.run([FFMPEG, "-nostdin", "-hide_banner", "-i", path, "-af", af, "-ac", "1", "-ar", str(RATE),
                           "-f", "s16le", "-"], capture_output=True).stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bank", required=True)
    ap.add_argument("--export", required=True)
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args()
    bank = Bank(a.bank)
    idx = json.load(open(os.path.join(a.export, "index.json")))
    wems = {
        "EXT_MONO": riff(fmt_ext(1, MASK_MONO), tone(600)),
        "EXT_STEREO": riff(fmt_ext(2, MASK_STEREO), tone(800, 2)),
        "PLAIN_18": riff(fmt_plain18(), tone(1000)),
        "REAL_EXT": riff(fmt_ext(1, MASK_MONO), real_pcm(os.path.join(a.export, idx[LINES["REAL_EXT"]]["wav"]))),
    }
    hirc = bytearray(bank.hirc)
    new_media = {}
    for name, guid in LINES.items():
        snd, med = bank.media_for_guid(guid)
        b = bank.sounds[snd]
        struct.pack_into("<I", hirc, b + 4, PLUGIN_PCM)
        struct.pack_into("<I", hirc, b + 13, len(wems[name]))
        new_media[med] = wems[name]
        print(name, guid, "media", med, len(wems[name]), "bytes")
    keep = [(m, s, (lambda m=m: bank.read_media(m))) for m, _, s in bank.didx if m not in new_media]
    keep += [(m, len(d), (lambda d=d: d)) for m, d in new_media.items()]
    os.makedirs(a.out_dir, exist_ok=True)
    write_bank(os.path.join(a.out_dir, MAIN_NAME), bank.bkhd, struct.unpack_from("<I", bank.bkhd, 4)[0], keep, hirc)
    print("wrote", a.out_dir)


if __name__ == "__main__":
    main()
