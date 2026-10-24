"""
Save manager handling atomic serialization and deserialization of player game state.
Safely saves player progress to JSON, restores it into new independent objects,
validates payload integrity, and resolves catalog references without mutation.
"""
import os
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Union

from src.models.player import Player
from src.models.pokemon import Pokemon
from src.models.species import PokemonSpecies
from src.models.attack import Attack
from src.models.personality import Personality
from src.models.inventory import Inventory
from src.models.item import Item
from src.models.save_data import CURRENT_SCHEMA_VERSION, SaveDataError, validate_schema_version
from src.models.quest import QuestStatus, QuestProgress, ObjectiveProgress, QuestDefinition
from src.models.world_interaction import Interactable, InteractableType
from src.models.world_exploration import WorldRegion
from src.data.items import ITEM_CATALOG, get_item
from src.data.quests import QUEST_CATALOG
from src.data.world_objects import WORLD_OBJECT_CATALOG
from src.data.world_regions import WORLD_REGION_CATALOG


def serialize_player(player: Player) -> dict[str, Any]:
    """
    Serializes a Player instance and all associated persistent state into a JSON-compatible dict.

    Persistent fields preserved:
      - Player: name, unique_id, max_team_size
      - Inventory: capacity, items (item_id -> quantity)
      - Collection: complete list of owned Pokemon with individual stats, levels, XP,
                    HP, personality, bond, obedience, attacks, trained stats, and awarded moves.
      - Team: ordered list of Pokemon unique IDs belonging to the active team.
      - Active Pokemon: unique ID of the currently active Pokemon (or None).

    Transient fields intentionally excluded:
      - Active battle state, turn number, speed order, combat action records, combat event logs.
      - Volatile battle-only status effects and stat reductions (HP is preserved; combat effects reset).
      - Live manager instances, RNG seeds, and runtime process state.

    Args:
        player: The Player instance to serialize.

    Returns:
        A JSON-compatible dictionary conforming to schema version 1.

    Raises:
        SaveDataError: If player is invalid or serialization encounters unhandled state.
    """
    if not isinstance(player, Player):
        raise SaveDataError(f"Expected Player instance for serialization, got {type(player).__name__}.")

    try:
        # 1. Player Info
        player_data = {
            "name": player.name,
            "unique_id": player.unique_id,
            "max_team_size": player.max_team_size,
            "currency": player.currency,
        }

        # 2. Inventory
        inv = player.inventory
        # Sort items predictably by item_id
        sorted_items = {
            stack.item_id: stack.quantity for stack in inv.list_items()
        }
        inventory_data = {
            "capacity": inv.capacity,
            "items": sorted_items,
        }

        # 3. Collection (all owned Pokemon)
        collection_data: list[dict[str, Any]] = []
        for mon in player.collection:
            mon_record = {
                "unique_id": mon.unique_id,
                "species": mon.species.name,
                "nickname": mon.nickname,
                "level": mon.level,
                "experience": mon.experience,
                "current_hp": mon.current_hp,
                "bond": mon.bond,
                "obedience": mon.obedience,
                "personality": mon.personality.to_dict(),
                "attacks": [atk.name for atk in mon.attacks],
                "trained_stats": mon.trained_stats,
                "awarded_level_moves": [
                    [level, move_name] for level, move_name in mon.awarded_level_moves
                ],
            }
            collection_data.append(mon_record)

        # 4. Team (ordered list of unique IDs)
        team_data = [mon.unique_id for mon in player.team]

        # 5. Active Pokemon ID
        active_id = player.active_pokemon.unique_id if player.active_pokemon else None

        # 6. Quests (mapping quest_id -> serialized quest progress)
        quests_data: dict[str, Any] = {}
        for q_id, q_prog in sorted(player.quests.items(), key=lambda kv: kv[0]):
            if isinstance(q_prog, QuestProgress):
                obj_data = {
                    obj_id: {
                        "objective_id": op.objective_id,
                        "target_count": op.target_count,
                        "current_count": op.current_count,
                        "is_completed": op.is_completed,
                    }
                    for obj_id, op in sorted(q_prog.objective_progress.items(), key=lambda kv: kv[0])
                }
                quests_data[q_id] = {
                    "quest_id": q_prog.quest_id,
                    "status": q_prog.status.value,
                    "is_completed": q_prog.is_completed,
                    "rewards_claimed": q_prog.rewards_claimed,
                    "objective_progress": obj_data,
                    "selected_choices": dict(q_prog.selected_choices),
                }
            elif isinstance(q_prog, dict):
                quests_data[q_id] = q_prog

        # 7. World Interaction: Collected Treasures
        collected_treasures_data = sorted(list(player.collected_treasures))

        # 8. World Exploration: Discovered Regions & Landmarks
        discovered_regions_data = sorted(list(player.discovered_regions))
        discovered_landmarks_data = sorted(list(player.discovered_landmarks))

        # 9. Wild Encounter Action History
        wild_history_data = [
            dict(item) for item in getattr(player, "wild_action_history", [])
        ]

        return {
            "schema_version": CURRENT_SCHEMA_VERSION,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "player": player_data,
            "inventory": inventory_data,
            "collection": collection_data,
            "team": team_data,
            "active_pokemon_id": active_id,
            "quests": quests_data,
            "collected_treasures": collected_treasures_data,
            "discovered_regions": discovered_regions_data,
            "discovered_landmarks": discovered_landmarks_data,
            "wild_action_history": wild_history_data,
        }
    except Exception as e:
        if isinstance(e, SaveDataError):
            raise
        raise SaveDataError(f"Failed to serialize player: {e}") from e


