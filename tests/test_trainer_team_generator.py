"""
Unit tests for TrainerTeamGenerator and dynamic trainer team generation.
Verifies party strength scaling, level bounds, team sizes, valid movesets,
archetype affinities, seed repeatability, and idempotency.
"""
import unittest
import random

from src.models.trainer import Trainer, DifficultyProfile, TrainerArchetype
from src.models.trainer_team_generator import (
    TrainerTeamGenerator,
    calculate_player_party_strength,
    get_eligible_species_for_trainer,
    generate_pokemon_for_trainer,
    generate_trainer_team,
    create_trainer,
)
from src.models.player import Player
from src.models.pokemon import Pokemon, MAX_KNOWN_MOVES
from src.models.species import PokemonSpecies
from src.models.personality import Personality
from src.models.attack import Attack
from src.models.pokemon_type import PokemonType
from src.data.species import PIKACHU, CHARMANDER, SQUIRTLE, BULBASAUR, CATERPIE, PIDGEY, GEODUDE


class TestTrainerTeamGenerator(unittest.TestCase):
    """Test cases for TrainerTeamGenerator and related helpers."""

    def setUp(self) -> None:
        self.personality = Personality(
            aggression=50,
            curiosity=50,
            fear=50,
            sociability=50,
            loyalty=50,
            confidence=50,
        )

    def test_party_strength_empty_or_none_player(self) -> None:
        """Party strength defaults to 5 for None player or player with no team."""
        self.assertEqual(calculate_player_party_strength(None), 5)

        player = Player(name="Red")
        self.assertEqual(calculate_player_party_strength(player), 5)

    def test_party_strength_calculation_formula(self) -> None:
        """Party strength combines max level, mean level, and active level."""
        player = Player(name="Red")
        mon1 = Pokemon(species=PIKACHU, personality=self.personality, level=10)
        mon2 = Pokemon(species=CHARMANDER, personality=self.personality, level=20)
        mon3 = Pokemon(species=SQUIRTLE, personality=self.personality, level=30)
        player.add_pokemon(mon1)
        player.add_to_team(mon1)
        player.add_pokemon(mon2)
        player.add_to_team(mon2)
        player.add_pokemon(mon3)
        player.add_to_team(mon3)
        player.set_active_pokemon(mon1)

        # Levels: [10, 20, 30]
        # max: 30, mean: 20, active: 10
        # composite: 0.4 * 30 + 0.4 * 20 + 0.2 * 10 = 12 + 8 + 2 = 22
        expected_strength = 22
        self.assertEqual(calculate_player_party_strength(player), expected_strength)

    def test_party_strength_bounds_and_clamping(self) -> None:
        """Party strength is clamped within [1, 100]."""
        player = Player(name="Red")
        mon_high = Pokemon(species=PIKACHU, personality=self.personality, level=100)
        player.add_pokemon(mon_high)
        player.add_to_team(mon_high)
        self.assertEqual(calculate_player_party_strength(player), 100)

        mon_low = Pokemon(species=BULBASAUR, personality=self.personality, level=1)
        player_low = Player(name="Blue")
        player_low.add_pokemon(mon_low)
        player_low.add_to_team(mon_low)
        self.assertEqual(calculate_player_party_strength(player_low), 1)

    def test_target_level_range_per_difficulty(self) -> None:
        """Verifies level bounds across difficulty tiers."""
        base_strength = 20

        # EASY: target = strength - 1 (19), min = 18, max = 19
        min_lvl, target_lvl, max_lvl = TrainerTeamGenerator.get_target_level_range(
            DifficultyProfile.EASY, base_strength
        )
        self.assertEqual(target_lvl, 19)
        self.assertLessEqual(min_lvl, target_lvl)
        self.assertLessEqual(target_lvl, max_lvl)

        # NORMAL: target = strength (20), min = 19, max = 21
        min_lvl, target_lvl, max_lvl = TrainerTeamGenerator.get_target_level_range(
            DifficultyProfile.NORMAL, base_strength
        )
        self.assertEqual(target_lvl, 20)
        self.assertEqual(min_lvl, 19)
        self.assertEqual(max_lvl, 21)

        # HARD: target = strength + 1 (21), min = 21, max = 23
        min_lvl, target_lvl, max_lvl = TrainerTeamGenerator.get_target_level_range(
            DifficultyProfile.HARD, base_strength
        )
        self.assertEqual(target_lvl, 21)
        self.assertEqual(min_lvl, 21)
        self.assertEqual(max_lvl, 23)

        # BOSS: target = strength + 2 (22), min = 22, max = 25
        min_lvl, target_lvl, max_lvl = TrainerTeamGenerator.get_target_level_range(
            DifficultyProfile.BOSS, base_strength
        )
        self.assertEqual(target_lvl, 22)
        self.assertEqual(min_lvl, 22)
        self.assertEqual(max_lvl, 25)

    def test_team_size_per_difficulty(self) -> None:
        """Verifies team sizes follow difficulty-appropriate bounds."""
        rng = random.Random(42)
        for _ in range(50):
            easy_size = TrainerTeamGenerator.get_team_size(DifficultyProfile.EASY, rng)
            self.assertIn(easy_size, (1, 2))

            normal_size = TrainerTeamGenerator.get_team_size(DifficultyProfile.NORMAL, rng)
            self.assertIn(normal_size, (2, 3))

            hard_size = TrainerTeamGenerator.get_team_size(DifficultyProfile.HARD, rng)
            self.assertIn(hard_size, (3, 4, 5))

            boss_size = TrainerTeamGenerator.get_team_size(DifficultyProfile.BOSS, rng)
            self.assertIn(boss_size, (4, 5, 6))

    def test_eligible_species_archetype_affinity(self) -> None:
        """Bug Catcher in meadow prioritizes Bug types (e.g. Caterpie)."""
        species_list = get_eligible_species_for_trainer(
            archetype=TrainerArchetype.BUG_CATCHER,
            region_id="starting_meadow",
        )
        self.assertTrue(len(species_list) > 0)
        # First species should be Bug type
        lead_species = species_list[0]
        self.assertEqual(lead_species.primary_type, PokemonType.BUG)

    def test_generate_moveset_validity(self) -> None:
        """Generated movesets contain 1-4 distinct, level-appropriate Attack instances."""
        # Low level Pikachu
        moves_lv1 = TrainerTeamGenerator.generate_moveset(PIKACHU, level=1)
        self.assertGreaterEqual(len(moves_lv1), 1)
        self.assertLessEqual(len(moves_lv1), MAX_KNOWN_MOVES)
        for m in moves_lv1:
            self.assertIsInstance(m, Attack)
        self.assertEqual(len(moves_lv1), len(set(moves_lv1)))

        # Level 10 Pikachu should have learned several moves
        moves_lv10 = TrainerTeamGenerator.generate_moveset(PIKACHU, level=10)
        self.assertEqual(len(moves_lv10), 4)
        for m in moves_lv10:
            self.assertIsInstance(m, Attack)

    def test_generate_pokemon_for_trainer(self) -> None:
        """Generated Pokemon has correct level, moves, full HP, and personality."""
        mon = generate_pokemon_for_trainer(species=PIDGEY, level=8)
        self.assertIsInstance(mon, Pokemon)
        self.assertEqual(mon.species.name, "Pidgey")
        self.assertEqual(mon.level, 8)
        self.assertEqual(mon.current_hp, mon.max_hp)
        self.assertTrue(mon.can_battle)
        self.assertGreater(len(mon.attacks), 0)

    def test_generate_trainer_team_and_lead(self) -> None:
        """Trainer team generation sets active Pokemon and populates team."""
        trainer = Trainer(
            trainer_id="youngster_joey",
            name="Joey",
            title="Youngster",
            archetype=TrainerArchetype.YOUNGSTER,
            difficulty=DifficultyProfile.NORMAL,
            region_id="starting_meadow",
        )

        team = generate_trainer_team(trainer, seed=123)
        self.assertTrue(trainer.has_team)
        self.assertEqual(len(trainer.team), len(team))
        self.assertIsNotNone(trainer.active_pokemon)
        self.assertEqual(trainer.active_pokemon, team[0])
        self.assertGreaterEqual(len(team), 2)
        self.assertLessEqual(len(team), 3)

        # Team members are battle-ready
        for mon in team:
            self.assertFalse(mon.is_fainted)
            self.assertTrue(mon.can_battle)
            self.assertGreater(len(mon.attacks), 0)

    def test_team_generation_idempotency(self) -> None:
        """Existing trainer team is preserved and not rerolled on subsequent calls."""
        trainer = Trainer(
            trainer_id="lass_sarah",
            name="Sarah",
            title="Lass",
            difficulty=DifficultyProfile.EASY,
            region_id="starting_meadow",
        )
        team1 = generate_trainer_team(trainer, seed=10)
        initial_ids = [p.unique_id for p in team1]

        # Call generate_team again without force_regenerate
        team2 = generate_trainer_team(trainer, seed=999)
        second_ids = [p.unique_id for p in team2]

        # Must be identical instances and IDs
        self.assertEqual(initial_ids, second_ids)
        self.assertEqual(team1, team2)

        # If force_regenerate=True, team is re-generated
        team3 = generate_trainer_team(trainer, seed=999, force_regenerate=True)
        third_ids = [p.unique_id for p in team3]
        self.assertNotEqual(initial_ids, third_ids)

    def test_seed_repeatability(self) -> None:
        """Identical seeds produce identical teams for the same trainer setup."""
        trainer_a = Trainer(
            trainer_id="t_a",
            name="Ace Bob",
            title="Ace Trainer",
            archetype=TrainerArchetype.ACE_TRAINER,
            difficulty=DifficultyProfile.HARD,
            region_id="starting_meadow",
        )
        trainer_b = Trainer(
            trainer_id="t_b",
            name="Ace Bob",
            title="Ace Trainer",
            archetype=TrainerArchetype.ACE_TRAINER,
            difficulty=DifficultyProfile.HARD,
            region_id="starting_meadow",
        )

        team_a = generate_trainer_team(trainer_a, seed=777)
        team_b = generate_trainer_team(trainer_b, seed=777)

        self.assertEqual(len(team_a), len(team_b))
        for ma, mb in zip(team_a, team_b):
            self.assertEqual(ma.species.name, mb.species.name)
            self.assertEqual(ma.level, mb.level)
            self.assertEqual([a.name for a in ma.attacks], [a.name for a in mb.attacks])

    def test_ace_pokemon_level_guarantee(self) -> None:
        """The last Pokemon on a trainer's team is scaled at or above target level."""
        player = Player(name="Red")
        lead = Pokemon(species=PIKACHU, personality=self.personality, level=15)
        player.add_pokemon(lead)
        player.add_to_team(lead)

        trainer = Trainer(
            trainer_id="boss_giovanni",
            name="Giovanni",
            title="Boss",
            archetype=TrainerArchetype.GYM_LEADER,
            difficulty=DifficultyProfile.BOSS,
            region_id="starting_meadow",
        )

        team = generate_trainer_team(trainer, player=player, seed=42)
        _, target_lvl, _ = TrainerTeamGenerator.get_target_level_range(
            DifficultyProfile.BOSS, calculate_player_party_strength(player)
        )
        ace_mon = team[-1]
        self.assertGreaterEqual(ace_mon.level, target_lvl)

    def test_create_trainer_convenience_factory(self) -> None:
        """create_trainer instantiates and populates a trainer in one call."""
        trainer = create_trainer(
            trainer_id="hiker_brock",
            name="Brock",
            title="Hiker",
            archetype=TrainerArchetype.HIKER,
            difficulty=DifficultyProfile.NORMAL,
            region_id="starting_meadow",
            seed=55,
        )
        self.assertEqual(trainer.name, "Brock")
        self.assertEqual(trainer.title, "Hiker")
        self.assertTrue(trainer.has_team)
        self.assertIsNotNone(trainer.active_pokemon)
        self.assertIn("super_potion", trainer.reward_items)

        # Serialization round-trip
        data = trainer.to_dict()
        restored = Trainer.from_dict(data)
        self.assertEqual(restored.trainer_id, trainer.trainer_id)
        self.assertEqual(len(restored.team), len(trainer.team))
        self.assertEqual(restored.active_pokemon.species.name, trainer.active_pokemon.species.name)


if __name__ == "__main__":
    unittest.main()
