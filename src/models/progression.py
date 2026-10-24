"""
Progression and leveling mechanics for Pokemon.
Manages XP accumulation, level-up thresholds, and stat recalculation.
"""
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.pokemon import Pokemon

# Maximum level a Pokemon can reach in the system
MAX_LEVEL: int = 100

# Base XP multiplier per level (XP required for next level = current_level * 100)
XP_PER_LEVEL_MULTIPLIER: int = 100


@dataclass(frozen=True)
class LevelUpResult:
    """
    Structured outcome of an experience gain and leveling event.
    """
    pokemon: "Pokemon"
    levels_gained: int
    initial_level: int
    final_level: int
    initial_xp: int
    final_xp: int
    hp_gained: int
    xp_applied: int


def get_xp_for_next_level(level: int) -> int:
    """
    Calculates the experience points required to advance from the given level
    to the next level.
    Formula: current_level * 100.

    Args:
        level: Current Pokemon level (must be integer between 1 and 100).

    Returns:
        The XP required for the next level.
    """
    if not isinstance(level, int) or isinstance(level, bool):
        raise TypeError(f"level must be an integer, got {type(level).__name__}.")
    if level < 1:
        raise ValueError(f"level must be at least 1, got {level}.")
    if level > MAX_LEVEL:
        raise ValueError(f"level cannot exceed maximum level of {MAX_LEVEL}, got {level}.")
    return level * XP_PER_LEVEL_MULTIPLIER


def calculate_xp_for_next_level(level: int) -> int:
    """Alias for get_xp_for_next_level."""
    return get_xp_for_next_level(level)


def apply_experience(pokemon: "Pokemon", xp: int) -> LevelUpResult:
    """
    Awards experience points to a Pokemon, triggering level-up(s) if thresholds are met.
    Remaining XP after leveling carries forward.

    Level-up effects:
      - Level increases (capped at MAX_LEVEL 100).
      - Maximum HP recalculates dynamically: species.base_hp + (level * 2).
      - If alive, current HP increases by the gained max HP (benefiting from level-up).
      - If fainted, current HP remains 0 (preserving fainted invariant).
      - Current HP is clamped so it never exceeds new max HP or falls below 0.

    Args:
        pokemon: The Pokemon receiving experience.
        xp: Amount of experience points to award (must be non-negative integer).

    Returns:
        LevelUpResult containing detailed progression metrics.
    """
    from src.models.pokemon import Pokemon

    if not isinstance(pokemon, Pokemon):
        raise TypeError(f"pokemon must be a Pokemon instance, got {type(pokemon).__name__}.")
    if not isinstance(xp, int) or isinstance(xp, bool):
        raise TypeError(f"xp must be an integer, got {type(xp).__name__}.")
    if xp < 0:
        raise ValueError(f"xp cannot be negative, got {xp}.")

    initial_level = pokemon.level
    initial_xp = pokemon.experience
    initial_max_hp = pokemon.max_hp
    initial_hp = pokemon.current_hp

    # If already at max level, XP cannot trigger level-ups
    if pokemon.level >= MAX_LEVEL:
        return LevelUpResult(
            pokemon=pokemon,
            levels_gained=0,
            initial_level=initial_level,
            final_level=initial_level,
            initial_xp=initial_xp,
            final_xp=initial_xp,
            hp_gained=0,
            xp_applied=xp,
        )

    accumulated_xp = initial_xp + xp
    current_lvl = initial_level

    while current_lvl < MAX_LEVEL:
        needed = get_xp_for_next_level(current_lvl)
        if accumulated_xp >= needed:
            accumulated_xp -= needed
            current_lvl += 1
        else:
            break

    # If reached MAX_LEVEL, reset leftover XP to 0 (no further level progression)
    if current_lvl >= MAX_LEVEL:
        accumulated_xp = 0

    levels_gained = current_lvl - initial_level

    # Apply updated level and remaining XP to Pokemon
    pokemon.level = current_lvl
    pokemon.experience = accumulated_xp

    # Recalculate HP benefits
    new_max_hp = pokemon.max_hp
    max_hp_delta = new_max_hp - initial_max_hp
    hp_gained = 0

    if levels_gained > 0:
        if initial_hp > 0:
            # Active/alive Pokemon gains current HP equal to max HP growth
            hp_gained = max_hp_delta
            pokemon.current_hp = min(new_max_hp, initial_hp + hp_gained)
        else:
            # Fainted Pokemon retains 0 HP invariant
            pokemon.current_hp = 0

    return LevelUpResult(
        pokemon=pokemon,
        levels_gained=levels_gained,
        initial_level=initial_level,
        final_level=current_lvl,
        initial_xp=initial_xp,
        final_xp=accumulated_xp,
        hp_gained=hp_gained,
        xp_applied=xp,
    )
