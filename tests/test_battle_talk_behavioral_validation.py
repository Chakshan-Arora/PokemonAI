# """
# Comprehensive behavioral validation test suite for Battle Talk (BT5.4).

# Validates:
# A. Personality consistency across 6 core profiles (Confidence, Fear, Loyalty,
#    Aggression, Curiosity, Balanced) across 7 dialogue situations.
# B. Combat milestone priority and reaction purity (no string concatenation,
#    clean knockout priority, status faint isolation).
# C. Event freshness, multi-turn lifecycle, deduplication, and turn bounds.
# D. Tactical instruction behavior (Dodge routing, negated commands, ambiguous
#    commands, unsupported manoeuvres, obedience and physical evasion).
# E. Combat-state isolation (zero mutation of HP, stats, bond, status, or turn progression).
# F. Fallback and failure handling (missing personality, partial traits, unknown events,
#    malformed inputs).
# """
# import copy
# import unittest
# from dataclasses import replace
# from typing import Any

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
#     BattleActionRecord,
#     BattleTalkCommand,
#     BattleTalkIntent,
#     TalkCategory,
#     TurnResult,
# )
# from src.models.battle_manager import BattleManager
# from src.models.status_effect import StatusEffect, StatusEffectType
# from src.ai.companion_service import (
#     CompanionService,
#     BattleTalkContext,
#     generate_battle_talk_response,
# )
# from src.ai.battle_talk_parser import BattleTalkParser, parse_battle_talk
# from src.data.species import PIKACHU, CHARMANDER, SQUIRTLE
# from src.data.attacks import THUNDER_SHOCK, QUICK_ATTACK, EMBER, SCRATCH, WATER_GUN


# class TestPersonalityConsistency(unittest.TestCase):
#     """
#     Validation Area A: Verify that existing personality profiles produce
#     recognizably different responses to the same event across 7 key situations.
#     """

#     def setUp(self) -> None:
#         self.profiles = {
#             "confidence": Personality(confidence=85, fear=50, aggression=50, loyalty=50, sociability=50, curiosity=50),
#             "fear": Personality(confidence=50, fear=85, aggression=50, loyalty=50, sociability=50, curiosity=50),
#             "loyalty": Personality(confidence=50, fear=50, aggression=50, loyalty=85, sociability=50, curiosity=50),
#             "aggression": Personality(confidence=50, fear=50, aggression=85, loyalty=50, sociability=50, curiosity=50),
#             "curiosity": Personality(confidence=50, fear=50, aggression=50, loyalty=50, sociability=50, curiosity=85),
#             "balanced": Personality(confidence=50, fear=50, aggression=50, loyalty=50, sociability=50, curiosity=50),
#         }
#         self.cmd = BattleTalkCommand(text="Hang in there!", intent=BattleTalkIntent.ENCOURAGE)

#     def _create_mon(self, personality: Personality) -> Pokemon:
#         return Pokemon(species=PIKACHU, personality=personality, level=5)

#     def test_01_low_hp_differentiation(self) -> None:
#         """Low HP (<= 25%) produces personality-consistent dialogue for all 6 profiles."""
#         responses = {}
#         for name, pers in self.profiles.items():
#             mon = self._create_mon(pers)
#             ctx = BattleTalkContext(is_low_hp=True, hp_percent=0.15)
#             resp = generate_battle_talk_response(mon, self.cmd, context=ctx)
#             self.assertIsInstance(resp, str)
#             self.assertGreater(len(resp), 0)
#             responses[name] = resp

        # Verify thematic hallmarks
#         self.assertIn("still fight", responses["confidence"].lower())
#         self.assertIn("desperate", responses["fear"].lower())
#         self.assertIn("won't let you down", responses["loyalty"].lower())
#         self.assertIn("tearing them down", responses["aggression"].lower())
#         self.assertIn("rhythm", responses["curiosity"].lower())
#         self.assertIn("pain", responses["balanced"].lower())

        # Ensure responses are distinct between profiles
