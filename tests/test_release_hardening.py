"""
Release readiness audit, regression tests, and lifecycle hardening for Syntax Error 2026.

Verifies:
1. Subsystem session isolation and world object reset between game runs.
2. Quest event emission on in-battle captures (POKEMON_CAPTURED and POKEMON_COLLECTED).
3. Trainer battle auto-switching when opponent Pokemon faints from status effects during player switch.
4. Exploration safety and team management safeguards when team is fainted.
5. Save/load edge cases: empty files, invalid JSON, unsupported schema versions, duplicate collection IDs.
6. Safe waypoint positioning on save restore without persisting volatile in-step coordinates.
7. Schema 1-4 migration integrity and idempotence.
"""
import io
import json
import os
import tempfile
import unittest

from src.models.personality import Personality
from src.models.pokemon import Pokemon
from src.models.pokemon_type import PokemonType
from src.models.attack import Attack
from src.models.player import Player
from src.models.battle_state import BattleState
from src.models.battle import Battle, BattleAction, BattleActionType
from src.models.battle_manager import BattleManager
from src.models.spawn_area import SpawnArea
from src.models.spawn_manager import SpawnManager
from src.models.encounter_manager import EncounterManager
from src.models.capture_manager import CaptureManager
from src.models.quest_manager import QuestManager
from src.models.quest import QuestStatus, QuestEventType
from src.models.status_effect import StatusEffectType, StatusEffect
from src.models.status_effect_manager import StatusEffectManager
from src.models.save_manager import save_game, load_game, serialize_player, deserialize_player, CURRENT_SCHEMA_VERSION, SaveDataError
from src.data.species import PIKACHU, CHARMANDER, SQUIRTLE
from src.data.attacks import THUNDER_SHOCK, QUICK_ATTACK, EMBER, SCRATCH, WATER_GUN, TACKLE
from src.data.quests import FIRST_ENCOUNTER, WILD_CHALLENGER
from game import AdventureGame


