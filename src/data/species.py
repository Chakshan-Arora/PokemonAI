"""
Predefined sample Pokémon species definitions.
"""
from src.models.pokemon_type import PokemonType
from src.models.species import PokemonSpecies
from src.data.attacks import (
    THUNDER_SHOCK,
    QUICK_ATTACK,
    THUNDERBOLT,
    SCRATCH,
    EMBER,
    FLAMETHROWER,
    TACKLE,
    WATER_GUN,
    HYDRO_PUMP,
    VINE_WHIP,
    RAZOR_LEAF,
    SOLAR_BEAM,
    POISON_POWDER,
    SLUDGE,
    GUST,
    WING_ATTACK,
    BITE,
    HYPER_FANG,
    HEADBUTT,
    BODY_SLAM,
    BUG_BITE,
    LEECH_LIFE,
    ROCK_THROW,
    ROCK_SLIDE,
    DEFENSE_CURL,
    CONFUSE_RAY,
    LOW_KICK,
    KARATE_CHOP,
    BRICK_BREAK,
    LICK,
    NIGHT_SHADE,
    SHADOW_BALL,
    CONFUSION,
    PSYBEAM,
    PSYCHIC_ATTACK,
    FLAME_WHEEL,
    BUBBLE,
    FIRE_FANG,
    SPARK,
)
from src.data.abilities import (
    STATIC,
    LIGHTNING_ROD,
    BLAZE,
    TORRENT,
    OVERGROW,
    KEEN_EYE,
    RUN_AWAY,
    SHIELD_DUST,
    COMPOUND_EYES,
    ROCK_HEAD,
    INNER_FOCUS,
    GUTS,
    LEVITATE,
    SYNCHRONIZE,
    ADAPTABILITY,
    INTIMIDATE,
    WATER_ABSORB,
)

# 1. Bulbasaur - Grass/Poison Starter
BULBASAUR = PokemonSpecies(
    name="Bulbasaur",
    primary_type=PokemonType.GRASS,
    secondary_type=PokemonType.POISON,
    base_hp=14,
    base_attack=49,
    base_defense=49,
    base_speed=45,
    available_attacks=(TACKLE, VINE_WHIP, POISON_POWDER),
    abilities=(OVERGROW,),
)

# 2. Charmander - Fire Starter
CHARMANDER = PokemonSpecies(
    name="Charmander",
    primary_type=PokemonType.FIRE,
    base_hp=12,
    base_attack=52,
    base_defense=43,
    base_speed=65,
    available_attacks=(SCRATCH, EMBER),
    abilities=(BLAZE,),
)

# 3. Squirtle - Water Starter
SQUIRTLE = PokemonSpecies(
    name="Squirtle",
    primary_type=PokemonType.WATER,
    base_hp=13,
    base_attack=48,
    base_defense=65,
    base_speed=43,
    available_attacks=(TACKLE, WATER_GUN),
    abilities=(TORRENT,),
)

# 4. Pikachu - Electric
PIKACHU = PokemonSpecies(
    name="Pikachu",
    primary_type=PokemonType.ELECTRIC,
    base_hp=11,
    base_attack=55,
    base_defense=40,
    base_speed=90,
    available_attacks=(THUNDER_SHOCK, QUICK_ATTACK),
    abilities=(STATIC, LIGHTNING_ROD),
)

# 5. Pidgey - Normal/Flying
PIDGEY = PokemonSpecies(
    name="Pidgey",
    primary_type=PokemonType.NORMAL,
    secondary_type=PokemonType.FLYING,
    base_hp=12,
    base_attack=45,
    base_defense=40,
    base_speed=56,
    available_attacks=(TACKLE, GUST),
    abilities=(KEEN_EYE,),
)

# 6. Rattata - Normal
RATTATA = PokemonSpecies(
    name="Rattata",
    primary_type=PokemonType.NORMAL,
    base_hp=10,
    base_attack=56,
    base_defense=35,
    base_speed=72,
    available_attacks=(TACKLE, QUICK_ATTACK),
    abilities=(RUN_AWAY,),
)

# 7. Caterpie - Bug
CATERPIE = PokemonSpecies(
    name="Caterpie",
    primary_type=PokemonType.BUG,
    base_hp=12,
    base_attack=30,
    base_defense=35,
    base_speed=45,
    available_attacks=(TACKLE, BUG_BITE),
    abilities=(SHIELD_DUST,),
)

