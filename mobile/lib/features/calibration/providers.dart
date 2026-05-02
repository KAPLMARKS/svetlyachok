/// Провайдеры calibration-фичи.
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/repositories/calibration_repository_impl.dart';
import '../../data/repositories/zone_repository_impl.dart';
import '../../domain/models/zone.dart';
import '../../domain/repositories/calibration_repository.dart';
import '../../domain/repositories/zone_repository.dart';
import '../auth/providers.dart';
import '../scanning/providers.dart';

final Provider<ZoneRepository> zoneRepositoryProvider = Provider<ZoneRepository>(
  (Ref ref) => ZoneRepositoryImpl(dio: ref.watch(dioProvider).main),
);

final Provider<CalibrationRepository> calibrationRepositoryProvider =
    Provider<CalibrationRepository>(
  (Ref ref) => CalibrationRepositoryImpl(
    wifiScan: ref.watch(wifiScanServiceProvider),
    dio: ref.watch(dioProvider).main,
    prefs: ref.watch(prefsProvider),
  ),
);

/// Список зон с backend (ленивая FutureProvider — кешируется до invalidate).
final FutureProvider<List<Zone>> zonesProvider = FutureProvider<List<Zone>>(
  (Ref ref) async {
    final repo = ref.watch(zoneRepositoryProvider);
    final result = await repo.listZones();
    return result.fold(
      (Object f) => throw StateError('zones load failed: $f'),
      (List<Zone> z) => z,
    );
  },
);
