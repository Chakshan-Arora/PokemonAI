"""
Autonomous Pokemon agent representation.
Maintains identity, drives, goals, beliefs, relationships, and multi-tier memory.
Integrates with authoritative game systems while allowing the agent to make independent decisions.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid
from typing import TYPE_CHECKING, Any, Optional, Sequence, Union

from src.ai.decision import AgentActionType, AgentDecision
from src.ai.memory import PokemonMemory, WorkingMemory, EpisodicMemory, LongTermMemory, MemoryEpisode
from src.ai.relationships import Relationship, RelationshipStage
from src.models.pokemon import Pokemon
from src.models.personality import Personality

if TYPE_CHECKING:
    from src.ai.perception import AgentPerception
    from src.ai.decision_provider import DecisionProvider
    from src.ai.action_validator import ActionValidator


@dataclass
class AgentIdentity:
    """
    Core identity, temperament, and inherent traits of a Pokemon agent.
    """
    species: str
    nickname: Optional[str] = None
    personality_traits: dict[str, int] = field(default_factory=dict)
    temperament: str = "balanced"
    communication_style: str = "expressive"

    def to_dict(self) -> dict[str, Any]:
        """Serializes agent identity."""
        return {
            "species": self.species,
            "nickname": self.nickname,
            "personality_traits": dict(self.personality_traits),
            "temperament": self.temperament,
            "communication_style": self.communication_style,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentIdentity":
        """Reconstructs agent identity."""
        if not isinstance(data, dict):
            raise TypeError("Identity data must be a dictionary.")
        return cls(
            species=str(data.get("species", "Unknown")),
            nickname=data.get("nickname"),
            personality_traits=dict(data.get("personality_traits", {})),
            temperament=str(data.get("temperament", "balanced")),
            communication_style=str(data.get("communication_style", "expressive")),
        )


@dataclass
class AgentGoals:
    """
    Immediate and long-term intentions and motivations.
    """
    immediate_goals: list[dict[str, Any]] = field(default_factory=list)
    long_term_goals: list[dict[str, Any]] = field(default_factory=list)

    def add_immediate_goal(self, description: str, priority: int = 1, status: str = "active") -> None:
        """Adds an immediate actionable goal."""
        self.immediate_goals.append({
            "goal_id": str(uuid.uuid4())[:8],
            "description": description,
            "priority": priority,
            "status": status,
        })

    def add_long_term_goal(self, description: str, motivation: str = "", status: str = "active") -> None:
        """Adds an overarching character goal."""
        self.long_term_goals.append({
            "goal_id": str(uuid.uuid4())[:8],
            "description": description,
            "motivation": motivation,
            "status": status,
        })

    def to_dict(self) -> dict[str, Any]:
        """Serializes goals."""
        return {
            "immediate_goals": list(self.immediate_goals),
            "long_term_goals": list(self.long_term_goals),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentGoals":
        """Reconstructs goals."""
        if not isinstance(data, dict):
            raise TypeError("Goals data must be a dictionary.")
        return cls(
            immediate_goals=list(data.get("immediate_goals", [])),
            long_term_goals=list(data.get("long_term_goals", [])),
        )


@dataclass
class AgentBeliefs:
    """
    What the agent perceives, understands, or misunderstands about the world and player.
    """
    perceived_player_intent: str = "neutral"
    world_beliefs: list[str] = field(default_factory=list)
    situational_beliefs: dict[str, Any] = field(default_factory=dict)

    def add_world_belief(self, belief: str) -> None:
        """Adds a persistent world belief."""
        if belief not in self.world_beliefs:
            self.world_beliefs.append(belief)

    def to_dict(self) -> dict[str, Any]:
        """Serializes beliefs."""
        return {
            "perceived_player_intent": self.perceived_player_intent,
            "world_beliefs": list(self.world_beliefs),
            "situational_beliefs": dict(self.situational_beliefs),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentBeliefs":
        """Reconstructs beliefs."""
        if not isinstance(data, dict):
            raise TypeError("Beliefs data must be a dictionary.")
        return cls(
            perceived_player_intent=str(data.get("perceived_player_intent", "neutral")),
            world_beliefs=list(data.get("world_beliefs", [])),
            situational_beliefs=dict(data.get("situational_beliefs", {})),
        )


class PokemonAgent:
    """
    Individual AI agent representing a single Pokemon.
    Maintains autonomous drives, distinct relationships, memory layers, and goals.
    """

    def __init__(
        self,
        agent_id: str,
        identity: AgentIdentity,
        memory: Optional[PokemonMemory] = None,
        relationships: Optional[dict[str, Relationship]] = None,
        goals: Optional[AgentGoals] = None,
        beliefs: Optional[AgentBeliefs] = None,
        is_wild: bool = True,
        is_captured: bool = False,
        last_decision: Optional[dict[str, Any]] = None,
    ) -> None:
        if not agent_id or not str(agent_id).strip():
            raise ValueError("agent_id must be a non-empty string.")
        if not isinstance(identity, AgentIdentity):
            raise TypeError("identity must be an AgentIdentity instance.")

        self.agent_id: str = str(agent_id).strip()
        self.identity: AgentIdentity = identity
        self.memory: PokemonMemory = memory if memory is not None else PokemonMemory()
        self.relationships: dict[str, Relationship] = dict(relationships) if relationships is not None else {}
        self.goals: AgentGoals = goals if goals is not None else AgentGoals()
        self.beliefs: AgentBeliefs = beliefs if beliefs is not None else AgentBeliefs()
        self.is_wild: bool = bool(is_wild)
        self.is_captured: bool = bool(is_captured)
        self.last_decision: Optional[dict[str, Any]] = last_decision

    @property
    def species(self) -> str:
        """Returns the Pokemon species name."""
        return self.identity.species

    @property
    def display_name(self) -> str:
        """Returns nickname if set, else species name."""
        return self.identity.nickname or self.identity.species

    def get_relationship(
        self,
        entity_id: str,
        default_name: str = "Unknown",
        default_type: str = "trainer",
    ) -> Relationship:
        """
        Retrieves the relationship with entity_id, creating an initial stranger relationship if absent.
        """
        if entity_id not in self.relationships:
            self.relationships[entity_id] = Relationship(
                entity_id=entity_id,
                entity_name=default_name,
                entity_type=default_type,
            )
        return self.relationships[entity_id]

    def record_experience(
        self,
        event_type: str,
        summary: str,
        emotional_impact: float = 0.0,
        involved_entities: Optional[Sequence[str]] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> MemoryEpisode:
        """
        Records a significant episodic experience and links it to involved entity relationships.
        """
        ep = self.memory.episodic.record_episode(
            event_type=event_type,
            summary=summary,
            emotional_impact=emotional_impact,
            involved_entities=involved_entities,
            details=details,
        )
        if involved_entities:
            for ent_id in involved_entities:
                if ent_id in self.relationships:
                    self.relationships[ent_id].add_memory(ep.episode_id)
        return ep

    def decide(
        self,
        perception: "AgentPerception",
        provider: "DecisionProvider",
        validator: Optional[Any] = None,
        fallback_handler: Optional[Any] = None,
        pokemon: Optional[Pokemon] = None,
    ) -> AgentDecision:
        """
        Assembles perception and uses the decision provider to generate an autonomous decision.
        Gracefully handles errors via fallback, validates the decision against game constraints,
        and records the intention into working memory.
        """
        try:
            decision = provider.decide(self, perception)
        except Exception as exc:
            if fallback_handler is not None and hasattr(fallback_handler, "create_fallback"):
                decision = fallback_handler.create_fallback(self, perception, exc)
            else:
                from src.ai.decision_provider import FallbackDecisionHandler
                decision = FallbackDecisionHandler.create_fallback(self, perception, exc)

        # Validate decision if validator is enabled (defaults to ActionValidator if None)
        active_validator = validator
        if active_validator is None:
            from src.ai.action_validator import ActionValidator
            active_validator = ActionValidator

        if active_validator is not False:
            if hasattr(active_validator, "validate"):
                val_result = active_validator.validate(
                    decision=decision,
                    pokemon=pokemon,
                    is_captured=self.is_captured,
                    perception=perception,
                )
                decision = val_result.sanitized_decision
            elif callable(active_validator):
                val_result = active_validator(decision)
                decision = getattr(val_result, "sanitized_decision", val_result)

        # Update working memory and agent tracking
        self.memory.working.set_active_intention(decision.intent)
        self.last_decision = decision.to_dict()

        return decision

    @classmethod
    def from_pokemon(
        cls,
        pokemon: Pokemon,
        is_wild: bool = False,
        is_captured: Optional[bool] = None,
    ) -> "PokemonAgent":
        """
        Factory method constructing an autonomous agent from an authoritative Pokemon instance.
        Preserves existing personality traits and generates an initial identity.
        """
        if not isinstance(pokemon, Pokemon):
            raise TypeError(f"pokemon must be a Pokemon instance, got {type(pokemon).__name__}.")

        pers = getattr(pokemon, "personality", None)
        pers_dict = pers.to_dict() if pers is not None else {}

        # Derive initial temperament from personality
        agg = pers_dict.get("aggression", 50)
        fear = pers_dict.get("fear", 50)
        cur = pers_dict.get("curiosity", 50)
        conf = pers_dict.get("confidence", 50)
        soc = pers_dict.get("sociability", 50)

        if fear >= 70:
            temperament = "cautious"
        elif agg >= 70:
            temperament = "aggressive"
        elif cur >= 70:
            temperament = "curious"
        elif conf >= 70:
            temperament = "bold"
        elif soc >= 70:
            temperament = "friendly"
        else:
            temperament = "balanced"

        identity = AgentIdentity(
            species=pokemon.species.name,
            nickname=getattr(pokemon, "nickname", None),
            personality_traits=pers_dict,
            temperament=temperament,
        )

        captured_flag = (not is_wild) if is_captured is None else bool(is_captured)
        return cls(
            agent_id=pokemon.unique_id,
            identity=identity,
            is_wild=bool(is_wild),
            is_captured=captured_flag,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serializes agent state for persistence in ai_state.json."""
        return {
            "agent_id": self.agent_id,
            "identity": self.identity.to_dict(),
            "memory": self.memory.to_dict(),
            "relationships": {k: rel.to_dict() for k, rel in self.relationships.items()},
            "goals": self.goals.to_dict(),
            "beliefs": self.beliefs.to_dict(),
            "is_wild": self.is_wild,
            "is_captured": self.is_captured,
            "last_decision": self.last_decision,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PokemonAgent":
        """Reconstructs agent from dictionary."""
        if not isinstance(data, dict):
            raise TypeError("Agent data must be a dictionary.")

        agent_id = str(data.get("agent_id", "")).strip()
        if not agent_id:
            raise ValueError("Missing agent_id in agent data.")

        identity_raw = data.get("identity", {})
        identity = AgentIdentity.from_dict(identity_raw)

        memory_raw = data.get("memory", {})
        memory = PokemonMemory.from_dict(memory_raw) if memory_raw else PokemonMemory()

        rels_raw = data.get("relationships", {})
        relationships = {
            k: Relationship.from_dict(v) for k, v in rels_raw.items() if isinstance(v, dict)
        }

        goals_raw = data.get("goals", {})
        goals = AgentGoals.from_dict(goals_raw) if goals_raw else AgentGoals()

        beliefs_raw = data.get("beliefs", {})
        beliefs = AgentBeliefs.from_dict(beliefs_raw) if beliefs_raw else AgentBeliefs()

        return cls(
            agent_id=agent_id,
            identity=identity,
            memory=memory,
            relationships=relationships,
            goals=goals,
            beliefs=beliefs,
            is_wild=bool(data.get("is_wild", True)),
            is_captured=bool(data.get("is_captured", False)),
            last_decision=data.get("last_decision"),
        )
