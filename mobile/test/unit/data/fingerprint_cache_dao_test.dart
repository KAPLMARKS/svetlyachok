/// Unit-тесты `FingerprintCacheDao` через in-memory sqflite_common_ffi.
library;

import 'package:flutter_test/flutter_test.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';
import 'package:svetlyachok_mobile/data/local/db.dart';
import 'package:svetlyachok_mobile/data/local/fingerprint_cache_dao.dart';

AppDatabase _newInMemoryDb() {
  return AppDatabase(
    path: inMemoryDatabasePath,
    factory: databaseFactoryFfi,
  );
}

FingerprintCacheRow _row({
  DateTime? capturedAt,
  Map<String, int>? rssi,
}) {
  return FingerprintCacheRow(
    capturedAt: capturedAt ?? DateTime.utc(2026, 5, 1, 10, 0),
    rssiVector: rssi ?? <String, int>{'AA:BB:CC:DD:EE:FF': -65},
    sampleCount: 1,
    deviceId: 'test-device',
  );
}

void main() {
  setUpAll(sqfliteFfiInit);

  group('FingerprintCacheDao', () {
    late AppDatabase appDb;
    late FingerprintCacheDao dao;

    setUp(() {
      appDb = _newInMemoryDb();
      dao = FingerprintCacheDao(appDb);
    });

    tearDown(() async {
      await appDb.close();
    });

    test('insert + readPending round-trip', () async {
      final id1 = await dao.insert(_row());
      final id2 = await dao.insert(
        _row(
          capturedAt: DateTime.utc(2026, 5, 1, 10, 1),
          rssi: <String, int>{'00:11:22:33:44:55': -75},
        ),
      );
      expect(id1, isPositive);
      expect(id2, greaterThan(id1));

      final pending = await dao.readPending();
      expect(pending, hasLength(2));
      expect(pending.first.id, id1);
      expect(pending.last.id, id2);
      expect(pending.first.rssiVector, <String, int>{'AA:BB:CC:DD:EE:FF': -65});
      expect(pending.last.deviceId, 'test-device');
    });

    test('countPending returns only sync_status=0', () async {
      await dao.insert(_row());
      await dao.insert(_row());
      await dao.insert(_row());
      expect(await dao.countPending(), 3);
    });

    test('markSynced sets server_id and removes from pending', () async {
      final id = await dao.insert(_row());
      await dao.markSynced(<int>[id], <int, int>{id: 999});

      expect(await dao.countPending(), 0);
      final pending = await dao.readPending();
      expect(pending, isEmpty);
    });

    test('markRejected moves to terminal status', () async {
      final id = await dao.insert(_row());
      await dao.markRejected(<int>[id], 'captured_at_too_old');

      expect(await dao.countPending(), 0);
    });

    test('incrementRetry keeps row pending and increases counter', () async {
      final id = await dao.insert(_row());
      await dao.incrementRetry(<int>[id]);
      await dao.incrementRetry(<int>[id]);

      final pending = await dao.readPending();
      expect(pending, hasLength(1));
      expect(pending.first.retryCount, 2);
      expect(pending.first.lastRetryAt, isNotNull);
    });

    test('readPending limit clips result', () async {
      for (int i = 0; i < 5; i++) {
        await dao.insert(
          _row(capturedAt: DateTime.utc(2026, 5, 1, 10, i)),
        );
      }
      final pending = await dao.readPending(limit: 3);
      expect(pending, hasLength(3));
    });

    test('deleteSyncedOlderThan removes only old synced rows', () async {
      // Старая synced-запись.
      final oldId = await dao.insert(
        _row(capturedAt: DateTime.now().toUtc().subtract(const Duration(days: 8))),
      );
      await dao.markSynced(<int>[oldId], <int, int>{oldId: 1});

      // Свежая synced-запись.
      final freshId = await dao.insert(_row());
      await dao.markSynced(<int>[freshId], <int, int>{freshId: 2});

      // Pending-запись (не должна удалиться).
      await dao.insert(_row());

      final removed = await dao.deleteSyncedOlderThan(const Duration(days: 7));
      expect(removed, 1);
      expect(await dao.countPending(), 1);
    });
  });
}
