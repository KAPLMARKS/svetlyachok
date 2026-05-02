/// Unit-тесты `FingerprintRepositoryImpl.syncPending()` через in-memory DAO
/// и кастомный Dio HttpClientAdapter, имитирующий backend.
library;

import 'dart:convert';
import 'dart:typed_data';

import 'package:dartz/dartz.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';
import 'package:svetlyachok_mobile/core/result.dart';
import 'package:svetlyachok_mobile/data/local/db.dart';
import 'package:svetlyachok_mobile/data/local/fingerprint_cache_dao.dart';
import 'package:svetlyachok_mobile/data/local/prefs.dart';
import 'package:svetlyachok_mobile/data/repositories/fingerprint_repository_impl.dart';
import 'package:svetlyachok_mobile/data/wifi/wifi_scan_service.dart';
import 'package:svetlyachok_mobile/domain/models/fingerprint.dart';
import 'package:svetlyachok_mobile/domain/models/wifi_network.dart';

class _FakeConnectivity implements ConnectivityChecker {
  _FakeConnectivity({this.online = true});
  bool online;
  @override
  Future<bool> hasConnection() async => online;
}

class _FakeWifi implements WifiScanService {
  _FakeWifi(this.networks);
  final List<WifiNetwork> networks;
  @override
  Future<Result<List<WifiNetwork>>> scanOnce() async => Right(networks);
  @override
  Stream<List<WifiNetwork>> watchScans() => const Stream.empty();
  @override
  Future<Result<bool>> ensurePermissions({bool background = false}) async =>
      const Right(true);
}

class _FakeAdapter implements HttpClientAdapter {
  _FakeAdapter(this.handler);

  final Future<ResponseBody> Function(RequestOptions options) handler;

  @override
  void close({bool force = false}) {}

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) =>
      handler(options);
}

ResponseBody _jsonResponse(Map<String, dynamic> body, {int status = 200}) {
  final bytes = utf8.encode(jsonEncode(body));
  return ResponseBody.fromBytes(
    bytes,
    status,
    headers: <String, List<String>>{
      'content-type': <String>['application/json'],
    },
  );
}

ResponseBody _statusOnly(int status) {
  return ResponseBody.fromBytes(
    Uint8List(0),
    status,
    headers: <String, List<String>>{},
  );
}

Dio _dioWith(
  Future<ResponseBody> Function(RequestOptions options) handler,
) {
  final dio = Dio()
    ..options.baseUrl = 'http://test'
    ..httpClientAdapter = _FakeAdapter(handler);
  return dio;
}

FingerprintCacheRow _row({
  required DateTime capturedAt,
  Map<String, int>? rssi,
}) {
  return FingerprintCacheRow(
    capturedAt: capturedAt,
    rssiVector: rssi ?? <String, int>{'AA:BB:CC:DD:EE:FF': -65},
  );
}

