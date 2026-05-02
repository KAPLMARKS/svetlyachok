/// Smoke widget-test: приложение монтируется и показывает splash-заглушку.
///
/// На Phase 1 — минимальный тест, доказывающий, что `SvetlyachokApp` стартует
/// в `ProviderScope`. Полные widget-тесты экранов добавляются в Phase 2-5
/// рядом с фичами.
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:svetlyachok_mobile/app/app.dart';

void main() {
  testWidgets('SvetlyachokApp boots and shows splash placeholder',
      (WidgetTester tester) async {
    await tester.pumpWidget(const ProviderScope(child: SvetlyachokApp()));
    await tester.pumpAndSettle();

    expect(find.text('Светлячок'), findsOneWidget);
    expect(find.text('Загрузка…'), findsOneWidget);
  });
}
