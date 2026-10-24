extends Control
## HUD - Heads-Up Display showing player status, active Pokemon, region, time, and interaction prompt

const RegionData = preload("res://scripts/data/RegionData.gd")
const ItemData = preload("res://scripts/data/ItemData.gd")
const PokemonData = preload("res://scripts/data/PokemonData.gd")
const QuestData = preload("res://scripts/data/QuestData.gd")

@onready var pokemon_panel: PanelContainer = $TopLeft/PokemonPanel
@onready var pokemon_name_lbl: Label = $TopLeft/PokemonPanel/VBox/HBox/NameLabel
@onready var pokemon_level_lbl: Label = $TopLeft/PokemonPanel/VBox/HBox/LevelLabel
@onready var hp_bar: ProgressBar = $TopLeft/PokemonPanel/VBox/HPBar
@onready var hp_text_lbl: Label = $TopLeft/PokemonPanel/VBox/HPTextLabel

@onready var time_label: Label = $TopRight/TimePanel/VBox/TimeLabel
@onready var tod_label: Label = $TopRight/TimePanel/VBox/TODLabel

@onready var region_label: Label = $BottomLeft/RegionPanel/VBox/RegionLabel
@onready var interact_prompt: PanelContainer = $CenterPrompt/InteractPrompt
@onready var prompt_label: Label = $CenterPrompt/InteractPrompt/PromptLabel

@onready var message_banner: PanelContainer = $TopCenter/MessageBanner
@onready var message_label: Label = $TopCenter/MessageBanner/MessageLabel

@onready var dialogue_box: PanelContainer = get_node_or_null("DialogueBox")
@onready var dialogue_label: Label = get_node_or_null("DialogueBox/HBox/VBox/DialogueLabel")
@onready var speaker_label: Label = get_node_or_null("DialogueBox/HBox/VBox/SpeakerLabel")
@onready var dialogue_portrait: TextureRect = get_node_or_null("DialogueBox/HBox/Portrait")

var _banner_timer: float = 0.0
var _dialogue_timer: float = 0.0

func _ready() -> void:
	interact_prompt.visible = false
	message_banner.visible = false
	
	EventBus.hud_update_requested.connect(update_hud)
	EventBus.region_discovered.connect(_on_region_discovered)
	EventBus.item_obtained.connect(_on_item_obtained)
	EventBus.show_message.connect(show_notification)
	
	GameState.region_changed.connect(_on_region_changed)
	GameState.game_time_changed.connect(_on_game_time_changed)
	
	EventBus.quest_updated.connect(func(_a, _b, _c, _d): update_hud())
	EventBus.quest_completed.connect(func(_a): update_hud())
	EventBus.quest_started.connect(func(_a): update_hud())
	
	update_hud()
	_build_companion_dialogue_ui()

var companion_panel: PanelContainer = null
var companion_input: LineEdit = null
var companion_output_lbl: Label = null
var companion_send_btn: Button = null
var companion_close_btn: Button = null
var _dialogue_tween: Tween = null

func _build_companion_dialogue_ui() -> void:
	companion_panel = PanelContainer.new()
	companion_panel.name = "CompanionChatPanel"
	companion_panel.anchors_preset = Control.PRESET_CENTER
	companion_panel.anchor_left = 0.5
	companion_panel.anchor_top = 0.5
	companion_panel.anchor_right = 0.5
	companion_panel.anchor_bottom = 0.5
	companion_panel.offset_left = -230
	companion_panel.offset_top = -100
	companion_panel.offset_right = 230
	companion_panel.offset_bottom = 100
	companion_panel.custom_minimum_size = Vector2(460, 200)
	companion_panel.visible = false
	
	var vbox = VBoxContainer.new()
	vbox.add_theme_constant_override("separation", 8)
	companion_panel.add_child(vbox)
	
	var header_hbox = HBoxContainer.new()
	vbox.add_child(header_hbox)
	
	var title = Label.new()
	title.text = "💬 Partner Pokémon (Local LLM)"
	title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	header_hbox.add_child(title)
	
	companion_close_btn = Button.new()
	companion_close_btn.text = " ✕ "
	companion_close_btn.pressed.connect(_close_companion_chat)
	header_hbox.add_child(companion_close_btn)
	
	companion_output_lbl = Label.new()
	companion_output_lbl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	companion_output_lbl.text = "Speak freely with your partner Pokemon (press C to toggle)..."
	companion_output_lbl.size_flags_vertical = Control.SIZE_EXPAND_FILL
	vbox.add_child(companion_output_lbl)
	
	var input_hbox = HBoxContainer.new()
	vbox.add_child(input_hbox)
	
	companion_input = LineEdit.new()
	companion_input.placeholder_text = "Type message to your partner..."
	companion_input.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	companion_input.text_submitted.connect(_on_companion_message_submitted)
	companion_input.focus_entered.connect(func(): GameState.set_meta("typing_active", true))
	companion_input.focus_exited.connect(func():
		if not (companion_panel and companion_panel.visible):
			GameState.set_meta("typing_active", false)
	)
	input_hbox.add_child(companion_input)
	
	companion_send_btn = Button.new()
	companion_send_btn.text = "Send"
	companion_send_btn.pressed.connect(func(): _on_companion_message_submitted(companion_input.text))
	input_hbox.add_child(companion_send_btn)
	
	add_child(companion_panel)

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		if companion_panel and companion_panel.visible:
			if event.keycode == KEY_ESCAPE:
				_close_companion_chat()
				get_viewport().set_input_as_handled()
				return
		if event.keycode == KEY_C:
			# Do not toggle with C if typing inside companion input
			if not (companion_input and companion_input.has_focus()):
				_toggle_companion_chat()
				get_viewport().set_input_as_handled()

