/**
 * Маппинг известных RFC 7807 `code` → русское сообщение для UI.
 *
 * Если `code` отсутствует или неизвестен — fallback на `detail` (что прислал
 * backend) или общее «Ошибка сервера. Попробуйте позже.».
 */
import { ApiError, NetworkError } from "../api/errors";

const CODE_MESSAGES: Record<string, string> = {
  // Auth
  invalid_credentials: "Неверный email или пароль",
  token_expired: "Сессия истекла, войдите снова",
  invalid_token: "Сессия истекла, войдите снова",
  auth_expired: "Сессия истекла, войдите снова",
  rate_limit_exceeded: "Слишком много попыток. Попробуйте позже",

  // Validation
  validation_failed: "Проверьте введённые данные",
  email_already_exists: "Сотрудник с таким email уже существует",

  // Zones
  zone_in_use: "Нельзя удалить: на зону ссылаются записи учёта",
  zone_not_found: "Зона не найдена",

  // Calibration
  not_a_calibration_point: "Эта точка не является калибровочной",
  empty_calibration_set: "Радиокарта пуста — нужны калибровочные точки",
  insufficient_calibration_points: "Недостаточно калибровочных точек для классификации",
  missing_zone_types: "В радиокарте не покрыты все типы зон",

  // Fingerprints
  captured_at_in_future: "Метка времени отпечатка из будущего",
  captured_at_too_old: "Отпечаток слишком старый",
  invalid_rssi_vector: "Некорректный вектор RSSI",
  rssi_value_out_of_range: "Значение RSSI вне допустимого диапазона",

  // Attendance
  attendance_self_only: "Доступ только к собственным данным",

  // Generic
  not_found: "Запись не найдена",
  forbidden: "Недостаточно прав",
  internal_error: "Ошибка сервера. Попробуйте позже",
};

const FALLBACK = "Ошибка сервера. Попробуйте позже";

export const getErrorMessage = (error: unknown): string => {
  if (error instanceof NetworkError) {
    return "Не удалось связаться с сервером. Проверьте подключение.";
  }
  if (error instanceof ApiError) {
    if (error.code !== undefined) {
      const msg = CODE_MESSAGES[error.code];
      if (msg !== undefined) return msg;
    }
    if (error.detail !== undefined && error.detail.length > 0) {
      return error.detail;
    }
    if (error.message.length > 0) return error.message;
  }
  if (error instanceof Error && error.message.length > 0) {
    return error.message;
  }
  return FALLBACK;
};
