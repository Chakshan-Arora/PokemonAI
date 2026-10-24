extends CharacterBody3D
## PlayerController - 3D player movement, billboard sprite animation, and interaction

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

var camera_rotation_x: float = -25.0
var camera_rotation_y: float = 0.0
const CAMERA_SENSITIVITY: float = 0.3
const CAMERA_MIN_X: float = -60.0
const CAMERA_MAX_X: float = 10.0

var _step_accumulator: float = 0.0
const STEP_DISTANCE: float = 1.5

var _nearest_interactable: Node3D = null
var _in_tall_grass: bool = false

# Animation state
var _facing: String = "down" # "down", "up", "left", "right"
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
		if avatar == "girl":
			var tex = load("res://assets/sprites/trainers/may_walk.png")
			if tex:
				trainer_sprite.texture = tex
		else:
			var tex = load("res://assets/sprites/trainers/brendan_walk.png")
			if tex:
				trainer_sprite.texture = tex

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

func _input(event: InputEvent) -> void:
	# Camera orbit with mouse drag
	if event is InputEventMouseMotion and Input.is_mouse_button_pressed(MOUSE_BUTTON_RIGHT):
		camera_rotation_y -= event.relative.x * CAMERA_SENSITIVITY
		camera_rotation_x -= event.relative.y * CAMERA_SENSITIVITY
		camera_rotation_x = clamp(camera_rotation_x, CAMERA_MIN_X, CAMERA_MAX_X)
		if is_instance_valid(camera_pivot):
			camera_pivot.rotation_degrees.y = camera_rotation_y
		if is_instance_valid(camera_arm):
			camera_arm.rotation_degrees.x = camera_rotation_x
	
	var is_interact_key = false
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode in [KEY_E, KEY_SPACE, KEY_ENTER, KEY_KP_ENTER] or event.physical_keycode in [KEY_E, KEY_SPACE, KEY_ENTER, KEY_KP_ENTER]:
			is_interact_key = true
	
	if is_interact_key or event.is_action_pressed("interact") or event.is_action_pressed("ui_accept"):
		_try_interact()
	if event.is_action_pressed("open_party"):
		EventBus.open_party_menu.emit()
	if event.is_action_pressed("open_inventory"):
		EventBus.open_inventory_ui.emit()
	if event.is_action_pressed("open_quests"):
		EventBus.open_quest_journal.emit()
	if event.is_action_pressed("pause"):
		EventBus.open_pause_menu.emit()

func _physics_process(delta: float) -> void:
	if GameState.is_in_battle or GameState.is_paused:
		return
	
	# Keep camera following player position smoothly
	if is_instance_valid(camera_pivot):
		camera_pivot.global_position = global_position + Vector3(0, 1.4, 0)
	
	# Gravity
	if not is_on_floor():
		velocity.y -= GRAVITY * delta
	
	# Camera rotate with arrow keys (no mouse drag)
	if Input.is_action_pressed("ui_left"):
		camera_rotation_y += 90.0 * delta
		if is_instance_valid(camera_pivot):
			camera_pivot.rotation_degrees.y = camera_rotation_y
	if Input.is_action_pressed("ui_right"):
		camera_rotation_y -= 90.0 * delta
		if is_instance_valid(camera_pivot):
			camera_pivot.rotation_degrees.y = camera_rotation_y
	
	# Movement direction relative to camera
	var input_dir = Input.get_vector("move_left", "move_right", "move_forward", "move_backward")
	var cam_forward = Vector3.FORWARD
	var cam_right = Vector3.RIGHT
	if is_instance_valid(camera_pivot):
		cam_forward = -camera_pivot.global_transform.basis.z
		cam_right = camera_pivot.global_transform.basis.x
	cam_forward.y = 0
	cam_right.y = 0
	cam_forward = cam_forward.normalized()
	cam_right = cam_right.normalized()
	
	var direction = (cam_forward * -input_dir.y + cam_right * input_dir.x).normalized()
	var speed = RUN_SPEED if Input.is_action_pressed("sprint") else WALK_SPEED
	
	if direction != Vector3.ZERO:
		velocity.x = direction.x * speed
		velocity.z = direction.z * speed
	else:
		velocity.x = move_toward(velocity.x, 0, speed * delta * 10.0)
		velocity.z = move_toward(velocity.z, 0, speed * delta * 10.0)
	
	var is_moving = direction.length_squared() > 0.01
	_update_sprite_animation(delta, input_dir, is_moving, speed > WALK_SPEED)
	
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
	
	# Region detection
	_check_region()
	
	# Update HUD interaction prompt
	_check_nearby_interactables()

func _update_sprite_animation(delta: float, input_dir: Vector2, is_moving: bool, is_sprinting: bool) -> void:
	if not is_instance_valid(trainer_sprite):
		return
	
	if is_moving:
		# Determine dominant direction from input
		if abs(input_dir.x) > abs(input_dir.y):
			_facing = "left" if input_dir.x < 0 else "right"
		else:
			_facing = "up" if input_dir.y < 0 else "down"
		
		_anim_timer += delta * (11.0 if is_sprinting else 7.5)
		var cycle = int(_anim_timer) % 4
		var step_frame = 0
		if cycle == 1:
			step_frame = 1
		elif cycle == 3:
			step_frame = 2
		
		match _facing:
			"down":
				trainer_sprite.frame = 0 if step_frame == 0 else (1 if step_frame == 1 else 2)
				trainer_sprite.flip_h = false
			"up":
				trainer_sprite.frame = 3 if step_frame == 0 else (4 if step_frame == 1 else 5)
				trainer_sprite.flip_h = false
			"left":
				trainer_sprite.frame = 6 if step_frame == 0 else (7 if step_frame == 1 else 8)
				trainer_sprite.flip_h = true
			"right":
				trainer_sprite.frame = 6 if step_frame == 0 else (7 if step_frame == 1 else 8)
				trainer_sprite.flip_h = false
	else:
		_anim_timer = 0.0
		match _facing:
			"down":
				trainer_sprite.frame = 0
				trainer_sprite.flip_h = false
			"up":
				trainer_sprite.frame = 3
				trainer_sprite.flip_h = false
			"left":
				trainer_sprite.frame = 6
				trainer_sprite.flip_h = true
			"right":
				trainer_sprite.frame = 6
				trainer_sprite.flip_h = false

func _check_region() -> void:
	var region_id = RegionData.get_region_at_position(global_position.x, global_position.z)
	if region_id != "" and region_id != GameState.current_region_id:
		GameState.change_region(region_id)
	
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

func _on_encounter_triggered(wild_pokemon: PokemonInstance) -> void:
	if GameState.is_in_battle:
		return
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
