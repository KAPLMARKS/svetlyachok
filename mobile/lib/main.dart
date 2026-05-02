/// Точка входа приложения.
///
/// 1. Привязывает Flutter binding (нужно для Workmanager().initialize).
/// 2. Логирует boot с `BACKEND_URL` и режимом сборки.
/// 3. Инициализирует Workmanager с `callbackDispatcher`. Регистрация
///    периодических задач — после login (см. CurrentUserNotifier).
/// 4. Запускает приложение в `ProviderScope` (Riverpod) — DI-корень.
library;

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:workmanager/workmanager.dart';

import 'app/app.dart';
import 'core/env.dart';
import 'core/logging.dart';
import 'features/scanning/background/workmanager_callback.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  AppLogger.instance.i(
    '[app.boot] start backendUrl=${Env.backendUrl} debug=$kDebugMode',
  );

  await Workmanager().initialize(
    callbackDispatcher,
    isInDebugMode: kDebugMode,
  );

  runApp(const ProviderScope(child: SvetlyachokApp()));
}
