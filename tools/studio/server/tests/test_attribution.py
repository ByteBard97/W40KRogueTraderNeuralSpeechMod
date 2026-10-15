import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from conftest import make_repo, put  # noqa: E402
from studio_server import attribution as A  # noqa: E402

KNOWN = ["Pasqal", "Jae", "Theodora", "Edelthrad", "Kunrad Voigtvir", "Mort", "Trazyn, Lord of Histories"]


def test_companion_conversations_named_by_job_or_a_spelling_variant_belong_to_that_companion():
    assert A.attribute("Companions_Techpriest_12", [], KNOWN) == ("Pasqal", "conversation name")
    assert A.attribute("Companions_Smugler_150", [], KNOWN)[0] == "Jae"
    assert A.attribute("BNTRS_Chapter2_Pascal_04", [], KNOWN)[0] == "Pasqal"
    assert A.attribute("BNTRS_Companion_DLC3_Eogann_9", [], KNOWN)[0] == "Eogunn"
    assert A.attribute("Companions_Sororitas_73", [], KNOWN)[0] == "Argenta"


def test_a_conversation_named_for_a_character_belongs_to_that_character():
    assert A.attribute("PRL_TheodoraFirstConversation_40", [], KNOWN)[0] == "Theodora"
    assert A.attribute("PRL_KunradReveal_3", [], KNOWN)[0] == "Kunrad Voigtvir"
    assert A.attribute("TrazynFirstMeet_Trazyn_01", [], KNOWN)[0] == "Trazyn, Lord of Histories"
    assert A.attribute("CH2_Dargonus_InquisitorTruth_5", [], KNOWN)[0] == "Dargonus"


def test_a_shared_conversation_falls_back_to_who_the_narration_names_at_the_start():
    got = A.attribute("PRL_BeforeFinalBattle_02", [{"text": 'Edelthrad winces, which only makes his grimace worse. "I am still standing."'}], KNOWN)
    assert got == ("Edelthrad", "narration names the speaker")
    assert A.attribute("PRL_MutinyBegins_01", [{"text": 'Theodora waves her hand in a commanding gesture. "Mort! Take a team."'}], KNOWN)[0] == "Theodora"


def test_a_named_character_outside_the_extractors_list_is_found_in_the_narration():
    got = A.attribute("CH2_Dargonus_InquisitorTruth_13", [{"text": 'Calcazar looks at you with disapproval. "I do not recommend lying."'}], KNOWN)
    assert got == ("Xavier Calcazar", "narration names the speaker")           # shared conversation: the narration beats the fallback


def test_nothing_to_go_on_stays_unattributed():
    assert A.attribute("PRL_WarrantSentinel_7", [{"text": '"—igh levels of caustic humours."'}], KNOWN) is None
    assert A.attribute("DeathCultIntroduction_Demonline", [{"text": "A ringing sound fills your ears."}], KNOWN) is None


def test_the_overlay_only_changes_unattributed_clips_and_the_original_catalog_is_untouched(tmp_path):
    cfg = make_repo(tmp_path)
    cat = {"a": {"event": "Companions_Techpriest_1", "speaker": "_unattributed", "wav": "w/a.wav", "duration": 3, "texts": []},
           "b": {"event": "Companions_Techpriest_2", "speaker": "Heinrix", "wav": "w/b.wav", "duration": 3, "texts": []}}
    put(cfg.voices / "catalog.json", cat)
    summary = A.build(cfg)
    assert summary["attributed"] == 1 and summary["by_speaker"] == {"Pasqal": 1}
    merged = A.catalog(cfg)
    assert merged["a"]["speaker"] == "Pasqal" and merged["a"]["attribution"] == "conversation name"
    assert merged["b"]["speaker"] == "Heinrix"                                  # already attributed: never overridden
    assert json.loads((cfg.voices / "catalog.json").read_text())["a"]["speaker"] == "_unattributed"
