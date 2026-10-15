#!/usr/bin/env python3
"""Map every dialog cue to a game chapter from the game's own blueprint pack (read-only).

Bundles/blueprints-pack.bbp holds every blueprint as a binary blob that stores references to other blueprints as 32-hex
guid strings; Bundles/cheatdata.json gives each blueprint's name and type. We build the reference graph from the blobs,
then walk from each BlueprintDialog up its referrers until we reach an etude, and up the etude's parents to Chapter01..05.
Output: data/chapter_map.json  {dialog_guid: {"chapters": [1,..], "via": [...]}}
"""
from __future__ import annotations

import json
import re
import struct
import uuid
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLES = Path("/mnt/games/SteamLibrary/steamapps/common/Warhammer 40,000 Rogue Trader/Bundles")
HEX = re.compile(rb"(?<![0-9a-f])[0-9a-f]{32}(?![0-9a-f])")


def load_pack():
    f = (BUNDLES / "blueprints-pack.bbp").open("rb")
    n = struct.unpack("<I", f.read(4))[0]
    ents = [(uuid.UUID(bytes_le=f.read(16)).hex, struct.unpack("<I", f.read(4))[0]) for _ in range(n)]
    data = f.read()
    base = f.tell() - len(data)
    order = sorted(ents, key=lambda e: e[1])
    refs = {}
    for i, (g, off) in enumerate(order):
        end = order[i + 1][1] if i + 1 < len(order) else base + len(data)
        blob = data[off - base:end - base]
        refs[g] = {m.decode() for m in HEX.findall(blob)} - {g}
    return refs


def main():
    meta = {}
    for e in json.load(open(BUNDLES / "cheatdata.json"))["Entries"]:
        meta[e["Guid"]] = (e["Name"], e["TypeFullName"].split(",")[0].split(".")[-1])
    refs = load_pack()
    print("blobs", len(refs), "with names", sum(g in meta for g in refs))
    out = ROOT / "data/chapter_map_graph.json"
    json.dump({"meta": {g: list(v) for g, v in meta.items()}, "refs": {g: sorted(r) for g, r in refs.items()}}, open(out, "w"))
    print("wrote", out)


if __name__ == "__main__":
    main()


CHAPTER = re.compile(r"^Chapter0([1-5])$")
CARRIERS = {"Cutscene", "CommandStartDialog", "ActionsHolder", "CommandAction", "BlueprintCue", "BlueprintAnswer", "BlueprintDialog",
            "BlueprintScriptZone", "BlueprintAnomaly", "BlueprintPointOfInterestBookEvent", "BlueprintBarkBanter", "ConditionsHolder",
            "BlueprintQuestObjective", "BlueprintQuest", "BlueprintAreaPreset"}


def chapter_of_etudes(meta, refs):
    """etude guid -> {chapter: distance}: forward walk over etude->etude references (a child lists its parent)."""
    chap = {g: int(m.group(1)) for g, (n, t) in meta.items() if t == "BlueprintEtude" and (m := CHAPTER.match(n))}
    cache = {}

    def walk(g):
        if g in cache:
            return cache[g]
        seen, frontier, found, d = {g}, [g], {}, 0
        while frontier and d < 10 and not found:
            nxt = []
            for x in frontier:
                if x in chap:
                    found[chap[x]] = d
                for r in refs.get(x, ()):
                    if r not in seen and meta.get(r, ("", ""))[1] == "BlueprintEtude":
                        seen.add(r)
                        nxt.append(r)
            frontier, d = nxt, d + 1
        cache[g] = found
        return found
    return walk


def dialog_chapters(meta, refs, max_up=4):
    rev = defaultdict(set)
    for g, rs in refs.items():
        for r in rs:
            rev[r].add(g)
    walk = chapter_of_etudes(meta, refs)
    out = {}
    for g, (n, t) in meta.items():
        if t != "BlueprintDialog":
            continue
        seen, frontier, hits = {g}, [g], {}
        for up in range(max_up):
            nxt = []
            for x in frontier:
                for r in rev.get(x, ()):
                    if r in seen:
                        continue
                    seen.add(r)
                    rt = meta.get(r, ("", ""))[1]
                    if rt == "BlueprintEtude":
                        for ch, dist in walk(r).items():
                            hits.setdefault(ch, []).append((up + dist, meta[r][0]))
                    elif rt in CARRIERS:
                        nxt.append(r)
            frontier = nxt
            if hits:
                break
        out[g] = {"name": n, "chapters": sorted(hits), "via": {str(c): sorted(v)[:3] for c, v in hits.items()}}
    return out


def build():
    meta = {}
    for e in json.load(open(BUNDLES / "cheatdata.json"))["Entries"]:
        meta[e["Guid"]] = (e["Name"], e["TypeFullName"].split(",")[0].split(".")[-1])
    return dialog_chapters(meta, load_pack())
