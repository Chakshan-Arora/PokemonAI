class_name WorldMap
extends Node
## WorldMap - Helper for world coordinate mapping and region queries

## Convert Python (x,y) coordinates to Godot 3D world (x, 0, z)
static func python_to_godot(px: float, py: float) -> Vector3:
	return Vector3(px * 10.0, 0.0, py * 10.0)

## Convert Godot 3D to Python coordinates
static func godot_to_python(world_pos: Vector3) -> Vector2:
	return Vector2(world_pos.x / 10.0, world_pos.z / 10.0)

## Get world object definitions (positions, types, etc.)
static func get_world_objects() -> Array:
	return [
		{
			"object_id": "berry_bush",
			"object_name": "Berry Bush",
			"object_type": "resource",
			"position": python_to_godot(5, 5),
			"region": "starting_meadow",
			"rewards": [{"item_id": "potion", "quantity": 1}],
			"interaction_text": "You found some berries! Received 1 Potion.",
			"respawn_duration": 60.0,
			"is_one_time": false,
			"color": "#55AA33"
		},
		{
			"object_id": "supply_cache",
			"object_name": "Supply Cache",
			"object_type": "treasure",
			"position": python_to_godot(15, 10),
			"region": "forest_trail",
			"rewards": [
				{"item_id": "super_potion", "quantity": 1},
				{"item_id": "antidote", "quantity": 2}
			],
			"interaction_text": "You found a hidden cache! Received 1 Super Potion and 2 Antidotes.",
			"respawn_duration": 0.0,
			"is_one_time": true,
			"color": "#AA8833"
		},
		{
			"object_id": "route1_sign",
			"object_name": "Route 1 Sign",
			"object_type": "sign",
			"position": python_to_godot(2, 1),
			"region": "starting_meadow",
			"rewards": [],
			"interaction_text": "Route 1: Pathway to Viridian City. Wild Pokémon dwell in the tall grass!",
			"respawn_duration": 0.0,
			"is_one_time": false,
			"color": "#AA7755"
		},
		{
			"object_id": "thunder_stone_shrine",
			"object_name": "Thunder Stone Shrine",
			"object_type": "landmark",
			"position": python_to_godot(25, 25),
			"region": "ancient_shrine_grounds",
			"rewards": [],
			"interaction_text": "An ancient shrine crackling with electrical energy. Legends say it grants power to Electric Pokémon.",
			"respawn_duration": 0.0,
			"is_one_time": false,
			"color": "#FFDD00"
		},
		{
			"object_id": "professor_oak",
			"object_name": "Professor Oak",
			"object_type": "npc",
			"position": python_to_godot(2.5, 1.5),
			"region": "starting_meadow",
			"rewards": [],
			"interaction_text": "Welcome, young trainer! The world of Pokémon awaits you. Explore, catch, and battle to become the best!",
			"respawn_duration": 0.0,
			"is_one_time": false,
			"color": "#DDBB88"
		},
		{
			"object_id": "field_trainer_koji",
			"object_name": "Field Trainer Koji",
			"object_type": "npc_trainer",
			"position": python_to_godot(15, 10),
			"region": "forest_trail",
			"rewards": [],
			"interaction_text": "I am Trainer Koji! I challenge all who pass through! Prepare for battle!",
			"respawn_duration": 0.0,
			"is_one_time": false,
			"color": "#FF5544"
		}
	]
