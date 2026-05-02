# План: Web-панель администратора (React + Vite + TypeScript)

**Ветка (worktree):** `worktree-agent-a6c22dd3bb275812a` (изолирована вызывающим, новая ветка не создаётся)
**Создан:** 2026-05-02
**Mode:** full
**Целевая директория реализации:** `web/` (создаётся с нуля)

## Settings

- **Testing:** yes — Vitest + React Testing Library (component tests + интеграционные тесты UI с MSW); Playwright откладываем (не входит в эту веху, поднимем при появлении полевого E2E)
- **Logging:** verbose, но **структурный** — никаких `console.log` в production-коде. Логи через тонкую обёртку `lib/log.ts` (`log.debug`, `log.info`, `log.warn`, `log.error`); вывод в `console.*` ТОЛЬКО при `import.meta.env.DEV`. На продакшен (если когда-то будет) — `noop`. Все ошибки от axios interceptor и react-query идут через `log.warn`/`log.error` с `correlation_id` из RFC 7807.
- **Docs:** yes — `web/README.md` (как запустить, как сгенерировать типы из `/openapi.json`, как добавить новую фичу), краткие docstrings (TSDoc) для нетривиальных хелперов и хуков. Обновить шаг 4 в `.ai-factory/ROADMAP.md` → `docs/local-setup.md` (его создание — задача финальной вехи; здесь только проверяем, что инструкция `npm install && npm run dev` действительно работает).

## Roadmap Linkage

