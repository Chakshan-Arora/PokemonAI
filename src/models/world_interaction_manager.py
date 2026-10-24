"""
World Interaction Manager handling object registration, proximity validation,
atomic reward delivery, resource node respawning, and quest event integration.
"""
import time
import math
from typing import Optional, Sequence, Callable, Any

from src.models.player import Player
from src.models.world_interaction import (
    InteractableType,
    Interactable,
    InteractionResult,
)
from src.models.quest import QuestEventType
from src.models.quest_manager import QuestManager
from src.data.world_objects import create_default_world_objects


class WorldInteractionManager:
    """
    Coordinates player interactions with world objects:
      - Validates 2D player proximity using Euclidean distance.
      - Enforces availability and respawn cooldowns deterministically.
      - Atomically validates and grants item rewards into player inventory.
      - Dispatches unique deduplicated quest events upon successful collection.
      - Tracks collected one-time treasures on the player instance.
    """

    def __init__(
        self,
        objects: Optional[Sequence[Interactable]] = None,
        quest_manager: Optional[QuestManager] = None,
        clock: Optional[Callable[[], float]] = None,
        exploration_manager: Optional[Any] = None,
    ) -> None:
        """
        Initializes the WorldInteractionManager.

        Args:
            objects: Optional initial sequence of Interactable objects.
                     If None, initializes with fresh default catalog instances.
            quest_manager: Optional QuestManager to notify upon resource collection.
            clock: Optional clock callable returning a float timestamp (defaults to time.time).
            exploration_manager: Optional WorldExplorationManager for resolving object regions.
        """
        self._objects: dict[str, Interactable] = {}
        self._quest_manager: Optional[QuestManager] = quest_manager
        self._clock: Callable[[], float] = clock if clock is not None else time.time
        self._exploration_manager: Optional[Any] = exploration_manager
        self._interaction_count: int = 0

        initial_objects = objects if objects is not None else create_default_world_objects()
        for obj in initial_objects:
            self.register_object(obj)

    @property
    def quest_manager(self) -> Optional[QuestManager]:
        """Associated QuestManager instance, if configured."""
        return self._quest_manager

    @quest_manager.setter
    def quest_manager(self, qm: Optional[QuestManager]) -> None:
        self._quest_manager = qm

    @property
    def exploration_manager(self) -> Optional[Any]:
        """Associated WorldExplorationManager instance, if configured."""
        return self._exploration_manager

    @exploration_manager.setter
    def exploration_manager(self, em: Optional[Any]) -> None:
        self._exploration_manager = em

    # --- Registration & Query Methods ---

    def register_object(self, obj: Interactable) -> None:
        """Registers an interactable object in the world registry."""
        if not isinstance(obj, Interactable):
            raise TypeError(f"Expected Interactable instance, got {type(obj).__name__}.")
        self._objects[obj.object_id.lower()] = obj

    def unregister_object(self, object_id: str) -> bool:
        """Removes an interactable object by ID. Returns True if removed."""
        if not isinstance(object_id, str):
            return False
        return self._objects.pop(object_id.strip().lower(), None) is not None

    def get_object(self, object_id: str) -> Optional[Interactable]:
        """Looks up an interactable object by its ID."""
        if not isinstance(object_id, str):
            return None
        return self._objects.get(object_id.strip().lower())

    def list_objects(self) -> list[Interactable]:
        """Returns all registered interactable objects."""
        return list(self._objects.values())

    def list_objects_in_range(
        self, position: Sequence[float], radius: float
    ) -> list[Interactable]:
        """
        Returns all registered objects located within `radius` units
        from the specified coordinate.
        """
        if not isinstance(position, (tuple, list)) or len(position) != 2:
            raise ValueError(f"position must be a 2D coordinate (x, y), got {position!r}.")
        if not isinstance(radius, (int, float)) or isinstance(radius, bool) or radius < 0.0:
            raise ValueError(f"radius must be a non-negative number, got {radius}.")

        results: list[Interactable] = []
        for obj in self._objects.values():
            dist = math.hypot(obj.position[0] - float(position[0]), obj.position[1] - float(position[1]))
            if dist <= float(radius):
                results.append(obj)
        return results

    # --- Availability & Respawn Checking ---

    def is_object_available(
        self,
        object_id: str,
        player: Optional[Player] = None,
        current_time: Optional[float] = None,
    ) -> bool:
        """
        Evaluates whether an object is currently available to be interacted with.

        Rules:
          - If unknown object: False.
          - If TREASURE: unavailable if already collected by player or obj.is_available is False.
          - If RESOURCE_NODE: available if obj.is_available is True, or if
            current_time >= respawn_deadline.
          - If SIGN or LANDMARK: always True.
        """
        obj = self.get_object(object_id)
        if obj is None:
            return False

        effective_time = float(current_time) if current_time is not None else self._clock()

        if obj.interactable_type == InteractableType.TREASURE:
            if player is not None and player.is_treasure_collected(obj.object_id):
                return False
            return obj.is_available

        if obj.interactable_type == InteractableType.RESOURCE_NODE:
            if obj.is_available:
                return True
            if obj.respawn_deadline is not None and effective_time >= obj.respawn_deadline:
                return True
            return False

        return True

    def check_respawns(self, current_time: Optional[float] = None) -> list[str]:
        """
        Scans all resource nodes and restores availability for any node whose
        respawn deadline has passed at the given timestamp.

        Returns:
            List of object IDs that respawned.
        """
        effective_time = float(current_time) if current_time is not None else self._clock()
        respawned_ids: list[str] = []

        for obj in self._objects.values():
            if obj.interactable_type == InteractableType.RESOURCE_NODE and not obj.is_available:
                if obj.respawn_deadline is not None and effective_time >= obj.respawn_deadline:
                    obj.is_available = True
                    obj.respawn_deadline = None
                    respawned_ids.append(obj.object_id)

        return respawned_ids

    # --- Interaction Pre-validation ---

    def can_interact(
        self,
        player: Player,
        object_id: str,
        player_position: Sequence[float],
        current_time: Optional[float] = None,
    ) -> tuple[bool, str]:
        """
        Validates whether a player can perform an interaction with a target object
        without mutating player or world state.

        Returns:
            (True, "OK") or (False, failure_reason).
        """
        if not isinstance(player, Player):
            return False, f"Expected Player instance, got {type(player).__name__}."

        obj = self.get_object(object_id)
        if obj is None:
            return False, f"World object '{object_id}' not found."

        # Validate coordinate format
        try:
            dist = obj.distance_to(player_position)
        except Exception as e:
            return False, f"Invalid player position coordinates: {e}"

        # Proximity check
        if dist > obj.interaction_radius:
            return False, (
                f"Player is out of range ({dist:.2f} > {obj.interaction_radius:.2f} max radius)."
            )

        effective_time = float(current_time) if current_time is not None else self._clock()

        # Type-specific availability check
        if obj.interactable_type == InteractableType.TREASURE:
            if player.is_treasure_collected(obj.object_id):
                return False, f"Treasure '{obj.name}' has already been collected."
            if not obj.is_available:
                return False, f"Treasure '{obj.name}' is currently unavailable."

        elif obj.interactable_type == InteractableType.RESOURCE_NODE:
            if not obj.is_available:
                if obj.respawn_deadline is not None and effective_time >= obj.respawn_deadline:
                    # Eligible for immediate respawn
                    pass
                else:
                    remaining = (
                        (obj.respawn_deadline - effective_time)
                        if obj.respawn_deadline is not None
                        else 0.0
                    )
                    return False, (
                        f"Resource node '{obj.name}' is depleted (respawns in {max(0.0, remaining):.1f}s)."
                    )

        # Inventory reward space check
        if obj.rewards:
            can_add, reason = player.inventory.can_add_items(obj.rewards)
            if not can_add:
                return False, f"Cannot gather '{obj.name}': {reason}"

        return True, "OK"

    # --- Interaction Execution ---

    def interact(
        self,
        player: Player,
        object_id: str,
        player_position: Sequence[float],
        current_time: Optional[float] = None,
        quest_manager: Optional[QuestManager] = None,
        region_id: Optional[str] = None,
        event_id: Optional[str] = None,
    ) -> InteractionResult:
        """
        Executes an interaction between a player and a world object.

        Execution Rules:
          - Validates position, distance, availability, and inventory space.
          - If any check fails, returns a failure result with 0 modifications.
          - If rewards exist, adds items atomically to player inventory.
          - Marks one-time treasures as collected on the player.
          - Depletes resource nodes and sets their respawn deadline.
          - Emits object-interacted quest events with unique deterministic event IDs.
          - Emits item-collected quest events with unique deterministic event IDs.
          - Returns structured InteractionResult.

        Returns:
            InteractionResult summarizing outcome, items granted, and messages.
        """
        if not isinstance(player, Player):
            raise TypeError(f"player must be a Player instance, got {type(player).__name__}.")

        obj = self.get_object(object_id)
        if obj is None:
            return InteractionResult(
                success=False,
                object_id=str(object_id),
                interactable_type=InteractableType.SIGN,
                message=f"World object '{object_id}' not found.",
                region_id=region_id,
            )

        effective_time = float(current_time) if current_time is not None else self._clock()

        # Resolve authoritative region
        eff_region_id: Optional[str] = None
        if isinstance(region_id, str) and region_id.strip():
            eff_region_id = region_id.strip().lower()
        elif obj.region_id is not None:
            eff_region_id = obj.region_id.strip().lower()
        elif self._exploration_manager is not None:
            try:
                reg = self._exploration_manager.find_region(obj.position)
                if reg is not None:
                    eff_region_id = reg.region_id.strip().lower()
            except Exception:
                pass
            if eff_region_id is None:
                try:
                    reg = self._exploration_manager.find_region(player_position)
                    if reg is not None:
                        eff_region_id = reg.region_id.strip().lower()
                except Exception:
                    pass

        # Run validation
        can_do, reason = self.can_interact(
            player=player,
            object_id=obj.object_id,
            player_position=player_position,
            current_time=effective_time,
        )
        if not can_do:
            return InteractionResult(
                success=False,
                object_id=obj.object_id,
                interactable_type=obj.interactable_type,
                message=reason,
                interaction_text=obj.interaction_text if obj.interactable_type in (InteractableType.SIGN, InteractableType.NPC, InteractableType.POKEMON_CENTER) else None,
                npc_id=obj.npc_id,
                region_id=eff_region_id,
            )

        # If depleted resource node was eligible for respawn, refresh it first
        if obj.interactable_type == InteractableType.RESOURCE_NODE and not obj.is_available:
            obj.is_available = True
            obj.respawn_deadline = None

        # Atomically grant item rewards
        granted_items: dict[str, int] = {}
        if obj.rewards:
            add_ok = player.inventory.add_items_atomically(obj.rewards)
            if not add_ok:
                return InteractionResult(
                    success=False,
                    object_id=obj.object_id,
                    interactable_type=obj.interactable_type,
                    message=f"Failed to receive rewards: {player.inventory.last_message}",
                    region_id=eff_region_id,
                )
            granted_items = dict(obj.rewards)

        # Update object and player state
        new_deadline: Optional[float] = None
        is_discovered = False
        is_first_discovery = False

        if obj.interactable_type == InteractableType.RESOURCE_NODE:
            obj.is_available = False
            if obj.respawn_duration is not None and obj.respawn_duration > 0:
                obj.respawn_deadline = effective_time + obj.respawn_duration
                new_deadline = obj.respawn_deadline
            else:
                obj.respawn_deadline = None

        elif obj.interactable_type == InteractableType.TREASURE:
            player.mark_treasure_collected(obj.object_id)

        elif obj.interactable_type == InteractableType.LANDMARK:
            is_discovered = True
            if not player.is_landmark_discovered(obj.object_id):
                player.mark_landmark_discovered(obj.object_id)
                is_first_discovery = True
            else:
                is_first_discovery = False

        elif obj.interactable_type == InteractableType.POKEMON_CENTER:
            all_pokemon = list(dict.fromkeys(player.get_all_pokemon() + player.team))
            for mon in all_pokemon:
                mon.restore_stats()

        # Dispatch quest events if items were collected or landmark discovered
        self._interaction_count += 1
        active_qm = quest_manager if quest_manager is not None else self._quest_manager

        if active_qm is not None:
            # 1. Authoritative OBJECT_INTERACTED quest event
            eff_event_id = event_id if event_id is not None else (
                f"quest_evt_interact_{obj.object_id}_{player.unique_id}_"
                f"{int(effective_time * 1000)}_{self._interaction_count}"
            )
            interact_payload: dict[str, Any] = {
                "object_id": obj.object_id,
                "interactable_type": obj.interactable_type.value,
                "count": 1,
            }
            if eff_region_id:
                interact_payload["region_id"] = eff_region_id
            if obj.npc_id:
                interact_payload["npc_id"] = obj.npc_id

            active_qm.record_event(
                player=player,
                event_type=QuestEventType.OBJECT_INTERACTED,
                payload=interact_payload,
                event_id=eff_event_id,
            )

            # 2. Item collection events
            if granted_items:
                for item_id, qty in granted_items.items():
                    event_id = (
                        f"world_interact_{obj.object_id}_{item_id}_"
                        f"{int(effective_time * 1000)}_{self._interaction_count}"
                    )
                    active_qm.record_event(
                        player=player,
                        event_type=QuestEventType.ITEM_COLLECTED,
                        payload={"item_id": item_id, "count": qty},
                        event_id=event_id,
                    )
            elif obj.interactable_type == InteractableType.LANDMARK and is_first_discovery:
                event_id = f"quest_evt_landmark_{obj.object_id}_{player.unique_id}"
                active_qm.record_event(
                    player=player,
                    event_type=QuestEventType.LANDMARK_DISCOVERED,
                    payload={"landmark_id": obj.object_id, "landmark_name": obj.name},
                    event_id=event_id,
                )

        # Build descriptive message
        if obj.interactable_type == InteractableType.SIGN:
            msg = f"Read {obj.name}: '{obj.interaction_text}'"
        elif obj.interactable_type == InteractableType.LANDMARK:
            msg = f"Discovered {obj.name}! {obj.interaction_text or ''}".strip()
        elif obj.interactable_type == InteractableType.NPC:
            msg = f"Spoke with {obj.name}: '{obj.interaction_text or ''}'".strip()
        elif obj.interactable_type == InteractableType.RESOURCE_NODE:
            items_str = ", ".join(f"{q}x {i}" for i, q in granted_items.items())
            msg = f"Gathered {items_str} from {obj.name}."
        elif obj.interactable_type == InteractableType.POKEMON_CENTER:
            msg = (
                obj.interaction_text
                or f"Welcome to {obj.name}! All your Pokémon have been restored to full health and default stats."
            )
        else:  # TREASURE
            items_str = ", ".join(f"{q}x {i}" for i, q in granted_items.items())
            msg = f"Opened {obj.name} and found: {items_str}."

        return InteractionResult(
            success=True,
            object_id=obj.object_id,
            interactable_type=obj.interactable_type,
            message=msg,
            items_granted=granted_items,
            interaction_text=obj.interaction_text,
            respawn_deadline=new_deadline,
            is_discovered=is_discovered,
            is_first_discovery=is_first_discovery,
            npc_id=obj.npc_id,
            region_id=eff_region_id,
        )
