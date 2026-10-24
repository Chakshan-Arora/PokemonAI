"""
Unit tests for individual agent decision interface, structured decision protocol,
action validation, perception assembly, and mock decision provider.
Enforces that Pokemon agents propose autonomous actions while the game engine
authoritatively governs validity and execution.
"""
import unittest

from src.ai import (
    AgentActionType,
    AgentDecision,
    AgentPerception,
    PerceptionBuilder,
    ActionValidator,
    ValidationResult,
    DecisionProvider,
    MockDecisionProvider,
    FallbackDecisionHandler,
    PokemonAgent,
    AgentIdentity,
)
from src.models.personality import Personality
from src.models.pokemon import Pokemon
from src.models.player import Player
from src.data.species import PIKACHU, CHARMANDER, SQUIRTLE
from src.data.attacks import THUNDER_SHOCK, QUICK_ATTACK, EMBER, WATER_GUN


class TestAgentDecisionProtocol(unittest.TestCase):
    """Tests the structured decision payload and AgentActionType enum."""

    def test_decision_instantiation_and_normalization(self) -> None:
        """Confidence is clamped and string action types are coerced to enum."""
        dec1 = AgentDecision(
            action_type="attack",
            intent="Strike hard",
            confidence=1.5,  # should clamp to 1.0
        )
        self.assertEqual(dec1.action_type, AgentActionType.ATTACK)
        self.assertEqual(dec1.confidence, 1.0)

        dec2 = AgentDecision(
            action_type="unknown_action_type",
            intent="Confused",
            confidence=-0.5,  # should clamp to 0.0
        )
        self.assertEqual(dec2.action_type, AgentActionType.HESITATE)
        self.assertEqual(dec2.confidence, 0.0)

    def test_decision_serialization_roundtrip(self) -> None:
        """Decisions serialize and deserialize cleanly without data loss."""
        orig = AgentDecision(
            action_type=AgentActionType.SUGGEST_ALTERNATIVE,
            intent="Suggest tactical change",
            target="Squirtle",
            chosen_move="Quick Attack",
            dialogue="Pika! Use this instead!",
            emotional_state="confident",
            rationale="Opponent is vulnerable to physical priority moves.",
            confidence=0.88,
            suggested_alternative="Quick Attack",
        )
        data = orig.to_dict()
        self.assertEqual(data["action_type"], "suggest")
        self.assertEqual(data["confidence"], 0.88)

        restored = AgentDecision.from_dict(data)
        self.assertEqual(restored.action_type, AgentActionType.SUGGEST_ALTERNATIVE)
        self.assertEqual(restored.intent, orig.intent)
        self.assertEqual(restored.target, orig.target)
        self.assertEqual(restored.chosen_move, orig.chosen_move)
        self.assertEqual(restored.dialogue, orig.dialogue)
        self.assertEqual(restored.emotional_state, orig.emotional_state)
        self.assertEqual(restored.rationale, orig.rationale)
        self.assertEqual(restored.confidence, orig.confidence)
        self.assertEqual(restored.suggested_alternative, orig.suggested_alternative)


