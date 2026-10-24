"""
Unit tests for AI-state persistence layer and agent memory architecture.
Verifies schema version validation, missing file fallbacks, malformed JSON handling,
atomic file writes, multi-tier memory preservation, and synchronization with game saves.
"""
import json
import os
import tempfile
import unittest
from pathlib import Path

from src.ai import (
    CURRENT_AI_SCHEMA_VERSION,
    SUPPORTED_AI_SCHEMA_VERSIONS,
    DEFAULT_AI_STATE_FILENAME,
    AiStateError,
    AiState,
    PokemonAgent,
    AgentIdentity,
    AgentGoals,
    AgentBeliefs,
    WorkingMemory,
    EpisodicMemory,
    MemoryEpisode,
    LongTermMemory,
    PokemonMemory,
    Relationship,
    RelationshipStage,
    validate_ai_schema_version,
    get_ai_state_path_for_save_file,
    serialize_ai_state,
    deserialize_ai_state,
    save_ai_state,
    load_ai_state,
)
from src.models.personality import Personality
from src.models.pokemon import Pokemon
from src.models.player import Player
from src.models.save_manager import (
    save_game,
    load_game,
    save_game_with_ai,
    load_game_with_ai,
    SaveManager,
)
from src.data.species import PIKACHU, CHARMANDER, SQUIRTLE
from src.data.attacks import THUNDER_SHOCK, QUICK_ATTACK, EMBER


class TestAiStateSchemaAndValidation(unittest.TestCase):
    """Tests schema validation, error handling, and version management."""

    def test_current_schema_version_supported(self) -> None:
        """CURRENT_AI_SCHEMA_VERSION is within SUPPORTED_AI_SCHEMA_VERSIONS."""
        self.assertIn(CURRENT_AI_SCHEMA_VERSION, SUPPORTED_AI_SCHEMA_VERSIONS)
        self.assertEqual(validate_ai_schema_version(CURRENT_AI_SCHEMA_VERSION), CURRENT_AI_SCHEMA_VERSION)

    def test_missing_schema_version_raises(self) -> None:
        """Missing schema_version raises AiStateError."""
        with self.assertRaises(AiStateError) as ctx:
            validate_ai_schema_version(None)
        self.assertIn("missing required 'schema_version'", str(ctx.exception))

    def test_invalid_type_schema_version_raises(self) -> None:
        """Non-integer schema_version (string, float, bool) raises AiStateError."""
        for invalid_val in ("1", 1.5, True, False, [1]):
            with self.assertRaises(AiStateError):
                validate_ai_schema_version(invalid_val)

    def test_unsupported_schema_version_raises(self) -> None:
        """Unsupported schema_version raises AiStateError with supported versions listed."""
        with self.assertRaises(AiStateError) as ctx:
            validate_ai_schema_version(999)
        self.assertIn("Unsupported AI schema version", str(ctx.exception))

    def test_get_ai_state_path_for_save_file(self) -> None:
        """Path resolution places ai_state.json co-located in the save file's directory."""
        p1 = get_ai_state_path_for_save_file("save_game.json")
        self.assertEqual(p1, Path("ai_state.json"))

        p2 = get_ai_state_path_for_save_file("saves/slot1.json")
        self.assertEqual(p2, Path("saves") / DEFAULT_AI_STATE_FILENAME)


