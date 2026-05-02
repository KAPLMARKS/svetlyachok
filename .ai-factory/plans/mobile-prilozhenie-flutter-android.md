# План: Mobile-приложение (Flutter, Android-only)

**Ветка (worktree):** `worktree-agent-ae03a3f4853a92cf1`
**Создан:** 2026-05-02
**Целевой каталог реализации:** `mobile/` (создаётся в рамках плана)

## Settings

- **Testing:** yes — unit-тесты use cases, репозиториев и ViewModel; widget-тесты ключевых экранов (login, scan, calibration); один integration-test happy-path под Android-эмулятор
- **Logging:** verbose — `logger`-пакет в Dart-стиле: `log.d` (debug, старт операции и параметры), `log.i` (info, ключевые переходы — login успех, отправлен batch, открыт scan), `log.w` (warning, бизнес-ошибки и retryable failures), `log.e` (error, неожиданные исключения с stacktrace). В release-сборке `Level.warning` и выше через `Logger.level`
- **Docs:** yes — `mobile/README.md` (на русском) с инструкцией: установка Flutter SDK, `flutter pub get`, сборка APK, передача `BACKEND_URL` через `--dart-define`, установка через ADB, обзор архитектуры и структуры папок

## Roadmap Linkage

- **Milestone:** "Mobile-приложение (Flutter, Android-only)"
- **Rationale:** План реализует веху №10 ROADMAP.md — экраны auth и сканирования, фоновое Wi-Fi сканирование через WorkManager (с учётом Android 9+ throttling: не более 4 сканов за 2 минуты), режим администратора для калибровки зон, локальный кэш `sqflite` неотправленных отпечатков с автоматической синхронизацией через bulk-endpoint при появлении сети. Без iOS, без production-инфраструктуры. После этой вехи остаются только web-панель и финальная веха «Локальный запуск + инструкция»

## Контекст и архитектурные решения

### Что уже есть на стороне backend (НЕ трогаем)

Все эндпоинты из спецификации `backend/README.md` готовы:

| Метод | Путь | Использование в mobile |
|-------|------|-------------------------|
| `POST` | `/api/v1/auth/login` | Login screen → пара токенов |
| `POST` | `/api/v1/auth/refresh` | Auto-refresh при 401 |
| `POST` | `/api/v1/auth/logout` | Кнопка «Выйти» |
| `GET` | `/api/v1/me` | Получение роли (`admin` / `employee`) для UI gate |
| `POST` | `/api/v1/fingerprints` | (опционально) синхронный отправщик. На практике используем только `batch` |
| `POST` | `/api/v1/fingerprints/batch` | **Главный канал sync.** До 100 items за запрос. Partial success: `accepted[].index` + `rejected[].index, code, message` |
| `POST` | `/api/v1/calibration/points` | Admin-only — отправка эталонной точки |
| `GET` | `/api/v1/zones` | Список зон для UI калибровки |
| `POST` | `/api/v1/positioning/classify` | (опционально) для отображения текущей зоны в UI после live-скана |

Контракт BSSID и dBm:
- `rssi_vector: Map<String, int>` — ключ BSSID, значение dBm в `[-100, 0]`
- Backend нормализует BSSID (любой регистр, `:`/`-` → канонический верхний регистр с `:`). Mobile **может** нормализовать заранее (для дедупликации в кэше), но это не обязательно
- `captured_at` — ISO-8601 с timezone (timezone-aware). Backend режектит «из будущего» более чем на 5 минут и старше 7 дней
- 1..200 точек доступа на отпечаток
- Batch: до 100 items за запрос; превышение → `422`

### Выбор state-management: **Riverpod 2.x** (vs Provider / BLoC)

| Кандидат | Pros | Cons | Решение |
|----------|------|------|---------|
| **Provider** | Простой, минимум boilerplate, рекомендован official-туториалом Flutter | Нет compile-time DI; `BuildContext` обязателен для чтения; сложнее тестировать (mock через `ProviderScope` сложнее, чем у Riverpod); устаревает | Отвергнут — мало преимуществ перед Riverpod |
| **BLoC** | Строгое разделение event/state, отличные devtools | Много boilerplate (event-классы, state-классы, freezed-кодген), для нашего CRUD-объёма избыточен, ViewModel-MVVM-стиль из flutter-skill менее естествен | Отвергнут — переусложнит mobile/ при размере фичи в ~5 экранов |
| **Riverpod 2.x** | Compile-time safe, не требует BuildContext (`ref.read/watch`), идеален для DI (`Provider`/`FutureProvider`/`StateNotifierProvider`/`AsyncNotifierProvider`), легко мокается в тестах через `ProviderContainer.overrideWith`, async-friendly | Кривая входа выше Provider; код-ген (`riverpod_generator`) опционален, но желателен | **Выбираем Riverpod 2.x** + `flutter_riverpod` + `riverpod_annotation` + `riverpod_generator` для DX |

ViewModel слой реализуем через `AsyncNotifier`/`StateNotifier` (внутри `features/<feature>/view_models/`); state-объекты — immutable через `freezed`. Это совместимо с MVVM из skill `flutter-apply-architecture-best-practices`.

### Layered архитектура (по ARCHITECTURE.md + base.md)

```
mobile/
├── lib/
│   ├── main.dart                    # Точка входа, ProviderScope, MaterialApp.router
│   ├── app/
│   │   ├── app.dart                 # MaterialApp + темы + GoRouter
│   │   ├── router.dart              # GoRouter routes + auth-guard
│   │   └── theme.dart               # ColorScheme + текстовые стили
│   ├── core/
│   │   ├── constants.dart           # kApiBaseUrl (через --dart-define), kBatchMaxItems=100
│   │   ├── env.dart                 # `Env.backendUrl` (compile-time const из --dart-define)
│   │   ├── errors.dart              # Failure-классы (NetworkFailure, AuthFailure, ServerFailure, CacheFailure)
│   │   ├── result.dart              # `typedef Result<T> = Either<Failure, T>` через dartz
│   │   └── logging.dart             # настройка logger (release vs debug уровни)
│   ├── data/
│   │   ├── api/
│   │   │   ├── dio_client.dart      # фабрика Dio + JWT-interceptor + retry-interceptor
│   │   │   ├── auth_interceptor.dart # авто-refresh при 401
│   │   │   ├── retry_interceptor.dart # exp backoff для idempotent методов
│   │   │   ├── dto/                 # *_dto.dart с json_serializable
│   │   │   │   ├── login_dto.dart
│   │   │   │   ├── token_pair_dto.dart
│   │   │   │   ├── me_dto.dart
│   │   │   │   ├── fingerprint_dto.dart
│   │   │   │   ├── batch_request_dto.dart
│   │   │   │   ├── batch_response_dto.dart
│   │   │   │   ├── zone_dto.dart
│   │   │   │   └── calibration_point_dto.dart
│   │   │   └── api_exceptions.dart  # маппинг HTTP кодов → Failure
│   │   ├── local/
│   │   │   ├── secure_storage.dart  # обёртка flutter_secure_storage (refresh-token)
│   │   │   ├── prefs.dart           # обёртка SharedPreferences (access-token + meta)
│   │   │   ├── db.dart              # singleton sqflite Database + создание схемы
│   │   │   └── fingerprint_cache_dao.dart # CRUD над локальной таблицей fingerprints
│   │   ├── wifi/
│   │   │   ├── wifi_scan_service.dart # обёртка wifi_scan plugin + permission helper
│   │   │   └── bssid_normalizer.dart  # утилита: AA-bb-cc-DD-ee-FF → AA:BB:CC:DD:EE:FF
│   │   └── repositories/
│   │       ├── auth_repository_impl.dart
│   │       ├── fingerprint_repository_impl.dart
│   │       ├── zone_repository_impl.dart
│   │       └── calibration_repository_impl.dart
│   ├── domain/
│   │   ├── models/                  # доменные модели (freezed, immutable)
│   │   │   ├── user.dart            # User (id, email, fullName, role)
│   │   │   ├── token_pair.dart      # access + refresh + expiresIn
│   │   │   ├── fingerprint.dart     # Fingerprint (capturedAt, rssiVector, sampleCount, deviceId, syncStatus)
│   │   │   ├── zone.dart            # Zone (id, name, type, displayColor)
│   │   │   └── calibration_point.dart
│   │   └── repositories/            # Protocol/abstract-классы
│   │       ├── auth_repository.dart
│   │       ├── fingerprint_repository.dart
│   │       ├── zone_repository.dart
│   │       └── calibration_repository.dart
│   ├── features/
│   │   ├── auth/
│   │   │   ├── view_models/
│   │   │   │   └── login_view_model.dart
│   │   │   └── views/
│   │   │       ├── login_screen.dart
│   │   │       └── splash_screen.dart # auto-login по сохранённому токену
│   │   ├── scanning/
│   │   │   ├── view_models/
│   │   │   │   ├── scanning_view_model.dart
│   │   │   │   └── sync_status_view_model.dart
│   │   │   ├── views/
│   │   │   │   ├── scan_home_screen.dart   # «Я на работе» + статус sync
│   │   │   │   └── scan_history_panel.dart # последние 20 отпечатков (cached)
│   │   │   └── background/
│   │   │       └── workmanager_callback.dart # точка входа фонового таска
│   │   ├── calibration/                       # admin-only
│   │   │   ├── view_models/
│   │   │   │   ├── calibration_view_model.dart
│   │   │   │   └── zone_picker_view_model.dart
│   │   │   └── views/
│   │   │       ├── calibration_home_screen.dart # gate по role==admin
│   │   │       ├── zone_picker_screen.dart      # выбор зоны для калибровки
│   │   │       └── capture_calibration_screen.dart # «снять отпечаток для зоны Х»
│   │   └── settings/
│   │       └── views/
│   │           └── settings_screen.dart  # logout, версия, build, информация о sync
│   └── shared/
│       ├── widgets/
│       │   ├── primary_button.dart
│       │   ├── error_banner.dart
│       │   ├── loading_overlay.dart
│       │   └── sync_indicator.dart       # точка-индикатор: синхронизировано/pending/offline
│       └── utils/
│           ├── time_utils.dart           # nowUtc(), DateTime → ISO-8601 timezone-aware
│           └── connectivity.dart         # обёртка connectivity_plus
├── android/
│   ├── app/
│   │   ├── build.gradle             # minSdkVersion=24, compileSdkVersion=34
│   │   └── src/main/AndroidManifest.xml # permissions: ACCESS_FINE_LOCATION, ACCESS_WIFI_STATE, CHANGE_WIFI_STATE, ACCESS_BACKGROUND_LOCATION, INTERNET
│   └── build.gradle
├── test/
│   ├── unit/
│   │   ├── data/
│   │   │   ├── fingerprint_cache_dao_test.dart
│   │   │   ├── bssid_normalizer_test.dart
│   │   │   └── auth_interceptor_test.dart
│   │   ├── domain/                  # пусто или smoke-тесты freezed
│   │   ├── features/
│   │   │   ├── auth/login_view_model_test.dart
│   │   │   ├── scanning/sync_view_model_test.dart
│   │   │   └── calibration/calibration_view_model_test.dart
│   │   └── shared/
│   │       └── time_utils_test.dart
│   ├── widget/
│   │   ├── login_screen_test.dart
│   │   └── scan_home_screen_test.dart
│   └── mocks/
│       └── mocks.mocks.dart         # mockito-сгенерированные моки
├── integration_test/
│   └── happy_path_test.dart         # один e2e на эмуляторе: login → scan-stub → cache → batch sync
├── pubspec.yaml
├── analysis_options.yaml            # очень строгие lint'ы (lints/recommended + custom)
└── README.md
```

