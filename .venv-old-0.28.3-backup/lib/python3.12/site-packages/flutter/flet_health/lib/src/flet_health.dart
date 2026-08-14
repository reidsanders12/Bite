import 'dart:convert';
import 'package:flet/flet.dart';
import 'package:health/health.dart';
import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:flet_health/src/utils/health_data.dart';
import 'package:flet_health/src/utils/health_meal_data.dart';


// Global Health instance
final health = Health();


class FletHealthControl extends StatefulWidget {
  final Control control;
  final Control? parent;
  final FletControlBackend backend;

  const FletHealthControl(
      {super.key,
      required this.parent,
      required this.control,
      required this.backend});

  @override
  _FletHealthControlState createState() => _FletHealthControlState();
}

class _FletHealthControlState extends State<FletHealthControl> {
  @override
  void initState() {
    // configure the health plugin
    health.configure();
    health.getHealthConnectSdkStatus();
    widget.control.onRemove.clear();
    widget.control.onRemove.add(_onRemove);
    super.initState();
  }

  void _onRemove() {
    debugPrint("PermissionHandler.remove($hashCode)");
    widget.backend.unsubscribeMethods(widget.control.id);
  }

  @override
  void deactivate() {
    debugPrint("PermissionHandler.deactivate($hashCode)");
    super.deactivate();
  }

  @override
  Widget build(BuildContext context) {
    debugPrint("Health build: ${widget.control.id} (${widget.control.hashCode})");

    () async {
      try {
        widget.backend.subscribeMethods(widget.control.id,
            (methodName, args) async {
          try {
            return switch (methodName) {
              "request_health_data_history_authorization" => _requestHealthDataHistoryAuthorization(),
              "is_health_data_history_available" => _isHealthDataHistoryAvailable(),
              "is_health_data_history_authorized" => _isHealthDataHistoryAuthorized(),
              "is_health_data_in_background_available" => _isHealthDataInBackgroundAvailable(),
              "request_health_data_in_background_authorization" => _requestHealthDataInBackgroundAuthorization(),
              "request_authorization" => _requestAuthorization(args),
              "has_permissions" => _hasPermissions(args),
              "revoke_permissions" => _revokePermissions(),
              "is_health_connect_available" => _isHealthConnectAvailable(),
              "install_health_connect" => _installHealthConnect(),
              "get_health_connect_sdk_status" => _getHealthConnectSdkStatus(),
              "get_total_steps_in_interval" => _getTotalStepsInInterval(args),
              "get_health_aggregate_data_from_types" => _getHealthAggregateDataFromTypes(args),
              "get_health_data_from_types" => _getHealthDataFromTypes(args),
              "get_health_interval_data_from_types" => _getHealthIntervalDataFromTypes(args),
              "write_health_data" => _writeHealthData(args),
              "write_blood_oxygen" => _writeBloodOxygen(args),
              "write_workout_data" => _writeWorkoutData(args),
              "write_blood_pressure" => _writeBloodPressure(args),
              "write_meal" => _writeMeal(args),
              "write_audiogram" => _writeAudiogram(args),
              "write_menstruation_flow" => _writeMenstruationFlow(args),
              "write_insulin_delivery" => _writeInsulinDelivery(args),
              "remove_duplicates" => _removeDuplicates(args),
              "delete" => _delete(args),
              "delete_by_uuid" => _deleteByUuid(args),
              _ => null,
            };
          } catch (error, stackTrace) {
            debugPrint(
                "Error:\nmethodName: $methodName\nerror: $error\nstackTrace: $stackTrace");
            widget.backend.triggerControlEvent(
              widget.control.id,
              "error",
              "methodName: $methodName\nerror: $error\nstackTrace: $stackTrace",
            );
            return error.toString();
          }
        });
      } catch (error, stackTrace) {
        debugPrint("Error:\nerror: $error\nstackTrace: $stackTrace");
        widget.backend.triggerControlEvent(
          widget.control.id,
          "error",
          "error: $error\nstackTrace: $stackTrace",
        );
      }
    }();

    return const SizedBox.shrink();
  }

  Future<String?> _requestHealthDataHistoryAuthorization() async {
    bool? result = await health.requestHealthDataHistoryAuthorization();
    return result.toString();
  }

  Future<String?> _isHealthDataHistoryAvailable() async {
    bool? result = await health.isHealthDataHistoryAvailable();
    return result.toString();
  }

  Future<String?> _isHealthDataHistoryAuthorized() async {
    bool? result = await health.isHealthConnectAvailable();
    return result.toString();
  }

