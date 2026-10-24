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
var talk_idle_timer: float = 0.0
const TALK_DECAY_INTERVAL: float = 300.0  # 5 minutes in real gameplay seconds

const GAME_DAY_REAL_MINUTES: float = 20.0
const GAME_TIME_RATE: float = 24.0 / (GAME_DAY_REAL_MINUTES * 60.0)  # 24 in-game hours per 20 real minutes (1200 real seconds) = 0.02 game hours/sec

var _last_emitted_minute: int = -1

signal game_time_changed(new_time: float, time_of_day: String)
signal region_changed(new_region_id: String)
signal game_started()
signal game_over()

var render_distance: float = 250.0
const MIN_RENDER_DISTANCE: float = 30.0
const MAX_RENDER_DISTANCE: float = 600.0

func _ready() -> void:
	_load_settings()

func _load_settings() -> void:
	var cfg = ConfigFile.new()
	if cfg.load("user://settings.cfg") == OK:
		render_distance = clampf(float(cfg.get_value("graphics", "render_distance", 250.0)), MIN_RENDER_DISTANCE, MAX_RENDER_DISTANCE)

func _save_settings() -> void:
	var cfg = ConfigFile.new()
	var _err = cfg.load("user://settings.cfg")
	cfg.set_value("graphics", "render_distance", render_distance)
	cfg.save("user://settings.cfg")

func set_render_distance(val: float) -> void:
	render_distance = clampf(val, MIN_RENDER_DISTANCE, MAX_RENDER_DISTANCE)
	_save_settings()
	EventBus.render_distance_changed.emit(render_distance)

func get_render_distance() -> float:
	return render_distance

func _process(delta: float) -> void:
	if is_game_started and not is_in_battle and not is_paused:
		var old_tod = get_time_of_day()
		game_time += delta * GAME_TIME_RATE
		if game_time >= 24.0:
			game_time -= 24.0
		var new_tod = get_time_of_day()
		
		# Emit when discrete minute changes or time of day changes
		var current_minute = int(round(game_time * 60.0)) % 1440
		if current_minute != _last_emitted_minute or new_tod != old_tod:
			_last_emitted_minute = current_minute
			game_time_changed.emit(game_time, new_tod)
		
		# Every 5 minutes without talking to active Pokemon, trust & affection decrease by 2
		talk_idle_timer += delta
		if talk_idle_timer >= TALK_DECAY_INTERVAL:
			talk_idle_timer -= TALK_DECAY_INTERVAL
			_apply_talk_decay()

func record_talk_interaction() -> void:
	talk_idle_timer = 0.0
	var active_p = get_active_pokemon()
	if active_p:
		active_p.last_talk_time = game_time

func _apply_talk_decay() -> void:
	var active_p = get_active_pokemon()
	if active_p:
		active_p.decay_trust_and_affection(2.0)
		EventBus.show_message.emit("💤 %s feels a bit lonely. (Trust -2, Affection -2)" % active_p.get_display_name())
		SaveLoad.save_game()

# ─── Game Management ──────────────────────────────────────────────────────────

func new_game(p_player_name: String, starter_species: String, avatar: String = "ash") -> void:
	player = PlayerModel.create(p_player_name)
	player.trainer_avatar = avatar
	
	# Create starter Pokémon at level 5
	var starter = PokemonInstance.create(starter_species, 5)
	starter.bond = 20.0
	starter.trust = 50.0
	starter.affection = 50.0
	player.add_to_team(starter)
	
	# Start auto-start quests
	for quest_id in QuestData.get_auto_start_quests():
		player.start_quest(quest_id)
	
	current_region_id = "starting_meadow"
	game_time = 8.0
	_last_emitted_minute = -1
	is_game_started = true
	is_in_battle = false
	
	game_started.emit()
	game_time_changed.emit(game_time, get_time_of_day())
	EventBus.starter_chosen.emit(starter)
	SaveLoad.save_game()

func load_game(player_model: PlayerModel) -> void:
	player = player_model
	_last_emitted_minute = -1
	is_game_started = true
	game_started.emit()
	game_time_changed.emit(game_time, get_time_of_day())

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
	if game_time >= 5.0 and game_time < 10.0:
		return "morning"
	elif game_time >= 10.0 and game_time < 17.0:
		return "day"
	elif game_time >= 17.0 and game_time < 21.0:
		return "evening"
	else:
		return "night"

func is_night() -> bool:
	return get_time_of_day() == "night"

func is_day() -> bool:
	return get_time_of_day() in ["morning", "day"]

func get_formatted_time() -> String:
	var total_minutes = int(round(game_time * 60.0))
	var hours = (total_minutes / 60) % 24
	var minutes = total_minutes % 60
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
