"""
Syntax Error 26 — Local Pokémon LLM & Backend API Bridge Server.
Provides high-performance, low-latency REST endpoints for the Godot 3D Frontend:
- GET  /health           : Health check and model metadata
- GET  /api/data         : Exports all backend Pokémon, attacks, items, quests, and habitats
- GET  /api/load         : Loads verified player save state from disk
- POST /api/save         : Persists player state through authoritative SaveManager
- POST /api/wild_encounter: Spawns wild encounter from HabitatManager with true species & personality
- POST /api/pokemon/create: Generates custom Pokémon instance using backend rules
- POST /companion/talk   : Interactive partner Pokémon bonding dialogue with sentiment dynamics
- POST /battle/decide    : Battle turn tactical move selection and combat dialogue
- POST /decide           : Generalized agent decision endpoint
"""
import argparse
import json
import os
import random
import re
import sys
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Optional
from dotenv import load_dotenv

# Ensure project root is in sys.path and load environment variables
repo_root = Path(__file__).resolve().parent
sys.path.insert(0, str(repo_root))
load_dotenv()
load_dotenv(repo_root / ".env")

from export_backend_data import build_backend_data
from src.models.save_manager import load_game, save_game, serialize_player, deserialize_player
from src.models.habitat_manager import HabitatManager
from src.models.habitat import TimeOfDay
from src.data.species import SAMPLE_SPECIES
from src.models.personality import Personality
from src.models.pokemon import Pokemon
from src.models.trainer_team_generator import TrainerTeamGenerator
from src.ai.decision_provider import DecisionProvider, FallbackDecisionHandler
from src.ai.live_provider import create_live_decision_provider
from src.ai.local_model_provider import LocalModelDecisionProvider
from src.ai.agent import PokemonAgent, AgentIdentity
from src.ai.perception import AgentPerception
from src.ai.battle_talk_parser import BattleTalkParser

VERY_NEGATIVE_PHRASES = [
    "hate you", "despise you", "loathe you", "shut up", "get lost", "get out",
    "go away", "drop dead", "kill yourself", "die already", "waste of space",
    "piece of trash", "piece of garbage", "regret catching you", "regret picking you",
    "never liked you", "dont want you", "don't want you", "throw you away",
    "worthless pokemon", "useless pokemon", "stupid pokemon", "pathetic pokemon",
    "abandon you", "replace you", "worst pokemon", "ugly pokemon", "go to hell",
    "f off", "fk off", "fuck off",
]

VERY_NEGATIVE_WORDS = {
    "stupid", "idiot", "dumb", "moron", "useless", "worthless", "pathetic",
    "garbage", "trash", "disgusting", "horrible", "terrible", "worst", "loser",
    "freak", "scum", "weakling", "failure", "hate", "despise", "loathe", "kill", "die",
    "ugly",
}

NEGATIVE_PHRASES = [
    "not good", "not great", "not happy", "dont like", "don't like",
    "bad job", "poor job", "stop that", "stop it", "quit it", "cut it out",
    "listen to me", "be quiet", "do better", "mess up", "messed up",
    "made a mistake", "not good enough", "why did you", "stop messing",
    "poor performance", "let down", "wake up",
]

NEGATIVE_WORDS = {
    "bad", "disappointed", "disappointing", "annoying", "annoyed", "clumsy",
    "slow", "lazy", "careless", "mistake", "wrong", "fail", "failed", "failing",
    "weak", "boring", "irritating", "troublesome", "disobedient", "stubborn",
}

POSITIVE_PHRASES = [
    "good job", "great job", "awesome job", "well done", "proud of you",
    "love you", "love ya", "i love", "not bad", "best partner", "good boy",
    "good girl", "good pokemon", "great pokemon", "nice work", "super star",
    "thank you", "thanks a lot", "so proud",
]

POSITIVE_WORDS = {
    "good", "great", "awesome", "amazing", "wonderful", "fantastic", "excellent",
    "brilliant", "super", "proud", "love", "loved", "lovely", "cute", "sweet",
    "precious", "adorable", "best", "hero", "strong", "brave", "clever", "smart",
    "genius", "perfect", "friend", "buddy", "pal", "cherish", "treat", "congrats",
    "congratulations", "thanks", "thank",
}

