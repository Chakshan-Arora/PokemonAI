extends Control
## BattleScene - Graphical turn-based battle controller with synchronized animations & typewriter text

const PokemonInstance = preload("res://scripts/models/PokemonInstance.gd")
const PokemonData = preload("res://scripts/data/PokemonData.gd")
const AttackData = preload("res://scripts/data/AttackData.gd")
const ItemData = preload("res://scripts/data/ItemData.gd")

@onready var opponent_panel_hbox: HBoxContainer = $BattleUI/OpponentPanel/VBox/HBox
@onready var opponent_name_lbl: Label = $BattleUI/OpponentPanel/VBox/HBox/NameLabel
@onready var opponent_level_lbl: Label = $BattleUI/OpponentPanel/VBox/HBox/LevelLabel
@onready var opponent_hp_bar: ProgressBar = $BattleUI/OpponentPanel/VBox/HPBar
@onready var opponent_sprite: Control = $Arena/OpponentSprite
@onready var opponent_sprite_label: Label = $Arena/OpponentSprite/Label

@onready var player_panel_hbox: HBoxContainer = $BattleUI/PlayerPanel/VBox/HBox
@onready var player_name_lbl: Label = $BattleUI/PlayerPanel/VBox/HBox/NameLabel
@onready var player_level_lbl: Label = $BattleUI/PlayerPanel/VBox/HBox/LevelLabel
@onready var player_hp_bar: ProgressBar = $BattleUI/PlayerPanel/VBox/HPBar
@onready var player_hp_text: Label = $BattleUI/PlayerPanel/VBox/HPTextLabel
@onready var player_exp_bar: ProgressBar = $BattleUI/PlayerPanel/VBox/EXPBar
@onready var player_sprite: Control = $Arena/PlayerSprite
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
var talk_menu: ScrollContainer = null
var talk_btn: Button = null
var continue_btn: Button = null
var active_battle_morale: int = 0
var morale_badge: Label = null

var battle_engine: Node = null
var player_pokemon: PokemonInstance = null
var opponent_pokemon: PokemonInstance = null
var is_wild: bool = true

var _battle_step_queue: Array[Dictionary] = []
var _is_displaying_messages: bool = false
var _typewriter_tween: Tween = null
var _battle_concluded: bool = false
var _waiting_for_continue: bool = false

func _ready() -> void:
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	GameState.is_in_battle = true
	battle_engine = load("res://scripts/systems/BattleEngine.gd").new()
	add_child(battle_engine)
	
	action_menu.columns = 3
	talk_btn = Button.new()
	talk_btn.name = "TalkBtn"
	talk_btn.layout_mode = 2
	talk_btn.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	talk_btn.size_flags_vertical = Control.SIZE_EXPAND_FILL
	talk_btn.text = "💬 TALK"
	talk_btn.pressed.connect(_on_talk_pressed)
	action_menu.add_child(talk_btn)
	action_menu.move_child(talk_btn, 3)
	
	for btn in [fight_btn, bag_btn, pokemon_btn, run_btn, talk_btn]:
		btn.add_theme_font_size_override("font_size", 16)
		
	morale_badge = Label.new()
	morale_badge.name = "MoraleBadge"
	morale_badge.text = "[STEADY]"
	morale_badge.add_theme_font_size_override("font_size", 12)
	morale_badge.self_modulate = Color(0.4, 0.85, 0.5)
	player_panel_hbox.add_child(morale_badge)
	
	fight_btn.pressed.connect(_on_fight_pressed)
	bag_btn.pressed.connect(_on_bag_pressed)
	pokemon_btn.pressed.connect(_on_pokemon_pressed)
	run_btn.pressed.connect(_on_run_pressed)
	back_btn.pressed.connect(_show_action_menu)
	
	_style_action_buttons()
	
	if is_instance_valid(player_exp_bar):
		var exp_fill = StyleBoxFlat.new()
		exp_fill.bg_color = Color("#3182ce")
		exp_fill.set_corner_radius_all(2)
		player_exp_bar.add_theme_stylebox_override("fill", exp_fill)
	
	for i in range(move_btns.size()):
		move_btns[i].pressed.connect(_on_move_selected.bind(i))
	
	_setup_battle()

func _process(_delta: float) -> void:
	if Input.mouse_mode != Input.MOUSE_MODE_VISIBLE:
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE

func _style_action_buttons() -> void:
	var btns = [fight_btn, bag_btn, pokemon_btn, run_btn, talk_btn]
	for b in btns:
		if b == null:
			continue
		b.pivot_offset = b.size / 2.0
		b.mouse_entered.connect(func():
			var tw = create_tween()
			tw.tween_property(b, "scale", Vector2(1.04, 1.04), 0.08)
		)
		b.mouse_exited.connect(func():
			var tw = create_tween()
			tw.tween_property(b, "scale", Vector2(1.0, 1.0), 0.08)
		)
		b.focus_entered.connect(func():
			var tw = create_tween()
			tw.tween_property(b, "scale", Vector2(1.04, 1.04), 0.08)
		)
		b.focus_exited.connect(func():
			var tw = create_tween()
			tw.tween_property(b, "scale", Vector2(1.0, 1.0), 0.08)
		)
	
	# Grid focus wrapping: 3 columns [Fight, Bag, Pokemon] / [Talk, Run]
	fight_btn.focus_neighbor_right = bag_btn.get_path()
	fight_btn.focus_neighbor_bottom = talk_btn.get_path()
	fight_btn.focus_neighbor_left = pokemon_btn.get_path()
	fight_btn.focus_neighbor_top = talk_btn.get_path()

	bag_btn.focus_neighbor_left = fight_btn.get_path()
	bag_btn.focus_neighbor_right = pokemon_btn.get_path()
	bag_btn.focus_neighbor_bottom = run_btn.get_path()
	bag_btn.focus_neighbor_top = run_btn.get_path()

	pokemon_btn.focus_neighbor_left = bag_btn.get_path()
	pokemon_btn.focus_neighbor_right = fight_btn.get_path()
	pokemon_btn.focus_neighbor_bottom = run_btn.get_path()
	pokemon_btn.focus_neighbor_top = run_btn.get_path()

	if talk_btn:
		talk_btn.focus_neighbor_right = run_btn.get_path()
		talk_btn.focus_neighbor_left = run_btn.get_path()
		talk_btn.focus_neighbor_top = fight_btn.get_path()
		talk_btn.focus_neighbor_bottom = fight_btn.get_path()

	run_btn.focus_neighbor_left = talk_btn.get_path() if talk_btn else pokemon_btn.get_path()
	run_btn.focus_neighbor_right = talk_btn.get_path() if talk_btn else pokemon_btn.get_path()
	run_btn.focus_neighbor_top = bag_btn.get_path()
	run_btn.focus_neighbor_bottom = bag_btn.get_path()