def deserialize_player(
    data: dict[str, Any],
    species_catalog: Optional[dict[str, PokemonSpecies]] = None,
    attack_catalog: Optional[dict[str, Attack]] = None,
    item_catalog: Optional[dict[str, Item]] = None,
    quest_catalog: Optional[dict[str, QuestDefinition]] = None,
    world_objects_catalog: Optional[dict[str, Interactable]] = None,
    region_catalog: Optional[dict[str, WorldRegion]] = None,
) -> Player:
    """
    Reconstructs an independent Player instance from a validated JSON dictionary.

    Restoration rules:
      - Strictly validates schema version and all required fields.
      - Resolves species, attack, item, quest, and world object references from catalogs.
      - Restores exact unique IDs for player and Pokémon.
      - Guarantees object identity: team members and active Pokémon refer to the exact same
        instances present in the player collection.
      - Fails cleanly and atomically on invalid or corrupt save data.

    Args:
        data: JSON dictionary loaded from save file.
        species_catalog: Optional custom species catalog mapping name -> PokemonSpecies.
        attack_catalog: Optional custom attack catalog mapping name -> Attack.
        item_catalog: Optional custom item catalog mapping item_id -> Item.
        quest_catalog: Optional custom quest catalog mapping quest_id -> QuestDefinition.
        world_objects_catalog: Optional custom world objects catalog mapping object_id -> Interactable.
        region_catalog: Optional custom region catalog mapping region_id -> WorldRegion.

    Returns:
        A fully reconstructed, isolated Player instance.

    Raises:
        SaveDataError: If payload is malformed, missing fields, or contains invalid values.
    """
    if not isinstance(data, dict):
        raise SaveDataError(f"Save data payload must be a dictionary, got {type(data).__name__}.")

    # Validate Schema Version
    version = validate_schema_version(data.get("schema_version"))

    # Catalog lookups
    if species_catalog is not None:
        species_cat = species_catalog
    else:
        from src.data.species import SAMPLE_SPECIES
        species_cat = SAMPLE_SPECIES

    if attack_catalog is not None:
        attack_cat = attack_catalog
    else:
        from src.data.attacks import SAMPLE_ATTACKS
        attack_cat = SAMPLE_ATTACKS
    item_cat = item_catalog if item_catalog is not None else ITEM_CATALOG
    quest_cat = quest_catalog if quest_catalog is not None else QUEST_CATALOG
    world_cat = world_objects_catalog if world_objects_catalog is not None else WORLD_OBJECT_CATALOG
    region_cat = region_catalog if region_catalog is not None else WORLD_REGION_CATALOG

    # Verify required top-level sections
    req_sections = ["player", "inventory", "collection", "team"]
    if version >= 2:
        req_sections.append("quests")
    if version >= 3:
        req_sections.append("collected_treasures")
    if version >= 4:
        req_sections.append("discovered_regions")
        req_sections.append("discovered_landmarks")

    for req_key in req_sections:
        if req_key not in data:
            raise SaveDataError(f"Missing required section '{req_key}' in save data.")

    # 1. Reconstruct Player Identity
    p_info = data["player"]
    if not isinstance(p_info, dict):
        raise SaveDataError("Player section must be a dictionary.")

    name = p_info.get("name")
    if not isinstance(name, str) or not name.strip():
        raise SaveDataError(f"Invalid player name in save data: {name!r}.")

    player_id = p_info.get("unique_id")
    if not isinstance(player_id, str) or not player_id.strip():
        raise SaveDataError(f"Invalid player unique_id in save data: {player_id!r}.")

    max_team_size = p_info.get("max_team_size", 6)
    if not isinstance(max_team_size, int) or isinstance(max_team_size, bool) or max_team_size < 1:
        raise SaveDataError(f"Invalid max_team_size in save data: {max_team_size}.")

    # 2. Reconstruct Inventory
    inv_data = data["inventory"]
    if not isinstance(inv_data, dict):
        raise SaveDataError("Inventory section must be a dictionary.")

    capacity = inv_data.get("capacity")
    if capacity is not None and (not isinstance(capacity, int) or isinstance(capacity, bool) or capacity < 1):
        raise SaveDataError(f"Invalid inventory capacity in save data: {capacity}.")

    try:
        inventory = Inventory(capacity=capacity, catalog=item_cat)
    except Exception as e:
        raise SaveDataError(f"Failed to initialize inventory: {e}") from e

    items_dict = inv_data.get("items", {})
    if not isinstance(items_dict, dict):
        raise SaveDataError("Inventory items must be a dictionary mapping item_id to quantity.")

    for item_id, quantity in items_dict.items():
        if not isinstance(item_id, str) or not item_id.strip():
            raise SaveDataError(f"Invalid item ID in inventory save data: {item_id!r}.")
        norm_item_id = item_id.strip().lower()
        if norm_item_id not in item_cat and get_item(norm_item_id) is None:
            raise SaveDataError(f"Unknown item '{item_id}' in inventory save data.")

        if isinstance(quantity, float):
            quantity = int(round(quantity))

        if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity <= 0:
            raise SaveDataError(f"Invalid quantity {quantity} for item '{item_id}' in save data.")

        success = inventory.add_item(norm_item_id, quantity)
        if not success:
            raise SaveDataError(
                f"Failed to restore item '{item_id}' (qty: {quantity}): {inventory.last_message}"
            )

    # Construct Player with restored inventory
    raw_currency = p_info.get("currency", data.get("currency", 500))
    currency = int(raw_currency) if isinstance(raw_currency, (int, float)) and not isinstance(raw_currency, bool) and raw_currency >= 0 else 500

    try:
        player = Player(
            name=name,
            unique_id=player_id,
            max_team_size=max_team_size,
            inventory=inventory,
            currency=currency,
        )
    except Exception as e:
        raise SaveDataError(f"Failed to instantiate Player: {e}") from e

    # 3. Reconstruct Collection
    raw_collection = data["collection"]
    if not isinstance(raw_collection, list):
        raise SaveDataError("Collection section must be a list of Pokemon records.")

    seen_pokemon_ids: set[str] = set()
    restored_pokemon_map: dict[str, Pokemon] = {}

    for idx, mon_data in enumerate(raw_collection):
        if not isinstance(mon_data, dict):
            raise SaveDataError(f"Pokemon entry at index {idx} must be a dictionary.")

        # ID
        mon_id = mon_data.get("unique_id")
        if not isinstance(mon_id, str) or not mon_id.strip():
            raise SaveDataError(f"Pokemon at index {idx} is missing a valid 'unique_id'.")
        if mon_id in seen_pokemon_ids:
            raise SaveDataError(f"Duplicate Pokemon ID '{mon_id}' detected in collection save data.")
        seen_pokemon_ids.add(mon_id)

        # Species resolution
        species_name = mon_data.get("species")
        if not isinstance(species_name, str) or not species_name.strip():
            raise SaveDataError(f"Pokemon '{mon_id}' is missing a valid 'species' name.")

        # Case-insensitive species lookup
        species_obj = None
        for k, v in species_cat.items():
            if k.strip().lower() == species_name.strip().lower() or v.name.strip().lower() == species_name.strip().lower():
                species_obj = v
                break
        if species_obj is None:
            raise SaveDataError(f"Unknown species '{species_name}' for Pokemon '{mon_id}'.")

        # Personality
        pers_data = mon_data.get("personality")
        if not isinstance(pers_data, dict):
            raise SaveDataError(f"Pokemon '{mon_id}' is missing personality data dictionary.")
        try:
            personality_obj = Personality(
                aggression=pers_data["aggression"],
                curiosity=pers_data["curiosity"],
                fear=pers_data["fear"],
                sociability=pers_data["sociability"],
                loyalty=pers_data["loyalty"],
                confidence=pers_data["confidence"],
            )
        except (KeyError, TypeError, ValueError) as e:
            raise SaveDataError(f"Malformed personality data for Pokemon '{mon_id}': {e}") from e

        # Level & Experience
        level = mon_data.get("level")
        if not isinstance(level, int) or isinstance(level, bool) or level < 1:
            raise SaveDataError(f"Invalid level {level} for Pokemon '{mon_id}'.")

        experience = mon_data.get("experience", 0)
        if not isinstance(experience, int) or isinstance(experience, bool) or experience < 0:
            raise SaveDataError(f"Invalid experience {experience} for Pokemon '{mon_id}'.")

        # Bond & Obedience
        bond = mon_data.get("bond", 0)
        if isinstance(bond, float):
            bond = int(round(bond))
        if not isinstance(bond, int) or isinstance(bond, bool) or not (0 <= bond <= 100):
            raise SaveDataError(f"Invalid bond value {bond} for Pokemon '{mon_id}'.")

        obedience = mon_data.get("obedience", 100)
        if isinstance(obedience, float):
            obedience = int(round(obedience))
        if not isinstance(obedience, int) or isinstance(obedience, bool) or not (0 <= obedience <= 100):
            raise SaveDataError(f"Invalid obedience value {obedience} for Pokemon '{mon_id}'.")

        # Attacks
        raw_attacks = mon_data.get("attacks", [])
        if not isinstance(raw_attacks, list):
            raise SaveDataError(f"Attacks for Pokemon '{mon_id}' must be a list.")
        attack_objs: list[Attack] = []
        for atk_name in raw_attacks:
            if not isinstance(atk_name, str):
                raise SaveDataError(f"Invalid attack name {atk_name!r} in Pokemon '{mon_id}'.")
            found_atk = None
            for k, v in attack_cat.items():
                if k.strip().lower() == atk_name.strip().lower() or v.name.strip().lower() == atk_name.strip().lower():
                    found_atk = v
                    break
            if found_atk is None:
                raise SaveDataError(f"Unknown attack '{atk_name}' for Pokemon '{mon_id}'.")
            attack_objs.append(found_atk)

        # Trained Stats
        trained_stats = mon_data.get("trained_stats", {"attack": 0, "defense": 0, "speed": 0})
        if not isinstance(trained_stats, dict):
            raise SaveDataError(f"trained_stats for Pokemon '{mon_id}' must be a dictionary.")

        # Construct Pokemon instance
        nickname = mon_data.get("nickname")
        try:
            pokemon = Pokemon(
                species=species_obj,
                personality=personality_obj,
                unique_id=mon_id,
                level=level,
                experience=experience,
                bond=bond,
                obedience=obedience,
                nickname=nickname,
                attacks=attack_objs,
                trained_stats=trained_stats,
            )
        except Exception as e:
            raise SaveDataError(f"Failed to instantiate Pokemon '{mon_id}': {e}") from e

        # Current HP
        current_hp = mon_data.get("current_hp")
        if current_hp is not None:
            if not isinstance(current_hp, int) or isinstance(current_hp, bool) or current_hp < 0:
                raise SaveDataError(f"Invalid current_hp {current_hp} for Pokemon '{mon_id}'.")
            if current_hp > pokemon.max_hp:
                raise SaveDataError(
                    f"current_hp ({current_hp}) exceeds maximum HP ({pokemon.max_hp}) for Pokemon '{mon_id}'."
                )
            pokemon.current_hp = current_hp

        # Awarded level-up moves
        awarded_moves = mon_data.get("awarded_level_moves", [])
        if isinstance(awarded_moves, list):
            for entry in awarded_moves:
                if isinstance(entry, (list, tuple)) and len(entry) == 2:
                    m_lvl, m_name = entry
                    if isinstance(m_lvl, int) and isinstance(m_name, str):
                        pokemon.mark_level_move_awarded(m_lvl, m_name)

        restored_pokemon_map[mon_id] = pokemon
        player.add_pokemon(pokemon)

    # 4. Reconstruct Team
    raw_team = data["team"]
    if not isinstance(raw_team, list):
        raise SaveDataError("Team section must be a list of Pokemon IDs.")

    if len(raw_team) > player.max_team_size:
        raise SaveDataError(
            f"Team size ({len(raw_team)}) exceeds maximum team size ({player.max_team_size})."
        )

    team_seen: set[str] = set()
    for team_id in raw_team:
        if not isinstance(team_id, str):
            raise SaveDataError(f"Invalid team Pokemon ID {team_id!r}.")
        if team_id in team_seen:
            raise SaveDataError(f"Duplicate Pokemon ID '{team_id}' in team specification.")
        team_seen.add(team_id)

        target_mon = restored_pokemon_map.get(team_id)
        if target_mon is None:
            raise SaveDataError(
                f"Team Pokemon ID '{team_id}' not found in player collection."
            )
        player.add_to_team(target_mon)

    # 5. Reconstruct Active Pokemon Selection
    active_id = data.get("active_pokemon_id")
    if active_id is not None:
        if not isinstance(active_id, str):
            raise SaveDataError(f"Invalid active_pokemon_id {active_id!r}.")
        active_mon = restored_pokemon_map.get(active_id)
        if active_mon is None:
            raise SaveDataError(
                f"Active Pokemon ID '{active_id}' not found in player collection."
            )
        if not player.is_on_team(active_mon):
            raise SaveDataError(
                f"Active Pokemon '{active_mon.display_name}' (ID: {active_id}) must belong to the active team."
            )
        player.set_active_pokemon(active_mon)

    # 6. Reconstruct Quests (Schema v2, with backward compatibility for v1)
    raw_quests = data.get("quests", {})
    if not isinstance(raw_quests, dict):
        raise SaveDataError("Quests section must be a dictionary.")

    restored_quests: dict[str, QuestProgress] = {}

    for q_id, q_record in raw_quests.items():
        if not isinstance(q_id, str) or not q_id.strip():
            raise SaveDataError(f"Invalid quest ID in save data: {q_id!r}.")
        norm_qid = q_id.strip().lower()
        quest_def = quest_cat.get(norm_qid)
        if quest_def is None:
            raise SaveDataError(f"Unknown quest '{q_id}' in save data.")

        if not isinstance(q_record, dict):
            raise SaveDataError(f"Quest data for '{q_id}' must be a dictionary.")

        raw_status = q_record.get("status")
        try:
            if isinstance(raw_status, str):
                try:
                    status = QuestStatus(raw_status)
                except ValueError:
                    status = QuestStatus(raw_status.lower())
            else:
                status = QuestStatus(raw_status)
        except (ValueError, TypeError):
            raise SaveDataError(f"Invalid quest status '{raw_status}' for quest '{q_id}'.")

        is_completed = q_record.get("is_completed", False)
        if not isinstance(is_completed, bool):
            raise SaveDataError(f"Invalid is_completed for quest '{q_id}'.")

        rewards_claimed = q_record.get("rewards_claimed", False)
        if not isinstance(rewards_claimed, bool):
            raise SaveDataError(f"Invalid rewards_claimed for quest '{q_id}'.")

        raw_obj_data = q_record.get("objective_progress", {})
        if not isinstance(raw_obj_data, dict):
            raise SaveDataError(f"Invalid objective_progress for quest '{q_id}'.")

        # Selected choices restoration
        raw_choices_data = q_record.get("selected_choices", {})
        if not isinstance(raw_choices_data, dict):
            raise SaveDataError(f"Invalid selected_choices for quest '{q_id}'.")

        restored_choices: dict[str, str] = {}
        for c_id, opt_id in raw_choices_data.items():
            if not isinstance(c_id, str) or not isinstance(opt_id, str):
                raise SaveDataError(f"Malformed choice entry ({c_id!r}: {opt_id!r}) in quest '{q_id}' save data.")
            norm_cid = c_id.strip().lower()
            norm_optid = opt_id.strip().lower()
            choice_def = quest_def.get_choice(norm_cid)
            if choice_def is None:
                raise SaveDataError(f"Unknown choice '{c_id}' in quest '{q_id}' save data.")
            opt_def = choice_def.get_option(norm_optid)
            if opt_def is None:
                raise SaveDataError(f"Unknown option '{opt_id}' for choice '{c_id}' in quest '{q_id}' save data.")
            restored_choices[norm_cid] = norm_optid

        def_objs = {obj.objective_id: obj for obj in quest_def.get_all_objectives()}
        restored_obj_map: dict[str, ObjectiveProgress] = {}

        for obj_id, obj_rec in raw_obj_data.items():
            if obj_id not in def_objs:
                raise SaveDataError(f"Unknown objective '{obj_id}' in quest '{q_id}' save data.")
            if not isinstance(obj_rec, dict):
                raise SaveDataError(f"Objective data for '{obj_id}' must be a dictionary.")

            target_obj = def_objs[obj_id]
            curr_count = obj_rec.get("current_count", 0)
            if not isinstance(curr_count, int) or isinstance(curr_count, bool) or curr_count < 0:
                raise SaveDataError(f"Invalid current_count for objective '{obj_id}'.")

            restored_obj_map[obj_id] = ObjectiveProgress(
                objective_id=obj_id,
                target_count=target_obj.target_count,
                current_count=curr_count,
            )

        # Expected active objectives: base objectives + branch objectives of selected choices
        expected_active_objs = list(quest_def.objectives)
        for norm_cid, norm_optid in restored_choices.items():
            choice_def = quest_def.get_choice(norm_cid)
            if choice_def is not None:
                opt_def = choice_def.get_option(norm_optid)
                if opt_def is not None:
                    expected_active_objs.extend(opt_def.objectives)

        for obj in expected_active_objs:
            if obj.objective_id not in restored_obj_map:
                restored_obj_map[obj.objective_id] = ObjectiveProgress(
                    objective_id=obj.objective_id,
                    target_count=obj.target_count,
                    current_count=0,
                )

        qp = QuestProgress(
            quest_id=norm_qid,
            status=status,
            objective_progress=restored_obj_map,
            is_completed=is_completed,
            rewards_claimed=rewards_claimed,
            selected_choices=restored_choices,
        )
        has_pending = quest_def.has_choices() and any(
            not qp.has_selected_choice(ch.choice_id) for ch in quest_def.choices
        )
        if not has_pending and qp.is_all_objectives_completed():
            qp.is_completed = True
            if qp.status == QuestStatus.ACTIVE:
                qp.status = QuestStatus.COMPLETED

        restored_quests[norm_qid] = qp

    player.quests.update(restored_quests)

    # 7. Reconstruct Collected Treasures (Schema v3, backward-compatible migration for v1 & v2)
    raw_treasures = data.get("collected_treasures", [])
    if not isinstance(raw_treasures, (list, tuple, set)):
        raise SaveDataError("collected_treasures must be a list of treasure ID strings.")

    for t_id in raw_treasures:
        if not isinstance(t_id, str) or not t_id.strip():
            raise SaveDataError(f"Invalid treasure ID in save data: {t_id!r}.")
        norm_tid = t_id.strip().lower()
        if world_cat is not None:
            obj = world_cat.get(norm_tid)
            if obj is None:
                raise SaveDataError(f"Unknown collected treasure ID '{t_id}' in save data.")
            if obj.interactable_type != InteractableType.TREASURE:
                raise SaveDataError(
                    f"Object '{t_id}' in collected_treasures is of type {obj.interactable_type.value}, not treasure."
                )
        player.mark_treasure_collected(norm_tid)

    # 8. Reconstruct Discovered Regions & Landmarks (Schema v4, backward-compatible migration for v1, v2, v3)
    raw_regions = data.get("discovered_regions", [])
    if not isinstance(raw_regions, (list, tuple, set)):
        raise SaveDataError("discovered_regions must be a list of region ID strings.")

    for r_id in raw_regions:
        if not isinstance(r_id, str) or not r_id.strip():
            raise SaveDataError(f"Invalid region ID in save data: {r_id!r}.")
        norm_rid = r_id.strip().lower()
        if region_cat is not None:
            if norm_rid not in region_cat:
                raise SaveDataError(f"Unknown discovered region ID '{r_id}' in save data.")
        if world_cat is not None and norm_rid in world_cat and world_cat[norm_rid].interactable_type == InteractableType.LANDMARK:
            raise SaveDataError(f"Landmark ID '{r_id}' cannot appear as a discovered region ID.")
        player.mark_region_discovered(norm_rid)

    raw_landmarks = data.get("discovered_landmarks", [])
    if not isinstance(raw_landmarks, (list, tuple, set)):
        raise SaveDataError("discovered_landmarks must be a list of landmark ID strings.")

    for l_id in raw_landmarks:
        if not isinstance(l_id, str) or not l_id.strip():
            raise SaveDataError(f"Invalid landmark ID in save data: {l_id!r}.")
        norm_lid = l_id.strip().lower()
        if world_cat is not None:
            obj = world_cat.get(norm_lid)
            if obj is None:
                raise SaveDataError(f"Unknown discovered landmark ID '{l_id}' in save data.")
            if obj.interactable_type != InteractableType.LANDMARK:
                raise SaveDataError(
                    f"Object '{l_id}' in discovered_landmarks is of type {obj.interactable_type.value}, not landmark."
                )
        if region_cat is not None and norm_lid in region_cat:
            raise SaveDataError(f"Region ID '{l_id}' cannot appear as a discovered landmark ID.")
        player.mark_landmark_discovered(norm_lid)

    # 9. Reconstruct Wild Action History (Backward-compatible migration)
    raw_history = data.get("wild_action_history", [])
    if isinstance(raw_history, (list, tuple)):
        for h in raw_history:
            if isinstance(h, dict):
                player.record_wild_action(
                    action=h.get("action", ""),
                    is_aggressive=h.get("is_aggressive", False),
                    is_peaceful=h.get("is_peaceful", False),
                    species_name=h.get("species_name"),
                    outcome=h.get("outcome"),
                )

    return player


