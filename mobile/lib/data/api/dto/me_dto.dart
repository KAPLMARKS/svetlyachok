/// DTO ответа `GET /api/v1/me`.
library;

import 'package:json_annotation/json_annotation.dart';

part 'me_dto.g.dart';

@JsonSerializable()
class MeDto {
  const MeDto({
    required this.id,
    required this.email,
    required this.fullName,
    required this.role,
    required this.isActive,
  });

  final int id;
  final String email;

  @JsonKey(name: 'full_name')
  final String fullName;

  final String role;

  @JsonKey(name: 'is_active')
  final bool isActive;

  Map<String, dynamic> toJson() => _$MeDtoToJson(this);

  factory MeDto.fromJson(Map<String, dynamic> json) => _$MeDtoFromJson(json);
}
