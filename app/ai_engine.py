"""
Client-side AI engine.

Every call in this file runs the Gemini request directly from the user's own
device using their own free-tier API key (read from the GEMINI_API_KEY
environment variable, loaded instantly from app.config). There is no proxy server
in between -- this is the piece that makes "$0 infrastructure at scale"
possible: Google, not us, pays for (and rate-limits) the inference.

We NEVER accept free-form conversational text back from the food analysis models. 
Requests set response_mime_type="application/json" and pass the MacroBreakdown 
Pydantic model directly as response_schema. The AI Coach utilizes a standard 
text generation stream wrapped with local context injection.
"""

import os
import json
import asyncio
from typing import List
from google import genai
from google.genai import types, errors

from app.models import MacroBreakdown, UserGoals, WorkoutEstimate, MealSuggestion, WorkoutPlan

MODEL_NAME = "gemini-2.5-flash"

_MAX_RETRIES = 3
_RETRY_BASE_DELAY_SECONDS = 2

class AIEngineError(Exception):
    """Raised on structural validation failures or API errors."""


_SYSTEM_PROMPT = (
    "You are a precise nutrition-estimation assistant embedded in a calorie "
    "tracking app. Always respond with your best numeric estimate even if "
    "you are uncertain -- never refuse and never ask a clarifying question. "
    "Estimate realistic portion sizes and standard macro values per typical "
    "preparation of each food. Round calories/protein/carbs/fat to whole "
    "numbers of kcal/grams."
)

_IMAGE_INSTRUCTION = (
    "Analyze the food shown in this photo. Identify each distinct food item, "
    "estimate its portion size, and produce one aggregated macro breakdown "
    "for the entire plate/meal shown. Provide an appropriate descriptive meal_name."
)

_TEXT_INSTRUCTION_TEMPLATE = (
    "Parse the following natural-language description of a meal or ingredient. "
    "Identify individual items and calculate an accurate aggregated macro breakdown:\n\n"
    "\"\"\"\n{text}\n\"\"\""
)

_AUDIO_INSTRUCTION = (
    "This is a voice recording of someone describing a meal or ingredient "
    "they just ate. Transcribe what they said, identify individual food "
    "items, and produce one aggregated macro breakdown for everything "
    "described. Provide an appropriate descriptive meal_name."
)

_WORKOUT_SYSTEM_PROMPT = (
    "You are a precise exercise-physiology estimation assistant embedded in a "
    "fitness tracking app. Always respond with your best numeric estimate even "
    "if you are uncertain -- never refuse and never ask a clarifying question. "
    "Estimate realistic calories burned using standard MET (metabolic "
    "equivalent) values for the activity described, scaled by the person's "
    "body weight (assume an average adult of about 70kg if none is given) and "
    "the stated or implied duration. Round duration and calories to whole "
    "numbers."
)

_WORKOUT_INSTRUCTION_TEMPLATE = (
    "Estimate calories burned for this workout description. {weight_clause}"
    "If a duration is stated or implied in the description, use it; otherwise "
    "estimate a typical duration for this kind of session.\n\n"
    "\"\"\"\n{text}\n\"\"\""
)

_COACH_SYSTEM_PROMPT = (
    "You are an elite sports nutritionist and personal fitness trainer. "
    "You are direct, highly supportive, evidence-based, and concise. "
    "You have full access to the user's current daily macro stats, target goals, "
    "and remaining macro budget for today. When asked for a meal, only suggest "
    "meals that realistically fit within the user's REMAINING calories/macros for "
    "today -- do not suggest something that would blow their budget. When asked "
    "for a workout, build it around the user's stated fitness goals (if given) "
    "and today's remaining energy/protein. Provide actionable advice, programming "
    "tweaks, or recipe ideas based on their actual day. Always wrap nutritional or "
    "training data points clearly."
)

_MEAL_SUGGESTION_INSTRUCTION = (
    "Suggest ONE specific meal or snack the user could eat right now. It must "
    "realistically fit within the remaining calories and macros shown above -- "
    "never exceed the remaining budget. Give a short one-to-two sentence rationale "
    "tying the choice to their remaining macros and stated goals, and list concrete "
    "ingredients with rough quantities."
)

_WORKOUT_PLAN_INSTRUCTION = (
    "Build ONE workout session for today. Tailor it to the user's stated fitness "
    "goals (if given) and their remaining energy/protein for today. Give a short "
    "one-to-two sentence rationale, then a concrete ordered list of exercises with "
    "sets and reps (or duration for timed/cardio work)."
)


def _get_client() -> genai.Client:
    """Initializes the standard client with the configuration key."""
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise AIEngineError("AI API key missing. Please verify your app/config.py settings.")
    return genai.Client(api_key=api_key)


def _config() -> types.GenerateContentConfig:
    """Shared rigid configuration template for the structured food analysis workflows."""
    return types.GenerateContentConfig(
        system_instruction=_SYSTEM_PROMPT,
        temperature=0.2,
        response_mime_type="application/json",
        response_schema=MacroBreakdown,
    )


