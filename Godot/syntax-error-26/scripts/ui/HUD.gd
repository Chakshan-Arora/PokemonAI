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

var _banner_timer: float = 0.0

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

func _process(delta: float) -> void:
	if message_banner.visible:
		_banner_timer -= delta
		if _banner_timer <= 0.0:
			message_banner.visible = false
	
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
			t_name.add_theme_color_override("font_color", Color(1.0, 0.9, 0.5))
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
		q_title.add_theme_color_override("font_color", Color(1.0, 0.85, 0.3))
		q_vbox.add_child(q_title)
		
		var q_obj = Label.new()
		q_obj.name = "QObj"
		q_obj.add_theme_font_size_override("font_size", 12)
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
		
		var lbl = Label.new()
		lbl.add_theme_font_size_override("font_size", 12)
		lbl.add_theme_color_override("font_color", Color(0.85, 0.9, 1.0, 0.9))
		lbl.text = " [W/A/S/D] Move  |  [Shift] Sprint  |  [RMB] Camera  |  [E] Interact  |  [Tab] Party  |  [I] Bag  |  [J] Quests  |  [Esc] Menu "
		guide.add_child(lbl)

func set_interaction_prompt(visible_state: bool, text: String = "") -> void:
	interact_prompt.visible = visible_state
	if visible_state:
		prompt_label.text = "[E] " + text

func show_notification(text: String, duration: float = 3.0) -> void:
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
