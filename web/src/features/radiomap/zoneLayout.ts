/**
 * Локальный конфиг координат зон на радиокарте.
 *
 * Координаты привязаны к viewBox SVG-фона (1200×800). Если в БД создаётся
 * новая зона, не описанная здесь — она не отрисуется на схеме (только
 * в таблице точек). Расширение карты — задача после полевых испытаний,
 * когда план офиса станет точным.
 *
 * Сейчас покрывает 4 типовых seed-зоны:
 * - id 1 → Рабочее место 1 (workplace)
 * - id 2 → Рабочее место 2 (workplace)
 * - id 3 → Переговорная (meeting_room)
 * - id 4 → Коридор (corridor)
 *
 * Для будущих зон: добавьте сюда `<id>: { x, y, w, h }` после создания
 * в админ-панели.
 */
export interface ZoneRect {
  x: number;
  y: number;
  w: number;
  h: number;
}

export const zoneLayout: Record<number, ZoneRect> = {
  1: { x: 80, y: 80, w: 380, h: 280 },
  2: { x: 500, y: 80, w: 380, h: 280 },
  3: { x: 920, y: 80, w: 240, h: 280 },
  4: { x: 80, y: 400, w: 1080, h: 160 },
};

/**
 * Минимум калибровочных точек на зону для готовности ML-классификации.
 * Совпадает с backend-проверкой `MIN_CALIBRATION_POINTS_PER_ZONE`.
 */
export const MIN_CALIBRATION_POINTS_PER_ZONE = 3;

/**
 * Палитра по типу зоны — используется когда `display_color` не задан.
 */
export const zoneTypeColor: Record<string, string> = {
  workplace: "#1e88e5",
  corridor: "#718096",
  meeting_room: "#38a169",
  outside_office: "#c53030",
};
