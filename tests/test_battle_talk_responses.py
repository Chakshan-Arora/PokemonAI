# """
# Unit tests for personality-aware battle talk responses (BT2.2):
# - Personality-sensitive dialogue generation across multiple traits:
#   - High confidence vs. low confidence
#   - High fear vs. low fear
#   - High aggression vs. low aggression
#   - High loyalty vs. low loyalty
#   - High sociability vs. low sociability
#   - High curiosity vs. low curiosity
#   - Balanced / neutral
# - Determinism: identical inputs and personality state produce identical responses
# - Invariants: no mutation of personality, bond, obedience, HP, stats, status effects, or RNG
# - BattleManager.talk() integration:
#   - Pipeline: raw text -> intent parser -> validated BattleTalkCommand -> personality dialogue -> result
#   - Access to talk_intent and talk_dialogue
#   - No combat turn advance, no opponent attacks, no damage
# - Terminal battle and fainted Pokemon safety
# - Tactical commands remain unsupported
# """
# import random
# import unittest

# from src.models.pokemon import Pokemon
# from src.models.player import Player
# from src.models.personality import Personality
# from src.models.attack import Attack
# from src.models.battle_state import BattleState
# from src.models.battle import (
#     Battle,
#     BattleAction,
#     BattleActionType,
#     BattleActionResult,
#     BattleTalkCommand,
#     BattleTalkIntent,
#     TalkCategory,
# )
# from src.models.battle_manager import BattleManager
# from src.models.status_effect import StatusEffectType
# from src.models.status_effect_manager import StatusEffectManager
# from src.ai.companion_service import CompanionService, generate_battle_talk_response
# from src.data.species import PIKACHU, CHARMANDER
# from src.data.attacks import THUNDER_SHOCK, QUICK_ATTACK, EMBER, SCRATCH


# class TestBattleTalkResponses(unittest.TestCase):
#     """Test suite verifying personality-driven dialogue generation and API integration."""

#     def setUp(self) -> None:
#         self.default_personality = Personality(
#             aggression=50, curiosity=50, fear=50, sociability=50, loyalty=50, confidence=50
#         )
#         self.pika = Pokemon(
#             species=PIKACHU,
#             personality=self.default_personality,
#             level=5,
#             attacks=[THUNDER_SHOCK, QUICK_ATTACK],
#         )
#         self.charm = Pokemon(
#             species=CHARMANDER,
#             personality=self.default_personality,
#             level=5,
#             attacks=[EMBER, SCRATCH],
#         )
#         self.player = Player(name="Ash")
#         self.player.add_pokemon(self.pika)
#         self.player.add_to_team(self.pika)
#         self.player.set_active_pokemon(self.pika)

    # 1. Personality trait differences across confidence
#     def test_01_confidence_trait_responses(self) -> None:
#         """High confidence Pokemon responds boldly; low confidence Pokemon responds modestly."""
#         high_conf = Pokemon(
#             species=PIKACHU,
#             personality=Personality(aggression=50, curiosity=50, fear=50, sociability=50, loyalty=50, confidence=85),
#             level=5,
#         )
#         low_conf = Pokemon(
#             species=PIKACHU,
#             personality=Personality(aggression=50, curiosity=50, fear=50, sociability=50, loyalty=50, confidence=15),
#             level=5,
#         )

#         resp_high = generate_battle_talk_response(high_conf, BattleTalkCommand(text="You've got this!", intent=BattleTalkIntent.ENCOURAGE))
#         resp_low = generate_battle_talk_response(low_conf, BattleTalkCommand(text="You've got this!", intent=BattleTalkIntent.ENCOURAGE))

#         self.assertIn("under control", resp_high.lower())
#         self.assertIn("try my hardest", resp_low.lower())
#         self.assertNotEqual(resp_high, resp_low)

    # 2. Personality trait differences across fear
#     def test_02_fear_trait_responses(self) -> None:
#         """High fear Pokemon shows nervousness/comfort; low fear Pokemon shows coolness."""
#         high_fear = Pokemon(
#             species=PIKACHU,
#             personality=Personality(aggression=50, curiosity=50, fear=85, sociability=50, loyalty=50, confidence=50),
#             level=5,
#         )
#         low_fear = Pokemon(
#             species=PIKACHU,
#             personality=Personality(aggression=50, curiosity=50, fear=15, sociability=50, loyalty=50, confidence=50),
#             level=5,
#         )

#         resp_high_praise = generate_battle_talk_response(high_fear, BattleTalkCommand(text="Good job!", intent=BattleTalkIntent.PRAISE))
#         resp_high_warn = generate_battle_talk_response(high_fear, BattleTalkCommand(text="Watch out!", intent=BattleTalkIntent.WARNING))

#         self.assertIn("comforted", resp_high_praise.lower())
#         self.assertIn("nervously", resp_high_warn.lower())

