class_name PokemonInstance
## PokemonInstance - Represents one live Pokémon (not a Node, plain class).
## HP formula: max_hp = base_hp + (level * 2)

const PokemonData = preload("res://scripts/data/PokemonData.gd")

var species_name: String = ""
var nickname: String = ""
var level: int = 1
var experience: int = 0
var current_hp: int = 0
var max_hp: int = 0
var bond: float = 0.0         # 0–100
var obedience: float = 100.0  # 0–100
var attacks: Array = []       # Array of attack name strings (max 4)
var trained_atk: int = 0
var trained_def: int = 0
var trained_spd: int = 0
var status_effects: Array = []  # Array of Dicts: {type, turns_remaining}
var unique_id: String = ""
var personality: Dictionary = {
	"aggression": 50,
	"curiosity": 50,
	"fear": 50,
	"sociability": 50,
	"loyalty": 50,
	"confidence": 50
}
var awarded_level_moves: Array = []

# Cached base stats (populated from PokemonData at creation)
var _base_hp: int = 0
var _base_attack: int = 0
var _base_defense: int = 0
var _base_speed: int = 0
var _types: Array = []
var types: Array:
	get:
		return _types.duplicate()

func get_display_name() -> String:
	return nickname if nickname != "" else species_name

func get_xp_for_next_level() -> int:
	return level * 100

func heal_full() -> int:
	var old = current_hp
	heal_to_full()
	clear_all_statuses()
	return max_hp - old

static func generate_random_personality() -> Dictionary:
	var rng = RandomNumberGenerator.new()
	rng.randomize()
	return {
		"aggression": rng.randi_range(1, 100),
		"curiosity": rng.randi_range(1, 100),
		"fear": rng.randi_range(1, 100),
		"sociability": rng.randi_range(1, 100),
		"loyalty": rng.randi_range(1, 100),
		"confidence": rng.randi_range(1, 100)
	}

func get_dominant_traits() -> String:
	if personality.is_empty():
		return "Neutral"
	var traits_sorted = []
	for k in personality.keys():
		traits_sorted.append({"name": str(k).capitalize(), "value": int(personality[k])})
	traits_sorted.sort_custom(func(a, b): return a["value"] > b["value"])
	if traits_sorted.size() >= 2:
		return "%s & %s" % [traits_sorted[0]["name"], traits_sorted[1]["name"]]
	elif traits_sorted.size() == 1:
		return traits_sorted[0]["name"]
	return "Neutral"

# ─── Constructor ──────────────────────────────────────────────────────────────

static func create(p_species_name: String, p_level: int, p_nickname: String = "", p_personality: Dictionary = {}):
	var inst = new()
	inst.species_name = p_species_name
	inst.nickname = p_nickname if p_nickname != "" else p_species_name
	inst.level = p_level
	inst.unique_id = _generate_uid()
	if not p_personality.is_empty():
		inst.personality = p_personality.duplicate()
	else:
		inst.personality = generate_random_personality()

	var species_data = PokemonData.get_species(p_species_name)
	if species_data.is_empty():
		push_error("PokemonInstance: Unknown species '%s'" % p_species_name)
		return inst

	inst._base_hp = species_data["base_hp"]
	inst._base_attack = species_data["base_attack"]
	inst._base_defense = species_data["base_defense"]
	inst._base_speed = species_data["base_speed"]
	inst._types = species_data["types"].duplicate()

	inst.max_hp = inst._base_hp + (p_level * 2)
	inst.current_hp = inst.max_hp

	# Assign level-appropriate attacks based on canonical move learning tables
	inst.attacks = PokemonData.get_moves_for_level(p_species_name, p_level)

	return inst

static func _generate_uid() -> String:
	var rng = RandomNumberGenerator.new()
	rng.randomize()
	return "%d_%d" % [Time.get_ticks_msec(), rng.randi()]

# ─── Core Stats ───────────────────────────────────────────────────────────────

func effective_attack() -> int:
	var base = _base_attack + trained_atk
	# Burn halves effective attack
	if has_status("BURN"):
		base = int(base * 0.5)
	return max(1, base)

func effective_defense() -> int:
	return max(1, _base_defense + trained_def)

func effective_speed() -> int:
	# Paralysis halves speed
	var spd = _base_speed + trained_spd
	if has_status("PARALYSIS"):
		spd = int(spd * 0.5)
	return max(1, spd)

func get_types() -> Array:
	return _types.duplicate()

# ─── HP / Damage ──────────────────────────────────────────────────────────────

func take_damage(amount: int) -> int:
	var actual = min(amount, current_hp)
	current_hp -= actual
	return actual

func heal(amount: int) -> int:
	var old_hp = current_hp
	current_hp = min(current_hp + amount, max_hp)
	return current_hp - old_hp

func heal_to_full() -> void:
	current_hp = max_hp

func is_fainted() -> bool:
	return current_hp <= 0

func hp_percent() -> float:
	if max_hp == 0:
		return 0.0
	return float(current_hp) / float(max_hp)

# ─── Experience / Levelling ───────────────────────────────────────────────────

## Returns dict: {levels_gained, old_level, new_level, hp_gained}
func gain_xp(amount: int) -> Dictionary:
	var result = {"levels_gained": 0, "old_level": level, "new_level": level, "hp_gained": 0}
	experience += amount
	while level < 100:
		var xp_needed = level * 100
		if experience >= xp_needed:
			experience -= xp_needed
			_level_up()
			result["levels_gained"] += 1
			result["hp_gained"] += 2
		else:
			break
	result["new_level"] = level
	return result

func _level_up() -> void:
	level += 1
	var old_max = max_hp
	max_hp = _base_hp + (level * 2)
	var hp_gain = max_hp - old_max
	if not is_fainted():
		current_hp += hp_gain
	_check_level_up_moves()

