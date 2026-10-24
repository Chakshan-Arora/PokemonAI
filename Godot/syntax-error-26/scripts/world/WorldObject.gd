extends StaticBody3D
## WorldObject - Interactable 3D world entity (signs, resource nodes, caches, landmarks, NPCs)

@export var object_id: String = "object_01"
@export var object_name: String = "World Object"
@export_enum("resource_node", "treasure", "sign", "landmark", "npc") var object_type: String = "sign"
@export_multiline var interaction_text: String = "You see an interesting object."
@export var rewards: Dictionary = {}  # item_id -> quantity
@export var respawn_duration: float = 0.0  # seconds, 0 = one-time or sign
@export var region_id: String = "starting_meadow"

@onready var label_3d: Label3D = $Label3D
@onready var sprite_3d: Sprite3D = $Sprite3D
@onready var shadow_mesh: MeshInstance3D = $Shadow

var _respawn_timer: float = 0.0
var _is_harvested: bool = false

func _ready() -> void:
	add_to_group("interactable")
	if is_instance_valid(label_3d):
		label_3d.text = object_name
	
	_setup_visuals()

func _process(delta: float) -> void:
	if _is_harvested and respawn_duration > 0.0:
		_respawn_timer -= delta
		if _respawn_timer <= 0.0:
			_is_harvested = false
			visible = true
			EventBus.world_object_respawned.emit(object_id)

func _setup_visuals() -> void:
	if not is_instance_valid(sprite_3d):
		return
	
	if object_id == "ancient_shrine" or object_type == "landmark":
		var tex = load("res://assets/sprites/world/rock.png")
		if tex:
			sprite_3d.texture = tex
			sprite_3d.pixel_size = 0.075
			sprite_3d.position.y = 1.0
	elif object_type == "resource_node" or "berry" in object_id:
		var tex = load("res://assets/sprites/world/bush.png")
		if tex:
			sprite_3d.texture = tex
			sprite_3d.pixel_size = 0.05
			sprite_3d.position.y = 0.7
	elif object_type == "sign" or "sign" in object_id:
		var tex = load("res://assets/sprites/world/sign.png")
		if tex:
			sprite_3d.texture = tex
			sprite_3d.pixel_size = 0.045
			sprite_3d.position.y = 0.65
	elif object_id == "npc_prof_oak" or "oak" in object_id.to_lower():
		var tex = load("res://assets/sprites/trainers/professor_oak.png")
		if tex:
			sprite_3d.texture = tex
			sprite_3d.pixel_size = 0.04
			sprite_3d.position.y = 1.12
	elif object_type == "npc":
		var tex = load("res://assets/sprites/trainers/ash.png")
		if tex:
			sprite_3d.texture = tex
			sprite_3d.pixel_size = 0.045
			sprite_3d.position.y = 0.75
	elif object_type == "treasure" or "cache" in object_id:
		var tex = load("res://assets/sprites/items/poke_ball.png")
		if tex:
			sprite_3d.texture = tex
			sprite_3d.pixel_size = 0.035
			sprite_3d.position.y = 0.5

func get_interaction_text() -> String:
	if _is_harvested:
		return "Depleted"
	match object_type:
		"sign": return "Read " + object_name
		"npc": return "Talk to " + object_name
		"resource_node": return "Gather from " + object_name
		"treasure": return "Open " + object_name
		"landmark": return "Examine " + object_name
		_: return "Interact with " + object_name

func on_interact(_player_node: Node3D) -> void:
	if _is_harvested:
		EventBus.show_message.emit("There's nothing here right now.")
		return
	
	# Show interaction message
	EventBus.show_message.emit(interaction_text)
	
	# Handle campfire rest: fully heal team!
	if object_id == "campfire_rest":
		if GameState.player:
			for p in GameState.player.team:
				p.heal_to_full()
				p.clear_all_statuses()
			EventBus.show_message.emit("All Pokémon in your party have been fully healed!")
	
	# Give rewards if any
	if not rewards.is_empty():
		for item_id in rewards:
			var qty = rewards[item_id]
			if GameState.player:
				GameState.player.add_item(item_id, qty)
			EventBus.item_obtained.emit(item_id, qty)
			EventBus.inventory_updated.emit(item_id, GameState.player.get_item_count(item_id) if GameState.player else qty)
		
		if respawn_duration > 0.0:
			_is_harvested = true
			_respawn_timer = respawn_duration
			visible = false
		else:
			_is_harvested = true
			if object_type == "treasure":
				queue_free()
	
	# Trigger quest step updates
	EventBus.world_object_interacted.emit(object_id, object_type)
