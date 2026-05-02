/**
 * Тонкий логгер. В production — no-op (никаких console.* в продакшен-bundle),
 * в DEV выводит структурированные сообщения с префиксом `[svetlyachok]`.
 *
 * Сигнатура: `log.info("[area.action] msg", { key: value })`. Поля во втором
 * аргументе сериализуются для удобства чтения в DevTools.
 *
 * ESLint запрещает `console.*` в коде проекта — все логи идут через эту обёртку.
 */
type LogFields = Record<string, unknown>;

const PREFIX = "[svetlyachok]";

const isDev = (): boolean => {
  try {
    return Boolean(import.meta.env.DEV);
  } catch {
    return false;
  }
};

const noop = (): void => {};

const make =
  (level: "debug" | "info" | "warn" | "error") =>
  (msg: string, fields?: LogFields): void => {
    if (!isDev()) return;
    // eslint-disable-next-line no-console
    const target = console[level] ?? console.log;
    if (fields !== undefined) {
      target(`${PREFIX} ${msg}`, fields);
    } else {
      target(`${PREFIX} ${msg}`);
    }
  };

export const log = {
  debug: isDev() ? make("debug") : noop,
  info: isDev() ? make("info") : noop,
  warn: isDev() ? make("warn") : noop,
  error: isDev() ? make("error") : noop,
};
