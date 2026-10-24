"""
Species move learning tables.
Defines level-up move learning progression for species using predefined attack definitions.
"""
from dataclasses import dataclass
from typing import Union, Optional
from src.models.attack import Attack
from src.models.species import PokemonSpecies
from src.data.attacks import (
    TACKLE,
    QUICK_ATTACK,
    SCRATCH,
    THUNDER_SHOCK,
    THUNDERBOLT,
    EMBER,
    FLAMETHROWER,
    WATER_GUN,
    HYDRO_PUMP,
    VINE_WHIP,
    RAZOR_LEAF,
    POISON_POWDER,
    GUST,
    WING_ATTACK,
    BITE,
    HYPER_FANG,
    BUG_BITE,
    LEECH_LIFE,
    ROCK_THROW,
    ROCK_SLIDE,
    DEFENSE_CURL,
    CONFUSE_RAY,
    LOW_KICK,
    KARATE_CHOP,
    BRICK_BREAK,
    LICK,
    NIGHT_SHADE,
    SHADOW_BALL,
    CONFUSION,
    PSYBEAM,
    PSYCHIC_ATTACK,
    FLAME_WHEEL,
    BUBBLE,
    BODY_SLAM,
)


@dataclass(frozen=True)
class LevelUpMove:
    """
    Represents an attack learnable by a Pokémon upon reaching a specific level.
    """
    level: int
    attack: Attack

    def __post_init__(self) -> None:
        if not isinstance(self.level, int) or isinstance(self.level, bool):
            raise TypeError(f"level must be an integer, got {type(self.level).__name__}.")
        if self.level < 1:
            raise ValueError(f"level must be positive (>= 1), got {self.level}.")
        if not isinstance(self.attack, Attack):
            raise TypeError(f"attack must be an Attack instance, got {type(self.attack).__name__}.")


# Species move learning progression tables
SPECIES_MOVE_LEARNING: dict[str, tuple[LevelUpMove, ...]] = {
    "Pikachu": (
        LevelUpMove(level=1, attack=THUNDER_SHOCK),
        LevelUpMove(level=3, attack=QUICK_ATTACK),
        LevelUpMove(level=6, attack=TACKLE),
        LevelUpMove(level=10, attack=THUNDERBOLT),
    ),
    "Charmander": (
        LevelUpMove(level=1, attack=SCRATCH),
        LevelUpMove(level=3, attack=EMBER),
        LevelUpMove(level=6, attack=TACKLE),
        LevelUpMove(level=10, attack=FLAMETHROWER),
    ),
    "Squirtle": (
        LevelUpMove(level=1, attack=TACKLE),
        LevelUpMove(level=3, attack=WATER_GUN),
        LevelUpMove(level=6, attack=QUICK_ATTACK),
        LevelUpMove(level=10, attack=HYDRO_PUMP),
    ),
    "Bulbasaur": (
        LevelUpMove(level=1, attack=TACKLE),
        LevelUpMove(level=3, attack=VINE_WHIP),
        LevelUpMove(level=6, attack=POISON_POWDER),
        LevelUpMove(level=10, attack=RAZOR_LEAF),
    ),
    "Pidgey": (
        LevelUpMove(level=1, attack=TACKLE),
        LevelUpMove(level=3, attack=GUST),
        LevelUpMove(level=6, attack=QUICK_ATTACK),
        LevelUpMove(level=10, attack=WING_ATTACK),
    ),
    "Rattata": (
        LevelUpMove(level=1, attack=TACKLE),
        LevelUpMove(level=3, attack=QUICK_ATTACK),
        LevelUpMove(level=6, attack=BITE),
        LevelUpMove(level=10, attack=HYPER_FANG),
    ),
    "Caterpie": (
        LevelUpMove(level=1, attack=TACKLE),
        LevelUpMove(level=3, attack=BUG_BITE),
        LevelUpMove(level=6, attack=TACKLE),
    ),
    "Butterfree": (
        LevelUpMove(level=1, attack=TACKLE),
        LevelUpMove(level=3, attack=GUST),
        LevelUpMove(level=6, attack=CONFUSION),
        LevelUpMove(level=10, attack=PSYBEAM),
    ),
    "Geodude": (
        LevelUpMove(level=1, attack=TACKLE),
        LevelUpMove(level=3, attack=ROCK_THROW),
        LevelUpMove(level=6, attack=DEFENSE_CURL),
        LevelUpMove(level=10, attack=ROCK_SLIDE),
    ),
    "Zubat": (
        LevelUpMove(level=1, attack=LEECH_LIFE),
        LevelUpMove(level=3, attack=BITE),
        LevelUpMove(level=6, attack=WING_ATTACK),
        LevelUpMove(level=10, attack=CONFUSE_RAY),
    ),
    "Machop": (
        LevelUpMove(level=1, attack=LOW_KICK),
        LevelUpMove(level=3, attack=KARATE_CHOP),
        LevelUpMove(level=6, attack=TACKLE),
        LevelUpMove(level=10, attack=BRICK_BREAK),
    ),
    "Gastly": (
        LevelUpMove(level=1, attack=LICK),
        LevelUpMove(level=3, attack=CONFUSE_RAY),
        LevelUpMove(level=6, attack=NIGHT_SHADE),
        LevelUpMove(level=10, attack=SHADOW_BALL),
    ),
    "Abra": (
        LevelUpMove(level=1, attack=TACKLE),
        LevelUpMove(level=3, attack=CONFUSION),
        LevelUpMove(level=6, attack=PSYBEAM),
        LevelUpMove(level=10, attack=PSYCHIC_ATTACK),
    ),
    "Eevee": (
        LevelUpMove(level=1, attack=TACKLE),
        LevelUpMove(level=3, attack=QUICK_ATTACK),
        LevelUpMove(level=6, attack=BITE),
        LevelUpMove(level=10, attack=BODY_SLAM),
    ),
    "Growlithe": (
        LevelUpMove(level=1, attack=BITE),
        LevelUpMove(level=3, attack=EMBER),
        LevelUpMove(level=6, attack=FLAME_WHEEL),
        LevelUpMove(level=10, attack=FLAMETHROWER),
    ),
    "Poliwag": (
        LevelUpMove(level=1, attack=WATER_GUN),
        LevelUpMove(level=3, attack=BUBBLE),
        LevelUpMove(level=6, attack=BODY_SLAM),
        LevelUpMove(level=10, attack=HYDRO_PUMP),
    ),
}


