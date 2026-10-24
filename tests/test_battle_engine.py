"""
Comprehensive unit and integration tests for the Turn-Based Battle Engine:
- Battle initialization, lifecycle states, and singleton enforcement
- Move execution, validation, accuracy misses, damage calculation, and type effectiveness
- Speed initiative and deterministic tie-breaking
- HP boundaries, fainting, and action preemption on KO
- Team switching, switch priority, opponent attack on switch, and switch validation
- Multi-Pokemon teams and team exhaustion defeat
- Wild encounter integration: initiation, fleeing, despawning, and in-battle capture
- Victory experience, level-up progression, bond rewards, and anti-duplication
- Defeat handling and encounter cleanup
- Terminal state enforcement: action rejection after conclusion
- Trainer battles: opponent teams, AI move selection, opponent switching, and wild separation
- Quest event integration, objective advancement, and event deduplication
- Multi-player state isolation and seeded RNG reproducibility
- Save/load compatibility with Schema Version 4
"""
import random
import unittest

from src.models.pokemon import Pokemon
from src.models.player import Player
from src.models.personality import Personality
from src.models.attack import Attack
from src.models.pokemon_type import PokemonType
from src.models.battle_state import BattleState
from src.models.battle import (
    Battle,
    BattleAction,
    BattleActionType,
    BattleActionResult,
    TurnResult,
)
from src.models.battle_manager import BattleManager
from src.models.spawn_area import SpawnArea
from src.models.spawn_manager import SpawnManager
from src.models.encounter_manager import EncounterManager, WildEncounter
from src.models.capture_manager import CaptureManager
from src.models.experience_manager import ExperienceManager
from src.models.bond_manager import BondManager
from src.models.quest_manager import QuestManager
from src.models.quest import QuestStatus, ObjectiveType, QuestEventType
from src.data.species import PIKACHU, CHARMANDER, SQUIRTLE
from src.data.attacks import (
    THUNDER_SHOCK,
    QUICK_ATTACK,
    EMBER,
    SCRATCH,
    WATER_GUN,
    TACKLE,
    WILL_O_WISP,
    THUNDER_WAVE,
)
from src.data.quests import WILD_CHALLENGER, FIRST_ENCOUNTER
from src.models.save_manager import save_game, load_game, CURRENT_SCHEMA_VERSION


