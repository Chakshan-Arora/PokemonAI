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
from src.models.battle import BattleTalkCommand, BattleTalkIntent, TalkCategory


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


@dataclass(frozen=True)
class BattleTalkContext:
    """
    Context for battle dialogue generation.
    Supports physical state (HP percent, status conditions) and battle events (dodge/attack results).
    """
    hp_percent: Optional[float] = None
    is_low_hp: Optional[bool] = None
    status_condition: Optional[str] = None
    last_event: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    is_opponent_knockout: Optional[bool] = None
    is_super_effective: Optional[bool] = None
    is_critical_hit: Optional[bool] = None


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

    @staticmethod
    def generate_battle_talk_response(
        pokemon: Pokemon,
        command: Union[BattleTalkCommand, str],
        context: Optional[Union[BattleTalkContext, dict[str, Any]]] = None,
    ) -> str:
        """
        Generates a short, deterministic dialogue response from a companion Pokemon
        during battle talk, influenced by the Pokemon's personality traits and battle context.

        Requirements:
        - Deterministic for the same input, personality state, and context.
        - Bounded response templates based on dominant personality traits.
        - Context-aware: responds dynamically to low HP (<=25%), status conditions, or battle events.
        - Backward-compatible: healthy baseline without context matches standard profile templates.
        - Pure and non-mutating (does not change personality, bond, HP, stats, or RNG).
        """
        if not isinstance(pokemon, Pokemon):
            raise TypeError(f"pokemon must be a Pokemon instance, got {type(pokemon).__name__}.")

        name = pokemon.display_name
        cry = name[:4]

        # 1. Resolve intent
        resolved_intent = BattleTalkIntent.GENERAL
        if isinstance(command, BattleTalkCommand):
            if isinstance(command.intent, BattleTalkIntent):
                resolved_intent = command.intent
            elif isinstance(command.intent, str):
                try:
                    resolved_intent = BattleTalkIntent(command.intent)
                except ValueError:
                    resolved_intent = BattleTalkIntent.GENERAL
        elif isinstance(command, str):
            from src.ai.battle_talk_parser import parse_battle_talk
            parsed = parse_battle_talk(command)
            if isinstance(parsed.intent, BattleTalkIntent):
                resolved_intent = parsed.intent

        # 2. Determine dominant personality trait
        personality = getattr(pokemon, "personality", None)
        dominant_profile = "balanced"

        if personality is not None:
            # Trait hierarchy for tie-breaking:
            trait_order = ("confidence", "fear", "aggression", "loyalty", "sociability", "curiosity")
            deviations = []
            for trait_name in trait_order:
                val = getattr(personality, trait_name, 50)
                deviations.append((abs(val - 50), trait_name, val))

            # Pick trait with highest deviation from neutral (50)
            best_dev, best_trait, best_val = max(deviations, key=lambda item: item[0])

            # If deviation is noticeable (>= 15), select trait-specific profile
            if best_dev >= 15:
                direction = "high" if best_val >= 50 else "low"
                dominant_profile = f"{direction}_{best_trait}"

        # 3. Resolve context parameters
        hp_pct = 1.0
        if getattr(pokemon, "max_hp", 0) > 0:
            hp_pct = max(0.0, min(1.0, float(pokemon.current_hp) / float(pokemon.max_hp)))

        is_low_hp = hp_pct <= 0.25
        status_cond: Optional[str] = None
        last_evt: Optional[str] = None

        if getattr(pokemon, "status_effects", None):
            first_eff = pokemon.status_effects[0] if isinstance(pokemon.status_effects, (list, tuple)) and pokemon.status_effects else None
            if first_eff is not None:
                eff_type = getattr(first_eff, "effect_type", None)
                if hasattr(eff_type, "value"):
                    status_cond = str(eff_type.value).lower()
                elif eff_type is not None:
                    status_cond = str(eff_type).lower()

        if context is not None:
            if isinstance(context, BattleTalkContext):
                if context.hp_percent is not None:
                    hp_pct = max(0.0, min(1.0, float(context.hp_percent)))
                    is_low_hp = hp_pct <= 0.25
                if context.is_low_hp is not None:
                    is_low_hp = bool(context.is_low_hp)
                if context.status_condition is not None:
                    status_cond = str(context.status_condition).lower()
                if context.last_event is not None:
                    last_evt = str(context.last_event).lower()
                elif context.is_opponent_knockout:
                    last_evt = "opponent_knockout"
                elif context.is_critical_hit and context.is_super_effective:
                    last_evt = "critical_and_super_effective"
                elif context.is_critical_hit:
                    last_evt = "critical_hit"
                elif context.is_super_effective:
                    last_evt = "super_effective"
            elif isinstance(context, dict):
                if "hp_percent" in context and context["hp_percent"] is not None:
                    hp_pct = max(0.0, min(1.0, float(context["hp_percent"])))
                    is_low_hp = hp_pct <= 0.25
                if "is_low_hp" in context and context["is_low_hp"] is not None:
                    is_low_hp = bool(context["is_low_hp"])
                if "status_condition" in context and context["status_condition"] is not None:
                    status_cond = str(context["status_condition"]).lower()
                if "last_event" in context and context["last_event"] is not None:
                    last_evt = str(context["last_event"]).lower()
                elif context.get("is_opponent_knockout"):
                    last_evt = "opponent_knockout"
                elif context.get("is_critical_hit") and context.get("is_super_effective"):
                    last_evt = "critical_and_super_effective"
                elif context.get("is_critical_hit"):
                    last_evt = "critical_hit"
                elif context.get("is_super_effective"):
                    last_evt = "super_effective"

        # 4. Context-aware template resolution
        template: Optional[str] = None

        # Priority A: Recent Battle Event (e.g. dodge success/failure)
        if last_evt and dominant_profile in _CONTEXT_EVENT_TEMPLATES:
            evt_dict = _CONTEXT_EVENT_TEMPLATES[dominant_profile]
            if last_evt in evt_dict:
                template = evt_dict[last_evt]
            elif "balanced" in _CONTEXT_EVENT_TEMPLATES and last_evt in _CONTEXT_EVENT_TEMPLATES["balanced"]:
                template = _CONTEXT_EVENT_TEMPLATES["balanced"][last_evt]

        # Priority B: Status Affliction (e.g. paralysis, poison, burn)
        if template is None and status_cond:
            status_key = "paralyzed" if "paral" in status_cond else ("status" if status_cond else None)
            if status_key:
                status_dict = _CONTEXT_STATUS_TEMPLATES.get(dominant_profile, _CONTEXT_STATUS_TEMPLATES.get("balanced", {}))
                if status_key in status_dict:
                    intent_dict = status_dict[status_key]
                    template = intent_dict.get(resolved_intent, intent_dict.get(BattleTalkIntent.GENERAL))

        # Priority C: Low HP state (<= 25%)
        if template is None and is_low_hp:
            low_hp_dict = _CONTEXT_LOW_HP_TEMPLATES.get(dominant_profile, _CONTEXT_LOW_HP_TEMPLATES.get("balanced", {}))
            template = low_hp_dict.get(resolved_intent, low_hp_dict.get(BattleTalkIntent.GENERAL))

        # Priority D: Baseline Personality Profile
        if template is None:
            profile_templates = _BATTLE_TALK_TEMPLATES.get(dominant_profile, _BATTLE_TALK_TEMPLATES["balanced"])
            template = profile_templates.get(resolved_intent, profile_templates[BattleTalkIntent.GENERAL])

        return template.format(name=name, cry=cry)


