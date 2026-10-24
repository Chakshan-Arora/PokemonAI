"""
Structured decision protocol for autonomous Pokemon agents.
Defines action types, structured decision payloads, and emotional state models.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class AgentActionType(str, Enum):
    """
    Permitted action types proposed by an autonomous Pokemon agent.
    """
    OBEY = "obey"                       # Follows trainer's exact command
    ATTACK = "attack"                   # Autonomously selects and executes a move
    DEFEND = "defend"                   # Focuses on defensive posture or dodging
    HESITATE = "hesitate"               # Freezes, wavers, or hesitates due to fear or doubt
    DISOBEY = "disobey"                 # Refuses command (slacking off, ignoring trainer)
    FLEE = "flee"                       # Attempts to escape or retreat from danger
    INSPECT = "inspect"                 # Curiously examines opponent, trainer, or area
    INTERACT = "interact"               # Social gesture or interaction
    SUGGEST_ALTERNATIVE = "suggest"     # Proposes an alternate move or tactic to trainer
    PROTEST = "protest"                 # Verbally or physically objects to trainer's action
    REQUEST_RELEASE = "request_release" # Pleads with trainer to be set free
    REST = "rest"                       # Rests, naps, or idles


@dataclass
class AgentDecision:
    """
    Structured outcome of an agent's decision-making process.
    Contains intended action, tactical parameters, dialogue/cries, and internal rationale.
    """
    action_type: AgentActionType
    intent: str
    target: Optional[str] = None
    chosen_move: Optional[str] = None
    dialogue: Optional[str] = None
    emotional_state: str = "neutral"
    rationale: str = ""
    confidence: float = 1.0
    suggested_alternative: Optional[str] = None
    trust_delta: float = 0.0
    affection_delta: float = 0.0

    def __post_init__(self) -> None:
        if isinstance(self.action_type, str):
            try:
                self.action_type = AgentActionType(self.action_type)
            except ValueError:
                self.action_type = AgentActionType.HESITATE
        self.confidence = max(0.0, min(1.0, float(self.confidence)))

    def to_dict(self) -> dict[str, Any]:
        """Serializes decision to dictionary."""
        return {
            "action_type": self.action_type.value,
            "intent": self.intent,
            "target": self.target,
            "chosen_move": self.chosen_move,
            "dialogue": self.dialogue,
            "emotional_state": self.emotional_state,
            "rationale": self.rationale,
            "confidence": round(self.confidence, 2),
            "suggested_alternative": self.suggested_alternative,
            "trust_delta": self.trust_delta,
            "affection_delta": self.affection_delta,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentDecision":
        """Reconstructs decision from dictionary."""
        if not isinstance(data, dict):
            raise TypeError("AgentDecision data must be a dictionary.")

        raw_action = data.get("action_type", AgentActionType.HESITATE.value)
        try:
            action_type = AgentActionType(raw_action)
        except ValueError:
            action_type = AgentActionType.HESITATE

        raw_trust = data.get("trust_delta")
        raw_aff = data.get("affection_delta")
        try:
            trust_delta = float(raw_trust) if raw_trust is not None else 0.0
        except (ValueError, TypeError):
            trust_delta = 0.0

        try:
            affection_delta = float(raw_aff) if raw_aff is not None else 0.0
        except (ValueError, TypeError):
            affection_delta = 0.0

        return cls(
            action_type=action_type,
            intent=str(data.get("intent", "unspecified")),
            target=data.get("target"),
            chosen_move=data.get("chosen_move"),
            dialogue=data.get("dialogue"),
            emotional_state=str(data.get("emotional_state", "neutral")),
            rationale=str(data.get("rationale", "")),
            confidence=float(data.get("confidence", 1.0)),
            suggested_alternative=data.get("suggested_alternative"),
            trust_delta=trust_delta,
            affection_delta=affection_delta,
        )
