extends StaticBody3D
## TrainerNPC - Overworld trainer NPC capable of initiating trainer battles

const PokemonInstance = preload("res://scripts/models/PokemonInstance.gd")

@export var trainer_id: String = "koji"
@export var trainer_name: String = "Field Trainer Koji"
@export_multiline var dialogue_intro: String = "Hey there! Let's see how strong your Pokemon are!"
@export_multiline var dialogue_defeat: String = "Wow, your team is remarkably well trained!"
@export var team_species: Array[String] = ["Geodude", "Machop"]
@export var team_levels: Array[int] = [4, 5]

@onready var label_3d: Label3D = $Label3D
@onready var sprite_3d: Sprite3D = $Sprite3D

var _is_defeated: bool = false

func _ready() -> void:
	add_to_group("interactable")
	if is_instance_valid(label_3d):
		label_3d.text = trainer_name
	
	if is_instance_valid(sprite_3d):
		var path = "res://assets/sprites/trainers/%s.png" % trainer_id.to_lower()
		var tex = load(path)
		if tex:
			sprite_3d.texture = tex

func get_interaction_text() -> String:
	var def = _is_defeated
	if GameState.player and GameState.player.is_trainer_defeated(trainer_id):
		def = true
	return "Talk to " + trainer_name if def else "Battle " + trainer_name

func on_interact(_player_node: Node3D) -> void:
	if _is_defeated or (GameState.player and GameState.player.is_trainer_defeated(trainer_id)):
		EventBus.show_message.emit(dialogue_defeat)
		return
	
	if is_instance_valid(_player_node) and GameState.player:
		GameState.player.player_position = _player_node.global_position
	
	EventBus.show_message.emit(dialogue_intro)
	
	# Create opponent Pokemon
	var opp_species = team_species[0] if not team_species.is_empty() else "Geodude"
	var opp_lvl = team_levels[0] if not team_levels.is_empty() else 4
	var opp_p = PokemonInstance.create(opp_species, opp_lvl)
	
	GameState.set_meta("trainer_name", trainer_name)
	GameState.set_meta("trainer_id", trainer_id)
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	
	_is_defeated = true
	
	EventBus.battle_started.emit(
		GameState.get_active_pokemon().to_dict() if GameState.get_active_pokemon() else {},
		opp_p.to_dict(),
		true
	)
	
	if has_node("/root/BattleTransition"):
		var bt = get_node("/root/BattleTransition")
		bt.start_trainer_encounter(opp_p.to_dict(), trainer_name)
	else:
		GameState.set_meta("wild_pokemon_for_battle", opp_p.to_dict())
		GameState.set_meta("is_trainer_battle", true)
		GameState.enter_battle()
		get_tree().change_scene_to_file("res://scenes/Battle.tscn")
