extends Node
## QuestSystem - Routes game events to quest objectives

const PokemonInstance = preload("res://scripts/models/PokemonInstance.gd")
const QuestData = preload("res://scripts/data/QuestData.gd")

func _ready() -> void:
	# Connect to EventBus signals
	EventBus.pokemon_caught.connect(_on_pokemon_caught)
	EventBus.region_discovered.connect(_on_region_discovered)
	EventBus.world_object_interacted.connect(_on_object_interacted)

# ─── Event Handlers ───────────────────────────────────────────────────────────

func _on_pokemon_caught(pokemon: PokemonInstance) -> void:
	if GameState.player == null:
		return
	_update_objectives("catch_pokemon", pokemon.species_name)
	_update_objectives("catch_count", "")
	GameState.player.total_catches += 1

func _on_region_discovered(region_id: String, _region_name: String) -> void:
	_update_objectives("visit_region", region_id)

func _on_object_interacted(object_id: String, _object_type: String) -> void:
	_update_objectives("interact_object", object_id)

func on_trainer_defeated(trainer_id: String) -> void:
	_update_objectives("defeat_trainer", trainer_id)

# ─── Objective Progression ────────────────────────────────────────────────────

func _update_objectives(objective_type: String, target_id: String) -> void:
	if GameState.player == null:
		return
	
	for quest_id in GameState.player.active_quest_ids:
		var quest_data = QuestData.get_quest(quest_id)
		if quest_data.is_empty():
			continue
		
		for obj in quest_data["objectives"]:
			if obj["type"] != objective_type:
				continue
			
			# For specific targets, match; for generic (catch_count), always progress
			var matches = false
			if obj["target_id"] == "" or obj["target_id"] == target_id:
				matches = true
			
			if not matches:
				continue
			
			var obj_id = obj["objective_id"]
			var current_progress = GameState.player.get_quest_objective_progress(quest_id, obj_id)
			var target = obj["target"]
			
			if current_progress >= target:
				continue  # Already done
			
			GameState.player.update_quest_progress(quest_id, obj_id, 1)
			var new_progress = current_progress + 1
			
			EventBus.quest_updated.emit(quest_id, obj_id, new_progress, target)
			
			# Check if quest is complete
			if _is_quest_complete(quest_id, quest_data):
				_complete_quest(quest_id, quest_data)

func _is_quest_complete(quest_id: String, quest_data: Dictionary) -> bool:
	for obj in quest_data["objectives"]:
		var progress = GameState.player.get_quest_objective_progress(quest_id, obj["objective_id"])
		if progress < obj["target"]:
			return false
	return true

func _complete_quest(quest_id: String, quest_data: Dictionary) -> void:
	GameState.player.complete_quest(quest_id)
	EventBus.quest_completed.emit(quest_id)
	
	# Grant rewards
	var rewards = quest_data.get("rewards", {})
	if rewards.has("item_id") and rewards.has("quantity"):
		GameState.player.add_item(rewards["item_id"], rewards["quantity"])
		EventBus.item_obtained.emit(rewards["item_id"], rewards["quantity"])
	
	# Check for newly unlocked quests (prerequisites met)
	_check_unlock_quests()

func _check_unlock_quests() -> void:
	if GameState.player == null:
		return
	for quest_id in QuestData.get_all_quest_ids():
		if quest_id in GameState.player.active_quest_ids:
			continue
		if quest_id in GameState.player.completed_quest_ids:
			continue
		var quest_data = QuestData.get_quest(quest_id)
		var prereqs = quest_data.get("prerequisite_quests", [])
		var all_done = true
		for prereq in prereqs:
			if prereq not in GameState.player.completed_quest_ids:
				all_done = false
				break
		if all_done and not prereqs.is_empty():
			GameState.player.start_quest(quest_id)
			EventBus.quest_started.emit(quest_id)