**Принципы границ слоёв (как в backend Clean Architecture):**

- `domain/` не импортирует ничего из `data/`, `features/`, никаких пакетов кроме freezed/dartz/equatable
- `data/repositories/` имплементирует абстракции из `domain/repositories/`
- `features/` зависит от `domain/`, не от `data/` напрямую — DI выдаёт абстракции через Riverpod-провайдеры
- `shared/` — без зависимостей от features

### Хранение токенов: `flutter_secure_storage` (refresh) + `SharedPreferences` (access)

| Что | Где | Почему |
|-----|-----|--------|
| **refresh_token** (7 дней TTL) | `flutter_secure_storage` (Android: `EncryptedSharedPreferences` + `Keystore`) | Длинный TTL, кража = угроза до 7 дней. Должен быть зашифрован OS-средствами |
| **access_token** (30 минут TTL) | `SharedPreferences` (plain) | Короткий TTL, защита диска не критична; secure-storage медленный для частых обращений (interceptor читает на каждый запрос) |
| **userInfo** (id, email, role, full_name) | `SharedPreferences` (plain) | Только для UI-gate (admin-mode); не секрет |
| **device_id** (UUID, единожды генерируется) | `SharedPreferences` (plain) | Идентификатор устройства для anti-fraud на backend |

Альтернативу «всё в secure_storage» отвергли: на каждом сетевом запросе interceptor читает access — частое обращение к keystore замедляет UX.

### Wi-Fi сканирование: `wifi_scan` plugin + Android 9+ throttling

**Plugin:** `wifi_scan` (^0.4.x) — поверх `WifiManager.getScanResults()`. Альтернатива `wifi_iot` отвергнута: `wifi_iot` фокусируется на подключении/отключении к сетям, а не на сканировании RSSI; `wifi_scan` минимальнее и точнее под задачу.

**Permissions (Android 10+):**
- `ACCESS_FINE_LOCATION` — обязателен для получения BSSID/RSSI начиная с Android 6 (API 23)
- `ACCESS_BACKGROUND_LOCATION` — обязателен для фоновых сканов начиная с Android 10 (API 29)
- `ACCESS_WIFI_STATE`, `CHANGE_WIFI_STATE`, `INTERNET` — стандартные

**Throttling Android 9+ (API 28):**

