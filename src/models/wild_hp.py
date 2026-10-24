"""
Wild Pokémon initial HP generation model.
Provides natural health distribution for wild Pokémon encounters:
  - Full HP (~50% chance)
  - Lightly wounded (70% - 90% HP, ~35% chance)
  - Severely wounded (20% - 30% HP, ~15% chance)
"""
import random
from typing import Optional


def determine_wild_hp(
    max_hp: int,
    rng: Optional[random.Random] = None,
    tier_override: Optional[str] = None,
) -> int:
    """
    Calculates initial HP for a wild Pokémon based on natural health distribution:
      - 'full': 100% of max_hp.
      - 'lightly_wounded': Random fraction between 70% and 90% of max_hp.
      - 'critically_wounded': Random fraction between 20% and 30% of max_hp.

    Args:
        max_hp: Maximum hit points of the Pokémon (must be positive).
        rng: Optional injected random.Random generator for deterministic evaluation.
        tier_override: Optional explicit tier string ('full', 'lightly_wounded', 'critically_wounded').

    Returns:
        Integer current HP value, guaranteed to be in range [1, max_hp].
    """
    if not isinstance(max_hp, int) or isinstance(max_hp, bool):
        raise TypeError(f"max_hp must be an integer, got {type(max_hp).__name__}.")
    if max_hp < 1:
        raise ValueError(f"max_hp must be at least 1, got {max_hp}.")

    if max_hp == 1:
        return 1

    r = rng if rng is not None else random.Random()

    tier = tier_override.strip().lower() if tier_override is not None else None
    if tier is None:
        roll = r.random()
        if roll < 0.50:
            tier = "full"
        elif roll < 0.85:
            tier = "lightly_wounded"
        else:
            tier = "critically_wounded"

    if tier == "full":
        return max_hp
    elif tier == "lightly_wounded":
        fraction = r.uniform(0.70, 0.90)
        calculated = int(round(max_hp * fraction))
        return max(1, min(max_hp, calculated))
    elif tier == "critically_wounded":
        fraction = r.uniform(0.20, 0.30)
        calculated = int(round(max_hp * fraction))
        return max(1, min(max_hp, calculated))
    else:
        raise ValueError(
            f"Unknown tier_override '{tier_override}'. Expected 'full', 'lightly_wounded', or 'critically_wounded'."
        )
