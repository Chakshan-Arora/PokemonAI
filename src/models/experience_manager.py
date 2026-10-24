"""
Experience and battle rewards management service.
Handles calculation and distribution of post-battle XP to victorious Pokemon.
"""
from dataclasses import dataclass
from typing import Optional
from src.models.pokemon import Pokemon
from src.models.battle import Battle
from src.models.battle_state import BattleState
from src.models.progression import apply_experience, LevelUpResult

# Default battle XP reward multiplier (defeated Pokemon's level * 50)
DEFAULT_XP_REWARD_MULTIPLIER: int = 50


def calculate_battle_xp_reward(defeated_level: int, multiplier: int = DEFAULT_XP_REWARD_MULTIPLIER) -> int:
    """
    Calculates the XP reward earned for defeating a Pokemon of the specified level.
    Formula: defeated_level * 50.

    Args:
        defeated_level: Level of the defeated Pokemon.
        multiplier: XP reward multiplier per level (default 50).

    Returns:
        The total XP reward amount.
    """
    if not isinstance(defeated_level, int) or isinstance(defeated_level, bool):
        raise TypeError(f"defeated_level must be an integer, got {type(defeated_level).__name__}.")
    if defeated_level < 1:
        raise ValueError(f"defeated_level must be positive (>= 1), got {defeated_level}.")
    if not isinstance(multiplier, int) or isinstance(multiplier, bool) or multiplier < 1:
        raise ValueError(f"multiplier must be a positive integer, got {multiplier}.")
    return defeated_level * multiplier


@dataclass(frozen=True)
class BattleRewardResult:
    """
    Structured outcome of post-battle reward processing.
    """
    battle: Battle
    winner: Optional[Pokemon]
    loser: Optional[Pokemon]
    recipient: Optional[Pokemon]
    xp_awarded: int
    levels_gained: int
    initial_level: int
    final_level: int
    initial_xp: int
    final_xp: int
    hp_gained: int
    eligible: bool
    reason: str


