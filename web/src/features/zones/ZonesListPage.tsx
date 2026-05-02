import { Edit, Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import type { ZoneResponse } from "@/api/types";
import { ConfirmModal } from "@/components/ConfirmModal";

import { zoneTypeLabels } from "./schema";
import { ZoneFormModal } from "./ZoneFormModal";
import { useDeleteZone, useZonesQuery } from "./zonesQueries";

export const ZonesListPage = (): JSX.Element => {
  const [createOpen, setCreateOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<ZoneResponse | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ZoneResponse | null>(null);

  const query = useZonesQuery();
  const deleteMut = useDeleteZone();

  return (
    <div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "var(--space-4)",
        }}
      >
        <h1 style={{ margin: 0 }}>Зоны</h1>
        <button
          type="button"
          onClick={() => setCreateOpen(true)}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "var(--space-2)",
            padding: "var(--space-2) var(--space-4)",
            background: "var(--color-primary)",
            color: "var(--color-primary-fg)",
            border: "none",
            borderRadius: "var(--radius-md)",
            cursor: "pointer",
            fontWeight: 600,
          }}
        >
          <Plus size={16} /> Добавить
        </button>
      </div>

      {query.isLoading && <p>Загрузка…</p>}
      {query.isError && <p style={{ color: "var(--color-danger)" }}>Не удалось загрузить</p>}

      {query.data && (
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
              <th style={th}>ID</th>
              <th style={th}>Название</th>
              <th style={th}>Тип</th>
              <th style={th}>Цвет</th>
              <th style={th}>Описание</th>
              <th style={th}>Действия</th>
            </tr>
          </thead>
          <tbody>
            {query.data.length === 0 && (
              <tr>
                <td colSpan={6} style={{ ...td, textAlign: "center", padding: "var(--space-6)" }}>
                  Зоны не созданы
                </td>
              </tr>
            )}
            {query.data.map((z) => (
              <tr key={z.id}>
                <td style={td}>{z.id}</td>
                <td style={td}>{z.name}</td>
                <td style={td}>{zoneTypeLabels[z.type]}</td>
                <td style={td}>
                  {z.display_color !== null ? (
                    <span
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "var(--space-2)",
                      }}
                    >
                      <span
                        style={{
                          width: 16,
                          height: 16,
                          borderRadius: 4,
                          background: z.display_color,
                          border: "1px solid var(--color-border)",
                        }}
                      />
                      <code style={{ fontSize: 12 }}>{z.display_color}</code>
                    </span>
                  ) : (
                    <span style={{ color: "var(--color-fg-muted)" }}>—</span>
                  )}
                </td>
                <td style={{ ...td, color: "var(--color-fg-muted)" }}>
                  {z.description ?? "—"}
                </td>
                <td style={td}>
                  <div style={{ display: "flex", gap: "var(--space-2)" }}>
                    <button
                      type="button"
                      onClick={() => setEditTarget(z)}
                      style={iconBtn}
                      aria-label="Редактировать"
                    >
                      <Edit size={14} />
                    </button>
                    <button
                      type="button"
                      onClick={() => setDeleteTarget(z)}
                      style={{ ...iconBtn, color: "var(--color-danger)" }}
                      aria-label="Удалить"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <ZoneFormModal open={createOpen} onClose={() => setCreateOpen(false)} mode="create" />
      <ZoneFormModal
        open={editTarget !== null}
        onClose={() => setEditTarget(null)}
        mode="edit"
        {...(editTarget !== null ? { zone: editTarget } : {})}
      />
      <ConfirmModal
        open={deleteTarget !== null}
        title="Удалить зону"
        message={`Удалить «${deleteTarget?.name ?? ""}»? Если на зону есть ссылки в учёте — backend отдаст 409.`}
        confirmLabel="Удалить"
        danger
        onCancel={() => setDeleteTarget(null)}
        onConfirm={() => {
          if (deleteTarget !== null) {
            deleteMut.mutate(deleteTarget.id, {
              onSettled: () => setDeleteTarget(null),
            });
          }
        }}
      />
    </div>
  );
};

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

const iconBtn: React.CSSProperties = {
  background: "transparent",
  border: "1px solid var(--color-border)",
  borderRadius: "var(--radius-sm)",
  padding: "var(--space-1) var(--space-2)",
  cursor: "pointer",
  display: "flex",
  alignItems: "center",
};
