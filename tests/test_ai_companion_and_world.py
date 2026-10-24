"""
Unit and integration test suite for companion Pokemon intelligence,
trainer interactions (talk, praise, scold, release), battle tactical decisions,
teammate social dynamics, and event-driven world scheduling (Steps 6 & 7).
"""
import unittest
from typing import Optional

from src.ai.agent import PokemonAgent
from src.ai.companion_service import (
    CompanionService,
    CompanionInteractionResult,
    CompanionBattleDisposition,
    TeammateInteractionResult,
)
from src.ai.decision import AgentActionType, AgentDecision
from src.ai.decision_provider import MockDecisionProvider
from src.ai.memory import MemoryEpisode
from src.ai.persistence import AiState, serialize_ai_state, deserialize_ai_state
from src.ai.relationships import RelationshipStage
from src.ai.scheduler import AutonomousWorldScheduler
from src.data.attacks import THUNDER_SHOCK, QUICK_ATTACK, TACKLE, EMBER, VINE_WHIP
from src.data.species import PIKACHU, CHARMANDER, SQUIRTLE, BULBASAUR
from src.models.attack import Attack
from src.models.battle import Battle, BattleAction, BattleActionType
from src.models.battle_manager import BattleManager
from src.models.battle_state import BattleState
from src.models.personality import Personality
from src.models.player import Player
from src.models.pokemon import Pokemon


class TestCompanionInteractions(unittest.TestCase):
    """Tests trainer-companion interactions, praise, scold, goals, and release (Step 6)."""

    def setUp(self) -> None:
        self.personality = Personality(aggression=40, fear=30, curiosity=80, loyalty=85, confidence=70, sociability=75)
        self.pikachu = Pokemon(species=PIKACHU, personality=self.personality, level=5, attacks=[THUNDER_SHOCK, QUICK_ATTACK])
        self.player = Player(name="Ash")
        self.player.add_pokemon(self.pikachu)
        self.player.add_to_team(self.pikachu)
        self.player.set_active_pokemon(self.pikachu)

        self.ai_state = AiState()
        self.agent = CompanionService.get_or_create_companion_agent(self.pikachu, self.ai_state, self.player)

    def test_companion_agent_initialization(self) -> None:
        """Companion is initialized as captured, with trainer relationship and default goals."""
        self.assertTrue(self.agent.is_captured)
        self.assertFalse(self.agent.is_wild)
        self.assertEqual(self.agent.identity.species, "Pikachu")

        rel = self.agent.get_relationship(self.player.unique_id)
        self.assertGreaterEqual(rel.trust, 25.0)
        self.assertGreaterEqual(rel.affection, 25.0)
        self.assertGreaterEqual(len(self.agent.goals.immediate_goals), 1)

    def test_interact_praise_enhances_relationship_and_bond(self) -> None:
        """Praising companion increases affection, trust, bond, and records memory."""
        initial_bond = self.pikachu.bond
        mock_provider = MockDecisionProvider(
            forced_decision=AgentDecision(
                action_type=AgentActionType.OBEY,
                intent="Receive praise warmly",
                dialogue="Pika-pi! (Beams happily)",
                emotional_state="joyful",
            )
        )

        res = CompanionService.interact(
            agent=self.agent,
            pokemon=self.pikachu,
            player=self.player,
            interaction_type="praise",
            provider=mock_provider,
        )

        self.assertGreater(res.affection_change, 0)
        self.assertGreater(res.trust_change, 0)
        self.assertGreater(res.bond_change, 0)
        self.assertGreater(self.pikachu.bond, initial_bond)
        self.assertIn("Pika-pi!", res.dialogue)

        # Verify episodic memory
        episodes = self.agent.memory.episodic.get_recent_episodes(5)
        praise_eps = [e for e in episodes if e.event_type == "trainer_praise"]
        self.assertTrue(len(praise_eps) > 0)
        self.assertGreater(praise_eps[0].emotional_impact, 0.0)

    def test_interact_scold_reduces_trust_and_affection(self) -> None:
        """Scolding companion decreases affection, trust, and records criticism memory."""
        self.pikachu.bond = 50
        initial_bond = self.pikachu.bond
        mock_provider = MockDecisionProvider(
            forced_decision=AgentDecision(
                action_type=AgentActionType.HESITATE,
                intent="Feel remorseful",
                dialogue="Chuu... (Droops head sadly)",
                emotional_state="dejected",
            )
        )

        res = CompanionService.interact(
            agent=self.agent,
            pokemon=self.pikachu,
            player=self.player,
            interaction_type="scold",
            provider=mock_provider,
        )

        self.assertLess(res.affection_change, 0)
        self.assertLess(res.trust_change, 0)
        self.assertLess(res.bond_change, 0)
        self.assertLess(self.pikachu.bond, initial_bond)

        episodes = self.agent.memory.episodic.get_recent_episodes(5)
        scold_eps = [e for e in episodes if e.event_type == "trainer_criticism"]
        self.assertTrue(len(scold_eps) > 0)
        self.assertLess(scold_eps[0].emotional_impact, 0.0)

    def test_interact_general_conversation(self) -> None:
        """Talking with partner increases familiarity and records conversation memory."""
        rel = self.agent.get_relationship(self.player.unique_id)
        prev_fam = rel.familiarity

        mock_provider = MockDecisionProvider(
            forced_decision=AgentDecision(
                action_type=AgentActionType.INTERACT,
                intent="Share cheerful banter",
                dialogue="Pikachu-pika!",
            )
        )

        res = CompanionService.interact(
            agent=self.agent,
            pokemon=self.pikachu,
            player=self.player,
            interaction_type="talk",
            provider=mock_provider,
        )

        self.assertGreater(rel.familiarity, prev_fam)
        self.assertIn("Pikachu-pika!", res.dialogue)

    def test_cannot_release_only_pokemon(self) -> None:
        """Player cannot release their sole remaining Pokemon."""
        self.assertEqual(len(self.player.collection), 1)
        ok, msg = CompanionService.release_pokemon(self.agent, self.pikachu, self.player, self.ai_state)
        self.assertFalse(ok)
        self.assertIn("cannot release your only", msg.lower())
        self.assertIn(self.pikachu.unique_id, self.player._collection)

    def test_successful_release_when_multiple_pokemon_owned(self) -> None:
        """When player has multiple Pokemon, release authoritatively removes ownership and updates agent."""
        charmander = Pokemon(species=CHARMANDER, personality=self.personality, level=5, attacks=[EMBER])
        self.player.add_pokemon(charmander)
        self.player.add_to_team(charmander)
        self.assertEqual(len(self.player.collection), 2)

        ok, msg = CompanionService.release_pokemon(self.agent, self.pikachu, self.player, self.ai_state)
        self.assertTrue(ok)
        self.assertNotIn(self.pikachu.unique_id, self.player._collection)
        self.assertNotIn(self.pikachu, self.player.team)
        self.assertTrue(self.agent.is_wild)
        self.assertFalse(self.agent.is_captured)

        # Active Pokemon reassigned to remaining conscious teammate
        self.assertEqual(self.player.active_pokemon, charmander)