class TestAiMemoryLayers(unittest.TestCase):
    """Tests working, episodic, and long-term memory layers."""

    def test_working_memory_bounded_capacity(self) -> None:
        """Working memory prunes recent interactions when exceeding max capacity."""
        wm = WorkingMemory(max_recent_interactions=5)
        for i in range(10):
            wm.add_interaction({"step": i, "action": f"act_{i}"})

        self.assertEqual(len(wm.recent_interactions), 5)
        self.assertEqual(wm.recent_interactions[0]["step"], 5)
        self.assertEqual(wm.recent_interactions[-1]["step"], 9)

    def test_working_memory_context_and_intention(self) -> None:
        """Immediate context and active intentions update cleanly."""
        wm = WorkingMemory()
        wm.set_immediate_context({"weather": "sunny", "location": "forest_trail"})
        wm.set_active_intention({"goal": "gather_berries", "priority": 2})

        self.assertEqual(wm.immediate_context["weather"], "sunny")
        self.assertEqual(wm.active_intention["goal"], "gather_berries")

        # Serialization round-trip
        data = wm.to_dict()
        restored = WorkingMemory.from_dict(data)
        self.assertEqual(restored.immediate_context, wm.immediate_context)
        self.assertEqual(restored.active_intention, wm.active_intention)

    def test_episodic_memory_recording_and_significance_pruning(self) -> None:
        """Episodic memory preserves emotionally impactful episodes during pruning."""
        em = EpisodicMemory(max_episodes=3)
        # Low impact episodes
        em.record_episode("routine", "saw a Pidgey", emotional_impact=0.1)
        em.record_episode("routine", "walked along road", emotional_impact=0.0)
        # High impact episode
        heroic_ep = em.record_episode("battle_victory", "Defeated rival gym leader", emotional_impact=0.95)
        # Another episode triggering prune
        em.record_episode("routine", "found an apple", emotional_impact=0.05)

        self.assertEqual(len(em.episodes), 3)
        # The heroic episode must be preserved due to high emotional impact
        episode_ids = [e.episode_id for e in em.episodes]
        self.assertIn(heroic_ep.episode_id, episode_ids)

    def test_long_term_memory(self) -> None:
        """Preferences, learned tendencies, and persistent goals are preserved."""
        ltm = LongTermMemory()
        ltm.set_preference("favorite_berry", "oran")
        ltm.add_learned_tendency("wary of wild electric types")
        ltm.add_persistent_goal({"goal": "become champion", "motivation": "prove strength"})

        data = ltm.to_dict()
        restored = LongTermMemory.from_dict(data)
        self.assertEqual(restored.preferences["favorite_berry"], "oran")
        self.assertIn("wary of wild electric types", restored.learned_tendencies)
        self.assertEqual(len(restored.persistent_goals), 1)


class TestAiRelationships(unittest.TestCase):
    """Tests relationship dynamics, metric adjustments, and stage transitions."""

    def test_relationship_clamping_and_initial_stage(self) -> None:
        """Relationship metrics clamp to [-100, 100] and default to STRANGER stage."""
        rel = Relationship(entity_id="trainer_1", entity_name="Ash", trust=200.0, affection=-150.0)
        self.assertEqual(rel.trust, 100.0)
        self.assertEqual(rel.affection, -100.0)

    def test_stage_transitions(self) -> None:
        """Relationship stage updates dynamically as trust and affection evolve."""
        rel = Relationship(entity_id="trainer_1", entity_name="Ash")
        self.assertEqual(rel.stage, RelationshipStage.STRANGER)

        # Build acquaintance
        rel.adjust_familiarity(20.0)
        rel.adjust_trust(15.0)
        rel.adjust_affection(15.0)
        self.assertEqual(rel.stage, RelationshipStage.ACQUAINTANCE)

        # Build companion
        rel.adjust_familiarity(30.0)
        rel.adjust_trust(30.0)
        rel.adjust_affection(30.0)
        self.assertEqual(rel.stage, RelationshipStage.COMPANION)

        # Deep devotion
        rel.adjust_familiarity(40.0)
        rel.adjust_trust(40.0)
        rel.adjust_affection(40.0)
        self.assertEqual(rel.stage, RelationshipStage.DEVOTED)

        # Severe betrayal causes resentment
        rel.adjust_trust(-150.0)
        rel.adjust_affection(-150.0)
        self.assertEqual(rel.stage, RelationshipStage.RESENTFUL)


class TestPokemonAgent(unittest.TestCase):
    """Tests PokemonAgent creation, state tracking, and serialization."""

    def setUp(self) -> None:
        self.pers = Personality(aggression=80, curiosity=30, fear=20, sociability=40, loyalty=90, confidence=85)
        self.charm = Pokemon(species=CHARMANDER, personality=self.pers, level=5, attacks=[EMBER])

    def test_create_from_pokemon(self) -> None:
        """Factory creates an agent matching Pokemon unique ID, species, and personality traits."""
        agent = PokemonAgent.from_pokemon(self.charm, is_wild=True)
        self.assertEqual(agent.agent_id, self.charm.unique_id)
        self.assertEqual(agent.species, "Charmander")
        self.assertEqual(agent.identity.temperament, "aggressive")
        self.assertTrue(agent.is_wild)
        self.assertFalse(agent.is_captured)

    def test_agent_serialization_round_trip(self) -> None:
        """PokemonAgent serializes to dict and reconstructs identically."""
        agent = PokemonAgent.from_pokemon(self.charm, is_wild=False, is_captured=True)
        agent.goals.add_immediate_goal("protect trainer", priority=1)
        agent.beliefs.add_world_belief("humans can be trustworthy")
        agent.record_experience("first_battle", "Fought bravely against wild Pidgey", emotional_impact=0.6)

        rel = agent.get_relationship("trainer_ash", default_name="Ash")
        rel.adjust_trust(40.0)
        rel.adjust_affection(35.0)
        rel.adjust_familiarity(30.0)

        data = agent.to_dict()
        restored = PokemonAgent.from_dict(data)

        self.assertEqual(restored.agent_id, agent.agent_id)
        self.assertEqual(restored.species, agent.species)
        self.assertEqual(restored.identity.temperament, agent.identity.temperament)
        self.assertFalse(restored.is_wild)
        self.assertTrue(restored.is_captured)
        self.assertEqual(len(restored.goals.immediate_goals), 1)
        self.assertIn("humans can be trustworthy", restored.beliefs.world_beliefs)
        self.assertEqual(len(restored.memory.episodic.episodes), 1)
        self.assertEqual(restored.relationships["trainer_ash"].stage, RelationshipStage.COMPANION)


