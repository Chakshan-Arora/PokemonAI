"""
Static catalog of habitats and wild Pokemon spawn candidates.
Defines predefined habitats mapped to world regions and time-of-day distributions.
"""
from typing import Optional
from src.models.habitat import Habitat, SpawnCandidate, TimeOfDay, Rarity
from src.data.species import (
    PIKACHU,
    CHARMANDER,
    SQUIRTLE,
    BULBASAUR,
    PIDGEY,
    RATTATA,
    CATERPIE,
    BUTTERFREE,
    GEODUDE,
    ZUBAT,
    MACHOP,
    GASTLY,
    ABRA,
    EEVEE,
    GROWLITHE,
    POLIWAG,
)


# 1. Meadow Habitat (associated with 'starting_meadow')
# Sunny open fields populated by diurnal electric and woodland Pokemon
MEADOW_HABITAT = Habitat(
    habitat_id="meadow",
    name="Sunny Meadow",
    description="A vibrant sunlit meadow where diurnal Pokemon forage and play.",
    region_ids=("starting_meadow",),
    candidates=(
        SpawnCandidate(
            species=PIDGEY,
            weight=60.0,
            allowed_times=(TimeOfDay.MORNING, TimeOfDay.DAY),
            min_level=2,
            max_level=4,
            rarity=Rarity.COMMON,
        ),
        SpawnCandidate(
            species=RATTATA,
            weight=55.0,
            allowed_times=(TimeOfDay.MORNING, TimeOfDay.DAY, TimeOfDay.EVENING),
            min_level=2,
            max_level=4,
            rarity=Rarity.COMMON,
        ),
        SpawnCandidate(
            species=CATERPIE,
            weight=50.0,
            allowed_times=(TimeOfDay.MORNING, TimeOfDay.DAY),
            min_level=2,
            max_level=3,
            rarity=Rarity.COMMON,
        ),
        SpawnCandidate(
            species=PIKACHU,
            weight=40.0,
            allowed_times=(TimeOfDay.MORNING, TimeOfDay.DAY),
            min_level=2,
            max_level=4,
            rarity=Rarity.UNCOMMON,
        ),
        SpawnCandidate(
            species=EEVEE,
            weight=15.0,
            allowed_times=(TimeOfDay.DAY, TimeOfDay.EVENING),
            min_level=3,
            max_level=5,
            rarity=Rarity.RARE,
        ),
        SpawnCandidate(
            species=BULBASAUR,
            weight=20.0,
            allowed_times=(TimeOfDay.MORNING, TimeOfDay.DAY),
            min_level=3,
            max_level=5,
            rarity=Rarity.UNCOMMON,
        ),
        SpawnCandidate(
            species=POLIWAG,
            weight=25.0,
            allowed_times=(TimeOfDay.DAY, TimeOfDay.EVENING),
            min_level=2,
            max_level=4,
            rarity=Rarity.UNCOMMON,
        ),
        SpawnCandidate(
            species=SQUIRTLE,
            weight=15.0,
            allowed_times=(TimeOfDay.DAY, TimeOfDay.EVENING),
            min_level=3,
            max_level=5,
            rarity=Rarity.RARE,
        ),
    ),
)

