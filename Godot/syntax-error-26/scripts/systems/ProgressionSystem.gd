class_name ProgressionSystem
extends Node
## ProgressionSystem - XP and leveling for PokémonAI

const PokemonInstance = preload("res://scripts/models/PokemonInstance.gd")

const MAX_LEVEL: int = 100

static func xp_for_next_level(level: int) -> int:
	return level * 100

## Apply XP to a pokemon, handling multi-level gains
## Returns: {levels_gained, old_level, new_level, hp_gained, xp_added}
static func apply_xp(pokemon: PokemonInstance, xp: int) -> Dictionary:
	var result = {
		"levels_gained": 0,
		"old_level": pokemon.level,
		"new_level": pokemon.level,
		"hp_gained": 0,
		"xp_added": xp
	}
	
	if pokemon.level >= MAX_LEVEL:
		result["xp_added"] = 0
		return result
	
	var level_up_result = pokemon.gain_xp(xp)
	result["levels_gained"] = level_up_result["levels_gained"]
	result["new_level"] = level_up_result["new_level"]
	result["hp_gained"] = level_up_result["hp_gained"]
	
	# Emit level up events
	if result["levels_gained"] > 0:
		EventBus.level_up.emit(pokemon, result["old_level"], result["new_level"])
	
	return result

## Calculate XP rewarded from defeating a Pokémon
static func calculate_xp_reward(defeated_pokemon: PokemonInstance, is_wild: bool) -> int:
	var base_xp: int = 50 + (defeated_pokemon.level * 5)
	if not is_wild:
		base_xp = int(base_xp * 1.5)
	return base_xp

## Distribute XP to all non-fainted team members after a battle
## Returns Array of result dicts
static func distribute_xp_to_team(team: Array, defeated: PokemonInstance, is_wild: bool) -> Array:
	var results = []
	var base_xp = calculate_xp_reward(defeated, is_wild)
	for pokemon in team:
		if not pokemon.is_fainted():
			var result = apply_xp(pokemon, base_xp)
			result["pokemon"] = pokemon
			result["xp_earned"] = base_xp
			results.append(result)
	return results
