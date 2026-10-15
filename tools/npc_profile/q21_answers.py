#!/usr/bin/env python3
"""Record the answers to the 21 pending conversation questions in data/npc_profile/human_labels.json.

  python3 tools/npc_profile/q21_answers.py [--dry-run]

Sources: data/npc_profile/review/research/{identity,who_speaks,voicing}.json (three research passes, 2026-10-12). For each
conversation this sets status "reviewed", adds `voices` (roster id -> voice key in prompts.json, a pool_<slot> or "narrator"),
applies per-line speaker overrides (line numbers are the numbering of the review dump), and a `resolution` block with the
confidence and whether the voice choice is a guess. Guesses are listed so the in-game flag loop can find them later.
Back up human_labels.json before running (the first run is idempotent; re-running re-applies the same answers).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
from roster import conversation_lines  # noqa: E402

LABELS = ROOT / "data/npc_profile/human_labels.json"
VIGDIS = "Vox Master Vigdis"

# conversation -> {"voices": roster id -> voice, "lines": {dump line number: roster id}, "conf": ..., "guess": bool, "note": ...}
ANSWERS: dict[str, dict] = {
    "Ulfar_BE": {"voices": {"skald": "narrator"}, "conf": "medium", "guess": True,
                 "note": "one reciter for the whole saga (research); reciter unnamed, so the narrator voice"},
    "Captives_dialogue": {"voices": {"survivor_1": "pool_female_human", "survivor_2": "pool_male_human"},
                          "lines": {5: "survivor_2", 10: "survivor_2", 21: "survivor_1"}, "conf": "low", "guess": True,
                          "note": "5 and 10 the male scout, 21 the female scout"},
    "FW_Cogitator_dialogue": {"voices": {"young_nobleman": "pool_male_human_young", "grey_haired_nobleman": "pool_male_human_old"},
                              "lines": {13: "young_nobleman"}, "conf": "low", "guess": True, "note": "line 13 leans young nobleman"},
    "VP_PrefectTrial_dialogue": {"voices": {"vultur": "pool_female_human", "marshal_strachs": "Marshal Gregoras Strachs"},
                                 "lines": {n: "vultur" for n in (7, 8, 14, 15, 27, 37)}, "conf": "medium", "guess": False,
                                 "note": "the prefect reads the charges (line 15 high)"},
    "StryxShedCogitator_dialogue": {"voices": {"big_pugh": "pool_male_human", "pugh_crew": "pool_male_human"},
                                    "conf": "medium", "guess": True,
                                    "note": "multi-speaker lines 12-14 rendered in one crew voice (research fallback)"},
    "Anger_NowYouAreOk_dialogue": {"voices": {"malice": "pool_other"}, "conf": "high", "guess": False,
                                   "note": "Malice is male (high); xenos gladiator boss, so the 'other' slot"},
    "DoorGuard": {"voices": {"door_guard": "pool_male_human"}, "conf": "low", "guess": True, "note": "gender undetermined, male by default"},
    "Scrapcode_bookevent": {"voices": {"lord_captain": "pool_male_human", "bridge_officer": "pool_male_human",
                                       "enginseer": "pool_male_human", "voidborn_officer": "pool_male_human",
                                       "junior_attendant": "pool_male_human_young", "junior_officers": "pool_male_human_young",
                                       "abelard_werserian": "Abelard", "idira": "Idira", "vox_master": VIGDIS},
                            "conf": "high", "guess": False, "note": "long narration lines contain no quoted speech (high)"},
    "UralonFinal_dialogue": {"voices": {"uralon": "pool_male_human", "edge_of_daybreak": "pool_other", "psyber_raven": "pool_other"},
                             "lines": {**{n: "psyber_raven" for n in range(35, 43)}, 67: "uralon"}, "conf": "medium", "guess": True,
                             "note": "35-42 the raven in the daemon's voice; 67 unresolved, leaning Uralon"},
    "MawBreakthrough_BE": {"voices": {"sebullon_primix": "pool_male_human", "argenta": "Argenta", "priest": "pool_male_human"},
                           "conf": "low", "guess": True, "note": "chronicle stays narrator (a chronicler voice is optional)"},
    "ThirdBattleWon_dialogue": {"voices": {"monster_servitor": "pool_other", "monster_dry": "pool_other", "abomination": "pool_other",
                                           "achilleas_scalander": "pool_male_human"}, "conf": "medium", "guess": True,
                                "note": "the three monsters merged into one voice"},
    "EX_ChronoWatcher_dialogue": {"voices": {"chronomancer_amatekh": "pool_other"}, "conf": "high", "guess": False,
                                  "note": "the blocking Warden is Amatekh himself"},
    "Cassia_Q2_BE": {"voices": {"cassia": "Cassia", "tisiphone": "pool_female_human_old", "senior_enforcer": "pool_male_human",
                                "enforcer": "pool_male_human", "servant": "pool_male_human_young", "hideh": "pool_male_machine"},
                     "conf": "medium", "guess": True, "note": "multi-speaker lines split per speaker (segments.json); servant gender unknown"},
    "NewVoxMaster_dialogue_Jul_Fix": {"voices": {"new_vox_master": "pool_female_human"}, "conf": "low", "guess": True,
                                      "note": "undetermined; female to match Vigdis, probably her successor"},
    "StrangeServitors_BE": {"voices": {"pasqal": "High Factotum Janris Danrok"}, "all_lines": "pasqal", "conf": "medium", "guess": True,
                            "note": "report 'from the words of High Factotum Janris Danrok', first person: his designed voice"},
    "NecronFleet_prompt": {"voices": {"ravor": "Master Helmsman Ravor", "vox_master": VIGDIS, "vigdis": VIGDIS},
                           "lines": {n: "vigdis" for n in (14, 21, 22, 26, 29)}, "conf": "medium", "guess": False,
                           "note": "the Vox Master is Vigdis; 14, 21, 22, 26, 29 are hers"},
    "Darg_PersonalCogitator_dialogue": {"voices": {"ancestor": "pool_male_human_old"}, "conf": "medium", "guess": True,
                                        "note": "'Laria' is a password; the author is most likely Seberian (male), an inference"},
    "Skeletons_AncientTrapEE_dialog": {"voices": {"scout_1": "pool_male_human", "lookout": "pool_male_human_young"},
                                       "conf": "high", "guess": True, "note": "split per speaker; genders not stated, voices are a guess"},
    "VoxMasterFarewell_dialogue": {"voices": {"vox_master": VIGDIS}, "conf": "medium", "guess": True,
                                   "note": "the Vox Master; one variant may be the successor, default to Vigdis"},
    "IntBeg_Prompt": {"voices": {"visitor": "pool_male_human"}, "conf": "low", "guess": True, "note": "undetermined, male by default"},
    "TW_Arbites_dialogue": {"voices": {"yeager": "pool_female_human", "arbitrator": "pool_female_human"},
                            "lines": {131: "yeager", 138: "yeager", 141: "yeager"}, "conf": "high", "guess": False,
                            "note": "131, 138 and 141 are all Yeager; there is no separate Arbitrator"},
}


def line_numbers(name: str, entry: dict, convs: list[dict]) -> dict[int, str]:
    """dump line number -> text_key for the conversation holding this entry's lines."""
    keys = set(entry["lines"])
    for cv in convs:
        if keys & {ln.get("text_key") for ln in cv["lines"]}:
            return {l["n"]: l["key"] for l in conversation_lines(cv, keys) if l["key"] in keys}
    raise SystemExit(f"conversation for {name} not found")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    data = json.loads(LABELS.read_text(encoding="utf-8"))
    convs = json.loads((ROOT / "data/conversations.enGB.json").read_text(encoding="utf-8"))
    changed = 0
    for name, ans in ANSWERS.items():
        entry = data["conversations"][name]
        nums = line_numbers(name, entry, convs)
        for n, rid in ans.get("lines", {}).items():
            guid = nums.get(n)
            if guid is None:      # a player line or a line the game already attributes; nothing to override
                print(f"  {name}: line {n} is not an attributed line, skipped")
                continue
            if entry["lines"][guid]["speaker"] != rid:
                entry["lines"][guid].update(speaker=rid, confidence=ans["conf"], why=f"q21 research: {ans['note']}")
                changed += 1
        if "all_lines" in ans:    # every narrator line of the report becomes this speaker's
            for l in entry["lines"].values():
                if l["speaker"] == "NARRATOR":
                    l.update(speaker=ans["all_lines"], confidence=ans["conf"], why=f"q21 research: {ans['note']}")
                    changed += 1
        known = {r["id"] for r in entry["roster"]}
        missing = set(ans["voices"]) - known
        if missing:
            raise SystemExit(f"{name}: voices for unknown roster ids {missing}")
        entry.update(status="reviewed", voices=ans["voices"],
                     resolution={"confidence": ans["conf"], "guess": ans["guess"], "note": ans["note"],
                                 "source": "data/npc_profile/review/research/*.json, 2026-10-12"})
    print(f"{len(ANSWERS)} conversations resolved, {changed} line speakers changed; guesses: "
          f"{sorted(n for n, a_ in ANSWERS.items() if a_['guess'])}")
    if not a.dry_run:
        LABELS.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
        print("wrote", LABELS)


if __name__ == "__main__":
    main()