_BATTLE_TALK_TEMPLATES: dict[str, dict[BattleTalkIntent, str]] = {
    "high_confidence": {
        BattleTalkIntent.PRAISE: "{name} puffs out its chest proudly: '{cry}! Knew I had it in me!'",
        BattleTalkIntent.ENCOURAGE: "{name} nods boldly: 'Don't worry, I've got this completely under control!'",
        BattleTalkIntent.WARNING: "{name} smirks with fierce confidence: 'I see it coming—they won't land a scratch!'",
        BattleTalkIntent.GENERAL: "{name} strikes a confident pose, eager to show off its strength.",
    },
    "low_confidence": {
        BattleTalkIntent.PRAISE: "{name} blushes modestly: 'R-really? Thank you... I did my best!'",
        BattleTalkIntent.ENCOURAGE: "{name} nods with quiet determination: 'If you believe in me, I'll try my hardest!'",
        BattleTalkIntent.WARNING: "{name} gulps and nods quickly, tightening its guard anxiously.",
        BattleTalkIntent.GENERAL: "{name} glances at you hesitantly, waiting for your lead.",
    },
    "high_fear": {
        BattleTalkIntent.PRAISE: "{name} breathes a shaky sigh of relief, clearly comforted by your kind words.",
        BattleTalkIntent.ENCOURAGE: "{name} trembles a bit, but your voice helps steady its shaking paws.",
        BattleTalkIntent.WARNING: "{name} flinches and jumps back nervously, frantically watching for danger!",
        BattleTalkIntent.GENERAL: "{name} stays close to your side, casting anxious glances around the field.",
    },
    "low_fear": {
        BattleTalkIntent.PRAISE: "{name} gives a steady, fearless nod, taking the praise in stride.",
        BattleTalkIntent.ENCOURAGE: "{name} grins without a hint of fear: 'Let's keep pressing forward!'",
        BattleTalkIntent.WARNING: "{name} narrows its eyes coolly, calmly tracking the threat.",
        BattleTalkIntent.GENERAL: "{name} stands firm and unflinching, scanning the battlefield with ease.",
    },
    "high_aggression": {
        BattleTalkIntent.PRAISE: "{name} lets out a fierce cry of triumph, hungry for the next clash!",
        BattleTalkIntent.ENCOURAGE: "{name} bares its teeth aggressively: 'Let's take them down right now!'",
        BattleTalkIntent.WARNING: "{name} snarls and snaps its attention forward, ready to counter-attack!",
        BattleTalkIntent.GENERAL: "{name} glares at the opposing side, pawing the ground impatiently.",
    },
    "low_aggression": {
        BattleTalkIntent.PRAISE: "{name} offers a gentle smile and a serene chirp.",
        BattleTalkIntent.ENCOURAGE: "{name} takes a calm, centered breath, focusing peacefully on the match.",
        BattleTalkIntent.WARNING: "{name} carefully observes the opponent without showing hostility.",
        BattleTalkIntent.GENERAL: "{name} looks back at you with a placid, tranquil expression.",
    },
    "high_loyalty": {
        BattleTalkIntent.PRAISE: "{name} looks at you with devoted eyes: 'Anything for you, Trainer!'",
        BattleTalkIntent.ENCOURAGE: "{name} nods resolutely: 'I'll give everything I have for our team!'",
        BattleTalkIntent.WARNING: "{name} steps firmly into a protective stance to keep you safe.",
        BattleTalkIntent.GENERAL: "{name} keeps its gaze locked onto you, attentively awaiting your next word.",
    },
    "low_loyalty": {
        BattleTalkIntent.PRAISE: "{name} gives a nonchalant shrug, accepting the compliment on its own terms.",
        BattleTalkIntent.ENCOURAGE: "{name} huffs softly, fighting at its own independent rhythm.",
        BattleTalkIntent.WARNING: "{name} glances at the danger independently, assessing its own survival.",
        BattleTalkIntent.GENERAL: "{name} watches the battle with detached independence.",
    },
    "high_sociability": {
        BattleTalkIntent.PRAISE: "{name} beams with delight, happily bouncing and chirping in response!",
        BattleTalkIntent.ENCOURAGE: "{name} chirps enthusiastically, energized by your encouragement!",
        BattleTalkIntent.WARNING: "{name} gives an appreciative chirp, glad to have you watching its back.",
        BattleTalkIntent.GENERAL: "{name} turns around with a bright, friendly smile, happy to chat.",
    },
    "low_sociability": {
        BattleTalkIntent.PRAISE: "{name} gives a curt, understated nod, quietly acknowledging your praise.",
        BattleTalkIntent.ENCOURAGE: "{name} offers a subtle nod, silently focusing its energy.",
        BattleTalkIntent.WARNING: "{name} narrows its eyes slightly and resumes an alert stance without a word.",
        BattleTalkIntent.GENERAL: "{name} glances back briefly before returning its gaze to the battlefield.",
    },
    "high_curiosity": {
        BattleTalkIntent.PRAISE: "{name} perks up its ears inquisitively, wondering what other moves to try!",
        BattleTalkIntent.ENCOURAGE: "{name} tilts its head with a keen spark in its eye, eager to see how the fight goes!",
        BattleTalkIntent.WARNING: "{name} perks its ears and studies the opponent's posture with sharp interest.",
        BattleTalkIntent.GENERAL: "{name} glances around curiously, observing every detail of the battleground.",
    },
    "low_curiosity": {
        BattleTalkIntent.PRAISE: "{name} nods simply, keeping its focus purely on the task at hand.",
        BattleTalkIntent.ENCOURAGE: "{name} keeps its eyes fixed ahead, ignoring all distractions.",
        BattleTalkIntent.WARNING: "{name} focuses strictly on the incoming threat without hesitation.",
        BattleTalkIntent.GENERAL: "{name} maintains laser focus on the battle, undisturbed by its surroundings.",
    },
    "balanced": {
        BattleTalkIntent.PRAISE: "{name} smiles warmly, heartened by your praise.",
        BattleTalkIntent.ENCOURAGE: "{name} nods firmly, bolstered by your encouragement.",
        BattleTalkIntent.WARNING: "{name} tenses up and focuses attentively on the opponent.",
        BattleTalkIntent.GENERAL: "{name} chirps in response, ready for battle.",
    },
}


