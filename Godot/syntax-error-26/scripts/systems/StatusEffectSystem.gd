class_name StatusEffectSystem
extends Node
## StatusEffectSystem - Manages status conditions for PokémonAI

const PokemonInstance = preload("res://scripts/models/PokemonInstance.gd")

## Attempt to apply a status to a Pokémon
## Returns dict: {success, message}
static func apply_status(pokemon: PokemonInstance, status_type: String) -> Dictionary:
	if pokemon.is_fainted():
		return {"success": false, "message": "%s is already fainted!" % pokemon.nickname}
	
	# Check type immunity
	var types = pokemon.get_types()
	match status_type:
		"POISON":
			if "Poison" in types or "Steel" in types:
				return {"success": false, "message": "%s is immune to poison!" % pokemon.nickname}
		"BURN":
			if "Fire" in types:
				return {"success": false, "message": "%s is immune to burn!" % pokemon.nickname}
		"PARALYSIS":
			if "Electric" in types:
				return {"success": false, "message": "%s is immune to paralysis!" % pokemon.nickname}
	
	if pokemon.has_status(status_type):
		return {"success": false, "message": "%s is already %s!" % [pokemon.nickname, status_type.to_lower()]}
	
	var success = pokemon.apply_status(status_type)
	if success:
		EventBus.pokemon_status_applied.emit(pokemon, status_type)
		return {"success": true, "message": _get_applied_message(pokemon.nickname, status_type)}
	
	return {"success": false, "message": "It had no effect!"}

## Cure a specific status
static func cure_status(pokemon: PokemonInstance, status_type: String) -> Dictionary:
	if not pokemon.has_status(status_type):
		return {"success": false, "message": "%s doesn't have %s!" % [pokemon.nickname, status_type]}
	pokemon.clear_status(status_type)
	EventBus.pokemon_status_cleared.emit(pokemon, status_type)
	return {"success": true, "message": "%s was cured of %s!" % [pokemon.nickname, status_type]}

## Cure all statuses
static func cure_all_statuses(pokemon: PokemonInstance) -> void:
	pokemon.clear_all_statuses()
	EventBus.pokemon_status_cleared.emit(pokemon, "ALL")

## Process end-of-turn status effects. Returns Array of event dicts.
static func process_end_of_turn(pokemon: PokemonInstance) -> Array:
	return pokemon.tick_status_effects()

## Returns formatted status label (for UI)
static func get_status_label(pokemon: PokemonInstance) -> String:
	var labels = []
	for s in pokemon.status_effects:
		labels.append(s["type"])
	return " ".join(labels)

static func _get_applied_message(nickname: String, status_type: String) -> String:
	match status_type:
		"POISON":
			return "%s was poisoned!" % nickname
		"BURN":
			return "%s was burned!" % nickname
		"PARALYSIS":
			return "%s is paralyzed! It may be unable to move!" % nickname
	return "%s gained %s status!" % [nickname, status_type]
