# Mobile АИС «Светлячок» — Flutter (Android-only)

Мобильное приложение для учёта посещаемости через Wi-Fi RSSI fingerprinting.
Сотрудник логинится, телефон периодически снимает RSSI-вектор и шлёт его на
backend; администратор использует тот же APK в admin-режиме для калибровки
зон. Без iOS, без production-инфраструктуры — пилот для дипломной работы.

## Стек

- **Flutter** 3.24+ (стабильно протестировано на 3.41.0), **Dart** 3.4+
- **Android-only** (`minSdk=24` Android 7.0, `targetSdk=35`)
- **State / DI:** Riverpod 2.x (`flutter_riverpod` + `riverpod_annotation` + `riverpod_generator`)
- **Models:** `freezed` + `json_serializable`
- **Network:** Dio + интерсепторы (auth-refresh, retry с экспоненциальным backoff)
- **Storage:** `flutter_secure_storage` (refresh-token), `shared_preferences` (access + meta), `sqflite` (локальный кэш отпечатков)
- **Wi-Fi:** `wifi_scan`, `permission_handler`, `connectivity_plus`
- **Background:** `workmanager` (15-минутные периодические задачи)
- **Routing:** `go_router`
- **Logging:** `logger` (никаких `print`/`debugPrint`)
- **Result-pattern:** `dartz` Either<Failure, T>

## Установка SDK

Проект использует **fvm** (Flutter Version Manager) — версия Flutter
зафиксирована в `.fvmrc`/глобальной конфигурации:

```bash
# Установить fvm (если ещё нет): https://fvm.app/documentation/getting-started/installation
fvm install 3.41.0      # один раз, при первой настройке окружения
fvm use 3.41.0          # переключить локально
fvm flutter doctor      # проверить toolchain
```

Также нужен **Android SDK 35+** (через Android Studio или standalone command-line tools)
и **ADB** для установки APK на устройство.

## Установка зависимостей

```bash
cd mobile
fvm flutter pub get
```

## Code generation (freezed / json_serializable / riverpod_generator)

После любых изменений в моделях (freezed/json_serializable) или провайдерах
(riverpod_generator) — перегенерировать:

```bash
fvm dart run build_runner build --delete-conflicting-outputs
```

Файлы `*.g.dart` и `*.freezed.dart` **коммитятся в git** (чтобы collaborators
не ставили build_runner локально и CI был детерминирован).

## Конфигурация BACKEND_URL

Адрес backend задаётся compile-time через `--dart-define`:

```bash
# Для Android-эмулятора (loopback к хосту через 10.0.2.2)
fvm flutter run --dart-define=BACKEND_URL=http://10.0.2.2:8000

# Для реального устройства (взять локальный IP компьютера через `ipconfig`)
fvm flutter run --dart-define=BACKEND_URL=http://192.168.x.y:8000
```

Дефолт (без `--dart-define`) — `http://10.0.2.2:8000`. Дополнительный флаг
`--dart-define=VERBOSE_HTTP=true` включает расширенное логирование Dio.

## Сборка release-APK

```bash
fvm flutter build apk --release \
  --dart-define=BACKEND_URL=http://192.168.x.y:8000
```

Артефакт: `mobile/build/app/outputs/flutter-apk/app-release.apk`.
Подписан debug-ключом (для пилотных полей этого хватает; production требует
свой signing config).

## Установка на устройство

```bash
adb install -r mobile/build/app/outputs/flutter-apk/app-release.apk
```

или скопировать APK на телефон и установить из проводника
(включить «Установка из неизвестных источников»).

## Архитектура

Layered (UI → Logic → Data) с Clean-Architecture-влиянием:

```
mobile/lib/
├── main.dart                    # Точка входа, ProviderScope
├── app/                         # MaterialApp.router, темы, GoRouter
├── core/                        # Cross-cutting: env, errors, result, logging
├── data/                        # API-клиент, локальное хранилище, repositories impl
│   ├── api/                     # Dio + interceptors + DTO + json_serializable
│   ├── local/                   # secure_storage, prefs, sqflite, DAO
│   ├── wifi/                    # wifi_scan + BSSID-нормализация + rate-limiter
│   └── repositories/            # реализации абстракций domain/repositories
├── domain/                      # Доменные модели и абстракции (Protocol-классы)
├── features/                    # Auth, Scanning, Calibration (admin), Settings
└── shared/                      # Виджеты + утилиты
```

Подробнее — в `.ai-factory/plans/mobile-prilozhenie-flutter-android.md`
и `.ai-factory/ARCHITECTURE.md`.

### DI map (Riverpod-провайдеры)

