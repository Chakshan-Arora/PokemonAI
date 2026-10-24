"""
Predefined sample attacks for Pokémon species.
"""
from src.models.pokemon_type import PokemonType
from src.models.attack import Attack

TACKLE = Attack(
    name="Tackle",
    type=PokemonType.NORMAL,
    power=40,
    accuracy=100,
)

QUICK_ATTACK = Attack(
    name="Quick Attack",
    type=PokemonType.NORMAL,
    power=40,
    accuracy=100,
)

SCRATCH = Attack(
    name="Scratch",
    type=PokemonType.NORMAL,
    power=40,
    accuracy=100,
)

THUNDER_SHOCK = Attack(
    name="Thunder Shock",
    type=PokemonType.ELECTRIC,
    power=40,
    accuracy=100,
)

THUNDERBOLT = Attack(
    name="Thunderbolt",
    type=PokemonType.ELECTRIC,
    power=90,
    accuracy=100,
)

EMBER = Attack(
    name="Ember",
    type=PokemonType.FIRE,
    power=40,
    accuracy=100,
)

FLAMETHROWER = Attack(
    name="Flamethrower",
    type=PokemonType.FIRE,
    power=90,
    accuracy=100,
)

WATER_GUN = Attack(
    name="Water Gun",
    type=PokemonType.WATER,
    power=40,
    accuracy=100,
)

HYDRO_PUMP = Attack(
    name="Hydro Pump",
    type=PokemonType.WATER,
    power=110,
    accuracy=80,
)

VINE_WHIP = Attack(
    name="Vine Whip",
    type=PokemonType.GRASS,
    power=45,
    accuracy=100,
)

# --- Attacks with Move Effects ---

from src.models.status_effect import (
    AttackEffect,
    StatusEffectType,
    DEFAULT_PARALYSIS_CHANCE,
    DEFAULT_STAT_REDUCTION_DURATION,
    DEFAULT_STAT_REDUCTION_MULTIPLIER,
)

WILL_O_WISP = Attack(
    name="Will-O-Wisp",
    type=PokemonType.FIRE,
    power=0,
    accuracy=100,
    effect=AttackEffect(
        effect_type=StatusEffectType.BURN,
        chance=100,
    ),
)

FIRE_FANG = Attack(
    name="Fire Fang",
    type=PokemonType.FIRE,
    power=65,
    accuracy=100,
    effect=AttackEffect(
        effect_type=StatusEffectType.BURN,
        chance=20,
    ),
)

POISON_POWDER = Attack(
    name="Poison Powder",
    type=PokemonType.GRASS,
    power=0,
    accuracy=100,
    effect=AttackEffect(
        effect_type=StatusEffectType.POISON,
        chance=100,
    ),
)

POISON_STING = Attack(
    name="Poison Sting",
    type=PokemonType.NORMAL,
    power=15,
    accuracy=100,
    effect=AttackEffect(
        effect_type=StatusEffectType.POISON,
        chance=30,
    ),
)

THUNDER_WAVE = Attack(
    name="Thunder Wave",
    type=PokemonType.ELECTRIC,
    power=0,
    accuracy=100,
    effect=AttackEffect(
        effect_type=StatusEffectType.PARALYSIS,
        chance=100,
        paralysis_chance=DEFAULT_PARALYSIS_CHANCE,
    ),
)

SPARK = Attack(
    name="Spark",
    type=PokemonType.ELECTRIC,
    power=65,
    accuracy=100,
    effect=AttackEffect(
        effect_type=StatusEffectType.PARALYSIS,
        chance=30,
        paralysis_chance=DEFAULT_PARALYSIS_CHANCE,
    ),
)

GROWL = Attack(
    name="Growl",
    type=PokemonType.NORMAL,
    power=0,
    accuracy=100,
    effect=AttackEffect(
        effect_type=StatusEffectType.ATTACK_REDUCTION,
        chance=100,
        duration=DEFAULT_STAT_REDUCTION_DURATION,
        multiplier=DEFAULT_STAT_REDUCTION_MULTIPLIER,
    ),
)

TAIL_WHIP = Attack(
    name="Tail Whip",
    type=PokemonType.NORMAL,
    power=0,
    accuracy=100,
    effect=AttackEffect(
        effect_type=StatusEffectType.DEFENSE_REDUCTION,
        chance=100,
        duration=DEFAULT_STAT_REDUCTION_DURATION,
        multiplier=DEFAULT_STAT_REDUCTION_MULTIPLIER,
    ),
)

LEER = Attack(
    name="Leer",
    type=PokemonType.NORMAL,
    power=0,
    accuracy=100,
    effect=AttackEffect(
        effect_type=StatusEffectType.DEFENSE_REDUCTION,
        chance=100,
        duration=DEFAULT_STAT_REDUCTION_DURATION,
        multiplier=DEFAULT_STAT_REDUCTION_MULTIPLIER,
    ),
)

RAZOR_LEAF = Attack(
    name="Razor Leaf",
    type=PokemonType.GRASS,
    power=55,
    accuracy=95,
)

SOLAR_BEAM = Attack(
    name="Solar Beam",
    type=PokemonType.GRASS,
    power=120,
    accuracy=100,
)

SLUDGE = Attack(
    name="Sludge",
    type=PokemonType.POISON,
    power=65,
    accuracy=100,
    effect=AttackEffect(
        effect_type=StatusEffectType.POISON,
        chance=30,
    ),
)

GUST = Attack(
    name="Gust",
    type=PokemonType.FLYING,
    power=40,
    accuracy=100,
)

WING_ATTACK = Attack(
    name="Wing Attack",
    type=PokemonType.FLYING,
    power=60,
    accuracy=100,
)

