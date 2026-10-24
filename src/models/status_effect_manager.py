"""
Status effect manager for Pokemon battles.
Coordinates status effect application, paralysis action checks, temporary stat multipliers,
end-of-turn damage, and effect duration expiration.
"""
import random
from dataclasses import dataclass
from typing import Optional, Union, Sequence
from src.models.pokemon import Pokemon
from src.models.status_effect import (
    StatusEffectType,
    AttackEffect,
    StatusEffect,
    DEFAULT_BURN_DAMAGE_FRACTION,
    DEFAULT_POISON_DAMAGE_FRACTION,
    DEFAULT_PARALYSIS_CHANCE,
    DEFAULT_STAT_REDUCTION_DURATION,
    DEFAULT_STAT_REDUCTION_MULTIPLIER,
)


@dataclass(frozen=True)
class EffectApplicationResult:
    """
    Structured outcome of an attempt to apply a status effect to a Pokemon.
    """
    success: bool
    pokemon: Optional[Pokemon]
    effect: Optional[StatusEffect]
    applied: bool
    roll: Optional[int]
    chance: int
    reason: str


@dataclass(frozen=True)
class ActionCheckResult:
    """
    Structured outcome of checking whether a Pokemon can execute its turn action (e.g. paralysis check).
    """
    can_act: bool
    pokemon: Pokemon
    paralyzed: bool
    roll: Optional[int]
    chance: int
    reason: str


@dataclass(frozen=True)
class EndOfTurnEffectRecord:
    """
    Record of a single status effect processed at end-of-turn for a Pokemon.
    """
    effect_type: StatusEffectType
    damage: int
    expired: bool
    remaining_duration: Optional[int]
    message: str


@dataclass(frozen=True)
class EndOfTurnResult:
    """
    Structured outcome of end-of-turn status processing for a Pokemon.
    """
    pokemon: Pokemon
    damage_taken: int
    fainted: bool
    effects_processed: tuple[EndOfTurnEffectRecord, ...]
    expired_effects: tuple[StatusEffectType, ...]
    reason: str


