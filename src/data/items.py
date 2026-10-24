"""
Predefined item catalog for the Pokemon game.
Contains standard consumable items: Potions, Status Cures, and Poke Balls.
"""
from typing import Optional
from src.models.item import Item, ItemType
from src.models.status_effect import StatusEffectType

# 1. Healing Items
POTION = Item(
    item_id="potion",
    name="Potion",
    description="A spray-type medicine for treating wounds. It restores 20 HP to a single Pokemon.",
    item_type=ItemType.HEALING,
    stackable=True,
    max_stack=99,
    heal_amount=20,
)

SUPER_POTION = Item(
    item_id="super_potion",
    name="Super Potion",
    description="A spray-type medicine for treating wounds. It restores 50 HP to a single Pokemon.",
    item_type=ItemType.HEALING,
    stackable=True,
    max_stack=99,
    heal_amount=50,
)

FULL_RESTORE = Item(
    item_id="full_restore",
    name="Full Restore",
    description="A medicine that fully restores the HP of a single Pokemon and heals any major status condition.",
    item_type=ItemType.HEALING,
    stackable=True,
    max_stack=99,
    heal_all_hp=True,
    cure_all_major=True,
)

# 2. Status Cure Items
ANTIDOTE = Item(
    item_id="antidote",
    name="Antidote",
    description="A spray-type medicine for treating poison. It lifts the effects of poison from a single Pokemon.",
    item_type=ItemType.STATUS_CURE,
    stackable=True,
    max_stack=99,
    cure_status=StatusEffectType.POISON,
)

BURN_HEAL = Item(
    item_id="burn_heal",
    name="Burn Heal",
    description="A spray-type medicine for treating burns. It heals a single Pokemon suffering from a burn.",
    item_type=ItemType.STATUS_CURE,
    stackable=True,
    max_stack=99,
    cure_status=StatusEffectType.BURN,
)

PARALYZE_HEAL = Item(
    item_id="paralyze_heal",
    name="Paralyze Heal",
    description="A spray-type medicine for treating paralysis. It cures a single Pokemon that is paralyzed.",
    item_type=ItemType.STATUS_CURE,
    stackable=True,
    max_stack=99,
    cure_status=StatusEffectType.PARALYSIS,
)

# 3. Capture Items
POKE_BALL = Item(
    item_id="poke_ball",
    name="Poké Ball",
    description="A device for catching wild Pokemon. Reserved for a future capture integration.",
    item_type=ItemType.CAPTURE,
    stackable=True,
    max_stack=99,
)

# Item Catalog Registry
ITEM_CATALOG: dict[str, Item] = {
    POTION.item_id: POTION,
    SUPER_POTION.item_id: SUPER_POTION,
    FULL_RESTORE.item_id: FULL_RESTORE,
    ANTIDOTE.item_id: ANTIDOTE,
    BURN_HEAL.item_id: BURN_HEAL,
    PARALYZE_HEAL.item_id: PARALYZE_HEAL,
    POKE_BALL.item_id: POKE_BALL,
}


def get_item(item_id: str) -> Optional[Item]:
    """
    Looks up an item in the catalog by its identifier.
    Returns the Item definition or None if not found.
    """
    if not isinstance(item_id, str):
        return None
    return ITEM_CATALOG.get(item_id.strip().lower())


def list_catalog_items() -> tuple[Item, ...]:
    """
    Returns all predefined items in the catalog in a predictable order.
    """
    return tuple(ITEM_CATALOG.values())
