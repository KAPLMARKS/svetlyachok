/// Wi-Fi сканирование с sliding-window rate-limiter и permission flow.
///
/// Android 9+ throttling: ОС режектит >4 запусков `WifiManager.startScan()`
/// за 2 минуты. Чтобы не получать `WiFiScanFailedException`, считаем сами:
/// храним очередь timestamps последних сканов, перед новым отбрасываем
/// просроченные (старше окна) и проверяем размер очереди против лимита.
///
/// Permission flow на Android:
/// - `Permission.locationWhenInUse` обязателен для `wifi_scan`
/// - `Permission.locationAlways` нужен для фонового скана (Phase 6)
///
/// `WifiScanService` — абстракция (для DI и тестов). `WifiScanServiceImpl` —
/// реализация на основе `wifi_scan` + `permission_handler`.
library;

import 'dart:async';
import 'dart:collection';

import 'package:flutter/foundation.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:wifi_scan/wifi_scan.dart';

import '../../core/constants.dart';
import '../../core/errors.dart';
import '../../core/logging.dart';
import '../../core/result.dart';
import '../../domain/models/wifi_network.dart';
import 'bssid_normalizer.dart';

abstract class WifiScanService {
  /// Один скан, синхронно ждёт результаты до 5 сек.
  ///
  /// Возвращает `Right([])` если скан прошёл, но не нашёл сетей.
  /// Возвращает `Left(ThrottledFailure)` если попали в Android-throttle.
  /// Возвращает `Left(PermissionFailure)` если нет permission'а.
  Future<Result<List<WifiNetwork>>> scanOnce();

  /// Стрим последних результатов сканов (system-инициированных тоже).
  Stream<List<WifiNetwork>> watchScans();

  /// Проверить + запросить permission'ы. `Right(true)` — всё ок,
  /// `Right(false)` — пользователь отказал но не permanently.
  /// `Left(PermissionFailure)` — permanently denied или not supported.
  Future<Result<bool>> ensurePermissions({bool background = false});
}

class WifiScanServiceImpl implements WifiScanService {
  WifiScanServiceImpl({
    WiFiScan? plugin,
    Clock? clock,
  })  : _plugin = plugin ?? WiFiScan.instance,
        _clock = clock ?? Clock.system;

  final WiFiScan _plugin;
  final Clock _clock;

  /// Sliding-window очередь timestamps последних сканов.
  final Queue<DateTime> _recentScans = Queue<DateTime>();

  /// Test-only: добавить timestamp вручную для проверки rate-limiter'а
  /// без реальных сканов.
  @visibleForTesting
  void registerScanForTest(DateTime ts) {
    _recentScans.addLast(ts);
  }

  /// Test-only: текущий размер окна (после автоочистки просроченных).
  @visibleForTesting
  int get scansInCurrentWindow {
    _isThrottled(); // у функции есть side effect: чистит просроченные
    return _recentScans.length;
  }

  bool _isThrottled() {
    final now = _clock.now();
    final cutoff = now.subtract(kScanThrottleWindow);
    while (_recentScans.isNotEmpty && _recentScans.first.isBefore(cutoff)) {
      _recentScans.removeFirst();
    }
    return _recentScans.length >= kScanThrottleMaxInWindow;
  }

  void _registerScan() {
    _recentScans.addLast(_clock.now());
  }

