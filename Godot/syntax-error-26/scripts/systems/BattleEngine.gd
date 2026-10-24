class_name BattleEngine
extends Node
## BattleEngine - Turn-based battle logic for PokémonAI

const PokemonInstance = preload("res://scripts/models/PokemonInstance.gd")
const AttackData = preload("res://scripts/data/AttackData.gd")
const CaptureSystem = preload("res://scripts/systems/CaptureSystem.gd")
const DamageCalculator = preload("res://scripts/systems/DamageCalculator.gd")
const StatusEffectSystem = preload("res://scripts/systems/StatusEffectSystem.gd")
const ItemData = preload("res://scripts/data/ItemData.gd")
const TrainerAI = preload("res://scripts/systems/TrainerAI.gd")

enum BattleState {NOT_STARTED, IN_PROGRESS, VICTORY, DEFEAT, DRAW, ESCAPED, CAPTURED}
enum ActionType {ATTACK, SWITCH, FLEE, CAPTURE, USE_ITEM}

var player_pokemon: PokemonInstance = null
var opponent_pokemon: PokemonInstance = null
var battle_state: BattleState = BattleState.NOT_STARTED
var current_turn: int = 0
var is_wild_battle: bool = true
var events: Array = []
var player_morale: int = 0

# Pending actions
var _player_action: Dictionary = {}
var _opponent_action: Dictionary = {}
var _override_opponent_action: Dictionary = {}

signal turn_resolved(turn_data: Dictionary)
signal battle_over(state: BattleState, events: Array)

# ─── Setup ────────────────────────────────────────────────────────────────────

func start_battle(p_pokemon: PokemonInstance, o_pokemon: PokemonInstance, wild: bool = true) -> void:
	player_pokemon = p_pokemon
	opponent_pokemon = o_pokemon
	is_wild_battle = wild
	battle_state = BattleState.IN_PROGRESS
	current_turn = 0
	events = []
	_player_action = {}
	_opponent_action = {}

func reset() -> void:
	player_pokemon = null
	opponent_pokemon = null
	battle_state = BattleState.NOT_STARTED
	current_turn = 0
	events = []

# ─── Action Selection ─────────────────────────────────────────────────────────

## Queue the player's chosen action
func select_player_action(action_type: ActionType, param: String = "") -> void:
	_player_action = {"type": action_type, "param": param}

## Explicitly set opponent's chosen action (e.g. from local LLM)
func set_override_opponent_action(action_type: ActionType, param: String = "") -> void:
	_override_opponent_action = {"type": action_type, "param": param}

## Updates combat morale affecting damage multipliers
func set_player_morale(morale: int) -> void:
	player_morale = clampi(morale, -10, 10)


## Resolve a full turn. Returns dict with all turn events.
func resolve_turn() -> Dictionary:
	if battle_state != BattleState.IN_PROGRESS:
		return {"state": battle_state, "events": []}
	if _player_action.is_empty():
		return {"state": battle_state, "events": [], "error": "No player action selected"}
	
	current_turn += 1
	var turn_events: Array = []
	
	# Choose opponent action
	_opponent_action = _choose_opponent_action()
	
	# Handle special player actions first (flee/capture/item)
	match _player_action["type"]:
		ActionType.FLEE:
			var flee_result = _attempt_flee()
			turn_events.append(flee_result)
			if flee_result["success"]:
				battle_state = BattleState.ESCAPED
				_player_action = {}
				return _finalize_turn(turn_events)
		
		ActionType.CAPTURE:
			if not is_wild_battle:
				turn_events.append({"type": "message", "text": "You can't capture a trainer's Pokémon!"})
			else:
				var cap_result = CaptureSystem.attempt(opponent_pokemon, GameState.player)
				turn_events.append({"type": "capture_attempt", "data": cap_result})
				if cap_result["success"]:
					battle_state = BattleState.CAPTURED
					_player_action = {}
					return _finalize_turn(turn_events)
		
		ActionType.USE_ITEM:
			var item_events = _use_item(_player_action["param"])
			turn_events.append_array(item_events)
		
		ActionType.SWITCH:
			var switch_events = _switch_pokemon(_player_action["param"])
			turn_events.append_array(switch_events)
	
	# If battle is still going, do attacks
	if battle_state == BattleState.IN_PROGRESS:
		# Determine turn order
		var order = _determine_turn_order()
		for attacker_is_player in order:
			if battle_state != BattleState.IN_PROGRESS:
				break
			if attacker_is_player:
				if _player_action["type"] == ActionType.ATTACK:
					var attack_events = _execute_attack(player_pokemon, opponent_pokemon, _player_action["param"])
					turn_events.append_array(attack_events)
			else:
				if _opponent_action["type"] == ActionType.ATTACK:
					var attack_events = _execute_attack(opponent_pokemon, player_pokemon, _opponent_action["param"])
					turn_events.append_array(attack_events)
			
			# Check terminals after each attack
			var terminal = _check_terminal_state()
			if terminal != BattleState.IN_PROGRESS:
				battle_state = terminal
				break
	
	# End of turn status effects
	if battle_state == BattleState.IN_PROGRESS:
		var status_events = _handle_status_effects_eot()
		turn_events.append_array(status_events)
		var terminal = _check_terminal_state()
		if terminal != BattleState.IN_PROGRESS:
			battle_state = terminal
	
	_player_action = {}
	return _finalize_turn(turn_events)