func _toggle_companion_chat() -> void:
	if companion_panel:
		companion_panel.visible = not companion_panel.visible
		if companion_panel.visible:
			GameState.set_meta("typing_active", true)
			if companion_input:
				companion_input.grab_focus()
		else:
			GameState.set_meta("typing_active", false)
			if companion_input and companion_input.has_focus():
				companion_input.release_focus()

func _close_companion_chat() -> void:
	if companion_panel:
		companion_panel.visible = false
		GameState.set_meta("typing_active", false)
		if companion_input and companion_input.has_focus():
			companion_input.release_focus()

func _on_companion_message_submitted(text: String) -> void:
	var msg = text.strip_edges()
	if msg == "":
		return
	var active_p = GameState.get_active_pokemon()
	if not active_p:
		companion_output_lbl.text = "No active partner Pokémon!"
		return
	
	companion_output_lbl.text = "%s is thinking..." % active_p.get_display_name()
	companion_input.text = ""
	companion_input.grab_focus()
	GameState.set_meta("typing_active", true)
	
	var p_name = GameState.player.player_name if GameState.player else "Trainer"
	var res = await LLMClient.talk_to_companion(active_p.species_name, msg, p_name)
	
	if not res.is_empty():
		companion_output_lbl.text = "%s: \"%s\"\n[State: %s | Trust: +%.1f | Affection: +%.1f]" % [
			active_p.get_display_name(),
			res.get("dialogue", ""),
			res.get("emotional_state", "pleased").capitalize(),
			float(res.get("trust_delta", 0.0)),
			float(res.get("affection_delta", 0.0))
		]
		show_notification("Spoke with %s!" % active_p.get_display_name(), 3.0)
	else:
		companion_output_lbl.text = "%s looked attentively, but couldn't answer." % active_p.get_display_name()

func _process(delta: float) -> void:
	if message_banner.visible:
		_banner_timer -= delta
		if _banner_timer <= 0.0:
			message_banner.visible = false
	
	if dialogue_box and dialogue_box.visible:
		_dialogue_timer -= delta
		if _dialogue_timer <= 0.0:
			dialogue_box.visible = false
	
	# Update time display smoothly
	time_label.text = GameState.get_formatted_time()
	tod_label.text = GameState.get_time_of_day().capitalize()

