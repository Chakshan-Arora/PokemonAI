class_name SpawnSystem
extends Node
## SpawnSystem - Manages wild Pokémon spawning based on region and time of day

const HabitatData = preload("res://scripts/data/HabitatData.gd")
const PokemonInstance = preload("res://scripts/models/PokemonInstance.gd")

## Pick a random species from a region's habitat using weighted selection
## Returns: {species_name, level} or {} if none available
static func pick_spawn(region_id: String, time_of_day: String) -> Dictionary:
	var candidates = HabitatData.get_habitat(region_id)
	if candidates.is_empty():
		return {}
	
	# Filter by time of day
	var valid = []
	for candidate in candidates:
		var allowed = candidate.get("allowed_times", [])
		if allowed.is_empty() or time_of_day in allowed:
			valid.append(candidate)
	
	if valid.is_empty():
		return {}
	
	# Weighted random selection
	var total_weight = 0
	for c in valid:
		total_weight += c.get("weight", 1)
	
	var rng = RandomNumberGenerator.new()
	rng.randomize()
	var roll = rng.randi_range(0, total_weight - 1)
	
	var accumulated = 0
	var chosen = valid[0]
	for c in valid:
		accumulated += c.get("weight", 1)
		if roll < accumulated:
			chosen = c
			break
	
	# Pick random level in range
	var min_lvl = chosen.get("min_level", 2)
	var max_lvl = chosen.get("max_level", 5)
	var level = rng.randi_range(min_lvl, max_lvl)
	
	return {"species_name": chosen["species"], "level": level}

## Create a PokemonInstance for a wild spawn
static func create_wild_pokemon(region_id: String, time_of_day: String) -> PokemonInstance:
	var spawn_data = pick_spawn(region_id, time_of_day)
	if spawn_data.is_empty():
		return null
	return PokemonInstance.create(spawn_data["species_name"], spawn_data["level"])
