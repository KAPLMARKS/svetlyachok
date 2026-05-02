/// Доменная модель пары JWT-токенов.
///
/// `accessToken` — короткоживущий (30 мин по бекенду), хранится в
/// SharedPreferences. `refreshToken` — 7 дней TTL, хранится в
/// flutter_secure_storage. `issuedAt` — момент получения пары (UTC),
/// нужен для `isAccessExpired` без обращения к серверу.
library;

import 'package:freezed_annotation/freezed_annotation.dart';

import '../../core/constants.dart';

part 'token_pair.freezed.dart';

@freezed
class TokenPair with _$TokenPair {
  const factory TokenPair({
    required String accessToken,
    required String refreshToken,
    required int expiresIn,
    required DateTime issuedAt,
  }) = _TokenPair;

  const TokenPair._();

  /// `true`, если access-токен истёк или вот-вот истечёт.
  ///
  /// `kAccessTokenRefreshBuffer` (30 сек) — запас на сетевые задержки и
  /// clock skew между клиентом и сервером.
  bool get isAccessExpired {
    final now = DateTime.now().toUtc();
    final expiresAt = issuedAt.toUtc().add(Duration(seconds: expiresIn));
    return now.isAfter(expiresAt.subtract(kAccessTokenRefreshBuffer));
  }
}