class TestPerceptionBuilder(unittest.TestCase):
    """Tests sensory and situational context building from authoritative game objects."""

    def setUp(self) -> None:
        self.pers = Personality(aggression=50, fear=50, curiosity=50, loyalty=50, confidence=50, sociability=50)
        self.pikachu = Pokemon(species=PIKACHU, personality=self.pers, level=5, attacks=[THUNDER_SHOCK, QUICK_ATTACK])
        self.agent = PokemonAgent.from_pokemon(self.pikachu, is_wild=False, is_captured=True)
        self.player = Player(name="Ash")
        self.opponent = Pokemon(species=SQUIRTLE, personality=self.pers, level=5)

    def test_physical_state_accuracy(self) -> None:
        """Perception includes self physical state without omniscient leaks."""
        perception = PerceptionBuilder.build(
            agent=self.agent,
            pokemon=self.pikachu,
            player=self.player,
            opponent=self.opponent,
        )
        self.assertEqual(perception.agent_id, self.agent.agent_id)
        self.assertEqual(perception.species, "Pikachu")
        self.assertEqual(perception.physical_state["current_hp"], self.pikachu.current_hp)
        self.assertEqual(perception.physical_state["max_hp"], self.pikachu.max_hp)
        self.assertEqual(perception.physical_state["hp_ratio"], 1.0)
        self.assertFalse(perception.physical_state["is_fainted"])
        self.assertIn("Thunder Shock", perception.physical_state["known_moves"])
        self.assertIn("Quick Attack", perception.physical_state["known_moves"])

    def test_trainer_context_captured(self) -> None:
        """Trainer relationship context and commands are built into perception."""
        rel = self.agent.get_relationship(self.player.unique_id, default_name="Ash")
        rel.adjust_trust(25.0)
        rel.adjust_affection(15.0)

        perception = PerceptionBuilder.build(
            agent=self.agent,
            pokemon=self.pikachu,
            player=self.player,
            command="Thunder Shock",
            command_intent="offensive",
            tone="encouraging",
        )
        tc = perception.trainer_context
        self.assertIsNotNone(tc)
        self.assertEqual(tc["trainer_id"], self.player.unique_id)
        self.assertEqual(tc["trainer_name"], "Ash")
        self.assertEqual(tc["command"], "Thunder Shock")
        self.assertEqual(tc["command_intent"], "offensive")
        self.assertEqual(tc["tone"], "encouraging")
        self.assertEqual(tc["trust"], 25.0)
        self.assertEqual(tc["affection"], 15.0)

    def test_opponent_qualitative_health_heuristic(self) -> None:
        """Opponent health is perceived qualitatively without exposing private engine internals."""
        # Full health opponent
        perc_full = PerceptionBuilder.build(
            agent=self.agent,
            pokemon=self.pikachu,
            opponent=self.opponent,
        )
        self.assertEqual(perc_full.opponent_context["apparent_health"], "healthy")

        # Wounded opponent (50% HP)
        self.opponent.current_hp = int(self.opponent.max_hp * 0.5)
        perc_half = PerceptionBuilder.build(
            agent=self.agent,
            pokemon=self.pikachu,
            opponent=self.opponent,
        )
        self.assertEqual(perc_half.opponent_context["apparent_health"], "wounded")

        # Critical opponent (20% HP)
        self.opponent.current_hp = int(self.opponent.max_hp * 0.2)
        perc_crit = PerceptionBuilder.build(
            agent=self.agent,
            pokemon=self.pikachu,
            opponent=self.opponent,
        )
        self.assertEqual(perc_crit.opponent_context["apparent_health"], "critical")

    def test_available_actions_dynamic_filtering(self) -> None:
        """Available actions adapt to battle status and fainted state."""
        # Fainted Pokemon cannot attack
        self.pikachu.current_hp = 0
        perc_fainted = PerceptionBuilder.build(
            agent=self.agent,
            pokemon=self.pikachu,
        )
        self.assertNotIn("attack", perc_fainted.available_actions)
        self.assertIn("rest", perc_fainted.available_actions)

        # Active captured in battle
        self.pikachu.current_hp = self.pikachu.max_hp
        perc_active = PerceptionBuilder.build(
            agent=self.agent,
            pokemon=self.pikachu,
            player=self.player,
            battle=object(),
        )
        self.assertIn("attack", perc_active.available_actions)
        self.assertIn("defend", perc_active.available_actions)
        self.assertIn("obey", perc_active.available_actions)
        self.assertIn("suggest", perc_active.available_actions)
        self.assertIn("request_release", perc_active.available_actions)

    def test_perception_serialization_roundtrip(self) -> None:
        """AgentPerception serializes and deserializes accurately."""
        perception = PerceptionBuilder.build(
            agent=self.agent,
            pokemon=self.pikachu,
            player=self.player,
            opponent=self.opponent,
            region_id="viridian_forest",
            time_of_day="dusk",
        )
        data = perception.to_dict()
        restored = AgentPerception.from_dict(data)
        self.assertEqual(restored.agent_id, perception.agent_id)
        self.assertEqual(restored.species, perception.species)
        self.assertEqual(restored.physical_state, perception.physical_state)
        self.assertEqual(restored.trainer_context, perception.trainer_context)
        self.assertEqual(restored.opponent_context, perception.opponent_context)
        self.assertEqual(restored.environment_context, perception.environment_context)


