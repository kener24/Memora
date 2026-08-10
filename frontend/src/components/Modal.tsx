import { X } from "lucide-react";
import { useEffect, useId, type ReactNode } from "react";

interface ModalProps {
  title: string;
  description?: string;
  open: boolean;
  onClose: () => void;
  children: ReactNode;
  size?: "small" | "large";
}
export function Modal({ title, description, open, onClose, children, size = "large" }: ModalProps) {
  const titleId = useId();
  useEffect(() => {
    if (!open) return;
    function handleKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKey);
    document.body.classList.add("modal-open");
    return () => {
      document.removeEventListener("keydown", handleKey);
      document.body.classList.remove("modal-open");
    };
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section className={`modal-dialog modal-dialog--${size}`} role="dialog" aria-modal="true" aria-labelledby={titleId}>
        <header className="modal-dialog__header">
          <div><h2 id={titleId}>{title}</h2>{description && <p>{description}</p>}</div>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Cerrar"><X size={20} /></button>
        </header>
        <div className="modal-dialog__body">{children}</div>
      </section>
    </div>
  );
}
