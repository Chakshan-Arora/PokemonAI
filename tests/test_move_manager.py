"""
Unit tests for MoveManager: attack learning, forgetting, replacing, and move limit enforcement.
"""
import unittest

from src.models.pokemon import Pokemon, MAX_KNOWN_MOVES
from src.models.attack import Attack
from src.models.pokemon_type import PokemonType
from src.models.personality import Personality
from src.models.battle import Battle
from src.data.species import PIKACHU, CHARMANDER, SQUIRTLE
from src.data.attacks import (
    TACKLE,
    QUICK_ATTACK,
    SCRATCH,
    THUNDER_SHOCK,
    THUNDERBOLT,
    EMBER,
    FLAMETHROWER,
    WATER_GUN,
    HYDRO_PUMP,
)
from src.models.move_manager import (
    MoveManager,
    MoveLearnResult,
    MoveForgetResult,
    MoveReplaceResult,
    DEFAULT_MAX_MOVES,
)


class TestMoveManager(unittest.TestCase):
    """Test suite for MoveManager operations on Pokemon instances."""

    def setUp(self) -> None:
        self.manager = MoveManager()
        self.personality = Personality(aggression=50, curiosity=50, fear=50, sociability=50, loyalty=50, confidence=50)

    def _create_pokemon(self, species=PIKACHU, attacks=None) -> Pokemon:
        return Pokemon(
            species=species,
            level=5,
            personality=self.personality,
            attacks=attacks if attacks is not None else [],
        )

    def test_01_learn_valid_attack(self) -> None:
        """A Pokemon with available move slots successfully learns a valid new attack."""
        pkmn = self._create_pokemon(attacks=[THUNDER_SHOCK])
        result = self.manager.learn_attack(pkmn, QUICK_ATTACK)

        self.assertTrue(result.success)
        self.assertIs(result.pokemon, pkmn)
        self.assertIs(result.attack, QUICK_ATTACK)
        self.assertFalse(result.move_limit_reached)
        self.assertIn(QUICK_ATTACK, pkmn.attacks)
        self.assertEqual(len(pkmn.attacks), 2)
        self.assertTrue(self.manager.knows_attack(pkmn, QUICK_ATTACK))
        self.assertTrue(self.manager.knows_attack(pkmn, "Quick Attack"))

    def test_02_duplicate_attack_rejection(self) -> None:
        """A Pokemon cannot learn an attack it already knows."""
        pkmn = self._create_pokemon(attacks=[THUNDER_SHOCK])
        result = self.manager.learn_attack(pkmn, THUNDER_SHOCK)

        self.assertFalse(result.success)
        self.assertFalse(result.move_limit_reached)
        self.assertIn("already knows", result.reason)
        self.assertEqual(len(pkmn.attacks), 1)

    def test_03_forget_known_attack_by_instance(self) -> None:
        """A Pokemon can forget an attack it currently knows by Attack instance."""
        pkmn = self._create_pokemon(attacks=[THUNDER_SHOCK, QUICK_ATTACK])
        result = self.manager.forget_attack(pkmn, THUNDER_SHOCK)

        self.assertTrue(result.success)
        self.assertIs(result.attack, THUNDER_SHOCK)
        self.assertNotIn(THUNDER_SHOCK, pkmn.attacks)
        self.assertEqual(len(pkmn.attacks), 1)
        self.assertIn(QUICK_ATTACK, pkmn.attacks)

    def test_04_forget_known_attack_by_name(self) -> None:
        """A Pokemon can forget an attack it currently knows specified by string name."""
        pkmn = self._create_pokemon(attacks=[THUNDER_SHOCK, QUICK_ATTACK])
        result = self.manager.forget_attack(pkmn, "thunder shock")

        self.assertTrue(result.success)
        self.assertEqual(result.attack.name, "Thunder Shock")
        self.assertNotIn(THUNDER_SHOCK, pkmn.attacks)
        self.assertEqual(len(pkmn.attacks), 1)

    def test_05_reject_forget_for_unknown_attack(self) -> None:
        """Attempting to forget an attack the Pokemon does not know fails cleanly."""
        pkmn = self._create_pokemon(attacks=[THUNDER_SHOCK])
        result = self.manager.forget_attack(pkmn, HYDRO_PUMP)

        self.assertFalse(result.success)
        self.assertIn("does not know", result.reason)
        self.assertEqual(len(pkmn.attacks), 1)
        self.assertIn(THUNDER_SHOCK, pkmn.attacks)

    def test_06_four_move_limit_enforced_on_learn(self) -> None:
        """When a Pokemon already knows 4 moves, learn_attack fails with move_limit_reached=True."""
        pkmn = self._create_pokemon(attacks=[THUNDER_SHOCK, QUICK_ATTACK, TACKLE, THUNDERBOLT])
        self.assertEqual(len(pkmn.attacks), 4)

        result = self.manager.learn_attack(pkmn, EMBER)
        self.assertFalse(result.success)
        self.assertTrue(result.move_limit_reached)
        self.assertIn("reached the move limit", result.reason)
        self.assertEqual(len(pkmn.attacks), 4)
        self.assertNotIn(EMBER, pkmn.attacks)

    def test_07_replace_attack_success(self) -> None:
        """Replacing a known attack with a new attack succeeds atomically."""
        pkmn = self._create_pokemon(attacks=[THUNDER_SHOCK, QUICK_ATTACK, TACKLE, THUNDERBOLT])
        result = self.manager.replace_attack(pkmn, TACKLE, EMBER)

        self.assertTrue(result.success)
        self.assertIs(result.old_attack, TACKLE)
        self.assertIs(result.new_attack, EMBER)
        self.assertNotIn(TACKLE, pkmn.attacks)
        self.assertIn(EMBER, pkmn.attacks)
        self.assertEqual(len(pkmn.attacks), 4)

    def test_08_replace_attack_by_name(self) -> None:
        """Replacing an attack using string name for old_attack succeeds."""
        pkmn = self._create_pokemon(attacks=[THUNDER_SHOCK, QUICK_ATTACK])
        result = self.manager.replace_attack(pkmn, "Quick Attack", FLAMETHROWER)

        self.assertTrue(result.success)
        self.assertNotIn(QUICK_ATTACK, pkmn.attacks)
        self.assertIn(FLAMETHROWER, pkmn.attacks)
        self.assertEqual(len(pkmn.attacks), 2)

    def test_09_replace_attack_failure_preserves_loadout_when_old_not_found(self) -> None:
        """If the old attack is not known, replacement fails and existing moves are untouched."""
        original_moves = [THUNDER_SHOCK, QUICK_ATTACK]
        pkmn = self._create_pokemon(attacks=list(original_moves))

        result = self.manager.replace_attack(pkmn, HYDRO_PUMP, EMBER)
        self.assertFalse(result.success)
        self.assertIn("does not know", result.reason)
        self.assertEqual(pkmn.attacks, original_moves)

    def test_10_replace_attack_failure_preserves_loadout_when_new_already_known(self) -> None:
        """If the new attack is already known, replacement fails and existing moves are untouched."""
        original_moves = [THUNDER_SHOCK, QUICK_ATTACK]
        pkmn = self._create_pokemon(attacks=list(original_moves))

        result = self.manager.replace_attack(pkmn, THUNDER_SHOCK, QUICK_ATTACK)
        self.assertFalse(result.success)
        self.assertIn("already knows", result.reason)
        self.assertEqual(pkmn.attacks, original_moves)

    def test_11_instance_isolation_between_same_species(self) -> None:
        """Modifying attacks on one Pokemon instance does not affect another of the same species."""
        pika_a = self._create_pokemon(species=PIKACHU, attacks=[THUNDER_SHOCK])
        pika_b = self._create_pokemon(species=PIKACHU, attacks=[THUNDER_SHOCK])

        self.manager.learn_attack(pika_a, QUICK_ATTACK)

        self.assertIn(QUICK_ATTACK, pika_a.attacks)
        self.assertNotIn(QUICK_ATTACK, pika_b.attacks)
        self.assertEqual(len(pika_a.attacks), 2)
        self.assertEqual(len(pika_b.attacks), 1)

    def test_12_get_known_attacks_returns_independent_list(self) -> None:
        """get_known_attacks returns a distinct list copy so mutating it does not corrupt the Pokemon."""
        pkmn = self._create_pokemon(attacks=[THUNDER_SHOCK])
        known = self.manager.get_known_attacks(pkmn)
        known.append(HYDRO_PUMP)

        self.assertNotIn(HYDRO_PUMP, pkmn.attacks)
        self.assertEqual(len(pkmn.attacks), 1)

    def test_13_can_learn_evaluation(self) -> None:
        """can_learn reports accurate status and reasons."""
        pkmn = self._create_pokemon(attacks=[THUNDER_SHOCK])
        can, reason = self.manager.can_learn(pkmn, QUICK_ATTACK)
        self.assertTrue(can)

        # Duplicate
        can, reason = self.manager.can_learn(pkmn, THUNDER_SHOCK)
        self.assertFalse(can)
        self.assertIn("already knows", reason)

        # Full loadout
        pkmn_full = self._create_pokemon(attacks=[THUNDER_SHOCK, QUICK_ATTACK, TACKLE, THUNDERBOLT])
        can, reason = self.manager.can_learn(pkmn_full, EMBER)
        self.assertFalse(can)
        self.assertIn("Move limit reached", reason)

    def test_14_invalid_inputs_handled_safely(self) -> None:
        """Invalid types passed to manager methods return failed results without crashing."""
        pkmn = self._create_pokemon(attacks=[THUNDER_SHOCK])

        # Invalid pokemon
        res1 = self.manager.learn_attack("not a pokemon", QUICK_ATTACK)  # type: ignore
        self.assertFalse(res1.success)
        self.assertIn("Invalid pokemon", res1.reason)

        # Invalid attack
        res2 = self.manager.learn_attack(pkmn, "not an attack")  # type: ignore
        self.assertFalse(res2.success)
        self.assertIn("Invalid attack", res2.reason)

        # Invalid forget pokemon
        res3 = self.manager.forget_attack(None, QUICK_ATTACK)  # type: ignore
        self.assertFalse(res3.success)

        # Invalid replace inputs
        res4 = self.manager.replace_attack("not a pokemon", THUNDER_SHOCK, QUICK_ATTACK)  # type: ignore
        self.assertFalse(res4.success)

        res5 = self.manager.replace_attack(pkmn, THUNDER_SHOCK, "invalid new attack")  # type: ignore
        self.assertFalse(res5.success)

    def test_15_battle_compatibility_with_updated_moves(self) -> None:
        """A Pokemon with newly learned and replaced moves can execute them cleanly in a Battle."""
        pika = self._create_pokemon(species=PIKACHU, attacks=[THUNDER_SHOCK])
        charm = self._create_pokemon(species=CHARMANDER, attacks=[SCRATCH])

        # Teach Pikachu Quick Attack
        self.manager.learn_attack(pika, QUICK_ATTACK)

        # Start a turn-based battle
        battle = Battle(pokemon1=pika, pokemon2=charm)
        battle.start()

        # Execute the newly learned Quick Attack
        turn_result = battle.resolve_turn(attack1=QUICK_ATTACK, attack2=SCRATCH)
        self.assertIsNotNone(turn_result)
        self.assertTrue(len(turn_result.actions) >= 1)
        self.assertEqual(turn_result.actions[0].attack.name, "Quick Attack")
        self.assertLess(charm.current_hp, charm.max_hp)


if __name__ == "__main__":
    unittest.main()
