"""
Status effect models and definitions for Pokémon battles.
Defines supported status conditions (Burn, Poison, Paralysis) and temporary stat modifiers
(Attack reduction, Defense reduction).
"""
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Union


class StatusEffectType(Enum):
    """
    Supported status effect types.
    """
    BURN = "burn"
    POISON = "poison"
    PARALYSIS = "paralysis"
    ATTACK_REDUCTION = "attack_reduction"
    DEFENSE_REDUCTION = "defense_reduction"

    @property
    def is_major_condition(self) -> bool:
        """True if this is a persistent major condition (Burn, Poison, Paralysis)."""
        return self in (
            StatusEffectType.BURN,
            StatusEffectType.POISON,
            StatusEffectType.PARALYSIS,
        )

    @property
    def is_stat_reduction(self) -> bool:
        """True if this is a temporary stat reduction (Attack, Defense)."""
        return self in (
            StatusEffectType.ATTACK_REDUCTION,
            StatusEffectType.DEFENSE_REDUCTION,
        )

    @property
    def display_name(self) -> str:
        """Formatted human-readable name."""
        return self.value.replace("_", " ").title()


# Default parameters for status effects
DEFAULT_BURN_DAMAGE_FRACTION: float = 0.0625   # 1/16th of max HP
DEFAULT_POISON_DAMAGE_FRACTION: float = 0.0625 # 1/16th of max HP
DEFAULT_PARALYSIS_CHANCE: int = 25             # 25% chance to skip turn
DEFAULT_STAT_REDUCTION_DURATION: int = 3       # 3 turns
DEFAULT_STAT_REDUCTION_MULTIPLIER: float = 0.8 # 20% reduction


@dataclass(frozen=True)
class AttackEffect:
    """
    Metadata attached to an Attack defining an effect it can inflict upon use.
    """
    effect_type: StatusEffectType
    chance: int = 100                             # Application chance (1 - 100%)
    duration: Optional[int] = None                # Remaining turns for temporary stat reductions
    multiplier: Optional[float] = None            # Stat multiplier for reductions (e.g. 0.8)
    damage_fraction: Optional[float] = None       # Damage fraction of max HP for burn/poison
    paralysis_chance: int = DEFAULT_PARALYSIS_CHANCE # Chance for paralysis to skip turn (1 - 100%)
    target: str = "defender"                      # "defender" or "user"

    def __post_init__(self) -> None:
        if not isinstance(self.effect_type, StatusEffectType):
            raise TypeError(f"effect_type must be a StatusEffectType, got {type(self.effect_type).__name__}.")

        if not isinstance(self.chance, int) or isinstance(self.chance, bool):
            raise TypeError(f"chance must be an integer, got {type(self.chance).__name__}.")
        if not (1 <= self.chance <= 100):
            raise ValueError(f"chance must be between 1 and 100, got {self.chance}.")

        if self.target not in ("defender", "user"):
            raise ValueError(f"target must be 'defender' or 'user', got '{self.target}'.")

        # Major conditions
        if self.effect_type.is_major_condition:
            if self.effect_type in (StatusEffectType.BURN, StatusEffectType.POISON):
                frac = self.damage_fraction if self.damage_fraction is not None else DEFAULT_BURN_DAMAGE_FRACTION
                if not isinstance(frac, (int, float)) or isinstance(frac, bool) or not (0.0 < frac <= 1.0):
                    raise ValueError(f"damage_fraction must be a float between 0.0 and 1.0, got {frac}.")

            if self.effect_type == StatusEffectType.PARALYSIS:
                if (
                    not isinstance(self.paralysis_chance, int)
                    or isinstance(self.paralysis_chance, bool)
                    or not (1 <= self.paralysis_chance <= 100)
                ):
                    raise ValueError(f"paralysis_chance must be an integer between 1 and 100, got {self.paralysis_chance}.")

        # Stat reductions
        if self.effect_type.is_stat_reduction:
            dur = self.duration if self.duration is not None else DEFAULT_STAT_REDUCTION_DURATION
            if not isinstance(dur, int) or isinstance(dur, bool) or dur < 1:
                raise ValueError(f"duration for stat reductions must be a positive integer, got {dur}.")

            mult = self.multiplier if self.multiplier is not None else DEFAULT_STAT_REDUCTION_MULTIPLIER
            if not isinstance(mult, (int, float)) or isinstance(mult, bool) or not (0.0 < mult < 1.0):
                raise ValueError(f"multiplier for stat reductions must be between 0.0 and 1.0, got {mult}.")


