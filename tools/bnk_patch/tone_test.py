"""Build a diagnostic bank set from the pristine AIVO bank to find out why replaced audio is silent.

Four narrator events get four different treatments; everything else stays original and audible:

  A_TONE_MAIN   1 kHz-ish tone as a PCM wem stored in the MAIN bank (no side bank involved)
  B_TONE_SIDE   the same tone as a PCM wem in a media-only SIDE bank
  C_WIRING      Sound re-pointed at another line's original Vorbis media (should play that other line)
  D_REAL_MAIN   the real narrator render as a PCM wem in the MAIN bank

  python3 tone_test.py --bank PRISTINE.bnk --export data/render/export_all_new --out-dir DIR
"""
import argparse, json, math, os, struct, sys
sys.path.insert(0, os.path.dirname(__file__))
from bank import Bank, fnv32, PLUGIN_PCM, PLUGIN_VORBIS
from wem import pcm_wem

A_TONE_MAIN = "2d5e736b-9e34-40ba-80a6-fafbdb639a80"
B_TONE_SIDE = "cb3f1b83-c684-48ea-aba1-3310527b2dc8"
C_WIRING = "a4e47895-75d8-4ecb-8624-ea262dcf00f8"
D_REAL_MAIN = "d976ffbc-4346-4667-94e9-8207f0d6e4ee"
WIRING_DONOR = "6328405c-2613-46f7-9f70-c5d2d8d01678"  # an unreplaced line with a known voice (Jae)
RATE, TONE_SECONDS, TONE_HZ, TONE_AMP = 24000, 4, 600, 0.5
ALIGN = 16
SIDE_NAME = "w40krt_avio_charvogen_pcm1"
MAIN_NAME = "w40krt_avio_charvogen.bnk"


def tone_wem():
    n = RATE * TONE_SECONDS
    fade = RATE // 20
    samples = []
    for i in range(n):
        env = min(1.0, i / fade, (n - i) / fade)
        samples.append(int(32767 * TONE_AMP * env * math.sin(2 * math.pi * TONE_HZ * i / RATE)))
    pcm = struct.pack("<%dh" % n, *samples)
    fmt = struct.pack("<HHIIHH", 1, 1, RATE, RATE * 2, 2, 16)
    body = b"WAVE" + b"fmt " + struct.pack("<I", 16) + fmt + b"data" + struct.pack("<I", len(pcm)) + pcm
    return b"RIFF" + struct.pack("<I", len(body)) + body


def write_bank(path, bkhd, bank_id, items, hirc):
    """items: list of (media_id, size, reader). hirc None writes a media-only bank."""
    entries, pos = [], 0
    for m, size, _ in items:
        pos = (pos + ALIGN - 1) // ALIGN * ALIGN
        entries.append((m, pos, size))
        pos += size
    assert pos < 2**32, "DATA over the u32 limit"
    didx = b"".join(struct.pack("<III", *e) for e in entries)
    head = bytearray(bkhd)
    struct.pack_into("<I", head, 4, bank_id)
    with open(path, "wb") as o:
        o.write(struct.pack("<4sI", b"BKHD", len(head)) + bytes(head))
        o.write(struct.pack("<4sI", b"DIDX", len(didx)) + didx)
        o.write(struct.pack("<4sI", b"DATA", pos))
        cur = 0
        for (m, p, s), (_, _, rd) in zip(entries, items):
            o.write(b"\0" * (p - cur))
            o.write(rd())
            cur = p + s
        if hirc is not None:
            o.write(struct.pack("<4sI", b"HIRC", len(hirc)) + bytes(hirc))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bank", required=True)
    ap.add_argument("--export", required=True)
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args()
    bank = Bank(a.bank)
    idx = json.load(open(os.path.join(a.export, "index.json")))

    media = {}
    for name, guid in [("A", A_TONE_MAIN), ("B", B_TONE_SIDE), ("C", C_WIRING), ("D", D_REAL_MAIN), ("donor", WIRING_DONOR)]:
        hit = bank.media_for_guid(guid)
        assert hit, f"{name} {guid}: no event/unsupported in this bank"
        media[name] = hit  # (sound object id, media id)
        print(name, guid, "sound", hit[0], "media", hit[1])

    tone = tone_wem()
    real = pcm_wem(os.path.join(a.export, idx[D_REAL_MAIN]["wav"]))
    new_media = {media["A"][1]: tone, media["D"][1]: real}  # into the main bank
    side_media = {media["B"][1]: tone}

    hirc = bytearray(bank.hirc)
    for key, data in (("A", tone), ("B", tone), ("D", real)):
        b = bank.sounds[media[key][0]]
        struct.pack_into("<I", hirc, b + 4, PLUGIN_PCM)
        struct.pack_into("<I", hirc, b + 13, len(data))
    donor_media = media["donor"][1]
    b = bank.sounds[media["C"][0]]
    struct.pack_into("<I", hirc, b + 4, PLUGIN_VORBIS)
    struct.pack_into("<I", hirc, b + 9, donor_media)
    struct.pack_into("<I", hirc, b + 13, bank.media_size[donor_media])

    drop = set(new_media) | set(side_media)
    keep = [(m, s, (lambda m=m: bank.read_media(m))) for m, _, s in bank.didx if m not in drop]
    keep += [(m, len(d), (lambda d=d: d)) for m, d in new_media.items()]
    os.makedirs(a.out_dir, exist_ok=True)
    main_bank_id = struct.unpack_from("<I", bank.bkhd, 4)[0]
    write_bank(os.path.join(a.out_dir, MAIN_NAME), bank.bkhd, main_bank_id, keep, hirc)
    side = [(m, len(d), (lambda d=d: d)) for m, d in side_media.items()]
    write_bank(os.path.join(a.out_dir, SIDE_NAME + ".bnk"), bank.bkhd, fnv32(SIDE_NAME), side, None)
    print("wrote", a.out_dir)


if __name__ == "__main__":
    main()
