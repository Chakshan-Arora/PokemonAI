extends CanvasLayer
## BattleTransition - Manages full-screen transition animations
## 1. Wild Pokemon Encounter Transition: Flash strobe, horizontal shutter wipe, spinning Pokeball, and encounter badge.
## 2. In-Battle Intro Animation: Diagonal chevron shutter sweep, neon glow borders, and dynamic VS / BATTLE START banner.
## 3. In-Battle Attack Impact Animation: Full-screen anime speed lines, diagonal energy slash, screen shake, and impact badge.

signal wild_transition_completed
signal battle_intro_completed
signal impact_animation_completed

var is_transitioning: bool = false

# Wild Encounter Nodes
var _wild_root: Control = null
var _flash_rect: ColorRect = null
var _shutter_bars: Array[ColorRect] = []
var _wild_banner: PanelContainer = null
var _wild_title: Label = null
var _wild_subtitle: Label = null
var _pokeball_draw: Control = null

# Battle Intro Nodes
var _battle_root: Control = null
var _battle_top_slab: Polygon2D = null
var _battle_bottom_slab: Polygon2D = null
var _battle_line_top: Line2D = null
var _battle_line_bottom: Line2D = null
var _vs_banner: PanelContainer = null
var _vs_title: Label = null

# Battle Impact Nodes
var _impact_root: Control = null
var _impact_flash: ColorRect = null
var _impact_speed_lines: Control = null
var _impact_slash: Line2D = null
var _impact_badge: PanelContainer = null
var _impact_text: Label = null

var _pokeball_angle: float = 0.0
var _pokeball_scale: float = 1.0
var _speed_lines_progress: float = 0.0

func _ready() -> void:
	layer = 125
	process_mode = Node.PROCESS_MODE_ALWAYS
	_build_ui()

