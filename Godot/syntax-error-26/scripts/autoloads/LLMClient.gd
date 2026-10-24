extends Node
## LLMClient - Connects the Godot 3D Frontend to the local Fine-Tuned Pokémon LLM and Backend API (Autoload)
## Communicates with http://127.0.0.1:8008 for companion dialogue, battle tactics, game data, and save state.

const BASE_URL: String = "http://127.0.0.1:8008"
const TIMEOUT_SECONDS: float = 25.0

var is_server_online: bool = false
var _health_request: HTTPRequest = null
var _health_timer: Timer = null

signal server_status_changed(is_online: bool)
signal companion_replied(data: Dictionary)
signal battle_decision_ready(data: Dictionary)

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	_health_request = HTTPRequest.new()
	_health_request.process_mode = Node.PROCESS_MODE_ALWAYS
	_health_request.timeout = 3.0
	add_child(_health_request)
	
	_health_timer = Timer.new()
	_health_timer.process_mode = Node.PROCESS_MODE_ALWAYS
	_health_timer.wait_time = 4.0
	_health_timer.autostart = true
	_health_timer.timeout.connect(_check_health)
	add_child(_health_timer)
	
	_check_health()

func _check_health() -> void:
	if not is_instance_valid(_health_request):
		return
	if _health_request.get_http_client_status() != HTTPClient.STATUS_DISCONNECTED:
		return
	var err = _health_request.request(BASE_URL + "/health")
	if err == OK:
		var res = await _health_request.request_completed
		var code = res[1]
		var was_online = is_server_online
		if code == 200:
			is_server_online = true
			if not was_online:
				print("[LLMClient] Connected to local Pokémon LLM server at ", BASE_URL)
				server_status_changed.emit(true)
		else:
			is_server_online = false
			if was_online:
				print("[LLMClient] Lost connection to Pokémon LLM server.")
				server_status_changed.emit(false)
	else:
		if is_server_online:
			is_server_online = false
			server_status_changed.emit(false)

## Fetches live game data (species, attacks, items, habitats, quests, personality traits) from Python backend
func fetch_backend_data() -> Dictionary:
	return await _get_json(BASE_URL + "/api/data")

## Saves game state through Python's authoritative SaveManager
func save_game_to_backend(save_dict: Dictionary) -> Dictionary:
	return await _post_json(BASE_URL + "/api/save", save_dict)

## Loads verified game state from Python's SaveManager
func load_game_from_backend() -> Dictionary:
	return await _get_json(BASE_URL + "/api/load")

## Generates wild Pokémon from Python backend HabitatManager with true species and personality traits
func generate_wild_pokemon(region_id: String, time_of_day: String = "day") -> Dictionary:
	var payload = {
		"region_id": region_id,
		"time_of_day": time_of_day
	}
	var res = await _post_json(BASE_URL + "/api/wild_encounter", payload)
	if res.has("pokemon") and res["pokemon"] is Dictionary:
		return res["pokemon"]
	return {}

## Creates a Pokémon instance using backend rules
func create_pokemon(species: String, level: int, nickname: String = "", personality: Dictionary = {}) -> Dictionary:
	var payload = {
		"species": species,
		"level": level,
		"nickname": nickname,
		"personality": personality
	}
	var res = await _post_json(BASE_URL + "/api/pokemon/create", payload)
	if res.has("pokemon") and res["pokemon"] is Dictionary:
		return res["pokemon"]
	return {}

## Requests a real-time partner Pokémon dialogue response from bonding_adapter
func talk_to_companion(species: String, message: String, player_name: String = "Trainer", trust: float = 30.0, affection: float = 30.0) -> Dictionary:
	var payload = {
		"species": species,
		"player_name": player_name,
		"message": message,
		"trust": trust,
		"affection": affection,
		"temperament": "bold"
	}
	
	var response = await _post_json(BASE_URL + "/companion/talk", payload)
	if not response.is_empty():
		companion_replied.emit(response)
		return response
	
	# Fallback response if LLM server is unreachable or timed out
	var fallback = {
		"species": species,
		"dialogue": "*swishes tail attentively* (Local LLM server is busy or offline. Please check terminal.)",
		"emotional_state": "thoughtful",
		"trust_delta": 0.0,
		"affection_delta": 0.0,
		"new_trust": trust,
		"new_affection": affection
	}
	companion_replied.emit(fallback)
	return fallback

## Requests tactical combat move and battle cry from battle_adapter
func decide_battle_action(active_pokemon_dict: Dictionary, opponent_pokemon_dict: Dictionary, is_trainer: bool = false, turn: int = 1) -> Dictionary:
	var payload = {
		"active_pokemon": active_pokemon_dict,
		"opponent_pokemon": opponent_pokemon_dict,
		"is_trainer_battle": is_trainer,
		"current_turn": turn
	}
	
	var response = await _post_json(BASE_URL + "/battle/decide", payload)
	if not response.is_empty():
		battle_decision_ready.emit(response)
		return response
	
	# Fallback if server unreachable
	var moves = active_pokemon_dict.get("known_moves", ["Tackle"])
	var fallback_move = moves[0] if not moves.is_empty() else "Tackle"
	var fallback = {
		"action_type": "attack",
		"chosen_move": fallback_move,
		"dialogue": "%s is focused on the battle!" % active_pokemon_dict.get("species", "Pokemon"),
		"emotional_state": "focused",
		"confidence": 0.5
	}
	battle_decision_ready.emit(fallback)
	return fallback

## Internal helper for asynchronous HTTP GET requests
func _get_json(url: String) -> Dictionary:
	var http = HTTPRequest.new()
	http.process_mode = Node.PROCESS_MODE_ALWAYS
	http.timeout = TIMEOUT_SECONDS
	add_child(http)
	
	var err = http.request(url)
	if err != OK:
		http.queue_free()
		return {}
	
	var result = await http.request_completed
	var resp_code = result[1]
	var body_bytes = result[3]
	http.queue_free()
	
	if resp_code == 200:
		is_server_online = true
		var body_str = body_bytes.get_string_from_utf8()
		var parsed = JSON.parse_string(body_str)
		if parsed is Dictionary:
			return parsed
	return {}

## Internal helper for asynchronous HTTP POST requests
func _post_json(url: String, data: Dictionary) -> Dictionary:
	var http = HTTPRequest.new()
	http.process_mode = Node.PROCESS_MODE_ALWAYS
	http.timeout = TIMEOUT_SECONDS
	add_child(http)
	
	var json_str = JSON.stringify(data)
	var headers = ["Content-Type: application/json"]
	
	var err = http.request(url, headers, HTTPClient.METHOD_POST, json_str)
	if err != OK:
		http.queue_free()
		return {}
	
	var result = await http.request_completed
	var resp_code = result[1]
	var body_bytes = result[3]
	http.queue_free()
	
	if resp_code == 200:
		is_server_online = true
		var body_str = body_bytes.get_string_from_utf8()
		var parsed = JSON.parse_string(body_str)
		if parsed is Dictionary:
			return parsed
	
	return {}
