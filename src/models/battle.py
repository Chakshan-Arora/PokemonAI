"""
Battle engine implementing turn-based combat between two Pokemon.
"""
from enum import Enum
import random
import uuid
from dataclasses import dataclass
from typing import Optional, Sequence, Any, Union
from src.models.pokemon import Pokemon
from src.models.attack import Attack
from src.models.battle_state import BattleState
from src.models.damage_calculator import calculate_damage
from src.data.type_chart import get_effectiveness_against_pokemon
from src.models.status_effect import StatusEffectType
from src.models.status_effect_manager import StatusEffectManager


class BattleActionType(str, Enum):
    """
    Supported battle action categories for player and opponent decisions.
    """
    ATTACK = "ATTACK"
    SWITCH = "SWITCH"
    FLEE = "FLEE"
    CAPTURE = "CAPTURE"
    USE_ITEM = "USE_ITEM"
    INSPECT = "INSPECT"


@dataclass(frozen=True)
class BattleAction:
    """
    Action command selected for a battle turn.
    """
    action_type: BattleActionType
    attack: Optional[Attack] = None
    target_pokemon: Optional[Pokemon] = None
    item_id: Optional[str] = None


@dataclass(frozen=True)
class BattleActionRecord:
    """
    Structured outcome of a single attack execution during a turn.
    """
    attacker: Pokemon
    defender: Pokemon
    attack: Attack
    hit: bool
    damage: int
    type_effectiveness: float
    defender_hp_remaining: int
    message: str
    is_critical: bool = False


@dataclass(frozen=True)
class TurnResult:
    """
    Structured outcome of a completed turn, containing all executed actions.
    """
    turn_number: int
    actions: tuple[BattleActionRecord, ...]
    battle_state: BattleState
    winner: Optional[Pokemon] = None
    loser: Optional[Pokemon] = None


@dataclass(frozen=True)
class BattleActionResult:
    """
    Structured outcome of executing a validated battle action.
    """
    accepted: bool
    reason: str
    action_type: BattleActionType
    battle_state: BattleState
    turn_result: Optional[TurnResult] = None
    switched_pokemon: Optional[Pokemon] = None
    captured: bool = False
    escaped: bool = False
    terminal: bool = False
    error_type: Optional[str] = None