func _setup_battle() -> void:
	player_pokemon = GameState.get_active_pokemon()
	if player_pokemon == null:
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
	
	# Background
	var bg_tr = $Arena/Background as TextureRect
	if bg_tr:
		var bg_path = "res://assets/backgrounds/meadow.jpg"
		var reg = GameState.current_region_id
		if "forest" in reg: bg_path = "res://assets/backgrounds/forest.jpg"
		elif "mountain" in reg: bg_path = "res://assets/backgrounds/mountain.jpg"
		elif "ruin" in reg or "haunted" in reg: bg_path = "res://assets/backgrounds/ruins.jpg"
		
		if ResourceLoader.exists(bg_path):
			bg_tr.texture = load(bg_path) as Texture2D
		
		# Apply day and night lighting/tint to battle arena
		_apply_time_of_day_atmosphere()
	
	var old_ball = $Arena.get_node_or_null("ActivePokeBall")
	if is_instance_valid(old_ball):
		old_ball.queue_free()
	if is_instance_valid(opponent_sprite):
		opponent_sprite.visible = true
		opponent_sprite.scale = Vector2.ONE
		opponent_sprite.modulate = Color.WHITE
	var opp_panel = $BattleUI/OpponentPanel
	if is_instance_valid(opp_panel):
		opp_panel.modulate.a = 1.0
	
	battle_engine.start_battle(player_pokemon, opponent_pokemon, is_wild)
	active_battle_morale = 0
	battle_engine.set_player_morale(0)
	_update_morale_badge("STEADY")
	
	_init_ui_stats()
	_update_move_buttons()
	_show_action_menu()
	
	if is_wild:
		_queue_message("A wild %s appeared!" % opponent_pokemon.get_display_name())
	else:
		var t_name = GameState.get_meta("trainer_name") if GameState.has_meta("trainer_name") else "Trainer"
		_queue_message("%s wants to battle!" % t_name)
		_queue_message("%s sent out %s!" % [t_name, opponent_pokemon.get_display_name()])
	
	if player_pokemon and player_pokemon.refuses_to_battle():
		_queue_message("⚠️ %s turns away and refuses to battle for you! (Trust & Affection below 0)" % player_pokemon.get_display_name())
	
	if has_node("/root/BattleTransition"):
		var bt = get_node("/root/BattleTransition")
		bt.play_battle_intro_animation()

func _update_hp_bar_color(bar: ProgressBar, current: int, maximum: int) -> void:
	var ratio = float(current) / float(max(1, maximum))
	var fill_style = StyleBoxFlat.new()
	fill_style.set_corner_radius_all(3)
	if ratio > 0.5:
		fill_style.bg_color = Color("#38a169") # Green
	elif ratio > 0.2:
		fill_style.bg_color = Color("#dd6b20") # Orange
	else:
		fill_style.bg_color = Color("#e53e3e") # Red
	bar.add_theme_stylebox_override("fill", fill_style)

## Initialize static visuals and initial HP states at start of battle or after switch
func _init_ui_stats() -> void:
	if player_pokemon:
		player_name_lbl.text = player_pokemon.get_display_name()
		player_level_lbl.text = "Lv. %d" % player_pokemon.level
		player_hp_bar.max_value = player_pokemon.max_hp
		player_hp_bar.value = player_pokemon.current_hp
		_update_hp_bar_color(player_hp_bar, player_pokemon.current_hp, player_pokemon.max_hp)
		player_hp_text.text = "%d / %d HP" % [player_pokemon.current_hp, player_pokemon.max_hp]
		
		# EXP Bar progress
		if is_instance_valid(player_exp_bar):
			var xp_pct = float(player_pokemon.experience) / float(max(1, player_pokemon.level * 100)) * 100.0
			player_exp_bar.value = xp_pct
		
		# Player sprite (back sprite preferred in battle)
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
			player_sprite_label.visible = false
			player_sprite.modulate.a = 1.0
		else:
			player_sprite_label.text = player_pokemon.get_display_name()
		
		# PMD portrait
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
		_update_hp_bar_color(opponent_hp_bar, opponent_pokemon.current_hp, opponent_pokemon.max_hp)
		
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
			opponent_sprite_label.visible = false
			opponent_sprite.modulate.a = 1.0
		else:
			opponent_sprite_label.text = opponent_pokemon.get_display_name()
		
		# PMD portrait
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

func _update_move_buttons() -> void:
	if player_pokemon:
		var visible_btns: Array[Button] = []
		for i in range(move_btns.size()):
			if i < player_pokemon.attacks.size():
				var atk_name = player_pokemon.attacks[i]
				var atk_data = AttackData.get_attack(atk_name)
				var atk_type = atk_data.get("type", "Normal")
				var max_pp = atk_data.get("pp", 20)
				move_btns[i].visible = true
				move_btns[i].text = "%s [%s]\nPwr:%d  Acc:%d%%  PP:%d" % [
					atk_name,
					atk_type,
					atk_data.get("power", 0),
					atk_data.get("accuracy", 100),
					max_pp
				]
				var tcolor = PokemonData.TYPE_COLORS.get(atk_type, Color(0.7, 0.7, 0.7))
				move_btns[i].self_modulate = tcolor.lightened(0.25)
				visible_btns.append(move_btns[i])
			else:
				move_btns[i].visible = false
		
		# Set focus neighbors for move buttons and back button
		if visible_btns.size() == 1:
			visible_btns[0].focus_neighbor_bottom = back_btn.get_path()
			visible_btns[0].focus_neighbor_top = back_btn.get_path()
			back_btn.focus_neighbor_top = visible_btns[0].get_path()
			back_btn.focus_neighbor_bottom = visible_btns[0].get_path()
		elif visible_btns.size() == 2:
			visible_btns[0].focus_neighbor_right = visible_btns[1].get_path()
			visible_btns[0].focus_neighbor_left = visible_btns[1].get_path()
			visible_btns[0].focus_neighbor_bottom = back_btn.get_path()
			visible_btns[1].focus_neighbor_left = visible_btns[0].get_path()
			visible_btns[1].focus_neighbor_right = visible_btns[0].get_path()
			visible_btns[1].focus_neighbor_bottom = back_btn.get_path()
			back_btn.focus_neighbor_top = visible_btns[0].get_path()
		elif visible_btns.size() >= 3:
			visible_btns[0].focus_neighbor_right = visible_btns[1].get_path()
			visible_btns[0].focus_neighbor_bottom = visible_btns[2].get_path()
			visible_btns[1].focus_neighbor_left = visible_btns[0].get_path()
			if visible_btns.size() >= 4:
				visible_btns[1].focus_neighbor_bottom = visible_btns[3].get_path()
				visible_btns[3].focus_neighbor_top = visible_btns[1].get_path()
				visible_btns[3].focus_neighbor_left = visible_btns[2].get_path()
				visible_btns[3].focus_neighbor_bottom = back_btn.get_path()
			else:
				visible_btns[1].focus_neighbor_bottom = back_btn.get_path()
			visible_btns[2].focus_neighbor_top = visible_btns[0].get_path()
			if visible_btns.size() >= 4:
				visible_btns[2].focus_neighbor_right = visible_btns[3].get_path()
			visible_btns[2].focus_neighbor_bottom = back_btn.get_path()
			back_btn.focus_neighbor_top = visible_btns[2].get_path()
			back_btn.focus_neighbor_bottom = visible_btns[0].get_path()

