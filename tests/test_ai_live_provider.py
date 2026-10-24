"""
Unit tests for live AI model providers, prompt building, response parsing,
credential management, and error resilience.
"""
import json
from typing import Any
import unittest

from src.ai import (
    AgentActionType,
    AgentDecision,
    AgentPerception,
    PerceptionBuilder,
    PokemonAgent,
    ActionValidator,
    PromptBuilder,
    DecisionResponseParser,
    GeminiDecisionProvider,
    OpenAIDecisionProvider,
    LiveAIDecisionProvider,
    create_live_decision_provider,
    AiConfigurationError,
    AiModelServiceError,
    GEMINI_API_KEY_PLACEHOLDER,
    OPENAI_API_KEY_PLACEHOLDER,
)
from src.models.personality import Personality
from src.models.pokemon import Pokemon
from src.models.player import Player
from src.data.species import PIKACHU, SQUIRTLE
from src.data.attacks import THUNDER_SHOCK, QUICK_ATTACK


class TestPromptBuilder(unittest.TestCase):
    """Tests system instruction and situational prompt construction."""

    def setUp(self) -> None:
        self.pers = Personality(aggression=40, fear=60, curiosity=80, loyalty=75, confidence=70, sociability=65)
        self.pikachu = Pokemon(species=PIKACHU, personality=self.pers, level=5, attacks=[THUNDER_SHOCK, QUICK_ATTACK])
        self.agent = PokemonAgent.from_pokemon(self.pikachu, is_wild=False, is_captured=True)
        self.agent.goals.add_immediate_goal("Master electrical focus", priority=1)
        self.agent.goals.add_long_term_goal("Become champion partner")
        self.agent.beliefs.add_world_belief("Thunder makes us stronger")
        self.player = Player(name="Ash")
        self.opponent = Pokemon(species=SQUIRTLE, personality=self.pers, level=5)

    def test_build_system_instruction(self) -> None:
        """System instruction includes species, personality metrics, goals, and behavioral principles."""
        instruction = PromptBuilder.build_system_instruction(self.agent)
        self.assertIn("Pikachu", instruction)
        self.assertIn("Aggression: 40/100", instruction)
        self.assertIn("Fear: 60/100", instruction)
        self.assertIn("Curiosity: 80/100", instruction)
        self.assertIn("Confidence: 70/100", instruction)
        self.assertIn("Master electrical focus", instruction)
        self.assertIn("Become champion partner", instruction)
        self.assertIn("Thunder makes us stronger", instruction)
        self.assertIn("BEHAVIOR GUIDELINES", instruction)

    def test_build_user_prompt(self) -> None:
        """User prompt includes physical state, trainer info, opponent condition, and JSON schema."""
        rel = self.agent.get_relationship(self.player.unique_id, default_name="Ash")
        rel.adjust_trust(35.0)
        rel.adjust_affection(25.0)

        perception = PerceptionBuilder.build(
            agent=self.agent,
            pokemon=self.pikachu,
            player=self.player,
            opponent=self.opponent,
            command="Thunder Shock",
            command_intent="offensive",
            tone="encouraging",
            region_id="viridian_forest",
            time_of_day="dusk",
        )
        prompt = PromptBuilder.build_user_prompt(perception)
        self.assertIn("viridian_forest", prompt)
        self.assertIn("Thunder Shock", prompt)
        self.assertIn("Squirtle", prompt)
        self.assertIn("Trust Level: 35.0 / 100.0", prompt)
        self.assertIn("REQUIRED JSON RESPONSE", prompt)


