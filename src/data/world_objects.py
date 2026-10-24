"""
Static catalog of world interactable objects, resource nodes, treasures, signs, and landmarks.
"""
from typing import Optional
from src.models.world_interaction import Interactable, InteractableType

# 1. Berry Bush (Resource Node - Renewable, grants 1 Potion, 60s respawn)
BERRY_BUSH = Interactable(
    object_id="berry_bush_route1",
    name="Berry Bush",
    description="A wild bush growing juicy berries that can restore vitality.",
    interactable_type=InteractableType.RESOURCE_NODE,
    position=(5.0, 5.0),
    interaction_radius=2.0,
    rewards={"potion": 1},
    interaction_text="You plucked a fresh berry from the bush! (Obtained 1x Potion)",
    respawn_duration=60.0,
    region_id="starting_meadow",
)

# 2. Hidden Supply Cache (Treasure - One-time reward, grants Super Potion + Antidotes)
SUPPLY_CACHE = Interactable(
    object_id="supply_cache_01",
    name="Trainer Supply Cache",
    description="A sturdy waterproof container left behind by seasoned trainers.",
    interactable_type=InteractableType.TREASURE,
    position=(15.0, 10.0),
    interaction_radius=2.5,
    rewards={"super_potion": 1, "antidote": 2},
    interaction_text="You opened the supply cache and recovered valuable items!",
    respawn_duration=None,
    region_id="forest_trail",
)

# 3. Route 1 Sign (Sign - Informational, no item rewards)
ROUTE1_SIGN = Interactable(
    object_id="route1_sign",
    name="Route 1 Trail Marker",
    description="A painted wooden signpost near the entrance of Route 1.",
    interactable_type=InteractableType.SIGN,
    position=(2.0, 1.0),
    interaction_radius=2.0,
    rewards={},
    interaction_text="Route 1: Pathway to Viridian City. Watch for wild Pokemon in the tall grass!",
    respawn_duration=None,
    region_id="starting_meadow",
)

# 4. Ancient Shrine (Landmark - Discovery objective, no item rewards)
ANCIENT_SHRINE = Interactable(
    object_id="ancient_shrine",
    name="Thunder Stone Shrine",
    description="An ancient monolithic shrine etched with lightning crests.",
    interactable_type=InteractableType.LANDMARK,
    position=(25.0, 25.0),
    interaction_radius=3.0,
    rewards={},
    interaction_text="You discovered the Thunder Stone Shrine! A crackling energy lingers in the air.",
    respawn_duration=None,
    region_id="ancient_shrine_grounds",
)

# 5. Professor Oak (NPC - Starting Meadow near Route 1 sign at (2.0, 1.0))
NPC_PROF_OAK = Interactable(
    object_id="npc_prof_oak",
    name="Professor Oak",
    description="The renowned Pokemon researcher studying regional wildlife and trainer bonds.",
    interactable_type=InteractableType.NPC,
    position=(2.5, 1.5),
    interaction_radius=2.5,
    rewards={},
    interaction_text="Hello there, young Trainer! The world of Pokemon is vast and full of wonderful mysteries.",
    npc_id="prof_oak",
    region_id="starting_meadow",
)

# 6. Field Trainer Koji (NPC - Forest Trail near Supply Cache at (15.0, 10.0))
NPC_BATTLE_SCOUT = Interactable(
    object_id="npc_battle_scout",
    name="Field Trainer Koji",
    description="An energetic trainer training hard along the forest paths.",
    interactable_type=InteractableType.NPC,
    position=(15.5, 10.5),
    interaction_radius=2.5,
    rewards={},
    interaction_text="Hey there! Nothing builds strength like testing your skills in real battle!",
    npc_id="battle_scout",
    region_id="forest_trail",
)

# 7. Park Ranger Logan (NPC - Ancient Shrine Grounds near Thunder Stone Shrine at (25.0, 25.0))
NPC_TRAIL_RANGER = Interactable(
    object_id="npc_trail_ranger",
    name="Park Ranger Logan",
    description="A seasoned ranger keeping watch over the ancient grounds and historic landmarks.",
    interactable_type=InteractableType.NPC,
    position=(25.5, 24.5),
    interaction_radius=2.5,
    rewards={},
    interaction_text="Greetings, explorer. The wilderness holds many secrets for those with keen eyes.",
    npc_id="trail_ranger",
    region_id="ancient_shrine_grounds",
)

# 8. Camp Merchant Maya (NPC - Starting Meadow near Berry Bush at (5.0, 5.0))
NPC_SUPPLY_CLERK = Interactable(
    object_id="npc_supply_clerk",
    name="Camp Merchant Maya",
    description="A friendly traveling merchant supplying trainers with essential provisions.",
    interactable_type=InteractableType.NPC,
    position=(5.5, 5.5),
    interaction_radius=2.5,
    rewards={},
    interaction_text="Welcome to camp! Always make sure your pack is stocked before heading out.",
    npc_id="supply_clerk",
    region_id="starting_meadow",
)

