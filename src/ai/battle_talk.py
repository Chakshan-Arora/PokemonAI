"""
Battle Talk intent interpretation and conversational handling for Syntax Error 26 (BT2B).

Provides:
- parse_battle_talk_intent: deterministic keyword/rule-based intent parser
- generate_battle_talk_response: personality-aware, cosmetic dialogue generator
"""
from typing import Optional, Union, Any

from src.models.battle import (
    BattleTalkCommand,
    BattleTalkIntent,
    TalkCategory,
)
from src.ai.battle_talk_parser import BattleTalkParser
from src.ai.companion_service import BattleTalkContext


def parse_battle_talk_intent(text: str) -> BattleTalkIntent:
    """
    Deterministically parses player text into a BattleTalkIntent.

    Rules:
      - Normalizes text.
      - Recognizes PRAISE, ENCOURAGE, WARNING, and GENERAL intents.
      - Empty, unclassified, or ambiguous phrases safely fall back to GENERAL.
    """
    if not isinstance(text, str):
        return BattleTalkIntent.GENERAL

    cmd = BattleTalkParser.parse(text)
    raw_intent = cmd.intent
    if isinstance(raw_intent, BattleTalkIntent):
        return raw_intent
    elif isinstance(raw_intent, str):
        try:
            return BattleTalkIntent(raw_intent)
        except ValueError:
            return BattleTalkIntent.GENERAL
    return BattleTalkIntent.GENERAL


def generate_battle_talk_response(
    pokemon: Any,
    intent_or_command: Union[BattleTalkIntent, BattleTalkCommand, str],
    context: Optional[Any] = None,
) -> str:
    """
    Generates a deterministic, personality-aware, cosmetic dialogue response
    reflecting the Pokemon's reaction to the trainer's words and battle context.

    Strictly cosmetic:
      - Does not alter combat state, HP, stats, bond, obedience, or personality.
      - Does not claim physical actions (dodges, blocks, attacks).
    """
    from src.ai.companion_service import CompanionService

    if isinstance(intent_or_command, BattleTalkIntent):
        cmd = BattleTalkCommand(text="", intent=intent_or_command)
        return CompanionService.generate_battle_talk_response(pokemon, cmd, context=context)
    return CompanionService.generate_battle_talk_response(pokemon, intent_or_command, context=context)
