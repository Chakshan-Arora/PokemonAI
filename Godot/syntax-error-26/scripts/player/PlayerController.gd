extends CharacterBody3D
## PlayerController - 3D player movement, billboard sprite animation, smooth mouse look around & interaction

const PokemonInstance = preload("res://scripts/models/PokemonInstance.gd")
const RegionData = preload("res://scripts/data/RegionData.gd")

const WALK_SPEED: float = 5.0
const RUN_SPEED: float = 8.5
const JUMP_VELOCITY: float = 4.5
const GRAVITY: float = 9.8

@onready var camera_pivot: Node3D = $CameraPivot
@onready var camera_arm: SpringArm3D = $CameraPivot/SpringArm3D
@onready var camera: Camera3D = $CameraPivot/SpringArm3D/Camera3D
@onready var interaction_area: Area3D = $InteractionArea
@onready var trainer_sprite: Sprite3D = $TrainerSprite

var camera_rotation_x: float = -20.0
var camera_rotation_y: float = 0.0
const CAMERA_SENSITIVITY: float = 0.25
const CAMERA_MIN_X: float = -75.0
const CAMERA_MAX_X: float = 45.0
var is_mouse_captured: bool = false

var _step_accumulator: float = 0.0
const STEP_DISTANCE: float = 1.5

var _nearest_interactable: Node3D = null
var _in_tall_grass: bool = false

# Animation state
var _facing: String = "up" # "up" = back facing camera/user
var _anim_timer: float = 0.0

# Encounter system reference
var encounter_system: Node = null

signal player_moved(position: Vector3)
signal interaction_triggered(object_node: Node3D)

func _ready() -> void:
	add_to_group("player")
	
	# Detach camera pivot from player rotation to eliminate feedback loop
	if is_instance_valid(camera_pivot):
		camera_pivot.top_level = true
		camera_pivot.global_position = global_position + Vector3(0, 1.4, 0)
		camera_pivot.rotation_degrees.y = camera_rotation_y
		if is_instance_valid(camera_arm):
			camera_arm.rotation_degrees.x = camera_rotation_x
	
	# Choose sprite texture based on chosen avatar
	if is_instance_valid(trainer_sprite):
		var avatar = "boy"
		if GameState.has_meta("player_avatar"):
			avatar = str(GameState.get_meta("player_avatar"))
		elif GameState.player and GameState.player.trainer_avatar != "":
			var a = GameState.player.trainer_avatar.to_lower()
			avatar = "girl" if (a == "girl" or a == "serena") else "boy"
			
		var is_girl = (avatar in ["girl", "misty", "serena", "may"])
		if is_girl:
			var tex = load("res://assets/sprites/trainers/misty_walk.png")
			if tex:
				trainer_sprite.texture = tex
				trainer_sprite.hframes = 9
				trainer_sprite.pixel_size = 0.04
				trainer_sprite.position.y = 0.96
		else:
			var tex = load("res://assets/sprites/trainers/ash_walk.png")
			if tex:
				trainer_sprite.texture = tex
				trainer_sprite.hframes = 9
				trainer_sprite.pixel_size = 0.04
				trainer_sprite.position.y = 0.96
		trainer_sprite.frame = 3

	# Create encounter system
	var enc_class = load("res://scripts/systems/EncounterSystem.gd")
	if enc_class:
		encounter_system = enc_class.new()
		add_child(encounter_system)
		encounter_system.encounter_triggered.connect(_on_encounter_triggered)
	
	# Connect EventBus signals for menu opening
	EventBus.open_party_menu.connect(_on_open_party_menu)
	EventBus.open_inventory_ui.connect(_on_open_inventory_ui)
	EventBus.open_quest_journal.connect(_on_open_quest_journal)

func _is_typing() -> bool:
	if GameState.has_meta("typing_active") and GameState.get_meta("typing_active"):
		return true
	var focus_owner = get_viewport().gui_get_focus_owner()
	if focus_owner is LineEdit or focus_owner is TextEdit:
		return true
	return false

func _is_in_menu() -> bool:
	return GameState.is_any_menu_open() or _is_typing()

