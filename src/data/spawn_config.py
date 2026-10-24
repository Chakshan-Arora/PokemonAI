"""
Spawn configurations and sample areas for wild Pokemon species.
"""
from dataclasses import dataclass
from typing import Sequence
from src.models.species import PokemonSpecies
from src.models.spawn_area import SpawnArea
from src.data.species import (
    PIKACHU,
    CHARMANDER,
    SQUIRTLE,
    BULBASAUR,
    PIDGEY,
    RATTATA,
    CATERPIE,
    BUTTERFREE,
    GEODUDE,
    ZUBAT,
    MACHOP,
    GASTLY,
    ABRA,
    EEVEE,
    GROWLITHE,
    POLIWAG,
)


@dataclass(frozen=True)
class SpeciesSpawnConfig:
    """
    Configuration defining how, where, and with what rarity a Pokemon species can spawn.
    """
    species: PokemonSpecies
    weight: int
    allowed_area_ids: tuple[str, ...]
    min_level: int = 2
    max_level: int = 5

    def __post_init__(self) -> None:
        if not isinstance(self.species, PokemonSpecies):
            raise TypeError(f"species must be a PokemonSpecies instance, got {type(self.species).__name__}.")

        if not isinstance(self.weight, int) or isinstance(self.weight, bool) or self.weight <= 0:
            raise ValueError(f"weight must be a positive integer (> 0), got {self.weight}.")

        if not self.allowed_area_ids:
            raise ValueError("allowed_area_ids cannot be empty.")

        # Normalize and validate allowed_area_ids
        if isinstance(self.allowed_area_ids, (list, tuple)):
            for area_id in self.allowed_area_ids:
                if not area_id or not str(area_id).strip():
                    raise ValueError("All area IDs must be non-empty strings.")
            object.__setattr__(
                self, "allowed_area_ids", tuple(str(a).strip() for a in self.allowed_area_ids)
            )
        else:
            raise TypeError("allowed_area_ids must be a sequence of strings.")

        if not isinstance(self.min_level, int) or isinstance(self.min_level, bool) or self.min_level < 1:
            raise ValueError(f"min_level must be an integer >= 1, got {self.min_level}.")

        if not isinstance(self.max_level, int) or isinstance(self.max_level, bool) or self.max_level < self.min_level:
            raise ValueError(f"max_level must be >= min_level ({self.min_level}), got {self.max_level}.")


# Standard species spawn configurations
PIKACHU_SPAWN_CONFIG = SpeciesSpawnConfig(
    species=PIKACHU,
    weight=70,  # Common in forest and grassland
    allowed_area_ids=("forest", "grassland", "meadow_spawns", "forest_spawns", "shrine_spawns"),
    min_level=3,
    max_level=6,
)

CHARMANDER_SPAWN_CONFIG = SpeciesSpawnConfig(
    species=CHARMANDER,
    weight=30,  # Rarer species
    allowed_area_ids=("mountain", "grassland", "forest_spawns", "shrine_spawns"),
    min_level=3,
    max_level=6,
)

SQUIRTLE_SPAWN_CONFIG = SpeciesSpawnConfig(
    species=SQUIRTLE,
    weight=50,  # Moderate rarity in lakeside
    allowed_area_ids=("lakeside", "meadow_spawns"),
    min_level=3,
    max_level=6,
)

BULBASAUR_SPAWN_CONFIG = SpeciesSpawnConfig(
    species=BULBASAUR,
    weight=30,
    allowed_area_ids=("forest", "grassland", "meadow_spawns"),
    min_level=3,
    max_level=6,
)

PIDGEY_SPAWN_CONFIG = SpeciesSpawnConfig(
    species=PIDGEY,
    weight=60,
    allowed_area_ids=("forest", "grassland", "meadow_spawns", "forest_spawns"),
    min_level=2,
    max_level=5,
)

RATTATA_SPAWN_CONFIG = SpeciesSpawnConfig(
    species=RATTATA,
    weight=60,
    allowed_area_ids=("grassland", "meadow_spawns", "forest_spawns"),
    min_level=2,
    max_level=5,
)

CATERPIE_SPAWN_CONFIG = SpeciesSpawnConfig(
    species=CATERPIE,
    weight=50,
    allowed_area_ids=("forest", "meadow_spawns", "forest_spawns"),
    min_level=2,
    max_level=4,
)

