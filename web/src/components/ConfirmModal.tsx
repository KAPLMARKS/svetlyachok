import { Modal } from "./Modal";

interface ConfirmModalProps {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
  danger?: boolean;
}

export const ConfirmModal = ({
  open,
  title,
  message,
  confirmLabel = "Подтвердить",
  onConfirm,
  onCancel,
  danger = false,
}: ConfirmModalProps): JSX.Element => {
  return (
    <Modal open={open} title={title} onClose={onCancel} maxWidth={400}>
      <p style={{ margin: 0, marginBottom: "var(--space-5)" }}>{message}</p>
      <div style={{ display: "flex", justifyContent: "flex-end", gap: "var(--space-3)" }}>
        <button
          type="button"
          onClick={onCancel}
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
          type="button"
          onClick={onConfirm}
          style={{
            padding: "var(--space-2) var(--space-4)",
            background: danger ? "var(--color-danger)" : "var(--color-primary)",
            color: "var(--color-primary-fg)",
            border: "none",
            borderRadius: "var(--radius-md)",
            cursor: "pointer",
            fontWeight: 600,
          }}
        >
          {confirmLabel}
        </button>
      </div>
    </Modal>
  );
};
