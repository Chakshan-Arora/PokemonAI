extends Control
## BattleScene - Graphical turn-based battle controller

const PokemonInstance = preload("res://scripts/models/PokemonInstance.gd")
const PokemonData = preload("res://scripts/data/PokemonData.gd")
const AttackData = preload("res://scripts/data/AttackData.gd")

@onready var opponent_name_lbl: Label = $BattleUI/OpponentPanel/VBox/HBox/NameLabel
@onready var opponent_level_lbl: Label = $BattleUI/OpponentPanel/VBox/HBox/LevelLabel
@onready var opponent_hp_bar: ProgressBar = $BattleUI/OpponentPanel/VBox/HPBar
@onready var opponent_sprite: ColorRect = $Arena/OpponentSprite
@onready var opponent_sprite_label: Label = $Arena/OpponentSprite/Label

@onready var player_name_lbl: Label = $BattleUI/PlayerPanel/VBox/HBox/NameLabel
@onready var player_level_lbl: Label = $BattleUI/PlayerPanel/VBox/HBox/LevelLabel
@onready var player_hp_bar: ProgressBar = $BattleUI/PlayerPanel/VBox/HPBar
@onready var player_hp_text: Label = $BattleUI/PlayerPanel/VBox/HPTextLabel
@onready var player_sprite: ColorRect = $Arena/PlayerSprite
@onready var player_sprite_label: Label = $Arena/PlayerSprite/Label

@onready var message_lbl: Label = $BattleUI/MessageBox/VBox/MessageLabel
@onready var action_menu: GridContainer = $BattleUI/MenuPanel/ActionMenu
@onready var fight_btn: Button = $BattleUI/MenuPanel/ActionMenu/FightBtn
@onready var bag_btn: Button = $BattleUI/MenuPanel/ActionMenu/BagBtn
@onready var pokemon_btn: Button = $BattleUI/MenuPanel/ActionMenu/PokemonBtn
@onready var run_btn: Button = $BattleUI/MenuPanel/ActionMenu/RunBtn

@onready var moves_menu: GridContainer = $BattleUI/MenuPanel/MovesMenu
@onready var move_btns: Array[Button] = [
	$BattleUI/MenuPanel/MovesMenu/Move1Btn,
	$BattleUI/MenuPanel/MovesMenu/Move2Btn,
	$BattleUI/MenuPanel/MovesMenu/Move3Btn,
	$BattleUI/MenuPanel/MovesMenu/Move4Btn
]
@onready var back_btn: Button = $BattleUI/MenuPanel/MovesMenu/BackBtn

var battle_engine: Node = null
var player_pokemon: PokemonInstance = null
var opponent_pokemon: PokemonInstance = null
var is_wild: bool = true

var _message_queue: Array[String] = []
var _is_displaying_messages: bool = false
var _turn_result_pending: Dictionary = {}

func _ready() -> void:
	battle_engine = load("res://scripts/systems/BattleEngine.gd").new()
	add_child(battle_engine)
	
	fight_btn.pressed.connect(_on_fight_pressed)
	bag_btn.pressed.connect(_on_bag_pressed)
	pokemon_btn.pressed.connect(_on_pokemon_pressed)
	run_btn.pressed.connect(_on_run_pressed)
	back_btn.pressed.connect(_show_action_menu)
	
	for i in range(move_btns.size()):
		move_btns[i].pressed.connect(_on_move_selected.bind(i))
	
	_setup_battle()

