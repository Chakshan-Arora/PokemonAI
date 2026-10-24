extends Node
## EventBus - Decoupled signal communication hub for the entire game.

# Battle signals
signal battle_started(player_pokemon, wild_pokemon, is_trainer_battle)
signal battle_ended(result)  # "victory", "defeat", "escaped", "captured"
signal battle_turn_resolved(turn_data)

# Pokemon signals
signal pokemon_caught(pokemon)
signal level_up(pokemon, old_level, new_level)
signal pokemon_fainted(pokemon)
signal pokemon_healed(pokemon)
signal pokemon_status_applied(pokemon, status)
signal pokemon_status_cleared(pokemon, status)

# Player signals
signal player_moved(position)
signal interaction_triggered(object_id)
signal player_entered_region(region_id, region_name)
signal player_exited_region(region_id)

# Quest signals
signal quest_started(quest_id)
signal quest_updated(quest_id, objective_id, progress, target)
signal quest_completed(quest_id)

# World signals
signal region_discovered(region_id, region_name)
signal landmark_discovered(landmark_id, landmark_name)
signal item_obtained(item_id, quantity)
signal world_object_interacted(object_id, object_type)
signal world_object_respawned(object_id)

# UI signals
signal save_requested()
signal load_requested()
signal starter_chosen(pokemon)
signal show_message(text)
signal hud_update_requested()
signal open_party_menu()
signal open_inventory_ui()
signal open_quest_journal()
signal open_pause_menu()
signal close_all_menus()

# Encounter signals
signal wild_encounter_triggered(species_name, level)
signal trainer_encounter_triggered(trainer_id)
