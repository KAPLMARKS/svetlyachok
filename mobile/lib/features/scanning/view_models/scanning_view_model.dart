/// `ScanningViewModel` — управляет ручным сканированием на главном экране.
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/errors.dart';
import '../../../core/logging.dart';
import '../../../domain/repositories/fingerprint_repository.dart';
import '../providers.dart';

class ScanState {
  const ScanState({
    this.isScanning = false,
    this.lastLocalId,
    this.lastErrorCode,
    this.lastErrorMessage,
  });

  final bool isScanning;
  final int? lastLocalId;
  final String? lastErrorCode;
  final String? lastErrorMessage;

  ScanState copyWith({
    bool? isScanning,
    int? lastLocalId,
    String? lastErrorCode,
    String? lastErrorMessage,
    bool clearError = false,
  }) {
    return ScanState(
      isScanning: isScanning ?? this.isScanning,
      lastLocalId: lastLocalId ?? this.lastLocalId,
      lastErrorCode: clearError ? null : (lastErrorCode ?? this.lastErrorCode),
      lastErrorMessage:
          clearError ? null : (lastErrorMessage ?? this.lastErrorMessage),
    );
  }
}

class ScanningViewModel extends AutoDisposeNotifier<ScanState> {
  @override
  ScanState build() => const ScanState();

  Future<void> manualScan() async {
    if (state.isScanning) return;
    AppLogger.instance.i('[scan_vm.manualScan] start');
    state = state.copyWith(isScanning: true, clearError: true);

    final FingerprintRepository repo = ref.read(fingerprintRepositoryProvider);
    final result = await repo.capture();
    result.fold(
      (Failure f) {
        if (f is ThrottledFailure) {
          AppLogger.instance.w('[scan_vm.manualScan] throttled');
        }
        state = state.copyWith(
          isScanning: false,
          lastErrorCode: f.code,
          lastErrorMessage: f.message,
        );
      },
      (int localId) {
        AppLogger.instance.i('[scan_vm.manualScan] done: localId=$localId');
        state = state.copyWith(
          isScanning: false,
          lastLocalId: localId,
          clearError: true,
        );
      },
    );
  }
}

final AutoDisposeNotifierProvider<ScanningViewModel, ScanState>
    scanningViewModelProvider =
    AutoDisposeNotifierProvider<ScanningViewModel, ScanState>(
  ScanningViewModel.new,
);