# 9. Mountain Pass Sign (Sign - Informational)
MOUNTAIN_PASS_SIGN = Interactable(
    object_id="mountain_pass_sign",
    name="Mountain Pass Sign",
    description="A wooden warning sign standing on the rocky mountain pass.",
    interactable_type=InteractableType.SIGN,
    position=(35.0, 5.0),
    interaction_radius=2.0,
    rewards={},
    interaction_text="Danger ahead! Strong wild Pokémon roam these mountains.",
    respawn_duration=None,
    region_id="mountain_pass",
)

# 10. Lakeside Berry Bush (Resource Node - Renewable, grants 1 Potion, 60s respawn)
LAKESIDE_BERRY_BUSH = Interactable(
    object_id="lakeside_berry_bush",
    name="Lakeside Berry Bush",
    description="A wild bush growing along the water's edge, laden with ripe berries.",
    interactable_type=InteractableType.RESOURCE_NODE,
    position=(5.0, 15.0),
    interaction_radius=2.0,
    rewards={"potion": 1},
    interaction_text="You gathered berries from the bush! (Obtained 1x Potion)",
    respawn_duration=60.0,
    region_id="lakeside",
)

# 11. Ruins Treasure Chest (Treasure - One-time reward)
RUINS_TREASURE_CHEST = Interactable(
    object_id="ruins_treasure_chest",
    name="Ruins Treasure Chest",
    description="An ancient chest resting among the crumbling ruins.",
    interactable_type=InteractableType.TREASURE,
    position=(15.0, 20.0),
    interaction_radius=2.5,
    rewards={"super_potion": 2, "antidote": 1},
    interaction_text="You opened the ruins treasure chest! (Obtained 2x Super Potion, 1x Antidote)",
    respawn_duration=None,
    region_id="haunted_ruins",
)

# 12. Plains Landmark Stone (Landmark - Discovery objective)
PLAINS_LANDMARK_STONE = Interactable(
    object_id="plains_landmark_stone",
    name="Plains Landmark Stone",
    description="A moss-covered standing stone marks the center of the plains.",
    interactable_type=InteractableType.LANDMARK,
    position=(25.0, 14.0),
    interaction_radius=2.5,
    rewards={},
    interaction_text="You inspect the moss-covered standing stone marking the center of the plains.",
    respawn_duration=None,
    region_id="tall_grass_plains",
)

# 13. Starting Meadow Pokémon Center
POKEMON_CENTER_MEADOW = Interactable(
    object_id="pokemon_center_meadow",
    name="Starting Meadow Pokémon Center",
    description="A welcoming Pokémon Center providing free medical care and rest for weary Pokémon.",
    interactable_type=InteractableType.POKEMON_CENTER,
    position=(5.0, 5.0),
    interaction_radius=2.5,
    rewards={},
    interaction_text="Welcome to the Pokémon Center! We have restored all your Pokémon to full health and default stats!",
    respawn_duration=None,
    region_id="starting_meadow",
)

# 14. Forest Trail Pokémon Center
POKEMON_CENTER_FOREST = Interactable(
    object_id="pokemon_center_forest",
    name="Forest Trail Pokémon Center",
    description="A wooden lodge Pokémon Center nestled along the forest path.",
    interactable_type=InteractableType.POKEMON_CENTER,
    position=(15.0, 10.0),
    interaction_radius=2.5,
    rewards={},
    interaction_text="Welcome to the Pokémon Center! We have restored all your Pokémon to full health and default stats!",
    respawn_duration=None,
    region_id="forest_trail",
)

# 15. Ancient Shrine Pokémon Center
POKEMON_CENTER_SHRINE = Interactable(
    object_id="pokemon_center_shrine",
    name="Ancient Shrine Pokémon Center",
    description="A field outpost Pokémon Center providing rest near the sacred grounds.",
    interactable_type=InteractableType.POKEMON_CENTER,
    position=(25.0, 25.0),
    interaction_radius=2.5,
    rewards={},
    interaction_text="Welcome to the Pokémon Center! We have restored all your Pokémon to full health and default stats!",
    respawn_duration=None,
    region_id="ancient_shrine_grounds",
)

# 16. Mountain Pass Pokémon Center
POKEMON_CENTER_MOUNTAIN = Interactable(
    object_id="pokemon_center_mountain",
    name="Mountain Pass Pokémon Center",
    description="A sturdy stone Pokémon Center built to withstand high altitude winds.",
    interactable_type=InteractableType.POKEMON_CENTER,
    position=(35.0, 5.0),
    interaction_radius=2.5,
    rewards={},
    interaction_text="Welcome to the Pokémon Center! We have restored all your Pokémon to full health and default stats!",
    respawn_duration=None,
    region_id="mountain_pass",
)