- **Milestone:** "Web-панель администратора (React + Vite + TypeScript)"
- **Rationale:** План реализует веху №10 ROADMAP.md — экраны auth, CRUD employees и zones, визуализация калибровочной радиокарты, отчёты по посещаемости. Backend (PR #9) полностью готов, все нужные эндпоинты задокументированы в `backend/README.md` и доступны через `/openapi.json`. Без production-build / Docker — только локальный `npm run dev` на `:5173`, как зафиксировано в шаге 4 «Локального запуска».

## Контекст и архитектурные решения

### Что уже есть на стороне backend

- FastAPI v1 эндпоинты (полный список в `backend/README.md`):
  - **Auth:** `POST /api/v1/auth/login`, `/refresh`, `/logout`. Access TTL 30 минут, refresh TTL 7 дней. Rate limit 5/min на login.
  - **Me:** `GET /api/v1/me` — возвращает `id`, `email`, `full_name`, `role`, `is_active`, `schedule_start/end`.
  - **Employees CRUD (admin):** create, list (с пагинацией `limit/offset` и фильтрами), get, patch, password (reset/change), deactivate, activate. `EmployeeResponse` без `hashed_password`.
  - **Zones CRUD:** GET — любой авторизованный (нужно для UI всех экранов), POST/PATCH/DELETE — admin. `display_color` валидируется regex `^#[0-9A-Fa-f]{6}$`.
  - **Calibration:** `POST /api/v1/calibration/points` (admin, инвалидирует ML-кэш), `GET /api/v1/calibration/points?zone_id=` (любой авторизованный), `DELETE` (admin).
  - **Fingerprints:** `GET /api/v1/fingerprints` и `GET /{id}` — admin (для дашборда «последние замеры»).
  - **Attendance:** `GET /api/v1/attendance` (фильтры: `employee_id`, `started_from`, `started_to`, `zone_id`, `status`, `limit`, `offset`); `GET /api/v1/attendance/summary` (`employee_id`, `from`, `to`).
- OpenAPI-схема публикуется по `GET /openapi.json` и `GET /docs` (Swagger).
- Все ошибки сервер возвращает в формате RFC 7807 (`type`, `title`, `status`, `detail`, `code`, `correlation_id`, опц. `errors[]`).
- CORS на backend (важная проверка перед стартом — см. Phase 2): `web/` и `backend/` запускаются на `localhost:5173` и `localhost:8000` соответственно. Если `CORS_ALLOW_ORIGINS` пока не настроен на backend под `http://localhost:5173`, в плане предусмотрен **smoke-чек** в Phase 2 (Task 2.1) и инструкция в `web/README.md` (но изменение backend-кода — за рамками этой вехи; если CORS не пропускает, ставим dev-proxy в Vite — см. ниже).

### Стек и обоснование

| Слой | Выбор | Почему именно так |
|------|-------|--------------------|
| **Bundler/dev** | Vite 5 | Уже зафиксирован в DESCRIPTION.md и ROADMAP («`npm run dev` на :5173»). Быстрый HMR; ESM из коробки; без webpack-зоопарка. |
| **Язык** | TypeScript 5.x, `strict: true` | Зафиксирован в base.md. Ловит ошибки типа `undefined.id` при работе с DTO от backend. |
| **UI-library** | React 18 | Зафиксирован в DESCRIPTION.md. Concurrent features (`<Suspense>`, `useTransition`) удобно сочетаются с TanStack Query. |
| **Server state** | **TanStack Query v5 (`@tanstack/react-query`)** | Зафиксирован в `rules/base.md` («Server state — TanStack Query»). Кэш с invalidation, автоматический retry, polling, mutations с onSuccess hooks; идеально для admin-CRUD. Альтернатива (Redux Toolkit Query) даёт тот же набор фич, но требует дополнительный slice-boilerplate. |
| **Client state** | **Zustand** (минимально) | Зафиксирован в `rules/base.md` («Zustand минимально»). Применяется ТОЛЬКО там, где TanStack Query не подходит: текущий пользователь (`useAuthStore`), глобальные UI-флаги (sidebar collapsed). Никаких бизнес-данных в Zustand — они в TanStack Query. |
| **Типы из API** | `openapi-typescript` v7 | Зафиксирован в `rules/base.md` («Клиенты генерируют типы через `openapi-typescript`»). Тянет `/openapi.json` и генерирует `web/src/api/schema.d.ts` с точными `paths`/`components`. Не путать с `openapi-fetch` (тоже допустим, но мы выберем минимальную обёртку — см. ниже). |
| **HTTP-клиент** | **axios** + **тонкая типизированная обёртка** | axios даёт interceptors (authRefresh, errorMapper), которые в `fetch` нужно писать руками. На уровне типов оборачиваем `axios.request<T>` в helper `apiFetch<P extends keyof paths>()`, который тянет тип ответа из сгенерированной OpenAPI-схемы. |
| **Форматирование/валидация форм** | `react-hook-form` + `zod` (через `@hookform/resolvers/zod`) | RHF — стандарт de-facto для admin-форм; декларативный, минимум rerender'ов. Zod даёт нам две вещи: (а) рантайм-валидация на клиенте; (б) **типы из zod-схем компилируются в TS-типы**, которые мы сравниваем с типами из `openapi-typescript` (если расходятся — сборка падает, что хорошо). |
| **Маршрутизация** | **React Router v6** (`react-router-dom`) | Зафиксирован в ARCHITECTURE.md и base.md (`web/src/routes/`). TanStack Router — мощнее, но overkill для пилота. v6 даёт `<Outlet>`, loaders/actions нам не нужны (используем TanStack Query). |
| **Стилизация** | **CSS Modules** | base.md: «CSS Modules или Tailwind — выбирается на этапе планирования». Выбираем **CSS Modules** — простой scoping без ребилда tailwind, без новой зависимости. На пилот хватит. Один глобальный файл `index.css` для CSS-переменных (тема, отступы) + `*.module.css` рядом с компонентами. |
| **Чарты** | **Recharts** | Самый простой среди serious-чартов. SVG, TypeScript-friendly, маленький bundle. Используем `BarChart` (work_hours по дням), `LineChart` (cumulative переработки). Альтернатива (Chart.js) — Canvas, требует ref-плёвое API, проигрывает на разработке. |
| **Toast/уведомления** | `react-hot-toast` | Минимальная зависимость для уведомлений «сохранено / ошибка». Используется как UI-сторона `errorMapper` (см. ниже). |
| **Иконки** | `lucide-react` | tree-shakable, типизированные, согласованные иконки для меню/кнопок. |
| **i18n** | **Без библиотеки** — литералы в коде, изолированы | На пилот русский UI; вводить i18next не оправдано. Все строки UI выносим в `web/src/i18n/ru.ts` (плоский объект с ключами `auth.login.title`, `employees.list.empty` и т. п.) и экспортируем `t(key)` без подстановки локали. Это даёт нам **единое место** для будущей миграции на i18next без правки компонентов. |
| **Иконки/семантика** | Семантические HTML-теги (`<button>`, `<nav>`, `<main>`, `<table>`), `aria-*` для нестандартных компонентов | base.md не запрещает; для admin-панели вуза доступность всё равно проверяют. |
| **Иммутабельные дата-операции** | `date-fns` | Только нужные функции (`format`, `parseISO`, `differenceInMinutes`). Альтернатива moment.js — не tree-shakable, deprecated. |

### Управление JWT — критическое решение

**Выбор:** **access** хранится в памяти (Zustand store, не сериализуется), **refresh** хранится в `localStorage`.

| Вариант | Плюсы | Минусы | Решение |
|---------|-------|--------|---------|
| access в памяти + refresh в `localStorage` | Простой клиент-сайд код. Бэкенд не меняется. На F5 через refresh восстанавливаем сессию. | XSS может стянуть refresh из localStorage. | **Берём для пилота** — backend не выставляет httpOnly cookie, и доделывать backend под cookie-based auth — за рамками этой вехи. CSP + отсутствие сторонних `<script>` минимизирует XSS-риск. |
| access + refresh оба в httpOnly cookie | Защита от XSS. | Требует backend-изменений (Set-Cookie + CSRF token), CORS с credentials, изменения rate-limit на login. | **Отказываемся** — backend этого не делает; добавление = breaking change. |
| Оба в localStorage | Простота. | Те же XSS-риски + access вечный до истечения. | Хуже первого варианта — отвергаем. |

**Поведение при F5:**

1. На старте `App.tsx` пытается прочитать `refresh_token` из `localStorage`.
2. Если есть — синхронно выставляем «загружаемся», делаем `POST /auth/refresh` через axios (но без interceptor'а, чтобы не зациклиться).
3. На успех — кладём новый access в Zustand, тянем `GET /me` для гидрации `currentUser`.
4. На ошибку (`401`/`invalid_token`) — стираем localStorage и редиректим на `/login`.

### Axios interceptor для авто-refresh

Один shared экземпляр `apiClient` (`web/src/api/client.ts`):

- **Request interceptor:** добавляет `Authorization: Bearer <access>` если access есть.
- **Response interceptor:** при `401 invalid_credentials` (и code из RFC 7807 `code: "token_expired"` либо `"invalid_token"`):
  1. Если запрос уже был retry — отдаём ошибку дальше (избегаем бесконечного цикла).
  2. Если нет access/refresh — отдаём ошибку.
  3. Иначе — ставим текущий запрос в очередь, дёргаем `POST /auth/refresh`, на успех обновляем access в Zustand и повторяем все запросы из очереди (single-flight refresh — только один параллельный refresh, остальные ждут промис).
  4. На неудачу refresh — очищаем токены, кидаем `AuthExpiredError`, редирект на `/login`.

**Почему single-flight:** при загрузке страницы TanStack Query параллельно дёргает 4-5 запросов (employees, zones, attendance). Если у access истёк TTL — все они получают 401 одновременно. Без single-flight будет 5 параллельных refresh-вызовов и backend rate limit (10/min) их положит.

### RFC 7807 → UI

Backend всегда возвращает ошибки как:
```json
{ "type": "about:blank", "title": "...", "status": 400, "detail": "...", "code": "validation_failed", "correlation_id": "...", "errors": [...] }
```

Парсер `web/src/api/errors.ts`:
- `parseProblemDetail(axiosError) -> { code, status, detail, correlationId, fieldErrors? }`
- Маппинг известных `code` → user-facing сообщение (на русском) в `lib/errorMessages.ts`, fallback — `detail`.
- На уровне UI:
  - **Toast** для общих ошибок («Не удалось сохранить сотрудника»).
  - **Inline под полем формы** для `validation_failed` с `errors[].field` через `setError` из react-hook-form.
  - **Banner** для `503 ml_*` ошибок calibration page (нечего классифицировать — мало точек).
- `correlation_id` логируется через `log.error("[api] ...", { correlationId, code, status })`.

### Feature-sliced layout (директории)

```
web/
├── src/
│   ├── main.tsx                      # entry: createRoot, QueryClientProvider, BrowserRouter
│   ├── App.tsx                       # корневые routes + AuthBootstrap (refresh при F5)
│   ├── api/                          # API-клиент, типы из OpenAPI, error-парсер
│   │   ├── client.ts                 # axios + interceptors
│   │   ├── schema.d.ts               # сгенерированный openapi-typescript (НЕ редактировать вручную)
│   │   ├── endpoints/                # типизированные обёртки для каждого ресурса
│   │   │   ├── auth.ts
│   │   │   ├── me.ts
│   │   │   ├── employees.ts
│   │   │   ├── zones.ts
│   │   │   ├── calibration.ts
│   │   │   ├── fingerprints.ts
│   │   │   └── attendance.ts
│   │   ├── errors.ts                 # parseProblemDetail, AuthExpiredError, NetworkError
│   │   └── queryKeys.ts              # фабрика TanStack Query key'ев (типизированная)
│   │
│   ├── features/                     # фичи по разделам admin-панели
│   │   ├── auth/
│   │   │   ├── LoginPage.tsx
│   │   │   ├── LoginForm.tsx
│   │   │   ├── useLoginMutation.ts
│   │   │   └── authStore.ts          # Zustand: access, currentUser, login(), logout()
│   │   ├── employees/
│   │   │   ├── EmployeesListPage.tsx
│   │   │   ├── EmployeeFormModal.tsx
│   │   │   ├── ChangePasswordModal.tsx
│   │   │   ├── DeactivateButton.tsx
│   │   │   ├── employeesQueries.ts   # useEmployeesQuery, useEmployeeQuery, и т. д.
│   │   │   ├── employeesMutations.ts # useCreateEmployee, useUpdateEmployee, ...
│   │   │   └── schema.ts             # zod-схемы create/update/changePassword
│   │   ├── zones/
│   │   │   ├── ZonesListPage.tsx
│   │   │   ├── ZoneFormModal.tsx
│   │   │   ├── DeleteZoneButton.tsx  # обработка 409 zone_in_use
│   │   │   ├── zonesQueries.ts
│   │   │   ├── zonesMutations.ts
│   │   │   └── schema.ts
│   │   ├── radiomap/
│   │   │   ├── RadiomapPage.tsx      # 2D-схема + список калибровочных точек
│   │   │   ├── RadiomapCanvas.tsx    # SVG-схема офиса с точками
│   │   │   ├── ZoneLegend.tsx
│   │   │   ├── CalibrationPointsTable.tsx
│   │   │   ├── DeleteCalibrationPointButton.tsx
│   │   │   ├── radiomapQueries.ts    # useCalibrationPointsQuery (с фильтром zone_id)
│   │   │   └── schema.ts
│   │   └── attendance/
│   │       ├── AttendanceDashboardPage.tsx     # «кто сейчас где»
│   │       ├── EmployeeAttendancePage.tsx      # детали по 1 сотруднику
│   │       ├── CurrentZoneTable.tsx            # таблица сотрудников + текущая зона (через GET /attendance с фильтром на открытые сессии)
│   │       ├── WorkHoursChart.tsx              # recharts BarChart по сотруднику за период
│   │       ├── LatenessOvertimeChart.tsx
│   │       ├── PeriodPicker.tsx
│   │       ├── attendanceQueries.ts
│   │       └── helpers.ts                      # формат "часы:минуты" из секунд, и т. п.
│   │
│   ├── components/                   # переиспользуемые UI-кирпичики
│   │   ├── Button.tsx
│   │   ├── Input.tsx
│   │   ├── Modal.tsx
│   │   ├── Table.tsx                 # обёртка над семантическим <table> + sorting/pagination props
│   │   ├── Pagination.tsx
│   │   ├── ColorChip.tsx             # маленький квадрат с display_color для зон
│   │   ├── EmptyState.tsx
│   │   ├── ErrorBanner.tsx
│   │   ├── ErrorBoundary.tsx         # фолбэк для критических React-ошибок
│   │   ├── LoadingSpinner.tsx
│   │   └── *.module.css
│   │
│   ├── hooks/                        # общие хуки
│   │   ├── useDebouncedValue.ts
│   │   ├── useRequireRole.ts         # навигационный guard (см. routes/)
│   │   └── useToast.ts               # обёртка над react-hot-toast
│   │
│   ├── lib/                          # утилиты, без React
│   │   ├── log.ts
│   │   ├── env.ts                    # читает import.meta.env с типизацией
│   │   ├── formatDate.ts
│   │   ├── formatDuration.ts         # секунды → "8 ч 32 мин"
│   │   └── errorMessages.ts          # mapping code → "message_ru"
│   │
│   ├── i18n/
│   │   └── ru.ts                     # плоский ключ-объект, t(key)
│   │
│   ├── routes/                       # React Router конфигурация
│   │   ├── AppRoutes.tsx
│   │   ├── PrivateRoute.tsx          # требует залогиненного
│   │   ├── AdminRoute.tsx            # требует role==admin
│   │   └── routes.ts                 # пути как const + типизированный helper toUrl()
│   │
│   ├── layout/
│   │   ├── AppShell.tsx              # боковая навигация + <Outlet>
│   │   ├── Sidebar.tsx
│   │   ├── Topbar.tsx                # текущий пользователь + кнопка «Выйти»
│   │   └── *.module.css
│   │
│   ├── styles/
│   │   ├── tokens.css                # CSS-переменные: цвета, отступы, размеры шрифтов
│   │   └── reset.css
│   │
│   └── types/
│       └── domain.ts                 # доменные алиасы поверх схемы (`Employee`, `Zone`, ...)
│
├── tests/
│   ├── setup.ts                      # настройка Vitest + JSDOM + mock-server
│   ├── msw/
│   │   ├── handlers.ts               # mock-handlers для всех endpoints
│   │   └── server.ts                 # setupServer
│   ├── components/                   # тесты компонентов
│   ├── features/                     # тесты фичей (LoginForm, EmployeeFormModal, ...)
│   └── api/
│       └── interceptor.test.ts       # тест auth-refresh interceptor'а
│
├── public/
│   └── office-floorplan.svg          # схема офиса для радиокарты (см. Phase 6)
│
├── index.html
├── package.json
├── tsconfig.json                     # strict, noUncheckedIndexedAccess, exactOptionalPropertyTypes
├── tsconfig.node.json
├── vite.config.ts                    # alias @/, dev-proxy /api → http://localhost:8000 (на случай CORS)
├── vitest.config.ts                  # JSDOM, setupFiles
├── .eslintrc.cjs                     # eslint-config + react + import + react-hooks
├── .prettierrc
└── README.md
```

### Маршруты (React Router v6)

```
/login                                 → LoginPage (public)
/                                      → RedirectToDashboard (private)
/employees                             → EmployeesListPage (admin)
/employees/new                         → EmployeesListPage с открытым модалом create (admin)
/employees/:id                         → EmployeesListPage с открытым модалом edit (admin)
/zones                                 → ZonesListPage (admin)
/radiomap                              → RadiomapPage (admin)
/attendance                            → AttendanceDashboardPage (admin)
/attendance/:employeeId                → EmployeeAttendancePage (admin)
*                                      → NotFoundPage
```

`PrivateRoute` проверяет `useAuthStore(s => s.currentUser !== null)`; `AdminRoute` дополнительно `role === 'admin'`. Если не авторизован → `<Navigate to="/login" replace>`. Если авторизован, но не admin → `<Navigate to="/" replace>` + toast «Доступ только для admin».

### Радиокарта (визуализация)

Нет встроенного API «координаты зоны», поэтому делаем простой подход для пилота:

1. **Статическая SVG-схема офиса** в `public/office-floorplan.svg` — упрощённый план с подписанными прямоугольниками-помещениями (учебный пример).
2. На странице `/radiomap` — `<RadiomapCanvas>` рисует фоновое SVG (`<image>`) и поверх него — точки калибровки.
3. Поскольку у `CalibrationPoint` (это `Fingerprint` с `is_calibration=true`) **нет координат на схеме** в backend (схема БД), для пилота используем подход:
   - Каждой зоне в UI ставим в соответствие центр прямоугольника на схеме — координаты задаём в JS-объекте `web/src/features/radiomap/zoneLayout.ts: Record<zone_id, { x, y, w, h }>`. Это **локальный конфиг для демо**; в полноценной системе появилась бы таблица `zones.coordinates` в БД. Для пилота этого достаточно — admin вручную сопоставит зоны с прямоугольниками после создания зон.
   - Точки калибровки рисуются маленькими кружочками внутри прямоугольника зоны, со смещением (`jitter`) от центра по индексу.
   - Цвет кружка = `zone.display_color` (если задан), иначе — палитра по `zone.type` (`workplace` синий, `corridor` серый, `meeting_room` зелёный, `outside_office` бордовый).
4. Hover на точке → popover с `captured_at`, `sample_count`, `BSSID count`. Click → красная иконка «удалить» (через `DELETE /calibration/points/{id}`).
5. Над схемой — фильтр «Зона» (select из `GET /zones`), легенда (`<ZoneLegend>`).
6. Сводный счётчик «X / Y зон откалибровано» (`Y` = все офисные `workplace + corridor + meeting_room`; `X` = у которых ≥ `MIN_CALIBRATION_POINTS_PER_ZONE = 3` точки в `GET /calibration/points`). Это даёт admin понять, готова ли система к классификации (соответствует backend-проверкам, которые поднимают `503` если калибровки мало).

> Примечание: «нарисовать SVG-фон вуза» — за рамками плана; кладём заглушку-SVG из 4 прямоугольников. Замена SVG на реальный план — задача после полевых испытаний.

### Дашборд посещаемости

**Главная страница `/attendance` (CurrentZoneTable + сводка):**

- Таблица:
  | Сотрудник | Email | Текущая зона | С какого времени | work_hours сегодня | Статус |
- «Текущая зона» = находим открытую сессию (`ended_at IS NULL`) для каждого сотрудника. Backend пока не даёт «открытые сессии bulk», поэтому стратегия:
  1. `useEmployeesQuery({ limit: 100 })` — получаем список.
  2. Для каждого employee — `useAttendanceQuery({ employee_id, started_from: startOfDay, limit: 1, offset: 0 })`. Сортировка по `started_at DESC` на backend → первая запись либо открытая, либо последняя закрытая сегодня.
  3. **Альтернатива (если 50 сотрудников × 1 запрос станет тяжко):** на этой вехе оставляем как есть, оптимизация — отложенная задача. Для пилота 50 сотрудников × `limit:1` — это 50 запросов, которые TanStack Query кэширует на 30 секунд (см. ниже).
- В `useAttendanceQuery` ставим `refetchInterval: 30_000` — обновляем «кто где» каждые 30 секунд.

**Страница сотрудника `/attendance/:employeeId`:**

- `<PeriodPicker>` — пресеты «сегодня / неделя / месяц» + custom date range.
- `<WorkHoursChart>` — bar chart часов по дням (через `GET /attendance/summary` с шагом 1 день и группировкой на клиенте по `started_at`).
- `<LatenessOvertimeChart>` — две линии (lateness_count и overtime_seconds) по дням.
- Таблица сессий: `started_at`, `ended_at`, длительность, зона, статус.
- Кнопка «Сменить пароль» (admin-reset-режим — без `old_password`).

### Формы CRUD: zod + react-hook-form

Каждая фича имеет `schema.ts` с zod-схемами. Пример для employees:

```ts
// web/src/features/employees/schema.ts
import { z } from "zod";

export const employeeCreateSchema = z.object({
  email: z.string().email(),
  full_name: z.string().min(1).max(255),
  role: z.enum(["admin", "employee"]),
  initial_password: z.string().min(8).max(128),
  schedule_start: z.string().regex(/^\d{2}:\d{2}$/).optional(),
  schedule_end: z.string().regex(/^\d{2}:\d{2}$/).optional(),
});
export type EmployeeCreateInput = z.infer<typeof employeeCreateSchema>;
```

В `EmployeeFormModal.tsx` подключаем через `useForm({ resolver: zodResolver(employeeCreateSchema) })`. На submit — мутация `useCreateEmployee()`. Серверные `validation_failed.errors` мапим в `setError("email", ...)` и т. п.

### Точки боли и принятые решения

1. **Нет «текущая зона сотрудника» в одном запросе.** Решение — N×1 запросов с TanStack Query polling (см. выше). Если станет проблемой — backend-задача `GET /attendance/current` (отложена).
2. **Нет координат зон.** Решение — локальный `zoneLayout.ts` (см. «Радиокарта»).
3. **CORS.** Если backend не пропускает `localhost:5173`, в `vite.config.ts` ставим dev-proxy `/api → http://localhost:8000` — браузер видит запросы как same-origin. Это **default-стратегия** (всегда включаем proxy в dev).
4. **Время на клиенте — UTC.** Backend ожидает ISO-8601 с `Z`. Все datetime-поля сериализуем через `new Date(...).toISOString()`. Отображение — через `date-fns.format(date, "dd.MM.yyyy HH:mm", { timeZone: "Europe/Moscow" })` (или системный TZ через `Intl.DateTimeFormat`). Зафиксировано в `lib/formatDate.ts`.
5. **`schedule_start/end`** на backend это `time` (`HH:MM:SS`), на форме храним `HH:MM`. На submit добавляем `:00` секунды; на read — отрезаем.
6. **`schedule` clear-флаги** (`clear_schedule_start: true` в PATCH). На UI — отдельный чекбокс «Без расписания» в форме edit; если включён — submit отправляет `clear_schedule_start: true, clear_schedule_end: true` без значений полей.
7. **`extra="forbid"` на бэке.** Любое лишнее поле в request body → 422. Поэтому формы строим строго по zod-схеме, в `apiFetch<P>()` тип запроса — из схемы, опечатка в ключе ловится TS на компиляции.

## Tasks

### Phase 1: Scaffold проекта

- [ ] **Task 1.1: Инициализация Vite + TypeScript**
  - **Файлы:** `web/package.json`, `web/tsconfig.json`, `web/tsconfig.node.json`, `web/vite.config.ts`, `web/index.html`, `web/src/main.tsx`, `web/src/App.tsx`, `web/.gitignore`, `web/.prettierrc`, `web/.eslintrc.cjs`
  - **Что:**
    - `npm create vite@latest . -- --template react-ts` (выполняет разработчик; задача описывает результат: Vite 5 + React 18 + TS 5).
    - В `tsconfig.json` включить: `"strict": true`, `"noUncheckedIndexedAccess": true`, `"exactOptionalPropertyTypes": true`, `"noUnusedLocals": true`, `"noUnusedParameters": true`, `"forceConsistentCasingInFileNames": true`, `"target": "ES2022"`, `"module": "ESNext"`, `"moduleResolution": "Bundler"`, `"jsx": "react-jsx"`, `"baseUrl": "."`, `"paths": { "@/*": ["src/*"] }`.
    - `vite.config.ts`: alias `@` → `src/`, `server.port: 5173`, `server.proxy: { "/api": "http://localhost:8000" }` — dev-proxy чтобы избежать CORS.
    - ESLint: `@typescript-eslint`, `eslint-plugin-react`, `eslint-plugin-react-hooks`, `eslint-plugin-import`. Правило `no-console: error` (исключения через `// eslint-disable-next-line` запрещены — все логи через `lib/log.ts`).
    - Prettier: 2 пробела, semi: true, singleQuote: false (двойные — стандарт TS).
    - `.gitignore`: `node_modules/`, `dist/`, `*.local`, `.env.local`, `coverage/`, `src/api/schema.d.ts` (генерируется).
  - **Логи:** N/A (сборка).
  - **Готово, когда:** `npm run dev` поднимает Vite на 5173, `npm run build` собирает без ошибок, `npm run lint` проходит.

- [ ] **Task 1.2: Зависимости и npm-скрипты**
  - **Файлы:** `web/package.json`
  - **Что:** В `dependencies` добавить: `react`, `react-dom`, `react-router-dom@^6`, `@tanstack/react-query@^5`, `axios`, `zustand`, `react-hook-form`, `@hookform/resolvers`, `zod`, `date-fns`, `recharts`, `react-hot-toast`, `lucide-react`. В `devDependencies`: `vitest`, `@testing-library/react`, `@testing-library/jest-dom`, `@testing-library/user-event`, `jsdom`, `msw`, `openapi-typescript`, `@types/react`, `@types/react-dom`, `@vitejs/plugin-react`, `typescript`, `eslint`, `prettier`, `@typescript-eslint/parser`, `@typescript-eslint/eslint-plugin`.
  - **npm-скрипты:** `dev`, `build`, `preview`, `lint`, `lint:fix`, `format`, `test`, `test:watch`, `test:cov`, `typecheck` (`tsc --noEmit`), `gen:api` (`openapi-typescript http://localhost:8000/openapi.json -o src/api/schema.d.ts`).
  - **Логи:** N/A.
  - **Готово, когда:** `npm install` без warnings (кроме peerDeps), все скрипты реестрируются.

- [ ] **Task 1.3: Базовые стили и tokens**
  - **Файлы:** `web/src/styles/tokens.css`, `web/src/styles/reset.css`, `web/src/index.css`
  - **Что:** В `tokens.css` — CSS-переменные: цвета (`--color-bg`, `--color-fg`, `--color-primary`, `--color-danger`, `--color-success`, `--color-zone-workplace`, `--color-zone-corridor`, `--color-zone-meeting`, `--color-zone-outside`), отступы (`--space-1` … `--space-8`), радиус (`--radius-sm/md/lg`), шрифт (`--font-sans` = system-ui stack). Тёмную тему НЕ делаем (пилот). `reset.css` — простой box-sizing reset + base font. `index.css` импортирует tokens + reset, задаёт `body { font-family: var(--font-sans); ... }`. Импортируется в `main.tsx`.
  - **Логи:** N/A.

- [ ] **Task 1.4: Утилита логирования**
  - **Файлы:** `web/src/lib/log.ts`
  - **Что:** Экспортирует `log` со связкой `debug/info/warn/error`. В `import.meta.env.DEV` пишет в `console.*` с префиксом `[svetlyachok]`; в production — no-op. Сигнатура: `log.info("[area.action] msg", { ...kv })`. Поля автоматически добавляются в JSON.stringify для удобного чтения.
  - **Логи:** сам файл — реализация логгера.

- [ ] **Task 1.5: Env-конфиг и helper**
  - **Файлы:** `web/src/lib/env.ts`, `web/.env.example`, `web/src/vite-env.d.ts`
  - **Что:** `vite-env.d.ts` декларирует `interface ImportMetaEnv { VITE_API_BASE_URL: string }`. `env.ts` читает `import.meta.env.VITE_API_BASE_URL` (default `"/api"` — попадает в dev-proxy). `.env.example`: `VITE_API_BASE_URL=/api`.
  - **Логи:** `log.debug("[env] loaded", { VITE_API_BASE_URL })` при импорте.

### Phase 2: API client + типы из OpenAPI

- [ ] **Task 2.1: Smoke-чек backend и проверка CORS/proxy**
  - **Файлы:** N/A (ручная проверка с записью в `web/README.md` шага «Перед стартом»).
  - **Что:** Документируем в README, что перед `npm run gen:api` backend должен быть запущен (`uvicorn` на 8000). Проверяем `curl http://localhost:8000/openapi.json` возвращает 200. Проверяем, что dev-proxy в `vite.config.ts` пропускает запрос `fetch("/api/v1/health")` из браузера. Если backend ОТКЛЮЧАЕТ CORS для localhost:5173 (что стандартно), proxy решает проблему — задача задокументировать это.
  - **Логи:** N/A.
  - **Готово, когда:** в README есть раздел «Backend prerequisites» с командами проверки.

- [ ] **Task 2.2: Генерация типов из OpenAPI**
  - **Файлы:** `web/src/api/schema.d.ts` (сгенерированный, в `.gitignore`), npm-скрипт `gen:api` (см. Task 1.2)
  - **Что:** Запустить `npm run gen:api` → получить `schema.d.ts`. Добавить `gen:api` в pre-push hook (опционально) или в CI; на этой вехе достаточно ручного запуска перед `npm run build` (документируем в README). `schema.d.ts` экспортирует `paths`, `components`, `operations` — типы наших DTO.
  - **Логи:** N/A.

- [ ] **Task 2.3: axios-клиент и типизированный helper**
  - **Файлы:** `web/src/api/client.ts`, `web/src/api/types.ts`
  - **Что:**
    - `client.ts`: `axios.create({ baseURL: env.VITE_API_BASE_URL, headers: { "Content-Type": "application/json" } })`. Экспортирует `apiClient: AxiosInstance`. **Без interceptors на этом шаге** — добавим в Task 3.x.
    - `types.ts`: helper `type ApiResponse<P, M> = paths[P]["responses"]["200"]["content"]["application/json"]` и аналогичный для `RequestBody`. Цель — чтобы вызовы `apiClient.get<ApiResponse<"/api/v1/zones", "get">>(...)` были полностью типизированы.
  - **Логи:** `log.debug("[api.client] request", { method, url })` через interceptor (добавим в Task 3.x).

- [ ] **Task 2.4: Парсер RFC 7807 + классы ошибок**
  - **Файлы:** `web/src/api/errors.ts`, `web/src/lib/errorMessages.ts`
  - **Что:**
    - `errors.ts`: `class ApiError extends Error { code; status; correlationId; detail; fieldErrors? }`. `class AuthExpiredError extends ApiError`. `class NetworkError extends Error`. Функция `parseProblemDetail(error: unknown): ApiError | NetworkError` — узнаёт `AxiosError`, читает `response.data.code/detail/correlation_id/errors`, возвращает структурированный объект.
    - `errorMessages.ts`: `Record<code, string>` — переводы известных code на русский: `invalid_credentials → "Неверный email или пароль"`, `validation_failed → "Проверьте введённые данные"`, `zone_in_use → "Нельзя удалить: на зону ссылаются записи учёта"`, `not_a_calibration_point → "Эта точка не является калибровочной"`, `empty_calibration_set/insufficient_calibration_points/missing_zone_types → "Для классификации недостаточно калибровочных точек"`, `attendance_self_only → "Доступ только к собственным данным"`, `captured_at_in_future/captured_at_too_old → "..."`, fallback — `"Ошибка сервера. Попробуйте позже."`.
    - Хелпер `getErrorMessage(error: unknown): string`.
  - **Логи:** при `parseProblemDetail` — `log.warn("[api.error] parsed", { code, status, correlationId })`.

- [ ] **Task 2.5: Endpoint-обёртки**
  - **Файлы:** `web/src/api/endpoints/auth.ts`, `me.ts`, `employees.ts`, `zones.ts`, `calibration.ts`, `fingerprints.ts`, `attendance.ts`
  - **Что:** На каждый ресурс — модуль с типизированными функциями `login(req)`, `refresh(req)`, `logout()`, `getMe()`, `listEmployees(params)`, `createEmployee(req)`, `updateEmployee(id, patch)`, `setEmployeePassword(id, req)`, `deactivateEmployee(id)`, `activateEmployee(id)`, `listZones()`, `getZone(id)`, `createZone(req)`, `updateZone(id, patch)`, `deleteZone(id)`, `listCalibrationPoints(zoneId?)`, `createCalibrationPoint(req)`, `deleteCalibrationPoint(id)`, `listFingerprints(params)`, `getFingerprint(id)`, `listAttendance(params)`, `getAttendanceSummary(params)`. Каждая возвращает `Promise<DTO>` где DTO — тип из `schema.d.ts`.
  - **Логи:** `log.debug("[api.<resource>.<op>] start", params)` на входе, `log.debug("[api.<resource>.<op>] done", { took })` на выходе.

- [ ] **Task 2.6: queryKeys фабрика**
  - **Файлы:** `web/src/api/queryKeys.ts`
  - **Что:** Типизированный builder `qk.employees.list(filters)`, `qk.employees.detail(id)`, `qk.zones.list()`, `qk.zones.detail(id)`, `qk.calibration.list(zoneId)`, `qk.attendance.list(filters)`, `qk.attendance.summary(employeeId, range)`, `qk.me()`. Возвращает `readonly [string, ...]`. Используется в `useQuery({ queryKey: qk.employees.list(...), ... })` и `queryClient.invalidateQueries({ queryKey: qk.employees._all })`.
  - **Логи:** N/A.

### Phase 2.5: Vitest + MSW infrastructure

- [ ] **Task 2.7: Vitest + JSDOM + MSW setup**
  - **Файлы:** `web/vitest.config.ts`, `web/tests/setup.ts`, `web/tests/msw/server.ts`, `web/tests/msw/handlers.ts`
  - **Что:**
    - `vitest.config.ts`: `environment: "jsdom"`, `setupFiles: ["./tests/setup.ts"]`, `globals: true`, alias `@` → `src/`, `coverage: { provider: "v8", reporter: ["text", "html"] }`.
    - `tests/setup.ts`: импортирует `@testing-library/jest-dom`, поднимает MSW (`server.listen({ onUnhandledRequest: "error" })` в `beforeAll`, `server.resetHandlers()` в `afterEach`, `server.close()` в `afterAll`). Также мокает `localStorage` и сбрасывает Zustand store между тестами.
    - `tests/msw/server.ts`: `setupServer(...handlers)`.
    - `tests/msw/handlers.ts`: handler'ы для всех endpoint'ов (`POST /api/v1/auth/login`, `POST /auth/refresh`, `GET /me`, employees CRUD, zones CRUD, calibration list/delete, attendance list/summary). По умолчанию каждый возвращает «happy path» с фиксированными фикстурами; в каждом тесте — `server.use(http.get(...).respondWith(...))` для override (например, 401, 409, 503).
  - **Логи:** N/A.
  - **Готово, когда:** `npm test` запускает пустой набор тестов без ошибок setup.

### Phase 3: Auth state, login screen, layout

- [ ] **Task 3.1: Zustand authStore**
  - **Файлы:** `web/src/features/auth/authStore.ts`
  - **Что:** Store с полями `accessToken: string | null`, `refreshToken: string | null` (читается/пишется в localStorage), `currentUser: CurrentUserResponse | null`, `status: "idle" | "loading" | "authenticated" | "anonymous"`. Методы: `login({email, password})`, `logout()` (вызывает `POST /auth/logout` — best-effort, errors глотаются — потом стирает локально), `bootstrapFromRefresh()` (на старте), `setAccessToken(token)`. **Не сериализуется в localStorage целиком** — только refresh пишется отдельно через `localStorage.setItem("svetlyachok.refresh", ...)`; access живёт в памяти.
  - **Логи:** `log.info("[auth.login] success", { userId, role })`, `log.info("[auth.logout] cleared")`, `log.warn("[auth.bootstrap] refresh_failed", { code })`, `log.debug("[auth.setAccessToken] updated", { ttl })`.
  - **Тесты:** `tests/features/auth/authStore.test.ts` — login успех/неуспех, logout стирает refresh из localStorage, bootstrap при отсутствии refresh не делает ничего.

- [ ] **Task 3.2: Axios interceptors + single-flight refresh**
  - **Файлы:** `web/src/api/client.ts` (расширение), `web/src/api/refreshSingleflight.ts`
  - **Что:**
    - Request interceptor: добавляет `Authorization: Bearer <access>` если `useAuthStore.getState().accessToken` есть. **Не на /auth/login и /auth/refresh** (исключение по url).
    - Response interceptor: при 401 + `code === "token_expired"|"invalid_token"` (читаем через `parseProblemDetail`) и `!config._retry`:
      1. Set `config._retry = true`.
      2. Через `refreshSingleflight.ts` — `singletonPromise = singletonPromise || performRefresh()`. Все одновременные 401 ждут один промис.
      3. На успех — обновляем access в Zustand, перезапускаем оригинальный запрос.
      4. На неудачу — `useAuthStore.getState().logout()`, кидаем `AuthExpiredError`. Глобальный listener в `App.tsx` редиректит на `/login`.
  - **Логи:** `log.warn("[api.refresh] triggered", { originalUrl })`, `log.info("[api.refresh] success")`, `log.error("[api.refresh] failed", { code, correlationId })`.
  - **Тесты:** `tests/api/interceptor.test.ts` через MSW: (а) 401 → refresh → retry успех; (б) одновременные 5 запросов на 401 — единственный refresh-вызов; (в) refresh упал — `AuthExpiredError`.

- [ ] **Task 3.3: TanStack Query Provider + ErrorBoundary**
  - **Файлы:** `web/src/main.tsx`, `web/src/App.tsx`, `web/src/components/ErrorBoundary.tsx`
  - **Что:**
    - `main.tsx`: создаёт `QueryClient` с `defaultOptions: { queries: { staleTime: 30_000, retry: (count, error) => !(error instanceof AuthExpiredError) && count < 2, refetchOnWindowFocus: false } }`. Оборачивает `<App>` в `<QueryClientProvider>`, `<BrowserRouter>`, `<Toaster>` (react-hot-toast).
    - `App.tsx`: на mount вызывает `useAuthStore.getState().bootstrapFromRefresh()`; пока `status === "loading"` — `<LoadingSpinner>`; иначе рендерит `<AppRoutes>`.
    - `ErrorBoundary.tsx`: классовый компонент, fallback — `<ErrorBanner title="Что-то сломалось" detail={error.message}>`. Используется в `<AppShell>` (см. Phase 3.5).
  - **Логи:** `log.error("[ErrorBoundary] caught", { error, componentStack })`.

- [ ] **Task 3.4: Login screen**
  - **Файлы:** `web/src/features/auth/LoginPage.tsx`, `LoginForm.tsx`, `useLoginMutation.ts`, `web/src/features/auth/schema.ts`, `*.module.css`
  - **Что:**
    - `schema.ts`: zod `loginSchema = z.object({ email: z.string().email(), password: z.string().min(1) })`.
    - `LoginForm.tsx`: react-hook-form + zodResolver. Поля email + password. Кнопка «Войти», disabled при loading. Отображение `getErrorMessage(error)` под формой при ошибке.
    - `useLoginMutation.ts`: `useMutation({ mutationFn: authApi.login, onSuccess: ({access, refresh}) => authStore.setTokens(...); navigate("/") })`.
    - `LoginPage.tsx`: центрированная карточка, лого («Светлячок»), `<LoginForm>`. Если `currentUser !== null` — `<Navigate to="/" replace>`.
  - **Логи:** `log.info("[auth.login.submit] start", { email })`, успех/неуспех уже логирует authStore.
  - **Тесты:** `tests/features/auth/LoginForm.test.tsx` — пустой email → inline-ошибка; submit → mock-ответ → navigate вызван; 401 → отображается «Неверный email или пароль».

- [ ] **Task 3.5: Layout (AppShell, Sidebar, Topbar)**
  - **Файлы:** `web/src/layout/AppShell.tsx`, `Sidebar.tsx`, `Topbar.tsx`, `*.module.css`
  - **Что:**
    - `AppShell` оборачивает `<Outlet>` в grid: левый sidebar 240px + content. Внутри `<ErrorBoundary>`.
    - `Sidebar`: ссылки (`<NavLink>`) на «Сотрудники», «Зоны», «Радиокарта», «Учёт времени». Активная подсветка через NavLink className. Иконки из `lucide-react`.
    - `Topbar`: справа — `currentUser.full_name`, dropdown «Выйти» (вызывает `authStore.logout()` → `<Navigate to="/login">`).
  - **Логи:** `log.debug("[layout.logout] click")`.

- [ ] **Task 3.6: Routes + guards**
  - **Файлы:** `web/src/routes/AppRoutes.tsx`, `PrivateRoute.tsx`, `AdminRoute.tsx`, `routes.ts`
  - **Что:**
    - `routes.ts`: `export const ROUTES = { login: "/login", home: "/", employees: "/employees", ..., notFound: "*" } as const;` + helper `toEmployeeUrl(id)`.
    - `PrivateRoute`: читает `currentUser` из authStore; если нет — `<Navigate to={ROUTES.login}>`; иначе `<Outlet>`.
    - `AdminRoute`: вложенный, проверяет `role === "admin"`; иначе `<Navigate to={ROUTES.home}>` + `toast.error("Доступ только для admin")`.
    - `AppRoutes`: дерево `<Routes>` со всеми путями (см. секцию «Маршруты» выше). `/` редиректит на `/attendance` (главный экран admin).
  - **Логи:** `log.debug("[routes] guard.deny", { route, reason })`.
  - **Тесты:** `tests/routes/PrivateRoute.test.tsx` — без currentUser → редирект на /login; `tests/routes/AdminRoute.test.tsx` — role=employee → редирект.

### Phase 4: Employees CRUD

- [ ] **Task 4.1: Queries и мутации**
  - **Файлы:** `web/src/features/employees/employeesQueries.ts`, `employeesMutations.ts`
  - **Что:**
    - `useEmployeesQuery({ limit, offset, search, role, is_active })` через `employeesApi.list`.
    - `useEmployeeQuery(id)`, enabled если id есть.
    - `useCreateEmployee()` с `onSuccess` → `queryClient.invalidateQueries({ queryKey: qk.employees._all }); toast.success("Сотрудник создан")`.
    - `useUpdateEmployee(id)`, `useDeactivateEmployee(id)`, `useActivateEmployee(id)`, `useChangePassword(id)` — все с invalidation и toast.
    - На ошибку — `toast.error(getErrorMessage(error))`.
  - **Логи:** `log.info("[employees.create] success", { id, email })`, аналогично для update/deactivate.

- [ ] **Task 4.2: Zod-схемы и форма**
  - **Файлы:** `web/src/features/employees/schema.ts`, `EmployeeFormModal.tsx`, `*.module.css`
  - **Что:**
    - `schema.ts`: `employeeCreateSchema`, `employeeUpdateSchema` (все поля optional), `changePasswordSchema` (`new_password.min(8)`, `old_password.optional()`). Кросс-валидация: `schedule_end > schedule_start` если оба заданы.
    - `EmployeeFormModal.tsx`: модалка через `<Modal>`. Поля: email (только в create), full_name, role select, schedule_start/end (`<input type="time">`), чекбокс «Очистить расписание» (только в edit). Кнопки «Сохранить» / «Отмена». На submit — соответствующая мутация. Отображение field-errors из validation_failed.
  - **Логи:** `log.debug("[employees.form.submit]", { mode })`.
  - **Тесты:** `tests/features/employees/EmployeeFormModal.test.tsx` — успешный create, валидация email, server validation_failed → setError.

- [ ] **Task 4.3: Список сотрудников**
  - **Файлы:** `web/src/features/employees/EmployeesListPage.tsx`, `*.module.css`, `web/src/components/Pagination.tsx`, `Table.tsx`, `EmptyState.tsx`
  - **Что:**
    - Таблица: ID, full_name, email, role, расписание (`HH:MM-HH:MM`), статус (active/inactive с `<ColorChip>`), действия (Edit, Deactivate/Activate, ChangePassword).
    - Над таблицей: search-input (debounced 300ms), select role, select active, кнопка «+ Сотрудник».
    - `<Pagination>` снизу (limit=20, offset через useState).
    - `<EmptyState>` если нет результатов.
    - Edit / ChangePassword открывают модалки. Deactivate показывает `<ConfirmModal>` («Деактивировать сотрудника? Он не сможет логиниться»).
    - Защита: admin не видит кнопку Deactivate напротив самого себя (anti-self-lock backend всё равно вернёт 400, но UX — лучше скрыть).
  - **Логи:** `log.debug("[employees.list] mounted", { filters })`.
  - **Тесты:** `tests/features/employees/EmployeesListPage.test.tsx` — рендер с MSW handler возвращает 3 сотрудников; нажатие «Деактивировать» вызывает confirm и мутацию.

- [ ] **Task 4.4: Смена пароля**
  - **Файлы:** `web/src/features/employees/ChangePasswordModal.tsx`
  - **Что:** Отдельная модалка. Если admin меняет ЧУЖОЙ пароль — `old_password` поле скрыто, отправляется без него (admin-reset). Если admin меняет СВОЙ или employee себя — `old_password` обязателен (но эту вторую ветку для self в admin-панели не используем, только admin reset; на всякий случай поле есть). После успеха — toast «Пароль обновлён».
  - **Логи:** `log.info("[employees.password.changed]", { id, mode: "admin_reset"|"self" })`.

### Phase 5: Zones CRUD

- [ ] **Task 5.1: Queries и мутации**
  - **Файлы:** `web/src/features/zones/zonesQueries.ts`, `zonesMutations.ts`
  - **Что:** `useZonesQuery()` (без пагинации — пилотных зон ≤ 20), `useZoneQuery(id)`, `useCreateZone`, `useUpdateZone`, `useDeleteZone` (с обработкой 409 `zone_in_use` → toast «Нельзя удалить: на зону ссылаются записи учёта»). Invalidation: `qk.zones._all` + `qk.calibration._all` (если зона удалена — её точки тоже не показываем).
  - **Логи:** `log.info("[zones.<op>] success", { id })`.

- [ ] **Task 5.2: Zod-схемы и форма зоны**
  - **Файлы:** `web/src/features/zones/schema.ts`, `ZoneFormModal.tsx`, `*.module.css`
  - **Что:**
    - `schema.ts`: `zoneCreateSchema = z.object({ name: z.string().min(1).max(100), type: z.enum(["workplace","corridor","meeting_room","outside_office"]), description: z.string().max(500).nullable(), display_color: z.string().regex(/^#[0-9A-Fa-f]{6}$/).nullable() })`.
    - `ZoneFormModal.tsx`: поля name, select type (с локализацией: «Рабочее место» / «Коридор» / «Переговорная» / «Вне офиса»), textarea description, color-picker (`<input type="color">` + поле для ручного ввода HEX; синхронизация). Чекбоксы `clear_description`, `clear_display_color` в edit.
  - **Логи:** `log.debug("[zones.form.submit]", { mode })`.

- [ ] **Task 5.3: Список зон**
  - **Файлы:** `web/src/features/zones/ZonesListPage.tsx`, `DeleteZoneButton.tsx`
  - **Что:** Таблица: name, type, description, цветной чип `display_color`, действия Edit/Delete. Над таблицей — кнопка «+ Зона». `<DeleteZoneButton>`: confirm-модалка → мутация → если 409 — toast с подсказкой «удалите связанные attendance_logs» (для пилота — переименовать зону).
  - **Логи:** `log.warn("[zones.delete] in_use", { id })` при 409.
  - **Тесты:** `tests/features/zones/ZonesListPage.test.tsx` — DELETE возвращает 409 → toast с правильным текстом.

### Phase 6: Калибровочная радиокарта

- [ ] **Task 6.1: SVG-фон офиса (заглушка)**
  - **Файлы:** `web/public/office-floorplan.svg`
  - **Что:** Создать упрощённую SVG (1200×800) с 4 прямоугольниками для типовых зон (workplace × 2, corridor, meeting_room) и подписями. Это **демо-заглушка**; admin позже заменит на реальный план вуза.
  - **Логи:** N/A.

- [ ] **Task 6.2: zoneLayout config**
  - **Файлы:** `web/src/features/radiomap/zoneLayout.ts`
  - **Что:** `Record<zoneId, { x, y, w, h, label }>`. Для пилота — фиксированные координаты под 4 заглушечных зоны seed'а (`scripts/seed.py` создаёт 4 зоны). Если зон в БД больше — рисуем «без координат: задайте zoneLayout вручную» (placeholder под схемой). Документируем в README, как добавить новые зоны в layout.
  - **Логи:** N/A.

- [ ] **Task 6.3: Queries для калибровки**
  - **Файлы:** `web/src/features/radiomap/radiomapQueries.ts`, `radiomapMutations.ts`
  - **Что:** `useCalibrationPointsQuery(zoneId?)`, `useDeleteCalibrationPoint()` с invalidation `qk.calibration._all`. Создание точек НЕ через web (это делает mobile-приложение в режиме калибровки) — но опционально добавим `useCreateCalibrationPoint` для будущего «ручного ввода» admin'ом.
  - **Логи:** `log.info("[calibration.delete]", { id })`.

- [ ] **Task 6.4: RadiomapCanvas (SVG)**
  - **Файлы:** `web/src/features/radiomap/RadiomapCanvas.tsx`, `*.module.css`
  - **Что:**
    - SVG `viewBox="0 0 1200 800"`, `<image href="/office-floorplan.svg" .../>` как фон.
    - Поверх — `<g>` для каждой зоны: прозрачный прямоугольник (`fill: zone.display_color || palette[zone.type]; opacity: 0.2`) + текст-метка.
    - Точки калибровки: для каждой `CalibrationPoint` (Fingerprint с is_calibration=true) — `<circle cx={zone.x + jitter(idx).dx} cy={zone.y + jitter(idx).dy} r={6} fill={zone.display_color}>`. `jitter` — детерминированная функция от `idx % grid` чтобы точки не накладывались.
    - Hover: `<title>` с `captured_at`, `sample_count`, `bssid_count` (число BSSID в `rssi_vector` — берём из FingerprintResponse).
    - Клик по точке: открыть `<DeleteCalibrationPointButton>` confirm.
  - **Логи:** `log.debug("[radiomap.canvas] render", { pointsCount, zonesCount })`.

- [ ] **Task 6.5: Страница радиокарты**
  - **Файлы:** `web/src/features/radiomap/RadiomapPage.tsx`, `ZoneLegend.tsx`, `CalibrationPointsTable.tsx`, `DeleteCalibrationPointButton.tsx`
  - **Что:**
    - Сверху: filter «Зона» (select из useZonesQuery). При выборе — `useCalibrationPointsQuery({ zone_id })`. По умолчанию — все зоны.
    - Сводка: «X / Y зон откалибровано (нужно ≥ 3 точек на зону)». Y = зоны типа `workplace|corridor|meeting_room` (исключая `outside_office`).
    - `<RadiomapCanvas>` с фильтром.
    - `<ZoneLegend>`: список зон с цветовыми чипами и счётчиком точек.
    - `<CalibrationPointsTable>` (свернутая по умолчанию): captured_at, zone, sample_count, bssid_count, employee_id (кто калибровал), action delete. Полезна когда SVG-схема не показывает все детали.
    - Если в системе нет ни одной калибровочной точки → `<EmptyState>` «Радиокарта пуста. Откалибруйте зоны через mobile-приложение в режиме админа.»
  - **Логи:** `log.debug("[radiomap.page] mounted", { zonesCount, pointsCount })`.
  - **Тесты:** `tests/features/radiomap/RadiomapPage.test.tsx` — MSW отдаёт 4 зоны и 12 точек → правильный счётчик «4 / 4 откалибровано».

### Phase 7: Дашборд посещаемости

- [ ] **Task 7.1: Queries для attendance**
  - **Файлы:** `web/src/features/attendance/attendanceQueries.ts`
  - **Что:**
    - `useAttendanceQuery({ employee_id, started_from, started_to, status, limit, offset })` — `staleTime: 30_000`, `refetchInterval: 30_000` для real-time «кто где».
    - `useAttendanceSummaryQuery({ employee_id, from, to })`.
    - `useCurrentZonesQuery(employeeIds: number[])`: внутри — `useQueries` массив, для каждого `employee_id` запрос `listAttendance({ employee_id, limit: 1, started_from: startOfToday })`. Возвращает `Map<employeeId, latestSession | null>`. Поле "is_open" — `ended_at == null`.
  - **Логи:** `log.debug("[attendance.queries] currentZones", { ids })`.

- [ ] **Task 7.2: Helpers форматирования**
  - **Файлы:** `web/src/features/attendance/helpers.ts`, `web/src/lib/formatDuration.ts`
  - **Что:**
    - `formatDuration(seconds)`: `"8 ч 32 мин"`, `"42 мин"`, `"45 сек"`.
    - `getStatusLabel(status)`: `"present"→"Присутствует"`, `"late"→"Опоздание"`, `"overtime"→"Переработка"`, `"absent"→"Отсутствие"`.
    - `getStatusColor(status)`: соответствует CSS-переменным.
    - `groupSessionsByDay(sessions)` — для chart'ов; учитывает только закрытые.
    - `dayPresets()`: возвращает `{ today, week, month }` с `from`/`to` в UTC.
  - **Логи:** N/A.

- [ ] **Task 7.3: CurrentZoneTable + Dashboard**
  - **Файлы:** `web/src/features/attendance/AttendanceDashboardPage.tsx`, `CurrentZoneTable.tsx`
  - **Что:**
    - `useEmployeesQuery({ limit: 100, is_active: true })` → массив сотрудников.
    - `useCurrentZonesQuery(employeeIds)` → текущая открытая или последняя сессия.
    - `useZonesQuery()` для маппинга zone_id → name+display_color.
    - Таблица: full_name, email, текущая зона (с ColorChip), `с какого времени` (formatRelative), длительность (formatDuration), статус (chip). Если нет сессий сегодня — «Не отмечался сегодня» (серым).
    - Над таблицей — счётчики «На рабочих местах: X» / «В коридоре: Y» / «На переговорной: Z» / «Не на месте: K».
    - Клик по строке → переход на `/attendance/:employeeId`.
  - **Логи:** `log.debug("[attendance.dashboard] tick", { onWorkplace, onCorridor })` каждые 30s.
  - **Тесты:** `tests/features/attendance/CurrentZoneTable.test.tsx` — 3 сотрудника, 2 с открытыми сессиями, 1 без → правильные счётчики.

- [ ] **Task 7.4: PeriodPicker**
  - **Файлы:** `web/src/features/attendance/PeriodPicker.tsx`
  - **Что:** Toggle-buttons: «Сегодня», «Неделя», «Месяц», «Период». При «Период» — два `<input type="date">`. onChange отдаёт `{ from, to }` в UTC.
  - **Логи:** N/A.

- [ ] **Task 7.5: Charts через recharts**
  - **Файлы:** `web/src/features/attendance/WorkHoursChart.tsx`, `LatenessOvertimeChart.tsx`
  - **Что:**
    - `WorkHoursChart`: получает `sessions: AttendanceLogResponse[]`, группирует по дням, рисует `BarChart` (X=date, Y=hours). Tooltip показывает «дата + N ч M мин». Цвет — `--color-primary`.
    - `LatenessOvertimeChart`: две линии (lateness count, overtime hours). `LineChart`.
    - Адаптивный размер через `<ResponsiveContainer>`.
  - **Логи:** N/A.
  - **Тесты:** `tests/features/attendance/WorkHoursChart.test.tsx` — 7 сессий за 3 дня → 3 бара с правильными суммами.

- [ ] **Task 7.6: EmployeeAttendancePage**
  - **Файлы:** `web/src/features/attendance/EmployeeAttendancePage.tsx`
  - **Что:**
    - `useEmployeeQuery(id)` (название, расписание).
    - `useAttendanceSummaryQuery({ employee_id, from, to })` — карточка с числами `work_hours_total`, `lateness_count`, `overtime_seconds_total / 3600`.
    - `useAttendanceQuery({ employee_id, started_from: from, started_to: to, limit: 100 })` — таблица сессий.
    - `<WorkHoursChart>`, `<LatenessOvertimeChart>` с этими данными.
    - Кнопка «Сменить пароль» открывает `<ChangePasswordModal>` (admin-reset).
  - **Логи:** `log.debug("[attendance.employee] mounted", { id, period })`.

### Phase 8: Документация и финал

- [ ] **Task 8.1: web/README.md**
  - **Файлы:** `web/README.md`
  - **Что:** На русском, разделы:
    - Обзор и стек.
    - Backend prerequisites: `uvicorn` на 8000 + миграции/seed.
    - Установка: `npm install`.
    - Генерация типов: `npm run gen:api` (требует поднятого backend).
    - Запуск: `npm run dev` → http://localhost:5173.
    - Скрипты: `dev`, `build`, `preview`, `lint`, `test`, `test:cov`, `typecheck`, `gen:api`.
    - Структура папок (краткая, со ссылкой на этот план для деталей).
    - Авторизация в dev-БД (admin@svetlyachok.local / admin12345 — из seed).
    - Как добавить новую фичу: создать `features/<name>/`, добавить queries, мутации, страницу, маршрут.
    - Как заменить заглушку SVG на реальный план: `public/office-floorplan.svg` + обновить `zoneLayout.ts`.
    - Известные ограничения пилота: координаты зон не в БД, нет E2E через Playwright, нет dark mode.
  - **Логи:** N/A.

- [ ] **Task 8.2: TSDoc в нетривиальных местах**
  - **Файлы:** `web/src/api/client.ts`, `errors.ts`, `refreshSingleflight.ts`, `features/auth/authStore.ts`, `features/radiomap/zoneLayout.ts`
  - **Что:** Краткие docstrings (русский) к экспортным функциям/классам, объясняющие непрямые решения (single-flight refresh, почему refresh в localStorage, почему zoneLayout локальный конфиг).
  - **Логи:** N/A.

- [ ] **Task 8.3: Smoke E2E (вручную)**
  - **Файлы:** N/A — финальная проверка по чеклисту в `web/README.md` (раздел «Чеклист пилотного запуска»).
  - **Что:**
    1. `uvicorn` поднят, `alembic upgrade head` + `python scripts/seed.py`.
    2. `cd web && npm install && npm run gen:api && npm run dev`.
    3. http://localhost:5173 → редирект на /login.
    4. Login admin@svetlyachok.local / admin12345 → дашборд.
    5. Создать сотрудника, активировать/деактивировать.
    6. Создать зону, удалить (если нет attendance — успех).
    7. На /radiomap — видны 4 зоны seed'а, точки калибровки (если seed создаёт).
    8. На /attendance — таблица сотрудников.
    9. F5 → пользователь остаётся залогиненным (refresh работает).
    10. Logout → редирект на /login, токены стёрты.
  - **Логи:** N/A.
  - **Готово, когда:** все 10 пунктов проходят.

- [ ] **Task 8.4: Lint/typecheck/test зелёные**
  - **Файлы:** N/A — финальная проверка.
  - **Что:** `npm run lint`, `npm run typecheck`, `npm run test` — все три без ошибок и без warnings (warnings → fail).
  - **Логи:** N/A.

## Commit Plan

Задач много (≈30 в детализации); чекпоинт-коммиты:

- **Checkpoint 1 (после Task 1.5):** `chore(web): scaffold проекта Vite + TypeScript + базовые стили + log/env`
- **Checkpoint 2 (после Task 2.7):** `feat(web): API-клиент с типами OpenAPI, RFC 7807 errors, queryKeys, Vitest+MSW infra`
- **Checkpoint 3 (после Task 3.6):** `feat(web): auth — login screen, JWT-store с auto-refresh, layout, route guards`
- **Checkpoint 4 (после Task 4.4):** `feat(web): CRUD сотрудников — список, форма, пароль, deactivate/activate`
- **Checkpoint 5 (после Task 5.3):** `feat(web): CRUD зон с обработкой 409 zone_in_use`
- **Checkpoint 6 (после Task 6.5):** `feat(web): визуализация калибровочной радиокарты (SVG + точки)`
- **Checkpoint 7 (после Task 7.6):** `feat(web): дашборд посещаемости — таблица «кто где» + графики work_hours/lateness/overtime`
- **Final commit (после Task 8.4):** `docs(web): README, TSDoc, smoke-чеклист пилотного запуска`

Conventional Commits на русском (как в проекте). Pre-push (если будет hook) запускает `lint && typecheck && test`.

## Принципы

1. **TypeScript strict, no `any`.** Если приходится — `unknown` + narrow через type guard, или `// @ts-expect-error` с комментарием почему.
2. **Никаких `console.log`.** Все логи через `lib/log.ts`. ESLint запрещает `console`.
3. **Feature-based структура.** Файлы фичи лежат в `features/<name>/`, не разбросаны по `pages/`, `services/`, `hooks/`.
4. **Никаких бизнес-данных в Zustand.** Всё, что приходит от backend → TanStack Query. Zustand только для auth, UI-флагов.
5. **Все DTO — типы из `openapi-typescript`.** Никаких ручных интерфейсов поверх API. Если бекенд изменил схему — `npm run gen:api` поднимет TS-ошибки.
6. **Zod-валидация на input forms** + кросс-валидация (например, `schedule_end > schedule_start`). Серверные `validation_failed.errors[]` мапятся через `setError` в react-hook-form.
7. **Все datetime — UTC ISO-строки на проводе**, локальный TZ только для display.
8. **Доступность:** семантические HTML-теги (`<button>`, `<nav>`, `<main>`, `<table>`), `<label htmlFor>`, `aria-live` для toast-сообщений, фокус-trap в модалках.
9. **Error boundaries вокруг shell'а** + react-query `useQuery({ throwOnError: false })` (default) — ошибки данных идут через UI banner, не убивают всё приложение.
10. **Suspense НЕ используем для data fetching** на этой вехе (TanStack Query v5 поддерживает, но смешивать с error boundaries сложнее) — используем `isLoading`/`isError` явно.
11. **CSS Modules**, никаких inline-стилей кроме редкой динамики (например, `style={{ fill: zone.display_color }}` в SVG — там оправдано).
12. **i18n изолирован в `i18n/ru.ts`** — миграция на i18next позже сводится к замене `t(key)` на `useTranslation()` без правки компонентов.
13. **Dev-proxy `/api → :8000` в Vite** — обходим CORS на пилоте, не трогая backend.
14. **Single-flight refresh** на 401 — критично для дашбордов с N параллельными запросами.
15. **Retry policy TanStack Query:** 2 раза, кроме `AuthExpiredError` (не повторяем — let user re-login).
16. **Никаких backend-изменений** — все недостающие данные собираем композицией существующих эндпоинтов; «нужно `GET /attendance/current`» — отдельная задача в roadmap, не блокирует эту веху.
