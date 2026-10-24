"""
End-to-end integration service for autonomous wild Pokemon encounters.
Coordinates perception, AI model decision making, action execution,
memory formation, relationship evolution, and persistence synchronization.
"""
from typing import Any, Optional, Sequence, Union

from src.ai.agent import PokemonAgent
from src.ai.decision import AgentActionType, AgentDecision
from src.ai.decision_provider import DecisionProvider
from src.ai.live_provider import create_live_decision_provider
from src.ai.memory import MemoryEpisode
from src.ai.perception import AgentPerception, PerceptionBuilder
from src.ai.persistence import AiState
from src.models.attack import Attack
from src.models.player import Player
from src.models.pokemon import Pokemon
from src.models.wild_ai import WildActionType, WildDecision


class AutonomousWildService:
    """
    Service managing the lifecycle, perception, decision-making, and memory
    of autonomous wild Pokemon encounters.
    """

    @staticmethod
    def get_or_create_agent(
        pokemon: Pokemon,
        ai_state: Optional[AiState] = None,
    ) -> PokemonAgent:
        """
        Retrieves an existing agent from AiState or initializes a new autonomous
        PokemonAgent from the wild Pokemon instance.
        """
        if not isinstance(pokemon, Pokemon):
            raise TypeError(f"pokemon must be a Pokemon instance, got {type(pokemon).__name__}.")

        if ai_state is not None:
            existing = ai_state.get_agent(pokemon.unique_id)
            if existing is not None:
                return existing

        agent = PokemonAgent.from_pokemon(pokemon, is_wild=True, is_captured=False)
        if ai_state is not None:
            ai_state.register_agent(agent)
        return agent

    @staticmethod
    def decide_turn(
        agent: PokemonAgent,
        wild_pokemon: Pokemon,
        player_pokemon: Optional[Pokemon] = None,
        player: Optional[Player] = None,
        battle: Optional[Any] = None,
        provider: Optional[DecisionProvider] = None,
        region_id: Optional[str] = None,
        time_of_day: Optional[str] = None,
    ) -> WildDecision:
        """
        Executes a decision turn for an autonomous wild Pokemon:
          1. Constructs sensory & situational perception.
          2. Queries the AI decision provider (live model or mock).
          3. Validates and sanitizes the action.
          4. Maps the validated AgentDecision to a battle-engine WildDecision.
        """
        if not isinstance(agent, PokemonAgent):
            raise TypeError(f"agent must be a PokemonAgent instance, got {type(agent).__name__}.")
        if not isinstance(wild_pokemon, Pokemon):
            raise TypeError(f"wild_pokemon must be a Pokemon instance, got {type(wild_pokemon).__name__}.")

        # 1. Perception
        perception = PerceptionBuilder.build(
            agent=agent,
            pokemon=wild_pokemon,
            player=player,
            opponent=player_pokemon,
            region_id=region_id,
            time_of_day=time_of_day,
            battle=battle,
        )

        # 2. Decision Provider
        active_provider = provider or create_live_decision_provider(provider_type="auto")

        # 3. Decision & Validation (via agent.decide)
        agent_dec = agent.decide(
            perception=perception,
            provider=active_provider,
            pokemon=wild_pokemon,
        )

        # 4. Map AgentDecision to WildDecision for Battle engine
        action = agent_dec.action_type
        if action == AgentActionType.FLEE:
            wild_action = WildActionType.FLEE
            chosen_atk = None
            reason = agent_dec.rationale or f"{wild_pokemon.display_name} chose to flee from danger."
        elif action in (AgentActionType.INSPECT, AgentActionType.HESITATE, AgentActionType.REST):
            wild_action = WildActionType.INSPECT
            chosen_atk = None
            reason = agent_dec.rationale or f"{wild_pokemon.display_name} paused cautiously to observe."
        else:
            wild_action = WildActionType.ATTACK
            chosen_atk = None
            if agent_dec.chosen_move and wild_pokemon.attacks:
                norm_chosen = agent_dec.chosen_move.strip().lower()
                chosen_atk = next((a for a in wild_pokemon.attacks if a.name.strip().lower() == norm_chosen), None)
            if chosen_atk is None and wild_pokemon.attacks:
                chosen_atk = wild_pokemon.attacks[0]
            reason = agent_dec.rationale or f"{wild_pokemon.display_name} attacks with {chosen_atk.name if chosen_atk else 'Struggle'}!"

        return WildDecision(
            action_type=wild_action,
            scores={wild_action: 100.0},
            reason=reason,
            chosen_attack=chosen_atk,
            factors={
                "agent_id": agent.agent_id,
                "agent_decision": agent_dec.to_dict(),
                "emotional_state": agent_dec.emotional_state,
                "dialogue": agent_dec.dialogue,
                "confidence": agent_dec.confidence,
            },
        )

    @staticmethod
    def record_combat_damage(
        agent: PokemonAgent,
        damage: int,
        attacker_pokemon: Optional[Pokemon] = None,
        player: Optional[Player] = None,
    ) -> MemoryEpisode:
        """
        Records an episodic memory when the wild agent takes damage in battle.
        Reduces trust towards the attacking trainer.
        """
        entities = []
        if player:
            entities.append(player.unique_id)
        if attacker_pokemon:
            entities.append(attacker_pokemon.unique_id)

        attacker_name = attacker_pokemon.display_name if attacker_pokemon else "opponent"
        ep = agent.record_experience(
            event_type="combat_damage",
            summary=f"Took {damage} damage from {attacker_name}",
            emotional_impact=-0.2 - min(0.6, damage / 50.0),
            involved_entities=entities,
            details={"damage": damage, "attacker": attacker_name},
        )

        if player:
            rel = agent.get_relationship(player.unique_id, default_name=player.name, default_type="trainer")
            rel.adjust_trust(-2.0)
            rel.adjust_familiarity(1.0)
            rel.add_memory(ep.episode_id)

        return ep

    @staticmethod
    def record_combat_strike(
        agent: PokemonAgent,
        damage: int,
        attack_name: str,
        defender_pokemon: Optional[Pokemon] = None,
    ) -> MemoryEpisode:
        """
        Records an episodic memory when the wild agent successfully strikes in combat.
        """
        entities = [defender_pokemon.unique_id] if defender_pokemon else []
        def_name = defender_pokemon.display_name if defender_pokemon else "opponent"
        return agent.record_experience(
            event_type="combat_strike",
            summary=f"Struck {def_name} with {attack_name} for {damage} damage",
            emotional_impact=0.2,
            involved_entities=entities,
            details={"damage": damage, "attack": attack_name},
        )

    @staticmethod
    def record_observation(
        agent: PokemonAgent,
        target_name: str,
        details: Optional[str] = None,
        player: Optional[Player] = None,
    ) -> MemoryEpisode:
        """
        Records an episodic memory when the wild agent inspects or observes the player.
        Gains familiarity with the trainer.
        """
        entities = [player.unique_id] if player else []
        summary = details or f"Observed {target_name} curiously from afar"
        ep = agent.record_experience(
            event_type="encounter_inspect",
            summary=summary,
            emotional_impact=0.1,
            involved_entities=entities,
        )
        if player:
            rel = agent.get_relationship(player.unique_id, default_name=player.name, default_type="trainer")
            rel.adjust_familiarity(5.0)
            rel.add_memory(ep.episode_id)
        return ep

    @staticmethod
    def record_encounter_concluded(
        agent: PokemonAgent,
        outcome: str,
        player: Optional[Player] = None,
    ) -> MemoryEpisode:
        """
        Records the outcome of the encounter (escaped, captured, fainted, victory).
        Updates ownership status if captured.
        """
        entities = [player.unique_id] if player else []
        trainer_name = player.name if player else "Trainer"

        if outcome == "captured":
            summary = f"Captured by {trainer_name}"
            impact = -0.15
            agent.is_captured = True
            agent.is_wild = False
        elif outcome == "escaped":
            summary = f"Fled and retreated from battle with {trainer_name}"
            impact = -0.1
        elif outcome == "victory":
            summary = f"Defeated {trainer_name}'s Pokemon in battle"
            impact = 0.5
        elif outcome == "fainted":
            summary = f"Fainted in battle against {trainer_name}"
            impact = -0.5
        else:
            summary = f"Encounter with {trainer_name} ended ({outcome})"
            impact = 0.0

        ep = agent.record_experience(
            event_type=f"encounter_{outcome}",
            summary=summary,
            emotional_impact=impact,
            involved_entities=entities,
        )
        if player:
            rel = agent.get_relationship(player.unique_id, default_name=player.name, default_type="trainer")
            rel.adjust_familiarity(2.0)
            rel.add_memory(ep.episode_id)

        return ep
