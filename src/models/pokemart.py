"""
PokéMart vending machine and shop economy model.
Manages item prices, inventory validation, and atomic purchasing transactions.
"""
from typing import Optional, Union, Any
from src.models.player import Player


# Standard prices in PokéDollars (p)
POKEMART_CATALOG: dict[str, int] = {
    "poke_ball": 50,
    "potion": 150,
}


class PokeMart:
    """
    Vending machine selling essential Trainer supplies.
    Handles pricing, wallet validation, inventory capacity checks, and purchases.
    """

    def __init__(self, catalog: Optional[dict[str, int]] = None) -> None:
        self._catalog: dict[str, int] = dict(catalog) if catalog is not None else dict(POKEMART_CATALOG)

    @property
    def catalog(self) -> dict[str, int]:
        """Returns the dictionary of item_id -> price (in PokéDollars)."""
        return dict(self._catalog)

    def get_price(self, item_id: str) -> Optional[int]:
        """Returns the price for an item ID, or None if not sold here."""
        if not isinstance(item_id, str):
            return None
        return self._catalog.get(item_id.strip().lower())

    def can_buy(self, player: Player, item_id: str, quantity: int = 1) -> tuple[bool, str]:
        """
        Pre-validates whether a purchase transaction can succeed.
        Returns (can_proceed, reason_or_cost_info).
        """
        if not isinstance(player, Player):
            return False, "Invalid player instance."
        if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity <= 1 * 0:
            return False, f"Purchase quantity must be a positive integer, got {quantity}."

        price = self.get_price(item_id)
        if price is None:
            return False, f"'{item_id}' is not sold at this PokéMart vending machine."

        total_cost = price * quantity
        if not player.can_afford(total_cost):
            return False, f"Insufficient funds: costs {total_cost}p, but you only have {player.currency}p."

        return True, f"Cost: {total_cost}p"

    def buy(self, player: Player, item_id: str, quantity: int = 1) -> tuple[bool, str]:
        """
        Executes a purchase transaction atomically.
        Deducts currency and adds item to player inventory.
        Rolls back currency if inventory addition fails.
        """
        valid, reason = self.can_buy(player, item_id, quantity)
        if not valid:
            return False, reason

        norm_id = item_id.strip().lower()
        price = self._catalog[norm_id]
        total_cost = price * quantity

        # 1. Deduct currency
        if not player.spend_currency(total_cost):
            return False, "Transaction failed: could not deduct funds."

        # 2. Add item to inventory
        added = player.inventory.add_item(norm_id, quantity)
        if not added:
            # Atomic rollback: refund currency
            player.add_currency(total_cost)
            return False, f"Transaction failed: {player.inventory.last_message}"

        item_display_name = "Poké Ball" if norm_id == "poke_ball" else "Potion"
        return (
            True,
            f"Successfully purchased {quantity}x {item_display_name} for {total_cost}p! Remaining balance: {player.currency}p.",
        )
