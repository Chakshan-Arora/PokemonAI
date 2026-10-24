"""
Bond manager for Pokemon.
Handles modifying, evaluating, and rewarding a Pokemon's bond with its trainer,
enforcing stat boundaries (0-100) and preventing duplicate event rewards.
"""
from dataclasses import dataclass
from typing import Optional, Union, Any
from src.models.pokemon import Pokemon, MIN_BOND, MAX_BOND
from src.models.battle import Battle
from src.models.battle_state import BattleState

# Default bond reward amounts for game events
DEFAULT_BOND_BATTLE_VICTORY: int = 5
DEFAULT_BOND_BATTLE_DEFEAT: int = 8
DEFAULT_BOND_LEVEL_UP: int = 3
DEFAULT_BOND_CAPTURE: int = 5


@dataclass(frozen=True)
class BondEventConfig:
    """
    Configuration specifying bond rewards for distinct game events.
    """
    battle_victory: int = DEFAULT_BOND_BATTLE_VICTORY
    battle_defeat: int = DEFAULT_BOND_BATTLE_DEFEAT
    level_up: int = DEFAULT_BOND_LEVEL_UP
    capture: int = DEFAULT_BOND_CAPTURE


@dataclass(frozen=True)
class BondChangeResult:
    """
    Structured outcome of a bond modification or event reward attempt.
    """
    pokemon: Optional[Pokemon]
    previous_bond: int
    new_bond: int
    change_amount: int
    was_clamped: bool
    success: bool = True
    event_id: Optional[str] = None
    reason: str = ""


