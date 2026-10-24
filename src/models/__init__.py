"""
Models package for Pokémon game entities.
"""
from src.models.pokemon_type import PokemonType
from src.models.ability import Ability
from src.models.attack import Attack
from src.models.personality import Personality
from src.models.species import PokemonSpecies
from src.models.pokemon import (
    Pokemon,
    MIN_BOND,
    MAX_BOND,
    MIN_OBEDIENCE,
    MAX_OBEDIENCE,
    MAX_KNOWN_MOVES,
)
from src.models.player import Player
from src.models.behavior_state import BehaviorState
from src.models.behavior_context import BehaviorContext
from src.models.pokemon_behavior import PokemonBehavior
from src.models.spawn_area import SpawnArea
from src.models.personality_generator import generate_wild_personality, PersonalityGenerator
from src.models.spawn_manager import SpawnManager
from src.models.encounter_manager import EncounterManager, EncounterResult, WildEncounter
from src.models.battle_state import BattleState
from src.models.damage_calculator import calculate_damage, DamageResult
from src.models.battle import (
    Battle,
    BattleActionRecord,
    TurnResult,
    BattleActionType,
    BattleAction,
    BattleActionResult,
    # BattleTalkCommand,
    # BattleTalkPayload,
    # BattleTalkIntent,
    # TalkCategory,
)
from src.models.battle_manager import BattleManager
from src.models.progression import (
    MAX_LEVEL,
    XP_PER_LEVEL_MULTIPLIER,
    LevelUpResult,
    get_xp_for_next_level,
    calculate_xp_for_next_level,
    apply_experience,
)
from src.models.experience_manager import (
    DEFAULT_XP_REWARD_MULTIPLIER,
    BattleRewardResult,
    ExperienceManager,
    calculate_battle_xp_reward,
)
from src.models.capture_manager import (
    MIN_CAPTURE_PROBABILITY,
    MAX_CAPTURE_PROBABILITY,
    CaptureResult,
    CaptureManager,
    calculate_capture_probability,
)
from src.models.bond_manager import (
    BondManager,
    BondChangeResult,
    BondEventConfig,
    DEFAULT_BOND_BATTLE_VICTORY,
    DEFAULT_BOND_BATTLE_DEFEAT,
    DEFAULT_BOND_LEVEL_UP,
    DEFAULT_BOND_CAPTURE,
)
from src.models.obedience_manager import (
    ObedienceManager,
    ObedienceResult,
    CommandContext,
    calculate_obedience_probability,
    BASE_OBEDIENCE_PROBABILITY,
    OBEDIENCE_WEIGHT,
    BOND_WEIGHT,
    MIN_OBEDIENCE_PROBABILITY,
    MAX_OBEDIENCE_PROBABILITY,
)
from src.models.training_manager import (
    TrainingManager,
    TrainingResult,
    TrainingConfig,
    SUPPORTED_TRAINING_STATS,
    DEFAULT_TRAINING_AMOUNT,
    DEFAULT_STAT_CAP,
    DEFAULT_STAT_CAPS,
)
from src.models.move_manager import (
    DEFAULT_MAX_MOVES,
    MoveLearnResult,
    MoveForgetResult,
    MoveReplaceResult,
    PendingMove,
    LevelUpMoveProgressionResult,
    MoveManager,
)
from src.models.status_effect import (
    StatusEffectType,
    AttackEffect,
    StatusEffect,
    DEFAULT_BURN_DAMAGE_FRACTION,
    DEFAULT_POISON_DAMAGE_FRACTION,
    DEFAULT_PARALYSIS_CHANCE,
    DEFAULT_STAT_REDUCTION_DURATION,
    DEFAULT_STAT_REDUCTION_MULTIPLIER,
)
from src.models.status_effect_manager import (
    EffectApplicationResult,
    ActionCheckResult,
    EndOfTurnEffectRecord,
    EndOfTurnResult,
    StatusEffectManager,
)
from src.models.item import ItemType, Item
from src.models.inventory import Inventory, ItemStack, DEFAULT_INVENTORY_CAPACITY
from src.models.item_manager import ItemUseResult, ItemManager
from src.models.save_data import CURRENT_SCHEMA_VERSION, SaveDataError, validate_schema_version
from src.models.save_manager import (
    serialize_player,
    deserialize_player,
    save_game,
    load_game,
    save_game_with_ai,
    load_game_with_ai,
    load_game_with_trainers,
    SaveManager,
)
from src.models.quest import (
    QuestStatus,
    ObjectiveType,
    QuestEventType,
    QuestObjective,
    QuestDefinition,
    ObjectiveProgress,
    QuestProgress,
    QuestEvent,
)
from src.models.quest_manager import (
    QuestNotification,
    QuestActionResult,
    EventResult,
    QuestRewardResult,
    QuestManager,
)
from src.models.quest_journal import (
    make_progress_bar,
    ObjectiveEntryView,
    QuestEntryView,
    QuestJournal,
)
from src.models.world_interaction import (
    InteractableType,
    Interactable,
    InteractionResult,
)
from src.models.world_interaction_manager import WorldInteractionManager
from src.models.world_exploration import WorldRegion, ExplorationResult
from src.models.world_exploration_manager import WorldExplorationManager
from src.models.habitat import (
    TimeOfDay,
    Rarity,
    SpawnCandidate,
    Habitat,
    SpawnSelectionResult,
    HabitatEncounterResult,
    get_time_of_day,
)
from src.models.npc import NPC
from src.models.habitat_manager import HabitatManager
from src.models.trainer import Trainer, DifficultyProfile, TrainerArchetype
from src.models.trainer_team_generator import (
    TrainerTeamGenerator,
    calculate_player_party_strength,
    get_eligible_species_for_trainer,
    generate_pokemon_for_trainer,
    generate_trainer_team,
    create_trainer,
)
from src.models.trainer_ai import (
    TrainerActionType,
    TrainerDecision,
    TrainerAIDecisionModel,
)
from src.models.trainer_manager import (
    TrainerManager,
    create_default_trainers,
    create_default_trainer_manager,
    DEFAULT_TRAINERS_FILENAME,
    get_trainer_state_path_for_save_file,
)

