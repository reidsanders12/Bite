"""
Client-side AI engine.

Every call in this file runs the Gemini request directly from the user's own
device using their own free-tier API key (read from the GEMINI_API_KEY
environment variable, set via the Settings view). There is no proxy server
in between -- this is the piece that makes "$0 infrastructure at scale"
possible: Google, not us, pays for (and rate-limits) the inference.

We NEVER accept free-form conversational text back from the model. Every
request sets response_mime_type="application/json" and passes the
MacroBreakdown Pydantic model directly as response_schema, so the SDK
validates and parses the structured output for us before it ever reaches
the UI layer.
"""

import os

from google import genai
from google.genai import types

from app.models import MacroBreakdown

MODEL_NAME = "gemini-2.5-flash"

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
    "for the entire plate/meal shown."
)

_TEXT_INSTRUCTION_TEMPLATE = (
    "Parse the following natural-language food log into a macro breakdown. "
    "Treat each mentioned food/quantity as one identified item.\n\n"
    'User log: "{text}"'
)


class AIEngineError(Exception):
    """Raised for any missing-key / network / parsing failure talking to Gemini."""


def _get_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise AIEngineError(
            "No Gemini API key configured. Add your free API key in Settings "
            "to enable AI photo and text logging."
        )
    return genai.Client(api_key=api_key)


def _config() -> types.GenerateContentConfig:
    return types.GenerateContentConfig(
        system_instruction=_SYSTEM_PROMPT,
        response_mime_type="application/json",
        response_schema=MacroBreakdown,
    )


def _extract(response: types.GenerateContentResponse) -> MacroBreakdown:
    # The SDK will populate `.parsed` automatically when response_schema is a
    # Pydantic model and the model's JSON validates against it.
    if getattr(response, "parsed", None) is not None:
        return response.parsed
    # Fall back to manual validation in case `.parsed` isn't populated for
    # any SDK-version reason -- response.text is still guaranteed JSON.
    try:
        return MacroBreakdown.model_validate_json(response.text)
    except Exception as exc:  # noqa: BLE001 - surfaced to the user as a friendly error
        raise AIEngineError(
            f"Gemini returned a response that couldn't be parsed as a macro breakdown: {exc}"
        ) from exc


async def analyze_image(image_bytes: bytes, mime_type: str = "image/jpeg") -> MacroBreakdown:
    """Send a food photo to Gemini Flash and get back a structured macro breakdown."""
    client = _get_client()
    try:
        response = await client.aio.models.generate_content(
            model=MODEL_NAME,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                _IMAGE_INSTRUCTION,
            ],
            config=_config(),
        )
    except AIEngineError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise AIEngineError(f"Gemini request failed: {exc}") from exc
    return _extract(response)


async def analyze_text(text: str) -> MacroBreakdown:
    """Send a natural-language food description to Gemini (text-only, cheap) for parsing."""
    client = _get_client()
    prompt = _TEXT_INSTRUCTION_TEMPLATE.format(text=text)
    try:
        response = await client.aio.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=_config(),
        )
    except AIEngineError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise AIEngineError(f"Gemini request failed: {exc}") from exc
    return _extract(response)
