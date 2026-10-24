extends Node3D
## World - Root scene for the 3D explorable Pokemon world

const RegionData = preload("res://scripts/data/RegionData.gd")

@onready var player_node: CharacterBody3D = $Player
@onready var hud: Control = $UILayer/HUD
@onready var world_env: WorldEnvironment = $WorldEnvironment
@onready var sun_light: DirectionalLight3D = $DirectionalLight3D

var _sky_mat: ProceduralSkyMaterial = null
var _env_res: Environment = null

# Day/night lighting keyframe table covering the complete 24-hour cycle
const KEYFRAMES = [
	{
		"time": 0.0,
		"sky_top": Color(0.025, 0.035, 0.085, 1.0),
		"sky_horizon": Color(0.06, 0.085, 0.16, 1.0),
		"ground_bottom": Color(0.02, 0.03, 0.04, 1.0),
		"ground_horizon": Color(0.04, 0.06, 0.08, 1.0),
		"sky_energy": 0.28,
		"ambient_color": Color(0.14, 0.18, 0.28, 1.0),
		"ambient_energy": 0.36,
		"light_color": Color(0.52, 0.62, 0.84, 1.0),
		"light_energy": 0.24,
		"pitch": -50.0,
		"yaw": 40.0
	},
	{
		"time": 5.0,
		"sky_top": Color(0.06, 0.08, 0.18, 1.0),
		"sky_horizon": Color(0.28, 0.18, 0.32, 1.0),
		"ground_bottom": Color(0.04, 0.05, 0.06, 1.0),
		"ground_horizon": Color(0.08, 0.10, 0.12, 1.0),
		"sky_energy": 0.42,
		"ambient_color": Color(0.20, 0.22, 0.35, 1.0),
		"ambient_energy": 0.40,
		"light_color": Color(0.62, 0.65, 0.82, 1.0),
		"light_energy": 0.30,
		"pitch": -30.0,
		"yaw": 55.0
	},
	{
		"time": 6.5,
		"sky_top": Color(0.22, 0.38, 0.72, 1.0),
		"sky_horizon": Color(0.98, 0.62, 0.36, 1.0),
		"ground_bottom": Color(0.14, 0.24, 0.14, 1.0),
		"ground_horizon": Color(0.40, 0.44, 0.30, 1.0),
		"sky_energy": 0.80,
		"ambient_color": Color(0.62, 0.54, 0.48, 1.0),
		"ambient_energy": 0.65,
		"light_color": Color(1.0, 0.82, 0.55, 1.0),
		"light_energy": 0.85,
		"pitch": -18.0,
		"yaw": 75.0
	},
	{
		"time": 9.0,
		"sky_top": Color(0.35, 0.62, 0.96, 1.0),
		"sky_horizon": Color(0.72, 0.84, 0.96, 1.0),
		"ground_bottom": Color(0.22, 0.42, 0.22, 1.0),
		"ground_horizon": Color(0.58, 0.70, 0.58, 1.0),
		"sky_energy": 1.0,
		"ambient_color": Color(0.68, 0.75, 0.86, 1.0),
		"ambient_energy": 0.85,
		"light_color": Color(1.0, 0.96, 0.90, 1.0),
		"light_energy": 1.10,
		"pitch": -45.0,
		"yaw": 105.0
	},
	{
		"time": 12.5,
		"sky_top": Color(0.38, 0.65, 0.98, 1.0),
		"sky_horizon": Color(0.75, 0.85, 0.95, 1.0),
		"ground_bottom": Color(0.25, 0.45, 0.25, 1.0),
		"ground_horizon": Color(0.65, 0.75, 0.65, 1.0),
		"sky_energy": 1.0,
		"ambient_color": Color(0.70, 0.78, 0.88, 1.0),
		"ambient_energy": 0.90,
		"light_color": Color(1.0, 0.98, 0.92, 1.0),
		"light_energy": 1.18,
		"pitch": -68.0,
		"yaw": 145.0
	},
	{
		"time": 17.0,
		"sky_top": Color(0.30, 0.46, 0.80, 1.0),
		"sky_horizon": Color(0.96, 0.68, 0.38, 1.0),
		"ground_bottom": Color(0.20, 0.38, 0.20, 1.0),
		"ground_horizon": Color(0.58, 0.55, 0.38, 1.0),
		"sky_energy": 0.90,
		"ambient_color": Color(0.68, 0.60, 0.52, 1.0),
		"ambient_energy": 0.82,
		"light_color": Color(1.0, 0.80, 0.50, 1.0),
		"light_energy": 1.05,
		"pitch": -35.0,
		"yaw": 195.0
	},
	{
		"time": 19.0,
		"sky_top": Color(0.22, 0.16, 0.38, 1.0),
		"sky_horizon": Color(0.94, 0.44, 0.20, 1.0),
		"ground_bottom": Color(0.12, 0.16, 0.14, 1.0),
		"ground_horizon": Color(0.40, 0.28, 0.24, 1.0),
		"sky_energy": 0.70,
		"ambient_color": Color(0.48, 0.36, 0.42, 1.0),
		"ambient_energy": 0.60,
		"light_color": Color(1.0, 0.52, 0.28, 1.0),
		"light_energy": 0.75,
		"pitch": -16.0,
		"yaw": 230.0
	},
	{
		"time": 20.5,
		"sky_top": Color(0.08, 0.08, 0.22, 1.0),
		"sky_horizon": Color(0.35, 0.20, 0.32, 1.0),
		"ground_bottom": Color(0.05, 0.07, 0.08, 1.0),
		"ground_horizon": Color(0.16, 0.12, 0.16, 1.0),
		"sky_energy": 0.45,
		"ambient_color": Color(0.25, 0.22, 0.36, 1.0),
		"ambient_energy": 0.45,
		"light_color": Color(0.58, 0.52, 0.72, 1.0),
		"light_energy": 0.38,
		"pitch": -30.0,
		"yaw": 260.0
	},
	{
		"time": 22.0,
		"sky_top": Color(0.025, 0.035, 0.085, 1.0),
		"sky_horizon": Color(0.06, 0.085, 0.16, 1.0),
		"ground_bottom": Color(0.02, 0.03, 0.04, 1.0),
		"ground_horizon": Color(0.04, 0.06, 0.08, 1.0),
		"sky_energy": 0.28,
		"ambient_color": Color(0.14, 0.18, 0.28, 1.0),
		"ambient_energy": 0.36,
		"light_color": Color(0.52, 0.62, 0.84, 1.0),
		"light_energy": 0.24,
		"pitch": -50.0,
		"yaw": 40.0
	},
	{
		"time": 24.0,
		"sky_top": Color(0.025, 0.035, 0.085, 1.0),
		"sky_horizon": Color(0.06, 0.085, 0.16, 1.0),
		"ground_bottom": Color(0.02, 0.03, 0.04, 1.0),
		"ground_horizon": Color(0.04, 0.06, 0.08, 1.0),
		"sky_energy": 0.28,
		"ambient_color": Color(0.14, 0.18, 0.28, 1.0),
		"ambient_energy": 0.36,
		"light_color": Color(0.52, 0.62, 0.84, 1.0),
		"light_energy": 0.24,
		"pitch": -50.0,
		"yaw": 40.0
	}
]

