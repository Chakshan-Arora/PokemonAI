"""
Live AI model decision providers and prompt integration for autonomous Pokemon agents.
Supports Google Gemini, OpenAI, and compatible LLM endpoints via structured JSON protocols.
Handles prompt assembly, response parsing, credential management with placeholders,
timeout/retry resilience, and seamless fallback routing.
"""
from abc import abstractmethod
import json
import os
import re
import urllib.error
import urllib.request
from typing import Any, Callable, Optional, Union
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from src.ai.agent import PokemonAgent
from src.ai.decision import AgentActionType, AgentDecision
from src.ai.decision_provider import DecisionProvider, FallbackDecisionHandler
from src.ai.perception import AgentPerception


# Default configuration constants and placeholders
GEMINI_API_KEY_DEFAULT = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
GEMINI_API_KEY_PLACEHOLDER = "YOUR_GEMINI_API_KEY_HERE"
OPENAI_API_KEY_PLACEHOLDER = "YOUR_OPENAI_API_KEY_HERE"

DEFAULT_GEMINI_MODEL = os.getenv("GEMINI_MODEL") or "gemini-2.5-flash"
DEFAULT_GEMINI_FALLBACK_MODELS = (
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-2.5-pro",
    "gemini-flash-latest",
    "gemini-3.5-flash-lite",
)
DEFAULT_OPENAI_MODEL = os.getenv("OPENAI_MODEL") or "gpt-4o-mini"

DEFAULT_REQUEST_TIMEOUT = 10.0
DEFAULT_MAX_RETRIES = 2


class AiConfigurationError(Exception):
    """Raised when an AI provider is missing required credentials or configuration."""
    pass


class AiModelServiceError(Exception):
    """Raised when an external AI service fails, times out, or returns an error."""
    pass


