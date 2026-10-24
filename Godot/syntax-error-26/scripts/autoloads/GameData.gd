extends Node
## GameData - Central access point for all static game data (Autoload)

const AttackData = preload("res://scripts/data/AttackData.gd")
const TypeChart = preload("res://scripts/data/TypeChart.gd")
const PokemonData = preload("res://scripts/data/PokemonData.gd")
const ItemData = preload("res://scripts/data/ItemData.gd")
const HabitatData = preload("res://scripts/data/HabitatData.gd")
const RegionData = preload("res://scripts/data/RegionData.gd")
const QuestData = preload("res://scripts/data/QuestData.gd")

# Data script instances
var _attack_data: GDScript
var _type_chart: GDScript
var _pokemon_data: GDScript
var _item_data: GDScript
var _habitat_data: GDScript
var _region_data: GDScript
var _quest_data: GDScript

func _ready() -> void:
	_attack_data = load("res://scripts/data/AttackData.gd")
	_type_chart = load("res://scripts/data/TypeChart.gd")
	_pokemon_data = load("res://scripts/data/PokemonData.gd")
	_item_data = load("res://scripts/data/ItemData.gd")
	_habitat_data = load("res://scripts/data/HabitatData.gd")
	_region_data = load("res://scripts/data/RegionData.gd")
	_quest_data = load("res://scripts/data/QuestData.gd")

# ─── Attack Data ──────────────────────────────────────────────────────────────

func get_attack(attack_name: String) -> Dictionary:
	return AttackData.get_attack(attack_name)

func has_attack(attack_name: String) -> bool:
	return AttackData.has_attack(attack_name)

# ─── Type Chart ───────────────────────────────────────────────────────────────

func get_type_effectiveness(attacking_type: String, defending_types: Array) -> float:
	return TypeChart.get_effectiveness(attacking_type, defending_types)

func get_effectiveness_message(multiplier: float) -> String:
	return TypeChart.get_effectiveness_message(multiplier)

# ─── Pokémon Species Data ─────────────────────────────────────────────────────

func get_species(species_name: String) -> Dictionary:
	return PokemonData.get_species(species_name)

func has_species(species_name: String) -> bool:
	return PokemonData.has_species(species_name)

func get_species_color(species_name: String) -> Color:
	return PokemonData.get_species_color(species_name)

func get_all_species_names() -> Array:
	return PokemonData.get_all_species_names()

func get_starters() -> Array:
	return PokemonData.get_starters()

func get_type_color(type_name: String) -> Color:
	if PokemonData.TYPE_COLORS.has(type_name):
		return PokemonData.TYPE_COLORS[type_name]
	return Color.GRAY

# ─── Item Data ────────────────────────────────────────────────────────────────

func get_item(item_id: String) -> Dictionary:
	return ItemData.get_item(item_id)

func has_item(item_id: String) -> bool:
	return ItemData.has_item(item_id)

func get_all_item_ids() -> Array:
	return ItemData.get_all_item_ids()

# ─── Habitat Data ─────────────────────────────────────────────────────────────

func get_habitat(region_id: String) -> Array:
	return HabitatData.get_habitat(region_id)

# ─── Region Data ──────────────────────────────────────────────────────────────

func get_region(region_id: String) -> Dictionary:
	return RegionData.get_region(region_id)

func get_all_region_ids() -> Array:
	return RegionData.get_all_region_ids()

func get_region_at_position(world_x: float, world_z: float) -> String:
	return RegionData.get_region_at_position(world_x, world_z)

# ─── Quest Data ───────────────────────────────────────────────────────────────

func get_quest(quest_id: String) -> Dictionary:
	return QuestData.get_quest(quest_id)

func get_all_quest_ids() -> Array:
	return QuestData.get_all_quest_ids()

func get_auto_start_quests() -> Array:
	return QuestData.get_auto_start_quests()
