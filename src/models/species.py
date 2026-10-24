"""
Species model defining intrinsic characteristics of a Pokémon species.
"""
from dataclasses import dataclass, field
from typing import Optional, Sequence
from src.models.pokemon_type import PokemonType
from src.models.attack import Attack
from src.models.ability import Ability


@dataclass(frozen=True)
class PokemonSpecies:
    """
    Represents the template/blueprint for a Pokémon species (e.g. Pikachu).
    Defines baseline stats, types, available moves, and abilities.
    """
    name: str
    primary_type: PokemonType
    base_hp: int
    base_attack: int
    base_defense: int
    base_speed: int
    secondary_type: Optional[PokemonType] = None
    available_attacks: tuple[Attack, ...] = field(default_factory=tuple)
    abilities: tuple[Ability, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("Species name cannot be empty.")

        if not isinstance(self.primary_type, PokemonType):
            raise TypeError(f"Primary type must be a PokemonType, got {type(self.primary_type).__name__}.")

        if self.secondary_type is not None:
            if not isinstance(self.secondary_type, PokemonType):
                raise TypeError(f"Secondary type must be a PokemonType or None, got {type(self.secondary_type).__name__}.")
            if self.secondary_type == self.primary_type:
                raise ValueError("Secondary type cannot be the same as primary type.")

        for stat_name, stat_value in [
            ("base_hp", self.base_hp),
            ("base_attack", self.base_attack),
            ("base_defense", self.base_defense),
            ("base_speed", self.base_speed),
        ]:
            if not isinstance(stat_value, int) or isinstance(stat_value, bool):
                raise TypeError(f"{stat_name} must be an integer, got {type(stat_value).__name__}.")
            if stat_value <= 0:
                raise ValueError(f"{stat_name} must be positive (> 0), got {stat_value}.")

        # Convert sequences to tuples if passed as lists, ensuring immutability
        if isinstance(self.available_attacks, (list, tuple)):
            for attack in self.available_attacks:
                if not isinstance(attack, Attack):
                    raise TypeError(f"All available attacks must be Attack instances, got {type(attack).__name__}.")
            object.__setattr__(self, "available_attacks", tuple(self.available_attacks))
        else:
            raise TypeError("available_attacks must be a sequence of Attack objects.")

        if isinstance(self.abilities, (list, tuple)):
            for ability in self.abilities:
                if not isinstance(ability, Ability):
                    raise TypeError(f"All abilities must be Ability instances, got {type(ability).__name__}.")
            object.__setattr__(self, "abilities", tuple(self.abilities))
        else:
            raise TypeError("abilities must be a sequence of Ability objects.")

    @property
    def types(self) -> tuple[PokemonType, ...]:
        """Returns all types associated with this species."""
        if self.secondary_type:
            return (self.primary_type, self.secondary_type)
        return (self.primary_type,)
