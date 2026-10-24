"""
Tactical AI decision model for dynamic trainer battles.
Evaluates battle state, type matchups, damage projections, status infliction,
and tactical switching across configurable difficulty profiles (EASY, NORMAL, HARD, BOSS).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
import random
from typing import Any, Optional, Sequence, Union

from src.models.pokemon import Pokemon
from src.models.attack import Attack
from src.models.trainer import Trainer, DifficultyProfile, TrainerArchetype
from src.models.pokemon_type import PokemonType
from src.data.type_chart import (
    get_effectiveness_against_pokemon,
    get_effectiveness_against_types,
)


class TrainerActionType(str, Enum):
    """Action categories an AI trainer can execute on their turn."""
    ATTACK = "ATTACK"
    SWITCH = "SWITCH"
    ITEM = "ITEM"


@dataclass(frozen=True)
class TrainerDecision:
    """
    Structured outcome of an AI trainer's tactical deliberation.
    """
    action_type: TrainerActionType
    chosen_attack: Optional[Attack] = None
    target_pokemon: Optional[Pokemon] = None
    chosen_item: Optional[str] = None
    reason: str = ""
    confidence: float = 1.0
    score: float = 0.0
    factors: dict[str, Any] = field(default_factory=dict)


class TrainerAIDecisionModel:
    """
    Tactical decision engine driving opponent trainer turns.
    Evaluates actions without reading hidden random rolls or cheating,
    acting purely through authoritative battle state and game rules.
    """

    def __init__(
        self,
        rng: Optional[random.Random] = None,
        seed: Optional[int] = None,
    ) -> None:
        if rng is not None:
            self._rng = rng
        elif seed is not None:
            self._rng = random.Random(seed)
        else:
            self._rng = random.Random()

    # --- Matchup & Effectiveness Evaluation ---

    @staticmethod
    def calculate_matchup_rating(attacker: Pokemon, defender: Pokemon) -> float:
        """
        Calculates a net type matchup rating for attacker vs defender.
        Positive indicates advantage; negative indicates disadvantage.
        """
        if not attacker or not defender:
            return 0.0

        # Offensive power: best STAB multiplier against defender
        atk_types = (
            (attacker.species.primary_type, attacker.species.secondary_type)
            if attacker.species.secondary_type
            else (attacker.species.primary_type,)
        )
        def_types = defender.species.types

        offensive_mult = max(
            (get_effectiveness_against_types(t, def_types) for t in atk_types),
            default=1.0,
        )

        # Defensive threat: best STAB multiplier defender has against attacker
        threat_mult = max(
            (get_effectiveness_against_types(t, atk_types) for t in def_types),
            default=1.0,
        )

        return float(offensive_mult - threat_mult)

    # --- Damage Projection & Attack Scoring ---

    def estimate_attack_damage(
        self,
        attack: Attack,
        attacker: Pokemon,
        defender: Pokemon,
    ) -> int:
        """
        Projects realistic damage for an attack without reading future RNG rolls.
        Accounts for base power, level factor, stats, type effectiveness, and STAB.
        """
        if attack.power <= 0:
            return 0

        eff = get_effectiveness_against_pokemon(attack, defender)
        if eff <= 0.0:
            return 0

        # STAB (Same-Type Attack Bonus)
        is_stab = (
            attack.type == attacker.species.primary_type
            or attack.type == attacker.species.secondary_type
        )
        stab_multiplier = 1.15 if is_stab else 1.0

        level_factor = (2 * attacker.level / 5) + 2
        atk_stat = max(1, getattr(attacker, "effective_attack", getattr(attacker, "attack", attacker.species.base_attack)))
        def_stat = max(1, getattr(defender, "effective_defense", getattr(defender, "defense", defender.species.base_defense)))
        stat_ratio = atk_stat / (def_stat * 35.0)

        base_dmg = (level_factor * attack.power * stat_ratio) + 2
        projected = int(base_dmg * eff * stab_multiplier)
        return max(1, projected)

    def score_attack(
        self,
        attack: Attack,
        attacker: Pokemon,
        defender: Pokemon,
        difficulty: DifficultyProfile,
        battle: Optional[Any] = None,
        archetype: Optional[TrainerArchetype] = None,
    ) -> tuple[float, str]:
        """
        Evaluates and scores a candidate attack according to tactical competence.
        Returns: (score, reason)
        """
        eff = get_effectiveness_against_pokemon(attack, defender)

        # 1. Status / Utility Move (power == 0)
        if attack.power <= 0:
            # Check if defender already has status
            has_status = False
            if battle is not None and hasattr(battle, "status_manager") and battle.status_manager is not None:
                has_status = battle.status_manager.has_any_effect(defender)

            if has_status:
                return (0.0, f"{attack.name} utility redundant: target already afflicted.")

            # Status moves are valuable when opponent is healthy
            hp_ratio = defender.current_hp / max(1, defender.max_hp)
            if hp_ratio > 0.5:
                status_score = 45.0 * (1.0 if difficulty != DifficultyProfile.EASY else 0.5)
                return (status_score, f"{attack.name} inflicts valuable status on healthy target.")
            else:
                return (10.0, f"{attack.name} status less valuable against weakened target.")

        # 2. Damaging Move
        if eff <= 0.0:
            if difficulty == DifficultyProfile.EASY and self._rng.random() < 0.25:
                # Easy AI occasionally misjudges immunities
                return (5.0, f"{attack.name} immune, but Easy AI made a careless mistake.")
            return (0.0, f"{attack.name} has no effect (type immunity).")

        dmg = self.estimate_attack_damage(attack, attacker, defender)
        accuracy_ratio = max(0.5, attack.accuracy / 100.0)
        base_score = float(dmg) * accuracy_ratio

        # Knockout detection (highest tactical priority)
        can_ko = dmg >= defender.current_hp
        if can_ko:
            if difficulty in (DifficultyProfile.HARD, DifficultyProfile.BOSS):
                base_score += 300.0
                return (base_score, f"{attack.name} scores a guaranteed knockout ({dmg} dmg vs {defender.current_hp} HP)!")
            elif difficulty == DifficultyProfile.NORMAL:
                base_score += 150.0
                return (base_score, f"{attack.name} provides high knockout opportunity.")
            else:
                base_score += 50.0

        # Super-effective bonus
        if eff > 1.0:
            base_score += 30.0 * eff
            reason = f"{attack.name} is super effective ({eff}x) dealing ~{dmg} damage."
        elif eff < 1.0:
            reason = f"{attack.name} is not very effective ({eff}x)."
        else:
            reason = f"{attack.name} deals standard damage (~{dmg} dmg)."

        # Archetype flavor preference
        if archetype is not None:
            from src.models.trainer_team_generator import ARCHETYPE_TYPE_AFFINITIES
            affinities = ARCHETYPE_TYPE_AFFINITIES.get(archetype, ())
            if attack.type in affinities:
                base_score += 8.0

        return (max(0.0, base_score), reason)

    # --- Tactical Switching Evaluation ---

    def evaluate_switch_options(
        self,
        trainer: Trainer,
        active_pokemon: Pokemon,
        opponent_pokemon: Pokemon,
        difficulty: DifficultyProfile,
        turn_number: int,
    ) -> Optional[tuple[Pokemon, float, str]]:
        """
        Determines whether a proactive switch is tactically advantageous.
        Returns: (candidate_pokemon, score, reason) or None if staying in.
        """
        # Easy AI never switches proactively
        if difficulty == DifficultyProfile.EASY:
            return None

        # Cooldown guard: enforce minimum gap between proactive switches
        last_turn = getattr(trainer, "last_switch_turn", -99)
        min_cooldown = 3 if difficulty == DifficultyProfile.NORMAL else 2
        if (turn_number - last_turn) < min_cooldown:
            return None

        # Must have conscious bench teammates
        conscious_bench = [
            p for p in trainer.team
            if not p.is_fainted and p.unique_id != active_pokemon.unique_id
        ]
        if not conscious_bench:
            return None

        # Check current active matchup
        current_matchup = self.calculate_matchup_rating(active_pokemon, opponent_pokemon)
        active_hp_ratio = active_pokemon.current_hp / max(1, active_pokemon.max_hp)

        # Check if active Pokemon has an imminent KO move against opponent (if so, never switch!)
        for atk in active_pokemon.attacks:
            if self.estimate_attack_damage(atk, active_pokemon, opponent_pokemon) >= opponent_pokemon.current_hp:
                return None

        # Evaluate bench options
        best_candidate: Optional[Pokemon] = None
        best_candidate_rating: float = -999.0

        for candidate in conscious_bench:
            candidate_rating = self.calculate_matchup_rating(candidate, opponent_pokemon)
            cand_hp_ratio = candidate.current_hp / max(1, candidate.max_hp)
            # Factor in bench health
            adjusted_rating = candidate_rating + (cand_hp_ratio * 0.5)

            if adjusted_rating > best_candidate_rating:
                best_candidate_rating = adjusted_rating
                best_candidate = candidate

        if best_candidate is None:
            return None

        # Switching threshold decision per difficulty tier
        net_advantage_gain = best_candidate_rating - current_matchup

        if difficulty == DifficultyProfile.NORMAL:
            # Normal AI switches only when near fainting (< 25% HP) and bench offers a significantly better matchup
            if active_hp_ratio < 0.25 and net_advantage_gain >= 1.5:
                if self._rng.random() < 0.35:
                    return (
                        best_candidate,
                        best_candidate_rating,
                        f"Tactical switch: {active_pokemon.display_name} weakened ({int(active_hp_ratio*100)}% HP); "
                        f"{best_candidate.display_name} offers superior type matchup ({best_candidate_rating:+.1f}).",
                    )
            return None

        elif difficulty == DifficultyProfile.HARD:
            # Hard AI switches if at severe disadvantage (< -1.0) or to preserve a low-HP ace
            if (current_matchup <= -1.0 and net_advantage_gain >= 1.5) or (active_hp_ratio < 0.3 and net_advantage_gain >= 1.0):
                if self._rng.random() < 0.60:
                    return (
                        best_candidate,
                        best_candidate_rating,
                        f"Counter switch: {best_candidate.display_name} counters opponent (gain {net_advantage_gain:+.1f}).",
                    )
            return None

        elif difficulty == DifficultyProfile.BOSS:
            # Boss AI proactively optimizes matchups and protects key team members
            if current_matchup <= -0.5 and net_advantage_gain >= 1.2:
                return (
                    best_candidate,
                    best_candidate_rating,
                    f"Elite counter-switch: deploying {best_candidate.display_name} for type dominance ({best_candidate_rating:+.1f}).",
                )

        return None

    # --- Turn Decision Entry Point ---

    def decide_action(
        self,
        battle: Any,
        trainer: Trainer,
        active_pokemon: Pokemon,
        opponent_pokemon: Pokemon,
        rng: Optional[random.Random] = None,
    ) -> TrainerDecision:
        """
        Main deliberation routine for an AI trainer turn.
        Evaluates potential switches and attacks, selecting the optimal legal action.
        """
        r = rng if rng is not None else self._rng
        diff_raw = getattr(trainer, "difficulty", DifficultyProfile.NORMAL)
        if isinstance(diff_raw, str):
            diff = DifficultyProfile[diff_raw.upper()] if diff_raw.upper() in DifficultyProfile.__members__ else DifficultyProfile.NORMAL
        elif isinstance(diff_raw, DifficultyProfile):
            diff = diff_raw
        else:
            diff = DifficultyProfile.NORMAL

        arch_raw = getattr(trainer, "archetype", None)
        if isinstance(arch_raw, str):
            archetype = TrainerArchetype[arch_raw.upper()] if arch_raw.upper() in TrainerArchetype.__members__ else None
        elif isinstance(arch_raw, TrainerArchetype):
            archetype = arch_raw
        else:
            archetype = None

        current_turn = getattr(battle, "current_turn", 1)

        # 1. Evaluate proactive switching
        switch_option = self.evaluate_switch_options(
            trainer=trainer,
            active_pokemon=active_pokemon,
            opponent_pokemon=opponent_pokemon,
            difficulty=diff,
            turn_number=current_turn,
        )
        if switch_option is not None:
            target_mon, switch_score, switch_reason = switch_option
            return TrainerDecision(
                action_type=TrainerActionType.SWITCH,
                target_pokemon=target_mon,
                reason=switch_reason,
                score=switch_score,
                confidence=0.85,
            )

        # 2. Evaluate available attacks
        attacks = list(active_pokemon.attacks)
        if not attacks:
            # Fallback struggle
            return TrainerDecision(
                action_type=TrainerActionType.ATTACK,
                chosen_attack=None,
                reason="No known attacks available; will struggle.",
                confidence=0.1,
            )

        scored_attacks: list[tuple[Attack, float, str]] = []
        for atk in attacks:
            score, reason = self.score_attack(
                attack=atk,
                attacker=active_pokemon,
                defender=opponent_pokemon,
                difficulty=diff,
                battle=battle,
                archetype=archetype,
            )
            # Difficulty noise
            if diff == DifficultyProfile.EASY:
                noise = r.uniform(-25.0, 25.0)
            elif diff == DifficultyProfile.NORMAL:
                noise = r.uniform(-8.0, 8.0)
            elif diff == DifficultyProfile.HARD:
                noise = r.uniform(-1.5, 1.5)
            else:
                noise = 0.0

            scored_attacks.append((atk, max(0.0, score + noise), reason))

        # Sort descending by score
        scored_attacks.sort(key=lambda item: item[1], reverse=True)

        # Final selection based on difficulty profile
        if diff == DifficultyProfile.EASY and r.random() < 0.25 and len(scored_attacks) > 1:
            # Easy AI occasionally picks an alternative move
            chosen_atk, chosen_score, chosen_reason = r.choice(scored_attacks)
        elif diff == DifficultyProfile.NORMAL and r.random() < 0.15 and len(scored_attacks) > 1:
            # Normal AI occasionally picks 2nd best move
            chosen_atk, chosen_score, chosen_reason = scored_attacks[1]
        else:
            # Best scored move
            chosen_atk, chosen_score, chosen_reason = scored_attacks[0]

        return TrainerDecision(
            action_type=TrainerActionType.ATTACK,
            chosen_attack=chosen_atk,
            score=chosen_score,
            reason=chosen_reason,
            confidence=0.9,
            factors={"turn": current_turn, "difficulty": diff.value},
        )
