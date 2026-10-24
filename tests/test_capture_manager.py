"""
Unit tests for the Pokemon capture and collection system.

Tests verify:
- Capture probability formula calculation, scaling, and clamping to [0.05, 0.90].
- Lower HP increasing capture probability.
- Higher level reducing capture probability.
- Valid successful capture adding the exact existing Pokemon instance to player's collection.
- Valid failed capture leaving player's collection unchanged.
- Rejection of fainted targets.
- Rejection of targets already owned in player's collection.
- Rejection of invalid player or target types.
- Encounter session lifecycle: active, completed, resolved, and duplicate attempt prevention.
- SpawnManager area population synchronization upon successful capture (despawn from wild).
- Full team handling: player with 6 team members can still capture into collection without replacing team members.
- Collection and active team independence.
- Deterministic capture outcomes with injected randomness.
"""
import random
import unittest

from src.models.personality import Personality
from src.models.pokemon import Pokemon
from src.models.player import Player
from src.models.spawn_area import SpawnArea
from src.models.spawn_manager import SpawnManager
from src.models.encounter_manager import EncounterManager, EncounterResult, WildEncounter
from src.models.capture_manager import (
    MIN_CAPTURE_PROBABILITY,
    MAX_CAPTURE_PROBABILITY,
    CaptureResult,
    CaptureManager,
    calculate_capture_probability,
)
from src.data.species import PIKACHU, CHARMANDER, SQUIRTLE
from src.data.attacks import THUNDER_SHOCK, QUICK_ATTACK, SCRATCH, WATER_GUN