> Системное ограничение: не более **4 сканов за 2 минуты на foreground-app**, и **гораздо строже** для background-приложений (фактически 1 скан в 30 минут). Описано в [`WifiManager` docs](https://developer.android.com/reference/android/net/wifi/WifiManager#startScan()).

Это значит:
1. **Foreground (экран открыт):** делаем не более 4 сканов за 2 минуты. На UI выставляем минимальный интервал ручного скана = 30 секунд (4 за 2 минуты = 1 за 30 сек).
2. **Background (WorkManager):** заявляем периодический таск с минимальной периодичностью **15 минут** (это и так минимум для `WorkManager` `PeriodicWorkRequest`). Никаких более частых сканов система не разрешит.
3. **Кодом самостоятельно делаем rate-limit:** в `WifiScanService` храним `_lastScanAt` и `_scansInWindow` (sliding 2-min window); при превышении возвращаем `Failure.throttled` без обращения к системе.
4. **`wifi_scan` API возвращает `CanGetScanResults.notSupported/noLocationPermissionRequired/noLocationServiceDisabled`** — пробрасываем в UI с понятным сообщением и кнопкой «Открыть настройки».

**Не используем `WifiManager.startScan()` под капотом** — `wifi_scan` сам делает старт-скан и возвращает результаты после `SCAN_RESULTS_AVAILABLE_ACTION`. Достаточно `WiFiScan.instance.getScannedResults()` после `startScan()` или `WiFiScan.instance.onScannedResultsAvailable` для подписки.

### Фоновое сканирование: `workmanager` package

**Package:** `workmanager` (^0.5.x) — обёртка над Android `WorkManager`. Регистрирует callback dispatcher, дёргает Dart-функцию из background-isolate.

**Конфигурация:**
- `Workmanager().registerPeriodicTask(uniqueName: "wifi_scan_periodic", taskName: "scanAndCache", frequency: const Duration(minutes: 15), constraints: Constraints(networkType: NetworkType.notRequired, requiresBatteryNotLow: true))` — без сетевых требований (мы кешируем локально и шлём при появлении сети — отдельный sync-таск)
- `Workmanager().registerPeriodicTask(uniqueName: "fingerprint_sync", taskName: "syncFingerprints", frequency: const Duration(minutes: 15), constraints: Constraints(networkType: NetworkType.connected))` — только при наличии сети
- `Constraints(requiresBatteryNotLow: true)` — не сканировать при низком заряде

**Background callback (`workmanager_callback.dart`):**
```dart
@pragma('vm:entry-point')
void callbackDispatcher() {
  Workmanager().executeTask((taskName, inputData) async {
    // изолят: создаём минимальный DI-контейнер: только то, что нужно для скана + кэша
    // log.i("[bg] task started", taskName);
    switch (taskName) {
      case 'scanAndCache':
        return await _runScanAndCache();
      case 'syncFingerprints':
        return await _runSync();
    }
    return true;
  });
}
```

В background-isolate **нет ProviderScope** из foreground — DI собираем вручную из синглтонов (Dio, sqflite, secureStorage). Это нормальная практика для WorkManager.

**Внимание:** Android может откладывать `PeriodicWorkRequest` на до 15 минут от запрошенной частоты + ещё больше при Doze. Это ОК — мы не претендуем на real-time tracking, только периодическое присутствие.

### Sqflite cache: одна таблица + pending-флаг

**Решение:** одна таблица `fingerprints` с явным `sync_status` (а не две таблицы pending/synced). Проще DAO, проще миграции, проще фильтр.

**Schema (v1):**

```sql
CREATE TABLE IF NOT EXISTS fingerprints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    captured_at TEXT NOT NULL,            -- ISO-8601 timezone-aware
    rssi_vector_json TEXT NOT NULL,       -- JSON {bssid: dbm}
    sample_count INTEGER NOT NULL DEFAULT 1,
    device_id TEXT,                        -- nullable (берём из prefs)
    sync_status INTEGER NOT NULL DEFAULT 0, -- 0=pending, 1=synced, 2=rejected_terminal
    server_id INTEGER,                     -- id с backend после accept
    last_error_code TEXT,                  -- captured_at_in_future / captured_at_too_old / ...
    retry_count INTEGER NOT NULL DEFAULT 0,
    last_retry_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_fp_sync_status ON fingerprints(sync_status);
CREATE INDEX IF NOT EXISTS idx_fp_captured_at ON fingerprints(captured_at);
```

**Версионирование:** `onCreate` создаёт v1; `onUpgrade(oldVer, newVer)` — пустой пока, готов к расширению. Версия БД в константе `_kDbVersion = 1`.

**TTL housekeeping:** при старте app и в sync-таске удаляем `sync_status=1` старше 7 дней (storage hygiene). `sync_status=2` (terminal reject) храним 30 дней для диагностики.

### Sync-стратегия через `/fingerprints/batch` (partial success)

**Алгоритм sync (детальный):**

1. **Connectivity check** — через `connectivity_plus`. Нет сети → выйти без ошибки, повторим из WorkManager
2. **Считать pending-чанк:** `SELECT * FROM fingerprints WHERE sync_status=0 ORDER BY captured_at ASC LIMIT 100` (kBatchMaxItems=100, ровно лимит backend)
3. Если pending пустой → `log.d("[sync] nothing to sync")`, return success
4. Сериализовать в `BatchRequestDto.items` (только `captured_at`, `rssi_vector`, `sample_count`, опционально `device_id` — НЕ передаём локальный id или sync_status)
5. `POST /api/v1/fingerprints/batch` с timeout 30s
6. **Обработка ответа** — критично:
   - **`200 OK`** → парсим `BatchResponseDto`. Для каждого `accepted[i].index` обновляем локальную запись по соответствующему позиционному id: `UPDATE fingerprints SET sync_status=1, server_id=? WHERE id=?`
   - Для каждого `rejected[i]`:
     - Если `code IN ('captured_at_in_future', 'captured_at_too_old', 'invalid_rssi_vector', 'rssi_value_out_of_range')` → terminal reject: `UPDATE fingerprints SET sync_status=2, last_error_code=? WHERE id=?`. Backend никогда не примет такой fingerprint
     - Если `code` нерасспознанный или временный (`internal_error`, `db_unavailable`) → оставляем `sync_status=0`, инкрементим `retry_count`, обновляем `last_retry_at`. Если `retry_count >= 5` — переводим в `sync_status=2` с пометкой
   - **`401`** → access протух → interceptor сделает refresh; если refresh failed → cancel sync, отправить event «нужен релогин»
   - **`422` на весь запрос** (Pydantic-validation, например >100 items) → log.e — это баг клиента, переходим в emergency-режим и шлём по 1 через `/fingerprints` (graceful degradation)
   - **`5xx`/timeout/network error** → не трогаем sync_status, инкрементим retry_count для каждой записи в чанке. Следующая попытка через WorkManager
7. Если есть ещё pending → повторить шаг 2 (до исчерпания или до hard-лимита 5 чанков за один запуск sync — иначе батарея/трафик)
8. `log.i("[sync] done", acceptedCount, rejectedCount, terminalRejects)`

**КРИТИЧНО — позиционное соответствие:** перед `POST` сохраняем `List<int> localIds` (порядок строго совпадает с `items`). После ответа: `accepted[].index` — это индекс в `items` массиве запроса = индекс в `localIds`. Удалить только по этим индексам. Не по `server_id` — он не возвращается у `rejected`.

### Retry/backoff при сетевых ошибках

**Уровень 1 — Dio retry interceptor:**
- Настройка `dio_smart_retry` (или ручной `RetryInterceptor`) — экспоненциальная задержка `[1s, 3s, 8s]`, до 3 попыток
- Применяется ТОЛЬКО к idempotent методам (`GET`) и к `POST /fingerprints/batch` (он идемпотентен по semantics — backend не делает дедупликацию, но повторная отправка тех же items даст партиал-success в рамках того же чанка; мы потом это поправим через server_id)
- НЕ применяем retry к `POST /auth/login` (рискуем дублировать ошибочный пароль и попасть под rate limit)

**Уровень 2 — sync-уровень backoff:**
- Между чанками внутри одного sync-запуска: 2 секунды
- Между запусками WorkManager: 15 минут (минимум `PeriodicWorkRequest`)
- В `sync_status=0` записях — `retry_count` (см. выше). При `retry_count >= 5` переводим в `sync_status=2`

**Уровень 3 — auth refresh:**
- AuthInterceptor ловит `401`, сериализует попытки refresh через `Mutex`/`Completer` (не делать 10 параллельных refresh при 10 одновременных 401), повторяет оригинальный запрос с новым access. При неудаче refresh — emit `AuthEvent.expired` и кикаем на login.

### Admin-mode UI gate по роли из JWT

**Источник истины — `/me`:** после login делаем `GET /api/v1/me`, сохраняем `User { id, email, fullName, role }` в SharedPreferences. Поле `role IN ('admin', 'employee')`. Не парсим JWT-payload — backend сам поднимет 401 если токен невалидный.

**Gate в UI:**
- `GoRouter` route `/admin/calibration` имеет `redirect`: если `currentUser.role != 'admin'` → редиректим на `/scan` с snackbar «Раздел только для администратора»
- На главном экране кнопка «Калибровка зон» отображается только если `role=='admin'` (через `Consumer` от `currentUserProvider`)

**Не рассчитываем роль на фронте:** при попытке `POST /calibration/points` без admin backend всё равно вернёт 403; UI gate — UX-удобство, а не security.

### Расчёт BSSID нормализации — на стороне клиента (для дедупликации)

**Решение:** нормализуем перед записью в локальный кэш, но **только для дедупликации внутри одного скана** (несколько samples из 1 wifi-точки в нескольких частотах могут вернуть один и тот же BSSID в разных регистрах — это редкий случай). Backend всё равно нормализует свою сторону — он никогда не доверяет клиенту.

**Утилита `bssid_normalizer.dart`:**
```dart
String normalizeBssid(String raw) {
  // Принимает: aa:bb:cc:dd:ee:ff, AA-BB-CC-DD-EE-FF, AABBCCDDEEFF, любой регистр
  // Возвращает: AA:BB:CC:DD:EE:FF (верхний регистр + ":")
}
```

Если BSSID не парсится (длина != 12 hex после удаления разделителей) — выбрасываем `FormatException`, логируем `log.w` и пропускаем эту wifi-точку (не валит весь скан).

### Permissions runtime-flow

**При первом запуске (или входе в scan-экран):**
1. Проверить `Permission.locationWhenInUse` (`permission_handler` package) — если denied, показать explainer screen «Нам нужно местоположение для Wi-Fi сканов» → кнопка «Разрешить» → системный диалог
2. Для фонового сканирования: `Permission.locationAlways` (`ACCESS_BACKGROUND_LOCATION`) — explainer + диалог. На Android 11+ это уведёт пользователя в системные настройки (нет inline-диалога)
3. Если permissionsстатус permanently denied — показать карточку «Откройте настройки» с кнопкой `openAppSettings()`

**В background callback** (workmanager) — если permission ушёл (пользователь отозвал) → `WiFiAccessStatus.notSupported` → возвращаем `Future.value(false)` (workmanager пометит таск как failed, переотправит позже), `log.w("[bg] no location permission")`.

### Connectivity-driven sync trigger (опционально, для UX)

Дополнительно к `PeriodicWorkRequest` подписываемся в foreground на `connectivity_plus`:
- При переходе offline → online (`ConnectivityResult.wifi` или `ConnectivityResult.mobile`) → запускаем `OneOffWorkRequest("fingerprint_sync_now")` без задержки
- Это не заменяет `PeriodicWorkRequest`, а дополняет его — даёт «мгновенный» sync при возврате сети, пока приложение открыто

### Что НЕ делаем (явные anti-scope)

- **iOS** — отключён в `pubspec.yaml` через отсутствие `ios/` директории и `flutter create --platforms=android`
- **HTTPS / certificate pinning** — backend в локальной сети по HTTP. На production-вехе планируется TLS, но это вне скоупа MVP-плана
- **Push-уведомления** — не нужны для учёта посещаемости
- **Offline classification на устройстве** — классификация остаётся серверной (backend `/positioning/classify`); mobile не знает зон
- **Шифрование sqflite-БД** — не критично: на устройстве лежат только RSSI-вектора, не PII
- **Биометрический login** — отложено
- **Локализация (l10n)** — UI на русском хардкод-строками. `intl` подключаем заголовочно, но используем минимально (для дат)
- **Token rotation / blacklist jti** — backend MVP это не делает, mobile не делает тоже
- **Дедупликация fingerprints на клиенте** — backend всё равно принимает близкие captured_at; нет смысла усложнять

## Tasks

### Phase 1: Setup проекта

- [ ] **Task 1.1: Инициализация Flutter-проекта**
  - **Файлы:** `mobile/pubspec.yaml`, `mobile/.gitignore`, `mobile/analysis_options.yaml`, `mobile/android/app/build.gradle`, `mobile/android/app/src/main/AndroidManifest.xml`, `mobile/lib/main.dart`
  - **Что:** Запустить (вручную, если есть Flutter SDK) `flutter create --platforms=android --org com.svetlyachok mobile`. После генерации:
    - В `pubspec.yaml` зафиксировать Dart SDK `>=3.4.0 <4.0.0`, Flutter SDK `>=3.24.0`
    - Удалить из `android/` всё, что относится к iOS (если что-то осталось)
    - В `android/app/build.gradle` поднять `minSdkVersion 24` (Android 7.0, охватывает 99% устройств), `compileSdkVersion 34`, `targetSdkVersion 34`
    - В `analysis_options.yaml` подключить `package:lints/recommended.yaml` + строгие правила: `prefer_const_constructors`, `avoid_print`, `prefer_final_locals`, `use_super_parameters`, `unnecessary_lambdas`
    - В `AndroidManifest.xml` добавить permissions: `INTERNET`, `ACCESS_WIFI_STATE`, `CHANGE_WIFI_STATE`, `ACCESS_FINE_LOCATION`, `ACCESS_BACKGROUND_LOCATION`, `WAKE_LOCK`, `RECEIVE_BOOT_COMPLETED` (последнее для restart workmanager после перезагрузки)
  - **Логи:** не требуются (генерация скелета)
  - **Зависимости в pubspec.yaml:**
    ```yaml
    dependencies:
      flutter:
        sdk: flutter
      flutter_riverpod: ^2.5.0
      riverpod_annotation: ^2.3.0
      freezed_annotation: ^2.4.0
      json_annotation: ^4.9.0
      dio: ^5.7.0
      dio_smart_retry: ^7.0.0
      flutter_secure_storage: ^9.2.0
      shared_preferences: ^2.3.0
      sqflite: ^2.3.0
      path_provider: ^2.1.0
      path: ^1.9.0
      wifi_scan: ^0.4.1
      workmanager: ^0.5.2
      permission_handler: ^11.3.0
      connectivity_plus: ^6.0.0
      go_router: ^14.0.0
      logger: ^2.4.0
      dartz: ^0.10.1
      uuid: ^4.4.0
      intl: ^0.19.0
    dev_dependencies:
      flutter_test:
        sdk: flutter
      integration_test:
        sdk: flutter
      mockito: ^5.4.0
      build_runner: ^2.4.0
      freezed: ^2.5.0
      json_serializable: ^6.8.0
      riverpod_generator: ^2.4.0
      riverpod_lint: ^2.3.0
      lints: ^4.0.0
    ```

- [ ] **Task 1.2: Базовая структура папок и core/**
  - **Файлы:** `mobile/lib/core/constants.dart`, `mobile/lib/core/env.dart`, `mobile/lib/core/errors.dart`, `mobile/lib/core/result.dart`, `mobile/lib/core/logging.dart`, `mobile/lib/main.dart`, `mobile/lib/app/app.dart`, `mobile/lib/app/router.dart`, `mobile/lib/app/theme.dart`
  - **Что:** Создать пустые папки слоёв (`data/`, `domain/`, `features/`, `shared/`). В `env.dart` — `class Env { static const backendUrl = String.fromEnvironment('BACKEND_URL', defaultValue: 'http://10.0.2.2:8000'); }` (10.0.2.2 — loopback к хосту с эмулятора). В `errors.dart` — sealed Failure-иерархия (`NetworkFailure`, `AuthFailure`, `ServerFailure`, `CacheFailure`, `ValidationFailure`, `PermissionFailure`, `ThrottledFailure`). В `result.dart` — `typedef Result<T> = Either<Failure, T>`. В `logging.dart` — настройка `Logger` с разными `Level` для kDebugMode и release. В `main.dart` — `runApp(ProviderScope(child: SvetlyachokApp()))`. В `app/router.dart` — GoRouter с initial route `/splash`, заглушки `/login`, `/scan`, `/admin/calibration`, `/settings`. В `theme.dart` — Material 3 ColorScheme (можно скопировать из шаблона), русская локаль `Locale('ru')` и `MaterialLocalizations.delegate`.
  - **Логи:** в `main.dart` `log.i("[app] boot: backendUrl=${Env.backendUrl}, debug=$kDebugMode")`
  - **Зависимости:** Task 1.1

- [ ] **Task 1.3: Generated-инфраструктура (build_runner)**
  - **Файлы:** `mobile/build.yaml` (опционально), `mobile/.gitignore` (добавить `*.g.dart` НЕ исключаем — мы их коммитим, чтобы collaborator не запускал build_runner для CI)
  - **Что:** Документировать в `README.md` команду `dart run build_runner build --delete-conflicting-outputs`. В `build.yaml` зафиксировать generated-output в той же директории.
  - **Логи:** не требуются
  - **Зависимости:** Task 1.2

### Phase 2: Auth flow

- [ ] **Task 2.1: Domain models — User, TokenPair**
  - **Файлы:** `mobile/lib/domain/models/user.dart`, `mobile/lib/domain/models/token_pair.dart`
  - **Что:** `freezed` модели:
    - `User`: `id: int`, `email: String`, `fullName: String`, `role: String` (`admin` | `employee`). Метод `bool get isAdmin => role == 'admin'`.
    - `TokenPair`: `accessToken: String`, `refreshToken: String`, `expiresIn: int`, `issuedAt: DateTime` (timezone-aware). Метод `bool get isAccessExpired => DateTime.now().toUtc().isAfter(issuedAt.add(Duration(seconds: expiresIn) - Duration(seconds: 30)))` (30-сек запас).
  - **Логи:** не требуются
  - **Тесты:** `test/unit/domain/user_test.dart` — `isAdmin` true/false; `token_pair_test.dart` — `isAccessExpired` для свежего/протухшего токена

- [ ] **Task 2.2: Domain repository — AuthRepository (abstract)**
  - **Файлы:** `mobile/lib/domain/repositories/auth_repository.dart`
  - **Что:** Abstract класс:
    ```dart
    abstract class AuthRepository {
      Future<Result<TokenPair>> login(String email, String password);
      Future<Result<TokenPair>> refresh(String refreshToken);
      Future<Result<User>> me();
      Future<Result<void>> logout();
      Future<TokenPair?> getCachedTokens();
      Future<User?> getCachedUser();
      Future<void> clearCache();
    }
    ```
  - **Логи:** не требуются (abstract)

- [ ] **Task 2.3: DTO + json_serializable**
  - **Файлы:** `mobile/lib/data/api/dto/login_dto.dart`, `token_pair_dto.dart`, `me_dto.dart`. Сгенерировать `*.g.dart` через build_runner.
  - **Что:** `LoginRequestDto({email, password})`, `TokenPairDto({accessToken, refreshToken, tokenType, expiresIn})`, `MeDto({id, email, fullName, role})`. Все поля `@JsonKey(name: 'access_token')` и т. д. (snake_case ↔ camelCase).
  - **Логи:** не требуются
  - **Тесты:** `test/unit/data/login_dto_test.dart` — round-trip JSON

- [ ] **Task 2.4: Dio client + AuthInterceptor + RetryInterceptor**
  - **Файлы:** `mobile/lib/data/api/dio_client.dart`, `mobile/lib/data/api/auth_interceptor.dart`, `mobile/lib/data/api/retry_interceptor.dart`, `mobile/lib/data/api/api_exceptions.dart`
  - **Что:**
    - `DioClient.create({required String baseUrl, required SecureStorage storage, required Prefs prefs}) -> Dio` — создаёт Dio с базовым URL, JSON-encoder, timeout 30s
    - `AuthInterceptor(prefs, storage, refreshFn)` — onRequest: подставляет `Authorization: Bearer ${access}` если есть. onError: при 401 + не-refresh-эндпоинт пытается refresh через `Mutex`, повторяет запрос; при провале refresh → emit `AuthExpiredEvent` через `StreamController` (Riverpod-провайдер слушает)
    - `RetryInterceptor` — обёртка `dio_smart_retry` с retries=3, backoff=[1s, 3s, 8s], whitelist методов GET и POST к `/fingerprints/batch`
    - `ApiException` маппинг: `DioException.connectionError → NetworkFailure.noConnection`, `DioException.connectionTimeout → NetworkFailure.timeout`, `DioException.badResponse(statusCode=401) → AuthFailure.unauthorized`, `403 → AuthFailure.forbidden`, `4xx → ServerFailure.badRequest`, `5xx → ServerFailure.internal`
  - **Логи:** в interceptor'ах: `log.d("[http] ${options.method} ${options.path}")`, `log.w("[http] 401 received, attempting refresh")`, `log.e("[http] ${err.response?.statusCode} ${err.requestOptions.path}")`. **Никогда не логировать тело запроса с паролем или токенами.**
  - **Тесты:** `test/unit/data/auth_interceptor_test.dart` — 401 → refresh → retry оригинальный запрос; refresh-fail → AuthExpired; параллельные 401 не делают 10 refresh

- [ ] **Task 2.5: SecureStorage и Prefs обёртки**
  - **Файлы:** `mobile/lib/data/local/secure_storage.dart`, `mobile/lib/data/local/prefs.dart`
  - **Что:**
    - `SecureStorage` — обёртка `flutter_secure_storage` с методами `saveRefreshToken(String)`, `getRefreshToken() -> Future<String?>`, `clear()`. Android-options: `EncryptedSharedPreferences`.
    - `Prefs` — обёртка `SharedPreferences` с методами для access token, expires_in, issued_at, user JSON, device_id (генерируется через uuid v4 при первом обращении).
  - **Логи:** `log.d("[storage] saveRefreshToken")`, `log.d("[prefs] getAccessToken: ${tk == null ? 'null' : 'present'}")` — **не логировать значения**
  - **Тесты:** `test/unit/data/prefs_test.dart` через `SharedPreferences.setMockInitialValues({})`

- [ ] **Task 2.6: AuthRepositoryImpl**
  - **Файлы:** `mobile/lib/data/repositories/auth_repository_impl.dart`
  - **Что:** Имплементация `AuthRepository` через Dio + SecureStorage + Prefs. `login`: `POST /auth/login` → парсим `TokenPairDto` → сохраняем в storage/prefs → возвращаем `Right(TokenPair)`. `refresh`: `POST /auth/refresh` с `refresh_token`. `me`: `GET /me` → `User` → кешируем. `logout`: `POST /auth/logout` (best-effort, игнорируем 401) + `clearCache()`. `getCachedTokens/User` — из storage/prefs.
  - **Логи:** `log.i("[auth.login] success: email=${email}")`, `log.w("[auth.login] failed: ${failure.code}")`, `log.i("[auth.refresh] success")`, `log.i("[auth.logout] tokens cleared")`. **Без значений токенов и паролей в логах.**
  - **Тесты:** `test/unit/features/auth/auth_repository_impl_test.dart` с моком Dio и storage

- [ ] **Task 2.7: Riverpod-провайдеры для auth**
  - **Файлы:** `mobile/lib/features/auth/providers.dart`
  - **Что:**
    - `prefsProvider`, `secureStorageProvider`, `dioProvider`, `authRepositoryProvider` (`Provider<AuthRepository>`)
    - `currentUserProvider` (`AsyncNotifierProvider<CurrentUserNotifier, User?>`) — на старте читает кеш + если access не протух, доверяет; иначе пытается refresh + me
  - **Логи:** `log.d("[providers.currentUser] init from cache: user=${user?.email}")`

- [ ] **Task 2.8: LoginViewModel + LoginScreen**
  - **Файлы:** `mobile/lib/features/auth/view_models/login_view_model.dart`, `mobile/lib/features/auth/views/login_screen.dart`, `mobile/lib/features/auth/views/splash_screen.dart`
  - **Что:**
    - `LoginViewModel extends AsyncNotifier<LoginState>` — состояние `LoginState({email, password, isLoading, error})`. Методы `setEmail`, `setPassword`, `submit() -> Future<void>` (вызывает `authRepository.login` → при успехе обновляет `currentUserProvider` → router сам перейдёт на `/scan`).
    - `LoginScreen` — Material 3 форма (TextField email, TextField password, кнопка «Войти», error banner, loading overlay). Валидация: email regex, password min length 8 (UI-side; backend всё равно проверит)
    - `SplashScreen` — пустой Scaffold с CircularProgressIndicator; на mount читает `currentUserProvider`, при готовности router редиректит на `/scan` (если auth) или `/login`
  - **Логи:** `log.i("[login.submit] started: email=${email}")`, `log.i("[login.submit] success")`, `log.w("[login.submit] failed: ${err.code}")`
  - **Тесты:** `test/unit/features/auth/login_view_model_test.dart` (моки auth-repo); `test/widget/login_screen_test.dart` (рендер + tap submit + проверка вызова mock)

- [ ] **Task 2.9: GoRouter auth-guard и редиректы**
  - **Файлы:** `mobile/lib/app/router.dart`
  - **Что:** `GoRouter.refreshListenable = ChangeNotifier`-обёртка над `currentUserProvider`. Routes:
    - `/splash` — SplashScreen, без guard
    - `/login` — LoginScreen, без guard, redirect на `/scan` если уже залогинен
    - `/scan` — ScanHomeScreen, redirect на `/login` если не залогинен
    - `/admin/calibration` — CalibrationHomeScreen, redirect на `/scan` если `!isAdmin`
    - `/settings` — SettingsScreen
  - **Логи:** `log.d("[router] redirect: from=${state.location} to=${next}")`

### Phase 3: Scanning + локальный кэш

- [ ] **Task 3.1: BSSID нормализация**
  - **Файлы:** `mobile/lib/data/wifi/bssid_normalizer.dart`
  - **Что:** Функция `String normalizeBssid(String raw)` (см. раздел «Расчёт BSSID нормализации»). Validate: 12 hex после удаления `:` `-`. Иначе `FormatException`.
  - **Логи:** `log.w("[bssid] cannot normalize: $raw")` при ошибке
  - **Тесты:** `test/unit/data/bssid_normalizer_test.dart` — 6+ кейсов: валид upper, валид lower, с дефисами, без разделителей, мусор, пустая строка, слишком короткая

- [ ] **Task 3.2: WifiScanService**
  - **Файлы:** `mobile/lib/data/wifi/wifi_scan_service.dart`
  - **Что:** Класс с интерфейсом:
    ```dart
    abstract class WifiScanService {
      Future<Result<List<WifiNetwork>>> scanOnce();
      Stream<List<WifiNetwork>> watchScans();
      Future<Result<bool>> ensurePermissions();
    }
    ```
    Имплементация `WifiScanServiceImpl` через `wifi_scan` plugin. Внутри — sliding-window rate-limiter: храним `Queue<DateTime>` последних сканов, при попытке нового скана если в окне 2 минут уже 4 → возвращаем `Left(ThrottledFailure(...))`. `ensurePermissions` через `permission_handler` (locationWhenInUse + locationAlways).
  - **WifiNetwork DTO:** `freezed { bssid: String, rssi: int, ssid: String?, frequency: int, capabilities: String? }`. RSSI ограничиваем `[-100, 0]` (если plugin вернёт что-то вне — clamp + log.w).
  - **Логи:** `log.d("[wifi.scan] start")`, `log.i("[wifi.scan] done: networks=${list.length}")`, `log.w("[wifi.scan] throttled: scansInWindow=${count}")`, `log.e("[wifi.scan] error: ${err}")`
  - **Тесты:** `test/unit/data/wifi_scan_service_test.dart` — rate-limiter (4 скана за 2 мин ОК, 5-й режектится); permission flow

- [ ] **Task 3.3: SQLite DB infrastructure**
  - **Файлы:** `mobile/lib/data/local/db.dart`
  - **Что:** Singleton `class AppDatabase { Future<Database> get db; }`. `_open()` через `openDatabase(path, version: 1, onCreate: _create)`, путь через `path_provider.getApplicationDocumentsDirectory()`. `_create` исполняет CREATE TABLE и индексы (см. раздел «Sqflite cache»). Пустой `onUpgrade` (готовность к v2).
  - **Логи:** `log.i("[db] opened: path=${path}, version=1")`
  - **Тесты:** в integration-тестах (sqflite не работает в pure-dart unit без `sqflite_common_ffi`); подключим `sqflite_common_ffi` в dev_dependencies для тестов

- [ ] **Task 3.4: FingerprintCacheDao**
  - **Файлы:** `mobile/lib/data/local/fingerprint_cache_dao.dart`
  - **Что:** DAO с методами:
    - `Future<int> insert(FingerprintCacheRow row)` — sync_status=0, retry_count=0
    - `Future<List<FingerprintCacheRow>> readPending({int limit = 100})`
    - `Future<void> markSynced(List<int> localIds, Map<int, int> serverIds)` — bulk UPDATE
    - `Future<void> markRejected(List<int> localIds, String code)` — terminal reject
    - `Future<void> incrementRetry(List<int> localIds)`
    - `Future<int> countPending()`
    - `Future<void> deleteSyncedOlderThan(Duration ttl)` — housekeeping
  - **`FingerprintCacheRow`** — простой data class (НЕ freezed, чтобы не плодить кодген) c `toMap()/fromMap()` для sqflite.
  - **Логи:** `log.d("[cache.insert] id=${id}, captured_at=${row.capturedAt}")`, `log.i("[cache.markSynced] count=${ids.length}")`, `log.i("[cache.markRejected] count=${ids.length}, code=${code}")`
  - **Тесты:** `test/unit/data/fingerprint_cache_dao_test.dart` через `sqflite_common_ffi` (in-memory `:memory:`). Проверить insert + readPending + markSynced + markRejected + incrementRetry. Минимум 6 тестов.

- [ ] **Task 3.5: Domain — Fingerprint модель + FingerprintRepository (abstract)**
  - **Файлы:** `mobile/lib/domain/models/fingerprint.dart`, `mobile/lib/domain/repositories/fingerprint_repository.dart`
  - **Что:** `Fingerprint` (freezed): `localId: int?`, `capturedAt: DateTime` (utc), `rssiVector: Map<String, int>`, `sampleCount: int`, `deviceId: String?`, `syncStatus: SyncStatus` (enum: pending/synced/rejected). `FingerprintRepository`:
    ```dart
    abstract class FingerprintRepository {
      Future<Result<int>> capture(); // делает скан, нормализует, кладёт в кэш, возвращает localId
      Future<Result<int>> captureCalibration(int zoneId); // admin-mode, шлёт сразу на /calibration/points
      Stream<int> watchPendingCount();
      Future<Result<SyncResult>> syncPending();
    }
    ```
    `SyncResult { acceptedCount, rejectedCount, terminalRejectCount, remainingPending }`.
  - **Логи:** abstract — без логов
  - **Тесты:** не требуются (abstract)

- [ ] **Task 3.6: Batch DTO**
  - **Файлы:** `mobile/lib/data/api/dto/fingerprint_dto.dart`, `batch_request_dto.dart`, `batch_response_dto.dart`
  - **Что:**
    - `FingerprintItemDto({capturedAt, rssiVector, sampleCount, deviceId})` — JsonKey snake_case
    - `BatchRequestDto({items})` — `items: List<FingerprintItemDto>`, max 100 (assert на конструкторе)
    - `BatchResponseDto({accepted, rejected, acceptedCount, rejectedCount})`
    - `BatchAcceptedDto({index, fingerprint: FingerprintResponseDto})`
    - `BatchRejectedDto({index, code, message})`
  - **Логи:** не требуются
  - **Тесты:** round-trip JSON для всех DTO

- [ ] **Task 3.7: FingerprintRepositoryImpl + sync logic**
  - **Файлы:** `mobile/lib/data/repositories/fingerprint_repository_impl.dart`
  - **Что:** Композирует `WifiScanService`, `FingerprintCacheDao`, `Dio`. `capture()`: вызывает scanOnce, нормализует BSSID, дедуплицирует ключи (если повторяется — берём max RSSI), кладёт в DAO. `captureCalibration(zoneId)`: scanOnce + сразу `POST /calibration/points` (без локального кэша — admin-операция, требует онлайн; при ошибке возвращаем Left). `syncPending()`: реализует алгоритм из раздела «Sync-стратегия» (читать pending → batch → распарсить accepted/rejected → marshal markSynced/markRejected/incrementRetry; цикл до 5 чанков). Connectivity-проверка через `connectivity_plus`. Hard-лимит 5 чанков за один запуск.
  - **Логи:** `log.i("[fp.capture] localId=${id}, networks=${count}")`, `log.i("[fp.sync] start: pending=${count}")`, `log.d("[fp.sync] chunk: items=${batch.length}")`, `log.i("[fp.sync] chunk done: accepted=${acc}, rejected=${rej}")`, `log.i("[fp.sync] complete: total_accepted=${total_acc}, total_rejected=${total_rej}, remaining_pending=${rem}")`, `log.w("[fp.sync] no connectivity")`, `log.e("[fp.sync] http error: ${status} ${path}")`
  - **Тесты:** `test/unit/data/fingerprint_repository_impl_test.dart` — мок Dio, мок DAO. Кейсы: пустой pending, partial success (3 accept + 2 reject), 5xx-ошибка (incrementRetry для всех), 401 (не должен дойти до DAO до refresh — но это тест auth_interceptor; здесь — мок успешного refresh). Минимум 8 тестов.

- [ ] **Task 3.8: ScanningViewModel + ScanHomeScreen**
  - **Файлы:** `mobile/lib/features/scanning/view_models/scanning_view_model.dart`, `mobile/lib/features/scanning/view_models/sync_status_view_model.dart`, `mobile/lib/features/scanning/views/scan_home_screen.dart`
  - **Что:**
    - `ScanningViewModel extends AsyncNotifier<ScanState>` — state: `lastScanAt`, `lastNetworks`, `pendingCount`, `error`. Метод `manualScan()` (вызывает `fingerprintRepository.capture()`).
    - `SyncStatusViewModel` слушает `watchPendingCount()` Stream + `connectivity_plus.onConnectivityChanged`. State: `pendingCount`, `isOnline`, `lastSyncAt`. Метод `syncNow()` — триггерит one-off WorkRequest.
    - `ScanHomeScreen` — Material 3: AppBar с пользователем, body — карточка «Я на работе» с большой кнопкой «Снять отпечаток сейчас», статус-карта `pendingCount` + `isOnline` (sync_indicator widget), краткая history последних 20 сканов, кнопка «Калибровка» (только для admin).
  - **Логи:** `log.i("[scan_vm.manualScan] start")`, `log.i("[scan_vm.manualScan] done: localId=${id}")`, `log.w("[scan_vm.manualScan] throttled")`
  - **Тесты:** `test/unit/features/scanning/scan_view_model_test.dart` (мок repo); `test/widget/scan_home_screen_test.dart` (рендер + tap)

### Phase 4: Sync через bulk-endpoint (доделка из Phase 3 + UI)

- [ ] **Task 4.1: Connectivity-driven one-off sync trigger (foreground)**
  - **Файлы:** `mobile/lib/features/scanning/view_models/sync_status_view_model.dart` (расширение)
  - **Что:** В ViewModel подписка на `Connectivity().onConnectivityChanged`. При переходе offline→online (детект по предыдущему значению):
    1. Если pendingCount > 0 → вызвать `Workmanager().registerOneOffTask("fingerprint_sync_now", "syncFingerprints", constraints: Constraints(networkType: NetworkType.connected))`
    2. Иначе ничего
  - **Зависимости:** Эта задача требует, чтобы `Workmanager().initialize(callbackDispatcher)` был выполнен до registerOneOffTask. **ВАЖНО:** `Workmanager().initialize` вынесен в Phase 1 (Task 1.2 — расширить main.dart) с пустым callbackDispatcher-stub'ом, который full-имплементируется в Task 6.1. Таким образом Task 4.1 может зарегистрировать one-off task начиная с Phase 4 без блокировки на Phase 6 (callback просто пропустит unknown task до его реализации в 6.1, что произойдёт раньше первого реального коммита Phase 4 при правильном порядке).
  - **Альтернатива (если предыдущая схема покажется хрупкой):** в foreground-режиме при переходе offline→online вызывать `fingerprintRepository.syncPending()` напрямую без WorkManager (foreground всё равно может выполнить сетевой запрос). One-off WorkRequest нужен только для случаев, когда foreground закрывается до завершения. Реализатор выбирает один из вариантов на этапе имплементации.
  - **Логи:** `log.i("[sync_vm] connectivity online, pending=${count}, triggering oneoff sync")`
  - **Тесты:** `test/unit/features/scanning/sync_view_model_test.dart` с моком ConnectivityPlus и Workmanager (через interface)

- [ ] **Task 4.2: SyncIndicator widget**
  - **Файлы:** `mobile/lib/shared/widgets/sync_indicator.dart`
  - **Что:** Маленький виджет в правом верхнем углу AppBar — точка зелёная (synced + online) / жёлтая (pending) / серая (offline). Подсказка-Tooltip: «N отпечатков ждут синхронизации».
  - **Логи:** не требуются (UI)
  - **Тесты:** `test/widget/sync_indicator_test.dart` — три состояния

- [ ] **Task 4.3: Manual «Sync now» в Settings**
  - **Файлы:** `mobile/lib/features/settings/views/settings_screen.dart`
  - **Что:** Экран настроек: показать `pendingCount`, кнопку «Синхронизировать сейчас» (вызывает `fingerprintRepository.syncPending()` напрямую в foreground), кнопку «Выйти» (вызывает `authRepository.logout()` → редирект на /login), версию приложения и build number, текущий BACKEND_URL (для отладки).
  - **Логи:** `log.i("[settings.syncNow] manual triggered")`, `log.i("[settings.logout] confirmed")`

### Phase 5: Admin calibration mode

- [ ] **Task 5.1: Domain — Zone, CalibrationPoint модели + ZoneRepository (abstract)**
  - **Файлы:** `mobile/lib/domain/models/zone.dart`, `mobile/lib/domain/models/calibration_point.dart`, `mobile/lib/domain/repositories/zone_repository.dart`, `mobile/lib/domain/repositories/calibration_repository.dart`
  - **Что:**
    - `Zone` (freezed): `id, name, type` (enum ZoneType: workplace/corridor/meetingRoom/outsideOffice), `description?`, `displayColor`
    - `CalibrationPoint` (freezed): `id, zoneId, capturedAt, rssiVector, sampleCount`
    - `ZoneRepository`: `Future<Result<List<Zone>>> listZones()`
    - `CalibrationRepository`: `Future<Result<CalibrationPoint>> submit(int zoneId, Fingerprint fp)` (`POST /calibration/points` напрямую без локального кэша)
  - **Логи:** abstract
  - **Тесты:** не требуются

- [ ] **Task 5.2: ZoneDto, CalibrationPointDto + Repository implementations**
  - **Файлы:** `mobile/lib/data/api/dto/zone_dto.dart`, `mobile/lib/data/api/dto/calibration_point_dto.dart`, `mobile/lib/data/repositories/zone_repository_impl.dart`, `mobile/lib/data/repositories/calibration_repository_impl.dart`
  - **Что:** `ZoneRepositoryImpl`: `GET /api/v1/zones` → `List<Zone>`, простой кеш в памяти (zone-список меняется редко, но не делаем persist). `CalibrationRepositoryImpl`: scanOnce + `POST /api/v1/calibration/points` с `zone_id, captured_at, rssi_vector, sample_count`. При 403 (employee пытается) → `Left(AuthFailure.forbidden)` (UI должен был это сам предотвратить, но защита глубокая).
  - **Логи:** `log.i("[zones.list] fetched: count=${list.length}")`, `log.i("[calibration.submit] zone=${zoneId}, networks=${count}")`, `log.w("[calibration.submit] failed: ${code}")`
  - **Тесты:** unit-тесты с моком Dio

- [ ] **Task 5.3: CalibrationViewModel + ZonePickerScreen + CaptureCalibrationScreen**
  - **Файлы:** `mobile/lib/features/calibration/view_models/calibration_view_model.dart`, `mobile/lib/features/calibration/view_models/zone_picker_view_model.dart`, `mobile/lib/features/calibration/views/calibration_home_screen.dart`, `mobile/lib/features/calibration/views/zone_picker_screen.dart`, `mobile/lib/features/calibration/views/capture_calibration_screen.dart`
  - **Что:**
    - `CalibrationHomeScreen` — список зон (через `zoneRepository.listZones()`) + рядом счётчик «N точек откалибровано» (опционально, можем взять с `GET /calibration/points?zone_id=N` через дополнительный метод — но это nice-to-have; в MVP просто список зон).
    - `ZonePickerScreen` — alternative entry для выбора зоны без главного списка (используется во flow «снять точку»).
    - `CaptureCalibrationScreen({required Zone zone})` — большая кнопка «Снять эталонную точку для зоны Х». При tap: scanOnce → отправить на `/calibration/points` → success snackbar или error banner. Возможность делать несколько подряд (чтобы admin набрал минимум 3 точки на зону без выхода-возврата).
  - **Логи:** `log.i("[calibration.capture] zone=${zoneName}, attempt=${n}")`, `log.i("[calibration.capture] success: serverId=${id}")`, `log.w("[calibration.capture] failed: ${code}")`
  - **Тесты:** `test/unit/features/calibration/calibration_view_model_test.dart` (моки)

- [ ] **Task 5.4: Admin-mode UI gate в роутере и HomeScreen**
  - **Файлы:** `mobile/lib/app/router.dart` (правка), `mobile/lib/features/scanning/views/scan_home_screen.dart` (правка)
  - **Что:** В router добавить `redirect: (ctx, state) => currentUser?.isAdmin == true ? null : '/scan'` для `/admin/*`. В `ScanHomeScreen` через `Consumer` от `currentUserProvider` показать кнопку «Калибровка» только для admin.
  - **Логи:** `log.d("[router] admin guard: user=${user.email}, isAdmin=${user.isAdmin}, location=${state.location}")`

### Phase 6: Background WorkManager

- [ ] **Task 6.1: WorkManager setup и callback dispatcher**
  - **Файлы:** `mobile/lib/features/scanning/background/workmanager_callback.dart`, `mobile/lib/main.dart` (правка)
  - **Что:**
    - В `main.dart` (до runApp): `await Workmanager().initialize(callbackDispatcher, isInDebugMode: kDebugMode)`. После этого регистрируем периодические задачи (см. раздел «Конфигурация»).
    - В `callbackDispatcher` собираем минимальный DI: `prefs = await SharedPreferences.getInstance()`, открываем sqflite, создаём Dio с auth-interceptor (берём токены из prefs+secureStorage), создаём WifiScanService, FingerprintRepositoryImpl. Внутри `executeTask` switch по taskName: `scanAndCache` → `repository.capture()`; `syncFingerprints` → `repository.syncPending()`. Возвращаем `true` при успехе или recoverable error (workmanager переотправит); `false` при `terminal failure` (нужен релогин).
    - При `AuthExpired` в background — пишем флаг `auth_expired_at` в Prefs, чтобы foreground при старте показал экран логина.
  - **Логи:** `log.i("[bg] task started: name=${taskName}")`, `log.i("[bg] task finished: name=${taskName}, success=${ok}")`, `log.e("[bg] uncaught: ${err}")`
  - **Тесты:** integration-тест запустить нельзя (workmanager dispatch требует Android). Unit-тест: вынести логику в чистую функцию `Future<bool> runScanAndCache(WifiScanService, FingerprintRepository)` и тестировать её отдельно с моками.

- [ ] **Task 6.2: Регистрация PeriodicWorkRequest при первом старте после login**
  - **Файлы:** `mobile/lib/features/auth/providers.dart` (правка currentUserProvider) или отдельный `mobile/lib/features/scanning/background/scheduler.dart`
  - **Что:** После успешного login или при старте уже залогиненного пользователя:
    ```dart
    Workmanager().registerPeriodicTask(
      "wifi_scan_periodic",
      "scanAndCache",
      frequency: const Duration(minutes: 15),
      constraints: Constraints(requiresBatteryNotLow: true),
      existingWorkPolicy: ExistingWorkPolicy.keep,
    );
    Workmanager().registerPeriodicTask(
      "fingerprint_sync",
      "syncFingerprints",
      frequency: const Duration(minutes: 15),
      constraints: Constraints(networkType: NetworkType.connected),
      existingWorkPolicy: ExistingWorkPolicy.keep,
    );
    ```
    `ExistingWorkPolicy.keep` — не переписываем уже зарегистрированные таски.
  - **На logout** — `Workmanager().cancelAll()` чтобы не сканировать без авторизации.
  - **Логи:** `log.i("[bg.scheduler] registered: scanAndCache + syncFingerprints, period=15min")`, `log.i("[bg.scheduler] cancelled all on logout")`

- [ ] **Task 6.3: Документация Android-специфики (для README)**
  - **Файлы:** `mobile/README.md` (раздел «Особенности Android»)
  - **Что:** Раздел в README:
    - Throttling Android 9+ (4 скана за 2 минуты в foreground; ~1 в 30 минут в background)
    - Doze mode и App Standby могут отложить задачи на час и более — это нормально
    - Battery optimization — пользователь может вручную отключить через Settings → Apps → Светлячок → Battery → Unrestricted, для надёжной работы фона
    - Permissions: ACCESS_FINE_LOCATION (foreground), ACCESS_BACKGROUND_LOCATION (Android 10+, для background)
  - **Логи:** не требуются (docs)

### Phase 7: Docs + build instructions

- [ ] **Task 7.1: README.md (русский, основной)**
  - **Файлы:** `mobile/README.md`
  - **Что:** Документ на русском, по образцу `backend/README.md`. Разделы:
    1. Стек (Flutter 3.24+, Dart 3.4+, Android-only, Riverpod, Dio, sqflite, workmanager, wifi_scan)
    2. Установка SDK (Flutter SDK + Android Studio + ADB)
    3. Установка зависимостей (`flutter pub get`)
    4. Code generation (`dart run build_runner build --delete-conflicting-outputs`)
    5. Конфигурация BACKEND_URL (через `--dart-define=BACKEND_URL=http://192.168.x.x:8000`)
    6. Запуск debug-сборки (`flutter run --dart-define=BACKEND_URL=http://...`)
    7. Сборка release APK (`flutter build apk --release --dart-define=BACKEND_URL=http://...`)
    8. Установка через ADB (`adb install -r build/app/outputs/flutter-apk/app-release.apk`)
    9. Архитектура (краткое описание слоёв со ссылкой на ARCHITECTURE.md)
    10. Permissions (что просит, зачем, как настраивать на устройстве)
    11. Особенности Android (см. Task 6.3)
    12. Тестирование (`flutter test`, integration_test)
    13. Troubleshooting (нет permission на location, не виден backend, sync не работает, и т. д.)
  - **Логи:** не требуются (docs)

- [ ] **Task 7.2: dependency injection map в README или architecture-section**
  - **Файлы:** `mobile/README.md` (или отдельно `mobile/docs/architecture.md` — на усмотрение реализатора)
  - **Что:** Краткая таблица: какой провайдер где определён, какие зависимости включает. Это помогает navigatable между файлами.
  - **Логи:** не требуются

- [ ] **Task 7.3: Integration-test happy-path**
  - **Файлы:** `mobile/integration_test/happy_path_test.dart`
  - **Что:** Тест на эмуляторе:
    1. Запустить приложение
    2. На LoginScreen ввести `admin@svetlyachok.local` / `admin12345`
    3. Дождаться перехода на ScanHome
    4. Подменить (через `ProviderContainer.overrideWith`) `WifiScanService` на FakeService возвращающий 3 сети
    5. Тапнуть «Снять отпечаток»
    6. Дождаться `pendingCount > 0`
    7. Подключиться (через mock Dio) — sync проходит, `pendingCount == 0`
  - **Логи:** integration-тест сам пишет в stdout, ничего дополнительного
  - **Зависимости:** все Phase 1-5 завершены
  - **Замечание:** Тест требует запущенного эмулятора и backend stub (или WireMock'а) — допустимо в дипломе пометить как опциональный, не блокировать вёрстку MVP

## Commit Plan

Большой план (24+ задач) — нужны промежуточные чекпоинт-коммиты. **Conventional Commits** + русский после префикса.

| # | После задач | Ветка | Сообщение коммита |
|---|-------------|-------|-------------------|
| 1 | 1.1, 1.2, 1.3 | scaffold | `feat(mobile): инициализация Flutter Android-проекта со скелетом core/app слоёв` |
| 2 | 2.1–2.6 | auth-data | `feat(mobile): auth слой — DTO, Dio interceptor с авто-refresh, secure storage и repository` |
| 3 | 2.7–2.9 | auth-ui | `feat(mobile): экраны login/splash + GoRouter с auth-guard` |
| 4 | 3.1–3.4 | wifi-cache | `feat(mobile): wifi сканирование с rate-limit Android 9+ и sqflite кэш отпечатков` |
| 5 | 3.5–3.8, 4.1–4.3 | sync | `feat(mobile): bulk sync через /fingerprints/batch с partial-success обработкой и UI индикатор` |
| 6 | 5.1–5.4 | calibration | `feat(mobile): admin-режим калибровки зон с UI gate по роли` |
| 7 | 6.1–6.3 | background | `feat(mobile): фоновое сканирование и sync через WorkManager` |
| 8 | 7.1–7.3 | docs | `docs(mobile): README с инструкцией сборки APK + integration test happy-path` |

После всех 8 коммитов — обновить ROADMAP.md (отметить веху `[x]`) отдельным коммитом по образцу предыдущих веx (это делает `/aif-implement` или вручную). PR на `main`.

## Принципы реализации

1. **Null safety strict** — никаких `!` без обоснования; все nullable поля явные. `late` только для late-inited через DI.
2. **Immutable state везде** — `freezed` для domain-моделей и view-state. `copyWith` для обновлений.
3. **Result-pattern** — все методы repository возвращают `Either<Failure, T>` (через dartz). Никаких `throw` через слои; исключения только внутри `data/api/` и сразу маппятся в `Failure`.
4. **Никаких `print`/`debugPrint`** — только `logger`-пакет с уровнями. Release-сборка автоматом фильтрует debug.
5. **Не логируем секреты** — никогда: пароли, access-token, refresh-token, raw response body с токенами. Только `correlation_id` (если backend начнёт его возвращать в headers — но для MVP пишем свои `client_request_id`).
6. **Timezone-aware datetime** — всегда `DateTime.now().toUtc()` или работа в UTC, ISO-8601 при сериализации. Backend режектит naive datetime.
7. **WorkManager Android 9+ throttling** — никаких попыток обойти лимиты; rate-limiter в `WifiScanService` гарантирует, что наш код не привысит. Period 15 минут — минимум для Periodic.
8. **DI через Riverpod, не GetIt** — провайдеры в `<feature>/providers.dart` или в файле фичи. `ref.read` в not-build, `ref.watch` в build. Тестируем через `ProviderContainer.overrideWith`.
9. **DTO ↔ Domain mapping** — DTO живут в `data/api/dto/`, домен в `domain/models/`. Маппинг — в Repository implementation (`fromDto()`/`toDto()` extension или фабричные методы DTO).
10. **Ни одного хардкода backend URL** — только через `Env.backendUrl` (compile-time от `--dart-define`). Default `http://10.0.2.2:8000` для эмулятора.
11. **Lint строгий** — `dart analyze` в pre-commit (опционально через `lefthook` или просто инструкция в README) — должно быть 0 warnings.
12. **Тестируем поведение, не реализацию** — view-model-тесты mock'ают repository (а не Dio); repository-тесты mock'ают Dio (а не HTTP-сервер).

## Открытые вопросы (на этапе реализации)

- **AccessToken refresh race** — реализовать через `Mutex` (пакет `synchronized` или ручной `Completer`). Допустимо в Task 2.4.
- **Workmanager + Riverpod isolate** — background isolate не имеет ProviderScope. Решено: ручная сборка DI в `callbackDispatcher`. Не пытаться шарить Riverpod-контейнер между изолятами.
- **`captured_at_too_old` после долгого офлайна** — если телефон был выключен > 7 дней с pending fingerprints, эти fingerprints окажутся в terminal-reject после первой попытки sync. Это OK — просто помечаем `sync_status=2`. Логируем `log.w` для диагностики.
- **iOS removal** — `flutter create --platforms=android` создаст без iOS-папок. Если понадобится потом — можно `flutter create --platforms=ios .` поверх. Но в рамках вехи — отключаем.
- **Splash + auto-refresh длительность** — если refresh-токен протух, splash зависнет на сети 30s. Решение: timeout в SplashScreen 5s → если currentUser ещё не определён → редирект на login.