class TestDecisionResponseParser(unittest.TestCase):
    """Tests parsing of raw model outputs, handling fences, wrappers, and malformed inputs."""

    def test_parse_clean_json(self) -> None:
        """Parses clean direct JSON string."""
        raw = json.dumps({
            "action_type": "attack",
            "intent": "Strike with electricity",
            "chosen_move": "Thunder Shock",
            "dialogue": "Pika-chuuu!",
            "emotional_state": "focused",
            "rationale": "Opponent is vulnerable.",
            "confidence": 0.9,
        })
        decision = DecisionResponseParser.parse(raw)
        self.assertEqual(decision.action_type, AgentActionType.ATTACK)
        self.assertEqual(decision.intent, "Strike with electricity")
        self.assertEqual(decision.chosen_move, "Thunder Shock")
        self.assertEqual(decision.dialogue, "Pika-chuuu!")
        self.assertEqual(decision.emotional_state, "focused")
        self.assertEqual(decision.confidence, 0.9)

    def test_parse_markdown_fenced_json(self) -> None:
        """Parses JSON enclosed in markdown code fences."""
        raw = """Here is my decision:
```json
{
  "action_type": "suggest",
  "intent": "Propose priority attack",
  "chosen_move": "Quick Attack",
  "dialogue": "Pikachu!",
  "emotional_state": "confident",
  "rationale": "Need priority to strike first.",
  "confidence": 0.85,
  "suggested_alternative": "Quick Attack"
}
```
I hope this works well!"""
        decision = DecisionResponseParser.parse(raw)
        self.assertEqual(decision.action_type, AgentActionType.SUGGEST_ALTERNATIVE)
        self.assertEqual(decision.chosen_move, "Quick Attack")
        self.assertEqual(decision.suggested_alternative, "Quick Attack")
        self.assertEqual(decision.confidence, 0.85)

    def test_parse_surrounding_conversational_text(self) -> None:
        """Locates outer JSON object even without code fences."""
        raw = 'Understood! {"action_type": "obey", "intent": "Follow order", "confidence": 0.95} Let\'s do it!'
        decision = DecisionResponseParser.parse(raw)
        self.assertEqual(decision.action_type, AgentActionType.OBEY)
        self.assertEqual(decision.confidence, 0.95)

    def test_parse_malformed_json_fallback(self) -> None:
        """Malformed JSON returns safe HESITATE decision without throwing."""
        raw = "This is not JSON at all."
        decision = DecisionResponseParser.parse(raw)
        self.assertEqual(decision.action_type, AgentActionType.HESITATE)
        self.assertEqual(decision.emotional_state, "confused")

    def test_parse_confidence_clamping(self) -> None:
        """Out of bounds confidence values are clamped to [0.0, 1.0]."""
        raw = json.dumps({"action_type": "rest", "confidence": 2.5})
        decision = DecisionResponseParser.parse(raw)
        self.assertEqual(decision.confidence, 1.0)

        raw_low = json.dumps({"action_type": "rest", "confidence": -0.8})
        decision_low = DecisionResponseParser.parse(raw_low)
        self.assertEqual(decision_low.confidence, 0.0)


class TestGeminiDecisionProvider(unittest.TestCase):
    """Tests Google Gemini provider configuration, mock transports, and error handling."""

    def setUp(self) -> None:
        self.pers = Personality(aggression=50, fear=50, curiosity=50, loyalty=50, confidence=50, sociability=50)
        self.pikachu = Pokemon(species=PIKACHU, personality=self.pers, level=5, attacks=[THUNDER_SHOCK])
        self.agent = PokemonAgent.from_pokemon(self.pikachu, is_wild=False, is_captured=True)
        self.perception = AgentPerception(agent_id=self.agent.agent_id, species="Pikachu")

    def test_is_configured_with_placeholder(self) -> None:
        """Placeholder key reports unconfigured; real key reports configured."""
        provider_placeholder = GeminiDecisionProvider(api_key=GEMINI_API_KEY_PLACEHOLDER)
        self.assertFalse(provider_placeholder.is_configured())

        provider_real = GeminiDecisionProvider(api_key="AIzaSy_test_valid_looking_key_12345")
        self.assertTrue(provider_real.is_configured())

    def test_decide_unconfigured_raises_ai_configuration_error(self) -> None:
        """Calling decide on an unconfigured Gemini provider raises AiConfigurationError."""
        provider = GeminiDecisionProvider(api_key=GEMINI_API_KEY_PLACEHOLDER)
        with self.assertRaises(AiConfigurationError):
            provider.decide(self.agent, self.perception)

    def test_mock_transport_success(self) -> None:
        """Gemini provider successfully communicates with endpoint via mock transport."""
        sent_requests = []

        def mock_client(url: str, headers: dict[str, str], payload: dict[str, Any], timeout: float) -> dict[str, Any]:
            sent_requests.append({"url": url, "headers": headers, "payload": payload, "timeout": timeout})
            # Standard Google Gemini REST API response format
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": json.dumps({
                                        "action_type": "obey",
                                        "intent": "Follow trainer instructions",
                                        "chosen_move": "Thunder Shock",
                                        "dialogue": "Pikachu!",
                                        "emotional_state": "determined",
                                        "rationale": "High trust in trainer.",
                                        "confidence": 0.95,
                                    })
                                }
                            ],
                            "role": "model",
                        },
                        "finishReason": "STOP",
                    }
                ]
            }

        provider = GeminiDecisionProvider(
            api_key="test_gemini_key",
            model_name="gemini-2.0-flash",
            http_client=mock_client,
        )
        decision = provider.decide(self.agent, self.perception)

        self.assertEqual(len(sent_requests), 1)
        self.assertIn("key=test_gemini_key", sent_requests[0]["url"])
        self.assertIn("gemini-2.0-flash", sent_requests[0]["url"])
        self.assertEqual(decision.action_type, AgentActionType.OBEY)
        self.assertEqual(decision.chosen_move, "Thunder Shock")
        self.assertEqual(decision.dialogue, "Pikachu!")

    def test_mock_transport_empty_candidates_raises_service_error(self) -> None:
        """Gemini response without candidates raises AiModelServiceError."""
        def mock_client_empty(url: str, headers: dict[str, str], payload: dict[str, Any], timeout: float) -> dict[str, Any]:
            return {"candidates": []}

        provider = GeminiDecisionProvider(
            api_key="test_gemini_key",
            max_retries=0,
            http_client=mock_client_empty,
        )
        with self.assertRaises(AiModelServiceError):
            provider.decide(self.agent, self.perception)


