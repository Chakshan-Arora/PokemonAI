"""
Unit tests for Companion Sentiment Guardrails and Relationship Dynamics.
Verifies that:
- Very negative comments (insults, hatred, abuse) cause trust and affection to drop (< 0).
- Negative comments (criticism, scolding, annoyance) result in exactly 0.0 delta.
- Neutral comments result in small or zero gain (0.0 to 1.0).
- Positive comments result in positive gain (>= 2.0).
- DecisionResponseParser correctly extracts negative deltas from JSON and regex fallback.
"""
import unittest
from unittest.mock import MagicMock

from server import classify_companion_sentiment, LLMBridgeHandler
from src.ai.decision import AgentActionType, AgentDecision
from src.ai.live_provider import DecisionResponseParser


class TestCompanionSentimentClassifier(unittest.TestCase):
    """Tests the sentiment classification rules and negation handling."""

    def test_very_negative_comments(self) -> None:
        very_negative_samples = [
            "Why are you so stupid and useless?",
            "I hate you, you are worthless trash!",
            "Shut up and get out of here!",
            "You are pathetic and weak.",
            "I regret catching you, you're the worst pokemon.",
            "You ugly freak, die already.",
            "I don't want you on my team anymore, useless.",
            "my charmander is stupid or what",
        ]
        for msg in very_negative_samples:
            with self.subTest(msg=msg):
                self.assertEqual(classify_companion_sentiment(msg), "very_negative")

    def test_negative_comments(self) -> None:
        negative_samples = [
            "You made a mistake, that was bad.",
            "You were really slow and clumsy today.",
            "I am disappointed in you.",
            "Stop it, that is annoying.",
            "That was not good.",
            "Why did you mess up the attack?",
            "You need to listen to me and do better.",
            "I don't like when you lose.",
        ]
        for msg in negative_samples:
            with self.subTest(msg=msg):
                self.assertEqual(classify_companion_sentiment(msg), "negative")

    def test_negations_do_not_falsely_trigger_negative(self) -> None:
        negated_samples = [
            ("You are not stupid, don't worry.", "neutral"),
            ("That wasn't bad at all, good job!", "positive"),
            ("Not bad, you did well!", "positive"),
            ("I don't hate you, you are my friend.", "positive"),
        ]
        for msg, expected in negated_samples:
            with self.subTest(msg=msg):
                self.assertEqual(classify_companion_sentiment(msg), expected)

    def test_positive_comments(self) -> None:
        positive_samples = [
            "Great job Charmander, you're amazing!",
            "I am so proud of you, buddy!",
            "I love you so much, you are the best partner!",
            "Thank you for helping me in that battle!",
            "Super work today!",
        ]
        for msg in positive_samples:
            with self.subTest(msg=msg):
                self.assertEqual(classify_companion_sentiment(msg), "positive")

    def test_neutral_comments(self) -> None:
        neutral_samples = [
            "Hello partner!",
            "What do you think of this town?",
            "Are you ready to head to the gym?",
            "The weather is nice today.",
            "How are you feeling?",
        ]
        for msg in neutral_samples:
            with self.subTest(msg=msg):
                self.assertEqual(classify_companion_sentiment(msg), "neutral")


class TestDecisionResponseParserNegativeDeltas(unittest.TestCase):
    """Verifies DecisionResponseParser parses signed and negative deltas."""

    def test_parses_negative_deltas_from_json(self) -> None:
        raw_json = '''{
            "dialogue": "Char... *droops head sadly* Sorry Trainer.",
            "emotional_state": "hurt",
            "action_type": "interact",
            "intent": "feel remorseful",
            "confidence": 0.9,
            "trust_delta": -3.5,
            "affection_delta": -4.0
        }'''
        decision = DecisionResponseParser.parse(raw_json)
        self.assertEqual(decision.trust_delta, -3.5)
        self.assertEqual(decision.affection_delta, -4.0)
        self.assertEqual(decision.emotional_state, "hurt")

    def test_parses_zero_deltas_from_json(self) -> None:
        raw_json = '''{
            "dialogue": "Char? *tilts head thoughtfully*",
            "emotional_state": "cautious",
            "action_type": "interact",
            "intent": "reflect",
            "confidence": 0.9,
            "trust_delta": 0.0,
            "affection_delta": 0.0
        }'''
        decision = DecisionResponseParser.parse(raw_json)
        self.assertEqual(decision.trust_delta, 0.0)
        self.assertEqual(decision.affection_delta, 0.0)

    def test_regex_rescue_handles_negative_deltas(self) -> None:
        # Malformed JSON with unescaped internal text or trailing characters
        raw_text = '''
        Here is the JSON:
        {"dialogue": "Char! *flinches* "Ouch" that hurt", "emotional_state": "hurt", "action_type": "interact", "intent": "react", "trust_delta": -2.5, "affection_delta": -3.0}
        Hope you like it!
        '''
        decision = DecisionResponseParser.parse(raw_text)
        self.assertEqual(decision.trust_delta, -2.5)
        self.assertEqual(decision.affection_delta, -3.0)


