"""
Spawn area model representing a logical zone where wild Pokemon can appear.
"""
from dataclasses import dataclass, field
from typing import Sequence, Optional
from src.models.species import PokemonSpecies


@dataclass
class SpawnArea:
    """
    Represents a logical region in the game world with species restrictions,
    population limits, spawn probability, and encounter detection range.
    """
    area_id: str
    name: str
    allowed_species: tuple[PokemonSpecies, ...] = field(default_factory=tuple)
    max_active_pokemon: int = 5
    base_spawn_probability: float = 1.0
    encounter_radius: float = 10.0
    enabled: bool = True
    region_id: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.area_id or not str(self.area_id).strip():
            raise ValueError("area_id cannot be empty.")
        self.area_id = str(self.area_id).strip()

        if not self.name or not str(self.name).strip():
            raise ValueError("name cannot be empty.")
        self.name = str(self.name).strip()

        if not isinstance(self.max_active_pokemon, int) or isinstance(self.max_active_pokemon, bool) or self.max_active_pokemon < 1:
            raise ValueError(f"max_active_pokemon must be an integer >= 1, got {self.max_active_pokemon}.")

        if not isinstance(self.base_spawn_probability, (int, float)) or isinstance(self.base_spawn_probability, bool):
            raise TypeError("base_spawn_probability must be a float between 0.0 and 1.0.")
        if not (0.0 <= self.base_spawn_probability <= 1.0):
            raise ValueError(f"base_spawn_probability must be between 0.0 and 1.0, got {self.base_spawn_probability}.")
        self.base_spawn_probability = float(self.base_spawn_probability)

        if not isinstance(self.encounter_radius, (int, float)) or isinstance(self.encounter_radius, bool):
            raise TypeError("encounter_radius must be a positive number.")
        if self.encounter_radius <= 0.0:
            raise ValueError(f"encounter_radius must be greater than 0, got {self.encounter_radius}.")
        self.encounter_radius = float(self.encounter_radius)

        if not isinstance(self.enabled, bool):
            raise TypeError("enabled must be a boolean.")

        # Validate and normalize allowed_species
        if isinstance(self.allowed_species, (list, tuple, set)):
            species_tuple = []
            for sp in self.allowed_species:
                if not isinstance(sp, PokemonSpecies):
                    raise TypeError(f"All allowed species must be PokemonSpecies instances, got {type(sp).__name__}.")
                species_tuple.append(sp)
            self.allowed_species = tuple(species_tuple)
        else:
            raise TypeError("allowed_species must be a sequence of PokemonSpecies instances.")

        if self.region_id is not None:
            if not isinstance(self.region_id, str) or not self.region_id.strip():
                raise ValueError("region_id must be a non-empty string or None.")
            self.region_id = self.region_id.strip().lower()

    def is_species_allowed(self, species: PokemonSpecies) -> bool:
        """Checks if a PokemonSpecies is permitted in this spawn area."""
        if not isinstance(species, PokemonSpecies):
            return False
        return any(sp.name == species.name for sp in self.allowed_species)