class TestOpenAIDecisionProvider(unittest.TestCase):
    """Tests OpenAI and compatible endpoint communication and parsing."""

    def setUp(self) -> None:
        self.pers = Personality(aggression=50, fear=50, curiosity=50, loyalty=50, confidence=50, sociability=50)
        self.pikachu = Pokemon(species=PIKACHU, personality=self.pers, level=5, attacks=[THUNDER_SHOCK])
        self.agent = PokemonAgent.from_pokemon(self.pikachu, is_wild=False, is_captured=True)
        self.perception = AgentPerception(agent_id=self.agent.agent_id, species="Pikachu")

    def test_is_configured_with_placeholder(self) -> None:
        """Placeholder key reports unconfigured; real key reports configured."""
        provider_placeholder = OpenAIDecisionProvider(api_key=OPENAI_API_KEY_PLACEHOLDER)
        self.assertFalse(provider_placeholder.is_configured())

        provider_real = OpenAIDecisionProvider(api_key="sk-test_valid_looking_key_12345")
        self.assertTrue(provider_real.is_configured())

    def test_mock_transport_success(self) -> None:
        """OpenAI provider formats bearer auth and parses message content."""
        sent_requests = []

        def mock_client(url: str, headers: dict[str, str], payload: dict[str, Any], timeout: float) -> dict[str, Any]:
            sent_requests.append({"url": url, "headers": headers, "payload": payload, "timeout": timeout})
            return {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": json.dumps({
                                "action_type": "attack",
                                "intent": "Strike hard",
                                "chosen_move": "Thunder Shock",
                                "dialogue": "Pika!",
                                "emotional_state": "aggressive",
                                "confidence": 0.88,
                            }),
                        }
                    }
                ]
            }

        provider = OpenAIDecisionProvider(
            api_key="sk-test_key",
            model_name="gpt-4o-mini",
            http_client=mock_client,
        )
        decision = provider.decide(self.agent, self.perception)

        self.assertEqual(len(sent_requests), 1)
        self.assertEqual(sent_requests[0]["headers"]["Authorization"], "Bearer sk-test_key")
        self.assertEqual(sent_requests[0]["payload"]["model"], "gpt-4o-mini")
        self.assertEqual(decision.action_type, AgentActionType.ATTACK)
        self.assertEqual(decision.chosen_move, "Thunder Shock")