func _animate_attack(is_player: bool) -> void:
	var sprite = player_sprite if is_player else opponent_sprite
	var orig_pos = sprite.position
	var target_offset = Vector2(30, -15) if is_player else Vector2(-30, 15)
	var tween = create_tween()
	tween.tween_property(sprite, "position", orig_pos + target_offset, 0.12).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	tween.tween_property(sprite, "position", orig_pos, 0.15).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)

func _animate_hit(is_player_hit: bool) -> void:
	var sprite = player_sprite if is_player_hit else opponent_sprite
	var orig_x = sprite.position.x
	var tween = create_tween()
	sprite.modulate = Color(2.5, 0.4, 0.4)
	tween.tween_property(sprite, "position:x", orig_x - 12, 0.04)
	tween.tween_property(sprite, "position:x", orig_x + 12, 0.04)
	tween.tween_property(sprite, "position:x", orig_x - 6, 0.04)
	tween.tween_property(sprite, "position:x", orig_x, 0.04)
	tween.tween_property(sprite, "modulate", Color.WHITE, 0.15)

func _animate_heal(is_player: bool) -> void:
	var sprite = player_sprite if is_player else opponent_sprite
	if not is_instance_valid(sprite):
		return
	var orig_y = sprite.position.y
	var tween = create_tween()
	sprite.modulate = Color(0.6, 2.2, 0.8)
	tween.tween_property(sprite, "position:y", orig_y - 8, 0.15).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	tween.tween_property(sprite, "position:y", orig_y, 0.2).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
	tween.parallel().tween_property(sprite, "modulate", Color.WHITE, 0.45).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)

func _spawn_heal_sparkles(center: Vector2) -> void:
	var arena = $Arena
	if not is_instance_valid(arena):
		return
	for i in range(6):
		var p = Label.new()
		p.text = "💚" if (i % 2 == 0) else "✨"
		p.add_theme_font_size_override("font_size", 16)
		p.position = center - Vector2(8, 8)
		p.z_index = 25
		arena.add_child(p)
		
		var angle = randf_range(-PI * 0.9, -PI * 0.1)
		var dist = randf_range(25.0, 55.0)
		var dest = center + Vector2(cos(angle), sin(angle)) * dist - Vector2(0, 15)
		
		var tw = create_tween().set_parallel(true)
		tw.tween_property(p, "position", dest, 0.5).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
		tw.tween_property(p, "scale", Vector2(1.2, 1.2), 0.2)
		tw.tween_property(p, "scale", Vector2(0.2, 0.2), 0.3).set_delay(0.2)
		tw.tween_property(p, "modulate:a", 0.0, 0.5)
		tw.chain().tween_callback(p.queue_free)

func _apply_heal(is_player: bool, new_hp: int, max_hp: int) -> void:
	if is_player:
		if is_instance_valid(player_hp_bar):
			var current_val = player_hp_bar.value
			if abs(current_val - float(new_hp)) > 0.01:
				var hp_tw = create_tween()
				hp_tw.tween_property(player_hp_bar, "value", float(new_hp), 0.45).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
				hp_tw.parallel().tween_method(func(val: float):
					if is_instance_valid(player_hp_text):
						player_hp_text.text = "%d / %d HP" % [int(round(val)), max_hp]
					_update_hp_bar_color(player_hp_bar, int(round(val)), max_hp)
				, current_val, float(new_hp), 0.45)
			else:
				if is_instance_valid(player_hp_text):
					player_hp_text.text = "%d / %d HP" % [new_hp, max_hp]
				_update_hp_bar_color(player_hp_bar, new_hp, max_hp)
				return
		_animate_heal(true)
		if is_instance_valid(player_sprite):
			_spawn_heal_sparkles(player_sprite.position + Vector2(player_sprite.size.x * 0.5, player_sprite.size.y * 0.5))
	else:
		if is_instance_valid(opponent_hp_bar):
			var current_val = opponent_hp_bar.value
			if abs(current_val - float(new_hp)) > 0.01:
				var opp_hp_tw = create_tween()
				opp_hp_tw.tween_property(opponent_hp_bar, "value", float(new_hp), 0.45).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
				opp_hp_tw.parallel().tween_method(func(val: float):
					_update_hp_bar_color(opponent_hp_bar, int(round(val)), max_hp)
				, current_val, float(new_hp), 0.45)
			else:
				_update_hp_bar_color(opponent_hp_bar, new_hp, max_hp)
				return
		_animate_heal(false)
		if is_instance_valid(opponent_sprite):
			_spawn_heal_sparkles(opponent_sprite.position + Vector2(opponent_sprite.size.x * 0.5, opponent_sprite.size.y * 0.5))

## ─── Poké Ball Throw & Capture Animations ───────────────────────────────────

func _animate_capture_throw(success: bool, callback: Callable) -> void:
	var arena = $Arena
	if not is_instance_valid(arena) or not is_instance_valid(opponent_sprite) or not is_instance_valid(player_sprite):
		callback.call()
		return
	
	# Clean up any leftover balls
	var old_ball = arena.get_node_or_null("ActivePokeBall")
	if is_instance_valid(old_ball):
		old_ball.queue_free()
	
	# Instantiate Poké Ball
	var ball = TextureRect.new()
	ball.name = "ActivePokeBall"
	ball.texture = load("res://assets/sprites/items/poke_ball.png")
	var ball_size = Vector2(44, 44)
	ball.custom_minimum_size = ball_size
	ball.size = ball_size
	ball.pivot_offset = ball_size / 2.0
	ball.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	ball.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	ball.z_index = 20
	
	var start_pos = player_sprite.position + Vector2(player_sprite.size.x * 0.4, player_sprite.size.y * 0.2)
	var opp_center = opponent_sprite.position + Vector2(opponent_sprite.size.x * 0.5, opponent_sprite.size.y * 0.5)
	var ground_pos = Vector2(opp_center.x - 22, opponent_sprite.position.y + opponent_sprite.size.y - 20)
	
	ball.position = start_pos
	arena.add_child(ball)
	
	# Phase 1: High Arc Throw (0.65s)
	var throw_tw = create_tween().set_parallel(true)
	throw_tw.tween_property(ball, "position:x", opp_center.x - 22, 0.65).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	
	# Parabolic Y: peak up by 140px, then down to opp_center.y
	var peak_y = minf(start_pos.y, opp_center.y) - 140.0
	var y_tw = create_tween()
	y_tw.tween_property(ball, "position:y", peak_y, 0.32).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	y_tw.tween_property(ball, "position:y", opp_center.y - 22, 0.33).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
	
	# Rapid spinning
	throw_tw.tween_property(ball, "rotation_degrees", 1080.0, 0.65)
	
	throw_tw.chain().tween_callback(func():
		_absorb_pokemon_into_ball(ball, opp_center, ground_pos, success, callback)
	)

