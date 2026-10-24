class_name AttackData
extends Node
## AttackData - All attack definitions for PokémonAI
## Each attack: {name, type, power, accuracy, category, effect, effect_target, effect_chance}
## effect: "" | "POISON" | "BURN" | "PARALYSIS" | "STAT_CHANGE"
## effect_target: "defender" | "self"
## category: "physical" | "special" | "status"

const ATTACKS: Dictionary = {
	"Tackle": {
		"name": "Tackle", "type": "Normal", "power": 40, "accuracy": 100,
		"category": "physical", "effect": "", "effect_target": "", "effect_chance": 0
	},
	"Quick Attack": {
		"name": "Quick Attack", "type": "Normal", "power": 40, "accuracy": 100,
		"category": "physical", "effect": "", "effect_target": "", "effect_chance": 0,
		"priority": 1
	},
	"Scratch": {
		"name": "Scratch", "type": "Normal", "power": 40, "accuracy": 100,
		"category": "physical", "effect": "", "effect_target": "", "effect_chance": 0
	},
	"Bite": {
		"name": "Bite", "type": "Normal", "power": 60, "accuracy": 100,
		"category": "physical", "effect": "", "effect_target": "", "effect_chance": 0
	},
	"Hyper Fang": {
		"name": "Hyper Fang", "type": "Normal", "power": 80, "accuracy": 90,
		"category": "physical", "effect": "", "effect_target": "", "effect_chance": 0
	},
	"Headbutt": {
		"name": "Headbutt", "type": "Normal", "power": 70, "accuracy": 100,
		"category": "physical", "effect": "", "effect_target": "", "effect_chance": 0
	},
	"Body Slam": {
		"name": "Body Slam", "type": "Normal", "power": 85, "accuracy": 100,
		"category": "physical", "effect": "PARALYSIS", "effect_target": "defender", "effect_chance": 30
	},
	# Electric
	"Thunder Shock": {
		"name": "Thunder Shock", "type": "Electric", "power": 40, "accuracy": 100,
		"category": "special", "effect": "PARALYSIS", "effect_target": "defender", "effect_chance": 10
	},
	"Thunderbolt": {
		"name": "Thunderbolt", "type": "Electric", "power": 90, "accuracy": 100,
		"category": "special", "effect": "PARALYSIS", "effect_target": "defender", "effect_chance": 10
	},
	"Spark": {
		"name": "Spark", "type": "Electric", "power": 65, "accuracy": 100,
		"category": "physical", "effect": "PARALYSIS", "effect_target": "defender", "effect_chance": 30
	},
	# Fire
	"Ember": {
		"name": "Ember", "type": "Fire", "power": 40, "accuracy": 100,
		"category": "special", "effect": "BURN", "effect_target": "defender", "effect_chance": 10
	},
	"Flamethrower": {
		"name": "Flamethrower", "type": "Fire", "power": 90, "accuracy": 100,
		"category": "special", "effect": "BURN", "effect_target": "defender", "effect_chance": 10
	},
	"Flame Wheel": {
		"name": "Flame Wheel", "type": "Fire", "power": 60, "accuracy": 100,
		"category": "physical", "effect": "BURN", "effect_target": "defender", "effect_chance": 10
	},
	"Fire Fang": {
		"name": "Fire Fang", "type": "Fire", "power": 65, "accuracy": 95,
		"category": "physical", "effect": "BURN", "effect_target": "defender", "effect_chance": 10
	},
	# Water
	"Water Gun": {
		"name": "Water Gun", "type": "Water", "power": 40, "accuracy": 100,
		"category": "special", "effect": "", "effect_target": "", "effect_chance": 0
	},
	"Hydro Pump": {
		"name": "Hydro Pump", "type": "Water", "power": 110, "accuracy": 80,
		"category": "special", "effect": "", "effect_target": "", "effect_chance": 0
	},
	"Bubble": {
		"name": "Bubble", "type": "Water", "power": 40, "accuracy": 100,
		"category": "special", "effect": "", "effect_target": "", "effect_chance": 0
	},
	# Grass
	"Vine Whip": {
		"name": "Vine Whip", "type": "Grass", "power": 45, "accuracy": 100,
		"category": "physical", "effect": "", "effect_target": "", "effect_chance": 0
	},
	"Razor Leaf": {
		"name": "Razor Leaf", "type": "Grass", "power": 55, "accuracy": 95,
		"category": "physical", "effect": "", "effect_target": "", "effect_chance": 0,
		"high_crit": true
	},
	"Solar Beam": {
		"name": "Solar Beam", "type": "Grass", "power": 120, "accuracy": 100,
		"category": "special", "effect": "", "effect_target": "", "effect_chance": 0
	},
	# Poison
	"Poison Powder": {
		"name": "Poison Powder", "type": "Poison", "power": 0, "accuracy": 75,
		"category": "status", "effect": "POISON", "effect_target": "defender", "effect_chance": 100
	},
	"Sludge": {
		"name": "Sludge", "type": "Poison", "power": 65, "accuracy": 100,
		"category": "special", "effect": "POISON", "effect_target": "defender", "effect_chance": 30
	},
	# Flying
	"Gust": {
		"name": "Gust", "type": "Flying", "power": 40, "accuracy": 100,
		"category": "special", "effect": "", "effect_target": "", "effect_chance": 0
	},
	"Wing Attack": {
		"name": "Wing Attack", "type": "Flying", "power": 60, "accuracy": 100,
		"category": "physical", "effect": "", "effect_target": "", "effect_chance": 0
	},
	# Bug
	"Bug Bite": {
		"name": "Bug Bite", "type": "Bug", "power": 60, "accuracy": 100,
		"category": "physical", "effect": "", "effect_target": "", "effect_chance": 0
	},
	"Leech Life": {
		"name": "Leech Life", "type": "Bug", "power": 20, "accuracy": 100,
		"category": "physical", "effect": "LEECH", "effect_target": "self", "effect_chance": 100
	},
	# Rock
	"Rock Throw": {
		"name": "Rock Throw", "type": "Rock", "power": 50, "accuracy": 90,
		"category": "physical", "effect": "", "effect_target": "", "effect_chance": 0
	},
	"Rock Slide": {
		"name": "Rock Slide", "type": "Rock", "power": 75, "accuracy": 90,
		"category": "physical", "effect": "", "effect_target": "", "effect_chance": 0
	},
	# Fighting
	"Low Kick": {
		"name": "Low Kick", "type": "Fighting", "power": 50, "accuracy": 100,
		"category": "physical", "effect": "", "effect_target": "", "effect_chance": 0
	},
	"Karate Chop": {
		"name": "Karate Chop", "type": "Fighting", "power": 50, "accuracy": 100,
		"category": "physical", "effect": "", "effect_target": "", "effect_chance": 0,
		"high_crit": true
	},
	"Brick Break": {
		"name": "Brick Break", "type": "Fighting", "power": 75, "accuracy": 100,
		"category": "physical", "effect": "", "effect_target": "", "effect_chance": 0
	},
	# Ghost
	"Lick": {
		"name": "Lick", "type": "Ghost", "power": 20, "accuracy": 100,
		"category": "physical", "effect": "PARALYSIS", "effect_target": "defender", "effect_chance": 30
	},
	"Night Shade": {
		"name": "Night Shade", "type": "Ghost", "power": 60, "accuracy": 100,
		"category": "special", "effect": "", "effect_target": "", "effect_chance": 0
	},
	"Shadow Ball": {
		"name": "Shadow Ball", "type": "Ghost", "power": 80, "accuracy": 100,
		"category": "special", "effect": "", "effect_target": "", "effect_chance": 0
	},
	# Psychic
	"Confusion": {
		"name": "Confusion", "type": "Psychic", "power": 50, "accuracy": 100,
		"category": "special", "effect": "", "effect_target": "", "effect_chance": 0
	},
	"Psybeam": {
		"name": "Psybeam", "type": "Psychic", "power": 65, "accuracy": 100,
		"category": "special", "effect": "", "effect_target": "", "effect_chance": 0
	},
	"Psychic": {
		"name": "Psychic", "type": "Psychic", "power": 90, "accuracy": 100,
		"category": "special", "effect": "", "effect_target": "", "effect_chance": 0
	},
	# Defense Curl (status - ATK reduction not applicable, treat as non-damaging buff)
	"Defense Curl": {
		"name": "Defense Curl", "type": "Normal", "power": 0, "accuracy": 100,
		"category": "status", "effect": "DEF_UP", "effect_target": "self", "effect_chance": 100
	},
}

## Returns attack data dict or empty dict if not found
static func get_attack(attack_name: String) -> Dictionary:
	if ATTACKS.has(attack_name):
		return ATTACKS[attack_name]
	return {}

## Returns true if attack exists
static func has_attack(attack_name: String) -> bool:
	return ATTACKS.has(attack_name)
