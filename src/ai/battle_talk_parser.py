"""
Battle Talk intent interpretation, tactical matchup advisor, prompt building,
and multi-archetype response parsing for Syntax Error 26.
Supports both LLM instruction prompting (fine-tuned models) and high-fidelity deterministic fallback.

Key capabilities:
- Natural Language Intent Parsing (Praise, Encourage, Warning, Tactical, Advice, Taunt, General)
- Type-Chart Aware Tactical Move Recommender (using authoritative type chart & species data)
- Temperament Matrix (Adamant, Brave, Timid, Jolly, Calm, Sassy, Modest, Gentle)
- Opponent Archetypes Banter (Wild, Rival, Gym Leader, Rocket Grunt)
- Combat Momentum & Morale Tracking (-20 to +20 momentum scoring)
- Status Effect & Critical Health Expressions
- ChatML/Instruction Prompt Builder for off-system LLM training
- LLM JSON Output Extraction and Strict Schema Validation
"""
import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

from src.data.species import SAMPLE_SPECIES
from src.data.attacks import SAMPLE_ATTACKS
from src.data.type_chart import get_effectiveness_against_types
from src.models.pokemon_type import PokemonType


class BattleTalkIntent(str, Enum):
    """Supported non-combat and conversational intents for Battle Talk."""
    PRAISE = "PRAISE"
    ENCOURAGE = "ENCOURAGE"
    WARNING = "WARNING"
    TACTICAL = "TACTICAL"
    ADVICE = "ADVICE"
    TAUNT = "TAUNT"
    GENERAL = "GENERAL"


class TalkCategory(str, Enum):
    """Broad category of the battle communication."""
    CONVERSATIONAL = "CONVERSATIONAL"
    TACTICAL = "TACTICAL"


@dataclass(frozen=True)
class BattleTalkCommand:
    """Structured data model for a Battle Talk action."""
    text: str
    category: TalkCategory = TalkCategory.CONVERSATIONAL
    intent: Union[BattleTalkIntent, str] = BattleTalkIntent.GENERAL
    is_tactical: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


# Regex patterns for deterministic classification
_TACTICAL_PATTERNS = [
    re.compile(r"\b(dodge|dodging|evade|evading|sidestep|sidestepping|duck|ducking)\b", re.IGNORECASE),
    re.compile(r"\b(jump\s+(?:over|away|aside|up|back)|leap\s+(?:away|aside|back))\b", re.IGNORECASE),
    re.compile(r"\b(block\s+it|block\s+the\s+attack|parry|parry\s+it|take\s+cover|brace|shield)\b", re.IGNORECASE),
]

_NEGATED_TACTICAL_PATTERNS = [
    re.compile(
        r"\b(don'?t|do\s+not|never|no|stop|cannot|can'?t|refrain\s+from)\s+(?:try\s+to\s+|attempt\s+to\s+)?(dodge|dodging|evade|evading|sidestep|sidestepping|duck|ducking|jump|block|parry|brace)\b",
        re.IGNORECASE,
    ),
]

_ADVICE_PATTERNS = [
    re.compile(r"\b(?:what|which|how|best|recommend|suggest|any)\b.*?\b(?:move|attack|do|use|play|beat|counter|strike)\b", re.IGNORECASE),
    re.compile(r"\b(what\s+(?:should|can)\s+(?:we|i)\s+do|what'?s\s+the\s+(?:play|plan|move)|give\s+me\s+advice|your\s+call|help\s+me\s+out)\b", re.IGNORECASE),
    re.compile(r"\b(weakness|type\s+advantage|super\s+effective|effective\s+against)\b", re.IGNORECASE),
]

_WARNING_PATTERNS = [
    re.compile(r"\b(watch\s+out|look\s+out|heads\s+up|be\s+careful|stay\s+alert|stay\s+sharp)\b", re.IGNORECASE),
    re.compile(r"\b(incoming|danger|behind\s+you|on\s+guard|look\s+alive|watch\s+your\s+back|guard\s+up)\b", re.IGNORECASE),
    re.compile(r"\b(keep\s+your\s+guard\s+up|eyes\s+open|caution|stay\s+on\s+guard|defend)\b", re.IGNORECASE),
    re.compile(r"\b(?:^|[,\.!?\s]+)careful\b", re.IGNORECASE),
]

