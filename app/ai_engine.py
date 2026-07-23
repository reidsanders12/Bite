"""
Client-side AI engine.

Every call in this file goes through the `gemini-proxy` Supabase Edge
Function (see supabase/functions/gemini-proxy/index.ts), not straight to
Gemini. Previously this called the google-genai SDK directly from the
user's device using a GEMINI_API_KEY embedded in the app's own .env --
which meant that key shipped inside every compiled build and anyone could
pull it back out and spend your quota outside the app entirely. The proxy
fixes that: the app builds the exact same request it always did (system
instruction, contents, generation config, response schema) and POSTs it to
the Edge Function instead, which holds the real key server-side, checks the
caller has a live Supabase session, enforces a per-user daily cap, and
forwards the request to Gemini on the app's behalf.

We NEVER accept free-form conversational text back from the food analysis
models. Requests set response_mime_type="application/json" and pass a
hand-converted Gemini Schema (see `_schema_for`) built from the MacroBreakdown
Pydantic model, so downstream parsing can skip writing any JSON-parsing /
regex defensive code. The AI Coach uses a standard text generation call with
local context injection and no schema (free-form reply).
"""

import asyncio
import base64
from typing import Optional, Type

import httpx
from pydantic import BaseModel

from app.config import SUPABASE_ANON_KEY, SUPABASE_URL
from app.models import MacroBreakdown, UserGoals, WorkoutEstimate, MealSuggestion, WorkoutPlan

MODEL_NAME = "gemini-2.5-flash"

_PROXY_URL = f"{SUPABASE_URL}/functions/v1/gemini-proxy"
_MAX_RETRIES = 3
_RETRY_BASE_DELAY_SECONDS = 2
_REQUEST_TIMEOUT_SECONDS = 30.0


class AIEngineError(Exception):
    """Raised on structural validation failures, proxy errors, or a missing session."""


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


# ------------------------------------------------------- SCHEMA CONVERSION

def _schema_for(model_cls: Type[BaseModel]) -> dict:
    """Converts a Pydantic model into Gemini's Schema format (a restricted,
    OpenAPI-flavored subset of JSON Schema: uppercase `type` enum, no
    `$ref`/`$defs` -- everything inlined, Optional[X] expressed as
    `nullable: true` instead of `anyOf`).

    Only supports the shapes actually used by this app's models: plain
    str/int/bool/float fields, `Optional[str]`-style nullable fields,
    `List[str]`, and `List[SubModel]` one level deep. It does not attempt to
    handle enums, unions beyond Optional, or deeper nesting -- extend this
    if a future model needs more.
    """
    raw = model_cls.model_json_schema()
    defs = raw.get("$defs", {})
    _TYPE_MAP = {
        "object": "OBJECT", "string": "STRING", "integer": "INTEGER",
        "number": "NUMBER", "boolean": "BOOLEAN", "array": "ARRAY",
    }

    def convert(node: dict) -> dict:
        if "$ref" in node:
            ref_name = node["$ref"].split("/")[-1]
            return convert(defs[ref_name])

        if "anyOf" in node:
            non_null = [n for n in node["anyOf"] if n.get("type") != "null"]
            converted = convert(non_null[0]) if non_null else {"type": "STRING"}
            converted["nullable"] = True
            return converted

        json_type = node.get("type", "object")
        out = {"type": _TYPE_MAP.get(json_type, "STRING")}
        if "description" in node:
            out["description"] = node["description"]

        if json_type == "object":
            props = node.get("properties", {})
            out["properties"] = {k: convert(v) for k, v in props.items()}
            if node.get("required"):
                out["required"] = node["required"]
        elif json_type == "array":
            out["items"] = convert(node.get("items", {}))

        return out

    return convert(raw)


def _extract(model_cls: Type[BaseModel], text: str):
    """Safely un-wraps and validates a JSON response body into a Pydantic model."""
    if not text:
        raise AIEngineError("The AI didn't return a response. Please try again.")
    try:
        return model_cls.model_validate_json(text)
    except Exception as exc:
        raise AIEngineError(
            f"The AI response couldn't be parsed as {model_cls.__name__}: {exc}"
        ) from exc


# --------------------------------------------------------------- PROXY CALL