func _absorb_pokemon_into_ball(ball: TextureRect, opp_center: Vector2, ground_pos: Vector2, success: bool, callback: Callable) -> void:
	if not is_instance_valid(ball) or not is_instance_valid(opponent_sprite):
		callback.call()
		return
	
	var orig_opp_pos = opponent_sprite.position
	var orig_opp_scale = opponent_sprite.scale
	opponent_sprite.pivot_offset = opponent_sprite.size / 2.0
	
	# Flash red energy on opponent and bright flash on ball
	var absorb_flash_tw = create_tween().set_parallel(true)
	absorb_flash_tw.tween_property(opponent_sprite, "modulate", Color(3.0, 1.2, 1.2, 1.0), 0.1)
	absorb_flash_tw.tween_property(ball, "modulate", Color(2.5, 2.5, 2.5, 1.0), 0.1)
	
	# Fade opponent HUD during capture attempt
	var opp_panel = $BattleUI/OpponentPanel
	if is_instance_valid(opp_panel):
		var panel_tw = create_tween()
		panel_tw.tween_property(opp_panel, "modulate:a", 0.0, 0.25)
	
	# Opponent shrinks down and gets sucked into ball center
	var absorb_tw = create_tween().set_parallel(true)
	absorb_tw.tween_property(opponent_sprite, "scale", Vector2(0.04, 0.04), 0.35).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_IN)
	absorb_tw.tween_property(opponent_sprite, "position", opp_center - opponent_sprite.size * 0.04 / 2.0, 0.35)
	absorb_tw.tween_property(opponent_sprite, "modulate:a", 0.0, 0.35)
	absorb_tw.tween_property(ball, "modulate", Color.WHITE, 0.25)
	
	absorb_tw.chain().tween_callback(func():
		opponent_sprite.visible = false
		opponent_sprite.position = orig_opp_pos
		opponent_sprite.scale = orig_opp_scale
		opponent_sprite.modulate = Color.WHITE
		
		# Drop to ground and bounce
		_drop_and_bounce_ball(ball, ground_pos, success, callback)
	)

func _drop_and_bounce_ball(ball: TextureRect, ground_pos: Vector2, success: bool, callback: Callable) -> void:
	if not is_instance_valid(ball):
		callback.call()
		return
	
	ball.rotation_degrees = 0.0
	var drop_tw = create_tween()
	# Fall to ground
	drop_tw.tween_property(ball, "position:y", ground_pos.y, 0.2).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
	# Bounce 1
	drop_tw.tween_property(ball, "position:y", ground_pos.y - 22, 0.1).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	drop_tw.tween_property(ball, "position:y", ground_pos.y, 0.08).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
	# Small bounce 2
	drop_tw.tween_property(ball, "position:y", ground_pos.y - 7, 0.06).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	drop_tw.tween_property(ball, "position:y", ground_pos.y, 0.05).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
	
	drop_tw.tween_callback(func():
		_tick_and_blink_ball(ball, ground_pos, success, callback)
	)

func _tick_and_blink_ball(ball: TextureRect, ground_pos: Vector2, success: bool, callback: Callable) -> void:
	if not is_instance_valid(ball):
		callback.call()
		return
	
	var tw = create_tween()
	
	if not success:
		# Exactly 2.0 seconds of ticking & blinking, then breaks free!
		# Tick 1 at 0.2s
		tw.tween_interval(0.2)
		tw.tween_callback(func(): _wobble_and_blink(ball, -22.0))
		# Tick 2 at 1.0s
		tw.tween_interval(0.8)
		tw.tween_callback(func(): _wobble_and_blink(ball, 22.0))
		# Tense rapid vibration from 1.6s to 2.0s (0.4s duration)
		tw.tween_interval(0.6)
		tw.tween_callback(func(): _vibrate_ball(ball, 0.4))
		# At 2.0s: Breaks free!
		tw.tween_interval(0.4)
		tw.tween_callback(func(): _break_free_animation(ball, ground_pos, callback))
	else:
		# Exactly 5.0 seconds of ticking & blinking, then caught!
		# Tick 1 at 0.4s
		tw.tween_interval(0.4)
		tw.tween_callback(func(): _wobble_and_blink(ball, -22.0))
		# Tick 2 at 1.5s
		tw.tween_interval(1.1)
		tw.tween_callback(func(): _wobble_and_blink(ball, 22.0))
		# Tick 3 at 2.7s
		tw.tween_interval(1.2)
		tw.tween_callback(func(): _wobble_and_blink(ball, -22.0))
		# Tick 4 at 3.9s
		tw.tween_interval(1.2)
		tw.tween_callback(func(): _wobble_and_blink(ball, 22.0))
		# At 5.0s: Celebration & stars!
		tw.tween_interval(1.1)
		tw.tween_callback(func(): _caught_celebration_animation(ball, ground_pos, callback))

func _wobble_and_blink(ball: TextureRect, angle: float) -> void:
	if not is_instance_valid(ball):
		return
	
	# Tilt left or right and snap back
	var r_tw = create_tween()
	r_tw.tween_property(ball, "rotation_degrees", angle, 0.12).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	r_tw.tween_property(ball, "rotation_degrees", 0.0, 0.18).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
	
	# Pulse / blink red light on the ball center
	var c_tw = create_tween()
	c_tw.tween_property(ball, "modulate", Color(2.8, 0.4, 0.4, 1.0), 0.1)
	c_tw.tween_property(ball, "modulate", Color.WHITE, 0.2)

func _vibrate_ball(ball: TextureRect, duration: float) -> void:
	if not is_instance_valid(ball):
		return
	var vib_tw = create_tween()
	var step_count = 6
	var step_time = duration / float(step_count * 2)
	for i in range(step_count):
		vib_tw.tween_property(ball, "rotation_degrees", -8.0, step_time)
		vib_tw.tween_property(ball, "rotation_degrees", 8.0, step_time)
	vib_tw.tween_property(ball, "rotation_degrees", 0.0, 0.05)

func _break_free_animation(ball: TextureRect, ground_pos: Vector2, callback: Callable) -> void:
	var arena = $Arena
	if not is_instance_valid(arena):
		callback.call()
		return
	
	# 1. Burst visual flash ring
	var burst_flash = ColorRect.new()
	burst_flash.custom_minimum_size = Vector2(60, 60)
	burst_flash.size = Vector2(60, 60)
	burst_flash.pivot_offset = Vector2(30, 30)
	burst_flash.position = ground_pos - Vector2(8, 8)
	burst_flash.color = Color(3.0, 2.5, 1.2, 0.95)
	burst_flash.z_index = 25
	arena.add_child(burst_flash)
	
	var flash_tw = create_tween().set_parallel(true)
	flash_tw.tween_property(burst_flash, "scale", Vector2(3.0, 3.0), 0.25).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	flash_tw.tween_property(burst_flash, "modulate:a", 0.0, 0.25)
	flash_tw.chain().tween_callback(burst_flash.queue_free)
	
	# Spawn burst particles / sparks
	_spawn_spark_burst(ground_pos + Vector2(22, 22), Color(1.0, 0.4, 0.3), 8)
	
	# Remove Poké Ball
	ball.queue_free()
	
	# 2. Opponent Pokémon bursts back onto screen with power
	if is_instance_valid(opponent_sprite):
		opponent_sprite.visible = true
		opponent_sprite.scale = Vector2(0.1, 0.1)
		opponent_sprite.modulate = Color(3.0, 1.4, 1.4, 1.0)
		
		var reemerge_tw = create_tween().set_parallel(true)
		reemerge_tw.tween_property(opponent_sprite, "scale", Vector2.ONE, 0.35).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
		reemerge_tw.tween_property(opponent_sprite, "modulate", Color.WHITE, 0.4)
		
		# Roar shake on opponent sprite
		var shake_tw = create_tween()
		var orig_x = opponent_sprite.position.x
		shake_tw.tween_property(opponent_sprite, "position:x", orig_x - 12, 0.05)
		shake_tw.tween_property(opponent_sprite, "position:x", orig_x + 12, 0.05)
		shake_tw.tween_property(opponent_sprite, "position:x", orig_x - 6, 0.05)
		shake_tw.tween_property(opponent_sprite, "position:x", orig_x, 0.05)
	
	# Restore Opponent HUD
	var opp_panel = $BattleUI/OpponentPanel
	if is_instance_valid(opp_panel):
		var panel_tw = create_tween()
		panel_tw.tween_property(opp_panel, "modulate:a", 1.0, 0.3)
	
	get_tree().create_timer(0.45).timeout.connect(func():
		callback.call()
	)

