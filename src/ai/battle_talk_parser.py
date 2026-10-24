"""
Rule-based, deterministic natural language intent parser for Syntax Error 26 Battle Talk (BT2.2).
Converts player battle messages into structured BattleTalkCommand objects without external APIs or LLMs.

Recognized intents:
- PRAISE: praise, compliments, recognition of good performance
- ENCOURAGE: reassurance, motivation, confidence-building
- WARNING: cautionary or defensive language, without executing tactical manoeuvres
- GENERAL: greetings, ordinary conversation, and unmatched input

Tactical commands:
- Explicit requests for physical battle manoeuvres (dodge, evade, jump, block) are
  flagged as tactical (is_tactical=True, TalkCategory.TACTICAL) so the authoritative
  battle engine can safely reject them as unsupported.
"""
import re
from typing import Optional, Union, Any

from src.models.battle import (
    BattleTalkCommand,
    BattleTalkIntent,
    TalkCategory,
)


# Tactical manoeuvre patterns (commands for physical actions)
_TACTICAL_PATTERNS = [
    re.compile(r"\b(dodge|dodging|evade|evading|sidestep|sidestepping|duck|ducking)\b", re.IGNORECASE),
    re.compile(r"\b(jump\s+(?:over|away|aside|up|back)|leap\s+(?:away|aside|back))\b", re.IGNORECASE),
    re.compile(r"\b(block\s+it|block\s+the\s+attack|parry|parry\s+it|take\s+cover)\b", re.IGNORECASE),
]

# Negated tactical manoeuvre patterns (e.g. "Don't dodge!", "Do not evade!")
_NEGATED_TACTICAL_PATTERNS = [
    re.compile(
        r"\b(don'?t|do\s+not|never|no|stop|cannot|can'?t|refrain\s+from)\s+(?:try\s+to\s+|attempt\s+to\s+)?(dodge|dodging|evade|evading|sidestep|sidestepping|duck|ducking|jump|block|parry)\b",
        re.IGNORECASE,
    ),
]

# Greeting patterns (must precede generic praise to avoid 'good morning' -> PRAISE)
_GREETING_PATTERNS = [
    re.compile(r"\b(good\s+(?:morning|afternoon|evening|day|night))\b", re.IGNORECASE),
    re.compile(r"\b(hello|hi|hey|greetings|howdy|sup|what'?s\s+up|how\s+are\s+you)\b", re.IGNORECASE),
]

# Warning patterns (cautionary / alert phrasing)
_WARNING_PATTERNS = [
    re.compile(r"\b(watch\s+out|look\s+out|heads\s+up|be\s+careful|stay\s+alert|stay\s+sharp)\b", re.IGNORECASE),
    re.compile(r"\b(incoming|danger|behind\s+you|on\s+guard|look\s+alive|watch\s+your\s+back)\b", re.IGNORECASE),
    re.compile(r"\b(keep\s+your\s+guard\s+up|eyes\s+open|caution|stay\s+on\s+guard)\b", re.IGNORECASE),
    re.compile(r"\b(?:^|[,\.!?]\s*)careful\b", re.IGNORECASE),
]

# Praise patterns (recognition, compliments, celebration of good performance)
_PRAISE_PATTERNS = [
    re.compile(r"\b(good\s+job|great\s+job|well\s+done|nice\s+job|nice\s+work|awesome\s+job)\b", re.IGNORECASE),
    re.compile(r"\b(nice\s+(?:hit|move|strike|attack|one|shot))\b", re.IGNORECASE),
    re.compile(r"\b(good\s+(?:hit|move|strike|attack|boy|girl))\b", re.IGNORECASE),
    re.compile(r"\b(proud\s+of\s+you|so\s+proud|am\s+proud)\b", re.IGNORECASE),
    re.compile(r"\b(you\s+(?:did|were)\s+(?:great|amazing|awesome|fantastic|wonderful))\b", re.IGNORECASE),
    re.compile(r"\b(you'?re\s+(?:amazing|awesome|fantastic|incredible|the\s+best))\b", re.IGNORECASE),
    re.compile(r"\b(awesome|fantastic|brilliant|superb|excellent|perfect|congrats|congratulations|bravo|kudos)\b", re.IGNORECASE),
    re.compile(r"\b(thank\s+you|thanks|love\s+you|best\s+partner)\b", re.IGNORECASE),
    re.compile(r"^(?:good|great)!\s*$", re.IGNORECASE),
]

# Encourage patterns (motivation, resilience, confidence, morale-boosting)
_ENCOURAGE_PATTERNS = [
    re.compile(r"\b(you\s+can\s+do\s+(?:this|it)|you'?ve\s+got\s+(?:this|it)|you\s+got\s+(?:this|it))\b", re.IGNORECASE),
    re.compile(r"\b(hang\s+in\s+there|don'?t\s+give\s+up|do\s+not\s+give\s+up|never\s+give\s+up)\b", re.IGNORECASE),
    re.compile(r"\b(keep\s+(?:going|it\s+up|fighting|pushing|trying)|fight\s+on|stay\s+strong)\b", re.IGNORECASE),
    re.compile(r"\b(believe\s+in\s+yourself|believe\s+in\s+us|stay\s+focused|focus\s+up|concentrate)\b", re.IGNORECASE),
    re.compile(r"\b(come\s+on|let'?s\s+go|let'?s\s+do\s+this|we\s+can\s+(?:win|do\s+this)|we'?ve\s+got\s+this|we\s+got\s+this)\b", re.IGNORECASE),
    re.compile(r"\b(give\s+it\s+your\s+all|show\s+them\s+what\s+you'?ve\s+got|show\s+them\s+what\s+you\s+got)\b", re.IGNORECASE),
    re.compile(r"\b(push\s+through|cheer\s+up|don'?t\s+lose\s+hope|you'?re\s+strong|you\s+are\s+strong)\b", re.IGNORECASE),
]


