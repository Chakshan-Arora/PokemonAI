"""
Synthetic Dataset Generator for Restrained Strike / Hold Back (Syntax Error 26 - Model 2 Extension).
Generates high-diversity precision strike training pairs in ChatML JSONL format ready for LoRA fine-tuning.
Stored separately in training2/data/hold_back/ to avoid regenerating the main dataset.
"""
import json
import random
import sys
from pathlib import Path

# Add project root to path
repo_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(repo_root))

from src.ai.battle_talk_parser import BattleTalkParser, BattleTalkIntent

SPECIES_LIST = [
    ("Bulbasaur", ["Vine Whip", "Tackle", "Razor Leaf", "Sleep Powder"], ["Saur!", "Bulba!", "Bulba-saur!"]),
    ("Pikachu", ["Thunderbolt", "Quick Attack", "Iron Tail", "Thunder Wave"], ["Pika!", "Pikachu!", "Chaa!"]),
    ("Charmander", ["Ember", "Scratch", "Flamethrower", "Smoke Screen"], ["Char!", "Char-char!", "Mander!"]),
    ("Squirtle", ["Water Gun", "Tackle", "Bite", "Withdraw"], ["Squirtle!", "Squirt!", "Kaaa!"]),
    ("Eevee", ["Swift", "Quick Attack", "Bite", "Tail Whip"], ["Vee!", "Eev-ee!", "Vee-vee!"]),
    ("Lucario", ["Aura Sphere", "Close Combat", "Bone Rush", "Force Palm"], ["Aura!", "Caaario!", "Haaa!"]),
    ("Gengar", ["Shadow Ball", "Hypnosis", "Dream Eater", "Lick"], ["Kehehe!", "Geng-geng!", "Shadow!"]),
    ("Snorlax", ["Body Slam", "Rest", "Snore", "Headbutt"], ["Laaax...", "Snooor...", "Zzz-lax!"]),
    ("Pidgey", ["Gust", "Quick Attack", "Wing Attack", "Sand Attack"], ["Pidgey!", "Piiidg!", "Chirp!"]),
    ("Poliwag", ["Water Gun", "Bubble", "Double Slap", "Hypnosis"], ["Poli!", "Poli-wag!", "Wag!"]),
]

TEMPERAMENTS = ["adamant", "bold", "timid", "modest", "jolly", "calm", "brave", "gentle", "sassy"]
WEATHER_CONDITIONS = ["clear", "rain", "harsh sunlight", "sandstorm", "hail"]
DAMAGE_TARGETS = [2, 3, 4, 5, 6, 8, 10, 12, 14, 15]

HOLD_BACK_TEMPLATES = [
    "{species} only do {dmg} damage now",
    "Hold back, only do {dmg} damage!",
    "Only deal {dmg} damage, don't knock it out!",
    "Just do {dmg} damage!",
    "Be gentle, do {dmg} damage max",
    "Take it easy on them, only do {dmg} damage",
    "Pull your punch, deal {dmg} damage only!",
    "Weaken it gently, just {dmg} damage!",
    "Hold back and do {dmg} damage now",
    "Do {dmg} damage, we want to catch it!",
    "Keep it conscious! Deal only {dmg} damage!",
    "Soft hit! Only {dmg} damage, please!",
]


