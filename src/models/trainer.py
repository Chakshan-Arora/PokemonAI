"""
Trainer model representing opponent trainers in Syntax Error 26.
Defines trainer identity, difficulty profiles, archetypes, dialogue,
battle team management, defeat tracking, and persistent state.
"""
from dataclasses import dataclass, field
from enum import Enum
import uuid
from typing import Any, Optional, Sequence, Union

from src.models.pokemon import Pokemon
from src.models.player import Player
from src.models.species import PokemonSpecies
from src.models.attack import Attack
from src.models.personality import Personality


class DifficultyProfile(str, Enum):
    """
    Strategic difficulty configuration controlling trainer tactical competence.
    """
    EASY = "EASY"          # Casual trainer: basic moves, occasional mistakes, no switching
    NORMAL = "NORMAL"      # Experienced trainer: recognizes type matchups, situational switching
    HARD = "HARD"          # Specialist trainer: tactical reasoning, counter-switching, status play
    BOSS = "BOSS"          # Gym Leader / Major opponent: curated synergy, optimal moves, high aggression


class TrainerArchetype(str, Enum):
    """
    Character archetype defining thematic species affinities and combat style.
    """
    YOUNGSTER = "YOUNGSTER"          # Early-route generalist (Normal/Bug/Grass)
    BUG_CATCHER = "BUG_CATCHER"      # Bug-type enthusiast (Caterpie, Butterfree)
    LASS = "LASS"                    # Balanced cute/woodland (Normal/Grass/Electric)
    HIKER = "HIKER"                  # Sturdy earth specialist (Rock/Ground/Fighting)
    BIRD_KEEPER = "BIRD_KEEPER"      # Aerial specialist (Flying types)
    PSYCHIC = "PSYCHIC"              # Mind & spirit specialist (Psychic/Ghost)
    SAILOR = "SAILOR"                # Aquatic & brawn specialist (Water/Fighting)
    ACE_TRAINER = "ACE_TRAINER"      # Balanced competitive strategist
    GYM_LEADER = "GYM_LEADER"        # Major regional boss with curated signature teams


