import 'package:flet_health/src/utils/parsers.dart';
import 'package:flutter/material.dart';
import 'package:health/health.dart';


class HealthData {
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
        debugPrint("Error in HealthData - tryAdd - error in '$key': $error");
        rethrow;
      }
    }

    // 1. Dates and times
    tryAdd("start_time", () => Parsers.dateTime(dataMap["start_time"]));
    tryAdd("end_time", () => Parsers.dateTime(dataMap["end_time"]));

    // 2. Numerical values
    tryAdd("value", () => Parsers.doubleValue(dataMap["value"]));
    tryAdd("saturation", () => Parsers.doubleValue(dataMap["saturation"]));
    tryAdd("units", () => Parsers.doubleValue(dataMap["units"]));
    tryAdd("total_distance", () => Parsers.intValue(dataMap["total_distance"]));
    tryAdd("total_energy_burned", () => Parsers.intValue(dataMap["total_energy_burned"]));
    tryAdd("systolic", () => Parsers.intValue(dataMap["systolic"]));
    tryAdd("diastolic", () => Parsers.intValue(dataMap["diastolic"]));

    // 3. Strings and booleans
    tryAdd("uuid", () => dataMap["uuid"]?.toString());
    tryAdd("title", () => dataMap["title"]?.toString());
    tryAdd("include_manual_entry", () => Parsers.boolValue(dataMap["include_manual_entry"]));
    tryAdd("is_start_of_cycle", () => Parsers.boolValue(dataMap["is_start_of_cycle"]));

    // 4. Lists
    tryAdd("frequencies", () => Parsers.doubleList(dataMap["frequencies"]));
    tryAdd("leftEarSensitivities", () => Parsers.doubleList(dataMap["leftEarSensitivities"]));
    tryAdd("rightEarSensitivities", () => Parsers.doubleList(dataMap["rightEarSensitivities"]));
    tryAdd("metadata", () => Parsers.stringMap(dataMap["metadata"]));

    // 5. Enums and complex types
    tryAdd("types", () => Parsers.enumValues<HealthDataType>(
        dataMap["types"],
        HealthDataType.values
    ));

    tryAdd("recording_method", () => Parsers.enumValues<RecordingMethod>(
        dataMap["recording_method"],
        RecordingMethod.values
    ));

    tryAdd("data_access", () => Parsers.enumValues<HealthDataAccess>(
        dataMap["data_access"],
        HealthDataAccess.values
    ));

    // 6. Specific Enums
    tryAdd("unit", () => Parsers.enumValues(dataMap["unit"], HealthDataUnit.values));
    tryAdd("total_energy_burned_unit", () => Parsers.enumValues(dataMap["total_energy_burned_unit"], HealthDataUnit.values));
    tryAdd("activity_type", () => Parsers.enumValues(dataMap["activity_type"], HealthWorkoutActivityType.values));
    tryAdd("total_distance_unit", () => Parsers.enumValues(dataMap["total_distance_unit"], HealthDataUnit.values));
    tryAdd("flow", () => Parsers.enumValues(dataMap["flow"], MenstrualFlow.values));
    tryAdd("reason", () => Parsers.enumValues(dataMap["reason"], InsulinDeliveryReason.values));

    return result;
  }

}