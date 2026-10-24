"""
Trainer Manager coordinating world trainer registration, regional rosters,
dynamic team preparation, battle initiation, rematch lifecycle, and persistent save/load.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import random
from typing import Any, Optional, Sequence, Union

from src.models.trainer import Trainer, DifficultyProfile, TrainerArchetype
from src.models.trainer_team_generator import TrainerTeamGenerator
from src.models.player import Player


DEFAULT_TRAINERS_FILENAME: str = "trainers.json"


def get_trainer_state_path_for_save_file(save_file_path: Union[str, Path]) -> Path:
    """
    Resolves the authoritative trainers.json filepath co-located with a given game save file.

    Examples:
      - 'save_game.json' -> 'trainers.json'
      - 'saves/slot1.json' -> 'saves/trainers.json'
    """
    save_path = Path(save_file_path)
    return save_path.parent / DEFAULT_TRAINERS_FILENAME


class TrainerManager:
    """
    Registry and lifecycle coordinator for opponent trainers.
    Manages in-world trainer discovery, progression-scaled team generation,
    defeat tracking, non-farmable rewards, rematches, and persistent serialization.
    """

    def __init__(
        self,
        trainers: Optional[Sequence[Trainer]] = None,
        rng: Optional[random.Random] = None,
        seed: Optional[int] = None,
    ) -> None:
        self._trainers: dict[str, Trainer] = {}
        if rng is not None:
            self._rng = rng
        elif seed is not None:
            self._rng = random.Random(seed)
        else:
            self._rng = random.Random()

        if trainers is not None:
            for t in trainers:
                self.register_trainer(t)

    # --- Registry & Lookup ---

    def register_trainer(self, trainer: Trainer) -> None:
        """Registers a trainer into the world registry."""
        if not isinstance(trainer, Trainer):
            raise TypeError(f"Expected Trainer instance, got {type(trainer).__name__}.")
        self._trainers[trainer.trainer_id] = trainer

    def unregister_trainer(self, trainer_id: str) -> bool:
        """Removes a trainer by ID. Returns True if removed."""
        if not isinstance(trainer_id, str):
            return False
        return self._trainers.pop(trainer_id.strip().lower(), None) is not None

    def get_trainer(self, trainer_id: str) -> Optional[Trainer]:
        """Looks up a trainer by unique ID."""
        if not isinstance(trainer_id, str):
            return None
        return self._trainers.get(trainer_id.strip().lower())

    def list_trainers(self) -> list[Trainer]:
        """Returns all registered trainers in catalog order."""
        return list(self._trainers.values())

    def get_trainers_in_region(self, region_id: str) -> list[Trainer]:
        """Filters trainers situated in a specific world region."""
        if not isinstance(region_id, str):
            return []
        norm = region_id.strip().lower()
        return [t for t in self._trainers.values() if t.region_id == norm]

    # --- Battle Preparation & Team Generation ---

    def prepare_trainer_battle(
        self,
        trainer_id: str,
        player: Player,
        rng: Optional[random.Random] = None,
    ) -> Trainer:
        """
        Prepares a trainer for battle against the player.
        Generates the trainer's team if not already populated.
        Idempotent: preserves existing generated teams across area re-entries and saves.
        """
        trainer = self.get_trainer(trainer_id)
        if trainer is None:
            raise ValueError(f"Trainer '{trainer_id}' is not registered.")

        r = rng if rng is not None else self._rng

        # Generate team if not populated
        if not trainer.has_team:
            TrainerTeamGenerator.generate_team(
                trainer=trainer,
                player=player,
                region_id=trainer.region_id,
                rng=r,
            )

        return trainer

    # --- Rematch Lifecycle ---

    def enable_rematch(self, trainer_id: str) -> bool:
        """
        Flags a defeated trainer as eligible for a rematch challenge.
        """
        trainer = self.get_trainer(trainer_id)
        if trainer is None:
            return False
        trainer.rematch_available = True
        return True

    def request_rematch(
        self,
        trainer_id: str,
        player: Optional[Player] = None,
        rescale_team: bool = True,
    ) -> tuple[bool, str, Optional[Trainer]]:
        """
        Initiates a rematch with a previously defeated trainer.
        Restores battle readiness (heals team) and optionally rescales levels
        to match current player party strength.
        Rewards are not duplicated.
        Returns: (success, reason_or_message, trainer_instance)
        """
        trainer = self.get_trainer(trainer_id)
        if trainer is None:
            return False, f"Trainer '{trainer_id}' does not exist.", None

        if not trainer.is_defeated:
            return False, f"Trainer '{trainer.name}' has not been defeated yet; initiate standard battle.", trainer

        if not trainer.rematch_available:
            return False, f"Trainer '{trainer.name}' is not ready for a rematch yet.", trainer

        # Rescale team levels to player's current progression if requested
        if rescale_team and player is not None and trainer.has_team:
            party_strength = TrainerTeamGenerator.calculate_party_strength(player)
            min_lvl, target_lvl, max_lvl = TrainerTeamGenerator.get_target_level_range(
                trainer.difficulty, party_strength
            )
            for idx, mon in enumerate(trainer.team):
                if idx == len(trainer.team) - 1:
                    new_lvl = self._rng.randint(target_lvl, max_lvl)
                else:
                    new_lvl = self._rng.randint(min_lvl, max_lvl)
                mon.level = new_lvl
                # Re-evaluate level-appropriate moves
                new_moves = TrainerTeamGenerator.generate_moveset(mon.species, new_lvl)
                for atk in new_moves:
                    if not mon.knows_attack(atk):
                        mon.assign_attack(atk)

        # Reset battle state (heal HP, clear status)
        trainer.reset_battle_state()
        trainer.rematch_available = False

        msg = f"Rematch challenge accepted! {trainer.title} is ready for battle!"
        return True, msg, trainer

    # --- Serialization & Persistence ---

    def to_dict(self) -> dict[str, Any]:
        """
        Serializes all registered trainers and their states into a JSON dictionary.
        """
        return {
            "trainers": [t.to_dict() for t in self._trainers.values()]
        }

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        rng: Optional[random.Random] = None,
    ) -> TrainerManager:
        """
        Reconstructs a TrainerManager and all its trainers from serialized data.
        """
        if not isinstance(data, dict):
            raise ValueError("TrainerManager data must be a dictionary.")

        manager = cls(rng=rng)
        for t_data in data.get("trainers", []):
            trainer = Trainer.from_dict(t_data)
            manager.register_trainer(trainer)

        return manager

    def save_to_file(self, filepath: Union[str, Path]) -> None:
        """Saves trainer states to JSON file atomically."""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(".tmp")
        data = self.to_dict()
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, path)

    @classmethod
    def load_from_file(
        cls,
        filepath: Union[str, Path],
        rng: Optional[random.Random] = None,
    ) -> TrainerManager:
        """Loads and reconstructs a TrainerManager from a JSON file."""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Trainer save file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data, rng=rng)


# --- Default In-World Trainers Catalog ---

def create_default_trainers() -> list[Trainer]:
    """
    Creates fresh instances of predefined in-world trainers mapped across regions.
    Teams start ungenerated and will be dynamically generated upon first encounter.
    """
    return [
        Trainer(
            trainer_id="youngster_joey",
            name="Joey",
            title="Youngster Joey",
            archetype=TrainerArchetype.YOUNGSTER,
            difficulty=DifficultyProfile.EASY,
            region_id="starting_meadow",
            dialogue_intro="Hi! I like shorts! They're comfy and easy to wear!",
            dialogue_defeat="I lost?! My top percentage team!",
            dialogue_victory="Ha! I told you we were the best!",
            reward_items={"potion": 1, "poke_ball": 2},
        ),
        Trainer(
            trainer_id="lass_haley",
            name="Haley",
            title="Lass Haley",
            archetype=TrainerArchetype.LASS,
            difficulty=DifficultyProfile.EASY,
            region_id="starting_meadow",
            dialogue_intro="You looked at me, so we have to battle!",
            dialogue_defeat="Oh no! My cute Pokemon!",
            dialogue_victory="Yay! We won!",
            reward_items={"potion": 1, "poke_ball": 2},
        ),
        Trainer(
            trainer_id="bug_catcher_sammy",
            name="Sammy",
            title="Bug Catcher Sammy",
            archetype=TrainerArchetype.BUG_CATCHER,
            difficulty=DifficultyProfile.NORMAL,
            region_id="forest_trail",
            dialogue_intro="I spent all morning hunting Bug Pokemon in the trees!",
            dialogue_defeat="My bugs couldn't hold out...",
            dialogue_victory="Bug Pokemon are the greatest!",
            reward_items={"super_potion": 1, "antidote": 2},
        ),
        Trainer(
            trainer_id="hiker_david",
            name="David",
            title="Hiker David",
            archetype=TrainerArchetype.HIKER,
            difficulty=DifficultyProfile.NORMAL,
            region_id="mountain_pass",
            dialogue_intro="Mountain climbing toughens you up! Let's see your stamina!",
            dialogue_defeat="Whoa! You knocked the wind right out of me!",
            dialogue_victory="Gwahaha! You need to train on the mountains!",
            reward_items={"super_potion": 1, "poke_ball": 3},
        ),
        Trainer(
            trainer_id="sailor_bob",
            name="Bob",
            title="Sailor Bob",
            archetype=TrainerArchetype.SAILOR,
            difficulty=DifficultyProfile.NORMAL,
            region_id="lakeside",
            dialogue_intro="Ahoy! The lake breeze makes my Pokemon eager for a bout!",
            dialogue_defeat="Washed out! You're a fine navigator!",
            dialogue_victory="Full steam ahead! Better luck on dry land!",
            reward_items={"super_potion": 1, "poke_ball": 3},
        ),
        Trainer(
            trainer_id="psychic_edward",
            name="Edward",
            title="Psychic Edward",
            archetype=TrainerArchetype.PSYCHIC,
            difficulty=DifficultyProfile.HARD,
            region_id="haunted_ruins",
            dialogue_intro="I foresaw your arrival... and your imminent defeat.",
            dialogue_defeat="My vision was clouded... your power defies prediction.",
            dialogue_victory="As the spirits foretold.",
            reward_items={"hyper_potion": 1, "ultra_ball": 2},
        ),
        Trainer(
            trainer_id="ace_trainer_kira",
            name="Kira",
            title="Ace Trainer Kira",
            archetype=TrainerArchetype.ACE_TRAINER,
            difficulty=DifficultyProfile.HARD,
            region_id="tall_grass_plains",
            dialogue_intro="I only battle trainers who take strategy seriously. Ready?",
            dialogue_defeat="Incredible tactical execution. You've earned this win.",
            dialogue_victory="Good effort, but you need more synergy in your team.",
            reward_items={"hyper_potion": 1, "ultra_ball": 2},
        ),
        Trainer(
            trainer_id="gym_leader_brock",
            name="Brock",
            title="Gym Leader Brock",
            archetype=TrainerArchetype.GYM_LEADER,
            difficulty=DifficultyProfile.BOSS,
            region_id="mountain_pass",
            dialogue_intro="I'm Brock! My rock-hard determination will test your limits!",
            dialogue_defeat="I took you for granted. As proof of your victory, take this!",
            dialogue_victory="Rock-solid defense! Come back when you've honed your skills.",
            reward_items={"max_potion": 1, "full_restore": 1, "nugget": 1},
        ),
    ]


def create_default_trainer_manager() -> TrainerManager:
    """Creates a TrainerManager populated with the default world trainers."""
    return TrainerManager(trainers=create_default_trainers())
