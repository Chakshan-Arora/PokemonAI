"""
Move manager for Pokemon.
Coordinates move learning, forgetting, replacing, and level-up move progression,
enforcing the 4-move limit and maintaining instance-level isolation.
"""
from dataclasses import dataclass
from typing import Optional, Union, Sequence, Any
from src.models.pokemon import Pokemon, MAX_KNOWN_MOVES
from src.models.attack import Attack
from src.data.move_learning import (
    LevelUpMove,
    get_learnable_moves,
    get_moves_in_level_range,
)

DEFAULT_MAX_MOVES: int = MAX_KNOWN_MOVES


@dataclass(frozen=True)
class MoveLearnResult:
    """
    Structured outcome of an attempt to learn an attack.
    """
    success: bool
    pokemon: Optional[Pokemon]
    attack: Optional[Attack]
    reason: str
    move_limit_reached: bool = False


@dataclass(frozen=True)
class MoveForgetResult:
    """
    Structured outcome of an attempt to forget a known attack.
    """
    success: bool
    pokemon: Optional[Pokemon]
    attack: Optional[Attack]
    reason: str


@dataclass(frozen=True)
class MoveReplaceResult:
    """
    Structured outcome of an attempt to replace an existing attack with a new attack.
    """
    success: bool
    pokemon: Optional[Pokemon]
    old_attack: Optional[Attack]
    new_attack: Optional[Attack]
    reason: str


@dataclass(frozen=True)
class PendingMove:
    """
    Represents an attack offered upon level-up that could not be auto-learned
    because the Pokemon already knows the maximum number of moves.
    """
    pokemon: Pokemon
    attack: Attack
    level: int
    reason: str


@dataclass(frozen=True)
class LevelUpMoveProgressionResult:
    """
    Structured outcome of level-up move progression processing.
    """
    pokemon: Pokemon
    from_level: int
    to_level: int
    learned_moves: tuple[Attack, ...]
    pending_moves: tuple[PendingMove, ...]
    skipped_moves: tuple[Attack, ...]
    reason: str