func _finalize_turn(turn_events: Array) -> Dictionary:
	events.append_array(turn_events)
	var result = {"state": battle_state, "events": turn_events, "turn": current_turn}
	turn_resolved.emit(result)
	EventBus.battle_turn_resolved.emit(result)
	if battle_state != BattleState.IN_PROGRESS:
		battle_over.emit(battle_state, events)
		var result_str = ""
		match battle_state:
			BattleState.VICTORY:
				result_str = "victory"
			BattleState.DEFEAT:
				result_str = "defeat"
			BattleState.ESCAPED:
				result_str = "escaped"
			BattleState.CAPTURED:
				result_str = "captured"
			BattleState.DRAW:
				result_str = "defeat"
		if result_str != "":
			EventBus.battle_ended.emit(result_str)
	return result

# ─── Turn Order ───────────────────────────────────────────────────────────────

## Returns [true, false] or [false, true] — true = player goes first
func _determine_turn_order() -> Array:
	var player_spd = player_pokemon.effective_speed() if player_pokemon else 0
	var opp_spd = opponent_pokemon.effective_speed() if opponent_pokemon else 0
	
	# Check priority moves
	var p_attack_data = AttackData.get_attack(_player_action.get("param", ""))
	var o_attack_data = AttackData.get_attack(_opponent_action.get("param", ""))
	var p_priority = p_attack_data.get("priority", 0)
	var o_priority = o_attack_data.get("priority", 0)
	
	if p_priority > o_priority:
		return [true, false]
	elif o_priority > p_priority:
		return [false, true]
	
	if player_spd > opp_spd:
		return [true, false]
	elif opp_spd > player_spd:
		return [false, true]
	else:
		var rng = RandomNumberGenerator.new()
		rng.randomize()
		if rng.randf() > 0.5:
			return [true, false]
		return [false, true]

# ─── Attack Execution ─────────────────────────────────────────────────────────

