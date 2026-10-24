"""
Player behavior tracking and classification model based on wild Pokémon interactions.
Classifies trainer demeanor as AGGRESSIVE, PEACEFUL, or NEUTRAL / WHATEVER based on
recent wild encounter actions and outcomes.
"""
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Sequence, Any


class PlayerBehaviorProfile(str, Enum):
    """
    Behavioral profile of the player towards wild Pokémon.
    """
    AGGRESSIVE = "aggressive"
    PEACEFUL = "peaceful"
    NEUTRAL = "neutral"
    WHATEVER = "whatever"

    @property
    def display_name(self) -> str:
        return self.value.title()


@dataclass(frozen=True)
class WildEncounterRecord:
    """
    A single recorded action or resolution during a wild Pokémon encounter.
    """
    action: str  # "attack", "flee", "inspect", "defeat", "capture"
    is_aggressive: bool = False
    is_peaceful: bool = False
    species_name: Optional[str] = None
    outcome: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "is_aggressive": self.is_aggressive,
            "is_peaceful": self.is_peaceful,
            "species_name": self.species_name,
            "outcome": self.outcome,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WildEncounterRecord":
        return cls(
            action=str(data.get("action", "")),
            is_aggressive=bool(data.get("is_aggressive", False)),
            is_peaceful=bool(data.get("is_peaceful", False)),
            species_name=data.get("species_name"),
            outcome=data.get("outcome"),
        )


class PlayerBehaviorTracker:
    """
    Analyzes historical interactions with wild Pokémon and categorizes the player's
    reputation / demeanor.
    """

    @staticmethod
    def classify_behavior(
        records: Sequence[Any],
        window_size: int = 10,
    ) -> PlayerBehaviorProfile:
        """
        Classifies player demeanor using the most recent `window_size` wild actions.

        Rules:
          - If empty: NEUTRAL.
          - If aggressive actions >= 2 and significantly outweigh peaceful actions (ratio >= 0.5): AGGRESSIVE.
          - If peaceful actions >= 2 and significantly outweigh aggressive actions (ratio >= 0.5): PEACEFUL.
          - Otherwise: NEUTRAL (or 'whatever').
        """
        if not records:
            return PlayerBehaviorProfile.NEUTRAL

        recent = list(records)[-window_size:]
        agg_count = 0
        peace_count = 0

        for r in recent:
            if isinstance(r, dict):
                act = str(r.get("action", "")).lower()
                is_agg = bool(r.get("is_aggressive", False)) or act in ("attack", "defeat")
                is_peace = bool(r.get("is_peaceful", False)) or act in ("flee", "inspect")
            elif isinstance(r, WildEncounterRecord):
                is_agg = r.is_aggressive or r.action.lower() in ("attack", "defeat")
                is_peace = r.is_peaceful or r.action.lower() in ("flee", "inspect")
            else:
                act = str(r).lower()
                is_agg = act in ("attack", "defeat")
                is_peace = act in ("flee", "inspect")

            if is_agg:
                agg_count += 1
            elif is_peace:
                peace_count += 1

        total = len(recent)
        if total == 0:
            return PlayerBehaviorProfile.NEUTRAL

        if agg_count >= 2 and (agg_count > peace_count) and (agg_count / total >= 0.45):
            return PlayerBehaviorProfile.AGGRESSIVE
        elif peace_count >= 2 and (peace_count > agg_count) and (peace_count / total >= 0.45):
            return PlayerBehaviorProfile.PEACEFUL
        else:
            return PlayerBehaviorProfile.NEUTRAL
