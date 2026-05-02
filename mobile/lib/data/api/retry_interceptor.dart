/// Retry-interceptor для Dio с экспоненциальным backoff.
///
/// Применяется только к идемпотентным методам (`GET`) и к
/// `POST /api/v1/fingerprints/batch` — он по семантике не делает дедупликацию,
/// но повторная отправка тех же items даёт partial-success (ничего не
/// сломаем). Авторизационные эндпоинты (`/auth/login`/`/auth/refresh`)
/// исключены — повтор неверного пароля попадёт под rate-limit.
library;

import 'package:dio/dio.dart';
import 'package:dio_smart_retry/dio_smart_retry.dart';

import '../../core/constants.dart';

RetryInterceptor buildRetryInterceptor(Dio dio) {
  return RetryInterceptor(
    dio: dio,
    retries: 3,
    retryDelays: const <Duration>[
      Duration(seconds: 1),
      Duration(seconds: 3),
      Duration(seconds: 8),
    ],
    retryEvaluator: _shouldRetry,
  );
}

Future<bool> _shouldRetry(DioException err, int attempt) async {
  final method = err.requestOptions.method.toUpperCase();
  final path = err.requestOptions.path;

  // /auth/* никогда не retry — ни login (rate-limit), ни refresh (single-flight),
  // ни logout (не критично).
  if (path.contains('/auth/')) {
    return false;
  }

  if (method == 'GET') {
    return DefaultRetryEvaluator(defaultRetryableStatuses).evaluate(err, attempt);
  }

  // POST /fingerprints/batch — семантически безопасен для retry на network/5xx.
  if (method == 'POST' &&
      path.endsWith('$kApiVersionPrefix/fingerprints/batch')) {
    return DefaultRetryEvaluator(defaultRetryableStatuses).evaluate(err, attempt);
  }

  return false;
}
