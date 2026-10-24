"""
Unit tests for ItemManager: item consumption, HP healing, status curing,
validation, and atomicity.
"""
import unittest
from src.models.personality import Personality
from src.models.pokemon import Pokemon
from src.models.inventory import Inventory
from src.models.item_manager import ItemManager, ItemUseResult
from src.models.status_effect import (
    StatusEffectType,
    StatusEffect,
    AttackEffect,
)
from src.models.status_effect_manager import StatusEffectManager
from src.data.species import PIKACHU, CHARMANDER, SQUIRTLE
from src.data.items import (
    POTION,
    SUPER_POTION,
    FULL_RESTORE,
    ANTIDOTE,
    BURN_HEAL,
    PARALYZE_HEAL,
    POKE_BALL,
)


class TestItemManager(unittest.TestCase):
    """
    Exhaustive test suite for ItemManager item usage on Pokemon.
    """

    def setUp(self) -> None:
        self.personality = Personality(50, 50, 50, 50, 50, 50)
        self.pika = Pokemon(species=PIKACHU, personality=self.personality, level=20) # max_hp = 11 + 40 = 51
        self.charm = Pokemon(species=CHARMANDER, personality=self.personality, level=20) # max_hp = 12 + 40 = 52
        self.inventory = Inventory(capacity=10)
        self.item_manager = ItemManager()
        self.status_manager = StatusEffectManager()

    def test_01_potion_and_super_potion_healing(self) -> None:
        """Potion restores 20 HP and Super Potion restores 50 HP."""
        # Potion test
        self.inventory.add_item("potion", 2)
        self.pika.take_damage(25) # 51 - 25 = 26 HP remaining
        self.assertEqual(self.pika.current_hp, 26)

        res = self.item_manager.use_item(self.inventory, "potion", self.pika)
        self.assertTrue(res.success)
        self.assertEqual(res.hp_restored, 20)
        self.assertEqual(self.pika.current_hp, 46)
        self.assertEqual(self.inventory.get_quantity("potion"), 1) # Consumed exactly 1

        # Super Potion test
        self.inventory.add_item("super_potion", 2)
        self.charm.take_damage(45) # 52 - 45 = 7 HP remaining
        self.assertEqual(self.charm.current_hp, 7)

        res_sp = self.item_manager.use_item(self.inventory, "super_potion", self.charm)
        self.assertTrue(res_sp.success)
        self.assertEqual(res_sp.hp_restored, 45) # Clamped to max HP 52 (7 + 45 = 52)
        self.assertEqual(self.charm.current_hp, self.charm.max_hp)
        self.assertEqual(self.inventory.get_quantity("super_potion"), 1)

    def test_02_healing_near_maximum_hp_without_exceeding_it(self) -> None:
        """Healing near maximum HP clamps to max_hp and returns actual HP restored."""
        self.inventory.add_item("potion", 3)
        self.pika.take_damage(5) # 51 - 5 = 46 HP remaining

        res = self.item_manager.use_item(self.inventory, "potion", self.pika)
        self.assertTrue(res.success)
        self.assertEqual(res.hp_restored, 5) # Only 5 HP restored, not 20
        self.assertEqual(self.pika.current_hp, self.pika.max_hp)
        self.assertEqual(self.inventory.get_quantity("potion"), 2)

    def test_03_full_restore_healing_and_curing_major_conditions(self) -> None:
        """Full Restore heals all lost HP and cures major conditions simultaneously."""
        self.inventory.add_item("full_restore", 2)
        self.pika.take_damage(30)
        self.status_manager.apply_effect(self.pika, StatusEffectType.BURN)

        self.assertEqual(self.pika.current_hp, 21)
        self.assertTrue(self.status_manager.has_effect(self.pika, StatusEffectType.BURN))

        res = self.item_manager.use_item(self.inventory, "full_restore", self.pika, self.status_manager)
        self.assertTrue(res.success)
        self.assertEqual(res.hp_restored, 30)
        self.assertEqual(self.pika.current_hp, self.pika.max_hp)
        self.assertIn(StatusEffectType.BURN, res.status_conditions_cured)
        self.assertFalse(self.status_manager.has_effect(self.pika, StatusEffectType.BURN))
        self.assertFalse(self.pika.has_status_effect(StatusEffectType.BURN))
        self.assertEqual(self.inventory.get_quantity("full_restore"), 1)

    def test_04_full_restore_on_full_hp_with_status_condition(self) -> None:
        """Full Restore works when HP is already full if a major status condition is present."""
        self.inventory.add_item("full_restore", 1)
        self.status_manager.apply_effect(self.pika, StatusEffectType.PARALYSIS)

        self.assertEqual(self.pika.current_hp, self.pika.max_hp)
        self.assertTrue(self.status_manager.has_effect(self.pika, StatusEffectType.PARALYSIS))

        res = self.item_manager.use_item(self.inventory, "full_restore", self.pika, self.status_manager)
        self.assertTrue(res.success)
        self.assertEqual(res.hp_restored, 0)
        self.assertIn(StatusEffectType.PARALYSIS, res.status_conditions_cured)
        self.assertFalse(self.status_manager.has_effect(self.pika, StatusEffectType.PARALYSIS))
        self.assertEqual(self.inventory.get_quantity("full_restore"), 0)

    def test_05_each_specific_status_cure(self) -> None:
        """Antidote cures poison, Burn Heal cures burn, and Paralyze Heal cures paralysis."""
        # Antidote
        self.inventory.add_item("antidote", 1)
        self.status_manager.apply_effect(self.pika, StatusEffectType.POISON)
        res_ant = self.item_manager.use_item(self.inventory, "antidote", self.pika, self.status_manager)
        self.assertTrue(res_ant.success)
        self.assertFalse(self.status_manager.has_effect(self.pika, StatusEffectType.POISON))
        self.assertEqual(self.inventory.get_quantity("antidote"), 0)

        # Burn Heal
        self.inventory.add_item("burn_heal", 1)
        self.status_manager.apply_effect(self.pika, StatusEffectType.BURN)
        res_bh = self.item_manager.use_item(self.inventory, "burn_heal", self.pika, self.status_manager)
        self.assertTrue(res_bh.success)
        self.assertFalse(self.status_manager.has_effect(self.pika, StatusEffectType.BURN))
        self.assertEqual(self.inventory.get_quantity("burn_heal"), 0)

        # Paralyze Heal
        self.inventory.add_item("paralyze_heal", 1)
        self.status_manager.apply_effect(self.pika, StatusEffectType.PARALYSIS)
        res_ph = self.item_manager.use_item(self.inventory, "paralyze_heal", self.pika, self.status_manager)
        self.assertTrue(res_ph.success)
        self.assertFalse(self.status_manager.has_effect(self.pika, StatusEffectType.PARALYSIS))
        self.assertEqual(self.inventory.get_quantity("paralyze_heal"), 0)

    def test_06_using_item_on_fainted_pokemon_rejected(self) -> None:
        """Healing and status curing items cannot be used on fainted Pokemon."""
        self.inventory.add_item("potion", 2)
        self.inventory.add_item("antidote", 1)
        self.pika.take_damage(self.pika.max_hp)
        self.assertTrue(self.pika.is_fainted)

        # Attempt healing item
        res = self.item_manager.use_item(self.inventory, "potion", self.pika)
        self.assertFalse(res.success)
        self.assertIn("fainted", res.message.lower())
        self.assertEqual(self.pika.current_hp, 0)
        self.assertEqual(self.inventory.get_quantity("potion"), 2) # Not consumed

        # Attempt status cure
        res_ant = self.item_manager.use_item(self.inventory, "antidote", self.pika)
        self.assertFalse(res_ant.success)
        self.assertIn("fainted", res_ant.message.lower())
        self.assertEqual(self.inventory.get_quantity("antidote"), 1)

    def test_07_using_healing_item_unnecessarily_rejected(self) -> None:
        """Using a healing item on a Pokemon at maximum HP with no condition fails without consumption."""
        self.inventory.add_item("potion", 3)
        self.inventory.add_item("full_restore", 1)
        self.assertEqual(self.pika.current_hp, self.pika.max_hp)

        # Potion on full HP
        res = self.item_manager.use_item(self.inventory, "potion", self.pika)
        self.assertFalse(res.success)
        self.assertIn("full health", res.message.lower())
        self.assertEqual(self.inventory.get_quantity("potion"), 3)

        # Full Restore on full HP without status condition
        res_fr = self.item_manager.use_item(self.inventory, "full_restore", self.pika)
        self.assertFalse(res_fr.success)
        self.assertIn("full health", res_fr.message.lower())
        self.assertEqual(self.inventory.get_quantity("full_restore"), 1)

    def test_08_using_status_cure_on_wrong_condition_rejected(self) -> None:
        """Using a specific status cure on an un-afflicted Pokemon or wrong condition fails without consumption."""
        self.inventory.add_item("antidote", 2)
        self.inventory.add_item("burn_heal", 1)

        # Antidote on completely healthy Pokemon
        res = self.item_manager.use_item(self.inventory, "antidote", self.pika)
        self.assertFalse(res.success)
        self.assertIn("not afflicted", res.message.lower())
        self.assertEqual(self.inventory.get_quantity("antidote"), 2)

        # Antidote on a Burned Pokemon
        self.status_manager.apply_effect(self.pika, StatusEffectType.BURN)
        res_wrong = self.item_manager.use_item(self.inventory, "antidote", self.pika, self.status_manager)
        self.assertFalse(res_wrong.success)
        self.assertIn("not afflicted", res_wrong.message.lower())
        self.assertTrue(self.status_manager.has_effect(self.pika, StatusEffectType.BURN))
        self.assertEqual(self.inventory.get_quantity("antidote"), 2)

    def test_09_missing_items_in_inventory_rejected(self) -> None:
        """Attempting to use an item that the player does not have returns a clean failure."""
        self.assertEqual(self.inventory.get_quantity("potion"), 0)
        self.pika.take_damage(10)

        res = self.item_manager.use_item(self.inventory, "potion", self.pika)
        self.assertFalse(res.success)
        self.assertIn("no potion available", res.message.lower())
        self.assertEqual(self.pika.current_hp, 41)

    def test_10_unsupported_poke_ball_use(self) -> None:
        """Poké Ball usage returns explicit unsupported-action result and does not consume item."""
        self.inventory.add_item("poke_ball", 5)

        res = self.item_manager.use_item(self.inventory, "poke_ball", self.pika)
        self.assertFalse(res.success)
        self.assertIn("item-based capture is not yet supported", res.message.lower())
        self.assertEqual(self.inventory.get_quantity("poke_ball"), 5) # Never consumed

    def test_11_unrelated_status_effects_and_trained_stats_remain_intact(self) -> None:
        """Curing poison does not remove temporary Attack reduction or mutate trained stats."""
        self.inventory.add_item("antidote", 1)
        self.pika.set_trained_stat("attack", 15) # Trained attack bonus
        initial_attack = self.pika.attack

        # Apply Poison AND Attack Reduction
        self.status_manager.apply_effect(self.pika, StatusEffectType.POISON)
        self.status_manager.apply_effect(self.pika, StatusEffectType.ATTACK_REDUCTION)

        self.assertTrue(self.status_manager.has_effect(self.pika, StatusEffectType.POISON))
        self.assertTrue(self.status_manager.has_effect(self.pika, StatusEffectType.ATTACK_REDUCTION))

        res = self.item_manager.use_item(self.inventory, "antidote", self.pika, self.status_manager)
        self.assertTrue(res.success)
        self.assertFalse(self.status_manager.has_effect(self.pika, StatusEffectType.POISON))
        # Attack reduction must STILL be present
        self.assertTrue(self.status_manager.has_effect(self.pika, StatusEffectType.ATTACK_REDUCTION))
        # Trained stat is unchanged
        self.assertEqual(self.pika.trained_attack, 15)
        self.assertEqual(self.pika.attack, initial_attack)

    def test_12_invalid_arguments_handled_safely(self) -> None:
        """Passing non-inventory, non-Pokemon, or invalid types returns clean failure."""
        res1 = self.item_manager.use_item("NotAnInventory", "potion", self.pika) # type: ignore
        self.assertFalse(res1.success)

        res2 = self.item_manager.use_item(self.inventory, "potion", "NotAPokemon") # type: ignore
        self.assertFalse(res2.success)

        res3 = self.item_manager.use_item(self.inventory, "non_existent_item", self.pika)
        self.assertFalse(res3.success)
        self.assertIn("unknown item", res3.message.lower())


if __name__ == "__main__":
    unittest.main()
