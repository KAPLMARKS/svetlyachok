/// Корневой виджет приложения — `MaterialApp.router` + темы + локализация.
library;

import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../features/scanning/providers.dart';
import 'router.dart';
import 'theme.dart';

class SvetlyachokApp extends ConsumerWidget {
  const SvetlyachokApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // Активируем background-scheduler: подписка на currentUserProvider
    // регистрирует WorkManager-задачи после login и отменяет на logout.
    ref.watch(backgroundLifecycleBindingProvider);
    final router = ref.watch(appRouterProvider);
    return MaterialApp.router(
      title: 'Светлячок',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light(),
      darkTheme: AppTheme.dark(),
      routerConfig: router,
      locale: const Locale('ru'),
      supportedLocales: const <Locale>[Locale('ru'), Locale('en')],
      localizationsDelegates: const <LocalizationsDelegate<Object>>[
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
    );
  }
}
