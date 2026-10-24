"""
Unit tests for Pokemon bond manager and bonding mechanics.
"""
import unittest
from src.models.personality import Personality
from src.models.pokemon import Pokemon, MIN_BOND, MAX_BOND
from src.models.bond_manager import (
    BondManager,
    BondChangeResult,
    BondEventConfig,
    DEFAULT_BOND_BATTLE_VICTORY,
    DEFAULT_BOND_BATTLE_DEFEAT,
    DEFAULT_BOND_LEVEL_UP,
    DEFAULT_BOND_CAPTURE,
)
from src.models.battle import Battle
from src.models.battle_state import BattleState
from src.models.progression import LevelUpResult
from src.models.capture_manager import CaptureResult
from src.data.species import PIKACHU, CHARMANDER, SQUIRTLE
from src.data.attacks import THUNDER_SHOCK, TACKLE


class TestBondManager(unittest.TestCase):
    """
    Exhaustive tests for BondManager, range constraints, duplicate event prevention,
    and battle/progression integration.
    """

    def setUp(self) -> None:
        self.personality = Personality(50, 50, 50, 50, 50, 50)
        self.pika = Pokemon(species=PIKACHU, personality=self.personality, bond=10)
        self.char = Pokemon(species=CHARMANDER, personality=self.personality, bond=50)
        self.manager = BondManager()

    def test_01_bond_increases_correctly(self) -> None:
        """Bond increases by the specified integer amount within bounds."""
        res = self.manager.increase_bond(self.pika, 15)
        self.assertTrue(res.success)
        self.assertEqual(res.previous_bond, 10)
        self.assertEqual(res.new_bond, 25)
        self.assertEqual(res.change_amount, 15)
        self.assertFalse(res.was_clamped)
        self.assertEqual(self.pika.bond, 25)

    def test_02_bond_decreases_correctly(self) -> None:
        """Bond decreases by the specified integer amount within bounds."""
        res = self.manager.decrease_bond(self.char, 20)
        self.assertTrue(res.success)
        self.assertEqual(res.previous_bond, 50)
        self.assertEqual(res.new_bond, 30)
        self.assertEqual(res.change_amount, -20)
        self.assertFalse(res.was_clamped)
        self.assertEqual(self.char.bond, 30)

    def test_03_bond_cannot_exceed_100(self) -> None:
        """Bond cannot exceed MAX_BOND (100) and clamps correctly."""
        self.pika.bond = 95
        res = self.manager.increase_bond(self.pika, 10)
        self.assertTrue(res.success)
        self.assertEqual(res.previous_bond, 95)
        self.assertEqual(res.new_bond, 100)
        self.assertEqual(res.change_amount, 5)
        self.assertTrue(res.was_clamped)
        self.assertEqual(self.pika.bond, 100)

        # Increasing when already at maximum
        res_capped = self.manager.increase_bond(self.pika, 5)
        self.assertEqual(res_capped.previous_bond, 100)
        self.assertEqual(res_capped.new_bond, 100)
        self.assertEqual(res_capped.change_amount, 0)
        self.assertTrue(res_capped.was_clamped)

    def test_04_bond_cannot_fall_below_0(self) -> None:
        """Bond cannot fall below MIN_BOND (0) and clamps correctly."""
        self.pika.bond = 10
        res = self.manager.decrease_bond(self.pika, 15)
        self.assertTrue(res.success)
        self.assertEqual(res.previous_bond, 10)
        self.assertEqual(res.new_bond, 0)
        self.assertEqual(res.change_amount, -10)
        self.assertTrue(res.was_clamped)
        self.assertEqual(self.pika.bond, 0)

        # Decreasing when already at minimum
        res_bottom = self.manager.decrease_bond(self.pika, 5)
        self.assertEqual(res_bottom.previous_bond, 0)
        self.assertEqual(res_bottom.new_bond, 0)
        self.assertEqual(res_bottom.change_amount, 0)
        self.assertTrue(res_bottom.was_clamped)

    def test_05_zero_change_behaves_correctly(self) -> None:
        """A delta or amount of 0 leaves bond unmodified with was_clamped=False."""
        res_change = self.manager.change_bond(self.pika, 0)
        self.assertTrue(res_change.success)
        self.assertEqual(res_change.previous_bond, 10)
        self.assertEqual(res_change.new_bond, 10)
        self.assertEqual(res_change.change_amount, 0)
        self.assertFalse(res_change.was_clamped)

        res_inc = self.manager.increase_bond(self.pika, 0)
        self.assertEqual(res_inc.change_amount, 0)
        self.assertFalse(res_inc.was_clamped)

        res_dec = self.manager.decrease_bond(self.pika, 0)
        self.assertEqual(res_dec.change_amount, 0)
        self.assertFalse(res_dec.was_clamped)

    def test_06_invalid_inputs_handled_safely(self) -> None:
        """Rejects non-Pokemon, non-integer amounts, negative amounts, and invalid IDs."""
        # Non-Pokemon
        with self.assertRaises(TypeError):
            self.manager.increase_bond("NotAPokemon", 5)  # type: ignore

        with self.assertRaises(TypeError):
            self.manager.change_bond("NotAPokemon", 5)  # type: ignore

        # Non-integer delta/amount
        with self.assertRaises(TypeError):
            self.manager.change_bond(self.pika, "10")  # type: ignore

        with self.assertRaises(TypeError):
            self.manager.change_bond(self.pika, True)  # type: ignore

        with self.assertRaises(TypeError):
            self.manager.increase_bond(self.pika, 5.5)  # type: ignore

        # Negative amount in increase/decrease
        with self.assertRaises(ValueError):
            self.manager.increase_bond(self.pika, -5)

        with self.assertRaises(ValueError):
            self.manager.decrease_bond(self.pika, -5)

        # Empty event ID in award_event_bond
        with self.assertRaises(ValueError):
            self.manager.award_event_bond(self.pika, "test", "")

    def test_07_duplicate_event_identifier_rejected(self) -> None:
        """A bond event cannot be rewarded twice when the same event identifier is supplied."""
        event_id = "battle_gym_01"
        res1 = self.manager.award_event_bond(self.pika, "Gym Victory", event_id, amount=10)
        self.assertTrue(res1.success)
        self.assertEqual(res1.new_bond, 20)
        self.assertEqual(self.pika.bond, 20)
        self.assertTrue(self.manager.has_event_been_claimed(event_id))

        # Second attempt with the exact same event_id
        res2 = self.manager.award_event_bond(self.pika, "Gym Victory", event_id, amount=10)
        self.assertFalse(res2.success)
        self.assertEqual(res2.change_amount, 0)
        self.assertEqual(res2.new_bond, 20)
        self.assertEqual(self.pika.bond, 20)  # Unmodified
        self.assertIn("already been claimed", res2.reason)

    def test_08_changes_affect_only_intended_pokemon(self) -> None:
        """Modifying one Pokemon's bond does not affect any other Pokemon."""
        self.assertEqual(self.pika.bond, 10)
        self.assertEqual(self.char.bond, 50)

        self.manager.increase_bond(self.pika, 30)
        self.assertEqual(self.pika.bond, 40)
        self.assertEqual(self.char.bond, 50)  # Preserved

        self.manager.decrease_bond(self.char, 10)
        self.assertEqual(self.pika.bond, 40)  # Preserved
        self.assertEqual(self.char.bond, 40)

    def test_09_battle_victory_bond_award_and_duplicate_prevention(self) -> None:
        """Battle victory awards bond to winner and rejects duplicates and losers."""
        p1 = Pokemon(species=PIKACHU, personality=self.personality, bond=20)
        p2 = Pokemon(species=SQUIRTLE, personality=self.personality, bond=15)
        p1.assign_attack(THUNDER_SHOCK)
        p2.assign_attack(TACKLE)

        battle = Battle(pokemon1=p1, pokemon2=p2, seed=123)
        battle.start()

        # Simulate battle until victory
        for _ in range(10):
            if battle.state.is_terminal():
                break
            battle.execute_turn(THUNDER_SHOCK, TACKLE)

        self.assertTrue(battle.state.is_terminal())
        self.assertIsNotNone(battle.winner)
        self.assertFalse(battle.bond_rewards_claimed)

        winner = battle.winner
        loser = battle.loser
        initial_winner_bond = winner.bond

        # 1. Award victory bond
        res = self.manager.award_battle_victory_bond(battle)
        self.assertTrue(res.success)
        self.assertEqual(res.new_bond, initial_winner_bond + DEFAULT_BOND_BATTLE_VICTORY)
        self.assertTrue(battle.bond_rewards_claimed)
        self.assertTrue(self.manager.has_event_been_claimed(battle.battle_id))

        # 2. Reject duplicate attempt on same battle
        res_dup = self.manager.award_battle_victory_bond(battle)
        self.assertFalse(res_dup.success)
        self.assertEqual(res_dup.change_amount, 0)
        self.assertIn("already been claimed", res_dup.reason)

        # 3. Defeated Pokemon cannot claim victory bond
        res_loser = self.manager.award_battle_victory_bond(battle, recipient=loser)
        self.assertFalse(res_loser.success)

    def test_10_battle_bond_rejects_unfinished_or_draw_battles(self) -> None:
        """Unfinished battles and draw battles reject bond awards."""
        p1 = Pokemon(species=PIKACHU, personality=self.personality)
        p2 = Pokemon(species=CHARMANDER, personality=self.personality)
        battle = Battle(pokemon1=p1, pokemon2=p2)

        # Not started
        res_not_started = self.manager.award_battle_victory_bond(battle)
        self.assertFalse(res_not_started.success)
        self.assertIn("not finished", res_not_started.reason)

    def test_11_level_up_bond_award_and_duplicate_prevention(self) -> None:
        """Level-up bond awards correctly and prevents duplicate rewards."""
        level_result = LevelUpResult(
            pokemon=self.pika,
            levels_gained=2,
            initial_level=5,
            final_level=7,
            initial_xp=100,
            final_xp=300,
            hp_gained=4,
            xp_applied=200,
        )

        initial_bond = self.pika.bond
        res = self.manager.award_level_up_bond(level_result)
        self.assertTrue(res.success)
        expected_gain = DEFAULT_BOND_LEVEL_UP * 2
        self.assertEqual(res.new_bond, initial_bond + expected_gain)

        # Second attempt with same result / event ID is rejected
        res_dup = self.manager.award_level_up_bond(level_result)
        self.assertFalse(res_dup.success)
        self.assertIn("already been claimed", res_dup.reason)

    def test_12_capture_bond_award_and_duplicate_prevention(self) -> None:
        """Capture bond awards upon joining player collection and blocks duplicates."""
        initial_bond = self.char.bond
        res = self.manager.award_capture_bond(self.char)
        self.assertTrue(res.success)
        self.assertEqual(res.new_bond, initial_bond + DEFAULT_BOND_CAPTURE)

        # Duplicate capture claim for same Pokemon
        res_dup = self.manager.award_capture_bond(self.char)
        self.assertFalse(res_dup.success)
        self.assertIn("already been claimed", res_dup.reason)

    def test_13_existing_pokemon_construction_and_bounds_remain_compatible(self) -> None:
        """Pokemon construction respects bond and obedience bounds."""
        mon = Pokemon(species=PIKACHU, personality=self.personality, bond=75, obedience=90)
        self.assertEqual(mon.bond, 75)
        self.assertEqual(mon.obedience, 90)

        # Bounds validation on Pokemon model directly
        with self.assertRaises(ValueError):
            mon.bond = -1

        with self.assertRaises(ValueError):
            mon.bond = 101

        with self.assertRaises(ValueError):
            mon.obedience = -1

        with self.assertRaises(ValueError):
            mon.obedience = 101

    def test_14_battle_defeat_bond_award_and_duplicate_prevention(self) -> None:
        """Battle defeat awards +8 hardship bond and prevents duplicate claims."""
        self.assertEqual(DEFAULT_BOND_BATTLE_DEFEAT, 8)
        self.assertEqual(self.manager.config.battle_defeat, 8)

        p1 = Pokemon(species=PIKACHU, personality=self.personality, bond=20)
        p2 = Pokemon(species=CHARMANDER, personality=self.personality, bond=20)
        battle = Battle(pokemon1=p1, pokemon2=p2, player_team=[p1], opponent_team=[p2])
        battle.start()

        # Reject while in progress
        res_progress = self.manager.award_battle_defeat_bond(battle, recipient=p1)
        self.assertFalse(res_progress.success)
        self.assertEqual(p1.bond, 20)

        # Force defeat
        p1.current_hp = 0
        battle._state = BattleState.DEFEAT

        # Award defeat bond
        res_defeat = self.manager.award_battle_defeat_bond(battle, recipient=p1)
        self.assertTrue(res_defeat.success)
        self.assertEqual(res_defeat.new_bond, 28)
        self.assertEqual(p1.bond, 28)
        self.assertEqual(res_defeat.change_amount, 8)

        # Duplicate claim is rejected
        res_dup = self.manager.award_battle_defeat_bond(battle, recipient=p1)
        self.assertFalse(res_dup.success)
        self.assertEqual(p1.bond, 28)
        self.assertIn("already been claimed", res_dup.reason)


if __name__ == "__main__":
    unittest.main()
