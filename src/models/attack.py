"""
Attack data model for Pokémon.
"""
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING
from src.models.pokemon_type import PokemonType

if TYPE_CHECKING:
    from src.models.status_effect import AttackEffect


@dataclass(frozen=True)
class Attack:
    """
    Represents an attack/move that can be used by Pokémon.
    Supports optional move effects (status conditions and stat modifiers).
    """
    name: str
    type: PokemonType
    power: int
    accuracy: int
    effect: Optional["AttackEffect"] = None

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("Attack name cannot be empty.")
        if not isinstance(self.type, PokemonType):
            raise TypeError(f"Attack type must be an instance of PokemonType, got {type(self.type).__name__}.")
        if self.power < 0:
            raise ValueError(f"Attack power cannot be negative, got {self.power}.")
        if not (0 <= self.accuracy <= 100):
            raise ValueError(f"Attack accuracy must be between 0 and 100, got {self.accuracy}.")
        if self.effect is not None:
            from src.models.status_effect import AttackEffect
            if not isinstance(self.effect, AttackEffect):
                raise TypeError(f"Attack effect must be an AttackEffect instance, got {type(self.effect).__name__}.")
