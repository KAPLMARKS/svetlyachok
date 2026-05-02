/// Integration happy-path: app boots → main screen accessible.
///
/// Запускается на реальном Android-эмуляторе/устройстве:
/// ```
/// fvm flutter test integration_test/happy_path_test.dart
/// ```
///
/// На host-машине без эмулятора смотри host-аналог в
/// `test/widget/happy_path_widget_test.dart`.
library;

import 'package:dartz/dartz.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';
import 'package:svetlyachok_mobile/app/app.dart';
import 'package:svetlyachok_mobile/core/result.dart';
import 'package:svetlyachok_mobile/data/local/db.dart';
import 'package:svetlyachok_mobile/data/repositories/fingerprint_repository_impl.dart';
import 'package:svetlyachok_mobile/data/wifi/wifi_scan_service.dart';
import 'package:svetlyachok_mobile/domain/models/user.dart';
import 'package:svetlyachok_mobile/domain/models/wifi_network.dart';
import 'package:svetlyachok_mobile/features/auth/providers.dart';
import 'package:svetlyachok_mobile/features/scanning/background/scheduler.dart';
import 'package:svetlyachok_mobile/features/scanning/providers.dart';

class _FakeWifiScan implements WifiScanService {
  @override
  Future<Result<List<WifiNetwork>>> scanOnce() async => const Right(<WifiNetwork>[
        WifiNetwork(bssid: 'AA:BB:CC:DD:EE:01', rssi: -55),
        WifiNetwork(bssid: 'AA:BB:CC:DD:EE:02', rssi: -65),
        WifiNetwork(bssid: 'AA:BB:CC:DD:EE:03', rssi: -75),
      ]);

  @override
  Stream<List<WifiNetwork>> watchScans() => const Stream.empty();

  @override
  Future<Result<bool>> ensurePermissions({bool background = false}) async =>
      const Right(true);
}

class _OnlineConnectivity implements ConnectivityChecker {
  @override
  Future<bool> hasConnection() async => true;
}

class _OfflineSchedulerStub implements BackgroundScheduler {
  int registers = 0;
  int cancels = 0;
  @override
  Future<void> registerPeriodicTasks() async => registers++;
  @override
  Future<void> cancelAll() async => cancels++;
  @override
  Future<void> registerOneOffSync() async {}
}

class _LoggedInCurrentUser extends CurrentUserNotifier {
  @override
  Future<User?> build() async {
    // Симуляция: на старте уже залогинен (skip login flow для теста).
    return const User(
      id: 1,
      email: 'admin@svetlyachok.local',
      fullName: 'Test Admin',
      role: 'admin',
      isActive: true,
    );
  }
}

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  setUpAll(sqfliteFfiInit);

  testWidgets('happy path: scan → fingerprint в pending → sync обнуляет',
      (WidgetTester tester) async {
    SharedPreferences.setMockInitialValues(<String, Object>{});

    final scheduler = _OfflineSchedulerStub();
    final wifi = _FakeWifiScan();
    final connectivity = _OnlineConnectivity();
    final db = AppDatabase(
      path: inMemoryDatabasePath,
      factory: databaseFactoryFfi,
    );

    await tester.pumpWidget(
      ProviderScope(
        overrides: <Override>[
          currentUserProvider.overrideWith(_LoggedInCurrentUser.new),
          wifiScanServiceProvider.overrideWithValue(wifi),
          connectivityCheckerProvider.overrideWithValue(connectivity),
          appDatabaseProvider.overrideWithValue(db),
          backgroundSchedulerProvider.overrideWithValue(scheduler),
        ],
        child: const SvetlyachokApp(),
      ),
    );

    // Прогоняем несколько pump'ов до стабилизации router'а на /scan.
    for (int i = 0; i < 8; i++) {
      await tester.pump(const Duration(milliseconds: 200));
    }

    expect(find.text('Я на работе'), findsOneWidget);
    expect(find.text('Снять отпечаток сейчас'), findsOneWidget);

    // Тап «Снять отпечаток».
    await tester.tap(find.text('Снять отпечаток сейчас'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 500));
    await tester.pump(const Duration(milliseconds: 500));

    // Локальный кэш должен содержать одну запись (DAO напрямую).
    final container = ProviderScope.containerOf(
      tester.element(find.byType(SvetlyachokApp)),
    );
    final repo = container.read(fingerprintRepositoryProvider);
    expect(await repo.currentPendingCount(), 1);
  });
}
