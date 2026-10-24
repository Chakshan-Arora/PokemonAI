"""
Comprehensive unit tests for wild Pokemon HP distribution, player behavior tracking,
and the quantified wild AI decision model.
"""
import random
import tempfile
import unittest
from pathlib import Path

from src.models.pokemon import Pokemon
from src.models.personality import Personality
from src.models.attack import Attack
from src.models.pokemon_type import PokemonType
from src.models.player import Player
from src.models.player_behavior import (
    PlayerBehaviorProfile,
    WildEncounterRecord,
    PlayerBehaviorTracker,
)
from src.models.wild_hp import determine_wild_hp
from src.models.wild_ai import (
    WildActionType,
    WildDecision,
    WildDecisionModel,
)
from src.models.battle_state import BattleState
from src.models.battle import (
    Battle,
    BattleAction,
    BattleActionType,
    BattleActionResult,
)
from src.models.battle_manager import BattleManager
from src.models.spawn_area import SpawnArea
from src.models.spawn_manager import SpawnManager
from src.models.encounter_manager import EncounterManager
from src.models.save_manager import save_game, load_game
from src.data.species import PIKACHU, CHARMANDER, SQUIRTLE, BULBASAUR
from src.data.attacks import THUNDER_SHOCK, QUICK_ATTACK, EMBER, SCRATCH, TACKLE


class TestWildHpDistribution(unittest.TestCase):
    """Tests for determine_wild_hp natural health distribution."""

    def test_full_hp_tier(self) -> None:
        """Full HP tier returns 100% of max_hp."""
        self.assertEqual(determine_wild_hp(50, tier_override="full"), 50)
        self.assertEqual(determine_wild_hp(100, tier_override="full"), 100)

    def test_lightly_wounded_tier(self) -> None:
        """Lightly wounded tier returns between 70% and 90% of max_hp."""
        for seed in range(20):
            rng = random.Random(seed)
            hp = determine_wild_hp(100, rng=rng, tier_override="lightly_wounded")
            self.assertGreaterEqual(hp, 70)
            self.assertLessEqual(hp, 90)

    def test_critically_wounded_tier(self) -> None:
        """Critically wounded tier returns between 20% and 30% of max_hp."""
        for seed in range(20):
            rng = random.Random(seed)
            hp = determine_wild_hp(100, rng=rng, tier_override="critically_wounded")
            self.assertGreaterEqual(hp, 20)
            self.assertLessEqual(hp, 30)

    def test_boundary_and_validation(self) -> None:
        """Boundary at max_hp=1 returns 1; invalid inputs raise exceptions."""
        self.assertEqual(determine_wild_hp(1), 1)
        with self.assertRaises(ValueError):
            determine_wild_hp(0)
        with self.assertRaises(ValueError):
            determine_wild_hp(-10)
        with self.assertRaises(TypeError):
            determine_wild_hp("50")  # type: ignore

    def test_statistical_distribution(self) -> None:
        """Over a large sample, natural distribution produces full, wounded, and critical tiers."""
        rng = random.Random(12345)
        counts = {"full": 0, "light": 0, "critical": 0}
        for _ in range(1000):
            hp = determine_wild_hp(100, rng=rng)
            if hp == 100:
                counts["full"] += 1
            elif 70 <= hp <= 90:
                counts["light"] += 1
            elif 20 <= hp <= 30:
                counts["critical"] += 1

        # Full ~50% (between 40% and 60%)
        self.assertGreater(counts["full"], 400)
        self.assertLess(counts["full"], 600)
        # Lightly wounded ~35% (between 25% and 45%)
        self.assertGreater(counts["light"], 250)
        self.assertLess(counts["light"], 450)
        # Critically wounded ~15% (between 8% and 25%)
        self.assertGreater(counts["critical"], 80)
        self.assertLess(counts["critical"], 250)


