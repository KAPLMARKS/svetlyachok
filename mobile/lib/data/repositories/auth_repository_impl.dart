/// Имплементация `AuthRepository` через Dio + SecureStorage + Prefs.
///
/// Никаких токенов/паролей в логах — только email и тип события.
library;

import 'package:dartz/dartz.dart';
import 'package:dio/dio.dart';
import 'package:logger/logger.dart';

import '../../core/constants.dart';
import '../../core/errors.dart';
import '../../core/logging.dart';
import '../../core/result.dart';
import '../../domain/models/token_pair.dart';
import '../../domain/models/user.dart';
import '../../domain/repositories/auth_repository.dart';
import '../api/api_exceptions.dart';
import '../api/dto/login_dto.dart';
import '../api/dto/me_dto.dart';
import '../api/dto/token_pair_dto.dart';
import '../local/prefs.dart';
import '../local/secure_storage.dart';

class AuthRepositoryImpl implements AuthRepository {
  AuthRepositoryImpl({
    required Dio dio,
    required Prefs prefs,
    required SecureStorage secureStorage,
    Logger? logger,
  })  : _dio = dio,
        _prefs = prefs,
        _secureStorage = secureStorage,
        _log = logger ?? AppLogger.instance;

  final Dio _dio;
  final Prefs _prefs;
  final SecureStorage _secureStorage;
  final Logger _log;

  @override
  Future<Result<TokenPair>> login(String email, String password) async {
    _log.i('[auth.login] start email=$email');
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '$kApiVersionPrefix/auth/login',
        data: LoginRequestDto(email: email, password: password).toJson(),
      );
      final body = response.data;
      if (body == null) {
        return failure(ServerFailure.internal(detail: 'empty_response'));
      }
      final dto = TokenPairDto.fromJson(body);
      final issuedAt = DateTime.now().toUtc();
      await _persistTokens(dto, issuedAt: issuedAt);
      _log.i('[auth.login] success email=$email');
      return success(
        TokenPair(
          accessToken: dto.accessToken,
          refreshToken: dto.refreshToken,
          expiresIn: dto.expiresIn,
          issuedAt: issuedAt,
        ),
      );
    } on DioException catch (e) {
      _log.w('[auth.login] failed: ${e.response?.statusCode}');
      return failure(mapDioErrorToFailure(e));
    } catch (e) {
      _log.e('[auth.login] unexpected: $e');
      return failure(UnknownFailure.from(e));
    }
  }

  @override
  Future<Result<TokenPair>> refresh(String refreshToken) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '$kApiVersionPrefix/auth/refresh',
        data: <String, dynamic>{'refresh_token': refreshToken},
      );
      final body = response.data;
      if (body == null) {
        return failure(ServerFailure.internal(detail: 'empty_response'));
      }
      final dto = TokenPairDto.fromJson(body);
      final issuedAt = DateTime.now().toUtc();
      await _persistTokens(dto, issuedAt: issuedAt);
      return success(
        TokenPair(
          accessToken: dto.accessToken,
          refreshToken: dto.refreshToken,
          expiresIn: dto.expiresIn,
          issuedAt: issuedAt,
        ),
      );
    } on DioException catch (e) {
      _log.w('[auth.refresh] failed: ${e.response?.statusCode}');
      return failure(mapDioErrorToFailure(e));
    } catch (e) {
      return failure(UnknownFailure.from(e));
    }
  }

  @override
  Future<Result<User>> me() async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        '$kApiVersionPrefix/me',
      );
      final body = response.data;
      if (body == null) {
        return failure(ServerFailure.internal(detail: 'empty_response'));
      }
      final dto = MeDto.fromJson(body);
      final user = User(
        id: dto.id,
        email: dto.email,
        fullName: dto.fullName,
        role: dto.role,
        isActive: dto.isActive,
      );
      await _prefs.saveUser(user);
      _log.i('[auth.me] resolved id=${user.id} role=${user.role}');
      return success(user);
    } on DioException catch (e) {
      _log.w('[auth.me] failed: ${e.response?.statusCode}');
      return failure(mapDioErrorToFailure(e));
    } catch (e) {
      return failure(UnknownFailure.from(e));
    }
  }

  @override
  Future<Result<void>> logout() async {
    _log.i('[auth.logout] start');
    Failure? networkFailure;
    try {
      await _dio.post<dynamic>('$kApiVersionPrefix/auth/logout');
    } on DioException catch (e) {
      // Best-effort — даже если /logout вернул 401/network error,
      // локальную сессию всё равно стираем.
      _log.w(
        '[auth.logout] server failed (best-effort): ${e.response?.statusCode}',
      );
      networkFailure = mapDioErrorToFailure(e);
    } catch (e) {
      _log.w('[auth.logout] unexpected (best-effort): $e');
    }
    await clearCache();
    _log.i('[auth.logout] tokens cleared');
    if (networkFailure != null) {
      // Возвращаем «успех» — логично с точки зрения UX (пользователь вышел).
      // Но предупредим в логе. Бизнес выбор: считать success.
      return const Right<Failure, void>(null);
    }
    return const Right<Failure, void>(null);
  }

  @override
  Future<TokenPair?> getCachedTokens() async {
    final refresh = await _secureStorage.getRefreshToken();
    return _prefs.buildTokenPair(refreshToken: refresh);
  }

  @override
  Future<User?> getCachedUser() => _prefs.getUser();

  @override
  Future<void> clearCache() async {
    await _prefs.clearAuth();
    await _secureStorage.clear();
  }

  Future<void> _persistTokens(
    TokenPairDto dto, {
    required DateTime issuedAt,
  }) async {
    await _prefs.saveAccessToken(
      dto.accessToken,
      expiresIn: dto.expiresIn,
      issuedAt: issuedAt,
    );
    await _secureStorage.saveRefreshToken(dto.refreshToken);
  }
}
