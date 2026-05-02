/// DTO для `GET /api/v1/zones` ответа.
library;

import 'package:json_annotation/json_annotation.dart';

part 'zone_dto.g.dart';

@JsonSerializable()
class ZoneDto {
  const ZoneDto({
    required this.id,
    required this.name,
    required this.type,
    this.description,
    this.displayColor,
  });

  final int id;
  final String name;
  final String type;
  final String? description;

  @JsonKey(name: 'display_color')
  final String? displayColor;

  factory ZoneDto.fromJson(Map<String, dynamic> json) =>
      _$ZoneDtoFromJson(json);

  Map<String, dynamic> toJson() => _$ZoneDtoToJson(this);
}

@JsonSerializable(explicitToJson: true)
class ZonesPageDto {
  const ZonesPageDto({
    required this.items,
    required this.total,
    required this.limit,
    required this.offset,
  });

  final List<ZoneDto> items;
  final int total;
  final int limit;
  final int offset;

  factory ZonesPageDto.fromJson(Map<String, dynamic> json) =>
      _$ZonesPageDtoFromJson(json);

  Map<String, dynamic> toJson() => _$ZonesPageDtoToJson(this);
}