class BondManager:
    """
    Manages bonding progression between Pokemon and trainers.
    Enforces the [0, 100] bond range, prevents duplicate claims for events
    (such as battle victories, level-ups, and captures), and ensures isolation across Pokemon instances.
    """

    def __init__(self, config: Optional[BondEventConfig] = None) -> None:
        self._config: BondEventConfig = config if config is not None else BondEventConfig()
        self._claimed_event_ids: set[str] = set()

    @property
    def config(self) -> BondEventConfig:
        """Configured bond reward values."""
        return self._config

    @property
    def claimed_event_ids(self) -> frozenset[str]:
        """Read-only view of claimed event identifiers."""
        return frozenset(self._claimed_event_ids)

    def has_event_been_claimed(self, event_id: str) -> bool:
        """Checks if a specific event identifier has already been awarded bond."""
        if not event_id or not isinstance(event_id, str):
            return False
        return event_id in self._claimed_event_ids

    def change_bond(
        self,
        pokemon: Pokemon,
        delta: int,
        event_id: Optional[str] = None,
        reason: str = "",
    ) -> BondChangeResult:
        """
        Modifies a Pokemon's bond by an integer delta (positive, negative, or zero).
        Clamps the resulting bond to [MIN_BOND, MAX_BOND] (0 to 100).
        """
        if not isinstance(pokemon, Pokemon):
            raise TypeError(f"pokemon must be a Pokemon instance, got {type(pokemon).__name__}.")
        if not isinstance(delta, int) or isinstance(delta, bool):
            raise TypeError(f"delta must be an integer, got {type(delta).__name__}.")

        prev_bond = pokemon.bond

        if delta == 0:
            return BondChangeResult(
                pokemon=pokemon,
                previous_bond=prev_bond,
                new_bond=prev_bond,
                change_amount=0,
                was_clamped=False,
                success=True,
                event_id=event_id,
                reason=reason or "No bond change applied (delta is 0).",
            )

        raw_target = prev_bond + delta
        clamped_bond = max(MIN_BOND, min(MAX_BOND, raw_target))
        was_clamped = (raw_target < MIN_BOND) or (raw_target > MAX_BOND)
        actual_change = clamped_bond - prev_bond

        # Apply mutation strictly to target instance
        pokemon.bond = clamped_bond

        default_reason = f"Bond changed by {actual_change:+d} ({prev_bond} -> {clamped_bond})."
        return BondChangeResult(
            pokemon=pokemon,
            previous_bond=prev_bond,
            new_bond=clamped_bond,
            change_amount=actual_change,
            was_clamped=was_clamped,
            success=True,
            event_id=event_id,
            reason=reason or default_reason,
        )

    def increase_bond(
        self,
        pokemon: Pokemon,
        amount: int,
        event_id: Optional[str] = None,
        reason: str = "",
    ) -> BondChangeResult:
        """
        Increases a Pokemon's bond by a non-negative integer amount.
        Clamps maximum bond at 100.
        """
        if not isinstance(amount, int) or isinstance(amount, bool):
            raise TypeError(f"amount must be an integer, got {type(amount).__name__}.")
        if amount < 0:
            raise ValueError(f"amount cannot be negative, got {amount}. Use decrease_bond to reduce bond.")
        return self.change_bond(pokemon, amount, event_id=event_id, reason=reason)

    def decrease_bond(
        self,
        pokemon: Pokemon,
        amount: int,
        event_id: Optional[str] = None,
        reason: str = "",
    ) -> BondChangeResult:
        """
        Decreases a Pokemon's bond by a non-negative integer amount.
        Clamps minimum bond at 0.
        """
        if not isinstance(amount, int) or isinstance(amount, bool):
            raise TypeError(f"amount must be an integer, got {type(amount).__name__}.")
        if amount < 0:
            raise ValueError(f"amount cannot be negative, got {amount}. Use increase_bond to add bond.")
        return self.change_bond(pokemon, -amount, event_id=event_id, reason=reason)

    def award_event_bond(
        self,
        pokemon: Pokemon,
        event_name: str,
        event_id: str,
        amount: Optional[int] = None,
    ) -> BondChangeResult:
        """
        Awards bond for an arbitrary unique event identifier.
        Rejects duplicate claims for the same event identifier cleanly without modifying bond.
        """
        if not isinstance(pokemon, Pokemon):
            raise TypeError(f"pokemon must be a Pokemon instance, got {type(pokemon).__name__}.")
        if not isinstance(event_id, str) or not event_id.strip():
            raise ValueError("event_id must be a non-empty string.")

        clean_event_id = event_id.strip()

        if clean_event_id in self._claimed_event_ids:
            return BondChangeResult(
                pokemon=pokemon,
                previous_bond=pokemon.bond,
                new_bond=pokemon.bond,
                change_amount=0,
                was_clamped=False,
                success=False,
                event_id=clean_event_id,
                reason=f"Event '{clean_event_id}' ({event_name}) has already been claimed.",
            )

        gain = amount if amount is not None else 5
        self._claimed_event_ids.add(clean_event_id)
        return self.increase_bond(
            pokemon,
            gain,
            event_id=clean_event_id,
            reason=f"Awarded +{gain} bond for event '{event_name}'.",
        )

    def award_battle_victory_bond(
        self,
        battle: Battle,
        recipient: Optional[Pokemon] = None,
        amount: Optional[int] = None,
    ) -> BondChangeResult:
        """
        Awards bond to the victorious Pokemon in a battle.

        Rules:
          - Battle must be finished (terminal state).
          - Draws and unfinished battles are rejected.
          - Defeated Pokemon cannot receive victory bond.
          - Only the winning Pokemon (or designated eligible recipient) receives bond.
          - Duplicate claims for the same battle are strictly rejected via battle_id
            and battle.bond_rewards_claimed.
        """
        if not isinstance(battle, Battle):
            raise TypeError(f"Expected Battle instance, got {type(battle).__name__}.")

        target_pokemon = recipient if recipient is not None else battle.winner
        rec_bond = target_pokemon.bond if isinstance(target_pokemon, Pokemon) else 0

        # 1. Check if battle is terminal
        if not battle.state.is_terminal():
            return BondChangeResult(
                pokemon=target_pokemon,
                previous_bond=rec_bond,
                new_bond=rec_bond,
                change_amount=0,
                was_clamped=False,
                success=False,
                event_id=battle.battle_id,
                reason=f"Cannot award bond: battle is not finished (current state: '{battle.state.value}').",
            )

        # 2. Check for draw or missing winner
        if battle.state == BattleState.DRAW or battle.winner is None or battle.loser is None:
            return BondChangeResult(
                pokemon=target_pokemon,
                previous_bond=rec_bond,
                new_bond=rec_bond,
                change_amount=0,
                was_clamped=False,
                success=False,
                event_id=battle.battle_id,
                reason="Cannot award victory bond: battle ended in a draw.",
            )

        # 3. Check for duplicate claims
        battle_event_key = f"battle:{battle.battle_id}"
        if battle.bond_rewards_claimed or battle.battle_id in self._claimed_event_ids or battle_event_key in self._claimed_event_ids:
            return BondChangeResult(
                pokemon=target_pokemon,
                previous_bond=rec_bond,
                new_bond=rec_bond,
                change_amount=0,
                was_clamped=False,
                success=False,
                event_id=battle.battle_id,
                reason="Cannot award bond: victory bond rewards have already been claimed for this battle.",
            )

        # 4. Validate recipient
        if not isinstance(target_pokemon, Pokemon):
            raise TypeError(f"recipient must be a Pokemon instance, got {type(target_pokemon).__name__}.")

        if target_pokemon is battle.loser:
            return BondChangeResult(
                pokemon=target_pokemon,
                previous_bond=rec_bond,
                new_bond=rec_bond,
                change_amount=0,
                was_clamped=False,
                success=False,
                event_id=battle.battle_id,
                reason=f"Cannot award victory bond: '{target_pokemon.display_name}' was defeated in this battle.",
            )

        if target_pokemon is not battle.winner:
            return BondChangeResult(
                pokemon=target_pokemon,
                previous_bond=rec_bond,
                new_bond=rec_bond,
                change_amount=0,
                was_clamped=False,
                success=False,
                event_id=battle.battle_id,
                reason=f"Cannot award bond: '{target_pokemon.display_name}' is not the winner of this battle.",
            )

        # 5. Mark as claimed and apply reward
        gain = amount if amount is not None else self._config.battle_victory
        self._claimed_event_ids.add(battle.battle_id)
        self._claimed_event_ids.add(battle_event_key)
        battle.bond_rewards_claimed = True

        return self.increase_bond(
            target_pokemon,
            gain,
            event_id=battle.battle_id,
            reason=f"Awarded +{gain} victory bond for winning battle {battle.battle_id[:8]}.",
        )

    def award_battle_defeat_bond(
        self,
        battle: Battle,
        recipient: Pokemon,
        amount: Optional[int] = None,
    ) -> BondChangeResult:
        """
        Awards bond to a Pokemon that fought in a lost battle.
        The shared hardship of defeat strengthens bonds between trainer and Pokemon.

        Rules:
          - Battle must be in DEFEAT state (or recipient's team has all fainted).
          - Recipient must be a Pokemon instance.
          - Duplicate claims for the same battle and recipient Pokemon are rejected.
        """
        if not isinstance(battle, Battle):
            raise TypeError(f"Expected Battle instance, got {type(battle).__name__}.")
        if not isinstance(recipient, Pokemon):
            raise TypeError(f"recipient must be a Pokemon instance, got {type(recipient).__name__}.")

        rec_bond = recipient.bond

        # 1. State check: battle in DEFEAT state or recipient's team all fainted
        is_defeat = (battle.state == BattleState.DEFEAT)
        if not is_defeat and getattr(battle, "player_team", None):
            is_defeat = all(p.is_fainted for p in battle.player_team)
        if not is_defeat and hasattr(battle, "opponent_team") and battle.opponent_team:
            if recipient in battle.opponent_team and all(p.is_fainted for p in battle.opponent_team):
                is_defeat = True

        if not is_defeat:
            return BondChangeResult(
                pokemon=recipient,
                previous_bond=rec_bond,
                new_bond=rec_bond,
                change_amount=0,
                was_clamped=False,
                success=False,
                event_id=battle.battle_id,
                reason=f"Cannot award defeat bond: battle is not in DEFEAT state (current state: '{battle.state.value}').",
            )

        # 2. Duplicate claim check: event ID: f"battle_defeat:{battle.battle_id}:{recipient.unique_id}"
        event_id = f"battle_defeat:{battle.battle_id}:{recipient.unique_id}"
        if event_id in self._claimed_event_ids:
            return BondChangeResult(
                pokemon=recipient,
                previous_bond=rec_bond,
                new_bond=rec_bond,
                change_amount=0,
                was_clamped=False,
                success=False,
                event_id=event_id,
                reason=f"Cannot award bond: defeat bond for Pokemon '{recipient.display_name}' has already been claimed for this battle.",
            )

        # 3. Apply reward
        gain = amount if amount is not None else self._config.battle_defeat
        self._claimed_event_ids.add(event_id)

        return self.increase_bond(
            recipient,
            gain,
            event_id=event_id,
            reason=f"Awarded +{gain} defeat hardship bond for battle {battle.battle_id[:8]}.",
        )

    def award_level_up_bond(
        self,
        pokemon_or_result: Any,
        event_id: Optional[str] = None,
        levels_gained: int = 1,
        amount: Optional[int] = None,
    ) -> BondChangeResult:
        """
        Awards bond when a Pokemon levels up.
        Accepts either a Pokemon instance or a LevelUpResult from the progression system.
        """
        if hasattr(pokemon_or_result, "pokemon") and hasattr(pokemon_or_result, "levels_gained"):
            pokemon = pokemon_or_result.pokemon
            effective_levels = pokemon_or_result.levels_gained
            auto_id = f"levelup:{pokemon.unique_id}:{getattr(pokemon_or_result, 'final_level', pokemon.level)}"
        else:
            pokemon = pokemon_or_result
            effective_levels = levels_gained
            auto_id = f"levelup:{pokemon.unique_id}:{pokemon.level}" if isinstance(pokemon, Pokemon) else None

        if not isinstance(pokemon, Pokemon):
            raise TypeError(f"Expected Pokemon or LevelUpResult, got {type(pokemon_or_result).__name__}.")

        effective_event_id = event_id if event_id is not None else auto_id

        if effective_event_id and effective_event_id in self._claimed_event_ids:
            return BondChangeResult(
                pokemon=pokemon,
                previous_bond=pokemon.bond,
                new_bond=pokemon.bond,
                change_amount=0,
                was_clamped=False,
                success=False,
                event_id=effective_event_id,
                reason=f"Level-up bond reward for event '{effective_event_id}' has already been claimed.",
            )

        gain = amount if amount is not None else (self._config.level_up * max(1, effective_levels))
        if effective_event_id:
            self._claimed_event_ids.add(effective_event_id)

        return self.increase_bond(
            pokemon,
            gain,
            event_id=effective_event_id,
            reason=f"Awarded +{gain} bond for leveling up ({effective_levels} level(s)).",
        )

    def award_capture_bond(
        self,
        pokemon_or_result: Any,
        event_id: Optional[str] = None,
        amount: Optional[int] = None,
    ) -> BondChangeResult:
        """
        Awards bond when a wild Pokemon is captured or joins the trainer's collection.
        Accepts either a Pokemon instance or a CaptureResult from the capture manager.
        """
        if hasattr(pokemon_or_result, "pokemon"):
            pokemon = pokemon_or_result.pokemon
        else:
            pokemon = pokemon_or_result

        if not isinstance(pokemon, Pokemon):
            raise TypeError(f"Expected Pokemon or CaptureResult, got {type(pokemon_or_result).__name__}.")

        auto_id = f"capture:{pokemon.unique_id}"
        effective_event_id = event_id if event_id is not None else auto_id

        if effective_event_id and effective_event_id in self._claimed_event_ids:
            return BondChangeResult(
                pokemon=pokemon,
                previous_bond=pokemon.bond,
                new_bond=pokemon.bond,
                change_amount=0,
                was_clamped=False,
                success=False,
                event_id=effective_event_id,
                reason=f"Capture bond reward for event '{effective_event_id}' has already been claimed.",
            )

        gain = amount if amount is not None else self._config.capture
        if effective_event_id:
            self._claimed_event_ids.add(effective_event_id)

        return self.increase_bond(
            pokemon,
            gain,
            event_id=effective_event_id,
            reason=f"Awarded +{gain} bond upon joining trainer's collection.",
        )
