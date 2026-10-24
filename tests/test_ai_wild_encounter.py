"""
Integration and unit tests for autonomous wild Pokemon intelligence in encounters
and battles, covering perception, AI decision-making, dialogue emission,
memory formation, relationship updates, and persistence.
"""
import unittest
import random
from typing import Optional

from src.ai.agent import PokemonAgent
from src.ai.decision import AgentActionType, AgentDecision
from src.ai.decision_provider import MockDecisionProvider
from src.ai.memory import MemoryEpisode
from src.ai.persistence import AiState, serialize_ai_state, deserialize_ai_state
from src.ai.relationships import RelationshipStage
from src.ai.wild_encounter_service import AutonomousWildService
from src.data.attacks import THUNDER_SHOCK, QUICK_ATTACK, TACKLE, EMBER
from src.data.species import PIKACHU, CHARMANDER, SQUIRTLE
from src.models.attack import Attack
from src.models.battle import Battle, BattleAction, BattleActionType
from src.models.battle_manager import BattleManager
from src.models.battle_state import BattleState
from src.models.personality import Personality
from src.models.player import Player
from src.models.pokemon import Pokemon
from src.models.wild_ai import WildActionType


class TestAutonomousWildService(unittest.TestCase):
    """Tests AutonomousWildService core functions."""

    def setUp(self) -> None:
        self.personality = Personality(aggression=60, fear=40, curiosity=70, loyalty=50, confidence=65, sociability=55)
        self.wild_pokemon = Pokemon(
            species=PIKACHU,
            personality=self.personality,
            level=4,
            attacks=[THUNDER_SHOCK, QUICK_ATTACK],
        )
        self.player_pokemon = Pokemon(
            species=SQUIRTLE,
            personality=self.personality,
            level=5,
            attacks=[TACKLE],
        )
        self.player = Player(name="Ash")
        self.ai_state = AiState()

    def test_get_or_create_agent_fresh_and_cached(self) -> None:
        """Creates a new agent on first request and retrieves existing agent subsequently."""
        agent1 = AutonomousWildService.get_or_create_agent(self.wild_pokemon, self.ai_state)
        self.assertIsInstance(agent1, PokemonAgent)
        self.assertEqual(agent1.agent_id, self.wild_pokemon.unique_id)
        self.assertEqual(agent1.identity.species, "Pikachu")
        self.assertTrue(agent1.is_wild)
        self.assertFalse(agent1.is_captured)
        self.assertIn(self.wild_pokemon.unique_id, self.ai_state.agents)

        # Second call returns the cached instance
        agent2 = AutonomousWildService.get_or_create_agent(self.wild_pokemon, self.ai_state)
        self.assertIs(agent1, agent2)

    def test_decide_turn_attack_action(self) -> None:
        """Deciding an attack returns a WildDecision with mapped attack and dialogue."""
        agent = AutonomousWildService.get_or_create_agent(self.wild_pokemon, self.ai_state)
        mock_provider = MockDecisionProvider(
            forced_decision=AgentDecision(
                action_type=AgentActionType.ATTACK,
                intent="Attack the opponent",
                chosen_move="Thunder Shock",
                dialogue="Pika... CHU!",
                rationale="Defending territory with electrical burst.",
                confidence=0.88,
                emotional_state="defiant",
            )
        )

        decision = AutonomousWildService.decide_turn(
            agent=agent,
            wild_pokemon=self.wild_pokemon,
            player_pokemon=self.player_pokemon,
            player=self.player,
            provider=mock_provider,
            region_id="starting_meadow",
        )

        self.assertEqual(decision.action_type, WildActionType.ATTACK)
        self.assertIsNotNone(decision.chosen_attack)
        self.assertEqual(decision.chosen_attack.name, "Thunder Shock")
        self.assertEqual(decision.factors["dialogue"], "Pika... CHU!")
        self.assertEqual(decision.factors["emotional_state"], "defiant")
        self.assertEqual(decision.factors["agent_id"], agent.agent_id)

    def test_decide_turn_flee_action(self) -> None:
        """Deciding to flee maps to WildActionType.FLEE with flee rationale."""
        agent = AutonomousWildService.get_or_create_agent(self.wild_pokemon, self.ai_state)
        mock_provider = MockDecisionProvider(
            forced_decision=AgentDecision(
                action_type=AgentActionType.FLEE,
                intent="Escape danger",
                dialogue="Pikaaa!",
                rationale="Overwhelmed and retreating to safety.",
                confidence=0.92,
                emotional_state="frightened",
            )
        )

        decision = AutonomousWildService.decide_turn(
            agent=agent,
            wild_pokemon=self.wild_pokemon,
            player_pokemon=self.player_pokemon,
            player=self.player,
            provider=mock_provider,
        )

        self.assertEqual(decision.action_type, WildActionType.FLEE)
        self.assertIsNone(decision.chosen_attack)
        self.assertIn("retreating to safety", decision.reason)

    def test_decide_turn_inspect_and_hesitate_action(self) -> None:
        """Inspecting or hesitating maps to WildActionType.INSPECT."""
        agent = AutonomousWildService.get_or_create_agent(self.wild_pokemon, self.ai_state)
        mock_provider = MockDecisionProvider(
            forced_decision=AgentDecision(
                action_type=AgentActionType.INSPECT,
                intent="Observe opponent",
                dialogue="Pika?",
                rationale="Observing opponent carefully.",
                confidence=0.75,
                emotional_state="curious",
            )
        )

        decision = AutonomousWildService.decide_turn(
            agent=agent,
            wild_pokemon=self.wild_pokemon,
            player_pokemon=self.player_pokemon,
            player=self.player,
            provider=mock_provider,
        )

        self.assertEqual(decision.action_type, WildActionType.INSPECT)
        self.assertIsNone(decision.chosen_attack)

    def test_record_combat_damage(self) -> None:
        """Recording combat damage stores episodic memory and adjusts trainer trust/familiarity."""
        agent = AutonomousWildService.get_or_create_agent(self.wild_pokemon, self.ai_state)
        ep = AutonomousWildService.record_combat_damage(
            agent=agent,
            damage=15,
            attacker_pokemon=self.player_pokemon,
            player=self.player,
        )

        self.assertEqual(ep.event_type, "combat_damage")
        self.assertIn("Took 15 damage", ep.summary)
        self.assertLess(ep.emotional_impact, 0.0)

        rel = agent.get_relationship(self.player.unique_id)
        self.assertLess(rel.trust, 0.0)
        self.assertGreater(rel.familiarity, 0.0)
        self.assertIn(ep.episode_id, rel.significant_memories)

    def test_record_combat_strike(self) -> None:
        """Recording combat strike stores episodic memory with positive valence."""
        agent = AutonomousWildService.get_or_create_agent(self.wild_pokemon, self.ai_state)
        ep = AutonomousWildService.record_combat_strike(
            agent=agent,
            damage=20,
            attack_name="Thunder Shock",
            defender_pokemon=self.player_pokemon,
        )

        self.assertEqual(ep.event_type, "combat_strike")
        self.assertIn("Thunder Shock", ep.summary)
        self.assertGreater(ep.emotional_impact, 0.0)

    def test_record_observation(self) -> None:
        """Recording observation increases familiarity with trainer."""
        agent = AutonomousWildService.get_or_create_agent(self.wild_pokemon, self.ai_state)
        ep = AutonomousWildService.record_observation(
            agent=agent,
            target_name=self.player_pokemon.display_name,
            details="Watched the trainer's stance intently",
            player=self.player,
        )

        self.assertEqual(ep.event_type, "encounter_inspect")
        rel = agent.get_relationship(self.player.unique_id)
        self.assertGreaterEqual(rel.familiarity, 5.0)

    def test_record_encounter_concluded_captured(self) -> None:
        """Captured outcome updates agent ownership flags and records memory."""
        agent = AutonomousWildService.get_or_create_agent(self.wild_pokemon, self.ai_state)
        self.assertTrue(agent.is_wild)
        self.assertFalse(agent.is_captured)

        ep = AutonomousWildService.record_encounter_concluded(
            agent=agent,
            outcome="captured",
            player=self.player,
        )

        self.assertEqual(ep.event_type, "encounter_captured")
        self.assertFalse(agent.is_wild)
        self.assertTrue(agent.is_captured)