# 2. Forest Habitat (associated with 'forest_trail')
# Dense canopy sustaining wild Pokemon across all daylight and twilight hours
FOREST_HABITAT = Habitat(
    habitat_id="forest",
    name="Temperate Forest",
    description="Dense shaded woodlands harboring curious Pokemon under leafy canopies.",
    region_ids=("forest_trail",),
    candidates=(
        SpawnCandidate(
            species=PIDGEY,
            weight=45.0,
            allowed_times=(TimeOfDay.MORNING, TimeOfDay.DAY, TimeOfDay.EVENING),
            min_level=3,
            max_level=5,
            rarity=Rarity.COMMON,
        ),
        SpawnCandidate(
            species=CATERPIE,
            weight=40.0,
            allowed_times=(TimeOfDay.MORNING, TimeOfDay.DAY),
            min_level=3,
            max_level=4,
            rarity=Rarity.COMMON,
        ),
        SpawnCandidate(
            species=ZUBAT,
            weight=45.0,
            allowed_times=(TimeOfDay.EVENING, TimeOfDay.NIGHT),
            min_level=3,
            max_level=5,
            rarity=Rarity.COMMON,
        ),
        SpawnCandidate(
            species=PIKACHU,
            weight=35.0,
            allowed_times=(TimeOfDay.MORNING, TimeOfDay.DAY, TimeOfDay.EVENING),
            min_level=3,
            max_level=5,
            rarity=Rarity.UNCOMMON,
        ),
        SpawnCandidate(
            species=CHARMANDER,
            weight=30.0,
            allowed_times=(TimeOfDay.DAY, TimeOfDay.EVENING, TimeOfDay.NIGHT),
            min_level=3,
            max_level=5,
            rarity=Rarity.UNCOMMON,
        ),
        SpawnCandidate(
            species=BUTTERFREE,
            weight=15.0,
            allowed_times=(TimeOfDay.MORNING, TimeOfDay.DAY),
            min_level=5,
            max_level=7,
            rarity=Rarity.RARE,
        ),
        SpawnCandidate(
            species=ABRA,
            weight=10.0,
            allowed_times=(TimeOfDay.NIGHT,),
            min_level=4,
            max_level=6,
            rarity=Rarity.RARE,
        ),
        SpawnCandidate(
            species=MACHOP,
            weight=20.0,
            allowed_times=(TimeOfDay.DAY, TimeOfDay.EVENING),
            min_level=4,
            max_level=6,
            rarity=Rarity.UNCOMMON,
        ),
    ),
)

# 3. Shrine Grounds Habitat (associated with 'ancient_shrine_grounds')
# Sacred nocturnal plateau crackling with elemental energy
SHRINE_GROUNDS_HABITAT = Habitat(
    habitat_id="shrine_grounds",
    name="Ancient Shrine Grounds",
    description="Mysterious stone grounds where electric and fire spirits gather under twilight and stars.",
    region_ids=("ancient_shrine_grounds",),
    candidates=(
        SpawnCandidate(
            species=GEODUDE,
            weight=45.0,
            allowed_times=(TimeOfDay.DAY, TimeOfDay.EVENING),
            min_level=4,
            max_level=6,
            rarity=Rarity.COMMON,
        ),
        SpawnCandidate(
            species=ZUBAT,
            weight=40.0,
            allowed_times=(TimeOfDay.EVENING, TimeOfDay.NIGHT),
            min_level=4,
            max_level=6,
            rarity=Rarity.COMMON,
        ),
        SpawnCandidate(
            species=GASTLY,
            weight=30.0,
            allowed_times=(TimeOfDay.NIGHT,),
            min_level=5,
            max_level=7,
            rarity=Rarity.UNCOMMON,
        ),
        SpawnCandidate(
            species=GROWLITHE,
            weight=25.0,
            allowed_times=(TimeOfDay.DAY, TimeOfDay.EVENING),
            min_level=5,
            max_level=7,
            rarity=Rarity.UNCOMMON,
        ),
        SpawnCandidate(
            species=PIKACHU,
            weight=20.0,
            allowed_times=(TimeOfDay.EVENING, TimeOfDay.NIGHT),
            min_level=4,
            max_level=6,
            rarity=Rarity.UNCOMMON,
        ),
        SpawnCandidate(
            species=MACHOP,
            weight=20.0,
            allowed_times=(TimeOfDay.DAY, TimeOfDay.EVENING),
            min_level=5,
            max_level=7,
            rarity=Rarity.UNCOMMON,
        ),
        SpawnCandidate(
            species=CHARMANDER,
            weight=10.0,
            allowed_times=(TimeOfDay.NIGHT,),
            min_level=5,
            max_level=7,
            rarity=Rarity.RARE,
        ),
        SpawnCandidate(
            species=ABRA,
            weight=8.0,
            allowed_times=(TimeOfDay.NIGHT,),
            min_level=5,
            max_level=7,
            rarity=Rarity.RARE,
        ),
    ),
)

