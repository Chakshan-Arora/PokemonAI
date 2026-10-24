extends Control
## PartyMenu - Player team management screen

const PokemonInstance = preload("res://scripts/models/PokemonInstance.gd")

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

func _ready() -> void:
	add_to_group("party_menu")
	visible = false
	process_mode = Node.PROCESS_MODE_ALWAYS
	close_btn.pressed.connect(hide_menu)
	set_active_btn.pressed.connect(_on_set_active_pressed)

func _input(event: InputEvent) -> void:
	if visible and (event.is_action_pressed("open_party") or event.is_action_pressed("ui_cancel")):
		hide_menu()
		get_viewport().set_input_as_handled()

func show_menu() -> void:
	visible = true
	GameState.pause_game()
	_refresh_list()
	if GameState.player != null and not GameState.player.team.is_empty():
		_select_pokemon(0)

func hide_menu() -> void:
	visible = false
	GameState.resume_game()
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
		btn.alignment = HORIZONTAL_ALIGNMENT_LEFT
		btn.pressed.connect(_select_pokemon.bind(i))
		slot_container.add_child(btn)

func _select_pokemon(index: int) -> void:
	_selected_index = index
	if GameState.player == null or index >= GameState.player.team.size():
		return
	var p: PokemonInstance = GameState.player.team[index]
	name_lbl.text = p.get_display_name() + (" (%s)" % p.species_name if p.nickname != "" else "")
	level_lbl.text = "Level %d  (XP: %d / %d)" % [p.level, p.experience, p.get_xp_for_next_level()]
	type_lbl.text = "Type: " + " / ".join(p.types)
	hp_lbl.text = "HP: %d / %d" % [p.current_hp, p.max_hp]
	stats_lbl.text = "Attack: %d | Defense: %d | Speed: %d\nBond: %d | Obedience: %d" % [
		p.effective_attack(),
		p.effective_defense(),
		p.effective_speed(),
		int(p.bond),
		int(p.obedience)
	]
	
	var moves_str = "Known Moves:\n"
	for m in p.attacks:
		moves_str += " • %s (%s, Pwr: %d, Acc: %d%%)\n" % [
			m.get("name", "Unknown"),
			m.get("type", "Normal"),
			m.get("power", 0),
			m.get("accuracy", 100)
		]
	moves_lbl.text = moves_str
	
	set_active_btn.disabled = (index == GameState.player.active_pokemon_index or p.is_fainted())

func _on_set_active_pressed() -> void:
	if GameState.player != null:
		GameState.player.set_active_pokemon_index(_selected_index)
		_refresh_list()
		_select_pokemon(_selected_index)
		EventBus.hud_update_requested.emit()
