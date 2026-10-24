"""
World Exploration Manager coordinating region registration, spatial region lookup,
first-time exploration discovery tracking, landmark discovery, and quest integration.
"""
import time
import math
from typing import Optional, Sequence, Callable, Any

from src.models.player import Player
from src.models.world_exploration import WorldRegion, ExplorationResult
from src.models.world_interaction import InteractableType, Interactable
from src.models.world_interaction_manager import WorldInteractionManager
from src.models.quest import QuestEventType
from src.models.quest_manager import QuestManager
from src.data.world_regions import create_default_world_regions
from src.data.world_objects import WORLD_OBJECT_CATALOG, get_world_object


class WorldExplorationManager:
    """
    Service coordinating world exploration, spatial mapping, and discovery:
      - Registers and retrieves logical world regions.
      - Finds regions containing 2D coordinates with a deterministic overlap policy.
      - Tracks per-player discovered regions and landmarks.
      - Dispatches unique, deduplicated quest events upon first-time discovery.
      - Integrates with WorldInteractionManager for proximity-validated landmark discovery.
    """

    def __init__(
        self,
        regions: Optional[Sequence[WorldRegion]] = None,
        interaction_manager: Optional[WorldInteractionManager] = None,
        quest_manager: Optional[QuestManager] = None,
        clock: Optional[Callable[[], float]] = None,
    ) -> None:
        """
        Initializes the WorldExplorationManager.

        Args:
            regions: Optional initial sequence of WorldRegion instances.
                     If None, initializes with fresh default catalog instances.
            interaction_manager: Optional WorldInteractionManager for landmark integration.
            quest_manager: Optional QuestManager for dispatching discovery quest events.
            clock: Optional clock callable returning float timestamps (defaults to time.time).
        """
        self._regions: dict[str, WorldRegion] = {}
        self._region_order: list[str] = []
        self._interaction_manager: Optional[WorldInteractionManager] = interaction_manager
        self._quest_manager: Optional[QuestManager] = quest_manager
        self._clock: Callable[[], float] = clock if clock is not None else time.time

        initial_regions = regions if regions is not None else create_default_world_regions()
        for r in initial_regions:
            self.register_region(r)

    @property
    def interaction_manager(self) -> Optional[WorldInteractionManager]:
        """Associated WorldInteractionManager instance, if configured."""
        return self._interaction_manager

    @interaction_manager.setter
    def interaction_manager(self, im: Optional[WorldInteractionManager]) -> None:
        self._interaction_manager = im

    @property
    def quest_manager(self) -> Optional[QuestManager]:
        """Associated QuestManager instance, if configured."""
        return self._quest_manager

    @quest_manager.setter
    def quest_manager(self, qm: Optional[QuestManager]) -> None:
        self._quest_manager = qm

    # --- Region Registration & Query Methods ---

    def register_region(self, region: WorldRegion) -> None:
        """
        Registers a world region into the manager.

        Raises:
            TypeError: If region is not a WorldRegion instance.
            ValueError: If a region with the same region_id is already registered.
        """
        if not isinstance(region, WorldRegion):
            raise TypeError(f"Expected WorldRegion instance, got {type(region).__name__}.")

        norm_id = region.region_id.lower()
        if norm_id in self._regions:
            raise ValueError(f"Region with ID '{region.region_id}' is already registered.")

        self._regions[norm_id] = region
        self._region_order.append(norm_id)

    def unregister_region(self, region_id: str) -> bool:
        """
        Removes a registered world region by ID.
        Returns True if the region was found and removed, False otherwise.
        """
        if not isinstance(region_id, str):
            return False
        norm_id = region_id.strip().lower()
        if norm_id in self._regions:
            del self._regions[norm_id]
            if norm_id in self._region_order:
                self._region_order.remove(norm_id)
            return True
        return False

    def get_region(self, region_id: str) -> Optional[WorldRegion]:
        """Looks up a registered region by its ID."""
        if not isinstance(region_id, str):
            return None
        return self._regions.get(region_id.strip().lower())

    def list_regions(self) -> list[WorldRegion]:
        """Returns all registered regions in registration order."""
        return [self._regions[rid] for rid in self._region_order]

    def is_position_valid(self, position: Any) -> bool:
        """Checks whether a position is a valid 2D coordinate tuple or list."""
        if not isinstance(position, (tuple, list)) or len(position) != 2:
            return False
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
            return False
        return True

    def find_region(self, position: Sequence[float]) -> Optional[WorldRegion]:
        """
        Finds the registered region containing the given 2D coordinates.

        Deterministic Overlap Policy:
            If coordinates fall within multiple registered regions, returns the
            first matching region according to registration order.

        Args:
            position: 2D coordinate (x, y).

        Returns:
            The matching WorldRegion, or None if coordinates lie outside all regions.
        """
        if not self.is_position_valid(position):
            raise ValueError(f"position must be a valid 2D coordinate (x, y), got {position!r}.")

        for rid in self._region_order:
            region = self._regions[rid]
            if region.contains_point(position):
                return region
        return None

    def find_all_regions(self, position: Sequence[float]) -> list[WorldRegion]:
        """
        Returns all registered regions containing the given 2D coordinates.
        Useful for inspecting multi-zone overlaps.
        """
        if not self.is_position_valid(position):
            raise ValueError(f"position must be a valid 2D coordinate (x, y), got {position!r}.")

        return [
            self._regions[rid]
            for rid in self._region_order
            if self._regions[rid].contains_point(position)
        ]

    # --- Discovery Operations ---

    def discover_region(
        self,
        player: Player,
        region_id: str,
        current_time: Optional[float] = None,
        quest_manager: Optional[QuestManager] = None,
    ) -> ExplorationResult:
        """
        Discovers a registered region for the specified player.

        Discovery Rules:
          - Validates player and region existence.
          - If already discovered by this player, returns success with is_first_discovery=False.
          - If first-time discovery, records it on the player and emits a deduplicated quest event.

        Returns:
            ExplorationResult summarizing discovery status, text, and emitted events.
        """
        if not isinstance(player, Player):
            raise TypeError(f"player must be a Player instance, got {type(player).__name__}.")

        if not isinstance(region_id, str) or not region_id.strip():
            return ExplorationResult(
                success=False,
                error_type="UNKNOWN_REGION",
                message="region_id must be a non-empty string.",
            )

        norm_id = region_id.strip().lower()
        region = self.get_region(norm_id)
        if region is None:
            return ExplorationResult(
                success=False,
                region_id=norm_id,
                error_type="UNKNOWN_REGION",
                message=f"World region '{region_id}' not found.",
            )

        # Check if already discovered by player
        if player.is_region_discovered(norm_id):
            return ExplorationResult(
                success=True,
                region_id=norm_id,
                is_first_discovery=False,
                message=f"Region '{region.name}' has already been discovered.",
                discovery_text=region.discovery_text,
                event_emitted=False,
            )

        # Record first discovery
        player.mark_region_discovered(norm_id)

        # Dispatch quest event
        active_qm = quest_manager if quest_manager is not None else self._quest_manager
        event_emitted = False
        if active_qm is not None:
            event_id = f"quest_evt_region_{norm_id}_{player.unique_id}"
            active_qm.record_event(
                player=player,
                event_type=QuestEventType.REGION_DISCOVERED,
                payload={"region_id": norm_id, "region_name": region.name, "count": 1},
                event_id=event_id,
            )
            event_emitted = True

        return ExplorationResult(
            success=True,
            region_id=norm_id,
            is_first_discovery=True,
            message=f"Discovered region: {region.name}!",
            discovery_text=region.discovery_text,
            event_emitted=event_emitted,
        )

    def discover_region_at_position(
        self,
        player: Player,
        position: Sequence[float],
        current_time: Optional[float] = None,
        quest_manager: Optional[QuestManager] = None,
    ) -> ExplorationResult:
        """
        Resolves the region containing the coordinates and attempts discovery.

        Returns:
            ExplorationResult summarizing discovery status or failure.
        """
        if not isinstance(player, Player):
            raise TypeError(f"player must be a Player instance, got {type(player).__name__}.")

        if not self.is_position_valid(position):
            return ExplorationResult(
                success=False,
                error_type="INVALID_POSITION",
                message=f"Invalid position coordinates: {position!r}.",
            )

        region = self.find_region(position)
        if region is None:
            return ExplorationResult(
                success=False,
                error_type="OUTSIDE_REGIONS",
                message=f"Position {position} is outside all registered world regions.",
            )

        return self.discover_region(
            player=player,
            region_id=region.region_id,
            current_time=current_time,
            quest_manager=quest_manager,
        )

    def discover_landmark(
        self,
        player: Player,
        landmark_id: str,
        player_position: Optional[Sequence[float]] = None,
        current_time: Optional[float] = None,
        quest_manager: Optional[QuestManager] = None,
    ) -> ExplorationResult:
        """
        Discovers a landmark in the world, validating proximity and recording discovery.

        Landmark Integration:
          - Resolves landmark definition from interaction_manager or static catalog.
          - If player_position is specified, verifies player is within landmark's interaction radius.
          - If landmark was already discovered by this player, returns without duplicate progress.
          - If first-time discovery, records it on player and emits a deduplicated quest event.

        Returns:
            ExplorationResult summarizing landmark discovery status.
        """
        if not isinstance(player, Player):
            raise TypeError(f"player must be a Player instance, got {type(player).__name__}.")

        if not isinstance(landmark_id, str) or not landmark_id.strip():
            return ExplorationResult(
                success=False,
                error_type="UNKNOWN_LANDMARK",
                message="landmark_id must be a non-empty string.",
            )

        norm_id = landmark_id.strip().lower()

        # Resolve landmark object
        obj: Optional[Interactable] = None
        if self._interaction_manager is not None:
            obj = self._interaction_manager.get_object(norm_id)
        if obj is None:
            obj = get_world_object(norm_id)

        if obj is None or obj.interactable_type != InteractableType.LANDMARK:
            return ExplorationResult(
                success=False,
                landmark_id=norm_id,
                error_type="UNKNOWN_LANDMARK",
                message=f"World landmark '{landmark_id}' not found.",
            )

        # Proximity check if position provided
        if player_position is not None:
            if not self.is_position_valid(player_position):
                return ExplorationResult(
                    success=False,
                    landmark_id=norm_id,
                    error_type="INVALID_POSITION",
                    message=f"Invalid player position coordinates: {player_position!r}.",
                )
            dist = obj.distance_to(player_position)
            if dist > obj.interaction_radius:
                return ExplorationResult(
                    success=False,
                    landmark_id=norm_id,
                    error_type="OUT_OF_RANGE",
                    message=(
                        f"Player is out of range to discover {obj.name} "
                        f"({dist:.2f} > {obj.interaction_radius:.2f} max radius)."
                    ),
                )

        # Check if already discovered
        if player.is_landmark_discovered(norm_id):
            return ExplorationResult(
                success=True,
                landmark_id=norm_id,
                is_first_discovery=False,
                message=f"Landmark '{obj.name}' has already been discovered.",
                discovery_text=obj.interaction_text,
                event_emitted=False,
            )

        # Record first discovery
        player.mark_landmark_discovered(norm_id)

        # Dispatch quest event
        active_qm = quest_manager if quest_manager is not None else self._quest_manager
        event_emitted = False
        if active_qm is not None:
            event_id = f"quest_evt_landmark_{norm_id}_{player.unique_id}"
            active_qm.record_event(
                player=player,
                event_type=QuestEventType.LANDMARK_DISCOVERED,
                payload={"landmark_id": norm_id, "landmark_name": obj.name, "count": 1},
                event_id=event_id,
            )
            event_emitted = True

        return ExplorationResult(
            success=True,
            landmark_id=norm_id,
            is_first_discovery=True,
            message=f"Discovered landmark: {obj.name}!",
            discovery_text=obj.interaction_text,
            event_emitted=event_emitted,
        )

    # --- Convenience Player Exploration Queries ---

    def is_region_discovered(self, player: Player, region_id: str) -> bool:
        """Returns True if the player has discovered the specified region."""
        return player.is_region_discovered(region_id)

    def is_landmark_discovered(self, player: Player, landmark_id: str) -> bool:
        """Returns True if the player has discovered the specified landmark."""
        return player.is_landmark_discovered(landmark_id)

    def get_discovered_regions(self, player: Player) -> set[str]:
        """Returns a copy of the player's discovered region IDs."""
        return set(player.discovered_regions)

    def get_discovered_landmarks(self, player: Player) -> set[str]:
        """Returns a copy of the player's discovered landmark IDs."""
        return set(player.discovered_landmarks)
