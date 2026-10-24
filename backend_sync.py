#!/usr/bin/env python3
"""
PokemonAI Backend Sync Utility.
Syncs data definitions from Python into Godot format,
verifies save files against Python's SaveManager schema,
and provides inspection of the current game state.
"""
import sys
import json
from pathlib import Path

from export_backend_data import export_backend_data
from src.models.save_manager import load_game, save_game


def status():
    save_path = Path(__file__).parent / "save_game.json"
    if not save_path.exists():
        print(f"No save file found at {save_path}")
        return

    player = load_game(save_path)
    print("=" * 50)
    print(f"Trainer: {player.name} (ID: {player.unique_id})")
    print(f"Collection: {len(player.collection)} Pokémon")
    print(f"Active Team: {len(player.team)} Pokémon")
    if player.active_pokemon:
        p = player.active_pokemon
        print(f"Active Pokémon: {p.species.name} (Lv {p.level}, HP: {p.current_hp}/{p.max_hp})")
        print(f"  Moves: {[atk.name for atk in p.attacks]}")
        print(f"  Personality: {p.personality.to_dict()}")
        print(f"  Bond: {p.bond} | Obedience: {p.obedience}")
    print("=" * 50)


def test_llm():
    """Simulates an interactive Battle Talk query against the local parser and logic."""
    from src.ai.battle_talk_parser import BattleTalkParser
    test_message = "Hang in there, Pikachu! Look out for that attack!"
    print("=" * 50)
    print("Testing Battle Talk Engine:")
    print(f"Input Message: '{test_message}'")
    cmd = BattleTalkParser.parse(test_message)
    print(f"Parsed Intent: {cmd.intent} (Category: {cmd.category})")
    resp = BattleTalkParser.generate_fallback_response(
        species="Pikachu",
        nickname="Sparky",
        message=test_message,
        personality={"aggression": 60, "loyalty": 85, "confidence": 75, "fear": 20},
        temperament="brave",
        bond=80.0,
        obedience=90.0,
        battle_context={"hp_ratio": 0.35, "status_effects": [], "opponent_species": "Onix"},
    )
    print("Engine Response:")
    print(json.dumps(resp, indent=2))
    print("=" * 50)


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else "sync"
    if arg in ("sync", "export"):
        export_backend_data()
    elif arg == "status":
        status()
    elif arg == "verify":
        save_path = Path(__file__).parent / "save_game.json"
        player = load_game(save_path)
        print(f"Save file {save_path} is valid for player '{player.name}'.")
    elif arg == "test_llm":
        test_llm()
    else:
        print("Usage: python backend_sync.py [sync|status|verify|test_llm]")


if __name__ == "__main__":
    main()
