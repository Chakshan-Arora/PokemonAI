"""
Wild Pokémon decision model.
Quantifies action choices (attack, flee, inspect) based on:
  1. Wild Pokémon current HP (self-preservation vs confidence).
  2. Level comparison between wild Pokémon and player's active Pokémon.
  3. Player's past behavioral reputation (aggressive, peaceful, or whatever).
  4. Individual behavioral personality traits (aggression, fear, curiosity, confidence).
"""
from enum import Enum
from dataclasses import dataclass, field
import random
from typing import Optional, Any
from src.models.pokemon import Pokemon
from src.models.attack import Attack
from src.models.player import Player
from src.models.player_behavior import PlayerBehaviorProfile, PlayerBehaviorTracker


class WildActionType(str, Enum):
    """
    Action choices available to wild Pokémon during encounters.
    """
    ATTACK = "attack"
    FLEE = "flee"
    INSPECT = "inspect"

    @property
    def display_name(self) -> str:
        return self.value.title()


@dataclass(frozen=True)
class WildDecision:
    """
    Decision outcome produced by the wild Pokémon decision model.
    """
    action_type: WildActionType
    scores: dict[WildActionType, float]
    reason: str
    chosen_attack: Optional[Attack] = None
    factors: dict[str, Any] = field(default_factory=dict)


