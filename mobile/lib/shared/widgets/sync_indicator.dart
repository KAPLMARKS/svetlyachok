/// Маленький индикатор-точка в AppBar — статус синхронизации.
///
/// Цвета:
/// - зелёный — pending=0 + online (всё доехало)
/// - жёлтый — pending>0 (есть несинхронизированные записи)
/// - серый — offline
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../features/scanning/view_models/sync_status_view_model.dart';

class SyncIndicator extends ConsumerWidget {
  const SyncIndicator({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(syncStatusViewModelProvider);

    final Color color;
    final String tooltip;
    if (!state.isOnline) {
      color = Colors.grey;
      tooltip = 'Нет подключения к серверу';
    } else if (state.pendingCount > 0) {
      color = Colors.amber;
      tooltip = 'В очереди: ${state.pendingCount} отпечатков';
    } else {
      color = Colors.green;
      tooltip = 'Все данные синхронизированы';
    }

    return Tooltip(
      message: tooltip,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            if (state.isSyncing)
              const SizedBox(
                width: 14,
                height: 14,
                child: CircularProgressIndicator(strokeWidth: 2),
              )
            else
              Container(
                width: 12,
                height: 12,
                decoration: BoxDecoration(
                  color: color,
                  shape: BoxShape.circle,
                ),
              ),
            if (state.pendingCount > 0) ...<Widget>[
              const SizedBox(width: 6),
              Text(
                '${state.pendingCount}',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          ],
        ),
      ),
    );
  }
}