  @override
  Future<Result<List<WifiNetwork>>> scanOnce() async {
    AppLogger.instance.d('[wifi.scan] start');
    if (_isThrottled()) {
      final retryAfter =
          kScanThrottleWindow - _clock.now().difference(_recentScans.first);
      AppLogger.instance.w(
        '[wifi.scan] throttled: scansInWindow=${_recentScans.length}',
      );
      return failure(ThrottledFailure.scan(retryAfter: retryAfter));
    }

    try {
      final canStart = await _plugin.canStartScan(askPermissions: false);
      if (canStart != CanStartScan.yes) {
        return failure(_mapCanStartToFailure(canStart));
      }

      final started = await _plugin.startScan();
      if (!started) {
        AppLogger.instance.w('[wifi.scan] startScan returned false');
        return failure(
          const ServerFailure(
            code: 'wifi_start_failed',
            message: 'Не удалось запустить Wi-Fi сканирование',
          ),
        );
      }
      _registerScan();

      final canGet = await _plugin.canGetScannedResults(askPermissions: false);
      if (canGet != CanGetScannedResults.yes) {
        return failure(_mapCanGetToFailure(canGet));
      }

      final raw = await _plugin.getScannedResults();
      final normalized = _normalize(raw);
      AppLogger.instance.i('[wifi.scan] done: networks=${normalized.length}');
      return success(normalized);
    } catch (e, st) {
      AppLogger.instance.e('[wifi.scan] error: $e', error: e, stackTrace: st);
      return failure(UnknownFailure.from(e));
    }
  }

  @override
  Stream<List<WifiNetwork>> watchScans() {
    return _plugin.onScannedResultsAvailable.map(_normalize);
  }

  @override
  Future<Result<bool>> ensurePermissions({bool background = false}) async {
    AppLogger.instance.d('[wifi.permissions] check background=$background');
    final foreground = await Permission.locationWhenInUse.request();
    if (foreground.isPermanentlyDenied) {
      return failure(PermissionFailure.locationDenied());
    }
    if (!foreground.isGranted) {
      return success(false);
    }
    if (background) {
      final bg = await Permission.locationAlways.request();
      if (bg.isPermanentlyDenied) {
        return failure(PermissionFailure.locationDenied());
      }
      return success(bg.isGranted);
    }
    return success(true);
  }

  List<WifiNetwork> _normalize(List<WiFiAccessPoint> raw) {
    final result = <WifiNetwork>[];
    for (final ap in raw) {
      try {
        final bssid = normalizeBssid(ap.bssid);
        var rssi = ap.level;
        if (rssi > 0) rssi = 0;
        if (rssi < -100) rssi = -100;
        result.add(
          WifiNetwork(
            bssid: bssid,
            rssi: rssi,
            ssid: ap.ssid.isEmpty ? null : ap.ssid,
            frequency: ap.frequency,
            capabilities: ap.capabilities.isEmpty ? null : ap.capabilities,
          ),
        );
      } on FormatException {
        // BSSID не парсится — пропускаем. log.w уже в normalizeBssid.
      }
    }
    return result;
  }

  Failure _mapCanStartToFailure(CanStartScan reason) {
    switch (reason) {
      case CanStartScan.notSupported:
        return PermissionFailure.notSupported();
      case CanStartScan.noLocationPermissionRequired:
      case CanStartScan.noLocationPermissionDenied:
      case CanStartScan.noLocationPermissionUpgradeAccuracy:
        return PermissionFailure.locationDenied();
      case CanStartScan.noLocationServiceDisabled:
        return PermissionFailure.locationServiceOff();
      case CanStartScan.failed:
      case CanStartScan.yes:
        return const ServerFailure(
          code: 'wifi_start_failed',
          message: 'Не удалось запустить Wi-Fi сканирование',
        );
    }
  }

  Failure _mapCanGetToFailure(CanGetScannedResults reason) {
    switch (reason) {
      case CanGetScannedResults.notSupported:
        return PermissionFailure.notSupported();
      case CanGetScannedResults.noLocationPermissionRequired:
      case CanGetScannedResults.noLocationPermissionDenied:
      case CanGetScannedResults.noLocationPermissionUpgradeAccuracy:
        return PermissionFailure.locationDenied();
      case CanGetScannedResults.noLocationServiceDisabled:
        return PermissionFailure.locationServiceOff();
      case CanGetScannedResults.yes:
        return const ServerFailure(
          code: 'wifi_get_failed',
          message: 'Не удалось получить результаты Wi-Fi сканирования',
        );
    }
  }
}

/// Источник «текущего времени» — для тестов rate-limiter'а можно подменить.
abstract class Clock {
  DateTime now();

  static const Clock system = _SystemClock();
}

class _SystemClock implements Clock {
  const _SystemClock();

  @override
  DateTime now() => DateTime.now();
}
