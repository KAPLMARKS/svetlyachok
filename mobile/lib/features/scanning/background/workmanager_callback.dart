/// Точка входа Workmanager-воркера.
///
/// Workmanager при срабатывании задачи поднимает изолят без UI и без
/// `ProviderScope`. Мы собираем минимальный DI прямо здесь:
/// - `SharedPreferences.getInstance()`
/// - `SecureStorage()`
/// - `AppDatabase()` (откроет sqflite по тому же пути, что foreground)
/// - `Dio` через `buildDio()` (включит auth-interceptor с авторефрешом)
/// - `WifiScanServiceImpl()` + `FingerprintRepositoryImpl`
///
/// Switch по `taskName`:
/// - `kBgTaskScanAndCache` (`scanAndCache`) → `repository.capture()`
/// - `kBgTaskSyncFingerprints` (`syncFingerprints`) → `repository.syncPending()`
///
/// Возвращаем `true` при успехе или recoverable error (workmanager
/// переотправит позже); `false` при terminal failure (требуется релогин —
/// записываем флаг `auth_expired_at` в Prefs, чтобы foreground заметил).
library;

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:workmanager/workmanager.dart';

import '../../../core/constants.dart';
import '../../../core/logging.dart';
import '../../../data/api/dio_client.dart';
import '../../../data/local/db.dart';
import '../../../data/local/fingerprint_cache_dao.dart';
import '../../../data/local/prefs.dart';
import '../../../data/local/secure_storage.dart';
import '../../../data/repositories/fingerprint_repository_impl.dart';
import '../../../data/wifi/wifi_scan_service.dart';
import '../../../domain/repositories/fingerprint_repository.dart';

/// Чистая логика capture-таска — отдельной функцией для unit-тестов.
Future<bool> runScanAndCache(FingerprintRepository repo) async {
  final result = await repo.capture();
  return result.fold((_) => false, (_) => true);
}

/// Чистая логика sync-таска.
Future<bool> runSyncFingerprints(FingerprintRepository repo) async {
  final result = await repo.syncPending();
  return result.fold((_) => false, (_) => true);
}

@pragma('vm:entry-point')
void callbackDispatcher() {
  Workmanager().executeTask((String taskName, Map<String, dynamic>? input) async {
    AppLogger.instance.i('[bg] task started: name=$taskName');
    try {
      final sp = await SharedPreferences.getInstance();
      final prefs = Prefs(sp);
      final secure = SecureStorage();
      final db = AppDatabase();
      final dao = FingerprintCacheDao(db);
      final dioPair = buildDio(prefs: prefs, secureStorage: secure);
      final wifi = WifiScanServiceImpl();
      final repo = FingerprintRepositoryImpl(
        wifiScan: wifi,
        cacheDao: dao,
        dio: dioPair.main,
        prefs: prefs,
        connectivity: ConnectivityPlusChecker(),
      );

      bool ok;
      switch (taskName) {
        case kBgTaskScanAndCache:
          ok = await runScanAndCache(repo);
          break;
        case kBgTaskSyncFingerprints:
          ok = await runSyncFingerprints(repo);
          break;
        default:
          AppLogger.instance.w('[bg] unknown task: $taskName');
          ok = true;
      }

      await repo.dispose();
      await db.close();
      dioPair.main.close(force: true);
      dioPair.refresh.close(force: true);

      AppLogger.instance.i('[bg] task finished: name=$taskName, success=$ok');
      return ok;
    } catch (e, st) {
      AppLogger.instance.e(
        '[bg] uncaught: $e',
        error: e,
        stackTrace: st,
      );
      // Возвращаем true только в debug — чтобы Workmanager не спамил
      // переотправками одного и того же сломанного таска.
      return kDebugMode;
    }
  });
}