class Battle:
    """
    Turn-based battle manager between two Pokemon participants.
    Manages turn order, attack execution, damage calculation, HP updates,
    and battle lifecycle states.
    """

    def __init__(
        self,
        pokemon1: Pokemon,
        pokemon2: Pokemon,
        rng: Optional[random.Random] = None,
        seed: Optional[int] = None,
        use_random_damage: bool = True,
        battle_id: Optional[str] = None,
        status_manager: Optional[StatusEffectManager] = None,
        player: Optional[Any] = None,
        opponent_trainer: Optional[Any] = None,
        encounter: Optional[Any] = None,
        player_team: Optional[Sequence[Pokemon]] = None,
        opponent_team: Optional[Sequence[Pokemon]] = None,
        region_id: Optional[str] = None,
        decision_model: Optional[Any] = None,
        use_wild_ai: Optional[bool] = None,
        wild_agent: Optional[Any] = None,
        player_agent: Optional[Any] = None,
        ai_provider: Optional[Any] = None,
        ai_state: Optional[Any] = None,
        trainer_ai: Optional[Any] = None,
    ) -> None:
        if not isinstance(pokemon1, Pokemon):
            raise TypeError(f"pokemon1 must be a Pokemon instance, got {type(pokemon1).__name__}.")
        if not isinstance(pokemon2, Pokemon):
            raise TypeError(f"pokemon2 must be a Pokemon instance, got {type(pokemon2).__name__}.")
        if pokemon1 is pokemon2 or pokemon1.unique_id == pokemon2.unique_id:
            raise ValueError("A Pokemon cannot battle itself.")

        self._pokemon1: Pokemon = pokemon1
        self._pokemon2: Pokemon = pokemon2
        self._use_random_damage: bool = use_random_damage
        self._battle_id: str = str(battle_id) if battle_id is not None else str(uuid.uuid4())
        self._rewards_claimed: bool = False
        self._bond_rewards_claimed: bool = False
        self._player: Optional[Any] = player
        self._opponent_trainer: Optional[Any] = opponent_trainer
        self._encounter: Optional[Any] = encounter
        self._decision_model = decision_model
        self._wild_agent: Optional[Any] = wild_agent
        self._player_agent: Optional[Any] = player_agent
        self._ai_provider: Optional[Any] = ai_provider
        self._ai_state: Optional[Any] = ai_state
        self._trainer_ai: Optional[Any] = trainer_ai
        if use_wild_ai is not None:
            self._use_wild_ai: bool = bool(use_wild_ai)
        else:
            self._use_wild_ai: bool = (encounter is not None or wild_agent is not None)

        if region_id is not None:
            if not isinstance(region_id, str) or not region_id.strip():
                raise ValueError("region_id must be a non-empty string or None.")
            self._region_id: Optional[str] = region_id.strip().lower()
        elif encounter is not None:
            enc_reg = getattr(encounter, "region_id", None)
            if enc_reg is not None and isinstance(enc_reg, str) and enc_reg.strip():
                self._region_id = enc_reg.strip().lower()
            elif getattr(encounter, "area", None) is not None and getattr(encounter.area, "region_id", None) is not None:
                self._region_id = str(encounter.area.region_id).strip().lower()
            else:
                self._region_id = None
        else:
            self._region_id = None

        # Establish player battle team
        if player_team is not None:
            self._player_team: list[Pokemon] = list(player_team)
        elif player is not None and getattr(player, "team", None):
            self._player_team = list(player.team)
        else:
            self._player_team = [pokemon1]
        if pokemon1 not in self._player_team:
            self._player_team.insert(0, pokemon1)

        # Establish opponent battle team
        if opponent_team is not None:
            self._opponent_team: list[Pokemon] = list(opponent_team)
        elif opponent_trainer is not None and getattr(opponent_trainer, "team", None):
            self._opponent_team = list(opponent_trainer.team)
        else:
            self._opponent_team = [pokemon2]
        if pokemon2 not in self._opponent_team:
            self._opponent_team.insert(0, pokemon2)

        if rng is not None:
            self._rng = rng
        elif seed is not None:
            self._rng = random.Random(seed)
        else:
            self._rng = random.Random()

        if status_manager is not None:
            self._status_manager = status_manager
        else:
            self._status_manager = StatusEffectManager(rng=self._rng)

        self._state: BattleState = BattleState.NOT_STARTED
        self._current_turn: int = 0
        self._winner: Optional[Pokemon] = None
        self._loser: Optional[Pokemon] = None

        self._events: list[str] = []
        self._history: list[TurnResult] = []
        self._selected_attacks: dict[str, Attack] = {}

    # --- Properties ---

    @property
    def player(self) -> Optional[Any]:
        """Player associated with this battle, if applicable."""
        return self._player

    @property
    def opponent_trainer(self) -> Optional[Any]:
        """Opponent trainer associated with this battle, if applicable."""
        return self._opponent_trainer

    @property
    def encounter(self) -> Optional[Any]:
        """WildEncounter session associated with this battle, if applicable."""
        return self._encounter

    @property
    def region_id(self) -> Optional[str]:
        """Region identifier where this battle takes place, if known."""
        if self._region_id is not None:
            return self._region_id
        if self._encounter is not None:
            enc_reg = getattr(self._encounter, "region_id", None)
            if enc_reg is not None and isinstance(enc_reg, str) and enc_reg.strip():
                return enc_reg.strip().lower()
            area = getattr(self._encounter, "area", None)
            if area is not None and getattr(area, "region_id", None) is not None:
                return str(area.region_id).strip().lower()
        return None

    @property
    def is_wild_battle(self) -> bool:
        """True if opposing participant is a wild Pokemon, False if an opponent trainer."""
        return self._opponent_trainer is None

    @property
    def is_trainer_battle(self) -> bool:
        """True if battling against an opponent trainer."""
        return self._opponent_trainer is not None

    @property
    def player_team(self) -> list[Pokemon]:
        """Copy of the player's battle team."""
        return list(self._player_team)

    @property
    def opponent_team(self) -> list[Pokemon]:
        """Copy of the opponent's battle team."""
        return list(self._opponent_team)

    @property
    def active_player_pokemon(self) -> Pokemon:
        """Currently active player Pokemon."""
        return self._pokemon1

    @property
    def active_opponent_pokemon(self) -> Pokemon:
        """Currently active opponent Pokemon."""
        return self._pokemon2

    @property
    def battle_id(self) -> str:
        """Unique UUID identifier for this battle instance."""
        return self._battle_id

    @property
    def rewards_claimed(self) -> bool:
        """Whether victory rewards have already been claimed for this battle."""
        return self._rewards_claimed

    @rewards_claimed.setter
    def rewards_claimed(self, value: bool) -> None:
        self._rewards_claimed = bool(value)

    @property
    def bond_rewards_claimed(self) -> bool:
        """Whether victory bond rewards have already been claimed for this battle."""
        return self._bond_rewards_claimed

    @bond_rewards_claimed.setter
    def bond_rewards_claimed(self, value: bool) -> None:
        self._bond_rewards_claimed = bool(value)

    @property
    def pokemon1(self) -> Pokemon:
        """First battle participant (typically player's Pokemon)."""
        return self._pokemon1

    @property
    def pokemon2(self) -> Pokemon:
        """Second battle participant (opponent or wild Pokemon)."""
        return self._pokemon2

    @property
    def state(self) -> BattleState:
        """Current lifecycle state of the battle."""
        return self._state

    @property
    def current_turn(self) -> int:
        """Current turn number (1-indexed once started)."""
        return self._current_turn

    @property
    def winner(self) -> Optional[Pokemon]:
        """Winning Pokemon, or None if unfinished or draw."""
        return self._winner

    @property
    def loser(self) -> Optional[Pokemon]:
        """Defeated Pokemon, or None if unfinished or draw."""
        return self._loser

    @property
    def events(self) -> list[str]:
        """Chronological list of battle log events."""
        return list(self._events)

    @property
    def turn_history(self) -> list[TurnResult]:
        """Historical records of all resolved turns."""
        return list(self._history)

    @property
    def status_manager(self) -> StatusEffectManager:
        """StatusEffectManager tracking active effects for this battle."""
        return self._status_manager

    @property
    def is_wild_battle(self) -> bool:
        """True if the opposing combatant is a wild Pokemon, False if trainer battle."""
        return not self.is_trainer_battle

    @property
    def use_wild_ai(self) -> bool:
        """Whether the wild decision model is active for this battle."""
        return self._use_wild_ai

    @use_wild_ai.setter
    def use_wild_ai(self, value: bool) -> None:
        self._use_wild_ai = bool(value)

    @property
    def wild_agent(self) -> Optional[Any]:
        """Autonomous AI agent controlling the wild Pokemon, if active."""
        return self._wild_agent

    @property
    def player_agent(self) -> Optional[Any]:
        """Autonomous AI agent controlling the player's companion Pokemon, if active."""
        return self._player_agent

    @property
    def ai_provider(self) -> Optional[Any]:
        """AI decision provider driving autonomous agents in this battle."""
        return self._ai_provider

    @property
    def trainer_ai(self) -> Any:
        """Tactical AI model driving opponent trainer turns."""
        if self._trainer_ai is None:
            from src.models.trainer_ai import TrainerAIDecisionModel
            self._trainer_ai = TrainerAIDecisionModel(rng=self._rng)
        return self._trainer_ai

    @trainer_ai.setter
    def trainer_ai(self, value: Any) -> None:
        self._trainer_ai = value

    def decide_wild_action(self) -> Any:
        """
        Evaluates and decides the wild Pokemon's action.
        If an autonomous PokemonAgent is assigned, queries the AI decision pipeline.
        Otherwise falls back to the deterministic WildDecisionModel.
        """
        if self._wild_agent is not None:
            from src.ai.wild_encounter_service import AutonomousWildService
            decision = AutonomousWildService.decide_turn(
                agent=self._wild_agent,
                wild_pokemon=self._pokemon2,
                player_pokemon=self._pokemon1,
                player=self._player,
                battle=self,
                provider=self._ai_provider,
                region_id=self._region_id,
            )
            dialogue = decision.factors.get("dialogue")
            if dialogue:
                self._events.append(f"Wild {self._pokemon2.display_name}: \"{dialogue}\"")
            return decision

        if self._decision_model is None:
            from src.models.wild_ai import WildDecisionModel
            self._decision_model = WildDecisionModel()
        return self._decision_model.decide_action(
            wild_pokemon=self._pokemon2,
            player_pokemon=self._pokemon1,
            player=self._player,
            rng=self._rng,
        )

    def clear_status_effects(self) -> None:
        """Clears all active status effects on both participants."""
        self._status_manager.clear_effects(self._pokemon1)
        self._status_manager.clear_effects(self._pokemon2)

    # --- Lifecycle ---

    def start(self) -> BattleState:
        """
        Starts the battle.
        Verifies both participants have HP > 0, clears lingering status effects,
        and transitions state to IN_PROGRESS.
        """
        if self._state != BattleState.NOT_STARTED:
            raise RuntimeError(f"Cannot start battle: battle is already in state '{self._state.value}'.")

        if self._pokemon1.is_fainted:
            raise ValueError(f"Cannot start battle: {self._pokemon1.display_name} has fainted.")
        if self._pokemon2.is_fainted:
            raise ValueError(f"Cannot start battle: {self._pokemon2.display_name} has fainted.")

        # Ensure participants start battle fresh without residual status effects
        self.clear_status_effects()

        self._state = BattleState.IN_PROGRESS
        self._current_turn = 1
        msg = f"Battle started between {self._pokemon1.display_name} and {self._pokemon2.display_name}!"
        self._events.append(msg)
        return self._state

    # --- Turn Actions ---

    def select_attack(self, pokemon: Pokemon, attack: Attack) -> None:
        """
        Selects an attack for a participant for the upcoming turn.
        Verifies ownership of the attack and battle state.
        """
        if self._state != BattleState.IN_PROGRESS:
            raise RuntimeError(f"Cannot select attack: battle is not in progress (current: {self._state.value}).")

        if pokemon is not self._pokemon1 and pokemon is not self._pokemon2:
            raise ValueError(f"Pokemon '{pokemon.display_name}' is not a participant in this battle.")

        if pokemon.is_fainted:
            raise ValueError(f"Fainted Pokemon '{pokemon.display_name}' cannot select an attack.")

        if not isinstance(attack, Attack):
            raise TypeError(f"attack must be an Attack instance, got {type(attack).__name__}.")

        if attack not in pokemon.attacks:
            raise ValueError(f"Pokemon '{pokemon.display_name}' does not know the attack '{attack.name}'.")

        self._selected_attacks[pokemon.unique_id] = attack

    def _determine_turn_order(
        self,
        attack1: Attack,
        attack2: Attack,
    ) -> tuple[tuple[Pokemon, Attack, Pokemon], tuple[Pokemon, Attack, Pokemon]]:
        """
        Determines which Pokemon acts first based on Speed stats.
        Ties are broken deterministically using the injected RNG.
        Returns: ((first_attacker, first_attack, first_defender), (second_attacker, second_attack, second_defender))
        """
        speed1 = getattr(self._pokemon1, "speed", self._pokemon1.species.base_speed)
        speed2 = getattr(self._pokemon2, "speed", self._pokemon2.species.base_speed)

        if speed1 > speed2:
            first_acts_p1 = True
        elif speed2 > speed1:
            first_acts_p1 = False
        else:
            # Equal Speed tie-breaker
            first_acts_p1 = self._rng.choice([True, False])

        if first_acts_p1:
            return (
                (self._pokemon1, attack1, self._pokemon2),
                (self._pokemon2, attack2, self._pokemon1),
            )
        else:
            return (
                (self._pokemon2, attack2, self._pokemon1),
                (self._pokemon1, attack1, self._pokemon2),
            )

    def _execute_action(
        self,
        attacker: Pokemon,
        attack: Attack,
        defender: Pokemon,
    ) -> BattleActionRecord:
        """
        Executes a single attack action, evaluating paralysis, accuracy, effectiveness,
        damage, and move effects.
        """
        # 1. Paralysis action check
        can_act_res = self._status_manager.check_can_act(attacker)
        if not can_act_res.can_act:
            msg = f"{attacker.display_name} is paralyzed! It can't move!"
            self._events.append(f"[Turn {self._current_turn}] {msg}")
            return BattleActionRecord(
                attacker=attacker,
                defender=defender,
                attack=attack,
                hit=False,
                damage=0,
                type_effectiveness=1.0,
                defender_hp_remaining=defender.current_hp,
                message=msg,
            )

        # 2. Accuracy check (accuracy is an integer between 0 and 100)
        roll = self._rng.randint(1, 100)
        hit = roll <= attack.accuracy

        is_crit = False
        if hit:
            eff = get_effectiveness_against_pokemon(attack, defender)
            dmg_res = calculate_damage(
                attacker=attacker,
                defender=defender,
                attack=attack,
                type_effectiveness=eff,
                rng=self._rng,
                use_random_factor=self._use_random_damage,
                status_manager=self._status_manager,
                bond=getattr(attacker, "bond", 0),
                use_critical=True,
            )
            dmg = dmg_res.damage
            is_crit = dmg_res.is_critical
            if dmg > 0:
                defender.take_damage(dmg)
                if self._wild_agent is not None:
                    from src.ai.wild_encounter_service import AutonomousWildService
                    if defender is self._pokemon2:
                        AutonomousWildService.record_combat_damage(
                            agent=self._wild_agent,
                            damage=dmg,
                            attacker_pokemon=attacker,
                            player=self._player,
                        )
                    elif attacker is self._pokemon2:
                        AutonomousWildService.record_combat_strike(
                            agent=self._wild_agent,
                            damage=dmg,
                            attack_name=attack.name,
                            defender_pokemon=defender,
                        )
                if self._player_agent is not None:
                    if defender is self._pokemon1:
                        self._player_agent.record_experience(
                            event_type="combat_damage",
                            summary=f"Took {dmg} damage from {attacker.display_name}",
                            emotional_impact=-0.2 - min(0.6, dmg / 50.0),
                            involved_entities=[attacker.unique_id],
                            details={"damage": dmg, "attacker": attacker.display_name},
                        )
                    elif attacker is self._pokemon1:
                        self._player_agent.record_experience(
                            event_type="combat_strike",
                            summary=f"Struck {defender.display_name} with {attack.name} for {dmg} damage",
                            emotional_impact=0.2,
                            involved_entities=[defender.unique_id],
                            details={"damage": dmg, "attack": attack.name},
                        )
                msg = f"{attacker.display_name} used {attack.name}! Hit for {dmg} damage."
                if is_crit:
                    msg += " A critical hit!"
                if eff >= 2.0:
                    msg += " It's super effective!"
                elif 0.0 < eff < 1.0:
                    msg += " It's not very effective..."
                elif eff == 0.0:
                    msg += " It had no effect!"
            else:
                msg = f"{attacker.display_name} used {attack.name}!"

            # 3. Apply move effect if defined and target remains eligible (not fainted)
            if getattr(attack, "effect", None) is not None:
                effect_target = attacker if attack.effect.target == "user" else defender
                if not effect_target.is_fainted:
                    app_res = self._status_manager.apply_attack_effect(
                        attacker=attacker,
                        defender=defender,
                        effect=attack.effect,
                        source_attack_name=attack.name,
                    )
                    if app_res.applied:
                        self._events.append(f"[Turn {self._current_turn}] {app_res.reason}")
                        msg += f" {app_res.reason}"
        else:
            dmg = 0
            eff = get_effectiveness_against_pokemon(attack, defender)
            msg = f"{attacker.display_name} used {attack.name}! But it missed!"

        record = BattleActionRecord(
            attacker=attacker,
            defender=defender,
            attack=attack,
            hit=hit,
            damage=dmg,
            type_effectiveness=eff,
            defender_hp_remaining=defender.current_hp,
            message=msg,
            is_critical=is_crit,
        )
        self._events.append(f"[Turn {self._current_turn}] {msg} ({defender.display_name} HP: {defender.current_hp}/{defender.max_hp})")
        return record

    def resolve_turn(
        self,
        attack1: Optional[Attack] = None,
        attack2: Optional[Attack] = None,
    ) -> TurnResult:
        """
        Resolves a turn in the battle.
        Accepts attacks directly or uses previously selected attacks.
        Determines turn order, resolves actions, updates HP, processes end-of-turn
        status damage and expirations, and checks victory/defeat conditions.
        """
        if self._state == BattleState.NOT_STARTED:
            raise RuntimeError("Cannot resolve turn: battle has not started yet. Call start() first.")
        if self._state.is_terminal():
            raise RuntimeError(f"Cannot resolve turn: battle has already concluded with result '{self._state.value}'.")

        # Select attacks if provided as arguments
        if attack1 is not None:
            self.select_attack(self._pokemon1, attack1)
        if attack2 is not None:
            self.select_attack(self._pokemon2, attack2)

        if (
            self._pokemon1.unique_id not in self._selected_attacks
            or self._pokemon2.unique_id not in self._selected_attacks
        ):
            raise ValueError("Both Pokemon must have an attack selected before resolving the turn.")

        atk1 = self._selected_attacks.pop(self._pokemon1.unique_id)
        atk2 = self._selected_attacks.pop(self._pokemon2.unique_id)

        first_action_tuple, second_action_tuple = self._determine_turn_order(atk1, atk2)
        first_attacker, first_attack, first_defender = first_action_tuple
        second_attacker, second_attack, second_defender = second_action_tuple

        executed_actions: list[BattleActionRecord] = []

        # 1. First Pokemon acts
        first_record = self._execute_action(first_attacker, first_attack, first_defender)
        executed_actions.append(first_record)

        # Check if first action resulted in knockouts
        if first_defender.is_fainted or first_attacker.is_fainted:
            if first_defender.is_fainted:
                self._events.append(f"{first_defender.display_name} fainted!")
            if first_attacker.is_fainted:
                self._events.append(f"{first_attacker.display_name} fainted!")
            self._update_terminal_state()
            turn_result = TurnResult(
                turn_number=self._current_turn,
                actions=tuple(executed_actions),
                battle_state=self._state,
                winner=self._winner,
                loser=self._loser,
            )
            self._history.append(turn_result)
            if not self._state.is_terminal():
                self._current_turn += 1
            return turn_result

        # 2. Second Pokemon acts (only if it didn't faint)
        second_record = self._execute_action(second_attacker, second_attack, second_defender)
        executed_actions.append(second_record)

        # Check if second action resulted in knockouts
        if second_defender.is_fainted or second_attacker.is_fainted:
            if second_defender.is_fainted:
                self._events.append(f"{second_defender.display_name} fainted!")
            if second_attacker.is_fainted:
                self._events.append(f"{second_attacker.display_name} fainted!")
            self._update_terminal_state()
            turn_result = TurnResult(
                turn_number=self._current_turn,
                actions=tuple(executed_actions),
                battle_state=self._state,
                winner=self._winner,
                loser=self._loser,
            )
            self._history.append(turn_result)
            if not self._state.is_terminal():
                self._current_turn += 1
            return turn_result

        # 3. End-of-turn status phase (burn/poison damage, duration decrement, expirations)
        if not self._state.is_terminal():
            for mon in (first_attacker, second_attacker):
                if not mon.is_fainted:
                    eot_res = self._status_manager.process_end_of_turn(mon)
                    for eff_rec in eot_res.effects_processed:
                        if eff_rec.damage > 0:
                            self._events.append(f"[Turn {self._current_turn}] {eff_rec.message}")
                    for exp_type in eot_res.expired_effects:
                        self._events.append(f"[Turn {self._current_turn}] {mon.display_name}'s {exp_type.display_name} wore off!")
                    if mon.is_fainted:
                        self._events.append(f"{mon.display_name} fainted!")

            # Check if any knockout occurred during end-of-turn
            if self._pokemon1.is_fainted or self._pokemon2.is_fainted:
                self._update_terminal_state()
            if not self._state.is_terminal():
                self._current_turn += 1

        turn_result = TurnResult(
            turn_number=self._current_turn if self._state.is_terminal() else self._current_turn - 1,
            actions=tuple(executed_actions),
            battle_state=self._state,
            winner=self._winner,
            loser=self._loser,
        )
        self._history.append(turn_result)
        return turn_result

    def execute_turn(self, attack1: Attack, attack2: Attack) -> TurnResult:
        """Convenience method resolving a turn with specified attacks."""
        return self.resolve_turn(attack1=attack1, attack2=attack2)

    def _update_terminal_state(self) -> None:
        """Evaluates participant HP and team status to transition to terminal state."""
        p1_fainted = self._pokemon1.is_fainted
        p2_fainted = self._pokemon2.is_fainted

        if p1_fainted and p2_fainted:
            p1_has_more = any(not p.is_fainted for p in self._player_team if p is not self._pokemon1)
            p2_has_more = any(not p.is_fainted for p in self._opponent_team if p is not self._pokemon2)
            if not p1_has_more and not p2_has_more:
                self._state = BattleState.DRAW
                self._winner = None
                self._loser = None
                self._events.append("The battle ended in a draw!")
        elif p2_fainted:
            p2_has_more = any(not p.is_fainted for p in self._opponent_team if p is not self._pokemon2)
            if not p2_has_more:
                self._state = BattleState.VICTORY
                self._winner = self._pokemon1
                self._loser = self._pokemon2
                self._events.append(f"{self._pokemon1.display_name} won the battle!")
                if self._wild_agent is not None:
                    from src.ai.wild_encounter_service import AutonomousWildService
                    AutonomousWildService.record_encounter_concluded(self._wild_agent, "fainted", self._player)
                if self._player_agent is not None and self._player is not None:
                    from src.ai.scheduler import AutonomousWorldScheduler
                    AutonomousWorldScheduler.on_battle_concluded(self._player, self, self._ai_state, "victory")
                if self.is_trainer_battle and self._opponent_trainer is not None:
                    if hasattr(self._opponent_trainer, "record_defeat"):
                        self._opponent_trainer.record_defeat()
                    if getattr(self._opponent_trainer, "dialogue_defeat", None):
                        self._events.append(f"{self._opponent_trainer.name}: \"{self._opponent_trainer.dialogue_defeat}\"")
        elif p1_fainted:
            p1_has_more = any(not p.is_fainted for p in self._player_team if p is not self._pokemon1)
            if not p1_has_more:
                self._state = BattleState.DEFEAT
                self._winner = self._pokemon2
                self._loser = self._pokemon1
                self._events.append(f"{self._pokemon2.display_name} won the battle!")
                if self._wild_agent is not None:
                    from src.ai.wild_encounter_service import AutonomousWildService
                    AutonomousWildService.record_encounter_concluded(self._wild_agent, "victory", self._player)
                if self._player_agent is not None and self._player is not None:
                    from src.ai.scheduler import AutonomousWorldScheduler
                    AutonomousWorldScheduler.on_battle_concluded(self._player, self, self._ai_state, "defeat")
                if self.is_trainer_battle and self._opponent_trainer is not None:
                    if getattr(self._opponent_trainer, "dialogue_victory", None):
                        self._events.append(f"{self._opponent_trainer.name}: \"{self._opponent_trainer.dialogue_victory}\"")

    def _choose_opponent_attack(self, pokemon: Pokemon) -> Optional[Attack]:
        """
        Chooses an attack for the opposing Pokemon using the injected RNG.
        Returns the chosen Attack, or None if the Pokemon has no known attacks.
        """
        if not pokemon.attacks:
            return None
        return self._rng.choice(pokemon.attacks)

    def _handle_opponent_trainer_ko(self) -> None:
        """
        In trainer battles, automatically switches in the opponent's next conscious Pokemon
        if the active opponent Pokemon fainted and the battle has not terminated.
        """
        if self._pokemon2.is_fainted and self.is_trainer_battle and not self._state.is_terminal():
            opp_conscious = [p for p in self._opponent_team if not p.is_fainted]
            if opp_conscious:
                next_opp = opp_conscious[0]
                self._pokemon2 = next_opp
                if self._opponent_trainer is not None:
                    self._opponent_trainer.set_active_pokemon(next_opp)
                self._events.append(
                    f"Opponent {self._opponent_trainer.name if self._opponent_trainer else 'Trainer'} "
                    f"sent out {next_opp.display_name}!"
                )

    def switch_opponent_pokemon(self, target_pokemon: Pokemon) -> bool:
        """
        Switches the active opponent Pokemon to target_pokemon.
        Used by trainer AI for proactive mid-battle switches.
        """
        if self._state.is_terminal() or self._state == BattleState.NOT_STARTED:
            return False
        if not isinstance(target_pokemon, Pokemon):
            return False
        if (
            target_pokemon not in self._opponent_team
            or target_pokemon.is_fainted
            or target_pokemon is self._pokemon2
            or target_pokemon.unique_id == self._pokemon2.unique_id
        ):
            return False

        old_mon = self._pokemon2
        self._pokemon2 = target_pokemon
        if self._opponent_trainer is not None:
            if hasattr(self._opponent_trainer, "set_active_pokemon"):
                self._opponent_trainer.set_active_pokemon(target_pokemon)
            if hasattr(self._opponent_trainer, "last_switch_turn"):
                self._opponent_trainer.last_switch_turn = self._current_turn

        trainer_name = getattr(self._opponent_trainer, "name", "Opponent Trainer")
        self._events.append(
            f"[Turn {self._current_turn}] {trainer_name} withdrew {old_mon.display_name} and sent out {target_pokemon.display_name}!"
        )
        return True

    def can_switch_pokemon(self, target_pokemon: Pokemon) -> tuple[bool, str]:
        """
        Validates whether the player can switch to target_pokemon.
        Returns: (can_switch, reason)
        """
        if self._state.is_terminal():
            return False, f"Cannot switch: battle has already concluded with result '{self._state.value}'."
        if self._state == BattleState.NOT_STARTED:
            return False, "Cannot switch: battle has not started yet."

        if not isinstance(target_pokemon, Pokemon):
            return False, f"target_pokemon must be a Pokemon instance, got {type(target_pokemon).__name__}."

        if target_pokemon not in self._player_team:
            return False, f"Pokemon '{target_pokemon.display_name}' is not on the player's battle team."

        if target_pokemon is self._pokemon1 or target_pokemon.unique_id == self._pokemon1.unique_id:
            return False, f"Pokemon '{target_pokemon.display_name}' is already the active Pokemon."

        if target_pokemon.is_fainted:
            return False, f"Cannot switch to fainted Pokemon '{target_pokemon.display_name}'."

        if self._player is not None and not self._player.is_pokemon_owned(target_pokemon):
            return False, f"Pokemon '{target_pokemon.display_name}' does not belong to the player."

        return True, "Switch is valid."

    def switch_pokemon(self, target_pokemon: Pokemon) -> BattleActionResult:
        """
        Executes a switch to target_pokemon.
        The switch takes priority. Then, if the opponent is conscious,
        the opposing Pokemon executes its chosen attack against the incoming Pokemon.
        """
        return self.take_action(BattleAction(action_type=BattleActionType.SWITCH, target_pokemon=target_pokemon))

    def flee(self) -> BattleActionResult:
        """
        Attempts to flee from the battle.
        Permitted only in wild battles. Concludes the battle with BattleState.ESCAPED.
        """
        return self.take_action(BattleAction(action_type=BattleActionType.FLEE))

    def escape(self) -> BattleActionResult:
        """Alias for flee()."""
        return self.flee()

    def execute_player_attack(self, attack: Attack) -> BattleActionResult:
        """Convenience method to execute an attack action for the active player Pokemon."""
        return self.take_action(BattleAction(action_type=BattleActionType.ATTACK, attack=attack))

    def inspect(self) -> BattleActionResult:
        """Convenience method to execute an inspect action against the opponent."""
        return self.take_action(BattleAction(action_type=BattleActionType.INSPECT))

    def take_action(self, action: BattleAction) -> BattleActionResult:
        """
        Executes a validated turn action (ATTACK, SWITCH, FLEE, CAPTURE, INSPECT) for the player.
        Returns a structured BattleActionResult indicating acceptance, outcome, and state.
        Safely rejects actions after the battle has concluded.
        """
        if not isinstance(action, BattleAction):
            raise TypeError(f"action must be a BattleAction instance, got {type(action).__name__}.")

        # 1. Reject if battle is already concluded (terminal)
        if self._state.is_terminal():
            return BattleActionResult(
                accepted=False,
                reason=f"Cannot execute action: battle has already concluded with result '{self._state.value}'.",
                action_type=action.action_type,
                battle_state=self._state,
                terminal=True,
                error_type="BATTLE_ALREADY_TERMINAL",
            )

        # 2. Reject if battle has not started yet
        if self._state == BattleState.NOT_STARTED:
            return BattleActionResult(
                accepted=False,
                reason="Cannot execute action: battle has not started yet. Call start() first.",
                action_type=action.action_type,
                battle_state=self._state,
                terminal=False,
                error_type="BATTLE_NOT_STARTED",
            )

        # --- Case A: ATTACK ---
        if action.action_type == BattleActionType.ATTACK:
            if action.attack is None:
                return BattleActionResult(
                    accepted=False,
                    reason="No attack specified for ATTACK action.",
                    action_type=action.action_type,
                    battle_state=self._state,
                    error_type="MISSING_ATTACK",
                )
            if self._pokemon1.is_fainted:
                return BattleActionResult(
                    accepted=False,
                    reason=f"Active Pokemon '{self._pokemon1.display_name}' has fainted and cannot attack. Switch Pokemon first.",
                    action_type=action.action_type,
                    battle_state=self._state,
                    error_type="POKEMON_FAINTED",
                )
            if action.attack not in self._pokemon1.attacks:
                return BattleActionResult(
                    accepted=False,
                    reason=f"Active Pokemon '{self._pokemon1.display_name}' does not know '{action.attack.name}'.",
                    action_type=action.action_type,
                    battle_state=self._state,
                    error_type="ATTACK_NOT_KNOWN",
                )

            # Record player attack intent against wild Pokémon
            if self.is_wild_battle and self._player is not None and hasattr(self._player, "record_wild_action"):
                species_name = self._pokemon2.species.name if self._pokemon2 else None
                self._player.record_wild_action("attack", is_aggressive=True, species_name=species_name)

            # Companion tactical disposition and character dialogue
            effective_player_attack = action.attack
            if self._player_agent is not None and self._player is not None:
                from src.ai.companion_service import CompanionService
                disposition = CompanionService.evaluate_battle_command(
                    agent=self._player_agent,
                    pokemon=self._pokemon1,
                    player=self._player,
                    chosen_attack=action.attack,
                    opponent=self._pokemon2,
                    battle=self,
                    provider=self._ai_provider,
                )
                if disposition.dialogue:
                    self._events.append(f"{self._pokemon1.display_name}: \"{disposition.dialogue}\"")
                if not disposition.is_obedient and disposition.chosen_attack is not None:
                    effective_player_attack = disposition.chosen_attack

            # Opponent selects an action
            if self._use_wild_ai and self.is_wild_battle and not self._pokemon2.is_fainted:
                from src.models.wild_ai import WildActionType
                wild_decision = self.decide_wild_action()

                if wild_decision.action_type == WildActionType.FLEE:
                    player_record = self._execute_action(
                        attacker=self._pokemon1,
                        attack=effective_player_attack,
                        defender=self._pokemon2,
                    )
                    executed_actions = [player_record]
                    if self._pokemon2.is_fainted:
                        self._events.append(f"{self._pokemon2.display_name} fainted!")
                        self._update_terminal_state()
                    else:
                        self._events.append(
                            f"[Turn {self._current_turn}] The wild {self._pokemon2.display_name} panicked and fled from battle! ({wild_decision.reason})"
                        )
                        self._state = BattleState.ESCAPED
                        if self._wild_agent is not None:
                            from src.ai.wild_encounter_service import AutonomousWildService
                            AutonomousWildService.record_encounter_concluded(self._wild_agent, "escaped", self._player)

                    turn_res = TurnResult(
                        turn_number=self._current_turn,
                        actions=tuple(executed_actions),
                        battle_state=self._state,
                        winner=self._winner,
                        loser=self._loser,
                    )
                    self._history.append(turn_res)
                    if not self._state.is_terminal():
                        self._current_turn += 1
                    return BattleActionResult(
                        accepted=True,
                        reason=wild_decision.reason if self._state == BattleState.ESCAPED else "Turn resolved successfully.",
                        action_type=action.action_type,
                        battle_state=self._state,
                        turn_result=turn_res,
                        escaped=(self._state == BattleState.ESCAPED),
                        terminal=self._state.is_terminal(),
                    )

                elif wild_decision.action_type == WildActionType.INSPECT:
                    # Wild Pokemon pauses to inspect without attacking
                    player_record = self._execute_action(
                        attacker=self._pokemon1,
                        attack=effective_player_attack,
                        defender=self._pokemon2,
                    )
                    executed_actions = [player_record]
                    if self._pokemon2.is_fainted:
                        self._events.append(f"{self._pokemon2.display_name} fainted!")
                        self._update_terminal_state()
                    else:
                        self._events.append(
                            f"[Turn {self._current_turn}] The wild {self._pokemon2.display_name} paused to inspect you! ({wild_decision.reason})"
                        )
                        if self._wild_agent is not None:
                            from src.ai.wild_encounter_service import AutonomousWildService
                            AutonomousWildService.record_observation(
                                agent=self._wild_agent,
                                target_name=self._pokemon1.display_name,
                                details=wild_decision.reason,
                                player=self._player,
                            )

                    # Status effects
                    if not self._state.is_terminal():
                        for mon in (self._pokemon1, self._pokemon2):
                            if not mon.is_fainted:
                                eot_res = self._status_manager.process_end_of_turn(mon)
                                for eff_rec in eot_res.effects_processed:
                                    if eff_rec.damage > 0:
                                        self._events.append(f"[Turn {self._current_turn}] {eff_rec.message}")
                                for exp_type in eot_res.expired_effects:
                                    self._events.append(f"[Turn {self._current_turn}] {mon.display_name}'s {exp_type.display_name} wore off!")
                                if mon.is_fainted:
                                    self._events.append(f"{mon.display_name} fainted!")
                        if self._pokemon1.is_fainted or self._pokemon2.is_fainted:
                            self._update_terminal_state()

                    turn_res = TurnResult(
                        turn_number=self._current_turn,
                        actions=tuple(executed_actions),
                        battle_state=self._state,
                        winner=self._winner,
                        loser=self._loser,
                    )
                    self._history.append(turn_res)
                    if not self._state.is_terminal():
                        self._current_turn += 1
                    return BattleActionResult(
                        accepted=True,
                        reason="Turn resolved successfully.",
                        action_type=action.action_type,
                        battle_state=self._state,
                        turn_result=turn_res,
                        terminal=self._state.is_terminal(),
                    )

                else:
                    opp_attack = wild_decision.chosen_attack or self._choose_opponent_attack(self._pokemon2)
                    if opp_attack is None:
                        opp_attack = Attack(name="Struggle", type=self._pokemon2.species.types[0], power=35, accuracy=100)
                    turn_res = self.resolve_turn(attack1=effective_player_attack, attack2=opp_attack)
                    return BattleActionResult(
                        accepted=True,
                        reason="Turn resolved successfully.",
                        action_type=action.action_type,
                        battle_state=self._state,
                        turn_result=turn_res,
                        terminal=self._state.is_terminal(),
                    )

            # Opponent selects an action in trainer battles or wild battles
            if self.is_trainer_battle and self._opponent_trainer is not None:
                decision = self.trainer_ai.decide_action(
                    battle=self,
                    trainer=self._opponent_trainer,
                    active_pokemon=self._pokemon2,
                    opponent_pokemon=self._pokemon1,
                    rng=self._rng,
                )
                from src.models.trainer_ai import TrainerActionType
                if decision.action_type == TrainerActionType.SWITCH and decision.target_pokemon is not None:
                    # Opponent switches proactively!
                    self.switch_opponent_pokemon(decision.target_pokemon)
                    executed_actions: list[BattleActionRecord] = []
                    player_record = self._execute_action(
                        attacker=self._pokemon1,
                        attack=effective_player_attack,
                        defender=self._pokemon2,
                    )
                    executed_actions.append(player_record)
                    if self._pokemon2.is_fainted:
                        self._events.append(f"{self._pokemon2.display_name} fainted!")
                        self._update_terminal_state()
                        self._handle_opponent_trainer_ko()

                    # End-of-turn status phase
                    if not self._state.is_terminal():
                        for mon in (self._pokemon1, self._pokemon2):
                            if not mon.is_fainted:
                                eot_res = self._status_manager.process_end_of_turn(mon)
                                for eff_rec in eot_res.effects_processed:
                                    if eff_rec.damage > 0:
                                        self._events.append(f"[Turn {self._current_turn}] {eff_rec.message}")
                                for exp_type in eot_res.expired_effects:
                                    self._events.append(f"[Turn {self._current_turn}] {mon.display_name}'s {exp_type.display_name} wore off!")
                                if mon.is_fainted:
                                    self._events.append(f"{mon.display_name} fainted!")

                        if self._pokemon1.is_fainted or self._pokemon2.is_fainted:
                            self._update_terminal_state()
                            self._handle_opponent_trainer_ko()

                        if not self._state.is_terminal():
                            self._current_turn += 1

                    turn_res = TurnResult(
                        turn_number=self._current_turn if self._state.is_terminal() else self._current_turn - 1,
                        actions=tuple(executed_actions),
                        battle_state=self._state,
                        winner=self._winner,
                        loser=self._loser,
                    )
                    self._history.append(turn_res)

                    return BattleActionResult(
                        accepted=True,
                        reason="Turn resolved successfully.",
                        action_type=action.action_type,
                        battle_state=self._state,
                        turn_result=turn_res,
                        switched_pokemon=decision.target_pokemon,
                        terminal=self._state.is_terminal(),
                    )
                else:
                    opp_attack = decision.chosen_attack or self._choose_opponent_attack(self._pokemon2)
            else:
                opp_attack = self._choose_opponent_attack(self._pokemon2)

            if opp_attack is None:
                opp_attack = Attack(name="Struggle", type=self._pokemon2.species.types[0], power=35, accuracy=100)

            turn_res = self.resolve_turn(attack1=effective_player_attack, attack2=opp_attack)

            # Opponent KO handling in trainer battles (switch in next opponent pokemon)
            self._handle_opponent_trainer_ko()

            return BattleActionResult(
                accepted=True,
                reason="Turn resolved successfully.",
                action_type=action.action_type,
                battle_state=self._state,
                turn_result=turn_res,
                terminal=self._state.is_terminal(),
            )

        # --- Case B: SWITCH ---
        elif action.action_type == BattleActionType.SWITCH:
            if action.target_pokemon is None:
                return BattleActionResult(
                    accepted=False,
                    reason="No target Pokemon specified for SWITCH action.",
                    action_type=action.action_type,
                    battle_state=self._state,
                    error_type="MISSING_SWITCH_TARGET",
                )
            valid, err_msg = self.can_switch_pokemon(action.target_pokemon)
            if not valid:
                return BattleActionResult(
                    accepted=False,
                    reason=err_msg,
                    action_type=action.action_type,
                    battle_state=self._state,
                    error_type="INVALID_SWITCH",
                )

            old_mon = self._pokemon1
            new_mon = action.target_pokemon
            self._pokemon1 = new_mon
            if self._player is not None:
                self._player.set_active_pokemon(new_mon)
            self._events.append(
                f"[Turn {self._current_turn}] Player withdrew {old_mon.display_name} and sent out {new_mon.display_name}!"
            )

            # Opposing Pokemon acts against incoming Pokemon
            executed_actions: list[BattleActionRecord] = []
            if not self._pokemon2.is_fainted:
                if self._use_wild_ai and self.is_wild_battle:
                    from src.models.wild_ai import WildActionType
                    wild_decision = self.decide_wild_action()
                    if wild_decision.action_type == WildActionType.FLEE:
                        self._events.append(
                            f"[Turn {self._current_turn}] The wild {self._pokemon2.display_name} fled upon seeing {new_mon.display_name}! ({wild_decision.reason})"
                        )
                        self._state = BattleState.ESCAPED
                    elif wild_decision.action_type == WildActionType.INSPECT:
                        self._events.append(
                            f"[Turn {self._current_turn}] The wild {self._pokemon2.display_name} sized up incoming {new_mon.display_name}! ({wild_decision.reason})"
                        )
                    else:
                        opp_attack = wild_decision.chosen_attack or self._choose_opponent_attack(self._pokemon2)
                        if opp_attack is not None:
                            opp_record = self._execute_action(
                                attacker=self._pokemon2,
                                attack=opp_attack,
                                defender=self._pokemon1,
                            )
                            executed_actions.append(opp_record)
                            if self._pokemon1.is_fainted:
                                self._events.append(f"{self._pokemon1.display_name} fainted!")
                                self._update_terminal_state()
                else:
                    if self.is_trainer_battle and self._opponent_trainer is not None:
                        decision = self.trainer_ai.decide_action(
                            battle=self,
                            trainer=self._opponent_trainer,
                            active_pokemon=self._pokemon2,
                            opponent_pokemon=self._pokemon1,
                            rng=self._rng,
                        )
                        opp_attack = decision.chosen_attack or self._choose_opponent_attack(self._pokemon2)
                    else:
                        opp_attack = self._choose_opponent_attack(self._pokemon2)
                    if opp_attack is not None:
                        opp_record = self._execute_action(
                            attacker=self._pokemon2,
                            attack=opp_attack,
                            defender=self._pokemon1,
                        )
                        executed_actions.append(opp_record)
                        if self._pokemon1.is_fainted:
                            self._events.append(f"{self._pokemon1.display_name} fainted!")
                            self._update_terminal_state()

            # End of turn status phase
            if not self._state.is_terminal():
                for mon in (self._pokemon1, self._pokemon2):
                    if not mon.is_fainted:
                        eot_res = self._status_manager.process_end_of_turn(mon)
                        for eff_rec in eot_res.effects_processed:
                            if eff_rec.damage > 0:
                                self._events.append(f"[Turn {self._current_turn}] {eff_rec.message}")
                        for exp_type in eot_res.expired_effects:
                            self._events.append(f"[Turn {self._current_turn}] {mon.display_name}'s {exp_type.display_name} wore off!")
                        if mon.is_fainted:
                            self._events.append(f"{mon.display_name} fainted!")

                if self._pokemon1.is_fainted or self._pokemon2.is_fainted:
                    self._update_terminal_state()
                    self._handle_opponent_trainer_ko()
                if not self._state.is_terminal():
                    self._current_turn += 1

            turn_res = TurnResult(
                turn_number=self._current_turn if self._state.is_terminal() else self._current_turn - 1,
                actions=tuple(executed_actions),
                battle_state=self._state,
                winner=self._winner,
                loser=self._loser,
            )
            self._history.append(turn_res)

            return BattleActionResult(
                accepted=True,
                reason=f"Switched active Pokemon to {new_mon.display_name}.",
                action_type=action.action_type,
                battle_state=self._state,
                turn_result=turn_res,
                switched_pokemon=new_mon,
                escaped=(self._state == BattleState.ESCAPED),
                terminal=self._state.is_terminal(),
            )

        # --- Case C: FLEE ---
        elif action.action_type == BattleActionType.FLEE:
            if self.is_trainer_battle:
                return BattleActionResult(
                    accepted=False,
                    reason="Cannot flee from a trainer battle!",
                    action_type=action.action_type,
                    battle_state=self._state,
                    error_type="CANNOT_FLEE_TRAINER",
                )
            if self._player is not None and hasattr(self._player, "record_wild_action"):
                self._player.record_wild_action("flee", is_peaceful=True, species_name=self._pokemon2.species.name)
            self._state = BattleState.ESCAPED
            self._events.append(f"[Turn {self._current_turn}] Player fled from the battle!")
            return BattleActionResult(
                accepted=True,
                reason="Successfully fled from battle.",
                action_type=action.action_type,
                battle_state=BattleState.ESCAPED,
                escaped=True,
                terminal=True,
            )

        # --- Case D: CAPTURE ---
        elif action.action_type == BattleActionType.CAPTURE:
            if self.is_trainer_battle:
                return BattleActionResult(
                    accepted=False,
                    reason="Cannot capture a trainer's Pokemon!",
                    action_type=action.action_type,
                    battle_state=self._state,
                    error_type="CANNOT_CAPTURE_TRAINER",
                )
            if self._pokemon2.is_fainted:
                return BattleActionResult(
                    accepted=False,
                    reason="Cannot capture a fainted Pokemon.",
                    action_type=action.action_type,
                    battle_state=self._state,
                    error_type="POKEMON_FAINTED",
                )
            return BattleActionResult(
                accepted=True,
                reason="Capture request accepted.",
                action_type=action.action_type,
                battle_state=self._state,
                terminal=False,
            )

        # --- Case E: INSPECT ---
        elif action.action_type == BattleActionType.INSPECT:
            if self._pokemon1.is_fainted:
                return BattleActionResult(
                    accepted=False,
                    reason=f"Active Pokemon '{self._pokemon1.display_name}' has fainted.",
                    action_type=action.action_type,
                    battle_state=self._state,
                    error_type="POKEMON_FAINTED",
                )

            self._events.append(
                f"[Turn {self._current_turn}] Trainer {self._player.name if self._player else 'Trainer'} "
                f"and {self._pokemon1.display_name} cautiously inspect wild {self._pokemon2.display_name} "
                f"(HP: {self._pokemon2.current_hp}/{self._pokemon2.max_hp}, Lv.{self._pokemon2.level})."
            )
            if self._player is not None and hasattr(self._player, "record_wild_action"):
                self._player.record_wild_action("inspect", is_peaceful=True, species_name=self._pokemon2.species.name)

            executed_actions: list[BattleActionRecord] = []
            if self._use_wild_ai and self.is_wild_battle and not self._pokemon2.is_fainted:
                from src.models.wild_ai import WildActionType
                wild_decision = self.decide_wild_action()

                if wild_decision.action_type == WildActionType.FLEE:
                    self._events.append(
                        f"[Turn {self._current_turn}] The wild {self._pokemon2.display_name} was startled and fled! ({wild_decision.reason})"
                    )
                    self._state = BattleState.ESCAPED
                    return BattleActionResult(
                        accepted=True,
                        reason=wild_decision.reason,
                        action_type=action.action_type,
                        battle_state=BattleState.ESCAPED,
                        escaped=True,
                        terminal=True,
                    )
                elif wild_decision.action_type == WildActionType.INSPECT:
                    self._events.append(
                        f"[Turn {self._current_turn}] The wild {self._pokemon2.display_name} inspects you back curiously. ({wild_decision.reason})"
                    )
                else:  # ATTACK
                    opp_attack = wild_decision.chosen_attack or self._choose_opponent_attack(self._pokemon2)
                    if opp_attack is not None:
                        opp_record = self._execute_action(
                            attacker=self._pokemon2,
                            attack=opp_attack,
                            defender=self._pokemon1,
                        )
                        executed_actions.append(opp_record)
                        if self._pokemon1.is_fainted:
                            self._events.append(f"{self._pokemon1.display_name} fainted!")
                            self._update_terminal_state()
            else:
                if not self._pokemon2.is_fainted:
                    opp_attack = self._choose_opponent_attack(self._pokemon2)
                    if opp_attack is not None:
                        opp_record = self._execute_action(
                            attacker=self._pokemon2,
                            attack=opp_attack,
                            defender=self._pokemon1,
                        )
                        executed_actions.append(opp_record)
                        if self._pokemon1.is_fainted:
                            self._events.append(f"{self._pokemon1.display_name} fainted!")
                            self._update_terminal_state()

            # End of turn status phase
            if not self._state.is_terminal():
                for mon in (self._pokemon1, self._pokemon2):
                    if not mon.is_fainted:
                        eot_res = self._status_manager.process_end_of_turn(mon)
                        for eff_rec in eot_res.effects_processed:
                            if eff_rec.damage > 0:
                                self._events.append(f"[Turn {self._current_turn}] {eff_rec.message}")
                        for exp_type in eot_res.expired_effects:
                            self._events.append(f"[Turn {self._current_turn}] {mon.display_name}'s {exp_type.display_name} wore off!")
                        if mon.is_fainted:
                            self._events.append(f"{mon.display_name} fainted!")

                if self._pokemon1.is_fainted or self._pokemon2.is_fainted:
                    self._update_terminal_state()
                if not self._state.is_terminal():
                    self._current_turn += 1

            turn_res = TurnResult(
                turn_number=self._current_turn if self._state.is_terminal() else self._current_turn - 1,
                actions=tuple(executed_actions),
                battle_state=self._state,
                winner=self._winner,
                loser=self._loser,
            )
            self._history.append(turn_res)

            return BattleActionResult(
                accepted=True,
                reason="Inspected wild Pokemon.",
                action_type=action.action_type,
                battle_state=self._state,
                turn_result=turn_res,
                terminal=self._state.is_terminal(),
            )

        return BattleActionResult(
            accepted=False,
            reason=f"Unsupported action type '{action.action_type}'.",
            action_type=action.action_type,
            battle_state=self._state,
            error_type="UNSUPPORTED_ACTION",
        )

