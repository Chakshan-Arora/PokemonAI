"""
Unit tests for Inventory model, slot capacity, stack limits, and Player integration.
"""
import unittest
from src.models.item import Item, ItemType
from src.models.inventory import Inventory, ItemStack, DEFAULT_INVENTORY_CAPACITY
from src.models.player import Player
from src.data.items import POTION, SUPER_POTION, FULL_RESTORE, ANTIDOTE, BURN_HEAL, POKE_BALL


class TestInventory(unittest.TestCase):
    """
    Exhaustive test suite for Inventory and item storage rules.
    """

    def setUp(self) -> None:
        self.inventory = Inventory(capacity=5)

    def test_01_item_validation_rules(self) -> None:
        """Item definitions reject empty IDs, empty names, invalid stack limits, etc."""
        # Empty item_id
        with self.assertRaises(ValueError):
            Item(item_id="", name="Invalid", description="", item_type=ItemType.HEALING, heal_amount=10)

        # Empty name
        with self.assertRaises(ValueError):
            Item(item_id="valid_id", name="", description="", item_type=ItemType.HEALING, heal_amount=10)

        # Invalid max_stack (<= 0)
        with self.assertRaises(ValueError):
            Item(item_id="valid_id", name="Valid", description="", item_type=ItemType.HEALING, max_stack=0, heal_amount=10)

        # Non-stackable with max_stack != 1
        with self.assertRaises(ValueError):
            Item(item_id="valid_id", name="Valid", description="", item_type=ItemType.UTILITY, stackable=False, max_stack=5)

        # Healing item missing heal effect
        with self.assertRaises(ValueError):
            Item(item_id="valid_id", name="Valid", description="", item_type=ItemType.HEALING)

        # Status cure missing cure effect
        with self.assertRaises(ValueError):
            Item(item_id="valid_id", name="Valid", description="", item_type=ItemType.STATUS_CURE)

    def test_02_adding_and_removing_items(self) -> None:
        """Items can be added and removed successfully, updating quantities and slots."""
        self.assertEqual(self.inventory.slots_used, 0)
        self.assertEqual(self.inventory.get_quantity("potion"), 0)

        # Add 3 potions
        added = self.inventory.add_item("potion", 3)
        self.assertTrue(added)
        self.assertEqual(self.inventory.get_quantity("potion"), 3)
        self.assertEqual(self.inventory.slots_used, 1)

        # Add 2 more potions
        added = self.inventory.add_item("potion", 2)
        self.assertTrue(added)
        self.assertEqual(self.inventory.get_quantity("potion"), 5)
        self.assertEqual(self.inventory.slots_used, 1)  # Same slot

        # Remove 2 potions
        removed = self.inventory.remove_item("potion", 2)
        self.assertTrue(removed)
        self.assertEqual(self.inventory.get_quantity("potion"), 3)
        self.assertEqual(self.inventory.slots_used, 1)

        # Remove remaining 3 potions
        removed = self.inventory.remove_item("potion", 3)
        self.assertTrue(removed)
        self.assertEqual(self.inventory.get_quantity("potion"), 0)
        self.assertEqual(self.inventory.slots_used, 0)  # Slot freed

    def test_03_quantity_lookup_and_availability_checks(self) -> None:
        """get_quantity and has_item return accurate results."""
        self.inventory.add_item("potion", 5)
        self.inventory.add_item("antidote", 1)

        self.assertEqual(self.inventory.get_quantity("potion"), 5)
        self.assertEqual(self.inventory.get_quantity("antidote"), 1)
        self.assertEqual(self.inventory.get_quantity("super_potion"), 0)

        self.assertTrue(self.inventory.has_item("potion", 5))
        self.assertTrue(self.inventory.has_item("potion", 1))
        self.assertFalse(self.inventory.has_item("potion", 6))
        self.assertTrue(self.inventory.has_item("antidote", 1))
        self.assertFalse(self.inventory.has_item("antidote", 2))
        self.assertFalse(self.inventory.has_item("super_potion", 1))

        # Check 'in' operator
        self.assertIn("potion", self.inventory)
        self.assertIn(ANTIDOTE, self.inventory)
        self.assertNotIn("super_potion", self.inventory)

    def test_04_unknown_item_ids_rejected(self) -> None:
        """Adding or removing unknown items is rejected cleanly."""
        added = self.inventory.add_item("mysterious_orb", 1)
        self.assertFalse(added)
        self.assertIn("unknown item", self.inventory.last_message.lower())
        self.assertEqual(self.inventory.slots_used, 0)

        removed = self.inventory.remove_item("mysterious_orb", 1)
        self.assertFalse(removed)
        self.assertEqual(self.inventory.slots_used, 0)

    def test_05_zero_and_negative_quantities_rejected(self) -> None:
        """Zero and negative quantities are rejected for both add and remove operations."""
        # Zero quantity
        self.assertFalse(self.inventory.add_item("potion", 0))
        self.assertFalse(self.inventory.remove_item("potion", 0))

        # Negative quantity
        self.assertFalse(self.inventory.add_item("potion", -5))
        self.assertFalse(self.inventory.remove_item("potion", -1))

        # Non-integer quantity
        self.assertFalse(self.inventory.add_item("potion", "three"))  # type: ignore
        self.assertFalse(self.inventory.remove_item("potion", 2.5))  # type: ignore

        self.assertEqual(self.inventory.slots_used, 0)

    def test_06_insufficient_quantity_removal_rejected(self) -> None:
        """Attempts to remove more than the available quantity fail and leave state unchanged."""
        self.inventory.add_item("potion", 3)
        self.assertEqual(self.inventory.get_quantity("potion"), 3)

        # Attempt to remove 4
        removed = self.inventory.remove_item("potion", 4)
        self.assertFalse(removed)
        self.assertIn("insufficient quantity", self.inventory.last_message.lower())

        # Quantity must remain exactly 3
        self.assertEqual(self.inventory.get_quantity("potion"), 3)
        self.assertEqual(self.inventory.slots_used, 1)

    def test_07_capacity_limits_enforced(self) -> None:
        """Inventory enforces maximum slot capacity when adding distinct item types."""
        small_inv = Inventory(capacity=2)
        self.assertEqual(small_inv.capacity, 2)

        # Add item 1
        self.assertTrue(small_inv.add_item("potion", 10))
        self.assertEqual(small_inv.slots_used, 1)
        self.assertFalse(small_inv.is_full)

        # Add item 2
        self.assertTrue(small_inv.add_item("antidote", 5))
        self.assertEqual(small_inv.slots_used, 2)
        self.assertTrue(small_inv.is_full)

        # Attempt to add a 3rd distinct item type (exceeds capacity)
        self.assertFalse(small_inv.add_item("super_potion", 1))
        self.assertIn("capacity reached", small_inv.last_message.lower())
        self.assertEqual(small_inv.slots_used, 2)
        self.assertEqual(small_inv.get_quantity("super_potion"), 0)

        # Existing items can still be replenished
        self.assertTrue(small_inv.add_item("potion", 5))
        self.assertEqual(small_inv.get_quantity("potion"), 15)

    def test_08_stack_limits_enforced(self) -> None:
        """Adding quantities exceeding the item's max_stack is rejected atomically."""
        custom_item = Item(
            item_id="rare_candy",
            name="Rare Candy",
            description="A special candy.",
            item_type=ItemType.UTILITY,
            stackable=True,
            max_stack=10,
        )
        custom_catalog = {"rare_candy": custom_item, **self.inventory._catalog}
        custom_inv = Inventory(capacity=5, catalog=custom_catalog)

        # Add up to max_stack
        self.assertTrue(custom_inv.add_item("rare_candy", 8))
        self.assertEqual(custom_inv.get_quantity("rare_candy"), 8)

        # Attempt to add 3 more (8 + 3 = 11 > 10)
        self.assertFalse(custom_inv.add_item("rare_candy", 3))
        self.assertIn("would exceed max stack size", custom_inv.last_message.lower())

        # Quantity must remain 8
        self.assertEqual(custom_inv.get_quantity("rare_candy"), 8)

        # Unstackable item (max_stack = 1)
        unstackable = Item(
            item_id="bicycle",
            name="Bicycle",
            description="A folding bike.",
            item_type=ItemType.UTILITY,
            stackable=False,
            max_stack=1,
        )
        custom_inv._catalog["bicycle"] = unstackable
        self.assertTrue(custom_inv.add_item("bicycle", 1))
        self.assertFalse(custom_inv.add_item("bicycle", 1))  # 1 + 1 > 1
        self.assertEqual(custom_inv.get_quantity("bicycle"), 1)

    def test_09_failed_operations_leave_state_unchanged(self) -> None:
        """Any failed operation guarantees total atomicity."""
        self.inventory.add_item("potion", 10)
        self.inventory.add_item("burn_heal", 2)

        # Snapshot state
        initial_potion = self.inventory.get_quantity("potion")
        initial_burn_heal = self.inventory.get_quantity("burn_heal")
        initial_slots = self.inventory.slots_used

        # Failed add: invalid quantity
        self.inventory.add_item("potion", -5)
        # Failed add: unknown item
        self.inventory.add_item("ghost_item", 1)
        # Failed remove: over-quantity
        self.inventory.remove_item("burn_heal", 10)

        self.assertEqual(self.inventory.get_quantity("potion"), initial_potion)
        self.assertEqual(self.inventory.get_quantity("burn_heal"), initial_burn_heal)
        self.assertEqual(self.inventory.slots_used, initial_slots)

    def test_10_list_items_predictable_order_and_unpacking(self) -> None:
        """list_items returns items in alphabetical order and supports unpacking."""
        self.inventory.add_item("super_potion", 2)
        self.inventory.add_item("antidote", 5)
        self.inventory.add_item("potion", 10)

        stacks = self.inventory.list_items()
        self.assertEqual(len(stacks), 3)

        # Alphabetical ordering: antidote, potion, super_potion
        self.assertEqual(stacks[0].item_id, "antidote")
        self.assertEqual(stacks[0].quantity, 5)
        self.assertEqual(stacks[1].item_id, "potion")
        self.assertEqual(stacks[1].quantity, 10)
        self.assertEqual(stacks[2].item_id, "super_potion")
        self.assertEqual(stacks[2].quantity, 2)

        # Unpacking as: item_id, quantity = stack
        unpacked = [(item_id, qty) for item_id, qty in stacks]
        self.assertEqual(unpacked, [("antidote", 5), ("potion", 10), ("super_potion", 2)])

    def test_11_independent_inventories_for_different_players(self) -> None:
        """Different Player instances possess isolated, independent inventories."""
        player_red = Player(name="Red")
        player_blue = Player(name="Blue")

        self.assertIsNot(player_red.inventory, player_blue.inventory)
        self.assertEqual(player_red.inventory.slots_used, 0)
        self.assertEqual(player_blue.inventory.slots_used, 0)

        # Add item to Red's inventory only
        player_red.inventory.add_item("potion", 3)
        self.assertEqual(player_red.inventory.get_quantity("potion"), 3)
        self.assertEqual(player_blue.inventory.get_quantity("potion"), 0)

        # Custom inventory injection
        custom_inv = Inventory(capacity=50)
        player_custom = Player(name="Green", inventory=custom_inv)
        self.assertIs(player_custom.inventory, custom_inv)
        self.assertEqual(player_custom.inventory.capacity, 50)


if __name__ == "__main__":
    unittest.main()