def save_game(player: Player, path: Union[str, Path]) -> None:
    """
    Serializes and atomically writes player game state to a JSON file at the specified path.

    Atomic guarantees:
      - Writes to a temporary file first in the destination directory.
      - Atomically renames/replaces the target file upon successful write.
      - Cleans up temporary artifacts upon error without corrupting any pre-existing save file.

    Args:
        player: The Player instance to save.
        path: Filepath where the save JSON should be stored.

    Raises:
        SaveDataError: If serialization, file creation, or atomic rename fails.
    """
    if not isinstance(player, Player):
        raise SaveDataError(f"Expected Player instance, got {type(player).__name__}.")

    target_path = Path(path)
    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        raise SaveDataError(f"Failed to create directory '{target_path.parent}': {e}") from e

    data = serialize_player(player)

    temp_path = target_path.parent / f".tmp_{target_path.name}_{uuid.uuid4().hex}"
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True, ensure_ascii=False)
        os.replace(temp_path, target_path)
    except Exception as e:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass
        raise SaveDataError(f"Failed to atomically write save file to '{target_path}': {e}") from e


def load_game(
    path: Union[str, Path],
    species_catalog: Optional[dict[str, PokemonSpecies]] = None,
    attack_catalog: Optional[dict[str, Attack]] = None,
    item_catalog: Optional[dict[str, Item]] = None,
    quest_catalog: Optional[dict[str, QuestDefinition]] = None,
    world_objects_catalog: Optional[dict[str, Interactable]] = None,
    region_catalog: Optional[dict[str, WorldRegion]] = None,
) -> Player:
    """
    Loads, validates, and reconstructs a Player instance from a save file.

    Args:
        path: Filepath to the save JSON file.
        species_catalog: Optional custom species catalog for resolution.
        attack_catalog: Optional custom attack catalog for resolution.
        item_catalog: Optional custom item catalog for resolution.
        quest_catalog: Optional custom quest catalog for resolution.
        world_objects_catalog: Optional custom world objects catalog for resolution.
        region_catalog: Optional custom region catalog for resolution.

    Returns:
        A completely reconstructed, isolated Player instance.

    Raises:
        SaveDataError: If the file does not exist, JSON is invalid, or payload validation fails.
    """
    target_path = Path(path)
    if not target_path.exists() or not target_path.is_file():
        raise SaveDataError(f"Save file not found at '{target_path}'.")

    try:
        with open(target_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise SaveDataError(f"Invalid JSON in save file '{target_path}': {e}") from e
    except Exception as e:
        raise SaveDataError(f"Failed to read save file '{target_path}': {e}") from e

    return deserialize_player(
        data=data,
        species_catalog=species_catalog,
        attack_catalog=attack_catalog,
        item_catalog=item_catalog,
        quest_catalog=quest_catalog,
        world_objects_catalog=world_objects_catalog,
        region_catalog=region_catalog,
    )


def save_game_with_ai(
    player: Player,
    path: Union[str, Path],
    ai_state: Optional[Any] = None,
    ai_state_path: Optional[Union[str, Path]] = None,
    trainer_manager: Optional[Any] = None,
    trainer_state_path: Optional[Union[str, Path]] = None,
) -> None:
    """
    Saves player game state and companion ai_state.json (and optional trainers.json) atomically.
    Synchronizes AI state with player collection.
    """
    from src.ai.persistence import save_ai_state, get_ai_state_path_for_save_file, AiState
    from src.models.trainer_manager import get_trainer_state_path_for_save_file

    save_game(player, path)
    if ai_state is not None:
        eff_ai_path = Path(ai_state_path) if ai_state_path is not None else get_ai_state_path_for_save_file(path)
        if hasattr(ai_state, "sync_with_player_collection"):
            ai_state.sync_with_player_collection(player)
        save_ai_state(ai_state, eff_ai_path)

    if trainer_manager is not None:
        eff_trainer_path = Path(trainer_state_path) if trainer_state_path is not None else get_trainer_state_path_for_save_file(path)
        if hasattr(trainer_manager, "save_to_file"):
            trainer_manager.save_to_file(eff_trainer_path)


def load_game_with_trainers(
    path: Union[str, Path],
    trainer_state_path: Optional[Union[str, Path]] = None,
    create_trainers_if_missing: bool = True,
    species_catalog: Optional[dict[str, PokemonSpecies]] = None,
    attack_catalog: Optional[dict[str, Attack]] = None,
    item_catalog: Optional[dict[str, Item]] = None,
    quest_catalog: Optional[dict[str, QuestDefinition]] = None,
    world_objects_catalog: Optional[dict[str, Interactable]] = None,
    region_catalog: Optional[dict[str, WorldRegion]] = None,
) -> tuple[Player, Any]:
    """
    Loads player game state and companion trainers.json.
    """
    from src.models.trainer_manager import (
        TrainerManager,
        get_trainer_state_path_for_save_file,
        create_default_trainer_manager,
    )

    player = load_game(
        path=path,
        species_catalog=species_catalog,
        attack_catalog=attack_catalog,
        item_catalog=item_catalog,
        quest_catalog=quest_catalog,
        world_objects_catalog=world_objects_catalog,
        region_catalog=region_catalog,
    )
    eff_path = Path(trainer_state_path) if trainer_state_path is not None else get_trainer_state_path_for_save_file(path)
    if eff_path.exists():
        trainer_manager = TrainerManager.load_from_file(eff_path)
    elif create_trainers_if_missing:
        trainer_manager = create_default_trainer_manager()
    else:
        trainer_manager = None

    return player, trainer_manager


def load_game_with_ai(
    path: Union[str, Path],
    ai_state_path: Optional[Union[str, Path]] = None,
    create_ai_if_missing: bool = True,
    species_catalog: Optional[dict[str, PokemonSpecies]] = None,
    attack_catalog: Optional[dict[str, Attack]] = None,
    item_catalog: Optional[dict[str, Item]] = None,
    quest_catalog: Optional[dict[str, QuestDefinition]] = None,
    world_objects_catalog: Optional[dict[str, Interactable]] = None,
    region_catalog: Optional[dict[str, WorldRegion]] = None,
) -> tuple[Player, Any]:
    """
    Loads player game state and companion ai_state.json.
    Reconstructs both and ensures registered agents match the player's collection.
    """
    from src.ai.persistence import load_ai_state, get_ai_state_path_for_save_file

    player = load_game(
        path=path,
        species_catalog=species_catalog,
        attack_catalog=attack_catalog,
        item_catalog=item_catalog,
        quest_catalog=quest_catalog,
        world_objects_catalog=world_objects_catalog,
        region_catalog=region_catalog,
    )
    eff_ai_path = Path(ai_state_path) if ai_state_path is not None else get_ai_state_path_for_save_file(path)
    ai_state = load_ai_state(eff_ai_path, create_if_missing=create_ai_if_missing)
    if hasattr(ai_state, "sync_with_player_collection"):
        ai_state.sync_with_player_collection(player)

    return player, ai_state


class SaveManager:
    """
    Service class wrapper providing standard save/load methods.
    """

    @staticmethod
    def save(player: Player, path: Union[str, Path]) -> None:
        """Saves player game state to the specified path."""
        save_game(player, path)

    @staticmethod
    def load(
        path: Union[str, Path],
        species_catalog: Optional[dict[str, PokemonSpecies]] = None,
        attack_catalog: Optional[dict[str, Attack]] = None,
        item_catalog: Optional[dict[str, Item]] = None,
        quest_catalog: Optional[dict[str, QuestDefinition]] = None,
        world_objects_catalog: Optional[dict[str, Interactable]] = None,
        region_catalog: Optional[dict[str, WorldRegion]] = None,
    ) -> Player:
        """Loads and returns a reconstructed Player instance from the specified path."""
        return load_game(
            path=path,
            species_catalog=species_catalog,
            attack_catalog=attack_catalog,
            item_catalog=item_catalog,
            quest_catalog=quest_catalog,
            world_objects_catalog=world_objects_catalog,
            region_catalog=region_catalog,
        )

    @staticmethod
    def save_with_ai(
        player: Player,
        path: Union[str, Path],
        ai_state: Optional[Any] = None,
        ai_state_path: Optional[Union[str, Path]] = None,
        trainer_manager: Optional[Any] = None,
        trainer_state_path: Optional[Union[str, Path]] = None,
    ) -> None:
        """Saves player game state and companion ai_state.json (and optional trainers.json) atomically."""
        save_game_with_ai(
            player,
            path,
            ai_state=ai_state,
            ai_state_path=ai_state_path,
            trainer_manager=trainer_manager,
            trainer_state_path=trainer_state_path,
        )

    @staticmethod
    def save_with_trainers(
        player: Player,
        path: Union[str, Path],
        trainer_manager: Any,
        trainer_state_path: Optional[Union[str, Path]] = None,
    ) -> None:
        """Saves player game state and companion trainers.json atomically."""
        save_game_with_ai(
            player,
            path,
            ai_state=None,
            trainer_manager=trainer_manager,
            trainer_state_path=trainer_state_path,
        )

    @staticmethod
    def load_with_trainers(
        path: Union[str, Path],
        trainer_state_path: Optional[Union[str, Path]] = None,
        create_trainers_if_missing: bool = True,
        species_catalog: Optional[dict[str, PokemonSpecies]] = None,
        attack_catalog: Optional[dict[str, Attack]] = None,
        item_catalog: Optional[dict[str, Item]] = None,
        quest_catalog: Optional[dict[str, QuestDefinition]] = None,
        world_objects_catalog: Optional[dict[str, Interactable]] = None,
        region_catalog: Optional[dict[str, WorldRegion]] = None,
    ) -> tuple[Player, Any]:
        """Loads player game state and companion trainers.json."""
        return load_game_with_trainers(
            path=path,
            trainer_state_path=trainer_state_path,
            create_trainers_if_missing=create_trainers_if_missing,
            species_catalog=species_catalog,
            attack_catalog=attack_catalog,
            item_catalog=item_catalog,
            quest_catalog=quest_catalog,
            world_objects_catalog=world_objects_catalog,
            region_catalog=region_catalog,
        )

    @staticmethod
    def load_with_ai(
        path: Union[str, Path],
        ai_state_path: Optional[Union[str, Path]] = None,
        create_ai_if_missing: bool = True,
        species_catalog: Optional[dict[str, PokemonSpecies]] = None,
        attack_catalog: Optional[dict[str, Attack]] = None,
        item_catalog: Optional[dict[str, Item]] = None,
        quest_catalog: Optional[dict[str, QuestDefinition]] = None,
        world_objects_catalog: Optional[dict[str, Interactable]] = None,
        region_catalog: Optional[dict[str, WorldRegion]] = None,
    ) -> tuple[Player, Any]:
        """Loads player game state and companion ai_state.json."""
        return load_game_with_ai(
            path=path,
            ai_state_path=ai_state_path,
            create_ai_if_missing=create_ai_if_missing,
            species_catalog=species_catalog,
            attack_catalog=attack_catalog,
            item_catalog=item_catalog,
            quest_catalog=quest_catalog,
            world_objects_catalog=world_objects_catalog,
            region_catalog=region_catalog,
        )

    @staticmethod
    def serialize(player: Player) -> dict[str, Any]:
        """Serializes player game state to a JSON-compatible dictionary."""
        return serialize_player(player)

    @staticmethod
    def deserialize(
        data: dict[str, Any],
        species_catalog: Optional[dict[str, PokemonSpecies]] = None,
        attack_catalog: Optional[dict[str, Attack]] = None,
        item_catalog: Optional[dict[str, Item]] = None,
        quest_catalog: Optional[dict[str, QuestDefinition]] = None,
        world_objects_catalog: Optional[dict[str, Interactable]] = None,
        region_catalog: Optional[dict[str, WorldRegion]] = None,
    ) -> Player:
        """Deserializes a JSON dictionary into a reconstructed Player instance."""
        return deserialize_player(
            data=data,
            species_catalog=species_catalog,
            attack_catalog=attack_catalog,
            item_catalog=item_catalog,
            quest_catalog=quest_catalog,
            world_objects_catalog=world_objects_catalog,
            region_catalog=region_catalog,
        )
