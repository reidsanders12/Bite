import sqlite3
from typing import List, Any

class Database:
    def __init__(self, db_path: str = "bite_tracker.db"):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Track daily logs with a unique auto-incrementing ID
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS food_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    meal_name TEXT NOT NULL,
                    calories INTEGER NOT NULL,
                    protein INTEGER NOT NULL,
                    carbs INTEGER NOT NULL,
                    fat INTEGER NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def log_food(self, name: str, cal: int, pro: int, carb: int, fat: int):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO food_logs (meal_name, calories, protein, carbs, fat)
                VALUES (?, ?, ?, ?, ?)
            """, (name, cal, pro, carb, fat))
            conn.commit()

    def get_daily_logs(self) -> List[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row  # Return rows as dictionary-accessible items
            cursor = conn.cursor()
            # Grab everything sorted by newest first
            cursor.execute("SELECT id, meal_name, calories, protein, carbs, fat FROM food_logs ORDER BY id DESC")
            return [dict(row) for row in cursor.fetchall()]

    def delete_log_entry(self, entry_id: int):
        """Removes a specific meal instance from your SQL storage block."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM food_logs WHERE id = ?", (entry_id,))
            conn.commit()