func _setup_battle() -> void:
	player_pokemon = GameState.get_active_pokemon()
	if player_pokemon == null:
		# Fallback if no active pokemon
		player_pokemon = PokemonInstance.create("Pikachu", 5)
		if GameState.player:
			GameState.player.add_to_team(player_pokemon)
	
	var wild_dict = {}
	if GameState.has_meta("wild_pokemon_for_battle"):
		wild_dict = GameState.get_meta("wild_pokemon_for_battle")
		GameState.remove_meta("wild_pokemon_for_battle")
	
	if not wild_dict.is_empty():
		opponent_pokemon = PokemonInstance.from_dict(wild_dict)
	else:
		opponent_pokemon = PokemonInstance.create("Pidgey", 3)
	
	is_wild = true
	if GameState.has_meta("is_trainer_battle"):
		is_wild = not GameState.get_meta("is_trainer_battle")
		GameState.remove_meta("is_trainer_battle")
	
	battle_engine.start_battle(player_pokemon, opponent_pokemon, is_wild)
	
	_update_ui()
	_show_action_menu()
	
	if is_wild:
		_queue_message("A wild %s appeared!" % opponent_pokemon.get_display_name())
	else:
		_queue_message("Trainer sent out %s!" % opponent_pokemon.get_display_name())

func _update_ui() -> void:
	if player_pokemon:
		player_name_lbl.text = player_pokemon.get_display_name()
		player_level_lbl.text = "Lv. %d" % player_pokemon.level
		player_hp_bar.max_value = player_pokemon.max_hp
		player_hp_bar.value = player_pokemon.current_hp
		player_hp_text.text = "%d / %d" % [player_pokemon.current_hp, player_pokemon.max_hp]
		player_sprite.color = PokemonData.get_species_color(player_pokemon.species_name)
		player_sprite_label.text = player_pokemon.get_display_name()
	
	if opponent_pokemon:
		opponent_name_lbl.text = opponent_pokemon.get_display_name()
		opponent_level_lbl.text = "Lv. %d" % opponent_pokemon.level
		opponent_hp_bar.max_value = opponent_pokemon.max_hp
		opponent_hp_bar.value = opponent_pokemon.current_hp
		opponent_sprite.color = PokemonData.get_species_color(opponent_pokemon.species_name)
		opponent_sprite_label.text = opponent_pokemon.get_display_name()
	
	# Update move buttons
	if player_pokemon:
		for i in range(move_btns.size()):
			if i < player_pokemon.attacks.size():
				var atk_name = player_pokemon.attacks[i]
				var atk_data = AttackData.get_attack(atk_name)
				move_btns[i].visible = true
				move_btns[i].text = "%s (%s)" % [atk_name, atk_data.get("type", "Normal")]
			else:
				move_btns[i].visible = false

func _show_action_menu() -> void:
	action_menu.visible = true
	moves_menu.visible = false
	fight_btn.grab_focus()

func _on_fight_pressed() -> void:
	action_menu.visible = false
	moves_menu.visible = true
	if move_btns[0].visible:
		move_btns[0].grab_focus()

func _on_move_selected(index: int) -> void:
	if player_pokemon == null or index >= player_pokemon.attacks.size():
		return
	var chosen_attack = player_pokemon.attacks[index]
	moves_menu.visible = false
	
	# Select player action in engine
	battle_engine.select_player_action(battle_engine.ActionType.ATTACK, chosen_attack)
	var result = battle_engine.resolve_turn()
	_process_turn_result(result)

func _on_bag_pressed() -> void:
	# Try capturing or healing
	if is_wild and GameState.player and GameState.player.get_item_count("poke_ball") > 0:
		action_menu.visible = false
		GameState.player.remove_item("poke_ball", 1)
		battle_engine.select_player_action(battle_engine.ActionType.CAPTURE, "poke_ball")
		var result = battle_engine.resolve_turn()
		_process_turn_result(result)
	elif GameState.player and GameState.player.get_item_count("potion") > 0:
		action_menu.visible = false
		GameState.player.remove_item("potion", 1)
		battle_engine.select_player_action(battle_engine.ActionType.USE_ITEM, "potion")
		var result = battle_engine.resolve_turn()
		_process_turn_result(result)
	else:
		_queue_message("No usable items in bag!")

func _on_pokemon_pressed() -> void:
	_queue_message("No other conscious Pokemon ready to switch!")