class TestLiveAIDecisionProviderWrapperAndFactory(unittest.TestCase):
    """Tests the high-level LiveAIDecisionProvider wrapper and factory."""

    def setUp(self) -> None:
        self.pers = Personality(aggression=50, fear=50, curiosity=50, loyalty=50, confidence=50, sociability=50)
        self.pikachu = Pokemon(species=PIKACHU, personality=self.pers, level=5, attacks=[THUNDER_SHOCK])
        self.agent = PokemonAgent.from_pokemon(self.pikachu, is_wild=False, is_captured=True)
        self.perception = AgentPerception(agent_id=self.agent.agent_id, species="Pikachu")

    def test_factory_instantiation(self) -> None:
        """Factory creates correct provider instances."""
        gemini_live = create_live_decision_provider(provider_type="gemini", api_key="test_key")
        self.assertIsInstance(gemini_live.active_provider, GeminiDecisionProvider)

        openai_live = create_live_decision_provider(provider_type="openai", api_key="test_key")
        self.assertIsInstance(openai_live.active_provider, OpenAIDecisionProvider)

        with self.assertRaises(ValueError):
            create_live_decision_provider(provider_type="invalid_type")

    def test_unconfigured_with_allow_mock_fallback(self) -> None:
        """Unconfigured provider gracefully routes to FallbackDecisionHandler when fallback is enabled."""
        provider = create_live_decision_provider(
            provider_type="gemini",
            api_key=GEMINI_API_KEY_PLACEHOLDER,
            allow_mock_fallback=True,
        )
        self.assertFalse(provider.is_configured())

        # Calling decide should NOT crash; returns fallback decision
        decision = provider.decide(self.agent, self.perception)
        self.assertEqual(decision.action_type, AgentActionType.DEFEND)
        self.assertIn("Fallback triggered", decision.rationale)

    def test_unconfigured_without_fallback_raises(self) -> None:
        """Unconfigured provider raises AiConfigurationError when fallback is disabled."""
        provider = create_live_decision_provider(
            provider_type="gemini",
            api_key=GEMINI_API_KEY_PLACEHOLDER,
            allow_mock_fallback=False,
        )
        with self.assertRaises(AiConfigurationError):
            provider.decide(self.agent, self.perception)


class TestAgentDecideIntegrationWithLiveProvider(unittest.TestCase):
    """Tests full PokemonAgent.decide() pipeline with live AI providers."""

    def setUp(self) -> None:
        self.pers = Personality(aggression=50, fear=50, curiosity=50, loyalty=50, confidence=50, sociability=50)
        self.pikachu = Pokemon(species=PIKACHU, personality=self.pers, level=5, attacks=[THUNDER_SHOCK, QUICK_ATTACK])
        self.agent = PokemonAgent.from_pokemon(self.pikachu, is_wild=False, is_captured=True)
        self.player = Player(name="Ash")
        self.perception = PerceptionBuilder.build(
            agent=self.agent,
            pokemon=self.pikachu,
            player=self.player,
            command="Thunder Shock",
        )

    def test_agent_decide_with_live_provider_success(self) -> None:
        """Agent pipeline executes, calls model, updates memory, and validates decision."""
        def mock_client(url: str, headers: dict[str, str], payload: dict[str, Any], timeout: float) -> dict[str, Any]:
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": json.dumps({
                                        "action_type": "obey",
                                        "intent": "Unleash electric shock",
                                        "chosen_move": "Thunder Shock",
                                        "dialogue": "Pikachu!",
                                        "confidence": 0.92,
                                    })
                                }
                            ]
                        }
                    }
                ]
            }

        live_provider = GeminiDecisionProvider(
            api_key="valid_test_key",
            http_client=mock_client,
        )

        decision = self.agent.decide(self.perception, live_provider, pokemon=self.pikachu)
        self.assertEqual(decision.action_type, AgentActionType.OBEY)
        self.assertEqual(decision.chosen_move, "Thunder Shock")
        self.assertEqual(self.agent.memory.working.get_active_intention()["intent"], decision.intent)
        self.assertEqual(self.agent.last_decision["action_type"], "obey")

    def test_agent_decide_with_unconfigured_provider_falls_back_safely(self) -> None:
        """Unconfigured live provider triggers fallback without crashing the game engine."""
        live_provider = GeminiDecisionProvider(api_key=GEMINI_API_KEY_PLACEHOLDER)
        self.assertFalse(live_provider.is_configured())

        # agent.decide catches provider errors and activates fallback
        decision = self.agent.decide(self.perception, live_provider, pokemon=self.pikachu)
        self.assertEqual(decision.action_type, AgentActionType.DEFEND)
        self.assertIn("Fallback triggered", decision.rationale)


if __name__ == "__main__":
    unittest.main()