func _input(event: InputEvent) -> void:
	# If player is in any menu, battle, or typing, ALWAYS release mouse and ignore world hotkeys
	if _is_in_menu():
		_release_mouse()
		return

	# Mouse wheel zoom in world
	if event is InputEventMouseButton and is_instance_valid(camera_arm):
		if event.button_index == MOUSE_BUTTON_WHEEL_UP:
			camera_arm.spring_length = max(2.0, camera_arm.spring_length - 0.5)
		elif event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			camera_arm.spring_length = min(12.0, camera_arm.spring_length + 0.5)

	# Camera look with mouse motion: works when captured OR when drag-clicking with Left or Right button
	if event is InputEventMouseMotion:
		var should_rotate = (Input.mouse_mode == Input.MOUSE_MODE_CAPTURED) or Input.is_mouse_button_pressed(MOUSE_BUTTON_RIGHT) or Input.is_mouse_button_pressed(MOUSE_BUTTON_LEFT)
		if should_rotate and not _is_in_menu():
			camera_rotation_y -= event.relative.x * CAMERA_SENSITIVITY
			camera_rotation_x -= event.relative.y * CAMERA_SENSITIVITY
			camera_rotation_x = clamp(camera_rotation_x, CAMERA_MIN_X, CAMERA_MAX_X)
			if is_instance_valid(camera_pivot):
				camera_pivot.rotation_degrees.y = camera_rotation_y
			if is_instance_valid(camera_arm):
				camera_arm.rotation_degrees.x = camera_rotation_x

	# Release mouse capture on Escape, Tab, or C (companion chat)
	if event is InputEventKey and event.pressed:
		if event.keycode == KEY_ESCAPE or event.keycode == KEY_TAB or event.keycode == KEY_C:
			_release_mouse()

	var is_interact_key = false
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode in [KEY_E, KEY_SPACE, KEY_ENTER, KEY_KP_ENTER] or event.physical_keycode in [KEY_E, KEY_SPACE, KEY_ENTER, KEY_KP_ENTER]:
			is_interact_key = true
	
	if is_interact_key or event.is_action_pressed("interact") or event.is_action_pressed("ui_accept"):
		_try_interact()
	if event.is_action_pressed("open_party"):
		_release_mouse()
		EventBus.open_party_menu.emit()
	if event.is_action_pressed("open_inventory"):
		_release_mouse()
		EventBus.open_inventory_ui.emit()
	if event.is_action_pressed("open_quests"):
		_release_mouse()
		EventBus.open_quest_journal.emit()
	if event.is_action_pressed("pause"):
		_release_mouse()
		EventBus.open_pause_menu.emit()

func _unhandled_input(event: InputEvent) -> void:
	if _is_in_menu():
		_release_mouse()
		return

	# Only acquire mouse capture when clicking directly into 3D world (outside of menus/UI/battles)
	if event is InputEventMouseButton and event.pressed:
		if not _is_in_menu():
			if event.button_index in [MOUSE_BUTTON_LEFT, MOUSE_BUTTON_RIGHT, MOUSE_BUTTON_MIDDLE]:
				if Input.mouse_mode != Input.MOUSE_MODE_CAPTURED:
					Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
					is_mouse_captured = true

func _release_mouse() -> void:
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	is_mouse_captured = false

