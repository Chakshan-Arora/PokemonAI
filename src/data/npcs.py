"""
Static catalog of in-world NPCs and quest givers.
Defines predefined NPC personalities, dialogue, locations, and offered quests.
"""
from typing import Optional
from src.models.npc import NPC

# 1. Professor Oak (Starting Meadow near Route 1 sign at (2.0, 1.0))
PROFESSOR_OAK = NPC(
    npc_id="prof_oak",
    name="Professor Oak",
    title="Pokemon Researcher",
    description="The renowned Pokemon researcher studying regional wildlife and trainer bonds.",
    position=(2.5, 1.5),
    interaction_radius=2.5,
    offered_quest_ids=("first_encounter", "species_research", "research_specialization"),
    dialogue={
        "greeting": "Hello there, young Trainer! The world of Pokemon is vast and full of wonderful mysteries.",
        "farewell": "Take care out there, Trainer! Remember to care for your Pokemon partner.",
        "offer": "I have an important research task that could use a capable trainer like yourself.",
        "first_encounter_offer": (
            "Before we delve into deeper studies, you need practical field experience. "
            "Head into the tall grass and capture your very first wild Pokemon!"
        ),
        "first_encounter_in_progress": "Have you captured a wild Pokemon yet? Check the tall grass in the meadow!",
        "first_encounter_completed": "Splendid work! You caught your first wild Pokemon. That bond will serve you well.",
        "first_encounter_declined": "No problem. Come speak with me whenever you feel ready to take on the wild.",
        "species_research_offer": (
            "Now that you know the basics of capture, I need specific specimens for our behavioral research. "
            "Please discover and capture both a Pikachu and a Squirtle!"
        ),
        "species_research_locked": (
            "I'm preparing a field study on different species, but you'll need foundational capture experience first! "
            "Please complete 'First Encounter' before we begin."
        ),
        "species_research_in_progress": (
            "We are studying Pikachu and Squirtle. Keep exploring different areas and times of day to find them!"
        ),
        "species_research_completed": (
            "Outstanding! Having both Pikachu and Squirtle data provides invaluable insight into species diversity."
        ),
        "species_research_declined": "Very well. Take your time training, and return when you're ready to research.",
        "research_specialization_offer": (
            "I am seeking a capable trainer to specialize in advanced field methodology. "
            "Will you focus on field capture techniques or tactical battle analysis?"
        ),
        "research_specialization_locked": (
            "You must complete 'First Encounter' to prove your core training abilities before specializing!"
        ),
        "research_specialization_in_progress": (
            "Consider your specialization branch carefully and fulfill its required fieldwork."
        ),
        "research_specialization_completed": (
            "Remarkable fieldwork! Your specialized contribution has greatly accelerated our regional studies."
        ),
        "research_specialization_declined": "Take your time. A researcher must choose their specialty with conviction.",
        "field_capture_chosen": "A patient observer! Capture data reveals true ecological behavior in the wild.",
        "tactical_combat_chosen": "A spirited battle strategist! Combat data illuminates Pokémon resilience and power.",
    },
)

# 2. Field Trainer Koji (Forest Trail near Supply Cache at (15.0, 10.0))
BATTLE_SCOUT = NPC(
    npc_id="battle_scout",
    name="Field Trainer Koji",
    title="Battle Scout",
    description="An energetic trainer training vigorously along the winding forest trails.",
    position=(15.5, 10.5),
    interaction_radius=2.5,
    offered_quest_ids=("wild_challenger", "growing_stronger"),
    dialogue={
        "greeting": "Hey there! Nothing builds strength like testing your skills in real battle!",
        "farewell": "Keep that fighting spirit sharp! See you on the battlefield.",
        "offer": "Looking to prove yourself in battle? I've got just the challenge for you.",
        "wild_challenger_offer": (
            "To become a top trainer, you must understand turn-based combat and type matchups. "
            "Step up and defeat any wild Pokemon in combat!"
        ),
        "wild_challenger_in_progress": "Find a wild Pokemon in combat and score a clean knockout!",
        "wild_challenger_completed": "Great combat instincts! You proved your tactical battle skills.",
        "wild_challenger_declined": "Catch your breath and come back whenever you're itching for a fight!",
        "growing_stronger_offer": (
            "A true battle partner grows with experience. "
            "Train and battle with your team until at least one of your Pokemon reaches Level 5!"
        ),
        "growing_stronger_locked": (
            "Before you focus on heavy leveling, you need practical capture experience! "
            "Complete 'First Encounter' first so you have a well-rounded foundation."
        ),
        "growing_stronger_in_progress": "Keep training your partner! Win wild battles to earn experience.",
        "growing_stronger_completed": "Incredible dedication! Your Pokemon is growing into a formidable companion.",
        "growing_stronger_declined": "Take it easy! Consistent training beats rushing every time.",
    },
)