func _caught_celebration_animation(ball: TextureRect, ground_pos: Vector2, callback: Callable) -> void:
	if not is_instance_valid(ball):
		callback.call()
		return
	
	# Click effect: ball button locks in with pop
	var click_tw = create_tween()
	click_tw.tween_property(ball, "scale", Vector2(0.85, 0.85), 0.08)
	click_tw.tween_property(ball, "scale", Vector2(1.1, 1.1), 0.1)
	click_tw.tween_property(ball, "scale", Vector2.ONE, 0.08)
	click_tw.tween_property(ball, "modulate", Color(1.3, 1.3, 1.1, 1.0), 0.1)
	
	# Spawn golden celebration stars
	_spawn_star_celebration(ground_pos + Vector2(22, 22))
	
	# Fade ball out smoothly before next turn screen
	var fade_tw = create_tween()
	fade_tw.tween_interval(0.6)
	fade_tw.tween_property(ball, "modulate:a", 0.0, 0.5)
	fade_tw.tween_callback(ball.queue_free)
	
	get_tree().create_timer(0.8).timeout.connect(func():
		callback.call()
	)

func _spawn_star_celebration(center: Vector2) -> void:
	var arena = $Arena
	if not is_instance_valid(arena):
		return
	
	var star_count = 8
	var star_chars = ["✨", "⭐", "🌟", "✨", "⭐", "🌟", "✨", "⭐"]
	for i in range(star_count):
		var star = Label.new()
		star.text = star_chars[i % star_chars.size()]
		star.add_theme_font_size_override("font_size", 22)
		star.self_modulate = Color(1.0, 0.9, 0.2, 1.0)
		star.position = center - Vector2(12, 12)
		star.z_index = 25
		arena.add_child(star)
		
		var angle = (float(i) / float(star_count)) * TAU
		var dist = randf_range(50.0, 95.0)
		var dest = center + Vector2(cos(angle), sin(angle)) * dist - Vector2(0, 30)
		
		var tw = create_tween().set_parallel(true)
		tw.tween_property(star, "position", dest, 0.7).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
		tw.tween_property(star, "scale", Vector2(1.4, 1.4), 0.35)
		tw.tween_property(star, "scale", Vector2(0.2, 0.2), 0.35).set_delay(0.35)
		tw.tween_property(star, "modulate:a", 0.0, 0.7)
		tw.chain().tween_callback(star.queue_free)

func _spawn_spark_burst(center: Vector2, color: Color, count: int) -> void:
	var arena = $Arena
	if not is_instance_valid(arena):
		return
	
	for i in range(count):
		var p = Label.new()
		p.text = "💥" if (i % 2 == 0) else "⚡"
		p.add_theme_font_size_override("font_size", 18)
		p.self_modulate = color
		p.position = center - Vector2(10, 10)
		p.z_index = 25
		arena.add_child(p)
		
		var angle = (float(i) / float(count)) * TAU
		var dist = randf_range(40.0, 80.0)
		var dest = center + Vector2(cos(angle), sin(angle)) * dist
		
		var tw = create_tween().set_parallel(true)
		tw.tween_property(p, "position", dest, 0.35).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
		tw.tween_property(p, "scale", Vector2(1.4, 1.4), 0.15)
		tw.tween_property(p, "scale", Vector2(0.1, 0.1), 0.2).set_delay(0.15)
		tw.tween_property(p, "modulate:a", 0.0, 0.35)
		tw.chain().tween_callback(p.queue_free)

func _show_action_menu() -> void:
	if continue_btn: continue_btn.visible = false
	action_menu.visible = true
	moves_menu.visible = false
	if bag_menu: bag_menu.visible = false
	if pokemon_menu: pokemon_menu.visible = false
	if talk_menu: talk_menu.visible = false
	fight_btn.grab_focus()

func _on_fight_pressed() -> void:
	if player_pokemon and player_pokemon.refuses_to_battle():
		_queue_message("%s refuses to battle for you! (Trust & Affection below 0)" % player_pokemon.get_display_name())
		return
	action_menu.visible = false
	moves_menu.visible = true
	if bag_menu: bag_menu.visible = false
	if pokemon_menu: pokemon_menu.visible = false
	if talk_menu: talk_menu.visible = false
	if move_btns[0].visible:
		move_btns[0].grab_focus()

func _on_move_selected(index: int) -> void:
	if player_pokemon == null or index >= player_pokemon.attacks.size():
		return
	if player_pokemon.refuses_to_battle():
		_queue_message("%s refuses to battle for you!" % player_pokemon.get_display_name())
		_show_action_menu()
		return
	var chosen_attack = player_pokemon.attacks[index]
	moves_menu.visible = false
	if talk_menu: talk_menu.visible = false
	
	# Query local fine-tuned LLM for opponent tactical action and combat dialogue
	if opponent_pokemon != null and LLMClient != null:
		var act_dict = {
			"species": opponent_pokemon.species_name,
			"level": opponent_pokemon.level,
			"current_hp": opponent_pokemon.current_hp,
			"max_hp": opponent_pokemon.max_hp,
			"known_moves": opponent_pokemon.attacks
		}
		var def_dict = {
			"species": player_pokemon.species_name,
			"level": player_pokemon.level,
			"apparent_health": "wounded" if player_pokemon.current_hp < player_pokemon.max_hp * 0.5 else "healthy"
		}
		var llm_res = await LLMClient.decide_battle_action(act_dict, def_dict, not is_wild, battle_engine.current_turn + 1)
		if not llm_res.is_empty():
			if llm_res.has("chosen_move") and llm_res["chosen_move"] != "":
				battle_engine.set_override_opponent_action(battle_engine.ActionType.ATTACK, llm_res["chosen_move"])
			if llm_res.has("dialogue") and llm_res["dialogue"] != "":
				_queue_message("%s" % llm_res["dialogue"])
	
	battle_engine.select_player_action(battle_engine.ActionType.ATTACK, chosen_attack)
	var result = battle_engine.resolve_turn()
	_process_turn_result(result)

