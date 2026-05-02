import { Edit, KeyRound, ShieldOff, ShieldCheck, UserPlus } from "lucide-react";
import { useState } from "react";

import type { EmployeeResponse } from "@/api/types";
import { ConfirmModal } from "@/components/ConfirmModal";
import { useAuthStore } from "@/features/auth/authStore";

import { ChangePasswordModal } from "./ChangePasswordModal";
import { EmployeeFormModal } from "./EmployeeFormModal";
import {
  useActivateEmployee,
  useDeactivateEmployee,
  useEmployeesQuery,
} from "./employeesQueries";


const stripSec = (t: string | null): string => (t === null ? "—" : t.slice(0, 5));

const PAGE_SIZE = 20;

export const EmployeesListPage = (): JSX.Element => {
  const [offset, setOffset] = useState(0);
  const [search, setSearch] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<EmployeeResponse | null>(null);
  const [pwdTarget, setPwdTarget] = useState<EmployeeResponse | null>(null);
  const [deactivateTarget, setDeactivateTarget] = useState<EmployeeResponse | null>(null);

  const me = useAuthStore((s) => s.currentUser);
  const query = useEmployeesQuery({
    limit: PAGE_SIZE,
    offset,
    ...(search ? { search } : {}),
  });

  const deactivateMut = useDeactivateEmployee(deactivateTarget?.id ?? 0);
  const activateMut = useActivateEmployee(0);

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
        <h1 style={{ margin: 0 }}>Сотрудники</h1>
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
          <UserPlus size={16} /> Добавить
        </button>
      </div>

      <input
        type="search"
        placeholder="Поиск по email / ФИО"
        value={search}
        onChange={(e) => {
          setSearch(e.target.value);
          setOffset(0);
        }}
        style={{
          padding: "var(--space-3)",
          border: "1px solid var(--color-border)",
          borderRadius: "var(--radius-md)",
          width: "100%",
          maxWidth: 400,
          marginBottom: "var(--space-4)",
        }}
      />

      {query.isLoading && <p>Загрузка…</p>}
      {query.isError && <p style={{ color: "var(--color-danger)" }}>Не удалось загрузить список</p>}

      {query.data && (
        <>
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
                <th style={th}>ФИО</th>
                <th style={th}>Email</th>
                <th style={th}>Роль</th>
                <th style={th}>Расписание</th>
                <th style={th}>Статус</th>
                <th style={th}>Действия</th>
              </tr>
            </thead>
            <tbody>
              {query.data.items.length === 0 && (
                <tr>
                  <td colSpan={7} style={{ ...td, textAlign: "center", padding: "var(--space-6)" }}>
                    Сотрудников нет
                  </td>
                </tr>
              )}
              {query.data.items.map((e) => {
                const isSelf = me?.id === e.id;
                return (
                  <tr key={e.id}>
                    <td style={td}>{e.id}</td>
                    <td style={td}>{e.full_name}</td>
                    <td style={td}>{e.email}</td>
                    <td style={td}>{e.role === "admin" ? "Администратор" : "Сотрудник"}</td>
                    <td style={td}>
                      {stripSec(e.schedule_start)} – {stripSec(e.schedule_end)}
                    </td>
                    <td style={td}>
                      <span
                        style={{
                          padding: "2px 8px",
                          borderRadius: "var(--radius-sm)",
                          fontSize: 12,
                          background: e.is_active ? "#c6f6d5" : "#fed7d7",
                          color: e.is_active ? "#22543d" : "#742a2a",
                        }}
                      >
                        {e.is_active ? "active" : "inactive"}
                      </span>
                    </td>
                    <td style={td}>
                      <div style={{ display: "flex", gap: "var(--space-2)" }}>
                        <button
                          type="button"
                          onClick={() => setEditTarget(e)}
                          style={iconBtn}
                          aria-label="Редактировать"
                        >
                          <Edit size={14} />
                        </button>
                        <button
                          type="button"
                          onClick={() => setPwdTarget(e)}
                          style={iconBtn}
                          aria-label="Сменить пароль"
                        >
                          <KeyRound size={14} />
                        </button>
                        {!isSelf && e.is_active && (
                          <button
                            type="button"
                            onClick={() => setDeactivateTarget(e)}
                            style={{ ...iconBtn, color: "var(--color-danger)" }}
                            aria-label="Деактивировать"
                          >
                            <ShieldOff size={14} />
                          </button>
                        )}
                        {!e.is_active && (
                          <button
                            type="button"
                            onClick={() => activateMut.mutate(undefined, { onSuccess: () => null })}
                            style={{ ...iconBtn, color: "var(--color-success)" }}
                            aria-label="Активировать"
                          >
                            <ShieldCheck size={14} />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          <div style={{ marginTop: "var(--space-4)", display: "flex", gap: "var(--space-3)", alignItems: "center" }}>
            <button
              type="button"
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
              style={pageBtn(offset === 0)}
            >
              Назад
            </button>
            <span style={{ fontSize: 13 }}>
              {offset + 1}–{Math.min(offset + PAGE_SIZE, query.data.total)} из {query.data.total}
            </span>
            <button
              type="button"
              disabled={offset + PAGE_SIZE >= query.data.total}
              onClick={() => setOffset(offset + PAGE_SIZE)}
              style={pageBtn(offset + PAGE_SIZE >= query.data.total)}
            >
              Вперёд
            </button>
          </div>
        </>
      )}

      <EmployeeFormModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        mode="create"
      />
      <EmployeeFormModal
        open={editTarget !== null}
        onClose={() => setEditTarget(null)}
        mode="edit"
        {...(editTarget !== null ? { employee: editTarget } : {})}
      />
      {pwdTarget !== null && (
        <ChangePasswordModal
          open={pwdTarget !== null}
          onClose={() => setPwdTarget(null)}
          employeeId={pwdTarget.id}
        />
      )}
      <ConfirmModal
        open={deactivateTarget !== null}
        title="Деактивировать сотрудника"
        message={`${deactivateTarget?.full_name} больше не сможет логиниться. Продолжить?`}
        confirmLabel="Деактивировать"
        danger
        onCancel={() => setDeactivateTarget(null)}
        onConfirm={() => {
          if (deactivateTarget !== null) {
            deactivateMut.mutate(undefined, {
              onSettled: () => setDeactivateTarget(null),
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

const pageBtn = (disabled: boolean): React.CSSProperties => ({
  padding: "var(--space-2) var(--space-3)",
  border: "1px solid var(--color-border)",
  borderRadius: "var(--radius-md)",
  background: "transparent",
  cursor: disabled ? "not-allowed" : "pointer",
  opacity: disabled ? 0.5 : 1,
});