BITE = Attack(
    name="Bite",
    type=PokemonType.NORMAL,
    power=60,
    accuracy=100,
)

HYPER_FANG = Attack(
    name="Hyper Fang",
    type=PokemonType.NORMAL,
    power=80,
    accuracy=90,
)

HEADBUTT = Attack(
    name="Headbutt",
    type=PokemonType.NORMAL,
    power=70,
    accuracy=100,
)

BODY_SLAM = Attack(
    name="Body Slam",
    type=PokemonType.NORMAL,
    power=85,
    accuracy=100,
    effect=AttackEffect(
        effect_type=StatusEffectType.PARALYSIS,
        chance=30,
        paralysis_chance=DEFAULT_PARALYSIS_CHANCE,
    ),
)

BUG_BITE = Attack(
    name="Bug Bite",
    type=PokemonType.BUG,
    power=60,
    accuracy=100,
)

LEECH_LIFE = Attack(
    name="Leech Life",
    type=PokemonType.BUG,
    power=20,
    accuracy=100,
)

ROCK_THROW = Attack(
    name="Rock Throw",
    type=PokemonType.ROCK,
    power=50,
    accuracy=90,
)

ROCK_SLIDE = Attack(
    name="Rock Slide",
    type=PokemonType.ROCK,
    power=75,
    accuracy=90,
)

DEFENSE_CURL = Attack(
    name="Defense Curl",
    type=PokemonType.NORMAL,
    power=0,
    accuracy=100,
)

CONFUSE_RAY = Attack(
    name="Confuse Ray",
    type=PokemonType.GHOST,
    power=0,
    accuracy=100,
)

LOW_KICK = Attack(
    name="Low Kick",
    type=PokemonType.FIGHTING,
    power=50,
    accuracy=100,
)

KARATE_CHOP = Attack(
    name="Karate Chop",
    type=PokemonType.FIGHTING,
    power=50,
    accuracy=100,
)

BRICK_BREAK = Attack(
    name="Brick Break",
    type=PokemonType.FIGHTING,
    power=75,
    accuracy=100,
)

LICK = Attack(
    name="Lick",
    type=PokemonType.GHOST,
    power=30,
    accuracy=100,
    effect=AttackEffect(
        effect_type=StatusEffectType.PARALYSIS,
        chance=30,
        paralysis_chance=DEFAULT_PARALYSIS_CHANCE,
    ),
)

NIGHT_SHADE = Attack(
    name="Night Shade",
    type=PokemonType.GHOST,
    power=50,
    accuracy=100,
)

SHADOW_BALL = Attack(
    name="Shadow Ball",
    type=PokemonType.GHOST,
    power=80,
    accuracy=100,
)

CONFUSION = Attack(
    name="Confusion",
    type=PokemonType.PSYCHIC,
    power=50,
    accuracy=100,
)

PSYBEAM = Attack(
    name="Psybeam",
    type=PokemonType.PSYCHIC,
    power=65,
    accuracy=100,
)

PSYCHIC_ATTACK = Attack(
    name="Psychic",
    type=PokemonType.PSYCHIC,
    power=90,
    accuracy=100,
)

FLAME_WHEEL = Attack(
    name="Flame Wheel",
    type=PokemonType.FIRE,
    power=60,
    accuracy=100,
    effect=AttackEffect(
        effect_type=StatusEffectType.BURN,
        chance=10,
    ),
)

BUBBLE = Attack(
    name="Bubble",
    type=PokemonType.WATER,
    power=40,
    accuracy=100,
)

SAMPLE_ATTACKS: dict[str, Attack] = {
    "Tackle": TACKLE,
    "Quick Attack": QUICK_ATTACK,
    "Scratch": SCRATCH,
    "Thunder Shock": THUNDER_SHOCK,
    "Thunderbolt": THUNDERBOLT,
    "Ember": EMBER,
    "Flamethrower": FLAMETHROWER,
    "Water Gun": WATER_GUN,
    "Hydro Pump": HYDRO_PUMP,
    "Vine Whip": VINE_WHIP,
    "Will-O-Wisp": WILL_O_WISP,
    "Fire Fang": FIRE_FANG,
    "Poison Powder": POISON_POWDER,
    "Poison Sting": POISON_STING,
    "Thunder Wave": THUNDER_WAVE,
    "Spark": SPARK,
    "Growl": GROWL,
    "Tail Whip": TAIL_WHIP,
    "Leer": LEER,
    "Razor Leaf": RAZOR_LEAF,
    "Solar Beam": SOLAR_BEAM,
    "Sludge": SLUDGE,
    "Gust": GUST,
    "Wing Attack": WING_ATTACK,
    "Bite": BITE,
    "Hyper Fang": HYPER_FANG,
    "Headbutt": HEADBUTT,
    "Body Slam": BODY_SLAM,
    "Bug Bite": BUG_BITE,
    "Leech Life": LEECH_LIFE,
    "Rock Throw": ROCK_THROW,
    "Rock Slide": ROCK_SLIDE,
    "Defense Curl": DEFENSE_CURL,
    "Confuse Ray": CONFUSE_RAY,
    "Low Kick": LOW_KICK,
    "Karate Chop": KARATE_CHOP,
    "Brick Break": BRICK_BREAK,
    "Lick": LICK,
    "Night Shade": NIGHT_SHADE,
    "Shadow Ball": SHADOW_BALL,
    "Confusion": CONFUSION,
    "Psybeam": PSYBEAM,
    "Psychic": PSYCHIC_ATTACK,
    "Flame Wheel": FLAME_WHEEL,
    "Bubble": BUBBLE,
}