  Future<String?> _isHealthDataInBackgroundAvailable() async {
    bool? result = await health.isHealthDataInBackgroundAvailable();
    return result.toString();
  }

  Future<String?> _requestHealthDataInBackgroundAuthorization() async {
    bool? result = await health.requestHealthDataInBackgroundAuthorization();
    return result.toString();
  }

  Future<String?> _requestAuthorization(Map<String, dynamic> args) async {
    final parsedData = HealthData.parse(args);
    var types = parsedData["types"];
    var data_access = parsedData["data_access"];
    bool? result =
        await health.requestAuthorization(types, permissions: data_access);
    return result.toString();
  }

  Future<String?> _hasPermissions(Map<String, dynamic> args) async {
    final parsedData = HealthData.parse(args);
    var types = parsedData["types"];
    var data_access = parsedData["data_access"];

    if (defaultTargetPlatform == TargetPlatform.iOS &&
        data_access.contains(HealthDataAccess.READ)) {
      return null;
    }
    bool? result = await health.hasPermissions(types, permissions: data_access);
    return result.toString();
  }

  Future<String?> _revokePermissions() async {
    await health.revokePermissions();
    return null;
  }

  Future<String?> _isHealthConnectAvailable() async {
    await health.isHealthConnectAvailable();
    return null;
  }

  Future<String?> _installHealthConnect() async {
    await health.installHealthConnect();
    return null;
  }

  Future<String?> _getHealthConnectSdkStatus() async {
    var result = await health.getHealthConnectSdkStatus();
    return result.toString();
  }

  Future<String?> _getTotalStepsInInterval(Map<String, dynamic> args) async {
    final parsedData = HealthData.parse(args);
    var startTime = parsedData["start_time"];
    var endTime = parsedData["end_time"];
    var includeManualEntry = parsedData["include_manual_entry"];
    var result = await health.getTotalStepsInInterval(startTime, endTime,
        includeManualEntry: includeManualEntry);
    return result.toString();
  }

  Future<String?> _getHealthAggregateDataFromTypes(
      Map<String, dynamic> args) async {
    final parsedData = HealthData.parse(args);
    var types = parsedData["types"];
    var startTime = parsedData["start_time"];
    var endTime = parsedData["end_time"];
    var activitySegmentDuration = parsedData["activity_segment_duration"];
    var includeManualEntry = parsedData["include_manual_entry"];

    List<HealthDataPoint> healthData =
        await health.getHealthAggregateDataFromTypes(
      types: types,
      startDate: startTime,
      endDate: endTime,
      activitySegmentDuration: activitySegmentDuration,
      includeManualEntry: includeManualEntry,
    );

    return jsonEncode(healthData.map((e) => e.toJson()).toList());
  }

  Future<String?> _getHealthDataFromTypes(Map<String, dynamic> args) async {
    final parsedData = HealthData.parse(args);
    var types = parsedData["types"];
    var startTime = parsedData["start_time"];
    var endTime = parsedData["end_time"];
    var recordingMethodsToFilter = parsedData["recording_method"];

    List<HealthDataPoint> healthData = await health.getHealthDataFromTypes(
      types: types,
      startTime: startTime,
      endTime: endTime,
      recordingMethodsToFilter: recordingMethodsToFilter,
    );

    return jsonEncode(healthData.map((e) => e.toJson()).toList());
  }

  Future<String?> _getHealthIntervalDataFromTypes(
      Map<String, dynamic> args) async {
    final parsedData = HealthData.parse(args);
    var types = parsedData["types"];
    var startTime = parsedData["start_time"];
    var endTime = parsedData["end_time"];
    var interval = parsedData["interval"];
    var recordingMethodsToFilter = parsedData["recording_method"];

    List<HealthDataPoint> healthData =
        await health.getHealthIntervalDataFromTypes(
      startDate: startTime,
      endDate: endTime,
      types: types,
      interval: interval,
      recordingMethodsToFilter: recordingMethodsToFilter,
    );

    return jsonEncode(healthData.map((e) => e.toJson()).toList());
  }

  Future<String?> _writeHealthData(Map<String, dynamic> args) async {
    final parsedData = HealthData.parse(args);
    var type = parsedData["types"];
    var value = parsedData["value"];
    var startTime = parsedData["start_time"];
    var endTime = parsedData["end_time"];
    var unit = parsedData["unit"];
    var recordingMethod = parsedData["recording_method"];

    var result = await health.writeHealthData(
      type: type,
      value: value,
      startTime: startTime,
      endTime: endTime,
      unit: unit,
      recordingMethod: recordingMethod,
    );

    return result.toString();
  }