_PRAISE_PATTERNS = [
    re.compile(r"\b((?:good|great|nice|awesome|fantastic|wonderful|superb|brilliant|clean|solid)\s+(?:job|work|hit|move|strike|attack|one|shot|boy|girl))\b", re.IGNORECASE),
    re.compile(r"\b(proud\s+of\s+you|so\s+proud|am\s+proud|love\s+you|best\s+partner|well\s+done)\b", re.IGNORECASE),
    re.compile(r"\byou\s+(?:did|were)\s+(?:so\s+)?(?:great|amazing|awesome|fantastic|wonderful|good)\b", re.IGNORECASE),
    re.compile(r"\byou\s*(?:'re|\s+are)\s+(?:so\s+)?(?:amazing|awesome|fantastic|incredible|the\s+best|good|great)\b", re.IGNORECASE),
    re.compile(r"\b(awesome|fantastic|brilliant|superb|excellent|perfect|congrats|congratulations|bravo|kudos)\b", re.IGNORECASE),
    re.compile(r"\b(thank\s+you|thanks|good\s+one|great\s+one|nice\s+one)\b", re.IGNORECASE),
    re.compile(r"^(?:good|great|nice)!\s*$", re.IGNORECASE),
]

_ENCOURAGE_PATTERNS = [
    re.compile(r"\b(you\s+can\s+do\s+(?:this|it)|you'?ve\s+got\s+(?:this|it)|you\s+got\s+(?:this|it))\b", re.IGNORECASE),
    re.compile(r"\b(hang\s+in\s+there|don'?t\s+give\s+up|do\s+not\s+give\s+up|never\s+give\s+up)\b", re.IGNORECASE),
    re.compile(r"\b(keep\s+(?:going|it\s+up|fighting|pushing|trying)|fight\s+on|stay\s+strong)\b", re.IGNORECASE),
    re.compile(r"\b(believe\s+in\s+yourself|believe\s+in\s+us|stay\s+focused|focus\s+up|concentrate)\b", re.IGNORECASE),
    re.compile(r"\b(come\s+on|let'?s\s+go|let'?s\s+do\s+this|we\s+can\s+(?:win|do\s+this)|we'?ve\s+got\s+this|we\s+got\s+this)\b", re.IGNORECASE),
    re.compile(r"\b(give\s+it\s+your\s+all|show\s+them\s+what\s+you'?ve\s+got|show\s+them\s+what\s+you\s+got)\b", re.IGNORECASE),
    re.compile(r"\b(push\s+through|cheer\s+up|don'?t\s+lose\s+hope|you'?re\s+strong|you\s+are\s+strong|we\s+fight)\b", re.IGNORECASE),
]

_TAUNT_PATTERNS = [
    re.compile(r"\b(is\s+that\s+all|too\s+slow|weak|pathetic|can'?t\s+touch\s+(?:this|me)|loser|give\s+up\s+now)\b", re.IGNORECASE),
    re.compile(r"\b(you\s+call\s+that\s+an\s+attack|easy\s+win|no\s+match)\b", re.IGNORECASE),
]

_GREETING_PATTERNS = [
    re.compile(r"\b(good\s+(?:morning|afternoon|evening|day|night))\b", re.IGNORECASE),
    re.compile(r"\b(hello|hi|hey|greetings|howdy|sup|what'?s\s+up|how\s+are\s+you)\b", re.IGNORECASE),
]


