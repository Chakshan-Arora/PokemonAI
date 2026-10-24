"""
Obedience manager for Pokemon.
Evaluates command compliance based on obedience (primary factor) and bond (secondary factor),
supporting deterministic probability calculation and roll evaluations.
"""
import random
from dataclasses import dataclass, field
from typing import Optional, Union, Any
from src.models.pokemon import Pokemon, MIN_OBEDIENCE, MAX_OBEDIENCE, MIN_BOND, MAX_BOND

# Probability formula constants
BASE_OBEDIENCE_PROBABILITY: float = 0.70
OBEDIENCE_WEIGHT: float = 0.25
BOND_WEIGHT: float = 0.05
LOYALTY_WEIGHT: float = 0.05
FEAR_WEIGHT: float = 0.03
MIN_OBEDIENCE_PROBABILITY: float = 0.05
MAX_OBEDIENCE_PROBABILITY: float = 1.00


@dataclass(frozen=True)
class CommandContext:
    """
    Context for a trainer command issued to a Pokemon.
    Allows specifying command type, optional target, and optional difficulty modifier.
    """
    command: str = "attack"
    target: Optional[Any] = None
    difficulty_modifier: float = 0.0
    metadata: Optional[dict[str, Any]] = None


@dataclass(frozen=True)
class ObedienceResult:
    """
    Structured outcome of an obedience evaluation.
    """
    is_obeyed: bool
    obedience: int
    bond: int
    probability: float
    reason: str
    pokemon: Optional[Pokemon] = None
    command: str = ""
    roll: Optional[float] = None


def calculate_obedience_probability(
    pokemon: Pokemon,
    context: Optional[Union[CommandContext, str]] = None,
    base_prob: float = BASE_OBEDIENCE_PROBABILITY,
    obedience_weight: float = OBEDIENCE_WEIGHT,
    bond_weight: float = BOND_WEIGHT,
    loyalty_weight: float = LOYALTY_WEIGHT,
    fear_weight: float = FEAR_WEIGHT,
    min_prob: float = MIN_OBEDIENCE_PROBABILITY,
    max_prob: float = MAX_OBEDIENCE_PROBABILITY,
) -> float:
    """
    Calculates the probability that a Pokemon obeys a command.

    Formula:
      obedience_term = (clamped_obedience / 100) * obedience_weight
      bond_term      = (clamped_bond / 100) * bond_weight
      loyalty_term   = ((loyalty - 50) / 100) * loyalty_weight
      fear_term      = ((50 - fear) / 100) * fear_weight
      raw_prob       = base_prob + obedience_term + bond_term + loyalty_term + fear_term - difficulty
      clamped        = clamp(raw_prob, min_prob, max_prob)

    With default constants:
      raw_prob = 0.70 + (obedience / 100) * 0.25 + (bond / 100) * 0.05 + ((loyalty - 50)/100)*0.05 + ((50 - fear)/100)*0.03
      clamped  = clamp(raw_prob, 0.05, 1.00)

    Args:
        pokemon: The Pokemon being commanded.
        context: Optional CommandContext or command name string.
        base_prob: Base obedience probability floor (default 0.70).
        obedience_weight: Influence multiplier for obedience (default 0.25).
        bond_weight: Influence multiplier for bond (default 0.05).
        loyalty_weight: Influence multiplier for loyalty trait deviation from 50 (default 0.05).
        fear_weight: Influence multiplier for fear trait deviation from 50 (default 0.03).
        min_prob: Minimum allowed probability (default 0.05).
        max_prob: Maximum allowed probability (default 1.00).

    Returns:
        A float probability clamped to [min_prob, max_prob].
    """
    if not isinstance(pokemon, Pokemon):
        raise TypeError(f"pokemon must be a Pokemon instance, got {type(pokemon).__name__}.")

    diff_modifier = 0.0
    if isinstance(context, CommandContext):
        diff_modifier = float(context.difficulty_modifier)

    # Clamp stat values safely to valid bounds
    clamped_obedience = max(MIN_OBEDIENCE, min(MAX_OBEDIENCE, float(pokemon.obedience)))
    clamped_bond = max(MIN_BOND, min(MAX_BOND, float(pokemon.bond)))

    obedience_term = (clamped_obedience / 100.0) * obedience_weight
    bond_term = (clamped_bond / 100.0) * bond_weight

    loyalty_term = 0.0
    fear_term = 0.0
    personality = getattr(pokemon, "personality", None)
    if personality is not None:
        clamped_loyalty = max(0.0, min(100.0, float(getattr(personality, "loyalty", 50.0))))
        clamped_fear = max(0.0, min(100.0, float(getattr(personality, "fear", 50.0))))
        loyalty_term = ((clamped_loyalty - 50.0) / 100.0) * loyalty_weight
        fear_term = ((50.0 - clamped_fear) / 100.0) * fear_weight

    raw_probability = base_prob + obedience_term + bond_term + loyalty_term + fear_term - diff_modifier
    return max(min_prob, min(max_prob, raw_probability))


