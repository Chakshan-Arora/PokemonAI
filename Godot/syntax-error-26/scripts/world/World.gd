extends Node3D
## World - Root scene for the 3D explorable Pokemon world

const RegionData = preload("res://scripts/data/RegionData.gd")

@onready var player_node: CharacterBody3D = $Player
@onready var hud: Control = $UILayer/HUD

func _ready() -> void:
	# Ensure GameState has a player model if testing World scene directly
	if GameState.player == null:
		GameState.new_game("Trainer", "Bulbasaur")
	
	GameState.exit_battle()
	GameState.resume_game()
	
	# Update region on start
	if player_node:
		var reg = RegionData.get_region_at_position(player_node.global_position.x, player_node.global_position.z)
		if reg != "":
			GameState.change_region(reg)
	
	EventBus.hud_update_requested.emit()

