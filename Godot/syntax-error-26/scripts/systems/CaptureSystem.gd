class_name CaptureSystem
extends Node
## CaptureSystem - Handles Poké Ball capture logic

const PokemonInstance = preload("res://scripts/models/PokemonInstance.gd")
const PlayerModel = preload("res://scripts/models/PlayerModel.gd")

## Calculate the probability of capture
## hp_factor: higher = more likely (low HP)
static func calculate_probability(current_hp: int, max_hp: int, level: int) -> float:
	var hp_factor: float = 1.0 - float(current_hp) / float(max_hp)
	var level_penalty: float = float(level) * 0.002
	var raw_capture: float = 0.65 * hp_factor + 0.20 - level_penalty
	return clamp(raw_capture, 0.05, 0.90)

## Attempt to capture a Pokémon using a Poké Ball
## Returns: {accepted, success, message, capture_probability, pokemon}
static func attempt(wild_pokemon: PokemonInstance, player: PlayerModel) -> Dictionary:
	# Check if player has a Poké Ball
	if not player.has_item("poke_ball"):
		return {
			"accepted": false,
			"success": false,
			"message": "You have no Poké Balls!",
			"capture_probability": 0.0,
			"pokemon": null
		}
	
	# Remove the ball
	player.remove_item("poke_ball", 1)
	
	var prob = calculate_probability(wild_pokemon.current_hp, wild_pokemon.max_hp, wild_pokemon.level)
	
	var rng = RandomNumberGenerator.new()
	rng.randomize()
	var roll = rng.randf()
	var success = roll <= prob
	
	var message = ""
	if success:
		# Add to team or collection
		if player.team.size() < player.max_team_size:
			player.add_to_team(wild_pokemon)
			message = "Gotcha! %s was caught and added to your team!" % wild_pokemon.nickname
		else:
			player.add_to_collection(wild_pokemon)
			message = "Gotcha! %s was caught and sent to your collection!" % wild_pokemon.nickname
		EventBus.pokemon_caught.emit(wild_pokemon)
		# Update quest tracking
		EventBus.quest_updated.emit("catch_count", "", 0, 0)  # Trigger QuestSystem catch tracking
	else:
		# Failed capture - probability of almost-catch shake animation varies
		if prob > 0.5:
			message = "Oh no! %s broke free after almost being caught!" % wild_pokemon.nickname
		elif prob > 0.3:
			message = "Darn! %s wiggled free!" % wild_pokemon.nickname
		else:
			message = "The Poké Ball missed %s!" % wild_pokemon.nickname
	
	return {
		"accepted": true,
		"success": success,
		"message": message,
		"capture_probability": prob,
		"pokemon": wild_pokemon if success else null
	}
