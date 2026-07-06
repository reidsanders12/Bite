"""
Local-only persistence layer.

Everything the app needs to remember (daily macro goals + the food log
history) lives in a single SQLite file on-device. There is no server, no
cloud database, and no per-user account -- this is what keeps infra cost at
literally $0 as the user base grows.

SQLite operations here are synchronous. That's intentional: local disk I/O
on a tiny SQLite file is on the order of microseconds-to-low-milliseconds,
so calling it directly from an async Flet event handler will not noticeably
block the UI thread. Wrapping every call in asyncio.to_thread would only add
complexity for no real benefit at this scale.
"""

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterator, List, Optional

from app.models import FoodItem, MacroBreakdown, UserGoals

DEFAULT_DB_PATH = Path.home() / ".macro_tracker" / "macro_tracker.db"


@dataclass
class LogEntry:
    id: int
    logged_at: str  # ISO timestamp
    meal_name: str
    calories: int
    protein: int
    carbs: int
    fat: int
    source: str  # "photo" | "text" | "barcode"
    scale_factor: float
    identified_items: List[FoodItem]

    @property
    def log_date(self) -> str:
        return self.logged_at[:10]


class Database:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS goals (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    daily_calories INTEGER NOT NULL,
                    daily_protein INTEGER NOT NULL,
                    daily_carbs INTEGER NOT NULL,
                    daily_fat INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    logged_at TEXT NOT NULL,
                    meal_name TEXT NOT NULL,
                    calories INTEGER NOT NULL,
                    protein INTEGER NOT NULL,
                    carbs INTEGER NOT NULL,
                    fat INTEGER NOT NULL,
                    source TEXT NOT NULL,
                    scale_factor REAL NOT NULL DEFAULT 1.0,
                    identified_items_json TEXT NOT NULL DEFAULT '[]'
                )
                """
            )

    # ---------------------------------------------------------------- goals
    def get_goals(self) -> UserGoals:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM goals WHERE id = 1").fetchone()
        if row is None:
            return UserGoals()
        return UserGoals(
            daily_calories=row["daily_calories"],
            daily_protein=row["daily_protein"],
            daily_carbs=row["daily_carbs"],
            daily_fat=row["daily_fat"],
        )

    def save_goals(self, goals: UserGoals) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO goals (id, daily_calories, daily_protein, daily_carbs, daily_fat)
                VALUES (1, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    daily_calories = excluded.daily_calories,
                    daily_protein = excluded.daily_protein,
                    daily_carbs = excluded.daily_carbs,
                    daily_fat = excluded.daily_fat
                """,
                (goals.daily_calories, goals.daily_protein, goals.daily_carbs, goals.daily_fat),
            )

    # ----------------------------------------------------------------- logs
    def add_log(
        self,
        breakdown: MacroBreakdown,
        source: str,
        scale_factor: float = 1.0,
        logged_at: Optional[datetime] = None,
    ) -> int:
        ts = (logged_at or datetime.now()).isoformat(timespec="seconds")
        items_json = json.dumps([item.model_dump() for item in breakdown.identified_items])
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO logs
                    (logged_at, meal_name, calories, protein, carbs, fat, source, scale_factor, identified_items_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ts,
                    breakdown.meal_name,
                    breakdown.calories,
                    breakdown.protein,
                    breakdown.carbs,
                    breakdown.fat,
                    source,
                    scale_factor,
                    items_json,
                ),
            )
            return cur.lastrowid

    def delete_log(self, log_id: int) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM logs WHERE id = ?", (log_id,))

    def get_logs_for_date(self, day: Optional[date] = None) -> List[LogEntry]:
        day = day or date.today()
        prefix = day.isoformat()
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM logs WHERE logged_at LIKE ? ORDER BY logged_at DESC",
                (f"{prefix}%",),
            ).fetchall()
        return [self._row_to_entry(row) for row in rows]

    def get_totals_for_date(self, day: Optional[date] = None) -> dict:
        entries = self.get_logs_for_date(day)
        return {
            "calories": sum(e.calories for e in entries),
            "protein": sum(e.protein for e in entries),
            "carbs": sum(e.carbs for e in entries),
            "fat": sum(e.fat for e in entries),
        }

    def get_recent_dates(self, limit: int = 14) -> List[str]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT substr(logged_at, 1, 10) AS d
                FROM logs
                ORDER BY d DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [row["d"] for row in rows]

    @staticmethod
    def _row_to_entry(row: sqlite3.Row) -> LogEntry:
        items_raw = json.loads(row["identified_items_json"])
        items = [FoodItem(**item) for item in items_raw]
        return LogEntry(
            id=row["id"],
            logged_at=row["logged_at"],
            meal_name=row["meal_name"],
            calories=row["calories"],
            protein=row["protein"],
            carbs=row["carbs"],
            fat=row["fat"],
            source=row["source"],
            scale_factor=row["scale_factor"],
            identified_items=items,
        )