class TestBattleWithAutonomousWildAgent(unittest.TestCase):
    """Tests turn-based Battle execution powered by autonomous wild Pokemon."""

    def setUp(self) -> None:
        self.personality = Personality(aggression=50, fear=50, curiosity=50, loyalty=50, confidence=50, sociability=50)
        self.player_mon = Pokemon(
            species=CHARMANDER,
            personality=self.personality,
            level=6,
            attacks=[EMBER, TACKLE],
        )
        self.wild_mon = Pokemon(
            species=PIKACHU,
            personality=self.personality,
            level=4,
            attacks=[THUNDER_SHOCK, QUICK_ATTACK],
        )
        self.player = Player(name="Red")
        self.player.add_pokemon(self.player_mon)
        self.player.set_active_pokemon(self.player_mon)

        self.ai_state = AiState()
        self.agent = AutonomousWildService.get_or_create_agent(self.wild_mon, self.ai_state)

    def test_battle_attack_turn_with_wild_agent(self) -> None:
        """When player and autonomous wild Pokemon attack, memories and dialogue are recorded."""
        provider = MockDecisionProvider(
            forced_decision=AgentDecision(
                action_type=AgentActionType.ATTACK,
                intent="Counterattack",
                chosen_move="Thunder Shock",
                dialogue="Pika... chuu!",
                rationale="Strike the fire lizard with lightning.",
                confidence=0.85,
            )
        )

        battle = Battle(
            pokemon1=self.player_mon,
            pokemon2=self.wild_mon,
            player=self.player,
            wild_agent=self.agent,
            ai_provider=provider,
            use_random_damage=False,
            seed=42,
        )
        battle.start()

        res = battle.take_action(BattleAction(action_type=BattleActionType.ATTACK, attack=EMBER))
        self.assertTrue(res.accepted)
        self.assertIsNotNone(res.turn_result)

        # Check dialogue in events
        dialogue_events = [e for e in battle.events if "Pika... chuu!" in e]
        self.assertTrue(len(dialogue_events) > 0, "Wild Pokemon dialogue should appear in battle events.")

        # Check memories formed on wild agent
        memory_types = [m.event_type for m in self.agent.memory.episodic.get_recent_episodes(5)]
        self.assertIn("combat_damage", memory_types, "Wild agent should remember taking damage.")
        self.assertIn("combat_strike", memory_types, "Wild agent should remember striking back.")

    def test_wild_agent_flee_terminates_battle_with_escaped(self) -> None:
        """When wild agent autonomously flees, battle state becomes ESCAPED and memory is formed."""
        provider = MockDecisionProvider(
            forced_decision=AgentDecision(
                action_type=AgentActionType.FLEE,
                intent="Flee from battle",
                dialogue="Pika-run!",
                rationale="Trainer looks too fierce; fleeing.",
            )
        )

        battle = Battle(
            pokemon1=self.player_mon,
            pokemon2=self.wild_mon,
            player=self.player,
            wild_agent=self.agent,
            ai_provider=provider,
            use_random_damage=False,
        )
        battle.start()

        # Wild agent decides to flee during player's attack action
        res = battle.take_action(BattleAction(action_type=BattleActionType.ATTACK, attack=EMBER))
        self.assertTrue(res.accepted)
        self.assertEqual(battle.state, BattleState.ESCAPED)

        # Check escaped memory
        escaped_mem = [m for m in self.agent.memory.episodic.get_recent_episodes(5) if m.event_type == "encounter_escaped"]
        self.assertTrue(len(escaped_mem) > 0, "Wild agent should record an encounter_escaped memory.")

    def test_wild_agent_fainted_records_fainted_memory(self) -> None:
        """Knocking out wild Pokemon records encounter_fainted on wild agent."""
        # Set wild mon HP very low so single attack KOs it
        self.wild_mon._current_hp = 1

        provider = MockDecisionProvider(
            forced_decision=AgentDecision(
                action_type=AgentActionType.ATTACK,
                intent="Desperate attack",
                chosen_move="Quick Attack",
            )
        )

        battle = Battle(
            pokemon1=self.player_mon,
            pokemon2=self.wild_mon,
            player=self.player,
            wild_agent=self.agent,
            ai_provider=provider,
            use_random_damage=False,
        )
        battle.start()

        res = battle.take_action(BattleAction(action_type=BattleActionType.ATTACK, attack=EMBER))
        self.assertTrue(res.accepted)
        self.assertEqual(battle.state, BattleState.VICTORY)

        fainted_mem = [m for m in self.agent.memory.episodic.get_recent_episodes(5) if m.event_type == "encounter_fainted"]
        self.assertTrue(len(fainted_mem) > 0, "Wild agent should record an encounter_fainted memory.")