_CONTEXT_LOW_HP_TEMPLATES: dict[str, dict[BattleTalkIntent, str]] = {
    "high_confidence": {
        BattleTalkIntent.PRAISE: "{name} wipes its brow and grins through the fatigue: '{cry}! Told you I wouldn't go down easy!'",
        BattleTalkIntent.ENCOURAGE: "{name} breathes heavily but flashes a daring smirk: 'Don't worry... I can still fight!'",
        BattleTalkIntent.WARNING: "{name} grits its teeth and braces sharply: 'I see it coming—I won't let it finish me!'",
        BattleTalkIntent.GENERAL: "{name} pants for breath, but keeps its stance wide and defiant.",
    },
    "low_confidence": {
        BattleTalkIntent.PRAISE: "{name} smiles weakly through its injuries: 'Really...? I'm doing okay despite being so weak...?'",
        BattleTalkIntent.ENCOURAGE: "{name} trembles and clutches its chest: 'If you believe in me... I'll try to hold on!'",
        BattleTalkIntent.WARNING: "{name} flinches in panic: 'I can't take much more...!'",
        BattleTalkIntent.GENERAL: "{name} sways unsteadily, looking at you with worried eyes.",
    },
    "high_fear": {
        BattleTalkIntent.PRAISE: "{name} gasps for air, comforted by your voice: '{cry}... thank goodness you're here!'",
        BattleTalkIntent.ENCOURAGE: "{name} shivers with wide, desperate eyes, clinging to your encouragement!",
        BattleTalkIntent.WARNING: "{name} squeals and cowers in dread: 'Danger incoming! I'm too hurt!'",
        BattleTalkIntent.GENERAL: "{name} huddles low, shivering from both pain and dread.",
    },
    "low_fear": {
        BattleTalkIntent.PRAISE: "{name} takes a calm, ragged breath, giving a nod of quiet grit.",
        BattleTalkIntent.ENCOURAGE: "{name} stands firm despite the damage: 'Pain won't slow us down. Let's finish this!'",
        BattleTalkIntent.WARNING: "{name} narrows its eyes coldly: 'Let them come. I'm ready.'",
        BattleTalkIntent.GENERAL: "{name} ignores its wounds, calmly watching the foe.",
    },
    "high_aggression": {
        BattleTalkIntent.PRAISE: "{name} roars through the pain: '{cry}!! They're going to pay for every hit!'",
        BattleTalkIntent.ENCOURAGE: "{name} bares bloodthirsty teeth: 'I don't care how hurt I am, I'm tearing them down!'",
        BattleTalkIntent.WARNING: "{name} snarls viciously, itching to strike back even as it staggers!",
        BattleTalkIntent.GENERAL: "{name} glares with red-hot ferocity, refusing to back down an inch.",
    },
    "low_aggression": {
        BattleTalkIntent.PRAISE: "{name} gives a weary, peaceful chirp, resting gently on its feet.",
        BattleTalkIntent.ENCOURAGE: "{name} exhales softly: 'I'll endure as long as our team needs me.'",
        BattleTalkIntent.WARNING: "{name} carefully keeps its distance, looking to preserve its strength.",
        BattleTalkIntent.GENERAL: "{name} breathes softly, enduring its wounds with quiet grace.",
    },
    "high_loyalty": {
        BattleTalkIntent.PRAISE: "{name} looks at you with fierce devotion: 'For you, Trainer... I'll fight until the very end!'",
        BattleTalkIntent.ENCOURAGE: "{name} stands taller despite its injuries: 'Your words give me strength! I won't let you down!'",
        BattleTalkIntent.WARNING: "{name} steps between you and the enemy: 'Stay behind me! I'll protect you no matter what!'",
        BattleTalkIntent.GENERAL: "{name} keeps its loyal eyes locked onto you, fighting through the exhaustion.",
    },
    "low_loyalty": {
        BattleTalkIntent.PRAISE: "{name} grunts grudgingly: 'Yeah, well... I'm looking out for myself here.'",
        BattleTalkIntent.ENCOURAGE: "{name} huffs wearily: 'Easy for you to say... I'm the one taking hits.'",
        BattleTalkIntent.WARNING: "{name} glances at the exits, weighing its own survival.",
        BattleTalkIntent.GENERAL: "{name} nurses its bruises with detached irritation.",
    },
    "high_sociability": {
        BattleTalkIntent.PRAISE: "{name} gives a strained but cheerful chirp: 'Together, we can pull through this!'",
        BattleTalkIntent.ENCOURAGE: "{name} perks its ears happily: 'Hearing your voice keeps my spirits high!'",
        BattleTalkIntent.WARNING: "{name} calls out to warn you of danger, glad for your teamwork!",
        BattleTalkIntent.GENERAL: "{name} gives a tired, friendly chirp, leaning toward your reassuring presence.",
    },
    "low_sociability": {
        BattleTalkIntent.PRAISE: "{name} gives a tight, taciturn nod, silently holding its ground.",
        BattleTalkIntent.ENCOURAGE: "{name} closes its eyes for a split second, taking in your words without speaking.",
        BattleTalkIntent.WARNING: "{name} sharpens its guard in heavy silence.",
        BattleTalkIntent.GENERAL: "{name} glances back once before facing the opponent in resolute silence.",
    },
    "high_curiosity": {
        BattleTalkIntent.PRAISE: "{name} perks up despite the exhaustion: 'We learned so much from that exchange!'",
        BattleTalkIntent.ENCOURAGE: "{name} tilts its head with a weary glint: 'They hit hard... but I see their rhythm now!'",
        BattleTalkIntent.WARNING: "{name} scans the opponent carefully, searching for attack trajectories through the pain.",
        BattleTalkIntent.GENERAL: "{name} studies the scratches on its paws inquisitively, unfazed by the danger.",
    },
    "low_curiosity": {
        BattleTalkIntent.PRAISE: "{name} nods sternly, entirely focused on staying upright.",
        BattleTalkIntent.ENCOURAGE: "{name} locks its eyes ahead: 'No distractions. One more hit.'",
        BattleTalkIntent.WARNING: "{name} braces rigidly against the incoming assault.",
        BattleTalkIntent.GENERAL: "{name} remains motionless and focused, conserving every drop of energy.",
    },
    "balanced": {
        BattleTalkIntent.PRAISE: "{name} smiles weakly through the exhaustion, heartened by your praise.",
        BattleTalkIntent.ENCOURAGE: "{name} nods firmly through the pain, bolstered by your encouragement.",
        BattleTalkIntent.WARNING: "{name} tenses up on weary legs, carefully watching the opponent.",
        BattleTalkIntent.GENERAL: "{name} breathes heavily, panting from exhaustion but determined to keep fighting.",
    },
}


