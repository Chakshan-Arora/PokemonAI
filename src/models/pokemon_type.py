"""
Type enumeration for Pokémon.
"""
from enum import Enum


class PokemonType(str, Enum):
    """
    Represents elemental Pokémon types.
    Inherits from str and Enum for easy string representation and comparison.
    """
    NORMAL = "Normal"
    FIRE = "Fire"
    WATER = "Water"
    GRASS = "Grass"
    ELECTRIC = "Electric"
    POISON = "Poison"
    FLYING = "Flying"
    BUG = "Bug"
    GROUND = "Ground"
    ROCK = "Rock"
    FIGHTING = "Fighting"
    PSYCHIC = "Psychic"
    GHOST = "Ghost"

    def __str__(self) -> str:
        return self.value
