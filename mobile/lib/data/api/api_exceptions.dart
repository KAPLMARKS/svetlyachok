/// Маппинг низкоуровневых HTTP/сетевых исключений в доменные `Failure`.
///
/// Используется в repository implementations: ловим `DioException`,
/// возвращаем `Result.failure(...)` с правильным подтипом.
library;

import 'package:dio/dio.dart';

import '../../core/errors.dart';

/// Конвертирует `DioException` в подходящий `Failure`.
///
/// Никогда не пробрасывает исходный exception дальше — все ошибки
/// унифицируются через Result-pattern.
Failure mapDioErrorToFailure(DioException error) {
  switch (error.type) {
    case DioExceptionType.connectionError:
    case DioExceptionType.unknown:
      return NetworkFailure.noConnection();
    case DioExceptionType.connectionTimeout:
    case DioExceptionType.sendTimeout:
    case DioExceptionType.receiveTimeout:
      return NetworkFailure.timeout();
    case DioExceptionType.badCertificate:
      return NetworkFailure.noConnection();
    case DioExceptionType.cancel:
      return const UnknownFailure(
        message: 'Запрос отменён',
        code: 'request_cancelled',
      );
    case DioExceptionType.badResponse:
      return _mapBadResponse(error.response);
  }
}

Failure _mapBadResponse(Response<dynamic>? response) {
  final statusCode = response?.statusCode;
  final body = response?.data;
  final problemDetail = _extractProblemDetail(body);
  switch (statusCode) {
    case 400:
      return ServerFailure.badRequest(detail: problemDetail);
    case 401:
      return AuthFailure.unauthorized();
    case 403:
      return AuthFailure.forbidden();
    case 404:
      return ServerFailure(
        code: 'server_not_found',
        message: problemDetail ?? 'Ресурс не найден',
        statusCode: 404,
      );
    case 409:
      return ServerFailure(
        code: 'server_conflict',
        message: problemDetail ?? 'Конфликт состояния',
        statusCode: 409,
      );
    case 422:
      return ValidationFailure(
        code: 'validation_failed',
        message: problemDetail ?? 'Невалидные данные запроса',
      );
    case 429:
      return ServerFailure(
        code: 'rate_limit_exceeded',
        message: problemDetail ?? 'Слишком много запросов, повторите позже',
        statusCode: 429,
      );
    case 503:
      return ServerFailure(
        code: 'server_unavailable',
        message: problemDetail ?? 'Сервис временно недоступен',
        statusCode: 503,
      );
    default:
      return ServerFailure.internal(
        statusCode: statusCode,
        detail: problemDetail,
      );
  }
}

String? _extractProblemDetail(Object? body) {
  if (body is Map<String, dynamic>) {
    final detail = body['detail'];
    if (detail is String && detail.isNotEmpty) {
      return detail;
    }
    final code = body['code'];
    if (code is String && code.isNotEmpty) {
      return code;
    }
  }
  return null;
}
