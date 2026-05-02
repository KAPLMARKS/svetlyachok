/// Unit-тесты чистой логики WorkManager-таска (без MethodChannel).
library;

import 'package:dartz/dartz.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:svetlyachok_mobile/core/errors.dart';
import 'package:svetlyachok_mobile/core/result.dart';
import 'package:svetlyachok_mobile/domain/models/fingerprint.dart';
import 'package:svetlyachok_mobile/domain/repositories/fingerprint_repository.dart';
import 'package:svetlyachok_mobile/features/scanning/background/workmanager_callback.dart';

class _StubRepo implements FingerprintRepository {
  _StubRepo({this.captureResult, this.syncResult});
  Result<int>? captureResult;
  Result<SyncResult>? syncResult;
  @override
  Future<Result<int>> capture() async => captureResult ?? const Right(1);
  @override
  Future<Result<int>> captureCalibration(int zoneId) async =>
      throw UnimplementedError();
  @override
  Future<Result<SyncResult>> syncPending() async =>
      syncResult ?? const Right(SyncResult.empty);
  @override
  Stream<int> watchPendingCount() => const Stream.empty();
  @override
  Future<int> currentPendingCount() async => 0;
}

void main() {
  group('runScanAndCache', () {
    test('returns true on Right', () async {
      expect(await runScanAndCache(_StubRepo()), isTrue);
    });

    test('returns false on Left', () async {
      expect(
        await runScanAndCache(
          _StubRepo(captureResult: Left(NetworkFailure.noConnection())),
        ),
        isFalse,
      );
    });
  });

  group('runSyncFingerprints', () {
    test('returns true on Right', () async {
      expect(await runSyncFingerprints(_StubRepo()), isTrue);
    });

    test('returns false on Left', () async {
      expect(
        await runSyncFingerprints(
          _StubRepo(syncResult: Left(NetworkFailure.noConnection())),
        ),
        isFalse,
      );
    });
  });
}
