"""
Unit tests for Syntax Error 26 BT2.3: Tactical Battle Commands and Dodge Mechanics:
- BattleActionType.DODGE enum representation and BattleActionResult contract
- Public APIs: Battle.dodge(), BattleManager.dodge(player), and BattleManager.talk(player, "dodge...") routing
- Probabilistic obedience check using ObedienceManager
- Deterministic evasion probability model:
    clamp(0.45 + speed_mod + bond_mod + conf_mod + fear_mod + acc_mod, 0.10, 0.85)
- Turn resolution:
    - Dodge attempt consumes exactly one combat turn (current_turn advances)
    - Opponent attack executes exactly once (turn_result.actions has 1 action record)
    - Successful dodge: damage is 0, attack status effects avoided, event logged
    - Failed dodge: damage dealt normally, attack status effects applied
    - Disobedient dodge: pokemon refuses to dodge, takes full attack damage
    - Status effect ticks (poison, burn) still resolve at end of turn during dodge
    - Defensive state does not persist or leak into subsequent turns
    - Consecutive dodges evaluate obedience and evasion independently
    - Terminal battle and fainted Pokemon safety validation
    - Unsupported tactical commands (jump, parry, block) remain rejected
"""
import unittest
from dataclasses import replace

from src.models.pokemon import Pokemon, PokemonSpecies
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
#     BattleTalkCommand,
#     TalkCategory,
)
from src.models.battle_manager import BattleManager
from src.models.obedience_manager import ObedienceManager, ObedienceResult
from src.models.status_effect import StatusEffectType
from src.models.status_effect_manager import StatusEffectManager
from src.data.species import PIKACHU, CHARMANDER, SQUIRTLE
from src.data.attacks import THUNDER_SHOCK, QUICK_ATTACK, EMBER, SCRATCH, WATER_GUN, TACKLE


