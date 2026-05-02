/// Round-trip JSON-тесты для всех auth-DTO.
library;

import 'package:flutter_test/flutter_test.dart';
import 'package:svetlyachok_mobile/data/api/dto/login_dto.dart';
import 'package:svetlyachok_mobile/data/api/dto/me_dto.dart';
import 'package:svetlyachok_mobile/data/api/dto/token_pair_dto.dart';

void main() {
  test('LoginRequestDto round-trip', () {
    const dto = LoginRequestDto(email: 'a@b.c', password: 'secret123');
    final json = dto.toJson();
    expect(json, <String, dynamic>{'email': 'a@b.c', 'password': 'secret123'});

    final parsed = LoginRequestDto.fromJson(json);
    expect(parsed.email, 'a@b.c');
    expect(parsed.password, 'secret123');
  });

  test('TokenPairDto maps snake_case to camelCase', () {
    final json = <String, dynamic>{
      'access_token': 'aaa.bbb.ccc',
      'refresh_token': 'xxx.yyy.zzz',
      'token_type': 'bearer',
      'expires_in': 1800,
    };
    final dto = TokenPairDto.fromJson(json);
    expect(dto.accessToken, 'aaa.bbb.ccc');
    expect(dto.refreshToken, 'xxx.yyy.zzz');
    expect(dto.tokenType, 'bearer');
    expect(dto.expiresIn, 1800);

    expect(dto.toJson(), json);
  });

  test('MeDto maps full_name and is_active', () {
    final json = <String, dynamic>{
      'id': 42,
      'email': 'admin@svetlyachok.local',
      'full_name': 'Иванов И.И.',
      'role': 'admin',
      'is_active': true,
    };
    final dto = MeDto.fromJson(json);
    expect(dto.id, 42);
    expect(dto.fullName, 'Иванов И.И.');
    expect(dto.role, 'admin');
    expect(dto.isActive, isTrue);
  });
}