# 4. Mountain Pass Habitat (associated with 'mountain_pass')
MOUNTAIN_PASS_HABITAT = Habitat(
    habitat_id="mountain_pass",
    name="Mountain Pass",
    description="A rocky mountain path with exposed boulders and cliffs.",
    region_ids=("mountain_pass",),
    candidates=(
        SpawnCandidate(
            species=GEODUDE,
            weight=60.0,
            allowed_times=(TimeOfDay.DAY, TimeOfDay.EVENING),
            min_level=5,
            max_level=8,
            rarity=Rarity.COMMON,
        ),
        SpawnCandidate(
            species=MACHOP,
            weight=45.0,
            allowed_times=(TimeOfDay.DAY, TimeOfDay.EVENING),
            min_level=5,
            max_level=8,
            rarity=Rarity.COMMON,
        ),
        SpawnCandidate(
            species=ZUBAT,
            weight=35.0,
            allowed_times=(TimeOfDay.EVENING, TimeOfDay.NIGHT),
            min_level=5,
            max_level=7,
            rarity=Rarity.UNCOMMON,
        ),
        SpawnCandidate(
            species=GROWLITHE,
            weight=20.0,
            allowed_times=(TimeOfDay.DAY,),
            min_level=6,
            max_level=9,
            rarity=Rarity.UNCOMMON,
        ),
        SpawnCandidate(
            species=RATTATA,
            weight=30.0,
            allowed_times=(TimeOfDay.MORNING, TimeOfDay.DAY),
            min_level=4,
            max_level=6,
            rarity=Rarity.COMMON,
        ),
    ),
)

# 5. Crystal Lakeside Habitat (associated with 'lakeside')
LAKESIDE_HABITAT = Habitat(
    habitat_id="lakeside",
    name="Crystal Lakeside",
    description="A serene lake surrounded by tall reeds and rippling water.",
    region_ids=("lakeside",),
    candidates=(
        SpawnCandidate(
            species=POLIWAG,
            weight=60.0,
            allowed_times=(TimeOfDay.MORNING, TimeOfDay.DAY, TimeOfDay.EVENING),
            min_level=3,
            max_level=6,
            rarity=Rarity.COMMON,
        ),
        SpawnCandidate(
            species=SQUIRTLE,
            weight=35.0,
            allowed_times=(TimeOfDay.DAY, TimeOfDay.EVENING),
            min_level=4,
            max_level=7,
            rarity=Rarity.UNCOMMON,
        ),
        SpawnCandidate(
            species=PIDGEY,
            weight=30.0,
            allowed_times=(TimeOfDay.MORNING, TimeOfDay.DAY),
            min_level=3,
            max_level=5,
            rarity=Rarity.COMMON,
        ),
        SpawnCandidate(
            species=EEVEE,
            weight=10.0,
            allowed_times=(TimeOfDay.EVENING,),
            min_level=5,
            max_level=7,
            rarity=Rarity.RARE,
        ),
        SpawnCandidate(
            species=CATERPIE,
            weight=25.0,
            allowed_times=(TimeOfDay.MORNING,),
            min_level=3,
            max_level=4,
            rarity=Rarity.COMMON,
        ),
    ),
)

# 6. Haunted Ruins Habitat (associated with 'haunted_ruins')
HAUNTED_RUINS_HABITAT = Habitat(
    habitat_id="haunted_ruins",
    name="Haunted Ruins",
    description="Crumbling stone ruins where eerie lights flicker after dark.",
    region_ids=("haunted_ruins",),
    candidates=(
        SpawnCandidate(
            species=GASTLY,
            weight=60.0,
            allowed_times=(TimeOfDay.EVENING, TimeOfDay.NIGHT),
            min_level=5,
            max_level=8,
            rarity=Rarity.COMMON,
        ),
        SpawnCandidate(
            species=ZUBAT,
            weight=50.0,
            allowed_times=(TimeOfDay.EVENING, TimeOfDay.NIGHT),
            min_level=5,
            max_level=7,
            rarity=Rarity.COMMON,
        ),
        SpawnCandidate(
            species=ABRA,
            weight=20.0,
            allowed_times=(TimeOfDay.NIGHT,),
            min_level=6,
            max_level=9,
            rarity=Rarity.RARE,
        ),
        SpawnCandidate(
            species=RATTATA,
            weight=25.0,
            allowed_times=(TimeOfDay.DAY, TimeOfDay.EVENING),
            min_level=4,
            max_level=6,
            rarity=Rarity.UNCOMMON,
        ),
    ),
)