class ObedienceManager:
    """
    Service responsible for evaluating whether a Pokemon follows trainer commands.
    Keeps probability calculation separate from rolls and supports deterministic RNG injection.
    """

    def __init__(
        self,
        rng: Optional[random.Random] = None,
        seed: Optional[int] = None,
        base_prob: float = BASE_OBEDIENCE_PROBABILITY,
        obedience_weight: float = OBEDIENCE_WEIGHT,
        bond_weight: float = BOND_WEIGHT,
        loyalty_weight: float = LOYALTY_WEIGHT,
        fear_weight: float = FEAR_WEIGHT,
        min_prob: float = MIN_OBEDIENCE_PROBABILITY,
        max_prob: float = MAX_OBEDIENCE_PROBABILITY,
    ) -> None:
        if rng is not None:
            self._rng = rng
        elif seed is not None:
            self._rng = random.Random(seed)
        else:
            self._rng = random.Random()

        self._base_prob = base_prob
        self._obedience_weight = obedience_weight
        self._bond_weight = bond_weight
        self._loyalty_weight = loyalty_weight
        self._fear_weight = fear_weight
        self._min_prob = min_prob
        self._max_prob = max_prob

    def calculate_probability(
        self,
        pokemon: Pokemon,
        context: Optional[Union[CommandContext, str]] = None,
    ) -> float:
        """
        Calculates obedience probability using this manager's configured parameters.
        Does not mutate the Pokemon or advance RNG.
        """
        return calculate_obedience_probability(
            pokemon,
            context=context,
            base_prob=self._base_prob,
            obedience_weight=self._obedience_weight,
            bond_weight=self._bond_weight,
            loyalty_weight=self._loyalty_weight,
            fear_weight=self._fear_weight,
            min_prob=self._min_prob,
            max_prob=self._max_prob,
        )

    def evaluate_obedience(
        self,
        pokemon: Pokemon,
        context: Optional[Union[CommandContext, str]] = None,
        rng: Optional[random.Random] = None,
    ) -> ObedienceResult:
        """
        Evaluates whether a Pokemon follows a command.

        Validation rules:
          - Pokemon must be a valid Pokemon instance.
          - Fainted Pokemon cannot obey commands (probability=0.0, is_obeyed=False).
          - Does not mutate Pokemon state (bond, obedience, HP, etc. remain unchanged).

        Evaluation:
          - Probability is computed via calculate_probability.
          - A random float is rolled in [0.0, 1.0).
          - If roll <= probability, command is obeyed; otherwise disobeyed.
        """
        resolved_context = (
            CommandContext(command=context) if isinstance(context, str)
            else (context if isinstance(context, CommandContext) else CommandContext())
        )
        cmd_name = resolved_context.command or "command"

        # 1. Validate Pokemon instance
        if not isinstance(pokemon, Pokemon):
            return ObedienceResult(
                is_obeyed=False,
                obedience=0,
                bond=0,
                probability=0.0,
                reason=f"Invalid Pokemon: expected Pokemon instance, got {type(pokemon).__name__}.",
                pokemon=None,
                command=cmd_name,
                roll=None,
            )

        # 2. Check fainted status
        if pokemon.is_fainted or pokemon.current_hp <= 0:
            return ObedienceResult(
                is_obeyed=False,
                obedience=pokemon.obedience,
                bond=pokemon.bond,
                probability=0.0,
                reason=f"{pokemon.display_name} is fainted and cannot obey '{cmd_name}'.",
                pokemon=pokemon,
                command=cmd_name,
                roll=None,
            )

        # 3. Calculate probability
        prob = self.calculate_probability(pokemon, context=resolved_context)

        # 4. Perform deterministic roll
        effective_rng = rng if rng is not None else self._rng
        roll = effective_rng.random()
        obeyed = roll <= prob

        # 5. Build reason description
        if obeyed:
            reason = f"{pokemon.display_name} happily obeyed the command '{cmd_name}'."
        else:
            reason = f"{pokemon.display_name} ignored the command '{cmd_name}'."

        return ObedienceResult(
            is_obeyed=obeyed,
            obedience=pokemon.obedience,
            bond=pokemon.bond,
            probability=prob,
            reason=reason,
            pokemon=pokemon,
            command=cmd_name,
            roll=roll,
        )
