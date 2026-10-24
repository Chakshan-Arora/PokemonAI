"""
Behavior states for Pokemon state machine.
"""
from enum import Enum


class BehaviorState(str, Enum):
    """
    Represents the general behavioral intent of a Pokemon.
    These states indicate what action the Pokemon wants to take in the environment.
    """
    IDLE = "IDLE"
    WANDER = "WANDER"
    INVESTIGATE = "INVESTIGATE"
    APPROACH = "APPROACH"
    FLEE = "FLEE"
    ATTACK = "ATTACK"
    HIDE = "HIDE"

    def __str__(self) -> str:
        return self.value
