"""
Pokemon behavior controller and state machine.
"""
from typing import Optional
from src.models.pokemon import Pokemon
from src.models.behavior_state import BehaviorState
from src.models.behavior_context import BehaviorContext


class PokemonBehavior:
    """
    State machine controller managing a Pokemon's behavioral intent.
    Evaluates environmental perception against the Pokemon's individual personality traits
    to transition between behavior states.
    """

    def __init__(
        self,
        pokemon: Pokemon,
        initial_state: BehaviorState = BehaviorState.IDLE,
    ) -> None:
        if not isinstance(pokemon, Pokemon):
            raise TypeError(f"Expected Pokemon instance, got {type(pokemon).__name__}.")
        if not isinstance(initial_state, BehaviorState):
            raise TypeError(f"Expected BehaviorState instance, got {type(initial_state).__name__}.")

        self._pokemon: Pokemon = pokemon
        self._state: BehaviorState = initial_state
        self._previous_state: Optional[BehaviorState] = None

    # --- Properties ---

    @property
    def pokemon(self) -> Pokemon:
        """Reference to the underlying Pokemon."""
        return self._pokemon

    @property
    def state(self) -> BehaviorState:
        """Current behavior state."""
        return self._state

    @property
    def previous_state(self) -> Optional[BehaviorState]:
        """Behavior state prior to the most recent update."""
        return self._previous_state

    # --- State Management ---

    def get_state(self) -> BehaviorState:
        """Returns the current behavior state."""
        return self._state

    def update(self, context: BehaviorContext) -> BehaviorState:
        """
        Evaluates the current environment context and updates the behavior state.
        Returns the newly evaluated state.
        """
        if not isinstance(context, BehaviorContext):
            raise TypeError(f"Expected BehaviorContext instance, got {type(context).__name__}.")

        next_state = self.decide_next_state(context)
        self._previous_state = self._state
        self._state = next_state
        return self._state

    def decide_next_state(self, context: BehaviorContext) -> BehaviorState:
        """
        Deterministic decision engine that determines the next behavior state
        based on personality traits and the perceived environment.
        """
        p = self._pokemon.personality

        has_threat = context.threat_level > 0
        player_present = context.player_visible or context.player_nearby
        is_close_to_player = context.distance_to_player <= 5.0 or context.player_nearby

        # Case 1: Player or threat is perceived
        if player_present or has_threat:
            # Confidence acts as a shield against fear: high confidence suppresses fear
            effective_fear = p.fear - (p.confidence * 0.5)

            # High fear with low confidence triggers defensive fleeing or hiding
            if (p.fear >= 60 and p.confidence < 60) or (has_threat and effective_fear > 30 and p.fear > p.aggression):
                # Close proximity or critical threat forces immediate panic flee
                if is_close_to_player or context.threat_level >= 70:
                    return BehaviorState.FLEE
                # Otherwise, attempt to seek cover and break line of sight: HIDE
                return BehaviorState.HIDE

            # Aggression triggers confrontation with the player
            if p.aggression >= 60:
                # High aggression + close distance -> direct ATTACK
                if p.aggression >= 75 and is_close_to_player:
                    return BehaviorState.ATTACK
                # Otherwise, close in on the player: APPROACH
                return BehaviorState.APPROACH

            # High curiosity prompts investigation or approach
            if p.curiosity >= 60:
                if is_close_to_player:
                    return BehaviorState.APPROACH
                return BehaviorState.INVESTIGATE

            # Moderate aggression approaches cautious engagement
            if p.aggression >= 40:
                return BehaviorState.APPROACH

            # High sociability prompts approaching non-threatening player
            if p.sociability >= 60 and p.fear < 40:
                return BehaviorState.APPROACH

            # Confident or moderately curious Pokemon investigates
            if p.confidence >= 50 or p.curiosity >= 40:
                return BehaviorState.INVESTIGATE

            # Default defensive idle
            return BehaviorState.IDLE

        # Case 2: Interesting object detected in environment
        if context.interesting_object_detected:
            if p.curiosity >= 40:
                return BehaviorState.INVESTIGATE

        # Case 3: Other Pokemon nearby (sociability factor)
        if context.nearby_pokemon_count > 0:
            if p.sociability >= 60:
                return BehaviorState.APPROACH
            if p.sociability >= 40:
                return BehaviorState.WANDER

        # Case 4: Peaceful environment (no player, no threat)
        # Highly curious Pokemon wander; otherwise stay idle
        if p.curiosity >= 50:
            return BehaviorState.WANDER
        return BehaviorState.IDLE

    def __repr__(self) -> str:
        return f"PokemonBehavior(pokemon='{self._pokemon.display_name}', state={self._state.value})"
