/// `FingerprintRepository` реализация — capture + sync через bulk-endpoint.
///
/// `capture()` снимает Wi-Fi скан, нормализует и дедуплицирует BSSID
/// (повторяющийся ключ → max RSSI), пишет в локальный кэш.
///
/// `syncPending()` реализует алгоритм из плана «Sync-стратегия»:
/// - connectivity-проверка → early return при offline
/// - чанками по `kBatchMaxItems` (100) до hard-лимита `kMaxChunksPerSync` (5)
/// - parsing accepted[].index / rejected[].index → markSynced / markRejected /
///   incrementRetry, при retry_count >= kMaxRetryCount → terminal reject
///
/// Errors-коды для terminal reject (из backend AppError):
/// - captured_at_in_future, captured_at_too_old
/// - invalid_rssi_vector, rssi_value_out_of_range
/// - rssi_vector_size_*
library;

import 'dart:async';

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:dio/dio.dart';

import '../../core/constants.dart';
import '../../core/errors.dart';
import '../../core/logging.dart';
import '../../core/result.dart';
import '../../domain/models/fingerprint.dart';
import '../../domain/models/wifi_network.dart';
import '../../domain/repositories/fingerprint_repository.dart';
import '../api/api_exceptions.dart';
import '../api/dto/batch_request_dto.dart';
import '../api/dto/batch_response_dto.dart';
import '../api/dto/fingerprint_dto.dart';
import '../local/fingerprint_cache_dao.dart';
import '../local/prefs.dart';
import '../wifi/wifi_scan_service.dart';

const Set<String> _terminalRejectCodes = <String>{
  'captured_at_in_future',
  'captured_at_too_old',
  'invalid_rssi_vector',
  'rssi_value_out_of_range',
  'rssi_vector_size_too_large',
  'rssi_vector_size_too_small',
  'invalid_bssid',
  'rssi_vector_empty',
};

abstract class ConnectivityChecker {
  Future<bool> hasConnection();
}

class ConnectivityPlusChecker implements ConnectivityChecker {
  ConnectivityPlusChecker([Connectivity? c]) : _c = c ?? Connectivity();

  final Connectivity _c;

  @override
  Future<bool> hasConnection() async {
    final results = await _c.checkConnectivity();
    return results.any((ConnectivityResult r) => r != ConnectivityResult.none);
  }
}

class FingerprintRepositoryImpl implements FingerprintRepository {
  FingerprintRepositoryImpl({
    required WifiScanService wifiScan,
    required FingerprintCacheDao cacheDao,
    required Dio dio,
    required Prefs prefs,
    required ConnectivityChecker connectivity,
  })  : _wifi = wifiScan,
        _dao = cacheDao,
        _dio = dio,
        _prefs = prefs,
        _connectivity = connectivity;

  final WifiScanService _wifi;
  final FingerprintCacheDao _dao;
  final Dio _dio;
  final Prefs _prefs;
  final ConnectivityChecker _connectivity;

  final StreamController<int> _pendingCount =
      StreamController<int>.broadcast();

  Future<void> _emitPending() async {
    if (_pendingCount.isClosed) return;
    _pendingCount.add(await _dao.countPending());
  }

  @override
  Stream<int> watchPendingCount() => _pendingCount.stream;

  @override
  Future<int> currentPendingCount() => _dao.countPending();

  Map<String, int> _dedupVector(Iterable<WifiNetwork> networks) {
    final result = <String, int>{};
    for (final n in networks) {
      final existing = result[n.bssid];
      // Берём максимум RSSI (ближе к 0 = сильнее сигнал).
      if (existing == null || n.rssi > existing) {
        result[n.bssid] = n.rssi;
      }
    }
    return result;
  }

  @override
  Future<Result<int>> capture() async {
    final scanResult = await _wifi.scanOnce();
    return scanResult.fold(
      failure,
      (List<WifiNetwork> networks) async {
        if (networks.isEmpty) {
          return failure(
            const ServerFailure(
              code: 'wifi_no_results',
              message: 'Сканер не нашёл точек доступа',
            ),
          );
        }
        final vector = _dedupVector(networks);
        if (vector.length > kFingerprintMaxNetworks) {
          // Срезаем по сильнейшим RSSI до лимита backend'а.
          final sorted = vector.entries.toList()
            ..sort(
              (MapEntry<String, int> a, MapEntry<String, int> b) =>
                  b.value.compareTo(a.value),
            );
          final trimmed = <String, int>{
            for (final e in sorted.take(kFingerprintMaxNetworks)) e.key: e.value,
          };
          AppLogger.instance.w(
            '[fp.capture] trimmed networks ${vector.length} → '
            '${trimmed.length}',
          );
          return _persist(trimmed);
        }
        return _persist(vector);
      },
    );
  }