func _build_ui() -> void:
	# Root container
	var root = Control.new()
	root.name = "TransitionRoot"
	root.anchors_preset = Control.PRESET_FULL_RECT
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(root)
	
	# =========================================================================
	# 1. WILD ENCOUNTER TRANSITION UI
	# =========================================================================
	_wild_root = Control.new()
	_wild_root.name = "WildEncounterRoot"
	_wild_root.anchors_preset = Control.PRESET_FULL_RECT
	_wild_root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_wild_root.visible = false
	root.add_child(_wild_root)
	
	# Horizontal Shutter Bars (12 bars alternating from left & right)
	_shutter_bars.clear()
	var bar_count = 12
	for i in range(bar_count):
		var bar = ColorRect.new()
		bar.name = "Bar_%02d" % i
		bar.color = Color(0.06, 0.08, 0.12, 1.0)
		bar.mouse_filter = Control.MOUSE_FILTER_IGNORE
		_wild_root.add_child(bar)
		_shutter_bars.append(bar)
	
	# Custom Draw Spinning Pokeball Silhouette
	_pokeball_draw = Control.new()
	_pokeball_draw.name = "PokeballSilhouette"
	_pokeball_draw.anchors_preset = Control.PRESET_CENTER
	_pokeball_draw.custom_minimum_size = Vector2(160, 160)
	_pokeball_draw.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_pokeball_draw.draw.connect(_on_draw_pokeball)
	_wild_root.add_child(_pokeball_draw)
	
	# Wild Encounter Badge
	_wild_banner = PanelContainer.new()
	_wild_banner.name = "WildBanner"
	_wild_banner.anchors_preset = Control.PRESET_CENTER
	_wild_banner.mouse_filter = Control.MOUSE_FILTER_IGNORE
	
	var wild_box = StyleBoxFlat.new()
	wild_box.bg_color = Color(0.08, 0.12, 0.18, 0.95)
	wild_box.border_width_left = 3
	wild_box.border_width_top = 3
	wild_box.border_width_right = 3
	wild_box.border_width_bottom = 3
	wild_box.border_color = Color(0.95, 0.22, 0.20, 1.0) # Vivid Red
	wild_box.set_corner_radius_all(8)
	wild_box.shadow_color = Color(0, 0, 0, 0.6)
	wild_box.shadow_size = 8
	_wild_banner.add_theme_stylebox_override("panel", wild_box)
	
	var wild_vbox = VBoxContainer.new()
	wild_vbox.alignment = BoxContainer.ALIGNMENT_CENTER
	wild_vbox.add_theme_constant_override("separation", 4)
	
	_wild_title = Label.new()
	_wild_title.text = "⚡ WILD POKÉMON ENCOUNTER! ⚡"
	_wild_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_wild_title.add_theme_font_size_override("font_size", 22)
	_wild_title.add_theme_color_override("font_color", Color(1.0, 0.88, 0.25, 1.0))
	_wild_title.add_theme_constant_override("outline_size", 6)
	_wild_title.add_theme_color_override("font_outline_color", Color(0.2, 0.05, 0.05, 1.0))
	wild_vbox.add_child(_wild_title)
	
	_wild_subtitle = Label.new()
	_wild_subtitle.text = "A wild Pokémon appeared!"
	_wild_subtitle.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_wild_subtitle.add_theme_font_size_override("font_size", 16)
	_wild_subtitle.add_theme_color_override("font_color", Color(0.95, 0.95, 0.95, 1.0))
	wild_vbox.add_child(_wild_subtitle)
	
	_wild_banner.add_child(wild_vbox)
	_wild_root.add_child(_wild_banner)
	
	# Flash Rect on top of wild root
	_flash_rect = ColorRect.new()
	_flash_rect.name = "FlashRect"
	_flash_rect.anchors_preset = Control.PRESET_FULL_RECT
	_flash_rect.color = Color(1, 1, 1, 0)
	_flash_rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_wild_root.add_child(_flash_rect)
	
	# =========================================================================
	# 2. IN-BATTLE INTRO TRANSITION UI (Diagonal Chevron Shutter Reveal)
	# =========================================================================
	_battle_root = Control.new()
	_battle_root.name = "BattleIntroRoot"
	_battle_root.anchors_preset = Control.PRESET_FULL_RECT
	_battle_root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_battle_root.visible = false
	root.add_child(_battle_root)
	
	_battle_top_slab = Polygon2D.new()
	_battle_top_slab.color = Color(0.08, 0.12, 0.18, 1.0)
	_battle_root.add_child(_battle_top_slab)
	
	_battle_line_top = Line2D.new()
	_battle_line_top.default_color = Color(0.25, 0.75, 1.0, 1.0) # Glowing Cyan
	_battle_line_top.width = 4.0
	_battle_root.add_child(_battle_line_top)
	
	_battle_bottom_slab = Polygon2D.new()
	_battle_bottom_slab.color = Color(0.06, 0.09, 0.15, 1.0)
	_battle_root.add_child(_battle_bottom_slab)
	
	_battle_line_bottom = Line2D.new()
	_battle_line_bottom.default_color = Color(0.95, 0.78, 0.25, 1.0) # Gold
	_battle_line_bottom.width = 4.0
	_battle_root.add_child(_battle_line_bottom)
	
	# VS / Battle Start Banner
	_vs_banner = PanelContainer.new()
	_vs_banner.name = "VSBanner"
	_vs_banner.anchors_preset = Control.PRESET_CENTER
	_vs_banner.mouse_filter = Control.MOUSE_FILTER_IGNORE
	
	var vs_box = StyleBoxFlat.new()
	vs_box.bg_color = Color(0.05, 0.08, 0.14, 0.95)
	vs_box.border_width_left = 3
	vs_box.border_width_top = 3
	vs_box.border_width_right = 3
	vs_box.border_width_bottom = 3
	vs_box.border_color = Color(0.3, 0.8, 1.0, 1.0)
	vs_box.set_corner_radius_all(6)
	vs_box.shadow_color = Color(0, 0, 0, 0.7)
	vs_box.shadow_size = 10
	_vs_banner.add_theme_stylebox_override("panel", vs_box)
	
	var vs_vbox = VBoxContainer.new()
	vs_vbox.alignment = BoxContainer.ALIGNMENT_CENTER
	
	_vs_title = Label.new()
	_vs_title.text = "⚔ BATTLE START! ⚔"
	_vs_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_vs_title.add_theme_font_size_override("font_size", 26)
	_vs_title.add_theme_color_override("font_color", Color(1.0, 1.0, 1.0, 1.0))
	_vs_title.add_theme_constant_override("outline_size", 6)
	_vs_title.add_theme_color_override("font_outline_color", Color(0.1, 0.3, 0.5, 1.0))
	vs_vbox.add_child(_vs_title)
	
	_vs_banner.add_child(vs_vbox)
	_battle_root.add_child(_vs_banner)
	
	# =========================================================================
	# 3. IN-BATTLE ATTACK IMPACT ANIMATION UI
	# =========================================================================
	_impact_root = Control.new()
	_impact_root.name = "ImpactRoot"
	_impact_root.anchors_preset = Control.PRESET_FULL_RECT
	_impact_root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_impact_root.visible = false
	root.add_child(_impact_root)
	
	_impact_flash = ColorRect.new()
	_impact_flash.anchors_preset = Control.PRESET_FULL_RECT
	_impact_flash.color = Color(1, 1, 1, 0)
	_impact_flash.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_impact_root.add_child(_impact_flash)
	
	_impact_speed_lines = Control.new()
	_impact_speed_lines.name = "SpeedLines"
	_impact_speed_lines.anchors_preset = Control.PRESET_FULL_RECT
	_impact_speed_lines.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_impact_speed_lines.draw.connect(_on_draw_speed_lines)
	_impact_root.add_child(_impact_speed_lines)
	
	_impact_slash = Line2D.new()
	_impact_slash.default_color = Color(1.0, 0.95, 0.85, 1.0)
	_impact_slash.width = 8.0
	_impact_root.add_child(_impact_slash)
	
	_impact_badge = PanelContainer.new()
	_impact_badge.name = "ImpactBadge"
	_impact_badge.anchors_preset = Control.PRESET_CENTER
	_impact_badge.mouse_filter = Control.MOUSE_FILTER_IGNORE
	
	var imp_box = StyleBoxFlat.new()
	imp_box.bg_color = Color(0.9, 0.15, 0.15, 0.92)
	imp_box.border_width_left = 2
	imp_box.border_width_top = 2
	imp_box.border_width_right = 2
	imp_box.border_width_bottom = 2
	imp_box.border_color = Color(1.0, 0.9, 0.3, 1.0)
	imp_box.set_corner_radius_all(6)
	_impact_badge.add_theme_stylebox_override("panel", imp_box)
	
	_impact_text = Label.new()
	_impact_text.text = "CRITICAL HIT!"
	_impact_text.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_impact_text.add_theme_font_size_override("font_size", 20)
	_impact_text.add_theme_color_override("font_color", Color(1, 1, 1, 1))
	_impact_text.add_theme_constant_override("outline_size", 4)
	_impact_text.add_theme_color_override("font_outline_color", Color(0, 0, 0, 1))
	_impact_badge.add_child(_impact_text)
	_impact_root.add_child(_impact_badge)

