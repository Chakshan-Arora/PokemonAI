"""
Syntax Error 26 - Autonomous Pokemon AI Architecture.
Provides independent, agent-driven Pokemon intelligence, memory layers,
relationship tracking, and local AI state persistence.
"""
from src.ai.memory import (
    WorkingMemory,
    MemoryEpisode,
    EpisodicMemory,
    LongTermMemory,
    PokemonMemory,
)
from src.ai.relationships import (
    Relationship,
    RelationshipStage,
)
from src.ai.agent import (
    AgentIdentity,
    AgentGoals,
    AgentBeliefs,
    PokemonAgent,
)
from src.ai.decision import (
    AgentActionType,
    AgentDecision,
)
from src.ai.perception import (
    AgentPerception,
    PerceptionBuilder,
)
from src.ai.action_validator import (
    ActionValidator,
    ValidationResult,
)
from src.ai.decision_provider import (
    DecisionProvider,
    MockDecisionProvider,
    FallbackDecisionHandler,
)
from src.ai.live_provider import (
    GEMINI_API_KEY_PLACEHOLDER,
    OPENAI_API_KEY_PLACEHOLDER,
    DEFAULT_GEMINI_MODEL,
    DEFAULT_OPENAI_MODEL,
    AiConfigurationError,
    AiModelServiceError,
    PromptBuilder,
    DecisionResponseParser,
    BaseLiveDecisionProvider,
    GeminiDecisionProvider,
    OpenAIDecisionProvider,
    LiveAIDecisionProvider,
    create_live_decision_provider,
)
from src.ai.local_model_provider import (
    LocalModelDecisionProvider,
    LocalModelError,
)
from src.ai.wild_encounter_service import AutonomousWildService
# from src.ai.battle_talk_parser import BattleTalkParser, parse as parse_battle_talk
# from src.ai.battle_talk import parse_battle_talk_intent
from src.ai.companion_service import (
    CompanionService,
    CompanionInteractionResult,
    CompanionBattleDisposition,
    TeammateInteractionResult,
    # BattleTalkContext,
    # generate_battle_talk_response,
)
# from src.ai.voice_input import (
#     VoiceInputService,
#     VoiceInputResult,
#     VoiceInputErrorType,
# )
from src.ai.scheduler import AutonomousWorldScheduler
from src.ai.persistence import (
    CURRENT_AI_SCHEMA_VERSION,
    SUPPORTED_AI_SCHEMA_VERSIONS,
    DEFAULT_AI_STATE_FILENAME,
    AiStateError,
    AiState,
    validate_ai_schema_version,
    get_ai_state_path_for_save_file,
    serialize_ai_state,
    deserialize_ai_state,
    save_ai_state,
    load_ai_state,
)

__all__ = [
    "WorkingMemory",
    "MemoryEpisode",
    "EpisodicMemory",
    "LongTermMemory",
    "PokemonMemory",
    "Relationship",
    "RelationshipStage",
    "AgentIdentity",
    "AgentGoals",
    "AgentBeliefs",
    "PokemonAgent",
    "AgentActionType",
    "AgentDecision",
    "AgentPerception",
    "PerceptionBuilder",
    "ActionValidator",
    "ValidationResult",
    "DecisionProvider",
    "MockDecisionProvider",
    "FallbackDecisionHandler",
    "GEMINI_API_KEY_PLACEHOLDER",
    "OPENAI_API_KEY_PLACEHOLDER",
    "DEFAULT_GEMINI_MODEL",
    "DEFAULT_OPENAI_MODEL",
    "AiConfigurationError",
    "AiModelServiceError",
    "PromptBuilder",
    "DecisionResponseParser",
    "BaseLiveDecisionProvider",
    "GeminiDecisionProvider",
    "OpenAIDecisionProvider",
    "LiveAIDecisionProvider",
    "create_live_decision_provider",
    "LocalModelDecisionProvider",
    "LocalModelError",
    "AutonomousWildService",
    "CompanionService",
    "CompanionInteractionResult",
    "CompanionBattleDisposition",
    "TeammateInteractionResult",
    # "BattleTalkParser",
    # "parse_battle_talk",
    # "parse_battle_talk_intent",
    # "BattleTalkContext",
    # "generate_battle_talk_response",
#     "VoiceInputService",
#     "VoiceInputResult",
#     "VoiceInputErrorType",
    "AutonomousWorldScheduler",
    "CURRENT_AI_SCHEMA_VERSION",
    "SUPPORTED_AI_SCHEMA_VERSIONS",
    "DEFAULT_AI_STATE_FILENAME",
    "AiStateError",
    "AiState",
    "validate_ai_schema_version",
    "get_ai_state_path_for_save_file",
    "serialize_ai_state",
    "deserialize_ai_state",
    "save_ai_state",
    "load_ai_state",
]