  Future<Result<int>> _persist(Map<String, int> vector) async {
    try {
      final deviceId = await _prefs.getOrCreateDeviceId();
      final row = FingerprintCacheRow(
        capturedAt: DateTime.now().toUtc(),
        rssiVector: vector,
        sampleCount: 1,
        deviceId: deviceId,
      );
      final id = await _dao.insert(row);
      AppLogger.instance.i(
        '[fp.capture] localId=$id, networks=${vector.length}',
      );
      await _emitPending();
      return success(id);
    } catch (e) {
      AppLogger.instance.e('[fp.capture] persist error: $e');
      return failure(CacheFailure.io(detail: '$e'));
    }
  }

  @override
  Future<Result<int>> captureCalibration(int zoneId) async {
    if (!await _connectivity.hasConnection()) {
      return failure(NetworkFailure.noConnection());
    }
    final scanResult = await _wifi.scanOnce();
    return scanResult.fold(
      failure,
      (List<WifiNetwork> networks) async {
        if (networks.isEmpty) {
          return failure(
            const ServerFailure(
              code: 'wifi_no_results',
              message: 'Сканер не нашёл точек доступа',
            ),
          );
        }
        final vector = _dedupVector(networks);
        try {
          final response = await _dio.post<Map<String, dynamic>>(
            '$kApiVersionPrefix/calibration/points',
            data: <String, dynamic>{
              'zone_id': zoneId,
              'captured_at': DateTime.now().toUtc().toIso8601String(),
              'rssi_vector': vector,
              'sample_count': 1,
            },
          );
          final body = response.data;
          if (body == null) {
            return failure(ServerFailure.internal(detail: 'empty_response'));
          }
          final id = (body['id'] as num).toInt();
          AppLogger.instance.i(
            '[fp.calibration] zone=$zoneId, id=$id',
          );
          return success(id);
        } on DioException catch (e) {
          AppLogger.instance.w(
            '[fp.calibration] failed: ${e.response?.statusCode}',
          );
          return failure(mapDioErrorToFailure(e));
        }
      },
    );
  }

