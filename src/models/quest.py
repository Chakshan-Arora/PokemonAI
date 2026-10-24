"""
Quest and Objective models for player progression and mission tracking.
Defines QuestStatus, ObjectiveType, QuestEventType, immutable quest definitions,
and mutable player-specific runtime progress tracking.
"""
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Any


class QuestStatus(Enum):
    """
    Lifecycle status of a quest for a specific player.
    """
    LOCKED = "locked"        # Prerequisites not yet met
    AVAILABLE = "available"  # Prerequisites met, ready to accept
    ACTIVE = "active"        # Accepted and actively tracking progress
    COMPLETED = "completed"  # All objectives fulfilled

    @property
    def display_name(self) -> str:
        return self.value.title()


class ObjectiveType(Enum):
    """
    Supported objective categories.
    """
    CAPTURE_SPECIES = "capture_species"      # Capture a specific Pokémon species
    CAPTURE_ANY = "capture_any"              # Capture any wild Pokémon
    DEFEAT_SPECIES = "defeat_species"        # Defeat a specific Pokémon species
    DEFEAT_ANY = "defeat_any"                # Defeat any Pokémon in battle
    REACH_LEVEL = "reach_level"              # Reach target level on any Pokémon
    OWN_SPECIES = "own_species"              # Own a specific Pokémon species in collection
    COLLECT_ITEM = "collect_item"            # Collect or possess a specific item
    DISCOVER_REGION = "discover_region"      # Discover a specific or any region
    DISCOVER_LANDMARK = "discover_landmark"  # Discover a specific or any landmark
    DISCOVER_LOCATIONS = "discover_locations"# Discover a count of distinct locations
    ENCOUNTER_SPECIES = "encounter_species"  # Encounter a specific Pokémon species
    ENCOUNTER_ANY = "encounter_any"          # Encounter any wild Pokémon
    INTERACT_OBJECT = "interact_object"      # Interact with a world object / interactable

    @property
    def display_name(self) -> str:
        return self.value.replace("_", " ").title()


class QuestEventType(Enum):
    """
    Event types emitted during gameplay to advance quest objectives.
    """
    POKEMON_CAPTURED = "pokemon_captured"
    POKEMON_DEFEATED = "pokemon_defeated"
    POKEMON_LEVEL_UP = "pokemon_level_up"
    POKEMON_COLLECTED = "pokemon_collected"
    ITEM_COLLECTED = "item_collected"
    ITEM_CONSUMED = "item_consumed"
    REGION_DISCOVERED = "region_discovered"
    LANDMARK_DISCOVERED = "landmark_discovered"
    POKEMON_ENCOUNTERED = "pokemon_encountered"
    OBJECT_INTERACTED = "object_interacted"


@dataclass(frozen=True)
class QuestEvent:
    """
    Typed event passed to QuestManager to evaluate and update objective progress.
    """
    event_type: QuestEventType
    payload: dict[str, Any] = field(default_factory=dict)
    event_id: Optional[str] = None  # Optional identifier for deduplication


