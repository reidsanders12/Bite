"""
Pydantic data models used across the app.

MacroBreakdown / FoodItem are the exact structured-output contract we force
Gemini to respond with (see app/ai_engine.py). Keeping this schema strict and
small is what lets us skip writing any JSON-parsing / regex defensive code
downstream -- Gemini simply cannot return anything else.
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class FoodItem(BaseModel):
    name: str = Field(description="Name of the individual ingredient or food item")
    portion_size: str = Field(
        description="Estimated weight or volume (e.g., '150g', '2 tablespoons')"
    )


class MacroBreakdown(BaseModel):
    meal_name: str = Field(description="A clean, concise overall name for the meal")
    calories: int = Field(description="Total estimated calories for the entire image portion")
    protein: int = Field(description="Total protein in grams")
    carbs: int = Field(description="Total carbohydrates in grams")
    fat: int = Field(description="Total fat in grams")
    identified_items: List[FoodItem] = Field(
        default_factory=list, description="List of distinct food items found in the image"
    )

    def scaled(self, factor: float) -> "MacroBreakdown":
        """Return a new MacroBreakdown with macros scaled by `factor`.

        Used by the Correction Slider (0.5x - 2.0x) to recalculate portions
        entirely on-device, with zero additional API calls.
        """
        return MacroBreakdown(
            meal_name=self.meal_name,
            calories=round(self.calories * factor),
            protein=round(self.protein * factor),
            carbs=round(self.carbs * factor),
            fat=round(self.fat * factor),
            identified_items=self.identified_items,
        )


class WorkoutEstimate(BaseModel):
    workout_name: str = Field(description="A clean, concise name for the workout")
    duration_minutes: int = Field(description="Estimated duration of the workout in minutes")
    calories_burned: int = Field(description="Estimated total calories burned during the workout")


class UserGoals(BaseModel):
    daily_calories: int = 2200
    daily_protein: int = 150
    daily_carbs: int = 220
    daily_fat: int = 70


class Circle(BaseModel):
    id: int
    name: str
    goal_description: str
    # 'custom' (manual check-in), 'workout' (auto check-in on any workout
    # log), or 'calories' (auto check-in once today's calories >= goal_value).
    goal_type: str = "custom"
    goal_value: Optional[int] = None
    invite_code: str
    created_by: str


class CircleMemberStatus(BaseModel):
    user_id: str
    display_name: str
    checked_in_today: bool = False
    streak_days: int = 0
