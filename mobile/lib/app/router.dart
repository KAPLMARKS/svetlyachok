/// GoRouter конфигурация с auth-guard'ом, привязанным к `currentUserProvider`.
///
/// Стратегия:
/// - `refreshListenable` — обёртка над Riverpod-провайдером, нотифицирует
///   GoRouter при каждом изменении `currentUserProvider`. Для AsyncNotifier
///   — это loading→data→data(null) переходы.
/// - `redirect` — единственная точка решения «куда пускать пользователя»:
///   - state.isLoading → /splash (если ещё не на нём — иначе stay).
///   - user==null + не на /login → /login.
///   - user!=null + на /login или /splash → /scan.
///   - role!=admin + на /admin/* → /scan.
library;

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../core/logging.dart';
import '../domain/models/user.dart';
import '../domain/models/zone.dart';
import '../features/auth/providers.dart';
import '../features/auth/views/login_screen.dart';
import '../features/auth/views/splash_screen.dart';
import '../features/calibration/views/calibration_home_screen.dart';
import '../features/calibration/views/capture_calibration_screen.dart';
import '../features/scanning/views/scan_home_screen.dart';
import '../features/settings/views/settings_screen.dart';

class AppRoutes {
  const AppRoutes._();
  static const String splash = '/splash';
  static const String login = '/login';
  static const String scan = '/scan';
  static const String adminCalibration = '/admin/calibration';
  static const String settings = '/settings';
}

/// `Listenable`-обёртка над любым Riverpod-провайдером. GoRouter
/// перевычисляет `redirect` при каждом `notifyListeners()`.
class _RouterRefreshNotifier extends ChangeNotifier {
  _RouterRefreshNotifier(Ref ref) {
    _sub = ref.listen<AsyncValue<User?>>(
      currentUserProvider,
      (AsyncValue<User?>? prev, AsyncValue<User?> next) {
        notifyListeners();
      },
      fireImmediately: false,
    );
  }

  late final ProviderSubscription<AsyncValue<User?>> _sub;

  @override
  void dispose() {
    _sub.close();
    super.dispose();
  }
}

GoRouter buildRouter(Ref ref) {
  final _RouterRefreshNotifier refresh = _RouterRefreshNotifier(ref);

  return GoRouter(
    initialLocation: AppRoutes.splash,
    refreshListenable: refresh,
    debugLogDiagnostics: kDebugMode,
    redirect: (BuildContext context, GoRouterState state) {
      final AsyncValue<User?> async = ref.read(currentUserProvider);
      final String location = state.matchedLocation;

      // Пока кеш-резолв не закончился — держим на /splash. Splash сам
      // имеет таймер, который форсит /login если зависло.
      if (async.isLoading) {
        return location == AppRoutes.splash ? null : AppRoutes.splash;
      }

      final User? user = async.value;
      final bool loggedIn = user != null;
      final bool isAdmin = user?.isAdmin ?? false;
      final bool atSplash = location == AppRoutes.splash;
      final bool atLogin = location == AppRoutes.login;
      final bool atAdmin = location.startsWith('/admin');

      String? next;
      if (!loggedIn) {
        if (!atLogin) next = AppRoutes.login;
      } else {
        if (atSplash || atLogin) {
          next = AppRoutes.scan;
        } else if (atAdmin && !isAdmin) {
          next = AppRoutes.scan;
        }
      }

      if (next != null) {
        AppLogger.instance.d(
          '[router] redirect: from=$location to=$next loggedIn=$loggedIn '
          'isAdmin=$isAdmin',
        );
      }
      return next;
    },
    routes: <RouteBase>[
      GoRoute(
        path: AppRoutes.splash,
        builder: (BuildContext context, GoRouterState state) =>
            const SplashScreen(),
      ),
      GoRoute(
        path: AppRoutes.login,
        builder: (BuildContext context, GoRouterState state) =>
            const LoginScreen(),
      ),
      GoRoute(
        path: AppRoutes.scan,
        builder: (BuildContext context, GoRouterState state) =>
            const ScanHomeScreen(),
      ),
      GoRoute(
        path: AppRoutes.adminCalibration,
        builder: (BuildContext context, GoRouterState state) =>
            const CalibrationHomeScreen(),
        routes: <RouteBase>[
          GoRoute(
            path: ':zoneId',
            builder: (BuildContext context, GoRouterState state) {
              final zone = state.extra is Zone ? state.extra! as Zone : null;
              if (zone == null) {
                return const Scaffold(
                  body: Center(child: Text('Зона не выбрана')),
                );
              }
              return CaptureCalibrationScreen(zone: zone);
            },
          ),
        ],
      ),
      GoRoute(
        path: AppRoutes.settings,
        builder: (BuildContext context, GoRouterState state) =>
            const SettingsScreen(),
      ),
    ],
  );
}

/// Провайдер самого роутера — зависит от `currentUserProvider` через `buildRouter`.
final Provider<GoRouter> appRouterProvider = Provider<GoRouter>((Ref ref) {
  final router = buildRouter(ref);
  ref.onDispose(router.dispose);
  return router;
});
