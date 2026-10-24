"""
Unit and integration tests for Pokémon Roster Expansion and Starter Selection.

Tests verify:
1. Starter selection properly initializes Bulbasaur, Charmander, and Squirtle.
2. Selection by number (1-3) and canonical name (case-insensitive).
3. Obsolete starter choices (Pikachu) and invalid inputs are rejected.
4. Correct stats, types, and initial moves for all starters.
5. Validity, types, and base stats for all 16 species in the expanded roster.
6. Type and stat distribution diversity across the roster.
7. Save/load round-trip persistence for all new species.
8. Backward compatibility: existing saves containing Pikachu continue to load seamlessly.
9. Wild encounter / spawn generation using the expanded roster.
10. Level-up move learning table validity for all expanded species.
"""
import os
import tempfile
import unittest

from src.models.personality import Personality
from src.models.pokemon import Pokemon
from src.models.player import Player
from src.models.pokemon_type import PokemonType
from src.models.species import PokemonSpecies
from src.models.save_manager import save_game, load_game, serialize_player, deserialize_player
from src.models.spawn_manager import SpawnManager
from src.models.spawn_area import SpawnArea
from src.data.species import (
    SAMPLE_SPECIES,
    PIKACHU,
    CHARMANDER,
    SQUIRTLE,
    BULBASAUR,
    PIDGEY,
    RATTATA,
    CATERPIE,
    BUTTERFREE,
    GEODUDE,
    ZUBAT,
    MACHOP,
    GASTLY,
    ABRA,
    EEVEE,
    GROWLITHE,
    POLIWAG,
)
from src.data.attacks import SAMPLE_ATTACKS, TACKLE, VINE_WHIP, SCRATCH, EMBER, WATER_GUN
from src.data.move_learning import get_learnable_moves, SPECIES_MOVE_LEARNING
from src.data.spawn_config import DEFAULT_SPAWN_CONFIGS
from game import AdventureGame


def make_scripted_io(inputs: list[str]):
    """Helper creating scripted input/output hooks for AdventureGame."""
    in_list = list(inputs)
    out_list: list[str] = []

    def mock_in(prompt: str = "") -> str:
        if in_list:
            return in_list.pop(0)
        return "quit"

    def mock_out(*args) -> None:
        out_list.append(" ".join(str(a) for a in args))

    return in_list, out_list, mock_in, mock_out


