/// Smoke widget-test: приложение монтируется и показывает SplashScreen.
///
/// Полные widget-тесты экранов лежат рядом с фичами в `test/widget/`.
/// Здесь — только проверка, что `SvetlyachokApp` стартует в `ProviderScope`,
/// resolve'ит провайдеры и доходит до splash.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:svetlyachok_mobile/app/app.dart';
import 'package:svetlyachok_mobile/domain/models/user.dart';
import 'package:svetlyachok_mobile/features/auth/providers.dart';

class _NullCurrentUser extends CurrentUserNotifier {
  @override
  Future<User?> build() async => null;
}

void main() {
  testWidgets('SvetlyachokApp boots and resolves to a routed screen',
      (WidgetTester tester) async {
    SharedPreferences.setMockInitialValues(<String, Object>{});

    await tester.pumpWidget(
      ProviderScope(
        overrides: <Override>[
          currentUserProvider.overrideWith(_NullCurrentUser.new),
        ],
        child: const SvetlyachokApp(),
      ),
    );

    // Несколько pump'ов, чтобы SharedPreferences future прорезолвился +
    // GoRouter применил redirect. pumpAndSettle нельзя — splash имеет Timer.
    for (int i = 0; i < 5; i++) {
      await tester.pump(const Duration(milliseconds: 100));
    }

    // После redirect'а с null-юзером роутер должен оказаться на /login.
    expect(find.byType(MaterialApp), findsOneWidget);
    expect(find.text('Светлячок'), findsWidgets);
  });
}