class StatusEffectManager:
    """
    Manages active status effects on Pokemon instances.
    Enforces rules:
      - At most one major persistent condition (burn, poison, paralysis) per Pokemon.
      - Duplicate persistent conditions are rejected.
      - Temporary stat reductions (attack, defense) can coexist with each other and major conditions.
      - Temporary reductions stack multiplicatively with a lower floor (min 25% of unmodified stat).
      - Fainted Pokemon cannot act or receive new effects.
      - Decrements duration of temporary effects and cleans them up upon expiration.
    """

    def __init__(
        self,
        rng: Optional[random.Random] = None,
        seed: Optional[int] = None,
    ) -> None:
        if rng is not None:
            self._rng: random.Random = rng
        elif seed is not None:
            self._rng = random.Random(seed)
        else:
            self._rng = random.Random()

        # Mapping of pokemon.unique_id -> list of active StatusEffect objects
        self._effects: dict[str, list[StatusEffect]] = {}

    def get_effects(self, pokemon: Pokemon) -> list[StatusEffect]:
        """Returns a copy of the list of active status effects on the Pokemon."""
        if not isinstance(pokemon, Pokemon):
            raise TypeError(f"pokemon must be a Pokemon instance, got {type(pokemon).__name__}.")
        return [eff.copy() for eff in self._effects.get(pokemon.unique_id, [])]

    def has_effect(self, pokemon: Pokemon, effect_type: StatusEffectType) -> bool:
        """Checks if the Pokemon currently has an active effect of the specified type."""
        if not isinstance(pokemon, Pokemon) or not isinstance(effect_type, StatusEffectType):
            return False
        return any(eff.effect_type == effect_type for eff in self._effects.get(pokemon.unique_id, []))

    def get_major_condition(self, pokemon: Pokemon) -> Optional[StatusEffect]:
        """Returns the active major persistent condition (Burn, Poison, Paralysis) if any, else None."""
        if not isinstance(pokemon, Pokemon):
            return None
        for eff in self._effects.get(pokemon.unique_id, []):
            if eff.effect_type.is_major_condition:
                return eff
        return None

    def apply_effect(
        self,
        pokemon: Pokemon,
        effect: Union[StatusEffect, AttackEffect, StatusEffectType],
        source_attack_name: Optional[str] = None,
        roll_override: Optional[int] = None,
    ) -> EffectApplicationResult:
        """
        Attempts to apply a status effect or attack effect to a Pokemon.

        Rules:
          - Fainted Pokemon cannot receive status effects.
          - If effect is an AttackEffect, evaluates accuracy/chance roll (1-100).
          - At most one major persistent condition (Burn, Poison, Paralysis) per Pokemon.
          - Duplicate major condition attempts are rejected.
          - Temporary stat reductions (Attack, Defense) can coexist.
        """
        if not isinstance(pokemon, Pokemon):
            return EffectApplicationResult(
                success=False,
                pokemon=None,
                effect=None,
                applied=False,
                roll=None,
                chance=0,
                reason=f"Invalid pokemon: expected Pokemon instance, got {type(pokemon).__name__}.",
            )

        if isinstance(effect, StatusEffectType):
            effect = StatusEffect(effect_type=effect, source_attack_name=source_attack_name)

        if not isinstance(effect, (StatusEffect, AttackEffect)):
            return EffectApplicationResult(
                success=False,
                pokemon=pokemon,
                effect=None,
                applied=False,
                roll=None,
                chance=0,
                reason=f"Invalid effect: expected StatusEffect or AttackEffect, got {type(effect).__name__}.",
            )

        # Fainted Pokemon cannot receive status effects
        if pokemon.is_fainted:
            return EffectApplicationResult(
                success=False,
                pokemon=pokemon,
                effect=None,
                applied=False,
                roll=None,
                chance=0,
                reason=f"{pokemon.display_name} has fainted and cannot receive status effects.",
            )

        # Evaluate chance roll if given an AttackEffect
        chance = effect.chance if isinstance(effect, AttackEffect) else 100
        roll: Optional[int] = None
        if isinstance(effect, AttackEffect):
            roll = roll_override if roll_override is not None else self._rng.randint(1, 100)
            if roll > chance:
                return EffectApplicationResult(
                    success=False,
                    pokemon=pokemon,
                    effect=None,
                    applied=False,
                    roll=roll,
                    chance=chance,
                    reason=f"{effect.effect_type.display_name} effect failed application chance (rolled {roll} > {chance}%).",
                )

        # Convert to active StatusEffect instance
        if isinstance(effect, AttackEffect):
            active_effect = StatusEffect.from_attack_effect(effect, source_attack_name=source_attack_name)
        else:
            active_effect = effect.copy()

        # Check major condition rules
        if active_effect.effect_type.is_major_condition:
            existing_major = self.get_major_condition(pokemon)
            if existing_major is not None:
                if existing_major.effect_type == active_effect.effect_type:
                    return EffectApplicationResult(
                        success=False,
                        pokemon=pokemon,
                        effect=None,
                        applied=False,
                        roll=roll,
                        chance=chance,
                        reason=f"{pokemon.display_name} is already afflicted with {active_effect.effect_type.display_name}.",
                    )
                else:
                    return EffectApplicationResult(
                        success=False,
                        pokemon=pokemon,
                        effect=None,
                        applied=False,
                        roll=roll,
                        chance=chance,
                        reason=(
                            f"{pokemon.display_name} already has major status condition "
                            f"{existing_major.effect_type.display_name} and cannot be afflicted with {active_effect.effect_type.display_name}."
                        ),
                    )

        # Store in internal tracking
        if pokemon.unique_id not in self._effects:
            self._effects[pokemon.unique_id] = []
        self._effects[pokemon.unique_id].append(active_effect)

        # Synchronize with Pokemon model helper if available
        if hasattr(pokemon, "add_status_effect"):
            pokemon.add_status_effect(active_effect)

        return EffectApplicationResult(
            success=True,
            pokemon=pokemon,
            effect=active_effect,
            applied=True,
            roll=roll,
            chance=chance,
            reason=f"{pokemon.display_name} was afflicted with {active_effect.effect_type.display_name}!",
        )

    def apply_attack_effect(
        self,
        attacker: Pokemon,
        defender: Pokemon,
        effect: AttackEffect,
        source_attack_name: Optional[str] = None,
        roll_override: Optional[int] = None,
    ) -> EffectApplicationResult:
        """
        Applies an AttackEffect from an attack execution to either the defender or attacker.
        """
        if not isinstance(effect, AttackEffect):
            raise TypeError(f"effect must be an AttackEffect, got {type(effect).__name__}.")

        target = attacker if effect.target == "user" else defender
        return self.apply_effect(
            pokemon=target,
            effect=effect,
            source_attack_name=source_attack_name,
            roll_override=roll_override,
        )

    def check_can_act(
        self,
        pokemon: Pokemon,
        roll_override: Optional[int] = None,
    ) -> ActionCheckResult:
        """
        Checks if the Pokemon is able to execute an action on its turn.
        Evaluates paralysis check (default 25% chance to skip turn).
        """
        if not isinstance(pokemon, Pokemon):
            raise TypeError(f"pokemon must be a Pokemon instance, got {type(pokemon).__name__}.")

        if pokemon.is_fainted:
            return ActionCheckResult(
                can_act=False,
                pokemon=pokemon,
                paralyzed=False,
                roll=None,
                chance=0,
                reason=f"{pokemon.display_name} is fainted and cannot act.",
            )

        # Find active paralysis effect
        para_effects = [eff for eff in self._effects.get(pokemon.unique_id, []) if eff.effect_type == StatusEffectType.PARALYSIS]
        if not para_effects:
            return ActionCheckResult(
                can_act=True,
                pokemon=pokemon,
                paralyzed=False,
                roll=None,
                chance=0,
                reason=f"{pokemon.display_name} is free to act.",
            )

        para_eff = para_effects[0]
        chance = para_eff.paralysis_chance
        roll = roll_override if roll_override is not None else self._rng.randint(1, 100)

        if roll <= chance:
            return ActionCheckResult(
                can_act=False,
                pokemon=pokemon,
                paralyzed=True,
                roll=roll,
                chance=chance,
                reason=f"{pokemon.display_name} is paralyzed! It can't move!",
            )
        else:
            return ActionCheckResult(
                can_act=True,
                pokemon=pokemon,
                paralyzed=True,
                roll=roll,
                chance=chance,
                reason=f"{pokemon.display_name} moved despite paralysis.",
            )

    def get_effective_stat(self, pokemon: Pokemon, stat_name: str) -> int:
        """
        Computes the effective combat stat for a Pokemon factoring in active temporary stat reductions.

        Stacking rule:
          - Multiple reductions stack multiplicatively: stat * m1 * m2 ...
          - Total multiplier cannot drop below 0.25 (floor of 25% of unmodified stat).
          - Effective stat is guaranteed to be at least 1.
          - Trained bonuses and species base stats remain intact when effects expire.
        """
        if not isinstance(pokemon, Pokemon):
            raise TypeError(f"pokemon must be a Pokemon instance, got {type(pokemon).__name__}.")

        norm = stat_name.strip().lower()
        active = self._effects.get(pokemon.unique_id, [])

        if norm == "attack":
            base_stat = pokemon.attack
            target_type = StatusEffectType.ATTACK_REDUCTION
        elif norm == "defense":
            base_stat = pokemon.defense
            target_type = StatusEffectType.DEFENSE_REDUCTION
        else:
            return pokemon.get_stat(norm)

        mult = 1.0
        for eff in active:
            if eff.effect_type == target_type and not eff.is_expired:
                m = eff.multiplier if eff.multiplier is not None else DEFAULT_STAT_REDUCTION_MULTIPLIER
                mult *= m

        # Clamp total multiplier between 0.25 and 1.0
        mult = max(0.25, mult)
        return max(1, int(base_stat * mult))

    def process_end_of_turn(self, pokemon: Pokemon) -> EndOfTurnResult:
        """
        Processes end-of-turn status events for a Pokemon:
          1. Burn/Poison status damage (min 1 damage).
          2. Decrements remaining duration for temporary stat effects.
          3. Cleans up and removes expired effects.

        Does not process damage on fainted Pokemon.
        """
        if not isinstance(pokemon, Pokemon):
            raise TypeError(f"pokemon must be a Pokemon instance, got {type(pokemon).__name__}.")

        if pokemon.is_fainted:
            return EndOfTurnResult(
                pokemon=pokemon,
                damage_taken=0,
                fainted=True,
                effects_processed=(),
                expired_effects=(),
                reason=f"{pokemon.display_name} has fainted.",
            )

        active = self._effects.get(pokemon.unique_id, [])
        records: list[EndOfTurnEffectRecord] = []
        expired_list: list[StatusEffectType] = []
        total_damage = 0

        for eff in list(active):
            # 1. Damage-dealing persistent conditions (Burn, Poison)
            if eff.effect_type in (StatusEffectType.BURN, StatusEffectType.POISON):
                frac = eff.damage_fraction if eff.damage_fraction is not None else DEFAULT_BURN_DAMAGE_FRACTION
                dmg = max(1, int(pokemon.max_hp * frac))
                actual_dmg = pokemon.take_damage(dmg)
                total_damage += actual_dmg

                msg = (
                    f"{pokemon.display_name} is hurt by its {eff.effect_type.value}! "
                    f"(-{actual_dmg} HP, remaining: {pokemon.current_hp}/{pokemon.max_hp})"
                )
                records.append(EndOfTurnEffectRecord(
                    effect_type=eff.effect_type,
                    damage=actual_dmg,
                    expired=False,
                    remaining_duration=None,
                    message=msg,
                ))

                if pokemon.is_fainted:
                    break

            # 2. Temporary stat reductions (duration decrement)
            elif eff.effect_type.is_stat_reduction:
                eff.decrement_duration()
                if eff.is_expired:
                    expired_list.append(eff.effect_type)
                    active.remove(eff)
                    if hasattr(pokemon, "remove_status_effect"):
                        pokemon.remove_status_effect(eff.effect_type)
                    msg = f"{pokemon.display_name}'s {eff.effect_type.display_name} wore off!"
                    records.append(EndOfTurnEffectRecord(
                        effect_type=eff.effect_type,
                        damage=0,
                        expired=True,
                        remaining_duration=0,
                        message=msg,
                    ))
                else:
                    msg = f"{pokemon.display_name}'s {eff.effect_type.display_name} has {eff.remaining_duration} turn(s) remaining."
                    records.append(EndOfTurnEffectRecord(
                        effect_type=eff.effect_type,
                        damage=0,
                        expired=False,
                        remaining_duration=eff.remaining_duration,
                        message=msg,
                    ))

        # Re-save active effects
        self._effects[pokemon.unique_id] = active

        summary_parts = [r.message for r in records]
        summary = " | ".join(summary_parts) if summary_parts else f"{pokemon.display_name} has no end-of-turn effects."

        return EndOfTurnResult(
            pokemon=pokemon,
            damage_taken=total_damage,
            fainted=pokemon.is_fainted,
            effects_processed=tuple(records),
            expired_effects=tuple(expired_list),
            reason=summary,
        )

    def remove_effect(self, pokemon: Pokemon, effect_type: StatusEffectType) -> bool:
        """
        Removes all active effects of the given type from the Pokemon.
        Returns True if at least one effect was removed, False otherwise.
        """
        if not isinstance(pokemon, Pokemon) or not isinstance(effect_type, StatusEffectType):
            return False

        active = self._effects.get(pokemon.unique_id, [])
        initial_count = len(active)
        self._effects[pokemon.unique_id] = [eff for eff in active if eff.effect_type != effect_type]

        if hasattr(pokemon, "remove_status_effect"):
            pokemon.remove_status_effect(effect_type)

        return len(self._effects[pokemon.unique_id]) < initial_count

    def clear_effects(self, pokemon: Pokemon) -> None:
        """Clears all active status effects from the Pokemon."""
        if not isinstance(pokemon, Pokemon):
            return
        if pokemon.unique_id in self._effects:
            self._effects[pokemon.unique_id].clear()
        if hasattr(pokemon, "clear_status_effects"):
            pokemon.clear_status_effects()

    def cure_major_condition(self, pokemon: Pokemon, condition: StatusEffectType) -> bool:
        """
        Cures a specific major condition (burn, poison, paralysis) from the Pokemon.
        Leaves unrelated temporary stat reductions intact.
        Returns True if the condition was removed, False if not present.
        """
        if not isinstance(condition, StatusEffectType) or not condition.is_major_condition:
            return False
        return self.remove_effect(pokemon, condition)

    def cure_all_major_conditions(self, pokemon: Pokemon) -> list[StatusEffectType]:
        """
        Cures all major persistent conditions (burn, poison, paralysis) currently active on the Pokemon.
        Leaves unrelated temporary stat reductions intact.
        Returns a list of cured StatusEffectType instances.
        """
        if not isinstance(pokemon, Pokemon):
            return []
        cured: list[StatusEffectType] = []
        for condition in (StatusEffectType.BURN, StatusEffectType.POISON, StatusEffectType.PARALYSIS):
            if self.has_effect(pokemon, condition):
                if self.remove_effect(pokemon, condition):
                    cured.append(condition)
        return cured

