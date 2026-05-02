/// Unit-тесты `CalibrationCaptureViewModel`.
library;

import 'package:dartz/dartz.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:svetlyachok_mobile/core/errors.dart';
import 'package:svetlyachok_mobile/core/result.dart';
import 'package:svetlyachok_mobile/domain/models/calibration_point.dart';
import 'package:svetlyachok_mobile/domain/repositories/calibration_repository.dart';
import 'package:svetlyachok_mobile/features/calibration/providers.dart';
import 'package:svetlyachok_mobile/features/calibration/view_models/calibration_view_model.dart';

class _FakeCalibrationRepo implements CalibrationRepository {
  _FakeCalibrationRepo({this.result});
  Result<CalibrationPoint>? result;
  int calls = 0;
  int? lastZoneId;

  @override
  Future<Result<CalibrationPoint>> submit(int zoneId) async {
    calls++;
    lastZoneId = zoneId;
    return result ??
        Right(
          CalibrationPoint(
            id: 7,
            zoneId: zoneId,
            capturedAt: DateTime.utc(2026),
            rssiVector: const <String, int>{'AA:BB:CC:DD:EE:FF': -65},
          ),
        );
  }
}

void main() {
  group('CalibrationCaptureViewModel.capture', () {
    test('successful capture increments successCount and stores serverId',
        () async {
      final fake = _FakeCalibrationRepo();
      final container = ProviderContainer(
        overrides: <Override>[
          calibrationRepositoryProvider.overrideWithValue(fake),
        ],
      );
      addTearDown(container.dispose);

      final notifier =
          container.read(calibrationCaptureProvider(123).notifier);
      await notifier.capture('TestZone');

      expect(fake.calls, 1);
      expect(fake.lastZoneId, 123);
      final state = container.read(calibrationCaptureProvider(123));
      expect(state.successCount, 1);
      expect(state.attemptCount, 1);
      expect(state.lastServerId, 7);
      expect(state.lastErrorMessage, isNull);
    });

    test('multiple successful captures accumulate counts', () async {
      final fake = _FakeCalibrationRepo();
      final container = ProviderContainer(
        overrides: <Override>[
          calibrationRepositoryProvider.overrideWithValue(fake),
        ],
      );
      addTearDown(container.dispose);

      final notifier =
          container.read(calibrationCaptureProvider(5).notifier);
      await notifier.capture('Z');
      await notifier.capture('Z');
      await notifier.capture('Z');

      expect(fake.calls, 3);
      final state = container.read(calibrationCaptureProvider(5));
      expect(state.attemptCount, 3);
      expect(state.successCount, 3);
    });

    test('failure keeps successCount, fills lastError*', () async {
      final fake = _FakeCalibrationRepo(
        result: Left(AuthFailure.forbidden()),
      );
      final container = ProviderContainer(
        overrides: <Override>[
          calibrationRepositoryProvider.overrideWithValue(fake),
        ],
      );
      addTearDown(container.dispose);

      final notifier =
          container.read(calibrationCaptureProvider(9).notifier);
      await notifier.capture('Z');

      final state = container.read(calibrationCaptureProvider(9));
      expect(state.successCount, 0);
      expect(state.attemptCount, 1);
      expect(state.lastErrorCode, 'auth_forbidden');
    });
  });
}
