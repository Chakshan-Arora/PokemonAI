class_name WorldInteraction
extends Node
## WorldInteraction - Manages world object states (respawn, one-time)

# object_id -> {harvested_at: int, respawn_duration: float, is_one_time: bool, is_depleted: bool}
var _object_states: Dictionary = {}

func _ready() -> void:
	EventBus.world_object_interacted.connect(_on_world_object_interacted)

func _process(delta: float) -> void:
	var now = Time.get_ticks_msec() / 1000.0
	for obj_id in _object_states:
		var state = _object_states[obj_id]
		if state["is_depleted"] and not state["is_one_time"]:
			var elapsed = now - state["harvested_at"]
			if elapsed >= state["respawn_duration"]:
				state["is_depleted"] = false
				EventBus.world_object_respawned.emit(obj_id)

func _on_world_object_interacted(object_id: String, object_type: String) -> void:
	if not _object_states.has(object_id):
		return
	_object_states[object_id]["is_depleted"] = true
	_object_states[object_id]["harvested_at"] = Time.get_ticks_msec() / 1000.0

## Register a world object with the system
func register_object(object_id: String, is_one_time: bool, respawn_duration: float) -> void:
	_object_states[object_id] = {
		"harvested_at": 0.0,
		"respawn_duration": respawn_duration,
		"is_one_time": is_one_time,
		"is_depleted": false
	}

## Check if an object is available for interaction
func is_available(object_id: String) -> bool:
	if not _object_states.has(object_id):
		return true
	return not _object_states[object_id]["is_depleted"]

## Check if a one-time object has been used
func is_permanently_depleted(object_id: String) -> bool:
	if not _object_states.has(object_id):
		# Check player's interaction history
		if GameState.player != null:
			var state = _object_states.get(object_id, {})
			return state.get("is_one_time", false) and state.get("is_depleted", false)
		return false
	var state = _object_states[object_id]
	return state["is_one_time"] and state["is_depleted"]