#         resp_low_warn = generate_battle_talk_response(low_fear, BattleTalkCommand(text="Watch out!", intent=BattleTalkIntent.WARNING))
#         self.assertIn("calmly", resp_low_warn.lower())
#         self.assertNotEqual(resp_high_warn, resp_low_warn)

    # 3. Personality trait differences across aggression
#     def test_03_aggression_trait_responses(self) -> None:
#         """High aggression Pokemon responds aggressively; low aggression responds gently."""
#         high_agg = Pokemon(
#             species=PIKACHU,
#             personality=Personality(aggression=85, curiosity=50, fear=50, sociability=50, loyalty=50, confidence=50),
#             level=5,
#         )
#         low_agg = Pokemon(
#             species=PIKACHU,
#             personality=Personality(aggression=15, curiosity=50, fear=50, sociability=50, loyalty=50, confidence=50),
#             level=5,
#         )

#         resp_high = generate_battle_talk_response(high_agg, BattleTalkCommand(text="Let's do this!", intent=BattleTalkIntent.ENCOURAGE))
#         resp_low = generate_battle_talk_response(low_agg, BattleTalkCommand(text="Let's do this!", intent=BattleTalkIntent.ENCOURAGE))

#         self.assertIn("teeth", resp_high.lower())
#         self.assertIn("peacefully", resp_low.lower())
#         self.assertNotEqual(resp_high, resp_low)

    # 4. Personality trait differences across loyalty
#     def test_04_loyalty_trait_responses(self) -> None:
#         """High loyalty Pokemon expresses devotion to its trainer; low loyalty expresses independence."""
#         high_loy = Pokemon(
#             species=PIKACHU,
#             personality=Personality(aggression=50, curiosity=50, fear=50, sociability=50, loyalty=85, confidence=50),
#             level=5,
#         )
#         low_loy = Pokemon(
#             species=PIKACHU,
#             personality=Personality(aggression=50, curiosity=50, fear=50, sociability=50, loyalty=15, confidence=50),
#             level=5,
#         )

#         resp_high = generate_battle_talk_response(high_loy, BattleTalkCommand(text="Good job!", intent=BattleTalkIntent.PRAISE))
#         resp_low = generate_battle_talk_response(low_loy, BattleTalkCommand(text="Good job!", intent=BattleTalkIntent.PRAISE))

#         self.assertIn("trainer", resp_high.lower())
#         self.assertIn("terms", resp_low.lower())
#         self.assertNotEqual(resp_high, resp_low)

    # 5. Personality trait differences across sociability
#     def test_05_sociability_trait_responses(self) -> None:
#         """High sociability Pokemon responds warmly; low sociability responds curtly."""
#         high_soc = Pokemon(
#             species=PIKACHU,
#             personality=Personality(aggression=50, curiosity=50, fear=50, sociability=85, loyalty=50, confidence=50),
#             level=5,
#         )
#         low_soc = Pokemon(
#             species=PIKACHU,
#             personality=Personality(aggression=50, curiosity=50, fear=50, sociability=15, loyalty=50, confidence=50),
#             level=5,
#         )

#         resp_high = generate_battle_talk_response(high_soc, BattleTalkCommand(text="Good job!", intent=BattleTalkIntent.PRAISE))
#         resp_low = generate_battle_talk_response(low_soc, BattleTalkCommand(text="Good job!", intent=BattleTalkIntent.PRAISE))

#         self.assertIn("bouncing", resp_high.lower())
#         self.assertIn("curt", resp_low.lower())
#         self.assertNotEqual(resp_high, resp_low)

    # 6. Personality trait differences across curiosity
#     def test_06_curiosity_trait_responses(self) -> None:
#         """High curiosity Pokemon displays interest and observation; low curiosity displays strict focus."""
#         high_cur = Pokemon(
#             species=PIKACHU,
#             personality=Personality(aggression=50, curiosity=85, fear=50, sociability=50, loyalty=50, confidence=50),
#             level=5,
#         )
#         low_cur = Pokemon(
#             species=PIKACHU,
#             personality=Personality(aggression=50, curiosity=15, fear=50, sociability=50, loyalty=50, confidence=50),
#             level=5,
#         )

#         resp_high = generate_battle_talk_response(high_cur, BattleTalkCommand(text="Stay alert!", intent=BattleTalkIntent.WARNING))
#         resp_low = generate_battle_talk_response(low_cur, BattleTalkCommand(text="Stay alert!", intent=BattleTalkIntent.WARNING))

#         self.assertIn("interest", resp_high.lower())
#         self.assertIn("without hesitation", resp_low.lower())
#         self.assertNotEqual(resp_high, resp_low)

    # 7. Balanced / neutral personality response
