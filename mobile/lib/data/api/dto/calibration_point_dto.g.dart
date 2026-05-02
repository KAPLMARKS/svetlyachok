// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'calibration_point_dto.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

CalibrationPointRequestDto _$CalibrationPointRequestDtoFromJson(
        Map<String, dynamic> json) =>
    CalibrationPointRequestDto(
      zoneId: (json['zone_id'] as num).toInt(),
      capturedAt: json['captured_at'] as String,
      rssiVector: Map<String, int>.from(json['rssi_vector'] as Map),
      sampleCount: (json['sample_count'] as num?)?.toInt() ?? 1,
      deviceId: json['device_id'] as String?,
    );

Map<String, dynamic> _$CalibrationPointRequestDtoToJson(
        CalibrationPointRequestDto instance) =>
    <String, dynamic>{
      'zone_id': instance.zoneId,
      'captured_at': instance.capturedAt,
      'rssi_vector': instance.rssiVector,
      'sample_count': instance.sampleCount,
      'device_id': instance.deviceId,
    };

CalibrationPointResponseDto _$CalibrationPointResponseDtoFromJson(
        Map<String, dynamic> json) =>
    CalibrationPointResponseDto(
      id: (json['id'] as num).toInt(),
      zoneId: (json['zone_id'] as num).toInt(),
      capturedAt: json['captured_at'] as String,
      rssiVector: Map<String, int>.from(json['rssi_vector'] as Map),
      sampleCount: (json['sample_count'] as num).toInt(),
    );

Map<String, dynamic> _$CalibrationPointResponseDtoToJson(
        CalibrationPointResponseDto instance) =>
    <String, dynamic>{
      'id': instance.id,
      'zone_id': instance.zoneId,
      'captured_at': instance.capturedAt,
      'rssi_vector': instance.rssiVector,
      'sample_count': instance.sampleCount,
    };