func _check_level_up_moves() -> void:
	var table = PokemonData.MOVE_LEARNING.get(species_name, [])
	for entry in table:
		var req_lvl = int(entry[0])
		var atk_name = str(entry[1])
		if req_lvl == level and not attacks.has(atk_name):
			if attacks.size() < 4:
				attacks.append(atk_name)
				awarded_level_moves.append(atk_name)
				EventBus.show_message.emit("%s learned %s!" % [get_display_name(), atk_name])
			else:
				var old_move = attacks[0]
				attacks.remove_at(0)
				attacks.append(atk_name)
				awarded_level_moves.append(atk_name)
				EventBus.show_message.emit("%s learned %s in place of %s!" % [get_display_name(), atk_name, old_move])

func xp_to_next_level() -> int:
	return (level * 100) - experience

# ─── Status Effects ───────────────────────────────────────────────────────────

func has_status(status_type: String) -> bool:
	for s in status_effects:
		if s["type"] == status_type:
			return true
	return false

func apply_status(status_type: String, turns: int = -1) -> bool:
	if has_status(status_type):
		return false
	var rng = RandomNumberGenerator.new()
	rng.randomize()
	var actual_turns = turns if turns > 0 else rng.randi_range(3, 5)
	status_effects.append({"type": status_type, "turns_remaining": actual_turns})
	return true

func clear_status(status_type: String) -> void:
	for i in range(status_effects.size() - 1, -1, -1):
		if status_effects[i]["type"] == status_type:
			status_effects.remove_at(i)

func clear_all_statuses() -> void:
	status_effects.clear()

## Ticks status effects at end of turn. Returns events array.
func tick_status_effects() -> Array:
	var events = []
	for i in range(status_effects.size() - 1, -1, -1):
		var s = status_effects[i]
		match s["type"]:
			"POISON":
				var dmg = max(1, int(max_hp / 8.0))
				take_damage(dmg)
				events.append({"type": "POISON_DAMAGE", "damage": dmg, "pokemon": nickname})
			"BURN":
				var dmg = max(1, int(max_hp / 16.0))
				take_damage(dmg)
				events.append({"type": "BURN_DAMAGE", "damage": dmg, "pokemon": nickname})
		s["turns_remaining"] -= 1
		if s["turns_remaining"] <= 0:
			var cleared_type = s["type"]
			status_effects.remove_at(i)
			events.append({"type": "STATUS_CLEARED", "status": cleared_type, "pokemon": nickname})
	return events

## Returns true if paralysis prevents action this turn
func paralysis_blocks() -> bool:
	if not has_status("PARALYSIS"):
		return false
	var rng = RandomNumberGenerator.new()
	rng.randomize()
	return rng.randf() < 0.25

# ─── Serialization ────────────────────────────────────────────────────────────

func to_dict() -> Dictionary:
	var clean_pers: Dictionary = {}
	if personality is Dictionary:
		for k in personality:
			clean_pers[k] = int(round(float(personality[k])))

	return {
		"species": species_name,
		"species_name": species_name,
		"nickname": nickname,
		"level": level,
		"experience": experience,
		"current_hp": min(current_hp, max_hp),
		"max_hp": max_hp,
		"bond": int(round(bond)),
		"obedience": int(round(obedience)),
		"personality": clean_pers,
		"attacks": attacks.duplicate(),
		"trained_atk": trained_atk,
		"trained_def": trained_def,
		"trained_spd": trained_spd,
		"trained_stats": {
			"attack": trained_atk,
			"defense": trained_def,
			"speed": trained_spd
		},
		"awarded_level_moves": awarded_level_moves.duplicate(),
		"status_effects": status_effects.duplicate(true),
		"unique_id": unique_id
	}

static func from_dict(d: Dictionary):
	var s_name = d.get("species", d.get("species_name", ""))
	var lvl = int(d.get("level", 1))
	var p_pers = d.get("personality", {})
	var inst = create(s_name, lvl, "", p_pers)
	var nick = d.get("nickname")
	if nick != null and str(nick) != "":
		inst.nickname = str(nick)
	inst.experience = int(d.get("experience", 0))
	inst.max_hp = int(d.get("max_hp", inst.max_hp))
	inst.current_hp = min(int(d.get("current_hp", inst.max_hp)), inst.max_hp)
	inst.bond = float(d.get("bond", 0.0))
	inst.obedience = float(d.get("obedience", 100.0))
	inst.awarded_level_moves = d.get("awarded_level_moves", []).duplicate()
	if d.has("attacks") and d["attacks"] is Array:
		var raw_atks = d["attacks"]
		var legal_moves = PokemonData.get_moves_for_level(s_name, lvl)
		var sanitized_atks = []
		for a in raw_atks:
			var a_str = str(a)
			if legal_moves.has(a_str) or inst.awarded_level_moves.has(a_str):
				sanitized_atks.append(a_str)
		if sanitized_atks.is_empty():
			sanitized_atks = legal_moves
		inst.attacks = sanitized_atks
	var t_stats = d.get("trained_stats", {})
	if not t_stats.is_empty():
		inst.trained_atk = int(t_stats.get("attack", 0))
		inst.trained_def = int(t_stats.get("defense", 0))
		inst.trained_spd = int(t_stats.get("speed", 0))
	else:
		inst.trained_atk = int(d.get("trained_atk", 0))
		inst.trained_def = int(d.get("trained_def", 0))
		inst.trained_spd = int(d.get("trained_spd", 0))
	inst.awarded_level_moves = d.get("awarded_level_moves", []).duplicate()
	inst.status_effects = d.get("status_effects", []).duplicate(true)
	inst.unique_id = str(d.get("unique_id", inst.unique_id))
	return inst