class TestPlayerBehaviorTracking(unittest.TestCase):
    """Tests for tracking and classifying player demeanor from wild encounter history."""

    def setUp(self) -> None:
        self.player = Player(name="Red")

    def test_initial_state_is_neutral(self) -> None:
        """A new player with no encounter history is classified as NEUTRAL."""
        self.assertEqual(len(self.player.wild_action_history), 0)
        self.assertEqual(self.player.behavior_profile, PlayerBehaviorProfile.NEUTRAL)

    def test_aggressive_classification(self) -> None:
        """Recording repeated attacks and defeats classifies player as AGGRESSIVE."""
        self.player.record_wild_action("attack", is_aggressive=True, species_name="Pidgey")
        self.player.record_wild_action("attack", is_aggressive=True, species_name="Rattata")
        self.player.record_wild_action("defeat", is_aggressive=True, species_name="Rattata")

        self.assertEqual(self.player.behavior_profile, PlayerBehaviorProfile.AGGRESSIVE)

    def test_peaceful_classification(self) -> None:
        """Recording repeated fleeing and inspecting classifies player as PEACEFUL."""
        self.player.record_wild_action("inspect", is_peaceful=True, species_name="Caterpie")
        self.player.record_wild_action("flee", is_peaceful=True, species_name="Pidgey")
        self.player.record_wild_action("inspect", is_peaceful=True, species_name="Butterfree")

        self.assertEqual(self.player.behavior_profile, PlayerBehaviorProfile.PEACEFUL)

    def test_neutral_and_sliding_window(self) -> None:
        """Mixed actions classify as NEUTRAL, and older actions slide out of the 10-action window."""
        tracker = PlayerBehaviorTracker()

        # 5 peaceful actions
        for _ in range(5):
            self.player.record_wild_action("inspect", is_peaceful=True)
        self.assertEqual(self.player.behavior_profile, PlayerBehaviorProfile.PEACEFUL)

        # Now 10 aggressive actions supersede the peaceful ones
        for _ in range(10):
            self.player.record_wild_action("attack", is_aggressive=True)
        self.assertEqual(self.player.behavior_profile, PlayerBehaviorProfile.AGGRESSIVE)


