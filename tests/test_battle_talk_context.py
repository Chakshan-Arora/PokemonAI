"""
Unit tests for context-aware Battle Talk dialogue generation (BT5.2A).

Verifies:
1. Low HP (<= 25%) contextual dialogue differentiation across personalities.
2. Healthy baseline preservation for uninjured Pokemon (> 25% HP).
3. Status condition awareness (e.g. paralysis).
4. Event context awareness (e.g. dodge success vs. dodge failure).
5. Invariants: no mutation of Pokemon attributes, combat state, stats, or RNG.
"""
import random
import unittest

from src.models.pokemon import Pokemon
from src.models.personality import Personality
from src.models.battle import (
    Battle,
    BattleAction,
    BattleActionType,
    BattleActionRecord,
    BattleTalkCommand,
    BattleTalkIntent,
    TurnResult,
)
from src.models.battle_state import BattleState
from src.models.player import Player
from src.data.species import CHARMANDER
from src.data.attacks import EMBER, SCRATCH
from src.models.status_effect import StatusEffect, StatusEffectType
from src.ai.companion_service import (
    CompanionService,
    BattleTalkContext,
    generate_battle_talk_response,
)
from src.data.species import PIKACHU
from src.data.attacks import THUNDER_SHOCK, QUICK_ATTACK


