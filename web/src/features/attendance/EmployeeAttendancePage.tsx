import { ArrowLeft } from "lucide-react";
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { useEmployeeQuery } from "@/features/employees/employeesQueries";
import { useZonesQuery } from "@/features/zones/zonesQueries";
import { ROUTES } from "@/routes/routes";

import { useAttendanceQuery, useAttendanceSummaryQuery } from "./attendanceQueries";
import { type DateRange, dayPresets, formatDate, formatDuration, formatTime, getStatusColor, getStatusLabel } from "./helpers";
import { PeriodPicker } from "./PeriodPicker";
import { WorkHoursChart } from "./WorkHoursChart";

export const EmployeeAttendancePage = (): JSX.Element => {
  const navigate = useNavigate();
  const params = useParams<{ employeeId: string }>();
  const employeeId = params.employeeId !== undefined ? Number(params.employeeId) : undefined;

  const [range, setRange] = useState<DateRange>(dayPresets().week);

  const employeeQuery = useEmployeeQuery(employeeId);
  const summaryQuery = useAttendanceSummaryQuery(employeeId, range.from, range.to);
  const sessionsQuery = useAttendanceQuery({
    ...(employeeId !== undefined ? { employee_id: employeeId } : {}),
    started_from: range.from,
    started_to: range.to,
    limit: 100,
  });
  const zonesQuery = useZonesQuery();

  const zoneById = new Map<number, string>();
  for (const z of zonesQuery.data ?? []) zoneById.set(z.id, z.name);

  return (
    <div>
      <button
        type="button"
        onClick={() => navigate(ROUTES.dashboard)}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: "var(--space-2)",
          background: "transparent",
          border: "none",
          cursor: "pointer",
          padding: 0,
          marginBottom: "var(--space-3)",
          color: "var(--color-primary)",
          fontSize: 13,
        }}
      >
        <ArrowLeft size={14} /> Назад к списку
      </button>

      <h1 style={{ margin: 0, marginBottom: "var(--space-4)" }}>
        {employeeQuery.data?.full_name ?? "..."}
      </h1>

      <PeriodPicker value={range} onChange={setRange} />

      {summaryQuery.data && (
        <div
          style={{
            marginTop: "var(--space-4)",
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))",
            gap: "var(--space-3)",
          }}
        >
          <SummaryCard
            label="Отработано"
            value={formatDuration(summaryQuery.data.work_seconds_total)}
          />
          <SummaryCard
            label="Опозданий"
            value={summaryQuery.data.lateness_count.toString()}
          />
          <SummaryCard
            label="Переработка"
            value={formatDuration(summaryQuery.data.overtime_seconds_total)}
          />
          <SummaryCard
            label="Сессий"
            value={summaryQuery.data.sessions_count.toString()}
          />
        </div>
      )}

      <h2 style={{ marginTop: "var(--space-5)", marginBottom: "var(--space-3)" }}>
        Часы по дням
      </h2>
      {sessionsQuery.data && <WorkHoursChart sessions={sessionsQuery.data.items} />}

      <h2 style={{ marginTop: "var(--space-5)", marginBottom: "var(--space-3)" }}>Сессии</h2>
      {sessionsQuery.data && (
        <table
          style={{
            width: "100%",
            borderCollapse: "collapse",
            background: "var(--color-surface)",
            borderRadius: "var(--radius-md)",
            overflow: "hidden",
          }}
        >
          <thead style={{ background: "var(--color-surface-muted)" }}>
            <tr>
              <th style={th}>Дата</th>
              <th style={th}>С</th>
              <th style={th}>До</th>
              <th style={th}>Длит.</th>
              <th style={th}>Зона</th>
              <th style={th}>Статус</th>
            </tr>
          </thead>
          <tbody>
            {sessionsQuery.data.items.length === 0 && (
              <tr>
                <td colSpan={6} style={{ ...td, textAlign: "center" }}>
                  Сессий нет
                </td>
              </tr>
            )}
            {sessionsQuery.data.items.map((s) => (
              <tr key={s.id}>
                <td style={td}>{formatDate(s.started_at)}</td>
                <td style={td}>{formatTime(s.started_at)}</td>
                <td style={td}>{formatTime(s.ended_at)}</td>
                <td style={td}>{formatDuration(s.duration_seconds)}</td>
                <td style={td}>{zoneById.get(s.zone_id) ?? `#${s.zone_id}`}</td>
                <td style={{ ...td, color: getStatusColor(s.status), fontWeight: 500 }}>
                  {getStatusLabel(s.status)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
};

const SummaryCard = ({ label, value }: { label: string; value: string }): JSX.Element => (
  <div
    style={{
      padding: "var(--space-4)",
      background: "var(--color-surface)",
      borderRadius: "var(--radius-md)",
      border: "1px solid var(--color-border)",
    }}
  >
    <div style={{ fontSize: 13, color: "var(--color-fg-muted)" }}>{label}</div>
    <div style={{ fontSize: 22, fontWeight: 600 }}>{value}</div>
  </div>
);

const th: React.CSSProperties = {
  textAlign: "left",
  padding: "var(--space-3) var(--space-4)",
  fontSize: 12,
  fontWeight: 600,
  color: "var(--color-fg-muted)",
  textTransform: "uppercase",
  borderBottom: "1px solid var(--color-border)",
};

const td: React.CSSProperties = {
  padding: "var(--space-3) var(--space-4)",
  borderBottom: "1px solid var(--color-border)",
  fontSize: 14,
};
