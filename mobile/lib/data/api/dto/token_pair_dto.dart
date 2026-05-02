/// DTO ответа `POST /auth/login` и `POST /auth/refresh`.
///
/// Backend возвращает поля в snake_case, в Dart мы используем camelCase
/// через `@JsonKey(name: ...)`.
library;

import 'package:json_annotation/json_annotation.dart';

part 'token_pair_dto.g.dart';

@JsonSerializable()
class TokenPairDto {
  const TokenPairDto({
    required this.accessToken,
    required this.refreshToken,
    required this.tokenType,
    required this.expiresIn,
  });

  @JsonKey(name: 'access_token')
  final String accessToken;

  @JsonKey(name: 'refresh_token')
  final String refreshToken;

  @JsonKey(name: 'token_type')
  final String tokenType;

  @JsonKey(name: 'expires_in')
  final int expiresIn;

  Map<String, dynamic> toJson() => _$TokenPairDtoToJson(this);

  factory TokenPairDto.fromJson(Map<String, dynamic> json) =>
      _$TokenPairDtoFromJson(json);
}