class TestBattleManagerAutonomousIntegration(unittest.TestCase):
    """Tests end-to-end BattleManager coordination of autonomous wild Pokemon."""

    def setUp(self) -> None:
        self.personality = Personality(aggression=50, fear=50, curiosity=50, loyalty=50, confidence=50, sociability=50)
        self.player_mon = Pokemon(
            species=CHARMANDER,
            personality=self.personality,
            level=7,
            attacks=[EMBER, TACKLE],
        )
        self.wild_mon = Pokemon(
            species=PIKACHU,
            personality=self.personality,
            level=3,
            attacks=[THUNDER_SHOCK, QUICK_ATTACK],
        )
        self.player = Player(name="Red")
        self.player.add_pokemon(self.player_mon)
        self.player.add_to_team(self.player_mon)
        self.player.set_active_pokemon(self.player_mon)

        self.ai_state = AiState()
        self.mock_provider = MockDecisionProvider(
            forced_decision=AgentDecision(
                action_type=AgentActionType.ATTACK,
                intent="Counterattack",
                chosen_move="Thunder Shock",
                dialogue="Pika-spark!",
            )
        )
        self.manager = BattleManager(
            ai_state=self.ai_state,
            ai_provider=self.mock_provider,
        )

    def test_start_battle_automatically_creates_agent_in_ai_state(self) -> None:
        """Starting a wild battle automatically creates and attaches an autonomous agent."""
        battle = self.manager.start_battle(self.player, self.wild_mon)
        self.assertIsNotNone(battle.wild_agent)
        self.assertEqual(battle.wild_agent.agent_id, self.wild_mon.unique_id)
        self.assertIn(self.wild_mon.unique_id, self.ai_state.agents)

    def test_attempt_capture_success_records_captured_on_wild_agent(self) -> None:
        """Successful capture marks agent as captured and updates relationship."""
        battle = self.manager.start_battle(self.player, self.wild_mon)
        agent = battle.wild_agent

        # Execute capture with mock capture manager that always succeeds
        class MockCaptureManager:
            def attempt_capture(self, player, wild_pokemon, encounter=None, spawn_manager=None):
                class Res:
                    success = True
                    message = "Gotcha! Pikachu was caught!"
                return Res()

        res = self.manager.attempt_capture(self.player, capture_manager=MockCaptureManager())
        self.assertTrue(res.captured)
        self.assertTrue(agent.is_captured)
        self.assertFalse(agent.is_wild)

        captured_mem = [m for m in agent.memory.episodic.get_recent_episodes(5) if m.event_type == "encounter_captured"]
        self.assertTrue(len(captured_mem) > 0)

    def test_ai_state_persistence_after_wild_battle(self) -> None:
        """Serializing and deserializing AiState preserves wild agent's battle experiences and relationships."""
        battle = self.manager.start_battle(self.player, self.wild_mon)
        agent = battle.wild_agent

        # Player attacks wild Pikachu
        res = self.manager.attack(self.player, EMBER)
        self.assertTrue(res.accepted)

        # Verify memories were created
        self.assertGreater(len(agent.memory.episodic.episodes), 0)

        # Serialize AI state to dictionary/JSON
        serialized = serialize_ai_state(self.ai_state)
        restored_ai_state = deserialize_ai_state(serialized)

        restored_agent = restored_ai_state.get_agent(self.wild_mon.unique_id)
        self.assertIsNotNone(restored_agent)
        self.assertEqual(restored_agent.agent_id, self.wild_mon.unique_id)
        self.assertEqual(len(restored_agent.memory.episodic.episodes), len(agent.memory.episodic.episodes))

        # Check restored relationship
        rel = restored_agent.get_relationship(self.player.unique_id)
        self.assertIsNotNone(rel)
        self.assertEqual(rel.entity_id, self.player.unique_id)
        self.assertLess(rel.trust, 0.0)


if __name__ == "__main__":
    unittest.main()
