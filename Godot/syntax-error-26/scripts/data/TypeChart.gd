class_name TypeChart
extends Node
## TypeChart - Type effectiveness lookup for PokémonAI
## Data ported from the Python source's type_effectiveness table.

# TYPE_CHART[attacking_type][defending_type] = multiplier
# Only entries differing from 1.0 are stored; missing = 1.0
const TYPE_CHART: Dictionary = {
	"Normal": {
		"Rock": 0.5,
		"Ghost": 0.0
	},
	"Fire": {
		"Grass": 2.0,
		"Bug": 2.0,
		"Fire": 0.5,
		"Water": 0.5,
		"Rock": 0.5
	},
	"Water": {
		"Fire": 2.0,
		"Ground": 2.0,
		"Rock": 2.0,
		"Water": 0.5,
		"Grass": 0.5
	},
	"Grass": {
		"Water": 2.0,
		"Ground": 2.0,
		"Rock": 2.0,
		"Fire": 0.5,
		"Grass": 0.5,
		"Poison": 0.5,
		"Flying": 0.5,
		"Bug": 0.5
	},
	"Electric": {
		"Water": 2.0,
		"Flying": 2.0,
		"Grass": 0.5,
		"Electric": 0.5,
		"Ground": 0.0
	},
	"Poison": {
		"Grass": 2.0,
		"Poison": 0.5,
		"Ground": 0.5,
		"Rock": 0.5,
		"Ghost": 0.5
	},
	"Flying": {
		"Grass": 2.0,
		"Fighting": 2.0,
		"Bug": 2.0,
		"Electric": 0.5,
		"Rock": 0.5
	},
	"Bug": {
		"Grass": 2.0,
		"Psychic": 2.0,
		"Fire": 0.5,
		"Fighting": 0.5,
		"Flying": 0.5,
		"Poison": 0.5,
		"Ghost": 0.5
	},
	"Ground": {
		"Fire": 2.0,
		"Electric": 2.0,
		"Poison": 2.0,
		"Rock": 2.0,
		"Grass": 0.5,
		"Bug": 0.5,
		"Flying": 0.0
	},
	"Rock": {
		"Fire": 2.0,
		"Flying": 2.0,
		"Bug": 2.0,
		"Fighting": 0.5,
		"Ground": 0.5
	},
	"Fighting": {
		"Normal": 2.0,
		"Rock": 2.0,
		"Poison": 0.5,
		"Flying": 0.5,
		"Psychic": 0.5,
		"Bug": 0.5,
		"Ghost": 0.0
	},
	"Psychic": {
		"Fighting": 2.0,
		"Poison": 2.0,
		"Psychic": 0.5
	},
	"Ghost": {
		"Ghost": 2.0,
		"Psychic": 2.0,
		"Normal": 0.0
	}
}

## Calculate total type effectiveness of an attack against a defending Pokémon.
## attacking_type: String (e.g. "Fire")
## defending_types: Array[String] (e.g. ["Grass", "Poison"])
## Returns: float multiplier (0.0, 0.25, 0.5, 1.0, 2.0, 4.0)
static func get_effectiveness(attacking_type: String, defending_types: Array) -> float:
	var multiplier: float = 1.0
	if not TYPE_CHART.has(attacking_type):
		return multiplier
	var atk_chart: Dictionary = TYPE_CHART[attacking_type]
	for def_type in defending_types:
		if atk_chart.has(def_type):
			multiplier *= atk_chart[def_type]
	return multiplier

## Returns a human-readable effectiveness message
static func get_effectiveness_message(multiplier: float) -> String:
	if multiplier == 0.0:
		return "It had no effect..."
	elif multiplier < 1.0:
		return "It's not very effective..."
	elif multiplier > 1.0:
		return "It's super effective!"
	return ""