# =============================================================================
# 1. WILD POKEMON ENCOUNTER ANIMATION (Before the fight)
# =============================================================================
func start_wild_encounter(wild_pokemon_dict: Dictionary) -> void:
	if is_transitioning:
		return
	is_transitioning = true
	
	var species_name = wild_pokemon_dict.get("species", "Wild Pokémon")
	if _wild_subtitle:
		_wild_subtitle.text = "A wild %s appeared!" % species_name
	
	# Setup GameState metadata and flags
	GameState.set_meta("wild_pokemon_for_battle", wild_pokemon_dict)
	GameState.set_meta("is_trainer_battle", false)
	GameState.enter_battle()
	
	_play_wild_transition()

func _play_wild_transition() -> void:
	_wild_root.visible = true
	_wild_root.mouse_filter = Control.MOUSE_FILTER_STOP
	_pokeball_angle = 0.0
	_pokeball_scale = 0.1
	_pokeball_draw.scale = Vector2(0.1, 0.1)
	_pokeball_draw.modulate.a = 0.0
	_wild_banner.scale = Vector2(0.1, 0.1)
	_wild_banner.modulate.a = 0.0
	
	var vp_size = _wild_root.get_viewport_rect().size
	var bar_count = _shutter_bars.size()
	var bar_h = ceil(vp_size.y / float(bar_count))
	
	# Position bars off-screen initially
	for i in range(bar_count):
		var bar = _shutter_bars[i]
		bar.size = Vector2(vp_size.x, bar_h + 1.0)
		bar.position.y = i * bar_h
		bar.position.x = -vp_size.x if (i % 2 == 0) else vp_size.x
	
	# Center pokeball and badge
	_pokeball_draw.position = (vp_size - _pokeball_draw.size) * 0.5
	_wild_banner.position = Vector2((vp_size.x - 360.0) * 0.5, vp_size.y * 0.5 + 40.0)
	_wild_banner.size = Vector2(360.0, 70.0)
	
	var tween = create_tween().set_parallel(false)
	
	# Phase 1: Rapid Retro Strobe Flashes (3 sharp flashes)
	tween.tween_property(_flash_rect, "color:a", 0.9, 0.05)
	tween.tween_property(_flash_rect, "color:a", 0.0, 0.05)
	tween.tween_property(_flash_rect, "color:a", 0.9, 0.05)
	tween.tween_property(_flash_rect, "color:a", 0.0, 0.05)
	tween.tween_property(_flash_rect, "color:a", 1.0, 0.06)
	tween.tween_property(_flash_rect, "color:a", 0.0, 0.06)
	
	# Phase 2: Horizontal Shutters slice in from left and right
	var shutter_tween = create_tween().set_parallel(true)
	for i in range(bar_count):
		var bar = _shutter_bars[i]
		var delay = (i % 3) * 0.04
		shutter_tween.tween_property(bar, "position:x", 0.0, 0.32).set_delay(delay).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	
	# Pop in Pokeball and Wild Banner
	shutter_tween.tween_property(_pokeball_draw, "modulate:a", 1.0, 0.25)
	shutter_tween.tween_property(_pokeball_draw, "scale", Vector2(1.0, 1.0), 0.35).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	shutter_tween.tween_property(_wild_banner, "modulate:a", 1.0, 0.25)
	shutter_tween.tween_property(_wild_banner, "scale", Vector2(1.0, 1.0), 0.35).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	
	# Spin pokeball
	var spin_tween = create_tween()
	spin_tween.tween_method(func(val):
		_pokeball_angle = val
		_pokeball_draw.queue_redraw()
	, 0.0, TAU * 2.0, 0.45)
	
	# Phase 3: Hold brief moment then wipe into Battle Scene
	await shutter_tween.finished
	await get_tree().create_timer(0.35).timeout
	
	# Change scene to Battle
	get_tree().change_scene_to_file("res://scenes/Battle.tscn")
	
	# Phase 4: Slide bars out to reveal battle
	var out_tween = create_tween().set_parallel(true)
	for i in range(bar_count):
		var bar = _shutter_bars[i]
		var target_x = vp_size.x if (i % 2 == 0) else -vp_size.x
		out_tween.tween_property(bar, "position:x", target_x, 0.35).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
	
	out_tween.tween_property(_pokeball_draw, "modulate:a", 0.0, 0.25)
	out_tween.tween_property(_wild_banner, "modulate:a", 0.0, 0.25)
	
	await out_tween.finished
	_wild_root.visible = false
	_wild_root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	is_transitioning = false
	wild_transition_completed.emit()

