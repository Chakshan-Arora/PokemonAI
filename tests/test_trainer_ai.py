"""
Unit tests for TrainerAIDecisionModel.
Validates tactical move selection, damage estimations, knockout prioritization,
proactive switching rules, and difficulty profile competence.
"""
import unittest
import random

from src.models.trainer import Trainer, DifficultyProfile, TrainerArchetype
from src.models.trainer_ai import (
    TrainerAIDecisionModel,
    TrainerActionType,
    TrainerDecision,
)
from src.models.pokemon import Pokemon
from src.models.species import PokemonSpecies
from src.models.personality import Personality
from src.models.attack import Attack
from src.models.pokemon_type import PokemonType
from src.data.species import (
    CHARMANDER,
    BULBASAUR,
    SQUIRTLE,
    PIKACHU,
    GEODUDE,
    GASTLY,
)
from src.data.attacks import (
    EMBER,
    FLAMETHROWER,
    WATER_GUN,
    VINE_WHIP,
    THUNDER_SHOCK,
    TACKLE,
    DEFENSE_CURL,
    POISON_POWDER,
)


class DummyBattle:
    """Mock Battle instance providing state context for AI decisions."""
    def __init__(self, current_turn: int = 1) -> None:
        self.current_turn = current_turn
        self.status_manager = None