  Future<String?> _writeBloodOxygen(Map<String, dynamic> args) async {
    final parsedData = HealthData.parse(args);
    var saturation = parsedData["saturation"];
    var startTime = parsedData["start_time"];
    var endTime = parsedData["end_time"];
    var recordingMethod = parsedData["recording_method"];

    var result = await health.writeBloodOxygen(
      saturation: saturation,
      startTime: startTime,
      endTime: endTime,
      recordingMethod: recordingMethod,
    );

    return result.toString();
  }

  Future<String?> _writeWorkoutData(Map<String, dynamic> args) async {
    final parsedData = HealthData.parse(args);
    var activityType = parsedData["activity_type"];
    var startTime = parsedData["start_time"];
    var endTime = parsedData["end_time"];
    var totalEnergyBurned = parsedData["total_energy_burned"];
    var totalEnergyBurnedUnit = parsedData["total_energy_burned_unit"];
    var totalDistance = parsedData["total_distance"];
    var totalDistanceUnit = parsedData["total_distance_unit"];
    var title = parsedData["title"];
    var recordingMethod = parsedData["recording_method"];

    var result = await health.writeWorkoutData(
      activityType: activityType,
      start: startTime,
      end: endTime,
      totalEnergyBurned: totalEnergyBurned,
      totalEnergyBurnedUnit: totalEnergyBurnedUnit,
      totalDistance: totalDistance,
      totalDistanceUnit: totalDistanceUnit,
      title: title,
      recordingMethod: recordingMethod,
    );

    return result.toString();
  }

  Future<String?> _writeBloodPressure(Map<String, dynamic> args) async {
    final parsedData = HealthData.parse(args);
    var systolic = parsedData["systolic"];
    var diastolic = parsedData["diastolic"];
    var startTime = parsedData["start_time"];
    var endTime = parsedData["end_time"];
    var recordingMethod = parsedData["recording_method"];

    var result = await health.writeBloodPressure(
      systolic: systolic,
      diastolic: diastolic,
      startTime: startTime,
      endTime: endTime,
      recordingMethod: recordingMethod,
    );

    return result.toString();
  }

  Future<String?> _writeMeal(Map<String, dynamic> args) async {
    final parsedData = MealData.parse(args);
    var mealType = parsedData["meal_type"];
    var startTime = parsedData["start_time"];
    var endTime = parsedData["end_time"];
    var caloriesConsumed = parsedData["calories_consumed"];
    var carbohydrates = parsedData["carbohydrates"];
    var protein = parsedData["protein"];
    var fatTotal = parsedData["fat_total"];
    var name = parsedData["name"];
    var caffeine = parsedData["caffeine"];
    var vitaminA = parsedData["vitamin_a"];
    var b1Thiamin = parsedData["b1_thiamin"];
    var b2Riboflavin = parsedData["b2_riboflavin"];
    var b3Niacin = parsedData["b3_niacin"];
    var b5PantothenicAcid = parsedData["b5_pantothenic_acid"];
    var b6Pyridoxine = parsedData["b6_pyridoxine"];
    var b7Biotin = parsedData["b7_biotin"];
    var b9Folate = parsedData["b9_folate"];
    var b12Cobalamin = parsedData["b12_cobalamin"];
    var vitaminC = parsedData["vitamin_c"];
    var vitaminD = parsedData["vitamin_d"];
    var vitaminE = parsedData["vitamin_e"];
    var vitaminK = parsedData["vitamin_k"];
    var calcium = parsedData["calcium"];
    var cholesterol = parsedData["cholesterol"];
    var chloride = parsedData["chloride"];
    var chromium = parsedData["chromium"];
    var copper = parsedData["copper"];
    var fatUnsaturated = parsedData["fat_unsaturated"];
    var fatMonounsaturated = parsedData["fat_monounsaturated"];
    var fatPolyunsaturated = parsedData["fat_polyunsaturated"];
    var fatSaturated = parsedData["fat_saturated"];
    var fatTransMonoenoic = parsedData["fat_trans_monoenoic"];
    var fiber = parsedData["fiber"];
    var iodine = parsedData["iodine"];
    var iron = parsedData["iron"];
    var magnesium = parsedData["magnesium"];
    var manganese = parsedData["manganese"];
    var molybdenum = parsedData["molybdenum"];
    var phosphorus = parsedData["phosphorus"];
    var potassium = parsedData["potassium"];
    var selenium = parsedData["selenium"];
    var sodium = parsedData["sodium"];
    var sugar = parsedData["sugar"];
    var water = parsedData["water"];
    var zinc = parsedData["zinc"];
    var recordingMethod = parsedData["recording_method"];

    var result = await health.writeMeal(
      mealType: mealType,
      startTime: startTime,
      endTime: endTime,
      caloriesConsumed: caloriesConsumed,
      carbohydrates: carbohydrates,
      protein: protein,
      fatTotal: fatTotal,
      name: name,
      caffeine: caffeine,
      vitaminA: vitaminA,
      b1Thiamin: b1Thiamin,
      b2Riboflavin: b2Riboflavin,
      b3Niacin: b3Niacin,
      b5PantothenicAcid: b5PantothenicAcid,
      b6Pyridoxine: b6Pyridoxine,
      b7Biotin: b7Biotin,
      b9Folate: b9Folate,
      b12Cobalamin: b12Cobalamin,
      vitaminC: vitaminC,
      vitaminD: vitaminD,
      vitaminE: vitaminE,
      vitaminK: vitaminK,
      calcium: calcium,
      cholesterol: cholesterol,
      chloride: chloride,
      chromium: chromium,
      copper: copper,
      fatUnsaturated: fatUnsaturated,
      fatMonounsaturated: fatMonounsaturated,
      fatPolyunsaturated: fatPolyunsaturated,
      fatSaturated: fatSaturated,
      fatTransMonoenoic: fatTransMonoenoic,
      fiber: fiber,
      iodine: iodine,
      iron: iron,
      magnesium: magnesium,
      manganese: manganese,
      molybdenum: molybdenum,
      phosphorus: phosphorus,
      potassium: potassium,
      selenium: selenium,
      sodium: sodium,
      sugar: sugar,
      water: water,
      zinc: zinc,
      recordingMethod: recordingMethod,
    );

    return result.toString();
  }

