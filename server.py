"""
Syntax Error 26 — Local Pokémon LLM HTTP Bridge Server.
Provides high-performance, low-latency REST endpoints for the Godot 3D Frontend:
- GET  /health           : Health check and model metadata
- POST /companion/talk   : Interactive partner Pokemon bonding dialogue
- POST /battle/decide    : Battle turn tactical move selection and combat dialogue
- POST /decide           : Generalized agent decision endpoint
"""
import argparse
import json
import os
import sys
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any

# Ensure project root is in sys.path
repo_root = Path(__file__).resolve().parent
sys.path.insert(0, str(repo_root))

import random
from export_backend_data import build_backend_data
from src.models.save_manager import load_game, save_game, serialize_player, deserialize_player
from src.models.habitat_manager import HabitatManager
from src.models.habitat import TimeOfDay
from src.data.species import SAMPLE_SPECIES
from src.models.personality import Personality
from src.models.pokemon import Pokemon
from src.ai.local_model_provider import LocalModelDecisionProvider
from src.ai.agent import PokemonAgent, AgentIdentity
from src.ai.perception import AgentPerception
from src.models.personality import Personality


_habitat_mgr: HabitatManager = None


def get_habitat_manager() -> HabitatManager:
    global _habitat_mgr
    if _habitat_mgr is None:
        _habitat_mgr = HabitatManager()
    return _habitat_mgr


def _serialize_pokemon_dict(mon: Pokemon) -> dict[str, Any]:
    return {
        "unique_id": getattr(mon, "unique_id", str(id(mon))),
        "species": mon.species.name,
        "species_name": mon.species.name,
        "nickname": getattr(mon, "nickname", mon.species.name) or mon.species.name,
        "level": mon.level,
        "experience": mon.experience,
        "current_hp": mon.current_hp,
        "max_hp": mon.max_hp,
        "bond": int(round(mon.bond)),
        "obedience": int(round(mon.obedience)),
        "personality": mon.personality.to_dict(),
        "attacks": [a.name for a in mon.attacks],
        "trained_stats": {
            "attack": mon.trained_attack,
            "defense": mon.trained_defense,
            "speed": mon.trained_speed,
        },
        "awarded_level_moves": list(getattr(mon, "_awarded_level_moves", [])),
    }


