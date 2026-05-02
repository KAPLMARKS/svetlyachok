/// Host-mode happy-path: app boots c заложенным состоянием
/// «не залогинен» → попадаем на /login.
///
/// Полный happy-path (login → scan → sync) с реальными платформенными
/// плагинами лежит в `integration_test/happy_path_test.dart` — он
/// запускается ТОЛЬКО на эмуляторе/устройстве:
/// ```
/// fvm flutter test integration_test/happy_path_test.dart
/// ```
///
/// На host-машине Workmanager/Connectivity/wifi_scan через MethodChannel
/// не работают, поэтому здесь — smoke-проверка маршрутизации.
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:svetlyachok_mobile/app/app.dart';
import 'package:svetlyachok_mobile/domain/models/user.dart';
import 'package:svetlyachok_mobile/features/auth/providers.dart';
import 'package:svetlyachok_mobile/features/scanning/background/scheduler.dart';
import 'package:svetlyachok_mobile/features/scanning/providers.dart';

class _NullCurrentUser extends CurrentUserNotifier {
  @override
  Future<User?> build() async => null;
}

class _NoopScheduler implements BackgroundScheduler {
  @override
  Future<void> registerPeriodicTasks() async {}
  @override
  Future<void> cancelAll() async {}
  @override
  Future<void> registerOneOffSync() async {}
}

void main() {
  testWidgets('app boots с null-юзером → редирект на /login',
      (WidgetTester tester) async {
    SharedPreferences.setMockInitialValues(<String, Object>{});

    await tester.pumpWidget(
      ProviderScope(
        overrides: <Override>[
          currentUserProvider.overrideWith(_NullCurrentUser.new),
          backgroundSchedulerProvider.overrideWithValue(_NoopScheduler()),
        ],
        child: const SvetlyachokApp(),
      ),
    );

    for (int i = 0; i < 6; i++) {
      await tester.pump(const Duration(milliseconds: 150));
    }

    expect(find.text('Войти'), findsOneWidget);
    expect(find.text('Светлячок'), findsWidgets);
  });
}