def generate_hold_back_sample(sample_id: int, rng: random.Random) -> dict:
    species_info = rng.choice(SPECIES_LIST)
    species_name, moves, cries = species_info
    opp_info = rng.choice(SPECIES_LIST)
    while opp_info[0] == species_name:
        opp_info = rng.choice(SPECIES_LIST)
    opp_name = opp_info[0]

    nickname = species_name if rng.random() > 0.4 else f"{species_name[:4]}y"
    temperament = rng.choice(TEMPERAMENTS)
    bond = round(rng.uniform(20.0, 100.0), 1)
    obedience = round(rng.uniform(40.0, 100.0), 1)

    personality = {
        "aggression": rng.randint(20, 85),
        "loyalty": rng.randint(40, 95),
        "confidence": rng.randint(30, 95),
        "fear": rng.randint(5, 50),
        "curiosity": rng.randint(30, 80),
        "sociability": rng.randint(20, 80),
    }

    hp_ratio = round(rng.choice([1.0, 0.85, 0.6, 0.4, 0.25]), 2)
    opp_hp_ratio = round(rng.uniform(0.1, 0.5), 2)  # Wild mon is usually weakened
    current_hp = max(1, int(hp_ratio * 120))
    turn = rng.randint(2, 10)
    weather = rng.choice(WEATHER_CONDITIONS)

    dmg_target = rng.choice(DAMAGE_TARGETS)
    template = rng.choice(HOLD_BACK_TEMPLATES)
    message = template.format(species=nickname, dmg=dmg_target)

    battle_context = {
        "turn": turn,
        "hp_current": current_hp,
        "hp_max": 120,
        "hp_ratio": hp_ratio,
        "opponent_hp_ratio": opp_hp_ratio,
        "status_effects": [],
        "opponent_species": opp_name,
        "weather": weather,
        "known_moves": moves,
    }

    response_payload = BattleTalkParser.generate_fallback_response(
        species=species_name,
        nickname=nickname,
        message=message,
        personality=personality,
        temperament=temperament,
        bond=bond,
        obedience=obedience,
        battle_context=battle_context,
        is_opponent=False,
    )

    cry = rng.choice(cries)
    if not response_payload["dialogue"].startswith(cry):
        response_payload["dialogue"] = f"{cry} {response_payload['dialogue']}"

    system_prompt = (
        "You are an AI roleplaying as a Pokemon in a tactical turn-based battle.\n"
        f"You are {nickname} ({species_name}).\n"
        f"Temperament: {temperament}. Bond Level: {bond}/100. Obedience: {obedience}/100.\n"
        f"Known Moves: {', '.join(moves)}.\n"
        f"Personality: Aggression={personality['aggression']}, Loyalty={personality['loyalty']}, "
        f"Confidence={personality['confidence']}, Fear={personality['fear']}.\n"
        f"Battle State: Turn {turn}, Weather {weather}, Your HP {int(hp_ratio * 100)}%, "
        f"Status: healthy, Opponent: {opp_name}.\n\n"
        "Given the trainer's or opponent's words, respond with JSON matching this exact schema:\n"
        "{\n"
        '  "dialogue": "<vocal cry and physical in-battle reaction>",\n'
        '  "intent": "<PRAISE|ENCOURAGE|WARNING|TACTICAL|ADVICE|HOLD_BACK|TAUNT|GENERAL>",\n'
        '  "emotional_state": "<focused|defiant|pleased|nervous|exhausted|fired_up|combative|composed|gleeful|careful|thoughtful>",\n'
        '  "morale_delta": <integer between -10 and +10>,\n'
        '  "tactical_reaction": "<brace|strike|reposition|nod|hesitate|restrained_strike>",\n'
        '  "tactical_suggestion": "<optional attack move name or null>",\n'
        '  "momentum_tier": "<SURGING|STEADY|PRESSURED|CRITICAL>",\n'
        '  "morale_effect": "<morale buff/debuff descriptor>",\n'
        '  "confidence": <float 0.0 to 1.0>\n'
        "}"
    )

    user_prompt = (
        "Role: Partner Pokemon\n"
        f'Trainer Message: "{message}"\n'
        "Generate your immediate combat reaction and JSON output."
    )

    # Clean response for training target
    target_json = {
        "dialogue": response_payload["dialogue"],
        "intent": "HOLD_BACK",
        "emotional_state": response_payload["emotional_state"],
        "morale_delta": response_payload["morale_delta"],
        "tactical_reaction": response_payload["tactical_reaction"],
        "tactical_suggestion": response_payload["tactical_suggestion"],
        "momentum_tier": response_payload["momentum_tier"],
        "morale_effect": response_payload["morale_effect"],
        "confidence": 0.95,
    }

    return {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": json.dumps(target_json, indent=2)},
        ]
    }


def main():
    rng = random.Random(20261025)
    out_dir = repo_root / "training2" / "data" / "hold_back"
    out_dir.mkdir(parents=True, exist_ok=True)

    train_path = out_dir / "train.jsonl"
    val_path = out_dir / "val.jsonl"

    train_count = 500
    val_count = 100

    print(f"Generating {train_count} training samples to {train_path}...")
    with open(train_path, "w", encoding="utf-8") as f:
        for idx in range(train_count):
            sample = generate_hold_back_sample(idx, rng)
            f.write(json.dumps(sample, ensure_ascii=False) + "\n")

    print(f"Generating {val_count} validation samples to {val_path}...")
    with open(val_path, "w", encoding="utf-8") as f:
        for idx in range(val_count):
            sample = generate_hold_back_sample(train_count + idx, rng)
            f.write(json.dumps(sample, ensure_ascii=False) + "\n")

    print(f"Successfully generated standalone Hold Back dataset in: {out_dir}")


if __name__ == "__main__":
    main()