func _on_bag_pressed() -> void:
	action_menu.visible = false
	moves_menu.visible = false
	if pokemon_menu: pokemon_menu.visible = false
	if talk_menu: talk_menu.visible = false
	
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
	
	# Auto-focus first item button or back button for keyboard/WASD navigation
	for ch in vbox.get_children():
		if ch is Button and not ch.disabled:
			ch.grab_focus()
			break

func _on_bag_item_selected(item_id: String) -> void:
	if bag_menu: bag_menu.visible = false
	
	if item_id == "poke_ball":
		if not is_wild:
			_queue_message("You can't capture a trainer's Pokémon!")
			_show_action_menu()
			return
		if GameState.player and GameState.player.get_item_count("poke_ball") > 0:
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
	if talk_menu: talk_menu.visible = false
	
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
	
	# Auto-focus first item button or back button for keyboard/WASD navigation
	for ch in vbox.get_children():
		if ch is Button and not ch.disabled:
			ch.grab_focus()
			break

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
	if talk_menu: talk_menu.visible = false
	battle_engine.select_player_action(battle_engine.ActionType.FLEE)
	var result = battle_engine.resolve_turn()
	_process_turn_result(result)

## Process turn results into a strictly synchronized sequence of action steps
func _process_turn_result(result: Dictionary) -> void:
	var current_attack_name = "Attack"
	var evts = result.get("events", [])
	for e in evts:
		var etype = e.get("type", "")
		match etype:
			"attack_used":
				var atkr = e.get("attacker", "")
				var is_p = (atkr == player_pokemon.get_display_name() or atkr == player_pokemon.species_name or atkr == player_pokemon.nickname)
				current_attack_name = e.get("attack", "Attack")
				_battle_step_queue.append({
					"type": "attack",
					"text": "%s used %s!" % [atkr, current_attack_name],
					"is_player": is_p
				})
			
			"damage_dealt":
				var is_p_hit = e.get("is_player_target", false)
				if not e.has("is_player_target"):
					var def_name = e.get("target", e.get("defender", ""))
					is_p_hit = (def_name == player_pokemon.get_display_name() or def_name == player_pokemon.species_name or def_name == player_pokemon.nickname)
				
				var eff = e.get("type_effectiveness", 1.0)
				var text = "Dealt %d damage!" % e.get("damage", 0)
				if eff > 1.0: text += " Super effective!"
				elif eff < 1.0 and eff > 0.0: text += " Not very effective..."
				elif eff == 0.0: text += " No effect!"
				if e.get("is_critical", false): text += " Critical hit!"
				
				_battle_step_queue.append({
					"type": "damage",
					"text": text,
					"is_player_target": is_p_hit,
					"defender_hp": e.get("defender_hp", 0),
					"defender_max_hp": e.get("defender_max_hp", 10),
					"move_name": current_attack_name,
					"is_super_effective": (eff > 1.0),
					"is_critical": e.get("is_critical", false)
				})
			
			"fainted", "pokemon_fainted":
				var f_name = e.get("pokemon", "")
				var is_p_fainted = e.get("is_player", false)
				if not e.has("is_player"):
					is_p_fainted = (f_name == player_pokemon.get_display_name() or f_name == player_pokemon.species_name or f_name == player_pokemon.nickname)
				_battle_step_queue.append({
					"type": "faint",
					"text": "%s fainted!" % f_name,
					"is_player": is_p_fainted
				})
			
			"switch":
				_battle_step_queue.append({
					"type": "switch",
					"text": "Go, %s!" % e.get("pokemon", "")
				})
			
			"item_used":
				var is_p = e.get("is_player", true)
				var poke = player_pokemon if is_p else opponent_pokemon
				var new_hp = e.get("new_hp", poke.current_hp if poke else -1)
				var max_hp = e.get("max_hp", poke.max_hp if poke else -1)
				_battle_step_queue.append({
					"type": "item_used",
					"text": "Used %s on %s!" % [e.get("item", ""), e.get("target", "")],
					"item": e.get("item", ""),
					"target": e.get("target", ""),
					"is_player": is_p,
					"new_hp": new_hp,
					"max_hp": max_hp,
					"heal_amount": e.get("heal_amount", 0)
				})
			
			"hp_update":
				var is_p = e.get("is_player", true)
				var new_hp = e.get("hp", 0)
				var max_hp = e.get("max_hp", 10)
				if not _battle_step_queue.is_empty():
					var last_step = _battle_step_queue[-1]
					if last_step.get("type") in ["item_used", "message"]:
						last_step["has_hp_update"] = true
						last_step["hp_is_player"] = is_p
						last_step["new_hp"] = new_hp
						last_step["max_hp"] = max_hp
				else:
					_battle_step_queue.append({
						"type": "hp_update",
						"text": "",
						"is_player": is_p,
						"new_hp": new_hp,
						"max_hp": max_hp,
						"has_hp_update": true
					})
			
			"capture_attempt":
				var cap_data = e.get("data", {})
				var success = cap_data.get("success", false)
				_battle_step_queue.append({
					"type": "capture_throw",
					"success": success,
					"text": "Go! Poké Ball!"
				})
				if success:
					_battle_step_queue.append({
						"type": "message",
						"text": "Gotcha! %s was caught!" % opponent_pokemon.get_display_name()
					})
				else:
					_battle_step_queue.append({
						"type": "message",
						"text": "Oh no! The wild Pokémon broke free!"
					})
			
			"flee":
				_battle_step_queue.append({
					"type": "message",
					"text": "Got away safely!" if e.get("success", false) else "Can't escape!"
				})
			
			"eot_status":
				var data = e.get("data", {})
				_battle_step_queue.append({
					"type": "message",
					"text": data.get("message", "")
				})
			
			"message":
				_battle_step_queue.append({
					"type": "message",
					"text": e.get("text", "")
				})
	
	# Check if the turn concluded the battle (victory, defeat, captured, escaped)
	var state = battle_engine.battle_state
	if state != battle_engine.BattleState.IN_PROGRESS and not _battle_concluded:
		_battle_concluded = true
		match state:
			battle_engine.BattleState.VICTORY:
				var xp_gained = opponent_pokemon.level * 40
				var xp_res = player_pokemon.gain_xp(xp_gained)
				_battle_step_queue.append({
					"type": "message",
					"text": "%s gained %d EXP points!" % [player_pokemon.get_display_name(), xp_gained]
				})
				if xp_res.get("levels_gained", 0) > 0:
					_battle_step_queue.append({
						"type": "message",
						"text": "%s grew to level %d!" % [player_pokemon.get_display_name(), player_pokemon.level]
					})
				# Currency prize reward for winning battle
				var prize_money: int = maxi(50, opponent_pokemon.level * 25) if is_wild else maxi(150, opponent_pokemon.level * 50 + 100)
				if GameState.player != null:
					GameState.player.add_currency(prize_money)
					EventBus.currency_changed.emit(GameState.player.currency, prize_money)
				var cur_bal = GameState.player.currency if GameState.player else prize_money
				_battle_step_queue.append({
					"type": "message",
					"text": "Earned %dp prize money! (Wallet: %dp)" % [prize_money, cur_bal]
				})
				if not is_wild:
					var tid = "koji"
					if GameState.has_meta("trainer_id"):
						tid = GameState.get_meta("trainer_id")
					if GameState.player:
						GameState.player.record_trainer_defeat(tid)
					if QuestSystem:
						QuestSystem.on_trainer_defeated(tid)
						QuestSystem.on_trainer_defeated("field_trainer_koji")
					var tname = GameState.get_meta("trainer_name") if GameState.has_meta("trainer_name") else "Trainer"
					_battle_step_queue.append({
						"type": "message",
						"text": "You defeated Trainer %s!" % tname
					})
				EventBus.battle_ended.emit("victory")
			
			battle_engine.BattleState.CAPTURED:
				if GameState.player and opponent_pokemon:
					GameState.player.add_to_collection(opponent_pokemon)
					if GameState.player.team.size() < GameState.player.max_team_size:
						GameState.player.add_to_team(opponent_pokemon)
					EventBus.pokemon_caught.emit(opponent_pokemon)
				EventBus.battle_ended.emit("captured")
			
			battle_engine.BattleState.ESCAPED:
				EventBus.battle_ended.emit("escaped")
			
			battle_engine.BattleState.DEFEAT:
				_battle_step_queue.append({
					"type": "message",
					"text": "You were defeated... Whited out!"
				})
				if GameState.player:
					for p in GameState.player.team:
						p.heal_to_full()
						p.clear_all_statuses()
					GameState.player.player_position = Vector3(25.0, 0.1, 25.0)
				EventBus.battle_ended.emit("defeat")
	
	if not _is_displaying_messages:
		_play_next_step()

