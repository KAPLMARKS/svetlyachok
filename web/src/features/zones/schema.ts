import { z } from "zod";

export const zoneTypes = ["workplace", "corridor", "meeting_room", "outside_office"] as const;

export const zoneTypeLabels: Record<(typeof zoneTypes)[number], string> = {
  workplace: "Рабочее место",
  corridor: "Коридор",
  meeting_room: "Переговорная",
  outside_office: "Вне офиса",
};

const colorRegex = /^#[0-9A-Fa-f]{6}$/;

export const zoneCreateSchema = z.object({
  name: z.string().min(1, "Введите название").max(100),
  type: z.enum(zoneTypes),
  description: z.string().max(500).optional().or(z.literal("")),
  display_color: z.string().regex(colorRegex, "Формат #RRGGBB").optional().or(z.literal("")),
});

export const zoneUpdateSchema = z.object({
  name: z.string().min(1).max(100).optional(),
  type: z.enum(zoneTypes).optional(),
  description: z.string().max(500).optional().or(z.literal("")),
  display_color: z.string().regex(colorRegex).optional().or(z.literal("")),
  clear_description: z.boolean().optional(),
  clear_display_color: z.boolean().optional(),
});

export type ZoneCreateInput = z.infer<typeof zoneCreateSchema>;
export type ZoneUpdateInput = z.infer<typeof zoneUpdateSchema>;
