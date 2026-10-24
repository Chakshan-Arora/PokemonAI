"""
Unit tests for the ExperienceManager post-battle reward service.

Tests verify:
- XP is awarded to the winning Pokemon after a decisive battle.
- XP reward scales according to the defeated Pokemon's level (level * 50).
- Defeated Pokemon cannot receive victory rewards.
- Draw battles do not award victory XP.
- Unfinished battles do not award victory XP.
- Duplicate reward claims for the same battle are strictly prevented.
- XP rewards can trigger single or multiple level-ups.
- Winner and loser are identified correctly regardless of player/opponent perspective.
- Structured BattleRewardResult contains accurate progression metrics.
- Configurable reward multiplier.
"""
import unittest

from src.models.personality import Personality
from src.models.pokemon import Pokemon
from src.models.attack import Attack
from src.models.battle import Battle
from src.models.battle_state import BattleState
from src.models.experience_manager import (
    DEFAULT_XP_REWARD_MULTIPLIER,
    BattleRewardResult,
    ExperienceManager,
    calculate_battle_xp_reward,
)
from src.data.species import PIKACHU, CHARMANDER, SQUIRTLE
from src.data.attacks import THUNDER_SHOCK, SCRATCH, WATER_GUN


class TestExperienceManager(unittest.TestCase):
    """Test suite for battle XP rewards, outcome verification, and anti-duplication."""

    def setUp(self) -> None:
        self.personality = Personality(
            aggression=50,
            curiosity=50,
            fear=50,
            sociability=50,
            loyalty=50,
            confidence=50,
        )
        self.pikachu = Pokemon(
            species=PIKACHU,
            personality=self.personality,
            level=5,
            experience=0,
            attacks=[THUNDER_SHOCK],
        )
        self.charmander = Pokemon(
            species=CHARMANDER,
            personality=self.personality,
            level=5,
            experience=0,
            attacks=[SCRATCH],
        )
        self.manager = ExperienceManager()

    # --- XP Calculation ---

    def test_calculate_battle_xp_reward(self) -> None:
        """XP reward equals defeated level multiplied by multiplier (default 50)."""
        self.assertEqual(calculate_battle_xp_reward(1), 50)
        self.assertEqual(calculate_battle_xp_reward(5), 250)
        self.assertEqual(calculate_battle_xp_reward(10), 500)
        self.assertEqual(calculate_battle_xp_reward(20, multiplier=100), 2000)

        # Invalid arguments
        with self.assertRaises(ValueError):
            calculate_battle_xp_reward(0)
        with self.assertRaises(ValueError):
            calculate_battle_xp_reward(-3)
        with self.assertRaises(TypeError):
            calculate_battle_xp_reward("5")  # type: ignore[arg-type]

    # --- Valid Victory Reward ---

    def test_xp_awarded_after_valid_victory(self) -> None:
        """Winner receives XP based on defeated opponent's level."""
        battle = Battle(self.pikachu, self.charmander, seed=42)
        battle.start()
        # Set Charmander HP to 1 so Pikachu knocks it out immediately
        self.charmander.current_hp = 1
        turn_res = battle.resolve_turn(attack1=THUNDER_SHOCK, attack2=SCRATCH)

        self.assertEqual(battle.state, BattleState.VICTORY)
        self.assertEqual(battle.winner, self.pikachu)
        self.assertEqual(battle.loser, self.charmander)
        self.assertTrue(self.manager.can_award_rewards(battle))

        # Award rewards: Charmander is level 5 -> 5 * 50 = 250 XP
        result = self.manager.award_battle_rewards(battle)

        self.assertTrue(result.eligible)
        self.assertEqual(result.xp_awarded, 250)
        self.assertEqual(result.winner, self.pikachu)
        self.assertEqual(result.loser, self.charmander)
        self.assertEqual(result.recipient, self.pikachu)
        self.assertEqual(self.pikachu.experience, 250)
        self.assertEqual(result.levels_gained, 0)  # Needs 500 XP at Lv 5

    def test_rewards_scale_with_defeated_pokemon_level(self) -> None:
        """Higher-level defeated Pokemon yields proportionally higher XP."""
        high_lvl_char = Pokemon(
            species=CHARMANDER,
            personality=self.personality,
            level=10,
            attacks=[SCRATCH],
        )
        battle = Battle(self.pikachu, high_lvl_char, seed=42)
        battle.start()
        high_lvl_char.current_hp = 1
        battle.resolve_turn(attack1=THUNDER_SHOCK, attack2=SCRATCH)

        # Defeated level 10 -> 10 * 50 = 500 XP
        result = self.manager.award_battle_rewards(battle)
        self.assertEqual(result.xp_awarded, 500)
        # Pikachu was level 5 (needs 500 XP) -> levels up to level 6!
        self.assertEqual(result.levels_gained, 1)
        self.assertEqual(result.final_level, 6)
        self.assertEqual(self.pikachu.level, 6)
        self.assertEqual(self.pikachu.experience, 0)

    # --- Winner and Loser Perspective Independence ---

    def test_victory_when_second_pokemon_wins(self) -> None:
        """When pokemon2 defeats pokemon1 (DEFEAT state), pokemon2 receives victory reward."""
        fast_char = Pokemon(species=CHARMANDER, personality=self.personality, level=8, attacks=[SCRATCH])
        slow_pika = Pokemon(species=PIKACHU, personality=self.personality, level=5, attacks=[THUNDER_SHOCK])

        battle = Battle(slow_pika, fast_char, seed=1)
        battle.start()
        slow_pika.current_hp = 1  # Fast Charmander defeats slow Pikachu
        battle.resolve_turn(attack1=THUNDER_SHOCK, attack2=SCRATCH)

        self.assertEqual(battle.state, BattleState.DEFEAT)
        self.assertEqual(battle.winner, fast_char)
        self.assertEqual(battle.loser, slow_pika)

        # Award rewards -> recipient is fast_char (the actual winner)
        result = self.manager.award_battle_rewards(battle)
        self.assertTrue(result.eligible)
        self.assertEqual(result.recipient, fast_char)
        # Defeated Pokemon level was 5 -> 5 * 50 = 250 XP
        self.assertEqual(result.xp_awarded, 250)
        self.assertEqual(fast_char.experience, 250)

    # --- Defeated Pokemon Rejection ---

    def test_defeated_pokemon_cannot_receive_rewards(self) -> None:
        """Explicitly requesting rewards for the defeated Pokemon is rejected."""
        battle = Battle(self.pikachu, self.charmander, seed=42)
        battle.start()
        self.charmander.current_hp = 1
        battle.resolve_turn(attack1=THUNDER_SHOCK, attack2=SCRATCH)

        # Attempt to award rewards to Charmander (loser)
        result = self.manager.award_battle_rewards(battle, recipient=self.charmander)
        self.assertFalse(result.eligible)
        self.assertEqual(result.xp_awarded, 0)
        self.assertEqual(self.charmander.experience, 0)

        # With raise_on_ineligible=True
        with self.assertRaises(ValueError):
            self.manager.award_battle_rewards(battle, recipient=self.charmander, raise_on_ineligible=True)

    # --- Draw Battle Rejection ---

    def test_draw_battle_does_not_award_victory_xp(self) -> None:
        """A battle ending in a draw awards no victory XP."""
        battle = Battle(self.pikachu, self.charmander, seed=42)
        battle.start()
        self.pikachu.take_damage(self.pikachu.max_hp)
        self.charmander.take_damage(self.charmander.max_hp)
        battle._update_terminal_state()

        self.assertEqual(battle.state, BattleState.DRAW)
        self.assertFalse(self.manager.can_award_rewards(battle))

        result = self.manager.award_battle_rewards(battle)
        self.assertFalse(result.eligible)
        self.assertEqual(result.xp_awarded, 0)
        self.assertIn("draw", result.reason.lower())

        with self.assertRaises(RuntimeError):
            self.manager.award_battle_rewards(battle, raise_on_ineligible=True)

    # --- Unfinished Battle Rejection ---

    def test_unfinished_battle_does_not_award_victory_xp(self) -> None:
        """An in-progress or not-started battle awards no XP."""
        battle = Battle(self.pikachu, self.charmander)
        # Battle NOT_STARTED
        self.assertFalse(self.manager.can_award_rewards(battle))
        res_not_started = self.manager.award_battle_rewards(battle)
        self.assertFalse(res_not_started.eligible)
        self.assertEqual(res_not_started.xp_awarded, 0)

        # Battle IN_PROGRESS
        battle.start()
        self.assertFalse(self.manager.can_award_rewards(battle))
        res_in_prog = self.manager.award_battle_rewards(battle)
        self.assertFalse(res_in_prog.eligible)
        self.assertEqual(res_in_prog.xp_awarded, 0)

        with self.assertRaises(RuntimeError):
            self.manager.award_battle_rewards(battle, raise_on_ineligible=True)

    # --- Prevention of Repeated / Duplicate Claims ---

    def test_rewards_cannot_be_claimed_repeatedly(self) -> None:
        """Calling award_battle_rewards twice on the same battle awards XP only once."""
        battle = Battle(self.pikachu, self.charmander, seed=42)
        battle.start()
        self.charmander.current_hp = 1
        battle.resolve_turn(attack1=THUNDER_SHOCK, attack2=SCRATCH)

        # First claim succeeds
        res1 = self.manager.award_battle_rewards(battle)
        self.assertTrue(res1.eligible)
        self.assertEqual(res1.xp_awarded, 250)
        self.assertEqual(self.pikachu.experience, 250)

        # Battle is no longer eligible
        self.assertFalse(self.manager.can_award_rewards(battle))
        self.assertTrue(battle.rewards_claimed)

        # Second claim fails safely
        res2 = self.manager.award_battle_rewards(battle)
        self.assertFalse(res2.eligible)
        self.assertEqual(res2.xp_awarded, 0)
        # Pikachu XP does NOT increase again
        self.assertEqual(self.pikachu.experience, 250)

        # With raise_on_ineligible=True
        with self.assertRaises(RuntimeError):
            self.manager.award_battle_rewards(battle, raise_on_ineligible=True)

    # --- Multiple Level-Ups Triggered from Battle Reward ---

    def test_battle_rewards_trigger_multiple_level_ups(self) -> None:
        """High-level opponent victory award can trigger multiple levels simultaneously."""
        boss_char = Pokemon(species=CHARMANDER, personality=self.personality, level=40, attacks=[SCRATCH])
        low_pika = Pokemon(species=PIKACHU, personality=self.personality, level=1, experience=0, attacks=[THUNDER_SHOCK])

        battle = Battle(low_pika, boss_char, seed=42)
        battle.start()
        boss_char.current_hp = 1
        battle.resolve_turn(attack1=THUNDER_SHOCK, attack2=SCRATCH)

        # Defeated Lv 40 -> 40 * 50 = 2000 XP
        # Low Pikachu at level 1:
        # Lv 1 -> 2: 100 XP
        # Lv 2 -> 3: 200 XP
        # Lv 3 -> 4: 300 XP
        # Lv 4 -> 5: 400 XP
        # Lv 5 -> 6: 500 XP
        # Total for Lv 6 = 1500 XP. Remainder = 500 XP at Lv 6 (which needs 600 XP).
        result = self.manager.award_battle_rewards(battle)

        self.assertTrue(result.eligible)
        self.assertEqual(result.xp_awarded, 2000)
        self.assertEqual(result.levels_gained, 5)
        self.assertEqual(result.initial_level, 1)
        self.assertEqual(result.final_level, 6)
        self.assertEqual(low_pika.level, 6)
        self.assertEqual(low_pika.experience, 500)
        # Max HP at Lv 1 was 11 + 2 = 13. At Lv 6: 11 + 12 = 23 (+10 HP).
        self.assertEqual(result.hp_gained, 10)
        self.assertEqual(low_pika.max_hp, 23)


if __name__ == "__main__":
    unittest.main()
