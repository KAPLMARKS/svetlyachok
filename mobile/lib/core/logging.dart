/// Настройка структурированного логирования через пакет `logger`.
///
/// В debug-сборке — `Level.trace` (видим всё, удобно при разработке).
/// В release-сборке — `Level.warning` (только бизнес-предупреждения и ошибки).
///
/// Никаких `print`/`debugPrint` в коде — `analysis_options.yaml` запрещает
/// (`avoid_print: error`). Используется `Logger log = AppLogger.instance` или
/// локальный `final log = Logger();` (PrettyPrinter).
///
/// КРИТИЧНО: никогда не логировать пароли, access/refresh-токены, тело
/// HTTP-ответов с токенами. Проксируется в interceptor'ах через явное
/// маскирование `Authorization: Bearer ***`.
library;

import 'package:flutter/foundation.dart';
import 'package:logger/logger.dart';

/// Глобальная фабрика логгеров: один настроенный экземпляр + helper для
/// именованных под-логгеров (через тэги).
class AppLogger {
  AppLogger._();

  /// Уровень в зависимости от сборки. Foreground UI debug-сессии хотят
  /// видеть всё; release-сборка — только warning+.
  static Level _defaultLevel() => kDebugMode ? Level.trace : Level.warning;

  static Logger? _instance;

  /// Глобальный синглтон. Создаётся лениво при первом обращении.
  static Logger get instance {
    _instance ??= Logger(
      level: _defaultLevel(),
      printer: PrettyPrinter(
        methodCount: 0,
        errorMethodCount: 5,
        lineLength: 100,
        colors: kDebugMode,
        printEmojis: false,
        dateTimeFormat: DateTimeFormat.onlyTimeAndSinceStart,
      ),
    );
    return _instance!;
  }

  /// Сбрасывает синглтон (для тестов).
  @visibleForTesting
  static void reset() {
    _instance = null;
  }
}
