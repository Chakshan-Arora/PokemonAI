"""
Dataset generator for Adapter B: Pokemon Battle Decisions.
Uses the authoritative game engine, type charts, damage calculators,
and TrainerAIDecisionModel to produce legally verified combat decision pairs.
"""
import sys
import os
from pathlib import Path

# Add project root to path for imports
repo_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(repo_root))

import json
import random
from typing import Any

from src.models.personality import Personality
from src.models.pokemon import Pokemon
from src.models.species import PokemonSpecies
from src.models.pokemon_type import PokemonType
from src.models.attack import Attack
from src.models.battle_state import BattleState
from src.models.battle import Battle
from src.data.species import (
    PIKACHU,
    CHARMANDER,
    SQUIRTLE,
    BULBASAUR,
    PIDGEY,
    RATTATA,
    GEODUDE,
    ZUBAT,
    MACHOP,
    GASTLY,
    GROWLITHE,
    EEVEE,
)
from src.data.attacks import (
    THUNDER_SHOCK,
    QUICK_ATTACK,
    EMBER,
    SCRATCH,
    WATER_GUN,
    TACKLE,
    VINE_WHIP,
    THUNDER_WAVE,
    TAIL_WHIP,
    GROWL,
    WILL_O_WISP,
    FLAMETHROWER,
    HYDRO_PUMP,
    THUNDERBOLT,
)
from src.models.trainer_ai import TrainerAIDecisionModel
from src.models.trainer import DifficultyProfile
from src.data.type_chart import get_effectiveness_against_pokemon

SPECIES_POOL = [
    PIKACHU,
    CHARMANDER,
    SQUIRTLE,
    BULBASAUR,
    PIDGEY,
    RATTATA,
    GEODUDE,
    ZUBAT,
    MACHOP,
    GASTLY,
    GROWLITHE,
    EEVEE,
]

ATTACK_POOL = [
    THUNDER_SHOCK,
    QUICK_ATTACK,
    EMBER,
    SCRATCH,
    WATER_GUN,
    TACKLE,
    VINE_WHIP,
    THUNDER_WAVE,
    TAIL_WHIP,
    GROWL,
]


def create_random_pokemon(species, level: int, rng: random.Random) -> Pokemon:
    personality = Personality(
        aggression=rng.randint(20, 80),
        curiosity=rng.randint(20, 80),
        fear=rng.randint(20, 80),
        sociability=rng.randint(20, 80),
        loyalty=rng.randint(20, 80),
        confidence=rng.randint(20, 80),
    )
    # Pick 2-4 appropriate attacks
    num_attacks = rng.randint(2, 4)
    # Give at least one attack matching species type if possible
    pool = [a for a in ATTACK_POOL if a.type in species.types]
    other_pool = [a for a in ATTACK_POOL if a.type not in species.types]
    selected_attacks = []
    if pool:
        selected_attacks.append(rng.choice(pool))
    while len(selected_attacks) < num_attacks:
        cand = rng.choice(ATTACK_POOL)
        if cand not in selected_attacks:
            selected_attacks.append(cand)

    mon = Pokemon(
        species=species,
        level=level,
        personality=personality,
        attacks=selected_attacks,
    )
    return mon


