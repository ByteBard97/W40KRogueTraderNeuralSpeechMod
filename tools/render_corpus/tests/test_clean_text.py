import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from clean_text import clean_for_tts, is_terminal_log  # noqa: E402


def test_gender_templates_take_the_male_form():
    assert clean_for_tts("{rt_mf|He|She}'s a noble{rt_mf|man|woman} like {rt_mf|him|her}.") == "He's a nobleman like him."


def test_player_name_becomes_the_title_and_the_domin_apostrophe_goes():
    assert clean_for_tts("Thoughts of Domin'{rt_name} crowd my mind") == "Thoughts of Domin Lord Captain crowd my mind"
    assert clean_for_tts("conviction, Domin'Lord Captain, yet") == "conviction, Domin Lord Captain, yet"
    assert clean_for_tts("Yes, Lord Captain's order") == "Yes, Lord Captain's order"


def test_slash_alternatives_keep_first():
    s = "calling it into question. //Out of respect for//Due to lack of authorisation to indict// the followers, we will not proceed with the //detainment//arrest//termination//."
    assert clean_for_tts(s) == "calling it into question. Out of respect for the followers, we will not proceed with the detainment."


def test_log_markers_and_symbols():
    out = clean_for_tts("///[INPUT] || [Pack.comp.] ///nom_OS STAB TRUE ///sector 567>245 dam.")
    assert "/" not in out and "[" not in out and "|" not in out and ">" not in out and "_" not in out
    assert "INPUT" in out and "sector 567 245 dam." in out


def test_single_slashes_and_glitch_tildes():
    assert clean_for_tts("Freight Hub LD-987/A14, he/she said") == "Freight Hub LD-987 A14, he said"
    assert clean_for_tts("O Star~orn, he~r t~e pra~ers") == "O Starorn, her te praers"


def test_ordinary_text_untouched():
    s = 'You hear it: "Move along..." — then silence; nothing else.'
    assert clean_for_tts(s) == s


def test_spaced_division():
    assert clean_for_tts("gain (Awareness / 10)% chance") == "gain (Awareness divided by 10)% chance"


def test_terminal_log_detection():
    assert is_terminal_log("///[INPUT] || [Pack.comp.] ///nom_OS STAB TRUE")
    assert is_terminal_log("PROCESS: Linguistic analysis [Alg.54782136] STATUS: [Alg. 7458-14] done")
    assert not is_terminal_log("The candidate concluded a contract [data expunged] with barons.")
    assert not is_terminal_log("The Rogue Trader nods. //Yes//No// she says.")


def test_title_never_glued_to_neighbouring_letters():
    assert clean_for_tts("DearLord Captain, hello") == "Dear Lord Captain, hello"
    assert clean_for_tts("Lord Captainwill see you") == "Lord Captain will see you"
    assert clean_for_tts("Lord Captain's seal; \"Lord Captain\"!") == "Lord Captain's seal; \"Lord Captain\"!"
