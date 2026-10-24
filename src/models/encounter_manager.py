"""
Encounter manager evaluating proximity and area conditions for wild Pokemon encounters.
"""
import math
import uuid
from dataclasses import dataclass
from typing import Optional, Sequence, Union, TYPE_CHECKING
from src.models.pokemon import Pokemon
from src.models.spawn_area import SpawnArea
from src.models.spawn_manager import SpawnManager
from src.models.player import Player

if TYPE_CHECKING:
    from src.models.quest_manager import QuestManager


class WildEncounter:
    """
    Represents an active wild Pokemon encounter session.
    Tracks participants, spawn area context, and completion state.
    """

    def __init__(
        self,
        player: Player,
        pokemon: Pokemon,
        area: Optional[SpawnArea] = None,
        encounter_id: Optional[str] = None,
        region_id: Optional[str] = None,
    ) -> None:
        if not isinstance(player, Player):
            raise TypeError(f"Expected Player instance, got {type(player).__name__}.")
        if not isinstance(pokemon, Pokemon):
            raise TypeError(f"Expected Pokemon instance, got {type(pokemon).__name__}.")
        if area is not None and not isinstance(area, SpawnArea):
            raise TypeError(f"Expected SpawnArea instance or None, got {type(area).__name__}.")

        self._encounter_id = str(encounter_id) if encounter_id is not None else str(uuid.uuid4())
        self._player = player
        self._pokemon = pokemon
        self._area = area
        if region_id is not None:
            if not isinstance(region_id, str) or not region_id.strip():
                raise ValueError("region_id must be a non-empty string or None.")
            self._region_id: Optional[str] = region_id.strip().lower()
        elif area is not None and getattr(area, "region_id", None) is not None:
            self._region_id = str(area.region_id).strip().lower()
        else:
            self._region_id = None
        self._is_active = True
        self._is_resolved = False
        self._resolution_reason: Optional[str] = None

    @property
    def encounter_id(self) -> str:
        """Unique UUID identifier for this encounter session."""
        return self._encounter_id

    @property
    def player(self) -> Player:
        """Player participating in this encounter."""
        return self._player

    @property
    def pokemon(self) -> Pokemon:
        """Wild Pokemon encountered."""
        return self._pokemon

    @property
    def area(self) -> Optional[SpawnArea]:
        """SpawnArea where the encounter takes place, if applicable."""
        return self._area

    @property
    def region_id(self) -> Optional[str]:
        """Region identifier where this encounter takes place, if known."""
        if self._region_id is not None:
            return self._region_id
        if self._area is not None and getattr(self._area, "region_id", None) is not None:
            return str(self._area.region_id).strip().lower()
        return None

    @property
    def is_active(self) -> bool:
        """True if the encounter is ongoing and can receive actions."""
        return self._is_active

    @property
    def is_resolved(self) -> bool:
        """True if the encounter has ended (captured, fled, defeated, etc.)."""
        return self._is_resolved

    @property
    def resolution_reason(self) -> Optional[str]:
        """Description of how the encounter concluded."""
        return self._resolution_reason

    def resolve(self, reason: str = "Resolved") -> None:
        """
        Concludes the encounter. Once resolved, no further actions (like capture)
        can be performed on this encounter session.
        """
        if self._is_resolved:
            raise RuntimeError(f"Encounter is already resolved: {self._resolution_reason}.")
        self._is_active = False
        self._is_resolved = True
        self._resolution_reason = reason

    def __repr__(self) -> str:
        return (
            f"WildEncounter(id={self._encounter_id[:8]}..., "
            f"player='{self._player.name}', pokemon='{self._pokemon.display_name}', "
            f"region='{self.region_id}', "
            f"active={self._is_active}, resolved={self._is_resolved})"
        )


@dataclass(frozen=True)
class EncounterResult:
    """
    Result of evaluating whether a wild Pokemon encounter can occur.
    """
    can_encounter: bool
    reason: str
    distance: float
    pokemon: Optional[Pokemon] = None
    area: Optional[SpawnArea] = None
    region_id: Optional[str] = None

    def start_encounter(self, player: Player) -> WildEncounter:
        """
        Starts a WildEncounter session from this result if permitted.
        """
        if not self.can_encounter or self.pokemon is None:
            raise RuntimeError(f"Cannot start encounter: {self.reason}")
        reg_id = self.region_id
        if reg_id is None and self.area is not None:
            reg_id = getattr(self.area, "region_id", None)
        return WildEncounter(player=player, pokemon=self.pokemon, area=self.area, region_id=reg_id)


