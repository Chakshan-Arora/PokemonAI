"""
Synthetic Dataset Generator for Battle Talk LLM (Syntax Error 26 - Model 2).
Generates high-diversity (instruction, context, utterance) -> (dialogue, intent, emotion, morale, advice)
training pairs in ChatML JSONL format ready for LoRA fine-tuning.
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
    ("Pikachu", ["Thunderbolt", "Quick Attack", "Iron Tail", "Thunder Wave"], ["Pika!", "Pikachu!", "Chaa!"]),
    ("Charizard", ["Flamethrower", "Wing Attack", "Slash", "Dragon Rage"], ["Graaar!", "Chaaar!", "Roaaar!"]),
    ("Blastoise", ["Hydro Pump", "Water Gun", "Bite", "Withdraw"], ["Blast!", "Hoo-blast!", "Kaaa!"]),
    ("Venusaur", ["Solar Beam", "Vine Whip", "Razor Leaf", "Sleep Powder"], ["Saur!", "Venu-saur!", "Grr-saur!"]),
    ("Gengar", ["Shadow Ball", "Hypnosis", "Dream Eater", "Lick"], ["Kehehe!", "Geng-geng!", "Shadow!"]),
    ("Lucario", ["Aura Sphere", "Close Combat", "Bone Rush", "Force Palm"], ["Aura!", "Caaario!", "Haaa!"]),
    ("Garchomp", ["Earthquake", "Dragon Claw", "Stone Edge", "Crunch"], ["Gaaarrr!", "Chomp!", "Rrr-chomp!"]),
    ("Snorlax", ["Body Slam", "Rest", "Snore", "Headbutt"], ["Laaax...", "Snooor...", "Zzz-lax!"]),
    ("Eevee", ["Swift", "Quick Attack", "Bite", "Tail Whip"], ["Vee!", "Eev-ee!", "Vee-vee!"]),
    ("Gyarados", ["Waterfall", "Dragon Dance", "Bite", "Twister"], ["Gyaaaaah!", "Raaargh!", "Kraaah!"]),
]

TEMPERAMENTS = ["adamant", "bold", "timid", "modest", "jolly", "calm", "brave", "sassy"]
WEATHER_CONDITIONS = ["clear", "rain", "harsh sunlight", "sandstorm", "hail"]
STATUS_CONDITIONS = [[], [], [], ["paralysis"], ["burn"], ["poison"], ["sleep"]]
OPPONENT_ARCHETYPES = ["wild", "rival", "gym_leader", "rocket_grunt"]

SAMPLE_UTTERANCES = {
    BattleTalkIntent.ADVICE: [
        "What should we do here? Which move is best?",
        "What's the play? What move do you recommend?",
        "How do we beat this opponent? Your call!",
        "Any ideas on which attack to use next?",
    ],
    BattleTalkIntent.PRAISE: [
        "Incredible hit! You're dominating this battle!",
        "Great job out there, that was beautiful!",
        "Awesome strike! Keep up that momentum!",
        "I'm so proud of how hard you're fighting!",
        "Well done! You completely read that move!",
        "Fantastic execution! Best partner ever!",
    ],
    BattleTalkIntent.ENCOURAGE: [
        "Hang in there! We can still turn this around!",
        "Don't give up now, I believe in you!",
        "You've got this! Push through the pain!",
        "Stay strong, buddy! We fight together till the end!",
        "Focus up! Let's show them what we're made of!",
        "Give it everything you've got! We're not backing down!",
    ],
    BattleTalkIntent.WARNING: [
        "Watch out! High-power attack incoming!",
        "Careful! Look at its posture, it's about to counter!",
        "Heads up! Don't let it flank you!",
        "Stay alert! Keep your guard raised!",
        "Danger behind you! Brace yourself!",
        "Eyes open! That move has type advantage against you!",
    ],
    BattleTalkIntent.TACTICAL: [
        "Dodge to the left right now!",
        "Jump up and evade that ground strike!",
        "Block it with your arms! Brace for impact!",
        "Duck and sidestep under that beam!",
        "Take cover behind the rocks!",
    ],
    BattleTalkIntent.TAUNT: [
        "Is that all you've got? Too slow!",
        "You can't even touch us with those weak moves!",
        "That didn't even scratch! Give up now!",
        "You call that an attack? Pathetic!",
    ],
    BattleTalkIntent.GENERAL: [
        "What's the plan here? Ready for the next command?",
        "How are you holding up?",
        "Let's stay calm and pace ourselves.",
        "Keep your rhythm steady.",
    ],
}


def generate_single_example(sample_id: int, rng: random.Random) -> dict:
    species_info = rng.choice(SPECIES_LIST)
    species_name, moves, cries = species_info
    opp_info = rng.choice(SPECIES_LIST)
    while opp_info[0] == species_name:
        opp_info = rng.choice(SPECIES_LIST)
    opp_name = opp_info[0]

    nickname = species_name if rng.random() > 0.4 else f"{species_name[:4]}y"
    temperament = rng.choice(TEMPERAMENTS)
    bond = round(rng.uniform(10.0, 100.0), 1)
    obedience = round(rng.uniform(20.0, 100.0), 1)

    personality = {
        "aggression": rng.randint(20, 95),
        "loyalty": rng.randint(25, 95),
        "confidence": rng.randint(20, 95),
        "fear": rng.randint(5, 75),
        "curiosity": rng.randint(30, 80),
        "sociability": rng.randint(20, 80),
    }

    hp_ratio = round(rng.choice([1.0, 0.85, 0.6, 0.4, 0.2, 0.1, 0.05]), 2)
    opp_hp_ratio = round(rng.uniform(0.1, 1.0), 2)
    current_hp = max(1, int(hp_ratio * 120))
    status = rng.choice(STATUS_CONDITIONS)
    turn = rng.randint(1, 12)
    weather = rng.choice(WEATHER_CONDITIONS)
    is_opponent = rng.random() < 0.2
    archetype = rng.choice(OPPONENT_ARCHETYPES) if is_opponent else "wild"

    # Pick intent and message
    intent_choice = rng.choice(list(SAMPLE_UTTERANCES.keys()))
    message = rng.choice(SAMPLE_UTTERANCES[intent_choice])

    battle_context = {
        "turn": turn,
        "hp_current": current_hp,
        "hp_max": 120,
        "hp_ratio": hp_ratio,
        "opponent_hp_ratio": opp_hp_ratio,
        "status_effects": status,
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
        is_opponent=is_opponent,
        opponent_archetype=archetype,
    )

    cry = rng.choice(cries)
    if not is_opponent and "sleep" not in status and "paralysis" not in status:
        if not response_payload["dialogue"].startswith(cry):
            response_payload["dialogue"] = f"{cry} {response_payload['dialogue']}"

    # Build prompt
    system_prompt = (
        "You are an AI roleplaying as a Pokemon in a tactical turn-based battle.\n"
        f"You are {nickname} ({species_name}).\n"
        f"Temperament: {temperament}. Bond Level: {bond}/100. Obedience: {obedience}/100.\n"
        f"Known Moves: {', '.join(moves)}.\n"
        f"Personality: Aggression={personality['aggression']}, Loyalty={personality['loyalty']}, "
        f"Confidence={personality['confidence']}, Fear={personality['fear']}.\n"
        f"Battle State: Turn {turn}, Weather {weather}, Your HP {int(hp_ratio * 100)}%, "
        f"Status: {', '.join(status) if status else 'healthy'}, Opponent: {opp_name}.\n\n"
        "Given the trainer's or opponent's words, respond with JSON matching this exact schema:\n"
        "{\n"
        '  "dialogue": "<vocal cry and physical in-battle reaction>",\n'
        '  "intent": "<PRAISE|ENCOURAGE|WARNING|TACTICAL|ADVICE|TAUNT|GENERAL>",\n'
        '  "emotional_state": "<focused|defiant|pleased|nervous|exhausted|fired_up|combative|composed|gleeful|cocky|malicious|thoughtful|recovering>",\n'
        '  "morale_delta": <integer between -10 and +10>,\n'
        '  "tactical_reaction": "<brace|strike|reposition|nod|hesitate>",\n'
        '  "tactical_suggestion": "<optional attack move name or null>",\n'
        '  "momentum_tier": "<SURGING|STEADY|PRESSURED|CRITICAL>",\n'
        '  "morale_effect": "<morale buff/debuff descriptor>",\n'
        '  "confidence": <float 0.0 to 1.0>\n'
        "}"
    )

    user_prompt = (
        f"Role: {'Opponent ' + archetype.capitalize() + ' Pokemon' if is_opponent else 'Partner Pokemon'}\n"
        f"Trainer Message: \"{message}\"\n"
        "Generate your immediate combat reaction and JSON output."
    )

    assistant_json = json.dumps(
        {
            "dialogue": response_payload["dialogue"],
            "intent": response_payload["intent"],
            "emotional_state": response_payload["emotional_state"],
            "morale_delta": response_payload["morale_delta"],
            "tactical_reaction": response_payload["tactical_reaction"],
            "tactical_suggestion": response_payload["tactical_suggestion"],
            "momentum_tier": response_payload["momentum_tier"],
            "morale_effect": response_payload["morale_effect"],
            "confidence": response_payload["confidence"],
        },
        indent=2,
    )

    return {
        "id": f"battle_talk_{sample_id:05d}",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": assistant_json},
        ],
        "metadata": {
            "species": species_name,
            "intent": response_payload["intent"],
            "emotional_state": response_payload["emotional_state"],
            "momentum_tier": response_payload["momentum_tier"],
            "is_opponent": is_opponent,
        },
    }


def main():
    rng = random.Random(42)
    output_dir = Path(__file__).resolve().parent.parent / "data" / "battle_talk"
    output_dir.mkdir(parents=True, exist_ok=True)

    total_samples = 3000
    print(f"[Training2] Generating {total_samples} enhanced Battle Talk training samples...")

    records = [generate_single_example(i, rng) for i in range(total_samples)]

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
        print(f"[Training2] Saved {len(data)} records to {path}")

    print("[Training2] Enhanced Battle Talk dataset generation complete!")


if __name__ == "__main__":
    main()
