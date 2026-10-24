from __future__ import annotations
"""
Spawn manager coordinating wild Pokemon spawns, active populations, and despawns across areas.
"""
import random
from typing import Optional, Sequence, Union, TYPE_CHECKING
from src.models.pokemon import Pokemon
from src.models.spawn_area import SpawnArea
from src.models.personality_generator import generate_wild_personality
from src.models.wild_hp import determine_wild_hp

if TYPE_CHECKING:
    from src.data.spawn_config import SpeciesSpawnConfig


class SpawnManager:
    """
    Manages wild Pokemon spawning and tracking across registered spawn areas.
    Maintains population limits, applies species weightings, and enforces area rules.
    """

    def __init__(
        self,
        spawn_configs: Optional[Sequence[SpeciesSpawnConfig]] = None,
        rng: Optional[random.Random] = None,
        seed: Optional[int] = None,
    ) -> None:
        if spawn_configs is not None:
            self._spawn_configs: list[SpeciesSpawnConfig] = list(spawn_configs)
        else:
            from src.data.spawn_config import DEFAULT_SPAWN_CONFIGS
            self._spawn_configs = list(DEFAULT_SPAWN_CONFIGS)

        if rng is not None:
            self._rng = rng
        elif seed is not None:
            self._rng = random.Random(seed)
        else:
            self._rng = random.Random()

        # Registered spawn areas keyed by area_id
        self._areas: dict[str, SpawnArea] = {}

        # Active wild Pokemon per area: area_id -> list[Pokemon]
        self._active_pokemon: dict[str, list[Pokemon]] = {}

        # Optional world position tracking: pokemon_id -> tuple[float, ...]
        self._pokemon_positions: dict[str, tuple[float, ...]] = {}

        # Optional deterministic respawn cooldown tracking: area_id -> cooldown_deadline_float
        self._area_cooldowns: dict[str, float] = {}

    # --- Area Registration ---

    def register_area(self, area: SpawnArea) -> None:
        """Registers a SpawnArea with the manager."""
        if not isinstance(area, SpawnArea):
            raise TypeError(f"Expected SpawnArea instance, got {type(area).__name__}.")

        self._areas[area.area_id] = area
        if area.area_id not in self._active_pokemon:
            self._active_pokemon[area.area_id] = []

    def get_area(self, area_id: str) -> Optional[SpawnArea]:
        """Retrieves a registered SpawnArea by its ID."""
        return self._areas.get(area_id)

    def get_all_areas(self) -> list[SpawnArea]:
        """Returns a list of all registered SpawnAreas."""
        return list(self._areas.values())

    # --- Population Queries ---

    def get_active_pokemon(self, area_id: str) -> list[Pokemon]:
        """Returns a copy of the list of active wild Pokemon in an area."""
        if area_id not in self._areas:
            raise KeyError(f"Spawn area '{area_id}' is not registered.")
        return list(self._active_pokemon.get(area_id, []))

    def get_active_count(self, area_id: str) -> int:
        """Returns the number of active wild Pokemon in an area."""
        if area_id not in self._areas:
            raise KeyError(f"Spawn area '{area_id}' is not registered.")
        return len(self._active_pokemon.get(area_id, []))

    def add_active_pokemon(
        self,
        area_id: str,
        pokemon: Pokemon,
        position: Optional[tuple[float, ...]] = None,
    ) -> bool:
        """
        Registers an externally created Pokemon into the area's active population.
        Returns True if added, False if the Pokemon is already active in that area.

        Raises:
            TypeError: If pokemon is not a Pokemon instance.
            KeyError: If area_id is not registered in SpawnManager.
        """
        if not isinstance(pokemon, Pokemon):
            raise TypeError(f"Expected Pokemon instance, got {type(pokemon).__name__}.")
        if area_id not in self._areas:
            raise KeyError(f"Spawn area '{area_id}' is not registered.")
        if self.is_pokemon_active(area_id, pokemon):
            return False

        self._active_pokemon[area_id].append(pokemon)
        if position is not None:
            self.set_pokemon_position(pokemon, position)
        return True

    def can_spawn(self, area_id: str, current_time: Optional[float] = None) -> bool:
        """
        Checks whether an area can currently spawn more wild Pokemon.
        Requires the area to be registered, enabled, below max capacity,
        and not in an active respawn cooldown (if current_time is provided).
        """
        area = self.get_area(area_id)
        if area is None or not area.enabled:
            return False

        if current_time is not None and self.is_area_on_cooldown(area_id, current_time):
            return False

        current_count = self.get_active_count(area_id)
        return current_count < area.max_active_pokemon

    # --- Cooldown Operations ---

    def set_area_cooldown(self, area_id: str, cooldown_duration: float, current_time: float) -> None:
        """
        Sets a deterministic respawn cooldown deadline on a spawn area.
        The area will be unable to spawn until current_time >= deadline.
        """
        if area_id not in self._areas:
            raise KeyError(f"Spawn area '{area_id}' is not registered.")
        if cooldown_duration < 0:
            raise ValueError(f"cooldown_duration cannot be negative, got {cooldown_duration}.")
        self._area_cooldowns[area_id] = float(current_time) + float(cooldown_duration)

    def get_area_cooldown(self, area_id: str) -> Optional[float]:
        """Returns the deadline timestamp until which the area is on cooldown, or None."""
        return self._area_cooldowns.get(area_id)

    def is_area_on_cooldown(self, area_id: str, current_time: float) -> bool:
        """Checks if a spawn area is currently on respawn cooldown."""
        deadline = self._area_cooldowns.get(area_id)
        if deadline is None:
            return False
        return float(current_time) < deadline

    def clear_area_cooldown(self, area_id: str) -> None:
        """Clears any active respawn cooldown for the area."""
        self._area_cooldowns.pop(area_id, None)

    def is_pokemon_active(self, area_id: str, pokemon: Union[Pokemon, str]) -> bool:
        """Checks if a specific Pokemon is active in the given area."""
        if area_id not in self._areas:
            return False
        p_id = pokemon.unique_id if isinstance(pokemon, Pokemon) else str(pokemon)
        return any(p.unique_id == p_id for p in self._active_pokemon.get(area_id, []))

    # --- Position Tracking ---

    def set_pokemon_position(self, pokemon: Union[Pokemon, str], position: tuple[float, ...]) -> None:
        """Records a world position for a wild Pokemon."""
        p_id = pokemon.unique_id if isinstance(pokemon, Pokemon) else str(pokemon)
        self._pokemon_positions[p_id] = tuple(float(x) for x in position)

    def get_pokemon_position(self, pokemon: Union[Pokemon, str]) -> Optional[tuple[float, ...]]:
        """Retrieves the recorded world position for a wild Pokemon."""
        p_id = pokemon.unique_id if isinstance(pokemon, Pokemon) else str(pokemon)
        return self._pokemon_positions.get(p_id)

    # --- Spawning Operations ---

    def get_eligible_configs(self, area_id: str) -> list[SpeciesSpawnConfig]:
        """Returns all spawn configs valid for the specified area."""
        area = self.get_area(area_id)
        if area is None:
            return []

        eligible = []
        for cfg in self._spawn_configs:
            if area_id in cfg.allowed_area_ids and area.is_species_allowed(cfg.species):
                eligible.append(cfg)
        return eligible

    def attempt_spawn(
        self,
        area_id: str,
        ignore_probability: bool = False,
        position: Optional[tuple[float, ...]] = None,
        current_time: Optional[float] = None,
    ) -> Optional[Pokemon]:
        """
        Attempts to spawn a single wild Pokemon in an area.
        Respects area capacity, enablement, cooldown, probability, and species weights.
        Returns the spawned Pokemon instance if successful, or None.
        """
        area = self.get_area(area_id)
        if area is None:
            raise KeyError(f"Spawn area '{area_id}' is not registered.")

        if not self.can_spawn(area_id, current_time=current_time):
            return None

        # Check probability roll unless explicitly bypassed
        if not ignore_probability:
            roll = self._rng.random()
            if roll > area.base_spawn_probability:
                return None

        # Find eligible species configs for this area
        eligible_configs = self.get_eligible_configs(area_id)
        if not eligible_configs:
            return None

        # Weighted selection of species
        weights = [cfg.weight for cfg in eligible_configs]
        chosen_config = self._rng.choices(eligible_configs, weights=weights, k=1)[0]

        # Determine level and personality
        level = self._rng.randint(chosen_config.min_level, chosen_config.max_level)
        personality = generate_wild_personality(rng=self._rng)

        # Create distinct individual Pokemon with its species available attacks
        wild_pokemon = Pokemon(
            species=chosen_config.species,
            personality=personality,
            level=level,
            attacks=chosen_config.species.available_attacks,
        )
        wild_pokemon.current_hp = determine_wild_hp(wild_pokemon.max_hp, rng=self._rng)

        # Register in active area population
        self._active_pokemon[area_id].append(wild_pokemon)

        # Store position if provided
        if position is not None:
            self.set_pokemon_position(wild_pokemon, position)

        return wild_pokemon

    def spawn_until_limit(
        self,
        area_id: str,
        ignore_probability: bool = True,
    ) -> list[Pokemon]:
        """
        Spawns wild Pokemon in an area until the area's maximum capacity is reached.
        Returns a list of all newly spawned Pokemon.
        """
        area = self.get_area(area_id)
        if area is None:
            raise KeyError(f"Spawn area '{area_id}' is not registered.")

        spawned = []
        while self.can_spawn(area_id):
            mon = self.attempt_spawn(area_id, ignore_probability=ignore_probability)
            if mon is None:
                # Break if no species can spawn
                break
            spawned.append(mon)
        return spawned

    # --- Despawning Operations ---

    def despawn_pokemon(
        self,
        area_id: str,
        pokemon: Union[Pokemon, str],
    ) -> Optional[Pokemon]:
        """
        Despawns a wild Pokemon from an area's active population.
        Removes its active tracking and returns the despawned Pokemon instance.
        Returns None if the Pokemon was not found in the area.
        """
        if area_id not in self._areas:
            raise KeyError(f"Spawn area '{area_id}' is not registered.")

        p_id = pokemon.unique_id if isinstance(pokemon, Pokemon) else str(pokemon)
        active_list = self._active_pokemon.get(area_id, [])

        for idx, mon in enumerate(active_list):
            if mon.unique_id == p_id:
                removed = active_list.pop(idx)
                # Clean up position
                self._pokemon_positions.pop(p_id, None)
                return removed

        return None

    def clear_area(self, area_id: str) -> list[Pokemon]:
        """Despawns all active Pokemon in an area and returns them."""
        if area_id not in self._areas:
            raise KeyError(f"Spawn area '{area_id}' is not registered.")

        removed_list = list(self._active_pokemon.get(area_id, []))
        self._active_pokemon[area_id] = []
        for mon in removed_list:
            self._pokemon_positions.pop(mon.unique_id, None)
        return removed_list
