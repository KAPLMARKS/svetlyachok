/// DTO для калибровочной точки (request + response).
///
/// Backend требует `zone_id`, `captured_at` (ISO-8601 timezone-aware),
/// `rssi_vector` (BSSID → dBm), `sample_count`.
library;

import 'package:json_annotation/json_annotation.dart';

part 'calibration_point_dto.g.dart';

@JsonSerializable()
class CalibrationPointRequestDto {
  const CalibrationPointRequestDto({
    required this.zoneId,
    required this.capturedAt,
    required this.rssiVector,
    this.sampleCount = 1,
    this.deviceId,
  });

  @JsonKey(name: 'zone_id')
  final int zoneId;

  @JsonKey(name: 'captured_at')
  final String capturedAt;

  @JsonKey(name: 'rssi_vector')
  final Map<String, int> rssiVector;

  @JsonKey(name: 'sample_count')
  final int sampleCount;

  @JsonKey(name: 'device_id')
  final String? deviceId;

  factory CalibrationPointRequestDto.fromJson(Map<String, dynamic> json) =>
      _$CalibrationPointRequestDtoFromJson(json);

  Map<String, dynamic> toJson() => _$CalibrationPointRequestDtoToJson(this);
}

@JsonSerializable()
class CalibrationPointResponseDto {
  const CalibrationPointResponseDto({
    required this.id,
    required this.zoneId,
    required this.capturedAt,
    required this.rssiVector,
    required this.sampleCount,
  });

  final int id;

  @JsonKey(name: 'zone_id')
  final int zoneId;

  @JsonKey(name: 'captured_at')
  final String capturedAt;

  @JsonKey(name: 'rssi_vector')
  final Map<String, int> rssiVector;

  @JsonKey(name: 'sample_count')
  final int sampleCount;

  factory CalibrationPointResponseDto.fromJson(Map<String, dynamic> json) =>
      _$CalibrationPointResponseDtoFromJson(json);

  Map<String, dynamic> toJson() => _$CalibrationPointResponseDtoToJson(this);
}
