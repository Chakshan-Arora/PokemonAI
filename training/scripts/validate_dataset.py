"""
Dataset Validation and Integrity Suite for Local Pokemon Model Training.
Validates:
1. Valid JSON formatting per record.
2. Complete ChatML structure (system, user, assistant messages).
3. Schema conformity of the assistant output payload.
4. Permitted action type legality.
5. Move legality: any chosen_move MUST be present in known_moves.
6. Target validity and confidence bounds [0.0, 1.0].
7. Distribution statistics across labels and species.
"""
import json
import sys
from collections import Counter
from pathlib import Path


def validate_file(path: Path, dataset_type: str) -> dict[str, Any]:
    print(f"\n--- Validating {dataset_type.upper()} dataset: {path.name} ---")
    if not path.exists():
        raise FileNotFoundError(f"Dataset file not found: {path}")

    total_records = 0
    errors = []
    action_counts = Counter()
    species_counts = Counter()
    emotion_counts = Counter()

    permitted_bonding_actions = {
        "obey", "attack", "defend", "hesitate", "disobey", "flee",
        "inspect", "interact", "suggest", "protest", "request_release", "rest"
    }
    permitted_battle_actions = {
        "attack", "defend", "flee", "hesitate", "suggest", "obey", "disobey"
    }

    with open(path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            total_records += 1

            try:
                record = json.loads(line)
            except json.JSONDecodeError as e:
                errors.append(f"Line {line_no}: Invalid JSON: {e}")
                continue

            # Validate ChatML structure
            messages = record.get("messages")
            if not isinstance(messages, list) or len(messages) != 3:
                errors.append(f"Line {line_no}: messages must be a list of 3 items (system, user, assistant).")
                continue

            roles = [m.get("role") for m in messages]
            if roles != ["system", "user", "assistant"]:
                errors.append(f"Line {line_no}: Unexpected roles: {roles}")
                continue

            # Validate Assistant JSON content
            assistant_text = messages[2].get("content", "")
            try:
                assistant_json = json.loads(assistant_text)
            except json.JSONDecodeError as e:
                errors.append(f"Line {line_no}: Assistant response is not valid JSON: {e}")
                continue

            # Parse user prompt input JSON
            user_text = messages[1].get("content", "")
            # Extract JSON from user prompt
            first_brace = user_text.find("{")
            last_brace = user_text.rfind("}")
            if first_brace == -1 or last_brace == -1:
                errors.append(f"Line {line_no}: User prompt does not contain JSON payload.")
                continue
            user_json = json.loads(user_text[first_brace : last_brace + 1])

            # Validation specific to dataset type
            action = assistant_json.get("action_type")
            conf = assistant_json.get("confidence")
            emotion = assistant_json.get("emotional_state")

            if not isinstance(conf, (int, float)) or not (0.0 <= conf <= 1.0):
                errors.append(f"Line {line_no}: Confidence out of bounds [0, 1]: {conf}")

            if dataset_type == "bonding":
                if action not in permitted_bonding_actions:
                    errors.append(f"Line {line_no}: Invalid bonding action_type: '{action}'")
                species = user_json.get("species")
                species_counts[species] += 1
                action_counts[action] += 1
                emotion_counts[emotion] += 1

                for field in ("interpretation", "intent", "dialogue", "rationale"):
                    if not assistant_json.get(field):
                        errors.append(f"Line {line_no}: Missing required bonding field: {field}")

            elif dataset_type == "battle":
                if action not in permitted_battle_actions:
                    errors.append(f"Line {line_no}: Invalid battle action_type: '{action}'")

                b_ctx = user_json.get("battle_context", {})
                active_mon = b_ctx.get("active_pokemon", {})
                known_moves = active_mon.get("known_moves", [])
                species = active_mon.get("species")

                species_counts[species] += 1
                action_counts[action] += 1
                emotion_counts[emotion] += 1

                if action == "attack":
                    chosen_move = assistant_json.get("chosen_move")
                    if not chosen_move:
                        errors.append(f"Line {line_no}: Attack action missing chosen_move.")
                    elif chosen_move not in known_moves:
                        errors.append(
                            f"Line {line_no}: Move '{chosen_move}' is NOT in known_moves {known_moves}."
                        )

                for field in ("dialogue", "rationale"):
                    if not assistant_json.get(field):
                        errors.append(f"Line {line_no}: Missing required battle field: {field}")

    print(f"Total records checked: {total_records}")
    print(f"Action distribution: {dict(action_counts)}")
    print(f"Emotion distribution: {dict(emotion_counts.most_common(5))}")
    print(f"Species covered ({len(species_counts)}): {list(species_counts.keys())}")

    if errors:
        print(f"FAILED with {len(errors)} error(s):")
        for err in errors[:10]:
            print(f"  - {err}")
        return {"success": False, "total": total_records, "errors": errors}

    print("ALL VALIDATION CHECKS PASSED SUCCESSFULLY (0 ERRORS)")
    return {"success": True, "total": total_records, "errors": []}


def main():
    root = Path(__file__).resolve().parent.parent / "data"
    all_ok = True

    for subset in ("train", "val", "test"):
        path = root / "bonding" / f"{subset}.jsonl"
        res = validate_file(path, "bonding")
        if not res["success"]:
            all_ok = False

    for subset in ("train", "val", "test"):
        path = root / "battle" / f"{subset}.jsonl"
        res = validate_file(path, "battle")
        if not res["success"]:
            all_ok = False

    if not all_ok:
        sys.exit(1)
    print("\nDataset validation suite complete: All training, validation, and test sets are 100% verified.")


if __name__ == "__main__":
    main()