class TestMockDecisionProviderBehaviors(unittest.TestCase):
    """Tests personality-driven divergence, captured responses, overrides, and fallbacks."""

    def test_personality_divergence_for_identical_perception(self) -> None:
        """Agents with differing personalities make distinct autonomous decisions given identical context."""
        provider = MockDecisionProvider()

        # Shared base situation: low health wild Pokemon encountering trainer
        situation_data = {
            "agent_id": "test_agent",
            "species": "Charmander",
            "physical_state": {"current_hp": 6, "max_hp": 30, "hp_ratio": 0.20, "known_moves": ["Ember", "Scratch"]},
            "environment_context": {"in_battle": True},
            "available_actions": ["attack", "flee", "inspect", "hesitate"],
        }
        perception = AgentPerception.from_dict(situation_data)

        # 1. Fearful Pokemon (fear >= 70) -> Flees for self-preservation
        fearful_identity = AgentIdentity(
            species="Charmander",
            personality_traits={"fear": 85, "aggression": 30, "curiosity": 20, "confidence": 20},
        )
        fearful_agent = PokemonAgent(agent_id="fearful_1", identity=fearful_identity, is_wild=True)
        dec_fear = provider.decide(fearful_agent, perception)
        self.assertEqual(dec_fear.action_type, AgentActionType.FLEE)

        # 2. Aggressive Pokemon (fear low, aggression high) -> Attacks despite low health
        aggressive_identity = AgentIdentity(
            species="Charmander",
            personality_traits={"fear": 20, "aggression": 90, "curiosity": 30, "confidence": 80},
        )
        aggressive_agent = PokemonAgent(agent_id="aggro_1", identity=aggressive_identity, is_wild=True)
        # Set hp_ratio higher to avoid automatic low-health retreat trigger
        situation_data["physical_state"]["hp_ratio"] = 0.60
        perception_healthy = AgentPerception.from_dict(situation_data)
        dec_aggro = provider.decide(aggressive_agent, perception_healthy)
        self.assertEqual(dec_aggro.action_type, AgentActionType.ATTACK)
        self.assertEqual(dec_aggro.chosen_move, "Ember")

        # 3. Highly curious Pokemon outside battle -> Inspects
        curious_identity = AgentIdentity(
            species="Charmander",
            personality_traits={"curiosity": 85, "fear": 30, "aggression": 20, "confidence": 50},
        )
        curious_agent = PokemonAgent(agent_id="curious_1", identity=curious_identity, is_wild=True)
        situation_data["environment_context"]["in_battle"] = False
        situation_data["physical_state"]["hp_ratio"] = 1.0
        perception_peaceful = AgentPerception.from_dict(situation_data)
        dec_curious = provider.decide(curious_agent, perception_peaceful)
        self.assertEqual(dec_curious.action_type, AgentActionType.INSPECT)

    def test_captured_obedient_behavior(self) -> None:
        """Cooperative captured Pokemon with positive trust obeys commands."""
        provider = MockDecisionProvider()
        identity = AgentIdentity(
            species="Pikachu",
            personality_traits={"loyalty": 80, "fear": 20, "confidence": 50},
        )
        agent = PokemonAgent(agent_id="pika_obedient", identity=identity, is_captured=True)
        perception = AgentPerception(
            agent_id=agent.agent_id,
            species="Pikachu",
            physical_state={"current_hp": 40, "max_hp": 40, "hp_ratio": 1.0, "known_moves": ["Thunder Shock", "Quick Attack"]},
            trainer_context={"trainer_id": "ash_1", "command": "Thunder Shock", "trust": 30.0, "affection": 20.0},
        )
        dec = provider.decide(agent, perception)
        self.assertEqual(dec.action_type, AgentActionType.OBEY)
        self.assertEqual(dec.chosen_move, "Thunder Shock")

    def test_captured_tactical_suggestion_behavior(self) -> None:
        """Confident captured Pokemon suggests tactical alternative move."""
        provider = MockDecisionProvider()
        identity = AgentIdentity(
            species="Pikachu",
            personality_traits={"confidence": 85, "loyalty": 60, "fear": 15},
        )
        agent = PokemonAgent(agent_id="pika_tactical", identity=identity, is_captured=True)
        perception = AgentPerception(
            agent_id=agent.agent_id,
            species="Pikachu",
            physical_state={"current_hp": 40, "max_hp": 40, "hp_ratio": 1.0, "known_moves": ["Thunder Shock", "Quick Attack"]},
            trainer_context={"trainer_id": "ash_1", "command": "Thunder Shock", "trust": 25.0, "affection": 20.0},
        )
        dec = provider.decide(agent, perception)
        self.assertEqual(dec.action_type, AgentActionType.SUGGEST_ALTERNATIVE)
        self.assertEqual(dec.chosen_move, "Quick Attack")
        self.assertEqual(dec.suggested_alternative, "Quick Attack")

    def test_captured_severe_resentment_release_request(self) -> None:
        """Captured Pokemon with severe negative trust pleads to be released."""
        provider = MockDecisionProvider()
        identity = AgentIdentity(
            species="Pikachu",
            personality_traits={"fear": 30, "loyalty": 10},
        )
        agent = PokemonAgent(agent_id="pika_resentful", identity=identity, is_captured=True)
        perception = AgentPerception(
            agent_id=agent.agent_id,
            species="Pikachu",
            physical_state={"current_hp": 40, "max_hp": 40, "hp_ratio": 1.0, "known_moves": ["Thunder Shock"]},
            trainer_context={"trainer_id": "ash_1", "command": "Thunder Shock", "trust": -55.0, "affection": -60.0},
        )
        dec = provider.decide(agent, perception)
        self.assertEqual(dec.action_type, AgentActionType.REQUEST_RELEASE)
        self.assertEqual(dec.emotional_state, "resentful")

    def test_captured_hesitates_on_critical_health(self) -> None:
        """Fearful captured Pokemon hesitates when health is critically low."""
        provider = MockDecisionProvider()
        identity = AgentIdentity(
            species="Pikachu",
            personality_traits={"fear": 75, "confidence": 30},
        )
        agent = PokemonAgent(agent_id="pika_scared", identity=identity, is_captured=True)
        perception = AgentPerception(
            agent_id=agent.agent_id,
            species="Pikachu",
            physical_state={"current_hp": 5, "max_hp": 40, "hp_ratio": 0.12, "known_moves": ["Thunder Shock"]},
            trainer_context={"trainer_id": "ash_1", "command": "Thunder Shock", "trust": 10.0, "affection": 5.0},
        )
        dec = provider.decide(agent, perception)
        self.assertEqual(dec.action_type, AgentActionType.HESITATE)

    def test_forced_decision_override(self) -> None:
        """Programmed forced decisions bypass heuristic generation for tests."""
        provider = MockDecisionProvider()
        forced = AgentDecision(
            action_type=AgentActionType.REST,
            intent="Testing sleep",
            dialogue="Pikachu fell asleep.",
        )
        provider.set_forced_decision(forced)

        identity = AgentIdentity(species="Pikachu")
        agent = PokemonAgent(agent_id="test_pika", identity=identity)
        perception = AgentPerception(agent_id="test_pika", species="Pikachu")

        dec = provider.decide(agent, perception)
        self.assertEqual(dec, forced)

    def test_error_simulation_and_fallback_handler(self) -> None:
        """Simulated provider error is safely handled by FallbackDecisionHandler."""
        provider = MockDecisionProvider(simulate_error=True)
        identity = AgentIdentity(species="Pikachu")
        agent_captured = PokemonAgent(agent_id="pika_err", identity=identity, is_captured=True)
        agent_wild = PokemonAgent(agent_id="pika_wild_err", identity=identity, is_wild=True, is_captured=False)
        perception = AgentPerception(
            agent_id="pika_err",
            species="Pikachu",
            physical_state={"known_moves": ["Thunder Shock"]},
        )

        with self.assertRaises(RuntimeError):
            provider.decide(agent_captured, perception)

        # Fallback handler handles error for captured Pokemon
        fb_captured = FallbackDecisionHandler.create_fallback(
            agent_captured, perception, RuntimeError("Timeout")
        )
        self.assertEqual(fb_captured.action_type, AgentActionType.DEFEND)

        # Fallback handler handles error for wild Pokemon
        fb_wild = FallbackDecisionHandler.create_fallback(
            agent_wild, perception, RuntimeError("Timeout")
        )
        self.assertEqual(fb_wild.action_type, AgentActionType.HESITATE)


