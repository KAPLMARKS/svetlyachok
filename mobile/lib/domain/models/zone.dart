/// Доменная модель зоны помещения для калибровки.
///
/// `type` приходит с backend строкой и может быть одним из:
/// `workplace`, `corridor`, `meeting_room`, `outside_office` (см.
/// `backend/app/domain/zones/value_objects.py::ZoneType`).
library;

import 'package:freezed_annotation/freezed_annotation.dart';

part 'zone.freezed.dart';

@freezed
class Zone with _$Zone {
  const factory Zone({
    required int id,
    required String name,
    required String type,
    String? description,
    String? displayColor,
  }) = _Zone;
}
