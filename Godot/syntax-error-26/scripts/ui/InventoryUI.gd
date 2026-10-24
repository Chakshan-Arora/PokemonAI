extends Control
## InventoryUI - Player item pouch and usable items screen

const ItemData = preload("res://scripts/data/ItemData.gd")

@onready var item_list: VBoxContainer = $Panel/HBox/ScrollContainer/VBoxContainer
@onready var item_name_lbl: Label = $Panel/HBox/DetailVBox/ItemNameLabel
@onready var item_desc_lbl: Label = $Panel/HBox/DetailVBox/ItemDescLabel
@onready var use_btn: Button = $Panel/HBox/DetailVBox/UseBtn
@onready var status_lbl: Label = $Panel/HBox/DetailVBox/StatusLabel
@onready var close_btn: Button = $Panel/CloseBtn

var _selected_item_id: String = ""

func _ready() -> void:
	add_to_group("inventory_ui")
	visible = false
	process_mode = Node.PROCESS_MODE_ALWAYS
	close_btn.pressed.connect(hide_menu)
	use_btn.pressed.connect(_on_use_pressed)

func _input(event: InputEvent) -> void:
	if visible and (event.is_action_pressed("open_inventory") or event.is_action_pressed("ui_cancel")):
		hide_menu()
		get_viewport().set_input_as_handled()

func show_menu() -> void:
	visible = true
	GameState.pause_game()
	_refresh_list()

func hide_menu() -> void:
	visible = false
	GameState.resume_game()
	EventBus.hud_update_requested.emit()

func _refresh_list() -> void:
	for child in item_list.get_children():
		child.queue_free()
	
	if GameState.player == null or GameState.player.inventory.is_empty():
		item_name_lbl.text = "Bag is empty"
		item_desc_lbl.text = "You do not have any items."
		use_btn.disabled = true
		return
	
	var first_item = ""
	for item_id in GameState.player.inventory:
		var qty = GameState.player.inventory[item_id]
		if qty <= 0:
			continue
		if first_item == "":
			first_item = item_id
		var idata = ItemData.get_item(item_id)
		var btn = Button.new()
		btn.text = "%s  x%d" % [idata.get("name", item_id), qty]
		btn.alignment = HORIZONTAL_ALIGNMENT_LEFT
		btn.pressed.connect(_select_item.bind(item_id))
		item_list.add_child(btn)
	
	if first_item != "":
		_select_item(first_item)
	else:
		item_name_lbl.text = "Bag is empty"
		item_desc_lbl.text = "You do not have any items."
		use_btn.disabled = true

func _select_item(item_id: String) -> void:
	_selected_item_id = item_id
	var idata = ItemData.get_item(item_id)
	item_name_lbl.text = idata.get("name", item_id)
	item_desc_lbl.text = idata.get("description", "")
	status_lbl.text = ""
	
	var effect = idata.get("effect", "")
	use_btn.disabled = not (effect == "heal" or effect == "full_restore")

func _on_use_pressed() -> void:
	if _selected_item_id == "" or GameState.player == null:
		return
	var active_p = GameState.get_active_pokemon()
	if active_p == null:
		status_lbl.text = "No active Pokemon."
		return
	
	var idata = ItemData.get_item(_selected_item_id)
	var category = idata.get("category", "")
	var effect_val = idata.get("effect_value", 0)
	
	if category == "healing":
		if active_p.current_hp >= active_p.max_hp:
			status_lbl.text = "%s's HP is already full!" % active_p.get_display_name()
			return
		if active_p.is_fainted():
			status_lbl.text = "%s is fainted! Cannot use healing item." % active_p.get_display_name()
			return
		
		var healed = active_p.heal(effect_val)
		GameState.player.remove_item(_selected_item_id, 1)
		status_lbl.text = "Restored %d HP to %s!" % [healed, active_p.get_display_name()]
		EventBus.pokemon_healed.emit(active_p)
		EventBus.hud_update_requested.emit()
		_refresh_list()
	elif category == "cure":
		if _selected_item_id == "full_restore":
			var healed = active_p.heal_full()
			GameState.player.remove_item(_selected_item_id, 1)
			status_lbl.text = "Fully restored %s! (Healed %d HP)" % [active_p.get_display_name(), healed]
			EventBus.pokemon_healed.emit(active_p)
			EventBus.hud_update_requested.emit()
			_refresh_list()
		else:
			status_lbl.text = "Used %s." % idata.get("name", _selected_item_id)
			GameState.player.remove_item(_selected_item_id, 1)
			_refresh_list()