  @override
  Future<Result<SyncResult>> syncPending() async {
    if (!await _connectivity.hasConnection()) {
      AppLogger.instance.w('[fp.sync] no connectivity');
      return failure(NetworkFailure.noConnection());
    }

    int totalAccepted = 0;
    int totalRejected = 0;
    int totalTerminal = 0;
    int chunksProcessed = 0;

    AppLogger.instance.i(
      '[fp.sync] start: pending=${await _dao.countPending()}',
    );

    for (int chunk = 0; chunk < kMaxChunksPerSync; chunk++) {
      final pending = await _dao.readPending(limit: kBatchMaxItems);
      if (pending.isEmpty) {
        AppLogger.instance.d('[fp.sync] nothing to sync');
        break;
      }
      AppLogger.instance.d('[fp.sync] chunk: items=${pending.length}');

      final List<int> localIds = pending.map((r) => r.id!).toList();
      final List<FingerprintItemDto> items = pending
          .map(
            (FingerprintCacheRow r) => FingerprintItemDto(
              capturedAt: r.capturedAt.toIso8601String(),
              rssiVector: r.rssiVector,
              sampleCount: r.sampleCount,
              deviceId: r.deviceId,
            ),
          )
          .toList(growable: false);

      try {
        final response = await _dio.post<Map<String, dynamic>>(
          '$kApiVersionPrefix/fingerprints/batch',
          data: BatchRequestDto(items: items).toJson(),
          options: Options(sendTimeout: const Duration(seconds: 30)),
        );
        final body = response.data;
        if (body == null) {
          await _dao.incrementRetry(localIds);
          await _bumpRetriesToTerminal(pending);
          break;
        }
        final dto = BatchResponseDto.fromJson(body);

        final acceptedLocalIds = <int>[];
        final acceptedServerIds = <int, int>{};
        for (final a in dto.accepted) {
          if (a.index < 0 || a.index >= localIds.length) continue;
          final localId = localIds[a.index];
          acceptedLocalIds.add(localId);
          acceptedServerIds[localId] = a.fingerprint.id;
        }
        await _dao.markSynced(acceptedLocalIds, acceptedServerIds);

        // rejected: terminal vs retryable.
        final terminalLocalIds = <int>[];
        final retryableLocalIds = <int>[];
        String? terminalCode;
        for (final r in dto.rejected) {
          if (r.index < 0 || r.index >= localIds.length) continue;
          final localId = localIds[r.index];
          if (_terminalRejectCodes.contains(r.code)) {
            terminalLocalIds.add(localId);
            terminalCode ??= r.code;
          } else {
            retryableLocalIds.add(localId);
          }
        }
        if (terminalLocalIds.isNotEmpty) {
          await _dao.markRejected(
            terminalLocalIds,
            terminalCode ?? 'unknown',
          );
        }
        if (retryableLocalIds.isNotEmpty) {
          await _dao.incrementRetry(retryableLocalIds);
          // Записи, превысившие kMaxRetryCount, → terminal.
          final overLimit = pending
              .where(
                (FingerprintCacheRow r) =>
                    retryableLocalIds.contains(r.id) &&
                    r.retryCount + 1 >= kMaxRetryCount,
              )
              .map((r) => r.id!)
              .toList();
          if (overLimit.isNotEmpty) {
            await _dao.markRejected(overLimit, 'max_retries_exceeded');
            totalTerminal += overLimit.length;
          }
        }

        totalAccepted += dto.acceptedCount;
        totalRejected += dto.rejectedCount;
        totalTerminal += terminalLocalIds.length;
        chunksProcessed++;
        AppLogger.instance.i(
          '[fp.sync] chunk done: accepted=${dto.acceptedCount}, '
          'rejected=${dto.rejectedCount}',
        );

        // Если все 100 пришли rejected — следующий чанк не нужен,
        // у нас может быть ничего нового или просто закончились pending.
        if (dto.acceptedCount == 0 && terminalLocalIds.isEmpty) {
          // Все retryable → дальше будем те же бить, не имеет смысла в этом запуске.
          break;
        }

        if (chunk < kMaxChunksPerSync - 1) {
          await Future<void>.delayed(const Duration(seconds: 2));
        }
      } on DioException catch (e) {
        final status = e.response?.statusCode;
        AppLogger.instance.w('[fp.sync] http error: $status');
        if (status == 401) {
          // Interceptor пытался refresh и не смог — выходим.
          return failure(AuthFailure.expired());
        }
        if (status == 422) {
          // Валидаторы Pydantic — баг клиента, terminal-режектим chunk целиком.
          AppLogger.instance.e(
            '[fp.sync] 422 validation failure, terminal-rejecting chunk',
          );
          await _dao.markRejected(localIds, 'client_validation_error');
          totalTerminal += localIds.length;
          break;
        }
        // 5xx / timeout / network → retry-count++. Если уже на пределе — terminal.
        await _dao.incrementRetry(localIds);
        await _bumpRetriesToTerminal(pending);
        return failure(mapDioErrorToFailure(e));
      }
    }

    final remaining = await _dao.countPending();
    await _emitPending();
    AppLogger.instance.i(
      '[fp.sync] complete: total_accepted=$totalAccepted, '
      'total_rejected=$totalRejected, terminal=$totalTerminal, '
      'remaining_pending=$remaining',
    );
    return success(
      SyncResult(
        acceptedCount: totalAccepted,
        rejectedCount: totalRejected,
        terminalRejectCount: totalTerminal,
        remainingPending: remaining,
        chunksProcessed: chunksProcessed,
      ),
    );
  }

  /// После incrementRetry проверяет, не превысили ли записи лимит retry,
  /// и переводит в terminal. Возвращает количество переведённых.
  Future<int> _bumpRetriesToTerminal(List<FingerprintCacheRow> pending) async {
    final overLimit = pending
        .where((FingerprintCacheRow r) => r.retryCount + 1 >= kMaxRetryCount)
        .map((r) => r.id!)
        .toList();
    if (overLimit.isEmpty) return 0;
    await _dao.markRejected(overLimit, 'max_retries_exceeded');
    return overLimit.length;
  }

  Future<void> dispose() async {
    await _pendingCount.close();
  }
}
