/// Точка входа приложения.
///
/// 1. Привязывает Flutter binding (нужно до Workmanager().initialize в Phase 6).
/// 2. Логирует boot с `BACKEND_URL` и режимом сборки.
/// 3. Запускает приложение в `ProviderScope` (Riverpod) — DI-корень.
library;

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app/app.dart';
import 'core/env.dart';
import 'core/logging.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();

  AppLogger.instance.i(
    '[app.boot] start backendUrl=${Env.backendUrl} debug=$kDebugMode',
  );

  runApp(const ProviderScope(child: SvetlyachokApp()));
}
