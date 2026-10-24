"""
Battle state enumeration defining the lifecycle of a battle.
"""
from enum import Enum


class BattleState(str, Enum):
    """
    Represents the operational state of a Pokemon battle.
    """
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    VICTORY = "VICTORY"
    DEFEAT = "DEFEAT"
    DRAW = "DRAW"
    ESCAPED = "ESCAPED"
    FLED = "ESCAPED"
    CAPTURED = "CAPTURED"
    CANCELED = "CANCELED"

    def is_terminal(self) -> bool:
        """Returns True if the battle has concluded and no further actions are allowed."""
        return self in (
            BattleState.VICTORY,
            BattleState.DEFEAT,
            BattleState.DRAW,
            BattleState.ESCAPED,
            BattleState.CAPTURED,
            BattleState.CANCELED,
        )

    def __str__(self) -> str:
        return self.value
