#!/usr/bin/env python3
"""Turn the in-game dialogue export (script.json) into ordered conversations for annotation.

Input:  script.json from the DialogueExporter mod (dialogs / nodes / units), plus
        data/strings.<locale>.json from extract_localization.py (for the voiced flag).
Output: data/conversations.<locale>.json  - one entry per BlueprintDialog, lines in depth-first
                                             script order with speaker, text, edges and context
        data/conversations.<locale>.stats.md

Traversal follows the same edges the game does (see ToyBox PreviewManagerRT / CueSelection):
  dialog.first_cue -> cue.continue / cue.answers -> answer.next -> ...
  check.success / check.fail, sequence.cues (+ exit_continue), book_page.cues / answers,
  answers_list.answers.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


def load(path: Path):
    return json.load(open(path, encoding="utf-8"))


def outgoing(node: dict) -> list[tuple[str, str]]:
    """(edge_kind, target_guid) pairs in the order the script should be read."""
    out: list[tuple[str, str]] = []
    kind = node.get("type")
    if kind == "cue":
        for g in (node.get("continue") or {}).get("cues", []):
            out.append(("continue", g))
        for g in node.get("answers", []):
            out.append(("answer", g))
    elif kind == "answer":
        for g in (node.get("next") or {}).get("cues", []):
            out.append(("next", g))
    elif kind == "answers_list":
        for g in node.get("answers", []):
            out.append(("answer", g))
    elif kind == "check":
        if node.get("success"):
            out.append(("success", node["success"]))
        if node.get("fail"):
            out.append(("fail", node["fail"]))
    elif kind == "sequence":
        for g in node.get("cues", []):
            out.append(("seq", g))
        for g in (node.get("exit_continue") or {}).get("cues", []):
            out.append(("continue", g))
    elif kind == "book_page":
        for g in node.get("cues", []):
            out.append(("seq", g))
        for g in node.get("answers", []):
            out.append(("answer", g))
    return out


def speaker_info(node: dict, units: dict) -> dict | None:
    if node.get("type") != "cue":
        return None
    if node.get("is_narrator_text"):
        return {"kind": "narrator"}
    guid = node.get("speaker_guid") or node.get("speaker_portrait_guid")
    if not guid:
        # No speaker blueprint: the game substitutes the dialog's default speaker (the NPC that
        # started the conversation) at runtime, unless the cue was flagged NoSpeaker.
        return {"kind": "narrator" if node.get("no_speaker") else "default_speaker"}
    u = units.get(guid, {})
    return {
        "kind": "unit",
        "guid": guid,
        "name": u.get("character_name") or u.get("name"),
        "blueprint": u.get("name"),
        "gender": u.get("gender"),
        "race": u.get("race"),
    }


def walk_dialog(dialog: dict, nodes: dict, units: dict, voiced: dict, plain: dict | None = None) -> list[dict]:
    """Depth-first, following continue-before-answers, each node emitted once per dialog."""
    lines: list[dict] = []
    seen: set[str] = set()
    stack: list[tuple[str, str | None, str, int]] = []
    for g in reversed((dialog.get("first_cue") or {}).get("cues", [])):
        stack.append((g, None, "start", 0))
    while stack:
        guid, parent, via, depth = stack.pop()
        if guid in seen:
            lines.append({"ref": guid, "parent": parent, "via": via, "depth": depth})
            continue
        seen.add(guid)
        node = nodes.get(guid)
        if node is None:
            lines.append({"missing": guid, "parent": parent, "via": via, "depth": depth})
            continue
        line = {
            "guid": guid,
            "kind": node.get("type"),
            "parent": parent,
            "via": via,
            "depth": depth,
        }
        if node.get("text_key"):
            line["text_key"] = node["text_key"]
            line["text"] = node.get("text") or (plain.get(node["text_key"]) if plain else None)
            line["voiced"] = voiced.get(node["text_key"])
        if node.get("type") == "cue":
            line["speaker"] = speaker_info(node, units)
            line["animation"] = node.get("animation")
            if node.get("listener_guid"):
                line["listener"] = units.get(node["listener_guid"], {}).get("character_name")
        elif node.get("type") == "answer":
            line["speaker"] = {"kind": "player"}
            if node.get("show_check_stat"):
                line["check"] = node["show_check_stat"]
        elif node.get("type") == "check":
            line["stat"] = node.get("stat")
            line["difficulty"] = node.get("difficulty")
        if node.get("comment"):
            line["comment"] = node["comment"]
        lines.append(line)
        edges = outgoing(node)
        for kind, target in reversed(edges):
            stack.append((target, guid, kind, depth + 1))
    return lines


def resolve_default_speakers(conversations: list[dict], min_share: float = 0.6, min_votes: int = 2) -> dict:
    """Attribute 'default_speaker' cues (no explicit speaker blueprint - the game substitutes
    whoever the player is talking to) to a concrete NPC, per dialog.

    Signal: within one dialog, tally the explicit ("unit") speakers seen on other cues. If one
    name dominates (>= min_share of explicit-speaker cues, >= min_votes), every default_speaker
    cue in that dialog is attributed to them with provenance "dialog_majority". This only uses
    within-dialog evidence, so it's conservative by construction - a dialog split evenly between
    two NPCs' cues is correctly left unresolved rather than guessed.
    Mutates lines in place; returns resolution stats.
    """
    resolved = ambiguous = 0
    for conv in conversations:
        votes: Counter = Counter()
        for l in conv["lines"]:
            sp = l.get("speaker")
            if sp and sp.get("kind") == "unit" and sp.get("name"):
                votes[sp["name"]] += 1
        total = sum(votes.values())
        owner = None
        if total >= min_votes:
            name, n = votes.most_common(1)[0]
            if n / total >= min_share:
                owner = name
        for l in conv["lines"]:
            sp = l.get("speaker")
            if sp and sp.get("kind") == "default_speaker":
                if owner:
                    l["speaker"] = {"kind": "unit_guess", "name": owner, "provenance": "dialog_majority"}
                    resolved += 1
                else:
                    ambiguous += 1
    return {"resolved": resolved, "ambiguous": ambiguous}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("script", help="script.json produced by the DialogueExporter mod")
    ap.add_argument("--locale", default="enGB")
    ap.add_argument("--out", default=str(DATA))
    args = ap.parse_args()

    export = load(Path(args.script))
    nodes: dict = export["nodes"]
    units: dict = export["units"]
    strings_path = Path(args.out) / f"strings.{args.locale}.json"
    strings = load(strings_path) if strings_path.exists() else []
    voiced = {r["key"]: r["voiced"] for r in strings}
    plain = {r["key"]: r["text"] for r in strings}

    conversations = []
    reached: set[str] = set()
    for d in export["dialogs"]:
        lines = walk_dialog(d, nodes, units, voiced, plain)
        for ln in lines:
            if "guid" in ln:
                reached.add(ln["guid"])
        conversations.append({
            "guid": d["guid"],
            "name": d.get("name"),
            "type": d.get("type"),
            "is_narrator_text": d.get("is_narrator_text"),
            "comment": d.get("comment"),
            "lines": lines,
        })

    resolution = resolve_default_speakers(conversations)

    out_path = Path(args.out) / f"conversations.{args.locale}.json"
    out_path.write_text(json.dumps(conversations, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---- stats ---------------------------------------------------------------------------------
    kinds = Counter(n.get("type") for n in nodes.values())
    cues = [n for n in nodes.values() if n.get("type") == "cue" and n.get("text_key")]
    answers = [n for n in nodes.values() if n.get("type") == "answer" and n.get("text_key")]
    unreached = [g for g in nodes if g not in reached]
    voiced_cues = sum(1 for c in cues if voiced.get(c["text_key"]))
    by_speaker: Counter = Counter()
    chars = 0
    for c in cues:
        chars += len(c.get("text") or "")
    for conv in conversations:
        for l in conv["lines"]:
            if l.get("kind") != "cue" or not l.get("text_key"):
                continue
            sp = l.get("speaker") or {}
            by_speaker[sp.get("name") or sp.get("kind") or "?"] += 1
    anim = Counter(c.get("animation") for c in cues)
    stats = [
        f"# Conversation stats ({args.locale})",
        "",
        f"- dialogs: {len(conversations)}",
        f"- nodes: {len(nodes)} ({', '.join(f'{k}={v}' for k, v in kinds.most_common())})",
        f"- cues with text: {len(cues)}; voiced: {voiced_cues} ({100*voiced_cues/max(1,len(cues)):.1f}%)",
        f"- answers with text: {len(answers)}",
        f"- cue text chars: {chars:,} (~{chars//4:,} tokens)",
        f"- nodes not reachable from any dialog: {len(unreached)}",
        f"- units referenced: {len(units)}",
        f"- default_speaker cues resolved to an NPC by dialog majority: {resolution['resolved']} "
        f"(left ambiguous: {resolution['ambiguous']})",
        "",
        "## Cues per speaker (top 40, after default_speaker resolution)",
        "",
        *[f"- {name}: {n}" for name, n in by_speaker.most_common(40)],
        "",
        "## Cue animations",
        "",
        *[f"- {a}: {n}" for a, n in anim.most_common()],
    ]
    (Path(args.out) / f"conversations.{args.locale}.stats.md").write_text("\n".join(stats) + "\n", encoding="utf-8")
    print("\n".join(stats))
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
