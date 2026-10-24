extends Node
## SaveLoad - Handles saving and loading game data (Autoload)
## Synchronizes directly with the Python backend's save_game.json (Schema v4).

const PlayerModel = preload("res://scripts/models/PlayerModel.gd")
const PokemonInstance = preload("res://scripts/models/PokemonInstance.gd")

const SAVE_VERSION: int = 4

signal save_completed(success: bool)
signal load_completed(success: bool)

func _ready() -> void:
	EventBus.save_requested.connect(_on_save_requested)
	EventBus.load_requested.connect(_on_load_requested)

func _on_save_requested() -> void:
	save_game()

func _on_load_requested() -> void:
	await load_game()

func get_save_file_path() -> String:
	# Primary: workspace root save_game.json
	var root_path = ProjectSettings.globalize_path("res://../../save_game.json")
	if FileAccess.file_exists(root_path):
		return root_path
	# If root directory exists and is writable, use root
	var root_dir = ProjectSettings.globalize_path("res://../../")
	if DirAccess.dir_exists_absolute(root_dir):
		return root_path
	return "user://save_game.json"

# ─── Save ─────────────────────────────────────────────────────────────────────

func save_game() -> bool:
	if GameState.player == null:
		push_warning("SaveLoad: No active player to save.")
		save_completed.emit(false)
		return false
	
	# Update stored position from current world scene
	var world_scene = get_tree().get_first_node_in_group("world")
	if world_scene:
		var player_node = world_scene.get_node_or_null("Player")
		if player_node:
			GameState.player.player_position = player_node.global_position
	
	var col_data = []
	for p in GameState.player.collection:
		col_data.append(p.to_dict())
	
	var team_data = []
	for p in GameState.player.team:
		team_data.append(p.unique_id)
	
	var active_mon = GameState.player.get_active_pokemon()
	var active_id = active_mon.unique_id if active_mon else (team_data[0] if team_data.size() > 0 else null)
	
	var save_data: Dictionary = {
		"schema_version": SAVE_VERSION,
		"saved_at": Time.get_datetime_string_from_system(false, true),
		"player": {
			"name": GameState.player.player_name,
			"player_name": GameState.player.player_name,
			"unique_id": GameState.player.unique_id,
			"max_team_size": GameState.player.max_team_size,
			"trainer_avatar": GameState.player.trainer_avatar
		},
		"inventory": {
			"capacity": 20,
			"items": GameState.player.inventory.duplicate()
		},
		"collection": col_data,
		"team": team_data,
		"active_pokemon_id": active_id,
		"discovered_regions": GameState.player.discovered_regions.duplicate(),
		"discovered_landmarks": GameState.player.discovered_landmarks.duplicate(),
		"collected_treasures": [],
		"quests": {},
		"wild_action_history": [],
		"player_position": {
			"x": GameState.player.player_position.x,
			"y": GameState.player.player_position.y,
			"z": GameState.player.player_position.z
		},
		"current_region_id": GameState.current_region_id,
		"game_time": GameState.game_time
	}
	
	var json_str = JSON.stringify(save_data, "  ")
	var primary_path = get_save_file_path()
	var file = FileAccess.open(primary_path, FileAccess.WRITE)
	if file == null:
		push_error("SaveLoad: Cannot open primary file for writing: %s" % primary_path)
		# Fallback to user://
		primary_path = "user://save_game.json"
		file = FileAccess.open(primary_path, FileAccess.WRITE)
		if file == null:
			save_completed.emit(false)
			return false
	
	file.store_string(json_str)
	file.close()
	
	# Also write backup to user:// if primary is outside
	if primary_path != "user://save_game.json":
		var user_file = FileAccess.open("user://save_game.json", FileAccess.WRITE)
		if user_file:
			user_file.store_string(json_str)
			user_file.close()

	print("SaveLoad: Game saved successfully to: ", primary_path)
	
	# Synchronize with live backend server if online
	if LLMClient and LLMClient.is_server_online:
		LLMClient.save_game_to_backend(save_data)
	
	save_completed.emit(true)
	return true

# ─── Load ─────────────────────────────────────────────────────────────────────

func save_exists() -> bool:
	var root_path = ProjectSettings.globalize_path("res://../../save_game.json")
	if FileAccess.file_exists(root_path):
		return true
	return FileAccess.file_exists("user://save_game.json")

