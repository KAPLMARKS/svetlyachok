// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'batch_response_dto.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

FingerprintResponseDto _$FingerprintResponseDtoFromJson(
        Map<String, dynamic> json) =>
    FingerprintResponseDto(
      id: (json['id'] as num).toInt(),
      capturedAt: json['captured_at'] as String,
      rssiVector: Map<String, int>.from(json['rssi_vector'] as Map),
      sampleCount: (json['sample_count'] as num).toInt(),
      isCalibration: json['is_calibration'] as bool,
      employeeId: (json['employee_id'] as num?)?.toInt(),
      zoneId: (json['zone_id'] as num?)?.toInt(),
      deviceId: json['device_id'] as String?,
    );

Map<String, dynamic> _$FingerprintResponseDtoToJson(
        FingerprintResponseDto instance) =>
    <String, dynamic>{
      'id': instance.id,
      'employee_id': instance.employeeId,
      'zone_id': instance.zoneId,
      'is_calibration': instance.isCalibration,
      'captured_at': instance.capturedAt,
      'device_id': instance.deviceId,
      'rssi_vector': instance.rssiVector,
      'sample_count': instance.sampleCount,
    };

BatchAcceptedDto _$BatchAcceptedDtoFromJson(Map<String, dynamic> json) =>
    BatchAcceptedDto(
      index: (json['index'] as num).toInt(),
      fingerprint: FingerprintResponseDto.fromJson(
          json['fingerprint'] as Map<String, dynamic>),
    );

Map<String, dynamic> _$BatchAcceptedDtoToJson(BatchAcceptedDto instance) =>
    <String, dynamic>{
      'index': instance.index,
      'fingerprint': instance.fingerprint.toJson(),
    };

BatchRejectedDto _$BatchRejectedDtoFromJson(Map<String, dynamic> json) =>
    BatchRejectedDto(
      index: (json['index'] as num).toInt(),
      code: json['code'] as String,
      message: json['message'] as String,
    );

Map<String, dynamic> _$BatchRejectedDtoToJson(BatchRejectedDto instance) =>
    <String, dynamic>{
      'index': instance.index,
      'code': instance.code,
      'message': instance.message,
    };

BatchResponseDto _$BatchResponseDtoFromJson(Map<String, dynamic> json) =>
    BatchResponseDto(
      accepted: (json['accepted'] as List<dynamic>)
          .map((e) => BatchAcceptedDto.fromJson(e as Map<String, dynamic>))
          .toList(),
      rejected: (json['rejected'] as List<dynamic>)
          .map((e) => BatchRejectedDto.fromJson(e as Map<String, dynamic>))
          .toList(),
      acceptedCount: (json['accepted_count'] as num).toInt(),
      rejectedCount: (json['rejected_count'] as num).toInt(),
    );

Map<String, dynamic> _$BatchResponseDtoToJson(BatchResponseDto instance) =>
    <String, dynamic>{
      'accepted': instance.accepted.map((e) => e.toJson()).toList(),
      'rejected': instance.rejected.map((e) => e.toJson()).toList(),
      'accepted_count': instance.acceptedCount,
      'rejected_count': instance.rejectedCount,
    };
