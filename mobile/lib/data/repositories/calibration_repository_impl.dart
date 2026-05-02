/// `CalibrationRepository` реализация — wifi-скан + POST /calibration/points.
///
/// Без локального кэша: операция admin'а, требует онлайн. На 403
/// возвращаем `AuthFailure.forbidden` (UI должен был это предотвратить
/// gate'ом, но защита глубокая).
library;

import 'package:dio/dio.dart';

import '../../core/constants.dart';
import '../../core/errors.dart';
import '../../core/logging.dart';
import '../../core/result.dart';
import '../../domain/models/calibration_point.dart';
import '../../domain/models/wifi_network.dart';
import '../../domain/repositories/calibration_repository.dart';
import '../api/api_exceptions.dart';
import '../api/dto/calibration_point_dto.dart';
import '../local/prefs.dart';
import '../wifi/wifi_scan_service.dart';

class CalibrationRepositoryImpl implements CalibrationRepository {
  CalibrationRepositoryImpl({
    required WifiScanService wifiScan,
    required Dio dio,
    required Prefs prefs,
  })  : _wifi = wifiScan,
        _dio = dio,
        _prefs = prefs;

  final WifiScanService _wifi;
  final Dio _dio;
  final Prefs _prefs;

  Map<String, int> _dedupVector(Iterable<WifiNetwork> networks) {
    final result = <String, int>{};
    for (final n in networks) {
      final existing = result[n.bssid];
      if (existing == null || n.rssi > existing) {
        result[n.bssid] = n.rssi;
      }
    }
    return result;
  }

  @override
  Future<Result<CalibrationPoint>> submit(int zoneId) async {
    final scan = await _wifi.scanOnce();
    return scan.fold(
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
        final deviceId = await _prefs.getOrCreateDeviceId();
        final request = CalibrationPointRequestDto(
          zoneId: zoneId,
          capturedAt: DateTime.now().toUtc().toIso8601String(),
          rssiVector: vector,
          deviceId: deviceId,
        );
        AppLogger.instance.i(
          '[calibration.submit] zone=$zoneId, networks=${vector.length}',
        );
        try {
          final response = await _dio.post<Map<String, dynamic>>(
            '$kApiVersionPrefix/calibration/points',
            data: request.toJson(),
          );
          final body = response.data;
          if (body == null) {
            return failure(ServerFailure.internal(detail: 'empty_response'));
          }
          final dto = CalibrationPointResponseDto.fromJson(body);
          AppLogger.instance.i(
            '[calibration.submit] success: serverId=${dto.id}',
          );
          return success(
            CalibrationPoint(
              id: dto.id,
              zoneId: dto.zoneId,
              capturedAt: DateTime.parse(dto.capturedAt).toUtc(),
              rssiVector: dto.rssiVector,
              sampleCount: dto.sampleCount,
            ),
          );
        } on DioException catch (e) {
          AppLogger.instance.w(
            '[calibration.submit] failed: ${e.response?.statusCode}',
          );
          if (e.response?.statusCode == 403) {
            return failure(AuthFailure.forbidden());
          }
          return failure(mapDioErrorToFailure(e));
        }
      },
    );
  }
}
