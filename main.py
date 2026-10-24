"""
Demonstration script for Pokémon data foundation and Player collection/team system.

Demonstrates:
- Creating individual Pokémon instances with clean 5-digit unique IDs.
- Creating a Player named 'Trainer'.
- Managing the complete Pokémon Collection vs. Active Team.
- Selecting an Active Pokémon.
- Showing that Collection and Team are separate concepts.
"""
import random
from src.models.personality import Personality
from src.models.pokemon import Pokemon
from src.models.player import Player
from src.models.behavior_context import BehaviorContext
from src.models.pokemon_behavior import PokemonBehavior
from src.models.spawn_area import SpawnArea
from src.models.spawn_manager import SpawnManager
from src.models.encounter_manager import EncounterManager
from src.models.battle import (
    Battle,
    BattleAction,
    BattleActionType,
    BattleActionResult,
)
from src.models.battle_manager import BattleManager
from src.models.battle_state import BattleState
from src.models.experience_manager import ExperienceManager
from src.models.progression import get_xp_for_next_level, apply_experience
from src.models.capture_manager import CaptureManager, calculate_capture_probability
from src.models.damage_calculator import calculate_damage
from src.models.bond_manager import BondManager, DEFAULT_BOND_BATTLE_VICTORY
from src.models.obedience_manager import (
    ObedienceManager,
    CommandContext,
    calculate_obedience_probability,
)
from src.models.training_manager import TrainingManager, TrainingConfig
from src.models.move_manager import MoveManager
from src.models.status_effect import StatusEffectType, AttackEffect
from src.models.status_effect_manager import StatusEffectManager
from src.data.species import PIKACHU, CHARMANDER, SQUIRTLE
from src.data.attacks import (
    THUNDER_SHOCK,
    QUICK_ATTACK,
    EMBER,
    SCRATCH,
    WATER_GUN,
    HYDRO_PUMP,
    TACKLE,
    THUNDERBOLT,
    FLAMETHROWER,
    WILL_O_WISP,
    THUNDER_WAVE,
    GROWL,
    TAIL_WHIP,
)
from src.data.spawn_config import create_sample_spawn_areas
from src.models.inventory import Inventory
from src.models.item_manager import ItemManager
from src.data.items import POTION, SUPER_POTION, FULL_RESTORE, ANTIDOTE, BURN_HEAL, POKE_BALL
import tempfile
from pathlib import Path
from src.models.save_manager import save_game, load_game, SaveDataError
from src.models.quest import QuestStatus, ObjectiveType, QuestEventType
from src.models.quest_manager import QuestManager
from src.data.quests import QUEST_CATALOG, list_catalog_quests
from src.models.world_interaction import InteractableType, Interactable
from src.models.world_interaction_manager import WorldInteractionManager
from src.data.world_objects import WORLD_OBJECT_CATALOG, create_default_world_objects
from src.models.world_exploration import WorldRegion, ExplorationResult
from src.models.world_exploration_manager import WorldExplorationManager
from src.data.world_regions import WORLD_REGION_CATALOG, create_default_world_regions
from src.models.habitat import (
    TimeOfDay,
    Rarity,
    SpawnCandidate,
    Habitat,
    SpawnSelectionResult,
    HabitatEncounterResult,
    get_time_of_day,
)
from src.models.habitat_manager import HabitatManager
from src.data.habitats import (
    HABITAT_CATALOG,
    MEADOW_HABITAT,
    FOREST_HABITAT,
    SHRINE_GROUNDS_HABITAT,
    get_habitat,
    get_habitat_for_region,
    list_habitats,
)


def print_pokemon_card(mon: Pokemon) -> None:
    """Prints a formatted summary card for a Pokemon instance."""
    print("=" * 60)
    print(f" {mon.display_name.upper()} (Species: {mon.species.name})")
    print(f" ID: {mon.unique_id}")
    print("=" * 60)
    print(f" Type(s)        : {', '.join(t.value for t in mon.species.types)}")
    print(f" Level          : {mon.level}")
    print(f" Experience     : {mon.experience} XP")
    print(f" HP             : {mon.current_hp} / {mon.max_hp} (Base HP: {mon.species.base_hp})")
    print(f" Base Stats     : ATK: {mon.species.base_attack} | DEF: {mon.species.base_defense} | SPD: {mon.species.base_speed}")
    print(f" Bond           : {mon.bond} / 100")
    print(f" Obedience      : {mon.obedience} / 100")
    
    print("\n [Personality Profile (0 - 100)]")
    traits = mon.personality.to_dict()
    for trait_name, trait_val in traits.items():
        filled = trait_val // 10
        bar = "#" * filled + "-" * (10 - filled)
        print(f"   {trait_name.capitalize():<12}: [{bar}] {trait_val:>3}")

    print("\n [Known Attacks]")
    if mon.attacks:
        for attack in mon.attacks:
            print(f"   - {attack.name} ({attack.type.value} | Power: {attack.power} | Acc: {attack.accuracy}%)")
    else:
        print("   (No attacks assigned)")

    print("\n [Species Abilities]")
    for ab in mon.species.abilities:
        print(f"   - {ab.name}: {ab.description}")
    print("=" * 60 + "\n")


def print_player_overview(player: Player) -> None:
    """Prints the required clean summary of player, collection, team, and active Pokemon."""
    print(f"Player: {player.name}\n")

    print("Collection:")
    if player.collection:
        for mon in player.collection:
            print(f"* {mon.display_name} (ID: {mon.unique_id}, Lv.{mon.level})")
    else:
        print("  (Empty)")

    print("\nTeam:")
    if player.team:
        for mon in player.team:
            print(f"* {mon.display_name} (ID: {mon.unique_id}, Lv.{mon.level})")
    else:
        print("  (Empty)")

    print("\nActive Pokemon:")
    if player.active_pokemon:
        active = player.active_pokemon
        print(f"* {active.display_name} (ID: {active.unique_id}, Lv.{active.level})")
    else:
        print("  (None)")


