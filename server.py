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

from src.ai.local_model_provider import LocalModelDecisionProvider
from src.ai.agent import PokemonAgent, AgentIdentity
from src.ai.perception import AgentPerception
from src.models.personality import Personality


class LLMBridgeHandler(BaseHTTPRequestHandler):
    provider: LocalModelDecisionProvider = None

    def _send_json_response(self, status: int, data: dict[str, Any]) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)
        self.wfile.flush()

    def do_OPTIONS(self) -> None:
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.send_header("Connection", "close")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        if self.path == "/health" or self.path == "/":
            payload = {
                "status": "online",
                "backend": "mlx_4bit",
                "model": "Qwen3-4B-4bit",
                "adapters": ["bonding_adapter", "battle_adapter"],
                "timestamp": time.time(),
            }
            self._send_json_response(200, payload)
        else:
            self._send_json_response(404, {"error": "Not found"})

    def do_POST(self) -> None:
        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length).decode("utf-8")
        
        try:
            req_data = json.loads(raw_body) if raw_body else {}
        except Exception as exc:
            self._send_json_response(400, {"error": f"Invalid JSON body: {exc}"})
            return

        try:
            if self.path == "/companion/talk":
                resp_data = self._handle_companion_talk(req_data)
            elif self.path == "/battle/decide":
                resp_data = self._handle_battle_decide(req_data)
            elif self.path == "/decide":
                resp_data = self._handle_generalized_decide(req_data)
            else:
                self._send_json_response(404, {"error": f"Unknown endpoint: {self.path}"})
                return

            self._send_json_response(200, resp_data)

        except Exception as exc:
            self._send_json_response(500, {"error": f"Inference failure: {exc}"})

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
        print(f"[Companion Talk] {species} -> \"{decision.dialogue}\" ({decision.emotional_state})")

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
    provider.load_model()
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