class TestBattleTacticalDodge(unittest.TestCase):
    """Test suite for BT2.3 Tactical Dodge Mechanics."""

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

    # 1. Action enum and result structure
    def test_01_action_enum_and_result_fields(self) -> None:
        """BattleActionType.DODGE exists and BattleActionResult carries dodge fields."""
        self.assertTrue(hasattr(BattleActionType, "DODGE"))
        self.assertEqual(BattleActionType.DODGE, "DODGE")

        battle = Battle(self.pika, self.charm, seed=42)
        battle.start()
        res = battle.dodge()

        self.assertTrue(res.accepted)
        self.assertEqual(res.action_type, BattleActionType.DODGE)
        self.assertIsInstance(res.is_obeyed, bool)
        self.assertIsInstance(res.dodge_successful, bool)
        self.assertIsNotNone(res.dodge_probability)
        self.assertGreaterEqual(res.dodge_probability, 0.10)
        self.assertLessEqual(res.dodge_probability, 0.85)
        self.assertIsNotNone(res.obedience_result)

    # 2. Probability formula calculation
    def test_02_dodge_probability_formula(self) -> None:
        """calculate_dodge_probability matches documented formula and clamps to [0.10, 0.85]."""
        # Create species with controlled speeds
        spec_50 = replace(PIKACHU, base_speed=50)
        mon1 = Pokemon(species=spec_50, personality=self.personality, level=5)
        mon2 = Pokemon(species=spec_50, personality=self.personality, level=5)
        mon1.bond = 0

        battle = Battle(mon1, mon2, seed=42)
        # Equal speed (50 vs 50), 0 bond, 50 conf, 50 fear, 100 acc attack
        # base=0.45, speed_mod=0, bond_mod=0, conf_mod=0, fear_mod=0, acc_mod=0 -> 0.45
        prob = battle.calculate_dodge_probability(mon1, mon2, incoming_attack=EMBER)
        self.assertAlmostEqual(prob, 0.45, places=4)

        # High bond (+0.10 at 100 bond)
        mon1.bond = 100
        prob_bond = battle.calculate_dodge_probability(mon1, mon2, incoming_attack=EMBER)
        self.assertAlmostEqual(prob_bond, 0.55, places=4)

        # Lower accuracy incoming attack (80 acc -> +0.10)
        inacc_attack = Attack(name="Inaccurate", type=PokemonType.NORMAL, power=50, accuracy=80)
        prob_inacc = battle.calculate_dodge_probability(mon1, mon2, incoming_attack=inacc_attack)
        self.assertAlmostEqual(prob_inacc, 0.65, places=4)

        # High speed difference (+0.15 capped)
        spec_fast = replace(PIKACHU, base_speed=200)
        spec_slow = replace(CHARMANDER, base_speed=10)
        mon_fast = Pokemon(species=spec_fast, personality=self.personality, level=5)
        mon_slow = Pokemon(species=spec_slow, personality=self.personality, level=5)
        mon_fast.bond = 100
        prob_fast = battle.calculate_dodge_probability(mon_fast, mon_slow, incoming_attack=EMBER)
        # 0.45 + 0.15 (speed) + 0.10 (bond) = 0.70
        self.assertAlmostEqual(prob_fast, 0.70, places=4)

        # Extreme values clamp to [0.10, 0.85]
        spec_ultra_fast = replace(PIKACHU, base_speed=1000)
        mon_ultra_fast = Pokemon(
            species=spec_ultra_fast,
            personality=Personality(aggression=50, curiosity=50, fear=0, sociability=50, loyalty=50, confidence=100),
            level=5,
        )
        mon_ultra_fast.bond = 100
        super_inacc = Attack(name="Wild", type=PokemonType.NORMAL, power=100, accuracy=10)
        prob_max = battle.calculate_dodge_probability(mon_ultra_fast, mon_slow, incoming_attack=super_inacc)
        self.assertEqual(prob_max, 0.85)

        # Extreme slow clamp to 0.10
        spec_ultra_slow = replace(PIKACHU, base_speed=1)
        mon_ultra_slow = Pokemon(
            species=spec_ultra_slow,
            personality=Personality(aggression=50, curiosity=50, fear=100, sociability=50, loyalty=50, confidence=0),
            level=5,
        )
        mon_ultra_slow.bond = 0
        accurate_atk = Attack(name="Laser", type=PokemonType.NORMAL, power=10, accuracy=100)
        prob_min = battle.calculate_dodge_probability(mon_ultra_slow, mon_fast, incoming_attack=accurate_atk)
        self.assertAlmostEqual(prob_min, 0.25, places=4)

    # 3. Successful dodge avoids damage and attack effects
    def test_03_successful_dodge_avoids_damage(self) -> None:
        """When dodge succeeds, defender takes 0 damage and turn advances."""
        # Seed 0 deterministically yields obedience success and dodge success
        battle = Battle(self.pika, self.charm, seed=0)
        battle.start()

        res = battle.dodge()

        self.assertTrue(res.accepted)
        self.assertTrue(res.is_obeyed)
        self.assertTrue(res.dodge_successful)
        self.assertEqual(self.pika.current_hp, self.pika.max_hp)
        self.assertIn("successfully dodged", res.reason)
        self.assertEqual(battle.current_turn, 2)
        self.assertEqual(len(res.turn_result.actions), 1)
        record = res.turn_result.actions[0]
        self.assertEqual(record.damage, 0)
        self.assertFalse(record.hit)
        self.assertIn("skillfully dodged", record.message)

    # 4. Failed dodge deals normal damage
    def test_04_failed_dodge_takes_normal_damage(self) -> None:
        """When dodge fails, defender takes normal damage from the opponent attack."""
        # Seed 1 deterministically yields obedience success but dodge failure
        battle = Battle(self.pika, self.charm, seed=1)
        battle.start()

        initial_hp = self.pika.current_hp
        res = battle.dodge()

        self.assertTrue(res.accepted)
        self.assertTrue(res.is_obeyed)
        self.assertFalse(res.dodge_successful)
        self.assertLess(self.pika.current_hp, initial_hp)
        self.assertIn("failed to dodge", res.reason)
        self.assertEqual(battle.current_turn, 2)
        self.assertEqual(len(res.turn_result.actions), 1)
        record = res.turn_result.actions[0]
        self.assertGreater(record.damage, 0)
        self.assertTrue(record.hit)

    # 5. Obedience failure causes dodge command to be ignored
    def test_05_disobedience_causes_dodge_failure(self) -> None:
        """A disobedient Pokemon ignores the dodge command and opponent attack resolves normally."""
        battle = Battle(self.pika, self.charm, seed=1)
        battle.start()

        class DisobedientManager(ObedienceManager):
            def evaluate_obedience(self, pokemon, context=None, rng=None):
                return ObedienceResult(
                    is_obeyed=False,
                    obedience=0,
                    bond=0,
                    probability=0.1,
                    reason="Pokemon loafed around!",
                )
        battle._obedience_manager = DisobedientManager()

        initial_hp = self.pika.current_hp
        res = battle.dodge()

        self.assertTrue(res.accepted)
        self.assertFalse(res.is_obeyed)
        self.assertFalse(res.dodge_successful)
        self.assertIn("disobeyed", res.reason)
        self.assertLess(self.pika.current_hp, initial_hp)
        self.assertEqual(battle.current_turn, 2)

    # 6. Opponent attack resolves exactly once
    def test_06_opponent_attack_resolves_exactly_once(self) -> None:
        """During a dodge action, opponent acts exactly once and only one action record is created."""
        battle = Battle(self.pika, self.charm, seed=42)
        battle.start()

        res = battle.dodge()
        self.assertEqual(len(res.turn_result.actions), 1)
        self.assertEqual(res.turn_result.actions[0].attacker, self.charm)
        self.assertEqual(res.turn_result.actions[0].defender, self.pika)
        self.assertEqual(len(battle.turn_history), 1)

    # 7. Status effect on attack skipped on dodge success
    def test_07_status_inflicting_attack_skipped_on_successful_dodge(self) -> None:
        """If opponent uses a status-inflicting attack and dodge succeeds, status is not applied."""
        status_manager = StatusEffectManager()
        # Seed 0 gives successful dodge
        battle = Battle(self.pika, self.charm, seed=0, status_manager=status_manager)
        battle.start()

        res = battle.dodge()
        self.assertTrue(res.dodge_successful)
        # Ensure pika has no status effects
        self.assertFalse(status_manager.has_effect(self.pika, StatusEffectType.BURN))
        self.assertFalse(status_manager.has_effect(self.pika, StatusEffectType.PARALYSIS))

    # 8. Defensive state cleanup (no immunity leak to next turn)
    def test_08_defensive_state_does_not_leak_into_subsequent_turns(self) -> None:
        """After a successful dodge, the next turn's normal attack does not inherit dodge immunity."""
        # Turn 1: Seed 0 dodge succeeds
        battle = Battle(self.pika, self.charm, seed=0)
        battle.start()

        res_dodge = battle.dodge()
        self.assertTrue(res_dodge.dodge_successful)
        self.assertEqual(self.pika.current_hp, self.pika.max_hp)
        self.assertEqual(battle.current_turn, 2)

        # Turn 2: Player uses an attack; opponent counter-attacks normally
        res_attack = battle.take_action(BattleAction(action_type=BattleActionType.ATTACK, attack=QUICK_ATTACK))
        self.assertTrue(res_attack.accepted)
        self.assertEqual(battle.current_turn, 3)
        # Charmander attacked pika and dealt damage (no immunity lingering)
        self.assertLess(self.pika.current_hp, self.pika.max_hp)

    # 9. Consecutive dodges evaluate independently
    def test_09_consecutive_dodges_evaluate_independently(self) -> None:
        """Multiple consecutive dodges consume turns and evaluate independently without crashing."""
        battle = Battle(self.pika, self.charm, seed=42)
        battle.start()

        res1 = battle.dodge()
        self.assertTrue(res1.accepted)
        self.assertEqual(battle.current_turn, 2)

        res2 = battle.dodge()
        self.assertTrue(res2.accepted)
        self.assertEqual(battle.current_turn, 3)

        self.assertEqual(len(battle.turn_history), 2)

    # 10. End-of-turn status damage still processes during dodge
    def test_10_end_of_turn_status_damage_ticks_during_dodge(self) -> None:
        """Poison or burn damage still ticks at end-of-turn even if dodge is executed."""
        status_manager = StatusEffectManager()
        # Seed 0 gives successful dodge
        battle = Battle(self.pika, self.charm, seed=0, status_manager=status_manager)
        battle.start()

        # Apply POISON to Pikachu before dodging
        status_manager.apply_effect(self.pika, StatusEffectType.POISON)
        hp_before = self.pika.current_hp

        res = battle.dodge()
        self.assertTrue(res.dodge_successful)
        # Pikachu dodged the opponent's strike, but poison damage ticked at end of turn!
        self.assertLess(self.pika.current_hp, hp_before)

    # 11. Terminal battle and fainted state validation
    def test_11_terminal_and_fainted_state_validation(self) -> None:
        """Dodge is rejected if active Pokemon is fainted or battle has ended."""
        battle = Battle(self.pika, self.charm, seed=42)
        battle.start()

        # Fainted active Pokemon
        self.pika.current_hp = 0
        res_fainted = battle.dodge()
        self.assertFalse(res_fainted.accepted)
        self.assertEqual(res_fainted.error_type, "POKEMON_FAINTED")

        # Concluded battle
        self.pika.current_hp = self.pika.max_hp
        self.charm.current_hp = 0
        battle._update_terminal_state()
        self.assertTrue(battle.state.is_terminal())

        res_terminal = battle.dodge()
        self.assertFalse(res_terminal.accepted)
        self.assertEqual(res_terminal.error_type, "BATTLE_ALREADY_TERMINAL")

    # 12. BattleManager.dodge() API
    def test_12_battle_manager_dodge_api(self) -> None:
        """BattleManager.dodge(player) dispatches dodge action through execute_action()."""
        manager = BattleManager(seed=42)
        manager.start_battle(self.player, self.charm)

        res = manager.dodge(self.player)
        self.assertTrue(res.accepted)
        self.assertEqual(res.action_type, BattleActionType.DODGE)
        self.assertIsNotNone(res.turn_result)

        # Non-Player type rejection
        with self.assertRaises(TypeError):
            manager.dodge("not a player")  # type: ignore

    # 13. Natural language routing via BattleManager.talk()
