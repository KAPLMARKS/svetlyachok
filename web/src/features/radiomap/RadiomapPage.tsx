import { useMemo, useState } from "react";

import { ConfirmModal } from "@/components/ConfirmModal";
import { zoneTypeLabels } from "@/features/zones/schema";
import { useZonesQuery } from "@/features/zones/zonesQueries";

import { RadiomapCanvas } from "./RadiomapCanvas";
import { useCalibrationPointsQuery, useDeleteCalibrationPoint } from "./radiomapQueries";
import { MIN_CALIBRATION_POINTS_PER_ZONE, zoneTypeColor } from "./zoneLayout";

const CALIBRATABLE_TYPES = ["workplace", "corridor", "meeting_room"] as const;

export const RadiomapPage = (): JSX.Element => {
  const [zoneFilter, setZoneFilter] = useState<number | "">("");
  const [deleteId, setDeleteId] = useState<number | null>(null);

  const zonesQuery = useZonesQuery();
  const pointsQuery = useCalibrationPointsQuery(
    zoneFilter === "" ? undefined : zoneFilter,
  );
  const deleteMut = useDeleteCalibrationPoint();

  const stats = useMemo(() => {
    if (!zonesQuery.data || !pointsQuery.data) return null;
    const calibrable = zonesQuery.data.filter((z) =>
      (CALIBRATABLE_TYPES as readonly string[]).includes(z.type),
    );
    const counts = new Map<number, number>();
    for (const p of pointsQuery.data) {
      if (p.zone_id === null) continue;
      counts.set(p.zone_id, (counts.get(p.zone_id) ?? 0) + 1);
    }
    const ready = calibrable.filter(
      (z) => (counts.get(z.id) ?? 0) >= MIN_CALIBRATION_POINTS_PER_ZONE,
    ).length;
    return { ready, total: calibrable.length, counts };
  }, [zonesQuery.data, pointsQuery.data]);

  return (
    <div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "var(--space-4)",
          flexWrap: "wrap",
          gap: "var(--space-3)",
        }}
      >
        <h1 style={{ margin: 0 }}>Радиокарта</h1>
        <div style={{ display: "flex", gap: "var(--space-3)", alignItems: "center" }}>
          <label style={{ fontSize: 13 }}>
            Зона:{" "}
            <select
              value={zoneFilter}
              onChange={(e) =>
                setZoneFilter(e.target.value === "" ? "" : Number(e.target.value))
              }
              style={{
                padding: "var(--space-2) var(--space-3)",
                border: "1px solid var(--color-border)",
                borderRadius: "var(--radius-md)",
              }}
            >
              <option value="">Все</option>
              {zonesQuery.data?.map((z) => (
                <option key={z.id} value={z.id}>
                  {z.name}
                </option>
              ))}
            </select>
          </label>
          {stats !== null && (
            <span
              style={{
                padding: "var(--space-2) var(--space-3)",
                background:
                  stats.ready === stats.total
                    ? "#c6f6d5"
                    : stats.ready === 0
                      ? "#fed7d7"
                      : "#fefcbf",
                borderRadius: "var(--radius-md)",
                fontSize: 13,
                fontWeight: 500,
              }}
            >
              {stats.ready} / {stats.total} зон откалибровано (≥{" "}
              {MIN_CALIBRATION_POINTS_PER_ZONE} точек)
            </span>
          )}
        </div>
      </div>

      {(zonesQuery.isLoading || pointsQuery.isLoading) && <p>Загрузка…</p>}

      {zonesQuery.data && pointsQuery.data && (
        <>
          <RadiomapCanvas
            zones={zonesQuery.data}
            points={pointsQuery.data}
            onPointClick={(id) => setDeleteId(id)}
          />

          <div
            style={{
              marginTop: "var(--space-4)",
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))",
              gap: "var(--space-3)",
            }}
          >
            {zonesQuery.data.map((z) => {
              const count = stats?.counts.get(z.id) ?? 0;
              const color = z.display_color ?? zoneTypeColor[z.type] ?? "#1e88e5";
              return (
                <div
                  key={z.id}
                  style={{
                    padding: "var(--space-3)",
                    background: "var(--color-surface)",
                    borderRadius: "var(--radius-md)",
                    border: "1px solid var(--color-border)",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "var(--space-2)",
                      fontWeight: 500,
                    }}
                  >
                    <span
                      style={{
                        width: 12,
                        height: 12,
                        borderRadius: "50%",
                        background: color,
                      }}
                    />
                    {z.name}
                  </div>
                  <div style={{ fontSize: 12, color: "var(--color-fg-muted)", marginTop: 4 }}>
                    {zoneTypeLabels[z.type]} · {count} точек
                  </div>
                </div>
              );
            })}
          </div>

          {pointsQuery.data.length === 0 && (
            <div
              style={{
                marginTop: "var(--space-5)",
                padding: "var(--space-5)",
                background: "var(--color-surface)",
                border: "1px dashed var(--color-border)",
                borderRadius: "var(--radius-md)",
                textAlign: "center",
              }}
            >
              <p style={{ margin: 0 }}>
                Радиокарта пуста. Откалибруйте зоны через mobile-приложение в режиме админа.
              </p>
            </div>
          )}
        </>
      )}

      <ConfirmModal
        open={deleteId !== null}
        title="Удалить точку калибровки"
        message="Точка будет удалена без возможности восстановления. Продолжить?"
        confirmLabel="Удалить"
        danger
        onCancel={() => setDeleteId(null)}
        onConfirm={() => {
          if (deleteId !== null) {
            deleteMut.mutate(deleteId, {
              onSettled: () => setDeleteId(null),
            });
          }
        }}
      />
    </div>
  );
};
