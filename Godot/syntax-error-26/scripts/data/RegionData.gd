class_name RegionData
extends Node
## RegionData - World region definitions for PokémonAI
## Python (x,y) → Godot (x*10, 0, z*10) scaled 10x
## Python y → Godot z axis

const REGIONS: Dictionary = {
	"starting_meadow": {
		"region_id": "starting_meadow",
		"name": "Starting Meadow",
		"description": "A peaceful meadow where new trainers begin their journey.",
		"bounds": {"x1": 0.0, "z1": 0.0, "x2": 100.0, "z2": 100.0},
		"color": "#5DB855",
		"has_tall_grass": true,
		"encounter_rate": 0.15,
		"music": "meadow_theme"
	},
	"forest_trail": {
		"region_id": "forest_trail",
		"name": "Forest Trail",
		"description": "A winding trail through dense forest. Bug and Flying types abound.",
		"bounds": {"x1": 110.0, "z1": 0.0, "x2": 200.0, "z2": 150.0},
		"color": "#2D6B2D",
		"has_tall_grass": true,
		"encounter_rate": 0.20,
		"music": "forest_theme"
	},
	"ancient_shrine_grounds": {
		"region_id": "ancient_shrine_grounds",
		"name": "Ancient Shrine Grounds",
		"description": "Mysterious ruins emanating psychic energy. Rare Pokémon dwell here.",
		"bounds": {"x1": 210.0, "z1": 200.0, "x2": 300.0, "z2": 300.0},
		"color": "#7B44BE",
		"has_tall_grass": true,
		"encounter_rate": 0.18,
		"music": "shrine_theme"
	},
	"mountain_pass": {
		"region_id": "mountain_pass",
		"name": "Mountain Pass",
		"description": "A rugged mountain path. Strong Rock and Fighting types live here.",
		"bounds": {"x1": 310.0, "z1": 0.0, "x2": 400.0, "z2": 100.0},
		"color": "#888888",
		"has_tall_grass": false,
		"encounter_rate": 0.25,
		"music": "mountain_theme"
	},
	"crystal_lakeside": {
		"region_id": "crystal_lakeside",
		"name": "Crystal Lakeside",
		"description": "A crystal-clear lake with sparkling water. Water Pokémon thrive here.",
		"bounds": {"x1": 0.0, "z1": 110.0, "x2": 100.0, "z2": 200.0},
		"color": "#4488EE",
		"has_tall_grass": true,
		"encounter_rate": 0.18,
		"music": "lake_theme"
	},
	"haunted_ruins": {
		"region_id": "haunted_ruins",
		"name": "Haunted Ruins",
		"description": "Ancient ruins shrouded in mist. Ghost Pokémon haunt the darkness.",
		"bounds": {"x1": 110.0, "z1": 160.0, "x2": 200.0, "z2": 250.0},
		"color": "#444444",
		"has_tall_grass": false,
		"encounter_rate": 0.22,
		"music": "haunted_theme"
	},
	"tall_grass_plains": {
		"region_id": "tall_grass_plains",
		"name": "Tall Grass Plains",
		"description": "Expansive plains with tall grass. Various Pokémon can be found here.",
		"bounds": {"x1": 210.0, "z1": 100.0, "x2": 300.0, "z2": 190.0},
		"color": "#99CC55",
		"has_tall_grass": true,
		"encounter_rate": 0.20,
		"music": "plains_theme"
	}
}

static func get_region(region_id: String) -> Dictionary:
	if REGIONS.has(region_id):
		return REGIONS[region_id]
	return {}

static func get_all_region_ids() -> Array:
	return REGIONS.keys()

## Returns which region a 3D position belongs to, or "" if none
static func get_region_at_position(world_x: float, world_z: float) -> String:
	for region_id in REGIONS:
		var r = REGIONS[region_id]
		var b = r["bounds"]
		if world_x >= b["x1"] and world_x <= b["x2"] and world_z >= b["z1"] and world_z <= b["z2"]:
			return region_id
	return ""
