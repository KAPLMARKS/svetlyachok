/// Compile-time окружение (передаётся через `--dart-define`).
///
/// Пример запуска:
/// ```bash
/// fvm flutter run --dart-define=BACKEND_URL=http://192.168.1.10:8000
/// fvm flutter build apk --release --dart-define=BACKEND_URL=http://192.168.1.10:8000
/// ```
///
/// Default — `http://10.0.2.2:8000` (loopback к хосту с Android-эмулятора).
class Env {
  const Env._();

  /// Базовый URL backend без `/api/v1` (префикс добавляется в Dio).
  static const String backendUrl = String.fromEnvironment(
    'BACKEND_URL',
    defaultValue: 'http://10.0.2.2:8000',
  );

  /// Включить расширенное логирование Dio (тело запросов/ответов).
  /// По умолчанию `false`, не используется в release-сборке.
  static const bool verboseHttpLogs = bool.fromEnvironment(
    'VERBOSE_HTTP',
    defaultValue: false,
  );
}
