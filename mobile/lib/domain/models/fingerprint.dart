/// Доменная модель Wi-Fi отпечатка для отправки в backend.
library;

import 'package:freezed_annotation/freezed_annotation.dart';

part 'fingerprint.freezed.dart';

enum SyncStatus { pending, synced, rejected }

@freezed
class Fingerprint with _$Fingerprint {
  const factory Fingerprint({
    required DateTime capturedAt,
    required Map<String, int> rssiVector,
    @Default(1) int sampleCount,
    String? deviceId,
    int? localId,
    int? serverId,
    @Default(SyncStatus.pending) SyncStatus syncStatus,
  }) = _Fingerprint;
}

/// Результат одного запуска `syncPending()`.
class SyncResult {
  const SyncResult({
    required this.acceptedCount,
    required this.rejectedCount,
    required this.terminalRejectCount,
    required this.remainingPending,
    required this.chunksProcessed,
  });

  final int acceptedCount;
  final int rejectedCount;
  final int terminalRejectCount;
  final int remainingPending;
  final int chunksProcessed;

  static const SyncResult empty = SyncResult(
    acceptedCount: 0,
    rejectedCount: 0,
    terminalRejectCount: 0,
    remainingPending: 0,
    chunksProcessed: 0,
  );
}
