"""
Ability data model for Pokémon.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Ability:
    """
    Represents a passive ability that a Pokémon species can possess.
    At this stage, abilities are static descriptive data.
    """
    name: str
    description: str

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("Ability name cannot be empty.")
        if not self.description or not self.description.strip():
            raise ValueError("Ability description cannot be empty.")
