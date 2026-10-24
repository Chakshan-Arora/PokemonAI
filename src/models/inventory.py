"""
Inventory model managing player consumable items and resources.
Implements slot-based capacity limits, item stack limits, atomic modifications,
and deterministic querying.
"""
from dataclasses import dataclass
from typing import Optional, Union, Iterator
from src.models.item import Item
from src.data.items import ITEM_CATALOG, get_item

DEFAULT_INVENTORY_CAPACITY: int = 20


@dataclass(frozen=True)
class ItemStack:
    """
    Represents an item entry and its quantity in an inventory.

    Supports tuple-like unpacking (item_id, quantity), indexing,
    and direct attribute access.
    """
    item_id: str
    quantity: int
    item: Optional[Item] = None

    def __iter__(self) -> Iterator[Union[str, int]]:
        """Allows unpacking as: item_id, quantity = stack"""
        yield self.item_id
        yield self.quantity

    def __getitem__(self, index: int) -> Union[str, int, Optional[Item]]:
        if index == 0:
            return self.item_id
        elif index == 1:
            return self.quantity
        elif index == 2:
            return self.item
        raise IndexError(f"ItemStack index {index} out of range (0-2).")

    def __len__(self) -> int:
        return 2

    def __repr__(self) -> str:
        name = self.item.name if self.item else self.item_id
        return f"ItemStack(item='{name}', quantity={self.quantity})"


