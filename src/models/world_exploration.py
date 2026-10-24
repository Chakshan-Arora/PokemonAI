"""
World exploration models representing logical map regions and exploration outcomes.
Defines WorldRegion and ExplorationResult.
"""
from dataclasses import dataclass, field
import math
from typing import Optional, Sequence, Any


@dataclass
class WorldRegion:
    """
    Represents a logical geographic zone in the game world defined by 2D bounding box coordinates.

    Attributes:
        region_id: Stable string identifier (e.g., 'starting_meadow').
        name: Human-readable display name.
        description: Textual description of the region.
        bounds: 2D bounding coordinates (min_x, min_y, max_x, max_y).
        discovery_text: Optional narrative/flavor text displayed upon first discovery.
        landmark_ids: Sequence of landmark object IDs located in or associated with this region.
    """
    region_id: str
    name: str
    description: str
    bounds: tuple[float, float, float, float]
    discovery_text: Optional[str] = None
    landmark_ids: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.region_id, str) or not self.region_id.strip():
            raise ValueError("region_id must be a non-empty string.")
        self.region_id = self.region_id.strip().lower()

        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("name must be a non-empty string.")
        self.name = self.name.strip()

        if not isinstance(self.description, str) or not self.description.strip():
            raise ValueError("description must be a non-empty string.")
        self.description = self.description.strip()

        # Validate bounds: (min_x, min_y, max_x, max_y)
        if not isinstance(self.bounds, (tuple, list)) or len(self.bounds) != 4:
            raise ValueError(
                f"bounds must be a 4-tuple of (min_x, min_y, max_x, max_y), got {self.bounds!r}."
            )

        min_x, min_y, max_x, max_y = self.bounds
        for val, name in (
            (min_x, "min_x"),
            (min_y, "min_y"),
            (max_x, "max_x"),
            (max_y, "max_y"),
        ):
            if not isinstance(val, (int, float)) or isinstance(val, bool) or math.isnan(val) or math.isinf(val):
                raise ValueError(f"bounds {name} must be a finite number, got {val!r}.")

        min_x, min_y, max_x, max_y = float(min_x), float(min_y), float(max_x), float(max_y)

        if min_x > max_x:
            raise ValueError(f"Inverted X bounds: min_x ({min_x}) cannot be greater than max_x ({max_x}).")
        if min_y > max_y:
            raise ValueError(f"Inverted Y bounds: min_y ({min_y}) cannot be greater than max_y ({max_y}).")

        self.bounds = (min_x, min_y, max_x, max_y)

        if self.discovery_text is not None:
            if not isinstance(self.discovery_text, str) or not self.discovery_text.strip():
                raise ValueError("discovery_text must be a non-empty string or None.")
            self.discovery_text = self.discovery_text.strip()

        # Validate landmark_ids
        if isinstance(self.landmark_ids, (list, tuple, set)):
            norm_landmarks: list[str] = []
            for lid in self.landmark_ids:
                if not isinstance(lid, str) or not lid.strip():
                    raise ValueError(f"landmark_id must be a non-empty string, got {lid!r}.")
                norm_landmarks.append(lid.strip().lower())
            self.landmark_ids = tuple(norm_landmarks)
        else:
            raise TypeError("landmark_ids must be a sequence of string identifiers.")

    def contains_point(self, position: Sequence[float]) -> bool:
        """
        Determines whether a 2D coordinate lies within this region's bounding box (inclusive).

        Args:
            position: 2D coordinate tuple or list (x, y).

        Returns:
            True if position is within [min_x, max_x] and [min_y, max_y], False otherwise.
        """
        if not isinstance(position, (tuple, list)) or len(position) != 2:
            raise ValueError(f"position must be a 2D coordinate (x, y), got {position!r}.")
        px, py = position
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
            raise ValueError(f"Position coordinates must be finite numbers, got {position!r}.")

        min_x, min_y, max_x, max_y = self.bounds
        return min_x <= float(px) <= max_x and min_y <= float(py) <= max_y

    def center(self) -> tuple[float, float]:
        """Returns the geometric center of this region."""
        min_x, min_y, max_x, max_y = self.bounds
        return ((min_x + max_x) / 2.0, (min_y + max_y) / 2.0)

    def distance_to(self, position: Sequence[float]) -> float:
        """
        Calculates the Euclidean distance from a position to the region's bounding box.
        Returns 0.0 if the position is inside or on the boundary of the region.
        """
        if not isinstance(position, (tuple, list)) or len(position) != 2:
            raise ValueError(f"position must be a 2D coordinate (x, y), got {position!r}.")
        px, py = float(position[0]), float(position[1])
        min_x, min_y, max_x, max_y = self.bounds

        dx = max(0.0, min_x - px, px - max_x)
        dy = max(0.0, min_y - py, py - max_y)
        return math.hypot(dx, dy)


@dataclass(frozen=True)
class ExplorationResult:
    """
    Structured outcome of an exploration or discovery attempt.
    """
    success: bool
    region_id: Optional[str] = None
    landmark_id: Optional[str] = None
    is_first_discovery: bool = False
    message: str = ""
    discovery_text: Optional[str] = None
    event_emitted: bool = False
    error_type: Optional[str] = None