class PromptBuilder:
    """
    Constructs rich, structured prompts for autonomous Pokemon agent decision-making.
    Reflects the agent's identity, personality, memories, and perceived world context.
    """

    @staticmethod
    def build_system_instruction(agent: PokemonAgent) -> str:
        """
        Builds the overarching persona and behavioral instructions for the agent.
        """
        ident = agent.identity
        traits = ident.personality_traits
        agg = traits.get("aggression", 50)
        fear = traits.get("fear", 50)
        cur = traits.get("curiosity", 50)
        conf = traits.get("confidence", 50)
        loyalty = traits.get("loyalty", 50)
        soc = traits.get("sociability", 50)

        immediate_goals_text = "\n".join(
            [f"- {g.get('description', '')}" for g in agent.goals.immediate_goals if g.get("status") == "active"]
        ) or "- None currently active"

        long_term_goals_text = "\n".join(
            [f"- {g.get('description', '')}" for g in agent.goals.long_term_goals if g.get("status") == "active"]
        ) or "- None currently active"

        beliefs_text = "\n".join(
            [f"- {b}" for b in agent.beliefs.world_beliefs]
        ) or "- Sees the world through its natural instincts"

        return f"""You are {agent.display_name}, an autonomous {agent.species} in a living Pokemon world.
You are an independent character with your own thoughts, emotions, instincts, and desires.
You are not a simple programmed automaton. You interpret situations from your own point of view.

=== CORE IDENTITY & PERSONALITY ===
Species: {agent.species}
Nickname: {ident.nickname or "None"}
Temperament: {ident.temperament}
Communication Style: {ident.communication_style}
Status: {"Captured (Owned by Trainer)" if agent.is_captured else "Wild (Free Pokémon)"}

Personality Traits (0 - 100):
- Aggression: {agg}/100
- Fear: {fear}/100
- Curiosity: {cur}/100
- Confidence: {conf}/100
- Loyalty: {loyalty}/100
- Sociability: {soc}/100

=== GOALS & MOTIVATIONS ===
Immediate Goals:
{immediate_goals_text}

Long-term Goals:
{long_term_goals_text}

=== BELIEFS & PERCEPTIONS ===
Perceived Player Intent: {agent.beliefs.perceived_player_intent}
World Beliefs:
{beliefs_text}

=== BEHAVIOR GUIDELINES ===
1. Make decisions that reflect your personality, current health, relationships, and goals.
2. If you trust and like your trainer, you will generally follow instructions willingly.
3. If a command seems tactically flawed and you are confident, you may suggest a better attack (suggest).
4. If you are terrified or severely wounded, you may hesitate, retreat, or protest.
5. If you are deeply resentful or mistreated, you may disobey or even plead to be released (request_release).
6. If you are a wild Pokemon, act on survival, territory defense, or curiosity.
7. Always communicate your intent through authentic Pokemon dialogue, cries, or physical gestures.
8. Your output must strictly be a single valid JSON object matching the requested schema.
"""

    @staticmethod
    def build_user_prompt(perception: AgentPerception) -> str:
        """
        Builds the situational context payload perceived by the agent for the decision turn.
        """
        phys = perception.physical_state
        hp = phys.get("current_hp", 0)
        max_hp = phys.get("max_hp", 1)
        hp_ratio = phys.get("hp_ratio", 1.0)
        is_fainted = phys.get("is_fainted", False)
        known_moves = phys.get("known_moves", [])
        status_effects = phys.get("status_effects", [])

        # Trainer context
        tc = perception.trainer_context
        if tc:
            trainer_info = (
                f"Trainer: {tc.get('trainer_name')} (ID: {tc.get('trainer_id')})\n"
                f"Trainer Command: \"{tc.get('command') or 'None'}\"\n"
                f"Command Intent: {tc.get('command_intent') or 'neutral'}\n"
                f"Trainer Tone: {tc.get('tone') or 'neutral'}\n"
                f"Relationship Stage: {tc.get('relationship_stage')}\n"
                f"Trust Level: {tc.get('trust', 0.0):.1f} / 100.0\n"
                f"Affection Level: {tc.get('affection', 0.0):.1f} / 100.0"
            )
        else:
            trainer_info = "No trainer present (wild encounter or solo exploration)."

        # Opponent context
        opp = perception.opponent_context
        if opp:
            opp_info = (
                f"Opponent Species: {opp.get('species')}\n"
                f"Opponent Level: {opp.get('level')}\n"
                f"Opponent Apparent Condition: {opp.get('apparent_health')}\n"
                f"Opponent Fainted: {opp.get('is_fainted')}"
            )
        else:
            opp_info = "No direct opponent currently engaged."

        # Memories
        memories_text = "\n".join([f"- {m}" for m in perception.relevant_memories]) or "- No specific recent memories."

        # Available actions
        actions_text = ", ".join(perception.available_actions)

        return f"""=== CURRENT SITUATION ===
Location: {perception.environment_context.get('region_id', 'unknown')} | Time: {perception.environment_context.get('time_of_day', 'day')}
In Battle: {perception.environment_context.get('in_battle', False)}

--- YOUR PHYSICAL STATE ---
HP: {hp}/{max_hp} ({hp_ratio:.0%})
Conscious: {not is_fainted}
Known Moves: {known_moves}
Status Effects: {status_effects or 'None'}

--- TRAINER CONTEXT ---
{trainer_info}

--- OPPONENT CONTEXT ---
{opp_info}

--- RECENT MEMORIES ---
{memories_text}

--- PERMITTED ACTION TYPES ---
{actions_text}

=== REQUIRED JSON RESPONSE ===
Respond ONLY with a single JSON object conforming to this exact structure:
{{
  "action_type": "<one of the permitted action types, e.g. obey, attack, defend, hesitate, disobey, flee, inspect, interact, suggest, protest, request_release, rest>",
  "intent": "<short summary of your immediate goal or action>",
  "target": "<target entity name or null>",
  "chosen_move": "<move name from Known Moves if attacking or suggesting, or null>",
  "dialogue": "<your authentic cry and dialogue, e.g. 'Bulba! *perks up alertly* (Hello Trainer! Ready to explore!)'>",
  "emotional_state": "<current feeling, e.g. confident, cautious, anxious, defiant, curious, affectionate, happy, hurt, discouraged, exhausted>",
  "rationale": "<internal reasoning explaining why you chose this based on your traits and context>",
  "confidence": <float from 0.0 to 1.0>,
  "suggested_alternative": "<move name from Known Moves if action_type is suggest, else null>",
  "trust_delta": <float delta from -5.0 to +5.0 reflecting relationship impact, or 0.0>,
  "affection_delta": <float delta from -5.0 to +5.0 reflecting relationship impact, or 0.0>
}}
"""


