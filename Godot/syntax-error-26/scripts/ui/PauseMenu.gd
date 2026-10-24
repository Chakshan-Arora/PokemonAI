extends Control
## PauseMenu - Pause screen overlay with navigation to menus, saving, and quit

@onready var resume_btn: Button = $Panel/VBox/ResumeBtn
@onready var party_btn: Button = $Panel/VBox/PartyBtn
@onready var bag_btn: Button = $Panel/VBox/BagBtn
@onready var quests_btn: Button = $Panel/VBox/QuestsBtn
@onready var render_distance_lbl: Label = $Panel/VBox/RenderDistanceBox/RenderDistanceLabel
@onready var render_distance_slider: HSlider = $Panel/VBox/RenderDistanceBox/RenderDistanceSlider
@onready var save_btn: Button = $Panel/VBox/SaveBtn
@onready var menu_btn: Button = $Panel/VBox/MenuBtn
@onready var quit_btn: Button = $Panel/VBox/QuitBtn
@onready var status_lbl: Label = $Panel/VBox/StatusLabel

func _ready() -> void:
	add_to_group("pause_menu")
	visible = false
	process_mode = Node.PROCESS_MODE_ALWAYS
	
	resume_btn.pressed.connect(hide_menu)
	party_btn.pressed.connect(_on_party_pressed)
	bag_btn.pressed.connect(_on_bag_pressed)
	quests_btn.pressed.connect(_on_quests_pressed)
	save_btn.pressed.connect(_on_save_pressed)
	menu_btn.pressed.connect(_on_menu_pressed)
	quit_btn.pressed.connect(_on_quit_pressed)
	
	render_distance_slider.min_value = GameState.MIN_RENDER_DISTANCE
	render_distance_slider.max_value = GameState.MAX_RENDER_DISTANCE
	render_distance_slider.step = 10.0
	render_distance_slider.value = GameState.get_render_distance()
	_update_render_distance_display(render_distance_slider.value)
	render_distance_slider.value_changed.connect(_on_render_distance_value_changed)
	
	quests_btn.focus_neighbor_bottom = render_distance_slider.get_path()
	render_distance_slider.focus_neighbor_top = quests_btn.get_path()
	render_distance_slider.focus_neighbor_bottom = save_btn.get_path()
	save_btn.focus_neighbor_top = render_distance_slider.get_path()
	
	resume_btn.focus_neighbor_top = quit_btn.get_path()
	quit_btn.focus_neighbor_bottom = resume_btn.get_path()
	
	for b in [resume_btn, party_btn, bag_btn, quests_btn, save_btn, menu_btn, quit_btn]:
		b.pivot_offset = b.size / 2.0
		b.focus_entered.connect(func():
			var tw = create_tween()
			tw.tween_property(b, "scale", Vector2(1.04, 1.04), 0.08)
		)
		b.focus_exited.connect(func():
			var tw = create_tween()
			tw.tween_property(b, "scale", Vector2(1.0, 1.0), 0.08)
		)
	
	EventBus.open_pause_menu.connect(toggle_menu)

func _input(event: InputEvent) -> void:
	if event.is_action_pressed("pause"):
		if visible:
			hide_menu()
			get_viewport().set_input_as_handled()

func toggle_menu() -> void:
	if visible:
		hide_menu()
	else:
		show_menu()

func _process(_delta: float) -> void:
	if visible and Input.mouse_mode != Input.MOUSE_MODE_VISIBLE:
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE

func show_menu() -> void:
	visible = true
	GameState.pause_game()
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	status_lbl.text = ""
	if is_instance_valid(render_distance_slider):
		render_distance_slider.value = GameState.get_render_distance()
		_update_render_distance_display(render_distance_slider.value)
	resume_btn.grab_focus()

func _on_render_distance_value_changed(val: float) -> void:
	GameState.set_render_distance(val)
	_update_render_distance_display(val)

func _update_render_distance_display(val: float) -> void:
	var preset = ""
	if val <= 60.0:
		preset = " (Very Near)"
	elif val <= 150.0:
		preset = " (Near)"
	elif val <= 300.0:
		preset = " (Medium)"
	elif val <= 450.0:
		preset = " (Far)"
	else:
		preset = " (Ultra)"
	if is_instance_valid(render_distance_lbl):
		render_distance_lbl.text = "Render Distance: %d m%s" % [int(val), preset]

func hide_menu() -> void:
	visible = false
	GameState.resume_game()
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE

func _on_party_pressed() -> void:
	hide_menu()
	EventBus.open_party_menu.emit()

func _on_bag_pressed() -> void:
	hide_menu()
	EventBus.open_inventory_ui.emit()

func _on_quests_pressed() -> void:
	hide_menu()
	EventBus.open_quest_journal.emit()

func _on_save_pressed() -> void:
	var success = SaveLoad.save_game()
	if success:
		status_lbl.text = "Game saved successfully!"
		EventBus.show_message.emit("Game saved!")
	else:
		status_lbl.text = "Failed to save game."

func _on_menu_pressed() -> void:
	hide_menu()
	get_tree().change_scene_to_file("res://scenes/MainMenu.tscn")

func _on_quit_pressed() -> void:
	get_tree().quit()