func update_hud() -> void:
	var active_p = GameState.get_active_pokemon()
	if active_p:
		pokemon_panel.visible = true
		pokemon_name_lbl.text = active_p.get_display_name()
		pokemon_level_lbl.text = "Lv. %d" % active_p.level
		hp_bar.max_value = active_p.max_hp
		hp_bar.value = active_p.current_hp
		
		# Health color gradient styling
		var ratio = float(active_p.current_hp) / float(max(1, active_p.max_hp))
		var hp_fill = StyleBoxFlat.new()
		hp_fill.set_corner_radius_all(3)
		if ratio > 0.5:
			hp_fill.bg_color = Color("#38a169") # Green
		elif ratio > 0.2:
			hp_fill.bg_color = Color("#dd6b20") # Orange
		else:
			hp_fill.bg_color = Color("#e53e3e") # Red
		hp_bar.add_theme_stylebox_override("fill", hp_fill)
		
		hp_text_lbl.text = "%d / %d HP" % [active_p.current_hp, active_p.max_hp]
		
		# Trainer profile header
		var vbox = $TopLeft/PokemonPanel/VBox
		var trainer_bar = vbox.get_node_or_null("TrainerBar") as HBoxContainer
		if trainer_bar == null:
			trainer_bar = HBoxContainer.new()
			trainer_bar.name = "TrainerBar"
			vbox.add_child(trainer_bar)
			vbox.move_child(trainer_bar, 0)
			
			var t_icon = TextureRect.new()
			t_icon.name = "TrainerIcon"
			t_icon.custom_minimum_size = Vector2(24, 24)
			t_icon.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
			t_icon.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
			trainer_bar.add_child(t_icon)
			
			var t_name = Label.new()
			t_name.name = "TrainerName"
			t_name.add_theme_font_size_override("font_size", 13)
			t_name.add_theme_color_override("font_color", Color(0.15, 0.28, 0.5, 1.0))
			trainer_bar.add_child(t_name)
		
		if GameState.player:
			var t_icon = trainer_bar.get_node_or_null("TrainerIcon") as TextureRect
			var avatar = GameState.player.trainer_avatar
			var a_path = "res://assets/sprites/trainers/%s.png" % avatar
			if ResourceLoader.exists(a_path) and t_icon:
				t_icon.texture = load(a_path) as Texture2D
			var t_name = trainer_bar.get_node_or_null("TrainerName") as Label
			if t_name:
				t_name.text = "%s  (Bond: %d%%)" % [GameState.player.player_name, int(active_p.bond)]
		
		# Display PMD portrait if available
		var hbox = $TopLeft/PokemonPanel/VBox/HBox
		var portrait_tr = hbox.get_node_or_null("Portrait") as TextureRect
		if portrait_tr == null:
			portrait_tr = TextureRect.new()
			portrait_tr.name = "Portrait"
			portrait_tr.custom_minimum_size = Vector2(36, 36)
			portrait_tr.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
			portrait_tr.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
			hbox.add_child(portrait_tr)
			hbox.move_child(portrait_tr, 0)
		
		var p_tex = PokemonData.get_portrait_texture(active_p.species_name)
		if p_tex:
			portrait_tr.texture = p_tex
			portrait_tr.visible = true
		else:
			portrait_tr.visible = false
	else:
		pokemon_panel.visible = false
	
	var r_data = RegionData.get_region(GameState.current_region_id)
	region_label.text = r_data.get("name", "Unknown Region")
	
	# Active Quest Tracker widget
	var quest_tracker = $TopRight.get_node_or_null("QuestTracker") as PanelContainer
	if quest_tracker == null:
		quest_tracker = PanelContainer.new()
		quest_tracker.name = "QuestTracker"
		quest_tracker.custom_minimum_size = Vector2(220, 60)
		quest_tracker.position = Vector2(0, 75)
		$TopRight.add_child(quest_tracker)
		
		var q_vbox = VBoxContainer.new()
		q_vbox.name = "QVBox"
		quest_tracker.add_child(q_vbox)
		
		var q_title = Label.new()
		q_title.name = "QTitle"
		q_title.add_theme_font_size_override("font_size", 13)
		q_title.add_theme_color_override("font_color", Color(0.15, 0.28, 0.5, 1.0))
		q_vbox.add_child(q_title)
		
		var q_obj = Label.new()
		q_obj.name = "QObj"
		q_obj.add_theme_font_size_override("font_size", 12)
		q_obj.add_theme_color_override("font_color", Color(0.18, 0.22, 0.28, 1.0))
		q_obj.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		q_vbox.add_child(q_obj)
	
	if GameState.player and not GameState.player.active_quest_ids.is_empty():
		var qid = GameState.player.active_quest_ids[0]
		var qdata = QuestData.get_quest(qid)
		var q_title = quest_tracker.get_node_or_null("QVBox/QTitle") as Label
		var q_obj = quest_tracker.get_node_or_null("QVBox/QObj") as Label
		if q_title: q_title.text = "🎯 " + qdata.get("title", qid)
		if q_obj:
			var obj_str = ""
			var p_prog = GameState.player.quest_progress.get(qid, {})
			for o in qdata.get("objectives", []):
				var oid = o.get("objective_id", o.get("id", ""))
				var target = o.get("target", o.get("target_count", 1))
				var cur = p_prog.get(oid, 0)
				obj_str += "• %s (%d/%d)\n" % [o.get("description", ""), cur, target]
			q_obj.text = obj_str.strip_edges()
		quest_tracker.visible = true
	else:
		quest_tracker.visible = false
	
	# Quick Controls Pill Bar at bottom right
	var guide = get_node_or_null("ControlsGuide") as PanelContainer
	if guide == null:
		guide = PanelContainer.new()
		guide.name = "ControlsGuide"
		guide.layout_mode = 1
		guide.anchors_preset = Control.PRESET_BOTTOM_RIGHT
		guide.grow_horizontal = Control.GROW_DIRECTION_BEGIN
		guide.grow_vertical = Control.GROW_DIRECTION_BEGIN
		guide.offset_left = -660.0
		guide.offset_top = -42.0
		guide.offset_right = -16.0
		guide.offset_bottom = -12.0
		add_child(guide)
		
		var sb = StyleBoxFlat.new()
		sb.bg_color = Color(0.1, 0.14, 0.22, 0.9)
		sb.border_color = Color(0.25, 0.35, 0.5, 0.8)
		sb.set_border_width_all(1)
		sb.set_corner_radius_all(6)
		sb.set_content_margin_all(5.0)
		guide.add_theme_stylebox_override("panel", sb)
		
		var lbl = Label.new()
		lbl.add_theme_font_size_override("font_size", 12)
		lbl.add_theme_color_override("font_color", Color(1.0, 1.0, 1.0, 0.95))
		lbl.text = " [W/A/S/D] Move  |  [Shift] Sprint  |  [RMB] Camera  |  [E] Interact  |  [Tab] Party  |  [I] Bag  |  [J] Quests  |  [Esc] Menu "
		guide.add_child(lbl)

