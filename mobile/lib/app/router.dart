/// GoRouter конфигурация — роуты и заглушки.
///
/// Реальные guard'ы (auth/admin) подключаются на Phase 2 после готовности
/// `currentUserProvider`. Пока — простые заглушки-Scaffold'ы для всех роутов;
/// initial location = `/splash`.
library;

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

class AppRoutes {
  const AppRoutes._();
  static const String splash = '/splash';
  static const String login = '/login';
  static const String scan = '/scan';
  static const String adminCalibration = '/admin/calibration';
  static const String settings = '/settings';
}

final GoRouter appRouter = GoRouter(
  initialLocation: AppRoutes.splash,
  routes: <RouteBase>[
    GoRoute(
      path: AppRoutes.splash,
      builder: (BuildContext context, GoRouterState state) =>
          const _PlaceholderScreen(title: 'Светлячок', subtitle: 'Загрузка…'),
    ),
    GoRoute(
      path: AppRoutes.login,
      builder: (BuildContext context, GoRouterState state) =>
          const _PlaceholderScreen(title: 'Вход', subtitle: 'Phase 2'),
    ),
    GoRoute(
      path: AppRoutes.scan,
      builder: (BuildContext context, GoRouterState state) =>
          const _PlaceholderScreen(
        title: 'Я на работе',
        subtitle: 'Phase 3-4',
      ),
    ),
    GoRoute(
      path: AppRoutes.adminCalibration,
      builder: (BuildContext context, GoRouterState state) =>
          const _PlaceholderScreen(
        title: 'Калибровка зон',
        subtitle: 'Phase 5 — admin',
      ),
    ),
    GoRoute(
      path: AppRoutes.settings,
      builder: (BuildContext context, GoRouterState state) =>
          const _PlaceholderScreen(title: 'Настройки', subtitle: 'Phase 4'),
    ),
  ],
);

class _PlaceholderScreen extends StatelessWidget {
  const _PlaceholderScreen({required this.title, required this.subtitle});

  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: <Widget>[
            const Icon(Icons.construction_outlined, size: 64),
            const SizedBox(height: 16),
            Text(subtitle, style: Theme.of(context).textTheme.bodyMedium),
          ],
        ),
      ),
    );
  }
}
