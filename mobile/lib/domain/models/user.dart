/// Доменная модель сотрудника.
///
/// Соответствует ответу `GET /api/v1/me` backend'а. UI gate'ы (admin-режим
/// калибровки) пользуются геттером `isAdmin`. Серверная проверка роли
/// дублируется на каждом admin-эндпоинте — UI gate тут только для UX.
library;

import 'package:freezed_annotation/freezed_annotation.dart';

part 'user.freezed.dart';

@freezed
class User with _$User {
  const factory User({
    required int id,
    required String email,
    required String fullName,
    required String role,
    required bool isActive,
  }) = _User;

  const User._();

  bool get isAdmin => role == 'admin';
}
