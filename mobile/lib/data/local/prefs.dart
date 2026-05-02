/// Обёртка над `SharedPreferences` для access-токена и метаданных пользователя.
///
/// Access TTL 30 минут — короткий, защита от XSS на диске не критична;
/// secure-storage медленный для частых обращений (на каждый HTTP-запрос
/// interceptor читает access).
library;

import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';
import 'package:uuid/uuid.dart';

import '../../domain/models/token_pair.dart';
import '../../domain/models/user.dart';

class Prefs {
  Prefs(this._prefs);

  final SharedPreferences _prefs;

  static const String _kAccessToken = 'access_token';
  static const String _kAccessExpiresIn = 'access_expires_in';
  static const String _kAccessIssuedAt = 'access_issued_at';
  static const String _kUser = 'user_json';
  static const String _kDeviceId = 'device_id';

  /// Запись access-токена + времени получения и TTL.
  Future<void> saveAccessToken(
    String token, {
    required int expiresIn,
    required DateTime issuedAt,
  }) async {
    await _prefs.setString(_kAccessToken, token);
    await _prefs.setInt(_kAccessExpiresIn, expiresIn);
    await _prefs.setString(_kAccessIssuedAt, issuedAt.toUtc().toIso8601String());
  }

  Future<String?> getAccessToken() async {
    return _prefs.getString(_kAccessToken);
  }

  /// Полная пара (access + meta + refresh) для UI/логики.
  ///
  /// `refreshToken` берётся отдельно из `SecureStorage` и приклеивается
  /// в `AuthRepositoryImpl.getCachedTokens()` — здесь его нет.
  Future<({int? expiresIn, DateTime? issuedAt})> getAccessMeta() async {
    final expiresIn = _prefs.getInt(_kAccessExpiresIn);
    final issuedAtStr = _prefs.getString(_kAccessIssuedAt);
    final issuedAt = issuedAtStr != null ? DateTime.tryParse(issuedAtStr) : null;
    return (expiresIn: expiresIn, issuedAt: issuedAt);
  }

  Future<void> saveUser(User user) async {
    final map = <String, dynamic>{
      'id': user.id,
      'email': user.email,
      'full_name': user.fullName,
      'role': user.role,
      'is_active': user.isActive,
    };
    await _prefs.setString(_kUser, jsonEncode(map));
  }

  Future<User?> getUser() async {
    final raw = _prefs.getString(_kUser);
    if (raw == null) return null;
    try {
      final map = jsonDecode(raw) as Map<String, dynamic>;
      return User(
        id: map['id'] as int,
        email: map['email'] as String,
        fullName: map['full_name'] as String,
        role: map['role'] as String,
        isActive: map['is_active'] as bool,
      );
    } catch (_) {
      return null;
    }
  }

  /// Идентификатор устройства — генерируется единожды и сохраняется.
  Future<String> getOrCreateDeviceId() async {
    final existing = _prefs.getString(_kDeviceId);
    if (existing != null && existing.isNotEmpty) {
      return existing;
    }
    final newId = const Uuid().v4();
    await _prefs.setString(_kDeviceId, newId);
    return newId;
  }

  Future<void> clearAuth() async {
    await _prefs.remove(_kAccessToken);
    await _prefs.remove(_kAccessExpiresIn);
    await _prefs.remove(_kAccessIssuedAt);
    await _prefs.remove(_kUser);
    // device_id НЕ стираем — он не секретный, единый для устройства
  }

  /// Реконструировать `TokenPair` из access + refresh + meta. Возвращает
  /// `null`, если нет хотя бы одного из обязательных полей.
  TokenPair? buildTokenPair({required String? refreshToken}) {
    final access = _prefs.getString(_kAccessToken);
    final expiresIn = _prefs.getInt(_kAccessExpiresIn);
    final issuedAtStr = _prefs.getString(_kAccessIssuedAt);
    if (access == null ||
        expiresIn == null ||
        issuedAtStr == null ||
        refreshToken == null) {
      return null;
    }
    final issuedAt = DateTime.tryParse(issuedAtStr);
    if (issuedAt == null) return null;
    return TokenPair(
      accessToken: access,
      refreshToken: refreshToken,
      expiresIn: expiresIn,
      issuedAt: issuedAt,
    );
  }
}