NEGATIONS = {
    "not", "no", "never", "dont", "don't", "isnt", "isn't", "arent", "aren't",
    "wont", "won't", "cannot", "can't", "cant", "hardly", "barely", "neither",
}


def classify_companion_sentiment(text: str) -> str:
    """
    Classifies player comment into 'very_negative', 'negative', 'positive', or 'neutral'.
    Handles phrase patterns, single token semantics, and negation windows.
    """
    cleaned = text.lower().strip()

    # Pre-emptively normalize negated very negative expressions so substrings don't falsely match
    negated_very_neg = [
        "don't hate", "dont hate", "do not hate", "not hate", "never hate",
        "not stupid", "not dumb", "not useless", "not worthless", "not ugly",
        "not pathetic", "not trash", "not a failure", "not garbage",
    ]
    for np in negated_very_neg:
        if np in cleaned:
            cleaned = cleaned.replace(np, "appreciate")

    # 1. Direct multi-word phrase matching
    for phrase in VERY_NEGATIVE_PHRASES:
        if phrase in cleaned:
            return "very_negative"

    for phrase in POSITIVE_PHRASES:
        if phrase in cleaned:
            return "positive"

    for phrase in NEGATIVE_PHRASES:
        if phrase in cleaned:
            return "negative"

    # 2. Token-level analysis with negation detection
    words = re.findall(r"[a-zA-Z']+", cleaned)
    has_very_neg = False
    has_neg = False
    has_pos = False

    for idx, word in enumerate(words):
        negated = False
        start_lookback = max(0, idx - 2)
        for prev in words[start_lookback:idx]:
            if prev in NEGATIONS:
                negated = True
                break

        if word in VERY_NEGATIVE_WORDS:
            if negated:
                has_pos = True  # e.g. 'not stupid'
            else:
                has_very_neg = True
        elif word in NEGATIVE_WORDS:
            if negated:
                has_pos = True  # e.g. 'not bad'
            else:
                has_neg = True
        elif word in POSITIVE_WORDS:
            if negated:
                has_neg = True  # e.g. 'not good'
            else:
                has_pos = True

    if has_very_neg:
        return "very_negative"
    if has_neg and not has_pos:
        return "negative"
    if has_pos and not has_neg:
        return "positive"
    if has_pos and has_neg:
        return "negative"
    return "neutral"


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
    provider: DecisionProvider = None

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

    def do_OPTIONS(self) -> None:
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

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
                    "/battle/talk",
                    "/battle/decide",
                    "/decide",
                ],
                "timestamp": time.time(),
            }
            self._send_json_response(200, payload)

        elif clean_path == "/api/data":
            try:
                data = build_backend_data()
                self._send_json_response(200, data)
            except Exception as exc:
                self._send_json_response(500, {"error": f"Failed to build backend data: {exc}"})

        elif clean_path in ("/api/load", "/api/save"):
            try:
                save_path = repo_root / "save_game.json"
                if not save_path.exists():
                    self._send_json_response(404, {"error": "No save file found"})
                    return
                player = load_game(save_path)
                serialized = serialize_player(player)
                self._send_json_response(200, serialized)
            except Exception as exc:
                self._send_json_response(500, {"error": f"Failed to load save file: {exc}"})

        else:
            self._send_json_response(404, {"error": f"Not found: {clean_path}"})

    def do_POST(self) -> None:
        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length).decode("utf-8")
        
        try:
            req_data = json.loads(raw_body) if raw_body else {}
        except Exception as exc:
            self._send_json_response(400, {"error": f"Invalid JSON body: {exc}"})
            return

        clean_path = self.path.split("?")[0]
        try:
            if clean_path == "/api/save":
                resp_data = self._handle_api_save(req_data)
            elif clean_path == "/api/wild_encounter":
                resp_data = self._handle_wild_encounter(req_data)
            elif clean_path == "/api/pokemon/create":
                resp_data = self._handle_pokemon_create(req_data)
            elif clean_path == "/companion/talk":
                resp_data = self._handle_companion_talk(req_data)
            elif clean_path == "/battle/talk":
                resp_data = self._handle_battle_talk(req_data)
            elif clean_path == "/battle/decide":
                resp_data = self._handle_battle_decide(req_data)
            elif clean_path == "/decide":
                resp_data = self._handle_generalized_decide(req_data)
            else:
                self._send_json_response(404, {"error": f"Unknown endpoint: {clean_path}"})
                return

            self._send_json_response(200, resp_data)

        except Exception as exc:
            self._send_json_response(500, {"error": f"Inference failure: {exc}"})

    def _handle_api_save(self, data: dict[str, Any]) -> dict[str, Any]:
        """Saves player state through authoritative SaveManager."""
        save_path = repo_root / "save_game.json"
        
        player_dict = data.get("player", data)
        if "inventory" in data and "inventory" not in player_dict:
            player_dict = data
        if "collection" in data and "collection" not in player_dict:
            player_dict = data

        # Ensure collection items have integer bond/obedience/personality
        col = player_dict.get("collection", [])
        for mon_d in col:
            if isinstance(mon_d, dict):
                if "bond" in mon_d and isinstance(mon_d["bond"], (int, float)):
                    mon_d["bond"] = int(round(mon_d["bond"]))
                if "obedience" in mon_d and isinstance(mon_d["obedience"], (int, float)):
                    mon_d["obedience"] = int(round(mon_d["obedience"]))
                if "personality" in mon_d and isinstance(mon_d["personality"], dict):
                    for pk, pv in list(mon_d["personality"].items()):
                        if isinstance(pv, (int, float)) and not isinstance(pv, bool):
                            mon_d["personality"][pk] = int(round(pv))

        # Ensure inventory item quantities are strictly integers
        inv = player_dict.get("inventory", {})
        if isinstance(inv, dict):
            items = inv.get("items", {})
            if isinstance(items, dict):
                for item_id, qty in list(items.items()):
                    if isinstance(qty, (int, float)) and not isinstance(qty, bool):
                        items[item_id] = int(round(qty))
        
        player = deserialize_player(player_dict)
        save_game(player, save_path)
        
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
            # Double check inventory item counts in file are integer
            if "inventory" in saved_json and isinstance(saved_json["inventory"], dict):
                s_items = saved_json["inventory"].get("items", {})
                if isinstance(s_items, dict):
                    for k, v in list(s_items.items()):
                        if isinstance(v, (int, float)) and not isinstance(v, bool):
                            s_items[k] = int(round(v))
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
        moves = TrainerTeamGenerator.generate_moveset(sp, level)
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
        moves = TrainerTeamGenerator.generate_moveset(sp, level)
        mon = Pokemon(species=sp, level=level, personality=pers, attacks=moves)
        if nickname:
            mon.nickname = nickname
        return {
            "success": True,
            "pokemon": _serialize_pokemon_dict(mon),
        }

    def _handle_companion_talk(self, data: dict[str, Any]) -> dict[str, Any]:
        """Handles companion conversation dialogue using bonding adapter with authoritative sentiment guardrails."""
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

        # Authoritative sentiment classification
        sentiment = classify_companion_sentiment(user_message)
        command_intent = {
            "very_negative": "insult",
            "negative": "criticism",
            "positive": "praise",
            "neutral": "talk",
        }.get(sentiment, "talk")

        perception = AgentPerception(
            agent_id=agent.agent_id,
            species=species,
            physical_state={"hp_ratio": float(data.get("hp_ratio", 1.0))},
            trainer_context={
                "trainer_id": player_name,
                "trainer_name": player_name,
                "command": user_message,
                "command_intent": command_intent,
                "sentiment": sentiment,
                "trust": trust,
                "affection": affection,
                "relationship_stage": "companion",
            },
            environment_context={"in_battle": False},
            available_actions=["interact", "obey", "suggest", "protest", "rest"],
        )

        decision = self.provider.decide(agent, perception)

        # Guard against defensive battle fallback dialogue leaking into companion talk
        if not decision.dialogue or "held its ground defensively" in decision.dialogue.lower():
            decision = FallbackDecisionHandler.create_fallback(agent, perception, Exception("Companion dialogue rescue"))

        print(f"[Companion Talk] {species} -> \"{decision.dialogue}\" ({decision.emotional_state}) [Sentiment: {sentiment}]")

        # Parse raw decision deltas from model
        raw_t_delta = getattr(decision, "trust_delta", None)
        raw_a_delta = getattr(decision, "affection_delta", None)
        try:
            model_t_delta = float(raw_t_delta) if raw_t_delta is not None else None
        except (ValueError, TypeError):
            model_t_delta = None

        try:
            model_a_delta = float(raw_a_delta) if raw_a_delta is not None else None
        except (ValueError, TypeError):
            model_a_delta = None

        # Authoritative Sentiment & Relationship Guardrails
        emotional_state = decision.emotional_state or "neutral"

        if sentiment == "very_negative":
            # Very negative comments: trust and affection MUST decrease (< 0.0)
            if model_t_delta is not None and model_t_delta < 0.0:
                trust_delta = max(-5.0, min(-2.0, model_t_delta))
            else:
                trust_delta = -3.0

            if model_a_delta is not None and model_a_delta < 0.0:
                affection_delta = max(-5.0, min(-2.5, model_a_delta))
            else:
                affection_delta = -4.0

            if emotional_state.lower() in ("pleased", "happy", "excited", "affectionate", "content", "bold", "confident", "joyful", "thoughtful"):
                emotional_state = "hurt"

        elif sentiment == "negative":
            # Negative comments: trust and affection MUST be 0.0
            trust_delta = 0.0
            affection_delta = 0.0

            if emotional_state.lower() in ("pleased", "happy", "excited", "affectionate", "content", "bold", "confident", "joyful", "thoughtful"):
                emotional_state = "discouraged"

        elif sentiment == "positive":
            # Positive comments: trust and affection increase
            if model_t_delta is not None and model_t_delta > 0.0:
                trust_delta = max(1.0, min(5.0, model_t_delta))
            else:
                trust_delta = 2.5

            if model_a_delta is not None and model_a_delta > 0.0:
                affection_delta = max(1.5, min(5.0, model_a_delta))
            else:
                affection_delta = 3.5

            if emotional_state.lower() in ("neutral", "discouraged", "hurt", "sad", "confused"):
                emotional_state = "happy"

        else:  # neutral
            # Casual conversation: modest or zero change
            if model_t_delta is not None:
                trust_delta = max(0.0, min(1.0, model_t_delta))
            else:
                trust_delta = 0.5

            if model_a_delta is not None:
                affection_delta = max(0.0, min(1.0, model_a_delta))
            else:
                affection_delta = 0.5

            if not emotional_state or emotional_state.lower() in ("hurt", "angry"):
                emotional_state = "thoughtful"

        new_trust = round(max(0.0, min(100.0, trust + trust_delta)), 1)
        new_affection = round(max(0.0, min(100.0, affection + affection_delta)), 1)

        return {
            "species": species,
            "dialogue": decision.dialogue or f"{species} looks at you attentively.",
            "emotional_state": emotional_state,
            "action_type": decision.action_type.value,
            "intent": decision.intent,
            "confidence": decision.confidence,
            "sentiment": sentiment,
            "trust_delta": round(trust_delta, 1),
            "affection_delta": round(affection_delta, 1),
            "new_trust": new_trust,
            "new_affection": new_affection,
        }

    def _handle_battle_talk(self, data: dict[str, Any]) -> dict[str, Any]:
        """Handles mid-combat trainer/opponent communication via LLM or deterministic fallback."""
        species = data.get("species", "Pikachu")
        nickname = data.get("nickname", species)
        message = data.get("message", "")
        personality = data.get("personality", {
            "aggression": 50, "loyalty": 70, "confidence": 60, "fear": 20, "curiosity": 50, "sociability": 50
        })
        temperament = data.get("temperament", "bold")
        bond = float(data.get("bond", 50.0))
        obedience = float(data.get("obedience", 70.0))
        battle_context = data.get("battle_context", {})
        is_opponent = bool(data.get("is_opponent", False))
        opponent_archetype = str(data.get("opponent_archetype", "wild"))

        fallback = BattleTalkParser.generate_fallback_response(
            species=species,
            nickname=nickname,
            message=message,
            personality=personality,
            temperament=temperament,
            bond=bond,
            obedience=obedience,
            battle_context=battle_context,
            is_opponent=is_opponent,
            opponent_archetype=opponent_archetype,
        )

        # If LLM model is loaded with generation capability, invoke it
        if self.provider and getattr(self.provider, "is_loaded", False):
            try:
                if hasattr(self.provider, "generate_raw"):
                    prompt = BattleTalkParser.build_prompt(
                        species=species,
                        nickname=nickname,
                        message=message,
                        personality=personality,
                        temperament=temperament,
                        bond=bond,
                        obedience=obedience,
                        battle_context=battle_context,
                        is_opponent=is_opponent,
                        opponent_archetype=opponent_archetype,
                    )
                    raw_out = self.provider.generate_raw(
                        system_instruction="You are a tactical Pokemon battle LLM.",
                        user_prompt=prompt,
                        max_tokens=150,
                        use_battle_adapter=True,
                    )
                    return BattleTalkParser.parse_llm_response(raw_out, fallback)
            except Exception as exc:
                sys.stderr.write(f"[LLM Server] Battle talk LLM inference fallback triggered: {exc}\n")

        return fallback

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


