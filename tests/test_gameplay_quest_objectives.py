"""
Integration and unit tests for Phase B2: Gameplay-Driven Quest Objectives.
Validates authoritative gameplay event dispatching, state-based inventory synchronization,
occurrence counter increments, idempotency, and permanent completion locking.
"""
import unittest
import random

from src.models.player import Player
from src.models.pokemon import Pokemon
from src.models.personality import Personality
from src.models.inventory import Inventory
from src.models.item_manager import ItemManager
from src.models.battle_manager import BattleManager
from src.models.capture_manager import CaptureManager
from src.models.encounter_manager import EncounterManager, WildEncounter
from src.models.spawn_area import SpawnArea
from src.models.spawn_manager import SpawnManager
from src.models.world_exploration_manager import WorldExplorationManager
from src.models.quest import (
    QuestStatus,
    ObjectiveType,
    QuestEventType,
    QuestObjective,
    QuestDefinition,
    ObjectiveProgress,
    QuestProgress,
)
from src.models.quest_manager import QuestManager
from src.data.species import PIKACHU, CHARMANDER, SQUIRTLE
from src.data.attacks import THUNDER_SHOCK, QUICK_ATTACK, TACKLE, SCRATCH
from src.data.items import POTION, SUPER_POTION, ANTIDOTE
from src.data.world_regions import create_default_world_regions
from src.data.world_objects import create_default_world_objects
from src.models.world_interaction_manager import WorldInteractionManager


