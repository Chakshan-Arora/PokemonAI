class_name TrainerAI
extends Node
## TrainerAI - Chooses actions for NPC trainer battles

const PokemonInstance = preload("res://scripts/models/PokemonInstance.gd")
const AttackData = preload("res://scripts/data/AttackData.gd")
const TypeChart = preload("res://scripts/data/TypeChart.gd")

## Choose the best action for a trainer Pokémon
## Returns dict: {type: ActionType, param: String}
static func choose_action(attacker: PokemonInstance, defender: PokemonInstance) -> Dictionary:
	# If HP < 30%, consider switching (placeholder – no team switching for now)
	# So just pick best move
	var best_move = _find_best_move(attacker, defender)
	return {"type": BattleEngine.ActionType.ATTACK, "param": best_move}

## Scores each available move and returns the best one
static func _find_best_move(attacker: PokemonInstance, defender: PokemonInstance) -> String:
	if attacker.attacks.is_empty():
		return "Tackle"
	
	var best_score = -1.0
	var best_move = attacker.attacks[0]
	
	for attack_name in attacker.attacks:
		var attack_data = AttackData.get_attack(attack_name)
		if attack_data.is_empty():
			continue
		
		var power = float(attack_data.get("power", 0))
		var accuracy = float(attack_data.get("accuracy", 100)) / 100.0
		var attack_type = attack_data.get("type", "Normal")
		var category = attack_data.get("category", "physical")
		
		# Status moves get low score unless defender isn't statused
		if category == "status":
			var effect = attack_data.get("effect", "")
			var target = attack_data.get("effect_target", "")
			if target == "defender" and not defender.has_status(effect):
				# Potentially useful
				var score = 30.0 * accuracy
				if score > best_score:
					best_score = score
					best_move = attack_name
			continue
		
		# Type effectiveness
		var type_eff = TypeChart.get_effectiveness(attack_type, defender.get_types())
		if type_eff == 0.0:
			continue  # Immune, skip
		
		# STAB
		var stab = 1.15 if attack_type in attacker.get_types() else 1.0
		
		# Expected damage score
		var score = power * type_eff * stab * accuracy
		
		if score > best_score:
			best_score = score
			best_move = attack_name
	
	return best_move
