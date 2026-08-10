import { CircleAlert } from "lucide-react";

import { Modal } from "./Modal";

interface ConfirmModalProps {
  open: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  loading?: boolean;
  tone?: "danger" | "primary";
  onConfirm: () => void;
  onCancel: () => void;
}
export function ConfirmModal({ open, title, description, confirmLabel, loading, tone = "danger", onConfirm, onCancel }: ConfirmModalProps) {
  return (
    <Modal open={open} onClose={onCancel} title={title} size="small">
      <div className="confirm-content">
        <span className={`confirm-content__icon confirm-content__icon--${tone}`}><CircleAlert size={24} /></span>
        <p>{description}</p>
      </div>
      <div className="modal-actions">
        <button type="button" className="secondary-button" onClick={onCancel} disabled={loading}>Cancelar</button>
        <button type="button" className={tone === "danger" ? "danger-button" : "primary-action"} onClick={onConfirm} disabled={loading}>
          {loading ? "Procesando…" : confirmLabel}
        </button>
      </div>
    </Modal>
  );
}