#         self.assertNotEqual(responses["confidence"], responses["fear"])
#         self.assertNotEqual(responses["aggression"], responses["loyalty"])

#     def test_02_status_condition_differentiation(self) -> None:
#         """Paralysis condition produces personality-consistent dialogue."""
#         responses = {}
#         for name, pers in self.profiles.items():
#             mon = self._create_mon(pers)
#             ctx = BattleTalkContext(status_condition="paralysis")
#             resp = generate_battle_talk_response(mon, self.cmd, context=ctx)
#             responses[name] = resp

#         self.assertIn("sparks", responses["confidence"].lower())
#         self.assertIn("locked up", responses["fear"].lower())
#         self.assertIn("let you down", responses["loyalty"].lower())
#         self.assertIn("won't save them", responses["aggression"].lower())
        # Curiosity safely falls back to balanced
#         self.assertIn("stiffness", responses["curiosity"].lower())
#         self.assertIn("stiffness", responses["balanced"].lower())

#     def test_03_dodge_success_differentiation(self) -> None:
#         """Dodge success produces personality-consistent dialogue."""
#         responses = {}
#         for name, pers in self.profiles.items():
#             mon = self._create_mon(pers)
#             ctx = BattleTalkContext(last_event="dodge_success")
#             resp = generate_battle_talk_response(mon, self.cmd, context=ctx)
#             responses[name] = resp

#         self.assertIn("scratch", responses["confidence"].lower())
#         self.assertIn("too close", responses["fear"].lower())
#         self.assertIn("trainer", responses["loyalty"].lower())
#         self.assertIn("too slow", responses["aggression"].lower())
#         self.assertIn("trajectory", responses["curiosity"].lower())
#         self.assertIn("smoothly", responses["balanced"].lower())

#     def test_04_dodge_failed_differentiation(self) -> None:
#         """Dodge failure produces personality-consistent dialogue."""
#         responses = {}
#         for name, pers in self.profiles.items():
#             mon = self._create_mon(pers)
#             ctx = BattleTalkContext(last_event="dodge_failed")
#             resp = generate_battle_talk_response(mon, self.cmd, context=ctx)
#             responses[name] = resp

#         self.assertIn("lucky hit", responses["confidence"].lower())
#         self.assertIn("cowers", responses["fear"].lower())
#         self.assertIn("sorry", responses["loyalty"].lower())
#         self.assertIn("payback", responses["aggression"].lower())
#         self.assertIn("timing", responses["curiosity"].lower())
#         self.assertIn("recovers", responses["balanced"].lower())

#     def test_05_critical_hit_differentiation(self) -> None:
#         """Critical hit produces personality-consistent dialogue."""
#         responses = {}
#         for name, pers in self.profiles.items():
#             mon = self._create_mon(pers)
#             ctx = BattleTalkContext(is_critical_hit=True)
#             resp = generate_battle_talk_response(mon, self.cmd, context=ctx)
#             responses[name] = resp

#         self.assertIn("sweet spot", responses["confidence"].lower())
#         self.assertIn("vulnerable", responses["fear"].lower())
#         self.assertIn("trainer", responses["loyalty"].lower())
#         self.assertIn("smashed", responses["aggression"].lower())
#         self.assertIn("angle", responses["curiosity"].lower())
#         self.assertIn("clean", responses["balanced"].lower())

#     def test_06_super_effective_differentiation(self) -> None:
#         """Super-effective hit produces personality-consistent dialogue."""
#         responses = {}
#         for name, pers in self.profiles.items():
#             mon = self._create_mon(pers)
#             ctx = BattleTalkContext(is_super_effective=True)
#             resp = generate_battle_talk_response(mon, self.cmd, context=ctx)
#             responses[name] = resp

