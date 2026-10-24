"""
Unit tests for the Syntax Error 26 Battle Talk Foundation (BT2.1):
- BattleActionType.TALK enum representation
- TalkCategory enum representation
- BattleTalkCommand data model (attributes, immutability, serialization, and alias)
- BattleAction integration and backward compatibility
- BattleActionResult structured result contract
- Authoritative validation in Battle.take_action():
  - Valid conversational commands accepted
  - Tactical commands safely rejected as unsupported in BT2.1
  - Missing, empty, or whitespace-only text rejected
  - Malformed payload types (e.g., int, bool, invalid objects) rejected safely
  - Rejection when battle is not started or already terminal
  - Rejection when active Pokemon is fainted or missing
- Battle lifecycle & turn economy preservation:
  - Turn counter does not advance
  - No opponent attack is triggered
  - No status ticks or combat damage occur
  - Repeated conversational talk allowed within the current turn model
  - RNG determinism preserved
- Post-talk battle progression:
  - Attacks, switches, and normal turn resolution function identically after talk actions
- Public BattleManager API:
  - BattleManager.talk(player, command) routing
  - Type validation on player parameter
  - Safe error response when no battle is active
- Existing action regression tests:
  - ATTACK, SWITCH, FLEE, and INSPECT actions remain fully intact
"""
import random
import unittest
from dataclasses import FrozenInstanceError

from src.models.pokemon import Pokemon
from src.models.player import Player
from src.models.personality import Personality
from src.models.attack import Attack
from src.models.pokemon_type import PokemonType
from src.models.battle_state import BattleState
from src.models.battle import (
    Battle,
    BattleAction,
    BattleActionType,
    BattleActionResult,
    BattleActionRecord,
    BattleTalkCommand,
    BattleTalkPayload,
    BattleTalkIntent,
    TalkCategory,
)
from src.models.battle_manager import BattleManager
from src.models.status_effect import StatusEffectType
from src.models.status_effect_manager import StatusEffectManager
from src.data.species import PIKACHU, CHARMANDER, SQUIRTLE
from src.data.attacks import THUNDER_SHOCK, QUICK_ATTACK, EMBER, SCRATCH, WATER_GUN, TACKLE


