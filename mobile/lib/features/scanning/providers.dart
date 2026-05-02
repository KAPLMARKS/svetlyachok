/// Провайдеры scanning-фичи: WifiScanService, AppDatabase + DAO,
/// ConnectivityChecker, FingerprintRepository.
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/local/db.dart';
import '../../data/local/fingerprint_cache_dao.dart';
import '../../data/repositories/fingerprint_repository_impl.dart';
import '../../data/wifi/wifi_scan_service.dart';
import '../../domain/repositories/fingerprint_repository.dart';
import '../auth/providers.dart';

final Provider<WifiScanService> wifiScanServiceProvider =
    Provider<WifiScanService>((Ref ref) => WifiScanServiceImpl());

final Provider<AppDatabase> appDatabaseProvider = Provider<AppDatabase>((Ref ref) {
  final db = AppDatabase();
  ref.onDispose(db.close);
  return db;
});

final Provider<FingerprintCacheDao> fingerprintCacheDaoProvider =
    Provider<FingerprintCacheDao>(
  (Ref ref) => FingerprintCacheDao(ref.watch(appDatabaseProvider)),
);

final Provider<ConnectivityChecker> connectivityCheckerProvider =
    Provider<ConnectivityChecker>((Ref ref) => ConnectivityPlusChecker());

final Provider<FingerprintRepository> fingerprintRepositoryProvider =
    Provider<FingerprintRepository>((Ref ref) {
  final dioPair = ref.watch(dioProvider);
  final repo = FingerprintRepositoryImpl(
    wifiScan: ref.watch(wifiScanServiceProvider),
    cacheDao: ref.watch(fingerprintCacheDaoProvider),
    dio: dioPair.main,
    prefs: ref.watch(prefsProvider),
    connectivity: ref.watch(connectivityCheckerProvider),
  );
  ref.onDispose(repo.dispose);
  return repo;
});

/// Стрим количества pending-отпечатков.
final StreamProvider<int> pendingFingerprintsCountProvider =
    StreamProvider<int>((Ref ref) async* {
  final repo = ref.watch(fingerprintRepositoryProvider);
  // Сначала отдадим текущее значение, потом подпишемся на стрим.
  yield await repo.currentPendingCount();
  yield* repo.watchPendingCount();
});