func _unhandled_input(event: InputEvent) -> void:
	if _waiting_for_continue:
		var proceed = false
		if event.is_action_pressed("ui_accept"):
			proceed = true
		elif event is InputEventKey and event.pressed and not event.echo:
			if event.keycode in [KEY_SPACE, KEY_ENTER, KEY_KP_ENTER, KEY_E]:
				proceed = true
		elif event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
			proceed = true
		
		if proceed:
			get_viewport().set_input_as_handled()
			_end_battle()
			return
	
	# Skip typewriter during message display
	if _is_displaying_messages and is_instance_valid(_typewriter_tween) and _typewriter_tween.is_running():
		var skip = false
		if event.is_action_pressed("ui_accept"):
			skip = true
		elif event is InputEventKey and event.pressed and not event.echo:
			if event.keycode in [KEY_SPACE, KEY_ENTER, KEY_KP_ENTER, KEY_E]:
				skip = true
		elif event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
			skip = true
		
		if skip:
			_typewriter_tween.custom_step(999.0)
			get_viewport().set_input_as_handled()

func _queue_message(text: String) -> void:
	_battle_step_queue.append({
		"type": "message",
		"text": text
	})
	if not _is_displaying_messages:
		_play_next_step()

func _play_next_step() -> void:
	if _battle_step_queue.is_empty():
		_is_displaying_messages = false
		_on_all_messages_displayed()
		return
	
	_is_displaying_messages = true
	var step = _battle_step_queue.pop_front()
	var stype = step.get("type", "message")
	var msg = step.get("text", "")
	
	message_lbl.text = msg
	message_lbl.visible_ratio = 0.0
	
	if _typewriter_tween and _typewriter_tween.is_valid():
		_typewriter_tween.kill()
	_typewriter_tween = create_tween()
	var tw_duration = min(0.6, max(0.2, msg.length() * 0.02))
	_typewriter_tween.tween_property(message_lbl, "visible_ratio", 1.0, tw_duration)
	
	var step_delay = tw_duration + 0.65
	
	match stype:
		"item_used":
			var is_p = step.get("is_player", true)
			var new_hp = step.get("new_hp", -1)
			var max_hp = step.get("max_hp", -1)
			if new_hp >= 0 and max_hp > 0:
				_apply_heal(is_p, new_hp, max_hp)
			step_delay = tw_duration + 0.65
		
		"hp_update":
			var is_p = step.get("is_player", true)
			var new_hp = step.get("new_hp", -1)
			var max_hp = step.get("max_hp", -1)
			if new_hp >= 0 and max_hp > 0:
				_apply_heal(is_p, new_hp, max_hp)
			step_delay = 0.45

		"capture_throw":
			var success = step.get("success", false)
			_animate_capture_throw(success, func():
				_play_next_step()
			)
			return
		
		"attack":
			# Only the attacker performs an animation. NO HP BARS ARE ALTERED!
			_animate_attack(step.get("is_player", true))
			step_delay = tw_duration + 0.45
		
		"damage":
			# The defender takes the hit. Only the defender's HP bar drains!
			var is_p_target = step.get("is_player_target", false)
			var new_hp = step.get("defender_hp", 0)
			var max_hp = step.get("defender_max_hp", 10)
			
			_animate_hit(is_p_target)
			
			if has_node("/root/BattleTransition"):
				var bt = get_node("/root/BattleTransition")
				bt.play_attack_impact_animation(
					step.get("move_name", "Attack"),
					step.get("is_super_effective", false),
					step.get("is_critical", false)
				)
			
			if is_p_target:
				var current_val = player_hp_bar.value
				var hp_tw = create_tween()
				hp_tw.tween_property(player_hp_bar, "value", float(new_hp), 0.35)
				hp_tw.parallel().tween_method(func(val: float):
					if is_instance_valid(player_hp_text):
						player_hp_text.text = "%d / %d HP" % [int(round(val)), max_hp]
					_update_hp_bar_color(player_hp_bar, int(round(val)), max_hp)
				, current_val, float(new_hp), 0.35)
			else:
				var current_val = opponent_hp_bar.value
				var opp_hp_tw = create_tween()
				opp_hp_tw.tween_property(opponent_hp_bar, "value", float(new_hp), 0.35)
				opp_hp_tw.parallel().tween_method(func(val: float):
					_update_hp_bar_color(opponent_hp_bar, int(round(val)), max_hp)
				, current_val, float(new_hp), 0.35)
			
			step_delay = tw_duration + 0.75
		
		"faint":
			var is_p = step.get("is_player", false)
			var sprite = player_sprite if is_p else opponent_sprite
			var faint_tw = create_tween()
			faint_tw.tween_property(sprite, "modulate:a", 0.0, 0.4)
			step_delay = tw_duration + 0.6
		
		"switch":
			player_pokemon = battle_engine.player_pokemon
			_init_ui_stats()
			_update_move_buttons()

		"message":
			if step.get("has_hp_update", false):
				var is_p = step.get("hp_is_player", true)
				var new_hp = step.get("new_hp", -1)
				var max_hp = step.get("max_hp", -1)
				if new_hp >= 0 and max_hp > 0:
					_apply_heal(is_p, new_hp, max_hp)
			step_delay = tw_duration + 0.65
	
	get_tree().create_timer(step_delay).timeout.connect(_play_next_step)

func _on_all_messages_displayed() -> void:
	if _battle_concluded:
		_show_continue_prompt()
	elif battle_engine.battle_state == battle_engine.BattleState.IN_PROGRESS:
		_show_action_menu()

