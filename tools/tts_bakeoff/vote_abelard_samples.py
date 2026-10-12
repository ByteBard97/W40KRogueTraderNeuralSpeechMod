#!/usr/bin/env python3
"""Voting server for the Abelard emotion-matched TTS bake-off
(data/bakeoff_abelard_emotion_matched/manifest.json).

Adapted from tools/listening_test/serve.py's proven design (same Borda-style scoring, same
per-clip error tags, same vote persistence), pointed at this session's manifest.json layout
instead of the older data/bakeoff/<engine>/ + tts_test_set.json layout, and changed from "rank
every clip" to "pick your top 3" per the user's request - you click your #1/#2/#3 picks (in
order) and the vote submits automatically; a "Done" button lets you submit with fewer than 3
if you prefer, or the tie button if you can't distinguish any of them.

Scoring only awards points to picks actually made (3/2/1 for #1/#2/#3, same Borda idea as the
older tool) - clips not picked simply score 0, no special-casing needed.

Usage: python3 tools/tts_bakeoff/vote_abelard_samples.py [--port 8902]
Votes -> data/bakeoff_abelard_emotion_matched/votes.json (keyed by guid, re-voting overwrites).
"""
from __future__ import annotations

import argparse
import json
import os
import threading
import time
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

ROOT = Path(__file__).resolve().parent.parent.parent
OUT_ROOT = ROOT / "data/bakeoff_abelard_emotion_matched"
MANIFEST_PATH = OUT_ROOT / "manifest.json"
VOTES_PATH = OUT_ROOT / "votes.json"
STATIC_DIR = Path(__file__).resolve().parent
SCRATCH_DIR = OUT_ROOT / "_qwen3_timbre_test"
SWEEP_ROOT = ROOT / "data/bakeoff_abelard_cfg_sweep"
SWEEP_MANIFEST_PATH = SWEEP_ROOT / "manifest.json"
SWEEP_WAV_DIR = SWEEP_ROOT / "wav"
SWEEP_RATINGS_PATH = SWEEP_ROOT / "ratings.json"
RATING_DIMS = {"emotion", "voice"}
RATING_VALUES = {1, 2, 3, 4, 5, None}
# Discrete failure tags per clip, stored apart from the 1-5 scores (tags.json) so the
# ratings.json schema the analysis script reads stays {cell_id: {dim: score}}.
SWEEP_TAGS_PATH = SWEEP_ROOT / "tags.json"
FAILURE_TAGS = {
    "gravelly": "gravelly", "whisper": "whisper", "high": "too high",
    "rhotic": "rhotic R", "rushed": "rushed", "other": "other",
}
# 1 (red, bad) -> 5 (green, good) - shared by the sweep page's buttons and any future rating UI.
RATING_COLORS = {1: "#7f1d1d", 2: "#c2410c", 3: "#a16207", 4: "#4d7c0f", 5: "#15803d"}

_ratings_lock = threading.Lock()


def load_sweep_ratings() -> dict:
    if not SWEEP_RATINGS_PATH.exists():
        return {}
    return json.loads(SWEEP_RATINGS_PATH.read_text(encoding="utf-8"))


def save_sweep_ratings(ratings: dict) -> None:
    SWEEP_ROOT.mkdir(parents=True, exist_ok=True)
    tmp = SWEEP_RATINGS_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(ratings, indent=2), encoding="utf-8")
    os.replace(tmp, SWEEP_RATINGS_PATH)

def load_sweep_tags() -> dict:
    if not SWEEP_TAGS_PATH.exists():
        return {}
    return json.loads(SWEEP_TAGS_PATH.read_text(encoding="utf-8"))


def save_sweep_tags(tags: dict) -> None:
    SWEEP_ROOT.mkdir(parents=True, exist_ok=True)
    tmp = SWEEP_TAGS_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(tags, indent=2), encoding="utf-8")
    os.replace(tmp, SWEEP_TAGS_PATH)


