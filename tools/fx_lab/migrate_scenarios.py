#!/usr/bin/env python3
"""Turn scenarios.json and rt_preset_recipes.json into pedalboard starting-point graphs (starters/<slug>.json).

  tools/fx_lab/.venv-fx/bin/python tools/fx_lab/migrate_scenarios.py [--check]

Each scenario was a set of flat control keys on the one big chain. The graph keeps only the pedals the scenario touches (a pedal at its
defaults is transparent), in the old chain order, so a human can read what a sound is made of. A dry/wet Mix below 1 becomes a Mix 2 node
fed by the chain and by the raw input, with levels 20*log10(mix) and 20*log10(1-mix), which is exactly mix*chain + (1-mix)*raw as before.
Output is deterministic (sorted keys, indent 1); --check fails when a committed starter differs from a fresh generation.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
WEB = HERE.parent / "studio" / "web"
STARTERS = HERE / "starters"
CHAIN_ORDER = ["highpass", "lowpass", "deesser", "eq", "pitch", "harmonizer", "freqshift", "lowshelf", "vocoder", "compressor", "drive", "resonator", "metal",
               "comb", "bitcrush", "ringmod", "tremolo", "chorus", "wowflutter", "phaser", "dropout", "echo", "static", "reverb", "autopan", "stereochorus",
               "stereophaser", "bassspread"]
MIX_KEY = "Mix_0_raw_1_processed"
# A pedal is 220 px wide; its height is a title bar plus one row per control (measured in the browser: one control is 119 px). Rows wrap after
# PER_ROW pedals and each row starts below the tallest pedal of the one above, so nothing overlaps.
X_STEP, PER_ROW = 260, 6
NODE_WIDTH, HEAD_PX, ROW_PX, ROW_GAP = 220, 57, 62, 48
MIN_LEVEL_DB = -60.0                                  # the Mix 2 level knob's floor; mix 0 would be minus infinity
CATEGORY_ORDER = ["Clean", "Machine", "Vox", "Helmet", "Ethereal", "Monstrous", "Space", "Rogue Trader", "Test"]
CATEGORY_BY_WORD = {"Machine": "Machine", "Vox": "Vox", "Helmet": "Helmet", "Ethereal": "Ethereal", "Monstrous": "Monstrous", "Cavernous": "Space",
                    "Phaser": "Test", "Clean": "Clean"}


def short(label: str) -> str:
    """Control label -> flat key ('Ring Hz' -> 'Ring_Hz'); same rule as dd_render.short, kept here so this script needs no audio libraries."""
    return re.sub(r"[^A-Za-z0-9]+", "_", label).strip("_")


def category_of(name: str) -> str:
    """Category from the name prefix, ignoring a leading version tag ('v2 Machine: x' -> Machine); vocoder tests are Test."""
    words = re.sub(r"^v\d+\s+", "", name).split()
    first = words[0].rstrip(":") if words else ""
    if first == "Vocoder":
        return "Test"
    return CATEGORY_BY_WORD.get(first, "Test")


def slug_of(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def flat_index(catalog: dict) -> dict[str, tuple[dict, dict]]:
    """flat key -> (block, control) for every effect and output control (the Mix 2 level labels repeat across mixes and are not flat keys)."""
    out: dict[str, tuple[dict, dict]] = {}
    for b in catalog["blocks"]:
        if b["kind"] == "effect" or b["id"] == "output":
            for c in b["controls"]:
                out[short(c["label"])] = (b, c)
    return out


def node_height(block: dict) -> int:
    """Estimated on-screen height of a pedal: the title bar plus a row for every control except the stomp switch."""
    return HEAD_PX + ROW_PX * sum(1 for c in block["controls"] if c["label"] != block["stomp"])


class Layout:
    """Places nodes left to right after the input, wrapping after PER_ROW and clearing the tallest pedal of the row above."""

    def __init__(self) -> None:
        self.count, self.row_y, self.row_height = 0, 0, 0

    def place(self, height: int) -> tuple[int, int]:
        col = self.count % PER_ROW
        if self.count and col == 0:
            self.row_y += self.row_height + ROW_GAP
            self.row_height = 0
        self.row_height = max(self.row_height, height)
        self.count += 1
        return X_STEP * (1 + col), self.row_y


def build_graph(slug: str, params: dict, catalog: dict) -> dict:
    index = flat_index(catalog)
    by_block: dict[str, dict] = {}
    for key, value in params.items():
        if key == MIX_KEY:
            continue
        if key not in index:
            raise KeyError(f"{slug}: flat key {key!r} is not a control in the catalog")
        block, control = index[key]
        if value != control["init"]:
            by_block.setdefault(block["id"], {})[control["label"]] = value
    blocks = {b["id"]: b for b in catalog["blocks"]}
    touched = [b for b in CHAIN_ORDER if b in by_block]
    mix = float(params.get(MIX_KEY, 1))
    nodes: list[dict] = [{"id": "input", "type": "input", "x": 0, "y": 0}]
    edges: list[dict] = []
    prev = "input"
    lay = Layout()

    def wire(source: str, target: str, port: int = 0) -> None:
        edges.append({"id": f"e{len(edges) + 1}", "source": source, "target": target, "targetPort": port})

    for bid in touched:
        stomp = blocks[bid]["stomp"]
        values = dict(by_block[bid])
        on = values.pop(stomp, 1) != 0
        x, y = lay.place(node_height(blocks[bid]))
        nodes.append({"id": bid, "type": bid, "x": x, "y": y, "on": on, "params": values})
        wire(prev, bid)
        prev = bid
    last = prev
    if mix < 1:
        x, y = lay.place(node_height(blocks["mix2"]))
        level = lambda m: round(max(MIN_LEVEL_DB, 20 * math.log10(m)) if m > 0 else MIN_LEVEL_DB, 6)
        nodes.append({"id": "mix2", "type": "mix2", "x": x, "y": y, "params": {"Level A dB": level(mix), "Level B dB": level(1 - mix)}})
        wire(prev, "mix2", 0)
        wire("input", "mix2", 1)
        last = "mix2"
    x, y = lay.place(node_height(blocks["output"]))
    nodes.append({"id": "output", "type": "output", "x": x, "y": y, "params": by_block.get("output", {})})
    wire(last, "output")
    return {"version": 1, "name": slug, "nodes": nodes, "edges": edges}


def build_starters(scenarios: dict, recipes: dict, catalog: dict) -> dict[str, dict]:
    by_name = {s["name"]: s for s in scenarios["scenarios"]}
    entries = [(s["name"], s.get("desc", ""), category_of(s["name"]), s["params"]) for s in scenarios["scenarios"]]
    for r in recipes["recipes"]:
        entries.append((r["name"], r.get("desc", ""), "Rogue Trader", {**by_name[r["base"]]["params"], **r["set"]}))
    out: dict[str, dict] = {}
    for name, desc, category, params in entries:
        slug = slug_of(name)
        if slug in out:
            raise ValueError(f"two starters share the slug {slug!r}")
        out[slug] = {"name": name, "description": desc, "category": category, "graph": build_graph(slug, params, catalog)}
    return out


def dump(obj: dict) -> str:
    return json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def generate_all(graphs: dict[str, dict]) -> dict[str, dict]:
    """Run the TypeScript generator over named graphs in one process; returns {name: {code, controls, params} | {error: issues}}."""
    with tempfile.TemporaryDirectory() as td:
        paths = {}
        for name, g in graphs.items():
            paths[name] = Path(td) / f"{name}.json"
            paths[name].write_text(json.dumps(g), encoding="utf-8")
        r = subprocess.run(["npx", "vite-node", "../../fx_lab/gen_batch.ts", "--", *map(str, paths.values())], cwd=WEB, capture_output=True, text=True, timeout=600)
        if r.returncode != 0:
            raise RuntimeError(f"generator failed: {r.stderr[-2000:]}")
        out = json.loads(r.stdout)
        return {name: out[str(p)] for name, p in paths.items()}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="fail if a committed starter differs from a fresh generation")
    args = ap.parse_args()
    catalog = json.loads((HERE / "faust/catalog.json").read_text(encoding="utf-8"))
    starters = build_starters(json.loads((HERE / "scenarios.json").read_text(encoding="utf-8")),
                              json.loads((HERE / "rt_preset_recipes.json").read_text(encoding="utf-8")), catalog)
    texts = {slug: dump(s) for slug, s in starters.items()}
    if args.check:
        bad = [f"{slug}.json" for slug, t in texts.items() if not (STARTERS / f"{slug}.json").is_file() or (STARTERS / f"{slug}.json").read_text(encoding="utf-8") != t]
        extra = [p.name for p in STARTERS.glob("*.json") if p.stem not in texts] if STARTERS.is_dir() else []
        if bad or extra:
            print(f"starters out of date: differ or missing {bad}, not generated {extra}", file=sys.stderr)
            return 1
        print(f"{len(texts)} starters match a fresh generation")
        return 0
    STARTERS.mkdir(exist_ok=True)
    for slug, t in texts.items():
        (STARTERS / f"{slug}.json").write_text(t, encoding="utf-8")
    results = generate_all({slug: s["graph"] for slug, s in starters.items()})
    errors = {slug: r["error"] for slug, r in results.items() if "error" in r}
    for slug, e in errors.items():
        print(f"INVALID {slug}: {json.dumps(e)}", file=sys.stderr)
    print(f"wrote {len(texts)} starters to {STARTERS}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
