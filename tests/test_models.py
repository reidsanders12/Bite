from app.models import FoodItem, MacroBreakdown, UserGoals


def _breakdown(**overrides):
    defaults = dict(meal_name="Oats", calories=400, protein=20, carbs=60, fat=10, identified_items=[])
    defaults.update(overrides)
    return MacroBreakdown(**defaults)


def test_scaled_halves_every_macro():
    original = _breakdown(calories=400, protein=20, carbs=60, fat=10)
    scaled = original.scaled(0.5)
    assert (scaled.calories, scaled.protein, scaled.carbs, scaled.fat) == (200, 10, 30, 5)


def test_scaled_doubles_every_macro():
    original = _breakdown(calories=400, protein=20, carbs=60, fat=10)
    scaled = original.scaled(2.0)
    assert (scaled.calories, scaled.protein, scaled.carbs, scaled.fat) == (800, 40, 120, 20)


def test_scaled_by_one_is_a_no_op():
    original = _breakdown(calories=401, protein=21, carbs=61, fat=11)
    scaled = original.scaled(1.0)
    assert (scaled.calories, scaled.protein, scaled.carbs, scaled.fat) == (401, 21, 61, 11)


def test_scaled_rounds_to_nearest_whole_gram():
    # 21 * 1.5 = 31.5 -> banker's-adjacent round() rounds to even (32), not truncation (31)
    original = _breakdown(calories=401, protein=21, carbs=61, fat=11)
    scaled = original.scaled(1.5)
    assert scaled.protein == round(21 * 1.5)


def test_scaled_preserves_meal_name_and_identified_items():
    item = FoodItem(name="Oats", portion_size="150g")
    original = _breakdown(identified_items=[item])
    scaled = original.scaled(0.5)
    assert scaled.meal_name == original.meal_name
    assert scaled.identified_items == [item]


def test_user_goals_defaults():
    goals = UserGoals()
    assert goals.daily_calories == 2200
    assert goals.daily_protein == 150
    assert goals.daily_carbs == 220
    assert goals.daily_fat == 70