class TestActionValidatorAuthority(unittest.TestCase):
    """Tests non-negotiable game engine rule enforcement and action sanitization."""

    def setUp(self) -> None:
        self.pers = Personality(aggression=50, fear=50, curiosity=50, loyalty=50, confidence=50, sociability=50)
        self.pikachu = Pokemon(species=PIKACHU, personality=self.pers, level=5, attacks=[THUNDER_SHOCK, QUICK_ATTACK])

    def test_fainted_pokemon_cannot_act(self) -> None:
        """Fainted Pokemon attempting attack or defend is sanitized to REST."""
        self.pikachu.current_hp = 0
        self.assertTrue(self.pikachu.is_fainted)

        dec = AgentDecision(
            action_type=AgentActionType.ATTACK,
            intent="Strike while fainted",
            chosen_move="Thunder Shock",
        )
        res = ActionValidator.validate(dec, pokemon=self.pikachu)
        self.assertFalse(res.valid)
        self.assertEqual(res.error_code, "POKEMON_FAINTED")
        self.assertEqual(res.sanitized_decision.action_type, AgentActionType.REST)

    def test_unknown_move_sanitized_to_known_move(self) -> None:
        """Pokemon proposing an unlearned attack is sanitized to its first known move."""
        dec = AgentDecision(
            action_type=AgentActionType.ATTACK,
            intent="Inventing move",
            chosen_move="Hydro Pump",  # Pikachu cannot know Hydro Pump
        )
        res = ActionValidator.validate(dec, pokemon=self.pikachu)
        self.assertFalse(res.valid)
        self.assertEqual(res.error_code, "INVALID_MOVE")
        self.assertEqual(res.sanitized_decision.action_type, AgentActionType.ATTACK)
        self.assertEqual(res.sanitized_decision.chosen_move, "Thunder Shock")

    def test_no_known_attacks_sanitized_to_hesitate(self) -> None:
        """Pokemon with no attack slots attempting ATTACK is sanitized to HESITATE."""
        pika_no_attacks = Pokemon(species=PIKACHU, personality=self.pers, level=5, attacks=[])
        dec = AgentDecision(
            action_type=AgentActionType.ATTACK,
            intent="Attack with empty moveset",
        )
        res = ActionValidator.validate(dec, pokemon=pika_no_attacks)
        self.assertFalse(res.valid)
        self.assertEqual(res.error_code, "NO_ATTACKS_KNOWN")
        self.assertEqual(res.sanitized_decision.action_type, AgentActionType.HESITATE)

    def test_flee_blocked_in_trainer_battle(self) -> None:
        """Fleeing during an official trainer battle is sanitized to DEFEND."""
        dec = AgentDecision(
            action_type=AgentActionType.FLEE,
            intent="Run away from gym battle",
        )
        res = ActionValidator.validate(
            dec, pokemon=self.pikachu, in_trainer_battle=True
        )
        self.assertFalse(res.valid)
        self.assertEqual(res.error_code, "CANNOT_FLEE_TRAINER")
        self.assertEqual(res.sanitized_decision.action_type, AgentActionType.DEFEND)

    def test_wild_pokemon_cannot_obey(self) -> None:
        """Wild Pokemon cannot OBEY trainer commands and is sanitized to INSPECT."""
        dec = AgentDecision(
            action_type=AgentActionType.OBEY,
            intent="Take orders from a stranger",
        )
        res = ActionValidator.validate(
            dec, pokemon=self.pikachu, is_captured=False
        )
        self.assertFalse(res.valid)
        self.assertEqual(res.error_code, "WILD_CANNOT_OBEY")
        self.assertEqual(res.sanitized_decision.action_type, AgentActionType.INSPECT)

    def test_request_release_preserves_engine_ownership(self) -> None:
        """REQUEST_RELEASE is valid emotional expression but cannot unilaterally modify ownership."""
        dec = AgentDecision(
            action_type=AgentActionType.REQUEST_RELEASE,
            intent="Pleads to leave",
        )
        res = ActionValidator.validate(
            dec, pokemon=self.pikachu, is_captured=True
        )
        # Marked valid as dialogue/expression
        self.assertTrue(res.valid)
        self.assertEqual(res.sanitized_decision.action_type, AgentActionType.REQUEST_RELEASE)
        # Engine ownership boundary remains strictly unchanged
        self.assertIn("Ownership remains unchanged", res.reason)

    def test_validation_with_perception_context_only(self) -> None:
        """Validator functions cleanly with perception context when Pokemon model is absent."""
        perception = AgentPerception(
            agent_id="test_pika",
            species="Pikachu",
            physical_state={
                "current_hp": 0,
                "max_hp": 40,
                "is_fainted": True,
                "known_moves": ["Thunder Shock"],
            },
        )
        dec = AgentDecision(
            action_type=AgentActionType.ATTACK,
            intent="Fainted attack",
            chosen_move="Thunder Shock",
        )
        res = ActionValidator.validate(dec, pokemon=None, perception=perception)
        self.assertFalse(res.valid)
        self.assertEqual(res.error_code, "POKEMON_FAINTED")


