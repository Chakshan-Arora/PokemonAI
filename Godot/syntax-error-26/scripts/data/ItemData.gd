class_name ItemData
extends Node
## ItemData - All item definitions for PokémonAI

const ITEMS: Dictionary = {
	"potion": {
		"id": "potion",
		"name": "Potion",
		"description": "Restores 20 HP to one Pokémon.",
		"heal_amount": 20,
		"effect": "heal",
		"usable_in_battle": true,
		"usable_in_field": true,
		"icon_color": "#DD4444"
	},
	"super_potion": {
		"id": "super_potion",
		"name": "Super Potion",
		"description": "Restores 50 HP to one Pokémon.",
		"heal_amount": 50,
		"effect": "heal",
		"usable_in_battle": true,
		"usable_in_field": true,
		"icon_color": "#DD2222"
	},
	"full_restore": {
		"id": "full_restore",
		"name": "Full Restore",
		"description": "Fully restores HP and cures all status conditions.",
		"heal_amount": 9999,
		"effect": "full_restore",
		"usable_in_battle": true,
		"usable_in_field": true,
		"icon_color": "#FFAA00"
	},
	"antidote": {
		"id": "antidote",
		"name": "Antidote",
		"description": "Cures a Pokémon of poison.",
		"heal_amount": 0,
		"effect": "cure_poison",
		"usable_in_battle": true,
		"usable_in_field": true,
		"icon_color": "#AA55CC"
	},
	"burn_heal": {
		"id": "burn_heal",
		"name": "Burn Heal",
		"description": "Cures a Pokémon of a burn.",
		"heal_amount": 0,
		"effect": "cure_burn",
		"usable_in_battle": true,
		"usable_in_field": true,
		"icon_color": "#FF8844"
	},
	"paralyze_heal": {
		"id": "paralyze_heal",
		"name": "Paralyze Heal",
		"description": "Cures a Pokémon of paralysis.",
		"heal_amount": 0,
		"effect": "cure_paralysis",
		"usable_in_battle": true,
		"usable_in_field": true,
		"icon_color": "#FFEE44"
	},
	"poke_ball": {
		"id": "poke_ball",
		"name": "Poké Ball",
		"description": "A device used to capture wild Pokémon.",
		"heal_amount": 0,
		"effect": "capture",
		"usable_in_battle": true,
		"usable_in_field": false,
		"icon_color": "#FF2222"
	}
}

static func get_item(item_id: String) -> Dictionary:
	if ITEMS.has(item_id):
		return ITEMS[item_id]
	return {}

static func has_item(item_id: String) -> bool:
	return ITEMS.has(item_id)

static func get_all_item_ids() -> Array:
	return ITEMS.keys()
