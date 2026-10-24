"""
Personality model for individual Pokémon.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Personality:
    """
    Represents an individual Pokémon's behavioral traits.
    Each trait ranges from 0 to 100.
    Values are immutable (fixed) at this stage.
    """
    aggression: int
    curiosity: int
    fear: int
    sociability: int
    loyalty: int
    confidence: int

    TRAIT_NAMES = (
        "aggression",
        "curiosity",
        "fear",
        "sociability",
        "loyalty",
        "confidence",
    )

    def __post_init__(self) -> None:
        for trait in self.TRAIT_NAMES:
            value = getattr(self, trait)
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise TypeError(f"Personality trait '{trait}' must be a number, got {type(value).__name__}.")
            if not (0 <= value <= 100):
                raise ValueError(f"Personality trait '{trait}' must be between 0 and 100, got {value}.")

    def to_dict(self) -> dict[str, int]:
        """Returns the personality traits as a dictionary."""
        return {trait: getattr(self, trait) for trait in self.TRAIT_NAMES}
