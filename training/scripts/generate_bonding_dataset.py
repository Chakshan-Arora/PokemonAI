"""
Dataset generator for Adapter A: Pokemon Personality and Bonding Decisions.
Generates structured, diverse, contrasting scenarios across species, temperaments,
trust/affection levels, and memories, split cleanly into train, val, and test sets.
"""
import json
import random
from pathlib import Path
from typing import Any

SPECIES_TEMPERAMENTS = {
    "Charmander": {"cries": ["Char! Char-mander!", "Chaaar!", "*smolders tail warmly*"], "nature": "proud"},
    "Pikachu": {"cries": ["Pika-pi!", "Pikachu!", "*sparks cheerfully from cheeks*"], "nature": "energetic"},
    "Squirtle": {"cries": ["Squirtle-squirt!", "Squirtle!", "*taps shell rhythmically*"], "nature": "calm"},
    "Bulbasaur": {"cries": ["Bulba-saur!", "Saur!", "*rustles bulb gently*"], "nature": "stoic"},
    "Eevee": {"cries": ["Eev-ee!", "Vee!", "*wags bushy tail enthusiastically*"], "nature": "affectionate"},
    "Growlithe": {"cries": ["Arf! Growlithe!", "Ruff!", "*stands attentively at attention*"], "nature": "loyal"},
    "Geodude": {"cries": ["Geo-dude!", "Dude!", "*bumps stony fists together*"], "nature": "tough"},
    "Zubat": {"cries": ["Zu-zu!", "Zubat!", "*flutters wings erratically*"], "nature": "skittish"},
    "Gastly": {"cries": ["Gast-ly!", "Ke-ke-ke!", "*drifts playfully through the air*"], "nature": "mischievous"},
    "Machop": {"cries": ["Chop! Machop!", "Maaa!", "*flexes biceps determinedly*"], "nature": "disciplined"},
}

PRAISE_INPUTS = [
    "You did fantastic in that battle!",
    "I'm so proud of how hard you fought today.",
    "Great work out there, partner!",
    "You're the best teammate I could ever ask for.",
    "Outstanding performance! Take a good rest now.",
    "That was brilliant, well done!",
    "You were so brave back there!",
    "You've grown so much stronger since we first met.",
    "I believe in you, you're doing amazing.",
    "Good job, keep it up!",
]

SCOLD_INPUTS = [
    "Why did you mess up that attack?",
    "That was terrible, you need to pay attention!",
    "You're not listening to my commands at all!",
    "Stop fooling around, this is serious!",
    "That was such a careless mistake.",
    "You were pathetic in that match.",
    "Listen to me when I'm speaking to you!",
    "If you keep slacking off, you won't stay on the team.",
    "Why can't you get this right?",
    "You completely embarrassed us out there.",
]

GOAL_INPUTS = [
    "What kind of goals do you want us to accomplish together?",
    "What are your biggest dreams for the future?",
    "Do you want to become the strongest in the region?",
    "What do you hope to achieve by traveling with me?",
    "Tell me about your aspirations, partner.",
]

RELEASE_INPUTS = [
    "Do you ever think about returning to the wild?",
    "Are you happy here, or do you want to be set free?",
    "If you want to leave the team, I won't hold you back.",
    "Would you prefer your freedom back in the forest?",
    "Do you want to say goodbye and return home?",
]

CHAT_INPUTS = [
    "How are you feeling today?",
    "The weather is really nice for a walk, isn't it?",
    "What do you think of this route?",
    "Are you hungry? We can stop for lunch soon.",
    "Just wanted to see how you're doing.",
]


