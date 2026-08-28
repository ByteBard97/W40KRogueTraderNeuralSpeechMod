#!/usr/bin/env python3
"""Extract Rogue Trader's voiced lines as speaker-attributed WAVs + a catalog for TTS experiments.

Pipeline (all local, nothing distributed):
  1. unpack the *_Dialogues.pck packages (bank + wem streams) into a work dir
  2. wwiser generates one .txtp per Wwise event, named by event (using names from Sound.json)
  3. vgmstream decodes each txtp to <out>/wav/<speaker>/<event>.wav
  4. catalog.json joins event -> speaker, wav path, duration, localization GUIDs and text

Speaker attribution: dialogue events map back to the localization strings that reference them
(Sound.json); the string GUID maps to cues in script.json whose speaker we exported. Banter
(BNTRS_*) and companion events also carry the speaker in the event name; both signals are used.

Requires: tools/bin/wwiser.pyz, tools/bin/vgmstream-cli, the game install, data/raw/script.json.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import wave
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIN = ROOT / "tools" / "bin"
GAME = Path("/mnt/games/SteamLibrary/steamapps/common/Warhammer 40,000 Rogue Trader")
SND = GAME / "WH40KRT_Data/StreamingAssets/Audio/GeneratedSoundBanks/Windows"
LOC = GAME / "WH40KRT_Data/StreamingAssets/Localization"

DIALOGUE_PCKS = ["WH40KRT_Main_Dialogues.pck", "WH40KRT_DLC2_Dialogues.pck", "WH40KRT_DLC3_Dialogues.pck"]

COMPANIONS = ["Abelard", "Argenta", "Cassia", "Heinrix", "Idira", "Jae", "Pasqal", "Yrliet",
              "Marazhai", "Ulfar", "Kibellah", "Solomorne", "Eogunn", "Manipulus"]
SPEAKER_IN_EVENT = re.compile("|".join(COMPANIONS) + "|RTMale[A-Za-z]+|RTFemale[A-Za-z]+", re.I)


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        raise RuntimeError(f"{cmd[0]} failed: {r.stderr[-400:]}")
    return r


def load_sound_map():
    """event name -> list of localization GUIDs whose string is voiced by it."""
    sound = json.load(open(LOC / "Sound.json", encoding="utf-8"))["strings"]
    ev2guids = defaultdict(list)
    for guid, v in sound.items():
        if v.get("Text"):
            ev2guids[v["Text"]].append(guid)
    return ev2guids


def load_speakers():
    """localization text GUID -> speaker character_name (from the dialogue export)."""
    script = json.load(open(ROOT / "data/raw/script.json", encoding="utf-8"))
    units = script["units"]
    guid2speaker = {}
    for n in script["nodes"].values():
        if n.get("type") != "cue" or not n.get("text_key"):
            continue
        sp = n.get("speaker_guid") or n.get("speaker_portrait_guid")
        if sp and sp in units:
            u = units[sp]
            guid2speaker[n["text_key"]] = u.get("character_name") or u.get("name")
    return guid2speaker


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / w.getframerate()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "data/voices"))
    ap.add_argument("--work", default=str(ROOT / "data/voices/_work"))
    ap.add_argument("--limit", type=int, default=0, help="decode at most N events (debug)")
    args = ap.parse_args()

    out = Path(args.out)
    work = Path(args.work)
    (out / "wav").mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)

    ev2guids = load_sound_map()
    guid2speaker = load_speakers()
    en = {r["key"]: r for r in json.load(open(ROOT / "data/strings.enGB.json", encoding="utf-8"))}

    # names file for wwiser
    (work / "wwnames.txt").write_text("\n".join(sorted(ev2guids)), encoding="utf-8")

    # 1-2: unpack + txtp per package
    txtps: list[Path] = []
    for pck in DIALOGUE_PCKS:
        stem = Path(pck).stem
        pck_dir = work / stem / "sfx"
        if not pck_dir.exists():
            run([sys.executable, str(ROOT / "tools/unpack_pck.py"), str(SND / "Packages" / pck), "--out", str(work)])
        for bnk in pck_dir.glob("*.bnk"):
            tdir = pck_dir / "txtp"
            if not tdir.exists():
                # wwiser auto-loads wwnames.txt from the bank's directory
                (pck_dir / "wwnames.txt").write_bytes((work / "wwnames.txt").read_bytes())
                run([sys.executable, str(BIN / "wwiser.pyz"), "-g", bnk.name], cwd=pck_dir)
            txtps += sorted(tdir.glob("*.txtp"))
    print(f"{len(txtps)} txtp events")

    # 3-4: decode + catalog
    catalog = {}
    skipped = Counter()
    done = 0
    for t in txtps:
        event = t.stem
        base_event = re.sub(r" \[.*\]$", "", event)  # switch variants: "Name [state=value]"
        if re.fullmatch(r"\d+-\d+-event", event):
            skipped["unnamed"] += 1
            continue
        guids = ev2guids.get(base_event, [])
        speaker = None
        for g in guids:
            if guid2speaker.get(g):
                speaker = guid2speaker[g]
                break
        if not speaker:
            m = SPEAKER_IN_EVENT.search(base_event)
            speaker = m.group(0) if m else "_unattributed"
        safe_speaker = re.sub(r"[^A-Za-z0-9_-]", "_", speaker)
        sdir = out / "wav" / safe_speaker
        sdir.mkdir(parents=True, exist_ok=True)
        wav_path = sdir / (re.sub(r"[^A-Za-z0-9_=\[\] -]", "_", event) + ".wav")
        if not wav_path.exists():
            r = subprocess.run([str(BIN / "vgmstream-cli"), "-o", str(wav_path), str(t)],
                               capture_output=True, text=True)
            if r.returncode != 0 or not wav_path.exists():
                skipped["decode_failed"] += 1
                continue
        texts = [{"guid": g, "text": en[g]["plain"], "voiced_speaker_hint": guid2speaker.get(g)}
                 for g in guids if g in en]
        catalog[event] = {
            "event": base_event,
            "speaker": speaker,
            "wav": str(wav_path.relative_to(out)),
            "duration": round(wav_duration(wav_path), 3),
            "texts": texts,
        }
        done += 1
        if done % 500 == 0:
            print(f"  decoded {done}...")
        if args.limit and done >= args.limit:
            break

    (out / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=1), encoding="utf-8")

    by_speaker = Counter()
    dur = Counter()
    for c in catalog.values():
        by_speaker[c["speaker"]] += 1
        dur[c["speaker"]] += c["duration"]
    lines = [f"# Voice extraction summary", "",
             f"- events decoded: {done}; skipped: {dict(skipped)}", "",
             f"| speaker | clips | minutes |", "|---|---|---|"]
    for s, n in by_speaker.most_common(40):
        lines.append(f"| {s} | {n} | {dur[s]/60:.1f} |")
    (out / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