class TestBattleEngine(unittest.TestCase):
    """Test suite verifying the comprehensive turn-based battle engine."""

    def setUp(self) -> None:
        self.default_personality = Personality(
            aggression=50, curiosity=50, fear=50, sociability=50, loyalty=50, confidence=50
        )
        self.pika = Pokemon(
            species=PIKACHU,
            personality=self.default_personality,
            level=5,
            attacks=[THUNDER_SHOCK, QUICK_ATTACK],
        )
        self.charm = Pokemon(
            species=CHARMANDER,
            personality=self.default_personality,
            level=5,
            attacks=[EMBER, SCRATCH],
        )
        self.squirtle = Pokemon(
            species=SQUIRTLE,
            personality=self.default_personality,
            level=5,
            attacks=[WATER_GUN, TACKLE],
        )

        self.player = Player(name="Ash")
        self.player.add_pokemon(self.pika)
        self.player.add_to_team(self.pika)
        self.player.set_active_pokemon(self.pika)

        self.spawn_area = SpawnArea(
            area_id="test_forest",
            name="Viridian Forest",
            allowed_species=(PIKACHU, CHARMANDER, SQUIRTLE),
            max_active_pokemon=3,
        )
        self.spawn_manager = SpawnManager()
        self.spawn_manager.register_area(self.spawn_area)
        self.encounter_manager = EncounterManager(spawn_manager=self.spawn_manager)
        self.capture_manager = CaptureManager(seed=42)
        self.experience_manager = ExperienceManager()
        self.bond_manager = BondManager()
        self.quest_manager = QuestManager()

        self.manager = BattleManager(
            spawn_manager=self.spawn_manager,
            encounter_manager=self.encounter_manager,
            capture_manager=self.capture_manager,
            experience_manager=self.experience_manager,
            quest_manager=self.quest_manager,
            bond_manager=self.bond_manager,
            seed=42,
        )

    # 1. Battle initialization and validation
    def test_01_battle_initialization_and_validation(self) -> None:
        """Battle initializes properly and rejects invalid inputs."""
        battle = Battle(self.pika, self.charm, seed=123)
        self.assertEqual(battle.state, BattleState.NOT_STARTED)
        self.assertFalse(battle.state.is_terminal())
        self.assertEqual(battle.current_turn, 0)
        self.assertEqual(battle.pokemon1, self.pika)
        self.assertEqual(battle.pokemon2, self.charm)
        self.assertTrue(battle.is_wild_battle)

        # Self battle rejected
        with self.assertRaises(ValueError):
            Battle(self.pika, self.pika)

        # Non-Pokemon participant rejected
        with self.assertRaises(TypeError):
            Battle(self.pika, "Not a Pokemon")  # type: ignore

        # Fainted participant rejected on start
        fainted_mon = Pokemon(species=SQUIRTLE, personality=self.default_personality, level=5, current_hp=0)
        battle_fainted = Battle(self.pika, fainted_mon)
        with self.assertRaises(ValueError):
            battle_fainted.start()

    # 2. BattleManager singleton active battle enforcement
    def test_02_battle_manager_singleton_active_battle(self) -> None:
        """A player cannot create multiple concurrent battles."""
        battle1 = self.manager.start_battle(self.player, self.charm)
        self.assertTrue(self.manager.has_active_battle(self.player))
        self.assertIs(self.manager.get_active_battle(self.player), battle1)

        # Starting a second battle while one is active raises RuntimeError
        with self.assertRaises(RuntimeError):
            self.manager.start_battle(self.player, self.squirtle)

        # Battle remains unchanged
        self.assertIs(self.manager.get_active_battle(self.player), battle1)

    # 3. Move validation and rejected actions
    def test_03_move_validation_and_rejected_actions(self) -> None:
        """Invalid actions are rejected without consuming turns or mutating state."""
        battle = self.manager.start_battle(self.player, self.charm)
        self.assertEqual(battle.current_turn, 1)
        hp_before = self.charm.current_hp

        # Move not known by active Pokemon (e.g. Flamethrower)
        unknown_move = Attack(name="Hydro Pump", type=PokemonType.WATER, power=110, accuracy=80)
        res = self.manager.attack(self.player, unknown_move)

        self.assertFalse(res.accepted)
        self.assertEqual(res.error_type, "ATTACK_NOT_KNOWN")
        self.assertEqual(battle.current_turn, 1)
        self.assertEqual(self.charm.current_hp, hp_before)

        # Missing attack
        res_missing = self.manager.execute_action(self.player, BattleAction(action_type=BattleActionType.ATTACK, attack=None))
        self.assertFalse(res_missing.accepted)
        self.assertEqual(res_missing.error_type, "MISSING_ATTACK")

    # 4. Accuracy misses cause zero damage
    def test_04_accuracy_and_miss_handling(self) -> None:
        """Moves with zero accuracy miss cleanly and deal 0 damage."""
        miss_move = Attack(name="Blind Strike", type=PokemonType.NORMAL, power=80, accuracy=0)
        custom_pika = Pokemon(
            species=PIKACHU,
            personality=self.default_personality,
            level=5,
            attacks=[miss_move],
        )
        player2 = Player(name="Red")
        player2.add_pokemon(custom_pika)
        player2.add_to_team(custom_pika)
        player2.set_active_pokemon(custom_pika)

        battle = self.manager.start_battle(player2, self.charm, seed=99)
        res = self.manager.attack(player2, miss_move)

        self.assertTrue(res.accepted)
        self.assertIsNotNone(res.turn_result)
        first_act = res.turn_result.actions[0]
        self.assertFalse(first_act.hit)
        self.assertEqual(first_act.damage, 0)
        self.assertIn("missed", first_act.message)

    # 5. Damage calculation and type effectiveness
    def test_05_damage_calculation_and_type_effectiveness(self) -> None:
        """Damage respects type effectiveness (e.g. Electric vs Water is super effective)."""
        battle = Battle(self.pika, self.squirtle, seed=42, use_random_damage=False)
        battle.start()

        # Thunder Shock (Electric) against Squirtle (Water) -> 2.0x effectiveness
        turn_res = battle.resolve_turn(attack1=THUNDER_SHOCK, attack2=TACKLE)
        pika_action = turn_res.actions[0]  # Pika faster

        self.assertTrue(pika_action.hit)
        self.assertEqual(pika_action.type_effectiveness, 2.0)
        self.assertIn("super effective", pika_action.message)
        self.assertGreater(pika_action.damage, 0)

    # 6. HP never falls below zero
    def test_06_hp_boundaries_and_zero_clamping(self) -> None:
        """Damage exceeding remaining HP clamps HP to exactly 0."""
        self.charm.current_hp = 2
        battle = Battle(self.pika, self.charm, seed=42, use_random_damage=False)
        battle.start()

        battle.resolve_turn(attack1=THUNDER_SHOCK, attack2=SCRATCH)
        self.assertEqual(self.charm.current_hp, 0)
        self.assertTrue(self.charm.is_fainted)

    # 7. Speed initiative and deterministic tie-breaker
    def test_07_speed_initiative_and_deterministic_tie_breaker(self) -> None:
        """Faster Pokemon acts first, and equal speeds are resolved deterministically."""
        # Pikachu base speed 90 vs Charmander base speed 65 -> Pikachu acts first
        battle = Battle(self.pika, self.charm, seed=42)
        battle.start()
        turn_res = battle.resolve_turn(attack1=QUICK_ATTACK, attack2=SCRATCH)
        self.assertEqual(turn_res.actions[0].attacker, self.pika)

        # Equal speed participants
        clone_pika = Pokemon(species=PIKACHU, personality=self.default_personality, level=5, attacks=[THUNDER_SHOCK])
        battle_tie1 = Battle(self.pika, clone_pika, rng=random.Random(100))
        battle_tie1.start()
        res1 = battle_tie1.resolve_turn(attack1=THUNDER_SHOCK, attack2=THUNDER_SHOCK)

        battle_tie2 = Battle(self.pika, clone_pika, rng=random.Random(100))
        battle_tie2.start()
        res2 = battle_tie2.resolve_turn(attack1=THUNDER_SHOCK, attack2=THUNDER_SHOCK)

        # Same seed yields identical first attacker
        self.assertEqual(res1.actions[0].attacker, res2.actions[0].attacker)

    # 8. Fainting immediately prevents subsequent action
    def test_08_fainting_immediately_prevents_subsequent_action(self) -> None:
        """When the first attacker knocks out the defender, the defender's move does not execute."""
        self.charm.current_hp = 1
        battle = Battle(self.pika, self.charm, seed=42, use_random_damage=False)
        battle.start()

        turn_res = battle.resolve_turn(attack1=THUNDER_SHOCK, attack2=SCRATCH)
        # Pikachu is faster and knocks out Charmander; Charmander's Scratch should NOT execute
        self.assertEqual(len(turn_res.actions), 1)
        self.assertEqual(turn_res.actions[0].attacker, self.pika)
        self.assertTrue(self.charm.is_fainted)
        self.assertEqual(self.pika.current_hp, self.pika.max_hp)  # Took 0 damage

    # 9. Team switching action priority and incoming attack
    def test_09_team_switching_action_priority(self) -> None:
        """Switching executes before regular attacks, and the opponent attacks the incoming Pokemon."""
        self.player.add_pokemon(self.squirtle)
        self.player.add_to_team(self.squirtle)

        battle = self.manager.start_battle(self.player, self.charm, seed=42, use_random_damage=False)
        self.assertIs(self.player.active_pokemon, self.pika)

        # Switch to Squirtle
        squirtle_hp_before = self.squirtle.current_hp
        res = self.manager.switch(self.player, self.squirtle)

        self.assertTrue(res.accepted)
        self.assertEqual(res.action_type, BattleActionType.SWITCH)
        self.assertIs(self.player.active_pokemon, self.squirtle)
        self.assertIs(battle.pokemon1, self.squirtle)

        # Opponent attacked the incoming Squirtle
        self.assertIsNotNone(res.turn_result)
        self.assertEqual(len(res.turn_result.actions), 1)
        opp_action = res.turn_result.actions[0]
        self.assertEqual(opp_action.attacker, self.charm)
        self.assertEqual(opp_action.defender, self.squirtle)
        self.assertLess(self.squirtle.current_hp, squirtle_hp_before)

    # 10. Invalid switch rejection
    def test_10_invalid_switch_rejection(self) -> None:
        """Switching to already active, fainted, or non-team Pokemon is rejected."""
        self.player.add_pokemon(self.squirtle)
        self.player.add_to_team(self.squirtle)
        battle = self.manager.start_battle(self.player, self.charm)

        # 1. Switch to already active Pokemon
        res_self = self.manager.switch(self.player, self.pika)
        self.assertFalse(res_self.accepted)
        self.assertEqual(res_self.error_type, "INVALID_SWITCH")

        # 2. Switch to fainted Pokemon
        self.squirtle.current_hp = 0
        res_fainted = self.manager.switch(self.player, self.squirtle)
        self.assertFalse(res_fainted.accepted)
        self.assertEqual(res_fainted.error_type, "INVALID_SWITCH")

        # 3. Switch to Pokemon not on team
        unowned_mon = Pokemon(species=CHARMANDER, personality=self.default_personality, level=5)
        res_unowned = self.manager.switch(self.player, unowned_mon)
        self.assertFalse(res_unowned.accepted)
        self.assertEqual(res_unowned.error_type, "INVALID_SWITCH")

    # 11. Multi-Pokemon team and defeat on exhaustion
    def test_11_multi_pokemon_team_and_defeat_on_exhaustion(self) -> None:
        """Battle concludes as DEFEAT only when all player team members are fainted."""
        self.player.add_pokemon(self.squirtle)
        self.player.add_to_team(self.squirtle)

        # Pika starts with 1 HP
        self.pika.current_hp = 1
        # Charmander has strong move that knocks out Pika
        overpower_move = Attack(name="Inferno Blast", type=PokemonType.FIRE, power=80, accuracy=100)
        strong_charm = Pokemon(species=CHARMANDER, personality=self.default_personality, level=10, attacks=[overpower_move])

        battle = self.manager.start_battle(self.player, strong_charm, seed=42)
        # Slower attack for Pikachu so strong_charm hits first
        pika_slow = Attack(name="Slow Strike", type=PokemonType.NORMAL, power=10, accuracy=100)
        self.pika.assign_attack(pika_slow)

        res = self.manager.attack(self.player, pika_slow)
        self.assertTrue(self.pika.is_fainted)
        # Because Squirtle is still alive on team, battle is NOT yet terminal DEFEAT!
        self.assertEqual(battle.state, BattleState.IN_PROGRESS)
        self.assertTrue(self.manager.has_active_battle(self.player))

        # Attacking with fainted Pika is rejected
        res_atk_fainted = self.manager.attack(self.player, pika_slow)
        self.assertFalse(res_atk_fainted.accepted)

        # Player switches to conscious Squirtle
        res_switch = self.manager.switch(self.player, self.squirtle)
        self.assertTrue(res_switch.accepted)
        self.assertIs(self.player.active_pokemon, self.squirtle)

        # Now knock out Squirtle
        self.squirtle.current_hp = 1
        res_ko_squirtle = self.manager.attack(self.player, WATER_GUN)
        # Squirtle faints -> all player Pokemon fainted -> DEFEAT!
        self.assertTrue(self.squirtle.is_fainted)
        self.assertEqual(battle.state, BattleState.DEFEAT)
        self.assertFalse(self.manager.has_active_battle(self.player))

    # 12. Flee from wild battle
    def test_12_flee_from_wild_battle(self) -> None:
        """Player can flee from a wild battle, cleaning up encounter and spawn area."""
        self.spawn_manager.add_active_pokemon("test_forest", self.charm, (1.0, 1.0))
        encounter = self.encounter_manager.start_encounter(self.player, self.charm, self.spawn_area)

        battle = self.manager.start_wild_battle(self.player, encounter)
        self.assertTrue(self.manager.has_active_battle(self.player))
        self.assertEqual(self.spawn_manager.get_active_count("test_forest"), 1)

        res = self.manager.flee(self.player)
        self.assertTrue(res.accepted)
        self.assertTrue(res.escaped)
        self.assertEqual(battle.state, BattleState.ESCAPED)
        self.assertTrue(battle.state.is_terminal())

        # Cleanup verified
        self.assertFalse(self.manager.has_active_battle(self.player))
        self.assertFalse(self.encounter_manager.has_active_encounter(self.player))
        self.assertEqual(self.spawn_manager.get_active_count("test_forest"), 0)
        self.assertFalse(battle.rewards_claimed)

    # 13. Flee rejected in trainer battle
    def test_13_flee_rejected_in_trainer_battle(self) -> None:
        """Fleeing from a trainer battle is rejected cleanly."""
        trainer_opponent = Player(name="Blue")
        trainer_opponent.add_pokemon(self.charm)
        trainer_opponent.add_to_team(self.charm)
        trainer_opponent.set_active_pokemon(self.charm)

        battle = self.manager.start_trainer_battle(self.player, trainer_opponent)
        self.assertTrue(battle.is_trainer_battle)

        res = self.manager.flee(self.player)
        self.assertFalse(res.accepted)
        self.assertEqual(res.error_type, "CANNOT_FLEE_TRAINER")
        self.assertEqual(battle.state, BattleState.IN_PROGRESS)

    # 14. Capture during wild battle success
    def test_14_capture_during_battle_success(self) -> None:
        """Successful in-battle capture adds Pokemon to player collection and despawns it."""
        self.spawn_manager.add_active_pokemon("test_forest", self.charm, (2.0, 2.0))
        encounter = self.encounter_manager.start_encounter(self.player, self.charm, self.spawn_area)

        battle = self.manager.start_wild_battle(self.player, encounter)
        # Guarantee capture roll success by setting min_probability=1.0 on a dedicated CaptureManager
        sure_cm = CaptureManager(min_probability=1.0)

        res = self.manager.attempt_capture(self.player, capture_manager=sure_cm)
        self.assertTrue(res.accepted)
        self.assertTrue(res.captured)
        self.assertEqual(battle.state, BattleState.CAPTURED)
        self.assertTrue(battle.state.is_terminal())

        # Pokemon added to collection
        self.assertTrue(self.player.is_pokemon_owned(self.charm))
        # Active encounter and battle cleaned up
        self.assertFalse(self.manager.has_active_battle(self.player))
        self.assertFalse(self.encounter_manager.has_active_encounter(self.player))
        self.assertEqual(self.spawn_manager.get_active_count("test_forest"), 0)

    # 15. Capture during wild battle failure triggers counterattack
    def test_15_capture_during_battle_failure_triggers_counterattack(self) -> None:
        """Failed in-battle capture consumes action and allows wild Pokemon to counterattack."""
        self.spawn_manager.add_active_pokemon("test_forest", self.charm, (2.0, 2.0))
        encounter = self.encounter_manager.start_encounter(self.player, self.charm, self.spawn_area)

        battle = self.manager.start_wild_battle(self.player, encounter)
        # Guarantee capture roll failure
        fail_cm = CaptureManager(min_probability=0.0, max_probability=0.0)

        pika_hp_before = self.pika.current_hp
        res = self.manager.attempt_capture(self.player, capture_manager=fail_cm)

        self.assertTrue(res.accepted)
        self.assertFalse(res.captured)
        self.assertEqual(battle.state, BattleState.IN_PROGRESS)

        # Counterattack executed
        self.assertIsNotNone(res.turn_result)
        self.assertEqual(len(res.turn_result.actions), 1)
        self.assertEqual(res.turn_result.actions[0].attacker, self.charm)
        self.assertEqual(res.turn_result.actions[0].defender, self.pika)
        self.assertLess(self.pika.current_hp, pika_hp_before)

    # 16. Capture rejected on fainted or trainer Pokemon
    def test_16_capture_rejected_on_fainted_or_trainer_pokemon(self) -> None:
        """Capture attempts are rejected against fainted wild Pokemon and trainer Pokemon."""
        # 1. Trainer battle capture rejection
        trainer_opponent = Player(name="Gary")
        trainer_opponent.add_pokemon(self.charm)
        trainer_opponent.add_to_team(self.charm)
        trainer_opponent.set_active_pokemon(self.charm)

        self.manager.start_trainer_battle(self.player, trainer_opponent)
        res_trainer = self.manager.attempt_capture(self.player)
        self.assertFalse(res_trainer.accepted)
        self.assertEqual(res_trainer.error_type, "CANNOT_CAPTURE_TRAINER")

        self.manager.resolve_battle(self.player)

        # 2. Fainted Pokemon capture rejection
        battle_wild = self.manager.start_battle(self.player, self.charm)
        self.charm.current_hp = 0  # Artificially fainted
        res_fainted = self.manager.attempt_capture(self.player)
        self.assertFalse(res_fainted.accepted)
        self.assertEqual(res_fainted.error_type, "POKEMON_FAINTED")

    # 17. Victory experience and level-up rewards
    def test_17_victory_experience_and_level_up_rewards(self) -> None:
        """Victory awards experience and bond to winning Pokemon, advancing level progression."""
        self.charm.current_hp = 1
        battle = self.manager.start_battle(self.player, self.charm, seed=42, use_random_damage=False)

        xp_before = self.pika.experience
        bond_before = self.pika.bond
        res = self.manager.attack(self.player, THUNDER_SHOCK)

        self.assertTrue(res.accepted)
        self.assertEqual(battle.state, BattleState.VICTORY)
        self.assertTrue(battle.rewards_claimed)
        self.assertTrue(battle.bond_rewards_claimed)

        # XP gained (Level 5 Charmander * 50 = 250 XP)
        self.assertGreater(self.pika.experience, xp_before)
        # Bond increased (+5)
        self.assertEqual(self.pika.bond, bond_before + 5)

        # Repeated reward calls fail cleanly
        reward_repeat = self.experience_manager.award_battle_rewards(battle)
        self.assertFalse(reward_repeat.eligible)

    # 18. Defeat concludes battle without experience
    def test_18_defeat_concludes_battle_without_experience(self) -> None:
        """Defeat concludes the battle once with zero XP awarded and cleans up sessions."""
        self.spawn_manager.add_active_pokemon("test_forest", self.charm, (1.0, 1.0))
        encounter = self.encounter_manager.start_encounter(self.player, self.charm, self.spawn_area)

        battle = self.manager.start_wild_battle(self.player, encounter)
        self.pika.current_hp = 1
        strong_atk = Attack(name="Mega Blast", type=PokemonType.FIRE, power=200, accuracy=100)
        self.charm.assign_attack(strong_atk)

        res = self.manager.attack(self.player, QUICK_ATTACK)
        # Pikachu attacks, then Charmander defeats Pikachu
        self.assertTrue(self.pika.is_fainted)
        self.assertEqual(battle.state, BattleState.DEFEAT)
        self.assertFalse(self.manager.has_active_battle(self.player))
        self.assertFalse(self.encounter_manager.has_active_encounter(self.player))
        self.assertFalse(battle.rewards_claimed)

    # 19. Action rejection after terminal state
    def test_19_action_rejection_after_terminal_state(self) -> None:
        """Any action submitted after a battle has concluded is rejected cleanly."""
        battle = self.manager.start_battle(self.player, self.charm)
        self.charm.current_hp = 1
        self.manager.attack(self.player, THUNDER_SHOCK)
        self.assertTrue(battle.state.is_terminal())

        # Attempt to attack after victory
        res_post = battle.take_action(BattleAction(action_type=BattleActionType.ATTACK, attack=THUNDER_SHOCK))
        self.assertFalse(res_post.accepted)
        self.assertEqual(res_post.error_type, "BATTLE_ALREADY_TERMINAL")

    # 20. Trainer battle lifecycle, AI selection, and opponent switching
    def test_20_trainer_battle_lifecycle_ai_and_opponent_switching(self) -> None:
        """Trainer battle opponent AI picks valid moves and switches upon active KO."""
        opponent = Player(name="Rival")
        opp_mon1 = Pokemon(species=CHARMANDER, personality=self.default_personality, level=5, attacks=[EMBER])
        opp_mon2 = Pokemon(species=SQUIRTLE, personality=self.default_personality, level=5, attacks=[WATER_GUN])
        opponent.add_pokemon(opp_mon1)
        opponent.add_pokemon(opp_mon2)
        opponent.add_to_team(opp_mon1)
        opponent.add_to_team(opp_mon2)
        opponent.set_active_pokemon(opp_mon1)

        battle = self.manager.start_trainer_battle(self.player, opponent, seed=42)
        self.assertTrue(battle.is_trainer_battle)

        # Knock out opponent's first Pokemon
        opp_mon1.current_hp = 1
        res = self.manager.attack(self.player, THUNDER_SHOCK)
        self.assertTrue(opp_mon1.is_fainted)

        # Opponent automatically switched to Squirtle!
        self.assertIs(battle.pokemon2, opp_mon2)
        self.assertIs(opponent.active_pokemon, opp_mon2)
        self.assertEqual(battle.state, BattleState.IN_PROGRESS)

        # Knock out Squirtle -> Victory!
        opp_mon2.current_hp = 1
        res2 = self.manager.attack(self.player, THUNDER_SHOCK)
        self.assertTrue(opp_mon2.is_fainted)
        self.assertEqual(battle.state, BattleState.VICTORY)
        self.assertFalse(self.manager.has_active_battle(self.player))

    # 21. Quest event integration and deduplication
    def test_21_quest_event_integration_and_deduplication(self) -> None:
        """Victory emits POKEMON_DEFEATED advancing quests, while capture or escape does not."""
        self.quest_manager.accept_quest(self.player, WILD_CHALLENGER.quest_id)
        prog = self.quest_manager.get_quest_progress(self.player, WILD_CHALLENGER.quest_id)
        self.assertIsNotNone(prog)
        self.assertEqual(prog.status, QuestStatus.ACTIVE)
        self.assertEqual(prog.objective_progress["defeat_any_pokemon"].current_count, 0)

        # Defeat wild Charmander in battle
        self.charm.current_hp = 1
        battle = self.manager.start_battle(self.player, self.charm, seed=42)
        self.manager.attack(self.player, THUNDER_SHOCK)

        # Quest objective updated
        self.assertEqual(prog.objective_progress["defeat_any_pokemon"].current_count, 1)
        self.assertTrue(prog.is_completed)

        # Deduplication test: replaying identical defeat event has no extra effect
        replayed_res = self.quest_manager.record_event(
            player=self.player,
            event_type=QuestEventType.POKEMON_DEFEATED,
            payload={"species_name": "Charmander", "level": 5},
            event_id=f"quest_evt_battle_defeat_{battle.battle_id}_{self.charm.unique_id}",
        )
        self.assertEqual(replayed_res.objectives_updated, 0)

    # 22. Multi-player state isolation
    def test_22_multi_player_battle_isolation(self) -> None:
        """Two players can battle simultaneously without state contamination."""
        player2 = Player(name="Leaf")
        pika2 = Pokemon(species=PIKACHU, personality=self.default_personality, level=5, attacks=[THUNDER_SHOCK])
        player2.add_pokemon(pika2)
        player2.add_to_team(pika2)
        player2.set_active_pokemon(pika2)

        wild1 = Pokemon(species=CHARMANDER, personality=self.default_personality, level=5, attacks=[SCRATCH])
        wild2 = Pokemon(species=SQUIRTLE, personality=self.default_personality, level=5, attacks=[TACKLE])

        battle1 = self.manager.start_battle(self.player, wild1)
        battle2 = self.manager.start_battle(player2, wild2)

        self.assertIs(self.manager.get_active_battle(self.player), battle1)
        self.assertIs(self.manager.get_active_battle(player2), battle2)

        # Player 1 acts
        self.manager.attack(self.player, THUNDER_SHOCK)
        self.assertEqual(battle1.current_turn, 2)
        self.assertEqual(battle2.current_turn, 1)

    # 23. Seeded RNG reproducibility
    def test_23_seeded_rng_reproducibility(self) -> None:
        """Identical seeds yield identical turns, accuracy rolls, and damage values."""
        pika_a = Pokemon(species=PIKACHU, personality=self.default_personality, level=5, attacks=[THUNDER_SHOCK])
        charm_a = Pokemon(species=CHARMANDER, personality=self.default_personality, level=5, attacks=[SCRATCH])
        battle_a = Battle(pika_a, charm_a, seed=777)
        battle_a.start()
        turn_a = battle_a.resolve_turn(attack1=THUNDER_SHOCK, attack2=SCRATCH)

        pika_b = Pokemon(species=PIKACHU, personality=self.default_personality, level=5, attacks=[THUNDER_SHOCK])
        charm_b = Pokemon(species=CHARMANDER, personality=self.default_personality, level=5, attacks=[SCRATCH])
        battle_b = Battle(pika_b, charm_b, seed=777)
        battle_b.start()
        turn_b = battle_b.resolve_turn(attack1=THUNDER_SHOCK, attack2=SCRATCH)

        self.assertEqual(turn_a.actions[0].damage, turn_b.actions[0].damage)
        self.assertEqual(turn_a.actions[0].hit, turn_b.actions[0].hit)
        self.assertEqual(pika_a.current_hp, pika_b.current_hp)
        self.assertEqual(charm_a.current_hp, charm_b.current_hp)

    # 24. Save/load persistence during and after battles
    def test_24_save_load_persistence_during_and_after_battles(self) -> None:
        """Battle outcomes persist cleanly through SaveManager Schema Version 4."""
        self.charm.current_hp = 1
        battle = self.manager.start_battle(self.player, self.charm, seed=42)
        self.manager.attack(self.player, THUNDER_SHOCK)
        self.assertEqual(battle.state, BattleState.VICTORY)

        # Save player state to dictionary
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmp_dir:
            save_path = os.path.join(tmp_dir, "test_battle_save.json")
            save_game(self.player, save_path)

            restored_player = load_game(save_path)
            self.assertEqual(restored_player.name, "Ash")
            restored_pika = restored_player.active_pokemon
            self.assertIsNotNone(restored_pika)
            self.assertEqual(restored_pika.experience, self.pika.experience)
            self.assertEqual(restored_pika.bond, self.pika.bond)

    # 25. Manual resolve_battle idempotency
    def test_25_manual_resolve_battle_idempotency(self) -> None:
        """Manual resolve_battle cleans up sessions and is strictly idempotent."""
        self.spawn_manager.add_active_pokemon("test_forest", self.charm, (1.0, 1.0))
        encounter = self.encounter_manager.start_encounter(self.player, self.charm, self.spawn_area)

        battle = self.manager.start_wild_battle(self.player, encounter)
        self.assertTrue(self.manager.has_active_battle(self.player))

        # First resolution
        resolved = self.manager.resolve_battle(self.player, reason="Canceled by referee")
        self.assertIs(resolved, battle)
        self.assertEqual(battle.state, BattleState.CANCELED)
        self.assertFalse(self.manager.has_active_battle(self.player))
        self.assertEqual(self.spawn_manager.get_active_count("test_forest"), 0)

        # Second resolution is safe no-op returning None
        resolved_again = self.manager.resolve_battle(self.player)
        self.assertIsNone(resolved_again)
        self.assertEqual(self.spawn_manager.get_active_count("test_forest"), 0)


if __name__ == "__main__":
    unittest.main()
