"""
Training manager for Pokemon stat growth.
Allows players to train individual Pokemon in Attack, Defense, and Speed,
enforcing stat caps, clamping, and ensuring changes persist only on the target instance.
"""
from dataclasses import dataclass, field
from typing import Optional, Union, Any
from src.models.pokemon import Pokemon

# Supported combat stats for training
SUPPORTED_TRAINING_STATS: tuple[str, ...] = ("attack", "defense", "speed")

# Default training progression values
DEFAULT_TRAINING_AMOUNT: int = 5
DEFAULT_STAT_CAP: int = 150
DEFAULT_STAT_CAPS: dict[str, int] = {
    "attack": DEFAULT_STAT_CAP,
    "defense": DEFAULT_STAT_CAP,
    "speed": DEFAULT_STAT_CAP,
}


@dataclass(frozen=True)
class TrainingConfig:
    """
    Configuration for training progression, amounts, and stat caps.
    """
    default_amount: int = DEFAULT_TRAINING_AMOUNT
    stat_caps: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_STAT_CAPS))
    max_trained_bonus: Optional[int] = None


@dataclass(frozen=True)
class TrainingResult:
    """
    Structured outcome of a Pokemon training session.
    """
    success: bool
    stat_name: str
    previous_value: int
    new_value: int
    actual_change: int
    reason: str
    pokemon: Optional[Pokemon] = None
    was_clamped: bool = False
    previous_trained: int = 0
    new_trained: int = 0

    @property
    def stat(self) -> str:
        """Alias for stat_name."""
        return self.stat_name

    @property
    def change_amount(self) -> int:
        """Alias for actual_change."""
        return self.actual_change