class DecisionResponseParser:
    """
    Parses and sanitizes raw JSON text output from LLMs into structured AgentDecision instances.
    Handles markdown code blocks, partial text wrappers, and out-of-range values.
    """

    @staticmethod
    def parse(raw_text: str) -> AgentDecision:
        """
        Parses model text into an AgentDecision payload.
        """
        if not raw_text or not raw_text.strip():
            return AgentDecision(
                action_type=AgentActionType.HESITATE,
                intent="Hesitate due to empty response",
                emotional_state="confused",
                rationale="Model returned empty text.",
                confidence=0.5,
            )

        cleaned = raw_text.strip()

        # Extract JSON from markdown fences if present
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
        if fence_match:
            cleaned = fence_match.group(1).strip()
        else:
            # Locate outer JSON braces
            first_brace = cleaned.find("{")
            last_brace = cleaned.rfind("}")
            if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                cleaned = cleaned[first_brace : last_brace + 1].strip()

        data = None
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            # Attempt streaming raw decode from first brace in case of trailing repetitions
            if first_brace != -1:
                try:
                    data, _ = json.JSONDecoder().raw_decode(raw_text[raw_text.find("{"):])
                except json.JSONDecodeError:
                    pass

        if not isinstance(data, dict):
            dlg_text = None
            try:
                dlg_match = re.search(r'"dialogue"\s*:\s*"(.*?)"\s*,\s*"\w+"', cleaned, re.DOTALL)
                if not dlg_match:
                    dlg_match = re.search(r'"dialogue"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)', cleaned)
                if dlg_match:
                    cand = dlg_match.group(1).replace('\\"', '"').strip()
                    if len(cand) > 2:
                        dlg_text = cand
            except Exception:
                pass

            # Check for dialogue preceding an unclosed '{'
            if not dlg_text:
                fb = cleaned.find("{")
                if fb > 10:
                    cand = cleaned[:fb].strip().strip('`"\'').strip()
                    cand = re.sub(r'["\';}\s]+$', '', cand).strip()
                    if len(cand) > 3 and ("*" in cand or "!" in cand):
                        dlg_text = cand

            # Direct conversational dialogue with roleplay cues (*action* or cries)
            if not dlg_text and ("*" in cleaned or ("!" in cleaned and len(cleaned) > 20)):
                cand = cleaned.strip('`"\'').strip()
                cand = re.sub(r'["\';}\s]+$', '', cand).strip()
                cand = re.sub(r'^["\';{\s]+', '', cand).strip()
                if cand and len(cand) > 1 and not cand.startswith("{"):
                    dlg_text = cand

            if dlg_text:
                emo_match = re.search(r'"emotional_state"\s*:\s*"([^"]+)"', cleaned)
                trust_match = re.search(r'"trust_delta"\s*:\s*(-?[0-9.]+)', cleaned)
                aff_match = re.search(r'"affection_delta"\s*:\s*(-?[0-9.]+)', cleaned)
                data = {
                    "dialogue": dlg_text,
                    "emotional_state": emo_match.group(1) if emo_match else "neutral",
                    "action_type": "interact",
                    "intent": "companion interaction",
                    "confidence": 0.9,
                    "trust_delta": float(trust_match.group(1)) if trust_match else 0.0,
                    "affection_delta": float(aff_match.group(1)) if aff_match else 0.0,
                }
            else:
                return AgentDecision(
                    action_type=AgentActionType.HESITATE,
                    intent="Hesitate due to malformed model response",
                    dialogue="...",
                    emotional_state="confused",
                    rationale="Failed to parse JSON response or returned non-dictionary JSON.",
                    confidence=0.5,
                )

        # Action type normalization
        action_raw = str(data.get("action_type", "hesitate")).strip().lower()
        try:
            action_type = AgentActionType(action_raw)
        except ValueError:
            action_type = AgentActionType.HESITATE

        # Confidence clamping
        try:
            conf = float(data.get("confidence", 0.8))
            conf = max(0.0, min(1.0, conf))
        except (ValueError, TypeError):
            conf = 0.8

        # Safe relationship delta extraction
        try:
            trust_val = float(data["trust_delta"]) if data.get("trust_delta") is not None else 0.0
        except (ValueError, TypeError):
            trust_val = 0.0

        try:
            aff_val = float(data["affection_delta"]) if data.get("affection_delta") is not None else 0.0
        except (ValueError, TypeError):
            aff_val = 0.0

        return AgentDecision(
            action_type=action_type,
            intent=str(data.get("intent", "Autonomous action")),
            target=data.get("target"),
            chosen_move=data.get("chosen_move"),
            dialogue=data.get("dialogue"),
            emotional_state=str(data.get("emotional_state", "neutral")),
            rationale=str(data.get("rationale", "")),
            confidence=conf,
            suggested_alternative=data.get("suggested_alternative"),
            trust_delta=trust_val,
            affection_delta=aff_val,
        )


