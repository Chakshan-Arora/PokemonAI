"""
Personality generator for wild Pokemon instances.
"""
import random
from typing import Optional
from src.models.personality import Personality


def generate_wild_personality(
    rng: Optional[random.Random] = None,
    seed: Optional[int] = None,
    **overrides: int,
) -> Personality:
    """
    Generates a randomized Personality with traits in the 0-100 range.
    Accepts an injected Random generator or seed for deterministic reproducibility.
    Allows specific trait overrides if needed.
    """
    if rng is None:
        if seed is not None:
            rng = random.Random(seed)
        else:
            rng = random.Random()

    traits = {
        "aggression": rng.randint(0, 100),
        "curiosity": rng.randint(0, 100),
        "fear": rng.randint(0, 100),
        "sociability": rng.randint(0, 100),
        "loyalty": rng.randint(0, 100),
        "confidence": rng.randint(0, 100),
    }

    # Apply any specific overrides
    for key, val in overrides.items():
        if key in traits:
            traits[key] = val

    return Personality(**traits)


class PersonalityGenerator:
    """
    Stateful generator for wild Pokemon personalities supporting an injectable RNG.
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

    def generate(self, **overrides: int) -> Personality:
        """Generates a new random Personality using the configured RNG."""
        return generate_wild_personality(rng=self._rng, **overrides)
