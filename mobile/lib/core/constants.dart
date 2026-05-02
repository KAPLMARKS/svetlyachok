/// Константы уровня приложения (АИС Светлячок).
///
/// Согласно правилам проекта (`.ai-factory/rules/base.md`) глобальные константы
/// именуются с префиксом `k`.
library;

/// Максимальное количество элементов в одном POST `/fingerprints/batch`.
/// Совпадает с `BATCH_MAX_ITEMS` на стороне backend; превышение → 422.
const int kBatchMaxItems = 100;

/// Жёсткий лимит чанков, отправляемых за один запуск sync.
/// Защита от гигантских foreground-выгрузок при долгом offline.
const int kMaxChunksPerSync = 5;

/// Окно throttling Wi-Fi сканера на Android 9+ — 4 скана за 2 минуты.
/// См. документацию `WifiManager.startScan()`.
const Duration kScanThrottleWindow = Duration(minutes: 2);

/// Максимум сканов в окне throttling (foreground).
const int kScanThrottleMaxInWindow = 4;

/// Минимальный интервал между ручными сканами в UI (1 скан / 30 сек).
/// 4 скана за 2 минуты = 1 скан в 30 сек.
const Duration kManualScanCooldown = Duration(seconds: 30);

/// Периодичность фоновых WorkManager-задач. Меньше 15 минут Android не разрешит.
const Duration kBackgroundTaskInterval = Duration(minutes: 15);

/// TTL для уже синхронизированных записей в локальном кэше.
const Duration kSyncedFingerprintTtl = Duration(days: 7);

/// TTL для terminal-rejected записей (хранятся для диагностики).
const Duration kRejectedFingerprintTtl = Duration(days: 30);

/// Максимальное количество retry до перевода записи в `sync_status=2 (rejected)`.
const int kMaxRetryCount = 5;

/// Таймаут ожидания auto-login на splash-экране до принудительного редиректа.
const Duration kSplashAuthTimeout = Duration(seconds: 5);

/// Запас в секундах при проверке протухшего access-токена (refresh с упреждением).
const Duration kAccessTokenRefreshBuffer = Duration(seconds: 30);

/// Имена WorkManager-задач (уникальные ID). Совпадают с регистрацией в scheduler.dart.
const String kBgTaskScanAndCache = 'scanAndCache';
const String kBgTaskSyncFingerprints = 'syncFingerprints';
const String kBgUniqueScanPeriodic = 'wifi_scan_periodic';
const String kBgUniqueSyncPeriodic = 'fingerprint_sync';
const String kBgUniqueSyncOneoff = 'fingerprint_sync_now';

/// Минимальный/максимальный диапазон RSSI (dBm) согласно контракту backend.
const int kRssiMin = -100;
const int kRssiMax = 0;

/// Максимальное количество wi-fi точек на отпечаток (контракт backend).
const int kFingerprintMaxNetworks = 200;

/// Минимальная длина пароля при UI-валидации формы login.
/// Backend всё равно проверит — это удобство ввода, не security.
const int kLoginPasswordMinLength = 8;

/// Базовый префикс REST API. Используется в Dio-клиенте.
const String kApiVersionPrefix = '/api/v1';
