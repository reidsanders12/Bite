"""
Small shared, in-memory state object.

Flet rebuilds view contents on every route change, so anything that needs to
survive a navigation (the AI result awaiting confirmation, cached goals, the
open Database handle) lives here instead of inside a single view class.
"""

from dataclasses import dataclass, field
from typing import Optional

from app.database import Database
from app.models import MacroBreakdown, UserGoals


@dataclass
class AppState:
    db: Database = field(default_factory=Database)
    goals: UserGoals = field(default_factory=UserGoals)

    # Set right before navigating to /confirm; cleared after save/discard.
    pending_breakdown: Optional[MacroBreakdown] = None
    pending_source: str = "photo"  # "photo" | "text" | "barcode"

    def __post_init__(self):
        self.goals = self.db.get_goals()

    def refresh_goals(self) -> None:
        self.goals = self.db.get_goals()

    def set_pending(self, breakdown: MacroBreakdown, source: str) -> None:
        self.pending_breakdown = breakdown
        self.pending_source = source

    def clear_pending(self) -> None:
        self.pending_breakdown = None
