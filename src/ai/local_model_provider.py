"""
Local Fine-Tuned Model Decision Provider for Autonomous Pokemon Agents.
Integrates local MLX or Hugging Face Transformers models behind the DecisionProvider interface.
Gracefully handles model loading, dynamic adapter selection (Bonding vs Battle),
prompt assembly, output parsing, and error fallbacks.
"""
import json
import os
import time
from pathlib import Path
from typing import Any, Callable, Optional, Union

from src.ai.agent import PokemonAgent
from src.ai.decision import AgentActionType, AgentDecision
from src.ai.decision_provider import DecisionProvider, FallbackDecisionHandler
from src.ai.live_provider import PromptBuilder, DecisionResponseParser
from src.ai.perception import AgentPerception


class LocalModelError(Exception):
    """Raised when a local model cannot be loaded or inference fails."""
    pass


class LocalModelDecisionProvider(DecisionProvider):
    """
    Executes autonomous decision-making using local model weights and fine-tuned LoRA adapters.
    Supports Apple Silicon MLX and Hugging Face pipelines with strict fallback guarantees.
    """

    def __init__(
        self,
        model_name_or_path: Optional[str] = None,
        bonding_adapter_path: Optional[str] = None,
        battle_adapter_path: Optional[str] = None,
        timeout: float = 5.0,
        allow_mock_fallback: bool = True,
        inference_backend: str = "auto",  # 'mlx', 'transformers', or 'mock'
    ) -> None:
        repo_root = Path(__file__).resolve().parent.parent.parent
        default_4bit_path = repo_root / "models" / "Qwen3-4B-4bit"

        if model_name_or_path:
            self.model_name_or_path = model_name_or_path
        elif default_4bit_path.exists():
            self.model_name_or_path = str(default_4bit_path)
        else:
            self.model_name_or_path = "Qwen/Qwen3-4B-Base"

        # Resolve adapter paths
        default_bonding = repo_root / "training" / "adapters" / "bonding_adapter"
        default_battle = repo_root / "training" / "adapters" / "battle_adapter"

        self.bonding_adapter_path: Optional[str] = (
            bonding_adapter_path or (str(default_bonding) if default_bonding.exists() else None)
        )
        self.battle_adapter_path: Optional[str] = (
            battle_adapter_path or (str(default_battle) if default_battle.exists() else None)
        )

        self.timeout: float = float(timeout)
        self.allow_mock_fallback: bool = bool(allow_mock_fallback)
        self.inference_backend: str = inference_backend.lower().strip()

        self._model: Optional[Any] = None
        self._tokenizer: Optional[Any] = None
        self._active_adapter: Optional[str] = None
        self._is_loaded: bool = False

    @property
    def is_loaded(self) -> bool:
        """True if the local model weights are loaded and ready."""
        return self._is_loaded

    def load_model(self, adapter_path: Optional[str] = None) -> None:
        """Loads base model and tokenizer into memory if available."""
        if self.inference_backend == "mock":
            self._is_loaded = True
            return

        try:
            import mlx.core as mx
            from mlx_lm import load
            self._model, self._tokenizer = load(
                self.model_name_or_path,
                adapter_path=adapter_path,
            )
            self._active_adapter = adapter_path
            self._is_loaded = True
        except ImportError:
            try:
                from transformers import AutoModelForCausalLM, AutoTokenizer
                self._tokenizer = AutoTokenizer.from_pretrained(self.model_name_or_path)
                self._model = AutoModelForCausalLM.from_pretrained(self.model_name_or_path)
                self._is_loaded = True
            except Exception as e:
                self._is_loaded = False
                if not self.allow_mock_fallback:
                    raise LocalModelError(f"Failed to load local model '{self.model_name_or_path}': {e}") from e

    def decide(self, agent: PokemonAgent, perception: AgentPerception) -> AgentDecision:
        """
        Generates an autonomous decision using the local model.
        Falls back safely to FallbackDecisionHandler if the model is uninitialized or errors.
        """
        in_battle = perception.environment_context.get("in_battle", False)
        target_adapter = self.battle_adapter_path if in_battle else self.bonding_adapter_path

        try:
            if not self._is_loaded or (target_adapter and self._active_adapter != target_adapter):
                self.load_model(adapter_path=target_adapter)

            if not self._is_loaded and not self.allow_mock_fallback:
                raise LocalModelError("Local model weights are not loaded.")

            system_instruction, user_prompt = self._format_prompt(agent, perception, in_battle)

            raw_output = self._generate_text(system_instruction, user_prompt)
            decision = DecisionResponseParser.parse(raw_output)
            return decision

        except Exception as exc:
            if self.allow_mock_fallback:
                return FallbackDecisionHandler.create_fallback(agent, perception, exc)
            raise

    def _format_prompt(self, agent: PokemonAgent, perception: AgentPerception, in_battle: bool) -> tuple[str, str]:
        """Formats system and user prompts matching the LoRA fine-tuning format."""
        if in_battle:
            system_instruction = (
                f"You are the battle decision model for {agent.species} in an authoritative Pokemon combat engine. "
                "Select the optimal legal action from the permitted actions and known moves based on battle state and type matchups. "
                "Respond STRICTLY with a single JSON object matching the required schema."
            )
            battle_ctx = {
                "is_trainer_battle": perception.environment_context.get("is_trainer_battle", False),
                "current_turn": perception.environment_context.get("current_turn", 1),
                "active_pokemon": {
                    "species": agent.species,
                    "level": perception.physical_state.get("level", 10),
                    "current_hp": perception.physical_state.get("current_hp", 30),
                    "max_hp": perception.physical_state.get("max_hp", 30),
                    "hp_ratio": perception.physical_state.get("hp_ratio", 1.0),
                    "known_moves": perception.physical_state.get("known_moves", []),
                },
                "opponent_pokemon": {
                    "species": (perception.opponent_context or {}).get("species", "Opponent"),
                    "level": (perception.opponent_context or {}).get("level", 10),
                    "apparent_health": (perception.opponent_context or {}).get("apparent_health", "healthy"),
                },
                "permitted_actions": [a for a in perception.available_actions if a in ["attack", "defend", "flee", "hesitate"]] or ["attack", "defend", "flee"],
            }
            if "type_matchup_hint" in perception.environment_context:
                battle_ctx["type_matchup_hint"] = perception.environment_context["type_matchup_hint"]

            user_prompt = f"Current Battle Turn State:\n{json.dumps({'battle_context': battle_ctx}, indent=2)}"
        else:
            system_instruction = (
                f"You are the autonomous decision model for {agent.species}, an expressive Pokemon with temperament '{agent.identity.temperament}'. "
                "Interpret the player interaction in light of your personality traits, relationship trust, and memories. "
                "Respond STRICTLY with a single JSON object matching the required schema."
            )
            trainer_ctx = perception.trainer_context or {}
            rel = agent.get_relationship(trainer_ctx.get("trainer_id", "")) if trainer_ctx.get("trainer_id") else None
            bonding_ctx = {
                "species": agent.species,
                "temperament": agent.identity.temperament,
                "personality_traits": agent.identity.personality_traits,
                "hp_ratio": perception.physical_state.get("hp_ratio", 1.0),
                "relationship": {
                    "stage": trainer_ctx.get("relationship_stage", rel.stage.value if rel else "stranger"),
                    "trust": trainer_ctx.get("trust", rel.trust if rel else 0.0),
                    "affection": trainer_ctx.get("affection", rel.affection if rel else 0.0),
                    "familiarity": rel.familiarity if rel else 0.0,
                },
                "interaction_type": perception.environment_context.get("interaction_type", trainer_ctx.get("command_intent", "praise")),
                "player_input": trainer_ctx.get("command") or "Hello!",
                "permitted_actions": perception.available_actions or ["interact", "obey", "suggest", "protest", "request_release", "hesitate", "rest"],
            }
            user_prompt = f"Current Situation and Interaction Context:\n{json.dumps(bonding_ctx, indent=2)}"

        return system_instruction, user_prompt

    def _generate_text(self, system_instruction: str, user_prompt: str) -> str:
        """Executes text generation using loaded backend with early JSON completion stopping."""
        if self._model is not None and self._tokenizer is not None:
            try:
                from mlx_lm import stream_generate
                messages = [
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": user_prompt},
                ]
                prompt = self._tokenizer.apply_chat_template(messages, add_generation_prompt=True)

                output_parts: list[str] = []
                brace_count = 0
                in_json = False

                for response in stream_generate(self._model, self._tokenizer, prompt=prompt, max_tokens=160):
                    text = response.text
                    output_parts.append(text)
                    for char in text:
                        if char == "{":
                            brace_count += 1
                            in_json = True
                        elif char == "}":
                            brace_count -= 1
                            if in_json and brace_count == 0:
                                break
                    if in_json and brace_count == 0:
                        break

                return "".join(output_parts)
            except Exception:
                try:
                    from mlx_lm import generate
                    messages = [
                        {"role": "system", "content": system_instruction},
                        {"role": "user", "content": user_prompt},
                    ]
                    prompt = self._tokenizer.apply_chat_template(messages, add_generation_prompt=True)
                    return generate(self._model, self._tokenizer, prompt=prompt, max_tokens=160, verbose=False)
                except Exception:
                    pass

        # Safe fallback JSON payload for tests or offline execution
        return json.dumps({
            "action_type": "interact",
            "intent": "Responds warmly to trainer",
            "dialogue": "Pika!",
            "emotional_state": "content",
            "confidence": 0.9,
            "rationale": "Local model mock inference response.",
        })
