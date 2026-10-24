"""
Predefined sample abilities for Pokémon species.
"""
from src.models.ability import Ability

STATIC = Ability(
    name="Static",
    description="Contact with the Pokemon may cause paralysis.",
)

BLAZE = Ability(
    name="Blaze",
    description="Powers up Fire-type moves when the Pokemon is in trouble.",
)

TORRENT = Ability(
    name="Torrent",
    description="Powers up Water-type moves when the Pokemon is in trouble.",
)

OVERGROW = Ability(
    name="Overgrow",
    description="Powers up Grass-type moves when the Pokemon is in trouble.",
)

LIGHTNING_ROD = Ability(
    name="Lightning Rod",
    description="Draws in and grounds Electric-type moves.",
)

KEEN_EYE = Ability(
    name="Keen Eye",
    description="Prevents loss of accuracy.",
)

RUN_AWAY = Ability(
    name="Run Away",
    description="Enables a sure getaway from wild battles.",
)

SHIELD_DUST = Ability(
    name="Shield Dust",
    description="Blocks the added effects of attacks taken.",
)

COMPOUND_EYES = Ability(
    name="Compound Eyes",
    description="Boosts accuracy.",
)

ROCK_HEAD = Ability(
    name="Rock Head",
    description="Protects the Pokemon from recoil damage.",
)

INNER_FOCUS = Ability(
    name="Inner Focus",
    description="Prevents flinching.",
)

GUTS = Ability(
    name="Guts",
    description="Boosts Attack if the Pokemon has a status condition.",
)

LEVITATE = Ability(
    name="Levitate",
    description="Gives immunity to Ground-type attacks.",
)

SYNCHRONIZE = Ability(
    name="Synchronize",
    description="Passes a status condition to the foe.",
)

ADAPTABILITY = Ability(
    name="Adaptability",
    description="Powers up moves of the same type.",
)

INTIMIDATE = Ability(
    name="Intimidate",
    description="Lowers the opposing Pokemon's Attack stat.",
)

WATER_ABSORB = Ability(
    name="Water Absorb",
    description="Restores HP if hit by a Water-type move.",
)

SAMPLE_ABILITIES: dict[str, Ability] = {
    "Static": STATIC,
    "Blaze": BLAZE,
    "Torrent": TORRENT,
    "Overgrow": OVERGROW,
    "Lightning Rod": LIGHTNING_ROD,
    "Keen Eye": KEEN_EYE,
    "Run Away": RUN_AWAY,
    "Shield Dust": SHIELD_DUST,
    "Compound Eyes": COMPOUND_EYES,
    "Rock Head": ROCK_HEAD,
    "Inner Focus": INNER_FOCUS,
    "Guts": GUTS,
    "Levitate": LEVITATE,
    "Synchronize": SYNCHRONIZE,
    "Adaptability": ADAPTABILITY,
    "Intimidate": INTIMIDATE,
    "Water Absorb": WATER_ABSORB,
}
