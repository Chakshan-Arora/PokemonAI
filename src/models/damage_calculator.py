"""
Damage calculator for Pokemon battles.
"""
from dataclasses import dataclass
import random
from typing import Optional
from src.models.pokemon import Pokemon
from src.models.attack import Attack


@dataclass(frozen=True)
class DamageResult:
    damage: int
    is_critical: bool
    bond_multiplier: float
    random_factor: float
    type_effectiveness: float

    def __int__(self) -> int:
        return self.damage


def calculate_damage(
    attacker: Pokemon,
    defender: Pokemon,
    attack: Attack,
    type_effectiveness: float = 1.0,
    rng: Optional[random.Random] = None,
    use_random_factor: bool = True,
    status_manager: Optional[object] = None,
    bond: int = 0,
    use_critical: bool = True,
) -> DamageResult:
    """
    Calculates the damage dealt by an attack against a defending Pokemon.

    Formula:
      level_factor = (2 * attacker.level / 5) + 2
      stat_ratio   = effective_attack / (effective_defense * 35)
      base_damage  = (level_factor * attack.power * stat_ratio) + 2
      stab_multiplier = 1.15 if attack.type in attacker.species types else 1.0
      random_factor = rng.uniform(0.85, 1.0) if (use_random_factor and rng) else 1.0
      bond_multiplier = 1.0 + (bond / 100.0) * 0.15
      crit_multiplier = 1.5 if is_critical else 1.0
      damage       = base_damage * type_effectiveness * stab_multiplier * random_factor * bond_multiplier * crit_multiplier

    Constraints:
      - Returns 0 damage if type_effectiveness <= 0.0 (immunity) or attack.power <= 0.
      - Guarantees minimum 1 damage for damaging moves with positive effectiveness.
      - Damage is never negative.
      - Returns DamageResult dataclass.
    """
    if not isinstance(attacker, Pokemon):
        raise TypeError(f"attacker must be a Pokemon, got {type(attacker).__name__}.")
    if not isinstance(defender, Pokemon):
        raise TypeError(f"defender must be a Pokemon, got {type(defender).__name__}.")
    if not isinstance(attack, Attack):
        raise TypeError(f"attack must be an Attack, got {type(attack).__name__}.")

    safe_bond = max(0, min(100, int(bond)))
    bond_multiplier = 1.0 + (safe_bond / 100.0) * 0.15

    # Immunity or non-damaging move
    if type_effectiveness <= 0.0 or attack.power <= 0:
        return DamageResult(
            damage=0,
            is_critical=False,
            bond_multiplier=bond_multiplier,
            random_factor=1.0,
            type_effectiveness=type_effectiveness,
        )

    if status_manager is not None and hasattr(status_manager, "get_effective_stat"):
        attack_stat = status_manager.get_effective_stat(attacker, "attack")
        defense_stat = max(1, status_manager.get_effective_stat(defender, "defense"))
    else:
        attack_stat = getattr(attacker, "effective_attack", getattr(attacker, "attack", attacker.species.base_attack))
        defense_stat = max(1, getattr(defender, "effective_defense", getattr(defender, "defense", defender.species.base_defense)))

    level_factor = ((2.0 * attacker.level) / 5.0) + 2.0
    stat_ratio = attack_stat / (defense_stat * 35.0)
    base_damage = (level_factor * attack.power * stat_ratio) + 2.0

    # STAB (Same-Type Attack Bonus) - 1.15x multiplier if attack type matches attacker species types
    attacker_types = getattr(attacker.species, "types", (attacker.species.primary_type,))
    stab_multiplier = 1.15 if attack.type in attacker_types else 1.0

    # Random factor (0.85 - 1.00)
    if use_random_factor and rng is not None:
        random_factor = rng.uniform(0.85, 1.0)
    else:
        random_factor = 1.0

    # Critical hit: 6.25% base chance, +0.05% per bond point (max ~11.25% at bond 100)
    critical_multiplier = 1.0
    is_critical = False
    if use_critical and rng is not None:
        crit_chance = 0.0625 + (safe_bond / 100.0) * 0.05
        if rng.random() < crit_chance:
            critical_multiplier = 1.5
            is_critical = True

    total = base_damage * type_effectiveness * stab_multiplier * random_factor * bond_multiplier * critical_multiplier
    total_damage = max(1, int(total))

    return DamageResult(
        damage=total_damage,
        is_critical=is_critical,
        bond_multiplier=bond_multiplier,
        random_factor=random_factor,
        type_effectiveness=type_effectiveness,
    )