class EncounterManager:
    """
    Evaluates encounter eligibility between a player and a wild Pokemon
    based on world coordinates, area configuration, and active population status.
    Manages active encounter tracking per player.
    """

    def __init__(
        self,
        spawn_manager: Optional[SpawnManager] = None,
        quest_manager: Optional["QuestManager"] = None,
    ) -> None:
        self._active_encounters: dict[str, WildEncounter] = {}
        self._spawn_manager: Optional[SpawnManager] = spawn_manager
        self._quest_manager: Optional["QuestManager"] = quest_manager

    @property
    def spawn_manager(self) -> Optional[SpawnManager]:
        """Associated SpawnManager instance for area population synchronization."""
        return self._spawn_manager

    @spawn_manager.setter
    def spawn_manager(self, sm: Optional[SpawnManager]) -> None:
        if sm is not None and not isinstance(sm, SpawnManager):
            raise TypeError(f"Expected SpawnManager instance or None, got {type(sm).__name__}.")
        self._spawn_manager = sm

    @property
    def quest_manager(self) -> Optional["QuestManager"]:
        """Associated QuestManager instance for wild encounter quest events."""
        return self._quest_manager

    @quest_manager.setter
    def quest_manager(self, qm: Optional["QuestManager"]) -> None:
        self._quest_manager = qm

    @staticmethod
    def calculate_distance(pos1: Sequence[float], pos2: Sequence[float]) -> float:
        """
        Calculates the Euclidean distance between two coordinate tuples.
        Works for 2D, 3D, or any matching dimensions.
        """
        if len(pos1) != len(pos2):
            raise ValueError(f"Position dimension mismatch: {len(pos1)} vs {len(pos2)}.")
        if len(pos1) == 0:
            raise ValueError("Position coordinates cannot be empty.")
        return math.sqrt(sum((float(a) - float(b)) ** 2 for a, b in zip(pos1, pos2)))

    def check_encounter(
        self,
        player_position: Sequence[float],
        pokemon_position: Sequence[float],
        pokemon: Pokemon,
        area: SpawnArea,
        is_active: bool = True,
    ) -> EncounterResult:
        """
        Checks whether the player can encounter the specified wild Pokemon.
        Verifies:
        1. SpawnArea is enabled.
        2. Pokemon species is permitted in the SpawnArea.
        3. Pokemon is currently active in the area.
        4. Player is within the area's encounter_radius.
        """
        if not isinstance(pokemon, Pokemon):
            raise TypeError(f"Expected Pokemon instance, got {type(pokemon).__name__}.")
        if not isinstance(area, SpawnArea):
            raise TypeError(f"Expected SpawnArea instance, got {type(area).__name__}.")

        dist = self.calculate_distance(player_position, pokemon_position)

        if not area.enabled:
            return EncounterResult(
                can_encounter=False,
                reason=f"Spawn area '{area.name}' is disabled.",
                distance=dist,
                pokemon=pokemon,
                area=area,
            )

        if not area.is_species_allowed(pokemon.species):
            return EncounterResult(
                can_encounter=False,
                reason=f"Species '{pokemon.species.name}' is not permitted in area '{area.name}'.",
                distance=dist,
                pokemon=pokemon,
                area=area,
            )

        if not is_active:
            return EncounterResult(
                can_encounter=False,
                reason=f"Pokemon '{pokemon.display_name}' (ID: {pokemon.unique_id}) is no longer active in area '{area.name}'.",
                distance=dist,
                pokemon=pokemon,
                area=area,
            )

        if dist > area.encounter_radius:
            return EncounterResult(
                can_encounter=False,
                reason=f"Player is outside encounter radius ({dist:.2f}m > {area.encounter_radius:.2f}m).",
                distance=dist,
                pokemon=pokemon,
                area=area,
            )

        return EncounterResult(
            can_encounter=True,
            reason="Encounter permitted.",
            distance=dist,
            pokemon=pokemon,
            area=area,
        )

    def check_encounter_with_manager(
        self,
        spawn_manager: SpawnManager,
        area_id: str,
        player_position: Sequence[float],
        pokemon: Pokemon,
        pokemon_position: Optional[Sequence[float]] = None,
    ) -> EncounterResult:
        """
        Convenience method verifying encounter conditions directly against a SpawnManager.
        Looks up registered area, active population status, and recorded position.
        """
        if not isinstance(spawn_manager, SpawnManager):
            raise TypeError(f"Expected SpawnManager instance, got {type(spawn_manager).__name__}.")

        area = spawn_manager.get_area(area_id)
        if area is None:
            raise KeyError(f"Spawn area '{area_id}' is not registered.")

        # Determine pokemon position
        if pokemon_position is None:
            pos = spawn_manager.get_pokemon_position(pokemon)
            if pos is None:
                raise ValueError(
                    f"No position provided and no recorded position found for Pokemon ID '{pokemon.unique_id}'."
                )
            pokemon_position = pos

        is_active = spawn_manager.is_pokemon_active(area_id, pokemon)
        return self.check_encounter(
            player_position=player_position,
            pokemon_position=pokemon_position,
            pokemon=pokemon,
            area=area,
            is_active=is_active,
        )

    def start_encounter(
        self,
        player: Player,
        pokemon: Pokemon,
        area: Optional[SpawnArea] = None,
        region_id: Optional[str] = None,
    ) -> WildEncounter:
        """
        Starts an active WildEncounter session between a player and a wild Pokemon.
        Enforces that a player cannot be placed into a new encounter while an active
        encounter is already ongoing.
        """
        if not isinstance(player, Player):
            raise TypeError(f"Expected Player instance, got {type(player).__name__}.")

        existing = self.get_active_encounter(player)
        if existing is not None and existing.is_active:
            raise RuntimeError(
                f"Player '{player.name}' (ID: {player.unique_id}) already has an active encounter ({existing.encounter_id})."
            )

        eff_region_id = region_id or (getattr(area, "region_id", None) if area else None)
        encounter = WildEncounter(player=player, pokemon=pokemon, area=area, region_id=eff_region_id)
        self._active_encounters[player.unique_id] = encounter

        if self._quest_manager is not None:
            habitat_id = getattr(area, "habitat_id", None) if area is not None else None
            enc_evt_id = f"quest_evt_encounter_{encounter.encounter_id}_{pokemon.unique_id}"
            self._quest_manager.record_encounter(
                player=player,
                species_name=pokemon.species.name,
                habitat_id=habitat_id,
                region_id=eff_region_id,
                count=1,
                event_id=enc_evt_id,
            )

        return encounter

    def get_active_encounter(self, player: Union[Player, str]) -> Optional[WildEncounter]:
        """
        Retrieves the active encounter session for a player, if any.
        Cleans up and returns None if the encounter has already concluded.
        """
        p_id = player.unique_id if isinstance(player, Player) else str(player)
        enc = self._active_encounters.get(p_id)
        if enc is not None:
            if not enc.is_active or enc.is_resolved:
                self._active_encounters.pop(p_id, None)
                return None
            return enc
        return None

    def has_active_encounter(self, player: Union[Player, str]) -> bool:
        """Returns True if the player currently has an active, unresolved encounter."""
        return self.get_active_encounter(player) is not None

    def resolve_active_encounter(
        self,
        player: Union[Player, str],
        reason: str = "Resolved",
        spawn_manager: Optional[SpawnManager] = None,
    ) -> Optional[WildEncounter]:
        """
        Resolves and removes the player's active encounter session.
        Returns the resolved WildEncounter instance, or None if no active encounter existed.
        If a SpawnManager is associated (or passed in) and the encounter has an associated area,
        despawns the Pokemon from the spawn area population exactly once.
        """
        enc = self.get_active_encounter(player)
        if enc is not None:
            enc.resolve(reason=reason)
            p_id = player.unique_id if isinstance(player, Player) else str(player)
            self._active_encounters.pop(p_id, None)

            effective_sm = spawn_manager if spawn_manager is not None else self._spawn_manager
            if effective_sm is not None and enc.area is not None:
                effective_sm.despawn_pokemon(enc.area.area_id, enc.pokemon)

            return enc
        return None