func _ready() -> void:
	# Ensure GameState has a player model if testing World scene directly
	if GameState.player == null:
		GameState.new_game("Trainer", "Bulbasaur")
	
	GameState.exit_battle()
	GameState.resume_game()
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	
	# Restore player position from saved/previous state
	if player_node and GameState.player and GameState.player.player_position != Vector3.ZERO:
		player_node.global_position = GameState.player.player_position
	
	# Update region on start
	if player_node:
		var reg = RegionData.get_region_at_position(player_node.global_position.x, player_node.global_position.z)
		if reg != "":
			GameState.change_region(reg)
	
	# Initialize unique copies of environment and sky material for dynamic day/night
	if world_env and world_env.environment:
		_env_res = world_env.environment.duplicate()
		world_env.environment = _env_res
		if _env_res.sky:
			_env_res.sky = _env_res.sky.duplicate()
			if _env_res.sky.sky_material and _env_res.sky.sky_material is ProceduralSkyMaterial:
				_sky_mat = _env_res.sky.sky_material.duplicate()
				_env_res.sky.sky_material = _sky_mat
	
	update_day_night_cycle(GameState.game_time)
	EventBus.render_distance_changed.connect(_on_render_distance_changed)
	_on_render_distance_changed(GameState.get_render_distance())
	EventBus.hud_update_requested.emit()

func _process(_delta: float) -> void:
	if GameState.is_game_started:
		update_day_night_cycle(GameState.game_time)

func update_day_night_cycle(time: float) -> void:
	if not sun_light or not _env_res:
		return
	
	# Wrap time into [0.0, 24.0)
	var t_hour = fmod(time, 24.0)
	if t_hour < 0.0:
		t_hour += 24.0
	
	# Find surrounding keyframes
	var k1 = KEYFRAMES[0]
	var k2 = KEYFRAMES[1]
	for i in range(KEYFRAMES.size() - 1):
		if t_hour >= KEYFRAMES[i].time and t_hour <= KEYFRAMES[i + 1].time:
			k1 = KEYFRAMES[i]
			k2 = KEYFRAMES[i + 1]
			break
	
	var span = k2.time - k1.time
	var factor: float = (t_hour - k1.time) / span if span > 0.0001 else 0.0
	factor = clampf(factor, 0.0, 1.0)
	
	# Interpolate Sky properties
	if _sky_mat:
		_sky_mat.sky_top_color = k1.sky_top.lerp(k2.sky_top, factor)
		_sky_mat.sky_horizon_color = k1.sky_horizon.lerp(k2.sky_horizon, factor)
		_sky_mat.ground_bottom_color = k1.ground_bottom.lerp(k2.ground_bottom, factor)
		_sky_mat.ground_horizon_color = k1.ground_horizon.lerp(k2.ground_horizon, factor)
		_sky_mat.sky_energy_multiplier = lerpf(k1.sky_energy, k2.sky_energy, factor)
	
	# Interpolate Ambient Light
	_env_res.ambient_light_color = k1.ambient_color.lerp(k2.ambient_color, factor)
	_env_res.ambient_light_energy = lerpf(k1.ambient_energy, k2.ambient_energy, factor)
	
	# Interpolate Directional Light (Sun/Moon)
	sun_light.light_color = k1.light_color.lerp(k2.light_color, factor)
	sun_light.light_energy = lerpf(k1.light_energy, k2.light_energy, factor)
	
	var pitch = lerpf(k1.pitch, k2.pitch, factor)
	var yaw_rad = lerp_angle(deg_to_rad(k1.yaw), deg_to_rad(k2.yaw), factor)
	sun_light.rotation_degrees = Vector3(pitch, rad_to_deg(yaw_rad), 0.0)
	
	if _env_res and _env_res.fog_enabled and _sky_mat:
		_env_res.fog_light_color = _sky_mat.sky_horizon_color

func _on_render_distance_changed(val: float) -> void:
	if _env_res:
		_env_res.fog_enabled = true
		_env_res.fog_mode = Environment.FOG_MODE_DEPTH
		_env_res.fog_depth_begin = val * 0.55
		_env_res.fog_depth_end = val
		if _sky_mat:
			_env_res.fog_light_color = _sky_mat.sky_horizon_color
