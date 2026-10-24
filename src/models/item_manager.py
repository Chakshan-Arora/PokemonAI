"""
Item Use Manager orchestrating item consumption, target validation,
HP restoration, and status condition removal.
"""
from dataclasses import dataclass
from typing import Optional, Union, TYPE_CHECKING
from src.models.pokemon import Pokemon
from src.models.item import Item, ItemType
from src.models.inventory import Inventory
from src.models.status_effect import StatusEffectType
from src.models.status_effect_manager import StatusEffectManager
from src.data.items import ITEM_CATALOG, get_item

if TYPE_CHECKING:
    from src.models.player import Player
    from src.models.quest_manager import QuestManager


@dataclass(frozen=True)
class ItemUseResult:
    """
    Structured outcome of an attempt to use an item on a Pokemon.

    Attributes:
        success: Whether the item was successfully used and consumed.
        message: Human-readable explanation of the outcome.
        item: The Item definition used, if resolved.
        target_pokemon: The target Pokemon instance, if resolved.
        hp_restored: Amount of HP restored to the Pokemon (0 if none).
        status_conditions_cured: Tuple of StatusEffectType conditions cured.
    """
    success: bool
    message: str
    item: Optional[Item] = None
    target_pokemon: Optional[Pokemon] = None
    hp_restored: int = 0
    status_conditions_cured: tuple[StatusEffectType, ...] = ()

    def __bool__(self) -> bool:
        return self.success