# 3. Park Ranger Logan (Ancient Shrine Grounds near Thunder Stone Shrine at (25.0, 25.0))
TRAIL_RANGER = NPC(
    npc_id="trail_ranger",
    name="Park Ranger Logan",
    title="Wilderness Scout",
    description="A seasoned ranger keeping watch over the ancient grounds and historic landmarks.",
    position=(25.5, 24.5),
    interaction_radius=2.5,
    offered_quest_ids=("trailblazer", "shrine_investigation"),
    dialogue={
        "greeting": "Greetings, explorer. The wilderness holds many secrets for those with keen eyes.",
        "farewell": "Respect the land and leave no trace behind. Safe travels.",
        "offer": "I'm charting landmark activity across the reserve. Care to help map the region?",
        "trailblazer_offer": (
            "A good trainer knows the lay of the land. Chart new horizons by discovering both "
            "the Starting Meadow and the legendary Thunder Stone Shrine!"
        ),
        "trailblazer_locked": (
            "The terrain out here can be unforgiving. You must complete 'First Encounter' "
            "to prove you can handle yourself before embarking on wilderness charting."
        ),
        "trailblazer_in_progress": (
            "Travel between regions and inspect ancient landmarks to record your discoveries."
        ),
        "trailblazer_completed": (
            "Superb orienteering! You have the makings of a true trailblazer."
        ),
        "trailblazer_declined": "Understood. The trails aren't going anywhere—let me know when you're ready.",
        "shrine_investigation_offer": (
            "The Ancient Shrine has been acting up with strange energy pulses. "
            "Discover the shrine, then choose whether to placate the energy with peaceful offerings or subdue wild guardians."
        ),
        "shrine_investigation_locked": (
            "The ancient shrine grounds are treacherous! Complete 'First Encounter' before venturing into shrine investigations."
        ),
        "shrine_investigation_in_progress": (
            "Travel to the Ancient Shrine and determine the best approach to resolve the anomaly."
        ),
        "shrine_investigation_completed": (
            "The energy at the shrine has completely stabilized! Outstanding work handling the investigation."
        ),
        "shrine_investigation_declined": "Stay alert regardless. The ancient grounds demand respect.",
        "peaceful_offering_chosen": "A wise path. Honoring ancient landmarks with offerings maintains natural harmony.",
        "combat_trial_chosen": "Stand resolute! A decisive victory will reassure the wild Pokémon inhabiting the grounds.",
    },
)

# 4. Camp Merchant Maya (Starting Meadow near Berry Bush at (5.0, 5.0))
SUPPLY_CLERK = NPC(
    npc_id="supply_clerk",
    name="Camp Merchant Maya",
    title="Field Outfitter",
    description="A cheerful traveling merchant supplying trainers with essential provisions.",
    position=(5.5, 5.5),
    interaction_radius=2.5,
    offered_quest_ids=("stocking_supplies", "collectors_pride"),
    dialogue={
        "greeting": "Welcome to camp! Always make sure your pack is stocked before heading out.",
        "farewell": "Check back anytime! A prepared trainer is a successful trainer.",
        "offer": "I have some helpful preparation tasks to get your journey properly equipped.",
        "stocking_supplies_offer": (
            "Long expeditions require medical supplies! Make sure your bag is ready by "
            "accumulating at least 3 Potions in your inventory."
        ),
        "stocking_supplies_in_progress": "You can gather berries from the bushes or loot supply caches to find Potions!",
        "stocking_supplies_completed": "A well-stocked bag gives great peace of mind! Here is your reward.",
        "stocking_supplies_declined": "No problem! You can always stock up later.",
        "collectors_pride_offer": (
            "Collectors and trainers alike revere Fire-type companions. "
            "Expand your collection by obtaining a Charmander!"
        ),
        "collectors_pride_in_progress": "Charmander can be chosen as a starter or encountered in warm habitats.",
        "collectors_pride_completed": "Magnificent! A Charmander is a fiery and devoted partner.",
        "collectors_pride_declined": "Take your time! The right partner will find you.",
    },
)

# Catalog Registry mapping npc_id -> template NPC
NPC_CATALOG: dict[str, NPC] = {
    PROFESSOR_OAK.npc_id: PROFESSOR_OAK,
    BATTLE_SCOUT.npc_id: BATTLE_SCOUT,
    TRAIL_RANGER.npc_id: TRAIL_RANGER,
    SUPPLY_CLERK.npc_id: SUPPLY_CLERK,
}


def get_npc(npc_id: str) -> Optional[NPC]:
    """Looks up an NPC template by identifier."""
    if not isinstance(npc_id, str):
        return None
    return NPC_CATALOG.get(npc_id.strip().lower())


def list_catalog_npcs() -> tuple[NPC, ...]:
    """Returns all NPC templates in the catalog in a predictable order."""
    return tuple(NPC_CATALOG.values())


def create_default_npcs() -> list[NPC]:
    """Creates fresh copies of all default NPCs."""
    return [
        NPC(
            npc_id=npc.npc_id,
            name=npc.name,
            title=npc.title,
            description=npc.description,
            position=npc.position,
            interaction_radius=npc.interaction_radius,
            offered_quest_ids=npc.offered_quest_ids,
            dialogue=dict(npc.dialogue),
        )
        for npc in NPC_CATALOG.values()
    ]
