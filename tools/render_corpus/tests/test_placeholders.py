import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))

from build_test_set import narration_only  # noqa: E402


def test_pet_noun_follows_the_species_the_line_describes():
    assert narration_only("{n}{petname} responds with a clack of the hooked beak.{/n}") == "The raven responds with a clack of the hooked beak."
    assert narration_only("{n}A battle on {petname}'s perch.{/n}") == "A battle on the raven's perch."
    assert narration_only("{n}You smile. {petname} leaps onto all fours with a growl.{/n}") == "You smile. The dog leaps onto all fours with a growl."


def test_pet_noun_is_neutral_when_the_line_does_not_say():
    assert narration_only("{n}{petname} watches you approach.{/n}") == "Your pet watches you approach."
    assert narration_only("{n}You wonder how {petname} did it.{/n}") == "You wonder how your pet did it."
    assert narration_only("{n}Feathers ruffled and growling, {petname} cries out.{/n}") == "Feathers ruffled and growling, your pet cries out."


def test_player_name_is_the_title():
    assert narration_only("{n}Very well, {name}.{/n}") == "Very well, Lord Captain."
