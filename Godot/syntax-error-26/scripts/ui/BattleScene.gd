extends Control
## BattleScene - Graphical turn-based battle controller

const PokemonInstance = preload("res://scripts/models/PokemonInstance.gd")
const PokemonData = preload("res://scripts/data/PokemonData.gd")
const AttackData = preload("res://scripts/data/AttackData.gd")
const ItemData = preload("res://scripts/data/ItemData.gd")

@onready var opponent_panel_hbox: HBoxContainer = $BattleUI/OpponentPanel/VBox/HBox
@onready var opponent_name_lbl: Label = $BattleUI/OpponentPanel/VBox/HBox/NameLabel
@onready var opponent_level_lbl: Label = $BattleUI/OpponentPanel/VBox/HBox/LevelLabel
@onready var opponent_hp_bar: ProgressBar = $BattleUI/OpponentPanel/VBox/HPBar
@onready var opponent_sprite: ColorRect = $Arena/OpponentSprite
@onready var opponent_sprite_label: Label = $Arena/OpponentSprite/Label

@onready var player_panel_hbox: HBoxContainer = $BattleUI/PlayerPanel/VBox/HBox
@onready var player_name_lbl: Label = $BattleUI/PlayerPanel/VBox/HBox/NameLabel
@onready var player_level_lbl: Label = $BattleUI/PlayerPanel/VBox/HBox/LevelLabel
@onready var player_hp_bar: ProgressBar = $BattleUI/PlayerPanel/VBox/HPBar
@onready var player_hp_text: Label = $BattleUI/PlayerPanel/VBox/HPTextLabel
@onready var player_sprite: ColorRect = $Arena/PlayerSprite
@onready var player_sprite_label: Label = $Arena/PlayerSprite/Label

@onready var message_lbl: Label = $BattleUI/MessageBox/VBox/MessageLabel
@onready var menu_panel: PanelContainer = $BattleUI/MenuPanel
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

