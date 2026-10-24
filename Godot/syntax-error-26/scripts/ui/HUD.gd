extends Control
## HUD - Heads-Up Display showing player status, active Pokemon, region, time, and interaction prompt

const RegionData = preload("res://scripts/data/RegionData.gd")
const ItemData = preload("res://scripts/data/ItemData.gd")

@onready var pokemon_panel: PanelContainer = $TopLeft/PokemonPanel
@onready var pokemon_name_lbl: Label = $TopLeft/PokemonPanel/VBox/NameLabel
@onready var pokemon_level_lbl: Label = $TopLeft/PokemonPanel/VBox/LevelLabel
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
	
	update_hud()
	_build_companion_dialogue_ui()

var companion_panel: PanelContainer = null
var companion_input: LineEdit = null
var companion_output_lbl: Label = null
var companion_send_btn: Button = null
var companion_close_btn: Button = null

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
	vbox.theme_override_constants.separation = 8
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
	input_hbox.add_child(companion_input)
	
	companion_send_btn = Button.new()
	companion_send_btn.text = "Send"
	companion_send_btn.pressed.connect(func(): _on_companion_message_submitted(companion_input.text))
	input_hbox.add_child(companion_send_btn)
	
	add_child(companion_panel)

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == KEY_C:
			_toggle_companion_chat()

func _toggle_companion_chat() -> void:
	if companion_panel:
		companion_panel.visible = not companion_panel.visible
		if companion_panel.visible and companion_input:
			companion_input.grab_focus()

func _close_companion_chat() -> void:
	if companion_panel:
		companion_panel.visible = false

func _on_companion_message_submitted(text: String) -> void:
	var msg = text.strip_edges()
	if msg == "":
		return
	var active_p = GameState.get_active_pokemon()
	if not active_p:
		companion_output_lbl.text = "No active partner Pokémon!"
		return
	
	companion_output_lbl.text = "Thinking..."
	companion_input.text = ""
	
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
	else:
		pokemon_panel.visible = false
	
	var r_data = RegionData.get_region(GameState.current_region_id)
	region_label.text = r_data.get("name", "Unknown Region")

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