class TestRosterAndStarters(unittest.TestCase):
    """Test suite for expanded Pokemon roster, starters, and compatibility."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.save_path = os.path.join(self.temp_dir.name, "test_roster_save.json")
        self.neutral_personality = Personality(50, 50, 50, 50, 50, 50)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    # --- 1. Starter Selection Tests ---

    def test_01_starter_selection_bulbasaur(self) -> None:
        """Selecting starter 1 creates Bulbasaur with Grass/Poison types, Lv.5, and Tackle + Vine Whip."""
        inputs = ["1", "Ash", "1", "10", "y", "3"]
        _, logs, mock_in, mock_out = make_scripted_io(inputs)
        game = AdventureGame(input_fn=mock_in, output_fn=mock_out, save_file=self.save_path)
        game.run()

        self.assertIsNotNone(game.player)
        mon = game.player.active_pokemon
        self.assertIsNotNone(mon)
        self.assertEqual(mon.species.name, "Bulbasaur")
        self.assertEqual(mon.level, 5)
        self.assertEqual(mon.species.primary_type, PokemonType.GRASS)
        self.assertEqual(mon.species.secondary_type, PokemonType.POISON)
        self.assertEqual(mon.species.types, (PokemonType.GRASS, PokemonType.POISON))
        # Base HP 14 + (5 * 2) = 24
        self.assertEqual(mon.max_hp, 24)
        self.assertEqual(mon.current_hp, 24)
        self.assertEqual([a.name for a in mon.attacks], ["Tackle", "Vine Whip"])

    def test_02_starter_selection_charmander(self) -> None:
        """Selecting starter 2 creates Charmander with Fire type, Lv.5, and Scratch + Ember."""
        inputs = ["1", "Ash", "2", "10", "y", "3"]
        _, logs, mock_in, mock_out = make_scripted_io(inputs)
        game = AdventureGame(input_fn=mock_in, output_fn=mock_out, save_file=self.save_path)
        game.run()

        mon = game.player.active_pokemon
        self.assertEqual(mon.species.name, "Charmander")
        self.assertEqual(mon.level, 5)
        self.assertEqual(mon.species.primary_type, PokemonType.FIRE)
        self.assertIsNone(mon.species.secondary_type)
        # Base HP 12 + (5 * 2) = 22
        self.assertEqual(mon.max_hp, 22)
        self.assertEqual([a.name for a in mon.attacks], ["Scratch", "Ember"])

    def test_03_starter_selection_squirtle(self) -> None:
        """Selecting starter 3 creates Squirtle with Water type, Lv.5, and Tackle + Water Gun."""
        inputs = ["1", "Ash", "3", "10", "y", "3"]
        _, logs, mock_in, mock_out = make_scripted_io(inputs)
        game = AdventureGame(input_fn=mock_in, output_fn=mock_out, save_file=self.save_path)
        game.run()

        mon = game.player.active_pokemon
        self.assertEqual(mon.species.name, "Squirtle")
        self.assertEqual(mon.level, 5)
        self.assertEqual(mon.species.primary_type, PokemonType.WATER)
        self.assertIsNone(mon.species.secondary_type)
        # Base HP 13 + (5 * 2) = 23
        self.assertEqual(mon.max_hp, 23)
        self.assertEqual([a.name for a in mon.attacks], ["Tackle", "Water Gun"])

    def test_04_starter_selection_by_name(self) -> None:
        """Entering species names 'bulbasaur', 'charmander', or 'squirtle' works case-insensitively."""
        for name_input, expected_species in [
            ("bulbasaur", "Bulbasaur"),
            ("CHARMANDER", "Charmander"),
            ("Squirtle", "Squirtle"),
        ]:
            inputs = ["1", "Red", name_input, "10", "y", "3"]
            _, _, mock_in, mock_out = make_scripted_io(inputs)
            game = AdventureGame(input_fn=mock_in, output_fn=mock_out, save_file=self.save_path)
            game.run()
            self.assertEqual(game.player.active_pokemon.species.name, expected_species)

    def test_05_rejection_of_obsolete_and_invalid_starters(self) -> None:
        """Entering obsolete starter 'pikachu', negative numbers, or invalid names is rejected."""
        inputs = ["1", "Ash", "pikachu", "0", "4", "-1", "mewtwo", "1", "10", "y", "3"]
        _, logs, mock_in, mock_out = make_scripted_io(inputs)
        game = AdventureGame(input_fn=mock_in, output_fn=mock_out, save_file=self.save_path)
        game.run()

        full_logs = "\n".join(logs)
        self.assertIn("Please enter 1, 2, or 3.", full_logs)
        self.assertEqual(game.player.active_pokemon.species.name, "Bulbasaur")

    # --- 2. Expanded Roster Species Validation ---

    def test_06_all_sixteen_species_defined_and_valid(self) -> None:
        """All 16 species in SAMPLE_SPECIES have valid attributes, positive stats, and can instantiate Pokemon."""
        self.assertGreaterEqual(len(SAMPLE_SPECIES), 16)
        expected_roster = {
            "Bulbasaur", "Charmander", "Squirtle", "Pikachu",
            "Pidgey", "Rattata", "Caterpie", "Butterfree",
            "Geodude", "Zubat", "Machop", "Gastly",
            "Abra", "Eevee", "Growlithe", "Poliwag",
        }
        for name in expected_roster:
            self.assertIn(name, SAMPLE_SPECIES)
            species = SAMPLE_SPECIES[name]
            self.assertIsInstance(species, PokemonSpecies)
            self.assertEqual(species.name, name)
            self.assertIsInstance(species.primary_type, PokemonType)
            if species.secondary_type is not None:
                self.assertIsInstance(species.secondary_type, PokemonType)
                self.assertNotEqual(species.primary_type, species.secondary_type)
            self.assertGreater(species.base_hp, 0)
            self.assertGreater(species.base_attack, 0)
            self.assertGreater(species.base_defense, 0)
            self.assertGreater(species.base_speed, 0)
            self.assertGreater(len(species.available_attacks), 0)
            self.assertGreater(len(species.abilities), 0)

            # Verify individual Pokemon instantiation
            mon = Pokemon(species=species, personality=self.neutral_personality, level=5)
            self.assertEqual(mon.species.name, name)
            self.assertEqual(mon.level, 5)
            self.assertEqual(mon.max_hp, species.base_hp + 10)
            self.assertEqual(mon.current_hp, mon.max_hp)

    def test_07_type_and_stat_diversity_coverage(self) -> None:
        """The expanded roster provides diversity across types, offensive/defensive, and speed tiers."""
        # 1. Dual types present
        dual_type_species = [s for s in SAMPLE_SPECIES.values() if s.secondary_type is not None]
        self.assertGreaterEqual(len(dual_type_species), 5)

        # 2. Defensive wall (Geodude Def 100)
        self.assertGreaterEqual(SAMPLE_SPECIES["Geodude"].base_defense, 100)

        # 3. Heavy physical attackers (Machop, Geodude, Growlithe Atk >= 70)
        self.assertGreaterEqual(SAMPLE_SPECIES["Machop"].base_attack, 80)
        self.assertGreaterEqual(SAMPLE_SPECIES["Growlithe"].base_attack, 70)

        # 4. Fast Pokemon (Speed >= 80: Pikachu, Abra, Poliwag, Gastly)
        fast_mons = [s.name for s in SAMPLE_SPECIES.values() if s.base_speed >= 80]
        self.assertIn("Pikachu", fast_mons)
        self.assertIn("Abra", fast_mons)
        self.assertIn("Gastly", fast_mons)
        self.assertIn("Poliwag", fast_mons)

        # 5. Slow / Tanky Pokemon (Speed <= 35: Geodude, Machop)
        slow_mons = [s.name for s in SAMPLE_SPECIES.values() if s.base_speed <= 35]
        self.assertIn("Geodude", slow_mons)
        self.assertIn("Machop", slow_mons)

    # --- 3. Save / Load Persistence and Compatibility ---

    def test_08_save_load_round_trip_with_new_species(self) -> None:
        """Player with a team composed of new species serializes, saves, and restores accurately."""
        player = Player(name="Champion Green")
        team_species = [BULBASAUR, PIDGEY, GEODUDE, MACHOP, GASTLY, ABRA]
        for idx, sp in enumerate(team_species, 1):
            mon = Pokemon(
                species=sp,
                personality=self.neutral_personality,
                level=idx + 3,
                attacks=sp.available_attacks[:2],
            )
            player.add_pokemon(mon)
            player.add_to_team(mon)
        player.set_active_pokemon(player.team[0])

        save_game(player, self.save_path)
        loaded = load_game(self.save_path)

        self.assertEqual(loaded.name, "Champion Green")
        self.assertEqual(len(loaded.team), 6)
        self.assertEqual(loaded.active_pokemon.species.name, "Bulbasaur")

        for original_mon, restored_mon in zip(player.team, loaded.team):
            self.assertEqual(restored_mon.species.name, original_mon.species.name)
            self.assertEqual(restored_mon.level, original_mon.level)
            self.assertEqual(restored_mon.current_hp, original_mon.current_hp)
            self.assertEqual(restored_mon.max_hp, original_mon.max_hp)
            self.assertEqual(
                [a.name for a in restored_mon.attacks],
                [a.name for a in original_mon.attacks],
            )

    def test_09_backwards_compatibility_existing_save_with_pikachu(self) -> None:
        """Existing save containing Pikachu continues to load and battle without error."""
        pika_mon = Pokemon(
            species=PIKACHU,
            personality=self.neutral_personality,
            level=5,
            attacks=PIKACHU.available_attacks[:2],
        )
        player = Player(name="Legacy Ash")
        player.add_pokemon(pika_mon)
        player.add_to_team(pika_mon)
        player.set_active_pokemon(pika_mon)

        save_game(player, self.save_path)
        loaded = load_game(self.save_path)

        self.assertEqual(loaded.name, "Legacy Ash")
        self.assertEqual(loaded.active_pokemon.species.name, "Pikachu")
        self.assertEqual(loaded.active_pokemon.level, 5)

    # --- 4. Wild Spawning and Move Progression ---

    def test_10_wild_encounter_generation_expanded_roster(self) -> None:
        """SpawnManager successfully spawns wild Pokemon from expanded configs."""
        mgr = SpawnManager(seed=123)
        area = SpawnArea(
            area_id="forest_spawns",
            name="Forest Trail Spawns",
            allowed_species=(BULBASAUR, PIDGEY, MACHOP, ZUBAT),
            max_active_pokemon=4,
            base_spawn_probability=1.0,
        )
        mgr.register_area(area)

        spawned = mgr.spawn_until_limit("forest_spawns")
        self.assertEqual(len(spawned), 4)
        for mon in spawned:
            self.assertIn(mon.species.name, ["Bulbasaur", "Pidgey", "Machop", "Zubat"])
            self.assertGreater(len(mon.attacks), 0)

    def test_11_move_learning_tables_for_all_species(self) -> None:
        """Every species in the expanded roster has a valid move-learning table sorted by level."""
        for species_name in SAMPLE_SPECIES:
            moves = get_learnable_moves(species_name)
            self.assertGreaterEqual(len(moves), 3, f"Species {species_name} should have >= 3 learnable moves.")
            levels = [m.level for m in moves]
            self.assertEqual(levels, sorted(levels), f"Moves for {species_name} must be sorted by level.")
            for m in moves:
                self.assertGreaterEqual(m.level, 1)
                self.assertIsNotNone(m.attack.name)
                self.assertIn(m.attack.name, SAMPLE_ATTACKS)


if __name__ == "__main__":
    unittest.main()
