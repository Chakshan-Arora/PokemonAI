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
