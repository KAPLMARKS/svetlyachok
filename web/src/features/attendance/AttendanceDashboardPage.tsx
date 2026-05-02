import { useMemo } from "react";
import { useNavigate } from "react-router-dom";

import { useEmployeesQuery } from "@/features/employees/employeesQueries";
import { useZonesQuery } from "@/features/zones/zonesQueries";
import { toEmployeeAttendanceUrl } from "@/routes/routes";

import { useCurrentZonesQuery } from "./attendanceQueries";
import { dayPresets, formatTime, getStatusColor, getStatusLabel } from "./helpers";

export const AttendanceDashboardPage = (): JSX.Element => {
  const navigate = useNavigate();
  const presets = dayPresets();

  const employeesQuery = useEmployeesQuery({ limit: 100, is_active: true });
  const zonesQuery = useZonesQuery();

  const employeeIds = useMemo(
    () => employeesQuery.data?.items.map((e) => e.id) ?? [],
    [employeesQuery.data],
  );

  const currentZones = useCurrentZonesQuery(employeeIds, presets.today.from);

  const zoneById = useMemo(() => {
    const m = new Map<number, { name: string; color: string | null; type: string }>();
    for (const z of zonesQuery.data ?? []) {
      m.set(z.id, { name: z.name, color: z.display_color, type: z.type });
    }
    return m;
  }, [zonesQuery.data]);

  const counters = useMemo(() => {
    let workplace = 0;
    let corridor = 0;
    let meeting = 0;
    let absent = 0;
    for (const id of employeeIds) {
      const session = currentZones.get(id);
      if (!session || session.ended_at !== null) {
        absent++;
        continue;
      }
      const zone = zoneById.get(session.zone_id);
      if (zone === undefined) continue;
      if (zone.type === "workplace") workplace++;
      else if (zone.type === "corridor") corridor++;
      else if (zone.type === "meeting_room") meeting++;
      else absent++;
    }
    return { workplace, corridor, meeting, absent };
  }, [employeeIds, currentZones, zoneById]);

  return (
    <div>
      <h1 style={{ marginTop: 0 }}>Учёт времени</h1>

      {/* Counters */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))",
          gap: "var(--space-3)",
          marginBottom: "var(--space-5)",
        }}
      >
        <CounterCard label="На рабочих местах" value={counters.workplace} color="#1e88e5" />
        <CounterCard label="В коридоре" value={counters.corridor} color="#718096" />
        <CounterCard label="На переговорной" value={counters.meeting} color="#38a169" />
        <CounterCard label="Не на месте" value={counters.absent} color="#c53030" />
      </div>

      {/* Table */}
      {employeesQuery.isLoading && <p>Загрузка…</p>}
      {employeesQuery.data && (
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
              <th style={th}>Сотрудник</th>
              <th style={th}>Email</th>
              <th style={th}>Зона</th>
              <th style={th}>С</th>
              <th style={th}>Статус</th>
            </tr>
          </thead>
          <tbody>
            {employeesQuery.data.items.map((e) => {
              const session = currentZones.get(e.id);
              const zone = session !== null && session !== undefined ? zoneById.get(session.zone_id) : undefined;
              const isOpen = session !== null && session?.ended_at === null;
              return (
                <tr
                  key={e.id}
                  onClick={() => navigate(toEmployeeAttendanceUrl(e.id))}
                  style={{ cursor: "pointer" }}
                >
                  <td style={td}>{e.full_name}</td>
                  <td style={td}>{e.email}</td>
                  <td style={td}>
                    {session !== null && session !== undefined && zone !== undefined ? (
                      <span
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "var(--space-2)",
                        }}
                      >
                        <span
                          style={{
                            width: 10,
                            height: 10,
                            borderRadius: "50%",
                            background: zone.color ?? "var(--color-fg-muted)",
                          }}
                        />
                        {zone.name}
                      </span>
                    ) : (
                      <span style={{ color: "var(--color-fg-muted)" }}>—</span>
                    )}
                  </td>
                  <td style={td}>
                    {isOpen ? formatTime(session?.started_at ?? null) : "—"}
                  </td>
                  <td style={td}>
                    {session !== null && session !== undefined ? (
                      <span style={{ color: getStatusColor(session.status), fontWeight: 500 }}>
                        {getStatusLabel(session.status)}
                      </span>
                    ) : (
                      <span style={{ color: "var(--color-fg-muted)" }}>Не отмечался сегодня</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
};

const CounterCard = ({ label, value, color }: { label: string; value: number; color: string }): JSX.Element => (
  <div
    style={{
      padding: "var(--space-4)",
      background: "var(--color-surface)",
      borderRadius: "var(--radius-md)",
      border: "1px solid var(--color-border)",
      borderLeft: `4px solid ${color}`,
    }}
  >
    <div style={{ fontSize: 13, color: "var(--color-fg-muted)" }}>{label}</div>
    <div style={{ fontSize: 28, fontWeight: 600 }}>{value}</div>
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
