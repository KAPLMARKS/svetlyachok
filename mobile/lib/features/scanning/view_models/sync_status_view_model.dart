/// `SyncStatusViewModel` — состояние подключения + count pending +
/// триггер sync при переходе offline → online.
///
/// MVP-вариант: при появлении сети напрямую вызываем
/// `fingerprintRepository.syncPending()` (foreground-only). One-off
/// WorkRequest добавляется в Phase 6 вместе с WorkManager.
library;

import 'dart:async';

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/logging.dart';
import '../providers.dart';

class SyncStatusState {
  const SyncStatusState({
    this.pendingCount = 0,
    this.isOnline = true,
    this.isSyncing = false,
    this.lastSyncAt,
    this.lastSyncAccepted = 0,
    this.lastSyncRejected = 0,
  });

  final int pendingCount;
  final bool isOnline;
  final bool isSyncing;
  final DateTime? lastSyncAt;
  final int lastSyncAccepted;
  final int lastSyncRejected;

  SyncStatusState copyWith({
    int? pendingCount,
    bool? isOnline,
    bool? isSyncing,
    DateTime? lastSyncAt,
    int? lastSyncAccepted,
    int? lastSyncRejected,
  }) {
    return SyncStatusState(
      pendingCount: pendingCount ?? this.pendingCount,
      isOnline: isOnline ?? this.isOnline,
      isSyncing: isSyncing ?? this.isSyncing,
      lastSyncAt: lastSyncAt ?? this.lastSyncAt,
      lastSyncAccepted: lastSyncAccepted ?? this.lastSyncAccepted,
      lastSyncRejected: lastSyncRejected ?? this.lastSyncRejected,
    );
  }
}

class SyncStatusViewModel extends Notifier<SyncStatusState> {
  StreamSubscription<List<ConnectivityResult>>? _connSub;
  StreamSubscription<int>? _pendingSub;
  bool _wasOnline = true;

  @override
  SyncStatusState build() {
    final repo = ref.watch(fingerprintRepositoryProvider);

    _pendingSub?.cancel();
    _pendingSub = repo.watchPendingCount().listen((int count) {
      state = state.copyWith(pendingCount: count);
    });
    repo.currentPendingCount().then((int count) {
      state = state.copyWith(pendingCount: count);
    });

    _connSub?.cancel();
    final conn = Connectivity();
    _connSub = conn.onConnectivityChanged.listen(_onConnectivity);
    conn.checkConnectivity().then(_onConnectivity);

    ref.onDispose(() {
      _pendingSub?.cancel();
      _connSub?.cancel();
    });

    return const SyncStatusState();
  }

  void _onConnectivity(List<ConnectivityResult> results) {
    final online = results.any((r) => r != ConnectivityResult.none);
    state = state.copyWith(isOnline: online);
    if (!_wasOnline && online && state.pendingCount > 0) {
      AppLogger.instance.i(
        '[sync_vm] connectivity online, pending=${state.pendingCount}, '
        'triggering sync',
      );
      unawaited(syncNow());
    }
    _wasOnline = online;
  }

  Future<void> syncNow() async {
    if (state.isSyncing) return;
    state = state.copyWith(isSyncing: true);
    final repo = ref.read(fingerprintRepositoryProvider);
    final result = await repo.syncPending();
    result.fold(
      (_) {
        state = state.copyWith(isSyncing: false);
      },
      (sr) {
        state = state.copyWith(
          isSyncing: false,
          lastSyncAt: DateTime.now(),
          lastSyncAccepted: sr.acceptedCount,
          lastSyncRejected: sr.rejectedCount,
        );
      },
    );
  }
}

final NotifierProvider<SyncStatusViewModel, SyncStatusState>
    syncStatusViewModelProvider =
    NotifierProvider<SyncStatusViewModel, SyncStatusState>(
  SyncStatusViewModel.new,
);