# 8. Butterfree - Bug/Flying
BUTTERFREE = PokemonSpecies(
    name="Butterfree",
    primary_type=PokemonType.BUG,
    secondary_type=PokemonType.FLYING,
    base_hp=16,
    base_attack=45,
    base_defense=50,
    base_speed=70,
    available_attacks=(GUST, CONFUSION, POISON_POWDER),
    abilities=(COMPOUND_EYES,),
)

# 9. Geodude - Rock/Ground
GEODUDE = PokemonSpecies(
    name="Geodude",
    primary_type=PokemonType.ROCK,
    secondary_type=PokemonType.GROUND,
    base_hp=12,
    base_attack=80,
    base_defense=100,
    base_speed=20,
    available_attacks=(TACKLE, ROCK_THROW, ROCK_SLIDE),
    abilities=(ROCK_HEAD,),
)

# 10. Zubat - Poison/Flying
ZUBAT = PokemonSpecies(
    name="Zubat",
    primary_type=PokemonType.POISON,
    secondary_type=PokemonType.FLYING,
    base_hp=11,
    base_attack=45,
    base_defense=35,
    base_speed=55,
    available_attacks=(LEECH_LIFE, BITE, WING_ATTACK),
    abilities=(INNER_FOCUS,),
)

# 11. Machop - Fighting
MACHOP = PokemonSpecies(
    name="Machop",
    primary_type=PokemonType.FIGHTING,
    base_hp=18,
    base_attack=80,
    base_defense=50,
    base_speed=35,
    available_attacks=(LOW_KICK, KARATE_CHOP, TACKLE, BRICK_BREAK),
    abilities=(GUTS,),
)

# 12. Gastly - Ghost/Poison
GASTLY = PokemonSpecies(
    name="Gastly",
    primary_type=PokemonType.GHOST,
    secondary_type=PokemonType.POISON,
    base_hp=10,
    base_attack=35,
    base_defense=30,
    base_speed=80,
    available_attacks=(LICK, NIGHT_SHADE, SHADOW_BALL),
    abilities=(LEVITATE,),
)

# 13. Abra - Psychic
ABRA = PokemonSpecies(
    name="Abra",
    primary_type=PokemonType.PSYCHIC,
    base_hp=8,
    base_attack=20,
    base_defense=15,
    base_speed=90,
    available_attacks=(TACKLE, CONFUSION, PSYBEAM, PSYCHIC_ATTACK),
    abilities=(SYNCHRONIZE,),
)

# 14. Eevee - Normal
EEVEE = PokemonSpecies(
    name="Eevee",
    primary_type=PokemonType.NORMAL,
    base_hp=14,
    base_attack=55,
    base_defense=50,
    base_speed=55,
    available_attacks=(TACKLE, QUICK_ATTACK, BITE, BODY_SLAM),
    abilities=(ADAPTABILITY, RUN_AWAY),
)

# 15. Growlithe - Fire
GROWLITHE = PokemonSpecies(
    name="Growlithe",
    primary_type=PokemonType.FIRE,
    base_hp=14,
    base_attack=70,
    base_defense=45,
    base_speed=60,
    available_attacks=(BITE, EMBER, FLAME_WHEEL, FLAMETHROWER),
    abilities=(INTIMIDATE,),
)

# 16. Poliwag - Water
POLIWAG = PokemonSpecies(
    name="Poliwag",
    primary_type=PokemonType.WATER,
    base_hp=12,
    base_attack=50,
    base_defense=40,
    base_speed=90,
    available_attacks=(WATER_GUN, BUBBLE, BODY_SLAM, HYDRO_PUMP),
    abilities=(WATER_ABSORB,),
)

SAMPLE_SPECIES: dict[str, PokemonSpecies] = {
    "Pikachu": PIKACHU,
    "Charmander": CHARMANDER,
    "Squirtle": SQUIRTLE,
    "Bulbasaur": BULBASAUR,
    "Pidgey": PIDGEY,
    "Rattata": RATTATA,
    "Caterpie": CATERPIE,
    "Butterfree": BUTTERFREE,
    "Geodude": GEODUDE,
    "Zubat": ZUBAT,
    "Machop": MACHOP,
    "Gastly": GASTLY,
    "Abra": ABRA,
    "Eevee": EEVEE,
    "Growlithe": GROWLITHE,
    "Poliwag": POLIWAG,
}
