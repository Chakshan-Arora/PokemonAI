extends Control
## PartyMenu - Player team management screen

const PokemonInstance = preload("res://scripts/models/PokemonInstance.gd")
const AttackData = preload("res://scripts/data/AttackData.gd")
const PokemonData = preload("res://scripts/data/PokemonData.gd")

@onready var slot_container: VBoxContainer = $Panel/HBox/SlotList/Scroll/VBox
@onready var detail_panel: VBoxContainer = $Panel/HBox/DetailPanel
@onready var name_lbl: Label = $Panel/HBox/DetailPanel/NameLabel
@onready var level_lbl: Label = $Panel/HBox/DetailPanel/LevelLabel
@onready var type_lbl: Label = $Panel/HBox/DetailPanel/TypeLabel
@onready var hp_lbl: Label = $Panel/HBox/DetailPanel/HPLabel
@onready var stats_lbl: Label = $Panel/HBox/DetailPanel/StatsLabel
@onready var moves_lbl: Label = $Panel/HBox/DetailPanel/MovesLabel
@onready var set_active_btn: Button = $Panel/HBox/DetailPanel/SetActiveBtn
@onready var close_btn: Button = $Panel/CloseBtn

var _selected_index: int = 0
var _prev_selected_index: int = -1

func _ready() -> void:
	add_to_group("party_menu")
	visible = false
	process_mode = Node.PROCESS_MODE_ALWAYS
	close_btn.pressed.connect(hide_menu)
	set_active_btn.pressed.connect(_on_set_active_pressed)
	set_active_btn.focus_neighbor_bottom = close_btn.get_path()
	close_btn.focus_neighbor_top = set_active_btn.get_path()

func _input(event: InputEvent) -> void:
	if visible and (event.is_action_pressed("open_party") or event.is_action_pressed("ui_cancel")):
		hide_menu()
		get_viewport().set_input_as_handled()

func _process(_delta: float) -> void:
	if visible and Input.mouse_mode != Input.MOUSE_MODE_VISIBLE:
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE

func show_menu() -> void:
	visible = true
	GameState.pause_game()
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	_prev_selected_index = -1
	_refresh_list()
	if GameState.player != null and not GameState.player.team.is_empty():
		_select_pokemon(0)
		if slot_container.get_child_count() > 0:
			var first_btn = slot_container.get_child(0) as Button
			if first_btn:
				first_btn.grab_focus()

func hide_menu() -> void:
	visible = false
	GameState.resume_game()
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	EventBus.hud_update_requested.emit()

func _refresh_list() -> void:
	# Clear previous buttons
	for child in slot_container.get_children():
		child.queue_free()
	
	if GameState.player == null:
		return
	
	for i in range(GameState.player.team.size()):
		var p: PokemonInstance = GameState.player.team[i]
		var btn = Button.new()
		var prefix = "[ACTIVE] " if i == GameState.player.active_pokemon_index else ""
		btn.text = "%s%s  Lv.%d (%d/%d HP)" % [
			prefix,
			p.get_display_name(),
			p.level,
			p.current_hp,
			p.max_hp
		]
		var p_tex = PokemonData.get_portrait_texture(p.species_name)
		if p_tex:
			btn.icon = p_tex
			btn.expand_icon = true
		btn.alignment = HORIZONTAL_ALIGNMENT_LEFT
		btn.pressed.connect(_select_pokemon.bind(i))
		btn.focus_entered.connect(_select_pokemon.bind(i))
		btn.focus_neighbor_right = set_active_btn.get_path()
		slot_container.add_child(btn)

func _select_pokemon(index: int) -> void:
	_selected_index = index
	if GameState.player == null or index >= GameState.player.team.size():
		return
	var p: PokemonInstance = GameState.player.team[index]
	
	# Portrait in detail panel
	var portrait_tr = detail_panel.get_node_or_null("Portrait") as TextureRect
	if portrait_tr == null:
		portrait_tr = TextureRect.new()
		portrait_tr.name = "Portrait"
		portrait_tr.custom_minimum_size = Vector2(48, 48)
		portrait_tr.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		portrait_tr.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		detail_panel.add_child(portrait_tr)
		detail_panel.move_child(portrait_tr, 0)
	var p_tex = PokemonData.get_portrait_texture(p.species_name)
	if p_tex:
		portrait_tr.texture = p_tex
		portrait_tr.visible = true
	else:
		portrait_tr.visible = false
	
	name_lbl.text = p.get_display_name() + (" (%s)" % p.species_name if p.nickname != "" else "")
	level_lbl.text = "Level %d  (XP: %d / %d)" % [p.level, p.experience, p.get_xp_for_next_level()]
	type_lbl.text = "Type: " + " / ".join(p.types)
	hp_lbl.text = "HP: %d / %d" % [p.current_hp, p.max_hp]
	var pers_summary = p.get_dominant_traits()
	stats_lbl.text = "Attack: %d | Defense: %d | Speed: %d\nBond: %d | Obedience: %d\nPersonality: %s (Agg:%d Cur:%d Loy:%d)" % [
		p.effective_attack(),
		p.effective_defense(),
		p.effective_speed(),
		int(p.bond),
		int(p.obedience),
		pers_summary,
		int(p.personality.get("aggression", 50)),
		int(p.personality.get("curiosity", 50)),
		int(p.personality.get("loyalty", 50))
	]
	
	var moves_str = "Known Moves:\n"
	for atk_name in p.attacks:
		var atk_data = AttackData.get_attack(atk_name)
		moves_str += " • %s (%s, Pwr: %d, Acc: %d%%)\n" % [
			atk_data.get("name", atk_name),
			atk_data.get("type", "Normal"),
			atk_data.get("power", 0),
			atk_data.get("accuracy", 100)
		]
	moves_lbl.text = moves_str
	
	set_active_btn.disabled = (index == GameState.player.active_pokemon_index or p.is_fainted())
	
	# Partner interaction buttons
	var interact_box = detail_panel.get_node_or_null("InteractBox") as HBoxContainer
	if interact_box == null:
		interact_box = HBoxContainer.new()
		interact_box.name = "InteractBox"
		
		var pet_btn = Button.new()
		pet_btn.text = "Pet"
		pet_btn.pressed.connect(_on_pet_pressed)
		interact_box.add_child(pet_btn)
		
		var talk_btn = Button.new()
		talk_btn.text = "Talk"
		talk_btn.pressed.connect(_on_talk_pressed)
		interact_box.add_child(talk_btn)
		
		var play_btn = Button.new()
		play_btn.text = "Play"
		play_btn.pressed.connect(_on_play_pressed)
		interact_box.add_child(play_btn)
		
		detail_panel.add_child(interact_box)
	
	var feedback_lbl = detail_panel.get_node_or_null("FeedbackLabel") as Label
	if feedback_lbl == null:
		feedback_lbl = Label.new()
		feedback_lbl.name = "FeedbackLabel"
		feedback_lbl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		feedback_lbl.add_theme_font_size_override("font_size", 13)
		feedback_lbl.add_theme_color_override("font_color", Color(0.18, 0.32, 0.55, 1.0))
		detail_panel.add_child(feedback_lbl)
	
	if index != _prev_selected_index:
		_prev_selected_index = index
		feedback_lbl.text = ""