# Scratch filenames don't consistently encode which dialogue line they're for (ad-hoc names
# from a debugging session, not a naming convention) - map filename prefixes to the guid they
# were generated for, by hand, so the /scratch page can group them under the same line
# structure the main voting page uses instead of one flat list.
SCRATCH_LINE_MAP = {
    "1_current_fix_joined_quotes": "03267eb7-0120-44fb-b0b5-024df2a0a867",
    "2_second_quote_only": "03267eb7-0120-44fb-b0b5-024df2a0a867",
    "3_x_vector_only_no_icl_text": "03267eb7-0120-44fb-b0b5-024df2a0a867",
    "4_altref_BNTRS_Chapter3_Abelard_10": "03267eb7-0120-44fb-b0b5-024df2a0a867",
    "4_altref_PRL_IdiraRecruit_19": "03267eb7-0120-44fb-b0b5-024df2a0a867",
    "5_altref_indignant_bf3ee630": "bf3ee630-ef78-451b-8a05-b08e0a0709c4",
    "5_altref_surprised_81dac0aa": "81dac0aa-dec3-4390-957c-cdcca5965873",
    "6_xvec_Chapter3_Abelard_10": "03267eb7-0120-44fb-b0b5-024df2a0a867",
    "6_xvec_IdiraRecruit_19": "03267eb7-0120-44fb-b0b5-024df2a0a867",
    "6_xvec_orig_ref": "03267eb7-0120-44fb-b0b5-024df2a0a867",
    "7_xvec_vladaym": "1c796994-4a41-4b17-8781-8e9f557f07c2",
    "8_full_original_text": "1c796994-4a41-4b17-8781-8e9f557f07c2",
    "8_quote_only_CURRENT": "1c796994-4a41-4b17-8781-8e9f557f07c2",
    "9_vladaym_dime_test": "1c796994-4a41-4b17-8781-8e9f557f07c2",
    "10_vladdime_trial0": "1c796994-4a41-4b17-8781-8e9f557f07c2",
    "10_vladdime_trial1": "1c796994-4a41-4b17-8781-8e9f557f07c2",
    "11_voxcpm2_take0": "81dac0aa-dec3-4390-957c-cdcca5965873",
    "11_voxcpm2_take1": "81dac0aa-dec3-4390-957c-cdcca5965873",
    "11_voxcpm2_take2": "81dac0aa-dec3-4390-957c-cdcca5965873",
    "12_voxcpm2_skeptical_take0": "ea8e726f-ddf0-4f5f-bf8f-8ad7d47ff8b8",
    "12_voxcpm2_skeptical_take1": "ea8e726f-ddf0-4f5f-bf8f-8ad7d47ff8b8",
    "12_voxcpm2_skeptical_take2": "ea8e726f-ddf0-4f5f-bf8f-8ad7d47ff8b8",
    "13_voxcpm2_fear_bfe47a42_take0": "bfe47a42-4849-41e9-af32-3169a2f01dc3",
    "13_voxcpm2_fear_bfe47a42_take1": "bfe47a42-4849-41e9-af32-3169a2f01dc3",
    "13_voxcpm2_fear_bfe47a42_take2": "bfe47a42-4849-41e9-af32-3169a2f01dc3",
    "13_voxcpm2_grateful_f10c2390_take0": "f10c2390-9b03-4351-b6cb-30cbe2ac0f65",
    "13_voxcpm2_grateful_f10c2390_take1": "f10c2390-9b03-4351-b6cb-30cbe2ac0f65",
    "13_voxcpm2_grateful_f10c2390_take2": "f10c2390-9b03-4351-b6cb-30cbe2ac0f65",
    "13_voxcpm2_relieved_03267eb7_take0": "03267eb7-0120-44fb-b0b5-024df2a0a867",
    "13_voxcpm2_relieved_03267eb7_take1": "03267eb7-0120-44fb-b0b5-024df2a0a867",
    "13_voxcpm2_relieved_03267eb7_take2": "03267eb7-0120-44fb-b0b5-024df2a0a867",
    "14_voxcpm2_instruct_toned_down_v1": "bfe47a42-4849-41e9-af32-3169a2f01dc3",
    "14_voxcpm2_instruct_toned_down_v2": "bfe47a42-4849-41e9-af32-3169a2f01dc3",
    "15_voxcpm2_astartia_altref_take0": "f10c2390-9b03-4351-b6cb-30cbe2ac0f65",
    "15_voxcpm2_astartia_altref_take1": "f10c2390-9b03-4351-b6cb-30cbe2ac0f65",
    "15_voxcpm2_astartia_altref_take2": "f10c2390-9b03-4351-b6cb-30cbe2ac0f65",
    "16_voxcpm2_cfg2.0_take0": "81dac0aa-dec3-4390-957c-cdcca5965873",
    "16_voxcpm2_cfg2.0_take1": "81dac0aa-dec3-4390-957c-cdcca5965873",
    "16_voxcpm2_cfg2.5_take0": "81dac0aa-dec3-4390-957c-cdcca5965873",
    "16_voxcpm2_cfg2.5_take1": "81dac0aa-dec3-4390-957c-cdcca5965873",
    "16_voxcpm2_cfg3.0_take0": "81dac0aa-dec3-4390-957c-cdcca5965873",
    "16_voxcpm2_cfg3.0_take1": "81dac0aa-dec3-4390-957c-cdcca5965873",
}
ERROR_TAGS = {
    "mispronunciation", "wrong_words", "garbled", "wrong_emotion", "wrong_accent",
    "voice_mismatch", "artifact", "other",
}

