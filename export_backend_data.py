#!/usr/bin/env python3
"""
Exports canonical game data definitions (Pokemon species, attacks, level-up move learning,
personality traits, items, habitats, regions, and quests) from Python source models into JSON format
for the Godot client.
"""
import json
import os
from pathlib import Path

# Import from backend source modules
from src.data.species import SAMPLE_SPECIES
from src.data.attacks import SAMPLE_ATTACKS
from src.data.move_learning import SPECIES_MOVE_LEARNING
from src.models.personality import Personality
from src.data.items import ITEM_CATALOG
from src.data.habitats import HABITAT_CATALOG
from src.data.world_regions import WORLD_REGION_CATALOG
from src.data.quests import QUEST_CATALOG


def build_backend_data() -> dict:
    species_dict = {}
    for name, sp in SAMPLE_SPECIES.items():
        types = [sp.primary_type.name.capitalize()]
        if sp.secondary_type:
            types.append(sp.secondary_type.name.capitalize())

        species_dict[name] = {
            "name": sp.name,
            "types": types,
            "base_hp": sp.base_hp,
            "base_attack": sp.base_attack,
            "base_defense": sp.base_defense,
            "base_speed": sp.base_speed,
            "available_attacks": [atk.name for atk in sp.available_attacks],
            "abilities": [ab.name for ab in sp.abilities],
            "color": "#FAD812" if name == "Pikachu" else ("#F05A0A" if name == "Charmander" else ("#458FE8" if name == "Squirtle" else "#4DAE44")),
            "description": f"A wild {sp.name}."
        }

    attacks_dict = {}
    for name, atk in SAMPLE_ATTACKS.items():
        effect_str = ""
        effect_target = "defender"
        effect_chance = 0
        if atk.effect:
            effect_str = atk.effect.effect_type.name
            effect_target = getattr(atk.effect, "target", "defender")
            effect_chance = getattr(atk.effect, "chance", 0)

        attacks_dict[name] = {
            "name": atk.name,
            "type": atk.type.name.capitalize(),
            "power": atk.power,
            "accuracy": atk.accuracy,
            "category": "special" if atk.type.name in ("FIRE", "WATER", "GRASS", "ELECTRIC", "PSYCHIC") else "physical",
            "effect": effect_str,
            "effect_target": effect_target,
            "effect_chance": effect_chance,
            "priority": getattr(atk, "priority", 0)
        }

    move_learning_dict = {}
    for sp_name, moves in SPECIES_MOVE_LEARNING.items():
        move_learning_dict[sp_name] = [[m.level, m.attack.name] for m in moves]

    items_dict = {}
    for item_id, item in ITEM_CATALOG.items():
        eff = "heal"
        heal_amt = 0
        if item_id == "potion":
            heal_amt = 20
        elif item_id == "super_potion":
            heal_amt = 50
        elif item_id == "full_restore":
            heal_amt = 9999
            eff = "full_restore"
        elif item_id in ("antidote", "burn_heal", "paralyze_heal"):
            eff = item_id
        elif item_id == "poke_ball":
            eff = "capture"

        items_dict[item_id] = {
            "id": item_id,
            "name": item.name,
            "description": getattr(item, "description", ""),
            "effect": eff,
            "heal_amount": heal_amt,
            "usable_in_battle": True,
            "usable_in_field": item_id != "poke_ball"
        }

    habitats_dict = {}
    for hab_id, hab in HABITAT_CATALOG.items():
        cands = []
        for c in hab.candidates:
            cands.append({
                "species": c.species.name,
                "weight": int(c.weight),
                "min_level": c.min_level,
                "max_level": c.max_level,
                "allowed_times": [t.name.lower() for t in c.allowed_times]
            })
        for r_id in hab.region_ids:
            habitats_dict[r_id] = cands
        habitats_dict[hab_id] = cands

    regions_dict = {}
    for r_id, r in WORLD_REGION_CATALOG.items():
        regions_dict[r_id] = {
            "id": r.region_id,
            "name": r.name,
            "description": r.description,
            "discovery_text": r.discovery_text,
            "bounds": {
                "x1": float(r.bounds[0]) * 10.0,
                "z1": float(r.bounds[1]) * 10.0,
                "x2": float(r.bounds[2]) * 10.0,
                "z2": float(r.bounds[3]) * 10.0,
            }
        }

    quests_dict = {}
    for q_id, q in QUEST_CATALOG.items():
        objs = []
        for o in q.objectives:
            objs.append({
                "objective_id": o.objective_id,
                "type": o.objective_type.value,
                "description": o.description,
                "target_count": o.target_count,
                "target_species": o.target_species,
                "target_item": o.target_item
            })
        quests_dict[q_id] = {
            "id": q.quest_id,
            "name": q.name,
            "description": q.description,
            "objectives": objs,
            "rewards": q.rewards,
            "prerequisites": list(q.prerequisites)
        }

    return {
        "species": species_dict,
        "attacks": attacks_dict,
        "move_learning": move_learning_dict,
        "personality_traits": list(Personality.TRAIT_NAMES),
        "items": items_dict,
        "habitats": habitats_dict,
        "regions": regions_dict,
        "quests": quests_dict
    }


def export_backend_data(target_path: Path = None) -> Path:
    if target_path is None:
        target_path = Path(__file__).parent / "Godot" / "syntax-error-26" / "data" / "backend_pokemon_data.json"

    target_path.parent.mkdir(parents=True, exist_ok=True)
    data = build_backend_data()

    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"Exported backend data successfully to {target_path}")
    print(f"  - Species: {len(data['species'])}")
    print(f"  - Attacks: {len(data['attacks'])}")
    print(f"  - Move tables: {len(data['move_learning'])}")
    print(f"  - Items: {len(data['items'])}")
    print(f"  - Habitats: {len(data['habitats'])}")
    print(f"  - Regions: {len(data['regions'])}")
    print(f"  - Quests: {len(data['quests'])}")
    print(f"  - Personality traits: {data['personality_traits']}")
    return target_path


if __name__ == "__main__":
    export_backend_data()