func _on_run_pressed() -> void:
	if not is_wild:
		_queue_message("You can't run from a trainer battle!")
		return
	action_menu.visible = false
	battle_engine.select_player_action(battle_engine.ActionType.FLEE)
	var result = battle_engine.resolve_turn()
	_process_turn_result(result)

func _process_turn_result(result: Dictionary) -> void:
	var evts = result.get("events", [])
	for e in evts:
		var etype = e.get("type", "")
		match etype:
			"attack_used":
				_queue_message("%s used %s!" % [e.get("attacker", ""), e.get("attack", "")])
			"damage_dealt":
				var eff = e.get("effectiveness", 1.0)
				var text = "Dealt %d damage!" % e.get("damage", 0)
				if eff > 1.0: text += " Super effective!"
				elif eff < 1.0 and eff > 0.0: text += " Not very effective..."
				elif eff == 0.0: text += " No effect!"
				if e.get("critical", false): text += " Critical hit!"
				_queue_message(text)
			"pokemon_fainted":
				_queue_message("%s fainted!" % e.get("pokemon", ""))
			"capture_attempt":
				var cap_data = e.get("data", {})
				if cap_data.get("success", false):
					_queue_message("Gotcha! %s was caught!" % opponent_pokemon.get_display_name())
				else:
					_queue_message("Oh no! The wild Pokemon broke free!")
			"flee":
				if e.get("success", false):
					_queue_message("Got away safely!")
				else:
					_queue_message("Can't escape!")
			"message":
				_queue_message(e.get("text", ""))
	
	_turn_result_pending = result
	_play_next_message()

func _queue_message(text: String) -> void:
	_message_queue.append(text)
	if not _is_displaying_messages:
		_play_next_message()

func _play_next_message() -> void:
	if _message_queue.is_empty():
		_is_displaying_messages = false
		_on_all_messages_displayed()
		return
	
	_is_displaying_messages = true
	var msg = _message_queue.pop_front()
	message_lbl.text = msg
	
	_update_ui()
	
	# Wait and display next message
	get_tree().create_timer(1.2).timeout.connect(_play_next_message)

func _on_all_messages_displayed() -> void:
	var state = battle_engine.battle_state
	match state:
		battle_engine.BattleState.VICTORY:
			var xp_gained = opponent_pokemon.level * 40
			var xp_res = player_pokemon.gain_xp(xp_gained)
			_queue_message("%s gained %d EXP points!" % [player_pokemon.get_display_name(), xp_gained])
			if xp_res.get("levels_gained", 0) > 0:
				_queue_message("%s grew to level %d!" % [player_pokemon.get_display_name(), player_pokemon.level])
			EventBus.battle_ended.emit("victory")
			get_tree().create_timer(2.0).timeout.connect(_end_battle)
		
		battle_engine.BattleState.CAPTURED:
			if GameState.player and opponent_pokemon:
				GameState.player.add_to_collection(opponent_pokemon)
				if GameState.player.team.size() < GameState.player.max_team_size:
					GameState.player.add_to_team(opponent_pokemon)
				EventBus.pokemon_caught.emit(opponent_pokemon)
			EventBus.battle_ended.emit("captured")
			get_tree().create_timer(1.5).timeout.connect(_end_battle)
		
		battle_engine.BattleState.ESCAPED:
			EventBus.battle_ended.emit("escaped")
			get_tree().create_timer(1.0).timeout.connect(_end_battle)
		
		battle_engine.BattleState.DEFEAT:
			_queue_message("You were defeated...")
			EventBus.battle_ended.emit("defeat")
			get_tree().create_timer(2.0).timeout.connect(_end_battle)
		
		battle_engine.BattleState.IN_PROGRESS:
			_show_action_menu()

func _end_battle() -> void:
	GameState.exit_battle()
	get_tree().change_scene_to_file("res://scenes/World.tscn")