func _on_set_active_pressed() -> void:
	if GameState.player != null:
		GameState.player.set_active_pokemon_index(_selected_index)
		_refresh_list()
		_select_pokemon(_selected_index)
		EventBus.hud_update_requested.emit()

func _on_pet_pressed() -> void:
	if GameState.player and _selected_index < GameState.player.team.size():
		var p: PokemonInstance = GameState.player.team[_selected_index]
		p.bond = clamp(p.bond + 3.0, 0.0, 100.0)
		var msg = "You gently patted %s! (Bond +3)" % p.get_display_name()
		var feedback_lbl = detail_panel.get_node_or_null("FeedbackLabel") as Label
		if feedback_lbl:
			feedback_lbl.text = "❤️ " + msg
		EventBus.show_message.emit(msg)
		_select_pokemon(_selected_index)

func _on_talk_pressed() -> void:
	if GameState.player and _selected_index < GameState.player.team.size():
		var p: PokemonInstance = GameState.player.team[_selected_index]
		p.obedience = clamp(p.obedience + 2.0, 0.0, 100.0)
		
		var feedback_lbl = detail_panel.get_node_or_null("FeedbackLabel") as Label
		if feedback_lbl:
			feedback_lbl.text = "💬 Talking with %s..." % p.get_display_name()
		
		if LLMClient:
			EventBus.show_message.emit("%s is thinking..." % p.get_display_name())
			var p_name = GameState.player.player_name if GameState.player else "Trainer"
			var party_prompts = [
				"How are you feeling right now, partner?",
				"What do you think of our journey and adventure so far?",
				"Are you ready for our next battle?",
				"What is on your mind today, buddy?",
				"What kind of moves or training should we focus on next?",
				"Tell me something you like about our team!"
			]
			var random_prompt = party_prompts[randi() % party_prompts.size()]
			var res = await LLMClient.talk_to_companion(p.species_name, random_prompt, p_name, p.obedience, p.bond)
			if not res.is_empty() and res.has("dialogue"):
				var t_delta = float(res.get("trust_delta", 0.0))
				var a_delta = float(res.get("affection_delta", 0.0))
				p.obedience = clamp(p.obedience + t_delta, 0.0, 100.0)
				p.bond = clamp(p.bond + a_delta, 0.0, 100.0)
				var reply = "%s: \"%s\"" % [p.get_display_name(), res["dialogue"]]
				if feedback_lbl:
					feedback_lbl.text = "💬 " + reply
				EventBus.show_message.emit(reply)
				SaveLoad.save_game()
				_select_pokemon(_selected_index)
				return
		
		var default_msg = "%s looks at you affectionately and swishes its tail! (Obedience +2)" % p.get_display_name()
		if feedback_lbl:
			feedback_lbl.text = "💬 " + default_msg
		EventBus.show_message.emit(default_msg)
		SaveLoad.save_game()
		_select_pokemon(_selected_index)

func _on_play_pressed() -> void:
	if GameState.player and _selected_index < GameState.player.team.size():
		var p: PokemonInstance = GameState.player.team[_selected_index]
		p.bond = clamp(p.bond + 4.0, 0.0, 100.0)
		p.obedience = clamp(p.obedience + 2.0, 0.0, 100.0)
		var msg = "You played a game with %s! (Bond +4, Obedience +2)" % p.get_display_name()
		var feedback_lbl = detail_panel.get_node_or_null("FeedbackLabel") as Label
		if feedback_lbl:
			feedback_lbl.text = "⭐ " + msg
		EventBus.show_message.emit(msg)
		_select_pokemon(_selected_index)
