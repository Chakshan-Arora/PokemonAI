"""
Relationship model for autonomous Pokemon agents.
Tracks evolving social dynamics (trust, affection, respect, familiarity)
with trainers and other Pokemon.
"""
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Optional


class RelationshipStage(str, Enum):
    """Categorical stage of a relationship."""
    STRANGER = "stranger"
    WARY = "wary"
    ACQUAINTANCE = "acquaintance"
    COMPANION = "companion"
    DEVOTED = "devoted"
    RIVAL = "rival"
    RESENTFUL = "resentful"


@dataclass
class Relationship:
    """
    Evolving relationship record between a Pokemon agent and another entity.
    """
    entity_id: str
    entity_name: str
    entity_type: str = "trainer"  # 'trainer', 'wild_pokemon', 'teammate_pokemon', 'npc'
    trust: float = 0.0          # -100.0 (distrust) to +100.0 (unshakable trust)
    affection: float = 0.0      # -100.0 (hatred/dislike) to +100.0 (deep affection)
    respect: float = 0.0        # -100.0 (contempt) to +100.0 (deep admiration)
    familiarity: float = 0.0    # 0.0 (complete stranger) to 100.0 (lifelong companion)
    stage: RelationshipStage = RelationshipStage.STRANGER
    significant_memories: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.trust = max(-100.0, min(100.0, float(self.trust)))
        self.affection = max(-100.0, min(100.0, float(self.affection)))
        self.respect = max(-100.0, min(100.0, float(self.respect)))
        self.familiarity = max(0.0, min(100.0, float(self.familiarity)))
        if isinstance(self.stage, str):
            try:
                self.stage = RelationshipStage(self.stage)
            except ValueError:
                self.stage = RelationshipStage.STRANGER

    def adjust_trust(self, delta: float) -> None:
        """Modifies trust within [-100, 100] and updates stage."""
        self.trust = max(-100.0, min(100.0, self.trust + float(delta)))
        self._auto_update_stage()

    def adjust_affection(self, delta: float) -> None:
        """Modifies affection within [-100, 100] and updates stage."""
        self.affection = max(-100.0, min(100.0, self.affection + float(delta)))
        self._auto_update_stage()

    def adjust_respect(self, delta: float) -> None:
        """Modifies respect within [-100, 100] and updates stage."""
        self.respect = max(-100.0, min(100.0, self.respect + float(delta)))
        self._auto_update_stage()

    def adjust_familiarity(self, delta: float) -> None:
        """Modifies familiarity within [0, 100] and updates stage."""
        self.familiarity = max(0.0, min(100.0, self.familiarity + float(delta)))
        self._auto_update_stage()

    def add_memory(self, episode_id: str) -> None:
        """Links a significant episodic memory to this relationship."""
        if episode_id not in self.significant_memories:
            self.significant_memories.append(episode_id)

    def _auto_update_stage(self) -> None:
        """Heuristically updates relationship stage based on current metrics."""
        if self.trust <= -40.0 or self.affection <= -50.0:
            self.stage = RelationshipStage.RESENTFUL
        elif self.trust >= 65.0 and self.affection >= 65.0 and self.familiarity >= 50.0:
            self.stage = RelationshipStage.DEVOTED
        elif self.trust >= 30.0 and self.affection >= 25.0 and self.familiarity >= 25.0:
            self.stage = RelationshipStage.COMPANION
        elif self.familiarity < 15.0 and self.trust < 10.0:
            self.stage = RelationshipStage.STRANGER if self.trust >= -10.0 else RelationshipStage.WARY
        elif self.trust < 0.0:
            self.stage = RelationshipStage.WARY
        else:
            self.stage = RelationshipStage.ACQUAINTANCE

    def to_dict(self) -> dict[str, Any]:
        """Serializes relationship to dictionary."""
        return {
            "entity_id": self.entity_id,
            "entity_name": self.entity_name,
            "entity_type": self.entity_type,
            "trust": round(self.trust, 2),
            "affection": round(self.affection, 2),
            "respect": round(self.respect, 2),
            "familiarity": round(self.familiarity, 2),
            "stage": self.stage.value,
            "significant_memories": list(self.significant_memories),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Relationship":
        """Reconstructs relationship from dictionary."""
        if not isinstance(data, dict):
            raise TypeError("Relationship data must be a dictionary.")
        return cls(
            entity_id=str(data.get("entity_id", "")),
            entity_name=str(data.get("entity_name", "Unknown")),
            entity_type=str(data.get("entity_type", "trainer")),
            trust=float(data.get("trust", 0.0)),
            affection=float(data.get("affection", 0.0)),
            respect=float(data.get("respect", 0.0)),
            familiarity=float(data.get("familiarity", 0.0)),
            stage=RelationshipStage(data.get("stage", RelationshipStage.STRANGER.value)),
            significant_memories=list(data.get("significant_memories", [])),
        )
