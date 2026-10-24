extends CharacterBody3D
## WildPokemonAI - Overworld wild Pokemon entity with autonomous behavior state machine

const PokemonInstance = preload("res://scripts/models/PokemonInstance.gd")
const PokemonData = preload("res://scripts/data/PokemonData.gd")

@export var species_name: String = "Pikachu"
@export var level: int = 3
@export var habitat_id: String = "meadow"

@onready var sprite_3d: Sprite3D = $Sprite3D
@onready var label_3d: Label3D = $Label3D
@onready var collision_shape: CollisionShape3D = $CollisionShape3D
@onready var shadow_mesh: MeshInstance3D = $Shadow

enum State { IDLE, WANDER, FLEE }
var current_state: State = State.IDLE

var _wander_target: Vector3 = Vector3.ZERO
var _timer: float = 0.0
var _origin_position: Vector3 = Vector3.ZERO
var _bob_timer: float = 0.0
const WANDER_RADIUS: float = 12.0
const MOVE_SPEED: float = 2.5
const ENCOUNTER_DISTANCE: float = 2.2

func _ready() -> void:
	add_to_group("wild_pokemon")
	add_to_group("interactable")
	_origin_position = global_position
	_wander_target = global_position
	
	if is_instance_valid(label_3d):
		label_3d.text = "%s Lv.%d" % [species_name, level]
	
	# Apply species sprite
	if is_instance_valid(sprite_3d):
		var sprite_tex = PokemonData.get_front_sprite_texture(species_name)
		if sprite_tex:
			sprite_3d.texture = sprite_tex
			sprite_3d.billboard = BaseMaterial3D.BILLBOARD_FIXED_Y
			sprite_3d.texture_filter = BaseMaterial3D.TEXTURE_FILTER_NEAREST

func _physics_process(delta: float) -> void:
	if GameState.is_in_battle or GameState.is_paused:
		return
	
	# Gravity
	if not is_on_floor():
		velocity.y -= 9.8 * delta
	
	# Check distance to player
	var player = get_tree().get_first_node_in_group("player")
	if is_instance_valid(player):
		var dist = global_position.distance_to(player.global_position)
		if dist <= ENCOUNTER_DISTANCE:
			_trigger_battle()
			return
		
		# Skittish types flee if player is close
		var s_data = PokemonData.get_species(species_name)
		var is_skittish = "Normal" in s_data.get("types", []) or "Bug" in s_data.get("types", [])
		if is_skittish and dist < 6.0:
			current_state = State.FLEE
	
	_timer -= delta
	match current_state:
		State.IDLE:
			velocity.x = move_toward(velocity.x, 0, delta * 5.0)
			velocity.z = move_toward(velocity.z, 0, delta * 5.0)
			if _timer <= 0.0:
				_pick_new_wander_target()
				current_state = State.WANDER
				_timer = randf_range(3.0, 6.0)
		
		State.WANDER:
			var dir = (_wander_target - global_position)
			dir.y = 0
			if dir.length() > 0.5:
				dir = dir.normalized()
				velocity.x = dir.x * MOVE_SPEED
				velocity.z = dir.z * MOVE_SPEED
				if is_instance_valid(sprite_3d):
					sprite_3d.flip_h = dir.x < 0
			else:
				current_state = State.IDLE
				_timer = randf_range(2.0, 5.0)
		
		State.FLEE:
			if is_instance_valid(player):
				var away_dir = (global_position - player.global_position)
				away_dir.y = 0
				away_dir = away_dir.normalized()
				velocity.x = away_dir.x * (MOVE_SPEED * 1.5)
				velocity.z = away_dir.z * (MOVE_SPEED * 1.5)
				if is_instance_valid(sprite_3d):
					sprite_3d.flip_h = away_dir.x < 0
			if _timer <= 0.0:
				current_state = State.IDLE
				_timer = randf_range(2.0, 4.0)
	
	# Subtle idle/walking hop animation
	if velocity.length_squared() > 0.1:
		_bob_timer += delta * 8.0
		if is_instance_valid(sprite_3d):
			sprite_3d.position.y = 0.55 + sin(_bob_timer) * 0.08
	else:
		if is_instance_valid(sprite_3d):
			sprite_3d.position.y = 0.55
	
	move_and_slide()

func _pick_new_wander_target() -> void:
	var angle = randf_range(0, TAU)
	var r = randf_range(2.0, WANDER_RADIUS)
	_wander_target = _origin_position + Vector3(cos(angle) * r, 0, sin(angle) * r)

func get_interaction_text() -> String:
	return "Battle %s" % species_name

func on_interact(_player: Node) -> void:
	_trigger_battle()

func _trigger_battle() -> void:
	if GameState.is_in_battle:
		return
	var player = get_tree().get_first_node_in_group("player")
	if is_instance_valid(player) and GameState.player:
		GameState.player.player_position = player.global_position
	
	var wild_p = PokemonInstance.create(species_name, level)
	GameState.set_meta("wild_pokemon_for_battle", wild_p.to_dict())
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	GameState.enter_battle()
	
	EventBus.battle_started.emit(
		GameState.get_active_pokemon().to_dict() if GameState.get_active_pokemon() else {},
		wild_p.to_dict(),
		false
	)
	
	queue_free()
	get_tree().change_scene_to_file("res://scenes/Battle.tscn")
