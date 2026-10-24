"""
Unit and integration tests for Phase C1: Quest Givers and Quest Discovery.
Verifies NPC models, dialogue retrieval, world interaction integration,
quest discovery and acceptance/declining, missing prerequisite feedback,
objective progress reporting, unclaimed reward reminders, and full gameplay journeys.
"""
import unittest
import tempfile
import os

from src.models.player import Player
from src.models.pokemon import Pokemon
from src.models.personality import Personality
from src.models.inventory import Inventory
from src.models.quest import QuestStatus, QuestProgress, ObjectiveProgress
from src.models.quest_manager import QuestManager
from src.models.npc import NPC
from src.data.npcs import (
    PROFESSOR_OAK,
    BATTLE_SCOUT,
    TRAIL_RANGER,
    SUPPLY_CLERK,
    NPC_CATALOG,
    get_npc,
    list_catalog_npcs,
    create_default_npcs,
)
from src.models.world_interaction import Interactable, InteractableType, InteractionResult
from src.models.world_interaction_manager import WorldInteractionManager
from src.data.world_objects import (
    BERRY_BUSH,
    SUPPLY_CACHE,
    ROUTE1_SIGN,
    ANCIENT_SHRINE,
    NPC_PROF_OAK,
    NPC_BATTLE_SCOUT,
    NPC_TRAIL_RANGER,
    NPC_SUPPLY_CLERK,
    WORLD_OBJECT_CATALOG,
    create_default_world_objects,
)
from src.data.species import PIKACHU, CHARMANDER, SQUIRTLE
from src.models.save_manager import save_game, load_game
from game import AdventureGame


def create_test_pokemon(species=PIKACHU, level=5) -> Pokemon:
    personality = Personality(
        aggression=30, curiosity=50, fear=20, sociability=70, loyalty=80, confidence=60
    )
    return Pokemon(species=species, personality=personality, level=level)


