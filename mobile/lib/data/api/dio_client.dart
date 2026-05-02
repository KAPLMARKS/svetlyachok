/// Фабрика Dio-клиента с auth + retry интерсепторами.
///
/// Возвращает пару `(mainDio, refreshDio)`:
/// - `mainDio` — для всех app-запросов, включает `AuthInterceptor` и retry;
/// - `refreshDio` — отдельный экземпляр без interceptor'ов; используется
///   `AuthInterceptor` для рефреша токена (исключаем рекурсию).
///
/// `baseOptions.baseUrl` = `Env.backendUrl`. Префикс `/api/v1` добавляется
/// к каждому пути в endpoint-методах.
library;

import 'package:dio/dio.dart';

import '../../core/env.dart';
import '../local/prefs.dart';
import '../local/secure_storage.dart';
import 'auth_interceptor.dart';
import 'retry_interceptor.dart';

class DioPair {
  const DioPair({required this.main, required this.refresh, required this.auth});

  final Dio main;
  final Dio refresh;
  final AuthInterceptor auth;
}

DioPair buildDio({
  required Prefs prefs,
  required SecureStorage secureStorage,
}) {
  final BaseOptions options = BaseOptions(
    baseUrl: Env.backendUrl,
    connectTimeout: const Duration(seconds: 10),
    sendTimeout: const Duration(seconds: 15),
    receiveTimeout: const Duration(seconds: 30),
    contentType: 'application/json',
    responseType: ResponseType.json,
    validateStatus: (int? status) =>
        status != null && status >= 200 && status < 300,
  );

  final Dio refreshDio = Dio(options);
  final Dio mainDio = Dio(options);

  final AuthInterceptor authInterceptor = AuthInterceptor(
    prefs: prefs,
    secureStorage: secureStorage,
    refreshDio: refreshDio,
  );

  mainDio.interceptors
    ..add(authInterceptor)
    ..add(buildRetryInterceptor(mainDio));

  return DioPair(main: mainDio, refresh: refreshDio, auth: authInterceptor);
}