class TestPokemonAgentDecidePipeline(unittest.TestCase):
    """Tests the full decision pipeline integrated into PokemonAgent."""

    def setUp(self) -> None:
        self.pers = Personality(aggression=50, fear=50, curiosity=50, loyalty=50, confidence=50, sociability=50)
        self.pikachu = Pokemon(species=PIKACHU, personality=self.pers, level=5, attacks=[THUNDER_SHOCK, QUICK_ATTACK])
        self.agent = PokemonAgent.from_pokemon(self.pikachu, is_wild=False, is_captured=True)
        self.player = Player(name="Ash")

    def test_agent_decide_updates_working_memory_and_last_decision(self) -> None:
        """Agent decide sets active intention and stores the decision."""
        provider = MockDecisionProvider()
        perception = PerceptionBuilder.build(
            agent=self.agent,
            pokemon=self.pikachu,
            player=self.player,
            command="Thunder Shock",
        )
        decision = self.agent.decide(perception, provider, pokemon=self.pikachu)
        self.assertEqual(decision.action_type, AgentActionType.OBEY)
        self.assertEqual(self.agent.memory.working.get_active_intention()["intent"], decision.intent)
        self.assertIsNotNone(self.agent.last_decision)
        self.assertEqual(self.agent.last_decision["action_type"], "obey")

    def test_agent_decide_handles_provider_failure_gracefully(self) -> None:
        """Provider failure triggers fallback handler without crashing the agent pipeline."""
        erroring_provider = MockDecisionProvider(simulate_error=True)
        perception = PerceptionBuilder.build(
            agent=self.agent,
            pokemon=self.pikachu,
            player=self.player,
        )
        decision = self.agent.decide(perception, erroring_provider, pokemon=self.pikachu)
        self.assertEqual(decision.action_type, AgentActionType.DEFEND)
        self.assertEqual(self.agent.memory.working.get_active_intention()["intent"], decision.intent)

    def test_agent_decide_enforces_automatic_action_validation(self) -> None:
        """Decide automatically validates and sanitizes invalid moves proposed by provider."""
        provider = MockDecisionProvider()
        invalid_dec = AgentDecision(
            action_type=AgentActionType.ATTACK,
            intent="Use illegal move",
            chosen_move="Hydro Pump",
        )
        provider.set_forced_decision(invalid_dec)

        perception = PerceptionBuilder.build(
            agent=self.agent,
            pokemon=self.pikachu,
            player=self.player,
        )
        decision = self.agent.decide(perception, provider, pokemon=self.pikachu)
        self.assertEqual(decision.action_type, AgentActionType.ATTACK)
        self.assertEqual(decision.chosen_move, "Thunder Shock")
        self.assertIn("Sanitized to known move", decision.rationale)


if __name__ == "__main__":
    unittest.main()
