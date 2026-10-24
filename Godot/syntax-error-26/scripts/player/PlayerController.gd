extends CharacterBody3D
## PlayerController - 3D player movement and interaction

const PokemonInstance = preload("res://scripts/models/PokemonInstance.gd")
const RegionData = preload("res://scripts/data/RegionData.gd")

const WALK_SPEED: float = 5.0
const RUN_SPEED: float = 9.0
const JUMP_VELOCITY: float = 4.5
const GRAVITY: float = 9.8

@onready var camera_pivot: Node3D = $CameraPivot
@onready var camera_arm: SpringArm3D = $CameraPivot/SpringArm3D
@onready var camera: Camera3D = $CameraPivot/SpringArm3D/Camera3D
@onready var interaction_area: Area3D = $InteractionArea
@onready var mesh_instance: MeshInstance3D = $MeshInstance3D

var camera_rotation_x: float = -25.0
var camera_rotation_y: float = 0.0
const CAMERA_SENSITIVITY: float = 0.3
const CAMERA_MIN_X: float = -60.0
const CAMERA_MAX_X: float = 10.0

var _step_accumulator: float = 0.0
const STEP_DISTANCE: float = 1.5

var _nearest_interactable: Node3D = null
var _in_tall_grass: bool = false

# Encounter system reference
var encounter_system: Node = null

signal player_moved(position: Vector3)
signal interaction_triggered(object_node: Node3D)

func _ready() -> void:
	add_to_group("player")
	# Create encounter system
	encounter_system = load("res://scripts/systems/EncounterSystem.gd").new()
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
		camera_pivot.rotation_degrees.y = camera_rotation_y
		camera_arm.rotation_degrees.x = camera_rotation_x
	
	if event.is_action_pressed("interact"):
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
	
	# Gravity
	if not is_on_floor():
		velocity.y -= GRAVITY * delta
	
	# Camera rotate with arrow keys (no mouse drag)
	if Input.is_action_pressed("ui_left"):
		camera_rotation_y += 90.0 * delta
		camera_pivot.rotation_degrees.y = camera_rotation_y
	if Input.is_action_pressed("ui_right"):
		camera_rotation_y -= 90.0 * delta
		camera_pivot.rotation_degrees.y = camera_rotation_y
	
	# Movement direction relative to camera
	var input_dir = Input.get_vector("move_left", "move_right", "move_forward", "move_backward")
	var cam_forward = -camera_pivot.global_transform.basis.z
	var cam_right = camera_pivot.global_transform.basis.x
	cam_forward.y = 0
	cam_right.y = 0
	cam_forward = cam_forward.normalized()
	cam_right = cam_right.normalized()
	
	var direction = (cam_forward * -input_dir.y + cam_right * input_dir.x).normalized()
	
	var speed = RUN_SPEED if Input.is_action_pressed("sprint") else WALK_SPEED
	
	if direction != Vector3.ZERO:
		velocity.x = direction.x * speed
		velocity.z = direction.z * speed
		# Face movement direction
		var target_angle = atan2(direction.x, direction.z)
		rotation.y = lerp_angle(rotation.y, target_angle, delta * 8.0)
	else:
		velocity.x = move_toward(velocity.x, 0, speed * delta * 10.0)
		velocity.z = move_toward(velocity.z, 0, speed * delta * 10.0)
	
	var prev_pos = global_position
	move_and_slide()
	
	# Step tracking for encounters
	if direction != Vector3.ZERO and is_on_floor():
		var dist = global_position.distance_to(prev_pos)
		_step_accumulator += dist
		if _step_accumulator >= STEP_DISTANCE:
			_step_accumulator = 0.0
			GameState.player.total_steps += 1
			encounter_system.on_player_step(GameState.current_region_id, _in_tall_grass)
		player_moved.emit(global_position)
	
	# Region detection
	_check_region()
	
	# Update HUD interaction prompt
	_check_nearby_interactables()

func _check_region() -> void:
	var region_id = RegionData.get_region_at_position(global_position.x, global_position.z)
	if region_id != "" and region_id != GameState.current_region_id:
		GameState.change_region(region_id)
	
	# Tall grass detection: if region has tall grass, consider player in tall grass
	var region_data = RegionData.get_region(GameState.current_region_id)
	_in_tall_grass = region_data.get("has_tall_grass", false)

func _check_nearby_interactables() -> void:
	_nearest_interactable = null
	var overlapping = interaction_area.get_overlapping_bodies()
	overlapping.append_array(interaction_area.get_overlapping_areas())
	
	var nearest_dist = INF
	for obj in overlapping:
		if obj.has_method("get_interaction_text") or obj.is_in_group("interactable"):
			var dist = global_position.distance_to(obj.global_position)
			if dist < nearest_dist:
				nearest_dist = dist
				_nearest_interactable = obj
	
	var hud = get_tree().get_first_node_in_group("hud")
	if hud and hud.has_method("set_interaction_prompt"):
		if _nearest_interactable != null:
			var txt = "Interact"
			if _nearest_interactable.has_method("get_interaction_text"):
				txt = _nearest_interactable.get_interaction_text()
			hud.set_interaction_prompt(true, txt)
		else:
			hud.set_interaction_prompt(false)

func _try_interact() -> void:
	if _nearest_interactable == null:
		return
	if _nearest_interactable.has_method("on_interact"):
		_nearest_interactable.on_interact(self)
		interaction_triggered.emit(_nearest_interactable)

func _on_encounter_triggered(wild_pokemon: PokemonInstance) -> void:
	if GameState.is_in_battle:
		return
	# Store wild pokemon info and transition to battle
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
	if party_menu:
		party_menu.show_menu()

func _on_open_inventory_ui() -> void:
	var inv_ui = get_tree().get_first_node_in_group("inventory_ui")
	if inv_ui:
		inv_ui.show_menu()

func _on_open_quest_journal() -> void:
	var quest_ui = get_tree().get_first_node_in_group("quest_journal")
	if quest_ui:
		quest_ui.show_menu()