class TrainingManager:
    """
    Service coordinating training sessions for individual Pokemon.
    Increases combat stats (Attack, Defense, Speed) independently of level progression,
    enforcing configurable stat caps and instance-level isolation.
    """

    def __init__(
        self,
        config: Optional[TrainingConfig] = None,
        default_amount: int = DEFAULT_TRAINING_AMOUNT,
        stat_caps: Optional[dict[str, int]] = None,
        max_trained_bonus: Optional[int] = None,
    ) -> None:
        if config is not None:
            self._config = config
            self._default_amount = config.default_amount
            self._stat_caps = dict(config.stat_caps)
            self._max_trained_bonus = config.max_trained_bonus
        else:
            self._default_amount = default_amount
            self._stat_caps = dict(stat_caps) if stat_caps is not None else dict(DEFAULT_STAT_CAPS)
            self._max_trained_bonus = max_trained_bonus
            self._config = TrainingConfig(
                default_amount=self._default_amount,
                stat_caps=self._stat_caps,
                max_trained_bonus=self._max_trained_bonus,
            )

    @property
    def config(self) -> TrainingConfig:
        """Active training configuration."""
        return self._config

    @property
    def default_amount(self) -> int:
        """Default training increment amount."""
        return self._default_amount

    def get_stat_cap(self, stat_name: str) -> int:
        """Returns the configured cap for the given stat."""
        norm = stat_name.strip().lower() if isinstance(stat_name, str) else ""
        return self._stat_caps.get(norm, DEFAULT_STAT_CAP)

    def can_train(
        self,
        pokemon: Pokemon,
        stat_name: str,
        stat_cap: Optional[int] = None,
    ) -> bool:
        """
        Checks whether a Pokemon is eligible to be trained in the given stat.
        Returns False if fainted, unsupported stat, or already at the stat cap.
        """
        if not isinstance(pokemon, Pokemon):
            return False
        if pokemon.is_fainted or pokemon.current_hp <= 0:
            return False

        norm = stat_name.strip().lower() if isinstance(stat_name, str) else ""
        if norm not in SUPPORTED_TRAINING_STATS:
            return False

        current_val = pokemon.get_stat(norm)
        cap = stat_cap if stat_cap is not None else self.get_stat_cap(norm)
        if self._max_trained_bonus is not None:
            base_val = getattr(pokemon.species, f"base_{norm}")
            cap = min(cap, base_val + self._max_trained_bonus)

        return current_val < cap

    def train_stat(
        self,
        pokemon: Pokemon,
        stat_name: str,
        amount: Optional[int] = None,
        stat_cap: Optional[int] = None,
    ) -> TrainingResult:
        """
        Trains an individual Pokemon in one supported combat stat (Attack, Defense, Speed).

        Rules:
          - Target must be a valid Pokemon instance.
          - Fainted Pokemon cannot be trained.
          - Stat name must be one of: 'attack', 'defense', 'speed' (case-insensitive).
          - Training amount must be a positive integer (> 0).
          - Growth is clamped at the configured stat cap and reports the actual change.
          - Training does not alter species templates, other Pokemon, or HP/XP/level.
        """
        norm_stat = stat_name.strip().lower() if isinstance(stat_name, str) else ""

        # 1. Validate Pokemon instance
        if not isinstance(pokemon, Pokemon):
            return TrainingResult(
                success=False,
                stat_name=str(stat_name),
                previous_value=0,
                new_value=0,
                actual_change=0,
                reason=f"Invalid pokemon: expected Pokemon instance, got {type(pokemon).__name__}.",
                pokemon=None,
            )

        # 2. Validate Stat Name
        if norm_stat not in SUPPORTED_TRAINING_STATS:
            return TrainingResult(
                success=False,
                stat_name=str(stat_name),
                previous_value=0,
                new_value=0,
                actual_change=0,
                reason=f"Unsupported stat '{stat_name}'. Supported stats are: {list(SUPPORTED_TRAINING_STATS)}.",
                pokemon=pokemon,
            )

        # 3. Check Fainted Status
        prev_stat = pokemon.get_stat(norm_stat)
        prev_trained = pokemon.get_trained_stat(norm_stat)

        if pokemon.is_fainted or pokemon.current_hp <= 0:
            return TrainingResult(
                success=False,
                stat_name=norm_stat,
                previous_value=prev_stat,
                new_value=prev_stat,
                actual_change=0,
                reason=f"Cannot train fainted Pokemon '{pokemon.display_name}'.",
                pokemon=pokemon,
                previous_trained=prev_trained,
                new_trained=prev_trained,
            )

        # 4. Validate Training Amount
        train_amount = amount if amount is not None else self._default_amount
        if not isinstance(train_amount, int) or isinstance(train_amount, bool):
            return TrainingResult(
                success=False,
                stat_name=norm_stat,
                previous_value=prev_stat,
                new_value=prev_stat,
                actual_change=0,
                reason=f"Training amount must be an integer, got {type(train_amount).__name__}.",
                pokemon=pokemon,
                previous_trained=prev_trained,
                new_trained=prev_trained,
            )

        if train_amount <= 0:
            return TrainingResult(
                success=False,
                stat_name=norm_stat,
                previous_value=prev_stat,
                new_value=prev_stat,
                actual_change=0,
                reason=f"Training amount must be positive (> 0), got {train_amount}.",
                pokemon=pokemon,
                previous_trained=prev_trained,
                new_trained=prev_trained,
            )

        # 5. Determine Stat Cap
        base_stat = getattr(pokemon.species, f"base_{norm_stat}")
        effective_cap = stat_cap if stat_cap is not None else self.get_stat_cap(norm_stat)
        if self._max_trained_bonus is not None:
            effective_cap = min(effective_cap, base_stat + self._max_trained_bonus)

        # 6. Check if already at or above cap
        if prev_stat >= effective_cap:
            return TrainingResult(
                success=False,
                stat_name=norm_stat,
                previous_value=prev_stat,
                new_value=prev_stat,
                actual_change=0,
                reason=f"Stat '{norm_stat}' is already at or above maximum cap ({effective_cap}).",
                pokemon=pokemon,
                was_clamped=True,
                previous_trained=prev_trained,
                new_trained=prev_trained,
            )

        # 7. Apply training with clamping
        target_stat = prev_stat + train_amount
        if target_stat >= effective_cap:
            new_stat = effective_cap
            actual_change = effective_cap - prev_stat
            was_clamped = True
        else:
            new_stat = target_stat
            actual_change = train_amount
            was_clamped = False

        new_trained = prev_trained + actual_change
        pokemon.set_trained_stat(norm_stat, new_trained)

        return TrainingResult(
            success=True,
            stat_name=norm_stat,
            previous_value=prev_stat,
            new_value=new_stat,
            actual_change=actual_change,
            reason=f"Successfully trained {norm_stat.capitalize()} by +{actual_change} ({prev_stat} -> {new_stat}).",
            pokemon=pokemon,
            was_clamped=was_clamped,
            previous_trained=prev_trained,
            new_trained=new_trained,
        )

    def train(
        self,
        pokemon: Pokemon,
        stat_name: str,
        amount: Optional[int] = None,
        stat_cap: Optional[int] = None,
    ) -> TrainingResult:
        """Alias for train_stat."""
        return self.train_stat(pokemon, stat_name, amount=amount, stat_cap=stat_cap)

    def train_attack(
        self,
        pokemon: Pokemon,
        amount: Optional[int] = None,
        stat_cap: Optional[int] = None,
    ) -> TrainingResult:
        """Trains the Attack stat."""
        return self.train_stat(pokemon, "attack", amount=amount, stat_cap=stat_cap)

    def train_defense(
        self,
        pokemon: Pokemon,
        amount: Optional[int] = None,
        stat_cap: Optional[int] = None,
    ) -> TrainingResult:
        """Trains the Defense stat."""
        return self.train_stat(pokemon, "defense", amount=amount, stat_cap=stat_cap)

    def train_speed(
        self,
        pokemon: Pokemon,
        amount: Optional[int] = None,
        stat_cap: Optional[int] = None,
    ) -> TrainingResult:
        """Trains the Speed stat."""
        return self.train_stat(pokemon, "speed", amount=amount, stat_cap=stat_cap)
