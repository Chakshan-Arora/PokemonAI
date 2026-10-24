"""
Habitat manager coordinating habitat lookups, deterministic time conversions,
weighted spawn candidate selection, encounter lifecycle integration,
and quest event dispatching.
"""
import random
from typing import Optional, Sequence, Union, Any

from src.models.species import PokemonSpecies
from src.models.pokemon import Pokemon
from src.models.player import Player
from src.models.spawn_area import SpawnArea
from src.models.spawn_manager import SpawnManager
from src.models.encounter_manager import EncounterManager, WildEncounter
from src.models.personality_generator import generate_wild_personality
from src.models.wild_hp import determine_wild_hp
from src.models.world_exploration import WorldRegion
from src.models.world_exploration_manager import WorldExplorationManager
from src.models.quest import QuestEventType
from src.models.quest_manager import QuestManager
from src.models.habitat import (
    TimeOfDay,
    Rarity,
    SpawnCandidate,
    Habitat,
    SpawnSelectionResult,
    HabitatEncounterResult,
    get_time_of_day,
)


class HabitatManager:
    """
    Coordinates data-driven habitat lookups, time-of-day filtering,
    weighted wild Pokemon selection, encounter initiation, and quest dispatch.
    """

    def __init__(
        self,
        habitats: Optional[Sequence[Habitat]] = None,
        exploration_manager: Optional[WorldExplorationManager] = None,
        spawn_manager: Optional[SpawnManager] = None,
        encounter_manager: Optional[EncounterManager] = None,
        quest_manager: Optional[QuestManager] = None,
        rng: Optional[random.Random] = None,
        seed: Optional[int] = None,
    ) -> None:
        """
        Initializes the HabitatManager.

        Args:
            habitats: Sequence of Habitat models (defaults to fresh default catalog instances).
            exploration_manager: Optional WorldExplorationManager for coordinate-based region lookup.
            spawn_manager: Optional SpawnManager for capacity, population, and cooldown tracking.
            encounter_manager: Optional EncounterManager for managing wild combat sessions.
            quest_manager: Optional QuestManager for dispatching encounter quest events.
            rng: Optional injectable random.Random instance for deterministic seeded testing.
            seed: Optional integer seed to initialize an internal random generator.
        """
        if rng is not None:
            self._rng = rng
        elif seed is not None:
            self._rng = random.Random(seed)
        else:
            self._rng = random.Random()

        self._exploration_manager = exploration_manager
        self._spawn_manager = spawn_manager
        self._encounter_manager = encounter_manager if encounter_manager is not None else EncounterManager(spawn_manager=spawn_manager)
        if self._encounter_manager.spawn_manager is None and self._spawn_manager is not None:
            self._encounter_manager.spawn_manager = self._spawn_manager
        self._quest_manager = quest_manager

        # Registered habitats keyed by lowercase habitat_id
        self._habitats: dict[str, Habitat] = {}
        # Mapping from lowercase region_id -> lowercase habitat_id
        self._region_habitat_map: dict[str, str] = {}

        if habitats is not None:
            initial_habitats = habitats
        else:
            from src.data.habitats import create_default_habitats
            initial_habitats = create_default_habitats()
        for h in initial_habitats:
            self.register_habitat(h)

    # --- Properties ---

    @property
    def exploration_manager(self) -> Optional[WorldExplorationManager]:
        """Associated WorldExplorationManager instance."""
        return self._exploration_manager

    @exploration_manager.setter
    def exploration_manager(self, em: Optional[WorldExplorationManager]) -> None:
        self._exploration_manager = em

    @property
    def spawn_manager(self) -> Optional[SpawnManager]:
        """Associated SpawnManager instance."""
        return self._spawn_manager

    @spawn_manager.setter
    def spawn_manager(self, sm: Optional[SpawnManager]) -> None:
        self._spawn_manager = sm
        if self._encounter_manager is not None and self._encounter_manager.spawn_manager is None:
            self._encounter_manager.spawn_manager = sm

    @property
    def encounter_manager(self) -> EncounterManager:
        """Associated EncounterManager instance."""
        return self._encounter_manager

    @encounter_manager.setter
    def encounter_manager(self, em: EncounterManager) -> None:
        if not isinstance(em, EncounterManager):
            raise TypeError(f"Expected EncounterManager instance, got {type(em).__name__}.")
        self._encounter_manager = em

    @property
    def quest_manager(self) -> Optional[QuestManager]:
        """Associated QuestManager instance."""
        return self._quest_manager

    @quest_manager.setter
    def quest_manager(self, qm: Optional[QuestManager]) -> None:
        self._quest_manager = qm

    # --- Habitat Registration & Queries ---

    def register_habitat(self, habitat: Habitat) -> None:
        """
        Registers a Habitat with the manager and binds its associated regions.

        Raises:
            TypeError: If habitat is not a Habitat instance.
            ValueError: If a habitat with the same ID is already registered.
        """
        if not isinstance(habitat, Habitat):
            raise TypeError(f"Expected Habitat instance, got {type(habitat).__name__}.")

        norm_id = habitat.habitat_id.lower()
        if norm_id in self._habitats:
            raise ValueError(f"Habitat with ID '{habitat.habitat_id}' is already registered.")

        self._habitats[norm_id] = habitat
        for rid in habitat.region_ids:
            self._region_habitat_map[rid.lower()] = norm_id

    def get_habitat(self, habitat_id: str) -> Optional[Habitat]:
        """Looks up a registered habitat by its identifier."""
        if not isinstance(habitat_id, str):
            return None
        return self._habitats.get(habitat_id.strip().lower())

    def get_habitat_for_region(self, region_id: str) -> Optional[Habitat]:
        """
        Resolves the Habitat registered for a given world-region ID.
        Returns None if the region is unknown or has no assigned habitat.
        """
        if not isinstance(region_id, str):
            return None
        norm_id = region_id.strip().lower()
        hab_id = self._region_habitat_map.get(norm_id)
        if hab_id is not None:
            return self._habitats.get(hab_id)
        return None

    def get_habitat_at_position(self, position: Sequence[float]) -> Optional[Habitat]:
        """
        Resolves the Habitat containing the given 2D coordinates
        using the configured WorldExplorationManager.
        """
        if self._exploration_manager is None:
            return None
        region = self._exploration_manager.find_region(position)
        if region is None:
            return None
        return self.get_habitat_for_region(region.region_id)

    def list_habitats(self) -> list[Habitat]:
        """Returns all registered habitats."""
        return list(self._habitats.values())

    # --- Time Period Resolution ---

    @staticmethod
    def resolve_time_of_day(time_input: Union[TimeOfDay, int, float, str]) -> TimeOfDay:
        """
        Resolves arbitrary time input into a validated TimeOfDay enum member.

        Supports:
          - TimeOfDay instance (returned as is)
          - Numeric hour in [0.0, 24.0) (mapped via get_time_of_day)
          - String enum name (e.g., 'morning', 'day', 'evening', 'night')
        """
        if isinstance(time_input, TimeOfDay):
            return time_input
        elif isinstance(time_input, (int, float)) and not isinstance(time_input, bool):
            return get_time_of_day(time_input)
        elif isinstance(time_input, str):
            norm = time_input.strip().lower()
            try:
                return TimeOfDay(norm)
            except ValueError:
                raise ValueError(
                    f"Invalid time string '{time_input}'. Expected one of: "
                    f"{[t.value for t in TimeOfDay]}."
                )
        else:
            raise TypeError(f"Invalid time input type: {type(time_input).__name__}.")

    # --- Eligibility Queries ---

    def get_eligible_candidates(
        self,
        region_or_habitat_id: str,
        time_of_day: Union[TimeOfDay, int, float, str],
    ) -> list[SpawnCandidate]:
        """
        Returns all eligible spawn candidates for a region or habitat at the given time.
        """
        time_enum = self.resolve_time_of_day(time_of_day)
        hab = self.get_habitat(region_or_habitat_id) or self.get_habitat_for_region(region_or_habitat_id)
        if hab is None:
            return []
        return hab.get_eligible_candidates(time_enum)

    def get_eligible_species(
        self,
        region_or_habitat_id: str,
        time_of_day: Union[TimeOfDay, int, float, str],
    ) -> list[PokemonSpecies]:
        """
        Returns all unique eligible PokemonSpecies for a region or habitat at the given time.
        """
        time_enum = self.resolve_time_of_day(time_of_day)
        hab = self.get_habitat(region_or_habitat_id) or self.get_habitat_for_region(region_or_habitat_id)
        if hab is None:
            return []
        return hab.get_eligible_species(time_enum)

    # --- Spawn Candidate Selection ---

    def select_spawn(
        self,
        region_id: Optional[str] = None,
        habitat_id: Optional[str] = None,
        position: Optional[Sequence[float]] = None,
        time_of_day: Optional[Union[TimeOfDay, int, float, str]] = None,
        spawn_area: Optional[SpawnArea] = None,
        rng: Optional[random.Random] = None,
    ) -> SpawnSelectionResult:
        """
        Selects a wild Pokemon candidate using data-driven habitat weights and time restrictions.

        Args:
            region_id: Optional world-region ID (e.g. 'starting_meadow').
            habitat_id: Optional direct habitat ID (e.g. 'meadow').
            position: Optional 2D coordinates (x, y) resolved via exploration_manager.
            time_of_day: Explicit TimeOfDay enum or numeric hour in [0.0, 24.0).
            spawn_area: Optional SpawnArea to enforce additional species whitelist restrictions.
            rng: Optional injectable random.Random instance for seeded deterministic results.

        Returns:
            SpawnSelectionResult with selected species, level, and candidate metadata.
        """
        # 1. Resolve Location -> Habitat & Region ID
        resolved_habitat: Optional[Habitat] = None
        resolved_region_id: Optional[str] = None

        if habitat_id is not None:
            resolved_habitat = self.get_habitat(habitat_id)
            if resolved_habitat is None:
                return SpawnSelectionResult(
                    success=False,
                    habitat_id=str(habitat_id),
                    error_type="UNKNOWN_HABITAT",
                    message=f"Habitat '{habitat_id}' not found in registered habitats.",
                )
            resolved_region_id = resolved_habitat.region_ids[0] if resolved_habitat.region_ids else None

        elif region_id is not None:
            resolved_region_id = str(region_id).strip().lower()
            resolved_habitat = self.get_habitat_for_region(resolved_region_id)
            if resolved_habitat is None:
                return SpawnSelectionResult(
                    success=False,
                    region_id=resolved_region_id,
                    error_type="NO_HABITAT",
                    message=f"No habitat registered for world region '{region_id}'.",
                )

        elif position is not None:
            if self._exploration_manager is None:
                return SpawnSelectionResult(
                    success=False,
                    error_type="NO_EXPLORATION_MANAGER",
                    message="Position lookup requires a configured WorldExplorationManager.",
                )
            if not self._exploration_manager.is_position_valid(position):
                return SpawnSelectionResult(
                    success=False,
                    error_type="INVALID_POSITION",
                    message=f"Invalid position coordinates: {position!r}.",
                )
            region = self._exploration_manager.find_region(position)
            if region is None:
                return SpawnSelectionResult(
                    success=False,
                    error_type="OUTSIDE_REGIONS",
                    message=f"Position {position} is outside all registered world regions.",
                )
            resolved_region_id = region.region_id
            resolved_habitat = self.get_habitat_for_region(resolved_region_id)
            if resolved_habitat is None:
                return SpawnSelectionResult(
                    success=False,
                    region_id=resolved_region_id,
                    error_type="NO_HABITAT",
                    message=f"No habitat registered for world region '{region.name}'.",
                )
        else:
            return SpawnSelectionResult(
                success=False,
                error_type="MISSING_LOCATION",
                message="Must provide region_id, habitat_id, or position to select spawn.",
            )

        # 2. Resolve Time Period
        if time_of_day is None:
            return SpawnSelectionResult(
                success=False,
                habitat_id=resolved_habitat.habitat_id,
                region_id=resolved_region_id,
                error_type="MISSING_TIME",
                message="time_of_day is required for spawn selection.",
            )

        try:
            time_enum = self.resolve_time_of_day(time_of_day)
        except (ValueError, TypeError) as err:
            return SpawnSelectionResult(
                success=False,
                habitat_id=resolved_habitat.habitat_id,
                region_id=resolved_region_id,
                error_type="INVALID_TIME",
                message=str(err),
            )

        # 3. Filter Eligible Candidates
        eligible = resolved_habitat.get_eligible_candidates(time_enum)

        # If spawn area provided, apply species whitelist
        if spawn_area is not None:
            if not isinstance(spawn_area, SpawnArea):
                raise TypeError(f"Expected SpawnArea instance, got {type(spawn_area).__name__}.")
            eligible = [c for c in eligible if spawn_area.is_species_allowed(c.species)]

        # 4. Handle Empty Pool
        if not eligible:
            return SpawnSelectionResult(
                success=False,
                habitat_id=resolved_habitat.habitat_id,
                region_id=resolved_region_id,
                time_of_day=time_enum,
                eligible_count=0,
                error_type="NO_ELIGIBLE_SPECIES",
                message=(
                    f"No eligible wild Pokemon found for habitat '{resolved_habitat.name}' "
                    f"during {time_enum.value.upper()}."
                ),
            )

        # 5. Weighted Random Selection
        effective_rng = rng if rng is not None else self._rng
        weights = [c.weight for c in eligible]
        chosen = effective_rng.choices(eligible, weights=weights, k=1)[0]

        # Determine level uniformly within candidate's configured level bounds
        level = effective_rng.randint(chosen.min_level, chosen.max_level)

        return SpawnSelectionResult(
            success=True,
            habitat_id=resolved_habitat.habitat_id,
            region_id=resolved_region_id,
            time_of_day=time_enum,
            candidate=chosen,
            species=chosen.species,
            level=level,
            eligible_count=len(eligible),
            message=(
                f"Selected wild {chosen.species.name} (Lv.{level}) in habitat "
                f"'{resolved_habitat.name}' for period {time_enum.value.upper()}."
            ),
        )

    # --- Wild Encounter Integration ---

    def trigger_encounter(
        self,
        player: Player,
        region_id: Optional[str] = None,
        habitat_id: Optional[str] = None,
        position: Optional[Sequence[float]] = None,
        time_of_day: Optional[Union[TimeOfDay, int, float, str]] = None,
        area_id: Optional[str] = None,
        current_time: Optional[float] = None,
        rng: Optional[random.Random] = None,
        quest_manager: Optional[QuestManager] = None,
        event_id: Optional[str] = None,
    ) -> HabitatEncounterResult:
        """
        Executes the complete habitat encounter pipeline:
          1. Validates player.
          2. Enforces active encounter singleton rule (no double encounters).
          3. Checks spawn capacity and respawn cooldowns if area_id provided.
          4. Selects an eligible candidate using data-driven habitat weights and time period.
          5. Instantiates the wild Pokemon instance with personality and species moves.
          6. Starts the encounter session via EncounterManager.
          7. Dispatches a deduplicated quest encounter event if QuestManager configured.

        Returns:
            HabitatEncounterResult summarizing success, WildEncounter, Pokemon, and emitted events.
        """
        # 1. Validate Player
        if not isinstance(player, Player):
            return HabitatEncounterResult(
                success=False,
                error_type="INVALID_PLAYER",
                message=f"player must be a Player instance, got {type(player).__name__}.",
            )

        # 2. Check Active Encounter Singleton Rule
        if self._encounter_manager.has_active_encounter(player):
            active_enc = self._encounter_manager.get_active_encounter(player)
            enc_id = active_enc.encounter_id if active_enc else "unknown"
            return HabitatEncounterResult(
                success=False,
                player=player,
                error_type="ACTIVE_ENCOUNTER_EXISTS",
                message=f"Player '{player.name}' already has an active encounter ({enc_id}).",
            )

        # 3. Check Spawn Capacity & Cooldown (if area_id is provided)
        target_area: Optional[SpawnArea] = None
        if self._spawn_manager is not None and area_id is not None:
            target_area = self._spawn_manager.get_area(area_id)
            if target_area is None:
                return HabitatEncounterResult(
                    success=False,
                    player=player,
                    error_type="UNKNOWN_SPAWN_AREA",
                    message=f"Spawn area '{area_id}' is not registered in SpawnManager.",
                )
            if not target_area.enabled:
                return HabitatEncounterResult(
                    success=False,
                    player=player,
                    error_type="SPAWN_AREA_DISABLED",
                    message=f"Spawn area '{target_area.name}' is disabled.",
                )
            if current_time is not None and self._spawn_manager.is_area_on_cooldown(area_id, current_time):
                deadline = self._spawn_manager.get_area_cooldown(area_id)
                remaining = (deadline - current_time) if deadline else 0.0
                return HabitatEncounterResult(
                    success=False,
                    player=player,
                    error_type="SPAWN_AREA_ON_COOLDOWN",
                    message=f"Spawn area '{target_area.name}' is on cooldown ({remaining:.1f}s remaining).",
                )
            if not self._spawn_manager.can_spawn(area_id, current_time=current_time):
                return HabitatEncounterResult(
                    success=False,
                    player=player,
                    error_type="SPAWN_CAPACITY_REACHED",
                    message=f"Spawn area '{target_area.name}' has reached max capacity ({target_area.max_active_pokemon}).",
                )

        # 4. Perform Habitat-Aware Selection
        selection_res = self.select_spawn(
            region_id=region_id,
            habitat_id=habitat_id,
            position=position,
            time_of_day=time_of_day,
            spawn_area=target_area,
            rng=rng,
        )

        if not selection_res.success:
            return HabitatEncounterResult(
                success=False,
                player=player,
                selection_result=selection_res,
                error_type=selection_res.error_type,
                message=selection_res.message,
            )

        # 5. Instantiate Wild Pokemon
        effective_rng = rng if rng is not None else self._rng
        wild_personality = generate_wild_personality(rng=effective_rng)
        wild_pokemon = Pokemon(
            species=selection_res.species,
            personality=wild_personality,
            level=selection_res.level,
            attacks=selection_res.species.available_attacks,
        )
        wild_pokemon.current_hp = determine_wild_hp(wild_pokemon.max_hp, rng=effective_rng)

        # 6. Register in Spawn Area population (if managed)
        if self._spawn_manager is not None and area_id is not None:
            self._spawn_manager.add_active_pokemon(
                area_id=area_id,
                pokemon=wild_pokemon,
                position=tuple(position) if position is not None else None,
            )

        # 7. Start Encounter Session via EncounterManager
        wild_encounter = self._encounter_manager.start_encounter(
            player=player,
            pokemon=wild_pokemon,
            area=target_area,
            region_id=selection_res.region_id,
        )

        # 8. Dispatch Deduplicated Quest Event (if QuestManager configured)
        active_qm = quest_manager if quest_manager is not None else self._quest_manager
        event_emitted = False
        emitted_event_id: Optional[str] = None
        if active_qm is not None:
            emitted_event_id = event_id if event_id is not None else (
                f"quest_evt_encounter_{wild_pokemon.unique_id}_{player.unique_id}"
            )
            active_qm.record_encounter(
                player=player,
                species_name=wild_pokemon.species.name,
                habitat_id=selection_res.habitat_id,
                region_id=selection_res.region_id,
                count=1,
                event_id=emitted_event_id,
            )
            event_emitted = True

        return HabitatEncounterResult(
            success=True,
            encounter=wild_encounter,
            selection_result=selection_res,
            pokemon=wild_pokemon,
            player=player,
            event_emitted=event_emitted,
            event_id=emitted_event_id,
            message=(
                f"Wild encounter started with {wild_pokemon.display_name} "
                f"(Lv.{wild_pokemon.level}) in habitat '{selection_res.habitat_id}'!"
            ),
        )

    def resolve_encounter(
        self,
        player: Union[Player, str],
        reason: str = "Resolved",
        despawn: bool = True,
    ) -> Optional[WildEncounter]:
        """
        Resolves the player's active wild encounter, releasing the player slot
        and automatically despawning the wild Pokemon from the associated spawn area.

        Args:
            player: The Player instance or unique player ID string.
            reason: Resolution description (e.g. 'Captured', 'Defeated', 'Fled', 'Cancelled').
            despawn: If True, despawns the Pokemon from its SpawnArea in SpawnManager.

        Returns:
            The resolved WildEncounter instance, or None if no active encounter existed.
        """
        return self._encounter_manager.resolve_active_encounter(
            player=player,
            reason=reason,
            spawn_manager=self._spawn_manager if despawn else None,
        )