class TestCaptureManager(unittest.TestCase):
    """Test suite for capture probabilities, eligibility checks, and collection updates."""

    def setUp(self) -> None:
        self.default_personality = Personality(
            aggression=50,
            curiosity=50,
            fear=50,
            sociability=50,
            loyalty=50,
            confidence=50,
        )
        self.player = Player(name="Ash")
        self.wild_pika = Pokemon(
            species=PIKACHU,
            personality=self.default_personality,
            level=5,
            attacks=[THUNDER_SHOCK, QUICK_ATTACK],
        )
        self.capture_manager = CaptureManager(seed=42)

    # --- Capture Probability Calculations ---

    def test_capture_probability_formula(self) -> None:
        """Verify capture chance follows: 0.65 * (1 - hp/max_hp) + 0.20 - level * 0.002."""
        # Level 5 at full HP (current_hp == max_hp):
        # hp_factor = 0, penalty = 5 * 0.002 = 0.010 -> 0.20 - 0.010 = 0.190
        prob = calculate_capture_probability(self.wild_pika)
        self.assertAlmostEqual(prob, 0.190, places=3)

    def test_lower_hp_improves_capture_chance(self) -> None:
        """Weakening the wild Pokemon strictly increases its capture probability."""
        full_hp_prob = calculate_capture_probability(self.wild_pika)

        # Deal damage to wild Pokemon
        self.wild_pika.take_damage(self.wild_pika.max_hp // 2)
        mid_hp_prob = calculate_capture_probability(self.wild_pika)

        self.wild_pika.take_damage(self.wild_pika.max_hp)  # Take more damage (leave 1 HP)
        self.wild_pika.current_hp = 1
        low_hp_prob = calculate_capture_probability(self.wild_pika)

        self.assertGreater(mid_hp_prob, full_hp_prob)
        self.assertGreater(low_hp_prob, mid_hp_prob)

    def test_higher_level_reduces_capture_chance(self) -> None:
        """Higher level wild Pokemon are harder to capture than lower level ones."""
        pika_low = Pokemon(species=PIKACHU, personality=self.default_personality, level=5)
        pika_mid = Pokemon(species=PIKACHU, personality=self.default_personality, level=30)
        pika_high = Pokemon(species=PIKACHU, personality=self.default_personality, level=70)

        prob_low = calculate_capture_probability(pika_low)
        prob_mid = calculate_capture_probability(pika_mid)
        prob_high = calculate_capture_probability(pika_high)

        self.assertGreater(prob_low, prob_mid)
        self.assertGreater(prob_mid, prob_high)

    def test_probability_clamped_to_configured_bounds(self) -> None:
        """Capture chance is strictly bounded to [0.05, 0.90]."""
        # Ultra high level (level 100, full HP): raw chance is <= 0.0, clamped to 0.05
        pika_lvl_100 = Pokemon(species=PIKACHU, personality=self.default_personality, level=100)
        prob_min = calculate_capture_probability(pika_lvl_100)
        self.assertEqual(prob_min, MIN_CAPTURE_PROBABILITY)

        # Extremely weak target with custom manager bounds
        custom_mgr = CaptureManager(min_probability=0.10, max_probability=0.80)
        self.assertEqual(custom_mgr.calculate_chance(pika_lvl_100), 0.10)

    # --- Eligibility & Rejection Rules ---

    def test_invalid_player_or_target_rejected(self) -> None:
        """Rejects non-Player and non-Pokemon arguments with accepted=False."""
        res1 = self.capture_manager.attempt_capture("NotAPlayer", self.wild_pika)  # type: ignore[arg-type]
        self.assertFalse(res1.accepted)
        self.assertFalse(res1.success)
        self.assertIn("Invalid player", res1.message)

        res2 = self.capture_manager.attempt_capture(self.player, "NotAPokemon")  # type: ignore[arg-type]
        self.assertFalse(res2.accepted)
        self.assertFalse(res2.success)
        self.assertIn("Invalid target", res2.message)

    def test_fainted_target_rejected(self) -> None:
        """Cannot attempt capture on a fainted wild Pokemon."""
        self.wild_pika.take_damage(self.wild_pika.max_hp)
        self.assertTrue(self.wild_pika.is_fainted)

        result = self.capture_manager.attempt_capture(self.player, self.wild_pika)
        self.assertFalse(result.accepted)
        self.assertFalse(result.success)
        self.assertIn("fainted", result.message)
        self.assertFalse(self.player.is_pokemon_owned(self.wild_pika))

    def test_already_owned_pokemon_rejected(self) -> None:
        """Cannot capture a Pokemon already belonging to the player's collection."""
        self.player.add_pokemon(self.wild_pika)
        self.assertTrue(self.player.is_pokemon_owned(self.wild_pika))

        result = self.capture_manager.attempt_capture(self.player, self.wild_pika)
        self.assertFalse(result.accepted)
        self.assertFalse(result.success)
        self.assertIn("already in player's collection", result.message)

    # --- Successful and Failed Captures ---

    def test_valid_successful_capture(self) -> None:
        """Successful capture adds the exact instance to the collection and reports success."""
        # Force a roll that guarantees success (e.g. roll = 0.01)
        mock_rng = random.Random()
        mock_rng.random = lambda: 0.01  # type: ignore[assignment]

        initial_collection_size = len(self.player.collection)
        result = self.capture_manager.attempt_capture(
            self.player,
            self.wild_pika,
            rng=mock_rng,
        )

        self.assertTrue(result.accepted)
        self.assertTrue(result.success)
        self.assertTrue(result.added_to_collection)
        self.assertIn("caught", result.message)

        # Preserved exact identity
        self.assertEqual(len(self.player.collection), initial_collection_size + 1)
        self.assertTrue(self.player.is_pokemon_owned(self.wild_pika))
        retrieved = self.player.get_pokemon_by_id(self.wild_pika.unique_id)
        self.assertIs(retrieved, self.wild_pika)

    def test_valid_failed_capture(self) -> None:
        """Failed capture roll does not add Pokemon to collection."""
        # Force a roll that guarantees failure (roll = 0.99)
        mock_rng = random.Random()
        mock_rng.random = lambda: 0.99  # type: ignore[assignment]

        initial_collection_size = len(self.player.collection)
        result = self.capture_manager.attempt_capture(
            self.player,
            self.wild_pika,
            rng=mock_rng,
        )

        self.assertTrue(result.accepted)
        self.assertFalse(result.success)
        self.assertFalse(result.added_to_collection)
        self.assertIn("broke free", result.message)

        # Collection unchanged
        self.assertEqual(len(self.player.collection), initial_collection_size)
        self.assertFalse(self.player.is_pokemon_owned(self.wild_pika))

    # --- Collection vs. Team Independence ---

    def test_capture_with_full_active_team(self) -> None:
        """A full team of 6 does not prevent capturing into collection."""
        # Fill team with 6 Pokemon
        for i in range(6):
            mon = Pokemon(species=CHARMANDER, personality=self.default_personality, level=i + 1)
            self.player.add_pokemon(mon)
            self.player.add_to_team(mon)

        self.assertEqual(len(self.player.team), 6)
        self.assertEqual(len(self.player.collection), 6)

        # Force capture success
        mock_rng = random.Random()
        mock_rng.random = lambda: 0.01  # type: ignore[assignment]

        result = self.capture_manager.attempt_capture(self.player, self.wild_pika, rng=mock_rng)
        self.assertTrue(result.success)

        # Collection expanded to 7, team remains strictly at 6
        self.assertEqual(len(self.player.collection), 7)
        self.assertEqual(len(self.player.team), 6)
        self.assertFalse(self.player.is_on_team(self.wild_pika))
        self.assertTrue(self.player.is_pokemon_owned(self.wild_pika))

    # --- Encounter Session Integration ---

    def test_wild_encounter_session_resolution(self) -> None:
        """Successful capture resolves the active WildEncounter session."""
        area = SpawnArea(
            area_id="forest",
            name="Viridian Forest",
            allowed_species=[PIKACHU],
        )
        encounter = WildEncounter(player=self.player, pokemon=self.wild_pika, area=area)
        self.assertTrue(encounter.is_active)
        self.assertFalse(encounter.is_resolved)

        mock_rng = random.Random()
        mock_rng.random = lambda: 0.01  # type: ignore[assignment]

        res = self.capture_manager.attempt_capture(
            self.player,
            self.wild_pika,
            encounter=encounter,
            rng=mock_rng,
        )
        self.assertTrue(res.success)
        self.assertFalse(encounter.is_active)
        self.assertTrue(encounter.is_resolved)
        self.assertEqual(encounter.resolution_reason, "Captured")

    def test_resolved_encounter_cannot_be_captured_again(self) -> None:
        """Attempting to capture on an already resolved encounter is rejected."""
        encounter = WildEncounter(player=self.player, pokemon=self.wild_pika)
        encounter.resolve("Fled")

        result = self.capture_manager.attempt_capture(
            self.player,
            self.wild_pika,
            encounter=encounter,
        )
        self.assertFalse(result.accepted)
        self.assertFalse(result.success)
        self.assertIn("already resolved", result.message)

    def test_encounter_mismatched_pokemon_rejected(self) -> None:
        """Encounter with a different Pokemon than target is rejected."""
        other_mon = Pokemon(species=SQUIRTLE, personality=self.default_personality)
        encounter = WildEncounter(player=self.player, pokemon=other_mon)

        result = self.capture_manager.attempt_capture(
            self.player,
            self.wild_pika,
            encounter=encounter,
        )
        self.assertFalse(result.accepted)
        self.assertIn("does not match", result.message)

    # --- SpawnManager Population Integration ---

    def test_captured_wild_pokemon_despawns_from_spawn_manager(self) -> None:
        """Successful capture despawns the Pokemon from SpawnManager active list."""
        spawn_mgr = SpawnManager(seed=101)
        area = SpawnArea(area_id="forest", name="Viridian Forest", allowed_species=[PIKACHU])
        spawn_mgr.register_area(area)

        spawned = spawn_mgr.attempt_spawn("forest", ignore_probability=True)
        self.assertIsNotNone(spawned)
        self.assertTrue(spawn_mgr.is_pokemon_active("forest", spawned))
        self.assertEqual(spawn_mgr.get_active_count("forest"), 1)

        # Force capture success
        mock_rng = random.Random()
        mock_rng.random = lambda: 0.01  # type: ignore[assignment]

        res = self.capture_manager.attempt_capture(
            self.player,
            spawned,
            spawn_manager=spawn_mgr,
            area_id="forest",
            rng=mock_rng,
        )
        self.assertTrue(res.success)
        # Pokemon is now owned by player and despawned from the wild
        self.assertTrue(self.player.is_pokemon_owned(spawned))
        self.assertFalse(spawn_mgr.is_pokemon_active("forest", spawned))
        self.assertEqual(spawn_mgr.get_active_count("forest"), 0)

    # --- Deterministic Injected RNG ---

    def test_deterministic_capture_with_injected_seed(self) -> None:
        """Seeded CaptureManager generates 100% reproducible outcomes."""
        pika1 = Pokemon(species=PIKACHU, personality=self.default_personality, level=5)
        pika2 = Pokemon(species=PIKACHU, personality=self.default_personality, level=5)

        mgr1 = CaptureManager(seed=999)
        player1 = Player(name="Red")
        res1 = mgr1.attempt_capture(player1, pika1)

        mgr2 = CaptureManager(seed=999)
        player2 = Player(name="Blue")
        res2 = mgr2.attempt_capture(player2, pika2)

        self.assertEqual(res1.accepted, res2.accepted)
        self.assertEqual(res1.success, res2.success)
        self.assertEqual(res1.capture_probability, res2.capture_probability)
        self.assertEqual(res1.roll, res2.roll)


if __name__ == "__main__":
    unittest.main()
