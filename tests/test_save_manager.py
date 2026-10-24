"""
Unit tests for Save/Load and Game State Serialization subsystem.
Verifies round-trip preservation, object identity, instance isolation,
atomic file operations, and comprehensive validation error handling.
"""
import os
import json
import unittest
import tempfile
from pathlib import Path

from src.models.personality import Personality
from src.models.pokemon import Pokemon
from src.models.player import Player
from src.models.inventory import Inventory
from src.models.save_data import CURRENT_SCHEMA_VERSION, SaveDataError
from src.models.save_manager import (
    serialize_player,
    deserialize_player,
    save_game,
    load_game,
    SaveManager,
)
from src.data.species import PIKACHU, CHARMANDER, SQUIRTLE, SAMPLE_SPECIES
from src.data.attacks import (
    THUNDER_SHOCK,
    QUICK_ATTACK,
    THUNDERBOLT,
    EMBER,
    SCRATCH,
    SAMPLE_ATTACKS,
)
from src.data.items import ITEM_CATALOG


class TestSaveManager(unittest.TestCase):
    """
    Exhaustive test suite for game state persistence and restoration.
    """

    def setUp(self) -> None:
        self.personality1 = Personality(
            aggression=25,
            curiosity=80,
            fear=10,
            sociability=90,
            loyalty=95,
            confidence=70,
        )
        self.personality2 = Personality(
            aggression=60,
            curiosity=40,
            fear=30,
            sociability=50,
            loyalty=70,
            confidence=85,
        )

        # Create player with inventory
        self.inventory = Inventory(capacity=25)
        self.inventory.add_item("potion", 5)
        self.inventory.add_item("super_potion", 2)
        self.inventory.add_item("antidote", 3)

        self.player = Player(name="Red", unique_id="player-uuid-001", inventory=self.inventory)

        # Create Pokemon 1: Pikachu
        self.pika = Pokemon(
            species=PIKACHU,
            personality=self.personality1,
            level=12,
            experience=150,
            bond=45,
            obedience=90,
            unique_id="10001",
            nickname="Sparky",
            attacks=[THUNDER_SHOCK, QUICK_ATTACK, THUNDERBOLT],
            trained_stats={"attack": 10, "defense": 5, "speed": 15},
        )
        self.pika.take_damage(10)  # HP missing
        self.pika.mark_level_move_awarded(1, "thunder shock")
        self.pika.mark_level_move_awarded(5, "quick attack")

        # Create Pokemon 2: Charmander
        self.charm = Pokemon(
            species=CHARMANDER,
            personality=self.personality2,
            level=10,
            experience=80,
            bond=30,
            obedience=85,
            unique_id="10002",
            nickname="Blaze",
            attacks=[SCRATCH, EMBER],
            trained_stats={"attack": 8, "defense": 4, "speed": 6},
        )

        # Setup collection and team
        self.player.add_pokemon(self.pika)
        self.player.add_pokemon(self.charm)

        self.player.add_to_team(self.pika)
        self.player.add_to_team(self.charm)
        self.player.set_active_pokemon(self.pika)

    # --- 1. Round-Trip Tests ---

    def test_01_round_trip_serialization_and_deserialization(self) -> None:
        """Serializing and deserializing a player in memory preserves all fields."""
        data = serialize_player(self.player)
        self.assertEqual(data["schema_version"], CURRENT_SCHEMA_VERSION)
        self.assertEqual(data["player"]["name"], "Red")
        self.assertEqual(data["player"]["unique_id"], "player-uuid-001")
        self.assertEqual(data["active_pokemon_id"], "10001")
        self.assertEqual(data["team"], ["10001", "10002"])

        loaded = deserialize_player(data)

        # Player assertions
        self.assertEqual(loaded.name, "Red")
        self.assertEqual(loaded.unique_id, "player-uuid-001")
        self.assertEqual(loaded.max_team_size, 6)

        # Inventory assertions
        self.assertEqual(loaded.inventory.capacity, 25)
        self.assertEqual(loaded.inventory.get_quantity("potion"), 5)
        self.assertEqual(loaded.inventory.get_quantity("super_potion"), 2)
        self.assertEqual(loaded.inventory.get_quantity("antidote"), 3)

        # Collection assertions
        self.assertEqual(len(loaded.collection), 2)
        pika_loaded = loaded.get_pokemon_by_id("10001")
        charm_loaded = loaded.get_pokemon_by_id("10002")
        self.assertIsNotNone(pika_loaded)
        self.assertIsNotNone(charm_loaded)

        # Pikachu exact field assertions
        self.assertEqual(pika_loaded.unique_id, "10001")
        self.assertEqual(pika_loaded.nickname, "Sparky")
        self.assertEqual(pika_loaded.species.name, "Pikachu")
        self.assertEqual(pika_loaded.level, 12)
        self.assertEqual(pika_loaded.experience, 150)
        self.assertEqual(pika_loaded.current_hp, self.pika.current_hp)
        self.assertEqual(pika_loaded.bond, 45)
        self.assertEqual(pika_loaded.obedience, 90)
        self.assertEqual(pika_loaded.personality.aggression, 25)
        self.assertEqual(pika_loaded.personality.curiosity, 80)
        self.assertEqual(pika_loaded.trained_attack, 10)
        self.assertEqual(pika_loaded.trained_defense, 5)
        self.assertEqual(pika_loaded.trained_speed, 15)
        self.assertEqual(
            [a.name for a in pika_loaded.attacks],
            ["Thunder Shock", "Quick Attack", "Thunderbolt"],
        )
        self.assertTrue(pika_loaded.is_level_move_awarded(1, "thunder shock"))
        self.assertTrue(pika_loaded.is_level_move_awarded(5, "quick attack"))

        # Team order and object identity assertions
        self.assertEqual(len(loaded.team), 2)
        self.assertEqual(loaded.team[0].unique_id, "10001")
        self.assertEqual(loaded.team[1].unique_id, "10002")
        self.assertIs(loaded.team[0], pika_loaded)
        self.assertIs(loaded.team[1], charm_loaded)

        # Active Pokemon selection assertions
        self.assertIsNotNone(loaded.active_pokemon)
        self.assertEqual(loaded.active_pokemon.unique_id, "10001")
        self.assertIs(loaded.active_pokemon, pika_loaded)

    def test_02_round_trip_file_save_and_load(self) -> None:
        """Saving to disk and loading from disk restores state accurately."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            save_path = Path(tmp_dir) / "saves" / "player_save.json"
            save_game(self.player, save_path)
            self.assertTrue(save_path.exists())

            loaded = load_game(save_path)
            self.assertEqual(loaded.name, "Red")
            self.assertEqual(len(loaded.team), 2)
            self.assertIs(loaded.team[0], loaded.get_pokemon_by_id("10001"))
            self.assertEqual(loaded.inventory.get_quantity("potion"), 5)

            # Using SaveManager service class
            loaded_via_service = SaveManager.load(save_path)
            self.assertEqual(loaded_via_service.name, "Red")

    def test_03_active_pokemon_none_preserved(self) -> None:
        """When player has no active Pokemon selected, None is saved and restored."""
        self.player.set_active_pokemon(None)
        self.assertIsNone(self.player.active_pokemon)

        data = serialize_player(self.player)
        self.assertIsNone(data["active_pokemon_id"])

        loaded = deserialize_player(data)
        self.assertIsNone(loaded.active_pokemon)

    # --- 2. Isolation Tests ---

    def test_04_loaded_instances_are_completely_independent(self) -> None:
        """Two separate loads from the same file produce independent mutable objects."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            save_path = Path(tmp_dir) / "test_save.json"
            save_game(self.player, save_path)

            loaded1 = load_game(save_path)
            loaded2 = load_game(save_path)

            # Players are independent
            self.assertIsNot(loaded1, loaded2)
            self.assertIsNot(loaded1.inventory, loaded2.inventory)

            # Pokemon are independent
            mon1 = loaded1.get_pokemon_by_id("10001")
            mon2 = loaded2.get_pokemon_by_id("10001")
            self.assertIsNot(mon1, mon2)

            # Mutating loaded1 does NOT affect loaded2
            loaded1.name = "Gold"
            loaded1.inventory.add_item("potion", 10)
            mon1.level = 50
            mon1.set_trained_stat("attack", 25)

            self.assertEqual(loaded2.name, "Red")
            self.assertEqual(loaded2.inventory.get_quantity("potion"), 5)
            self.assertEqual(mon2.level, 12)
            self.assertEqual(mon2.trained_attack, 10)

    def test_05_global_catalogs_are_never_mutated(self) -> None:
        """Restoration never modifies global species, attack, or item catalogs."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            save_path = Path(tmp_dir) / "catalog_test.json"
            save_game(self.player, save_path)

            # Baseline catalog checks
            pika_species_hp = PIKACHU.base_hp
            scratch_power = SCRATCH.power
            potion_max_stack = ITEM_CATALOG["potion"].max_stack

            # Load
            load_game(save_path)

            self.assertEqual(PIKACHU.base_hp, pika_species_hp)
            self.assertEqual(SCRATCH.power, scratch_power)
            self.assertEqual(ITEM_CATALOG["potion"].max_stack, potion_max_stack)

    # --- 3. Atomic File Operation Tests ---

    def test_06_atomic_save_leaves_existing_save_intact_on_failure(self) -> None:
        """If serialization or write fails, an existing valid save file is not destroyed."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            save_path = Path(tmp_dir) / "atomic_save.json"
            # First valid save
            save_game(self.player, save_path)
            original_content = save_path.read_text(encoding="utf-8")

            # Corrupt player or mock invalid player
            with self.assertRaises(SaveDataError):
                save_game("NotAPlayer", save_path)  # type: ignore

            # Save file must remain intact
            self.assertTrue(save_path.exists())
            self.assertEqual(save_path.read_text(encoding="utf-8"), original_content)

    # --- 4. Failure and Validation Tests ---

    def test_07_missing_file_raises_save_data_error(self) -> None:
        """Loading a non-existent file raises SaveDataError."""
        with self.assertRaises(SaveDataError) as ctx:
            load_game("non_existent_directory/non_existent_save.json")
        self.assertIn("not found", str(ctx.exception).lower())

    def test_08_invalid_json_raises_save_data_error(self) -> None:
        """Loading a malformed JSON file raises SaveDataError."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            corrupt_path = Path(tmp_dir) / "corrupt.json"
            corrupt_path.write_text("{ incomplete json: ", encoding="utf-8")

            with self.assertRaises(SaveDataError) as ctx:
                load_game(corrupt_path)
            self.assertIn("invalid json", str(ctx.exception).lower())

    def test_09_unsupported_schema_version_rejected(self) -> None:
        """Save data with an unknown/future schema version is rejected."""
        data = serialize_player(self.player)
        data["schema_version"] = 999

        with self.assertRaises(SaveDataError) as ctx:
            deserialize_player(data)
        self.assertIn("unsupported schema version", str(ctx.exception).lower())

    def test_10_missing_required_sections_rejected(self) -> None:
        """Save data missing top-level sections is rejected."""
        data = serialize_player(self.player)
        del data["collection"]

        with self.assertRaises(SaveDataError) as ctx:
            deserialize_player(data)
        self.assertIn("missing required section 'collection'", str(ctx.exception).lower())

    def test_11_unknown_species_or_attack_rejected(self) -> None:
        """Save data with unknown species or attacks raises SaveDataError."""
        # Unknown species
        data_bad_sp = serialize_player(self.player)
        data_bad_sp["collection"][0]["species"] = "Mewtwo_Unknown"
        with self.assertRaises(SaveDataError) as ctx:
            deserialize_player(data_bad_sp)
        self.assertIn("unknown species", str(ctx.exception).lower())

        # Unknown attack
        data_bad_atk = serialize_player(self.player)
        data_bad_atk["collection"][0]["attacks"] = ["Hyper_Beam_Unknown"]
        with self.assertRaises(SaveDataError) as ctx:
            deserialize_player(data_bad_atk)
        self.assertIn("unknown attack", str(ctx.exception).lower())

    def test_12_invalid_hp_or_level_rejected(self) -> None:
        """Save data with negative HP or HP exceeding max_hp is rejected."""
        # Current HP exceeding max_hp
        data_high_hp = serialize_player(self.player)
        data_high_hp["collection"][0]["current_hp"] = 9999
        with self.assertRaises(SaveDataError) as ctx:
            deserialize_player(data_high_hp)
        self.assertIn("exceeds maximum hp", str(ctx.exception).lower())

        # Negative HP
        data_neg_hp = serialize_player(self.player)
        data_neg_hp["collection"][0]["current_hp"] = -5
        with self.assertRaises(SaveDataError) as ctx:
            deserialize_player(data_neg_hp)
        self.assertIn("invalid current_hp", str(ctx.exception).lower())

        # Invalid level (0)
        data_zero_lvl = serialize_player(self.player)
        data_zero_lvl["collection"][0]["level"] = 0
        with self.assertRaises(SaveDataError) as ctx:
            deserialize_player(data_zero_lvl)
        self.assertIn("invalid level", str(ctx.exception).lower())

    def test_13_duplicate_pokemon_ids_in_collection_rejected(self) -> None:
        """Duplicate Pokemon IDs in the save collection are rejected."""
        data = serialize_player(self.player)
        # Duplicate Pikachu entry
        data["collection"].append(dict(data["collection"][0]))

        with self.assertRaises(SaveDataError) as ctx:
            deserialize_player(data)
        self.assertIn("duplicate pokemon id", str(ctx.exception).lower())

    def test_14_invalid_team_reference_rejected(self) -> None:
        """A team entry referencing a Pokemon ID not in the collection is rejected."""
        data = serialize_player(self.player)
        data["team"].append("99999_not_in_collection")

        with self.assertRaises(SaveDataError) as ctx:
            deserialize_player(data)
        self.assertIn("not found in player collection", str(ctx.exception).lower())

    def test_15_active_pokemon_not_on_team_rejected(self) -> None:
        """Active Pokemon selection must belong to the active team."""
        data = serialize_player(self.player)
        # Charmander is in collection, but remove it from team
        data["team"] = ["10001"]
        data["active_pokemon_id"] = "10002"  # In collection, but NOT on team

        with self.assertRaises(SaveDataError) as ctx:
            deserialize_player(data)
        self.assertIn("must belong to the active team", str(ctx.exception).lower())

    def test_16_invalid_inventory_data_rejected(self) -> None:
        """Save data with invalid inventory values or unknown items is rejected."""
        # Unknown item
        data_bad_item = serialize_player(self.player)
        data_bad_item["inventory"]["items"]["unobtainable_gem"] = 1
        with self.assertRaises(SaveDataError) as ctx:
            deserialize_player(data_bad_item)
        self.assertIn("unknown item", str(ctx.exception).lower())

        # Negative quantity
        data_neg_qty = serialize_player(self.player)
        data_neg_qty["inventory"]["items"]["potion"] = -2
        with self.assertRaises(SaveDataError) as ctx:
            deserialize_player(data_neg_qty)
        self.assertIn("invalid quantity", str(ctx.exception).lower())


if __name__ == "__main__":
    unittest.main()
