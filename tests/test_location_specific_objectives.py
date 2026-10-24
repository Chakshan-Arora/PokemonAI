"""
Unit and integration tests for Phase C2.1: Location-Specific Objectives.

Tests verify:
1. Location-restricted defeat objective advances in the correct region.
2. Defeat in the wrong region does not advance a location-restricted objective.
3. Location-restricted capture objective advances only in the correct region.
4. Capture in the wrong region does not advance a location-restricted capture objective,
   including through any secondary event path (such as POKEMON_COLLECTED).
5. Unrestricted legacy objectives still advance in any region.
6. Missing or unknown region context is handled safely and cannot satisfy a restricted objective.
7. Replayed events with the same event_id do not award duplicate progress.
8. Objective counts never exceed their targets.
9. Case-insensitive region ID matching works reliably.
10. Species-specific location-restricted defeats and captures enforce both species and region.
11. Location-restricted wild encounter objectives advance only in the correct region.
12. End-to-end BattleManager battle victory advances region-restricted defeat objectives authoritatively.
13. End-to-end BattleManager capture advances region-restricted capture objectives authoritatively.
14. End-to-end battle in the wrong region does not advance region-restricted objectives.
15. Quests with location-restricted objectives trigger completion notifications, allow claiming,
    and persist across save/load round-trips.
"""
import unittest
import tempfile
import shutil
from pathlib import Path

from src.models.player import Player
from src.models.personality import Personality
from src.models.pokemon import Pokemon
from src.models.spawn_area import SpawnArea
from src.models.encounter_manager import EncounterManager, WildEncounter, EncounterResult
from src.models.battle_manager import BattleManager
from src.models.battle import Battle
from src.models.battle_state import BattleState
from src.models.save_manager import save_game, load_game
from src.models.quest import (
    ObjectiveType,
    QuestEventType,
    QuestObjective,
    QuestDefinition,
    QuestStatus,
)
from src.models.capture_manager import CaptureManager
from src.models.quest_manager import QuestManager
from src.data.species import PIKACHU, CHARMANDER, SQUIRTLE
from src.data.attacks import THUNDER_SHOCK, TACKLE