func _execute_attack(attacker: PokemonInstance, defender: PokemonInstance, attack_name: String) -> Array:
	var evts = []
	
	if attacker.is_fainted():
		return evts
	
	var attack_data = AttackData.get_attack(attack_name)
	if attack_data.is_empty():
		evts.append({"type": "message", "text": "%s tried to use an unknown move!" % attacker.nickname})
		return evts
	
	# Check paralysis block
	if attacker.paralysis_blocks():
		evts.append({"type": "message", "text": "%s is paralyzed and couldn't move!" % attacker.nickname})
		return evts
	
	# Announce attack
	evts.append({"type": "attack_used", "attacker": attacker.nickname, "attack": attack_name})
	
	# Accuracy check
	var accuracy = attack_data.get("accuracy", 100)
	var rng = RandomNumberGenerator.new()
	rng.randomize()
	if rng.randf() * 100.0 > float(accuracy):
		evts.append({"type": "message", "text": "%s's attack missed!" % attacker.nickname})
		return evts
	
	var power = attack_data.get("power", 0)
	var category = attack_data.get("category", "physical")
	
	if category == "status":
		# Status move
		var effect = attack_data.get("effect", "")
		var effect_target = attack_data.get("effect_target", "")
		if effect != "" and effect_target == "defender":
			var status_result = StatusEffectSystem.apply_status(defender, effect)
			evts.append({"type": "message", "text": status_result["message"]})
		elif effect != "" and effect_target == "self":
			var status_result = StatusEffectSystem.apply_status(attacker, effect)
			evts.append({"type": "message", "text": status_result["message"]})
	elif power > 0:
		# Damaging move
		var calc_result = DamageCalculator.calculate_from_pokemon(attacker, defender, attack_name)
		var damage = calc_result["damage"]
		
		# Apply combat morale modifiers for player Pokemon
		if attacker == player_pokemon:
			if player_morale >= 5:
				damage = int(round(damage * 1.15))
			elif player_morale <= -5:
				damage = max(1, int(round(damage * 0.85)))
		
		# Handle Ghost vs Normal immunity
		var type_eff = calc_result["type_effectiveness"]
		if type_eff == 0.0:
			evts.append({"type": "message", "text": "It had no effect on %s..." % defender.nickname})
			return evts
		
		var actual_damage = defender.take_damage(damage)
		
		var is_player_def = (defender == player_pokemon)
		evts.append({
			"type": "damage_dealt",
			"target": defender.nickname,
			"defender": defender.nickname,
			"attacker": attacker.nickname,
			"is_player_target": is_player_def,
			"damage": actual_damage,
			"is_critical": calc_result["is_critical"],
			"type_effectiveness": type_eff,
			"defender_hp": defender.current_hp,
			"defender_max_hp": defender.max_hp
		})
		
		if attacker == player_pokemon and player_morale >= 5:
			evts.append({"type": "message", "text": "✨ Surging morale boosted %s's strike (+15%% damage)!" % attacker.nickname})
		elif attacker == player_pokemon and player_morale <= -5:
			evts.append({"type": "message", "text": "⚠️ Low morale weakened %s's focus (-15%% damage)..." % attacker.nickname})
		
		if calc_result["message_suffix"] != "":
			evts.append({"type": "message", "text": calc_result["message_suffix"]})
		
		# Leech life: heal attacker for 50% of damage
		var effect = attack_data.get("effect", "")
		if effect == "LEECH":
			var heal_amount = max(1, int(actual_damage * 0.5))
			attacker.heal(heal_amount)
			evts.append({"type": "message", "text": "%s had its energy drained!" % defender.nickname})
		
		# Secondary status effect from attack
		var sec_effect = attack_data.get("effect", "")
		var sec_target = attack_data.get("effect_target", "")
		var sec_chance = attack_data.get("effect_chance", 0)
		if sec_effect != "" and sec_effect != "LEECH" and sec_chance > 0:
			var rng2 = RandomNumberGenerator.new()
			rng2.randomize()
			if rng2.randf() * 100.0 < float(sec_chance):
				var target_pokemon = defender if sec_target == "defender" else attacker
				var status_result = StatusEffectSystem.apply_status(target_pokemon, sec_effect)
				if status_result["success"]:
					evts.append({"type": "message", "text": status_result["message"]})
		
		# Check faint
		if defender.is_fainted():
			evts.append({"type": "fainted", "pokemon": defender.nickname, "is_player": is_player_def})
			EventBus.pokemon_fainted.emit(defender)
	
	return evts

# ─── Status Effects EOT ───────────────────────────────────────────────────────

func _handle_status_effects_eot() -> Array:
	var evts = []
	
	if not player_pokemon.is_fainted():
		var p_events = StatusEffectSystem.process_end_of_turn(player_pokemon)
		for e in p_events:
			evts.append({"type": "eot_status", "data": e, "is_player": true})
			if player_pokemon.is_fainted():
				evts.append({"type": "fainted", "pokemon": player_pokemon.nickname})
				EventBus.pokemon_fainted.emit(player_pokemon)
	
	if not opponent_pokemon.is_fainted():
		var o_events = StatusEffectSystem.process_end_of_turn(opponent_pokemon)
		for e in o_events:
			evts.append({"type": "eot_status", "data": e, "is_player": false})
			if opponent_pokemon.is_fainted():
				evts.append({"type": "fainted", "pokemon": opponent_pokemon.nickname})
				EventBus.pokemon_fainted.emit(opponent_pokemon)
	
	return evts

# ─── Terminal State Check ─────────────────────────────────────────────────────

func _check_terminal_state() -> BattleState:
	var player_fainted = player_pokemon == null or player_pokemon.is_fainted()
	var opp_fainted = opponent_pokemon == null or opponent_pokemon.is_fainted()
	
	if player_fainted and opp_fainted:
		return BattleState.DRAW
	elif player_fainted:
		# Check if any other team member available
		if GameState.player != null and GameState.player.has_living_pokemon():
			return BattleState.IN_PROGRESS  # Can switch
		return BattleState.DEFEAT
	elif opp_fainted:
		return BattleState.VICTORY
	
	return BattleState.IN_PROGRESS