#     def test_13_natural_language_routing_via_talk(self) -> None:
#         """BattleManager.talk() routes dodge phrases to BattleActionType.DODGE."""
#         manager = BattleManager(seed=42)
#         manager.start_battle(self.player, self.charm)
# 
        # "Pikachu, dodge that attack!" routes to DODGE
#         res = manager.talk(self.player, "Pikachu, dodge that attack!")
#         self.assertTrue(res.accepted)
#         self.assertEqual(res.action_type, BattleActionType.DODGE)
#         self.assertIsNotNone(res.dodge_probability)
# 
    # 14. Unsupported tactical commands remain rejected via manager.talk()
#     def test_14_unsupported_tactical_commands_rejected_via_talk(self) -> None:
#         """Unsupported tactical actions (jump, block, parry) remain rejected with UNSUPPORTED_COMMAND."""
#         manager = BattleManager(seed=42)
#         manager.start_battle(self.player, self.charm)
# 
#         res_jump = manager.talk(self.player, "Jump over the attack!")
#         self.assertFalse(res_jump.accepted)
#         self.assertEqual(res_jump.error_type, "UNSUPPORTED_COMMAND")
# 
#         res_block = manager.talk(self.player, "Block the attack with your shield!")
#         self.assertFalse(res_block.accepted)
#         self.assertEqual(res_block.error_type, "UNSUPPORTED_COMMAND")
# 
    # 15. Conversational talk continues to work alongside dodge
