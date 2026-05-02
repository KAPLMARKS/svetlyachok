# Web АИС «Светлячок» — React + Vite + TypeScript

Админ-панель для пилота Wi-Fi RSSI indoor positioning. Без production-инфраструктуры —
только локальный `npm run dev` на `:5173`.

## Стек

- **Vite 5** + **React 18** + **TypeScript 5** (strict + `noUncheckedIndexedAccess` + `exactOptionalPropertyTypes`)
- **TanStack Query v5** — server state (CRUD + cache + invalidation)
- **Zustand** — client state (auth, UI)
- **react-router-dom v6** — маршрутизация + guards
- **react-hook-form + zod** — формы + валидация
- **axios** — HTTP-клиент с interceptor'ами (auth-refresh single-flight)
- **CSS Modules** + CSS-переменные
- **recharts** — графики посещаемости
- **react-hot-toast** — уведомления
- **lucide-react** — иконки
- **Vitest + React Testing Library + MSW** — тесты

## Backend prerequisites

Перед стартом убедитесь, что backend доступен:

```bash
cd backend
.venv/Scripts/python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# В другом терминале:
curl http://localhost:8000/openapi.json
```

CORS пропускается через Vite dev-proxy (`/api → http://localhost:8000`),
не требует изменений в backend.

## Установка

```bash
cd web
npm install
```

## Генерация типов из OpenAPI

```bash
# Backend должен быть запущен
npm run gen:api
```

Это сгенерирует `src/api/schema.d.ts` (в `.gitignore`).

## Запуск

```bash
npm run dev
# → http://localhost:5173
```

## Скрипты

| Скрипт | Что делает |
|--------|------------|
| `npm run dev` | Поднимает Vite на `:5173` с HMR и dev-proxy |
| `npm run build` | TypeScript-typecheck + production-bundle |
| `npm run preview` | Просмотр production-сборки локально |
| `npm run lint` | ESLint (max-warnings 0) |
| `npm run lint:fix` | ESLint + автофикс |
| `npm run format` | Prettier |
| `npm run typecheck` | `tsc -b --noEmit` |
| `npm run test` | Vitest run |
| `npm run test:watch` | Vitest watch |
| `npm run test:cov` | Тесты с покрытием (v8) |
| `npm run gen:api` | Перегенерировать типы из `/openapi.json` |

## Авторизация в dev-БД

После `python scripts/seed.py` на backend:
- email: `admin@svetlyachok.local`
- пароль: `admin12345`

## Структура папок

```
web/
├── src/
│   ├── api/              # axios-клиент, types.ts (ручные DTO), endpoints, queryKeys, errors, interceptors
│   │   └── endpoints/    # auth.ts, employees.ts, zones.ts, calibration.ts, attendance.ts
│   ├── components/       # Modal, ConfirmModal
│   ├── features/
│   │   ├── auth/         # authStore, LoginPage, schema
│   │   ├── employees/    # queries, schema, EmployeeFormModal, ChangePasswordModal, EmployeesListPage
│   │   ├── zones/        # queries, schema, ZoneFormModal, ZonesListPage
│   │   ├── radiomap/     # queries, zoneLayout, RadiomapCanvas, RadiomapPage
│   │   └── attendance/   # queries, helpers, PeriodPicker, WorkHoursChart, dashboard, employee detail
│   ├── layout/           # AppShell, Sidebar, Topbar
│   ├── lib/              # log, env, errorMessages
│   ├── routes/           # routes (константы), PrivateRoute, AdminRoute, AppRoutes
│   ├── styles/           # tokens.css, reset.css
│   ├── App.tsx           # BrowserRouter + Toaster + bootstrapFromRefresh
│   ├── main.tsx          # QueryClient + installInterceptors + render
│   └── index.css         # импорт tokens + reset
├── tests/
│   ├── setup.ts          # Vitest + JSDOM + MSW + localStorage cleanup
│   ├── msw/              # server.ts + handlers.ts (default happy-path)
│   └── lib/              # errorMessages.test.ts (4 тестa)
├── public/
│   └── office-floorplan.svg   # SVG-заглушка плана офиса
├── index.html
├── package.json
├── tsconfig.json + tsconfig.node.json
├── vite.config.ts        # alias @/, dev-proxy /api → :8000
├── vitest.config.ts      # jsdom + globals + setupFiles
└── .eslintrc.cjs + .prettierrc
```

## Как добавить новую фичу

1. Создать папку `src/features/<name>/`.
2. Положить туда: `*Queries.ts` (TanStack Query hooks), `schema.ts` (zod),
   формы/страницы (`*.tsx`).
3. Добавить query-ключ в `src/api/queryKeys.ts` (`qk.<resource>._all` /
   `.list` / `.detail`).
4. Если нужна типизация ответа — добавить в `src/api/types.ts` (или
   перегенерировать `schema.d.ts` через `npm run gen:api`).
5. Добавить endpoint-обёртку в `src/api/endpoints/<resource>.ts`.
6. Подключить страницу в `src/routes/AppRoutes.tsx`.

## Как заменить заглушку SVG-плана офиса

1. Заменить файл `public/office-floorplan.svg` на реальный план
   (рекомендованный размер viewBox — 1200×800).
2. Обновить координаты в `src/features/radiomap/zoneLayout.ts`:
   `Record<zoneId, { x, y, w, h }>`. Координаты — в системе viewBox.
3. Перезапустить `npm run dev` — изменения подхватятся.

## Smoke E2E чеклист (пилотный запуск)

Backend и web запущены:
- [ ] `cd backend && .venv/Scripts/python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000`
- [ ] `cd web && npm install && npm run dev` → http://localhost:5173

Сценарий:
1. Открыть http://localhost:5173 → должен редиректить на `/login`.
2. Войти `admin@svetlyachok.local` / `admin12345` → попадаем на `/attendance`.
3. Сайдбар «Сотрудники» → создать нового, активировать/деактивировать.
4. Сайдбар «Зоны» → создать зону, удалить (если нет attendance — успех; иначе
   увидим toast про 409 zone_in_use).
5. Сайдбар «Радиокарта» → видны 4 seed-зоны и точки калибровки (если есть).
6. Сайдбар «Учёт времени» → таблица сотрудников с текущей зоной обновляется
   каждые 30 сек.
7. Клик по строке сотрудника → детальная страница с графиком часов и таблицей
   сессий, переключение Сегодня / Неделя / Месяц / Период.
8. F5 на любой странице → пользователь остаётся залогиненным (refresh-flow).
9. Topbar «Выйти» → редирект на `/login`, токены стёрты.

## Известные ограничения пилота

- Координаты зон не хранятся в БД — статический `zoneLayout.ts` в коде
- Нет E2E через Playwright (откладываем до полевых испытаний)
- Нет dark mode
- Refresh-token хранится в `localStorage` (на пилоте достаточно — backend
  не выставляет httpOnly cookie)
- `src/api/types.ts` — ручные интерфейсы DTO (актуальны на момент написания);
  для автомиграции при изменениях backend используйте `npm run gen:api`,
  результат кладётся в `src/api/schema.d.ts` (в `.gitignore`)
- ESLint v8 (deprecated upstream); миграция на v9 flat-config — отдельная задача
