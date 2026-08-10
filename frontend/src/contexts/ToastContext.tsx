import { CheckCircle2, CircleAlert, X } from "lucide-react";
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

type ToastType = "success" | "error";

interface ToastMessage {
  id: number;
  message: string;
  type: ToastType;
}
interface ToastContextValue {
  showToast: (message: string, type?: ToastType) => void;
}

const ToastContext = createContext<ToastContextValue | undefined>(undefined);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const dismiss = useCallback((id: number) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const showToast = useCallback((message: string, type: ToastType = "success") => {
    const id = Date.now() + Math.random();
    setToasts((current) => [...current.slice(-2), { id, message, type }]);
    window.setTimeout(() => dismiss(id), 4500);
  }, [dismiss]);

  const value = useMemo(() => ({ showToast }), [showToast]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="toast-region" aria-live="polite" aria-atomic="false">
        {toasts.map((toast) => (
          <div className={`toast toast--${toast.type}`} key={toast.id} role={toast.type === "error" ? "alert" : "status"}>
            {toast.type === "success" ? <CheckCircle2 size={19} /> : <CircleAlert size={19} />}
            <span>{toast.message}</span>
            <button type="button" onClick={() => dismiss(toast.id)} aria-label="Cerrar notificación"><X size={16} /></button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) throw new Error("useToast debe utilizarse dentro de ToastProvider.");
  return context;
}