#         self.assertIn("bullseye", responses["confidence"].lower())
#         self.assertIn("nervous", responses["fear"].lower())
#         self.assertIn("weakness", responses["loyalty"].lower())
#         self.assertIn("crushed", responses["aggression"].lower())
#         self.assertIn("matchup", responses["curiosity"].lower())
#         self.assertIn("satisfaction", responses["balanced"].lower())

#     def test_07_opponent_knockout_differentiation(self) -> None:
#         """Opponent knockout produces personality-consistent dialogue."""
#         responses = {}
#         for name, pers in self.profiles.items():
#             mon = self._create_mon(pers)
#             ctx = BattleTalkContext(is_opponent_knockout=True)
#             resp = generate_battle_talk_response(mon, self.cmd, context=ctx)
#             responses[name] = resp

#         self.assertIn("down for the count", responses["confidence"].lower())
#         self.assertIn("safe now", responses["fear"].lower())
#         self.assertIn("target neutralized", responses["loyalty"].lower())
#         self.assertIn("roar", responses["aggression"].lower())
#         self.assertIn("fascination", responses["curiosity"].lower())
#         self.assertIn("decisive", responses["balanced"].lower())


# class TestCombatMilestonePriorityAndPurity(unittest.TestCase):
#     """
#     Validation Area B: Verify priority hierarchy and ensure milestone reactions
#     never concatenate multiple phrases into one response.
#     """

#     def setUp(self) -> None:
#         self.default_personality = Personality(50, 50, 50, 50, 50, 50)
#         self.pika = Pokemon(
#             species=PIKACHU,
#             personality=Personality(confidence=85, fear=50, aggression=50, loyalty=50, sociability=50, curiosity=50),
#             level=5,
#         )
#         self.charm = Pokemon(species=CHARMANDER, personality=self.default_personality, level=5)
#         self.cmd = BattleTalkCommand(text="Great move!", intent=BattleTalkIntent.PRAISE)

#     def test_01_knockout_supersedes_all_and_does_not_concatenate(self) -> None:
#         """A finishing blow that was also critical + super-effective outputs pure knockout dialogue."""
#         ctx = BattleTalkContext(is_opponent_knockout=True, is_critical_hit=True, is_super_effective=True)
#         resp = generate_battle_talk_response(self.pika, self.cmd, context=ctx)

        # Must contain knockout text
#         self.assertIn("down for the count", resp.lower())
        # Must NOT contain critical hit or super effective phrases
#         self.assertNotIn("sweet spot", resp.lower())
#         self.assertNotIn("bullseye", resp.lower())
#         self.assertNotIn("maximum power", resp.lower())

#     def test_02_combined_crit_and_super_effective_purity(self) -> None:
#         """Combined crit + super-effective generates combined template without separate fragments."""
#         ctx = BattleTalkContext(is_critical_hit=True, is_super_effective=True)
#         resp = generate_battle_talk_response(self.pika, self.cmd, context=ctx)

#         self.assertIn("unstoppable", resp.lower())
        # Should not duplicate the standalone critical or super-effective text
#         self.assertNotIn("sweet spot", resp.lower())
#         self.assertNotIn("bullseye", resp.lower())

#     def test_03_status_induced_faint_isolation_recheck(self) -> None:
#         """Poison tick knockout after surviving attack does NOT trigger knockout milestone."""
#         battle = Battle(pokemon1=self.pika, pokemon2=self.charm, seed=42)
#         battle.start()

        # Attack hit for 10 damage, Charmander survives with 15 HP
#         record = BattleActionRecord(
#             attacker=self.pika,
#             defender=self.charm,
#             attack=THUNDER_SHOCK,
#             hit=True,
#             damage=10,
#             type_effectiveness=1.0,
#             defender_hp_remaining=15,
#             message="Thunder Shock hit!",
#             is_critical=False,
#         )
        # Charmander faints at end of turn from status
#         self.charm.take_damage(self.charm.max_hp)
#         self.assertTrue(self.charm.is_fainted)

