import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "tools/render_corpus"), str(ROOT / "tools/bnk_patch")]

from plan_extra import classify, clean, skip_reason  # noqa: E402


def test_clean_strips_markup_and_quotes_and_dividers():
    assert clean('*** "Be {g|Encyclopedia:X}ware," he said.{br}\nNow.') == "Be ware, he said. Now."


def test_spaced_binary_is_decoded():
    assert clean("01000101 01111000 01100001 01101100 01110100 00100001") == "Exalt!"


def test_skip_reasons():
    assert skip_reason("Placeholder") == "junk"
    assert skip_reason("B573") == "one_letter"
    assert skip_reason("Недостаточный уровень доступа") == "no_latin_text"
    assert skip_reason("Rocky World") is None


def test_classify():
    assert classify("Rocky World", "Rocky World") == "short_name"
    assert classify("Over here quick.", '"Over here quick."') == "quoted"
    assert classify("x" * 1300, "x" * 1300) == "long"
    assert classify("A long ranged weapon that deals damage.", "A long ranged weapon that deals damage.") == "sentence"