def main() -> None:
    print("\n" + "#" * 60)
    print("      PLAYER + POKEMON COLLECTION & TEAM SYSTEM")
    print("#" * 60 + "\n")

    # 1. Create a Player
    player = Player(name="Trainer")

    # 2. Create distinct Pokemon with unique 5-digit IDs
    pikachu_personality = Personality(
        aggression=20,
        curiosity=90,
        fear=15,
        sociability=85,
        loyalty=95,
        confidence=75,
    )
    pikachu = Pokemon(
        species=PIKACHU,
        personality=pikachu_personality,
        level=5,
        bond=80,
        obedience=100,
        nickname="Sparky",
    )
    pikachu.assign_attack(THUNDER_SHOCK)
    pikachu.assign_attack(QUICK_ATTACK)

    charmander_personality = Personality(
        aggression=40,
        curiosity=75,
        fear=25,
        sociability=70,
        loyalty=90,
        confidence=65,
    )
    charmander = Pokemon(
        species=CHARMANDER,
        personality=charmander_personality,
        level=5,
        bond=70,
        obedience=95,
        nickname="Blaze",
    )
    charmander.assign_attack(SCRATCH)
    charmander.assign_attack(EMBER)

    squirtle_personality = Personality(
        aggression=15,
        curiosity=80,
        fear=10,
        sociability=85,
        loyalty=90,
        confidence=80,
    )
    squirtle = Pokemon(
        species=SQUIRTLE,
        personality=squirtle_personality,
        level=5,
        bond=60,
        obedience=90,
        nickname="Bubbles",
    )
    squirtle.assign_attack(WATER_GUN)
    squirtle.assign_attack(HYDRO_PUMP)

    # 3. Add all three Pokemon to the player's collection
    player.add_pokemon(pikachu)
    player.add_pokemon(charmander)
    player.add_pokemon(squirtle)

    # 4. Add Pikachu and Charmander to the active team (Squirtle remains in collection only)
    player.add_to_team(pikachu)
    player.add_to_team(charmander)

    # 5. Set Pikachu as the active Pokemon
    player.set_active_pokemon(pikachu)

    # 6. Display Player Overview
    print_player_overview(player)

    # 7. Demonstrate that Collection and Team are separate concepts
    print("\n" + "-" * 60)
    print("Demonstration: Collection vs Team Independence")
    print("-" * 60)
    print(f"Total owned in Collection : {len(player.collection)} (Pikachu, Charmander, Squirtle)")
    print(f"Currently on Team         : {len(player.team)} (Pikachu, Charmander)")
    print(f"Squirtle is owned?        : {player.is_pokemon_owned(squirtle)} (Stored in collection)")
    print(f"Squirtle is on team?      : {player.is_on_team(squirtle)} (Not selected for team)")
    print(f"Active Pokemon            : {player.active_pokemon.display_name}")

    print("\n" + "=" * 60)
    print(" Active Pokemon Details:")
    print_pokemon_card(player.active_pokemon)

    # 8. Pokemon Behaviour Demonstration
    print("=" * 60)
    print(" POKEMON BEHAVIOUR SYSTEM DEMONSTRATION")
    print("=" * 60)
    print("Scenario: Player detected nearby (distance: 4.0m, threat_level: 50.0)\n")

    test_context = BehaviorContext(
        player_visible=True,
        player_nearby=True,
        distance_to_player=4.0,
        threat_level=50.0,
    )

    aggro_mon = Pokemon(
        species=CHARMANDER,
        personality=Personality(aggression=85, curiosity=20, fear=10, sociability=10, loyalty=40, confidence=75),
        nickname="Aggro-Mander",
    )
    aggro_behavior = PokemonBehavior(aggro_mon)

    fear_mon = Pokemon(
        species=PIKACHU,
        personality=Personality(aggression=10, curiosity=25, fear=85, sociability=15, loyalty=30, confidence=20),
        nickname="Shy-Chu",
    )
    fear_behavior = PokemonBehavior(fear_mon)

    curious_mon = Pokemon(
        species=SQUIRTLE,
        personality=Personality(aggression=20, curiosity=90, fear=15, sociability=75, loyalty=70, confidence=70),
        nickname="Curious-Turtle",
    )
    curious_behavior = PokemonBehavior(curious_mon)

    for b in [aggro_behavior, fear_behavior, curious_behavior]:
        p = b.pokemon
        prev_state = b.get_state()
        new_state = b.update(test_context)
        print(f"Pokemon      : {p.display_name} ({p.species.name})")
        print(f"Key Traits   : Aggression: {p.personality.aggression} | Fear: {p.personality.fear} | Curiosity: {p.personality.curiosity} | Confidence: {p.personality.confidence}")
        print(f"Transition   : {prev_state.value} -> {new_state.value}")
        print("-" * 60)

    # 9. Wild Pokemon Spawning & Encounter System Demonstration
    print("\n" + "=" * 60)
    print(" WILD POKEMON SPAWN & ENCOUNTER SYSTEM DEMONSTRATION")
    print("=" * 60)

    # Step 1 & 2: Register areas and configure species
    spawn_mgr = SpawnManager(seed=101)
    sample_areas = create_sample_spawn_areas()
    for area in sample_areas.values():
        spawn_mgr.register_area(area)

    print("Registered Spawn Areas:")
    for area in spawn_mgr.get_all_areas():
        allowed = ", ".join(sp.name for sp in area.allowed_species)
        print(f" - {area.name} (ID: '{area.area_id}') | Allowed: [{allowed}] | Max: {area.max_active_pokemon} | Radius: {area.encounter_radius}m")

    # Step 3 & 4: Spawn wild Pokemon and print details
    print("\nSpawning Wild Pokemon across areas:")
    spawned_forest = spawn_mgr.attempt_spawn("forest", ignore_probability=True, position=(12.0, 15.0))
    spawned_grassland = spawn_mgr.attempt_spawn("grassland", ignore_probability=True, position=(5.0, 5.0))
    spawned_lakeside = spawn_mgr.attempt_spawn("lakeside", ignore_probability=True, position=(50.0, 60.0))

    spawned_list = [
        ("forest", spawned_forest),
        ("grassland", spawned_grassland),
        ("lakeside", spawned_lakeside),
    ]

    for area_id, mon in spawned_list:
        if mon:
            p = mon.personality
            pos = spawn_mgr.get_pokemon_position(mon)
            print(f" * Area: {area_id:<9} | {mon.species.name} (ID: {mon.unique_id}, Lv.{mon.level}) at Pos {pos}")
            print(f"   Personality -> Agg: {p.aggression}, Cur: {p.curiosity}, Fear: {p.fear}, Soc: {p.sociability}, Loy: {p.loyalty}, Conf: {p.confidence}")

    # Step 5: Demonstrate encounter checks with two player positions
    print("\nEncounter Checks for Grassland Pokemon at (5.0, 5.0):")
    encounter_mgr = EncounterManager()

    # Case A: Player close (inside radius 10m)
    player_close_pos = (8.0, 5.0)  # distance = 3.0m
    result_close = encounter_mgr.check_encounter_with_manager(
        spawn_manager=spawn_mgr,
        area_id="grassland",
        player_position=player_close_pos,
        pokemon=spawned_grassland,
    )
    print(f" - Player at {player_close_pos}: Can Encounter? {result_close.can_encounter} (Distance: {result_close.distance:.2f}m) -> {result_close.reason}")

    # Case B: Player far (outside radius 10m)
    player_far_pos = (25.0, 5.0)  # distance = 20.0m
    result_far = encounter_mgr.check_encounter_with_manager(
        spawn_manager=spawn_mgr,
        area_id="grassland",
        player_position=player_far_pos,
        pokemon=spawned_grassland,
    )
    print(f" - Player at {player_far_pos}: Can Encounter? {result_far.can_encounter} (Distance: {result_far.distance:.2f}m) -> {result_far.reason}")

    # Step 6: Demonstrate despawning and replacement
    print("\nDespawn and Replacement in Forest:")
    print(f" - Active count before despawn: {spawn_mgr.get_active_count('forest')}")
    despawned = spawn_mgr.despawn_pokemon("forest", spawned_forest)
    print(f" - Despawned: {despawned.species.name} (ID: {despawned.unique_id})")
    print(f" - Active count after despawn: {spawn_mgr.get_active_count('forest')}")

    replacement = spawn_mgr.attempt_spawn("forest", ignore_probability=True, position=(14.0, 16.0))
    print(f" - Spawned replacement: {replacement.species.name} (ID: {replacement.unique_id}, Lv.{replacement.level})")
    print(f" - Active count after replacement: {spawn_mgr.get_active_count('forest')}")

    # Step 7: Show spawned Pokemon passed to PokemonBehavior
    print("\nSpawned Pokemon Behavior Evaluation:")
    wild_behavior = PokemonBehavior(spawned_grassland)
    print(f" - Initial state of wild {spawned_grassland.species.name}: {wild_behavior.get_state().value}")
    threat_ctx = BehaviorContext(player_visible=True, player_nearby=True, distance_to_player=2.0)
    next_state = wild_behavior.update(threat_ctx)
    print(f" - Context: Player close (distance: 2.0m) -> State: {next_state.value}")
    print("-" * 60)

    # 10. Turn-based Battle Engine Demonstration
    print("\n" + "=" * 60)
    print(" TURN-BASED BATTLE ENGINE DEMONSTRATION")
    print("=" * 60)

    # Combatants
    pika_pers = Personality(aggression=70, curiosity=50, fear=20, sociability=60, loyalty=90, confidence=80)
    squirtle_pers = Personality(aggression=40, curiosity=60, fear=30, sociability=70, loyalty=80, confidence=75)

    battle_pika = Pokemon(
        species=PIKACHU,
        personality=pika_pers,
        level=5,
        experience=300,
        nickname="Sparky",
        attacks=[THUNDER_SHOCK, QUICK_ATTACK],
    )
    battle_squirtle = Pokemon(
        species=SQUIRTLE,
        personality=squirtle_pers,
        level=5,
        nickname="Bubbles",
        attacks=[WATER_GUN, TACKLE],
    )

    print("Participants:")
    print(f" - {battle_pika.display_name} ({battle_pika.species.name}) | Lv.{battle_pika.level} | HP: {battle_pika.current_hp}/{battle_pika.max_hp} | SPD: {battle_pika.species.base_speed}")
    print(f" - {battle_squirtle.display_name} ({battle_squirtle.species.name}) | Lv.{battle_squirtle.level} | HP: {battle_squirtle.current_hp}/{battle_squirtle.max_hp} | SPD: {battle_squirtle.species.base_speed}\n")

    battle = Battle(battle_pika, battle_squirtle, seed=42)
    battle.start()
    print(f"Battle State: {battle.state.value}\n")

    max_turns = 10
    turn_count = 1
    while not battle.state.is_terminal() and turn_count <= max_turns:
        print(f"--- Turn {battle.current_turn} ---")
        turn_res = battle.resolve_turn(attack1=THUNDER_SHOCK, attack2=WATER_GUN)

        for action in turn_res.actions:
            hit_str = "HIT" if action.hit else "MISSED"
            eff_str = f" (x{action.type_effectiveness})" if action.hit else ""
            print(f" * {action.attacker.display_name} used {action.attack.name} -> {hit_str}{eff_str} | Damage: {action.damage} | {action.defender.display_name} HP: {action.defender_hp_remaining}/{action.defender.max_hp}")

        print(f" Turn Outcome: State={turn_res.battle_state.value}\n")
        turn_count += 1

    print(f"Final Battle Result: {battle.state.value}")
    if battle.winner:
        print(f"Winner: {battle.winner.display_name} ({battle.winner.species.name})")
    if battle.loser:
        print(f"Defeated: {battle.loser.display_name} ({battle.loser.species.name})")
    print("=" * 60)

    # 11. Battle Rewards & Pokemon Progression Demonstration
    print("\n" + "=" * 60)
    print(" BATTLE REWARDS & POKEMON PROGRESSION DEMONSTRATION")
    print("=" * 60)

    exp_mgr = ExperienceManager()

    # Pre-reward snapshot
    pika_pre_lvl = battle_pika.level
    pika_pre_xp = battle_pika.experience
    pika_pre_max_hp = battle_pika.max_hp
    pika_pre_hp = battle_pika.current_hp
    xp_needed_pre = get_xp_for_next_level(pika_pre_lvl)

    print(f"Pre-Reward State for Winner '{battle_pika.display_name}':")
    print(f" - Level          : {pika_pre_lvl}")
    print(f" - Experience     : {pika_pre_xp} / {xp_needed_pre} XP")
    print(f" - HP Status      : {pika_pre_hp} / {pika_pre_max_hp}\n")

    expected_xp = exp_mgr.calculate_reward_xp(battle)
    print(f"Calculated Victory Reward: {expected_xp} XP (Defeated Lv.{battle_squirtle.level} x 50)")

    # Award the battle reward
    reward_result = exp_mgr.award_battle_rewards(battle)
    print(f"Award Status: {reward_result.reason}")
    print(f" - XP Awarded     : +{reward_result.xp_awarded} XP")
    print(f" - Levels Gained  : +{reward_result.levels_gained} level(s)")

    pika_post_lvl = battle_pika.level
    pika_post_xp = battle_pika.experience
    pika_post_max_hp = battle_pika.max_hp
    pika_post_hp = battle_pika.current_hp
    xp_needed_post = get_xp_for_next_level(pika_post_lvl)

    print(f"\nPost-Reward State for Winner '{battle_pika.display_name}':")
    print(f" - Level          : {pika_pre_lvl} -> {pika_post_lvl} (Level Up!)")
    print(f" - Experience     : {pika_post_xp} / {xp_needed_post} XP (Carried forward)")
    print(f" - Maximum HP     : {pika_pre_max_hp} -> {pika_post_max_hp} (+{reward_result.hp_gained} max HP)")
    print(f" - Current HP     : {pika_pre_hp} -> {pika_post_hp} (Gained HP benefit)")

    # Demonstrate prevention of duplicate claims
    print("\nAttempting Duplicate Reward Claim:")
    dup_result = exp_mgr.award_battle_rewards(battle)
    print(f" - Can Award Again? {exp_mgr.can_award_rewards(battle)}")
    print(f" - Claim Result    : {dup_result.reason}")
    print(f" - XP Awarded      : {dup_result.xp_awarded} XP (Safe no-op)")
    print(f" - Sparky Level    : Lv.{battle_pika.level} (Unchanged)")
    print("=" * 60)

    # 12. Wild Pokemon Capture & Collection Demonstration
    print("\n" + "=" * 60)
    print(" WILD POKEMON CAPTURE & COLLECTION DEMONSTRATION")
    print("=" * 60)

    # Spawn wild target in Grassland
    wild_target = spawn_mgr.attempt_spawn("grassland", ignore_probability=True, position=(6.0, 6.0))
    print(f"Spawned Wild Target  : {wild_target.display_name} ({wild_target.species.name}, Lv.{wild_target.level})")
    print(f"Target Unique ID     : {wild_target.unique_id}")
    print(f"Wild Target HP       : {wild_target.current_hp} / {wild_target.max_hp}")
    print(f"Grassland Population : {spawn_mgr.get_active_count('grassland')} active Pokemon")

    # Step 1: Detect encounter and start encounter session
    encounter_check = encounter_mgr.check_encounter_with_manager(
        spawn_manager=spawn_mgr,
        area_id="grassland",
        player_position=(7.0, 6.0),
        pokemon=wild_target,
    )
    print(f"\nInitiating Wild Encounter (Player at (7.0, 6.0), Distance: {encounter_check.distance:.2f}m)...")
    wild_encounter = encounter_check.start_encounter(player)
    print(f" - Encounter Session : Active={wild_encounter.is_active}, Resolved={wild_encounter.is_resolved}")
    print(f" - Encounter ID      : {wild_encounter.encounter_id}")

    # Pre-capture inventory inspection
    print(f"\nPlayer State Before Capture Attempt:")
    print(f" - Collection Count  : {len(player.collection)} Pokemon")
    print(f" - Team Count        : {len(player.team)} Pokemon")
    print(f" - Is Target Owned?  : {player.is_pokemon_owned(wild_target)}")

    # Step 2: Weaken target to show probability scaling
    full_hp_prob = calculate_capture_probability(wild_target)
    damage_taken = int(wild_target.max_hp * 0.70)
    wild_target.take_damage(damage_taken)
    weakened_prob = calculate_capture_probability(wild_target)

    print(f"\nWeakening Wild Target (Combat Simulation):")
    print(f" - Inflicted Damage  : -{damage_taken} HP")
    print(f" - Remaining HP      : {wild_target.current_hp} / {wild_target.max_hp}")
    print(f" - Full HP Chance    : {full_hp_prob:.1%}")
    print(f" - Weakened Chance   : {weakened_prob:.1%} (Catch probability scaled up!)")

    # Step 3: Attempt deterministic capture
    capture_mgr = CaptureManager(seed=1)
    capture_res = capture_mgr.attempt_capture(
        player=player,
        wild_pokemon=wild_target,
        encounter=wild_encounter,
        spawn_manager=spawn_mgr,
        area_id="grassland",
    )

    print(f"\nCapture Attempt Execution:")
    print(f" - Accepted          : {capture_res.accepted}")
    print(f" - Probability Roll  : {capture_res.roll:.4f} <= {capture_res.capture_probability:.4f}")
    print(f" - Success           : {capture_res.success}")
    print(f" - Result Message    : {capture_res.message}")
    print(f" - Added to Coll.    : {capture_res.added_to_collection}")

    # Step 4: Verify post-capture state
    print(f"\nPlayer State After Capture:")
    print(f" - Collection Count  : {len(player.collection)} (Incremented: {len(player.collection) - 1} -> {len(player.collection)})")
    print(f" - Team Count        : {len(player.team)} (Unchanged; team slots preserved)")
    print(f" - Is Target Owned?  : {player.is_pokemon_owned(wild_target)} (Successfully stored in player collection)")
    print(f" - Encounter Active  : {wild_encounter.is_active} (Resolved Reason: '{wild_encounter.resolution_reason}')")
    print(f" - Grassland Active  : {spawn_mgr.get_active_count('grassland')} (Target despawned from wild area)")

    # Step 5: Duplicate catch and resolved encounter rejection
    print("\nAttempting Re-Capture on Owned Pokemon / Resolved Encounter:")
    dup_capture = capture_mgr.attempt_capture(
        player=player,
        wild_pokemon=wild_target,
        encounter=wild_encounter,
    )
    print(f" - Accepted          : {dup_capture.accepted}")
    print(f" - Message           : {dup_capture.message}")
    print("=" * 60)

    # 13. Bonding & Obedience System Demonstration
    print("\n" + "=" * 60)
    print(" POKEMON BONDING & OBEDIENCE SYSTEM DEMONSTRATION")
    print("=" * 60)

    bond_mgr = BondManager()

    # Part 1: Bond gain after battle victory
    print(f"Pre-Bond State for Winner '{battle_pika.display_name}':")
    print(f" - Current Bond      : {battle_pika.bond} / 100")
    print(f" - Current Obedience : {battle_pika.obedience} / 100")

    bond_victory_res = bond_mgr.award_battle_victory_bond(battle)
    print(f"\nAwarding Battle Victory Bond Reward:")
    print(f" - Status            : Success={bond_victory_res.success}")
    print(f" - Bond Change       : +{bond_victory_res.change_amount} ({bond_victory_res.previous_bond} -> {bond_victory_res.new_bond})")
    print(f" - Was Clamped?      : {bond_victory_res.was_clamped}")
    print(f" - Details           : {bond_victory_res.reason}")

    # Part 2: Safe rejection of duplicate event reward
    print("\nAttempting Duplicate Battle Bond Reward:")
    dup_bond_res = bond_mgr.award_battle_victory_bond(battle)
    print(f" - Status            : Success={dup_bond_res.success} (Rejected)")
    print(f" - Delta Applied     : {dup_bond_res.change_amount}")
    print(f" - Current Bond      : {battle_pika.bond} / 100 (Unchanged)")
    print(f" - Rejection Reason  : {dup_bond_res.reason}")

    # Also show capture bond reward for the newly captured Pokemon
    print(f"\nAwarding Collection Joining Bond to '{wild_target.display_name}':")
    cap_bond_res = bond_mgr.award_capture_bond(wild_target)
    print(f" - Status            : Success={cap_bond_res.success}")
    print(f" - Bond Change       : +{cap_bond_res.change_amount} ({cap_bond_res.previous_bond} -> {cap_bond_res.new_bond})")
    print(f" - Reason            : {cap_bond_res.reason}")

    # Part 3: Obedience probability calculation
    print("\n" + "-" * 60)
    print("Obedience Probability Calculation:")
    print("-" * 60)
    pika_prob = calculate_obedience_probability(battle_pika)
    print(f"Target: '{battle_pika.display_name}'")
    print(f" - Obedience Stat    : {battle_pika.obedience} / 100 (Primary factor: +{(battle_pika.obedience / 100) * 0.25:.3f})")
    print(f" - Bond Stat         : {battle_pika.bond} / 100 (Secondary factor: +{(battle_pika.bond / 100) * 0.05:.3f})")
    print(f" - Base Probability  : 0.700")
    print(f" - Calculated Chance : {pika_prob:.1%}")

    # Contrast with a rebellious / untrained Pokemon
    rebel_mon = Pokemon(
        species=CHARMANDER,
        personality=Personality(90, 20, 10, 10, 10, 80),
        nickname="Stubborn-Char",
        bond=0,
        obedience=10,
    )
    rebel_prob = calculate_obedience_probability(rebel_mon)
    print(f"\nContrast: '{rebel_mon.display_name}' (Untrained / Low Obedience):")
    print(f" - Obedience Stat    : {rebel_mon.obedience} / 100")
    print(f" - Bond Stat         : {rebel_mon.bond} / 100")
    print(f" - Calculated Chance : {rebel_prob:.1%} (Significantly lower compliance rate)")

    # Part 4: Deterministic obedience evaluation using injected randomness
    print("\n" + "-" * 60)
    print("Deterministic Obedience Evaluation (Injected RNG):")
    print("-" * 60)

    # Evaluation on obedient Pokemon (seed=42 rolls ~0.6394 <= 0.9925 -> Obeyed)
    obedient_evaluator = ObedienceManager(seed=42)
    pika_eval = obedient_evaluator.evaluate_obedience(battle_pika, "Thunder Shock")
    print(f"Case A: Command '{pika_eval.command}' issued to {battle_pika.display_name}")
    print(f" - Roll Result       : {pika_eval.roll:.4f} <= {pika_eval.probability:.4f}")
    print(f" - Obeyed?           : {pika_eval.is_obeyed}")
    print(f" - Outcome           : {pika_eval.reason}")
    print(f" - State Preserved   : Bond={battle_pika.bond}, Obedience={battle_pika.obedience} (Unmutated)")

    # Evaluation on rebellious Pokemon (seed=0 rolls ~0.8444 > 0.7250 -> Ignored)
    rebel_evaluator = ObedienceManager(seed=0)
    rebel_eval = rebel_evaluator.evaluate_obedience(rebel_mon, "Ember")
    print(f"\nCase B: Command '{rebel_eval.command}' issued to {rebel_mon.display_name}")
    print(f" - Roll Result       : {rebel_eval.roll:.4f} <= {rebel_eval.probability:.4f}")
    print(f" - Obeyed?           : {rebel_eval.is_obeyed}")
    print(f" - Outcome           : {rebel_eval.reason}")
    print("=" * 60)

    # 14. Pokemon Training & Stat Growth Demonstration
    print("\n" + "=" * 60)
    print(" POKEMON TRAINING & STAT GROWTH DEMONSTRATION")
    print("=" * 60)

    train_mgr = TrainingManager()

    # Step 1: Two Pokemon of the same species with initially equivalent stats
    trainer_personality = Personality(50, 50, 50, 50, 50, 50)
    char_alpha = Pokemon(
        species=CHARMANDER,
        personality=trainer_personality,
        nickname="Char-Alpha",
    )
    char_beta = Pokemon(
        species=CHARMANDER,
        personality=trainer_personality,
        nickname="Char-Beta",
    )
    char_alpha.assign_attack(SCRATCH)
    char_beta.assign_attack(SCRATCH)

    print("Step 1: Two Pokemon of the same species (Charmander):")
    print(f" - {char_alpha.display_name} : Attack={char_alpha.attack}, Defense={char_alpha.defense}, Speed={char_alpha.speed}")
    print(f" - {char_beta.display_name}  : Attack={char_beta.attack}, Defense={char_beta.defense}, Speed={char_beta.speed}")
    print(f" - Species Baseline   : Attack={CHARMANDER.base_attack}, Defense={CHARMANDER.base_defense}, Speed={CHARMANDER.base_speed}")

    # Step 2: Train Attack on Char-Alpha only
    print("\nStep 2: Training Attack (+15) on Char-Alpha only:")
    train_atk_res = train_mgr.train_attack(char_alpha, amount=15)
    print(f" - Status             : Success={train_atk_res.success}")
    print(f" - Stat Trained       : {train_atk_res.stat_name.capitalize()}")
    print(f" - Value Progression  : {train_atk_res.previous_value} -> {train_atk_res.new_value} (+{train_atk_res.actual_change})")
    print(f" - Was Clamped?       : {train_atk_res.was_clamped}")
    print(f" - Outcome Details    : {train_atk_res.reason}")

    # Step 3: Verifying Char-Beta and species template remain unchanged
    print("\nStep 3: Verification of Instance Isolation & Template Immutability:")
    print(f" - Char-Alpha Attack  : {char_alpha.attack} (Trained: +{char_alpha.trained_attack})")
    print(f" - Char-Beta Attack   : {char_beta.attack} (Trained: +{char_beta.trained_attack} - Unaffected!)")
    print(f" - Species Base Attack: {CHARMANDER.base_attack} (Immutable blueprint preserved!)")

    # Step 4: Train Speed on Char-Alpha (+20) and Defense on Char-Beta (+15)
    print("\nStep 4: Training Additional Stats:")
    train_spd_res = train_mgr.train_speed(char_alpha, amount=20)
    print(f" - Char-Alpha Speed   : {train_spd_res.previous_value} -> {train_spd_res.new_value} (+{train_spd_res.actual_change})")
    train_def_res = train_mgr.train_defense(char_beta, amount=15)
    print(f" - Char-Beta Defense  : {train_def_res.previous_value} -> {train_def_res.new_value} (+{train_def_res.actual_change})")

    # Step 5: Showing how trained stats affect a subsequent battle
    print("\nStep 5: Subsequent Battle Demonstration (Trained vs Untrained):")
    print(f"Combatants: {char_alpha.display_name} (Spd: {char_alpha.speed}, Atk: {char_alpha.attack}) vs {char_beta.display_name} (Spd: {char_beta.speed}, Atk: {char_beta.attack})")

    # Turn order evaluation
    train_battle = Battle(pokemon1=char_alpha, pokemon2=char_beta, seed=42)
    turn_order = train_battle._determine_turn_order(SCRATCH, SCRATCH)
    first_mon = turn_order[0][0]
    print(f" - Turn Order Priority: {first_mon.display_name} strikes first (Speed: {first_mon.speed})!")

    # Damage comparison
    train_battle.start()
    turn_res = train_battle.execute_turn(SCRATCH, SCRATCH)
    action1 = turn_res.actions[0]
    action2 = turn_res.actions[1]
    print(f" - Action 1: {action1.attacker.display_name} (Atk: {action1.attacker.attack}) dealt {action1.damage} damage to {action1.defender.display_name}")
    print(f" - Action 2: {action2.attacker.display_name} (Atk: {action2.attacker.attack}) dealt {action2.damage} damage to {action2.defender.display_name}")
    print(f" - Combat Summary     : Trained stats directly amplified damage and secured speed priority!")
    print("=" * 60)

    # 15. Pokemon Move Learning & Move Management Demonstration
    print("\n" + "=" * 60)
    print(" POKEMON MOVE LEARNING & MOVE MANAGEMENT DEMONSTRATION")
    print("=" * 60)

    move_mgr = MoveManager()

    # Step 1: Learning a new attack
    move_pika = Pokemon(
        species=PIKACHU,
        personality=Personality(50, 50, 50, 50, 50, 50),
        level=1,
        nickname="Volt",
        attacks=[THUNDER_SHOCK],
    )
    print("Step 1: Initial Move Loadout for Volt (Pikachu, Lv.1):")
    print(f" - Known Moves       : {[atk.name for atk in move_pika.attacks]}")

    print("\nTeaching Volt 'Quick Attack':")
    learn_res = move_mgr.learn_attack(move_pika, QUICK_ATTACK)
    print(f" - Success            : {learn_res.success}")
    print(f" - Outcome            : {learn_res.reason}")
    print(f" - Updated Loadout    : {[atk.name for atk in move_pika.attacks]}")

    # Step 2: Duplicate learning attempt rejected
    print("\nStep 2: Attempting Duplicate Move Learning ('Quick Attack'):")
    dup_learn_res = move_mgr.learn_attack(move_pika, QUICK_ATTACK)
    print(f" - Success            : {dup_learn_res.success}")
    print(f" - Outcome            : {dup_learn_res.reason}")
    print(f" - Loadout Preserved  : {[atk.name for atk in move_pika.attacks]}")

    # Step 3: Pokemon reaching a move-learning level (Lv.1 -> Lv.6)
    print("\nStep 3: Level Progression and Auto-Learning (Lv.1 -> Lv.6):")
    lvl_up_res = apply_experience(move_pika, 1500)
    print(f" - Level Progression  : Lv.1 -> Lv.{move_pika.level}")
    prog_res = move_mgr.check_level_up_moves(lvl_up_res)
    print(f" - Learned Moves      : {[atk.name for atk in prog_res.learned_moves]}")
    print(f" - Skipped (Known)    : {[atk.name for atk in prog_res.skipped_moves]}")
    print(f" - Current Loadout    : {[atk.name for atk in move_pika.attacks]}")

    # Step 4: Full 4-move loadout generating pending replacement state
    print("\nStep 4: Move Limit Enforced (4 Moves Max) & Pending Move Generation:")
    move_mgr.learn_attack(move_pika, EMBER)
    print(f" - Volt now knows 4/4 moves: {[atk.name for atk in move_pika.attacks]}")

    # Advance Volt to Lv.10 where Thunderbolt is unlocked
    lvl_up_res_10 = apply_experience(move_pika, 3000)
    print(f" - Volt advances to Lv.{move_pika.level}")
    prog_res_10 = move_mgr.check_level_up_moves(lvl_up_res_10)
    print(f" - Auto-learned       : {[atk.name for atk in prog_res_10.learned_moves]}")
    print(f" - Pending Moves      : {[p.attack.name for p in prog_res_10.pending_moves]}")
    if prog_res_10.pending_moves:
        pending = prog_res_10.pending_moves[0]
        print(f" - Pending Details    : {pending.reason}")
    print(f" - Existing Loadout Intact: {[atk.name for atk in move_pika.attacks]}")

    # Step 5: Replacing a move successfully
    print("\nStep 5: Atomic Move Replacement:")
    print("Trainer decides to replace 'Ember' with pending 'Thunderbolt':")
    replace_res = move_mgr.replace_attack(move_pika, EMBER, THUNDERBOLT)
    print(f" - Success            : {replace_res.success}")
    print(f" - Outcome            : {replace_res.reason}")
    print(f" - Final Move Loadout : {[atk.name for atk in move_pika.attacks]}")
    print("=" * 60)

    # 16. Battle Status Effects & Move Effects Demonstration
    print("\n" + "=" * 60)
    print(" BATTLE STATUS EFFECTS & MOVE EFFECTS DEMONSTRATION")
    print("=" * 60)

    # Setup combatants
    status_pika = Pokemon(
        species=PIKACHU,
        personality=Personality(50, 50, 50, 50, 50, 50),
        level=10,
        nickname="Sparky",
        attacks=[THUNDER_SHOCK, GROWL],
    )
    status_charm = Pokemon(
        species=CHARMANDER,
        personality=Personality(50, 50, 50, 50, 50, 50),
        level=10,
        nickname="Char",
        attacks=[SCRATCH, WILL_O_WISP],
    )

    status_battle = Battle(pokemon1=status_pika, pokemon2=status_charm, seed=7, use_random_damage=False)
    status_battle.start()

    # Step 1: A move applying a status effect
    print("Step 1: Move Applying Status Effect (Will-O-Wisp -> Burn):")
    pika_hp_start = status_pika.current_hp
    turn1_res = status_battle.resolve_turn(attack1=THUNDER_SHOCK, attack2=WILL_O_WISP)
    print(f" - Turn 1 Action 1: {turn1_res.actions[0].message}")
    print(f" - Turn 1 Action 2: {turn1_res.actions[1].message}")
    print(f" - Sparky Afflicted with Burn? {status_battle.status_manager.has_effect(status_pika, StatusEffectType.BURN)}")

    # Step 2: End-of-turn damage from a persistent condition
    print("\nStep 2: End-of-Turn Damage from Persistent Burn:")
    print(f" - Sparky HP: {pika_hp_start} -> {status_pika.current_hp} / {status_pika.max_hp}")
    burn_events = [ev for ev in status_battle.events if "hurt by its burn" in ev]
    if burn_events:
        print(f" - Status Log : {burn_events[0]}")

    # Step 3: Paralysis check preventing a turn
    print("\nStep 3: Paralysis Check Preventing Action:")
    # Teach Sparky Thunder Wave and inflict paralysis on Char
    status_battle.status_manager.apply_effect(status_charm, AttackEffect(effect_type=StatusEffectType.PARALYSIS, chance=100))
    print(f" - Char afflicted with Paralysis: {status_battle.status_manager.has_effect(status_charm, StatusEffectType.PARALYSIS)}")
    # Trigger deterministic paralysis block
    para_eff = status_battle.status_manager.get_major_condition(status_charm)
    para_eff.paralysis_chance = 100
    turn2_res = status_battle.resolve_turn(attack1=THUNDER_SHOCK, attack2=SCRATCH)
    print(f" - Turn 2 Action 1: {turn2_res.actions[0].message}")
    print(f" - Turn 2 Action 2: {turn2_res.actions[1].message} (Turn Skipped!)")

    # Step 4: Temporary stat reduction changing damage
    print("\nStep 4: Temporary Stat Reduction Changing Damage (Growl -> Attack -20%):")
    para_eff.paralysis_chance = 0
    char_unmodified_atk = status_charm.attack
    unreduced_scratch_dmg = calculate_damage(attacker=status_charm, defender=status_pika, attack=SCRATCH, use_random_factor=False).damage
    turn3_res = status_battle.resolve_turn(attack1=GROWL, attack2=SCRATCH)
    print(f" - Turn 3 Action 1       : {turn3_res.actions[0].message}")
    reduced_scratch_dmg = turn3_res.actions[1].damage
    effective_char_atk = status_battle.status_manager.get_effective_stat(status_charm, "attack")
    print(f" - Char Base Attack      : {char_unmodified_atk}")
    print(f" - Char Effective Attack : {effective_char_atk} (-20% modifier applied)")
    print(f" - Turn 3 Action 2       : {turn3_res.actions[1].message}")
    print(f" - Scratch Damage Impact : Reduced from {unreduced_scratch_dmg} dmg -> {reduced_scratch_dmg} dmg!")

    # Step 5: Effect expiring and restoring previous effective stat
    print("\nStep 5: Effect Expiration and Stat Restoration:")
    print("Advancing turns until Growl's Attack reduction wears off...")
    turn4_res = status_battle.resolve_turn(attack1=THUNDER_SHOCK, attack2=SCRATCH)
    turn5_res = status_battle.resolve_turn(attack1=THUNDER_SHOCK, attack2=SCRATCH)
    wore_off_events = [ev for ev in status_battle.events if "wore off" in ev]
    if wore_off_events:
        print(f" - Expiration Log         : {wore_off_events[-1]}")
    restored_char_atk = status_battle.status_manager.get_effective_stat(status_charm, "attack")
    print(f" - Restored Char Attack   : {restored_char_atk} (Fully restored to baseline {char_unmodified_atk}!)")
    print("=" * 60)

    # -------------------------------------------------------------
    # 17. Player Inventory & Consumable Items Demonstration
    # -------------------------------------------------------------
    print("\n" + "=" * 60)
    print(" PLAYER INVENTORY & CONSUMABLE ITEMS DEMONSTRATION")
    print("=" * 60)

    item_mgr = ItemManager()

    # Step 1: Creating an inventory
    print("Step 1: Creating Player Inventory:")
    trainer_ash = Player(name="Ash")
    inv = trainer_ash.inventory
    print(f" - Trainer Name      : {trainer_ash.name}")
    print(f" - Inventory Slots   : {inv.slots_used}/{inv.capacity} used")

    # Step 2: Adding multiple item quantities
    print("\nStep 2: Stocking Inventory with Consumables:")
    inv.add_item("potion", 5)
    inv.add_item("super_potion", 2)
    inv.add_item("antidote", 3)
    inv.add_item("poke_ball", 10)
    print(f" - Slots Occupied    : {inv.slots_used}/{inv.capacity}")
    for item_id, qty in inv.list_items():
        print(f"   * {item_id:<14}: {qty} in stock")

    # Step 3: Healing a damaged Pokemon with a Potion
    print("\nStep 3: Healing Damaged Pokemon with Potion:")
    demo_personality = Personality(50, 50, 50, 50, 50, 50)
    demo_pika = Pokemon(species=PIKACHU, personality=demo_personality, level=5)
    demo_pika.take_damage(25)  # 45 -> 20 HP
    print(f" - Pikachu HP Before : {demo_pika.current_hp}/{demo_pika.max_hp}")
    print(f" - Potion Stock      : {inv.get_quantity('potion')}")
    heal_res = item_mgr.use_item(inv, "potion", demo_pika)
    print(f" - Operation Success : {heal_res.success}")
    print(f" - Result Message    : {heal_res.message}")
    print(f" - HP Restored       : +{heal_res.hp_restored} HP")
    print(f" - Pikachu HP After  : {demo_pika.current_hp}/{demo_pika.max_hp}")
    print(f" - Potion Stock After: {inv.get_quantity('potion')} (Consumed exactly 1!)")

    # Step 4: Curing a status condition
    print("\nStep 4: Curing Status Condition with Antidote:")
    demo_status_mgr = StatusEffectManager()
    demo_status_mgr.apply_effect(demo_pika, StatusEffectType.POISON)
    print(f" - Pikachu Afflicted : Poison={demo_status_mgr.has_effect(demo_pika, StatusEffectType.POISON)}")
    print(f" - Antidote Stock    : {inv.get_quantity('antidote')}")
    cure_res = item_mgr.use_item(inv, "antidote", demo_pika, demo_status_mgr)
    print(f" - Operation Success : {cure_res.success}")
    print(f" - Result Message    : {cure_res.message}")
    print(f" - Conditions Cured  : {[c.display_name for c in cure_res.status_conditions_cured]}")
    print(f" - Pikachu Afflicted : Poison={demo_status_mgr.has_effect(demo_pika, StatusEffectType.POISON)} (Cured!)")
    print(f" - Antidote Stock    : {inv.get_quantity('antidote')} (Consumed exactly 1!)")

    # Step 5: Showing that an unsuccessful item use does not consume the item
    print("\nStep 5: Failed Item Use Preserving Inventory State:")
    # Damaged by only 5 HP, heals to max
    demo_pika.take_damage(5)
    item_mgr.use_item(inv, "potion", demo_pika)
    print(f" - Pikachu HP Now    : {demo_pika.current_hp}/{demo_pika.max_hp} (Full HP)")
    potion_stock_before = inv.get_quantity("potion")
    print(f"Attempting to use Potion on Pikachu already at full HP (Stock: {potion_stock_before}):")
    fail_heal_res = item_mgr.use_item(inv, "potion", demo_pika)
    print(f" - Success           : {fail_heal_res.success}")
    print(f" - Message           : {fail_heal_res.message}")
    print(f" - Potion Stock After: {inv.get_quantity('potion')} (Preserved! 0 consumed)")

    antidote_stock_before = inv.get_quantity("antidote")
    print(f"Attempting to use Antidote on healthy Pikachu (Stock: {antidote_stock_before}):")
    fail_cure_res = item_mgr.use_item(inv, "antidote", demo_pika, demo_status_mgr)
    print(f" - Success           : {fail_cure_res.success}")
    print(f" - Message           : {fail_cure_res.message}")
    print(f" - Antidote Stock    : {inv.get_quantity('antidote')} (Preserved! 0 consumed)")

    # Step 6: Showing that Poke Ball use is explicitly unsupported for now
    print("\nStep 6: Capture Item (Poke Ball) Explicitly Unsupported:")
    pokeball_stock_before = inv.get_quantity("poke_ball")
    print(f"Attempting to use Poke Ball from inventory (Stock: {pokeball_stock_before}):")
    ball_res = item_mgr.use_item(inv, "poke_ball", demo_pika)
    print(f" - Success           : {ball_res.success}")
    print(f" - Message           : {ball_res.message}")
    print(f" - Poke Ball Stock   : {inv.get_quantity('poke_ball')} (Preserved! 0 consumed)")
    print("=" * 60)

    # -------------------------------------------------------------
    # 18. Save/Load & Game State Serialization Demonstration
    # -------------------------------------------------------------
    print("\n" + "=" * 60)
    print(" SAVE/LOAD & GAME STATE SERIALIZATION DEMONSTRATION")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as save_demo_dir:
        demo_save_path = Path(save_demo_dir) / "demo_slot_1.json"

        # Step 1: Create player with Pokemon team and inventory
        print("Step 1: Creating Player with Team & Inventory:")
        save_player = Player(name="Red", unique_id="trainer-red-001")
        save_player.inventory.add_item("potion", 4)
        save_player.inventory.add_item("super_potion", 2)
        save_player.inventory.add_item("antidote", 1)

        pika_pers = Personality(30, 80, 15, 85, 95, 75)
        pika_mon = Pokemon(
            species=PIKACHU,
            personality=pika_pers,
            level=12,
            experience=160,
            bond=50,
            obedience=95,
            unique_id="10099",
            nickname="Volt",
            attacks=[THUNDER_SHOCK, QUICK_ATTACK, THUNDERBOLT],
        )
        save_player.add_pokemon(pika_mon)
        save_player.add_to_team(pika_mon)
        save_player.set_active_pokemon(pika_mon)

        print(f" - Player Name       : {save_player.name} (ID: {save_player.unique_id})")
        print(f" - Team Size         : {len(save_player.team)} (Active: {save_player.active_pokemon.display_name})")
        print(f" - Inventory Slots   : {save_player.inventory.slots_used}/{save_player.inventory.capacity}")

        # Step 2: Modifying progression and training stats
        print("\nStep 2: Training & Modifying Progression:")
        pika_mon.set_trained_stat("attack", 15)
        pika_mon.set_trained_stat("speed", 20)
        pika_mon.take_damage(8)
        pika_mon.mark_level_move_awarded(1, "thunder shock")
        pika_mon.mark_level_move_awarded(5, "quick attack")
        print(f" - Trained Attack    : +{pika_mon.trained_attack} (Effective Attack: {pika_mon.attack})")
        print(f" - Trained Speed     : +{pika_mon.trained_speed} (Effective Speed: {pika_mon.speed})")
        print(f" - Current HP        : {pika_mon.current_hp}/{pika_mon.max_hp}")

        # Step 3: Saving the game
        print("\nStep 3: Atomically Saving Game to Disk:")
        save_game(save_player, demo_save_path)
        print(f" - Save File Name    : {demo_save_path.name}")
        print(f" - Save File Size    : {demo_save_path.stat().st_size} bytes (UTF-8 JSON)")

        # Step 4: Loading into a new player instance
        print("\nStep 4: Restoring Game into Independent Player Instance:")
        loaded_player = load_game(demo_save_path)
        print(f" - Restored Player   : {loaded_player.name} (ID: {loaded_player.unique_id})")
        print(f" - Restored Team Size: {len(loaded_player.team)}")
        print(f" - Restored Active   : {loaded_player.active_pokemon.display_name}")

        # Step 5: Verifying key values and object identity
        print("\nStep 5: Verifying Preserved Values & Identity Preservation:")
        loaded_pika = loaded_player.get_pokemon_by_id("10099")
        print(f" - Preserved ID      : {loaded_pika.unique_id} == '10099' ({loaded_pika.unique_id == '10099'})")
        print(f" - Preserved Nickname: {loaded_pika.nickname}")
        print(f" - Preserved Level/XP: Lv.{loaded_pika.level}, {loaded_pika.experience} XP")
        print(f" - Preserved HP      : {loaded_pika.current_hp}/{loaded_pika.max_hp}")
        print(f" - Preserved Bond/Ob : Bond={loaded_pika.bond}, Obedience={loaded_pika.obedience}")
        print(f" - Trained Atk/Spd   : Atk=+{loaded_pika.trained_attack}, Spd=+{loaded_pika.trained_speed}")
        print(f" - Team[0] is Coll[0]: {loaded_player.team[0] is loaded_pika} (Exact object identity guaranteed!)")
        print(f" - Active is Team[0] : {loaded_player.active_pokemon is loaded_pika} (Exact object identity guaranteed!)")
        print(f" - Inventory Potions : {loaded_player.inventory.get_quantity('potion')} (Preserved!)")

        # Step 6: Modifying loaded instance does NOT mutate original in-memory instance
        print("\nStep 6: Instance Isolation Verification:")
        loaded_player.name = "Red-Modified"
        loaded_pika.set_trained_stat("attack", 99)
        loaded_player.inventory.add_item("potion", 10)
        print(f" - Loaded Player Name: {loaded_player.name}")
        print(f" - Original Name     : {save_player.name} (Unchanged!)")
        print(f" - Loaded Pika Atk   : {loaded_pika.trained_attack}")
        print(f" - Original Pika Atk : {pika_mon.trained_attack} (Unchanged!)")
        print(f" - Loaded Potions    : {loaded_player.inventory.get_quantity('potion')}")
        print(f" - Original Potions  : {save_player.inventory.get_quantity('potion')} (Unchanged!)")

        # Step 7: Handling a save/load error cleanly
        print("\nStep 7: Robust Error Handling Demonstration:")
        corrupt_path = Path(save_demo_dir) / "corrupt_save.json"
        corrupt_path.write_text("{ corrupt json data ...", encoding="utf-8")
        try:
            load_game(corrupt_path)
            print(" - Error Handling    : FAILED (Expected exception)")
        except SaveDataError as err:
            print(f" - Caught SaveDataError cleanly:")
            print(f"   * {err}")

        missing_path = Path(save_demo_dir) / "non_existent.json"
        try:
            load_game(missing_path)
        except SaveDataError as err:
            print(f" - Missing File Error:")
            print(f"   * {err}")
    print("=" * 60)

    # 19. Quest & Objective System Demonstration
    print("\n" + "=" * 60)
    print(" QUEST & OBJECTIVE SYSTEM DEMONSTRATION")
    print("=" * 60)

    quest_player = Player(name="Ash Ketchum", inventory=Inventory(capacity=20))
    quest_mgr = QuestManager()

    # Step 1: Listing initial catalog quests and player statuses
    print("Step 1: Inspecting Available Quests in Catalog for New Trainer:")
    available_initial = quest_mgr.list_available_quests(quest_player)
    print(f" - Initial Available Quests: {[q.name for q in available_initial]}")
    for q_def in available_initial[:3]:
        print(f"   * [{q_def.quest_id}] '{q_def.name}': {q_def.description}")
        print(f"     Objectives : {[o.description for o in q_def.objectives]}")
        print(f"     Rewards    : {q_def.rewards}")

    # Step 2: Checking a locked quest (prerequisites not met)
    print("\nStep 2: Checking Prerequisite Enforcement (Locked Quest):")
    res_research_status = quest_mgr.get_quest_status(quest_player, "species_research")
    print(f" - 'Species Research' Status : {res_research_status.value.upper()} (Requires 'first_encounter')")
    accept_locked = quest_mgr.accept_quest(quest_player, "species_research")
    print(f" - Attempt to Accept Locked : Success={accept_locked.success}, Message='{accept_locked.message}'")

    # Step 3: Accepting 'First Encounter'
    print("\nStep 3: Accepting Quest 'First Encounter':")
    accept_fe = quest_mgr.accept_quest(quest_player, "first_encounter")
    print(f" - Quest Accepted          : Success={accept_fe.success}, Message='{accept_fe.message}'")
    fe_prog = quest_mgr.get_quest_progress(quest_player, "first_encounter")
    print(f" - Quest Status            : {fe_prog.status.value.upper()}")
    print(f" - Objectives Progress     : {[(o.objective_id, o.current_count, o.target_count, o.is_completed) for o in fe_prog.objective_progress.values()]}")

    # Step 4: Advancing and completing quest via gameplay event
    print("\nStep 4: Dispatching Gameplay Event ('pokemon_captured'):")
    print("Ash ventures into tall grass and captures a wild Pikachu!")
    evt_res = quest_mgr.record_capture(quest_player, species_name="Pikachu", event_id="cap_demo_001")
    print(f" - Event Processed         : {evt_res.events_processed}")
    print(f" - Objectives Updated      : {evt_res.objectives_updated}")
    print(f" - Quests Completed        : {evt_res.quests_completed}")
    print(f" - 'First Encounter' Status: {quest_mgr.get_quest_status(quest_player, 'first_encounter').value.upper()}")

    # Step 5: Downstream quests unlocked
    print("\nStep 5: Verifying Downstream Quests Unlocked:")
    print(f" - 'Species Research' Status: {quest_mgr.get_quest_status(quest_player, 'species_research').value.upper()} (Unlocked!)")
    print(f" - 'Growing Stronger' Status: {quest_mgr.get_quest_status(quest_player, 'growing_stronger').value.upper()} (Unlocked!)")

    # Step 6: Claiming rewards atomically
    print("\nStep 6: Atomically Claiming Quest Rewards:")
    print(f" - Bag Potions Before Claim: {quest_player.inventory.get_quantity('potion')}")
    claim_res = quest_mgr.claim_rewards(quest_player, "first_encounter")
    print(f" - Claim Result            : Success={claim_res.success}, Message='{claim_res.message}'")
    print(f" - Items Granted           : {claim_res.items_granted}")
    print(f" - Bag Potions After Claim : {quest_player.inventory.get_quantity('potion')}")

    # Step 7: Duplicate claim rejected
    print("\nStep 7: Rejecting Duplicate Reward Claim:")
    dup_claim = quest_mgr.claim_rewards(quest_player, "first_encounter")
    print(f" - Duplicate Claim Result  : Success={dup_claim.success}, Message='{dup_claim.message}'")

    # Step 8: Persistence across Save/Load
    print("\nStep 8: Save/Load Serialization & Quest Progress Restoration:")
    with tempfile.TemporaryDirectory() as q_temp_dir:
        q_save_path = Path(q_temp_dir) / "quest_demo_save.json"
        save_game(quest_player, q_save_path)
        print(f" - Game Saved Successfully to: {q_save_path.name}")

        restored_player = load_game(q_save_path)
        restored_fe = quest_mgr.get_quest_progress(restored_player, "first_encounter")
        print(f" - Restored Player Name    : {restored_player.name}")
        print(f" - Restored Quest Status   : {restored_fe.status.value.upper()}")
        print(f" - Rewards Already Claimed : {restored_fe.rewards_claimed}")
        print(f" - Restored Potion Count   : {restored_player.inventory.get_quantity('potion')}")
    print("=" * 60)

    # 20. World Interaction & Resource Gathering Demonstration
    print("\n" + "=" * 60)
    print(" WORLD INTERACTION & RESOURCE GATHERING DEMONSTRATION")
    print("=" * 60)

    sim_time = 500.0
    world_player = Player(name="Explorer Red", inventory=Inventory(capacity=20))
    world_qm = QuestManager()
    # Accept stocking_supplies (Collect 3 potions) to demonstrate quest integration
    world_qm.accept_quest(world_player, "stocking_supplies")

    world_mgr = WorldInteractionManager(
        quest_manager=world_qm,
        clock=lambda: sim_time,
    )

    # Step 1: Listing interactable objects in world
    print("Step 1: Listing Registered World Objects:")
    for obj in world_mgr.list_objects():
        print(f" - [{obj.interactable_type.name}] '{obj.name}' (ID: {obj.object_id}) at {obj.position}, radius={obj.interaction_radius}")

    # Step 2: Gathering from a resource node (Berry Bush)
    print("\nStep 2: Gathering from Resource Node (Berry Bush):")
    print(f" - Player Position       : (5.0, 5.0) (Adjacent to bush)")
    print(f" - Player Potions Before : {world_player.inventory.get_quantity('potion')}")
    gather_res = world_mgr.interact(world_player, "berry_bush_route1", (5.0, 5.0), sim_time)
    print(f" - Gather Success         : {gather_res.success}")
    print(f" - Outcome Message        : {gather_res.message}")
    print(f" - Items Granted          : {gather_res.items_granted}")
    print(f" - Player Potions After  : {world_player.inventory.get_quantity('potion')}")
    stocking_prog = world_qm.get_quest_progress(world_player, "stocking_supplies")
    pot_cnt = stocking_prog.objective_progress["collect_potions"].current_count if stocking_prog else 0
    print(f" - Quest Progress Sync    : Stocking Supplies = {pot_cnt}/3 Potions")

    # Step 3: Showing node unavailable state and respawn deadline
    print("\nStep 3: Resource Cooldown & Respawn Deadline:")
    bush = world_mgr.get_object("berry_bush_route1")
    print(f" - Bush Available Now?   : {bush.is_available} (Depleted at t={sim_time})")
    print(f" - Respawn Deadline       : t={bush.respawn_deadline} (Cooldown: 60s)")
    mid_res = world_mgr.interact(world_player, "berry_bush_route1", (5.0, 5.0), sim_time + 20.0)
    print(f" - Regather at t=520.0s   : Success={mid_res.success}, Message='{mid_res.message}'")

    # Step 4: Proximity validation (attempting interaction too far away)
    print("\nStep 4: Proximity Validation (Too Far Away):")
    far_res = world_mgr.interact(world_player, "berry_bush_route1", (15.0, 15.0), sim_time + 70.0)
    print(f" - Player Position       : (15.0, 15.0) (Distance ~14.1 units)")
    print(f" - Result                 : Success={far_res.success}")
    print(f" - Outcome Message        : {far_res.message}")

    # Step 5: Opening a treasure (supply cache) with multiple items
    print("\nStep 5: Opening Treasure Cache (Multi-Item Atomic Grant):")
    cache_res = world_mgr.interact(world_player, "supply_cache_01", (15.0, 10.0), sim_time)
    print(f" - Cache Open Result     : Success={cache_res.success}")
    print(f" - Outcome Message        : {cache_res.message}")
    print(f" - Items Granted          : {cache_res.items_granted}")
    print(f" - Super Potions in Bag   : {world_player.inventory.get_quantity('super_potion')}")
    print(f" - Antidotes in Bag       : {world_player.inventory.get_quantity('antidote')}")
    print(f" - Is Treasure Looted?    : {world_player.is_treasure_collected('supply_cache_01')}")

    # Step 6: Reading a sign
    print("\nStep 6: Reading Informational Signpost:")
    sign_res = world_mgr.interact(world_player, "route1_sign", (2.0, 1.0), sim_time)
    print(f" - Sign Read Success      : {sign_res.success}")
    print(f" - Sign Inscription       : {sign_res.interaction_text}")
    print(f" - Bag Stacks Occupied    : {world_player.inventory.slots_used} (Unchanged)")

    # Step 7: Atomic failure when inventory cannot hold items
    print("\nStep 7: Atomic Failure on Full Inventory:")
    full_inv = Inventory(capacity=1)
    full_inv.add_item("potion", 1)  # 1/1 slots filled
    constrained_player = Player(name="Packed Bag", inventory=full_inv)
    # Attempt to open cache (requires 2 slots for super_potion and antidote)
    fail_loot = world_mgr.interact(constrained_player, "supply_cache_01", (15.0, 10.0), sim_time)
    print(f" - Attempt to Loot Cache  : Success={fail_loot.success}")
    print(f" - Outcome Message        : {fail_loot.message}")
    print(f" - Inventory slots used   : {constrained_player.inventory.slots_used}/1 (Untouched!)")
    print(f" - Treasure Looted State  : {constrained_player.is_treasure_collected('supply_cache_01')} (Preserved unlooted!)")

    # Step 8: Save/Load persistence of collected treasure state
    print("\nStep 8: Save/Load Serialization & Persistent Treasure State:")
    with tempfile.TemporaryDirectory() as world_temp_dir:
        w_save_path = Path(world_temp_dir) / "world_demo_save.json"
        save_game(world_player, w_save_path)
        print(f" - Saved Player State to Disk: {w_save_path.name}")

        restored_world_player = load_game(w_save_path)
        print(f" - Restored Player Name  : {restored_world_player.name}")
        print(f" - Restored Treasures    : {restored_world_player.collected_treasures}")
        print(f" - Cache Already Looted? : {restored_world_player.is_treasure_collected('supply_cache_01')}")
        # Trying to loot again with restored player is rejected
        reloot = world_mgr.interact(restored_world_player, "supply_cache_01", (15.0, 10.0), sim_time)
        print(f" - Re-loot Attempt       : Success={reloot.success}, Message='{reloot.message}'")
    print("=" * 60)

    # 21. World Exploration, Map Regions & Discovery Demonstration
    print("\n" + "=" * 60)
    print(" WORLD EXPLORATION, MAP REGIONS & DISCOVERY DEMONSTRATION")
    print("=" * 60)

    explore_player = Player(name="Pathfinder Gary", inventory=Inventory(capacity=20))
    explore_qm = QuestManager()
    # Fulfill prerequisite and accept trailblazer quest to demonstrate quest integration
    explore_qm.accept_quest(explore_player, "first_encounter")
    explore_qm.record_capture(explore_player, "Pikachu", event_id="gary_cap_001")
    accept_tb = explore_qm.accept_quest(explore_player, "trailblazer")

    explore_interaction_mgr = WorldInteractionManager(
        objects=create_default_world_objects(),
        quest_manager=explore_qm,
    )
    explore_mgr = WorldExplorationManager(
        regions=create_default_world_regions(),
        interaction_manager=explore_interaction_mgr,
        quest_manager=explore_qm,
    )

    # Step 1: Listing available regions
    print("Step 1: Listing Registered World Regions:")
    for reg in explore_mgr.list_regions():
        print(f" - [{reg.region_id}] '{reg.name}' | Bounds: {reg.bounds} | Landmarks: {reg.landmark_ids}")

    # Step 2: Finding region containing sample positions
    print("\nStep 2: Spatial Region Lookup (find_region):")
    sample_pt_meadow = (4.0, 6.0)
    found_reg_1 = explore_mgr.find_region(sample_pt_meadow)
    print(f" - Coordinate {sample_pt_meadow} -> Region: '{found_reg_1.name if found_reg_1 else None}'")
    sample_pt_trail = (15.0, 10.0)
    found_reg_2 = explore_mgr.find_region(sample_pt_trail)
    print(f" - Coordinate {sample_pt_trail} -> Region: '{found_reg_2.name if found_reg_2 else None}'")
    sample_pt_void = (99.0, 99.0)
    found_reg_3 = explore_mgr.find_region(sample_pt_void)
    print(f" - Coordinate {sample_pt_void} -> Region: {found_reg_3} (Outside all regions)")

    # Step 3: Discovering a region for the first time
    print("\nStep 3: Discovering a Region for the First Time:")
    disc_1 = explore_mgr.discover_region(explore_player, "starting_meadow")
    print(f" - Discovery Success     : {disc_1.success}")
    print(f" - First Discovery?       : {disc_1.is_first_discovery}")
    print(f" - Outcome Message        : {disc_1.message}")
    print(f" - Discovery Narrative    : {disc_1.discovery_text}")
    print(f" - Quest Event Emitted?   : {disc_1.event_emitted}")
    tb_prog = explore_qm.get_quest_progress(explore_player, "trailblazer")
    print(f" - Trailblazer Meadow Obj : {tb_prog.objective_progress['discover_meadow'].is_completed} (Progress: {tb_prog.objective_progress['discover_meadow'].current_count}/1)")

    # Step 4: Attempting to discover the same region again
    print("\nStep 4: Attempting to Discover the Same Region Again:")
    disc_dup = explore_mgr.discover_region(explore_player, "starting_meadow")
    print(f" - Discovery Success     : {disc_dup.success}")
    print(f" - First Discovery?       : {disc_dup.is_first_discovery} (Duplicate ignored)")
    print(f" - Outcome Message        : {disc_dup.message}")
    print(f" - Quest Event Emitted?   : {disc_dup.event_emitted}")

    # Step 5: Discovering an existing nearby landmark through intended interaction sequence
    print("\nStep 5: Discovering Landmark Through Interaction (Thunder Stone Shrine):")
    # Shrine is at (25.0, 25.0) with radius 3.0
    landmark_res = explore_interaction_mgr.interact(
        player=explore_player,
        object_id="ancient_shrine",
        player_position=(25.0, 25.0),
    )
    print(f" - Landmark Interact Res : {landmark_res.success}")
    print(f" - Landmark First Time?  : {landmark_res.is_first_discovery}")
    print(f" - Message / Lore         : {landmark_res.message}")
    print(f" - Player Discovered Set : {explore_player.discovered_landmarks}")
    print(f" - Trailblazer Shrine Obj : {tb_prog.objective_progress['discover_shrine'].is_completed} (Progress: {tb_prog.objective_progress['discover_shrine'].current_count}/1)")
    print(f" - Trailblazer Quest Done : {tb_prog.is_completed} (Status: {tb_prog.status.value.upper()})")

    # Step 6: Showing that an out-of-range interaction fails
    print("\nStep 6: Landmark Out-of-Range Discovery Failure:")
    far_landmark_res = explore_mgr.discover_landmark(
        player=explore_player,
        landmark_id="ancient_shrine",
        player_position=(0.0, 0.0),
    )
    print(f" - Out-of-Range Result   : {far_landmark_res.success}")
    print(f" - Error Type             : {far_landmark_res.error_type}")
    print(f" - Outcome Message        : {far_landmark_res.message}")

    # Step 7: Showing quest-event integration and deduplication
    print("\nStep 7: Quest Event Integration & Deduplication:")
    tb_status = explore_qm.get_quest_status(explore_player, "trailblazer")
    print(f" - Trailblazer Status     : {tb_status.value.upper()}")
    # Replay identical event
    dedup_res = explore_qm.record_event(
        explore_player,
        QuestEventType.REGION_DISCOVERED,
        payload={"region_id": "starting_meadow"},
        event_id=f"quest_evt_region_starting_meadow_{explore_player.unique_id}",
    )
    print(f" - Replayed Event Process : {dedup_res.message}")

    # Step 8: Saving and restoring discovered regions and landmarks
    print("\nStep 8: Saving and Restoring Discovered Regions & Landmarks (Schema v4):")
    # Also collect a treasure on explore_player to verify existing treasure persistence
    explore_player.mark_treasure_collected("supply_cache_01")

    with tempfile.TemporaryDirectory() as exp_temp_dir:
        exp_save_path = Path(exp_temp_dir) / "exploration_demo_save.json"
        save_game(explore_player, exp_save_path)
        print(f" - Saved Game to Disk     : {exp_save_path.name}")

        restored_explorer = load_game(exp_save_path)
        print(f" - Restored Player Name   : {restored_explorer.name}")
        print(f" - Restored Regions       : {restored_explorer.discovered_regions}")
        print(f" - Restored Landmarks     : {restored_explorer.discovered_landmarks}")
        print(f" - Preserved Treasures    : {restored_explorer.collected_treasures}")
        print(f" - Region Still Marked?   : {restored_explorer.is_region_discovered('starting_meadow')}")
        print(f" - Shrine Still Marked?   : {restored_explorer.is_landmark_discovered('ancient_shrine')}")

        # Step 9: Confirming existing treasure persistence still works
        print("\nStep 9: Confirming Treasure Persistence & Backward Compatibility:")
        print(f" - Is Cache Already Looted: {restored_explorer.is_treasure_collected('supply_cache_01')}")
    print("=" * 60)

    # 22. Dynamic Pokemon Encounters, Habitats & Time-Based Spawning Demonstration
    print("\n" + "=" * 60)
    print(" DYNAMIC POKEMON ENCOUNTERS, HABITATS & TIME-BASED SPAWNING DEMONSTRATION")
    print("=" * 60)

    # Initialize habitat subsystem with seeded RNG for reproducible demonstration
    demo_hab_player = Player(name="Trainer Blue")
    demo_explore_mgr = WorldExplorationManager()
    demo_spawn_mgr = SpawnManager(seed=777)
    demo_encounter_mgr = EncounterManager()
    demo_quest_mgr = QuestManager()

    demo_habitat_mgr = HabitatManager(
        exploration_manager=demo_explore_mgr,
        spawn_manager=demo_spawn_mgr,
        encounter_manager=demo_encounter_mgr,
        quest_manager=demo_quest_mgr,
        seed=777,
    )

    # Step 1: Listing Configured Habitats
    print("Step 1: Listing Configured Habitats in Catalog:")
    for hab in list_habitats():
        cand_summary = ", ".join(f"{c.species.name} (w={c.weight}, lv={c.min_level}-{c.max_level})" for c in hab.candidates)
        times_summary = ", ".join(sorted(set(t.value for c in hab.candidates for t in c.allowed_times)))
        print(f" - [{hab.habitat_id}] '{hab.name}': {hab.description}")
        print(f"   Associated Regions : {hab.region_ids}")
        print(f"   Active Periods     : [{times_summary}]")
        print(f"   Candidates         : [{cand_summary}]")

    # Step 2: Resolving a Habitat from a Known World Region
    print("\nStep 2: Resolving Habitat from World Region:")
    resolved_meadow = demo_habitat_mgr.get_habitat_for_region("starting_meadow")
    resolved_forest = demo_habitat_mgr.get_habitat_for_region("forest_trail")
    print(f" - Region 'starting_meadow' -> Habitat: '{resolved_meadow.name}' (ID: {resolved_meadow.habitat_id})")
    print(f" - Region 'forest_trail'    -> Habitat: '{resolved_forest.name}' (ID: {resolved_forest.habitat_id})")

    # Step 3: Selecting a Pokémon During the Day
    print("\nStep 3: Selecting Wild Pokemon During Daytime (12:00 / DAY):")
    day_selection = demo_habitat_mgr.select_spawn(
        region_id="starting_meadow",
        time_of_day=12.0,  # 12:00 -> TimeOfDay.DAY
    )
    print(f" - Region              : {day_selection.region_id}")
    print(f" - Input Hour          : 12.0 -> {day_selection.time_of_day.value.upper()}")
    print(f" - Selection Success   : {day_selection.success}")
    print(f" - Selected Species    : {day_selection.species.name} (Lv.{day_selection.level})")
    print(f" - Eligible Candidates : {day_selection.eligible_count}")
    print(f" - Outcome Message     : {day_selection.message}")

    # Step 4: Selecting from a Different Time Period (NIGHT)
    print("\nStep 4: Selecting Wild Pokemon from a Different Time Period (22:30 / NIGHT in Forest):")
    night_selection = demo_habitat_mgr.select_spawn(
        region_id="forest_trail",
        time_of_day=22.5,  # 22:30 -> TimeOfDay.NIGHT
    )
    print(f" - Region              : {night_selection.region_id}")
    print(f" - Input Hour          : 22.5 -> {night_selection.time_of_day.value.upper()}")
    print(f" - Selection Success   : {night_selection.success}")
    print(f" - Selected Species    : {night_selection.species.name} (Lv.{night_selection.level})")
    print(f" - Eligible Candidates : {night_selection.eligible_count}")
    print(f" - Outcome Message     : {night_selection.message}")

    # Step 5: Showing a Species Excluded by a Habitat or Time Restriction
    print("\nStep 5: Showing Species Excluded by Habitat and Time Restrictions:")
    meadow_eligible_night = demo_habitat_mgr.get_eligible_species("starting_meadow", TimeOfDay.NIGHT)
    print(f" - Starting Meadow Eligible Species at NIGHT : {[s.name for s in meadow_eligible_night]} (Pikachu is diurnal!)")
    forest_day_species = [s.name for s in demo_habitat_mgr.get_eligible_species("forest_trail", TimeOfDay.DAY)]
    print(f" - Forest Trail Eligible Species at DAY      : {forest_day_species} (Squirtle excluded by habitat!)")

    # Step 6: Showing Clean Failures for Unknown Region and Empty Pool
    print("\nStep 6: Demonstrating Clean Failures (Unknown Region & Empty Candidate Pool):")
    unknown_res = demo_habitat_mgr.select_spawn(region_id="volcano_core", time_of_day=TimeOfDay.DAY)
    print(f" - Unknown Region Result : Success={unknown_res.success}, Error={unknown_res.error_type}")
    print(f"   Message               : {unknown_res.message}")

    empty_pool_res = demo_habitat_mgr.select_spawn(region_id="starting_meadow", time_of_day=TimeOfDay.NIGHT)
    print(f" - Empty Pool Result     : Success={empty_pool_res.success}, Error={empty_pool_res.error_type}")
    print(f"   Message               : {empty_pool_res.message}")

    # Step 7: Starting an Encounter Through the Existing Encounter Manager
    print("\nStep 7: Starting Wild Encounter Through EncounterManager:")
    enc_trigger_res = demo_habitat_mgr.trigger_encounter(
        player=demo_hab_player,
        region_id="starting_meadow",
        time_of_day=TimeOfDay.MORNING,
    )
    print(f" - Encounter Success     : {enc_trigger_res.success}")
    print(f" - Wild Pokemon          : {enc_trigger_res.pokemon.display_name} (Lv.{enc_trigger_res.pokemon.level})")
    print(f" - Session ID            : {enc_trigger_res.encounter.encounter_id[:8]}...")
    print(f" - Encounter Active?     : {enc_trigger_res.encounter.is_active}")
    print(f" - Manager Has Active?   : {demo_encounter_mgr.has_active_encounter(demo_hab_player)}")
    print(f" - Outcome Message       : {enc_trigger_res.message}")

    # Prevent concurrent encounter (Singleton rule)
    dup_enc_res = demo_habitat_mgr.trigger_encounter(
        player=demo_hab_player,
        region_id="forest_trail",
        time_of_day=TimeOfDay.DAY,
    )
    print(f" - Concurrent Attempt    : Success={dup_enc_res.success}, Error={dup_enc_res.error_type}")
    print(f"   Outcome Message       : {dup_enc_res.message}")

    # Conclude encounter
    demo_encounter_mgr.resolve_active_encounter(demo_hab_player, reason="Fled from wild Pikachu")
    print(f" - Encounter Concluded   : Active={demo_encounter_mgr.has_active_encounter(demo_hab_player)}")

    # Step 8: Demonstrating Deterministic Selection with a Seeded Generator
    print("\nStep 8: Demonstrating Deterministic Seeded Selection Reproducibility:")
    seq_a = [demo_habitat_mgr.select_spawn(region_id="forest_trail", time_of_day=TimeOfDay.DAY, rng=random.Random(999)).species.name for _ in range(5)]
    seq_b = [demo_habitat_mgr.select_spawn(region_id="forest_trail", time_of_day=TimeOfDay.DAY, rng=random.Random(999)).species.name for _ in range(5)]
    print(f" - Generator A Sequence  : {seq_a}")
    print(f" - Generator B Sequence  : {seq_b}")
    print(f" - Sequences Match?      : {seq_a == seq_b}")

    # Step 9: Demonstrating Spawn Capacity and Respawn Cooldown Behavior
    print("\nStep 9: Demonstrating Spawn Capacity and Respawn Cooldown Behavior:")
    demo_spawn_area = SpawnArea(
        area_id="demo_meadow_zone",
        name="Meadow Spawns",
        allowed_species=(PIKACHU, SQUIRTLE),
        max_active_pokemon=2,
    )
    demo_spawn_mgr.register_area(demo_spawn_area)
    print(f" - Registered Area       : '{demo_spawn_area.name}' (Cap: {demo_spawn_area.max_active_pokemon})")
    print(f" - Active Count Before   : {demo_spawn_mgr.get_active_count('demo_meadow_zone')}")
    print(f" - Can Spawn At t=200.0? : {demo_spawn_mgr.can_spawn('demo_meadow_zone', current_time=200.0)}")

    # Set 45s respawn cooldown
    demo_spawn_mgr.set_area_cooldown("demo_meadow_zone", cooldown_duration=45.0, current_time=200.0)
    print(f" - Cooldown Set          : 45s (Deadline t=245.0)")
    print(f" - Can Spawn At t=220.0? : {demo_spawn_mgr.can_spawn('demo_meadow_zone', current_time=220.0)} (On Cooldown)")
    print(f" - Can Spawn At t=250.0? : {demo_spawn_mgr.can_spawn('demo_meadow_zone', current_time=250.0)} (Cooldown Expired)")

    # Step 10: Demonstrating Quest Event Integration & Deduplication
    print("\nStep 10: Demonstrating Quest Event Integration & Deduplication:")
    quest_enc_res = demo_habitat_mgr.trigger_encounter(
        player=demo_hab_player,
        region_id="forest_trail",
        time_of_day=TimeOfDay.DAY,
    )
    print(f" - Encounter Triggered   : Success={quest_enc_res.success}, Wild={quest_enc_res.pokemon.species.name}")
    print(f" - Quest Event Emitted?  : {quest_enc_res.event_emitted}")

    # Deduplicate replayed encounter event
    evt_dedup_res = demo_quest_mgr.record_encounter(
        player=demo_hab_player,
        species_name=quest_enc_res.pokemon.species.name,
        habitat_id="forest",
        event_id=f"quest_evt_encounter_{quest_enc_res.pokemon.unique_id}_{demo_hab_player.unique_id}",
    )
    print(f" - Replayed Event Result : {evt_dedup_res.message}")
    demo_encounter_mgr.resolve_active_encounter(demo_hab_player, reason="Captured")
    # 23. Turn-Based Battle Engine, Move Resolution & Battle Rewards Demonstration
    print("\n" + "=" * 60)
    print(" TURN-BASED BATTLE ENGINE, MOVE RESOLUTION & REWARDS DEMONSTRATION")
    print("=" * 60)

    # Step 1: Initializing Battle Manager and Player Setup
    print("Step 1: Initializing Battle Manager and Participants:")
    demo_battle_player = Player(name="Ash Ketchum")
    demo_battle_pika = Pokemon(
        species=PIKACHU,
        personality=Personality(50, 50, 50, 50, 50, 50),
        level=5,
        attacks=[THUNDER_SHOCK, QUICK_ATTACK],
    )
    demo_battle_squirtle = Pokemon(
        species=SQUIRTLE,
        personality=Personality(50, 50, 50, 50, 50, 50),
        level=5,
        attacks=[WATER_GUN, TACKLE],
    )
    demo_battle_player.add_pokemon(demo_battle_pika)
    demo_battle_player.add_pokemon(demo_battle_squirtle)
    demo_battle_player.add_to_team(demo_battle_pika)
    demo_battle_player.add_to_team(demo_battle_squirtle)
    demo_battle_player.set_active_pokemon(demo_battle_pika)

    demo_battle_area = SpawnArea(
        area_id="demo_battle_forest",
        name="Viridian Combat Zone",
        allowed_species=(PIKACHU, CHARMANDER, SQUIRTLE),
        max_active_pokemon=3,
    )
    demo_battle_spawn_mgr = SpawnManager()
    demo_battle_spawn_mgr.register_area(demo_battle_area)
    demo_battle_enc_mgr = EncounterManager(spawn_manager=demo_battle_spawn_mgr)
    demo_battle_exp_mgr = ExperienceManager()
    demo_battle_bond_mgr = BondManager()
    demo_battle_quest_mgr = QuestManager()
    demo_battle_mgr = BattleManager(
        spawn_manager=demo_battle_spawn_mgr,
        encounter_manager=demo_battle_enc_mgr,
        experience_manager=demo_battle_exp_mgr,
        bond_manager=demo_battle_bond_mgr,
        quest_manager=demo_battle_quest_mgr,
        seed=101,
    )
    print(f" - Player Name           : {demo_battle_player.name}")
    print(f" - Active Pokemon        : {demo_battle_player.active_pokemon.display_name} (Lv.{demo_battle_player.active_pokemon.level})")
    print(f" - Team Size             : {len(demo_battle_player.team)} (Pikachu, Squirtle)")

    # Step 2: Wild Encounter Initiation and Starting Battle
    print("\nStep 2: Starting Wild Pokemon Battle from Encounter Session:")
    wild_charmander = Pokemon(
        species=CHARMANDER,
        personality=Personality(50, 50, 50, 50, 50, 50),
        level=5,
        attacks=[EMBER, SCRATCH],
    )
    demo_battle_spawn_mgr.add_active_pokemon("demo_battle_forest", wild_charmander, (2.0, 3.0))
    wild_enc_session = demo_battle_enc_mgr.start_encounter(
        player=demo_battle_player,
        pokemon=wild_charmander,
        area=demo_battle_area,
    )
    active_battle = demo_battle_mgr.start_wild_battle(demo_battle_player, wild_enc_session)
    print(f" - Battle Started ID     : {active_battle.battle_id[:8]}...")
    print(f" - Opponent Species      : {active_battle.pokemon2.display_name} (Lv.{active_battle.pokemon2.level})")
    print(f" - Initial Battle State  : {active_battle.state}")
    print(f" - Has Active Battle?    : {demo_battle_mgr.has_active_battle(demo_battle_player)}")

    # Step 3: Turn Actions: Attack, Speed Priority & Damage
    print("\nStep 3: Executing Attack Action (Quick Attack vs Scratch):")
    atk_result = demo_battle_mgr.attack(demo_battle_player, QUICK_ATTACK)
    print(f" - Action Accepted?      : {atk_result.accepted}")
    print(f" - Turn Number           : {atk_result.turn_result.turn_number}")
    print(f" - First Action Executed : {atk_result.turn_result.actions[0].message}")
    print(f" - Second Action Executed: {atk_result.turn_result.actions[1].message}")
    print(f" - Pikachu HP Remaining  : {demo_battle_pika.current_hp}/{demo_battle_pika.max_hp}")
    print(f" - Charmander HP Rem.    : {wild_charmander.current_hp}/{wild_charmander.max_hp}")

    # Step 4: Team Switching Action Priority & Opponent Reaction
    print("\nStep 4: Executing Switch Action to Squirtle:")
    switch_res = demo_battle_mgr.switch(demo_battle_player, demo_battle_squirtle)
    print(f" - Switch Accepted?      : {switch_res.accepted}")
    print(f" - New Active Pokemon    : {demo_battle_player.active_pokemon.display_name}")
    print(f" - Opponent Counter-Hit  : {switch_res.turn_result.actions[0].message if switch_res.turn_result.actions else 'None'}")
    print(f" - Squirtle HP Remaining : {demo_battle_squirtle.current_hp}/{demo_battle_squirtle.max_hp}")

    # Step 5: Victory, Authoritative Rewards & Progression
    print("\nStep 5: Concluding Battle via Super-Effective KO (Water Gun):")
    wild_charmander.current_hp = 2  # Set low HP for decisive knockout
    win_res = demo_battle_mgr.attack(demo_battle_player, WATER_GUN)
    print(f" - Final Action Result   : {win_res.accepted}")
    print(f" - Decisive Action       : {win_res.turn_result.actions[0].message}")
    print(f" - Terminal State        : {win_res.battle_state}")
    print(f" - Battle Winner         : {active_battle.winner.display_name}")
    print(f" - Squirtle XP Before    : 0 XP")
    print(f" - Squirtle XP After     : {demo_battle_squirtle.experience} XP (+250 XP earned)")
    print(f" - Squirtle Bond After   : {demo_battle_squirtle.bond}/100 (+5 bond awarded)")

    # Step 6: Quest Event Ingestion & Deduplication
    print("\nStep 6: Quest Event Ingestion & Deduplication:")
    demo_battle_quest_mgr.accept_quest(demo_battle_player, "wild_challenger")
    # Manually re-verify defeat progress advances quest
    q_evt_res = demo_battle_quest_mgr.record_event(
        player=demo_battle_player,
        event_type=QuestEventType.POKEMON_DEFEATED,
        payload={"species_name": "Charmander", "level": 5},
        event_id=f"quest_evt_battle_defeat_{active_battle.battle_id}_{wild_charmander.unique_id}",
    )
    print(f" - Quest Defeat Recorded : {q_evt_res.objectives_updated} objective(s) updated")
    # Replay same event ID
    q_dedup_res = demo_battle_quest_mgr.record_event(
        player=demo_battle_player,
        event_type=QuestEventType.POKEMON_DEFEATED,
        payload={"species_name": "Charmander", "level": 5},
        event_id=f"quest_evt_battle_defeat_{active_battle.battle_id}_{wild_charmander.unique_id}",
    )
    print(f" - Duplicate Event Replay: {q_dedup_res.message}")

    # Step 7: Wild Encounter & Spawn Area Cleanup
    print("\nStep 7: Wild Encounter & Spawn Population Cleanup:")
    print(f" - Has Active Battle?    : {demo_battle_mgr.has_active_battle(demo_battle_player)}")
    print(f" - Has Active Encounter? : {demo_battle_enc_mgr.has_active_encounter(demo_battle_player)}")
    print(f" - Active Spawn Count    : {demo_battle_spawn_mgr.get_active_count('demo_battle_forest')} (Cleanly despawned)")

    # Step 8: Trainer Battle Demonstration with Opponent AI and Team Switching
    print("\nStep 8: Trainer Battle Demonstration with Opponent AI & Team Switching:")
    trainer_gary = Player(name="Gary Oak")
    gary_charm = Pokemon(species=CHARMANDER, personality=Personality(50, 50, 50, 50, 50, 50), level=5, attacks=[EMBER])
    gary_squirtle = Pokemon(species=SQUIRTLE, personality=Personality(50, 50, 50, 50, 50, 50), level=5, attacks=[WATER_GUN])
    trainer_gary.add_pokemon(gary_charm)
    trainer_gary.add_pokemon(gary_squirtle)
    trainer_gary.add_to_team(gary_charm)
    trainer_gary.add_to_team(gary_squirtle)
    trainer_gary.set_active_pokemon(gary_charm)

    trainer_battle = demo_battle_mgr.start_trainer_battle(demo_battle_player, trainer_gary, seed=77)
    print(f" - Trainer Match Started : {demo_battle_player.name} vs {trainer_gary.name}")
    print(f" - Opponent Active Mon   : {trainer_gary.active_pokemon.display_name}")
    # Knock out Gary's Charmander
    gary_charm.current_hp = 1
    demo_battle_mgr.attack(demo_battle_player, WATER_GUN)
    print(f" - Gary's Charmander     : Fainted={gary_charm.is_fainted}")
    print(f" - Gary Sent Out Next Mon: {trainer_battle.pokemon2.display_name} (Auto-switched)")
    print(f" - Battle Still Active?  : {trainer_battle.state == BattleState.IN_PROGRESS}")
    # Knock out Gary's Squirtle for complete victory
    gary_squirtle.current_hp = 1
    t_win_res = demo_battle_mgr.attack(demo_battle_player, WATER_GUN)
    print(f" - All Gary Mons Defeated: {gary_squirtle.is_fainted}")
    print(f" - Trainer Match Winner  : {t_win_res.battle_state} (Player Victorious!)")

    # Step 9: In-Battle Capture Demonstration
    print("\nStep 9: In-Battle Wild Capture Demonstration:")
    wild_pika_target = Pokemon(species=PIKACHU, personality=Personality(50, 50, 50, 50, 50, 50), level=3, attacks=[QUICK_ATTACK])
    demo_battle_spawn_mgr.add_active_pokemon("demo_battle_forest", wild_pika_target, (1.0, 1.0))
    cap_enc = demo_battle_enc_mgr.start_encounter(demo_battle_player, wild_pika_target, demo_battle_area)
    demo_battle_mgr.start_wild_battle(demo_battle_player, cap_enc)

    sure_capture_mgr = CaptureManager(min_probability=1.0)
    cap_action_res = demo_battle_mgr.attempt_capture(demo_battle_player, capture_manager=sure_capture_mgr)
    print(f" - Capture Success       : {cap_action_res.captured}")
    print(f" - Terminal State        : {cap_action_res.battle_state}")
    print(f" - Added to Collection?  : {demo_battle_player.is_pokemon_owned(wild_pika_target)}")
    print(f" - Spawn Area Cleared?   : {demo_battle_spawn_mgr.get_active_count('demo_battle_forest') == 0}")
    print("=" * 60)

    print("\n>> All demonstrations complete. All systems functioning as expected.")



if __name__ == "__main__":
    main()