@dataclass(frozen=True)
class QuestObjective:
    """
    Immutable blueprint for a single objective within a quest definition.

    Attributes:
        objective_id: Unique string identifier for this objective.
        objective_type: Category of objective (ObjectiveType).
        description: Human-readable objective description.
        target_count: Target threshold (e.g. 1 capture, level 5, 2 items).
        target_species: Species name required for species-specific objectives.
        target_item: Item identifier required for item-collection objectives.
        target_region: Region identifier for region discovery objectives.
        target_landmark: Landmark identifier for landmark discovery objectives.
    """
    objective_id: str
    objective_type: ObjectiveType
    description: str
    target_count: int = 1
    target_species: Optional[str] = None
    target_item: Optional[str] = None
    target_region: Optional[str] = None
    target_landmark: Optional[str] = None
    target_object: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.objective_id, str) or not self.objective_id.strip():
            raise ValueError("objective_id must be a non-empty string.")

        if not isinstance(self.objective_type, ObjectiveType):
            raise TypeError(f"objective_type must be an ObjectiveType enum, got {type(self.objective_type).__name__}.")

        if not isinstance(self.description, str) or not self.description.strip():
            raise ValueError("description must be a non-empty string.")

        if not isinstance(self.target_count, int) or isinstance(self.target_count, bool) or self.target_count < 1:
            raise ValueError(f"target_count must be an integer >= 1, got {self.target_count}.")

        # Species requirement check
        if self.objective_type in (ObjectiveType.CAPTURE_SPECIES, ObjectiveType.DEFEAT_SPECIES, ObjectiveType.OWN_SPECIES):
            if not isinstance(self.target_species, str) or not self.target_species.strip():
                raise ValueError(f"Objective '{self.objective_id}' of type {self.objective_type.value} requires a non-empty target_species.")

        # Item requirement check
        if self.objective_type == ObjectiveType.COLLECT_ITEM:
            if not isinstance(self.target_item, str) or not self.target_item.strip():
                raise ValueError(f"Objective '{self.objective_id}' of type COLLECT_ITEM requires a non-empty target_item.")

        # Level requirement check
        if self.objective_type == ObjectiveType.REACH_LEVEL:
            if self.target_count > 100:
                raise ValueError(f"target_count for REACH_LEVEL cannot exceed maximum level 100, got {self.target_count}.")

        # Region requirement check
        if self.target_region is not None:
            if not isinstance(self.target_region, str) or not self.target_region.strip():
                raise ValueError(f"Objective '{self.objective_id}' requires a non-empty target_region if specified.")

        # Landmark requirement check
        if self.objective_type == ObjectiveType.DISCOVER_LANDMARK and self.target_landmark is not None:
            if not isinstance(self.target_landmark, str) or not self.target_landmark.strip():
                raise ValueError(f"Objective '{self.objective_id}' requires a non-empty target_landmark if specified.")

        # Object requirement check
        if self.target_object is not None:
            if not isinstance(self.target_object, str) or not self.target_object.strip():
                raise ValueError(f"Objective '{self.objective_id}' requires a non-empty target_object if specified.")


@dataclass(frozen=True)
class QuestChoiceOption:
    """
    An individual selectable option within a QuestChoice.

    Attributes:
        option_id: Unique lowercase string identifier for this option.
        text: Display title/name of the option.
        description: Narrative explanation of the option and its implications.
        objectives: Branch-specific objectives activated when this option is chosen.
        rewards: Optional additional item rewards granted upon quest completion if this option was chosen.
    """
    option_id: str
    text: str
    description: str = ""
    objectives: tuple[QuestObjective, ...] = ()
    rewards: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.option_id, str) or not self.option_id.strip():
            raise ValueError("option_id must be a non-empty string.")
        object.__setattr__(self, "option_id", self.option_id.strip().lower())

        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError("text must be a non-empty string.")
        object.__setattr__(self, "text", self.text.strip())

        if not isinstance(self.description, str):
            raise TypeError("description must be a string.")
        object.__setattr__(self, "description", self.description.strip())

        if not isinstance(self.objectives, (tuple, list)):
            raise TypeError("objectives must be a tuple or list of QuestObjective instances.")
        for obj in self.objectives:
            if not isinstance(obj, QuestObjective):
                raise TypeError(f"All branch objectives must be QuestObjective instances, got {type(obj).__name__}.")
        object.__setattr__(self, "objectives", tuple(self.objectives))

        # Check unique branch objective IDs within option
        branch_ids = [o.objective_id for o in self.objectives]
        if len(branch_ids) != len(set(branch_ids)):
            raise ValueError(f"Duplicate branch objective IDs found in option '{self.option_id}': {branch_ids}.")

        if not isinstance(self.rewards, dict):
            raise TypeError("rewards must be a dictionary mapping item_id to quantity.")
        for item_id, qty in self.rewards.items():
            if not isinstance(item_id, str) or not item_id.strip():
                raise ValueError(f"Reward item_id must be a non-empty string, got {item_id!r}.")
            if not isinstance(qty, int) or isinstance(qty, bool) or qty <= 0:
                raise ValueError(f"Reward quantity for item '{item_id}' must be a positive integer, got {qty}.")