_CONTEXT_STATUS_TEMPLATES: dict[str, dict[str, dict[BattleTalkIntent, str]]] = {
    "high_confidence": {
        "paralyzed": {
            BattleTalkIntent.PRAISE: "{name} twitches from electric sparks: '{cry}... My body won't move right, but I'm not backing down!'",
            BattleTalkIntent.ENCOURAGE: "{name} shakes off a burst of sparks with a grin: 'Just a little numbness—I've got this!'",
            BattleTalkIntent.WARNING: "{name} strains against the static: 'I see it coming—sparks won't stop me!'",
            BattleTalkIntent.GENERAL: "{name} sparks with static, stubbornly keeping its guard raised.",
        },
        "status": {
            BattleTalkIntent.PRAISE: "{name} grunts through the ailment: 'It stings, but I'm not slowing down!'",
            BattleTalkIntent.ENCOURAGE: "{name} nods defiantly: 'I'll fight right through this condition!'",
            BattleTalkIntent.WARNING: "{name} glares at the foe: 'Sick or not, they won't touch me!'",
            BattleTalkIntent.GENERAL: "{name} stands firm, enduring the discomfort with confidence.",
        },
    },
    "high_fear": {
        "paralyzed": {
            BattleTalkIntent.PRAISE: "{name} whimpers as sparks bind its paws, comforted by your voice.",
            BattleTalkIntent.ENCOURAGE: "{name} trembles violently: 'I-I'm locked up... please stay close!'",
            BattleTalkIntent.WARNING: "{name} squeaks in terror: 'I can't move my feet to dodge!'",
            BattleTalkIntent.GENERAL: "{name} shivers helplessly as sparks crackle over its limbs, looking to you in distress!",
        },
        "status": {
            BattleTalkIntent.PRAISE: "{name} breathes raggedly, visibly comforted by your reassurance.",
            BattleTalkIntent.ENCOURAGE: "{name} whimpers softly, struggling against the persistent condition.",
            BattleTalkIntent.WARNING: "{name} flinches anxiously: 'I'm too weakened to avoid danger!'",
            BattleTalkIntent.GENERAL: "{name} huddles nervously, drained by the status affliction.",
        },
    },
    "high_aggression": {
        "paralyzed": {
            BattleTalkIntent.PRAISE: "{name} growls in fury, eager to rip through the sparks!",
            BattleTalkIntent.ENCOURAGE: "{name} snarls aggressively: 'These sparks won't save them from me!'",
            BattleTalkIntent.WARNING: "{name} snaps its jaws forward, fighting through the paralyzing numbness!",
            BattleTalkIntent.GENERAL: "{name} growls in frustration, straining viciously against the paralyzing numbness!",
        },
        "status": {
            BattleTalkIntent.PRAISE: "{name} lets out an angry snarl, channeling the pain into rage!",
            BattleTalkIntent.ENCOURAGE: "{name} bares its fangs: 'This pain is just making me angrier!'",
            BattleTalkIntent.WARNING: "{name} glares with venomous fury at the opponent.",
            BattleTalkIntent.GENERAL: "{name} lashes out aggressively, impatient with the ailment.",
        },
    },
    "high_loyalty": {
        "paralyzed": {
            BattleTalkIntent.PRAISE: "{name} looks at you with devoted eyes despite the sparks: 'For you, I'll break through this!'",
            BattleTalkIntent.ENCOURAGE: "{name} struggles against the paralysis, desperate not to let you down!",
            BattleTalkIntent.WARNING: "{name} steps awkwardly to shield you, fighting the paralysis with all its might.",
            BattleTalkIntent.GENERAL: "{name} maintains eye contact, straining against the static to follow your lead.",
        },
        "status": {
            BattleTalkIntent.PRAISE: "{name} smiles devotedly through the pain, grateful for your praise.",
            BattleTalkIntent.ENCOURAGE: "{name} nods resolutely: 'I will push through this for our team!'",
            BattleTalkIntent.WARNING: "{name} steps in front of you protectively despite the condition.",
            BattleTalkIntent.GENERAL: "{name} endures the condition with unwavering loyalty to you.",
        },
    },
    "balanced": {
        "paralyzed": {
            BattleTalkIntent.PRAISE: "{name} twitches with static but smiles gratefully at your words.",
            BattleTalkIntent.ENCOURAGE: "{name} nods through the stiffness, trying to shake off the paralysis.",
            BattleTalkIntent.WARNING: "{name} braces carefully as sparks crackle across its body.",
            BattleTalkIntent.GENERAL: "{name} twitches uncomfortably, fighting against the paralysis.",
        },
        "status": {
            BattleTalkIntent.PRAISE: "{name} bears the discomfort steadily, heartened by your encouragement.",
            BattleTalkIntent.ENCOURAGE: "{name} nods determinedly, fighting through the status condition.",
            BattleTalkIntent.WARNING: "{name} stays cautious while managing its ailment.",
            BattleTalkIntent.GENERAL: "{name} winces slightly from the ailment, maintaining its focus.",
        },
    },
}


