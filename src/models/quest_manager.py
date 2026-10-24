"""
Quest Manager orchestrating quest lifecycles, objective progress tracking,
gameplay event handling, and atomic reward distribution.
"""
from dataclasses import dataclass, field
from typing import Optional, Union, Any

from src.models.player import Player
from src.models.quest import (
    QuestStatus,
    ObjectiveType,
    QuestEventType,
    QuestObjective,
    QuestDefinition,
    ObjectiveProgress,
    QuestProgress,
    QuestEvent,
    QuestChoice,
    QuestChoiceOption,
)
from src.data.quests import QUEST_CATALOG, get_quest
from src.data.items import ITEM_CATALOG, get_item


@dataclass(frozen=True)
class QuestNotification:
    """
    Notification payload generated upon quest completion.
    Encapsulates immutable quest identification, status, and pending rewards.
    """
    quest_id: str
    quest_name: str
    status: QuestStatus = QuestStatus.COMPLETED
    rewards: dict[str, int] = field(default_factory=dict)
    message: str = ""

    @property
    def formatted_rewards(self) -> str:
        """Human-readable reward list."""
        if not self.rewards:
            return "None"
        return ", ".join(f"{cnt}x {item.replace('_', ' ').title()}" for item, cnt in self.rewards.items())

    def format_banner(self) -> list[str]:
        """Formats a standard ASCII notification banner."""
        lines = [
            "=" * 55,
            f" [!] QUEST COMPLETED: '{self.quest_name}'!",
            "     Status: Completed | All objectives fulfilled.",
        ]
        if self.rewards:
            lines.append(f"     Rewards available to claim: {self.formatted_rewards}")
        else:
            lines.append("     No item rewards for this quest.")
        lines.append("     (Claim rewards via Quest Journal [j] or Quest Log [6])")
        lines.append("=" * 55)
        return lines


@dataclass(frozen=True)
class QuestActionResult:
    """
    Result returned when accepting, abandoning, or altering a quest.
    """
    success: bool
    quest_id: str
    message: str


@dataclass(frozen=True)
class EventResult:
    """
    Result returned after recording gameplay events across active quests.
    """
    events_processed: int
    objectives_updated: int
    quests_completed: list[str]
    message: str
    notifications: list[QuestNotification] = field(default_factory=list)


@dataclass(frozen=True)
class QuestRewardResult:
    """
    Result returned after claiming rewards for a completed quest.
    """
    success: bool
    quest_id: str
    items_granted: dict[str, int]
    message: str


