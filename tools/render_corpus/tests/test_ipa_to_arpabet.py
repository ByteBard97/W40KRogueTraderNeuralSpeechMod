import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/render_corpus"))

from ipa_to_arpabet import ipa_to_arpabet  # noqa: E402


def test_servitor():
    assert ipa_to_arpabet("ˈsɜːvɪtə") == "{S ER1 V IH0 T AH0}"


def test_secondary_stress_and_digraphs():
    assert ipa_to_arpabet("ˌɒmˈnɪsiːə") == "{AA2 M N IH1 S IY0 AH0}".replace("N IH1", "N IH1")
    assert ipa_to_arpabet("tʃaɪ") == "{CH AY1}"


def test_every_lexicon_entry_converts():
    d = json.load(open(ROOT / "data/lexicon/lexicon.json", encoding="utf-8"))
    for k, v in d.items():
        if not k.startswith("_"):
            assert ipa_to_arpabet(v["ipa"]).startswith("{"), k


def test_single_syllable_word_is_stressed():
    assert ipa_to_arpabet("vɒks") == "{V AA1 K S}"