def run_server(
    host: str = "127.0.0.1",
    port: int = 8008,
    provider_type: str = "auto",
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> None:
    print("=" * 60)
    print(" Syntax Error 26 — Pokémon AI & LLM Bridge Server")
    print(f" Target: http://{host}:{port}")
    print("=" * 60)

    try:
        server = ReusableHTTPServer((host, port), LLMBridgeHandler)
    except OSError as err:
        if err.errno in (48, 10048):
            print(f"\n[!] Port {port} is already in use by another instance.")
            print(f"    Or specify another port: python server.py --port {port+1}\n")
            sys.exit(1)
        raise

    print(f"Initializing AI Decision Provider (mode: {provider_type})...")
    provider = create_live_decision_provider(
        provider_type=provider_type,
        api_key=api_key,
        model_name=model,
        allow_mock_fallback=True,
    )
    if hasattr(provider, "load_model"):
        try:
            provider.load_model()
        except Exception:
            pass

    LLMBridgeHandler.provider = provider

    # Log active provider status
    if hasattr(provider, "is_configured") and provider.is_configured():
        act_p = getattr(provider, "active_provider", provider)
        p_name = getattr(act_p, "provider_name", type(act_p).__name__)
        m_name = getattr(act_p, "model_name", "default")
        print(f"[OK] Live Cloud AI Provider Connected: {p_name} ({m_name})")
    elif getattr(provider, "is_loaded", False):
        print(f"[OK] Local LLM Model Loaded: {getattr(provider, 'model_name_or_path', 'Local')}")
    else:
        print("[OK] Autonomous Companion Engine Active (Offline Mode).")
        print("     To connect live Cloud LLM, set GEMINI_API_KEY or OPENAI_API_KEY in .env")

    print(f"[OK] LLM Bridge Server Ready and Listening on http://{host}:{port}!")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")
    finally:
        server.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Pokemon AI LLM HTTP Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host address")
    parser.add_argument("--port", type=int, default=8008, help="Port number")
    parser.add_argument(
        "--provider",
        default=os.environ.get("POKEMON_AI_PROVIDER", "auto"),
        help="AI Provider: auto, gemini, openai, ollama, local, mock"
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY"),
        help="API Key for live cloud AI"
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("POKEMON_AI_MODEL"),
        help="Model name override (e.g. gemini-2.5-flash, gpt-4o-mini)"
    )
    args = parser.parse_args()
    run_server(args.host, args.port, provider_type=args.provider, api_key=args.api_key, model=args.model)
