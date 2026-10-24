class_name PokemonData
extends Node
## PokemonData - All 16 species definitions for PokémonAI

# Color constants (Color objects as hex strings for serialization)
const TYPE_COLORS: Dictionary = {
	"Normal":   Color(0.66, 0.65, 0.61),
	"Fire":     Color(0.94, 0.33, 0.07),
	"Water":    Color(0.27, 0.56, 0.95),
	"Grass":    Color(0.29, 0.73, 0.24),
	"Electric": Color(0.98, 0.84, 0.07),
	"Poison":   Color(0.63, 0.22, 0.72),
	"Flying":   Color(0.55, 0.75, 0.95),
	"Bug":      Color(0.47, 0.67, 0.07),
	"Ground":   Color(0.55, 0.40, 0.15),
	"Rock":     Color(0.44, 0.40, 0.24),
	"Fighting": Color(0.74, 0.22, 0.18),
	"Psychic":  Color(0.97, 0.33, 0.58),
	"Ghost":    Color(0.27, 0.19, 0.49)
}

# Canonical move learning progression tables (level, attack)
const MOVE_LEARNING: Dictionary = {
	"Pikachu": [[1, "Thunder Shock"], [3, "Quick Attack"], [6, "Tackle"], [10, "Thunderbolt"]],
	"Charmander": [[1, "Scratch"], [3, "Ember"], [6, "Tackle"], [10, "Flamethrower"]],
	"Squirtle": [[1, "Tackle"], [3, "Water Gun"], [6, "Quick Attack"], [10, "Hydro Pump"]],
	"Bulbasaur": [[1, "Tackle"], [3, "Vine Whip"], [6, "Poison Powder"], [10, "Razor Leaf"]],
	"Pidgey": [[1, "Tackle"], [3, "Gust"], [6, "Quick Attack"], [10, "Wing Attack"]],
	"Rattata": [[1, "Tackle"], [3, "Quick Attack"], [6, "Bite"], [10, "Hyper Fang"]],
	"Caterpie": [[1, "Tackle"], [3, "Bug Bite"], [6, "Tackle"]],
	"Butterfree": [[1, "Tackle"], [3, "Gust"], [6, "Confusion"], [10, "Psybeam"]],
	"Geodude": [[1, "Tackle"], [3, "Rock Throw"], [6, "Defense Curl"], [10, "Rock Slide"]],
	"Zubat": [[1, "Leech Life"], [3, "Bite"], [6, "Wing Attack"], [10, "Confuse Ray"]],
	"Machop": [[1, "Low Kick"], [3, "Karate Chop"], [6, "Tackle"], [10, "Brick Break"]],
	"Gastly": [[1, "Lick"], [3, "Confuse Ray"], [6, "Night Shade"], [10, "Shadow Ball"]],
	"Abra": [[1, "Tackle"], [3, "Confusion"], [6, "Psybeam"], [10, "Psychic"]],
	"Eevee": [[1, "Tackle"], [3, "Quick Attack"], [6, "Bite"], [10, "Body Slam"]],
	"Growlithe": [[1, "Bite"], [3, "Ember"], [6, "Flame Wheel"], [10, "Flamethrower"]],
	"Poliwag": [[1, "Water Gun"], [3, "Bubble"], [6, "Body Slam"], [10, "Hydro Pump"]]
}

## Returns all moves learned by a species up to the given level (max 4 most recent)
static func get_moves_for_level(species_name: String, level: int) -> Array:
	var table = MOVE_LEARNING.get(species_name, [])
	var moves: Array = []
	for entry in table:
		var req_lvl = int(entry[0])
		var atk_name = str(entry[1])
		if req_lvl <= level and not moves.has(atk_name):
			moves.append(atk_name)
	if moves.size() > 4:
		moves = moves.slice(moves.size() - 4, moves.size())
	if moves.is_empty():
		var sp = SPECIES.get(species_name, {})
		var av = sp.get("available_attacks", [])
		if not av.is_empty():
			moves.append(av[0])
	return moves