@dataclass(frozen=True)
class QuestChoice:
    """
    A decision point within a quest presenting two or more selectable branches.

    Attributes:
        choice_id: Unique lowercase string identifier for this choice.
        prompt: Question or prompt presented to the player.
        options: Ordered tuple of selectable QuestChoiceOption blueprints.
        prerequisite_objectives: Optional objective IDs that must be completed before this choice is offered.
    """
    choice_id: str
    prompt: str
    options: tuple[QuestChoiceOption, ...]
    prerequisite_objectives: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.choice_id, str) or not self.choice_id.strip():
            raise ValueError("choice_id must be a non-empty string.")
        object.__setattr__(self, "choice_id", self.choice_id.strip().lower())

        if not isinstance(self.prompt, str) or not self.prompt.strip():
            raise ValueError("prompt must be a non-empty string.")
        object.__setattr__(self, "prompt", self.prompt.strip())

        if not isinstance(self.options, (tuple, list)) or len(self.options) < 2:
            raise ValueError("options must be a sequence of at least 2 QuestChoiceOption instances.")
        for opt in self.options:
            if not isinstance(opt, QuestChoiceOption):
                raise TypeError(f"All options must be QuestChoiceOption instances, got {type(opt).__name__}.")
        object.__setattr__(self, "options", tuple(self.options))

        # Ensure unique option IDs
        opt_ids = [o.option_id for o in self.options]
        if len(opt_ids) != len(set(opt_ids)):
            raise ValueError(f"Duplicate option IDs found in choice '{self.choice_id}': {opt_ids}.")

        if not isinstance(self.prerequisite_objectives, (tuple, list)):
            raise TypeError("prerequisite_objectives must be a tuple or list of string objective IDs.")
        for p_id in self.prerequisite_objectives:
            if not isinstance(p_id, str) or not p_id.strip():
                raise ValueError("All prerequisite objective IDs must be non-empty strings.")
        object.__setattr__(self, "prerequisite_objectives", tuple(p.strip() for p in self.prerequisite_objectives))

    def get_option(self, option_id: str) -> Optional[QuestChoiceOption]:
        """Returns option by option_id, or None if not found."""
        if not isinstance(option_id, str):
            return None
        norm_id = option_id.strip().lower()
        for opt in self.options:
            if opt.option_id == norm_id:
                return opt
        return None


@dataclass(frozen=True)
class QuestDefinition:
    """
    Immutable template defining a quest, its objectives, prerequisites, choices, and rewards.

    Attributes:
        quest_id: Stable lowercase string identifier.
        name: Display title of the quest.
        description: Narrative/task explanation.
        objectives: Ordered tuple of base QuestObjective specifications.
        prerequisites: Tuple of quest IDs that must be completed first.
        rewards: Dictionary of item_id -> quantity granted upon completion.
        repeatable: Whether this quest can be repeated after completion.
        choices: Optional tuple of branching decision points (QuestChoice).
    """
    quest_id: str
    name: str
    description: str
    objectives: tuple[QuestObjective, ...] = ()
    prerequisites: tuple[str, ...] = ()
    rewards: dict[str, int] = field(default_factory=dict)
    repeatable: bool = False
    choices: tuple[QuestChoice, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.quest_id, str) or not self.quest_id.strip():
            raise ValueError("quest_id must be a non-empty string.")
        object.__setattr__(self, "quest_id", self.quest_id.strip().lower())

        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("name must be a non-empty string.")

        if not isinstance(self.description, str):
            raise TypeError("description must be a string.")

        if not isinstance(self.objectives, (tuple, list)):
            raise TypeError("objectives must be a tuple or list of QuestObjective instances.")

        for obj in self.objectives:
            if not isinstance(obj, QuestObjective):
                raise TypeError(f"All objectives must be QuestObjective instances, got {type(obj).__name__}.")
        object.__setattr__(self, "objectives", tuple(self.objectives))

        # Choices validation
        if not isinstance(self.choices, (tuple, list)):
            raise TypeError("choices must be a tuple or list of QuestChoice instances.")
        for ch in self.choices:
            if not isinstance(ch, QuestChoice):
                raise TypeError(f"All choices must be QuestChoice instances, got {type(ch).__name__}.")
        object.__setattr__(self, "choices", tuple(self.choices))

        if not self.objectives and not self.choices:
            raise ValueError("Quest must have at least one objective or choice.")

        # Ensure unique choice IDs within the quest
        ch_ids = [c.choice_id for c in self.choices]
        if len(ch_ids) != len(set(ch_ids)):
            raise ValueError(f"Duplicate choice IDs found in quest '{self.quest_id}': {ch_ids}.")

        # Ensure unique objective IDs across base objectives and all choice options
        all_objs = list(self.objectives)
        for ch in self.choices:
            for opt in ch.options:
                all_objs.extend(opt.objectives)

        all_obj_ids = [o.objective_id for o in all_objs]
        if len(all_obj_ids) != len(set(all_obj_ids)):
            raise ValueError(f"Duplicate objective IDs found in quest '{self.quest_id}': {all_obj_ids}.")

        # Validate rewards
        if not isinstance(self.rewards, dict):
            raise TypeError("rewards must be a dictionary mapping item_id to quantity.")
        for item_id, qty in self.rewards.items():
            if not isinstance(item_id, str) or not item_id.strip():
                raise ValueError(f"Reward item_id must be a non-empty string, got {item_id!r}.")
            if not isinstance(qty, int) or isinstance(qty, bool) or qty <= 0:
                raise ValueError(f"Reward quantity for item '{item_id}' must be a positive integer, got {qty}.")

    def get_choice(self, choice_id: str) -> Optional[QuestChoice]:
        """Looks up a choice by choice_id."""
        if not isinstance(choice_id, str):
            return None
        norm_id = choice_id.strip().lower()
        for ch in self.choices:
            if ch.choice_id == norm_id:
                return ch
        return None

    def has_choices(self) -> bool:
        """True if the quest has one or more branching choice points."""
        return len(self.choices) > 0

    def get_all_objectives(self) -> tuple[QuestObjective, ...]:
        """Returns all base objectives and all branch objectives across all choices."""
        objs = list(self.objectives)
        for ch in self.choices:
            for opt in ch.options:
                objs.extend(opt.objectives)
        return tuple(objs)

    def get_active_objectives(self, quest_prog: "QuestProgress") -> tuple[QuestObjective, ...]:
        """Returns all currently active objectives for a player's quest progress (base + chosen branches)."""
        active: list[QuestObjective] = list(self.objectives)
        for ch in self.choices:
            opt_id = quest_prog.get_selected_option(ch.choice_id)
            if opt_id:
                opt = ch.get_option(opt_id)
                if opt:
                    active.extend(opt.objectives)
        return tuple(active)


