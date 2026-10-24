"""
Unit tests for LocalModelDecisionProvider and factory integration.
Tests verify:
1. Provider initialization and parameter defaults.
2. Graceful fallback execution when model weights are not loaded.
3. Factory creation via create_live_decision_provider(provider_type="local").
4. Environment variable detection (POKEMON_AI_PROVIDER="local").
5. Integration with ActionValidator and game systems.
6. Integration with CompanionService and AutonomousWildService.
"""
import os
import unittest
from unittest.mock import patch

from src.ai.agent import PokemonAgent, AgentIdentity
from src.ai.decision import AgentActionType, AgentDecision
from src.ai.local_model_provider import LocalModelDecisionProvider, LocalModelError
from src.ai.live_provider import create_live_decision_provider
from src.ai.perception import PerceptionBuilder
from src.ai.companion_service import CompanionService
from src.ai.wild_encounter_service import AutonomousWildService
from src.data.species import PIKACHU, CHARMANDER
from src.data.attacks import THUNDER_SHOCK, QUICK_ATTACK, EMBER, SCRATCH
from src.models.personality import Personality
from src.models.player import Player
from src.models.pokemon import Pokemon


class TestLocalModelProvider(unittest.TestCase):

    def setUp(self):
        self.p1 = Personality(50, 50, 50, 50, 50, 50)
        self.mon = Pokemon(species=PIKACHU, level=10, personality=self.p1, attacks=[THUNDER_SHOCK, QUICK_ATTACK])
        self.agent = PokemonAgent.from_pokemon(self.mon, is_wild=False, is_captured=True)
        self.player = Player(name="Ash")
        self.player.add_pokemon(self.mon)
        self.player.add_to_team(self.mon)
        self.player.set_active_pokemon(self.mon)

    def test_provider_initialization_defaults(self):
        provider = LocalModelDecisionProvider()
        self.assertTrue(provider.model_name_or_path.endswith("Qwen3-4B-4bit") or provider.model_name_or_path == "Qwen/Qwen3-4B-Base")
        self.assertTrue(provider.allow_mock_fallback)
        self.assertFalse(provider.is_loaded)

    def test_mock_backend_decision(self):
        provider = LocalModelDecisionProvider(inference_backend="mock")
        perception = PerceptionBuilder.build(
            agent=self.agent,
            pokemon=self.mon,
            player=self.player,
            command="Great battle!",
        )
        decision = provider.decide(self.agent, perception)
        self.assertIsInstance(decision, AgentDecision)
        self.assertEqual(decision.action_type, AgentActionType.INTERACT)
        self.assertIn("Pika", decision.dialogue)

    def test_fallback_on_unloaded_model(self):
        provider = LocalModelDecisionProvider(
            model_name_or_path="non_existent_model_checkpoint",
            allow_mock_fallback=True,
            inference_backend="invalid_backend",
        )
        perception = PerceptionBuilder.build(
            agent=self.agent,
            pokemon=self.mon,
            player=self.player,
            command="Attack!",
        )
        decision = provider.decide(self.agent, perception)
        # Should return safe defensive fallback without raising exception
        self.assertIsInstance(decision, AgentDecision)
        self.assertIn("fallback", decision.rationale.lower())

    def test_factory_creation_local(self):
        prov = create_live_decision_provider(provider_type="local")
        self.assertIsInstance(prov, LocalModelDecisionProvider)

    def test_factory_creation_auto_with_env_var(self):
        with patch.dict(os.environ, {"POKEMON_AI_PROVIDER": "local"}):
            prov = create_live_decision_provider(provider_type="auto")
            self.assertIsInstance(prov, LocalModelDecisionProvider)

    def test_companion_service_integration_with_local_provider(self):
        local_prov = LocalModelDecisionProvider(inference_backend="mock")
        res = CompanionService.interact(
            agent=self.agent,
            pokemon=self.mon,
            player=self.player,
            interaction_type="talk",
            message="Let's train together!",
            provider=local_prov,
        )
        self.assertIsNotNone(res.decision)
        self.assertIsInstance(res.decision, AgentDecision)
        self.assertTrue(len(self.agent.memory.episodic.episodes) >= 1)

    def test_wild_service_integration_with_local_provider(self):
        wild_mon = Pokemon(species=CHARMANDER, level=5, personality=self.p1, attacks=[EMBER, SCRATCH])
        wild_agent = AutonomousWildService.get_or_create_agent(wild_mon)
        local_prov = LocalModelDecisionProvider(inference_backend="mock")

        wild_dec = AutonomousWildService.decide_turn(
            agent=wild_agent,
            wild_pokemon=wild_mon,
            player_pokemon=self.mon,
            player=self.player,
            provider=local_prov,
        )
        self.assertIsNotNone(wild_dec.action_type)
        self.assertIn("agent_decision", wild_dec.factors)


if __name__ == "__main__":
    unittest.main()