class MoveManager:
    """
    Manages attack loadouts for individual Pokemon instances.
    Enforces the configurable move limit (default 4 moves), prevents duplicate attacks,
    supports explicit move replacement, and processes level-up learning.
    """

    def __init__(self, max_moves: int = DEFAULT_MAX_MOVES) -> None:
        if not isinstance(max_moves, int) or isinstance(max_moves, bool) or max_moves < 1:
            raise ValueError(f"max_moves must be a positive integer, got {max_moves}.")
        self._max_moves: int = max_moves

    @property
    def max_moves(self) -> int:
        """Configured maximum number of known attacks allowed per Pokemon."""
        return self._max_moves

    def knows_attack(self, pokemon: Pokemon, attack: Union[Attack, str]) -> bool:
        """Checks if a Pokemon knows the specified attack (by Attack instance or name)."""
        if not isinstance(pokemon, Pokemon):
            return False
        return pokemon.knows_attack(attack)

    def get_known_attacks(self, pokemon: Pokemon) -> list[Attack]:
        """Returns a copy of the list of attacks currently known by the Pokemon."""
        if not isinstance(pokemon, Pokemon):
            raise TypeError(f"pokemon must be a Pokemon instance, got {type(pokemon).__name__}.")
        return list(pokemon.attacks)

    def can_learn(self, pokemon: Pokemon, attack: Attack) -> tuple[bool, str]:
        """
        Evaluates whether a Pokemon can currently learn the specified attack.
        Returns a tuple (can_learn, reason).
        """
        if not isinstance(pokemon, Pokemon):
            return False, f"Invalid pokemon: expected Pokemon instance, got {type(pokemon).__name__}."
        if not isinstance(attack, Attack):
            return False, f"Invalid attack: expected Attack instance, got {type(attack).__name__}."
        if pokemon.knows_attack(attack):
            return False, f"{pokemon.display_name} already knows {attack.name}."
        if len(pokemon.attacks) >= self._max_moves:
            return False, f"Move limit reached: {pokemon.display_name} already knows {self._max_moves} attacks."
        return True, f"{pokemon.display_name} is eligible to learn {attack.name}."

    def learn_attack(self, pokemon: Pokemon, attack: Attack) -> MoveLearnResult:
        """
        Attempts to teach a new attack to a Pokemon.

        Rules:
          - Pokemon must be a valid Pokemon instance.
          - Attack must be a valid Attack instance.
          - Duplicate moves are rejected.
          - If the Pokemon already knows max_moves (default 4), learning is rejected
            with move_limit_reached=True without replacing any move.
        """
        if not isinstance(pokemon, Pokemon):
            return MoveLearnResult(
                success=False,
                pokemon=None,
                attack=attack if isinstance(attack, Attack) else None,
                reason=f"Invalid pokemon: expected Pokemon instance, got {type(pokemon).__name__}.",
            )

        if not isinstance(attack, Attack):
            return MoveLearnResult(
                success=False,
                pokemon=pokemon,
                attack=None,
                reason=f"Invalid attack: expected Attack instance, got {type(attack).__name__}.",
            )

        # Check duplicate
        if pokemon.knows_attack(attack):
            return MoveLearnResult(
                success=False,
                pokemon=pokemon,
                attack=attack,
                reason=f"{pokemon.display_name} already knows {attack.name}.",
            )

        # Check move limit
        if len(pokemon.attacks) >= self._max_moves:
            return MoveLearnResult(
                success=False,
                pokemon=pokemon,
                attack=attack,
                reason=(
                    f"Cannot learn {attack.name}: {pokemon.display_name} has reached the move limit "
                    f"of {self._max_moves} attacks. An existing move must be forgotten or replaced."
                ),
                move_limit_reached=True,
            )

        # Assign attack
        pokemon.assign_attack(attack)
        return MoveLearnResult(
            success=True,
            pokemon=pokemon,
            attack=attack,
            reason=f"{pokemon.display_name} successfully learned {attack.name}!",
        )

    def forget_attack(self, pokemon: Pokemon, attack: Union[Attack, str]) -> MoveForgetResult:
        """
        Removes an attack that the Pokemon currently knows.

        Rules:
          - Pokemon must be a valid Pokemon instance.
          - If the Pokemon does not know the attack, the operation is rejected.
        """
        if not isinstance(pokemon, Pokemon):
            return MoveForgetResult(
                success=False,
                pokemon=None,
                attack=attack if isinstance(attack, Attack) else None,
                reason=f"Invalid pokemon: expected Pokemon instance, got {type(pokemon).__name__}.",
            )

        target_attack: Optional[Attack] = (
            attack if isinstance(attack, Attack)
            else pokemon.get_attack_by_name(attack) if isinstance(attack, str)
            else None
        )

        name_str = attack.name if isinstance(attack, Attack) else str(attack)

        if not target_attack or not pokemon.knows_attack(target_attack):
            return MoveForgetResult(
                success=False,
                pokemon=pokemon,
                attack=target_attack,
                reason=f"{pokemon.display_name} does not know the attack '{name_str}'.",
            )

        pokemon.forget_attack(target_attack)
        return MoveForgetResult(
            success=True,
            pokemon=pokemon,
            attack=target_attack,
            reason=f"{pokemon.display_name} forgot {target_attack.name}.",
        )

    def replace_attack(
        self,
        pokemon: Pokemon,
        old_attack: Union[Attack, str],
        new_attack: Attack,
    ) -> MoveReplaceResult:
        """
        Replaces an existing known attack with a new attack.

        Rules:
          - Validates both attacks.
          - old_attack must be currently known by the Pokemon.
          - new_attack must be a valid Attack and not already known.
          - If replacement fails, the original loadout is left completely unchanged.
        """
        if not isinstance(pokemon, Pokemon):
            return MoveReplaceResult(
                success=False,
                pokemon=None,
                old_attack=old_attack if isinstance(old_attack, Attack) else None,
                new_attack=new_attack if isinstance(new_attack, Attack) else None,
                reason=f"Invalid pokemon: expected Pokemon instance, got {type(pokemon).__name__}.",
            )

        if not isinstance(new_attack, Attack):
            return MoveReplaceResult(
                success=False,
                pokemon=pokemon,
                old_attack=old_attack if isinstance(old_attack, Attack) else None,
                new_attack=None,
                reason=f"Invalid new_attack: expected Attack instance, got {type(new_attack).__name__}.",
            )

        target_old: Optional[Attack] = (
            old_attack if isinstance(old_attack, Attack)
            else pokemon.get_attack_by_name(old_attack) if isinstance(old_attack, str)
            else None
        )

        old_name_str = old_attack.name if isinstance(old_attack, Attack) else str(old_attack)

        # Check old attack is known
        if not target_old or not pokemon.knows_attack(target_old):
            return MoveReplaceResult(
                success=False,
                pokemon=pokemon,
                old_attack=target_old,
                new_attack=new_attack,
                reason=f"Cannot replace: {pokemon.display_name} does not know '{old_name_str}'.",
            )

        # Check new attack is not already known
        if pokemon.knows_attack(new_attack):
            return MoveReplaceResult(
                success=False,
                pokemon=pokemon,
                old_attack=target_old,
                new_attack=new_attack,
                reason=f"Cannot replace: {pokemon.display_name} already knows {new_attack.name}.",
            )

        # Perform atomic replacement
        success = pokemon.replace_attack(target_old, new_attack)
        if success:
            return MoveReplaceResult(
                success=True,
                pokemon=pokemon,
                old_attack=target_old,
                new_attack=new_attack,
                reason=f"{pokemon.display_name} forgot {target_old.name} and learned {new_attack.name}!",
            )
        else:
            return MoveReplaceResult(
                success=False,
                pokemon=pokemon,
                old_attack=target_old,
                new_attack=new_attack,
                reason="Replacement failed unexpectedly. Original loadout preserved.",
            )

    def process_level_up_moves(
        self,
        pokemon: Pokemon,
        from_level: int,
        to_level: int,
        auto_learn: bool = True,
    ) -> LevelUpMoveProgressionResult:
        """
        Evaluates and applies move learning across a level-up progression range (from_level < level <= to_level).

        Rules:
          - Moves are processed in strictly ascending level order.
          - Moves already awarded to this Pokemon instance for that level are not awarded repeatedly.
          - Duplicate moves already known are skipped.
          - If the Pokemon has fewer than max_moves, new moves are automatically learned.
          - If the Pokemon already knows max_moves, new moves are flagged as pending / requiring replacement.
            Original loadout is never automatically overwritten.
        """
        if not isinstance(pokemon, Pokemon):
            raise TypeError(f"pokemon must be a Pokemon instance, got {type(pokemon).__name__}.")
        if not isinstance(from_level, int) or isinstance(from_level, bool):
            raise TypeError(f"from_level must be an integer, got {type(from_level).__name__}.")
        if not isinstance(to_level, int) or isinstance(to_level, bool):
            raise TypeError(f"to_level must be an integer, got {type(to_level).__name__}.")

        if to_level <= from_level:
            return LevelUpMoveProgressionResult(
                pokemon=pokemon,
                from_level=from_level,
                to_level=to_level,
                learned_moves=(),
                pending_moves=(),
                skipped_moves=(),
                reason="No level advancement (to_level <= from_level).",
            )

        eligible_moves = get_moves_in_level_range(
            species=pokemon.species,
            start_level=from_level,
            end_level=to_level,
            inclusive_start=False,
        )

        learned_list: list[Attack] = []
        pending_list: list[PendingMove] = []
        skipped_list: list[Attack] = []

        for entry in eligible_moves:
            lvl = entry.level
            atk = entry.attack

            # Guard against duplicate awards for the same level threshold
            if pokemon.is_level_move_awarded(lvl, atk.name):
                continue

            # Mark this level threshold move as processed for this instance
            pokemon.mark_level_move_awarded(lvl, atk.name)

            # If already known, record as skipped
            if pokemon.knows_attack(atk):
                skipped_list.append(atk)
                continue

            # Check if there is capacity to learn
            if len(pokemon.attacks) < self._max_moves and auto_learn:
                learn_res = self.learn_attack(pokemon, atk)
                if learn_res.success:
                    learned_list.append(atk)
                else:
                    pending_list.append(PendingMove(
                        pokemon=pokemon,
                        attack=atk,
                        level=lvl,
                        reason=learn_res.reason,
                    ))
            else:
                # Capacity reached: flag as pending
                pending_list.append(PendingMove(
                    pokemon=pokemon,
                    attack=atk,
                    level=lvl,
                    reason=(
                        f"{pokemon.display_name} is eligible to learn {atk.name} at Lv.{lvl}, "
                        f"but already knows {len(pokemon.attacks)}/{self._max_moves} attacks. "
                        f"An explicit move replacement decision is required."
                    ),
                ))

        learned_tuple = tuple(learned_list)
        pending_tuple = tuple(pending_list)
        skipped_tuple = tuple(skipped_list)

        msg_parts: list[str] = []
        if learned_tuple:
            msg_parts.append(f"Learned: {', '.join(a.name for a in learned_tuple)}")
        if pending_tuple:
            msg_parts.append(f"Pending replacement: {', '.join(p.attack.name for p in pending_tuple)}")
        if skipped_tuple:
            msg_parts.append(f"Already known: {', '.join(a.name for a in skipped_tuple)}")
        summary = " | ".join(msg_parts) if msg_parts else "No new moves learned."

        return LevelUpMoveProgressionResult(
            pokemon=pokemon,
            from_level=from_level,
            to_level=to_level,
            learned_moves=learned_tuple,
            pending_moves=pending_tuple,
            skipped_moves=skipped_tuple,
            reason=summary,
        )

    def check_level_up_moves(
        self,
        pokemon_or_result: Any,
        from_level: Optional[int] = None,
        to_level: Optional[int] = None,
    ) -> LevelUpMoveProgressionResult:
        """
        Convenience coordinator accepting either a LevelUpResult or a Pokemon with level bounds.
        """
        if hasattr(pokemon_or_result, "pokemon") and hasattr(pokemon_or_result, "initial_level"):
            pokemon = pokemon_or_result.pokemon
            start_lvl = pokemon_or_result.initial_level
            end_lvl = pokemon_or_result.final_level
        else:
            pokemon = pokemon_or_result
            start_lvl = from_level if from_level is not None else 1
            end_lvl = to_level if to_level is not None else getattr(pokemon, "level", 1)

        return self.process_level_up_moves(pokemon, start_lvl, end_lvl)