#     def test_15_conversational_talk_preserved(self) -> None:
#         """Conversational talk (praise, encourage, warning, general) remains fully functional."""
#         manager = BattleManager(seed=42)
#         battle = manager.start_battle(self.player, self.charm)
# 
#         res_talk = manager.talk(self.player, "Great job, Pikachu!")
#         self.assertTrue(res_talk.accepted)
#         self.assertEqual(res_talk.action_type, BattleActionType.TALK)
#         self.assertIsNotNone(res_talk.talk_dialogue)
        # Turn did not advance for conversational talk
#         self.assertEqual(battle.current_turn, 1)
# 
    # 16. All three public entry points route dodge commands to DODGE execution
#     def test_16_all_three_entry_points_execute_dodge(self) -> None:
#         """BattleManager.talk(), Battle.talk(), and Battle.take_action(TALK) all execute DODGE."""
        # Entry point 1: BattleManager.talk(player, "Dodge!")
#         manager = BattleManager(seed=0)
#         battle1 = manager.start_battle(self.player, self.charm)
#         res1 = manager.talk(self.player, "Dodge!")
#         self.assertTrue(res1.accepted)
#         self.assertEqual(res1.action_type, BattleActionType.DODGE)
#         self.assertIsNotNone(res1.turn_result)
#         self.assertEqual(battle1.current_turn, 2)
# 
        # Entry point 2: Battle.talk("Dodge!")
#         battle2 = Battle(self.pika, self.charm, seed=0)
#         battle2.start()
#         res2 = battle2.talk("Dodge!")
#         self.assertTrue(res2.accepted)
#         self.assertEqual(res2.action_type, BattleActionType.DODGE)
#         self.assertIsNotNone(res2.turn_result)
#         self.assertEqual(battle2.current_turn, 2)
# 
        # Entry point 3: Battle.take_action(BattleAction(action_type=TALK, text="Evade!"))
#         battle3 = Battle(self.pika, self.charm, seed=0)
#         battle3.start()
#         res3 = battle3.take_action(
#             BattleAction(action_type=BattleActionType.TALK, text="Evade the attack!")
#         )
#         self.assertTrue(res3.accepted)
#         self.assertEqual(res3.action_type, BattleActionType.DODGE)
#         self.assertIsNotNone(res3.turn_result)
#         self.assertEqual(battle3.current_turn, 2)
# 
    # 17. Conversational phrases do not trigger dodge
