class_name HabitatData
extends Node
## HabitatData - Wild Pokémon spawning definitions per region

# Each entry: region_id -> Array of spawn candidates
# Each spawn candidate: {species, weight, min_level, max_level, allowed_times}
# allowed_times: Array of strings from ["morning","day","evening","night"] or [] for all times

const HABITATS: Dictionary = {
	"starting_meadow": [
		{"species": "Pidgey",    "weight": 30, "min_level": 2, "max_level": 5,  "allowed_times": ["morning", "day", "evening"]},
		{"species": "Rattata",   "weight": 30, "min_level": 2, "max_level": 5,  "allowed_times": ["evening", "night"]},
		{"species": "Caterpie",  "weight": 20, "min_level": 2, "max_level": 4,  "allowed_times": ["morning", "day"]},
		{"species": "Pikachu",   "weight": 10, "min_level": 3, "max_level": 6,  "allowed_times": []},
		{"species": "Eevee",     "weight": 5,  "min_level": 3, "max_level": 6,  "allowed_times": []},
		{"species": "Bulbasaur", "weight": 5,  "min_level": 3, "max_level": 5,  "allowed_times": ["morning", "day"]}
	],
	"forest_trail": [
		{"species": "Caterpie",  "weight": 30, "min_level": 3, "max_level": 7,  "allowed_times": ["morning", "day"]},
		{"species": "Butterfree","weight": 20, "min_level": 5, "max_level": 10, "allowed_times": ["morning", "day"]},
		{"species": "Zubat",     "weight": 30, "min_level": 4, "max_level": 8,  "allowed_times": ["evening", "night"]},
		{"species": "Growlithe", "weight": 20, "min_level": 5, "max_level": 9,  "allowed_times": []}
	],
	"ancient_shrine_grounds": [
		{"species": "Abra",     "weight": 40, "min_level": 8, "max_level": 14, "allowed_times": []},
		{"species": "Gastly",   "weight": 40, "min_level": 8, "max_level": 13, "allowed_times": ["evening", "night"]},
		{"species": "Pikachu",  "weight": 20, "min_level": 6, "max_level": 11, "allowed_times": []}
	],
	"mountain_pass": [
		{"species": "Geodude",  "weight": 45, "min_level": 8,  "max_level": 15, "allowed_times": []},
		{"species": "Machop",   "weight": 35, "min_level": 8,  "max_level": 14, "allowed_times": []},
		{"species": "Zubat",    "weight": 20, "min_level": 6,  "max_level": 12, "allowed_times": ["evening", "night"]}
	],
	"crystal_lakeside": [
		{"species": "Squirtle", "weight": 40, "min_level": 5, "max_level": 10, "allowed_times": []},
		{"species": "Poliwag",  "weight": 60, "min_level": 4, "max_level": 9,  "allowed_times": []}
	],
	"haunted_ruins": [
		{"species": "Gastly",  "weight": 50, "min_level": 9,  "max_level": 16, "allowed_times": ["evening", "night"]},
		{"species": "Zubat",   "weight": 30, "min_level": 7,  "max_level": 12, "allowed_times": ["evening", "night"]},
		{"species": "Abra",    "weight": 20, "min_level": 8,  "max_level": 13, "allowed_times": []}
	],
	"tall_grass_plains": [
		{"species": "Pikachu",    "weight": 25, "min_level": 5, "max_level": 10, "allowed_times": []},
		{"species": "Charmander", "weight": 25, "min_level": 5, "max_level": 10, "allowed_times": ["morning", "day"]},
		{"species": "Rattata",    "weight": 30, "min_level": 4, "max_level": 8,  "allowed_times": ["evening", "night"]},
		{"species": "Eevee",      "weight": 20, "min_level": 5, "max_level": 10, "allowed_times": []}
	]
}

static func get_habitat(region_id: String) -> Array:
	if HABITATS.has(region_id):
		return HABITATS[region_id]
	return []

static func get_all_region_ids() -> Array:
	return HABITATS.keys()