class TestServerCompanionTalkGuardrails(unittest.TestCase):
    """Verifies LLMBridgeHandler._handle_companion_talk authoritative guardrails."""

    def setUp(self) -> None:
        self.handler = LLMBridgeHandler.__new__(LLMBridgeHandler)
        self.mock_provider = MagicMock()
        self.handler.provider = self.mock_provider

    def test_very_negative_comment_forces_negative_deltas_even_if_model_hallucinates_positive(self) -> None:
        # Mock model mistakenly hallucinating positive deltas on an insult
        self.mock_provider.decide.return_value = AgentDecision(
            action_type=AgentActionType.INTERACT,
            intent="talk",
            dialogue="Char! *wags tail*",
            emotional_state="pleased",
            trust_delta=3.0,
            affection_delta=4.0,
        )

        res = self.handler._handle_companion_talk({
            "species": "Charmander",
            "message": "Why are you so stupid and useless?",
            "trust": 50.0,
            "affection": 50.0,
        })

        self.assertEqual(res["sentiment"], "very_negative")
        self.assertLess(res["trust_delta"], 0.0)
        self.assertLess(res["affection_delta"], 0.0)
        self.assertLess(res["new_trust"], 50.0)
        self.assertLess(res["new_affection"], 50.0)
        self.assertEqual(res["emotional_state"], "hurt")

    def test_negative_critique_decreases_trust_and_affection_by_2(self) -> None:
        # Scolding / criticism: trust and affection must decrease by 2.0
        # If model hallucinated a cheerful state, server guardrail overrides it to discouraged
        self.mock_provider.decide.return_value = AgentDecision(
            action_type=AgentActionType.INTERACT,
            intent="talk",
            dialogue="Char... *looks down*",
            emotional_state="pleased",
            trust_delta=2.0,
            affection_delta=2.0,
        )

        res = self.handler._handle_companion_talk({
            "species": "Charmander",
            "message": "You made a mistake, that was bad.",
            "trust": 40.0,
            "affection": 40.0,
        })

        self.assertEqual(res["sentiment"], "negative")
        self.assertEqual(res["trust_delta"], -2.0)
        self.assertEqual(res["affection_delta"], -2.0)
        self.assertEqual(res["new_trust"], 38.0)
        self.assertEqual(res["new_affection"], 38.0)
        self.assertEqual(res["emotional_state"], "discouraged")

    def test_positive_comment_increases_trust_and_affection(self) -> None:
        self.mock_provider.decide.return_value = AgentDecision(
            action_type=AgentActionType.INTERACT,
            intent="talk",
            dialogue="Chaaar! *hugs trainer*",
            emotional_state="happy",
            trust_delta=2.5,
            affection_delta=3.5,
        )

        res = self.handler._handle_companion_talk({
            "species": "Charmander",
            "message": "Great job Charmander, you're amazing!",
            "trust": 30.0,
            "affection": 30.0,
        })

        self.assertEqual(res["sentiment"], "positive")
        self.assertGreater(res["trust_delta"], 0.0)
        self.assertGreater(res["affection_delta"], 0.0)
        self.assertGreater(res["new_trust"], 30.0)
        self.assertGreater(res["new_affection"], 30.0)
        self.assertEqual(res["emotional_state"], "happy")

    def test_relationship_values_clamped_at_bounds_and_refuses_to_battle(self) -> None:
        # Dropping below 0
        self.mock_provider.decide.return_value = AgentDecision(
            action_type=AgentActionType.INTERACT,
            intent="talk",
            dialogue="Char...",
            emotional_state="hurt",
            trust_delta=-5.0,
            affection_delta=-5.0,
        )
        res_min = self.handler._handle_companion_talk({
            "species": "Charmander",
            "message": "I hate you, you are useless trash!",
            "trust": 1.0,
            "affection": 1.0,
        })
        self.assertEqual(res_min["new_trust"], -4.0)
        self.assertEqual(res_min["new_affection"], -4.0)
        self.assertTrue(res_min["refuses_to_battle"])
        self.assertGreaterEqual(res_min["new_trust"], -100.0)
        self.assertGreaterEqual(res_min["new_affection"], -100.0)

        # Near 100
        self.mock_provider.decide.return_value = AgentDecision(
            action_type=AgentActionType.INTERACT,
            intent="talk",
            dialogue="Char!",
            emotional_state="happy",
            trust_delta=5.0,
            affection_delta=5.0,
        )
        res_max = self.handler._handle_companion_talk({
            "species": "Charmander",
            "message": "I love you so much, best partner!",
            "trust": 99.0,
            "affection": 99.0,
        })
        self.assertLessEqual(res_max["new_trust"], 100.0)
        self.assertLessEqual(res_max["new_affection"], 100.0)
        self.assertFalse(res_max["refuses_to_battle"])


