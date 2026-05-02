/// Response DTO для `POST /api/v1/fingerprints/batch`.
///
/// Backend гарантирует `accepted_count + rejected_count == len(items)`.
/// `accepted[].index` и `rejected[].index` — индекс item'а в исходном
/// списке, на этом строится позиционное соответствие с локальными id.
library;

import 'package:json_annotation/json_annotation.dart';

part 'batch_response_dto.g.dart';

@JsonSerializable()
class FingerprintResponseDto {
  const FingerprintResponseDto({
    required this.id,
    required this.capturedAt,
    required this.rssiVector,
    required this.sampleCount,
    required this.isCalibration,
    this.employeeId,
    this.zoneId,
    this.deviceId,
  });

  final int id;

  @JsonKey(name: 'employee_id')
  final int? employeeId;

  @JsonKey(name: 'zone_id')
  final int? zoneId;

  @JsonKey(name: 'is_calibration')
  final bool isCalibration;

  @JsonKey(name: 'captured_at')
  final String capturedAt;

  @JsonKey(name: 'device_id')
  final String? deviceId;

  @JsonKey(name: 'rssi_vector')
  final Map<String, int> rssiVector;

  @JsonKey(name: 'sample_count')
  final int sampleCount;

  factory FingerprintResponseDto.fromJson(Map<String, dynamic> json) =>
      _$FingerprintResponseDtoFromJson(json);

  Map<String, dynamic> toJson() => _$FingerprintResponseDtoToJson(this);
}

@JsonSerializable(explicitToJson: true)
class BatchAcceptedDto {
  const BatchAcceptedDto({required this.index, required this.fingerprint});

  final int index;
  final FingerprintResponseDto fingerprint;

  factory BatchAcceptedDto.fromJson(Map<String, dynamic> json) =>
      _$BatchAcceptedDtoFromJson(json);

  Map<String, dynamic> toJson() => _$BatchAcceptedDtoToJson(this);
}

@JsonSerializable()
class BatchRejectedDto {
  const BatchRejectedDto({
    required this.index,
    required this.code,
    required this.message,
  });

  final int index;
  final String code;
  final String message;

  factory BatchRejectedDto.fromJson(Map<String, dynamic> json) =>
      _$BatchRejectedDtoFromJson(json);

  Map<String, dynamic> toJson() => _$BatchRejectedDtoToJson(this);
}

@JsonSerializable(explicitToJson: true)
class BatchResponseDto {
  const BatchResponseDto({
    required this.accepted,
    required this.rejected,
    required this.acceptedCount,
    required this.rejectedCount,
  });

  final List<BatchAcceptedDto> accepted;
  final List<BatchRejectedDto> rejected;

  @JsonKey(name: 'accepted_count')
  final int acceptedCount;

  @JsonKey(name: 'rejected_count')
  final int rejectedCount;

  factory BatchResponseDto.fromJson(Map<String, dynamic> json) =>
      _$BatchResponseDtoFromJson(json);

  Map<String, dynamic> toJson() => _$BatchResponseDtoToJson(this);
}
