"""
Battle Talk public interface and coordination for Syntax Error 26.
Integrates parser, companion reaction, tactical matchup advisor, and battle talk generation.
"""
from typing import Any, Dict, Optional, Union

from src.ai.battle_talk_parser import (
    BattleTalkCommand,
    BattleTalkIntent,
    BattleTalkParser,
    TalkCategory,
    parse_battle_talk,
)


def parse_battle_talk_intent(text: str) -> BattleTalkIntent:
    """Parses player combat utterance into a BattleTalkIntent."""
    cmd = BattleTalkParser.parse(text)
    if isinstance(cmd.intent, BattleTalkIntent):
        return cmd.intent
    try:
        return BattleTalkIntent(cmd.intent)
    except Exception:
        return BattleTalkIntent.GENERAL


def generate_battle_talk_response(
    species: str,
    nickname: str = "",
    message: str = "",
    personality: Optional[Dict[str, Any]] = None,
    temperament: str = "bold",
    bond: float = 50.0,
    obedience: float = 70.0,
    battle_context: Optional[Dict[str, Any]] = None,
    is_opponent: bool = False,
    opponent_archetype: str = "wild",
) -> Dict[str, Any]:
    """Generates battle talk response using the deterministic engine."""
    p_dict = personality or {"aggression": 50, "loyalty": 50, "confidence": 50, "fear": 20}
    ctx = battle_context or {}
    return BattleTalkParser.generate_fallback_response(
        species=species,
        nickname=nickname or species,
        message=message,
        personality=p_dict,
        temperament=temperament,
        bond=bond,
        obedience=obedience,
        battle_context=ctx,
        is_opponent=is_opponent,
        opponent_archetype=opponent_archetype,
    )