def _default_http_post(
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: float = DEFAULT_REQUEST_TIMEOUT,
) -> dict[str, Any]:
    """
    Standard library HTTP POST client for executing API requests without external SDK dependencies.
    """
    data_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.HTTPError as err:
        err_body = err.read().decode("utf-8", errors="replace")
        raise AiModelServiceError(
            f"HTTP error {err.code} from AI service: {err.reason}. Response: {err_body}"
        ) from err
    except urllib.error.URLError as err:
        raise AiModelServiceError(f"Network error connecting to AI service: {err.reason}") from err
    except TimeoutError as err:
        raise AiModelServiceError(f"Timeout ({timeout}s) waiting for AI service response.") from err
    except json.JSONDecodeError as err:
        raise AiModelServiceError(f"AI service returned invalid non-JSON HTTP response: {err}") from err


class BaseLiveDecisionProvider(DecisionProvider):
    """
    Base class for real live AI model decision providers.
    Manages credentials, model identifiers, timeout, retries, and transport injection.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "",
        timeout: float = DEFAULT_REQUEST_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        http_client: Optional[Callable[[str, dict[str, str], dict[str, Any], float], dict[str, Any]]] = None,
    ) -> None:
        self.api_key: str = (api_key or "").strip()
        self.model_name: str = model_name
        self.timeout: float = float(timeout)
        self.max_retries: int = max(0, int(max_retries))
        self.http_client = http_client or _default_http_post

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the AI provider."""
        pass

    @property
    @abstractmethod
    def env_var_name(self) -> str:
        """Primary environment variable name for this provider's API key."""
        pass

    @property
    @abstractmethod
    def placeholder_key(self) -> str:
        """Placeholder key string used when unconfigured."""
        pass

    def is_configured(self) -> bool:
        """
        Returns True if the provider has a real, non-placeholder API key configured.
        """
        if not self.api_key:
            return False
        if self.api_key == self.placeholder_key:
            return False
        if "YOUR_" in self.api_key and "_KEY_HERE" in self.api_key:
            return False
        return True

    @abstractmethod
    def _execute_model_call(self, system_instruction: str, user_prompt: str) -> str:
        """
        Executes the provider-specific HTTP call and returns raw output text.
        """
        pass

    def decide(self, agent: PokemonAgent, perception: AgentPerception) -> AgentDecision:
        """
        Generates an autonomous decision using the live AI model.
        Assembles prompts, calls the model, and parses the response.
        """
        if not self.is_configured():
            raise AiConfigurationError(
                f"API key for {self.provider_name} is not configured (current value: '{self.api_key or 'None'}'). "
                f"Please set the {self.env_var_name} environment variable or provide a valid API key."
            )

        system_instruction = PromptBuilder.build_system_instruction(agent)
        user_prompt = PromptBuilder.build_user_prompt(perception)

        last_error: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                raw_response = self._execute_model_call(system_instruction, user_prompt)
                decision = DecisionResponseParser.parse(raw_response)
                return decision
            except Exception as exc:
                last_error = exc
                if attempt == self.max_retries:
                    break

        raise AiModelServiceError(
            f"Failed to generate decision via {self.provider_name} after {self.max_retries + 1} attempts: {last_error}"
        ) from last_error


