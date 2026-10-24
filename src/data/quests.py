"""
Predefined quest catalog containing data-driven quest and objective definitions.
"""
from typing import Optional
from src.models.quest import (
    QuestDefinition,
    QuestObjective,
    ObjectiveType,
    QuestChoice,
    QuestChoiceOption,
)

# 1. First Encounter: Capture any wild Pokemon
FIRST_ENCOUNTER = QuestDefinition(
    quest_id="first_encounter",
    name="First Encounter",
    description="Venture into the wild tall grass and capture your very first wild Pokemon.",
    objectives=(
        QuestObjective(
            objective_id="capture_first_pokemon",
            objective_type=ObjectiveType.CAPTURE_ANY,
            description="Capture any 1 wild Pokemon",
            target_count=1,
        ),
    ),
    prerequisites=(),
    rewards={"potion": 2},
)

# 2. Species Research: Capture one Pikachu and one Squirtle
SPECIES_RESEARCH = QuestDefinition(
    quest_id="species_research",
    name="Species Research",
    description="Aid the research project by discovering and capturing a Pikachu and a Squirtle.",
    objectives=(
        QuestObjective(
            objective_id="capture_pikachu",
            objective_type=ObjectiveType.CAPTURE_SPECIES,
            description="Capture 1 Pikachu",
            target_count=1,
            target_species="Pikachu",
        ),
        QuestObjective(
            objective_id="capture_squirtle",
            objective_type=ObjectiveType.CAPTURE_SPECIES,
            description="Capture 1 Squirtle",
            target_count=1,
            target_species="Squirtle",
        ),
    ),
    prerequisites=("first_encounter",),
    rewards={"potion": 3},
)

# 3. Growing Stronger: Reach level 5 on any Pokemon
GROWING_STRONGER = QuestDefinition(
    quest_id="growing_stronger",
    name="Growing Stronger",
    description="Train and battle with your Pokemon until at least one reaches Level 5.",
    objectives=(
        QuestObjective(
            objective_id="reach_level_5",
            objective_type=ObjectiveType.REACH_LEVEL,
            description="Reach Level 5 on any Pokemon",
            target_count=5,
        ),
    ),
    prerequisites=("first_encounter",),
    rewards={"super_potion": 1},
)

# 4. Collector's Pride: Own a Charmander in your collection
COLLECTORS_PRIDE = QuestDefinition(
    quest_id="collectors_pride",
    name="Collector's Pride",
    description="Expand your trainer collection by obtaining a Charmander.",
    objectives=(
        QuestObjective(
            objective_id="own_charmander",
            objective_type=ObjectiveType.OWN_SPECIES,
            description="Own 1 Charmander in collection",
            target_count=1,
            target_species="Charmander",
        ),
    ),
    prerequisites=(),
    rewards={"antidote": 1},
)

# 5. Wild Challenger: Defeat any Pokemon in combat
WILD_CHALLENGER = QuestDefinition(
    quest_id="wild_challenger",
    name="Wild Challenger",
    description="Test your combat skills in a turn-based battle and defeat any Pokemon.",
    objectives=(
        QuestObjective(
            objective_id="defeat_any_pokemon",
            objective_type=ObjectiveType.DEFEAT_ANY,
            description="Defeat any 1 Pokemon in battle",
            target_count=1,
        ),
    ),
    prerequisites=(),
    rewards={"super_potion": 1},
)

# 6. Stocking Supplies: Collect 3 Potions in inventory
STOCKING_SUPPLIES = QuestDefinition(
    quest_id="stocking_supplies",
    name="Stocking Supplies",
    description="Ensure your bag is ready for exploration by accumulating at least 3 Potions.",
    objectives=(
        QuestObjective(
            objective_id="collect_potions",
            objective_type=ObjectiveType.COLLECT_ITEM,
            description="Possess at least 3 Potions in inventory",
            target_count=3,
            target_item="potion",
        ),
    ),
    prerequisites=(),
    rewards={"super_potion": 1},
)

# 7. Trailblazer: Exploration of Starting Meadow and Thunder Stone Shrine
TRAILBLAZER = QuestDefinition(
    quest_id="trailblazer",
    name="Trailblazer",
    description="Chart new horizons by discovering the Starting Meadow and the Thunder Stone Shrine.",
    objectives=(
        QuestObjective(
            objective_id="discover_meadow",
            objective_type=ObjectiveType.DISCOVER_REGION,
            description="Discover Starting Meadow",
            target_count=1,
            target_region="starting_meadow",
        ),
        QuestObjective(
            objective_id="discover_shrine",
            objective_type=ObjectiveType.DISCOVER_LANDMARK,
            description="Discover Thunder Stone Shrine",
            target_count=1,
            target_landmark="ancient_shrine",
        ),
    ),
    prerequisites=("first_encounter",),
    rewards={"potion": 2},
)

