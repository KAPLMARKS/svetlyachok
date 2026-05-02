/// Request DTO для `POST /api/v1/fingerprints/batch`.
library;

import 'package:json_annotation/json_annotation.dart';

import '../../../core/constants.dart';
import 'fingerprint_dto.dart';

part 'batch_request_dto.g.dart';

@JsonSerializable(explicitToJson: true)
class BatchRequestDto {
  BatchRequestDto({required this.items})
      : assert(
          items.length <= kBatchMaxItems,
          'Batch must contain ≤ $kBatchMaxItems items',
        );

  final List<FingerprintItemDto> items;

  factory BatchRequestDto.fromJson(Map<String, dynamic> json) =>
      _$BatchRequestDtoFromJson(json);

  Map<String, dynamic> toJson() => _$BatchRequestDtoToJson(this);
}
