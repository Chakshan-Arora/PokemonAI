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

var backend_data: Dictionary = {}
var move_learning_data: Dictionary = {}
var personality_traits: Array = [
	"aggression", "curiosity", "fear", "sociability", "loyalty", "confidence"
]

func _ready() -> void:
	_attack_data = load("res://scripts/data/AttackData.gd")
	_type_chart = load("res://scripts/data/TypeChart.gd")
	_pokemon_data = load("res://scripts/data/PokemonData.gd")
	_item_data = load("res://scripts/data/ItemData.gd")
	_habitat_data = load("res://scripts/data/HabitatData.gd")
	_region_data = load("res://scripts/data/RegionData.gd")
	_quest_data = load("res://scripts/data/QuestData.gd")
	_load_backend_data()
	if LLMClient:
		LLMClient.server_status_changed.connect(func(online):
			if online:
				_fetch_from_live_backend_server()
		)
		call_deferred("_fetch_from_live_backend_server")

func _fetch_from_live_backend_server() -> void:
	if not LLMClient:
		return
	var live_data = await LLMClient.fetch_backend_data()
	if not live_data.is_empty():
		backend_data = live_data
		_apply_backend_data()
		print("GameData: Successfully synced live data from Python backend server!")

func _load_backend_data() -> void:
	var paths = [
		"res://data/backend_pokemon_data.json",
		ProjectSettings.globalize_path("res://../../Godot/syntax-error-26/data/backend_pokemon_data.json"),
		ProjectSettings.globalize_path("res://data/backend_pokemon_data.json")
	]
	var loaded = false
	for p in paths:
		if FileAccess.file_exists(p):
			var f = FileAccess.open(p, FileAccess.READ)
			if f:
				var json_str = f.get_as_text()
				f.close()
				var json = JSON.new()
				if json.parse(json_str) == OK and json.data is Dictionary:
					backend_data = json.data
					_apply_backend_data()
					loaded = true
					print("GameData: Successfully loaded backend data from: ", p)
					break
	if not loaded:
		print("GameData: backend_pokemon_data.json not found, using compiled data fallbacks.")

func _apply_backend_data() -> void:
	if backend_data.has("species") and backend_data["species"] is Dictionary:
		for sp_name in backend_data["species"]:
			var sp_info = backend_data["species"][sp_name]
			if PokemonData.SPECIES.has(sp_name):
				for k in sp_info:
					PokemonData.SPECIES[sp_name][k] = sp_info[k]
			else:
				PokemonData.SPECIES[sp_name] = sp_info.duplicate()
	
	if backend_data.has("attacks") and backend_data["attacks"] is Dictionary:
		for atk_name in backend_data["attacks"]:
			var atk_info = backend_data["attacks"][atk_name]
			if AttackData.ATTACKS.has(atk_name):
				for k in atk_info:
					AttackData.ATTACKS[atk_name][k] = atk_info[k]
			else:
				AttackData.ATTACKS[atk_name] = atk_info.duplicate()
	
	if backend_data.has("items") and backend_data["items"] is Dictionary:
		for item_id in backend_data["items"]:
			var item_info = backend_data["items"][item_id]
			if ItemData.ITEMS.has(item_id):
				for k in item_info:
					ItemData.ITEMS[item_id][k] = item_info[k]
			else:
				ItemData.ITEMS[item_id] = item_info.duplicate()

	if backend_data.has("habitats") and backend_data["habitats"] is Dictionary:
		for hab_id in backend_data["habitats"]:
			HabitatData.HABITATS[hab_id] = backend_data["habitats"][hab_id].duplicate(true)

	if backend_data.has("regions") and backend_data["regions"] is Dictionary:
		for reg_id in backend_data["regions"]:
			var reg_info = backend_data["regions"][reg_id]
			if RegionData.REGIONS.has(reg_id):
				for k in reg_info:
					if k == "bounds":
						var b = reg_info[k]
						if b is Array and b.size() >= 4:
							RegionData.REGIONS[reg_id]["bounds"] = {
								"x1": float(b[0]) * 10.0,
								"z1": float(b[1]) * 10.0,
								"x2": float(b[2]) * 10.0,
								"z2": float(b[3]) * 10.0
							}
						elif b is Dictionary:
							RegionData.REGIONS[reg_id]["bounds"] = b
					else:
						RegionData.REGIONS[reg_id][k] = reg_info[k]
			else:
				var new_entry = reg_info.duplicate()
				if new_entry.has("bounds") and new_entry["bounds"] is Array and new_entry["bounds"].size() >= 4:
					var b = new_entry["bounds"]
					new_entry["bounds"] = {
						"x1": float(b[0]) * 10.0,
						"z1": float(b[1]) * 10.0,
						"x2": float(b[2]) * 10.0,
						"z2": float(b[3]) * 10.0
					}
				RegionData.REGIONS[reg_id] = new_entry

	if backend_data.has("quests") and backend_data["quests"] is Dictionary:
		for q_id in backend_data["quests"]:
			var q_info = backend_data["quests"][q_id]
			if QuestData.QUESTS.has(q_id):
				for k in q_info:
					QuestData.QUESTS[q_id][k] = q_info[k]
			else:
				QuestData.QUESTS[q_id] = q_info.duplicate()

	if backend_data.has("move_learning"):
		move_learning_data = backend_data["move_learning"]
	if backend_data.has("personality_traits"):
		personality_traits = backend_data["personality_traits"]

func get_move_learning(species_name: String) -> Array:
	return move_learning_data.get(species_name, [])

func generate_personality() -> Dictionary:
	var rng = RandomNumberGenerator.new()
	rng.randomize()
	var pers = {}
	for trait_name in personality_traits:
		pers[trait_name] = rng.randi_range(1, 100)
	return pers

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
