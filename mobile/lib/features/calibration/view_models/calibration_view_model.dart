/// `CalibrationViewModel` управляет одним capture-сеансом для конкретной зоны.
///
/// State хранит: количество снятых точек в текущей сессии и последний
/// результат (success/failure). UI отображает счётчик + кнопку «Снять ещё».
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/errors.dart';
import '../../../core/logging.dart';
import '../providers.dart';

class CalibrationCaptureState {
  const CalibrationCaptureState({
    this.attemptCount = 0,
    this.successCount = 0,
    this.isCapturing = false,
    this.lastErrorCode,
    this.lastErrorMessage,
    this.lastServerId,
  });

  final int attemptCount;
  final int successCount;
  final bool isCapturing;
  final String? lastErrorCode;
  final String? lastErrorMessage;
  final int? lastServerId;

  CalibrationCaptureState copyWith({
    int? attemptCount,
    int? successCount,
    bool? isCapturing,
    String? lastErrorCode,
    String? lastErrorMessage,
    int? lastServerId,
    bool clearError = false,
  }) {
    return CalibrationCaptureState(
      attemptCount: attemptCount ?? this.attemptCount,
      successCount: successCount ?? this.successCount,
      isCapturing: isCapturing ?? this.isCapturing,
      lastErrorCode: clearError ? null : (lastErrorCode ?? this.lastErrorCode),
      lastErrorMessage:
          clearError ? null : (lastErrorMessage ?? this.lastErrorMessage),
      lastServerId: lastServerId ?? this.lastServerId,
    );
  }
}

class CalibrationCaptureViewModel
    extends AutoDisposeFamilyNotifier<CalibrationCaptureState, int> {
  @override
  CalibrationCaptureState build(int zoneId) =>
      const CalibrationCaptureState();

  Future<void> capture(String zoneName) async {
    if (state.isCapturing) return;
    final attempt = state.attemptCount + 1;
    AppLogger.instance.i(
      '[calibration.capture] zone=$zoneName, attempt=$attempt',
    );
    state = state.copyWith(
      isCapturing: true,
      attemptCount: attempt,
      clearError: true,
    );

    final repo = ref.read(calibrationRepositoryProvider);
    final result = await repo.submit(arg);
    result.fold(
      (Failure f) {
        AppLogger.instance.w('[calibration.capture] failed: ${f.code}');
        state = state.copyWith(
          isCapturing: false,
          lastErrorCode: f.code,
          lastErrorMessage: f.message,
        );
      },
      (point) {
        AppLogger.instance.i(
          '[calibration.capture] success: serverId=${point.id}',
        );
        state = state.copyWith(
          isCapturing: false,
          successCount: state.successCount + 1,
          lastServerId: point.id,
          clearError: true,
        );
      },
    );
  }
}

final AutoDisposeNotifierProviderFamily<CalibrationCaptureViewModel,
        CalibrationCaptureState, int> calibrationCaptureProvider =
    AutoDisposeNotifierProvider.family<CalibrationCaptureViewModel,
        CalibrationCaptureState, int>(
  CalibrationCaptureViewModel.new,
);
