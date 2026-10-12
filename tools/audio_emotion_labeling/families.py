"""Coarse emotion families for the forced-choice audio-LLM pilot (pilot 2).
Every word used in curation.json's Abelard labels is mapped; see FAMILY_OF."""
FAMILIES = {
    "stern": ["stern", "firm", "commanding", "measured", "matter-of-fact", "clinical",
              "insistent", "dutiful", "rallying", "fervent"],
    "warm": ["reassuring", "relieved", "hopeful", "grateful", "satisfied", "impressed"],
    "anxious": ["fear", "worried", "uneasy", "cautious", "guarded", "suspicious",
                "skeptical", "pleading"],
    "angry": ["exasperated", "annoyed", "impatience", "accusatory", "thundering", "admonishing"],
    "sad": ["solemn", "somber", "rueful", "regretful", "wistful", "weary", "grim",
            "reverent", "reverence", "pensive"],
    "surprised": ["incredulous", "surprised", "questioning"],
    "sardonic": ["sardonic", "dry", "amused", "contemptuous", "dismissive"],
    "other": ["neutral", "complex", "ambivalent"],
}
FAMILY_OF = {w: f for f, ws in FAMILIES.items() for w in ws}
DESCRIPTIONS = {
    "stern": "stern, formal, firm, commanding, dutiful, matter-of-fact",
    "warm": "warm, soft, reassuring, relieved, hopeful, grateful",
    "anxious": "anxious, afraid, worried, uneasy, wary, guarded, pleading",
    "angry": "angry, intense, exasperated, annoyed, accusatory, admonishing",
    "sad": "sad, somber, solemn, rueful, regretful, weary, grim, reverent",
    "surprised": "surprised, incredulous, questioning",
    "sardonic": "sardonic, dry, amused, contemptuous, dismissive",
    "other": "neutral or none of the above",
}