class ItemManager:
    """
    Coordinates using consumable items from a player's inventory on target Pokemon.

    Rules:
      - Validates inventory, item existence, and target Pokemon before state changes.
      - Fainted Pokemon cannot receive healing or status cure items.
      - Healing items cannot be used on Pokemon already at maximum HP (unless also curing status).
      - Status cures only succeed if the target is afflicted with the corresponding condition.
      - Poké Ball and capture items are recognized but return an explicit unsupported result.
      - Exactly one item is consumed from inventory upon success.
      - Unsuccessful operations leave inventory, HP, and status effects completely unchanged.
      - Temporary combat stat modifiers and permanent stats are never corrupted.
    """

    def __init__(
        self,
        catalog: Optional[dict[str, Item]] = None,
        quest_manager: Optional["QuestManager"] = None,
    ) -> None:
        self._catalog: dict[str, Item] = dict(catalog) if catalog is not None else dict(ITEM_CATALOG)
        self._quest_manager: Optional["QuestManager"] = quest_manager

    @property
    def quest_manager(self) -> Optional["QuestManager"]:
        """Associated QuestManager instance for synchronizing item objectives."""
        return self._quest_manager

    @quest_manager.setter
    def quest_manager(self, qm: Optional["QuestManager"]) -> None:
        self._quest_manager = qm

    def _resolve_item(self, item_or_id: Union[Item, str]) -> tuple[Optional[str], Optional[Item]]:
        """Resolves an item identifier or instance into (item_id, Item)."""
        if isinstance(item_or_id, Item):
            norm_id = item_or_id.item_id.strip().lower()
            return norm_id, item_or_id
        elif isinstance(item_or_id, str) and item_or_id.strip():
            norm_id = item_or_id.strip().lower()
            item = self._catalog.get(norm_id) or get_item(norm_id)
            return norm_id, item
        return None, None

    @staticmethod
    def _has_status(
        pokemon: Pokemon,
        condition: StatusEffectType,
        status_manager: Optional[StatusEffectManager],
    ) -> bool:
        """Checks if the Pokemon has the specified status condition."""
        if status_manager is not None and status_manager.has_effect(pokemon, condition):
            return True
        return pokemon.has_status_effect(condition)

    @staticmethod
    def _cure_status(
        pokemon: Pokemon,
        condition: StatusEffectType,
        status_manager: Optional[StatusEffectManager],
    ) -> bool:
        """Cures the specified status condition across both manager and Pokemon instance."""
        removed = False
        if status_manager is not None and status_manager.has_effect(pokemon, condition):
            removed = status_manager.cure_major_condition(pokemon, condition) or removed
        if pokemon.has_status_effect(condition):
            removed = pokemon.remove_status_effect(condition) or removed
        return removed

    def use_item(
        self,
        inventory: Inventory,
        item_or_id: Union[Item, str],
        target_pokemon: Pokemon,
        status_manager: Optional[StatusEffectManager] = None,
        player: Optional["Player"] = None,
        quest_manager: Optional["QuestManager"] = None,
    ) -> ItemUseResult:
        """
        Attempts to use an item from the given inventory on the target Pokemon.

        Args:
            inventory: The Inventory instance holding the item.
            item_or_id: Item identifier string or Item instance to use.
            target_pokemon: The target Pokemon to apply the item to.
            status_manager: Optional active battle StatusEffectManager instance.
            player: Optional Player instance for quest event notification.
            quest_manager: Optional QuestManager instance override.

        Returns:
            An ItemUseResult describing the outcome.
        """
        # Validate inventory
        if not isinstance(inventory, Inventory):
            return ItemUseResult(
                success=False,
                message=f"Invalid inventory: expected Inventory instance, got {type(inventory).__name__}.",
            )

        # Validate target Pokemon
        if not isinstance(target_pokemon, Pokemon):
            return ItemUseResult(
                success=False,
                message=f"Invalid target: expected Pokemon instance, got {type(target_pokemon).__name__}.",
            )

        # Resolve item
        norm_id, item = self._resolve_item(item_or_id)
        if not norm_id or item is None:
            name_repr = item_or_id if isinstance(item_or_id, str) else type(item_or_id).__name__
            return ItemUseResult(
                success=False,
                message=f"Unknown item '{name_repr}'.",
                target_pokemon=target_pokemon,
            )

        # Check inventory availability
        if not inventory.has_item(norm_id, 1):
            return ItemUseResult(
                success=False,
                message=f"No {item.name} available in inventory.",
                item=item,
                target_pokemon=target_pokemon,
            )

        # Rejection of fainted Pokemon
        if target_pokemon.is_fainted:
            return ItemUseResult(
                success=False,
                message=f"Cannot use {item.name} on fainted Pokemon {target_pokemon.display_name}.",
                item=item,
                target_pokemon=target_pokemon,
            )

        # Capture Items (Poké Ball)
        if item.item_type == ItemType.CAPTURE:
            return ItemUseResult(
                success=False,
                message=f"Cannot use {item.name}: item-based capture is not yet supported.",
                item=item,
                target_pokemon=target_pokemon,
            )

        # Utility Items
        if item.item_type == ItemType.UTILITY:
            return ItemUseResult(
                success=False,
                message=f"Cannot use {item.name}: utility item use is not supported in this context.",
                item=item,
                target_pokemon=target_pokemon,
            )

        # Healing Items (Potion, Super Potion, Full Restore)
        if item.item_type == ItemType.HEALING:
            hp_missing = target_pokemon.max_hp - target_pokemon.current_hp
            can_heal_hp = hp_missing > 0

            # Check if this healing item also cures status conditions
            cured_conditions: list[StatusEffectType] = []
            if item.cure_all_major:
                for cond in (StatusEffectType.BURN, StatusEffectType.POISON, StatusEffectType.PARALYSIS):
                    if self._has_status(target_pokemon, cond, status_manager):
                        cured_conditions.append(cond)
            elif item.cure_status is not None:
                if self._has_status(target_pokemon, item.cure_status, status_manager):
                    cured_conditions.append(item.cure_status)

            # If no HP can be healed AND no status condition can be cured, fail without consuming item
            if not can_heal_hp and not cured_conditions:
                return ItemUseResult(
                    success=False,
                    message=f"It won't have any effect! {target_pokemon.display_name} is already at full health.",
                    item=item,
                    target_pokemon=target_pokemon,
                )

            # Apply HP restoration
            actual_healed = 0
            if can_heal_hp:
                heal_val = target_pokemon.max_hp if item.heal_all_hp else (item.heal_amount or 0)
                actual_healed = target_pokemon.heal(heal_val)

            # Apply status cures
            for cond in cured_conditions:
                self._cure_status(target_pokemon, cond, status_manager)

            # Consume exactly 1 item from inventory
            inventory.remove_item(norm_id, 1)

            # Notify quest manager of item consumption
            active_qm = quest_manager or self._quest_manager
            if active_qm is not None and player is not None:
                active_qm.record_item_consumed(player, norm_id, count=1)

            # Construct message
            msg_parts: list[str] = []
            if actual_healed > 0:
                msg_parts.append(f"Restored {actual_healed} HP ({target_pokemon.current_hp}/{target_pokemon.max_hp})")
            if cured_conditions:
                cured_names = ", ".join(c.display_name for c in cured_conditions)
                msg_parts.append(f"Cured {cured_names}")

            msg = f"Used {item.name} on {target_pokemon.display_name}! " + ". ".join(msg_parts) + "."
            return ItemUseResult(
                success=True,
                message=msg,
                item=item,
                target_pokemon=target_pokemon,
                hp_restored=actual_healed,
                status_conditions_cured=tuple(cured_conditions),
            )

        # Status Cure Items (Antidote, Burn Heal, Paralyze Heal)
        if item.item_type == ItemType.STATUS_CURE:
            cured_conditions: list[StatusEffectType] = []

            if item.cure_all_major:
                for cond in (StatusEffectType.BURN, StatusEffectType.POISON, StatusEffectType.PARALYSIS):
                    if self._has_status(target_pokemon, cond, status_manager):
                        cured_conditions.append(cond)
            elif item.cure_status is not None:
                if self._has_status(target_pokemon, item.cure_status, status_manager):
                    cured_conditions.append(item.cure_status)

            # If target does not have the corresponding condition, fail without consuming item
            if not cured_conditions:
                target_cond_name = item.cure_status.display_name.lower() if item.cure_status else "status conditions"
                return ItemUseResult(
                    success=False,
                    message=f"It won't have any effect! {target_pokemon.display_name} is not afflicted with {target_cond_name}.",
                    item=item,
                    target_pokemon=target_pokemon,
                )

            # Apply status cures
            for cond in cured_conditions:
                self._cure_status(target_pokemon, cond, status_manager)

            # Consume exactly 1 item from inventory
            inventory.remove_item(norm_id, 1)

            # Notify quest manager of item consumption
            active_qm = quest_manager or self._quest_manager
            if active_qm is not None and player is not None:
                active_qm.record_item_consumed(player, norm_id, count=1)

            cured_names = ", ".join(c.display_name for c in cured_conditions)
            msg = f"Used {item.name} on {target_pokemon.display_name}! Cured {cured_names}."
            return ItemUseResult(
                success=True,
                message=msg,
                item=item,
                target_pokemon=target_pokemon,
                hp_restored=0,
                status_conditions_cured=tuple(cured_conditions),
            )

        return ItemUseResult(
            success=False,
            message=f"Unsupported item action for '{item.name}'.",
            item=item,
            target_pokemon=target_pokemon,
        )