class TestBattleTalkContext(unittest.TestCase):
    """Test suite verifying context-sensitive dialogue generation."""

    def setUp(self) -> None:
        self.default_personality = Personality(
            aggression=50, curiosity=50, fear=50, sociability=50, loyalty=50, confidence=50
        )
        self.pika = Pokemon(
            species=PIKACHU,
            personality=self.default_personality,
            level=5,
            attacks=[THUNDER_SHOCK, QUICK_ATTACK],
        )

    def test_01_healthy_baseline_preserved(self) -> None:
        """When HP is above 25% and no status exists, standard personality templates are used."""
        cmd = BattleTalkCommand(text="Good job!", intent=BattleTalkIntent.PRAISE)
        # Full HP
        self.assertEqual(self.pika.current_hp, self.pika.max_hp)
        resp_healthy = generate_battle_talk_response(self.pika, cmd)
        self.assertIn("smiles warmly", resp_healthy.lower())

    def test_02_low_hp_differentiation_high_confidence(self) -> None:
        """High confidence Pokemon shows defiance/smirks when low on HP instead of ordinary pride."""
        high_conf = Pokemon(
            species=PIKACHU,
            personality=Personality(confidence=85, fear=50, aggression=50, loyalty=50, curiosity=50, sociability=50),
            level=5,
        )
        cmd = BattleTalkCommand(text="Hang in there!", intent=BattleTalkIntent.ENCOURAGE)

        # Healthy
        resp_healthy = generate_battle_talk_response(high_conf, cmd)
        self.assertIn("completely under control", resp_healthy.lower())

        # Low HP via explicit context
        ctx_low = BattleTalkContext(hp_percent=0.15)
        resp_low_ctx = generate_battle_talk_response(high_conf, cmd, context=ctx_low)
        self.assertIn("still fight", resp_low_ctx.lower())
        self.assertNotEqual(resp_healthy, resp_low_ctx)

        # Low HP automatically deduced from Pokemon current_hp
        high_conf.take_damage(high_conf.max_hp - 1)  # 1 HP left (<= 25%)
        self.assertLessEqual(high_conf.current_hp / high_conf.max_hp, 0.25)
        resp_low_auto = generate_battle_talk_response(high_conf, cmd)
        self.assertEqual(resp_low_ctx, resp_low_auto)

    def test_03_low_hp_differentiation_high_fear(self) -> None:
        """High fear Pokemon shows panic/desperation when low on HP."""
        high_fear = Pokemon(
            species=PIKACHU,
            personality=Personality(confidence=50, fear=85, aggression=50, loyalty=50, curiosity=50, sociability=50),
            level=5,
        )
        cmd = BattleTalkCommand(text="Hang in there!", intent=BattleTalkIntent.ENCOURAGE)

        resp_healthy = generate_battle_talk_response(high_fear, cmd)
        self.assertIn("steady its shaking paws", resp_healthy.lower())

        high_fear.take_damage(high_fear.max_hp - 2)
        resp_low = generate_battle_talk_response(high_fear, cmd)
        self.assertIn("desperate", resp_low.lower())
        self.assertNotEqual(resp_healthy, resp_low)

    def test_04_low_hp_differentiation_high_loyalty(self) -> None:
        """High loyalty Pokemon pledges to fight until the end for the trainer when critically hurt."""
        high_loyalty = Pokemon(
            species=PIKACHU,
            personality=Personality(confidence=50, fear=50, aggression=50, loyalty=85, curiosity=50, sociability=50),
            level=5,
        )
        cmd = BattleTalkCommand(text="Good job!", intent=BattleTalkIntent.PRAISE)

        resp_healthy = generate_battle_talk_response(high_loyalty, cmd)
        self.assertIn("devoted eyes", resp_healthy.lower())

        high_loyalty.take_damage(high_loyalty.max_hp - 1)
        resp_low = generate_battle_talk_response(high_loyalty, cmd)
        self.assertIn("until the very end", resp_low.lower())
        self.assertNotEqual(resp_healthy, resp_low)

    def test_05_paralysis_status_awareness(self) -> None:
        """Paralyzed Pokemon acknowledges sparks and stiffness tailored to its personality."""
        high_conf = Pokemon(
            species=PIKACHU,
            personality=Personality(confidence=85, fear=50, aggression=50, loyalty=50, curiosity=50, sociability=50),
            level=5,
        )
        high_conf.add_status_effect(StatusEffect(StatusEffectType.PARALYSIS))

        cmd = BattleTalkCommand(text="Watch out!", intent=BattleTalkIntent.WARNING)
        resp = generate_battle_talk_response(high_conf, cmd)
        self.assertIn("won't stop me", resp.lower())

    def test_06_event_reaction_dodge_success_and_failure(self) -> None:
        """Recent dodge events elicit appropriate reactions without contradictory claims."""
        high_conf = Pokemon(
            species=PIKACHU,
            personality=Personality(confidence=85, fear=50, aggression=50, loyalty=50, curiosity=50, sociability=50),
            level=5,
        )
        cmd = BattleTalkCommand(text="Hello", intent=BattleTalkIntent.GENERAL)

        # Success event
        ctx_success = BattleTalkContext(last_event="dodge_success")
        resp_succ = generate_battle_talk_response(high_conf, cmd, context=ctx_success)
        self.assertIn("scratch", resp_succ.lower())

        # Failed event
        ctx_failed = BattleTalkContext(last_event="dodge_failed")
        resp_fail = generate_battle_talk_response(high_conf, cmd, context=ctx_failed)
        self.assertIn("lucky hit", resp_fail.lower())
        self.assertNotIn("scratch", resp_fail.lower())

    def test_07_invariants_preserved_with_context(self) -> None:
        """Context-aware generation does not mutate Pokemon HP, bond, obedience, or RNG."""
        rng = random.Random(9999)
        expected_roll = rng.randint(1, 1000)
        test_rng = random.Random(9999)

        hp_before = self.pika.current_hp
        bond_before = self.pika.bond
        ob_before = self.pika.obedience
        pers_before = self.pika.personality.to_dict()

        ctx = BattleTalkContext(hp_percent=0.10, status_condition="paralysis", last_event="dodge_success")
        generate_battle_talk_response(self.pika, "Hang in there!", context=ctx)

        self.assertEqual(self.pika.current_hp, hp_before)
        self.assertEqual(self.pika.bond, bond_before)
        self.assertEqual(self.pika.obedience, ob_before)
        self.assertEqual(self.pika.personality.to_dict(), pers_before)
        self.assertEqual(test_rng.randint(1, 1000), expected_roll)

    # --- BT5.3B Combat Milestone Reactions ---

    def test_08_opponent_knockout_reaction(self) -> None:
        """Opponent knockout triggers celebratory reaction reflecting personality."""
        high_conf = Pokemon(
            species=PIKACHU,
            personality=Personality(confidence=85, fear=50, aggression=50, loyalty=50, curiosity=50, sociability=50),
            level=5,
        )
        high_fear = Pokemon(
            species=PIKACHU,
            personality=Personality(confidence=50, fear=85, aggression=50, loyalty=50, curiosity=50, sociability=50),
            level=5,
        )
        high_loy = Pokemon(
            species=PIKACHU,
            personality=Personality(confidence=50, fear=50, aggression=50, loyalty=85, curiosity=50, sociability=50),
            level=5,
        )
        cmd = BattleTalkCommand(text="Great job!", intent=BattleTalkIntent.PRAISE)
        ctx = BattleTalkContext(is_opponent_knockout=True)

        resp_conf = generate_battle_talk_response(high_conf, cmd, context=ctx)
        resp_fear = generate_battle_talk_response(high_fear, cmd, context=ctx)
        resp_loy = generate_battle_talk_response(high_loy, cmd, context=ctx)

        self.assertIn("down for the count", resp_conf.lower())
        self.assertIn("relief", resp_fear.lower())
        self.assertIn("target neutralized", resp_loy.lower())

    def test_09_super_effective_reaction(self) -> None:
        """Super-effective hit triggers type-advantage awareness."""
        high_cur = Pokemon(
            species=PIKACHU,
            personality=Personality(confidence=50, fear=50, aggression=50, loyalty=50, curiosity=85, sociability=50),
            level=5,
        )
        cmd = BattleTalkCommand(text="Nice move!", intent=BattleTalkIntent.GENERAL)
        ctx = BattleTalkContext(is_super_effective=True)

        resp = generate_battle_talk_response(high_cur, cmd, context=ctx)
        self.assertIn("matchup", resp.lower())

    def test_10_critical_hit_reaction(self) -> None:
        """Critical hit triggers precision impact acknowledgement."""
        high_conf = Pokemon(
            species=PIKACHU,
            personality=Personality(confidence=85, fear=50, aggression=50, loyalty=50, curiosity=50, sociability=50),
            level=5,
        )
        cmd = BattleTalkCommand(text="Awesome!", intent=BattleTalkIntent.GENERAL)
        ctx = BattleTalkContext(is_critical_hit=True)

        resp = generate_battle_talk_response(high_conf, cmd, context=ctx)
        self.assertIn("sweet spot", resp.lower())

    def test_11_combined_critical_and_super_effective_reaction(self) -> None:
        """Combined critical and super-effective hit triggers devastating combo reaction."""
        high_agg = Pokemon(
            species=PIKACHU,
            personality=Personality(confidence=50, fear=50, aggression=85, loyalty=50, curiosity=50, sociability=50),
            level=5,
        )
        cmd = BattleTalkCommand(text="Take that!", intent=BattleTalkIntent.GENERAL)
        ctx = BattleTalkContext(is_critical_hit=True, is_super_effective=True)

        resp = generate_battle_talk_response(high_agg, cmd, context=ctx)
        self.assertIn("annihilation", resp.lower())

    def test_12_knockout_takes_precedence_over_critical_and_super_effective(self) -> None:
        """When an attack causes a knockout and was also crit + super-effective, knockout takes priority."""
        high_conf = Pokemon(
            species=PIKACHU,
            personality=Personality(confidence=85, fear=50, aggression=50, loyalty=50, curiosity=50, sociability=50),
            level=5,
        )
        cmd = BattleTalkCommand(text="Good hit!", intent=BattleTalkIntent.PRAISE)
        ctx = BattleTalkContext(is_opponent_knockout=True, is_critical_hit=True, is_super_effective=True)

        resp = generate_battle_talk_response(high_conf, cmd, context=ctx)
        # Must resolve to knockout, not critical or super-effective
        self.assertIn("down for the count", resp.lower())

    def test_13_structured_history_milestone_detection_and_attribution(self) -> None:
        """Battle.get_latest_player_combat_milestone() correctly attributes player actions and ignores opponent actions."""
        pika = Pokemon(species=PIKACHU, personality=self.default_personality, level=5, attacks=[THUNDER_SHOCK])
        charm = Pokemon(species=CHARMANDER, personality=self.default_personality, level=5, attacks=[EMBER])
        battle = Battle(pokemon1=pika, pokemon2=charm, seed=42)
        battle.start()

        # No history initially
        self.assertIsNone(battle.get_latest_player_combat_milestone())

        # Simulate turn 1 with opponent-caused critical hit
        opp_record = BattleActionRecord(
            attacker=charm,
            defender=pika,
            attack=EMBER,
            hit=True,
            damage=10,
            type_effectiveness=1.0,
            defender_hp_remaining=20,
            message="Charmander scored a critical hit!",
            is_critical=True,
        )
        turn_opp = TurnResult(
            turn_number=1,
            actions=(opp_record,),
            battle_state=BattleState.IN_PROGRESS,
        )
        battle._history.append(turn_opp)

        # Must NOT attribute opponent's critical hit to player's Pokemon
        self.assertIsNone(battle.get_latest_player_combat_milestone())

        # Simulate turn 2 with player-caused critical hit
        player_record = BattleActionRecord(
            attacker=pika,
            defender=charm,
            attack=THUNDER_SHOCK,
            hit=True,
            damage=15,
            type_effectiveness=1.0,
            defender_hp_remaining=10,
            message="Pikachu scored a critical hit!",
            is_critical=True,
        )
        turn_player = TurnResult(
            turn_number=2,
            actions=(player_record,),
            battle_state=BattleState.IN_PROGRESS,
        )
        battle._history.append(turn_player)

        # Must detect player's critical hit
        self.assertEqual(battle.get_latest_player_combat_milestone(), "critical_hit")

    def test_14_stale_event_and_deduplication_prevention(self) -> None:
        """A combat milestone is consumed once and not replayed across subsequent TALK calls."""
        pika = Pokemon(species=PIKACHU, personality=self.default_personality, level=5, attacks=[THUNDER_SHOCK])
        charm = Pokemon(species=CHARMANDER, personality=self.default_personality, level=5, attacks=[EMBER])
        battle = Battle(pokemon1=pika, pokemon2=charm, seed=42)
        battle.start()

        # Turn 1: Player lands super-effective attack
        record = BattleActionRecord(
            attacker=pika,
            defender=charm,
            attack=THUNDER_SHOCK,
            hit=True,
            damage=15,
            type_effectiveness=2.0,
            defender_hp_remaining=10,
            message="Super effective!",
            is_critical=False,
        )
        turn1 = TurnResult(turn_number=1, actions=(record,), battle_state=BattleState.IN_PROGRESS)
        battle._history.append(turn1)

        # First consumption
        milestone1 = battle.get_latest_player_combat_milestone(mark_consumed=True)
        self.assertEqual(milestone1, "super_effective")

        # Second query in the same turn without new combat actions
        milestone2 = battle.get_latest_player_combat_milestone(mark_consumed=True)
        self.assertIsNone(milestone2)

        # Turn 2: Non-combat turn (no player attack records) -> milestone is stale
        turn2 = TurnResult(turn_number=2, actions=(), battle_state=BattleState.IN_PROGRESS)
        battle._history.append(turn2)
        self.assertIsNone(battle.get_latest_player_combat_milestone())

        # Turn 3: New fresh critical hit
        record3 = BattleActionRecord(
            attacker=pika,
            defender=charm,
            attack=THUNDER_SHOCK,
            hit=True,
            damage=20,
            type_effectiveness=1.0,
            defender_hp_remaining=0,
            message="Critical and KO!",
            is_critical=True,
        )
        turn3 = TurnResult(turn_number=3, actions=(record3,), battle_state=BattleState.IN_PROGRESS)
        battle._history.append(turn3)

        # Fresh knockout recognized!
        self.assertEqual(battle.get_latest_player_combat_milestone(mark_consumed=True), "opponent_knockout")

    def test_15_battle_reset_isolation(self) -> None:
        """Milestone consumption state does not leak between separate battle instances."""
        pika = Pokemon(species=PIKACHU, personality=self.default_personality, level=5)
        charm = Pokemon(species=CHARMANDER, personality=self.default_personality, level=5)

        battle1 = Battle(pokemon1=pika, pokemon2=charm, seed=10)
        battle2 = Battle(pokemon1=pika, pokemon2=charm, seed=20)

        # Battle 1 consumes milestone
        record = BattleActionRecord(
            attacker=pika, defender=charm, attack=THUNDER_SHOCK, hit=True,
            damage=10, type_effectiveness=2.0, defender_hp_remaining=10, message="hit",
        )
        battle1._history.append(TurnResult(turn_number=1, actions=(record,), battle_state=BattleState.IN_PROGRESS))
        battle1.get_latest_player_combat_milestone(mark_consumed=True)
        self.assertEqual(battle1._consumed_milestone_turn, 1)

        # Battle 2 remains unaffected
        self.assertIsNone(battle2._consumed_milestone_turn)
        self.assertIsNone(battle2.get_latest_player_combat_milestone())

    def test_16_one_talk_per_turn_preserved_with_milestones(self) -> None:
        """One talk action per turn limit strictly applies even when combat milestones exist."""
        pika = Pokemon(species=PIKACHU, personality=self.default_personality, level=5)
        charm = Pokemon(species=CHARMANDER, personality=self.default_personality, level=5)
        battle = Battle(pokemon1=pika, pokemon2=charm, seed=42)
        battle.start()

        # Turn 1: Player lands super-effective attack
        record = BattleActionRecord(
            attacker=pika, defender=charm, attack=THUNDER_SHOCK, hit=True,
            damage=10, type_effectiveness=2.0, defender_hp_remaining=10, message="hit",
        )
        battle._history.append(TurnResult(turn_number=1, actions=(record,), battle_state=BattleState.IN_PROGRESS))
        battle._current_turn = 2

        # First talk in Turn 2 succeeds and consumes milestone
        res1 = battle.talk("Awesome attack!")
        self.assertTrue(res1.accepted)
        self.assertIn("satisfaction", res1.talk_dialogue.lower())

        # Second talk in the same turn is rejected
        res2 = battle.talk("Keep it up!")
        self.assertFalse(res2.accepted)
        self.assertEqual(res2.error_type, "TALK_LIMIT_REACHED")

    def test_17_direct_attack_knockout_triggers_knockout_milestone(self) -> None:
        """A player attack reducing defender_hp_remaining to 0 directly triggers opponent_knockout."""
        pika = Pokemon(species=PIKACHU, personality=self.default_personality, level=5)
        charm = Pokemon(species=CHARMANDER, personality=self.default_personality, level=5)
        battle = Battle(pokemon1=pika, pokemon2=charm, seed=42)
        battle.start()

        # Turn 1: Player lands attack reducing Charmander to 0 HP
        charm.take_damage(charm.max_hp)
        self.assertTrue(charm.is_fainted)
        record = BattleActionRecord(
            attacker=pika,
            defender=charm,
            attack=THUNDER_SHOCK,
            hit=True,
            damage=30,
            type_effectiveness=1.0,
            defender_hp_remaining=0,
            message="Charmander fainted!",
            is_critical=False,
        )
        battle._history.append(TurnResult(turn_number=1, actions=(record,), battle_state=BattleState.VICTORY))

        milestone = battle.get_latest_player_combat_milestone()
        self.assertEqual(milestone, "opponent_knockout")

    def test_18_status_knockout_with_positive_attack_hp_does_not_trigger_knockout(self) -> None:
        """An attack leaving defender with positive HP does not trigger knockout even if defender faints later from status."""
        pika = Pokemon(species=PIKACHU, personality=self.default_personality, level=5)
        charm = Pokemon(species=CHARMANDER, personality=self.default_personality, level=5)
        battle = Battle(pokemon1=pika, pokemon2=charm, seed=42)
        battle.start()

        # Attack hit and left Charmander with 5 HP
        record = BattleActionRecord(
            attacker=pika,
            defender=charm,
            attack=THUNDER_SHOCK,
            hit=True,
            damage=10,
            type_effectiveness=1.0,
            defender_hp_remaining=5,
            message="Pikachu used Thunder Shock!",
            is_critical=False,
        )
        # End of turn status damage subsequently faints Charmander
        charm.take_damage(charm.max_hp)
        self.assertTrue(charm.is_fainted)
        self.assertTrue(battle.pokemon2.is_fainted)

        battle._history.append(TurnResult(turn_number=1, actions=(record,), battle_state=BattleState.VICTORY))

        # Because defender_hp_remaining was > 0, direct knockout is NOT attributed
        milestone = battle.get_latest_player_combat_milestone()
        self.assertIsNone(milestone)

        # Even if that non-lethal attack was critical, it triggers critical_hit, NOT knockout
        record_crit = BattleActionRecord(
            attacker=pika,
            defender=charm,
            attack=THUNDER_SHOCK,
            hit=True,
            damage=15,
            type_effectiveness=1.0,
            defender_hp_remaining=4,
            message="Critical hit!",
            is_critical=True,
        )
        battle._history[-1] = TurnResult(turn_number=1, actions=(record_crit,), battle_state=BattleState.VICTORY)
        self.assertEqual(battle.get_latest_player_combat_milestone(), "critical_hit")

    def test_19_genuine_knockout_takes_priority_over_crit_and_super_effective(self) -> None:
        """A direct lethal attack that is both critical and super-effective prioritizes knockout."""
        pika = Pokemon(species=PIKACHU, personality=self.default_personality, level=5)
        charm = Pokemon(species=CHARMANDER, personality=self.default_personality, level=5)
        battle = Battle(pokemon1=pika, pokemon2=charm, seed=42)
        battle.start()

        record = BattleActionRecord(
            attacker=pika,
            defender=charm,
            attack=THUNDER_SHOCK,
            hit=True,
            damage=45,
            type_effectiveness=2.0,
            defender_hp_remaining=0,
            message="Critical hit and super effective knockout!",
            is_critical=True,
        )
        battle._history.append(TurnResult(turn_number=1, actions=(record,), battle_state=BattleState.VICTORY))

        self.assertEqual(battle.get_latest_player_combat_milestone(), "opponent_knockout")

    def test_20_existing_crit_and_super_effective_reactions_remain_unchanged(self) -> None:
        """Non-lethal critical, super-effective, and combined reactions evaluate accurately."""
        pika = Pokemon(species=PIKACHU, personality=self.default_personality, level=5)
        charm = Pokemon(species=CHARMANDER, personality=self.default_personality, level=5)
        battle = Battle(pokemon1=pika, pokemon2=charm, seed=42)
        battle.start()

        # Crit only
        r_crit = BattleActionRecord(
            attacker=pika, defender=charm, attack=THUNDER_SHOCK, hit=True,
            damage=10, type_effectiveness=1.0, defender_hp_remaining=15, message="crit", is_critical=True
        )
        battle._history.append(TurnResult(turn_number=1, actions=(r_crit,), battle_state=BattleState.IN_PROGRESS))
        self.assertEqual(battle.get_latest_player_combat_milestone(), "critical_hit")

        # Super effective only
        r_super = BattleActionRecord(
            attacker=pika, defender=charm, attack=THUNDER_SHOCK, hit=True,
            damage=10, type_effectiveness=2.0, defender_hp_remaining=15, message="super", is_critical=False
        )
        battle._history[-1] = TurnResult(turn_number=1, actions=(r_super,), battle_state=BattleState.IN_PROGRESS)
        self.assertEqual(battle.get_latest_player_combat_milestone(), "super_effective")

        # Crit + Super effective
        r_both = BattleActionRecord(
            attacker=pika, defender=charm, attack=THUNDER_SHOCK, hit=True,
            damage=20, type_effectiveness=2.0, defender_hp_remaining=10, message="both", is_critical=True
        )
        battle._history[-1] = TurnResult(turn_number=1, actions=(r_both,), battle_state=BattleState.IN_PROGRESS)
        self.assertEqual(battle.get_latest_player_combat_milestone(), "critical_and_super_effective")

    def test_21_opponent_caused_events_strictly_excluded(self) -> None:
        """Opponent knockout or critical strikes are never attributed to the player."""
        pika = Pokemon(species=PIKACHU, personality=self.default_personality, level=5)
        charm = Pokemon(species=CHARMANDER, personality=self.default_personality, level=5)
        battle = Battle(pokemon1=pika, pokemon2=charm, seed=42)
        battle.start()

        # Opponent knocks out player
        pika.take_damage(pika.max_hp)
        r_opp_ko = BattleActionRecord(
            attacker=charm, defender=pika, attack=EMBER, hit=True,
            damage=30, type_effectiveness=1.0, defender_hp_remaining=0, message="Charmander KO'd Pikachu!", is_critical=True
        )
        battle._history.append(TurnResult(turn_number=1, actions=(r_opp_ko,), battle_state=BattleState.DEFEAT))
        self.assertIsNone(battle.get_latest_player_combat_milestone())


if __name__ == "__main__":
    unittest.main()
