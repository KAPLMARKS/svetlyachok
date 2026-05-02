// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'batch_request_dto.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

BatchRequestDto _$BatchRequestDtoFromJson(Map<String, dynamic> json) =>
    BatchRequestDto(
      items: (json['items'] as List<dynamic>)
          .map((e) => FingerprintItemDto.fromJson(e as Map<String, dynamic>))
          .toList(),
    );

Map<String, dynamic> _$BatchRequestDtoToJson(BatchRequestDto instance) =>
    <String, dynamic>{
      'items': instance.items.map((e) => e.toJson()).toList(),
    };
