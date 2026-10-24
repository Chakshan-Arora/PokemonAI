"""
Perception and context construction for autonomous Pokemon agents.
Assembles only the information a Pokemon can realistically observe or perceive,
avoiding omniscient game engine state leakage.
"""
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

from src.ai.agent import PokemonAgent
from src.models.pokemon import Pokemon
from src.models.player import Player


@dataclass
class AgentPerception:
    """
    Sensory and situational context perceived by a Pokemon agent for decision making.
    """
    agent_id: str
    species: str
    physical_state: dict[str, Any] = field(default_factory=dict)
    trainer_context: Optional[dict[str, Any]] = None
    opponent_context: Optional[dict[str, Any]] = None
    environment_context: dict[str, Any] = field(default_factory=dict)
    relevant_memories: list[str] = field(default_factory=list)
    active_goals: list[str] = field(default_factory=list)
    available_actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serializes perception context for AI model consumption."""
        return {
            "agent_id": self.agent_id,
            "species": self.species,
            "physical_state": dict(self.physical_state),
            "trainer_context": dict(self.trainer_context) if self.trainer_context else None,
            "opponent_context": dict(self.opponent_context) if self.opponent_context else None,
            "environment_context": dict(self.environment_context),
            "relevant_memories": list(self.relevant_memories),
            "active_goals": list(self.active_goals),
            "available_actions": list(self.available_actions),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentPerception":
        """Reconstructs perception context from dictionary."""
        if not isinstance(data, dict):
            raise TypeError("AgentPerception data must be a dictionary.")
        return cls(
            agent_id=str(data.get("agent_id", "")),
            species=str(data.get("species", "Unknown")),
            physical_state=dict(data.get("physical_state", {})),
            trainer_context=data.get("trainer_context"),
            opponent_context=data.get("opponent_context"),
            environment_context=dict(data.get("environment_context", {})),
            relevant_memories=list(data.get("relevant_memories", [])),
            active_goals=list(data.get("active_goals", [])),
            available_actions=list(data.get("available_actions", [])),
        )


class PerceptionBuilder:
    """
    Assembles authoritative game data and agent memories into realistic agent perception.
    """

    @staticmethod
    def build(
        agent: PokemonAgent,
        pokemon: Pokemon,
        player: Optional[Player] = None,
        opponent: Optional[Pokemon] = None,
        command: Optional[str] = None,
        command_intent: str = "tactical",
        tone: str = "neutral",
        region_id: Optional[str] = None,
        time_of_day: Optional[str] = None,
        battle: Optional[Any] = None,
        additional_context: Optional[dict[str, Any]] = None,
    ) -> AgentPerception:
        """
        Builds a filtered AgentPerception tailored to the agent's point of view.
        """
        if not isinstance(agent, PokemonAgent):
            raise TypeError("agent must be a PokemonAgent instance.")
        if not isinstance(pokemon, Pokemon):
            raise TypeError("pokemon must be a Pokemon instance.")

        # 1. Physical State (Self perception)
        hp_ratio = round(pokemon.current_hp / max(1, pokemon.max_hp), 2)
        known_moves = [atk.name for atk in pokemon.attacks]
        physical_state = {
            "current_hp": pokemon.current_hp,
            "max_hp": pokemon.max_hp,
            "hp_ratio": hp_ratio,
            "is_fainted": pokemon.is_fainted,
            "level": pokemon.level,
            "known_moves": known_moves,
            "status_effects": [eff.value for eff in getattr(pokemon, "status_effects", [])],
        }

        # 2. Trainer Context (if owned/interacting)
        trainer_context: Optional[dict[str, Any]] = None
        if player is not None:
            rel = agent.get_relationship(player.unique_id, default_name=player.name, default_type="trainer")
            trainer_context = {
                "trainer_id": player.unique_id,
                "trainer_name": player.name,
                "command": command,
                "command_intent": command_intent,
                "tone": tone,
                "trust": rel.trust,
                "affection": rel.affection,
                "relationship_stage": rel.stage.value,
            }

        # 3. Opponent Context (Visually perceived info only)
        opponent_context: Optional[dict[str, Any]] = None
        if opponent is not None:
            opp_ratio = opponent.current_hp / max(1, opponent.max_hp)
            if opp_ratio <= 0.30:
                apparent_health = "critical"
            elif opp_ratio <= 0.65:
                apparent_health = "wounded"
            else:
                apparent_health = "healthy"

            opponent_context = {
                "species": opponent.species.name,
                "level": opponent.level,
                "apparent_health": apparent_health,
                "is_fainted": opponent.is_fainted,
            }

        # 4. Environment Context
        environment_context = {
            "region_id": region_id or "unknown_area",
            "time_of_day": time_of_day or "day",
            "in_battle": (battle is not None),
        }
        if additional_context:
            environment_context.update(additional_context)

        # 5. Relevant Memories
        relevant_memories: list[str] = []
        # Include top recent episodes involving player or opponent
        entities_to_check = []
        if player:
            entities_to_check.append(player.unique_id)
        if opponent:
            entities_to_check.append(opponent.unique_id)

        for ep in agent.memory.episodic.get_recent_episodes(limit=4):
            relevant_memories.append(f"[{ep.event_type}] {ep.summary} (impact: {ep.emotional_impact:+.1f})")

        # 6. Active Goals
        active_goals = [
            g.get("description", "") for g in agent.goals.immediate_goals if g.get("status") == "active"
        ]
        if not active_goals:
            active_goals = [
                g.get("description", "") for g in agent.goals.long_term_goals if g.get("status") == "active"
            ]

        # 7. Available Actions
        available_actions = ["hesitate", "rest"]
        if not pokemon.is_fainted:
            if known_moves:
                available_actions.append("attack")
            if battle is not None:
                available_actions.extend(["defend", "flee", "inspect"])
            if player is not None:
                available_actions.extend(["obey", "disobey", "suggest", "protest"])
                if agent.is_captured:
                    available_actions.append("request_release")
            else:
                available_actions.extend(["inspect", "flee", "interact"])

        return AgentPerception(
            agent_id=agent.agent_id,
            species=agent.species,
            physical_state=physical_state,
            trainer_context=trainer_context,
            opponent_context=opponent_context,
            environment_context=environment_context,
            relevant_memories=relevant_memories,
            active_goals=active_goals,
            available_actions=available_actions,
        )
