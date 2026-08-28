#!/usr/bin/env python3
"""Extract Rogue Trader localization strings into a flat, analysis-ready dataset.

Reads <game>/WH40KRT_Data/StreamingAssets/Localization/{locale}.json and Sound.json
(the voiced-line map) and writes:

  data/strings.<locale>.json   one record per string: key, text, plain (markup stripped),
                               voiced event name (or null), markup tag inventory
  data/vocab_worklist.<locale>.csv   out-of-dictionary tokens by frequency (lexicon candidates)
  data/stats.<locale>.md       summary numbers

No game process needed; these are plain files on disk.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path

DEFAULT_GAME_DIR = "/mnt/games/SteamLibrary/steamapps/common/Warhammer 40,000 Rogue Trader"
WORDLISTS = ["/usr/share/dict/american-english", "/usr/share/dict/british-english", "/usr/share/dict/words"]

# Owlcat/TMP markup seen in the strings: {g|Encyclopedia:Foo}text{/g}, {n}, {mf|his|her}, <b>, <color=#...>, <i>, etc.
OWLCAT_TAG_OPEN = re.compile(r"\{([a-zA-Z]+)(?:\|([^}]*))?\}")
OWLCAT_TAG_CLOSE = re.compile(r"\{/([a-zA-Z]+)\}")
TMP_TAG = re.compile(r"</?[a-zA-Z][^<>]*>")
TOKEN = re.compile(r"[A-Za-z][A-Za-z'\-]+")


def strip_markup(text: str) -> tuple[str, Counter]:
    """Return plain text plus a Counter of tag kinds encountered."""
    tags: Counter = Counter()

    def owlcat_open(m: re.Match) -> str:
        kind, arg = m.group(1), m.group(2)
        tags[f"{{{kind}}}"] += 1
        if kind == "mf" and arg:  # {mf|male|female} gender variants -> keep male form for the worklist
            return arg.split("|")[0]
        if kind == "n":  # {n} = newline
            return " "
        return ""  # {g|...}, {d|...} etc. wrap visible text; the wrapper itself carries nothing to speak

    plain = OWLCAT_TAG_OPEN.sub(owlcat_open, text)
    plain = OWLCAT_TAG_CLOSE.sub("", plain)

    def tmp(m: re.Match) -> str:
        tags[m.group(0).split()[0].strip("<>/") if not m.group(0).startswith("</") else "close"] += 1
        return ""

    plain = TMP_TAG.sub(tmp, plain)
    plain = re.sub(r"\s+", " ", plain).strip()
    return plain, tags


def load_wordlist() -> set[str]:
    words: set[str] = set()
    for p in WORDLISTS:
        try:
            with open(p, encoding="utf-8", errors="ignore") as f:
                words.update(w.strip().lower() for w in f)
        except FileNotFoundError:
            pass
    return words


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--game-dir", default=DEFAULT_GAME_DIR)
    ap.add_argument("--locale", default="enGB")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "data"))
    args = ap.parse_args()

    loc_dir = Path(args.game_dir) / "WH40KRT_Data" / "StreamingAssets" / "Localization"
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    strings = json.load(open(loc_dir / f"{args.locale}.json", encoding="utf-8"))["strings"]
    sound = json.load(open(loc_dir / "Sound.json", encoding="utf-8"))["strings"]
    voiced = {k: v["Text"] for k, v in sound.items()}

    wordlist = load_wordlist()
    records = []
    tag_totals: Counter = Counter()
    oov: Counter = Counter()
    oov_examples: dict[str, str] = {}
    total_chars = 0
    empty = 0

    for key, entry in strings.items():
        text = entry.get("Text", "")
        if not text.strip():
            empty += 1
        plain, tags = strip_markup(text)
        tag_totals.update(tags)
        total_chars += len(plain)
        for tok in TOKEN.findall(plain):
            low = tok.lower().strip("'-")
            if len(low) < 3 or low in wordlist:
                continue
            oov[low] += 1
            oov_examples.setdefault(low, plain[:160])
        records.append({
            "key": key,
            "text": text,
            "plain": plain,
            "voiced": voiced.get(key),
            "tags": dict(tags) if tags else None,
        })

    (out_dir / f"strings.{args.locale}.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=0), encoding="utf-8")

    with open(out_dir / f"vocab_worklist.{args.locale}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["token", "count", "example"])
        for tok, n in oov.most_common():
            w.writerow([tok, n, oov_examples[tok]])

    n_voiced = sum(1 for r in records if r["voiced"])
    lengths = sorted(len(r["plain"]) for r in records)
    stats = [
        f"# Localization stats ({args.locale})",
        "",
        f"- strings: {len(records)}",
        f"- empty: {empty}",
        f"- voiced (present in Sound.json): {n_voiced} ({100*n_voiced/len(records):.1f}%)",
        f"- total plain chars: {total_chars:,} (~{total_chars//4:,} tokens)",
        f"- length median/p90/max: {lengths[len(lengths)//2]} / {lengths[int(len(lengths)*0.9)]} / {lengths[-1]}",
        f"- distinct out-of-dictionary tokens: {len(oov)}; occurrences: {sum(oov.values()):,}",
        "",
        "## Markup tags seen",
        "",
        *[f"- `{t}`: {n}" for t, n in tag_totals.most_common(25)],
        "",
        "## Top 40 out-of-dictionary tokens",
        "",
        *[f"- {t}: {n}" for t, n in oov.most_common(40)],
    ]
    (out_dir / f"stats.{args.locale}.md").write_text("\n".join(stats) + "\n", encoding="utf-8")
    print("\n".join(stats))


if __name__ == "__main__":
    main()