class GeminiDecisionProvider(BaseLiveDecisionProvider):
    """
    Google Gemini AI decision provider for autonomous Pokemon agents.
    Uses the native Gemini generateContent REST API with JSON response format.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = DEFAULT_GEMINI_MODEL,
        timeout: float = DEFAULT_REQUEST_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        http_client: Optional[Callable[[str, dict[str, str], dict[str, Any], float], dict[str, Any]]] = None,
    ) -> None:
        resolved_key = (
            api_key
            or os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY")
            or GEMINI_API_KEY_DEFAULT
            or GEMINI_API_KEY_PLACEHOLDER
        )
        super().__init__(
            api_key=resolved_key,
            model_name=model_name or DEFAULT_GEMINI_MODEL,
            timeout=timeout,
            max_retries=max_retries,
            http_client=http_client,
        )

    @property
    def provider_name(self) -> str:
        return "Google Gemini"

    @property
    def env_var_name(self) -> str:
        return "GEMINI_API_KEY"

    @property
    def placeholder_key(self) -> str:
        return GEMINI_API_KEY_PLACEHOLDER

    def _execute_model_call(self, system_instruction: str, user_prompt: str) -> str:
        """
        Executes Google Gemini generateContent call via HTTP POST.
        """
        headers = {
            "Content-Type": "application/json",
        }
        payload = {
            "systemInstruction": {
                "parts": [{"text": system_instruction}]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": user_prompt}]
                }
            ],
            "generationConfig": {
                "temperature": 0.7,
                "responseMimeType": "application/json",
            },
        }

        models_to_try = [self.model_name]
        for fb in DEFAULT_GEMINI_FALLBACK_MODELS:
            if fb not in models_to_try:
                models_to_try.append(fb)

        last_err: Optional[Exception] = None
        for m_name in models_to_try:
            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/{m_name}:generateContent"
                f"?key={self.api_key}"
            )
            try:
                resp = self.http_client(url, headers, payload, self.timeout)
                candidates = resp.get("candidates", [])
                if not candidates:
                    continue
                parts = candidates[0].get("content", {}).get("parts", [])
                if not parts:
                    continue
                return parts[0].get("text", "")
            except Exception as err:
                last_err = err
                continue

        if last_err is not None:
            raise last_err
        raise AiModelServiceError(f"Gemini API returned no candidates across models: {models_to_try}")


class OpenAIDecisionProvider(BaseLiveDecisionProvider):
    """
    OpenAI and OpenAI-compatible AI decision provider (e.g. OpenAI, OpenRouter, local Ollama/vLLM).
    Uses the Chat Completions REST API with json_object response format.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = DEFAULT_OPENAI_MODEL,
        base_url: str = "https://api.openai.com/v1",
        timeout: float = DEFAULT_REQUEST_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        http_client: Optional[Callable[[str, dict[str, str], dict[str, Any], float], dict[str, Any]]] = None,
    ) -> None:
        resolved_key = (
            api_key
            or os.environ.get("OPENAI_API_KEY")
            or OPENAI_API_KEY_PLACEHOLDER
        )
        super().__init__(
            api_key=resolved_key,
            model_name=model_name or DEFAULT_OPENAI_MODEL,
            timeout=timeout,
            max_retries=max_retries,
            http_client=http_client,
        )
        self.base_url: str = base_url.rstrip("/")

    @property
    def provider_name(self) -> str:
        return "OpenAI"

    @property
    def env_var_name(self) -> str:
        return "OPENAI_API_KEY"

    @property
    def placeholder_key(self) -> str:
        return OPENAI_API_KEY_PLACEHOLDER

    def _execute_model_call(self, system_instruction: str, user_prompt: str) -> str:
        """
        Executes OpenAI chat completions call via HTTP POST.
        """
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.7,
            "response_format": {"type": "json_object"},
        }

        resp = self.http_client(url, headers, payload, self.timeout)

        # Parse OpenAI response structure: choices[0].message.content
        choices = resp.get("choices", [])
        if not choices:
            raise AiModelServiceError(f"OpenAI API returned no choices. Full response: {resp}")

        content = choices[0].get("message", {}).get("content", "")
        return content