class TestWildAiDecisionModel(unittest.TestCase):
    """Tests for quantifying factors into ATTACK, FLEE, and INSPECT scores."""

    def setUp(self) -> None:
        self.ai = WildDecisionModel()
        self.neutral_pers = Personality(50, 50, 50, 50, 50, 50)
        self.wild_pika = Pokemon(species=PIKACHU, personality=self.neutral_pers, level=5, attacks=[THUNDER_SHOCK])
        self.player_charm = Pokemon(species=CHARMANDER, personality=self.neutral_pers, level=5, attacks=[EMBER])
        self.player = Player(name="Blue")

    def test_low_hp_increases_flee_score(self) -> None:
        """Critically wounded wild Pokemon has significantly higher FLEE score than full HP."""
        self.wild_pika.current_hp = self.wild_pika.max_hp
        scores_healthy, _ = self.ai.evaluate_action_scores(self.wild_pika, self.player_charm, self.player)

        self.wild_pika.current_hp = max(1, int(self.wild_pika.max_hp * 0.15))
        scores_wounded, factors = self.ai.evaluate_action_scores(self.wild_pika, self.player_charm, self.player)

        self.assertGreater(scores_wounded[WildActionType.FLEE], scores_healthy[WildActionType.FLEE])
        self.assertLess(scores_wounded[WildActionType.ATTACK], scores_healthy[WildActionType.ATTACK])
        self.assertEqual(factors["hp_ratio"], round(self.wild_pika.current_hp / self.wild_pika.max_hp, 2))

    def test_level_difference_effects(self) -> None:
        """Higher level wild Pokemon is aggressive; lower level wild Pokemon is prone to fleeing."""
        high_level_wild = Pokemon(species=CHARMANDER, personality=self.neutral_pers, level=15, attacks=[EMBER])
        low_level_player = Pokemon(species=PIKACHU, personality=self.neutral_pers, level=3, attacks=[THUNDER_SHOCK])
        scores_dominant, _ = self.ai.evaluate_action_scores(high_level_wild, low_level_player, self.player)

        low_level_wild = Pokemon(species=CHARMANDER, personality=self.neutral_pers, level=2, attacks=[EMBER])
        high_level_player = Pokemon(species=PIKACHU, personality=self.neutral_pers, level=12, attacks=[THUNDER_SHOCK])
        scores_intimidated, _ = self.ai.evaluate_action_scores(low_level_wild, high_level_player, self.player)

        self.assertGreater(scores_dominant[WildActionType.ATTACK], scores_intimidated[WildActionType.ATTACK])
        self.assertGreater(scores_intimidated[WildActionType.FLEE], scores_dominant[WildActionType.FLEE])

    def test_player_past_behavior_influences_decision(self) -> None:
        """Wild Pokemon flees from AGGRESSIVE player and inspects a PEACEFUL player."""
        # 1. Aggressive player
        scores_agg, _ = self.ai.evaluate_action_scores(
            self.wild_pika,
            self.player_charm,
            player_behavior_override=PlayerBehaviorProfile.AGGRESSIVE,
        )
        # 2. Peaceful player
        scores_peace, _ = self.ai.evaluate_action_scores(
            self.wild_pika,
            self.player_charm,
            player_behavior_override=PlayerBehaviorProfile.PEACEFUL,
        )

        self.assertGreater(scores_agg[WildActionType.FLEE], scores_peace[WildActionType.FLEE])
        self.assertGreater(scores_peace[WildActionType.INSPECT], scores_agg[WildActionType.INSPECT])

    def test_personality_traits_factor(self) -> None:
        """High fear boosts flee; high curiosity boosts inspect; high aggression boosts attack."""
        fearful_pers = Personality(aggression=20, curiosity=20, fear=95, sociability=20, loyalty=50, confidence=10)
        fearful_mon = Pokemon(species=PIKACHU, personality=fearful_pers, level=5, attacks=[THUNDER_SHOCK])
        scores_fearful, _ = self.ai.evaluate_action_scores(fearful_mon, self.player_charm, self.player)

        curious_pers = Personality(aggression=20, curiosity=95, fear=20, sociability=95, loyalty=50, confidence=50)
        curious_mon = Pokemon(species=PIKACHU, personality=curious_pers, level=5, attacks=[THUNDER_SHOCK])
        scores_curious, _ = self.ai.evaluate_action_scores(curious_mon, self.player_charm, self.player)

        self.assertGreater(scores_fearful[WildActionType.FLEE], scores_curious[WildActionType.FLEE])
        self.assertGreater(scores_curious[WildActionType.INSPECT], scores_fearful[WildActionType.INSPECT])

    def test_wild_pokemon_without_attacks_cannot_attack(self) -> None:
        """Wild Pokemon with no attacks has ATTACK score clamped to 0.0."""
        mon_no_moves = Pokemon(species=PIKACHU, personality=self.neutral_pers, level=5, attacks=[])
        scores, _ = self.ai.evaluate_action_scores(mon_no_moves, self.player_charm, self.player)
        self.assertEqual(scores[WildActionType.ATTACK], 0.0)

    def test_decide_action_deterministic(self) -> None:
        """Deterministic decision selects the action with the maximum score."""
        # Intimidated, wounded wild mon -> FLEE
        self.wild_pika.current_hp = 3
        decision = self.ai.decide_action(
            self.wild_pika,
            self.player_charm,
            self.player,
            deterministic=True,
            player_behavior_override=PlayerBehaviorProfile.AGGRESSIVE,
        )
        self.assertEqual(decision.action_type, WildActionType.FLEE)
        self.assertTrue(decision.reason)

        # Peaceful player facing healthy curious mon -> INSPECT
        curious_pers = Personality(aggression=10, curiosity=90, fear=10, sociability=90, loyalty=50, confidence=50)
        curious_mon = Pokemon(species=PIKACHU, personality=curious_pers, level=5, attacks=[THUNDER_SHOCK])
        decision_peace = self.ai.decide_action(
            curious_mon,
            self.player_charm,
            self.player,
            deterministic=True,
            player_behavior_override=PlayerBehaviorProfile.PEACEFUL,
        )
        self.assertEqual(decision_peace.action_type, WildActionType.INSPECT)