# 8. Shrine Investigation: Branching investigation at the Ancient Thunder Stone Shrine
SHRINE_INVESTIGATION = QuestDefinition(
    quest_id="shrine_investigation",
    name="Shrine Investigation",
    description="Investigate anomalous energy at the Ancient Shrine and choose your resolution path.",
    objectives=(
        QuestObjective(
            objective_id="obj_reach_shrine",
            objective_type=ObjectiveType.DISCOVER_LANDMARK,
            description="Discover Ancient Shrine landmark",
            target_count=1,
            target_landmark="ancient_shrine",
        ),
    ),
    prerequisites=("first_encounter",),
    rewards={"potion": 1},
    choices=(
        QuestChoice(
            choice_id="investigation_path",
            prompt="How will you handle the shrine disturbance?",
            prerequisite_objectives=("obj_reach_shrine",),
            options=(
                QuestChoiceOption(
                    option_id="peaceful_offering",
                    text="Peaceful Offering",
                    description="Inspect the ancient shrine and gather botanical berries as an offering.",
                    objectives=(
                        QuestObjective(
                            objective_id="obj_shrine_inspect",
                            objective_type=ObjectiveType.INTERACT_OBJECT,
                            description="Examine the Ancient Thunder Stone Shrine",
                            target_count=1,
                            target_object="shrine_thunder_stone",
                        ),
                        QuestObjective(
                            objective_id="obj_shrine_potions",
                            objective_type=ObjectiveType.COLLECT_ITEM,
                            description="Possess at least 2 Potions as a peace offering",
                            target_count=2,
                            target_item="potion",
                        ),
                    ),
                    rewards={"antidote": 2, "potion": 1},
                ),
                QuestChoiceOption(
                    option_id="combat_trial",
                    text="Combat Trial",
                    description="Subdue wild challengers near the shrine to calm the area.",
                    objectives=(
                        QuestObjective(
                            objective_id="obj_shrine_combat",
                            objective_type=ObjectiveType.DEFEAT_ANY,
                            description="Defeat 2 wild Pokémon near Ancient Shrine",
                            target_count=2,
                            target_region="ancient_shrine",
                        ),
                    ),
                    rewards={"super_potion": 2},
                ),
            ),
        ),
    ),
)

# 9. Research Specialization: Choose an immediate academic focus
RESEARCH_SPECIALIZATION = QuestDefinition(
    quest_id="research_specialization",
    name="Research Specialization",
    description="Select a specialized field research focus to assist Professor Oak.",
    objectives=(),
    prerequisites=("first_encounter",),
    rewards={"potion": 1},
    choices=(
        QuestChoice(
            choice_id="specialization_branch",
            prompt="Which field research discipline do you wish to pursue?",
            options=(
                QuestChoiceOption(
                    option_id="field_capture",
                    text="Field Capture Specialist",
                    description="Study behavioral patterns by capturing 2 wild Pokémon in Starting Meadow.",
                    objectives=(
                        QuestObjective(
                            objective_id="obj_spec_capture",
                            objective_type=ObjectiveType.CAPTURE_ANY,
                            description="Capture 2 wild Pokémon in Starting Meadow",
                            target_count=2,
                            target_region="starting_meadow",
                        ),
                    ),
                    rewards={"poke_ball": 3},
                ),
                QuestChoiceOption(
                    option_id="tactical_combat",
                    text="Tactical Combat Specialist",
                    description="Test battle capabilities by defeating 2 wild Pokémon in Starting Meadow.",
                    objectives=(
                        QuestObjective(
                            objective_id="obj_spec_defeat",
                            objective_type=ObjectiveType.DEFEAT_ANY,
                            description="Defeat 2 wild Pokémon in Starting Meadow",
                            target_count=2,
                            target_region="starting_meadow",
                        ),
                    ),
                    rewards={"super_potion": 1, "potion": 1},
                ),
            ),
        ),
    ),
)

# Quest Catalog Registry
QUEST_CATALOG: dict[str, QuestDefinition] = {
    FIRST_ENCOUNTER.quest_id: FIRST_ENCOUNTER,
    SPECIES_RESEARCH.quest_id: SPECIES_RESEARCH,
    GROWING_STRONGER.quest_id: GROWING_STRONGER,
    COLLECTORS_PRIDE.quest_id: COLLECTORS_PRIDE,
    WILD_CHALLENGER.quest_id: WILD_CHALLENGER,
    STOCKING_SUPPLIES.quest_id: STOCKING_SUPPLIES,
    TRAILBLAZER.quest_id: TRAILBLAZER,
    SHRINE_INVESTIGATION.quest_id: SHRINE_INVESTIGATION,
    RESEARCH_SPECIALIZATION.quest_id: RESEARCH_SPECIALIZATION,
}


def get_quest(quest_id: str) -> Optional[QuestDefinition]:
    """
    Looks up a quest definition from the catalog by its identifier.
    Returns the QuestDefinition or None if not found.
    """
    if not isinstance(quest_id, str):
        return None
    return QUEST_CATALOG.get(quest_id.strip().lower())


def list_catalog_quests() -> tuple[QuestDefinition, ...]:
    """Returns all quest definitions in the catalog in a predictable order."""
    return tuple(QUEST_CATALOG.values())