def generate_single_example(sample_id: int, rng: random.Random) -> dict[str, Any]:
    species = rng.choice(list(SPECIES_TEMPERAMENTS.keys()))
    meta = SPECIES_TEMPERAMENTS[species]
    cry = rng.choice(meta["cries"])
    
    # 5 distinct interaction contexts
    interaction_type = rng.choice(["praise", "scold", "discuss_goals", "discuss_release", "talk"])
    
    # Relationship archetype
    rel_archetype = rng.choice(["devoted", "friend", "acquaintance", "wary", "resentful"])
    if rel_archetype == "devoted":
        trust = rng.uniform(60.0, 95.0)
        affection = rng.uniform(65.0, 95.0)
        fam = rng.uniform(70.0, 100.0)
        stage = "devoted"
    elif rel_archetype == "friend":
        trust = rng.uniform(25.0, 59.0)
        affection = rng.uniform(30.0, 64.0)
        fam = rng.uniform(40.0, 75.0)
        stage = "friend"
    elif rel_archetype == "acquaintance":
        trust = rng.uniform(0.0, 24.0)
        affection = rng.uniform(0.0, 29.0)
        fam = rng.uniform(15.0, 45.0)
        stage = "acquaintance"
    elif rel_archetype == "wary":
        trust = rng.uniform(-25.0, -1.0)
        affection = rng.uniform(-20.0, 5.0)
        fam = rng.uniform(5.0, 35.0)
        stage = "wary"
    else:  # resentful
        trust = rng.uniform(-75.0, -26.0)
        affection = rng.uniform(-80.0, -15.0)
        fam = rng.uniform(20.0, 60.0)
        stage = "resentful"

    # Personality traits
    agg = rng.randint(15, 85)
    fear = rng.randint(15, 85)
    cur = rng.randint(20, 85)
    conf = rng.randint(20, 85)
    loy = rng.randint(15, 90)
    soc = rng.randint(20, 85)

    if fear >= 65 and conf < 50:
        temperament = "cautious"
    elif agg >= 65:
        temperament = "aggressive"
    elif cur >= 65:
        temperament = "curious"
    elif conf >= 65:
        temperament = "bold"
    elif soc >= 65:
        temperament = "friendly"
    else:
        temperament = "balanced"

    hp_ratio = round(rng.uniform(0.2, 1.0), 2)
    
    # Select user input
    if interaction_type == "praise":
        player_msg = rng.choice(PRAISE_INPUTS)
    elif interaction_type == "scold":
        player_msg = rng.choice(SCOLD_INPUTS)
    elif interaction_type == "discuss_goals":
        player_msg = rng.choice(GOAL_INPUTS)
    elif interaction_type == "discuss_release":
        player_msg = rng.choice(RELEASE_INPUTS)
    else:
        player_msg = rng.choice(CHAT_INPUTS)

    # Determine ground-truth structured decision based on context
    if interaction_type == "praise":
        interpretation = "praise"
        if stage in ("devoted", "friend"):
            emotional_state = "pleased"
            action_type = "interact"
            intent = "Celebrate praise and show affection towards trainer"
            dialogue = f"{cry} *happily approaches and leans into trainer's praise*"
            confidence = 0.95
            rationale = f"High trust ({trust:.1f}) and devotion foster deep appreciation for praise."
        elif stage == "wary":
            emotional_state = "surprised"
            action_type = "inspect"
            intent = "Observe trainer cautiously while accepting tentative praise"
            dialogue = f"{cry} *blinks in surprise, hesitating before offering a small nod*"
            confidence = 0.8
            rationale = f"Wary relationship ({stage}) causes initial suspicion despite positive praise."
        else:  # resentful
            emotional_state = "defiant"
            action_type = "protest" if agg >= 50 else "hesitate"
            intent = "Reject trainer praise due to ongoing resentment"
            dialogue = f"{cry} *scoffs and turns head away coldly, ignoring the trainer*"
            confidence = 0.88
            rationale = f"Negative trust ({trust:.1f}) and alienation prevent accepting praise."

    elif interaction_type == "scold":
        interpretation = "scold"
        if stage in ("devoted", "friend") and loy >= 60:
            emotional_state = "dejected"
            action_type = "hesitate"
            intent = "Lower head in regret and resolve to do better"
            dialogue = f"{cry} *droops ears apologetically and looks down in remorse*"
            confidence = 0.9
            rationale = f"High loyalty ({loy}) causes Pokemon to take criticism deeply to heart."
        elif agg >= 65 or stage == "resentful":
            emotional_state = "indignant"
            action_type = "protest" if stage != "resentful" else "disobey"
            intent = "Angrily reject harsh reprimand"
            dialogue = f"{cry} *growls sharply and bristles its posture in defiance*"
            confidence = 0.92
            rationale = f"High aggression ({agg}) and resentment ({trust:.1f}) provoke hostility against scolding."
        else:
            emotional_state = "anxious"
            action_type = "hesitate"
            intent = "Flinch back nervously from harsh tone"
            dialogue = f"{cry} *takes a nervous step back, trembling slightly*"
            confidence = 0.85
            rationale = f"Fear ({fear}) and negative reprimand trigger defensive withdrawal."

    elif interaction_type == "discuss_goals":
        interpretation = "inquire_goals"
        emotional_state = "inspired"
        action_type = "interact"
        intent = "Share ambition to conquer gym challenges and master combat"
        dialogue = f"{cry} *strikes a proud determined pose, eyes gleaming with ambition*"
        confidence = 0.9
        rationale = f"Confidence ({conf}) and curiosity ({cur}) encourage enthusiastic goal sharing."

    elif interaction_type == "discuss_release":
        interpretation = "discuss_release"
        if stage == "resentful" or (trust < -30.0 and loy < 40):
            emotional_state = "longing"
            action_type = "request_release"
            intent = "Plead to be released back into the open wild"
            dialogue = f"{cry} *looks toward the open horizon with longing eyes, asking for freedom*"
            confidence = 0.94
            rationale = f"Severe resentment ({trust:.1f}) and low loyalty ({loy}) prompt request to return to the wild."
        else:
            emotional_state = "anxious"
            action_type = "interact"
            intent = "Reassure trainer of commitment to remain together"
            dialogue = f"{cry} *shakes head firmly and presses close to trainer's side*"
            confidence = 0.92
            rationale = f"Established trust ({trust:.1f}) confirms desire to stay with current trainer."

    else:  # talk
        interpretation = "casual_chat"
        emotional_state = "content"
        action_type = "interact"
        intent = "Enjoy peaceful conversation and companionship"
        dialogue = f"{cry} *chirps warmly in pleasant conversation*"
        confidence = 0.88
        rationale = f"Casual conversation fosters gradual familiarity gain."

    input_payload = {
        "species": species,
        "temperament": temperament,
        "personality_traits": {
            "aggression": agg,
            "fear": fear,
            "curiosity": cur,
            "confidence": conf,
            "loyalty": loy,
            "sociability": soc,
        },
        "hp_ratio": hp_ratio,
        "relationship": {
            "stage": stage,
            "trust": round(trust, 1),
            "affection": round(affection, 1),
            "familiarity": round(fam, 1),
        },
        "interaction_type": interaction_type,
        "player_input": player_msg,
        "permitted_actions": ["interact", "obey", "suggest", "protest", "request_release", "hesitate", "disobey", "rest"],
    }

    output_payload = {
        "interpretation": interpretation,
        "emotional_state": emotional_state,
        "action_type": action_type,
        "intent": intent,
        "dialogue": dialogue,
        "confidence": confidence,
        "rationale": rationale,
        "suggested_alternative": None,
    }

    # Format into ChatML instruction-following conversation record
    system_prompt = (
        f"You are the autonomous decision model for {species}, an expressive Pokemon with temperament '{temperament}'. "
        "Interpret the player interaction in light of your personality traits, relationship trust, and memories. "
        "Respond STRICTLY with a single JSON object matching the required schema."
    )
    user_prompt = f"Current Situation and Interaction Context:\n{json.dumps(input_payload, indent=2)}"
    assistant_reply = json.dumps(output_payload, indent=2)

    return {
        "id": f"bonding_sample_{sample_id:05d}",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": assistant_reply},
        ],
        "metadata": {
            "species": species,
            "interaction_type": interaction_type,
            "stage": stage,
            "action_type": action_type,
        }
    }


def main():
    rng = random.Random(42)
    output_dir = Path(__file__).resolve().parent.parent / "data" / "bonding"
    output_dir.mkdir(parents=True, exist_ok=True)

    total_samples = 3000
    print(f"Generating {total_samples} bonding dataset samples...")

    records = [generate_single_example(i, rng) for i in range(total_samples)]

    # 80% train, 10% val, 10% held-out test
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

    print("Bonding dataset generation complete!")


if __name__ == "__main__":
    main()
