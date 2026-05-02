/// Нормализация BSSID на клиенте — для дедупликации в одном скане.
///
/// Принимает BSSID в любой форме:
/// - `aa:bb:cc:dd:ee:ff` (lower + двоеточия)
/// - `AA-BB-CC-DD-EE-FF` (upper + дефисы)
/// - `aabbccddeeff` (без разделителей)
/// - смешанный регистр и разделители
///
/// Возвращает каноническую форму: `AA:BB:CC:DD:EE:FF`.
///
/// Кидает `FormatException`, если после удаления `:` и `-` не получается
/// ровно 12 hex-символов. Backend всё равно нормализует свою сторону —
/// клиентская нормализация только для удобства дедупа.
library;

import '../../core/logging.dart';

final RegExp _hexOnly = RegExp(r'^[0-9A-Fa-f]+$');

String normalizeBssid(String raw) {
  final cleaned = raw.replaceAll(':', '').replaceAll('-', '');
  if (cleaned.length != 12 || !_hexOnly.hasMatch(cleaned)) {
    AppLogger.instance.w('[bssid] cannot normalize: $raw');
    throw FormatException('Invalid BSSID', raw);
  }
  final upper = cleaned.toUpperCase();
  return <String>[
    upper.substring(0, 2),
    upper.substring(2, 4),
    upper.substring(4, 6),
    upper.substring(6, 8),
    upper.substring(8, 10),
    upper.substring(10, 12),
  ].join(':');
}
