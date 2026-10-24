class_name PlayerModel
## PlayerModel - Player data model (not a Node)

const PokemonInstance = preload("res://scripts/models/PokemonInstance.gd")
const QuestData = preload("res://scripts/data/QuestData.gd")

var player_name: String = "Trainer"
var trainer_avatar: String = "ash"
var unique_id: String = ""
var team: Array = []           # Array of PokemonInstance (max 6)
var party: Array:
	get:
		return team
var collection: Array = []     # All caught Pokémon
var inventory: Dictionary = {} # item_id -> quantity
var max_team_size: int = 6
var discovered_regions: Array = []    # Array of region_id strings
var discovered_landmarks: Array = []  # Array of landmark_id strings
var interacted_objects: Dictionary = {} # object_id -> {count, last_time}
var active_pokemon_index: int = 0
var defeated_trainers: Array = []
var active_quest_ids: Array = []
var completed_quest_ids: Array = []
var active_quests: Array:
	get:
		return active_quest_ids
var completed_quests: Array:
	get:
		return completed_quest_ids
var quest_progress: Dictionary = {}  # quest_id -> {objective_id -> progress}
var player_position: Vector3 = Vector3(50.0, 0.5, 50.0)  # Start in meadow
var total_steps: int = 0
var total_battles: int = 0
var total_catches: int = 0

# ─── Constructor ──────────────────────────────────────────────────────────────

static func create(p_name: String):
	var pm = new()
	pm.player_name = p_name
	pm.unique_id = _generate_uid()
	# Starter inventory
	pm.inventory = {"poke_ball": 5, "potion": 3}
	return pm

static func _generate_uid() -> String:
	var rng = RandomNumberGenerator.new()
	rng.randomize()
	return "player_%d_%d" % [Time.get_ticks_msec(), rng.randi()]

# ─── Team Management ──────────────────────────────────────────────────────────

func add_to_team(p: PokemonInstance) -> bool:
	if team.size() >= max_team_size:
		return false
	if is_on_team(p):
		return false
	team.append(p)
	if not is_in_collection(p):
		collection.append(p)
	return true

func is_on_team(p: PokemonInstance) -> bool:
	for member in team:
		if member.unique_id == p.unique_id:
			return true
	return false

func remove_from_team(p: PokemonInstance) -> bool:
	for i in range(team.size()):
		if team[i].unique_id == p.unique_id:
			team.remove_at(i)
			return true
	return false

func get_active_pokemon() -> PokemonInstance:
	if active_pokemon_index >= 0 and active_pokemon_index < team.size():
		var p = team[active_pokemon_index]
		if not p.is_fainted():
			return p
	for i in range(team.size()):
		if not team[i].is_fainted():
			active_pokemon_index = i
			return team[i]
	return null

func set_active_pokemon_index(index: int) -> void:
	if index >= 0 and index < team.size():
		active_pokemon_index = index

func has_living_pokemon() -> bool:
	for p in team:
		if not p.is_fainted():
			return true
	return false

func swap_team_positions(i: int, j: int) -> void:
	if i >= 0 and i < team.size() and j >= 0 and j < team.size():
		var tmp = team[i]
		team[i] = team[j]
		team[j] = tmp

# ─── Collection ───────────────────────────────────────────────────────────────

func add_to_collection(p: PokemonInstance) -> void:
	if not is_in_collection(p):
		collection.append(p)
	total_catches += 1

func is_in_collection(p: PokemonInstance) -> bool:
	for c in collection:
		if c.unique_id == p.unique_id:
			return true
	return false

func has_species_in_collection(species_name: String) -> bool:
	for c in collection:
		if c.species_name == species_name:
			return true
	return false

# ─── Inventory ────────────────────────────────────────────────────────────────

func add_item(item_id: String, quantity: int = 1) -> void:
	var q = int(quantity)
	if inventory.has(item_id):
		inventory[item_id] = int(inventory[item_id]) + q
	else:
		inventory[item_id] = q

func remove_item(item_id: String, quantity: int = 1) -> bool:
	var q = int(quantity)
	if not inventory.has(item_id) or int(inventory[item_id]) < q:
		return false
	inventory[item_id] = int(inventory[item_id]) - q
	if inventory[item_id] <= 0:
		inventory.erase(item_id)
	return true

func has_item(item_id: String, quantity: int = 1) -> bool:
	return int(inventory.get(item_id, 0)) >= int(quantity)

func get_item_count(item_id: String) -> int:
	return int(inventory.get(item_id, 0))

# ─── Regions / Exploration ────────────────────────────────────────────────────

func discover_region(region_id: String) -> bool:
	if region_id not in discovered_regions:
		discovered_regions.append(region_id)
		return true
	return false

func has_discovered_region(region_id: String) -> bool:
	return region_id in discovered_regions

func discover_landmark(landmark_id: String) -> bool:
	if landmark_id not in discovered_landmarks:
		discovered_landmarks.append(landmark_id)
		return true
	return false

# ─── World Object Tracking ────────────────────────────────────────────────────