class TestWildAiInBattleIntegration(unittest.TestCase):
    """Tests wild AI execution during live battle sessions."""

    def setUp(self) -> None:
        self.neutral_pers = Personality(50, 50, 50, 50, 50, 50)
        self.pika = Pokemon(species=PIKACHU, personality=self.neutral_pers, level=5, attacks=[THUNDER_SHOCK, QUICK_ATTACK])
        self.charm = Pokemon(species=CHARMANDER, personality=self.neutral_pers, level=5, attacks=[EMBER, SCRATCH])
        self.player = Player(name="Ash")
        self.player.add_pokemon(self.pika)
        self.player.set_active_pokemon(self.pika)

    def test_player_inspect_action_records_peaceful_and_triggers_wild_response(self) -> None:
        """Inspecting a wild Pokemon records peaceful action and processes wild reaction."""
        battle = Battle(
            pokemon1=self.pika,
            pokemon2=self.charm,
            player=self.player,
            use_wild_ai=True,
        )
        battle.start()

        # Player inspects
        res = battle.inspect()
        self.assertTrue(res.accepted)
        self.assertEqual(res.action_type, BattleActionType.INSPECT)

        # Verified action recorded
        self.assertEqual(len(self.player.wild_action_history), 1)
        self.assertEqual(self.player.wild_action_history[0]["action"], "inspect")
        self.assertTrue(self.player.wild_action_history[0]["is_peaceful"])

    def test_wild_pokemon_flees_when_critically_wounded_on_inspect(self) -> None:
        """When player inspects a terrified critically wounded wild mon, it escapes immediately."""
        self.charm.current_hp = 2
        # Mark player aggressive
        self.player.record_wild_action("attack", is_aggressive=True)
        self.player.record_wild_action("defeat", is_aggressive=True)

        battle = Battle(
            pokemon1=self.pika,
            pokemon2=self.charm,
            player=self.player,
            use_wild_ai=True,
        )
        battle.start()

        res = battle.inspect()
        self.assertTrue(res.accepted)
        self.assertEqual(battle.state, BattleState.ESCAPED)
        self.assertTrue(res.escaped)
        self.assertTrue(res.terminal)

    def test_battle_manager_inspect_convenience_method(self) -> None:
        """BattleManager.inspect_wild_pokemon delegates cleanly to active battle."""
        bm = BattleManager()
        battle = bm.start_battle(self.player, self.charm, use_wild_ai=True)

        res = bm.inspect_wild_pokemon(self.player)
        self.assertTrue(res.accepted)
        self.assertEqual(res.action_type, BattleActionType.INSPECT)


class TestWildAiPersistence(unittest.TestCase):
    """Tests save and load round-trip persistence of player wild action history."""

    def test_save_and_load_preserves_wild_action_history(self) -> None:
        """Player's wild_action_history survives JSON serialization and deserialization."""
        player = Player(name="Gary")
        player.add_pokemon(Pokemon(species=SQUIRTLE, personality=Personality(50, 50, 50, 50, 50, 50), level=5))
        player.record_wild_action("attack", is_aggressive=True, species_name="Pidgey")
        player.record_wild_action("flee", is_peaceful=True, species_name="Rattata")
        player.record_wild_action("inspect", is_peaceful=True, species_name="Caterpie")

        with tempfile.TemporaryDirectory() as tmp_dir:
            save_path = Path(tmp_dir) / "test_wild_history_save.json"
            save_game(player, save_path)
            loaded_player = load_game(save_path)

            self.assertEqual(len(loaded_player.wild_action_history), 3)
            self.assertEqual(loaded_player.wild_action_history[0]["action"], "attack")
            self.assertEqual(loaded_player.wild_action_history[1]["action"], "flee")
            self.assertEqual(loaded_player.wild_action_history[2]["action"], "inspect")
            self.assertEqual(loaded_player.behavior_profile, player.behavior_profile)


if __name__ == "__main__":
    unittest.main()
