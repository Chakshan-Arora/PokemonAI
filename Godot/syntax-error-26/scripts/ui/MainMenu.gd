extends Control
## MainMenu - Main menu screen logic

@onready var new_game_btn: Button = $VBoxContainer/NewGameBtn
@onready var continue_btn: Button = $VBoxContainer/ContinueBtn
@onready var quit_btn: Button = $VBoxContainer/QuitBtn
@onready var dialog_panel: Panel = $DialogPanel
@onready var player_name_input: LineEdit = $DialogPanel/VBox/NameInput
@onready var start_btn: Button = $DialogPanel/VBox/StartBtn
@onready var back_btn: Button = $DialogPanel/VBox/BackBtn
@onready var save_info_label: Label = $VBoxContainer/SaveInfoLabel

func _ready() -> void:
	new_game_btn.pressed.connect(_on_new_game_pressed)
	continue_btn.pressed.connect(_on_continue_pressed)
	quit_btn.pressed.connect(_on_quit_pressed)
	start_btn.pressed.connect(_on_start_pressed)
	back_btn.pressed.connect(_on_back_pressed)
	dialog_panel.visible = false
	
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

func _on_new_game_pressed() -> void:
	dialog_panel.visible = true
	player_name_input.grab_focus()

func _on_continue_pressed() -> void:
	var success = SaveLoad.load_game()
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
	# Transition to starter choice
	get_tree().change_scene_to_file("res://scenes/StarterChoice.tscn")
	# Store the player name for StarterChoice to use
	# We use a metadata on autoload
	GameState.set_meta("pending_player_name", player_name)

func _on_back_pressed() -> void:
	dialog_panel.visible = false
