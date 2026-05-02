/// LoginViewModel — состояние формы логина и обработка submit'а.
///
/// AsyncNotifier, потому что `submit()` — async операция с loading-состоянием
/// и потенциальной ошибкой. State хранит email/password (controlled inputs)
/// и errorCode/errorMessage от последней попытки логина.
///
/// При успехе:
/// 1. Получаем `User` через `authRepository.me()` (нужно для UI gate'ов).
/// 2. Записываем в `currentUserProvider` через `setUser` → router редиректит.
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/errors.dart';
import '../../../core/logging.dart';
import '../../../core/result.dart';
import '../../../domain/models/token_pair.dart';
import '../../../domain/models/user.dart';
import '../../../domain/repositories/auth_repository.dart';
import '../providers.dart';

class LoginState {
  const LoginState({
    this.email = '',
    this.password = '',
    this.isSubmitting = false,
    this.errorCode,
    this.errorMessage,
  });

  final String email;
  final String password;
  final bool isSubmitting;
  final String? errorCode;
  final String? errorMessage;

  LoginState copyWith({
    String? email,
    String? password,
    bool? isSubmitting,
    String? errorCode,
    String? errorMessage,
    bool clearError = false,
  }) {
    return LoginState(
      email: email ?? this.email,
      password: password ?? this.password,
      isSubmitting: isSubmitting ?? this.isSubmitting,
      errorCode: clearError ? null : (errorCode ?? this.errorCode),
      errorMessage: clearError ? null : (errorMessage ?? this.errorMessage),
    );
  }
}

class LoginViewModel extends AutoDisposeNotifier<LoginState> {
  static final RegExp _emailRe = RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$');

  @override
  LoginState build() => const LoginState();

  void setEmail(String value) {
    state = state.copyWith(email: value, clearError: true);
  }

  void setPassword(String value) {
    state = state.copyWith(password: value, clearError: true);
  }

  /// Локальная (UI) валидация. Возвращает текст ошибки или `null`.
  /// Сигнатура совместима с `FormFieldValidator<String>` — принимает `String?`.
  String? validateEmail(String? value) {
    final v = value?.trim() ?? '';
    if (v.isEmpty) return 'Введите email';
    if (!_emailRe.hasMatch(v)) return 'Некорректный email';
    return null;
  }

  String? validatePassword(String? value) {
    final v = value ?? '';
    if (v.isEmpty) return 'Введите пароль';
    if (v.length < 8) return 'Минимум 8 символов';
    return null;
  }

  Future<bool> submit() async {
    final email = state.email.trim();
    final password = state.password;
    final emailErr = validateEmail(email);
    final passErr = validatePassword(password);
    if (emailErr != null || passErr != null) {
      state = state.copyWith(
        errorCode: 'validation_invalid',
        errorMessage: emailErr ?? passErr,
      );
      return false;
    }

    AppLogger.instance.i('[login.submit] started: email=$email');
    state = state.copyWith(isSubmitting: true, clearError: true);

    final AuthRepository repo = ref.read(authRepositoryProvider);
    final Result<TokenPair> loginResult = await repo.login(email, password);

    final ok = await loginResult.fold(
      (Failure f) async {
        AppLogger.instance.w('[login.submit] failed: ${f.code}');
        state = state.copyWith(
          isSubmitting: false,
          errorCode: f.code,
          errorMessage: f.message,
        );
        return false;
      },
      (TokenPair _) async {
        final Result<User> meResult = await repo.me();
        return meResult.fold(
          (Failure f) async {
            AppLogger.instance.w('[login.submit] /me failed: ${f.code}');
            state = state.copyWith(
              isSubmitting: false,
              errorCode: f.code,
              errorMessage: f.message,
            );
            return false;
          },
          (User user) async {
            AppLogger.instance.i('[login.submit] success email=${user.email}');
            await ref.read(currentUserProvider.notifier).setUser(user);
            state = state.copyWith(isSubmitting: false, clearError: true);
            return true;
          },
        );
      },
    );

    return ok;
  }
}

final AutoDisposeNotifierProvider<LoginViewModel, LoginState>
    loginViewModelProvider =
    AutoDisposeNotifierProvider<LoginViewModel, LoginState>(
  LoginViewModel.new,
);
