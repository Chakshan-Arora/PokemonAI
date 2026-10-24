extends Control
## PokeMartUI - Vending machine shop interface for purchasing Poké Balls and Potions.

const ItemData = preload("res://scripts/data/ItemData.gd")

const POKEBALL_PRICE: int = 50
const POTION_PRICE: int = 150

@onready var wallet_label: Label = $Panel/VBox/Header/WalletLabel
@onready var feedback_label: Label = $Panel/VBox/FeedbackLabel
@onready var close_btn: Button = $Panel/VBox/Footer/CloseBtn

# Poké Ball card nodes
@onready var pokeball_icon: TextureRect = $Panel/VBox/ItemsContainer/PokeballCard/HBox/Icon
@onready var pokeball_name: Label = $Panel/VBox/ItemsContainer/PokeballCard/HBox/Details/NameLabel
@onready var pokeball_bag: Label = $Panel/VBox/ItemsContainer/PokeballCard/HBox/Details/BagLabel
@onready var btn_buy_ball_1: Button = $Panel/VBox/ItemsContainer/PokeballCard/HBox/Actions/Buy1Btn
@onready var btn_buy_ball_5: Button = $Panel/VBox/ItemsContainer/PokeballCard/HBox/Actions/Buy5Btn

# Potion card nodes
@onready var potion_icon: TextureRect = $Panel/VBox/ItemsContainer/PotionCard/HBox/Icon
@onready var potion_name: Label = $Panel/VBox/ItemsContainer/PotionCard/HBox/Details/NameLabel
@onready var potion_bag: Label = $Panel/VBox/ItemsContainer/PotionCard/HBox/Details/BagLabel
@onready var btn_buy_potion_1: Button = $Panel/VBox/ItemsContainer/PotionCard/HBox/Actions/Buy1Btn
@onready var btn_buy_potion_3: Button = $Panel/VBox/ItemsContainer/PotionCard/HBox/Actions/Buy3Btn

var _feedback_timer: float = 0.0

func _ready() -> void:
	add_to_group("pokemart_ui")
	visible = false
	process_mode = Node.PROCESS_MODE_ALWAYS
	
	EventBus.open_pokemart.connect(show_menu)
	
	close_btn.pressed.connect(hide_menu)
	
	btn_buy_ball_1.pressed.connect(func(): _buy_item("poke_ball", 1, POKEBALL_PRICE))
	btn_buy_ball_5.pressed.connect(func(): _buy_item("poke_ball", 5, POKEBALL_PRICE * 5))
	
	btn_buy_potion_1.pressed.connect(func(): _buy_item("potion", 1, POTION_PRICE))
	btn_buy_potion_3.pressed.connect(func(): _buy_item("potion", 3, POTION_PRICE * 3))
	
	# Load item icons
	var ball_tex = ItemData.get_item_texture("poke_ball")
	if ball_tex and is_instance_valid(pokeball_icon):
		pokeball_icon.texture = ball_tex
		
	var pot_tex = ItemData.get_item_texture("potion")
	if pot_tex and is_instance_valid(potion_icon):
		potion_icon.texture = pot_tex

func _input(event: InputEvent) -> void:
	if visible and event.is_action_pressed("ui_cancel"):
		hide_menu()
		get_viewport().set_input_as_handled()

func _process(delta: float) -> void:
	if visible and Input.mouse_mode != Input.MOUSE_MODE_VISIBLE:
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
		
	if _feedback_timer > 0.0:
		_feedback_timer -= delta
		if _feedback_timer <= 0.0 and is_instance_valid(feedback_label):
			feedback_label.text = ""

func show_menu() -> void:
	visible = true
	GameState.pause_game()
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	if is_instance_valid(feedback_label):
		feedback_label.text = "Select an item to purchase with your PokéDollars (p)."
		feedback_label.add_theme_color_override("font_color", Color(0.85, 0.9, 1.0))
	_update_ui()
	if is_instance_valid(btn_buy_ball_1):
		btn_buy_ball_1.grab_focus()

func hide_menu() -> void:
	visible = false
	GameState.resume_game()
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	EventBus.hud_update_requested.emit()

func _update_ui() -> void:
	if GameState.player == null:
		return
		
	var cur = GameState.player.currency
	if is_instance_valid(wallet_label):
		wallet_label.text = "Your Wallet: %dp" % cur
		
	var ball_count = GameState.player.get_item_count("poke_ball")
	if is_instance_valid(pokeball_bag):
		pokeball_bag.text = "In Bag: x%d" % ball_count
		
	var pot_count = GameState.player.get_item_count("potion")
	if is_instance_valid(potion_bag):
		potion_bag.text = "In Bag: x%d" % pot_count
		
	if is_instance_valid(btn_buy_ball_1):
		btn_buy_ball_1.disabled = (cur < POKEBALL_PRICE)
	if is_instance_valid(btn_buy_ball_5):
		btn_buy_ball_5.disabled = (cur < POKEBALL_PRICE * 5)
		
	if is_instance_valid(btn_buy_potion_1):
		btn_buy_potion_1.disabled = (cur < POTION_PRICE)
	if is_instance_valid(btn_buy_potion_3):
		btn_buy_potion_3.disabled = (cur < POTION_PRICE * 3)

func _buy_item(item_id: String, qty: int, total_cost: int) -> void:
	if GameState.player == null:
		return
		
	if not GameState.player.can_afford(total_cost):
		_show_feedback("Not enough money! You need %dp but only have %dp." % [total_cost, GameState.player.currency], false)
		return
		
	var iname = "Poké Ball" if item_id == "poke_ball" else "Potion"
	
	var ok = GameState.player.remove_currency(total_cost)
	if not ok:
		_show_feedback("Transaction failed: insufficient funds.", false)
		return
		
	GameState.player.add_item(item_id, qty)
	EventBus.currency_changed.emit(GameState.player.currency, -total_cost)
	EventBus.item_obtained.emit(item_id, qty)
	EventBus.hud_update_requested.emit()
	
	_show_feedback("Dispensed %dx %s for %dp! (Remaining: %dp)" % [qty, iname, total_cost, GameState.player.currency], true)
	_update_ui()

func _show_feedback(msg: String, success: bool) -> void:
	if not is_instance_valid(feedback_label):
		return
	feedback_label.text = msg
	if success:
		feedback_label.add_theme_color_override("font_color", Color(0.3, 0.95, 0.4))
	else:
		feedback_label.add_theme_color_override("font_color", Color(1.0, 0.35, 0.3))
	_feedback_timer = 3.5