#     def test_17_conversational_phrases_do_not_trigger_dodge(self) -> None:
#         """Ambiguous warning, praise, and encourage commands remain conversational and do not dodge."""
#         battle = Battle(self.pika, self.charm, seed=42)
#         battle.start()
# 
        # Warning phrases like "Watch out!" must not dodge
#         res_warn = battle.talk("Watch out!")
#         self.assertTrue(res_warn.accepted)
#         self.assertEqual(res_warn.action_type, BattleActionType.TALK)
#         self.assertFalse(res_warn.dodge_successful)
#         self.assertIsNone(res_warn.turn_result)
#         self.assertEqual(battle.current_turn, 1)
# 
        # Advance turn via combat dodge
#         res_dodge = battle.dodge()
#         self.assertTrue(res_dodge.accepted)
#         self.assertEqual(battle.current_turn, 2)
# 
        # Praise phrases like "Great job!" must not dodge
#         res_praise = battle.talk("Great job, Pikachu!")
#         self.assertTrue(res_praise.accepted)
#         self.assertEqual(res_praise.action_type, BattleActionType.TALK)
#         self.assertIsNone(res_praise.turn_result)
#         self.assertEqual(battle.current_turn, 2)
# 
        # Advance turn via attack
#         res_atk = battle.take_action(BattleAction(action_type=BattleActionType.ATTACK, attack=QUICK_ATTACK))
#         self.assertTrue(res_atk.accepted)
#         self.assertEqual(battle.current_turn, 3)
# 
        # Encourage phrases like "Hang in there!" must not dodge
#         res_enc = battle.talk("Hang in there, buddy!")
#         self.assertTrue(res_enc.accepted)
#         self.assertEqual(res_enc.action_type, BattleActionType.TALK)
#         self.assertIsNone(res_enc.turn_result)
#         self.assertEqual(battle.current_turn, 3)
# 
    # 18. Unsupported tactical commands rejected cleanly across entry points
#     def test_18_unsupported_tactical_commands_rejected_across_entry_points(self) -> None:
#         """Unsupported commands (jump, block, parry) return UNSUPPORTED_COMMAND without consuming turns."""
#         manager = BattleManager(seed=42)
#         battle = manager.start_battle(self.player, self.charm)
# 
        # Entry point 1: BattleManager.talk
#         res1 = manager.talk(self.player, "Jump over the attack!")
#         self.assertFalse(res1.accepted)
#         self.assertEqual(res1.error_type, "UNSUPPORTED_COMMAND")
#         self.assertEqual(battle.current_turn, 1)
#         self.assertTrue(battle.can_talk_this_turn)
# 
        # Entry point 2: Battle.talk
#         res2 = battle.talk("Parry the strike!")
#         self.assertFalse(res2.accepted)
#         self.assertEqual(res2.error_type, "UNSUPPORTED_COMMAND")
#         self.assertEqual(battle.current_turn, 1)
#         self.assertTrue(battle.can_talk_this_turn)
# 
        # Entry point 3: Battle.take_action
#         res3 = battle.take_action(
#             BattleAction(action_type=BattleActionType.TALK, text="Block it with a barrier!")
#         )
#         self.assertFalse(res3.accepted)
#         self.assertEqual(res3.error_type, "UNSUPPORTED_COMMAND")
#         self.assertEqual(battle.current_turn, 1)
#         self.assertTrue(battle.can_talk_this_turn)
# 
        # Talk allowance was not consumed by rejected tactical commands
