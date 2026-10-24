extends Control
## QuestJournalUI - Shows active and completed quests, progress, and objectives

const QuestData = preload("res://scripts/data/QuestData.gd")
const ItemData = preload("res://scripts/data/ItemData.gd")

@onready var active_tab_btn: Button = $Panel/VBox/TabBar/ActiveBtn
@onready var completed_tab_btn: Button = $Panel/VBox/TabBar/CompletedBtn
@onready var quest_list: VBoxContainer = $Panel/VBox/HBox/Scroll/VBox
@onready var title_lbl: Label = $Panel/VBox/HBox/DetailVBox/TitleLabel
@onready var desc_lbl: Label = $Panel/VBox/HBox/DetailVBox/DescLabel
@onready var objectives_lbl: Label = $Panel/VBox/HBox/DetailVBox/ObjectivesLabel
@onready var rewards_lbl: Label = $Panel/VBox/HBox/DetailVBox/RewardsLabel
@onready var close_btn: Button = $Panel/CloseBtn

var _showing_active: bool = true

func _ready() -> void:
	add_to_group("quest_journal")
	visible = false
	process_mode = Node.PROCESS_MODE_ALWAYS
	close_btn.pressed.connect(hide_menu)
	active_tab_btn.pressed.connect(_switch_tab.bind(true))
	completed_tab_btn.pressed.connect(_switch_tab.bind(false))

func _input(event: InputEvent) -> void:
	if visible and (event.is_action_pressed("open_quests") or event.is_action_pressed("ui_cancel")):
		hide_menu()
		get_viewport().set_input_as_handled()

func _process(_delta: float) -> void:
	if visible and Input.mouse_mode != Input.MOUSE_MODE_VISIBLE:
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE

func show_menu() -> void:
	visible = true
	GameState.pause_game()
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	_refresh_list()

func hide_menu() -> void:
	visible = false
	GameState.resume_game()
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE

func _switch_tab(active_tab: bool) -> void:
	_showing_active = active_tab
	_refresh_list()

func _refresh_list() -> void:
	for child in quest_list.get_children():
		child.queue_free()
	
	if GameState.player == null:
		return
	
	var list_to_show = GameState.player.active_quests if _showing_active else GameState.player.completed_quests
	
	if list_to_show.is_empty():
		title_lbl.text = "No " + ("Active" if _showing_active else "Completed") + " Quests"
		desc_lbl.text = ""
		objectives_lbl.text = ""
		rewards_lbl.text = ""
		return
	
	for q_id in list_to_show:
		var q_data = QuestData.get_quest(q_id)
		var btn = Button.new()
		btn.text = q_data.get("title", q_id)
		btn.alignment = HORIZONTAL_ALIGNMENT_LEFT
		btn.pressed.connect(_select_quest.bind(q_id))
		quest_list.add_child(btn)
	
	_select_quest(list_to_show[0])

func _select_quest(quest_id: String) -> void:
	var q_data = QuestData.get_quest(quest_id)
	title_lbl.text = q_data.get("title", quest_id)
	desc_lbl.text = q_data.get("description", "")
	
	var obj_text = "Objectives:\n"
	var p_prog = GameState.player.quest_progress.get(quest_id, {})
	for obj in q_data.get("objectives", []):
		var o_id = obj.get("objective_id", obj.get("id", ""))
		var o_desc = obj.get("description", "")
		var target = obj.get("target", obj.get("target_count", 1))
		var current = p_prog.get(o_id, 0)
		var check = "[X] " if current >= target else "[ ] "
		obj_text += " %s%s (%d/%d)\n" % [check, o_desc, current, target]
	objectives_lbl.text = obj_text
	
	var r_text = "Rewards:\n"
	var rew = q_data.get("rewards", {})
	if rew.has("xp"):
		r_text += " • %d XP\n" % rew["xp"]
	if rew.has("item_id"):
		var idata = ItemData.get_item(rew["item_id"])
		r_text += " • %dx %s\n" % [rew.get("quantity", 1), idata.get("name", rew["item_id"])]
	elif rew.has("items"):
		for item_id in rew["items"]:
			var idata = ItemData.get_item(item_id)
			r_text += " • %dx %s\n" % [rew["items"][item_id], idata.get("name", item_id)]
	rewards_lbl.text = r_text

