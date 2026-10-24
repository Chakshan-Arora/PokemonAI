class_name DamageCalculator
extends Node
## DamageCalculator - Exact port of Python damage formula

## Main damage calculation
## Returns: {damage, is_critical, type_effectiveness, message_suffix}
static func calculate(
	attacker_level: int,
	eff_atk: int,
	eff_def: int,
	attack_power: int,
	attack_type: String,
	species_types: Array,
	type_effectiveness: float,
	bond: float,
	use_random: bool = true
) -> Dictionary:
	
	# Non-damaging move (status): no damage
	if attack_power <= 0:
		return {"damage": 0, "is_critical": false, "type_effectiveness": type_effectiveness, "message_suffix": ""}

	# Immunity: 0 damage
	if type_effectiveness <= 0.0:
		var eff_msg = TypeChart.get_effectiveness_message(type_effectiveness)
		return {"damage": 0, "is_critical": false, "type_effectiveness": type_effectiveness, "message_suffix": eff_msg.strip_edges()}
	
	# Clamp bond safely between 0 and 100
	var safe_bond: float = clampf(bond, 0.0, 100.0)

	# Level factor
	var level_factor: float = (2.0 * float(attacker_level) / 5.0) + 2.0
	
	# Stat ratio
	var stat_ratio: float = float(eff_atk) / (float(eff_def) * 35.0)
	
	# Base damage
	var base_dmg: float = (level_factor * float(attack_power) * stat_ratio) + 2.0
	
	# STAB (Same Type Attack Bonus)
	var stab: float = 1.15 if attack_type in species_types else 1.0
	
	# Random factor
	var random_factor: float = 1.0
	if use_random:
		var rng = RandomNumberGenerator.new()
		rng.randomize()
		random_factor = rng.randf_range(0.85, 1.0)
	
	# Bond multiplier
	var bond_mult: float = 1.0 + (safe_bond / 100.0) * 0.15
	
	# Critical hit
	var crit_chance: float = 0.0625 + (safe_bond / 100.0) * 0.05
	var rng2 = RandomNumberGenerator.new()
	rng2.randomize()
	var is_critical: bool = rng2.randf() < crit_chance
	var crit_mult: float = 1.5 if is_critical else 1.0
	
	# Final damage (guaranteed minimum 1 for positive effectiveness)
	var damage: int = max(1, int(base_dmg * type_effectiveness * stab * random_factor * bond_mult * crit_mult))
	
	# Build message suffix
	var suffix = ""
	var eff_msg = TypeChart.get_effectiveness_message(type_effectiveness)
	if eff_msg != "":
		suffix += eff_msg + " "
	if is_critical:
		suffix += "A critical hit!"
	
	return {
		"damage": damage,
		"is_critical": is_critical,
		"type_effectiveness": type_effectiveness,
		"message_suffix": suffix.strip_edges()
	}

## Convenience: calculate using full PokemonInstance objects and attack name
static func calculate_from_pokemon(
	attacker: PokemonInstance,
	defender: PokemonInstance,
	attack_name: String,
	use_random: bool = true
) -> Dictionary:
	var attack_data = AttackData.get_attack(attack_name)
	if attack_data.is_empty():
		return {"damage": 0, "is_critical": false, "type_effectiveness": 1.0, "message_suffix": "But it failed!"}
	
	var power: int = attack_data.get("power", 0)
	var attack_type: String = attack_data.get("type", "Normal")
	
	var type_eff = TypeChart.get_effectiveness(attack_type, defender.get_types())
	
	return calculate(
		attacker.level,
		attacker.effective_attack(),
		defender.effective_defense(),
		power,
		attack_type,
		attacker.get_types(),
		type_eff,
		attacker.bond,
		use_random
	)
