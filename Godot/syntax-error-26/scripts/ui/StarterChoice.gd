extends Control
## StarterChoice - Starter Pokémon selection screen

const PokemonData = preload("res://scripts/data/PokemonData.gd")

@onready var bulbasaur_btn: Button = $HBoxContainer/BulbasaurPanel/SelectBtn
@onready var charmander_btn: Button = $HBoxContainer/CharmanderPanel/SelectBtn
@onready var squirtle_btn: Button = $HBoxContainer/SquirtlePanel/SelectBtn
@onready var title_label: Label = $TitleLabel
@onready var desc_label: Label = $DescLabel

const STARTERS = ["Bulbasaur", "Charmander", "Squirtle"]

func _ready() -> void:
	bulbasaur_btn.pressed.connect(_on_starter_chosen.bind("Bulbasaur"))
	charmander_btn.pressed.connect(_on_starter_chosen.bind("Charmander"))
	squirtle_btn.pressed.connect(_on_starter_chosen.bind("Squirtle"))
	
	# Update stat labels for each starter
	for starter in STARTERS:
		_update_starter_panel(starter)

func _update_starter_panel(species_name: String) -> void:
	var sd = PokemonData.get_species(species_name)
	if sd.is_empty():
		return
	var panel_name = species_name + "Panel"
	var panel = get_node_or_null("HBoxContainer/" + panel_name)
	if panel == null:
		return
	var name_lbl = panel.get_node_or_null("NameLabel")
	var stats_lbl = panel.get_node_or_null("StatsLabel")
	var type_lbl = panel.get_node_or_null("TypeLabel")
	var color_rect = panel.get_node_or_null("ColorRect")
	
	if name_lbl:
		name_lbl.text = species_name
	if stats_lbl:
		var moves = sd.get("available_attacks", [])
		var moves_preview = ", ".join(moves.slice(0, 2)) if moves.size() > 0 else ""
		stats_lbl.text = "HP: %d  ATK: %d\nDEF: %d  SPD: %d\nMoves: %s" % [
			sd["base_hp"] + 10,  # level 5 hp approx
			sd["base_attack"],
			sd["base_defense"],
			sd["base_speed"],
			moves_preview
		]
	if type_lbl:
		type_lbl.text = " / ".join(sd["types"])
	if color_rect:
		var sprite_tr = color_rect.get_node_or_null("SpriteTex") as TextureRect
		if sprite_tr == null:
			sprite_tr = TextureRect.new()
			sprite_tr.name = "SpriteTex"
			sprite_tr.layout_mode = 1
			sprite_tr.anchors_preset = Control.PRESET_FULL_RECT
			sprite_tr.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
			sprite_tr.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
			color_rect.add_child(sprite_tr)
		var p_tex = PokemonData.get_front_sprite_texture(species_name)
		if p_tex:
			sprite_tr.texture = p_tex
			color_rect.color = Color(0.15, 0.2, 0.28, 0.5)
		else:
			color_rect.color = PokemonData.get_species_color(species_name)

func _on_starter_chosen(species_name: String) -> void:
	var player_name = "Trainer"
	var avatar = "calem"
	if GameState.has_meta("pending_player_name"):
		player_name = GameState.get_meta("pending_player_name")
		GameState.remove_meta("pending_player_name")
	if GameState.has_meta("pending_trainer_avatar"):
		avatar = GameState.get_meta("pending_trainer_avatar")
		GameState.remove_meta("pending_trainer_avatar")
	
	GameState.new_game(player_name, species_name, avatar)
	get_tree().change_scene_to_file("res://scenes/World.tscn")
