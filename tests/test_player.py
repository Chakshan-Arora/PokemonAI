"""
Unit tests for the Player model and Pokemon collection/team management.

Tests verify:
1. Player can be created.
2. Player starts with an empty collection.
3. Pokémon can be added to collection.
4. Multiple Pokémon can be owned.
5. Duplicate Pokémon cannot be added.
6. Pokémon can be retrieved by ID.
7. Pokémon can be removed.
8. Pokémon can be added to the team.
9. Unowned Pokémon cannot be added to the team.
10. Duplicate team entries are prevented.
11. Team cannot exceed 6 Pokémon.
12. Pokémon can be removed from the team.
13. Active Pokémon can be selected.
14. Unowned Pokémon cannot become active.
15. Removing the active Pokémon clears the active Pokémon.
16. Removing a Pokémon from the collection also removes it from the team.
17. Removing a Pokémon from the collection clears active status if necessary.
"""
import unittest

from src.models.personality import Personality
from src.models.pokemon import Pokemon
from src.models.player import Player
from src.data.species import PIKACHU, CHARMANDER, SQUIRTLE


class TestPlayerSystem(unittest.TestCase):
    """Test suite covering the Player model, collection, and team management."""

    def setUp(self) -> None:
        """Create sample personality and Pokemon instances for testing."""
        self.sample_personality = Personality(
            aggression=30,
            curiosity=60,
            fear=20,
            sociability=70,
            loyalty=80,
            confidence=60,
        )
        self.pikachu = Pokemon(species=PIKACHU, personality=self.sample_personality, level=5)
        self.charmander = Pokemon(species=CHARMANDER, personality=self.sample_personality, level=5)
        self.squirtle = Pokemon(species=SQUIRTLE, personality=self.sample_personality, level=5)

    # 1. Player can be created.
    def test_01_player_can_be_created(self) -> None:
        player = Player(name="Red")
        self.assertEqual(player.name, "Red")
        self.assertIsNotNone(player.unique_id)
        self.assertEqual(player.max_team_size, 6)
        self.assertIsNone(player.active_pokemon)

        # Player name cannot be empty
        with self.assertRaises(ValueError):
            Player(name="")

        with self.assertRaises(ValueError):
            Player(name="   ")

        # Invalid max_team_size
        with self.assertRaises(ValueError):
            Player(name="Red", max_team_size=0)

    # 2. Player starts with an empty collection.
    def test_02_player_starts_with_empty_collection(self) -> None:
        player = Player(name="Ash")
        self.assertEqual(len(player.collection), 0)
        self.assertEqual(player.get_all_pokemon(), [])
        self.assertEqual(len(player.team), 0)
        self.assertIsNone(player.active_pokemon)

    # 3. Pokémon can be added to collection.
    def test_03_pokemon_can_be_added_to_collection(self) -> None:
        player = Player(name="Ash")
        player.add_pokemon(self.pikachu)

        self.assertEqual(len(player.collection), 1)
        self.assertTrue(player.is_pokemon_owned(self.pikachu))
        self.assertTrue(player.has_pokemon(self.pikachu))
        self.assertIn(self.pikachu, player)

    # 4. Multiple Pokémon can be owned.
    def test_04_multiple_pokemon_can_be_owned(self) -> None:
        player = Player(name="Ash")
        player.add_pokemon(self.pikachu)
        player.add_pokemon(self.charmander)
        player.add_pokemon(self.squirtle)

        self.assertEqual(len(player.collection), 3)
        all_mon = player.get_all_pokemon()
        self.assertIn(self.pikachu, all_mon)
        self.assertIn(self.charmander, all_mon)
        self.assertIn(self.squirtle, all_mon)

    # 5. Duplicate Pokémon cannot be added.
    def test_05_duplicate_pokemon_cannot_be_added(self) -> None:
        player = Player(name="Ash")
        player.add_pokemon(self.pikachu)

        with self.assertRaises(ValueError):
            player.add_pokemon(self.pikachu)

    # 6. Pokémon can be retrieved by ID.
    def test_06_pokemon_can_be_retrieved_by_id(self) -> None:
        player = Player(name="Ash")
        player.add_pokemon(self.pikachu)

        retrieved = player.get_pokemon_by_id(self.pikachu.unique_id)
        self.assertIs(retrieved, self.pikachu)

        # Non-existent ID returns None
        self.assertIsNone(player.get_pokemon_by_id("99999"))

    # 7. Pokémon can be removed.
    def test_07_pokemon_can_be_removed(self) -> None:
        player = Player(name="Ash")
        player.add_pokemon(self.pikachu)
        self.assertTrue(player.is_pokemon_owned(self.pikachu))

        removed = player.remove_pokemon(self.pikachu)
        self.assertIs(removed, self.pikachu)
        self.assertEqual(len(player.collection), 0)
        self.assertFalse(player.is_pokemon_owned(self.pikachu))

        # Removing unowned Pokémon raises ValueError
        with self.assertRaises(ValueError):
            player.remove_pokemon(self.pikachu)

    # 8. Pokémon can be added to the team.
    def test_08_pokemon_can_be_added_to_team(self) -> None:
        player = Player(name="Ash")
        player.add_pokemon(self.pikachu)
        player.add_to_team(self.pikachu)

        self.assertEqual(len(player.team), 1)
        self.assertTrue(player.is_on_team(self.pikachu))
        self.assertIn(self.pikachu, player.get_team())

    # 9. Unowned Pokémon cannot be added to the team.
    def test_09_unowned_pokemon_cannot_be_added_to_team(self) -> None:
        player = Player(name="Ash")
        with self.assertRaises(ValueError):
            player.add_to_team(self.pikachu)

    # 10. Duplicate team entries are prevented.
    def test_10_duplicate_team_entries_are_prevented(self) -> None:
        player = Player(name="Ash")
        player.add_pokemon(self.pikachu)
        player.add_to_team(self.pikachu)

        with self.assertRaises(ValueError):
            player.add_to_team(self.pikachu)

    # 11. Team cannot exceed 6 Pokémon.
    def test_11_team_cannot_exceed_max_size(self) -> None:
        player = Player(name="Ash", max_team_size=6)
        team_members = [
            Pokemon(species=PIKACHU, personality=self.sample_personality, level=i + 1)
            for i in range(6)
        ]
        for mon in team_members:
            player.add_pokemon(mon)
            player.add_to_team(mon)

        self.assertEqual(len(player.team), 6)

        # 7th Pokemon cannot be added to team
        seventh_mon = Pokemon(species=CHARMANDER, personality=self.sample_personality, level=1)
        player.add_pokemon(seventh_mon)
        with self.assertRaises(ValueError):
            player.add_to_team(seventh_mon)

    # 12. Pokémon can be removed from the team.
    def test_12_pokemon_can_be_removed_from_team(self) -> None:
        player = Player(name="Ash")
        player.add_pokemon(self.pikachu)
        player.add_to_team(self.pikachu)

        removed = player.remove_from_team(self.pikachu)
        self.assertIs(removed, self.pikachu)
        self.assertEqual(len(player.team), 0)
        self.assertFalse(player.is_on_team(self.pikachu))

        # Still in collection!
        self.assertTrue(player.is_pokemon_owned(self.pikachu))

        # Removing a Pokemon not on team raises ValueError
        with self.assertRaises(ValueError):
            player.remove_from_team(self.pikachu)

    # 13. Active Pokémon can be selected.
    def test_13_active_pokemon_can_be_selected(self) -> None:
        player = Player(name="Ash")
        player.add_pokemon(self.pikachu)
        player.set_active_pokemon(self.pikachu)

        self.assertIs(player.get_active_pokemon(), self.pikachu)
        self.assertIs(player.active_pokemon, self.pikachu)

    # 14. Unowned Pokémon cannot become active.
    def test_14_unowned_pokemon_cannot_become_active(self) -> None:
        player = Player(name="Ash")
        with self.assertRaises(ValueError):
            player.set_active_pokemon(self.pikachu)

    # 15. Removing the active Pokémon clears the active Pokémon.
    def test_15_removing_active_pokemon_clears_active(self) -> None:
        player = Player(name="Ash")
        player.add_pokemon(self.pikachu)
        player.add_to_team(self.pikachu)
        player.set_active_pokemon(self.pikachu)
        self.assertIs(player.active_pokemon, self.pikachu)

        # Removing from team clears active pokemon
        player.remove_from_team(self.pikachu)
        self.assertIsNone(player.active_pokemon)

    # 16. Removing a Pokémon from the collection also removes it from the team.
    def test_16_removing_from_collection_removes_from_team(self) -> None:
        player = Player(name="Ash")
        player.add_pokemon(self.pikachu)
        player.add_to_team(self.pikachu)
        self.assertTrue(player.is_on_team(self.pikachu))

        player.remove_pokemon(self.pikachu)
        self.assertFalse(player.is_on_team(self.pikachu))
        self.assertEqual(len(player.team), 0)

    # 17. Removing a Pokémon from the collection clears active status if necessary.
    def test_17_removing_from_collection_clears_active_status(self) -> None:
        player = Player(name="Ash")
        player.add_pokemon(self.pikachu)
        player.set_active_pokemon(self.pikachu)
        self.assertIs(player.active_pokemon, self.pikachu)

        player.remove_pokemon(self.pikachu)
        self.assertIsNone(player.active_pokemon)

    # Additional tests: 5-digit unique ID generation
    def test_pokemon_ids_are_unique_5_digit_numbers(self) -> None:
        mon1 = Pokemon(species=PIKACHU, personality=self.sample_personality)
        mon2 = Pokemon(species=PIKACHU, personality=self.sample_personality)
        self.assertEqual(len(mon1.unique_id), 5)
        self.assertEqual(len(mon2.unique_id), 5)
        self.assertTrue(mon1.unique_id.isdigit())
        self.assertTrue(mon2.unique_id.isdigit())
        self.assertNotEqual(mon1.unique_id, mon2.unique_id)


if __name__ == "__main__":
    unittest.main()
