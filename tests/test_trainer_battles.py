"""
End-to-end and integration tests for Dynamic AI-Controlled Trainer Battles.
Validates battle initiation, tactical AI turns, proactive mid-battle switching,
post-KO team rotations, defeat recording, and reward distribution.
"""
import unittest

from src.models.trainer import Trainer, DifficultyProfile, TrainerArchetype
from src.models.trainer_team_generator import create_trainer, TrainerTeamGenerator
from src.models.trainer_ai import TrainerAIDecisionModel, TrainerActionType
from src.models.battle import Battle, BattleAction, BattleActionType, BattleState
from src.models.battle_manager import BattleManager
from src.models.player import Player
from src.models.pokemon import Pokemon
from src.models.personality import Personality
from src.data.species import (
    CHARMANDER,
    BULBASAUR,
    SQUIRTLE,
    PIKACHU,
    GEODUDE,
)
from src.data.attacks import (
    TACKLE,
    EMBER,
    WATER_GUN,
    VINE_WHIP,
    THUNDER_SHOCK,
    QUICK_ATTACK,
)


class TestTrainerBattles(unittest.TestCase):
    """Test suite for integrated AI trainer battles."""

    def setUp(self) -> None:
        self.personality = Personality(
            aggression=50,
            curiosity=50,
            fear=50,
            sociability=50,
            loyalty=50,
            confidence=50,
        )
        self.player = Player(name="Ash")
        self.player_pikachu = Pokemon(
            species=PIKACHU,
            personality=self.personality,
            level=12,
            attacks=[THUNDER_SHOCK, QUICK_ATTACK, TACKLE],
        )
        self.player.add_pokemon(self.player_pikachu)
        self.player.add_to_team(self.player_pikachu)
        self.player.set_active_pokemon(self.player_pikachu)

        self.battle_manager = BattleManager(seed=42)

    def test_start_trainer_battle_generates_team_if_unpopulated(self) -> None:
        """Starting a trainer battle against an unpopulated trainer generates their team on the fly."""
        trainer = Trainer(
            trainer_id="youngster_joey",
            name="Joey",
            title="Youngster Joey",
            archetype=TrainerArchetype.YOUNGSTER,
            difficulty=DifficultyProfile.NORMAL,
            region_id="starting_meadow",
        )
        self.assertFalse(trainer.has_team)

        battle = self.battle_manager.start_trainer_battle(
            player=self.player,
            opponent_trainer=trainer,
            seed=10,
        )

        self.assertTrue(trainer.has_team)
        self.assertIsNotNone(trainer.active_pokemon)
        self.assertEqual(battle.pokemon2, trainer.active_pokemon)
        self.assertTrue(battle.is_trainer_battle)
        self.assertEqual(battle.state, BattleState.IN_PROGRESS)
        self.assertTrue(self.battle_manager.has_active_battle(self.player))

    def test_trainer_battle_singleton_enforcement(self) -> None:
        """A player cannot engage in two trainer battles concurrently."""
        trainer1 = create_trainer("t1", "Joey", "Youngster", seed=1)
        trainer2 = create_trainer("t2", "Haley", "Lass", seed=2)

        self.battle_manager.start_trainer_battle(self.player, trainer1)
        with self.assertRaises(RuntimeError):
            self.battle_manager.start_trainer_battle(self.player, trainer2)

    def test_ai_controlled_opponent_selects_effective_move(self) -> None:
        """In battle turn execution, AI opponent chooses super-effective move (Ember vs Bulbasaur)."""
        # Player has Grass type
        player_mon = Pokemon(species=BULBASAUR, personality=self.personality, level=10, attacks=[TACKLE])
        self.player.add_pokemon(player_mon)
        self.player.set_active_pokemon(player_mon)

        # Trainer has Fire type with Tackle and Ember
        opponent_mon = Pokemon(
            species=CHARMANDER,
            personality=self.personality,
            level=10,
            attacks=[TACKLE, EMBER],
        )
        trainer = Trainer(
            trainer_id="camper_chris",
            name="Chris",
            title="Camper Chris",
            difficulty=DifficultyProfile.HARD,
            team=[opponent_mon],
        )

        battle = self.battle_manager.start_trainer_battle(
            player=self.player,
            opponent_trainer=trainer,
            seed=42,
        )

        # Player attacks with Tackle
        result = battle.take_action(BattleAction(action_type=BattleActionType.ATTACK, attack=TACKLE))
        self.assertTrue(result.accepted)

        # Check turn actions: Opponent should have executed Ember (super effective against Grass)
        actions = result.turn_result.actions
        opp_action = [a for a in actions if a.attacker is opponent_mon]
        self.assertTrue(len(opp_action) > 0)
        self.assertEqual(opp_action[0].attack.name, "Ember")
        self.assertGreater(opp_action[0].type_effectiveness, 1.0)

    def test_proactive_mid_battle_switching_by_boss_ai(self) -> None:
        """Boss AI proactively switches away from a severe type disadvantage to counter the player."""
        # Player has Electric lead (Pikachu)
        # Trainer has Water lead (Squirtle) and Ground bench (Geodude)
        # Squirtle is weak to Electric; Geodude is immune to Electric!
        trainer_squirtle = Pokemon(species=SQUIRTLE, personality=self.personality, level=10, attacks=[TACKLE])
        trainer_geodude = Pokemon(species=GEODUDE, personality=self.personality, level=10, attacks=[TACKLE])

        trainer = Trainer(
            trainer_id="boss_brock",
            name="Brock",
            title="Leader Brock",
            difficulty=DifficultyProfile.BOSS,
            team=[trainer_squirtle, trainer_geodude],
        )

        battle = self.battle_manager.start_trainer_battle(
            player=self.player,
            opponent_trainer=trainer,
            seed=42,
        )
        self.assertEqual(battle.pokemon2, trainer_squirtle)

        # Player attacks with Thunder Shock. Boss AI should evaluate that Squirtle is in danger
        # and switch to Geodude!
        result = battle.take_action(BattleAction(action_type=BattleActionType.ATTACK, attack=THUNDER_SHOCK))
        self.assertTrue(result.accepted)

        # Verify that opponent switched to Geodude
        self.assertEqual(battle.pokemon2, trainer_geodude)
        self.assertEqual(trainer.active_pokemon, trainer_geodude)

        # Pikachu's Thunder Shock hits incoming Geodude, which is Ground type (0x effectiveness!)
        actions = result.turn_result.actions
        player_hit = [a for a in actions if a.attacker is self.player_pikachu]
        self.assertTrue(len(player_hit) > 0)
        self.assertEqual(player_hit[0].defender, trainer_geodude)
        self.assertEqual(player_hit[0].type_effectiveness, 0.0)

    def test_post_ko_opponent_rotates_next_conscious_pokemon(self) -> None:
        """When an opponent Pokemon faints, the trainer sends out their next conscious Pokemon."""
        # Weak opponent mon that will faint from 1 high-power hit
        opp_mon1 = Pokemon(species=BULBASAUR, personality=self.personality, level=1, attacks=[TACKLE])
        opp_mon2 = Pokemon(species=CHARMANDER, personality=self.personality, level=10, attacks=[EMBER])

        trainer = Trainer(
            trainer_id="ace_dave",
            name="Dave",
            title="Ace Dave",
            difficulty=DifficultyProfile.NORMAL,
            team=[opp_mon1, opp_mon2],
        )

        # Give player a strong attack to faint opp_mon1 in 1 hit
        strong_pikachu = Pokemon(
            species=PIKACHU,
            personality=self.personality,
            level=30,
            attacks=[THUNDER_SHOCK],
        )
        self.player.add_pokemon(strong_pikachu)
        self.player.set_active_pokemon(strong_pikachu)

        battle = self.battle_manager.start_trainer_battle(
            player=self.player,
            opponent_trainer=trainer,
            seed=42,
        )
        self.assertEqual(battle.pokemon2, opp_mon1)

        # Set opponent to 1 HP so any hit will faint it
        opp_mon1.take_damage(opp_mon1.max_hp - 1)
        self.assertEqual(opp_mon1.current_hp, 1)

        result = battle.take_action(BattleAction(action_type=BattleActionType.ATTACK, attack=THUNDER_SHOCK))
        self.assertTrue(result.accepted)
        self.assertTrue(opp_mon1.is_fainted)

        # Battle should still be in progress because opp_mon2 is alive
        self.assertEqual(battle.state, BattleState.IN_PROGRESS)
        # opp_mon2 should now be active
        self.assertEqual(battle.pokemon2, opp_mon2)
        self.assertEqual(trainer.active_pokemon, opp_mon2)

    def test_full_trainer_defeat_records_victory_and_awards_items(self) -> None:
        """When all opponent Pokemon faint, player wins, defeat is recorded, and rewards are granted."""
        opp_mon = Pokemon(species=BULBASAUR, personality=self.personality, level=1, attacks=[TACKLE])
        trainer = Trainer(
            trainer_id="youngster_ben",
            name="Ben",
            title="Youngster Ben",
            difficulty=DifficultyProfile.EASY,
            team=[opp_mon],
            reward_items={"poke_ball": 3, "potion": 1},
        )

        strong_pikachu = Pokemon(
            species=PIKACHU,
            personality=self.personality,
            level=30,
            attacks=[THUNDER_SHOCK],
        )
        self.player.add_pokemon(strong_pikachu)
        self.player.set_active_pokemon(strong_pikachu)

        battle = self.battle_manager.start_trainer_battle(
            player=self.player,
            opponent_trainer=trainer,
            seed=42,
        )

        # Set opponent to 1 HP so any hit will faint it
        opp_mon.take_damage(opp_mon.max_hp - 1)
        self.assertEqual(opp_mon.current_hp, 1)

        # Player KO's Ben's only Pokemon through BattleManager
        result = self.battle_manager.attack(self.player, THUNDER_SHOCK)
        self.assertTrue(result.accepted)
        self.assertEqual(battle.state, BattleState.VICTORY)

        # Battle concluded cleanup
        self.assertFalse(self.battle_manager.has_active_battle(self.player))

        # Trainer defeat status
        self.assertTrue(trainer.is_defeated)
        self.assertEqual(trainer.defeat_count, 1)
        self.assertTrue(trainer.reward_claimed)

        # Rewards deposited to player inventory
        self.assertEqual(self.player.inventory.get_quantity("poke_ball"), 3)
        self.assertEqual(self.player.inventory.get_quantity("potion"), 1)

        # Rewards cannot be claimed twice
        second_claim = trainer.claim_rewards(self.player)
        self.assertEqual(second_claim, {})


if __name__ == "__main__":
    unittest.main()