#         battle._history.append(TurnResult(turn_number=1, actions=(record,), battle_state=BattleState.VICTORY))

        # Milestone must be None, NOT opponent_knockout
#         milestone = battle.get_latest_player_combat_milestone()
#         self.assertIsNone(milestone)


# class TestEventFreshnessAndMultiTurnLifecycle(unittest.TestCase):
#     """
#     Validation Area C: Test realistic multi-turn combat sequences, consumption,
#     expiry, deduplication, and single accepted TALK per turn.
#     """

#     def setUp(self) -> None:
#         self.default_personality = Personality(50, 50, 50, 50, 50, 50)
#         self.pika = Pokemon(species=PIKACHU, personality=self.default_personality, level=5, attacks=[THUNDER_SHOCK, QUICK_ATTACK])
#         self.charm = Pokemon(species=CHARMANDER, personality=self.default_personality, level=5, attacks=[EMBER, SCRATCH])
#         self.player = Player(name="Ash")
#         self.player.add_pokemon(self.pika)
#         self.player.add_to_team(self.pika)
#         self.player.set_active_pokemon(self.pika)
#         self.manager = BattleManager()

#     def test_01_multi_turn_flow_with_milestones_and_talk(self) -> None:
#         """
#         Step-by-step multi-turn flow:
#         1. Turn 1: Player lands super-effective attack.
#         2. Turn 2: Player talks -> receives super-effective reaction.
#         3. Turn 2: Player tries talking again -> rejected (one-talk-per-turn).
#         4. Turn 2: Player lands critical hit -> turn resolves.
#         5. Turn 3: Player talks -> receives fresh critical-hit reaction.
#         6. Turn 3: Combat action resolves with no milestone.
#         7. Turn 4: Player talks -> milestone expired, receives standard dialogue.
#         """
#         battle = self.manager.start_battle(self.player, self.charm)
#         self.assertEqual(battle.current_turn, 1)

        # 1. Turn 1 resolves with super-effective attack
#         rec1 = BattleActionRecord(
#             attacker=self.pika, defender=self.charm, attack=THUNDER_SHOCK, hit=True,
#             damage=15, type_effectiveness=2.0, defender_hp_remaining=20, message="Super effective!",
#             is_critical=False,
#         )
#         battle._history.append(TurnResult(turn_number=1, actions=(rec1,), battle_state=BattleState.IN_PROGRESS))
#         battle._current_turn = 2

        # 2. Turn 2: Player requests TALK
#         res_talk1 = self.manager.talk(self.player, "Great attack!")
#         self.assertTrue(res_talk1.accepted)
#         self.assertIn("satisfaction", res_talk1.talk_dialogue.lower())

        # 3. Turn 2: Player tries talking again -> rejected
#         res_talk2 = self.manager.talk(self.player, "Keep it up!")
#         self.assertFalse(res_talk2.accepted)
#         self.assertEqual(res_talk2.error_type, "TALK_LIMIT_REACHED")

        # 4. Turn 2: Combat occurs (critical hit)
#         rec2 = BattleActionRecord(
#             attacker=self.pika, defender=self.charm, attack=THUNDER_SHOCK, hit=True,
#             damage=25, type_effectiveness=1.0, defender_hp_remaining=5, message="Critical hit!",
#             is_critical=True,
#         )
#         battle._history.append(TurnResult(turn_number=2, actions=(rec2,), battle_state=BattleState.IN_PROGRESS))
#         battle._current_turn = 3

        # 5. Turn 3: Player requests TALK -> receives fresh critical hit reaction
#         res_talk3 = self.manager.talk(self.player, "Amazing!")
#         self.assertTrue(res_talk3.accepted)
#         self.assertIn("clean critical strike", res_talk3.talk_dialogue.lower())
#         self.assertNotIn("super-effective", res_talk3.talk_dialogue.lower())

        # 6. Turn 3: Combat action with standard non-milestone hit
