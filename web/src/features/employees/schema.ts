import { z } from "zod";

export const employeeRoles = ["admin", "employee"] as const;

const timeRegex = /^\d{2}:\d{2}$/;

export const employeeCreateSchema = z
  .object({
    email: z.string().email("Некорректный email"),
    full_name: z.string().min(1, "Введите ФИО").max(255),
    role: z.enum(employeeRoles),
    initial_password: z
      .string()
      .min(8, "Минимум 8 символов")
      .max(128, "Максимум 128 символов"),
    schedule_start: z.string().regex(timeRegex, "Формат HH:MM").optional().or(z.literal("")),
    schedule_end: z.string().regex(timeRegex, "Формат HH:MM").optional().or(z.literal("")),
  })
  .refine(
    (v) => {
      if (v.schedule_start && v.schedule_end) {
        return v.schedule_end > v.schedule_start;
      }
      return true;
    },
    { message: "Окончание раньше начала", path: ["schedule_end"] },
  );

export const employeeUpdateSchema = z
  .object({
    full_name: z.string().min(1).max(255).optional(),
    role: z.enum(employeeRoles).optional(),
    schedule_start: z.string().regex(timeRegex).optional().or(z.literal("")),
    schedule_end: z.string().regex(timeRegex).optional().or(z.literal("")),
    clear_schedule_start: z.boolean().optional(),
    clear_schedule_end: z.boolean().optional(),
  })
  .refine(
    (v) => {
      if (v.schedule_start && v.schedule_end) {
        return v.schedule_end > v.schedule_start;
      }
      return true;
    },
    { message: "Окончание раньше начала", path: ["schedule_end"] },
  );

export const changePasswordSchema = z.object({
  new_password: z.string().min(8, "Минимум 8 символов").max(128),
  old_password: z.string().optional(),
});

export type EmployeeCreateInput = z.infer<typeof employeeCreateSchema>;
export type EmployeeUpdateInput = z.infer<typeof employeeUpdateSchema>;
export type ChangePasswordInput = z.infer<typeof changePasswordSchema>;
