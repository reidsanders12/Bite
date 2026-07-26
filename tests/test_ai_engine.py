"""
Unit tests for the pure, network-free parts of app/ai_engine.py:
Pydantic -> Gemini schema conversion and JSON response extraction.
"""
import pytest

from app import ai_engine
from app.models import MacroBreakdown, WorkoutExercise, WorkoutPlan


def test_schema_for_flat_model_maps_basic_types():
    schema = ai_engine._schema_for(MacroBreakdown)

    assert schema["type"] == "OBJECT"
    props = schema["properties"]
    assert props["meal_name"]["type"] == "STRING"
    assert props["calories"]["type"] == "INTEGER"
    assert props["identified_items"]["type"] == "ARRAY"
    assert set(schema["required"]) >= {"meal_name", "calories", "protein", "carbs", "fat"}


def test_schema_for_resolves_nested_refs_and_arrays():
    schema = ai_engine._schema_for(WorkoutPlan)

    exercises = schema["properties"]["exercises"]
    assert exercises["type"] == "ARRAY"
    item_schema = exercises["items"]
    assert item_schema["type"] == "OBJECT"
    assert set(item_schema["properties"].keys()) >= {"name", "sets", "reps", "notes"}


def test_schema_for_optional_field_is_nullable():
    schema = ai_engine._schema_for(WorkoutExercise)

    notes_schema = schema["properties"]["notes"]
    assert notes_schema["nullable"] is True


def test_extract_parses_valid_json_into_model():
    payload = (
        '{"meal_name": "Oatmeal", "calories": 300, "protein": 10, '
        '"carbs": 50, "fat": 5, "identified_items": []}'
    )

    result = ai_engine._extract(MacroBreakdown, payload)

    assert isinstance(result, MacroBreakdown)
    assert result.meal_name == "Oatmeal"
    assert result.calories == 300


def test_extract_raises_ai_engine_error_on_empty_text():
    with pytest.raises(ai_engine.AIEngineError):
        ai_engine._extract(MacroBreakdown, "")


def test_extract_raises_ai_engine_error_on_malformed_json():
    with pytest.raises(ai_engine.AIEngineError):
        ai_engine._extract(MacroBreakdown, "{not valid json")


def test_extract_raises_ai_engine_error_on_schema_mismatch():
    # Valid JSON, but missing required fields -- Pydantic validation should fail.
    with pytest.raises(ai_engine.AIEngineError):
        ai_engine._extract(MacroBreakdown, '{"meal_name": "Oatmeal"}')
