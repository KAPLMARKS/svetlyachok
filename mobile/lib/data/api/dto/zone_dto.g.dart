// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'zone_dto.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

ZoneDto _$ZoneDtoFromJson(Map<String, dynamic> json) => ZoneDto(
      id: (json['id'] as num).toInt(),
      name: json['name'] as String,
      type: json['type'] as String,
      description: json['description'] as String?,
      displayColor: json['display_color'] as String?,
    );

Map<String, dynamic> _$ZoneDtoToJson(ZoneDto instance) => <String, dynamic>{
      'id': instance.id,
      'name': instance.name,
      'type': instance.type,
      'description': instance.description,
      'display_color': instance.displayColor,
    };

ZonesPageDto _$ZonesPageDtoFromJson(Map<String, dynamic> json) => ZonesPageDto(
      items: (json['items'] as List<dynamic>)
          .map((e) => ZoneDto.fromJson(e as Map<String, dynamic>))
          .toList(),
      total: (json['total'] as num).toInt(),
      limit: (json['limit'] as num).toInt(),
      offset: (json['offset'] as num).toInt(),
    );

Map<String, dynamic> _$ZonesPageDtoToJson(ZonesPageDto instance) =>
    <String, dynamic>{
      'items': instance.items.map((e) => e.toJson()).toList(),
      'total': instance.total,
      'limit': instance.limit,
      'offset': instance.offset,
    };