func _on_draw_pokeball() -> void:
	var center = _pokeball_draw.size * 0.5
	var r = 50.0
	
	# Rotate canvas around center
	_pokeball_draw.draw_set_transform(center, _pokeball_angle, Vector2.ONE)
	
	# Outer Pokeball Circle
	_pokeball_draw.draw_circle(Vector2.ZERO, r, Color(0.95, 0.25, 0.22, 0.95)) # Red top
	
	# Bottom white hemisphere
	var pts: PackedVector2Array = []
	pts.append(Vector2(-r, 0))
	for a in range(0, 185, 10):
		var rad = deg_to_rad(a)
		pts.append(Vector2(cos(rad) * r, sin(rad) * r))
	pts.append(Vector2(r, 0))
	_pokeball_draw.draw_polygon(pts, [Color(0.95, 0.95, 0.95, 0.95)])
	
	# Outer border ring
	_pokeball_draw.draw_arc(Vector2.ZERO, r, 0, TAU, 32, Color(0.1, 0.12, 0.18, 1.0), 4.0)
	# Center divider line
	_pokeball_draw.draw_line(Vector2(-r, 0), Vector2(r, 0), Color(0.1, 0.12, 0.18, 1.0), 4.0)
	# Center button
	_pokeball_draw.draw_circle(Vector2.ZERO, 16.0, Color(0.1, 0.12, 0.18, 1.0))
	_pokeball_draw.draw_circle(Vector2.ZERO, 10.0, Color(1, 1, 1, 1.0))
	_pokeball_draw.draw_circle(Vector2.ZERO, 5.0, Color(0.8, 0.85, 0.9, 1.0))