var bag_menu: ScrollContainer = null
var pokemon_menu: ScrollContainer = null

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
	
	# Dynamic region battle background
	var bg_rect = $Arena/Background as ColorRect
	if bg_rect:
		var bg_tr = bg_rect.get_node_or_null("BattleBG") as TextureRect
		if bg_tr == null:
			bg_tr = TextureRect.new()
			bg_tr.name = "BattleBG"
			bg_tr.layout_mode = 1
			bg_tr.anchors_preset = Control.PRESET_FULL_RECT
			bg_tr.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
			bg_tr.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
			bg_rect.add_child(bg_tr)
		
		var bg_path = "res://assets/backgrounds/meadow.jpg"
		var reg = GameState.current_region_id
		if "forest" in reg: bg_path = "res://assets/backgrounds/forest.jpg"
		elif "mountain" in reg: bg_path = "res://assets/backgrounds/mountain.jpg"
		elif "ruin" in reg or "haunted" in reg: bg_path = "res://assets/backgrounds/ruins.jpg"
		
		if ResourceLoader.exists(bg_path):
			bg_tr.texture = load(bg_path) as Texture2D
	
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
		
		# Player sprite (back or front sprite)
		var p_tex = PokemonData.get_back_sprite_texture(player_pokemon.species_name)
		if p_tex == null:
			p_tex = PokemonData.get_front_sprite_texture(player_pokemon.species_name)
		if p_tex:
			var ptr = player_sprite.get_node_or_null("SpriteTex") as TextureRect
			if ptr == null:
				ptr = TextureRect.new()
				ptr.name = "SpriteTex"
				ptr.layout_mode = 1
				ptr.anchors_preset = Control.PRESET_FULL_RECT
				ptr.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
				ptr.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
				player_sprite.add_child(ptr)
			ptr.texture = p_tex
			player_sprite.color = Color(0, 0, 0, 0)
			player_sprite_label.visible = false
		else:
			player_sprite.color = PokemonData.get_species_color(player_pokemon.species_name)
			player_sprite_label.text = player_pokemon.get_display_name()
		
		# Player panel PMD portrait
		var port_tr = player_panel_hbox.get_node_or_null("Portrait") as TextureRect
		if port_tr == null:
			port_tr = TextureRect.new()
			port_tr.name = "Portrait"
			port_tr.custom_minimum_size = Vector2(36, 36)
			port_tr.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
			port_tr.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
			player_panel_hbox.add_child(port_tr)
			player_panel_hbox.move_child(port_tr, 0)
		var port_tex = PokemonData.get_portrait_texture(player_pokemon.species_name)
		if port_tex:
			port_tr.texture = port_tex
			port_tr.visible = true
		else:
			port_tr.visible = false
	
	if opponent_pokemon:
		opponent_name_lbl.text = opponent_pokemon.get_display_name()
		opponent_level_lbl.text = "Lv. %d" % opponent_pokemon.level
		opponent_hp_bar.max_value = opponent_pokemon.max_hp
		opponent_hp_bar.value = opponent_pokemon.current_hp
		
		# Opponent sprite (front sprite)
		var opp_tex = PokemonData.get_front_sprite_texture(opponent_pokemon.species_name)
		if opp_tex:
			var otr = opponent_sprite.get_node_or_null("SpriteTex") as TextureRect
			if otr == null:
				otr = TextureRect.new()
				otr.name = "SpriteTex"
				otr.layout_mode = 1
				otr.anchors_preset = Control.PRESET_FULL_RECT
				otr.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
				otr.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
				opponent_sprite.add_child(otr)
			otr.texture = opp_tex
			opponent_sprite.color = Color(0, 0, 0, 0)
			opponent_sprite_label.visible = false
		else:
			opponent_sprite.color = PokemonData.get_species_color(opponent_pokemon.species_name)
			opponent_sprite_label.text = opponent_pokemon.get_display_name()
		
		# Opponent panel PMD portrait
		var opp_port_tr = opponent_panel_hbox.get_node_or_null("Portrait") as TextureRect
		if opp_port_tr == null:
			opp_port_tr = TextureRect.new()
			opp_port_tr.name = "Portrait"
			opp_port_tr.custom_minimum_size = Vector2(36, 36)
			opp_port_tr.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
			opp_port_tr.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
			opponent_panel_hbox.add_child(opp_port_tr)
			opponent_panel_hbox.move_child(opp_port_tr, 0)
		var opp_port_tex = PokemonData.get_portrait_texture(opponent_pokemon.species_name)
		if opp_port_tex:
			opp_port_tr.texture = opp_port_tex
			opp_port_tr.visible = true
		else:
			opp_port_tr.visible = false
	
	# Update move buttons with stylized type colors
	if player_pokemon:
		for i in range(move_btns.size()):
			if i < player_pokemon.attacks.size():
				var atk_name = player_pokemon.attacks[i]
				var atk_data = AttackData.get_attack(atk_name)
				var atk_type = atk_data.get("type", "Normal")
				move_btns[i].visible = true
				move_btns[i].text = "%s [%s]\nPwr:%d  Acc:%d%%" % [
					atk_name,
					atk_type,
					atk_data.get("power", 0),
					atk_data.get("accuracy", 100)
				]
				var tcolor = PokemonData.TYPE_COLORS.get(atk_type, Color(0.7, 0.7, 0.7))
				move_btns[i].modulate = tcolor.lightened(0.3)
			else:
				move_btns[i].visible = false

func _animate_attack(is_player: bool) -> void:
	var sprite = player_sprite if is_player else opponent_sprite
	var orig_pos = sprite.position
	var target_offset = Vector2(25, -12) if is_player else Vector2(-25, 12)
	var tween = create_tween()
	tween.tween_property(sprite, "position", orig_pos + target_offset, 0.12).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	tween.tween_property(sprite, "position", orig_pos, 0.15).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)

func _animate_hit(is_player_hit: bool) -> void:
	var sprite = player_sprite if is_player_hit else opponent_sprite
	var orig_x = sprite.position.x
	var tween = create_tween()
	sprite.modulate = Color(2.2, 0.35, 0.35)
	tween.tween_property(sprite, "position:x", orig_x - 10, 0.05)
	tween.tween_property(sprite, "position:x", orig_x + 10, 0.05)
	tween.tween_property(sprite, "position:x", orig_x - 5, 0.05)
	tween.tween_property(sprite, "position:x", orig_x, 0.05)
	tween.tween_property(sprite, "modulate", Color.WHITE, 0.15)