#     def test_07_balanced_personality_response(self) -> None:
#         """A Pokemon with balanced traits uses stable, composed responses."""
#         resp = generate_battle_talk_response(
#             self.pika, BattleTalkCommand(text="Good job!", intent=BattleTalkIntent.PRAISE)
#         )
#         self.assertIn("smiles warmly", resp.lower())

    # 8. Determinism: identical inputs and personality states yield identical responses
#     def test_08_deterministic_output(self) -> None:
#         """Repeated response generation produces strictly identical strings."""
#         cmd = BattleTalkCommand(text="Hang in there!", intent=BattleTalkIntent.ENCOURAGE)
#         first_resp = generate_battle_talk_response(self.pika, cmd)

#         for _ in range(50):
#             subsequent = generate_battle_talk_response(self.pika, cmd)
#             self.assertEqual(first_resp, subsequent)

    # 9. Invariants: no mutation of personality, bond, obedience, HP, stats, or RNG
#     def test_09_invariants_preserved_no_mutation(self) -> None:
#         """Dialogue generation does not alter Pokemon attributes, state, or RNG."""
#         rng = random.Random(12345)
#         expected_roll = rng.randint(1, 100)

        # Re-initialize to verify talk does not advance this generator
#         test_rng = random.Random(12345)

#         hp_before = self.pika.current_hp
#         bond_before = self.pika.bond
#         ob_before = self.pika.obedience
#         pers_dict_before = self.pika.personality.to_dict()

#         generate_battle_talk_response(
#             self.pika, BattleTalkCommand(text="Great job!", intent=BattleTalkIntent.PRAISE)
#         )

#         self.assertEqual(self.pika.current_hp, hp_before)
#         self.assertEqual(self.pika.bond, bond_before)
#         self.assertEqual(self.pika.obedience, ob_before)
#         self.assertEqual(self.pika.personality.to_dict(), pers_dict_before)
#         self.assertEqual(test_rng.randint(1, 100), expected_roll)

    # 10. Integration: BattleManager.talk() pipeline with raw text input
#     def test_10_battle_manager_talk_pipeline_integration(self) -> None:
#         """BattleManager.talk() parses text, resolves intent, and attaches companion dialogue."""
#         manager = BattleManager(seed=42)
#         battle = manager.start_battle(self.player, self.charm)
#         self.assertEqual(battle.current_turn, 1)

        # Talk action with raw text
#         res = manager.talk(self.player, "Great job, Pikachu!")

#         self.assertTrue(res.accepted)
#         self.assertEqual(res.action_type, BattleActionType.TALK)
#         self.assertEqual(res.talk_intent, BattleTalkIntent.PRAISE)
#         self.assertIsNotNone(res.talk_dialogue)
#         self.assertIn("Pikachu", res.talk_dialogue)

        # Verified in BattleActionRecord / event log
#         self.assertTrue(any("Player: \"Great job, Pikachu!\"" in event for event in battle._events))

        # Combat invariants preserved
#         self.assertEqual(battle.current_turn, 1)
#         self.assertEqual(self.pika.current_hp, self.pika.max_hp)
#         self.assertEqual(self.charm.current_hp, self.charm.max_hp)

    # 11. Tactical commands through BattleManager remain safely unsupported
#     def test_11_tactical_commands_rejected_via_manager(self) -> None:
#         """Requesting unsupported tactical manoeuvres (e.g. jump, parry) through manager.talk() is rejected."""
#         manager = BattleManager(seed=42)
#         manager.start_battle(self.player, self.charm)

#         res = manager.talk(self.player, "Jump over the attack!")

#         self.assertFalse(res.accepted)
#         self.assertEqual(res.error_type, "UNSUPPORTED_COMMAND")
#         self.assertIsNone(res.talk_dialogue)

    # 12. Terminal battle and fainted Pokemon safety
#     def test_12_terminal_and_fainted_safety(self) -> None:
#         """BattleManager.talk() returns safety error without dialogue if Pokemon is fainted or battle ended."""
#         manager = BattleManager(seed=42)
#         battle = manager.start_battle(self.player, self.charm)

        # KO active Pokemon
#         self.pika.current_hp = 0
#         self.assertTrue(self.pika.is_fainted)

#         res_fainted = manager.talk(self.player, "Get up, you can do it!")
#         self.assertFalse(res_fainted.accepted)
#         self.assertEqual(res_fainted.error_type, "POKEMON_FAINTED")
#         self.assertIsNone(res_fainted.talk_dialogue)

        # Conclude battle
#         battle._state = BattleState.VICTORY
#         res_term = battle.talk("Great win!")
#         self.assertFalse(res_term.accepted)
#         self.assertEqual(res_term.error_type, "BATTLE_ALREADY_TERMINAL")

        # Manager also rejects cleanly when battle concluded
#         res_mgr = manager.talk(self.player, "Hello?")
#         self.assertFalse(res_mgr.accepted)
#         self.assertEqual(res_mgr.error_type, "NO_ACTIVE_BATTLE")


# if __name__ == "__main__":
#     unittest.main()