__all__ = [
    "PokemonType",
    "Ability",
    "Attack",
    "Personality",
    "PokemonSpecies",
    "Pokemon",
    "MIN_BOND",
    "MAX_BOND",
    "MIN_OBEDIENCE",
    "MAX_OBEDIENCE",
    "MAX_KNOWN_MOVES",
    "Player",
    "BehaviorState",
    "BehaviorContext",
    "PokemonBehavior",
    "SpawnArea",
    "generate_wild_personality",
    "PersonalityGenerator",
    "SpawnManager",
    "EncounterManager",
    "EncounterResult",
    "WildEncounter",
    "BattleState",
    "calculate_damage",
    "DamageResult",
    "Battle",
    "BattleActionRecord",
    "TurnResult",
    "BattleActionType",
    "BattleAction",
    "BattleActionResult",
    # "BattleTalkCommand",
    # "BattleTalkPayload",
    # "BattleTalkIntent",
    # "TalkCategory",
    "BattleManager",
    "MAX_LEVEL",
    "XP_PER_LEVEL_MULTIPLIER",
    "LevelUpResult",
    "get_xp_for_next_level",
    "calculate_xp_for_next_level",
    "apply_experience",
    "DEFAULT_XP_REWARD_MULTIPLIER",
    "BattleRewardResult",
    "ExperienceManager",
    "calculate_battle_xp_reward",
    "MIN_CAPTURE_PROBABILITY",
    "MAX_CAPTURE_PROBABILITY",
    "CaptureResult",
    "CaptureManager",
    "calculate_capture_probability",
    "BondManager",
    "BondChangeResult",
    "BondEventConfig",
    "DEFAULT_BOND_BATTLE_VICTORY",
    "DEFAULT_BOND_BATTLE_DEFEAT",
    "DEFAULT_BOND_LEVEL_UP",
    "DEFAULT_BOND_CAPTURE",
    "ObedienceManager",
    "ObedienceResult",
    "CommandContext",
    "calculate_obedience_probability",
    "BASE_OBEDIENCE_PROBABILITY",
    "OBEDIENCE_WEIGHT",
    "BOND_WEIGHT",
    "MIN_OBEDIENCE_PROBABILITY",
    "MAX_OBEDIENCE_PROBABILITY",
    "TrainingManager",
    "TrainingResult",
    "TrainingConfig",
    "SUPPORTED_TRAINING_STATS",
    "DEFAULT_TRAINING_AMOUNT",
    "DEFAULT_STAT_CAP",
    "DEFAULT_STAT_CAPS",
    "DEFAULT_MAX_MOVES",
    "MoveLearnResult",
    "MoveForgetResult",
    "MoveReplaceResult",
    "PendingMove",
    "LevelUpMoveProgressionResult",
    "MoveManager",
    "StatusEffectType",
    "AttackEffect",
    "StatusEffect",
    "DEFAULT_BURN_DAMAGE_FRACTION",
    "DEFAULT_POISON_DAMAGE_FRACTION",
    "DEFAULT_PARALYSIS_CHANCE",
    "DEFAULT_STAT_REDUCTION_DURATION",
    "DEFAULT_STAT_REDUCTION_MULTIPLIER",
    "EffectApplicationResult",
    "ActionCheckResult",
    "EndOfTurnEffectRecord",
    "EndOfTurnResult",
    "StatusEffectManager",
    "ItemType",
    "Item",
    "ItemStack",
    "Inventory",
    "DEFAULT_INVENTORY_CAPACITY",
    "ItemUseResult",
    "ItemManager",
    "CURRENT_SCHEMA_VERSION",
    "SaveDataError",
    "validate_schema_version",
    "serialize_player",
    "deserialize_player",
    "save_game",
    "load_game",
    "save_game_with_ai",
    "load_game_with_ai",
    "load_game_with_trainers",
    "SaveManager",
    "QuestStatus",
    "ObjectiveType",
    "QuestEventType",
    "QuestObjective",
    "QuestDefinition",
    "ObjectiveProgress",
    "QuestProgress",
    "QuestEvent",
    "QuestNotification",
    "QuestActionResult",
    "EventResult",
    "QuestRewardResult",
    "QuestManager",
    "make_progress_bar",
    "ObjectiveEntryView",
    "QuestEntryView",
    "QuestJournal",
    "InteractableType",
    "Interactable",
    "InteractionResult",
    "WorldInteractionManager",
    "WorldRegion",
    "ExplorationResult",
    "WorldExplorationManager",
    "TimeOfDay",
    "Rarity",
    "SpawnCandidate",
    "Habitat",
    "SpawnSelectionResult",
    "HabitatEncounterResult",
    "get_time_of_day",
    "HabitatManager",
    "NPC",
    "DifficultyProfile",
    "TrainerArchetype",
    "Trainer",
    "TrainerTeamGenerator",
    "calculate_player_party_strength",
    "get_eligible_species_for_trainer",
    "generate_pokemon_for_trainer",
    "generate_trainer_team",
    "create_trainer",
    "TrainerActionType",
    "TrainerDecision",
    "TrainerAIDecisionModel",
    "TrainerManager",
    "create_default_trainers",
    "create_default_trainer_manager",
    "DEFAULT_TRAINERS_FILENAME",
    "get_trainer_state_path_for_save_file",
]
