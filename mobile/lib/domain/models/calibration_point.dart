/// Доменная модель эталонной калибровочной точки.
library;

import 'package:freezed_annotation/freezed_annotation.dart';

part 'calibration_point.freezed.dart';

@freezed
class CalibrationPoint with _$CalibrationPoint {
  const factory CalibrationPoint({
    required int id,
    required int zoneId,
    required DateTime capturedAt,
    required Map<String, int> rssiVector,
    @Default(1) int sampleCount,
  }) = _CalibrationPoint;
}
