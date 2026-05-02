/// Unit-тесты `LoginViewModel`: валидация формы, успех логина, ошибки.
library;

import 'package:dartz/dartz.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:svetlyachok_mobile/core/errors.dart';
import 'package:svetlyachok_mobile/domain/models/token_pair.dart';
import 'package:svetlyachok_mobile/domain/models/user.dart';
import 'package:svetlyachok_mobile/domain/repositories/auth_repository.dart';
import 'package:svetlyachok_mobile/features/auth/providers.dart';
import 'package:svetlyachok_mobile/features/auth/view_models/login_view_model.dart';

class _FakeAuthRepository implements AuthRepository {
  _FakeAuthRepository({
    this.loginResult,
    this.meResult,
  });

  Either<Failure, TokenPair>? loginResult;
  Either<Failure, User>? meResult;

  int loginCalls = 0;
  int meCalls = 0;

  @override
  Future<Either<Failure, TokenPair>> login(String email, String password) async {
    loginCalls++;
    return loginResult ??
        Right(
          TokenPair(
            accessToken: 'a',
            refreshToken: 'r',
            expiresIn: 1800,
            issuedAt: DateTime.now().toUtc(),
          ),
        );
  }

  @override
  Future<Either<Failure, User>> me() async {
    meCalls++;
    return meResult ??
        const Right(
          User(
            id: 1,
            email: 'a@b.c',
            fullName: 'Test User',
            role: 'employee',
            isActive: true,
          ),
        );
  }

  @override
  Future<Either<Failure, TokenPair>> refresh(String refreshToken) async =>
      throw UnimplementedError();

  @override
  Future<Either<Failure, void>> logout() async => const Right<Failure, void>(null);

  @override
  Future<TokenPair?> getCachedTokens() async => null;

  @override
  Future<User?> getCachedUser() async => null;

  @override
  Future<void> clearCache() async {}
}

class _AlwaysLoadingCurrentUser extends CurrentUserNotifier {
  @override
  Future<User?> build() async {
    return null;
  }
}

void main() {
  group('LoginViewModel.validate*', () {
    test('validateEmail rejects empty / malformed', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);
      final vm = container.read(loginViewModelProvider.notifier);
      expect(vm.validateEmail(null), 'Введите email');
      expect(vm.validateEmail(''), 'Введите email');
      expect(vm.validateEmail('not-an-email'), 'Некорректный email');
      expect(vm.validateEmail('a@b.c'), isNull);
    });

    test('validatePassword requires min length 8', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);
      final vm = container.read(loginViewModelProvider.notifier);
      expect(vm.validatePassword(null), 'Введите пароль');
      expect(vm.validatePassword(''), 'Введите пароль');
      expect(vm.validatePassword('1234567'), 'Минимум 8 символов');
      expect(vm.validatePassword('12345678'), isNull);
    });
  });

  group('LoginViewModel.submit', () {
    test('returns false on UI validation failure (no repo call)', () async {
      final fake = _FakeAuthRepository();
      final container = ProviderContainer(
        overrides: <Override>[
          authRepositoryProvider.overrideWithValue(fake),
          currentUserProvider.overrideWith(_AlwaysLoadingCurrentUser.new),
        ],
      );
      addTearDown(container.dispose);
      final vm = container.read(loginViewModelProvider.notifier);

      vm.setEmail('not-email');
      vm.setPassword('short');
      final ok = await vm.submit();

      expect(ok, isFalse);
      expect(fake.loginCalls, 0);
      final state = container.read(loginViewModelProvider);
      expect(state.errorCode, 'validation_invalid');
      expect(state.errorMessage, isNotNull);
    });

    test('returns true on successful login + sets currentUser', () async {
      final user = const User(
        id: 42,
        email: 'admin@svetlyachok.local',
        fullName: 'Админ',
        role: 'admin',
        isActive: true,
      );
      final fake = _FakeAuthRepository(
        meResult: Right(user),
      );
      final container = ProviderContainer(
        overrides: <Override>[
          authRepositoryProvider.overrideWithValue(fake),
          currentUserProvider.overrideWith(_AlwaysLoadingCurrentUser.new),
        ],
      );
      addTearDown(container.dispose);

      // Проинициализировать currentUserProvider, чтобы можно было читать notifier.
      await container.read(currentUserProvider.future);

      final vm = container.read(loginViewModelProvider.notifier);
      vm.setEmail('admin@svetlyachok.local');
      vm.setPassword('admin12345');
      final ok = await vm.submit();

      expect(ok, isTrue);
      expect(fake.loginCalls, 1);
      expect(fake.meCalls, 1);
      final state = container.read(loginViewModelProvider);
      expect(state.isSubmitting, isFalse);
      expect(state.errorMessage, isNull);
      expect(container.read(currentUserProvider).value, equals(user));
    });

    test('returns false on auth_unauthorized + saves error code', () async {
      final fake = _FakeAuthRepository(
        loginResult: Left(AuthFailure.unauthorized()),
      );
      final container = ProviderContainer(
        overrides: <Override>[
          authRepositoryProvider.overrideWithValue(fake),
          currentUserProvider.overrideWith(_AlwaysLoadingCurrentUser.new),
        ],
      );
      addTearDown(container.dispose);
      await container.read(currentUserProvider.future);

      final vm = container.read(loginViewModelProvider.notifier);
      vm.setEmail('admin@svetlyachok.local');
      vm.setPassword('wrong-password');
      final ok = await vm.submit();

      expect(ok, isFalse);
      expect(fake.loginCalls, 1);
      expect(fake.meCalls, 0);
      final state = container.read(loginViewModelProvider);
      expect(state.errorCode, 'auth_unauthorized');
      expect(state.isSubmitting, isFalse);
    });
  });
}
