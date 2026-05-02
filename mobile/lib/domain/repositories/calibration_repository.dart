/// Контракт репозитория калибровочных точек.
///
/// `submit()` снимает Wi-Fi скан, нормализует и сразу отправляет на
/// `POST /api/v1/calibration/points` (admin-only). Без локального кэша —
/// требует онлайн-подключения. При 403 → `AuthFailure.forbidden`.
library;

import '../../core/result.dart';
import '../models/calibration_point.dart';

abstract class CalibrationRepository {
  Future<Result<CalibrationPoint>> submit(int zoneId);
}