_votes_lock = threading.Lock()


def load_manifest_by_guid() -> dict[str, dict]:
    if not MANIFEST_PATH.exists():
        return {}
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    by_guid: dict[str, dict] = {}
    for entry in manifest.values():
        guid = entry["guid"]
        g = by_guid.setdefault(guid, {
            "text": entry["text"], "annotation": entry["annotation"],
            "reference": entry["reference"], "engines": {},
        })
        g["engines"][entry["engine"]] = entry
    return by_guid


def load_votes() -> dict:
    if not VOTES_PATH.exists():
        return {}
    return json.loads(VOTES_PATH.read_text(encoding="utf-8"))


def save_votes(votes: dict) -> None:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    tmp = VOTES_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(votes, indent=2), encoding="utf-8")
    os.replace(tmp, VOTES_PATH)


def compute_tally(votes: dict) -> dict:
    """Points: #1 pick = 3, #2 = 2, #3 = 1 (only for picks actually made). Same Borda idea as
    tools/listening_test/serve.py, just fixed at a 3-slot top-N instead of a full ranking."""
    points: Counter = Counter()
    firsts: Counter = Counter()
    picked_n: Counter = Counter()
    ties = 0
    for v in votes.values():
        if v.get("tie"):
            ties += 1
            continue
        picks = v.get("picks") or []
        for idx, engine in enumerate(picks):
            points[engine] += len(picks) - idx  # #1 of N picks scores N, ... last pick scores 1
            picked_n[engine] += 1
            if idx == 0:
                firsts[engine] += 1
    engines = sorted(set(points) | set(picked_n), key=lambda e: -points[e])
    return {
        "standings": [
            {"engine": e, "points": points[e], "first_place": firsts[e], "n": picked_n[e]}
            for e in engines
        ],
        "ties": ties,
        "n_votes": len(votes),
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send_json(self, obj, status=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/" or path == "/index.html":
            return self._serve_static("vote.html", "text/html")
        if path == "/items":
            return self._items()
        if path == "/tally":
            return self._tally()
        if path == "/export":
            return self._export()
        if path == "/wav":
            return self._wav()
        if path == "/scratch":
            return self._scratch()
        if path == "/scratch_wav":
            return self._scratch_wav()
        if path == "/sweep":
            return self._sweep()
        if path == "/sweep_wav":
            return self._sweep_wav()
        if path == "/sweep_tags":
            with _ratings_lock:
                return self._send_json(load_sweep_tags())
        if path == "/sweep_ratings":
            with _ratings_lock:
                return self._send_json(load_sweep_ratings())
        self.send_error(404)

    def _serve_static(self, name, content_type):
        data = (STATIC_DIR / name).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _items(self):
        by_guid = load_manifest_by_guid()
        with _votes_lock:
            saved_votes = load_votes()
        all_engines = sorted({e for g in by_guid.values() for e in g["engines"]})
        items = []
        for guid, g in by_guid.items():
            clips = []
            default_instruct = g["annotation"].get("instruct")
            for engine in all_engines:
                entry = g["engines"].get(engine)
                if entry and "error" not in entry:
                    clip = {"engine": engine, "url": f"/wav?path={entry['wav_path']}"}
                    clip_instruct = entry["annotation"].get("instruct")
                    # Different variants can now carry their own instruct text (delivery-
                    # mechanics rewrites, toned-down wording tests, etc.) - only surface it
                    # per-clip when it actually diverges from the line's default, so most
                    # clips stay uncluttered.
                    if clip_instruct and clip_instruct != default_instruct:
                        clip["instruct"] = clip_instruct
                    clips.append(clip)
            if len(clips) < 2:
                continue
            ann = g["annotation"]
            ref = g["reference"]
            ref_rel = str(Path(ref["wav"]).resolve().relative_to(ROOT))
            items.append({
                "id": guid, "text": g["text"],
                "direction": {"instruct": ann.get("instruct"), "emotion": ann.get("emotion"),
                              "intensity": ann.get("intensity"), "nonverbal": ann.get("nonverbal") or []},
                "reference": {"url": f"/wav?path={ref_rel}", "text": ref["text"],
                              "match_note": ("exact match" if ref["exact_match"]
                                             else f"nearest neighbor, real emotion '{ref['matched_emotion']}'")},
                "clips": clips,
                "saved": saved_votes.get(guid),
            })
        self._send_json({"items": items})

    def _wav(self):
        q = parse_qs(urlparse(self.path).query)
        rel = unquote(q.get("path", [""])[0])
        full = (ROOT / rel).resolve()
        if not str(full).startswith(str(ROOT)) or not full.is_file():
            return self.send_error(404)
        data = full.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _scratch(self):
        # Ad-hoc listening page for one-off comparison clips dropped in SCRATCH_DIR during
        # debugging/curation (not part of the formal manifest/voting flow) - lets you audition
        # them with a click instead of the native file browser + media player. Grouped by
        # dialogue line (same "Line N" numbering the main voting page uses) via
        # SCRATCH_LINE_MAP, since these ad-hoc filenames don't consistently encode which line
        # they're for on their own.
        by_guid = load_manifest_by_guid()
        line_info = {}  # guid -> (line_num, emotion, text)
        for i, (guid, g) in enumerate(by_guid.items(), start=1):
            line_info[guid] = (i, g["annotation"].get("emotion"), g["text"])

        files = sorted(SCRATCH_DIR.glob("*.wav"), key=lambda p: p.name)
        groups: dict[str | None, list[Path]] = {}
        for f in files:
            guid = SCRATCH_LINE_MAP.get(f.stem)
            groups.setdefault(guid, []).append(f)

        def sort_key(guid):
            return (line_info[guid][0] if guid in line_info else 9999)

        sections = []
        for guid in sorted(groups, key=sort_key):
            group_files = groups[guid]
            if guid and guid in line_info:
                n, emotion, text = line_info[guid]
                heading = f'Line {n} &middot; <span class="emo">[{emotion}]</span> &ldquo;{text}&rdquo;'
            else:
                heading = "Ungrouped / general tests"
            rows = "\n".join(
                f'<div class="row"><div class="name">{f.name}</div>'
                f'<audio controls preload="none" src="/scratch_wav?name={quote(f.name)}"></audio></div>'
                for f in group_files
            )
            sections.append(f'<h2>{heading}</h2>\n<div class="group">{rows}</div>')

        body = f"""<!doctype html><html><head><meta charset="utf-8">
<title>Scratch listening</title>
<style>
body {{ background:#0f1115; color:#e5e7eb; font-family:system-ui,sans-serif; padding:24px; }}
.row {{ display:flex; align-items:center; gap:16px; padding:8px 0; border-bottom:1px solid #262a33; }}
.name {{ flex: 0 0 420px; font-size:13px; color:#cbd5e1; word-break:break-all; }}
audio {{ flex:1; height:32px; }}
h1 {{ font-size:18px; }}
h2 {{ font-size:14px; color:#facc15; margin:28px 0 6px; font-weight:600; }}
.emo {{ color:#94a3b8; font-weight:400; }}
.group {{ margin-bottom:4px; }}
</style></head><body>
<h1>Scratch listening ({len(files)} files in {SCRATCH_DIR.name}/)</h1>
{"".join(sections)}
</body></html>"""
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _scratch_wav(self):
        q = parse_qs(urlparse(self.path).query)
        name = unquote(q.get("name", [""])[0])
        full = (SCRATCH_DIR / name).resolve()
        if not str(full).startswith(str(SCRATCH_DIR)) or not full.is_file():
            return self.send_error(404)
        data = full.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _sweep(self):
        # Playback page for the cfg_value sweep (tools/tts_bakeoff/sweep_voxcpm2_cfg.py):
        # 19 lines x {1.5, 2.0, 2.5, 3.0} cfg_value x 3 repeats, inference_timesteps fixed at 10.
        # Re-reads the sweep manifest on every request, so this stays live while the sweep script
        # is still rendering in the background - refresh the page to see new clips land.
        by_guid = load_manifest_by_guid()
        line_info = {}  # guid -> (line_num, emotion, text, ref_url, ref_text)
        for i, (guid, g) in enumerate(by_guid.items(), start=1):
            ref = g["reference"]
            ref_rel = str(Path(ref["wav"]).resolve().relative_to(ROOT))
            line_info[guid] = {
                "n": i, "emotion": g["annotation"].get("emotion"), "text": g["text"],
                "ref_url": f"/wav?path={ref_rel}",
                "default_entry": g["engines"].get("voxcpm2"),
            }

        sweep_entries = []
        if SWEEP_MANIFEST_PATH.exists():
            sweep_entries = json.loads(SWEEP_MANIFEST_PATH.read_text(encoding="utf-8"))

        by_line: dict[str, dict] = {}
        for e in sweep_entries:
            cell = by_line.setdefault(e["guid"], {})
            cell.setdefault(e["cfg_value"], {})[e["repeat"]] = e

        cfg_values = sorted({e["cfg_value"] for e in sweep_entries}) or [1.5, 2.0, 2.5, 3.0]
        repeats = sorted({e["repeat"] for e in sweep_entries}) or [0, 1, 2]
        n_expected = len(line_info) * len(cfg_values) * len(repeats)

        def score_buttons(dim):
            btns = "".join(
                f'<button class="score" data-dim="{dim}" data-val="{v}" '
                f'style="--score-color:{RATING_COLORS[v]}">{v}</button>'
                for v in (1, 2, 3, 4, 5)
            )
            return f'<span class="rate-label">{dim}</span><span class="score-group">{btns}</span>'

        tag_buttons = "".join(
            f'<button class="tag" data-tag="{k}">{label}</button>'
            for k, label in FAILURE_TAGS.items()
        )

        def rating_html(cell_id):
            return (
                f'<div class="rate-row" data-cell="{cell_id}">'
                f'{score_buttons("emotion")}{score_buttons("voice")}'
                f'</div>'
                f'<div class="tag-row" data-cell="{cell_id}">{tag_buttons}</div>'
            )

        def cell_html(guid, cfg):
            cells = by_line.get(guid, {}).get(cfg, {})
            parts = []
            for r in repeats:
                e = cells.get(r)
                if e:
                    label = f"r{r} &middot; {e['audio_seconds']}s"
                    parts.append(
                        f'<div class="take"><div class="take-label">{label}</div>'
                        f'<audio controls preload="none" '
                        f'src="/sweep_wav?path={quote(e["wav_path"])}"></audio>'
                        f'{rating_html(e["cell_id"])}</div>')
                else:
                    parts.append(f'<div class="take pending"><div class="take-label">r{r}</div>'
                                  f'<div class="pending-txt">pending&hellip;</div></div>')
            return "".join(parts)

        sections = []
        for guid in sorted(line_info, key=lambda g: line_info[g]["n"]):
            info = line_info[guid]
            default_entry = info["default_entry"]
            default_html = ""
            if default_entry and "error" not in default_entry:
                default_html = (
                    '<div class="take"><div class="take-label">current default (cfg 2.0, prod instruct)</div>'
                    f'<audio controls preload="none" src="/wav?path={default_entry["wav_path"]}"></audio></div>')
            cols = "".join(
                f'<div class="col"><div class="col-head">cfg {cfg}</div>{cell_html(guid, cfg)}</div>'
                for cfg in cfg_values
            )
            sections.append(f"""
<section class="line">
  <h2>Line {info['n']} &middot; <span class="emo">[{info['emotion']}]</span> &ldquo;{info['text']}&rdquo;</h2>
  <div class="refrow">
    <div class="take"><div class="take-label">reference (real actor)</div>
      <audio controls preload="none" src="{info['ref_url']}"></audio></div>
    {default_html}
  </div>
  <div class="grid">{cols}</div>
</section>""")

        n_done = len(sweep_entries)
        body = f"""<!doctype html><html><head><meta charset="utf-8">
<title>VoxCPM2 cfg_value sweep</title>
<style>
body {{ background:#0f1115; color:#e5e7eb; font-family:system-ui,sans-serif; padding:24px; }}
h1 {{ font-size:18px; }}
.progress {{ color:#94a3b8; font-size:13px; margin-bottom:20px; }}
.line {{ border-top:1px solid #262a33; padding:18px 0; }}
h2 {{ font-size:15px; margin:0 0 10px; }}
.emo {{ color:#94a3b8; font-weight:400; }}
.refrow {{ display:flex; gap:20px; margin-bottom:14px; flex-wrap:wrap; }}
.grid {{ display:flex; gap:14px; flex-wrap:wrap; }}
.col {{ background:#171a21; border-radius:8px; padding:10px; min-width:220px; flex:1; }}
.col-head {{ color:#facc15; font-size:13px; font-weight:600; margin-bottom:8px; }}
.take {{ margin-bottom:8px; }}
.take-label {{ font-size:11px; color:#94a3b8; margin-bottom:2px; }}
.take.pending {{ opacity:0.5; }}
.pending-txt {{ font-size:12px; }}
audio {{ width:100%; height:30px; }}
a {{ color:#facc15; }}
.rate-row {{ display:flex; align-items:center; gap:6px; margin-top:6px; flex-wrap:wrap; }}
.rate-label {{ font-size:10px; color:#64748b; text-transform:uppercase; letter-spacing:0.03em; }}
.score-group {{ display:flex; gap:3px; margin-right:8px; }}
.score {{
  background:#0f1115; border:1px solid #262a33; color:#94a3b8; border-radius:4px;
  width:22px; height:22px; font-size:12px; font-weight:600; cursor:pointer; padding:0;
  line-height:1; display:flex; align-items:center; justify-content:center;
}}
.score:hover {{ border-color:#64748b; }}
.score.active {{ background:var(--score-color); border-color:var(--score-color); color:#f8fafc; }}
.tag-row {{ display:flex; gap:4px; margin-top:4px; flex-wrap:wrap; }}
.tag {{
  background:#0f1115; border:1px solid #262a33; color:#94a3b8; border-radius:4px;
  font-size:11px; padding:2px 6px; cursor:pointer;
}}
.tag:hover {{ border-color:#64748b; }}
.tag.active {{ background:#7f1d1d; border-color:#b91c1c; color:#f8fafc; }}
.legend {{ font-size:12px; color:#94a3b8; margin-bottom:18px; display:flex; align-items:center; gap:8px; flex-wrap:wrap; }}
.legend-swatch {{
  display:inline-flex; align-items:center; justify-content:center; width:18px; height:18px;
  border-radius:3px; color:#f8fafc; font-size:11px; font-weight:600;
}}
</style></head><body>
<h1>VoxCPM2 cfg_value sweep</h1>
<div class="progress">{n_done} / {n_expected} clips rendered &middot;
cfg_value &isin; {cfg_values}, inference_timesteps fixed, {len(repeats)} repeats/cell &middot;
reload page for new clips &middot; <a href="/">back to main vote</a> &middot;
<span id="ratingSummary"></span></div>
<div class="legend">Rate each clip 1-5 on <b>emotion</b> (delivers the intended emotion) and
<b>voice</b> (sounds like Abelard):
{"".join(f'<span class="legend-swatch" style="background:{RATING_COLORS[v]}">{v}</span>' for v in (1,2,3,4,5))}
<span style="color:#64748b;">(1 = bad &middot; 5 = good)</span>
&middot; tick a <b>failure tag</b> when you hear that problem (lines rated before tags existed have none)</div>
{"".join(sections)}
<script>
async function loadRatings() {{
  const resp = await fetch('/sweep_ratings');
  const ratings = await resp.json();
  document.querySelectorAll('.rate-row').forEach(row => {{
    const cellId = row.dataset.cell;
    const r = ratings[cellId] || {{}};
    row.querySelectorAll('.score').forEach(btn => {{
      const dim = btn.dataset.dim, val = parseInt(btn.dataset.val, 10);
      btn.classList.toggle('active', r[dim] === val);
    }});
  }});
  const tags = await (await fetch('/sweep_tags')).json();
  document.querySelectorAll('.tag-row').forEach(row => {{
    const on = tags[row.dataset.cell] || [];
    row.querySelectorAll('.tag').forEach(b => b.classList.toggle('active', on.includes(b.dataset.tag)));
  }});
  let nRated = Object.keys(ratings).length;
  document.getElementById('ratingSummary').textContent = `${{nRated}} clips rated so far`;
}}

document.querySelectorAll('.score').forEach(btn => {{
  btn.addEventListener('click', async () => {{
    const row = btn.closest('.rate-row');
    const cellId = row.dataset.cell;
    const dim = btn.dataset.dim;
    const val = parseInt(btn.dataset.val, 10);
    const wasActive = btn.classList.contains('active');
    const newVal = wasActive ? null : val;
    row.querySelectorAll(`.score[data-dim="${{dim}}"]`).forEach(b => b.classList.remove('active'));
    if (newVal !== null) btn.classList.add('active');
    await fetch('/sweep_rate', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{cell_id: cellId, dim, value: newVal}}),
    }});
    loadRatings();
  }});
}});

document.querySelectorAll('.tag').forEach(btn => {{
  btn.addEventListener('click', async () => {{
    const on = !btn.classList.contains('active');
    btn.classList.toggle('active', on);
    await fetch('/sweep_tag', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{cell_id: btn.closest('.tag-row').dataset.cell, tag: btn.dataset.tag, on}}),
    }});
  }});
}});

loadRatings();
</script>
</body></html>"""
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _sweep_wav(self):
        q = parse_qs(urlparse(self.path).query)
        rel = unquote(q.get("path", [""])[0])
        full = (ROOT / rel).resolve()
        if not str(full).startswith(str(SWEEP_WAV_DIR)) or not full.is_file():
            return self.send_error(404)
        data = full.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _tally(self):
        with _votes_lock:
            votes = load_votes()
        self._send_json(compute_tally(votes))

    def _export(self):
        with _votes_lock:
            votes = load_votes()
        body = json.dumps(list(votes.values()), indent=2).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Disposition", 'attachment; filename="abelard_votes.json"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/vote":
            return self._post_vote()
        if path == "/sweep_rate":
            return self._post_sweep_rate()
        if path == "/sweep_tag":
            return self._post_sweep_tag()
        return self.send_error(404)

    def _post_vote(self):
        length = int(self.headers.get("Content-Length", 0))
        try:
            vote = json.loads(self.rfile.read(length))
        except json.JSONDecodeError:
            return self.send_error(400)
        required = {"id", "order"}
        if not required.issubset(vote):
            return self.send_error(400)
        if vote.get("tie"):
            vote["picks"] = None
        else:
            picks = vote.get("picks")
            if not picks or len(picks) > 3 or not set(picks) <= set(vote["order"]) or len(set(picks)) != len(picks):
                return self.send_error(400)
        for entry in vote.get("clip_errors", []):
            if not set(entry.get("tags", [])) <= ERROR_TAGS:
                return self.send_error(400)
        vote["ts"] = time.time()
        with _votes_lock:
            votes = load_votes()
            votes[vote["id"]] = vote
            save_votes(votes)
        self._send_json({"ok": True})

    def _post_sweep_tag(self):
        # Toggle one failure tag on a clip. tags.json: {cell_id: [tag, ...]}.
        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length))
        except json.JSONDecodeError:
            return self.send_error(400)
        cell_id, tag, on = body.get("cell_id"), body.get("tag"), body.get("on")
        if not cell_id or tag not in FAILURE_TAGS or not isinstance(on, bool):
            return self.send_error(400)
        with _ratings_lock:
            tags = load_sweep_tags()
            current = set(tags.get(cell_id, []))
            current.add(tag) if on else current.discard(tag)
            if current:
                tags[cell_id] = sorted(current)
            else:
                tags.pop(cell_id, None)
            save_sweep_tags(tags)
        self._send_json({"ok": True})

    def _post_sweep_rate(self):
        # Thumbs up/down on each cfg-sweep clip, on two independent dimensions: does it deliver
        # the target emotion, and does it sound like Abelard (voice/timbre match). Keyed by the
        # sweep manifest's cell_id (guid_cfgX_tsY_rZ) so ratings survive re-reading the sweep
        # manifest and can be joined back to cfg_value/repeat for pattern analysis afterward.
        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length))
        except json.JSONDecodeError:
            return self.send_error(400)
        cell_id = body.get("cell_id")
        dim = body.get("dim")
        value = body.get("value")
        if not cell_id or dim not in RATING_DIMS or value not in RATING_VALUES:
            return self.send_error(400)
        with _ratings_lock:
            ratings = load_sweep_ratings()
            entry = ratings.setdefault(cell_id, {})
            if value is None:
                entry.pop(dim, None)
                if not entry:
                    ratings.pop(cell_id, None)
            else:
                entry[dim] = value
            save_sweep_ratings(ratings)
        self._send_json({"ok": True})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8902)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()

    if not MANIFEST_PATH.exists():
        raise SystemExit(f"no manifest at {MANIFEST_PATH} - run the bake-off generation first")

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Abelard voting running at http://{args.host}:{args.port} (Ctrl+C to stop)")
    print(f"Votes -> {VOTES_PATH}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