class TestQuestGivers(unittest.TestCase):
    """Exhaustive test suite for Phase C1: Quest Givers and Quest Discovery."""

    def setUp(self) -> None:
        self.player = Player(name="Red", inventory=Inventory(capacity=20))
        mon = create_test_pokemon(PIKACHU, level=5)
        self.player.add_pokemon(mon)
        self.player.add_to_team(mon)
        self.quest_mgr = QuestManager()
        self.interaction_mgr = WorldInteractionManager(quest_manager=self.quest_mgr)

    # 1. NPC Model validation and distance/range calculations
    def test_01_npc_model_validation_and_range(self) -> None:
        """NPC validates attributes, positions, and calculates Euclidean distances accurately."""
        npc = NPC(
            npc_id="guide_steve",
            name="Guide Steve",
            title="Trail Guide",
            description="A friendly guide.",
            position=(10.0, 10.0),
            interaction_radius=2.0,
            offered_quest_ids=("first_encounter",),
            dialogue={"greeting": "Hello traveller!"},
        )
        self.assertEqual(npc.npc_id, "guide_steve")
        self.assertEqual(npc.name, "Guide Steve")
        self.assertEqual(npc.title, "Trail Guide")
        self.assertEqual(npc.position, (10.0, 10.0))
        self.assertEqual(npc.interaction_radius, 2.0)
        self.assertEqual(npc.offered_quest_ids, ("first_encounter",))

        # Within range
        self.assertTrue(npc.is_in_range((10.5, 11.0)))
        self.assertAlmostEqual(npc.distance_to((10.0, 10.0)), 0.0)

        # Outside range
        self.assertFalse(npc.is_in_range((10.0, 15.0)))
        self.assertGreater(npc.distance_to((10.0, 15.0)), 2.0)

        # Rejects invalid coordinates
        with self.assertRaises(ValueError):
            NPC("id", "Name", "Title", "Desc", position=("bad", 1.0))
        with self.assertRaises(ValueError):
            NPC("id", "Name", "Title", "Desc", position=(0.0, 0.0), interaction_radius=-1.0)

    # 2. Dialogue retrieval and priority fallback
    def test_02_dialogue_retrieval_and_fallbacks(self) -> None:
        """NPC dialogue handles specific quest keys, dialogue types, and defaults."""
        npc = PROFESSOR_OAK
        # Greeting
        self.assertIn("young Trainer", npc.get_dialogue("greeting"))
        # Specific quest offer
        self.assertIn("practical field experience", npc.get_quest_dialogue("first_encounter", "offer"))
        # Specific locked dialogue
        self.assertIn("foundational capture experience", npc.get_quest_dialogue("species_research", "locked"))
        # Fallback to generic offer
        self.assertEqual(npc.get_quest_dialogue("unknown_quest", "offer"), npc.dialogue["offer"])
        # Custom default fallback
        self.assertEqual(npc.get_quest_dialogue("unknown_quest", "custom_type", "Default text"), "Default text")

    # 3. Catalog reachability and regional placement
    def test_03_catalog_reachability_and_coordinates(self) -> None:
        """All 4 catalog NPCs exist, map to valid quests, and are reachable near waypoints."""
        npcs = list_catalog_npcs()
        self.assertEqual(len(npcs), 4)

        oak = get_npc("prof_oak")
        self.assertIsNotNone(oak)
        self.assertEqual(oak.offered_quest_ids, ("first_encounter", "species_research", "research_specialization"))

        koji = get_npc("battle_scout")
        self.assertIsNotNone(koji)
        self.assertEqual(koji.offered_quest_ids, ("wild_challenger", "growing_stronger"))

        logan = get_npc("trail_ranger")
        self.assertIsNotNone(logan)
        self.assertEqual(logan.offered_quest_ids, ("trailblazer", "shrine_investigation"))

        maya = get_npc("supply_clerk")
        self.assertIsNotNone(maya)
        self.assertEqual(maya.offered_quest_ids, ("stocking_supplies", "collectors_pride"))

        # Verify all offered quests exist in QUEST_CATALOG
        for npc in npcs:
            for q_id in npc.offered_quest_ids:
                self.assertIsNotNone(
                    self.quest_mgr.get_quest_definition(q_id),
                    f"Quest '{q_id}' offered by {npc.name} must exist in QUEST_CATALOG",
                )

    # 4. World interaction index stability (Indices 1 to 4 preserved)
    def test_04_world_object_index_stability(self) -> None:
        """World object catalog preserves Berry Bush, Supply Cache, Sign, and Shrine as first 4 items."""
        default_objs = create_default_world_objects()
        self.assertGreaterEqual(len(default_objs), 8)

        # Indices 0 to 3 (Menu 1 to 4)
        self.assertEqual(default_objs[0].object_id, "berry_bush_route1")
        self.assertEqual(default_objs[0].interactable_type, InteractableType.RESOURCE_NODE)

        self.assertEqual(default_objs[1].object_id, "supply_cache_01")
        self.assertEqual(default_objs[1].interactable_type, InteractableType.TREASURE)

        self.assertEqual(default_objs[2].object_id, "route1_sign")
        self.assertEqual(default_objs[2].interactable_type, InteractableType.SIGN)

        self.assertEqual(default_objs[3].object_id, "ancient_shrine")
        self.assertEqual(default_objs[3].interactable_type, InteractableType.LANDMARK)

        # Indices 4 to 7 (Menu 5 to 8) are NPCs
        self.assertEqual(default_objs[4].object_id, "npc_prof_oak")
        self.assertEqual(default_objs[4].interactable_type, InteractableType.NPC)
        self.assertEqual(default_objs[4].npc_id, "prof_oak")

        self.assertEqual(default_objs[5].object_id, "npc_battle_scout")
        self.assertEqual(default_objs[5].interactable_type, InteractableType.NPC)

        self.assertEqual(default_objs[6].object_id, "npc_trail_ranger")
        self.assertEqual(default_objs[6].interactable_type, InteractableType.NPC)

        self.assertEqual(default_objs[7].object_id, "npc_supply_clerk")
        self.assertEqual(default_objs[7].interactable_type, InteractableType.NPC)

    # 5. WorldInteractionManager NPC interaction has zero side effects
    def test_05_npc_interaction_zero_side_effects(self) -> None:
        """Interacting with an NPC grants 0 items, triggers no cooldowns, and is repeatable."""
        # Player standing next to Professor Oak at (2.5, 1.5)
        player_pos = (2.5, 1.5)
        result1 = self.interaction_mgr.interact(
            player=self.player,
            object_id="npc_prof_oak",
            player_position=player_pos,
        )
        self.assertTrue(result1.success)
        self.assertEqual(result1.interactable_type, InteractableType.NPC)
        self.assertEqual(result1.npc_id, "prof_oak")
        self.assertEqual(len(result1.items_granted), 0)
        self.assertIsNone(result1.respawn_deadline)
        self.assertIn("Spoke with Professor Oak", result1.message)

        # Repeating interaction immediately succeeds
        result2 = self.interaction_mgr.interact(
            player=self.player,
            object_id="npc_prof_oak",
            player_position=player_pos,
        )
        self.assertTrue(result2.success)
        self.assertEqual(len(self.player.inventory), 0)
        self.assertEqual(len(self.player.collected_treasures), 0)

    # 6. NPC out-of-range interaction rejection
    def test_06_npc_out_of_range_rejection(self) -> None:
        """Interacting with an NPC when far away fails with clean proximity message."""
        # Oak is at (2.5, 1.5), player is at (20.0, 20.0)
        far_pos = (20.0, 20.0)
        result = self.interaction_mgr.interact(
            player=self.player,
            object_id="npc_prof_oak",
            player_position=far_pos,
        )
        self.assertFalse(result.success)
        self.assertIn("out of range", result.message)

    # 7. Quest status evaluation and missing prerequisite reporting
    def test_07_missing_prerequisites_reporting(self) -> None:
        """get_missing_prerequisites accurately reports incomplete prerequisites."""
        # Initially, First Encounter is AVAILABLE, Species Research requires First Encounter
        self.assertEqual(self.quest_mgr.get_quest_status(self.player, "first_encounter"), QuestStatus.AVAILABLE)
        self.assertEqual(self.quest_mgr.get_quest_status(self.player, "species_research"), QuestStatus.LOCKED)

        missing = self.quest_mgr.get_missing_prerequisites(self.player, "species_research")
        self.assertEqual(len(missing), 1)
        self.assertEqual(missing[0].quest_id, "first_encounter")
        self.assertEqual(missing[0].name, "First Encounter")

        # After completing First Encounter, Species Research has 0 missing prerequisites
        self.quest_mgr.accept_quest(self.player, "first_encounter")
        q_prog = self.player.quests["first_encounter"]
        q_prog.objective_progress["capture_first_pokemon"].increment(1)
        q_prog.update_completion()
        self.assertTrue(q_prog.is_completed)

        self.assertEqual(self.quest_mgr.get_quest_status(self.player, "species_research"), QuestStatus.AVAILABLE)
        missing_after = self.quest_mgr.get_missing_prerequisites(self.player, "species_research")
        self.assertEqual(len(missing_after), 0)

    # 8. Scripted NPC dialogue: Available quest inspection and acceptance
    def test_08_npc_dialogue_accept_quest(self) -> None:
        """Player can talk to Professor Oak, inspect First Encounter, and accept it."""
        # Flow:
        # 1. Main menu: Travel to Route 1 Signpost (coords 2.0, 1.0) -> [2] Travel -> [2] Signpost
        # 2. Main menu: Interact with World Objects (3) -> [5] Professor Oak
        # 3. NPC Menu: Choose topic [1] First Encounter
        # 4. Quest prompt: Choose [1] Accept Quest
        # 5. Return to topics: [0] Leave Conversation
        # 6. Title menu: [10] -> [y] -> Quit [3]
        inputs = [
            "1", "Ash", "1",           # New game, Ash, Pikachu starter
            "2", "2",                  # Travel to Route 1 Signpost (within range of Oak at 2.5, 1.5)
            "3", "5",                  # Interact with [5] Professor Oak
            "1",                       # Topic 1: First Encounter
            "1",                       # Accept quest
            "0",                       # Leave conversation
            "10", "y", "3",            # Quit
        ]
        logs: list[str] = []
        input_iter = iter(inputs)

        def mock_in(prompt: str = "") -> str:
            return next(input_iter)

        def mock_out(*args: object) -> None:
            logs.append(" ".join(str(a) for a in args))

        game = AdventureGame(input_fn=mock_in, output_fn=mock_out)
        game.run()

        # Verify acceptance logged and recorded in player state
        self.assertTrue(any("Professor Oak" in line for line in logs))
        self.assertTrue(any("Accepted quest: 'First Encounter'" in line for line in logs))
        self.assertTrue(game.player.has_quest("first_encounter"))
        self.assertEqual(game.player.quests["first_encounter"].status, QuestStatus.ACTIVE)

    # 9. Scripted NPC dialogue: Declining an available quest leaves state unchanged
    def test_09_npc_dialogue_decline_quest(self) -> None:
        """Player can inspect a quest and decline it; quest remains unaccepted and AVAILABLE."""
        inputs = [
            "1", "Ash", "1",
            "2", "2",                  # Travel to Route 1 Signpost
            "3", "5",                  # Talk to Professor Oak
            "1",                       # Topic 1: First Encounter
            "2",                       # [2] Decline / Not Right Now
            "0",                       # Leave conversation
            "10", "y", "3",
        ]
        logs: list[str] = []
        input_iter = iter(inputs)

        game = AdventureGame(input_fn=lambda p="": next(input_iter), output_fn=lambda *a: logs.append(" ".join(str(x) for x in a)))
        game.run()

        self.assertTrue(any("Come speak with me whenever you feel ready" in line for line in logs))
        # Quest is NOT accepted
        self.assertFalse(game.player.has_quest("first_encounter"))
        self.assertEqual(game.quest_manager.get_quest_status(game.player, "first_encounter"), QuestStatus.AVAILABLE)

    # 10. Scripted NPC dialogue: Locked quest displays missing prerequisites
    def test_10_npc_dialogue_locked_quest_feedback(self) -> None:
        """Selecting a locked quest from an NPC displays prerequisite requirements clearly."""
        inputs = [
            "1", "Ash", "1",
            "2", "2",                  # Travel to Route 1 Signpost
            "3", "5",                  # Talk to Professor Oak
            "2",                       # Topic 2: Species Research (LOCKED)
            "0",                       # Leave conversation
            "10", "y", "3",
        ]
        logs: list[str] = []
        input_iter = iter(inputs)

        game = AdventureGame(input_fn=lambda p="": next(input_iter), output_fn=lambda *a: logs.append(" ".join(str(x) for x in a)))
        game.run()

        self.assertTrue(any("QUEST LOCKED: Species Research" in line for line in logs))
        self.assertTrue(any("Must complete 'First Encounter' first" in line for line in logs))
        self.assertFalse(game.player.has_quest("species_research"))

    # 11. Scripted NPC dialogue: Active quest displays current progress
    def test_11_npc_dialogue_active_quest_progress(self) -> None:
        """Talking to an NPC about an active quest reports live objective progress."""
        inputs = [
            "1", "Ash", "1",
            "2", "2",                  # Travel to Route 1 Signpost
            "3", "5",                  # Talk to Professor Oak
            "1", "1",                  # Select First Encounter -> Accept
            "1",                       # Select First Encounter again (now ACTIVE)
            "0",                       # Leave conversation
            "10", "y", "3",
        ]
        logs: list[str] = []
        input_iter = iter(inputs)

        game = AdventureGame(input_fn=lambda p="": next(input_iter), output_fn=lambda *a: logs.append(" ".join(str(x) for x in a)))
        game.run()

        self.assertTrue(any("CURRENT OBJECTIVES: First Encounter" in line for line in logs))
        self.assertTrue(any("capture_first_pokemon: 0/1 (IN PROGRESS)" in line for line in logs))

    # 12. Scripted NPC dialogue: Completed quest dialogue & unclaimed rewards reminder
    def test_12_npc_dialogue_completed_quest_and_unclaimed_rewards(self) -> None:
        """NPC commends player on quest completion and reminds them of unclaimed rewards."""
        inputs = [
            "1", "Ash", "1",
            "2", "2",                  # Travel to Route 1 Signpost
            "3", "5",                  # Talk to Professor Oak
            "1", "1",                  # Accept First Encounter
            "0",                       # Leave Oak
        ]
        logs: list[str] = []
        input_iter = iter(inputs)

        def mock_in(prompt: str = "") -> str:
            try:
                return next(input_iter)
            except StopIteration:
                return "0"

        game = AdventureGame(input_fn=mock_in, output_fn=lambda *a: logs.append(" ".join(str(x) for x in a)))
        # Setup initial state
        game.player = Player(name="Ash", inventory=Inventory(capacity=20))
        mon = create_test_pokemon(PIKACHU, level=5)
        game.player.add_pokemon(mon)
        game.player.add_to_team(mon)
        game.player_pos = [2.0, 1.0]

        # Accept quest, complete it, but do NOT claim rewards
        game.quest_manager.accept_quest(game.player, "first_encounter")
        q_prog = game.player.quests["first_encounter"]
        q_prog.objective_progress["capture_first_pokemon"].increment(1)
        q_prog.update_completion()
        self.assertTrue(q_prog.is_completed)
        self.assertFalse(q_prog.rewards_claimed)

        # Talk to Oak again
        oak_obj = [o for o in game.world_interaction_manager.list_objects() if o.object_id == "npc_prof_oak"][0]
        res = game.world_interaction_manager.interact(game.player, "npc_prof_oak", game.player_pos)
        
        # Script inspect completed quest topic: choose topic 1, then leave (0)
        topic_inputs = iter(["1", "0"])
        game._prompt = lambda p="": next(topic_inputs)
        game._npc_dialogue_flow(oak_obj, res)

        self.assertTrue(any("QUEST COMPLETED: First Encounter" in line for line in logs))
        self.assertTrue(any("Rewards waiting to be claimed: 2x Potion" in line for line in logs))
        # Rewards must NOT be claimed by talking
        self.assertFalse(game.player.quests["first_encounter"].rewards_claimed)
        self.assertEqual(game.player.inventory.get_quantity("potion"), 0)

    # 13. Save/load compatibility: NPCs do not pollute treasures or landmarks
    def test_13_save_load_compatibility_with_npcs(self) -> None:
        """Game with active/completed quests and NPC interactions saves and loads cleanly."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            save_path = os.path.join(tmp_dir, "test_npc_save.json")

            # Create game, accept quest from Oak, save
            game = AdventureGame(save_file=save_path)
            game.player = Player(name="Red", inventory=Inventory(capacity=20))
            mon = create_test_pokemon(PIKACHU, level=5)
            game.player.add_pokemon(mon)
            game.player.add_to_team(mon)
            game.player_pos = [2.5, 1.5]

            # Accept quest
            accept_res = game.quest_manager.accept_quest(game.player, "first_encounter")
            self.assertTrue(accept_res.success)

            # Interact with Oak
            res = game.world_interaction_manager.interact(game.player, "npc_prof_oak", game.player_pos)
            self.assertTrue(res.success)

            # Save game
            save_game(game.player, save_path)
            self.assertTrue(os.path.exists(save_path))

            # Load game into fresh session
            loaded_player = load_game(save_path)
            self.assertIsNotNone(loaded_player)
            self.assertEqual(loaded_player.name, "Red")
            self.assertTrue(loaded_player.has_quest("first_encounter"))

            # Verify no NPC IDs in collected_treasures or discovered_landmarks
            self.assertNotIn("npc_prof_oak", loaded_player.collected_treasures)
            self.assertNotIn("npc_prof_oak", loaded_player.discovered_landmarks)

    # 14. Existing quest-log menu navigation [6] -> [1] remains fully functional
    def test_14_legacy_quest_menu_acceptance_compatibility(self) -> None:
        """Opening Quest Log (6) -> Accept (1) -> Stocking Supplies (4) continues to function perfectly."""
        inputs = [
            "1", "Ash", "1",
            "6", "1", "4",              # Quest menu [6] -> Accept [1] -> Stocking Supplies [4]
            "0",                        # Back to main menu
            "10", "y", "3",             # Quit
        ]
        logs: list[str] = []
        input_iter = iter(inputs)

        game = AdventureGame(input_fn=lambda p="": next(input_iter), output_fn=lambda *a: logs.append(" ".join(str(x) for x in a)))
        game.run()

        self.assertTrue(any("Accepted quest: 'Stocking Supplies'" in line for line in logs))
        self.assertTrue(game.player.has_quest("stocking_supplies"))

    # 15. All 4 NPCs can be spoken to and offer their distinct quests
    def test_15_all_four_npcs_offer_correct_quests(self) -> None:
        """Verify each of the 4 NPCs presents their expected quests."""
        expected_assignments = {
            "npc_prof_oak": ("first_encounter", "species_research", "research_specialization"),
            "npc_battle_scout": ("wild_challenger", "growing_stronger"),
            "npc_trail_ranger": ("trailblazer", "shrine_investigation"),
            "npc_supply_clerk": ("stocking_supplies", "collectors_pride"),
        }
        for obj_id, expected_qids in expected_assignments.items():
            obj = self.interaction_mgr.get_object(obj_id)
            self.assertIsNotNone(obj, f"Object {obj_id} must be registered")
            self.assertEqual(obj.interactable_type, InteractableType.NPC)
            npc = get_npc(obj.npc_id)
            self.assertIsNotNone(npc)
            self.assertEqual(npc.offered_quest_ids, expected_qids)


if __name__ == "__main__":
    unittest.main()
