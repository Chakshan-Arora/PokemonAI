"""
Battle Manager coordinating player battle sessions, wild encounters,
turn resolution, captures, rewards, quest events, and spawn area cleanup.
"""
import random
import uuid
from typing import Optional, Union, Any, Sequence

from src.models.pokemon import Pokemon
from src.models.player import Player
from src.models.trainer import Trainer
from src.models.attack import Attack
from src.models.battle_state import BattleState
from src.models.battle import (
    Battle,
    BattleAction,
    BattleActionType,
    BattleActionResult,
    TurnResult,
#     BattleTalkCommand,
)
from src.models.encounter_manager import EncounterManager, WildEncounter, EncounterResult
from src.models.spawn_manager import SpawnManager
from src.models.capture_manager import CaptureManager, CaptureResult
from src.models.experience_manager import ExperienceManager, BattleRewardResult
from src.models.quest_manager import QuestManager
from src.models.quest import QuestEventType
from src.models.bond_manager import BondManager, BondChangeResult


class BattleManager:
    """
    High-level manager for Pokemon battles in Syntax Error 2026.
    Coordinates active battle sessions per player, connects battles to wild encounters
    and trainer matches, dispatches player actions, and authoritatively resolves
    victories, defeats, rewards, quest events, and spawn population cleanup.
    """

    def __init__(
        self,
        spawn_manager: Optional[SpawnManager] = None,
        encounter_manager: Optional[EncounterManager] = None,
        capture_manager: Optional[CaptureManager] = None,
        experience_manager: Optional[ExperienceManager] = None,
        quest_manager: Optional[QuestManager] = None,
        bond_manager: Optional[BondManager] = None,
        rng: Optional[random.Random] = None,
        seed: Optional[int] = None,
        ai_state: Optional[Any] = None,
        ai_provider: Optional[Any] = None,
    ) -> None:
        self._spawn_manager: Optional[SpawnManager] = spawn_manager
        self._encounter_manager: Optional[EncounterManager] = encounter_manager
        self._capture_manager: Optional[CaptureManager] = capture_manager
        self._experience_manager: Optional[ExperienceManager] = experience_manager
        self._quest_manager: Optional[QuestManager] = quest_manager
        self._bond_manager: Optional[BondManager] = bond_manager
        self._ai_state: Optional[Any] = ai_state
        self._ai_provider: Optional[Any] = ai_provider

        if rng is not None:
            self._rng = rng
        elif seed is not None:
            self._rng = random.Random(seed)
        else:
            self._rng = random.Random()

        # Active battles mapped by player unique_id
        self._active_battles: dict[str, Battle] = {}

    # --- Properties ---

    @property
    def spawn_manager(self) -> Optional[SpawnManager]:
        return self._spawn_manager

    @spawn_manager.setter
    def spawn_manager(self, sm: Optional[SpawnManager]) -> None:
        self._spawn_manager = sm

    @property
    def encounter_manager(self) -> Optional[EncounterManager]:
        return self._encounter_manager

    @encounter_manager.setter
    def encounter_manager(self, em: Optional[EncounterManager]) -> None:
        self._encounter_manager = em

    @property
    def capture_manager(self) -> Optional[CaptureManager]:
        return self._capture_manager

    @capture_manager.setter
    def capture_manager(self, cm: Optional[CaptureManager]) -> None:
        self._capture_manager = cm

    @property
    def experience_manager(self) -> Optional[ExperienceManager]:
        return self._experience_manager

    @experience_manager.setter
    def experience_manager(self, em: Optional[ExperienceManager]) -> None:
        self._experience_manager = em

    @property
    def quest_manager(self) -> Optional[QuestManager]:
        return self._quest_manager

    @quest_manager.setter
    def quest_manager(self, qm: Optional[QuestManager]) -> None:
        self._quest_manager = qm

    @property
    def ai_state(self) -> Optional[Any]:
        return self._ai_state

    @ai_state.setter
    def ai_state(self, val: Optional[Any]) -> None:
        self._ai_state = val

    @property
    def ai_provider(self) -> Optional[Any]:
        return self._ai_provider

    @ai_provider.setter
    def ai_provider(self, val: Optional[Any]) -> None:
        self._ai_provider = val

    @property
    def bond_manager(self) -> Optional[BondManager]:
        return self._bond_manager

    @bond_manager.setter
    def bond_manager(self, bm: Optional[BondManager]) -> None:
        self._bond_manager = bm

    @property
    def active_battles(self) -> dict[str, Battle]:
        """Dictionary of currently active battle sessions."""
        return dict(self._active_battles)

    # --- Session Queries ---

    def get_active_battle(self, player: Union[Player, str]) -> Optional[Battle]:
        """
        Retrieves the active battle session for a player, if any.
        Cleans up and returns None if the battle has already concluded.
        """
        p_id = player.unique_id if isinstance(player, Player) else str(player)
        battle = self._active_battles.get(p_id)
        if battle is not None:
            if battle.state.is_terminal():
                self._active_battles.pop(p_id, None)
                return None
            return battle
        return None

    def has_active_battle(self, player: Union[Player, str]) -> bool:
        """Returns True if the player currently has an active, non-terminal battle."""
        return self.get_active_battle(player) is not None

    # --- Battle Creation ---

    def start_battle(
        self,
        player: Player,
        opponent: Union[Pokemon, Player, Trainer],
        encounter: Optional[Union[WildEncounter, EncounterResult]] = None,
        rng: Optional[random.Random] = None,
        seed: Optional[int] = None,
        use_random_damage: bool = True,
        region_id: Optional[str] = None,
        use_wild_ai: Optional[bool] = None,
        wild_agent: Optional[Any] = None,
        ai_provider: Optional[Any] = None,
        ai_state: Optional[Any] = None,
        trainer_ai: Optional[Any] = None,
    ) -> Battle:
        """
        Initializes and starts a new battle session for the player.
        Supports wild battles (opponent is Pokemon) and trainer battles (opponent is Player).
        Enforces singleton rule: a player cannot have multiple concurrent battles.
        """
        if not isinstance(player, Player):
            raise TypeError(f"player must be a Player instance, got {type(player).__name__}.")

        # 1. Enforce single active battle per player
        if self.has_active_battle(player):
            existing = self.get_active_battle(player)
            raise RuntimeError(
                f"Player '{player.name}' (ID: {player.unique_id}) already has an active battle "
                f"({existing.battle_id if existing else 'unknown'})."
            )

        # 2. Validate player team has conscious Pokemon
        if player.active_pokemon is None or player.active_pokemon.is_fainted:
            conscious_team = [p for p in player.team if not p.is_fainted]
            if not conscious_team:
                raise ValueError(f"Player '{player.name}' has no conscious Pokemon to battle with.")
            player.set_active_pokemon(conscious_team[0])

        eff_rng = rng if rng is not None else (random.Random(seed) if seed is not None else self._rng)

        # 3. Create battle according to opponent type
        if isinstance(opponent, Pokemon):
            # Wild Pokemon battle
            if opponent.is_fainted:
                raise ValueError(f"Cannot start battle: wild Pokemon '{opponent.display_name}' has fainted.")

            eff_encounter: Optional[WildEncounter] = None
            if encounter is not None:
                if isinstance(encounter, EncounterResult):
                    eff_encounter = encounter.start_encounter(player)
                elif isinstance(encounter, WildEncounter):
                    eff_encounter = encounter
                else:
                    raise TypeError(f"encounter must be WildEncounter or EncounterResult, got {type(encounter).__name__}.")

                if not eff_encounter.is_active or eff_encounter.is_resolved:
                    raise RuntimeError(f"Cannot start battle: encounter is already resolved ({eff_encounter.resolution_reason}).")

                if eff_encounter.pokemon is not opponent and eff_encounter.pokemon.unique_id != opponent.unique_id:
                    raise ValueError("Encounter Pokemon does not match opponent Pokemon.")

            # Resolve authoritative battle region
            eff_region_id: Optional[str] = region_id
            if eff_region_id is None and eff_encounter is not None:
                eff_region_id = eff_encounter.region_id

            eff_ai_state = ai_state if ai_state is not None else self._ai_state
            eff_ai_provider = ai_provider if ai_provider is not None else self._ai_provider
            eff_wild_agent = wild_agent
            if eff_wild_agent is None and eff_ai_state is not None:
                from src.ai.wild_encounter_service import AutonomousWildService
                eff_wild_agent = AutonomousWildService.get_or_create_agent(opponent, eff_ai_state)

            eff_player_agent = None
            if eff_ai_state is not None and player.active_pokemon is not None:
                from src.ai.companion_service import CompanionService
                eff_player_agent = CompanionService.get_or_create_companion_agent(player.active_pokemon, eff_ai_state, player)

            battle = Battle(
                pokemon1=player.active_pokemon,
                pokemon2=opponent,
                rng=eff_rng,
                use_random_damage=use_random_damage,
                player=player,
                encounter=eff_encounter,
                player_team=player.team,
                opponent_team=[opponent],
                region_id=eff_region_id,
                use_wild_ai=use_wild_ai,
                wild_agent=eff_wild_agent,
                player_agent=eff_player_agent,
                ai_provider=eff_ai_provider,
                ai_state=eff_ai_state,
            )

        elif isinstance(opponent, (Player, Trainer)):
            # Trainer battle
            if opponent is player or getattr(opponent, "unique_id", None) == player.unique_id:
                raise ValueError("A player cannot battle themselves.")

            # If Trainer has no team yet, generate team dynamically!
            if isinstance(opponent, Trainer) and not opponent.has_team:
                from src.models.trainer_team_generator import TrainerTeamGenerator
                TrainerTeamGenerator.generate_team(
                    trainer=opponent,
                    player=player,
                    region_id=region_id,
                    rng=eff_rng,
                )

            if opponent.active_pokemon is None or opponent.active_pokemon.is_fainted:
                opp_conscious = [p for p in opponent.team if not p.is_fainted]
                if not opp_conscious:
                    raise ValueError(f"Opponent trainer '{opponent.name}' has no conscious Pokemon to battle with.")
                opponent.set_active_pokemon(opp_conscious[0])

            eff_ai_state = ai_state if ai_state is not None else self._ai_state
            eff_ai_provider = ai_provider if ai_provider is not None else self._ai_provider
            eff_player_agent = None
            if eff_ai_state is not None and player.active_pokemon is not None:
                from src.ai.companion_service import CompanionService
                eff_player_agent = CompanionService.get_or_create_companion_agent(player.active_pokemon, eff_ai_state, player)

            battle = Battle(
                pokemon1=player.active_pokemon,
                pokemon2=opponent.active_pokemon,
                rng=eff_rng,
                use_random_damage=use_random_damage,
                player=player,
                opponent_trainer=opponent,
                player_team=player.team,
                opponent_team=opponent.team,
                region_id=region_id,
                player_agent=eff_player_agent,
                ai_provider=eff_ai_provider,
                ai_state=eff_ai_state,
                trainer_ai=trainer_ai,
            )

        else:
            raise TypeError(f"opponent must be a Pokemon, Player, or Trainer instance, got {type(opponent).__name__}.")

        # 4. Start the battle and record session
        battle.start()
        self._active_battles[player.unique_id] = battle

        # Dispatch wild encounter quest event
        if self._quest_manager is not None and isinstance(opponent, Pokemon):
            habitat_id = None
            if eff_encounter is not None and eff_encounter.area is not None:
                habitat_id = getattr(eff_encounter.area, "habitat_id", None)
            enc_id = eff_encounter.encounter_id if eff_encounter is not None else battle.battle_id
            enc_evt_id = f"quest_evt_encounter_{enc_id}_{opponent.unique_id}"
            self._quest_manager.record_encounter(
                player=player,
                species_name=opponent.species.name,
                habitat_id=habitat_id,
                region_id=battle.region_id,
                count=1,
                event_id=enc_evt_id,
            )

        return battle

    def start_wild_battle(
        self,
        player: Player,
        encounter: Union[WildEncounter, EncounterResult],
        rng: Optional[random.Random] = None,
        seed: Optional[int] = None,
        use_random_damage: bool = True,
        region_id: Optional[str] = None,
        use_wild_ai: Optional[bool] = None,
        wild_agent: Optional[Any] = None,
        ai_provider: Optional[Any] = None,
        ai_state: Optional[Any] = None,
    ) -> Battle:
        """Convenience method initiating a wild battle directly from an encounter session."""
        if isinstance(encounter, EncounterResult):
            enc_session = encounter.start_encounter(player)
        elif isinstance(encounter, WildEncounter):
            enc_session = encounter
        else:
            raise TypeError(f"encounter must be WildEncounter or EncounterResult, got {type(encounter).__name__}.")

        return self.start_battle(
            player=player,
            opponent=enc_session.pokemon,
            encounter=enc_session,
            rng=rng,
            seed=seed,
            use_random_damage=use_random_damage,
            region_id=region_id,
            use_wild_ai=use_wild_ai,
            wild_agent=wild_agent,
            ai_provider=ai_provider,
            ai_state=ai_state,
        )

    def start_trainer_battle(
        self,
        player: Player,
        opponent_trainer: Union[Player, Trainer],
        rng: Optional[random.Random] = None,
        seed: Optional[int] = None,
        use_random_damage: bool = True,
        region_id: Optional[str] = None,
        trainer_ai: Optional[Any] = None,
        ai_provider: Optional[Any] = None,
        ai_state: Optional[Any] = None,
    ) -> Battle:
        """Convenience method initiating a trainer battle against an opponent Trainer or Player."""
        return self.start_battle(
            player=player,
            opponent=opponent_trainer,
            rng=rng,
            seed=seed,
            use_random_damage=use_random_damage,
            region_id=region_id,
            trainer_ai=trainer_ai,
            ai_provider=ai_provider,
            ai_state=ai_state,
        )

    # --- Turn Actions ---

    def execute_action(self, player: Player, action: BattleAction) -> BattleActionResult:
        """
        Executes a turn action for the player's active battle.
        If the battle finishes, authoritatively concludes the battle and distributes rewards.
        """
        if not isinstance(player, Player):
            raise TypeError(f"player must be a Player instance, got {type(player).__name__}.")

        battle = self.get_active_battle(player)
        if battle is None:
            return BattleActionResult(
                accepted=False,
                reason=f"Player '{player.name}' has no active battle.",
                action_type=action.action_type,
                battle_state=BattleState.NOT_STARTED,
                error_type="NO_ACTIVE_BATTLE",
            )

        if action.action_type == BattleActionType.CAPTURE:
            return self.attempt_capture(player)

        res = battle.take_action(action)
        if res.accepted and battle.state.is_terminal():
            self._conclude_battle(battle, player)

        return res

    def attack(self, player: Player, attack: Attack) -> BattleActionResult:
        """Convenience method for player executing an attack."""
        return self.execute_action(player, BattleAction(action_type=BattleActionType.ATTACK, attack=attack))

    def switch(self, player: Player, target_pokemon: Pokemon) -> BattleActionResult:
        """Convenience method for player switching to a different team Pokemon."""
        return self.execute_action(player, BattleAction(action_type=BattleActionType.SWITCH, target_pokemon=target_pokemon))

    def flee(self, player: Player) -> BattleActionResult:
        """Convenience method for player fleeing from a wild battle."""
        return self.execute_action(player, BattleAction(action_type=BattleActionType.FLEE))

    def inspect_wild_pokemon(self, player: Player) -> BattleActionResult:
        """Convenience method for player inspecting a wild Pokemon."""
        return self.execute_action(player, BattleAction(action_type=BattleActionType.INSPECT))

    def dodge(self, player: Player) -> BattleActionResult:
        """Convenience method for player executing a tactical dodge action."""
        return self.execute_action(player, BattleAction(action_type=BattleActionType.DODGE))