def generate_single_battle_example(sample_id: int, rng: random.Random) -> dict[str, Any]:
    trainer_ai = TrainerAIDecisionModel(rng=rng)

    sp1 = rng.choice(SPECIES_POOL)
    sp2 = rng.choice([s for s in SPECIES_POOL if s != sp1])

    lvl1 = rng.randint(5, 30)
    lvl2 = rng.randint(max(5, lvl1 - 4), lvl1 + 4)

    mon1 = create_random_pokemon(sp1, lvl1, rng)
    mon2 = create_random_pokemon(sp2, lvl2, rng)

    # Randomize current HP
    hp_pct1 = rng.uniform(0.15, 1.0)
    hp_pct2 = rng.uniform(0.15, 1.0)
    mon1.current_hp = max(1, int(mon1.max_hp * hp_pct1))
    mon2.current_hp = max(1, int(mon2.max_hp * hp_pct2))

    is_trainer_battle = rng.choice([True, False])
    current_turn = rng.randint(1, 8)

    # If critical HP in wild battle, Pokemon may choose to flee
    can_flee = (not is_trainer_battle) and (hp_pct1 <= 0.25) and (mon1.personality.fear >= 60)

    if can_flee and rng.random() < 0.7:
        action_type = "flee"
        chosen_move = None
        emotional_state = "panicked"
        dialogue = f"{mon1.display_name} leaped back in terror and fled from the battlefield!"
        confidence = 0.92
        rationale = f"Critical health ({int(hp_pct1*100)}% HP) and high fear ({mon1.personality.fear}) trigger self-preservation flight."
    else:
        # Use tactical AI to score and pick best legal attack
        difficulty = rng.choice([DifficultyProfile.NORMAL, DifficultyProfile.HARD, DifficultyProfile.BOSS])
        best_attack = None
        best_score = -1.0
        best_reason = ""

        for atk in mon1.attacks:
            score, reason = trainer_ai.score_attack(
                attack=atk,
                attacker=mon1,
                defender=mon2,
                difficulty=difficulty,
            )
            if score > best_score:
                best_score = score
                best_attack = atk
                best_reason = reason

        action_type = "attack"
        chosen_move = best_attack.name if best_attack else mon1.attacks[0].name
        eff = get_effectiveness_against_pokemon(best_attack or mon1.attacks[0], mon2)
        emotional_state = "focused" if eff >= 1.0 else "cautious"
        dialogue = f"{mon1.display_name} gathered energy and struck with {chosen_move}!"
        confidence = round(min(0.98, max(0.65, best_score / 100.0)), 2)
        rationale = best_reason

    input_payload = {
        "battle_context": {
            "is_trainer_battle": is_trainer_battle,
            "current_turn": current_turn,
            "active_pokemon": {
                "species": mon1.species.name,
                "level": mon1.level,
                "current_hp": mon1.current_hp,
                "max_hp": mon1.max_hp,
                "hp_ratio": round(mon1.current_hp / mon1.max_hp, 2),
                "known_moves": [a.name for a in mon1.attacks],
            },
            "opponent_pokemon": {
                "species": mon2.species.name,
                "level": mon2.level,
                "apparent_health": "critical" if hp_pct2 <= 0.3 else ("wounded" if hp_pct2 <= 0.65 else "healthy"),
            },
            "type_matchup_hint": {
                "attacker_types": [t.name.lower() for t in mon1.species.types],
                "defender_types": [t.name.lower() for t in mon2.species.types],
            },
            "permitted_actions": ["attack", "defend"] + (["flee"] if not is_trainer_battle else []),
        }
    }

    output_payload = {
        "action_type": action_type,
        "chosen_move": chosen_move,
        "target": mon2.species.name if action_type == "attack" else None,
        "emotional_state": emotional_state,
        "dialogue": dialogue,
        "confidence": confidence,
        "rationale": rationale,
        "suggested_alternative": None,
    }

    system_prompt = (
        f"You are the battle decision model for {mon1.species.name} in an authoritative Pokemon combat engine. "
        "Select the optimal legal action from the permitted actions and known moves based on battle state and type matchups. "
        "Respond STRICTLY with a single JSON object matching the required schema."
    )
    user_prompt = f"Current Battle Turn State:\n{json.dumps(input_payload, indent=2)}"
    assistant_reply = json.dumps(output_payload, indent=2)

    return {
        "id": f"battle_sample_{sample_id:05d}",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": assistant_reply},
        ],
        "metadata": {
            "attacker_species": mon1.species.name,
            "defender_species": mon2.species.name,
            "action_type": action_type,
            "chosen_move": chosen_move,
            "is_trainer_battle": is_trainer_battle,
        }
    }


def main():
    rng = random.Random(1337)
    output_dir = Path(__file__).resolve().parent.parent / "data" / "battle"
    output_dir.mkdir(parents=True, exist_ok=True)

    total_samples = 6000
    print(f"Generating {total_samples} battle dataset samples...")

    records = [generate_single_battle_example(i, rng) for i in range(total_samples)]

    n_train = int(total_samples * 0.8)
    n_val = int(total_samples * 0.1)

    train_data = records[:n_train]
    val_data = records[n_train : n_train + n_val]
    test_data = records[n_train + n_val :]

    for name, data in [("train", train_data), ("val", val_data), ("valid", val_data), ("test", test_data)]:
        path = output_dir / f"{name}.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            for rec in data:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"Saved {len(data)} records to {path}")

    print("Battle dataset generation complete!")


if __name__ == "__main__":
    main()