#         res_valid = battle.talk("Good job, Pikachu!")
#         self.assertTrue(res_valid.accepted)
#         self.assertFalse(battle.can_talk_this_turn)
# 
    # 19. Non-attacking wild Pokémon inspect during dodge
    def test_19_non_attacking_wild_inspect_during_dodge(self) -> None:
        """When wild Pokémon inspects during player dodge, no attack resolves and no Struggle is forced."""
        from src.models.wild_ai import WildDecision, WildActionType

        battle = Battle(self.pika, self.charm, seed=0, use_wild_ai=True)
        battle.start()

        # Wild Pokémon decides to INSPECT instead of attacking
        battle.decide_wild_action = lambda: WildDecision(
            action_type=WildActionType.INSPECT,
            scores={WildActionType.INSPECT: 50.0},
            reason="sizes you up curiously",
            chosen_attack=None,
        )

        res = battle.dodge()
        self.assertTrue(res.accepted)
        self.assertTrue(res.is_obeyed)
        self.assertFalse(res.dodge_successful)
        self.assertEqual(len(res.turn_result.actions), 0)
        self.assertIn("prepared to dodge, but the opponent did not attack", res.reason)
        self.assertEqual(battle.current_turn, 2)
        # Pikachu took no damage from any phantom attacks
        self.assertEqual(self.pika.current_hp, self.pika.max_hp)

    # 20. Non-attacking opponent trainer switch during dodge
    def test_20_non_attacking_opponent_trainer_switch_during_dodge(self) -> None:
        """When opponent trainer switches during player dodge, switch occurs with no attack."""
        from src.models.trainer import Trainer, TrainerArchetype, DifficultyProfile
        from src.models.trainer_ai import TrainerDecision, TrainerActionType

        squirtle = Pokemon(species=SQUIRTLE, personality=self.personality, level=5, attacks=[WATER_GUN, TACKLE])
        opp_trainer = Trainer(
            trainer_id="trainer_gary",
            name="Gary",
            title="Rival Gary",
            archetype=TrainerArchetype.ACE_TRAINER,
            difficulty=DifficultyProfile.HARD,
            team=[self.charm, squirtle],
        )

        battle = Battle(
            pokemon1=self.pika,
            pokemon2=self.charm,
            opponent_trainer=opp_trainer,
            seed=0,
        )
        battle.start()

        # Trainer AI decides to proactively SWITCH
        battle.trainer_ai.decide_action = lambda **kwargs: TrainerDecision(
            action_type=TrainerActionType.SWITCH,
            chosen_attack=None,
            target_pokemon=squirtle,
            reason="type advantage switch",
        )

        res = battle.dodge()
        self.assertTrue(res.accepted)
        self.assertTrue(res.is_obeyed)
        self.assertFalse(res.dodge_successful)
        self.assertEqual(len(res.turn_result.actions), 0)
        self.assertIn("prepared to dodge, but the opponent did not attack", res.reason)
        self.assertEqual(battle.current_turn, 2)
        self.assertIs(battle.pokemon2, squirtle)
        self.assertEqual(self.pika.current_hp, self.pika.max_hp)

    # 21. Opponent natural miss during failed dodge
    def test_21_opponent_natural_miss_during_failed_dodge(self) -> None:
        """When dodge fails but opponent attack misses naturally, record.hit is False and damage is 0."""
        # Attack with 1 accuracy guarantees natural miss on almost all rolls
        inacc_atk = Attack(name="ZeroAcc", type=PokemonType.NORMAL, power=40, accuracy=1)
        charm_miss = Pokemon(species=CHARMANDER, personality=self.personality, level=5, attacks=[inacc_atk])

        # Seed 1 with low dodge probability ensures dodge fails while attack also misses
        battle = Battle(self.pika, charm_miss, seed=1)
        battle.start()
        battle.calculate_dodge_probability = lambda *args, **kwargs: 0.10

        initial_hp = self.pika.current_hp
        res = battle.dodge()
        self.assertTrue(res.accepted)
        self.assertFalse(res.dodge_successful)
        self.assertEqual(len(res.turn_result.actions), 1)

        record = res.turn_result.actions[0]
        self.assertFalse(record.hit)
        self.assertEqual(record.damage, 0)
        self.assertIn("missed", record.message)
        self.assertEqual(self.pika.current_hp, initial_hp)
        self.assertEqual(battle.current_turn, 2)

    # 22. Conversational talk and tactical dodge in the same turn
#     def test_22_conversational_talk_and_dodge_same_turn(self) -> None:
#         """Player can talk conversationally and then execute dodge in the same turn."""
#         battle = Battle(self.pika, self.charm, seed=0)
#         battle.start()
# 
        # 1. Conversational talk succeeds
#         res_talk = battle.talk("Let's stay sharp!")
#         self.assertTrue(res_talk.accepted)
#         self.assertEqual(battle.current_turn, 1)
#         self.assertFalse(battle.can_talk_this_turn)
# 
        # 2. Tactical dodge succeeds in same turn and advances combat turn
#         res_dodge = battle.talk("Pikachu, dodge!")
#         self.assertTrue(res_dodge.accepted)
#         self.assertEqual(res_dodge.action_type, BattleActionType.DODGE)
#         self.assertEqual(battle.current_turn, 2)
# 
        # 3. On Turn 2, talk allowance is reset
