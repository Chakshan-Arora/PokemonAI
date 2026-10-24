"""
Habitat and time-based encounter models for wild Pokemon spawning.
Defines TimeOfDay, Rarity, SpawnCandidate, Habitat, SpawnSelectionResult,
and HabitatEncounterResult.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
import math
from typing import Optional, Sequence, Union, Any, TYPE_CHECKING

from src.models.species import PokemonSpecies
from src.models.pokemon import Pokemon

if TYPE_CHECKING:
    from src.models.player import Player
    from src.models.spawn_area import SpawnArea
    from src.models.encounter_manager import WildEncounter


class TimeOfDay(str, Enum):
    """
    Deterministic time periods of a 24-hour cycle.
    """
    MORNING = "morning"  # 05:00 - 09:59
    DAY = "day"          # 10:00 - 16:59
    EVENING = "evening"  # 17:00 - 20:59
    NIGHT = "night"      # 21:00 - 04:59

    @property
    def display_name(self) -> str:
        """Formatted title name."""
        return self.value.title()


class Rarity(str, Enum):
    """
    Relative rarity classifications for wild spawn candidates.
    """
    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    VERY_RARE = "very_rare"
    LEGENDARY = "legendary"

    @property
    def display_name(self) -> str:
        """Formatted title name."""
        return self.value.replace("_", " ").title()

    @property
    def default_weight(self) -> float:
        """Default selection weight associated with this rarity tier."""
        weights = {
            Rarity.COMMON: 50.0,
            Rarity.UNCOMMON: 25.0,
            Rarity.RARE: 10.0,
            Rarity.VERY_RARE: 3.0,
            Rarity.LEGENDARY: 1.0,
        }
        return weights[self]


def get_time_of_day(hour: Union[int, float]) -> TimeOfDay:
    """
    Maps a clock hour [0.0, 24.0) to its corresponding deterministic TimeOfDay period.

    Time boundaries:
      - MORNING : 05:00 <= hour < 10:00
      - DAY     : 10:00 <= hour < 17:00
      - EVENING : 17:00 <= hour < 21:00
      - NIGHT   : 21:00 <= hour < 24.0 OR 0.0 <= hour < 05:00 (including midnight 0.0)

    Args:
        hour: Clock hour as a float or integer in [0.0, 24.0).

    Returns:
        The matching TimeOfDay enum member.

    Raises:
        TypeError: If hour is not a numeric type (or is a boolean).
        ValueError: If hour is outside [0.0, 24.0), NaN, or infinite.
    """
    if not isinstance(hour, (int, float)) or isinstance(hour, bool):
        raise TypeError(f"hour must be a number, got {type(hour).__name__}.")

    if math.isnan(hour) or math.isinf(hour):
        raise ValueError(f"hour must be a finite number, got {hour!r}.")

    hour_val = float(hour)
    if hour_val < 0.0 or hour_val >= 24.0:
        raise ValueError(f"hour must be in range [0.0, 24.0), got {hour_val}.")

    if 5.0 <= hour_val < 10.0:
        return TimeOfDay.MORNING
    elif 10.0 <= hour_val < 17.0:
        return TimeOfDay.DAY
    elif 17.0 <= hour_val < 21.0:
        return TimeOfDay.EVENING
    else:
        # 21.0 <= hour_val < 24.0 OR 0.0 <= hour_val < 5.0
        return TimeOfDay.NIGHT


@dataclass(frozen=True)
class SpawnCandidate:
    """
    Specification for an eligible wild Pokemon candidate in a habitat.

    Attributes:
        species: PokemonSpecies blueprint.
        weight: Relative selection probability weight (must be > 0). If omitted, derived from rarity.
        allowed_times: Tuple of TimeOfDay periods when candidate can appear.
        min_level: Minimum level when spawned (>= 1).
        max_level: Maximum level when spawned (>= min_level).
        rarity: Optional rarity classification.
    """
    species: PokemonSpecies
    weight: Optional[float] = None
    allowed_times: tuple[TimeOfDay, ...] = ()
    min_level: int = 2
    max_level: int = 5
    rarity: Optional[Rarity] = None

    def __post_init__(self) -> None:
        if not isinstance(self.species, PokemonSpecies):
            raise TypeError(f"species must be a PokemonSpecies instance, got {type(self.species).__name__}.")

        if self.rarity is not None and not isinstance(self.rarity, Rarity):
            raise TypeError(f"rarity must be a Rarity enum or None, got {type(self.rarity).__name__}.")

        eff_weight = self.weight
        if eff_weight is None:
            if self.rarity is not None:
                eff_weight = self.rarity.default_weight
            else:
                raise ValueError("SpawnCandidate must provide either 'weight' or 'rarity'.")

        if (
            not isinstance(eff_weight, (int, float))
            or isinstance(eff_weight, bool)
            or math.isnan(eff_weight)
            or math.isinf(eff_weight)
            or eff_weight <= 0.0
        ):
            raise ValueError(f"weight must be a finite positive number (> 0), got {eff_weight!r}.")
        object.__setattr__(self, "weight", float(eff_weight))

        if not self.allowed_times or not isinstance(self.allowed_times, (tuple, list, set)):
            raise ValueError("allowed_times must be a non-empty sequence of TimeOfDay.")

        norm_times: list[TimeOfDay] = []
        for t in self.allowed_times:
            if not isinstance(t, TimeOfDay):
                raise TypeError(f"All items in allowed_times must be TimeOfDay, got {type(t).__name__}.")
            norm_times.append(t)
        object.__setattr__(self, "allowed_times", tuple(norm_times))

        if not isinstance(self.min_level, int) or isinstance(self.min_level, bool) or self.min_level < 1:
            raise ValueError(f"min_level must be an integer >= 1, got {self.min_level}.")

        if not isinstance(self.max_level, int) or isinstance(self.max_level, bool) or self.max_level < self.min_level:
            raise ValueError(f"max_level must be an integer >= min_level ({self.min_level}), got {self.max_level}.")

    def is_eligible_at(self, time_of_day: TimeOfDay) -> bool:
        """Checks if this candidate is eligible during the specified time period."""
        if not isinstance(time_of_day, TimeOfDay):
            return False
        return time_of_day in self.allowed_times


@dataclass(frozen=True)
class Habitat:
    """
    Validated habitat model grouping geographic world regions with wild spawn candidates.

    Attributes:
        habitat_id: Unique string identifier (e.g. 'meadow').
        name: Human-readable display name.
        description: Textual lore/flavor description.
        region_ids: Tuple of associated world-region IDs.
        candidates: Tuple of eligible SpawnCandidate specifications.
    """
    habitat_id: str
    name: str
    description: str
    region_ids: tuple[str, ...]
    candidates: tuple[SpawnCandidate, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.habitat_id, str) or not self.habitat_id.strip():
            raise ValueError("habitat_id must be a non-empty string.")
        object.__setattr__(self, "habitat_id", self.habitat_id.strip().lower())

        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("name must be a non-empty string.")
        object.__setattr__(self, "name", self.name.strip())

        if not isinstance(self.description, str) or not self.description.strip():
            raise ValueError("description must be a non-empty string.")
        object.__setattr__(self, "description", self.description.strip())

        if not isinstance(self.region_ids, (tuple, list, set)):
            raise TypeError("region_ids must be a sequence of string region IDs.")

        norm_regions: list[str] = []
        for rid in self.region_ids:
            if not isinstance(rid, str) or not rid.strip():
                raise ValueError("All region IDs must be non-empty strings.")
            norm_regions.append(rid.strip().lower())
        object.__setattr__(self, "region_ids", tuple(norm_regions))

        if not isinstance(self.candidates, (tuple, list)):
            raise TypeError("candidates must be a sequence of SpawnCandidate instances.")

        norm_candidates: list[SpawnCandidate] = []
        for cand in self.candidates:
            if not isinstance(cand, SpawnCandidate):
                raise TypeError(f"All candidates must be SpawnCandidate instances, got {type(cand).__name__}.")
            norm_candidates.append(cand)
        object.__setattr__(self, "candidates", tuple(norm_candidates))

    def get_eligible_candidates(self, time_of_day: TimeOfDay) -> list[SpawnCandidate]:
        """Returns all spawn candidates eligible during the given time of day."""
        if not isinstance(time_of_day, TimeOfDay):
            raise TypeError(f"time_of_day must be a TimeOfDay enum, got {type(time_of_day).__name__}.")
        return [c for c in self.candidates if c.is_eligible_at(time_of_day)]

    def get_eligible_species(self, time_of_day: TimeOfDay) -> list[PokemonSpecies]:
        """Returns unique PokemonSpecies eligible in this habitat during the given time of day."""
        eligible_candidates = self.get_eligible_candidates(time_of_day)
        seen: set[str] = set()
        species_list: list[PokemonSpecies] = []
        for c in eligible_candidates:
            if c.species.name not in seen:
                seen.add(c.species.name)
                species_list.append(c.species)
        return species_list

    def is_species_eligible(
        self,
        species: Union[PokemonSpecies, str],
        time_of_day: TimeOfDay,
    ) -> bool:
        """Checks whether a specific species is eligible in this habitat at the given time."""
        target_name = species.name if isinstance(species, PokemonSpecies) else str(species).strip()
        for cand in self.get_eligible_candidates(time_of_day):
            if cand.species.name.lower() == target_name.lower():
                return True
        return False


@dataclass(frozen=True)
class SpawnSelectionResult:
    """
    Structured outcome of a habitat-aware spawn selection query.
    """
    success: bool
    habitat_id: Optional[str] = None
    region_id: Optional[str] = None
    time_of_day: Optional[TimeOfDay] = None
    candidate: Optional[SpawnCandidate] = None
    species: Optional[PokemonSpecies] = None
    level: Optional[int] = None
    eligible_count: int = 0
    message: str = ""
    error_type: Optional[str] = None


@dataclass(frozen=True)
class HabitatEncounterResult:
    """
    Structured outcome of triggering a wild encounter through habitat selection.
    """
    success: bool
    encounter: Optional[WildEncounter] = None
    selection_result: Optional[SpawnSelectionResult] = None
    pokemon: Optional[Pokemon] = None
    player: Optional[Player] = None
    event_emitted: bool = False
    event_id: Optional[str] = None
    message: str = ""
    error_type: Optional[str] = None