@dataclass
class ObjectiveProgress:
    """
    Tracks runtime progress for an individual objective of an active quest.
    """
    objective_id: str
    target_count: int
    current_count: int = 0
    is_completed: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.objective_id, str) or not self.objective_id.strip():
            raise ValueError("objective_id must be a non-empty string.")
        if not isinstance(self.target_count, int) or isinstance(self.target_count, bool) or self.target_count < 1:
            raise ValueError(f"target_count must be an integer >= 1, got {self.target_count}.")
        if not isinstance(self.current_count, int) or isinstance(self.current_count, bool):
            raise TypeError(f"current_count must be an integer, got {type(self.current_count).__name__}.")

        self.current_count = max(0, min(self.target_count, self.current_count))
        self.is_completed = self.current_count >= self.target_count

    @property
    def remaining(self) -> int:
        """Remaining progress units needed to reach target_count."""
        return max(0, self.target_count - self.current_count)

    @property
    def remaining_count(self) -> int:
        """Alias for remaining."""
        return self.remaining

    @property
    def progress_ratio(self) -> float:
        """Progress completion ratio clamped to [0.0, 1.0]."""
        if self.target_count <= 0:
            return 1.0
        return max(0.0, min(1.0, float(self.current_count) / float(self.target_count)))

    @property
    def progress_percentage(self) -> float:
        """Progress completion percentage in range [0.0, 100.0]."""
        return self.progress_ratio * 100.0

    @property
    def is_incomplete(self) -> bool:
        """True if the objective has not yet reached target_count."""
        return not self.is_completed

    def increment(self, amount: int = 1) -> bool:
        """
        Increments current progress by amount (up to target_count).
        Returns True if progress changed, False otherwise.
        """
        if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0 or self.is_completed:
            return False
        old_val = self.current_count
        self.current_count = min(self.target_count, self.current_count + amount)
        self.is_completed = self.current_count >= self.target_count
        return self.current_count > old_val

    def set_progress(self, count: int, allow_decrease: bool = False) -> bool:
        """
        Sets absolute progress count (clamped to target_count).
        If allow_decrease is False (default), does not allow progress to decrease.
        If allow_decrease is True, allows progress to decrease only if the objective is NOT already completed.
        Once an objective is completed, its progress is permanently locked and cannot decrease.
        Returns True if progress changed, False otherwise.
        """
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            return False
        if self.is_completed:
            return False
        old_val = self.current_count
        if allow_decrease:
            self.current_count = max(0, min(self.target_count, count))
        else:
            self.current_count = max(self.current_count, min(self.target_count, count))
        self.is_completed = self.current_count >= self.target_count
        return self.current_count != old_val

    def sync_state(self, count: int) -> bool:
        """
        Synchronizes runtime progress with authoritative state count.
        Allows progress to increase or decrease to reflect current state while incomplete.
        Once an objective is completed, it remains permanently completed.
        Returns True if progress changed, False otherwise.
        """
        return self.set_progress(count, allow_decrease=True)

    def __repr__(self) -> str:
        status = "COMPLETED" if self.is_completed else f"{self.current_count}/{self.target_count}"
        return f"ObjectiveProgress(id='{self.objective_id}', {status})"


