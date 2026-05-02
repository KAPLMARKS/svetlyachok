import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { useForm } from "react-hook-form";

import type { ZoneResponse } from "@/api/types";
import { Modal } from "@/components/Modal";

import {
  type ZoneCreateInput,
  type ZoneUpdateInput,
  zoneCreateSchema,
  zoneTypeLabels,
  zoneTypes,
  zoneUpdateSchema,
} from "./schema";
import { useCreateZone, useUpdateZone } from "./zonesQueries";

interface Props {
  open: boolean;
  onClose: () => void;
  mode: "create" | "edit";
  zone?: ZoneResponse;
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

export const ZoneFormModal = ({ open, onClose, mode, zone }: Props): JSX.Element => {
  const createMut = useCreateZone();
  const updateMut = useUpdateZone(zone?.id ?? 0);
  const isCreate = mode === "create";
  const schema = isCreate ? zoneCreateSchema : zoneUpdateSchema;

  type FormValues = ZoneCreateInput | ZoneUpdateInput;

  const {
    register,
    handleSubmit,
    reset,
    watch,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: isCreate
      ? { name: "", type: "workplace", description: "", display_color: "" }
      : {
          name: zone?.name ?? "",
          type: zone?.type ?? "workplace",
          description: zone?.description ?? "",
          display_color: zone?.display_color ?? "",
          clear_description: false,
          clear_display_color: false,
        },
  });

  useEffect(() => {
    if (!open) return;
    if (isCreate) {
      reset({ name: "", type: "workplace", description: "", display_color: "" });
    } else if (zone) {
      reset({
        name: zone.name,
        type: zone.type,
        description: zone.description ?? "",
        display_color: zone.display_color ?? "",
        clear_description: false,
        clear_display_color: false,
      });
    }
  }, [open, isCreate, zone, reset]);

  const colorValue = watch("display_color" as never) as unknown as string | undefined;

  const onSubmit = handleSubmit(async (data) => {
    if (isCreate) {
      const input = data as ZoneCreateInput;
      await createMut.mutateAsync({
        name: input.name,
        type: input.type,
        ...(input.description ? { description: input.description } : {}),
        ...(input.display_color ? { display_color: input.display_color } : {}),
      });
    } else {
      const input = data as ZoneUpdateInput;
      const payload: Record<string, unknown> = {};
      if (input.name) payload["name"] = input.name;
      if (input.type) payload["type"] = input.type;
      if (input.clear_description) payload["clear_description"] = true;
      else if (input.description) payload["description"] = input.description;
      if (input.clear_display_color) payload["clear_display_color"] = true;
      else if (input.display_color) payload["display_color"] = input.display_color;
      await updateMut.mutateAsync(payload);
    }
    onClose();
  });

  return (
    <Modal open={open} title={isCreate ? "Новая зона" : "Редактирование зоны"} onClose={onClose}>
      <form onSubmit={onSubmit} style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
        <label style={labelStyle}>
          Название
          <input type="text" {...register("name" as never)} style={inputStyle} />
          {(errors as Record<string, { message?: string }>)["name"] && (
            <span style={{ color: "var(--color-danger)", fontSize: 12 }}>
              {(errors as Record<string, { message?: string }>)["name"]?.message}
            </span>
          )}
        </label>

        <label style={labelStyle}>
          Тип
          <select {...register("type" as never)} style={inputStyle}>
            {zoneTypes.map((t) => (
              <option key={t} value={t}>
                {zoneTypeLabels[t]}
              </option>
            ))}
          </select>
        </label>

        <label style={labelStyle}>
          Описание
          <textarea {...register("description" as never)} rows={3} style={inputStyle} />
        </label>

        <label style={labelStyle}>
          Цвет (на радиокарте)
          <div style={{ display: "flex", gap: "var(--space-3)", alignItems: "center" }}>
            <input
              type="color"
              value={colorValue && colorValue.length > 0 ? colorValue : "#1e88e5"}
              onChange={(e) =>
                setValue("display_color" as never, e.target.value as never, { shouldDirty: true })
              }
              style={{ width: 52, height: 38, padding: 0, border: "1px solid var(--color-border)" }}
            />
            <input
              type="text"
              {...register("display_color" as never)}
              placeholder="#RRGGBB"
              style={{ ...inputStyle, fontFamily: "var(--font-mono)" }}
            />
          </div>
          {(errors as Record<string, { message?: string }>)["display_color"] && (
            <span style={{ color: "var(--color-danger)", fontSize: 12 }}>
              {(errors as Record<string, { message?: string }>)["display_color"]?.message}
            </span>
          )}
        </label>

        {!isCreate && (
          <div style={{ display: "flex", gap: "var(--space-4)", fontSize: 13 }}>
            <label>
              <input type="checkbox" {...register("clear_description" as never)} /> Без описания
            </label>
            <label>
              <input type="checkbox" {...register("clear_display_color" as never)} /> Без цвета
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
