"""
Capture manager for wild Pokemon.
Handles capture probability calculation, encounter validation,
deterministic random checks, and player collection integration.
"""
import random
from dataclasses import dataclass
from typing import Optional, Union
from src.models.pokemon import Pokemon
from src.models.player import Player
from src.models.encounter_manager import WildEncounter, EncounterResult
from src.models.spawn_manager import SpawnManager
from src.models.quest import QuestEventType
from src.models.quest_manager import QuestManager

# Probability formula constants
MIN_CAPTURE_PROBABILITY: float = 0.05
MAX_CAPTURE_PROBABILITY: float = 0.90
BASE_CAPTURE_CHANCE: float = 0.20
HP_FACTOR_MULTIPLIER: float = 0.65
LEVEL_PENALTY_MULTIPLIER: float = 0.002


def calculate_capture_probability(
    pokemon: Pokemon,
    min_prob: float = MIN_CAPTURE_PROBABILITY,
    max_prob: float = MAX_CAPTURE_PROBABILITY,
) -> float:
    """
    Calculates the capture chance for a wild Pokemon based on remaining HP and level.

    Formula:
      hp_factor     = 1.0 - (current_hp / max_hp)
      level_penalty = level * 0.002
      raw_chance    = 0.65 * hp_factor + 0.20 - level_penalty
      clamped       = clamp(raw_chance, min_prob, max_prob)

    Args:
        pokemon: The Pokemon being targeted.
        min_prob: Minimum allowed probability (default 0.05).
        max_prob: Maximum allowed probability (default 0.90).

    Returns:
        A float probability clamped to [min_prob, max_prob].
    """
    if not isinstance(pokemon, Pokemon):
        raise TypeError(f"pokemon must be a Pokemon instance, got {type(pokemon).__name__}.")

    hp_ratio = max(0.0, min(1.0, float(pokemon.current_hp) / float(pokemon.max_hp)))
    hp_factor = 1.0 - hp_ratio
    level_penalty = float(pokemon.level) * LEVEL_PENALTY_MULTIPLIER

    raw_chance = (HP_FACTOR_MULTIPLIER * hp_factor) + BASE_CAPTURE_CHANCE - level_penalty
    return max(min_prob, min(max_prob, raw_chance))


@dataclass(frozen=True)
class CaptureResult:
    """
    Structured outcome of a Pokemon capture attempt.
    """
    accepted: bool
    success: bool
    pokemon: Optional[Pokemon]
    player: Optional[Player]
    capture_probability: float
    message: str
    added_to_collection: bool
    roll: Optional[float] = None
    added_to_team: bool = False