async def _call_gemini(
    access_token: Optional[str],
    contents: list,
    system_instruction: str,
    temperature: float,
    response_mime_type: Optional[str] = None,
    response_schema_cls: Optional[Type[BaseModel]] = None,
) -> str:
    """POSTs a request to the gemini-proxy Edge Function and returns the
    generated text. Retries on 5xx (proxy or upstream Gemini transient
    failures); raises AIEngineError on anything else (missing session,
    rate limit, bad request)."""
    if not access_token:
        raise AIEngineError("You're not signed in -- please sign in again.")

    payload: dict = {
        "model": MODEL_NAME,
        "contents": contents,
        "system_instruction": system_instruction,
        "temperature": temperature,
    }
    if response_mime_type:
        payload["response_mime_type"] = response_mime_type
    if response_schema_cls:
        payload["response_schema"] = _schema_for(response_schema_cls)

    headers = {
        "Authorization": f"Bearer {access_token}",
        "apikey": SUPABASE_ANON_KEY,
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
        resp = None
        for attempt in range(_MAX_RETRIES):
            try:
                resp = await client.post(_PROXY_URL, json=payload, headers=headers)
            except httpx.HTTPError as exc:
                if attempt == _MAX_RETRIES - 1:
                    raise AIEngineError(f"Couldn't reach the AI service: {exc}") from exc
                await asyncio.sleep(_RETRY_BASE_DELAY_SECONDS * (2 ** attempt))
                continue

            if resp.status_code == 429:
                detail = _safe_error_detail(resp)
                raise AIEngineError(detail or "Daily AI request limit reached. Try again tomorrow.")
            if resp.status_code == 401:
                raise AIEngineError("Your session expired -- please sign in again.")
            if resp.status_code >= 500 and attempt < _MAX_RETRIES - 1:
                await asyncio.sleep(_RETRY_BASE_DELAY_SECONDS * (2 ** attempt))
                continue
            if resp.status_code >= 400:
                detail = _safe_error_detail(resp)
                raise AIEngineError(detail or f"AI request failed ({resp.status_code}).")
            break

    data = resp.json()
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError):
        raise AIEngineError("The AI didn't return a usable response. Please try again.")


def _safe_error_detail(resp: httpx.Response) -> Optional[str]:
    try:
        return resp.json().get("error")
    except Exception:
        return None


# ------------------------------------------------------------- CORE ANALYSIS LOGS

async def analyze_image(photo_bytes: bytes, access_token: str) -> MacroBreakdown:
    """Send raw photo bytes to Gemini (via the proxy) for strict Pydantic parsing."""
    b64 = base64.b64encode(photo_bytes).decode("ascii")
    contents = [{
        "role": "user",
        "parts": [
            {"inlineData": {"mimeType": "image/jpeg", "data": b64}},
            {"text": _IMAGE_INSTRUCTION},
        ],
    }]
    try:
        text = await _call_gemini(
            access_token, contents, _SYSTEM_PROMPT, temperature=0.2,
            response_mime_type="application/json", response_schema_cls=MacroBreakdown,
        )
    except AIEngineError:
        raise
    except Exception as exc:
        raise AIEngineError(f"AI photo analysis failed: {exc}") from exc

    return _extract(MacroBreakdown, text)


async def analyze_audio(audio_bytes: bytes, access_token: str, mime_type: str = "audio/wav") -> MacroBreakdown:
    """Send a raw voice-log recording to Gemini (via the proxy) for structured parsing.

    Gemini transcribes and interprets the speech in a single multimodal call
    -- same "AI does the heavy lifting" pattern as analyze_image, just with
    an audio Part instead of an image Part.
    """
    b64 = base64.b64encode(audio_bytes).decode("ascii")
    contents = [{
        "role": "user",
        "parts": [
            {"inlineData": {"mimeType": mime_type, "data": b64}},
            {"text": _AUDIO_INSTRUCTION},
        ],
    }]
    try:
        text = await _call_gemini(
            access_token, contents, _SYSTEM_PROMPT, temperature=0.2,
            response_mime_type="application/json", response_schema_cls=MacroBreakdown,
        )
    except AIEngineError:
        raise
    except Exception as exc:
        raise AIEngineError(f"AI audio analysis failed: {exc}") from exc
    return _extract(MacroBreakdown, text)


async def analyze_text(text: str, access_token: str) -> MacroBreakdown:
    """Send a natural-language food description to Gemini (via the proxy, text-only, cheap) for parsing."""
    prompt = _TEXT_INSTRUCTION_TEMPLATE.format(text=text)
    contents = [{"role": "user", "parts": [{"text": prompt}]}]
    try:
        response_text = await _call_gemini(
            access_token, contents, _SYSTEM_PROMPT, temperature=0.2,
            response_mime_type="application/json", response_schema_cls=MacroBreakdown,
        )
    except AIEngineError:
        raise
    except Exception as exc:
        raise AIEngineError(f"AI text analysis failed: {exc}") from exc
    return _extract(MacroBreakdown, response_text)


