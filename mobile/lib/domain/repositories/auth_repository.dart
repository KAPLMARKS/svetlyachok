/// Контракт репозитория аутентификации.
///
/// Реализация в `data/repositories/auth_repository_impl.dart` использует
/// Dio для HTTP-запросов и SecureStorage/Prefs для кэша токенов.
/// Use cases / view models / providers зависят от этой абстракции.
library;

import '../../core/result.dart';
import '../models/token_pair.dart';
import '../models/user.dart';

abstract class AuthRepository {
  /// `POST /auth/login` — обмен email+пароль на пару токенов.
  Future<Result<TokenPair>> login(String email, String password);

  /// `POST /auth/refresh` — обмен refresh на новую пару токенов.
  Future<Result<TokenPair>> refresh(String refreshToken);

  /// `GET /me` — получение текущего пользователя.
  Future<Result<User>> me();

  /// `POST /auth/logout` — best-effort серверный logout + локальная очистка.
  Future<Result<void>> logout();

  /// Локально кэшированная пара (или `null`, если ещё не логинился).
  Future<TokenPair?> getCachedTokens();

  /// Локально кэшированный пользователь (`/me` ответ).
  Future<User?> getCachedUser();

  /// Стереть и токены, и пользователя локально (без обращения к серверу).
  Future<void> clearCache();
}