class ExperienceManager:
    """
    Service responsible for calculating and awarding post-battle experience points.
    Enforces battle outcome validation, prevents duplicate claims, and applies level progression.
    """

    def __init__(self, reward_multiplier: int = DEFAULT_XP_REWARD_MULTIPLIER) -> None:
        if not isinstance(reward_multiplier, int) or isinstance(reward_multiplier, bool) or reward_multiplier < 1:
            raise ValueError(f"reward_multiplier must be a positive integer, got {reward_multiplier}.")
        self._reward_multiplier: int = reward_multiplier
        self._claimed_battle_ids: set[str] = set()

    @property
    def reward_multiplier(self) -> int:
        """XP reward multiplier per defeated level."""
        return self._reward_multiplier

    def calculate_reward_xp(self, battle: Battle) -> int:
        """
        Calculates the XP reward for a battle based on the defeated Pokemon's level.
        Returns 0 if the battle is unfinished, a draw, or has no valid loser.
        """
        if not isinstance(battle, Battle):
            raise TypeError(f"Expected Battle instance, got {type(battle).__name__}.")
        if not battle.state.is_terminal() or battle.state == BattleState.DRAW or battle.loser is None:
            return 0
        return calculate_battle_xp_reward(battle.loser.level, self._reward_multiplier)

    def can_award_rewards(self, battle: Battle) -> bool:
        """
        Determines whether a battle is eligible for victory reward distribution.
        Requires terminal state, a decisive winner and loser, and that rewards have not yet been claimed.
        """
        if not isinstance(battle, Battle):
            raise TypeError(f"Expected Battle instance, got {type(battle).__name__}.")
        if not battle.state.is_terminal():
            return False
        if battle.state == BattleState.DRAW or battle.winner is None or battle.loser is None:
            return False
        if battle.battle_id in self._claimed_battle_ids or battle.rewards_claimed:
            return False
        return True

    def award_battle_rewards(
        self,
        battle: Battle,
        recipient: Optional[Pokemon] = None,
        raise_on_ineligible: bool = False,
    ) -> BattleRewardResult:
        """
        Processes and distributes victory XP for a finished battle.

        Rules:
          - Battle must be finished (terminal state).
          - Battle must have a winner (draws and unfinished battles receive 0 XP).
          - Victory rewards are awarded only to the victorious Pokemon (or a designated eligible winner).
          - Defeated Pokemon cannot receive victory rewards.
          - Duplicate claims for the same battle are strictly rejected.

        Args:
            battle: The Battle instance to reward.
            recipient: The Pokemon to receive the reward (defaults to battle.winner).
            raise_on_ineligible: If True, raises exceptions on invalid/duplicate claims.
                                 If False (default), returns a structured result with eligible=False.

        Returns:
            BattleRewardResult summarizing the reward and progression outcome.
        """
        if not isinstance(battle, Battle):
            raise TypeError(f"Expected Battle instance, got {type(battle).__name__}.")

        # 1. Check if battle is terminal
        if not battle.state.is_terminal():
            msg = f"Cannot award rewards: battle is not finished (current state: '{battle.state.value}')."
            if raise_on_ineligible:
                raise RuntimeError(msg)
            return BattleRewardResult(
                battle=battle, winner=None, loser=None, recipient=recipient,
                xp_awarded=0, levels_gained=0, initial_level=0, final_level=0,
                initial_xp=0, final_xp=0, hp_gained=0, eligible=False, reason=msg,
            )

        # 2. Check for draw
        if battle.state == BattleState.DRAW or battle.winner is None or battle.loser is None:
            msg = "Cannot award victory rewards: battle ended in a draw."
            if raise_on_ineligible:
                raise RuntimeError(msg)
            return BattleRewardResult(
                battle=battle, winner=battle.winner, loser=battle.loser, recipient=recipient,
                xp_awarded=0, levels_gained=0, initial_level=0, final_level=0,
                initial_xp=0, final_xp=0, hp_gained=0, eligible=False, reason=msg,
            )

        # 3. Check for duplicate claims
        if battle.battle_id in self._claimed_battle_ids or battle.rewards_claimed:
            msg = "Cannot award rewards: victory rewards have already been claimed for this battle."
            if raise_on_ineligible:
                raise RuntimeError(msg)
            target = recipient or battle.winner
            rec_lvl = target.level if target else 0
            rec_xp = target.experience if target else 0
            return BattleRewardResult(
                battle=battle, winner=battle.winner, loser=battle.loser, recipient=target,
                xp_awarded=0, levels_gained=0, initial_level=rec_lvl, final_level=rec_lvl,
                initial_xp=rec_xp, final_xp=rec_xp, hp_gained=0, eligible=False, reason=msg,
            )

        # 4. Resolve recipient
        target_pokemon = recipient if recipient is not None else battle.winner
        if not isinstance(target_pokemon, Pokemon):
            raise TypeError(f"recipient must be a Pokemon instance, got {type(target_pokemon).__name__}.")

        # 5. Defeated Pokemon must not receive victory rewards
        if target_pokemon is battle.loser:
            msg = f"Cannot award victory rewards: '{target_pokemon.display_name}' was defeated in this battle."
            if raise_on_ineligible:
                raise ValueError(msg)
            return BattleRewardResult(
                battle=battle, winner=battle.winner, loser=battle.loser, recipient=target_pokemon,
                xp_awarded=0, levels_gained=0, initial_level=target_pokemon.level, final_level=target_pokemon.level,
                initial_xp=target_pokemon.experience, final_xp=target_pokemon.experience, hp_gained=0,
                eligible=False, reason=msg,
            )

        # 6. Recipient must be the battle winner
        if target_pokemon is not battle.winner:
            msg = f"Cannot award rewards: '{target_pokemon.display_name}' is not the winner of this battle."
            if raise_on_ineligible:
                raise ValueError(msg)
            return BattleRewardResult(
                battle=battle, winner=battle.winner, loser=battle.loser, recipient=target_pokemon,
                xp_awarded=0, levels_gained=0, initial_level=target_pokemon.level, final_level=target_pokemon.level,
                initial_xp=target_pokemon.experience, final_xp=target_pokemon.experience, hp_gained=0,
                eligible=False, reason=msg,
            )

        # 7. Calculate and award XP
        xp_reward = self.calculate_reward_xp(battle)

        # Mark battle as claimed before applying XP
        self._claimed_battle_ids.add(battle.battle_id)
        battle.rewards_claimed = True

        progression_result = apply_experience(target_pokemon, xp_reward)

        return BattleRewardResult(
            battle=battle,
            winner=battle.winner,
            loser=battle.loser,
            recipient=target_pokemon,
            xp_awarded=xp_reward,
            levels_gained=progression_result.levels_gained,
            initial_level=progression_result.initial_level,
            final_level=progression_result.final_level,
            initial_xp=progression_result.initial_xp,
            final_xp=progression_result.final_xp,
            hp_gained=progression_result.hp_gained,
            eligible=True,
            reason=f"Awarded {xp_reward} XP to {target_pokemon.display_name}.",
        )
