/// Riverpod-провайдеры auth-слоя.
///
/// - `sharedPreferencesProvider` — async-инициализация `SharedPreferences`.
/// - `prefsProvider` — обёртка над `SharedPreferences` для access-токена/user/device_id.
/// - `secureStorageProvider` — обёртка над `flutter_secure_storage` для refresh-токена.
/// - `dioProvider` — пара Dio (main+refresh) с auth/retry интерсепторами.
/// - `authRepositoryProvider` — реализация AuthRepository.
/// - `currentUserProvider` — AsyncNotifier, источник истины «кто сейчас залогинен».
///
/// `currentUserProvider` загружает кеш на старте и:
/// 1. Если access не протух → доверяет кешу (offline-friendly).
/// 2. Если access протух, но refresh есть → пытается /auth/refresh + /me.
/// 3. Если refresh нет/refresh упал → state=AsyncData(null).
library;

import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../core/errors.dart';
import '../../core/logging.dart';
import '../../core/result.dart';
import '../../data/api/auth_interceptor.dart';
import '../../data/api/dio_client.dart';
import '../../data/local/prefs.dart';
import '../../data/local/secure_storage.dart';
import '../../data/repositories/auth_repository_impl.dart';
import '../../domain/models/token_pair.dart';
import '../../domain/models/user.dart';
import '../../domain/repositories/auth_repository.dart';

/// Async-провайдер `SharedPreferences`. Резолвится один раз при старте.
final FutureProvider<SharedPreferences> sharedPreferencesProvider =
    FutureProvider<SharedPreferences>((ref) async {
  return SharedPreferences.getInstance();
});

/// Обёртка `Prefs`. Зависит от готовности `SharedPreferences`.
///
/// Если `SharedPreferences` ещё не загрузились — кидает `StateError`. В UI
/// до этого мы не доходим, потому что `SplashScreen` ждёт `currentUserProvider`,
/// а тот зависит от `sharedPreferencesProvider`.
final Provider<Prefs> prefsProvider = Provider<Prefs>((ref) {
  final asyncSp = ref.watch(sharedPreferencesProvider);
  return asyncSp.when(
    data: Prefs.new,
    error: (Object e, StackTrace st) =>
        throw StateError('SharedPreferences init failed: $e'),
    loading: () => throw StateError('SharedPreferences not ready'),
  );
});

/// Singleton `SecureStorage` (без Future — конструктор не делает I/O).
final Provider<SecureStorage> secureStorageProvider =
    Provider<SecureStorage>((ref) => SecureStorage());

/// Пара Dio (main+refresh) и сам `AuthInterceptor`.
final Provider<DioPair> dioProvider = Provider<DioPair>((ref) {
  final prefs = ref.watch(prefsProvider);
  final secureStorage = ref.watch(secureStorageProvider);
  final pair = buildDio(prefs: prefs, secureStorage: secureStorage);
  ref.onDispose(() {
    pair.auth.dispose();
    pair.main.close(force: true);
    pair.refresh.close(force: true);
  });
  return pair;
});

/// Реализация `AuthRepository`. UI/ViewModel зависят только от абстракции.
final Provider<AuthRepository> authRepositoryProvider =
    Provider<AuthRepository>((ref) {
  final dioPair = ref.watch(dioProvider);
  return AuthRepositoryImpl(
    dio: dioPair.main,
    prefs: ref.watch(prefsProvider),
    secureStorage: ref.watch(secureStorageProvider),
  );
});

/// AsyncNotifier — источник истины «текущий пользователь».
///
/// `state.value == null` → не залогинен (router перебросит на /login).
/// `state.value != null` → залогинен (router пропустит на /scan).
/// `state.isLoading` → splash крутится.
class CurrentUserNotifier extends AsyncNotifier<User?> {
  StreamSubscription<AuthEvent>? _authSub;

  @override
  Future<User?> build() async {
    final repo = ref.watch(authRepositoryProvider);
    final dioPair = ref.watch(dioProvider);

    // Подписка на AuthExpired из interceptor'а (refresh упал) — сбрасываем
    // state в null, router редиректит на /login.
    unawaited(_authSub?.cancel());
    _authSub = dioPair.auth.events.listen((AuthEvent event) {
      if (event == AuthEvent.expired) {
        AppLogger.instance.w('[providers.currentUser] auth expired event');
        state = const AsyncData<User?>(null);
      }
    });
    ref.onDispose(() {
      unawaited(_authSub?.cancel());
    });

    return _resolveCurrentUser(repo);
  }

  Future<User?> _resolveCurrentUser(AuthRepository repo) async {
    final cachedUser = await repo.getCachedUser();
    final cachedTokens = await repo.getCachedTokens();
    AppLogger.instance.d(
      '[providers.currentUser] init from cache: '
      'user=${cachedUser?.email} tokens=${cachedTokens != null}',
    );

    if (cachedUser == null || cachedTokens == null) {
      return null;
    }

    if (!cachedTokens.isAccessExpired) {
      return cachedUser;
    }

    AppLogger.instance.d(
      '[providers.currentUser] access expired, trying refresh',
    );
    final Result<TokenPair> refreshed = await repo.refresh(
      cachedTokens.refreshToken,
    );
    return refreshed.fold(
      (Failure f) async {
        AppLogger.instance.w(
          '[providers.currentUser] refresh failed: ${f.code}',
        );
        await repo.clearCache();
        return null;
      },
      (TokenPair _) async {
        final Result<User> meResult = await repo.me();
        return meResult.fold(
          (Failure f) async {
            AppLogger.instance.w(
              '[providers.currentUser] /me failed after refresh: ${f.code}',
            );
            return cachedUser;
          },
          (User user) => user,
        );
      },
    );
  }

  /// Установка пользователя после успешного логина (LoginViewModel.submit).
  Future<void> setUser(User user) async {
    AppLogger.instance.i(
      '[providers.currentUser] setUser: id=${user.id} role=${user.role}',
    );
    state = AsyncData<User?>(user);
  }

  /// Полный logout: best-effort серверный + локальная очистка + state=null.
  Future<void> logout() async {
    final repo = ref.read(authRepositoryProvider);
    AppLogger.instance.i('[providers.currentUser] logout requested');
    await repo.logout();
    state = const AsyncData<User?>(null);
  }

  /// Форсированный сброс в «не залогинен» — без обращения к серверу
  /// и без очистки кеша (используется splash-таймером и interceptor'ом).
  void forceLoggedOut() {
    AppLogger.instance.w('[providers.currentUser] forceLoggedOut');
    state = const AsyncData<User?>(null);
  }
}

final AsyncNotifierProvider<CurrentUserNotifier, User?> currentUserProvider =
    AsyncNotifierProvider<CurrentUserNotifier, User?>(CurrentUserNotifier.new);