class TestCompanionBattleTactics(unittest.TestCase):
    """Tests autonomous companion tactical decisions, obedience, and character dialogue in battles (Step 7)."""

    def setUp(self) -> None:
        self.personality = Personality(aggression=50, fear=40, curiosity=60, loyalty=90, confidence=75, sociability=70)
        self.pikachu = Pokemon(species=PIKACHU, personality=self.personality, level=6, attacks=[THUNDER_SHOCK, QUICK_ATTACK])
        self.opponent = Pokemon(species=SQUIRTLE, personality=self.personality, level=5, attacks=[TACKLE])

        self.player = Player(name="Ash")
        self.player.add_pokemon(self.pikachu)
        self.player.add_to_team(self.pikachu)
        self.player.set_active_pokemon(self.pikachu)

        self.ai_state = AiState()
        self.agent = CompanionService.get_or_create_companion_agent(self.pikachu, self.ai_state, self.player)

    def test_loyal_companion_obeys_battle_command(self) -> None:
        """Loyal companion cheerfully obeys battle commands and emits cry/dialogue."""
        mock_provider = MockDecisionProvider(
            forced_decision=AgentDecision(
                action_type=AgentActionType.OBEY,
                intent="Execute Thunder Shock with precision",
                dialogue="Pika-chuuu!",
                confidence=0.95,
            )
        )

        disp = CompanionService.evaluate_battle_command(
            agent=self.agent,
            pokemon=self.pikachu,
            player=self.player,
            chosen_attack=THUNDER_SHOCK,
            opponent=self.opponent,
            provider=mock_provider,
        )

        self.assertTrue(disp.is_obedient)
        self.assertEqual(disp.chosen_attack, THUNDER_SHOCK)
        self.assertEqual(disp.action_type, AgentActionType.OBEY)
        self.assertIn("Pika-chuuu!", disp.dialogue)

    def test_battle_turn_execution_with_companion_dialogue_and_memories(self) -> None:
        """Executing attack in Battle records companion memories and emits dialogue to battle events."""
        mock_provider = MockDecisionProvider(
            forced_decision=AgentDecision(
                action_type=AgentActionType.OBEY,
                intent="Charge electricity",
                dialogue="Pika-spark!",
            )
        )

        battle = Battle(
            pokemon1=self.pikachu,
            pokemon2=self.opponent,
            player=self.player,
            player_agent=self.agent,
            ai_provider=mock_provider,
            use_random_damage=False,
            seed=10,
        )
        battle.start()

        res = battle.take_action(BattleAction(action_type=BattleActionType.ATTACK, attack=THUNDER_SHOCK))
        self.assertTrue(res.accepted)

        # Companion dialogue appeared in battle events
        dialogue_events = [e for e in battle.events if "Pika-spark!" in e]
        self.assertTrue(len(dialogue_events) > 0)

        # Memories recorded on companion
        recent_mems = [m.event_type for m in self.agent.memory.episodic.get_recent_episodes(5)]
        self.assertIn("combat_strike", recent_mems)

    def test_resentful_companion_disobeys_battle_command(self) -> None:
        """Resentful companion with negative trust disobeys and substitutes a different attack."""
        rel = self.agent.get_relationship(self.player.unique_id)
        rel.trust = -50.0
        rel.stage = RelationshipStage.RESENTFUL

        mock_provider = MockDecisionProvider(
            forced_decision=AgentDecision(
                action_type=AgentActionType.DISOBEY,
                intent="Lash out independently",
                chosen_move="Quick Attack",
                dialogue="Pika-grr! (Ignores command)",
            )
        )

        disp = CompanionService.evaluate_battle_command(
            agent=self.agent,
            pokemon=self.pikachu,
            player=self.player,
            chosen_attack=THUNDER_SHOCK,
            opponent=self.opponent,
            provider=mock_provider,
        )

        self.assertFalse(disp.is_obedient)
        self.assertEqual(disp.action_type, AgentActionType.DISOBEY)
        self.assertEqual(disp.chosen_attack, QUICK_ATTACK)


