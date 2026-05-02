/// Тесты sliding-window rate-limiter в `WifiScanServiceImpl`.
///
/// Логика самого `wifi_scan` plugin не тестируется — это требует
/// MethodChannel mock'ов. Здесь только rate-limiter, который полностью
/// в Dart и не зависит от платформы.
library;

import 'package:flutter_test/flutter_test.dart';
import 'package:svetlyachok_mobile/core/errors.dart';
import 'package:svetlyachok_mobile/data/wifi/wifi_scan_service.dart';

class _FakeClock implements Clock {
  _FakeClock(this._now);

  DateTime _now;

  @override
  DateTime now() => _now;

  void advance(Duration d) {
    _now = _now.add(d);
  }
}

void main() {
  group('WifiScanServiceImpl rate-limiter', () {
    test('first 4 scans within window are allowed; 5th is throttled',
        () async {
      final clock = _FakeClock(DateTime(2026));
      final svc = WifiScanServiceImpl(clock: clock);

      // Регистрируем 4 скана за минуту — это в пределах окна 2 мин и лимита 4.
      svc.registerScanForTest(clock.now());
      clock.advance(const Duration(seconds: 15));
      svc.registerScanForTest(clock.now());
      clock.advance(const Duration(seconds: 15));
      svc.registerScanForTest(clock.now());
      clock.advance(const Duration(seconds: 15));
      svc.registerScanForTest(clock.now());
      expect(svc.scansInCurrentWindow, 4);

      // 5-й — должен быть заблокирован.
      final result = await svc.scanOnce();
      expect(result.isLeft(), isTrue);
      result.fold(
        (Failure f) {
          expect(f, isA<ThrottledFailure>());
          expect(f.code, 'wifi_throttled');
        },
        (_) => fail('expected Left'),
      );
    });

    test('scans older than window are evicted, allowing new', () async {
      final clock = _FakeClock(DateTime(2026));
      final svc = WifiScanServiceImpl(clock: clock);

      // 4 скана — окно заполнено.
      for (int i = 0; i < 4; i++) {
        svc.registerScanForTest(clock.now());
        clock.advance(const Duration(seconds: 15));
      }
      expect(svc.scansInCurrentWindow, 4);

      // Промотаем время на 2 мин 1 сек — все 4 скана должны выйти из окна.
      clock.advance(const Duration(minutes: 2, seconds: 1));
      expect(svc.scansInCurrentWindow, 0);
    });

    test('partial eviction keeps recent scans', () async {
      final clock = _FakeClock(DateTime(2026));
      final svc = WifiScanServiceImpl(clock: clock);

      svc.registerScanForTest(clock.now()); // t=0
      clock.advance(const Duration(seconds: 100));
      svc.registerScanForTest(clock.now()); // t=100s
      clock.advance(const Duration(seconds: 30));
      // Теперь now=130s. Окно [now-120s, now] = [10s, 130s].
      // Первый скан был на t=0 — выпадает. Второй на t=100 — остаётся.
      expect(svc.scansInCurrentWindow, 1);
    });
  });
}
