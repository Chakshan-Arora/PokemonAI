extends Node
## GameState - Manages running game state (Autoload)

const PlayerModel = preload("res://scripts/models/PlayerModel.gd")
const PokemonInstance = preload("res://scripts/models/PokemonInstance.gd")
const QuestData = preload("res://scripts/data/QuestData.gd")
const RegionData = preload("res://scripts/data/RegionData.gd")

var player: PlayerModel = null
var current_region_id: String = "starting_meadow"
var game_time: float = 8.0    # 0–24 hour cycle, starts at 8am
var is_in_battle: bool = false
var is_game_started: bool = false
var is_paused: bool = false

const GAME_TIME_RATE: float = 1.0 / 240.0  # 1 game-hour per 4 real minutes (gentle, immersive day/night cycle)

signal game_time_changed(new_time: float, time_of_day: String)
signal region_changed(new_region_id: String)
signal game_started()
signal game_over()

func _ready() -> void:
	pass

func _process(delta: float) -> void:
	if is_game_started and not is_in_battle and not is_paused:
		var old_tod = get_time_of_day()
		game_time += delta * GAME_TIME_RATE
		if game_time >= 24.0:
			game_time -= 24.0
		var new_tod = get_time_of_day()
		if new_tod != old_tod:
			game_time_changed.emit(game_time, new_tod)

# ─── Game Management ──────────────────────────────────────────────────────────

func new_game(p_player_name: String, starter_species: String, avatar: String = "ash") -> void:
	player = PlayerModel.create(p_player_name)
	player.trainer_avatar = avatar
	
	# Create starter Pokémon at level 5
	var starter = PokemonInstance.create(starter_species, 5)
	starter.bond = 20.0
	player.add_to_team(starter)
	
	# Start auto-start quests
	for quest_id in QuestData.get_auto_start_quests():
		player.start_quest(quest_id)
	
	current_region_id = "starting_meadow"
	game_time = 8.0
	is_game_started = true
	is_in_battle = false
	
	game_started.emit()
	EventBus.starter_chosen.emit(starter)
	SaveLoad.save_game()

func load_game(player_model: PlayerModel) -> void:
	player = player_model
	is_game_started = true
	game_started.emit()

# ─── Party / Pokemon Access ───────────────────────────────────────────────────

func get_party() -> Array:
	if player == null:
		return []
	return player.team

func get_active_pokemon() -> PokemonInstance:
	if player == null:
		return null
	return player.get_active_pokemon()

func get_first_usable_pokemon_index() -> int:
	if player == null:
		return -1
	for i in range(player.team.size()):
		if not player.team[i].is_fainted():
			return i
	return -1

# ─── Region Management ────────────────────────────────────────────────────────

func change_region(new_region_id: String) -> void:
	if new_region_id == current_region_id:
		return
	current_region_id = new_region_id
	if player != null:
		var is_new = player.discover_region(new_region_id)
		if is_new:
			var region_data = RegionData.get_region(new_region_id)
			EventBus.region_discovered.emit(new_region_id, region_data.get("name", new_region_id))
	region_changed.emit(new_region_id)

# ─── Time of Day ──────────────────────────────────────────────────────────────

func get_time_of_day() -> String:
	if game_time >= 6.0 and game_time < 10.0:
		return "morning"
	elif game_time >= 10.0 and game_time < 18.0:
		return "day"
	elif game_time >= 18.0 and game_time < 21.0:
		return "evening"
	else:
		return "night"

func get_formatted_time() -> String:
	var hours = int(game_time)
	var minutes = int((game_time - hours) * 60.0)
	var ampm = "AM" if hours < 12 else "PM"
	var display_hour = hours % 12
	if display_hour == 0:
		display_hour = 12
	return "%02d:%02d %s" % [display_hour, minutes, ampm]

# ─── Battle State ─────────────────────────────────────────────────────────────

func enter_battle() -> void:
	is_in_battle = true
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE

func exit_battle() -> void:
	is_in_battle = false
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE

# ─── Pause & Menus ────────────────────────────────────────────────────────────

func pause_game() -> void:
	is_paused = true
	get_tree().paused = true
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE

func resume_game() -> void:
	is_paused = false
	get_tree().paused = false
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE

func release_mouse() -> void:
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE

## Returns true if player is in a battle, game is paused, or any UI menu is active/visible
func is_any_menu_open() -> bool:
	if is_in_battle or is_paused:
		return true
	
	var tree = get_tree()
	if not is_instance_valid(tree):
		return false
	
	# Check if current scene is Battle or Menu
	var current = tree.current_scene
	if is_instance_valid(current):
		var s_name = current.name.to_lower()
		if "battle" in s_name or "mainmenu" in s_name or "starter" in s_name:
			return true

	# Check UI menus in groups
	for grp in ["party_menu", "inventory_ui", "quest_journal", "pause_menu"]:
		var node = tree.get_first_node_in_group(grp)
		if is_instance_valid(node) and node is CanvasItem and node.visible:
			return true

	# Check companion dialogue panel
	var companion = tree.get_first_node_in_group("companion_chat")
	if is_instance_valid(companion) and companion is CanvasItem and companion.visible:
		return true

	# Check typing metadata
	if has_meta("typing_active") and get_meta("typing_active"):
		return true

	return false