# 17. Crystal Lakeside Pokémon Center
POKEMON_CENTER_LAKESIDE = Interactable(
    object_id="pokemon_center_lakeside",
    name="Crystal Lakeside Pokémon Center",
    description="A tranquil waterside Pokémon Center with panoramic lake views.",
    interactable_type=InteractableType.POKEMON_CENTER,
    position=(5.0, 15.0),
    interaction_radius=2.5,
    rewards={},
    interaction_text="Welcome to the Pokémon Center! We have restored all your Pokémon to full health and default stats!",
    respawn_duration=None,
    region_id="lakeside",
)

# 18. Haunted Ruins Pokémon Center
POKEMON_CENTER_RUINS = Interactable(
    object_id="pokemon_center_ruins",
    name="Haunted Ruins Pokémon Center",
    description="A fortified shelter Pokémon Center standing resilient against eerie ruins.",
    interactable_type=InteractableType.POKEMON_CENTER,
    position=(15.0, 20.0),
    interaction_radius=2.5,
    rewards={},
    interaction_text="Welcome to the Pokémon Center! We have restored all your Pokémon to full health and default stats!",
    respawn_duration=None,
    region_id="haunted_ruins",
)

# 19. Tall Grass Plains Pokémon Center
POKEMON_CENTER_PLAINS = Interactable(
    object_id="pokemon_center_plains",
    name="Tall Grass Plains Pokémon Center",
    description="A bright open-air Pokémon Center serving trainers traversing the wide plains.",
    interactable_type=InteractableType.POKEMON_CENTER,
    position=(25.0, 14.0),
    interaction_radius=2.5,
    rewards={},
    interaction_text="Welcome to the Pokémon Center! We have restored all your Pokémon to full health and default stats!",
    respawn_duration=None,
    region_id="tall_grass_plains",
)

# Catalog mapping object_id -> template Interactable
WORLD_OBJECT_CATALOG: dict[str, Interactable] = {
    BERRY_BUSH.object_id: BERRY_BUSH,
    SUPPLY_CACHE.object_id: SUPPLY_CACHE,
    ROUTE1_SIGN.object_id: ROUTE1_SIGN,
    ANCIENT_SHRINE.object_id: ANCIENT_SHRINE,
    NPC_PROF_OAK.object_id: NPC_PROF_OAK,
    NPC_BATTLE_SCOUT.object_id: NPC_BATTLE_SCOUT,
    NPC_TRAIL_RANGER.object_id: NPC_TRAIL_RANGER,
    NPC_SUPPLY_CLERK.object_id: NPC_SUPPLY_CLERK,
    MOUNTAIN_PASS_SIGN.object_id: MOUNTAIN_PASS_SIGN,
    LAKESIDE_BERRY_BUSH.object_id: LAKESIDE_BERRY_BUSH,
    RUINS_TREASURE_CHEST.object_id: RUINS_TREASURE_CHEST,
    PLAINS_LANDMARK_STONE.object_id: PLAINS_LANDMARK_STONE,
    POKEMON_CENTER_MEADOW.object_id: POKEMON_CENTER_MEADOW,
    POKEMON_CENTER_FOREST.object_id: POKEMON_CENTER_FOREST,
    POKEMON_CENTER_SHRINE.object_id: POKEMON_CENTER_SHRINE,
    POKEMON_CENTER_MOUNTAIN.object_id: POKEMON_CENTER_MOUNTAIN,
    POKEMON_CENTER_LAKESIDE.object_id: POKEMON_CENTER_LAKESIDE,
    POKEMON_CENTER_RUINS.object_id: POKEMON_CENTER_RUINS,
    POKEMON_CENTER_PLAINS.object_id: POKEMON_CENTER_PLAINS,
}


def get_world_object(object_id: str) -> Optional[Interactable]:
    """Looks up a world object definition by its ID."""
    if not isinstance(object_id, str):
        return None
    return WORLD_OBJECT_CATALOG.get(object_id.strip().lower())


def list_catalog_objects() -> tuple[Interactable, ...]:
    """Returns all world object templates in the catalog."""
    return tuple(WORLD_OBJECT_CATALOG.values())


def create_default_world_objects() -> list[Interactable]:
    """
    Creates fresh, independent instances of all default world objects
    to ensure runtime modifications never alter global catalog templates.
    """
    instances: list[Interactable] = []
    for template in WORLD_OBJECT_CATALOG.values():
        instances.append(
            Interactable(
                object_id=template.object_id,
                name=template.name,
                description=template.description,
                interactable_type=template.interactable_type,
                position=template.position,
                interaction_radius=template.interaction_radius,
                is_available=template.is_available,
                rewards=dict(template.rewards),
                interaction_text=template.interaction_text,
                respawn_duration=template.respawn_duration,
                respawn_deadline=template.respawn_deadline,
                npc_id=template.npc_id,
                region_id=template.region_id,
            )
        )
    return instances
