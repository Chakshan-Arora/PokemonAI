"""
Companion Pokemon intelligence and interaction service.
Coordinates autonomous companion decision-making, trainer interactions
(talk, praise, scold, release requests), relationship evolution,
battle tactical compliance/disobedience, and teammate social dynamics.
"""
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence, Union

from src.ai.agent import PokemonAgent
from src.ai.decision import AgentActionType, AgentDecision
from src.ai.decision_provider import DecisionProvider
from src.ai.live_provider import create_live_decision_provider
from src.ai.memory import MemoryEpisode
from src.ai.perception import AgentPerception, PerceptionBuilder
from src.ai.persistence import AiState
from src.ai.relationships import Relationship, RelationshipStage
from src.models.attack import Attack
from src.models.bond_manager import BondManager
from src.models.player import Player
from src.models.pokemon import Pokemon


@dataclass(frozen=True)
class CompanionInteractionResult:
    """
    Structured outcome of an interaction between trainer and companion Pokemon.
    """
    decision: AgentDecision
    dialogue: str
    reaction_summary: str
    bond_change: int
    trust_change: float
    affection_change: float
    stage: RelationshipStage
    requested_release: bool = False
    released: bool = False
    memory_episode: Optional[MemoryEpisode] = None
    inferred_type: str = "talk"


@dataclass(frozen=True)
class CompanionBattleDisposition:
    """
    Tactical compliance outcome when a companion Pokemon receives a battle order.
    """
    action_type: AgentActionType
    chosen_attack: Attack
    dialogue: str
    is_obedient: bool
    rationale: str
    confidence: float
    suggested_alternative: Optional[str] = None


@dataclass(frozen=True)
class TeammateInteractionResult:
    """
    Structured outcome of a social interaction between two team Pokemon.
    """
    pokemon1_dialogue: str
    pokemon2_dialogue: str
    summary: str
    mutual_familiarity_gain: float
    memory1: Optional[MemoryEpisode] = None
    memory2: Optional[MemoryEpisode] = None