| Provider | Файл | Зависит от |
|----------|------|------------|
| `sharedPreferencesProvider` | `features/auth/providers.dart` | — (Future) |
| `prefsProvider` | `features/auth/providers.dart` | `sharedPreferencesProvider` |
| `secureStorageProvider` | `features/auth/providers.dart` | — |
| `dioProvider` | `features/auth/providers.dart` | `prefsProvider`, `secureStorageProvider` |
| `authRepositoryProvider` | `features/auth/providers.dart` | `dioProvider`, `prefsProvider`, `secureStorageProvider` |
| `currentUserProvider` | `features/auth/providers.dart` | `authRepositoryProvider`, `dioProvider` (AsyncNotifier) |
| `loginViewModelProvider` | `features/auth/view_models/login_view_model.dart` | `authRepositoryProvider`, `currentUserProvider` |
| `wifiScanServiceProvider` | `features/scanning/providers.dart` | — |
| `appDatabaseProvider` | `features/scanning/providers.dart` | — |
| `fingerprintCacheDaoProvider` | `features/scanning/providers.dart` | `appDatabaseProvider` |
| `connectivityCheckerProvider` | `features/scanning/providers.dart` | — |
| `fingerprintRepositoryProvider` | `features/scanning/providers.dart` | wifi/dao/dio/prefs/connectivity |
| `pendingFingerprintsCountProvider` | `features/scanning/providers.dart` | `fingerprintRepositoryProvider` |
| `scanningViewModelProvider` | `features/scanning/view_models/scanning_view_model.dart` | `fingerprintRepositoryProvider` |
| `syncStatusViewModelProvider` | `features/scanning/view_models/sync_status_view_model.dart` | `fingerprintRepositoryProvider` |
| `backgroundSchedulerProvider` | `features/scanning/providers.dart` | — |
| `backgroundLifecycleBindingProvider` | `features/scanning/providers.dart` | `currentUserProvider`, `backgroundSchedulerProvider` |
| `zoneRepositoryProvider` | `features/calibration/providers.dart` | `dioProvider` |
| `zonesProvider` | `features/calibration/providers.dart` | `zoneRepositoryProvider` (FutureProvider) |
| `calibrationRepositoryProvider` | `features/calibration/providers.dart` | wifi/dio/prefs |
| `calibrationCaptureProvider` | `features/calibration/view_models/calibration_view_model.dart` | `calibrationRepositoryProvider` (Family по zoneId) |
| `appRouterProvider` | `app/router.dart` | `currentUserProvider` (refreshListenable) |

Корневой `SvetlyachokApp` дополнительно `ref.watch(backgroundLifecycleBindingProvider)`,
чтобы автозапустить scheduler-binding после успешного login.

## Permissions

Запрашивает у пользователя:
- `ACCESS_FINE_LOCATION` — обязателен для получения BSSID/RSSI на Android 6+
- `ACCESS_BACKGROUND_LOCATION` — для фонового сканирования на Android 10+
- `ACCESS_WIFI_STATE`, `CHANGE_WIFI_STATE` — Wi-Fi сканирование
- `INTERNET`, `ACCESS_NETWORK_STATE` — связь с backend
- `WAKE_LOCK`, `RECEIVE_BOOT_COMPLETED` — устойчивость WorkManager-задач

При первом запуске приложение показывает explainer и системный диалог.
Если пользователь отказал permanently — кнопка «Открыть настройки».

## Особенности Android

- **Throttling Android 9+**: системное ограничение — не более 4 сканов
  за 2 минуты в foreground, ~1 скан в 30 минут для background. Ручной скан
  в UI ограничен 1 раз в 30 секунд (на стороне клиента); WorkManager
  периодика — 15 минут (минимум, который Android разрешит).
- **Doze / App Standby**: Android может откладывать background-задачи
  на час и более — это нормально, MVP не претендует на real-time tracking.
- **Battery optimization**: для надёжной работы фона — `Settings → Apps →
  Светлячок → Battery → Unrestricted`.

## Тестирование

```bash
# Анализ статически (lints, типизация)
fvm flutter analyze

# Unit + widget-тесты
fvm flutter test

# Integration-тесты (требуют запущенного эмулятора или подключённого устройства)
fvm flutter test integration_test
```

`analysis_options.yaml` строгий: `strict-casts`, `strict-inference`,
`strict-raw-types`, плюс набор `linter.rules` (см. файл).

## Troubleshooting

| Симптом | Что проверить |
|---------|----------------|
| `flutter doctor` ругается на Chrome | Игнорируем — мы Android-only |
| `flutter pub get` падает при `wifi_scan`/`workmanager` | Обновить Android SDK до 35; проверить `local.properties` |
| `INSUFFICIENT_PRIVILEGES` при сканах в эмуляторе | Эмулятор не показывает реальный Wi-Fi; тестировать на физическом устройстве |
| Backend не виден с устройства | IP компьютера, открытый порт `:8000`, отключённый firewall, `--dart-define=BACKEND_URL=...` правильный |
| `--dart-define` не применяется | Полный rebuild: `fvm flutter clean && fvm flutter pub get && fvm flutter run --dart-define=...` |
| Sync не работает в фоне | Включить «Unrestricted battery» в системных настройках устройства |
