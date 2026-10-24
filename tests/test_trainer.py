"""
Unit tests for the Trainer model in Syntax Error 26.
Validates trainer identity, difficulty configurations, battle team methods,
active pokemon management, defeat tracking, rewards, and serialization.
"""
import unittest

from src.models.trainer import Trainer, DifficultyProfile, TrainerArchetype
from src.models.pokemon import Pokemon
from src.models.personality import Personality
from src.data.species import PIKACHU, CHARMANDER, SQUIRTLE
from src.data.attacks import THUNDER_SHOCK, QUICK_ATTACK, TACKLE


class TestTrainerModel(unittest.TestCase):
    """Test suite for Trainer model capabilities."""

    def setUp(self) -> None:
        self.personality = Personality(
            aggression=60,
            curiosity=40,
            fear=30,
            sociability=70,
            loyalty=80,
            confidence=65,
        )
        self.mon1 = Pokemon(
            species=PIKACHU,
            personality=self.personality,
            level=10,
            attacks=[THUNDER_SHOCK, QUICK_ATTACK],
        )
        self.mon2 = Pokemon(
            species=CHARMANDER,
            personality=self.personality,
            level=10,
            attacks=[TACKLE],
        )

    def test_trainer_initialization_success(self) -> None:
        """Trainer initializes with valid identity, defaults, and properties."""
        trainer = Trainer(
            trainer_id="youngster_joey",
            name="Joey",
            title="Youngster Joey",
            archetype=TrainerArchetype.YOUNGSTER,
            difficulty=DifficultyProfile.EASY,
            region_id="starting_meadow",
            team=[self.mon1, self.mon2],
            dialogue_intro="My Rattata is in the top percentage of Rattata!",
            dialogue_defeat="I lost?! No way!",
            dialogue_victory="Ha! I told you we were tough!",
            reward_items={"potion": 1},
        )

        self.assertEqual(trainer.trainer_id, "youngster_joey")
        self.assertEqual(trainer.unique_id, "youngster_joey")
        self.assertEqual(trainer.name, "Joey")
        self.assertEqual(trainer.title, "Youngster Joey")
        self.assertEqual(trainer.archetype, TrainerArchetype.YOUNGSTER)
        self.assertEqual(trainer.difficulty, DifficultyProfile.EASY)
        self.assertEqual(trainer.region_id, "starting_meadow")
        self.assertTrue(trainer.has_team)
        self.assertEqual(len(trainer.team), 2)
        self.assertEqual(trainer.active_pokemon, self.mon1)
        self.assertFalse(trainer.is_defeated)
        self.assertEqual(trainer.defeat_count, 0)
        self.assertIn("potion", trainer.reward_items)

    def test_trainer_validation_errors(self) -> None:
        """Trainer constructor raises ValueError on invalid inputs."""
        with self.assertRaises(ValueError):
            Trainer(trainer_id="", name="Joey", title="Youngster")

        with self.assertRaises(ValueError):
            Trainer(trainer_id="j", name="  ", title="Youngster")

        with self.assertRaises(ValueError):
            Trainer(trainer_id="j", name="Joey", title="")

        with self.assertRaises(ValueError):
            Trainer(trainer_id="j", name="Joey", title="Youngster", archetype="INVALID_ARCHETYPE")

        with self.assertRaises(ValueError):
            Trainer(trainer_id="j", name="Joey", title="Youngster", difficulty="SUPER_HARD")

    def test_team_and_active_pokemon_management(self) -> None:
        """Setting team automatically assigns active Pokemon to the first conscious member."""
        trainer = Trainer(
            trainer_id="t1",
            name="Lass",
            title="Lass Haley",
            archetype=TrainerArchetype.LASS,
        )
        self.assertFalse(trainer.has_team)
        self.assertIsNone(trainer.active_pokemon)

        trainer.set_team([self.mon1, self.mon2])
        self.assertTrue(trainer.has_team)
        self.assertEqual(trainer.active_pokemon, self.mon1)

        # Switching active Pokemon
        trainer.set_active_pokemon(self.mon2)
        self.assertEqual(trainer.active_pokemon, self.mon2)

        # Fainting active Pokemon and fetching next conscious
        self.mon2.take_damage(self.mon2.max_hp)
        self.assertTrue(self.mon2.is_fainted)
        next_mon = trainer.get_next_conscious_pokemon()
        self.assertEqual(next_mon, self.mon1)

        # When all faint
        self.mon1.take_damage(self.mon1.max_hp)
        self.assertFalse(trainer.has_conscious_pokemon())
        self.assertIsNone(trainer.get_next_conscious_pokemon())

    def test_duck_type_compatibility_with_player(self) -> None:
        """Trainer implements is_pokemon_owned, get_team, and get_all_pokemon for battle engine compatibility."""
        trainer = Trainer(
            trainer_id="t2",
            name="Hiker",
            title="Hiker David",
            team=[self.mon1],
        )
        self.assertTrue(trainer.is_pokemon_owned(self.mon1))
        self.assertTrue(trainer.is_pokemon_owned(self.mon1.unique_id))
        self.assertFalse(trainer.is_pokemon_owned(self.mon2))

        self.assertEqual(trainer.get_team(), [self.mon1])
        self.assertEqual(trainer.get_all_pokemon(), [self.mon1])

    def test_defeat_recording_and_reset(self) -> None:
        """Defeat tracking records defeat count, is_defeated flag, and reset heals team."""
        trainer = Trainer(
            trainer_id="t3",
            name="Bug Catcher",
            title="Bug Catcher Sammy",
            team=[self.mon1],
        )
        self.mon1.take_damage(self.mon1.max_hp)
        self.assertTrue(self.mon1.is_fainted)

        trainer.record_defeat()
        self.assertTrue(trainer.is_defeated)
        self.assertEqual(trainer.defeat_count, 1)

        # Resetting battle state restores team health
        trainer.reset_battle_state()
        self.assertFalse(self.mon1.is_fainted)
        self.assertEqual(self.mon1.current_hp, self.mon1.max_hp)
        self.assertEqual(trainer.active_pokemon, self.mon1)

    def test_reward_claiming(self) -> None:
        """Victory rewards can only be claimed once."""
        trainer = Trainer(
            trainer_id="t4",
            name="Ace",
            title="Ace Trainer",
            reward_items={"poke_ball": 5, "hyper_potion": 2},
        )
        self.assertFalse(trainer.reward_claimed)

        # First claim succeeds
        rewards = trainer.claim_rewards()
        self.assertEqual(rewards, {"poke_ball": 5, "hyper_potion": 2})
        self.assertTrue(trainer.reward_claimed)

        # Second claim yields empty dict
        empty_rewards = trainer.claim_rewards()
        self.assertEqual(empty_rewards, {})

    def test_serialization_round_trip(self) -> None:
        """Trainer serializes to dictionary and deserializes cleanly without data loss."""
        trainer = Trainer(
            trainer_id="gym_brock",
            name="Brock",
            title="Gym Leader Brock",
            archetype=TrainerArchetype.GYM_LEADER,
            difficulty=DifficultyProfile.BOSS,
            region_id="pewter_gym",
            team=[self.mon1, self.mon2],
            dialogue_intro="I'm Brock! I believe in rock-hard determination!",
            dialogue_defeat="I took you for granted.",
            reward_items={"tm34": 1},
        )
        trainer.record_defeat()

        data = trainer.to_dict()
        self.assertEqual(data["trainer_id"], "gym_brock")
        self.assertEqual(data["difficulty"], "BOSS")
        self.assertEqual(data["archetype"], "GYM_LEADER")
        self.assertEqual(len(data["team"]), 2)
        self.assertTrue(data["is_defeated"])
        self.assertEqual(data["defeat_count"], 1)

        restored = Trainer.from_dict(data)
        self.assertEqual(restored.trainer_id, "gym_brock")
        self.assertEqual(restored.name, "Brock")
        self.assertEqual(restored.difficulty, DifficultyProfile.BOSS)
        self.assertEqual(restored.archetype, TrainerArchetype.GYM_LEADER)
        self.assertEqual(len(restored.team), 2)
        self.assertEqual(restored.active_pokemon.species.name, "Pikachu")
        self.assertTrue(restored.is_defeated)
        self.assertEqual(restored.defeat_count, 1)


if __name__ == "__main__":
    unittest.main()