  Future<String?> _writeAudiogram(Map<String, dynamic> args) async {
    final parsedData = HealthData.parse(args);
    var frequencies = parsedData["frequencies"];
    var leftEarSensitivities = parsedData["leftEarSensitivities"];
    var rightEarSensitivities = parsedData["rightEarSensitivities"];
    var startTime = parsedData["start_time"];
    var endTime = parsedData["end_time"];
    var metadata = parsedData["metadata"];

    var result = await health.writeAudiogram(
      frequencies: frequencies,
      leftEarSensitivities: leftEarSensitivities,
      rightEarSensitivities: rightEarSensitivities,
      startTime: startTime,
      endTime: endTime,
      metadata: metadata,
    );

    return result.toString();
  }

  Future<String?> _writeMenstruationFlow(Map<String, dynamic> args) async {
    final parsedData = HealthData.parse(args);
    var flow = parsedData["flow"];
    var startTime = parsedData["start_time"];
    var endTime = parsedData["end_time"];
    var isStartOfCycle = parsedData["is_start_of_cycle"];
    var recordingMethod = parsedData["recording_method"];

    var result = await health.writeMenstruationFlow(
      flow: flow,
      startTime: startTime,
      endTime: endTime,
      isStartOfCycle: isStartOfCycle,
      recordingMethod: recordingMethod,
    );

    return result.toString();
  }

  Future<String?> _writeInsulinDelivery(Map<String, dynamic> args) async {
    final parsedData = HealthData.parse(args);
    var units = parsedData["units"];
    var reason = parsedData["reason"];
    var startTime = parsedData["start_time"];
    var endTime = parsedData["end_time"];

    var result = await health.writeInsulinDelivery(
      units,
      reason,
      startTime,
      endTime,
    );

    return result.toString();
  }

  Future<String?> _removeDuplicates(Map<String, dynamic> args) async {
    String dataStr = args["data"]!;
    List<dynamic> rawPoints = json.decode(dataStr);
    List<HealthDataPoint> points = rawPoints
        .map((e) => HealthDataPoint.fromJson(Map<String, dynamic>.from(e)))
        .toList();

    List<HealthDataPoint> deduped = health.removeDuplicates(points);
    return jsonEncode(deduped.map((e) => e.toJson()).toList());
  }

  Future<String?> _delete(Map<String, dynamic> args) async {
    final parsedData = HealthData.parse(args);
    var types = parsedData["types"];
    var startTime = parsedData["start_time"];
    var endTime = parsedData["end_time"];

    var result = await health.delete(
      type: types,
      startTime: startTime,
      endTime: endTime,
    );

    return result.toString();
  }

  Future<String?> _deleteByUuid(Map<String, dynamic> args) async {
    final parsedData = HealthData.parse(args);
    var uuid = parsedData["uuid"];
    var types = parsedData["types"];

    var result = await health.deleteByUUID(uuid: uuid, type: types);
    return result.toString();
  }
}