func _show_action_menu() -> void:
	action_menu.visible = true
	moves_menu.visible = false
	if bag_menu: bag_menu.visible = false
	if pokemon_menu: pokemon_menu.visible = false
	fight_btn.grab_focus()

func _on_fight_pressed() -> void:
	action_menu.visible = false
	moves_menu.visible = true
	if bag_menu: bag_menu.visible = false
	if pokemon_menu: pokemon_menu.visible = false
	if move_btns[0].visible:
		move_btns[0].grab_focus()

func _on_move_selected(index: int) -> void:
	if player_pokemon == null or index >= player_pokemon.attacks.size():
		return
	var chosen_attack = player_pokemon.attacks[index]
	moves_menu.visible = false
	
	battle_engine.select_player_action(battle_engine.ActionType.ATTACK, chosen_attack)
	var result = battle_engine.resolve_turn()
	_process_turn_result(result)

func _on_bag_pressed() -> void:
	action_menu.visible = false
	moves_menu.visible = false
	if pokemon_menu: pokemon_menu.visible = false
	
	if bag_menu == null:
		bag_menu = ScrollContainer.new()
		bag_menu.name = "BagMenu"
		bag_menu.custom_minimum_size = Vector2(360, 120)
		menu_panel.add_child(bag_menu)
	
	bag_menu.visible = true
	
	for c in bag_menu.get_children():
		c.queue_free()
	
	var vbox = VBoxContainer.new()
	vbox.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	bag_menu.add_child(vbox)
	
	var count_usable = 0
	if GameState.player and not GameState.player.inventory.is_empty():
		for item_id in GameState.player.inventory:
			var qty = GameState.player.inventory[item_id]
			if qty <= 0:
				continue
			var idata = ItemData.get_item(item_id)
			var eff = idata.get("effect", "")
			if not (eff in ["capture", "heal", "full_restore", "cure_poison", "cure_burn", "cure_paralysis"]):
				continue
			
			count_usable += 1
			var btn = Button.new()
			btn.text = "%s  x%d" % [idata.get("name", item_id), qty]
			var icon_tex = ItemData.get_item_texture(item_id)
			if icon_tex:
				btn.icon = icon_tex
				btn.expand_icon = true
			btn.alignment = HORIZONTAL_ALIGNMENT_LEFT
			btn.pressed.connect(_on_bag_item_selected.bind(item_id))
			vbox.add_child(btn)
	
	if count_usable == 0:
		var lbl = Label.new()
		lbl.text = "No usable items in bag!"
		vbox.add_child(lbl)
	
	var back = Button.new()
	back.text = "← Back"
	back.pressed.connect(_show_action_menu)
	vbox.add_child(back)

func _on_bag_item_selected(item_id: String) -> void:
	if bag_menu: bag_menu.visible = false
	
	if item_id == "poke_ball":
		if not is_wild:
			_queue_message("You can't capture a trainer's Pokémon!")
			_show_action_menu()
			return
		if GameState.player and GameState.player.get_item_count("poke_ball") > 0:
			GameState.player.remove_item("poke_ball", 1)
			battle_engine.select_player_action(battle_engine.ActionType.CAPTURE, "poke_ball")
			var result = battle_engine.resolve_turn()
			_process_turn_result(result)
		else:
			_queue_message("No Poké Balls remaining!")
			_show_action_menu()
	else:
		if GameState.player and GameState.player.get_item_count(item_id) > 0:
			battle_engine.select_player_action(battle_engine.ActionType.USE_ITEM, item_id)
			var result = battle_engine.resolve_turn()
			_process_turn_result(result)
		else:
			_queue_message("You don't have that item!")
			_show_action_menu()

