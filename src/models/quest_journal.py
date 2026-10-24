"""
Quest Journal and Progress Display presentation layer for Syntax Error 2026.

Provides view models, progress bar rendering, summary formatting,
and detailed quest dossier inspection decoupled from input/output mechanics.
Authoritative state is queried directly from Player and QuestManager without mutation.
"""
from dataclasses import dataclass, field
from typing import Optional, Union, Any

from src.models.player import Player
from src.models.quest import (
    QuestStatus,
    QuestDefinition,
    QuestObjective,
    ObjectiveProgress,
    QuestProgress,
)
from src.models.quest_manager import QuestManager, QuestNotification, QuestRewardResult
from src.data.quests import QUEST_CATALOG


def make_progress_bar(ratio: float, width: int = 10) -> str:
    """
    Renders a pure ASCII progress bar of specified width.
    Example: ratio=0.4, width=10 -> '[====------]'
    """
    clamped = max(0.0, min(1.0, float(ratio)))
    filled = int(round(clamped * width))
    empty = max(0, width - filled)
    return f"[{'=' * filled}{'-' * empty}]"


@dataclass(frozen=True)
class ObjectiveEntryView:
    """
    Read-only presentation model for an individual quest objective.
    """
    objective_id: str
    description: str
    current_count: int
    target_count: int
    remaining_count: int
    is_completed: bool
    progress_ratio: float
    progress_percentage: float
    progress_bar: str

    @property
    def formatted_counts(self) -> str:
        """Formatted current/target string, e.g. '3/5'."""
        return f"{self.current_count}/{self.target_count}"

    @property
    def status_tag(self) -> str:
        """Visual status label."""
        return "[COMPLETED]" if self.is_completed else "[IN PROGRESS]"

    @property
    def marker(self) -> str:
        """ASCII checkmark representation."""
        return "[X]" if self.is_completed else "[ ]"


@dataclass(frozen=True)
class QuestEntryView:
    """
    Read-only presentation model for a tracked quest in the player's journal.
    """
    quest_id: str
    name: str
    description: str
    status: QuestStatus
    is_completed: bool
    rewards_claimed: bool
    can_claim_rewards: bool
    progress_ratio: float
    progress_percentage: float
    progress_bar: str
    total_objectives_count: int
    completed_objectives_count: int
    remaining_objectives_count: int
    rewards: dict[str, int]
    prerequisites: tuple[str, ...]
    objectives: list[ObjectiveEntryView]
    chosen_paths: list[str] = field(default_factory=list)

    @property
    def status_label(self) -> str:
        """Display label for quest status."""
        if self.is_completed:
            if self.rewards_claimed:
                return "COMPLETED"
            return "COMPLETED (READY TO CLAIM)"
        return "ACTIVE"

    @property
    def marker(self) -> str:
        """ASCII marker for quest state."""
        return "[X]" if self.is_completed else "[*]"

    @property
    def formatted_rewards(self) -> str:
        """Human-readable reward item list."""
        if not self.rewards:
            return "None"
        return ", ".join(f"{cnt}x {item.replace('_', ' ').title()}" for item, cnt in self.rewards.items())