_CONTEXT_EVENT_TEMPLATES: dict[str, dict[str, str]] = {
    "high_confidence": {
        "dodge_success": "{name} winks with swagger: '{cry}! Told you they wouldn't lay a scratch on me!'",
        "dodge_failed": "{name} shakes off the blow stubbornly: 'A lucky hit, but it takes more than that to stop me!'",
        "opponent_knockout": "{name} crosses its arms with a victorious grin: '{cry}! Down for the count, just as expected!'",
        "critical_and_super_effective": "{name} smirks with supreme swagger: 'Maximum power right where it hurts! Unstoppable!'",
        "critical_hit": "{name} beams with pride: 'Nailed the sweet spot! Felt that one right in my paws!'",
        "super_effective": "{name} winks with swagger: 'Bullseye! Their defenses couldn't take that at all!'",
    },
    "low_confidence": {
        "dodge_success": "{name} sighs in modest relief: 'I... I actually dodged it?! Thank goodness!'",
        "dodge_failed": "{name} blushes in embarrassment: 'I'm sorry, I wasn't quick enough...!'",
        "opponent_knockout": "{name} blinks in disbelief, then smiles modestly: 'W-we did it! I really managed to finish the battle...?'",
        "critical_and_super_effective": "{name} gasps softly: 'Did that really hit so hard...? Thank you for guiding me!'",
        "critical_hit": "{name} blushes happily: 'I landed a critical hit...? That was amazing!'",
        "super_effective": "{name} sighs with relief: 'I'm so glad that move worked against them!'",
    },
    "high_fear": {
        "dodge_success": "{name} sighs in immense relief: 'Whew! That was way too close!'",
        "dodge_failed": "{name} cowers slightly, nursing the sting of the landed hit with anxious eyes.",
        "opponent_knockout": "{name} lets out an enormous sigh of relief: 'Whew... they're down! We're safe now!'",
        "critical_and_super_effective": "{name} squeaks in wide-eyed amazement: 'Whoa! That hit with unbelievable power!'",
        "critical_hit": "{name} blinks in startled joy: 'Did you see that?! It struck right where they were vulnerable!'",
        "super_effective": "{name} gasps in relieved delight: 'It was super effective! I was so nervous, but it worked!'",
    },
    "low_fear": {
        "dodge_success": "{name} steps aside coolly, letting the attack pass without flinching.",
        "dodge_failed": "{name} absorbs the impact with stoic composure, unaffected.",
        "opponent_knockout": "{name} nods calmly, unfazed by the fallen opponent: 'Target neutralized. Clean and efficient.'",
        "critical_and_super_effective": "{name} grins coolly: 'A devastating strike. Exactly what they had coming.'",
        "critical_hit": "{name} narrows its eyes with sharp satisfaction: 'Precision strike landed.'",
        "super_effective": "{name} stands firm: 'Exploited their weakness without hesitation.'",
    },
    "high_aggression": {
        "dodge_success": "{name} snarls with a vicious smirk: 'Too slow! Now it's my turn!'",
        "dodge_failed": "{name} snaps its jaws in fury at taking the hit, itching for payback!",
        "opponent_knockout": "{name} lets out a triumphant roar: '{cry}!! Knocked clean out! Bring on the next one!'",
        "critical_and_super_effective": "{name} bares its fangs in savage delight: 'Total annihilation! They never stood a chance!'",
        "critical_hit": "{name} snarls viciously: 'Smashed right through their guard! Feel that power!'",
        "super_effective": "{name} grins ferociously: 'Crushed them! That's what happens when you mess with us!'",
    },
    "low_aggression": {
        "dodge_success": "{name} gracefully slips past the attack with tranquil ease.",
        "dodge_failed": "{name} yields to the blow gently, maintaining peaceful focus.",
        "opponent_knockout": "{name} bows gently toward the fallen foe: 'A good match. Rest well now.'",
        "critical_and_super_effective": "{name} offers a tranquil nod: 'A harmonious, perfectly placed strike.'",
        "critical_hit": "{name} gives a serene chirp, appreciating the clean delivery of the move.",
        "super_effective": "{name} chirps calmly: 'The elemental balance guided our attack true.'",
    },
    "high_loyalty": {
        "dodge_success": "{name} snaps into an alert defensive stance: 'Dodged cleanly, Trainer!'",
        "dodge_failed": "{name} grits its teeth apologetically: 'Sorry Trainer, I couldn't evade in time!'",
        "opponent_knockout": "{name} salutes you proudly: 'Target neutralized, Trainer! Your strategy was flawless!'",
        "critical_and_super_effective": "{name} looks at you with fierce devotion: 'Our combined power is unstoppable, Trainer!'",
        "critical_hit": "{name} nods eagerly: 'Your timing was perfect, Trainer! Struck right where it counted!'",
        "super_effective": "{name} turns to you with bright eyes: 'Your call on their weakness was spot on!'",
    },
    "low_loyalty": {
        "dodge_success": "{name} hops back independently, looking out for its own safety.",
        "dodge_failed": "{name} huffs with annoyance at getting clipped.",
        "opponent_knockout": "{name} huffs nonchalantly: 'Downed them myself. Pretty good, if I say so.'",
        "critical_and_super_effective": "{name} shrugs with a smirk: 'See what happens when you let me do my thing?'",
        "critical_hit": "{name} smirks independently: 'That was all in the technique. Flawless execution.'",
        "super_effective": "{name} mutters casually: 'Obvious weakness. Anyone could see that.'",
    },
    "high_sociability": {
        "dodge_success": "{name} winks cheerfully at you after slipping away from the attack!",
        "dodge_failed": "{name} rubs its head sheepishly: 'Ouch! Almost had it!'",
        "opponent_knockout": "{name} bounds over to you happily: 'We did it, partner! That was an incredible finish!'",
        "critical_and_super_effective": "{name} chirps enthusiastically, bouncing with joy at the spectacular blow!",
        "critical_hit": "{name} beams with excitement: 'Did you see that spark?! That felt amazing!'",
        "super_effective": "{name} gives a cheerful chirp: 'Our teamwork really cracked their defense wide open!'",
    },
    "low_sociability": {
        "dodge_success": "{name} sidesteps silently, eyes never leaving the target.",
        "dodge_failed": "{name} resets its footing without a sound.",
        "opponent_knockout": "{name} gives a curt, decisive nod, quietly acknowledging the victory.",
        "critical_and_super_effective": "{name} holds its stance in stoic silence, eyes reflecting the devastating hit.",
        "critical_hit": "{name} gives a faint nod of approval, refocusing immediately.",
        "super_effective": "{name} maintains an alert, composed posture, noting the clean hit.",
    },
    "high_curiosity": {
        "dodge_success": "{name} tilts its head with a keen spark: 'Saw that attack's trajectory coming from a mile away!'",
        "dodge_failed": "{name} notes the attack angle intently: 'That was fast... I have to adjust my timing.'",
        "opponent_knockout": "{name} tilts its head, inspecting the fallen foe with keen fascination.",
        "critical_and_super_effective": "{name} perks up its ears with delight: 'Fascinating! Critical impact combined with elemental weakness!'",
        "critical_hit": "{name} studies the impact point inquisitively: 'Remarkable! Hitting that angle amplified the force!'",
        "super_effective": "{name} perks its ears enthusiastically: 'The type matchup yielded optimal results!'",
    },
    "low_curiosity": {
        "dodge_success": "{name} dodges with mechanical precision, ignoring the flashiness of the attack.",
        "dodge_failed": "{name} absorbs the blow rigidly, unbothered by how it happened.",
        "opponent_knockout": "{name} remains firmly centered: 'Job is done. Ready for what is next.'",
        "critical_and_super_effective": "{name} locks its eyes forward: 'Effective hit. That is all that matters.'",
        "critical_hit": "{name} nods once with strict discipline: 'Hit landed true.'",
        "super_effective": "{name} stays strictly focused on the battle, undisturbed.'",
    },
    "balanced": {
        "dodge_success": "{name} deftly regains its balance after smoothly evading the attack.",
        "dodge_failed": "{name} recovers its footing after taking the hit, ready to push on.",
        "opponent_knockout": "{name} catches its breath, proud of securing the decisive knockout.",
        "critical_and_super_effective": "{name} smiles brightly at the devastating, super-effective critical hit!",
        "critical_hit": "{name} chirps happily after landing the clean critical strike.",
        "super_effective": "{name} nods with satisfaction at the powerful, super-effective strike.",
    },
}


def generate_battle_talk_response(
    pokemon: Pokemon,
    command: Union[BattleTalkCommand, str],
    context: Optional[Union[BattleTalkContext, dict[str, Any]]] = None,
) -> str:
    """Convenience module-level interface for CompanionService.generate_battle_talk_response."""
    return CompanionService.generate_battle_talk_response(pokemon, command, context=context)

