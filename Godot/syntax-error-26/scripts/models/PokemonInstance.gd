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

# ─── Constructor ──────────────────────────────────────────────────────────────

static func create(p_species_name: String, p_level: int, p_nickname: String = ""):
	var inst = new()
	inst.species_name = p_species_name
	inst.nickname = p_nickname if p_nickname != "" else p_species_name
	inst.level = p_level
	inst.unique_id = _generate_uid()

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

	# Assign first 4 available attacks
	var available = species_data["available_attacks"]
	for i in range(min(4, available.size())):
		inst.attacks.append(available[i])

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
	return {
		"species_name": species_name,
		"nickname": nickname,
		"level": level,
		"experience": experience,
		"current_hp": current_hp,
		"max_hp": max_hp,
		"bond": bond,
		"obedience": obedience,
		"attacks": attacks.duplicate(),
		"trained_atk": trained_atk,
		"trained_def": trained_def,
		"trained_spd": trained_spd,
		"status_effects": status_effects.duplicate(true),
		"unique_id": unique_id
	}

static func from_dict(d: Dictionary):
	var inst = create(d.get("species_name", ""), d.get("level", 1))
	inst.nickname = d.get("nickname", inst.nickname)
	inst.experience = d.get("experience", 0)
	inst.current_hp = d.get("current_hp", inst.max_hp)
	inst.max_hp = d.get("max_hp", inst.max_hp)
	inst.bond = d.get("bond", 0.0)
	inst.obedience = d.get("obedience", 100.0)
	inst.attacks = d.get("attacks", inst.attacks).duplicate()
	inst.trained_atk = d.get("trained_atk", 0)
	inst.trained_def = d.get("trained_def", 0)
	inst.trained_spd = d.get("trained_spd", 0)
	inst.status_effects = d.get("status_effects", []).duplicate(true)
	inst.unique_id = d.get("unique_id", inst.unique_id)
	return inst
