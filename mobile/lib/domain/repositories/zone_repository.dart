/// Контракт репозитория зон.
library;

import '../../core/result.dart';
import '../models/zone.dart';

abstract class ZoneRepository {
  /// `GET /api/v1/zones` — список зон, доступных для калибровки/UI.
  Future<Result<List<Zone>>> listZones();
}
