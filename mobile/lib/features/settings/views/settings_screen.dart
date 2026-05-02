/// Экран настроек: статус sync + ручной триггер sync now + logout +
/// версия приложения и текущий BACKEND_URL.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:package_info_plus/package_info_plus.dart';

import '../../../core/env.dart';
import '../../../core/logging.dart';
import '../../auth/providers.dart';
import '../../scanning/view_models/sync_status_view_model.dart';

class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key});

  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen> {
  PackageInfo? _info;

  @override
  void initState() {
    super.initState();
    PackageInfo.fromPlatform().then((info) {
      if (mounted) setState(() => _info = info);
    });
  }

  @override
  Widget build(BuildContext context) {
    final user = ref.watch(currentUserProvider).value;
    final sync = ref.watch(syncStatusViewModelProvider);
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(title: const Text('Настройки')),
      body: SafeArea(
        child: ListView(
          children: <Widget>[
            if (user != null)
              ListTile(
                leading: const Icon(Icons.person_outline),
                title: Text(user.fullName),
                subtitle: Text(user.email),
                trailing: Chip(
                  label: Text(user.isAdmin ? 'admin' : 'employee'),
                ),
              ),
            const Divider(),
            ListTile(
              leading: const Icon(Icons.cloud_sync_outlined),
              title: const Text('Синхронизация'),
              subtitle: Text(
                'В очереди: ${sync.pendingCount}\n'
                'Статус: ${sync.isOnline ? "онлайн" : "офлайн"}'
                '${sync.lastSyncAt != null ? "\nПоследняя: ${sync.lastSyncAt}" : ""}',
              ),
              isThreeLine: true,
              trailing: FilledButton(
                onPressed: sync.isSyncing
                    ? null
                    : () {
                        AppLogger.instance.i(
                          '[settings.syncNow] manual triggered',
                        );
                        ref
                            .read(syncStatusViewModelProvider.notifier)
                            .syncNow();
                      },
                child: sync.isSyncing
                    ? const SizedBox(
                        height: 16,
                        width: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Text('Сейчас'),
              ),
            ),
            const Divider(),
            const ListTile(
              leading: Icon(Icons.dns_outlined),
              title: Text('Backend URL'),
              subtitle: Text(Env.backendUrl),
            ),
            ListTile(
              leading: const Icon(Icons.info_outline),
              title: const Text('Версия'),
              subtitle: Text(
                _info == null
                    ? '...'
                    : '${_info!.version}+${_info!.buildNumber}',
              ),
            ),
            const Divider(),
            ListTile(
              leading: Icon(
                Icons.logout,
                color: theme.colorScheme.error,
              ),
              title: Text(
                'Выйти',
                style: TextStyle(color: theme.colorScheme.error),
              ),
              onTap: () async {
                AppLogger.instance.i('[settings.logout] confirmed');
                await ref.read(currentUserProvider.notifier).logout();
              },
            ),
          ],
        ),
      ),
    );
  }
}