class CaptureManager:
    """
    Coordinates wild Pokemon capture attempts.
    Validates eligibility, calculates capture probabilities, rolls deterministic RNG checks,
    and updates player collection and encounter lifecycles.
    """

    def __init__(
        self,
        rng: Optional[random.Random] = None,
        seed: Optional[int] = None,
        min_probability: float = MIN_CAPTURE_PROBABILITY,
        max_probability: float = MAX_CAPTURE_PROBABILITY,
        quest_manager: Optional[QuestManager] = None,
    ) -> None:
        if rng is not None:
            self._rng = rng
        elif seed is not None:
            self._rng = random.Random(seed)
        else:
            self._rng = random.Random()

        self._min_probability = min_probability
        self._max_probability = max_probability
        self._quest_manager: Optional[QuestManager] = quest_manager

    @property
    def min_probability(self) -> float:
        """Configured minimum capture probability floor."""
        return self._min_probability

    @property
    def max_probability(self) -> float:
        """Configured maximum capture probability ceiling."""
        return self._max_probability

    @property
    def quest_manager(self) -> Optional[QuestManager]:
        """Associated QuestManager instance for dispatching capture events."""
        return self._quest_manager

    @quest_manager.setter
    def quest_manager(self, qm: Optional[QuestManager]) -> None:
        self._quest_manager = qm

    def calculate_chance(self, pokemon: Pokemon) -> float:
        """Calculates capture chance using this manager's probability bounds."""
        return calculate_capture_probability(
            pokemon,
            min_prob=self._min_probability,
            max_prob=self._max_probability,
        )

    def attempt_capture(
        self,
        player: Player,
        wild_pokemon: Pokemon,
        encounter: Optional[Union[WildEncounter, EncounterResult]] = None,
        spawn_manager: Optional[SpawnManager] = None,
        area_id: Optional[str] = None,
        rng: Optional[random.Random] = None,
        quest_manager: Optional[QuestManager] = None,
    ) -> CaptureResult:
        """
        Executes a capture attempt on a wild Pokemon.

        Eligibility Rules:
          - player must be a valid Player instance.
          - wild_pokemon must be a valid Pokemon instance.
          - wild_pokemon must not be fainted (HP > 0).
          - wild_pokemon must not already be in player's collection.
          - If encounter is provided, it must be valid and active.
          - If spawn_manager and area_id are provided, wild_pokemon must be active in that area.

        Outcomes:
          - If rejected: accepted=False, success=False, added_to_collection=False.
          - If roll fails: accepted=True, success=False, added_to_collection=False.
          - If roll succeeds: accepted=True, success=True, added_to_collection=True,
            the existing Pokemon instance is added to player's collection, encounter is resolved,
            and (if applicable) wild_pokemon is despawned from the spawn area.
        """
        # 1. Validate Player
        if not isinstance(player, Player):
            return CaptureResult(
                accepted=False,
                success=False,
                pokemon=wild_pokemon if isinstance(wild_pokemon, Pokemon) else None,
                player=None,
                capture_probability=0.0,
                message=f"Invalid player: expected Player instance, got {type(player).__name__}.",
                added_to_collection=False,
            )

        # 2. Validate Target Pokemon
        if not isinstance(wild_pokemon, Pokemon):
            return CaptureResult(
                accepted=False,
                success=False,
                pokemon=None,
                player=player,
                capture_probability=0.0,
                message=f"Invalid target: expected Pokemon instance, got {type(wild_pokemon).__name__}.",
                added_to_collection=False,
            )

        # 3. Check if target is already owned
        if player.is_pokemon_owned(wild_pokemon):
            return CaptureResult(
                accepted=False,
                success=False,
                pokemon=wild_pokemon,
                player=player,
                capture_probability=0.0,
                message=f"Pokemon '{wild_pokemon.display_name}' (ID: {wild_pokemon.unique_id}) is already in player's collection.",
                added_to_collection=False,
            )

        # 4. Check if target is fainted
        if wild_pokemon.is_fainted or wild_pokemon.current_hp <= 0:
            return CaptureResult(
                accepted=False,
                success=False,
                pokemon=wild_pokemon,
                player=player,
                capture_probability=0.0,
                message=f"Cannot capture fainted Pokemon '{wild_pokemon.display_name}'.",
                added_to_collection=False,
            )

        # 5. Validate Encounter Session / Result
        if encounter is not None:
            if isinstance(encounter, WildEncounter):
                if encounter.pokemon is not wild_pokemon:
                    return CaptureResult(
                        accepted=False,
                        success=False,
                        pokemon=wild_pokemon,
                        player=player,
                        capture_probability=0.0,
                        message="Target Pokemon does not match the encounter session Pokemon.",
                        added_to_collection=False,
                    )
                if encounter.player is not player:
                    return CaptureResult(
                        accepted=False,
                        success=False,
                        pokemon=wild_pokemon,
                        player=player,
                        capture_probability=0.0,
                        message="Player does not match the encounter session player.",
                        added_to_collection=False,
                    )
                if encounter.is_resolved or not encounter.is_active:
                    return CaptureResult(
                        accepted=False,
                        success=False,
                        pokemon=wild_pokemon,
                        player=player,
                        capture_probability=0.0,
                        message=f"Encounter is no longer active (already resolved: '{encounter.resolution_reason}').",
                        added_to_collection=False,
                    )
            elif isinstance(encounter, EncounterResult):
                if not encounter.can_encounter:
                    return CaptureResult(
                        accepted=False,
                        success=False,
                        pokemon=wild_pokemon,
                        player=player,
                        capture_probability=0.0,
                        message=f"Invalid encounter check: {encounter.reason}",
                        added_to_collection=False,
                    )
                if encounter.pokemon is not None and encounter.pokemon is not wild_pokemon:
                    return CaptureResult(
                        accepted=False,
                        success=False,
                        pokemon=wild_pokemon,
                        player=player,
                        capture_probability=0.0,
                        message="Target Pokemon does not match the encounter result Pokemon.",
                        added_to_collection=False,
                    )
            else:
                return CaptureResult(
                    accepted=False,
                    success=False,
                    pokemon=wild_pokemon,
                    player=player,
                    capture_probability=0.0,
                    message=f"Invalid encounter object: expected WildEncounter or EncounterResult, got {type(encounter).__name__}.",
                    added_to_collection=False,
                )

        # 6. Validate Spawn Manager & Area
        if spawn_manager is not None and area_id is not None:
            if not isinstance(spawn_manager, SpawnManager):
                return CaptureResult(
                    accepted=False,
                    success=False,
                    pokemon=wild_pokemon,
                    player=player,
                    capture_probability=0.0,
                    message=f"Invalid spawn_manager: expected SpawnManager, got {type(spawn_manager).__name__}.",
                    added_to_collection=False,
                )
            if not spawn_manager.is_pokemon_active(area_id, wild_pokemon):
                return CaptureResult(
                    accepted=False,
                    success=False,
                    pokemon=wild_pokemon,
                    player=player,
                    capture_probability=0.0,
                    message=f"Pokemon '{wild_pokemon.display_name}' is not active in spawn area '{area_id}'.",
                    added_to_collection=False,
                )

        # 7. Calculate probability and roll
        prob = self.calculate_chance(wild_pokemon)
        effective_rng = rng if rng is not None else self._rng
        roll = effective_rng.random()
        success = roll <= prob

        # 8. Handle Success
        if success:
            # Add existing Pokemon instance to player's collection if not already owned
            if not player.is_pokemon_owned(wild_pokemon):
                player.add_pokemon(wild_pokemon)

            # Auto-assign to active team if open slot is available
            added_to_team = False
            if len(player.team) < player.max_team_size and not player.is_on_team(wild_pokemon):
                player.add_to_team(wild_pokemon)
                added_to_team = True
                if player.active_pokemon is None and not wild_pokemon.is_fainted:
                    player.set_active_pokemon(wild_pokemon)

            # Resolve encounter session if present
            if isinstance(encounter, WildEncounter) and encounter.is_active:
                encounter.resolve(reason="Captured")

            # Despawn from wild spawn manager if provided
            effective_area_id = area_id
            if effective_area_id is None and isinstance(encounter, WildEncounter) and encounter.area is not None:
                effective_area_id = encounter.area.area_id

            if spawn_manager is not None and effective_area_id is not None:
                spawn_manager.despawn_pokemon(effective_area_id, wild_pokemon)

            if added_to_team:
                msg = f"Gotcha! {wild_pokemon.display_name} was caught and joined your team!"
            else:
                msg = f"Gotcha! {wild_pokemon.display_name} was caught and sent to your PC!"

            # Dispatch quest events if quest_manager is configured
            active_qm = quest_manager if quest_manager is not None else self._quest_manager
            if active_qm is not None:
                enc_id = encounter.encounter_id if isinstance(encounter, WildEncounter) else "direct"
                cap_evt_id = f"quest_evt_capture_{enc_id}_{wild_pokemon.unique_id}"
                col_evt_id = f"quest_evt_collect_{enc_id}_{wild_pokemon.unique_id}_{len(player.collection)}"

                # Resolve region from encounter or spawn area
                reg_id: Optional[str] = None
                if isinstance(encounter, WildEncounter):
                    reg_id = encounter.region_id
                elif isinstance(encounter, EncounterResult):
                    reg_id = encounter.region_id or (getattr(encounter.area, "region_id", None) if encounter.area else None)
                elif effective_area_id is not None and spawn_manager is not None:
                    sp_area = spawn_manager.get_area(effective_area_id)
                    if sp_area is not None:
                        reg_id = getattr(sp_area, "region_id", None)

                payload_cap: dict[str, Any] = {
                    "species_name": wild_pokemon.species.name,
                    "level": wild_pokemon.level,
                    "count": 1,
                }
                if reg_id:
                    payload_cap["region_id"] = reg_id

                payload_col: dict[str, Any] = {
                    "species_name": wild_pokemon.species.name,
                    "count": len(player.collection),
                }
                if reg_id:
                    payload_col["region_id"] = reg_id

                active_qm.record_event(
                    player=player,
                    event_type=QuestEventType.POKEMON_CAPTURED,
                    payload=payload_cap,
                    event_id=cap_evt_id,
                )
                active_qm.record_event(
                    player=player,
                    event_type=QuestEventType.POKEMON_COLLECTED,
                    payload=payload_col,
                    event_id=col_evt_id,
                )

            return CaptureResult(
                accepted=True,
                success=True,
                pokemon=wild_pokemon,
                player=player,
                capture_probability=prob,
                message=msg,
                added_to_collection=True,
                roll=roll,
                added_to_team=added_to_team,
            )

        # 9. Handle Failure
        return CaptureResult(
            accepted=True,
            success=False,
            pokemon=wild_pokemon,
            player=player,
            capture_probability=prob,
            message=f"Oh no! The wild {wild_pokemon.display_name} broke free!",
            added_to_collection=False,
            roll=roll,
        )
