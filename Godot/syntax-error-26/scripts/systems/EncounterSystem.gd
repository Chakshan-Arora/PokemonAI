class_name EncounterSystem
extends Node
## EncounterSystem - Detects wild Pokémon encounters via step counting

const PokemonInstance = preload("res://scripts/models/PokemonInstance.gd")
const RegionData = preload("res://scripts/data/RegionData.gd")
const SpawnSystem = preload("res://scripts/systems/SpawnSystem.gd")

const MIN_STEPS_BEFORE_ENCOUNTER: int = 15
const MAX_STEPS_BEFORE_ENCOUNTER: int = 35

var _steps_until_encounter: int = 0
var _in_tall_grass: bool = false
var _current_region_id: String = ""

signal encounter_triggered(wild_pokemon: PokemonInstance)

func _ready() -> void:
	_randomize_step_counter()

## Call this when the player takes a step (distance-based or key-press based)
func on_player_step(region_id: String, is_in_tall_grass: bool) -> void:
	if GameState.is_in_battle:
		return
	if not is_in_tall_grass:
		return
	
	_current_region_id = region_id
	_steps_until_encounter -= 1
	
	if _steps_until_encounter <= 0:
		_randomize_step_counter()
		_try_trigger_encounter(region_id)

func _try_trigger_encounter(region_id: String) -> void:
	# Check region's encounter rate
	var region_data = RegionData.get_region(region_id)
	var encounter_rate = region_data.get("encounter_rate", 0.15)
	
	var rng = RandomNumberGenerator.new()
	rng.randomize()
	if rng.randf() > encounter_rate:
		return
	
	var time_of_day = GameState.get_time_of_day()
	var wild_pokemon: PokemonInstance = null
	
	# If live Python backend is online, query HabitatManager directly
	var llm = get_node_or_null("/root/LLMClient")
	if llm and llm.is_server_online:
		var b_mon = await llm.generate_wild_pokemon(region_id, time_of_day)
		if not b_mon.is_empty():
			wild_pokemon = PokemonInstance.from_dict(b_mon)
	
	if wild_pokemon == null:
		wild_pokemon = SpawnSystem.create_wild_pokemon(region_id, time_of_day)
	if wild_pokemon == null:
		return
	
	encounter_triggered.emit(wild_pokemon)
	EventBus.wild_encounter_triggered.emit(wild_pokemon.species_name, wild_pokemon.level)

func _randomize_step_counter() -> void:
	var rng = RandomNumberGenerator.new()
	rng.randomize()
	_steps_until_encounter = rng.randi_range(MIN_STEPS_BEFORE_ENCOUNTER, MAX_STEPS_BEFORE_ENCOUNTER)

## Force an encounter in the given region (for testing)
func force_encounter(region_id: String) -> void:
	_try_trigger_encounter(region_id)