class TestLocationSpecificObjectives(unittest.TestCase):
    """Test suite covering location-specific quest objectives (Phase C2.1)."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.save_file = str(Path(self.temp_dir) / "test_c2_save.json")

        self.personality = Personality(
            aggression=30, curiosity=60, fear=20, sociability=80, loyalty=90, confidence=70
        )
        self.starter = Pokemon(
            species=PIKACHU,
            personality=self.personality,
            level=5,
            attacks=[THUNDER_SHOCK],
        )
        self.player = Player(name="Red")
        self.player.add_pokemon(self.starter)
        self.player.add_to_team(self.starter)
        self.player.set_active_pokemon(self.starter)

        # Custom location-aware quest definitions
        self.quest_defeat_forest = QuestDefinition(
            quest_id="defeat_forest_wild",
            name="Forest Combat",
            description="Defeat any wild Pokemon in the Forest Trail.",
            objectives=(
                QuestObjective(
                    objective_id="defeat_in_forest",
                    objective_type=ObjectiveType.DEFEAT_ANY,
                    description="Defeat 1 Pokemon in Forest Trail",
                    target_count=1,
                    target_region="forest_trail",
                ),
            ),
            rewards={"potion": 1},
        )

        self.quest_capture_meadow = QuestDefinition(
            quest_id="capture_meadow_wild",
            name="Meadow Foraging",
            description="Capture any wild Pokemon in the Starting Meadow.",
            objectives=(
                QuestObjective(
                    objective_id="capture_in_meadow",
                    objective_type=ObjectiveType.CAPTURE_ANY,
                    description="Capture 1 wild Pokemon in Starting Meadow",
                    target_count=1,
                    target_region="starting_meadow",
                ),
            ),
            rewards={"poke_ball": 3},
        )

        self.quest_legacy_unrestricted = QuestDefinition(
            quest_id="unrestricted_defeat",
            name="General Battler",
            description="Defeat any Pokemon anywhere in the world.",
            objectives=(
                QuestObjective(
                    objective_id="defeat_anywhere",
                    objective_type=ObjectiveType.DEFEAT_ANY,
                    description="Defeat 1 Pokemon anywhere",
                    target_count=1,
                    target_region=None,
                ),
            ),
            rewards={"super_potion": 1},
        )

        self.quest_species_region = QuestDefinition(
            quest_id="shrine_charmander_hunt",
            name="Shrine Challenger",
            description="Defeat a Charmander at the Ancient Shrine Grounds.",
            objectives=(
                QuestObjective(
                    objective_id="defeat_shrine_charmander",
                    objective_type=ObjectiveType.DEFEAT_SPECIES,
                    description="Defeat 1 Charmander at Ancient Shrine Grounds",
                    target_count=1,
                    target_species="Charmander",
                    target_region="ancient_shrine_grounds",
                ),
            ),
            rewards={"max_potion": 1},
        )

        self.quest_encounter_region = QuestDefinition(
            quest_id="encounter_forest_scout",
            name="Forest Scout",
            description="Encounter any wild Pokemon in the Forest Trail.",
            objectives=(
                QuestObjective(
                    objective_id="encounter_in_forest",
                    objective_type=ObjectiveType.ENCOUNTER_ANY,
                    description="Encounter 1 wild Pokemon in Forest Trail",
                    target_count=1,
                    target_region="forest_trail",
                ),
            ),
            rewards={"antidote": 1},
        )

        self.custom_catalog = {
            self.quest_defeat_forest.quest_id: self.quest_defeat_forest,
            self.quest_capture_meadow.quest_id: self.quest_capture_meadow,
            self.quest_legacy_unrestricted.quest_id: self.quest_legacy_unrestricted,
            self.quest_species_region.quest_id: self.quest_species_region,
            self.quest_encounter_region.quest_id: self.quest_encounter_region,
        }

        self.quest_manager = QuestManager(catalog=self.custom_catalog)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # 1. A location-restricted defeat objective advances in the correct region.
    def test_01_location_restricted_defeat_advances_in_correct_region(self) -> None:
        self.quest_manager.accept_quest(self.player, "defeat_forest_wild")
        prog = self.player.quests["defeat_forest_wild"]
        self.assertEqual(prog.status, QuestStatus.ACTIVE)
        self.assertEqual(prog.get_objective("defeat_in_forest").current_count, 0)

        # Defeat in forest_trail
        res = self.quest_manager.record_defeat(
            self.player, species_name="Pikachu", region_id="forest_trail"
        )
        self.assertEqual(res.objectives_updated, 1)
        self.assertEqual(prog.get_objective("defeat_in_forest").current_count, 1)
        self.assertTrue(prog.get_objective("defeat_in_forest").is_completed)
        self.assertEqual(prog.status, QuestStatus.COMPLETED)

    # 2. A defeat in the wrong region does not advance it.
    def test_02_defeat_in_wrong_region_does_not_advance_objective(self) -> None:
        self.quest_manager.accept_quest(self.player, "defeat_forest_wild")
        prog = self.player.quests["defeat_forest_wild"]

        # Defeat in starting_meadow instead of forest_trail
        res = self.quest_manager.record_defeat(
            self.player, species_name="Pikachu", region_id="starting_meadow"
        )
        self.assertEqual(res.objectives_updated, 0)
        self.assertEqual(prog.get_objective("defeat_in_forest").current_count, 0)
        self.assertFalse(prog.get_objective("defeat_in_forest").is_completed)
        self.assertEqual(prog.status, QuestStatus.ACTIVE)

        # Defeat in ancient_shrine_grounds instead of forest_trail
        res2 = self.quest_manager.record_defeat(
            self.player, species_name="Charmander", region_id="ancient_shrine_grounds"
        )
        self.assertEqual(res2.objectives_updated, 0)
        self.assertEqual(prog.get_objective("defeat_in_forest").current_count, 0)
        self.assertEqual(prog.status, QuestStatus.ACTIVE)

    # 3. A location-restricted capture objective advances only in the correct region.
    def test_03_location_restricted_capture_advances_in_correct_region(self) -> None:
        self.quest_manager.accept_quest(self.player, "capture_meadow_wild")
        prog = self.player.quests["capture_meadow_wild"]
        self.assertEqual(prog.status, QuestStatus.ACTIVE)

        res = self.quest_manager.record_capture(
            self.player, species_name="Pikachu", region_id="starting_meadow"
        )
        self.assertEqual(res.objectives_updated, 1)
        self.assertEqual(prog.get_objective("capture_in_meadow").current_count, 1)
        self.assertTrue(prog.get_objective("capture_in_meadow").is_completed)
        self.assertEqual(prog.status, QuestStatus.COMPLETED)

    # 4. A capture in the wrong region does not advance it, including secondary event paths.
    def test_04_capture_in_wrong_region_does_not_advance_objective(self) -> None:
        self.quest_manager.accept_quest(self.player, "capture_meadow_wild")
        prog = self.player.quests["capture_meadow_wild"]

        # Capture in forest_trail
        res = self.quest_manager.record_capture(
            self.player, species_name="Pikachu", region_id="forest_trail"
        )
        self.assertEqual(res.objectives_updated, 0)
        self.assertEqual(prog.get_objective("capture_in_meadow").current_count, 0)
        self.assertFalse(prog.get_objective("capture_in_meadow").is_completed)

        # Secondary POKEMON_COLLECTED event should also not bypass capture region restriction
        res_col = self.quest_manager.record_event(
            self.player,
            QuestEventType.POKEMON_COLLECTED,
            payload={"species_name": "Pikachu", "count": 2, "region_id": "forest_trail"},
        )
        self.assertEqual(res_col.objectives_updated, 0)
        self.assertEqual(prog.get_objective("capture_in_meadow").current_count, 0)
        self.assertEqual(prog.status, QuestStatus.ACTIVE)

    # 5. Unrestricted legacy objectives still advance in any region.
    def test_05_unrestricted_legacy_objectives_advance_in_any_region(self) -> None:
        self.quest_manager.accept_quest(self.player, "unrestricted_defeat")
        prog = self.player.quests["unrestricted_defeat"]

        # Defeat with forest_trail
        res1 = self.quest_manager.record_defeat(
            self.player, species_name="Pikachu", region_id="forest_trail"
        )
        self.assertEqual(res1.objectives_updated, 1)
        self.assertEqual(prog.get_objective("defeat_anywhere").current_count, 1)
        self.assertTrue(prog.is_completed)

        # Reset and test with no region_id provided at all
        player2 = Player(name="Blue")
        player2.add_pokemon(self.starter)
        player2.add_to_team(self.starter)
        player2.set_active_pokemon(self.starter)
        self.quest_manager.accept_quest(player2, "unrestricted_defeat")
        prog2 = player2.quests["unrestricted_defeat"]
        res2 = self.quest_manager.record_defeat(player2, species_name="Squirtle")
        self.assertEqual(res2.objectives_updated, 1)
        self.assertEqual(prog2.get_objective("defeat_anywhere").current_count, 1)
        self.assertTrue(prog2.is_completed)

    # 6. Missing or unknown region context is handled safely and cannot satisfy a restricted objective.
    def test_06_missing_or_unknown_region_context_handled_safely(self) -> None:
        self.quest_manager.accept_quest(self.player, "defeat_forest_wild")
        prog = self.player.quests["defeat_forest_wild"]

        # Missing region_id (None)
        res_none = self.quest_manager.record_defeat(self.player, species_name="Pikachu", region_id=None)
        self.assertEqual(res_none.objectives_updated, 0)
        self.assertEqual(prog.get_objective("defeat_in_forest").current_count, 0)

        # Empty string region_id
        res_empty = self.quest_manager.record_defeat(self.player, species_name="Pikachu", region_id="")
        self.assertEqual(res_empty.objectives_updated, 0)
        self.assertEqual(prog.get_objective("defeat_in_forest").current_count, 0)

        # Whitespace region_id
        res_spaces = self.quest_manager.record_defeat(self.player, species_name="Pikachu", region_id="   ")
        self.assertEqual(res_spaces.objectives_updated, 0)
        self.assertEqual(prog.get_objective("defeat_in_forest").current_count, 0)

        # Unknown region_id
        res_unknown = self.quest_manager.record_defeat(self.player, species_name="Pikachu", region_id="outer_space")
        self.assertEqual(res_unknown.objectives_updated, 0)
        self.assertEqual(prog.get_objective("defeat_in_forest").current_count, 0)
        self.assertEqual(prog.status, QuestStatus.ACTIVE)

    # 7. Replayed events do not award duplicate progress.
    def test_07_replayed_events_do_not_award_duplicate_progress(self) -> None:
        self.quest_manager.accept_quest(self.player, "defeat_forest_wild")
        prog = self.player.quests["defeat_forest_wild"]

        event_id = "battle_evt_defeat_001"
        res1 = self.quest_manager.record_defeat(
            self.player, species_name="Pikachu", region_id="forest_trail", event_id=event_id
        )
        self.assertEqual(res1.objectives_updated, 1)
        self.assertEqual(prog.get_objective("defeat_in_forest").current_count, 1)

        # Replay the identical event
        res_replay = self.quest_manager.record_defeat(
            self.player, species_name="Pikachu", region_id="forest_trail", event_id=event_id
        )
        self.assertEqual(res_replay.objectives_updated, 0)
        self.assertEqual(prog.get_objective("defeat_in_forest").current_count, 1)

    # 8. Objective counts never exceed their targets.
    def test_08_objective_counts_never_exceed_targets(self) -> None:
        self.quest_manager.accept_quest(self.player, "defeat_forest_wild")
        prog = self.player.quests["defeat_forest_wild"]

        # First defeat
        self.quest_manager.record_defeat(
            self.player, species_name="Pikachu", count=1, region_id="forest_trail", event_id="evt_01"
        )
        self.assertEqual(prog.get_objective("defeat_in_forest").current_count, 1)

        # Subsequent defeat
        self.quest_manager.record_defeat(
            self.player, species_name="Pikachu", count=1, region_id="forest_trail", event_id="evt_02"
        )
        self.assertEqual(prog.get_objective("defeat_in_forest").current_count, 1)

    # 9. Case-insensitive region ID matching works reliably.
    def test_09_case_insensitive_region_matching(self) -> None:
        self.quest_manager.accept_quest(self.player, "defeat_forest_wild")
        prog = self.player.quests["defeat_forest_wild"]

        res = self.quest_manager.record_defeat(
            self.player, species_name="Pikachu", region_id="FoReSt_TrAiL"
        )
        self.assertEqual(res.objectives_updated, 1)
        self.assertEqual(prog.get_objective("defeat_in_forest").current_count, 1)
        self.assertTrue(prog.is_completed)

    # 10. Species-specific location-restricted defeats and captures enforce both species and region.
    def test_10_species_and_region_restricted_objectives(self) -> None:
        self.quest_manager.accept_quest(self.player, "shrine_charmander_hunt")
        prog = self.player.quests["shrine_charmander_hunt"]

        # Correct region, wrong species (Pikachu)
        res_wrong_species = self.quest_manager.record_defeat(
            self.player, species_name="Pikachu", region_id="ancient_shrine_grounds"
        )
        self.assertEqual(res_wrong_species.objectives_updated, 0)
        self.assertEqual(prog.get_objective("defeat_shrine_charmander").current_count, 0)

        # Correct species, wrong region (forest_trail)
        res_wrong_region = self.quest_manager.record_defeat(
            self.player, species_name="Charmander", region_id="forest_trail"
        )
        self.assertEqual(res_wrong_region.objectives_updated, 0)
        self.assertEqual(prog.get_objective("defeat_shrine_charmander").current_count, 0)

        # Correct species and correct region (Charmander at ancient_shrine_grounds)
        res_match = self.quest_manager.record_defeat(
            self.player, species_name="Charmander", region_id="ancient_shrine_grounds"
        )
        self.assertEqual(res_match.objectives_updated, 1)
        self.assertEqual(prog.get_objective("defeat_shrine_charmander").current_count, 1)
        self.assertTrue(prog.is_completed)

    # 11. Location-restricted wild encounter objectives advance only in the correct region.
    def test_11_location_restricted_encounter_objectives(self) -> None:
        self.quest_manager.accept_quest(self.player, "encounter_forest_scout")
        prog = self.player.quests["encounter_forest_scout"]

        # Encounter in starting_meadow
        res_wrong = self.quest_manager.record_encounter(
            self.player, species_name="Pikachu", region_id="starting_meadow"
        )
        self.assertEqual(res_wrong.objectives_updated, 0)
        self.assertEqual(prog.get_objective("encounter_in_forest").current_count, 0)

        # Encounter in forest_trail
        res_right = self.quest_manager.record_encounter(
            self.player, species_name="Pikachu", region_id="forest_trail"
        )
        self.assertEqual(res_right.objectives_updated, 1)
        self.assertEqual(prog.get_objective("encounter_in_forest").current_count, 1)
        self.assertTrue(prog.is_completed)

    # 12. End-to-end BattleManager battle victory advances region-restricted defeat objectives authoritatively.
    def test_12_battle_manager_victory_advances_region_restricted_objective(self) -> None:
        self.quest_manager.accept_quest(self.player, "defeat_forest_wild")
        prog = self.player.quests["defeat_forest_wild"]

        # SpawnArea in forest_trail
        forest_spawn = SpawnArea(
            area_id="forest_area",
            name="Forest Area",
            allowed_species=(CHARMANDER,),
            region_id="forest_trail",
        )
        opponent = Pokemon(species=CHARMANDER, personality=self.personality, level=2, current_hp=1, attacks=[TACKLE])
        encounter = WildEncounter(player=self.player, pokemon=opponent, area=forest_spawn)
        self.assertEqual(encounter.region_id, "forest_trail")

        bm = BattleManager(quest_manager=self.quest_manager)
        battle = bm.start_wild_battle(self.player, encounter=encounter, use_random_damage=False)
        self.assertEqual(battle.region_id, "forest_trail")

        # Attack to defeat opponent
        attack = self.starter.attacks[0]
        res = bm.attack(self.player, attack)
        self.assertTrue(res.accepted)
        self.assertEqual(battle.state, BattleState.VICTORY)

        # Verify quest advanced
        self.assertEqual(prog.get_objective("defeat_in_forest").current_count, 1)
        self.assertTrue(prog.is_completed)
        self.assertEqual(prog.status, QuestStatus.COMPLETED)

    # 13. End-to-end BattleManager capture advances region-restricted capture objectives authoritatively.
    def test_13_battle_manager_capture_advances_region_restricted_objective(self) -> None:
        self.quest_manager.accept_quest(self.player, "capture_meadow_wild")
        prog = self.player.quests["capture_meadow_wild"]

        meadow_spawn = SpawnArea(
            area_id="meadow_area",
            name="Meadow Area",
            allowed_species=(SQUIRTLE,),
            region_id="starting_meadow",
        )
        wild_squirtle = Pokemon(species=SQUIRTLE, personality=self.personality, level=2, current_hp=1, attacks=[TACKLE])
        encounter = WildEncounter(player=self.player, pokemon=wild_squirtle, area=meadow_spawn)
        self.assertEqual(encounter.region_id, "starting_meadow")

        cap_mgr = CaptureManager(quest_manager=self.quest_manager)
        cap_mgr._min_probability = 1.0
        cap_mgr._max_probability = 1.0
        bm = BattleManager(capture_manager=cap_mgr, quest_manager=self.quest_manager)
        battle = bm.start_wild_battle(self.player, encounter=encounter, use_random_damage=False)
        self.assertEqual(battle.region_id, "starting_meadow")

        cap_res = bm.attempt_capture(self.player)
        self.assertTrue(cap_res.captured)
        self.assertEqual(battle.state, BattleState.CAPTURED)

        # Verify quest advanced
        self.assertEqual(prog.get_objective("capture_in_meadow").current_count, 1)
        self.assertTrue(prog.is_completed)
        self.assertEqual(prog.status, QuestStatus.COMPLETED)

    # 14. End-to-end battle in the wrong region does not advance region-restricted objectives.
    def test_14_battle_manager_wrong_region_does_not_advance_objective(self) -> None:
        self.quest_manager.accept_quest(self.player, "defeat_forest_wild")
        prog = self.player.quests["defeat_forest_wild"]

        # Meadow spawn area (wrong region)
        meadow_spawn = SpawnArea(
            area_id="meadow_area",
            name="Meadow Area",
            allowed_species=(CHARMANDER,),
            region_id="starting_meadow",
        )
        opponent = Pokemon(species=CHARMANDER, personality=self.personality, level=2, current_hp=1, attacks=[TACKLE])
        encounter = WildEncounter(player=self.player, pokemon=opponent, area=meadow_spawn)

        bm = BattleManager(quest_manager=self.quest_manager)
        battle = bm.start_wild_battle(self.player, encounter=encounter, use_random_damage=False)
        self.assertEqual(battle.region_id, "starting_meadow")

        attack = self.starter.attacks[0]
        bm.attack(self.player, attack)
        self.assertEqual(battle.state, BattleState.VICTORY)

        # Verify quest did NOT advance
        self.assertEqual(prog.get_objective("defeat_in_forest").current_count, 0)
        self.assertFalse(prog.is_completed)
        self.assertEqual(prog.status, QuestStatus.ACTIVE)

    # 15. Quests with location-restricted objectives trigger completion notifications,
    # allow claiming, and persist across save/load round-trips.
    def test_15_notifications_claiming_and_persistence(self) -> None:
        self.quest_manager.accept_quest(self.player, "defeat_forest_wild")
        prog = self.player.quests["defeat_forest_wild"]

        # Defeat in forest
        self.quest_manager.record_defeat(
            self.player, species_name="Pikachu", region_id="forest_trail"
        )
        self.assertTrue(prog.is_completed)

        # Notification verification
        self.assertTrue(self.quest_manager.has_pending_notifications())
        notes = self.quest_manager.pop_pending_notifications()
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0].quest_id, "defeat_forest_wild")

        # Save to disk
        save_game(self.player, self.save_file)

        # Restore from disk
        restored = load_game(self.save_file, quest_catalog=self.custom_catalog)
        self.assertIn("defeat_forest_wild", restored.quests)
        restored_prog = restored.quests["defeat_forest_wild"]
        self.assertTrue(restored_prog.is_completed)
        self.assertEqual(restored_prog.get_objective("defeat_in_forest").current_count, 1)
        self.assertFalse(restored_prog.rewards_claimed)

        # Claim rewards on restored player
        claim_res = self.quest_manager.claim_rewards(restored, "defeat_forest_wild")
        self.assertTrue(claim_res.success)
        self.assertEqual(claim_res.items_granted, {"potion": 1})
        self.assertEqual(restored.inventory.get_quantity("potion"), 1)
        self.assertTrue(restored_prog.rewards_claimed)


if __name__ == "__main__":
    unittest.main()
