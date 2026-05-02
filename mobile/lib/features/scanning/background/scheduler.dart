/// Регистрация/отмена WorkManager-задач.
///
/// Вызывается:
/// - после успешного логина (или при старте, если уже залогинен) →
///   `registerPeriodicTasks()`
/// - при logout → `cancelAll()`
///
/// `ExistingWorkPolicy.keep` — если задачи уже зарегистрированы, не
/// переписываем (Android может перетряхнуть периодичность). Минимальная
/// частота `PeriodicWorkRequest` — 15 минут.
library;

import 'package:workmanager/workmanager.dart';

import '../../../core/constants.dart';
import '../../../core/logging.dart';

abstract class BackgroundScheduler {
  Future<void> registerPeriodicTasks();
  Future<void> cancelAll();
  Future<void> registerOneOffSync();
}

class WorkmanagerScheduler implements BackgroundScheduler {
  WorkmanagerScheduler({Workmanager? workmanager})
      : _wm = workmanager ?? Workmanager();

  final Workmanager _wm;

  @override
  Future<void> registerPeriodicTasks() async {
    await _wm.registerPeriodicTask(
      kBgUniqueScanPeriodic,
      kBgTaskScanAndCache,
      frequency: kBackgroundTaskInterval,
      constraints: Constraints(
        // ignore: constant_identifier_names
        networkType: NetworkType.not_required,
        requiresBatteryNotLow: true,
      ),
      existingWorkPolicy: ExistingWorkPolicy.keep,
    );
    await _wm.registerPeriodicTask(
      kBgUniqueSyncPeriodic,
      kBgTaskSyncFingerprints,
      frequency: kBackgroundTaskInterval,
      constraints: Constraints(networkType: NetworkType.connected),
      existingWorkPolicy: ExistingWorkPolicy.keep,
    );
    AppLogger.instance.i(
      '[bg.scheduler] registered: scanAndCache + syncFingerprints, '
      'period=${kBackgroundTaskInterval.inMinutes}min',
    );
  }

  @override
  Future<void> cancelAll() async {
    await _wm.cancelAll();
    AppLogger.instance.i('[bg.scheduler] cancelled all on logout');
  }

  @override
  Future<void> registerOneOffSync() async {
    await _wm.registerOneOffTask(
      kBgUniqueSyncOneoff,
      kBgTaskSyncFingerprints,
      constraints: Constraints(networkType: NetworkType.connected),
      existingWorkPolicy: ExistingWorkPolicy.replace,
    );
    AppLogger.instance.i('[bg.scheduler] registered one-off sync');
  }
}