class BattleTalkAdvisor:
    """
    Evaluates type matchups and move pools to generate smart tactical combat advice.
    """

    @classmethod
    def evaluate_tactical_advice(
        cls,
        known_moves: List[str],
        opponent_species_name: str,
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Determines the most advantageous move against the opponent species using type effectiveness.
        Returns (best_move_name, rationale_string).
        """
        opp_spec = SAMPLE_SPECIES.get(opponent_species_name)
        if not opp_spec or not known_moves:
            return None, None

        opp_types = [opp_spec.primary_type]
        if opp_spec.secondary_type:
            opp_types.append(opp_spec.secondary_type)

        scored_moves: List[Tuple[float, str, str]] = []

        for move_name in known_moves:
            atk = SAMPLE_ATTACKS.get(move_name)
            if not atk:
                continue

            multiplier = get_effectiveness_against_types(atk.type, opp_types)
            score = multiplier * (atk.power or 40)

            if multiplier >= 2.0:
                note = f"{move_name} is super-effective ({multiplier}x) against {opp_spec.name}'s typing!"
            elif multiplier == 0.0:
                note = f"{move_name} has no effect (0x) against {opp_spec.name}!"
            elif multiplier < 1.0:
                note = f"{move_name} is resisted ({multiplier}x) by {opp_spec.name}."
            else:
                note = f"{move_name} provides steady neutral damage against {opp_spec.name}."

            scored_moves.append((score, move_name, note))

        if not scored_moves:
            return None, None

        scored_moves.sort(key=lambda x: x[0], reverse=True)
        best_score, best_move, best_rationale = scored_moves[0]
        return best_move, best_rationale


class BattleTalkParser:
    """
    Parser, prompt generator, tactical advisor, and deterministic response engine for Battle Talk.
    """

    @classmethod
    def parse(cls, text: str) -> BattleTalkCommand:
        """Parses player combat message into a structured BattleTalkCommand."""
        if not isinstance(text, str) or not text.strip():
            return BattleTalkCommand(
                text="" if text is None else str(text),
                category=TalkCategory.CONVERSATIONAL,
                intent=BattleTalkIntent.GENERAL,
                is_tactical=False,
            )

        stripped = text.strip()

        # 1. Negated tactical commands
        for pattern in _NEGATED_TACTICAL_PATTERNS:
            if pattern.search(stripped):
                return BattleTalkCommand(
                    text=stripped,
                    category=TalkCategory.CONVERSATIONAL,
                    intent=BattleTalkIntent.GENERAL,
                    is_tactical=False,
                    metadata={"negated_tactical": True},
                )

        # 2. Advice requests
        for pattern in _ADVICE_PATTERNS:
            if pattern.search(stripped):
                return BattleTalkCommand(
                    text=stripped,
                    category=TalkCategory.TACTICAL,
                    intent=BattleTalkIntent.ADVICE,
                    is_tactical=True,
                    metadata={"requested_advice": True},
                )

        # 3. Tactical maneuver commands (dodge, block, jump, brace)
        for pattern in _TACTICAL_PATTERNS:
            match = pattern.search(stripped)
            if match:
                action_word = match.group(1).lower()
                return BattleTalkCommand(
                    text=stripped,
                    category=TalkCategory.TACTICAL,
                    intent=BattleTalkIntent.TACTICAL,
                    is_tactical=True,
                    metadata={"detected_tactical_action": action_word},
                )

        # 4. Taunts
        for pattern in _TAUNT_PATTERNS:
            if pattern.search(stripped):
                return BattleTalkCommand(
                    text=stripped,
                    category=TalkCategory.CONVERSATIONAL,
                    intent=BattleTalkIntent.TAUNT,
                    is_tactical=False,
                )

        # 5. Warnings (high precedence over praise)
        for pattern in _WARNING_PATTERNS:
            if pattern.search(stripped):
                return BattleTalkCommand(
                    text=stripped,
                    category=TalkCategory.CONVERSATIONAL,
                    intent=BattleTalkIntent.WARNING,
                    is_tactical=False,
                )

        # 6. Greetings precedence
        for pattern in _GREETING_PATTERNS:
            if pattern.search(stripped):
                if not any(ep.search(stripped) for ep in _ENCOURAGE_PATTERNS):
                    return BattleTalkCommand(
                        text=stripped,
                        category=TalkCategory.CONVERSATIONAL,
                        intent=BattleTalkIntent.GENERAL,
                        is_tactical=False,
                    )

        # 7. Praise
        for pattern in _PRAISE_PATTERNS:
            if pattern.search(stripped):
                return BattleTalkCommand(
                    text=stripped,
                    category=TalkCategory.CONVERSATIONAL,
                    intent=BattleTalkIntent.PRAISE,
                    is_tactical=False,
                )

        # 8. Encourage
        for pattern in _ENCOURAGE_PATTERNS:
            if pattern.search(stripped):
                return BattleTalkCommand(
                    text=stripped,
                    category=TalkCategory.CONVERSATIONAL,
                    intent=BattleTalkIntent.ENCOURAGE,
                    is_tactical=False,
                )

        return BattleTalkCommand(
            text=stripped,
            category=TalkCategory.CONVERSATIONAL,
            intent=BattleTalkIntent.GENERAL,
            is_tactical=False,
        )

    @classmethod
    def calculate_combat_momentum(
        cls,
        hp_ratio: float,
        opp_hp_ratio: float,
        bond: float,
        morale_delta: int,
    ) -> Tuple[str, str]:
        """
        Calculates momentum tier (SURGING, STEADY, PRESSURED, CRITICAL) and active morale effect.
        """
        hp_diff = (hp_ratio - opp_hp_ratio) * 10
        momentum_score = int(round(hp_diff + (morale_delta * 1.5) + (bond / 20.0 - 2.5)))

        if momentum_score >= 8:
            return "SURGING", "buff_critical_focus"
        elif momentum_score >= 0:
            return "STEADY", "buff_morale_stable"
        elif momentum_score >= -7:
            return "PRESSURED", "debuff_tension"
        else:
            return "CRITICAL", "rallying_desperation"

    @classmethod
    def generate_opponent_banter(
        cls,
        species: str,
        opp_species: str,
        intent: str,
        archetype: str,
        hp_ratio: float,
    ) -> Dict[str, Any]:
        """
        Generates contextual trash talk or combat cries for opposing archetypes.
        """
        archetype = (archetype or "wild").lower()

        if archetype == "rival":
            if hp_ratio > 0.6:
                dialogue = f"{species}'s trainer smirks: 'Is that all you've got? {species}, show them real power!'"
                emotion = "cocky"
            elif hp_ratio > 0.25:
                dialogue = f"{species} grits its teeth as its trainer snaps: 'Stop messing around, take {opp_species} down!'"
                emotion = "combative"
            else:
                dialogue = f"{species}'s trainer shouts angrily: 'No way! Hang on, {species}, don't let them win!'"
                emotion = "frustrated"
            reaction = "strike"

        elif archetype == "gym_leader":
            if hp_ratio > 0.5:
                dialogue = f"{species}'s Gym Leader observes calmly: 'A spirited effort, but our defense is impenetrable.'"
                emotion = "composed"
            else:
                dialogue = f"{species}'s Gym Leader smiles with admiration: 'Impressive tactical synergy! Now let us see your finish!'"
                emotion = "focused"
            reaction = "nod"

        elif archetype == "rocket_grunt":
            dialogue = f"{species} snarls viciously while the Grunt snickers: 'Give it up, kid! Hand over your Pokémon!'"
            emotion = "malicious"
            reaction = "strike"

        else:  # Wild Pokémon
            if hp_ratio <= 0.25:
                dialogue = f"The wild {species} screeches frantically, cornered and fighting with raw primal fury!"
                emotion = "desperate"
                reaction = "brace"
            elif intent == "TAUNT":
                dialogue = f"The wild {species} flares its stance and roars aggressively, rejecting any intimidation!"
                emotion = "combative"
                reaction = "strike"
            else:
                dialogue = f"The wild {species} circles warily, teeth bared and eyes fixated on {opp_species}."
                emotion = "combative"
                reaction = "reposition"

        return {
            "species": species,
            "dialogue": dialogue,
            "intent": intent,
            "emotional_state": emotion,
            "morale_delta": 0,
            "tactical_reaction": reaction,
            "tactical_suggestion": None,
            "momentum_tier": "STEADY",
            "morale_effect": "opponent_active",
            "confidence": 0.9,
            "source": "rule_fallback",
        }

    @classmethod
    def generate_fallback_response(
        cls,
        species: str,
        nickname: str,
        message: str,
        personality: Dict[str, Any],
        temperament: str,
        bond: float,
        obedience: float,
        battle_context: Dict[str, Any],
        is_opponent: bool = False,
        opponent_archetype: str = "wild",
    ) -> Dict[str, Any]:
        """
        Deterministic, personality-aware, context-sensitive fallback engine.
        Produces vibrant responses reflecting health, bond, temperament, and battle conditions.
        """
        display_name = nickname or species
        cmd = cls.parse(message)
        intent = cmd.intent.value if isinstance(cmd.intent, BattleTalkIntent) else str(cmd.intent)

        hp_ratio = float(battle_context.get("hp_ratio", 1.0))
        opp_hp_ratio = float(battle_context.get("opponent_hp_ratio", 1.0))
        is_low_hp = hp_ratio <= 0.25
        status_effects = battle_context.get("status_effects", [])
        opp_species = battle_context.get("opponent_species", "the opponent")
        tactical_action = cmd.metadata.get("detected_tactical_action", "")
        known_moves = battle_context.get("known_moves", [])

        # Route opponent banter
        if is_opponent:
            return cls.generate_opponent_banter(
                species=species,
                opp_species=opp_species,
                intent=intent,
                archetype=opponent_archetype,
                hp_ratio=hp_ratio,
            )

        # Status condition overrides
        if "asleep" in status_effects or "sleep" in status_effects:
            return {
                "species": species,
                "dialogue": f"{display_name} is fast asleep and only lets out a soft, unconscious snore...",
                "intent": intent,
                "emotional_state": "exhausted",
                "morale_delta": 0,
                "tactical_reaction": "hesitate",
                "tactical_suggestion": None,
                "momentum_tier": "CRITICAL",
                "morale_effect": "status_sleep_immobilized",
                "confidence": 0.95,
                "source": "rule_fallback",
            }
        elif "paralysis" in status_effects or "paralyzed" in status_effects:
            return {
                "species": species,
                "dialogue": f"{display_name} tries to respond, but yellow sparks lock its muscles with a painful wince!",
                "intent": intent,
                "emotional_state": "struggling",
                "morale_delta": -2,
                "tactical_reaction": "hesitate",
                "tactical_suggestion": None,
                "momentum_tier": "PRESSURED",
                "morale_effect": "status_paralysis_slow",
                "confidence": 0.9,
                "source": "rule_fallback",
            }
        elif "burn" in status_effects or "burned" in status_effects:
            status_dialogue_suffix = f" {display_name} flinches from the burning sting on its shoulder."
        else:
            status_dialogue_suffix = ""

        # Tactical Advice Evaluation
        best_move, move_rationale = BattleTalkAdvisor.evaluate_tactical_advice(known_moves, opp_species)

        # Temperament and obedience influences
        temp = (temperament or "bold").lower()
        is_rebellious = obedience < 35 or bond < 20
        morale_delta = 0
        tactical_suggestion = None
        tactical_reaction = "nod"

        # 1. ADVICE INTENT
        if intent == BattleTalkIntent.ADVICE.value:
            tactical_suggestion = best_move
            tactical_reaction = "reposition"
            morale_delta = 3
            if best_move:
                dialogue = f"{display_name} signals eagerness towards using {best_move}! ({move_rationale})"
                emotion = "focused"
            else:
                dialogue = f"{display_name} glances back with keen eyes, sizing up {opp_species}'s defensive stance."
                emotion = "thoughtful"

        # 2. PRAISE INTENT
        elif intent == BattleTalkIntent.PRAISE.value:
            if is_rebellious:
                dialogue = f"{display_name} turns away with a dismissive scoff, pretending the praise means nothing."
                emotion = "indifferent"
                morale_delta = 1
                tactical_reaction = "reposition"
            elif is_low_hp:
                if temp in ["brave", "adamant"]:
                    dialogue = f"{display_name} wipes bruised brow and lets out a battle-hardened grin!"
                    emotion = "defiant"
                else:
                    dialogue = f"{display_name} breathes heavily, panting, but flashes a grateful, tired smile!"
                    emotion = "exhausted"
                morale_delta = 7
                tactical_reaction = "nod"
            else:
                if temp in ["jolly", "cheerful"]:
                    dialogue = f"{display_name} hops excitedly with a bright, energetic cry!"
                    emotion = "gleeful"
                elif temp in ["brave", "adamant"]:
                    dialogue = f"{display_name} flexes with unbridled confidence, roaring for the next challenge!"
                    emotion = "fired_up"
                else:
                    dialogue = f"{display_name} beams with pride and sparks with combat energy!"
                    emotion = "pleased"
                morale_delta = 8
                tactical_reaction = "strike"

        # 3. ENCOURAGE INTENT
        elif intent == BattleTalkIntent.ENCOURAGE.value:
            if is_low_hp:
                if temp in ["brave", "adamant"]:
                    dialogue = f"{display_name} plants its heels into the dirt, eyes blazing with an unbreakable resolve!"
                    emotion = "defiant"
                elif temp in ["timid", "gentle"]:
                    dialogue = f"{display_name} trembles slightly, but hearing your voice steadies its trembling paws."
                    emotion = "recovering"
                else:
                    dialogue = f"{display_name} digs deep, refusing to collapse while you stand beside it!"
                    emotion = "defiant"
                morale_delta = 10
                tactical_reaction = "brace"
            elif is_rebellious:
                dialogue = f"{display_name} grunts stubbornly, fighting fiercely on its own stubborn terms."
                emotion = "stubborn"
                morale_delta = 2
                tactical_reaction = "strike"
            else:
                dialogue = f"{display_name} nods vigorously, focus sharpening like a razor blade!"
                emotion = "focused"
                morale_delta = 7
                tactical_reaction = "nod"

        # 4. WARNING INTENT
        elif intent == BattleTalkIntent.WARNING.value:
            tactical_reaction = "brace"
            morale_delta = 4
            tactical_suggestion = best_move or ("Protect" if "Protect" in known_moves else None)
            if temp in ["timid", "gentle"] or is_low_hp:
                dialogue = f"{display_name} recoils defensively, tracking {opp_species}'s every subtle twitch with wide eyes!"
                emotion = "nervous"
            else:
                dialogue = f"{display_name} immediately snaps into a defensive guard, bracing for {opp_species}'s strike!"
                emotion = "focused"

        # 5. TACTICAL INTENT
        elif intent == BattleTalkIntent.TACTICAL.value:
            tactical_reaction = tactical_action if tactical_action else "reposition"
            if is_rebellious:
                dialogue = f"{display_name} hesitates on your command, choosing its own angle instead."
                emotion = "hesitant"
                morale_delta = -1
            else:
                dialogue = f"{display_name} cleanly shifts its footing to {tactical_reaction} the incoming assault!"
                emotion = "focused"
                morale_delta = 5

        # 6. TAUNT INTENT
        elif intent == BattleTalkIntent.TAUNT.value:
            if temp in ["sassy", "adamant", "brave"]:
                dialogue = f"{display_name} lets loose a daring, defiant roar across the arena, completely unfazed by {opp_species}!"
                emotion = "defiant"
                morale_delta = 5
            else:
                dialogue = f"{display_name} calls out a firm combat challenge, daring {opp_species} to step closer!"
                emotion = "focused"
                morale_delta = 3
            tactical_reaction = "strike"

        # 7. GENERAL INTENT
        else:
            if is_low_hp:
                dialogue = f"{display_name} lets out a strained cry, fighting through exhaustion for your next command."
                emotion = "exhausted"
                morale_delta = 1
            else:
                if temp in ["calm", "modest"]:
                    dialogue = f"{display_name} breathes in rhythm, centered and waiting for your tactical direction."
                    emotion = "composed"
                else:
                    dialogue = f"{display_name} chirps attentively, locking eyes with you for the next move."
                    emotion = "focused"
                morale_delta = 2

        dialogue += status_dialogue_suffix
        momentum_tier, morale_effect = cls.calculate_combat_momentum(hp_ratio, opp_hp_ratio, bond, morale_delta)

        return {
            "species": species,
            "dialogue": dialogue,
            "intent": intent,
            "emotional_state": emotion,
            "morale_delta": morale_delta,
            "tactical_reaction": tactical_reaction,
            "tactical_suggestion": tactical_suggestion,
            "momentum_tier": momentum_tier,
            "morale_effect": morale_effect,
            "confidence": 0.9,
            "source": "rule_fallback",
        }

    @classmethod
    def build_prompt(
        cls,
        species: str,
        nickname: str,
        message: str,
        personality: Dict[str, Any],
        temperament: str,
        bond: float,
        obedience: float,
        battle_context: Dict[str, Any],
        is_opponent: bool = False,
        opponent_archetype: str = "wild",
    ) -> str:
        """
        Builds a structured prompt formatted for ChatML or standard instruction LLMs.
        """
        display_name = nickname or species
        hp_ratio = float(battle_context.get("hp_ratio", 1.0))
        status_effects = battle_context.get("status_effects", [])
        status_str = ", ".join(status_effects) if status_effects else "healthy"
        opp_species = battle_context.get("opponent_species", "Opponent")
        turn = battle_context.get("turn", 1)
        weather = battle_context.get("weather", "clear")
        known_moves = battle_context.get("known_moves", [])

        system_msg = (
            "You are an AI roleplaying as a Pokemon in a tactical turn-based battle.\n"
            f"You are {display_name} ({species}).\n"
            f"Temperament: {temperament}. Bond Level: {bond}/100. Obedience: {obedience}/100.\n"
            f"Known Moves: {', '.join(known_moves) if known_moves else 'Standard attacks'}.\n"
            f"Personality: Aggression={personality.get('aggression', 50)}, Loyalty={personality.get('loyalty', 50)}, "
            f"Confidence={personality.get('confidence', 50)}, Fear={personality.get('fear', 20)}.\n"
            f"Battle State: Turn {turn}, Weather {weather}, Your HP {int(hp_ratio * 100)}%, Status: {status_str}, Opponent: {opp_species}.\n\n"
            "Given the trainer's or opponent's words, respond with JSON matching this exact schema:\n"
            "{\n"
            '  "dialogue": "<vocal cry and physical in-battle reaction>",\n'
            '  "intent": "<PRAISE|ENCOURAGE|WARNING|TACTICAL|ADVICE|TAUNT|GENERAL>",\n'
            '  "emotional_state": "<focused|defiant|pleased|nervous|exhausted|fired_up|combative|composed|gleeful>",\n'
            '  "morale_delta": <integer between -10 and +10>,\n'
            '  "tactical_reaction": "<brace|strike|reposition|nod|hesitate>",\n'
            '  "tactical_suggestion": "<optional attack move name or null>",\n'
            '  "momentum_tier": "<SURGING|STEADY|PRESSURED|CRITICAL>",\n'
            '  "morale_effect": "<morale buff/debuff descriptor>",\n'
            '  "confidence": <float 0.0 to 1.0>\n'
            "}"
        )

        user_msg = (
            f"Role: {'Opponent ' + opponent_archetype.capitalize() + ' Pokemon' if is_opponent else 'Partner Pokemon'}\n"
            f"Trainer Message: \"{message}\"\n"
            "Generate your immediate combat reaction and JSON output."
        )

        return f"<|im_start|>system\n{system_msg}<|im_end|>\n<|im_start|>user\n{user_msg}<|im_end|>\n<|im_start|>assistant\n"

    @classmethod
    def parse_llm_response(cls, raw_output: str, fallback_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extracts JSON from LLM generation with validation and clean fallback.
        """
        if not raw_output or not isinstance(raw_output, str):
            return fallback_data

        try:
            match = re.search(r"\{.*\}", raw_output, re.DOTALL)
            if not match:
                return fallback_data
            parsed = json.loads(match.group(0))

            return {
                "species": fallback_data.get("species", "Pokemon"),
                "dialogue": str(parsed.get("dialogue") or fallback_data["dialogue"]),
                "intent": str(parsed.get("intent") or fallback_data["intent"]).upper(),
                "emotional_state": str(parsed.get("emotional_state") or fallback_data["emotional_state"]),
                "morale_delta": int(parsed.get("morale_delta", fallback_data.get("morale_delta", 0))),
                "tactical_reaction": str(parsed.get("tactical_reaction", fallback_data.get("tactical_reaction", "nod"))),
                "tactical_suggestion": parsed.get("tactical_suggestion") or fallback_data.get("tactical_suggestion"),
                "momentum_tier": str(parsed.get("momentum_tier", fallback_data.get("momentum_tier", "STEADY"))),
                "morale_effect": str(parsed.get("morale_effect", fallback_data.get("morale_effect", "buff_morale_stable"))),
                "confidence": float(parsed.get("confidence", 0.9)),
                "source": "llm_adapter",
            }
        except Exception:
            return fallback_data


def parse_battle_talk(text: str) -> BattleTalkCommand:
    """Public helper to parse battle talk input."""
    return BattleTalkParser.parse(text)
