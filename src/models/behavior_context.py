"""
Environmental context perceived by a Pokemon.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class BehaviorContext:
    """
    Represents perceptual data and environmental signals available to a Pokemon.
    Supplied by the game world (or future Godot layer) to drive behavior decisions.
    Sensible defaults allow a baseline calm context to be created with zero arguments.
    """
    distance_to_player: float = 100.0
    player_visible: bool = False
    player_nearby: bool = False
    threat_level: float = 0.0
    territory_distance: float = 0.0
    nearby_pokemon_count: int = 0
    interesting_object_detected: bool = False

    def __post_init__(self) -> None:
        if self.distance_to_player < 0:
            raise ValueError(f"distance_to_player cannot be negative, got {self.distance_to_player}.")
        if self.threat_level < 0:
            raise ValueError(f"threat_level cannot be negative, got {self.threat_level}.")
        if self.territory_distance < 0:
            raise ValueError(f"territory_distance cannot be negative, got {self.territory_distance}.")
        if self.nearby_pokemon_count < 0:
            raise ValueError(f"nearby_pokemon_count cannot be negative, got {self.nearby_pokemon_count}.")
