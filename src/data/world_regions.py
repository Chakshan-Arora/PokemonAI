"""
Static catalog of world exploration regions and region definitions.
Defines predefined geographic regions compatible with the world object catalog.
"""
from typing import Optional
from src.models.world_exploration import WorldRegion

# 1. Starting Meadow (Encompasses Pallet Town, Ash's House, Oak's House, Oak's Lab, and Route 1 Tall Grass)
STARTING_MEADOW = WorldRegion(
    region_id="starting_meadow",
    name="Starting Meadow",
    description="A sunlit town and clearing where new trainers begin their journey. Features Ash's House, Oak's Residence, Oak's Pokémon Research Lab, and Route 1 tall grass.",
    bounds=(0.0, 0.0, 10.0, 10.0),
    discovery_text="You have stepped into the Starting Meadow! Warm sunlight illuminates the open clearing.",
    landmark_ids=("player_house", "oak_house", "oak_lab", "route1_tall_grass"),
)

# 2. Forest Trail (Encompasses Supply Cache at (15.0, 10.0))
FOREST_TRAIL = WorldRegion(
    region_id="forest_trail",
    name="Forest Trail",
    description="A shaded winding pathway bordered by dense brush where travelers cache supplies.",
    bounds=(11.0, 0.0, 20.0, 15.0),
    discovery_text="You entered the Forest Trail. Tall canopies whisper quietly in the forest wind.",
    landmark_ids=(),
)

# 3. Ancient Shrine Grounds (Encompasses Thunder Stone Shrine at (25.0, 25.0))
ANCIENT_SHRINE_GROUNDS = WorldRegion(
    region_id="ancient_shrine_grounds",
    name="Ancient Shrine Grounds",
    description="A secluded plateau surrounding the legendary Thunder Stone Shrine.",
    bounds=(21.0, 20.0, 30.0, 30.0),
    discovery_text="You discovered the Ancient Shrine Grounds! Residual thunder energy pulses through the stone.",
    landmark_ids=("ancient_shrine",),
)

# 4. Mountain Pass
MOUNTAIN_PASS = WorldRegion(
    region_id="mountain_pass",
    name="Mountain Pass",
    description="A rocky mountain path with exposed boulders and cliffs.",
    bounds=(31.0, 0.0, 40.0, 10.0),
    discovery_text="You entered the Mountain Pass! Cold mountain winds sweep across rugged rocky cliffs.",
    landmark_ids=("mountain_pass_sign",),
)

# 5. Crystal Lakeside
LAKESIDE = WorldRegion(
    region_id="lakeside",
    name="Crystal Lakeside",
    description="A serene lake surrounded by tall reeds and rippling water.",
    bounds=(0.0, 11.0, 10.0, 20.0),
    discovery_text="You discovered the Crystal Lakeside! Gentle ripples lap against the shore under fresh breezes.",
    landmark_ids=("lakeside_berry_bush",),
)

# 6. Haunted Ruins
HAUNTED_RUINS = WorldRegion(
    region_id="haunted_ruins",
    name="Haunted Ruins",
    description="Crumbling stone ruins where eerie lights flicker after dark.",
    bounds=(11.0, 16.0, 20.0, 25.0),
    discovery_text="You entered the Haunted Ruins! A mysterious chill lingers amidst crumbling stone arches.",
    landmark_ids=("ruins_treasure_chest",),
)

# 7. Tall Grass Plains
TALL_GRASS_PLAINS = WorldRegion(
    region_id="tall_grass_plains",
    name="Tall Grass Plains",
    description="Wide open grasslands where wild Pokémon roam freely.",
    bounds=(21.0, 10.0, 30.0, 19.0),
    discovery_text="You arrived at the Tall Grass Plains! An expansive sea of tall whispering grasses surrounds you.",
    landmark_ids=("plains_landmark_stone",),
)

# Region Catalog Registry
WORLD_REGION_CATALOG: dict[str, WorldRegion] = {
    STARTING_MEADOW.region_id: STARTING_MEADOW,
    FOREST_TRAIL.region_id: FOREST_TRAIL,
    ANCIENT_SHRINE_GROUNDS.region_id: ANCIENT_SHRINE_GROUNDS,
    MOUNTAIN_PASS.region_id: MOUNTAIN_PASS,
    LAKESIDE.region_id: LAKESIDE,
    HAUNTED_RUINS.region_id: HAUNTED_RUINS,
    TALL_GRASS_PLAINS.region_id: TALL_GRASS_PLAINS,
}


def get_region_definition(region_id: str) -> Optional[WorldRegion]:
    """
    Looks up a world region template from the catalog by its identifier.
    Returns the WorldRegion or None if not found.
    """
    if not isinstance(region_id, str):
        return None
    return WORLD_REGION_CATALOG.get(region_id.strip().lower())


def list_catalog_regions() -> tuple[WorldRegion, ...]:
    """Returns all region definitions in the catalog in predictable order."""
    return tuple(WORLD_REGION_CATALOG.values())


def create_default_world_regions() -> list[WorldRegion]:
    """
    Creates fresh, independent instances of all default world regions
    to prevent runtime modifications from mutating global catalog definitions.
    """
    return [
        WorldRegion(
            region_id=r.region_id,
            name=r.name,
            description=r.description,
            bounds=r.bounds,
            discovery_text=r.discovery_text,
            landmark_ids=r.landmark_ids,
        )
        for r in WORLD_REGION_CATALOG.values()
    ]
