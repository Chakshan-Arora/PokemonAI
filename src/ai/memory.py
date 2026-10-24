"""
Memory architecture for autonomous Pokemon agents.
Defines three conceptual memory layers:
  1. Working Memory: Immediate context, recent observations, active intentions.
  2. Episodic Memory: Significant emotional and gameplay events (battles, acts of kindness, milestones).
  3. Long-Term Memory: Stable preferences, evolving relationships, learned tendencies, persistent goals.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid
from typing import Any, Optional, Sequence, Union


@dataclass
class WorkingMemory:
    """
    Volatile, short-term working memory representing the agent's immediate focus.
    Bounded to prevent unbounded growth.
    """
    immediate_context: dict[str, Any] = field(default_factory=dict)
    recent_interactions: list[dict[str, Any]] = field(default_factory=list)
    active_intention: Optional[dict[str, Any]] = None
    max_recent_interactions: int = 15

    def add_interaction(self, interaction: dict[str, Any]) -> None:
        """Adds a recent interaction, pruning to max_recent_interactions."""
        if not isinstance(interaction, dict):
            raise TypeError("interaction must be a dictionary.")
        self.recent_interactions.append(interaction)
        if len(self.recent_interactions) > self.max_recent_interactions:
            self.recent_interactions = self.recent_interactions[-self.max_recent_interactions:]

    def set_immediate_context(self, context: dict[str, Any]) -> None:
        """Updates immediate sensory and situational context."""
        if not isinstance(context, dict):
            raise TypeError("context must be a dictionary.")
        self.immediate_context = dict(context)

    def set_active_intention(self, intention: Optional[Union[dict[str, Any], str]]) -> None:
        """Sets or clears the current active intention."""
        if intention is None:
            self.active_intention = None
        elif isinstance(intention, str):
            self.active_intention = {"intent": intention}
        elif isinstance(intention, dict):
            self.active_intention = dict(intention)
        else:
            raise TypeError("intention must be a dictionary, string, or None.")

    def get_active_intention(self) -> Optional[dict[str, Any]]:
        """Returns the current active intention."""
        return self.active_intention

    def to_dict(self) -> dict[str, Any]:
        """Serializes working memory to a JSON-compatible dictionary."""
        return {
            "immediate_context": self.immediate_context,
            "recent_interactions": self.recent_interactions,
            "active_intention": self.active_intention,
            "max_recent_interactions": self.max_recent_interactions,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkingMemory":
        """Reconstructs working memory from a dictionary."""
        if not isinstance(data, dict):
            raise TypeError("Working memory data must be a dictionary.")
        return cls(
            immediate_context=dict(data.get("immediate_context", {})),
            recent_interactions=list(data.get("recent_interactions", [])),
            active_intention=data.get("active_intention"),
            max_recent_interactions=int(data.get("max_recent_interactions", 15)),
        )


@dataclass
class MemoryEpisode:
    """
    An episodic memory representing a significant past experience.
    """
    episode_id: str
    event_type: str
    summary: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    emotional_impact: float = 0.0  # -1.0 (traumatic/distrust) to +1.0 (ecstatic/deep bond)
    involved_entities: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.emotional_impact = max(-1.0, min(1.0, float(self.emotional_impact)))
        if not self.episode_id:
            self.episode_id = str(uuid.uuid4())

    def to_dict(self) -> dict[str, Any]:
        """Serializes episode to a JSON-compatible dictionary."""
        return {
            "episode_id": self.episode_id,
            "event_type": self.event_type,
            "summary": self.summary,
            "timestamp": self.timestamp,
            "emotional_impact": round(self.emotional_impact, 2),
            "involved_entities": list(self.involved_entities),
            "details": self.details,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryEpisode":
        """Reconstructs an episode from a dictionary."""
        if not isinstance(data, dict):
            raise TypeError("Episode data must be a dictionary.")
        return cls(
            episode_id=str(data.get("episode_id", uuid.uuid4())),
            event_type=str(data.get("event_type", "general")),
            summary=str(data.get("summary", "")),
            timestamp=str(data.get("timestamp", datetime.now(timezone.utc).isoformat())),
            emotional_impact=float(data.get("emotional_impact", 0.0)),
            involved_entities=list(data.get("involved_entities", [])),
            details=dict(data.get("details", {})),
        )


@dataclass
class EpisodicMemory:
    """
    Manages episodic memories with significance scoring and bounded storage.
    """
    episodes: list[MemoryEpisode] = field(default_factory=list)
    max_episodes: int = 50

    def record_episode(
        self,
        event_type: str,
        summary: str,
        emotional_impact: float = 0.0,
        involved_entities: Optional[Sequence[str]] = None,
        details: Optional[dict[str, Any]] = None,
        episode_id: Optional[str] = None,
    ) -> MemoryEpisode:
        """Creates, stores, and returns a new memory episode."""
        ep = MemoryEpisode(
            episode_id=episode_id or str(uuid.uuid4()),
            event_type=event_type,
            summary=summary,
            emotional_impact=emotional_impact,
            involved_entities=list(involved_entities) if involved_entities else [],
            details=dict(details) if details else {},
        )
        self.episodes.append(ep)
        self._prune_if_needed()
        return ep

    def _prune_if_needed(self) -> None:
        """
        Retains the most emotionally impactful and recent memories when capacity is exceeded.
        """
        if len(self.episodes) <= self.max_episodes:
            return

        # Score episodes: absolute emotional impact (high weight) + recency index
        # Keep the top episodes by significance
        indexed = list(enumerate(self.episodes))
        # Significance = abs(emotional_impact) * 100 + position_index * 0.5
        indexed.sort(key=lambda item: abs(item[1].emotional_impact) * 100.0 + item[0] * 0.5, reverse=True)
        keep_indices = set(idx for idx, _ in indexed[:self.max_episodes])
        self.episodes = [ep for i, ep in enumerate(self.episodes) if i in keep_indices]

    def get_recent_episodes(self, limit: int = 5) -> list[MemoryEpisode]:
        """Returns the N most recent episodic memories."""
        return self.episodes[-limit:]

    def get_episodes_with_entity(self, entity_id: str) -> list[MemoryEpisode]:
        """Finds all episodes involving a specific entity (e.g., player ID or other Pokemon)."""
        return [ep for ep in self.episodes if entity_id in ep.involved_entities]

    def to_dict(self) -> dict[str, Any]:
        """Serializes episodic memory."""
        return {
            "max_episodes": self.max_episodes,
            "episodes": [ep.to_dict() for ep in self.episodes],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EpisodicMemory":
        """Reconstructs episodic memory."""
        if not isinstance(data, dict):
            raise TypeError("Episodic memory data must be a dictionary.")
        max_eps = int(data.get("max_episodes", 50))
        episodes_raw = data.get("episodes", [])
        episodes = [MemoryEpisode.from_dict(e) for e in episodes_raw if isinstance(e, dict)]
        return cls(episodes=episodes, max_episodes=max_eps)


@dataclass
class LongTermMemory:
    """
    Stable long-term character development, preferences, and learned tendencies.
    """
    preferences: dict[str, Any] = field(default_factory=dict)
    learned_tendencies: list[str] = field(default_factory=list)
    persistent_goals: list[dict[str, Any]] = field(default_factory=list)

    def set_preference(self, key: str, value: Any) -> None:
        """Sets a personal preference (e.g., favorite food, disliked battle style)."""
        self.preferences[key] = value

    def add_learned_tendency(self, tendency: str) -> None:
        """Adds a learned behavioral tendency if not already present."""
        if tendency not in self.learned_tendencies:
            self.learned_tendencies.append(tendency)

    def add_persistent_goal(self, goal: dict[str, Any]) -> None:
        """Adds a long-term goal."""
        self.persistent_goals.append(goal)

    def to_dict(self) -> dict[str, Any]:
        """Serializes long-term memory."""
        return {
            "preferences": self.preferences,
            "learned_tendencies": list(self.learned_tendencies),
            "persistent_goals": list(self.persistent_goals),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LongTermMemory":
        """Reconstructs long-term memory."""
        if not isinstance(data, dict):
            raise TypeError("Long-term memory data must be a dictionary.")
        return cls(
            preferences=dict(data.get("preferences", {})),
            learned_tendencies=list(data.get("learned_tendencies", [])),
            persistent_goals=list(data.get("persistent_goals", [])),
        )


@dataclass
class PokemonMemory:
    """
    Unified memory container holding all three conceptual layers.
    """
    working: WorkingMemory = field(default_factory=WorkingMemory)
    episodic: EpisodicMemory = field(default_factory=EpisodicMemory)
    long_term: LongTermMemory = field(default_factory=LongTermMemory)

    def to_dict(self) -> dict[str, Any]:
        """Serializes all memory layers."""
        return {
            "working": self.working.to_dict(),
            "episodic": self.episodic.to_dict(),
            "long_term": self.long_term.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PokemonMemory":
        """Reconstructs all memory layers from dictionary."""
        if not isinstance(data, dict):
            raise TypeError("Pokemon memory data must be a dictionary.")
        return cls(
            working=WorkingMemory.from_dict(data.get("working", {})),
            episodic=EpisodicMemory.from_dict(data.get("episodic", {})),
            long_term=LongTermMemory.from_dict(data.get("long_term", {})),
        )