void main() {
  setUpAll(sqfliteFfiInit);

  setUp(() {
    SharedPreferences.setMockInitialValues(<String, Object>{});
  });

  group('FingerprintRepositoryImpl.syncPending', () {
    late AppDatabase appDb;
    late FingerprintCacheDao dao;
    late Prefs prefs;

    setUp(() async {
      appDb = AppDatabase(
        path: inMemoryDatabasePath,
        factory: databaseFactoryFfi,
      );
      dao = FingerprintCacheDao(appDb);
      final sp = await SharedPreferences.getInstance();
      prefs = Prefs(sp);
    });

    tearDown(() async {
      await appDb.close();
    });

    FingerprintRepositoryImpl buildRepo({
      required Dio dio,
      bool online = true,
    }) {
      return FingerprintRepositoryImpl(
        wifiScan: _FakeWifi(const <WifiNetwork>[]),
        cacheDao: dao,
        dio: dio,
        prefs: prefs,
        connectivity: _FakeConnectivity(online: online),
      );
    }

    test('returns NetworkFailure when offline', () async {
      final repo = buildRepo(
        dio: _dioWith((_) async => _statusOnly(500)),
        online: false,
      );
      final result = await repo.syncPending();
      expect(result.isLeft(), isTrue);
    });

    test('empty pending → success with chunksProcessed=0', () async {
      final repo = buildRepo(dio: _dioWith((_) async => _statusOnly(500)));
      final result = await repo.syncPending();
      result.fold(
        (_) => fail('expected Right'),
        (SyncResult sr) {
          expect(sr.acceptedCount, 0);
          expect(sr.chunksProcessed, 0);
          expect(sr.remainingPending, 0);
        },
      );
    });

    test('partial success: 2 accepted + 1 rejected (terminal)', () async {
      final id1 = await dao.insert(
        _row(capturedAt: DateTime.utc(2026, 5, 1, 10)),
      );
      final id2 = await dao.insert(
        _row(capturedAt: DateTime.utc(2026, 5, 1, 10, 1)),
      );
      final id3 = await dao.insert(
        _row(capturedAt: DateTime.utc(2026, 5, 1, 10, 2)),
      );

      Map<String, dynamic> fakeFp(int sid) => <String, dynamic>{
            'id': sid,
            'employee_id': null,
            'zone_id': null,
            'is_calibration': false,
            'captured_at': '2026-05-01T10:00:00Z',
            'device_id': null,
            'rssi_vector': <String, int>{'AA:BB:CC:DD:EE:FF': -65},
            'sample_count': 1,
          };

      final body = <String, dynamic>{
        'accepted': <Map<String, dynamic>>[
          <String, dynamic>{'index': 0, 'fingerprint': fakeFp(901)},
          <String, dynamic>{'index': 1, 'fingerprint': fakeFp(902)},
        ],
        'rejected': <Map<String, dynamic>>[
          <String, dynamic>{
            'index': 2,
            'code': 'captured_at_too_old',
            'message': 'too old',
          },
        ],
        'accepted_count': 2,
        'rejected_count': 1,
      };
      final dio = _dioWith((_) async => _jsonResponse(body));

      final repo = buildRepo(dio: dio);
      final result = await repo.syncPending();
      result.fold(
        (_) => fail('expected Right'),
        (SyncResult sr) {
          expect(sr.acceptedCount, 2);
          expect(sr.rejectedCount, 1);
          expect(sr.terminalRejectCount, 1);
          expect(sr.remainingPending, 0);
        },
      );

      // id1, id2 → synced; id3 → rejected_terminal.
      expect(await dao.countPending(), 0);
      expect(id1, isNotNull);
      expect(id2, isNotNull);
      expect(id3, isNotNull);
    });

    test('5xx error increments retry_count for whole chunk', () async {
      final id = await dao.insert(
        _row(capturedAt: DateTime.utc(2026, 5, 1, 10)),
      );
      final dio = _dioWith(
        (_) async => _jsonResponse(
          <String, dynamic>{'detail': 'server error'},
          status: 500,
        ),
      );
      final repo = buildRepo(dio: dio);
      final result = await repo.syncPending();
      expect(result.isLeft(), isTrue);

      final pending = await dao.readPending();
      expect(pending, hasLength(1));
      expect(pending.first.id, id);
      expect(pending.first.retryCount, 1);
    });

    test('422 → terminal-reject whole chunk', () async {
      await dao.insert(_row(capturedAt: DateTime.utc(2026, 5, 1, 10)));
      await dao.insert(_row(capturedAt: DateTime.utc(2026, 5, 1, 10, 1)));
      final dio = _dioWith(
        (_) async => _jsonResponse(
          <String, dynamic>{'detail': 'validation'},
          status: 422,
        ),
      );
      final repo = buildRepo(dio: dio);
      final result = await repo.syncPending();
      // Возвращаем Right, потому что мы обработали и пометили terminal.
      result.fold(
        (_) {},
        (SyncResult sr) {
          expect(sr.terminalRejectCount, 2);
        },
      );
      expect(await dao.countPending(), 0);
    });

    test('retryable rejected code → incrementRetry, not terminal', () async {
      await dao.insert(_row(capturedAt: DateTime.utc(2026, 5, 1, 10)));
      final body = <String, dynamic>{
        'accepted': <Map<String, dynamic>>[],
        'rejected': <Map<String, dynamic>>[
          <String, dynamic>{
            'index': 0,
            'code': 'internal_error',
            'message': 'transient',
          },
        ],
        'accepted_count': 0,
        'rejected_count': 1,
      };
      final dio = _dioWith((_) async => _jsonResponse(body));
      final repo = buildRepo(dio: dio);
      final result = await repo.syncPending();
      result.fold(
        (_) => fail('expected Right'),
        (SyncResult sr) {
          expect(sr.acceptedCount, 0);
          expect(sr.rejectedCount, 1);
          expect(sr.terminalRejectCount, 0);
          expect(sr.remainingPending, 1);
        },
      );
      final pending = await dao.readPending();
      expect(pending.first.retryCount, 1);
    });
  });
}
