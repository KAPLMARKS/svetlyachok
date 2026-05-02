/// DTO для item'а fingerprint в `/fingerprints/batch` request'е.
library;

import 'package:json_annotation/json_annotation.dart';

part 'fingerprint_dto.g.dart';

@JsonSerializable()
class FingerprintItemDto {
  const FingerprintItemDto({
    required this.capturedAt,
    required this.rssiVector,
    this.sampleCount = 1,
    this.deviceId,
  });

  @JsonKey(name: 'captured_at')
  final String capturedAt;

  @JsonKey(name: 'rssi_vector')
  final Map<String, int> rssiVector;

  @JsonKey(name: 'sample_count')
  final int sampleCount;

  @JsonKey(name: 'device_id')
  final String? deviceId;

  factory FingerprintItemDto.fromJson(Map<String, dynamic> json) =>
      _$FingerprintItemDtoFromJson(json);

  Map<String, dynamic> toJson() => _$FingerprintItemDtoToJson(this);
}
