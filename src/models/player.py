"""
Player model representing the trainer, their complete Pokemon collection, and active battle team.
"""
import uuid
from typing import Optional, Union, Any, Sequence
from src.models.pokemon import Pokemon
from src.models.inventory import Inventory


class Player:
    """
    Represents a player in the game.
    Manages the player's identity, full Pokemon collection, active team,
    currently active Pokemon, and item inventory.
    """

    def __init__(
        self,
        name: str,
        unique_id: Optional[str] = None,
        max_team_size: int = 6,
        inventory: Optional[Inventory] = None,
        quests: Optional[dict[str, Any]] = None,
        collected_treasures: Optional[set[str]] = None,
        discovered_regions: Optional[set[str]] = None,
        discovered_landmarks: Optional[set[str]] = None,
        wild_action_history: Optional[Sequence[dict[str, Any]]] = None,
    ) -> None:
        if not name or not name.strip():
            raise ValueError("Player name cannot be empty.")

        if not isinstance(max_team_size, int) or isinstance(max_team_size, bool) or max_team_size < 1:
            raise ValueError(f"max_team_size must be a positive integer, got {max_team_size}.")

        self._name: str = name.strip()
        self._unique_id: str = str(unique_id) if unique_id is not None else str(uuid.uuid4())
        self._max_team_size: int = max_team_size

        # Player's personal item inventory (independent instance per player)
        self._inventory: Inventory = inventory if inventory is not None else Inventory()

        # Player's quest progress dictionary mapping quest_id -> QuestProgress
        self._quests: dict[str, Any] = dict(quests) if quests is not None else {}

        # Set of collected one-time treasure IDs
        self._collected_treasures: set[str] = (
            {str(t).strip().lower() for t in collected_treasures}
            if collected_treasures is not None
            else set()
        )

        # Set of discovered world region IDs
        self._discovered_regions: set[str] = (
            {str(r).strip().lower() for r in discovered_regions}
            if discovered_regions is not None
            else set()
        )

        # Set of discovered landmark IDs
        self._discovered_landmarks: set[str] = (
            {str(l).strip().lower() for l in discovered_landmarks}
            if discovered_landmarks is not None
            else set()
        )

        # History of recent interactions with wild Pokemon
        self._wild_action_history: list[dict[str, Any]] = (
            [dict(item) for item in wild_action_history]
            if wild_action_history is not None
            else []
        )

        # Collection of all owned Pokemon, mapped by unique_id for O(1) lookup
        self._collection: dict[str, Pokemon] = {}

        # Ordered list of Pokemon selected for active team use
        self._team: list[Pokemon] = []

        # Reference to the single active Pokemon
        self._active_pokemon: Optional[Pokemon] = None

    # --- Properties ---

    @property
    def inventory(self) -> Inventory:
        """The player's item inventory."""
        return self._inventory

    @property
    def quests(self) -> dict[str, Any]:
        """Dictionary of quest progress tracked for this player."""
        return self._quests

    def get_quest(self, quest_id: str) -> Optional[Any]:
        """Returns the QuestProgress for the given quest ID, or None if not tracked."""
        if not isinstance(quest_id, str):
            return None
        return self._quests.get(quest_id.strip().lower())

    def has_quest(self, quest_id: str) -> bool:
        """Checks if a quest is currently tracked by this player."""
        if not isinstance(quest_id, str):
            return False
        return quest_id.strip().lower() in self._quests

    def is_quest_completed(self, quest_id: str) -> bool:
        """Checks if the specified quest is tracked and marked completed."""
        q = self.get_quest(quest_id)
        return bool(q.is_completed) if q is not None else False

    def is_quest_active(self, quest_id: str) -> bool:
        """Checks if the specified quest is tracked and actively in progress."""
        q = self.get_quest(quest_id)
        if q is None:
            return False
        status_val = getattr(q, "status", None)
        status_name = getattr(status_val, "name", str(status_val))
        return status_name.upper() == "ACTIVE" and not bool(q.is_completed)

    @property
    def collected_treasures(self) -> set[str]:
        """Set of collected one-time treasure IDs for this player."""
        return self._collected_treasures

    def is_treasure_collected(self, treasure_id: str) -> bool:
        """Checks if a one-time treasure has already been collected."""
        if not isinstance(treasure_id, str):
            return False
        return treasure_id.strip().lower() in self._collected_treasures

    def mark_treasure_collected(self, treasure_id: str) -> None:
        """Records that a one-time treasure has been collected."""
        if isinstance(treasure_id, str) and treasure_id.strip():
            self._collected_treasures.add(treasure_id.strip().lower())

    @property
    def discovered_regions(self) -> set[str]:
        """Set of discovered region IDs for this player."""
        return self._discovered_regions

    def is_region_discovered(self, region_id: str) -> bool:
        """Checks if a world region has been discovered by this player."""
        if not isinstance(region_id, str):
            return False
        return region_id.strip().lower() in self._discovered_regions

    def mark_region_discovered(self, region_id: str) -> None:
        """Records that a world region has been discovered."""
        if isinstance(region_id, str) and region_id.strip():
            self._discovered_regions.add(region_id.strip().lower())

    @property
    def discovered_landmarks(self) -> set[str]:
        """Set of discovered landmark IDs for this player."""
        return self._discovered_landmarks

    def is_landmark_discovered(self, landmark_id: str) -> bool:
        """Checks if a world landmark has been discovered by this player."""
        if not isinstance(landmark_id, str):
            return False
        return landmark_id.strip().lower() in self._discovered_landmarks

    def mark_landmark_discovered(self, landmark_id: str) -> None:
        """Records that a world landmark has been discovered."""
        if isinstance(landmark_id, str) and landmark_id.strip():
            self._discovered_landmarks.add(landmark_id.strip().lower())

    @property
    def wild_action_history(self) -> list[dict[str, Any]]:
        """List of recorded historical actions during wild encounters."""
        return [dict(item) for item in self._wild_action_history]

    def record_wild_action(
        self,
        action: str,
        is_aggressive: bool = False,
        is_peaceful: bool = False,
        species_name: Optional[str] = None,
        outcome: Optional[str] = None,
        max_history: int = 30,
    ) -> None:
        """Records an action or outcome during a wild encounter."""
        entry = {
            "action": str(action).strip().lower(),
            "is_aggressive": bool(is_aggressive),
            "is_peaceful": bool(is_peaceful),
            "species_name": str(species_name) if species_name else None,
            "outcome": str(outcome) if outcome else None,
        }
        self._wild_action_history.append(entry)
        if len(self._wild_action_history) > max_history:
            self._wild_action_history = self._wild_action_history[-max_history:]

    def get_behavior_profile(self, window_size: int = 10):
        """Classifies the player's demeanor using recent wild interactions."""
        from src.models.player_behavior import PlayerBehaviorTracker
        return PlayerBehaviorTracker.classify_behavior(self._wild_action_history, window_size=window_size)

    @property
    def behavior_profile(self):
        """Current behavior profile of the player towards wild Pokemon."""
        return self.get_behavior_profile(window_size=10)

    @property
    def unique_id(self) -> str:
        """Unique UUID identifier for this player."""
        return self._unique_id

    @property
    def name(self) -> str:
        """Player's display name."""
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        if not value or not value.strip():
            raise ValueError("Player name cannot be empty.")
        self._name = value.strip()

    @property
    def max_team_size(self) -> int:
        """Maximum number of Pokemon allowed on the team."""
        return self._max_team_size

    @property
    def active_pokemon(self) -> Optional[Pokemon]:
        """Currently active Pokemon, or None if none selected."""
        return self._active_pokemon

    @active_pokemon.setter
    def active_pokemon(self, pokemon: Optional[Pokemon]) -> None:
        self.set_active_pokemon(pokemon)

    @property
    def collection(self) -> list[Pokemon]:
        """List of all owned Pokemon in the collection."""
        return self.get_all_pokemon()

    @property
    def team(self) -> list[Pokemon]:
        """List of Pokemon currently on the team."""
        return self.get_team()

    # --- Collection Management ---

    def add_pokemon(self, pokemon: Pokemon) -> None:
        """
        Adds a Pokemon to the player's collection.
        Rejects duplicates and non-Pokemon types.
        """
        if not isinstance(pokemon, Pokemon):
            raise TypeError(f"Expected Pokemon instance, got {type(pokemon).__name__}.")

        if pokemon.unique_id in self._collection:
            raise ValueError(
                f"Pokemon '{pokemon.display_name}' (ID: {pokemon.unique_id}) is already in the collection."
            )

        self._collection[pokemon.unique_id] = pokemon

    def remove_pokemon(self, pokemon: Union[Pokemon, str]) -> Pokemon:
        """
        Removes a Pokemon from the player's collection by instance or unique ID.
        Also removes the Pokemon from the team and clears active status if applicable.
        """
        pokemon_id = pokemon.unique_id if isinstance(pokemon, Pokemon) else str(pokemon)

        if pokemon_id not in self._collection:
            raise ValueError(f"Pokemon with ID '{pokemon_id}' is not in the player's collection.")

        removed = self._collection.pop(pokemon_id)

        # Clean up from team if present
        if removed in self._team:
            self._team.remove(removed)

        # Clear active status if the removed Pokemon was active
        if self._active_pokemon is removed:
            self._active_pokemon = None

        return removed

    def get_pokemon_by_id(self, pokemon_id: str) -> Optional[Pokemon]:
        """
        Retrieves an owned Pokemon by its unique ID.
        Returns None if not found in collection.
        """
        return self._collection.get(str(pokemon_id))

    def get_all_pokemon(self) -> list[Pokemon]:
        """Returns a list of all Pokemon currently owned by the player."""
        return list(self._collection.values())

    def is_pokemon_owned(self, pokemon: Union[Pokemon, str]) -> bool:
        """Checks whether a Pokemon (or its unique ID) belongs to the player's collection."""
        pokemon_id = pokemon.unique_id if isinstance(pokemon, Pokemon) else str(pokemon)
        return pokemon_id in self._collection

    def has_pokemon(self, pokemon: Union[Pokemon, str]) -> bool:
        """Alias for is_pokemon_owned."""
        return self.is_pokemon_owned(pokemon)

    # --- Active Pokemon Management ---

    def set_active_pokemon(self, pokemon: Optional[Pokemon]) -> None:
        """
        Sets the player's active Pokemon.
        The Pokemon must already be part of the player's collection.
        Passing None clears the active Pokemon.
        """
        if pokemon is None:
            self._active_pokemon = None
            return

        if not isinstance(pokemon, Pokemon):
            raise TypeError(f"Expected Pokemon instance, got {type(pokemon).__name__}.")

        if not self.is_pokemon_owned(pokemon):
            raise ValueError(
                f"Pokemon '{pokemon.display_name}' (ID: {pokemon.unique_id}) cannot become active "
                "because it is not in the player's collection."
            )

        self._active_pokemon = pokemon

    def get_active_pokemon(self) -> Optional[Pokemon]:
        """Returns the currently active Pokemon, or None if none is active."""
        return self._active_pokemon

    # --- Team Management ---

    def add_to_team(self, pokemon: Pokemon) -> None:
        """
        Adds an owned Pokemon to the active team.
        Enforces ownership, uniqueness on team, and maximum team size.
        """
        if not isinstance(pokemon, Pokemon):
            raise TypeError(f"Expected Pokemon instance, got {type(pokemon).__name__}.")

        if not self.is_pokemon_owned(pokemon):
            raise ValueError(
                f"Cannot add '{pokemon.display_name}' to team: Pokemon must be owned first."
            )

        if self.is_on_team(pokemon):
            raise ValueError(
                f"Pokemon '{pokemon.display_name}' (ID: {pokemon.unique_id}) is already on the team."
            )

        if len(self._team) >= self._max_team_size:
            raise ValueError(
                f"Cannot add '{pokemon.display_name}' to team: team is full (maximum {self._max_team_size})."
            )

        self._team.append(pokemon)

    def remove_from_team(self, pokemon: Pokemon) -> Pokemon:
        """
        Removes a Pokemon from the active team.
        If the removed Pokemon was the active Pokemon, clears active status.
        """
        if not isinstance(pokemon, Pokemon):
            raise TypeError(f"Expected Pokemon instance, got {type(pokemon).__name__}.")

        if not self.is_on_team(pokemon):
            raise ValueError(
                f"Pokemon '{pokemon.display_name}' (ID: {pokemon.unique_id}) is not on the team."
            )

        self._team.remove(pokemon)

        # Clear active Pokemon reference if the removed team member was active
        if self._active_pokemon is pokemon:
            self._active_pokemon = None

        return pokemon

    def swap_team_member(
        self,
        team_pokemon: Union[Pokemon, str],
        collection_pokemon: Union[Pokemon, str],
    ) -> tuple[Pokemon, Pokemon]:
        """
        Swaps an active team member with an owned Pokemon stored in the collection.
        Preserves both Pokemon in the player's collection.
        Preserves team ordering by replacing the team member in-place.
        Updates active Pokemon reference safely if the swapped team member was active.

        Args:
            team_pokemon: Pokemon instance or unique ID currently on the active team.
            collection_pokemon: Pokemon instance or unique ID owned in collection (not on team).

        Returns:
            A tuple of (swapped_out_pokemon, swapped_in_pokemon).

        Raises:
            TypeError: If arguments are invalid types.
            ValueError: If team_pokemon is not on team, collection_pokemon is not owned,
                        or collection_pokemon is already on the team.
        """
        if isinstance(team_pokemon, str):
            mon_team = self.get_pokemon_by_id(team_pokemon)
            if mon_team is None:
                raise ValueError(f"Pokemon with ID '{team_pokemon}' is not owned by the player.")
        elif isinstance(team_pokemon, Pokemon):
            mon_team = team_pokemon
        else:
            raise TypeError(f"Expected Pokemon or str for team_pokemon, got {type(team_pokemon).__name__}.")

        if isinstance(collection_pokemon, str):
            mon_col = self.get_pokemon_by_id(collection_pokemon)
            if mon_col is None:
                raise ValueError(f"Pokemon with ID '{collection_pokemon}' is not owned by the player.")
        elif isinstance(collection_pokemon, Pokemon):
            mon_col = collection_pokemon
        else:
            raise TypeError(f"Expected Pokemon or str for collection_pokemon, got {type(collection_pokemon).__name__}.")

        if not self.is_on_team(mon_team):
            raise ValueError(
                f"Pokemon '{mon_team.display_name}' (ID: {mon_team.unique_id}) is not on the active team."
            )

        if not self.is_pokemon_owned(mon_col):
            raise ValueError(
                f"Pokemon '{mon_col.display_name}' (ID: {mon_col.unique_id}) must be owned to join the team."
            )

        if self.is_on_team(mon_col):
            raise ValueError(
                f"Pokemon '{mon_col.display_name}' (ID: {mon_col.unique_id}) is already on the active team."
            )

        idx = self._team.index(mon_team)
        self._team[idx] = mon_col

        if self._active_pokemon is mon_team:
            if not mon_col.is_fainted:
                self._active_pokemon = mon_col
            else:
                first_conscious = next((p for p in self._team if not p.is_fainted), None)
                self._active_pokemon = first_conscious

        return (mon_team, mon_col)

    def get_team(self) -> list[Pokemon]:
        """Returns a copy of the list of Pokemon on the player's active team."""
        return list(self._team)

    def is_on_team(self, pokemon: Pokemon) -> bool:
        """Checks if a Pokemon is currently on the player's active team."""
        return pokemon in self._team

    # --- Pythonic helpers ---

    def __contains__(self, pokemon: Union[Pokemon, str]) -> bool:
        """Allows using 'pokemon in player' to check ownership."""
        return self.is_pokemon_owned(pokemon)

    def __repr__(self) -> str:
        active_str = self._active_pokemon.display_name if self._active_pokemon else "None"
        return (
            f"Player(id={self._unique_id[:8]}..., name='{self._name}', "
            f"collection_size={len(self._collection)}, team_size={len(self._team)}/{self._max_team_size}, "
            f"active={active_str})"
        )
