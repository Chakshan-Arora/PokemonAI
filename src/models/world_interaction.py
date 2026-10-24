"""
World interaction models for interactable objects, object types, and interaction results.
Defines InteractableType, Interactable, and InteractionResult.
"""
from enum import Enum
from dataclasses import dataclass, field
import math
from typing import Optional, Sequence, Any


class InteractableType(Enum):
    """
    Categories of interactable objects in the game world.
    """
    RESOURCE_NODE = "resource_node"  # Renewable nodes granting resources with cooldown
    TREASURE = "treasure"            # One-time treasure chests and hidden item caches
    SIGN = "sign"                    # Informational signposts and notices
    LANDMARK = "landmark"            # Points of interest, shrines, and discovery sites
    NPC = "npc"                      # Non-player characters and quest givers
    POKEMON_CENTER = "pokemon_center"  # Healing facility restoring team HP and stats

    @property
    def display_name(self) -> str:
        return self.value.replace("_", " ").title()


@dataclass
class Interactable:
    """
    Represents an interactable entity in the game world at a logical 2D coordinate.

    Attributes:
        object_id: Stable string identifier (e.g. "berry_bush_route1").
        name: Human-readable display name.
        description: Textual description of the object.
        interactable_type: Category of interactable (InteractableType).
        position: Logical 2D coordinates (x, y).
        interaction_radius: Maximum Euclidean distance for player interaction.
        is_available: Whether the object can currently be interacted with.
        rewards: Dictionary of item_id -> quantity granted upon interaction.
        interaction_text: Descriptive dialog/sign text returned upon interaction.
        respawn_duration: Cooldown duration in seconds before a resource node respawns.
        respawn_deadline: Timestamp at/after which the object becomes available again.
    """
    object_id: str
    name: str
    description: str
    interactable_type: InteractableType
    position: tuple[float, float]
    interaction_radius: float = 2.0
    is_available: bool = True
    rewards: dict[str, int] = field(default_factory=dict)
    interaction_text: Optional[str] = None
    respawn_duration: Optional[float] = None
    respawn_deadline: Optional[float] = None
    npc_id: Optional[str] = None
    region_id: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.object_id, str) or not self.object_id.strip():
            raise ValueError("object_id must be a non-empty string.")
        self.object_id = self.object_id.strip()

        if self.region_id is not None:
            if not isinstance(self.region_id, str) or not self.region_id.strip():
                raise ValueError("region_id must be a non-empty string or None.")
            self.region_id = self.region_id.strip().lower()

        if self.npc_id is not None:
            if not isinstance(self.npc_id, str) or not self.npc_id.strip():
                raise ValueError("npc_id must be a non-empty string or None.")
            self.npc_id = self.npc_id.strip().lower()

        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("name must be a non-empty string.")
        self.name = self.name.strip()

        if not isinstance(self.description, str):
            raise TypeError("description must be a string.")

        if not isinstance(self.interactable_type, InteractableType):
            raise TypeError(
                f"interactable_type must be an InteractableType enum, got {type(self.interactable_type).__name__}."
            )

        # Validate position
        if not isinstance(self.position, (tuple, list)) or len(self.position) != 2:
            raise ValueError(f"position must be a 2D coordinate tuple (x, y), got {self.position!r}.")

        x, y = self.position
        if not isinstance(x, (int, float)) or isinstance(x, bool) or math.isnan(x) or math.isinf(x):
            raise ValueError(f"position x coordinate must be a finite number, got {x}.")
        if not isinstance(y, (int, float)) or isinstance(y, bool) or math.isnan(y) or math.isinf(y):
            raise ValueError(f"position y coordinate must be a finite number, got {y}.")
        self.position = (float(x), float(y))

        # Validate radius
        if (
            not isinstance(self.interaction_radius, (int, float))
            or isinstance(self.interaction_radius, bool)
            or self.interaction_radius <= 0.0
            or math.isnan(self.interaction_radius)
            or math.isinf(self.interaction_radius)
        ):
            raise ValueError(
                f"interaction_radius must be a positive number > 0, got {self.interaction_radius}."
            )
        self.interaction_radius = float(self.interaction_radius)

        if not isinstance(self.is_available, bool):
            raise TypeError(f"is_available must be a boolean, got {type(self.is_available).__name__}.")

        # Validate rewards
        if not isinstance(self.rewards, dict):
            raise TypeError("rewards must be a dictionary mapping item_id to positive quantity.")
        for item_id, qty in self.rewards.items():
            if not isinstance(item_id, str) or not item_id.strip():
                raise ValueError(f"Reward item_id must be a non-empty string, got {item_id!r}.")
            if not isinstance(qty, int) or isinstance(qty, bool) or qty <= 0:
                raise ValueError(f"Reward quantity for '{item_id}' must be a positive integer, got {qty}.")

        # Sign validation
        if self.interactable_type == InteractableType.SIGN:
            if not isinstance(self.interaction_text, str) or not self.interaction_text.strip():
                raise ValueError("Signs must have a non-empty interaction_text.")

        # Respawn duration validation
        if self.respawn_duration is not None:
            if (
                not isinstance(self.respawn_duration, (int, float))
                or isinstance(self.respawn_duration, bool)
                or self.respawn_duration <= 0.0
                or math.isnan(self.respawn_duration)
                or math.isinf(self.respawn_duration)
            ):
                raise ValueError(f"respawn_duration must be a positive number > 0, got {self.respawn_duration}.")
            self.respawn_duration = float(self.respawn_duration)

        if self.respawn_deadline is not None:
            if (
                not isinstance(self.respawn_deadline, (int, float))
                or isinstance(self.respawn_deadline, bool)
                or math.isnan(self.respawn_deadline)
                or math.isinf(self.respawn_deadline)
            ):
                raise ValueError(f"respawn_deadline must be a finite float or None, got {self.respawn_deadline}.")
            self.respawn_deadline = float(self.respawn_deadline)

    def distance_to(self, player_position: Sequence[float]) -> float:
        """Calculates Euclidean distance to the player's coordinate."""
        if not isinstance(player_position, (tuple, list)) or len(player_position) != 2:
            raise ValueError(f"Player position must be a 2D coordinate (x, y), got {player_position!r}.")
        px, py = player_position
        if (
            not isinstance(px, (int, float))
            or isinstance(px, bool)
            or math.isnan(px)
            or math.isinf(px)
            or not isinstance(py, (int, float))
            or isinstance(py, bool)
            or math.isnan(py)
            or math.isinf(py)
        ):
            raise ValueError(f"Player coordinates must be finite numbers, got {player_position!r}.")
        return math.hypot(self.position[0] - float(px), self.position[1] - float(py))

    def is_in_range(self, player_position: Sequence[float]) -> bool:
        """True if the player position is within interaction_radius."""
        return self.distance_to(player_position) <= self.interaction_radius

    def is_available_at(self, current_time: Optional[float] = None) -> bool:
        """
        Determines whether the object is available to interact with.
        If depleted with a respawn deadline, checks if current_time >= respawn_deadline.
        """
        if self.is_available:
            return True
        if self.respawn_deadline is not None and current_time is not None:
            return current_time >= self.respawn_deadline
        return False


@dataclass(frozen=True)
class InteractionResult:
    """
    Structured outcome of interacting with a world object.
    """
    success: bool
    object_id: str
    interactable_type: InteractableType
    message: str
    items_granted: dict[str, int] = field(default_factory=dict)
    interaction_text: Optional[str] = None
    respawn_deadline: Optional[float] = None
    is_discovered: bool = False
    is_first_discovery: bool = False
    npc_id: Optional[str] = None
    region_id: Optional[str] = None