class TestBattleTalkFoundation(unittest.TestCase):
    """Test suite verifying the Battle Talk foundational contract (BT2.1)."""

    def setUp(self) -> None:
        self.personality = Personality(
            aggression=50, curiosity=50, fear=50, sociability=50, loyalty=50, confidence=50
        )
        self.pika = Pokemon(
            species=PIKACHU,
            personality=self.personality,
            level=5,
            attacks=[THUNDER_SHOCK, QUICK_ATTACK],
        )
        self.charm = Pokemon(
            species=CHARMANDER,
            personality=self.personality,
            level=5,
            attacks=[EMBER, SCRATCH],
        )
        self.player = Player(name="Ash")
        self.player.add_pokemon(self.pika)
        self.player.add_to_team(self.pika)
        self.player.set_active_pokemon(self.pika)

    # 1. Action enum and TalkCategory representation
    def test_01_enum_representation(self) -> None:
        """BattleActionType.TALK and TalkCategory enums are properly defined."""
        self.assertTrue(hasattr(BattleActionType, "TALK"))
        self.assertEqual(BattleActionType.TALK, "TALK")
        self.assertEqual(BattleActionType.TALK.value, "TALK")
        self.assertIsInstance(BattleActionType.TALK, BattleActionType)

        self.assertEqual(TalkCategory.CONVERSATIONAL, "CONVERSATIONAL")
        self.assertEqual(TalkCategory.TACTICAL, "TACTICAL")
        self.assertIsInstance(TalkCategory.CONVERSATIONAL, TalkCategory)

    # 2. BattleTalkCommand data model contract
    def test_02_command_data_model(self) -> None:
        """BattleTalkCommand stores text, category, intent, is_tactical flag, and metadata."""
        cmd = BattleTalkCommand(
            text="You've got this, Pikachu!",
            category=TalkCategory.CONVERSATIONAL,
            intent="encourage",
            is_tactical=False,
            metadata={"confidence": 0.95},
        )
        self.assertEqual(cmd.text, "You've got this, Pikachu!")
        self.assertEqual(cmd.category, TalkCategory.CONVERSATIONAL)
        self.assertEqual(cmd.intent, "encourage")
        self.assertFalse(cmd.is_tactical)
        self.assertEqual(cmd.metadata, {"confidence": 0.95})

        # Immutability
        with self.assertRaises(FrozenInstanceError):
            cmd.text = "Changed"  # type: ignore

        # Defaults
        default_cmd = BattleTalkCommand(text="Hello")
        self.assertEqual(default_cmd.category, TalkCategory.CONVERSATIONAL)
        self.assertIsNone(default_cmd.intent)
        self.assertFalse(default_cmd.is_tactical)
        self.assertIsNone(default_cmd.metadata)

        # Tactical normalization in post_init
        tactical_cmd = BattleTalkCommand(text="Dodge!", is_tactical=True)
        self.assertEqual(tactical_cmd.category, TalkCategory.TACTICAL)
        self.assertTrue(tactical_cmd.is_tactical)

        # Serialization: to_dict and from_dict
        d = cmd.to_dict()
        self.assertEqual(d["text"], "You've got this, Pikachu!")
        self.assertEqual(d["category"], "CONVERSATIONAL")
        self.assertEqual(d["intent"], "encourage")
        self.assertFalse(d["is_tactical"])

        restored = BattleTalkCommand.from_dict(d)
        self.assertEqual(restored.text, cmd.text)
        self.assertEqual(restored.category, cmd.category)
        self.assertEqual(restored.intent, cmd.intent)
        self.assertEqual(restored.is_tactical, cmd.is_tactical)

        # Backward compatibility alias
        self.assertIs(BattleTalkPayload, BattleTalkCommand)

    # 3. BattleAction dataclass compatibility
    def test_03_action_dataclass_compatibility(self) -> None:
        """BattleAction supports talk_command, talk_payload, and text normalization."""
        # Standard combat action untouched
        atk_act = BattleAction(action_type=BattleActionType.ATTACK, attack=THUNDER_SHOCK)
        self.assertIsNone(atk_act.text)
        self.assertIsNone(atk_act.talk_command)
        self.assertIsNone(atk_act.talk_payload)

        # Talk action with text string
        talk_str = BattleAction(action_type=BattleActionType.TALK, text="Keep focused!")
        self.assertEqual(talk_str.text, "Keep focused!")
        self.assertIsInstance(talk_str.talk_command, BattleTalkCommand)
        self.assertEqual(talk_str.talk_command.text, "Keep focused!")
        self.assertIs(talk_str.talk_command, talk_str.talk_payload)

        # Talk action with BattleTalkCommand
        cmd = BattleTalkCommand(text="Hang in there!", intent="cheer")
        talk_cmd = BattleAction(action_type=BattleActionType.TALK, talk_command=cmd)
        self.assertEqual(talk_cmd.text, "Hang in there!")
        self.assertIs(talk_cmd.talk_command, cmd)
        self.assertIs(talk_cmd.talk_payload, cmd)

    # 4. Valid conversational command accepted
    def test_04_valid_conversational_command_accepted(self) -> None:
        """A valid conversational command returns an accepted BattleActionResult with intent and dialogue."""
        battle = Battle(self.pika, self.charm, seed=42)
        battle.start()

        cmd = BattleTalkCommand(text="Great job, stay alert!")
        res = battle.take_action(BattleAction(action_type=BattleActionType.TALK, talk_command=cmd))

        self.assertTrue(res.accepted)
        self.assertEqual(res.action_type, BattleActionType.TALK)
        self.assertEqual(res.battle_state, BattleState.IN_PROGRESS)
        self.assertFalse(res.terminal)
        self.assertIsNone(res.error_type)
        self.assertIsNotNone(res.talk_command)
        self.assertEqual(res.talk_command.text, "Great job, stay alert!")
        self.assertEqual(res.talk_payload.text, "Great job, stay alert!")
        self.assertIn("Great job, stay alert!", res.reason)
        self.assertIsNotNone(res.talk_dialogue)
        self.assertIsNotNone(res.talk_intent)

        # Second talk in the same turn is rejected with TALK_LIMIT_REACHED
        res2 = battle.talk("We can do this!")
        self.assertFalse(res2.accepted)
        self.assertEqual(res2.error_type, "TALK_LIMIT_REACHED")

    # 5. Unsupported tactical manoeuvres safely rejected
    def test_05_tactical_command_rejected_unsupported(self) -> None:
        """Unsupported tactical commands like jump/block/parry are rejected with UNSUPPORTED_COMMAND."""
        battle = Battle(self.pika, self.charm, seed=42)
        battle.start()

        cmd_tactical = BattleTalkCommand(
            text="Jump over the attack!",
            category=TalkCategory.TACTICAL,
            is_tactical=True,
        )
        res = battle.take_action(BattleAction(action_type=BattleActionType.TALK, talk_command=cmd_tactical))

        self.assertFalse(res.accepted)
        self.assertEqual(res.error_type, "UNSUPPORTED_COMMAND")
        self.assertIn("Tactical manoeuvres", res.reason)

    # 6. Missing, empty, or whitespace-only commands rejected
    def test_06_empty_or_missing_command_rejected(self) -> None:
        """Missing or blank text inputs are rejected with appropriate error types."""
        battle = Battle(self.pika, self.charm, seed=42)
        battle.start()

        # Missing text and command
        res_missing = battle.take_action(BattleAction(action_type=BattleActionType.TALK))
        self.assertFalse(res_missing.accepted)
        self.assertEqual(res_missing.error_type, "MISSING_TALK_TEXT")

        # Empty string
        res_empty = battle.talk("")
        self.assertFalse(res_empty.accepted)
        self.assertEqual(res_empty.error_type, "EMPTY_TALK_TEXT")

        # Whitespace only
        res_ws = battle.talk("   \t  \n ")
        self.assertFalse(res_ws.accepted)
        self.assertEqual(res_ws.error_type, "EMPTY_TALK_TEXT")

    # 7. Malformed payload types rejected cleanly
    def test_07_malformed_payload_rejected(self) -> None:
        """Non-string text or invalid payload objects are rejected without uncaught exceptions."""
        battle = Battle(self.pika, self.charm, seed=42)
        battle.start()

        res_int = battle.take_action(BattleAction(action_type=BattleActionType.TALK, text=12345))  # type: ignore
        self.assertFalse(res_int.accepted)
        self.assertEqual(res_int.error_type, "MALFORMED_TALK_PAYLOAD")

        res_bool = battle.take_action(BattleAction(action_type=BattleActionType.TALK, text=True))  # type: ignore
        self.assertFalse(res_bool.accepted)
        self.assertEqual(res_bool.error_type, "MALFORMED_TALK_PAYLOAD")

        res_bad_obj = battle.take_action(BattleAction(action_type=BattleActionType.TALK, talk_command=object()))  # type: ignore
        self.assertFalse(res_bad_obj.accepted)
        self.assertEqual(res_bad_obj.error_type, "MALFORMED_TALK_PAYLOAD")

        # BattleTalkCommand with non-string text
        res_bad_cmd = battle.take_action(
            BattleAction(action_type=BattleActionType.TALK, talk_command=BattleTalkCommand(text=None))  # type: ignore
        )
        self.assertFalse(res_bad_cmd.accepted)
        self.assertEqual(res_bad_cmd.error_type, "MALFORMED_TALK_PAYLOAD")

    # 8. Battle state lifecycle validation (terminal and unstarted)
    def test_08_terminal_and_unstarted_battles(self) -> None:
        """Talk is rejected before battle starts and after conclusion."""
        # Unstarted battle
        unstarted = Battle(self.pika, self.charm, seed=42)
        self.assertEqual(unstarted.state, BattleState.NOT_STARTED)
        self.assertFalse(unstarted.can_talk_this_turn)
        res_unstarted = unstarted.talk("Get ready!")
        self.assertFalse(res_unstarted.accepted)
        self.assertEqual(res_unstarted.error_type, "BATTLE_NOT_STARTED")

        # Concluded / terminal battle
        battle = Battle(self.pika, self.charm, seed=42)
        battle.start()
        battle.flee()
        self.assertTrue(battle.state.is_terminal())
        self.assertFalse(battle.can_talk_this_turn)

        res_term = battle.talk("Good job fleeing!")
        self.assertFalse(res_term.accepted)
        self.assertEqual(res_term.error_type, "BATTLE_ALREADY_TERMINAL")
        self.assertTrue(res_term.terminal)

    # 9. Active Pokemon state validation (fainted or missing)
    def test_09_active_pokemon_state_validation(self) -> None:
        """Talk is rejected when the active player Pokemon is fainted or missing."""
        battle = Battle(self.pika, self.charm, seed=42)
        battle.start()

        self.pika.current_hp = 0
        self.assertTrue(self.pika.is_fainted)
        self.assertFalse(battle.can_talk_this_turn)

        res_fainted = battle.talk("Get back up!")
        self.assertFalse(res_fainted.accepted)
        self.assertEqual(res_fainted.error_type, "POKEMON_FAINTED")
        self.assertIn("fainted", res_fainted.reason)

        # Missing active pokemon
        battle._pokemon1 = None  # type: ignore
        res_missing_mon = battle.talk("Hello?")
        self.assertFalse(res_missing_mon.accepted)
        self.assertEqual(res_missing_mon.error_type, "NO_ACTIVE_POKEMON")

    # 10. Turn economy and non-mutation: no turn advance, no opponent attack, no damage
    def test_10_turn_economy_and_no_opponent_attack(self) -> None:
        """Conversational talk does not advance turn, trigger opponent attacks, or tick damage."""
        status_manager = StatusEffectManager()
        status_manager.apply_effect(self.charm, StatusEffectType.POISON)

        battle = Battle(self.pika, self.charm, seed=42, status_manager=status_manager)
        battle.start()
        self.assertEqual(battle.current_turn, 1)

        pika_hp_before = self.pika.current_hp
        charm_hp_before = self.charm.current_hp
        pika_bond_before = self.pika.bond
        pika_ob_before = self.pika.obedience

        # First talk
        res1 = battle.talk("Stay focused!")
        self.assertTrue(res1.accepted)
        self.assertEqual(battle.current_turn, 1)

        # Repeated conversational talk in same turn is rejected with TALK_LIMIT_REACHED
        res2 = battle.talk("You can do this!")
        self.assertFalse(res2.accepted)
        self.assertEqual(res2.error_type, "TALK_LIMIT_REACHED")
        self.assertEqual(battle.current_turn, 1)

        # Combat state unchanged
        self.assertEqual(self.pika.current_hp, pika_hp_before)
        self.assertEqual(self.charm.current_hp, charm_hp_before)
        self.assertEqual(self.pika.bond, pika_bond_before)
        self.assertEqual(self.pika.obedience, pika_ob_before)
        self.assertEqual(battle.state, BattleState.IN_PROGRESS)

    # 11. Post-talk battle progression remains standard
    def test_11_normal_combat_action_after_talk(self) -> None:
        """After talking, an attack executes normally, consumes the turn, and damages opponent."""
        battle = Battle(self.pika, self.charm, seed=42, use_random_damage=False)
        battle.start()
        self.assertEqual(battle.current_turn, 1)

        # Talk first
        res_talk = battle.talk("Pikachu, let's start!")
        self.assertTrue(res_talk.accepted)
        self.assertEqual(battle.current_turn, 1)

        # Attack afterwards
        res_atk = battle.execute_player_attack(THUNDER_SHOCK)
        self.assertTrue(res_atk.accepted)
        self.assertIsNotNone(res_atk.turn_result)
        self.assertEqual(battle.current_turn, 2)
        self.assertLess(self.charm.current_hp, self.charm.max_hp)

    # 12. Seeded determinism and RNG isolation
    def test_12_seeded_determinism_preserved(self) -> None:
        """Conversational talk does not consume or desynchronize seeded RNG rolls."""
        rng1 = random.Random(777)
        battle1 = Battle(self.pika, self.charm, rng=rng1, use_random_damage=True)
        battle1.start()

        pika_clone = Pokemon(species=PIKACHU, personality=self.personality, level=5, attacks=[THUNDER_SHOCK, QUICK_ATTACK])
        charm_clone = Pokemon(species=CHARMANDER, personality=self.personality, level=5, attacks=[EMBER, SCRATCH])
        rng2 = random.Random(777)
        battle2 = Battle(pika_clone, charm_clone, rng=rng2, use_random_damage=True)
        battle2.start()

        # Battle 1 talks first
        battle1.talk("Concentrate!")

        # Both resolve identical attack actions
        res1 = battle1.execute_player_attack(THUNDER_SHOCK)
        res2 = battle2.execute_player_attack(THUNDER_SHOCK)

        # Identical damage confirms RNG was not advanced by talk
        self.assertEqual(res1.turn_result.actions[0].damage, res2.turn_result.actions[0].damage)

    # 13. Public BattleManager.talk() API
    def test_13_battle_manager_talk_api(self) -> None:
        """BattleManager.talk() routes talk actions and validates player argument."""
        manager = BattleManager(seed=42)

        # TypeError on invalid player
        with self.assertRaises(TypeError):
            manager.talk("NotAPlayer", "Hi")  # type: ignore

        # No active battle
        res_no_battle = manager.talk(self.player, "Hello?")
        self.assertFalse(res_no_battle.accepted)
        self.assertEqual(res_no_battle.error_type, "NO_ACTIVE_BATTLE")

        # Active battle with text string
        battle = manager.start_battle(self.player, self.charm)
        res_active_str = manager.talk(self.player, "Go Pikachu!")
        self.assertTrue(res_active_str.accepted)
        self.assertEqual(res_active_str.action_type, BattleActionType.TALK)
        self.assertEqual(res_active_str.talk_command.text, "Go Pikachu!")

        # Second talk in same turn is rejected with TALK_LIMIT_REACHED
        cmd = BattleTalkCommand(text="Focus on timing!", intent="tactical_advice")
        res_limit = manager.talk(self.player, cmd)
        self.assertFalse(res_limit.accepted)
        self.assertEqual(res_limit.error_type, "TALK_LIMIT_REACHED")

        # After resolving a combat turn, talk is accepted again
        battle.execute_player_attack(THUNDER_SHOCK)
        res_active_cmd = manager.talk(self.player, cmd)
        self.assertTrue(res_active_cmd.accepted)
        self.assertEqual(res_active_cmd.talk_command.text, "Focus on timing!")

    # 14. Existing action regression verification (ATTACK, SWITCH, FLEE, INSPECT)
    def test_14_existing_actions_regression(self) -> None:
        """ATTACK, SWITCH, FLEE, and INSPECT actions maintain their behavior."""
        squirtle = Pokemon(species=SQUIRTLE, personality=self.personality, level=5, attacks=[WATER_GUN, TACKLE])
        self.player.add_pokemon(squirtle)
        self.player.add_to_team(squirtle)

        battle = Battle(self.pika, self.charm, player=self.player, player_team=[self.pika, squirtle], seed=42)
        battle.start()

        # INSPECT
        res_inspect = battle.inspect()
        self.assertTrue(res_inspect.accepted)
        self.assertEqual(res_inspect.action_type, BattleActionType.INSPECT)

        # SWITCH
        res_switch = battle.take_action(BattleAction(action_type=BattleActionType.SWITCH, target_pokemon=squirtle))
        self.assertTrue(res_switch.accepted)
        self.assertEqual(battle.pokemon1, squirtle)

        # ATTACK
        res_atk = battle.execute_player_attack(WATER_GUN)
        self.assertTrue(res_atk.accepted)
        self.assertEqual(res_atk.action_type, BattleActionType.ATTACK)

        # FLEE
        res_flee = battle.flee()
        self.assertTrue(res_flee.accepted)
        self.assertEqual(res_flee.action_type, BattleActionType.FLEE)
        self.assertEqual(battle.state, BattleState.ESCAPED)

    # 15. Rejected talk attempts do not consume turn allowance
    def test_15_allowance_preserved_on_rejected_input(self) -> None:
        """Malformed or blank talk inputs do not consume the turn allowance."""
        battle = Battle(self.pika, self.charm, seed=42)
        battle.start()
        self.assertTrue(battle.can_talk_this_turn)

        # 1. Blank input rejected
        res_empty = battle.talk("   ")
        self.assertFalse(res_empty.accepted)
        self.assertEqual(res_empty.error_type, "EMPTY_TALK_TEXT")
        self.assertTrue(battle.can_talk_this_turn)

        # 2. Malformed input rejected
        res_bad = battle.take_action(BattleAction(action_type=BattleActionType.TALK, text=12345))  # type: ignore
        self.assertFalse(res_bad.accepted)
        self.assertEqual(res_bad.error_type, "MALFORMED_TALK_PAYLOAD")
        self.assertTrue(battle.can_talk_this_turn)

        # 3. Tactical input rejected
        res_tactical = battle.take_action(
            BattleAction(action_type=BattleActionType.TALK, talk_command=BattleTalkCommand(text="Block the attack!", is_tactical=True))
        )
        self.assertFalse(res_tactical.accepted)
        self.assertEqual(res_tactical.error_type, "UNSUPPORTED_COMMAND")
        self.assertTrue(battle.can_talk_this_turn)

        # 4. Valid talk now succeeds and consumes allowance
        res_valid = battle.talk("Let's go, Pikachu!")
        self.assertTrue(res_valid.accepted)
        self.assertFalse(battle.can_talk_this_turn)

        # 5. Second valid talk is now rejected due to limit
        res_limit = battle.talk("One more thing!")
        self.assertFalse(res_limit.accepted)
        self.assertEqual(res_limit.error_type, "TALK_LIMIT_REACHED")

    # 16. Authoritative turn advance resets allowance (attack and switch)
    def test_16_turn_advance_via_attack_and_switch_resets_allowance(self) -> None:
        """Turn advance via attack and switch properly resets the talk allowance."""
        squirtle = Pokemon(species=SQUIRTLE, personality=self.personality, level=5, attacks=[WATER_GUN, TACKLE])
        self.player.add_pokemon(squirtle)
        self.player.add_to_team(squirtle)

        battle = Battle(self.pika, self.charm, player=self.player, player_team=[self.pika, squirtle], seed=42)
        battle.start()
        self.assertEqual(battle.current_turn, 1)

        # Turn 1 talk
        res_t1 = battle.talk("Give it your best!")
        self.assertTrue(res_t1.accepted)
        self.assertFalse(battle.can_talk_this_turn)

        # Attack advances turn to 2
        battle.execute_player_attack(THUNDER_SHOCK)
        self.assertEqual(battle.current_turn, 2)
        self.assertTrue(battle.can_talk_this_turn)

        # Turn 2 talk
        res_t2 = battle.talk("Great job on that hit!")
        self.assertTrue(res_t2.accepted)
        self.assertFalse(battle.can_talk_this_turn)

        # Switch advances turn to 3
        battle.take_action(BattleAction(action_type=BattleActionType.SWITCH, target_pokemon=squirtle))
        self.assertEqual(battle.current_turn, 3)
        self.assertTrue(battle.can_talk_this_turn)

        # Turn 3 talk to new active Pokemon
        res_t3 = battle.talk("You're up, Squirtle!")
        self.assertTrue(res_t3.accepted)
        self.assertFalse(battle.can_talk_this_turn)

    # 17. Repeated action queries do not reset allowance
    def test_17_repeated_action_queries_do_not_reset_allowance(self) -> None:
        """Querying can_talk_this_turn or inspecting battle does not reset allowance."""
        battle = Battle(self.pika, self.charm, seed=42)
        battle.start()

        # Talk consumed
        res_talk = battle.talk("Focus up!")
        self.assertTrue(res_talk.accepted)
        self.assertFalse(battle.can_talk_this_turn)

        # Inspecting or querying property
        for _ in range(5):
            self.assertFalse(battle.can_talk_this_turn)

        # Non-turn-advancing query
        battle.can_switch_pokemon(self.pika)
        self.assertFalse(battle.can_talk_this_turn)

        # Repeated talk still rejected
        res_retry = battle.talk("Still listening?")
        self.assertFalse(res_retry.accepted)
        self.assertEqual(res_retry.error_type, "TALK_LIMIT_REACHED")

    # 18. Four intents and personality-aware dialogue via Battle.take_action()
    def test_18_four_intents_and_personality_aware_dialogue_via_take_action(self) -> None:
        """The four intents (PRAISE, ENCOURAGE, WARNING, GENERAL) and dialogue resolve through take_action()."""
        # Test PRAISE
        b1 = Battle(self.pika, self.charm, seed=42)
        b1.start()
        res_praise = b1.take_action(BattleAction(action_type=BattleActionType.TALK, text="Great job, Pikachu!"))
        self.assertTrue(res_praise.accepted)
        self.assertEqual(res_praise.talk_intent, BattleTalkIntent.PRAISE)
        self.assertIsNotNone(res_praise.talk_dialogue)
        self.assertIsInstance(res_praise.talk_dialogue, str)
        self.assertGreater(len(res_praise.talk_dialogue), 0)

        # Test ENCOURAGE
        b2 = Battle(self.pika, self.charm, seed=42)
        b2.start()
        res_enc = b2.take_action(BattleAction(action_type=BattleActionType.TALK, text="You can do this! Don't give up!"))
        self.assertTrue(res_enc.accepted)
        self.assertEqual(res_enc.talk_intent, BattleTalkIntent.ENCOURAGE)
        self.assertIsNotNone(res_enc.talk_dialogue)

        # Test WARNING
        b3 = Battle(self.pika, self.charm, seed=42)
        b3.start()
        res_warn = b3.take_action(BattleAction(action_type=BattleActionType.TALK, text="Watch out for incoming attacks!"))
        self.assertTrue(res_warn.accepted)
        self.assertEqual(res_warn.talk_intent, BattleTalkIntent.WARNING)
        self.assertIsNotNone(res_warn.talk_dialogue)

        # Test GENERAL
        b4 = Battle(self.pika, self.charm, seed=42)
        b4.start()
        res_gen = b4.take_action(BattleAction(action_type=BattleActionType.TALK, text="I'm right here with you."))
        self.assertTrue(res_gen.accepted)
        self.assertEqual(res_gen.talk_intent, BattleTalkIntent.GENERAL)
        self.assertIsNotNone(res_gen.talk_dialogue)

        # Determinism: identical input and personality produces identical dialogue
        b5 = Battle(self.pika, self.charm, seed=42)
        b5.start()
        res_praise_2 = b5.take_action(BattleAction(action_type=BattleActionType.TALK, text="Great job, Pikachu!"))
        self.assertEqual(res_praise.talk_dialogue, res_praise_2.talk_dialogue)

        # Personality contrast: high confidence vs high fear produce different reactions
        p_confident = Personality(confidence=90, fear=10, aggression=50, sociability=50, loyalty=50, curiosity=50)
        p_fearful = Personality(confidence=10, fear=90, aggression=50, sociability=50, loyalty=50, curiosity=50)
        mon_conf = Pokemon(species=PIKACHU, personality=p_confident, level=5, attacks=[THUNDER_SHOCK])
        mon_fear = Pokemon(species=PIKACHU, personality=p_fearful, level=5, attacks=[THUNDER_SHOCK])

        b_conf = Battle(mon_conf, self.charm, seed=42)
        b_conf.start()
        res_conf = b_conf.talk("Watch out!")

        b_fear = Battle(mon_fear, self.charm, seed=42)
        b_fear.start()
        res_fear = b_fear.talk("Watch out!")

        self.assertNotEqual(res_conf.talk_dialogue, res_fear.talk_dialogue)

    # 19. Talk strictly cosmetic invariants
    def test_19_talk_remains_strictly_cosmetic_invariants(self) -> None:
        """Conversational talk does not mutate HP, bond, obedience, personality, or status effects."""
        status_manager = StatusEffectManager()
        battle = Battle(self.pika, self.charm, seed=42, status_manager=status_manager)
        battle.start()
        status_manager.apply_effect(self.pika, StatusEffectType.PARALYSIS)

        hp_before = self.pika.current_hp
        bond_before = self.pika.bond
        ob_before = self.pika.obedience
        traits_before = {
            "agg": self.pika.personality.aggression,
            "cur": self.pika.personality.curiosity,
            "fear": self.pika.personality.fear,
            "soc": self.pika.personality.sociability,
            "loy": self.pika.personality.loyalty,
            "conf": self.pika.personality.confidence,
        }

        res = battle.talk("You're doing amazing!")
        self.assertTrue(res.accepted)

        self.assertEqual(self.pika.current_hp, hp_before)
        self.assertEqual(self.pika.bond, bond_before)
        self.assertEqual(self.pika.obedience, ob_before)
        self.assertEqual(self.pika.personality.aggression, traits_before["agg"])
        self.assertEqual(self.pika.personality.curiosity, traits_before["cur"])
        self.assertEqual(self.pika.personality.fear, traits_before["fear"])
        self.assertEqual(self.pika.personality.sociability, traits_before["soc"])
        self.assertEqual(self.pika.personality.loyalty, traits_before["loy"])
        self.assertEqual(self.pika.personality.confidence, traits_before["conf"])
        self.assertTrue(status_manager.has_effect(self.pika, StatusEffectType.PARALYSIS))


if __name__ == "__main__":
    unittest.main()