# All species data with level-appropriate base starting attacks
static var SPECIES: Dictionary = {
	"Bulbasaur": {
		"name": "Bulbasaur",
		"types": ["Grass", "Poison"],
		"base_hp": 14,
		"base_attack": 49,
		"base_defense": 49,
		"base_speed": 45,
		"available_attacks": ["Tackle", "Vine Whip"],
		"color": "#4DAE44",
		"description": "A strange seed was planted on its back at birth."
	},
	"Charmander": {
		"name": "Charmander",
		"types": ["Fire"],
		"base_hp": 12,
		"base_attack": 52,
		"base_defense": 43,
		"base_speed": 65,
		"available_attacks": ["Scratch", "Ember"],
		"color": "#F05A0A",
		"description": "The flame on its tail shows the strength of its life force."
	},
	"Squirtle": {
		"name": "Squirtle",
		"types": ["Water"],
		"base_hp": 13,
		"base_attack": 48,
		"base_defense": 65,
		"base_speed": 43,
		"available_attacks": ["Tackle", "Water Gun"],
		"color": "#458FE8",
		"description": "When it retracts its long neck into its shell, it squirts water."
	},
	"Pikachu": {
		"name": "Pikachu",
		"types": ["Electric"],
		"base_hp": 11,
		"base_attack": 55,
		"base_defense": 40,
		"base_speed": 90,
		"available_attacks": ["Thunder Shock", "Quick Attack"],
		"color": "#FAD812",
		"description": "When several of these Pokémon gather, their electricity can build up."
	},
	"Pidgey": {
		"name": "Pidgey",
		"types": ["Normal", "Flying"],
		"base_hp": 12,
		"base_attack": 45,
		"base_defense": 40,
		"base_speed": 56,
		"available_attacks": ["Tackle", "Gust"],
		"color": "#A0C0D0",
		"description": "A common sight in fields and forests. Very docile."
	},
	"Rattata": {
		"name": "Rattata",
		"types": ["Normal"],
		"base_hp": 10,
		"base_attack": 56,
		"base_defense": 35,
		"base_speed": 72,
		"available_attacks": ["Tackle", "Quick Attack"],
		"color": "#A0609A",
		"description": "Will chew on anything with its fangs. Very tenacious."
	},
	"Caterpie": {
		"name": "Caterpie",
		"types": ["Bug"],
		"base_hp": 12,
		"base_attack": 30,
		"base_defense": 35,
		"base_speed": 45,
		"available_attacks": ["Tackle", "Bug Bite"],
		"color": "#78AA46",
		"description": "Its feet have suction cups, which it uses to climb."
	},
	"Butterfree": {
		"name": "Butterfree",
		"types": ["Bug", "Flying"],
		"base_hp": 16,
		"base_attack": 45,
		"base_defense": 50,
		"base_speed": 70,
		"available_attacks": ["Tackle", "Gust"],
		"color": "#78B0D8",
		"description": "In battle, it flaps its wings at great speed."
	},
	"Geodude": {
		"name": "Geodude",
		"types": ["Rock", "Ground"],
		"base_hp": 12,
		"base_attack": 80,
		"base_defense": 100,
		"base_speed": 20,
		"available_attacks": ["Tackle", "Rock Throw"],
		"color": "#907840",
		"description": "Found in fields and mountains. Mistaken for rocks often."
	},
	"Zubat": {
		"name": "Zubat",
		"types": ["Poison", "Flying"],
		"base_hp": 11,
		"base_attack": 45,
		"base_defense": 35,
		"base_speed": 55,
		"available_attacks": ["Leech Life", "Bite"],
		"color": "#6038A0",
		"description": "Forms colonies in dark places. Uses ultrasonic waves."
	},
	"Machop": {
		"name": "Machop",
		"types": ["Fighting"],
		"base_hp": 18,
		"base_attack": 80,
		"base_defense": 50,
		"base_speed": 35,
		"available_attacks": ["Low Kick", "Karate Chop"],
		"color": "#C03020",
		"description": "Its whole body is composed of muscles. Never gets tired."
	},
	"Gastly": {
		"name": "Gastly",
		"types": ["Ghost", "Poison"],
		"base_hp": 10,
		"base_attack": 35,
		"base_defense": 30,
		"base_speed": 80,
		"available_attacks": ["Lick", "Confuse Ray"],
		"color": "#40307C",
		"description": "Almost invisible in darkness. Its body is made of gas."
	},
	"Abra": {
		"name": "Abra",
		"types": ["Psychic"],
		"base_hp": 8,
		"base_attack": 20,
		"base_defense": 15,
		"base_speed": 90,
		"available_attacks": ["Tackle", "Confusion"],
		"color": "#F855C8",
		"description": "Using its ability to read minds, it will identify impending danger."
	},
	"Eevee": {
		"name": "Eevee",
		"types": ["Normal"],
		"base_hp": 14,
		"base_attack": 55,
		"base_defense": 50,
		"base_speed": 55,
		"available_attacks": ["Tackle", "Quick Attack"],
		"color": "#C8A040",
		"description": "Its genetic code is irregular. It may mutate if it is exposed."
	},
	"Growlithe": {
		"name": "Growlithe",
		"types": ["Fire"],
		"base_hp": 14,
		"base_attack": 70,
		"base_defense": 45,
		"base_speed": 60,
		"available_attacks": ["Bite", "Ember"],
		"color": "#E06010",
		"description": "Very protective of its territory. It will bark at any threat."
	},
	"Poliwag": {
		"name": "Poliwag",
		"types": ["Water"],
		"base_hp": 12,
		"base_attack": 50,
		"base_defense": 40,
		"base_speed": 90,
		"available_attacks": ["Water Gun", "Bubble"],
		"color": "#3068D8",
		"description": "Its newly grown legs prevent it from running. It's more adept at swimming."
	}
}

## Returns species data dict or empty dict if not found
static func get_species(species_name: String) -> Dictionary:
	if SPECIES.has(species_name):
		return SPECIES[species_name]
	return {}

## Returns true if species exists
static func has_species(species_name: String) -> bool:
	return SPECIES.has(species_name)

## Returns the primary type color for a species
static func get_species_color(species_name: String) -> Color:
	if not SPECIES.has(species_name):
		return Color.GRAY
	var sp = SPECIES[species_name]
	if sp["types"].size() > 0:
		var primary_type = sp["types"][0]
		if TYPE_COLORS.has(primary_type):
			return TYPE_COLORS[primary_type]
	return Color.GRAY

## Returns all species names
static func get_all_species_names() -> Array:
	return SPECIES.keys()

## Returns the starter species names
static func get_starters() -> Array:
	return ["Bulbasaur", "Charmander", "Squirtle"]

## Returns the PMD portrait texture for a species, or null if not found
static func get_portrait_texture(species_name: String) -> Texture2D:
	var path = "res://assets/sprites/portraits/%s.png" % species_name
	if ResourceLoader.exists(path):
		return load(path) as Texture2D
	return null

## Returns the battle front sprite texture for a species
static func get_front_sprite_texture(species_name: String) -> Texture2D:
	var path = "res://assets/sprites/pokemon/%s_front.png" % species_name
	if ResourceLoader.exists(path):
		return load(path) as Texture2D
	return null

## Returns the battle back sprite texture for a species
static func get_back_sprite_texture(species_name: String) -> Texture2D:
	var path = "res://assets/sprites/pokemon/%s_back.png" % species_name
	if ResourceLoader.exists(path):
		return load(path) as Texture2D
	return null
