"""
Shared AI decision provider abstraction and mock implementation.
Provides decoupled model interfaces, context-sensitive mock decision generation,
and robust fallback handling.
"""
from abc import ABC, abstractmethod
from typing import Any, Optional

from src.ai.agent import PokemonAgent
from src.ai.decision import AgentActionType, AgentDecision
from src.ai.perception import AgentPerception


class DecisionProvider(ABC):
    """
    Abstract base class for all AI decision services.
    Decouples model execution (mock, local heuristics, or remote LLM) from game logic.
    """

    @abstractmethod
    def decide(self, agent: PokemonAgent, perception: AgentPerception) -> AgentDecision:
        """
        Assembles perception and agent state to generate a structured decision.

        Args:
            agent: The Pokemon agent making the decision.
            perception: The situational context perceived by the agent.

        Returns:
            An AgentDecision payload.
        """
        pass


class MockDecisionProvider(DecisionProvider):
    """
    Deterministic, rule-backed mock decision provider for automated testing and offline simulation.
    Interprets personality traits, relationship trust, and physical conditions
    to produce realistic autonomous responses without external API calls.
    """

    def __init__(
        self,
        forced_decision: Optional[AgentDecision] = None,
        simulate_error: bool = False,
    ) -> None:
        self.forced_decision: Optional[AgentDecision] = forced_decision
        self.simulate_error: bool = simulate_error

    def set_forced_decision(self, decision: Optional[AgentDecision]) -> None:
        """Sets a programmed decision to be returned on the next decision request."""
        self.forced_decision = decision

    def set_simulate_error(self, simulate: bool) -> None:
        """Toggles error simulation to test fallback behavior."""
        self.simulate_error = bool(simulate)

    def decide(self, agent: PokemonAgent, perception: AgentPerception) -> AgentDecision:
        """Generates a context-sensitive decision based on agent traits and perception."""
        if self.simulate_error:
            raise RuntimeError("Simulated AI model provider connection failure or timeout.")

        if self.forced_decision is not None:
            return self.forced_decision

        hp_ratio = perception.physical_state.get("hp_ratio", 1.0)
        traits = agent.identity.personality_traits
        agg = traits.get("aggression", 50)
        fear = traits.get("fear", 50)
        loyalty = traits.get("loyalty", 50)
        cur = traits.get("curiosity", 50)
        conf = traits.get("confidence", 50)

        known_moves = perception.physical_state.get("known_moves", [])
        primary_move = known_moves[0] if known_moves else None

        # --- A. Captured Pokemon Behavior ---
        if agent.is_captured and perception.trainer_context is not None:
            tc = perception.trainer_context
            trust = tc.get("trust", 0.0)
            affection = tc.get("affection", 0.0)
            command = tc.get("command")

            # 1. Severe resentment: requests release or disobeys
            if trust <= -40.0 or affection <= -50.0:
                if fear < 60:
                    return AgentDecision(
                        action_type=AgentActionType.REQUEST_RELEASE,
                        intent="Plea to be released from captivity",
                        dialogue=f"{agent.display_name} turns away coldly, pleading to be set free.",
                        emotional_state="resentful",
                        rationale=f"Trust is severely negative ({trust:.1f}). Pokemon feels alienated.",
                        confidence=0.9,
                    )
                else:
                    return AgentDecision(
                        action_type=AgentActionType.DISOBEY,
                        intent="Refuse trainer command out of distrust",
                        dialogue=f"{agent.display_name} ignores your voice entirely.",
                        emotional_state="defiant",
                        rationale="Low trust leads to command refusal.",
                        confidence=0.85,
                    )

            # 2. Critical health & high fear: hesitates or protests
            if hp_ratio <= 0.25 and fear >= 65 and trust < 50.0:
                return AgentDecision(
                    action_type=AgentActionType.HESITATE,
                    intent="Hesitate due to low health and fear",
                    dialogue=f"{agent.display_name} trembles nervously, hesitant to fight.",
                    emotional_state="frightened",
                    rationale=f"Health is critical ({hp_ratio:.0%}) and fear is high ({fear}).",
                    confidence=0.8,
                )

            # 3. High confidence with command: suggest alternative or follow command
            if command and conf >= 75 and len(known_moves) > 1:
                other_moves = [m for m in known_moves if m.lower() != command.lower()]
                if other_moves:
                    alt_move = other_moves[0]
                    return AgentDecision(
                        action_type=AgentActionType.SUGGEST_ALTERNATIVE,
                        intent=f"Suggests tactical alternative move {alt_move}",
                        chosen_move=alt_move,
                        dialogue=f"{agent.display_name} indicates it prefers using {alt_move}!",
                        emotional_state="confident",
                        rationale=f"High confidence ({conf}) encourages autonomous tactical suggestions.",
                        confidence=0.75,
                        suggested_alternative=alt_move,
                    )

            # 4. Standard cooperation / Obey
            if command:
                in_battle = perception.environment_context.get("in_battle", False)
                if not in_battle and (command not in known_moves or "interact" in perception.available_actions):
                    return FallbackDecisionHandler._create_companion_fallback(agent, perception, Exception("Mock companion dialogue"))

                chosen_attack = command if command in known_moves else primary_move
                return AgentDecision(
                    action_type=AgentActionType.OBEY,
                    intent=f"Follows trainer command: {command}",
                    chosen_move=chosen_attack,
                    dialogue=f"{agent.display_name} nodded enthusiastically!",
                    emotional_state="cooperative",
                    rationale=f"Loyalty ({loyalty}) and trust ({trust:.1f}) support following command.",
                    confidence=0.95,
                )

        # --- B. Wild Pokemon Behavior ---
        if hp_ratio <= 0.25 or (fear >= 70 and conf < 40):
            return AgentDecision(
                action_type=AgentActionType.FLEE,
                intent="Escape danger and retreat",
                dialogue=f"Wild {agent.display_name} panicked and turned to flee!",
                emotional_state="panicked",
                rationale=f"Self-preservation triggered (HP ratio: {hp_ratio:.0%}, fear: {fear}).",
                confidence=0.9,
            )

        if cur >= 70 and (not perception.environment_context.get("in_battle", False) or hp_ratio >= 0.8):
            return AgentDecision(
                action_type=AgentActionType.INSPECT,
                intent="Curiously observe surroundings and trainer",
                dialogue=f"Wild {agent.display_name} tilted its head, observing with curiosity.",
                emotional_state="curious",
                rationale=f"High curiosity trait ({cur}) encourages non-hostile inspection.",
                confidence=0.85,
            )

        # Default aggressive / wild attack
        chosen = primary_move or "Tackle"
        return AgentDecision(
            action_type=AgentActionType.ATTACK,
            intent=f"Strikes with {chosen}",
            chosen_move=chosen,
            dialogue=f"Wild {agent.display_name} leaped forward aggressively!",
            emotional_state="combative",
            rationale=f"Aggression ({agg}) drives direct battle confrontation.",
            confidence=0.8,
        )


