/// Auth-interceptor для Dio: подставляет Bearer access-токен и обрабатывает
/// 401 через single-flight refresh.
///
/// Стратегия:
/// - `onRequest`: если есть access — добавляем `Authorization: Bearer ...`.
///   Эндпоинты `/auth/login` и `/auth/refresh` пропускаем без заголовка.
/// - `onError` при 401:
///   1. Если запрос уже retry'ился — отдаём ошибку дальше (нет цикла).
///   2. Иначе — через `Mutex` (пакет `synchronized`) пытаемся refresh.
///      Все параллельные 401 ждут один shared refresh-фьючер.
///   3. На успех — обновляем токен в Prefs и повторяем оригинальный запрос.
///   4. На неудачу — emit `AuthExpired` через `authEvents` стрим, очищаем
///      кэш, отдаём 401 наверх.
///
/// КРИТИЧНО — НЕ ЛОГИРОВАТЬ:
/// - Тело /auth/login (пароль)
/// - Тело /auth/refresh (refresh-токен)
/// - Заголовок `Authorization` (access-токен)
/// - Тело ответа /auth/login и /auth/refresh (новые токены)
library;

import 'dart:async';

import 'package:dio/dio.dart';
import 'package:logger/logger.dart';
import 'package:synchronized/synchronized.dart';

import '../../core/constants.dart';
import '../../core/logging.dart';
import '../local/prefs.dart';
import '../local/secure_storage.dart';
import 'dto/token_pair_dto.dart';

/// События auth-стрима для UI (router редиректит на /login).
enum AuthEvent { expired }

class AuthInterceptor extends Interceptor {
  AuthInterceptor({
    required Prefs prefs,
    required SecureStorage secureStorage,
    required Dio refreshDio,
    Logger? logger,
  })  : _prefs = prefs,
        _secureStorage = secureStorage,
        _refreshDio = refreshDio,
        _log = logger ?? AppLogger.instance;

  final Prefs _prefs;
  final SecureStorage _secureStorage;

  /// Отдельный Dio без interceptor'ов — чтобы рефрешить без рекурсии.
  final Dio _refreshDio;
  final Logger _log;

  final Lock _refreshLock = Lock();
  final StreamController<AuthEvent> _events =
      StreamController<AuthEvent>.broadcast();

  Stream<AuthEvent> get events => _events.stream;

  /// Roughly: any in-flight refresh future shared between concurrent 401s.
  Future<String?>? _ongoingRefresh;

  static const String _retryFlag = 'auth_retried';

  bool _isAuthEndpoint(String path) {
    return path.endsWith('/auth/login') ||
        path.endsWith('/auth/refresh') ||
        path.endsWith('/auth/logout');
  }

  @override
  Future<void> onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) async {
    if (!_isAuthEndpoint(options.path)) {
      final access = await _prefs.getAccessToken();
      if (access != null && access.isNotEmpty) {
        options.headers['Authorization'] = 'Bearer $access';
      }
    }
    handler.next(options);
  }

  @override
  Future<void> onError(
    DioException err,
    ErrorInterceptorHandler handler,
  ) async {
    final response = err.response;
    final isUnauthorized = response?.statusCode == 401;
    final alreadyRetried = err.requestOptions.extra[_retryFlag] == true;
    final isRefreshOrLogin = _isAuthEndpoint(err.requestOptions.path);

    if (!isUnauthorized || alreadyRetried || isRefreshOrLogin) {
      handler.next(err);
      return;
    }

    final newAccess = await _refreshOnce();
    if (newAccess == null) {
      _log.w('[auth.interceptor] refresh failed, emitting AuthExpired');
      _events.add(AuthEvent.expired);
      handler.next(err);
      return;
    }

    // Retry оригинального запроса с новым токеном.
    final retryOptions = err.requestOptions
      ..headers['Authorization'] = 'Bearer $newAccess'
      ..extra[_retryFlag] = true;

    try {
      final retryResponse = await _refreshDio.fetch<dynamic>(retryOptions);
      handler.resolve(retryResponse);
    } on DioException catch (retryErr) {
      handler.next(retryErr);
    }
  }

  /// Single-flight refresh: первый параллельный 401 запускает реальный
  /// `POST /auth/refresh`, остальные ждут результат.
  Future<String?> _refreshOnce() async {
    return _refreshLock.synchronized(() async {
      final ongoing = _ongoingRefresh;
      if (ongoing != null) {
        return ongoing;
      }

      final completer = Completer<String?>();
      _ongoingRefresh = completer.future;

      try {
        final refresh = await _secureStorage.getRefreshToken();
        if (refresh == null || refresh.isEmpty) {
          completer.complete(null);
          return null;
        }

        _log.d('[auth.interceptor] refreshing access token');
        final response = await _refreshDio.post<Map<String, dynamic>>(
          '$kApiVersionPrefix/auth/refresh',
          data: <String, dynamic>{'refresh_token': refresh},
        );

        final body = response.data;
        if (body == null) {
          completer.complete(null);
          return null;
        }
        final dto = TokenPairDto.fromJson(body);
        await _prefs.saveAccessToken(
          dto.accessToken,
          expiresIn: dto.expiresIn,
          issuedAt: DateTime.now().toUtc(),
        );
        await _secureStorage.saveRefreshToken(dto.refreshToken);
        _log.i('[auth.interceptor] refresh success');
        completer.complete(dto.accessToken);
        return dto.accessToken;
      } on DioException catch (e) {
        _log.w(
          '[auth.interceptor] refresh failed: ${e.response?.statusCode}',
        );
        completer.complete(null);
        return null;
      } catch (e) {
        _log.e('[auth.interceptor] refresh unexpected error: $e');
        completer.complete(null);
        return null;
      } finally {
        _ongoingRefresh = null;
      }
    });
  }

  /// Освобождает ресурсы (для тестов).
  Future<void> dispose() async {
    await _events.close();
  }
}