#         rec3 = BattleActionRecord(
#             attacker=self.pika, defender=self.charm, attack=QUICK_ATTACK, hit=True,
#             damage=4, type_effectiveness=1.0, defender_hp_remaining=1, message="Quick attack",
#             is_critical=False,
#         )
#         battle._history.append(TurnResult(turn_number=3, actions=(rec3,), battle_state=BattleState.IN_PROGRESS))
#         battle._current_turn = 4

        # 7. Turn 4: Player requests TALK -> milestone is expired, normal baseline dialogue returned
#         res_talk4 = self.manager.talk(self.player, "Hang in there!")
#         self.assertTrue(res_talk4.accepted)
        # Should return baseline PRAISE/ENCOURAGE, NOT critical or super-effective
#         self.assertNotIn("clean critical strike", res_talk4.talk_dialogue.lower())
#         self.assertNotIn("super-effective", res_talk4.talk_dialogue.lower())
#         self.assertIn("bolstered by your encouragement", res_talk4.talk_dialogue.lower())

#     def test_02_battle_instance_isolation(self) -> None:
#         """Milestones and consumption do not leak across separate battles."""
#         battle1 = Battle(pokemon1=self.pika, pokemon2=self.charm, seed=1)
#         battle2 = Battle(pokemon1=self.pika, pokemon2=self.charm, seed=2)
#         battle1.start()
#         battle2.start()

        # Battle 1 gets a milestone
#         rec = BattleActionRecord(
#             attacker=self.pika, defender=self.charm, attack=THUNDER_SHOCK, hit=True,
#             damage=30, type_effectiveness=1.0, defender_hp_remaining=0, message="KO!",
#         )
#         battle1._history.append(TurnResult(turn_number=1, actions=(rec,), battle_state=BattleState.VICTORY))
#         self.assertEqual(battle1.get_latest_player_combat_milestone(mark_consumed=True), "opponent_knockout")

        # Battle 2 must remain completely unaware
#         self.assertIsNone(battle2.get_latest_player_combat_milestone())
#         self.assertIsNone(battle2._consumed_milestone_turn)


# class TestTacticalInstructionBehavior(unittest.TestCase):
#     """
#     Validation Area D: Verify tactical talk parsing and Dodge flow across valid,
#     negated, ambiguous, and unsupported commands.
#     """

#     def setUp(self) -> None:
#         self.default_personality = Personality(50, 50, 50, 50, 50, 50)
#         self.pika = Pokemon(species=PIKACHU, personality=self.default_personality, level=5, attacks=[THUNDER_SHOCK])
#         self.charm = Pokemon(species=CHARMANDER, personality=self.default_personality, level=5, attacks=[EMBER])
#         self.player = Player(name="Ash")
#         self.player.add_pokemon(self.pika)
#         self.player.add_to_team(self.pika)
#         self.player.set_active_pokemon(self.pika)
#         self.manager = BattleManager()

#     def test_01_valid_dodge_instruction(self) -> None:
#         """Valid dodge phrasing routes to BattleActionType.DODGE and advances combat turn."""
#         battle = self.manager.start_battle(self.player, self.charm, seed=42)
#         initial_turn = battle.current_turn

#         res = self.manager.talk(self.player, "Dodge the next attack!")
#         self.assertTrue(res.accepted)
#         self.assertEqual(res.action_type, BattleActionType.DODGE)
#         self.assertIsInstance(res.dodge_successful, bool)
#         self.assertIsNotNone(res.dodge_probability)
#         self.assertEqual(battle.current_turn, initial_turn + 1)

#     def test_02_negated_dodge_instruction(self) -> None:
#         """Negated command ('Don't dodge!') is conversational and does NOT execute dodge."""
#         battle = self.manager.start_battle(self.player, self.charm, seed=42)
#         initial_turn = battle.current_turn

        # Should be parsed as conversational GENERAL, not tactical