class FallbackDecisionHandler:
    """
    Provides safe, non-crashing fallback decisions if a decision provider times out or fails.
    """

    SPECIES_CRIES = {
        "Pikachu": ("Pika!", "Pika-pi!", "Pikachu!"),
        "Charmander": ("Char!", "Chaaar!", "Charmander!"),
        "Squirtle": ("Squirtle!", "Squirt!", "Squirtle-squirt!"),
        "Bulbasaur": ("Bulba!", "Bulbasaur!", "Saur-bulba!"),
        "Eevee": ("Vee!", "Eevee!", "Eev-vee!"),
        "Pidgey": ("Pidgey!", "Pidge-pidge!"),
        "Rattata": ("Ratta!", "Rattata!"),
        "Geodude": ("Geo!", "Geodude!"),
        "Gastly": ("Gast!", "Gast-ly!"),
        "Machop": ("Chop!", "Machop!"),
    }

    @classmethod
    def _create_companion_fallback(
        cls, agent: PokemonAgent, perception: AgentPerception, error: Exception
    ) -> AgentDecision:
        species = agent.species or "Pokemon"
        cries = cls.SPECIES_CRIES.get(species, (f"{species}!", f"{species}!"))
        cry = cries[0]

        tc = perception.trainer_context or {}
        trainer_name = tc.get("trainer_name") or "Trainer"
        command = str(tc.get("command") or "").strip()
        sentiment = tc.get("sentiment")

        traits = agent.identity.personality_traits if hasattr(agent.identity, "personality_traits") else {}
        conf = traits.get("confidence", 50)
        soc = traits.get("sociability", 50)
        loyalty = traits.get("loyalty", 50)

        # Classify sentiment from message if not provided
        cmd_lower = command.lower()
        if not sentiment:
            if any(w in cmd_lower for w in ("hate", "stupid", "useless", "worst", "pathetic", "ugly", "trash", "die", "garbage", "shut up")):
                sentiment = "very_negative"
            elif any(w in cmd_lower for w in ("bad", "mistake", "disappointed", "slow", "clumsy", "stop it", "quit it", "not good")):
                sentiment = "negative"
            elif any(w in cmd_lower for w in ("good", "great", "awesome", "proud", "love", "amazing", "wonderful", "best", "friend", "thank", "nice")):
                sentiment = "positive"
            else:
                sentiment = "neutral"

        if sentiment == "very_negative":
            emotional_state = "hurt"
            trust_delta = -3.0
            affection_delta = -4.0
            dialogue = f"{cry}... *flinches back with wide, hurt eyes, shrinking away* (Why would you say that to me...?)"
            intent = "React with hurt feelings to harsh words"
        elif sentiment == "negative":
            emotional_state = "discouraged"
            trust_delta = 0.0
            affection_delta = 0.0
            dialogue = f"{cry}... *droops its head apologetically and looks down* (I'm sorry, {trainer_name}... I will try harder.)"
            intent = "Apologize and reflect on trainer criticism"
        elif sentiment == "positive":
            emotional_state = "happy"
            trust_delta = 2.5
            affection_delta = 3.5
            if conf >= 70:
                dialogue = f"{cries[-1]} *puffs out chest proudly with a bright grin* (Knew I had it in me! Thanks for believing in me, {trainer_name}!)"
            elif soc >= 65 or loyalty >= 65:
                dialogue = f"{cry} *beams with joy, happily bouncing and nuzzling against your hand* (Thank you so much, {trainer_name}! I love being your partner!)"
            else:
                dialogue = f"{cry} *beams brightly, eyes sparkling with appreciation* (Thank you, {trainer_name}! That means a lot to me!)"
            intent = "Express joy and appreciation for trainer praise"
        else:
            # Neutral / Casual conversation
            trust_delta = 0.5
            affection_delta = 0.5
            if any(g in cmd_lower for g in ("hello", "hey", "hi ", "hi!", "good morning", "good evening", "greetings")):
                emotional_state = "content"
                dialogue = f"{cry} *perks up alertly and gives a cheerful, friendly wave* (Hello {trainer_name}! It's great to be out here with you!)"
                intent = "Greet trainer cheerfully"
            elif any(q in cmd_lower for q in ("how are you", "feeling", "how you doing", "you okay", "are you okay")):
                emotional_state = "content"
                dialogue = f"{cry} *stretches comfortably and gives a lively chirp* (I'm feeling great and ready for our next adventure!)"
                intent = "Share current mood and readiness"
            elif any(f in cmd_lower for f in ("hungry", "food", "eat", "lunch", "dinner", "breakfast", "berry", "snack", "treat")):
                emotional_state = "excited"
                dialogue = f"{cry}! *eyes sparkle at the mention of food, eagerly patting its tummy* (Ooh, yes please! I'd love a delicious berry treat right about now!)"
                intent = "Eagerly accept the idea of food"
            elif any(t in cmd_lower for t in ("battle", "train", "gym", "fight", "strong", "power", "ready")):
                emotional_state = "confident"
                dialogue = f"{cries[-1]} *strikes an energetic battle pose with sharp determination* (I'm all warmed up and ready to show our strength!)"
                intent = "Show determination for battle training"
            elif any(w in cmd_lower for w in ("where", "explore", "route", "town", "what should", "next", "go", "think")):
                emotional_state = "curious"
                dialogue = f"{cry} *tilts head curiously, scanning the horizon with keen interest* (Wherever you lead, I'm right behind you! Let's go explore!)"
                intent = "Express excitement to explore the world"
            else:
                emotional_state = "thoughtful"
                dialogue = f"{cry} *swishes tail and looks up at you with bright, attentive eyes* (I'm right here with you, {trainer_name}. What's on your mind?)"
                intent = "Listen attentively to trainer"

        return AgentDecision(
            action_type=AgentActionType.INTERACT,
            intent=intent,
            chosen_move=None,
            dialogue=dialogue,
            emotional_state=emotional_state,
            rationale=f"Autonomous companion interaction (provider fallback: {error})",
            confidence=0.85,
            trust_delta=trust_delta,
            affection_delta=affection_delta,
        )

    @classmethod
    def create_fallback(cls, agent: PokemonAgent, perception: AgentPerception, error: Exception) -> AgentDecision:
        """Generates a safe fallback decision."""
        known_moves = perception.physical_state.get("known_moves", [])
        primary_move = known_moves[0] if known_moves else None
        in_battle = perception.environment_context.get("in_battle", False)

        if agent.is_captured:
            tc = perception.trainer_context or {}
            command_str = str(tc.get("command") or "").strip()
            command_intent = str(tc.get("command_intent") or "").lower()
            known_moves_lower = [m.lower() for m in known_moves]
            is_move_order = command_str.lower() in known_moves_lower or command_intent in ("attack", "offensive")

            is_chat_intent = command_intent in (
                "talk", "conversation", "praise", "scold", "insult", "criticism", "inquire_goals", "discuss_release"
            ) or tc.get("relationship_stage") == "companion"
            is_chat_context = bool((perception.environment_context or {}).get("interaction_type") in ("talk", "chat", "companion"))

            # Out-of-battle companion chat is when trainer speaks to companion outside combat
            is_companion_chat = (
                not in_battle
                and bool(command_str)
                and not is_move_order
                and (is_chat_intent or is_chat_context or "interact" in perception.available_actions)
            )
            if is_companion_chat:
                return cls._create_companion_fallback(agent, perception, error)

            # Safe defensive/hesitation fallback for owned Pokemon in battle
            return AgentDecision(
                action_type=AgentActionType.DEFEND,
                intent="Defensive posture fallback due to communication delay",
                chosen_move=primary_move,
                dialogue=f"{agent.display_name} held its ground defensively.",
                emotional_state="cautious",
                rationale=f"Fallback triggered by provider error: {error}",
                confidence=0.5,
            )
        else:
            # Safe retreat or hesitation fallback for wild Pokemon
            return AgentDecision(
                action_type=AgentActionType.HESITATE,
                intent="Hesitate due to sensory disorientation",
                dialogue=f"Wild {agent.display_name} paused cautiously.",
                emotional_state="confused",
                rationale=f"Fallback triggered by provider error: {error}",
                confidence=0.5,
            )