class TestTrainerAIDecisionModel(unittest.TestCase):
    """Test suite for TrainerAIDecisionModel."""

    def setUp(self) -> None:
        self.personality = Personality(
            aggression=50,
            curiosity=50,
            fear=50,
            sociability=50,
            loyalty=50,
            confidence=50,
        )
        self.ai = TrainerAIDecisionModel(seed=42)

    def test_damage_estimation_accounts_for_type_and_stats(self) -> None:
        """Ember against Bulbasaur deals super-effective damage compared to Squirtle."""
        charmander = Pokemon(species=CHARMANDER, personality=self.personality, level=10, attacks=[EMBER])
        bulbasaur = Pokemon(species=BULBASAUR, personality=self.personality, level=10)
        squirtle = Pokemon(species=SQUIRTLE, personality=self.personality, level=10)

        dmg_vs_grass = self.ai.estimate_attack_damage(EMBER, charmander, bulbasaur)
        dmg_vs_water = self.ai.estimate_attack_damage(EMBER, charmander, squirtle)

        self.assertGreater(dmg_vs_grass, dmg_vs_water)

    def test_immunity_move_scores_zero_for_competent_ai(self) -> None:
        """Tackle (Normal) against Gastly (Ghost) scores 0 due to type immunity."""
        pikachu = Pokemon(species=PIKACHU, personality=self.personality, level=10, attacks=[TACKLE])
        gastly = Pokemon(species=GASTLY, personality=self.personality, level=10)

        score, reason = self.ai.score_attack(
            attack=TACKLE,
            attacker=pikachu,
            defender=gastly,
            difficulty=DifficultyProfile.BOSS,
        )
        self.assertEqual(score, 0.0)
        self.assertIn("immunity", reason)

    def test_knockout_move_is_prioritized(self) -> None:
        """When an attack can faint the player's Pokemon, it receives top priority score."""
        charmander = Pokemon(
            species=CHARMANDER,
            personality=self.personality,
            level=15,
            attacks=[TACKLE, FLAMETHROWER],
        )
        # Weakened opponent with only 5 HP left
        weak_opponent = Pokemon(species=BULBASAUR, personality=self.personality, level=10)
        weak_opponent.take_damage(weak_opponent.max_hp - 5)
        self.assertEqual(weak_opponent.current_hp, 5)

        score_ko, reason = self.ai.score_attack(
            attack=FLAMETHROWER,
            attacker=charmander,
            defender=weak_opponent,
            difficulty=DifficultyProfile.BOSS,
        )
        self.assertGreater(score_ko, 200.0)
        self.assertIn("knockout", reason.lower())

    def test_super_effective_scored_higher_than_resisted(self) -> None:
        """Water Gun is scored much higher against Geodude than against Bulbasaur."""
        squirtle = Pokemon(species=SQUIRTLE, personality=self.personality, level=10, attacks=[WATER_GUN])
        geodude = Pokemon(species=GEODUDE, personality=self.personality, level=10)
        bulbasaur = Pokemon(species=BULBASAUR, personality=self.personality, level=10)

        score_geodude, _ = self.ai.score_attack(
            attack=WATER_GUN,
            attacker=squirtle,
            defender=geodude,
            difficulty=DifficultyProfile.HARD,
        )
        score_bulbasaur, _ = self.ai.score_attack(
            attack=WATER_GUN,
            attacker=squirtle,
            defender=bulbasaur,
            difficulty=DifficultyProfile.HARD,
        )
        self.assertGreater(score_geodude, score_bulbasaur)

    def test_easy_ai_never_switches_proactively(self) -> None:
        """Easy difficulty trainers never execute a proactive switch."""
        mon1 = Pokemon(species=BULBASAUR, personality=self.personality, level=5, attacks=[TACKLE])
        mon2 = Pokemon(species=CHARMANDER, personality=self.personality, level=10, attacks=[EMBER])
        trainer = Trainer(
            trainer_id="easy_t",
            name="Bob",
            title="Youngster Bob",
            difficulty=DifficultyProfile.EASY,
            team=[mon1, mon2],
        )
        opponent = Pokemon(species=CHARMANDER, personality=self.personality, level=10)

        # Bulbasaur at 1 HP facing a Fire type
        mon1.take_damage(mon1.max_hp - 1)

        switch = self.ai.evaluate_switch_options(
            trainer=trainer,
            active_pokemon=mon1,
            opponent_pokemon=opponent,
            difficulty=DifficultyProfile.EASY,
            turn_number=5,
        )
        self.assertIsNone(switch)

    def test_boss_ai_counter_switches_disadvantaged_lead(self) -> None:
        """Boss AI proactively switches to a bench Pokemon with severe type advantage."""
        # Grass lead facing Fire opponent
        lead_mon = Pokemon(species=BULBASAUR, personality=self.personality, level=10, attacks=[TACKLE])
        # Water bench that resists Fire and deals super-effective STAB
        bench_mon = Pokemon(species=SQUIRTLE, personality=self.personality, level=10, attacks=[WATER_GUN])
        opponent = Pokemon(species=CHARMANDER, personality=self.personality, level=10)

        trainer = Trainer(
            trainer_id="boss_misty",
            name="Misty",
            title="Leader Misty",
            difficulty=DifficultyProfile.BOSS,
            team=[lead_mon, bench_mon],
        )

        switch = self.ai.evaluate_switch_options(
            trainer=trainer,
            active_pokemon=lead_mon,
            opponent_pokemon=opponent,
            difficulty=DifficultyProfile.BOSS,
            turn_number=3,
        )
        self.assertIsNotNone(switch)
        target_mon, _, reason = switch
        self.assertEqual(target_mon, bench_mon)
        self.assertIn("counter", reason.lower())

    def test_switch_cooldown_prevents_rapid_switching(self) -> None:
        """Trainer will not switch on the turn immediately following a previous switch."""
        lead_mon = Pokemon(species=BULBASAUR, personality=self.personality, level=10, attacks=[TACKLE])
        bench_mon = Pokemon(species=SQUIRTLE, personality=self.personality, level=10, attacks=[WATER_GUN])
        opponent = Pokemon(species=CHARMANDER, personality=self.personality, level=10)

        trainer = Trainer(
            trainer_id="boss_misty",
            name="Misty",
            title="Leader Misty",
            difficulty=DifficultyProfile.BOSS,
            team=[lead_mon, bench_mon],
        )
        # Switched on turn 3
        trainer.last_switch_turn = 3

        # On turn 4 (only 1 turn later), should refuse to switch
        switch = self.ai.evaluate_switch_options(
            trainer=trainer,
            active_pokemon=lead_mon,
            opponent_pokemon=opponent,
            difficulty=DifficultyProfile.BOSS,
            turn_number=4,
        )
        self.assertIsNone(switch)

    def test_never_switch_if_imminent_knockout_available(self) -> None:
        """Active Pokemon will not switch if it can knock out the opponent this turn."""
        lead_mon = Pokemon(species=CHARMANDER, personality=self.personality, level=15, attacks=[EMBER])
        bench_mon = Pokemon(species=SQUIRTLE, personality=self.personality, level=15, attacks=[WATER_GUN])
        # Opponent has 2 HP left
        opponent = Pokemon(species=BULBASAUR, personality=self.personality, level=10)
        opponent.take_damage(opponent.max_hp - 2)

        trainer = Trainer(
            trainer_id="boss_blaine",
            name="Blaine",
            title="Leader Blaine",
            difficulty=DifficultyProfile.BOSS,
            team=[lead_mon, bench_mon],
        )

        switch = self.ai.evaluate_switch_options(
            trainer=trainer,
            active_pokemon=lead_mon,
            opponent_pokemon=opponent,
            difficulty=DifficultyProfile.BOSS,
            turn_number=5,
        )
        self.assertIsNone(switch)

    def test_decide_action_returns_valid_attack_decision(self) -> None:
        """decide_action returns a structured TrainerDecision with selected attack."""
        lead = Pokemon(species=PIKACHU, personality=self.personality, level=10, attacks=[THUNDER_SHOCK, TACKLE])
        opp = Pokemon(species=SQUIRTLE, personality=self.personality, level=10)
        trainer = Trainer(
            trainer_id="lt_surge",
            name="Surge",
            title="Leader Surge",
            difficulty=DifficultyProfile.HARD,
            team=[lead],
        )
        battle = DummyBattle(current_turn=1)

        decision = self.ai.decide_action(
            battle=battle,
            trainer=trainer,
            active_pokemon=lead,
            opponent_pokemon=opp,
        )
        self.assertEqual(decision.action_type, TrainerActionType.ATTACK)
        self.assertIsNotNone(decision.chosen_attack)
        # Thunder Shock is super effective against Squirtle
        self.assertEqual(decision.chosen_attack.name, "Thunder Shock")
        self.assertGreater(decision.score, 0)
        self.assertIn("difficulty", decision.factors)


if __name__ == "__main__":
    unittest.main()
