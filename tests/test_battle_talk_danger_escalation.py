# """
# Unit tests for BT5.5C: Danger Escalation and Duplicate Suppression.
#
# Tests the following specifications:
# 1. Low-tier reaction at exactly 25% HP.
# 2. No low-tier reaction above 25% HP (healthy baseline preserved).
# 3. Critical reaction at exactly 10% HP.
# 4. Critical reaction supersedes a previously consumed low-tier warning.
# 5. Repeated TALK does not repeat a consumed warning while remaining in the same danger tier.
# 6. Healing above a tier boundary resets consumed state and re-enables reaction upon re-entry.
# 7. Substantial additional damage within the same tier retriggers a fresh reaction at threshold.
# 8. High-priority combat milestones do not erase unserved danger reactions (deferred delivery).
# 9. Opponent-switch and danger events do not overwrite one another (strict priority ordering).
# 10. Battle-instance isolation (independent tracking per battle session).
# 11. Missing/invalid HP handling fails safely to normal baseline.
# 12. Personality-aware differentiation across all 13 profiles for critical vs low tiers.
# 13. Existing Battle Talk invariants and mechanics preserved without mutation.
# """
# import random
# import unittest
#
# from src.models.pokemon import Pokemon
# from src.models.personality import Personality
# from src.models.battle import (
#     Battle,
#     BattleAction,
#     BattleActionType,
#     BattleActionRecord,
#     BattleTalkCommand,
#     BattleTalkIntent,
#     TurnResult,
# )
# from src.models.battle_state import BattleState
# from src.models.player import Player
# from src.models.trainer import Trainer, TrainerArchetype, DifficultyProfile
# from src.models.battle_manager import BattleManager
# from src.ai.companion_service import (
#     CompanionService,
#     BattleTalkContext,
#     generate_battle_talk_response,
# )
# from src.data.species import PIKACHU, PIDGEY, RATTATA, CHARMANDER, SQUIRTLE, BULBASAUR
# from src.data.attacks import THUNDER_SHOCK, QUICK_ATTACK, TACKLE
#
#
# class TestBattleTalkDangerEscalation(unittest.TestCase):
#     """Test suite verifying danger escalation tiers, suppression, and event priority."""
#
#     def setUp(self) -> None:
#         self.default_personality = Personality(50, 50, 50, 50, 50, 50)
#         self.pika = Pokemon(
#             species=PIKACHU,
#             personality=self.default_personality,
#             level=25,
#             attacks=[THUNDER_SHOCK, QUICK_ATTACK],
#         )
#         self.player = Player(name="Ash")
#         self.player.add_pokemon(self.pika)
#         self.player.add_to_team(self.pika)
#         self.player.set_active_pokemon(self.pika)
#
#         self.rattata = Pokemon(
#             species=RATTATA,
#             personality=self.default_personality,
#             level=5,
#             attacks=[TACKLE],
#         )
#         self.pidgey = Pokemon(
#             species=PIDGEY,
#             personality=self.default_personality,
#             level=5,
#             attacks=[TACKLE],
#         )
#         self.trainer = Trainer(
#             trainer_id="youngster_joey",
#             name="Joey",
#             title="Youngster",
#             archetype=TrainerArchetype.YOUNGSTER,
#             difficulty=DifficultyProfile.NORMAL,
#             team=[self.rattata, self.pidgey],
#         )
#
#     # 1. Low-tier reaction at exactly 25% HP
#     def test_01_low_tier_reaction_at_exactly_25_percent(self) -> None:
#         """At exactly 25% HP, the companion triggers the low-danger reaction."""
#         # max_hp for level 25 Pikachu is 35 + (25 * 2) = 85
#         # Set current_hp to exactly 25% (or pass hp_percent=0.25)
#         ctx = BattleTalkContext(hp_percent=0.25)
#         resp = generate_battle_talk_response(self.pika, "Keep it up!", context=ctx)
#         # Balanced low-HP template phrase: "nods firmly through the pain"
#         self.assertIn("pain", resp.lower())
#         self.assertIn("bolstered by your encouragement", resp.lower())
#
#         # Also via Battle.get_pending_danger_tier
#         battle = Battle(self.pika, self.rattata, player=self.player)
#         battle.start()
#         # Set exactly 25% HP: e.g. 80 max_hp -> 20 current_hp
#         exact_25_hp = int(self.pika.max_hp * 0.25)
#         self.pika.current_hp = exact_25_hp
#         self.assertAlmostEqual(self.pika.current_hp / self.pika.max_hp, 0.25, delta=0.01)
#         tier = battle.get_pending_danger_tier(mark_consumed=False)
#         self.assertEqual(tier, "low")
#
#     # 2. No low-tier reaction above 25% HP
#     def test_02_no_low_tier_reaction_above_25_percent(self) -> None:
#         """Above 25% HP, companion uses normal healthy baseline templates."""
#         # hp_percent = 0.26
#         ctx_above = BattleTalkContext(hp_percent=0.26)
#         resp_above = generate_battle_talk_response(self.pika, "Keep it up!", context=ctx_above)
#         # Healthy balanced encouragement: "smiles warmly" or "nods firmly, bolstered" without pain
#         self.assertNotIn("pain", resp_above.lower())
#         self.assertNotIn("limit", resp_above.lower())
#
#         battle = Battle(self.pika, self.rattata, player=self.player)
#         battle.start()
#         # Set HP to 26%
#         hp_26 = int(self.pika.max_hp * 0.26) + 1
#         self.pika.current_hp = hp_26
#         self.assertGreater(self.pika.current_hp / self.pika.max_hp, 0.25)
#         self.assertIsNone(battle.get_pending_danger_tier(mark_consumed=False))
#
#     # 3. Critical reaction at exactly 10% HP
#     def test_03_critical_reaction_at_exactly_10_percent(self) -> None:
#         """At exactly 10% HP, the companion triggers the urgent critical danger reaction."""
#         ctx = BattleTalkContext(hp_percent=0.10)
#         resp = generate_battle_talk_response(self.pika, "Hang in there!", context=ctx)
#         # Balanced critical template: "absolute limit" or "exhausted legs"
#         self.assertIn("exhausted legs", resp.lower())
#         self.assertIn("barely holding on", resp.lower())
#
#         battle = Battle(self.pika, self.rattata, player=self.player)
#         battle.start()
#         hp_10 = int(self.pika.max_hp * 0.10)
#         self.pika.current_hp = hp_10
#         self.assertLessEqual(self.pika.current_hp / self.pika.max_hp, 0.10)
#         self.assertEqual(battle.get_pending_danger_tier(mark_consumed=False), "critical")
#
#     # 4. Critical reaction supersedes a previously consumed low-tier warning
#     def test_04_critical_reaction_supersedes_consumed_low_tier_warning(self) -> None:
#         """Dropping from low tier into critical tier delivers a fresh urgent critical warning."""
#         battle = Battle(self.pika, self.rattata, player=self.player)
#         battle.start()
#
#         # Step 1: drop into low tier (20%)
#         self.pika.current_hp = int(self.pika.max_hp * 0.20)
#         self.assertEqual(battle.get_pending_danger_tier(mark_consumed=True), "low")
#
#         # Low warning is now consumed
#         self.assertIsNone(battle.get_pending_danger_tier(mark_consumed=False))
#
#         # Step 2: drop into critical tier (8%)
#         self.pika.current_hp = int(self.pika.max_hp * 0.08)
#         # Escalates to critical!
#         self.assertEqual(battle.get_pending_danger_tier(mark_consumed=True), "critical")
#
#         # Critical is now consumed
#         self.assertIsNone(battle.get_pending_danger_tier(mark_consumed=False))
#
#     # 5. Repeated TALK does not repeat a consumed warning
#     def test_05_repeated_talk_does_not_repeat_consumed_warning(self) -> None:
#         """Repeated TALK calls while remaining in the same tier suppress duplicate warnings."""
#         self.pika.set_trained_stat("defense", 100)
#         rattata1 = Pokemon(species=RATTATA, personality=self.default_personality, level=1, attacks=[TACKLE])
#         rattata1.set_trained_stat("defense", 100)
#         trainer = Trainer(
#             trainer_id="youngster_joey",
#             name="Joey",
#             title="Youngster",
#             archetype=TrainerArchetype.YOUNGSTER,
#             difficulty=DifficultyProfile.NORMAL,
#             team=[rattata1],
#         )
#         manager = BattleManager(seed=42)
#         battle = manager.start_battle(self.player, trainer, seed=42)
#
#         # Set player Pokemon to 20% HP (Low danger)
#         self.pika.current_hp = int(self.pika.max_hp * 0.20)
#
#         # First TALK on turn 1: delivers low danger warning
#         res1 = manager.talk(self.player, "Hang in there Pikachu!")
#         self.assertTrue(res1.accepted)
#         self.assertIn("pain", res1.talk_dialogue.lower())
#
#         # Complete turn 1 with non-lethal move to advance turn (Rattata survives, deals minor damage)
#         res_act = battle.take_action(BattleAction(action_type=BattleActionType.ATTACK, attack=QUICK_ATTACK))
#         self.assertTrue(res_act.accepted)
#         self.assertFalse(rattata1.is_fainted)
#         self.assertEqual(battle.current_turn, 2)
#
#         # Second TALK on turn 2: low warning was already consumed and drop was under threshold, so baseline dialogue is delivered
#         res2 = manager.talk(self.player, "Hang in there Pikachu!")
#         self.assertTrue(res2.accepted)
#         self.assertNotIn("pain", res2.talk_dialogue.lower())
#         self.assertIn("bolstered by your encouragement", res2.talk_dialogue.lower())
#
#     # 6. Healing above a tier boundary and later re-entering that tier
#     def test_06_healing_above_tier_boundary_re_enables_danger_reaction(self) -> None:
#         """Healing above 25% resets danger state so later dropping below 25% triggers a new warning."""
#         battle = Battle(self.pika, self.rattata, player=self.player)
#         battle.start()
#
#         # Enter low tier and consume
#         self.pika.current_hp = int(self.pika.max_hp * 0.20)
#         self.assertEqual(battle.get_pending_danger_tier(mark_consumed=True), "low")
#         self.assertIsNone(battle.get_pending_danger_tier(mark_consumed=False))
#
#         # Heal back to 60% HP (normal tier)
#         self.pika.current_hp = int(self.pika.max_hp * 0.60)
#         # Calling get_pending_danger_tier resets the consumed tier
#         self.assertIsNone(battle.get_pending_danger_tier(mark_consumed=False))
#
#         # Drop into low tier again (18%)
#         self.pika.current_hp = int(self.pika.max_hp * 0.18)
#         # Re-entry triggers a fresh warning!
#         self.assertEqual(battle.get_pending_danger_tier(mark_consumed=True), "low")
#
#     # 7. Additional-damage retriggering threshold
#     def test_07_additional_damage_retriggering_threshold(self) -> None:
#         """Losing >= 10% max HP within low tier retriggers, while < 10% loss remains suppressed."""
#         battle = Battle(self.pika, self.rattata, player=self.player)
#         battle.start()
#
#         # Warning consumed at 25% HP
#         self.pika.current_hp = int(self.pika.max_hp * 0.25)
#         self.assertEqual(battle.get_pending_danger_tier(mark_consumed=True), "low")
#
#         # Sub-threshold drop: loss of 5% (to 20% HP) -> suppressed!
#         self.pika.current_hp = int(self.pika.max_hp * 0.20)
#         self.assertIsNone(battle.get_pending_danger_tier(mark_consumed=False))
#
#         # Sub-threshold boundary: loss of 9% (to 16% HP) -> suppressed!
#         self.pika.current_hp = int(self.pika.max_hp * 0.16)
#         self.assertIsNone(battle.get_pending_danger_tier(mark_consumed=False))
#
#         # Threshold reached: loss of >= 10% (down to 14% HP) -> retriggers!
#         self.pika.current_hp = int(self.pika.max_hp * 0.14)
#         self.assertEqual(battle.get_pending_danger_tier(mark_consumed=True), "low")
#
#     # 8. High-priority milestone does not erase an unserved danger reaction
#     def test_08_high_priority_milestone_does_not_erase_unserved_danger_reaction(self) -> None:
#         """Turn with knockout milestone delivers KO first; switch second; danger reaction third."""
#         self.pika.set_trained_stat("defense", 100)
#         self.pidgey.set_trained_stat("defense", 100)
#         manager = BattleManager(seed=42)
#         battle = manager.start_battle(self.player, self.trainer, seed=42)
#
#         # Set Rattata to 1 HP for direct lethal KO
#         self.rattata.current_hp = 1
#         # Set Pikachu to 20% HP (Low danger)
#         self.pika.current_hp = int(self.pika.max_hp * 0.20)
#
#         # Turn 1: Player knocks out Rattata
#         res_ko = battle.take_action(BattleAction(action_type=BattleActionType.ATTACK, attack=THUNDER_SHOCK))
#         self.assertTrue(self.rattata.is_fainted)
#         self.assertEqual(battle.current_turn, 2)
#
#         # Milestone, switch, and danger condition all exist
#         self.assertEqual(battle.get_latest_player_combat_milestone(mark_consumed=False), "opponent_knockout")
#         self.assertIsNotNone(battle.get_latest_opponent_switch(mark_consumed=False))
#         self.assertEqual(battle.get_pending_danger_tier(mark_consumed=False), "low")
#
#         # Turn 2 TALK: delivers highest priority (knockout milestone celebration)
#         res_talk1 = manager.talk(self.player, "Awesome finish!")
#         self.assertTrue(res_talk1.accepted)
#         self.assertIn("knockout", res_talk1.talk_dialogue.lower())
#         self.assertNotIn("pidgey", res_talk1.talk_dialogue.lower())
#
#         # Milestone is consumed; switch and danger are NOT consumed
#         self.assertIsNone(battle.get_latest_player_combat_milestone(mark_consumed=False))
#         self.assertIsNotNone(battle.get_latest_opponent_switch(mark_consumed=False))
#         self.assertEqual(battle.get_pending_danger_tier(mark_consumed=False), "low")
#
#         # Turn 2 combat action (non-lethal attack on Pidgey)
#         res_t2 = battle.take_action(BattleAction(action_type=BattleActionType.ATTACK, attack=QUICK_ATTACK))
#         self.assertTrue(res_t2.accepted)
#         self.assertEqual(battle.current_turn, 3)
#
#         # Turn 3 TALK: delivers deferred switch reaction (Priority A2 over Priority C)
#         res_talk2 = manager.talk(self.player, "What's the plan now?")
#         self.assertTrue(res_talk2.accepted)
#         self.assertIn("pidgey", res_talk2.talk_dialogue.lower())
#
#         # Switch is consumed; danger remains unconsumed (low or escalated to critical)
#         self.assertIsNone(battle.get_latest_opponent_switch(mark_consumed=False))
#         self.assertIn(battle.get_pending_danger_tier(mark_consumed=False), ("low", "critical"))
#
#         # Turn 3 combat action (non-lethal attack on Pidgey)
#         res_t3 = battle.take_action(BattleAction(action_type=BattleActionType.ATTACK, attack=QUICK_ATTACK))
#         self.assertTrue(res_t3.accepted)
#         self.assertEqual(battle.current_turn, 4)
#
#         # Turn 4 TALK: now delivers deferred danger reaction!
#         res_talk3 = manager.talk(self.player, "How are you holding up?")
#         self.assertTrue(res_talk3.accepted)
#         # Pikachu is in danger tier
#         self.assertTrue(
#             "pain" in res_talk3.talk_dialogue.lower()
#             or "fainting" in res_talk3.talk_dialogue.lower()
#             or "exhausted" in res_talk3.talk_dialogue.lower()
#             or "limit" in res_talk3.talk_dialogue.lower()
#         )
#
#         # Danger reaction is now consumed
#         self.assertIsNone(battle.get_pending_danger_tier(mark_consumed=False))
#
#     # 9. Opponent-switch and danger events do not overwrite one another
#     def test_09_opponent_switch_and_danger_events_do_not_overwrite_one_another(self) -> None:
#         """When an opponent switches and Pikachu is low HP, switch reaction takes precedence and danger reaction is deferred."""
#         manager = BattleManager(seed=42)
#         battle = manager.start_battle(self.player, self.trainer, seed=42)
#
#         # Pikachu is in low danger
#         self.pika.current_hp = int(self.pika.max_hp * 0.20)
#         # Trainer switches to Pidgey proactively
#         battle.switch_opponent_pokemon(self.pidgey)
#
#         # Both switch event and danger condition exist
#         self.assertIsNotNone(battle.get_latest_opponent_switch(mark_consumed=False))
#         self.assertEqual(battle.get_pending_danger_tier(mark_consumed=False), "low")
#
#         # Turn 1 TALK: delivers switch reaction
#         res_talk1 = manager.talk(self.player, "Look at that!")
#         self.assertTrue(res_talk1.accepted)
#         self.assertIn("pidgey", res_talk1.talk_dialogue.lower())
#
#         # Switch is consumed; danger remains unconsumed
#         self.assertIsNone(battle.get_latest_opponent_switch(mark_consumed=False))
#         self.assertEqual(battle.get_pending_danger_tier(mark_consumed=False), "low")
#
#         # Turn 1 combat action: Pikachu attacks with Quick Attack
#         res_t1 = battle.take_action(BattleAction(action_type=BattleActionType.ATTACK, attack=QUICK_ATTACK))
#         self.assertTrue(res_t1.accepted)
#         self.assertEqual(battle.current_turn, 2)
#
#         # Turn 2 TALK: delivers deferred danger reaction
#         res_talk2 = manager.talk(self.player, "Can you keep going?")
#         self.assertTrue(res_talk2.accepted)
#         self.assertTrue(
#             "pain" in res_talk2.talk_dialogue.lower()
#             or "fainting" in res_talk2.talk_dialogue.lower()
#             or "exhausted" in res_talk2.talk_dialogue.lower()
#         )
#
#     # 10. Battle-instance isolation
#     def test_10_battle_instance_isolation(self) -> None:
#         """Danger consumption in one battle does not suppress warnings in a separate battle."""
#         battle1 = Battle(self.pika, self.rattata, player=self.player)
#         battle1.start()
#         self.pika.current_hp = int(self.pika.max_hp * 0.20)
#         # Consume in battle 1
#         self.assertEqual(battle1.get_pending_danger_tier(mark_consumed=True), "low")
#         self.assertIsNone(battle1.get_pending_danger_tier(mark_consumed=False))
#
#         # Battle 2 with a different Pikachu
#         pika2 = Pokemon(species=PIKACHU, personality=self.default_personality, level=25)
#         player2 = Player(name="Red")
#         player2.add_pokemon(pika2)
#         player2.add_to_team(pika2)
#         player2.set_active_pokemon(pika2)
#         pika2.current_hp = int(pika2.max_hp * 0.20)
#
#         battle2 = Battle(pika2, self.rattata, player=player2)
#         battle2.start()
#
#         # Battle 2 is unconsumed and ready to deliver
#         self.assertEqual(battle2.get_pending_danger_tier(mark_consumed=False), "low")
#
#     # 11. Missing/invalid HP handling
#     def test_11_missing_and_invalid_hp_handling_fails_safely(self) -> None:
#         """Missing, zero, negative, or non-numeric HP values safely return None without errors."""
#         battle = Battle(self.pika, self.rattata, player=self.player)
#         battle.start()
#
#         # Context with negative hp_percent
#         ctx_neg = BattleTalkContext(hp_percent=-0.5)
#         resp_neg = generate_battle_talk_response(self.pika, "Hello", context=ctx_neg)
#         self.assertIsNotNone(resp_neg)
#
#         # Context with invalid hp_percent > 1.0
#         ctx_high = BattleTalkContext(hp_percent=1.5)
#         resp_high = generate_battle_talk_response(self.pika, "Hello", context=ctx_high)
#         self.assertIsNotNone(resp_high)
#
#         # Dict context with malformed values
#         resp_dict = generate_battle_talk_response(self.pika, "Hello", context={"hp_percent": "bad_data"})
#         self.assertIsNotNone(resp_dict)
#
#         # Mock Pokemon with zero max_hp (valid Pokemon subclass)
#         class ZeroHpPokemon(Pokemon):
#             def __init__(self, personality):
#                 super().__init__(PIKACHU, personality, level=1)
#
#             @property
#             def max_hp(self) -> int:
#                 return 0
#
#         zero_mon = ZeroHpPokemon(self.default_personality)
#         battle_zero = Battle(zero_mon, self.rattata, player=self.player)
#         self.assertIsNone(battle_zero.get_pending_danger_tier(mark_consumed=False))
#
#     # 12. Personality-aware differentiation across all 13 profiles
#     def test_12_personality_differentiation_low_vs_critical(self) -> None:
#         """All 13 personality profiles produce distinct, characterful responses for low vs critical tiers."""
#         profiles = [
#             ("high_confidence", Personality(confidence=85, fear=50, aggression=50, loyalty=50, curiosity=50, sociability=50), "still fight", "refuse to drop"),
#             ("low_confidence", Personality(confidence=15, fear=50, aggression=50, loyalty=50, curiosity=50, sociability=50), "hold on", "absolute limit"),
#             ("high_fear", Personality(confidence=50, fear=85, aggression=50, loyalty=50, curiosity=50, sociability=50), "desperate", "frantic terror"),
#             ("low_fear", Personality(confidence=50, fear=15, aggression=50, loyalty=50, curiosity=50, sociability=50), "pain won't slow", "critical threshold"),
#             ("high_aggression", Personality(confidence=50, fear=50, aggression=85, loyalty=50, curiosity=50, sociability=50), "tearing them down", "all or nothing"),
#             ("low_aggression", Personality(confidence=50, fear=50, aggression=15, loyalty=50, curiosity=50, sociability=50), "endure as long", "one last breath"),
#             ("high_loyalty", Personality(confidence=50, fear=50, aggression=50, loyalty=85, curiosity=50, sociability=50), "won't let you down", "heart stops"),
#             ("low_loyalty", Personality(confidence=50, fear=50, aggression=50, loyalty=15, curiosity=50, sociability=50), "easy for you to say", "do something already"),
#             ("high_sociability", Personality(confidence=50, fear=50, aggression=50, loyalty=50, curiosity=50, sociability=85), "spirits high", "won't give up on us"),
#             ("low_sociability", Personality(confidence=50, fear=50, aggression=50, loyalty=50, curiosity=50, sociability=15), "without speaking", "stoic silence"),
#             ("high_curiosity", Personality(confidence=50, fear=50, aggression=50, loyalty=50, curiosity=85, sociability=50), "see their rhythm", "final gambit"),
#             ("low_curiosity", Personality(confidence=50, fear=50, aggression=50, loyalty=50, curiosity=15, sociability=50), "no distractions", "final strike"),
#             ("balanced", Personality(50, 50, 50, 50, 50, 50), "bolstered by your encouragement", "barely holding on"),
#         ]
#
#         for prof_name, personality, low_keyword, crit_keyword in profiles:
#             p = Pokemon(species=PIKACHU, personality=personality, level=20)
#             cmd = BattleTalkCommand(text="Hang in there!", intent=BattleTalkIntent.ENCOURAGE)
#
#             resp_low = generate_battle_talk_response(p, cmd, context=BattleTalkContext(hp_percent=0.20))
#             resp_crit = generate_battle_talk_response(p, cmd, context=BattleTalkContext(hp_percent=0.08))
#
#             self.assertIn(low_keyword.lower(), resp_low.lower(), f"{prof_name} failed low HP keyword match")
#             self.assertIn(crit_keyword.lower(), resp_crit.lower(), f"{prof_name} failed critical HP keyword match")
#             self.assertNotEqual(resp_low, resp_crit, f"{prof_name} low and critical responses must be distinct")
#
#     # 13. Invariants preserved: no mutation of Pokemon combat stats, turn economy, or RNG
#     def test_13_combat_invariants_preserved(self) -> None:
#         """Danger dialogue checks do not mutate Pokemon stats, HP, turn count, or obedience."""
#         init_hp = self.pika.current_hp
#         init_max = self.pika.max_hp
#         init_atk = self.pika.attack
#         init_def = self.pika.defense
#         init_spd = self.pika.speed
#         init_obd = self.pika.obedience
#         init_bnd = self.pika.bond
#
#         manager = BattleManager(seed=42)
#         battle = manager.start_battle(self.player, self.trainer, seed=42)
#
#         res = manager.talk(self.player, "Good luck!")
#         self.assertTrue(res.accepted)
#
#         self.assertEqual(self.pika.current_hp, init_hp)
#         self.assertEqual(self.pika.max_hp, init_max)
#         self.assertEqual(self.pika.attack, init_atk)
#         self.assertEqual(self.pika.defense, init_def)
#         self.assertEqual(self.pika.speed, init_spd)
#         self.assertEqual(self.pika.obedience, init_obd)
#         self.assertEqual(self.pika.bond, init_bnd)
#         # Turn economy: talk does not consume combat turn
#         self.assertEqual(battle.current_turn, 1)
#
#
# if __name__ == "__main__":
#     unittest.main()
