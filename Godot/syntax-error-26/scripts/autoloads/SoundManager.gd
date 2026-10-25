extends Node
## SoundManager - Global sound effects and audio management.
## Manages UI click sound effects across all buttons, controls, and menus,
## and plays the Pokémon battle transition sound effect during encounters.

const BATTLE_TRANSITION_SOUND: AudioStream = preload("res://assets/audio/battle_transition.mp3")
const CLICK_SOUND: AudioStream = preload("res://assets/audio/click.mp3")

var _battle_player: AudioStreamPlayer = null
var _click_players: Array[AudioStreamPlayer] = []
var _click_pool_size: int = 6
var _click_index: int = 0
var _fade_tween: Tween = null

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	
	# 1. Initialize Battle Transition Audio Player
	_battle_player = AudioStreamPlayer.new()
	_battle_player.name = "BattleTransitionPlayer"
	_battle_player.stream = BATTLE_TRANSITION_SOUND
	_battle_player.bus = "Master"
	add_child(_battle_player)
	
	# 2. Initialize Click Audio Player Pool (allows overlapping clicks during fast navigation)
	for i in range(_click_pool_size):
		var cp = AudioStreamPlayer.new()
		cp.name = "ClickPlayer_%d" % i
		cp.stream = CLICK_SOUND
		cp.bus = "Master"
		add_child(cp)
		_click_players.append(cp)
	
	# 3. Hook into scene tree for automatic UI sound effects on buttons and interactive controls
	get_tree().node_added.connect(_on_node_added)
	_connect_existing_nodes(get_tree().root)
	
	# 4. Listen to global interaction events
	if has_node("/root/EventBus"):
		var eb = get_node("/root/EventBus")
		eb.interaction_triggered.connect(_on_interaction_triggered)

func _connect_existing_nodes(node: Node) -> void:
	_hook_node(node)
	for child in node.get_children():
		_connect_existing_nodes(child)

func _on_node_added(node: Node) -> void:
	_hook_node(node)

func _hook_node(node: Node) -> void:
	if node is BaseButton:
		if not node.pressed.is_connected(_on_button_pressed):
			node.pressed.connect(_on_button_pressed)
	elif node is Slider:
		if not node.drag_started.is_connected(_on_slider_drag_started):
			node.drag_started.connect(_on_slider_drag_started)
	elif node is TabBar:
		if not node.tab_clicked.is_connected(_on_tab_clicked):
			node.tab_clicked.connect(_on_tab_clicked)
	elif node is ItemList:
		if not node.item_selected.is_connected(_on_item_selected):
			node.item_selected.connect(_on_item_selected)

func _on_button_pressed() -> void:
	play_click()

func _on_slider_drag_started() -> void:
	play_click()

func _on_tab_clicked(_tab_idx: int) -> void:
	play_click()

func _on_item_selected(_item_idx: int) -> void:
	play_click()

func _on_interaction_triggered(_object_id: String) -> void:
	play_click()

## Play the UI click sound effect
func play_click() -> void:
	if _click_players.is_empty():
		return
	var player = _click_players[_click_index]
	_click_index = (_click_index + 1) % _click_players.size()
	player.stop()
	player.play()

## Play the 14-second Pokémon battle transition sound effect
func play_battle_transition() -> void:
	if _fade_tween and _fade_tween.is_valid():
		_fade_tween.kill()
	if _battle_player:
		_battle_player.volume_db = 0.0
		_battle_player.stop()
		_battle_player.play()

## Returns true if the battle transition sound is currently active
func is_battle_transition_playing() -> bool:
	return _battle_player != null and _battle_player.is_playing()

## Smoothly fade out and stop the battle transition sound effect
func stop_battle_transition(fade_time: float = 0.5) -> void:
	if _battle_player == null or not _battle_player.is_playing():
		return
	if fade_time <= 0.0:
		_battle_player.stop()
		_battle_player.volume_db = 0.0
		return
	if _fade_tween and _fade_tween.is_valid():
		_fade_tween.kill()
	_fade_tween = create_tween()
	_fade_tween.tween_property(_battle_player, "volume_db", -40.0, fade_time)
	_fade_tween.tween_callback(func():
		if _battle_player:
			_battle_player.stop()
			_battle_player.volume_db = 0.0
	)
