extends Control
## MinimapRadar - Renders a stylized Pokemon radar minimap centered on the player

const RADAR_SCALE: float = 1.6 # pixels per meter (covers ~100m diameter view)

var player_node: Node3D = null
var current_region_name: String = "Pallet Town"

@onready var location_label: Label = get_node_or_null("../LocationContainer/LocationLabel") as Label

func _ready() -> void:
	custom_minimum_size = Vector2(150, 120)
	clip_contents = true

func _process(_delta: float) -> void:
	if not is_instance_valid(player_node):
		player_node = get_tree().get_first_node_in_group("player") as Node3D
	
	if is_instance_valid(player_node):
		_update_region_name(player_node.global_position)
		queue_redraw()

func _update_region_name(pos: Vector3) -> void:
	var new_name = "Starting Meadow"
	if pos.z > 8.0 and pos.z < 58.0 and pos.x > 0.0 and pos.x < 50.0:
		new_name = "Pallet Town"
	elif pos.z <= 8.0 and pos.z > -65.0 and pos.x > 0.0 and pos.x < 50.0:
		new_name = "Route 1"
	elif pos.z >= 58.0 and pos.x > 0.0 and pos.x < 50.0:
		new_name = "Route 21 Coast"
	elif pos.x > 100.0 and pos.z < 120.0:
		new_name = "Forest Trail"
	elif pos.z > 100.0 and pos.x < 100.0:
		new_name = "Crystal Lake"
	elif pos.z > 180.0 and pos.x > 100.0 and pos.x < 200.0:
		new_name = "Crumbling Ruins"
	elif pos.z > 180.0 and pos.x >= 200.0:
		new_name = "Ancient Shrine"
	elif pos.x >= 200.0 and pos.z < 180.0:
		new_name = "Tall Grass Plains"
	
	if new_name != current_region_name:
		current_region_name = new_name
		if is_instance_valid(location_label):
			location_label.text = current_region_name

