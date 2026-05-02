// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'fingerprint_dto.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

FingerprintItemDto _$FingerprintItemDtoFromJson(Map<String, dynamic> json) =>
    FingerprintItemDto(
      capturedAt: json['captured_at'] as String,
      rssiVector: Map<String, int>.from(json['rssi_vector'] as Map),
      sampleCount: (json['sample_count'] as num?)?.toInt() ?? 1,
      deviceId: json['device_id'] as String?,
    );

Map<String, dynamic> _$FingerprintItemDtoToJson(FingerprintItemDto instance) =>
    <String, dynamic>{
      'captured_at': instance.capturedAt,
      'rssi_vector': instance.rssiVector,
      'sample_count': instance.sampleCount,
      'device_id': instance.deviceId,
    };
