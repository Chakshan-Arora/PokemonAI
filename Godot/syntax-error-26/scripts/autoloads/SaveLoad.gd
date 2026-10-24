extends Node
## SaveLoad - Handles saving and loading game data (Autoload)

const PlayerModel = preload("res://scripts/models/PlayerModel.gd")

const SAVE_FILE_PATH: String = "user://save_game.json"
const SAVE_VERSION: int = 1

signal save_completed(success: bool)
signal load_completed(success: bool)

func _ready() -> void:
	EventBus.save_requested.connect(_on_save_requested)
	EventBus.load_requested.connect(_on_load_requested)

func _on_save_requested() -> void:
	save_game()

func _on_load_requested() -> void:
	load_game()

# ─── Save ─────────────────────────────────────────────────────────────────────

func save_game() -> bool:
	if GameState.player == null:
		push_warning("SaveLoad: No active player to save.")
		save_completed.emit(false)
		return false
	
	# Update stored position from the current world scene if available
	var world_scene = get_tree().get_first_node_in_group("world")
	if world_scene:
		var player_node = world_scene.get_node_or_null("Player")
		if player_node:
			GameState.player.player_position = player_node.global_position
	
	var save_data: Dictionary = {
		"save_version": SAVE_VERSION,
		"timestamp": Time.get_unix_time_from_system(),
		"player": GameState.player.to_dict(),
		"current_region_id": GameState.current_region_id,
		"game_time": GameState.game_time
	}
	
	var json_str = JSON.stringify(save_data, "\t")
	var file = FileAccess.open(SAVE_FILE_PATH, FileAccess.WRITE)
	if file == null:
		push_error("SaveLoad: Cannot open file for writing: %s" % SAVE_FILE_PATH)
		save_completed.emit(false)
		return false
	
	file.store_string(json_str)
	file.close()
	print("SaveLoad: Game saved successfully.")
	save_completed.emit(true)
	return true

# ─── Load ─────────────────────────────────────────────────────────────────────

func save_exists() -> bool:
	return FileAccess.file_exists(SAVE_FILE_PATH)

func load_game() -> bool:
	if not FileAccess.file_exists(SAVE_FILE_PATH):
		push_warning("SaveLoad: No save file found.")
		load_completed.emit(false)
		return false
	
	var file = FileAccess.open(SAVE_FILE_PATH, FileAccess.READ)
	if file == null:
		push_error("SaveLoad: Cannot open save file for reading.")
		load_completed.emit(false)
		return false
	
	var json_str = file.get_as_text()
	file.close()
	
	var json = JSON.new()
	var error = json.parse(json_str)
	if error != OK:
		push_error("SaveLoad: Failed to parse save file JSON: %s" % json.get_error_message())
		load_completed.emit(false)
		return false
	
	var save_data: Dictionary = json.data
	
	# Validate version
	var version = save_data.get("save_version", 0)
	if version != SAVE_VERSION:
		push_warning("SaveLoad: Save file version mismatch (%d vs %d)" % [version, SAVE_VERSION])
	
	# Load player
	var player_dict = save_data.get("player", {})
	if player_dict.is_empty():
		push_error("SaveLoad: Save file missing player data.")
		load_completed.emit(false)
		return false
	
	var player = PlayerModel.from_dict(player_dict)
	GameState.current_region_id = save_data.get("current_region_id", "starting_meadow")
	GameState.game_time = save_data.get("game_time", 8.0)
	GameState.load_game(player)
	
	print("SaveLoad: Game loaded successfully.")
	load_completed.emit(true)
	return true

## Returns save file metadata without full load (for continue screen preview)
func get_save_preview() -> Dictionary:
	if not save_exists():
		return {}
	var file = FileAccess.open(SAVE_FILE_PATH, FileAccess.READ)
	if file == null:
		return {}
	var json_str = file.get_as_text()
	file.close()
	var json = JSON.new()
	if json.parse(json_str) != OK:
		return {}
	var d = json.data
	var player_d = d.get("player", {})
	return {
		"player_name": player_d.get("player_name", "Unknown"),
		"team_size": player_d.get("team", []).size(),
		"total_catches": player_d.get("total_catches", 0),
		"timestamp": d.get("timestamp", 0),
		"region_id": d.get("current_region_id", "")
	}

func delete_save() -> void:
	if save_exists():
		DirAccess.remove_absolute(SAVE_FILE_PATH)
