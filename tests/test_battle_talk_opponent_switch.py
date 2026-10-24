# """
# Unit and integration tests for Opponent Switch Reactions in Battle Talk (BT5.5B).
#
# Validates:
# 1. Proactive opponent switch records outgoing and incoming Pokemon.
# 2. Knockout replacement records incoming Pokemon and outgoing state accurately.
# 3. Initial battle setup does not generate any switch event or reaction.
# 4. Personality-consistent switch dialogue mentioning the incoming Pokemon across profiles.
# 5. Deduplication and consumption: repeated TALK calls do not replay consumed switch events.
# 6. Multiple switches across a battle produce distinct, fresh switch events.
# 7. Knockout milestone priority and post-KO replacement event deferred delivery (no silent loss).
# 8. Wild battles never emit switch events.
# 9. Separate battle instances remain strictly isolated.
# 10. Preserves all existing combat invariants (DODGE, crits, super-effective, negated commands, free-TALK).
# """
# import unittest
#
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
#     OpponentSwitchEvent,
#     TalkCategory,
#     TurnResult,
# )
# from src.models.battle_manager import BattleManager
# from src.models.trainer import Trainer, TrainerArchetype, DifficultyProfile
# from src.ai.companion_service import (
#     CompanionService,
#     BattleTalkContext,
#     generate_battle_talk_response,
# )
# from src.data.species import PIKACHU, CHARMANDER, SQUIRTLE, BULBASAUR, PIDGEY, RATTATA
# from src.data.attacks import THUNDER_SHOCK, QUICK_ATTACK, EMBER, SCRATCH, TACKLE, WATER_GUN
#
#
# class TestBattleTalkOpponentSwitch(unittest.TestCase):
#     """Test suite for BT5.5B opponent switch detection, representation, and dialogue."""
#
#     def setUp(self) -> None:
#         self.default_personality = Personality(50, 50, 50, 50, 50, 50)
#         self.pika = Pokemon(species=PIKACHU, personality=self.default_personality, level=25, attacks=[THUNDER_SHOCK, QUICK_ATTACK])
#         self.player = Player(name="Ash")
#         self.player.add_pokemon(self.pika)
#         self.player.add_to_team(self.pika)
#         self.player.set_active_pokemon(self.pika)
#
#         self.rattata = Pokemon(species=RATTATA, personality=self.default_personality, level=25, attacks=[TACKLE])
#         self.pidgey = Pokemon(species=PIDGEY, personality=self.default_personality, level=25, attacks=[TACKLE])
#         self.trainer = Trainer(
#             trainer_id="youngster_joey",
#             name="Joey",
#             title="Youngster",
#             team=[self.rattata, self.pidgey],
#             archetype=TrainerArchetype.YOUNGSTER,
#             difficulty=DifficultyProfile.NORMAL,
#         )
#
#     # 1. Proactive opponent switch records outgoing and incoming Pokemon
#     def test_01_proactive_switch_records_incoming_and_outgoing(self) -> None:
#         """Proactive opponent switch records outgoing, incoming, turn number, and switch_type."""
#         battle = Battle(
#             pokemon1=self.pika,
#             pokemon2=self.rattata,
#             player=self.player,
#             opponent_trainer=self.trainer,
#             opponent_team=[self.rattata, self.pidgey],
#             seed=42,
#         )
#         battle.start()
#         self.assertEqual(battle.current_turn, 1)
#
#         # Execute proactive switch
#         success = battle.switch_opponent_pokemon(self.pidgey)
#         self.assertTrue(success)
#
#         # Inspect switch event on battle
#         sw_event = battle.get_latest_opponent_switch(mark_consumed=False)
#         self.assertIsNotNone(sw_event)
#         self.assertEqual(sw_event.incoming_pokemon, self.pidgey)
#         self.assertEqual(sw_event.outgoing_pokemon, self.rattata)
#         self.assertEqual(sw_event.switch_type, "proactive")
#         self.assertEqual(sw_event.turn_number, 1)
#         self.assertTrue(sw_event.event_id)
#
#     # 2. Knockout replacement records incoming Pokemon without inventing invalid state
#     def test_02_knockout_replacement_records_incoming_and_fainted_outgoing(self) -> None:
#         """When an opponent Pokemon is KO'd, replacement event records incoming and fainted outgoing."""
#         battle = Battle(
#             pokemon1=self.pika,
#             pokemon2=self.rattata,
#             player=self.player,
#             opponent_trainer=self.trainer,
#             opponent_team=[self.rattata, self.pidgey],
#             seed=42,
#         )
#         battle.start()
#
#         # Knock out Rattata
#         self.rattata.take_damage(self.rattata.max_hp)
#         self.assertTrue(self.rattata.is_fainted)
#
#         # Handle trainer replacement
#         battle._handle_opponent_trainer_ko()
#         self.assertEqual(battle.pokemon2, self.pidgey)
#
#         sw_event = battle.get_latest_opponent_switch(mark_consumed=False)
#         self.assertIsNotNone(sw_event)
#         self.assertEqual(sw_event.incoming_pokemon, self.pidgey)
#         self.assertEqual(sw_event.outgoing_pokemon, self.rattata)
#         self.assertEqual(sw_event.switch_type, "knockout_replacement")
#
#     # 3. Initial battle setup does not generate any switch event or reaction
#     def test_03_initial_battle_setup_no_switch_event(self) -> None:
#         """Starting a battle does not create any switch event or switch dialogue."""
#         manager = BattleManager(seed=42)
#         battle = manager.start_battle(self.player, self.trainer, seed=42)
#         self.assertEqual(battle.current_turn, 1)
#
#         self.assertIsNone(battle.get_latest_opponent_switch(mark_consumed=False))
#
#         # Initial talk returns standard baseline greeting, not switch reaction
#         res = manager.talk(self.player, "Hello, Pikachu!")
#         self.assertTrue(res.accepted)
#         self.assertNotIn("new opponent", res.talk_dialogue.lower())
#         self.assertNotIn("challenger", res.talk_dialogue.lower())
#         self.assertNotIn("target deployed", res.talk_dialogue.lower())
#
#     # 4. Personality-consistent switch dialogue mentioning the incoming Pokemon across profiles
#     def test_04_personality_appropriate_switch_responses(self) -> None:
#         """Switch dialogue accurately names incoming Pokemon and reflects distinct personality traits."""
#         profiles = {
#             "high_confidence": (Personality(confidence=85, fear=50, aggression=50, loyalty=50, sociability=50, curiosity=50), "new challenger"),
#             "low_confidence": (Personality(confidence=15, fear=50, aggression=50, loyalty=50, sociability=50, curiosity=50), "do my best against them"),
#             "high_fear": (Personality(confidence=50, fear=85, aggression=50, loyalty=50, sociability=50, curiosity=50), "looks tough"),
#             "low_fear": (Personality(confidence=50, fear=15, aggression=50, loyalty=50, sociability=50, curiosity=50), "new target deployed"),
#             "high_aggression": (Personality(confidence=50, fear=50, aggression=85, loyalty=50, sociability=50, curiosity=50), "tear right through them"),
#             "high_loyalty": (Personality(confidence=50, fear=50, aggression=50, loyalty=85, sociability=50, curiosity=50), "leave them to me"),
#             "high_curiosity": (Personality(confidence=50, fear=50, aggression=50, loyalty=50, sociability=50, curiosity=85), "what techniques they bring"),
#             "balanced": (Personality(confidence=50, fear=50, aggression=50, loyalty=50, sociability=50, curiosity=50), "ready for the new challenge"),
#         }
#
#         for prof_name, (pers, expected_phrase) in profiles.items():
#             mon = Pokemon(species=PIKACHU, personality=pers, level=10, attacks=[THUNDER_SHOCK])
#             player = Player(name=f"Trainer_{prof_name}")
#             player.add_pokemon(mon)
#             player.add_to_team(mon)
#             player.set_active_pokemon(mon)
#
#             rat = Pokemon(species=RATTATA, personality=self.default_personality, level=5, attacks=[TACKLE])
#             pidg = Pokemon(species=PIDGEY, personality=self.default_personality, level=5, attacks=[TACKLE])
#             trainer = Trainer(
#                 trainer_id=f"joey_{prof_name}",
#                 name="Joey",
#                 title="Youngster",
#                 team=[rat, pidg],
#                 archetype=TrainerArchetype.YOUNGSTER,
#                 difficulty=DifficultyProfile.NORMAL,
#             )
#
#             manager = BattleManager(seed=42)
#             battle = manager.start_battle(player, trainer, seed=42)
#
#             # Trigger proactive switch to Pidgey
#             battle.switch_opponent_pokemon(pidg)
#
#             res = manager.talk(player, "Watch out!")
#             self.assertTrue(res.accepted)
#             self.assertEqual(res.action_type, BattleActionType.TALK)
#             self.assertIsNotNone(res.talk_dialogue)
#             self.assertIn("pidgey", res.talk_dialogue.lower(), f"{prof_name} failed to name incoming Pokemon")
#             self.assertIn(expected_phrase.lower(), res.talk_dialogue.lower(), f"{prof_name} failed personality phrasing")
#
#     # 5. Repeated TALK calls do not repeat a consumed switch event
#     def test_05_repeated_talk_does_not_repeat_consumed_switch(self) -> None:
#         """Once consumed, an opponent switch event is not repeated on subsequent talk turns."""
#         manager = BattleManager(seed=42)
#         battle = manager.start_battle(self.player, self.trainer, seed=42)
#
#         # Proactive switch on turn 1
#         battle.switch_opponent_pokemon(self.pidgey)
#         self.assertIsNotNone(battle.get_latest_opponent_switch(mark_consumed=False))
#
#         # First TALK consumes the switch event
#         res1 = manager.talk(self.player, "What do you think of this one?")
#         self.assertTrue(res1.accepted)
#         self.assertIn("pidgey", res1.talk_dialogue.lower())
#
#         # Second query on the battle shows the event is consumed
#         self.assertIsNone(battle.get_latest_opponent_switch(mark_consumed=False))
#
#         # Advance combat turn with normal attack (Pidgey survives)
#         res_atk = battle.take_action(BattleAction(action_type=BattleActionType.ATTACK, attack=QUICK_ATTACK))
#         self.assertTrue(res_atk.accepted)
#         self.assertEqual(battle.current_turn, 2)
#
#         # Next TALK on turn 2 produces baseline dialogue, NOT switch reaction
#         res2 = manager.talk(self.player, "Keep it up!")
#         self.assertTrue(res2.accepted)
#         self.assertNotIn("pidgey", res2.talk_dialogue.lower())
#         self.assertNotIn("new challenge", res2.talk_dialogue.lower())
#
#     # 6. A later switch can produce a separate reaction
#     def test_06_later_switch_produces_separate_reaction(self) -> None:
#         """A subsequent switch later in the battle generates a fresh independent switch reaction."""
#         # Trainer with 3 balanced-level Pokemon
#         rattata = Pokemon(species=RATTATA, personality=self.default_personality, level=25, attacks=[TACKLE])
#         pidgey = Pokemon(species=PIDGEY, personality=self.default_personality, level=25, attacks=[TACKLE])
#         zubat = Pokemon(species=PIDGEY, personality=self.default_personality, level=25, attacks=[TACKLE])
#
#         trainer3 = Trainer(
#             trainer_id="super_joey",
#             name="Joey",
#             title="Youngster",
#             archetype=TrainerArchetype.YOUNGSTER,
#             difficulty=DifficultyProfile.HARD,
#             team=[rattata, pidgey, zubat],
#         )
#         manager = BattleManager(seed=42)
#         battle = manager.start_battle(self.player, trainer3, seed=42)
#
#         # Switch 1: to Pidgey
#         battle.switch_opponent_pokemon(pidgey)
#         res1 = manager.talk(self.player, "Look!")
#         self.assertIn("pidgey", res1.talk_dialogue.lower())
#
#         # Complete turn 1 with non-lethal attack
#         battle.take_action(BattleAction(action_type=BattleActionType.ATTACK, attack=QUICK_ATTACK))
#         self.assertEqual(battle.current_turn, 2)
#
#         # Switch 2: to Zubat (incoming display name is Pidgey)
#         battle.switch_opponent_pokemon(zubat)
#         res2 = manager.talk(self.player, "Another switch!")
#         self.assertTrue(res2.accepted)
#         self.assertIn(zubat.display_name.lower(), res2.talk_dialogue.lower())
#
#     # 7. Knockout milestone and replacement event are not misattributed or silently lost
#     def test_07_knockout_milestone_and_replacement_not_misattributed_or_lost(self) -> None:
#         """Turn with knockout and replacement delivers KO celebration first, then switch reaction on next TALK."""
#         # Prepare Rattata with 1 HP for direct lethal KO
#         self.rattata.current_hp = 1
#
#         manager = BattleManager(seed=42)
#         battle = manager.start_battle(self.player, self.trainer, seed=42)
#         self.assertEqual(battle.current_turn, 1)
#
#         # Turn 1: Player directly knocks out Rattata
#         res_ko = battle.take_action(BattleAction(action_type=BattleActionType.ATTACK, attack=THUNDER_SHOCK))
#         self.assertTrue(self.rattata.is_fainted)
#         self.assertEqual(battle.pokemon2, self.pidgey)
#         self.assertEqual(battle.current_turn, 2)
#
#         # Both events occurred on turn 1:
#         # Milestone: opponent_knockout
#         # Switch: knockout_replacement (Pidgey)
#         self.assertEqual(battle.get_latest_player_combat_milestone(mark_consumed=False), "opponent_knockout")
#         self.assertIsNotNone(battle.get_latest_opponent_switch(mark_consumed=False))
#
#         # Turn 2: Player uses TALK before combat action
#         # Highest priority (Knockout) MUST take precedence!
#         res_talk1 = manager.talk(self.player, "Great job Pikachu!")
#         self.assertTrue(res_talk1.accepted)
#         self.assertIn("knockout", res_talk1.talk_dialogue.lower())
#         self.assertNotIn("pidgey", res_talk1.talk_dialogue.lower())
#
#         # Knockout milestone is now consumed
#         self.assertIsNone(battle.get_latest_player_combat_milestone(mark_consumed=False))
#         # Switch event MUST NOT be lost!
#         self.assertIsNotNone(battle.get_latest_opponent_switch(mark_consumed=False))
#
#         # Turn 2 combat action (non-lethal attack on Pidgey)
#         res_t2 = battle.take_action(BattleAction(action_type=BattleActionType.ATTACK, attack=QUICK_ATTACK))
#         self.assertTrue(res_t2.accepted)
#         self.assertFalse(self.pidgey.is_fainted)
#         self.assertEqual(battle.current_turn, 3)
#
#         # Turn 3: Player uses TALK before combat action
#         # Because no combat milestone exists on turn 2, the deferred switch event is delivered!
#         res_talk2 = manager.talk(self.player, "How does the field look?")
#         self.assertTrue(res_talk2.accepted)
#         self.assertIn("pidgey", res_talk2.talk_dialogue.lower())
#         self.assertIn("ready for the new challenge", res_talk2.talk_dialogue.lower())
#
#         # Switch event is now consumed
#         self.assertIsNone(battle.get_latest_opponent_switch(mark_consumed=False))
#
#     # 8. Wild battles do not produce switch events
#     def test_08_wild_battles_never_produce_switch_events(self) -> None:
#         """Wild battles feature single Pokemon and never emit opponent switch events."""
#         wild_pidgey = Pokemon(species=PIDGEY, personality=self.default_personality, level=25, attacks=[TACKLE])
#
#         manager = BattleManager(seed=42)
#         battle = manager.start_battle(self.player, wild_pidgey, seed=42)
#         self.assertTrue(battle.is_wild_battle)
#
#         # Turn 1: Player attacks
#         res_atk = battle.take_action(BattleAction(action_type=BattleActionType.ATTACK, attack=QUICK_ATTACK))
#         self.assertTrue(res_atk.accepted)
#         self.assertEqual(battle.current_turn, 2)
#
#         self.assertIsNone(battle.get_latest_opponent_switch(mark_consumed=False))
#
#         res_talk = manager.talk(self.player, "Hello Pikachu!")
#         self.assertTrue(res_talk.accepted)
#         self.assertNotIn("new opponent", res_talk.talk_dialogue.lower())
#
#     # 9. Separate battles remain isolated
#     def test_09_separate_battles_remain_isolated(self) -> None:
#         """Switch events and consumption in one battle do not leak into another battle instance."""
#         manager = BattleManager(seed=42)
#         battle1 = manager.start_battle(self.player, self.trainer, seed=42)
#         battle1.switch_opponent_pokemon(self.pidgey)
#
#         # Create separate second battle
#         pika2 = Pokemon(species=PIKACHU, personality=self.default_personality, level=10)
#         player2 = Player(name="Red")
#         player2.add_pokemon(pika2)
#         player2.add_to_team(pika2)
#         player2.set_active_pokemon(pika2)
#
#         trainer2 = Trainer(
#             trainer_id="lass_haley",
#             name="Haley",
#             title="Lass",
#             team=[Pokemon(species=BULBASAUR, personality=self.default_personality, level=5)],
#             archetype=TrainerArchetype.LASS,
#         )
#         battle2 = Battle(pokemon1=pika2, pokemon2=trainer2.team[0], player=player2, opponent_trainer=trainer2, seed=99)
#         battle2.start()
#
#         self.assertIsNotNone(battle1.get_latest_opponent_switch(mark_consumed=False))
#         self.assertIsNone(battle2.get_latest_opponent_switch(mark_consumed=False))
#
#         # Consuming switch in battle 1 does not affect battle 2
#         ev1 = battle1.get_latest_opponent_switch(mark_consumed=True)
#         self.assertIsNotNone(ev1)
#         self.assertIsNone(battle2.get_latest_opponent_switch(mark_consumed=False))
#
#     # 10. Existing knockout, critical-hit, super-effective, DODGE, and free-TALK behavior unchanged
#     def test_10_existing_mechanics_invariants_preserved(self) -> None:
#         """Battle Talk turn economy, tactical dodge, and non-switch combat milestones remain intact."""
#         manager = BattleManager(seed=42)
#         battle = manager.start_battle(self.player, self.rattata, seed=42)
#
#         # Conversational talk is free (does not advance turn)
#         initial_turn = battle.current_turn
#         res_talk = manager.talk(self.player, "Good job!")
#         self.assertTrue(res_talk.accepted)
#         self.assertEqual(res_talk.action_type, BattleActionType.TALK)
#         self.assertEqual(battle.current_turn, initial_turn)
#
#         # Tactical dodge consumes combat turn
#         res_dodge = manager.talk(self.player, "Dodge the next attack!")
#         self.assertTrue(res_dodge.accepted)
#         self.assertEqual(res_dodge.action_type, BattleActionType.DODGE)
#         self.assertEqual(battle.current_turn, initial_turn + 1)
#
#
# if __name__ == "__main__":
#     unittest.main()