class LiveAIDecisionProvider(DecisionProvider):
    """
    Unified live decision provider wrapper with automated provider selection and fallback.
    Seamlessly routes to Gemini or OpenAI, or falls back to FallbackDecisionHandler if unconfigured.
    """

    def __init__(
        self,
        active_provider: Optional[BaseLiveDecisionProvider] = None,
        allow_mock_fallback: bool = True,
    ) -> None:
        self.active_provider: Optional[BaseLiveDecisionProvider] = active_provider
        self.allow_mock_fallback: bool = allow_mock_fallback

    def is_configured(self) -> bool:
        """Returns True if the underlying live provider is configured with a valid key."""
        return self.active_provider is not None and self.active_provider.is_configured()

    def decide(self, agent: PokemonAgent, perception: AgentPerception) -> AgentDecision:
        """
        Generates an autonomous decision. If the live provider is unconfigured or fails,
        and allow_mock_fallback is True, routes gracefully to safe fallback behavior.
        """
        if self.active_provider is None or not self.active_provider.is_configured():
            if self.allow_mock_fallback:
                return FallbackDecisionHandler.create_fallback(
                    agent,
                    perception,
                    AiConfigurationError("Live AI model is not configured with an active API key.")
                )
            raise AiConfigurationError(
                "No configured live AI provider available. Please set GEMINI_API_KEY or OPENAI_API_KEY."
            )

        try:
            return self.active_provider.decide(agent, perception)
        except Exception as exc:
            if self.allow_mock_fallback:
                return FallbackDecisionHandler.create_fallback(agent, perception, exc)
            raise