class Trainer:
    """
    Represents an opponent trainer in Syntax Error 26.
    Maintains identity, difficulty, team state, battle readiness, and defeat flags.
    Duck-type compatible with Player for battle engine interoperation.
    """

    def __init__(
        self,
        trainer_id: str,
        name: str,
        title: str,
        archetype: Union[TrainerArchetype, str] = TrainerArchetype.YOUNGSTER,
        difficulty: Union[DifficultyProfile, str] = DifficultyProfile.NORMAL,
        region_id: str = "starting_meadow",
        team: Optional[Sequence[Pokemon]] = None,
        active_pokemon: Optional[Pokemon] = None,
        is_defeated: bool = False,
        defeat_count: int = 0,
        rematch_available: bool = False,
        dialogue_intro: str = "",
        dialogue_defeat: str = "",
        dialogue_victory: str = "",
        reward_items: Optional[dict[str, int]] = None,
        reward_claimed: bool = False,
    ) -> None:
        if not trainer_id or not str(trainer_id).strip():
            raise ValueError("trainer_id must be a non-empty string.")
        if not name or not str(name).strip():
            raise ValueError("name must be a non-empty string.")
        if not title or not str(title).strip():
            raise ValueError("title must be a non-empty string.")
        if not region_id or not str(region_id).strip():
            raise ValueError("region_id must be a non-empty string.")

        self._trainer_id: str = str(trainer_id).strip().lower()
        self._name: str = str(name).strip()
        self._title: str = str(title).strip()

        # Archetype
        if isinstance(archetype, TrainerArchetype):
            self._archetype = archetype
        elif isinstance(archetype, str) and archetype.upper() in TrainerArchetype.__members__:
            self._archetype = TrainerArchetype[archetype.upper()]
        else:
            raise ValueError(f"Invalid TrainerArchetype: {archetype}")

        # Difficulty
        if isinstance(difficulty, DifficultyProfile):
            self._difficulty = difficulty
        elif isinstance(difficulty, str) and difficulty.upper() in DifficultyProfile.__members__:
            self._difficulty = DifficultyProfile[difficulty.upper()]
        else:
            raise ValueError(f"Invalid DifficultyProfile: {difficulty}")

        self._region_id: str = str(region_id).strip().lower()

        # Team & Active Pokemon
        self._team: list[Pokemon] = list(team) if team is not None else []
        self._active_pokemon: Optional[Pokemon] = active_pokemon
        if self._active_pokemon is None and self._team:
            self._active_pokemon = self._team[0]

        # Defeat & Progression Tracking
        self._is_defeated: bool = bool(is_defeated)
        self._defeat_count: int = max(0, int(defeat_count))
        self._rematch_available: bool = bool(rematch_available)

        # Dialogue
        self._dialogue_intro: str = dialogue_intro.strip()
        self._dialogue_defeat: str = dialogue_defeat.strip()
        self._dialogue_victory: str = dialogue_victory.strip()

        # Rewards
        self._reward_items: dict[str, int] = dict(reward_items) if reward_items is not None else {}
        self._reward_claimed: bool = bool(reward_claimed)

        # Battle tactics tracking
        self._last_switch_turn: int = -99
        self._switch_count: int = 0

    # --- Properties ---

    @property
    def trainer_id(self) -> str:
        """Unique identifier for this trainer."""
        return self._trainer_id

    @property
    def unique_id(self) -> str:
        """Alias for trainer_id for battle engine compatibility."""
        return self._trainer_id

    @property
    def name(self) -> str:
        """Trainer's given name."""
        return self._name

    @property
    def title(self) -> str:
        """Full title (e.g. 'Youngster Joey')."""
        return self._title

    @property
    def archetype(self) -> TrainerArchetype:
        """Trainer's thematic character archetype."""
        return self._archetype

    @property
    def difficulty(self) -> DifficultyProfile:
        """Trainer's tactical AI competence profile."""
        return self._difficulty

    @difficulty.setter
    def difficulty(self, value: Union[DifficultyProfile, str]) -> None:
        if isinstance(value, DifficultyProfile):
            self._difficulty = value
        elif isinstance(value, str) and value.upper() in DifficultyProfile.__members__:
            self._difficulty = DifficultyProfile[value.upper()]
        else:
            raise ValueError(f"Invalid DifficultyProfile: {value}")

    @property
    def region_id(self) -> str:
        """World region where this trainer resides."""
        return self._region_id

    @property
    def team(self) -> list[Pokemon]:
        """Ordered list of Pokemon currently on the trainer's team."""
        return list(self._team)

    @team.setter
    def team(self, value: Sequence[Pokemon]) -> None:
        self.set_team(value)

    @property
    def has_team(self) -> bool:
        """Returns True if the trainer has at least one Pokemon on their team."""
        return len(self._team) > 0

    @property
    def active_pokemon(self) -> Optional[Pokemon]:
        """Currently active Pokemon in battle."""
        return self._active_pokemon

    @property
    def is_defeated(self) -> bool:
        """True if the player has previously defeated this trainer."""
        return self._is_defeated

    @property
    def defeat_count(self) -> int:
        """Total number of times this trainer has been defeated."""
        return self._defeat_count

    @property
    def rematch_available(self) -> bool:
        """Whether a rematch challenge is currently available."""
        return self._rematch_available

    @rematch_available.setter
    def rematch_available(self, value: bool) -> None:
        self._rematch_available = bool(value)

    @property
    def dialogue_intro(self) -> str:
        """Dialogue spoken when the battle commences."""
        return self._dialogue_intro

    @property
    def dialogue_defeat(self) -> str:
        """Dialogue spoken when defeated by the player."""
        return self._dialogue_defeat

    @property
    def dialogue_victory(self) -> str:
        """Dialogue spoken if the trainer defeats the player."""
        return self._dialogue_victory

    @property
    def reward_items(self) -> dict[str, int]:
        """Copy of items granted on first defeat."""
        return dict(self._reward_items)

    @property
    def reward_claimed(self) -> bool:
        """Whether the trainer's victory reward has already been claimed."""
        return self._reward_claimed

    @property
    def last_switch_turn(self) -> int:
        """Turn number on which the trainer last switched Pokemon."""
        return self._last_switch_turn

    @last_switch_turn.setter
    def last_switch_turn(self, value: int) -> None:
        self._last_switch_turn = int(value)
        self._switch_count += 1

    @property
    def switch_count(self) -> int:
        """Number of switches performed by this trainer in current battle."""
        return self._switch_count

    # --- Team Management ---

    def set_team(self, team: Sequence[Pokemon]) -> None:
        """
        Sets the trainer's battle team and initializes active Pokemon.
        """
        if not team:
            raise ValueError("Trainer team cannot be empty.")
        for mon in team:
            if not isinstance(mon, Pokemon):
                raise TypeError(f"All team members must be Pokemon instances, got {type(mon).__name__}.")
        self._team = list(team)
        # Set first conscious Pokemon as active, or first member
        conscious = [p for p in self._team if not p.is_fainted]
        self._active_pokemon = conscious[0] if conscious else self._team[0]

    def set_active_pokemon(self, pokemon: Optional[Pokemon]) -> None:
        """
        Sets the trainer's active Pokemon in battle.
        """
        if pokemon is not None and pokemon not in self._team:
            raise ValueError(f"Pokemon '{pokemon.display_name}' is not on trainer '{self._name}'s team.")
        self._active_pokemon = pokemon

    def is_pokemon_owned(self, pokemon: Union[Pokemon, str]) -> bool:
        """
        Returns True if the specified Pokemon belongs to this trainer's team.
        """
        pid = pokemon.unique_id if isinstance(pokemon, Pokemon) else str(pokemon)
        return any(p.unique_id == pid for p in self._team)

    def get_team(self) -> list[Pokemon]:
        """Returns the trainer's team for battle engine duck-typing."""
        return list(self._team)

    def get_all_pokemon(self) -> list[Pokemon]:
        """Returns all Pokemon owned by this trainer for duck-typing."""
        return list(self._team)

    @property
    def conscious_pokemon(self) -> list[Pokemon]:
        """List of all currently conscious (unfainted) team members."""
        return [p for p in self._team if not p.is_fainted]

    def has_conscious_pokemon(self) -> bool:
        """Returns True if the trainer has at least one conscious Pokemon."""
        return any(not p.is_fainted for p in self._team)

    def get_next_conscious_pokemon(self) -> Optional[Pokemon]:
        """
        Returns the next eligible conscious Pokemon that is not currently active,
        or any conscious Pokemon if active is fainted.
        """
        # First preference: conscious teammate that is not current active
        for mon in self._team:
            if not mon.is_fainted and (self._active_pokemon is None or mon.unique_id != self._active_pokemon.unique_id):
                return mon
        # Fallback to any conscious
        for mon in self._team:
            if not mon.is_fainted:
                return mon
        return None

    @property
    def is_team_defeated(self) -> bool:
        """True if all Pokemon on the trainer's team have fainted."""
        return len(self._team) > 0 and all(p.is_fainted for p in self._team)

    def mark_defeated(self) -> None:
        """
        Marks this trainer as defeated and increments defeat counter.
        """
        self._is_defeated = True
        self._defeat_count += 1

    def record_defeat(self) -> None:
        """Alias for mark_defeated for battle completion tracking."""
        self.mark_defeated()

    def reset_battle_state(self) -> None:
        """
        Restores trainer's team to full battle-readiness (heals HP, clears debuffs).
        """
        for mon in self._team:
            mon.heal_full()
        if self._team:
            self._active_pokemon = self._team[0]
        self._last_switch_turn = -99
        self._switch_count = 0

    def claim_rewards(self, player: Optional[Player] = None) -> dict[str, int]:
        """
        Awards one-time victory items to the player's inventory if provided.
        Returns the dictionary of claimed reward items.
        Prevents duplicate claims.
        """
        if self._reward_claimed:
            return {}
        if player is not None and not isinstance(player, Player):
            raise TypeError("player must be a Player instance or None.")

        granted: dict[str, int] = {}
        for item_id, count in self._reward_items.items():
            if count > 0:
                if player is not None and hasattr(player, "inventory"):
                    player.inventory.add_item(item_id, count)
                granted[item_id] = count
        self._reward_claimed = True
        return granted

    # --- Serialization & Persistence ---

    def to_dict(self) -> dict[str, Any]:
        """
        Serializes trainer state and full generated team into a persistent dictionary.
        """
        serialized_team: list[dict[str, Any]] = []
        for mon in self._team:
            mon_record = {
                "unique_id": mon.unique_id,
                "species": mon.species.name,
                "nickname": mon.nickname,
                "level": mon.level,
                "experience": mon.experience,
                "current_hp": mon.current_hp,
                "bond": mon.bond,
                "obedience": mon.obedience,
                "personality": mon.personality.to_dict(),
                "attacks": [atk.name for atk in mon.attacks],
                "trained_stats": mon.trained_stats,
            }
            serialized_team.append(mon_record)

        active_id = self._active_pokemon.unique_id if self._active_pokemon else None

        return {
            "trainer_id": self._trainer_id,
            "name": self._name,
            "title": self._title,
            "archetype": self._archetype.value,
            "difficulty": self._difficulty.value,
            "region_id": self._region_id,
            "is_defeated": self._is_defeated,
            "defeat_count": self._defeat_count,
            "rematch_available": self._rematch_available,
            "dialogue_intro": self._dialogue_intro,
            "dialogue_defeat": self._dialogue_defeat,
            "dialogue_victory": self._dialogue_victory,
            "reward_items": dict(self._reward_items),
            "reward_claimed": self._reward_claimed,
            "active_pokemon_id": active_id,
            "team": serialized_team,
        }

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        species_catalog: Optional[dict[str, PokemonSpecies]] = None,
        attack_catalog: Optional[dict[str, Attack]] = None,
    ) -> "Trainer":
        """
        Reconstructs a Trainer and their persistent team from a dictionary payload.
        """
        from src.data.species import SAMPLE_SPECIES
        from src.data.attacks import SAMPLE_ATTACKS

        sp_cat = species_catalog if species_catalog is not None else SAMPLE_SPECIES
        atk_cat = attack_catalog if attack_catalog is not None else SAMPLE_ATTACKS

        restored_team: list[Pokemon] = []
        for mon_data in data.get("team", []):
            sp_name = mon_data.get("species", "")
            species = sp_cat.get(sp_name)
            if species is None:
                # Case-insensitive lookup
                for k, v in sp_cat.items():
                    if k.lower() == str(sp_name).lower():
                        species = v
                        break
            if species is None:
                raise ValueError(f"Unknown species '{sp_name}' during trainer restoration.")

            # Personality
            pers_data = mon_data.get("personality", {})
            personality = Personality(
                aggression=pers_data.get("aggression", 50),
                curiosity=pers_data.get("curiosity", 50),
                fear=pers_data.get("fear", 50),
                sociability=pers_data.get("sociability", 50),
                loyalty=pers_data.get("loyalty", 50),
                confidence=pers_data.get("confidence", 50),
            )

            # Attacks
            attack_names = mon_data.get("attacks", [])
            restored_attacks: list[Attack] = []
            for a_name in attack_names:
                atk = atk_cat.get(a_name)
                if atk is None:
                    for k, v in atk_cat.items():
                        if k.lower() == str(a_name).lower():
                            atk = v
                            break
                if atk is not None and atk not in restored_attacks:
                    restored_attacks.append(atk)

            mon = Pokemon(
                species=species,
                personality=personality,
                level=mon_data.get("level", 1),
                experience=mon_data.get("experience", 0),
                current_hp=mon_data.get("current_hp"),
                bond=mon_data.get("bond", 0),
                obedience=mon_data.get("obedience", 100),
                unique_id=mon_data.get("unique_id"),
                nickname=mon_data.get("nickname"),
                attacks=restored_attacks,
                trained_stats=mon_data.get("trained_stats"),
            )
            restored_team.append(mon)

        trainer = cls(
            trainer_id=data["trainer_id"],
            name=data["name"],
            title=data.get("title", data["name"]),
            archetype=data.get("archetype", TrainerArchetype.YOUNGSTER.value),
            difficulty=data.get("difficulty", DifficultyProfile.NORMAL.value),
            region_id=data.get("region_id", "starting_meadow"),
            team=restored_team,
            is_defeated=data.get("is_defeated", False),
            defeat_count=data.get("defeat_count", 0),
            rematch_available=data.get("rematch_available", False),
            dialogue_intro=data.get("dialogue_intro", ""),
            dialogue_defeat=data.get("dialogue_defeat", ""),
            dialogue_victory=data.get("dialogue_victory", ""),
            reward_items=data.get("reward_items", {}),
            reward_claimed=data.get("reward_claimed", False),
        )

        active_id = data.get("active_pokemon_id")
        if active_id:
            matching = [p for p in restored_team if p.unique_id == active_id]
            if matching:
                trainer.set_active_pokemon(matching[0])

        return trainer