class TestAiStatePersistence(unittest.TestCase):
    """Tests atomic file persistence, missing file handling, and error recovery."""

    def setUp(self) -> None:
        self.pers = Personality(50, 50, 50, 50, 50, 50)
        self.pika = Pokemon(species=PIKACHU, personality=self.pers, level=5, attacks=[THUNDER_SHOCK])
        self.squirtle = Pokemon(species=SQUIRTLE, personality=self.pers, level=5)

    def test_missing_file_without_create_raises(self) -> None:
        """load_ai_state raises AiStateError if file not found and create_if_missing=False."""
        non_existent = Path("non_existent_ai_state.json")
        with self.assertRaises(AiStateError) as ctx:
            load_ai_state(non_existent, create_if_missing=False)
        self.assertIn("not found", str(ctx.exception))

    def test_missing_file_with_create_returns_fresh_state(self) -> None:
        """load_ai_state with create_if_missing=True returns a valid empty AiState."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "ai_state.json"
            state = load_ai_state(file_path, create_if_missing=True)
            self.assertIsInstance(state, AiState)
            self.assertEqual(len(state.agents), 0)
            self.assertEqual(state.schema_version, CURRENT_AI_SCHEMA_VERSION)

    def test_malformed_json_raises_ai_state_error(self) -> None:
        """Corrupted JSON syntax in ai_state.json raises AiStateError."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            bad_file = Path(tmp_dir) / "ai_state.json"
            with open(bad_file, "w", encoding="utf-8") as f:
                f.write("{ invalid json string :::: 123 }")

            with self.assertRaises(AiStateError) as ctx:
                load_ai_state(bad_file)
            self.assertIn("Invalid JSON", str(ctx.exception))

    def test_corrupted_agents_payload_raises_ai_state_error(self) -> None:
        """Invalid schema payload structure raises AiStateError."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            bad_file = Path(tmp_dir) / "ai_state.json"
            # 'agents' should be a dict, provide a string
            with open(bad_file, "w", encoding="utf-8") as f:
                json.dump({"schema_version": 1, "agents": "invalid_string"}, f)

            with self.assertRaises(AiStateError) as ctx:
                load_ai_state(bad_file)
            self.assertIn("Field 'agents' must be a dictionary", str(ctx.exception))

    def test_atomic_save_and_load_round_trip(self) -> None:
        """AiState with multiple agents saves atomically and loads with complete fidelity."""
        state = AiState(metadata={"game_version": "Syntax Error 26"})
        agent1 = state.get_or_create_agent(self.pika, is_wild=False, is_captured=True)
        agent2 = state.get_or_create_agent(self.squirtle, is_wild=True)

        agent1.memory.working.set_immediate_context({"area": "viridian_forest"})
        agent1.record_experience("captured", "Caught in a Poke Ball", emotional_impact=0.4)

        with tempfile.TemporaryDirectory() as tmp_dir:
            target_path = Path(tmp_dir) / "subfolder" / "ai_state.json"
            save_ai_state(state, target_path)

            self.assertTrue(target_path.exists())
            self.assertTrue(target_path.is_file())

            loaded_state = load_ai_state(target_path)
            self.assertEqual(loaded_state.schema_version, CURRENT_AI_SCHEMA_VERSION)
            self.assertEqual(len(loaded_state.agents), 2)
            self.assertIn(self.pika.unique_id, loaded_state.agents)
            self.assertIn(self.squirtle.unique_id, loaded_state.agents)

            loaded_agent1 = loaded_state.get_agent(self.pika.unique_id)
            self.assertIsNotNone(loaded_agent1)
            self.assertTrue(loaded_agent1.is_captured)
            self.assertEqual(loaded_agent1.memory.working.immediate_context["area"], "viridian_forest")
            self.assertEqual(len(loaded_agent1.memory.episodic.episodes), 1)

    def test_sync_with_player_collection(self) -> None:
        """sync_with_player_collection registers agents for all player Pokemon and links relationship."""
        player = Player(name="Red")
        player.add_pokemon(self.pika)
        player.add_pokemon(self.squirtle)
        self.pika.bond = 40

        state = AiState()
        self.assertEqual(len(state.agents), 0)

        state.sync_with_player_collection(player)

        # Both Pokemon now registered
        self.assertEqual(len(state.agents), 2)
        pika_agent = state.get_agent(self.pika.unique_id)
        self.assertIsNotNone(pika_agent)
        self.assertTrue(pika_agent.is_captured)

        # Relationship established and bond transferred
        rel = pika_agent.relationships[player.unique_id]
        self.assertEqual(rel.entity_name, "Red")
        self.assertEqual(rel.entity_type, "trainer")
        self.assertGreater(rel.familiarity, 0)
        self.assertGreater(rel.trust, 0)

    def test_save_manager_integration(self) -> None:
        """SaveManager.save_with_ai and load_with_ai synchronize and persist both save files cleanly."""
        player = Player(name="Ash")
        player.add_pokemon(self.pika)
        player.add_to_team(self.pika)

        ai_state = AiState()
        ai_state.sync_with_player_collection(player)
        agent = ai_state.get_agent(self.pika.unique_id)
        agent.goals.add_immediate_goal("master thunder shock", priority=1)

        with tempfile.TemporaryDirectory() as tmp_dir:
            save_path = Path(tmp_dir) / "save_game.json"
            ai_path = Path(tmp_dir) / "ai_state.json"

            # Save both
            SaveManager.save_with_ai(player, save_path, ai_state=ai_state, ai_state_path=ai_path)
            self.assertTrue(save_path.exists())
            self.assertTrue(ai_path.exists())

            # Load both
            loaded_player, loaded_ai = SaveManager.load_with_ai(
                path=save_path,
                ai_state_path=ai_path,
            )
            self.assertEqual(loaded_player.name, "Ash")
            self.assertIn(self.pika.unique_id, loaded_ai.agents)
            loaded_agent = loaded_ai.get_agent(self.pika.unique_id)
            self.assertEqual(len(loaded_agent.goals.immediate_goals), 1)
            self.assertEqual(loaded_agent.goals.immediate_goals[0]["description"], "master thunder shock")

    def test_adventure_game_save_load_ai_state_integration(self) -> None:
        """AdventureGame saves and loads companion ai_state.json alongside save_game.json."""
        from game import AdventureGame

        with tempfile.TemporaryDirectory() as tmp_dir:
            save_path = Path(tmp_dir) / "test_adventure_save.json"
            ai_path = Path(tmp_dir) / "ai_state.json"

            # 1. Start new game and save
            game = AdventureGame(save_file=str(save_path))
            game.player = Player(name="Red")
            game.player.add_pokemon(self.pika)
            game.player.add_to_team(self.pika)
            game.player.set_active_pokemon(self.pika)

            # Sync AI state and add an agent goal
            game.ai_state.sync_with_player_collection(game.player)
            agent = game.ai_state.get_agent(self.pika.unique_id)
            self.assertIsNotNone(agent)
            agent.goals.add_immediate_goal("explore tall grass", priority=2)

            # Save through game loop action
            game._action_save()
            self.assertTrue(save_path.exists())
            self.assertTrue(ai_path.exists())

            # 2. Re-load game through game load flow
            game2 = AdventureGame(save_file=str(save_path))
            loaded_success = game2._load_game_flow()
            self.assertTrue(loaded_success)
            self.assertIsNotNone(game2.player)
            self.assertEqual(game2.player.name, "Red")

            # Verify AI state loaded and matches
            self.assertIsNotNone(game2.ai_state)
            loaded_agent = game2.ai_state.get_agent(self.pika.unique_id)
            self.assertIsNotNone(loaded_agent)
            self.assertEqual(len(loaded_agent.goals.immediate_goals), 1)
            self.assertEqual(loaded_agent.goals.immediate_goals[0]["description"], "explore tall grass")


if __name__ == "__main__":
    unittest.main()