func _draw() -> void:
	var center = size * 0.5
	var p_pos = Vector3(25.0, 0.0, 28.0)
	var p_rot: float = 0.0
	
	if is_instance_valid(player_node):
		p_pos = player_node.global_position
		if player_node.velocity.length_squared() > 0.1:
			p_rot = atan2(player_node.velocity.x, player_node.velocity.z)
		else:
			p_rot = player_node.rotation.y
	
	# 1. Base vibrant grass terrain
	draw_rect(Rect2(Vector2.ZERO, size), Color(0.34, 0.62, 0.22, 1.0))
	
	# 2. Water Bodies
	_draw_world_rect(Vector2(-30, 58), Vector2(100, 70), Color(0.24, 0.52, 0.86), center, p_pos) # Sea
	_draw_world_rect(Vector2(5, 110), Vector2(90, 90), Color(0.24, 0.52, 0.86), center, p_pos) # Lake
	
	# 3. Roads and Dirt Paths
	var path_col = Color(0.84, 0.73, 0.48)
	_draw_world_rect(Vector2(22, -65), Vector2(6, 122), path_col, center, p_pos) # Route 1 & Pallet Main Ave
	_draw_world_rect(Vector2(14, 25), Vector2(11, 4), path_col, center, p_pos) # Ash branch
	_draw_world_rect(Vector2(25, 25), Vector2(11, 4), path_col, center, p_pos) # Oak branch
	_draw_world_rect(Vector2(25, 41.5), Vector2(11, 4), path_col, center, p_pos) # Lab branch
	_draw_world_rect(Vector2(23.5, 56), Vector2(3, 10), Color(0.68, 0.52, 0.36), center, p_pos) # Pier
	_draw_world_rect(Vector2(-20, 23), Vector2(44, 4), path_col, center, p_pos) # West trail
	
	# 4. Buildings
	# Ash's House
	_draw_world_rect(Vector2(10.2, 21.0), Vector2(7.6, 6.0), Color(0.85, 0.25, 0.20), center, p_pos, Color.WHITE)
	# Oak's House
	_draw_world_rect(Vector2(32.2, 21.0), Vector2(7.6, 6.0), Color(0.78, 0.36, 0.22), center, p_pos, Color.WHITE)
	# Oak's Lab
	_draw_world_rect(Vector2(29.5, 43.5), Vector2(13.0, 9.0), Color(0.28, 0.48, 0.74), center, p_pos, Color.WHITE)
	
	# 5. Tall Grass Patches
	var grass_nodes = get_tree().get_nodes_in_group("tall_grass")
	for g in grass_nodes:
		if g is Node3D:
			var g_pos = g.global_position
			var g_size = Vector2(8.0, 8.0)
			if "patch_size" in g:
				g_size = Vector2(g.patch_size.x, g.patch_size.z)
			_draw_world_rect(Vector2(g_pos.x - g_size.x * 0.5, g_pos.z - g_size.y * 0.5), g_size, Color(0.46, 0.78, 0.24, 0.9), center, p_pos, Color(0.25, 0.55, 0.18))
	
	# 6. Trees
	var tree_nodes = get_tree().get_nodes_in_group("trees")
	for t in tree_nodes:
		if t is Node3D:
			var t_screen = _world_to_radar(Vector2(t.global_position.x, t.global_position.z), center, p_pos)
			if _is_point_visible(t_screen):
				draw_circle(t_screen, 3.2, Color(0.16, 0.42, 0.14))
				draw_circle(t_screen + Vector2(-0.8, -0.8), 1.2, Color(0.28, 0.60, 0.22))
	
	# 7. NPCs & Trainers
	var npc_nodes = get_tree().get_nodes_in_group("npc")
	for n in npc_nodes:
		if n is Node3D:
			var n_screen = _world_to_radar(Vector2(n.global_position.x, n.global_position.z), center, p_pos)
			if _is_point_visible(n_screen):
				draw_circle(n_screen, 3.0, Color(1.0, 0.75, 0.20))
				draw_arc(n_screen, 3.0, 0, TAU, 8, Color(0.2, 0.15, 0.05), 1.0)
	
	# 8. Wild Pokemon
	var wild_nodes = get_tree().get_nodes_in_group("wild_pokemon")
	for w in wild_nodes:
		if w is Node3D:
			var w_screen = _world_to_radar(Vector2(w.global_position.x, w.global_position.z), center, p_pos)
			if _is_point_visible(w_screen):
				draw_circle(w_screen, 2.5, Color(0.92, 0.32, 0.85))
	
	# 9. Signs and Points of Interest
	var obj_nodes = get_tree().get_nodes_in_group("interactable")
	for o in obj_nodes:
		if o is Node3D and not o.is_in_group("npc") and not o.is_in_group("tall_grass"):
			var o_screen = _world_to_radar(Vector2(o.global_position.x, o.global_position.z), center, p_pos)
			if _is_point_visible(o_screen):
				draw_circle(o_screen, 2.2, Color(0.30, 0.85, 0.95))
	
	# 10. Radar Range Ring
	draw_arc(center, 44.0, 0, TAU, 32, Color(1, 1, 1, 0.18), 1.0)
	
	# 11. Player Arrow (Directional marker)
	_draw_player_marker(center, p_rot)

func _world_to_radar(world_xz: Vector2, center: Vector2, p_pos: Vector3) -> Vector2:
	return center + Vector2(world_xz.x - p_pos.x, world_xz.y - p_pos.z) * RADAR_SCALE

func _is_point_visible(pt: Vector2) -> bool:
	return pt.x >= -12 and pt.x <= size.x + 12 and pt.y >= -12 and pt.y <= size.y + 12

func _draw_world_rect(w_pos: Vector2, w_size: Vector2, col: Color, center: Vector2, p_pos: Vector3, border_col: Color = Color.TRANSPARENT) -> void:
	var top_left = _world_to_radar(w_pos, center, p_pos)
	var r_size = w_size * RADAR_SCALE
	var r = Rect2(top_left, r_size)
	if r.intersects(Rect2(Vector2.ZERO, size)):
		draw_rect(r, col)
		if border_col != Color.TRANSPARENT:
			draw_rect(r, border_col, false, 1.2)

func _draw_player_marker(center: Vector2, angle_rad: float) -> void:
	var forward = Vector2(sin(angle_rad), cos(angle_rad)).normalized()
	var right = Vector2(-forward.y, forward.x)
	
	var tip = center + forward * 8.0
	var back_left = center - forward * 5.0 + right * 5.0
	var back_right = center - forward * 5.0 - right * 5.0
	var notch = center - forward * 2.5
	
	var points = PackedVector2Array([tip, back_left, notch, back_right])
	draw_colored_polygon(points, Color(0.95, 0.20, 0.18))
	draw_polyline(points + PackedVector2Array([tip]), Color(1, 1, 1, 1), 1.5)
	draw_circle(center, 2.2, Color(1, 1, 1, 1))
	draw_circle(center, 1.2, Color(0.15, 0.2, 0.3))
