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
@onready var mesh_instance: MeshInstance3D = $MeshInstance3D

var _respawn_timer: float = 0.0
var _is_harvested: bool = false

func _ready() -> void:
	add_to_group("interactable")
	if label_3d:
		label_3d.text = object_name
	
	# Apply distinct color material based on type
	if mesh_instance:
		_apply_type_material()

func _process(delta: float) -> void:
	if _is_harvested and respawn_duration > 0.0:
		_respawn_timer -= delta
		if _respawn_timer <= 0.0:
			_is_harvested = false
			visible = true
			EventBus.world_object_respawned.emit(object_id)

func _apply_type_material() -> void:
	var mat = StandardMaterial3D.new()
	match object_type:
		"resource_node":
			mat.albedo_color = Color(0.2, 0.8, 0.3)  # Berry green
		"treasure":
			mat.albedo_color = Color(1.0, 0.84, 0.0) # Gold
		"sign":
			mat.albedo_color = Color(0.6, 0.4, 0.2)  # Wood brown
		"landmark":
			mat.albedo_color = Color(0.7, 0.3, 0.9)  # Shrine purple
		"npc":
			mat.albedo_color = Color(0.2, 0.7, 0.9)  # Cyan
		_:
			mat.albedo_color = Color(0.8, 0.8, 0.8)
	mesh_instance.material_override = mat

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
	EventBus.show_message.emit(interaction_text, 4.0)
	
	# Handle campfire rest healing
	if object_id == "campfire_rest" and GameState.player != null:
		for p in GameState.player.team:
			p.heal_to_full()
			p.clear_all_statuses()
		EventBus.hud_update_requested.emit()
	
	# Grant rewards if any
	if not rewards.is_empty() and GameState.player != null:
		for item_id in rewards:
			var qty = int(rewards[item_id])
			GameState.player.add_item(item_id, qty)
			EventBus.item_obtained.emit(item_id, qty)
	
	# Handle landmark discovery
	if object_type == "landmark" and GameState.player != null:
		var is_new = GameState.player.discover_landmark(object_id)
		if is_new:
			EventBus.landmark_discovered.emit(object_id, object_name)
	
	# Record interaction in player model
	if GameState.player != null:
		GameState.player.record_object_interaction(object_id)
	
	EventBus.world_object_interacted.emit(object_id, object_type)
	
	# Handle depletion / respawn
	if object_type == "treasure":
		_is_harvested = true
		visible = false
	elif object_type == "resource_node" and respawn_duration > 0.0:
		_is_harvested = true
		_respawn_timer = respawn_duration
		visible = false