func set_interaction_prompt(visible_state: bool, text: String = "") -> void:
	interact_prompt.visible = visible_state
	if visible_state:
		prompt_label.text = "[E] " + text

func show_notification(text: String, duration: float = 3.0) -> void:
	if dialogue_box and text.length() > 22:
		# Show rich dialogue box with portrait and typewriter effect
		var speaker = "Notice"
		var portrait_path = ""
		if "Oak" in text:
			speaker = "Professor Oak"
			portrait_path = "res://assets/sprites/trainers/red.png"
		elif "Koji" in text:
			speaker = "Trainer Koji"
			portrait_path = "res://assets/sprites/trainers/koji.png"
		elif "campfire" in text.to_lower() or "healed" in text.to_lower():
			speaker = "Campfire Rest Area"
			portrait_path = "res://assets/sprites/world/campfire.png"
		elif "sign" in text.to_lower() or "route" in text.to_lower():
			speaker = "Wooden Signpost"
			portrait_path = "res://assets/sprites/world/sign.png"
		elif "obtained" in text.to_lower() or "cache" in text.to_lower():
			speaker = "Item Recovery"
			portrait_path = "res://assets/sprites/items/poke_ball.png"
		elif "shrine" in text.to_lower():
			speaker = "Ancient Shrine"
			portrait_path = "res://assets/sprites/world/rock.png"
		
		if speaker_label:
			speaker_label.text = speaker
		if dialogue_portrait:
			if portrait_path != "" and ResourceLoader.exists(portrait_path):
				dialogue_portrait.texture = load(portrait_path)
				dialogue_portrait.visible = true
			else:
				dialogue_portrait.visible = false
		if dialogue_label:
			dialogue_label.text = text
			dialogue_label.visible_ratio = 0.0
			if _dialogue_tween and _dialogue_tween.is_valid():
				_dialogue_tween.kill()
			_dialogue_tween = create_tween()
			_dialogue_tween.tween_property(dialogue_label, "visible_ratio", 1.0, 0.4)
		
		dialogue_box.visible = true
		_dialogue_timer = duration + 0.5
	else:
		message_label.text = text
		message_banner.visible = true
		_banner_timer = duration

func _on_region_changed(region_id: String) -> void:
	var r_data = RegionData.get_region(region_id)
	region_label.text = r_data.get("name", region_id)

func _on_region_discovered(region_id: String, region_name: String) -> void:
	show_notification("Discovered: " + region_name + "!", 4.0)

func _on_item_obtained(item_id: String, quantity: int) -> void:
	var item_data = ItemData.get_item(item_id)
	var iname = item_data.get("name", item_id)
	show_notification("Obtained %dx %s!" % [quantity, iname], 3.0)

func _on_game_time_changed(_new_time: float, _new_tod: String) -> void:
	time_label.text = GameState.get_formatted_time()
	tod_label.text = _new_tod.capitalize()
