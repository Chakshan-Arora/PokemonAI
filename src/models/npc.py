"""
NPC (Non-Player Character) model representing in-world characters and quest givers.
Defines NPC identity, location, offered quests, dialogue, and proximity validation.
"""
from dataclasses import dataclass, field
import math
from typing import Optional, Sequence, Any


@dataclass(frozen=True)
class NPC:
    """
    Immutable model representing an in-world character/quest giver.

    Attributes:
        npc_id: Unique string identifier (e.g., 'prof_oak').
        name: Display name (e.g., 'Professor Oak').
        title: Professional or role title (e.g., 'Pokemon Researcher').
        description: Visual or background description.
        position: Logical 2D coordinate (x, y).
        interaction_radius: Maximum Euclidean distance for interaction (default 2.5).
        offered_quest_ids: Sequence of quest IDs offered by this character.
        dialogue: Dictionary mapping dialogue context keys to spoken text.
    """
    npc_id: str
    name: str
    title: str
    description: str
    position: tuple[float, float]
    interaction_radius: float = 2.5
    offered_quest_ids: tuple[str, ...] = field(default_factory=tuple)
    dialogue: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.npc_id, str) or not self.npc_id.strip():
            raise ValueError("npc_id must be a non-empty string.")
        object.__setattr__(self, "npc_id", self.npc_id.strip().lower())

        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("name must be a non-empty string.")
        object.__setattr__(self, "name", self.name.strip())

        if not isinstance(self.title, str):
            raise TypeError("title must be a string.")
        object.__setattr__(self, "title", self.title.strip())

        if not isinstance(self.description, str):
            raise TypeError("description must be a string.")
        object.__setattr__(self, "description", self.description.strip())

        # Validate position (x, y)
        if not isinstance(self.position, (tuple, list)) or len(self.position) != 2:
            raise ValueError(f"position must be a 2D coordinate tuple (x, y), got {self.position!r}.")

        px, py = self.position
        if not isinstance(px, (int, float)) or isinstance(px, bool) or math.isnan(px) or math.isinf(px):
            raise ValueError(f"position x coordinate must be a finite number, got {px}.")
        if not isinstance(py, (int, float)) or isinstance(py, bool) or math.isnan(py) or math.isinf(py):
            raise ValueError(f"position y coordinate must be a finite number, got {py}.")
        object.__setattr__(self, "position", (float(px), float(py)))

        # Validate interaction_radius
        if (
            not isinstance(self.interaction_radius, (int, float))
            or isinstance(self.interaction_radius, bool)
            or self.interaction_radius <= 0.0
            or math.isnan(self.interaction_radius)
            or math.isinf(self.interaction_radius)
        ):
            raise ValueError(f"interaction_radius must be a positive number > 0, got {self.interaction_radius}.")
        object.__setattr__(self, "interaction_radius", float(self.interaction_radius))

        # Validate offered_quest_ids
        if not isinstance(self.offered_quest_ids, (tuple, list)):
            raise TypeError("offered_quest_ids must be a sequence of quest ID strings.")
        norm_quests: list[str] = []
        for q_id in self.offered_quest_ids:
            if not isinstance(q_id, str) or not q_id.strip():
                raise ValueError("All offered quest IDs must be non-empty strings.")
            norm_quests.append(q_id.strip().lower())
        object.__setattr__(self, "offered_quest_ids", tuple(norm_quests))

        # Validate dialogue dictionary
        if not isinstance(self.dialogue, dict):
            raise TypeError("dialogue must be a dictionary mapping string keys to dialogue strings.")
        for k, v in self.dialogue.items():
            if not isinstance(k, str) or not k.strip():
                raise ValueError("Dialogue keys must be non-empty strings.")
            if not isinstance(v, str):
                raise TypeError(f"Dialogue text for key '{k}' must be a string.")

    def distance_to(self, player_position: Sequence[float]) -> float:
        """
        Calculates Euclidean distance to the player coordinate.

        Args:
            player_position: 2D coordinate (x, y).

        Returns:
            Euclidean distance as float.
        """
        if not isinstance(player_position, (tuple, list)) or len(player_position) != 2:
            raise ValueError(f"player_position must be a 2D coordinate (x, y), got {player_position!r}.")
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
            raise ValueError(f"player_position coordinates must be finite numbers, got {player_position!r}.")
        return math.hypot(self.position[0] - float(px), self.position[1] - float(py))

    def is_in_range(self, player_position: Sequence[float]) -> bool:
        """True if the player position is within interaction_radius."""
        return self.distance_to(player_position) <= self.interaction_radius

    def get_dialogue(self, key: str, default: Optional[str] = None) -> str:
        """
        Retrieves dialogue text for a context key with an optional fallback.

        Args:
            key: Contextual key (e.g., 'greeting', 'farewell').
            default: Fallback string if key is not found.

        Returns:
            Dialogue text string.
        """
        if not isinstance(key, str):
            return default if default is not None else ""
        norm_key = key.strip().lower()
        if norm_key in self.dialogue:
            return self.dialogue[norm_key]
        return default if default is not None else ""

    def get_quest_dialogue(
        self,
        quest_id: str,
        dialogue_type: str,
        default: Optional[str] = None,
    ) -> str:
        """
        Retrieves quest-specific dialogue for an offered quest.

        Tries the following keys in priority order:
          1. "{quest_id}_{dialogue_type}" (e.g. "first_encounter_offer")
          2. "{dialogue_type}_{quest_id}" (e.g. "offer_first_encounter")
          3. "{dialogue_type}" (generic type fallback, e.g. "offer")
          4. default argument

        Args:
            quest_id: Quest ID string.
            dialogue_type: Dialogue category ('offer', 'locked', 'in_progress', 'completed', 'declined').
            default: Fallback string if no matching key is found.

        Returns:
            Dialogue string.
        """
        norm_qid = quest_id.strip().lower() if isinstance(quest_id, str) else ""
        norm_type = dialogue_type.strip().lower() if isinstance(dialogue_type, str) else ""

        key1 = f"{norm_qid}_{norm_type}"
        if key1 in self.dialogue:
            return self.dialogue[key1]

        key2 = f"{norm_type}_{norm_qid}"
        if key2 in self.dialogue:
            return self.dialogue[key2]

        if norm_type in self.dialogue:
            return self.dialogue[norm_type]

        return default if default is not None else ""