@dataclass
class StatusEffect:
    """
    Represents an active status effect instance applied to an individual Pokémon.
    """
    effect_type: StatusEffectType
    remaining_duration: Optional[int] = None
    multiplier: Optional[float] = None
    damage_fraction: Optional[float] = None
    paralysis_chance: int = DEFAULT_PARALYSIS_CHANCE
    source_attack_name: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.effect_type, StatusEffectType):
            raise TypeError(f"effect_type must be a StatusEffectType, got {type(self.effect_type).__name__}.")

        # Assign defaults based on effect type
        if self.effect_type == StatusEffectType.BURN:
            if self.damage_fraction is None:
                self.damage_fraction = DEFAULT_BURN_DAMAGE_FRACTION
            self.remaining_duration = None
        elif self.effect_type == StatusEffectType.POISON:
            if self.damage_fraction is None:
                self.damage_fraction = DEFAULT_POISON_DAMAGE_FRACTION
            self.remaining_duration = None
        elif self.effect_type == StatusEffectType.PARALYSIS:
            self.remaining_duration = None
        elif self.effect_type.is_stat_reduction:
            if self.remaining_duration is None:
                self.remaining_duration = DEFAULT_STAT_REDUCTION_DURATION
            if self.multiplier is None:
                self.multiplier = DEFAULT_STAT_REDUCTION_MULTIPLIER

    @property
    def is_persistent(self) -> bool:
        """True if condition persists indefinitely during battle (Burn, Poison, Paralysis)."""
        return self.effect_type.is_major_condition

    @property
    def is_temporary(self) -> bool:
        """True if condition is temporary with turn duration (Attack, Defense reductions)."""
        return self.effect_type.is_stat_reduction

    @property
    def is_expired(self) -> bool:
        """True if a temporary effect has reached 0 remaining duration."""
        return (
            not self.is_persistent
            and self.remaining_duration is not None
            and self.remaining_duration <= 0
        )

    def decrement_duration(self) -> int:
        """
        Decrements the remaining duration for temporary stat effects.
        Returns the new remaining duration (or 0 if already expired/persistent).
        """
        if not self.is_persistent and self.remaining_duration is not None:
            self.remaining_duration = max(0, self.remaining_duration - 1)
            return self.remaining_duration
        return 0

    def copy(self) -> "StatusEffect":
        """Creates an independent copy of this status effect."""
        return StatusEffect(
            effect_type=self.effect_type,
            remaining_duration=self.remaining_duration,
            multiplier=self.multiplier,
            damage_fraction=self.damage_fraction,
            paralysis_chance=self.paralysis_chance,
            source_attack_name=self.source_attack_name,
        )

    @classmethod
    def from_attack_effect(
        cls,
        attack_effect: AttackEffect,
        source_attack_name: Optional[str] = None,
    ) -> "StatusEffect":
        """Constructs an active StatusEffect from an AttackEffect definition."""
        return cls(
            effect_type=attack_effect.effect_type,
            remaining_duration=attack_effect.duration,
            multiplier=attack_effect.multiplier,
            damage_fraction=attack_effect.damage_fraction,
            paralysis_chance=attack_effect.paralysis_chance,
            source_attack_name=source_attack_name,
        )