class TestReleaseHardening(unittest.TestCase):
    """Release readiness and regression audit suite."""

    def setUp(self) -> None:
        self.personality = Personality(50, 50, 50, 50, 50, 50)
        self.pika = Pokemon(species=PIKACHU, personality=self.personality, level=5, attacks=[THUNDER_SHOCK, QUICK_ATTACK])
        self.charm = Pokemon(species=CHARMANDER, personality=self.personality, level=5, attacks=[EMBER, SCRATCH])
        self.squirt = Pokemon(species=SQUIRTLE, personality=self.personality, level=5, attacks=[WATER_GUN, TACKLE])

        self.player = Player(name="Ash")
        self.player.add_pokemon(self.pika)
        self.player.add_to_team(self.pika)
        self.player.set_active_pokemon(self.pika)

    # --- Defect 1: Subsystem State Leak Across Game Sessions ---

    def test_01_subsystem_session_isolation_resets_world_objects(self) -> None:
        """New game sessions must create fresh world objects and not retain depleted nodes."""
        input_stream = iter(["Ash", "1", "quit"])
        output_lines: list[str] = []

        game = AdventureGame(
            input_fn=lambda prompt="": next(input_stream),
            output_fn=lambda *args, **kwargs: output_lines.append(" ".join(str(a) for a in args)),
        )

        # 1. Start a game session and deplete a resource node
        game._start_new_game()
        bush = game.world_interaction_manager.get_object("berry_bush_route1")
        self.assertIsNotNone(bush)
        res = game.world_interaction_manager.interact(game.player, "berry_bush_route1", [5.0, 5.0], current_time=0.0)
        self.assertTrue(res.success)
        self.assertFalse(bush.is_available)

        # 2. Start a new game session on the same game instance
        input_stream = iter(["Gary", "2", "quit"])
        game._start_new_game()

        new_bush = game.world_interaction_manager.get_object("berry_bush_route1")
        self.assertIsNotNone(new_bush)
        # In the new session, the bush must be fresh and available
        self.assertTrue(new_bush.is_available)
        self.assertEqual(game.player.name, "Gary")

    # --- Defect 2: Opponent Trainer KO on Status Phase during Player Switch ---

    def test_02_trainer_battle_auto_switch_on_status_ko_during_switch(self) -> None:
        """Opponent trainer must auto-switch if active Pokemon faints from status effects on switch."""
        opp_mon1 = Pokemon(species=CHARMANDER, personality=self.personality, level=5, attacks=[EMBER])
        opp_mon2 = Pokemon(species=SQUIRTLE, personality=self.personality, level=5, attacks=[WATER_GUN])

        opponent = Player(name="Rival")
        opponent.add_pokemon(opp_mon1)
        opponent.add_pokemon(opp_mon2)
        opponent.add_to_team(opp_mon1)
        opponent.add_to_team(opp_mon2)
        opponent.set_active_pokemon(opp_mon1)

        # Player has 2 Pokemon: Pika (active) and Squirtle (benched)
        self.player.add_pokemon(self.squirt)
        self.player.add_to_team(self.squirt)

        battle = Battle(
            pokemon1=self.pika,
            pokemon2=opp_mon1,
            player=self.player,
            opponent_trainer=opponent,
            player_team=self.player.team,
            opponent_team=opponent.team,
            seed=42,
        )
        battle.start()

        # Poison opp_mon1 and drop HP to 1 so status phase KO's it
        opp_mon1.current_hp = 1
        battle.status_manager.apply_effect(opp_mon1, StatusEffectType.POISON)

        # Player switches to benched Squirtle
        switch_res = battle.take_action(BattleAction(action_type=BattleActionType.SWITCH, target_pokemon=self.squirt))

        self.assertTrue(switch_res.accepted)
        self.assertTrue(opp_mon1.is_fainted)
        # Opponent should automatically switch in opp_mon2 (Squirtle)
        self.assertIs(battle.pokemon2, opp_mon2)
        self.assertIs(opponent.active_pokemon, opp_mon2)
        # Battle should not be terminated because opponent has conscious teammates
        self.assertEqual(battle.state, BattleState.IN_PROGRESS)
        self.assertFalse(switch_res.terminal)

    # --- Defect 3: Quest Events on In-Battle Capture ---

    def test_03_in_battle_capture_emits_quest_events(self) -> None:
        """Capturing a Pokemon in battle must dispatch POKEMON_CAPTURED and advance capture quests."""
        quest_manager = QuestManager()
        capture_manager = CaptureManager(seed=42)
        battle_manager = BattleManager(
            capture_manager=capture_manager,
            quest_manager=quest_manager,
        )

        # Player accepts First Encounter quest (objective: capture_any)
        accept_res = quest_manager.accept_quest(self.player, FIRST_ENCOUNTER.quest_id)
        self.assertTrue(accept_res.success)
        quest_prog = quest_manager.get_quest_progress(self.player, FIRST_ENCOUNTER.quest_id)
        self.assertEqual(quest_prog.objective_progress["capture_first_pokemon"].current_count, 0)

        # Wild battle with low HP Charmander to guarantee high capture chance
        self.charm.current_hp = 1
        battle = battle_manager.start_battle(self.player, self.charm, seed=42)

        # Force deterministic capture success by setting high capture prob floor or 100% chance
        cap_res = battle_manager.attempt_capture(self.player, capture_manager=CaptureManager(seed=1, min_probability=1.0))

        self.assertTrue(cap_res.accepted)
        self.assertTrue(cap_res.captured)
        self.assertEqual(battle.state, BattleState.CAPTURED)

        # Verify quest advanced and completed
        self.assertEqual(quest_prog.objective_progress["capture_first_pokemon"].current_count, 1)
        self.assertTrue(quest_prog.is_completed)

    # --- Defect 4: All-Fainted Team Refusal in Exploration & Manage Team ---

    def test_04_all_fainted_team_exploration_safety(self) -> None:
        """Exploring with an all-fainted team must be rejected with a user-facing warning."""
        output_lines: list[str] = []
        game = AdventureGame(
            input_fn=lambda prompt="": "quit",
            output_fn=lambda *args, **kwargs: output_lines.append(" ".join(str(a) for a in args)),
        )
        game.player = self.player
        # Faint player's active Pokemon
        self.pika.take_damage(self.pika.max_hp)
        self.assertTrue(self.pika.is_fainted)

        # Trigger explore
        game._action_explore()

        # Exploration should be rejected without errors
        output_text = "\n".join(output_lines)
        self.assertIn("All Pokemon on your team have fainted", output_text)
        self.assertIn("Heal your team with items or rest", output_text)

    def test_05_cannot_set_fainted_pokemon_active(self) -> None:
        """Setting a fainted Pokemon as active in team management is rejected."""
        # Add a healthy Squirtle and faint Pikachu
        self.player.add_pokemon(self.squirt)
        self.player.add_to_team(self.squirt)
        self.player.set_active_pokemon(self.squirt)
        self.pika.take_damage(self.pika.max_hp)

        output_lines: list[str] = []
        # Input: [1] Set Active, [1] (which is Pikachu), [0] (Back to main menu)
        input_stream = iter(["1", "1", "0"])
        game = AdventureGame(
            input_fn=lambda prompt="": next(input_stream),
            output_fn=lambda *args, **kwargs: output_lines.append(" ".join(str(a) for a in args)),
        )
        game.player = self.player
        game._action_manage_team()

        output_text = "\n".join(output_lines)
        self.assertIn("has fainted and cannot be set as your active partner", output_text)
        self.assertIs(self.player.active_pokemon, self.squirt)

    # --- Save/Load Integrity & Edge Cases ---

    def test_06_save_load_empty_or_whitespace_file_rejected(self) -> None:
        """Empty or whitespace-only save files must raise SaveDataError."""
        with tempfile.NamedTemporaryFile("w", delete=False) as tf:
            tf.write("   \n\t  ")
            tf_path = tf.name

        try:
            with self.assertRaises(SaveDataError) as ctx:
                load_game(tf_path)
            self.assertIn("invalid json", str(ctx.exception).lower())
        finally:
            if os.path.exists(tf_path):
                os.remove(tf_path)

    def test_07_save_load_corrupt_json_rejected(self) -> None:
        """Malformed JSON must raise SaveDataError with descriptive message."""
        with tempfile.NamedTemporaryFile("w", delete=False) as tf:
            tf.write("{bad json: missing quotes,")
            tf_path = tf.name

        try:
            with self.assertRaises(SaveDataError) as ctx:
                load_game(tf_path)
            self.assertIn("invalid json", str(ctx.exception).lower())
        finally:
            if os.path.exists(tf_path):
                os.remove(tf_path)

    def test_08_save_load_missing_schema_version_rejected(self) -> None:
        """Save payload lacking schema_version must raise SaveDataError."""
        with tempfile.NamedTemporaryFile("w", delete=False) as tf:
            json.dump({"player": {"name": "Ash"}}, tf)
            tf_path = tf.name

        try:
            with self.assertRaises(SaveDataError) as ctx:
                load_game(tf_path)
            self.assertIn("schema_version", str(ctx.exception))
        finally:
            if os.path.exists(tf_path):
                os.remove(tf_path)

    def test_09_save_load_future_schema_version_rejected(self) -> None:
        """Save payload with an unsupported future schema version must raise SaveDataError."""
        with tempfile.NamedTemporaryFile("w", delete=False) as tf:
            json.dump({"schema_version": 99, "player": {"name": "Ash"}}, tf)
            tf_path = tf.name

        try:
            with self.assertRaises(SaveDataError) as ctx:
                load_game(tf_path)
            self.assertIn("unsupported schema version", str(ctx.exception).lower())
        finally:
            if os.path.exists(tf_path):
                os.remove(tf_path)

    def test_10_save_load_duplicate_collection_ids_rejected(self) -> None:
        """Collection with duplicate Pokemon unique IDs must be rejected by SaveData."""
        save_dict = {
            "schema_version": CURRENT_SCHEMA_VERSION,
            "player": {"name": "Ash", "unique_id": "player-ash-001", "max_team_size": 6},
            "inventory": {"capacity": 20, "items": {}},
            "collection": [
                {
                    "unique_id": "dup-id-123",
                    "species": "Pikachu",
                    "level": 5,
                    "personality": {"aggression": 50, "curiosity": 50, "fear": 50, "sociability": 50, "loyalty": 50, "confidence": 50},
                    "attacks": ["Thunder Shock"],
                },
                {
                    "unique_id": "dup-id-123",
                    "species": "Charmander",
                    "level": 5,
                    "personality": {"aggression": 50, "curiosity": 50, "fear": 50, "sociability": 50, "loyalty": 50, "confidence": 50},
                    "attacks": ["Scratch"],
                },
            ],
            "team": ["dup-id-123"],
            "quests": {},
            "collected_treasures": [],
            "discovered_regions": [],
            "discovered_landmarks": [],
        }
        with tempfile.NamedTemporaryFile("w", delete=False) as tf:
            json.dump(save_dict, tf)
            tf_path = tf.name

        try:
            with self.assertRaises(SaveDataError) as ctx:
                load_game(tf_path)
            self.assertIn("duplicate pokemon id", str(ctx.exception).lower())
        finally:
            if os.path.exists(tf_path):
                os.remove(tf_path)

    def test_11_safe_waypoint_restoration_on_load(self) -> None:
        """Loaded games reset volatile clock to midday and position player at safe region waypoint."""
        self.player.mark_region_discovered("forest_trail")
        self.player.mark_region_discovered("starting_meadow")

        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as tf:
            tf_path = tf.name

        try:
            save_game(self.player, tf_path)
            output_lines: list[str] = []
            game = AdventureGame(
                input_fn=lambda prompt="": "quit",
                output_fn=lambda *args, **kwargs: output_lines.append(" ".join(str(a) for a in args)),
                save_file=tf_path,
            )

            loaded = game._load_game_flow()
            self.assertTrue(loaded)
            # Position should be at forest trail waypoint (15.0, 10.0)
            self.assertEqual(game.current_region_id, "forest_trail")
            self.assertEqual(game.player_pos, [15.0, 10.0])
            # Clock resets cleanly to safe daytime (12.0)
            self.assertEqual(game.game_hour, 12.0)
            self.assertEqual(game.elapsed_seconds, 0.0)
        finally:
            if os.path.exists(tf_path):
                os.remove(tf_path)

    def test_12_schema_v1_migration_to_v4(self) -> None:
        """Schema v1 saves migrate cleanly to Schema v4 with default discoveries and treasures."""
        v1_data = {
            "schema_version": 1,
            "player": {"name": "Red", "unique_id": "player-red-001", "max_team_size": 6},
            "inventory": {"capacity": 20, "items": {}},
            "collection": [
                {
                    "unique_id": "mon-1",
                    "species": "Pikachu",
                    "level": 5,
                    "personality": {"aggression": 50, "curiosity": 50, "fear": 50, "sociability": 50, "loyalty": 50, "confidence": 50},
                    "attacks": ["Thunder Shock"],
                }
            ],
            "team": ["mon-1"],
        }
        with tempfile.NamedTemporaryFile("w", delete=False) as tf:
            json.dump(v1_data, tf)
            tf_path = tf.name

        try:
            loaded = load_game(tf_path)
            self.assertEqual(loaded.name, "Red")
            self.assertEqual(len(loaded.team), 1)
            # Migrated fields
            self.assertEqual(loaded.discovered_regions, set())
            self.assertEqual(loaded.discovered_landmarks, set())
            self.assertEqual(loaded.collected_treasures, set())
            self.assertEqual(loaded.quests, {})
        finally:
            if os.path.exists(tf_path):
                os.remove(tf_path)

    # --- Battle Manager Idempotence & Boundary Checks ---

    def test_13_resolve_battle_idempotent_and_safe(self) -> None:
        """resolve_battle safely returns None on subsequent calls without side effects."""
        bm = BattleManager()
        battle = bm.start_battle(self.player, self.charm)
        self.assertTrue(bm.has_active_battle(self.player))

        # First resolution
        res1 = bm.resolve_battle(self.player, reason="Test resolve")
        self.assertIsNotNone(res1)
        self.assertFalse(bm.has_active_battle(self.player))

        # Second resolution is a safe no-op
        res2 = bm.resolve_battle(self.player, reason="Test resolve again")
        self.assertIsNone(res2)


if __name__ == "__main__":
    unittest.main()
