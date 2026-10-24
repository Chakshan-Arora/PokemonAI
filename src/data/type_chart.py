"""
Type effectiveness chart and multiplier calculations for Pokemon battles.
"""
from typing import Sequence
from src.models.pokemon_type import PokemonType
from src.models.attack import Attack
from src.models.pokemon import Pokemon


# Attacking type -> {Defending type -> Multiplier}
TYPE_EFFECTIVENESS_CHART: dict[PokemonType, dict[PokemonType, float]] = {
    PokemonType.NORMAL: {
        PokemonType.NORMAL: 1.0,
        PokemonType.FIRE: 1.0,
        PokemonType.WATER: 1.0,
        PokemonType.GRASS: 1.0,
        PokemonType.ELECTRIC: 1.0,
        PokemonType.ROCK: 0.5,
        PokemonType.GHOST: 0.0,
    },
    PokemonType.FIRE: {
        PokemonType.NORMAL: 1.0,
        PokemonType.FIRE: 0.5,
        PokemonType.WATER: 0.5,
        PokemonType.GRASS: 2.0,
        PokemonType.ELECTRIC: 1.0,
        PokemonType.BUG: 2.0,
        PokemonType.ROCK: 0.5,
    },
    PokemonType.WATER: {
        PokemonType.NORMAL: 1.0,
        PokemonType.FIRE: 2.0,
        PokemonType.WATER: 0.5,
        PokemonType.GRASS: 0.5,
        PokemonType.ELECTRIC: 1.0,
        PokemonType.GROUND: 2.0,
        PokemonType.ROCK: 2.0,
    },
    PokemonType.GRASS: {
        PokemonType.NORMAL: 1.0,
        PokemonType.FIRE: 0.5,
        PokemonType.WATER: 2.0,
        PokemonType.GRASS: 0.5,
        PokemonType.ELECTRIC: 1.0,
        PokemonType.POISON: 0.5,
        PokemonType.FLYING: 0.5,
        PokemonType.BUG: 0.5,
        PokemonType.GROUND: 2.0,
        PokemonType.ROCK: 2.0,
    },
    PokemonType.ELECTRIC: {
        PokemonType.NORMAL: 1.0,
        PokemonType.FIRE: 1.0,
        PokemonType.WATER: 2.0,
        PokemonType.GRASS: 0.5,
        PokemonType.ELECTRIC: 0.5,
        PokemonType.FLYING: 2.0,
        PokemonType.GROUND: 0.0,
    },
    PokemonType.POISON: {
        PokemonType.GRASS: 2.0,
        PokemonType.POISON: 0.5,
        PokemonType.GROUND: 0.5,
        PokemonType.ROCK: 0.5,
        PokemonType.GHOST: 0.5,
    },
    PokemonType.FLYING: {
        PokemonType.GRASS: 2.0,
        PokemonType.FIGHTING: 2.0,
        PokemonType.BUG: 2.0,
        PokemonType.ELECTRIC: 0.5,
        PokemonType.ROCK: 0.5,
    },
    PokemonType.BUG: {
        PokemonType.GRASS: 2.0,
        PokemonType.PSYCHIC: 2.0,
        PokemonType.FIRE: 0.5,
        PokemonType.FIGHTING: 0.5,
        PokemonType.FLYING: 0.5,
        PokemonType.POISON: 0.5,
        PokemonType.GHOST: 0.5,
    },
    PokemonType.GROUND: {
        PokemonType.FIRE: 2.0,
        PokemonType.ELECTRIC: 2.0,
        PokemonType.POISON: 2.0,
        PokemonType.ROCK: 2.0,
        PokemonType.GRASS: 0.5,
        PokemonType.BUG: 0.5,
        PokemonType.FLYING: 0.0,
    },
    PokemonType.ROCK: {
        PokemonType.FIRE: 2.0,
        PokemonType.FLYING: 2.0,
        PokemonType.BUG: 2.0,
        PokemonType.FIGHTING: 0.5,
        PokemonType.GROUND: 0.5,
    },
    PokemonType.FIGHTING: {
        PokemonType.NORMAL: 2.0,
        PokemonType.ROCK: 2.0,
        PokemonType.POISON: 0.5,
        PokemonType.FLYING: 0.5,
        PokemonType.PSYCHIC: 0.5,
        PokemonType.BUG: 0.5,
        PokemonType.GHOST: 0.0,
    },
    PokemonType.PSYCHIC: {
        PokemonType.FIGHTING: 2.0,
        PokemonType.POISON: 2.0,
        PokemonType.PSYCHIC: 0.5,
    },
    PokemonType.GHOST: {
        PokemonType.GHOST: 2.0,
        PokemonType.PSYCHIC: 2.0,
        PokemonType.NORMAL: 0.0,
    },
}


def get_type_effectiveness(attacking_type: PokemonType, defending_type: PokemonType) -> float:
    """
    Returns the damage multiplier of an attacking type against a single defending type.
    Defaults to 1.0 if not defined.
    """
    if not isinstance(attacking_type, PokemonType):
        raise TypeError(f"attacking_type must be a PokemonType, got {type(attacking_type).__name__}.")
    if not isinstance(defending_type, PokemonType):
        raise TypeError(f"defending_type must be a PokemonType, got {type(defending_type).__name__}.")

    attack_matchups = TYPE_EFFECTIVENESS_CHART.get(attacking_type, {})
    return attack_matchups.get(defending_type, 1.0)


def get_effectiveness_against_types(
    attacking_type: PokemonType,
    defending_types: Sequence[PokemonType],
) -> float:
    """
    Calculates combined damage multiplier against one or more defending types (e.g. dual-types).
    Multipliers from each defending type are multiplied together.
    """
    if not defending_types:
        return 1.0

    multiplier = 1.0
    for def_type in defending_types:
        multiplier *= get_type_effectiveness(attacking_type, def_type)
    return multiplier


def get_effectiveness_against_pokemon(attack: Attack, defender: Pokemon) -> float:
    """
    Calculates the type effectiveness multiplier of an attack against a defender Pokemon.
    Considers the attack's type and all of the defender's species types.
    """
    if not isinstance(attack, Attack):
        raise TypeError(f"Expected Attack instance, got {type(attack).__name__}.")
    if not isinstance(defender, Pokemon):
        raise TypeError(f"Expected Pokemon instance, got {type(defender).__name__}.")

    return get_effectiveness_against_types(attack.type, defender.species.types)