func _show_continue_prompt() -> void:
	_waiting_for_continue = true
	action_menu.visible = false
	moves_menu.visible = false
	if bag_menu: bag_menu.visible = false
	if pokemon_menu: pokemon_menu.visible = false
	if talk_menu: talk_menu.visible = false
	
	if continue_btn == null:
		continue_btn = Button.new()
		continue_btn.name = "ContinueBtn"
		continue_btn.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		continue_btn.size_flags_vertical = Control.SIZE_EXPAND_FILL
		continue_btn.text = "CONTINUE ▶\n(Press Space or Enter)"
		continue_btn.add_theme_font_size_override("font_size", 18)
		continue_btn.pressed.connect(_end_battle)
		menu_panel.add_child(continue_btn)
	
	continue_btn.visible = true
	continue_btn.grab_focus()

func _end_battle() -> void:
	_waiting_for_continue = false
	SaveLoad.save_game()
	GameState.exit_battle()
	get_tree().change_scene_to_file("res://scenes/World.tscn")

func _on_talk_pressed() -> void:
	action_menu.visible = false
	moves_menu.visible = false
	if bag_menu: bag_menu.visible = false
	if pokemon_menu: pokemon_menu.visible = false
	_create_talk_menu()
	if talk_menu:
		talk_menu.visible = true

func _create_talk_menu() -> void:
	if talk_menu == null:
		talk_menu = ScrollContainer.new()
		talk_menu.name = "TalkMenu"
		talk_menu.custom_minimum_size = Vector2(400, 140)
		menu_panel.add_child(talk_menu)
	
	for c in talk_menu.get_children():
		c.queue_free()
	
	var vbox = VBoxContainer.new()
	vbox.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	talk_menu.add_child(vbox)
	
	var p_name = player_pokemon.get_display_name() if player_pokemon else "Partner"
	var header = Label.new()
	header.text = "Battle Communication with %s:" % p_name
	header.add_theme_font_size_override("font_size", 14)
	vbox.add_child(header)
	
	var presets = [
		{"label": "💡 Ask Move Advice", "text": "What move should we use here?"},
		{"label": "🔥 Cheer & Encourage", "text": "You can do this! Give it everything you've got!"},
		{"label": "⭐ Praise Performance", "text": "Amazing job! That was fantastic!"},
		{"label": "🛡️ Watch Out & Guard", "text": "Careful now! Watch out and stay on your guard!"}
	]
	
	for p in presets:
		var btn = Button.new()
		btn.text = p["label"]
		btn.alignment = HORIZONTAL_ALIGNMENT_LEFT
		btn.pressed.connect(_send_battle_talk.bind(p["text"]))
		vbox.add_child(btn)
	
	var back = Button.new()
	back.text = "← Back"
	back.pressed.connect(_show_action_menu)
	vbox.add_child(back)
	
	for ch in vbox.get_children():
		if ch is Button and not ch.disabled:
			ch.grab_focus()
			break

func _send_battle_talk(msg: String) -> void:
	if talk_menu:
		talk_menu.visible = false
	if player_pokemon == null:
		_show_action_menu()
		return
	
	_queue_message("You: \"%s\"" % msg)
	
	var p_dict = {
		"species": player_pokemon.species_name,
		"species_name": player_pokemon.species_name,
		"nickname": player_pokemon.get_display_name(),
		"bond": float(player_pokemon.level * 10),
		"temperament": "brave"
	}
	var ctx = {
		"current_turn": battle_engine.current_turn if battle_engine else 1,
		"player_hp": player_pokemon.current_hp,
		"player_max_hp": player_pokemon.max_hp,
		"opponent_species": opponent_pokemon.species_name if opponent_pokemon else "Unknown",
		"opponent_apparent_health": ("wounded" if opponent_pokemon and opponent_pokemon.current_hp < opponent_pokemon.max_hp * 0.5 else "healthy"),
		"known_moves": player_pokemon.attacks
	}
	
	var reply = await LLMClient.talk_in_battle(p_dict, msg, ctx, false)
	if not reply.is_empty():
		var dial = reply.get("dialogue", "")
		if dial != "":
			_queue_message(dial)
		
		var delta = int(reply.get("morale_delta", 0))
		active_battle_morale = clampi(active_battle_morale + delta, -10, 10)
		if battle_engine:
			battle_engine.set_player_morale(active_battle_morale)
		
		var tier = reply.get("momentum_tier", "STEADY")
		_update_morale_badge(tier)
		
		var is_restrained = bool(reply.get("is_restrained_strike", false))
		var chosen_move = str(reply.get("chosen_move", ""))
		var precision_dmg = int(reply.get("precision_damage", 0))
		
		if is_restrained and chosen_move != "" and precision_dmg > 0:
			# Auto-execute the restrained strike turn
			battle_engine.set_override_player_damage(precision_dmg)
			battle_engine.select_player_action(battle_engine.ActionType.ATTACK, chosen_move)
			var result = battle_engine.resolve_turn()
			_process_turn_result(result)
			return
		
		var sug = reply.get("tactical_suggestion", "")
		if sug != null and sug != "" and sug != "null":
			_queue_message("%s recommends using %s!" % [player_pokemon.get_display_name(), sug])

func _update_morale_badge(tier: String) -> void:
	if not is_instance_valid(morale_badge):
		return
	
	morale_badge.text = "[%s]" % tier
	match tier:
		"SURGING":
			morale_badge.self_modulate = Color(0.2, 0.9, 1.0)
			morale_badge.tooltip_text = "Morale: Surging (+15% Damage)"
		"STEADY":
			morale_badge.self_modulate = Color(0.4, 0.85, 0.5)
			morale_badge.tooltip_text = "Morale: Steady (Normal)"
		"PRESSURED":
			morale_badge.self_modulate = Color(1.0, 0.7, 0.2)
			morale_badge.tooltip_text = "Morale: Pressured"
		"CRITICAL":
			morale_badge.self_modulate = Color(1.0, 0.3, 0.3)
			morale_badge.tooltip_text = "Morale: Critical (-15% Damage)"
		_:
			morale_badge.self_modulate = Color(0.8, 0.8, 0.8)
			morale_badge.tooltip_text = "Morale: Normal"

func _apply_time_of_day_atmosphere() -> void:
	var tod = GameState.get_time_of_day()
	var bg_tr = $Arena/Background as TextureRect
	var dim_rect = $Arena/Background/DimOverlay as ColorRect
	if not bg_tr or not dim_rect:
		return
	
	match tod:
		"morning":
			bg_tr.modulate = Color(1.0, 0.96, 0.88, 1.0)
			dim_rect.color = Color(0.20, 0.12, 0.05, 0.10)
		"day":
			bg_tr.modulate = Color(1.0, 1.0, 1.0, 1.0)
			dim_rect.color = Color(0.0, 0.0, 0.0, 0.15)
		"evening":
			bg_tr.modulate = Color(1.0, 0.78, 0.65, 1.0)
			dim_rect.color = Color(0.30, 0.10, 0.05, 0.22)
		"night":
			bg_tr.modulate = Color(0.55, 0.60, 0.85, 1.0)
			dim_rect.color = Color(0.04, 0.06, 0.18, 0.42)
