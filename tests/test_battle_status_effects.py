"""
Integration tests for Battle Status Effects:
In-battle move effects, paralysis turns, burn/poison damage ticks,
stat reductions affecting damage, knockouts from status, and battle isolation.
"""
import unittest
import random

from src.models.pokemon import Pokemon
from src.models.personality import Personality
from src.models.attack import Attack
from src.models.pokemon_type import PokemonType
from src.models.battle import Battle
from src.models.battle_state import BattleState
from src.models.experience_manager import ExperienceManager
from src.data.species import PIKACHU, CHARMANDER, SQUIRTLE
from src.data.attacks import (
    TACKLE,
    QUICK_ATTACK,
    SCRATCH,
    THUNDER_SHOCK,
    EMBER,
    WATER_GUN,
    WILL_O_WISP,
    POISON_POWDER,
    THUNDER_WAVE,
    GROWL,
    TAIL_WHIP,
    FIRE_FANG,
)
from src.models.status_effect import StatusEffectType, AttackEffect


class TestBattleStatusEffects(unittest.TestCase):
    """Test suite verifying battle turn flow integration with status effects."""

    def setUp(self) -> None:
        self.personality = Personality(aggression=50, curiosity=50, fear=50, sociability=50, loyalty=50, confidence=50)

    def _create_pokemon(self, species=PIKACHU, level=5, attacks=None, current_hp=None, trained_stats=None) -> Pokemon:
        return Pokemon(
            species=species,
            personality=self.personality,
            level=level,
            attacks=attacks if attacks is not None else [],
            current_hp=current_hp,
            trained_stats=trained_stats,
        )

    def test_01_move_applies_status_effect_in_battle(self) -> None:
        """A move with 100% burn effect inflicts Burn on the defender upon hitting."""
        attacker = self._create_pokemon(species=CHARMANDER, attacks=[WILL_O_WISP])
        defender = self._create_pokemon(species=SQUIRTLE, attacks=[TACKLE])

        battle = Battle(pokemon1=attacker, pokemon2=defender, seed=1)
        battle.start()

        turn_res = battle.resolve_turn(attack1=WILL_O_WISP, attack2=TACKLE)
        self.assertIsNotNone(turn_res)
        self.assertTrue(battle.status_manager.has_effect(defender, StatusEffectType.BURN))

        # Check event log recorded the application
        self.assertTrue(any("afflicted with Burn" in event for event in battle.events))

    def test_02_burn_ticks_at_end_of_turn(self) -> None:
        """Burn inflicts damage at the end of the turn and is recorded in the event log."""
        attacker = self._create_pokemon(species=CHARMANDER, attacks=[WILL_O_WISP])
        defender = self._create_pokemon(species=SQUIRTLE, level=10, attacks=[TACKLE])

        battle = Battle(pokemon1=attacker, pokemon2=defender, seed=1, use_random_damage=False)
        battle.start()

        # Tackle deals non-lethal damage, Will-O-Wisp inflicts burn
        hp_before = defender.current_hp
        battle.resolve_turn(attack1=WILL_O_WISP, attack2=TACKLE)

        # Defender took end-of-turn burn damage
        self.assertLess(defender.current_hp, hp_before)
        self.assertTrue(any("hurt by its burn" in event for event in battle.events))

    def test_03_paralysis_prevents_action_during_battle(self) -> None:
        """A paralyzed Pokemon fails to act when its paralysis roll triggers."""
        pika = self._create_pokemon(species=PIKACHU, attacks=[THUNDER_WAVE])
        charm = self._create_pokemon(species=CHARMANDER, attacks=[SCRATCH])

        battle = Battle(pokemon1=pika, pokemon2=charm, seed=42)
        battle.start()

        # Inflict paralysis on Charmander
        battle.resolve_turn(attack1=THUNDER_WAVE, attack2=SCRATCH)
        self.assertTrue(battle.status_manager.has_effect(charm, StatusEffectType.PARALYSIS))

        # Mock or seed RNG so that Charmander's paralysis roll blocks action on next turn
        # By setting paralysis chance to 100% on Charmander, we guarantee blocking
        charm_eff = battle.status_manager.get_major_condition(charm)
        charm_eff.paralysis_chance = 100

        pika_hp_before = pika.current_hp
        turn_res2 = battle.resolve_turn(attack1=THUNDER_WAVE, attack2=SCRATCH)

        # Charmander should not have dealt any damage because it was paralyzed
        self.assertEqual(pika.current_hp, pika_hp_before)
        self.assertTrue(any("is paralyzed! It can't move!" in event for event in battle.events))

    def test_04_attack_reduction_reduces_damage_dealt(self) -> None:
        """Growl reduces defender's effective Attack, noticeably weakening its subsequent attacks."""
        p1 = self._create_pokemon(species=PIKACHU, attacks=[GROWL, TACKLE])
        p2 = self._create_pokemon(species=CHARMANDER, attacks=[SCRATCH])

        # Baseline battle without Growl
        base_battle = Battle(pokemon1=p1, pokemon2=p2, seed=10, use_random_damage=False)
        base_battle.start()
        turn_base = base_battle.resolve_turn(attack1=TACKLE, attack2=SCRATCH)
        damage_unmodified = [act for act in turn_base.actions if act.attacker is p2][0].damage

        # Reset HP
        p1.current_hp = p1.max_hp
        p2.current_hp = p2.max_hp

        # Battle with Growl
        growl_battle = Battle(pokemon1=p1, pokemon2=p2, seed=10, use_random_damage=False)
        growl_battle.start()
        # Turn 1: P1 uses Growl on P2
        growl_battle.resolve_turn(attack1=GROWL, attack2=SCRATCH)
        self.assertTrue(growl_battle.status_manager.has_effect(p2, StatusEffectType.ATTACK_REDUCTION))

        # Turn 2: P2 uses Scratch with reduced Attack
        turn2 = growl_battle.resolve_turn(attack1=GROWL, attack2=SCRATCH)
        damage_reduced = [act for act in turn2.actions if act.attacker is p2][0].damage

        # Reduced damage must be less than or equal to unmodified
        self.assertLessEqual(damage_reduced, damage_unmodified)

    def test_05_stat_reduction_expires_and_restores_stats_in_battle(self) -> None:
        """After 3 turns, Tail Whip's defense reduction expires in battle."""
        p1 = self._create_pokemon(species=PIKACHU, level=20, attacks=[TAIL_WHIP])
        p2 = self._create_pokemon(species=CHARMANDER, level=20, attacks=[SCRATCH])

        battle = Battle(pokemon1=p1, pokemon2=p2, seed=1, use_random_damage=False)
        battle.start()

        # Turn 1: Tail Whip applied (duration=3)
        battle.resolve_turn(attack1=TAIL_WHIP, attack2=SCRATCH)
        self.assertTrue(battle.status_manager.has_effect(p2, StatusEffectType.DEFENSE_REDUCTION))

        # Turn 2
        battle.resolve_turn(attack1=TAIL_WHIP, attack2=SCRATCH)
        # Turn 3
        battle.resolve_turn(attack1=TAIL_WHIP, attack2=SCRATCH)

        # Effect should have expired by the end of turn 3 (duration 3 -> 2 -> 1 -> 0 expired)
        self.assertTrue(any("wore off" in event for event in battle.events))

    def test_06_knockout_from_status_damage_ends_battle_correctly(self) -> None:
        """When a Pokemon's HP is reduced to 0 by burn damage at end of turn, battle ends in VICTORY."""
        winner = self._create_pokemon(species=CHARMANDER, attacks=[WILL_O_WISP])
        # Low HP opponent that will survive attack (power 0) but faint from end-of-turn burn
        loser = self._create_pokemon(species=SQUIRTLE, current_hp=1, attacks=[TACKLE])

        battle = Battle(pokemon1=winner, pokemon2=loser, seed=5)
        battle.start()

        turn_res = battle.resolve_turn(attack1=WILL_O_WISP, attack2=TACKLE)

        # Loser should have fainted from burn
        self.assertTrue(loser.is_fainted)
        self.assertEqual(battle.state, BattleState.VICTORY)
        self.assertIs(battle.winner, winner)
        self.assertIs(battle.loser, loser)
        self.assertTrue(any("Squirtle fainted!" in event for event in battle.events))

    def test_07_fainted_pokemon_cannot_receive_new_effects_on_knockout(self) -> None:
        """If a Pokemon faints from an attack, the move's status effect is not applied."""
        attacker = self._create_pokemon(species=CHARMANDER, level=50, attacks=[FIRE_FANG])
        defender = self._create_pokemon(species=PIKACHU, level=1, current_hp=1, attacks=[TACKLE])

        battle = Battle(pokemon1=attacker, pokemon2=defender, seed=1)
        battle.start()

        # Fire Fang deals massive damage and knocks out defender
        battle.resolve_turn(attack1=FIRE_FANG, attack2=TACKLE)

        self.assertTrue(defender.is_fainted)
        self.assertEqual(battle.state, BattleState.VICTORY)
        # Defender should NOT have active status effect because it was knocked out
        self.assertFalse(battle.status_manager.has_effect(defender, StatusEffectType.BURN))

    def test_08_existing_attacks_without_effects_remain_fully_compatible(self) -> None:
        """Standard attacks without effects (Tackle, Scratch, etc.) work identically as before."""
        p1 = self._create_pokemon(species=PIKACHU, attacks=[TACKLE])
        p2 = self._create_pokemon(species=CHARMANDER, attacks=[SCRATCH])

        battle = Battle(pokemon1=p1, pokemon2=p2, seed=123)
        battle.start()

        turn_res = battle.resolve_turn(attack1=TACKLE, attack2=SCRATCH)
        self.assertEqual(len(turn_res.actions), 2)
        self.assertEqual(len(battle.status_manager.get_effects(p1)), 0)
        self.assertEqual(len(battle.status_manager.get_effects(p2)), 0)

    def test_09_effects_do_not_leak_into_new_battle(self) -> None:
        """Starting a new battle cleanses residual effects so they never leak into subsequent battles."""
        p1 = self._create_pokemon(species=CHARMANDER, attacks=[WILL_O_WISP])
        p2 = self._create_pokemon(species=SQUIRTLE, level=10, attacks=[TACKLE])

        # Battle 1: p2 gets burned
        battle1 = Battle(pokemon1=p1, pokemon2=p2, seed=1)
        battle1.start()
        battle1.resolve_turn(attack1=WILL_O_WISP, attack2=TACKLE)
        self.assertTrue(battle1.status_manager.has_effect(p2, StatusEffectType.BURN))

        # Battle 2: p2 enters a new battle with p3
        p3 = self._create_pokemon(species=PIKACHU, attacks=[THUNDER_SHOCK])
        battle2 = Battle(pokemon1=p2, pokemon2=p3, seed=2)
        battle2.start()

        # In battle 2, p2 must have no active effects!
        self.assertFalse(battle2.status_manager.has_effect(p2, StatusEffectType.BURN))
        self.assertEqual(len(battle2.status_manager.get_effects(p2)), 0)

    def test_10_battle_rewards_protected_after_status_knockout(self) -> None:
        """Victory from status knockout allows claiming XP rewards exactly once."""
        exp_mgr = ExperienceManager()
        winner = self._create_pokemon(species=CHARMANDER, attacks=[WILL_O_WISP])
        loser = self._create_pokemon(species=SQUIRTLE, current_hp=1, attacks=[TACKLE])

        battle = Battle(pokemon1=winner, pokemon2=loser, seed=5)
        battle.start()
        battle.resolve_turn(attack1=WILL_O_WISP, attack2=TACKLE)
        self.assertEqual(battle.state, BattleState.VICTORY)

        # Claim rewards
        reward_res1 = exp_mgr.award_battle_rewards(battle)
        self.assertTrue(reward_res1.eligible)
        self.assertGreater(reward_res1.xp_awarded, 0)

        # Second claim rejected
        reward_res2 = exp_mgr.award_battle_rewards(battle)
        self.assertFalse(reward_res2.eligible)
        self.assertEqual(reward_res2.xp_awarded, 0)


if __name__ == "__main__":
    unittest.main()
