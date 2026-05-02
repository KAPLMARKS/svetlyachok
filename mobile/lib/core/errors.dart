/// Иерархия ошибок (Failure-классы) для Result-pattern.
///
/// Все методы репозиториев возвращают `Either<Failure, T>` (см. `result.dart`).
/// Конкретные подтипы Failure позволяют UI показывать понятные сообщения
/// и принимать решения (retry, relogin, открыть настройки и т. д.).
library;

import 'package:equatable/equatable.dart';

/// Базовый класс для ошибок проекта. Не выбрасывается как exception —
/// упаковывается в `Left<Failure, T>` через dartz.
sealed class Failure extends Equatable {
  const Failure({required this.message, this.code});

  /// Технический код (для логов и UI-ветвлений). Стабильные коды:
  /// `network_no_connection`, `network_timeout`, `auth_unauthorized`,
  /// `auth_forbidden`, `auth_expired`, `server_bad_request`, `server_internal`,
  /// `cache_io`, `wifi_throttled`, `wifi_permission_denied`,
  /// `wifi_location_off`, `wifi_no_results`, `validation_invalid`,
  /// `unknown`.
  final String? code;

  /// Человекочитаемое сообщение для UI (русский).
  final String message;

  @override
  List<Object?> get props => [code, message];
}

/// Сетевые ошибки: нет интернета, таймаут, DNS и т. д.
class NetworkFailure extends Failure {
  const NetworkFailure({required super.message, super.code});

  factory NetworkFailure.noConnection() => const NetworkFailure(
        code: 'network_no_connection',
        message: 'Нет соединения с сервером',
      );

  factory NetworkFailure.timeout() => const NetworkFailure(
        code: 'network_timeout',
        message: 'Превышено время ожидания ответа сервера',
      );
}

/// Ошибки аутентификации/авторизации.
class AuthFailure extends Failure {
  const AuthFailure({required super.message, super.code});

  factory AuthFailure.unauthorized() => const AuthFailure(
        code: 'auth_unauthorized',
        message: 'Неверный логин или пароль',
      );

  factory AuthFailure.forbidden() => const AuthFailure(
        code: 'auth_forbidden',
        message: 'Недостаточно прав для выполнения операции',
      );

  /// Refresh не удался — нужен релогин.
  factory AuthFailure.expired() => const AuthFailure(
        code: 'auth_expired',
        message: 'Сессия истекла, войдите снова',
      );
}

/// HTTP 4xx/5xx, не покрытые AuthFailure.
class ServerFailure extends Failure {
  const ServerFailure({
    required super.message,
    super.code,
    this.statusCode,
  });

  final int? statusCode;

  factory ServerFailure.badRequest({String? detail}) => ServerFailure(
        code: 'server_bad_request',
        message: detail ?? 'Сервер отклонил запрос',
        statusCode: 400,
      );

  factory ServerFailure.internal({int? statusCode, String? detail}) =>
      ServerFailure(
        code: 'server_internal',
        message: detail ?? 'Ошибка на стороне сервера',
        statusCode: statusCode,
      );

  @override
  List<Object?> get props => [code, message, statusCode];
}

/// Ошибки локального хранилища (sqflite, secure storage, prefs).
class CacheFailure extends Failure {
  const CacheFailure({required super.message, super.code});

  factory CacheFailure.io({String? detail}) => CacheFailure(
        code: 'cache_io',
        message: detail ?? 'Ошибка локального хранилища',
      );
}

/// Логическая валидация (UI-форма, длина пароля, формат email).
class ValidationFailure extends Failure {
  const ValidationFailure({required super.message, super.code});
}

/// Wi-Fi throttling — система не позволила выполнить ещё один скан.
class ThrottledFailure extends Failure {
  const ThrottledFailure({required super.message, super.code});

  factory ThrottledFailure.scan({Duration? retryAfter}) => ThrottledFailure(
        code: 'wifi_throttled',
        message: retryAfter != null
            ? 'Слишком частое сканирование Wi-Fi. Повторите через ${retryAfter.inSeconds} сек.'
            : 'Слишком частое сканирование Wi-Fi. Повторите позже.',
      );
}

/// Permission или системные настройки запретили операцию.
class PermissionFailure extends Failure {
  const PermissionFailure({required super.message, super.code});

  factory PermissionFailure.locationDenied() => const PermissionFailure(
        code: 'wifi_permission_denied',
        message: 'Нет разрешения на использование местоположения',
      );

  factory PermissionFailure.locationServiceOff() => const PermissionFailure(
        code: 'wifi_location_off',
        message: 'Включите службы геолокации в настройках',
      );

  factory PermissionFailure.notSupported() => const PermissionFailure(
        code: 'wifi_not_supported',
        message: 'Wi-Fi сканирование недоступно на этом устройстве',
      );
}

/// Неизвестная ошибка — fallback при необработанных исключениях.
class UnknownFailure extends Failure {
  const UnknownFailure({required super.message, super.code = 'unknown'});

  factory UnknownFailure.from(Object error) => UnknownFailure(
        message: 'Непредвиденная ошибка: $error',
      );
}
