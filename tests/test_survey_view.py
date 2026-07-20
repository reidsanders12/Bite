from app.views.survey_view import calculate_macro_targets


def _goals(**overrides):
    defaults = dict(age=28, gender="male", activity=1.375, weight_kg=80.0, height_cm=178.0, goal="maintain")
    defaults.update(overrides)
    return calculate_macro_targets(**defaults)


def test_male_bmr_matches_mifflin_st_jeor_plus_five():
    # BMR = 10*80 + 6.25*178 - 5*28 + 5 = 800 + 1112.5 - 140 + 5 = 1777.5
    # TDEE = 1777.5 * 1.375 = 2444.0625 -> maintain -> int() truncates to 2444
    goals = _goals(gender="male", activity=1.375, weight_kg=80.0, height_cm=178.0, age=28, goal="maintain")
    assert goals.daily_calories == 2444


def test_female_bmr_matches_mifflin_st_jeor_minus_161():
    # BMR = 10*60 + 6.25*165 - 5*30 - 161 = 600 + 1031.25 - 150 - 161 = 1320.25
    # TDEE = 1320.25 * 1.2 = 1584.3 -> maintain -> 1584
    goals = _goals(gender="female", activity=1.2, weight_kg=60.0, height_cm=165.0, age=30, goal="maintain")
    assert goals.daily_calories == 1584


def test_cut_goal_subtracts_400_from_tdee():
    maintain = _goals(goal="maintain")
    cut = _goals(goal="cut")
    assert maintain.daily_calories - cut.daily_calories == 400


def test_bulk_goal_adds_250_to_tdee():
    maintain = _goals(goal="maintain")
    bulk = _goals(goal="bulk")
    assert bulk.daily_calories - maintain.daily_calories == 250


def test_calorie_floor_never_drops_below_1200():
    # A tiny, low-activity, cutting profile would otherwise compute well under 1200.
    goals = _goals(age=70, gender="female", activity=1.2, weight_kg=40.0, height_cm=140.0, goal="cut")
    assert goals.daily_calories == 1200


def test_protein_is_one_gram_per_pound_of_bodyweight():
    goals = _goals(weight_kg=80.0)
    assert goals.daily_protein == round(80.0 * 2.20462)


def test_fat_is_25_percent_of_calories_at_9_kcal_per_gram():
    goals = _goals()
    assert goals.daily_fat == round(goals.daily_calories * 0.25 / 9)


def test_carbs_fill_remaining_calorie_budget():
    goals = _goals()
    # Carbs are derived from the *raw* fat-calorie share (calories * 0.25),
    # not from daily_fat*9 -- fat_g is independently rounded from the same
    # raw share, so reconstructing from the rounded gram value would drift.
    protein_cal = goals.daily_protein * 4
    fat_cal = goals.daily_calories * 0.25
    carb_cal = max(0, goals.daily_calories - protein_cal - fat_cal)
    assert goals.daily_carbs == round(carb_cal / 4)


def test_protein_floor_applies_to_a_very_light_bodyweight():
    # 20kg * 2.20462 lb/kg = ~44g of protein, below the 50g floor.
    goals = _goals(age=10, gender="male", activity=1.2, weight_kg=20.0, height_cm=110.0, goal="cut")
    assert goals.daily_protein == 50


def test_carbs_floor_applies_when_protein_demand_consumes_most_of_the_budget():
    # High bodyweight (high protein demand) on a small frame at the calorie
    # floor leaves less than 50g worth of carb calories once protein+fat
    # are subtracted, so this hits the carbs floor rather than the
    # remaining-budget formula.
    goals = _goals(age=60, gender="female", activity=1.2, weight_kg=100.0, height_cm=150.0, goal="cut")
    assert goals.daily_carbs == 50


def test_fat_floor_of_30_is_unreachable_given_the_1200_calorie_floor():
    # 1200 (the lowest daily_calories can ever be) * 0.25 / 9 = ~33g, which
    # is already above the 30g floor -- so max(30, fat_g) never actually
    # binds for any input. Documented here so a future change to either
    # constant doesn't silently make this dead code do something new.
    goals = _goals(age=90, gender="female", activity=1.2, weight_kg=35.0, height_cm=140.0, goal="cut")
    assert goals.daily_calories == 1200
    assert goals.daily_fat > 30