#     def talk(self, player: Player, command: Union[BattleTalkCommand, str]) -> BattleActionResult:
#         """
#         Public BattleManager API for talking to the active Pokemon in battle.
# 
#         Processes raw player text through the natural-language intent parser,
#         generates personality-aware dialogue for conversational battle talk,
#         or routes tactical dodge commands to the DODGE action.
# 
#         Args:
#             player: The Player issuing the battle talk action.
#             command: A structured BattleTalkCommand or a raw string message.
# 
#         Returns:
#             BattleActionResult indicating acceptance or rejection reason.
#         """
#         if not isinstance(player, Player):
#             raise TypeError(f"player must be a Player instance, got {type(player).__name__}.")
# 
#         battle = self.get_active_battle(player)
#         if battle is None:
#             return BattleActionResult(
#                 accepted=False,
#                 reason=f"Player '{player.name}' has no active battle.",
#                 action_type=BattleActionType.TALK,
#                 battle_state=BattleState.NOT_STARTED,
#                 error_type="NO_ACTIVE_BATTLE",
#             )
# 
        # 1. Parse raw text into structured BattleTalkCommand if a string was provided
#         if isinstance(command, BattleTalkCommand):
#             talk_cmd = command
#         elif isinstance(command, str):
#             from src.ai.battle_talk_parser import parse_battle_talk
#             talk_cmd = parse_battle_talk(command)
#         else:
#             return battle.take_action(BattleAction(action_type=BattleActionType.TALK, talk_command=command))
# 
        # 2. If tactical manoeuvre requested, route supported dodge to DODGE action, otherwise forward TALK for engine rejection
