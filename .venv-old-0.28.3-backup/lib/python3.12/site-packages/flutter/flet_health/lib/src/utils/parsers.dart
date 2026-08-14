import 'dart:convert';

import 'package:flutter/material.dart';


class Parsers {
  static DateTime? dateTime(dynamic v) =>
      v is int ? DateTime.fromMillisecondsSinceEpoch(v) : null;

  static double? doubleValue(dynamic value) {
    if (value == null) return null;
    if (value is num) return value.toDouble();
    if (value is String) {
      final cleaned = value.replaceAll(',', '.').replaceAll(RegExp(r'[^0-9.-]'), '');
      return double.tryParse(cleaned);
    }
    return null;
  }

  static int? intValue(dynamic value) {
    if (value == null) return null;
    if (value is num) return value.toInt();
    if (value is String) {
      final cleaned = value.replaceAll(RegExp(r'[^0-9-]'), '');
      return int.tryParse(cleaned);
    }
    return null;
  }

  static bool? boolValue(dynamic v) {
    if (v is bool) return v;
    if (v is String) return v.toLowerCase() == "true";
    if (v is num) return v != 0;
    return null;
  }

  static List<double>? doubleList(dynamic v) =>
      v is List ? v.map((e) => doubleValue(e)).whereType<double>().toList() : null;

  static Map<String, dynamic>? stringMap(dynamic v) {
    if (v == null) return null;
    if (v is Map<String, dynamic>) return v;
    if (v is Map) return Map<String, dynamic>.from(v);
    return null;
  }

  static Map<String, dynamic> parseInput(Map<String, dynamic> args) {
    try {
      final dataStr = args["data"] ?? '{}';
      return json.decode(dataStr) as Map<String, dynamic>;
    } catch (error) {
      debugPrint("HealthDataParser - Error decoding JSON: $error");
      return {};
    }
  }

  static dynamic enumValues<T extends Enum>(dynamic value, List<T> enumValues) {
    try {
      if (value == null) return null;

      // 1. Case String
      if (value is String) {
        try {
          return enumValues.byName(value);
        } catch (error) {
          debugPrint('enumValues: Value "$value" is not a valid enum value. Error: $error');
          return null;
        }
      }

      // 2. Case List
      if (value is List) {
        return value.whereType<String>().map((e) {
          try {
            return enumValues.byName(e);
          } catch (_) {
            return null;
          }
        }).whereType<T>().toList();
      }

      return null;
    } catch (error) {
      debugPrint('enumValues - Error: $error');
      return null;
    }
  }
}