class Inventory:
    """
    Stores and manages a collection of items by item ID.

    Capacity and Stacking Rules:
      - Slot Definition: Each slot in the inventory represents one distinct item stack
        dedicated to a specific item type.
      - Stack Limit: An item stack cannot exceed the item's configured max_stack
        (default 99 for stackable items, 1 for unstackable items).
      - Capacity Limit: Configurable maximum number of distinct slots (default 20).
        When all slots are occupied, adding a new item type is rejected.
        Existing items with available stack space can be replenished without consuming a new slot.
      - Atomicity: Operations that fail do not partially alter quantities or slot allocations.
    """

    def __init__(
        self,
        capacity: Optional[int] = DEFAULT_INVENTORY_CAPACITY,
        max_slots: Optional[int] = None,
        catalog: Optional[dict[str, Item]] = None,
    ) -> None:
        effective_capacity = max_slots if max_slots is not None else capacity
        if effective_capacity is not None:
            if not isinstance(effective_capacity, int) or isinstance(effective_capacity, bool) or effective_capacity < 1:
                raise ValueError(f"Inventory capacity must be a positive integer >= 1, got {effective_capacity}.")

        self._capacity: Optional[int] = effective_capacity
        self._catalog: dict[str, Item] = dict(catalog) if catalog is not None else dict(ITEM_CATALOG)

        # Storage mapping: item_id -> quantity
        self._items: dict[str, int] = {}
        self._last_message: str = "Initialized empty inventory."

    # --- Properties ---

    @property
    def capacity(self) -> Optional[int]:
        """Maximum number of distinct item slots allowed (None for unlimited)."""
        return self._capacity

    @property
    def slots_used(self) -> int:
        """Current number of occupied item slots."""
        return len(self._items)

    @property
    def is_full(self) -> bool:
        """True if all inventory slots are occupied."""
        if self._capacity is None:
            return False
        return self.slots_used >= self._capacity

    @property
    def last_message(self) -> str:
        """Description of the most recent inventory operation outcome."""
        return self._last_message

    # --- Item Queries ---

    def _resolve_item(self, item_or_id: Union[Item, str]) -> tuple[Optional[str], Optional[Item]]:
        """Resolves an item argument into (item_id, Item) or (None, None)."""
        if isinstance(item_or_id, Item):
            norm_id = item_or_id.item_id.strip().lower()
            return norm_id, item_or_id
        elif isinstance(item_or_id, str) and item_or_id.strip():
            norm_id = item_or_id.strip().lower()
            item = self._catalog.get(norm_id) or get_item(norm_id)
            return norm_id, item
        return None, None

    def get_quantity(self, item_or_id: Union[Item, str]) -> int:
        """Returns the current quantity of the specified item."""
        norm_id, _ = self._resolve_item(item_or_id)
        if not norm_id:
            return 0
        return self._items.get(norm_id, 0)

    def has_item(self, item_or_id: Union[Item, str], quantity: int = 1) -> bool:
        """Checks whether the inventory contains at least `quantity` of the specified item."""
        if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity <= 0:
            return False
        return self.get_quantity(item_or_id) >= quantity

    def list_items(self) -> list[ItemStack]:
        """
        Returns all non-empty item stacks currently in the inventory,
        sorted in predictable alphabetical order by item ID.
        """
        sorted_ids = sorted(self._items.keys())
        result: list[ItemStack] = []
        for item_id in sorted_ids:
            qty = self._items[item_id]
            item = self._catalog.get(item_id) or get_item(item_id)
            result.append(ItemStack(item_id=item_id, quantity=qty, item=item))
        return result

    # --- Inventory Mutations ---

    def add_item(self, item_or_id: Union[Item, str], quantity: int = 1) -> bool:
        """
        Adds the specified quantity of an item to the inventory.

        Rules:
          - Rejects non-integer, zero, or negative quantities.
          - Rejects unknown items not found in the catalog.
          - Rejects adding new item types if all slots are occupied (capacity reached).
          - Rejects adding quantities that would exceed the item's configured max_stack.
          - Leaves inventory state completely unchanged upon failure.

        Returns:
            True if addition succeeded in full, False otherwise.
        """
        # Validate quantity
        if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity <= 0:
            self._last_message = f"Invalid quantity {quantity}: quantity must be a positive integer."
            return False

        # Resolve item definition
        norm_id, item = self._resolve_item(item_or_id)
        if not norm_id or item is None:
            name_repr = item_or_id if isinstance(item_or_id, str) else type(item_or_id).__name__
            self._last_message = f"Cannot add unknown item '{name_repr}'."
            return False

        current_qty = self._items.get(norm_id, 0)

        # Check capacity if adding a new distinct item type
        if current_qty == 0:
            if self._capacity is not None and self.slots_used >= self._capacity:
                self._last_message = (
                    f"Cannot add '{item.name}': inventory capacity reached ({self.slots_used}/{self._capacity} slots)."
                )
                return False

        # Check stack limits
        max_allowed = item.max_stack
        if current_qty + quantity > max_allowed:
            self._last_message = (
                f"Cannot add {quantity} '{item.name}': would exceed max stack size of {max_allowed} "
                f"(current: {current_qty}, projected: {current_qty + quantity})."
            )
            return False

        # Atomic commit
        self._items[norm_id] = current_qty + quantity
        self._last_message = f"Added {quantity}x '{item.name}' (new quantity: {self._items[norm_id]})."
        return True

    def can_add_items(self, items: dict[str, int]) -> tuple[bool, str]:
        """
        Validates whether multiple items can be added atomically to the inventory
        without violating catalog requirements, slot capacity, or stack limits.

        Returns:
            (True, "OK") if all items can be added, or (False, reason) otherwise.
        """
        if not isinstance(items, dict):
            return False, "Items specification must be a dictionary."

        new_slots_needed = 0
        projected_quantities: dict[str, int] = {}

        for item_or_id, quantity in items.items():
            if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity <= 0:
                return False, f"Invalid quantity {quantity} for '{item_or_id}': must be a positive integer."

            norm_id, item_obj = self._resolve_item(item_or_id)
            if not norm_id or item_obj is None:
                name_repr = item_or_id if isinstance(item_or_id, str) else type(item_or_id).__name__
                return False, f"Cannot add unknown item '{name_repr}'."

            curr_qty = self._items.get(norm_id, 0)
            already_projected = projected_quantities.get(norm_id, curr_qty)
            new_projected = already_projected + quantity

            if new_projected > item_obj.max_stack:
                return False, (
                    f"Cannot add {quantity}x '{item_obj.name}': would exceed max stack size "
                    f"({item_obj.max_stack})."
                )

            if curr_qty == 0 and norm_id not in projected_quantities:
                new_slots_needed += 1

            projected_quantities[norm_id] = new_projected

        if self._capacity is not None and self.slots_used + new_slots_needed > self._capacity:
            return False, (
                f"Inventory capacity exceeded "
                f"({self.slots_used + new_slots_needed}/{self._capacity} slots needed)."
            )

        return True, "OK"

    def add_items_atomically(self, items: dict[str, int]) -> bool:
        """
        Atomically adds multiple items to the inventory.
        If any item cannot be added (capacity, stack limit, invalid item),
        the entire addition is aborted leaving the inventory untouched.

        Returns:
            True if all items were added, False otherwise.
        """
        can_add, reason = self.can_add_items(items)
        if not can_add:
            self._last_message = reason
            return False

        for item_id, quantity in items.items():
            self.add_item(item_id, quantity)

        self._last_message = f"Atomically added {len(items)} item stack(s)."
        return True

    def remove_item(self, item_or_id: Union[Item, str], quantity: int = 1) -> bool:
        """
        Removes the specified quantity of an item from the inventory.

        Rules:
          - Rejects non-integer, zero, or negative quantities.
          - Rejects removal if the item is not present or quantity exceeds available stock.
          - Frees the slot completely when quantity reaches 0.
          - Leaves inventory state completely unchanged upon failure.

        Returns:
            True if removal succeeded in full, False otherwise.
        """
        # Validate quantity
        if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity <= 0:
            self._last_message = f"Invalid quantity {quantity}: quantity must be a positive integer."
            return False

        # Resolve item identifier
        norm_id, item = self._resolve_item(item_or_id)
        if not norm_id:
            self._last_message = f"Cannot remove invalid item '{item_or_id}'."
            return False

        current_qty = self._items.get(norm_id, 0)
        item_display = item.name if item else norm_id

        if current_qty < quantity:
            self._last_message = (
                f"Cannot remove {quantity}x '{item_display}': insufficient quantity (available: {current_qty})."
            )
            return False

        # Atomic commit
        new_qty = current_qty - quantity
        if new_qty == 0:
            del self._items[norm_id]
        else:
            self._items[norm_id] = new_qty

        self._last_message = f"Removed {quantity}x '{item_display}' (remaining: {new_qty})."
        return True

    def clear(self) -> None:
        """Clears all items from the inventory."""
        self._items.clear()
        self._last_message = "Inventory cleared."

    def __len__(self) -> int:
        """Returns the number of occupied slots."""
        return len(self._items)

    def __contains__(self, item_or_id: Union[Item, str]) -> bool:
        """Checks if at least 1 unit of the item is in the inventory."""
        return self.has_item(item_or_id, 1)

    def __repr__(self) -> str:
        items_str = ", ".join(f"{k}: {v}" for k, v in sorted(self._items.items()))
        cap_str = f"/{self._capacity}" if self._capacity is not None else ""
        return f"Inventory(slots={self.slots_used}{cap_str}, items={{{items_str}}})"
