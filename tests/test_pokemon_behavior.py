"""
Unit tests for the Pokemon behavior state machine and context evaluation.

Tests verify:
1. Pokemon starts in a valid initial state.
2. Calm Pokemon can wander/idle when nothing is detected.
3. Curious Pokemon investigates a nearby player/object.
4. Aggressive Pokemon approaches a nearby player.
5. Highly aggressive Pokemon can attack when the player is sufficiently close.
6. Fearful Pokemon flees/hides from a nearby threat.
7. High confidence reduces fleeing behavior.
8. Different personalities can produce different states from the same context.
9. State transitions work correctly.
10. Context with no threat can cause a Pokemon to return to IDLE/WANDER.
11. Existing Pokemon behavior data is not modified unexpectedly.
12. Existing Pokemon foundation tests still pass.
"""
import unittest

from src.models.personality import Personality
from src.models.pokemon import Pokemon
from src.models.behavior_state import BehaviorState
from src.models.behavior_context import BehaviorContext
from src.models.pokemon_behavior import PokemonBehavior
from src.data.species import PIKACHU, CHARMANDER, SQUIRTLE


class TestPokemonBehavior(unittest.TestCase):
    """Test suite for PokemonBehavior state machine and personality-driven decisions."""

    def setUp(self) -> None:
        """Create sample personality profiles and Pokemon instances for behavior tests."""
        # 1. Calm / Neutral
        self.calm_personality = Personality(
            aggression=20,
            curiosity=30,
            fear=20,
            sociability=40,
            loyalty=50,
            confidence=50,
        )
        self.calm_pokemon = Pokemon(species=PIKACHU, personality=self.calm_personality)

        # 2. Curious
        self.curious_personality = Personality(
            aggression=20,
            curiosity=85,
            fear=15,
            sociability=70,
            loyalty=60,
            confidence=60,
        )
        self.curious_pokemon = Pokemon(species=SQUIRTLE, personality=self.curious_personality)

        # 3. Aggressive
        self.aggressive_personality = Personality(
            aggression=80,
            curiosity=30,
            fear=10,
            sociability=20,
            loyalty=40,
            confidence=70,
        )
        self.aggressive_pokemon = Pokemon(species=CHARMANDER, personality=self.aggressive_personality)

        # 4. Fearful (low confidence)
        self.fearful_personality = Personality(
            aggression=10,
            curiosity=20,
            fear=85,
            sociability=15,
            loyalty=30,
            confidence=20,
        )
        self.fearful_pokemon = Pokemon(species=PIKACHU, personality=self.fearful_personality)

        # 5. Fearful with high confidence
        self.confident_fearful_personality = Personality(
            aggression=30,
            curiosity=50,
            fear=65,
            sociability=40,
            loyalty=50,
            confidence=85,
        )
        self.confident_pokemon = Pokemon(species=PIKACHU, personality=self.confident_fearful_personality)

    # 1. Pokemon starts in a valid initial state.
    def test_01_initial_state_is_valid(self) -> None:
        behavior = PokemonBehavior(self.calm_pokemon)
        self.assertEqual(behavior.get_state(), BehaviorState.IDLE)
        self.assertEqual(behavior.state, BehaviorState.IDLE)
        self.assertIs(behavior.pokemon, self.calm_pokemon)

        # Custom initial state
        custom_behavior = PokemonBehavior(self.calm_pokemon, initial_state=BehaviorState.WANDER)
        self.assertEqual(custom_behavior.get_state(), BehaviorState.WANDER)

    # 2. Calm Pokemon can wander/idle when nothing is detected.
    def test_02_calm_pokemon_wanders_or_idles_when_nothing_detected(self) -> None:
        behavior_idle = PokemonBehavior(self.calm_pokemon)
        peaceful_context = BehaviorContext()  # No player, no threat, peaceful

        new_state = behavior_idle.update(peaceful_context)
        self.assertIn(new_state, [BehaviorState.IDLE, BehaviorState.WANDER])
        self.assertEqual(new_state, BehaviorState.IDLE)

        # A curious Pokemon in peaceful surroundings wanders
        behavior_curious = PokemonBehavior(self.curious_pokemon)
        curious_peaceful_state = behavior_curious.update(peaceful_context)
        self.assertEqual(curious_peaceful_state, BehaviorState.WANDER)

    # 3. Curious Pokemon investigates a nearby player/object.
    def test_03_curious_pokemon_investigates_nearby_player_or_object(self) -> None:
        behavior = PokemonBehavior(self.curious_pokemon)

        # Player visible at a distance
        player_context = BehaviorContext(player_visible=True, distance_to_player=15.0)
        state_player = behavior.update(player_context)
        self.assertEqual(state_player, BehaviorState.INVESTIGATE)

        # Or interesting object detected in peaceful area
        object_context = BehaviorContext(interesting_object_detected=True)
        state_object = behavior.update(object_context)
        self.assertEqual(state_object, BehaviorState.INVESTIGATE)

    # 4. Aggressive Pokemon approaches a nearby player.
    def test_04_aggressive_pokemon_approaches_nearby_player(self) -> None:
        behavior = PokemonBehavior(self.aggressive_pokemon)
        context = BehaviorContext(player_visible=True, distance_to_player=12.0)

        state = behavior.update(context)
        self.assertEqual(state, BehaviorState.APPROACH)

    # 5. Highly aggressive Pokemon can attack when the player is sufficiently close.
    def test_05_highly_aggressive_pokemon_attacks_when_close(self) -> None:
        behavior = PokemonBehavior(self.aggressive_pokemon)
        close_context = BehaviorContext(
            player_visible=True,
            player_nearby=True,
            distance_to_player=3.0,
        )

        state = behavior.update(close_context)
        self.assertEqual(state, BehaviorState.ATTACK)

    # 6. Fearful Pokemon flees/hides from a nearby threat.
    def test_06_fearful_pokemon_flees_or_hides_from_threat(self) -> None:
        behavior = PokemonBehavior(self.fearful_pokemon)

        # Distant threat -> HIDE
        distant_threat_context = BehaviorContext(
            player_visible=True,
            threat_level=40.0,
            distance_to_player=15.0,
        )
        state_hide = behavior.update(distant_threat_context)
        self.assertEqual(state_hide, BehaviorState.HIDE)

        # Close threat / player nearby -> FLEE
        close_threat_context = BehaviorContext(
            player_visible=True,
            player_nearby=True,
            threat_level=70.0,
            distance_to_player=4.0,
        )
        state_flee = behavior.update(close_threat_context)
        self.assertEqual(state_flee, BehaviorState.FLEE)

    # 7. High confidence reduces fleeing behavior.
    def test_07_high_confidence_reduces_fleeing_behavior(self) -> None:
        # Both have fear >= 65, but self.confident_pokemon has confidence 85, while self.fearful_pokemon has 20
        threat_context = BehaviorContext(
            player_visible=True,
            threat_level=40.0,
            distance_to_player=15.0,
        )

        fearful_behavior = PokemonBehavior(self.fearful_pokemon)
        fearful_state = fearful_behavior.update(threat_context)
        self.assertEqual(fearful_state, BehaviorState.HIDE)

        confident_behavior = PokemonBehavior(self.confident_pokemon)
        confident_state = confident_behavior.update(threat_context)
        # Confident Pokemon stands ground or investigates instead of hiding/fleeing
        self.assertNotIn(confident_state, [BehaviorState.FLEE, BehaviorState.HIDE])
        self.assertEqual(confident_state, BehaviorState.INVESTIGATE)

    # 8. Different personalities can produce different states from the same context.
    def test_08_different_personalities_produce_different_states_same_context(self) -> None:
        shared_context = BehaviorContext(
            player_visible=True,
            player_nearby=True,
            distance_to_player=4.0,
        )

        behavior_aggro = PokemonBehavior(self.aggressive_pokemon)
        behavior_fear = PokemonBehavior(self.fearful_pokemon)
        behavior_curious = PokemonBehavior(self.curious_pokemon)

        state_aggro = behavior_aggro.update(shared_context)
        state_fear = behavior_fear.update(shared_context)
        state_curious = behavior_curious.update(shared_context)

        self.assertEqual(state_aggro, BehaviorState.ATTACK)
        self.assertEqual(state_fear, BehaviorState.FLEE)
        self.assertEqual(state_curious, BehaviorState.APPROACH)

        # Confirm they produced distinct states
        self.assertNotEqual(state_aggro, state_fear)
        self.assertNotEqual(state_aggro, state_curious)
        self.assertNotEqual(state_fear, state_curious)

    # 9. State transitions work correctly.
    def test_09_state_transitions_work_correctly(self) -> None:
        behavior = PokemonBehavior(self.aggressive_pokemon)
        self.assertEqual(behavior.get_state(), BehaviorState.IDLE)

        # Player appears far away: IDLE -> APPROACH
        context_far = BehaviorContext(player_visible=True, distance_to_player=12.0)
        behavior.update(context_far)
        self.assertEqual(behavior.get_state(), BehaviorState.APPROACH)
        self.assertEqual(behavior.previous_state, BehaviorState.IDLE)

        # Player gets close: APPROACH -> ATTACK
        context_close = BehaviorContext(player_visible=True, player_nearby=True, distance_to_player=3.0)
        behavior.update(context_close)
        self.assertEqual(behavior.get_state(), BehaviorState.ATTACK)
        self.assertEqual(behavior.previous_state, BehaviorState.APPROACH)

    # 10. Context with no threat can cause a Pokemon to return to IDLE/WANDER.
    def test_10_context_with_no_threat_returns_to_idle_or_wander(self) -> None:
        behavior = PokemonBehavior(self.fearful_pokemon)

        # Threat puts it into FLEE
        threat_context = BehaviorContext(player_visible=True, player_nearby=True, distance_to_player=3.0)
        behavior.update(threat_context)
        self.assertEqual(behavior.get_state(), BehaviorState.FLEE)

        # Threat gone: returns to calm
        peaceful_context = BehaviorContext()
        behavior.update(peaceful_context)
        self.assertIn(behavior.get_state(), [BehaviorState.IDLE, BehaviorState.WANDER])

    # 11. Existing Pokemon behavior data is not modified unexpectedly.
    def test_11_pokemon_underlying_data_is_not_modified(self) -> None:
        initial_hp = self.aggressive_pokemon.current_hp
        initial_level = self.aggressive_pokemon.level
        initial_bond = self.aggressive_pokemon.bond
        initial_personality = self.aggressive_pokemon.personality

        behavior = PokemonBehavior(self.aggressive_pokemon)
        behavior.update(BehaviorContext(player_visible=True, distance_to_player=3.0))

        self.assertEqual(self.aggressive_pokemon.current_hp, initial_hp)
        self.assertEqual(self.aggressive_pokemon.level, initial_level)
        self.assertEqual(self.aggressive_pokemon.bond, initial_bond)
        self.assertEqual(self.aggressive_pokemon.personality, initial_personality)

    # Context validation tests
    def test_context_validation(self) -> None:
        with self.assertRaises(ValueError):
            BehaviorContext(distance_to_player=-5.0)

        with self.assertRaises(ValueError):
            BehaviorContext(threat_level=-1.0)


if __name__ == "__main__":
    unittest.main()
