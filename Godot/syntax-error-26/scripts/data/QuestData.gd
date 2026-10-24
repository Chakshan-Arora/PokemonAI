class_name QuestData
extends Node
## QuestData - Quest definitions for PokémonAI

# objective types: "catch_pokemon", "defeat_trainer", "visit_region",
#                  "interact_object", "collect_item", "catch_count"

const QUESTS: Dictionary = {
	"q001_first_steps": {
		"quest_id": "q001_first_steps",
		"title": "First Steps",
		"description": "Professor Oak has asked you to explore the Starting Meadow.",
		"giver": "Professor Oak",
		"objectives": [
			{
				"objective_id": "obj_visit_meadow",
				"description": "Explore the Starting Meadow",
				"type": "visit_region",
				"target_id": "starting_meadow",
				"target": 1
			},
			{
				"objective_id": "obj_catch_first",
				"description": "Catch your first Pokémon",
				"type": "catch_count",
				"target_id": "",
				"target": 1
			}
		],
		"rewards": {"item_id": "potion", "quantity": 3, "xp": 100},
		"auto_start": true,
		"prerequisite_quests": []
	},
	"q002_bug_hunter": {
		"quest_id": "q002_bug_hunter",
		"title": "Bug Hunter",
		"description": "The forest is full of Bug Pokémon. Catch one of each!",
		"giver": "Field Trainer Koji",
		"objectives": [
			{
				"objective_id": "obj_catch_caterpie",
				"description": "Catch a Caterpie",
				"type": "catch_pokemon",
				"target_id": "Caterpie",
				"target": 1
			},
			{
				"objective_id": "obj_catch_butterfree",
				"description": "Catch a Butterfree",
				"type": "catch_pokemon",
				"target_id": "Butterfree",
				"target": 1
			},
			{
				"objective_id": "obj_visit_forest",
				"description": "Explore the Forest Trail",
				"type": "visit_region",
				"target_id": "forest_trail",
				"target": 1
			}
		],
		"rewards": {"item_id": "super_potion", "quantity": 2, "xp": 200},
		"auto_start": false,
		"prerequisite_quests": ["q001_first_steps"]
	},
	"q003_electric_surge": {
		"quest_id": "q003_electric_surge",
		"title": "Electric Surge",
		"description": "Catch a Pikachu from the Tall Grass Plains or Starting Meadow.",
		"giver": "Professor Oak",
		"objectives": [
			{
				"objective_id": "obj_catch_pikachu",
				"description": "Catch a Pikachu",
				"type": "catch_pokemon",
				"target_id": "Pikachu",
				"target": 1
			},
			{
				"objective_id": "obj_visit_shrine",
				"description": "Visit the Thunder Stone Shrine",
				"type": "interact_object",
				"target_id": "thunder_stone_shrine",
				"target": 1
			}
		],
		"rewards": {"item_id": "full_restore", "quantity": 1, "xp": 300},
		"auto_start": false,
		"prerequisite_quests": ["q001_first_steps"]
	},
	"q004_mountain_challenge": {
		"quest_id": "q004_mountain_challenge",
		"title": "Mountain Challenge",
		"description": "Prove your strength by defeating the trainer in Mountain Pass.",
		"giver": "Field Trainer Koji",
		"objectives": [
			{
				"objective_id": "obj_visit_mountain",
				"description": "Reach Mountain Pass",
				"type": "visit_region",
				"target_id": "mountain_pass",
				"target": 1
			},
			{
				"objective_id": "obj_defeat_koji",
				"description": "Defeat Field Trainer Koji",
				"type": "defeat_trainer",
				"target_id": "field_trainer_koji",
				"target": 1
			}
		],
		"rewards": {"item_id": "super_potion", "quantity": 3, "xp": 400},
		"auto_start": false,
		"prerequisite_quests": ["q002_bug_hunter"]
	},
	"q005_ghost_hunter": {
		"quest_id": "q005_ghost_hunter",
		"title": "Ghost Hunter",
		"description": "Investigate the Haunted Ruins and catch a Ghost-type Pokémon.",
		"giver": "Professor Oak",
		"objectives": [
			{
				"objective_id": "obj_visit_ruins",
				"description": "Enter the Haunted Ruins",
				"type": "visit_region",
				"target_id": "haunted_ruins",
				"target": 1
			},
			{
				"objective_id": "obj_catch_gastly",
				"description": "Catch a Gastly",
				"type": "catch_pokemon",
				"target_id": "Gastly",
				"target": 1
			}
		],
		"rewards": {"item_id": "poke_ball", "quantity": 5, "xp": 350},
		"auto_start": false,
		"prerequisite_quests": ["q001_first_steps"]
	},
	"q006_pokemon_collector": {
		"quest_id": "q006_pokemon_collector",
		"title": "Pokémon Collector",
		"description": "Catch 10 different Pokémon species to build your collection.",
		"giver": "Professor Oak",
		"objectives": [
			{
				"objective_id": "obj_catch_10",
				"description": "Catch 10 Pokémon",
				"type": "catch_count",
				"target_id": "",
				"target": 10
			}
		],
		"rewards": {"item_id": "full_restore", "quantity": 2, "xp": 500},
		"auto_start": false,
		"prerequisite_quests": ["q002_bug_hunter"]
	}
}

static func get_quest(quest_id: String) -> Dictionary:
	if QUESTS.has(quest_id):
		return QUESTS[quest_id]
	return {}

static func get_all_quest_ids() -> Array:
	return QUESTS.keys()

static func get_auto_start_quests() -> Array:
	var result = []
	for qid in QUESTS:
		if QUESTS[qid].get("auto_start", false):
			result.append(qid)
	return result