func _on_pokemon_pressed() -> void:
	action_menu.visible = false
	moves_menu.visible = false
	if bag_menu: bag_menu.visible = false
	
	if pokemon_menu == null:
		pokemon_menu = ScrollContainer.new()
		pokemon_menu.name = "PokemonMenu"
		pokemon_menu.custom_minimum_size = Vector2(360, 120)
		menu_panel.add_child(pokemon_menu)
	
	pokemon_menu.visible = true
	
	for c in pokemon_menu.get_children():
		c.queue_free()
	
	var vbox = VBoxContainer.new()
	vbox.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	pokemon_menu.add_child(vbox)
	
	if GameState.player:
		for p in GameState.player.team:
			var btn = Button.new()
			var p_tex = PokemonData.get_portrait_texture(p.species_name)
			if p_tex:
				btn.icon = p_tex
				btn.expand_icon = true
			
			if p.unique_id == player_pokemon.unique_id:
				btn.text = "%s Lv.%d (Active) - %d/%d HP" % [p.get_display_name(), p.level, p.current_hp, p.max_hp]
				btn.disabled = true
			elif p.is_fainted():
				btn.text = "%s Lv.%d (Fainted)" % [p.get_display_name(), p.level]
				btn.disabled = true
			else:
				btn.text = "%s Lv.%d - %d/%d HP" % [p.get_display_name(), p.level, p.current_hp, p.max_hp]
				btn.pressed.connect(_on_pokemon_switch_selected.bind(p))
			
			btn.alignment = HORIZONTAL_ALIGNMENT_LEFT
			vbox.add_child(btn)
	
	var back = Button.new()
	back.text = "← Back"
	back.pressed.connect(_show_action_menu)
	vbox.add_child(back)

func _on_pokemon_switch_selected(new_pokemon: PokemonInstance) -> void:
	if pokemon_menu: pokemon_menu.visible = false
	battle_engine.select_player_action(battle_engine.ActionType.SWITCH, new_pokemon.unique_id)
	player_pokemon = new_pokemon
	var result = battle_engine.resolve_turn()
	_process_turn_result(result)

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
				var atkr = e.get("attacker", "")
				var is_p = (atkr == player_pokemon.get_display_name() or atkr == player_pokemon.species_name)
				_animate_attack(is_p)
				_queue_message("%s used %s!" % [atkr, e.get("attack", "")])
			"damage_dealt":
				var def_name = e.get("defender", "")
				var is_p_hit = (def_name == player_pokemon.get_display_name() or def_name == player_pokemon.species_name)
				_animate_hit(is_p_hit)
				var eff = e.get("effectiveness", 1.0)
				var text = "Dealt %d damage!" % e.get("damage", 0)
				if eff > 1.0: text += " Super effective!"
				elif eff < 1.0 and eff > 0.0: text += " Not very effective..."
				elif eff == 0.0: text += " No effect!"
				if e.get("critical", false): text += " Critical hit!"
				_queue_message(text)
			"pokemon_fainted":
				_queue_message("%s fainted!" % e.get("pokemon", ""))
			"fainted":
				_queue_message("%s fainted!" % e.get("pokemon", ""))
			"switch":
				_queue_message("Go, %s!" % e.get("pokemon", ""))
				player_pokemon = battle_engine.player_pokemon
				_update_ui()
			"item_used":
				_queue_message("Used %s on %s!" % [e.get("item", ""), e.get("target", "")])
				_update_ui()
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
			
			if not is_wild:
				var tid = "koji"
				if GameState.has_meta("trainer_id"):
					tid = GameState.get_meta("trainer_id")
				if GameState.player:
					GameState.player.record_trainer_defeat(tid)
				if QuestSystem:
					QuestSystem.on_trainer_defeated(tid)
					QuestSystem.on_trainer_defeated("field_trainer_koji")
				_queue_message("You defeated Trainer %s!" % (GameState.get_meta("trainer_name") if GameState.has_meta("trainer_name") else ""))
			
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
			_queue_message("You were defeated... Whited out!")
			if GameState.player:
				for p in GameState.player.team:
					p.heal_to_full()
					p.clear_all_statuses()
				GameState.player.player_position = Vector3(25.0, 0.1, 25.0)
			EventBus.battle_ended.emit("defeat")
			get_tree().create_timer(2.0).timeout.connect(_end_battle)
		
		battle_engine.BattleState.IN_PROGRESS:
			_show_action_menu()

func _end_battle() -> void:
	GameState.exit_battle()
	get_tree().change_scene_to_file("res://scenes/World.tscn")