func load_game() -> bool:
	var save_data: Dictionary = {}
	var path_to_load = ""
	
	# 1. Try loading from live Python backend server if reachable
	if LLMClient and LLMClient.is_server_online:
		var b_data = await LLMClient.load_game_from_backend()
		if not b_data.is_empty():
			save_data = b_data
			path_to_load = "http://127.0.0.1:8008/api/load"
			print("SaveLoad: Successfully loaded verified save from live Python backend server!")
	
	# 2. Fallback to local files if backend server offline or didn't respond
	if save_data.is_empty():
		var root_path = ProjectSettings.globalize_path("res://../../save_game.json")
		if FileAccess.file_exists(root_path):
			path_to_load = root_path
		elif FileAccess.file_exists("user://save_game.json"):
			path_to_load = "user://save_game.json"
		else:
			push_warning("SaveLoad: No save file found.")
			load_completed.emit(false)
			return false
		
		var file = FileAccess.open(path_to_load, FileAccess.READ)
		if file == null:
			push_error("SaveLoad: Cannot open save file: " + path_to_load)
			load_completed.emit(false)
			return false
		
		var json_str = file.get_as_text()
		file.close()
		
		var json = JSON.new()
		if json.parse(json_str) != OK:
			push_error("SaveLoad: Failed to parse save file JSON: %s" % json.get_error_message())
			load_completed.emit(false)
			return false
		save_data = json.data
	var player_dict = save_data.get("player", {})
	var p_name = player_dict.get("name", player_dict.get("player_name", "Trainer"))
	var p_avatar = player_dict.get("trainer_avatar", "calem")
	
	var player = PlayerModel.create(p_name)
	player.trainer_avatar = p_avatar
	player.unique_id = str(player_dict.get("unique_id", player.unique_id))
	player.max_team_size = int(player_dict.get("max_team_size", 6))
	
	# Inventory
	var inv_data = save_data.get("inventory", {})
	if inv_data.has("items") and inv_data["items"] is Dictionary:
		player.inventory = inv_data["items"].duplicate()
	elif inv_data is Dictionary:
		player.inventory = inv_data.duplicate()
	
	# Collection
	player.collection.clear()
	var col_list = save_data.get("collection", [])
	var col_by_id = {}
	for mon_d in col_list:
		if mon_d is Dictionary:
			var mon = PokemonInstance.from_dict(mon_d)
			player.collection.append(mon)
			col_by_id[mon.unique_id] = mon
	
	# Team
	player.team.clear()
	var team_list = save_data.get("team", [])
	for item in team_list:
		if item is String:
			if col_by_id.has(item):
				player.team.append(col_by_id[item])
		elif item is Dictionary:
			var mon = PokemonInstance.from_dict(item)
			player.team.append(mon)
			if not col_by_id.has(mon.unique_id):
				player.collection.append(mon)
				col_by_id[mon.unique_id] = mon
	
	# If team was empty but collection has Pokémon, put first in team
	if player.team.is_empty() and not player.collection.is_empty():
		player.team.append(player.collection[0])
	
	# Active Pokémon index
	var active_id = save_data.get("active_pokemon_id", null)
	if active_id != null:
		for i in range(player.team.size()):
			if player.team[i].unique_id == str(active_id):
				player.active_pokemon_index = i
				break
	
	# Exploration
	player.discovered_regions = save_data.get("discovered_regions", ["starting_meadow"]).duplicate()
	player.discovered_landmarks = save_data.get("discovered_landmarks", []).duplicate()
	
	# Position
	var pos_d = save_data.get("player_position", {"x": 50.0, "y": 0.5, "z": 50.0})
	player.player_position = Vector3(float(pos_d.get("x", 50.0)), float(pos_d.get("y", 0.5)), float(pos_d.get("z", 50.0)))
	
	GameState.current_region_id = save_data.get("current_region_id", "starting_meadow")
	GameState.game_time = float(save_data.get("game_time", 8.0))
	GameState.load_game(player)
	
	print("SaveLoad: Loaded player '%s' from %s" % [player.player_name, path_to_load])
	load_completed.emit(true)
	return true

func get_save_preview() -> Dictionary:
	var path_to_load = ""
	var root_path = ProjectSettings.globalize_path("res://../../save_game.json")
	if FileAccess.file_exists(root_path):
		path_to_load = root_path
	elif FileAccess.file_exists("user://save_game.json"):
		path_to_load = "user://save_game.json"
	else:
		return {}
	
	var file = FileAccess.open(path_to_load, FileAccess.READ)
	if file == null:
		return {}
	var json_str = file.get_as_text()
	file.close()
	var json = JSON.new()
	if json.parse(json_str) != OK or not (json.data is Dictionary):
		return {}
	var d = json.data
	var player_d = d.get("player", {})
	var p_name = player_d.get("name", player_d.get("player_name", "Trainer"))
	var team_size = d.get("team", []).size()
	var catches = d.get("collection", []).size()
	
	return {
		"player_name": p_name,
		"team_size": team_size,
		"total_catches": catches,
		"timestamp": d.get("saved_at", ""),
		"region_id": d.get("current_region_id", "starting_meadow")
	}

func delete_save() -> void:
	var root_path = ProjectSettings.globalize_path("res://../../save_game.json")
	if FileAccess.file_exists(root_path):
		DirAccess.remove_absolute(root_path)
	if FileAccess.file_exists("user://save_game.json"):
		DirAccess.remove_absolute("user://save_game.json")