# 7. Tall Grass Plains Habitat (associated with 'tall_grass_plains')
PLAINS_HABITAT = Habitat(
    habitat_id="tall_grass_plains",
    name="Tall Grass Plains",
    description="Wide open grasslands where wild Pokémon roam freely.",
    region_ids=("tall_grass_plains",),
    candidates=(
        SpawnCandidate(
            species=RATTATA,
            weight=55.0,
            allowed_times=(TimeOfDay.MORNING, TimeOfDay.DAY, TimeOfDay.EVENING),
            min_level=3,
            max_level=6,
            rarity=Rarity.COMMON,
        ),
        SpawnCandidate(
            species=PIDGEY,
            weight=55.0,
            allowed_times=(TimeOfDay.MORNING, TimeOfDay.DAY),
            min_level=3,
            max_level=6,
            rarity=Rarity.COMMON,
        ),
        SpawnCandidate(
            species=EEVEE,
            weight=20.0,
            allowed_times=(TimeOfDay.DAY, TimeOfDay.EVENING),
            min_level=4,
            max_level=7,
            rarity=Rarity.UNCOMMON,
        ),
        SpawnCandidate(
            species=GROWLITHE,
            weight=25.0,
            allowed_times=(TimeOfDay.DAY, TimeOfDay.EVENING),
            min_level=5,
            max_level=7,
            rarity=Rarity.UNCOMMON,
        ),
        SpawnCandidate(
            species=BULBASAUR,
            weight=15.0,
            allowed_times=(TimeOfDay.MORNING, TimeOfDay.DAY),
            min_level=4,
            max_level=6,
            rarity=Rarity.UNCOMMON,
        ),
        SpawnCandidate(
            species=PIKACHU,
            weight=15.0,
            allowed_times=(TimeOfDay.DAY,),
            min_level=4,
            max_level=6,
            rarity=Rarity.UNCOMMON,
        ),
    ),
)

# Habitat Catalog Registry
HABITAT_CATALOG: dict[str, Habitat] = {
    MEADOW_HABITAT.habitat_id: MEADOW_HABITAT,
    FOREST_HABITAT.habitat_id: FOREST_HABITAT,
    SHRINE_GROUNDS_HABITAT.habitat_id: SHRINE_GROUNDS_HABITAT,
    MOUNTAIN_PASS_HABITAT.habitat_id: MOUNTAIN_PASS_HABITAT,
    LAKESIDE_HABITAT.habitat_id: LAKESIDE_HABITAT,
    HAUNTED_RUINS_HABITAT.habitat_id: HAUNTED_RUINS_HABITAT,
    PLAINS_HABITAT.habitat_id: PLAINS_HABITAT,
}

# Fast lookup from region_id to habitat_id
REGION_TO_HABITAT_MAP: dict[str, str] = {
    "starting_meadow": MEADOW_HABITAT.habitat_id,
    "forest_trail": FOREST_HABITAT.habitat_id,
    "ancient_shrine_grounds": SHRINE_GROUNDS_HABITAT.habitat_id,
    "mountain_pass": MOUNTAIN_PASS_HABITAT.habitat_id,
    "lakeside": LAKESIDE_HABITAT.habitat_id,
    "haunted_ruins": HAUNTED_RUINS_HABITAT.habitat_id,
    "tall_grass_plains": PLAINS_HABITAT.habitat_id,
}


def get_habitat(habitat_id: str) -> Optional[Habitat]:
    """
    Looks up a Habitat definition from the catalog by its ID.
    Returns the Habitat instance or None if not found.
    """
    if not isinstance(habitat_id, str):
        return None
    return HABITAT_CATALOG.get(habitat_id.strip().lower())


def get_habitat_for_region(region_id: str) -> Optional[Habitat]:
    """
    Finds the Habitat associated with a given world-region ID.
    Returns the Habitat instance or None if the region has no configured habitat.
    """
    if not isinstance(region_id, str):
        return None
    norm_id = region_id.strip().lower()
    hab_id = REGION_TO_HABITAT_MAP.get(norm_id)
    if hab_id is not None:
        return HABITAT_CATALOG.get(hab_id)

    # Fallback search across region_ids of all catalog habitats
    for hab in HABITAT_CATALOG.values():
        if norm_id in hab.region_ids:
            return hab
    return None


def list_habitats() -> tuple[Habitat, ...]:
    """Returns all habitat definitions in predictable catalog order."""
    return tuple(HABITAT_CATALOG.values())


def create_default_habitats() -> list[Habitat]:
    """
    Creates fresh, independent instances of default habitats
    to protect static definitions from runtime mutation.
    """
    return [
        Habitat(
            habitat_id=h.habitat_id,
            name=h.name,
            description=h.description,
            region_ids=h.region_ids,
            candidates=h.candidates,
        )
        for h in HABITAT_CATALOG.values()
    ]
