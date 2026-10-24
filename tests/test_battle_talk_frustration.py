# """
# Unit tests for BT5.5D: Combat Frustration Reactions.
#
# Tests the following specifications:
# 1. Single player miss does not trigger reaction.
# 2. Two qualifying player misses trigger repeated misses reaction.
# 3. Successful player attack resets miss streak.
# 4. Opponent misses do not count toward player streak.
# 5. Paralysis and non-attack events do not count as misses.
# 6. Repeated TALK calls suppress duplicate frustration warnings.
# 7. Type immunity triggers with recorded zero effectiveness and damage.
# 8. Unrelated zero-damage events do not trigger immunity.
# 9. Distinct later immunity triggers a new reaction.
# 10. Resistance requires effectiveness in (0, 1) and positive damage.
# 11. Neutral and super-effective attacks do not trigger resistance.
# 12. Higher-priority milestone does not erase unserved frustration.
# 13. Frustration reactions do not overwrite pending switch or danger reactions.
# 14. Isolation between distinct battle instances.
# 15. Personality fallback and profile coverage across all 13 profiles.
# 16. Compatibility with existing Battle Talk context and priority stack.
# 17. Combat state integrity (HP, stats, obedience, turns unmutated).
# """
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
# from src.models.attack import Attack
# from src.models.pokemon_type import PokemonType
# from src.models.status_effect import StatusEffectType
# from src.ai.companion_service import (
#     CompanionService,
#     BattleTalkContext,
#     generate_battle_talk_response,
#     _CONTEXT_EVENT_TEMPLATES,
# )
# from src.data.species import PIKACHU, PIDGEY, RATTATA, GASTLY, BULBASAUR, GEODUDE
# from src.data.attacks import THUNDER_SHOCK, QUICK_ATTACK, TACKLE
#
#
# class TestBattleTalkFrustration(unittest.TestCase):
#     """Test suite verifying combat frustration reactions, miss streaks, immunity, and resistance."""
#
#     def setUp(self) -> None:
#         self.default_personality = Personality(50, 50, 50, 50, 50, 50)
#
#         # Attacks for controlled testing
#         self.miss_attack = Attack(
#             name="Inaccurate Strike",
#             type=PokemonType.NORMAL,
#             power=20,
#             accuracy=0,  # Always misses
#         )
#         self.hit_attack = Attack(
#             name="Accurate Strike",
#             type=PokemonType.NORMAL,
#             power=10,
#             accuracy=100,  # Always hits
#         )
#
#         self.pika = Pokemon(
#             species=PIKACHU,
#             personality=self.default_personality,
#             level=25,
#             attacks=[self.miss_attack, self.hit_attack, THUNDER_SHOCK, QUICK_ATTACK],
#         )
#         self.pika.set_trained_stat("defense", 100)
#
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
#         self.rattata.set_trained_stat("defense", 100)
#
#         self.pidgey = Pokemon(
#             species=PIDGEY,
#             personality=self.default_personality,
#             level=5,
#             attacks=[TACKLE],
#         )
#         self.pidgey.set_trained_stat("defense", 100)
#
#         self.trainer = Trainer(
#             trainer_id="youngster_joey",
#             name="Joey",
#             title="Youngster",
#             archetype=TrainerArchetype.YOUNGSTER,
#             difficulty=DifficultyProfile.NORMAL,
#             team=[self.rattata, self.pidgey],
#         )
#
#     # 1. Single player miss does not trigger reaction
#     def test_01_single_player_miss_does_not_trigger_reaction(self) -> None:
#         """A single player miss does not reach the >= 2 streak threshold."""
#         battle = Battle(self.pika, self.rattata, player=self.player)
#         battle.start()
#
#         # Turn 1: Player uses a move with 0 accuracy (guaranteed miss)
#         res = battle.take_action(BattleAction(action_type=BattleActionType.ATTACK, attack=self.miss_attack))
#         self.assertTrue(res.accepted)
#         self.assertEqual(battle._player_consecutive_misses, 1)
#         self.assertIsNone(battle.get_latest_frustration_event())
#
#         # Talk action returns baseline personality dialogue, not frustration
#         talk_res = battle.talk("Keep focused!")
#         self.assertTrue(talk_res.accepted)
#         dialogue = talk_res.talk_command.dialogue.lower()
#         self.assertNotIn("missed again", dialogue)
#         self.assertNotIn("frustration", dialogue)
#         self.assertIn("ready for battle", dialogue)
#
#     # 2. Two qualifying player misses trigger repeated misses reaction
#     def test_02_two_qualifying_player_misses_trigger_repeated_misses_reaction(self) -> None:
#         """Two consecutive qualifying player misses trigger the repeated_misses reaction."""
#         battle = Battle(self.pika, self.rattata, player=self.player)
#         battle.start()
#
#         # Turn 1: Miss
#         battle.take_action(BattleAction(action_type=BattleActionType.ATTACK, attack=self.miss_attack))
#         self.assertEqual(battle._player_consecutive_misses, 1)
#
#         # Turn 2: Miss again
#         battle.take_action(BattleAction(action_type=BattleActionType.ATTACK, attack=self.miss_attack))
#         self.assertEqual(battle._player_consecutive_misses, 2)
#         self.assertEqual(battle.get_latest_frustration_event(), "repeated_misses")
#
#         # Talk action yields repeated_misses dialogue
#         talk_res = battle.talk("Don't worry!")
#         self.assertTrue(talk_res.accepted)
#         dialogue = talk_res.talk_command.dialogue.lower()
#         self.assertIn("frowns with frustration after missing again", dialogue)
#
#     # 3. Successful player attack resets miss streak
#     def test_03_successful_player_attack_resets_miss_streak(self) -> None:
#         """A successful hit resets the miss streak to 0."""
#         battle = Battle(self.pika, self.rattata, player=self.player)
#         battle.start()
#
#         # Turn 1: Miss
#         battle.take_action(BattleAction(action_type=BattleActionType.ATTACK, attack=self.miss_attack))
#         self.assertEqual(battle._player_consecutive_misses, 1)
#
#         # Turn 2: Hit
#         battle.take_action(BattleAction(action_type=BattleActionType.ATTACK, attack=self.hit_attack))
#         self.assertEqual(battle._player_consecutive_misses, 0)
#
#         # Turn 3: Miss
#         battle.take_action(BattleAction(action_type=BattleActionType.ATTACK, attack=self.miss_attack))
#         self.assertEqual(battle._player_consecutive_misses, 1)
#         self.assertIsNone(battle.get_latest_frustration_event())
#
#     # 4. Opponent misses do not count toward player streak
#     def test_04_opponent_misses_do_not_count_toward_player_streak(self) -> None:
#         """Opponent attack misses do not increment the player's miss counter."""
#         miss_rattata = Pokemon(
#             species=RATTATA,
#             personality=self.default_personality,
#             level=5,
#             attacks=[self.miss_attack],
#         )
#         miss_rattata.set_trained_stat("defense", 100)
#         battle = Battle(self.pika, miss_rattata, player=self.player)
#         battle.start()
#
#         # Turn 1: Player hits, opponent misses
#         battle.take_action(BattleAction(action_type=BattleActionType.ATTACK, attack=self.hit_attack))
#         self.assertEqual(battle._player_consecutive_misses, 0)
#         self.assertIsNone(battle.get_latest_frustration_event())
#
#     # 5. Paralysis and non-attack events do not count as misses
#     def test_05_paralysis_and_non_attack_events_do_not_count_as_misses(self) -> None:
#         """Paralysis failure does not increment consecutive miss streak."""
#         battle = Battle(self.pika, self.rattata, player=self.player)
#         battle.start()
#
#         # Turn 1: Miss
#         battle.take_action(BattleAction(action_type=BattleActionType.ATTACK, attack=self.miss_attack))
#         self.assertEqual(battle._player_consecutive_misses, 1)
#
#         # Apply paralysis to Pikachu
#         self.pika.add_status_effect(StatusEffectType.PARALYSIS)
#
#         # Mock status manager check to simulate paralysis blocking turn
#         from src.models.status_effect_manager import ActionCheckResult
#         orig_check = battle._status_manager.check_can_act
#         battle._status_manager.check_can_act = lambda mon, **kwargs: ActionCheckResult(
#             can_act=False, pokemon=mon, paralyzed=True, roll=10, chance=25, reason="paralyzed"
#         )
#
#         # Turn 2: Paralysis prevents acting
#         battle.take_action(BattleAction(action_type=BattleActionType.ATTACK, attack=self.miss_attack))
#         battle._status_manager.check_can_act = orig_check
#
#         # Consecutive miss streak should remain 1, not 2
#         self.assertEqual(battle._player_consecutive_misses, 1)
#         self.assertIsNone(battle.get_latest_frustration_event())
#
#     # 6. Repeated TALK calls suppress duplicate frustration warnings
#     def test_06_repeated_talk_suppresses_duplicate_frustration_warnings(self) -> None:
#         """Subsequent TALK calls in the same turn suppress duplicate frustration dialogue."""
#         battle = Battle(self.pika, self.rattata, player=self.player)
#         battle.start()
#
#         # Cause 2 misses
#         battle.take_action(BattleAction(action_type=BattleActionType.ATTACK, attack=self.miss_attack))
#         battle.take_action(BattleAction(action_type=BattleActionType.ATTACK, attack=self.miss_attack))
#         self.assertEqual(battle.get_latest_frustration_event(), "repeated_misses")
#
#         # First talk: consumes frustration
#         res1 = battle.talk("Focus up!")
#         self.assertIn("frowns with frustration after missing again", res1.talk_command.dialogue.lower())
#         self.assertIsNone(battle.get_latest_frustration_event())
#
#         # Second talk in same turn: returns duplicate-suppressed baseline
#         # Reset turn allowance for unit test of dialogue output
#         battle._last_talk_turn = None
#         res2 = battle.talk("You can do it!")
#         self.assertNotIn("missing again", res2.talk_command.dialogue.lower())
#         self.assertIn("bolstered by your encouragement", res2.talk_command.dialogue.lower())
#
#     # 7. Type immunity triggers with recorded zero effectiveness and damage
#     def test_07_type_immunity_triggers_with_recorded_zero_effectiveness_and_damage(self) -> None:
#         """Normal attack vs Ghost type triggers attack_immune reaction."""
#         gastly = Pokemon(
#             species=GASTLY,
#             personality=self.default_personality,
#             level=10,
#             attacks=[TACKLE],
#         )
#         gastly.set_trained_stat("defense", 100)
#         battle = Battle(self.pika, gastly, player=self.player)
#         battle.start()
#
#         # Normal attack vs Ghost (effectiveness 0.0, damage 0)
#         res = battle.take_action(BattleAction(action_type=BattleActionType.ATTACK, attack=self.hit_attack))
#         self.assertTrue(res.accepted)
#         self.assertEqual(battle.get_latest_frustration_event(), "attack_immune")
#
#         # Talk action returns attack_immune dialogue
#         talk_res = battle.talk("What happened?")
#         self.assertTrue(talk_res.accepted)
#         self.assertIn("no effect on the opponent", talk_res.talk_command.dialogue.lower())
#
#     # 8. Unrelated zero-damage events do not trigger immunity
#     def test_08_unrelated_zero_damage_events_do_not_trigger_immunity(self) -> None:
#         """Accuracy miss with damage=0 does not trigger attack_immune."""
#         battle = Battle(self.pika, self.rattata, player=self.player)
#         battle.start()
#
#         # Miss attack
#         battle.take_action(BattleAction(action_type=BattleActionType.ATTACK, attack=self.miss_attack))
#         # Miss is not immunity
#         self.assertNotEqual(battle.get_latest_frustration_event(), "attack_immune")
#         self.assertIsNone(battle.get_latest_frustration_event())
#
#     # 9. Distinct later immunity triggers a new reaction
#     def test_09_distinct_later_immunity_triggers_new_reaction(self) -> None:
#         """A new immunity event on a subsequent turn triggers a fresh reaction."""
#         gastly = Pokemon(
#             species=GASTLY,
#             personality=self.default_personality,
#             level=10,
#             attacks=[TACKLE],
#         )
#         gastly.set_trained_stat("defense", 100)
#         battle = Battle(self.pika, gastly, player=self.player)
#         battle.start()
#
#         # Turn 1: Immunity
#         battle.take_action(BattleAction(action_type=BattleActionType.ATTACK, attack=self.hit_attack))
#         self.assertEqual(battle.get_latest_frustration_event(mark_consumed=True), "attack_immune")
#         self.assertIsNone(battle.get_latest_frustration_event())
#
#         # Turn 2: Another Normal attack vs Ghost
#         battle.take_action(BattleAction(action_type=BattleActionType.ATTACK, attack=self.hit_attack))
#         self.assertEqual(battle.get_latest_frustration_event(), "attack_immune")
#
#     # 10. Resistance requires effectiveness in (0, 1) and positive damage
#     def test_10_resistance_requires_effectiveness_in_range_and_positive_damage(self) -> None:
#         """Electric attack vs Bulbasaur (Grass, 0.5x eff, >0 dmg) triggers attack_resisted."""
#         bulba = Pokemon(
#             species=BULBASAUR,
#             personality=self.default_personality,
#             level=10,
#             attacks=[TACKLE],
#         )
#         bulba.set_trained_stat("defense", 100)
#         battle = Battle(self.pika, bulba, player=self.player, seed=123)
#         battle.start()
#
#         # Thunder Shock vs Bulbasaur (Grass resists Electric)
#         res = battle.take_action(BattleAction(action_type=BattleActionType.ATTACK, attack=THUNDER_SHOCK))
#         self.assertTrue(res.accepted)
#         self.assertEqual(battle.get_latest_frustration_event(), "attack_resisted")
#
#         # Talk action returns attack_resisted dialogue
#         talk_res = battle.talk("Keep pressing!")
#         self.assertTrue(talk_res.accepted)
#         self.assertIn("attack is resisted, dealing minimal damage", talk_res.talk_command.dialogue.lower())
#
#     # 11. Neutral and super-effective attacks do not trigger resistance
#     def test_11_neutral_and_super_effective_attacks_do_not_trigger_resistance(self) -> None:
#         """Neutral (1.0x) and super-effective (2.0x) attacks do not trigger resistance."""
#         battle = Battle(self.pika, self.rattata, player=self.player)
#         battle.start()
#
#         # Neutral attack: Quick Attack vs Rattata (1.0x)
#         battle.take_action(BattleAction(action_type=BattleActionType.ATTACK, attack=QUICK_ATTACK))
#         self.assertNotEqual(battle.get_latest_frustration_event(), "attack_resisted")
#
#         # Super-effective attack: Thunder Shock vs Pidgey (2.0x)
#         battle2 = Battle(self.pika, self.pidgey, player=self.player)
#         battle2.start()
#         battle2.take_action(BattleAction(action_type=BattleActionType.ATTACK, attack=THUNDER_SHOCK))
#         self.assertNotEqual(battle2.get_latest_frustration_event(), "attack_resisted")
#
#     # 12. Higher-priority milestone does not erase unserved frustration
#     def test_12_higher_priority_milestone_does_not_erase_unserved_frustration(self) -> None:
#         """A combat milestone takes precedence in delivery without destroying pending frustration."""
#         battle = Battle(self.pika, self.pidgey, player=self.player)
#         battle.start()
#
#         # Turn 1 & 2: Miss twice -> repeated_misses frustration pending
#         battle.take_action(BattleAction(action_type=BattleActionType.ATTACK, attack=self.miss_attack))
#         battle.take_action(BattleAction(action_type=BattleActionType.ATTACK, attack=self.miss_attack))
#         self.assertEqual(battle._pending_frustration_event, "repeated_misses")
#
#         # Turn 3: Super-effective hit (milestone)
#         battle.take_action(BattleAction(action_type=BattleActionType.ATTACK, attack=THUNDER_SHOCK))
#         self.assertEqual(battle.get_latest_player_combat_milestone(), "super_effective")
#
#         # Talk on Turn 3: Milestone is served first
#         talk_res = battle.talk("Great shot!")
#         self.assertIn("super-effective strike", talk_res.talk_command.dialogue.lower())
#
#         # Frustration event was NOT erased
#         self.assertEqual(battle._pending_frustration_event, "repeated_misses")
#
#     # 13. Frustration reactions do not overwrite pending switch or danger reactions
#     def test_13_frustration_reactions_do_not_overwrite_switch_or_danger_reactions(self) -> None:
#         """Danger tier and opponent switch reactions take priority over frustration."""
#         # Danger tier priority
#         battle = Battle(self.pika, self.rattata, player=self.player)
#         battle.start()
#
#         # Turn 1 & 2: Miss twice
#         battle.take_action(BattleAction(action_type=BattleActionType.ATTACK, attack=self.miss_attack))
#         battle.take_action(BattleAction(action_type=BattleActionType.ATTACK, attack=self.miss_attack))
#
#         # Put Pikachu into critical danger (<= 10% HP)
#         self.pika.current_hp = int(self.pika.max_hp * 0.08)
#
#         # Talk action should prioritize danger tier over frustration
#         talk_res = battle.talk("Hold on!")
#         dialogue = talk_res.talk_command.dialogue.lower()
#         self.assertIn("dangerously close to fainting", dialogue)
#         self.assertNotIn("missing again", dialogue)
#
#         # Frustration event is still unconsumed!
#         self.assertIsNotNone(battle._pending_frustration_event)
#
#     # 14. Isolation between distinct battle instances
#     def test_14_battle_instance_isolation(self) -> None:
#         """Two separate Battle instances maintain independent frustration tracking."""
#         battle_a = Battle(self.pika, self.rattata, player=self.player)
#         battle_b = Battle(self.pika, self.pidgey, player=self.player)
#         battle_a.start()
#         battle_b.start()
#
#         # Battle A misses twice
#         battle_a.take_action(BattleAction(action_type=BattleActionType.ATTACK, attack=self.miss_attack))
#         battle_a.take_action(BattleAction(action_type=BattleActionType.ATTACK, attack=self.miss_attack))
#
#         # Battle B hits once
#         battle_b.take_action(BattleAction(action_type=BattleActionType.ATTACK, attack=self.hit_attack))
#
#         self.assertEqual(battle_a.get_latest_frustration_event(), "repeated_misses")
#         self.assertIsNone(battle_b.get_latest_frustration_event())
#
#     # 15. Personality fallback and profile coverage across all 13 profiles
#     def test_15_personality_fallback_and_profile_coverage(self) -> None:
#         """Every personality profile has distinct templates for repeated_misses, attack_immune, attack_resisted."""
#         profiles = [
#             "high_confidence", "low_confidence", "high_fear", "low_fear",
#             "high_aggression", "low_aggression", "high_loyalty", "low_loyalty",
#             "high_sociability", "low_sociability", "high_curiosity", "low_curiosity",
#             "balanced",
#         ]
#         events = ["repeated_misses", "attack_immune", "attack_resisted"]
#
#         for profile in profiles:
#             self.assertIn(profile, _CONTEXT_EVENT_TEMPLATES)
#             for ev in events:
#                 self.assertIn(ev, _CONTEXT_EVENT_TEMPLATES[profile], f"Missing {ev} in profile {profile}")
#                 tmpl = _CONTEXT_EVENT_TEMPLATES[profile][ev]
#                 self.assertTrue(len(tmpl) > 10)
#
#         # Check fallback to balanced when unknown trait is evaluated
#         ctx = BattleTalkContext(last_event="repeated_misses")
#         dummy_mon = Pokemon(species=PIKACHU, personality=Personality(50, 50, 50, 50, 50, 50))
#         resp = generate_battle_talk_response(dummy_mon, "Hang in there!", context=ctx)
#         self.assertIn("frowns with frustration after missing again", resp)
#
#     # 16. Compatibility with existing Battle Talk context and priority stack
#     def test_16_compatibility_with_existing_battle_talk_context(self) -> None:
#         """Status condition and negated tactical commands override frustration flags in context."""
#         ctx_misses = BattleTalkContext(is_repeated_misses=True)
#         resp1 = generate_battle_talk_response(self.pika, "Keep trying!", context=ctx_misses)
#         self.assertIn("frowns with frustration", resp1)
#
#         # Status condition overrides frustration
#         ctx_paralysis = BattleTalkContext(is_repeated_misses=True, status_condition="paralyzed")
#         resp2 = generate_battle_talk_response(self.pika, "Keep trying!", context=ctx_paralysis)
#         self.assertIn("paralysis", resp2.lower())
#         self.assertNotIn("frustration", resp2.lower())
#
#         # Negated tactical command overrides frustration
#         cmd = BattleTalkCommand(text="Don't dodge", metadata={"negated_tactical": True})
#         resp3 = generate_battle_talk_response(self.pika, cmd, context=ctx_misses)
#         self.assertIn("holding its ground firmly", resp3.lower())
#
#     # 17. Combat state integrity (HP, stats, obedience, turns unmutated)
#     def test_17_combat_state_integrity(self) -> None:
#         """Battle Talk queries do not alter combat stats, HP, or turn advancement."""
#         battle = Battle(self.pika, self.rattata, player=self.player)
#         battle.start()
#
#         # Two misses
#         battle.take_action(BattleAction(action_type=BattleActionType.ATTACK, attack=self.miss_attack))
#         battle.take_action(BattleAction(action_type=BattleActionType.ATTACK, attack=self.miss_attack))
#
#         turn_before = battle.current_turn
#         pika_hp_before = self.pika.current_hp
#         rattata_hp_before = self.rattata.current_hp
#
#         # Execute TALK
#         res = battle.talk("Stay sharp!")
#         self.assertTrue(res.accepted)
#
#         # Verify no combat mutations occurred
#         self.assertEqual(battle.current_turn, turn_before)
#         self.assertEqual(self.pika.current_hp, pika_hp_before)
#         self.assertEqual(self.rattata.current_hp, rattata_hp_before)
#
#
# if __name__ == "__main__":
#     unittest.main()
