/// Result-pattern через `dartz.Either<Failure, T>`.
///
/// Все методы repository возвращают `Result<T>`. Никаких `throw` через слои —
/// исключения отлавливаются в `data/api/` и сразу маппятся в `Failure`.
library;

import 'package:dartz/dartz.dart';

import 'errors.dart';

/// Псевдоним для удобства: `Future<Result<User>>` читается короче,
/// чем `Future<Either<Failure, User>>`.
typedef Result<T> = Either<Failure, T>;

/// Хелпер для успешного результата.
Result<T> success<T>(T value) => Right<Failure, T>(value);

/// Хелпер для ошибки.
Result<T> failure<T>(Failure error) => Left<Failure, T>(error);
