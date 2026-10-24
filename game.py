"""
Playable Adventure Loop & End-to-End Game Integration for Syntax Error 2026.

Provides a text-based, menu-driven adventure experience connecting:
- Player creation, starter selection, and team management
- World exploration, travel, and region/landmark discovery
- World object interactions (resource gathering, signs, treasure caches, landmarks)
- Time-of-day progression and habitat-based wild Pokemon encounters
- Turn-based battle engine (attacks, team switching, Poke Ball capture, fleeing, rewards)
- Inventory inspection and item consumption
- Quest log, acceptance, objective progression, and reward claiming
- Single-slot persistent save/resume using SaveManager (Schema v4)

Decoupled I/O via injectable input_fn and output_fn for 100% automated testability.
"""
import math
import os
import random
import sys
from pathlib import Path
from typing import Callable, Optional, Sequence, Union, Any
from dotenv import load_dotenv
load_dotenv()
load_dotenv(Path(__file__).resolve().parent / ".env")

from src.models.pokemon_type import PokemonType
from src.models.species import PokemonSpecies
from src.models.pokemon import Pokemon
from src.models.personality import Personality
from src.models.player import Player
from src.models.inventory import Inventory
from src.models.item import Item, ItemType
from src.models.item_manager import ItemManager
from src.models.quest import QuestStatus, QuestDefinition, ObjectiveType
from src.models.quest_manager import QuestManager, QuestNotification
from src.models.quest_journal import QuestJournal,QuestEntryView,ObjectiveEntryView,make_progress_bar
from src.models.world_exploration import WorldRegion, ExplorationResult
from src.models.world_exploration_manager import WorldExplorationManager
from src.models.world_interaction import Interactable, InteractableType, InteractionResult
from src.models.world_interaction_manager import WorldInteractionManager
from src.models.spawn_area import SpawnArea
from src.models.spawn_manager import SpawnManager
from src.models.encounter_manager import EncounterManager
from src.models.experience_manager import ExperienceManager
from src.models.bond_manager import BondManager
from src.models.capture_manager import CaptureManager
from src.models.habitat import Habitat, TimeOfDay, get_time_of_day
from src.models.habitat_manager import HabitatManager
from src.models.battle import Battle,BattleAction,BattleActionType,BattleActionResult
from src.models.battle_state import BattleState
from src.models.battle_manager import BattleManager
from src.models.save_manager import save_game, load_game, SaveDataError
from src.models.trainer import Trainer, DifficultyProfile, TrainerArchetype
from src.models.trainer_manager import (
    TrainerManager,
    create_default_trainer_manager,
    create_default_trainers,
    get_trainer_state_path_for_save_file,
)
from src.ai.persistence import AiState, save_ai_state, load_ai_state, get_ai_state_path_for_save_file
from src.ai.live_provider import create_live_decision_provider

from src.data.species import (
    PIKACHU,
    CHARMANDER,
    SQUIRTLE,
    BULBASAUR,
    PIDGEY,
    RATTATA,
    CATERPIE,
    BUTTERFREE,
    GEODUDE,
    ZUBAT,
    MACHOP,
    GASTLY,
    GROWLITHE,
    POLIWAG,
    EEVEE,
    ABRA,
)
from src.data.attacks import (
    THUNDER_SHOCK,
    QUICK_ATTACK,
    SCRATCH,
    EMBER,
    TACKLE,
    WATER_GUN,
    VINE_WHIP,
)
from src.data.items import POTION, SUPER_POTION, ANTIDOTE, POKE_BALL, ITEM_CATALOG
from src.data.quests import QUEST_CATALOG
from src.data.world_regions import create_default_world_regions
from src.data.world_objects import create_default_world_objects
from src.data.habitats import create_default_habitats
from src.models.npc import NPC
from src.data.npcs import get_npc, NPC_CATALOG


# Named geographic waypoints in the game world
WORLD_DESTINATIONS = (
    ("starting_meadow", "Starting Meadow (Meadow Clearing)", (5.0, 5.0)),
    ("starting_meadow", "Starting Meadow (Route 1 Signpost)", (2.0, 1.0)),
    ("forest_trail", "Forest Trail (Supply Cache Path)", (15.0, 10.0)),
    ("ancient_shrine_grounds", "Ancient Shrine Grounds (Thunder Stone Shrine)", (25.0, 25.0)),
    ("mountain_pass", "Mountain Pass (Rocky Summit)", (35.0, 5.0)),
    ("lakeside", "Crystal Lakeside (Lake Shore)", (5.0, 15.0)),
    ("haunted_ruins", "Haunted Ruins (Crumbling Gate)", (15.0, 20.0)),
    ("tall_grass_plains", "Tall Grass Plains (Open Fields)", (25.0, 14.0)),
)