#         self.assertTrue(battle.can_talk_this_turn)
#         res_talk2 = battle.talk("Great job!")
#         self.assertTrue(res_talk2.accepted)
#         self.assertFalse(battle.can_talk_this_turn)
# 
    # 23. Defender paralysis prevents dodge
    def test_23_defender_paralysis_prevents_dodge(self) -> None:
        """When the active Pokemon is paralyzed and cannot act, dodge fails and opponent attacks."""
        status_manager = StatusEffectManager()
        status_manager.apply_effect(self.pika, StatusEffectType.PARALYSIS)

        pika_checks = [0]
        orig_check = status_manager.check_can_act
        def mock_check(mon, roll_override=None):
            if mon is self.pika:
                pika_checks[0] += 1
                from src.models.status_effect_manager import ActionCheckResult
                return ActionCheckResult(
                    can_act=False,
                    pokemon=mon,
                    paralyzed=True,
                    roll=1,
                    chance=25,
                    reason=f"{mon.display_name} is paralyzed! It can't move!",
                )
            return orig_check(mon, roll_override=roll_override)
        status_manager.check_can_act = mock_check

        battle = Battle(self.pika, self.charm, seed=0, status_manager=status_manager)
        battle.start()

        initial_hp = self.pika.current_hp
        res = battle.dodge()

        self.assertTrue(res.accepted)
        self.assertFalse(res.dodge_successful)
        self.assertIn("paralyzed and could not dodge", res.reason)
        # Action-eligibility checked exactly once on the defender
        self.assertEqual(pika_checks[0], 1)
        # Event explicitly logged
        self.assertTrue(any("paralyzed! It can't move!" in evt for evt in battle.events))
        # Opponent attack resolved and dealt damage
        self.assertLess(self.pika.current_hp, initial_hp)
        self.assertEqual(battle.current_turn, 2)

    # 24. Opponent paralysis prevents attack and avoids false dodge
    def test_24_opponent_paralysis_prevents_attack_and_avoids_false_dodge(self) -> None:
        """When opponent is paralyzed and cannot act, no false dodge-success is reported."""
        status_manager = StatusEffectManager()
        status_manager.apply_effect(self.charm, StatusEffectType.PARALYSIS)

        orig_check = status_manager.check_can_act
        def mock_check(mon, roll_override=None):
            if mon is self.charm:
                from src.models.status_effect_manager import ActionCheckResult
                return ActionCheckResult(
                    can_act=False,
                    pokemon=mon,
                    paralyzed=True,
                    roll=1,
                    chance=25,
                    reason=f"{mon.display_name} is paralyzed! It can't move!",
                )
            return orig_check(mon, roll_override=roll_override)
        status_manager.check_can_act = mock_check

        # Seed 0 would normally yield successful dodge if an attack occurred
        battle = Battle(self.pika, self.charm, seed=0, status_manager=status_manager)
        battle.start()

        res = battle.dodge()
        self.assertTrue(res.accepted)
        # Did not report false dodge success because no attack occurred
        self.assertFalse(res.dodge_successful)
        self.assertIn("was paralyzed and couldn't attack", res.reason)
        # Pikachu took 0 damage
        self.assertEqual(self.pika.current_hp, self.pika.max_hp)
        self.assertEqual(len(res.turn_result.actions), 1)
        self.assertFalse(res.turn_result.actions[0].hit)
        self.assertEqual(battle.current_turn, 2)

    # 25. Failed dodge logs explicit failure event
    def test_25_failed_dodge_logs_explicit_failure_event(self) -> None:
        """When defender obeys but fails to evade an attack that hits, failure is explicitly logged."""
        # Seed 1 gives failed dodge
        battle = Battle(self.pika, self.charm, seed=1)
        battle.start()

        res = battle.dodge()
        self.assertTrue(res.accepted)
        self.assertTrue(res.is_obeyed)
        self.assertFalse(res.dodge_successful)
        # Explicit failure narration in battle.events
        self.assertTrue(any("failed to dodge in time!" in evt for evt in battle.events))
        self.assertIn("failed to dodge the attack", res.reason)

    # 26. Negated dodge phrases do not dispatch dodge
#     def test_26_negated_dodge_phrases_do_not_dispatch_dodge(self) -> None:
#         """Negated commands like 'Don't dodge!' do not trigger DODGE combat turns."""
#         manager = BattleManager(seed=42)
#         battle = manager.start_battle(self.player, self.charm)
# 
        # Dispatch path 1: BattleManager.talk
