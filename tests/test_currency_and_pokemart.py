"""Unit tests for the Currency System, PokéMart Vending Machine, and Battle Rewards."""

import unittest
import os
import tempfile
from src.models.player import Player
from src.models.pokemart import PokeMart
from src.models.pokemon import Pokemon
from src.models.personality import Personality
from src.models.trainer import Trainer, DifficultyProfile
from src.models.battle import BattleState
from src.models.battle_manager import BattleManager
from src.models.save_manager import SaveManager, serialize_player, deserialize_player
from src.data.species import PIKACHU, PIDGEY
from src.data.attacks import THUNDER_SHOCK, TACKLE


class TestCurrencyAndPokeMart(unittest.TestCase):
    """Test suite for player currency, PokéMart vending machine, and battle prize rewards."""

    def setUp(self):
        self.personality = Personality(
            aggression=50,
            curiosity=50,
            fear=50,
            sociability=50,
            loyalty=50,
            confidence=50,
        )
        self.player = Player(name="Red")

    def test_initial_currency(self):
        """Player must begin with exactly 500 PokéDollars (500p)."""
        self.assertEqual(self.player.currency, 500)

    def test_add_currency(self):
        """Adding currency increments the wallet balance correctly."""
        self.player.add_currency(200)
        self.assertEqual(self.player.currency, 700)

        with self.assertRaises(ValueError):
            self.player.add_currency(-50)

    def test_can_afford(self):
        """can_afford checks if player has sufficient funds."""
        self.assertTrue(self.player.can_afford(500))
        self.assertTrue(self.player.can_afford(50))
        self.assertTrue(self.player.can_afford(0))
        self.assertFalse(self.player.can_afford(501))

    def test_spend_currency(self):
        """spend_currency deducts currency on success and rejects on insufficient funds."""
        self.assertTrue(self.player.spend_currency(150))
        self.assertEqual(self.player.currency, 350)

        # Cannot spend more than balance
        self.assertFalse(self.player.spend_currency(400))
        self.assertEqual(self.player.currency, 350)  # Balance unchanged

        # Cannot spend negative
        with self.assertRaises(ValueError):
            self.player.spend_currency(-10)

    def test_pokemart_pricing_and_catalog(self):
        """PokéMart catalog prices must be exactly 50p for poke_ball and 150p for potion."""
        mart = PokeMart()
        self.assertEqual(mart.get_price("poke_ball"), 50)
        self.assertEqual(mart.get_price("potion"), 150)
        self.assertIsNone(mart.get_price("master_ball"))

    def test_pokemart_buy_pokeball(self):
        """Buying a Poké Ball costs 50p and adds 1 poke_ball to inventory."""
        mart = PokeMart()
        init_balls = self.player.inventory.get_quantity("poke_ball")
        init_currency = self.player.currency

        success, msg = mart.buy(self.player, "poke_ball", quantity=1)
        self.assertTrue(success)
        self.assertEqual(self.player.currency, init_currency - 50)
        self.assertEqual(self.player.inventory.get_quantity("poke_ball"), init_balls + 1)
        self.assertIn("Successfully purchased 1x Poké Ball for 50p", msg)

    def test_pokemart_buy_potion(self):
        """Buying a Potion costs 150p and adds 1 potion to inventory."""
        mart = PokeMart()
        init_potions = self.player.inventory.get_quantity("potion")
        init_currency = self.player.currency

        success, msg = mart.buy(self.player, "potion", quantity=2)
        self.assertTrue(success)
        self.assertEqual(self.player.currency, init_currency - 300)
        self.assertEqual(self.player.inventory.get_quantity("potion"), init_potions + 2)
        self.assertIn("Successfully purchased 2x Potion for 300p", msg)

    def test_pokemart_insufficient_funds(self):
        """Purchase is rejected when player cannot afford the total cost."""
        mart = PokeMart()
        self.player.spend_currency(450)  # Left with 50p
        self.assertEqual(self.player.currency, 50)

        # Cannot afford 150p potion
        success, msg = mart.buy(self.player, "potion", quantity=1)
        self.assertFalse(success)
        self.assertEqual(self.player.currency, 50)
        self.assertIn("Insufficient funds", msg)

    def test_pokemart_invalid_item_or_qty(self):
        """Purchasing unknown item or non-positive quantity fails cleanly."""
        mart = PokeMart()
        success, msg = mart.buy(self.player, "bicycle", quantity=1)
        self.assertFalse(success)
        self.assertIn("not sold", msg)

        success, msg = mart.buy(self.player, "poke_ball", quantity=0)
        self.assertFalse(success)
        self.assertIn("positive integer", msg)

    def test_battle_victory_earns_currency(self):
        """Winning a battle awards currency to the player."""
        p1 = Pokemon(
            species=PIKACHU,
            personality=self.personality,
            level=25,
            attacks=[THUNDER_SHOCK],
        )
        self.player.add_pokemon(p1)
        self.player.add_to_team(p1)
        self.player.set_active_pokemon(p1)

        opp_mon = Pokemon(
            species=PIDGEY,
            personality=self.personality,
            level=4,
            attacks=[TACKLE],
        )
        trainer = Trainer(
            trainer_id="youngster_joey",
            name="Joey",
            title="Youngster Joey",
            difficulty=DifficultyProfile.EASY,
            team=[opp_mon],
        )

        bm = BattleManager(seed=42)
        battle = bm.start_trainer_battle(player=self.player, opponent_trainer=trainer, seed=42)

        init_currency = self.player.currency
        # Set opponent to 1 HP so any hit will faint it
        opp_mon.take_damage(opp_mon.max_hp - 1)
        self.assertEqual(opp_mon.current_hp, 1)

        result = bm.attack(self.player, THUNDER_SHOCK)
        self.assertTrue(result.accepted)
        self.assertEqual(battle.state, BattleState.VICTORY)

        # Opponent level 4: currency reward is max(50, 4 * 25) = 100
        self.assertEqual(self.player.currency, init_currency + 100)

    def test_save_manager_currency_persistence(self):
        """SaveManager persists and reloads currency accurately."""
        self.player.add_currency(750)
        self.assertEqual(self.player.currency, 1250)

        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = os.path.join(tmpdir, "test_save.json")
            SaveManager.save(self.player, save_path)
            self.assertTrue(os.path.exists(save_path))

            loaded_player = SaveManager.load(save_path)
            self.assertIsNotNone(loaded_player)
            self.assertEqual(loaded_player.currency, 1250)

    def test_save_manager_backward_compatibility(self):
        """Older save files missing 'currency' key default safely to 500."""
        # Use valid serialized dict and strip "currency" from player dict
        data = serialize_player(self.player)
        self.assertIn("player", data)
        self.assertIn("currency", data["player"])
        del data["player"]["currency"]

        loaded_player = deserialize_player(data)
        self.assertEqual(loaded_player.currency, 500)


if __name__ == "__main__":
    unittest.main()