#         cmd = parse_battle_talk("Don't dodge!")
#         self.assertFalse(cmd.is_tactical)
#         self.assertEqual(cmd.category, TalkCategory.CONVERSATIONAL)
#         self.assertTrue(cmd.metadata.get("negated_tactical"))

        # In battle, it executes as conversational talk (turn does NOT advance)
#         res = self.manager.talk(self.player, "Don't dodge!")
#         self.assertTrue(res.accepted)
#         self.assertEqual(res.action_type, BattleActionType.TALK)
#         self.assertEqual(battle.current_turn, initial_turn)

#     def test_03_ambiguous_instruction(self) -> None:
#         """Ambiguous phrasing is treated as conversational GENERAL."""
#         cmd = parse_battle_talk("Maybe we should move around?")
#         self.assertFalse(cmd.is_tactical)
#         self.assertEqual(cmd.category, TalkCategory.CONVERSATIONAL)
#         self.assertEqual(cmd.intent, BattleTalkIntent.GENERAL)

#     def test_04_unsupported_tactical_manoeuvre(self) -> None:
#         """Unsupported tactical manoeuvre ('Block the attack!') is safely rejected."""
#         battle = self.manager.start_battle(self.player, self.charm, seed=42)
#         initial_turn = battle.current_turn

#         res = self.manager.talk(self.player, "Block the attack!")
#         self.assertFalse(res.accepted)
#         self.assertEqual(res.error_type, "UNSUPPORTED_COMMAND")
#         self.assertIn("unsupported", res.reason.lower())
        # Turn must not advance
#         self.assertEqual(battle.current_turn, initial_turn)

#     def test_05_parsing_does_not_execute_actions(self) -> None:
#         """Parsing a string does not mutate battle state or execute any action."""
#         cmd = BattleTalkParser.parse("Dodge right now!")
#         self.assertTrue(cmd.is_tactical)
#         self.assertEqual(cmd.category, TalkCategory.TACTICAL)


# class TestCombatStateIsolation(unittest.TestCase):
#     """
#     Validation Area E: Confirm dialogue generation does not modify HP, stats,
#     bond, status, turn progression, or combat outcomes.
#     """

#     def setUp(self) -> None:
#         self.default_personality = Personality(50, 50, 50, 50, 50, 50)
#         self.pika = Pokemon(
#             species=PIKACHU,
#             personality=Personality(confidence=70, fear=50, aggression=50, loyalty=50, sociability=50, curiosity=50),
#             level=5,
#             attacks=[THUNDER_SHOCK],
#         )
#         self.pika.bond = 40
#         self.charm = Pokemon(species=CHARMANDER, personality=self.default_personality, level=5, attacks=[EMBER])
#         self.player = Player(name="Ash")
#         self.player.add_pokemon(self.pika)
#         self.player.add_to_team(self.pika)
#         self.player.set_active_pokemon(self.pika)
#         self.manager = BattleManager()

#     def test_01_talk_does_not_mutate_pokemon_attributes(self) -> None:
#         """Conversational talk leaves all Pokemon combat attributes identical."""
#         battle = self.manager.start_battle(self.player, self.charm, seed=42)

        # Snapshot before talk
#         hp_before = self.pika.current_hp
#         max_hp_before = self.pika.max_hp
#         bond_before = self.pika.bond
#         atk_before = self.pika.attack
#         def_before = self.pika.defense
#         spd_before = self.pika.speed
#         turn_before = battle.current_turn

#         res = self.manager.talk(self.player, "You're doing great, Pikachu!")
#         self.assertTrue(res.accepted)

        # Snapshot after talk
#         self.assertEqual(self.pika.current_hp, hp_before)
#         self.assertEqual(self.pika.max_hp, max_hp_before)
#         self.assertEqual(self.pika.bond, bond_before)
#         self.assertEqual(self.pika.attack, atk_before)
#         self.assertEqual(self.pika.defense, def_before)
#         self.assertEqual(self.pika.speed, spd_before)
#         self.assertEqual(battle.current_turn, turn_before)