class QuestManager:
    """
    Service responsible for managing player quest lifecycles:
      - Evaluating quest availability based on prerequisites.
      - Accepting quests and initializing progress tracking.
      - Evaluating state-based objectives on demand and upon acceptance.
      - Ingesting gameplay events with deduplication and updating objectives.
      - Validating and atomically granting item rewards into player inventory.
    """

    def __init__(
        self,
        catalog: Optional[dict[str, QuestDefinition]] = None,
        on_quest_completed: Optional[Any] = None,
    ) -> None:
        """
        Initializes the QuestManager with a quest catalog.

        Args:
            catalog: Optional custom dictionary of QuestDefinitions. Defaults to QUEST_CATALOG.
            on_quest_completed: Optional callable invoked when a quest transitions to COMPLETED.
        """
        self._catalog: dict[str, QuestDefinition] = (
            dict(catalog) if catalog is not None else dict(QUEST_CATALOG)
        )
        self._processed_event_ids: set[str] = set()
        self._announced_completions: set[str] = set()
        self._pending_notifications: list[QuestNotification] = []
        self._on_quest_completed = on_quest_completed

    @property
    def catalog(self) -> dict[str, QuestDefinition]:
        """Dictionary of registered quest definitions."""
        return self._catalog

    def register_quest(self, quest_def: QuestDefinition) -> None:
        """Registers a quest definition into the manager's catalog."""
        if not isinstance(quest_def, QuestDefinition):
            raise TypeError(f"quest_def must be a QuestDefinition instance, got {type(quest_def).__name__}.")
        self._catalog[quest_def.quest_id.strip().lower()] = quest_def

    @property
    def on_quest_completed(self) -> Optional[Any]:
        """Callback invoked when a quest transitions to completed."""
        return self._on_quest_completed

    @on_quest_completed.setter
    def on_quest_completed(self, callback: Optional[Any]) -> None:
        self._on_quest_completed = callback

    def has_pending_notifications(self) -> bool:
        """True if there are unconsumed completion notifications in the queue."""
        return len(self._pending_notifications) > 0

    def get_pending_notifications(self) -> list[QuestNotification]:
        """Returns a copy of all pending completion notifications without clearing the queue."""
        return list(self._pending_notifications)

    def peek_pending_notifications(self) -> list[QuestNotification]:
        """Alias for get_pending_notifications."""
        return self.get_pending_notifications()

    def pop_pending_notifications(self) -> list[QuestNotification]:
        """Returns and clears all pending completion notifications from the queue."""
        notifications = list(self._pending_notifications)
        self._pending_notifications.clear()
        return notifications

    def clear_pending_notifications(self) -> None:
        """Clears all pending completion notifications without returning them."""
        self._pending_notifications.clear()

    def is_completion_announced(self, quest_id: str) -> bool:
        """True if the quest completion has already been announced or queued."""
        if not isinstance(quest_id, str):
            return False
        return quest_id.strip().lower() in self._announced_completions

    def mark_completion_announced(self, quest_id: str) -> None:
        """Marks a quest completion as announced to prevent redundant notifications."""
        if isinstance(quest_id, str) and quest_id.strip():
            self._announced_completions.add(quest_id.strip().lower())

    def reset_completion_announcement(self, quest_id: str) -> None:
        """Clears the announced status for a quest (e.g. for repeatable quests)."""
        if isinstance(quest_id, str) and quest_id.strip():
            self._announced_completions.discard(quest_id.strip().lower())

    def _handle_quest_completed(self, player: Player, quest_id: str) -> Optional[QuestNotification]:
        """
        Authoritative handler invoked when a quest transitions from incomplete to COMPLETED.
        Enqueues a completion notification if not already announced.
        Returns the created QuestNotification if newly announced, None otherwise.
        """
        norm_id = quest_id.strip().lower()
        if norm_id in self._announced_completions:
            return None

        self._announced_completions.add(norm_id)

        quest_def = self._catalog.get(norm_id)
        quest_name = quest_def.name if quest_def else norm_id.replace("_", " ").title()
        rewards = self.get_effective_rewards(player, norm_id)

        rew_str = ", ".join(f"{cnt}x {item.replace('_', ' ').title()}" for item, cnt in rewards.items()) if rewards else "None"
        msg = f"Quest '{quest_name}' completed!"
        if rewards:
            msg += f" Rewards available: {rew_str}."

        notification = QuestNotification(
            quest_id=norm_id,
            quest_name=quest_name,
            status=QuestStatus.COMPLETED,
            rewards=rewards,
            message=msg,
        )
        self._pending_notifications.append(notification)

        if self._on_quest_completed is not None:
            try:
                self._on_quest_completed(notification)
            except Exception:
                pass

        return notification

    # --- Query Methods ---

    def get_quest_definition(self, quest_id: str) -> Optional[QuestDefinition]:
        """Looks up a quest definition from the catalog by ID."""
        if not isinstance(quest_id, str):
            return None
        return self._catalog.get(quest_id.strip().lower())

    def get_quest_progress(self, player: Player, quest_id: str) -> Optional[QuestProgress]:
        """Returns the QuestProgress instance for the player, or None if not accepted."""
        if not isinstance(player, Player) or not isinstance(quest_id, str):
            return None
        return player.quests.get(quest_id.strip().lower())

    def get_quest_status(self, player: Player, quest_id: str) -> QuestStatus:
        """
        Evaluates the current status of a quest for a specific player:
          - If tracked in player.quests: returns recorded QuestStatus.
          - If all prerequisites are completed in player.quests: returns AVAILABLE.
          - Otherwise: returns LOCKED.

        Raises:
            ValueError: If quest_id is not in the quest catalog.
            TypeError: If player is not a Player instance.
        """
        if not isinstance(player, Player):
            raise TypeError(f"player must be a Player instance, got {type(player).__name__}.")

        if not isinstance(quest_id, str) or not quest_id.strip():
            raise ValueError("quest_id must be a non-empty string.")

        norm_id = quest_id.strip().lower()
        quest_def = self._catalog.get(norm_id)
        if quest_def is None:
            raise ValueError(f"Unknown quest_id '{quest_id}' not found in quest catalog.")

        # Check existing progress on player
        prog = player.quests.get(norm_id)
        if prog is not None:
            return prog.status

        # Evaluate prerequisites
        for prereq_id in quest_def.prerequisites:
            prereq_prog = player.quests.get(prereq_id)
            if prereq_prog is None or prereq_prog.status != QuestStatus.COMPLETED:
                return QuestStatus.LOCKED

        return QuestStatus.AVAILABLE

    def get_missing_prerequisites(self, player: Player, quest_id: str) -> list[QuestDefinition]:
        """
        Returns list of prerequisite QuestDefinitions that have not yet been completed by the player.

        Args:
            player: The Player instance to evaluate against.
            quest_id: The identifier of the target quest.

        Returns:
            List of unfulfilled prerequisite QuestDefinitions.
        """
        if not isinstance(player, Player):
            raise TypeError(f"player must be a Player instance, got {type(player).__name__}.")
        if not isinstance(quest_id, str) or not quest_id.strip():
            return []

        norm_id = quest_id.strip().lower()
        quest_def = self._catalog.get(norm_id)
        if quest_def is None:
            return []

        missing: list[QuestDefinition] = []
        for prereq_id in quest_def.prerequisites:
            prereq_prog = player.quests.get(prereq_id)
            if prereq_prog is None or prereq_prog.status != QuestStatus.COMPLETED:
                prereq_def = self._catalog.get(prereq_id)
                if prereq_def is not None:
                    missing.append(prereq_def)
                else:
                    missing.append(
                        QuestDefinition(
                            quest_id=prereq_id,
                            name=prereq_id.replace("_", " ").title(),
                            description="Prerequisite quest.",
                            objectives=(),
                        )
                    )
        return missing

    def list_available_quests(self, player: Player) -> list[QuestDefinition]:
        """Returns definitions of all quests currently available for the player to accept."""
        return [
            q_def for q_def in self._catalog.values()
            if self.get_quest_status(player, q_def.quest_id) == QuestStatus.AVAILABLE
        ]

    def list_active_quests(self, player: Player) -> list[QuestDefinition]:
        """Returns definitions of all currently active quests for the player."""
        return [
            q_def for q_def in self._catalog.values()
            if self.get_quest_status(player, q_def.quest_id) == QuestStatus.ACTIVE
        ]

    def list_completed_quests(self, player: Player) -> list[QuestDefinition]:
        """Returns definitions of all quests completed by the player."""
        return [
            q_def for q_def in self._catalog.values()
            if self.get_quest_status(player, q_def.quest_id) == QuestStatus.COMPLETED
        ]

    # --- Quest Acceptance ---

    def accept_quest(self, player: Player, quest_id: str) -> QuestActionResult:
        """
        Accepts a quest for the player, initializing objective tracking.

        Validation rules:
          - Quest must exist in catalog.
          - Quest must not already be ACTIVE.
          - Quest must not already be COMPLETED unless marked repeatable.
          - All prerequisites must be met.

        Upon acceptance:
          - Evaluates immediate state-based objectives (REACH_LEVEL, OWN_SPECIES, COLLECT_ITEM).
          - Sets initial progress.
          - If all objectives are satisfied immediately, transitions status to COMPLETED.

        Returns:
            QuestActionResult indicating success or failure.
        """
        if not isinstance(player, Player):
            raise TypeError(f"player must be a Player instance, got {type(player).__name__}.")

        if not isinstance(quest_id, str) or not quest_id.strip():
            return QuestActionResult(success=False, quest_id=str(quest_id), message="Invalid quest_id.")

        norm_id = quest_id.strip().lower()
        quest_def = self._catalog.get(norm_id)
        if quest_def is None:
            return QuestActionResult(
                success=False,
                quest_id=norm_id,
                message=f"Quest '{quest_id}' not found in catalog.",
            )

        existing = player.quests.get(norm_id)
        if existing is not None:
            if existing.status == QuestStatus.ACTIVE:
                return QuestActionResult(
                    success=False,
                    quest_id=norm_id,
                    message=f"Quest '{quest_def.name}' is already active.",
                )
            if existing.status == QuestStatus.COMPLETED:
                if not quest_def.repeatable:
                    return QuestActionResult(
                        success=False,
                        quest_id=norm_id,
                        message=f"Quest '{quest_def.name}' is already completed and cannot be repeated.",
                    )
                self.reset_completion_announcement(norm_id)

        # Check prerequisites
        status = self.get_quest_status(player, norm_id)
        if status == QuestStatus.LOCKED:
            return QuestActionResult(
                success=False,
                quest_id=norm_id,
                message=f"Cannot accept '{quest_def.name}': prerequisites not met.",
            )

        # Initialize objective progress trackers
        obj_progress_map: dict[str, ObjectiveProgress] = {}
        for obj in quest_def.objectives:
            prog = ObjectiveProgress(
                objective_id=obj.objective_id,
                target_count=obj.target_count,
                current_count=0,
            )
            obj_progress_map[obj.objective_id] = prog

        # Create QuestProgress instance
        quest_prog = QuestProgress(
            quest_id=norm_id,
            status=QuestStatus.ACTIVE,
            objective_progress=obj_progress_map,
            is_completed=False,
            rewards_claimed=False,
        )
        player.quests[norm_id] = quest_prog

        # Evaluate state-based objectives immediately
        completed_quests = self.evaluate_state_based_objectives(player, norm_id)
        completed_immediately = norm_id in completed_quests

        if completed_immediately:
            return QuestActionResult(
                success=True,
                quest_id=norm_id,
                message=f"Quest '{quest_def.name}' accepted and immediately completed!",
            )

        return QuestActionResult(
            success=True,
            quest_id=norm_id,
            message=f"Quest '{quest_def.name}' accepted successfully.",
        )

    # --- Branching Quests & Choices ---

    def _quest_has_pending_choices(self, quest_prog: QuestProgress) -> bool:
        """
        True if the quest has choices defined and at least one choice has not been made yet.
        """
        quest_def = self._catalog.get(quest_prog.quest_id)
        if not quest_def or not quest_def.has_choices():
            return False
        return any(not quest_prog.has_selected_choice(ch.choice_id) for ch in quest_def.choices)

    def is_choice_available(self, player: Player, quest_id: str, choice_id: str) -> bool:
        """
        Evaluates whether a branching choice can currently be selected by the player.

        Rules:
          - Player must be a Player instance.
          - Quest must exist in catalog.
          - Quest must be tracked and in ACTIVE status on player.
          - Quest must not already be COMPLETED.
          - Choice must exist in the quest definition.
          - Choice must not already be committed in player's quest progress.
          - All prerequisite objectives for the choice (if any) must be completed.

        Returns:
            True if the choice is available for selection, False otherwise.
        """
        if not isinstance(player, Player):
            return False
        if not isinstance(quest_id, str) or not isinstance(choice_id, str):
            return False

        norm_qid = quest_id.strip().lower()
        norm_cid = choice_id.strip().lower()

        quest_def = self._catalog.get(norm_qid)
        if quest_def is None:
            return False

        choice = quest_def.get_choice(norm_cid)
        if choice is None:
            return False

        quest_prog = player.quests.get(norm_qid)
        if quest_prog is None or quest_prog.status != QuestStatus.ACTIVE or quest_prog.is_completed:
            return False

        if quest_prog.has_selected_choice(norm_cid):
            return False

        for prereq_oid in choice.prerequisite_objectives:
            if not quest_prog.is_objective_completed(prereq_oid):
                return False

        return True

    def get_available_choices(self, player: Player, quest_id: str) -> list[QuestChoice]:
        """
        Returns all choices currently available to be made for an active quest.
        """
        if not isinstance(player, Player) or not isinstance(quest_id, str):
            return []

        norm_qid = quest_id.strip().lower()
        quest_def = self._catalog.get(norm_qid)
        if quest_def is None:
            return []

        return [
            choice for choice in quest_def.choices
            if self.is_choice_available(player, norm_qid, choice.choice_id)
        ]

    def get_selected_choice(
        self,
        player: Player,
        quest_id: str,
        choice_id: str,
    ) -> Optional[QuestChoiceOption]:
        """
        Returns the chosen QuestChoiceOption for the specified quest and choice, or None.
        """
        if not isinstance(player, Player) or not isinstance(quest_id, str) or not isinstance(choice_id, str):
            return None

        norm_qid = quest_id.strip().lower()
        norm_cid = choice_id.strip().lower()

        quest_def = self._catalog.get(norm_qid)
        if quest_def is None:
            return None

        choice = quest_def.get_choice(norm_cid)
        if choice is None:
            return None

        quest_prog = player.quests.get(norm_qid)
        if quest_prog is None:
            return None

        opt_id = quest_prog.get_selected_option(norm_cid)
        if opt_id is None:
            return None

        return choice.get_option(opt_id)

    def get_effective_rewards(self, player: Optional[Player], quest_id: str) -> dict[str, int]:
        """
        Calculates the complete reward dictionary for a quest, merging base rewards
        with any option-specific rewards granted by committed choices.
        """
        if not isinstance(quest_id, str):
            return {}

        norm_qid = quest_id.strip().lower()
        quest_def = self._catalog.get(norm_qid)
        if quest_def is None:
            return {}

        rewards = dict(quest_def.rewards)
        if player is not None and isinstance(player, Player):
            quest_prog = player.quests.get(norm_qid)
            if quest_prog is not None and quest_prog.selected_choices:
                for c_id, opt_id in quest_prog.selected_choices.items():
                    choice = quest_def.get_choice(c_id)
                    if choice is not None:
                        opt = choice.get_option(opt_id)
                        if opt is not None and opt.rewards:
                            for itm, qty in opt.rewards.items():
                                rewards[itm] = rewards.get(itm, 0) + qty

        return rewards

    def make_choice(
        self,
        player: Player,
        quest_id: str,
        choice_id: str,
        option_id: str,
    ) -> QuestActionResult:
        """
        Commits a player's selection for a branching quest choice.

        Validation rules:
          - Validates player, quest_id, choice_id, and option_id.
          - Quest must exist in catalog and be tracked in player.quests.
          - Quest must be in ACTIVE status; cannot choose on LOCKED, AVAILABLE, or COMPLETED quests.
          - Choice must exist in quest definition.
          - If the choice has already been committed:
            * If the exact same option is submitted again: returns failure informing it was already chosen.
            * If a different option is submitted: returns failure prohibiting contradictory overwrite.
          - All prerequisite objectives for the choice must be completed.
          - Selected option must exist within the choice definition.

        Outcomes:
          - Records selection in quest_prog.selected_choices.
          - Activates all branch objectives for the chosen option into quest_prog.objective_progress.
          - Immediately evaluates state-based objectives against current player state.
          - Evaluates whether all objectives are now completed.
          - If completed, transitions quest to COMPLETED and enqueues completion notification.
          - Does NEVER auto-claim rewards.

        Returns:
            QuestActionResult indicating success or rejection reason.
        """
        if not isinstance(player, Player):
            raise TypeError(f"player must be a Player instance, got {type(player).__name__}.")

        if not isinstance(quest_id, str) or not quest_id.strip():
            return QuestActionResult(success=False, quest_id=str(quest_id), message="Invalid quest_id.")

        if not isinstance(choice_id, str) or not choice_id.strip():
            return QuestActionResult(success=False, quest_id=str(quest_id), message="Invalid choice_id.")

        if not isinstance(option_id, str) or not option_id.strip():
            return QuestActionResult(success=False, quest_id=str(quest_id), message="Invalid option_id.")

        norm_qid = quest_id.strip().lower()
        norm_cid = choice_id.strip().lower()
        norm_optid = option_id.strip().lower()

        quest_def = self._catalog.get(norm_qid)
        if quest_def is None:
            return QuestActionResult(
                success=False,
                quest_id=norm_qid,
                message=f"Quest '{quest_id}' not found in quest catalog.",
            )

        quest_prog = player.quests.get(norm_qid)
        if quest_prog is None:
            return QuestActionResult(
                success=False,
                quest_id=norm_qid,
                message=f"Quest '{quest_def.name}' has not been accepted.",
            )

        if quest_prog.is_completed or quest_prog.status == QuestStatus.COMPLETED:
            return QuestActionResult(
                success=False,
                quest_id=norm_qid,
                message=f"Cannot make a choice for completed quest '{quest_def.name}'.",
            )

        if quest_prog.status != QuestStatus.ACTIVE:
            return QuestActionResult(
                success=False,
                quest_id=norm_qid,
                message=f"Quest '{quest_def.name}' is not currently active.",
            )

        choice = quest_def.get_choice(norm_cid)
        if choice is None:
            return QuestActionResult(
                success=False,
                quest_id=norm_qid,
                message=f"Choice '{choice_id}' does not exist on quest '{quest_def.name}'.",
            )

        if quest_prog.has_selected_choice(norm_cid):
            existing_opt = quest_prog.get_selected_option(norm_cid)
            if existing_opt == norm_optid:
                return QuestActionResult(
                    success=False,
                    quest_id=norm_qid,
                    message=f"Choice '{norm_cid}' has already been made.",
                )
            return QuestActionResult(
                success=False,
                quest_id=norm_qid,
                message=f"Cannot change previously committed choice '{norm_cid}'.",
            )

        # Check prerequisite objectives
        for prereq_oid in choice.prerequisite_objectives:
            if not quest_prog.is_objective_completed(prereq_oid):
                return QuestActionResult(
                    success=False,
                    quest_id=norm_qid,
                    message=f"Choice '{norm_cid}' requires completing objective '{prereq_oid}' first.",
                )

        selected_opt = choice.get_option(norm_optid)
        if selected_opt is None:
            return QuestActionResult(
                success=False,
                quest_id=norm_qid,
                message=f"Option '{option_id}' does not exist for choice '{norm_cid}'.",
            )

        # Commit selection
        quest_prog.select_choice(norm_cid, norm_optid)

        # Activate branch objectives
        for branch_obj in selected_opt.objectives:
            if branch_obj.objective_id not in quest_prog.objective_progress:
                quest_prog.objective_progress[branch_obj.objective_id] = ObjectiveProgress(
                    objective_id=branch_obj.objective_id,
                    target_count=branch_obj.target_count,
                    current_count=0,
                )

        # Evaluate state-based objectives immediately
        self.evaluate_state_based_objectives(player, norm_qid)

        # Evaluate completion
        has_pending = self._quest_has_pending_choices(quest_prog)
        if quest_prog.update_completion(has_pending_choices=has_pending):
            self._handle_quest_completed(player, norm_qid)
            return QuestActionResult(
                success=True,
                quest_id=norm_qid,
                message=f"Selected '{selected_opt.text}'. Quest '{quest_def.name}' is now completed!",
            )

        return QuestActionResult(
            success=True,
            quest_id=norm_qid,
            message=f"Selected '{selected_opt.text}' for '{choice.prompt}'.",
        )

    # --- Direct Objective Progression & State Synchronization ---

    def advance_objective(
        self,
        player: Player,
        quest_id: str,
        objective_id: str,
        amount: int = 1,
    ) -> bool:
        """
        Manually advances an active quest's objective by amount.
        Returns True if the objective's progress was incremented, False otherwise.
        Automatically updates quest completion state if all objectives complete.
        """
        if not isinstance(quest_id, str) or not isinstance(objective_id, str):
            return False
        norm_qid = quest_id.strip().lower()
        norm_oid = objective_id.strip()

        quest_prog = player.quests.get(norm_qid)
        if not quest_prog or getattr(quest_prog, "status", None) != QuestStatus.ACTIVE:
            return False

        obj_prog = quest_prog.get_objective(norm_oid)
        if not obj_prog:
            return False

        updated = obj_prog.increment(amount)
        if updated:
            has_pending = self._quest_has_pending_choices(quest_prog)
            if quest_prog.update_completion(has_pending_choices=has_pending):
                self._handle_quest_completed(player, quest_prog.quest_id)
        return updated

    def set_objective_progress(
        self,
        player: Player,
        quest_id: str,
        objective_id: str,
        count: int,
        allow_decrease: bool = False,
    ) -> bool:
        """
        Manually sets an active quest's objective progress count.
        Returns True if the objective's progress changed, False otherwise.
        Automatically updates quest completion state if all objectives complete.
        """
        if not isinstance(quest_id, str) or not isinstance(objective_id, str):
            return False
        norm_qid = quest_id.strip().lower()
        norm_oid = objective_id.strip()

        quest_prog = player.quests.get(norm_qid)
        if not quest_prog or getattr(quest_prog, "status", None) != QuestStatus.ACTIVE:
            return False

        obj_prog = quest_prog.get_objective(norm_oid)
        if not obj_prog:
            return False

        updated = obj_prog.set_progress(count, allow_decrease=allow_decrease)
        if updated:
            has_pending = self._quest_has_pending_choices(quest_prog)
            if quest_prog.update_completion(has_pending_choices=has_pending):
                self._handle_quest_completed(player, quest_prog.quest_id)
        return updated

    def sync_objective_progress(
        self,
        player: Player,
        quest_id: str,
        objective_id: str,
        count: int,
    ) -> bool:
        """
        Manually synchronizes an active quest's objective progress count.
        Allows incomplete objectives to decrease if count < current_count.
        """
        return self.set_objective_progress(
            player=player,
            quest_id=quest_id,
            objective_id=objective_id,
            count=count,
            allow_decrease=True,
        )

    def evaluate_state_based_objectives(
        self,
        player: Player,
        quest_id: Optional[str] = None,
    ) -> list[str]:
        """
        Evaluates state-based objectives (inventory counts, collection levels,
        owned species, exploration discoveries) against current player state
        for all active quests or a specific quest.
        Returns a list of quest IDs that transitioned to completed.
        """
        quests_to_eval: list[QuestProgress] = []
        if quest_id is not None:
            norm_qid = quest_id.strip().lower()
            q = player.quests.get(norm_qid)
            if q and getattr(q, "status", None) == QuestStatus.ACTIVE:
                quests_to_eval.append(q)
        else:
            quests_to_eval = [
                q for q in player.quests.values()
                if getattr(q, "status", None) == QuestStatus.ACTIVE
            ]

        completed_quests: list[str] = []
        for quest_prog in quests_to_eval:
            quest_def = self._catalog.get(quest_prog.quest_id)
            if not quest_def:
                continue

            active_objs = quest_def.get_active_objectives(quest_prog)
            for obj in active_objs:
                obj_prog = quest_prog.get_objective(obj.objective_id)
                if not obj_prog:
                    continue

                if obj.objective_type == ObjectiveType.REACH_LEVEL:
                    highest_lvl = max((m.level for m in player.collection), default=0)
                    obj_prog.set_progress(highest_lvl)
                elif obj.objective_type == ObjectiveType.OWN_SPECIES and obj.target_species:
                    owned_cnt = sum(
                        1 for m in player.collection
                        if m.species.name.lower() == obj.target_species.lower()
                    )
                    obj_prog.sync_state(owned_cnt)
                elif obj.objective_type == ObjectiveType.COLLECT_ITEM and obj.target_item:
                    qty = player.inventory.get_quantity(obj.target_item)
                    obj_prog.sync_state(qty)
                elif obj.objective_type == ObjectiveType.DISCOVER_REGION:
                    if obj.target_region:
                        obj_prog.set_progress(1 if player.is_region_discovered(obj.target_region) else 0)
                    else:
                        obj_prog.set_progress(len(player.discovered_regions))
                elif obj.objective_type == ObjectiveType.DISCOVER_LANDMARK:
                    if obj.target_landmark:
                        obj_prog.set_progress(1 if player.is_landmark_discovered(obj.target_landmark) else 0)
                    else:
                        obj_prog.set_progress(len(player.discovered_landmarks))
                elif obj.objective_type == ObjectiveType.DISCOVER_LOCATIONS:
                    obj_prog.set_progress(len(player.discovered_regions) + len(player.discovered_landmarks))

            has_pending = self._quest_has_pending_choices(quest_prog)
            if quest_prog.update_completion(has_pending_choices=has_pending):
                completed_quests.append(quest_prog.quest_id)
                self._handle_quest_completed(player, quest_prog.quest_id)

        return completed_quests

    @staticmethod
    def _matches_region(obj: QuestObjective, payload: dict[str, Any]) -> bool:
        """
        Validates whether an event payload satisfies an objective's target_region restriction.
        If obj.target_region is None: unrestricted (returns True).
        If obj.target_region is specified:
          payload must contain a non-empty string region_id matching obj.target_region (case-insensitive).
          Missing, unknown, or mismatched region context returns False.
        """
        if obj.target_region is None:
            return True
        event_region = payload.get("region_id") or payload.get("region")
        if not isinstance(event_region, str) or not event_region.strip():
            return False
        return event_region.strip().lower() == obj.target_region.strip().lower()

    # --- Gameplay Event Ingestion ---

    def record_event(
        self,
        player: Player,
        event_type: Union[QuestEventType, str],
        payload: Optional[dict[str, Any]] = None,
        event_id: Optional[str] = None,
    ) -> EventResult:
        """
        Records a gameplay event and advances objectives for all active quests.

        Args:
            player: The Player instance whose active quests will be updated.
            event_type: The QuestEventType or matching string value.
            payload: Contextual dictionary with event data (e.g. species, new_level, count).
            event_id: Optional unique string to deduplicate events.

        Returns:
            EventResult summarizing objectives updated and quests completed.
        """
        if not isinstance(player, Player):
            raise TypeError(f"player must be a Player instance, got {type(player).__name__}.")

        # Event deduplication
        if event_id is not None:
            if not isinstance(event_id, str) or not event_id.strip():
                return EventResult(0, 0, [], "Invalid event_id.")
            clean_event_id = event_id.strip()
            if clean_event_id in self._processed_event_ids:
                return EventResult(0, 0, [], f"Duplicate event '{clean_event_id}' ignored.")
            self._processed_event_ids.add(clean_event_id)

        # Parse event type
        if isinstance(event_type, str):
            try:
                event_type_enum = QuestEventType(event_type.strip().lower())
            except ValueError:
                return EventResult(0, 0, [], f"Unknown event type '{event_type}'.")
        elif isinstance(event_type, QuestEventType):
            event_type_enum = event_type
        else:
            return EventResult(0, 0, [], f"Invalid event_type {type(event_type).__name__}.")

        event_payload = payload if payload is not None else {}
        active_quests = [
            qp for qp in player.quests.values()
            if qp.status == QuestStatus.ACTIVE
        ]

        if not active_quests:
            return EventResult(1, 0, [], "Event recorded; no active quests to update.")

        objectives_updated = 0
        quests_completed: list[str] = []
        new_notifications: list[QuestNotification] = []

        for quest_prog in active_quests:
            quest_def = self._catalog.get(quest_prog.quest_id)
            if quest_def is None:
                continue

            active_objs = quest_def.get_active_objectives(quest_prog)
            for obj in active_objs:
                obj_prog = quest_prog.objective_progress.get(obj.objective_id)
                if obj_prog is None or obj_prog.is_completed:
                    continue

                updated = False

                if event_type_enum == QuestEventType.POKEMON_CAPTURED:
                    if obj.objective_type == ObjectiveType.CAPTURE_ANY:
                        if not self._matches_region(obj, event_payload):
                            continue
                        count = int(event_payload.get("count", 1))
                        updated = obj_prog.increment(max(1, count))
                    elif obj.objective_type == ObjectiveType.CAPTURE_SPECIES:
                        if not self._matches_region(obj, event_payload):
                            continue
                        species_name = (
                            event_payload.get("species_name")
                            or event_payload.get("species")
                        )
                        if (
                            isinstance(species_name, str)
                            and obj.target_species
                            and species_name.strip().lower() == obj.target_species.strip().lower()
                        ):
                            count = int(event_payload.get("count", 1))
                            updated = obj_prog.increment(max(1, count))

                elif event_type_enum == QuestEventType.POKEMON_DEFEATED:
                    if obj.objective_type == ObjectiveType.DEFEAT_ANY:
                        if not self._matches_region(obj, event_payload):
                            continue
                        count = int(event_payload.get("count", 1))
                        updated = obj_prog.increment(max(1, count))
                    elif obj.objective_type == ObjectiveType.DEFEAT_SPECIES:
                        if not self._matches_region(obj, event_payload):
                            continue
                        species_name = (
                            event_payload.get("species_name")
                            or event_payload.get("species")
                        )
                        if (
                            isinstance(species_name, str)
                            and obj.target_species
                            and species_name.strip().lower() == obj.target_species.strip().lower()
                        ):
                            count = int(event_payload.get("count", 1))
                            updated = obj_prog.increment(max(1, count))

                elif event_type_enum == QuestEventType.POKEMON_LEVEL_UP:
                    if obj.objective_type == ObjectiveType.REACH_LEVEL:
                        new_lvl = event_payload.get("new_level") or event_payload.get("level")
                        max_collection_lvl = max((m.level for m in player.collection), default=0)
                        if isinstance(new_lvl, int) and not isinstance(new_lvl, bool):
                            target_lvl = max(new_lvl, max_collection_lvl)
                        else:
                            target_lvl = max_collection_lvl
                        updated = obj_prog.set_progress(target_lvl)

                elif event_type_enum == QuestEventType.POKEMON_COLLECTED:
                    if obj.objective_type == ObjectiveType.OWN_SPECIES:
                        if obj.target_species:
                            owned_cnt = sum(
                                1 for m in player.collection
                                if m.species.name.lower() == obj.target_species.lower()
                            )
                            updated = obj_prog.sync_state(owned_cnt)

                elif event_type_enum == QuestEventType.ITEM_COLLECTED:
                    if obj.objective_type == ObjectiveType.COLLECT_ITEM:
                        item_id = event_payload.get("item_id") or event_payload.get("item")
                        if item_id is not None and isinstance(item_id, str) and obj.target_item:
                            if item_id.strip().lower() != obj.target_item.strip().lower():
                                continue
                        if obj.target_item:
                            inv_qty = player.inventory.get_quantity(obj.target_item)
                            updated = obj_prog.sync_state(inv_qty)
                        else:
                            count = int(event_payload.get("count", 1))
                            updated = obj_prog.increment(max(1, count))

                elif event_type_enum == QuestEventType.ITEM_CONSUMED:
                    if obj.objective_type == ObjectiveType.COLLECT_ITEM and obj.target_item:
                        item_id = event_payload.get("item_id") or event_payload.get("item")
                        if item_id is not None and isinstance(item_id, str):
                            if item_id.strip().lower() != obj.target_item.strip().lower():
                                continue
                        inv_qty = player.inventory.get_quantity(obj.target_item)
                        updated = obj_prog.sync_state(inv_qty)

                elif event_type_enum == QuestEventType.REGION_DISCOVERED:
                    if obj.objective_type == ObjectiveType.DISCOVER_REGION:
                        region_id = (
                            event_payload.get("region_id")
                            or event_payload.get("region")
                        )
                        if obj.target_region:
                            if isinstance(region_id, str) and region_id.strip().lower() == obj.target_region.strip().lower():
                                updated = obj_prog.set_progress(1)
                        else:
                            count = int(event_payload.get("count", 1))
                            updated = obj_prog.increment(max(1, count))
                    elif obj.objective_type == ObjectiveType.DISCOVER_LOCATIONS:
                        count = int(event_payload.get("count", 1))
                        updated = obj_prog.increment(max(1, count))

                elif event_type_enum == QuestEventType.LANDMARK_DISCOVERED:
                    if obj.objective_type == ObjectiveType.DISCOVER_LANDMARK:
                        landmark_id = (
                            event_payload.get("landmark_id")
                            or event_payload.get("landmark")
                        )
                        if obj.target_landmark:
                            if isinstance(landmark_id, str) and landmark_id.strip().lower() == obj.target_landmark.strip().lower():
                                updated = obj_prog.set_progress(1)
                        else:
                            count = int(event_payload.get("count", 1))
                            updated = obj_prog.increment(max(1, count))
                    elif obj.objective_type == ObjectiveType.DISCOVER_LOCATIONS:
                        count = int(event_payload.get("count", 1))
                        updated = obj_prog.increment(max(1, count))

                elif event_type_enum == QuestEventType.POKEMON_ENCOUNTERED:
                    if obj.objective_type == ObjectiveType.ENCOUNTER_ANY:
                        if not self._matches_region(obj, event_payload):
                            continue
                        count = int(event_payload.get("count", 1))
                        updated = obj_prog.increment(max(1, count))
                    elif obj.objective_type == ObjectiveType.ENCOUNTER_SPECIES:
                        if not self._matches_region(obj, event_payload):
                            continue
                        species_name = (
                            event_payload.get("species_name")
                            or event_payload.get("species")
                        )
                        if (
                            isinstance(species_name, str)
                            and obj.target_species
                            and species_name.strip().lower() == obj.target_species.strip().lower()
                        ):
                            count = int(event_payload.get("count", 1))
                            updated = obj_prog.increment(max(1, count))

                elif event_type_enum == QuestEventType.OBJECT_INTERACTED:
                    if obj.objective_type == ObjectiveType.INTERACT_OBJECT:
                        if not self._matches_region(obj, event_payload):
                            continue
                        target_obj = (
                            event_payload.get("object_id")
                            or event_payload.get("target_object")
                            or event_payload.get("interactable_id")
                        )
                        target_npc = event_payload.get("npc_id")
                        if obj.target_object:
                            norm_target = obj.target_object.strip().lower()
                            candidates: set[str] = set()
                            if isinstance(target_obj, str) and target_obj.strip():
                                t_clean = target_obj.strip().lower()
                                candidates.add(t_clean)
                                if t_clean.startswith("npc_"):
                                    candidates.add(t_clean[4:])
                            if isinstance(target_npc, str) and target_npc.strip():
                                n_clean = target_npc.strip().lower()
                                candidates.add(n_clean)
                                candidates.add(f"npc_{n_clean}")
                            if norm_target not in candidates:
                                continue
                        count = int(event_payload.get("count", 1))
                        updated = obj_prog.increment(max(1, count))

                if updated:
                    objectives_updated += 1

            has_pending = self._quest_has_pending_choices(quest_prog)
            if quest_prog.update_completion(has_pending_choices=has_pending):
                quests_completed.append(quest_prog.quest_id)
                note = self._handle_quest_completed(player, quest_prog.quest_id)
                if note is not None:
                    new_notifications.append(note)

        msg = f"Processed event: {objectives_updated} objective(s) updated."
        if quests_completed:
            msg += f" Completed: {', '.join(quests_completed)}."

        return EventResult(
            events_processed=1,
            objectives_updated=objectives_updated,
            quests_completed=quests_completed,
            message=msg,
            notifications=new_notifications,
        )

    # --- Convenience Event Helpers ---

    def record_capture(
        self,
        player: Player,
        species_name: Optional[str] = None,
        count: int = 1,
        event_id: Optional[str] = None,
        region_id: Optional[str] = None,
    ) -> EventResult:
        """Helper to record a wild Pokemon capture event."""
        payload: dict[str, Any] = {"count": count}
        if species_name:
            payload["species_name"] = species_name
        if region_id:
            payload["region_id"] = region_id
        return self.record_event(
            player,
            QuestEventType.POKEMON_CAPTURED,
            payload=payload,
            event_id=event_id,
        )

    def record_defeat(
        self,
        player: Player,
        species_name: Optional[str] = None,
        count: int = 1,
        event_id: Optional[str] = None,
        region_id: Optional[str] = None,
    ) -> EventResult:
        """Helper to record an enemy Pokemon defeat event."""
        payload: dict[str, Any] = {"count": count}
        if species_name:
            payload["species_name"] = species_name
        if region_id:
            payload["region_id"] = region_id
        return self.record_event(
            player,
            QuestEventType.POKEMON_DEFEATED,
            payload=payload,
            event_id=event_id,
        )

    def record_level_up(
        self,
        player: Player,
        new_level: int,
        event_id: Optional[str] = None,
    ) -> EventResult:
        """Helper to record a Pokemon level-up event."""
        return self.record_event(
            player,
            QuestEventType.POKEMON_LEVEL_UP,
            payload={"new_level": new_level},
            event_id=event_id,
        )

    def record_item_collected(
        self,
        player: Player,
        item_id: str,
        event_id: Optional[str] = None,
    ) -> EventResult:
        """Helper to record an item acquisition event and sync item collection objectives."""
        return self.record_event(
            player,
            QuestEventType.ITEM_COLLECTED,
            payload={"item_id": item_id},
            event_id=event_id,
        )

    def record_item_consumed(
        self,
        player: Player,
        item_id: str,
        count: int = 1,
        event_id: Optional[str] = None,
    ) -> EventResult:
        """Helper to record an item consumption event and synchronize item possession objectives."""
        return self.record_event(
            player,
            QuestEventType.ITEM_CONSUMED,
            payload={"item_id": item_id, "count": count},
            event_id=event_id,
        )

    def sync_inventory_state(
        self,
        player: Player,
        item_id: Optional[str] = None,
    ) -> EventResult:
        """
        Synchronizes all state-based item possession objectives for active quests
        with the player's current inventory quantities.

        Allows incomplete item possession objectives to adjust upwards or downwards
        accurately, while guaranteeing that completed objectives and quests are never
        reverted or degraded.
        """
        if not isinstance(player, Player):
            raise TypeError(f"player must be a Player instance, got {type(player).__name__}.")

        norm_item = item_id.strip().lower() if isinstance(item_id, str) and item_id.strip() else None

        active_quests = [
            qp for qp in player.quests.values()
            if qp.status == QuestStatus.ACTIVE
        ]

        if not active_quests:
            return EventResult(1, 0, [], "Inventory synced; no active quests to update.")

        objectives_updated = 0
        quests_completed: list[str] = []
        new_notifications: list[QuestNotification] = []

        for quest_prog in active_quests:
            quest_def = self._catalog.get(quest_prog.quest_id)
            if quest_def is None:
                continue

            for obj in quest_def.objectives:
                if obj.objective_type != ObjectiveType.COLLECT_ITEM or not obj.target_item:
                    continue

                if norm_item is not None and obj.target_item.strip().lower() != norm_item:
                    continue

                obj_prog = quest_prog.get_objective(obj.objective_id)
                if obj_prog is None or obj_prog.is_completed:
                    continue

                inv_qty = player.inventory.get_quantity(obj.target_item)
                if obj_prog.sync_state(inv_qty):
                    objectives_updated += 1

            if quest_prog.update_completion():
                quests_completed.append(quest_prog.quest_id)
                note = self._handle_quest_completed(player, quest_prog.quest_id)
                if note is not None:
                    new_notifications.append(note)

        msg = f"Synced inventory state: {objectives_updated} objective(s) updated."
        if quests_completed:
            msg += f" Completed: {', '.join(quests_completed)}."

        return EventResult(
            events_processed=1,
            objectives_updated=objectives_updated,
            quests_completed=quests_completed,
            message=msg,
            notifications=new_notifications,
        )

    def record_region_discovery(
        self,
        player: Player,
        region_id: str,
        event_id: Optional[str] = None,
    ) -> EventResult:
        """Helper to record a region discovery event and update discovery objectives."""
        return self.record_event(
            player,
            QuestEventType.REGION_DISCOVERED,
            payload={"region_id": region_id, "count": 1},
            event_id=event_id,
        )

    def record_landmark_discovery(
        self,
        player: Player,
        landmark_id: str,
        event_id: Optional[str] = None,
    ) -> EventResult:
        """Helper to record a landmark discovery event and update discovery objectives."""
        return self.record_event(
            player,
            QuestEventType.LANDMARK_DISCOVERED,
            payload={"landmark_id": landmark_id, "count": 1},
            event_id=event_id,
        )

    def record_encounter(
        self,
        player: Player,
        species_name: Optional[str] = None,
        habitat_id: Optional[str] = None,
        region_id: Optional[str] = None,
        count: int = 1,
        event_id: Optional[str] = None,
    ) -> EventResult:
        """Helper to record a wild Pokemon encounter event."""
        payload: dict[str, Any] = {"count": count}
        if species_name:
            payload["species_name"] = species_name
        if habitat_id:
            payload["habitat_id"] = habitat_id
        if region_id:
            payload["region_id"] = region_id
        return self.record_event(
            player,
            QuestEventType.POKEMON_ENCOUNTERED,
            payload=payload,
            event_id=event_id,
        )

    def record_object_interaction(
        self,
        player: Player,
        object_id: str,
        region_id: Optional[str] = None,
        npc_id: Optional[str] = None,
        count: int = 1,
        event_id: Optional[str] = None,
    ) -> EventResult:
        """Helper to record a world object interaction event."""
        payload: dict[str, Any] = {"object_id": object_id, "count": count}
        if region_id:
            payload["region_id"] = region_id
        if npc_id:
            payload["npc_id"] = npc_id
        return self.record_event(
            player,
            QuestEventType.OBJECT_INTERACTED,
            payload=payload,
            event_id=event_id,
        )

    # --- Atomic Reward Claiming ---

    def claim_rewards(self, player: Player, quest_id: str) -> QuestRewardResult:
        """
        Atomically claims item rewards for a completed quest.

        Atomicity guarantees:
          - Verifies the quest is COMPLETED.
          - Rejects duplicate claims if already claimed.
          - Pre-validates that player inventory has sufficient slot capacity
            and item stack headroom for ALL reward items before granting any.
          - If capacity or stack limit checks fail, leaves inventory unchanged
            and leaves rewards_claimed = False.
          - Grants all items atomically and sets rewards_claimed = True.

        Returns:
            QuestRewardResult indicating success, items granted, or failure message.
        """
        if not isinstance(player, Player):
            raise TypeError(f"player must be a Player instance, got {type(player).__name__}.")

        if not isinstance(quest_id, str) or not quest_id.strip():
            return QuestRewardResult(
                success=False,
                quest_id=str(quest_id),
                items_granted={},
                message="Invalid quest_id.",
            )

        norm_id = quest_id.strip().lower()
        quest_prog = player.quests.get(norm_id)
        if quest_prog is None:
            return QuestRewardResult(
                success=False,
                quest_id=norm_id,
                items_granted={},
                message=f"Quest '{quest_id}' has not been accepted.",
            )

        if not quest_prog.is_completed:
            return QuestRewardResult(
                success=False,
                quest_id=norm_id,
                items_granted={},
                message=f"Quest '{quest_id}' is not completed yet.",
            )

        if quest_prog.rewards_claimed:
            return QuestRewardResult(
                success=False,
                quest_id=norm_id,
                items_granted={},
                message=f"Rewards for quest '{quest_id}' have already been claimed.",
            )

        quest_def = self._catalog.get(norm_id)
        if quest_def is None:
            return QuestRewardResult(
                success=False,
                quest_id=norm_id,
                items_granted={},
                message=f"Quest definition for '{quest_id}' not found in catalog.",
            )

        rewards = self.get_effective_rewards(player, norm_id)
        if not rewards:
            quest_prog.rewards_claimed = True
            return QuestRewardResult(
                success=True,
                quest_id=norm_id,
                items_granted={},
                message=f"Rewards claimed for '{quest_def.name}' (no items).",
            )

        # Pre-validate inventory capacity & stack limits atomically
        inv = player.inventory
        new_slots_needed = 0

        for item_id, quantity in rewards.items():
            norm_item = item_id.strip().lower()
            item_obj = inv._catalog.get(norm_item) or get_item(norm_item)
            if item_obj is None:
                return QuestRewardResult(
                    success=False,
                    quest_id=norm_id,
                    items_granted={},
                    message=f"Reward item '{item_id}' not found in catalog.",
                )

            current_qty = inv.get_quantity(norm_item)
            if current_qty == 0:
                new_slots_needed += 1

            if current_qty + quantity > item_obj.max_stack:
                return QuestRewardResult(
                    success=False,
                    quest_id=norm_id,
                    items_granted={},
                    message=(
                        f"Cannot claim rewards: adding {quantity}x '{item_obj.name}' "
                        f"would exceed max stack size ({item_obj.max_stack})."
                    ),
                )

        if inv.capacity is not None and inv.slots_used + new_slots_needed > inv.capacity:
            return QuestRewardResult(
                success=False,
                quest_id=norm_id,
                items_granted={},
                message=(
                    f"Cannot claim rewards: inventory capacity exceeded "
                    f"({inv.slots_used + new_slots_needed}/{inv.capacity} slots needed)."
                ),
            )

        # Atomically grant all reward items
        granted: dict[str, int] = {}
        for item_id, quantity in rewards.items():
            norm_item = item_id.strip().lower()
            inv.add_item(norm_item, quantity)
            granted[norm_item] = quantity

        quest_prog.rewards_claimed = True
        return QuestRewardResult(
            success=True,
            quest_id=norm_id,
            items_granted=granted,
            message=f"Rewards successfully claimed for quest '{quest_def.name}'!",
        )

    def claim_all_completed_rewards(self, player: Player) -> list[QuestRewardResult]:
        """
        Attempts to claim rewards for all completed quests with unclaimed rewards.
        Returns a list of QuestRewardResult instances for each claim attempt.
        """
        if not isinstance(player, Player):
            raise TypeError(f"player must be a Player instance, got {type(player).__name__}.")

        results: list[QuestRewardResult] = []
        claimable_ids = [
            q_prog.quest_id for q_prog in player.quests.values()
            if q_prog.is_completed and not q_prog.rewards_claimed
        ]

        for q_id in claimable_ids:
            res = self.claim_rewards(player, q_id)
            results.append(res)

        return results

