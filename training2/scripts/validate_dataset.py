"""
Dataset Validator for Battle Talk LLM (Syntax Error 26 - Model 2).
Validates JSON syntax, schema conformance, message formatting, and value bounds.
"""
import json
import sys
from pathlib import Path

# Add project root to path
repo_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(repo_root))


def validate_file(file_path: Path, schema: dict) -> bool:
    print(f"\nValidating {file_path.name}...")
    if not file_path.exists():
        print(f"Error: {file_path} does not exist.")
        return False

    required_keys = schema.get("required", [])
    valid_intents = set(schema["properties"]["intent"]["enum"])

    count = 0
    errors = 0

    with open(file_path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            count += 1
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception as e:
                print(f"  Line {idx+1}: Invalid JSON line - {e}")
                errors += 1
                continue

            # Check messages structure
            messages = rec.get("messages", [])
            if len(messages) != 3:
                print(f"  Line {idx+1}: Expected 3 messages (system, user, assistant), got {len(messages)}")
                errors += 1
                continue

            # Validate assistant payload against schema
            try:
                assistant_payload = json.loads(messages[2]["content"])
            except Exception as e:
                print(f"  Line {idx+1}: Assistant response is not valid JSON - {e}")
                errors += 1
                continue

            for req in required_keys:
                if req not in assistant_payload:
                    print(f"  Line {idx+1}: Missing required property '{req}'")
                    errors += 1

            intent = assistant_payload.get("intent")
            if intent not in valid_intents:
                print(f"  Line {idx+1}: Invalid intent '{intent}'")
                errors += 1

            morale = assistant_payload.get("morale_delta", 0)
            if not (-10 <= morale <= 10):
                print(f"  Line {idx+1}: Morale delta out of bounds (-10 to 10): {morale}")
                errors += 1

            confidence = assistant_payload.get("confidence", 0.0)
            if not (0.0 <= confidence <= 1.0):
                print(f"  Line {idx+1}: Confidence out of bounds (0.0 to 1.0): {confidence}")
                errors += 1

    if errors == 0:
        print(f"  SUCCESS: All {count} records conform to schema!")
        return True
    else:
        print(f"  FAILED: Encountered {errors} validation errors out of {count} records.")
        return False


def main():
    schema_path = Path(__file__).resolve().parent.parent / "schemas" / "battle_talk_schema.json"
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    data_dir = Path(__file__).resolve().parent.parent / "data" / "battle_talk"
    all_ok = True
    for split in ["train.jsonl", "val.jsonl", "test.jsonl"]:
        p = data_dir / split
        if p.exists():
            if not validate_file(p, schema):
                all_ok = False

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