#     def test_02_milestone_queries_are_pure(self) -> None:
#         """Querying get_latest_player_combat_milestone(mark_consumed=False) causes zero mutations."""
#         battle = Battle(pokemon1=self.pika, pokemon2=self.charm, seed=42)
#         battle.start()

#         rec = BattleActionRecord(
#             attacker=self.pika, defender=self.charm, attack=THUNDER_SHOCK, hit=True,
#             damage=10, type_effectiveness=2.0, defender_hp_remaining=10, message="Hit",
#         )
#         battle._history.append(TurnResult(turn_number=1, actions=(rec,), battle_state=BattleState.IN_PROGRESS))

        # Query without consuming
#         m1 = battle.get_latest_player_combat_milestone(mark_consumed=False)
#         m2 = battle.get_latest_player_combat_milestone(mark_consumed=False)
#         self.assertEqual(m1, "super_effective")
#         self.assertEqual(m2, "super_effective")
#         self.assertIsNone(battle._consumed_milestone_turn)


# class TestFallbackAndFailureHandling(unittest.TestCase):
#     """
#     Validation Area F: Inspect system behavior when personality is missing,
#     context is empty, or inputs are malformed.
#     """

#     def test_01_missing_personality_defaults_to_balanced(self) -> None:
#         """Pokemon with personality=None falls back safely to balanced templates."""
#         mon = Pokemon(species=PIKACHU, personality=Personality(50, 50, 50, 50, 50, 50), level=5)
#         mon._personality = None

#         cmd = BattleTalkCommand(text="Hang in there!", intent=BattleTalkIntent.ENCOURAGE)
#         resp = generate_battle_talk_response(mon, cmd)
#         self.assertIsInstance(resp, str)
#         self.assertIn("bolstered by your encouragement", resp.lower())

#     def test_02_partial_personality_traits(self) -> None:
#         """Custom object with missing personality traits defaults missing fields to 50."""
#         class PartialPersonality:
#             confidence = 80
            # fear, aggression, loyalty, sociability, curiosity omitted

#         mon = Pokemon(species=PIKACHU, personality=Personality(50, 50, 50, 50, 50, 50), level=5)
#         mon._personality = PartialPersonality()

#         cmd = BattleTalkCommand(text="Good job!", intent=BattleTalkIntent.PRAISE)
#         resp = generate_battle_talk_response(mon, cmd)
#         self.assertIsInstance(resp, str)
        # Should pick high_confidence because confidence=80 is deviation 30
#         self.assertIn("knew i had it in me", resp.lower())

#     def test_03_unknown_event_falls_back_gracefully(self) -> None:
#         """An unknown event string safely falls back to standard profile templates."""
#         mon = Pokemon(species=PIKACHU, personality=Personality(50, 50, 50, 50, 50, 50), level=5)
#         ctx = BattleTalkContext(last_event="unknown_event_foo_bar")
#         cmd = BattleTalkCommand(text="Keep going!", intent=BattleTalkIntent.ENCOURAGE)

#         resp = generate_battle_talk_response(mon, cmd, context=ctx)
#         self.assertIsInstance(resp, str)
#         self.assertIn("bolstered by your encouragement", resp.lower())

#     def test_04_malformed_parser_input(self) -> None:
#         """None, empty, or whitespace-only inputs parse safely into GENERAL intent."""
#         for val in (None, "", "   ", "\t\n"):
#             cmd = parse_battle_talk(val)
#             self.assertEqual(cmd.category, TalkCategory.CONVERSATIONAL)
#             self.assertEqual(cmd.intent, BattleTalkIntent.GENERAL)
#             self.assertFalse(cmd.is_tactical)


# if __name__ == "__main__":
#     unittest.main()
