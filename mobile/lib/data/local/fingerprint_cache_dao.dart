/// DAO над таблицей `fingerprints` локального кэша.
///
/// Не зависит от freezed (намеренно простой data-class), потому что:
/// 1. Маппинг в `Map<String, Object?>` для sqflite всё равно ручной.
/// 2. Не хочется тащить дополнительный кодген ради CRUD-структуры.
library;

import 'dart:convert';

import 'package:sqflite/sqflite.dart';

import '../../core/logging.dart';
import 'db.dart';

/// `0` = pending (не отправлено), `1` = synced (accepted backend'ом),
/// `2` = rejected_terminal (повторы исчерпаны или код 4xx без шансов).
class SyncStatusCode {
  const SyncStatusCode._();
  static const int pending = 0;
  static const int synced = 1;
  static const int rejectedTerminal = 2;
}

class FingerprintCacheRow {
  FingerprintCacheRow({
    this.id,
    required this.capturedAt,
    required this.rssiVector,
    this.sampleCount = 1,
    this.deviceId,
    this.syncStatus = SyncStatusCode.pending,
    this.serverId,
    this.lastErrorCode,
    this.retryCount = 0,
    this.lastRetryAt,
  });

  final int? id;
  final DateTime capturedAt;
  final Map<String, int> rssiVector;
  final int sampleCount;
  final String? deviceId;
  final int syncStatus;
  final int? serverId;
  final String? lastErrorCode;
  final int retryCount;
  final DateTime? lastRetryAt;

  Map<String, Object?> toMap() {
    return <String, Object?>{
      if (id != null) 'id': id,
      'captured_at': capturedAt.toUtc().toIso8601String(),
      'rssi_vector_json': jsonEncode(rssiVector),
      'sample_count': sampleCount,
      'device_id': deviceId,
      'sync_status': syncStatus,
      'server_id': serverId,
      'last_error_code': lastErrorCode,
      'retry_count': retryCount,
      'last_retry_at': lastRetryAt?.toUtc().toIso8601String(),
    };
  }

  static FingerprintCacheRow fromMap(Map<String, Object?> m) {
    final rawVector = m['rssi_vector_json'] as String? ?? '{}';
    final decoded = jsonDecode(rawVector) as Map<String, dynamic>;
    final vector = <String, int>{
      for (final entry in decoded.entries)
        entry.key: (entry.value as num).toInt(),
    };
    return FingerprintCacheRow(
      id: m['id'] as int?,
      capturedAt: DateTime.parse(m['captured_at']! as String).toUtc(),
      rssiVector: vector,
      sampleCount: (m['sample_count'] as int?) ?? 1,
      deviceId: m['device_id'] as String?,
      syncStatus: (m['sync_status'] as int?) ?? SyncStatusCode.pending,
      serverId: m['server_id'] as int?,
      lastErrorCode: m['last_error_code'] as String?,
      retryCount: (m['retry_count'] as int?) ?? 0,
      lastRetryAt: m['last_retry_at'] == null
          ? null
          : DateTime.parse(m['last_retry_at']! as String).toUtc(),
    );
  }
}

class FingerprintCacheDao {
  FingerprintCacheDao(this._appDb);

  final AppDatabase _appDb;

  Future<int> insert(FingerprintCacheRow row) async {
    final db = await _appDb.database;
    final inserted = await db.insert(
      kFingerprintsTable,
      row.toMap()..remove('id'),
    );
    AppLogger.instance.d(
      '[cache.insert] id=$inserted, captured_at=${row.capturedAt}',
    );
    return inserted;
  }

  Future<List<FingerprintCacheRow>> readPending({int limit = 100}) async {
    final db = await _appDb.database;
    final rows = await db.query(
      kFingerprintsTable,
      where: 'sync_status = ?',
      whereArgs: <Object>[SyncStatusCode.pending],
      orderBy: 'captured_at ASC',
      limit: limit,
    );
    return rows.map(FingerprintCacheRow.fromMap).toList(growable: false);
  }

  /// Помечает локальные id как успешно отправленные (`sync_status=1`)
  /// и проставляет `server_id` из словаря `localId → serverId`.
  Future<void> markSynced(
    List<int> localIds,
    Map<int, int> serverIds,
  ) async {
    if (localIds.isEmpty) return;
    final db = await _appDb.database;
    await db.transaction((Transaction txn) async {
      for (final localId in localIds) {
        await txn.update(
          kFingerprintsTable,
          <String, Object?>{
            'sync_status': SyncStatusCode.synced,
            'server_id': serverIds[localId],
            'last_error_code': null,
          },
          where: 'id = ?',
          whereArgs: <Object>[localId],
        );
      }
    });
    AppLogger.instance.i('[cache.markSynced] count=${localIds.length}');
  }

  /// Terminal-reject: записи больше не пытаемся отправлять.
  Future<void> markRejected(List<int> localIds, String code) async {
    if (localIds.isEmpty) return;
    final db = await _appDb.database;
    await db.transaction((Transaction txn) async {
      for (final localId in localIds) {
        await txn.update(
          kFingerprintsTable,
          <String, Object?>{
            'sync_status': SyncStatusCode.rejectedTerminal,
            'last_error_code': code,
            'last_retry_at': DateTime.now().toUtc().toIso8601String(),
          },
          where: 'id = ?',
          whereArgs: <Object>[localId],
        );
      }
    });
    AppLogger.instance.i(
      '[cache.markRejected] count=${localIds.length}, code=$code',
    );
  }

  /// Инкремент retry_count + last_retry_at для retryable failures.
  /// Записи остаются `pending` — следующий sync попробует ещё раз.
  Future<void> incrementRetry(List<int> localIds) async {
    if (localIds.isEmpty) return;
    final db = await _appDb.database;
    final now = DateTime.now().toUtc().toIso8601String();
    await db.transaction((Transaction txn) async {
      for (final localId in localIds) {
        await txn.rawUpdate(
          'UPDATE $kFingerprintsTable '
          'SET retry_count = retry_count + 1, last_retry_at = ? '
          'WHERE id = ?',
          <Object>[now, localId],
        );
      }
    });
    AppLogger.instance.d(
      '[cache.incrementRetry] count=${localIds.length}',
    );
  }

  Future<int> countPending() async {
    final db = await _appDb.database;
    final res = await db.rawQuery(
      'SELECT COUNT(*) AS c FROM $kFingerprintsTable WHERE sync_status = ?',
      <Object>[SyncStatusCode.pending],
    );
    return Sqflite.firstIntValue(res) ?? 0;
  }

  /// Housekeeping: удаляет synced-записи старше TTL для экономии места.
  /// Rejected-terminal считаем отдельно, см. `deleteRejectedOlderThan`.
  Future<int> deleteSyncedOlderThan(Duration ttl) async {
    final db = await _appDb.database;
    final cutoff = DateTime.now().toUtc().subtract(ttl).toIso8601String();
    return db.delete(
      kFingerprintsTable,
      where: 'sync_status = ? AND captured_at < ?',
      whereArgs: <Object>[SyncStatusCode.synced, cutoff],
    );
  }

  Future<int> deleteRejectedOlderThan(Duration ttl) async {
    final db = await _appDb.database;
    final cutoff = DateTime.now().toUtc().subtract(ttl).toIso8601String();
    return db.delete(
      kFingerprintsTable,
      where: 'sync_status = ? AND captured_at < ?',
      whereArgs: <Object>[SyncStatusCode.rejectedTerminal, cutoff],
    );
  }
}