class AdventureGame:
    """
    Main interactive game coordinator for Syntax Error 2026.
    Connects all gameplay subsystems into a playable menu-driven text loop.
    """

    def __init__(
        self,
        input_fn: Optional[Callable[[str], str]] = None,
        output_fn: Optional[Callable[..., None]] = None,
        save_file: str = "save_game.json",
        seed: Optional[int] = None,
        voice_service: Optional[Any] = None,
    ) -> None:
        """
        Initializes an independent adventure game session.

        Args:
            input_fn: Injectable prompt function (defaults to built-in input).
            output_fn: Injectable output function (defaults to built-in print).
            save_file: Single-slot save file path (defaults to save_game.json).
            seed: Optional integer seed for deterministic RNG in tests.
        """
        self._input_fn: Callable[[str], str] = input_fn if input_fn is not None else input
        self._output_fn: Callable[..., None] = output_fn if output_fn is not None else print
        self.save_file: str = save_file
        self.seed: Optional[int] = seed
        self._initial_voice_service = voice_service

        # Deterministic random generator for this session
        self.rng: random.Random = random.Random(seed) if seed is not None else random.Random()

        # Initialize all subsystem managers
        self._reset_subsystems()

        # Player state
        self.player: Optional[Player] = None
        self.player_pos: list[float] = [5.0, 5.0]
        self.current_region_id: str = "starting_meadow"
        self.is_running: bool = True

    def _reset_subsystems(self) -> None:
        """
        Resets and re-instantiates subsystem managers to guarantee clean session isolation.
        Prevents depleted resource nodes, stale active encounters, or completed quests
        from leaking across consecutive game sessions.
        """
        self.game_hour = 12.0  # Midday (12:00 / DAY)
        self.elapsed_seconds = 0.0

        # Subsystem managers (fresh independent instances per game session)
        self.quest_manager = QuestManager()
        self.quest_journal = QuestJournal(quest_manager=self.quest_manager)
        self.item_manager = ItemManager()

        self.world_interaction_manager = WorldInteractionManager(
            objects=create_default_world_objects(),
            quest_manager=self.quest_manager,
            clock=lambda: self.elapsed_seconds,
        )

        self.world_exploration_manager = WorldExplorationManager(
            regions=create_default_world_regions(),
            interaction_manager=self.world_interaction_manager,
            quest_manager=self.quest_manager,
            clock=lambda: self.elapsed_seconds,
        )
        self.world_interaction_manager.exploration_manager = self.world_exploration_manager

        # Spawning and encounter managers
        self.spawn_manager = SpawnManager()
        self._init_spawn_areas()

        self.encounter_manager = EncounterManager(spawn_manager=self.spawn_manager)
        self.experience_manager = ExperienceManager()
        self.bond_manager = BondManager()
        prev_min_prob = getattr(self.capture_manager, "_min_probability", None) if hasattr(self, "capture_manager") else None
        prev_max_prob = getattr(self.capture_manager, "_max_probability", None) if hasattr(self, "capture_manager") else None
        self.capture_manager = CaptureManager(rng=self.rng)
        if prev_min_prob is not None:
            self.capture_manager._min_probability = prev_min_prob
        if prev_max_prob is not None:
            self.capture_manager._max_probability = prev_max_prob

        self.habitat_manager = HabitatManager(
            habitats=create_default_habitats(),
            exploration_manager=self.world_exploration_manager,
            spawn_manager=self.spawn_manager,
            encounter_manager=self.encounter_manager,
            quest_manager=self.quest_manager,
            rng=self.rng,
        )

        self.battle_manager = BattleManager(
            spawn_manager=self.spawn_manager,
            encounter_manager=self.encounter_manager,
            capture_manager=self.capture_manager,
            experience_manager=self.experience_manager,
            quest_manager=self.quest_manager,
            bond_manager=self.bond_manager,
            rng=self.rng,
        )

        self.item_manager.quest_manager = self.quest_manager
        self.encounter_manager.quest_manager = self.quest_manager
        self.capture_manager.quest_manager = self.quest_manager

        # Autonomous AI state container
        self.ai_state = AiState()
        self.battle_manager.ai_state = self.ai_state
        self.battle_manager.ai_provider = create_live_decision_provider(provider_type="auto")

        # In-world trainer manager
        self.trainer_manager = create_default_trainer_manager()


        # Voice Input via AssemblyAI (BT3.1) - commented out
        # from src.ai.voice_input import VoiceInputService
        # self.voice_service: VoiceInputService = (
        #     self._initial_voice_service if getattr(self, "_initial_voice_service", None) is not None else VoiceInputService()
        # )
        self.voice_service = None

    def _init_spawn_areas(self) -> None:
        """Configures default spawn areas for regions."""
        meadow_area = SpawnArea(
            area_id="meadow_spawns",
            name="Starting Meadow Spawns",
            allowed_species=(PIKACHU, SQUIRTLE, BULBASAUR, PIDGEY, RATTATA, CATERPIE, EEVEE, POLIWAG),
            max_active_pokemon=3,
            region_id="starting_meadow",
        )
        forest_area = SpawnArea(
            area_id="forest_spawns",
            name="Forest Trail Spawns",
            allowed_species=(PIKACHU, CHARMANDER, PIDGEY, CATERPIE, BUTTERFREE, ZUBAT, MACHOP, ABRA),
            max_active_pokemon=3,
            region_id="forest_trail",
        )
        shrine_area = SpawnArea(
            area_id="shrine_spawns",
            name="Ancient Shrine Spawns",
            allowed_species=(PIKACHU, CHARMANDER, GEODUDE, GASTLY, ZUBAT, GROWLITHE, MACHOP, ABRA),
            max_active_pokemon=3,
            region_id="ancient_shrine_grounds",
        )
        mountain_area = SpawnArea(
            area_id="mountain_spawns",
            name="Mountain Pass Spawns",
            allowed_species=(GEODUDE, MACHOP, ZUBAT, GROWLITHE, RATTATA),
            max_active_pokemon=3,
            region_id="mountain_pass",
        )
        lakeside_area = SpawnArea(
            area_id="lakeside_spawns",
            name="Crystal Lakeside Spawns",
            allowed_species=(POLIWAG, SQUIRTLE, PIDGEY, EEVEE, CATERPIE),
            max_active_pokemon=3,
            region_id="lakeside",
        )
        ruins_area = SpawnArea(
            area_id="ruins_spawns",
            name="Haunted Ruins Spawns",
            allowed_species=(GASTLY, ZUBAT, ABRA, RATTATA),
            max_active_pokemon=3,
            region_id="haunted_ruins",
        )
        plains_area = SpawnArea(
            area_id="plains_spawns",
            name="Tall Grass Plains Spawns",
            allowed_species=(RATTATA, PIDGEY, EEVEE, GROWLITHE, BULBASAUR, PIKACHU),
            max_active_pokemon=3,
            region_id="tall_grass_plains",
        )
        self.spawn_manager.register_area(meadow_area)
        self.spawn_manager.register_area(forest_area)
        self.spawn_manager.register_area(shrine_area)
        self.spawn_manager.register_area(mountain_area)
        self.spawn_manager.register_area(lakeside_area)
        self.spawn_manager.register_area(ruins_area)
        self.spawn_manager.register_area(plains_area)

    # --- I/O Abstraction Helpers ---

    def _prompt(self, message: str = "") -> str:
        """Reads user input safely, handling EOF and interruptions."""
        try:
            raw = self._input_fn(message)
            if raw is None:
                return "quit"
            return str(raw).strip()
        except (EOFError, StopIteration, KeyboardInterrupt):
            return "quit"

    def _print(self, *args: Any, **kwargs: Any) -> None:
        """Emits text output through the injected output function."""
        self._output_fn(*args, **kwargs)

    # --- Time Progression ---

    def advance_time(self, hours: float = 0.0, seconds: float = 0.0) -> None:
        """
        Advances the in-memory clock by a given number of hours and seconds.
        Updates elapsed seconds and triggers resource node respawn evaluation.
        """
        total_secs = hours * 3600.0 + seconds
        if total_secs <= 0:
            return
        self.game_hour = (self.game_hour + (total_secs / 3600.0)) % 24.0
        self.elapsed_seconds += total_secs
        self.world_interaction_manager.check_respawns(self.elapsed_seconds)

    @property
    def time_of_day(self) -> TimeOfDay:
        """Current biological time-of-day period."""
        return get_time_of_day(self.game_hour)

    def get_time_display(self) -> str:
        """Formats the in-game clock into a human-readable string."""
        total_minutes = int(self.game_hour * 60)
        h = (total_minutes // 60) % 24
        m = total_minutes % 60
        period = self.time_of_day.value.upper()
        return f"{h:02d}:{m:02d} ({period})"

    # --- Top-Level Lifecycle ---

    def run(self) -> None:
        """Runs the top-level title menu loop until the user quits."""
        self.is_running = True
        while self.is_running:
            self._print("\n" + "=" * 50)
            self._print("               SYNTAX ERROR 2026")
            self._print("       A Pokemon-Inspired Adventure Game")
            self._print("=" * 50)
            self._print("[1] New Game")
            self._print("[2] Load Game")
            self._print("[3] Quit")

            choice = self._prompt("\nEnter choice (1-3): ")
            if choice == "1":
                if self._start_new_game():
                    self._adventure_loop()
            elif choice == "2":
                if self._load_game_flow():
                    self._adventure_loop()
            elif choice in ("3", "quit", "q", "exit"):
                self._print("\nThank you for playing Syntax Error 2026! Goodbye.")
                self.is_running = False
                break
            else:
                self._print(f"\nInvalid choice '{choice}'. Please select 1, 2, or 3.")

    # --- New Game & Resume Flows ---

    def _start_new_game(self) -> bool:
        """Executes player creation, starter selection, and inventory setup."""
        self._reset_subsystems()
        self._print("\n" + "-" * 40)
        self._print("STARTING A NEW ADVENTURE")
        self._print("-" * 40)

        name = self._prompt("Enter your Trainer name (default 'Ash'): ")
        if name in ("quit", "exit"):
            return False
        if not name:
            name = "Ash"

        self._print(f"\nWelcome, Trainer {name}!")
        self._print("Choose your starter Pokemon:")
        self._print(" [1] Bulbasaur  (Grass/Poison) - Calm Nature, Tackle & Vine Whip")
        self._print(" [2] Charmander (Fire)         - Fiery Spirit, Scratch & Ember")
        self._print(" [3] Squirtle   (Water)        - Sturdy Shell, Tackle & Water Gun")

        starter_choice = ""
        while starter_choice not in ("1", "2", "3", "quit"):
            raw_choice = self._prompt("Choose your starter (1-3): ").strip().lower()
            if raw_choice in ("1", "bulbasaur"):
                starter_choice = "1"
            elif raw_choice in ("2", "charmander"):
                starter_choice = "2"
            elif raw_choice in ("3", "squirtle"):
                starter_choice = "3"
            elif raw_choice in ("quit", "exit"):
                starter_choice = "quit"
            else:
                self._print("Please enter 1, 2, or 3.")

        if starter_choice == "quit":
            return False

        neutral_personality = Personality(50, 50, 50, 50, 50, 50)
        if starter_choice == "1":
            starter_mon = Pokemon(
                species=BULBASAUR,
                personality=neutral_personality,
                level=5,
                attacks=[TACKLE, VINE_WHIP],
            )
        elif starter_choice == "2":
            starter_mon = Pokemon(
                species=CHARMANDER,
                personality=neutral_personality,
                level=5,
                attacks=[SCRATCH, EMBER],
            )
        else:
            starter_mon = Pokemon(
                species=SQUIRTLE,
                personality=neutral_personality,
                level=5,
                attacks=[TACKLE, WATER_GUN],
            )

        # Initialize Player
        self.player = Player(name=name)
        self.player.add_pokemon(starter_mon)
        self.player.add_to_team(starter_mon)
        self.player.set_active_pokemon(starter_mon)

        # Starting inventory: 5x Poke Balls, 3x Potions
        self.player.inventory.add_item("poke_ball", 5)
        self.player.inventory.add_item("potion", 3)

        # Set starting location in Starting Meadow
        self.player_pos = [5.0, 5.0]
        self.current_region_id = "starting_meadow"
        self.game_hour = 12.0
        self.elapsed_seconds = 0.0

        # Mark starting meadow discovered
        self.world_exploration_manager.discover_region(
            player=self.player,
            region_id="starting_meadow",
            current_time=self.elapsed_seconds,
        )

        self._print(f"\nYou received {starter_mon.display_name} (Lv.5)!")
        self._print("Your backpack has been stocked with 5x Poke Balls and 3x Potions.")
        self._print("Your adventure begins in the sunlit Starting Meadow.")

        # Initialize and synchronize autonomous AI agent for starter
        if hasattr(self, "ai_state") and self.ai_state is not None:
            self.ai_state.sync_with_player_collection(self.player)

        return True

    def _load_game_flow(self) -> bool:
        """Loads persistent player state from disk safely."""
        path = Path(self.save_file)
        if not path.exists():
            self._print(f"\nNo save file found at '{self.save_file}'. Please start a New Game.")
            return False

        try:
            loaded_player = load_game(self.save_file)
            self._reset_subsystems()
            self.player = loaded_player

            # Load and restore companion AI state
            ai_path = get_ai_state_path_for_save_file(self.save_file)
            self.ai_state = load_ai_state(ai_path, create_if_missing=True)
            self.ai_state.sync_with_player_collection(self.player)
            self.battle_manager.ai_state = self.ai_state

            # Load and restore companion trainer manager
            trainer_path = get_trainer_state_path_for_save_file(self.save_file)
            if trainer_path.exists():
                self.trainer_manager = TrainerManager.load_from_file(trainer_path, rng=self.rng)
            else:
                self.trainer_manager = create_default_trainer_manager()


            # Sync spatial state
            self.player_pos = [5.0, 5.0]
            self.current_region_id = "starting_meadow"
            if loaded_player.is_region_discovered("haunted_ruins"):
                self.player_pos = [15.0, 20.0]
                self.current_region_id = "haunted_ruins"
            elif loaded_player.is_region_discovered("mountain_pass"):
                self.player_pos = [35.0, 5.0]
                self.current_region_id = "mountain_pass"
            elif loaded_player.is_region_discovered("tall_grass_plains"):
                self.player_pos = [25.0, 14.0]
                self.current_region_id = "tall_grass_plains"
            elif loaded_player.is_region_discovered("lakeside"):
                self.player_pos = [5.0, 15.0]
                self.current_region_id = "lakeside"
            elif loaded_player.is_region_discovered("ancient_shrine_grounds"):
                self.player_pos = [25.0, 25.0]
                self.current_region_id = "ancient_shrine_grounds"
            elif loaded_player.is_region_discovered("forest_trail"):
                self.player_pos = [15.0, 10.0]
                self.current_region_id = "forest_trail"

            # Mark previously completed quests as announced to avoid duplicate notifications upon load
            for q_id, q_prog in loaded_player.quests.items():
                if q_prog.is_completed:
                    self.quest_manager.mark_completion_announced(q_id)

            self._print(f"\nWelcome back, Trainer {loaded_player.name}!")
            self._print(f"Loaded game successfully from '{self.save_file}'.")
            if loaded_player.active_pokemon:
                self._print(
                    f"Active Partner: {loaded_player.active_pokemon.display_name} "
                    f"(Lv.{loaded_player.active_pokemon.level}, "
                    f"HP: {loaded_player.active_pokemon.current_hp}/{loaded_player.active_pokemon.max_hp})"
                )
            return True
        except SaveDataError as sde:
            self._print(f"\nFailed to load save file '{self.save_file}': {sde}")
            return False
        except Exception as e:
            self._print(f"\nUnexpected error loading save file: {e}")
            return False

    def load_game(self) -> bool:
        """Public method to load save game state."""
        return self._load_game_flow()

    def _display_quest_notifications(self) -> list[QuestNotification]:
        """
        Checks and displays any pending quest completion notifications from QuestManager.
        Returns the list of notifications displayed.
        """
        if not self.quest_manager or not self.quest_manager.has_pending_notifications():
            return []

        notifications = self.quest_manager.pop_pending_notifications()
        for note in notifications:
            for line in note.format_banner():
                self._print(line)
        return notifications

    # --- Main Adventure Loop ---

    def _adventure_loop(self) -> None:
        """Main exploration and interaction menu loop."""
        while self.player is not None:
            self._display_quest_notifications()
            region = self.world_exploration_manager.get_region(self.current_region_id)
            region_name = region.name if region else self.current_region_id
            active_name = (
                f"{self.player.active_pokemon.display_name} (Lv.{self.player.active_pokemon.level} "
                f"HP:{self.player.active_pokemon.current_hp}/{self.player.active_pokemon.max_hp})"
                if self.player.active_pokemon
                else "None"
            )

            self._print("\n" + "=" * 55)
            self._print(f" Trainer: {self.player.name} | Location: {region_name} ({self.player_pos[0]:.1f}, {self.player_pos[1]:.1f})")
            self._print(f" Time   : {self.get_time_display()} | Partner: {active_name}")
            self._print("=" * 55)
            self._print(" [1] Explore Current Area")
            self._print(" [2] Travel to Location")
            self._print(" [3] Interact with World Objects")
            self._print(" [4] Pokemon PC & Team Management")
            self._print(" [5] View Inventory & Use Items")
            self._print(" [6] Quest Journal & Quest Log (or 'j' for Journal)")
            self._print(" [7] View Map & Discovered Locations")
            self._print(" [8] Rest & Wait")
            self._print(" [9] Save Game")
            self._print(" [p] Partner Pokémon: Talk & Interact")
            self._print(" [t] Challenge Area Trainers")
            self._print(" [10] Return to Title Menu")

            choice = self._prompt("\nWhat would you like to do? (1-10, p, t): ")

            if choice == "1":
                self._action_explore()
            elif choice == "2":
                self._action_travel()
            elif choice == "3":
                self._action_interact()
            elif choice in ("4", "pc", "collection", "team"):
                self._action_manage_team()
            elif choice == "5":
                self._action_inventory()
            elif choice in ("6", "quests", "quest", "log"):
                self._action_quests()
            elif choice in ("j", "journal"):
                self._action_quest_journal()
            elif choice == "7":
                self._action_view_map()
            elif choice == "8":
                self._action_rest()
            elif choice == "9":
                self._action_save()
            elif choice in ("p", "partner", "companion"):
                self._action_partner_interaction()
            elif choice in ("t", "trainer", "trainers", "battle", "challenge"):
                self._action_challenge_trainer()
            elif choice in ("10", "quit", "q", "exit"):
                confirm = self._prompt("Return to title menu? (y/n, default y): ")
                if confirm.lower() in ("", "y", "yes", "quit"):
                    self._print("\nReturning to title menu...")
                    break
            else:
                self._print(f"\nInvalid choice '{choice}'. Please select an option from 1 to 10.")

    # --- Adventure Actions ---

    def _action_explore(self) -> None:
        """Explores current surroundings, triggering discovery and wild encounters."""
        if self.player is None:
            return

        if not self.player.team or not any(not p.is_fainted for p in self.player.team):
            self._print("\nAll Pokemon on your team have fainted! You cannot safely explore tall grass.")
            self._print("Heal your team with items or rest before exploring.")
            return

        self.advance_time(0.5)
        self._print(f"\nYou wander through {self.current_region_id.replace('_', ' ').title()}...")

        # Evaluate region discovery at current position
        disc_res = self.world_exploration_manager.discover_region_at_position(
            player=self.player,
            position=self.player_pos,
            current_time=self.elapsed_seconds,
        )
        if disc_res.is_first_discovery:
            self._print(f"[*] {disc_res.message}")
            if disc_res.discovery_text:
                self._print(f"  \"{disc_res.discovery_text}\"")

        # Evaluate wild encounter
        enc_res = self.habitat_manager.trigger_encounter(
            player=self.player,
            region_id=self.current_region_id,
            time_of_day=self.time_of_day,
            current_time=self.elapsed_seconds,
        )

        if enc_res.success and enc_res.pokemon is not None and enc_res.encounter is not None:
            wild = enc_res.pokemon
            self._print(f"\n[!] A wild {wild.display_name} (Lv.{wild.level}) jumped out of the grass!")
            battle = self.battle_manager.start_wild_battle(self.player, enc_res.encounter)
            self._battle_loop(battle)
        else:
            if enc_res.error_type == "NO_ELIGIBLE_SPECIES":
                self._print(f"The area is peaceful right now during {self.time_of_day.value.upper()}. No wild Pokemon appeared.")
            elif enc_res.error_type == "SPAWN_AREA_ON_COOLDOWN":
                self._print("The area recently had wild activity; all is currently calm.")
            else:
                self._print(f"You searched the area, but found no wild Pokemon nearby. ({enc_res.message})")

        self._display_quest_notifications()

    def _action_travel(self) -> None:
        """Allows player to travel between defined regions and key landmarks."""
        if self.player is None:
            return

        self._print("\n" + "-" * 40)
        self._print("TRAVEL DESTINATIONS")
        self._print("-" * 40)
        for idx, (reg_id, name, coords) in enumerate(WORLD_DESTINATIONS, 1):
            is_current = (
                math.isclose(self.player_pos[0], coords[0], abs_tol=0.1)
                and math.isclose(self.player_pos[1], coords[1], abs_tol=0.1)
            )
            marker = " [HERE]" if is_current else ""
            self._print(f" [{idx}] {name} - Coords ({coords[0]:.1f}, {coords[1]:.1f}){marker}")
        self._print(" [0] Cancel")

        choice = self._prompt(f"Select destination (0-{len(WORLD_DESTINATIONS)}): ")
        if choice in ("0", "cancel", "quit", "back"):
            return

        try:
            val = int(choice)
            if not (1 <= val <= len(WORLD_DESTINATIONS)):
                self._print(f"Invalid destination '{choice}'.")
                return
        except ValueError:
            self._print(f"Invalid input '{choice}'.")
            return

        target_reg_id, target_name, target_coords = WORLD_DESTINATIONS[val - 1]
        self.player_pos = [target_coords[0], target_coords[1]]
        self.current_region_id = target_reg_id
        self.advance_time(1.0)

        self._print(f"\nYou traveled to {target_name}.")
        # Trigger discovery
        disc_res = self.world_exploration_manager.discover_region_at_position(
            player=self.player,
            position=self.player_pos,
            current_time=self.elapsed_seconds,
        )
        if disc_res.is_first_discovery:
            self._print(f"[*] {disc_res.message}")
            if disc_res.discovery_text:
                self._print(f"  \"{disc_res.discovery_text}\"")

        if hasattr(self, "ai_state") and self.ai_state is not None:
            from src.ai.scheduler import AutonomousWorldScheduler
            scheduler_events = AutonomousWorldScheduler.on_region_entered(
                player=self.player,
                region_id=self.current_region_id,
                ai_state=self.ai_state,
            )
            for evt in scheduler_events:
                self._print(f"  > {evt}")

        self._display_quest_notifications()

    def _action_interact(self) -> None:
        """Displays interactable objects in range and processes interaction."""
        if self.player is None:
            return

        all_objects = self.world_interaction_manager.list_objects()
        if not all_objects:
            self._print("\nNo interactable objects registered in the world.")
            return

        # Filter strictly to objects currently within interaction range at player position
        in_range_objects = [
            obj for obj in all_objects
            if obj.distance_to(self.player_pos) <= obj.interaction_radius
        ]

        if not in_range_objects:
            self._print("\nNo interactable world objects within range at your current position.")
            return

        self._print("\n" + "-" * 40)
        self._print("WORLD OBJECTS (IN RANGE)")
        self._print("-" * 40)

        for idx, obj in enumerate(in_range_objects, 1):
            status_tag = ""
            if obj.interactable_type == InteractableType.TREASURE and self.player.is_treasure_collected(obj.object_id):
                status_tag = " [ALREADY LOOTED]"
            elif obj.interactable_type == InteractableType.RESOURCE_NODE and not obj.is_available:
                status_tag = " [DEPLETED]"

            self._print(
                f" [{idx}] {obj.name} ({obj.interactable_type.value.title()}) "
                f"- Coords ({obj.position[0]:.1f}, {obj.position[1]:.1f}) "
                f"[IN RANGE]{status_tag}"
            )
        self._print(" [0] Cancel")

        choice = self._prompt(f"Select object to interact with (0-{len(in_range_objects)}): ")
        if choice in ("0", "cancel", "quit", "back"):
            return

        try:
            val = int(choice)
            if 1 <= val <= len(in_range_objects):
                chosen_obj = in_range_objects[val - 1]
            elif 1 <= val <= len(all_objects) and all_objects[val - 1] in in_range_objects:
                # Backwards compatibility fallback if a test script passed the global index of an in-range object
                chosen_obj = all_objects[val - 1]
            else:
                self._print(f"Invalid selection '{choice}'.")
                return
        except ValueError:
            self._print(f"Invalid input '{choice}'.")
            return

        self.advance_time(seconds=5.0)

        # Execute interaction
        result = self.world_interaction_manager.interact(
            player=self.player,
            object_id=chosen_obj.object_id,
            player_position=self.player_pos,
            current_time=self.elapsed_seconds,
        )

        if result.success:
            self._print(f"\n[+] {result.message}")
            if result.items_granted:
                rewards_str = ", ".join(f"{cnt}x {item_id}" for item_id, cnt in result.items_granted.items())
                self._print(f"  Acquired: {rewards_str}")

            # If landmark, also register landmark discovery
            if chosen_obj.interactable_type == InteractableType.LANDMARK:
                lm_res = self.world_exploration_manager.discover_landmark(
                    player=self.player,
                    landmark_id=chosen_obj.object_id,
                    player_position=self.player_pos,
                    current_time=self.elapsed_seconds,
                )
                if lm_res.is_first_discovery:
                    self._print(f"[*] {lm_res.message}")
                    if hasattr(self, "ai_state") and self.ai_state is not None:
                        from src.ai.scheduler import AutonomousWorldScheduler
                        lm_events = AutonomousWorldScheduler.on_landmark_discovered(
                            player=self.player,
                            landmark_id=chosen_obj.object_id,
                            ai_state=self.ai_state,
                        )
                        for evt in lm_events:
                            self._print(f"  > {evt}")

            # If NPC, trigger dialogue and quest discovery conversation
            elif chosen_obj.interactable_type == InteractableType.NPC:
                self._npc_dialogue_flow(chosen_obj, result)

            elif chosen_obj.interactable_type == InteractableType.POKEMON_CENTER:
                if self.player.team:
                    self._print("\nNurse Joy: 'Your Pokémon are fully healed and in peak fighting shape!'")
                    self._print("Team Status:")
                    for mon in self.player.team:
                        self._print(
                            f"  - {mon.display_name} (Lv.{mon.level}): "
                            f"{mon.current_hp}/{mon.max_hp} HP | "
                            f"Atk: {mon.effective_attack} | Def: {mon.effective_defense}"
                        )
        else:
            self._print(f"\n[-] Could not interact with {chosen_obj.name}: {result.message}")

        self._display_quest_notifications()

    def _handle_quest_choices(
        self,
        target_qid: str,
        target_qdef: QuestDefinition,
        npc: Optional[NPC] = None,
    ) -> bool:
        """
        Presents any available branching choices for target_qid to the player and handles selection.
        Returns True if at least one choice was processed, False otherwise.
        """
        if self.player is None:
            return False

        avail_choices = self.quest_manager.get_available_choices(self.player, target_qid)
        if not avail_choices:
            return False

        for ch in avail_choices:
            if not self.quest_manager.is_choice_available(self.player, target_qid, ch.choice_id):
                continue

            self._print("\n" + "=" * 45)
            self._print(f" [!] DECISION REQUIRED: {ch.prompt}")
            self._print("=" * 45)
            for opt_idx, opt in enumerate(ch.options, 1):
                opt_desc = f" - {opt.description}" if opt.description else ""
                self._print(f"  [{opt_idx}] {opt.text}{opt_desc}")
            self._print("  [0] Decide Later")

            ch_sel = self._prompt(f"Select your path (0-{len(ch.options)}): ")
            if ch_sel in ("0", "cancel", "back", "later", "no"):
                self._print("You decided to consider your options before choosing.")
            else:
                try:
                    opt_num = int(ch_sel)
                    if 1 <= opt_num <= len(ch.options):
                        chosen_opt = ch.options[opt_num - 1]
                        ch_res = self.quest_manager.make_choice(
                            self.player, target_qid, ch.choice_id, chosen_opt.option_id
                        )
                        if ch_res.success:
                            self._print(f"\n[+] Selected path: '{chosen_opt.text}'!")
                            if npc is not None:
                                ch_dialogue = npc.get_quest_dialogue(
                                    target_qid, f"{chosen_opt.option_id}_chosen", ""
                                )
                                if ch_dialogue:
                                    self._print(f'"{ch_dialogue}"')
                            self._display_quest_notifications()
                        else:
                            self._print(f"\n[-] Could not select path: {ch_res.message}")
                    else:
                        self._print("Invalid selection.")
                except ValueError:
                    self._print("Please enter a valid number.")

        return True

    def _display_quest_current_objectives(
        self,
        target_qid: str,
        target_qdef: QuestDefinition,
    ) -> None:
        """Displays current objectives and chosen paths for an active quest."""
        if self.player is None:
            return

        prog = self.player.quests.get(target_qid)
        self._print("\n" + "-" * 40)
        self._print(f"CURRENT OBJECTIVES: {target_qdef.name}")
        self._print("-" * 40)
        if prog:
            if prog.selected_choices:
                for c_id, opt_id in prog.selected_choices.items():
                    ch_obj = target_qdef.get_choice(c_id)
                    if ch_obj:
                        opt_obj = ch_obj.get_option(opt_id)
                        if opt_obj:
                            self._print(f"  Chosen Path: {opt_obj.text}")
            for obj_id, obj_prog in prog.objective_progress.items():
                status_str = "COMPLETED" if obj_prog.is_completed else "IN PROGRESS"
                marker = "[X]" if obj_prog.is_completed else "[ ]"
                self._print(f"  {marker} {obj_id}: {obj_prog.current_count}/{obj_prog.target_count} ({status_str})")

    def _npc_dialogue_flow(self, obj: Interactable, result: InteractionResult) -> None:
        """
        Interactive conversation and quest discovery loop with an in-world NPC.
        """
        if self.player is None:
            return

        npc = get_npc(obj.npc_id) if obj.npc_id else None
        if npc is None:
            clean_id = obj.object_id.replace("npc_", "")
            npc = get_npc(clean_id)

        npc_name = npc.name if npc else obj.name
        npc_title = f" ({npc.title})" if npc and npc.title else ""

        self._print("\n" + "=" * 55)
        self._print(f" {npc_name}{npc_title}")
        self._print("=" * 55)

        greeting = (
            npc.get_dialogue("greeting", obj.interaction_text or "Hello, Trainer!")
            if npc
            else (obj.interaction_text or "Hello, Trainer!")
        )
        self._print(f'"{greeting}"')

        if not npc or not npc.offered_quest_ids:
            return

        while True:
            self._print(f"\nTOPICS & QUESTS FROM {npc.name.upper()}:")
            for idx, q_id in enumerate(npc.offered_quest_ids, 1):
                q_def = self.quest_manager.get_quest_definition(q_id)
                q_name = q_def.name if q_def else q_id.replace("_", " ").title()
                q_status = self.quest_manager.get_quest_status(self.player, q_id)
                if q_status == QuestStatus.AVAILABLE:
                    tag = " [AVAILABLE - New Quest!]"
                elif q_status == QuestStatus.ACTIVE:
                    tag = " [ACTIVE - In Progress]"
                elif q_status == QuestStatus.COMPLETED:
                    prog = self.player.quests.get(q_id)
                    if prog and not prog.rewards_claimed:
                        tag = " [COMPLETED - Rewards Ready!]"
                    else:
                        tag = " [COMPLETED]"
                else:  # LOCKED
                    tag = " [LOCKED]"
                self._print(f" [{idx}] {q_name}{tag}")
            self._print(" [0] Leave Conversation")

            choice = self._prompt(f"Select a topic (0-{len(npc.offered_quest_ids)}): ")
            if choice in ("0", "leave", "exit", "bye", "cancel", "back", "quit"):
                farewell = npc.get_dialogue("farewell", "Farewell, Trainer! Safe travels on your journey.")
                self._print(f'\n"{farewell}"')
                break

            try:
                val = int(choice)
                if not (1 <= val <= len(npc.offered_quest_ids)):
                    self._print("Invalid selection.")
                    continue
            except ValueError:
                self._print("Please enter a valid number.")
                continue

            target_qid = npc.offered_quest_ids[val - 1]
            target_qdef = self.quest_manager.get_quest_definition(target_qid)
            if not target_qdef:
                self._print(f"Quest '{target_qid}' not found in catalog.")
                continue

            q_status = self.quest_manager.get_quest_status(self.player, target_qid)
            prog = self.player.quests.get(target_qid)

            if q_status == QuestStatus.AVAILABLE:
                offer_text = npc.get_quest_dialogue(
                    target_qid, "offer", f"I have a task for you: '{target_qdef.name}'."
                )
                self._print(f'\n"{offer_text}"')
                self._print("\n" + "-" * 40)
                self._print(f"QUEST DETAILS: {target_qdef.name}")
                self._print("-" * 40)
                self._print(f"Description: {target_qdef.description}")
                self._print("Objectives:")
                for obj_item in target_qdef.objectives:
                    self._print(f" * {obj_item.description} (Target: {obj_item.target_count})")
                rew_str = (
                    ", ".join(
                        f"{cnt}x {it.replace('_', ' ').title()}"
                        for it, cnt in target_qdef.rewards.items()
                    )
                    if target_qdef.rewards
                    else "None"
                )
                self._print(f"Rewards: {rew_str}")

                self._print("\nOptions:")
                self._print(" [1] Accept Quest")
                self._print(" [2] Decline / Not Right Now")
                self._print(" [0] Back to Topics")

                sub_choice = self._prompt("Choose action (0-2): ")
                if sub_choice == "1":
                    accept_res = self.quest_manager.accept_quest(self.player, target_qid)
                    if accept_res.success:
                        self._print(f"\n[+] Accepted quest: '{target_qdef.name}'!")
                        self._display_quest_notifications()
                        if self.quest_manager.get_available_choices(self.player, target_qid):
                            self._handle_quest_choices(target_qid, target_qdef, npc)
                            self._display_quest_current_objectives(target_qid, target_qdef)
                    else:
                        self._print(f"\n[-] Could not accept quest: {accept_res.message}")
                elif sub_choice == "2":
                    decline_text = npc.get_quest_dialogue(
                        target_qid, "declined", "No problem at all! Come back when you're ready."
                    )
                    self._print(f'\n"{decline_text}"')
                else:
                    pass

            elif q_status == QuestStatus.LOCKED:
                locked_text = npc.get_quest_dialogue(
                    target_qid, "locked", "You are not quite ready to take on this quest yet."
                )
                self._print(f'\n"{locked_text}"')
                self._print("\n" + "-" * 40)
                self._print(f"QUEST LOCKED: {target_qdef.name}")
                self._print("-" * 40)
                self._print(f"Description: {target_qdef.description}")
                missing_prereqs = self.quest_manager.get_missing_prerequisites(self.player, target_qid)
                self._print("\nPrerequisites required:")
                if missing_prereqs:
                    for prereq in missing_prereqs:
                        self._print(f" [!] Must complete '{prereq.name}' first.")
                else:
                    for pid in target_qdef.prerequisites:
                        self._print(f" [!] Must complete '{pid.replace('_', ' ').title()}' first.")
                self._print("Return once you have met the prerequisites!")

            elif q_status == QuestStatus.ACTIVE:
                in_prog_text = npc.get_quest_dialogue(
                    target_qid, "in_progress", f"How is your progress on '{target_qdef.name}'?"
                )
                self._print(f'\n"{in_prog_text}"')

                # Check if there are pending branching choices to be made
                self._handle_quest_choices(target_qid, target_qdef, npc)
                self._display_quest_current_objectives(target_qid, target_qdef)

            elif q_status == QuestStatus.COMPLETED:
                completed_text = npc.get_quest_dialogue(
                    target_qid, "completed", f"Splendid job on completing '{target_qdef.name}'!"
                )
                self._print(f'\n"{completed_text}"')
                self._print("\n" + "-" * 40)
                self._print(f"QUEST COMPLETED: {target_qdef.name}")
                self._print("-" * 40)
                if prog and not prog.rewards_claimed:
                    eff_rewards = self.quest_manager.get_effective_rewards(self.player, target_qid)
                    rew_str = (
                        ", ".join(
                            f"{cnt}x {it.replace('_', ' ').title()}"
                            for it, cnt in eff_rewards.items()
                        )
                        if eff_rewards
                        else "None"
                    )
                    self._print(f"[*] Rewards waiting to be claimed: {rew_str}")
                    self._print("    (You can claim your rewards from the Quest Log [6] or Quest Journal [j]!)")
                else:
                    self._print("[X] All rewards have been claimed. Thank you for your assistance!")

    def _action_manage_team(self) -> None:
        """Displays team and PC collection, and allows managing Pokemon."""
        if self.player is None:
            return

        while True:
            self._print("\n" + "=" * 50)
            self._print(
                f"POKEMON PC & TEAM MANAGEMENT ({len(self.player.team)}/{self.player.max_team_size} Team | "
                f"{len(self.player.collection)} Total Owned)"
            )
            self._print("=" * 50)

            # View Current Team
            self._print("--- ACTIVE TEAM ---")
            if not self.player.team:
                self._print("  (Your active team is currently empty.)")
            else:
                for idx, mon in enumerate(self.player.team, 1):
                    active_tag = "[*] [ACTIVE]" if mon is self.player.active_pokemon else "  [BENCH] "
                    status_tag = " (FAINTED)" if mon.is_fainted else ""
                    attacks_str = ", ".join(a.name for a in mon.attacks) or "None"
                    self._print(
                        f" [{idx}] {active_tag} {mon.display_name} (Lv.{mon.level}) "
                        f"HP: {mon.current_hp}/{mon.max_hp} | Type: {mon.species.primary_type.value}{status_tag}\n"
                        f"      Moves: {attacks_str} | Bond: {mon.bond}/100"
                    )

            self._print("\n [1] Set Active Pokemon")
            self._print(" [2] View Entire Collection (PC Box)")
            self._print(" [3] Add Stored Pokemon to Team")
            self._print(" [4] Swap Team Member with Stored Pokemon")
            self._print(" [5] Deposit Pokemon to PC (Remove from Team)")
            self._print(" [0] Back to Main Menu")

            sub_choice = self._prompt("Choose action (0-5): ")
            if sub_choice.strip() in ("0", "cancel", "back", "quit"):
                break
            elif sub_choice.strip() == "1":
                if not self.player.team:
                    self._print("\n[-] No Pokemon on your team to make active.")
                    continue
                mon_idx_str = self._prompt(f"Select Pokemon number to make active (1-{len(self.player.team)}): ")
                try:
                    mon_idx = int(mon_idx_str.strip())
                    if 1 <= mon_idx <= len(self.player.team):
                        chosen_mon = self.player.team[mon_idx - 1]
                        if chosen_mon.is_fainted:
                            self._print(f"\n{chosen_mon.display_name} has fainted and cannot be set as your active partner!")
                        elif chosen_mon is self.player.active_pokemon:
                            self._print(f"\n{chosen_mon.display_name} is already your active Pokemon.")
                        else:
                            self.player.set_active_pokemon(chosen_mon)
                            self._print(f"\n{chosen_mon.display_name} is now your active Pokemon!")
                    else:
                        self._print("Invalid Pokemon number.")
                except ValueError:
                    self._print("Please enter a valid number.")
            elif sub_choice.strip() == "2":
                self._print("\n" + "-" * 55)
                self._print(f"POKEMON PC STORAGE & COLLECTION ({len(self.player.collection)} Total Owned)")
                self._print("-" * 55)
                if not self.player.collection:
                    self._print("  (Your Pokemon collection is empty.)")
                else:
                    for idx, mon in enumerate(self.player.collection, 1):
                        location_tag = "[TEAM]" if self.player.is_on_team(mon) else "[PC]  "
                        active_tag = " [*ACTIVE*]" if mon is self.player.active_pokemon else ""
                        status_tag = " (FAINTED)" if mon.is_fainted else ""
                        attacks_str = ", ".join(a.name for a in mon.attacks) or "None"
                        type_str = mon.species.primary_type.value
                        if mon.species.secondary_type:
                            type_str += f"/{mon.species.secondary_type.value}"
                        self._print(
                            f" [{idx}] {location_tag}{active_tag} {mon.display_name} (Lv.{mon.level}) "
                            f"HP: {mon.current_hp}/{mon.max_hp} | Type: {type_str}{status_tag}\n"
                            f"      ID: {mon.unique_id} | Moves: {attacks_str} | Bond: {mon.bond}/100 | Exp: {mon.experience}"
                        )
                stored_count = len([m for m in self.player.collection if not self.player.is_on_team(m)])
                self._print(f"\nSummary: {len(self.player.team)} on Team | {stored_count} stored in PC Box")
            elif sub_choice.strip() == "3":
                if len(self.player.team) >= self.player.max_team_size:
                    self._print(f"\n[-] Your team is already full ({self.player.max_team_size}/{self.player.max_team_size})! You must swap a Pokemon or free a slot first.")
                    continue

                stored_pokemon = [m for m in self.player.collection if not self.player.is_on_team(m)]
                if not stored_pokemon:
                    self._print("\n[-] You have no Pokemon stored in your PC to add to the team.")
                    continue

                self._print("\n" + "-" * 45)
                self._print("STORED POKEMON IN PC")
                self._print("-" * 45)
                for idx, mon in enumerate(stored_pokemon, 1):
                    status_tag = " (FAINTED)" if mon.is_fainted else ""
                    self._print(f" [{idx}] {mon.display_name} (Lv.{mon.level}) HP: {mon.current_hp}/{mon.max_hp} | Type: {mon.species.primary_type.value}{status_tag}")
                self._print(" [0] Cancel")

                choice_str = self._prompt(f"Select stored Pokemon to add (1-{len(stored_pokemon)}, 0 to cancel): ")
                if choice_str.strip() in ("0", "cancel", "back", "quit", ""):
                    self._print("Canceled adding Pokemon.")
                    continue

                try:
                    c_idx = int(choice_str.strip())
                    if 1 <= c_idx <= len(stored_pokemon):
                        chosen_mon = stored_pokemon[c_idx - 1]
                        if self.player.is_on_team(chosen_mon):
                            self._print(f"\n[-] {chosen_mon.display_name} is already on your team.")
                        elif len(self.player.team) >= self.player.max_team_size:
                            self._print(f"\n[-] Team is full ({self.player.max_team_size}/{self.player.max_team_size}).")
                        else:
                            self.player.add_to_team(chosen_mon)
                            if self.player.active_pokemon is None and not chosen_mon.is_fainted:
                                self.player.set_active_pokemon(chosen_mon)
                            self._print(f"\n[+] {chosen_mon.display_name} was added to your team!")
                    else:
                        self._print("Invalid selection number.")
                except ValueError:
                    self._print("Please enter a valid number.")
            elif sub_choice.strip() == "4":
                stored_pokemon = [m for m in self.player.collection if not self.player.is_on_team(m)]
                if not stored_pokemon:
                    self._print("\n[-] You have no Pokemon stored in your PC to swap into the team.")
                    continue

                if not self.player.team:
                    self._print("\n[-] Your team is empty. Use 'Add Stored Pokemon to Team' instead.")
                    continue

                self._print("\n" + "-" * 45)
                self._print("SELECT TEAM MEMBER TO SEND TO PC")
                self._print("-" * 45)
                for idx, mon in enumerate(self.player.team, 1):
                    active_tag = " [*ACTIVE*]" if mon is self.player.active_pokemon else ""
                    status_tag = " (FAINTED)" if mon.is_fainted else ""
                    self._print(f" [{idx}]{active_tag} {mon.display_name} (Lv.{mon.level}) HP: {mon.current_hp}/{mon.max_hp}{status_tag}")
                self._print(" [0] Cancel")

                team_idx_str = self._prompt(f"Select team member to swap out (1-{len(self.player.team)}, 0 to cancel): ")
                if team_idx_str.strip() in ("0", "cancel", "back", "quit", ""):
                    self._print("Canceled team swap.")
                    continue

                try:
                    t_idx = int(team_idx_str.strip())
                    if not (1 <= t_idx <= len(self.player.team)):
                        self._print("Invalid team member number.")
                        continue
                except ValueError:
                    self._print("Please enter a valid number.")
                    continue

                team_mon = self.player.team[t_idx - 1]

                self._print("\n" + "-" * 45)
                self._print("SELECT STORED POKEMON TO BRING FROM PC")
                self._print("-" * 45)
                for idx, mon in enumerate(stored_pokemon, 1):
                    status_tag = " (FAINTED)" if mon.is_fainted else ""
                    self._print(f" [{idx}] {mon.display_name} (Lv.{mon.level}) HP: {mon.current_hp}/{mon.max_hp}{status_tag}")
                self._print(" [0] Cancel")

                pc_idx_str = self._prompt(f"Select stored Pokemon to bring in (1-{len(stored_pokemon)}, 0 to cancel): ")
                if pc_idx_str.strip() in ("0", "cancel", "back", "quit", ""):
                    self._print("Canceled team swap.")
                    continue

                try:
                    p_idx = int(pc_idx_str.strip())
                    if not (1 <= p_idx <= len(stored_pokemon)):
                        self._print("Invalid stored Pokemon number.")
                        continue
                except ValueError:
                    self._print("Please enter a valid number.")
                    continue

                pc_mon = stored_pokemon[p_idx - 1]

                try:
                    self.player.swap_team_member(team_mon, pc_mon)
                    self._print(f"\n[+] Successfully swapped {team_mon.display_name} with {pc_mon.display_name}!")
                    self._print(f"    {team_mon.display_name} is now stored in your PC.")
                    self._print(f"    {pc_mon.display_name} is now in your active team!")
                except Exception as e:
                    self._print(f"\n[-] Failed to swap Pokemon: {e}")
            elif sub_choice.strip() == "5":
                if len(self.player.team) <= 1:
                    self._print("\n[-] You cannot deposit your only team Pokemon! You must keep at least 1 Pokemon in your team.")
                    continue

                self._print("\n" + "-" * 45)
                self._print("SELECT TEAM MEMBER TO DEPOSIT TO PC")
                self._print("-" * 45)
                for idx, mon in enumerate(self.player.team, 1):
                    active_tag = " [*ACTIVE*]" if mon is self.player.active_pokemon else ""
                    status_tag = " (FAINTED)" if mon.is_fainted else ""
                    self._print(f" [{idx}]{active_tag} {mon.display_name} (Lv.{mon.level}) HP: {mon.current_hp}/{mon.max_hp}{status_tag}")
                self._print(" [0] Cancel")

                dep_idx_str = self._prompt(f"Select team member to deposit (1-{len(self.player.team)}, 0 to cancel): ")
                if dep_idx_str.strip() in ("0", "cancel", "back", "quit", ""):
                    self._print("Canceled deposit.")
                    continue

                try:
                    d_idx = int(dep_idx_str.strip())
                    if 1 <= d_idx <= len(self.player.team):
                        dep_mon = self.player.team[d_idx - 1]
                        self.player.remove_from_team(dep_mon)
                        if self.player.active_pokemon is None:
                            first_conscious = next((p for p in self.player.team if not p.is_fainted), None)
                            if first_conscious is None and self.player.team:
                                first_conscious = self.player.team[0]
                            self.player.set_active_pokemon(first_conscious)
                        self._print(f"\n[+] {dep_mon.display_name} was deposited to your PC.")
                    else:
                        self._print("Invalid team member number.")
                except ValueError:
                    self._print("Please enter a valid number.")
            else:
                self._print("Invalid selection.")

    def _action_partner_interaction(self) -> None:
        """Direct conversational and behavioral interaction with partner Pokemon via autonomous AI."""
        if self.player is None or self.player.active_pokemon is None:
            self._print("\nYou don't currently have an active partner Pokemon!")
            return

        active_mon = self.player.active_pokemon
        from src.ai.companion_service import CompanionService
        agent = CompanionService.get_or_create_companion_agent(active_mon, self.ai_state, self.player)

        while True:
            rel = agent.get_relationship(self.player.unique_id, default_name=self.player.name, default_type="trainer")
            self._print("\n" + "=" * 55)
            self._print(f" PARTNER POKÉMON: {active_mon.display_name} (Lv.{active_mon.level} {active_mon.species.name})")
            self._print(f" Temperament: {agent.identity.temperament.capitalize()} | Relationship: {rel.stage.value.capitalize()}")
            self._print(f" Trust: {rel.trust:+.1f} | Affection: {rel.affection:+.1f} | Familiarity: {rel.familiarity:.1f}/100")
            self._print(f" Bond : {active_mon.bond}/100 | Obedience: {active_mon.obedience}/100")
            self._print("=" * 55)
            self._print("Speak freely with your partner Pokemon (praise, scold, ask questions,")
            self._print("discuss goals, interact with teammates, or talk about release).")
            self._print("[Type 'back' or '0' to return to Adventure Menu]")

            user_input = self._prompt(f"\n{self.player.name}: ").strip()

            if user_input.lower() in ("0", "cancel", "back", "quit", "exit", "leave", "done"):
                break
            if not user_input:
                continue

            # Check if player refers to teammate interaction
            other_members = [p for p in self.player.team if p is not active_mon]
            teammate_target = None
            if len(other_members) >= 1:
                lower_in = user_input.lower()
                for tm in other_members:
                    if tm.display_name.lower() in lower_in or tm.species.name.lower() in lower_in:
                        teammate_target = tm
                        break

            if teammate_target is not None:
                agent2 = CompanionService.get_or_create_companion_agent(teammate_target, self.ai_state, self.player)
                t_res = CompanionService.teammate_interaction(agent, active_mon, agent2, teammate_target, context=user_input)
                self._print(f"\n{active_mon.display_name}: \"{t_res.pokemon1_dialogue}\"")
                self._print(f"{teammate_target.display_name}: \"{t_res.pokemon2_dialogue}\"")
                self._print(f"  > {t_res.summary}")
                continue

            # Process AI interaction through decision provider
            res = CompanionService.interact(
                agent=agent,
                pokemon=active_mon,
                player=self.player,
                interaction_type="talk",
                message=user_input,
                bond_manager=self.bond_manager,
                ai_state=self.ai_state,
            )

            self._print(f"\n{active_mon.display_name}: \"{res.dialogue}\"")
            self._print(f"  > {res.reaction_summary}")
            if res.trust_change or res.affection_change or res.bond_change:
                sign_t = f"{res.trust_change:+.1f}"
                sign_a = f"{res.affection_change:+.1f}"
                sign_b = f"{res.bond_change:+d}"
                self._print(f"  [*] Trust {sign_t} | Affection {sign_a} | Bond {sign_b}")

            # If goals were discussed or asked about, display active and long-term goals
            if res.inferred_type == "discuss_goals":
                self._print("  > Current Goals:")
                for g in agent.goals.immediate_goals:
                    status_tag = "[COMPLETED]" if g.get("status") == "completed" else "[ACTIVE]"
                    self._print(f"    * {status_tag} {g.get('description')}")
                for g in agent.goals.long_term_goals:
                    self._print(f"    * [LONG TERM] {g.get('description')}")

            # If release was requested by Pokemon or initiated by player
            if res.requested_release or res.inferred_type == "discuss_release":
                if any(w in user_input.lower() for w in ("release", "set free", "goodbye", "farewell")):
                    if len(self.player.collection) <= 1:
                        self._print("\n[-] You cannot release your only Pokemon! A trainer must have at least one partner.")
                    else:
                        confirm = self._prompt(f"\nAre you sure you want to release {active_mon.display_name} to the wild forever? (yes/no): ").strip().lower()
                        if confirm in ("yes", "y"):
                            ok, msg = CompanionService.release_pokemon(agent, active_mon, self.player, self.ai_state)
                            if ok:
                                self._print(f"\n[+] {msg}")
                                break
                            else:
                                self._print(f"\n[-] {msg}")
                        else:
                            self._print("Release canceled.")

    def _action_inventory(self) -> None:
        """Displays inventory and allows item usage on team Pokemon."""
        if self.player is None:
            return

        while True:
            inv_items = self.player.inventory.list_items()
            self._print("\n" + "-" * 40)
            self._print(f"INVENTORY ({self.player.inventory.slots_used}/{self.player.inventory.capacity} slots)")
            self._print("-" * 40)

            if not inv_items:
                self._print("Your inventory is currently empty.")
                self._prompt("\nPress Enter to return: ")
                break

            for idx, stack in enumerate(inv_items, 1):
                i_name = stack.item.name if stack.item else stack.item_id
                i_desc = stack.item.description if stack.item else ""
                self._print(f" [{idx}] {i_name} x{stack.quantity} - {i_desc}")

            self._print("\n [1] Use an Item")
            self._print(" [0] Back to Main Menu")

            sub_choice = self._prompt("Choose action (0-1): ")
            if sub_choice in ("0", "cancel", "back", "quit"):
                break
            elif sub_choice == "1":
                item_idx_str = self._prompt(f"Select item number to use (1-{len(inv_items)}): ")
                try:
                    item_idx = int(item_idx_str)
                    if not (1 <= item_idx <= len(inv_items)):
                        self._print("Invalid item choice.")
                        continue
                except ValueError:
                    self._print("Please enter a valid number.")
                    continue

                selected_item_entry = inv_items[item_idx - 1]
                item_def = ITEM_CATALOG.get(selected_item_entry.item_id)

                if item_def is not None and item_def.item_type == ItemType.CAPTURE:
                    self._print("\nPoke Balls can only be used during wild Pokemon battles!")
                    continue

                # Select target Pokemon
                self._print("\nSelect target Pokemon:")
                for p_idx, p_mon in enumerate(self.player.team, 1):
                    self._print(f" [{p_idx}] {p_mon.display_name} (HP: {p_mon.current_hp}/{p_mon.max_hp})")
                self._print(" [0] Cancel")

                target_str = self._prompt(f"Target Pokemon (0-{len(self.player.team)}): ")
                if target_str in ("0", "cancel", "back", "quit"):
                    continue

                try:
                    target_idx = int(target_str)
                    if not (1 <= target_idx <= len(self.player.team)):
                        self._print("Invalid target Pokemon.")
                        continue
                except ValueError:
                    self._print("Please enter a valid number.")
                    continue

                target_mon = self.player.team[target_idx - 1]
                use_res = self.item_manager.use_item(
                    inventory=self.player.inventory,
                    item_or_id=selected_item_entry.item_id,
                    target_pokemon=target_mon,
                    player=self.player,
                )

                entry_name = selected_item_entry.item.name if selected_item_entry.item else selected_item_entry.item_id
                if use_res.success:
                    self._print(f"\n[+] {use_res.message}")
                else:
                    self._print(f"\n[-] Could not use {entry_name}: {use_res.message}")
            else:
                self._print("Invalid selection.")

        self._display_quest_notifications()

    def _action_quests(self) -> None:
        """Displays quest log, accepts available quests, and claims completed rewards."""
        if self.player is None:
            return

        while True:
            active_quests = self.quest_manager.list_active_quests(self.player)
            available_quests = self.quest_manager.list_available_quests(self.player)
            completed_quests = self.quest_manager.list_completed_quests(self.player)

            self._print("\n" + "-" * 40)
            self._print("QUEST LOG")
            self._print("-" * 40)

            self._print("ACTIVE QUESTS:")
            if not active_quests:
                self._print(" (None)")
            else:
                for q_def in active_quests:
                    prog = self.player.quests.get(q_def.quest_id)
                    all_done = prog.is_all_objectives_completed() if prog else False
                    tag = " [READY TO CLAIM!]" if all_done else ""
                    self._print(f" * {q_def.name}: {q_def.description}{tag}")
                    if prog:
                        for obj_id, obj_prog in prog.objective_progress.items():
                            status_str = "COMPLETED" if obj_prog.is_completed else "IN PROGRESS"
                            marker = "[X]" if obj_prog.is_completed else "[ ]"
                            self._print(f"    - {marker} {obj_id}: {obj_prog.current_count}/{obj_prog.target_count} ({status_str})")

            self._print("\nAVAILABLE QUESTS:")
            if not available_quests:
                self._print(" (None)")
            else:
                for q_def in available_quests:
                    reward_str = ", ".join(f"{cnt}x {it}" for it, cnt in q_def.rewards.items()) or "None"
                    self._print(f" * {q_def.name} (ID: {q_def.quest_id}) - Reward: {reward_str}\n   {q_def.description}")

            self._print("\nCOMPLETED QUESTS:")
            if not completed_quests:
                self._print(" (None)")
            else:
                for q_def in completed_quests:
                    self._print(f" [+] {q_def.name}")

            self._print("\n [1] Accept an Available Quest")
            self._print(" [2] Claim Completed Quest Rewards")
            self._print(" [3] Open Detailed Quest Journal")
            self._print(" [0] Back to Main Menu")

            sub_choice = self._prompt("Choose action (0-3): ")
            if sub_choice in ("0", "cancel", "back", "quit"):
                break
            elif sub_choice == "1":
                if not available_quests:
                    self._print("\nNo quests are currently available to accept.")
                    continue
                self._print("\nSelect quest to accept:")
                for idx, q_def in enumerate(available_quests, 1):
                    self._print(f" [{idx}] {q_def.name}")
                self._print(" [0] Cancel")

                q_sel = self._prompt(f"Select quest (0-{len(available_quests)}): ")
                if q_sel in ("0", "cancel", "back", "quit"):
                    continue
                try:
                    q_val = int(q_sel)
                    if 1 <= q_val <= len(available_quests):
                        target_q = available_quests[q_val - 1]
                        accept_res = self.quest_manager.accept_quest(self.player, target_q.quest_id)
                        if accept_res.success:
                            self._print(f"\n[+] Accepted quest: '{target_q.name}'!")
                            self._display_quest_notifications()
                            if self.quest_manager.get_available_choices(self.player, target_q.quest_id):
                                self._handle_quest_choices(target_q.quest_id, target_q, None)
                                self._display_quest_current_objectives(target_q.quest_id, target_q)
                        else:
                            self._print(f"\n[-] Could not accept quest: {accept_res.message}")
                    else:
                        self._print("Invalid selection.")
                except ValueError:
                    self._print("Please enter a valid number.")

            elif sub_choice == "2":
                # Find claimable completed quests
                claimable = [
                    q_def for q_def in self.quest_manager._catalog.values()
                    if self.player.quests.get(q_def.quest_id)
                    and (
                        self.player.quests[q_def.quest_id].is_completed
                        or self.player.quests[q_def.quest_id].is_all_objectives_completed()
                    )
                    and not self.player.quests[q_def.quest_id].rewards_claimed
                ]
                if not claimable:
                    self._print("\nNo completed quests with unclaimed rewards.")
                    continue

                for q_def in claimable:
                    rew = q_def.rewards
                    rew_str = ", ".join(f"{cnt}x {it.replace('_', ' ').title()}" for it, cnt in rew.items()) if rew else "None"
                    self._print(f"\nAvailable rewards for '{q_def.name}': {rew_str}")
                    claim_res = self.quest_manager.claim_rewards(self.player, q_def.quest_id)
                    if claim_res.success:
                        items_str = ", ".join(f"{cnt}x {it}" for it, cnt in claim_res.items_granted.items()) if claim_res.items_granted else "None"
                        self._print(f"[*] Claimed rewards for '{q_def.name}': {items_str}!")
                    else:
                        self._print(f"[-] Could not claim rewards for '{q_def.name}': {claim_res.message}")
            elif sub_choice in ("3", "journal", "j"):
                self._action_quest_journal()
            else:
                self._print("Invalid choice.")

    def _action_quest_journal(self) -> None:
        """Dedicated Quest Journal screen displaying tracked quest progress and dossiers."""
        if self.player is None:
            return

        current_filter: Optional[str] = None  # None = All, 'active', 'completed'
        current_page: int = 1
        page_size: int = 4

        while True:
            # Re-read authoritative state on every redraw
            entries = self.quest_journal.get_tracked_entries(self.player, filter_status=current_filter)

            # Print header
            self._print("\n" + "\n".join(self.quest_journal.format_summary_header(self.player)))

            # Filter status indicator
            f_label = "ALL TRACKED" if not current_filter else current_filter.upper()
            self._print(f" CURRENT VIEW: {f_label} ({len(entries)} quests)")
            self._print("-" * 55)

            # Print quest list
            list_lines, current_page, total_pages = self.quest_journal.format_quest_list(
                entries, page=current_page, page_size=page_size
            )
            for line in list_lines:
                self._print(line)

            # Journal navigation actions
            self._print("--- JOURNAL ACTIONS ---")
            self._print(" [1] Inspect Quest Details")
            self._print(" [2] Filter Quests (All / Active / Completed)")
            self._print(" [3] Claim Available Rewards")
            if total_pages > 1:
                self._print(f" [N] Next Page | [P] Previous Page (Page {current_page}/{total_pages})")
            self._print(" [0] Back to Previous Menu")

            j_choice = self._prompt("Journal option: ").strip().lower()

            if j_choice in ("0", "back", "cancel", "quit", "q"):
                break
            elif j_choice in ("n", "next") and total_pages > 1:
                if current_page < total_pages:
                    current_page += 1
                else:
                    self._print("\nAlready on the last page.")
            elif j_choice in ("p", "prev", "previous") and total_pages > 1:
                if current_page > 1:
                    current_page -= 1
                else:
                    self._print("\nAlready on the first page.")
            elif j_choice == "1" or j_choice.startswith("inspect"):
                if not entries:
                    self._print("\nNo quests in the current view to inspect.")
                    continue

                sel_str = self._prompt(f"Select quest number to inspect (1-{len(entries)}, 0 to cancel): ").strip()
                if sel_str in ("0", "cancel", "back", "quit", ""):
                    continue
                try:
                    q_num = int(sel_str)
                    if 1 <= q_num <= len(entries):
                        target_entry = entries[q_num - 1]
                        dossier_lines = self.quest_journal.format_quest_dossier(target_entry)
                        self._print("\n" + "\n".join(dossier_lines))
                        self._prompt("\nPress Enter to return to journal: ")
                    else:
                        self._print("Invalid quest number.")
                except ValueError:
                    self._print("Please enter a valid number.")

            elif j_choice == "2" or j_choice == "filter":
                self._print("\nSelect view filter:")
                self._print(" [1] All Tracked Quests")
                self._print(" [2] Active Quests Only")
                self._print(" [3] Completed Quests Only")
                self._print(" [0] Cancel")
                f_sel = self._prompt("Choose filter (0-3): ").strip()
                if f_sel == "1":
                    current_filter = None
                    current_page = 1
                elif f_sel == "2":
                    current_filter = "active"
                    current_page = 1
                elif f_sel == "3":
                    current_filter = "completed"
                    current_page = 1
                elif f_sel in ("0", "cancel"):
                    pass
                else:
                    self._print("Invalid filter choice.")

            elif j_choice == "3" or j_choice in ("claim", "rewards"):
                claimable = [
                    e for e in self.quest_journal.get_tracked_entries(self.player)
                    if e.can_claim_rewards
                ]
                if not claimable:
                    self._print("\nNo completed quests with unclaimed rewards.")
                    continue

                for entry in claimable:
                    rew_str = entry.formatted_rewards
                    self._print(f"\nAvailable rewards for '{entry.name}': {rew_str}")
                    claim_res = self.quest_manager.claim_rewards(self.player, entry.quest_id)
                    if claim_res.success:
                        items_str = ", ".join(f"{cnt}x {it}" for it, cnt in claim_res.items_granted.items()) if claim_res.items_granted else "None"
                        self._print(f"[*] Claimed rewards for '{entry.name}': {items_str}!")
                    else:
                        self._print(f"[-] Could not claim rewards for '{entry.name}': {claim_res.message}")
            else:
                # Also allow direct numeric selection of a quest from the menu!
                try:
                    direct_num = int(j_choice)
                    if 1 <= direct_num <= len(entries):
                        target_entry = entries[direct_num - 1]
                        dossier_lines = self.quest_journal.format_quest_dossier(target_entry)
                        self._print("\n" + "\n".join(dossier_lines))
                        self._prompt("\nPress Enter to return to journal: ")
                    else:
                        self._print(f"Invalid choice '{j_choice}'.")
                except ValueError:
                    self._print(f"Invalid option '{j_choice}'.")

    def _action_view_map(self) -> None:
        """Displays discovered regions, landmarks, and spatial coordinates."""
        if self.player is None:
            return

        self._print("\n" + "-" * 40)
        self._print("WORLD MAP & DISCOVERED LOCATIONS")
        self._print("-" * 40)
        self._print(f"Current Position: ({self.player_pos[0]:.1f}, {self.player_pos[1]:.1f}) in {self.current_region_id}")

        self._print("\nDISCOVERED REGIONS:")
        if not self.player.discovered_regions:
            self._print(" (None)")
        else:
            for reg_id in sorted(self.player.discovered_regions):
                reg = self.world_exploration_manager.get_region(reg_id)
                reg_name = reg.name if reg else reg_id
                bounds_str = f"Bounds: {reg.bounds}" if reg else ""
                desc = reg.description if reg else ""
                self._print(f" * {reg_name} ({bounds_str})\n   {desc}")

        self._print("\nDISCOVERED LANDMARKS:")
        if not self.player.discovered_landmarks:
            self._print(" (None)")
        else:
            for lm_id in sorted(self.player.discovered_landmarks):
                obj = self.world_interaction_manager.get_object(lm_id)
                lm_name = obj.name if obj else lm_id
                pos_str = f"Coords: {obj.position}" if obj else ""
                desc = obj.description if obj else ""
                self._print(f" * {lm_name} ({pos_str})\n   {desc}")

        self._prompt("\nPress Enter to return: ")

    def _action_rest(self) -> None:
        """Advances time by resting."""
        self._print("\nResting allows time to pass and resource nodes to recover.")
        hours_str = self._prompt("How many hours would you like to rest? (1-12, default 8): ")
        if hours_str in ("cancel", "back", "quit"):
            return

        hours = 8.0
        if hours_str.strip():
            try:
                val = float(hours_str)
                if 1.0 <= val <= 24.0:
                    hours = val
                else:
                    self._print("Defaulting to 8 hours.")
            except ValueError:
                self._print("Invalid number; resting for 8 hours.")

        self.advance_time(hours)
        self._print(f"\nYou rested for {hours:.1f} hours. The current time is now {self.get_time_display()}.")

        if hasattr(self, "ai_state") and self.ai_state is not None:
            from src.ai.scheduler import AutonomousWorldScheduler
            rest_events = AutonomousWorldScheduler.on_rest(
                player=self.player,
                hours=hours,
                ai_state=self.ai_state,
            )
            for evt in rest_events:
                self._print(f"  > {evt}")

    def _action_save(self) -> None:
        """Saves player progress to disk."""
        if self.player is None:
            return

        try:
            save_game(self.player, self.save_file)
            if hasattr(self, "ai_state") and self.ai_state is not None:
                ai_path = get_ai_state_path_for_save_file(self.save_file)
                self.ai_state.sync_with_player_collection(self.player)
                save_ai_state(self.ai_state, ai_path)
            if hasattr(self, "trainer_manager") and self.trainer_manager is not None:
                trainer_path = get_trainer_state_path_for_save_file(self.save_file)
                self.trainer_manager.save_to_file(trainer_path)
            self._print(f"\n[+] Game progress successfully saved to '{self.save_file}'.")
        except Exception as e:
            self._print(f"\n[-] Failed to save game: {e}")

    def _action_challenge_trainer(self) -> None:
        """Allows player to challenge local area trainers to an AI-controlled battle."""
        if self.player is None:
            return

        if not self.player.team or not any(not p.is_fainted for p in self.player.team):
            self._print("\nAll Pokemon on your team have fainted! You cannot battle right now.")
            self._print("Heal your team before challenging trainers.")
            return

        trainers = self.trainer_manager.get_trainers_in_region(self.current_region_id)
        if not trainers:
            region = self.world_exploration_manager.get_region(self.current_region_id)
            r_name = region.name if region else self.current_region_id
            self._print(f"\nThere are no opponent trainers currently waiting for a battle in {r_name}.")
            return

        self._print("\n" + "=" * 50)
        self._print(f" AREA TRAINERS - {self.current_region_id.replace('_', ' ').title()}")
        self._print("=" * 50)
        for idx, t in enumerate(trainers, 1):
            if t.is_defeated:
                status = "[DEFEATED]" if not t.rematch_available else "[REMATCH AVAILABLE]"
            else:
                status = "[READY TO BATTLE]"
            diff_tag = f"({t.difficulty.value.upper()})"
            team_size = f"{len(t.team)} Pokemon" if t.has_team else "Team unrevealed"
            self._print(f" [{idx}] {t.title} - {diff_tag} {status} ({team_size})")
        self._print(" [0] Cancel")

        choice = self._prompt(f"\nSelect a trainer to challenge (0-{len(trainers)}): ")
        if choice in ("0", "cancel", "back", "quit", "exit", ""):
            return

        try:
            val = int(choice)
            if not (1 <= val <= len(trainers)):
                self._print(f"Invalid trainer selection '{choice}'.")
                return
        except ValueError:
            self._print(f"Invalid input '{choice}'. Please enter a number.")
            return

        target_trainer = trainers[val - 1]

        if target_trainer.is_defeated and not target_trainer.rematch_available:
            if target_trainer.dialogue_defeat:
                self._print(f"\n{target_trainer.title}: \"{target_trainer.dialogue_defeat}\"")
            self._print(f"[-] {target_trainer.title} has already been defeated! Train more and return later for a rematch.")
            return

        # Prepare battle (generates dynamic progression-scaled team if not yet populated)
        self._print(f"\nYou challenged {target_trainer.title} to a battle!")
        if target_trainer.dialogue_intro:
            self._print(f"{target_trainer.title}: \"{target_trainer.dialogue_intro}\"")

        self.advance_time(seconds=10.0)
        prepared_trainer = self.trainer_manager.prepare_trainer_battle(
            trainer_id=target_trainer.trainer_id,
            player=self.player,
            rng=self.rng,
        )

        battle = self.battle_manager.start_trainer_battle(
            player=self.player,
            opponent_trainer=prepared_trainer,
        )
        self._battle_loop(battle)


    def _print_battle_events(self, battle: Battle, res: BattleActionResult, prev_event_count: int) -> int:
        """Prints battle log messages generated during an action."""
        new_events = battle.events[prev_event_count:]
        if new_events:
            for evt in new_events:
                self._print(f"  > {evt}")
        elif res.turn_result and res.turn_result.actions:
            for act in res.turn_result.actions:
                if act.message:
                    self._print(f"  > {act.message}")
        elif res.reason:
            self._print(f"  > {res.reason}")
        return len(battle.events)

    def _handle_battle_talk_menu(self, battle: Battle, active_mon: Pokemon, opp_mon: Optional[Pokemon], prev_event_cursor: int) -> int:
        """
        Presents interactive Battle Talk to the player.
        Supports freeform speech, advice requests, praise, warnings, and morale tracking.
        """
        from src.ai.battle_talk_parser import BattleTalkParser

        opp_name = opp_mon.display_name if opp_mon else "the opponent"

        self._print("\n" + "=" * 50)
        self._print(f" BATTLE TALK: Speak to {active_mon.display_name}")
        self._print("=" * 50)
        self._print(" Examples:")
        self._print("  - Advice   : 'What move should we use?' / 'What should we do?'")
        self._print("  - Praise   : 'Great attack!' / 'Awesome job, buddy!'")
        self._print("  - Encourage: 'Hang in there!' / 'You\'ve got this!'")
        self._print("  - Warning  : 'Watch out for that attack!'")
        self._print("  - Tactical : 'Dodge to the left!' / 'Brace yourself!'")
        self._print("  - Hold Back: 'Bulbasaur only do 4 damage now' / 'Hold back!'")
        self._print("-" * 50)

        typed_text = self._prompt(f"Enter words for {active_mon.display_name} (or 'cancel'): ").strip()
        if typed_text.lower() in ("cancel", "back", "0", "exit", ""):
            self._print("[-] Battle talk cancelled.")
            return prev_event_cursor

        personality_dict = active_mon.personality.to_dict() if getattr(active_mon, "personality", None) else {}
        opp_hp = getattr(opp_mon, "current_hp", 30) if opp_mon else 30
        opp_max_hp = getattr(opp_mon, "max_hp", 30) if opp_mon else 30

        battle_ctx = {
            "turn": battle.current_turn,
            "hp_current": active_mon.current_hp,
            "hp_max": active_mon.max_hp,
            "hp_ratio": active_mon.current_hp / max(1, active_mon.max_hp),
            "opponent_hp_ratio": opp_hp / max(1, opp_max_hp),
            "status_effects": [eff.name.lower() for eff in getattr(active_mon, "status_effects", [])],
            "opponent_species": getattr(getattr(opp_mon, "species", None), "name", opp_name),
            "known_moves": [a.name for a in active_mon.attacks],
        }

        resp = BattleTalkParser.generate_fallback_response(
            species=active_mon.species.name,
            nickname=active_mon.display_name,
            message=typed_text,
            personality=personality_dict,
            temperament="bold",
            bond=float(getattr(active_mon, "bond", 50.0)),
            obedience=float(getattr(active_mon, "obedience", 70.0)),
            battle_context=battle_ctx,
            is_opponent=False,
        )

        morale_sign = "+" if resp["morale_delta"] > 0 else ""
        self._print("\n" + "-" * 50)
        self._print(f" [Battle Talk] Intent: {resp['intent']} | Morale: {morale_sign}{resp['morale_delta']} ({resp['momentum_tier']})")
        self._print(f" {active_mon.display_name} [{resp['emotional_state'].upper()}]: \"{resp['dialogue']}\"")
        if resp.get("tactical_suggestion"):
            self._print(f" [*] Tactical Suggestion: Recommended move -> {resp['tactical_suggestion']}")
        
        if resp.get("is_restrained_strike"):
            chosen_name = resp.get("chosen_move")
            precision_dmg = resp.get("precision_damage", 4)
            self._print(f" [*] Precision Strike: {active_mon.display_name} will hold back with {chosen_name} for ~{precision_dmg} DMG!")
            matching_atk = next((a for a in active_mon.attacks if a.name.lower() == chosen_name.lower()), None)
            if matching_atk is None and active_mon.attacks:
                matching_atk = active_mon.attacks[0]
            if matching_atk:
                exec_now = self._prompt(f"Execute {matching_atk.name} restrained strike right now? (y/n): ").strip().lower()
                if exec_now in ("y", "yes", "1"):
                    battle.set_override_player_damage(precision_dmg)
                    res = self.battle_manager.attack(self.player, matching_atk)
                    prev_event_cursor = self._print_battle_events(battle, res, prev_event_cursor)

        self._print("-" * 50 + "\n")

        return prev_event_cursor
# 
    # --- Battle Sub-Loop ---

    def _battle_loop(self, battle: Battle) -> None:
        """Runs the interactive turn-based battle engine sub-loop."""
        if self.player is None:
            return

        is_trainer = battle.is_trainer_battle
        trainer = getattr(battle, "opponent_trainer", None)
        opp_mon = battle.pokemon2
        event_cursor = len(battle.events)

        while not battle.state.is_terminal():
            active_mon = self.player.active_pokemon
            opp_mon = battle.pokemon2

            # Check if active Pokemon fainted mid-battle
            if active_mon is None or active_mon.is_fainted:
                conscious_teammates = [p for p in self.player.team if not p.is_fainted]
                if not conscious_teammates:
                    self._print(f"\nAll your Pokemon have fainted!")
                    self.battle_manager.resolve_battle(self.player, reason="All player Pokemon fainted")
                    break

                self._print(f"\nYour {active_mon.display_name if active_mon else 'Pokemon'} fainted!")
                self._print("You must send out a conscious teammate:")
                for idx, teammate in enumerate(conscious_teammates, 1):
                    self._print(f" [{idx}] {teammate.display_name} (HP: {teammate.current_hp}/{teammate.max_hp})")

                switch_choice = self._prompt(f"Choose Pokemon to send out (1-{len(conscious_teammates)}): ")
                if switch_choice in ("quit", "exit"):
                    self.battle_manager.resolve_battle(self.player, reason="Player quit")
                    break
                try:
                    sw_val = int(switch_choice)
                    if 1 <= sw_val <= len(conscious_teammates):
                        sw_res = self.battle_manager.switch(self.player, conscious_teammates[sw_val - 1])
                        event_cursor = self._print_battle_events(battle, sw_res, event_cursor)
                        continue
                    else:
                        self._print("Invalid selection.")
                        continue
                except ValueError:
                    self._print("Please enter a number.")
                    continue

            # Display Battle HUD
            self._print("\n" + "-" * 45)
            rep = getattr(self.player, "behavior_profile", None)
            rep_label = f" | Demeanor: {rep.value.capitalize()}" if rep else ""

            if is_trainer and trainer is not None:
                trainer_team = getattr(trainer, "team", [])
                conscious_opp = len([p for p in trainer_team if not p.is_fainted])
                total_opp = len(trainer_team)
                self._print(f" TRAINER BATTLE: {trainer.title} (Turn {battle.current_turn})")
                self._print(f" Your Pokemon  : {active_mon.display_name} (Lv.{active_mon.level}) [HP: {active_mon.current_hp}/{active_mon.max_hp}]{rep_label}")
                self._print(f" Opponent Mon  : {opp_mon.display_name} (Lv.{opp_mon.level}) [HP: {opp_mon.current_hp}/{opp_mon.max_hp}]")
                self._print(f" Opponent Team : {conscious_opp}/{total_opp} conscious")
            else:
                self._print(f" BATTLE (Turn {battle.current_turn})")
                self._print(f" Your Pokemon  : {active_mon.display_name} (Lv.{active_mon.level}) [HP: {active_mon.current_hp}/{active_mon.max_hp}]{rep_label}")
                self._print(f" Wild Opponent : {opp_mon.display_name} (Lv.{opp_mon.level}) [HP: {opp_mon.current_hp}/{opp_mon.max_hp}]")
            self._print("-" * 45)
            self._print(" [1] Attack")
            self._print(" [2] Switch Pokemon")
            self._print(" [3] Throw Poke Ball")
            self._print(" [4] Flee")
            self._print(f" [5] Inspect {'Opponent' if is_trainer else 'Wild'} Pokemon")
            self._print(" [6] Battle Talk")
            self._print(" [7] Dodge (Tactical Manoeuvre)")

            action_choice = self._prompt("\nChoose action (1-7): ")

            if action_choice == "1":
                # List moves
                self._print("\nAvailable Moves:")
                for idx, atk in enumerate(active_mon.attacks, 1):
                    self._print(f" [{idx}] {atk.name} (Type: {atk.type.value}, Pwr: {atk.power}, Acc: {atk.accuracy}%)")
                self._print(" [0] Cancel")

                move_choice = self._prompt(f"Select move (0-{len(active_mon.attacks)}): ")
                if move_choice in ("quit", "exit"):
                    self.battle_manager.resolve_battle(self.player, reason="Player quit")
                    break
                if move_choice in ("0", "cancel", "back"):
                    continue

                try:
                    m_val = int(move_choice)
                    if 1 <= m_val <= len(active_mon.attacks):
                        chosen_attack = active_mon.attacks[m_val - 1]
                        res = self.battle_manager.attack(self.player, chosen_attack)
                        event_cursor = self._print_battle_events(battle, res, event_cursor)
                    else:
                        self._print("Invalid move number.")
                except ValueError:
                    self._print("Please enter a valid number.")

            elif action_choice == "2":
                eligible = [p for p in self.player.team if p is not active_mon and not p.is_fainted]
                if not eligible:
                    self._print("\nNo other conscious Pokemon available to switch to!")
                    continue

                self._print("\nSwitch to teammate:")
                for idx, t_mon in enumerate(eligible, 1):
                    self._print(f" [{idx}] {t_mon.display_name} (Lv.{t_mon.level}, HP: {t_mon.current_hp}/{t_mon.max_hp})")
                self._print(" [0] Cancel")

                sw_choice = self._prompt(f"Select Pokemon (0-{len(eligible)}): ")
                if sw_choice in ("quit", "exit"):
                    self.battle_manager.resolve_battle(self.player, reason="Player quit")
                    break
                if sw_choice in ("0", "cancel", "back"):
                    continue

                try:
                    sw_val = int(sw_choice)
                    if 1 <= sw_val <= len(eligible):
                        target_t = eligible[sw_val - 1]
                        res = self.battle_manager.switch(self.player, target_t)
                        event_cursor = self._print_battle_events(battle, res, event_cursor)
                    else:
                        self._print("Invalid selection.")
                except ValueError:
                    self._print("Please enter a valid number.")

            elif action_choice == "3":
                if is_trainer:
                    self._print("\n[-] You cannot catch another trainer's Pokémon!")
                    continue

                if not self.player.inventory.has_item("poke_ball", 1):
                    self._print("\n[-] You do not have any Poke Balls in your inventory!")
                    continue

                self.player.inventory.remove_item("poke_ball", 1)
                self.quest_manager.record_item_consumed(self.player, "poke_ball", 1)
                self._print(f"\nYou threw a Poke Ball at {opp_mon.display_name}!")
                res = self.battle_manager.attempt_capture(self.player)
                event_cursor = self._print_battle_events(battle, res, event_cursor)
                if res.captured:
                    self._print(f"[+] Congratulations! You caught the wild {opp_mon.display_name}!")
                    if self.player.is_on_team(opp_mon):
                        self._print(f"[+] {opp_mon.display_name} was captured and joined your team!")
                    else:
                        self._print(f"[+] {opp_mon.display_name} was captured and sent to your PC.")
                else:
                    self._print(f"[-] Oh no! The wild {opp_mon.display_name} broke free!")

            elif action_choice == "4":
                if is_trainer:
                    self._print("\n[-] You cannot flee from a trainer battle! You must finish the fight.")
                    continue

                res = self.battle_manager.flee(self.player)
                event_cursor = self._print_battle_events(battle, res, event_cursor)
                self._print("You safely fled from battle!")
                break

            elif action_choice == "5":
                if is_trainer:
                    trainer_name = getattr(trainer, "name", "Trainer") if trainer else "Trainer"
                    self._print(f"\n[Inspect] {trainer_name}'s {opp_mon.display_name} (Lv.{opp_mon.level})")
                    self._print(f"  Type: {', '.join(t.value for t in opp_mon.species.types)}")
                    self._print(f"  HP: {opp_mon.current_hp}/{opp_mon.max_hp}")
                    if opp_mon.attacks:
                        self._print(f"  Observed Moves: {', '.join(a.name for a in opp_mon.attacks)}")
                else:
                    res = self.battle_manager.inspect_wild_pokemon(self.player)
                    event_cursor = self._print_battle_events(battle, res, event_cursor)

            elif action_choice == "6":
                event_cursor = self._handle_battle_talk_menu(battle, active_mon, opp_mon, event_cursor)

            elif action_choice == "7":
                res = self.battle_manager.dodge(self.player)
                event_cursor = self._print_battle_events(battle, res, event_cursor)

            elif action_choice in ("quit", "exit"):
                self.battle_manager.resolve_battle(self.player, reason="Player quit")
                break

            else:
                self._print(f"Invalid choice '{action_choice}'. Please select 1, 2, 3, 4, 5, 6, or 7.")

        # Post-Battle Resolution
        self._print("\n" + "=" * 45)
        if battle.state == BattleState.VICTORY:
            if is_trainer and trainer is not None:
                self._print(f"[*] VICTORY! You defeated {trainer.title}!")
                if getattr(trainer, "dialogue_defeat", None):
                    self._print(f"  {trainer.title}: \"{trainer.dialogue_defeat}\"")
                if getattr(trainer, "reward_items", None):
                    rew_str = ", ".join(f"{cnt}x {item_id}" for item_id, cnt in trainer.reward_items.items())
                    self._print(f"  Rewards Received: {rew_str}")
            else:
                self._print(f"[*] VICTORY! Wild {opp_mon.display_name} was defeated!")
            if self.player.active_pokemon:
                self._print(
                    f"  {self.player.active_pokemon.display_name} gained experience and bond! "
                    f"(Lv.{self.player.active_pokemon.level}, XP: {self.player.active_pokemon.experience}, "
                    f"Bond: {self.player.active_pokemon.bond}/100)"
                )
        elif battle.state == BattleState.CAPTURED:
            self._print(f"[*] CAPTURED! Wild {opp_mon.display_name} was added to your Pokemon collection!")
            if self.player.is_on_team(opp_mon):
                self._print(f"    {opp_mon.display_name} joined your team!")
            else:
                self._print(f"    {opp_mon.display_name} was sent to your PC.")
        elif battle.state == BattleState.ESCAPED:
            self._print("[*] ESCAPED! You got away safely.")
        elif battle.state == BattleState.DEFEAT:
            if is_trainer and trainer is not None:
                self._print(f"[*] DEFEAT! You were defeated by {trainer.title}!")
                if getattr(trainer, "dialogue_victory", None):
                    self._print(f"  {trainer.title}: \"{trainer.dialogue_victory}\"")
            else:
                self._print("[*] DEFEAT! All your Pokemon fainted!")
            self._print("Your Pokémon fought bravely. The shared hardship strengthened your bond!")
            if self.player.active_pokemon:
                self._print(
                    f"  {self.player.active_pokemon.display_name}'s bond increased! "
                    f"(Bond: {self.player.active_pokemon.bond}/100)"
                )
            self._print("You blacked out and rushed back to safety...")
            # Restore team to prevent soft-lock
            for p in self.player.team:
                p.current_hp = p.max_hp
            self._print("Your Pokemon team was restored to full health.")

        self._print("=" * 45)
        self._display_quest_notifications()


def main() -> None:
    """CLI entry point for running the interactive adventure."""
    game = AdventureGame()
    game.run()


if __name__ == "__main__":
    main()