async def _generate_with_retry(client: genai.Client, **kwargs) -> types.GenerateContentResponse:
    """Calls generate_content, retrying on transient 503 (model overloaded) errors."""
    for attempt in range(_MAX_RETRIES):
        try:
            return await client.aio.models.generate_content(**kwargs)
        except errors.ServerError:
            if attempt == _MAX_RETRIES - 1:
                raise
            await asyncio.sleep(_RETRY_BASE_DELAY_SECONDS * (2 ** attempt))


def _extract(response: types.GenerateContentResponse) -> MacroBreakdown:
    """Safely un-wraps and validates JSON structures returning an absolute data model."""
    txt = response.text
    if not txt:
        raise AIEngineError("The AI didn't return a response. Please try again.")
    try:
        return MacroBreakdown.model_validate_json(txt)
    except Exception as exc:
        raise AIEngineError(
            f"The AI response couldn't be parsed as a macro breakdown: {exc}"
        ) from exc


# ------------------------------------------------------------- CORE ANALYSIS LOGS

async def analyze_image(photo_bytes: bytes) -> MacroBreakdown:
    """Send raw photo bytes to Gemini asynchronously for strict Pydantic parsing."""
    client = _get_client()
    try:
        # Construct the official binary Part object required by the new SDK
        image_part = types.Part.from_bytes(
            data=photo_bytes,
            mime_type="image/jpeg"
        )
        
        # Use your native async pipeline wrapper (.aio), retrying transient 503s
        response = await _generate_with_retry(
            client,
            model=MODEL_NAME,
            contents=[image_part, _IMAGE_INSTRUCTION],
            config=_config() # Uses your rigorous predefined Pydantic schema rule
        )
    except Exception as exc:
        raise AIEngineError(f"AI photo analysis failed: {exc}") from exc
        
    return _extract(response)


async def analyze_audio(audio_bytes: bytes, mime_type: str = "audio/wav") -> MacroBreakdown:
    """Send a raw voice-log recording to Gemini for structured Pydantic parsing.

    Gemini transcribes and interprets the speech in a single multimodal call
    -- same "AI does the heavy lifting" pattern as analyze_image, just with
    an audio Part instead of an image Part.
    """
    client = _get_client()
    try:
        audio_part = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)
        response = await _generate_with_retry(
            client,
            model=MODEL_NAME,
            contents=[audio_part, _AUDIO_INSTRUCTION],
            config=_config(),
        )
    except Exception as exc:
        raise AIEngineError(f"AI audio analysis failed: {exc}") from exc
    return _extract(response)


async def analyze_text(text: str) -> MacroBreakdown:
    """Send a natural-language food description to Gemini (text-only, cheap) for parsing."""
    client = _get_client()
    prompt = _TEXT_INSTRUCTION_TEMPLATE.format(text=text)
    try:
        response = await _generate_with_retry(
            client,
            model=MODEL_NAME,
            contents=prompt,
            config=_config(),
        )
    except AIEngineError:
        raise
    except Exception as exc:
        raise AIEngineError(f"AI text analysis failed: {exc}") from exc
    return _extract(response)


async def analyze_workout(text: str, weight_kg: float = None) -> WorkoutEstimate:
    """Send a natural-language workout description to Gemini for a calories-burned estimate."""
    client = _get_client()
    weight_clause = f"The person weighs approximately {weight_kg:.0f}kg. " if weight_kg else ""
    prompt = _WORKOUT_INSTRUCTION_TEMPLATE.format(weight_clause=weight_clause, text=text)
    try:
        response = await _generate_with_retry(
            client,
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=_WORKOUT_SYSTEM_PROMPT,
                temperature=0.2,
                response_mime_type="application/json",
                response_schema=WorkoutEstimate,
            ),
        )
    except AIEngineError:
        raise
    except Exception as exc:
        raise AIEngineError(f"AI workout analysis failed: {exc}") from exc

    txt = response.text
    if not txt:
        raise AIEngineError("The AI didn't return a response. Please try again.")
    try:
        return WorkoutEstimate.model_validate_json(txt)
    except Exception as exc:
        raise AIEngineError(
            f"The AI response couldn't be parsed as a workout estimate: {exc}"
        ) from exc


# ----------------------------------------------------------------- AI COACH SYSTEM

