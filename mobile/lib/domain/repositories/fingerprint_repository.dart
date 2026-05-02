/// Контракт репозитория Wi-Fi отпечатков (capture + cache + sync).
library;

import '../../core/result.dart';
import '../models/fingerprint.dart';

abstract class FingerprintRepository {
  /// Снять Wi-Fi отпечаток и положить в локальный кэш.
  /// Возвращает `localId` (id строки в sqflite).
  Future<Result<int>> capture();

  /// Снять отпечаток и сразу отправить как калибровочную точку
  /// `POST /calibration/points` (admin-only). Без локального кэша —
  /// требует онлайн-подключения.
  Future<Result<int>> captureCalibration(int zoneId);

  /// Стрим количества pending-отпечатков. Эмитит при любой записи в DAO,
  /// которая меняет `sync_status`.
  Stream<int> watchPendingCount();

  /// Запустить sync `pending → /fingerprints/batch` чанками.
  /// Hard-лимит 5 чанков за один запуск.
  Future<Result<SyncResult>> syncPending();

  /// Текущий счётчик pending (для UI без подписки на стрим).
  Future<int> currentPendingCount();
}
