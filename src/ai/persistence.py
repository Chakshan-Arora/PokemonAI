"""
Local AI memory and state persistence layer for Syntax Error 26.
Manages atomic serialization and deserialization of ai_state.json,
schema validation, backup handling, error recovery, and synchronization with game saves.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import uuid
from typing import Any, Optional, Union

from src.ai.agent import PokemonAgent
from src.models.pokemon import Pokemon
from src.models.player import Player


CURRENT_AI_SCHEMA_VERSION: int = 1
SUPPORTED_AI_SCHEMA_VERSIONS: tuple[int, ...] = (1,)
DEFAULT_AI_STATE_FILENAME: str = "ai_state.json"


class AiStateError(Exception):
    """Raised when AI state persistence, serialization, or validation fails."""
    pass


def validate_ai_schema_version(version: Any) -> int:
    """
    Validates that the provided AI schema version is supported.

    Args:
        version: The schema_version value from JSON.

    Returns:
        The validated integer schema version.

    Raises:
        AiStateError: If schema version is missing, invalid, or unsupported.
    """
    if version is None:
        raise AiStateError("AI state is missing required 'schema_version' field.")

    if not isinstance(version, int) or isinstance(version, bool):
        raise AiStateError(f"schema_version must be an integer, got {type(version).__name__}.")

    if version not in SUPPORTED_AI_SCHEMA_VERSIONS:
        raise AiStateError(
            f"Unsupported AI schema version: {version}. "
            f"Supported versions: {SUPPORTED_AI_SCHEMA_VERSIONS}."
        )

    return version


def get_ai_state_path_for_save_file(save_file_path: Union[str, Path]) -> Path:
    """
    Resolves the authoritative ai_state.json filepath co-located with a given game save file.

    Examples:
      - 'save_game.json' -> 'ai_state.json'
      - 'saves/slot1.json' -> 'saves/ai_state.json'
    """
    save_path = Path(save_file_path)
    return save_path.parent / DEFAULT_AI_STATE_FILENAME


@dataclass
class AiState:
    """
    Root container for persistent AI state across all autonomous Pokemon agents.
    Stored separately in ai_state.json.
    """
    schema_version: int = CURRENT_AI_SCHEMA_VERSION
    saved_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    agents: dict[str, PokemonAgent] = field(default_factory=dict)
    global_memory: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def register_agent(self, agent: PokemonAgent) -> None:
        """Registers or updates a PokemonAgent in the AI state."""
        if not isinstance(agent, PokemonAgent):
            raise TypeError(f"Expected PokemonAgent, got {type(agent).__name__}.")
        self.agents[agent.agent_id] = agent

    def get_agent(self, agent_id: str) -> Optional[PokemonAgent]:
        """Retrieves an agent by its agent_id (Pokemon unique_id)."""
        return self.agents.get(str(agent_id))

    def remove_agent(self, agent_id: str) -> Optional[PokemonAgent]:
        """Removes and returns an agent (e.g., when released or completely despawned)."""
        return self.agents.pop(str(agent_id), None)

    def get_or_create_agent(
        self,
        pokemon: Pokemon,
        is_wild: bool = False,
        is_captured: Optional[bool] = None,
    ) -> PokemonAgent:
        """
        Retrieves existing agent matching pokemon.unique_id, or initializes and registers a new one.
        """
        agent = self.get_agent(pokemon.unique_id)
        if agent is None:
            agent = PokemonAgent.from_pokemon(
                pokemon=pokemon,
                is_wild=is_wild,
                is_captured=is_captured,
            )
            self.register_agent(agent)
        else:
            # Sync captured / wild flags if updated
            if is_captured is not None:
                agent.is_captured = is_captured
                agent.is_wild = not is_captured
        return agent

    def sync_with_player_collection(self, player: Player) -> None:
        """
        Synchronizes AI state with player collection.
        Ensures all owned Pokemon have registered agents marked as captured,
        and establishes an initial relationship with the player if absent.
        """
        if not isinstance(player, Player):
            raise TypeError(f"Expected Player instance, got {type(player).__name__}.")

        for mon in player.collection:
            agent = self.get_or_create_agent(mon, is_wild=False, is_captured=True)
            # Ensure relationship with trainer exists
            rel = agent.get_relationship(
                entity_id=player.unique_id,
                default_name=player.name,
                default_type="trainer",
            )
            # Synchronize bond from game engine if relationship familiarity is low
            if rel.familiarity < 10.0 and getattr(mon, "bond", 0) > 0:
                rel.adjust_familiarity(mon.bond * 0.5)
                rel.adjust_trust(mon.bond * 0.3)
                rel.adjust_affection(mon.bond * 0.3)

    def to_dict(self) -> dict[str, Any]:
        """Serializes the complete AI state to a JSON-compatible dictionary."""
        return {
            "schema_version": self.schema_version,
            "saved_at": self.saved_at,
            "agents": {k: agent.to_dict() for k, agent in self.agents.items()},
            "global_memory": list(self.global_memory),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AiState":
        """Reconstructs and validates an AiState container from a dictionary."""
        if not isinstance(data, dict):
            raise AiStateError(f"AI state data must be a dictionary, got {type(data).__name__}.")

        schema_version = validate_ai_schema_version(data.get("schema_version"))
        saved_at = str(data.get("saved_at", datetime.now(timezone.utc).isoformat()))

        agents_raw = data.get("agents", {})
        if not isinstance(agents_raw, dict):
            raise AiStateError("Field 'agents' must be a dictionary mapping agent_id to agent data.")

        restored_agents: dict[str, PokemonAgent] = {}
        for agent_id, agent_data in agents_raw.items():
            if not isinstance(agent_data, dict):
                raise AiStateError(f"Agent data for '{agent_id}' must be a dictionary.")
            try:
                restored_agents[agent_id] = PokemonAgent.from_dict(agent_data)
            except Exception as e:
                raise AiStateError(f"Failed to deserialize agent '{agent_id}': {e}") from e

        global_mem = data.get("global_memory", [])
        if not isinstance(global_mem, list):
            raise AiStateError("Field 'global_memory' must be a list.")

        metadata = data.get("metadata", {})
        if not isinstance(metadata, dict):
            raise AiStateError("Field 'metadata' must be a dictionary.")

        return cls(
            schema_version=schema_version,
            saved_at=saved_at,
            agents=restored_agents,
            global_memory=list(global_mem),
            metadata=dict(metadata),
        )


def serialize_ai_state(ai_state: AiState) -> dict[str, Any]:
    """Serializes an AiState instance to a JSON-compatible dict."""
    if not isinstance(ai_state, AiState):
        raise AiStateError(f"Expected AiState instance, got {type(ai_state).__name__}.")
    return ai_state.to_dict()


def deserialize_ai_state(data: dict[str, Any]) -> AiState:
    """Deserializes a dictionary into an AiState instance with schema validation."""
    return AiState.from_dict(data)


def save_ai_state(ai_state: AiState, path: Union[str, Path]) -> None:
    """
    Atomically serializes and writes AI state to the specified JSON file path.

    Atomic guarantees:
      - Writes to a unique hidden temporary file in the destination folder.
      - Atomically replaces the destination file on success.
      - Cleans up temporary artifacts on failure.
    """
    if not isinstance(ai_state, AiState):
        raise AiStateError(f"Expected AiState instance, got {type(ai_state).__name__}.")

    target_path = Path(path)
    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        raise AiStateError(f"Failed to create directory '{target_path.parent}': {e}") from e

    data = serialize_ai_state(ai_state)

    temp_path = target_path.parent / f".tmp_{target_path.name}_{uuid.uuid4().hex}"
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True, ensure_ascii=False)
        os.replace(temp_path, target_path)
    except Exception as e:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass
        raise AiStateError(f"Failed to atomically write AI state to '{target_path}': {e}") from e


def load_ai_state(
    path: Union[str, Path],
    create_if_missing: bool = False,
) -> AiState:
    """
    Loads, validates, and reconstructs AiState from disk.

    Args:
        path: Path to the ai_state.json file.
        create_if_missing: If True and the file does not exist, returns a fresh empty AiState.

    Returns:
        Reconstructed AiState instance.

    Raises:
        AiStateError: If file is not found (when create_if_missing=False), JSON is invalid,
                      or schema/payload validation fails.
    """
    target_path = Path(path)
    if not target_path.exists() or not target_path.is_file():
        if create_if_missing:
            return AiState()
        raise AiStateError(f"AI state file not found at '{target_path}'.")

    try:
        with open(target_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise AiStateError(f"Invalid JSON in AI state file '{target_path}': {e}") from e
    except Exception as e:
        raise AiStateError(f"Failed to read AI state file '{target_path}': {e}") from e

    return deserialize_ai_state(data)