func record_interaction(object_id: String) -> void:
	if interacted_objects.has(object_id):
		interacted_objects[object_id]["count"] += 1
		interacted_objects[object_id]["last_time"] = Time.get_ticks_msec()
	else:
		interacted_objects[object_id] = {"count": 1, "last_time": Time.get_ticks_msec()}

func record_object_interaction(object_id: String) -> void:
	record_interaction(object_id)

func has_interacted(object_id: String) -> bool:
	return interacted_objects.has(object_id)

func interaction_count(object_id: String) -> int:
	return interacted_objects.get(object_id, {}).get("count", 0)

func is_trainer_defeated(trainer_id: String) -> bool:
	return trainer_id in defeated_trainers

func record_trainer_defeat(trainer_id: String) -> void:
	if trainer_id not in defeated_trainers:
		defeated_trainers.append(trainer_id)
		total_battles += 1

# ─── Quest Tracking ───────────────────────────────────────────────────────────

func start_quest(quest_id: String) -> void:
	if quest_id not in active_quest_ids and quest_id not in completed_quest_ids:
		active_quest_ids.append(quest_id)
		quest_progress[quest_id] = {}
		# Initialize all objective progress to 0
		var quest_data = QuestData.get_quest(quest_id)
		if not quest_data.is_empty():
			for obj in quest_data["objectives"]:
				quest_progress[quest_id][obj["objective_id"]] = 0

func complete_quest(quest_id: String) -> void:
	active_quest_ids.erase(quest_id)
	if quest_id not in completed_quest_ids:
		completed_quest_ids.append(quest_id)

func get_quest_objective_progress(quest_id: String, objective_id: String) -> int:
	return quest_progress.get(quest_id, {}).get(objective_id, 0)

func update_quest_progress(quest_id: String, objective_id: String, amount: int = 1) -> void:
	if not quest_progress.has(quest_id):
		quest_progress[quest_id] = {}
	quest_progress[quest_id][objective_id] = quest_progress[quest_id].get(objective_id, 0) + amount

# ─── Serialization ────────────────────────────────────────────────────────────

func to_dict() -> Dictionary:
	var team_data = []
	for p in team:
		team_data.append(p.to_dict())
	var collection_data = []
	for p in collection:
		collection_data.append(p.to_dict())
	var clean_inv: Dictionary = {}
	for k in inventory:
		clean_inv[str(k)] = int(round(float(inventory[k])))

	return {
		"player_name": player_name,
		"trainer_avatar": trainer_avatar,
		"unique_id": unique_id,
		"active_pokemon_index": active_pokemon_index,
		"team": team_data,
		"collection": collection_data,
		"inventory": clean_inv,
		"discovered_regions": discovered_regions.duplicate(),
		"discovered_landmarks": discovered_landmarks.duplicate(),
		"defeated_trainers": defeated_trainers.duplicate(),
		"interacted_objects": interacted_objects.duplicate(true),
		"active_quest_ids": active_quest_ids.duplicate(),
		"completed_quest_ids": completed_quest_ids.duplicate(),
		"quest_progress": quest_progress.duplicate(true),
		"player_position": {"x": player_position.x, "y": player_position.y, "z": player_position.z},
		"total_steps": total_steps,
		"total_battles": total_battles,
		"total_catches": total_catches
	}

static func from_dict(d: Dictionary):
	var pm = new()
	pm.player_name = d.get("player_name", "Trainer")
	pm.trainer_avatar = d.get("trainer_avatar", "ash")
	pm.unique_id = d.get("unique_id", "")
	pm.active_pokemon_index = d.get("active_pokemon_index", 0)
	var raw_inv = d.get("inventory", {"poke_ball": 5, "potion": 3})
	pm.inventory = {}
	if raw_inv is Dictionary:
		for k in raw_inv:
			pm.inventory[str(k)] = int(round(float(raw_inv[k])))
	pm.discovered_regions = d.get("discovered_regions", []).duplicate()
	pm.discovered_landmarks = d.get("discovered_landmarks", []).duplicate()
	pm.defeated_trainers = d.get("defeated_trainers", []).duplicate()
	pm.interacted_objects = d.get("interacted_objects", {}).duplicate(true)
	pm.active_quest_ids = d.get("active_quest_ids", []).duplicate()
	pm.completed_quest_ids = d.get("completed_quest_ids", []).duplicate()
	pm.quest_progress = d.get("quest_progress", {}).duplicate(true)
	pm.total_steps = d.get("total_steps", 0)
	pm.total_battles = d.get("total_battles", 0)
	pm.total_catches = d.get("total_catches", 0)
	# Position
	var pos_d = d.get("player_position", {"x": 50.0, "y": 0.5, "z": 50.0})
	pm.player_position = Vector3(pos_d.get("x", 50.0), pos_d.get("y", 0.5), pos_d.get("z", 50.0))
	# Team
	for pd in d.get("team", []):
		var p = PokemonInstance.from_dict(pd)
		pm.team.append(p)
	# Collection (rebuild, avoid duplicates)
	for pd in d.get("collection", []):
		var p = PokemonInstance.from_dict(pd)
		pm.collection.append(p)
	return pm