class LLMBridgeHandler(BaseHTTPRequestHandler):
    provider: LocalModelDecisionProvider = None

    def _set_headers(self, status: int = 200, content_type: str = "application/json") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_OPTIONS(self) -> None:
        self._set_headers(200)

    def do_GET(self) -> None:
        clean_path = self.path.split("?")[0]
        if clean_path in ("/health", "/"):
            payload = {
                "status": "online",
                "backend": "mlx_4bit",
                "model": "Qwen3-4B-4bit",
                "adapters": ["bonding_adapter", "battle_adapter"],
                "endpoints": [
                    "/health",
                    "/api/data",
                    "/api/load",
                    "/api/save",
                    "/api/wild_encounter",
                    "/api/pokemon/create",
                    "/companion/talk",
                    "/battle/decide",
                    "/decide",
                ],
                "timestamp": time.time(),
            }
            self._set_headers(200)
            self.wfile.write(json.dumps(payload).encode("utf-8"))
        elif clean_path == "/api/data":
            try:
                data = build_backend_data()
                self._set_headers(200)
                self.wfile.write(json.dumps(data).encode("utf-8"))
            except Exception as exc:
                self._set_headers(500)
                self.wfile.write(json.dumps({"error": f"Failed to build backend data: {exc}"}).encode("utf-8"))
        elif clean_path in ("/api/load", "/api/save"):
            try:
                save_path = repo_root / "save_game.json"
                if not save_path.exists():
                    self._set_headers(404)
                    self.wfile.write(json.dumps({"error": "No save file found"}).encode("utf-8"))
                    return
                player = load_game(save_path)
                serialized = serialize_player(player)
                self._set_headers(200)
                self.wfile.write(json.dumps(serialized).encode("utf-8"))
            except Exception as exc:
                self._set_headers(500)
                self.wfile.write(json.dumps({"error": f"Failed to load save file: {exc}"}).encode("utf-8"))
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({"error": "Not found"}).encode("utf-8"))

    def do_POST(self) -> None:
        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length).decode("utf-8")
        
        try:
            req_data = json.loads(raw_body) if raw_body else {}
        except Exception as exc:
            self._set_headers(400)
            self.wfile.write(json.dumps({"error": f"Invalid JSON body: {exc}"}).encode("utf-8"))
            return

        clean_path = self.path.split("?")[0]
        try:
            if clean_path == "/companion/talk":
                resp_data = self._handle_companion_talk(req_data)
            elif clean_path == "/battle/decide":
                resp_data = self._handle_battle_decide(req_data)
            elif clean_path == "/decide":
                resp_data = self._handle_generalized_decide(req_data)
            elif clean_path == "/api/save":
                resp_data = self._handle_api_save(req_data)
            elif clean_path == "/api/wild_encounter":
                resp_data = self._handle_wild_encounter(req_data)
            elif clean_path == "/api/pokemon/create":
                resp_data = self._handle_pokemon_create(req_data)
            else:
                self._set_headers(404)
                self.wfile.write(json.dumps({"error": f"Unknown endpoint: {self.path}"}).encode("utf-8"))
                return

            self._set_headers(200)
            self.wfile.write(json.dumps(resp_data).encode("utf-8"))

        except Exception as exc:
            self._set_headers(500)
            self.wfile.write(json.dumps({"error": f"Inference/backend failure: {exc}"}).encode("utf-8"))

    def _handle_api_save(self, data: dict[str, Any]) -> dict[str, Any]:
        """Validates and persists game save via Python SaveManager."""
        save_path = repo_root / "save_game.json"
        
        # In Godot, save data might have top-level wrapper or direct player fields
        player_dict = data.get("player", data)
        # Ensure collection items have integer bond/obedience
        col = player_dict.get("collection", [])
        for mon_d in col:
            if isinstance(mon_d, dict):
                if "bond" in mon_d and isinstance(mon_d["bond"], (int, float)):
                    mon_d["bond"] = int(round(mon_d["bond"]))
                if "obedience" in mon_d and isinstance(mon_d["obedience"], (int, float)):
                    mon_d["obedience"] = int(round(mon_d["obedience"]))
        
        # Deserialize to validate
        player = deserialize_player(player_dict)
        save_game(player, save_path)
        
        # If extra fields were passed (like current_region_id, game_time), ensure they are in file
        try:
            with open(save_path, "r", encoding="utf-8") as f:
                saved_json = json.load(f)
            if "current_region_id" in data:
                saved_json["current_region_id"] = data["current_region_id"]
            if "game_time" in data:
                saved_json["game_time"] = data["game_time"]
            if "discovered_regions" in data:
                saved_json["discovered_regions"] = data["discovered_regions"]
            if "discovered_landmarks" in data:
                saved_json["discovered_landmarks"] = data["discovered_landmarks"]
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(saved_json, f, indent=2)
        except Exception:
            pass

        return {
            "success": True,
            "player_name": player.name,
            "collection_count": len(player.collection),
            "timestamp": time.time(),
        }

    def _handle_wild_encounter(self, data: dict[str, Any]) -> dict[str, Any]:
        """Selects a wild spawn candidate from HabitatManager and instantiates Pokemon."""
        region_id = data.get("region_id", "starting_meadow")
        tod_str = str(data.get("time_of_day", "day")).lower()
        tod = TimeOfDay.NIGHT if tod_str in ("night", "dusk") else TimeOfDay.DAY
        
        hm = get_habitat_manager()
        spawn = hm.select_spawn(region_id=region_id, time_of_day=tod)
        if not spawn or not spawn.success or not spawn.species:
            # Fallback to a base species
            sp_name = random.choice(["Rattata", "Pidgey", "Pikachu"])
            sp = SAMPLE_SPECIES.get(sp_name, SAMPLE_SPECIES["Pikachu"])
            level = random.randint(2, 5)
        else:
            sp = spawn.species
            level = spawn.level or random.randint(2, 5)

        pers = Personality(
            aggression=random.randint(1, 100),
            curiosity=random.randint(1, 100),
            fear=random.randint(1, 100),
            sociability=random.randint(1, 100),
            loyalty=random.randint(1, 100),
            confidence=random.randint(1, 100),
        )
        moves = list(sp.available_attacks)[:4]
        mon = Pokemon(species=sp, level=level, personality=pers, attacks=moves)
        return {
            "success": True,
            "pokemon": _serialize_pokemon_dict(mon),
        }

    def _handle_pokemon_create(self, data: dict[str, Any]) -> dict[str, Any]:
        """Creates a customized Pokemon using backend rules."""
        sp_name = data.get("species", "Charmander")
        sp = SAMPLE_SPECIES.get(sp_name, SAMPLE_SPECIES.get("Pikachu"))
        level = int(data.get("level", 5))
        nickname = data.get("nickname", sp.name)
        
        p_data = data.get("personality", {})
        pers = Personality(
            aggression=int(p_data.get("aggression", random.randint(1, 100))),
            curiosity=int(p_data.get("curiosity", random.randint(1, 100))),
            fear=int(p_data.get("fear", random.randint(1, 100))),
            sociability=int(p_data.get("sociability", random.randint(1, 100))),
            loyalty=int(p_data.get("loyalty", random.randint(1, 100))),
            confidence=int(p_data.get("confidence", random.randint(1, 100))),
        )
        moves = list(sp.available_attacks)[:4]
        mon = Pokemon(species=sp, level=level, personality=pers, attacks=moves)
        if nickname:
            mon.nickname = nickname
        return {
            "success": True,
            "pokemon": _serialize_pokemon_dict(mon),
        }

    def _handle_companion_talk(self, data: dict[str, Any]) -> dict[str, Any]:
        """Handles companion conversation dialogue using bonding adapter."""
        species = data.get("species", "Charmander")
        player_name = data.get("player_name", "Trainer")
        user_message = data.get("message", "Hello partner!")
        temperament = data.get("temperament", "bold")
        trust = float(data.get("trust", 30.0))
        affection = float(data.get("affection", 30.0))

        # Synthetic agent setup
        identity = AgentIdentity(
            species=species,
            nickname=data.get("nickname", species),
            temperament=temperament,
            communication_style="affectionate",
            personality_traits=data.get("personality_traits", {
                "aggression": 40, "curiosity": 65, "fear": 20, "confidence": 70, "loyalty": 85, "sociability": 75
            }),
        )
        agent = PokemonAgent(
            agent_id=f"companion_{species.lower()}",
            identity=identity,
            is_captured=True,
            is_wild=False,
        )
        rel = agent.get_relationship(player_name, default_name=player_name, default_type="trainer")
        rel.trust = trust
        rel.affection = affection

        perception = AgentPerception(
            agent_id=agent.agent_id,
            species=species,
            physical_state={"hp_ratio": float(data.get("hp_ratio", 1.0))},
            trainer_context={
                "trainer_id": player_name,
                "trainer_name": player_name,
                "command": user_message,
                "command_intent": "praise" if any(w in user_message.lower() for w in ["good", "great", "proud", "amazing", "best"]) else "talk",
                "trust": trust,
                "affection": affection,
                "relationship_stage": "companion",
            },
            environment_context={"in_battle": False},
            available_actions=["interact", "obey", "suggest", "protest", "rest"],
        )

        decision = self.provider.decide(agent, perception)

        # Dynamic relationship delta parsed from model response
        trust_delta = float(getattr(decision, "trust_delta", 2.0) or 2.0)
        affection_delta = float(getattr(decision, "affection_delta", 3.0) or 3.0)

        return {
            "species": species,
            "dialogue": decision.dialogue or f"{species} looks at you happily!",
            "emotional_state": decision.emotional_state or "pleased",
            "action_type": decision.action_type.value,
            "intent": decision.intent,
            "confidence": decision.confidence,
            "trust_delta": trust_delta,
            "affection_delta": affection_delta,
            "new_trust": round(trust + trust_delta, 1),
            "new_affection": round(affection + affection_delta, 1),
        }

    def _handle_battle_decide(self, data: dict[str, Any]) -> dict[str, Any]:
        """Handles combat turn decisions using battle adapter."""
        active = data.get("active_pokemon", {})
        opponent = data.get("opponent_pokemon", {})
        known_moves = active.get("known_moves", ["Tackle"])
        species = active.get("species", "Pikachu")
        opp_species = opponent.get("species", "Opponent")

        identity = AgentIdentity(
            species=species,
            nickname=active.get("nickname", species),
            temperament="focused",
            communication_style="tactical",
            personality_traits={"aggression": 60, "curiosity": 50, "fear": 20, "confidence": 75, "loyalty": 80, "sociability": 50},
        )
        agent = PokemonAgent(
            agent_id=f"mon_{species.lower()}",
            identity=identity,
            is_captured=True,
            is_wild=False,
        )

        perception = AgentPerception(
            agent_id=agent.agent_id,
            species=species,
            physical_state={
                "level": active.get("level", 10),
                "current_hp": active.get("current_hp", 30),
                "max_hp": active.get("max_hp", 30),
                "hp_ratio": active.get("current_hp", 30) / max(1, active.get("max_hp", 30)),
                "known_moves": known_moves,
            },
            opponent_context={
                "species": opp_species,
                "level": opponent.get("level", 10),
                "apparent_health": opponent.get("apparent_health", "healthy"),
            },
            environment_context={
                "in_battle": True,
                "is_trainer_battle": data.get("is_trainer_battle", False),
                "current_turn": data.get("current_turn", 1),
            },
            available_actions=["attack", "defend", "flee"],
        )

        decision = self.provider.decide(agent, perception)

        # Enforce legal move constraint authoritatively
        chosen_move = decision.chosen_move
        if decision.action_type.value == "attack":
            if chosen_move not in known_moves:
                chosen_move = known_moves[0] if known_moves else "Tackle"

        return {
            "action_type": decision.action_type.value,
            "chosen_move": chosen_move,
            "dialogue": decision.dialogue or f"{species} readied its attack!",
            "emotional_state": decision.emotional_state or "focused",
            "confidence": decision.confidence,
            "rationale": decision.rationale,
        }

    def _handle_generalized_decide(self, data: dict[str, Any]) -> dict[str, Any]:
        """Handles full AgentPerception payload."""
        agent = PokemonAgent.from_dict(data["agent"])
        perception = AgentPerception.from_dict(data["perception"])
        decision = self.provider.decide(agent, perception)
        return decision.to_dict()

    def log_message(self, format: str, *args) -> None:
        """Custom minimal HTTP request logging."""
        sys.stderr.write(f"[LLM Server] {self.address_string()} - {format % args}\n")


