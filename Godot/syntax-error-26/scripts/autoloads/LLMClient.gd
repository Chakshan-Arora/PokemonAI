extends Node
## LLMClient - Connects the Godot 3D Frontend to the local Fine-Tuned Pokémon LLM (Autoload)
## Communicates with http://127.0.0.1:8008 for companion dialogue and battle tactics.

const BASE_URL: String = "http://127.0.0.1:8008"
const TIMEOUT_SECONDS: float = 5.0

var is_server_online: bool = false
var _health_request: HTTPRequest = null

signal companion_replied(data: Dictionary)
signal battle_decision_ready(data: Dictionary)

func _ready() -> void:
	_health_request = HTTPRequest.new()
	_health_request.timeout = 2.0
	add_child(_health_request)
	_check_health()

func _check_health() -> void:
	var err = _health_request.request(BASE_URL + "/health")
	if err == OK:
		var res = await _health_request.request_completed
		var code = res[1]
		if code == 200:
			is_server_online = true
			print("[LLMClient] Connected to local Pokémon LLM server at ", BASE_URL)
		else:
			is_server_online = false
	else:
		is_server_online = false

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
	
	# Fallback response if LLM server is unreachable
	var fallback = {
		"species": species,
		"dialogue": "%s: *looks at %s attentively and chirps happily*" % [species, player_name],
		"emotional_state": "content",
		"trust_delta": 2.0,
		"affection_delta": 3.0,
		"new_trust": trust + 2.0,
		"new_affection": affection + 3.0
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

## Internal helper for asynchronous HTTP POST requests
func _post_json(url: String, data: Dictionary) -> Dictionary:
	var http = HTTPRequest.new()
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