# =============================================================================
# 2. IN-BATTLE INTRO ANIMATION (Different full-screen animation in battles)
# =============================================================================
func play_battle_intro_animation(on_complete: Callable = Callable()) -> void:
	_battle_root.visible = true
	var vp = _battle_root.get_viewport_rect().size
	var diag_offset = vp.x * 0.35
	
	# Configure Top Slab (covers top-left half)
	var top_pts = PackedVector2Array([
		Vector2(0, 0),
		Vector2(vp.x + diag_offset, 0),
		Vector2(0, vp.y + diag_offset)
	])
	_battle_top_slab.polygon = top_pts
	
	# Top dividing line
	_battle_line_top.points = PackedVector2Array([
		Vector2(vp.x + diag_offset, 0),
		Vector2(0, vp.y + diag_offset)
	])
	
	# Configure Bottom Slab (covers bottom-right half)
	var btm_pts = PackedVector2Array([
		Vector2(vp.x + diag_offset, 0),
		Vector2(vp.x, vp.y),
		Vector2(0, vp.y),
		Vector2(0, vp.y + diag_offset)
	])
	_battle_bottom_slab.polygon = btm_pts
	
	# Bottom dividing line
	_battle_line_bottom.points = PackedVector2Array([
		Vector2(vp.x + diag_offset, 0),
		Vector2(0, vp.y + diag_offset)
	])
	
	# Center VS Banner
	_vs_banner.position = Vector2((vp.x - 300.0) * 0.5, (vp.y - 60.0) * 0.5)
	_vs_banner.size = Vector2(300.0, 60.0)
	_vs_banner.scale = Vector2(0.2, 0.2)
	_vs_banner.modulate.a = 0.0
	
	# Reset slab offsets to fully covering screen
	_battle_top_slab.position = Vector2.ZERO
	_battle_line_top.position = Vector2.ZERO
	_battle_bottom_slab.position = Vector2.ZERO
	_battle_line_bottom.position = Vector2.ZERO
	
	# Animate VS banner punch
	var intro_tw = create_tween()
	intro_tw.tween_property(_vs_banner, "modulate:a", 1.0, 0.15)
	intro_tw.parallel().tween_property(_vs_banner, "scale", Vector2(1.05, 1.05), 0.25).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	intro_tw.tween_interval(0.25)
	
	# Slice open diagonal chevrons apart!
	var open_tw = create_tween().set_parallel(true)
	var move_dist = vp.y * 1.4
	open_tw.tween_property(_battle_top_slab, "position", Vector2(-move_dist, -move_dist), 0.45).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN_OUT)
	open_tw.tween_property(_battle_line_top, "position", Vector2(-move_dist, -move_dist), 0.45).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN_OUT)
	open_tw.tween_property(_battle_bottom_slab, "position", Vector2(move_dist, move_dist), 0.45).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN_OUT)
	open_tw.tween_property(_battle_line_bottom, "position", Vector2(move_dist, move_dist), 0.45).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN_OUT)
	open_tw.tween_property(_vs_banner, "modulate:a", 0.0, 0.3)
	open_tw.tween_property(_vs_banner, "scale", Vector2(1.4, 0.1), 0.3)
	
	await open_tw.finished
	_battle_root.visible = false
	battle_intro_completed.emit()
	if on_complete.is_valid():
		on_complete.call()

