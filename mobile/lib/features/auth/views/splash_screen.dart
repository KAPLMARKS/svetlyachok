/// SplashScreen — индикатор пока `currentUserProvider` решает, кто залогинен.
///
/// Сам редирект делает GoRouter через `redirect`-callback и `refreshListenable`.
/// Этот экран — просто визуальное «подождите»: spinner + лого + safety-таймер.
///
/// Safety-таймер: если `currentUserProvider` зависает дольше 6 сек — форсим
/// редирект на /login (offline + протухший access + нет ответа от refresh).
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/router.dart';
import '../../../core/logging.dart';
import '../providers.dart';

class SplashScreen extends ConsumerStatefulWidget {
  const SplashScreen({super.key});

  @override
  ConsumerState<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends ConsumerState<SplashScreen> {
  Timer? _timeoutTimer;

  @override
  void initState() {
    super.initState();
    _timeoutTimer = Timer(const Duration(seconds: 6), () {
      final async = ref.read(currentUserProvider);
      if (!mounted || !async.isLoading) return;
      AppLogger.instance.w(
        '[splash] timeout, forcing redirect to /login',
      );
      ref.read(currentUserProvider.notifier).forceLoggedOut();
      if (mounted) {
        context.go(AppRoutes.login);
      }
    });
  }

  @override
  void dispose() {
    _timeoutTimer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: <Widget>[
            Icon(
              Icons.location_on_outlined,
              size: 72,
              color: theme.colorScheme.primary,
            ),
            const SizedBox(height: 16),
            Text(
              'Светлячок',
              style: theme.textTheme.headlineSmall,
            ),
            const SizedBox(height: 32),
            const CircularProgressIndicator(),
          ],
        ),
      ),
    );
  }
}
