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
│   ├── api/              # axios-клиент, типы из OpenAPI, queryKeys, endpoints
│   ├── components/       # переиспользуемые UI-компоненты
│   ├── features/         # auth, employees, zones, radiomap, attendance
│   ├── layout/           # AppShell + Sidebar + Topbar
│   ├── lib/              # log, env, formatDate, errorMessages
│   ├── routes/           # AppRoutes, PrivateRoute, AdminRoute
│   ├── styles/           # tokens.css, reset.css
│   ├── i18n/             # ru.ts (плоский словарь)
│   ├── App.tsx
│   ├── main.tsx
│   └── index.css
├── tests/
│   ├── setup.ts          # Vitest + JSDOM + MSW
│   ├── msw/              # mock-handlers
│   └── ...
├── public/
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
└── vitest.config.ts
```

## Известные ограничения пилота

- Координаты зон не хранятся в БД — статический `zoneLayout.ts` в коде
- Нет E2E через Playwright (откладываем до полевых испытаний)
- Нет dark mode
- Refresh-token хранится в `localStorage` (на пилоте достаточно — backend не выставляет httpOnly cookie)
