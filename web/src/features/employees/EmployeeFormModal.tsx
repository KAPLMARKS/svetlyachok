import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { useForm } from "react-hook-form";


import type { EmployeeResponse } from "@/api/types";
import { Modal } from "@/components/Modal";

import { useCreateEmployee, useUpdateEmployee } from "./employeesQueries";
import {
  type EmployeeCreateInput,
  type EmployeeUpdateInput,
  employeeCreateSchema,
  employeeUpdateSchema,
} from "./schema";

interface Props {
  open: boolean;
  onClose: () => void;
  mode: "create" | "edit";
  employee?: EmployeeResponse;
}

const inputStyle: React.CSSProperties = {
  padding: "var(--space-3)",
  border: "1px solid var(--color-border)",
  borderRadius: "var(--radius-md)",
  fontSize: 14,
  width: "100%",
};

const labelStyle: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: "var(--space-1)",
  fontSize: 13,
  fontWeight: 500,
};

const errorStyle: React.CSSProperties = { color: "var(--color-danger)", fontSize: 12 };

const stripSeconds = (t: string | null | undefined): string =>
  typeof t === "string" && t.length >= 5 ? t.slice(0, 5) : "";

export const EmployeeFormModal = ({ open, onClose, mode, employee }: Props): JSX.Element => {
  const createMut = useCreateEmployee();
  const updateMut = useUpdateEmployee(employee?.id ?? 0);

  const isCreate = mode === "create";
  const schema = isCreate ? employeeCreateSchema : employeeUpdateSchema;

  type FormValues = EmployeeCreateInput | EmployeeUpdateInput;

  const {
    register,
    handleSubmit,
    reset,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: isCreate
      ? {
          email: "",
          full_name: "",
          role: "employee",
          initial_password: "",
          schedule_start: "",
          schedule_end: "",
        }
      : {
          full_name: employee?.full_name ?? "",
          role: employee?.role ?? "employee",
          schedule_start: stripSeconds(employee?.schedule_start),
          schedule_end: stripSeconds(employee?.schedule_end),
          clear_schedule_start: false,
          clear_schedule_end: false,
        },
  });

  useEffect(() => {
    if (!open) return;
    if (isCreate) {
      reset({
        email: "",
        full_name: "",
        role: "employee",
        initial_password: "",
        schedule_start: "",
        schedule_end: "",
      });
    } else if (employee) {
      reset({
        full_name: employee.full_name,
        role: employee.role,
        schedule_start: stripSeconds(employee.schedule_start),
        schedule_end: stripSeconds(employee.schedule_end),
        clear_schedule_start: false,
        clear_schedule_end: false,
      });
    }
  }, [open, isCreate, employee, reset]);

  const clearStart = watch("clear_schedule_start" as never);
  const clearEnd = watch("clear_schedule_end" as never);

  const onSubmit = handleSubmit(async (data) => {
    if (isCreate) {
      const input = data as EmployeeCreateInput;
      const payload = {
        email: input.email,
        full_name: input.full_name,
        role: input.role,
        initial_password: input.initial_password,
        ...(input.schedule_start ? { schedule_start: `${input.schedule_start}:00` } : {}),
        ...(input.schedule_end ? { schedule_end: `${input.schedule_end}:00` } : {}),
      };
      await createMut.mutateAsync(payload);
    } else {
      const input = data as EmployeeUpdateInput;
      const payload: Record<string, unknown> = {};
      if (input.full_name) payload["full_name"] = input.full_name;
      if (input.role) payload["role"] = input.role;
      if (input.clear_schedule_start) {
        payload["clear_schedule_start"] = true;
      } else if (input.schedule_start) {
        payload["schedule_start"] = `${input.schedule_start}:00`;
      }
      if (input.clear_schedule_end) {
        payload["clear_schedule_end"] = true;
      } else if (input.schedule_end) {
        payload["schedule_end"] = `${input.schedule_end}:00`;
      }
      await updateMut.mutateAsync(payload);
    }
    onClose();
  });

  return (
    <Modal open={open} title={isCreate ? "Новый сотрудник" : "Редактирование"} onClose={onClose}>
      <form onSubmit={onSubmit} style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
        {isCreate && (
          <label style={labelStyle}>
            Email
            <input type="email" {...register("email" as never)} style={inputStyle} />
            {(errors as Record<string, { message?: string }>)["email"] && (
              <span style={errorStyle}>
                {(errors as Record<string, { message?: string }>)["email"]?.message}
              </span>
            )}
          </label>
        )}

        <label style={labelStyle}>
          ФИО
          <input type="text" {...register("full_name" as never)} style={inputStyle} />
          {(errors as Record<string, { message?: string }>)["full_name"] && (
            <span style={errorStyle}>
              {(errors as Record<string, { message?: string }>)["full_name"]?.message}
            </span>
          )}
        </label>

        <label style={labelStyle}>
          Роль
          <select {...register("role" as never)} style={inputStyle}>
            <option value="employee">Сотрудник</option>
            <option value="admin">Администратор</option>
          </select>
        </label>

        {isCreate && (
          <label style={labelStyle}>
            Начальный пароль
            <input type="password" {...register("initial_password" as never)} style={inputStyle} />
            {(errors as Record<string, { message?: string }>)["initial_password"] && (
              <span style={errorStyle}>
                {(errors as Record<string, { message?: string }>)["initial_password"]?.message}
              </span>
            )}
          </label>
        )}

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-3)" }}>
          <label style={labelStyle}>
            Начало
            <input
              type="time"
              disabled={!isCreate && Boolean(clearStart)}
              {...register("schedule_start" as never)}
              style={inputStyle}
            />
          </label>
          <label style={labelStyle}>
            Окончание
            <input
              type="time"
              disabled={!isCreate && Boolean(clearEnd)}
              {...register("schedule_end" as never)}
              style={inputStyle}
            />
            {(errors as Record<string, { message?: string }>)["schedule_end"] && (
              <span style={errorStyle}>
                {(errors as Record<string, { message?: string }>)["schedule_end"]?.message}
              </span>
            )}
          </label>
        </div>

        {!isCreate && (
          <div style={{ display: "flex", gap: "var(--space-4)", fontSize: 13 }}>
            <label>
              <input type="checkbox" {...register("clear_schedule_start" as never)} /> Без начала
            </label>
            <label>
              <input type="checkbox" {...register("clear_schedule_end" as never)} /> Без окончания
            </label>
          </div>
        )}

        <div style={{ display: "flex", justifyContent: "flex-end", gap: "var(--space-3)" }}>
          <button
            type="button"
            onClick={onClose}
            style={{
              padding: "var(--space-2) var(--space-4)",
              background: "transparent",
              border: "1px solid var(--color-border)",
              borderRadius: "var(--radius-md)",
              cursor: "pointer",
            }}
          >
            Отмена
          </button>
          <button
            type="submit"
            disabled={isSubmitting}
            style={{
              padding: "var(--space-2) var(--space-4)",
              background: "var(--color-primary)",
              color: "var(--color-primary-fg)",
              border: "none",
              borderRadius: "var(--radius-md)",
              cursor: "pointer",
              fontWeight: 600,
            }}
          >
            {isSubmitting ? "Сохраняем…" : "Сохранить"}
          </button>
        </div>
      </form>
    </Modal>
  );
};