def _normalize_species_name(species: Union[PokemonSpecies, str]) -> str:
    """Extracts and normalizes the species name string."""
    if isinstance(species, PokemonSpecies):
        return species.name.strip()
    elif isinstance(species, str):
        return species.strip()
    else:
        raise TypeError(f"species must be a PokemonSpecies or string, got {type(species).__name__}.")


def get_learnable_moves(species: Union[PokemonSpecies, str]) -> tuple[LevelUpMove, ...]:
    """
    Returns all learnable level-up moves for a given species, sorted by level.
    Returns an empty tuple if the species has no configured move-learning table.
    """
    name = _normalize_species_name(species)
    for sp_name, moves in SPECIES_MOVE_LEARNING.items():
        if sp_name.lower() == name.lower():
            return moves
    return ()


def get_moves_at_level(species: Union[PokemonSpecies, str], level: int) -> tuple[Attack, ...]:
    """
    Returns all attacks learnable by a species at a specific level.
    """
    if not isinstance(level, int) or isinstance(level, bool):
        raise TypeError(f"level must be an integer, got {type(level).__name__}.")
    learnable = get_learnable_moves(species)
    return tuple(entry.attack for entry in learnable if entry.level == level)


def get_moves_in_level_range(
    species: Union[PokemonSpecies, str],
    start_level: int,
    end_level: int,
    inclusive_start: bool = False,
) -> list[LevelUpMove]:
    """
    Returns all level-up moves learnable within a level transition range in ascending order.
    By default, excludes start_level and includes end_level (start_level < level <= end_level).
    If inclusive_start is True, includes start_level (start_level <= level <= end_level).
    """
    if not isinstance(start_level, int) or isinstance(start_level, bool):
        raise TypeError(f"start_level must be an integer, got {type(start_level).__name__}.")
    if not isinstance(end_level, int) or isinstance(end_level, bool):
        raise TypeError(f"end_level must be an integer, got {type(end_level).__name__}.")
    if end_level < start_level:
        return []

    learnable = get_learnable_moves(species)
    result: list[LevelUpMove] = []
    for entry in learnable:
        condition = (
            (start_level <= entry.level <= end_level)
            if inclusive_start
            else (start_level < entry.level <= end_level)
        )
        if condition:
            result.append(entry)

    result.sort(key=lambda m: m.level)
    return result
