import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";

import { Modal } from "@/components/Modal";

import { useChangePassword } from "./employeesQueries";
import { changePasswordSchema, type ChangePasswordInput } from "./schema";


interface Props {
  open: boolean;
  onClose: () => void;
  employeeId: number;
  /** Если admin меняет пароль другому сотруднику — old_password не нужен. */
  adminReset?: boolean;
}

const inputStyle: React.CSSProperties = {
  padding: "var(--space-3)",
  border: "1px solid var(--color-border)",
  borderRadius: "var(--radius-md)",
  fontSize: 14,
  width: "100%",
};

export const ChangePasswordModal = ({
  open,
  onClose,
  employeeId,
  adminReset = true,
}: Props): JSX.Element => {
  const mutation = useChangePassword(employeeId);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    reset,
  } = useForm<ChangePasswordInput>({
    resolver: zodResolver(changePasswordSchema),
    defaultValues: { new_password: "", old_password: "" },
  });

  const onSubmit = handleSubmit(async (data) => {
    await mutation.mutateAsync({
      new_password: data.new_password,
      ...(!adminReset && data.old_password ? { old_password: data.old_password } : {}),
    });
    reset();
    onClose();
  });

  return (
    <Modal open={open} title="Сменить пароль" onClose={onClose}>
      <form onSubmit={onSubmit} style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
        {!adminReset && (
          <label style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)", fontSize: 13 }}>
            Старый пароль
            <input type="password" {...register("old_password")} style={inputStyle} />
          </label>
        )}
        <label style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)", fontSize: 13 }}>
          Новый пароль (минимум 8 символов)
          <input type="password" {...register("new_password")} style={inputStyle} />
          {errors.new_password && (
            <span style={{ color: "var(--color-danger)", fontSize: 12 }}>{errors.new_password.message}</span>
          )}
        </label>
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
