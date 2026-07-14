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

from app.models import MacroBreakdown, UserGoals

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


def _get_client() -> genai.Client:
    """Initializes the standard client with the configuration key."""
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise AIEngineError("Gemini API key missing. Please verify your app/config.py settings.")
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
        raise AIEngineError("Gemini returned an empty response.")
    try:
        return MacroBreakdown.model_validate_json(txt)
    except Exception as exc:
        raise AIEngineError(
            f"Gemini returned a response that couldn't be parsed as a macro breakdown: {exc}"
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
        raise AIEngineError(f"Gemini multimodal photo request failed: {exc}") from exc
        
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
        raise AIEngineError(f"Gemini text request failed: {exc}") from exc
    return _extract(response)


# ----------------------------------------------------------------- AI COACH SYSTEM

async def chat_with_coach(
    user_message: str,
    history: list,
    totals: dict,
    goals: UserGoals,
    workout_goals: str = "",
) -> str:
    """Runs a free conversational fitness consultation directly on the client device.

    Injects local database macro state (including how much of today's budget
    is left) plus the user's stated fitness goals, to give the AI context on
    both what they can still eat today and what they're training for.
    """
    client = _get_client()

    remaining_cal = goals.daily_calories - totals['calories']
    remaining_pro = goals.daily_protein - totals['protein']
    remaining_carb = goals.daily_carbs - totals['carbs']
    remaining_fat = goals.daily_fat - totals['fat']

    # 1. Synthesize current fitness context from cloud database metrics
    context_prefix = (
        f"[CURRENT LOGGED STATS FOR TODAY]:\n"
        f"- Calories: {totals['calories']} consumed / {goals.daily_calories} target / {remaining_cal} remaining kcal\n"
        f"- Protein: {totals['protein']}g consumed / {goals.daily_protein}g target / {remaining_pro}g remaining\n"
        f"- Carbs: {totals['carbs']}g consumed / {goals.daily_carbs}g target / {remaining_carb}g remaining\n"
        f"- Fat: {totals['fat']}g consumed / {goals.daily_fat}g target / {remaining_fat}g remaining\n\n"
        + (f"[USER'S STATED FITNESS GOALS]: {workout_goals}\n\n" if workout_goals.strip() else "")
        + f"Answer the user's question with these metrics explicitly in mind."
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