class TestWorldSchedulerAndSocialDynamics(unittest.TestCase):
    """Tests event-driven world simulation, teammate bonding, and goal updates (Step 7)."""

    def setUp(self) -> None:
        self.personality = Personality(aggression=50, fear=40, curiosity=75, loyalty=80, confidence=70, sociability=80)
        self.pikachu = Pokemon(species=PIKACHU, personality=self.personality, level=5)
        self.bulbasaur = Pokemon(species=BULBASAUR, personality=self.personality, level=5)

        self.player = Player(name="Red")
        self.player.add_pokemon(self.pikachu)
        self.player.add_pokemon(self.bulbasaur)
        self.player.add_to_team(self.pikachu)
        self.player.add_to_team(self.bulbasaur)
        self.player.set_active_pokemon(self.pikachu)

        self.ai_state = AiState()
        self.pika_agent = CompanionService.get_or_create_companion_agent(self.pikachu, self.ai_state, self.player)
        self.bulba_agent = CompanionService.get_or_create_companion_agent(self.bulbasaur, self.ai_state, self.player)

    def test_teammate_interaction_during_rest(self) -> None:
        """Teammates bond during rest, increasing mutual familiarity and recording shared memories."""
        res = CompanionService.teammate_interaction(
            agent1=self.pika_agent,
            mon1=self.pikachu,
            agent2=self.bulba_agent,
            mon2=self.bulbasaur,
            context="camping overnight",
        )

        self.assertIn("bonding", res.summary)
        rel1 = self.pika_agent.get_relationship(self.bulbasaur.unique_id)
        rel2 = self.bulba_agent.get_relationship(self.pikachu.unique_id)
        self.assertGreater(rel1.familiarity, 0)
        self.assertGreater(rel2.familiarity, 0)

    def test_scheduler_on_region_entered_progresses_exploration_goals(self) -> None:
        """Entering a region triggers observations and completes matching exploration goals."""
        self.pika_agent.goals.add_immediate_goal("Explore the forest_trail", priority=1)
        events = AutonomousWorldScheduler.on_region_entered(
            player=self.player,
            region_id="forest_trail",
            ai_state=self.ai_state,
        )

        self.assertTrue(any("forest" in e.lower() for e in events))
        # Goal marked completed
        matching_goal = next(g for g in self.pika_agent.goals.immediate_goals if "forest_trail" in g["description"])
        self.assertEqual(matching_goal["status"], "completed")

    def test_scheduler_on_landmark_discovered_records_memory(self) -> None:
        """Landmark discovery triggers awe reflection and records episodic memory."""
        events = AutonomousWorldScheduler.on_landmark_discovered(
            player=self.player,
            landmark_id="thunder_stone_shrine",
            ai_state=self.ai_state,
        )

        self.assertTrue(len(events) > 0)
        recent_mems = [m.event_type for m in self.pika_agent.memory.episodic.get_recent_episodes(5)]
        self.assertIn("landmark_discovered", recent_mems)

    def test_scheduler_on_rest_triggers_teammate_socialization(self) -> None:
        """Resting triggers teammate bonding events."""
        events = AutonomousWorldScheduler.on_rest(
            player=self.player,
            hours=8.0,
            ai_state=self.ai_state,
        )
        self.assertTrue(any("resting" in e.lower() or "bonding" in e.lower() for e in events))

    def test_ai_state_persistence_for_companion_and_teammates(self) -> None:
        """Serializing and deserializing preserves companion relationships, memories, and teammate bonds."""
        CompanionService.interact(
            agent=self.pika_agent,
            pokemon=self.pikachu,
            player=self.player,
            interaction_type="praise",
            provider=MockDecisionProvider(),
        )

        serialized = serialize_ai_state(self.ai_state)
        restored_state = deserialize_ai_state(serialized)

        restored_pika = restored_state.get_agent(self.pikachu.unique_id)
        self.assertIsNotNone(restored_pika)
        self.assertTrue(restored_pika.is_captured)
        self.assertFalse(restored_pika.is_wild)

        rel = restored_pika.get_relationship(self.player.unique_id)
        self.assertGreater(rel.trust, 30.0)
        self.assertGreater(len(restored_pika.memory.episodic.episodes), 0)


    def test_direct_natural_language_interaction_inferences(self) -> None:
        """Verifies natural language free-form player messages are correctly inferred and executed by AI."""
        # 1. Praise
        res_praise = CompanionService.interact(
            agent=self.pika_agent,
            pokemon=self.pikachu,
            player=self.player,
            interaction_type="talk",
            message="You did an amazing job out there! I'm so proud of you!",
            provider=MockDecisionProvider(),
        )
        self.assertEqual(res_praise.inferred_type, "praise")
        self.assertGreater(res_praise.affection_change, 0)
        self.assertGreater(res_praise.trust_change, 0)

        # 2. Scold
        self.pikachu.bond = 50
        res_scold = CompanionService.interact(
            agent=self.pika_agent,
            pokemon=self.pikachu,
            player=self.player,
            interaction_type="talk",
            message="That was terrible! Why did you disobey and fail like that?",
            provider=MockDecisionProvider(),
        )
        self.assertEqual(res_scold.inferred_type, "scold")
        self.assertLess(res_scold.affection_change, 0)
        self.assertLess(res_scold.trust_change, 0)

        # 3. Goals
        res_goals = CompanionService.interact(
            agent=self.pika_agent,
            pokemon=self.pikachu,
            player=self.player,
            interaction_type="talk",
            message="What are your goals and dreams for the future?",
            provider=MockDecisionProvider(),
        )
        self.assertEqual(res_goals.inferred_type, "discuss_goals")

        # 4. Release
        res_release = CompanionService.interact(
            agent=self.pika_agent,
            pokemon=self.pikachu,
            player=self.player,
            interaction_type="talk",
            message="I'm thinking of setting you free so you can return to the wild.",
            provider=MockDecisionProvider(),
        )
        self.assertEqual(res_release.inferred_type, "discuss_release")


if __name__ == "__main__":
    unittest.main()