#         if talk_cmd.is_tactical:
#             tactical_action = ""
#             if talk_cmd.metadata and "detected_tactical_action" in talk_cmd.metadata:
#                 tactical_action = str(talk_cmd.metadata["detected_tactical_action"]).lower()
#             elif talk_cmd.intent:
#                 tactical_action = str(talk_cmd.intent).lower()
# 
#             is_dodge = any(k in tactical_action for k in ("dodge", "evade", "sidestep", "duck"))
#             if is_dodge:
#                 action = BattleAction(
#                     action_type=BattleActionType.DODGE,
#                     text=talk_cmd.text,
#                     talk_command=talk_cmd,
#                 )
#                 return self.execute_action(player, action)
#             return self.execute_action(player, BattleAction(action_type=BattleActionType.TALK, talk_command=talk_cmd))
# 
        # 3. Generate personality-aware companion dialogue if active Pokemon is present, conscious, and battle is in progress
#         if (
#             battle.state == BattleState.IN_PROGRESS
#             and battle.pokemon1 is not None
#             and not battle.pokemon1.is_fainted
#             and talk_cmd.dialogue is None
#         ):
#             from src.ai.companion_service import CompanionService, BattleTalkContext
#             milestone = None
#             if hasattr(battle, "get_latest_player_combat_milestone"):
#                 milestone = battle.get_latest_player_combat_milestone(mark_consumed=True)
#             last_event = milestone
#             if not last_event and hasattr(battle, "events") and battle.events:
#                 for ev in reversed(battle.events[-5:]):
#                     if "[DODGE_SUCCESS]" in ev:
#                         last_event = "dodge_success"
#                         break
#                     elif "[DODGE_FAILED]" in ev:
#                         last_event = "dodge_failed"
#                         break
#             bt_ctx = BattleTalkContext(last_event=last_event) if last_event else None
#             dialogue = CompanionService.generate_battle_talk_response(battle.pokemon1, talk_cmd, context=bt_ctx)
#             import dataclasses
#             talk_cmd = dataclasses.replace(talk_cmd, dialogue=dialogue)
# 
#         action = BattleAction(action_type=BattleActionType.TALK, talk_command=talk_cmd)
#         return self.execute_action(player, action)

    # --- In-Battle Capture ---

    def attempt_capture(
        self,
        player: Player,
        capture_manager: Optional[CaptureManager] = None,
    ) -> BattleActionResult:
        """
        Attempts to capture the opposing wild Pokemon during an active battle.
        If capture succeeds: resolves encounter, despawns wild Pokemon, concludes battle with CAPTURED.
        If capture fails: consumes turn and allows wild Pokemon to attack.
        """
        if not isinstance(player, Player):
            raise TypeError(f"player must be a Player instance, got {type(player).__name__}.")

        battle = self.get_active_battle(player)
        if battle is None:
            return BattleActionResult(
                accepted=False,
                reason=f"Player '{player.name}' has no active battle to capture in.",
                action_type=BattleActionType.CAPTURE,
                battle_state=BattleState.NOT_STARTED,
                error_type="NO_ACTIVE_BATTLE",
            )

        if battle.is_trainer_battle:
            return BattleActionResult(
                accepted=False,
                reason="Cannot capture a trainer's Pokemon!",
                action_type=BattleActionType.CAPTURE,
                battle_state=battle.state,
                error_type="CANNOT_CAPTURE_TRAINER",
            )

        if battle.pokemon2.is_fainted:
            return BattleActionResult(
                accepted=False,
                reason="Cannot capture a fainted Pokemon.",
                action_type=BattleActionType.CAPTURE,
                battle_state=battle.state,
                error_type="POKEMON_FAINTED",
            )

        cm = capture_manager or self._capture_manager or CaptureManager(rng=self._rng)

        cap_res = cm.attempt_capture(
            player=player,
            wild_pokemon=battle.pokemon2,
            encounter=battle.encounter,
            spawn_manager=self._spawn_manager,
        )

        if cap_res.success:
            battle._state = BattleState.CAPTURED
            battle._events.append(f"Successfully captured wild {battle.pokemon2.display_name}!")
            if battle.wild_agent is not None:
                from src.ai.wild_encounter_service import AutonomousWildService
                AutonomousWildService.record_encounter_concluded(battle.wild_agent, "captured", player)
            self._conclude_battle(battle, player)
            return BattleActionResult(
                accepted=True,
                reason=cap_res.message,
                action_type=BattleActionType.CAPTURE,
                battle_state=BattleState.CAPTURED,
                captured=True,
                terminal=True,
            )
        else:
            # Capture roll failed: wild Pokemon gets to counterattack
            executed_actions: list[Any] = []
            if not battle.pokemon2.is_fainted:
                opp_atk = battle._choose_opponent_attack(battle.pokemon2)
                if opp_atk is not None:
                    opp_record = battle._execute_action(
                        attacker=battle.pokemon2,
                        attack=opp_atk,
                        defender=battle.pokemon1,
                    )
                    executed_actions.append(opp_record)
                    if battle.pokemon1.is_fainted:
                        battle._events.append(f"{battle.pokemon1.display_name} fainted!")
                        battle._update_terminal_state()

            turn_res = TurnResult(
                turn_number=battle.current_turn,
                actions=tuple(executed_actions),
                battle_state=battle.state,
                winner=battle.winner,
                loser=battle.loser,
            )
            battle._history.append(turn_res)

            if battle.state.is_terminal():
                self._conclude_battle(battle, player)

            return BattleActionResult(
                accepted=True,
                reason=f"Capture attempt failed: {cap_res.message}",
                action_type=BattleActionType.CAPTURE,
                battle_state=battle.state,
                captured=False,
                turn_result=turn_res,
                terminal=battle.state.is_terminal(),
            )

    # --- Battle Resolution and Rewards ---

    def _conclude_battle(self, battle: Battle, player: Player) -> None:
        """
        Authoritatively handles post-battle rewards, quest events, and cleanup.
        Prevents duplicate rewards and ensures clean spawn area population cleanup.
        """
        # Remove from active battles
        self._active_battles.pop(player.unique_id, None)

        if battle.state == BattleState.VICTORY:
            # Record player aggressive action on wild defeat
            if battle.is_wild_battle and player is not None and hasattr(player, "record_wild_action"):
                species_name = battle.pokemon2.species.name if battle.pokemon2 else None
                player.record_wild_action("defeat", is_aggressive=True, species_name=species_name)

            # Award trainer victory items if battle was against a Trainer
            if battle.is_trainer_battle and battle.opponent_trainer is not None:
                if hasattr(battle.opponent_trainer, "claim_rewards"):
                    battle.opponent_trainer.claim_rewards(player)

            # 1. Experience rewards
            if self._experience_manager is not None and not battle.rewards_claimed:
                recipient = player.active_pokemon if player.active_pokemon and not player.active_pokemon.is_fainted else battle.winner
                rew = self._experience_manager.award_battle_rewards(battle, recipient=recipient)
                # Level up quest event
                if rew.eligible and rew.levels_gained > 0 and self._quest_manager is not None and recipient is not None:
                    self._quest_manager.record_event(
                        player=player,
                        event_type=QuestEventType.POKEMON_LEVEL_UP,
                        payload={"species_name": recipient.species.name, "new_level": recipient.level},
                        event_id=f"quest_evt_battle_levelup_{battle.battle_id}_{recipient.unique_id}_{recipient.level}",
                    )

            # 2. Bond rewards
            if self._bond_manager is not None and not battle.bond_rewards_claimed:
                recipient = player.active_pokemon if player.active_pokemon and not player.active_pokemon.is_fainted else battle.winner
                self._bond_manager.award_battle_victory_bond(battle, recipient=recipient)

            # 3. Quest event: POKEMON_DEFEATED
            if self._quest_manager is not None and battle.loser is not None:
                payload_def: dict[str, Any] = {
                    "species_name": battle.loser.species.name,
                    "level": battle.loser.level,
                    "count": 1,
                }
                if battle.region_id:
                    payload_def["region_id"] = battle.region_id
                self._quest_manager.record_event(
                    player=player,
                    event_type=QuestEventType.POKEMON_DEFEATED,
                    payload=payload_def,
                    event_id=f"quest_evt_battle_defeat_{battle.battle_id}_{battle.loser.unique_id}",
                )

            # 4. Award battle victory currency
            currency_reward = max(50, battle.loser.level * 25) if battle.loser is not None else 50
            player.add_currency(currency_reward)

            # 5. Wild encounter cleanup
            if battle.encounter is not None:
                if self._encounter_manager is not None:
                    self._encounter_manager.resolve_active_encounter(
                        player=player,
                        reason="Defeated in battle",
                        spawn_manager=self._spawn_manager,
                    )
                elif not battle.encounter.is_resolved:
                    battle.encounter.resolve(reason="Defeated in battle")
                    if self._spawn_manager is not None and battle.encounter.area is not None:
                        self._spawn_manager.despawn_pokemon(battle.encounter.area.area_id, battle.encounter.pokemon)

        elif battle.state in (BattleState.DEFEAT, BattleState.ESCAPED, BattleState.CANCELED):
            if battle.state == BattleState.DEFEAT:
                # Award defeat bond to all team members
                if self._bond_manager is not None:
                    team_mons = getattr(battle, "player_team", None) or player.team
                    for team_mon in team_mons:
                        self._bond_manager.award_battle_defeat_bond(battle, recipient=team_mon)

            # Clean up encounter and spawn area
            if battle.encounter is not None:
                if self._encounter_manager is not None:
                    self._encounter_manager.resolve_active_encounter(
                        player=player,
                        reason=f"Battle {battle.state.value.lower()}",
                        spawn_manager=self._spawn_manager,
                    )
                elif not battle.encounter.is_resolved:
                    battle.encounter.resolve(reason=f"Battle {battle.state.value.lower()}")
                    if self._spawn_manager is not None and battle.encounter.area is not None:
                        self._spawn_manager.despawn_pokemon(battle.encounter.area.area_id, battle.encounter.pokemon)

        elif battle.state == BattleState.CAPTURED:
            # Record player action on wild capture
            if battle.is_wild_battle and player is not None and hasattr(player, "record_wild_action"):
                species_name = battle.pokemon2.species.name if battle.pokemon2 else None
                is_peaceful = (battle.pokemon2.current_hp == battle.pokemon2.max_hp) if battle.pokemon2 else False
                player.record_wild_action("capture", is_peaceful=is_peaceful, is_aggressive=(not is_peaceful), species_name=species_name)

            # Capture cleanup already processed by CaptureManager, but ensure encounter manager is clear
            if self._encounter_manager is not None and self._encounter_manager.has_active_encounter(player):
                self._encounter_manager.resolve_active_encounter(player=player, reason="Captured")
            # Quest event dispatch for in-battle captures
            if self._quest_manager is not None and battle.pokemon2 is not None:
                enc_id = battle.encounter.encounter_id if (battle.encounter is not None and hasattr(battle.encounter, "encounter_id")) else "direct"
                cap_evt_id = f"quest_evt_capture_{enc_id}_{battle.pokemon2.unique_id}"
                col_evt_id = f"quest_evt_collect_{enc_id}_{battle.pokemon2.unique_id}_{len(player.collection)}"
                payload_cap: dict[str, Any] = {
                    "species_name": battle.pokemon2.species.name,
                    "level": battle.pokemon2.level,
                    "count": 1,
                }
                if battle.region_id:
                    payload_cap["region_id"] = battle.region_id
                self._quest_manager.record_event(
                    player=player,
                    event_type=QuestEventType.POKEMON_CAPTURED,
                    payload=payload_cap,
                    event_id=cap_evt_id,
                )
                payload_col: dict[str, Any] = {
                    "species_name": battle.pokemon2.species.name,
                    "count": len(player.collection),
                }
                if battle.region_id:
                    payload_col["region_id"] = battle.region_id
                self._quest_manager.record_event(
                    player=player,
                    event_type=QuestEventType.POKEMON_COLLECTED,
                    payload=payload_col,
                    event_id=col_evt_id,
                )

    def resolve_battle(self, player: Union[Player, str], reason: str = "Resolved") -> Optional[Battle]:
        """
        Manually and authoritatively resolves an active battle session.
        Releases active encounter and spawn population cleanly.
        Safe and idempotent: repeated calls return None without duplicate side-effects.
        """
        battle = self.get_active_battle(player)
        if battle is not None:
            if not battle.state.is_terminal():
                battle._state = BattleState.CANCELED
            p_obj = player if isinstance(player, Player) else battle.player
            if p_obj is not None:
                self._conclude_battle(battle, p_obj)
            else:
                p_id = player if isinstance(player, str) else player.unique_id
                self._active_battles.pop(p_id, None)
            return battle
        return None
