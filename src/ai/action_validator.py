"""
Authoritative action validator for autonomous Pokemon agents.
Enforces non-negotiable world rules and game engine authority:
  - The AI proposes intentions; the engine decides what is valid and what actually happens.
  - Captured Pokemon cannot independently leave their trainer.
  - Pokemon cannot invent unknown moves or act when fainted.
  - Free-form model outputs are sanitized into valid, permitted game actions.
"""
from dataclasses import dataclass
from typing import Any, Optional, Sequence

from src.ai.decision import AgentActionType, AgentDecision
from src.models.pokemon import Pokemon


@dataclass(frozen=True)
class ValidationResult:
    """
    Outcome of validating an AI agent's proposed decision against authoritative game rules.
    """
    valid: bool
    sanitized_decision: AgentDecision
    reason: str
    error_code: Optional[str] = None


class ActionValidator:
    """
    Validates and sanitizes proposed agent decisions against game constraints.
    """

    @staticmethod
    def validate(
        decision: AgentDecision,
        pokemon: Optional[Pokemon] = None,
        is_captured: bool = False,
        in_trainer_battle: bool = False,
        in_wild_battle: bool = False,
        perception: Optional[Any] = None,
    ) -> ValidationResult:
        """
        Validates an AgentDecision against the Pokemon's actual state and battle context.
        If invalid, produces a sanitized safe fallback decision with a clear reason.
        """
        if not isinstance(decision, AgentDecision):
            raise TypeError("decision must be an AgentDecision instance.")
        if pokemon is None and perception is None:
            raise ValueError("Either pokemon or perception must be provided for validation.")
        if pokemon is not None and not isinstance(pokemon, Pokemon):
            raise TypeError("pokemon must be a Pokemon instance.")

        if pokemon is not None:
            display_name = pokemon.display_name
            known_move_names = [atk.name.lower() for atk in pokemon.attacks]
            is_fainted = pokemon.is_fainted
            has_attacks = bool(pokemon.attacks)
            default_move = pokemon.attacks[0].name if pokemon.attacks else None
        else:
            display_name = getattr(perception, "species", "Pokemon")
            phys = getattr(perception, "physical_state", {})
            known_moves = phys.get("known_moves", [])
            known_move_names = [m.lower() for m in known_moves]
            is_fainted = bool(phys.get("is_fainted", False))
            has_attacks = bool(known_moves)
            default_move = known_moves[0] if known_moves else None

        action = decision.action_type

        # 1. Check fainted status
        if is_fainted:
            if action in (AgentActionType.ATTACK, AgentActionType.DEFEND, AgentActionType.FLEE):
                sanitized = AgentDecision(
                    action_type=AgentActionType.REST,
                    intent="Resting while fainted",
                    dialogue=f"{display_name} has no energy left to act.",
                    emotional_state="exhausted",
                    rationale=f"Cannot perform {action.value} because {display_name} has fainted.",
                    confidence=1.0,
                )
                return ValidationResult(
                    valid=False,
                    sanitized_decision=sanitized,
                    reason=f"{display_name} has fainted and cannot {action.value}.",
                    error_code="POKEMON_FAINTED",
                )

        # 2. Check Attack validity (known moves)
        if action == AgentActionType.ATTACK:
            if not has_attacks:
                sanitized = AgentDecision(
                    action_type=AgentActionType.HESITATE,
                    intent="Hesitates with no known attacks",
                    dialogue=f"{display_name} looks confused and has no attacks to use.",
                    emotional_state="confused",
                    rationale="Attempted to attack with no known moves.",
                    confidence=1.0,
                )
                return ValidationResult(
                    valid=False,
                    sanitized_decision=sanitized,
                    reason="Pokemon has no available attacks.",
                    error_code="NO_ATTACKS_KNOWN",
                )

            chosen = (decision.chosen_move or "").strip().lower()
            if not chosen or chosen not in known_move_names:
                # Fallback to the Pokemon's first known attack
                sanitized = AgentDecision(
                    action_type=AgentActionType.ATTACK,
                    intent=decision.intent,
                    target=decision.target,
                    chosen_move=default_move,
                    dialogue=decision.dialogue or f"{display_name} used {default_move}!",
                    emotional_state=decision.emotional_state,
                    rationale=f"Proposed move '{decision.chosen_move}' not known. Sanitized to known move '{default_move}'.",
                    confidence=decision.confidence,
                )
                return ValidationResult(
                    valid=False,
                    sanitized_decision=sanitized,
                    reason=f"Move '{decision.chosen_move}' is not known by {display_name}. Sanitized to '{default_move}'.",
                    error_code="INVALID_MOVE",
                )

        # 3. Check Trainer battle Flee restrictions
        if action == AgentActionType.FLEE and in_trainer_battle:
            sanitized = AgentDecision(
                action_type=AgentActionType.DEFEND,
                intent="Defensive retreat attempt blocked by trainer battle rules",
                dialogue=f"{display_name} wanted to run, but there is nowhere to hide in a trainer match!",
                emotional_state="anxious",
                rationale="Cannot flee from an official trainer match.",
                confidence=decision.confidence,
            )
            return ValidationResult(
                valid=False,
                sanitized_decision=sanitized,
                reason="Cannot flee from a trainer battle. Sanitized to DEFEND.",
                error_code="CANNOT_FLEE_TRAINER",
            )

        # 4. Check Non-negotiable Ownership Boundary (REQUEST_RELEASE)
        if action == AgentActionType.REQUEST_RELEASE:
            # The release request is VALID as dialogue/expression,
            # but cannot independently remove ownership from the trainer.
            sanitized = AgentDecision(
                action_type=AgentActionType.REQUEST_RELEASE,
                intent="Pleads to be set free",
                dialogue=decision.dialogue or f"{display_name} looks at you with sorrowful eyes, pleading to return to the wild.",
                emotional_state="distressed",
                rationale=decision.rationale or "Pokemon is unhappy and requests to be released by its trainer.",
                confidence=decision.confidence,
            )
            return ValidationResult(
                valid=True,
                sanitized_decision=sanitized,
                reason="Release requested. Ownership remains unchanged until explicit player release action.",
            )

        # 5. Check Obey validity
        if action == AgentActionType.OBEY:
            if not is_captured:
                # Wild Pokemon cannot obey a trainer it doesn't belong to
                sanitized = AgentDecision(
                    action_type=AgentActionType.INSPECT,
                    intent="Observing stranger",
                    dialogue=f"Wild {display_name} does not take orders from strangers.",
                    emotional_state="wary",
                    rationale="Wild Pokemon cannot OBEY trainer commands.",
                    confidence=decision.confidence,
                )
                return ValidationResult(
                    valid=False,
                    sanitized_decision=sanitized,
                    reason="Wild Pokemon cannot obey trainer commands. Sanitized to INSPECT.",
                    error_code="WILD_CANNOT_OBEY",
                )

        # Proposed decision passed all validations
        return ValidationResult(
            valid=True,
            sanitized_decision=decision,
            reason="Action is valid and permitted by game engine.",
        )