class TestTrustAffectionBondMechanics(unittest.TestCase):
    """Tests the trust/affection decay, 1.5x bond multiplier, and 100% bond EXP reward."""

    def setUp(self) -> None:
        from src.models.personality import Personality
        from src.data.species import PIKACHU
        from src.models.pokemon import Pokemon
        from src.models.bond_manager import BondManager

        self.pers = Personality(50, 50, 50, 50, 50, 50)
        self.pokemon = Pokemon(
            species=PIKACHU,
            personality=self.pers,
            level=5,
            bond=40,
            obedience=60,
            trust=60.0,
            affection=60.0,
        )
        self.bond_mgr = BondManager()

    def test_bond_multiplier_active_when_both_above_50(self) -> None:
        self.pokemon.trust = 55.0
        self.pokemon.affection = 55.0
        self.assertEqual(self.pokemon.bond_multiplier, 1.5)

        # Baseline gain 10 -> with 1.5x should become 15
        prev_bond = self.pokemon.bond
        res = self.bond_mgr.increase_bond(self.pokemon, 10)
        self.assertEqual(res.new_bond, prev_bond + 15)

    def test_bond_multiplier_normal_when_either_at_or_below_50(self) -> None:
        self.pokemon.trust = 50.0
        self.pokemon.affection = 60.0
        self.assertEqual(self.pokemon.bond_multiplier, 1.0)

        prev_bond = self.pokemon.bond
        res = self.bond_mgr.increase_bond(self.pokemon, 10)
        self.assertEqual(res.new_bond, prev_bond + 10)

    def test_100_percent_bond_awards_50_percent_exp_to_next_level(self) -> None:
        # At level 5, xp_for_next_level is 500. 50% is 250 XP.
        self.pokemon.bond = 90
        prev_xp = self.pokemon.experience
        res = self.bond_mgr.increase_bond(self.pokemon, 10)
        self.assertEqual(self.pokemon.bond, 100)
        self.assertEqual(self.pokemon.experience, prev_xp + 250)

    def test_decay_trust_and_affection(self) -> None:
        self.pokemon.trust = 60.0
        self.pokemon.affection = 40.0
        self.pokemon.decay_trust_and_affection(2.0)
        self.assertEqual(self.pokemon.trust, 58.0)
        self.assertEqual(self.pokemon.affection, 38.0)

    def test_refuses_to_battle_when_trust_and_affection_below_zero(self) -> None:
        self.pokemon.trust = -1.0
        self.pokemon.affection = -1.0
        self.assertTrue(self.pokemon.refuses_to_battle)
        self.assertFalse(self.pokemon.can_battle)

        # At 0.0 or positive, does not refuse
        self.pokemon.trust = 0.0
        self.pokemon.affection = 0.0
        self.assertFalse(self.pokemon.refuses_to_battle)
        self.assertTrue(self.pokemon.can_battle)

    def test_decay_can_push_trust_and_affection_below_zero(self) -> None:
        self.pokemon.trust = 1.0
        self.pokemon.affection = 1.0
        self.pokemon.decay_trust_and_affection(2.0)
        self.assertEqual(self.pokemon.trust, -1.0)
        self.assertEqual(self.pokemon.affection, -1.0)
        self.assertTrue(self.pokemon.refuses_to_battle)

    def test_battle_rejects_attack_when_refusing_to_battle(self) -> None:
        from src.models.battle import Battle
        from src.models.pokemon import Pokemon
        from src.data.species import CHARMANDER
        from src.models.personality import Personality
        from src.data.attacks import QUICK_ATTACK, TACKLE

        opp_pers = Personality(50, 50, 50, 50, 50, 50)
        opp = Pokemon(species=CHARMANDER, personality=opp_pers, level=5)
        self.pokemon.assign_attack(QUICK_ATTACK)
        opp.assign_attack(TACKLE)

        # Set below 0
        self.pokemon.trust = -2.0
        self.pokemon.affection = -2.0
        self.assertTrue(self.pokemon.refuses_to_battle)

        battle = Battle(pokemon1=self.pokemon, pokemon2=opp)
        battle.start()

        # select_attack raises ValueError
        with self.assertRaises(ValueError) as ctx:
            battle.select_attack(self.pokemon, QUICK_ATTACK)
        self.assertIn("refuses to battle", str(ctx.exception))

        # Restoring trust and affection allows battle
        self.pokemon.trust = 10.0
        self.pokemon.affection = 10.0
        self.assertFalse(self.pokemon.refuses_to_battle)
        battle.select_attack(self.pokemon, QUICK_ATTACK)
        self.assertEqual(battle._selected_attacks[self.pokemon.unique_id], QUICK_ATTACK)


if __name__ == "__main__":
    unittest.main()