class ReusableHTTPServer(HTTPServer):
    allow_reuse_address = True


def run_server(host: str = "127.0.0.1", port: int = 8008) -> None:
    print("=" * 60)
    print(" Syntax Error 26 — Local Pokémon LLM Bridge Server")
    print(f" Target: http://{host}:{port}")
    print("=" * 60)

    try:
        server = ReusableHTTPServer((host, port), LLMBridgeHandler)
    except OSError as err:
        if err.errno == 48:
            print(f"\n[!] Port {port} is already in use by another instance.")
            print(f"    To see what is using it: lsof -i :{port}")
            print(f"    Or specify another port: python3 server.py --port {port+1}\n")
            sys.exit(1)
        raise

    print("Initializing LocalModelDecisionProvider (4-bit MLX weights)...")
    provider = LocalModelDecisionProvider(allow_mock_fallback=True)
    provider.load_model(adapter_path=provider.bonding_adapter_path)
    LLMBridgeHandler.provider = provider
    print(f"[OK] Local LLM Model Loaded and Ready on http://{host}:{port}!")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")
    finally:
        server.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Local Pokemon LLM HTTP Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host address")
    parser.add_argument("--port", type=int, default=8008, help="Port number")
    args = parser.parse_args()
    run_server(args.host, args.port)
