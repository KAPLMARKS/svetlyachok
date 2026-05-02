/// Главный экран — «Я на работе».
///
/// Большая кнопка «Снять отпечаток сейчас» вызывает `ScanningViewModel.manualScan`.
/// Видна для всех ролей. Кнопка «Калибровка зон» в drawer показывается
/// только админам (gate в router и в UI).
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/router.dart';
import '../../../shared/widgets/sync_indicator.dart';
import '../../auth/providers.dart';
import '../view_models/scanning_view_model.dart';
import '../view_models/sync_status_view_model.dart';

class ScanHomeScreen extends ConsumerWidget {
  const ScanHomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user = ref.watch(currentUserProvider).value;
    final scanState = ref.watch(scanningViewModelProvider);
    final sync = ref.watch(syncStatusViewModelProvider);
    final theme = Theme.of(context);

    ref.listen<ScanState>(scanningViewModelProvider, (prev, next) {
      if (next.lastErrorMessage != null &&
          next.lastErrorMessage != prev?.lastErrorMessage) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(next.lastErrorMessage!)),
        );
      } else if (next.lastLocalId != null &&
          next.lastLocalId != prev?.lastLocalId) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Отпечаток сохранён')),
        );
      }
    });

    return Scaffold(
      appBar: AppBar(
        title: const Text('Я на работе'),
        actions: <Widget>[
          const SyncIndicator(),
          IconButton(
            icon: const Icon(Icons.settings_outlined),
            tooltip: 'Настройки',
            onPressed: () => context.push(AppRoutes.settings),
          ),
        ],
      ),
      drawer: _AppDrawer(),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            children: <Widget>[
              if (user != null)
                Card(
                  child: ListTile(
                    leading: CircleAvatar(
                      child: Text(
                        user.fullName.isNotEmpty ? user.fullName[0] : '?',
                      ),
                    ),
                    title: Text(user.fullName),
                    subtitle: Text(
                      user.isAdmin ? 'Администратор' : 'Сотрудник',
                    ),
                  ),
                ),
              const SizedBox(height: 20),
              Expanded(
                child: Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: <Widget>[
                      Icon(
                        Icons.location_on_rounded,
                        size: 96,
                        color: theme.colorScheme.primary,
                      ),
                      const SizedBox(height: 24),
                      Text(
                        'Снимите Wi-Fi отпечаток,\nчтобы отметить присутствие',
                        textAlign: TextAlign.center,
                        style: theme.textTheme.bodyLarge,
                      ),
                      const SizedBox(height: 32),
                      FilledButton.icon(
                        onPressed: scanState.isScanning ? null : () {
                          ref
                              .read(scanningViewModelProvider.notifier)
                              .manualScan();
                        },
                        icon: scanState.isScanning
                            ? const SizedBox(
                                width: 18,
                                height: 18,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2.5,
                                ),
                              )
                            : const Icon(Icons.wifi_tethering),
                        label: Text(
                          scanState.isScanning
                              ? 'Сканирую…'
                              : 'Снять отпечаток сейчас',
                        ),
                        style: FilledButton.styleFrom(
                          minimumSize: const Size(280, 56),
                          textStyle: theme.textTheme.titleMedium,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Row(
                    children: <Widget>[
                      Icon(
                        sync.isOnline ? Icons.cloud_done : Icons.cloud_off,
                        color: sync.isOnline ? Colors.green : Colors.grey,
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: <Widget>[
                            Text(
                              sync.isOnline ? 'Онлайн' : 'Офлайн',
                              style: theme.textTheme.bodyLarge,
                            ),
                            Text(
                              'В очереди: ${sync.pendingCount}',
                              style: theme.textTheme.bodySmall,
                            ),
                          ],
                        ),
                      ),
                      if (sync.pendingCount > 0)
                        TextButton(
                          onPressed: sync.isSyncing
                              ? null
                              : () => ref
                                  .read(syncStatusViewModelProvider.notifier)
                                  .syncNow(),
                          child: const Text('Синхронизировать'),
                        ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _AppDrawer extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user = ref.watch(currentUserProvider).value;
    return Drawer(
      child: SafeArea(
        child: ListView(
          children: <Widget>[
            UserAccountsDrawerHeader(
              accountName: Text(user?.fullName ?? ''),
              accountEmail: Text(user?.email ?? ''),
              currentAccountPicture: CircleAvatar(
                child: Text(
                  user?.fullName.isNotEmpty == true ? user!.fullName[0] : '?',
                ),
              ),
            ),
            ListTile(
              leading: const Icon(Icons.location_on_outlined),
              title: const Text('Я на работе'),
              onTap: () {
                Navigator.pop(context);
                context.go(AppRoutes.scan);
              },
            ),
            if (user?.isAdmin == true)
              ListTile(
                leading: const Icon(Icons.tune),
                title: const Text('Калибровка зон'),
                onTap: () {
                  Navigator.pop(context);
                  context.go(AppRoutes.adminCalibration);
                },
              ),
            const Divider(),
            ListTile(
              leading: const Icon(Icons.settings_outlined),
              title: const Text('Настройки'),
              onTap: () {
                Navigator.pop(context);
                context.push(AppRoutes.settings);
              },
            ),
          ],
        ),
      ),
    );
  }
}