@dataclass
class QuestProgress:
    """
    Tracks a player's runtime progress on a quest independently from definitions.
    """
    quest_id: str
    status: QuestStatus = QuestStatus.LOCKED
    objective_progress: dict[str, ObjectiveProgress] = field(default_factory=dict)
    is_completed: bool = False
    rewards_claimed: bool = False
    selected_choices: dict[str, str] = field(default_factory=dict)

    def has_selected_choice(self, choice_id: str) -> bool:
        """True if the player has committed a choice for choice_id."""
        if not isinstance(choice_id, str):
            return False
        return choice_id.strip().lower() in self.selected_choices

    def get_selected_option(self, choice_id: str) -> Optional[str]:
        """Returns the chosen option_id for choice_id, or None if not chosen."""
        if not isinstance(choice_id, str):
            return None
        return self.selected_choices.get(choice_id.strip().lower())

    def select_choice(self, choice_id: str, option_id: str) -> None:
        """Commits choice_id -> option_id selection."""
        if not isinstance(choice_id, str) or not choice_id.strip():
            raise ValueError("choice_id must be a non-empty string.")
        if not isinstance(option_id, str) or not option_id.strip():
            raise ValueError("option_id must be a non-empty string.")
        self.selected_choices[choice_id.strip().lower()] = option_id.strip().lower()

    def is_all_objectives_completed(self) -> bool:
        """True if every tracked objective has reached its target."""
        if not self.objective_progress:
            return False
        return all(obj.is_completed for obj in self.objective_progress.values())

    def update_completion(self, has_pending_choices: bool = False) -> bool:
        """
        Updates is_completed and status if all objectives are fulfilled and no choices are pending.
        Returns True if quest transitioned to COMPLETED.
        """
        if self.is_completed:
            return False
        if has_pending_choices:
            return False
        if self.is_all_objectives_completed():
            self.is_completed = True
            if self.status == QuestStatus.ACTIVE:
                self.status = QuestStatus.COMPLETED
                return True
        return False

    def get_objective(self, objective_id: str) -> Optional[ObjectiveProgress]:
        """Returns ObjectiveProgress for the given objective_id, or None if not found."""
        if not isinstance(objective_id, str):
            return None
        return self.objective_progress.get(objective_id.strip())

    def get_objective_progress(self, objective_id: str) -> Optional[ObjectiveProgress]:
        """Alias for get_objective."""
        return self.get_objective(objective_id)

    def is_objective_completed(self, objective_id: str) -> bool:
        """True if the given objective is tracked and completed."""
        obj = self.get_objective(objective_id)
        return obj.is_completed if obj is not None else False

    def get_incomplete_objectives(self) -> list[ObjectiveProgress]:
        """Returns list of all objectives that are not yet completed."""
        return [obj for obj in self.objective_progress.values() if not obj.is_completed]

    def get_completed_objectives(self) -> list[ObjectiveProgress]:
        """Returns list of all objectives that have been completed."""
        return [obj for obj in self.objective_progress.values() if obj.is_completed]

    @property
    def incomplete_objectives(self) -> list[ObjectiveProgress]:
        """Property returning incomplete objectives."""
        return self.get_incomplete_objectives()

    @property
    def completed_objectives(self) -> list[ObjectiveProgress]:
        """Property returning completed objectives."""
        return self.get_completed_objectives()

    @property
    def total_objectives_count(self) -> int:
        """Total number of objectives in this quest."""
        return len(self.objective_progress)

    @property
    def remaining_objectives_count(self) -> int:
        """Number of remaining incomplete objectives."""
        return len(self.get_incomplete_objectives())

    @property
    def completed_objectives_count(self) -> int:
        """Number of completed objectives."""
        return len(self.get_completed_objectives())

    @property
    def can_claim_rewards(self) -> bool:
        """True if quest is completed and rewards have not yet been claimed."""
        return self.is_completed and not self.rewards_claimed

    @property
    def progress_ratio(self) -> float:
        """Overall progress ratio across all objectives."""
        if not self.objective_progress:
            return 1.0 if self.is_completed else 0.0
        total_target = sum(obj.target_count for obj in self.objective_progress.values())
        if total_target <= 0:
            return 1.0
        total_current = sum(obj.current_count for obj in self.objective_progress.values())
        return max(0.0, min(1.0, float(total_current) / float(total_target)))

    @property
    def progress_percentage(self) -> float:
        """Overall progress percentage in range [0.0, 100.0]."""
        return self.progress_ratio * 100.0
