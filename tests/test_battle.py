"""
Unit tests for the Battle engine.

Tests verify:
6. Accuracy misses cause zero damage.
7. A battle cannot resolve before starting.
8. A battle cannot continue after it ends.
9. Only known attacks can be selected.
10. Faster Pokémon acts first.
11. Equal-Speed tie-breaking is testable and reproducible.
12. A knocked-out Pokémon cannot retaliate.
13. HP never becomes negative.
14. Battle state updates correctly on victory, defeat, or draw.
15. Events/results accurately report damage, hit status, and remaining HP.
16. Both Pokémon's attacks can be used if the battle continues.
"""
import random
import unittest

from src.models.personality import Personality
from src.models.pokemon import Pokemon
from src.models.species import PokemonSpecies
from src.models.pokemon_type import PokemonType
from src.models.attack import Attack
from src.models.battle_state import BattleState
from src.models.battle import Battle, BattleActionRecord, TurnResult
from src.data.species import PIKACHU, CHARMANDER, SQUIRTLE
from src.data.attacks import THUNDER_SHOCK, QUICK_ATTACK, EMBER, SCRATCH, TACKLE, WATER_GUN


class TestBattle(unittest.TestCase):
    """Test suite covering turn order, battle lifecycle, accuracy, and resolution."""

    def setUp(self) -> None:
        self.default_personality = Personality(
            aggression=50,
            curiosity=50,
            fear=50,
            sociability=50,
            loyalty=50,
            confidence=50,
        )
        self.pikachu = Pokemon(
            species=PIKACHU,
            personality=self.default_personality,
            level=5,
            attacks=[THUNDER_SHOCK, QUICK_ATTACK],
        )
        self.charmander = Pokemon(
            species=CHARMANDER,
            personality=self.default_personality,
            level=5,
            attacks=[EMBER, SCRATCH],
        )

    # 6. Accuracy misses cause zero damage.
    def test_06_accuracy_miss_causes_zero_damage(self) -> None:
        # Move with 0 accuracy guarantees a miss
        miss_move = Attack(name="Blind Strike", type=PokemonType.NORMAL, power=50, accuracy=0)
        pika_custom = Pokemon(
            species=PIKACHU,
            personality=self.default_personality,
            level=5,
            attacks=[miss_move],
        )
        battle = Battle(pika_custom, self.charmander, seed=42)
        battle.start()

        turn_res = battle.resolve_turn(attack1=miss_move, attack2=SCRATCH)
        first_action = turn_res.actions[0]  # Pikachu is faster (SPD 90 vs 65)

        self.assertFalse(first_action.hit)
        self.assertEqual(first_action.damage, 0)
        self.assertIn("missed", first_action.message)
        self.assertEqual(self.charmander.current_hp, self.charmander.max_hp)

    # 7. A battle cannot resolve before starting.
    def test_07_battle_cannot_resolve_before_starting(self) -> None:
        battle = Battle(self.pikachu, self.charmander)
        self.assertEqual(battle.state, BattleState.NOT_STARTED)

        with self.assertRaises(RuntimeError):
            battle.resolve_turn(attack1=THUNDER_SHOCK, attack2=SCRATCH)

    # 8. A battle cannot continue after it ends.
    def test_08_battle_cannot_continue_after_it_ends(self) -> None:
        battle = Battle(self.pikachu, self.charmander, seed=42)
        battle.start()

        # Artificially set Charmander HP to 1 so Pikachu knocks it out in one hit
        self.charmander.current_hp = 1
        turn_res = battle.resolve_turn(attack1=THUNDER_SHOCK, attack2=SCRATCH)

        self.assertEqual(turn_res.battle_state, BattleState.VICTORY)
        self.assertTrue(battle.state.is_terminal())

        # Attempting to resolve another turn must be rejected
        with self.assertRaises(RuntimeError):
            battle.resolve_turn(attack1=THUNDER_SHOCK, attack2=SCRATCH)

    # 9. Only known attacks can be selected.
    def test_09_only_known_attacks_can_be_selected(self) -> None:
        battle = Battle(self.pikachu, self.charmander)
        battle.start()

        # Pikachu does not know Water Gun
        with self.assertRaises(ValueError):
            battle.resolve_turn(attack1=WATER_GUN, attack2=EMBER)

    # 10. Faster Pokémon acts first.
    def test_10_faster_pokemon_acts_first(self) -> None:
        # Pikachu SPD: 90, Charmander SPD: 65
        battle = Battle(self.pikachu, self.charmander, seed=42)
        battle.start()

        turn_res = battle.resolve_turn(attack1=THUNDER_SHOCK, attack2=EMBER)
        self.assertEqual(turn_res.actions[0].attacker, self.pikachu)
        self.assertEqual(turn_res.actions[1].attacker, self.charmander)

    # 11. Equal-Speed tie-breaking is testable and reproducible.
    def test_11_equal_speed_tie_breaker_reproducible(self) -> None:
        pika1 = Pokemon(species=PIKACHU, personality=self.default_personality, attacks=[THUNDER_SHOCK])
        pika2 = Pokemon(species=PIKACHU, personality=self.default_personality, attacks=[THUNDER_SHOCK])

        # Test with seed A
        battle_a = Battle(pika1, pika2, seed=123)
        battle_a.start()
        turn_a = battle_a.resolve_turn(attack1=THUNDER_SHOCK, attack2=THUNDER_SHOCK)

        # Test again with same seed A on separate instances
        pika1_copy = Pokemon(species=PIKACHU, personality=self.default_personality, attacks=[THUNDER_SHOCK])
        pika2_copy = Pokemon(species=PIKACHU, personality=self.default_personality, attacks=[THUNDER_SHOCK])
        battle_b = Battle(pika1_copy, pika2_copy, seed=123)
        battle_b.start()
        turn_b = battle_b.resolve_turn(attack1=THUNDER_SHOCK, attack2=THUNDER_SHOCK)

        # Confirm that the tie breaker chose the exact same participant position
        p1_first_a = turn_a.actions[0].attacker is battle_a.pokemon1
        p1_first_b = turn_b.actions[0].attacker is battle_b.pokemon1
        self.assertEqual(p1_first_a, p1_first_b)

    # 12. A knocked-out Pokémon cannot retaliate.
    def test_12_knocked_out_pokemon_cannot_retaliate(self) -> None:
        battle = Battle(self.pikachu, self.charmander, seed=42)
        battle.start()

        # Charmander has only 1 HP remaining
        self.charmander.current_hp = 1
        turn_res = battle.resolve_turn(attack1=THUNDER_SHOCK, attack2=SCRATCH)

        # Pikachu knocked out Charmander first; Charmander does not retaliate
        self.assertEqual(len(turn_res.actions), 1)
        self.assertEqual(turn_res.actions[0].attacker, self.pikachu)
        self.assertTrue(self.charmander.is_fainted)
        self.assertEqual(battle.state, BattleState.VICTORY)

    # 13. HP never becomes negative.
    def test_13_hp_never_becomes_negative(self) -> None:
        self.charmander.current_hp = 5
        self.charmander.take_damage(100)
        self.assertEqual(self.charmander.current_hp, 0)
        self.assertTrue(self.charmander.is_fainted)

    # 14. Battle state updates correctly on victory, defeat, or draw.
    def test_14_battle_state_updates_correctly(self) -> None:
        # Victory (pokemon2 faints) -> VICTORY from battle perspective, winner is pokemon1
        battle_vic = Battle(self.pikachu, self.charmander, seed=1)
        battle_vic.start()
        self.charmander.current_hp = 1
        turn_vic = battle_vic.resolve_turn(attack1=THUNDER_SHOCK, attack2=SCRATCH)
        self.assertEqual(battle_vic.state, BattleState.VICTORY)
        self.assertEqual(battle_vic.winner, self.pikachu)
        self.assertEqual(battle_vic.loser, self.charmander)
        self.assertEqual(turn_vic.battle_state, BattleState.VICTORY)
        self.assertEqual(turn_vic.winner, self.pikachu)
        self.assertEqual(turn_vic.loser, self.charmander)

        # Defeat (pokemon1 faints) -> DEFEAT from battle perspective, winner is pokemon2
        slow_squirtle = Pokemon(species=SQUIRTLE, personality=self.default_personality, level=5, attacks=[WATER_GUN])
        fast_pikachu = Pokemon(species=PIKACHU, personality=self.default_personality, level=5, attacks=[THUNDER_SHOCK])
        battle_def = Battle(slow_squirtle, fast_pikachu, seed=1)
        battle_def.start()
        slow_squirtle.current_hp = 1  # Fast Pikachu knocks it out
        turn_def = battle_def.resolve_turn(attack1=WATER_GUN, attack2=THUNDER_SHOCK)
        self.assertEqual(battle_def.state, BattleState.DEFEAT)
        self.assertEqual(battle_def.winner, fast_pikachu)
        self.assertEqual(battle_def.loser, slow_squirtle)
        self.assertEqual(turn_def.battle_state, BattleState.DEFEAT)
        self.assertEqual(turn_def.winner, fast_pikachu)
        self.assertEqual(turn_def.loser, slow_squirtle)

        # Draw (both pokemon faint) -> DRAW, winner and loser are None
        pika_draw = Pokemon(species=PIKACHU, personality=self.default_personality, level=5, attacks=[THUNDER_SHOCK])
        char_draw = Pokemon(species=CHARMANDER, personality=self.default_personality, level=5, attacks=[EMBER])
        battle_draw = Battle(pika_draw, char_draw, seed=1)
        battle_draw.start()
        pika_draw.take_damage(pika_draw.max_hp)
        char_draw.take_damage(char_draw.max_hp)
        battle_draw._update_terminal_state()
        self.assertEqual(battle_draw.state, BattleState.DRAW)
        self.assertIsNone(battle_draw.winner)
        self.assertIsNone(battle_draw.loser)
        self.assertIn("The battle ended in a draw!", battle_draw.events)

    # 15. Events/results accurately report damage, hit status, and remaining HP.
    def test_15_events_accurately_report_details(self) -> None:
        battle = Battle(self.pikachu, self.charmander, seed=42)
        battle.start()

        initial_hp = self.charmander.current_hp
        turn_res = battle.resolve_turn(attack1=THUNDER_SHOCK, attack2=SCRATCH)
        action1 = turn_res.actions[0]

        self.assertTrue(action1.hit)
        self.assertGreater(action1.damage, 0)
        self.assertEqual(action1.defender_hp_remaining, initial_hp - action1.damage)
        self.assertEqual(action1.type_effectiveness, 1.0)
        self.assertGreater(len(battle.events), 0)

    # 16. Both Pokémon's attacks can be used if the battle continues.
    def test_16_both_pokemon_attacks_used_if_battle_continues(self) -> None:
        battle = Battle(self.pikachu, self.charmander, seed=42)
        battle.start()

        turn_res1 = battle.resolve_turn(attack1=THUNDER_SHOCK, attack2=EMBER)
        # Both survived turn 1
        self.assertEqual(len(turn_res1.actions), 2)
        self.assertEqual(battle.state, BattleState.IN_PROGRESS)
        self.assertEqual(battle.current_turn, 2)

        # Both can act again on turn 2
        turn_res2 = battle.resolve_turn(attack1=QUICK_ATTACK, attack2=SCRATCH)
        self.assertEqual(len(turn_res2.actions), 2)

    # 17. Invalid moves and attack selection validation
    def test_17_invalid_moves_and_participant_validation(self) -> None:
        battle = Battle(self.pikachu, self.charmander)
        battle.start()

        # Non-Attack type passed to select_attack
        with self.assertRaises(TypeError):
            battle.select_attack(self.pikachu, "Thunder Shock")  # type: ignore[arg-type]

        # Non-Attack type passed to resolve_turn
        with self.assertRaises(TypeError):
            battle.resolve_turn(attack1="Thunder Shock", attack2=SCRATCH)  # type: ignore[arg-type]

        # Pokemon not part of the battle
        outsider = Pokemon(species=SQUIRTLE, personality=self.default_personality, attacks=[WATER_GUN])
        with self.assertRaises(ValueError):
            battle.select_attack(outsider, WATER_GUN)

        # Fainted Pokemon cannot select an attack
        self.pikachu.take_damage(self.pikachu.max_hp)
        with self.assertRaises(ValueError):
            battle.select_attack(self.pikachu, THUNDER_SHOCK)

        # Restoring Pikachu HP for incomplete selection test
        self.pikachu.heal(self.pikachu.max_hp)
        # Only 1 Pokemon selected attack
        battle.select_attack(self.pikachu, THUNDER_SHOCK)
        with self.assertRaises(ValueError):
            battle.resolve_turn()

    # 18. Actions before starting and participant initialization constraints
    def test_18_actions_before_starting_and_init_constraints(self) -> None:
        # Cannot battle same instance or same unique ID
        with self.assertRaises(ValueError):
            Battle(self.pikachu, self.pikachu)

        # Non-Pokemon types
        with self.assertRaises(TypeError):
            Battle("Pikachu", self.charmander)  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            Battle(self.pikachu, "Charmander")  # type: ignore[arg-type]

        battle = Battle(self.pikachu, self.charmander)
        # select_attack before starting raises RuntimeError
        with self.assertRaises(RuntimeError):
            battle.select_attack(self.pikachu, THUNDER_SHOCK)

        # Cannot start battle if pokemon1 has fainted
        pika_fainted = Pokemon(species=PIKACHU, personality=self.default_personality)
        pika_fainted.take_damage(pika_fainted.max_hp)
        battle_fainted1 = Battle(pika_fainted, self.charmander)
        with self.assertRaises(ValueError):
            battle_fainted1.start()

        # Cannot start battle if pokemon2 has fainted
        char_fainted = Pokemon(species=CHARMANDER, personality=self.default_personality)
        char_fainted.take_damage(char_fainted.max_hp)
        battle_fainted2 = Battle(self.pikachu, char_fainted)
        with self.assertRaises(ValueError):
            battle_fainted2.start()

        # Cannot start battle twice
        battle.start()
        with self.assertRaises(RuntimeError):
            battle.start()

    # 19. Actions after battle ends are strictly rejected
    def test_19_actions_after_battle_ends_rejected(self) -> None:
        battle = Battle(self.pikachu, self.charmander, seed=42)
        battle.start()
        self.charmander.current_hp = 1
        battle.resolve_turn(attack1=THUNDER_SHOCK, attack2=SCRATCH)

        self.assertTrue(battle.state.is_terminal())
        # resolve_turn after conclusion
        with self.assertRaises(RuntimeError):
            battle.resolve_turn(attack1=THUNDER_SHOCK, attack2=SCRATCH)

        # select_attack after conclusion
        with self.assertRaises(RuntimeError):
            battle.select_attack(self.pikachu, THUNDER_SHOCK)

        # start() after conclusion
        with self.assertRaises(RuntimeError):
            battle.start()

    # 20. Event log contents follow exact expected sequence
    def test_20_event_log_contents_comprehensive(self) -> None:
        battle = Battle(self.pikachu, self.charmander, seed=42)
        battle.start()

        self.assertEqual(battle.events[0], "Battle started between Pikachu and Charmander!")

        # Turn 1: normal hit
        turn_res = battle.resolve_turn(attack1=THUNDER_SHOCK, attack2=SCRATCH)
        self.assertIn("[Turn 1] Pikachu used Thunder Shock! Hit for", battle.events[1])
        self.assertIn(f"Charmander HP: {self.charmander.current_hp}/{self.charmander.max_hp}", battle.events[1])
        self.assertIn("[Turn 1] Charmander used Scratch! Hit for", battle.events[2])

        # Knockout turn
        self.charmander.current_hp = 1
        battle.resolve_turn(attack1=THUNDER_SHOCK, attack2=SCRATCH)
        self.assertIn("Charmander fainted!", battle.events)
        self.assertIn("Pikachu won the battle!", battle.events)
        self.assertEqual(len(battle.turn_history), 2)

    # 21. Reproducibility with injected random generator
    def test_21_reproducibility_with_injected_rng(self) -> None:
        # Identical seeds must produce identical damage and accuracy rolls
        rng1 = random.Random(999)
        battle1 = Battle(
            Pokemon(species=PIKACHU, personality=self.default_personality, attacks=[THUNDER_SHOCK]),
            Pokemon(species=CHARMANDER, personality=self.default_personality, attacks=[SCRATCH]),
            rng=rng1,
        )
        battle1.start()
        turn1 = battle1.resolve_turn(attack1=THUNDER_SHOCK, attack2=SCRATCH)

        rng2 = random.Random(999)
        battle2 = Battle(
            Pokemon(species=PIKACHU, personality=self.default_personality, attacks=[THUNDER_SHOCK]),
            Pokemon(species=CHARMANDER, personality=self.default_personality, attacks=[SCRATCH]),
            rng=rng2,
        )
        battle2.start()
        turn2 = battle2.resolve_turn(attack1=THUNDER_SHOCK, attack2=SCRATCH)

        self.assertEqual(turn1.actions[0].damage, turn2.actions[0].damage)
        self.assertEqual(turn1.actions[0].hit, turn2.actions[0].hit)
        self.assertEqual(turn1.actions[1].damage, turn2.actions[1].damage)
        self.assertEqual(turn1.actions[1].hit, turn2.actions[1].hit)

        # Disabling random damage variance produces exact base damage without consuming RNG
        battle_no_rand = Battle(
            Pokemon(species=PIKACHU, personality=self.default_personality, attacks=[THUNDER_SHOCK]),
            Pokemon(species=CHARMANDER, personality=self.default_personality, attacks=[SCRATCH]),
            use_random_damage=False,
            seed=42,
        )
        battle_no_rand.start()
        turn_no_rand = battle_no_rand.resolve_turn(attack1=THUNDER_SHOCK, attack2=SCRATCH)
        # Verify base damage factor is 1.0 (deterministic)
        self.assertTrue(turn_no_rand.actions[0].hit)
        self.assertGreater(turn_no_rand.actions[0].damage, 0)

    # 22. Critical hit records and message
    def test_22_critical_hit_records_and_message(self) -> None:
        """Critical hits are reflected in BattleActionRecord.is_critical and attack message."""
        class MockCritRng:
            def randint(self, a, b):
                return 1  # 100% accuracy hit
            def random(self):
                return 0.001  # Guaranteed critical hit
            def uniform(self, a, b):
                return 1.0

        pika = Pokemon(species=PIKACHU, personality=self.default_personality, attacks=[THUNDER_SHOCK], bond=50)
        charm = Pokemon(species=CHARMANDER, personality=self.default_personality, attacks=[SCRATCH], bond=0)
        battle = Battle(pika, charm, rng=MockCritRng())
        battle.start()
        turn = battle.resolve_turn(attack1=THUNDER_SHOCK, attack2=SCRATCH)
        action0 = turn.actions[0]
        self.assertTrue(action0.is_critical)
        self.assertIn("A critical hit!", action0.message)


if __name__ == "__main__":
    unittest.main()
