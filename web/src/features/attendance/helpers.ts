import type { AttendanceLogResponse, AttendanceStatus } from "@/api/types";

export const formatDuration = (seconds: number | null): string => {
  if (seconds === null || seconds < 0) return "—";
  if (seconds < 60) return `${seconds} сек`;
  const total = Math.floor(seconds);
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  if (hours === 0) return `${minutes} мин`;
  return `${hours} ч ${minutes.toString().padStart(2, "0")} мин`;
};

const STATUS_LABEL: Record<AttendanceStatus, string> = {
  present: "Присутствует",
  late: "Опоздание",
  overtime: "Переработка",
  absent: "Отсутствие",
};

const STATUS_COLOR: Record<AttendanceStatus, string> = {
  present: "var(--color-success)",
  late: "var(--color-warning)",
  overtime: "var(--color-info)",
  absent: "var(--color-fg-muted)",
};

export const getStatusLabel = (status: AttendanceStatus): string => STATUS_LABEL[status];
export const getStatusColor = (status: AttendanceStatus): string => STATUS_COLOR[status];

export const groupSessionsByDay = (
  sessions: AttendanceLogResponse[],
): Map<string, number> => {
  const result = new Map<string, number>();
  for (const s of sessions) {
    if (s.duration_seconds === null) continue;
    const day = s.started_at.slice(0, 10);
    result.set(day, (result.get(day) ?? 0) + s.duration_seconds);
  }
  return result;
};

export interface DateRange {
  from: string;
  to: string;
}

const startOfDayUtc = (date: Date): Date => {
  const d = new Date(date);
  d.setUTCHours(0, 0, 0, 0);
  return d;
};

const endOfDayUtc = (date: Date): Date => {
  const d = new Date(date);
  d.setUTCHours(23, 59, 59, 999);
  return d;
};

export const dayPresets = (): {
  today: DateRange;
  week: DateRange;
  month: DateRange;
} => {
  const now = new Date();
  const today: DateRange = {
    from: startOfDayUtc(now).toISOString(),
    to: endOfDayUtc(now).toISOString(),
  };
  const weekStart = new Date(now);
  weekStart.setUTCDate(weekStart.getUTCDate() - 6);
  const week: DateRange = {
    from: startOfDayUtc(weekStart).toISOString(),
    to: endOfDayUtc(now).toISOString(),
  };
  const monthStart = new Date(now);
  monthStart.setUTCDate(monthStart.getUTCDate() - 29);
  const month: DateRange = {
    from: startOfDayUtc(monthStart).toISOString(),
    to: endOfDayUtc(now).toISOString(),
  };
  return { today, week, month };
};

export const formatTime = (iso: string | null): string => {
  if (iso === null) return "—";
  const d = new Date(iso);
  return d.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
};

export const formatDate = (iso: string): string => {
  const d = new Date(iso);
  return d.toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit", year: "numeric" });
};