class TestGameplayQuestObjectives(unittest.TestCase):
    """
    Test suite verifying that authoritative gameplay actions correctly advance
    or synchronize quest objectives without regression or data corruption.
    """

    def setUp(self) -> None:
        self.personality = Personality(50, 50, 50, 50, 50, 50)
        self.player = Player(name="Ash")
        self.quest_manager = QuestManager()
        self.rng = random.Random(42)

        self.spawn_manager = SpawnManager()
        self.encounter_manager = EncounterManager(
            spawn_manager=self.spawn_manager,
            quest_manager=self.quest_manager,
        )
        self.capture_manager = CaptureManager(
            rng=self.rng,
            quest_manager=self.quest_manager,
        )
        self.item_manager = ItemManager(quest_manager=self.quest_manager)
        self.battle_manager = BattleManager(
            spawn_manager=self.spawn_manager,
            encounter_manager=self.encounter_manager,
            capture_manager=self.capture_manager,
            quest_manager=self.quest_manager,
            rng=self.rng,
        )
        self.interaction_manager = WorldInteractionManager(
            objects=create_default_world_objects(),
            quest_manager=self.quest_manager,
        )
        self.exploration_manager = WorldExplorationManager(
            regions=create_default_world_regions(),
            interaction_manager=self.interaction_manager,
            quest_manager=self.quest_manager,
        )

        # Starter Pokemon
        self.starter = Pokemon(
            species=PIKACHU,
            personality=self.personality,
            level=5,
            attacks=[THUNDER_SHOCK, QUICK_ATTACK],
        )
        self.player.add_pokemon(self.starter)
        self.player.add_to_team(self.starter)
        self.player.set_active_pokemon(self.starter)

    def _create_wild_pokemon(self, species=PIKACHU, level=3) -> Pokemon:
        return Pokemon(
            species=species,
            personality=self.personality,
            level=level,
            attacks=[TACKLE],
        )

    # --- 1. Wild Capture & Species Matching ---

    def test_01_wild_capture_success_advances_capture_any_and_capture_species(self) -> None:
        """Capturing wild Pokemon advances CAPTURE_ANY and matching CAPTURE_SPECIES."""
        self.quest_manager.accept_quest(self.player, "first_encounter")
        wild_pika = self._create_wild_pokemon(PIKACHU, level=2)

        # Standalone capture with fixed deterministic RNG guarantee (seed with high prob roll)
        cap_mgr = CaptureManager(rng=random.Random(1), quest_manager=self.quest_manager)
        # We lower pika HP to guarantee high catch chance
        wild_pika.take_damage(wild_pika.max_hp - 1)
        res = cap_mgr.attempt_capture(self.player, wild_pika)
        self.assertTrue(res.success)

        # first_encounter requires CAPTURE_ANY 1 -> completed
        q_prog = self.quest_manager.get_quest_progress(self.player, "first_encounter")
        self.assertIsNotNone(q_prog)
        self.assertTrue(q_prog.is_completed)
        self.assertEqual(q_prog.status, QuestStatus.COMPLETED)

    def test_02_wild_capture_different_species_does_not_advance_wrong_species_objective(self) -> None:
        """Capturing Charmander does NOT advance Pikachu or Squirtle in species_research."""
        # Complete first encounter and accept species_research
        self.quest_manager.accept_quest(self.player, "first_encounter")
        self.quest_manager.record_capture(self.player, "Rattata")
        self.quest_manager.accept_quest(self.player, "species_research")

        wild_charm = self._create_wild_pokemon(CHARMANDER, level=2)
        wild_charm.take_damage(wild_charm.max_hp - 1)

        cap_mgr = CaptureManager(rng=random.Random(1), quest_manager=self.quest_manager)
        res = cap_mgr.attempt_capture(self.player, wild_charm)
        self.assertTrue(res.success)

        # species_research requires Pikachu and Squirtle
        q_prog = self.quest_manager.get_quest_progress(self.player, "species_research")
        obj_pika = q_prog.get_objective("capture_pikachu")
        obj_sq = q_prog.get_objective("capture_squirtle")
        self.assertEqual(obj_pika.current_count, 0)
        self.assertEqual(obj_sq.current_count, 0)
        self.assertFalse(q_prog.is_completed)

    def test_03_failed_capture_roll_emits_no_quest_progress(self) -> None:
        """When wild Pokemon breaks free, no capture quest progress is awarded."""
        self.quest_manager.accept_quest(self.player, "first_encounter")
        wild_pika = self._create_wild_pokemon(PIKACHU, level=10)

        # Use an RNG that returns 1.0 (always above capture probability)
        class FailRNG(random.Random):
            def random(self):
                return 0.99

        cap_mgr = CaptureManager(rng=FailRNG(), quest_manager=self.quest_manager)
        res = cap_mgr.attempt_capture(self.player, wild_pika)
        self.assertFalse(res.success)

        q_prog = self.quest_manager.get_quest_progress(self.player, "first_encounter")
        obj_prog = q_prog.get_objective("capture_first_pokemon")
        self.assertEqual(obj_prog.current_count, 0)
        self.assertFalse(q_prog.is_completed)

    # --- 2. Wild Encounters ---

    def test_04_wild_encounter_start_advances_encounter_objectives(self) -> None:
        """Starting a wild battle dispatches POKEMON_ENCOUNTERED and advances objectives."""
        custom_quest = QuestDefinition(
            quest_id="wild_spotter",
            name="Wild Spotter",
            description="Spot a wild Pikachu in the wild.",
            objectives=(
                QuestObjective(
                    objective_id="spot_pika",
                    objective_type=ObjectiveType.ENCOUNTER_SPECIES,
                    description="Encounter 1 Pikachu",
                    target_count=1,
                    target_species="Pikachu",
                ),
            ),
        )
        qm = QuestManager(catalog={"wild_spotter": custom_quest})
        qm.accept_quest(self.player, "wild_spotter")

        bm = BattleManager(quest_manager=qm, rng=self.rng)
        wild_pika = self._create_wild_pokemon(PIKACHU)

        # Start wild battle
        battle = bm.start_battle(self.player, opponent=wild_pika)
        self.assertIsNotNone(battle)

        q_prog = qm.get_quest_progress(self.player, "wild_spotter")
        self.assertTrue(q_prog.is_completed)

    # --- 3. Inventory Item Possession vs Consumption ---

    def test_05_item_collection_advances_state_based_collect_item(self) -> None:
        """Adding Potions to inventory advances stocking_supplies."""
        self.quest_manager.accept_quest(self.player, "stocking_supplies")
        q_prog = self.quest_manager.get_quest_progress(self.player, "stocking_supplies")
        obj_prog = q_prog.get_objective("collect_potions")
        self.assertEqual(obj_prog.current_count, 0)

        # Add 2 potions
        self.player.inventory.add_item("potion", 2)
        self.quest_manager.record_item_collected(self.player, "potion")
        self.assertEqual(obj_prog.current_count, 2)
        self.assertFalse(q_prog.is_completed)

    def test_06_item_consumption_decreases_progress_on_incomplete_objective(self) -> None:
        """Consuming an item decreases progress when objective is incomplete."""
        self.quest_manager.accept_quest(self.player, "stocking_supplies")
        q_prog = self.quest_manager.get_quest_progress(self.player, "stocking_supplies")
        obj_prog = q_prog.get_objective("collect_potions")

        # Give 2 potions -> 2/3
        self.player.inventory.add_item("potion", 2)
        self.quest_manager.record_item_collected(self.player, "potion")
        self.assertEqual(obj_prog.current_count, 2)

        # Use 1 potion on starter -> inventory has 1
        self.starter.take_damage(20)
        use_res = self.item_manager.use_item(
            inventory=self.player.inventory,
            item_or_id="potion",
            target_pokemon=self.starter,
            player=self.player,
        )
        self.assertTrue(use_res.success)
        self.assertEqual(self.player.inventory.get_quantity("potion"), 1)

        # Progress should accurately reflect 1/3
        self.assertEqual(obj_prog.current_count, 1)
        self.assertFalse(obj_prog.is_completed)

    def test_07_completed_item_possession_quest_never_reverts_when_items_consumed(self) -> None:
        """Once stocking_supplies completes at 3/3, subsequent consumption NEVER reverts it."""
        self.quest_manager.accept_quest(self.player, "stocking_supplies")
        q_prog = self.quest_manager.get_quest_progress(self.player, "stocking_supplies")
        obj_prog = q_prog.get_objective("collect_potions")

        # Give 3 potions -> 3/3 completed
        self.player.inventory.add_item("potion", 3)
        self.quest_manager.record_item_collected(self.player, "potion")
        self.assertTrue(obj_prog.is_completed)
        self.assertTrue(q_prog.is_completed)
        self.assertEqual(q_prog.status, QuestStatus.COMPLETED)

        # Use all 3 potions
        self.starter.take_damage(10)
        self.item_manager.use_item(self.player.inventory, "potion", self.starter, player=self.player)
        self.starter.take_damage(10)
        self.item_manager.use_item(self.player.inventory, "potion", self.starter, player=self.player)
        self.starter.take_damage(10)
        self.item_manager.use_item(self.player.inventory, "potion", self.starter, player=self.player)

        self.assertEqual(self.player.inventory.get_quantity("potion"), 0)

        # Objective and Quest MUST remain COMPLETED
        self.assertTrue(obj_prog.is_completed)
        self.assertEqual(obj_prog.current_count, 3)
        self.assertTrue(q_prog.is_completed)
        self.assertEqual(q_prog.status, QuestStatus.COMPLETED)

    def test_08_consuming_unrelated_item_does_not_affect_objective(self) -> None:
        """Consuming a Super Potion does NOT decrease progress on Potion collection objective."""
        self.quest_manager.accept_quest(self.player, "stocking_supplies")
        q_prog = self.quest_manager.get_quest_progress(self.player, "stocking_supplies")
        obj_prog = q_prog.get_objective("collect_potions")

        # Pick up 2 potions and 2 super potions
        self.player.inventory.add_item("potion", 2)
        self.player.inventory.add_item("super_potion", 2)
        self.quest_manager.record_item_collected(self.player, "potion")
        self.assertEqual(obj_prog.current_count, 2)

        # Damage starter and use super_potion
        self.starter.take_damage(10)
        use_res = self.item_manager.use_item(
            inventory=self.player.inventory,
            item_or_id="super_potion",
            target_pokemon=self.starter,
            player=self.player,
        )
        self.assertTrue(use_res.success)
        self.assertEqual(self.player.inventory.get_quantity("super_potion"), 1)
        self.assertEqual(self.player.inventory.get_quantity("potion"), 2)

        # Potion objective remains at 2!
        self.assertEqual(obj_prog.current_count, 2)

    # --- 4. Battle Victories and Fleeing ---

    def test_09_defeat_in_battle_advances_defeat_objectives_while_fleeing_does_not(self) -> None:
        """Winning battle advances DEFEAT_ANY; fleeing leaves it unadvanced."""
        self.quest_manager.accept_quest(self.player, "wild_challenger")
        q_prog = self.quest_manager.get_quest_progress(self.player, "wild_challenger")
        obj_prog = q_prog.get_objective("defeat_any_pokemon")
        self.assertEqual(obj_prog.current_count, 0)

        # Fleeing from wild battle
        wild_pika = self._create_wild_pokemon(PIKACHU)
        battle = self.battle_manager.start_battle(self.player, opponent=wild_pika)
        flee_res = self.battle_manager.flee(self.player)
        self.assertTrue(flee_res.accepted)
        self.assertEqual(obj_prog.current_count, 0)
        self.assertFalse(q_prog.is_completed)

        # KO in next battle
        wild_charm = self._create_wild_pokemon(CHARMANDER, level=1)
        wild_charm.take_damage(wild_charm.max_hp - 1)  # 1 HP remaining
        battle2 = self.battle_manager.start_battle(self.player, opponent=wild_charm)
        atk_res = self.battle_manager.attack(self.player, THUNDER_SHOCK)
        self.assertTrue(atk_res.accepted)
        self.assertTrue(atk_res.terminal)

        # Quest should now be completed
        self.assertEqual(obj_prog.current_count, 1)
        self.assertTrue(q_prog.is_completed)

    # --- 5. Exploration & Discovery Objectives ---

    def test_10_exploration_discoveries_advance_discovery_objectives(self) -> None:
        """Discovering region and landmark advances trailblazer quest."""
        # Complete first_encounter to unlock trailblazer
        self.quest_manager.accept_quest(self.player, "first_encounter")
        self.quest_manager.record_capture(self.player, "Pikachu")
        self.quest_manager.accept_quest(self.player, "trailblazer")

        q_prog = self.quest_manager.get_quest_progress(self.player, "trailblazer")
        self.assertFalse(q_prog.is_completed)

        # Discover starting meadow
        reg_res = self.exploration_manager.discover_region(self.player, "starting_meadow")
        self.assertTrue(reg_res.success)
        self.assertTrue(reg_res.event_emitted)
        self.assertEqual(q_prog.get_objective("discover_meadow").current_count, 1)

        # Discover ancient shrine landmark (landmark position is 25.0, 25.0)
        lm_res = self.exploration_manager.discover_landmark(self.player, "ancient_shrine", player_position=(25.0, 25.0))
        self.assertTrue(lm_res.success)
        self.assertTrue(lm_res.event_emitted)
        self.assertEqual(q_prog.get_objective("discover_shrine").current_count, 1)

        # All objectives fulfilled -> quest complete
        self.assertTrue(q_prog.is_completed)
        self.assertEqual(q_prog.status, QuestStatus.COMPLETED)

    def test_11_failed_discoveries_emit_no_quest_progress(self) -> None:
        """Discovery attempts outside radius or already discovered emit no progress."""
        self.quest_manager.accept_quest(self.player, "first_encounter")
        self.quest_manager.record_capture(self.player, "Pikachu")
        self.quest_manager.accept_quest(self.player, "trailblazer")

        # Discover once
        self.exploration_manager.discover_region(self.player, "starting_meadow")
        q_prog = self.quest_manager.get_quest_progress(self.player, "trailblazer")
        self.assertEqual(q_prog.get_objective("discover_meadow").current_count, 1)

        # Attempt rediscovery -> event_emitted is False
        rediscover = self.exploration_manager.discover_region(self.player, "starting_meadow")
        self.assertFalse(rediscover.event_emitted)

        # Attempt out of range landmark discovery (shrine is at 25, 25; player at 999, 999)
        out_of_range = self.exploration_manager.discover_landmark(
            self.player,
            "ancient_shrine",
            player_position=(999.0, 999.0),
        )
        self.assertFalse(out_of_range.success)
        self.assertFalse(out_of_range.event_emitted)
        self.assertEqual(q_prog.get_objective("discover_shrine").current_count, 0)

    # --- 6. Immediate Evaluation & Idempotency ---

    def test_12_accepting_quest_with_preexisting_state_immediately_evaluates(self) -> None:
        """Accepting a quest when already meeting conditions immediately completes."""
        # Pre-populate 3 potions in inventory
        self.player.inventory.add_item("potion", 3)

        res = self.quest_manager.accept_quest(self.player, "stocking_supplies")
        self.assertTrue(res.success)
        self.assertIn("immediately completed", res.message.lower())

        q_prog = self.quest_manager.get_quest_progress(self.player, "stocking_supplies")
        self.assertTrue(q_prog.is_completed)
        self.assertEqual(q_prog.status, QuestStatus.COMPLETED)

    def test_13_event_id_deduplication_prevents_duplicate_progress(self) -> None:
        """Replaying identical event IDs is idempotent and prevents extra progress."""
        self.quest_manager.accept_quest(self.player, "first_encounter")
        q_prog = self.quest_manager.get_quest_progress(self.player, "first_encounter")
        obj_prog = q_prog.get_objective("capture_first_pokemon")

        # First event
        res1 = self.quest_manager.record_capture(self.player, "Pikachu", event_id="evt_unique_1")
        self.assertEqual(res1.events_processed, 1)
        self.assertEqual(obj_prog.current_count, 1)

        # Duplicate event with same ID
        res2 = self.quest_manager.record_capture(self.player, "Pikachu", event_id="evt_unique_1")
        self.assertEqual(res2.events_processed, 0)
        self.assertIn("duplicate", res2.message.lower())

    def test_14_sync_inventory_state_updates_all_active_item_objectives(self) -> None:
        """sync_inventory_state adjusts active item objectives to reflect inventory count."""
        self.quest_manager.accept_quest(self.player, "stocking_supplies")
        q_prog = self.quest_manager.get_quest_progress(self.player, "stocking_supplies")
        obj_prog = q_prog.get_objective("collect_potions")

        # Directly alter inventory without event
        self.player.inventory.add_item("potion", 2)
        self.assertEqual(obj_prog.current_count, 0)

        # Sync inventory state
        sync_res = self.quest_manager.sync_inventory_state(self.player)
        self.assertEqual(sync_res.objectives_updated, 1)
        self.assertEqual(obj_prog.current_count, 2)


if __name__ == "__main__":
    unittest.main()