async def analyze_workout(text: str, access_token: str, weight_kg: float = None) -> WorkoutEstimate:
    """Send a natural-language workout description to Gemini (via the proxy) for a calories-burned estimate."""
    weight_clause = f"The person weighs approximately {weight_kg:.0f}kg. " if weight_kg else ""
    prompt = _WORKOUT_INSTRUCTION_TEMPLATE.format(weight_clause=weight_clause, text=text)
    contents = [{"role": "user", "parts": [{"text": prompt}]}]
    try:
        response_text = await _call_gemini(
            access_token, contents, _WORKOUT_SYSTEM_PROMPT, temperature=0.2,
            response_mime_type="application/json", response_schema_cls=WorkoutEstimate,
        )
    except AIEngineError:
        raise
    except Exception as exc:
        raise AIEngineError(f"AI workout analysis failed: {exc}") from exc

    return _extract(WorkoutEstimate, response_text)


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
    access_token: str,
    workout_goals: str = "",
) -> MealSuggestion:
    """One-shot structured meal suggestion for the coach screen's "Suggest a meal"
    button. Unlike chat_with_coach, this forces a response_schema so the
    UI always gets a clean, consistently-shaped card instead of free-form prose.
    """
    context = _build_coach_context(totals, goals, workout_goals=workout_goals)
    prompt = f"{context}{_MEAL_SUGGESTION_INSTRUCTION}"
    contents = [{"role": "user", "parts": [{"text": prompt}]}]
    try:
        response_text = await _call_gemini(
            access_token, contents, _COACH_SYSTEM_PROMPT, temperature=0.4,
            response_mime_type="application/json", response_schema_cls=MealSuggestion,
        )
    except AIEngineError:
        raise
    except Exception as exc:
        raise AIEngineError(f"AI meal suggestion failed: {exc}") from exc

    return _extract(MealSuggestion, response_text)


async def suggest_workout(
    totals: dict,
    goals: UserGoals,
    access_token: str,
    workout_goals: str = "",
    workouts_summary: str = "",
    weight_trend_summary: str = "",
) -> WorkoutPlan:
    """One-shot structured workout plan for the coach screen's "Suggest a workout"
    button. Forces a response_schema for the same reason as suggest_meal.
    """
    context = _build_coach_context(
        totals, goals, workout_goals=workout_goals,
        workouts_summary=workouts_summary, weight_trend_summary=weight_trend_summary,
    )
    prompt = f"{context}{_WORKOUT_PLAN_INSTRUCTION}"
    contents = [{"role": "user", "parts": [{"text": prompt}]}]
    try:
        response_text = await _call_gemini(
            access_token, contents, _COACH_SYSTEM_PROMPT, temperature=0.4,
            response_mime_type="application/json", response_schema_cls=WorkoutPlan,
        )
    except AIEngineError:
        raise
    except Exception as exc:
        raise AIEngineError(f"AI workout plan request failed: {exc}") from exc

    return _extract(WorkoutPlan, response_text)


async def chat_with_coach(
    user_message: str,
    history: list,
    totals: dict,
    goals: UserGoals,
    access_token: str,
    workout_goals: str = "",
    workouts_summary: str = "",
    weight_trend_summary: str = "",
) -> str:
    """Runs a free conversational fitness consultation via the proxy.

    Injects local database macro state (including how much of today's budget
    is left, adjusted for any exercise calories logged today), the user's
    stated fitness goals, today's logged workouts, and their weight trend --
    so the coach reasons about the whole picture, not just food macros.
    """
    context_prefix = (
        _build_coach_context(totals, goals, workout_goals, workouts_summary, weight_trend_summary)
        + "Answer the user's question with these metrics explicitly in mind."
    )

    contents = []
    for turn in history[-6:]:  # Rolling memory window to keep context tight and fast
        role = "user" if turn["is_user"] else "model"
        contents.append({"role": role, "parts": [{"text": turn["text"]}]})

    contents.append({
        "role": "user",
        "parts": [{"text": f"{context_prefix}\n\nUser: {user_message}"}],
    })

    try:
        text = await _call_gemini(access_token, contents, _COACH_SYSTEM_PROMPT, temperature=0.7)
        return text if text else "Coach couldn't process that response."
    except AIEngineError:
        raise
    except Exception as exc:
        raise AIEngineError(f"Trainer chat failed: {exc}") from exc