class CompanionService:
    """
    Service managing autonomous companion Pokemon intelligence, trainer interactions,
    obedience dynamics, goals, and social relationships within the player's team.
    """

    @staticmethod
    def get_or_create_companion_agent(
        pokemon: Pokemon,
        ai_state: Optional[AiState] = None,
        player: Optional[Player] = None,
    ) -> PokemonAgent:
        """
        Retrieves an existing agent from AiState or initializes a companion agent
        with established relationship and default character goals.
        """
        if not isinstance(pokemon, Pokemon):
            raise TypeError(f"pokemon must be a Pokemon instance, got {type(pokemon).__name__}.")

        if ai_state is not None:
            existing = ai_state.get_agent(pokemon.unique_id)
            if existing is not None:
                # Ensure companion status is up-to-date
                existing.is_captured = True
                existing.is_wild = False
                if player is not None:
                    rel = existing.get_relationship(player.unique_id, default_name=player.name, default_type="trainer")
                    if rel.trust == 0.0 and rel.affection == 0.0:
                        rel.adjust_trust(30.0)
                        rel.adjust_affection(30.0)
                        rel.adjust_familiarity(25.0)
                return existing

        agent = PokemonAgent.from_pokemon(pokemon, is_wild=False, is_captured=True)

        # Initialize trainer relationship
        if player is not None:
            rel = agent.get_relationship(player.unique_id, default_name=player.name, default_type="trainer")
            rel.adjust_trust(30.0)
            rel.adjust_affection(30.0)
            rel.adjust_familiarity(25.0)

        # Seed default companion goals if empty
        if not agent.goals.immediate_goals:
            agent.goals.add_immediate_goal(f"Train with {player.name if player else 'Trainer'} and grow stronger", priority=1)
        if not agent.goals.long_term_goals:
            agent.goals.add_long_term_goal("Become a formidable and reliable battle partner")

        if ai_state is not None:
            ai_state.register_agent(agent)

        return agent

    @staticmethod
    def infer_intent_from_message(message: str) -> tuple[str, str]:
        """
        Infers interaction intent and emotional tone from player's natural language input.
        Returns:
            (interaction_type, tone) e.g. ('praise', 'supportive'), ('scold', 'harsh'), etc.
        """
        msg = message.lower().strip()

        # Release keywords
        release_words = (
            "release", "set free", "set you free", "setting you free", "setting free",
            "leave the team", "go back to the wild", "return to the wild", "goodbye",
            "farewell", "part ways", "free you", "freedom"
        )
        if any(w in msg for w in release_words):
            return "discuss_release", "serious"

        # Goals keywords
        goal_words = ("goal", "goals", "dream", "dreams", "aspiration", "aspirations", "ambition", "future", "what do you want")
        if any(w in msg for w in goal_words):
            return "discuss_goals", "friendly"

        # Praise keywords
        praise_words = (
            "good job", "great job", "well done", "awesome", "proud", "amazing",
            "love you", "thank", "thanks", "brave", "hero", "pat", "hug", "pet",
            "sweet", "best partner", "good boy", "good girl", "congrats",
            "congratulations", "nice work", "super", "fantastic", "brilliant",
            "nice", "good", "praise", "praising", "encourage"
        )
        if any(w in msg for w in praise_words):
            return "praise", "supportive"

        # Scold keywords
        scold_words = (
            "bad", "terrible", "awful", "disappointed", "angry", "useless", "stupid",
            "idiot", "scold", "shame", "hate", "pathetic", "weak", "fail", "horrible",
            "listen to me", "be quiet", "shut up", "get lost", "stop it", "fool"
        )
        if any(w in msg for w in scold_words):
            return "scold", "harsh"

        return "talk", "friendly"

    @staticmethod
    def interact(
        agent: PokemonAgent,
        pokemon: Pokemon,
        player: Player,
        interaction_type: str = "talk",
        message: Optional[str] = None,
        provider: Optional[DecisionProvider] = None,
        bond_manager: Optional[BondManager] = None,
        ai_state: Optional[AiState] = None,
    ) -> CompanionInteractionResult:
        """
        Processes an interactive conversation or action between trainer and companion Pokemon:
          - 'talk' / 'free_talk': conversational inquiry or open chat
          - 'praise' / 'encourage': positive reinforcement and bonding
          - 'scold' / 'criticize': frustration or scolding
          - 'discuss_goals': inquiring about aspirations and goals
          - 'discuss_release': discussing leaving the team
        """
        if not isinstance(agent, PokemonAgent):
            raise TypeError("agent must be a PokemonAgent instance.")
        if not isinstance(pokemon, Pokemon):
            raise TypeError("pokemon must be a Pokemon instance.")
        if not isinstance(player, Player):
            raise TypeError("player must be a Player instance.")

        norm_type = interaction_type.strip().lower()
        if norm_type in ("talk", "chat", "direct", "free", "general") and message:
            inferred_type, inferred_tone = CompanionService.infer_intent_from_message(message)
            norm_type = inferred_type
            tone = inferred_tone
        else:
            inferred_tone = None

        # Determine emotional tone and prompt framing
        if norm_type in ("praise", "encourage"):
            tone = inferred_tone or "supportive"
            prompt_intent = "praise"
            default_text = message or f"{player.name} smiles warmly, patting {pokemon.display_name} and praising their dedication."
        elif norm_type in ("scold", "criticize"):
            tone = inferred_tone or "harsh"
            prompt_intent = "scold"
            default_text = message or f"{player.name} frowns sternly, criticizing {pokemon.display_name}'s recent performance."
        elif norm_type in ("discuss_release", "request_release"):
            tone = inferred_tone or "serious"
            prompt_intent = "discuss_release"
            default_text = message or f"{player.name} speaks with {pokemon.display_name} about whether it wishes to return to the wild."
        elif norm_type == "discuss_goals":
            tone = inferred_tone or "friendly"
            prompt_intent = "inquire_goals"
            default_text = message or f"{player.name} asks {pokemon.display_name} what dreams and goals it hopes to achieve."
        else:
            tone = inferred_tone or "friendly"
            prompt_intent = "conversation"
            default_text = message or f"{player.name} kneels down and chats gently with {pokemon.display_name}."

        # Build perception
        perception = PerceptionBuilder.build(
            agent=agent,
            pokemon=pokemon,
            player=player,
            command=default_text,
            command_intent=prompt_intent,
            tone=tone,
            additional_context={"interaction_type": norm_type},
        )

        active_provider = provider or create_live_decision_provider(provider_type="auto")
        decision = agent.decide(perception=perception, provider=active_provider, pokemon=pokemon)

        # Relationship metrics
        rel = agent.get_relationship(player.unique_id, default_name=player.name, default_type="trainer")
        bond_delta = 0
        trust_delta = 0.0
        affection_delta = 0.0
        req_release = (decision.action_type == AgentActionType.REQUEST_RELEASE)

        # Apply psychological and relational consequences
        if norm_type in ("praise", "encourage"):
            trust_delta = 3.0
            affection_delta = 5.0
            rel.adjust_trust(trust_delta)
            rel.adjust_affection(affection_delta)
            rel.adjust_familiarity(2.0)
            bond_delta = 3
            if bond_manager:
                bond_manager.change_bond(pokemon, bond_delta, reason="Trainer praise")
            else:
                pokemon.bond = max(0, min(100, pokemon.bond + bond_delta))

            dialogue = decision.dialogue or f"{pokemon.display_name} beams with joy and nuzzles your hand!"
            summary = f"{pokemon.display_name} felt appreciated and gained deep affection for {player.name}."
            event_type = "trainer_praise"
            impact = 0.4

        elif norm_type in ("scold", "criticize"):
            # Reprimand/criticism: drops trust and affection
            traits = agent.identity.personality_traits
            agg = traits.get("aggression", 50)
            loy = traits.get("loyalty", 50)

            trust_delta = -3.0
            affection_delta = -6.0
            rel.adjust_trust(trust_delta)
            rel.adjust_affection(affection_delta)
            bond_delta = -2
            if bond_manager:
                bond_manager.change_bond(pokemon, bond_delta, reason="Trainer criticism")
            else:
                pokemon.bond = max(0, min(100, pokemon.bond + bond_delta))

            if agg >= 65 and loy < 60:
                dialogue = decision.dialogue or f"{pokemon.display_name} snarls defiantly and looks away in irritation!"
                summary = f"{pokemon.display_name} resented {player.name}'s harsh reprimand."
            else:
                dialogue = decision.dialogue or f"{pokemon.display_name} droops its ears in dejection and looks guilty."
                summary = f"{pokemon.display_name} felt disheartened by {player.name}'s reprimand."
            event_type = "trainer_criticism"
            impact = -0.4

        elif req_release or norm_type in ("discuss_release", "request_release"):
            dialogue = decision.dialogue or f"{pokemon.display_name} gazes toward the open wild, longing for freedom."
            summary = f"{pokemon.display_name} expressed its thoughts about freedom and the wild."
            event_type = "trainer_release_discussion"
            impact = 0.1
            rel.adjust_familiarity(3.0)

        elif norm_type == "discuss_goals":
            goals_list = [g.get("description", "") for g in agent.goals.immediate_goals + agent.goals.long_term_goals if g.get("status") == "active"]
            goals_str = "; ".join(goals_list) if goals_list else "growing stronger together"
            dialogue = decision.dialogue or f"{pokemon.display_name} shares its ambitions: {goals_str}!"
            summary = f"{pokemon.display_name} shared its aspirations and bonded with {player.name}."
            event_type = "trainer_goal_discussion"
            impact = 0.2
            rel.adjust_familiarity(4.0)

        else:
            # General conversation
            dialogue = decision.dialogue or f"{pokemon.display_name} chirps companionably, enjoying the conversation."
            summary = f"{pokemon.display_name} chatted and spent peaceful time with {player.name}."
            event_type = "trainer_conversation"
            impact = 0.15
            rel.adjust_familiarity(2.0)

        # Record episodic memory
        ep = agent.record_experience(
            event_type=event_type,
            summary=summary,
            emotional_impact=impact,
            involved_entities=[player.unique_id],
            details={"dialogue": dialogue, "intent": prompt_intent},
        )
        rel.add_memory(ep.episode_id)

        return CompanionInteractionResult(
            decision=decision,
            dialogue=dialogue,
            reaction_summary=summary,
            bond_change=bond_delta,
            trust_change=trust_delta,
            affection_change=affection_delta,
            stage=rel.stage,
            requested_release=req_release,
            released=False,
            memory_episode=ep,
            inferred_type=norm_type,
        )

    @staticmethod
    def evaluate_battle_command(
        agent: PokemonAgent,
        pokemon: Pokemon,
        player: Player,
        chosen_attack: Attack,
        opponent: Pokemon,
        battle: Optional[Any] = None,
        provider: Optional[DecisionProvider] = None,
    ) -> CompanionBattleDisposition:
        """
        Evaluates a companion Pokemon's compliance, hesitation, or tactical suggestion
        when given an attack order in battle.
        Preserves game mechanics while allowing autonomous character expression.
        """
        if not isinstance(agent, PokemonAgent):
            raise TypeError("agent must be a PokemonAgent instance.")
        if not isinstance(pokemon, Pokemon):
            raise TypeError("pokemon must be a Pokemon instance.")
        if not isinstance(chosen_attack, Attack):
            raise TypeError("chosen_attack must be an Attack instance.")

        rel = agent.get_relationship(player.unique_id, default_name=player.name, default_type="trainer")
        traits = agent.identity.personality_traits
        agg = traits.get("aggression", 50)
        fear = traits.get("fear", 50)
        loy = traits.get("loyalty", 50)
        conf = traits.get("confidence", 50)

        # Build tactical perception
        perception = PerceptionBuilder.build(
            agent=agent,
            pokemon=pokemon,
            player=player,
            opponent=opponent,
            command=chosen_attack.name,
            command_intent="attack",
            tone="tactical",
            battle=battle,
        )

        active_provider = provider or create_live_decision_provider(provider_type="auto")
        decision = agent.decide(perception=perception, provider=active_provider, pokemon=pokemon)

        # Heuristic obedience check:
        # A companion is fully obedient if trust > -20 and relationship is not RESENTFUL
        is_resentful = (rel.stage == RelationshipStage.RESENTFUL or rel.trust <= -40.0)
        low_obedience = (pokemon.obedience < 20 or (fear >= 85 and conf <= 25 and pokemon.current_hp / pokemon.max_hp <= 0.20))

        if is_resentful and decision.action_type in (AgentActionType.DISOBEY, AgentActionType.PROTEST):
            # Disobeys order due to severe resentment or distrust
            # Might use a different move or hesitate
            alt_move = next((a for a in pokemon.attacks if a != chosen_attack), chosen_attack)
            dialogue = decision.dialogue or f"{pokemon.display_name} ignores the command with a disdainful glare and lashes out independently with {alt_move.name}!"
            return CompanionBattleDisposition(
                action_type=AgentActionType.DISOBEY,
                chosen_attack=alt_move,
                dialogue=dialogue,
                is_obedient=False,
                rationale="Severe distrust caused independent tactical action.",
                confidence=decision.confidence,
            )

        elif low_obedience and decision.action_type in (AgentActionType.HESITATE, AgentActionType.FLEE):
            # Hesitates from fear or panic
            dialogue = decision.dialogue or f"{pokemon.display_name} trembles nervously, hesitating before executing {chosen_attack.name}!"
            return CompanionBattleDisposition(
                action_type=AgentActionType.HESITATE,
                chosen_attack=chosen_attack,
                dialogue=dialogue,
                is_obedient=False,
                rationale="Fear and critically low HP caused hesitation.",
                confidence=decision.confidence,
            )

        # Standard obedient execution with character flavor
        cry = decision.dialogue or f"{pokemon.display_name} nods sharply: '{pokemon.display_name[:4]}!' and prepares {chosen_attack.name}!"
        return CompanionBattleDisposition(
            action_type=AgentActionType.OBEY,
            chosen_attack=chosen_attack,
            dialogue=cry,
            is_obedient=True,
            rationale=decision.rationale or f"Follows {player.name}'s battle command.",
            confidence=decision.confidence,
            suggested_alternative=decision.suggested_alternative,
        )

    @staticmethod
    def teammate_interaction(
        agent1: PokemonAgent,
        mon1: Pokemon,
        agent2: PokemonAgent,
        mon2: Pokemon,
        context: str = "resting",
    ) -> TeammateInteractionResult:
        """
        Simulates a social dynamic between two team members (e.g. while resting).
        Develops mutual camaraderie, rivalry, or friendship.
        """
        rel1_to_2 = agent1.get_relationship(mon2.unique_id, default_name=mon2.display_name, default_type="teammate_pokemon")
        rel2_to_1 = agent2.get_relationship(mon1.unique_id, default_name=mon1.display_name, default_type="teammate_pokemon")

        rel1_to_2.adjust_familiarity(5.0)
        rel1_to_2.adjust_affection(3.0)
        rel2_to_1.adjust_familiarity(5.0)
        rel2_to_1.adjust_affection(3.0)

        d1 = f"{mon1.display_name} gives a friendly nod to {mon2.display_name}."
        d2 = f"{mon2.display_name} returns the gesture with a cheerful cry."
        summary = f"{mon1.display_name} and {mon2.display_name} spent time bonding while {context}."

        ep1 = agent1.record_experience(
            event_type="teammate_bonding",
            summary=summary,
            emotional_impact=0.2,
            involved_entities=[mon2.unique_id],
        )
        ep2 = agent2.record_experience(
            event_type="teammate_bonding",
            summary=summary,
            emotional_impact=0.2,
            involved_entities=[mon1.unique_id],
        )

        return TeammateInteractionResult(
            pokemon1_dialogue=d1,
            pokemon2_dialogue=d2,
            summary=summary,
            mutual_familiarity_gain=5.0,
            memory1=ep1,
            memory2=ep2,
        )

    @staticmethod
    def release_pokemon(
        agent: PokemonAgent,
        pokemon: Pokemon,
        player: Player,
        ai_state: Optional[AiState] = None,
    ) -> tuple[bool, str]:
        """
        Authoritatively releases a Pokemon from the trainer's collection into the wild.
        Enforces game constraint: Player cannot release their only remaining Pokemon.
        """
        if len(player.collection) <= 1:
            return False, "You cannot release your only remaining Pokemon! A trainer must have at least one partner."

        # Remove from player
        player.remove_pokemon(pokemon)

        # Update autonomous agent status
        agent.is_captured = False
        agent.is_wild = True

        rel = agent.get_relationship(player.unique_id, default_name=player.name, default_type="trainer")
        rel.adjust_trust(5.0)  # Respects trainer for granting freedom
        rel.adjust_affection(5.0)

        ep = agent.record_experience(
            event_type="released_to_wild",
            summary=f"Granted freedom and released into the wild by {player.name}",
            emotional_impact=0.4,
            involved_entities=[player.unique_id],
        )
        rel.add_memory(ep.episode_id)

        # Re-assign active pokemon if needed
        if player.active_pokemon is None and player.team:
            conscious = next((p for p in player.team if not p.is_fainted), player.team[0])
            player.set_active_pokemon(conscious)

        return True, f"You bid a heartfelt farewell to {pokemon.display_name}. It returned freely to the wild!"
