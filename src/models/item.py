"""
Item model and ItemType definitions for player inventory and consumable items.
Defines supported item types (Healing, Status Cure, Capture, Utility) and
the Item dataclass with strict validation.
"""
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Union
from src.models.status_effect import StatusEffectType


class ItemType(Enum):
    """
    Supported item categories in the game.
    """
    HEALING = "healing"
    STATUS_CURE = "status_cure"
    CAPTURE = "capture"
    UTILITY = "utility"

    @property
    def display_name(self) -> str:
        """Human-readable display name for this item type."""
        return self.value.replace("_", " ").title()


@dataclass(frozen=True)
class Item:
    """
    Immutable specification and metadata for an item.

    Attributes:
        item_id: Stable lowercase string identifier (e.g. 'potion').
        name: Display name (e.g. 'Potion').
        description: Short human-readable description.
        item_type: Category enum (ItemType).
        stackable: Whether multiple copies can share an inventory stack.
        max_stack: Maximum number of items in a single stack (default 99).
        heal_amount: Optional integer HP amount restored (for healing items).
        heal_all_hp: Whether this item fully restores HP to maximum (e.g. Full Restore).
        cure_status: Optional specific StatusEffectType cured by this item.
        cure_all_major: Whether this item cures all major conditions (burn, poison, paralysis).
    """
    item_id: str
    name: str
    description: str
    item_type: ItemType
    stackable: bool = True
    max_stack: int = 99
    heal_amount: Optional[int] = None
    heal_all_hp: bool = False
    cure_status: Optional[StatusEffectType] = None
    cure_all_major: bool = False

    def __post_init__(self) -> None:
        """Validates all item fields upon initialization."""
        # Validate item_id
        if not isinstance(self.item_id, str) or not self.item_id.strip():
            raise ValueError("item_id must be a non-empty string.")

        # Validate name
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("name must be a non-empty string.")

        # Validate description
        if not isinstance(self.description, str):
            raise TypeError(f"description must be a string, got {type(self.description).__name__}.")

        # Validate item_type
        if not isinstance(self.item_type, ItemType):
            raise TypeError(f"item_type must be an ItemType enum instance, got {type(self.item_type).__name__}.")

        # Validate stackable
        if not isinstance(self.stackable, bool):
            raise TypeError(f"stackable must be a boolean, got {type(self.stackable).__name__}.")

        # Validate max_stack
        if not isinstance(self.max_stack, int) or isinstance(self.max_stack, bool) or self.max_stack < 1:
            raise ValueError(f"max_stack must be a positive integer >= 1, got {self.max_stack}.")

        if not self.stackable and self.max_stack != 1:
            raise ValueError(f"Non-stackable items must have max_stack=1, got {self.max_stack}.")

        # Validate healing configuration
        if self.heal_amount is not None:
            if not isinstance(self.heal_amount, int) or isinstance(self.heal_amount, bool) or self.heal_amount <= 0:
                raise ValueError(f"heal_amount must be a positive integer > 0, got {self.heal_amount}.")

        if not isinstance(self.heal_all_hp, bool):
            raise TypeError(f"heal_all_hp must be a boolean, got {type(self.heal_all_hp).__name__}.")

        if self.item_type == ItemType.HEALING:
            if self.heal_amount is None and not self.heal_all_hp:
                raise ValueError("Healing items must specify heal_amount or set heal_all_hp=True.")

        # Validate status cure configuration
        if self.cure_status is not None:
            if not isinstance(self.cure_status, StatusEffectType):
                raise TypeError(f"cure_status must be a StatusEffectType, got {type(self.cure_status).__name__}.")

        if not isinstance(self.cure_all_major, bool):
            raise TypeError(f"cure_all_major must be a boolean, got {type(self.cure_all_major).__name__}.")

        if self.item_type == ItemType.STATUS_CURE:
            if self.cure_status is None and not self.cure_all_major:
                raise ValueError("Status cure items must specify cure_status or set cure_all_major=True.")