class BattleTalkParser:
    """
    Deterministic natural language intent parser for Battle Talk messages.
    """

    @classmethod
    def parse(cls, text: str) -> BattleTalkCommand:
        """
        Parses raw player text into a structured BattleTalkCommand.

        Rules and Precedence:
        1. Non-string, empty, or whitespace-only inputs are defaulted safely.
        2. Explicit physical battle requests (dodge, evade, jump, block) -> TACTICAL category.
        3. Greetings ("good morning", "hello", "hi") -> GENERAL intent (preceding "good" praise).
        4. Warning and alert phrasing ("watch out", "be careful") -> WARNING intent.
           (Takes precedence over praise in mixed sentences like "Good job, but watch out!").
        5. Praise and compliments -> PRAISE intent.
        6. Encouragement, motivation, resilience -> ENCOURAGE intent.
        7. Unmatched or general conversational phrasing -> GENERAL intent.

        Args:
            text: Raw player input string.

        Returns:
            A structured BattleTalkCommand with normalized category and parsed intent.
        """
        if not isinstance(text, str):
            return BattleTalkCommand(
                text="" if text is None else str(text),
                category=TalkCategory.CONVERSATIONAL,
                intent=BattleTalkIntent.GENERAL,
                is_tactical=False,
            )

        stripped_text = text.strip()
        if not stripped_text:
            return BattleTalkCommand(
                text=stripped_text,
                category=TalkCategory.CONVERSATIONAL,
                intent=BattleTalkIntent.GENERAL,
                is_tactical=False,
            )

        # 1. Negated tactical commands (e.g. "Don't dodge!", "Do not evade!", "Never dodge!")
        # These are treated as conversational to avoid unintended tactical dispatch.
        for pattern in _NEGATED_TACTICAL_PATTERNS:
            if pattern.search(stripped_text):
                return BattleTalkCommand(
                    text=stripped_text,
                    category=TalkCategory.CONVERSATIONAL,
                    intent=BattleTalkIntent.GENERAL,
                    is_tactical=False,
                    metadata={"negated_tactical": True},
                )

        # 2. Tactical manoeuvre commands (dodge, evade, jump, block)
        for pattern in _TACTICAL_PATTERNS:
            match = pattern.search(stripped_text)
            if match:
                action_word = match.group(1).lower()
                return BattleTalkCommand(
                    text=stripped_text,
                    category=TalkCategory.TACTICAL,
                    intent=f"tactical_{action_word}",
                    is_tactical=True,
                    metadata={"detected_tactical_action": action_word},
                )

        # 2. Greetings precedence (e.g. "Good morning!" -> GENERAL, not PRAISE)
        for pattern in _GREETING_PATTERNS:
            if pattern.search(stripped_text):
                # Only if the message is primarily a greeting without a warning or encourage
                if not any(wp.search(stripped_text) for wp in _WARNING_PATTERNS) and \
                   not any(ep.search(stripped_text) for ep in _ENCOURAGE_PATTERNS):
                    return BattleTalkCommand(
                        text=stripped_text,
                        category=TalkCategory.CONVERSATIONAL,
                        intent=BattleTalkIntent.GENERAL,
                        is_tactical=False,
                    )

        # 3. WARNING takes precedence over praise/encourage when cautionary language is present
        for pattern in _WARNING_PATTERNS:
            if pattern.search(stripped_text):
                return BattleTalkCommand(
                    text=stripped_text,
                    category=TalkCategory.CONVERSATIONAL,
                    intent=BattleTalkIntent.WARNING,
                    is_tactical=False,
                )

        # 4. PRAISE (recognition, compliments, celebration)
        for pattern in _PRAISE_PATTERNS:
            if pattern.search(stripped_text):
                return BattleTalkCommand(
                    text=stripped_text,
                    category=TalkCategory.CONVERSATIONAL,
                    intent=BattleTalkIntent.PRAISE,
                    is_tactical=False,
                )

        # 5. ENCOURAGE (morale, reassurance, urging to fight on)
        for pattern in _ENCOURAGE_PATTERNS:
            if pattern.search(stripped_text):
                return BattleTalkCommand(
                    text=stripped_text,
                    category=TalkCategory.CONVERSATIONAL,
                    intent=BattleTalkIntent.ENCOURAGE,
                    is_tactical=False,
                )

        # 6. Fallback: GENERAL conversation
        return BattleTalkCommand(
            text=stripped_text,
            category=TalkCategory.CONVERSATIONAL,
            intent=BattleTalkIntent.GENERAL,
            is_tactical=False,
        )


def parse(text: str) -> BattleTalkCommand:
    """Convenience public interface to parse raw text into BattleTalkCommand."""
    return BattleTalkParser.parse(text)


parse_battle_talk = parse
