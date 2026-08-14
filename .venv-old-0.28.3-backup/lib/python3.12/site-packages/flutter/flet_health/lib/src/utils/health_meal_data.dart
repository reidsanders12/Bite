import 'package:health/health.dart';
import 'package:flutter/material.dart';
import 'package:flet_health/src/utils/parsers.dart';


class MealData {
  static Map<String, dynamic> parse(Map<String, dynamic> args) {
    final dataMap = Parsers.parseInput(args);
    final result = <String, dynamic>{};

    void tryAdd(String key, dynamic Function() parser) {
      try {
        final value = parser();
        if (value != null) {
          result[key] = value;
        }
      } catch (error) {
        debugPrint("Error in MealParser - tryAdd - error in '$key': $error");
        rethrow;
      }
    }

    // Dates
    tryAdd("start_time", () => Parsers.dateTime(dataMap["start_time"]));
    tryAdd("end_time", () => Parsers.dateTime(dataMap["end_time"]));

    // Basic information
    tryAdd("name", () => dataMap["name"]?.toString());

    // Macronutrients
    tryAdd("calories_consumed", () => Parsers.doubleValue(dataMap["calories_consumed"]));
    tryAdd("carbohydrates", () => Parsers.doubleValue(dataMap["carbohydrates"]));
    tryAdd("protein", () => Parsers.doubleValue(dataMap["protein"]));
    tryAdd("fat_total", () => Parsers.doubleValue(dataMap["fat_total"]));

    // Vitamins
    tryAdd("caffeine", () => Parsers.doubleValue(dataMap["caffeine"]));
    tryAdd("vitamin_a", () => Parsers.doubleValue(dataMap["vitamin_a"]));
    tryAdd("b1_thiamin", () => Parsers.doubleValue(dataMap["b1_thiamin"]));
    tryAdd("b2_riboflavin", () => Parsers.doubleValue(dataMap["b2_riboflavin"]));
    tryAdd("b3_niacin", () => Parsers.doubleValue(dataMap["b3_niacin"]));
    tryAdd("b5_pantothenic_acid", () => Parsers.doubleValue(dataMap["b5_pantothenic_acid"]));
    tryAdd("b6_pyridoxine", () => Parsers.doubleValue(dataMap["b6_pyridoxine"]));
    tryAdd("b7_biotin", () => Parsers.doubleValue(dataMap["b7_biotin"]));
    tryAdd("b9_folate", () => Parsers.doubleValue(dataMap["b9_folate"]));
    tryAdd("b12_cobalamin", () => Parsers.doubleValue(dataMap["b12_cobalamin"]));
    tryAdd("vitamin_c", () => Parsers.doubleValue(dataMap["vitamin_c"]));
    tryAdd("vitamin_d", () => Parsers.doubleValue(dataMap["vitamin_d"]));
    tryAdd("vitamin_e", () => Parsers.doubleValue(dataMap["vitamin_e"]));
    tryAdd("vitamin_k", () => Parsers.doubleValue(dataMap["vitamin_k"]));

    // Minerals
    tryAdd("calcium", () => Parsers.doubleValue(dataMap["calcium"]));
    tryAdd("cholesterol", () => Parsers.doubleValue(dataMap["cholesterol"]));
    tryAdd("chloride", () => Parsers.doubleValue(dataMap["chloride"]));
    tryAdd("chromium", () => Parsers.doubleValue(dataMap["chromium"]));
    tryAdd("copper", () => Parsers.doubleValue(dataMap["copper"]));
    tryAdd("iron", () => Parsers.doubleValue(dataMap["iron"]));
    tryAdd("magnesium", () => Parsers.doubleValue(dataMap["magnesium"]));
    tryAdd("manganese", () => Parsers.doubleValue(dataMap["manganese"]));
    tryAdd("molybdenum", () => Parsers.doubleValue(dataMap["molybdenum"]));
    tryAdd("phosphorus", () => Parsers.doubleValue(dataMap["phosphorus"]));
    tryAdd("potassium", () => Parsers.doubleValue(dataMap["potassium"]));
    tryAdd("selenium", () => Parsers.doubleValue(dataMap["selenium"]));
    tryAdd("sodium", () => Parsers.doubleValue(dataMap["sodium"]));
    tryAdd("zinc", () => Parsers.doubleValue(dataMap["zinc"]));

    // Fats
    tryAdd("fat_unsaturated", () => Parsers.doubleValue(dataMap["fat_unsaturated"]));
    tryAdd("fat_monounsaturated", () => Parsers.doubleValue(dataMap["fat_monounsaturated"]));
    tryAdd("fat_polyunsaturated", () => Parsers.doubleValue(dataMap["fat_polyunsaturated"]));
    tryAdd("fat_saturated", () => Parsers.doubleValue(dataMap["fat_saturated"]));
    tryAdd("fat_trans_monoenoic", () => Parsers.doubleValue(dataMap["fat_trans_monoenoic"]));

    // Others
    tryAdd("fiber", () => Parsers.doubleValue(dataMap["fiber"]));
    tryAdd("sugar", () => Parsers.doubleValue(dataMap["sugar"]));
    tryAdd("water", () => Parsers.doubleValue(dataMap["water"]));

    // Enums
    tryAdd("meal_type", () => Parsers.enumValues(dataMap["meal_type"], MealType.values));
    tryAdd("recording_method", () => Parsers.enumValues(dataMap["recording_method"], RecordingMethod.values));

    return result;
  }
}