class QuestJournal:
    """
    Presentation and formatting engine for the player's Quest Journal.
    Decoupled from terminal I/O for 100% automated testability.
    Queries authoritative state from Player and QuestManager without side effects.
    """

    def __init__(
        self,
        quest_manager: Optional[QuestManager] = None,
        catalog: Optional[dict[str, QuestDefinition]] = None,
    ) -> None:
        self._manager = quest_manager or QuestManager()
        self._catalog = catalog if catalog is not None else self._manager.catalog

    def get_tracked_entries(
        self,
        player: Player,
        filter_status: Optional[Union[QuestStatus, str]] = None,
    ) -> list[QuestEntryView]:
        """
        Retrieves all quests currently tracked by the player as QuestEntryView models.
        Supports filtering by status ('ACTIVE', 'COMPLETED', etc.).
        """
        if not isinstance(player, Player):
            return []

        norm_filter: Optional[str] = None
        if filter_status is not None:
            norm_filter = (
                filter_status.value
                if isinstance(filter_status, QuestStatus)
                else str(filter_status).strip().lower()
            )

        entries: list[QuestEntryView] = []
        for quest_id, quest_prog in player.quests.items():
            status_val = quest_prog.status.value if isinstance(quest_prog.status, QuestStatus) else str(quest_prog.status).lower()
            if norm_filter and status_val != norm_filter:
                continue

            entry = self._build_entry_view(quest_id, quest_prog)
            if entry:
                entries.append(entry)

        # Sort entries: Active quests first, then Completed
        entries.sort(key=lambda e: (1 if e.is_completed else 0, e.name.lower()))
        return entries

    def get_entry(self, player: Player, quest_id: str) -> Optional[QuestEntryView]:
        """
        Retrieves a single QuestEntryView for a specific tracked quest ID.
        """
        if not isinstance(player, Player) or not isinstance(quest_id, str):
            return None

        norm_qid = quest_id.strip().lower()
        quest_prog = player.quests.get(norm_qid)
        if quest_prog is None:
            return None

        return self._build_entry_view(norm_qid, quest_prog)

    def _build_entry_view(self, quest_id: str, quest_prog: QuestProgress) -> QuestEntryView:
        """Builds a QuestEntryView from authoritative QuestProgress and catalog definition."""
        quest_def = self._catalog.get(quest_id)

        name = quest_def.name if quest_def else quest_id.replace("_", " ").title()
        description = quest_def.description if quest_def else "No description available."
        # Determine active objective definitions, chosen paths, and effective rewards
        chosen_paths: list[str] = []
        active_obj_defs: list[QuestObjective] = []
        rewards: dict[str, int] = dict(quest_def.rewards) if quest_def else {}
        prerequisites: tuple[str, ...] = tuple(quest_def.prerequisites) if quest_def else ()

        if quest_def:
            active_obj_defs.extend(quest_def.objectives)
            if quest_def.choices and quest_prog.selected_choices:
                for ch in quest_def.choices:
                    sel_opt_id = quest_prog.get_selected_option(ch.choice_id)
                    if sel_opt_id:
                        opt = ch.get_option(sel_opt_id)
                        if opt:
                            chosen_paths.append(opt.text)
                            active_obj_defs.extend(opt.objectives)
                            if opt.rewards:
                                for itm, qty in opt.rewards.items():
                                    rewards[itm] = rewards.get(itm, 0) + qty

        # Build objective entry views
        obj_entries: list[ObjectiveEntryView] = []
        if active_obj_defs:
            for obj_def in active_obj_defs:
                obj_prog = quest_prog.get_objective(obj_def.objective_id)
                cur_cnt = obj_prog.current_count if obj_prog else 0
                tgt_cnt = obj_prog.target_count if obj_prog else obj_def.target_count
                rem_cnt = obj_prog.remaining if obj_prog else tgt_cnt
                is_done = obj_prog.is_completed if obj_prog else (cur_cnt >= tgt_cnt)
                ratio = obj_prog.progress_ratio if obj_prog else (float(cur_cnt) / float(tgt_cnt) if tgt_cnt > 0 else 0.0)
                pct = obj_prog.progress_percentage if obj_prog else ratio * 100.0

                obj_entries.append(
                    ObjectiveEntryView(
                        objective_id=obj_def.objective_id,
                        description=obj_def.description or obj_def.objective_id.replace("_", " ").title(),
                        current_count=cur_cnt,
                        target_count=tgt_cnt,
                        remaining_count=rem_cnt,
                        is_completed=is_done,
                        progress_ratio=ratio,
                        progress_percentage=pct,
                        progress_bar=make_progress_bar(ratio),
                    )
                )
        else:
            # Fallback for dynamic / untracked definitions
            for obj_id, obj_prog in quest_prog.objective_progress.items():
                obj_entries.append(
                    ObjectiveEntryView(
                        objective_id=obj_id,
                        description=obj_id.replace("_", " ").title(),
                        current_count=obj_prog.current_count,
                        target_count=obj_prog.target_count,
                        remaining_count=obj_prog.remaining,
                        is_completed=obj_prog.is_completed,
                        progress_ratio=obj_prog.progress_ratio,
                        progress_percentage=obj_prog.progress_percentage,
                        progress_bar=make_progress_bar(obj_prog.progress_ratio),
                    )
                )

        ratio = quest_prog.progress_ratio
        pct = quest_prog.progress_percentage
        bar = make_progress_bar(ratio)

        return QuestEntryView(
            quest_id=quest_id,
            name=name,
            description=description,
            status=quest_prog.status,
            is_completed=quest_prog.is_completed,
            rewards_claimed=quest_prog.rewards_claimed,
            can_claim_rewards=quest_prog.can_claim_rewards,
            progress_ratio=ratio,
            progress_percentage=pct,
            progress_bar=bar,
            total_objectives_count=quest_prog.total_objectives_count,
            completed_objectives_count=quest_prog.completed_objectives_count,
            remaining_objectives_count=quest_prog.remaining_objectives_count,
            rewards=rewards,
            prerequisites=prerequisites,
            objectives=obj_entries,
            chosen_paths=chosen_paths,
        )

    # --- Formatting Methods ---

    def format_summary_header(self, player: Player) -> list[str]:
        """Formats the top header and summary counts."""
        tracked = list(player.quests.values())
        total = len(tracked)
        active = sum(1 for q in tracked if q.status == QuestStatus.ACTIVE)
        completed = sum(1 for q in tracked if q.is_completed)
        claimable = sum(1 for q in tracked if q.can_claim_rewards)

        lines: list[str] = [
            "=" * 55,
            f" QUEST JOURNAL - {player.name}'s Adventure Log",
            "=" * 55,
            f" Summary: {total} Tracked | {active} Active | {completed} Completed | {claimable} Claimable",
            "-" * 55,
        ]
        return lines

    def format_empty_state(self, filter_status: Optional[Union[QuestStatus, str]] = None) -> list[str]:
        """Formats a sensible empty state message."""
        norm_filter = (
            filter_status.value
            if isinstance(filter_status, QuestStatus)
            else str(filter_status).strip().lower() if filter_status else None
        )

        if norm_filter == "active":
            return ["  (No active quests in progress.)"]
        elif norm_filter == "completed":
            return ["  (No completed quests yet.)"]
        else:
            return [
                "  (Your quest journal is currently empty.)",
                "  (No quests are being tracked. Accept available quests from the Quest Log!)",
            ]

    def format_quest_list(
        self,
        entries: list[QuestEntryView],
        page: int = 1,
        page_size: int = 4,
    ) -> tuple[list[str], int, int]:
        """
        Formats a paginated list of quest summaries for the journal panel.
        Returns (lines, current_page, total_pages).
        """
        if not entries:
            return (self.format_empty_state(), 1, 1)

        total_pages = max(1, (len(entries) + page_size - 1) // page_size)
        curr_page = max(1, min(page, total_pages))

        start_idx = (curr_page - 1) * page_size
        page_entries = entries[start_idx : start_idx + page_size]

        lines: list[str] = []
        page_indicator = f" (Page {curr_page}/{total_pages})" if total_pages > 1 else ""
        lines.append(f"--- TRACKED QUESTS{page_indicator} ---")

        for idx, entry in enumerate(page_entries, start_idx + 1):
            status_tag = f"[{entry.status.value.upper()}]" if isinstance(entry.status, QuestStatus) else f"[{str(entry.status).upper()}]"
            claim_tag = " [READY TO CLAIM!]" if entry.can_claim_rewards else ""
            claimed_tag = " [REWARDS CLAIMED]" if entry.rewards_claimed else ""

            lines.append(f" [{idx}] {entry.marker} {entry.name} {status_tag}{claim_tag}{claimed_tag}")
            lines.append(
                f"      Progress: {entry.progress_bar} {entry.progress_percentage:.1f}% "
                f"({entry.completed_objectives_count}/{entry.total_objectives_count} objectives)"
            )

            # Show objective progress lines
            if not entry.objectives:
                lines.append("      Objectives: None defined")
            else:
                for obj in entry.objectives:
                    rem_str = f", {obj.remaining_count} remaining" if obj.remaining_count > 0 else ""
                    lines.append(
                        f"      - {obj.marker} {obj.description}: {obj.formatted_counts} "
                        f"{obj.progress_bar} ({obj.progress_percentage:.1f}%{rem_str}) {obj.status_tag}"
                    )

            if entry.can_claim_rewards:
                lines.append(f"      Reward Available: {entry.formatted_rewards}")
            lines.append("")

        return (lines, curr_page, total_pages)

    def format_quest_dossier(self, entry: QuestEntryView) -> list[str]:
        """
        Formats a detailed dossier inspection view for a single quest.
        """
        status_tag = f"[{entry.status.value.upper()}]" if isinstance(entry.status, QuestStatus) else f"[{str(entry.status).upper()}]"
        lines: list[str] = [
            "=" * 55,
            f" QUEST DOSSIER: {entry.name} {status_tag}",
            "=" * 55,
            f" Quest ID     : {entry.quest_id}",
            f" Status       : {entry.status_label}",
            f" Progress     : {entry.progress_bar} {entry.progress_percentage:.1f}% "
            f"({entry.completed_objectives_count}/{entry.total_objectives_count} objectives completed)",
            f" Description  : {entry.description}",
        ]

        prereq_str = ", ".join(entry.prerequisites) if entry.prerequisites else "None"
        lines.append(f" Prerequisites: {prereq_str}")
        if entry.chosen_paths:
            lines.append(f" Chosen Path  : {', '.join(entry.chosen_paths)}")

        lines.append("\n--- OBJECTIVES ---")
        if not entry.objectives:
            lines.append("  (No objectives defined for this quest.)")
        else:
            for idx, obj in enumerate(entry.objectives, 1):
                rem_str = f", {obj.remaining_count} remaining" if obj.remaining_count > 0 else ""
                lines.append(f" {obj.marker} {idx}. {obj.description}")
                lines.append(
                    f"     Count   : {obj.formatted_counts} units {obj.progress_bar} "
                    f"({obj.progress_percentage:.1f}%{rem_str})"
                )
                lines.append(f"     Status  : {obj.status_tag}")

        lines.append("\n--- REWARDS ---")
        lines.append(f" Items       : {entry.formatted_rewards}")
        if entry.can_claim_rewards:
            lines.append(" Claim Status: [!] READY TO CLAIM! (Claim from Journal or Quest menu)")
        elif entry.rewards_claimed:
            lines.append(" Claim Status: Claimed")
        elif entry.is_completed:
            lines.append(" Claim Status: Completed (No rewards to claim)")
        else:
            lines.append(" Claim Status: Incomplete (Complete all objectives to claim rewards)")

        lines.append("=" * 55)
        return lines

    def format_completion_notification(self, notification: QuestNotification) -> list[str]:
        """Formats a multi-line ASCII completion notification banner."""
        return notification.format_banner()

    def format_claim_result(
        self,
        result: QuestRewardResult,
        quest_name: Optional[str] = None,
    ) -> list[str]:
        """Formats human-readable feedback for a reward claim operation."""
        name = quest_name or result.quest_id.replace("_", " ").title()
        if result.success:
            if result.items_granted:
                items_str = ", ".join(
                    f"{cnt}x {it.replace('_', ' ').title()}"
                    for it, cnt in result.items_granted.items()
                )
                return [
                    f"[*] Claimed rewards for '{name}': {items_str}!",
                    "    Items have been safely added to your inventory.",
                ]
            return [
                f"[*] Claimed rewards for '{name}': None (No item rewards).",
                "    Quest officially completed!",
            ]
        return [
            f"[-] Could not claim rewards for '{name}': {result.message}",
        ]

