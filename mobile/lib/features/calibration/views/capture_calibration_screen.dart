/// «Снять эталонную точку для зоны Х» — admin-режим.
///
/// Кнопка триггерит `CalibrationCaptureViewModel.capture(zoneName)`.
/// State показывает счётчики attempts/successes и последний результат.
/// Несколько capture'ов подряд — плановое поведение, чтобы admin собрал
/// 3+ точек на зону без выхода-возврата.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../domain/models/zone.dart';
import '../view_models/calibration_view_model.dart';

class CaptureCalibrationScreen extends ConsumerWidget {
  const CaptureCalibrationScreen({required this.zone, super.key});

  final Zone zone;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(calibrationCaptureProvider(zone.id));
    final vm = ref.read(calibrationCaptureProvider(zone.id).notifier);
    final theme = Theme.of(context);

    ref.listen<CalibrationCaptureState>(
      calibrationCaptureProvider(zone.id),
      (prev, next) {
        if (next.lastErrorMessage != null &&
            next.lastErrorMessage != prev?.lastErrorMessage) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(next.lastErrorMessage!)),
          );
        } else if (next.successCount > (prev?.successCount ?? 0)) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Эталонная точка сохранена')),
          );
        }
      },
    );

    return Scaffold(
      appBar: AppBar(title: Text('Калибровка: ${zone.name}')),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            children: <Widget>[
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Row(
                    children: <Widget>[
                      Icon(
                        Icons.adjust,
                        color: theme.colorScheme.primary,
                        size: 32,
                      ),
                      const SizedBox(width: 16),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: <Widget>[
                            Text(
                              zone.name,
                              style: theme.textTheme.titleLarge,
                            ),
                            if (zone.description != null)
                              Text(
                                zone.description!,
                                style: theme.textTheme.bodySmall,
                              ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 24),
              _CounterCard(
                label: 'Снято точек',
                value: state.successCount.toString(),
                hint: 'Рекомендуется минимум 3 точки на зону',
              ),
              const SizedBox(height: 12),
              _CounterCard(
                label: 'Попыток',
                value: state.attemptCount.toString(),
              ),
              const Spacer(),
              FilledButton.icon(
                onPressed: state.isCapturing
                    ? null
                    : () => vm.capture(zone.name),
                icon: state.isCapturing
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2.5),
                      )
                    : const Icon(Icons.wifi_tethering),
                label: Text(
                  state.isCapturing
                      ? 'Сканирую…'
                      : (state.successCount == 0
                          ? 'Снять эталонную точку'
                          : 'Снять ещё одну'),
                ),
                style: FilledButton.styleFrom(
                  minimumSize: const Size.fromHeight(56),
                ),
              ),
              const SizedBox(height: 8),
              Text(
                'После 3+ точек закройте экран. ML обновится при '
                'следующем запросе позиционирования.',
                textAlign: TextAlign.center,
                style: theme.textTheme.bodySmall,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _CounterCard extends StatelessWidget {
  const _CounterCard({required this.label, required this.value, this.hint});
  final String label;
  final String value;
  final String? hint;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: <Widget>[
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text(label, style: Theme.of(context).textTheme.titleMedium),
                  if (hint != null)
                    Text(
                      hint!,
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                ],
              ),
            ),
            Text(
              value,
              style: Theme.of(context).textTheme.headlineMedium,
            ),
          ],
        ),
      ),
    );
  }
}