func _physics_process(delta: float) -> void:
	if _is_in_menu():
		_release_mouse()
		return
	
	# If player is actively typing, stop movement and do not process camera arrows or WASD
	if _is_typing():
		_release_mouse()
		velocity.x = move_toward(velocity.x, 0, WALK_SPEED * delta * 10.0)
		velocity.z = move_toward(velocity.z, 0, WALK_SPEED * delta * 10.0)
		move_and_slide()
		return
	
	# Keep camera following player position smoothly
	if is_instance_valid(camera_pivot):
		camera_pivot.global_position = global_position + Vector3(0, 1.4, 0)
	
	# Gravity
	if not is_on_floor():
		velocity.y -= GRAVITY * delta
	
	# Keyboard camera look around (Arrow keys)
	var cam_changed = false
	if Input.is_key_pressed(KEY_LEFT):
		camera_rotation_y += 100.0 * delta
		cam_changed = true
	if Input.is_key_pressed(KEY_RIGHT):
		camera_rotation_y -= 100.0 * delta
		cam_changed = true
	if Input.is_key_pressed(KEY_UP):
		camera_rotation_x += 70.0 * delta
		cam_changed = true
	if Input.is_key_pressed(KEY_DOWN):
		camera_rotation_x -= 70.0 * delta
		cam_changed = true
	
	if cam_changed:
		camera_rotation_x = clamp(camera_rotation_x, CAMERA_MIN_X, CAMERA_MAX_X)
		if is_instance_valid(camera_pivot):
			camera_pivot.rotation_degrees.y = camera_rotation_y
		if is_instance_valid(camera_arm):
			camera_arm.rotation_degrees.x = camera_rotation_x
	
	# Movement direction relative to camera
	var input_x = 0.0
	var input_z = 0.0
	if Input.is_key_pressed(KEY_W): input_z -= 1.0
	if Input.is_key_pressed(KEY_S): input_z += 1.0
	if Input.is_key_pressed(KEY_A): input_x -= 1.0
	if Input.is_key_pressed(KEY_D): input_x += 1.0
	
	# Fallback to action events if WASD not held directly
	if input_x == 0.0 and input_z == 0.0:
		var move_v = Input.get_vector("move_left", "move_right", "move_forward", "move_backward")
		input_x = move_v.x
		input_z = move_v.y

	var cam_forward = Vector3.FORWARD
	var cam_right = Vector3.RIGHT
	if is_instance_valid(camera_pivot):
		cam_forward = -camera_pivot.global_transform.basis.z
		cam_right = camera_pivot.global_transform.basis.x
	cam_forward.y = 0
	cam_right.y = 0
	cam_forward = cam_forward.normalized()
	cam_right = cam_right.normalized()
	
	var direction = (cam_forward * -input_z + cam_right * input_x).normalized()
	var speed = RUN_SPEED if Input.is_action_pressed("sprint") else WALK_SPEED
	
	if direction != Vector3.ZERO:
		velocity.x = direction.x * speed
		velocity.z = direction.z * speed
	else:
		velocity.x = move_toward(velocity.x, 0, speed * delta * 10.0)
		velocity.z = move_toward(velocity.z, 0, speed * delta * 10.0)
	
	var is_moving = direction.length_squared() > 0.01
	_update_sprite_animation(delta, Vector2(input_x, input_z), is_moving, speed > WALK_SPEED)
	
	var prev_pos = global_position
	move_and_slide()
	
	# Step tracking for encounters
	if is_moving and is_on_floor():
		var dist = global_position.distance_to(prev_pos)
		_step_accumulator += dist
		if _step_accumulator >= STEP_DISTANCE:
			_step_accumulator = 0.0
			GameState.player.total_steps += 1
			if is_instance_valid(encounter_system):
				encounter_system.on_player_step(GameState.current_region_id, _in_tall_grass)
		player_moved.emit(global_position)
		EventBus.player_moved.emit(global_position)
	
	# Region detection
	_check_region()
	
	# Update HUD interaction prompt
	_check_nearby_interactables()

func _update_sprite_animation(delta: float, _input_dir: Vector2, is_moving: bool, is_sprinting: bool) -> void:
	if not is_instance_valid(trainer_sprite):
		return
	
	if is_moving:
		_anim_timer += delta * (11.0 if is_sprinting else 7.5)
		var cycle = int(_anim_timer) % 4
		var step_frame = 3
		if cycle == 1:
			step_frame = 4 # step left
		elif cycle == 3:
			step_frame = 5 # step right
		
		# Always maintain the player back visible to the user
		trainer_sprite.frame = step_frame
		trainer_sprite.flip_h = false
	else:
		_anim_timer = 0.0
		# Back idle frame (facing forward into the world)
		trainer_sprite.frame = 3
		trainer_sprite.flip_h = false

