import { Brand } from "./Brand";

export function FullPageLoader() {
  return (
    <div className="page-loader" role="status" aria-live="polite">
      <Brand />
      <span className="spinner" aria-hidden="true" />
      <span className="sr-only">Cargando Memora</span>
    </div>
  );
}