# ─── Flee ─────────────────────────────────────────────────────────────────────

func _attempt_flee() -> Dictionary:
	if not is_wild_battle:
		return {"type": "flee_attempt", "success": false, "message": "Can't flee from a trainer battle!"}
	
	# Flee formula: based on speed comparison
	var player_spd = player_pokemon.effective_speed() if player_pokemon else 1
	var opp_spd = opponent_pokemon.effective_speed() if opponent_pokemon else 1
	var flee_chance = clamp(float(player_spd) / float(opp_spd) * 0.7, 0.25, 0.95)
	
	var rng = RandomNumberGenerator.new()
	rng.randomize()
	var success = rng.randf() < flee_chance
	var msg = "Got away safely!" if success else "Can't escape!"
	return {"type": "flee_attempt", "success": success, "message": msg}

# ─── Item Use ─────────────────────────────────────────────────────────────────

func _use_item(item_id: String) -> Array:
	var evts = []
	var item_data = ItemData.get_item(item_id)
	if item_data.is_empty():
		evts.append({"type": "message", "text": "Item not found!"})
		return evts
	
	if not GameState.player.has_item(item_id):
		evts.append({"type": "message", "text": "You don't have any %s!" % item_data["name"]})
		return evts
	
	GameState.player.remove_item(item_id)
	var effect = item_data.get("effect", "")
	var target = player_pokemon
	
	match effect:
		"heal":
			var amount = item_data.get("heal_amount", 20)
			var healed = target.heal(amount)
			evts.append({"type": "item_used", "item": item_data["name"], "target": target.nickname})
			evts.append({"type": "message", "text": "%s recovered %d HP!" % [target.nickname, healed]})
			evts.append({"type": "hp_update", "pokemon": target.nickname, "is_player": true,
				"hp": target.current_hp, "max_hp": target.max_hp})
		"full_restore":
			target.heal_to_full()
			target.clear_all_statuses()
			evts.append({"type": "item_used", "item": item_data["name"], "target": target.nickname})
			evts.append({"type": "message", "text": "%s was fully restored!" % target.nickname})
			evts.append({"type": "hp_update", "pokemon": target.nickname, "is_player": true,
				"hp": target.current_hp, "max_hp": target.max_hp})
		"cure_poison":
			StatusEffectSystem.cure_status(target, "POISON")
			evts.append({"type": "message", "text": "%s was cured of poison!" % target.nickname})
		"cure_burn":
			StatusEffectSystem.cure_status(target, "BURN")
			evts.append({"type": "message", "text": "%s was cured of its burn!" % target.nickname})
		"cure_paralysis":
			StatusEffectSystem.cure_status(target, "PARALYSIS")
			evts.append({"type": "message", "text": "%s was cured of paralysis!" % target.nickname})
	
	return evts

# ─── Switch ───────────────────────────────────────────────────────────────────

func _switch_pokemon(pokemon_uid: String) -> Array:
	var evts = []
	if GameState.player == null:
		return evts
	
	for p in GameState.player.team:
		if p.unique_id == pokemon_uid and not p.is_fainted():
			evts.append({"type": "message", "text": "Come back, %s!" % player_pokemon.nickname})
			player_pokemon = p
			evts.append({"type": "message", "text": "Go, %s!" % player_pokemon.nickname})
			evts.append({"type": "switch", "pokemon": p.nickname, "is_player": true})
			break
	
	return evts

# ─── Opponent AI ──────────────────────────────────────────────────────────────

func _choose_opponent_action() -> Dictionary:
	if not _override_opponent_action.is_empty():
		var act = _override_opponent_action
		_override_opponent_action = {}
		return act

	if opponent_pokemon == null or opponent_pokemon.attacks.is_empty():
		return {"type": ActionType.ATTACK, "param": "Tackle"}
	
	if is_wild_battle:
		# Wild: random move
		var rng = RandomNumberGenerator.new()
		rng.randomize()
		var move = opponent_pokemon.attacks[rng.randi() % opponent_pokemon.attacks.size()]
		return {"type": ActionType.ATTACK, "param": move}
	else:
		# Trainer: use TrainerAI
		return TrainerAI.choose_action(opponent_pokemon, player_pokemon)