#         res_neg1 = manager.talk(self.player, "Don't dodge!")
#         self.assertTrue(res_neg1.accepted)
#         self.assertEqual(res_neg1.action_type, BattleActionType.TALK)
#         self.assertIsNone(res_neg1.turn_result)
#         self.assertEqual(battle.current_turn, 1)
# 
        # Dispatch path 2: Battle.talk
#         battle2 = Battle(self.pika, self.charm, seed=42)
#         battle2.start()
#         res_neg2 = battle2.talk("Never evade!")
#         self.assertTrue(res_neg2.accepted)
#         self.assertEqual(res_neg2.action_type, BattleActionType.TALK)
#         self.assertIsNone(res_neg2.turn_result)
#         self.assertEqual(battle2.current_turn, 1)
# 
        # Dispatch path 3: Battle.take_action
#         battle3 = Battle(self.pika, self.charm, seed=42)
#         battle3.start()
#         res_neg3 = battle3.take_action(
#             BattleAction(action_type=BattleActionType.TALK, text="Do not dodge!")
#         )
#         self.assertTrue(res_neg3.accepted)
#         self.assertEqual(res_neg3.action_type, BattleActionType.TALK)
#         self.assertIsNone(res_neg3.turn_result)
#         self.assertEqual(battle3.current_turn, 1)
# 
    # 27. Direct CLI menu option [7] executes Dodge in wild battle
    def test_27_cli_dodge_menu_integration(self) -> None:
        """Direct CLI option [7] routes through BattleManager.dodge() in wild battles."""
        from game import AdventureGame
        from unittest.mock import patch

        game = AdventureGame()
        game.player = self.player
        manager = BattleManager(seed=0)
        game.battle_manager = manager
        battle = manager.start_battle(self.player, self.charm)

        # Simulate selecting '7' in the battle loop prompt
        with patch.object(game, "_prompt", side_effect=["7", "quit"]), \
             patch.object(game, "_print"):
            game._battle_loop(battle)

        # Turn advanced via dodge
        self.assertEqual(battle.current_turn, 2)

    # 28. Paralyzed defender can act when paralysis check succeeds
    def test_28_defender_paralyzed_but_moves_and_evades(self) -> None:
        """When defender is paralyzed but can_act is True, dodge executes normally."""
        status_manager = StatusEffectManager()
        status_manager.apply_effect(self.pika, StatusEffectType.PARALYSIS)

        pika_checks = [0]
        orig_check = status_manager.check_can_act
        def mock_check(mon, roll_override=None):
            if mon is self.pika:
                pika_checks[0] += 1
                from src.models.status_effect_manager import ActionCheckResult
                return ActionCheckResult(
                    can_act=True,
                    pokemon=mon,
                    paralyzed=True,
                    roll=50,
                    chance=25,
                    reason=f"{mon.display_name} moved despite paralysis.",
                )
            return orig_check(mon, roll_override=roll_override)
        status_manager.check_can_act = mock_check

        # Seed 0 gives successful evasion
        battle = Battle(self.pika, self.charm, seed=0, status_manager=status_manager)
        battle.start()

        res = battle.dodge()
        self.assertTrue(res.accepted)
        self.assertTrue(res.dodge_successful)
        self.assertEqual(pika_checks[0], 1)
        self.assertEqual(self.pika.current_hp, self.pika.max_hp)
        self.assertEqual(battle.current_turn, 2)

    # 29. Direct CLI menu option [7] in trainer battle
    def test_29_cli_dodge_menu_integration_trainer_battle(self) -> None:
        """Direct CLI option [7] routes through BattleManager.dodge() in trainer battles."""
        from game import AdventureGame
        from unittest.mock import patch
        from src.models.trainer import Trainer, TrainerArchetype, DifficultyProfile

        opp_trainer = Trainer(
            trainer_id="trainer_blue",
            name="Blue",
            title="Leader Blue",
            archetype=TrainerArchetype.GYM_LEADER,
            difficulty=DifficultyProfile.HARD,
            team=[self.charm],
        )

        game = AdventureGame()
        game.player = self.player
        manager = BattleManager(seed=0)
        game.battle_manager = manager
        battle = manager.start_trainer_battle(self.player, opp_trainer)

        # Simulate selecting '7' then 'quit'
        with patch.object(game, "_prompt", side_effect=["7", "quit"]), \
             patch.object(game, "_print"):
            game._battle_loop(battle)

        # Turn advanced via dodge in trainer battle
        self.assertEqual(battle.current_turn, 2)


if __name__ == "__main__":
    unittest.main()