BUTTERFREE_SPAWN_CONFIG = SpeciesSpawnConfig(
    species=BUTTERFREE,
    weight=20,
    allowed_area_ids=("forest", "forest_spawns"),
    min_level=4,
    max_level=7,
)

GEODUDE_SPAWN_CONFIG = SpeciesSpawnConfig(
    species=GEODUDE,
    weight=50,
    allowed_area_ids=("mountain", "shrine_spawns"),
    min_level=3,
    max_level=6,
)

ZUBAT_SPAWN_CONFIG = SpeciesSpawnConfig(
    species=ZUBAT,
    weight=40,
    allowed_area_ids=("forest", "mountain", "forest_spawns", "shrine_spawns"),
    min_level=3,
    max_level=6,
)

MACHOP_SPAWN_CONFIG = SpeciesSpawnConfig(
    species=MACHOP,
    weight=30,
    allowed_area_ids=("mountain", "forest_spawns", "shrine_spawns"),
    min_level=3,
    max_level=6,
)

GASTLY_SPAWN_CONFIG = SpeciesSpawnConfig(
    species=GASTLY,
    weight=40,
    allowed_area_ids=("shrine_spawns",),
    min_level=4,
    max_level=7,
)

ABRA_SPAWN_CONFIG = SpeciesSpawnConfig(
    species=ABRA,
    weight=20,
    allowed_area_ids=("grassland", "forest_spawns"),
    min_level=3,
    max_level=6,
)

EEVEE_SPAWN_CONFIG = SpeciesSpawnConfig(
    species=EEVEE,
    weight=15,
    allowed_area_ids=("grassland", "meadow_spawns"),
    min_level=3,
    max_level=5,
)

GROWLITHE_SPAWN_CONFIG = SpeciesSpawnConfig(
    species=GROWLITHE,
    weight=25,
    allowed_area_ids=("mountain", "shrine_spawns"),
    min_level=3,
    max_level=6,
)

POLIWAG_SPAWN_CONFIG = SpeciesSpawnConfig(
    species=POLIWAG,
    weight=40,
    allowed_area_ids=("lakeside", "meadow_spawns"),
    min_level=2,
    max_level=5,
)

DEFAULT_SPAWN_CONFIGS: tuple[SpeciesSpawnConfig, ...] = (
    PIKACHU_SPAWN_CONFIG,
    CHARMANDER_SPAWN_CONFIG,
    SQUIRTLE_SPAWN_CONFIG,
    BULBASAUR_SPAWN_CONFIG,
    PIDGEY_SPAWN_CONFIG,
    RATTATA_SPAWN_CONFIG,
    CATERPIE_SPAWN_CONFIG,
    BUTTERFREE_SPAWN_CONFIG,
    GEODUDE_SPAWN_CONFIG,
    ZUBAT_SPAWN_CONFIG,
    MACHOP_SPAWN_CONFIG,
    GASTLY_SPAWN_CONFIG,
    ABRA_SPAWN_CONFIG,
    EEVEE_SPAWN_CONFIG,
    GROWLITHE_SPAWN_CONFIG,
    POLIWAG_SPAWN_CONFIG,
)


def create_sample_spawn_areas() -> dict[str, SpawnArea]:
    """Factory creating the default sample spawn areas."""
    return {
        "forest": SpawnArea(
            area_id="forest",
            name="Viridian Forest",
            allowed_species=(PIKACHU,),
            max_active_pokemon=3,
            base_spawn_probability=0.8,
            encounter_radius=8.0,
        ),
        "grassland": SpawnArea(
            area_id="grassland",
            name="Pallet Grassland",
            allowed_species=(PIKACHU, CHARMANDER),
            max_active_pokemon=4,
            base_spawn_probability=0.9,
            encounter_radius=10.0,
        ),
        "lakeside": SpawnArea(
            area_id="lakeside",
            name="Cerulean Lakeside",
            allowed_species=(SQUIRTLE,),
            max_active_pokemon=3,
            base_spawn_probability=0.85,
            encounter_radius=7.0,
        ),
        "mountain": SpawnArea(
            area_id="mountain",
            name="Cinnabar Mountain",
            allowed_species=(CHARMANDER,),
            max_active_pokemon=2,
            base_spawn_probability=0.7,
            encounter_radius=6.0,
        ),
    }
