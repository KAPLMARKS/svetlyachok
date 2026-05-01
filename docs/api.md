[← Архитектура](architecture.md) · [Back to README](../README.md) · [Конфигурация →](configuration.md)

# API Reference

REST API АИС «Светлячок». Все endpoints находятся под префиксом `/api/v1/`.

На текущей вехе реализован только healthcheck. Остальные endpoints (приём радиоотпечатков, классификация, учёт времени, ERP-интеграция) появятся на следующих вехах согласно [.ai-factory/ROADMAP.md](../.ai-factory/ROADMAP.md).

## Базовый URL

| Окружение | URL |
|-----------|-----|
| Local development | `http://localhost:8000` |
| Staging | TBD |
| Production | TBD |

## Интерактивная документация

| Инструмент | URL |
|-----------|-----|
| Swagger UI | `/docs` |
| ReDoc | `/redoc` |
| OpenAPI JSON | `/openapi.json` |

## Версионирование

Версия API указывается в URL-префиксе: `/api/v1/`. Breaking changes выпускаются под новым префиксом (`/api/v2/...`), сохраняя старый функциональным до согласованного срока поддержки.

## Аутентификация

На текущей вехе аутентификация не требуется (только healthcheck). На следующей вехе будет добавлен JWT-based auth с endpoint'ами `/api/v1/auth/login` и `/api/v1/auth/refresh`. Все защищённые endpoints будут принимать `Authorization: Bearer <jwt>`.

## Корреляция запросов

Каждый HTTP-запрос автоматически получает `X-Correlation-ID` (UUID hex). Сервер:

1. Если клиент передал свой `X-Correlation-ID` в заголовке запроса — использует его
2. Иначе — генерирует новый UUID4
3. Возвращает значение в response header
4. Включает `correlation_id` в JSON-логи и в `correlation_id` поле любых error responses

Это позволяет связать запрос пользователя со всеми серверными логами:

```bash
curl -H "X-Correlation-ID: my-debug-trace-123" http://localhost:8000/api/v1/health -i
# HTTP/1.1 200 OK
# x-correlation-id: my-debug-trace-123
# ...
```

## Формат ошибок (RFC 7807)

Все ошибки возвращаются в формате [RFC 7807 Problem Details](https://datatracker.ietf.org/doc/html/rfc7807) с расширениями проекта.

Content-Type: `application/problem+json`

### Структура

```json
{
  "type": "about:blank",
  "title": "Not Found",
  "status": 404,
  "detail": "Employee with ID 'abc-123' not found",
  "instance": "/api/v1/employees/abc-123",
  "code": "employee_not_found",
  "correlation_id": "a3f9d8c1b2e4f56789abcdef01234567"
}
```

### Поля

| Поле | Тип | Описание |
|------|-----|----------|
| `type` | string | URI идентификатор типа проблемы. По умолчанию `about:blank` |
| `title` | string | Краткое описание (соответствует HTTP reason phrase) |
| `status` | integer | HTTP status code |
| `detail` | string | Детальное описание этого случая |
| `instance` | string | URI запроса, в котором произошла ошибка |
| `code` | string | Machine-readable код ошибки (snake_case). Используется клиентом для обработки конкретных случаев |
| `correlation_id` | string | ID корреляции из X-Correlation-ID header |
| `validation_errors` | array | (только для 400) Список ошибок валидации Pydantic |

### Стандартные status codes

| Status | Доменное исключение | code (default) |
|--------|---------------------|----------------|
| 400 | `ValidationError` | `validation_error` |
| 401 | `UnauthorizedError` | `unauthorized` |
| 403 | `ForbiddenError` | `forbidden` |
| 404 | `NotFoundError` | `not_found` |
| 409 | `ConflictError` | `conflict` |
| 500 | unhandled `Exception` | `internal_error` |

### Пример ошибки валидации (400)

```json
{
  "type": "about:blank",
  "title": "Bad Request",
  "status": 400,
  "detail": "Request payload validation failed",
  "instance": "/api/v1/employees",
  "code": "validation_error",
  "correlation_id": "...",
  "validation_errors": [
    {
      "loc": ["body", "email"],
      "msg": "value is not a valid email address",
      "type": "value_error.email"
    }
  ]
}
```

## Endpoints

### `GET /api/v1/health`

Healthcheck endpoint. Возвращает текущее состояние приложения и его подсистем.

**Auth:** не требуется
**Status codes:** 200 OK

**Response:**

```json
{
  "status": "ok",
  "version": "0.1.0",
  "environment": "development",
  "checks": {
    "app": "ok",
    "database": "ok"
  }
}
```

| Поле | Значения | Описание |
|------|----------|----------|
| `status` | `ok` / `degraded` | Общий статус (`degraded` если хотя бы одна проверка failed) |
| `version` | string | Версия приложения из `pyproject.toml` |
| `environment` | `development` / `staging` / `production` | Окружение запуска |
| `checks` | object | Результаты по подсистемам |

**Текущие подсистемы:**

| Ключ | Что проверяется |
|------|-----------------|
| `app` | Liveness — приложение запущено и обрабатывает запросы |
| `database` | TODO: подключение к PostgreSQL (`SELECT 1`) — заглушка на текущей вехе |

**Использование для мониторинга:**

- **Liveness probe:** просто проверка 200 OK на `/api/v1/health`
- **Readiness probe:** дополнительно проверять `body.status == "ok"` (если `degraded` — приложение пока не готово)

**Пример:**

```bash
curl http://localhost:8000/api/v1/health
# 200 OK
# {"status":"ok","version":"0.1.0","environment":"development","checks":{"app":"ok","database":"ok"}}
```

## Планируемые endpoints (следующие вехи)

| Endpoint | Веха | Назначение |
|---------|------|-----------|
| `POST /api/v1/auth/login` | Аутентификация | JWT login |
| `POST /api/v1/auth/refresh` | Аутентификация | JWT refresh |
| `GET/POST/PUT/DELETE /api/v1/employees` | Управление сотрудниками | CRUD |
| `GET/POST /api/v1/zones` | Управление зонами | CRUD |
| `POST /api/v1/fingerprints` | Радиоотпечатки | Приём с устройства |
| `POST /api/v1/calibration/points` | Радиоотпечатки | Создание эталонной точки |
| `POST /api/v1/positioning/classify` | ML | Классификация позиции |
| `GET /api/v1/attendance/...` | Учёт времени | Отчёты |
| `POST /api/v1/erp/export` | Интеграция | Выгрузка в формате 1С |

## See Also

- [Конфигурация](configuration.md) — переменные окружения для настройки API
- [Архитектура](architecture.md) — структура слоёв backend