def _build_coach_context(
    totals: dict,
    goals: UserGoals,
    workout_goals: str = "",
    workouts_summary: str = "",
    weight_trend_summary: str = "",
) -> str:
    """Synthesizes the shared '[CURRENT LOGGED STATS FOR TODAY]' block injected
    into every coach request (free-form chat, meal suggestions, workout plans),
    so all three reason from the exact same local database state.
    """
    remaining_cal = goals.daily_calories - totals['calories']
    remaining_pro = goals.daily_protein - totals['protein']
    remaining_carb = goals.daily_carbs - totals['carbs']
    remaining_fat = goals.daily_fat - totals['fat']

    return (
        f"[CURRENT LOGGED STATS FOR TODAY]:\n"
        f"- Calories: {totals['calories']} consumed / {goals.daily_calories} target / {remaining_cal} remaining kcal\n"
        f"- Protein: {totals['protein']}g consumed / {goals.daily_protein}g target / {remaining_pro}g remaining\n"
        f"- Carbs: {totals['carbs']}g consumed / {goals.daily_carbs}g target / {remaining_carb}g remaining\n"
        f"- Fat: {totals['fat']}g consumed / {goals.daily_fat}g target / {remaining_fat}g remaining\n"
        + (f"- Workouts today: {workouts_summary}\n" if workouts_summary.strip() else "")
        + (f"- Weight trend: {weight_trend_summary}\n" if weight_trend_summary.strip() else "")
        + "\n"
        + (f"[USER'S STATED FITNESS GOALS]: {workout_goals}\n\n" if workout_goals.strip() else "")
    )


async def suggest_meal(
    totals: dict,
    goals: UserGoals,
    workout_goals: str = "",
) -> MealSuggestion:
    """One-shot structured meal suggestion for the coach screen's "Suggest a meal"
    button. Unlike chat_with_coach, this forces a Pydantic response_schema so the
    UI always gets a clean, consistently-shaped card instead of free-form prose.
    """
    client = _get_client()
    context = _build_coach_context(totals, goals, workout_goals=workout_goals)
    prompt = f"{context}{_MEAL_SUGGESTION_INSTRUCTION}"
    try:
        response = await _generate_with_retry(
            client,
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=_COACH_SYSTEM_PROMPT,
                temperature=0.4,
                response_mime_type="application/json",
                response_schema=MealSuggestion,
            ),
        )
    except Exception as exc:
        raise AIEngineError(f"AI meal suggestion failed: {exc}") from exc

    txt = response.text
    if not txt:
        raise AIEngineError("The AI didn't return a response. Please try again.")
    try:
        return MealSuggestion.model_validate_json(txt)
    except Exception as exc:
        raise AIEngineError(
            f"The AI response couldn't be parsed as a meal suggestion: {exc}"
        ) from exc


async def suggest_workout(
    totals: dict,
    goals: UserGoals,
    workout_goals: str = "",
    workouts_summary: str = "",
    weight_trend_summary: str = "",
) -> WorkoutPlan:
    """One-shot structured workout plan for the coach screen's "Suggest a workout"
    button. Forces a Pydantic response_schema for the same reason as suggest_meal.
    """
    client = _get_client()
    context = _build_coach_context(
        totals,
        goals,
        workout_goals=workout_goals,
        workouts_summary=workouts_summary,
        weight_trend_summary=weight_trend_summary,
    )
    prompt = f"{context}{_WORKOUT_PLAN_INSTRUCTION}"
    try:
        response = await _generate_with_retry(
            client,
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=_COACH_SYSTEM_PROMPT,
                temperature=0.4,
                response_mime_type="application/json",
                response_schema=WorkoutPlan,
            ),
        )
    except Exception as exc:
        raise AIEngineError(f"AI workout plan request failed: {exc}") from exc

    txt = response.text
    if not txt:
        raise AIEngineError("The AI didn't return a response. Please try again.")
    try:
        return WorkoutPlan.model_validate_json(txt)
    except Exception as exc:
        raise AIEngineError(
            f"The AI response couldn't be parsed as a workout plan: {exc}"
        ) from exc


async def chat_with_coach(
    user_message: str,
    history: list,
    totals: dict,
    goals: UserGoals,
    workout_goals: str = "",
    workouts_summary: str = "",
    weight_trend_summary: str = "",
) -> str:
    """Runs a free conversational fitness consultation directly on the client device.

    Injects local database macro state (including how much of today's budget
    is left, adjusted for any exercise calories logged today), the user's
    stated fitness goals, today's logged workouts, and their weight trend --
    so the coach reasons about the whole picture, not just food macros.
    """
    client = _get_client()

    # 1. Synthesize current fitness context from cloud database metrics
    context_prefix = (
        _build_coach_context(totals, goals, workout_goals, workouts_summary, weight_trend_summary)
        + "Answer the user's question with these metrics explicitly in mind."
    )

    # 2. Build explicit conversation history for Gemini API
    contents = []
    for turn in history[-6:]:  # Rolling memory window to keep context tight and fast
        role = "user" if turn["is_user"] else "model"
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=turn["text"])]))
        
    # Append the newest message with the injected local context header
    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=f"{context_prefix}\n\nUser: {user_message}")]))
    
    try:
        response = await client.aio.models.generate_content(
            model=MODEL_NAME,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=_COACH_SYSTEM_PROMPT,
                temperature=0.7
            )
        )
        return response.text if response.text else "Coach couldn't process that response."
    except Exception as exc:
        raise AIEngineError(f"Trainer chat failed: {exc}") from exc