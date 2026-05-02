/// Список зон для калибровки (admin-only).
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/router.dart';
import '../../../domain/models/zone.dart';
import '../providers.dart';

class CalibrationHomeScreen extends ConsumerWidget {
  const CalibrationHomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final asyncZones = ref.watch(zonesProvider);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Калибровка зон'),
        actions: <Widget>[
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'Обновить',
            onPressed: () => ref.invalidate(zonesProvider),
          ),
        ],
      ),
      body: asyncZones.when(
        data: (List<Zone> zones) => _ZonesList(zones: zones),
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (Object e, StackTrace _) => Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: <Widget>[
                const Icon(Icons.error_outline, size: 48),
                const SizedBox(height: 16),
                Text(
                  'Не удалось загрузить зоны:\n$e',
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 16),
                FilledButton(
                  onPressed: () => ref.invalidate(zonesProvider),
                  child: const Text('Повторить'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _ZonesList extends StatelessWidget {
  const _ZonesList({required this.zones});
  final List<Zone> zones;

  @override
  Widget build(BuildContext context) {
    if (zones.isEmpty) {
      return const Center(child: Text('Зоны не настроены'));
    }
    return ListView.separated(
      padding: const EdgeInsets.symmetric(vertical: 8),
      itemCount: zones.length,
      separatorBuilder: (_, __) => const Divider(height: 1),
      itemBuilder: (BuildContext context, int i) {
        final z = zones[i];
        return ListTile(
          leading: CircleAvatar(
            backgroundColor: _zoneColor(z),
            child: Text(z.name.isNotEmpty ? z.name[0].toUpperCase() : '?'),
          ),
          title: Text(z.name),
          subtitle: Text('${_zoneTypeLabel(z.type)}'
              '${z.description != null ? "  ·  ${z.description}" : ""}'),
          trailing: const Icon(Icons.chevron_right),
          onTap: () => context.push(
            '${AppRoutes.adminCalibration}/${z.id}',
            extra: z,
          ),
        );
      },
    );
  }

  Color _zoneColor(Zone z) {
    final raw = z.displayColor;
    if (raw == null) return Colors.blueGrey;
    final hex = raw.replaceAll('#', '');
    if (hex.length != 6) return Colors.blueGrey;
    final value = int.tryParse(hex, radix: 16);
    if (value == null) return Colors.blueGrey;
    return Color(0xFF000000 | value);
  }

  String _zoneTypeLabel(String type) {
    switch (type) {
      case 'workplace':
        return 'Рабочее место';
      case 'corridor':
        return 'Коридор';
      case 'meeting_room':
        return 'Переговорная';
      case 'outside_office':
        return 'Вне офиса';
      default:
        return type;
    }
  }
}