# =============================================================================
# 3. IN-BATTLE ATTACK IMPACT ANIMATION (Full-screen anime speed lines & slash)
# =============================================================================
func play_attack_impact_animation(move_name: String, is_super_effective: bool = false, is_critical: bool = false, on_complete: Callable = Callable()) -> void:
	_impact_root.visible = true
	var vp = _impact_root.get_viewport_rect().size
	
	# Setup impact badge text
	if is_super_effective and is_critical:
		_impact_text.text = "💥 SUPER-EFFECTIVE CRITICAL HIT! 💥"
	elif is_super_effective:
		_impact_text.text = "⚡ SUPER EFFECTIVE! ⚡"
	elif is_critical:
		_impact_text.text = "🎯 CRITICAL HIT! 🎯"
	else:
		_impact_text.text = "⚡ %s! ⚡" % move_name.to_upper()
	
	_impact_badge.position = Vector2((vp.x - 340.0) * 0.5, vp.y * 0.28)
	_impact_badge.size = Vector2(340.0, 50.0)
	_impact_badge.scale = Vector2(0.2, 0.2)
	_impact_badge.modulate.a = 0.0
	
	# Configure diagonal slash line
	_impact_slash.points = PackedVector2Array([
		Vector2(vp.x * 0.1, vp.y * 0.85),
		Vector2(vp.x * 0.9, vp.y * 0.15)
	])
	_impact_slash.modulate.a = 0.0
	
	# Color determination
	var flash_col = Color(1.0, 0.2, 0.2, 0.5) if (is_critical or is_super_effective) else Color(1.0, 0.9, 0.4, 0.4)
	
	var tw = create_tween().set_parallel(true)
	# Full-screen flash
	tw.tween_property(_impact_flash, "color", flash_col, 0.06)
	tw.tween_property(_impact_slash, "modulate:a", 1.0, 0.08)
	tw.tween_property(_impact_badge, "modulate:a", 1.0, 0.1)
	tw.tween_property(_impact_badge, "scale", Vector2(1.1, 1.1), 0.18).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	
	# Speed lines animation
	var lines_tw = create_tween()
	lines_tw.tween_method(func(val):
		_speed_lines_progress = val
		_impact_speed_lines.queue_redraw()
	, 0.0, 1.0, 0.28)
	
	await tw.finished
	await lines_tw.finished
	
	# Fade out
	var fade_tw = create_tween().set_parallel(true)
	fade_tw.tween_property(_impact_flash, "color:a", 0.0, 0.18)
	fade_tw.tween_property(_impact_slash, "modulate:a", 0.0, 0.15)
	fade_tw.tween_property(_impact_badge, "modulate:a", 0.0, 0.15)
	fade_tw.tween_property(_impact_badge, "scale", Vector2(1.3, 0.2), 0.15)
	
	await fade_tw.finished
	_impact_root.visible = false
	impact_animation_completed.emit()
	if on_complete.is_valid():
		on_complete.call()

func _on_draw_speed_lines() -> void:
	if _speed_lines_progress <= 0.01 or _speed_lines_progress >= 0.99:
		return
	
	var vp = _impact_speed_lines.get_viewport_rect().size
	var center = vp * 0.5
	var line_count = 24
	var alpha = (1.0 - _speed_lines_progress) * 0.75
	var col = Color(1.0, 0.95, 0.8, alpha)
	
	for i in range(line_count):
		var angle = (float(i) / float(line_count)) * TAU
		var dir = Vector2(cos(angle), sin(angle))
		var start_dist = lerp(80.0, 40.0, _speed_lines_progress)
		var end_dist = max(vp.x, vp.y) * 1.1
		_impact_speed_lines.draw_line(center + dir * start_dist, center + dir * end_dist, col, 2.5)

# Trainer encounter initiation
func start_trainer_encounter(opp_pokemon_dict: Dictionary, trainer_name: String) -> void:
	if is_transitioning:
		return
	is_transitioning = true
	
	if _wild_title:
		_wild_title.text = "⚔ TRAINER BATTLE CHALLENGE! ⚔"
	if _wild_subtitle:
		_wild_subtitle.text = "%s wants to battle!" % trainer_name
	
	GameState.set_meta("wild_pokemon_for_battle", opp_pokemon_dict)
	GameState.set_meta("is_trainer_battle", true)
	GameState.enter_battle()
	
	_play_wild_transition()