func _check_region() -> void:
	var region_id = RegionData.get_region_at_position(global_position.x, global_position.z)
	if region_id != "" and region_id != GameState.current_region_id:
		var old_region_id = GameState.current_region_id
		GameState.change_region(region_id)
		EventBus.player_exited_region.emit(old_region_id)
		var region_data = RegionData.get_region(region_id)
		EventBus.player_entered_region.emit(region_id, region_data.get("name", region_id))
	
	# Tall grass detection
	var region_data = RegionData.get_region(GameState.current_region_id)
	_in_tall_grass = region_data.get("has_tall_grass", false)

func _check_nearby_interactables() -> void:
	_nearest_interactable = null
	var max_reach: float = 4.8
	var nearest_dist: float = max_reach
	
	# Check all nodes in interactable group by 3D distance
	var interactables = get_tree().get_nodes_in_group("interactable")
	for obj in interactables:
		if is_instance_valid(obj) and obj is Node3D and obj.visible:
			var dist = global_position.distance_to(obj.global_position)
			if dist < nearest_dist:
				nearest_dist = dist
				_nearest_interactable = obj
	
	# Also fallback to overlapping areas if needed
	if _nearest_interactable == null and is_instance_valid(interaction_area):
		var overlapping = interaction_area.get_overlapping_bodies()
		overlapping.append_array(interaction_area.get_overlapping_areas())
		for obj in overlapping:
			var candidate = obj
			if not (candidate.has_method("get_interaction_text") or candidate.is_in_group("interactable")):
				if candidate.get_parent() and (candidate.get_parent().has_method("get_interaction_text") or candidate.get_parent().is_in_group("interactable")):
					candidate = candidate.get_parent()
			if is_instance_valid(candidate) and (candidate.has_method("get_interaction_text") or candidate.is_in_group("interactable")):
				var dist = global_position.distance_to(candidate.global_position)
				if dist < nearest_dist:
					nearest_dist = dist
					_nearest_interactable = candidate
	
	var hud = get_tree().get_first_node_in_group("hud")
	if is_instance_valid(hud) and hud.has_method("set_interaction_prompt"):
		if is_instance_valid(_nearest_interactable):
			var txt = "Interact"
			if _nearest_interactable.has_method("get_interaction_text"):
				txt = _nearest_interactable.get_interaction_text()
			hud.set_interaction_prompt(true, txt)
		else:
			hud.set_interaction_prompt(false)

func _try_interact() -> void:
	if not is_instance_valid(_nearest_interactable):
		_check_nearby_interactables()
	if not is_instance_valid(_nearest_interactable):
		return
	if _nearest_interactable.has_method("on_interact"):
		_nearest_interactable.on_interact(self)
		interaction_triggered.emit(_nearest_interactable)
		var obj_id = _nearest_interactable.get("object_id") if "object_id" in _nearest_interactable else _nearest_interactable.name
		EventBus.interaction_triggered.emit(obj_id)
		var obj_type = _nearest_interactable.get("object_type") if "object_type" in _nearest_interactable else "world_object"
		EventBus.world_object_interacted.emit(obj_id, obj_type)

func _on_encounter_triggered(wild_pokemon: PokemonInstance) -> void:
	if GameState.is_in_battle:
		return
	_release_mouse()
	GameState.set_meta("wild_pokemon_for_battle", wild_pokemon.to_dict())
	GameState.enter_battle()
	EventBus.battle_started.emit(
		GameState.get_active_pokemon().to_dict() if GameState.get_active_pokemon() else {},
		wild_pokemon.to_dict(),
		false
	)
	get_tree().change_scene_to_file("res://scenes/Battle.tscn")

func _on_open_party_menu() -> void:
	var party_menu = get_tree().get_first_node_in_group("party_menu")
	if is_instance_valid(party_menu):
		party_menu.show_menu()

func _on_open_inventory_ui() -> void:
	var inv_ui = get_tree().get_first_node_in_group("inventory_ui")
	if is_instance_valid(inv_ui):
		inv_ui.show_menu()

func _on_open_quest_journal() -> void:
	var quest_ui = get_tree().get_first_node_in_group("quest_journal")
	if is_instance_valid(quest_ui):
		quest_ui.show_menu()