class WildDecisionModel:
    """
    Decision engine evaluating and quantifying action factors for wild Pokémon.
    """

    def __init__(
        self,
        base_attack: float = 40.0,
        base_flee: float = 15.0,
        base_inspect: float = 15.0,
    ) -> None:
        self.base_attack = float(base_attack)
        self.base_flee = float(base_flee)
        self.base_inspect = float(base_inspect)

    def evaluate_action_scores(
        self,
        wild_pokemon: Pokemon,
        player_pokemon: Optional[Pokemon] = None,
        player: Optional[Player] = None,
        player_behavior_override: Optional[PlayerBehaviorProfile] = None,
    ) -> tuple[dict[WildActionType, float], dict[str, Any]]:
        """
        Quantifies action weights for ATTACK, FLEE, and INSPECT using all key factors.

        Returns:
            Tuple of (scores_dict, factors_dict).
        """
        if not isinstance(wild_pokemon, Pokemon):
            raise TypeError(f"wild_pokemon must be a Pokemon instance, got {type(wild_pokemon).__name__}.")

        # 1. Base Scores
        attack_score = self.base_attack
        flee_score = self.base_flee
        inspect_score = self.base_inspect

        # 2. HP Factor (Self-preservation vs Battle readiness)
        hp_ratio = wild_pokemon.current_hp / max(1, wild_pokemon.max_hp)
        hp_mods = {"attack": 0.0, "flee": 0.0, "inspect": 0.0}

        if hp_ratio <= 0.30:
            # Low / Critical HP: massive urge to flee, reduced attack, zero inspect
            low_scale = (0.35 - hp_ratio) / 0.35
            hp_mods["flee"] += 35.0 * low_scale
            hp_mods["attack"] -= 20.0 * low_scale
            hp_mods["inspect"] -= 25.0
        elif hp_ratio <= 0.55:
            # Moderately damaged
            hp_mods["flee"] += 10.0
            hp_mods["attack"] -= 5.0
            hp_mods["inspect"] -= 10.0
        elif hp_ratio >= 0.75:
            # Healthy / Full HP
            hp_mods["flee"] -= 10.0
            hp_mods["attack"] += 10.0
            hp_mods["inspect"] += 10.0

        attack_score += hp_mods["attack"]
        flee_score += hp_mods["flee"]
        inspect_score += hp_mods["inspect"]

        # 3. Level Difference Factor (Relative strength assessment)
        player_lvl = player_pokemon.level if player_pokemon is not None else wild_pokemon.level
        level_diff = wild_pokemon.level - player_lvl
        lvl_mods = {"attack": 0.0, "flee": 0.0, "inspect": 0.0}

        if level_diff > 0:
            # Wild is higher level: confident predator / fighter
            lvl_mods["attack"] += min(35.0, level_diff * 4.0)
            lvl_mods["flee"] -= min(25.0, level_diff * 5.0)
            lvl_mods["inspect"] += min(15.0, level_diff * 1.5)
        elif level_diff < 0:
            # Wild is lower level: intimidated by stronger opponent
            abs_diff = abs(level_diff)
            lvl_mods["flee"] += min(40.0, abs_diff * 5.0)
            lvl_mods["attack"] -= min(30.0, abs_diff * 3.5)
            lvl_mods["inspect"] -= min(15.0, abs_diff * 1.5)

        attack_score += lvl_mods["attack"]
        flee_score += lvl_mods["flee"]
        inspect_score += lvl_mods["inspect"]

        # 4. Player Past Behavior Factor (Reputation perception)
        if player_behavior_override is not None:
            profile = player_behavior_override
        elif player is not None:
            profile = getattr(player, "behavior_profile", PlayerBehaviorProfile.NEUTRAL)
        else:
            profile = PlayerBehaviorProfile.NEUTRAL

        beh_mods = {"attack": 0.0, "flee": 0.0, "inspect": 0.0}
        if profile == PlayerBehaviorProfile.AGGRESSIVE:
            # Player is known to attack and defeat Pokémon
            if level_diff <= 0 or hp_ratio < 0.65:
                beh_mods["flee"] += 35.0   # Flee from ruthless trainer
                beh_mods["attack"] -= 10.0
                beh_mods["inspect"] -= 30.0
            else:
                beh_mods["attack"] += 20.0  # Dominant wild Pokémon fights back fiercely
                beh_mods["inspect"] -= 30.0
        elif profile == PlayerBehaviorProfile.PEACEFUL:
            # Player is known for peaceful encounters (fleeing safely, observing, not attacking)
            beh_mods["inspect"] += 45.0  # Approached with curiosity
            beh_mods["flee"] -= 20.0     # Feels safe
            beh_mods["attack"] -= 25.0   # Disinclined to strike unprovoked
        else:
            # Neutral / Whatever
            pass

        attack_score += beh_mods["attack"]
        flee_score += beh_mods["flee"]
        inspect_score += beh_mods["inspect"]

        # 5. Personality Traits Factor (Inherent temperament)
        pers = getattr(wild_pokemon, "personality", None)
        pers_mods = {"attack": 0.0, "flee": 0.0, "inspect": 0.0}
        if pers is not None:
            agg = getattr(pers, "aggression", 50)
            fear = getattr(pers, "fear", 50)
            cur = getattr(pers, "curiosity", 50)
            soc = getattr(pers, "sociability", 50)
            conf = getattr(pers, "confidence", 50)

            pers_mods["attack"] += (agg - 50) * 0.35 + (conf - 50) * 0.15
            pers_mods["flee"] += (fear - 50) * 0.35 - (conf - 50) * 0.15
            pers_mods["inspect"] += ((cur + soc) / 2.0 - 50) * 0.30

        attack_score += pers_mods["attack"]
        flee_score += pers_mods["flee"]
        inspect_score += pers_mods["inspect"]

        # 6. Attack Capability Constraint
        if not wild_pokemon.attacks:
            attack_score = 0.0

        # 7. Floor Clamping
        final_attack = max(0.0 if not wild_pokemon.attacks else 5.0, round(attack_score, 2))
        final_flee = max(1.0, round(flee_score, 2))
        final_inspect = max(0.0, round(inspect_score, 2))

        scores = {
            WildActionType.ATTACK: final_attack,
            WildActionType.FLEE: final_flee,
            WildActionType.INSPECT: final_inspect,
        }

        factors = {
            "hp_ratio": round(hp_ratio, 2),
            "level_diff": level_diff,
            "player_profile": profile.value,
            "hp_mods": hp_mods,
            "level_mods": lvl_mods,
            "behavior_mods": beh_mods,
            "personality_mods": pers_mods,
        }

        return scores, factors

    def decide_action(
        self,
        wild_pokemon: Pokemon,
        player_pokemon: Optional[Pokemon] = None,
        player: Optional[Player] = None,
        rng: Optional[random.Random] = None,
        deterministic: bool = True,
        player_behavior_override: Optional[PlayerBehaviorProfile] = None,
    ) -> WildDecision:
        """
        Evaluates scores and deterministically or probabilistically decides the wild Pokémon's action.

        Args:
            wild_pokemon: The wild Pokémon making the decision.
            player_pokemon: Player's active battling Pokémon.
            player: Player instance containing behavior history.
            rng: Injected random number generator.
            deterministic: If True, selects the highest scored action.
            player_behavior_override: Explicit behavior profile override for testing.

        Returns:
            WildDecision summarizing chosen action, scores, rationale, and chosen attack (if attacking).
        """
        scores, factors = self.evaluate_action_scores(
            wild_pokemon=wild_pokemon,
            player_pokemon=player_pokemon,
            player=player,
            player_behavior_override=player_behavior_override,
        )

        r = rng if rng is not None else random.Random()

        if deterministic:
            chosen_type = max(scores, key=lambda k: scores[k])
        else:
            action_types = list(scores.keys())
            weights = [scores[t] for t in action_types]
            total_weight = sum(weights)
            if total_weight <= 0:
                chosen_type = WildActionType.ATTACK if wild_pokemon.attacks else WildActionType.FLEE
            else:
                chosen_type = r.choices(action_types, weights=weights, k=1)[0]

        chosen_attack: Optional[Attack] = None
        if chosen_type == WildActionType.ATTACK:
            if wild_pokemon.attacks:
                chosen_attack = r.choice(wild_pokemon.attacks)
            else:
                # Fallback if no attacks known
                chosen_type = WildActionType.FLEE

        # Build informative human-readable rationale
        name = wild_pokemon.display_name
        hp_pct = int(factors["hp_ratio"] * 100)
        lvl_diff = factors["level_diff"]
        profile = factors["player_profile"]

        if chosen_type == WildActionType.FLEE:
            if factors["hp_ratio"] <= 0.35:
                reason = f"Wild {name} was critically injured ({hp_pct}% HP) and fled in self-preservation."
            elif lvl_diff < 0:
                reason = f"Wild {name} was outmatched by the higher-level opponent ({lvl_diff:+d} Lv) and fled."
            elif profile == "aggressive":
                reason = f"Wild {name} sensed your aggressive demeanor and fled to safety."
            else:
                reason = f"Wild {name} was startled and fled from battle."

        elif chosen_type == WildActionType.INSPECT:
            if profile == "peaceful":
                reason = f"Wild {name} sensed your calm, peaceful aura and is inspecting you curiously."
            elif lvl_diff > 0:
                reason = f"Wild {name} confidently held its ground to size up your team."
            else:
                reason = f"Wild {name} paused warily to inspect your movements."

        else:  # ATTACK
            atk_name = chosen_attack.name if chosen_attack else "an attack"
            if profile == "aggressive":
                reason = f"Wild {name} stood its ground against your aggression and lashed out with {atk_name}!"
            elif lvl_diff > 0:
                reason = f"Wild {name} asserted its dominance with {atk_name}!"
            else:
                reason = f"Wild {name} struck with {atk_name}."

        return WildDecision(
            action_type=chosen_type,
            scores=scores,
            reason=reason,
            chosen_attack=chosen_attack,
            factors=factors,
        )
