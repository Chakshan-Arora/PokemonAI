extends Control
## MainMenu - Main menu screen logic

@onready var main_buttons_container: VBoxContainer = $VBoxContainer
@onready var new_game_btn: Button = $VBoxContainer/NewGameBtn
@onready var continue_btn: Button = $VBoxContainer/ContinueBtn
@onready var quit_btn: Button = $VBoxContainer/QuitBtn
@onready var dialog_panel: Panel = $DialogPanel
@onready var player_name_input: LineEdit = $DialogPanel/VBox/NameInput
@onready var start_btn: Button = $DialogPanel/VBox/StartBtn
@onready var back_btn: Button = $DialogPanel/VBox/BackBtn
@onready var save_info_label: Label = $VBoxContainer/SaveInfoLabel

var selected_avatar: String = "ash"

func _ready() -> void:
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	new_game_btn.pressed.connect(_on_new_game_pressed)
	continue_btn.pressed.connect(_on_continue_pressed)
	quit_btn.pressed.connect(_on_quit_pressed)
	start_btn.pressed.connect(_on_start_pressed)
	back_btn.pressed.connect(_on_back_pressed)
	dialog_panel.visible = false
	main_buttons_container.visible = true
	
	# Setup avatar buttons in dialog panel
	_setup_avatar_selection()
	
	# Update continue button state
	if SaveLoad.save_exists():
		continue_btn.disabled = false
		var preview = SaveLoad.get_save_preview()
		if not preview.is_empty():
			save_info_label.text = "Save: %s | Team: %d | Caught: %d" % [
				preview.get("player_name", "?"),
				preview.get("team_size", 0),
				preview.get("total_catches", 0)
			]
	else:
		continue_btn.disabled = true
		save_info_label.text = "No save file found."

func _setup_avatar_selection() -> void:
	var vbox = $DialogPanel/VBox
	var avatar_box = vbox.get_node_or_null("AvatarBox") as HBoxContainer
	if avatar_box == null:
		avatar_box = HBoxContainer.new()
		avatar_box.name = "AvatarBox"
		avatar_box.alignment = BoxContainer.ALIGNMENT_CENTER
		avatar_box.add_theme_constant_override("separation", 16)
		
		var ash_btn = Button.new()
		ash_btn.name = "AshBtn"
		ash_btn.text = " Ash (Boy)"
		var c_tex = load("res://assets/sprites/trainers/ash.png") as Texture2D
		if c_tex:
			ash_btn.icon = c_tex
			ash_btn.expand_icon = true
			ash_btn.custom_minimum_size = Vector2(110, 44)
		ash_btn.pressed.connect(func(): _select_avatar("ash"))
		avatar_box.add_child(ash_btn)
		
		var misty_btn = Button.new()
		misty_btn.name = "MistyBtn"
		misty_btn.text = " Misty (Girl)"
		var s_tex = load("res://assets/sprites/trainers/misty.png") as Texture2D
		if s_tex:
			misty_btn.icon = s_tex
			misty_btn.expand_icon = true
			misty_btn.custom_minimum_size = Vector2(110, 44)
		misty_btn.pressed.connect(func(): _select_avatar("misty"))
		avatar_box.add_child(misty_btn)
		
		# Insert before StartBtn
		vbox.add_child(avatar_box)
		vbox.move_child(avatar_box, vbox.get_child_count() - 3)

func _select_avatar(avatar: String) -> void:
	selected_avatar = avatar
	var ash_btn = $DialogPanel/VBox/AvatarBox/AshBtn as Button
	var misty_btn = $DialogPanel/VBox/AvatarBox/MistyBtn as Button
	if ash_btn and misty_btn:
		var is_boy = (avatar == "ash" or avatar == "boy" or avatar == "calem")
		ash_btn.modulate = Color(1.3, 1.3, 1.3) if is_boy else Color(0.7, 0.7, 0.7)
		misty_btn.modulate = Color(1.3, 1.3, 1.3) if not is_boy else Color(0.7, 0.7, 0.7)

func _on_new_game_pressed() -> void:
	main_buttons_container.visible = false
	dialog_panel.visible = true
	_select_avatar(selected_avatar)
	player_name_input.grab_focus()

func _on_continue_pressed() -> void:
	var success = await SaveLoad.load_game()
	if success:
		get_tree().change_scene_to_file("res://scenes/World.tscn")
	else:
		save_info_label.text = "Failed to load save file!"

func _on_quit_pressed() -> void:
	get_tree().quit()

func _on_start_pressed() -> void:
	var player_name = player_name_input.text.strip_edges()
	if player_name == "":
		player_name = "Trainer"
	
	# Store metadata BEFORE changing scenes
	GameState.set_meta("pending_player_name", player_name)
	GameState.set_meta("pending_trainer_avatar", selected_avatar)
	
	# Transition to starter choice
	get_tree().change_scene_to_file("res://scenes/StarterChoice.tscn")

func _on_back_pressed() -> void:
	dialog_panel.visible = false
	main_buttons_container.visible = true