def create_live_decision_provider(
    provider_type: str = "auto",
    api_key: Optional[str] = None,
    model_name: Optional[str] = None,
    timeout: float = DEFAULT_REQUEST_TIMEOUT,
    allow_mock_fallback: bool = True,
    http_client: Optional[Callable[[str, dict[str, str], dict[str, Any], float], dict[str, Any]]] = None,
) -> LiveAIDecisionProvider:
    """
    Factory function for instantiating live AI decision providers.

    Args:
        provider_type: "gemini", "openai", or "auto" (detects available environment variables).
        api_key: Optional explicit API key override.
        model_name: Optional explicit model override.
        timeout: HTTP request timeout in seconds.
        allow_mock_fallback: If True, falls back to safe actions when unconfigured or erroring.
        http_client: Optional custom HTTP POST client (for unit testing or custom transports).
    """
    ptype = provider_type.lower().strip()

    if ptype == "local":
        from src.ai.local_model_provider import LocalModelDecisionProvider
        return LocalModelDecisionProvider(
            model_name_or_path=model_name,
            timeout=timeout,
            allow_mock_fallback=allow_mock_fallback,
        )
    elif ptype == "gemini":
        provider = GeminiDecisionProvider(
            api_key=api_key,
            model_name=model_name or DEFAULT_GEMINI_MODEL,
            timeout=timeout,
            http_client=http_client,
        )
    elif ptype == "openai":
        provider = OpenAIDecisionProvider(
            api_key=api_key,
            model_name=model_name or DEFAULT_OPENAI_MODEL,
            base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            timeout=timeout,
            http_client=http_client,
        )
    elif ptype == "ollama":
        base_url = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1")
        provider = OpenAIDecisionProvider(
            api_key=api_key or "ollama",
            model_name=model_name or os.environ.get("OLLAMA_MODEL", "qwen2.5:3b"),
            base_url=base_url,
            timeout=timeout,
            http_client=http_client,
        )
    elif ptype == "auto":
        use_local = os.environ.get("POKEMON_AI_PROVIDER", "").lower() == "local" or os.environ.get("USE_LOCAL_POKEMON_MODEL") == "1"
        if use_local:
            from src.ai.local_model_provider import LocalModelDecisionProvider
            return LocalModelDecisionProvider(
                model_name_or_path=model_name,
                timeout=timeout,
                allow_mock_fallback=allow_mock_fallback,
            )

        # Check explicit api_key or env vars
        resolved_gemini_key = (
            api_key if (api_key and (api_key.startswith("AIza") or "gemini" in (model_name or "").lower()))
            else (
                os.environ.get("GEMINI_API_KEY")
                or os.environ.get("GOOGLE_API_KEY")
                or (GEMINI_API_KEY_DEFAULT and GEMINI_API_KEY_DEFAULT != GEMINI_API_KEY_PLACEHOLDER)
            )
        )
        resolved_openai_key = (
            api_key if (api_key and (api_key.startswith("sk-") or "gpt" in (model_name or "").lower()))
            else os.environ.get("OPENAI_API_KEY")
        )

        if resolved_gemini_key:
            provider = GeminiDecisionProvider(
                api_key=resolved_gemini_key,
                model_name=model_name or DEFAULT_GEMINI_MODEL,
                timeout=timeout,
                http_client=http_client,
            )
        elif resolved_openai_key:
            provider = OpenAIDecisionProvider(
                api_key=resolved_openai_key,
                model_name=model_name or DEFAULT_OPENAI_MODEL,
                base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
                timeout=timeout,
                http_client=http_client,
            )
        elif os.environ.get("OPENAI_BASE_URL") or os.environ.get("OLLAMA_BASE_URL"):
            base_url = os.environ.get("OPENAI_BASE_URL") or os.environ.get("OLLAMA_BASE_URL")
            provider = OpenAIDecisionProvider(
                api_key=api_key or "ollama",
                model_name=model_name or os.environ.get("OLLAMA_MODEL", "qwen2.5:3b"),
                base_url=base_url,
                timeout=timeout,
                http_client=http_client,
            )
        else:
            # Check if generic api_key was provided without recognized prefix
            if api_key and api_key != GEMINI_API_KEY_PLACEHOLDER and api_key != OPENAI_API_KEY_PLACEHOLDER:
                provider = GeminiDecisionProvider(
                    api_key=api_key,
                    model_name=model_name or DEFAULT_GEMINI_MODEL,
                    timeout=timeout,
                    http_client=http_client,
                )
            else:
                provider = GeminiDecisionProvider(
                    api_key=GEMINI_API_KEY_PLACEHOLDER,
                    model_name=model_name or DEFAULT_GEMINI_MODEL,
                    timeout=timeout,
                    http_client=http_client,
                )
    else:
        raise ValueError(f"Unsupported AI provider_type: '{provider_type}'. Must be 'gemini', 'openai', 'ollama', 'local', or 'auto'.")

    return LiveAIDecisionProvider(active_provider=provider, allow_mock_fallback=allow_mock_fallback)
